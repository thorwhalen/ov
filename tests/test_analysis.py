"""Deterministic analysis tests over synthetic artifacts (no browser, no model)."""

import json

from ov.analysis.arch.api import analyze_api
from ov.analysis.arch.bundles import analyze_bundles, detect_source_maps
from ov.analysis.arch.framework import analyze_framework
from ov.analysis.arch.rendering import analyze_rendering, classify_rendering
from ov.analysis.context import AnalysisContext
from ov.analysis.run import run_analysis
from ov.analysis.ux.a11y import analyze_a11y
from ov.analysis.ux.contrast_focus import analyze_contrast_focus, contrast_ratio
from ov.analysis.ux.cwv import analyze_cwv, cwv_from_perf
from ov.analysis.ux.heuristics import analyze_heuristics
from ov.analysis.ux.metrics import analyze_metrics, form_friction
from ov.base import Action, CaptureRun, JourneyStep


def _run_with(store, artifacts, **run_kw):
    return CaptureRun(target_url="http://t.example", artifacts=list(artifacts), **run_kw)


def _ctx(store, run):
    return AnalysisContext(run=run, store=store)


# --- UX: accessibility ----------------------------------------------------- #

def test_a11y_detects_perennials(tmp_store):
    html = (
        "<html><body>"
        "<img src='x.png'>"  # missing alt
        "<a href='/p'></a>"  # empty link
        "<button></button>"  # empty button
        "<form><input type='text' name='q'></form>"  # unlabeled control
        "</body></html>"
    )
    art = tmp_store.put_artifact(html.encode(), kind="dom", content_type="text/html")
    out = analyze_a11y(_ctx(tmp_store, _run_with(tmp_store, [art])))
    signals = {f.signal for f in out.findings}
    assert {"a11y.html-lang", "a11y.image-alt", "a11y.link-name",
            "a11y.button-name", "a11y.form-label"} <= signals
    # honesty: a manual-review finding is always present
    assert any(f.needs_human_review and f.type == "undetermined" for f in out.findings)


def test_a11y_alt_present_not_flagged(tmp_store):
    html = "<html lang='en'><body><img src='x' alt='a cat'></body></html>"
    art = tmp_store.put_artifact(html.encode(), kind="dom", content_type="text/html")
    out = analyze_a11y(_ctx(tmp_store, _run_with(tmp_store, [art])))
    signals = {f.signal for f in out.findings}
    assert "a11y.image-alt" not in signals
    assert "a11y.html-lang" not in signals


# --- UX: contrast ---------------------------------------------------------- #

def test_contrast_flags_low_ratio(tmp_store):
    styles = [{"selector": "p", "text": "hi", "fg": [200, 200, 200], "bg": [255, 255, 255],
               "fontSize": 16, "large": False}]
    art = tmp_store.put_artifact(json.dumps(styles).encode(), kind="a11y_styles",
                                 content_type="application/json")
    out = analyze_contrast_focus(_ctx(tmp_store, _run_with(tmp_store, [art])))
    contrast = [f for f in out.findings if f.signal == "contrast.text"]
    assert contrast and contrast[0].wcag_criterion["id"] == "1.4.3"


def test_contrast_passes_high_ratio(tmp_store):
    styles = [{"selector": "p", "fg": [0, 0, 0], "bg": [255, 255, 255], "large": False}]
    art = tmp_store.put_artifact(json.dumps(styles).encode(), kind="a11y_styles",
                                 content_type="application/json")
    out = analyze_contrast_focus(_ctx(tmp_store, _run_with(tmp_store, [art])))
    assert not [f for f in out.findings if f.signal == "contrast.text"]


# --- UX: CWV --------------------------------------------------------------- #

def test_cwv_flags_threshold_breaches(tmp_store):
    payload = {"vitals": {"inp": [{"duration": 300, "interactionId": 1}],
                          "cls": [{"value": 0.2}], "lcp": [{"value": 3000}]},
               "navigation": {"ttfb": 900}}
    art = tmp_store.put_artifact(json.dumps(payload).encode(), kind="perf",
                                 content_type="application/json")
    out = analyze_cwv(_ctx(tmp_store, _run_with(tmp_store, [art])))
    signals = {f.signal for f in out.findings}
    assert {"cwv.inp", "cwv.cls", "cwv.lcp", "cwv.ttfb"} <= signals


