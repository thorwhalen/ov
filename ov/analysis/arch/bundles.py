"""Source-map detection + recovery -- the decisive bimodal lever (D2).

Reconstruction quality is bimodal: WITH source maps you recover the original file
tree, source text, and ``node_modules`` version paths; WITHOUT them you get a
beautified-but-renamed approximation. So this analyzer detects map presence from
the captured JS bodies and asset URLs and sets ``source_maps_present`` (which
gates downstream reconstruction confidence everywhere).

Recovery is **pure-Python and Node-free** (see :mod:`ov.analysis.arch.sourcemaps`):
it parses any captured ``.map`` body (explicit ``source_map`` artifacts, incidental
``.map`` responses, or inline ``data:`` maps), persists each recovered file
content-addressed (``recovered_source`` artifacts indexed by a manifest blob), and
surfaces recovered ``node_modules`` packages as top-provenance
:class:`~ov.base.TechFinding`s for the dependency inventory. Recovered artifacts
are not appended to ``run.artifacts``, so re-analysis stays idempotent.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from itertools import islice
from typing import Any

from ...base import Finding, TechFinding
from ...util import content_hash
from .. import register_analyzer
from ..context import AnalysisContext, AnalyzerOutput
from .sourcemaps import (
    RecoveredFile,
    extract_inline_map,
    node_modules_packages,
    recover_from_map,
)

_MAP_MARKERS = ("//# sourceMappingURL=", "//@ sourceMappingURL=")

# Recovery caps (named, not magic): bound pathological maps / huge trees.
_MAX_MAPS = 50  # source-map documents consumed per run
_MAX_RECOVERED_FILES = 5000  # files persisted as artifacts per run
_MAX_RECOVERED_DEPS = 1000  # node_modules packages surfaced as TechFindings
_SAMPLE = 50  # sample sizes embedded in metric_detail


def js_response_bodies(ctx: AnalysisContext) -> list[tuple[str, str]]:
    """Return ``(url, text)`` for captured JS response bodies (reused across arch)."""
    body_arts = {a.artifact_id: a for a in ctx.artifacts("request")}
    out: list[tuple[str, str]] = []
    for records in ctx.jsons("network"):
        for rec in records or []:
            ct = (rec.get("response_headers") or {}).get("content-type", "")
            is_js = rec.get("resource_type") == "script" or "javascript" in ct
            if is_js and rec.get("body_artifact_id") in body_arts:
                out.append(
                    (rec.get("url", ""), ctx.text(body_arts[rec["body_artifact_id"]]))
                )
    return out


def detect_source_maps(
    js_bodies: list[tuple[str, str]], asset_urls: list[str]
) -> tuple[bool, list[str]]:
    """Detect source-map presence from JS bodies + asset urls (pure, testable).

    >>> detect_source_maps([("a.js", "x=1\\n//# sourceMappingURL=a.js.map")], [])[0]
    True
    >>> detect_source_maps([("a.js", "x=1")], ["https://x/b.js.map"])[0]
    True
    >>> detect_source_maps([("a.js", "x=1")], [])[0]
    False
    """
    evidence: list[str] = []
    for url, text in js_bodies:
        tail = text[-2000:]
        if any(m in tail for m in _MAP_MARKERS):
            evidence.append(f"sourceMappingURL in {url or 'bundle'}")
    for u in asset_urls:
        if u.endswith(".map"):
            evidence.append(f"served map asset {u}")
    return bool(evidence), evidence


@register_analyzer(
    "bundles", lens="arch", requires=("network",), produces=("source_maps_present",)
)
def analyze_bundles(ctx: AnalysisContext) -> AnalyzerOutput:
    """Set ``run.source_maps_present`` and emit an arch_fact (+ optional recovery)."""
    out = AnalyzerOutput()
    js_bodies = js_response_bodies(ctx)
    asset_urls: list[str] = []
    for inv in ctx.jsons("assets"):
        asset_urls.extend(a.get("url", "") for a in (inv or []))

    present, evidence = detect_source_maps(js_bodies, asset_urls)
    smap_arts = ctx.artifacts("source_map")
    if smap_arts:
        evidence.append(f"{len(smap_arts)} captured source-map artifact(s)")

    # Recovery is attempted unconditionally: detect_source_maps only scans each
    # bundle's 2 kB tail, so a large INLINE data: map (its marker pushed past the
    # window by the base64 payload) or a probe-fetched source_map artifact would be
    # missed -- yet recovering any map is itself proof maps are present. So derive
    # `present` from detection OR a successful recovery, not the reverse.
    recovery = _recover_sources(ctx, js_bodies)
    present = present or bool(smap_arts) or recovery["maps_consumed"] > 0
    if recovery["maps_consumed"]:
        evidence.append(
            f"recovered {recovery['recovered_files']} file(s) from source maps"
        )
    out.run_fields["source_maps_present"] = present

    metric_detail: dict[str, Any] = {
        "source_maps_present": present,
        "recovered_files": recovery["recovered_files"],
        "recovered_packages": recovery["recovered_packages"],
        "had_sources_content": recovery["had_sources_content"],
        "maps_consumed": recovery["maps_consumed"],
        "skipped_unsafe_paths": recovery["skipped_unsafe_paths"],
        "file_tree_sample": recovery["file_tree_sample"],
        "packages_sample": recovery["packages_sample"],
        "manifest_uri": recovery["manifest_uri"],
        "truncated": recovery["truncated"],
        "packages_truncated": recovery["packages_truncated"],
    }
    # Recovered node_modules versions are the top-rank dependency provenance
    # (sourcemap path > bundle comment > global signature) -> TechFindings so the
    # existing dependency inventory + CVE scan + tech-diff pick them up. They are
    # the SBOM, kept out of the headline stack via is_recovered_dependency.
    for name, version in recovery["packages"][:_MAX_RECOVERED_DEPS]:
        out.tech.append(
            TechFinding(
                name=name,
                version=version,
                categories=["dependency"],
                confidence=95 if version else 85,
                provenance=["sourcemap"],
            )
        )

    out.findings.append(
        Finding(
            type="arch_fact",
            signal="arch.source_maps",
            category="architecture",
            title=f"Source maps {'present' if present else 'absent'}",
            evidence_refs=[a.artifact_id for a in ctx.artifacts("network")[:1]]
            or ["network"],
            observed=(
                "; ".join(evidence[:5])
                if present
                else "no sourceMappingURL markers or .map assets found"
            ),
            metric_detail=metric_detail,
            judgment=None,
            source_layer="deterministic",
            confidence=0.9 if present else 0.6,
        )
    )
    out.summary = {
        "source_maps_present": present,
        "recovered_files": recovery["recovered_files"],
        "recovered_packages": recovery["recovered_packages"],
        "had_sources_content": recovery["had_sources_content"],
    }
    return out


def _collect_map_texts(
    ctx: AnalysisContext, js_bodies: list[tuple[str, str]]
) -> Iterator[str]:
    """Yield candidate source-map JSON bodies from the captured artifacts, lazily.

    Three sources: explicit ``source_map`` artifacts (the capture probe's output),
    incidental ``.map`` response bodies captured as ``request`` bodies, and inline
    ``data:`` maps embedded in JS bundles. Yielding lazily (vs. building a list)
    lets the caller stop after ``_MAX_MAPS`` without decoding every captured map;
    the seen-hash guard stops one logical map collected via two channels (e.g. an
    explicit artifact and an inline copy) from being consumed/counted twice.
    """
    seen: set[str] = set()

    def _fresh(text: str) -> bool:
        h = content_hash(text)
        if h in seen:
            return False
        seen.add(h)
        return True

    for a in ctx.artifacts("source_map"):
        text = ctx.text(a)
        if _fresh(text):
            yield text
    body_arts = {a.artifact_id: a for a in ctx.artifacts("request")}
    for records in ctx.jsons("network"):
        for rec in records or []:
            if (
                rec.get("url", "").endswith(".map")
                and rec.get("body_artifact_id") in body_arts
            ):
                text = ctx.text(body_arts[rec["body_artifact_id"]])
                if _fresh(text):
                    yield text
    for _url, text in js_bodies:
        inline = extract_inline_map(text)
        if inline and _fresh(inline):
            yield inline


def _recover_sources(
    ctx: AnalysisContext, js_bodies: list[tuple[str, str]]
) -> dict[str, Any]:
    """Recover + persist original source from captured maps (pure-Python; idempotent).

    Recovered files are stored content-addressed (``recovered_source`` artifacts)
    and indexed by ``uri`` in a ``recovered_source_manifest`` blob -- they are
    *not* appended to ``run.artifacts``, so re-analysis stays duplicate-free
    (identical bytes dedupe to the same uri). Always returns a well-formed summary
    dict (zeroed when no maps were found). Caps are explicit, never silent.
    """
    recovered: list[RecoveredFile] = []
    seen: set[str] = set()
    skipped_unsafe = 0
    had_content = False
    maps_consumed = 0
    for mt in islice(_collect_map_texts(ctx, js_bodies), _MAX_MAPS):
        rec = recover_from_map(mt)
        if rec.sources_total == 0 and rec.recovered_count == 0:
            continue
        maps_consumed += 1
        skipped_unsafe += rec.skipped_unsafe
        had_content = had_content or rec.had_sources_content
        for rf in rec.files:
            if rf.path in seen:
                continue
            seen.add(rf.path)
            recovered.append(rf)

    truncated = len(recovered) > _MAX_RECOVERED_FILES
    persisted = recovered[:_MAX_RECOVERED_FILES]
    manifest: list[dict[str, str]] = []
    for rf in persisted:
        art = ctx.store.put_artifact(
            rf.content.encode("utf-8"),
            kind="recovered_source",
            meta={"path": rf.path},
        )
        manifest.append({"path": rf.path, "uri": art.uri})

    manifest_uri: str | None = None
    if manifest:
        man = ctx.store.put_artifact(
            json.dumps(manifest).encode("utf-8"),
            kind="recovered_source_manifest",
            content_type="application/json",
            meta={"file_count": len(manifest)},
        )
        manifest_uri = man.uri

    # Infer the SBOM over the SAME files we persisted, so the manifest and the
    # dependency list never disagree about what was actually recovered.
    packages = node_modules_packages(persisted)
    return {
        "recovered_files": len(manifest),
        "recovered_packages": len(packages),
        "had_sources_content": had_content,
        "maps_consumed": maps_consumed,
        "skipped_unsafe_paths": skipped_unsafe,
        "truncated": truncated,
        "packages_truncated": len(packages) > _MAX_RECOVERED_DEPS,
        "manifest_uri": manifest_uri,
        "file_tree_sample": [m["path"] for m in manifest[:_SAMPLE]],
        "packages_sample": [f"{n}@{v}" if v else n for n, v in packages[:_SAMPLE]],
        "packages": packages,
    }
