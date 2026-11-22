# ov.capture.session

`CaptureSession` – owns the browser and orchestrates the probes (§3.1).

The session is the deterministic capture spine: it resolves and dependency-orders
the enabled probes, attaches their listeners before navigation, snapshots state
on demand (the `snapshot_state` primitive of §2.3), finalizes and flushes them
at the end, stores the HAR, and persists the [`CaptureRun`](ov.base.html.md#ov.base.CaptureRun).

It exposes `page` so the `operate` primitives and the scripted driver can act
on the same browser, and is a context manager for safe teardown.

### Classes

| [`CaptureSession`](#ov.capture.session.CaptureSession)(\*, target_url[, config, ...])   | Drive one target and record everything into the store (zero-config default).   |
|--------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------|

### *class* ov.capture.session.CaptureSession(, target_url, config=None, store=None, mode='reconstruct', probes='default', record_har=True, read_only=False)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Drive one target and record everything into the store (zero-config default).

Typical use is via the [`ov.observe()`](ov.html.md#ov.observe) facade, but the session is directly
usable:

```default
with CaptureSession(target_url="https://example.com") as s:
    s.open()                 # navigate to target_url + capture the load state
    run = s.run
```

#### capture_step(step)

Run per-state probes for an externally-built step (used by the driver).

* **Return type:**
  [`JourneyStep`](ov.base.html.md#ov.base.JourneyStep)

#### close()

Finalize if needed and tear down (idempotent).

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### finalize()

Flush every probe (page still alive), close the browser, store the HAR.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### navigate(url)

Navigate the page to `url` (waits for the default load state).

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### open(url=None, , intent='load')

Navigate to the target (or `url`) and capture the initial state.

* **Return type:**
  [`JourneyStep`](ov.base.html.md#ov.base.JourneyStep)

#### *property* page

The active Playwright `Page` for `operate` primitives / the driver.

#### snapshot_state(, intent='observe', strategy='ax_snapshot')

Capture all probes for the current state and journal a `JourneyStep`.

Bundles the §2.3 `snapshot_state` primitive: observe affordances, run
per-state probes, and record one step keyed to the produced artifacts.

* **Return type:**
  [`JourneyStep`](ov.base.html.md#ov.base.JourneyStep)

#### start()

Launch the browser, attach CDP (Chromium), and attach all probes.

* **Return type:**
  [`CaptureSession`](#ov.capture.session.CaptureSession)
