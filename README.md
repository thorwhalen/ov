# ov

**OverView** — point it at a URL and it drives the web app like a user, records
what the app *does* (pages, DOM, screenshots, network, console, journey) and what
it's *made of* (HTML, JS, frameworks, API surface), then analyzes both for **UX**
and **software architecture** and writes Markdown reports plus a single synopsis.

```python
import ov

run = ov.observe("https://example.com")        # capture (zero config)
print(run.fingerprint)                          # detected technologies
print(len(run.artifacts), "artifacts captured")
```

```bash
ov observe https://example.com                  # same, from the shell
ov check                                         # what system deps are present
```

`ov` is a **tool + skill library with a deterministic, model-free core**. The
near-term "agent" that orchestrates it is a *host agent* (Claude Code) following
the skills in `.claude/skills/` — `ov` supplies the hands (drive the target) and
eyes (observe + analyze); the host supplies the control loop. Everything in the
core runs with **no model and no host**, so it's testable, cheap, and repeatable.

## Install

```bash
pip install -e .            # the package
playwright install chromium # the browser it drives (required for capture)
```

The arch/API reconstruction and evidence layers have optional extras
(`pip install -e ".[arch,evidence]"`) and an optional Node sidecar; run
`ov check` (or `ov.check_requirements()`) to see what's present and how to
install what's missing.

## What it captures

Capture is organized into **probes** — independent, registerable units that each
write typed artifacts into a content-addressed store:

- **Behavioral**: `navigation`, `network` (request/response + size-capped bodies),
  `dom` (serialized DOM + ARIA snapshot + full AX tree), `screenshot`, `console`,
  `perf`, `storage`, `websocket`, `sse`.
- **Static**: `fingerprint` (framework/library detection), `assets` (inventory).

The five **operate** primitives — `observe` / `act` / `journal` / `progress` /
`snapshot_state` — are the deterministic, LLM-free "hands" the host (or a scripted
driver) uses to drive a journey; the journey trace *is* the UX evidence.

## The facade

| Function | What it does |
|---|---|
| `ov.observe(url)` | Drive + capture → `CaptureRun` (persisted to a store) |
| `ov.analyze(run)` | Deterministic UX + architecture analyzers → findings *(Phase 2)* |
| `ov.diff(run)` | Own-target regression: diff a run vs a prior baseline → `RunDiff` *(review mode)* |
| `ov.report(run)` | Render Markdown report sections *(Phase 2)* |
| `ov.synopsis(dir)` | Aggregate reports into one synopsis *(Phase 2)* |
| `ov.overview(url)` | The one-liner: observe → analyze → report → synopsis *(Phase 2)* |

The CLI mirrors these: `ov observe|analyze|diff|report|synopsis|overview|check|runs|mcp`.

In `mode="review"` (your own target), `ov.overview(url, mode="review")` inserts a
diff step: it compares the run against the latest prior run of the same target and
reports what is **new**, **changed**, or **resolved** — drift detection for a
downstream creation/modification agent. Artifacts are content-addressed, so this
own-target diffing is cheap by design. The first review run has no baseline and is
a no-op; pass `baseline=<run_id>` to pin a specific prior run.

## In-package agents (optional — `ov[agents]`)

The host-agent path above is the default and the pit of success. When you need a
*self-contained* runtime — a non-Claude-Code host, programmatic use, or process
isolation — `ov.agents` re-hosts the **same** skills + deterministic core as runnable
agents. It is the spec's "mechanical lift" (Phase 4): nothing is rewritten, the lift
is done by [`coact`](https://github.com/thorwhalen/coact) (`COMPLETE` a skill into an
agent definition, `REALIZE` it onto a backend), and `ov.agents` adds only the bits
coact deliberately leaves out — the operator's live-browser loop, the analyst's
multimodal evidence-bundle call, and the orchestration topology (via
[`aw`](https://github.com/thorwhalen/aw)).

```bash
pip install -e ".[agents]"          # coact[sdk,mcp] + aw + py2mcp + fastmcp
```

```python
from ov import agents

# 1. Cheapest: materialize ov's agents as .claude/agents/ so Claude Code runs them
#    (host backend — zero LLM, no fan-out). The host stays the manager.
agents.materialize()

# 2. The cost gate before standing up an in-process fleet (~15× the tokens):
print(agents.estimate(["ux-analyst", "arch-analyst"]).render())

# 3. In-package study (LLM dependency-injected; omit it for a deterministic run):
result = agents.study("https://example.com", llm=my_model)   # -> synopsis + run
```

Each agent reuses Phase 1–3 machinery unchanged and routes by the §10 cost gate
(operator → Haiku, UX-analyst → Sonnet, Arch-analyst / orchestrator → Opus). The
analyst applies the **cite-or-abstain** contract — every LLM claim cites a
mark/fact id or is downgraded to `undetermined`. For a foreign MCP host,
`ov mcp` (or `agents.mcp_server()`) exposes `study_url` / `capture_url` via
[`py2mcp`](https://github.com/i2mint/py2mcp).

## Authorization & privacy

`ov` analyzes *publicly served* frontend material and observable network behavior
of targets you are **authorized** to inspect. Foreign-target runs require an
explicit `authorized=True` acknowledgement; secret/PII capture is off by default
and storage values are redacted. It does not defeat access controls.

## Status

Built in phases (see the GitHub issues). **Phases 1–3** are shipped: the capture
spine + operate primitives, the deterministic UX + architecture analysis +
reports + synopsis, and the host-agent skill layer with the grounded evidence
bundle. **Phase 4** adds the optional in-package agent layer (`ov[agents]`, above)
and **review mode** — own-target diff / regression detection (`ov.diff`,
`ov.overview(url, mode="review")`). Its remaining depth items (source-map /
GraphQL / Lighthouse probes) are deferred to follow-up issues.

---

*Author: Thor Whalen.*
