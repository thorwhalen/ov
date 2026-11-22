# ov.analysis.ux.contrast_focus

Contrast + focus analyzer (deterministic, no engine).

Contrast ratios are computed from the captured `a11y_styles` artifact (effective
fg/bg colors) with the exact WCAG relative-luminance formula and the 4.5:1 normal
/ 3:1 large+UI thresholds (D3 §3). Focus issues that are statically detectable
(positive `tabindex`) are flagged from the DOM; the genuinely behavioral focus
properties (keyboard traps, focus-order *logicality*, visible-focus indicator)
need active key-driving and are routed to `needs_human_review` rather than
asserted – the honesty constraint again.

### Functions

| [`analyze_contrast_focus`](#ov.analysis.ux.contrast_focus.analyze_contrast_focus)(ctx)   | Emit contrast Findings + statically-detectable focus Findings.   |
|--------------------------------------------------------------------------------|------------------------------------------------------------------|
| [`contrast_ratio`](#ov.analysis.ux.contrast_focus.contrast_ratio)(fg, bg)        | WCAG contrast ratio between two sRGB colors (>=1.0).             |
| [`relative_luminance`](#ov.analysis.ux.contrast_focus.relative_luminance)(rgb)       | WCAG relative luminance of an sRGB `(r, g, b)` in 0-255.         |

### ov.analysis.ux.contrast_focus.analyze_contrast_focus(ctx)

Emit contrast Findings + statically-detectable focus Findings.

* **Return type:**
  [`AnalyzerOutput`](ov.analysis.context.html.md#ov.analysis.context.AnalyzerOutput)

### ov.analysis.ux.contrast_focus.contrast_ratio(fg, bg)

WCAG contrast ratio between two sRGB colors (>=1.0).

```pycon
>>> contrast_ratio([0, 0, 0], [255, 255, 255])
21.0
>>> round(contrast_ratio([255, 255, 255], [255, 255, 255]), 1)
1.0
```

* **Return type:**
  [`float`](https://docs.python.org/3/builtins/functions.html#float)

### ov.analysis.ux.contrast_focus.relative_luminance(rgb)

WCAG relative luminance of an sRGB `(r, g, b)` in 0-255.

```pycon
>>> relative_luminance([255, 255, 255])
1.0
>>> relative_luminance([0, 0, 0])
0.0
```

* **Return type:**
  [`float`](https://docs.python.org/3/builtins/functions.html#float)
