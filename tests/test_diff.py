"""Own-target review-mode diffing tests (deterministic, no browser, no model).

Covers the cross-run finding identity (:func:`finding_key`), the pure
classification (:func:`diff_runs`), baseline auto-discovery + persistence
(:func:`build_diff`), and how the diff flows into the review report section and
the regression synopsis.
"""

from __future__ import annotations

import json
from datetime import timedelta

import ov
from ov.analysis.diff import build_diff, diff_runs, find_baseline_run, finding_key
from ov.base import (
    CaptureRun,
    Endpoint,
    Finding,
    Severity,
    TechFinding,
    utcnow,
)
from ov.reporting.render import render_reports
from ov.reporting.synopsis import build_synopsis, build_synopsis_doc


def _finding(
    signal="contrast.text",
    *,
    score=3.0,
    selector=None,
    cat="a11y",
    type_="ux_issue",
    title=None,
    observed="",
    engine_rule_id=None,
):
    return Finding(
        type=type_,
        signal=signal,
        category=cat,
        title=title if title is not None else signal,
        observed=observed,
        engine_rule_id=engine_rule_id,
        severity=Severity(impact_tier="serious", score=score)
        if score is not None
        else None,
        location={"selector": selector} if selector else None,
    )


# --------------------------------------------------------------------------- #
# finding_key — stable cross-run identity
# --------------------------------------------------------------------------- #


def test_finding_key_ignores_per_run_ids():
    a = Finding(
        type="ux_issue",
        signal="x",
        category="ux",
        location={"selector": "#a", "step_id": "step_1"},
    )
    b = Finding(
        type="ux_issue",
        signal="x",
        category="ux",
        location={"selector": "#a", "step_id": "step_2"},
    )
    assert finding_key(a) == finding_key(b)  # step_id differs, identity holds


def test_finding_key_distinguishes_locator_and_signal():
    assert finding_key(_finding("x", selector="#a")) != finding_key(
        _finding("x", selector="#b")
    )
    assert finding_key(_finding("x", selector="#a")) != finding_key(
        _finding("y", selector="#a")
    )


def test_finding_key_incorporates_engine_and_wcag():
    base = _finding("a11y.axe", selector="#a")
    with_rule = _finding("a11y.axe", selector="#a", engine_rule_id="axe:color-contrast")
    assert finding_key(base) != finding_key(with_rule)
    wcag = Finding(
        type="ux_issue",
        signal="a11y.axe",
        category="a11y",
        wcag_criterion={"id": "1.4.3"},
        location={"selector": "#a"},
    )
    assert "wcag:1.4.3" in finding_key(wcag)


def test_finding_key_falls_back_to_targets_then_intent():
    by_targets = Finding(
        type="ux_issue", signal="s", category="a11y", location={"targets": ["#a", "#b"]}
    )
    assert "#a|#b" in finding_key(by_targets)
    by_intent = Finding(
        type="ux_issue",
        signal="s",
        category="ux",
        location={"intent": "advance", "step_id": "step_9"},
    )
    assert finding_key(by_intent).endswith("advance")  # step_id excluded


# --------------------------------------------------------------------------- #
# diff_runs — pure classification + in-place annotation
# --------------------------------------------------------------------------- #


def test_diff_runs_classifies_new_changed_resolved_unchanged():
    baseline = CaptureRun(
        target_url="u",
        findings=[
            _finding("a", score=2.0, selector="#a"),  # will change (severity up)
            _finding("b", score=3.0, selector="#b"),  # will be resolved (gone)
            _finding("c", score=1.0, selector="#c"),  # unchanged
        ],
    )
    current = CaptureRun(
        target_url="u",
        findings=[
            _finding("a", score=5.0, selector="#a"),  # changed
            _finding("c", score=1.0, selector="#c"),  # unchanged
            _finding("d", score=4.0, selector="#d"),  # new
        ],
    )
    diff = diff_runs(current, baseline)
    assert diff.counts == {"new": 1, "changed": 1, "resolved": 1, "unchanged": 0 + 1}

    by_signal = {d.signal: d for d in diff.finding_deltas}
    assert by_signal["a"].status == "changed"
    assert by_signal["c"].status == "unchanged"
    assert by_signal["d"].status == "new"
    assert by_signal["b"].status == "resolved"
    # diff_status set in place on the current run's findings
    assert current.findings[0].diff_status == "changed"
    assert current.findings[1].diff_status is None  # unchanged carries no annotation
    assert current.findings[2].diff_status == "new"


