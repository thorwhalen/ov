"""Structural tests for the shipped skill layer (a first-class deliverable, §3.5)."""

from pathlib import Path

import pytest

SKILLS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "skills"
EXPECTED = {"study-web-app", "ov-capture", "ov-operate", "ov-analyze-ux",
            "ov-analyze-arch", "ov-report"}


def _frontmatter(text: str) -> dict[str, str]:
    """Parse the simple ``name``/``description`` YAML frontmatter (no yaml dep)."""
    assert text.startswith("---"), "SKILL.md must start with frontmatter"
    _, fm, _body = text.split("---", 2)
    fields: dict[str, str] = {}
    key = None
    for line in fm.splitlines():
        if line and not line.startswith((" ", "\t")) and ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            fields[key] = val.strip().lstrip(">-").strip()
        elif key and line.strip():  # folded continuation (e.g. description: >-)
            fields[key] = (fields.get(key, "") + " " + line.strip()).strip()
    return fields


def test_all_expected_skills_present():
    found = {p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md")}
    assert EXPECTED <= found, f"missing skills: {EXPECTED - found}"


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_skill_has_trigger_rich_frontmatter(name):
    text = (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
    fm = _frontmatter(text)
    assert fm.get("name") == name
    desc = fm.get("description", "")
    assert len(desc) >= 60, "description should be trigger-rich (hosts under-trigger)"


def test_main_skill_points_to_subskills():
    text = (SKILLS_DIR / "study-web-app" / "SKILL.md").read_text(encoding="utf-8")
    for sub in EXPECTED - {"study-web-app"}:
        assert sub in text, f"main skill should reference {sub}"


def test_skills_stay_small():
    # D4: split files past ~300 lines so the library stays light on context.
    for p in SKILLS_DIR.glob("*/SKILL.md"):
        assert len(p.read_text().splitlines()) <= 320, f"{p} is too long; split it"
