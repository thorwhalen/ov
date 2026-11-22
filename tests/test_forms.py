"""The forms analyzer (#21): fixture page with a CSRF contact form, a multipart form, a nav-only select."""

import json
from pathlib import Path

from ov.analysis.ux.forms import extract_forms, header_facts

PAGE = (Path(__file__).parent / "fixtures" / "forms" / "contact.html").read_text()
URL = "https://example.org/contact-us"


def test_extract_forms_records():
    recs = extract_forms(PAGE, URL)
    contact, upload, nav, ajax = recs
    assert contact["action"] == "https://example.org/contact"
    assert contact["method"] == "POST" and contact["encoding"] == "urlencoded"
    assert [f["name"] for f in contact["fields"]] == ["_token", "name", "email", "msg", "website"]
    assert contact["fields"][1]["label"] == "Your name" and contact["fields"][1]["required"]
    assert contact["protections"] == {
        "csrf": True,
        "honeypot_fields": ["website"],
        "captcha": True,
        "file_upload": False,
        "navigation_only": False,
    }
    assert upload["encoding"] == "multipart" and upload["protections"]["file_upload"]
    assert upload["fields"][0]["accept"] == ".pdf,.docx"
    assert nav["protections"]["navigation_only"] is True
    assert nav["fields"][0]["options"] == ["en", "fr"]
    assert ajax["kind"] == "ajax" and ajax["action"] == "https://example.org/api/vote"


def test_header_facts():
    f = header_facts(
        {"Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'", "Set-Cookie": "s=1; Path=/; SameSite=Lax"}
    )
    assert f["framing_blocked"] and f["frame_ancestors"] == "'none'"
    assert f["session_cookie_samesite"] == "Lax"
    assert header_facts({"set-cookie": "<redacted:12>"})["session_cookie_samesite"] is None


def test_analyze_writes_forms_artifact(tmp_store):
    import ov
    from ov.base import CaptureRun

    run = CaptureRun(target_url=URL, mode="reconstruct")
    run.artifacts.append(tmp_store.put_artifact(PAGE.encode(), kind="dom", content_type="text/html", meta={"url": URL}))
    tmp_store.save_run(run)
    summary = ov.analyze(run, lenses=["ux"], store=tmp_store)
    assert summary["forms"]["forms"] == 4
    art = [a for a in run.artifacts if a.kind == "forms"]
    assert len(art) == 1
    assert len(json.loads(tmp_store.artifact_bytes(art[0]))["forms"]) == 4
    ov.analyze(run, lenses=["ux"], store=tmp_store)  # idempotent
    assert len([a for a in run.artifacts if a.kind == "forms"]) == 1
