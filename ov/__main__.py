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


def observe(url, *, headed=False, probes="default", mode="reconstruct", crawl_pages: int = 1, store=None, authorized=False):
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


def synopsis(reports_dir, *, out=None, store=None):
    """Aggregate reports into a single synopsis (Phase 2)."""
    yield str(_ov.synopsis(reports_dir, out=out, store=store))


def overview(url, *, headed=False, mode="reconstruct", out_dir=None, store=None, authorized=False):
    """observe -> analyze -> report -> synopsis, the one-liner (Phase 2)."""
    yield str(_ov.overview(url, headed=headed, mode=mode, out_dir=out_dir, store=store, authorized=authorized))


def check():
    """Check system dependencies (Playwright browsers, Node, sidecar, CLIs)."""
    rep = _check_requirements(verbose=False)
    yield rep.render()


def runs(*, store=None):
    """List stored capture run ids."""
    s = CaptureStore(store)
    for rid in s.run_ids():
        yield rid


def main(argv=None):
    """Entry point for the ``ov`` console script."""
    parser = argh.ArghParser(prog="ov", description="OverView: web reconnaissance & analysis")
    argh.add_commands(parser, [observe, analyze, report, synopsis, overview, check, runs])
    parser.dispatch(argv=argv)


if __name__ == "__main__":
    main()
