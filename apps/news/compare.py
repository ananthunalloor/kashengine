"""Compare LLM models on one fixed set of labelled headlines.

Use it to pick the model for prod: run the same items on the small model (dev) and on the larger
model (prod), then look at the accuracy, the failures, and the time for each item.

The built-in set (data/sentiment_eval.csv) is small and made up by us. It uses invented company
names. It shows if a model is clearly bad. It cannot show which good model is the best. For a
better test, make your own CSV with real headlines, with the columns label, title, summary
(label is positive, neutral, or negative).
"""

import csv
from dataclasses import dataclass, field
from pathlib import Path

from apps.llm.client import LLMClient, LLMInvalidOutput

from .sentiment import score_text

DEFAULT_SET = Path(__file__).resolve().parent / "data" / "sentiment_eval.csv"
LABEL_VALUE = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}
NEUTRAL_BAND = 0.2  # A score between -0.2 and 0.2 counts as neutral.


def label_for(score: float) -> str:
    if score > NEUTRAL_BAND:
        return "positive"
    if score < -NEUTRAL_BAND:
        return "negative"
    return "neutral"


@dataclass(frozen=True)
class EvalItem:
    label: str
    title: str
    summary: str = ""


def load_items(path: Path | str | None = None) -> list[EvalItem]:
    path = Path(path) if path else DEFAULT_SET
    items = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            label = (row.get("label") or "").strip().lower()
            title = (row.get("title") or "").strip()
            if label not in LABEL_VALUE or not title:
                raise ValueError(
                    f"Bad row in {path}: {row}. Use the label positive, neutral, or negative, "
                    "and give a title."
                )
            items.append(EvalItem(label, title, (row.get("summary") or "").strip()))
    return items


@dataclass
class ModelReport:
    model: str
    items: list[EvalItem]
    scores: list[float | None] = field(default_factory=list)  # None: no valid answer.
    seconds: float = 0.0

    @property
    def failures(self) -> int:
        return sum(score is None for score in self.scores)

    def _scored(self) -> list[tuple[EvalItem, float]]:
        return [(item, s) for item, s in zip(self.items, self.scores, strict=True) if s is not None]

    @property
    def accuracy(self) -> float | None:
        """Share of the scored items where the class (positive, neutral, negative) is right."""
        scored = self._scored()
        if not scored:
            return None
        return sum(label_for(s) == item.label for item, s in scored) / len(scored)

    @property
    def mean_abs_error(self) -> float | None:
        """Mean distance between the score and the label (+1, 0, or -1)."""
        scored = self._scored()
        if not scored:
            return None
        return sum(abs(s - LABEL_VALUE[item.label]) for item, s in scored) / len(scored)

    @property
    def seconds_per_item(self) -> float:
        return self.seconds / len(self.items) if self.items else 0.0

    def agreement_with(self, other: "ModelReport") -> float | None:
        """Share of the items where both models give the same class."""
        pairs = [
            (a, b)
            for a, b in zip(self.scores, other.scores, strict=True)
            if a is not None and b is not None
        ]
        if not pairs:
            return None
        return sum(label_for(a) == label_for(b) for a, b in pairs) / len(pairs)


def evaluate_model(llm: LLMClient, items: list[EvalItem]) -> ModelReport:
    """Score all items with one model. LLMUnavailable is not caught: the caller handles it."""
    report = ModelReport(model=llm.model, items=items)
    for item in items:
        try:
            report.scores.append(score_text(llm, item.title, item.summary).score)
        except LLMInvalidOutput:
            report.scores.append(None)
        report.seconds += llm.last_seconds
    return report
