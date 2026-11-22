# ov.capture.probes.perf

Performance probe: Navigation Timing, paint, web-vitals entries, CDP counters.

An init script installs `PerformanceObserver``s that accumulate layout-shift and
event-timing entries onto ``window.__ov_perf` (so per-step CWV attribution is
possible downstream); at each captured state the probe reads those plus the
Navigation Timing and paint entries, and – on Chromium – `Performance.getMetrics`
via CDP. Web-vitals *attribution* (naming the offending element) is refined in the
`cwv` analyzer; this probe captures the raw entries deterministically.

### Classes

| [`PerfProbe`](#ov.capture.probes.perf.PerfProbe)()   | Snapshot timing + web-vitals entries + CDP counters per captured state.   |
|----------------------------------------------------------------|---------------------------------------------------------------------------|

### *class* ov.capture.probes.perf.PerfProbe

Bases: [`Probe`](ov.capture.probes.html.md#ov.capture.probes.Probe)

Snapshot timing + web-vitals entries + CDP counters per captured state.

#### attach(ctx)

Subscribe listeners before navigation. Default: no-op.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### capture(ctx)

Snapshot current state into artifacts. Default: nothing.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Artifact`](ov.base.html.md#ov.base.Artifact)]
