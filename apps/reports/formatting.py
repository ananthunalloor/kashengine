"""Display scores consistently in reports and web pages."""


def score_out_of_ten(value: float | str | None, *, signed: bool = False) -> str:
    """Format a 0..1 score (or a signed -1..1 score) on a 1.0..10.0 scale."""
    if value is None or value == "":
        return "–"
    number = float(value)
    if signed:
        number = (number + 1) / 2
    return f"{1 + 9 * number:.1f}/10"
