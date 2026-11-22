# ov.analysis.context

The analysis context + analyzer output – the currency of the pure analyzers.

Analyzers are pure functions over captured *artifacts*: they never touch a
browser or a model. [`AnalysisContext`](#ov.analysis.context.AnalysisContext) injects the run + store + config and
gives small helpers for reading artifacts by kind; [`AnalyzerOutput`](#ov.analysis.context.AnalyzerOutput) is
what every analyzer returns, which the orchestrator merges back into the run.

This is the testability seam: feed an analyzer synthetic artifacts and assert on
the :class:

```
`
```

~ov.base.Finding\`s it returns – no network, no browser, no LLM.

### Classes

| [`AnalysisContext`](#ov.analysis.context.AnalysisContext)(run, store[, config, extras])    | Everything an analyzer needs, plus artifact-reading helpers.        |
|---------------------------------------------------------------------------------------------------|---------------------------------------------------------------------|
| [`AnalyzerOutput`](#ov.analysis.context.AnalyzerOutput)([findings, endpoints, tech, ...]) | What an analyzer produces; merged into the run by the orchestrator. |

### *class* ov.analysis.context.AnalysisContext(run, store, config=OvConfig(), extras=dict())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Everything an analyzer needs, plus artifact-reading helpers.

#### artifacts(kind)

All artifacts of `kind` in run order.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Artifact`](ov.base.html.md#ov.base.Artifact)]

#### by_step(kind)

Group artifacts of `kind` by their `step_id`.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None), [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Artifact`](ov.base.html.md#ov.base.Artifact)]]

#### json(artifact)

Parse an artifact’s bytes as JSON (`None` on failure).

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)

#### jsons(kind)

Parse every artifact of `kind` as JSON, dropping unparseable ones.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

#### latest(kind)

The last artifact of `kind` (or `None`).

* **Return type:**
  [`Artifact`](ov.base.html.md#ov.base.Artifact) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### raw(artifact)

Raw bytes for an artifact.

* **Return type:**
  [`bytes`](https://docs.python.org/3/builtins/stdtypes.html#bytes)

#### text(artifact)

Decode an artifact’s bytes as UTF-8 text.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### *class* ov.analysis.context.AnalyzerOutput(findings=list(), endpoints=list(), tech=list(), run_fields=dict(), summary=dict())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

What an analyzer produces; merged into the run by the orchestrator.
