"""The instruments that we download, and how much each one counts in the prediction.

TARGET_SYMBOL is the index that we predict (Nifty 50). The global cues show what happened in
other markets before the Indian market opens.

Each global cue has:
- weight: how much it counts. The sign is the direction. A plus sign means "a rise is good for
  Indian stocks". A minus sign means "a rise is bad" (oil, the dollar, fear). The weights
  without signs add up to 1.
- scale: the move in percent that counts as a full signal. A move of this size gives 1.0.
  A bigger move is cut to 1.0, so one big move cannot decide alone.

THE WEIGHTS AND THE SCALES ARE OUR FIRST GUESS. They are not fitted to data. Change them only
when the accuracy numbers (python manage.py prediction_stats) give a reason.

The symbols are Yahoo Finance symbols. We could not test them on the live service when we wrote
this. A symbol that fails is logged and skipped. The prediction then uses the other cues.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str
    weight: float = 0.0
    scale: float = 1.0


NIFTY = Instrument("^NSEI", "Nifty 50")
SENSEX = Instrument("^BSESN", "Sensex")
TARGET_SYMBOL = NIFTY.symbol

INDEXES = (NIFTY, SENSEX)

GLOBAL_CUES = (
    Instrument("^GSPC", "S&P 500", weight=0.30, scale=2.0),
    Instrument("^IXIC", "Nasdaq", weight=0.15, scale=2.5),
    Instrument("^N225", "Nikkei 225", weight=0.10, scale=2.5),
    Instrument("^HSI", "Hang Seng", weight=0.10, scale=2.5),
    Instrument("BZ=F", "Brent crude", weight=-0.15, scale=3.0),
    Instrument("USDINR=X", "USD/INR", weight=-0.10, scale=0.6),
    Instrument("^INDIAVIX", "India VIX", weight=-0.10, scale=8.0),
)

ALL_INSTRUMENTS = INDEXES + GLOBAL_CUES
TOTAL_CUE_WEIGHT = round(sum(abs(cue.weight) for cue in GLOBAL_CUES), 6)
