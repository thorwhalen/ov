"""The ``overview`` one-liner: observe -> analyze -> report -> synopsis (§4).

This is the pit-of-success entry point behind :func:`ov.overview`. It threads a
single store through capture, the deterministic analyzers, report rendering, and
the synopsis, returning the synopsis path/key. No model is involved.
"""

from __future__ import annotations

from typing import Any

from ..capture.stores import resolve_store


def run_overview(
    url: str,
    *,
    headed: bool = False,
    mode: str = "reconstruct",
    probes: Any = "default",
    store: Any = None,
    out_dir: Any = None,
    authorized: bool | None = None,
    lenses: tuple[str, ...] = ("ux", "arch"),
    **observe_kw: Any,
) -> str:
    """Run the full deterministic pipeline and return the synopsis path/key."""
    import ov

    from ..analysis.run import run_analysis
    from .render import render_reports
    from .synopsis import build_synopsis

    store = resolve_store(store)
    run = ov.observe(
        url,
        headed=headed,
        mode=mode,
        probes=probes,
        store=store,
        authorized=authorized,
        **observe_kw,
    )
    run_analysis(run, lenses=lenses, store=store)
    render_reports(run, out_dir=out_dir, store=store)
    return build_synopsis(run, out=out_dir, store=store)
