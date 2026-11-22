# ov.agents

`ov.agents` — the optional in-package agent layer (Phase 4 productization).

This is the *mechanical lift* the spec promised (§7, D4): the Phase-1–3 deterministic
core + the `.claude/skills/` policy are re-hosted as **runnable agents**, with no
rewrite. The lift is done by [coact](https://github.com/thorwhalen/coact)
(`COMPLETE` a skill into an agent definition, `REALIZE` it onto a backend); this
package is the thin ov-specific glue that coact intentionally leaves out — the
operator’s live-browser **loop**, the analyst’s **multimodal** evidence-bundle call,
and the orchestration **topology**.

Three things to know:

* **Host stays the manager (the cheap default).** [`materialize()`](#ov.agents.materialize) writes
  `.claude/agents/` so Claude Code runs ov’s agents as subagents — zero LLM, no
  fan-out. In-package SDK agents ([`OperatorAgent`](#ov.agents.OperatorAgent), [`AnalystAgent`](#ov.agents.AnalystAgent),
  [`study()`](#ov.agents.study)) are opt-in; [`estimate()`](#ov.agents.estimate) surfaces the ~15× fan-out cost gate.
* **Reuse, don’t rewrite.** Capture, the analyzers, the evidence-bundle assembler,
  the reliability passes and the synopsis map-reduce are used unchanged.
* **Injected, optional, model-free-by-default.** Every LLM is dependency-injected;
  `coact`/`aw`/`py2mcp` are the `ov[agents]` extra, gated with a friendly
  error — importing this package needs none of them.
  ```pycon
  >>> from ov.agents import OV_AGENTS, default_model
  >>> sorted(OV_AGENTS)
  ['arch-analyst', 'operator', 'orchestrator', 'ux-analyst']
  >>> default_model("operator")
  'haiku'
  ```

### *class* ov.agents.AgentSpec(name, role, skill, lens=None, default_model='sonnet')

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

One `ov` agent: its name, role, source skill, optional lens, default model.

```pycon
>>> AgentSpec("ov-analyze-ux", "analyst", "ov-analyze-ux", "ux").lens
'ux'
```

### *class* ov.agents.AnalystAgent(lens, llm=None, judge=None, model=None, max_marks=20, task=None, name='')

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Interpret a captured run’s evidence bundle into grounded findings (UX or Arch).

* **Parameters:**
  * **lens** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – `"ux"` or `"arch"` — selects default model + finding defaults.
  * **llm** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – the injected LLM (a callable, an object exposing `structured` for the
    multimodal path, an `aw` `StepConfig`, or `None`). Ignored if a
    `judge` is given.
  * **judge** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis), [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)]]) – `(bundle, *, run, store) -> list[Finding | dict]`. Override the whole
    LLM step (tests, alternative providers). Defaults to `_default_judge()`.
  * **model** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]) – model selector for the image-budget + info (defaults from the lens).
  * **max_marks** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – cap on Set-of-Mark regions in the bundle.

#### execute(input_data, context=None)

Analyze a run (or a prebuilt bundle) → `(verified_findings, info)` (aw protocol).

`input_data` may be a [`CaptureRun`](ov.base.html.md#ov.base.CaptureRun), an
[`EvidenceBundle`](ov.base.html.md#ov.base.EvidenceBundle), or a mapping carrying `run` / `store` /
`bundle`. The verified LLM findings are appended to `run.findings` (additive
— `source_layer` keeps them distinct from deterministic facts) and returned.

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Finding`](ov.base.html.md#ov.base.Finding)], [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]]

### *class* ov.agents.OperatorAgent(decider, session=None, max_steps=12, strategy='ax_snapshot', polite_rate_s=0.0, no_progress_steps=3, observe_fn=None, act_fn=None, model='haiku', name='operator')

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Drive a target toward a goal, recording every step (an `aw.AgenticStep`).

* **Parameters:**
  * **decider** ([`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis), [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Action`](ov.base.html.md#ov.base.Action)]]) – `(observation, *, goal, history) -> Action | None`. Returns the
    next action, or `None` to stop. Use `make_llm_decider()` for a
    model-backed one, or any callable (host / script / test stub).
  * **session** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – a [`CaptureSession`](ov.capture.session.html.md#ov.capture.session.CaptureSession) (supplies `.page` +
    `.run`). Optional — `page` and `run` may instead arrive via the
    `context` passed to [`execute()`](#ov.agents.OperatorAgent.execute) (keys `"page"` / `"run"`).
  * **max_steps** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – hard cap on actions (a budget; the deterministic loop signal is
    advisory, the cap is the backstop).
  * **strategy** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – perception strategy for the default `observe` (`"ax_snapshot"`
    | `"screenshot"` | `"hybrid"`).
  * **act_fn** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`Any`](https://docs.python.org/3/library/typing.html#typing.Any), [`Action`](ov.base.html.md#ov.base.Action)], [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]]) – injection seams for the hands (default to the real
    [`observe()`](ov.operate.html.md#ov.operate.observe) / [`act()`](ov.operate.html.md#ov.operate.act)); tests pass fakes.

#### execute(input_data, context=None)

Pursue `input_data` (the goal) and return `(CaptureRun, info)` (aw protocol).

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`CaptureRun`](ov.base.html.md#ov.base.CaptureRun), [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]]

### *class* ov.agents.Orchestrator(llm=None, lenses=('ux', 'arch'), out_dir=None, store=None, capture_fn=<function \_default_capture>, analyze_fn=<function \_default_analyze>, report_fn=<function \_default_report>, synopsis_fn=<function \_default_synopsis>, capture_kwargs=dict())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Coordinate a full study, delegating each stage (never analyzing itself).

* **Parameters:**
  * **llm** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – the injected model for the analyst agents. `None` → deterministic-only
    study (the host-is-manager default; analysts are skipped).
  * **lenses** ([`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)) – which analysis lenses to run (`"ux"` and/or `"arch"`).
  * **out_dir** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – where reports + synopsis are written (`None` → the run’s store).
  * **synopsis_fn** ([`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)) – stage seams (default to the
    real `ov` facade). Inject fakes to unit-test the coordination.
  * **capture_kwargs** ([`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)) – extra kwargs forwarded to `capture_fn` (e.g. `mode`,
    `authorized`, `crawl_pages`, `journey`).

