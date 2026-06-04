"""Navigation probe: URL changes, redirects, frame tree, and SPA history.

Hard navigations are captured from ``framenavigated``; SPA soft navigations
(``history.pushState``/``replaceState``/``popstate``) are captured by injecting a
tiny init script that records URL changes onto ``window.__ov_nav`` and reading it
back at finalize. This keeps client-side route changes visible even when no
network request accompanies them.
"""

from __future__ import annotations

import json
from typing import Any

from ...base import Artifact
from . import Probe, ProbeContext, register_probe

_NAV_HOOK = """
(() => {
  if (window.__ov_nav_installed) return;
  window.__ov_nav_installed = true;
  window.__ov_nav = [{t: Date.now(), url: location.href, kind: 'init'}];
  const record = (kind) => window.__ov_nav.push({t: Date.now(), url: location.href, kind});
  const wrap = (name) => {
    const orig = history[name];
    history[name] = function () { const r = orig.apply(this, arguments); record(name); return r; };
  };
  wrap('pushState'); wrap('replaceState');
  window.addEventListener('popstate', () => record('popstate'));
  window.addEventListener('hashchange', () => record('hashchange'));
})();
"""


@register_probe("navigation", produces=("navigation",))
class NavigationProbe(Probe):
    """Record hard navigations (events) + soft SPA navigations (injected hook)."""

    name = "navigation"

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self._ctx: ProbeContext | None = None

    def attach(self, ctx: ProbeContext) -> None:
        self._ctx = ctx
        page = ctx.page
        if page is None:
            return
        try:
            page.add_init_script(_NAV_HOOK)
        except Exception:  # noqa: BLE001 - hook is best-effort
            pass
        page.on("framenavigated", self._on_framenavigated)

    def _on_framenavigated(self, frame: Any) -> None:
        try:
            self.events.append(
                {
                    "kind": "framenavigated",
                    "url": frame.url,
                    "is_main": frame == frame.page.main_frame,
                    "step_id": self._ctx.step.id
                    if self._ctx and self._ctx.step
                    else None,
                }
            )
        except Exception:  # noqa: BLE001
            pass

    def finalize(self, ctx: ProbeContext) -> list[Artifact]:
        spa: list[dict[str, Any]] = []
        if ctx.page is not None:
            try:
                spa = ctx.page.evaluate("window.__ov_nav || []")
            except Exception:  # noqa: BLE001
                spa = []
        payload = {"hard": self.events, "soft": spa}
        art = ctx.store.put_artifact(
            json.dumps(payload, indent=2).encode("utf-8"),
            kind="navigation",
            content_type="application/json",
            meta={"hard": len(self.events), "soft": len(spa)},
        )
        return [art]
