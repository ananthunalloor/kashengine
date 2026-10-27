"""Chronological ML gates, cold starts, immutable deadlines and watchdog publication tests."""

import math
from datetime import timedelta
from decimal import Decimal

import pytest

from apps.companies.models import Company, CompanyCandle, CompanyOutlook
from apps.companies.outlook import save_outlook
from apps.ipos.models import Ipo
from apps.ipos.scoring import score_ipos
from apps.markets import tasks
from apps.markets.evaluation import accuracy_stats, evaluate_pending
from apps.markets.forecast_audit import audit_publications
from apps.markets.forecast_outcomes import collect_outcomes
from apps.markets.learning import forecast, infer, train_model
from apps.markets.models import ForecastModel, ForecastSample, Prediction
from apps.markets.prediction import make_prediction, news_signal, read_cues
from apps.markets.trading import session_open
from apps.markets.watchdog import check_forecast, check_model, check_rule
from apps.reports.builder import build_report

from .helpers import MON, NEXT_MON, PREV_FRI, article, ist, quote

pytestmark = pytest.mark.django_db

COMPANY_CONTEXT = {
    "band": 0.25,
    "instrument_key": "NSE_EQ|test",
    "reference_close": 100.0,
    "threshold": 0.15,
}


def company_forecast(now=None, **changes):
    kwargs = {
        "kind": "company",
        "entity": "1",
        "target": MON,
        "features": [0.1, 0.5, 1.0],
        "rule_label": "up",
        "rule_score": 0.22,
        "now": now or ist(MON, 8),
        "deadline": session_open(MON),
        "context": COMPANY_CONTEXT,
        "reasons": [],
    }
    kwargs.update(changes)
    return forecast(**kwargs)


def seed_training(*, learnable=True, leaked=False, count=80):
    days = []
    day = MON
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    for index, day in enumerate(days):
        sign = 1 if index % 2 else -1
        ForecastSample.objects.create(
            kind="company",
            entity="1",
            target_date=day,
            issued_at=ist(day, 8),
            deadline=session_open(day),
            features=[0.1 * sign if learnable else 0.0, 0, 0],
            context=COMPANY_CONTEXT,
            rule_label="flat",
            predicted_label="flat",
            audit={"watchdog": {"status": "passed"}},
            actual_label="up" if sign > 0 else "down",
            actual_change=sign,
            observed_at=ist(days[-1] + timedelta(days=1), 17) if leaked else ist(day, 17),
        )
    return ist(days[-1] + timedelta(days=2), 8)


def test_cold_start_is_explicitly_experimental_but_not_falsely_blocked():
    label, score, metadata = company_forecast()
    assert (label, score) == ("up", 0.22)
    assert metadata["experimental"] is True
    assert metadata["watchdog"]["status"] == "passed"
    assert ForecastSample.objects.get().features == [0.1, 0.5, 1.0]


def test_watchdog_recalculates_rules_and_blocks_mismatches():
    _, _, metadata = company_forecast(rule_score=0.8)
    assert metadata["watchdog"]["status"] == "blocked"
    assert "disagrees" in metadata["watchdog"]["reasons"][0]
    assert ForecastSample.objects.get().features == []


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, 1.1])
def test_watchdog_rejects_nonfinite_or_out_of_range_values(value):
    result = check_forecast(
        [value],
        value,
        "up",
        allowed=("up",),
        now=ist(MON, 8),
        deadline=session_open(MON),
        reasons=[],
    )
    assert result["status"] == "blocked"


def test_snapshots_refresh_before_open_and_freeze_at_deadline():
    company_forecast()
    company_forecast(now=ist(MON, 9), features=[0.2, 0, 0], rule_score=0.2)
    sample = ForecastSample.objects.get()
    assert sample.features == [0.2, 0, 0]
    _, _, late = company_forecast(now=ist(MON, 10))
    assert late["watchdog"]["status"] == "blocked"
    sample.refresh_from_db()
    assert sample.issued_at == ist(MON, 9)
    assert sample.features == [0.2, 0, 0]


