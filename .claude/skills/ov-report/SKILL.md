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
paths = ov.report(run, out_dir="out/")     # writes section .md files; returns paths
```
Default sections (by mode): `00_overview`, `10_ux_analysis`, `20_architecture`,
`30_api_surface`, then `40_reconstruction_blueprint` (reconstruct) **or**
`40_review_audit` (review), then `90_appendix`. Pass `sections=[...]` to select a
subset. Without `out_dir`, sections are written to the store under the run id.

## Build the synopsis (the deliverable for a downstream agent)
```python
md_path = ov.synopsis(run, out="out/")     # writes synopsis.json + SYNOPSIS.md
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

## One-liner
```python
ov.overview("https://target", out_dir="out/")   # observe -> analyze -> report -> synopsis
```
runs the whole deterministic pipeline and returns the synopsis path. From the
shell: `ov overview https://target`.

## What to tell the user in the write-up
- Lead with the synopsis histogram and the top severity-ranked findings.
- Separate **deterministic** findings (facts) from **needs_human_review** ones (the
  non-automatable a11y/UX tail) — never present the latter as resolved.
- For reconstruct mode, frame the architecture section as a rebuild blueprint;
  mark map-backed claims as higher-confidence than name-lost ones.
- Markdown deliverables are authored as "Thor Whalen" (standing preference).
