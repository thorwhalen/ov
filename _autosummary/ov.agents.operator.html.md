# ov.agents.operator

The Operator agent — the model-bound perceive→decide→act→record loop.

In Phases 1–3 the *host* plays the operator, following the `ov-operate` skill: it
reads affordances, decides the next action, and records intent. Phase 4 packages that
loop as a runnable agent. The deterministic “hands” (`observe` / `act` /
`make_step` / `journal` / `progress`) are reused unchanged; the only thing the
agent adds is the **decide** step — and that is *injected* (`decider`), so:

* the package never hard-depends on an LLM (the host, a script, or a model can all
  supply `decide`); and
* the loop is unit-testable with a trivial decider and fake `observe`/`act`
  callables — no browser, no API call.

The agent satisfies the `aw.AgenticStep` protocol structurally
(`execute(input_data, context) -> (artifact, info)`), so it drops into an `aw`
workflow (see [`ov.agents.orchestrator`](ov.agents.orchestrator.html.md#module-ov.agents.orchestrator)). Its artifact is the populated
[`CaptureRun`](ov.base.html.md#ov.base.CaptureRun); the model-free [`progress()`](ov.operate.html.md#ov.operate.progress) facts are
the deterministic stop signal a budget-bound manager interprets.

### Module Attributes

| [`Decider`](#ov.agents.operator.Decider)   | A decider maps the current observation (+ goal + history) to the next action, or `None` to stop.   |
|------------------------------------------------------------|----------------------------------------------------------------------------------------------------|

### Functions

| [`make_llm_decider`](#ov.agents.operator.make_llm_decider)([llm, instruction])   | A model-backed [`Decider`](#ov.agents.operator.Decider) that picks the next [`Action`](ov.base.html.md#ov.base.Action).   |
|-----------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|

### Classes

| [`OperatorAgent`](#ov.agents.operator.OperatorAgent)(decider[, session, max_steps, ...])   | Drive a target toward a goal, recording every step (an `aw.AgenticStep`).   |
|------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------|

### ov.agents.operator.Decider

A decider maps the current observation (+ goal + history) to the next action,
or `None` to stop. The model’s only job in the loop.

alias of `Callable`[[…], [`Action`](ov.base.html.md#ov.base.Action) | [`None`](https://docs.python.org/3/builtins/constants.html#None)]

### *class* ov.agents.operator.OperatorAgent(decider, session=None, max_steps=12, strategy='ax_snapshot', polite_rate_s=0.0, no_progress_steps=3, observe_fn=None, act_fn=None, model='haiku', name='operator')

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Drive a target toward a goal, recording every step (an `aw.AgenticStep`).

* **Parameters:**
  * **decider** ([`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis), [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Action`](ov.base.html.md#ov.base.Action)]]) – `(observation, *, goal, history) -> Action | None`. Returns the
    next action, or `None` to stop. Use [`make_llm_decider()`](#ov.agents.operator.make_llm_decider) for a
    model-backed one, or any callable (host / script / test stub).
  * **session** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – a [`CaptureSession`](ov.capture.session.html.md#ov.capture.session.CaptureSession) (supplies `.page` +
    `.run`). Optional — `page` and `run` may instead arrive via the
    `context` passed to [`execute()`](#ov.agents.operator.OperatorAgent.execute) (keys `"page"` / `"run"`).
  * **max_steps** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – hard cap on actions (a budget; the deterministic loop signal is
    advisory, the cap is the backstop).
  * **strategy** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – perception strategy for the default `observe` (`"ax_snapshot"`
    | `"screenshot"` | `"hybrid"`).
  * **act_fn** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`Any`](https://docs.python.org/3/library/typing.html#typing.Any), [`Action`](ov.base.html.md#ov.base.Action)], [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]]) – injection seams for the hands (default to the real
    [`observe()`](ov.operate.html.md#ov.operate.observe) / [`act()`](ov.operate.html.md#ov.operate.act)); tests pass fakes.

#### execute(input_data, context=None)

Pursue `input_data` (the goal) and return `(CaptureRun, info)` (aw protocol).

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`CaptureRun`](ov.base.html.md#ov.base.CaptureRun), [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]]

### ov.agents.operator.make_llm_decider(llm=None, , instruction=None)

A model-backed [`Decider`](#ov.agents.operator.Decider) that picks the next [`Action`](ov.base.html.md#ov.base.Action).

Uses the injected `llm` through [`ov.agents.llm.structured()`](ov.agents.llm.html.md#ov.agents.llm.structured) to choose an
action conforming to `Action`’s schema. Returns `None` (stop) when no LLM is
resolvable, on a parse miss, or when the model signals a stop — so an operator
built with this decider degrades safely to a no-op rather than crashing.

* **Return type:**
  [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis), [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Action`](ov.base.html.md#ov.base.Action)]]
