"""Performance probe: Navigation Timing, paint, web-vitals entries, CDP counters.

An init script installs ``PerformanceObserver``s that accumulate layout-shift and
event-timing entries onto ``window.__ov_perf`` (so per-step CWV attribution is
possible downstream); at each captured state the probe reads those plus the
Navigation Timing and paint entries, and -- on Chromium -- ``Performance.getMetrics``
via CDP. Web-vitals *attribution* (naming the offending element) is refined in the
``cwv`` analyzer; this probe captures the raw entries deterministically.
"""

from __future__ import annotations

import json
from typing import Any

from ...base import Artifact
from . import Probe, ProbeContext, register_probe

_PERF_HOOK = r"""
(() => {
  if (window.__ov_perf_installed) return;
  window.__ov_perf_installed = true;
  window.__ov_perf = {cls: [], inp: [], lcp: []};
  try {
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) {
        if (!e.hadRecentInput) window.__ov_perf.cls.push({value: e.value, t: e.startTime});
      }
    }).observe({type: 'layout-shift', buffered: true});
  } catch (e) {}
  try {
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) {
        window.__ov_perf.inp.push({duration: e.duration, name: e.name, t: e.startTime,
                                   interactionId: e.interactionId});
      }
    }).observe({type: 'event', buffered: true, durationThreshold: 16});
  } catch (e) {}
  try {
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) window.__ov_perf.lcp.push({value: e.startTime, size: e.size});
    }).observe({type: 'largest-contentful-paint', buffered: true});
  } catch (e) {}
})();
"""

_READ_JS = r"""
() => {
  const nav = performance.getEntriesByType('navigation')[0];
  const paints = {};
  for (const p of performance.getEntriesByType('paint')) paints[p.name] = p.startTime;
  return {
    navigation: nav ? {
      ttfb: nav.responseStart, domContentLoaded: nav.domContentLoadedEventEnd,
      load: nav.loadEventEnd, duration: nav.duration, transferSize: nav.transferSize,
    } : null,
    paints: paints,
    vitals: window.__ov_perf || null,
    resourceCount: performance.getEntriesByType('resource').length,
  };
}
"""


@register_probe("perf", produces=("perf",))
class PerfProbe(Probe):
    """Snapshot timing + web-vitals entries + CDP counters per captured state."""

    name = "perf"

    def attach(self, ctx: ProbeContext) -> None:
        if ctx.page is not None:
            try:
                ctx.page.add_init_script(_PERF_HOOK)
            except Exception:  # noqa: BLE001
                pass

    def capture(self, ctx: ProbeContext) -> list[Artifact]:
        page = ctx.page
        if page is None:
            return []
        payload: dict[str, Any] = {}
        try:
            payload = page.evaluate(_READ_JS)
        except Exception:  # noqa: BLE001
            payload = {}
        if ctx.cdp is not None:
            try:
                payload["cdp_metrics"] = ctx.cdp.get_performance_metrics()
            except Exception:  # noqa: BLE001
                pass
        art = ctx.store.put_artifact(
            json.dumps(payload, indent=2).encode("utf-8"),
            kind="perf",
            step_id=ctx.step.id if ctx.step else None,
            content_type="application/json",
            meta={"url": page.url},
        )
        return [art]
