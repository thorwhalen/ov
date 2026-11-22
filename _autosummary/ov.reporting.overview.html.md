# ov.reporting.overview

The `overview` one-liner: observe -> analyze -> report -> synopsis (§4).

This is the pit-of-success entry point behind [`ov.overview()`](ov.html.md#ov.overview). It threads a
single store through capture, the deterministic analyzers, report rendering, and
the synopsis, returning the synopsis path/key. No model is involved.

### Functions

| [`run_overview`](#ov.reporting.overview.run_overview)(url, \*[, headed, mode, probes, ...])   | Run the full deterministic pipeline and return the synopsis path/key.   |
|-------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------|

### ov.reporting.overview.run_overview(url, , headed=False, mode='reconstruct', probes='default', store=None, out_dir=None, authorized=None, lenses=('ux', 'arch'), baseline=None, \*\*observe_kw)

Run the full deterministic pipeline and return the synopsis path/key.

In `mode="review"` it inserts an own-target diff step between analysis and
reporting: the run is compared against a stored prior baseline (`baseline`,
or the latest prior run of the same target) so the review report and synopsis
carry regression/drift detail. A first review run (no baseline) is a no-op.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
