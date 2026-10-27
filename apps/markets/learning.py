"""Train chronological challengers and publish only independently checked predictions."""

import logging
import math
from collections import Counter
from datetime import date, datetime, timedelta

from django.db import transaction
from django.db.models import F, Window
from django.db.models.functions import RowNumber

from .models import ForecastModel, ForecastSample
from .watchdog import check_forecast, check_model, check_rule

logger = logging.getLogger(__name__)

LABELS = {
    "market": ("down", "flat", "up"),
    "company": ("down", "flat", "up"),
    "ipo": ("weak", "good"),
}
FEATURE_COUNTS = {"market": 4, "company": 3, "ipo": 6}
MIN_TRAIN_DAYS = 60
MIN_TEST_DAYS = 20
MIN_CLASS_SAMPLES = 10
MIN_CLASSES = 2
PROMOTION_MARGIN = 0.05
MODEL_MAX_AGE = timedelta(days=7)
MAX_HISTORY_DAYS = 730
MAX_TRAIN_SAMPLES = 20_000


def _policy(kind: str, context: dict) -> dict:
    """Keep incompatible outcome definitions out of the same training cohort.

    Args:
        kind: The forecast family.
        context: The reference values and outcome thresholds for the forecast.

    Returns:
        The context values that define a compatible training cohort.
    """
    keys = (
        ("symbol", "band")
        if kind == "market"
        else ("band",)
        if kind == "company"
        else ("good_gain",)
    )
    return {key: context[key] for key in keys}


def infer(parameters: dict, features: list[float]) -> tuple[str, float, float]:
    """Evaluate JSON logistic coefficients without loading an executable model artifact.

    Args:
        parameters: The classifier coefficients, scaling values, and class labels.
        features: The input values in the trained feature order.

    Returns:
        The predicted label, directional score, and winning class probability.

    Raises:
        ValueError: If the input feature count does not match the model schema.
    """
    if len(features) != len(parameters["mean"]):
        raise ValueError("Forecast model feature schema does not match the inputs.")
    normalized = [
        (value - mean) / scale
        for value, mean, scale in zip(
            features, parameters["mean"], parameters["scale"], strict=True
        )
    ]
    logits = [
        bias + sum(weight * value for weight, value in zip(row, normalized, strict=True))
        for row, bias in zip(parameters["coef"], parameters["intercept"], strict=True)
    ]
    if len(logits) == 1:
        positive = 1 / (1 + math.exp(-max(-700.0, min(700.0, logits[0]))))
        probabilities = [1 - positive, positive]
    else:
        largest = max(logits)
        exponents = [math.exp(value - largest) for value in logits]
        probabilities = [value / sum(exponents) for value in exponents]
    by_label = dict(zip(parameters["classes"], probabilities, strict=True))
    label = max(by_label, key=by_label.__getitem__)
    score = by_label.get("up", by_label.get("good", 0.0)) - by_label.get(
        "down", by_label.get("weak", 0.0)
    )
    return label, score, by_label[label]


def forecast(  # noqa: PLR0913
    kind: str,
    entity: str,
    target: date,
    features: list[float],
    *,
    rule_label: str,
    rule_score: float,
    now: datetime,
    deadline: datetime,
    context: dict,
    reasons: list[str],
    rule_strength: float | None = None,
) -> tuple[str, float, dict]:
    """Choose a validated model or explicit experimental rule, then apply the watchdog.

    Args:
        kind: The forecast family.
        entity: The identifier of the forecast subject.
        target: The session date being forecast.
        features: The normalized input values in the family's feature order.
        rule_label: The experimental rule's predicted label.
        rule_score: The experimental rule's directional score.
        now: The forecast issue time.
        deadline: The cutoff for publishing the forecast.
        context: The reference values and settings used by the rule and outcome policy.
        reasons: Existing reasons to withhold publication.
        rule_strength: The optional signal strength of the experimental rule.

    Returns:
        The chosen label, score, and metadata containing the watchdog audit.

    Raises:
        ValueError: If the feature count does not match the forecast family.
    """
    label, score = rule_label, rule_score
    reasons = list(reasons)
    if len(features) != FEATURE_COUNTS[kind]:
        raise ValueError(f"Wrong feature count for {kind}.")
    reasons.extend(check_rule(kind, features, rule_score, rule_label, context))
    model = ForecastModel.objects.filter(kind=kind).first()
    metadata = {
        "method": "experimental-rule",
        "experimental": True,
        "validation": model.metrics if model else {"reason": "No trained model yet."},
    }
    if (
        not reasons
        and model
        and model.approved
        and now - MODEL_MAX_AGE <= model.trained_at <= now
        and model.parameters.get("policy") == _policy(kind, context)
    ):
        label, score, strength = infer(model.parameters, features)
        metadata.update(
            method="logistic-v1",
            experimental=False,
            trained_at=model.trained_at.isoformat(),
            model_strength=strength,
            model_id=model.pk,
        )
        reasons.extend(check_model(model.parameters, features, label, score, strength))
    allowed = LABELS[kind] + (("mixed",) if kind == "ipo" else ())
    audit = check_forecast(
        features, score, label, allowed=allowed, now=now, deadline=deadline, reasons=reasons
    )
    metadata["watchdog"] = audit
    metadata["rule_score"] = rule_score if math.isfinite(rule_score) else None
    metadata["score"] = score if math.isfinite(score) else None
    metadata["strength"] = metadata.get("model_strength", rule_strength)
    # Only pending, pre-deadline evidence may be refreshed.
    with transaction.atomic():
        sample, created = ForecastSample.objects.select_for_update().get_or_create(
            kind=kind,
            entity=entity,
            target_date=target,
            defaults={
                "issued_at": now,
                "deadline": deadline,
                "features": features if audit["status"] == "passed" else [],
                "context": context,
                "rule_label": rule_label,
                "predicted_label": label,
                "audit": metadata,
            },
        )
        if not created and now < sample.deadline and sample.observed_at is None:
            sample.issued_at = now
            sample.features = features if audit["status"] == "passed" else []
            sample.context = context
            sample.rule_label = rule_label
            sample.predicted_label = label
            sample.audit = metadata
            sample.save()
    return label, score, metadata


