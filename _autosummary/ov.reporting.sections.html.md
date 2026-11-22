# ov.reporting.sections

The default report sections (§8.3) – each a registered Markdown fragment.

A section is `fn(run, analyses) -> str`. Sections are registered with an
`order` (numeric prefix) and the `modes` they apply to (reconstruct/review),
so [`ov.reporting.render`](ov.reporting.render.html.md#module-ov.reporting.render) can select and concatenate them. They read the
already-analyzed [`CaptureRun`](ov.base.html.md#ov.base.CaptureRun) (findings, fingerprint, api_surface,
rendering_model, …) plus the per-analyzer summaries – no model involved.

### Functions

| `api_section`(run, analyses)              |    |
|-------------------------------------------|----|
| `appendix_section`(run, analyses)         |    |
| `architecture_section`(run, analyses)     |    |
| `overview_section`(run, analyses)         |    |
| `reconstruction_section`(run, analyses)   |    |
| `recovered_source_section`(run, analyses) |    |
| `review_section`(run, analyses)           |    |
| `ux_section`(run, analyses)               |    |
