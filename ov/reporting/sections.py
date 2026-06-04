"""The default report sections (§8.3) -- each a registered Markdown fragment.

A section is ``fn(run, analyses) -> str``. Sections are registered with an
``order`` (numeric prefix) and the ``modes`` they apply to (reconstruct/review),
so :mod:`ov.reporting.render` can select and concatenate them. They read the
already-analyzed :class:`~ov.base.CaptureRun` (findings, fingerprint, api_surface,
rendering_model, ...) plus the per-analyzer summaries -- no model involved.
"""

from __future__ import annotations

from typing import Any

from ..base import CaptureRun, Finding
from . import register_section

# Readability truncation limits (full data remains in the run / appendix).
_TECH_LIMIT = 10  # technologies listed in the overview header
_HEADLINE_LIMIT = 5  # headline findings in the overview


def _sev_score(f: Finding) -> float:
    return f.severity.score if f.severity else -1.0


def _sorted_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=_sev_score, reverse=True)


def _findings_table(findings: list[Finding], *, limit: int | None = None) -> str:
    rows = ["| Severity | Signal | Title | Where |", "|---|---|---|---|"]
    for f in _sorted_findings(findings)[:limit]:
        score = f"{f.severity.score:g}" if f.severity else "-"
        where = ""
        if f.location:
            where = str(
                f.location.get("selector")
                or f.location.get("step_id")
                or f.location.get("form")
                or ""
            )
        rows.append(f"| {score} | `{f.signal}` | {f.title} | {where} |")
    return "\n".join(rows) if len(rows) > 2 else "_None._"


@register_section("00_overview", order=0, modes=("reconstruct", "review"))
def overview_section(run: CaptureRun, analyses: dict[str, Any]) -> str:
    techs = (
        ", ".join(
            f"{t.name}" + (f" {t.version}" if t.version else "")
            for t in run.fingerprint[:_TECH_LIMIT]
        )
        or "_none detected_"
    )
    jm = analyses.get("journey_metrics", {})
    headline = _findings_table(
        [f for f in run.findings if f.type != "undetermined"], limit=_HEADLINE_LIMIT
    )
    lines = [
        f"# OverView report — {run.target_url}",
        "",
        f"- **Mode**: {run.mode}",
        f"- **Run**: `{run.run_id}` · started {run.started_at.isoformat()}",
        f"- **Journey**: {len(run.steps)} step(s), {jm.get('distinct_states', '?')} distinct state(s)",
        f"- **Rendering model**: {run.rendering_model or 'unknown'}",
        f"- **Source maps**: {'present' if run.source_maps_present else 'absent' if run.source_maps_present is not None else 'unknown'}",
        f"- **Detected technologies**: {techs}",
        f"- **Findings**: {len(run.findings)} total "
        f"({sum(1 for f in run.findings if f.needs_human_review)} need human review)",
        "",
        "## Headline findings",
        "",
        headline,
    ]
    return "\n".join(lines)


@register_section("10_ux_analysis", order=10, modes=("reconstruct", "review"))
def ux_section(run: CaptureRun, analyses: dict[str, Any]) -> str:
    ux = [
        f
        for f in run.findings
        if f.category in ("ux", "a11y", "performance", "robustness")
    ]
    automatable = [
        f for f in ux if not f.needs_human_review and f.type != "undetermined"
    ]
    manual = [f for f in ux if f.needs_human_review or f.type == "undetermined"]
    lines = [
        "# UX & accessibility analysis",
        "",
        "> Automated accessibility tooling catches only ~30–40% of WCAG issues. The "
        "items under **Needs human review** are *not* assertions of conformance — the "
        "non-automatable majority must be checked by a person / assistive tech.",
        "",
        "## Prioritized issues (deterministic)",
        "",
        _findings_table(automatable),
        "",
        "## Needs human review",
        "",
        _findings_table(manual),
    ]
    return "\n".join(lines)


