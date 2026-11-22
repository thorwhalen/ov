# ov.analysis.arch

Architecture-reconstruction analyzers (§6, D2).

A deterministic `fingerprint -> bundle-recovery -> api-synthesis` pipeline,
each analyzer reading captured artifacts and emitting scored facts
([`TechFinding`](ov.base.html.md#ov.base.TechFinding)/[`Endpoint`](ov.base.html.md#ov.base.Endpoint)) with provenance. The
single biggest lever is source-map presence (reconstruction quality is bimodal),
so `source_maps_present` gates downstream confidence. Heavy JS-only tooling runs
in the optional Node sidecar; everything degrades gracefully without it.

### Modules

| [`api`](ov.analysis.arch.api.html.md#module-ov.analysis.arch.api)                   | API-surface synthesis: merge schemas across journeys, classify, detect auth (D2 §4).   |
|----------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| [`bundles`](ov.analysis.arch.bundles.html.md#module-ov.analysis.arch.bundles)           | Source-map detection + recovery -- the decisive bimodal lever (D2).                    |
| [`dependencies`](ov.analysis.arch.dependencies.html.md#module-ov.analysis.arch.dependencies) | Dependency inventory + known-vulnerability flags (D2).                                 |
| [`framework`](ov.analysis.arch.framework.html.md#module-ov.analysis.arch.framework)       | Framework / bundler / state-management / routing enrichment (D2 §5).                   |
| [`pipeline`](ov.analysis.arch.pipeline.html.md#module-ov.analysis.arch.pipeline)         | The arch pipeline as a composable transform (§6: fingerprint -> bundles -> api).       |
| [`rendering`](ov.analysis.arch.rendering.html.md#module-ov.analysis.arch.rendering)       | Rendering-model classifier: CSR vs SSR/SSG via raw-HTML-vs-rendered-DOM diff (D2).     |
| [`sidecar`](ov.analysis.arch.sidecar.html.md#module-ov.analysis.arch.sidecar)           | Python facade over the Node reverse-engineering sidecar (§6.1, D2).                    |
| [`sourcemaps`](ov.analysis.arch.sourcemaps.html.md#module-ov.analysis.arch.sourcemaps)     | Pure source-map recovery: original file tree + `node_modules` versions (D2).           |