def test_diff_runs_direction_regression_and_improvement():
    baseline = CaptureRun(
        target_url="u",
        findings=[
            _finding("up", score=2.0, selector="#u"),
            _finding("down", score=5.0, selector="#d"),
            _finding("gone", score=4.0, selector="#g"),
        ],
    )
    current = CaptureRun(
        target_url="u",
        findings=[
            _finding("up", score=4.0, selector="#u"),  # worse -> regression
            _finding("down", score=1.0, selector="#d"),  # better -> improvement
            _finding(
                "fresh", score=3.0, selector="#f"
            ),  # new with severity -> regression
        ],
    )
    diff = diff_runs(current, baseline)
    reg = {d.signal for d in diff.regressions}
    imp = {d.signal for d in diff.improvements}
    assert reg == {"up", "fresh"}
    assert imp == {"down", "gone"}  # resolved 'gone' is an improvement


def test_diff_runs_new_without_severity_is_neutral():
    baseline = CaptureRun(target_url="u", findings=[])
    current = CaptureRun(
        target_url="u",
        findings=[
            Finding(
                type="undetermined", signal="x.manual", category="a11y", title="manual"
            ),
        ],
    )
    diff = diff_runs(current, baseline)
    assert diff.finding_deltas[0].status == "new"
    assert (
        diff.finding_deltas[0].direction == "neutral"
    )  # no severity -> not a regression
    assert "no analyzed findings" in " ".join(diff.notes)


def test_diff_runs_tech_endpoint_and_field_deltas():
    baseline = CaptureRun(
        target_url="u",
        rendering_model="csr",
        source_maps_present=False,
        fingerprint=[
            TechFinding(name="React", confidence=80),
            TechFinding(name="jQuery", confidence=50),
        ],
        api_surface=[Endpoint(method="GET", path_template="/a", kind="rest")],
    )
    current = CaptureRun(
        target_url="u",
        rendering_model="ssr",
        source_maps_present=True,
        fingerprint=[
            TechFinding(name="React", confidence=90),
            TechFinding(name="Vite", confidence=70),
        ],
        api_surface=[
            Endpoint(method="GET", path_template="/a", kind="rest"),
            Endpoint(method="POST", path_template="/b", kind="rest"),
        ],
    )
    diff = diff_runs(current, baseline)
    assert diff.tech_added == ["Vite"]
    assert diff.tech_removed == ["jQuery"]
    assert diff.endpoints_added == ["POST /b"]
    assert diff.endpoints_removed == []
    assert diff.rendering_model_change == {"from": "csr", "to": "ssr"}
    assert diff.source_maps_change == {"from": False, "to": True}
    assert diff.has_drift is True


def test_diff_runs_identical_has_no_drift():
    findings = [_finding("a", score=2.0, selector="#a")]
    baseline = CaptureRun(
        target_url="u", findings=[_finding("a", score=2.0, selector="#a")]
    )
    current = CaptureRun(target_url="u", findings=findings)
    diff = diff_runs(current, baseline)
    assert diff.counts["unchanged"] == 1
    assert diff.has_drift is False
    assert current.findings[0].diff_status is None


# --------------------------------------------------------------------------- #
# build_diff — baseline resolution + persistence
# --------------------------------------------------------------------------- #


def _save_run(
    store, *, signals_scores, mode="review", started_at=None, target="http://t"
):
    run = CaptureRun(
        target_url=target,
        mode=mode,
        findings=[_finding(s, score=sc, selector="#" + s) for s, sc in signals_scores],
    )
    if started_at is not None:
        run.started_at = started_at
    store.save_run(run)
    return run


