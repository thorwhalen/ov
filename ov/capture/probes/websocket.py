"""WebSocket probe: frames sent/received and open/close, first-class (D1).

Uses ``page.on("websocket")`` -> ``framesent``/``framereceived``/``close`` (a
high-level Playwright API, *not* CDP). Frame payloads are truncated to a sane cap
to keep the store bounded; realtime *shape* synthesis happens later in arch
analysis, not here.
"""

from __future__ import annotations

import json
from typing import Any

from ...base import Artifact
from . import Probe, ProbeContext, register_probe


def _truncate(payload: Any, cap: int) -> Any:
    if isinstance(payload, (bytes, bytearray)):
        return {"binary": True, "len": len(payload)}
    if isinstance(payload, str) and len(payload) > cap:
        return payload[:cap] + f"...(+{len(payload) - cap})"
    return payload


@register_probe("websocket", produces=("websocket",))
class WebSocketProbe(Probe):
    """Capture WS lifecycle + frames via ``page.on('websocket')``."""

    name = "websocket"

    def __init__(self) -> None:
        self.sockets: list[dict[str, Any]] = []
        self._ctx: ProbeContext | None = None

    def attach(self, ctx: ProbeContext) -> None:
        self._ctx = ctx
        page = ctx.page
        if page is None:
            return
        page.on("websocket", self._on_websocket)

    def _on_websocket(self, ws: Any) -> None:
        cap = self._ctx.config.ws_frame_cap if self._ctx else 4_096
        record: dict[str, Any] = {"url": ws.url, "frames": [], "closed": False}
        self.sockets.append(record)

        def _sent(payload: Any) -> None:
            record["frames"].append({"dir": "sent", "payload": _truncate(payload, cap)})

        def _recv(payload: Any) -> None:
            record["frames"].append({"dir": "recv", "payload": _truncate(payload, cap)})

        def _closed() -> None:
            record["closed"] = True

        try:
            ws.on("framesent", _sent)
            ws.on("framereceived", _recv)
            ws.on("close", lambda *_: _closed())
        except Exception:  # noqa: BLE001
            pass

    def finalize(self, ctx: ProbeContext) -> list[Artifact]:
        if not self.sockets:
            return []
        art = ctx.store.put_artifact(
            json.dumps(self.sockets, indent=2).encode("utf-8"),
            kind="websocket",
            content_type="application/json",
            meta={"sockets": len(self.sockets)},
        )
        return [art]
