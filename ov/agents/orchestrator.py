"""The Orchestrator — a *pure coordinator* over the study pipeline (``aw`` workflow).

The orchestrator plans and delegates; it does **not** analyze (plan quality degrades
when the planner also does the work — §7). It sequences the study the ``study-web-app``
skill describes — capture → deterministic analysis → (optional) analyst judgment →
report → synopsis — by chaining ``aw.AgenticStep``s through an :class:`aw.AgenticWorkflow`
with the :class:`~ov.base.CaptureRun` as the shared SSOT in the workflow context.

Two design properties carry the spec's intent:

* **Host-is-the-manager stays the default.** With no ``llm`` injected the pipeline is
  fully deterministic (capture + analyzers + report + synopsis) — the analyst agents
  are *additive* and only run when a model is supplied. The cheap path is the default.
* **Everything is injected.** Each stage (capture / analyze / report / synopsis) is a
  swappable callable defaulting to the real ``ov`` facade, so the coordination logic
  is unit-testable with fakes — no browser, no model — while the defaults wire the
  genuine end-to-end study.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

from ._util import require
from .analyst import arch_analyst, ux_analyst


def _call(fn: Callable, *args: Any, store: Any = None, **kwargs: Any) -> Any:
    """Call ``fn(*args, **kwargs)``, forwarding ``store`` only if ``fn`` accepts it.

    Lets the real ``ov`` facade stages receive the shared ``store`` (so the whole
    pipeline reads/writes one store) while injected test/alternative stages that take
    no ``store`` keyword still work unchanged.
    """
    try:
        params = inspect.signature(fn).parameters
        takes_store = "store" in params or any(
            p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()
        )
    except (TypeError, ValueError):  # builtins / C funcs without a signature
        takes_store = False
    if takes_store and store is not None:
        kwargs["store"] = store
    return fn(*args, **kwargs)


@dataclass
class OrchestratorResult:
    """What a study produced: the run, the synopsis, report paths, and step metadata."""

    run: Any
    synopsis: Any = None
    reports: list = field(default_factory=list)
    workflow: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Pipeline stages — each a tiny aw.AgenticStep over the shared run (SSOT)
# --------------------------------------------------------------------------- #


@dataclass
class _CaptureStep:
    capture_fn: Callable
    kwargs: dict
    store: Any = None
    name: str = "capture"

    def execute(self, url: Any, context):
        run = _call(self.capture_fn, url, store=self.store, **self.kwargs)
        context["run"] = run
        return run, {
            "success": True,
            "agent": self.name,
            "run_id": getattr(run, "run_id", None),
        }


@dataclass
class _AnalyzeStep:
    analyze_fn: Callable
    lenses: tuple
    store: Any = None
    name: str = "analyze"

    def execute(self, run: Any, context):
        run = context.get("run", run)
        analyses = _call(self.analyze_fn, run, store=self.store, lenses=self.lenses)
        context["analyses"] = analyses
        return run, {"success": True, "agent": self.name, "lenses": list(self.lenses)}


@dataclass
class _AnalystStep:
    analyst: Any  # an AnalystAgent

    @property
    def name(self) -> str:
        return self.analyst.name

    def execute(self, run: Any, context):
        run = context.get("run", run)
        _, info = self.analyst.execute(run, context)
        return run, info


@dataclass
class _ReportStep:
    report_fn: Callable
    out_dir: Any
    store: Any = None
    name: str = "report"

    def execute(self, run: Any, context):
        run = context.get("run", run)
        paths = _call(self.report_fn, run, store=self.store, out_dir=self.out_dir)
        context["reports"] = list(paths or [])
        return run, {
            "success": True,
            "agent": self.name,
            "n_reports": len(context["reports"]),
        }


@dataclass
class _SynopsisStep:
    synopsis_fn: Callable
    out_dir: Any
    store: Any = None
    name: str = "synopsis"

    def execute(self, run: Any, context):
        run = context.get("run", run)
        source = context.get("reports") or run
        synopsis = _call(self.synopsis_fn, source, store=self.store, out=self.out_dir)
        context["synopsis"] = synopsis
        return run, {"success": True, "agent": self.name}


# --------------------------------------------------------------------------- #
# The coordinator
# --------------------------------------------------------------------------- #


def _default_capture(url, *, store=None, **kw):
    import ov

    return ov.observe(url, store=store, **kw)


def _default_analyze(run, *, lenses, store=None):
    import ov

    return ov.analyze(run, lenses=lenses, store=store)


def _default_report(run, *, out_dir, store=None):
    import ov

    return ov.report(run, out_dir=out_dir, store=store)


def _default_synopsis(source, *, out, store=None):
    import ov

    return ov.synopsis(source, out=out, store=store)


@dataclass
class Orchestrator:
    """Coordinate a full study, delegating each stage (never analyzing itself).

    Args:
        llm: the injected model for the analyst agents. ``None`` → deterministic-only
            study (the host-is-manager default; analysts are skipped).
        lenses: which analysis lenses to run (``"ux"`` and/or ``"arch"``).
        out_dir: where reports + synopsis are written (``None`` → the run's store).
        capture_fn / analyze_fn / report_fn / synopsis_fn: stage seams (default to the
            real ``ov`` facade). Inject fakes to unit-test the coordination.
        capture_kwargs: extra kwargs forwarded to ``capture_fn`` (e.g. ``mode``,
            ``authorized``, ``crawl_pages``, ``journey``).
    """

    llm: Any = None
    lenses: tuple = ("ux", "arch")
    out_dir: Any = None
    store: Any = None
    capture_fn: Callable = _default_capture
    analyze_fn: Callable = _default_analyze
    report_fn: Callable = _default_report
    synopsis_fn: Callable = _default_synopsis
    capture_kwargs: dict = field(default_factory=dict)

    def _resolved_store(self) -> Any:
        """The one concrete store the whole pipeline shares.

        An explicit ``store`` wins. Otherwise, on the *real* capture path resolve the
        default store so the analyzers + analysts read the same artifacts capture
        wrote; with injected (fake) stages it stays ``None`` (no filesystem touch).
        """
        if self.store is not None:
            return self.store
        if self.capture_fn is _default_capture:
            from ..capture.stores import resolve_store

            return resolve_store(None)
        return None

    def _build_steps(self, store: Any) -> list[tuple[str, Any]]:
        """Assemble the ordered pipeline; analyst steps appear only when an llm is set.

        The one ``store`` is threaded through every stage so capture, the analyzers,
        the report and the synopsis all read/write the *same* artifact store.
        """
        steps: list[tuple[str, Any]] = [
            (
                "capture",
                _CaptureStep(self.capture_fn, dict(self.capture_kwargs), store),
            ),
            ("analyze", _AnalyzeStep(self.analyze_fn, tuple(self.lenses), store)),
        ]
        if self.llm is not None:
            if "ux" in self.lenses:
                steps.append(("ux-analyst", _AnalystStep(ux_analyst(self.llm))))
            if "arch" in self.lenses:
                steps.append(("arch-analyst", _AnalystStep(arch_analyst(self.llm))))
        steps.append(("report", _ReportStep(self.report_fn, self.out_dir, store)))
        steps.append(("synopsis", _SynopsisStep(self.synopsis_fn, self.out_dir, store)))
        return steps

    def run(self, url: str) -> OrchestratorResult:
        """Run the full study for ``url`` and return an :class:`OrchestratorResult`."""
        (aw,) = require("aw", feature="ov.agents.Orchestrator")
        store = self._resolved_store()
        context = aw.Context({"url": url, "store": store})
        workflow = aw.AgenticWorkflow(context)
        for name, step in self._build_steps(store):
            workflow.add_step(name, step)
        run, meta = workflow.run(url)
        return OrchestratorResult(
            run=context.get("run", run),
            synopsis=context.get("synopsis"),
            reports=context.get("reports", []),
            workflow=meta,
        )


def study(
    url: str, *, llm: Any = None, lenses: Iterable[str] = ("ux", "arch"), **kwargs: Any
) -> OrchestratorResult:
    """Run an end-to-end study of ``url`` (the in-package twin of the ``study-web-app`` skill).

    The pit-of-success one-liner: capture → analyze → (optional analyst judgment) →
    report → synopsis. With ``llm=None`` it is fully deterministic; pass an injected
    model to add grounded UX/Arch narrative. Forwards ``mode`` / ``authorized`` /
    ``crawl_pages`` / ``out_dir`` / stage seams via ``**kwargs``.
    """
    field_names = {f for f in Orchestrator.__dataclass_fields__}  # type: ignore[attr-defined]
    config = {k: v for k, v in kwargs.items() if k in field_names}
    capture_kwargs = {k: v for k, v in kwargs.items() if k not in field_names}
    if capture_kwargs:
        config.setdefault("capture_kwargs", {}).update(capture_kwargs)
    return Orchestrator(llm=llm, lenses=tuple(lenses), **config).run(url)