def test_build_diff_auto_discovers_latest_prior_run(tmp_store):
    t0 = utcnow()
    old = _save_run(
        tmp_store, signals_scores=[("a", 2.0)], started_at=t0 - timedelta(hours=2)
    )
    mid = _save_run(
        tmp_store, signals_scores=[("a", 3.0)], started_at=t0 - timedelta(hours=1)
    )
    cur = _save_run(tmp_store, signals_scores=[("a", 5.0)], started_at=t0)

    base = find_baseline_run(tmp_store, cur)
    assert base.run_id == mid.run_id  # latest *prior*, not the oldest

    diff = build_diff(cur, store=tmp_store)
    assert diff is not None
    assert diff.baseline_run_id == mid.run_id
    assert diff.counts["changed"] == 1  # 3.0 -> 5.0


def test_build_diff_persists_run_and_blob(tmp_store):
    t0 = utcnow()
    _save_run(
        tmp_store, signals_scores=[("a", 2.0)], started_at=t0 - timedelta(hours=1)
    )
    cur = _save_run(tmp_store, signals_scores=[("a", 5.0), ("b", 3.0)], started_at=t0)

    diff = build_diff(cur, store=tmp_store)
    assert diff is not None
    # diff_status persisted on the reloaded run
    reloaded = tmp_store.load_run(cur.run_id)
    statuses = {f.signal: f.diff_status for f in reloaded.findings}
    assert statuses == {"a": "changed", "b": "new"}
    # diff blob persisted and self-describing
    blob = tmp_store.load_analysis(f"diff_{cur.run_id}")
    assert blob["baseline_run_id"] and blob["counts"]["new"] == 1


def test_build_diff_no_baseline_returns_none_with_note(tmp_store):
    cur = _save_run(tmp_store, signals_scores=[("a", 2.0)])
    diff = build_diff(cur, store=tmp_store)
    assert diff is None
    reloaded = tmp_store.load_run(cur.run_id)
    assert any("no prior baseline" in n for n in reloaded.notes)


def test_build_diff_explicit_baseline_id(tmp_store):
    base = _save_run(tmp_store, signals_scores=[("a", 2.0)], target="http://other")
    cur = _save_run(tmp_store, signals_scores=[("a", 9.0)], target="http://t")
    # different targets -> auto-discovery finds nothing, but explicit id is honored
    assert find_baseline_run(tmp_store, cur) is None
    diff = build_diff(cur, baseline=base.run_id, store=tmp_store)
    assert diff is not None and diff.baseline_run_id == base.run_id


def test_find_baseline_ignores_other_targets(tmp_store):
    t0 = utcnow()
    _save_run(
        tmp_store,
        signals_scores=[("a", 2.0)],
        target="http://other",
        started_at=t0 - timedelta(hours=1),
    )
    cur = _save_run(
        tmp_store, signals_scores=[("a", 5.0)], target="http://t", started_at=t0
    )
    assert find_baseline_run(tmp_store, cur) is None


# --------------------------------------------------------------------------- #
# report section + synopsis integration
# --------------------------------------------------------------------------- #


def test_review_section_renders_diff(tmp_store):
    t0 = utcnow()
    _save_run(
        tmp_store,
        signals_scores=[("a", 2.0), ("gone", 3.0)],
        started_at=t0 - timedelta(hours=1),
    )
    cur = _save_run(
        tmp_store, signals_scores=[("a", 5.0), ("fresh", 4.0)], started_at=t0
    )
    build_diff(cur, store=tmp_store)

    render_reports(cur, store=tmp_store)
    md = tmp_store.reports[f"{cur.run_id}/40_review_audit.md"]
    assert "Drift vs. prior run" in md
    assert "New findings" in md and "Resolved findings" in md
    assert "`fresh`" in md  # the new finding's signal appears
    assert "1 new · 1 changed · 1 resolved" in md


