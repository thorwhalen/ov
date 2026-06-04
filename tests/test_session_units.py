"""Model-free tests for the session wiring, safety enforcement, and facade.

These exercise the browser-free paths the capture tests can't: probe resolution
+ ordering, the safety-default *enforcement* (redaction/header scrubbing), config
serializability, and the facade's clean deferral of not-yet-built phases.
"""

import importlib.util

import pytest

from ov.capture.probes.network import _scrub_headers
from ov.capture.probes.storage import _redact_store
from ov.capture.session import CaptureSession, _resolve_probe_names
from ov.config import OvConfig


def test_resolve_probe_names_reports_unknowns():
    known, unknown = _resolve_probe_names(["network", "dom", "bogus"], OvConfig())
    assert known == ["network", "dom"]
    assert unknown == ["bogus"]


def test_resolve_probe_names_default_and_all():
    cfg = OvConfig()
    default_known, _ = _resolve_probe_names("default", cfg)
    assert set(default_known) == set(cfg.default_probes)
    all_known, _ = _resolve_probe_names("all", cfg)
    assert "perf" in all_known and "storage" in all_known  # heavier probes opt-in via "all"


def test_session_constructs_without_browser_and_notes_unknowns(tmp_store):
    # No start(): construction must not require a browser.
    session = CaptureSession(target_url="https://x", store=tmp_store, probes=["network", "typo"])
    assert session.probe_names == ["network"]
    assert any("typo" in n for n in session.run.notes)
    assert session.run.target_url == "https://x"


def test_safety_header_scrubbing_enforced():
    headers = {"cookie": "sid=abc", "authorization": "Bearer t", "content-type": "text/html"}
    scrubbed = _scrub_headers(headers, redact=True)
    assert scrubbed["cookie"].startswith("<redacted")
    assert scrubbed["authorization"].startswith("<redacted")
    assert scrubbed["content-type"] == "text/html"  # non-sensitive header preserved
    # redact=False is a deliberate opt-out
    assert _scrub_headers(headers, redact=True) != _scrub_headers(headers, redact=False)


def test_safety_storage_redaction_enforced():
    store = {"token": "secret", "theme": "dark"}
    redacted = _redact_store(store, redact=True)
    assert all(v.startswith("<redacted") for v in redacted.values())
    assert _redact_store(store, redact=False) == store


def test_config_snapshot_is_json_serializable():
    import json

    snap = OvConfig().snapshot()
    # must round-trip through JSON for CaptureRun.settings_snapshot persistence
    assert json.loads(json.dumps(snap))["redact_values"] is True


@pytest.mark.parametrize(
    "func_name, module",
    [
        ("analyze", "ov.analysis.run"),
        ("report", "ov.reporting.render"),
        ("synopsis", "ov.reporting.synopsis"),
        ("overview", "ov.reporting.overview"),
    ],
)
def test_facade_defers_unbuilt_phases_cleanly(func_name, module):
    """Phase-2+ facade functions raise NotImplementedError (not ModuleNotFoundError)
    while their module is absent; once the module exists this assertion is skipped."""
    import ov

    if importlib.util.find_spec(module) is not None:
        pytest.skip(f"{module} is implemented; deferral no longer applies")
    func = getattr(ov, func_name)
    with pytest.raises(NotImplementedError):
        func("x")
