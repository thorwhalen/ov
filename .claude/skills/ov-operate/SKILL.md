---
name: ov-operate
description: >-
  How to drive a web app with ov's operate primitives — read affordances, choose and
  execute the next action, log per-step intent, and detect no-progress. Load this when
  you (the host) are driving a journey: crawling, pursuing a goal (signup/checkout),
  or replaying a script, and need the perceive→decide→act→record loop.
coact:
  model: haiku
  tools: [Bash, Read, Grep, Glob]
  memory: project
  consumes: goal
  returns:
    json_schema:
      type: object
      properties:
        run_id: { type: string }
        steps_taken: { type: integer }
        stopped_reason: { type: string }
        goal_achieved: { type: boolean }
      required: [run_id, steps_taken, stopped_reason]
    description: >-
      Outcome of the drive — the journey is recorded into the CaptureRun; this is
      the compact summary a manager consumes. Throughput-bound (many steps), so
      Haiku-routed (cost gate, §10).
---

# Driving a target with `ov.operate`

The operate layer is the deterministic, model-free **hands**. It composes as
`journal(progress(act(observe())))`. You supply the *decide* step (which action
advances the goal) and the *stop* decision — the package only reports facts.

## The primitives
```python
from ov.operate import observe, act, journal, make_step, progress
from ov.base import Action

obs = observe(session.page)  # -> Observation: affordances {ref, role, name, bbox, ...}
res = act(session.page, Action(type="click", ref="e7", description="Sign up"))
# -> ActionResult: ok/error + a FRESH Observation
step = make_step(intent="advance", action=res.action, pre_observation=obs, result=res)
journal(run, step)  # append the structured per-step record
sig = progress(run.steps)  # -> ProgressSignal: loop/no-progress FACTS
```
- `observe(page, strategy)` — strategies: `ax_snapshot` (cheap default), `screenshot`
  (pixels/bbox, for canvas/exotic UIs), `hybrid` (robust when AX is thin).
- Actions: `click`, `type` (uses `text`), `select` (uses `value`), `navigate`
  (uses `url`), `key`, `scroll`, `wait`. Element actions need a `ref` from the
  current observation **and** a human `description` (safety + legible journal).
- Refs are stamped per observation (`data-ov-ref`); they go stale after navigation —
  re-`observe()` to refresh them.

## Choosing a strategy (the per-step intent)
The three journey strategies differ only in the intent you log:
- **crawl-and-map** (`intent="enumerate"`) — follow links/tabs/menuitems; progress =
  new URLs / new AX subtrees. For a model-free baseline use
  `ov.operate.driver.crawl(session, max_pages=N)`.
- **goal-pursuit** (`intent="advance"`) — *your* loop toward a success predicate.
  No deterministic driver — it needs your judgment.
- **guided-replay** (`intent="replay"`) — `ov.operate.driver.replay(session, actions)`.

## Drive into the hard states (deliberately)
UX bugs concentrate where automation is usually blind:
- **empty**: new account, filtered-to-zero, cleared cart.
- **error**: invalid/blank/oversized input, bad route → 404, wrong credentials.
- **loading/latency**: capture intermediate states.
The UX engine then checks error specificity, field association, and recovery paths.

## Manager discipline (you own this)
- **Bound**: stop at `config.max_steps`, `config.max_failures`, or a wall-clock budget.
- **No-progress**: `progress(history)` returns `loop_suspected`, `no_new_signal_steps`,
  `url_stasis`, `ax_stasis`, `repeated_action`, `repeated_error`. The package detects;
  **you decide to abort.** Abort on `loop_suspected`.
- **Recover** from `ActionResult.error`: stale ref → re-observe; not-found →
  scroll then re-observe; auth/captcha/payment → pause and ask the user.
- After each meaningful state, call `session.capture_step(step)` (or
  `session.snapshot_state(intent=...)`) so probes record the new state.

## Why this split
Anything specifiable deterministically and testable without a model is a tool
(observe/act/journal/progress); anything goal-relative is your policy. That keeps
the journey trace itself usable as UX evidence regardless of whether the task
succeeded — never assume it did.