def test_cwv_from_perf_inp_grouping():
    metrics = cwv_from_perf({"vitals": {"inp": [{"duration": 50, "interactionId": 1},
                                                  {"duration": 90, "interactionId": 1}]}})
    assert metrics["inp"] == 90  # max within an interactionId


# --- UX: form friction + journey ------------------------------------------- #

def test_form_friction_cliff(tmp_store):
    inputs = "".join(f"<input name='f{i}' required>" for i in range(8))
    html = f"<html lang='en'><body><form id='signup'>{inputs}</form></body></html>"
    art = tmp_store.put_artifact(html.encode(), kind="dom", content_type="text/html")
    out = analyze_metrics(_ctx(tmp_store, _run_with(tmp_store, [art])))
    friction = [f for f in out.findings if f.signal == "form.friction"]
    assert friction and friction[0].severity.impact_tier == "serious"


def test_form_friction_thresholds():
    assert form_friction(3, 1) is None
    assert form_friction(6, 2)[0] == "moderate"
    assert form_friction(12, 5)[0] == "critical"


# --- arch: rendering ------------------------------------------------------- #

def test_rendering_csr_from_artifacts(tmp_store):
    raw = "<html><body><div id='root'></div></body></html>"
    rendered = "<html><body><div id='root'><h1>Welcome</h1><p>lots of rendered content here</p></div></body></html>"
    raw_art = tmp_store.put_artifact(raw.encode(), kind="request", content_type="text/html")
    dom_art = tmp_store.put_artifact(rendered.encode(), kind="dom", content_type="text/html")
    records = [{"url": "http://t.example/", "resource_type": "document", "status": 200,
                "body_artifact_id": raw_art.artifact_id, "response_headers": {"content-type": "text/html"}}]
    net_art = tmp_store.put_artifact(json.dumps(records).encode(), kind="network",
                                     content_type="application/json")
    run = _run_with(tmp_store, [raw_art, dom_art, net_art])
    out = analyze_rendering(_ctx(tmp_store, run))
    assert out.run_fields["rendering_model"] == "csr"


def test_classify_rendering_ssr():
    page = "<html><body><h1>Title</h1><p>full server-rendered article body text here</p></body></html>"
    assert classify_rendering(page, page)[0] == "ssr-or-ssg"


# --- arch: API surface ----------------------------------------------------- #

def test_api_synthesis(tmp_store):
    body = tmp_store.put_artifact(json.dumps({"id": 1, "name": "x"}).encode(),
                                  kind="request", content_type="application/json")
    records = [{
        "url": "http://t.example/api/users/42", "method": "GET", "status": 200,
        "resource_type": "xhr", "response_headers": {"content-type": "application/json"},
        "request_headers": {"authorization": "<redacted:30>"},
        "body_artifact_id": body.artifact_id,
    }]
    net = tmp_store.put_artifact(json.dumps(records).encode(), kind="network",
                                 content_type="application/json")
    out = analyze_api(_ctx(tmp_store, _run_with(tmp_store, [body, net])))
    assert len(out.endpoints) == 1
    ep = out.endpoints[0]
    assert ep.method == "GET" and ep.path_template == "/api/users/{id}"
    assert ep.kind == "rest" and ep.auth == "bearer"
    assert ep.response_schema and ep.response_schema.get("type") == "object"


# --- arch: source maps + framework ---------------------------------------- #

def test_detect_source_maps_pure():
    assert detect_source_maps([("a.js", "x=1\n//# sourceMappingURL=a.js.map")], [])[0] is True
    assert detect_source_maps([("a.js", "x=1")], [])[0] is False


