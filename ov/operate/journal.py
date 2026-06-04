"""``journal(run, step)`` -- append the structured per-step record (§2.3).

The journey trace *is* the UX evidence: each step records the stated intent, the
action, the affordances that were available, pre/post observation hashes, and
network/console deltas. :func:`make_step` builds the record from an action's
before/after observations; :func:`journal` appends it to the run.
"""

from __future__ import annotations

from ..base import Action, ActionResult, CaptureRun, JourneyStep, Observation


def make_step(
    *,
    intent: str,
    action: Action | None = None,
    pre_observation: Observation | None = None,
    result: ActionResult | None = None,
    artifact_ids: list[str] | None = None,
    network_delta: int = 0,
    console_delta: int = 0,
    note: str | None = None,
) -> JourneyStep:
    """Build a :class:`JourneyStep` from an action's before/after observations.

    ``outcome`` is derived: ``error`` on a failed action, ``noop`` when the
    post-observation hash equals the pre-observation hash (nothing changed),
    else ``ok``.
    """
    post = result.observation if result else None
    pre_hash = pre_observation.obs_hash if pre_observation else None
    post_hash = post.obs_hash if post else None

    if result is not None and not result.ok:
        outcome = "error"
    elif pre_hash is not None and post_hash is not None and pre_hash == post_hash:
        outcome = "noop"
    else:
        outcome = "ok"

    return JourneyStep(
        intent=intent,
        action=action,
        affordances_seen=pre_observation.affordances if pre_observation else [],
        outcome=outcome,
        artifact_ids=artifact_ids or [],
        pre_obs_hash=pre_hash,
        post_obs_hash=post_hash,
        network_delta=network_delta,
        console_delta=console_delta,
        note=note,
        t_ms=result.t_ms if result else 0.0,
    )


def journal(run: CaptureRun, step: JourneyStep) -> JourneyStep:
    """Append ``step`` to ``run.steps`` and return it."""
    run.steps.append(step)
    return step
