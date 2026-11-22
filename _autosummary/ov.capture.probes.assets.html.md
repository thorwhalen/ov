# ov.capture.probes.assets

Assets probe: a content-addressed inventory of loaded resources.

Bodies are already stored by the `network` probe (content-addressed, so they
dedupe). This probe builds the *inventory*: one manifest row per resource with
url, MIME, size, hash, and the body artifact id when captured. It `requires`
the network stream and therefore runs after it (registry ordering).

### Classes

| [`AssetsProbe`](#ov.capture.probes.assets.AssetsProbe)()   | Build an asset inventory from the accumulated network records.   |
|------------------------------------------------------------------|------------------------------------------------------------------|

### *class* ov.capture.probes.assets.AssetsProbe

Bases: [`Probe`](ov.capture.probes.html.md#ov.capture.probes.Probe)

Build an asset inventory from the accumulated network records.

#### finalize(ctx)

Flush accumulated state into artifacts at run end. Default: nothing.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Artifact`](ov.base.html.md#ov.base.Artifact)]
