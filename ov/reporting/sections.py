"""The default report sections (§8.3) -- each a registered Markdown fragment.

A section is ``fn(run, analyses) -> str``. Sections are registered with an
``order`` (numeric prefix) and the ``modes`` they apply to (reconstruct/review),
so :mod:`ov.reporting.render` can select and concatenate them. They read the
already-analyzed :class:`~ov.base.CaptureRun` (findings, fingerprint, api_surface,
rendering_model, ...) plus the per-analyzer summaries -- no model involved.
"""

from __future__ import annotations

from typing import Any

from ..analysis.arch.sourcemaps import is_recovered_dependency as _is_recovered_dep
from ..base import CaptureRun, Finding
from . import register_section

# Readability truncation limits (full data remains in the run / appendix).
_TECH_LIMIT = 10  # technologies listed in the overview header
_HEADLINE_LIMIT = 5  # headline findings in the overview
_RECOVERED_DEP_LIMIT = 50  # recovered-dependency rows in the recovered-source section


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
    # Headline stack only -- the recovered-dependency SBOM has its own section and
    # would otherwise flood this most-read line (and is unsorted in run order).
    stack = sorted(
        (t for t in run.fingerprint if not _is_recovered_dep(t)),
        key=lambda t: -t.confidence,
    )
    techs = (
        ", ".join(
            f"{t.name}" + (f" {t.version}" if t.version else "")
            for t in stack[:_TECH_LIMIT]
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
    # Recovered node_modules deps (the SBOM) get their own section; keep the
    # headline stack table framework-level rather than letting it drown in deps.
    stack = [t for t in run.fingerprint if not _is_recovered_dep(t)]
    for t in sorted(stack, key=lambda t: -t.confidence):
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


@register_section("25_recovered_source", order=25, modes=("reconstruct", "review"))
def recovered_source_section(run: CaptureRun, analyses: dict[str, Any]) -> str:
    sm = next((f for f in run.findings if f.signal == "arch.source_maps"), None)
    md = (sm.metric_detail or {}) if sm else {}
    file_count = md.get("recovered_files", 0)
    if not file_count:
        if run.source_maps_present is None:
            note = "Source-map status unknown — architecture analysis did not run."
        elif run.source_maps_present:
            note = (
                "Source maps were detected but no original source was recovered "
                "(maps not captured, or `sourcesContent` absent — the capture-time "
                "source-map probe fetches external `.js.map` files)."
            )
        else:
            note = "No source maps present — original source is not recoverable."
        return f"# Recovered source\n\n_{note}_"

    recovered_deps = [t for t in run.fingerprint if _is_recovered_dep(t)]
    versioned = sum(1 for t in recovered_deps if t.version)
    lines = [
        "# Recovered source",
        "",
        "_Original file tree + dependency versions recovered from the app's own "
        "source maps (pure-Python, no Node)._",
        "",
        f"- **Files recovered**: {file_count}"
        + (" (truncated)" if md.get("truncated") else ""),
        f"- **`sourcesContent` present**: {'yes' if md.get('had_sources_content') else 'no'}",
        f"- **Maps consumed**: {md.get('maps_consumed', 0)}",
        f"- **Unsafe paths skipped**: {md.get('skipped_unsafe_paths', 0)}",
        f"- **Dependencies recovered**: {len(recovered_deps)} ({versioned} with versions)"
        + (" — capped" if md.get("packages_truncated") else ""),
    ]
    sample = md.get("file_tree_sample") or []
    if sample:
        lines += ["", "## File tree (sample)", ""]
        lines += [f"- `{p}`" for p in sample]
        if file_count > len(sample):
            lines.append(f"- _… +{file_count - len(sample)} more_")
    if recovered_deps:
        rows = ["| Package | Version |", "|---|---|"]
        for t in sorted(recovered_deps, key=lambda t: t.name)[:_RECOVERED_DEP_LIMIT]:
            rows.append(f"| {t.name} | {t.version or '-'} |")
        lines += ["", "## Recovered dependencies (SBOM)", "", "\n".join(rows)]
        if len(recovered_deps) > _RECOVERED_DEP_LIMIT:
            lines.append(f"\n_… +{len(recovered_deps) - _RECOVERED_DEP_LIMIT} more_")
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
    recovered = analyses.get("bundles", {}).get("recovered_files", 0)
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
        f"- **Recovered source**: "
        + (
            f"{recovered} file(s) — see the Recovered source section"
            if recovered
            else "none recovered"
        ),
        f"- **Routes to implement**: {', '.join(fw.get('routes', [])[:20]) or 'none discovered'}",
        f"- **API shape**: {len(run.api_surface)} endpoint(s) — see the API surface section",
        "",
        "Map-backed claims rank above name-lost ones; abstain where no client-facing signal exists.",
    ]
    return "\n".join(lines)


_DIRECTION_GLYPH = {"regression": "▲", "improvement": "▼", "neutral": "·"}


def _delta_rows(deltas: list[dict[str, Any]], status: str) -> str:
    """Render the deltas of one status as a severity-sorted Markdown table."""
    rows = ["| Dir | Severity | Signal | Title | Detail |", "|---|---|---|---|---|"]
    items = sorted(
        (d for d in deltas if d.get("status") == status),
        key=lambda d: -(d.get("severity_score") or 0),
    )
    for d in items:
        score = (
            f"{d['severity_score']:g}" if d.get("severity_score") is not None else "-"
        )
        glyph = _DIRECTION_GLYPH.get(d.get("direction", "neutral"), "")
        rows.append(
            f"| {glyph} | {score} | `{d.get('signal', '')}` | "
            f"{d.get('title', '')} | {d.get('detail') or ''} |"
        )
    return "\n".join(rows) if len(rows) > 2 else "_none_"


def _stack_drift_line(diff: dict[str, Any]) -> str | None:
    """One-line summary of non-finding drift (tech / API / rendering / source maps)."""
    bits: list[str] = []
    if diff.get("tech_added"):
        bits.append(f"tech added: {', '.join(diff['tech_added'])}")
    if diff.get("tech_removed"):
        bits.append(f"tech removed: {', '.join(diff['tech_removed'])}")
    if diff.get("endpoints_added"):
        bits.append(f"endpoints added: {', '.join(diff['endpoints_added'])}")
    if diff.get("endpoints_removed"):
        bits.append(f"endpoints removed: {', '.join(diff['endpoints_removed'])}")
    if diff.get("rendering_model_change"):
        rc = diff["rendering_model_change"]
        bits.append(f"rendering model {rc['from']}→{rc['to']}")
    if diff.get("source_maps_change"):
        sc = diff["source_maps_change"]
        bits.append(f"source maps {sc['from']}→{sc['to']}")
    return "**Stack / API drift:** " + "; ".join(bits) if bits else None


def _render_diff_md(diff: dict[str, Any] | None) -> list[str]:
    """Markdown lines for the own-target drift block (review mode)."""
    if not diff:
        return [
            "## Drift vs. prior run",
            "",
            "_No baseline run found — capture a prior run of this target in review "
            "mode (`ov observe <url> --mode review`) to enable own-target "
            "regression diffing._",
        ]
    deltas = diff.get("finding_deltas", [])
    counts = diff.get("counts", {})
    lines = [
        "## Drift vs. prior run",
        "",
        f"- **Baseline run**: `{diff.get('baseline_run_id')}`",
        f"- **Findings**: {counts.get('new', 0)} new · {counts.get('changed', 0)} "
        f"changed · {counts.get('resolved', 0)} resolved · "
        f"{counts.get('unchanged', 0)} unchanged",
        "",
    ]
    drift = _stack_drift_line(diff)
    if drift:
        lines += [drift, ""]
    lines += [
        "### New findings",
        "",
        _delta_rows(deltas, "new"),
        "",
        "### Changed findings",
        "",
        _delta_rows(deltas, "changed"),
        "",
        "### Resolved findings",
        "",
        _delta_rows(deltas, "resolved"),
    ]
    return lines


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
    ]
    lines += _render_diff_md(analyses.get("review_diff"))
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