def test_real_model_trains_and_beats_both_baselines_on_later_dates():
    now = seed_training()
    metrics = train_model("company", now)
    assert metrics["approved"] is True
    assert metrics["training_samples"] == 60
    assert metrics["validation_samples"] == 20
    assert metrics["accuracy"] == 1
    assert metrics["baseline"] == 0.5
    assert metrics["rule_accuracy"] == 0
    model = ForecastModel.objects.get()
    assert infer(model.parameters, [0.1, 0, 0])[0] == "up"
    assert infer(model.parameters, [-0.1, 0, 0])[0] == "down"
    _, _, metadata = company_forecast(
        now=now,
        target=now.date(),
        deadline=session_open(now.date()),
    )
    assert metadata["method"] == "logistic-v1"
    assert metadata["experimental"] is False


@pytest.mark.parametrize("kind", ["market", "ipo"])
def test_market_and_ipo_families_train_separate_real_classifiers(kind):
    now = seed_training()
    for row in ForecastSample.objects.all():
        sign = 1 if row.actual_label == "up" else -1
        row.kind = kind
        if kind == "market":
            row.features = [0.1 * sign, 0, 1, 0.5]
            row.context = {"symbol": "^NSEI", "band": 0.25}
        else:
            row.features = [0.1 * sign, 0, 0, 1, 0, 0]
            row.context = {"good_gain": 10}
            row.rule_label = "mixed" if sign > 0 else "weak"
            row.actual_label = "good" if sign > 0 else "weak"
        row.save()
    metrics = train_model(kind, now)
    assert metrics["approved"] is True
    model = ForecastModel.objects.get(kind=kind)
    features = [0.1, 0, 1, 0.5] if kind == "market" else [0.1, 0, 0, 1, 0, 0]
    label, score, strength = infer(model.parameters, features)
    assert label == ("up" if kind == "market" else "good")
    assert check_model(model.parameters, features, label, score, strength) == []
    assert check_model(model.parameters, features, label, -score, strength)


def test_retraining_keeps_the_older_model_for_independent_replay():
    now = seed_training()
    train_model("company", now)
    first = ForecastModel.objects.get()
    train_model("company", now + timedelta(hours=1))
    assert ForecastModel.objects.count() == 2
    assert ForecastModel.objects.first().pk != first.pk
    first.refresh_from_db()
    assert infer(first.parameters, [0.1, 0, 0])[0] == "up"


def test_insufficient_dates_do_not_promote_a_model():
    now = seed_training(count=79)
    assert train_model("company", now)["approved"] is False


def test_model_that_cannot_beat_baseline_is_not_promoted():
    now = seed_training(learnable=False)
    metrics = train_model("company", now)
    assert metrics["approved"] is False
    assert metrics["accuracy"] <= metrics["baseline"]


@pytest.mark.parametrize(("flipped", "approved"), [(8, True), (9, True), (10, False)])
def test_promotion_requires_at_least_five_percentage_points(flipped, approved):
    now = seed_training()
    test = list(ForecastSample.objects.order_by("-target_date")[:20])
    for row in test[:flipped]:
        row.features[0] *= -1
        row.save(update_fields=["features"])
    metrics = train_model("company", now)
    assert metrics["baseline"] == 0.5
    assert metrics["accuracy"] == (20 - flipped) / 20
    assert metrics["approved"] is approved


def test_holdout_purges_training_outcomes_unavailable_at_validation_time():
    now = seed_training(leaked=True)
    metrics = train_model("company", now)
    assert metrics["approved"] is False
    assert "purging" in metrics["reason"]


def test_stale_model_or_incompatible_outcome_policy_is_not_used():
    now = seed_training()
    train_model("company", now)
    model = ForecastModel.objects.get()
    model.trained_at = ist(MON, 7)
    model.save()
    _, _, metadata = company_forecast(now=now, deadline=now + timedelta(hours=1))
    assert metadata["experimental"] is True
    model.trained_at = now
    model.save()
    _, _, metadata = company_forecast(
        now=now,
        deadline=now + timedelta(hours=1),
        context={**COMPANY_CONTEXT, "band": 0.5},
    )
    assert metadata["experimental"] is True


