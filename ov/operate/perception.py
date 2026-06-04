"""Perception strategies -- pluggable ways to turn a page into an ``Observation``.

A perception strategy returns a uniform :class:`~ov.base.Observation` so the rest
of the operate layer (and the host's policy) stays declarative about *what* an
observation is, not *how* it was grounded. Three strategies ship:

* ``ax_snapshot`` -- affordances from an accessibility-relevant DOM walk plus the
  concise ARIA snapshot text (cheap, deterministic, the default).
* ``screenshot`` -- the same affordances with bounding boxes, intended to pair
  with a screenshot artifact (for canvas/exotic renderers).
* ``hybrid`` -- AX-grounded affordances, robust when the AX layer is thin.

Affordances are extracted by stamping a stable ``data-ov-ref`` attribute on each
interactive element, so :func:`~ov.operate.act.act` can target it deterministically
(``getByRole``-stable, survives CSS churn) -- the require-description-and-ref
safety pattern from Playwright-MCP.
"""

from __future__ import annotations

from typing import Any, Callable

from ..base import Affordance, Observation
from ..util import stable_hash

#: The attribute stamped on interactive elements to create stable refs.
REF_ATTR = "data-ov-ref"

#: name -> ``perceiver(page) -> Observation``
PERCEPTION_REGISTRY: dict[str, Callable[[Any], Observation]] = {}


def register_perception(name: str):
    """Decorator registering a perceiver under ``name``."""

    def deco(fn: Callable[[Any], Observation]) -> Callable[[Any], Observation]:
        PERCEPTION_REGISTRY[name] = fn
        return fn

    return deco


# JS that stamps refs and returns the affordance list for the current state.
_AFFORDANCE_JS = r"""
(refAttr) => {
  const sel = [
    'a[href]', 'button', 'input:not([type=hidden])', 'select', 'textarea',
    '[role=button]', '[role=link]', '[role=tab]', '[role=menuitem]',
    '[role=checkbox]', '[role=radio]', '[role=switch]', '[role=combobox]',
    '[contenteditable=true]', '[onclick]'
  ].join(',');
  const els = Array.from(document.querySelectorAll(sel));
  const out = [];
  let i = 0;
  for (const el of els) {
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    if ((rect.width === 0 && rect.height === 0) || style.visibility === 'hidden' || style.display === 'none') continue;
    const ref = 'e' + (i++);
    el.setAttribute(refAttr, ref);
    const tag = el.tagName.toLowerCase();
    const role = el.getAttribute('role') || tag;
    const name = (el.getAttribute('aria-label') || el.innerText || el.value ||
                  el.getAttribute('placeholder') || el.getAttribute('title') || '').trim().slice(0, 120);
    const editable = ['input', 'textarea'].includes(tag) || el.getAttribute('contenteditable') === 'true';
    out.push({ref, role, name, bbox: [rect.x, rect.y, rect.width, rect.height],
              enabled: !el.disabled, editable});
  }
  return out;
}
"""


def _extract_affordances(page: Any) -> list[Affordance]:
    try:
        raw = page.evaluate(_AFFORDANCE_JS, REF_ATTR)
    except Exception:  # noqa: BLE001 - perception is best-effort
        return []
    affordances = []
    for r in raw:
        bbox = r.get("bbox")
        affordances.append(
            Affordance(
                ref=r["ref"],
                role=r.get("role", ""),
                name=r.get("name", ""),
                bbox=tuple(bbox) if bbox else None,
                enabled=r.get("enabled", True),
                editable=r.get("editable", False),
            )
        )
    return affordances


def _obs_hash(url: str | None, affordances: list[Affordance]) -> str:
    """A content hash of the salient observable state (drives progress detection)."""
    salient = {
        "url": url,
        "affordances": sorted((a.role, a.name) for a in affordances),
    }
    return stable_hash(salient)


def _base_observation(page: Any, strategy: str) -> Observation:
    affordances = _extract_affordances(page)
    url = getattr(page, "url", None)
    title = None
    try:
        title = page.title()
    except Exception:  # noqa: BLE001
        pass
    return Observation(
        strategy=strategy,
        url=url,
        title=title,
        affordances=affordances,
        obs_hash=_obs_hash(url, affordances),
    )


@register_perception("ax_snapshot")
def perceive_ax_snapshot(page: Any) -> Observation:
    """Affordances + concise ARIA snapshot text (the cheap, deterministic default)."""
    obs = _base_observation(page, "ax_snapshot")
    try:
        obs.aria_snapshot = page.locator("body").aria_snapshot()
    except Exception:  # noqa: BLE001
        pass
    return obs


@register_perception("screenshot")
def perceive_screenshot(page: Any) -> Observation:
    """Affordances with bounding boxes (pairs with a screenshot artifact)."""
    return _base_observation(page, "screenshot")


@register_perception("hybrid")
def perceive_hybrid(page: Any) -> Observation:
    """AX-grounded affordances + ARIA snapshot; the robust default when AX is thin."""
    obs = _base_observation(page, "hybrid")
    try:
        obs.aria_snapshot = page.locator("body").aria_snapshot()
    except Exception:  # noqa: BLE001
        pass
    return obs


def perceive(page: Any, strategy: str = "ax_snapshot") -> Observation:
    """Dispatch to the named perception strategy (defaults to ``ax_snapshot``).

    Raises ``KeyError`` with the known strategies when ``strategy`` is unknown --
    an informative error per the project's principles.
    """
    if strategy not in PERCEPTION_REGISTRY:
        raise KeyError(
            f"unknown perception strategy {strategy!r}; "
            f"known: {sorted(PERCEPTION_REGISTRY)}"
        )
    return PERCEPTION_REGISTRY[strategy](page)
