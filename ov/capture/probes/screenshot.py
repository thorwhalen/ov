"""Screenshot probe: full-page PNG per captured state.

Full-page screenshots ground the set-of-mark evidence bundle later (§8.1). The
artifact id is recorded onto the step so the evidence assembler can resolve the
exact image a finding refers to.
"""

from __future__ import annotations

from ...base import Artifact
from . import Probe, ProbeContext, register_probe


@register_probe("screenshot", produces=("screenshot",))
class ScreenshotProbe(Probe):
    """Capture a full-page PNG of the current state."""

    name = "screenshot"

    def capture(self, ctx: ProbeContext) -> list[Artifact]:
        page = ctx.page
        if page is None:
            return []
        step_id = ctx.step.id if ctx.step else None
        try:
            png = page.screenshot(full_page=True)
        except Exception:  # noqa: BLE001 - some pages reject full_page; fall back
            try:
                png = page.screenshot()
            except Exception:  # noqa: BLE001
                return []
        art = ctx.store.put_artifact(
            png,
            kind="screenshot",
            step_id=step_id,
            content_type="image/png",
            meta={"url": page.url},
        )
        return [art]
