"""Reliability passes over findings (§5.2, D4) -- deterministic gates, model-free.

These enforce the grounding discipline on findings (whether deterministic, or
authored by the host LLM over an evidence bundle):

* **cite-or-abstain** -- every non-``undetermined`` claim must cite at least one
  *resolvable* evidence ref; otherwise it is downgraded to ``undetermined`` (a
  first-class outcome, not an error).
* **set-of-mark membership** -- any mark id a finding references must exist in the
  bundle.
* **just-in-time retrieval** -- :func:`lookup_evidence` resolves an evidence id
  back to its artifact/finding/step so provenance is verifiable.
* **factored Chain-of-Verification scaffolding** -- :func:`verification_questions`
  generates the questions the *host* answers (independently, via evidence lookup)
  for high-severity findings; :func:`apply_verification` downgrades a finding whose
  verification fails. The judgment is the host's; the gating here is deterministic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..base import CaptureRun, EvidenceBundle, Finding

_MARK_RE = re.compile(r"\bR\d+\b")
_PATTERNED_PREFIXES = ("mark:", "find:", "net:", "metric:", "dom:", "stack:", "trace:")


def resolvable(ref: str, run: CaptureRun, bundle: EvidenceBundle | None = None) -> bool:
    """True if an evidence ref resolves to something concrete (artifact/finding/step/bundle)."""
    if not ref:
        return False
    if any(a.artifact_id == ref for a in run.artifacts):
        return True
    if any(s.id == ref for s in run.steps):
        return True
    if any(f.finding_id == ref for f in run.findings):
        return True
    if bundle is not None and (ref in bundle.marks.values()
                               or any(e.evidence_id == ref for e in bundle.facts)):
        return True
    return ref.startswith(_PATTERNED_PREFIXES)


def lookup_evidence(evidence_id: str, run: CaptureRun, store: Any) -> dict[str, Any]:
    """Resolve an evidence id back to its underlying data (just-in-time retrieval).

    Returns a dict describing what the id points at, so a verification pass (or a
    downstream agent) can confirm a finding against the original artifact/record.
    """
    for a in run.artifacts:
        if a.artifact_id == evidence_id:
            return {"kind": "artifact", "artifact": a.model_dump(mode="json")}
    for f in run.findings:
        if f.finding_id == evidence_id or evidence_id == f"find:{f.finding_id}":
            return {"kind": "finding", "finding": f.model_dump(mode="json")}
    for s in run.steps:
        if s.id == evidence_id:
            return {"kind": "step", "step": s.model_dump(mode="json")}
    return {"kind": "unresolved", "id": evidence_id}


@dataclass
class ReliabilityReport:
    """Outcome of :func:`verify_findings`."""

    kept: list[Finding] = field(default_factory=list)
    downgraded: list[Finding] = field(default_factory=list)  # -> undetermined
    notes: list[str] = field(default_factory=list)

    @property
    def all_findings(self) -> list[Finding]:
        """Kept + downgraded, in that order (nothing is silently dropped)."""
        return [*self.kept, *self.downgraded]


def _downgrade(f: Finding, reason: str) -> Finding:
    f.type = "undetermined"
    f.needs_human_review = True
    f.judgment = ((f.judgment + " ") if f.judgment else "") + f"[downgraded: {reason}]"
    return f


def verify_findings(
    findings: list[Finding],
    run: CaptureRun,
    *,
    bundle: EvidenceBundle | None = None,
) -> ReliabilityReport:
    """Apply cite-or-abstain + mark-membership; downgrade unsupported findings.

    Deterministic findings (``source_layer == "deterministic"``) are facts and are
    kept; LLM findings must cite resolvable evidence and reference only existing
    marks. A finding that fails is downgraded to ``undetermined`` (kept, flagged),
    never silently dropped.

    Note: downgrading mutates the offending :class:`Finding` in place (the caller
    hands its findings in to be gated), so the objects in ``report.downgraded`` are
    the same instances, now marked ``undetermined`` + ``needs_human_review``.
    """
    report = ReliabilityReport()
    for f in findings:
        if f.type == "undetermined":
            report.kept.append(f)
            continue
        if f.source_layer == "deterministic":
            report.kept.append(f)
            continue
        # LLM finding: cite-or-abstain
        resolvable_refs = [r for r in f.evidence_refs if resolvable(r, run, bundle)]
        if not resolvable_refs:
            report.downgraded.append(_downgrade(f, "no resolvable evidence (cite-or-abstain)"))
            continue
        # set-of-mark membership: any RN it mentions must exist in the bundle
        if bundle is not None:
            mentioned = set(_MARK_RE.findall(f.judgment or "")) | {
                m for r in f.evidence_refs for m in _MARK_RE.findall(r)
            }
            unknown = mentioned - set(bundle.marks)
            if unknown:
                report.downgraded.append(_downgrade(f, f"references unknown marks {sorted(unknown)}"))
                continue
        report.kept.append(f)
    report.notes.append(f"verified {len(findings)}: kept {len(report.kept)}, downgraded {len(report.downgraded)}")
    return report


def verification_questions(finding: Finding) -> list[str]:
    """Generate factored Chain-of-Verification questions for a high-severity finding.

    The host answers each *independently* (via :func:`lookup_evidence`), not
    conditioned on the original claim -- that's what makes CoVe factored.

    >>> from ov.base import Finding
    >>> qs = verification_questions(Finding(type="ux_issue", signal="contrast.text",
    ...     category="a11y", observed="contrast 2.1:1", evidence_refs=["art_1"]))
    >>> len(qs) >= 2
    True
    """
    qs = [
        f"Does evidence {finding.evidence_refs or '(none)'} actually show: {finding.observed!r}?",
        f"Is the signal '{finding.signal}' the correct classification for that evidence?",
    ]
    if finding.severity:
        qs.append(f"Does the evidence justify severity score {finding.severity.score}?")
    return qs


def apply_verification(finding: Finding, verdicts: list[bool]) -> Finding:
    """Downgrade a finding to ``undetermined`` if a majority of verifications fail.

    ``verdicts`` are the host's independent answers (True = supported). This is the
    deterministic application of the host's factored CoVe / NLI judgments.
    """
    if verdicts and sum(verdicts) < (len(verdicts) / 2):
        return _downgrade(finding, "failed chain-of-verification")
    return finding
