# ov.capture.stores

The capture store – a `MutableMapping` Mall over a run directory (§3.4).

A single root holds many runs. Artifacts are **content-addressed** (keyed by a
hash of their bytes) so identical assets dedupe across runs – which is exactly
what makes own-target diffing cheap. `dol` provides the filesystem-backed
mappings; this module is a thin facade that adds the `ov` semantics (typed
runs, artifact put/get, report + analysis storage) on top.

Layout under `root`:

```default
runs/<run_id>.json          # CaptureRun, JSON
artifacts/<hash>.<ext>      # content-addressed bytes (shared across runs)
reports/<run_id>/<name>     # rendered Markdown
analyses/<analysis_id>.json # analysis JSON
```

The Mall exposes four `MutableMapping` attributes (`runs`, `artifacts`,
`reports`, `analyses`) for callers who want raw access, plus convenience
methods that speak the SSOT models.

### Functions

| [`resolve_store`](#ov.capture.stores.resolve_store)(store)   | Coerce `store` (a CaptureStore, a path, or `None`) into a CaptureStore.   |
|-------------------------------------------------------------------------|---------------------------------------------------------------------------|

### Classes

| [`CaptureStore`](#ov.capture.stores.CaptureStore)([root])   | A store of stores for one or many capture runs (XDG-aligned root by default).   |
|-------------------------------------------------------------------------|---------------------------------------------------------------------------------|

### *class* ov.capture.stores.CaptureStore(root=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A store of stores for one or many capture runs (XDG-aligned root by default).

```pycon
>>> import tempfile
>>> store = CaptureStore(tempfile.mkdtemp())
>>> art = store.put_artifact(b"<html>hi</html>", kind="dom")
>>> store.artifact_bytes(art) == b"<html>hi</html>"
True
>>> from ov.base import CaptureRun
>>> run = CaptureRun(target_url="http://x", artifacts=[art])
>>> store.save_run(run)
>>> store.load_run(run.run_id).target_url
'http://x'
```

#### artifact_bytes(artifact_or_uri)

Return the raw bytes for an `Artifact` (or a raw `uri` string).

* **Return type:**
  [`bytes`](https://docs.python.org/3/builtins/stdtypes.html#bytes)

#### load_analysis(analysis_id)

Load an analysis JSON blob by id.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

#### load_run(run_id)

Load a `CaptureRun` by id (accepts bare id or `<id>.json`).

* **Return type:**
  [`CaptureRun`](ov.base.html.md#ov.base.CaptureRun)

#### put_artifact(data, , kind, step_id=None, content_type=None, meta=None)

Store `data` content-addressed and return its `Artifact` record.

Identical bytes produce the same `uri`, so re-storing is a no-op write
and cross-run assets dedupe automatically.

* **Return type:**
  [`Artifact`](ov.base.html.md#ov.base.Artifact)

#### report_names(run_id)

List report keys belonging to `run_id` (separator-normalized).

`dol` returns directory-listing keys with the OS separator, which is a
backslash on Windows; we always speak the logical `/` separator (and
store/read with it), so normalize before the prefix match.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

#### run_ids()

List stored run ids (without the `.json` suffix).

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

#### save_analysis(analysis_id, obj)

Persist an analysis JSON blob by id.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### save_report(run_id, name, markdown)

Store a rendered Markdown report; return its store key.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

#### save_run(run)

Persist a `CaptureRun` as JSON under its `run_id`.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### ov.capture.stores.resolve_store(store)

Coerce `store` (a CaptureStore, a path, or `None`) into a CaptureStore.

The dependency-injection seam: callers pass whatever they have and get a
usable store, defaulting to the XDG root.

* **Return type:**
  [`CaptureStore`](#ov.capture.stores.CaptureStore)
