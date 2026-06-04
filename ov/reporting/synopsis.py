"""Synopsis: structured map-reduce over findings into one agent-consumable file (§8.4).

Maps each :class:`~ov.base.Finding` into a compact synopsis record, **deduplicates
deterministically** (cluster on type + evidence-ref overlap + normalized summary;
merge to the union of evidence refs and the max severity), and emits two
renderings from one source: ``synopsis.json`` (the SSOT a downstream agent
consumes) and ``SYNOPSIS.md`` derived from it (never hand-authored). Evidence-id
overlap is a model-free check, more reliable than LLM similarity-judging.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..base import CaptureRun, Finding
from ..capture.stores import resolve_store

_WORD_RE = re.compile(r"[^a-z0-9]+")


def _norm(f: Finding) -> str:
    """Normalized text key for clustering (signal + title, lowercased, de-punctuated)."""
    return _WORD_RE.sub(" ", f"{f.signal} {f.title}".lower()).strip()


def _sev_score(f: Finding) -> float:
    return f.severity.score if f.severity else -1.0


def dedupe_findings(findings: list[Finding]) -> list[dict[str, Any]]:
    """Cluster + merge findings deterministically; return synopsis records (pure).

    Two findings cluster when they share ``type`` and either overlap on evidence
    refs or share a normalized summary. Each cluster yields one record holding the
    union of evidence refs, the max severity, and the highest-severity representative.

    >>> from ov.base import Finding, Severity
    >>> a = Finding(type="ux_issue", signal="contrast.text", category="a11y",
    ...             title="low contrast", evidence_refs=["x"],
    ...             severity=Severity(impact_tier="serious", score=3.0))
    >>> b = Finding(type="ux_issue", signal="contrast.text", category="a11y",
    ...             title="low contrast", evidence_refs=["y"],
    ...             severity=Severity(impact_tier="serious", score=5.0))
    >>> recs = dedupe_findings([a, b])
    >>> len(recs), sorted(recs[0]["evidence_refs"]), recs[0]["severity_score"]
    (1, ['x', 'y'], 5.0)
    """
    clusters: list[dict[str, Any]] = []
    for f in findings:
        nf, rf = _norm(f), set(f.evidence_refs)
        placed = False
        for c in clusters:
            if c["type"] == f.type and ((rf and rf & c["refs"]) or nf == c["norm"]):
                c["refs"] |= rf
                c["members"].append(f)
                if _sev_score(f) > _sev_score(c["rep"]):
                    c["rep"] = f
                placed = True
                break
        if not placed:
            clusters.append(
                {"type": f.type, "norm": nf, "refs": set(rf), "rep": f, "members": [f]}
            )

    records = []
    for c in clusters:
        rep: Finding = c["rep"]
        records.append(
            {
                "id": rep.finding_id,
                "type": rep.type,
                "signal": rep.signal,
                "category": rep.category,
                "summary": rep.title or rep.observed,
                "severity_tier": rep.severity.impact_tier if rep.severity else None,
                "severity_score": _sev_score(rep) if rep.severity else None,
                "evidence_refs": sorted(c["refs"]),
                "confidence": rep.confidence,
                "recommendation": rep.suggested_fix,
                "needs_human_review": any(m.needs_human_review for m in c["members"]),
                "occurrences": len(c["members"]),
                "diff_status": rep.diff_status,
            }
        )
    records.sort(
        key=lambda r: (r["severity_score"] is None, -(r["severity_score"] or 0))
    )
    return records


def _regression_summary(diff: dict[str, Any]) -> dict[str, Any]:
    """Distill a :class:`~ov.base.RunDiff` dict into the synopsis regression block.

    Regression-oriented for a downstream creation/modification agent: it leads
    with what got *worse or newly appeared* (the fix list) and what *improved*,
    plus non-finding drift (stack / API / rendering / source maps).
    """
    deltas = diff.get("finding_deltas", [])

    def by_direction(direction: str) -> list[dict[str, Any]]:
        return sorted(
            (d for d in deltas if d.get("direction") == direction),
            key=lambda d: -(d.get("severity_score") or 0),
        )

    return {
        "baseline_run_id": diff.get("baseline_run_id"),
        "has_drift": diff.get("has_drift"),
        "counts": diff.get("counts", {}),
        "regressions": by_direction("regression"),
        "improvements": by_direction("improvement"),
        "tech_added": diff.get("tech_added", []),
        "tech_removed": diff.get("tech_removed", []),
        "endpoints_added": diff.get("endpoints_added", []),
        "endpoints_removed": diff.get("endpoints_removed", []),
        "rendering_model_change": diff.get("rendering_model_change"),
        "source_maps_change": diff.get("source_maps_change"),
    }


def build_synopsis_doc(
    run: CaptureRun, *, diff: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build the ``synopsis.json`` SSOT document from a run's findings (pure).

    When ``diff`` (a serialized :class:`~ov.base.RunDiff`) is given -- review mode
    with a baseline -- a ``regression`` block is appended so the synopsis tells a
    downstream agent what changed since the prior run, not just the current state.
    """
    records = dedupe_findings(run.findings)
    histogram: dict[str, int] = {}
    for r in records:
        tier = str(r["severity_tier"] or "n/a")
        histogram[tier] = histogram.get(tier, 0) + 1
    doc: dict[str, Any] = {
        "run_id": run.run_id,
        "target_url": run.target_url,
        "mode": run.mode,
        "target_kind": "own" if run.mode == "review" else "foreign",
        "rendering_model": run.rendering_model,
        "source_maps_present": run.source_maps_present,
        "technologies": [
            {"name": t.name, "version": t.version, "confidence": t.confidence}
            for t in run.fingerprint
        ],
        "api_endpoints": [
            {"method": e.method, "path": e.path_template, "kind": e.kind}
            for e in run.api_surface
        ],
        "severity_histogram": histogram,
        "findings": records,
    }
    if diff:
        doc["regression"] = _regression_summary(diff)
    return doc


