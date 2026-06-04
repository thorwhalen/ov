"""Storage probe: cookies, localStorage, sessionStorage, IndexedDB names.

Values are **redacted by default** (privacy; ``config.redact_values``) -- we keep
the *shape* of client state (which keys exist, how big) without persisting
secrets/PII. sessionStorage is read manually (it is not in ``storage_state``) and
IndexedDB is probed for database names only (deep dumps are fragile and deferred).
"""

from __future__ import annotations

import json
from typing import Any

from ...base import Artifact
from ...util import redact_value
from . import Probe, ProbeContext, register_probe

_READ_JS = r"""
async () => {
  const dump = (s) => { const o = {}; for (let i = 0; i < s.length; i++) { const k = s.key(i); o[k] = s.getItem(k); } return o; };
  let idb = [];
  try { if (indexedDB.databases) idb = (await indexedDB.databases()).map(d => d.name); } catch (e) {}
  return {
    localStorage: dump(window.localStorage),
    sessionStorage: dump(window.sessionStorage),
    indexedDB: idb,
  };
}
"""


def _redact_store(mapping: dict[str, Any], *, redact: bool) -> dict[str, Any]:
    if not redact:
        return mapping
    return {k: redact_value(v) for k, v in mapping.items()}


@register_probe("storage", produces=("storage",))
class StorageProbe(Probe):
    """Snapshot client storage (redacted) for the current state."""

    name = "storage"

    def capture(self, ctx: ProbeContext) -> list[Artifact]:
        page = ctx.page
        if page is None:
            return []
        redact = ctx.config.redact_values
        payload: dict[str, Any] = {"localStorage": {}, "sessionStorage": {}, "indexedDB": []}
        try:
            raw = page.evaluate(_READ_JS)
            payload["localStorage"] = _redact_store(raw.get("localStorage", {}), redact=redact)
            payload["sessionStorage"] = _redact_store(raw.get("sessionStorage", {}), redact=redact)
            payload["indexedDB"] = raw.get("indexedDB", [])
        except Exception:  # noqa: BLE001
            pass
        try:
            cookies = page.context.cookies()
            payload["cookies"] = [
                {
                    "name": c.get("name"),
                    "domain": c.get("domain"),
                    "value": redact_value(c.get("value")) if redact else c.get("value"),
                    "httpOnly": c.get("httpOnly"),
                    "secure": c.get("secure"),
                }
                for c in cookies
            ]
        except Exception:  # noqa: BLE001
            payload["cookies"] = []
        art = ctx.store.put_artifact(
            json.dumps(payload, indent=2).encode("utf-8"),
            kind="storage",
            step_id=ctx.step.id if ctx.step else None,
            content_type="application/json",
            meta={"redacted": redact},
        )
        return [art]
