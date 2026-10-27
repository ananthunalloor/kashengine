"""Models for the markets app: calendar exceptions, quotes, predictions and instruments.

`IndexQuote` holds one daily close for each symbol. `quotes.py` writes it. `Prediction` holds the
prediction for one trading day and, later, the real result. `prediction.py` creates it and
`evaluation.py` fills in the result. `Instrument` is the list of symbols to download, with the
weight and scale of each global cue. `MarketInstrument` is the provider-refreshed NSE/BSE catalog.
Admins edit `Instrument` on the Ops pages. `TradingCalendarDay` stores staff-maintained NSE
holidays and special-session hours.
"""

from typing import ClassVar

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class TradingCalendarDay(models.Model):
    """A staff-maintained exception to the regular NSE cash/equity session."""

    class Kind(models.TextChoices):
        """Supported exchange calendar exceptions."""

        HOLIDAY = "holiday", "Holiday"
        SPECIAL = "special", "Special trading session"

    day = models.DateField(unique=True)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    reason = models.CharField(max_length=250, help_text="Exchange-announced reason for this day.")
    opens_at = models.TimeField(null=True, blank=True, help_text="Special session start, in IST.")
    closes_at = models.TimeField(null=True, blank=True, help_text="Special session end, in IST.")
    source_url = models.URLField(blank=True, help_text="Optional official exchange circular.")

    class Meta:
        ordering: ClassVar[list[str]] = ["day"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=(
                    models.Q(kind="holiday", opens_at__isnull=True, closes_at__isnull=True)
                    | models.Q(
                        kind="special",
                        opens_at__isnull=False,
                        closes_at__isnull=False,
                        closes_at__gt=models.F("opens_at"),
                    )
                ),
                name="valid_trading_calendar_session",
            ),
            models.CheckConstraint(
                condition=~models.Q(reason=""), name="trading_calendar_reason_required"
            ),
        ]

    def __str__(self) -> str:
        """Return the day and the reason, for the admin and for logs."""
        return f"{self.day}: {self.reason}"

    def clean(self) -> None:
        """Reject a missing reason and wrong session hours.

        The method also removes spaces around the reason.

        Raises:
            ValidationError: If the reason is empty, if a holiday has session hours, or if a
                special session has no start, no end, or an end that is not after the start.
        """
        super().clean()
        self.reason = self.reason.strip()
        if not self.reason:
            raise ValidationError({"reason": "Enter the exchange-announced reason."})
        if self.kind == self.Kind.HOLIDAY:
            if self.opens_at is not None or self.closes_at is not None:
                raise ValidationError("Holidays cannot have session hours.")
        elif self.kind == self.Kind.SPECIAL and (
            self.opens_at is None or self.closes_at is None or self.closes_at <= self.opens_at
        ):
            raise ValidationError("Special sessions need a start and a later end time in IST.")


class MarketInstrument(models.Model):
    """One active NSE or BSE instrument from the Upstox daily instrument master."""

    instrument_key = models.CharField(max_length=100, unique=True)
    exchange = models.CharField(max_length=3)
    segment = models.CharField(max_length=20)
    trading_symbol = models.CharField(max_length=100)
    name = models.CharField(max_length=200)
    instrument_type = models.CharField(max_length=30)
    isin = models.CharField(max_length=12, blank=True)
    underlying_symbol = models.CharField(max_length=100, blank=True)
    expiry = models.DateField(null=True, blank=True)
    strike_price = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    lot_size = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    refreshed_at = models.DateTimeField(auto_now=True)
    company = models.ForeignKey(
        "companies.Company",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="market_instruments",
    )

    class Meta:
        ordering: ClassVar[list[str]] = ["exchange", "trading_symbol", "expiry", "pk"]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["exchange", "segment", "instrument_type"]),
            models.Index(fields=["exchange", "trading_symbol"]),
            models.Index(fields=["expiry"]),
        ]

    def __str__(self):
        """Return the exchange and trading symbol."""
        return f"{self.exchange}:{self.trading_symbol}"


class IndexConstituent(models.Model):
    """A company membership in an official Nifty index constituent file."""

    index_code = models.CharField(max_length=30)
    symbol = models.CharField(max_length=50)
    isin = models.CharField(max_length=12)
    company = models.ForeignKey(
        "companies.Company",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="index_memberships",
    )
    refreshed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["index_code", "symbol"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["index_code", "symbol"], name="unique_index_symbol"),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["index_code", "company"]),
        ]

    def __str__(self):
        """Return the index and its company symbol."""
        return f"{self.index_code}: {self.symbol}"


class IndexQuote(models.Model):
    """The close of one day for one symbol (an index or a global cue), from Yahoo Finance.

    There is at most one row for each (symbol, day) pair. The database enforces this with the
    constraint `unique_quote_symbol_day`. `quotes.save_bars` writes the rows with an upsert, so a
    later download replaces the close and the change of an existing row.

    `updated_at` has a rule for readers. The evaluation code treats a row as final only when
    `updated_at` is later than the close of the market for that day.
    """

    symbol = models.CharField(
        max_length=20, help_text="The Yahoo Finance symbol, for example ^NSEI."
    )
    day = models.DateField(help_text="The trading day. This is the local date of the exchange.")
    close = models.FloatField()
    change_pct = models.FloatField(
        null=True,
        blank=True,
        help_text="Change from the close of the day before, in percent.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When we last saved this row. A row that is older than the close of the "
        "market can hold a price from the middle of the session.",
    )

    class Meta:
        ordering: ClassVar[list[str]] = ["symbol", "-day"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["symbol", "day"], name="unique_quote_symbol_day"),
        ]

    def __str__(self):
        """Return the symbol, the day and the close, for example `^NSEI 2026-01-05 22000`."""
        return f"{self.symbol} {self.day} {self.close:g}"


