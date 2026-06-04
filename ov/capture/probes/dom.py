"""DOM probe: serialized DOM + ARIA snapshot (agent view) + full AX tree (evidence).

Two accessibility views, per the progressive-disclosure rule (§9): the concise
**ARIA snapshot** (``locator.aria_snapshot`` -- ~200-400 tokens, the agent's
view) and the full CDP **AX tree** (recorded as evidence). The serialized DOM
(``page.content()``) is stored for the rendering-model diff and selector lookups.
Runs per captured state so SPA/modal/revealed-menu states are each recorded.
"""

from __future__ import annotations

import json
from typing import Any

from ...base import Artifact
from . import Probe, ProbeContext, register_probe


@register_probe("dom", produces=("dom", "ax_tree", "aria_snapshot"))
class DomProbe(Probe):
    """Snapshot DOM + ARIA snapshot + full AX tree for the current state."""

    name = "dom"

    def capture(self, ctx: ProbeContext) -> list[Artifact]:
        page = ctx.page
        if page is None:
            return []
        artifacts: list[Artifact] = []
        step_id = ctx.step.id if ctx.step else None

        try:
            html = page.content()
            artifacts.append(
                ctx.store.put_artifact(
                    html.encode("utf-8"),
                    kind="dom",
                    step_id=step_id,
                    content_type="text/html",
                    meta={"url": page.url},
                )
            )
        except Exception:  # noqa: BLE001
            pass

        try:
            aria = page.locator("body").aria_snapshot()
            artifacts.append(
                ctx.store.put_artifact(
                    aria.encode("utf-8"),
                    kind="aria_snapshot",
                    step_id=step_id,
                    content_type="text/plain",
                    meta={"url": page.url},
                )
            )
        except Exception:  # noqa: BLE001 - aria snapshot is best-effort
            pass

        if ctx.cdp is not None:
            try:
                nodes = ctx.cdp.get_full_ax_tree()
                artifacts.append(
                    ctx.store.put_artifact(
                        json.dumps(nodes, indent=2).encode("utf-8"),
                        kind="ax_tree",
                        step_id=step_id,
                        content_type="application/json",
                        meta={"url": page.url, "nodes": len(nodes)},
                    )
                )
            except Exception:  # noqa: BLE001
                pass

        return artifacts


def _frames_of(page: Any) -> list[Any]:  # reserved for per-frame AX recursion
    """Return the page's frames (AX tree does not cross-origin-recurse)."""
    try:
        return list(page.frames)
    except Exception:  # noqa: BLE001
        return []