@register_section("20_architecture", order=20, modes=("reconstruct", "review"))
def architecture_section(run: CaptureRun, analyses: dict[str, Any]) -> str:
    arch_facts = [f for f in run.findings if f.category == "architecture"]
    tech_rows = [
        "| Technology | Version | Categories | Confidence |",
        "|---|---|---|---|",
    ]
    for t in sorted(run.fingerprint, key=lambda t: -t.confidence):
        tech_rows.append(
            f"| {t.name} | {t.version or '-'} | {', '.join(t.categories)} | {t.confidence} |"
        )
    fw = analyses.get("framework", {})
    lines = [
        "# Frontend architecture",
        "",
        f"- **Rendering model**: {run.rendering_model or 'unknown'}",
        f"- **Source maps**: {'present (reconstruction-grade)' if run.source_maps_present else 'absent (names lost)' if run.source_maps_present is not None else 'unknown'}",
        f"- **Build tooling**: {', '.join(fw.get('build_tools', [])) or 'undetermined'}",
        f"- **Client routes**: {len(fw.get('routes', []))}",
        "",
        "## Detected stack",
        "",
        "\n".join(tech_rows) if len(tech_rows) > 2 else "_none detected_",
        "",
        "## Architecture facts",
        "",
        _findings_table(arch_facts) if arch_facts else "_none_",
    ]
    return "\n".join(lines)


@register_section("30_api_surface", order=30, modes=("reconstruct", "review"))
def api_section(run: CaptureRun, analyses: dict[str, Any]) -> str:
    if not run.api_surface:
        return "# API surface\n\n_No XHR/fetch endpoints observed._"
    rows = ["| Method | Path | Kind | Auth | Coverage |", "|---|---|---|---|---|"]
    for e in run.api_surface:
        rows.append(
            f"| {e.method} | `{e.path_template}` | {e.kind} | {e.auth or '-'} | "
            f"{e.confidence} ({e.coverage.get('samples', 0)} samples) |"
        )
    return "# API surface\n\n" + "\n".join(rows)


@register_section("40_reconstruction_blueprint", order=40, modes=("reconstruct",))
def reconstruction_section(run: CaptureRun, analyses: dict[str, Any]) -> str:
    fw = analyses.get("framework", {})
    ui = next(
        (
            t.name
            for t in run.fingerprint
            if "ui-framework" in t.categories or "framework" in t.categories
        ),
        "an unknown framework",
    )
    lines = [
        "# Reconstruction blueprint",
        "",
        "_Deterministic rebuild checklist (the host agent expands this into prose)._",
        "",
        f"- **Framework**: {ui}",
        f"- **Rendering**: {run.rendering_model or 'unknown'} "
        f"({'recover original source via maps' if run.source_maps_present else 'maps absent — reconstruct from beautified bundles, identifiers lost'})",
        f"- **Build tooling**: {', '.join(fw.get('build_tools', [])) or 'undetermined'}",
        f"- **Routes to implement**: {', '.join(fw.get('routes', [])[:20]) or 'none discovered'}",
        f"- **API shape**: {len(run.api_surface)} endpoint(s) — see the API surface section",
        "",
        "Map-backed claims rank above name-lost ones; abstain where no client-facing signal exists.",
    ]
    return "\n".join(lines)


@register_section("40_review_audit", order=40, modes=("review",))
def review_section(run: CaptureRun, analyses: dict[str, Any]) -> str:
    risks = [f for f in run.findings if f.type == "risk" or f.category == "robustness"]
    lines = [
        "# Architecture review & audit",
        "",
        "## Risks & robustness",
        "",
        _findings_table(risks) if risks else "_no risks flagged deterministically_",
        "",
        "_Drift vs. a prior run is available in review mode when a baseline exists "
        "(diffing is a Phase-4 depth item)._",
    ]
    return "\n".join(lines)


@register_section("90_appendix", order=90, modes=("reconstruct", "review"))
def appendix_section(run: CaptureRun, analyses: dict[str, Any]) -> str:
    kinds: dict[str, int] = {}
    for a in run.artifacts:
        kinds[a.kind] = kinds.get(a.kind, 0) + 1
    artifact_rows = "\n".join(f"- `{k}`: {v}" for k, v in sorted(kinds.items()))
    notes = "\n".join(f"- {n}" for n in run.notes) or "_none_"
    return "\n".join(
        [
            "# Appendix",
            "",
            "## Artifacts captured",
            "",
            artifact_rows or "_none_",
            "",
            "## Run notes",
            "",
            notes,
        ]
    )
