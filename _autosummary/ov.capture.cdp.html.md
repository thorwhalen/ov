# ov.capture.cdp

The CDP escape-hatch plugin (Chromium-only) – the ~20% Playwright can’t reach.

Per D1, attach a CDP session to the same page and use it for: the full
accessibility tree (`Accessibility.getFullAXTree`), Server-Sent-Event frames
(`Network.eventSourceMessageReceived`, which `page.route` cannot reliably
intercept), runtime counters (`Performance.getMetrics`), and the TLS
certificate. `response.body()` eviction recovery via `Network.getResponseBody`
is also exposed but not relied on by the default network probe.

Critical gotcha encoded here: in an AX node, `role`/`name`/`value` are
`AXValue` *objects*, so the accessible name lives at `node["name"]["value"]`;
and `getFullAXTree` does **not** cross-origin-recurse, so frames are handled
one at a time. CDP is Chromium-only – an accepted constraint for the capture tail.

### Functions

| [`flatten_ax_node`](#ov.capture.cdp.flatten_ax_node)(node)   | Flatten a raw CDP AX node into `{role, name, value, ...}` plain values.   |
|--------------------------------------------------------------------------|---------------------------------------------------------------------------|

### Classes

| [`CdpSession`](#ov.capture.cdp.CdpSession)(client)   | A thin, friendly wrapper over a Playwright `CDPSession` (Chromium).   |
|-----------------------------------------------------------------------|-----------------------------------------------------------------------|

### *class* ov.capture.cdp.CdpSession(client)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A thin, friendly wrapper over a Playwright `CDPSession` (Chromium).

#### capture_sse(sink)

Append every SSE frame to `sink` (`Network.eventSourceMessageReceived`).

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### enable_network()

Enable the `Network` domain once (required for SSE + body recovery).

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### get_certificate(origin)

Return the TLS certificate info for `origin` (`Network.getCertificate`).

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

#### get_full_ax_tree(, frame_id=None)

Return the full AX tree as flattened nodes (recorded as evidence).

`getFullAXTree` does not recurse cross-origin frames; pass `frame_id`
to fetch a specific frame’s tree.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]]

#### get_performance_metrics()

Return `Performance.getMetrics` as a `name -> value` mapping.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`float`](https://docs.python.org/3/builtins/functions.html#float)]

#### get_response_body(request_id)

Recover a response body by CDP `requestId` -> `(body, base64Encoded)`.

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`bool`](https://docs.python.org/3/builtins/functions.html#bool)]

#### on(event, handler)

Subscribe to a raw CDP event.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### send(method, params=None)

Send a raw CDP command (the underlying escape hatch).

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)

### ov.capture.cdp.flatten_ax_node(node)

Flatten a raw CDP AX node into `{role, name, value, ...}` plain values.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]
