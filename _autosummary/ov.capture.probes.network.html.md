# ov.capture.probes.network

Network probe: request/response metadata + bodies, accumulated from events.

Structured records come from Playwright `request`/`response` events (which we
control), not from the HAR file – the HAR is stored separately by the session as
a raw artifact. Bodies are captured only for configured content types and under
the size cap; `response.body()` eviction is caught and recorded as a fact
rather than crashing the run (D1: design around eviction from day one).

Headers are redacted by default (privacy): cookie/auth/token headers never
persist as raw values unless `config.capture_secrets` is set.

### Classes

| [`NetworkProbe`](#ov.capture.probes.network.NetworkProbe)()   | Accumulate request/response records (+ size-capped bodies) via events.   |
|-------------------------------------------------------------------|--------------------------------------------------------------------------|

### *class* ov.capture.probes.network.NetworkProbe

Bases: [`Probe`](ov.capture.probes.html.md#ov.capture.probes.Probe)

Accumulate request/response records (+ size-capped bodies) via events.

#### attach(ctx)

Subscribe listeners before navigation. Default: no-op.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### finalize(ctx)

Flush accumulated state into artifacts at run end. Default: nothing.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Artifact`](ov.base.html.md#ov.base.Artifact)]
