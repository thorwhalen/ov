# ov.capture.probes.websocket

WebSocket probe: frames sent/received and open/close, first-class (D1).

Uses `page.on("websocket")` -> `framesent`/`framereceived`/`close` (a
high-level Playwright API, *not* CDP). Frame payloads are truncated to a sane cap
to keep the store bounded; realtime *shape* synthesis happens later in arch
analysis, not here.

### Classes

| [`WebSocketProbe`](#ov.capture.probes.websocket.WebSocketProbe)()   | Capture WS lifecycle + frames via `page.on('websocket')`.   |
|---------------------------------------------------------------------|-------------------------------------------------------------|

### *class* ov.capture.probes.websocket.WebSocketProbe

Bases: [`Probe`](ov.capture.probes.html.md#ov.capture.probes.Probe)

Capture WS lifecycle + frames via `page.on('websocket')`.

#### attach(ctx)

Subscribe listeners before navigation. Default: no-op.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### finalize(ctx)

Flush accumulated state into artifacts at run end. Default: nothing.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Artifact`](ov.base.html.md#ov.base.Artifact)]
