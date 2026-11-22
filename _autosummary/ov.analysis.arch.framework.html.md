# ov.analysis.arch.framework

Framework / bundler / state-management / routing enrichment (D2 §5).

The `fingerprint` probe already detected frameworks from runtime globals; this
analyzer enriches the picture from the *bundle text* (bundler + state-management
signatures) and reconstructs a client routing map from `<a href>` links. New
`fingerprint`` (dedup by name,
max confidence); the routing map is surfaced for the architecture report.

### Functions

| [`analyze_framework`](#ov.analysis.arch.framework.analyze_framework)(ctx)   | Detect bundler + state-management from bundles; reconstruct the route map.   |
|---------------------------------------------------------------------------|------------------------------------------------------------------------------|

### ov.analysis.arch.framework.analyze_framework(ctx)

Detect bundler + state-management from bundles; reconstruct the route map.

* **Return type:**
  [`AnalyzerOutput`](ov.analysis.context.html.md#ov.analysis.context.AnalyzerOutput)
