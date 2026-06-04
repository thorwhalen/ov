"""``ov.agents`` — the optional in-package agent layer (Phase 4 productization).

This is the *mechanical lift* the spec promised (§7, D4): the Phase-1–3 deterministic
core + the ``.claude/skills/`` policy are re-hosted as **runnable agents**, with no
rewrite. The lift is done by `coact <https://github.com/thorwhalen/coact>`_
(``COMPLETE`` a skill into an agent definition, ``REALIZE`` it onto a backend); this
package is the thin ov-specific glue that coact intentionally leaves out — the
operator's live-browser **loop**, the analyst's **multimodal** evidence-bundle call,
and the orchestration **topology**.

Three things to know:

* **Host stays the manager (the cheap default).** :func:`materialize` writes
  ``.claude/agents/`` so Claude Code runs ov's agents as subagents — zero LLM, no
  fan-out. In-package SDK agents (:class:`OperatorAgent`, :class:`AnalystAgent`,
  :func:`study`) are opt-in; :func:`estimate` surfaces the ~15× fan-out cost gate.
* **Reuse, don't rewrite.** Capture, the analyzers, the evidence-bundle assembler,
  the reliability passes and the synopsis map-reduce are used unchanged.
* **Injected, optional, model-free-by-default.** Every LLM is dependency-injected;
  ``coact``/``aw``/``py2mcp`` are the ``ov[agents]`` extra, gated with a friendly
  error — importing this package needs none of them.

    >>> from ov.agents import OV_AGENTS, default_model
    >>> sorted(OV_AGENTS)
    ['arch-analyst', 'operator', 'orchestrator', 'ux-analyst']
    >>> default_model("operator")
    'haiku'
"""

from __future__ import annotations

from typing import Any

# Light, always-available surface (no optional deps).
from .definitions import AgentSpec, OV_AGENTS, agents_for_role, analyst_specs
from .llm import DEFAULT_MODELS, default_model, resolve_llm, structured
from ._skills import default_skills_dir, skill_path

__all__ = [
    # SSOT / data
    "AgentSpec",
    "OV_AGENTS",
    "agents_for_role",
    "analyst_specs",
    "default_skills_dir",
    "skill_path",
    # LLM facade
    "DEFAULT_MODELS",
    "default_model",
    "resolve_llm",
    "structured",
    # The mechanical lift (coact) — lazily loaded (needs ov[agents])
    "complete_agent",
    "complete_all",
    "materialize",
    "realize_agent",
    "estimate",
    # In-package runtimes — lazily loaded
    "OperatorAgent",
    "AnalystAgent",
    "ux_analyst",
    "arch_analyst",
    "study",
    "Orchestrator",
    # Foreign-host MCP — lazily loaded
    "mcp_server",
    "ov_tools",
]

#: attribute name -> submodule that defines it (loaded on first access so the base
#: import stays free of coact/aw/py2mcp).
_LAZY = {
    "complete_agent": "realize",
    "complete_all": "realize",
    "materialize": "realize",
    "realize_agent": "realize",
    "estimate": "realize",
    "OperatorAgent": "operator",
    "AnalystAgent": "analyst",
    "ux_analyst": "analyst",
    "arch_analyst": "analyst",
    "study": "orchestrator",
    "Orchestrator": "orchestrator",
    "mcp_server": "mcp",
    "ov_tools": "mcp",
}


def __getattr__(name: str) -> Any:
    """Lazily resolve coact/aw/py2mcp-backed symbols from their submodule (PEP 562)."""
    module_name = _LAZY.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module = importlib.import_module(f"{__name__}.{module_name}")
    return getattr(module, name)


def __dir__() -> list[str]:
    return sorted(__all__)
