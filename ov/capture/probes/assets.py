"""Assets probe: a content-addressed inventory of loaded resources.

Bodies are already stored by the ``network`` probe (content-addressed, so they
dedupe). This probe builds the *inventory*: one manifest row per resource with
url, MIME, size, hash, and the body artifact id when captured. It ``requires``
the network stream and therefore runs after it (registry ordering).
"""

from __future__ import annotations

import json
from typing import Any

from ...base import Artifact
from . import Probe, ProbeContext, register_probe


@register_probe("assets", requires=("network", "request"), produces=("assets",))
class AssetsProbe(Probe):
    """Build an asset inventory from the accumulated network records."""

    name = "assets"

    def finalize(self, ctx: ProbeContext) -> list[Artifact]:
        records: list[dict[str, Any]] = ctx.extras.get("network_records", [])
        body_arts = {
            a.artifact_id: a for a in ctx.extras.get("network_body_artifacts", [])
        }
        inventory: list[dict[str, Any]] = []
        for rec in records:
            art = body_arts.get(rec.get("body_artifact_id"))
            inventory.append(
                {
                    "url": rec.get("url"),
                    "mime": (rec.get("response_headers") or {}).get("content-type"),
                    "status": rec.get("status"),
                    "resource_type": rec.get("resource_type"),
                    "size": art.size if art else rec.get("body_too_large"),
                    "hash": art.content_hash if art else None,
                    "artifact_id": rec.get("body_artifact_id"),
                }
            )
        art = ctx.store.put_artifact(
            json.dumps(inventory, indent=2).encode("utf-8"),
            kind="assets",
            content_type="application/json",
            meta={"count": len(inventory)},
        )
        return [art]
