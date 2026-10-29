"""Check that the agent skills in `skills/` follow the Agent Skills format."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
SKILL_DIRS = sorted(path for path in SKILLS.iterdir() if path.is_dir())
NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
FRONTMATTER = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)
MAX_NAME = 64
MAX_DESCRIPTION = 1024
MAX_LINES = 500


def frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER.match(text)
    assert match, "SKILL.md must start with YAML frontmatter"
    fields = {}
    for line in match.group("body").splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip("'\"")
    return fields


@pytest.mark.parametrize("skill", SKILL_DIRS, ids=lambda path: path.name)
def test_skill_follows_format(skill):
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    fields = frontmatter(text)

    assert fields.get("name") == skill.name
    assert NAME_PATTERN.fullmatch(skill.name)
    assert len(skill.name) <= MAX_NAME
    assert 0 < len(fields.get("description", "")) <= MAX_DESCRIPTION
    assert text.count("\n") < MAX_LINES
    for path in skill.rglob("*"):
        if path.is_file():
            assert len(path.relative_to(skill).parts) <= 2, f"{path} is nested too deep"


@pytest.mark.parametrize("link", [".github/skills", ".claude/skills"])
def test_agent_skill_links_point_to_skills(link):
    path = ROOT / link
    assert path.is_symlink()
    assert path.resolve() == SKILLS