def test_review_section_without_baseline_shows_hint(tmp_store):
    cur = _save_run(tmp_store, signals_scores=[("a", 2.0)])
    build_diff(cur, store=tmp_store)  # no baseline -> no blob
    render_reports(cur, store=tmp_store)
    md = tmp_store.reports[f"{cur.run_id}/40_review_audit.md"]
    assert "No baseline run found" in md


def test_synopsis_includes_regression_block(tmp_store):
    t0 = utcnow()
    _save_run(
        tmp_store,
        signals_scores=[("a", 2.0), ("gone", 3.0)],
        started_at=t0 - timedelta(hours=1),
    )
    cur = _save_run(
        tmp_store, signals_scores=[("a", 5.0), ("fresh", 4.0)], started_at=t0
    )
    build_diff(cur, store=tmp_store)

    build_synopsis(cur, store=tmp_store)
    doc = json.loads(tmp_store.reports[f"{cur.run_id}/synopsis.json"])
    assert "regression" in doc
    reg = doc["regression"]
    assert reg["counts"]["new"] == 1 and reg["counts"]["resolved"] == 1
    assert {r["signal"] for r in reg["regressions"]} == {"a", "fresh"}
    assert {r["signal"] for r in reg["improvements"]} == {"gone"}
    md = tmp_store.reports[f"{cur.run_id}/SYNOPSIS.md"]
    assert "Regression vs baseline" in md


def test_synopsis_doc_without_diff_has_no_regression():
    run = CaptureRun(target_url="u", mode="review", findings=[_finding("a")])
    assert "regression" not in build_synopsis_doc(run)


def test_ov_diff_facade(tmp_store):
    t0 = utcnow()
    _save_run(
        tmp_store, signals_scores=[("a", 2.0)], started_at=t0 - timedelta(hours=1)
    )
    cur = _save_run(tmp_store, signals_scores=[("a", 5.0)], started_at=t0)
    diff = ov.diff(cur, store=tmp_store)
    assert isinstance(diff, ov.RunDiff)
    assert diff.counts["changed"] == 1


# --------------------------------------------------------------------------- #
# Locator-less, multi-instance signals (the deps.known-vulnerability shape)
# --------------------------------------------------------------------------- #


def _vuln(component, *, score=4.0):
    """A finding shaped like ov.analysis.arch.dependencies emits (no locator)."""
    return Finding(
        type="risk",
        signal="deps.known-vulnerability",
        category="robustness",
        title=f"Vulnerable {component}",
        observed=f"{component} is vulnerable",
        metric_detail={"component": component},
        severity=Severity(impact_tier="serious", score=score),
    )


def test_finding_key_disambiguates_locatorless_multi_instance():
    assert finding_key(_vuln("lodash")) != finding_key(_vuln("jquery"))
    # console-error shape: distinguished only by the message in `observed`
    a = Finding(
        type="ux_issue",
        signal="heuristic.console-error",
        category="robustness",
        heuristic="nielsen-5",
        observed="TypeError: a",
        location={"step_id": "s1", "intent": "enumerate"},
    )
    b = Finding(
        type="ux_issue",
        signal="heuristic.console-error",
        category="robustness",
        heuristic="nielsen-5",
        observed="TypeError: b",
        location={"step_id": "s2", "intent": "enumerate"},
    )
    assert finding_key(a) != finding_key(b)  # would have collided on intent alone


def test_diff_runs_locatorless_vulns_not_masked():
    # Regression the fix targets: baseline {lodash, jquery}, current {lodash, axios}.
    baseline = CaptureRun(target_url="u", findings=[_vuln("lodash"), _vuln("jquery")])
    current = CaptureRun(target_url="u", findings=[_vuln("lodash"), _vuln("axios")])
    diff = diff_runs(current, baseline)
    assert diff.counts == {"new": 1, "changed": 0, "resolved": 1, "unchanged": 1}
    by_title = {d.title: d.status for d in diff.finding_deltas}
    assert by_title["Vulnerable lodash"] == "unchanged"
    assert by_title["Vulnerable axios"] == "new"
    assert by_title["Vulnerable jquery"] == "resolved"


