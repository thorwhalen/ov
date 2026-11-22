# ov.analysis.arch.bundles

Source-map detection + recovery – the decisive bimodal lever (D2).

Reconstruction quality is bimodal: WITH source maps you recover the original file
tree, source text, and `node_modules` version paths; WITHOUT them you get a
beautified-but-renamed approximation. So this analyzer detects map presence from
the captured JS bodies and asset URLs and sets `source_maps_present` (which
gates downstream reconstruction confidence everywhere).

Recovery is **pure-Python and Node-free** (see [`ov.analysis.arch.sourcemaps`](ov.analysis.arch.sourcemaps.html.md#module-ov.analysis.arch.sourcemaps)):
it parses any captured `.map` body (explicit `source_map` artifacts, incidental
`.map` responses, or inline `data:` maps), persists each recovered file
content-addressed (`recovered_source` artifacts indexed by a manifest blob), and
surfaces recovered `node_modules` packages as top-provenance
`artifacts``, so re-analysis stays idempotent.

### Functions

| [`analyze_bundles`](#ov.analysis.arch.bundles.analyze_bundles)(ctx)                      | Set `run.source_maps_present` and emit an arch_fact (+ optional recovery).   |
|--------------------------------------------------------------------------------------------|------------------------------------------------------------------------------|
| [`detect_source_maps`](#ov.analysis.arch.bundles.detect_source_maps)(js_bodies, asset_urls) | Detect source-map presence from JS bodies + asset urls (pure, testable).     |
| [`js_response_bodies`](#ov.analysis.arch.bundles.js_response_bodies)(ctx)                   | Return `(url, text)` for captured JS response bodies (reused across arch).   |

### ov.analysis.arch.bundles.analyze_bundles(ctx)

Set `run.source_maps_present` and emit an arch_fact (+ optional recovery).

* **Return type:**
  [`AnalyzerOutput`](ov.analysis.context.html.md#ov.analysis.context.AnalyzerOutput)

### ov.analysis.arch.bundles.detect_source_maps(js_bodies, asset_urls)

Detect source-map presence from JS bodies + asset urls (pure, testable).

```pycon
>>> detect_source_maps([("a.js", "x=1\n//# sourceMappingURL=a.js.map")], [])[0]
True
>>> detect_source_maps([("a.js", "x=1")], ["https://x/b.js.map"])[0]
True
>>> detect_source_maps([("a.js", "x=1")], [])[0]
False
```

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`bool`](https://docs.python.org/3/builtins/functions.html#bool), [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]

### ov.analysis.arch.bundles.js_response_bodies(ctx)

Return `(url, text)` for captured JS response bodies (reused across arch).

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]
