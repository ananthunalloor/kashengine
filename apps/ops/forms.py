"""Forms of the settings pages. The settings form is built from the registry."""

from typing import ClassVar, cast

from django import forms

from apps.access.models import Subscription
from apps.markets.models import Instrument
from apps.news.models import NewsFeed
from apps.siteconfig import registry
from apps.siteconfig.registry import Spec

from . import schedule

INPUT = (
    "w-full rounded-md border border-rule bg-card px-3 py-2 text-sm text-ink "
    "placeholder:text-muted focus:border-accent focus:outline-none"
)
CHECKBOX = "h-4 w-4 rounded border-rule"
RESET_PREFIX = "reset__"
LIST_ROWS = 4


def _field(spec: Spec) -> forms.Field:
    """One form field for a setting."""
    if spec.kind == registry.BOOL:
        return forms.BooleanField(
            required=False, label=spec.label, widget=forms.CheckboxInput(attrs={"class": CHECKBOX})
        )
    if spec.kind in {registry.LIST, registry.URLS}:
        return forms.CharField(
            required=False,
            label=spec.label,
            widget=forms.Textarea(attrs={"class": INPUT, "rows": LIST_ROWS, "spellcheck": "false"}),
        )
    if spec.kind == registry.SECRET:
        return forms.CharField(
            required=False,
            label=spec.label,
            widget=forms.PasswordInput(
                attrs={"class": INPUT, "autocomplete": "off", "placeholder": "Enter a new value"},
                render_value=False,
            ),
        )
    attrs = {"class": INPUT, "spellcheck": "false", "autocomplete": "off"}
    if spec.kind in {registry.INT, registry.FLOAT}:
        attrs["inputmode"] = "decimal"
    return forms.CharField(required=False, label=spec.label, widget=forms.TextInput(attrs=attrs))


class SettingsForm(forms.Form):
    """The settings of one group. Build it with `settings_form(group)`."""

    specs: ClassVar[list[Spec]] = []

    def clean(self) -> dict:
        """Check each value with the rules of the registry."""
        cleaned = super().clean() or {}
        for spec in self.specs:
            if cleaned.get(RESET_PREFIX + spec.key):
                continue  # The saved value will be deleted. No check needed.
            try:
                cleaned[spec.key] = registry.validate(spec, cleaned.get(spec.key, ""))
            except ValueError as exc:
                self.add_error(spec.key, str(exc))
        return cleaned


def settings_form(group: str) -> type[SettingsForm]:
    """A form class with one field for each setting of the group."""
    specs = registry.specs_in(group)
    fields: dict = {"specs": specs}
    for spec in specs:
        fields[spec.key] = _field(spec)
        fields[RESET_PREFIX + spec.key] = forms.BooleanField(
            required=False,
            label="Clear the saved value" if spec.secret else "Use the default",
            widget=forms.CheckboxInput(attrs={"class": CHECKBOX}),
        )
    return type(f"{group.title()}SettingsForm", (SettingsForm,), fields)


