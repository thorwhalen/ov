"""Tests for the model-free operate primitives (progress/journal/strategies)."""

from ov.base import Action, ActionResult, JourneyStep, Observation
from ov.operate.journal import make_step
from ov.operate.progress import progress
from ov.operate.strategies import absolutize, is_same_origin, navigable_affordances


def _step(post_hash, outcome="ok", action=None):
    return JourneyStep(action=action, post_obs_hash=post_hash, outcome=outcome)


def test_progress_empty_history():
    sig = progress([])
    assert sig.loop_suspected is False and sig.no_new_signal_steps == 0


def test_progress_detects_flat_states():
    history = [_step("h"), _step("h"), _step("h")]
    sig = progress(history, no_progress_steps=3)
    assert sig.no_new_signal_steps == 3
    assert sig.ax_stasis is True
    assert sig.loop_suspected is True


def test_progress_repeated_error():
    history = [_step("a", "error"), _step("b", "error")]
    sig = progress(history)
    assert sig.repeated_error is True and sig.loop_suspected is True


def test_progress_repeated_action():
    a = Action(type="click", ref="e1")
    history = [_step("a", action=a), _step("b", action=a.model_copy())]
    sig = progress(history)
    assert sig.repeated_action is True


def test_make_step_outcome_derivation():
    pre = Observation(strategy="ax_snapshot", obs_hash="h1")
    # noop: post hash equals pre hash
    res_noop = ActionResult(action=Action(type="click", ref="e1"), ok=True,
                            observation=Observation(strategy="ax_snapshot", obs_hash="h1"))
    step = make_step(intent="advance", action=res_noop.action, pre_observation=pre, result=res_noop)
    assert step.outcome == "noop"
    # error: failed action
    res_err = ActionResult(action=Action(type="click", ref="e1"), ok=False, error="boom")
    step2 = make_step(intent="advance", action=res_err.action, pre_observation=pre, result=res_err)
    assert step2.outcome == "error"
    # ok: post hash differs
    res_ok = ActionResult(action=Action(type="click", ref="e1"), ok=True,
                          observation=Observation(strategy="ax_snapshot", obs_hash="h2"))
    step3 = make_step(intent="advance", action=res_ok.action, pre_observation=pre, result=res_ok)
    assert step3.outcome == "ok"


def test_strategies_same_origin_and_absolutize():
    assert is_same_origin("https://x.com/a", "https://x.com/b") is True
    assert is_same_origin("https://y.com/a", "https://x.com/b") is False
    assert absolutize("/foo#frag", "https://x.com/bar") == "https://x.com/foo"


def test_navigable_affordances_filters_roles():
    from ov.base import Affordance

    obs = Observation(
        strategy="ax_snapshot",
        affordances=[
            Affordance(ref="e1", role="a", name="Home"),
            Affordance(ref="e2", role="button", name="Go"),
            Affordance(ref="e3", role="link", name="Docs"),
        ],
    )
    refs = {a.ref for a in navigable_affordances(obs)}
    assert refs == {"e1", "e3"}
