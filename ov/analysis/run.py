"""The analysis orchestrator -- resolve, order, run analyzers, merge into the run.

``run_analysis`` is what :func:`ov.analyze` calls. It selects analyzers by lens,
orders them by their ``requires``/``produces`` dependencies, runs each over an
:class:`~ov.analysis.context.AnalysisContext`, and merges every
:class:`~ov.analysis.context.AnalyzerOutput` back into the :class:`CaptureRun`
(findings, endpoints, tech, run fields). It is model-free and idempotent: it
clears prior analysis output before re-running so a run can be re-analyzed.
"""

from __future__ import annotations

from typing import Any, Iterable

from ..base import CaptureRun
from ..capture.stores import resolve_store
from ..config import OvConfig
from . import ANALYZER_REGISTRY, load_builtin_analyzers
from .context import AnalysisContext, AnalyzerOutput


def merge_output(run: CaptureRun, out: AnalyzerOutput) -> None:
    """Merge one analyzer's output into the run (findings, endpoints, tech, fields)."""
    run.findings.extend(out.findings)
    run.api_surface.extend(out.endpoints)
    by_name = {t.name: t for t in run.fingerprint}
    for t in out.tech:
        existing = by_name.get(t.name)
        if existing is None:
            run.fingerprint.append(t)
            by_name[t.name] = t
        else:
            existing.confidence = max(existing.confidence, t.confidence)
            for p in t.provenance:
                if p not in existing.provenance:
                    existing.provenance.append(p)
    for field, value in out.run_fields.items():
        setattr(run, field, value)


def run_analysis(
    run: CaptureRun | str,
    *,
    lenses: Iterable[str] = ("ux", "arch"),
    store: Any = None,
    config: OvConfig | None = None,
) -> dict[str, Any]:
    """Run the deterministic analyzers for ``lenses`` over a run; return per-analyzer summaries.

    ``run`` may be a :class:`CaptureRun` or a run id (loaded from ``store``). The
    run is mutated in place (findings/api_surface/fingerprint/rendering_model/...)
    and persisted; an analysis blob is also stored.
    """
    load_builtin_analyzers()
    store = resolve_store(store)
    if isinstance(run, str):
        run = store.load_run(run)
    lenses = tuple(lenses)

    # Idempotency: clear prior analysis output so re-analysis doesn't duplicate.
    run.findings = []
    run.api_surface = []

    ctx = AnalysisContext(run=run, store=store, config=config or OvConfig.from_env())
    selected = [name for name, item in ANALYZER_REGISTRY.items.items() if item.meta.get("lens") in lenses]

    results: dict[str, Any] = {}
    for item in ANALYZER_REGISTRY.ordered(selected):
        try:
            out = item.fn(ctx)
        except Exception as e:  # noqa: BLE001 - one analyzer must not abort the rest
            run.notes.append(f"analyzer {item.name} failed: {type(e).__name__}: {e}")
            continue
        merge_output(run, out)
        results[item.name] = out.summary

    store.save_run(run)
    store.save_analysis(
        f"analysis_{run.run_id}",
        {
            "run_id": run.run_id,
            "lenses": list(lenses),
            "results": results,
            "findings": [f.model_dump(mode="json") for f in run.findings],
            "api_surface": [e.model_dump(mode="json") for e in run.api_surface],
        },
    )
    return results
