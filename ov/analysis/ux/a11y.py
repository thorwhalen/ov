"""Accessibility analyzer: WebAIM perennials from the DOM + optional axe mapping.

The deterministic baseline parses each captured DOM state (``selectolax``) and
detects the WebAIM-Million perennials that are computable without a browser or a
GPL engine: missing image ``alt``, empty links, empty buttons, unlabeled form
controls, and missing document language. These are ~96% of *detected* errors
(D3), so nailing them deterministically is high-value and fully testable.

If an ``axe`` artifact exists (an optional in-browser axe-core run at capture
time), its violations are additively mapped to Findings with ``engine_rule_id``
``axe:<id>``. Contrast is handled by :mod:`ov.analysis.ux.contrast_focus` (it
needs computed colors, not static DOM).

**Honesty constraint (D3):** automated tooling catches only ~30-40% of WCAG
issues, so this analyzer always emits one ``undetermined`` finding routing the
non-automatable ~60-70% (meaningful alt text, reading/focus-order logicality,
in-context link text, screen-reader announcement quality, ARIA intent) to
``needs_human_review`` -- never asserting "no automated violations" == accessible.
"""

from __future__ import annotations

from typing import Any

from selectolax.parser import HTMLParser

from ...base import Finding, new_id
from .. import register_analyzer
from ..context import AnalysisContext, AnalyzerOutput
from .severity import make_severity

# signal -> (wcag id, level, impact tier, human label, fix hint)
_PERENNIALS = {
    "a11y.image-alt": ("1.1.1", "A", "critical", "image missing alt attribute",
                       "add an alt attribute (alt=\"\" if decorative)"),
    "a11y.link-name": ("2.4.4", "A", "serious", "link has no discernible text",
                       "give the link text, an aria-label, or a titled child"),
    "a11y.button-name": ("4.1.2", "A", "critical", "button has no accessible name",
                         "add text content or an aria-label to the button"),
    "a11y.form-label": ("1.3.1", "A", "critical", "form control has no associated label",
                        "add a <label for>, aria-label, or aria-labelledby"),
    "a11y.html-lang": ("3.1.1", "A", "serious", "document has no lang attribute",
                       "set <html lang=...> to the page language"),
}


def _acc_name(node: Any) -> str:
    attrs = node.attributes
    parts = [
        (node.text(deep=True) or "").strip(),
        (attrs.get("aria-label") or ""),
        (attrs.get("title") or ""),
        (attrs.get("value") or ""),
    ]
    # an image child's alt counts as the link/button name
    for img in node.css("img"):
        parts.append(img.attributes.get("alt") or "")
    return " ".join(p for p in parts if p).strip()


def _selector(node: Any, idx: int) -> str:
    attrs = node.attributes
    if attrs.get("id"):
        return f"#{attrs['id']}"
    if attrs.get("name"):
        return f"{node.tag}[name={attrs['name']}]"
    return f"{node.tag}:nth-of-type({idx})"


def _has_label(node: Any, label_fors: set[str]) -> bool:
    attrs = node.attributes
    if attrs.get("aria-label") or attrs.get("aria-labelledby") or attrs.get("title"):
        return True
    if attrs.get("id") and attrs["id"] in label_fors:
        return True
    # wrapped in a <label>
    parent = node.parent
    depth = 0
    while parent is not None and depth < 4:
        if parent.tag == "label":
            return True
        parent = parent.parent
        depth += 1
    return False


def _scan_dom(html: str) -> list[dict[str, Any]]:
    """Return raw perennial violations found in one DOM state."""
    tree = HTMLParser(html)
    out: list[dict[str, Any]] = []

    html_node = tree.css_first("html")
    if html_node is not None and not (html_node.attributes.get("lang") or "").strip():
        out.append({"signal": "a11y.html-lang", "selector": "html"})

    for i, img in enumerate(tree.css("img"), 1):
        if "alt" not in img.attributes:  # alt="" is allowed (decorative)
            out.append({"signal": "a11y.image-alt", "selector": _selector(img, i)})

    for i, a in enumerate(tree.css("a[href]"), 1):
        if not _acc_name(a):
            out.append({"signal": "a11y.link-name", "selector": _selector(a, i)})

    for i, b in enumerate(tree.css("button"), 1):
        if not _acc_name(b):
            out.append({"signal": "a11y.button-name", "selector": _selector(b, i)})

    label_fors = {lab.attributes.get("for") for lab in tree.css("label[for]")}
    label_fors.discard(None)
    controls = tree.css("input, select, textarea")
    skip_types = {"hidden", "submit", "button", "reset", "image"}
    for i, c in enumerate(controls, 1):
        if c.tag == "input" and (c.attributes.get("type") or "text") in skip_types:
            continue
        if not _has_label(c, label_fors):
            out.append({"signal": "a11y.form-label", "selector": _selector(c, i)})

    return out


