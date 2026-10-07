"""Small template filters for the web pages."""

from django import template

register = template.Library()

ARROWS = {"up": "▲", "down": "▼", "flat": "▬"}
DIRECTION_WORDS = {"up": "Up", "down": "Down", "flat": "Flat"}

TONE_CLASSES = {
    "gain": "bg-gain-soft text-gain",
    "loss": "bg-loss-soft text-loss",
    "flat": "bg-flat-soft text-muted",
}
BADGES = {
    "up": TONE_CLASSES["gain"],
    "down": TONE_CLASSES["loss"],
    "flat": TONE_CLASSES["flat"],
    "good": TONE_CLASSES["gain"],
    "weak": TONE_CLASSES["loss"],
    "mixed": TONE_CLASSES["flat"],
    "unknown": TONE_CLASSES["flat"],
    "sent": TONE_CLASSES["gain"],
    "failed": TONE_CLASSES["loss"],
    "open": TONE_CLASSES["gain"],
    "upcoming": TONE_CLASSES["flat"],
    "closed": TONE_CLASSES["flat"],
    "listed": TONE_CLASSES["flat"],
}


@register.filter
def signed(value, digits: int = 1):
    """+1.2 or -0.4 (with a real minus sign). An empty value gives a dash."""
    if value is None or value == "":
        return "–"
    number = float(value)
    text = f"{abs(number):.{int(digits)}f}"
    if number > 0 and float(text) != 0:
        return f"+{text}"
    if number < 0 and float(text) != 0:
        return f"−{text}"
    return text


@register.filter
def percent(value, digits: int = 0):
    """0.62 gives 62%."""
    if value is None or value == "":
        return "–"
    return f"{float(value) * 100:.{int(digits)}f}%"


@register.filter
def tone(value):
    """The text colour class for a number: green above zero, red below, grey at zero."""
    if value is None or value == "":
        return "text-muted"
    number = float(value)
    if number > 0:
        return "text-gain"
    if number < 0:
        return "text-loss"
    return "text-muted"


@register.filter
def arrow(direction):
    return ARROWS.get(direction, "")


@register.filter
def direction_word(direction):
    return DIRECTION_WORDS.get(direction, "")


@register.filter
def badge(key):
    """The colour classes for a small label (a direction, a verdict, a status)."""
    return BADGES.get(key, TONE_CLASSES["flat"])


@register.filter
def rupees(value):
    """₹1,234 or ₹1,234.50. An empty value gives a dash."""
    if value is None or value == "":
        return "–"
    number = float(value)
    return f"₹{number:,.0f}" if number == int(number) else f"₹{number:,.2f}"


@register.filter
def times(value):
    """52.3x. An empty value gives a dash."""
    if value is None or value == "":
        return "–"
    return f"{float(value):,.1f}x"


@register.filter
def get_item(mapping, key):
    return mapping.get(key) if hasattr(mapping, "get") else None
