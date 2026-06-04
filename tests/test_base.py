"""Tests for the SSOT model tree (``ov.base``)."""

from ov.base import (
    Action,
    Affordance,
    CaptureRun,
    Finding,
    JourneyStep,
    Severity,
    TechFinding,
    new_id,
    utcnow,
)


def test_new_id_prefix_and_shape():
    i = new_id("run")
    assert i.startswith("run_")
    assert len(i.split("_")[1]) == 8
    assert new_id("x") != new_id("x")  # unique


def test_capture_run_minimal_defaults():
    run = CaptureRun(target_url="https://example.com")
    assert run.run_id.startswith("run_")
    assert run.mode == "reconstruct"
    assert run.steps == [] and run.artifacts == [] and run.findings == []
    assert run.started_at <= utcnow()


def test_capture_run_json_roundtrip():
    run = CaptureRun(
        target_url="https://x",
        steps=[JourneyStep(intent="load", action=Action(type="navigate", url="https://x"))],
        fingerprint=[TechFinding(name="React", confidence=80)],
        findings=[
            Finding(
                type="ux_issue",
                signal="contrast.text",
                category="a11y",
                severity=Severity(impact_tier="serious", score=3.0),
                evidence_refs=["ev_1"],
                observed="low contrast",
            )
        ],
    )
    data = run.model_dump(mode="json")
    restored = CaptureRun.model_validate(data)
    assert restored.target_url == "https://x"
    assert restored.fingerprint[0].name == "React"
    assert restored.findings[0].category == "a11y"


def test_affordance_bbox_optional():
    a = Affordance(ref="e1", role="button", name="Go")
    assert a.bbox is None and a.enabled is True
    b = Affordance(ref="e2", role="link", name="Home", bbox=(1.0, 2.0, 3.0, 4.0))
    assert b.bbox == (1.0, 2.0, 3.0, 4.0)


def test_finding_fact_judgment_split_defaults():
    f = Finding(type="undetermined", signal="x", category="ux", observed="")
    assert f.evidence_refs == []  # cite-or-abstain is enforced by the analyzer, not the model
    assert f.judgment is None
    assert f.source_layer == "deterministic"
