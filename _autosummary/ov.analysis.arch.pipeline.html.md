# ov.analysis.arch.pipeline

The arch pipeline as a composable transform (§6: fingerprint -> bundles -> api).

The architecture lens is conceptually a three-stage deterministic pipeline. The
registry already orders the arch analyzers by their declared dependencies; this
module exposes that ordering and a convenience that runs *only* the arch lens
over a context and returns the merged output – useful for callers (or tests)
that want architecture facts without the full UX pass.

### Module Attributes

| [`ARCH_STAGES`](#ov.analysis.arch.pipeline.ARCH_STAGES)   | Canonical arch stage order (fingerprint detection -> bundle recovery -> API synthesis).   |
|----------------------------------------------------------------|-------------------------------------------------------------------------------------------|

### Functions

| [`run_arch_pipeline`](#ov.analysis.arch.pipeline.run_arch_pipeline)(ctx)   | Run the arch-lens analyzers in dependency order; return one merged output.   |
|---------------------------------------------------------------------------|------------------------------------------------------------------------------|

### ov.analysis.arch.pipeline.ARCH_STAGES *= ('rendering', 'framework', 'bundles', 'api_surface', 'dependencies')*

Canonical arch stage order (fingerprint detection -> bundle recovery -> API synthesis).

### ov.analysis.arch.pipeline.run_arch_pipeline(ctx)

Run the arch-lens analyzers in dependency order; return one merged output.

* **Return type:**
  [`AnalyzerOutput`](ov.analysis.context.html.md#ov.analysis.context.AnalyzerOutput)
