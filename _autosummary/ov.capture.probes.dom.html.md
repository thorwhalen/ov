# ov.capture.probes.dom

DOM probe: serialized DOM + ARIA snapshot (agent view) + full AX tree (evidence).

Two accessibility views, per the progressive-disclosure rule (§9): the concise
**ARIA snapshot** (`locator.aria_snapshot` – ~200-400 tokens, the agent’s
view) and the full CDP **AX tree** (recorded as evidence). The serialized DOM
(`page.content()`) is stored for the rendering-model diff and selector lookups.
Runs per captured state so SPA/modal/revealed-menu states are each recorded.

### Classes

| [`DomProbe`](#ov.capture.probes.dom.DomProbe)()   | Snapshot DOM + ARIA snapshot + full AX tree for the current state.   |
|---------------------------------------------------------------|----------------------------------------------------------------------|

### *class* ov.capture.probes.dom.DomProbe

Bases: [`Probe`](ov.capture.probes.html.md#ov.capture.probes.Probe)

Snapshot DOM + ARIA snapshot + full AX tree for the current state.

#### capture(ctx)

Snapshot current state into artifacts. Default: nothing.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Artifact`](ov.base.html.md#ov.base.Artifact)]
