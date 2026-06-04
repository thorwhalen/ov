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
| `ov.report(run)` | Render Markdown report sections *(Phase 2)* |
| `ov.synopsis(dir)` | Aggregate reports into one synopsis *(Phase 2)* |
| `ov.overview(url)` | The one-liner: observe → analyze → report → synopsis *(Phase 2)* |

The CLI mirrors these: `ov observe|analyze|report|synopsis|overview|check|runs`.

## Authorization & privacy

`ov` analyzes *publicly served* frontend material and observable network behavior
of targets you are **authorized** to inspect. Foreign-target runs require an
explicit `authorized=True` acknowledgement; secret/PII capture is off by default
and storage values are redacted. It does not defeat access controls.

## Status

Built in phases (see the GitHub issues). **Phase 1** (capture spine + operate
primitives) is implemented; Phases 2–3 (deterministic analysis + reports, then
the host-agent skill layer) follow. In-package agents are an optional, deferred
Phase 4.

---

*Author: Thor Whalen.*
