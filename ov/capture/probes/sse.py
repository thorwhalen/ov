"""SSE probe: Server-Sent-Event frames via CDP (Chromium-only).

SSE frames are *not* reliably reachable through ``page.route`` or
``response.body()``, so this probe uses ``Network.eventSourceMessageReceived``
through the CDP escape hatch (which requires ``Network.enable``). When CDP is
unavailable (non-Chromium), the probe is inert.
"""

from __future__ import annotations

import json
from typing import Any

from ...base import Artifact
from . import Probe, ProbeContext, register_probe


@register_probe("sse", produces=("sse",))
class SseProbe(Probe):
    """Capture SSE frames via ``CdpSession.capture_sse`` when CDP is available."""

    name = "sse"

    def __init__(self) -> None:
        self.frames: list[dict[str, Any]] = []

    def attach(self, ctx: ProbeContext) -> None:
        if ctx.cdp is None:
            return
        try:
            ctx.cdp.capture_sse(self.frames)
        except Exception:  # noqa: BLE001 - CDP best-effort
            pass

    def finalize(self, ctx: ProbeContext) -> list[Artifact]:
        if not self.frames:
            return []
        art = ctx.store.put_artifact(
            json.dumps(self.frames, indent=2).encode("utf-8"),
            kind="sse",
            content_type="application/json",
            meta={"frames": len(self.frames)},
        )
        return [art]
