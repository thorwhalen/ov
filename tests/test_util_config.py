"""Tests for util helpers, config, and check_requirements."""

from ov.config import OvConfig
from ov.util import (
    RequirementReport,
    check_requirements,
    content_hash,
    redact_mapping,
    redact_value,
    stable_hash,
)


def test_content_hash_stable_and_str_bytes_equiv():
    assert content_hash(b"hello") == content_hash("hello")
    assert content_hash(b"a") != content_hash(b"b")
    assert len(content_hash(b"x", length=8)) == 8


def test_stable_hash_order_independent():
    assert stable_hash({"a": 1, "b": 2}) == stable_hash({"b": 2, "a": 1})
    assert stable_hash([1, 2]) != stable_hash([2, 1])


def test_redaction_keeps_shape_drops_content():
    assert redact_value("secret") == "<redacted:6>"
    assert redact_value(None) == "<redacted>"
    out = redact_mapping({"token": "abc"}, redact=True)
    assert out == {"token": "<redacted:3>"}
    assert redact_mapping({"k": "v"}, redact=False) == {"k": "v"}


def test_config_from_env_and_snapshot(monkeypatch):
    monkeypatch.setenv("OV_HEADED", "true")
    monkeypatch.setenv("OV_MAX_STEPS", "7")
    monkeypatch.setenv("OV_AUTHORIZED", "yes")
    cfg = OvConfig.from_env()
    assert cfg.headed is True and cfg.max_steps == 7 and cfg.authorized is True
    snap = cfg.snapshot()
    assert isinstance(snap["store_root"], str)  # Path serialized
    assert snap["default_probes"] == list(cfg.default_probes)


def test_config_safety_defaults():
    cfg = OvConfig()
    assert cfg.redact_values is True
    assert cfg.capture_secrets is False
    assert cfg.respect_robots is True
    assert cfg.authorized is False  # foreign targets must opt in


def test_check_requirements_reports_and_messages():
    rep = check_requirements(components=["clis"], verbose=False)
    assert isinstance(rep, RequirementReport)
    text = rep.render()
    assert "ov requirements" in text
    # optional CLIs missing should still produce install hints
    for r in rep:
        if not r.present:
            assert r.install_hint
