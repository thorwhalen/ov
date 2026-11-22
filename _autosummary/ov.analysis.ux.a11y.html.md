# ov.analysis.ux.a11y

Accessibility analyzer: WebAIM perennials from the DOM + optional axe mapping.

The deterministic baseline parses each captured DOM state (`selectolax`) and
detects the WebAIM-Million perennials that are computable without a browser or a
GPL engine: missing image `alt`, empty links, empty buttons, unlabeled form
controls, and missing document language. These are ~96% of *detected* errors
(D3), so nailing them deterministically is high-value and fully testable.

If an `axe` artifact exists (an optional in-browser axe-core run at capture
time), its violations are additively mapped to Findings with `engine_rule_id`
`axe:<id>`. Contrast is handled by [`ov.analysis.ux.contrast_focus`](ov.analysis.ux.contrast_focus.html.md#module-ov.analysis.ux.contrast_focus) (it
needs computed colors, not static DOM).

**Honesty constraint (D3):** automated tooling catches only ~30-40% of WCAG
issues, so this analyzer always emits one `undetermined` finding routing the
non-automatable ~60-70% (meaningful alt text, reading/focus-order logicality,
in-context link text, screen-reader announcement quality, ARIA intent) to
`needs_human_review` – never asserting “no automated violations” == accessible.

### Functions

| [`analyze_a11y`](#ov.analysis.ux.a11y.analyze_a11y)(ctx)   | Emit a11y Findings from DOM perennials (+ axe results if captured).   |
|----------------------------------------------------------------------|-----------------------------------------------------------------------|

### ov.analysis.ux.a11y.analyze_a11y(ctx)

Emit a11y Findings from DOM perennials (+ axe results if captured).

* **Return type:**
  [`AnalyzerOutput`](ov.analysis.context.html.md#ov.analysis.context.AnalyzerOutput)
