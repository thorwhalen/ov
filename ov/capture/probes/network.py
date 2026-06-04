"""Network probe: request/response metadata + bodies, accumulated from events.

Structured records come from Playwright ``request``/``response`` events (which we
control), not from the HAR file -- the HAR is stored separately by the session as
a raw artifact. Bodies are captured only for configured content types and under
the size cap; ``response.body()`` eviction is caught and recorded as a fact
rather than crashing the run (D1: design around eviction from day one).

Headers are redacted by default (privacy): cookie/auth/token headers never
persist as raw values unless ``config.capture_secrets`` is set.
"""

from __future__ import annotations

import json
from typing import Any

from ...base import Artifact
from ...util import redact_value
from . import Probe, ProbeContext, register_probe

_SENSITIVE_HEADERS = {
    "cookie",
    "set-cookie",
    "authorization",
    "proxy-authorization",
    "x-api-key",
    "x-auth-token",
}


def _scrub_headers(headers: dict[str, str], *, redact: bool) -> dict[str, str]:
    if not redact:
        return dict(headers)
    return {
        k: (redact_value(v) if k.lower() in _SENSITIVE_HEADERS else v)
        for k, v in headers.items()
    }


def _capturable(content_type: str | None, config) -> bool:
    if not content_type:
        return False
    base = content_type.split(";")[0].strip().lower()
    return base in config.capture_body_content_types


def _shape_only(obj: Any) -> Any:
    """Type-preserving redaction of a JSON value (keeps shape for schema synthesis).

    Replaces leaf values with type-zero placeholders so GenSON still infers the
    correct schema while no actual request value (which may be a secret/PII) is
    persisted. Arrays are sampled to keep the store bounded.
    """
    if isinstance(obj, dict):
        return {k: _shape_only(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_shape_only(v) for v in obj[:3]]
    if isinstance(obj, bool):
        return False
    if isinstance(obj, int):
        return 0
    if isinstance(obj, float):
        return 0.0
    if isinstance(obj, str):
        return ""
    return None


@register_probe("network", produces=("request", "network"))
class NetworkProbe(Probe):
    """Accumulate request/response records (+ size-capped bodies) via events."""

    name = "network"

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []
        self.body_artifacts: list[Artifact] = []
        self._ctx: ProbeContext | None = None

    def attach(self, ctx: ProbeContext) -> None:
        self._ctx = ctx
        # Share growing records + body artifacts so the `assets` probe (which
        # `requires` the network stream) can build its inventory without globals.
        ctx.extras["network_records"] = self.records
        ctx.extras["network_body_artifacts"] = self.body_artifacts
        page = ctx.page
        if page is None:
            return
        page.on("response", self._on_response)
        page.on("requestfailed", self._on_failed)

    def _step_id(self) -> str | None:
        return self._ctx.step.id if self._ctx and self._ctx.step else None

    def _on_response(self, response: Any) -> None:
        ctx = self._ctx
        if ctx is None:
            return
        try:
            req = response.request
            headers = response.headers
            content_type = headers.get("content-type")
            rec: dict[str, Any] = {
                "url": response.url,
                "method": req.method,
                "status": response.status,
                "resource_type": req.resource_type,
                "request_headers": _scrub_headers(req.headers, redact=ctx.config.redact_values),
                "response_headers": _scrub_headers(headers, redact=ctx.config.redact_values),
                "step_id": self._step_id(),
                "body_artifact_id": None,
                "body_evicted": False,
            }
            self._capture_request_body(req, rec, ctx)
            if _capturable(content_type, ctx.config):
                try:
                    body = response.body()
                    if body is not None and len(body) <= ctx.config.max_body_bytes:
                        art = ctx.store.put_artifact(
                            body,
                            kind="request",
                            step_id=self._step_id(),
                            content_type=content_type,
                            meta={"url": response.url, "status": response.status},
                        )
                        self.body_artifacts.append(art)
                        rec["body_artifact_id"] = art.artifact_id
                    elif body is not None:
                        rec["body_too_large"] = len(body)
                except Exception:  # noqa: BLE001 - eviction or transient read failure
                    rec["body_evicted"] = True
            self.records.append(rec)
        except Exception:  # noqa: BLE001 - never let a probe crash the run
            pass

    def _capture_request_body(self, req: Any, rec: dict[str, Any], ctx: ProbeContext) -> None:
        """Record the request body's *shape* (JSON only) for API schema synthesis."""
        try:
            post = req.post_data
        except Exception:  # noqa: BLE001
            return
        if not post or len(post) > ctx.config.max_body_bytes:
            return
        try:
            parsed = json.loads(post)
        except (ValueError, TypeError):
            return  # form-encoded / multipart / non-JSON: no shape to record
        rec["request_body"] = _shape_only(parsed) if ctx.config.redact_values else parsed

    def _on_failed(self, request: Any) -> None:
        try:
            self.records.append(
                {
                    "url": request.url,
                    "method": request.method,
                    "status": None,
                    "resource_type": request.resource_type,
                    "failure": (request.failure or "")[:200],
                    "step_id": self._step_id(),
                }
            )
        except Exception:  # noqa: BLE001
            pass

    def finalize(self, ctx: ProbeContext) -> list[Artifact]:
        records_art = ctx.store.put_artifact(
            json.dumps(self.records, indent=2).encode("utf-8"),
            kind="network",
            content_type="application/json",
            meta={"count": len(self.records)},
        )
        return [records_art, *self.body_artifacts]
