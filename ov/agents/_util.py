"""Shared helpers for the ``ov`` agent layer — optional-dependency gating.

The agent layer is an opt-in productization (the ``[agents]`` extra): ``coact``,
``aw``, ``py2mcp`` and the Agent SDK are **not** core ``ov`` dependencies, so the
deterministic core stays model-free and cheap to install. These helpers turn a
missing optional dependency into one clear, actionable error (with the exact
install command) instead of a raw :class:`ImportError` deep in a call stack.
"""

from __future__ import annotations

import importlib
from types import ModuleType

#: top-level import name -> the pip target that provides it (all under ``ov[agents]``).
_PIP_FOR = {
    "coact": "coact",
    "aw": "aw",
    "py2mcp": "py2mcp",
    "fastmcp": "fastmcp",
    "claude_agent_sdk": "claude-agent-sdk",
}


def require(
    *import_names: str, feature: str = "the ov agent layer"
) -> list[ModuleType]:
    """Import and return the named modules, or raise a friendly install hint.

    Submodules are accepted (``"coact.llm"``); the pip target is keyed off the
    top-level package name.

    >>> require("json")[0].__name__
    'json'
    """
    mods: list[ModuleType] = []
    missing: list[str] = []
    for name in import_names:
        try:
            mods.append(importlib.import_module(name))
        except ImportError:
            missing.append(name)
    if missing:
        pips = " ".join(
            sorted({_PIP_FOR.get(m.split(".")[0], m.split(".")[0]) for m in missing})
        )
        raise ImportError(
            f"{feature} needs {', '.join(missing)} (not installed). Install with: "
            f"pip install 'ov[agents]'   (or: pip install {pips})"
        )
    return mods
