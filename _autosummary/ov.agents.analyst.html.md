# ov.agents.analyst

The Analyst agents (UX + Arch) — grounded judgment over an evidence bundle.

The hard architectural seam (§8.1, D4): **analysts never touch the live browser.**
They consume a *deterministic, model-free* evidence bundle — marked screenshots +
derived facts + a cite-or-abstain contract — and add narrative judgment on top. The
package supplies three reused-unchanged pieces and the agent wires them:

1. [`build_evidence_bundle()`](ov.analysis.evidence.html.md#ov.analysis.evidence.build_evidence_bundle) assembles the bundle (Set-of-
   Mark regions, computed token budget);
2. the injected `judge` (an LLM under the cite-or-abstain contract) returns
   candidate `Finding`s (``source_layer="llm"``);
3. [`verify_findings()`](ov.analysis.reliability.html.md#ov.analysis.reliability.verify_findings) gates them — any claim without a
   *resolvable* evidence ref (or referencing an unknown mark) is \*\*downgraded to

   ```
   ``
   ```

   undetermined\`\`\*\*, never silently dropped.

So the model interprets; it never authors facts. The judge is injected (DI), so the
agent is unit-testable with a stub that returns canned findings — no API call, no
vision model. UX routes to Sonnet, Arch to Opus (§10). Satisfies `aw.AgenticStep`.

### Module Attributes

| [`Judge`](#ov.agents.analyst.Judge)   | A judge maps an evidence bundle to candidate findings (dicts or Findings).   |
|----------------------------------------------------------|------------------------------------------------------------------------------|

### Functions

| [`arch_analyst`](#ov.agents.analyst.arch_analyst)([llm])   | A software-architecture analyst (Opus-routed).   |
|------------------------------------------------------------------------|--------------------------------------------------|
| [`ux_analyst`](#ov.agents.analyst.ux_analyst)([llm])     | A UX/accessibility analyst (Sonnet-routed).      |

### Classes

| [`AnalystAgent`](#ov.agents.analyst.AnalystAgent)(lens[, llm, judge, model, ...])   | Interpret a captured run's evidence bundle into grounded findings (UX or Arch).   |
|-------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------|

### *class* ov.agents.analyst.AnalystAgent(lens, llm=None, judge=None, model=None, max_marks=20, task=None, name='')

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Interpret a captured run’s evidence bundle into grounded findings (UX or Arch).

* **Parameters:**
  * **lens** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – `"ux"` or `"arch"` — selects default model + finding defaults.
  * **llm** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – the injected LLM (a callable, an object exposing `structured` for the
    multimodal path, an `aw` `StepConfig`, or `None`). Ignored if a
    `judge` is given.
  * **judge** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis), [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)]]) – `(bundle, *, run, store) -> list[Finding | dict]`. Override the whole
    LLM step (tests, alternative providers). Defaults to `_default_judge()`.
  * **model** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]) – model selector for the image-budget + info (defaults from the lens).
  * **max_marks** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – cap on Set-of-Mark regions in the bundle.

#### execute(input_data, context=None)

Analyze a run (or a prebuilt bundle) → `(verified_findings, info)` (aw protocol).

`input_data` may be a [`CaptureRun`](ov.base.html.md#ov.base.CaptureRun), an
[`EvidenceBundle`](ov.base.html.md#ov.base.EvidenceBundle), or a mapping carrying `run` / `store` /
`bundle`. The verified LLM findings are appended to `run.findings` (additive
— `source_layer` keeps them distinct from deterministic facts) and returned.

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Finding`](ov.base.html.md#ov.base.Finding)], [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]]

### ov.agents.analyst.Judge

A judge maps an evidence bundle to candidate findings (dicts or Findings).

alias of `Callable`[[…], [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)]

### ov.agents.analyst.arch_analyst(llm=None, \*\*kwargs)

A software-architecture analyst (Opus-routed). `llm` is the injected model.

```pycon
>>> arch_analyst().model
'opus'
```

* **Return type:**
  [`AnalystAgent`](#ov.agents.analyst.AnalystAgent)

### ov.agents.analyst.ux_analyst(llm=None, \*\*kwargs)

A UX/accessibility analyst (Sonnet-routed). `llm` is the injected model.

```pycon
>>> a = ux_analyst()
>>> a.lens, a.model, a.name
('ux', 'sonnet', 'ux-analyst')
```

* **Return type:**
  [`AnalystAgent`](#ov.agents.analyst.AnalystAgent)
