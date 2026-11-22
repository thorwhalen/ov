# ov.analysis.arch.dependencies

Dependency inventory + known-vulnerability flags (D2).

Builds a dependency inventory from the detected technologies (provenance ranks
sourcemap path > bundle comment > global signature) and, when the **Retire.js**
CLI is available, scans the captured JS bodies for CVE-backed vulnerable library
versions. Retire.js is shelled out to (it must not run untrusted JS in-process);
when it is absent the analyzer emits an honest `undetermined` finding routing
CVE coverage to a human rather than asserting “no known vulnerabilities”.

### Functions

| [`analyze_dependencies`](#ov.analysis.arch.dependencies.analyze_dependencies)(ctx)   | Inventory dependencies and flag known-vulnerable versions (Retire.js, optional).   |
|------------------------------------------------------------------------------|------------------------------------------------------------------------------------|

### ov.analysis.arch.dependencies.analyze_dependencies(ctx)

Inventory dependencies and flag known-vulnerable versions (Retire.js, optional).

* **Return type:**
  [`AnalyzerOutput`](ov.analysis.context.html.md#ov.analysis.context.AnalyzerOutput)
