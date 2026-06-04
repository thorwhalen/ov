"""Render Markdown report sections from an analyzed run (§8.3).

Selects the registered sections that apply to the run's mode, orders them by their
numeric ``order``, renders each over the run + per-analyzer summaries, and writes
them to the store (and optionally an output directory). Returns the written keys
or paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..base import CaptureRun
from ..capture.stores import resolve_store
from . import REPORT_SECTION_REGISTRY, load_builtin_sections


def _resolve_run(run_or_id: Any, store: Any) -> CaptureRun:
    if isinstance(run_or_id, CaptureRun):
        return run_or_id
    if isinstance(run_or_id, str):
        return store.load_run(run_or_id)
    raise TypeError(f"expected a CaptureRun or run id, got {type(run_or_id).__name__}")


def _load_analyses(store: Any, run_id: str) -> dict[str, Any]:
    try:
        blob = store.load_analysis(f"analysis_{run_id}")
        return blob.get("results", {})
    except KeyError:
        return {}


def render_reports(
    run_or_analyses: Any,
    *,
    sections: Any = "default",
    out_dir: Any = None,
    store: Any = None,
) -> list[str]:
    """Render and persist the report sections; return their store keys/paths."""
    load_builtin_sections()
    store = resolve_store(store)
    run = _resolve_run(run_or_analyses, store)
    analyses = _load_analyses(store, run.run_id)

    items = list(REPORT_SECTION_REGISTRY.items.values())
    items.sort(key=lambda it: it.meta.get("order", 999))

    if sections not in ("default", "all", None):
        wanted = {sections} if isinstance(sections, str) else set(sections)
        items = [it for it in items if it.name in wanted]
    else:
        items = [it for it in items if run.mode in it.meta.get("modes", ("reconstruct", "review"))]

    out_paths: list[str] = []
    out_dir_path = Path(out_dir) if out_dir else None
    if out_dir_path:
        out_dir_path.mkdir(parents=True, exist_ok=True)

    for it in items:
        try:
            md = it.fn(run, analyses)
        except Exception as e:  # noqa: BLE001 - a bad section must not abort the rest
            md = f"# {it.name}\n\n_section failed: {type(e).__name__}: {e}_"
            run.notes.append(f"section {it.name} failed: {e}")
        filename = f"{it.name}.md"
        key = store.save_report(run.run_id, filename, md)
        if out_dir_path:
            path = out_dir_path / filename
            path.write_text(md, encoding="utf-8")
            out_paths.append(str(path))
        else:
            out_paths.append(key)
    return out_paths