class Prediction(models.Model):
    """The prediction for one trading day (Nifty 50), and later the real result.

    There is one row for each target day (`target_date` is unique). `prediction.make_prediction`
    creates the row with the direction, the confidence and the numbers behind them. After the
    market closes, `evaluation.evaluate_pending` fills in the real result fields
    (`actual_change_pct`, `actual_direction`, `correct`, `evaluated_at`).

    Result states:
    - Not evaluated: `evaluated_at` is empty.
    - Evaluated with a result: `correct` is True or False.
    - Void: `evaluated_at` is set and `correct` is empty. The market had no session that day.
    """

    class Direction(models.TextChoices):
        """The three possible directions of a day: up, down or flat."""

        UP = "up", "Up"
        DOWN = "down", "Down"
        FLAT = "flat", "Flat"

    target_date = models.DateField(unique=True, help_text="The trading day that we predict.")
    direction = models.CharField(max_length=10, choices=Direction.choices)
    confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="How strong the signal is, from 0 to 1. It is NOT a measured probability. "
        "Compare it with the accuracy numbers (python manage.py prediction_stats).",
    )
    score = models.FloatField(help_text="From -1 (down) to 1 (up).")
    news_score = models.FloatField(null=True, blank=True, help_text="Part of the score from news.")
    global_score = models.FloatField(
        null=True, blank=True, help_text="Part of the score from global markets."
    )
    news_articles = models.PositiveIntegerField(default=0, help_text="Articles in the news score.")
    inputs = models.JSONField(
        default=dict, blank=True, help_text="All the numbers that gave this prediction."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # The real result. We fill it in after the market closes.
    actual_change_pct = models.FloatField(null=True, blank=True)
    actual_direction = models.CharField(max_length=10, choices=Direction.choices, blank=True)
    correct = models.BooleanField(
        null=True,
        blank=True,
        help_text="Empty means no result yet, or no trading session on that day.",
    )
    evaluated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["-target_date"]

    def __str__(self):
        """Return the target date, the direction and the confidence."""
        return f"{self.target_date} {self.direction} ({self.confidence:.2f})"


class Instrument(models.Model):
    """A symbol that we download, with its weight and scale in the prediction.

    `instruments.py` reads the rows and converts them to plain `Instrument` values. A database
    constraint (`one_target_instrument`) allows at most one row of kind `target`.

    Kinds:
    - target: the index that we predict (Nifty 50). There is exactly one.
    - index: another index that we download and show.
    - cue: a global cue. It counts in the prediction with its weight.

    The weight is how much a cue counts. The sign is the direction: a plus sign means "a rise is
    good for Indian stocks", a minus sign means "a rise is bad" (oil, the dollar, fear). The scale
    is the move in percent that counts as a full signal. A bigger move is cut to 1.0.
    The numbers are a first guess. Change them only when the accuracy numbers give a reason.
    The symbols are Yahoo Finance symbols. A symbol that fails is logged and skipped.
    """

    class Kind(models.TextChoices):
        """The role of an instrument: target index, other index or global cue."""

        TARGET = "target", "Target index"
        INDEX = "index", "Index"
        CUE = "cue", "Global cue"

    symbol = models.CharField(max_length=20, unique=True, help_text="The Yahoo Finance symbol.")
    name = models.CharField(max_length=60)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.CUE)
    weight = models.FloatField(
        default=0.0, help_text="For a cue: from -1 to 1. Not used for others."
    )
    scale = models.FloatField(
        default=1.0, help_text="For a cue: the move in % that is a full signal."
    )
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["id"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["kind"], condition=models.Q(kind="target"), name="one_target_instrument"
            ),
        ]

    def __str__(self) -> str:
        """Return the name and the symbol, for example `Nifty 50 (^NSEI)`."""
        return f"{self.name} ({self.symbol})"


class LiveSnapshot(models.Model):
    """The newest normalized Upstox stream payload of one instrument or of the market status.

    The stream worker upserts these rows in bulk (no model signals, so no SSE invalidation storm).
    The WebSocket consumer reads them to send a first snapshot to a new browser subscriber.
    """

    class Kind(models.TextChoices):
        """What the payload describes."""

        EQUITY = "equity", "Company"
        INDEX = "index", "Index"
        STATUS = "status", "Market status"

    key = models.CharField(max_length=100, unique=True)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    company = models.ForeignKey(
        "companies.Company", null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    payload = models.JSONField(default=dict)
    updated_at = models.DateTimeField()

    class Meta:
        ordering: ClassVar[list[str]] = ["key"]

    def __str__(self) -> str:
        """Return the key and the time of the last update."""
        return f"{self.key} @ {self.updated_at}"