def test_future_news_cannot_leak_into_an_earlier_prediction():
    article(1, 1, 1, published_at=ist(MON, 9))
    article(2, -1, 1, published_at=ist(MON, 7))
    signal = news_signal(ist(PREV_FRI, 16), ist(MON, 8))
    assert signal.articles == 1
    assert signal.score == -1


def test_same_session_close_is_not_a_premarket_cue():
    quote("^GSPC", MON, 5)
    assert read_cues(MON) == []


def test_a_quote_received_later_is_not_available_to_an_earlier_forecast():
    quote("^GSPC", PREV_FRI, 1, saved_at=ist(MON, 9))
    assert read_cues(MON, now=ist(MON, 8)) == []


def test_empty_market_prediction_is_withheld_and_excluded_from_accuracy():
    prediction, _ = make_prediction(MON, now=ist(MON, 8))
    assert prediction.direction == "withheld"
    assert evaluate_pending(ist(MON, 17))["waiting"] == 0
    assert accuracy_stats()["pending"] == 0
    report, _ = build_report(MON, now=ist(MON, 8))
    assert report.prediction == ""
    assert report.confidence is None
    assert "Prediction withheld" in report.text
    assert "FLAT:" not in report.text


def test_force_cannot_rewrite_a_prediction_after_session_opens():
    quote("^GSPC", PREV_FRI, 1)
    first, _ = make_prediction(MON, now=ist(MON, 8))
    second, changed = make_prediction(MON, now=ist(MON, 10), force=True)
    assert changed is False
    assert second.inputs == first.inputs


def test_company_outcome_waits_for_a_final_candle():
    company = Company.objects.create(
        name="Test", symbol="TEST", upstox_instrument_key="NSE_EQ|test"
    )
    company_forecast(entity=str(company.pk))
    candle = CompanyCandle.objects.create(
        company=company,
        instrument_key="NSE_EQ|test",
        day=MON,
        open=100,
        high=102,
        low=99,
        close=101,
        volume=10,
    )
    CompanyCandle.objects.filter(pk=candle.pk).update(updated_at=ist(MON, 12))
    assert collect_outcomes(ist(MON, 17)) == {"evaluated": 0, "waiting": 1}
    CompanyCandle.objects.filter(pk=candle.pk).update(updated_at=ist(MON, 17))
    assert collect_outcomes(ist(MON, 17))["evaluated"] == 1
    sample = ForecastSample.objects.get()
    assert sample.actual_label == "up"
    assert sample.actual_change == pytest.approx(1)
    assert collect_outcomes(ist(MON, 18))["evaluated"] == 0


def test_company_with_inconsistent_ohlcv_is_withheld(monkeypatch):
    monkeypatch.setattr("apps.companies.outlook.latest_completed_day", lambda: PREV_FRI)
    monkeypatch.setattr("apps.companies.outlook.timezone.now", lambda: ist(MON, 8))
    company = Company.objects.create(name="Bad candle", symbol="BAD", upstox_instrument_key="key")
    for index in range(21):
        CompanyCandle.objects.create(
            company=company,
            instrument_key="key",
            day=PREV_FRI - timedelta(days=index),
            open=100,
            high=90,
            low=80,
            close=100,
            volume=10,
        )
    outlook = save_outlook(company)
    assert outlook.direction == "withheld"
    assert outlook.inputs["learning"]["watchdog"]["status"] == "blocked"


def test_ipo_without_a_listing_date_is_blocked():
    ipo = Ipo.objects.create(name="Unknown date", gmp=20, price_band_high=100)
    score_ipos()
    ipo.refresh_from_db()
    assert ipo.verdict == "unknown"
    assert ipo.score is None
    assert "No listing date" in " ".join(ipo.score_inputs["notes"])


def test_ipo_outcomes_use_actual_listing_price_not_the_gmp():
    ipo = Ipo.objects.create(
        name="Listing test",
        gmp=20,
        price_band_high=100,
        listing_date=NEXT_MON,
        gmp_updated_at=ist(MON, 8),
    )
    score_ipos(ist(MON, 8))
    ipo.listing_price = Decimal("105")
    ipo.save()
    assert collect_outcomes(ist(NEXT_MON, 17))["evaluated"] == 1
    assert ForecastSample.objects.get().actual_label == "weak"


