"""Compare LLM models on one fixed set of labelled headlines.

Use it to pick the model for production. Run the same items on the small model (dev) and on the
larger model (prod). Then compare the accuracy, the failures, and the time for each item.

The built-in set (data/sentiment_eval.csv) is small and made up. It uses invented company names.
It shows if a model is clearly bad. It cannot show which good model is the best. For a better
test, make your own CSV with real headlines. Use the columns label, title, summary. The label is
positive, neutral, or negative.
"""

import csv
from dataclasses import dataclass, field
from pathlib import Path

from apps.llm.client import LLMClient, LLMInvalidOutputError

from .sentiment import score_text

DEFAULT_SET = Path(__file__).resolve().parent / "data" / "sentiment_eval.csv"
LABEL_VALUE = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}
NEUTRAL_BAND = 0.2  # A score between -0.2 and 0.2 counts as neutral.


def label_for(score: float) -> str:
    """Return the class (positive, neutral, or negative) for a sentiment score."""
    if score > NEUTRAL_BAND:
        return "positive"
    if score < -NEUTRAL_BAND:
        return "negative"
    return "neutral"


@dataclass(frozen=True)
class EvalItem:
    """One labelled headline."""

    label: str
    title: str
    summary: str = ""


def load_items(path: Path | str | None = None) -> list[EvalItem]:
    """Read labelled headlines from a CSV file. Use the built-in set if no path is given.

    Raises:
        ValueError: A row has no title or a label that is not positive, neutral, or negative.
    """
    path = Path(path) if path else DEFAULT_SET
    items = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            label = (row.get("label") or "").strip().lower()
            title = (row.get("title") or "").strip()
            if label not in LABEL_VALUE or not title:
                msg = (
                    f"Bad row in {path}: {row}. Use the label positive, neutral, or negative, "
                    "and give a title."
                )
                raise ValueError(msg)
            items.append(EvalItem(label, title, (row.get("summary") or "").strip()))
    return items


@dataclass
class ModelReport:
    """Scores of one model on a set of items."""

    model: str
    items: list[EvalItem]
    scores: list[float | None] = field(default_factory=list)  # None: no valid answer.
    seconds: float = 0.0

    @property
    def failures(self) -> int:
        """Number of items with no valid answer."""
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
        """Mean time to score one item."""
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
    """Score all items with one model. LLMUnavailableError is not caught: the caller handles it."""
    report = ModelReport(model=llm.model, items=items)
    for item in items:
        try:
            report.scores.append(score_text(llm, item.title, item.summary).score)
        except LLMInvalidOutputError:
            report.scores.append(None)
        report.seconds += llm.last_seconds
    return report
