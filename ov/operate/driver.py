"""The scripted/guided driver -- model-free journey execution (Phase 1).

Two deterministic strategies that compose the operate primitives over a
:class:`~ov.capture.session.CaptureSession`:

* :func:`replay` -- execute a scripted list of actions (guided-replay), capturing
  state and journaling each step.
* :func:`crawl` -- a polite, same-origin breadth-first crawl (crawl-and-map),
  capturing each visited page and stopping on ``max_pages`` / no-progress.

These let the capture spine produce a real multi-state journey with **no model**.
Goal-pursuit (``advance`` toward a success predicate) is the host's job via the
``ov-operate`` skill; the package supplies the hands, not the policy.
"""

from __future__ import annotations

import time
from typing import Any

from ..base import Action, JourneyStep
from .act import act
from .journal import make_step
from .observe import observe
from .progress import progress
from .strategies import INTENT_ENUMERATE, INTENT_REPLAY, absolutize, is_same_origin

_LINKS_JS = r"""
() => Array.from(document.querySelectorAll('a[href]'))
        .map(a => a.getAttribute('href')).filter(Boolean)
"""


def _coerce_action(item: Action | dict[str, Any]) -> Action:
    return item if isinstance(item, Action) else Action(**item)


def replay(session: Any, actions: list[Action | dict[str, Any]]) -> list[JourneyStep]:
    """Execute a scripted action list, capturing + journaling each step.

    >>> # actions are Action models or dicts: {"type": "click", "ref": "e3"}
    >>> callable(replay)
    True
    """
    steps: list[JourneyStep] = []
    for item in actions:
        action = _coerce_action(item)
        pre = observe(session.page)
        result = act(
            session.page,
            action,
            polite_rate_s=session.config.polite_rate_s,
        )
        step = make_step(intent=INTENT_REPLAY, action=action, pre_observation=pre, result=result)
        session.capture_step(step)
        session.run.steps.append(step)
        steps.append(step)
        if len(session.run.steps) >= session.config.max_steps:
            session.run.notes.append("replay stopped: max_steps reached")
            break
    return steps


def crawl(session: Any, *, max_pages: int = 5) -> list[JourneyStep]:
    """Politely crawl same-origin links breadth-first, capturing each page.

    Stops at ``max_pages``, on ``max_steps``, or when the deterministic progress
    signal reports a loop. The host can run a richer crawl; this is the model-free
    baseline that yields a multi-state capture.
    """
    base_url = session.run.target_url
    visited: set[str] = set()
    queue: list[str] = []
    steps: list[JourneyStep] = []

    # seed from the already-open page
    start_url = session.page.url
    visited.add(start_url)
    queue.extend(_discover_links(session, base_url, visited))

    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        action = Action(type="navigate", url=url, description=f"crawl to {url}")
        pre = observe(session.page)
        result = act(session.page, action, polite_rate_s=session.config.polite_rate_s)
        step = make_step(intent=INTENT_ENUMERATE, action=action, pre_observation=pre, result=result)
        session.capture_step(step)
        session.run.steps.append(step)
        steps.append(step)

        sig = progress(session.run.steps, no_progress_steps=session.config.no_progress_steps)
        if sig.loop_suspected or len(session.run.steps) >= session.config.max_steps:
            session.run.notes.append(
                f"crawl stopped: {'loop_suspected' if sig.loop_suspected else 'max_steps'}"
            )
            break
        queue.extend(_discover_links(session, base_url, visited | set(queue)))
    return steps


def _discover_links(session: Any, base_url: str, seen: set[str]) -> list[str]:
    """Return new, same-origin, absolute links found on the current page."""
    try:
        hrefs = session.page.evaluate(_LINKS_JS)
    except Exception:  # noqa: BLE001
        return []
    found: list[str] = []
    for href in hrefs:
        url = absolutize(href, session.page.url)
        if url not in seen and is_same_origin(url, base_url) and url not in found:
            found.append(url)
    return found
