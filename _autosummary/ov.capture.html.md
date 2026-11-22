# ov.capture

Capture layer: drive a browser and record behavioral + static streams.

The public entry point is [`CaptureSession`](ov.capture.session.html.md#ov.capture.session.CaptureSession); persisted
state lives in [`CaptureStore`](ov.capture.stores.html.md#ov.capture.stores.CaptureStore). Probes are registered
plugins (see [`ov.capture.probes`](ov.capture.probes.html.md#module-ov.capture.probes)).

### Modules

| [`browser`](ov.capture.browser.html.md#module-ov.capture.browser)   | Playwright facade -- the baseline driver (§9, D1).                              |
|--------------------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| [`cdp`](ov.capture.cdp.html.md#module-ov.capture.cdp)           | The CDP escape-hatch plugin (Chromium-only) -- the ~20% Playwright can't reach. |
| [`probes`](ov.capture.probes.html.md#module-ov.capture.probes)     | Probes -- the registerable units of *what intelligence to gather* (§2).         |
| [`session`](ov.capture.session.html.md#module-ov.capture.session)   | `CaptureSession` -- owns the browser and orchestrates the probes (§3.1).        |
| [`stores`](ov.capture.stores.html.md#module-ov.capture.stores)     | The capture store -- a `MutableMapping` Mall over a run directory (§3.4).       |
