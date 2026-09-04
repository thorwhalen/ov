"""Command-line interface -- ``cw`` dispatch over the same facade functions (§4).

This is the deterministic, scriptable face of the library (dispatch-to-interface):
``ov observe <url>``, ``ov analyze <run_id>``, ``ov report <run_id>``,
``ov synopsis <dir>``, ``ov overview <url>``, and ``ov check`` (requirements).
Each command calls the very functions a skill or a normal caller would call.
"""

from __future__ import annotations

import cw

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


def diff(run_id, *, baseline=None, store=None):
    """Diff an analyzed run against a prior baseline run (own-target review mode)."""
    from .analysis.diff import build_diff
    from .capture.stores import resolve_store

    s = resolve_store(store)
    try:
        run = s.load_run(run_id)
    except (KeyError, ValueError) as e:
        yield f"error: could not load run {run_id!r}: {e}"
        yield "run `ov runs` to list available run ids"
        return
    d = build_diff(run, baseline=baseline, store=s)
    if d is None:
        yield "no prior baseline run found for this target; nothing to diff"
        return
    yield f"baseline: {d.baseline_run_id}"
    c = d.counts
    yield (
        f"findings: {c['new']} new · {c['changed']} changed · "
        f"{c['resolved']} resolved · {c['unchanged']} unchanged"
    )
    if d.tech_added or d.tech_removed:
        yield f"tech: +{d.tech_added or '[]'} -{d.tech_removed or '[]'}"
    if d.endpoints_added or d.endpoints_removed:
        yield f"endpoints: +{len(d.endpoints_added)} -{len(d.endpoints_removed)}"
    if d.rendering_model_change:
        yield f"rendering model: {d.rendering_model_change['from']} -> {d.rendering_model_change['to']}"
    if d.source_maps_change:
        yield f"source maps: {d.source_maps_change['from']} -> {d.source_maps_change['to']}"


def report(run_id, *, sections="default", out_dir=None, store=None):
    """Render Markdown report sections for a stored run (Phase 2)."""
    paths = _ov.report(run_id, sections=sections, out_dir=out_dir, store=store)
    for p in paths:
        yield str(p)


def synopsis(run_id, *, out=None, store=None):
    """Aggregate a run's findings into a single synopsis (synopsis.json + SYNOPSIS.md)."""
    yield str(_ov.synopsis(run_id, out=out, store=store))


def overview(
    url,
    *,
    headed=False,
    mode="reconstruct",
    out_dir=None,
    store=None,
    authorized=False,
    baseline=None,
):
    """observe -> analyze -> [diff in review mode] -> report -> synopsis (Phase 2)."""
    yield str(
        _ov.overview(
            url,
            headed=headed,
            mode=mode,
            out_dir=out_dir,
            store=store,
            authorized=authorized,
            baseline=baseline,
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


# The commands the CLI dispatches, in help order. Named so a test can assert
# on the list itself rather than re-deriving it from the parser.
COMMANDS = [
    observe,
    analyze,
    diff,
    report,
    synopsis,
    overview,
    evidence,
    check,
    runs,
    mcp,
]


def main(argv=None):
    """Entry point for the ``ov`` console script.

    Returns the exit code. ``cw.run`` returns it rather than exiting, so the
    console-script shim (which does ``sys.exit(main())``) and the ``__main__``
    guard below are what turn it into a process exit status.
    """
    parser = cw.mk_parser(
        COMMANDS, prog="ov", description="OverView: web reconnaissance & analysis"
    )
    return cw.run(parser, argv)


if __name__ == "__main__":
    raise SystemExit(main())