def test_bundles_and_framework(tmp_store):
    js = "var x=1;\nfunction __webpack_require__(){}\n//# sourceMappingURL=app.js.map"
    body = tmp_store.put_artifact(js.encode(), kind="request", content_type="application/javascript")
    records = [{"url": "http://t.example/app.js", "resource_type": "script", "status": 200,
                "response_headers": {"content-type": "application/javascript"},
                "body_artifact_id": body.artifact_id}]
    net = tmp_store.put_artifact(json.dumps(records).encode(), kind="network",
                                 content_type="application/json")
    dom = tmp_store.put_artifact(b"<html><body></body></html>", kind="dom", content_type="text/html")
    run = _run_with(tmp_store, [body, net, dom])
    ctx = _ctx(tmp_store, run)
    assert analyze_bundles(ctx).run_fields["source_maps_present"] is True
    fw = analyze_framework(ctx)
    assert any(t.name == "webpack" for t in fw.tech)


# --- orchestrator end-to-end (synthetic) ----------------------------------- #

def test_run_analysis_end_to_end(tmp_store):
    html = "<html><body><img src='x'><form><input name='a'><input name='b'><input name='c'>" \
           "<input name='d'><input name='e' required></form></body></html>"
    dom = tmp_store.put_artifact(html.encode(), kind="dom", content_type="text/html")
    net = tmp_store.put_artifact(b"[]", kind="network", content_type="application/json")
    console = tmp_store.put_artifact(b"[]", kind="console", content_type="application/json")
    run = _run_with(tmp_store, [dom, net, console],
                    steps=[JourneyStep(intent="load", post_obs_hash="h1")])
    tmp_store.save_run(run)
    results = run_analysis(run, store=tmp_store)
    assert "a11y" in results and "rendering" in results
    assert run.findings  # at least a11y perennials
    # idempotent: re-running doesn't duplicate (counts AND signals stable)
    sigs = sorted(f.signal for f in run.findings)
    run_analysis(run, store=tmp_store)
    assert sorted(f.signal for f in run.findings) == sigs


# --- heuristics ------------------------------------------------------------ #

def test_heuristics_console_error_and_missing_feedback(tmp_store):
    dom = tmp_store.put_artifact(b"<html><body><button>x</button></body></html>",
                                 kind="dom", content_type="text/html")
    s1 = JourneyStep(id="s1", intent="do x", action=Action(type="click", ref="e1"),
                     outcome="ok", post_obs_hash="h1")
    s2 = JourneyStep(id="s2", intent="do y", action=Action(type="click", ref="e2"),
                     outcome="noop", post_obs_hash="h1", network_delta=0)
    console = [{"kind": "console", "type": "error", "text": "boom", "step_id": "s1"}]
    cons = tmp_store.put_artifact(json.dumps(console).encode(), kind="console",
                                  content_type="application/json")
    out = analyze_heuristics(_ctx(tmp_store, _run_with(tmp_store, [dom, cons], steps=[s1, s2])))
    signals = {f.signal for f in out.findings}
    assert "heuristic.console-error" in signals
    assert "heuristic.no-feedback" in signals  # noop click, no network


def test_heuristics_live_region_absence(tmp_store):
    dom = tmp_store.put_artifact(b"<html><body><div>static</div></body></html>",
                                 kind="dom", content_type="text/html")
    step = JourneyStep(id="s1", intent="click", action=Action(type="click", ref="e1"),
                       outcome="ok", post_obs_hash="h2")
    cons = tmp_store.put_artifact(b"[]", kind="console", content_type="application/json")
    out = analyze_heuristics(_ctx(tmp_store, _run_with(tmp_store, [dom, cons], steps=[step])))
    assert any(f.signal == "heuristic.no-live-region" for f in out.findings)


def test_journey_backtracking(tmp_store):
    dom = tmp_store.put_artifact(b"<html></html>", kind="dom", content_type="text/html")
    steps = [JourneyStep(post_obs_hash=h) for h in ("a", "b", "a", "a")]
    out = analyze_metrics(_ctx(tmp_store, _run_with(tmp_store, [dom], steps=steps)))
    assert any(f.signal == "journey.backtracking" for f in out.findings)


# --- graceful degradation + isolation -------------------------------------- #

