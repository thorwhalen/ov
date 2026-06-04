"""Contrast + focus analyzer (deterministic, no engine).

Contrast ratios are computed from the captured ``a11y_styles`` artifact (effective
fg/bg colors) with the exact WCAG relative-luminance formula and the 4.5:1 normal
/ 3:1 large+UI thresholds (D3 §3). Focus issues that are statically detectable
(positive ``tabindex``) are flagged from the DOM; the genuinely behavioral focus
properties (keyboard traps, focus-order *logicality*, visible-focus indicator)
need active key-driving and are routed to ``needs_human_review`` rather than
asserted -- the honesty constraint again.
"""

from __future__ import annotations

from typing import Any

from selectolax.parser import HTMLParser

from ...base import Finding, new_id
from .. import register_analyzer
from ..context import AnalysisContext, AnalyzerOutput
from .severity import make_severity


def _linearize(channel_0_255: float) -> float:
    c = channel_0_255 / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: list[float] | tuple[float, ...]) -> float:
    """WCAG relative luminance of an sRGB ``(r, g, b)`` in 0-255.

    >>> relative_luminance([255, 255, 255])
    1.0
    >>> relative_luminance([0, 0, 0])
    0.0
    """
    r, g, b = (_linearize(c) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: list[float], bg: list[float]) -> float:
    """WCAG contrast ratio between two sRGB colors (>=1.0).

    >>> contrast_ratio([0, 0, 0], [255, 255, 255])
    21.0
    >>> round(contrast_ratio([255, 255, 255], [255, 255, 255]), 1)
    1.0
    """
    l1, l2 = relative_luminance(fg), relative_luminance(bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return round((lighter + 0.05) / (darker + 0.05), 2)


@register_analyzer(
    "contrast_focus", lens="ux", requires=("a11y_styles", "dom"), produces=("findings",)
)
def analyze_contrast_focus(ctx: AnalysisContext) -> AnalyzerOutput:
    """Emit contrast Findings + statically-detectable focus Findings."""
    out = AnalyzerOutput()
    style_states = ctx.jsons("a11y_styles")
    num_states = max(len(style_states), 1)

    # Contrast: dedupe by selector across states.
    seen: dict[str, dict[str, Any]] = {}
    for state in style_states:
        for rec in state or []:
            fg, bg = rec.get("fg"), rec.get("bg")
            if not fg or not bg:
                continue
            ratio = contrast_ratio(fg, bg)
            threshold = 3.0 if rec.get("large") else 4.5
            if ratio < threshold:
                key = rec.get("selector", "?")
                prior = seen.get(key)
                if prior is None or ratio < prior["ratio"]:
                    seen[key] = {
                        "ratio": ratio,
                        "threshold": threshold,
                        "text": rec.get("text", ""),
                        "states": 0,
                    }
                seen[key]["states"] += 1

    for selector, rec in seen.items():
        out.findings.append(
            Finding(
                type="ux_issue",
                signal="contrast.text",
                category="a11y",
                title=f"Low text contrast ({rec['ratio']}:1 < {rec['threshold']}:1)",
                wcag_criterion={"id": "1.4.3", "level": "AA"},
                engine_rule_id=None,
                severity=make_severity(
                    "serious",
                    nodes=1,
                    states_affected=rec["states"],
                    journey_fraction=rec["states"] / num_states,
                ),
                evidence_refs=[a.artifact_id for a in ctx.artifacts("a11y_styles")[:1]],
                observed=f"text {rec['text']!r} has contrast {rec['ratio']}:1 (needs {rec['threshold']}:1)",
                metric_detail={"ratio": rec["ratio"], "threshold": rec["threshold"]},
                location={"selector": selector},
                suggested_fix="increase the contrast between text and its background",
                source_layer="deterministic",
                confidence=1.0,
            )
        )

    out.findings.extend(_static_focus_findings(ctx, num_states))
    out.findings.append(_focus_manual_finding())
    out.summary = {"low_contrast_nodes": len(seen), "style_states": len(style_states)}
    return out


def _static_focus_findings(ctx: AnalysisContext, num_states: int) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[str] = set()
    for art in ctx.artifacts("dom"):
        tree = HTMLParser(ctx.text(art))
        for el in tree.css("[tabindex]"):
            try:
                ti = int(el.attributes.get("tabindex", "0"))
            except ValueError:
                continue
            if ti > 0:
                sel = f"{el.tag}[tabindex={ti}]"
                if sel in seen:
                    continue
                seen.add(sel)
                findings.append(
                    Finding(
                        type="ux_issue",
                        signal="focus.tabindex-positive",
                        category="a11y",
                        title="Positive tabindex disrupts natural focus order",
                        wcag_criterion={"id": "2.4.3", "level": "A"},
                        severity=make_severity(
                            "moderate", nodes=1, journey_fraction=1.0 / num_states
                        ),
                        evidence_refs=[art.artifact_id],
                        observed=f"element {sel} uses a positive tabindex",
                        location={"selector": sel},
                        suggested_fix="use tabindex=0 (or rely on DOM order) instead of a positive value",
                        source_layer="deterministic",
                        confidence=1.0,
                    )
                )
    return findings


def _focus_manual_finding() -> Finding:
    return Finding(
        finding_id=new_id("find"),
        type="undetermined",
        signal="focus.behavioral-review-required",
        category="a11y",
        title="Keyboard behavior needs interactive review",
        observed=(
            "Keyboard traps, focus-order logicality, and visible-focus-indicator "
            "quality require active key-driving and human judgment; not asserted here."
        ),
        evidence_refs=[],
        source_layer="deterministic",
        confidence=1.0,
        needs_human_review=True,
    )