class ScheduleForm(forms.Form):
    """One schedule entry."""

    name = forms.CharField(max_length=200, widget=forms.TextInput(attrs={"class": INPUT}))
    task = forms.ChoiceField(widget=forms.Select(attrs={"class": INPUT}))
    minute = forms.CharField(
        max_length=60, initial="0", widget=forms.TextInput(attrs={"class": INPUT})
    )
    hour = forms.CharField(
        max_length=60, initial="*", widget=forms.TextInput(attrs={"class": INPUT})
    )
    day_of_week = forms.CharField(
        max_length=60, initial="*", widget=forms.TextInput(attrs={"class": INPUT})
    )
    day_of_month = forms.CharField(
        max_length=60, initial="*", widget=forms.TextInput(attrs={"class": INPUT})
    )
    month = forms.CharField(
        max_length=60, initial="*", widget=forms.TextInput(attrs={"class": INPUT})
    )
    enabled = forms.BooleanField(
        required=False, initial=True, widget=forms.CheckboxInput(attrs={"class": CHECKBOX})
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        task_field = cast("forms.ChoiceField", self.fields["task"])
        task_field.choices = [
            (task, f"{label} ({task})") for task, label in schedule.schedulable_tasks().items()
        ]

    def clean(self) -> dict:
        """Check the five cron fields together."""
        cleaned = super().clean() or {}
        fields = ("minute", "hour", "day_of_week", "day_of_month", "month")
        if all(cleaned.get(name) for name in fields):
            try:
                schedule.parse_cron(*(cleaned[name] for name in fields))
            except ValueError as exc:
                raise forms.ValidationError(str(exc)) from exc
        return cleaned


class FeedForm(forms.ModelForm):
    """Add a news feed."""

    class Meta:
        model = NewsFeed
        fields = ("source", "name", "url")
        widgets: ClassVar[dict] = {name: forms.TextInput(attrs={"class": INPUT}) for name in fields}

    def clean_url(self) -> str:
        """Only http and https addresses."""
        url = self.cleaned_data["url"].strip()
        if not url.lower().startswith(("http://", "https://")):
            msg = "Use an address that starts with http:// or https://."
            raise forms.ValidationError(msg)
        return url


class InstrumentForm(forms.ModelForm):
    """Add or change an instrument."""

    class Meta:
        model = Instrument
        fields = ("symbol", "name", "kind", "weight", "scale", "enabled")
        widgets: ClassVar[dict] = {
            "symbol": forms.TextInput(attrs={"class": INPUT}),
            "name": forms.TextInput(attrs={"class": INPUT}),
            "kind": forms.Select(attrs={"class": INPUT}),
            "weight": forms.NumberInput(attrs={"class": INPUT, "step": "0.01"}),
            "scale": forms.NumberInput(attrs={"class": INPUT, "step": "0.1"}),
            "enabled": forms.CheckboxInput(attrs={"class": CHECKBOX}),
        }

    def clean_weight(self) -> float:
        """A weight is from -1 to 1."""
        weight = self.cleaned_data["weight"]
        if not -1 <= weight <= 1:
            msg = "The weight is from -1 to 1."
            raise forms.ValidationError(msg)
        return weight

    def clean_scale(self) -> float:
        """A scale is more than zero."""
        scale = self.cleaned_data["scale"]
        if scale <= 0:
            msg = "The scale must be more than 0."
            raise forms.ValidationError(msg)
        return scale

    def clean(self) -> dict:
        """The target index stays. It cannot be changed here."""
        cleaned = super().clean() or {}
        kind = cleaned.get("kind")
        existing = self.instance.kind if self.instance.pk else None
        if kind == Instrument.Kind.TARGET and existing != Instrument.Kind.TARGET:
            raise forms.ValidationError("There is one target index. Edit the existing one.")
        if existing == Instrument.Kind.TARGET and kind != Instrument.Kind.TARGET:
            raise forms.ValidationError("The target index must stay the target.")
        if existing == Instrument.Kind.TARGET and not cleaned.get("enabled", True):
            raise forms.ValidationError("The target index cannot be turned off.")
        return cleaned


class SubscriptionGiveForm(forms.Form):
    """Give or change the subscription of a user. Use the days or an end date, not both."""

    kind = forms.ChoiceField(
        choices=Subscription.Kind.choices,
        initial=Subscription.Kind.PAID,
        widget=forms.Select(attrs={"class": INPUT}),
    )
    days = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=3650,
        label="Days to add",
        widget=forms.NumberInput(attrs={"class": INPUT, "inputmode": "numeric"}),
    )
    ends_on = forms.DateField(
        required=False,
        label="Or: ends at the end of",
        widget=forms.DateInput(attrs={"class": INPUT, "type": "date"}),
    )
    note = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={"class": INPUT, "placeholder": "For example: paid by UPI"}),
    )

    def clean(self) -> dict:
        """Exactly one of the days and the end date."""
        cleaned = super().clean() or {}
        has_days = cleaned.get("days") is not None
        has_date = cleaned.get("ends_on") is not None
        if has_days == has_date and not self.errors:
            raise forms.ValidationError("Enter the number of days, or an end date. Not both.")
        return cleaned
