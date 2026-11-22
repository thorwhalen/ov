# ov.reporting

Report layer: registered Markdown sections + the synopsis (Phase 2).

Each section is a registered function (`register_section()`) that takes the
analyses + run and returns a Markdown fragment; [`ov.reporting.render`](ov.reporting.render.html.md#module-ov.reporting.render)
concatenates the selected sections. [`ov.reporting.synopsis`](ov.reporting.synopsis.html.md#module-ov.reporting.synopsis) performs the
structured map-reduce that compresses many findings into one agent-consumable
synopsis.

(The package is named `reporting` rather than `report` so it cannot shadow
the `ov.report` facade *function*; see `ov/__init__.py`.)

### Functions

| [`load_builtin_sections`](#ov.reporting.load_builtin_sections)()   | Import builtin report-section modules so their `@register_section` runs.   |
|----------------------------------------------------------------------------|----------------------------------------------------------------------------|

### ov.reporting.load_builtin_sections()

Import builtin report-section modules so their `@register_section` runs.

Invoked once at the bottom of this module so the section registry is fully
populated on import (no order-dependent gaps). Safe to call repeatedly.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### Modules

| [`overview`](ov.reporting.overview.html.md#module-ov.reporting.overview)   | The `overview` one-liner: observe -> analyze -> report -> synopsis (§4).             |
|------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------|
| [`render`](ov.reporting.render.html.md#module-ov.reporting.render)       | Render Markdown report sections from an analyzed run (§8.3).                         |
| [`sections`](ov.reporting.sections.html.md#module-ov.reporting.sections)   | The default report sections (§8.3) -- each a registered Markdown fragment.           |
| [`synopsis`](ov.reporting.synopsis.html.md#module-ov.reporting.synopsis)   | Synopsis: structured map-reduce over findings into one agent-consumable file (§8.4). |
