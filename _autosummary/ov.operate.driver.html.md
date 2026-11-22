# ov.operate.driver

The scripted/guided driver – model-free journey execution (Phase 1).

Two deterministic strategies that compose the operate primitives over a
[`CaptureSession`](ov.capture.session.html.md#ov.capture.session.CaptureSession):

* [`replay()`](#ov.operate.driver.replay) – execute a scripted list of actions (guided-replay), capturing
  state and journaling each step.
* [`crawl()`](#ov.operate.driver.crawl) – a polite, same-origin breadth-first crawl (crawl-and-map),
  capturing each visited page and stopping on `max_pages` / no-progress.

These let the capture spine produce a real multi-state journey with **no model**.
Goal-pursuit (`advance` toward a success predicate) is the host’s job via the
`ov-operate` skill; the package supplies the hands, not the policy.

### Functions

| [`crawl`](#ov.operate.driver.crawl)(session, \*[, max_pages])   | Politely crawl same-origin links breadth-first, capturing each page.   |
|------------------------------------------------------------------------------------|------------------------------------------------------------------------|
| [`replay`](#ov.operate.driver.replay)(session, actions)          | Execute a scripted action list, capturing + journaling each step.      |

### ov.operate.driver.crawl(session, , max_pages=5)

Politely crawl same-origin links breadth-first, capturing each page.

Stops at `max_pages`, on `max_steps`, or when the deterministic progress
signal reports a loop. The host can run a richer crawl; this is the model-free
baseline that yields a multi-state capture.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`JourneyStep`](ov.base.html.md#ov.base.JourneyStep)]

### ov.operate.driver.replay(session, actions)

Execute a scripted action list, capturing + journaling each step.

```pycon
>>> # actions are Action models or dicts: {"type": "click", "ref": "e3"}
>>> callable(replay)
True
```

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`JourneyStep`](ov.base.html.md#ov.base.JourneyStep)]
