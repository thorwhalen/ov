# ov.analysis

Analysis layer: deterministic analyzers over captured artifacts (Phases 2-3).

Analyzers are registered plugins (`ANALYZER_REGISTRY`) that read a
[`CaptureRun`](ov.base.html.md#ov.base.CaptureRun) plus its store and emit :class:

```
`
```

~ov.base.Finding\`s /
:class:

```
`
```

~ov.base.Endpoint\`s / facts – all model-free and fully testable on
synthetic artifacts. The host (or, later, an in-package agent) adds narrative
judgment *on top* of these via the evidence bundle.

Each analyzer is registered with a `lens` (`"ux"` or `"arch"`) so
`ov.analyze(run, lenses=...)` can select which to run; `requires`/`produces`
order them. The builtins are eagerly imported on first import of this package so
the registry is never half-populated (same robustness rule as the probes).

(The package is named `analysis` rather than `analyze` so it cannot shadow
the `ov.analyze` facade *function*; see `ov/__init__.py`.)

### Functions

| [`load_builtin_analyzers`](#ov.analysis.load_builtin_analyzers)()   | Import builtin analyzer modules so their `@register_analyzer` runs.   |
|-----------------------------------------------------------------------------|-----------------------------------------------------------------------|

### ov.analysis.load_builtin_analyzers()

Import builtin analyzer modules so their `@register_analyzer` runs.

Safe to call repeatedly. Invoked once at the bottom of this module so the
registry is fully populated on import (no order-dependent gaps).

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### Modules

| [`arch`](ov.analysis.arch.html.md#module-ov.analysis.arch)               | Architecture-reconstruction analyzers (§6, D2).                                 |
|---------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| [`context`](ov.analysis.context.html.md#module-ov.analysis.context)         | The analysis context + analyzer output -- the currency of the pure analyzers.   |
| [`diff`](ov.analysis.diff.html.md#module-ov.analysis.diff)               | Own-target diffing: a run vs a stored prior baseline run (review mode, §10).    |
| [`evidence`](ov.analysis.evidence.html.md#module-ov.analysis.evidence)       | The evidence-bundle assembler (§8.1, D4) -- deterministic, model-free.          |
| [`reliability`](ov.analysis.reliability.html.md#module-ov.analysis.reliability) | Reliability passes over findings (§5.2, D4) -- deterministic gates, model-free. |
| [`run`](ov.analysis.run.html.md#module-ov.analysis.run)                 | The analysis orchestrator -- resolve, order, run analyzers, merge into the run. |
| [`ux`](ov.analysis.ux.html.md#module-ov.analysis.ux)                   | UX + accessibility deterministic analyzers (§5.1, D3).                          |
