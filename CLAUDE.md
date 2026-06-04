# CLAUDE.md — orientation for agents working in `ov`

`ov` (OverView) drives a web app, captures behavioral + static streams, and
analyzes them for UX and software architecture. The authoritative design is
`misc/docs/ov_specification.md` (read it before non-trivial work). Four research
reports (`misc/docs/ov_dr_0{1..4}*.md`) back the key decisions.

## The one architectural idea to hold onto

**The host is the manager.** `ov` is a deterministic, model-free *tool + skill*
library. The near-term agent that plans, decides, and recovers is the **host
agent (Claude Code) following `.claude/skills/`**, not code in this package. So:

- Every capability is a clean, individually-callable, **tool-shaped** function
  with a typed (Pydantic) return and an agent-legible docstring.
- The deterministic core (capture, analyzers, evidence assembler, synopsis) runs
  with **no model and no host** — that's what keeps it testable and cheap.
- In-package agents (`ov/agents/`) are an **optional, deferred Phase 4**. Do not
  build them unless that productization is the explicit goal. If you reach for an
  orchestrator/LLM-loop in Phases 1–3, stop — that belongs in a skill.

## Layering (and the seam that makes it testable)

```
capture/   → drives a browser, writes plain-data ARTIFACTS to the store  (needs a browser)
operate/   → the model-free "hands": observe / act / journal / progress  (needs a page)
analysis/  → PURE functions over captured artifacts → Findings/Endpoints (no browser, no model)
reporting/ → registered Markdown sections + the synopsis map-reduce
```

> **Naming**: the subpackages are `analysis/` and `reporting/` (not the spec's
> `analyze/`/`report/`). The spec names *both* a facade function `ov.analyze()` /
> `ov.report()` AND a subpackage with the same name — a Python attribute
> collision (a subpackage import shadows the function). The public API
> (`ov.analyze`/`ov.report`/`ov.overview` + the CLI) is preserved; only the
> internal package names changed. `overview`'s impl lives in `reporting/overview.py`.

The hard seam is **capture → artifacts → analyze**: analyzers never touch a
browser, only stored artifacts. That's why the deterministic core is unit-tested
with synthetic artifacts and the real-browser tests are *gated* (skip when
Chromium isn't launchable). Keep this seam intact.

## SSOT & plugins

- `ov/base.py` is the single source of truth (Pydantic v2). Everything reads from
  it; don't invent parallel shapes.
- Three registries (`ov/registry.py` + each package's `__init__`): `PROBE_REGISTRY`,
  `ANALYZER_REGISTRY`, `REPORT_SECTION_REGISTRY`. Adding a capability = registering
  a decorated function with `requires`/`produces` deps. Never edit a dispatcher.
- Stores are `dol`-backed `MutableMapping`s; artifacts are **content-addressed**
  (identical bytes dedupe across runs → cheap own-target diffing).

## Conventions specific to this repo

- **Every module needs a top-level docstring** (ruff `D100` is enabled; CI fails
  without it).
- Probes/analyzers/sections are functions-as-data; helpers used once are inner
  functions, module-private helpers get a `_` prefix, cross-module reusable ones
  don't.
- Fingerprinting is a **built-in license-clean detector**, *not* `wappalyzer-next`
  (GPL-3.0, incompatible with MIT). Heavy Node tools (Retire.js, webcrack) are
  optional, surfaced via `check_requirements`.
- Playwright is a **facade over a CDP escape hatch** (`capture/cdp.py`,
  Chromium-only) — callers never touch raw Playwright objects.

## Build status / phases

Tracked in GitHub issues (one per phase). Phase 1 = capture spine + operate
primitives. Phase 2 = deterministic analysis + reports + Node sidecar. Phase 3 =
host-agent skills + evidence bundle + reliability passes. Phase 4 (deferred) =
in-package agents + depth + review-mode diffing.

## Running things

```bash
pip install -e ".[arch,evidence,dev]" && playwright install chromium
python -m pytest -q                 # deterministic tests always run; browser tests skip if absent
python -m pytest --doctest-modules ov -q
python -m ruff check ov
ov check                            # system dependency report
```
