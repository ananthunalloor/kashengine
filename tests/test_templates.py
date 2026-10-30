"""Guard for a fault that a code formatter can cause in Django templates."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = sorted(
    [
        *(ROOT / "apps").glob("*/templates/**/*.html"),
        *(ROOT / "tests/legacy_templates").glob("**/*.html"),
    ]
)


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: str(p.relative_to(ROOT)))
def test_template_tags_and_variables_stay_on_one_line(path):
    """Django reads `{% %}` and `{{ }}` on one line only. A split tag breaks the page."""
    broken = [
        number
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if line.count("{%") != line.count("%}") or line.count("{{") != line.count("}}")
    ]
    assert not broken, f"Join the tag on these lines: {broken}"