def test_diff_runs_notes_true_key_collision():
    # Two findings that genuinely share a key (no locator, no metric_detail, same title).
    def dup():
        return Finding(type="ux_issue", signal="x.dup", category="ux", title="dup")

    current = CaptureRun(target_url="u", findings=[dup(), dup()])
    diff = diff_runs(current, CaptureRun(target_url="u", findings=[]))
    assert any("sharing a diff key" in n and "x.dup" in n for n in diff.notes)


# --------------------------------------------------------------------------- #
# changed-but-neutral (confidence / observed-only change)
# --------------------------------------------------------------------------- #


def test_diff_runs_confidence_only_change_is_changed_but_neutral():
    base_f = _finding("a", score=3.0, selector="#a")
    cur_f = _finding("a", score=3.0, selector="#a")
    cur_f.confidence = 0.5  # same severity, different confidence
    diff = diff_runs(
        CaptureRun(target_url="u", findings=[cur_f]),
        CaptureRun(target_url="u", findings=[base_f]),
    )
    delta = diff.finding_deltas[0]
    assert delta.status == "changed" and delta.direction == "neutral"
    assert "confidence" in (delta.detail or "")
    assert delta not in diff.regressions and delta not in diff.improvements


def test_diff_runs_observed_only_change_detail():
    base_f = _finding("a", score=3.0, selector="#a", observed="2 errors")
    cur_f = _finding("a", score=3.0, selector="#a", observed="5 errors")
    diff = diff_runs(
        CaptureRun(target_url="u", findings=[cur_f]),
        CaptureRun(target_url="u", findings=[base_f]),
    )
    delta = diff.finding_deltas[0]
    assert delta.status == "changed"
    assert "observed signal changed" in (delta.detail or "")


# --------------------------------------------------------------------------- #
# build_diff input polymorphism (run-id string + CaptureRun-object baseline)
# --------------------------------------------------------------------------- #


def test_build_diff_accepts_run_id_string_and_object_baseline(tmp_store):
    t0 = utcnow()
    base = _save_run(
        tmp_store, signals_scores=[("a", 2.0)], started_at=t0 - timedelta(hours=1)
    )
    cur = _save_run(tmp_store, signals_scores=[("a", 5.0)], started_at=t0)
    # current passed as a run-id STRING; baseline passed as a CaptureRun OBJECT
    diff = build_diff(cur.run_id, baseline=base, store=tmp_store)
    assert diff is not None and diff.baseline_run_id == base.run_id
    assert diff.counts["changed"] == 1


# --------------------------------------------------------------------------- #
# Stack / API drift rendering (report section + synopsis Markdown)
# --------------------------------------------------------------------------- #


def _save_run_with_stack(
    tmp_store, *, tech, endpoints, rendering, source_maps, started_at, target="http://t"
):
    run = CaptureRun(
        target_url=target,
        mode="review",
        rendering_model=rendering,
        source_maps_present=source_maps,
        fingerprint=[TechFinding(name=n, confidence=80) for n in tech],
        api_surface=[
            Endpoint(method=m, path_template=p, kind="rest") for m, p in endpoints
        ],
        findings=[_finding("a", score=2.0, selector="#a")],
    )
    run.started_at = started_at
    tmp_store.save_run(run)
    return run


def test_stack_drift_renders_in_section_and_synopsis(tmp_store):
    t0 = utcnow()
    _save_run_with_stack(
        tmp_store,
        tech=["React", "jQuery"],
        endpoints=[("GET", "/a")],
        rendering="csr",
        source_maps=False,
        started_at=t0 - timedelta(hours=1),
    )
    cur = _save_run_with_stack(
        tmp_store,
        tech=["React", "Vite"],
        endpoints=[("GET", "/a"), ("POST", "/b")],
        rendering="ssr",
        source_maps=True,
        started_at=t0,
    )
    build_diff(cur, store=tmp_store)
    render_reports(cur, store=tmp_store)
    build_synopsis(cur, store=tmp_store)

    section = tmp_store.reports[f"{cur.run_id}/40_review_audit.md"]
    syn = tmp_store.reports[f"{cur.run_id}/SYNOPSIS.md"]
    for md in (section, syn):
        assert "Stack / API drift" in md
        assert "Vite" in md and "jQuery" in md
        assert "POST /b" in md
        assert "csr" in md and "ssr" in md  # rendering model change
        assert "source maps" in md


