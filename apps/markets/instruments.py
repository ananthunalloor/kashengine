"""The instruments that we download, and how much each cue counts in the prediction.

The instruments are in the database (model Instrument). An admin changes them on the Ops pages
(Ops > Instruments). See the model for what weight and scale mean.
"""

from dataclasses import dataclass

from .models import Instrument as InstrumentRow


class NoTargetError(Exception):
    """No target index is set, so we cannot make or check a prediction."""


@dataclass(frozen=True)
class Instrument:
    """A symbol that we download, with its weight and scale in the prediction."""

    symbol: str
    name: str
    weight: float = 0.0
    scale: float = 1.0


def _convert(rows) -> list[Instrument]:
    return [Instrument(row.symbol, row.name, row.weight, row.scale) for row in rows]


def all_instruments() -> list[Instrument]:
    """The enabled instruments that we download."""
    return _convert(InstrumentRow.objects.filter(enabled=True))


def global_cues() -> list[Instrument]:
    """The enabled global cues."""
    return _convert(InstrumentRow.objects.filter(enabled=True, kind=InstrumentRow.Kind.CUE))


def target_symbol() -> str:
    """The Yahoo symbol of the index that we predict."""
    symbol = (
        InstrumentRow.objects.filter(kind=InstrumentRow.Kind.TARGET)
        .values_list("symbol", flat=True)
        .first()
    )
    if symbol is None:
        msg = "No target index is set. Add one on the Ops pages (Ops > Instruments)."
        raise NoTargetError(msg)
    return symbol


def total_cue_weight(cues: list[Instrument]) -> float:
    """The sum of the weights of the cues, without signs."""
    return round(sum(abs(cue.weight) for cue in cues), 6)
