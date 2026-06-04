"""Report rendering + synopsis map-reduce tests (deterministic, no browser)."""

import json

from ov.base import CaptureRun, Endpoint, Finding, Severity, TechFinding
from ov.reporting.render import render_reports
from ov.reporting.synopsis import build_synopsis, build_synopsis_doc, dedupe_findings


def _finding(signal="contrast.text", score=3.0, refs=("a",), type_="ux_issue", cat="a11y", title="low contrast"):
    return Finding(
        type=type_, signal=signal, category=cat, title=title,
        severity=Severity(impact_tier="serious", score=score),
        evidence_refs=list(refs), observed=title,
    )


def _analyzed_run():
    return CaptureRun(
        target_url="http://t.example",
        mode="reconstruct",
        rendering_model="csr",
        source_maps_present=True,
        fingerprint=[TechFinding(name="React", confidence=80)],
        api_surface=[Endpoint(method="GET", path_template="/api/x", kind="rest", confidence=75)],
        findings=[_finding(), _finding(signal="form.friction", title="too many fields", cat="ux")],
    )


def test_render_reports_writes_sections(tmp_store):
    run = _analyzed_run()
    tmp_store.save_run(run)
    keys = render_reports(run, store=tmp_store)
    names = {k.split("/")[-1] for k in keys}
    assert "00_overview.md" in names
    assert "40_reconstruction_blueprint.md" in names  # reconstruct mode
    assert "40_review_audit.md" not in names  # review-only section excluded
    overview_md = tmp_store.reports[f"{run.run_id}/00_overview.md"]
    assert "OverView report" in overview_md and "React" in overview_md


def test_render_reports_review_mode_swaps_section(tmp_store):
    run = _analyzed_run()
    run.mode = "review"
    tmp_store.save_run(run)
    keys = render_reports(run, store=tmp_store)
    names = {k.split("/")[-1] for k in keys}
    assert "40_review_audit.md" in names
    assert "40_reconstruction_blueprint.md" not in names


def test_dedupe_merges_on_evidence_and_summary():
    a = _finding(refs=["x"], score=3.0)
    b = _finding(refs=["y"], score=5.0)  # same signal/title -> same norm -> merge
    c = _finding(signal="cwv.inp", title="slow", refs=["z"], score=4.0)  # distinct
    records = dedupe_findings([a, b, c])
    contrast = [r for r in records if r["signal"] == "contrast.text"]
    assert len(contrast) == 1
    assert sorted(contrast[0]["evidence_refs"]) == ["x", "y"]
    assert contrast[0]["severity_score"] == 5.0  # max severity kept
    assert contrast[0]["occurrences"] == 2


def test_build_synopsis_doc_and_histogram():
    run = _analyzed_run()
    doc = build_synopsis_doc(run)
    assert doc["target_kind"] == "foreign"
    assert doc["findings"]
    assert sum(doc["severity_histogram"].values()) == len(doc["findings"])
    # findings sorted by severity desc
    scores = [f["severity_score"] for f in doc["findings"] if f["severity_score"] is not None]
    assert scores == sorted(scores, reverse=True)


def test_build_synopsis_emits_json_and_md(tmp_store):
    run = _analyzed_run()
    tmp_store.save_run(run)
    md_key = build_synopsis(run, store=tmp_store)
    assert md_key.endswith("SYNOPSIS.md")
    doc = json.loads(tmp_store.reports[f"{run.run_id}/synopsis.json"])
    assert doc["run_id"] == run.run_id and doc["findings"]
    md = tmp_store.reports[f"{run.run_id}/SYNOPSIS.md"]
    assert "Synopsis" in md and "Thor Whalen" in md


def test_synopsis_null_severity_in_histogram():
    run = _analyzed_run()
    run.findings.append(Finding(type="undetermined", signal="x.manual", category="a11y",
                                title="manual review", observed=""))
    doc = build_synopsis_doc(run)
    assert "n/a" in doc["severity_histogram"]  # the null-severity finding
    assert doc["findings"][-1]["severity_score"] is None  # nulls sort to the end


def test_dedupe_three_way_chain_merge():
    a = _finding(signal="s.a", title="A", refs=["1"])
    b = _finding(signal="s.b", title="B", refs=["1", "2"])  # overlaps a via ref 1
    c = _finding(signal="s.c", title="C", refs=["2", "3"])  # overlaps b via ref 2
    records = dedupe_findings([a, b, c])
    assert len(records) == 1
    assert sorted(records[0]["evidence_refs"]) == ["1", "2", "3"]


def test_render_section_crash_is_isolated(tmp_store):
    from ov.reporting import REPORT_SECTION_REGISTRY, register_section

    @register_section("99_boom", order=99, modes=("reconstruct", "review"))
    def _boom(run, analyses):
        raise RuntimeError("section kaboom")

    try:
        run = _analyzed_run()
        tmp_store.save_run(run)
        keys = render_reports(run, store=tmp_store)
        assert any("99_boom" in k for k in keys)  # still produced a file
        assert "section failed" in tmp_store.reports[f"{run.run_id}/99_boom.md"]
    finally:
        REPORT_SECTION_REGISTRY._items.pop("99_boom", None)
