"""Independent, deterministic publication checks; these cannot certify future returns."""

import logging
import math
from datetime import datetime

logger = logging.getLogger(__name__)


def check_model(
    parameters: dict, features: list[float], label: str, score: float, strength: float
) -> list[str]:
    """Replay the classifier independently with vector operations, not the producer's infer."""
    import numpy as np  # noqa: PLC0415

    means = np.asarray(parameters["mean"], dtype=float)
    scales = np.asarray(parameters["scale"], dtype=float)
    weights = np.asarray(parameters["coef"], dtype=float)
    biases = np.asarray(parameters["intercept"], dtype=float)
    classes = parameters["classes"]
    if (
        means.shape != (len(features),)
        or scales.shape != means.shape
        or biases.ndim != 1
        or weights.shape != (len(biases), len(features))
        or not all(np.isfinite(values).all() for values in (means, scales, weights, biases))
        or np.any(scales <= 0)
    ):
        return ["Invalid classifier coefficients or scaling parameters."]
    logits = weights @ ((np.asarray(features) - means) / scales) + biases
    if len(logits) == 1:
        positive = float(1 / (1 + np.exp(-np.clip(logits[0], -700, 700))))
        probabilities = np.asarray([1 - positive, positive])
    else:
        probabilities = np.exp(logits - logits.max())
        probabilities /= probabilities.sum()
    if len(classes) != len(probabilities):
        return ["Classifier labels and coefficient dimensions disagree."]
    prediction = str(classes[int(probabilities.argmax())])
    signs = {"up": 1, "down": -1, "flat": 0, "good": 1, "weak": -1}
    expected_score = sum(
        signs[direction] * float(probability)
        for direction, probability in zip(classes, probabilities, strict=True)
    )
    if (
        label != prediction
        or not math.isclose(score, expected_score, abs_tol=1e-10)
        or not math.isclose(strength, float(probabilities.max()), abs_tol=1e-10)
    ):
        return ["Independent watchdog classifier calculation disagrees with the model output."]
    return []


def check_rule(
    kind: str, features: list[float], score: float, label: str, context: dict
) -> list[str]:
    """Recalculate the rule independently of the prediction producer."""
    if not all(math.isfinite(value) for value in features):
        return ["Non-finite source evidence."]
    if kind == "market":
        news, global_score, fraction, coverage = features
        news_weight = context["news_weight"] * fraction
        global_weight = coverage - news_weight
        expected = (
            (news * news_weight + global_score * global_weight) / coverage if coverage > 0 else 0
        )
        threshold = context["threshold"]
        expected_label = (
            "up" if expected >= threshold else "down" if expected <= -threshold else "flat"
        )
    elif kind == "company":
        momentum, news, has_news = features
        expected = round(0.7 * momentum + 0.3 * news if has_news else momentum, 12)
        threshold = context["threshold"]
        expected_label = (
            "up" if expected > threshold else "down" if expected < -threshold else "flat"
        )
    else:
        weights = [0.45 * features[3], 0.40 * features[4], 0.15 * features[5]]
        used = sum(weights)
        expected = sum(value * weight for value, weight in zip(features[:3], weights, strict=True))
        expected = round(expected / used if used else 0, 4)
        expected_label = (
            "unknown"
            if not any(features[3:5])
            else "good"
            if expected >= context["good"]
            else "weak"
            if expected < context["weak"]
            else "mixed"
        )
    if not math.isclose(score, expected, abs_tol=0.00011) or label != expected_label:
        return ["Independent watchdog calculation disagrees with the rule output."]
    return []


def check_forecast(
    features: list[float],
    score: float,
    label: str,
    *,
    allowed: tuple[str, ...],
    now: datetime,
    deadline: datetime,
    reasons: list[str],
) -> dict:
    """Reject missing, non-finite, out-of-range or late evidence before publication."""
    problems = list(reasons)
    if not features or not all(math.isfinite(value) and -1 <= value <= 1 for value in features):
        problems.append("Inputs must be finite normalized values between -1 and 1.")
    if not math.isfinite(score) or not -1 <= score <= 1:
        problems.append("The calculated score is invalid.")
    if label not in allowed:
        problems.append("No usable prediction label.")
    if now >= deadline:
        problems.append("The forecast deadline has passed; late predictions are withheld.")
    result = {
        "status": "blocked" if problems else "passed",
        "checked_at": now.isoformat(),
        "reasons": problems,
        "version": "watchdog-v1",
    }
    if problems:
        logger.warning("Forecast withheld: %s", "; ".join(problems))
    return result
