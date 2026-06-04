"""Expose ``ov`` to non-Claude-Code hosts as an MCP server (via ``py2mcp``).

The host-agent path assumes Claude Code. For *any other* MCP client (a different
agent runtime, an IDE, a foreign orchestrator) this module turns ``ov``'s coarse,
JSON-shaped facade into MCP tools — the spec's "optional ``py2mcp`` MCP server for
non-Claude-Code hosts" (§9.6 / Phase 4). It deliberately exposes the *coarse* entry
points (``study_url`` / ``capture_url``), not the page-stateful operate primitives:
MCP tools are stateless calls, and ``ov.observe`` already owns its own browser
session internally, so each tool is a clean one-shot.

``py2mcp`` builds the tool schemas by introspecting these functions' type hints and
docstrings, so they are kept small and well-typed on purpose. The same skill-declared
path also works the coact-native way::

    coact realize study-web-app --backend mcp   # reads the skill's `coact: mcp:` block

Run the server directly with ``python -m ov.agents.mcp`` (or the ``ov mcp`` CLI).
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from ._util import require


def study_url(
    url: str,
    *,
    mode: str = "reconstruct",
    authorized: bool = False,
    crawl_pages: int = 0,
    lenses: str = "ux,arch",
) -> dict:
    """Study a web app end-to-end (deterministic) and return its synopsis.

    Drives the target, runs the UX + architecture analyzers, and returns the
    deduplicated ``synopsis.json`` document — the compact, evidence-referenced SSOT a
    downstream agent acts on. Model-free (no LLM judgment); the host adds narrative.

    Args:
        url: the target to study.
        mode: ``"reconstruct"`` (foreign target) or ``"review"`` (own target).
        authorized: acknowledge authorization to study a foreign target.
        crawl_pages: if > 1, politely crawl that many same-origin pages.
        lenses: comma-separated analysis lenses (``"ux"``, ``"arch"``).

    Returns:
        The synopsis document (run id, deduplicated findings, severity histogram).
    """
    import ov
    from ov.reporting.synopsis import build_synopsis_doc

    run = ov.observe(
        url, mode=mode, authorized=authorized, crawl_pages=(crawl_pages or None)
    )
    ov.analyze(run, lenses=tuple(s.strip() for s in lenses.split(",") if s.strip()))
    return build_synopsis_doc(run)


def capture_url(
    url: str,
    *,
    mode: str = "reconstruct",
    authorized: bool = False,
    crawl_pages: int = 0,
) -> dict:
    """Capture a web app (behavioral + static streams) and return a compact summary.

    Runs only the deterministic capture (no analysis). Use when you want the raw
    captured facts (technologies, rendering model, step/artifact counts) without the
    analyzers.

    Args:
        url: the target to capture.
        mode: ``"reconstruct"`` or ``"review"``.
        authorized: acknowledge authorization to capture a foreign target.
        crawl_pages: if > 1, politely crawl that many same-origin pages.

    Returns:
        A summary dict (run id, target, counts, detected technologies, rendering model).
    """
    import ov

    run = ov.observe(
        url, mode=mode, authorized=authorized, crawl_pages=(crawl_pages or None)
    )
    return _run_summary(run)


def _run_summary(run: Any) -> dict:
    """A compact, JSON-safe summary of a :class:`~ov.base.CaptureRun` for MCP returns."""
    return {
        "run_id": run.run_id,
        "target_url": run.target_url,
        "mode": run.mode,
        "rendering_model": run.rendering_model,
        "source_maps_present": run.source_maps_present,
        "steps": len(run.steps),
        "artifacts": len(run.artifacts),
        "findings": len(run.findings),
        "technologies": [
            {"name": t.name, "version": t.version, "confidence": t.confidence}
            for t in run.fingerprint
        ],
        "api_endpoints": len(run.api_surface),
    }


def ov_tools() -> list[Callable]:
    """The ``ov`` callables exposed as MCP tools (coarse, stateless, JSON-shaped)."""
    return [study_url, capture_url]


def mcp_server(
    *,
    name: str = "ov",
    tools: Optional[list[Callable]] = None,
    input_trans: Optional[Callable[[dict], dict]] = None,
) -> Any:
    """Build a FastMCP server exposing ``ov`` to foreign hosts (via ``py2mcp``).

    >>> srv = mcp_server()                      # doctest: +SKIP
    >>> srv.run()                               # serve over stdio   # doctest: +SKIP
    """
    py2mcp, _fastmcp = require("py2mcp", "fastmcp", feature="ov.agents.mcp server")
    return py2mcp.mk_mcp_server(tools or ov_tools(), name=name, input_trans=input_trans)


def main() -> None:
    """Run the ``ov`` MCP server over stdio (``python -m ov.agents.mcp`` / ``ov mcp``)."""
    mcp_server().run()


if __name__ == "__main__":  # pragma: no cover - process entry point
    main()
