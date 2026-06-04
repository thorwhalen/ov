"""Core Web Vitals analyzer: performance-as-UX from the captured ``perf`` artifacts.

Computes INP (group ``event`` entries by ``interactionId``, max duration; 200ms),
CLS (sum ``layout-shift`` values excluding ``hadRecentInput``, already filtered at
capture; 0.1), and LCP/TTFB from the most complete perf snapshot. Per D3, LCP/FCP/
TTFB are **initial-load-only** until the Soft Navigations API lands, so those
findings are labelled provisional. True per-step bucketing by wall-clock window is
a depth item; here metrics are attributed at the page level.
"""

from __future__ import annotations

from typing import Any

from ...base import Finding
from .. import register_analyzer
from ..context import AnalysisContext, AnalyzerOutput
from .severity import make_severity

# metric -> (threshold, unit, impact tier, wcag/none, provisional?)
_THRESHOLDS = {
    "inp": (200.0, "ms", "serious", False),
    "cls": (0.1, "", "serious", False),
    "lcp": (2500.0, "ms", "moderate", True),
    "ttfb": (800.0, "ms", "minor", True),
}


def cwv_from_perf(payload: dict[str, Any]) -> dict[str, float | None]:
    """Reduce one perf payload to ``{inp, cls, lcp, ttfb}`` (pure, testable).

    >>> cwv_from_perf({"vitals": {"inp": [{"duration": 50, "interactionId": 1},
    ...                                    {"duration": 90, "interactionId": 1}],
    ...                            "cls": [{"value": 0.05}, {"value": 0.03}],
    ...                            "lcp": [{"value": 1200}]},
    ...                 "navigation": {"ttfb": 300}})
    {'inp': 90, 'cls': 0.08, 'lcp': 1200, 'ttfb': 300}
    """
    vitals = (payload or {}).get("vitals") or {}
    nav = (payload or {}).get("navigation") or {}

    # INP: max duration per interactionId, then max across interactions.
    by_interaction: dict[Any, float] = {}
    for e in vitals.get("inp", []) or []:
        iid = e.get("interactionId")
        by_interaction[iid] = max(by_interaction.get(iid, 0.0), e.get("duration", 0.0))
    inp = max(by_interaction.values()) if by_interaction else None

    cls_vals = [e.get("value", 0.0) for e in (vitals.get("cls") or [])]
    cls = round(sum(cls_vals), 4) if cls_vals else None

    lcp_vals = [e.get("value", 0.0) for e in (vitals.get("lcp") or [])]
    lcp = max(lcp_vals) if lcp_vals else None

    ttfb = nav.get("ttfb") if nav else None
    return {"inp": inp, "cls": cls, "lcp": lcp, "ttfb": ttfb}


@register_analyzer("cwv", lens="ux", requires=("perf",), produces=("findings",))
def analyze_cwv(ctx: AnalysisContext) -> AnalyzerOutput:
    """Emit performance Findings from the most complete perf snapshot."""
    out = AnalyzerOutput()
    perf_states = ctx.jsons("perf")
    if not perf_states:
        return out

    # Pick the snapshot with the most signal (latest, richest vitals).
    payload = max(perf_states, key=lambda p: len((p.get("vitals") or {}).get("cls", [])) + 1)
    metrics = cwv_from_perf(payload)

    for name, value in metrics.items():
        if value is None:
            continue
        threshold, unit, impact, provisional = _THRESHOLDS[name]
        if value <= threshold:
            continue
        title = f"{name.upper()} {value}{unit} exceeds {threshold}{unit}"
        out.findings.append(
            Finding(
                type="ux_issue",
                signal=f"cwv.{name}",
                category="performance",
                title=title + (" (initial-load, provisional)" if provisional else ""),
                severity=make_severity(impact, nodes=1, journey_fraction=1.0),
                evidence_refs=[a.artifact_id for a in ctx.artifacts("perf")[:1]],
                observed=f"{name.upper()} measured at {value}{unit} (threshold {threshold}{unit})",
                metric_detail={
                    "metric": name, "value": value, "threshold": threshold,
                    "unit": unit, "initial_load_only": provisional,
                },
                suggested_fix=_FIX_HINTS.get(name),
                source_layer="deterministic",
                confidence=1.0,
                needs_human_review=provisional,  # SPA per-route attribution is provisional
            )
        )

    out.summary = {"metrics": metrics}
    return out


_FIX_HINTS = {
    "inp": "reduce main-thread work during interactions (break up long tasks)",
    "cls": "reserve space for late-loading media/ads; avoid layout-shifting injects",
    "lcp": "optimize the largest element's load (preload, compress, prioritize)",
    "ttfb": "reduce server response time / use edge caching",
}