def _training_rows(kind: str, now: datetime) -> list[ForecastSample]:
    """Read only outcomes actually available before this training run.

    Args:
        kind: The forecast family to train.
        now: The training time and cutoff for observed outcomes.

    Returns:
        Eligible samples in chronological order, capped per session date.
    """
    eligible = ForecastSample.objects.filter(
        kind=kind,
        observed_at__lte=now,
        issued_at__lt=F("deadline"),
        deadline__lte=F("observed_at"),
        target_date__gte=(now - timedelta(days=MAX_HISTORY_DAYS)).date(),
        audit__watchdog__status="passed",
        actual_label__in=LABELS[kind],
    )
    dates = list(eligible.order_by("target_date").values_list("target_date", flat=True).distinct())
    if not dates:
        return []
    per_date = max(1, MAX_TRAIN_SAMPLES // len(dates))
    # A large company universe must not crowd older dates out of chronological validation.
    return list(
        eligible.annotate(
            date_row=Window(
                expression=RowNumber(), partition_by=[F("target_date")], order_by="entity"
            )
        )
        .filter(date_row__lte=per_date)
        .order_by("target_date", "pk")
    )


def train_model(kind: str, now: datetime) -> dict:
    """Test one fixed regularized model on untouched later dates before promoting it.

    Args:
        kind: The forecast family to train.
        now: The training time and cutoff for available evidence.

    Returns:
        Training and validation metrics with the model's approval status.

    Raises:
        ValueError: If the fitted scaler has no vector parameters.
    """
    from numpy import ndarray  # noqa: PLC0415
    from sklearn.linear_model import LogisticRegression  # noqa: PLC0415
    from sklearn.preprocessing import StandardScaler  # noqa: PLC0415

    rows = _training_rows(kind, now)
    policy = _policy(kind, rows[-1].context) if rows else {}
    rows = [row for row in rows if _policy(kind, row.context) == policy]
    days = sorted({row.target_date for row in rows})
    metrics: dict = {"samples": len(rows), "dates": len(days)}
    parameters: dict = {}
    approved = False
    if len(days) < MIN_TRAIN_DAYS + MIN_TEST_DAYS:
        metrics["reason"] = "Need at least 60 training dates and 20 later validation dates."
    else:
        boundary = days[-max(MIN_TEST_DAYS, len(days) // 4)]
        train = [row for row in rows if row.target_date < boundary]
        test = [row for row in rows if row.target_date >= boundary]
        # Purge outcomes not yet observable when the holdout begins (especially IPOs).
        first_test = min(row.issued_at for row in test)
        train = [row for row in train if row.observed_at < first_test]
        counts = Counter(row.actual_label for row in train)
        if len({row.target_date for row in train}) < MIN_TRAIN_DAYS:
            metrics["reason"] = "Insufficient training dates after point-in-time purging."
        elif len(counts) < MIN_CLASSES or min(counts.values()) < MIN_CLASS_SAMPLES:
            metrics["reason"] = "Need at least two classes with ten training examples each."
        else:
            scaler = StandardScaler()
            x_train = scaler.fit_transform([row.features for row in train])
            classifier = LogisticRegression(C=0.1, max_iter=1000, random_state=0)
            classifier.fit(x_train, [row.actual_label for row in train])
            if not isinstance(scaler.mean_, ndarray) or not isinstance(scaler.scale_, ndarray):
                raise ValueError("The fitted forecast scaler has no vector parameters.")
            guesses = classifier.predict(scaler.transform([row.features for row in test]))
            accuracy = sum(
                guess == row.actual_label for guess, row in zip(guesses, test, strict=True)
            ) / len(test)
            baseline = max(Counter(row.actual_label for row in test).values()) / len(test)
            rule = sum(row.rule_label == row.actual_label for row in test) / len(test)
            approved = accuracy >= max(baseline, rule) + PROMOTION_MARGIN
            metrics.update(
                accuracy=accuracy,
                baseline=baseline,
                rule_accuracy=rule,
                training_samples=len(train),
                validation_samples=len(test),
                validation_start=boundary.isoformat(),
                validation_end=days[-1].isoformat(),
                required_margin=PROMOTION_MARGIN,
                reason="Promoted." if approved else "Did not beat both baselines by 5 points.",
            )
            # Deploy the validated fit, not a different, unvalidated refit on the holdout.
            parameters = {
                "classes": classifier.classes_.tolist(),
                "coef": classifier.coef_.tolist(),
                "intercept": classifier.intercept_.tolist(),
                "mean": scaler.mean_.tolist(),
                "scale": scaler.scale_.tolist(),
                "policy": policy,
            }
    ForecastModel.objects.update_or_create(
        kind=kind,
        trained_at=now,
        defaults={
            "parameters": parameters,
            "metrics": metrics,
            "approved": approved,
        },
    )
    logger.info("Forecast model %s: %s", kind, metrics)
    return {**metrics, "approved": approved}
