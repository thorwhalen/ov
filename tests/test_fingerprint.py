"""Tests for the license-clean technology detector (pure, no browser)."""

from ov.capture.probes.fingerprint import detect_technologies


def test_detect_next_implies_react():
    findings = detect_technologies({"globals": {"__NEXT_DATA__": True}})
    names = {f.name for f in findings}
    assert "Next.js" in names and "React" in names
    next_f = next(f for f in findings if f.name == "Next.js")
    react_f = next(f for f in findings if f.name == "React")
    assert next_f.confidence > react_f.confidence  # explicit beats implied


def test_detect_ng_version_sets_version():
    findings = detect_technologies({"ngVersion": "17.1.0"})
    ng = next(f for f in findings if f.name == "Angular")
    assert ng.version == "17.1.0" and ng.confidence >= 90


def test_detect_from_headers():
    findings = detect_technologies({"globals": {}}, {"x-powered-by": "Express"})
    assert any(f.name == "Express" for f in findings)


def test_detect_meta_generator():
    findings = detect_technologies({"metaGenerator": "Hugo 0.120"})
    assert any(f.name == "Hugo" for f in findings)


def test_findings_sorted_by_confidence_desc():
    findings = detect_technologies(
        {"globals": {"__NEXT_DATA__": True, "jquery": True, "webpack": True}}
    )
    confidences = [f.confidence for f in findings]
    assert confidences == sorted(confidences, reverse=True)
    for f in findings:
        assert f.provenance  # every finding records provenance
