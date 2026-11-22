# ov.agents.realize

The mechanical lift — turn `ov`’s skills into agent definitions and realize them.

This is the thin ov-specific facade over coact’s two transforms (D4): `COMPLETE`
(a `.claude/skills/` skill → an `coact.AgentDefinition`, reading the extras
from the skill’s `coact:` block) and `REALIZE` (a definition → a running agent on
a chosen backend). Nothing here re-implements an agent loop or a persona; coact does
the lift, `ov` just points it at the right skills and surfaces the cost gate.

The cheapest backend is the default (`host`): [`materialize()`](#ov.agents.realize.materialize) writes
`.claude/agents/*.md` and links the skills so **Claude Code** runs ov’s agents as
subagents — no new runtime, no fan-out. Standing up an in-process fleet (`sdk`) or
a foreign-host tool server (`mcp`) is opt-in; call [`estimate()`](#ov.agents.realize.estimate) first to see the
~15× fan-out premium before you spawn one (the §3.5 cost gate).

### Functions

| [`complete_agent`](#ov.agents.realize.complete_agent)(role_or_name, \*[, ...])         | `COMPLETE` one ov skill into a `coact.AgentDefinition` (the lift).                  |
|--------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------|
| [`complete_all`](#ov.agents.realize.complete_all)(\*[, roles, skills_dir, policy])   | `COMPLETE` every ov agent (or `roles`) → `{role: AgentDefinition}`.                 |
| [`estimate`](#ov.agents.realize.estimate)([roles, skills_dir])                   | The cost gate — coact's fan-out estimate over the selected ov agents.               |
| [`materialize`](#ov.agents.realize.materialize)(\*[, roles, dest, scope, ...])      | Realize ov's agents on the **host** backend: write `.claude/agents/` + link skills. |
| [`realize_agent`](#ov.agents.realize.realize_agent)(role_or_name, \*[, backend, ...]) | Realize a single ov agent on `backend` (`"host"` | `"sdk"` | `"mcp"`).              |

### ov.agents.realize.complete_agent(role_or_name, , skills_dir=None, policy=None, llm=None)

`COMPLETE` one ov skill into a `coact.AgentDefinition` (the lift).

Mechanical by default (no LLM): model, tools, return contract and MCP wiring come
from the skill’s `coact:` block. Pass `llm=` only to let coact *draft* a
persona — the deterministic template path is used otherwise.

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)

### ov.agents.realize.complete_all(, roles=None, skills_dir=None, policy=None)

`COMPLETE` every ov agent (or `roles`) → `{role: AgentDefinition}`.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

### ov.agents.realize.estimate(roles=None, , skills_dir=None)

The cost gate — coact’s fan-out estimate over the selected ov agents.

Realizing an in-package fleet costs roughly an order of magnitude more tokens
than the host path, and the premium is worst on *interdependent* work (ov’s
analysts share the evidence bundle). Render this before spawning:

```default
from ov.agents import estimate
print(estimate(["ux-analyst", "arch-analyst"]).render())
```

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)

### ov.agents.realize.materialize(, roles=None, dest=None, scope='project', project_dir=None, link=True, skills_dir=None, force=False, policy=None)

Realize ov’s agents on the **host** backend: write `.claude/agents/` + link skills.

This is the cheap pit-of-success — it stands up *no* runtime. It emits one
`<name>.md` per agent into `dest` (default: the project’s `.claude/agents/`)
and symlinks each referenced skill into the sibling `.claude/skills/` so Claude
Code discovers both, then verifies discovery. Returns coact’s `RealizedHost`
(`.agents`, `.skills`, `.warnings`).

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)

### ov.agents.realize.realize_agent(role_or_name, , backend='host', skills_dir=None, policy=None, \*\*kwargs)

Realize a single ov agent on `backend` (`"host"` | `"sdk"` | `"mcp"`).

`sdk` returns a `coact.RunnableAgent` (an `aw.AgenticStep`) for text-shaped
agents; `mcp` exposes the skill’s declared `coact: mcp:` tools as a FastMCP
server (foreign hosts). For ov’s live-browser / multimodal runtimes use
[`OperatorAgent`](ov.agents.operator.html.md#ov.agents.operator.OperatorAgent) / [`AnalystAgent`](ov.agents.analyst.html.md#ov.agents.analyst.AnalystAgent)
instead — coact’s text-prompt `sdk` agent can’t drive a page or send images.

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)
