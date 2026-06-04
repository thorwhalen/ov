"""SSOT: which ``ov`` skills become which agents (role, lens, model routing).

The *extras* a skill needs to become an agent — model, tool allowlist, return
contract, MCP exposure — live in each skill's additive ``coact:`` frontmatter block
(coact reads them during ``COMPLETE``). This module records only the ov-side mapping
coact cannot infer: which skill plays which **role** in the study pipeline and, for
analysts, which analysis **lens** it carries.

Everything here is *data*. Add an agent by adding a row — no dispatcher to edit
(open-closed). This mirrors ``ov``'s other registries (probes / analyzers / report
sections): a capability is a registered piece of data, never a branch in a switch.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSpec:
    """One ``ov`` agent: its name, role, source skill, optional lens, default model.

    >>> AgentSpec("ov-analyze-ux", "analyst", "ov-analyze-ux", "ux").lens
    'ux'
    """

    name: str
    role: str  # "operator" | "analyst" | "orchestrator"
    skill: str
    lens: str | None = None  # analysts only: "ux" | "arch"
    default_model: str = "sonnet"  # fallback when the skill carries no coact: model


#: The ``ov`` agent registry (role key -> spec) — the headline of Phase 4.
#: Model defaults follow the spec's §10 cost gate (Opus for design/planning
#: judgment, Sonnet for grounded UX narrative, Haiku for the throughput-bound driver).
OV_AGENTS: dict[str, AgentSpec] = {
    "operator": AgentSpec("ov-operate", "operator", "ov-operate", None, "haiku"),
    "ux-analyst": AgentSpec("ov-analyze-ux", "analyst", "ov-analyze-ux", "ux", "sonnet"),
    "arch-analyst": AgentSpec(
        "ov-analyze-arch", "analyst", "ov-analyze-arch", "arch", "opus"
    ),
    "orchestrator": AgentSpec("study-web-app", "orchestrator", "study-web-app", None, "opus"),
}


def agents_for_role(role: str) -> list[AgentSpec]:
    """All specs with ``role`` (e.g. both analysts).

    >>> [s.lens for s in agents_for_role("analyst")]
    ['ux', 'arch']
    """
    return [spec for spec in OV_AGENTS.values() if spec.role == role]


def analyst_specs() -> list[AgentSpec]:
    """The UX + Arch analyst specs, in pipeline order (UX then Arch)."""
    return agents_for_role("analyst")