def test_dependencies_degrades_without_retire(tmp_store, monkeypatch):
    import ov.analysis.arch.dependencies as dep

    monkeypatch.setattr(dep.shutil, "which", lambda name: None)
    fp = tmp_store.put_artifact(b"{}", kind="fingerprint", content_type="application/json")
    out = dep.analyze_dependencies(_ctx(tmp_store, _run_with(tmp_store, [fp])))
    assert any(f.signal == "deps.cve-scan-skipped" and f.needs_human_review for f in out.findings)


def test_run_analysis_isolates_failing_analyzer(tmp_store):
    from ov.analysis import ANALYZER_REGISTRY, register_analyzer

    @register_analyzer("boom_test", lens="ux")
    def _boom(ctx):
        raise RuntimeError("kaboom")

    try:
        dom = tmp_store.put_artifact(b"<html lang='en'><body></body></html>", kind="dom", content_type="text/html")
        net = tmp_store.put_artifact(b"[]", kind="network", content_type="application/json")
        run = _run_with(tmp_store, [dom, net])
        tmp_store.save_run(run)
        results = run_analysis(run, store=tmp_store)
        assert "boom_test" not in results  # crashed -> skipped
        assert any("boom_test" in n for n in run.notes)  # error recorded
        assert "a11y" in results  # other analyzers still ran
    finally:
        ANALYZER_REGISTRY._items.pop("boom_test", None)


def test_bundles_no_source_maps(tmp_store):
    js = tmp_store.put_artifact(b"var x=1;", kind="request", content_type="application/javascript")
    records = [{"url": "http://t/app.js", "resource_type": "script", "status": 200,
                "response_headers": {"content-type": "application/javascript"},
                "body_artifact_id": js.artifact_id}]
    net = tmp_store.put_artifact(json.dumps(records).encode(), kind="network", content_type="application/json")
    out = analyze_bundles(_ctx(tmp_store, _run_with(tmp_store, [js, net])))
    assert out.run_fields["source_maps_present"] is False


def test_contrast_no_styles_only_manual(tmp_store):
    out = analyze_contrast_focus(_ctx(tmp_store, _run_with(tmp_store, [])))
    assert not [f for f in out.findings if f.signal == "contrast.text"]
    assert any(f.signal == "focus.behavioral-review-required" for f in out.findings)


def test_classify_rendering_hybrid_and_globals():
    raw = "<html><body>" + " ".join(["word"] * 50) + "</body></html>"
    rendered = "<html><body>" + " ".join(["word"] * 100) + "</body></html>"
    assert classify_rendering(raw, rendered)[0] == "hybrid"  # 0.3 < divergence < 0.7
    model, conf, _ = classify_rendering(rendered, rendered, {"__NEXT_DATA__": True})
    assert model == "ssr-or-ssg" and conf >= 80


def test_coverage_confidence_scoring():
    from ov.analysis.arch.api import _coverage_confidence

    assert _coverage_confidence(0, set()) == 0
    assert _coverage_confidence(5, {200}) == 75  # base 50 + 2xx 25
    assert _coverage_confidence(5, {200, 404}) == 100  # + error path 25


def test_cwv_sparse_payloads():
    assert cwv_from_perf({"navigation": {"ttfb": 100}})["inp"] is None
    assert cwv_from_perf({})["cls"] is None


def test_sidecar_unavailable_when_missing():
    from ov.analysis.arch.sidecar import Sidecar

    assert Sidecar(script="/nonexistent/server.js").available() is False


def test_merge_output_fills_version_and_unions_categories():
    from ov.analysis.context import AnalyzerOutput
    from ov.analysis.run import merge_output
    from ov.base import TechFinding

    run = CaptureRun(target_url="http://t", fingerprint=[
        TechFinding(name="webpack", categories=["bundler"], version=None,
                    confidence=70, provenance=["window.webpack"])])
    out = AnalyzerOutput(tech=[
        TechFinding(name="webpack", categories=["dependency"], version="5.88.0",
                    confidence=95, provenance=["sourcemap"])])
    merge_output(run, out)
    wp = next(t for t in run.fingerprint if t.name == "webpack")
    assert wp.version == "5.88.0"  # recovered version fills the versionless detection
    assert set(wp.categories) == {"bundler", "dependency"}  # union keeps bundler identity
    assert wp.confidence == 95
