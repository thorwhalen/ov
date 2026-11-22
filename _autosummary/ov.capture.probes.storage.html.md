# ov.capture.probes.storage

Storage probe: cookies, localStorage, sessionStorage, IndexedDB names.

Values are **redacted by default** (privacy; `config.redact_values`) – we keep
the *shape* of client state (which keys exist, how big) without persisting
secrets/PII. sessionStorage is read manually (it is not in `storage_state`) and
IndexedDB is probed for database names only (deep dumps are fragile and deferred).

### Classes

| [`StorageProbe`](#ov.capture.probes.storage.StorageProbe)()   | Snapshot client storage (redacted) for the current state.   |
|-------------------------------------------------------------------|-------------------------------------------------------------|

### *class* ov.capture.probes.storage.StorageProbe

Bases: [`Probe`](ov.capture.probes.html.md#ov.capture.probes.Probe)

Snapshot client storage (redacted) for the current state.

#### capture(ctx)

Snapshot current state into artifacts. Default: nothing.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Artifact`](ov.base.html.md#ov.base.Artifact)]
