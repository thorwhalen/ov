"""Tests for the Phase-4 in-package agent layer (``ov.agents``).

Two tiers, mirroring the repo's browser-gated philosophy:

* the **in-package runtimes** (operator loop, analyst cite-or-abstain gate, the LLM
  facade, the SSOT/resolver) are tested with *injected* deciders / judges / stages,
  so they run with **no optional dependency, no browser, no API call**;
* the **coact / aw / py2mcp** integration (the mechanical lift, the orchestrator
  engine, the MCP server) gates on the ``ov[agents]`` extra via ``importorskip`` —
  exactly as the capture tests gate on a launchable Chromium.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ov.base import (
    Action,
    ActionResult,
    Affordance,
    CaptureRun,
    Finding,
    Observation,
    Severity,
    TechFinding,
)

SKILLS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "skills"


def _obs(url: str, *refs: str) -> Observation:
    return Observation(
        strategy="ax_snapshot",
        url=url,
        obs_hash=url,
        affordances=[Affordance(ref=r, role="button", name=r) for r in refs],
    )


# --------------------------------------------------------------------------- #
# SSOT, resolver, LLM facade — no optional dependency
# --------------------------------------------------------------------------- #


def test_definitions_ssot():
    from ov.agents.definitions import OV_AGENTS, analyst_specs

    assert set(OV_AGENTS) == {"operator", "ux-analyst", "arch-analyst", "orchestrator"}
    assert [s.lens for s in analyst_specs()] == ["ux", "arch"]
    assert OV_AGENTS["operator"].default_model == "haiku"


def test_skills_resolver_finds_repo_skills():
    from ov.agents._skills import default_skills_dir, skill_path

    assert default_skills_dir().is_dir()
    assert skill_path("ov-analyze-ux").name == "ov-analyze-ux"
    with pytest.raises(FileNotFoundError):
        skill_path("does-not-exist")


def test_llm_facade_routing_and_injection():
    from ov.agents.llm import default_model, resolve_llm, structured

    assert default_model("operator") == "haiku"
    assert default_model("arch") == "opus"
    assert default_model("???") == "sonnet"  # fallback
    assert resolve_llm(lambda p: "hi")("x") == "hi"

    class Client:  # a rich (multimodal-capable) injected client
        def structured(self, prompt, schema, images=None):
            return {"saw_images": bool(images), "title": schema.get("title")}

    out = structured("p", {"title": "T"}, llm=Client(), images=[b"img"])
    assert out == {"saw_images": True, "title": "T"}


# --------------------------------------------------------------------------- #
# Operator — perceive→decide→act→record loop (injected decider + hands)
# --------------------------------------------------------------------------- #


def test_operator_drives_then_stops():
    from ov.agents.operator import OperatorAgent

    calls = {"n": 0}

    def decider(obs, *, goal, history):
        calls["n"] += 1
        return Action(type="click", ref="e1", description="go") if calls["n"] == 1 else None

    def fake_act(page, action):
        return ActionResult(action=action, ok=True, observation=_obs("/next", "e2"))

    run = CaptureRun(target_url="/start")
    op = OperatorAgent(
        decider=decider,
        observe_fn=lambda p: _obs("/start", "e1"),
        act_fn=fake_act,
        max_steps=5,
    )
    artifact, info = op.execute("sign up", {"page": None, "run": run})

    assert info["steps_taken"] == 1
    assert info["stopped_reason"] == "decider-stop"
    assert len(artifact.steps) == 1
    assert info["run_id"] == run.run_id


def test_operator_detects_no_progress_loop():
    from ov.agents.operator import OperatorAgent

    def loopy(obs, *, goal, history):
        return Action(type="click", ref="e1", description="x")

    def static_act(page, action):
        return ActionResult(action=action, ok=True, observation=_obs("/same", "e1"))

    op = OperatorAgent(
        decider=loopy,
        observe_fn=lambda p: _obs("/same", "e1"),
        act_fn=static_act,
        max_steps=10,
        no_progress_steps=2,
    )
    _, info = op.execute("loop", {"page": None, "run": CaptureRun()})
    assert info["loop_suspected"] is True
    assert info["stopped_reason"] == "loop-suspected"


def test_operator_caps_at_max_steps():
    from ov.agents.operator import OperatorAgent

    seq = iter(range(100))

    def always(obs, *, goal, history):
        return Action(type="click", ref=f"e{next(seq)}", description="x")

    def changing_act(page, action):
        return ActionResult(action=action, ok=True, observation=_obs(f"/{action.ref}", action.ref))

    op = OperatorAgent(
        decider=always,
        observe_fn=lambda p: _obs("/0", "e0"),
        act_fn=changing_act,
        max_steps=3,
    )
    _, info = op.execute("g", {"page": None, "run": CaptureRun()})
    assert info["steps_taken"] == 3
    assert info["stopped_reason"] == "max-steps"


def test_make_llm_decider_with_injected_client():
    from ov.agents.operator import make_llm_decider

    class LLM:
        def __init__(self, reply):
            self.reply = reply

        def structured(self, prompt, schema, images=None):
            return self.reply

    act = make_llm_decider(LLM({"type": "click", "ref": "e3", "description": "go"}))
    chosen = act(_obs("/p", "e3"), goal="g", history=[])
    assert isinstance(chosen, Action) and chosen.ref == "e3"

    stop = make_llm_decider(LLM({"type": "stop"}))
    assert stop(_obs("/p"), goal="g", history=[]) is None


# --------------------------------------------------------------------------- #
# Analyst — evidence bundle → judge → cite-or-abstain gate (injected judge)
# --------------------------------------------------------------------------- #


def test_analyst_cite_or_abstain_gate():
    from ov.agents.analyst import ux_analyst

    det = Finding(
        type="ux_issue",
        signal="contrast.text",
        category="a11y",
        observed="2.1:1",
        source_layer="deterministic",
        severity=Severity(impact_tier="serious", score=3.0),
    )
    run = CaptureRun(target_url="/x", findings=[det])
    grounded_ref = f"find:{det.finding_id}"

    def judge(bundle, *, run, store):
        return [
            {"type": "ux_issue", "signal": "contrast.text", "title": "low contrast",
             "evidence_refs": [grounded_ref], "judgment": "hard to read"},
            {"type": "ux_issue", "signal": "made.up", "title": "hallucinated",
             "evidence_refs": [], "judgment": "no evidence"},
        ]

    findings, info = ux_analyst(judge=judge).execute(run, {"store": None})
    assert info["candidates"] == 2
    assert info["kept"] == 1 and info["downgraded"] == 1
    downgraded = [f for f in findings if f.type == "undetermined"]
    assert downgraded and downgraded[0].needs_human_review
    assert all(f.source_layer == "llm" for f in findings)
    # additive: the run now carries the deterministic + the two llm findings
    assert len(run.findings) == 3


def test_analyst_model_routing_and_lens_validation():
    from ov.agents.analyst import AnalystAgent, arch_analyst, ux_analyst

    assert ux_analyst().model == "sonnet" and ux_analyst().name == "ux-analyst"
    assert arch_analyst().model == "opus"
    with pytest.raises(ValueError):
        AnalystAgent(lens="bogus")


def test_analyst_returns_empty_without_llm():
    # No judge and no resolvable LLM → no llm findings, deterministic floor preserved.
    from ov.agents.analyst import ux_analyst

    run = CaptureRun(target_url="/x")
    findings, info = ux_analyst(judge=lambda b, **k: []).execute(run, {"store": None})
    assert findings == [] and info["kept"] == 0


# --------------------------------------------------------------------------- #
# The mechanical lift (coact) — gated on the ov[agents] extra
# --------------------------------------------------------------------------- #


def test_coact_blocks_complete_with_pydantic_return_contract():
    pytest.importorskip("coact")
    from ov.agents.realize import complete_all

    ads = complete_all()
    assert set(ads) == {"operator", "ux-analyst", "arch-analyst", "orchestrator"}
    assert ads["ux-analyst"].model == "sonnet"
    assert ads["arch-analyst"].model == "opus"
    # the UX analyst's return contract resolves to the real Finding schema
    schema = ads["ux-analyst"].returns.schema()
    assert schema.get("title") == "Finding" and "evidence_refs" in schema.get("properties", {})


def test_materialize_writes_agents_and_links_skills(tmp_path):
    pytest.importorskip("coact")
    from ov.agents.realize import materialize

    result = materialize(dest=str(tmp_path), skills_dir=str(SKILLS_DIR))
    assert result.warnings == []
    assert {p.name for p in tmp_path.glob("*.md")} == {
        "ov-operate.md", "ov-analyze-ux.md", "ov-analyze-arch.md", "study-web-app.md"
    }
    # point-don't-copy: the agent references the skill by name, never inlines it
    text = (tmp_path / "ov-analyze-ux.md").read_text()
    assert "ov-analyze-ux" in text


def test_estimate_surfaces_cost_gate():
    pytest.importorskip("coact")
    from ov.agents.realize import estimate

    est = estimate(["ux-analyst", "arch-analyst"])
    rendered = est.render()
    assert "interdependent" in rendered.lower()


# --------------------------------------------------------------------------- #
# Orchestrator — pure coordinator (gated on aw)
# --------------------------------------------------------------------------- #


def _fake_stage_kwargs():
    def fake_capture(url, **kw):
        return CaptureRun(target_url=url, findings=[
            Finding(type="ux_issue", signal="s", category="a11y",
                    observed="x", source_layer="deterministic")])

    return dict(
        capture_fn=fake_capture,
        analyze_fn=lambda run, *, lenses: {"ux": {}},
        report_fn=lambda run, *, out_dir: ["00_overview.md"],
        synopsis_fn=lambda source, *, out: {"synopsis_path": "syn.json"},
    )


def test_orchestrator_deterministic_pipeline_skips_analysts():
    pytest.importorskip("aw")
    from ov.agents.orchestrator import Orchestrator

    res = Orchestrator(llm=None, **_fake_stage_kwargs()).run("/start")
    names = [s["name"] for s in res.workflow["steps"]]
    assert names == ["capture", "analyze", "report", "synopsis"]
    assert res.synopsis["synopsis_path"] == "syn.json"


def test_orchestrator_inserts_analysts_when_llm_injected():
    pytest.importorskip("aw")
    from ov.agents.orchestrator import Orchestrator

    class LLM:
        def structured(self, prompt, schema, images=None):
            return {"findings": [{"type": "ux_issue", "signal": "x", "title": "t",
                                  "evidence_refs": ["find:abc"], "judgment": "R1"}]}

    res = Orchestrator(llm=LLM(), **_fake_stage_kwargs()).run("/start")
    names = [s["name"] for s in res.workflow["steps"]]
    assert names == ["capture", "analyze", "ux-analyst", "arch-analyst", "report", "synopsis"]
    # 1 deterministic + 1 ux-llm + 1 arch-llm finding
    assert len(res.run.findings) == 3


# --------------------------------------------------------------------------- #
# Foreign-host MCP server (gated on py2mcp / fastmcp)
# --------------------------------------------------------------------------- #


def test_mcp_server_builds_and_exposes_tools():
    pytest.importorskip("py2mcp")
    pytest.importorskip("fastmcp")
    from ov.agents.mcp import mcp_server, ov_tools

    assert [f.__name__ for f in ov_tools()] == ["study_url", "capture_url"]
    server = mcp_server()
    assert server.__class__.__name__ == "FastMCP"


def test_mcp_run_summary_is_json_shaped():
    from ov.agents.mcp import _run_summary

    run = CaptureRun(
        target_url="/x",
        rendering_model="csr",
        fingerprint=[TechFinding(name="React", version="18", confidence=90)],
    )
    summary = _run_summary(run)
    assert summary["target_url"] == "/x"
    assert summary["technologies"][0]["name"] == "React"


def test_coact_mcp_backend_reads_skill_block():
    pytest.importorskip("coact")
    pytest.importorskip("py2mcp")
    import coact

    server = coact.realize(str(SKILLS_DIR / "study-web-app"), backend="mcp")
    assert server.__class__.__name__ == "FastMCP"


# --------------------------------------------------------------------------- #
# Regression + edge-case coverage (review pass)
# --------------------------------------------------------------------------- #


def test_require_raises_friendly_error_for_missing_extra():
    from ov.agents._util import require

    with pytest.raises(ImportError, match="not installed"):
        require("a_module_that_does_not_exist", feature="X")


def test_default_skills_dir_respects_env_changes(monkeypatch, tmp_path):
    # The resolver must read OV_SKILLS_DIR at call time (no stale cache).
    from ov.agents import _skills

    (tmp_path / "ov-operate").mkdir()
    (tmp_path / "ov-operate" / "SKILL.md").write_text("---\nname: ov-operate\n---\n")
    monkeypatch.setenv("OV_SKILLS_DIR", str(tmp_path))
    assert _skills.default_skills_dir() == tmp_path
    monkeypatch.delenv("OV_SKILLS_DIR")
    assert _skills.default_skills_dir() != tmp_path  # falls back, not the cached env path


def test_skills_resolver_finds_packaged_location(monkeypatch, tmp_path):
    # Simulate an installed wheel: repo .claude/skills absent, ov/data/skills present.
    from ov.agents import _skills

    packaged = tmp_path / "data" / "skills" / "ov-analyze-ux"
    packaged.mkdir(parents=True)
    (packaged / "SKILL.md").write_text("---\nname: ov-analyze-ux\n---\n")
    monkeypatch.delenv("OV_SKILLS_DIR", raising=False)
    # point the "packaged" probe at our fake data dir, and make the repo probe miss
    monkeypatch.setattr(_skills, "__file__", str(tmp_path / "agents" / "_skills.py"))
    real_has = _skills._has_skills
    monkeypatch.setattr(
        _skills, "_has_skills",
        lambda d: real_has(d) if "data/skills" in str(d) else False,
    )
    assert _skills.default_skills_dir() == tmp_path / "data" / "skills"


def test_resolvable_accepts_set_of_mark_id():
    # Regression: a ref that is a bare mark id (key like "R1") must resolve — the
    # cite-or-abstain prompt tells the model to cite mark ids.
    from ov.analysis.reliability import resolvable
    from ov.base import EvidenceBundle

    bundle = EvidenceBundle(marks={"R1": "mark:step#R1"})
    run = CaptureRun()
    assert resolvable("R1", run, bundle) is True           # mark id (key)
    assert resolvable("mark:step#R1", run, bundle) is True  # evidence id (value)
    assert resolvable("R9", run, bundle) is False           # unknown mark


def test_analyst_keeps_finding_citing_bare_mark_id():
    # End-to-end: a judge that cites a bundle mark id (key, e.g. "R1") is KEPT, not
    # downgraded — exercises the resolvable() fix through the analyst's gate.
    from ov.agents.analyst import ux_analyst
    from ov.base import Evidence, EvidenceBundle

    bundle = EvidenceBundle(
        marks={"R1": "mark:s#R1"},
        facts=[Evidence(evidence_id="mark:s#R1", kind="mark", summary="button 'Go'")],
        task="assess",
    )
    run = CaptureRun(target_url="/x")

    def judge(b, *, run, store):
        return [{"type": "ux_issue", "signal": "ux.x", "title": "t",
                 "evidence_refs": ["R1"], "judgment": "region R1 is unreadable"}]

    findings, info = ux_analyst(judge=judge).execute(bundle, {"run": run})
    assert info["kept"] == 1 and info["downgraded"] == 0


def test_coerce_findings_overrides_falsy_required_fields():
    from ov.agents.analyst import ux_analyst

    out = ux_analyst()._coerce_findings([
        {"type": "ux_issue", "signal": None, "title": "explicit-null-signal"},
        {"type": None, "signal": "ux.s", "title": "explicit-null-type"},
        {"title": "missing-required"},
        "not-a-dict",
        12345,
    ])
    # the 3 mappings coerce into valid Findings (falsy fields filled); 2 non-dicts dropped
    assert len(out) == 3
    assert all(f.signal and f.type and f.category for f in out)
    assert all(f.source_layer == "llm" for f in out)


def test_analyst_image_fetch_failure_is_non_fatal():
    from ov.agents.analyst import ux_analyst
    from ov.base import Artifact, EvidenceBundle

    art = Artifact(kind="screenshot")
    run = CaptureRun(artifacts=[art])
    bundle = EvidenceBundle(marked_image_artifact_ids=[art.artifact_id])

    class FailingStore:
        def artifact_bytes(self, artifact):
            raise OSError("boom")

    assert ux_analyst()._bundle_images(bundle, run, FailingStore()) == []


def test_make_llm_decider_parse_failures_stop():
    from ov.agents.operator import make_llm_decider

    class LLM:
        def __init__(self, reply):
            self.reply = reply

        def structured(self, prompt, schema, images=None):
            return self.reply

    for reply in ("just a string", {"ref": "e3"}, {"type": "invalid_action", "ref": "e3"},
                  {"type": "click", "ref": "e1", "args": {"stop": True}}):
        decide = make_llm_decider(LLM(reply))
        assert decide(_obs("/p", "e1"), goal="g", history=[]) is None


def test_operator_falls_back_to_observe_when_result_has_no_observation():
    from ov.agents.operator import OperatorAgent

    def decider(obs, *, goal, history):
        return Action(type="click", ref="e1", description="go") if not history else None

    observes = {"n": 0}

    def observe_fn(page):
        observes["n"] += 1
        return _obs("/fallback", "e1")

    def act_no_obs(page, action):
        return ActionResult(action=action, ok=True, observation=None)

    op = OperatorAgent(decider=decider, observe_fn=observe_fn, act_fn=act_no_obs, max_steps=3)
    _, info = op.execute("g", {"page": None, "run": CaptureRun()})
    assert info["steps_taken"] == 1
    assert observes["n"] >= 2  # initial observe + the post-act fallback observe


def test_llm_structured_falls_back_for_legacy_client_without_images():
    from ov.agents.llm import structured

    class LegacyClient:  # .structured() does NOT accept images=
        def structured(self, prompt, schema):
            return {"ok": True}

    assert structured("p", {"type": "object"}, llm=LegacyClient(), images=[b"x"]) == {"ok": True}


def test_orchestrator_extracts_run_and_reports_from_context():
    pytest.importorskip("aw")
    from ov.agents.orchestrator import Orchestrator

    res = Orchestrator(llm=None, **_fake_stage_kwargs()).run("/start")
    assert res.run is not None and res.run.target_url == "/start"
    assert res.reports == ["00_overview.md"]
    assert res.workflow["success"] is True
