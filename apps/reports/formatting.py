"""Display scores consistently in reports and web pages."""


def score_out_of_ten(value: float | str | None, *, signed: bool = False) -> str:
    """Format a 0..1 score (or a signed -1..1 score) on a 1.0..10.0 scale.

    The formula is `1 + 9 * score`. A signed score first becomes `(score + 1) / 2`, so 0 is 5.5.
    The function does not clamp a value that is out of range.

    Args:
        value: The score. A number, a numeric text, `None` or an empty text.
        signed: True if the score is in the range -1 to 1. False if it is in the range 0 to 1.

    Returns:
        A text such as `7.3/10`. An en dash for `None` or an empty text.
    """
    if value is None or value == "":
        return "–"
    number = float(value)
    if signed:
        number = (number + 1) / 2
    return f"{1 + 9 * number:.1f}/10"
