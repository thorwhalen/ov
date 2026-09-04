---
name: study-web-app
description: >-
  Study, audit, reverse-engineer, or review a web app or website end-to-end with the
  `ov` tool. Use whenever the user says things like "go study this app", "audit this
  site's UX", "reconstruct this frontend", "what's this site built with", "review our
  web app", "analyze the accessibility of this page", or hands you a URL to investigate.
  You (the host agent) are the manager: you plan the journey, call ov's deterministic
  tools, reason over the grounded evidence, and assemble the report. ov supplies the
  hands (drive) and eyes (observe + analyze); you supply the control loop.
coact:
  model: opus
  tools: [Bash, Read, Grep, Glob]
  memory: project
  mcp:
    - module: ov.agents.mcp
      functions: [study_url]
  returns:
    json_schema:
      type: object
      properties:
        synopsis_path: { type: string }
        findings_count: { type: integer }
        report_paths: { type: array, items: { type: string } }
      required: [synopsis_path]
    description: >-
      The deduplicated synopsis (path + counts) plus rendered report paths, for a
      downstream creation/modification agent. Pure coordinator — plans + delegates
      to the operator and analyst agents, never analyzes (Opus-routed, §10).
---

# Study a web app with `ov`

`ov` (OverView) drives a web app like a user and records two streams — the
**behavioral** stream (pages, DOM, screenshots, network, console, journey) and the
**static** stream (HTML, JS, frameworks, API surface) — then runs deterministic UX
and architecture analyzers and renders Markdown reports plus a single synopsis.

**You are the manager.** The package is a deterministic, model-free tool library;
the planning, decision-making, recovery, and narrative judgment are yours. This
skill is your policy. It points to focused sub-skills — load each when you reach
its step.

## The workflow

### 0. Confirm authorization and mode (do this first)
- **Authorization.** `ov` analyzes publicly-served frontend material of targets the
  user is authorized to inspect. For a *foreign* target (not the user's own), confirm
  the user is authorized, then pass `authorized=True`. Never defeat access controls,
  bruteforce, or rate-abuse.
- **Mode.** Pick `mode="reconstruct"` for a foreign target (goal: rebuild-grade
  intelligence) or `mode="review"` for the user's own app (goal: critique + drift).
  The machinery is identical; only the framing and baseline differ.

### 1. Capture — load **`ov-capture`**
Run a capture session. The zero-config path:
```python
import ov

run = ov.observe("https://target", mode="reconstruct", authorized=True)
```
Decide which probes you need (default is a good baseline; add `probes="all"` for
perf/storage/websocket/sse). See `ov-capture` for the probe catalog and how to
inspect the store.

### 2. Drive a journey — load **`ov-operate`**
A single page load is rarely enough. Decide a strategy:
- **crawl-and-map** (breadth) — enumerate the site; good for reconstruct.
- **goal-pursuit** (depth) — drive toward a success state (signup, checkout); this
  is *your* loop using the operate primitives, since it needs goal-relative judgment.
- **guided-replay** — execute a known script.

Deliberately drive into **empty / error / loading states** (invalid form input,
bad route, filtered-to-zero) — microcopy and recovery bugs hide there.

**Manager discipline (this is the part that would otherwise be agent code):**
- Bound the run: respect `max_steps`, `max_failures`, and a wall-clock budget.
- After each step call `progress(history)` — it returns *facts* (loop suspected,
  no-progress count). **The package never decides to stop; you do.** Abort on
  `loop_suspected`.
- Recover from a failed `ActionResult`: stale ref → re-observe; not-found →
  scroll/disambiguate; auth wall → pause and ask the user.
- Don't assume the agent "usually succeeds" — instrument every step; the journey
  trace is evidence regardless of task success.

### 3. Analyze (deterministic) — load **`ov-analyze-ux`** and **`ov-analyze-arch`**
```python
ov.analyze(run)  # runs the UX + arch analyzers, fully model-free
```
This populates `run.findings`, `run.api_surface`, `run.fingerprint`,
`run.rendering_model`, `run.source_maps_present`. This deterministic layer is the
**source of truth**.

### 4. Add judgment (you, grounded)
Build the evidence bundle and reason over it to add the genuinely subjective items
(alt-text *meaningfulness*, error-message *helpfulness*, label↔intent match,
design intent). The bundle is set-of-mark grounded with a computed token budget:
```python
from ov.analysis.evidence import build_evidence_bundle

bundle = build_evidence_bundle(
    run, store
)  # marked image + facts + cite-or-abstain contract
```
**Grounding rules (non-negotiable):**
- Cite-or-abstain: every claim cites a fact/mark id; if the evidence doesn't
  support it, output `type="undetermined"` — don't guess.
- Discuss only marked regions; never scan the image for new issues.
- Never assert a fact field — you cite the deterministic facts, you don't author them.
Then gate your findings:
```python
from ov.analysis.reliability import verify_findings

report = verify_findings(
    your_findings, run, bundle=bundle
)  # downgrades unsupported -> undetermined
```

### 5. Report + synopsis — load **`ov-report`**
```python
ov.report(run, out_dir="out/")  # Markdown sections
ov.synopsis(run, out="out/")  # synopsis.json (SSOT) + derived SYNOPSIS.md
```
Or the whole deterministic pipeline in one call: `ov.overview(url, out_dir="out/")`.

**Review mode (own target):** add an own-target diff to detect drift/regression
against a stored prior run before reporting:
```python
ov.diff(run)  # sets Finding.diff_status; persists a diff blob
```
The `40_review_audit` section and the synopsis then carry a regression block
(new/changed/resolved + stack/API drift). `ov.overview(url, mode="review")` runs
this automatically. The first review run has no baseline (no-op); from then on it
diffs against the latest prior run of the same target.

## Honesty constraints (state these in the report)
- Automated accessibility tooling catches only ~30–40% of WCAG issues. Never report
  "no automated violations" as "accessible"; the `needs_human_review` findings are
  the non-automatable majority and must be surfaced as such.
- Every inferred technology/endpoint/rendering fact is probabilistic — carry its
  confidence; map-backed reconstructions rank above name-lost ones.

## When something blocks you
Auth walls, captchas, payment steps, or destructive actions → pause and ask the
user. 2–3 failed tool attempts on the same thing → stop and report what you tried.
