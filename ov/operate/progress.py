"""``progress(history) -> ProgressSignal`` -- deterministic no-progress *facts*.

This computes facts only; it never decides to stop. The host (policy layer)
interprets the signal against its budgets and aborts on ``loop_suspected`` (§2.3:
"the package detects and reports no-progress; the host decides to abort").

Signals (all model-free):

* ``repeated_action`` -- the last step's ``(action.type, args_hash)`` recurred.
* ``no_new_signal_steps`` -- trailing run of steps with an unchanged post-obs hash.
* ``url_stasis`` / ``ax_stasis`` -- URL / AX state unchanged across the recent window.
* ``repeated_error`` -- the last two steps failed identically.
* ``loop_suspected`` -- rolled-up advisory when any threshold is crossed.
"""

from __future__ import annotations

from ..base import JourneyStep, ProgressSignal
from ..util import stable_hash


def _args_hash(step: JourneyStep) -> str:
    if step.action is None:
        return "noop"
    a = step.action
    return stable_hash([a.type, a.ref, a.url, a.text, a.key, a.value, a.args])


def progress(history: list[JourneyStep], *, no_progress_steps: int = 3) -> ProgressSignal:
    """Compute loop/no-progress facts from the journey ``history`` so far.

    >>> from ov.base import JourneyStep, Action
    >>> s = JourneyStep(action=Action(type='click', ref='e1'), post_obs_hash='h')
    >>> sig = progress([s, s.model_copy(), s.model_copy()], no_progress_steps=3)
    >>> sig.no_new_signal_steps >= 3 and sig.loop_suspected
    True
    """
    if not history:
        return ProgressSignal()

    last = history[-1]

    # repeated_action: same (type, args) seen earlier in history
    last_h = _args_hash(last)
    repeated_action = any(_args_hash(s) == last_h for s in history[:-1])

    # trailing run of unchanged post-observation hash
    no_new = 0
    ref_hash = last.post_obs_hash
    if ref_hash is not None:
        for s in reversed(history):
            if s.post_obs_hash == ref_hash:
                no_new += 1
            else:
                break

    # URL / AX stasis over the recent window
    window = history[-no_progress_steps:]
    urls = {
        (s.action.url if s.action and s.action.type == "navigate" else None) for s in window
    }
    url_stasis = len(window) >= no_progress_steps and len(urls) <= 1
    ax_hashes = {s.post_obs_hash for s in window if s.post_obs_hash is not None}
    ax_stasis = len(window) >= no_progress_steps and len(ax_hashes) <= 1

    repeated_error = (
        len(history) >= 2
        and history[-1].outcome == "error"
        and history[-2].outcome == "error"
    )

    loop_suspected = no_new >= no_progress_steps or (repeated_action and ax_stasis) or repeated_error

    return ProgressSignal(
        repeated_action=repeated_action,
        no_new_signal_steps=no_new,
        url_stasis=url_stasis,
        ax_stasis=ax_stasis,
        repeated_error=repeated_error,
        loop_suspected=loop_suspected,
        detail={"history_len": len(history), "last_outcome": last.outcome},
    )
