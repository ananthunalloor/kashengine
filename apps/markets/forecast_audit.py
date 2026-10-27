"""Scheduled reviewer of stored forecast publications, independent of production."""

import logging
import math
from datetime import datetime

from django.db import transaction
from django.db.models import Q

from apps.companies.models import CompanyOutlook
from apps.ipos.models import Ipo

from .models import ForecastModel, ForecastSample, Prediction
from .trading import today_ist
from .watchdog import check_forecast, check_model, check_rule

logger = logging.getLogger(__name__)


def withhold_market_reports(target, reasons: list[str]) -> None:
    """Withdraw cached report copies too, including reports not yet delivered."""
    from apps.reports.builder import render_text  # noqa: PLC0415
    from apps.reports.models import Report  # noqa: PLC0415

    for report in Report.objects.filter(data__prediction__target_date=target.isoformat()):
        report.data["prediction"].update(
            direction="withheld",
            confidence=0.0,
            score=0.0,
            notes=["Withheld by the prediction watchdog.", *reasons],
        )
        report.prediction, report.confidence = "", None
        report.text = render_text(report.data)
        report.save(update_fields=["prediction", "confidence", "text", "data"])


def withhold_ipo_reports(ipo: Ipo, now: datetime) -> None:
    """Remove a withheld issue from current cached report recommendations."""
    from apps.reports.builder import render_text  # noqa: PLC0415
    from apps.reports.models import Report  # noqa: PLC0415

    def matches(item: dict) -> bool:
        """Recognize new report identities and pre-migration report snapshots."""
        return item.get("id") == ipo.pk or (
            "id" not in item
            and item.get("name") == ipo.name
            and item.get("open_date") == (ipo.open_date.isoformat() if ipo.open_date else None)
        )

    for report in Report.objects.filter(date__gte=today_ist(now)):
        groups = report.data.get("ipos", {})
        changed = False
        was_judged = False
        for key in ("open_now", "upcoming", "listing_today"):
            for item in groups.get(key, []):
                if matches(item):
                    was_judged |= key != "listing_today" and item.get("verdict") not in (
                        "unknown",
                        "",
                    )
                    item.update(verdict="unknown", score=None)
                    changed = True
        before = groups.get("likely_good", [])
        groups["likely_good"] = [item for item in before if not matches(item)]
        changed |= len(before) != len(groups["likely_good"])
        if not changed:
            continue
        if was_judged:
            groups["without_verdict"] = groups.get("without_verdict", 0) + 1
        groups["watchdog_notes"] = list(
            dict.fromkeys(
                [
                    *groups.get("watchdog_notes", []),
                    f"{ipo.name}: prediction withheld by the watchdog.",
                ]
            )
        )
        report.text = render_text(report.data)
        report.save(update_fields=["text", "data"])


def _publication(sample: ForecastSample):
    """Find the currently published result for this evidence."""
    if sample.kind == "market":
        return Prediction.objects.filter(target_date=sample.target_date).first()
    if sample.kind == "company":
        return CompanyOutlook.objects.filter(
            company_id=sample.entity, target_date=sample.target_date
        ).first()
    return Ipo.objects.filter(pk=sample.entity, listing_date=sample.target_date).first()


@transaction.atomic
def _withhold(publication: Prediction | CompanyOutlook | Ipo, audit: dict, now: datetime) -> None:
    """Withdraw a publication and its cached copies in the same transaction."""
    if isinstance(publication, Ipo):
        publication.verdict, publication.score = "unknown", None
        inputs = publication.score_inputs
        inputs["notes"] = inputs.get("notes", []) + audit["reasons"]
        inputs["learning"] = {**inputs.get("learning", {}), "watchdog": audit}
        publication.save(update_fields=["verdict", "score", "score_inputs"])
        withhold_ipo_reports(publication, now)
        return
    publication.direction, publication.score = "withheld", 0.0
    publication.inputs["learning"] = {**publication.inputs.get("learning", {}), "watchdog": audit}
    if isinstance(publication, Prediction):
        publication.confidence = 0.0
        publication.correct = None
        publication.inputs["notes"] = publication.inputs.get("notes", []) + audit["reasons"]
        withhold_market_reports(publication.target_date, audit["reasons"])
    publication.save()


def _withhold_legacy(now: datetime) -> int:
    """Do not certify active pre-watchdog forecasts retrospectively without provenance."""
    today = today_ist(now)
    queries = (
        Prediction.objects.filter(target_date__gte=today).exclude(inputs__has_key="learning"),
        CompanyOutlook.objects.filter(target_date__gte=today).exclude(inputs__has_key="learning"),
        Ipo.objects.filter(
            Q(listing_date__gte=today) | Q(listing_date__isnull=True),
            listing_gain_pct__isnull=True,
        )
        .exclude(verdict__in=["", "unknown"])
        .exclude(score_inputs__has_key="learning"),
    )
    count = 0
    for query in queries:
        for publication in query:
            audit = {
                "status": "blocked",
                "checked_at": now.isoformat(),
                "version": "watchdog-v1",
                "reasons": ["Legacy forecast has no watchdog-verified point-in-time evidence."],
            }
            _withhold(publication, audit, now)
            logger.warning(
                "Withheld unaudited legacy %s:%s", type(publication).__name__, publication.pk
            )
            count += 1
    return count


def audit_publications(now: datetime) -> dict:
    """Recalculate rules and compare published values to recorded model decisions."""
    legacy = _withhold_legacy(now)
    result = {"checked": legacy, "blocked": legacy}
    for sample in ForecastSample.objects.filter(
        target_date__gte=today_ist(now), audit__watchdog__status="passed"
    ):
        publication = _publication(sample)
        if publication is None:
            continue
        problems = check_rule(
            sample.kind,
            sample.features,
            sample.audit["rule_score"],
            sample.rule_label,
            sample.context,
        )
        score = publication.score
        label = publication.verdict if sample.kind == "ipo" else publication.direction
        if sample.audit["method"] == "logistic-v1":
            model = ForecastModel.objects.get(pk=sample.audit["model_id"])
            problems.extend(
                check_model(
                    model.parameters,
                    sample.features,
                    sample.predicted_label,
                    sample.audit["score"],
                    sample.audit["model_strength"],
                )
            )
        if (
            score is None
            or not math.isfinite(score)
            or not math.isclose(score, sample.audit["score"], abs_tol=0.00011)
            or label != sample.predicted_label
        ):
            problems.append("Published values disagree with the recorded forecast evidence.")
        if sample.kind == "market" and (
            not math.isfinite(publication.confidence)
            or not 0 <= publication.confidence <= 1
            or not math.isclose(publication.confidence, sample.audit["strength"], abs_tol=0.00001)
        ):
            problems.append("Published signal strength disagrees with the recorded evidence.")
        audit = check_forecast(
            sample.features,
            score if score is not None else math.nan,
            label,
            allowed=(sample.predicted_label,),
            now=sample.issued_at,
            deadline=sample.deadline,
            reasons=problems,
        )
        result["checked"] += 1
        if audit["status"] == "passed":
            continue
        result["blocked"] += 1
        audit["checked_at"] = now.isoformat()
        with transaction.atomic():
            sample.audit = {**sample.audit, "watchdog": audit}
            sample.save(update_fields=["audit"])
            _withhold(publication, audit, now)
        logger.error(
            "Watchdog withheld %s:%s for %s", sample.kind, sample.entity, sample.target_date
        )
    return result
