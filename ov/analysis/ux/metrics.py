"""Journey-metrics analyzer: form friction, backtracking, and journey summary (D3 §5).

Form friction is the headline finding -- conversion drops sharply across the 5-7
field cliff, so forms are scored by field/required count. Backtracking and
dead-ends are read from the journey trace (revisited observation hashes, noop/
error steps). Descriptive journey metrics (steps, distinct states, success) are
surfaced in the analyzer summary for the report's overview section.
"""

from __future__ import annotations

from typing import Any

from selectolax.parser import HTMLParser

from ...base import Finding
from .. import register_analyzer
from ..context import AnalysisContext, AnalyzerOutput
from .severity import make_severity

_NON_FRICTION_TYPES = {"hidden", "submit", "button", "reset", "image"}


def form_friction(field_count: int, required_count: int) -> tuple[str, str] | None:
    """Map a form's field counts to (impact_tier, note) past the 5-field cliff.

    >>> form_friction(3, 2) is None
    True
    >>> form_friction(6, 4)[0]
    'moderate'
    >>> form_friction(10, 8)[0]
    'critical'
    """
    if field_count < 5:
        return None
    if field_count <= 6:
        return "moderate", "past the 5-field friction cliff"
    if field_count <= 9:
        return "serious", "well past the 5-7 field conversion cliff"
    return "critical", "very long form; expect steep abandonment"


def _count_form_fields(form: Any) -> tuple[int, int]:
    fields = form.css("input, select, textarea")
    count = required = 0
    for f in fields:
        if f.tag == "input" and (f.attributes.get("type") or "text") in _NON_FRICTION_TYPES:
            continue
        count += 1
        if "required" in f.attributes or f.attributes.get("aria-required") == "true":
            required += 1
    return count, required


@register_analyzer("journey_metrics", lens="ux", requires=("dom",), produces=("findings",))
def analyze_metrics(ctx: AnalysisContext) -> AnalyzerOutput:
    """Emit form-friction + backtracking Findings and a journey summary."""
    out = AnalyzerOutput()

    # --- form friction (dedupe forms by id/action across states) ---
    seen_forms: set[str] = set()
    for art in ctx.artifacts("dom"):
        tree = HTMLParser(ctx.text(art))
        for i, form in enumerate(tree.css("form"), 1):
            fid = form.attributes.get("id") or form.attributes.get("action") or f"form{i}"
            if fid in seen_forms:
                continue
            seen_forms.add(fid)
            count, required = _count_form_fields(form)
            verdict = form_friction(count, required)
            if verdict is None:
                continue
            impact, note = verdict
            out.findings.append(
                Finding(
                    type="ux_issue",
                    signal="form.friction",
                    category="ux",
                    title=f"Form '{fid}' has {count} fields ({required} required) -- {note}",
                    heuristic="nielsen-6",
                    severity=make_severity(impact, nodes=count, journey_fraction=1.0),
                    evidence_refs=[art.artifact_id],
                    observed=f"form '{fid}': {count} fields, {required} required",
                    metric_detail={"field_count": count, "required_count": required},
                    location={"form": fid},
                    suggested_fix="reduce fields, split into steps, or defer optional inputs",
                    source_layer="deterministic",
                    confidence=1.0,
                )
            )

    # --- backtracking / dead-ends from the journey trace ---
    summary = _journey_summary(ctx.run.steps)
    if summary["revisits"] >= 2:
        out.findings.append(
            Finding(
                type="ux_issue",
                signal="journey.backtracking",
                category="ux",
                title=f"Journey revisited {summary['revisits']} prior state(s)",
                heuristic="nielsen-7",
                severity=make_severity(
                    "moderate", nodes=summary["revisits"],
                    journey_fraction=summary["revisits"] / max(summary["steps"], 1),
                ),
                evidence_refs=[s.id for s in ctx.run.steps[:1]] or ["journey"],
                observed=f"{summary['revisits']} state revisits across {summary['steps']} steps",
                metric_detail=summary,
                suggested_fix="shorten paths to key states; reduce dead-ends",
                source_layer="deterministic",
                confidence=0.8,
                needs_human_review=True,  # whether revisiting is a real problem needs judgment
            )
        )

    out.summary = summary
    return out


def _journey_summary(steps: list[Any]) -> dict[str, Any]:
    hashes = [s.post_obs_hash for s in steps if s.post_obs_hash]
    distinct = len(set(hashes))
    revisits = len(hashes) - distinct
    errors = sum(1 for s in steps if s.outcome == "error")
    noops = sum(1 for s in steps if s.outcome == "noop")
    return {
        "steps": len(steps),
        "distinct_states": distinct,
        "revisits": revisits,
        "errors": errors,
        "noops": noops,
    }
