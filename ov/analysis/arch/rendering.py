"""Rendering-model classifier: CSR vs SSR/SSG via raw-HTML-vs-rendered-DOM diff (D2).

The deterministic test compares the *server-sent* HTML (the captured document
response body, pre-JS) against the *rendered* DOM (post-JS). A large divergence
=> CSR (server sends a shell, JS builds the page); near-identity => SSR/SSG. This
is computed entirely from captured artifacts -- no re-fetch -- so it stays
hermetic. State-injection globals (``__NEXT_DATA__``/``__NUXT__``/``__remixContext``)
corroborate SSR/SSG. SSG vs SSR needs multiple requests and is left as a refinement.
"""

from __future__ import annotations

from typing import Any

from selectolax.parser import HTMLParser

from ...base import Finding, Scored
from .. import register_analyzer
from ..context import AnalysisContext, AnalyzerOutput

# Classification thresholds + confidences (named so the heuristic is auditable).
_MIN_SERVER_WORDS = 40  # below this, the server sent ~a shell
_CSR_DIVERGENCE = 0.7  # rendered >> server  => CSR
_SSR_DIVERGENCE = 0.3  # rendered ~= server  => SSR/SSG
_CONF_UNKNOWN = 20
_CONF_CSR = 85
_CONF_SSR = 80
_CONF_HYBRID = 60
_CONF_MAX = 95
_INJECTION_BOOST = 10  # boost when a state-injection global corroborates SSR/SSG


def _visible_text_len(html: str) -> int:
    """Word count of visible text (scripts/styles stripped) -- the diff signal."""
    tree = HTMLParser(html or "")
    for node in tree.css("script, style, noscript"):
        node.decompose()
    body = tree.body or tree.root
    text = body.text(separator=" ") if body is not None else ""
    return len(text.split())


def classify_rendering(
    raw_html: str, rendered_html: str, globals_present: dict[str, bool] | None = None
) -> tuple[str, int, str]:
    """Classify the rendering model from raw vs rendered HTML (pure, testable).

    Returns ``(model, confidence_0_100, rationale)`` where model is one of
    ``csr`` | ``ssr-or-ssg`` | ``hybrid`` | ``unknown``.

    >>> classify_rendering("<html><body><div id=root></div></body></html>",
    ...                    "<html><body><div id=root><h1>Hi</h1><p>lots of text here</p></div></body></html>")[0]
    'csr'
    """
    raw_len = _visible_text_len(raw_html or "")
    rendered_len = _visible_text_len(rendered_html or "")
    globals_present = globals_present or {}
    has_injection = any(
        globals_present.get(k)
        for k in ("__NEXT_DATA__", "__NUXT__", "__remixContext", "__gatsby")
    )

    if rendered_len == 0:
        return "unknown", _CONF_UNKNOWN, "no rendered text to compare"
    divergence = (rendered_len - raw_len) / rendered_len

    if raw_len < _MIN_SERVER_WORDS and divergence > _CSR_DIVERGENCE:
        model, conf = "csr", _CONF_CSR
        rationale = f"server HTML had ~{raw_len} words, rendered ~{rendered_len} (divergence {divergence:.0%})"
    elif divergence < _SSR_DIVERGENCE:
        model, conf = "ssr-or-ssg", _CONF_SSR
        rationale = f"server HTML matched the rendered DOM closely (divergence {divergence:.0%})"
    else:
        model, conf = "hybrid", _CONF_HYBRID
        rationale = (
            f"partial server markup, hydrated client-side (divergence {divergence:.0%})"
        )

    if has_injection and model in ("ssr-or-ssg", "hybrid"):
        conf = min(_CONF_MAX, conf + _INJECTION_BOOST)
        rationale += "; state-injection global present"
    elif has_injection and model == "csr":
        rationale += "; note: framework global present despite empty shell"
    return model, conf, rationale


def _document_bodies(ctx: AnalysisContext) -> list[str]:
    """Server-sent HTML bodies (document responses) from the network records."""
    body_arts = {a.artifact_id: a for a in ctx.artifacts("request")}
    htmls: list[str] = []
    for records in ctx.jsons("network"):
        for rec in records or []:
            if rec.get("resource_type") == "document" and rec.get("body_artifact_id"):
                art = body_arts.get(rec["body_artifact_id"])
                if art is not None:
                    htmls.append(ctx.text(art))
    return htmls


@register_analyzer(
    "rendering", lens="arch", requires=("dom", "network"), produces=("rendering_model",)
)
def analyze_rendering(ctx: AnalysisContext) -> AnalyzerOutput:
    """Set ``run.rendering_model`` and emit an arch_fact Finding."""
    out = AnalyzerOutput()
    dom_arts = ctx.artifacts("dom")
    raw_htmls = _document_bodies(ctx)
    if not dom_arts or not raw_htmls:
        out.summary = {
            "rendering_model": None,
            "reason": "missing document body or DOM",
        }
        return out

    fp = ctx.jsons("fingerprint")
    globals_present = (fp[0].get("signals", {}).get("globals") if fp else {}) or {}
    model, conf, rationale = classify_rendering(
        raw_htmls[0], ctx.text(dom_arts[0]), globals_present
    )
    out.run_fields["rendering_model"] = model
    out.findings.append(
        Finding(
            type="arch_fact",
            signal="arch.rendering_model",
            category="architecture",
            title=f"Rendering model: {model}",
            severity=None,
            evidence_refs=[dom_arts[0].artifact_id],
            observed=rationale,
            judgment=None,
            metric_detail={"model": model, "confidence": conf},
            source_layer="deterministic",
            confidence=conf / 100.0,
        )
    )
    out.summary = {"rendering_model": model, "confidence": conf, "rationale": rationale}
    return out


def rendering_scored(model: str, confidence: int, provenance: list[str]) -> Scored:
    """Wrap a rendering classification as a :class:`Scored` fact (helper)."""
    return Scored(confidence=confidence, provenance=provenance)
