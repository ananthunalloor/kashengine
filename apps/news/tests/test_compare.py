"""Tests for the model comparison."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.llm.client import LLMInvalidOutput, LLMUnavailable
from apps.news.compare import (
    EvalItem,
    ModelReport,
    evaluate_model,
    label_for,
    load_items,
)

from .fakes import FakeLLM


def answer(score: float) -> dict:
    return {"score": score, "relevance": 0.5, "reason": "x"}


def test_the_built_in_set_is_balanced_and_valid():
    items = load_items()

    assert len(items) == 24
    for label in ("positive", "neutral", "negative"):
        assert sum(item.label == label for item in items) == 8
    assert all(item.title for item in items)


def test_load_items_from_a_file_and_reject_a_bad_label(tmp_path):
    good = tmp_path / "good.csv"
    good.write_text('label,title,summary\nPositive,"Rates fall, banks gain",\n', encoding="utf-8")
    assert load_items(good) == [EvalItem("positive", "Rates fall, banks gain", "")]

    bad = tmp_path / "bad.csv"
    bad.write_text("label,title\nbullish,Something\n", encoding="utf-8")
    with pytest.raises(ValueError, match="positive, neutral, or negative"):
        load_items(bad)


def test_label_for():
    assert label_for(0.21) == "positive"
    assert label_for(0.2) == "neutral"
    assert label_for(0.0) == "neutral"
    assert label_for(-0.2) == "neutral"
    assert label_for(-0.21) == "negative"


ITEMS = [
    EvalItem("positive", "a"),
    EvalItem("neutral", "b"),
    EvalItem("negative", "c"),
    EvalItem("positive", "d"),
]


def test_evaluate_model_measures_accuracy_error_failures_and_time():
    llm = FakeLLM(
        answers=[answer(0.8), answer(0.1), answer(0.6), LLMInvalidOutput("bad")], model="m1"
    )

    report = evaluate_model(llm, ITEMS)

    assert report.model == "m1"
    assert report.scores == [0.8, 0.1, 0.6, None]
    assert report.failures == 1
    assert report.accuracy == pytest.approx(2 / 3)  # The third item is wrong.
    assert report.mean_abs_error == pytest.approx((0.2 + 0.1 + 1.6) / 3)
    assert report.seconds_per_item == 1.0


def test_evaluate_model_does_not_hide_a_down_server():
    with pytest.raises(LLMUnavailable):
        evaluate_model(FakeLLM(default=LLMUnavailable("down")), ITEMS)


def test_agreement_between_two_models():
    first = ModelReport("a", ITEMS, scores=[0.8, 0.0, -0.9, None])
    second = ModelReport("b", ITEMS, scores=[0.5, 0.9, -0.5, 0.7])

    # Items 1 and 3 have the same class. Item 2 differs. Item 4 has no score from the first.
    assert first.agreement_with(second) == pytest.approx(2 / 3)
    assert ModelReport("c", ITEMS, scores=[None] * 4).agreement_with(second) is None
    assert ModelReport("c", ITEMS, scores=[None] * 4).accuracy is None


@pytest.fixture
def fake_models(monkeypatch):
    from apps.news.management.commands import compare_models

    def factory(model=None):
        return FakeLLM(model=model, default=answer(0.9 if model == "big" else 0.0))

    monkeypatch.setattr(compare_models, "LLMClient", factory)


def test_compare_models_command_shows_one_row_for_each_model(fake_models, capsys):
    call_command("compare_models", "small", "big")

    out = capsys.readouterr().out
    assert "small" in out
    assert "big" in out
    assert "Accuracy" in out
    assert "Same class, small and big" in out
    # "small" always says 0.0: only the 8 neutral items are right. "big" says 0.9: the 8 positive.
    assert "33%" in out


def test_compare_models_command_verbose_and_single_model(fake_models, capsys):
    call_command("compare_models", "big", "--verbose")

    out = capsys.readouterr().out
    assert "Tip: give two models" in out
    assert "+0.90 pos" in out


def test_compare_models_command_turns_errors_into_command_errors(monkeypatch):
    from apps.news.management.commands import compare_models

    monkeypatch.setattr(
        compare_models, "LLMClient", lambda model=None: FakeLLM(default=LLMUnavailable("down"))
    )
    with pytest.raises(CommandError, match="down"):
        call_command("compare_models", "x")
    with pytest.raises(CommandError):
        call_command("compare_models", "x", "--file", "/no/such/file.csv")
