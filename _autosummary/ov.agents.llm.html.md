# ov.agents.llm

Provider-agnostic LLM facade for the `ov` agent layer (thin, injected, optional).

`ov`’s deterministic core needs no model. The agent layer adds *bounded* model use
— always **dependency-injected**, so there is no provider lock-in and the package
imports fine with no LLM SDK present. This facade is a thin layer over
`coact.llm` (itself glue over `skill.ai`), adding the two ov-specific things
coact’s generic facade does not carry:

* **model routing** — the per-role default models from the spec’s §10 cost gate:
  operator → Haiku (throughput, many steps), UX-analyst → Sonnet (grounded
  narrative judgment), Arch-analyst / orchestrator → Opus (design reasoning /
  planning);
* a **multimodal** [`structured()`](#ov.agents.llm.structured) path — the UX analyst grounds judgment in
  *marked screenshots*, which coact’s text-only `structured` cannot carry. Inject
  any object exposing `structured(prompt, schema, *, images=...)` for full control
  (real vision client); otherwise this degrades to coact’s portable text-only path,
  which is still grounded because the evidence bundle’s *facts* are textual
  summaries of each marked region (§8.1).

### Module Attributes

| [`DEFAULT_MODELS`](#ov.agents.llm.DEFAULT_MODELS)   | Per-role default model selectors (host SDK literals), from the §10 cost gate.   |
|-------------------------------------------------------------------|---------------------------------------------------------------------------------|

### Functions

| [`default_model`](#ov.agents.llm.default_model)(role)                                | The default model selector for a role (falls back to `"sonnet"`).         |
|-----------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------|
| [`resolve_llm`](#ov.agents.llm.resolve_llm)([llm])                                 | Resolve `llm` to a `callable(str) -> str`, or `None`.                     |
| [`structured`](#ov.agents.llm.structured)(prompt, schema, \*[, llm, images, ...]) | Best-effort schema-conforming dict from an LLM, or `None` if unavailable. |

### ov.agents.llm.DEFAULT_MODELS *: [dict](https://docs.python.org/3/builtins/stdtypes.html#dict)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [str](https://docs.python.org/3/builtins/stdtypes.html#str)]* *= {'arch': 'opus', 'operator': 'haiku', 'orchestrator': 'opus', 'ux': 'sonnet'}*

Per-role default model selectors (host SDK literals), from the §10 cost gate.

### ov.agents.llm.default_model(role)

The default model selector for a role (falls back to `"sonnet"`).

```pycon
>>> default_model("operator"), default_model("arch"), default_model("???")
('haiku', 'opus', 'sonnet')
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### ov.agents.llm.resolve_llm(llm=None)

Resolve `llm` to a `callable(str) -> str`, or `None`.

One injection convention: a callable (used as-is), an `aw` `StepConfig`, a
model-name string, or `None` to discover an ambient provider. A plain callable
short-circuits (no optional dependency needed); the other forms defer to
`coact.llm.resolve_llm()`.

```pycon
>>> resolve_llm(lambda p: "hi")("x")
'hi'
```

### ov.agents.llm.structured(prompt, schema, , llm=None, images=None, retries=1)

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
