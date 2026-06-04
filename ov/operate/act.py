"""``act(page, action) -> ActionResult`` -- execute one action, return a fresh read.

Every action returns success/error **plus a fresh Observation**, so the policy
layer can decide the next step without a separate observe call. Actions that
touch an element target it by the stable ``data-ov-ref`` stamped during
perception; unknown refs and Playwright errors are caught and surfaced as a
clean ``ActionResult`` error (e.g. a stale ref the host should re-observe to fix).
"""

from __future__ import annotations

import time
from typing import Any

from ..base import Action, ActionResult, Observation
from .observe import observe
from .perception import REF_ATTR


def _locator(page: Any, ref: str):
    return page.locator(f"[{REF_ATTR}='{ref}']")


def _perform(page: Any, action: Action) -> None:
    """Execute the action's side effect (raises on failure)."""
    kind = action.type
    if kind == "navigate":
        if not action.url:
            raise ValueError("navigate action requires `url`")
        page.goto(action.url)
        return
    if kind == "key":
        if not action.key:
            raise ValueError("key action requires `key`")
        page.keyboard.press(action.key)
        return
    if kind == "scroll":
        dx = float(action.args.get("dx", 0))
        dy = float(action.args.get("dy", action.args.get("delta", 600)))
        page.mouse.wheel(dx, dy)
        return
    if kind == "wait":
        page.wait_for_timeout(int(action.args.get("ms", 500)))
        return

    # element-targeted actions require a ref
    if not action.ref:
        raise ValueError(f"{kind} action requires `ref`")
    loc = _locator(page, action.ref)
    if kind == "click":
        loc.click()
    elif kind == "type":
        loc.fill(action.text or "")
    elif kind == "select":
        loc.select_option(action.value)
    else:
        raise ValueError(f"unknown action type {kind!r}")


def act(
    page: Any,
    action: Action,
    *,
    perception: str = "ax_snapshot",
    polite_rate_s: float = 0.0,
) -> ActionResult:
    """Execute ``action`` against ``page`` and return the result + a fresh Observation.

    On failure, ``ok=False`` and ``error`` carries the message; a fresh
    Observation is still attached so the host can recover (re-observe, scroll,
    disambiguate).
    """
    t0 = time.monotonic()
    ok = True
    error: str | None = None
    try:
        _perform(page, action)
        if polite_rate_s:
            time.sleep(polite_rate_s)
    except Exception as e:  # noqa: BLE001 - surfaced, not raised
        ok = False
        error = f"{type(e).__name__}: {e}".splitlines()[0][:300]

    fresh: Observation | None = None
    try:
        fresh = observe(page, perception)
    except Exception:  # noqa: BLE001
        fresh = None
    return ActionResult(
        action=action,
        ok=ok,
        error=error,
        observation=fresh,
        t_ms=(time.monotonic() - t0) * 1000.0,
    )