def render_synopsis_md(doc: dict[str, Any]) -> str:
    """Derive SYNOPSIS.md from the synopsis JSON (never hand-authored)."""
    lines = [
        f"# Synopsis — {doc['target_url']}",
        "",
        f"*Author: Thor Whalen.*",
        "",
        f"- **Target**: {doc['target_kind']} ({doc['mode']} mode)",
        f"- **Rendering**: {doc.get('rendering_model') or 'unknown'} · "
        f"**source maps**: {doc.get('source_maps_present')}",
        f"- **Findings**: {len(doc['findings'])} · histogram: {doc['severity_histogram']}",
        "",
        "## Findings (deduplicated, severity-ranked)",
        "",
        "| Score | Type | Signal | Summary | Evidence | Review? |",
        "|---|---|---|---|---|---|",
    ]
    for r in doc["findings"]:
        score = f"{r['severity_score']:g}" if r["severity_score"] is not None else "-"
        lines.append(
            f"| {score} | {r['type']} | `{r['signal']}` | {r['summary']} | "
            f"{len(r['evidence_refs'])} ref(s) | {'yes' if r['needs_human_review'] else ''} |"
        )
    lines += _render_regression_md(doc.get("regression"))
    return "\n".join(lines)


def _render_regression_md(reg: dict[str, Any] | None) -> list[str]:
    """Markdown lines for the synopsis regression block (review mode w/ baseline)."""
    if not reg:
        return []
    lines = [
        "",
        "## Regression vs baseline",
        "",
        f"- **Baseline**: `{reg.get('baseline_run_id')}` · drift: {reg.get('has_drift')}",
        f"- **Counts**: {reg.get('counts', {})}",
    ]
    if reg.get("regressions"):
        lines += [
            "",
            "### Regressions (worse / newly present)",
            "",
            "| Score | Signal | Summary |",
            "|---|---|---|",
        ]
        for r in reg["regressions"]:
            score = (
                f"{r['severity_score']:g}"
                if r.get("severity_score") is not None
                else "-"
            )
            lines.append(
                f"| {score} | `{r.get('signal', '')}` | {r.get('title', '')} |"
            )
    if reg.get("improvements"):
        lines += [
            "",
            "### Improvements (resolved / better)",
            "",
            "| Signal | Summary |",
            "|---|---|",
        ]
        for r in reg["improvements"]:
            lines.append(f"| `{r.get('signal', '')}` | {r.get('title', '')} |")
    drift: list[str] = []
    for key, label in (
        ("tech_added", "tech +"),
        ("tech_removed", "tech −"),
        ("endpoints_added", "endpoints +"),
        ("endpoints_removed", "endpoints −"),
    ):
        if reg.get(key):
            drift.append(f"{label}: {', '.join(reg[key])}")
    if reg.get("rendering_model_change"):
        rc = reg["rendering_model_change"]
        drift.append(f"rendering {rc['from']}→{rc['to']}")
    if reg.get("source_maps_change"):
        sc = reg["source_maps_change"]
        drift.append(f"source maps {sc['from']}→{sc['to']}")
    if drift:
        lines += ["", "**Stack / API drift:** " + "; ".join(drift)]
    return lines


def build_synopsis(run_or_id: Any, *, out: Any = None, store: Any = None) -> str:
    """Build + persist ``synopsis.json`` and the derived ``SYNOPSIS.md``; return the md path/key.

    ``run_or_id`` may be a :class:`CaptureRun` or a run id. The JSON is the SSOT;
    the Markdown is derived. Both are written to the store (and ``out`` dir if given).
    """
    from ..analysis.diff import load_diff

    store = resolve_store(store)
    run = run_or_id if isinstance(run_or_id, CaptureRun) else store.load_run(run_or_id)
    diff = load_diff(store, run.run_id)
    doc = build_synopsis_doc(run, diff=diff)
    md = render_synopsis_md(doc)

    store.save_report(run.run_id, "synopsis.json", json.dumps(doc, indent=2))
    md_key = store.save_report(run.run_id, "SYNOPSIS.md", md)

    if out:
        out_dir = Path(out)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "synopsis.json").write_text(
            json.dumps(doc, indent=2), encoding="utf-8"
        )
        md_path = out_dir / "SYNOPSIS.md"
        md_path.write_text(md, encoding="utf-8")
        return str(md_path)
    return md_key
