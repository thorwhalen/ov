"""Tests for the evidence-bundle assembler + reliability passes (deterministic)."""

import base64
import importlib.util

import pytest

from ov.analysis.evidence import (
    build_evidence_bundle,
    fit_to_cap,
    image_token_cost,
    png_dimensions,
)
from ov.analysis.reliability import (
    apply_verification,
    lookup_evidence,
    resolvable,
    verification_questions,
    verify_findings,
)
from ov.base import Affordance, CaptureRun, EvidenceBundle, Finding, JourneyStep, Severity

_PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


# --- token budget / dimensions (pure) -------------------------------------- #

def test_png_dimensions():
    assert png_dimensions(_PIXEL) == (1, 1)
    assert png_dimensions(b"not a png") is None


def test_image_token_cost():
    assert image_token_cost(1000, 1000) == 1334


def test_fit_to_cap_downsamples_large_images():
    r = fit_to_cap(5000, 4000, "opus")
    assert r["downsampled"] is True
    assert max(r["fitted"]["w"], r["fitted"]["h"]) <= 2576
    assert r["fitted"]["tokens"] <= 4784
    small = fit_to_cap(800, 600, "opus")
    assert small["downsampled"] is False


# --- bundle assembly ------------------------------------------------------- #

def test_build_evidence_bundle_set_of_mark(tmp_store):
    step = JourneyStep(
        intent="observe",
        affordances_seen=[
            Affordance(ref="e1", role="button", name="Sign up", bbox=(0.0, 0.0, 10.0, 10.0)),
            Affordance(ref="e2", role="link", name="Home", bbox=(0.0, 20.0, 30.0, 10.0)),
        ],
        post_obs_hash="h1",
    )
    shot = tmp_store.put_artifact(_PIXEL, kind="screenshot", step_id=step.id, content_type="image/png")
    finding = Finding(type="ux_issue", signal="contrast.text", category="a11y",
                      title="low contrast", observed="2.1:1", evidence_refs=[shot.artifact_id],
                      location={"step_id": step.id}, severity=Severity(impact_tier="serious", score=3.0))
    run = CaptureRun(target_url="http://t", artifacts=[shot], steps=[step], findings=[finding])
    bundle = build_evidence_bundle(run, tmp_store, overlay=False)
    assert bundle.step_id == step.id
    assert set(bundle.marks) == {"R1", "R2"}  # one per affordance with a bbox
    assert bundle.token_budget.get("fitted")  # budget computed
    assert any(e.kind == "mark" for e in bundle.facts)
    assert any(e.evidence_id == f"find:{finding.finding_id}" for e in bundle.facts)
    assert "cite" in bundle.contract.lower()


def test_build_evidence_bundle_empty_run(tmp_store):
    bundle = build_evidence_bundle(CaptureRun(target_url="http://t"), tmp_store)
    assert isinstance(bundle, EvidenceBundle) and bundle.marks == {}


def test_no_marks_when_step_lacks_own_screenshot(tmp_store):
    # A stray screenshot (step_id=None) must NOT receive another step's marks.
    step = JourneyStep(intent="x", post_obs_hash="h",
                       affordances_seen=[Affordance(ref="e1", role="button", name="Go", bbox=(0.0, 0.0, 5.0, 5.0))])
    stray = tmp_store.put_artifact(_PIXEL, kind="screenshot", content_type="image/png")  # step_id=None
    run = CaptureRun(target_url="http://t", artifacts=[stray], steps=[step])
    bundle = build_evidence_bundle(run, tmp_store, overlay=False)
    assert bundle.marks == {}  # no marks grounded against a foreign screenshot


def test_overlay_false_references_original_screenshot(tmp_store):
    step = JourneyStep(intent="x", post_obs_hash="h",
                       affordances_seen=[Affordance(ref="e1", role="button", name="Go", bbox=(0.0, 0.0, 5.0, 5.0))])
    shot = tmp_store.put_artifact(_PIXEL, kind="screenshot", step_id=step.id, content_type="image/png")
    run = CaptureRun(target_url="http://t", artifacts=[shot], steps=[step])
    bundle = build_evidence_bundle(run, tmp_store, overlay=False)
    assert bundle.marked_image_artifact_ids == [shot.artifact_id]  # falls back to original
    assert set(bundle.marks) == {"R1"}  # marks still computed as facts


