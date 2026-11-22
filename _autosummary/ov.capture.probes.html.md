# ov.capture.probes

Probes – the registerable units of *what intelligence to gather* (§2).

Each probe is an independent plugin that writes typed artifacts into the capture
store. A probe is a small class implementing the [`Probe`](#ov.capture.probes.Probe) lifecycle:

* [`Probe.attach()`](#ov.capture.probes.Probe.attach) – subscribe event listeners *before* navigation (used by
  the streaming probes: network, console, navigation, websocket, sse).
* [`Probe.capture()`](#ov.capture.probes.Probe.capture) – snapshot the current state into artifacts (used by the
  per-state probes: dom, screenshot, perf, storage, fingerprint).
* [`Probe.finalize()`](#ov.capture.probes.Probe.finalize) – flush accumulated state into artifacts at run end.

Probes are registered with `register_probe()` and ordered by the registry’s
`requires`/`produces` dependency declarations, so e.g. `assets` (which
needs the network stream) runs after `network`.

### Functions

| [`load_builtin_probes`](#ov.capture.probes.load_builtin_probes)()   | Import the builtin probe modules so their `@register_probe` runs.   |
|--------------------------------------------------------------------------|---------------------------------------------------------------------|

### Classes

| [`Probe`](#ov.capture.probes.Probe)()                                       | Base class for probes; override only the lifecycle hooks you need.   |
|------------------------------------------------------------------------------------------------|----------------------------------------------------------------------|
| [`ProbeContext`](#ov.capture.probes.ProbeContext)(store, run, config[, page, ...]) | Everything a probe needs, injected by the `CaptureSession`.          |

### *class* ov.capture.probes.Probe

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Base class for probes; override only the lifecycle hooks you need.

#### attach(ctx)

Subscribe listeners before navigation. Default: no-op.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### capture(ctx)

Snapshot current state into artifacts. Default: nothing.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Artifact`](ov.base.html.md#ov.base.Artifact)]

#### finalize(ctx)

Flush accumulated state into artifacts at run end. Default: nothing.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Artifact`](ov.base.html.md#ov.base.Artifact)]

### *class* ov.capture.probes.ProbeContext(store, run, config, page=None, cdp=None, step=None, extras=dict())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Everything a probe needs, injected by the `CaptureSession`.

`extras` is shared scratch (e.g. the accumulating network record list) so
streaming probes can hand data to per-state probes without globals.

### ov.capture.probes.load_builtin_probes()

Import the builtin probe modules so their `@register_probe` runs.

Safe to call repeatedly (imports are cached). It is also invoked once at the
bottom of this module so that simply importing [`ov.capture.probes`](#module-ov.capture.probes)
yields a fully-populated `PROBE_REGISTRY` – no caller (the session, a
test, a skill) ever observes a half-registered registry depending on import
order. The probe modules pull in no heavy/browser dependencies at import.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### Modules

| [`a11y`](ov.capture.probes.a11y.html.md#module-ov.capture.probes.a11y)               | Accessibility-signals probe: computed text styles (for contrast) + optional axe.   |
|---------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------|
| [`assets`](ov.capture.probes.assets.html.md#module-ov.capture.probes.assets)           | Assets probe: a content-addressed inventory of loaded resources.                   |
| [`console`](ov.capture.probes.console.html.md#module-ov.capture.probes.console)         | Console probe: console messages, page errors, and unhandled rejections.            |
| [`dom`](ov.capture.probes.dom.html.md#module-ov.capture.probes.dom)                 | DOM probe: serialized DOM + ARIA snapshot (agent view) + full AX tree (evidence).  |
| [`fingerprint`](ov.capture.probes.fingerprint.html.md#module-ov.capture.probes.fingerprint) | Fingerprint probe: a built-in, license-clean technology detector.                  |
| [`navigation`](ov.capture.probes.navigation.html.md#module-ov.capture.probes.navigation)   | Navigation probe: URL changes, redirects, frame tree, and SPA history.             |
| [`network`](ov.capture.probes.network.html.md#module-ov.capture.probes.network)         | Network probe: request/response metadata + bodies, accumulated from events.        |
| [`perf`](ov.capture.probes.perf.html.md#module-ov.capture.probes.perf)               | Performance probe: Navigation Timing, paint, web-vitals entries, CDP counters.     |
| [`screenshot`](ov.capture.probes.screenshot.html.md#module-ov.capture.probes.screenshot)   | Screenshot probe: full-page PNG per captured state.                                |
| [`sse`](ov.capture.probes.sse.html.md#module-ov.capture.probes.sse)                 | SSE probe: Server-Sent-Event frames via CDP (Chromium-only).                       |
| [`storage`](ov.capture.probes.storage.html.md#module-ov.capture.probes.storage)         | Storage probe: cookies, localStorage, sessionStorage, IndexedDB names.             |
| [`websocket`](ov.capture.probes.websocket.html.md#module-ov.capture.probes.websocket)     | WebSocket probe: frames sent/received and open/close, first-class (D1).            |
