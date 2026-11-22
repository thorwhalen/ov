# ov.capture.probes.a11y

Accessibility-signals probe: computed text styles (for contrast) + optional axe.

Contrast cannot be judged from static DOM – it needs *computed* colors. This
probe snapshots, per visible text element, the effective foreground/background
colors, font size/weight, and bbox, so the deterministic
[`ov.analysis.ux.contrast_focus`](ov.analysis.ux.contrast_focus.html.md#module-ov.analysis.ux.contrast_focus) analyzer can compute WCAG ratios offline.

If an axe-core bundle is resolvable (`OV_AXE_PATH` or the sidecar’s
`node_modules/axe-core/axe.min.js`), it is injected and `axe.run()` results
are stored as an `axe` artifact – additive, never required. axe-core is used
as an external tool here (no vendoring), keeping the package license-clean.

### Classes

| [`A11yProbe`](#ov.capture.probes.a11y.A11yProbe)()   | Capture computed text styles (always) + axe-core results (when available).   |
|----------------------------------------------------------------|------------------------------------------------------------------------------|

### *class* ov.capture.probes.a11y.A11yProbe

Bases: [`Probe`](ov.capture.probes.html.md#ov.capture.probes.Probe)

Capture computed text styles (always) + axe-core results (when available).

#### capture(ctx)

Snapshot current state into artifacts. Default: nothing.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Artifact`](ov.base.html.md#ov.base.Artifact)]
