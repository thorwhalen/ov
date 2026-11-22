# ov.capture.probes.sse

SSE probe: Server-Sent-Event frames via CDP (Chromium-only).

SSE frames are *not* reliably reachable through `page.route` or
`response.body()`, so this probe uses `Network.eventSourceMessageReceived`
through the CDP escape hatch (which requires `Network.enable`). When CDP is
unavailable (non-Chromium), the probe is inert.

### Classes

| [`SseProbe`](#ov.capture.probes.sse.SseProbe)()   | Capture SSE frames via `CdpSession.capture_sse` when CDP is available.   |
|---------------------------------------------------------------|--------------------------------------------------------------------------|

### *class* ov.capture.probes.sse.SseProbe

Bases: [`Probe`](ov.capture.probes.html.md#ov.capture.probes.Probe)

Capture SSE frames via `CdpSession.capture_sse` when CDP is available.

#### attach(ctx)

Subscribe listeners before navigation. Default: no-op.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### finalize(ctx)

Flush accumulated state into artifacts at run end. Default: nothing.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Artifact`](ov.base.html.md#ov.base.Artifact)]
