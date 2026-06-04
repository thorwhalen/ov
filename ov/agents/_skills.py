"""Locate ``ov``'s bundled skills — the SSOT for the skill→agent lift.

``ov``'s skills are authored once, on disk, and are the single source of truth for
both the host-agent path (Claude Code reads ``.claude/skills/``) and the
productized agents (coact ``COMPLETE``-s those same files). To make the productized
agents work whether ``ov`` was ``pip install``-ed *or* run from a clone, the skills
are shipped into the wheel at ``ov/data/skills/`` (hatch ``force-include``) and this
resolver finds them in either layout:

1. an explicit ``OV_SKILLS_DIR`` env override;
2. the packaged ``ov/data/skills/`` (an installed wheel);
3. the repo's ``.claude/skills/`` (an editable / source checkout).

Point-don't-copy: callers pass the resolved *path* to coact, so the skill body is
never duplicated into an agent definition.
"""

from __future__ import annotations

import os
from pathlib import Path

#: The skills that participate in the study pipeline (used to recognize a skills dir).
AGENT_SKILLS = (
    "ov-capture",
    "ov-operate",
    "ov-analyze-ux",
    "ov-analyze-arch",
    "ov-report",
    "study-web-app",
)


def _has_skills(directory: Path) -> bool:
    """True if ``directory`` looks like an ov skills dir (holds known ``<name>/SKILL.md``)."""
    return directory.is_dir() and any(
        (directory / name / "SKILL.md").exists() for name in AGENT_SKILLS
    )


def default_skills_dir() -> Path:
    """Resolve the directory holding ``ov``'s skills (env, then packaged, then repo).

    Returns the first layout that actually contains skills; if none is found, the
    packaged path is returned so callers get a clear, consistent miss to report.

    Deliberately *not* cached: it reads ``OV_SKILLS_DIR`` at call time (a few cheap
    ``Path`` checks), so an env change is always honoured. Resolution is invoked
    once per agent lift, not in a hot loop, so the cost is immaterial.
    """
    env = os.environ.get("OV_SKILLS_DIR")
    if env and _has_skills(Path(env)):
        return Path(env)

    packaged = Path(__file__).resolve().parent.parent / "data" / "skills"
    if _has_skills(packaged):
        return packaged

    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".claude" / "skills"
        if _has_skills(candidate):
            return candidate

    return packaged


def skill_path(name: str, *, skills_dir: str | Path | None = None) -> Path:
    """Absolute path to skill ``name``'s directory (the one holding ``SKILL.md``).

    Raises :class:`FileNotFoundError` with an actionable hint when the skill is not
    discoverable, rather than letting coact fail later on a missing path.
    """
    directory = Path(skills_dir) if skills_dir is not None else default_skills_dir()
    path = directory / name
    if not (path / "SKILL.md").exists():
        raise FileNotFoundError(
            f"skill {name!r} not found under {directory} — set OV_SKILLS_DIR or pass "
            f"skills_dir= (known ov skills: {', '.join(AGENT_SKILLS)})"
        )
    return path