def _manual_review_finding() -> Finding:
    return Finding(
        finding_id=new_id("find"),
        type="undetermined",
        signal="a11y.manual-review-required",
        category="a11y",
        title="Automated a11y coverage is partial -- manual review required",
        observed=(
            "Automated tooling detects only ~30-40% of WCAG issues. The "
            "non-automatable majority (meaningful alt text, reading/focus-order "
            "logicality, in-context link text, screen-reader announcement quality, "
            "ARIA intent) is not asserted here and must be checked by a human / AT."
        ),
        evidence_refs=[],  # an honesty marker, not a cite-or-abstain claim
        source_layer="deterministic",
        confidence=1.0,
        needs_human_review=True,
    )


@register_analyzer("a11y", lens="ux", requires=("dom",), produces=("findings",))
def analyze_a11y(ctx: AnalysisContext) -> AnalyzerOutput:
    """Emit a11y Findings from DOM perennials (+ axe results if captured)."""
    dom_arts = ctx.artifacts("dom")
    num_states = max(len(dom_arts), 1)
    out = AnalyzerOutput()

    # Aggregate perennials across states, deduping by (signal, selector).
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for art in dom_arts:
        for v in _scan_dom(ctx.text(art)):
            key = (v["signal"], v["selector"])
            rec = seen.setdefault(key, {**v, "states": 0, "artifact_id": art.artifact_id})
            rec["states"] += 1

    for (signal, selector), rec in seen.items():
        wcag_id, level, impact, label, fix = _PERENNIALS[signal]
        states = rec["states"]
        out.findings.append(
            Finding(
                type="ux_issue",
                signal=signal,
                category="a11y",
                title=label,
                wcag_criterion={"id": wcag_id, "level": level},
                engine_rule_id=None,
                severity=make_severity(
                    impact, nodes=1, states_affected=states,
                    journey_fraction=states / num_states,
                ),
                evidence_refs=[rec["artifact_id"]],
                observed=f"{label} ({selector})",
                location={"selector": selector, "states_affected": states},
                suggested_fix=fix,
                source_layer="deterministic",
                confidence=1.0,
                needs_human_review=False,
            )
        )

    out.findings.extend(_map_axe(ctx, num_states))
    out.findings.append(_manual_review_finding())
    out.summary = {
        "perennial_findings": len(seen),
        "states_scanned": len(dom_arts),
        "axe_present": bool(ctx.artifacts("axe")),
    }
    return out


def _map_axe(ctx: AnalysisContext, num_states: int) -> list[Finding]:
    """Map optional captured axe-core violations to Findings (additive)."""
    findings: list[Finding] = []
    for art in ctx.artifacts("axe"):
        data = ctx.json(art) or {}
        for v in data.get("violations", []):
            nodes = v.get("nodes", [])
            findings.append(
                Finding(
                    type="ux_issue",
                    signal=f"axe.{v.get('id', 'unknown')}",
                    category="a11y",
                    title=v.get("help", v.get("id", "axe violation")),
                    wcag_criterion={"tags": [t for t in v.get("tags", []) if t.startswith("wcag")]},
                    engine_rule_id=f"axe:{v.get('id')}",
                    severity=make_severity(
                        v.get("impact", "moderate"),
                        nodes=max(len(nodes), 1),
                        journey_fraction=1.0 / num_states,
                    ),
                    evidence_refs=[art.artifact_id],
                    observed=v.get("description", ""),
                    location={"targets": [n.get("target") for n in nodes][:10]},
                    suggested_fix=v.get("helpUrl"),
                    source_layer="deterministic",
                    confidence=1.0,
                )
            )
    return findings
