# ov.analysis.arch.sidecar

Python facade over the Node reverse-engineering sidecar (§6.1, D2).

The mature JS-only tooling (`source-map`, bundle unpacking, AST literal
extraction) lives in a long-lived Node process spoken to over \*\*newline-delimited
JSON-RPC 2.0 on stdio\*\* – the same transport MCP uses, sub-process-bound with no
network exposure of a process that ingests untrusted JS. The wire contract is
defined once here as typed methods; the sidecar functions are pure and stateless.

Everything degrades gracefully: if Node or the sidecar deps are absent,
[`Sidecar.available()`](#ov.analysis.arch.sidecar.Sidecar.available) is `False` and callers skip recovery rather than fail.

### Classes

| [`Sidecar`](#ov.analysis.arch.sidecar.Sidecar)(\*[, node, script, timeout])   | A lazily-started Node sidecar process exposing pure JSON-RPC functions.   |
|-----------------------------------------------------------------------------------------|---------------------------------------------------------------------------|

### Exceptions

| [`SidecarUnavailable`](#ov.analysis.arch.sidecar.SidecarUnavailable)   | Raised when the Node sidecar cannot be used (Node/deps missing).   |
|-----------------------------------------------------------------------|--------------------------------------------------------------------|

### *class* ov.analysis.arch.sidecar.Sidecar(, node='node', script=None, timeout=30.0)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A lazily-started Node sidecar process exposing pure JSON-RPC functions.

#### available()

True when the script exists and its `node_modules` are installed.

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

#### call(method, params)

Invoke a sidecar method; raise [`SidecarUnavailable`](#ov.analysis.arch.sidecar.SidecarUnavailable) on transport error.

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)

#### close()

Terminate the sidecar process (idempotent).

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### consume_source_map(map_json)

Recover `{files: [{path, content}], sources}` from a source map.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

#### extract_literals(js_text)

Static AST extraction of `{strings, urls, routes}` (never evals JS).

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

#### unpack_bundle(js_text)

Unpack a bundle into `{modules: [...]}` (names lost without a map).

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

### *exception* ov.analysis.arch.sidecar.SidecarUnavailable

Bases: [`RuntimeError`](https://docs.python.org/3/builtins/exceptions.html#RuntimeError)

Raised when the Node sidecar cannot be used (Node/deps missing).
