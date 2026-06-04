"""Framework / bundler / state-management / routing enrichment (D2 §5).

The ``fingerprint`` probe already detected frameworks from runtime globals; this
analyzer enriches the picture from the *bundle text* (bundler + state-management
signatures) and reconstructs a client routing map from ``<a href>`` links. New
:class:`~ov.base.TechFinding`s are merged into ``run.fingerprint`` (dedup by name,
max confidence); the routing map is surfaced for the architecture report.
"""

from __future__ import annotations

from urllib.parse import urlparse

from selectolax.parser import HTMLParser

from ...base import Finding, TechFinding
from .. import register_analyzer
from ..context import AnalysisContext, AnalyzerOutput
from .bundles import js_response_bodies

# signature substring -> (name, categories, confidence)
_BUNDLER_SIGNATURES = {
    "__webpack_require__": ("webpack", ["bundler"], 85),
    "webpackChunk": ("webpack", ["bundler"], 80),
    "import.meta.hot": ("Vite", ["bundler"], 80),
    "/@vite/client": ("Vite", ["bundler"], 90),
    "__turbopack": ("Turbopack", ["bundler"], 80),
    "__esm(": ("esbuild", ["bundler"], 70),
    "__commonJS(": ("esbuild", ["bundler"], 65),
}
_STATE_SIGNATURES = {
    "zustand": ("Zustand", ["state-management"], 70),
    "createStore": ("Redux", ["state-management"], 55),
    "recoil": ("Recoil", ["state-management"], 65),
    "pinia": ("Pinia", ["state-management"], 70),
    "vuex": ("Vuex", ["state-management"], 70),
}
_MAX_SCAN_CHARS = 2_000_000  # cap total bundle text scanned


@register_analyzer(
    "framework", lens="arch", requires=("network", "dom"), produces=("tech",)
)
def analyze_framework(ctx: AnalysisContext) -> AnalyzerOutput:
    """Detect bundler + state-management from bundles; reconstruct the route map."""
    out = AnalyzerOutput()
    blob = []
    total = 0
    for _url, text in js_response_bodies(ctx):
        blob.append(text)
        total += len(text)
        if total >= _MAX_SCAN_CHARS:
            break
    corpus = "\n".join(blob)

    detected: dict[str, TechFinding] = {}
    for sig, (name, cats, conf) in {**_BUNDLER_SIGNATURES, **_STATE_SIGNATURES}.items():
        if sig in corpus:
            prior = detected.get(name)
            if prior is None or conf > prior.confidence:
                detected[name] = TechFinding(
                    name=name,
                    categories=cats,
                    confidence=conf,
                    provenance=[f"bundle-signature:{sig}"],
                )
    out.tech = list(detected.values())

    routes = _route_map(ctx)
    if out.tech:
        out.findings.append(
            Finding(
                type="arch_fact",
                signal="arch.build_tooling",
                category="architecture",
                title="Build tooling / state management: "
                + ", ".join(sorted(detected)),
                evidence_refs=[a.artifact_id for a in ctx.artifacts("network")[:1]]
                or ["network"],
                observed="; ".join(f"{t.name} ({t.confidence})" for t in out.tech),
                source_layer="deterministic",
                confidence=0.8,
            )
        )
    if routes:
        out.findings.append(
            Finding(
                type="arch_fact",
                signal="arch.routing_map",
                category="architecture",
                title=f"{len(routes)} client route(s) discovered",
                evidence_refs=[a.artifact_id for a in ctx.artifacts("dom")[:1]]
                or ["dom"],
                observed="routes: " + ", ".join(sorted(routes)[:20]),
                metric_detail={"routes": sorted(routes)},
                source_layer="deterministic",
                confidence=0.7,
            )
        )
    out.summary = {"build_tools": sorted(detected), "routes": sorted(routes)}
    return out


def _route_map(ctx: AnalysisContext) -> set[str]:
    """Collect same-origin client routes from ``<a href>`` across DOM states."""
    routes: set[str] = set()
    target_host = urlparse(ctx.run.target_url).netloc
    for art in ctx.artifacts("dom"):
        for a in HTMLParser(ctx.text(art)).css("a[href]"):
            href = a.attributes.get("href") or ""
            if (
                href.startswith("#")
                or href.startswith("javascript:")
                or href.startswith("mailto:")
            ):
                continue
            parsed = urlparse(href)
            if parsed.netloc and parsed.netloc != target_host:
                continue  # external link
            path = parsed.path or "/"
            if path:
                routes.add(path)
    return routes