#### run(url)

Run the full study for `url` and return an `OrchestratorResult`.

* **Return type:**
  [`OrchestratorResult`](ov.agents.orchestrator.html.md#ov.agents.orchestrator.OrchestratorResult)

### ov.agents.agents_for_role(role)

All specs with `role` (e.g. both analysts).

```pycon
>>> [s.lens for s in agents_for_role("analyst")]
['ux', 'arch']
```

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`AgentSpec`](ov.agents.definitions.html.md#ov.agents.definitions.AgentSpec)]

### ov.agents.analyst_specs()

The UX + Arch analyst specs, in pipeline order (UX then Arch).

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`AgentSpec`](ov.agents.definitions.html.md#ov.agents.definitions.AgentSpec)]

### ov.agents.arch_analyst(llm=None, \*\*kwargs)

A software-architecture analyst (Opus-routed). `llm` is the injected model.

```pycon
>>> arch_analyst().model
'opus'
```

* **Return type:**
  [`AnalystAgent`](ov.agents.analyst.html.md#ov.agents.analyst.AnalystAgent)

### ov.agents.complete_agent(role_or_name, , skills_dir=None, policy=None, llm=None)

`COMPLETE` one ov skill into a `coact.AgentDefinition` (the lift).

Mechanical by default (no LLM): model, tools, return contract and MCP wiring come
from the skill’s `coact:` block. Pass `llm=` only to let coact *draft* a
persona — the deterministic template path is used otherwise.

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)

### ov.agents.complete_all(, roles=None, skills_dir=None, policy=None)

`COMPLETE` every ov agent (or `roles`) → `{role: AgentDefinition}`.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

### ov.agents.default_model(role)

The default model selector for a role (falls back to `"sonnet"`).

```pycon
>>> default_model("operator"), default_model("arch"), default_model("???")
('haiku', 'opus', 'sonnet')
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### ov.agents.default_skills_dir()

Resolve the directory holding `ov`’s skills (env, then packaged, then repo).

Returns the first layout that actually contains skills; if none is found, the
packaged path is returned so callers get a clear, consistent miss to report.

Deliberately *not* cached: it reads `OV_SKILLS_DIR` at call time (a few cheap
`Path` checks), so an env change is always honoured. Resolution is invoked
once per agent lift, not in a hot loop, so the cost is immaterial.

* **Return type:**
  [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)

### ov.agents.estimate(roles=None, , skills_dir=None)

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

### ov.agents.materialize(, roles=None, dest=None, scope='project', project_dir=None, link=True, skills_dir=None, force=False, policy=None)

Realize ov’s agents on the **host** backend: write `.claude/agents/` + link skills.

This is the cheap pit-of-success — it stands up *no* runtime. It emits one
`<name>.md` per agent into `dest` (default: the project’s `.claude/agents/`)
and symlinks each referenced skill into the sibling `.claude/skills/` so Claude
Code discovers both, then verifies discovery. Returns coact’s `RealizedHost`
(`.agents`, `.skills`, `.warnings`).

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)

### ov.agents.mcp_server(, name='ov', tools=None, input_trans=None)

Build a FastMCP server exposing `ov` to foreign hosts (via `py2mcp`).

```pycon
>>> srv = mcp_server()
>>> srv.run()                               # serve over stdio
```

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)

### ov.agents.ov_tools()

The `ov` callables exposed as MCP tools (coarse, stateless, JSON-shaped).

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)]

### ov.agents.realize_agent(role_or_name, , backend='host', skills_dir=None, policy=None, \*\*kwargs)

Realize a single ov agent on `backend` (`"host"` | `"sdk"` | `"mcp"`).

`sdk` returns a `coact.RunnableAgent` (an `aw.AgenticStep`) for text-shaped
agents; `mcp` exposes the skill’s declared `coact: mcp:` tools as a FastMCP
server (foreign hosts). For ov’s live-browser / multimodal runtimes use
[`OperatorAgent`](ov.agents.operator.html.md#ov.agents.operator.OperatorAgent) / [`AnalystAgent`](ov.agents.analyst.html.md#ov.agents.analyst.AnalystAgent)
instead — coact’s text-prompt `sdk` agent can’t drive a page or send images.

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)

### ov.agents.resolve_llm(llm=None)

Resolve `llm` to a `callable(str) -> str`, or `None`.

One injection convention: a callable (used as-is), an `aw` `StepConfig`, a
model-name string, or `None` to discover an ambient provider. A plain callable
short-circuits (no optional dependency needed); the other forms defer to
`coact.llm.resolve_llm()`.

```pycon
>>> resolve_llm(lambda p: "hi")("x")
'hi'
```

### ov.agents.skill_path(name, , skills_dir=None)

Absolute path to skill `name`’s directory (the one holding `SKILL.md`).

Raises [`FileNotFoundError`](https://docs.python.org/3/builtins/exceptions.html#FileNotFoundError) with an actionable hint when the skill is not
discoverable, rather than letting coact fail later on a missing path.

* **Return type:**
  [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)

### ov.agents.structured(prompt, schema, , llm=None, images=None, retries=1)

Best-effort schema-conforming dict from an LLM, or `None` if unavailable.

Resolution order honours dependency injection:

1. if `llm` exposes a `structured` method, it is used as-is — this is the
   multimodal path (the method may accept `images=`); a real vision client
   plugs in here;
2. otherwise fall through to coact’s portable text-only `structured` (any
   `images` are dropped — the bundle’s textual facts still ground the claims);
3. if no LLM is resolvable at all, return `None` so callers fall back to a
   deterministic-only path (no crash, no provider lock-in).

* **Return type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]

### ov.agents.study(url, , llm=None, lenses=('ux', 'arch'), \*\*kwargs)

Run an end-to-end study of `url` (the in-package twin of the `study-web-app` skill).

The pit-of-success one-liner: capture → analyze → (optional analyst judgment) →
report → synopsis. With `llm=None` it is fully deterministic; pass an injected
model to add grounded UX/Arch narrative. Forwards `mode` / `authorized` /
`crawl_pages` / `out_dir` / stage seams via `**kwargs`.

* **Return type:**
  [`OrchestratorResult`](ov.agents.orchestrator.html.md#ov.agents.orchestrator.OrchestratorResult)

### ov.agents.ux_analyst(llm=None, \*\*kwargs)

A UX/accessibility analyst (Sonnet-routed). `llm` is the injected model.

```pycon
>>> a = ux_analyst()
>>> a.lens, a.model, a.name
('ux', 'sonnet', 'ux-analyst')
```

* **Return type:**
  [`AnalystAgent`](ov.agents.analyst.html.md#ov.agents.analyst.AnalystAgent)

### Modules

| [`analyst`](ov.agents.analyst.html.md#module-ov.agents.analyst)           | The Analyst agents (UX + Arch) — grounded judgment over an evidence bundle.       |
|---------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------|
| [`definitions`](ov.agents.definitions.html.md#module-ov.agents.definitions)   | SSOT: which `ov` skills become which agents (role, lens, model routing).          |
| [`llm`](ov.agents.llm.html.md#module-ov.agents.llm)                   | Provider-agnostic LLM facade for the `ov` agent layer (thin, injected, optional). |
| [`mcp`](ov.agents.mcp.html.md#module-ov.agents.mcp)                   | Expose `ov` to non-Claude-Code hosts as an MCP server (via `py2mcp`).             |
| [`operator`](ov.agents.operator.html.md#module-ov.agents.operator)         | The Operator agent — the model-bound perceive→decide→act→record loop.             |
| [`orchestrator`](ov.agents.orchestrator.html.md#module-ov.agents.orchestrator) | The Orchestrator — a *pure coordinator* over the study pipeline (`aw` workflow).  |
| [`realize`](ov.agents.realize.html.md#module-ov.agents.realize)           | The mechanical lift — turn `ov`'s skills into agent definitions and realize them. |
