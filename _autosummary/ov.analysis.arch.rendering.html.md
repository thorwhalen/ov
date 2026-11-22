# ov.analysis.arch.rendering

Rendering-model classifier: CSR vs SSR/SSG via raw-HTML-vs-rendered-DOM diff (D2).

The deterministic test compares the *server-sent* HTML (the captured document
response body, pre-JS) against the *rendered* DOM (post-JS). A large divergence
=> CSR (server sends a shell, JS builds the page); near-identity => SSR/SSG. This
is computed entirely from captured artifacts – no re-fetch – so it stays
hermetic. State-injection globals (`__NEXT_DATA__`/`__NUXT__`/`__remixContext`)
corroborate SSR/SSG. SSG vs SSR needs multiple requests and is left as a refinement.

### Functions

| [`analyze_rendering`](#ov.analysis.arch.rendering.analyze_rendering)(ctx)                          | Set `run.rendering_model` and emit an arch_fact Finding.                 |
|--------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| [`classify_rendering`](#ov.analysis.arch.rendering.classify_rendering)(raw_html, rendered_html)     | Classify the rendering model from raw vs rendered HTML (pure, testable). |
| [`rendering_scored`](#ov.analysis.arch.rendering.rendering_scored)(model, confidence, provenance) | Wrap a rendering classification as a `Scored` fact (helper).             |

### ov.analysis.arch.rendering.analyze_rendering(ctx)

Set `run.rendering_model` and emit an arch_fact Finding.

* **Return type:**
  [`AnalyzerOutput`](ov.analysis.context.html.md#ov.analysis.context.AnalyzerOutput)

### ov.analysis.arch.rendering.classify_rendering(raw_html, rendered_html, globals_present=None)

Classify the rendering model from raw vs rendered HTML (pure, testable).

Returns `(model, confidence_0_100, rationale)` where model is one of
`csr` | `ssr-or-ssg` | `hybrid` | `unknown`.

```pycon
>>> classify_rendering("<html><body><div id=root></div></body></html>",
...                    "<html><body><div id=root><h1>Hi</h1><p>lots of text here</p></div></body></html>")[0]
'csr'
```

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`int`](https://docs.python.org/3/builtins/functions.html#int), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### ov.analysis.arch.rendering.rendering_scored(model, confidence, provenance)

Wrap a rendering classification as a `Scored` fact (helper).

* **Return type:**
  [`Scored`](ov.base.html.md#ov.base.Scored)
