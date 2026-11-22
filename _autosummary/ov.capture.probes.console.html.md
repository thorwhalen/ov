# ov.capture.probes.console

Console probe: console messages, page errors, and unhandled rejections.

Captured from Playwright `console`/`pageerror` events. Each entry carries the
step it occurred in so the UX engine can attribute console-error-on-step (§5.1
heuristic) and the robustness analysis can corroborate broken states.

### Classes

| [`ConsoleProbe`](#ov.capture.probes.console.ConsoleProbe)()   | Accumulate console + pageerror entries via events.   |
|-------------------------------------------------------------------|------------------------------------------------------|

### *class* ov.capture.probes.console.ConsoleProbe

Bases: [`Probe`](ov.capture.probes.html.md#ov.capture.probes.Probe)

Accumulate console + pageerror entries via events.

#### attach(ctx)

Subscribe listeners before navigation. Default: no-op.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### finalize(ctx)

Flush accumulated state into artifacts at run end. Default: nothing.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Artifact`](ov.base.html.md#ov.base.Artifact)]
