"""Tests for the reference generator (`docs/scripts/generate_reference.py` and `docgen`)."""

import importlib
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs" / "scripts"))
inventory = importlib.import_module("docgen.inventory")
checks = importlib.import_module("docgen.checks")
docstrings = importlib.import_module("docgen.docstrings")
generator = importlib.import_module("generate_reference")


def scan(tmp_path: Path, source: str) -> list:
    """Write `source` as `apps/demo/code.py` and return the findings for it."""
    folder = tmp_path / "apps" / "demo"
    folder.mkdir(parents=True)
    (folder / "code.py").write_text(textwrap.dedent(source), encoding="utf-8")
    return checks.findings(inventory.inspect(tmp_path, ["apps"]))


def names(found: list) -> set[str]:
    return {item.name for item in found}


GOOD = '''
    """Demo module."""


    def good(a: int, b: int) -> int:
        """Add two numbers.

        Args:
            a: The first number.
            b: The second number.

        Returns:
            The sum.
        """
        return a + b
'''


def test_complete_function_has_no_finding(tmp_path):
    assert scan(tmp_path, GOOD) == []


def test_missing_docstring_is_found(tmp_path):
    found = scan(tmp_path, '"""Demo."""\n\n\ndef bad(a):\n    return a\n')
    assert names(found) == {"bad"}
    assert found[0].status == checks.MISSING


def test_missing_module_docstring_is_found(tmp_path):
    found = scan(tmp_path, "def f():\n    return 1\n")
    assert "<module>" in names(found)


def test_args_must_list_every_parameter(tmp_path):
    found = scan(
        tmp_path,
        '''
        """Demo."""


        def f(a, b):
            """Do it.

            Args:
                a: One.
            """
            print(a, b)
        ''',
    )
    assert any("Args does not list: b" in problem for item in found for problem in item.problems)


def test_args_must_not_list_unknown_names(tmp_path):
    found = scan(
        tmp_path,
        '''
        """Demo."""


        def f(a):
            """Do it.

            Args:
                a: One.
                z: Not a parameter.
            """
            print(a)
        ''',
    )
    assert any("that are not parameters: z" in p for item in found for p in item.problems)


def test_returns_section_is_required_for_a_value(tmp_path):
    found = scan(
        tmp_path,
        '''
        """Demo."""


        def f(a: int) -> int:
            """Double.

            Args:
                a: A number.
            """
            b = a * 2
            return b
        ''',
    )
    assert any("no Returns section" in p for item in found for p in item.problems)


def test_raises_section_is_required_for_an_explicit_raise(tmp_path):
    found = scan(
        tmp_path,
        '''
        """Demo."""


        def f() -> None:
            """Fail."""
            msg = "no"
            raise ValueError(msg)
        ''',
    )
    assert any("no Raises section" in p for item in found for p in item.problems)


def test_meta_class_and_dunder_need_only_a_summary(tmp_path):
    found = scan(
        tmp_path,
        '''
        """Demo."""


        class Thing:
            """A thing."""

            class Meta:
                ordering = ("a",)

            def __str__(self):
                """Return the name."""
                return "x"
        ''',
    )
    assert found == []


def test_route_function_needs_only_a_summary(tmp_path):
    found = scan(
        tmp_path,
        '''
        """Demo."""


        @router.get("/things", summary="List things")
        def list_things(request, page: int = 1) -> list:
            """List things."""
            return [request, page]
        ''',
    )
    assert found == []


def test_tests_are_not_scanned(tmp_path):
    folder = tmp_path / "apps" / "demo" / "tests"
    folder.mkdir(parents=True)
    (folder / "test_x.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    assert inventory.inspect(tmp_path, ["apps"]) == []


def test_parse_reads_sections():
    doc = docstrings.parse(
        textwrap.dedent(
            """\
            Summary line.

            More text.

            Args:
                a (int): First.
                *rest: The rest.

            Raises:
                ValueError: If bad.
            """
        )
    )
    assert doc.summary == "Summary line."
    assert doc.documented_params == {"a", "rest"}
    assert doc.raised == {"ValueError"}


def test_escape_keeps_code_and_escapes_mdx_characters():
    assert docstrings.escape("a < b {x} `<code> {y}`") == "a &lt; b &#123;x&#125; `<code> {y}`"


def test_cell_escapes_pipes_and_newlines():
    assert docstrings.cell("a | b\nc") == "a \\| b c"


def test_baseline_accepts_known_gaps_and_rejects_new_ones(tmp_path, capsys):
    found = scan(tmp_path, '"""Demo."""\n\n\ndef bad(a):\n    return a\n')
    baseline = tmp_path / "baseline.txt"
    assert generator.check_against_baseline(found, baseline) == 1  # No baseline: it is new.
    generator.write_baseline(baseline, found)
    assert generator.check_against_baseline(found, baseline) == 0
    assert generator.check_against_baseline([], baseline) == 1  # Fixed, but still listed.
    assert "remove from the baseline" in capsys.readouterr().err


def test_baseline_key_has_no_line_number(tmp_path):
    found = scan(tmp_path, '"""Demo."""\n\n\ndef bad(a):\n    return a\n')
    assert generator.finding_key(found[0]) == "apps/demo/code.py::bad"


@pytest.mark.parametrize("flag", ["--check"])
def test_repository_meets_the_docstring_contract(flag, capsys):
    """CI gate: new code needs a complete docstring. Only the baseline may have gaps."""
    code = generator.main(["--no-write", flag])
    output = capsys.readouterr()
    assert code == 0, output.err
