"""Cheap CI gate: every SKILL.md under agent-runtime/skills must have valid,
complete YAML frontmatter. This is a structural lint, not an LLM eval of
skill quality — run with `pytest agent-runtime/tests`.
"""

from pathlib import Path

import pytest
import yaml

SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"

# _shared/ holds an included markdown fragment, not a skill with its own
# frontmatter — every other immediate subdirectory must be a skill.
SKILL_DIRS = [
    p for p in SKILLS_ROOT.iterdir() if p.is_dir() and not p.name.startswith("_")
]


def _read_frontmatter(skill_md: Path) -> dict:
    text = skill_md.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{skill_md} must start with a YAML frontmatter block"
    _, _, rest = text.partition("---\n")
    frontmatter_text, sep, _body = rest.partition("\n---\n")
    assert sep, f"{skill_md} frontmatter block is not closed with a second '---' line"
    return yaml.safe_load(frontmatter_text)


@pytest.mark.parametrize("skill_dir", SKILL_DIRS, ids=lambda p: p.name)
def test_skill_has_valid_frontmatter(skill_dir: Path):
    skill_md = skill_dir / "SKILL.md"
    assert skill_md.exists(), f"{skill_dir} has no SKILL.md"

    frontmatter = _read_frontmatter(skill_md)

    assert "name" in frontmatter, f"{skill_md} frontmatter missing 'name'"
    name = frontmatter["name"]
    assert name == name.lower(), f"{skill_md} name must be lowercase"
    assert all(c.isalnum() or c == "-" for c in name), (
        f"{skill_md} name must use only lowercase letters, digits, and hyphens"
    )
    assert name == skill_dir.name, (
        f"{skill_md} frontmatter name '{name}' must match its directory name '{skill_dir.name}'"
    )

    assert "description" in frontmatter, f"{skill_md} frontmatter missing 'description'"
    description = frontmatter["description"]
    assert description, f"{skill_md} description must not be empty"
    assert len(description) <= 160, (
        f"{skill_md} description is {len(description)} chars, must be <= 160"
    )


def test_at_least_the_phase1_skills_exist():
    names = {p.name for p in SKILL_DIRS}
    assert {"triage", "draft-reply"} <= names
