---
name: ov-report
description: >-
  How to render ov's Markdown report sections and produce the single agent-consumable
  synopsis. Load this for the final step of study-web-app — turning analyzed findings
  into reports and a deduplicated synopsis.json + SYNOPSIS.md.
---

# Rendering reports + the synopsis

The reporting layer is deterministic: it renders the analyzed run into Markdown
sections and compresses the findings into one synopsis.

## Render the section reports
```python
import ov

paths = ov.report(run, out_dir="out/")  # writes section .md files; returns paths
```
Default sections (by mode): `00_overview`, `10_ux_analysis`, `20_architecture`,
`30_api_surface`, then `40_reconstruction_blueprint` (reconstruct) **or**
`40_review_audit` (review), then `90_appendix`. Pass `sections=[...]` to select a
subset. Without `out_dir`, sections are written to the store under the run id.

## Build the synopsis (the deliverable for a downstream agent)
```python
md_path = ov.synopsis(run, out="out/")  # writes synopsis.json + SYNOPSIS.md
```
The synopsis is a **structured map-reduce** over `run.findings`:
- Each finding maps to a compact record.
- Findings are **deduplicated deterministically** — clustered on
  `(type, evidence-ref overlap, normalized summary)` and merged into one record
  holding the union of evidence refs and the max severity. (Evidence-id overlap is
  model-free and beats LLM similarity-judging.)
- `synopsis.json` is the SSOT; `SYNOPSIS.md` is **derived** from it — never
  hand-author the Markdown. It carries run metadata, target (foreign/own), the
  findings array, and a rolled-up severity histogram.
- Every synopsis finding resolves back (via `ov.analysis.reliability.lookup_evidence`)
  to the artifact/record it cites — so a downstream creation/modification agent can
  act on and *verify* a finding.

## Review mode — own-target diff / regression
For the user's *own* app (`mode="review"`), add a diff against a stored prior run
of the same target. It's deterministic (no model) and cheap (artifacts are
content-addressed):
```python
diff = ov.diff(run)  # vs the latest prior run of this target
diff = ov.diff(run, baseline=prior_run_id)  # or pin a specific baseline
```
`ov.diff` returns a `RunDiff` (or `None` on the first run — no baseline yet). It:
- sets `Finding.diff_status` (`new` / `changed` / `resolved`) on the run in place;
- persists a `diff_<run_id>` blob the report + synopsis read automatically;
- rolls each delta into a **direction** (`regression` / `improvement` / `neutral`)
  so `diff.regressions` is the fix-list for a downstream modification agent.

When a diff exists, the `40_review_audit` section gains a **"Drift vs. prior run"**
block (new/changed/resolved tables + tech/API/rendering drift) and the synopsis
gains a **"Regression vs baseline"** block (regressions, improvements, drift).
`ov.overview(url, mode="review")` runs this diff step automatically between analyze
and report. From the shell: `ov diff <run_id>` or `ov overview <url> --mode review`.

## One-liner
```python
ov.overview(
    "https://target", out_dir="out/"
)  # observe -> analyze -> report -> synopsis
```
runs the whole deterministic pipeline and returns the synopsis path. From the
shell: `ov overview https://target`. In review mode it becomes
observe → analyze → **diff** → report → synopsis.

## What to tell the user in the write-up
- Lead with the synopsis histogram and the top severity-ranked findings.
- Separate **deterministic** findings (facts) from **needs_human_review** ones (the
  non-automatable a11y/UX tail) — never present the latter as resolved.
- For reconstruct mode, frame the architecture section as a rebuild blueprint;
  mark map-backed claims as higher-confidence than name-lost ones.
- Markdown deliverables are authored as "Thor Whalen" (standing preference).
