# ov.agents.orchestrator

The Orchestrator — a *pure coordinator* over the study pipeline (`aw` workflow).

The orchestrator plans and delegates; it does **not** analyze (plan quality degrades
when the planner also does the work — §7). It sequences the study the `study-web-app`
skill describes — capture → deterministic analysis → (optional) analyst judgment →
report → synopsis — by chaining 

```
``
```

aw.AgenticStep\`\`s through an `aw.AgenticWorkflow`
with the [`CaptureRun`](ov.base.html.md#ov.base.CaptureRun) as the shared SSOT in the workflow context.

Two design properties carry the spec’s intent:

* **Host-is-the-manager stays the default.** With no `llm` injected the pipeline is
  fully deterministic (capture + analyzers + report + synopsis) — the analyst agents
  are *additive* and only run when a model is supplied. The cheap path is the default.
* **Everything is injected.** Each stage (capture / analyze / report / synopsis) is a
  swappable callable defaulting to the real `ov` facade, so the coordination logic
  is unit-testable with fakes — no browser, no model — while the defaults wire the
  genuine end-to-end study.

### Functions

| [`study`](#ov.agents.orchestrator.study)(url, \*[, llm, lenses])   | Run an end-to-end study of `url` (the in-package twin of the `study-web-app` skill).   |
|----------------------------------------------------------------------------------|----------------------------------------------------------------------------------------|

### Classes

| [`Orchestrator`](#ov.agents.orchestrator.Orchestrator)([llm, lenses, out_dir, store, ...])   | Coordinate a full study, delegating each stage (never analyzing itself).       |
|-----------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------|
| [`OrchestratorResult`](#ov.agents.orchestrator.OrchestratorResult)(run[, synopsis, reports, ...])  | What a study produced: the run, the synopsis, report paths, and step metadata. |

### *class* ov.agents.orchestrator.Orchestrator(llm=None, lenses=('ux', 'arch'), out_dir=None, store=None, capture_fn=<function \_default_capture>, analyze_fn=<function \_default_analyze>, report_fn=<function \_default_report>, synopsis_fn=<function \_default_synopsis>, capture_kwargs=dict())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Coordinate a full study, delegating each stage (never analyzing itself).

* **Parameters:**
  * **llm** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – the injected model for the analyst agents. `None` → deterministic-only
    study (the host-is-manager default; analysts are skipped).
  * **lenses** ([`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)) – which analysis lenses to run (`"ux"` and/or `"arch"`).
  * **out_dir** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – where reports + synopsis are written (`None` → the run’s store).
  * **synopsis_fn** ([`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)) – stage seams (default to the
    real `ov` facade). Inject fakes to unit-test the coordination.
  * **capture_kwargs** ([`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)) – extra kwargs forwarded to `capture_fn` (e.g. `mode`,
    `authorized`, `crawl_pages`, `journey`).

#### run(url)

Run the full study for `url` and return an [`OrchestratorResult`](#ov.agents.orchestrator.OrchestratorResult).

* **Return type:**
  [`OrchestratorResult`](#ov.agents.orchestrator.OrchestratorResult)

### *class* ov.agents.orchestrator.OrchestratorResult(run, synopsis=None, reports=list(), workflow=dict())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

What a study produced: the run, the synopsis, report paths, and step metadata.

### ov.agents.orchestrator.study(url, , llm=None, lenses=('ux', 'arch'), \*\*kwargs)

Run an end-to-end study of `url` (the in-package twin of the `study-web-app` skill).

The pit-of-success one-liner: capture → analyze → (optional analyst judgment) →
report → synopsis. With `llm=None` it is fully deterministic; pass an injected
model to add grounded UX/Arch narrative. Forwards `mode` / `authorized` /
`crawl_pages` / `out_dir` / stage seams via `**kwargs`.

* **Return type:**
  [`OrchestratorResult`](#ov.agents.orchestrator.OrchestratorResult)
