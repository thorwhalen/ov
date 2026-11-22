# ov.analysis.evidence

The evidence-bundle assembler (§8.1, D4) – deterministic, model-free.

Builds the grounded bundle a vision LLM (the host) reasons over, so token cost and
grounding are *computed*, not hoped for:

* **Set-of-Mark** – each discussable region (a step’s affordances) gets a stable
  mark id (`R1` …) that is overlaid on the screenshot, appears in the facts,
  and is *required* in the model’s output. This turns “describe what you see” into
  “interpret marked region R3”.
* **Order** – the bundle is `[role/system + cite-or-abstain] -> [marked image(s)]
  -> [facts keyed to ids] -> [task last]`.
* **Token budget** – projected as `Σ(w×h/750)` per image against the model cap
  (≈1568 px / 1568 tok standard; ≈2576 px / 4784 tok on Opus 4.7/4.8) *before* the
  call; images are downsampled to fit.
* **Omit raw bytes** – facts are *derived summaries*, never raw HAR/DOM/bundle
  text; those stay reachable by `evidence_id` for just-in-time retrieval.

The actual image overlay needs Pillow (the `evidence` extra); everything else
(dimensions, budget, mark assignment, the bundle structure) is pure stdlib so the
budget math and grounding are testable without it.

### Module Attributes

| [`MODEL_CAPS`](#ov.analysis.evidence.MODEL_CAPS)   | (long-edge pixels, token cap).   |
|---------------------------------------------------------------|----------------------------------|

### Functions

| [`build_evidence_bundle`](#ov.analysis.evidence.build_evidence_bundle)(run, store, \*[, ...])   | Assemble a grounded [`EvidenceBundle`](ov.base.html.md#ov.base.EvidenceBundle) for a step (model-free).   |
|-------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------|
| [`fit_to_cap`](#ov.analysis.evidence.fit_to_cap)(width, height[, model])             | Project tokens and a downsample factor to fit a model's image cap (pure).                                                             |
| [`image_token_cost`](#ov.analysis.evidence.image_token_cost)(width, height)                | Anthropic image token estimate `ceil(w*h/750)`.                                                                                       |
| [`png_dimensions`](#ov.analysis.evidence.png_dimensions)(data)                           | Return `(width, height)` of a PNG from its IHDR header (stdlib only).                                                                 |

### ov.analysis.evidence.MODEL_CAPS *: [dict](https://docs.python.org/3/builtins/stdtypes.html#dict)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[int](https://docs.python.org/3/builtins/functions.html#int), [int](https://docs.python.org/3/builtins/functions.html#int)]]* *= {'opus': (2576, 4784), 'standard': (1568, 1568)}*

(long-edge pixels, token cap). Opus 4.7/4.8 are larger.

* **Type:**
  Per-model image caps

### ov.analysis.evidence.build_evidence_bundle(run, store, , step_id=None, model='opus', task='Assess UX and architecture; cite marks/facts for every claim.', max_marks=20, overlay=True, out_dir=None)

Assemble a grounded [`EvidenceBundle`](ov.base.html.md#ov.base.EvidenceBundle) for a step (model-free).

Marks are drawn from the step’s affordances (which carry bounding boxes);
facts include those marked regions plus the deterministic findings touching the
step. The token budget is computed against `model`’s cap. When Pillow is
available and `overlay` is set, a numbered overlay screenshot (and crops for
small regions) are rendered and stored; otherwise the original screenshot is
referenced and a note is recorded.

* **Return type:**
  [`EvidenceBundle`](ov.base.html.md#ov.base.EvidenceBundle)

### ov.analysis.evidence.fit_to_cap(width, height, model='opus')

Project tokens and a downsample factor to fit a model’s image cap (pure).

Honors BOTH constraints – the long-edge pixel cap *and* the token (area) cap
– taking whichever is more restrictive, because a long-edge-only clamp can
still blow the token budget (a 2576x2576 image is ~8853 tokens).

```pycon
>>> r = fit_to_cap(5000, 4000, "opus")
>>> r["downsampled"] and r["fitted"]["tokens"] <= 4784
True
>>> fit_to_cap(800, 600, "opus")["downsampled"]
False
```

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

### ov.analysis.evidence.image_token_cost(width, height)

Anthropic image token estimate `ceil(w*h/750)`.

```pycon
>>> image_token_cost(1000, 1000)
1334
```

* **Return type:**
  [`int`](https://docs.python.org/3/builtins/functions.html#int)

### ov.analysis.evidence.png_dimensions(data)

Return `(width, height)` of a PNG from its IHDR header (stdlib only).

```pycon
>>> import base64
>>> px = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==')
>>> png_dimensions(px)
(1, 1)
```

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int)] | [`None`](https://docs.python.org/3/builtins/constants.html#None)
