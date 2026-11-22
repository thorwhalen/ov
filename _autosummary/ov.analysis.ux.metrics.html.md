# ov.analysis.ux.metrics

Journey-metrics analyzer: form friction, backtracking, and journey summary (D3 §5).

Form friction is the headline finding – conversion drops sharply across the 5-7
field cliff, so forms are scored by field/required count. Backtracking and
dead-ends are read from the journey trace (revisited observation hashes, noop/
error steps). Descriptive journey metrics (steps, distinct states, success) are
surfaced in the analyzer summary for the report’s overview section.

### Functions

| [`analyze_metrics`](#ov.analysis.ux.metrics.analyze_metrics)(ctx)                       | Emit form-friction + backtracking Findings and a journey summary.        |
|---------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| [`form_friction`](#ov.analysis.ux.metrics.form_friction)(field_count, required_count) | Map a form's field counts to (impact_tier, note) past the 5-field cliff. |

### ov.analysis.ux.metrics.analyze_metrics(ctx)

Emit form-friction + backtracking Findings and a journey summary.

* **Return type:**
  [`AnalyzerOutput`](ov.analysis.context.html.md#ov.analysis.context.AnalyzerOutput)

### ov.analysis.ux.metrics.form_friction(field_count, required_count)

Map a form’s field counts to (impact_tier, note) past the 5-field cliff.

```pycon
>>> form_friction(3, 2) is None
True
>>> form_friction(6, 4)[0]
'moderate'
>>> form_friction(10, 8)[0]
'critical'
```

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)] | [`None`](https://docs.python.org/3/builtins/constants.html#None)
