"""End-to-end capture tests against the hermetic local site (browser-gated).

These exercise the real Playwright capture spine; they skip cleanly when a
Chromium browser is not launchable, keeping the deterministic core green
everywhere (e.g. CI without ``playwright install``).
"""

import json

import pytest

from _browser import requires_browser

pytestmark = requires_browser


def _artifacts_by_kind(run, store, kind):
    return [a for a in run.artifacts if a.kind == kind]


@requires_browser
def test_observe_static_site_populates_run(local_site, tmp_store):
    import ov

    run = ov.observe(f"{local_site}/index.html", store=tmp_store)
    assert run.target_url.endswith("/index.html")
    assert run.finished_at is not None
    assert len(run.steps) >= 1

    # core artifact kinds present
    kinds = {a.kind for a in run.artifacts}
    assert {"dom", "screenshot", "network", "fingerprint", "assets"} <= kinds

    # fingerprint detected something (React global / generator meta were seeded)
    names = {t.name for t in run.fingerprint}
    assert "React" in names or "TestGen" in names

    # run persisted and reloadable
    reloaded = tmp_store.load_run(run.run_id)
    assert reloaded.run_id == run.run_id


@requires_browser
def test_network_records_capture_requests(local_site, tmp_store):
    import ov

    run = ov.observe(f"{local_site}/index.html", store=tmp_store)
    net = _artifacts_by_kind(run, tmp_store, "network")
    assert net
    records = json.loads(tmp_store.artifact_bytes(net[0]).decode())
    urls = [r["url"] for r in records]
    assert any("index.html" in u for u in urls)
    # the document response carries headers
    docs = [r for r in records if r.get("resource_type") == "document"]
    assert docs and "response_headers" in docs[0]


@requires_browser
def test_dom_includes_aria_and_ax(local_site, tmp_store):
    import ov

    run = ov.observe(f"{local_site}/index.html", store=tmp_store)
    kinds = {a.kind for a in run.artifacts}
    assert "aria_snapshot" in kinds  # agent view
    assert "ax_tree" in kinds  # CDP evidence (Chromium)


@requires_browser
def test_crawl_visits_multiple_pages(local_site, tmp_store):
    import ov

    run = ov.observe(f"{local_site}/index.html", store=tmp_store, crawl_pages=3)
    # at least the initial load + one crawled page
    nav_steps = [s for s in run.steps if s.intent in ("load", "enumerate")]
    assert len(nav_steps) >= 2


@requires_browser
def test_observe_with_probes_all_adds_perf_storage(local_site, tmp_store):
    import ov

    run = ov.observe(f"{local_site}/index.html", store=tmp_store, probes="all")
    kinds = {a.kind for a in run.artifacts}
    assert "perf" in kinds and "storage" in kinds


@requires_browser
def test_overview_pipeline_end_to_end(local_site, tmp_store):
    import json

    import ov

    md_key = ov.overview(f"{local_site}/index.html", store=tmp_store)
    assert str(md_key).endswith("SYNOPSIS.md")
    run_id = tmp_store.run_ids()[-1]
    run = tmp_store.load_run(run_id)
    # analysis populated the run
    assert run.findings
    assert run.rendering_model in ("csr", "ssr-or-ssg", "hybrid", "unknown")
    # the test site has a missing-alt image, an unlabeled input, and low-contrast text
    signals = {f.signal for f in run.findings}
    assert {"a11y.image-alt", "a11y.form-label"} & signals
    # synopsis json is the SSOT and resolves
    doc = json.loads(tmp_store.reports[f"{run_id}/synopsis.json"])
    assert doc["findings"] and "severity_histogram" in doc


@requires_browser
def test_operate_observe_and_act(local_site, tmp_store):
    from ov.base import Action
    from ov.capture.session import CaptureSession
    from ov.operate import act, observe

    with CaptureSession(target_url=f"{local_site}/spa.html", store=tmp_store) as session:
        session.open()
        obs = observe(session.page)
        assert obs.affordances  # buttons discovered
        # click the "About" button (find its ref by name)
        about = next((a for a in obs.affordances if "About" in a.name), None)
        assert about is not None
        result = act(session.page, Action(type="click", ref=about.ref, description="About"))
        assert result.ok
        assert result.observation is not None
