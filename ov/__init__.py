"""``ov`` -- OverView: agent-driven web reconnaissance & analysis.

Point ``ov`` at a URL and it drives the target like a user, recording two
parallel streams -- the *behavioral* stream (what the app does) and the *static*
stream (what it is made of) -- then runs two analysis lenses (UX and
software-design) and renders Markdown reports plus a single synopsis.

This module is the **progressive-disclosure facade**: the five top-level
functions below are all most callers need, and each works with sensible defaults.
Everything underneath (capture probes, operate primitives, analyzers, report
sections) is reachable but never required.

    >>> import ov
    >>> callable(ov.observe) and callable(ov.overview)
    True

The primary consumption model is a *host agent* (Claude Code) wielding these
functions via the skills in ``.claude/skills/`` -- the deterministic core here
runs with no model and no host.
"""

from __future__ import annotations

from typing import Any, Iterable

from .base import CaptureRun
from .config import OvConfig
from .util import check_requirements

# Naming note: the facade exposes ``analyze``/``report``/``overview`` as
# *functions* (the public API of §4). The internal subpackages are therefore
# named ``ov/analysis/`` and ``ov/reporting/`` (not ``analyze``/``report``) so a
# subpackage import can never shadow the same-named facade function on ``ov`` --
# a real Python attribute collision the spec's two halves would otherwise create.

__all__ = [
    "observe",
    "analyze",
    "report",
    "synopsis",
    "overview",
    "check_requirements",
    "OvConfig",
    "CaptureRun",
    "__version__",
]

__version__ = "0.1.0"


def observe(
    url: str,
    *,
    goal: str | None = None,
    journey: list | None = None,
    mode: str = "reconstruct",
    probes: Any = "default",
    headed: bool = False,
    store: Any = None,
    crawl_pages: int | None = None,
    config: OvConfig | None = None,
    authorized: bool | None = None,
) -> CaptureRun:
    """Drive the target and capture everything. Zero-config default works.

    Args:
        url: the target to study.
        goal: a natural-language objective (goal-pursuit is *host* policy; the
            deterministic core records it and does the baseline journey).
        journey: an optional scripted action list (guided-replay), each item an
            :class:`~ov.base.Action` or a dict like ``{"type": "click", "ref": "e3"}``.
        mode: ``"reconstruct"`` (foreign target) or ``"review"`` (own target).
        probes: ``"default"``, ``"all"``, or an iterable of probe names.
        headed: run the browser headed (default headless).
        store: a :class:`~ov.capture.stores.CaptureStore`, a path, or ``None``.
        crawl_pages: if set (>1), politely crawl that many same-origin pages.
        config: an explicit :class:`OvConfig` (overrides ``headed``).
        authorized: acknowledge authorization to study a *foreign* target.

    Returns:
        The populated :class:`~ov.base.CaptureRun` (also persisted to the store).
    """
    from .capture.session import CaptureSession
    from .operate.driver import crawl as _crawl
    from .operate.driver import replay as _replay

    cfg = config or OvConfig.from_env(headed=headed)
    if authorized is not None:
        cfg.authorized = authorized

    session = CaptureSession(
        target_url=url, config=cfg, store=store, mode=mode, probes=probes
    )
    with session:
        session.open()
        if goal:
            session.run.notes.append(f"goal: {goal} (goal-pursuit is host policy)")
        if journey:
            _replay(session, journey)
        elif crawl_pages and crawl_pages > 1:
            _crawl(session, max_pages=crawl_pages)
    return session.run


def analyze(
    run: Any,
    *,
    lenses: Iterable[str] = ("ux", "arch"),
    llm: Any = None,
    store: Any = None,
) -> dict:
    """Run the deterministic UX + architecture analyzers over a captured run.

    Runs fully without a model (``llm=None`` is the default and the only path
    needed in Phases 1-2). The host agent reasons over the returned analyses +
    evidence bundle to add narrative judgment.
    """
    try:
        from .analysis.run import run_analysis
    except ModuleNotFoundError as e:  # the deterministic analyzers land in Phase 2
        if (e.name or "").startswith("ov.analysis"):
            raise NotImplementedError(
                "ov.analyze (deterministic UX + architecture analyzers) is a Phase 2 feature"
            ) from e
        raise
    return run_analysis(run, lenses=tuple(lenses), store=store)


def report(
    run_or_analyses: Any,
    *,
    sections: Any = "default",
    out_dir: Any = None,
    store: Any = None,
) -> list:
    """Render Markdown reports from analyses. Returns the written paths/keys."""
    try:
        from .reporting.render import render_reports
    except ModuleNotFoundError as e:  # report rendering lands in Phase 2
        if (e.name or "").startswith("ov.reporting"):
            raise NotImplementedError(
                "ov.report (Markdown report rendering) is a Phase 2 feature"
            ) from e
        raise
    return render_reports(run_or_analyses, sections=sections, out_dir=out_dir, store=store)


def synopsis(reports_or_dir: Any, *, out: Any = None, store: Any = None) -> Any:
    """Extract-and-aggregate many reports into one synopsis for downstream agents."""
    try:
        from .reporting.synopsis import build_synopsis
    except ModuleNotFoundError as e:  # the synopsis map-reduce lands in Phase 2
        if (e.name or "").startswith("ov.reporting"):
            raise NotImplementedError(
                "ov.synopsis (extract-and-aggregate synopsis) is a Phase 2 feature"
            ) from e
        raise
    return build_synopsis(reports_or_dir, out=out, store=store)


def overview(url: str, **kw: Any) -> Any:
    """``observe -> analyze -> report -> synopsis``, the one-liner.

    Returns the synopsis path/handle. This is the pit-of-success entry point.
    """
    try:
        from .reporting.overview import run_overview
    except ModuleNotFoundError as e:  # the full pipeline lands in Phase 2
        if (e.name or "").startswith("ov.reporting"):
            raise NotImplementedError(
                "ov.overview (observe -> analyze -> report -> synopsis) is a Phase 2 feature; "
                "ov.observe(url) is available now"
            ) from e
        raise
    return run_overview(url, **kw)
