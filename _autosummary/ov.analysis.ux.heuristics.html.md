# ov.analysis.ux.heuristics

Heuristic analyzer: the automatable subset of Nielsen / cognitive-walkthrough (D3 §6).

Each heuristic maps to a machine-observable signal computed from the journey
trace + console + DOM:

* **console-error-on-step** – a console error emitted during a step (robustness).
* **missing feedback (Nielsen H1 / CW Q4)** – a `click` whose post-observation
  hash is unchanged with no console/network delta (no visible response).
* **live-region presence (WCAG 4.1.3)** – dynamic states but no `aria-live` /
  `role=status` region to announce them.

The Operator’s per-step *intent* is the cognitive-walkthrough ground truth for
“expected action”, so a noop on an intentful click is a meaningful signal.

### Functions

| [`analyze_heuristics`](#ov.analysis.ux.heuristics.analyze_heuristics)(ctx)   | Emit Findings for console-on-step, missing feedback, and live-region absence.   |
|----------------------------------------------------------------------------|---------------------------------------------------------------------------------|

### ov.analysis.ux.heuristics.analyze_heuristics(ctx)

Emit Findings for console-on-step, missing feedback, and live-region absence.

* **Return type:**
  [`AnalyzerOutput`](ov.analysis.context.html.md#ov.analysis.context.AnalyzerOutput)
