"""Heuristic analyzer: the automatable subset of Nielsen / cognitive-walkthrough (D3 §6).

Each heuristic maps to a machine-observable signal computed from the journey
trace + console + DOM:

* **console-error-on-step** -- a console error emitted during a step (robustness).
* **missing feedback (Nielsen H1 / CW Q4)** -- a ``click`` whose post-observation
  hash is unchanged with no console/network delta (no visible response).
* **live-region presence (WCAG 4.1.3)** -- dynamic states but no ``aria-live`` /
  ``role=status`` region to announce them.

The Operator's per-step *intent* is the cognitive-walkthrough ground truth for
"expected action", so a noop on an intentful click is a meaningful signal.
"""

from __future__ import annotations

from typing import Any

from selectolax.parser import HTMLParser

from ...base import Finding
from .. import register_analyzer
from ..context import AnalysisContext, AnalyzerOutput
from .severity import make_severity


@register_analyzer(
    "heuristics", lens="ux", requires=("console", "dom"), produces=("findings",)
)
def analyze_heuristics(ctx: AnalysisContext) -> AnalyzerOutput:
    """Emit Findings for console-on-step, missing feedback, and live-region absence."""
    out = AnalyzerOutput()
    steps = ctx.run.steps
    num_steps = max(len(steps), 1)

    # --- console errors grouped by step ---
    errors_by_step: dict[str | None, list[str]] = {}
    for entries in ctx.jsons("console"):
        for e in entries or []:
            if e.get("type") == "error" or e.get("kind") == "pageerror":
                errors_by_step.setdefault(e.get("step_id"), []).append(
                    e.get("text", "")[:160]
                )

    for step in steps:
        msgs = errors_by_step.get(step.id)
        if not msgs:
            continue
        out.findings.append(
            Finding(
                type="ux_issue",
                signal="heuristic.console-error",
                category="robustness",
                title=f"Console error during step '{step.intent}'",
                heuristic="nielsen-5",
                severity=make_severity(
                    "serious", nodes=len(msgs), journey_fraction=1.0 / num_steps
                ),
                evidence_refs=[step.id],
                observed="; ".join(msgs[:3]),
                location={"step_id": step.id, "intent": step.intent},
                suggested_fix="fix the underlying JS error; surface a user-facing recovery if relevant",
                source_layer="deterministic",
                confidence=1.0,
            )
        )

    # --- missing feedback: intentful click that produced a noop ---
    for step in steps:
        if (
            step.action is not None
            and step.action.type == "click"
            and step.outcome == "noop"
            and step.network_delta == 0
        ):
            out.findings.append(
                Finding(
                    type="ux_issue",
                    signal="heuristic.no-feedback",
                    category="ux",
                    title=f"Click produced no visible change ('{step.intent}')",
                    heuristic="nielsen-1",
                    severity=make_severity(
                        "moderate", nodes=1, journey_fraction=1.0 / num_steps
                    ),
                    evidence_refs=[step.id],
                    observed="click did not change the observed state and triggered no network activity",
                    location={"step_id": step.id, "intent": step.intent},
                    suggested_fix="provide immediate visual feedback (state change, spinner, message)",
                    source_layer="deterministic",
                    confidence=0.7,
                    needs_human_review=True,  # could be intentional (e.g. toggling identical state)
                )
            )

    # --- live-region presence (only flag if the journey had dynamic changes) ---
    had_dynamic = any(
        s.outcome == "ok" and s.action and s.action.type == "click" for s in steps
    )
    has_live_region = any(
        HTMLParser(ctx.text(art)).css_first("[aria-live], [role=status], [role=alert]")
        is not None
        for art in ctx.artifacts("dom")
    )
    if had_dynamic and not has_live_region and ctx.artifacts("dom"):
        out.findings.append(
            Finding(
                type="undetermined",
                signal="heuristic.no-live-region",
                category="a11y",
                title="No ARIA live region found for a dynamic UI",
                heuristic="cw-q4",
                wcag_criterion={"id": "4.1.3", "level": "AA"},
                severity=make_severity("moderate", nodes=1, journey_fraction=1.0),
                evidence_refs=[ctx.artifacts("dom")[0].artifact_id],
                observed="interactions changed the UI but no aria-live/role=status region was present",
                suggested_fix="announce dynamic updates via an aria-live or role=status region",
                source_layer="deterministic",
                confidence=0.6,
                needs_human_review=True,
            )
        )

    out.summary = {"steps_with_console_errors": len(errors_by_step)}
    return out
