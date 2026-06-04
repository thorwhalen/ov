"""Command-line interface -- ``argh`` dispatch over the same facade functions (§4).

This is the deterministic, scriptable face of the library (dispatch-to-interface):
``ov observe <url>``, ``ov analyze <run_id>``, ``ov report <run_id>``,
``ov synopsis <dir>``, ``ov overview <url>``, and ``ov check`` (requirements).
Each command calls the very functions a skill or a normal caller would call.
"""

from __future__ import annotations

import argh

import ov as _ov
from .capture.browser import BrowserNotAvailable
from .capture.stores import CaptureStore
from .util import check_requirements as _check_requirements


def observe(
    url,
    *,
    headed=False,
    probes="default",
    mode="reconstruct",
    crawl_pages: int = 1,
    store=None,
    authorized=False,
):
    """Capture a target into the store and print a summary of the run."""
    try:
        run = _ov.observe(
            url,
            headed=headed,
            probes=probes,
            mode=mode,
            crawl_pages=crawl_pages,
            store=store,
            authorized=authorized,
        )
    except BrowserNotAvailable as e:
        yield f"error: {e}"
        yield "run `ov check` to see what's missing, or `playwright install chromium`"
        return
    yield f"run_id: {run.run_id}"
    yield f"target: {run.target_url}  mode: {run.mode}"
    yield f"steps: {len(run.steps)}  artifacts: {len(run.artifacts)}"
    if run.fingerprint:
        yield "fingerprint: " + ", ".join(
            f"{t.name}({t.confidence})" for t in run.fingerprint[:8]
        )
    for note in run.notes:
        yield f"note: {note}"


def analyze(run_id, *, lenses="ux,arch", store=None):
    """Run the deterministic analyzers over a stored run (Phase 2)."""
    result = _ov.analyze(run_id, lenses=lenses.split(","), store=store)
    yield f"analyses: {list(result)}"


def report(run_id, *, sections="default", out_dir=None, store=None):
    """Render Markdown report sections for a stored run (Phase 2)."""
    paths = _ov.report(run_id, sections=sections, out_dir=out_dir, store=store)
    for p in paths:
        yield str(p)


def synopsis(run_id, *, out=None, store=None):
    """Aggregate a run's findings into a single synopsis (synopsis.json + SYNOPSIS.md)."""
    yield str(_ov.synopsis(run_id, out=out, store=store))


def overview(
    url, *, headed=False, mode="reconstruct", out_dir=None, store=None, authorized=False
):
    """observe -> analyze -> report -> synopsis, the one-liner (Phase 2)."""
    yield str(
        _ov.overview(
            url,
            headed=headed,
            mode=mode,
            out_dir=out_dir,
            store=store,
            authorized=authorized,
        )
    )


def evidence(run_id, *, step_id=None, model="opus", out_dir=None, store=None):
    """Build a grounded evidence bundle for a run (set-of-mark + token budget)."""
    from .analysis.evidence import build_evidence_bundle
    from .capture.stores import resolve_store

    s = resolve_store(store)
    try:
        run = s.load_run(run_id)
    except (KeyError, ValueError) as e:
        yield f"error: could not load run {run_id!r}: {e}"
        yield "run `ov runs` to list available run ids"
        return
    bundle = build_evidence_bundle(
        run, s, step_id=step_id, model=model, out_dir=out_dir
    )
    yield f"step: {bundle.step_id}"
    yield f"marks: {len(bundle.marks)}  facts: {len(bundle.facts)}"
    yield f"token_budget: {bundle.token_budget}"
    yield f"marked_images: {bundle.marked_image_artifact_ids}"


def check():
    """Check system dependencies (Playwright browsers, Node, sidecar, CLIs)."""
    rep = _check_requirements(verbose=False)
    yield rep.render()


def mcp():
    """Serve ov as an MCP server (stdio) for non-Claude-Code hosts (needs ov[agents])."""
    from .agents.mcp import main as _serve

    _serve()


def runs(*, store=None):
    """List stored capture run ids."""
    s = CaptureStore(store)
    for rid in s.run_ids():
        yield rid


def main(argv=None):
    """Entry point for the ``ov`` console script."""
    parser = argh.ArghParser(
        prog="ov", description="OverView: web reconnaissance & analysis"
    )
    argh.add_commands(
        parser,
        [observe, analyze, report, synopsis, overview, evidence, check, runs, mcp],
    )
    parser.dispatch(argv=argv)


if __name__ == "__main__":
    main()
