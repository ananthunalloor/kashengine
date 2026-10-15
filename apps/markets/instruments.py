"""The instruments that we download, and how much each cue counts in the prediction.

The instruments are in the database (model `Instrument`). An admin changes them on the Ops pages
(Ops > Instruments). See the model for what weight and scale mean.

This module reads the rows and gives plain, read-only `Instrument` values to the callers.
`quotes.py` uses `all_instruments` to know which symbols to download. `prediction.py` uses
`global_cues`, `total_cue_weight` to build the global score. `evaluation.py` uses `target_symbol`
to find the quotes of the index that we predict.
"""

from dataclasses import dataclass

from .models import Instrument as InstrumentRow


class NoTargetError(Exception):
    """No target index is set, so we cannot check a prediction.

    `target_symbol` raises this error when no `Instrument` row has the kind `target`.
    """


@dataclass(frozen=True)
class Instrument:
    """A read-only copy of one `Instrument` row, with its weight and scale.

    Attributes:
        symbol: The Yahoo Finance symbol, for example `^NSEI`.
        name: The display name.
        weight: How much a cue counts. The sign gives the direction. Not used for indexes.
        scale: The move in percent that counts as a full signal.
    """

    symbol: str
    name: str
    weight: float = 0.0
    scale: float = 1.0


def _convert(rows) -> list[Instrument]:
    """Convert database rows to a list of `Instrument` values, in the same order.

    Args:
        rows: An iterable of `Instrument` model rows.

    Returns:
        A new list with one read-only `Instrument` value for each row.
    """
    return [Instrument(row.symbol, row.name, row.weight, row.scale) for row in rows]


def all_instruments() -> list[Instrument]:
    """Return the enabled instruments that we download.

    The list has the rows of all kinds (target, index and cue) that have `enabled` set. The order
    is the order of the `id` of the rows.

    Returns:
        A list of `Instrument` values. It is empty when no row is enabled.

    Note:
        A target row that is not enabled is not in this list. The quotes of the target are then
        not downloaded, but `target_symbol` still returns its symbol.
    """
    return _convert(InstrumentRow.objects.filter(enabled=True))


def global_cues() -> list[Instrument]:
    """Return the enabled instruments of kind `cue`.

    Returns:
        A list of `Instrument` values, in the order of the `id` of the rows. It is empty when no
        cue is enabled.
    """
    return _convert(InstrumentRow.objects.filter(enabled=True, kind=InstrumentRow.Kind.CUE))


def target_symbol() -> str:
    """Return the Yahoo symbol of the index that we predict.

    The function reads the row of kind `target`. It does not check the `enabled` flag.

    Returns:
        The symbol of the target index, for example `^NSEI`.

    Raises:
        NoTargetError: When no row has the kind `target`.
    """
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
    """Return the sum of the absolute weights of the cues.

    The signs are dropped, so a cue with a weight of -0.5 adds 0.5. The prediction code uses the
    total to find how much of the wanted cue data is present.

    Args:
        cues: The cues to add up, for example the result of `global_cues`.

    Returns:
        The sum, rounded to 6 decimal places. It is 0.0 for an empty list.
    """
    return round(sum(abs(cue.weight) for cue in cues), 6)
