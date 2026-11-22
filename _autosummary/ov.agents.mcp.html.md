# ov.agents.mcp

Expose `ov` to non-Claude-Code hosts as an MCP server (via `py2mcp`).

The host-agent path assumes Claude Code. For *any other* MCP client (a different
agent runtime, an IDE, a foreign orchestrator) this module turns `ov`’s coarse,
JSON-shaped facade into MCP tools — the spec’s “optional `py2mcp` MCP server for
non-Claude-Code hosts” (§9.6 / Phase 4). It deliberately exposes the *coarse* entry
points (`study_url` / `capture_url`), not the page-stateful operate primitives:
MCP tools are stateless calls, and `ov.observe` already owns its own browser
session internally, so each tool is a clean one-shot.

`py2mcp` builds the tool schemas by introspecting these functions’ type hints and
docstrings, so they are kept small and well-typed on purpose. The same skill-declared
path also works the coact-native way:

```default
coact realize study-web-app --backend mcp   # reads the skill's `coact: mcp:` block
```

Run the server directly with `python -m ov.agents.mcp` (or the `ov mcp` CLI).

### Functions

| [`capture_url`](#ov.agents.mcp.capture_url)(url, \*[, mode, authorized, ...])   | Capture a web app (behavioral + static streams) and return a compact summary.   |
|--------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| [`main`](#ov.agents.mcp.main)()                                          | Run the `ov` MCP server over stdio (`python -m ov.agents.mcp` / `ov mcp`).      |
| [`mcp_server`](#ov.agents.mcp.mcp_server)(\*[, name, tools, input_trans])      | Build a FastMCP server exposing `ov` to foreign hosts (via `py2mcp`).           |
| [`ov_tools`](#ov.agents.mcp.ov_tools)()                                      | The `ov` callables exposed as MCP tools (coarse, stateless, JSON-shaped).       |
| [`study_url`](#ov.agents.mcp.study_url)(url, \*[, mode, authorized, ...])     | Study a web app end-to-end (deterministic) and return its synopsis.             |

### ov.agents.mcp.capture_url(url, , mode='reconstruct', authorized=False, crawl_pages=0)

Capture a web app (behavioral + static streams) and return a compact summary.

Runs only the deterministic capture (no analysis). Use when you want the raw
captured facts (technologies, rendering model, step/artifact counts) without the
analyzers.

* **Parameters:**
  * **url** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – the target to capture.
  * **mode** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – `"reconstruct"` or `"review"`.
  * **authorized** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – acknowledge authorization to capture a foreign target.
  * **crawl_pages** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – if > 1, politely crawl that many same-origin pages.
* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)
* **Returns:**
  A summary dict (run id, target, counts, detected technologies, rendering model).

### ov.agents.mcp.main()

Run the `ov` MCP server over stdio (`python -m ov.agents.mcp` / `ov mcp`).

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### ov.agents.mcp.mcp_server(, name='ov', tools=None, input_trans=None)

Build a FastMCP server exposing `ov` to foreign hosts (via `py2mcp`).

```pycon
>>> srv = mcp_server()
>>> srv.run()                               # serve over stdio
```

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)

### ov.agents.mcp.ov_tools()

The `ov` callables exposed as MCP tools (coarse, stateless, JSON-shaped).

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)]

### ov.agents.mcp.study_url(url, , mode='reconstruct', authorized=False, crawl_pages=0, lenses='ux,arch')

Study a web app end-to-end (deterministic) and return its synopsis.

Drives the target, runs the UX + architecture analyzers, and returns the
deduplicated `synopsis.json` document — the compact, evidence-referenced SSOT a
downstream agent acts on. Model-free (no LLM judgment); the host adds narrative.

* **Parameters:**
  * **url** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – the target to study.
  * **mode** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – `"reconstruct"` (foreign target) or `"review"` (own target).
  * **authorized** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – acknowledge authorization to study a foreign target.
  * **crawl_pages** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – if > 1, politely crawl that many same-origin pages.
  * **lenses** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – comma-separated analysis lenses (`"ux"`, `"arch"`).
* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)
* **Returns:**
  The synopsis document (run id, deduplicated findings, severity histogram).
