"""Source-map detection + (optional) recovery -- the decisive bimodal lever (D2).

Reconstruction quality is bimodal: WITH source maps you recover the original file
tree, source text, and ``node_modules`` version paths; WITHOUT them you get a
beautified-but-renamed approximation. So this analyzer detects map presence from
the captured JS bodies and asset URLs and sets ``source_maps_present`` (which
gates downstream reconstruction confidence everywhere). If the Node sidecar is
available and a ``.map`` body was captured, it recovers the file tree too.
"""

from __future__ import annotations

from typing import Any

from ...base import Finding
from .. import register_analyzer
from ..context import AnalysisContext, AnalyzerOutput

_MAP_MARKERS = ("//# sourceMappingURL=", "//@ sourceMappingURL=")


def js_response_bodies(ctx: AnalysisContext) -> list[tuple[str, str]]:
    """Return ``(url, text)`` for captured JS response bodies (reused across arch)."""
    body_arts = {a.artifact_id: a for a in ctx.artifacts("request")}
    out: list[tuple[str, str]] = []
    for records in ctx.jsons("network"):
        for rec in records or []:
            ct = (rec.get("response_headers") or {}).get("content-type", "")
            is_js = rec.get("resource_type") == "script" or "javascript" in ct
            if is_js and rec.get("body_artifact_id") in body_arts:
                out.append(
                    (rec.get("url", ""), ctx.text(body_arts[rec["body_artifact_id"]]))
                )
    return out


def detect_source_maps(
    js_bodies: list[tuple[str, str]], asset_urls: list[str]
) -> tuple[bool, list[str]]:
    """Detect source-map presence from JS bodies + asset urls (pure, testable).

    >>> detect_source_maps([("a.js", "x=1\\n//# sourceMappingURL=a.js.map")], [])[0]
    True
    >>> detect_source_maps([("a.js", "x=1")], ["https://x/b.js.map"])[0]
    True
    >>> detect_source_maps([("a.js", "x=1")], [])[0]
    False
    """
    evidence: list[str] = []
    for url, text in js_bodies:
        tail = text[-2000:]
        if any(m in tail for m in _MAP_MARKERS):
            evidence.append(f"sourceMappingURL in {url or 'bundle'}")
    for u in asset_urls:
        if u.endswith(".map"):
            evidence.append(f"served map asset {u}")
    return bool(evidence), evidence


@register_analyzer(
    "bundles", lens="arch", requires=("network",), produces=("source_maps_present",)
)
def analyze_bundles(ctx: AnalysisContext) -> AnalyzerOutput:
    """Set ``run.source_maps_present`` and emit an arch_fact (+ optional recovery)."""
    out = AnalyzerOutput()
    js_bodies = js_response_bodies(ctx)
    asset_urls: list[str] = []
    for inv in ctx.jsons("assets"):
        asset_urls.extend(a.get("url", "") for a in (inv or []))

    present, evidence = detect_source_maps(js_bodies, asset_urls)
    out.run_fields["source_maps_present"] = present

    recovered_files = 0
    if present:
        recovered_files = _try_recover(ctx, asset_urls)

    out.findings.append(
        Finding(
            type="arch_fact",
            signal="arch.source_maps",
            category="architecture",
            title=f"Source maps {'present' if present else 'absent'}",
            evidence_refs=[a.artifact_id for a in ctx.artifacts("network")[:1]]
            or ["network"],
            observed=(
                "; ".join(evidence[:5])
                if present
                else "no sourceMappingURL markers or .map assets found"
            ),
            metric_detail={
                "source_maps_present": present,
                "recovered_files": recovered_files,
            },
            judgment=None,
            source_layer="deterministic",
            confidence=0.9 if present else 0.6,
        )
    )
    out.summary = {"source_maps_present": present, "recovered_files": recovered_files}
    return out


def _try_recover(ctx: AnalysisContext, asset_urls: list[str]) -> int:
    """Best-effort source-map recovery via the sidecar; returns files recovered."""
    body_arts = {a.artifact_id: a for a in ctx.artifacts("request")}
    map_texts: list[str] = []
    for records in ctx.jsons("network"):
        for rec in records or []:
            if (
                rec.get("url", "").endswith(".map")
                and rec.get("body_artifact_id") in body_arts
            ):
                map_texts.append(ctx.text(body_arts[rec["body_artifact_id"]]))
    if not map_texts:
        return 0
    try:
        from .sidecar import Sidecar, SidecarUnavailable

        sc = Sidecar()
        if not sc.available():
            return 0
        total = 0
        with sc:
            for mt in map_texts[:5]:
                try:
                    result = sc.consume_source_map(mt)
                    total += len(result.get("files", []))
                except SidecarUnavailable:
                    break
        return total
    except Exception:  # noqa: BLE001
        return 0
