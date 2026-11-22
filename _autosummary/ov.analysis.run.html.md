# ov.analysis.run

The analysis orchestrator – resolve, order, run analyzers, merge into the run.

`run_analysis` is what [`ov.analyze()`](ov.html.md#ov.analyze) calls. It selects analyzers by lens,
orders them by their `requires`/`produces` dependencies, runs each over an
[`AnalysisContext`](ov.analysis.context.html.md#ov.analysis.context.AnalysisContext), and merges every
[`AnalyzerOutput`](ov.analysis.context.html.md#ov.analysis.context.AnalyzerOutput) back into the `CaptureRun`
(findings, endpoints, tech, run fields). It is model-free and idempotent: it
clears prior analysis output before re-running so a run can be re-analyzed.

### Functions

| [`merge_output`](#ov.analysis.run.merge_output)(run, out)                         | Merge one analyzer's output into the run (findings, endpoints, tech, fields).           |
|-------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| [`run_analysis`](#ov.analysis.run.run_analysis)(run, \*[, lenses, store, config]) | Run the deterministic analyzers for `lenses` over a run; return per-analyzer summaries. |

### ov.analysis.run.merge_output(run, out)

Merge one analyzer’s output into the run (findings, endpoints, tech, fields).

Tech dedupes by name: confidence takes the max, provenance and categories
union (so a package seen both as a recovered dependency and by framework/bundler
signature keeps *both* category identities), and a missing version is filled
from any analyzer that supplies one (source-map versions are the top provenance
rank, so they must not be lost to an earlier versionless detection).

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### ov.analysis.run.run_analysis(run, , lenses=('ux', 'arch'), store=None, config=None)

Run the deterministic analyzers for `lenses` over a run; return per-analyzer summaries.

`run` may be a `CaptureRun` or a run id (loaded from `store`). The
run is mutated in place (findings/api_surface/fingerprint/rendering_model/…)
and persisted; an analysis blob is also stored.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]
