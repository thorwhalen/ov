# ov.operate

The operate layer – deterministic, LLM-free tool primitives (the “hands”).

This is the package-owned *tool plane* from §2.3. It composes as
`journal(progress(act(observe())))` and contains no model and no policy: it
perceives affordances, executes actions, records the journey, and reports
loop/no-progress *facts*. The decision of *what to do next* and *when to stop*
belongs to the policy plane – the host (Claude Code) via the `ov-operate`
skill, or, later, an in-package agent.

Primitives (each is individually callable and testable):

* `observe()` – `observe(page, strategy) -> Observation`
* `act()` – `act(page, action) -> ActionResult` (returns a fresh Observation)
* `journal()` – append a structured per-step record
* `progress()` – loop/no-progress facts (never decides to stop)
* perception strategies – [`PERCEPTION_REGISTRY`](ov.operate.perception.html.md#ov.operate.perception.PERCEPTION_REGISTRY)

### Functions

| [`observe`](#ov.operate.observe)(page[, strategy])                          | Perceive the current page state with `strategy` and return an Observation.   |
|-----------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------|
| [`act`](#ov.operate.act)(page, action, \*[, perception, polite_rate_s]) | Execute `action` against `page` and return the result + a fresh Observation. |
| [`journal`](#ov.operate.journal)(run, step)                                 | Append `step` to `run.steps` and return it.                                  |
| [`make_step`](#ov.operate.make_step)(\*, intent[, action, ...])               | Build a `JourneyStep` from an action's before/after observations.            |
| [`progress`](#ov.operate.progress)(history, \*[, no_progress_steps])         | Compute loop/no-progress facts from the journey `history` so far.            |
| [`perceive`](#ov.operate.perceive)(page[, strategy])                         | Dispatch to the named perception strategy (defaults to `ax_snapshot`).       |

### ov.operate.act(page, action, , perception='ax_snapshot', polite_rate_s=0.0)

Execute `action` against `page` and return the result + a fresh Observation.

On failure, `ok=False` and `error` carries the message; a fresh
Observation is still attached so the host can recover (re-observe, scroll,
disambiguate).

* **Return type:**
  [`ActionResult`](ov.base.html.md#ov.base.ActionResult)

### ov.operate.journal(run, step)

Append `step` to `run.steps` and return it.

* **Return type:**
  [`JourneyStep`](ov.base.html.md#ov.base.JourneyStep)

### ov.operate.make_step(, intent, action=None, pre_observation=None, result=None, artifact_ids=None, network_delta=0, console_delta=0, note=None)

Build a `JourneyStep` from an action’s before/after observations.

`outcome` is derived: `error` on a failed action, `noop` when the
post-observation hash equals the pre-observation hash (nothing changed),
else `ok`.

* **Return type:**
  [`JourneyStep`](ov.base.html.md#ov.base.JourneyStep)

### ov.operate.observe(page, strategy='ax_snapshot')

Perceive the current page state with `strategy` and return an Observation.

```pycon
>>> from ov.operate.perception import PERCEPTION_REGISTRY
>>> "ax_snapshot" in PERCEPTION_REGISTRY
True
```

* **Return type:**
  [`Observation`](ov.base.html.md#ov.base.Observation)

### ov.operate.perceive(page, strategy='ax_snapshot')

Dispatch to the named perception strategy (defaults to `ax_snapshot`).

Raises `KeyError` with the known strategies when `strategy` is unknown –
an informative error per the project’s principles.

* **Return type:**
  [`Observation`](ov.base.html.md#ov.base.Observation)

### ov.operate.progress(history, , no_progress_steps=3)

Compute loop/no-progress facts from the journey `history` so far.

```pycon
>>> from ov.base import JourneyStep, Action
>>> s = JourneyStep(action=Action(type='click', ref='e1'), post_obs_hash='h')
>>> sig = progress([s, s.model_copy(), s.model_copy()], no_progress_steps=3)
>>> sig.no_new_signal_steps >= 3 and sig.loop_suspected
True
```

* **Return type:**
  [`ProgressSignal`](ov.base.html.md#ov.base.ProgressSignal)

### Modules

| [`driver`](ov.operate.driver.html.md#module-ov.operate.driver)         | The scripted/guided driver -- model-free journey execution (Phase 1).         |
|------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------|
| [`perception`](ov.operate.perception.html.md#module-ov.operate.perception) | Perception strategies -- pluggable ways to turn a page into an `Observation`. |
| [`strategies`](ov.operate.strategies.html.md#module-ov.operate.strategies) | Journey-strategy helpers -- intent shaping for the three strategies (§2.3).   |
