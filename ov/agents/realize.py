"""The mechanical lift — turn ``ov``'s skills into agent definitions and realize them.

This is the thin ov-specific facade over coact's two transforms (D4): ``COMPLETE``
(a ``.claude/skills/`` skill → an :class:`coact.AgentDefinition`, reading the extras
from the skill's ``coact:`` block) and ``REALIZE`` (a definition → a running agent on
a chosen backend). Nothing here re-implements an agent loop or a persona; coact does
the lift, ``ov`` just points it at the right skills and surfaces the cost gate.

The cheapest backend is the default (``host``): :func:`materialize` writes
``.claude/agents/*.md`` and links the skills so **Claude Code** runs ov's agents as
subagents — no new runtime, no fan-out. Standing up an in-process fleet (``sdk``) or
a foreign-host tool server (``mcp``) is opt-in; call :func:`estimate` first to see the
~15× fan-out premium before you spawn one (the §3.5 cost gate).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Optional

from ._skills import skill_path
from ._util import require
from .definitions import OV_AGENTS, AgentSpec


def _resolve_spec(role_or_name: str) -> AgentSpec:
    """Resolve a role key (``"ux-analyst"``), an agent/skill name, to an :class:`AgentSpec`."""
    if role_or_name in OV_AGENTS:
        return OV_AGENTS[role_or_name]
    for spec in OV_AGENTS.values():
        if role_or_name in (spec.name, spec.skill):
            return spec
    known = ", ".join(OV_AGENTS)
    raise KeyError(f"unknown ov agent {role_or_name!r} (known roles: {known})")


def _specs(roles: Optional[Iterable[str]] = None) -> list[AgentSpec]:
    """The specs for ``roles`` (default: all, in registry order)."""
    if roles is None:
        return list(OV_AGENTS.values())
    return [_resolve_spec(role) for role in roles]


def complete_agent(
    role_or_name: str,
    *,
    skills_dir: str | Path | None = None,
    policy: Any = None,
    llm: Any = None,
) -> Any:
    """``COMPLETE`` one ov skill into a :class:`coact.AgentDefinition` (the lift).

    Mechanical by default (no LLM): model, tools, return contract and MCP wiring come
    from the skill's ``coact:`` block. Pass ``llm=`` only to let coact *draft* a
    persona — the deterministic template path is used otherwise.
    """
    (coact,) = require("coact", feature="ov.agents.complete_agent")
    spec = _resolve_spec(role_or_name)
    source = skill_path(spec.skill, skills_dir=skills_dir)
    return coact.complete(str(source), policy=policy, llm=llm)


def complete_all(
    *,
    roles: Optional[Iterable[str]] = None,
    skills_dir: str | Path | None = None,
    policy: Any = None,
) -> dict[str, Any]:
    """``COMPLETE`` every ov agent (or ``roles``) → ``{role: AgentDefinition}``."""
    return {
        role: complete_agent(role, skills_dir=skills_dir, policy=policy)
        for role in (roles or list(OV_AGENTS))
    }


def materialize(
    *,
    roles: Optional[Iterable[str]] = None,
    dest: str | Path | None = None,
    scope: str = "project",
    project_dir: str | Path | None = None,
    link: bool = True,
    skills_dir: str | Path | None = None,
    force: bool = False,
    policy: Any = None,
) -> Any:
    """Realize ov's agents on the **host** backend: write ``.claude/agents/`` + link skills.

    This is the cheap pit-of-success — it stands up *no* runtime. It emits one
    ``<name>.md`` per agent into ``dest`` (default: the project's ``.claude/agents/``)
    and symlinks each referenced skill into the sibling ``.claude/skills/`` so Claude
    Code discovers both, then verifies discovery. Returns coact's ``RealizedHost``
    (``.agents``, ``.skills``, ``.warnings``).
    """
    (coact,) = require("coact", feature="ov.agents.materialize")
    agents = [
        complete_agent(spec.name, skills_dir=skills_dir, policy=policy)
        for spec in _specs(roles)
    ]
    return coact.realize(
        agents,
        backend="host",
        scope=scope,
        dest=dest,
        project_dir=project_dir,
        link=link,
        skills_source=str(skills_dir) if skills_dir is not None else None,
        force=force,
    )


def realize_agent(
    role_or_name: str,
    *,
    backend: str = "host",
    skills_dir: str | Path | None = None,
    policy: Any = None,
    **kwargs: Any,
) -> Any:
    """Realize a single ov agent on ``backend`` (``"host"`` | ``"sdk"`` | ``"mcp"``).

    ``sdk`` returns a ``coact.RunnableAgent`` (an ``aw.AgenticStep``) for text-shaped
    agents; ``mcp`` exposes the skill's declared ``coact: mcp:`` tools as a FastMCP
    server (foreign hosts). For ov's live-browser / multimodal runtimes use
    :class:`~ov.agents.operator.OperatorAgent` / :class:`~ov.agents.analyst.AnalystAgent`
    instead — coact's text-prompt ``sdk`` agent can't drive a page or send images.
    """
    (coact,) = require("coact", feature="ov.agents.realize_agent")
    spec = _resolve_spec(role_or_name)
    source = skill_path(spec.skill, skills_dir=skills_dir)
    target = (
        coact.complete(str(source), policy=policy) if backend != "mcp" else str(source)
    )
    return coact.realize(target, backend=backend, **kwargs)


def estimate(
    roles: Optional[Iterable[str]] = None,
    *,
    skills_dir: str | Path | None = None,
) -> Any:
    """The cost gate — coact's fan-out estimate over the selected ov agents.

    Realizing an in-package fleet costs roughly an order of magnitude more tokens
    than the host path, and the premium is worst on *interdependent* work (ov's
    analysts share the evidence bundle). Render this before spawning::

        from ov.agents import estimate
        print(estimate(["ux-analyst", "arch-analyst"]).render())
    """
    (coact,) = require("coact", feature="ov.agents.estimate")
    agents = [
        complete_agent(spec.name, skills_dir=skills_dir) for spec in _specs(roles)
    ]
    return coact.estimate(agents)
