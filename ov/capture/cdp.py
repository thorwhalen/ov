"""The CDP escape-hatch plugin (Chromium-only) -- the ~20% Playwright can't reach.

Per D1, attach a CDP session to the same page and use it for: the full
accessibility tree (``Accessibility.getFullAXTree``), Server-Sent-Event frames
(``Network.eventSourceMessageReceived``, which ``page.route`` cannot reliably
intercept), runtime counters (``Performance.getMetrics``), and the TLS
certificate. ``response.body()`` eviction recovery via ``Network.getResponseBody``
is also exposed but not relied on by the default network probe.

Critical gotcha encoded here: in an AX node, ``role``/``name``/``value`` are
``AXValue`` *objects*, so the accessible name lives at ``node["name"]["value"]``;
and ``getFullAXTree`` does **not** cross-origin-recurse, so frames are handled
one at a time. CDP is Chromium-only -- an accepted constraint for the capture tail.
"""

from __future__ import annotations

from typing import Any, Callable


def _ax_value(field: Any) -> Any:
    """Unwrap an ``AXValue`` object to its ``.value`` (handles plain values too)."""
    if isinstance(field, dict) and "value" in field:
        return field["value"]
    return field


def flatten_ax_node(node: dict[str, Any]) -> dict[str, Any]:
    """Flatten a raw CDP AX node into ``{role, name, value, ...}`` plain values."""
    props = {
        p.get("name"): _ax_value(p.get("value")) for p in node.get("properties", [])
    }
    return {
        "nodeId": node.get("nodeId"),
        "role": _ax_value(node.get("role")),
        "name": _ax_value(node.get("name")),
        "value": _ax_value(node.get("value")),
        "description": _ax_value(node.get("description")),
        "ignored": node.get("ignored", False),
        "backendDOMNodeId": node.get("backendDOMNodeId"),
        "childIds": node.get("childIds", []),
        "properties": props,
    }


class CdpSession:
    """A thin, friendly wrapper over a Playwright ``CDPSession`` (Chromium)."""

    def __init__(self, client: Any):
        self._client = client
        self._network_enabled = False

    def send(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Send a raw CDP command (the underlying escape hatch)."""
        return self._client.send(method, params or {})

    def on(self, event: str, handler: Callable[[dict[str, Any]], None]) -> None:
        """Subscribe to a raw CDP event."""
        self._client.on(event, handler)

    def enable_network(self) -> None:
        """Enable the ``Network`` domain once (required for SSE + body recovery)."""
        if not self._network_enabled:
            self.send("Network.enable")
            self._network_enabled = True

    # --- accessibility ----------------------------------------------------- #

    def get_full_ax_tree(self, *, frame_id: str | None = None) -> list[dict[str, Any]]:
        """Return the full AX tree as flattened nodes (recorded as evidence).

        ``getFullAXTree`` does not recurse cross-origin frames; pass ``frame_id``
        to fetch a specific frame's tree.
        """
        self.send("Accessibility.enable")  # keeps AXNodeIds stable across calls
        params = {"frameId": frame_id} if frame_id else {}
        result = self.send("Accessibility.getFullAXTree", params)
        return [flatten_ax_node(n) for n in result.get("nodes", [])]

    # --- performance ------------------------------------------------------- #

    def get_performance_metrics(self) -> dict[str, float]:
        """Return ``Performance.getMetrics`` as a ``name -> value`` mapping."""
        self.send("Performance.enable")
        result = self.send("Performance.getMetrics")
        return {m["name"]: m["value"] for m in result.get("metrics", [])}

    # --- realtime: SSE ----------------------------------------------------- #

    def capture_sse(self, sink: list[dict[str, Any]]) -> None:
        """Append every SSE frame to ``sink`` (``Network.eventSourceMessageReceived``)."""
        self.enable_network()

        def _on_sse(params: dict[str, Any]) -> None:
            sink.append(
                {
                    "requestId": params.get("requestId"),
                    "timestamp": params.get("timestamp"),
                    "eventName": params.get("eventName"),
                    "eventId": params.get("eventId"),
                    "data": params.get("data"),
                }
            )

        self.on("Network.eventSourceMessageReceived", _on_sse)

    # --- body eviction recovery (available; not relied on by default) ------ #

    def get_response_body(self, request_id: str) -> tuple[str, bool]:
        """Recover a response body by CDP ``requestId`` -> ``(body, base64Encoded)``."""
        result = self.send("Network.getResponseBody", {"requestId": request_id})
        return result.get("body", ""), bool(result.get("base64Encoded"))

    # --- certificate ------------------------------------------------------- #

    def get_certificate(self, origin: str) -> dict[str, Any]:
        """Return the TLS certificate info for ``origin`` (``Network.getCertificate``)."""
        self.enable_network()
        try:
            return self.send("Network.getCertificate", {"origin": origin})
        except Exception:  # noqa: BLE001 - certificate is best-effort
            return {}