def test_listing_day_refresh_cannot_erase_the_frozen_ipo_forecast():
    ipo = Ipo.objects.create(
        name="Frozen listing",
        gmp=20,
        price_band_high=100,
        listing_date=NEXT_MON,
        gmp_updated_at=ist(MON, 8),
    )
    score_ipos(ist(MON, 8))
    ipo.refresh_from_db()
    before = ipo.score_inputs
    score_ipos(ist(NEXT_MON, 12))
    ipo.refresh_from_db()
    assert ipo.verdict == "good"
    assert ipo.score_inputs == before


def test_ipo_watchdog_removes_cached_recommendations():
    ipo = Ipo.objects.create(
        name="Cached IPO",
        gmp=20,
        price_band_high=100,
        listing_date=NEXT_MON,
        open_date=MON,
        close_date=MON + timedelta(days=2),
        gmp_updated_at=ist(MON, 8),
    )
    score_ipos(ist(MON, 8))
    report, _ = build_report(MON, now=ist(MON, 8))
    assert report.data["ipos"]["likely_good"]
    Ipo.objects.filter(pk=ipo.pk).update(score=-0.9)
    assert audit_publications(ist(MON, 9))["blocked"] == 1
    report.refresh_from_db()
    assert report.data["ipos"]["likely_good"] == []
    assert report.data["ipos"]["open_now"][0]["verdict"] == "unknown"
    assert "Cached IPO: prediction withheld" in report.text


def test_separate_watchdog_withholds_tampered_company_values():
    company = Company.objects.create(name="Test", symbol="TEST")
    _, score, metadata = company_forecast(entity=str(company.pk))
    publication = CompanyOutlook.objects.create(
        company=company,
        target_date=MON,
        direction="up",
        score=score,
        momentum_score=0.1,
        news_score=0.5,
        inputs={"learning": metadata},
    )
    assert audit_publications(ist(MON, 8)) == {"checked": 1, "blocked": 0}
    publication.score = 0.9
    publication.save()
    assert audit_publications(ist(MON, 9))["blocked"] == 1
    publication.refresh_from_db()
    assert publication.direction == "withheld"
    assert publication.inputs["learning"]["watchdog"]["status"] == "blocked"


def test_watchdog_withholds_active_legacy_forecasts_without_inventing_training_evidence():
    company = Company.objects.create(name="Legacy", symbol="OLD")
    publication = CompanyOutlook.objects.create(
        company=company,
        target_date=MON,
        direction="up",
        score=0.4,
        momentum_score=0.4,
        news_score=None,
        inputs={},
    )
    assert audit_publications(ist(MON, 8)) == {"checked": 1, "blocked": 1}
    publication.refresh_from_db()
    assert publication.direction == "withheld"
    assert ForecastSample.objects.count() == 0
    assert audit_publications(ist(MON, 9)) == {"checked": 0, "blocked": 0}


def test_market_watchdog_withdraws_cached_report_too():
    quote("^GSPC", PREV_FRI, 1)
    make_prediction(MON, now=ist(MON, 8))
    report, _ = build_report(MON, now=ist(MON, 8))
    Prediction.objects.filter(target_date=MON).update(score=-0.9)
    assert audit_publications(ist(MON, 9))["blocked"] == 1
    report.refresh_from_db()
    assert report.prediction == ""
    assert "Prediction withheld" in report.text


def test_automation_runs_all_families_without_network_calls(monkeypatch):
    monkeypatch.setattr(tasks.timezone, "now", lambda: ist(MON, 8))
    result = tasks.refresh_forecasts()
    assert result["market"] == "withheld"
    assert result["companies"] == 0
    assert result["ipos"] == {"scored": 0, "unknown": 0}


def test_ipo_watchdog_independently_verifies_weighted_inputs():
    features = [0.6, 1, -0.5, 1, 1, 1 / 3]
    score = (0.45 * 0.6 + 0.4 - 0.15 * 0.5 / 3) / (0.45 + 0.4 + 0.15 / 3)
    context = {"good": 0.3, "weak": 0.1}
    assert check_rule("ipo", features, round(score, 4), "good", context) == []
    assert check_rule("ipo", features, 0.1, "weak", context)