# --------------------------------------------------------------------------- #
# CLI surface + run_overview review-mode wiring
# --------------------------------------------------------------------------- #


def test_cli_diff_happy_no_baseline_and_error(tmp_store):
    from ov.__main__ import diff as cli_diff

    t0 = utcnow()
    _save_run(
        tmp_store, signals_scores=[("a", 2.0)], started_at=t0 - timedelta(hours=1)
    )
    cur = _save_run(tmp_store, signals_scores=[("a", 5.0)], started_at=t0)

    out = "\n".join(cli_diff(cur.run_id, store=tmp_store))
    assert "baseline:" in out and "1 changed" in out

    lonely = _save_run(tmp_store, signals_scores=[("z", 1.0)], target="http://solo")
    assert "no prior baseline" in "\n".join(cli_diff(lonely.run_id, store=tmp_store))

    err = "\n".join(cli_diff("run_does_not_exist", store=tmp_store))
    assert "error: could not load run" in err and "ov runs" in err


def test_run_overview_review_mode_runs_diff(tmp_store, monkeypatch):
    import ov as _ov
    from ov.analysis.diff import load_diff
    from ov.reporting.overview import run_overview

    t0 = utcnow()
    _save_run(
        tmp_store, signals_scores=[("a", 2.0)], started_at=t0 - timedelta(hours=1)
    )
    captured: dict = {}

    def fake_observe(url, *, store=None, mode="reconstruct", **kw):
        run = CaptureRun(target_url=url, mode=mode)
        store.save_run(run)
        captured["run"] = run
        return run

    monkeypatch.setattr(_ov, "observe", fake_observe)
    run_overview("http://t", mode="review", store=tmp_store)
    cur_id = captured["run"].run_id
    diff = load_diff(tmp_store, cur_id)
    assert diff is not None  # the review branch inserted the diff step
    assert diff["counts"]["resolved"] >= 1  # baseline 'a' has no current twin


def test_run_overview_reconstruct_skips_diff(tmp_store, monkeypatch):
    import ov as _ov
    from ov.analysis.diff import load_diff
    from ov.reporting.overview import run_overview

    t0 = utcnow()
    _save_run(
        tmp_store,
        signals_scores=[("a", 2.0)],
        started_at=t0 - timedelta(hours=1),
        mode="reconstruct",
        target="http://r",
    )
    captured: dict = {}

    def fake_observe(url, *, store=None, mode="reconstruct", **kw):
        run = CaptureRun(target_url=url, mode=mode)
        store.save_run(run)
        captured["run"] = run
        return run

    monkeypatch.setattr(_ov, "observe", fake_observe)
    run_overview("http://r", mode="reconstruct", store=tmp_store)
    assert (
        load_diff(tmp_store, captured["run"].run_id) is None
    )  # no diff in reconstruct


def test_tech_diff_excludes_recovered_dependency_sbom():
    baseline = CaptureRun(
        target_url="u",
        fingerprint=[TechFinding(name="React", categories=["ui-framework"])],
    )
    current = CaptureRun(
        target_url="u",
        fingerprint=[
            TechFinding(name="React", categories=["ui-framework"]),
            TechFinding(name="lodash", categories=["dependency"], provenance=["sourcemap"]),
            TechFinding(name="axios", categories=["dependency"], provenance=["sourcemap"]),
        ],
    )
    # Recovered-dep SBOM churn must NOT flood review-mode stack drift.
    assert diff_runs(current, baseline).tech_added == []
