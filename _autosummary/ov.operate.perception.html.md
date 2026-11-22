# ov.operate.perception

Perception strategies – pluggable ways to turn a page into an `Observation`.

A perception strategy returns a uniform [`Observation`](ov.base.html.md#ov.base.Observation) so the rest
of the operate layer (and the host’s policy) stays declarative about *what* an
observation is, not *how* it was grounded. Three strategies ship:

* `ax_snapshot` – affordances from an accessibility-relevant DOM walk plus the
  concise ARIA snapshot text (cheap, deterministic, the default).
* `screenshot` – the same affordances with bounding boxes, intended to pair
  with a screenshot artifact (for canvas/exotic renderers).
* `hybrid` – AX-grounded affordances, robust when the AX layer is thin.

Affordances are extracted by stamping a stable `data-ov-ref` attribute on each
interactive element, so `act()` can target it deterministically
(`getByRole`-stable, survives CSS churn) – the require-description-and-ref
safety pattern from Playwright-MCP.

### Module Attributes

| [`REF_ATTR`](#ov.operate.perception.REF_ATTR)            | The attribute stamped on interactive elements to create stable refs.   |
|----------------------------------------------------------------------|------------------------------------------------------------------------|
| [`PERCEPTION_REGISTRY`](#ov.operate.perception.PERCEPTION_REGISTRY) | name -> `perceiver(page) -> Observation`                               |

### Functions

| [`perceive`](#ov.operate.perception.perceive)(page[, strategy])   | Dispatch to the named perception strategy (defaults to `ax_snapshot`).       |
|-------------------------------------------------------------------------------|------------------------------------------------------------------------------|
| [`perceive_ax_snapshot`](#ov.operate.perception.perceive_ax_snapshot)(page)   | Affordances + concise ARIA snapshot text (the cheap, deterministic default). |
| [`perceive_hybrid`](#ov.operate.perception.perceive_hybrid)(page)        | AX-grounded affordances + ARIA snapshot; the robust default when AX is thin. |
| [`perceive_screenshot`](#ov.operate.perception.perceive_screenshot)(page)    | Affordances with bounding boxes (pairs with a screenshot artifact).          |
| [`register_perception`](#ov.operate.perception.register_perception)(name)    | Decorator registering a perceiver under `name`.                              |

### ov.operate.perception.PERCEPTION_REGISTRY *: [dict](https://docs.python.org/3/builtins/stdtypes.html#dict)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [Callable](https://docs.python.org/3/library/typing.html#typing.Callable)[[[Any](https://docs.python.org/3/library/typing.html#typing.Any)], [Observation](ov.base.html.md#ov.base.Observation)]]* *= {'ax_snapshot': <function perceive_ax_snapshot>, 'hybrid': <function perceive_hybrid>, 'screenshot': <function perceive_screenshot>}*

name -> `perceiver(page) -> Observation`

### ov.operate.perception.REF_ATTR *= 'data-ov-ref'*

The attribute stamped on interactive elements to create stable refs.

### ov.operate.perception.perceive(page, strategy='ax_snapshot')

Dispatch to the named perception strategy (defaults to `ax_snapshot`).

Raises `KeyError` with the known strategies when `strategy` is unknown –
an informative error per the project’s principles.

* **Return type:**
  [`Observation`](ov.base.html.md#ov.base.Observation)

### ov.operate.perception.perceive_ax_snapshot(page)

Affordances + concise ARIA snapshot text (the cheap, deterministic default).

* **Return type:**
  [`Observation`](ov.base.html.md#ov.base.Observation)

### ov.operate.perception.perceive_hybrid(page)

AX-grounded affordances + ARIA snapshot; the robust default when AX is thin.

* **Return type:**
  [`Observation`](ov.base.html.md#ov.base.Observation)

### ov.operate.perception.perceive_screenshot(page)

Affordances with bounding boxes (pairs with a screenshot artifact).

* **Return type:**
  [`Observation`](ov.base.html.md#ov.base.Observation)

### ov.operate.perception.register_perception(name)

Decorator registering a perceiver under `name`.
