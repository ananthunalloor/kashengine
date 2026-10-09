"""Template filters and tags for the Ops pages."""

from datetime import datetime

from django import template
from django.utils import timezone
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe

from apps.ops import health
from apps.ops.metrics import format_bytes

register = template.Library()

GAIN = "bg-gain-soft text-gain"
LOSS = "bg-loss-soft text-loss"
WARN = "bg-warn-soft text-warn"
FLAT = "bg-flat-soft text-muted"

STATUS_CLASSES = {
    health.OK: GAIN,
    "success": GAIN,
    health.WARN: WARN,
    "pending": WARN,
    health.FAIL: LOSS,
    "failure": LOSS,
    health.SKIP: FLAT,
    "started": FLAT,
    "login": GAIN,
    "logout": FLAT,
    "failed": LOSS,
}
STATUS_TEXT = {
    health.OK: "OK",
    health.WARN: "Warning",
    health.FAIL: "Problem",
    health.SKIP: "No data",
}
MS_PER_SECOND = 1000
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400


@register.filter
def status_class(status):
    """The colour classes for a status label."""
    return STATUS_CLASSES.get(status, FLAT)


@register.filter
def status_text(status):
    """The words for a health status."""
    return STATUS_TEXT.get(status, str(status))


@register.filter
def duration(ms):
    """850 ms, 1.2 s, or 3 min 4 s. An empty value gives a dash."""
    if ms in (None, ""):
        return "–"
    ms = int(ms)
    if ms < MS_PER_SECOND:
        return f"{ms} ms"
    seconds = ms / MS_PER_SECOND
    if seconds < SECONDS_PER_MINUTE:
        return f"{seconds:.1f} s"
    minutes, rest = divmod(int(seconds), SECONDS_PER_MINUTE)
    return f"{minutes} min {rest} s"


@register.filter
def span(seconds):
    """A time span: 5 min, 3 h, or 2 days. An empty value gives a dash."""
    if seconds in (None, ""):
        return "–"
    seconds = int(seconds)
    if seconds < SECONDS_PER_MINUTE:
        return f"{seconds} s"
    if seconds < SECONDS_PER_HOUR:
        return f"{seconds // SECONDS_PER_MINUTE} min"
    if seconds < SECONDS_PER_DAY:
        return f"{seconds // SECONDS_PER_HOUR} h"
    return f"{seconds // SECONDS_PER_DAY} days"


@register.filter
def ago(moment: datetime | None):
    """How long ago a moment was: 5 min ago. An empty value gives a dash."""
    if not moment:
        return "–"
    seconds = (timezone.now() - moment).total_seconds()
    return f"{span(max(seconds, 0))} ago"


@register.filter
def until(moment: datetime | None):
    """How long until a moment: in 3 h. An empty value gives a dash."""
    if not moment:
        return "–"
    seconds = (moment - timezone.now()).total_seconds()
    return "now" if seconds <= 0 else f"in {span(seconds)}"


@register.filter
def bytes_text(value):
    """12.3 MB. An empty value gives a dash."""
    return format_bytes(value)


@register.filter
def short_agent(text: str) -> str:
    """A shorter browser name from a User-Agent text."""
    if not text:
        return "–"
    for name in ("Edg", "OPR", "Firefox", "Chrome", "Safari", "curl", "python-requests"):
        if name in text:
            return {"Edg": "Edge", "OPR": "Opera"}.get(name, name)
    return text[:30]


BAR_AREA_HEIGHT = 60
BAR_WIDTH = 14
BAR_GAP = 6


@register.simple_tag
def bar_chart(title, labels, values, alerts=None):
    """A bar chart as an inline SVG. `alerts` is an optional second series, drawn in red.

    The chart has a text table for screen readers.
    """
    alerts = alerts or [0] * len(values)
    peak = max([*values, *alerts, 1])
    width = len(values) * (BAR_WIDTH + BAR_GAP)
    bars = []
    for index, (value, alert) in enumerate(zip(values, alerts, strict=False)):
        x = index * (BAR_WIDTH + BAR_GAP) + BAR_GAP / 2
        for amount, css, offset in ((value, "fill-accent", 0), (alert, "fill-loss", 0)):
            if not amount:
                continue
            height = max(2, round(amount / peak * BAR_AREA_HEIGHT))
            half = BAR_WIDTH / 2 if alert and value else BAR_WIDTH
            left = x + (half if css == "fill-loss" and value else offset)
            bars.append(
                format_html(
                    '<rect x="{}" y="{}" width="{}" height="{}" class="{}">'
                    "<title>{}: {}</title></rect>",
                    left,
                    BAR_AREA_HEIGHT - height,
                    half,
                    height,
                    css,
                    labels[index],
                    amount,
                )
            )
    rows = "".join(
        f"<tr><th scope='row'>{escape(label)}</th><td>{value}</td><td>{alert}</td></tr>"
        for label, value, alert in zip(labels, values, alerts, strict=False)
    )
    return format_html(
        '<svg viewBox="0 0 {} {}" class="h-20 w-full" role="img" aria-label="{}" '
        'preserveAspectRatio="none">{}</svg>'
        '<table class="sr-only"><caption>{}</caption><tbody>{}</tbody></table>',
        width,
        BAR_AREA_HEIGHT,
        title,
        mark_safe("".join(bars)),  # noqa: S308  # Each bar is made with format_html.
        title,
        mark_safe(rows),  # noqa: S308  # The labels are escaped above.
    )
