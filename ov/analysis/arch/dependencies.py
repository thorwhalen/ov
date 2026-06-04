"""Dependency inventory + known-vulnerability flags (D2).

Builds a dependency inventory from the detected technologies (provenance ranks
sourcemap path > bundle comment > global signature) and, when the **Retire.js**
CLI is available, scans the captured JS bodies for CVE-backed vulnerable library
versions. Retire.js is shelled out to (it must not run untrusted JS in-process);
when it is absent the analyzer emits an honest ``undetermined`` finding routing
CVE coverage to a human rather than asserting "no known vulnerabilities".
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ...base import Finding
from .. import register_analyzer
from ..context import AnalysisContext, AnalyzerOutput
from ..ux.severity import make_severity
from .bundles import js_response_bodies


@register_analyzer("dependencies", lens="arch", requires=("fingerprint",), produces=("findings",))
def analyze_dependencies(ctx: AnalysisContext) -> AnalyzerOutput:
    """Inventory dependencies and flag known-vulnerable versions (Retire.js, optional)."""
    out = AnalyzerOutput()
    libraries = [
        {"name": t.name, "version": t.version, "confidence": t.confidence,
         "categories": t.categories, "provenance": t.provenance}
        for t in ctx.run.fingerprint
    ]
    out.summary = {"libraries": libraries}

    if shutil.which("retire") is None:
        out.findings.append(
            Finding(
                type="undetermined",
                signal="deps.cve-scan-skipped",
                category="robustness",
                title="CVE scan skipped -- Retire.js not installed",
                observed="Install Retire.js (`npm install -g retire`) to scan for known-vulnerable libraries.",
                evidence_refs=[],
                source_layer="deterministic",
                confidence=1.0,
                needs_human_review=True,
            )
        )
        return out

    vulns = _run_retire(ctx)
    for v in vulns:
        out.findings.append(
            Finding(
                type="risk",
                signal="deps.known-vulnerability",
                category="robustness",
                title=f"Vulnerable {v.get('component')} {v.get('version')}",
                severity=make_severity(_sev_tier(v), nodes=1, journey_fraction=1.0),
                evidence_refs=[a.artifact_id for a in ctx.artifacts("network")[:1]] or ["network"],
                observed=f"{v.get('component')} {v.get('version')}: "
                + ", ".join(str(i.get("summary", i)) for i in v.get("vulnerabilities", []))[:300],
                metric_detail=v,
                suggested_fix=f"upgrade {v.get('component')} to a patched version",
                source_layer="deterministic",
                confidence=0.9,
            )
        )
    out.summary["vulnerabilities"] = len(vulns)
    return out


def _sev_tier(v: dict[str, Any]) -> str:
    sevs = {str(i.get("severity", "")).lower() for i in v.get("vulnerabilities", [])}
    for tier in ("critical", "high", "medium", "low"):
        if tier in sevs:
            return {"critical": "critical", "high": "serious", "medium": "moderate", "low": "minor"}[tier]
    return "moderate"


def _run_retire(ctx: AnalysisContext) -> list[dict[str, Any]]:
    """Write captured JS to a temp dir and run Retire.js; return its findings."""
    bodies = js_response_bodies(ctx)
    if not bodies:
        return []
    try:
        with tempfile.TemporaryDirectory() as td:
            for i, (_url, text) in enumerate(bodies[:50]):
                (Path(td) / f"bundle_{i}.js").write_text(text, encoding="utf-8")
            out_path = Path(td) / "retire.json"
            subprocess.run(
                ["retire", "--path", td, "--outputformat", "json", "--outputpath", str(out_path)],
                capture_output=True, timeout=120, check=False,
            )
            if not out_path.exists():
                return []
            data = json.loads(out_path.read_text(encoding="utf-8"))
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    findings: list[dict[str, Any]] = []
    for entry in data.get("data", data if isinstance(data, list) else []):
        for res in entry.get("results", []):
            if res.get("vulnerabilities"):
                findings.append(res)
    return findings
