# ov.analysis.arch.sourcemaps

Pure source-map recovery: original file tree + `node_modules` versions (D2).

Source maps are the decisive, *bimodal* reconstruction lever. When a deployed
bundle ships a Source Map v3 document (`//# sourceMappingURL=...` or a sibling
`.js.map`), the original file tree and source text are recoverable by a plain
JSON parse: the `sourcesContent` array holds the verbatim sources, indexed in
parallel with `sources`. No VLQ `mappings` decoding and **no Node** are needed
for source recovery – that machinery only matters for stack-trace *position*
mapping. Keeping recovery pure-Python keeps the deterministic core testable,
cheap, and ungated by an optional sidecar (the spec’s “source-map sidecar depth”
is satisfied here in-process; the sidecar remains for the no-maps webcrack path).

This module is model-free and side-effect-free: it parses bytes already captured
into the store and returns plain, transient data. Persisting recovered files as
artifacts and emitting findings/tech is the analyzer’s job
([`ov.analysis.arch.bundles`](ov.analysis.arch.bundles.html.md#module-ov.analysis.arch.bundles)).

Security: `sources` paths come from an untrusted producer, so every path is
sanitized (scheme prefixes stripped, traversal contained) before it is used as a
relative path – escaping entries are skipped and counted, never resolved above a
root. The path-sanitization approach is adapted from rarecoil’s MIT-licensed
`unwebpack-sourcemap` `PathSanitiser`.

### Functions

| [`extract_inline_map`](#ov.analysis.arch.sourcemaps.extract_inline_map)(js_text)                  | Return the decoded JSON of an inline `sourceMappingURL=data:...` map, else `None`.   |
|-----------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------|
| [`is_recovered_dependency`](#ov.analysis.arch.sourcemaps.is_recovered_dependency)(tech)                | True for a `node_modules` package recovered from a source map (SBOM, not stack).     |
| [`node_modules_packages`](#ov.analysis.arch.sourcemaps.node_modules_packages)(files)                 | Infer sorted `(package, version|None)` pairs from recovered `node_modules` paths.    |
| [`parse_source_map`](#ov.analysis.arch.sourcemaps.parse_source_map)(map_text)                   | Parse a `.map` body into a Source Map v3 dict, or `None` if it is not one.           |
| [`recover_from_map`](#ov.analysis.arch.sourcemaps.recover_from_map)(map_text)                   | Recover original files from one source-map body (pure; no I/O, no Node).             |
| [`sanitize_source_path`](#ov.analysis.arch.sourcemaps.sanitize_source_path)(raw, \*[, source_root]) | Turn an untrusted `sources` entry into a safe root-relative path (or `None`).        |

### Classes

| [`MapRecovery`](#ov.analysis.arch.sourcemaps.MapRecovery)([files, sources_total, ...])   | Result of recovering one source map (transient internal data, not SSOT).     |
|---------------------------------------------------------------------------------------------|------------------------------------------------------------------------------|
| [`RecoveredFile`](#ov.analysis.arch.sourcemaps.RecoveredFile)(path, content, raw_source)   | One original file recovered from a source map (transient; never serialized). |

### *class* ov.analysis.arch.sourcemaps.MapRecovery(files=list(), sources_total=0, had_sources_content=False, skipped_unsafe=0)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Result of recovering one source map (transient internal data, not SSOT).

#### *property* recovered_count *: [int](https://docs.python.org/3/builtins/functions.html#int)*

Number of files with content actually recovered.

### *class* ov.analysis.arch.sourcemaps.RecoveredFile(path, content, raw_source)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

One original file recovered from a source map (transient; never serialized).

### ov.analysis.arch.sourcemaps.extract_inline_map(js_text)

Return the decoded JSON of an inline `sourceMappingURL=data:...` map, else `None`.

Handles `;base64,` and URL-encoded data URIs. External (`.map` URL) markers
return `None` – those are fetched by the capture probe, not decoded here.

```pycon
>>> import base64, json
>>> payload = base64.b64encode(json.dumps({"version": 3, "sources": []}).encode()).decode()
>>> js = "a=1\n//# sourceMappingURL=data:application/json;base64," + payload
>>> json.loads(extract_inline_map(js))["version"]
3
>>> extract_inline_map("a=1\n//# sourceMappingURL=app.js.map") is None
True
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

### ov.analysis.arch.sourcemaps.is_recovered_dependency(tech)

True for a `node_modules` package recovered from a source map (SBOM, not stack).

Single source of truth for separating the recovered-dependency SBOM from
framework-level technologies wherever `run.fingerprint` is summarized (the
overview header, the architecture stack table, the synopsis, review-mode
tech-diff). A tech that is ALSO a framework/bundler – e.g. `webpack`
detected both as a recovered dependency and by signature – carries an extra
category (so the set is not exactly `{"dependency"}`) and is NOT treated as a
pure recovered dependency, keeping it in the headline stack.

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### ov.analysis.arch.sourcemaps.node_modules_packages(files)

Infer sorted `(package, version|None)` pairs from recovered `node_modules` paths.

Version sources, in precedence order: a pnpm `.pnpm/<pkg>@<ver>/` path
segment, then a recovered `package.json` `version` field. Otherwise the
version is unknown (`None`). Scoped packages (`@scope/name`) are handled.

```pycon
>>> fs = [
...   RecoveredFile("node_modules/lodash/lodash.js", "x", "x"),
...   RecoveredFile("node_modules/@scope/ui/index.js", "y", "y"),
...   RecoveredFile("node_modules/.pnpm/axios@1.6.2/node_modules/axios/i.js", "z", "z"),
... ]
>>> d = dict(node_modules_packages(fs))
>>> d["lodash"] is None, d["axios"], "@scope/ui" in d
(True, '1.6.2', True)
```

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)]]

### ov.analysis.arch.sourcemaps.parse_source_map(map_text)

Parse a `.map` body into a Source Map v3 dict, or `None` if it is not one.

```pycon
>>> parse_source_map('{"version":3,"sources":["a.js"]}')["version"]
3
>>> parse_source_map("not json") is None
True
>>> parse_source_map('{"version":3}') is None
True
```

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

### ov.analysis.arch.sourcemaps.recover_from_map(map_text)

Recover original files from one source-map body (pure; no I/O, no Node).

Only `sources` with non-empty `sourcesContent` are recoverable; entries
whose path escapes the root are skipped and counted in `skipped_unsafe`.

```pycon
>>> m = ('{"version":3,"sources":["webpack:///src/a.js","webpack:///../evil"],'
...      '"sourcesContent":["console.log(1)","x"]}')
>>> r = recover_from_map(m)
>>> [f.path for f in r.files], r.skipped_unsafe, r.had_sources_content
(['src/a.js'], 1, True)
```

* **Return type:**
  [`MapRecovery`](#ov.analysis.arch.sourcemaps.MapRecovery)

### ov.analysis.arch.sourcemaps.sanitize_source_path(raw, , source_root='')

Turn an untrusted `sources` entry into a safe root-relative path (or `None`).

Applies `sourceRoot`, drops query/fragment and any `scheme://` prefix, then
*contains* traversal: a path that would escape the virtual root (a leading
`..` after normalization) or is absolute is rejected.

```pycon
>>> sanitize_source_path("webpack:///src/App.tsx")
'src/App.tsx'
>>> sanitize_source_path("../../etc/passwd") is None
True
>>> sanitize_source_path("webpack:///./a/../b.js")
'b.js'
>>> sanitize_source_path("a.js", source_root="webpack:///src/")
'src/a.js'
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)
