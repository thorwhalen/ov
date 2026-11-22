# ov.analysis.ux.cwv

Core Web Vitals analyzer: performance-as-UX from the captured `perf` artifacts.

Computes INP (group `event` entries by `interactionId`, max duration; 200ms),
CLS (sum `layout-shift` values excluding `hadRecentInput`, already filtered at
capture; 0.1), and LCP/TTFB from the most complete perf snapshot. Per D3, LCP/FCP/
TTFB are **initial-load-only** until the Soft Navigations API lands, so those
findings are labelled provisional. True per-step bucketing by wall-clock window is
a depth item; here metrics are attributed at the page level.

### Functions

| [`analyze_cwv`](#ov.analysis.ux.cwv.analyze_cwv)(ctx)       | Emit performance Findings from the most complete perf snapshot.      |
|-------------------------------------------------------------------------|----------------------------------------------------------------------|
| [`cwv_from_perf`](#ov.analysis.ux.cwv.cwv_from_perf)(payload) | Reduce one perf payload to `{inp, cls, lcp, ttfb}` (pure, testable). |

### ov.analysis.ux.cwv.analyze_cwv(ctx)

Emit performance Findings from the most complete perf snapshot.

* **Return type:**
  [`AnalyzerOutput`](ov.analysis.context.html.md#ov.analysis.context.AnalyzerOutput)

### ov.analysis.ux.cwv.cwv_from_perf(payload)

Reduce one perf payload to `{inp, cls, lcp, ttfb}` (pure, testable).

```pycon
>>> cwv_from_perf({"vitals": {"inp": [{"duration": 50, "interactionId": 1},
...                                    {"duration": 90, "interactionId": 1}],
...                            "cls": [{"value": 0.05}, {"value": 0.03}],
...                            "lcp": [{"value": 1200}]},
...                 "navigation": {"ttfb": 300}})
{'inp': 90, 'cls': 0.08, 'lcp': 1200, 'ttfb': 300}
```

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`float`](https://docs.python.org/3/builtins/functions.html#float) | [`None`](https://docs.python.org/3/builtins/constants.html#None)]
