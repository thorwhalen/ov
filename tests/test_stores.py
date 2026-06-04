"""Tests for the content-addressed Mall store (``ov.capture.stores``)."""

from ov.base import CaptureRun
from ov.capture.stores import CaptureStore, resolve_store


def test_put_artifact_content_addressed_and_dedupes(tmp_store):
    a1 = tmp_store.put_artifact(b"hello", kind="dom")
    a2 = tmp_store.put_artifact(b"hello", kind="dom")
    assert a1.uri == a2.uri  # identical bytes -> same content-addressed uri
    assert tmp_store.artifact_bytes(a1) == b"hello"
    a3 = tmp_store.put_artifact(b"different", kind="dom")
    assert a3.uri != a1.uri


def test_artifact_extension_by_content_type(tmp_store):
    png = tmp_store.put_artifact(b"\x89PNG", kind="screenshot", content_type="image/png")
    assert png.uri.endswith(".png")
    js = tmp_store.put_artifact(b"x=1", kind="request", content_type="application/javascript")
    assert js.uri.endswith(".js")


def test_save_and_load_run(tmp_store):
    run = CaptureRun(target_url="https://x")
    tmp_store.save_run(run)
    assert run.run_id in tmp_store.run_ids()
    loaded = tmp_store.load_run(run.run_id)
    assert loaded.target_url == "https://x"


def test_reports_and_analyses(tmp_store):
    run = CaptureRun(target_url="https://x")
    key = tmp_store.save_report(run.run_id, "00_overview.md", "# hi")
    assert key in tmp_store.report_names(run.run_id)
    tmp_store.save_analysis("an_1", {"k": 1})
    assert tmp_store.load_analysis("an_1") == {"k": 1}


def test_resolve_store_accepts_path_and_instance(tmp_path):
    s = resolve_store(tmp_path / "s")
    assert isinstance(s, CaptureStore)
    assert resolve_store(s) is s
