---
name: ov-analyze-ux
description: >-
  How to run ov's deterministic UX + accessibility analyzers, assemble a grounded
  evidence bundle, and add narrative UX judgment as the host. Load this for the UX
  lens: accessibility audit, contrast, Core Web Vitals, form friction, Nielsen
  heuristics, and severity-ranked usability findings with fixes.
coact:
  model: sonnet
  tools: [Read, Grep, Glob]
  memory: project
  consumes: evidence_bundle
  returns:
    schema_ref: ov.base:Finding
    description: >-
      Severity-ranked UX / a11y findings (a list of ov.base:Finding,
      source_layer="llm") grounded in the evidence bundle under the cite-or-abstain
      contract — every claim cites a mark/fact id or is downgraded to undetermined.
---

# UX & accessibility analysis

Two layers in strict order: a **deterministic engine** (the source of truth) and
then **your grounded judgment** for the subjective parts. The model never *detects*
facts — it interprets the evidence bundle.

## 1. Run the deterministic engine
```python
import ov
ov.analyze(run, lenses=("ux",))   # or ("ux","arch") for both
```
This emits normalized `Finding`s into `run.findings`. The analyzers:
- **a11y** — WebAIM perennials from the DOM (missing alt, empty link/button,
  unlabeled control, missing lang) + axe-core results if captured.
- **contrast_focus** — WCAG contrast ratios from computed styles (4.5:1 / 3:1);
  positive-tabindex; behavioral focus → human review.
- **cwv** — INP (200ms), CLS (0.1), LCP (2500ms, initial-load/provisional), TTFB.
- **journey_metrics** — form friction (the 5–7 field conversion cliff), backtracking.
- **heuristics** — console-error-on-step, missing-feedback (intentful noop click),
  live-region absence. Your operator's per-step *intent* is the cognitive-walkthrough
  ground truth for "expected action".

Each `Finding` carries `severity = impact_tier × reach` (high-reach beats
rare-critical), a WCAG/heuristic mapping, and `source_layer="deterministic"`.

## 2. The honesty constraint (must surface)
Automated tooling catches only ~30–40% of WCAG issues. The analyzers always emit
`needs_human_review` findings for the non-automatable majority — meaningful alt
text, reading/focus-order *logicality*, in-context link text, screen-reader
announcement quality, ARIA *intent*. **Never** report "no automated violations" as
"accessible". Present these as routed-to-human, not as resolved.

## 3. Add your judgment (grounded)
For the genuinely subjective items (alt-text *meaningfulness*, error-message
*helpfulness*, label↔intent match, microcopy/empty-state quality, focus-order
logicality), reason over the evidence bundle:
```python
from ov.analysis.evidence import build_evidence_bundle
bundle = build_evidence_bundle(run, store)   # marked screenshot + facts + token budget
```
Then, per the cite-or-abstain contract in `bundle.contract`:
- Discuss only marked regions (R1, R2, …); never scan for new issues.
- Every claim cites a fact/mark id; unsupported → `type="undetermined"`.
- Use Nielsen's 10 heuristics with 0–4 severity (review mode = "fix"; reconstruct
  mode = "catalog the interaction pattern, note preserve-vs-improve").

## 4. Gate your findings
```python
from ov.analysis.reliability import verify_findings, verification_questions, apply_verification
report = verify_findings(my_findings, run, bundle=bundle)  # cite-or-abstain + mark membership
# for high-severity findings, run a factored check:
for f in high_severity:
    answers = [self_answer(q) for q in verification_questions(f)]  # answer each independently
    apply_verification(f, answers)                                  # downgrades if it fails
```
`verify_findings` keeps deterministic findings, keeps grounded LLM findings, and
downgrades unsupported ones to `undetermined` (never silently dropped).

## Output shape
Findings are the `Finding` schema (severity, evidence_refs, judgment, location,
needs_human_review, source_layer). Keep facts (`observed`, `metric_detail`) and
judgment separate — you cite facts, you never author them.
