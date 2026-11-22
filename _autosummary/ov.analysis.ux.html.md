# ov.analysis.ux

UX + accessibility deterministic analyzers (§5.1, D3).

Each module registers an analyzer that reads captured artifacts and emits
normalized `Finding`s with ``severity = impact_tier x reach``.
The hard honesty constraint (D3) lives here: automated tooling catches only
~30-40% of WCAG issues, so the non-automatable tail is routed to
`needs_human_review` and never asserted as resolved.

### Modules

| [`a11y`](ov.analysis.ux.a11y.html.md#module-ov.analysis.ux.a11y)                     | Accessibility analyzer: WebAIM perennials from the DOM + optional axe mapping.         |
|------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| [`contrast_focus`](ov.analysis.ux.contrast_focus.html.md#module-ov.analysis.ux.contrast_focus) | Contrast + focus analyzer (deterministic, no engine).                                  |
| [`cwv`](ov.analysis.ux.cwv.html.md#module-ov.analysis.ux.cwv)                       | Core Web Vitals analyzer: performance-as-UX from the captured `perf` artifacts.        |
| [`heuristics`](ov.analysis.ux.heuristics.html.md#module-ov.analysis.ux.heuristics)         | Heuristic analyzer: the automatable subset of Nielsen / cognitive-walkthrough (D3 §6). |
| [`metrics`](ov.analysis.ux.metrics.html.md#module-ov.analysis.ux.metrics)               | Journey-metrics analyzer: form friction, backtracking, and journey summary (D3 §5).    |
| [`severity`](ov.analysis.ux.severity.html.md#module-ov.analysis.ux.severity)             | Severity scoring: `score = impact_tier x reach` (D3 §1).                               |
