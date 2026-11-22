# ov.capture.probes.screenshot

Screenshot probe: full-page PNG per captured state.

Full-page screenshots ground the set-of-mark evidence bundle later (§8.1). The
artifact id is recorded onto the step so the evidence assembler can resolve the
exact image a finding refers to.

### Classes

| [`ScreenshotProbe`](#ov.capture.probes.screenshot.ScreenshotProbe)()   | Capture a full-page PNG of the current state.   |
|----------------------------------------------------------------------|-------------------------------------------------|

### *class* ov.capture.probes.screenshot.ScreenshotProbe

Bases: [`Probe`](ov.capture.probes.html.md#ov.capture.probes.Probe)

Capture a full-page PNG of the current state.

#### capture(ctx)

Snapshot current state into artifacts. Default: nothing.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Artifact`](ov.base.html.md#ov.base.Artifact)]
