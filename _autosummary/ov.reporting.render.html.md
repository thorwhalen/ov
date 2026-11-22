# ov.reporting.render

Render Markdown report sections from an analyzed run (§8.3).

Selects the registered sections that apply to the run’s mode, orders them by their
numeric `order`, renders each over the run + per-analyzer summaries, and writes
them to the store (and optionally an output directory). Returns the written keys
or paths.

### Functions

| [`render_reports`](#ov.reporting.render.render_reports)(run_or_analyses, \*[, ...])   | Render and persist the report sections; return their store keys/paths.   |
|-----------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|

### ov.reporting.render.render_reports(run_or_analyses, , sections='default', out_dir=None, store=None)

Render and persist the report sections; return their store keys/paths.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]