@pytest.mark.skipif(importlib.util.find_spec("PIL") is None, reason="Pillow not installed")
def test_overlay_renders_set_of_mark(tmp_store):
    step = JourneyStep(intent="x", post_obs_hash="h",
                       affordances_seen=[Affordance(ref="e1", role="button", name="Go", bbox=(0.0, 0.0, 5.0, 5.0))])
    shot = tmp_store.put_artifact(_PIXEL, kind="screenshot", step_id=step.id, content_type="image/png")
    run = CaptureRun(target_url="http://t", artifacts=[shot], steps=[step])
    bundle = build_evidence_bundle(run, tmp_store, overlay=True)
    assert bundle.marked_image_artifact_ids  # a marked image was rendered + stored
    assert any(a.meta.get("set_of_mark") for a in run.artifacts)


def test_png_dimensions_truncated_header():
    assert png_dimensions(b"\x89PNG\r\n\x1a\n" + b"\x00" * 4) is None  # valid sig, truncated IHDR


def test_apply_verification_edge_cases():
    f_empty = Finding(type="ux_issue", signal="x", category="ux", observed="o", source_layer="llm")
    apply_verification(f_empty, [])  # no verdicts -> unchanged
    assert f_empty.type == "ux_issue"
    f_single = Finding(type="ux_issue", signal="x", category="ux", observed="o", source_layer="llm")
    apply_verification(f_single, [False])  # 0 of 1 supported -> downgrade
    assert f_single.type == "undetermined"


# --- reliability: cite-or-abstain + marks ---------------------------------- #

def _run_with_artifact(tmp_store):
    art = tmp_store.put_artifact(b"x", kind="dom")
    return CaptureRun(target_url="http://t", artifacts=[art]), art


def test_resolvable_refs(tmp_store):
    run, art = _run_with_artifact(tmp_store)
    assert resolvable(art.artifact_id, run) is True
    assert resolvable("mark:state1#R3", run) is True  # patterned id
    assert resolvable("totally-made-up", run) is False
    assert resolvable("", run) is False


def test_verify_keeps_deterministic_downgrades_unsupported_llm(tmp_store):
    run, art = _run_with_artifact(tmp_store)
    det = Finding(type="ux_issue", signal="a11y.image-alt", category="a11y",
                  observed="missing alt", evidence_refs=[art.artifact_id], source_layer="deterministic")
    llm_ok = Finding(type="ux_issue", signal="ux.copy", category="ux", observed="unclear label",
                     judgment="cites R1", evidence_refs=[art.artifact_id], source_layer="llm")
    llm_bad = Finding(type="ux_issue", signal="ux.guess", category="ux", observed="vibe",
                      judgment="I think so", evidence_refs=[], source_layer="llm")
    report = verify_findings([det, llm_ok, llm_bad], run)
    kept_ids = {f.finding_id for f in report.kept}
    assert det.finding_id in kept_ids and llm_ok.finding_id in kept_ids
    assert llm_bad.finding_id in {f.finding_id for f in report.downgraded}
    assert llm_bad.type == "undetermined" and llm_bad.needs_human_review


def test_verify_mark_membership(tmp_store):
    run, art = _run_with_artifact(tmp_store)
    bundle = EvidenceBundle(marks={"R1": "mark:s#R1"})
    bad = Finding(type="ux_issue", signal="ux.x", category="ux", observed="o",
                  judgment="see region R9", evidence_refs=[art.artifact_id], source_layer="llm")
    report = verify_findings([bad], run, bundle=bundle)
    assert bad.type == "undetermined"  # R9 not in marks -> downgraded


def test_cove_scaffolding():
    f = Finding(type="ux_issue", signal="contrast.text", category="a11y",
                observed="2.1:1", evidence_refs=["art_1"], severity=Severity(impact_tier="serious", score=3.0))
    assert len(verification_questions(f)) >= 3
    apply_verification(f, [False, False, True])  # majority fail
    assert f.type == "undetermined"
    g = Finding(type="ux_issue", signal="x", category="ux", observed="o", source_layer="llm")
    apply_verification(g, [True, True, False])  # majority pass
    assert g.type == "ux_issue"


def test_lookup_evidence_resolves(tmp_store):
    run, art = _run_with_artifact(tmp_store)
    assert lookup_evidence(art.artifact_id, run, tmp_store)["kind"] == "artifact"
    assert lookup_evidence("nope", run, tmp_store)["kind"] == "unresolved"
