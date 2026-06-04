"""Console probe: console messages, page errors, and unhandled rejections.

Captured from Playwright ``console``/``pageerror`` events. Each entry carries the
step it occurred in so the UX engine can attribute console-error-on-step (§5.1
heuristic) and the robustness analysis can corroborate broken states.
"""

from __future__ import annotations

import json
from typing import Any

from ...base import Artifact
from . import Probe, ProbeContext, register_probe


@register_probe("console", produces=("console",))
class ConsoleProbe(Probe):
    """Accumulate console + pageerror entries via events."""

    name = "console"

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []
        self._ctx: ProbeContext | None = None

    def attach(self, ctx: ProbeContext) -> None:
        self._ctx = ctx
        page = ctx.page
        if page is None:
            return
        page.on("console", self._on_console)
        page.on("pageerror", self._on_pageerror)

    def _step_id(self) -> str | None:
        return self._ctx.step.id if self._ctx and self._ctx.step else None

    def _cap(self) -> int:
        return self._ctx.config.console_text_cap if self._ctx else 2_000

    def _on_console(self, msg: Any) -> None:
        try:
            loc = msg.location or {}
            self.entries.append(
                {
                    "kind": "console",
                    "type": msg.type,
                    "text": msg.text[: self._cap()],
                    "url": loc.get("url"),
                    "line": loc.get("lineNumber"),
                    "step_id": self._step_id(),
                }
            )
        except Exception:  # noqa: BLE001
            pass

    def _on_pageerror(self, err: Any) -> None:
        try:
            self.entries.append(
                {
                    "kind": "pageerror",
                    "type": "error",
                    "text": str(err)[: self._cap()],
                    "step_id": self._step_id(),
                }
            )
        except Exception:  # noqa: BLE001
            pass

    def finalize(self, ctx: ProbeContext) -> list[Artifact]:
        art = ctx.store.put_artifact(
            json.dumps(self.entries, indent=2).encode("utf-8"),
            kind="console",
            content_type="application/json",
            meta={"count": len(self.entries)},
        )
        return [art]
