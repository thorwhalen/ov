# ov.agents.definitions

SSOT: which `ov` skills become which agents (role, lens, model routing).

The *extras* a skill needs to become an agent — model, tool allowlist, return
contract, MCP exposure — live in each skill’s additive `coact:` frontmatter block
(coact reads them during `COMPLETE`). This module records only the ov-side mapping
coact cannot infer: which skill plays which **role** in the study pipeline and, for
analysts, which analysis **lens** it carries.

Everything here is *data*. Add an agent by adding a row — no dispatcher to edit
(open-closed). This mirrors `ov`’s other registries (probes / analyzers / report
sections): a capability is a registered piece of data, never a branch in a switch.

### Module Attributes

| [`OV_AGENTS`](#ov.agents.definitions.OV_AGENTS)   | The `ov` agent registry (role key -> spec) — the headline of Phase 4.   |
|--------------------------------------------------------------|-------------------------------------------------------------------------|

### Functions

| [`agents_for_role`](#ov.agents.definitions.agents_for_role)(role)   | All specs with `role` (e.g. both analysts).                    |
|--------------------------------------------------------------------------|----------------------------------------------------------------|
| [`analyst_specs`](#ov.agents.definitions.analyst_specs)()         | The UX + Arch analyst specs, in pipeline order (UX then Arch). |

### Classes

| [`AgentSpec`](#ov.agents.definitions.AgentSpec)(name, role, skill[, lens, ...])   | One `ov` agent: its name, role, source skill, optional lens, default model.   |
|----------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------|

### *class* ov.agents.definitions.AgentSpec(name, role, skill, lens=None, default_model='sonnet')

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

One `ov` agent: its name, role, source skill, optional lens, default model.

```pycon
>>> AgentSpec("ov-analyze-ux", "analyst", "ov-analyze-ux", "ux").lens
'ux'
```

### ov.agents.definitions.OV_AGENTS *: [dict](https://docs.python.org/3/builtins/stdtypes.html#dict)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [AgentSpec](#ov.agents.definitions.AgentSpec)]* *= {'arch-analyst': AgentSpec(name='ov-analyze-arch', role='analyst', skill='ov-analyze-arch', lens='arch', default_model='opus'), 'operator': AgentSpec(name='ov-operate', role='operator', skill='ov-operate', lens=None, default_model='haiku'), 'orchestrator': AgentSpec(name='study-web-app', role='orchestrator', skill='study-web-app', lens=None, default_model='opus'), 'ux-analyst': AgentSpec(name='ov-analyze-ux', role='analyst', skill='ov-analyze-ux', lens='ux', default_model='sonnet')}*

The `ov` agent registry (role key -> spec) — the headline of Phase 4.
Model defaults follow the spec’s §10 cost gate (Opus for design/planning
judgment, Sonnet for grounded UX narrative, Haiku for the throughput-bound driver).

### ov.agents.definitions.agents_for_role(role)

All specs with `role` (e.g. both analysts).

```pycon
>>> [s.lens for s in agents_for_role("analyst")]
['ux', 'arch']
```

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`AgentSpec`](#ov.agents.definitions.AgentSpec)]

### ov.agents.definitions.analyst_specs()

The UX + Arch analyst specs, in pipeline order (UX then Arch).

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`AgentSpec`](#ov.agents.definitions.AgentSpec)]
