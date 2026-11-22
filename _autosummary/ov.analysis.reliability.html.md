# ov.analysis.reliability

Reliability passes over findings (§5.2, D4) – deterministic gates, model-free.

These enforce the grounding discipline on findings (whether deterministic, or
authored by the host LLM over an evidence bundle):

* **cite-or-abstain** – every non-`undetermined` claim must cite at least one
  *resolvable* evidence ref; otherwise it is downgraded to `undetermined` (a
  first-class outcome, not an error).
* **set-of-mark membership** – any mark id a finding references must exist in the
  bundle.
* **just-in-time retrieval** – [`lookup_evidence()`](#ov.analysis.reliability.lookup_evidence) resolves an evidence id
  back to its artifact/finding/step so provenance is verifiable.
* **factored Chain-of-Verification scaffolding** – [`verification_questions()`](#ov.analysis.reliability.verification_questions)
  generates the questions the *host* answers (independently, via evidence lookup)
  for high-severity findings; [`apply_verification()`](#ov.analysis.reliability.apply_verification) downgrades a finding whose
  verification fails. The judgment is the host’s; the gating here is deterministic.

### Functions

| [`apply_verification`](#ov.analysis.reliability.apply_verification)(finding, verdicts)        | Downgrade a finding to `undetermined` if a majority of verifications fail.             |
|-----------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| [`lookup_evidence`](#ov.analysis.reliability.lookup_evidence)(evidence_id, run, store)     | Resolve an evidence id back to its underlying data (just-in-time retrieval).           |
| [`resolvable`](#ov.analysis.reliability.resolvable)(ref, run[, bundle])               | True if an evidence ref resolves to something concrete (artifact/finding/step/bundle). |
| [`verification_questions`](#ov.analysis.reliability.verification_questions)(finding)              | Generate factored Chain-of-Verification questions for a high-severity finding.         |
| [`verify_findings`](#ov.analysis.reliability.verify_findings)(findings, run, \*[, bundle]) | Apply cite-or-abstain + mark-membership; downgrade unsupported findings.               |

### Classes

| [`ReliabilityReport`](#ov.analysis.reliability.ReliabilityReport)([kept, downgraded, notes])   | Outcome of [`verify_findings()`](#ov.analysis.reliability.verify_findings).   |
|-------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|

### *class* ov.analysis.reliability.ReliabilityReport(kept=list(), downgraded=list(), notes=list())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Outcome of [`verify_findings()`](#ov.analysis.reliability.verify_findings).

#### *property* all_findings *: [list](https://docs.python.org/3/builtins/stdtypes.html#list)[[Finding](ov.base.html.md#ov.base.Finding)]*

Kept + downgraded, in that order (nothing is silently dropped).

### ov.analysis.reliability.apply_verification(finding, verdicts)

Downgrade a finding to `undetermined` if a majority of verifications fail.

`verdicts` are the host’s independent answers (True = supported). This is the
deterministic application of the host’s factored CoVe / NLI judgments.

* **Return type:**
  [`Finding`](ov.base.html.md#ov.base.Finding)

### ov.analysis.reliability.lookup_evidence(evidence_id, run, store)

Resolve an evidence id back to its underlying data (just-in-time retrieval).

Returns a dict describing what the id points at, so a verification pass (or a
downstream agent) can confirm a finding against the original artifact/record.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

### ov.analysis.reliability.resolvable(ref, run, bundle=None)

True if an evidence ref resolves to something concrete (artifact/finding/step/bundle).

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### ov.analysis.reliability.verification_questions(finding)

Generate factored Chain-of-Verification questions for a high-severity finding.

The host answers each *independently* (via [`lookup_evidence()`](#ov.analysis.reliability.lookup_evidence)), not
conditioned on the original claim – that’s what makes CoVe factored.

```pycon
>>> from ov.base import Finding
>>> qs = verification_questions(Finding(type="ux_issue", signal="contrast.text",
...     category="a11y", observed="contrast 2.1:1", evidence_refs=["art_1"]))
>>> len(qs) >= 2
True
```

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### ov.analysis.reliability.verify_findings(findings, run, , bundle=None)

Apply cite-or-abstain + mark-membership; downgrade unsupported findings.

Deterministic findings (`source_layer == "deterministic"`) are facts and are
kept; LLM findings must cite resolvable evidence and reference only existing
marks. A finding that fails is downgraded to `undetermined` (kept, flagged),
never silently dropped.

#### NOTE
downgrading mutates the offending `Finding` in place (the caller
hands its findings in to be gated), so the objects in `report.downgraded` are
the same instances, now marked `undetermined` + `needs_human_review`.

* **Return type:**
  [`ReliabilityReport`](#ov.analysis.reliability.ReliabilityReport)
