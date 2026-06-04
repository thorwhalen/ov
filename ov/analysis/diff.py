"""Own-target diffing: a run vs a stored prior baseline run (review mode, §10).

Review mode's distinguishing capability is *regression/drift detection*: compare
an analyzed :class:`~ov.base.CaptureRun` against a stored prior run of the same
target and report what is **new**, **changed**, or **resolved**. Because
artifacts are content-addressed (identical bytes dedupe across runs), this
comparison is cheap by design (spec §3.4).

The matching unit is the :class:`~ov.base.Finding`. Finding ids are regenerated
every run, so cross-run identity is derived from *stable semantic fields*
(:func:`finding_key`) -- category, signal, engine/heuristic/WCAG identifiers, and
a stable locator -- explicitly excluding per-run ids (``finding_id``, ``step_id``,
``state_id``) that would make every finding look brand new.

Two entry points:

* :func:`diff_runs` -- **pure**: compare two in-memory runs, annotate the current
  run's ``Finding.diff_status`` in place, and return a :class:`~ov.base.RunDiff`.
* :func:`build_diff` -- **store-aware**: resolve a baseline (explicit id/run or
  the latest prior run of the same target via :func:`find_baseline_run`), run
  :func:`diff_runs`, and persist both the annotated run and a ``diff_<run_id>``
  analysis blob so the review report section + the synopsis can read it.
"""

from __future__ import annotations

from typing import Any

from ..base import CaptureRun, Finding, FindingDelta, RunDiff
from ..capture.stores import resolve_store
from ..util import content_hash

# Structural locators that pin a finding to a stable element/route across runs.
# Per-run ids (``step_id``/``state_id``) are deliberately excluded -- including
# them would make every finding look new. ``intent`` is behavioral, not
# structural, so it is a weak fallback only (see ``_content_discriminator``).
_STRUCTURAL_LOCATORS = ("selector", "url_or_route", "route", "form")


def _content_discriminator(finding: Finding, loc: dict) -> str:
    """A *stable* per-finding discriminator for locator-less, multi-instance signals.

    Some analyzers emit many findings under one signal with no structural locator
    -- e.g. one ``deps.known-vulnerability`` per vulnerable library, or one
    ``heuristic.console-error`` per error message. Without a discriminator they
    all collapse to one key and the diff silently under-reports new/resolved
    deltas. We fold in the most stable identifying content available, preferring
    fields that survive re-capture (a library *name*) over volatile ones (a
    version string): ``metric_detail['component']`` → ``observed`` → ``intent`` →
    ``title``. Used only when no structural locator is present, so it never
    destabilizes well-located findings (whose ``observed`` may carry drifting
    numbers like a contrast ratio).
    """
    md = finding.metric_detail or {}
    if md.get("component"):
        return f"c:{md['component']}"
    if finding.observed:
        return f"o:{content_hash(finding.observed, length=12)}"
    if loc.get("intent"):
        return f"i:{loc['intent']}"
    if finding.title:
        return f"t:{content_hash(finding.title, length=12)}"
    return ""


def finding_key(finding: Finding) -> str:
    """Return a stable cross-run identity for a finding (pure, model-free).

    Built from semantic fields that survive re-capture -- category, signal, any
    engine/heuristic/WCAG rule id, a structural locator, and (only when no
    structural locator pins identity) a stable content discriminator. Never from
    per-run ids. Two findings describing the same issue in two runs share a key;
    two *distinct* findings of the same locator-less signal do not collapse.

    >>> from ov.base import Finding
    >>> a = Finding(type="ux_issue", signal="contrast.text", category="a11y",
    ...             location={"selector": ".btn", "step_id": "step_aaa"})
    >>> b = Finding(type="ux_issue", signal="contrast.text", category="a11y",
    ...             location={"selector": ".btn", "step_id": "step_zzz"})
    >>> finding_key(a) == finding_key(b)   # step_id differs but identity holds
    True
    >>> v1 = Finding(type="risk", signal="deps.known-vulnerability",
    ...              category="robustness", metric_detail={"component": "lodash"})
    >>> v2 = Finding(type="risk", signal="deps.known-vulnerability",
    ...              category="robustness", metric_detail={"component": "jquery"})
    >>> finding_key(v1) == finding_key(v2)   # distinct libraries -> distinct keys
    False
    """
    loc = finding.location or {}
    parts = [finding.category, finding.signal]
    if finding.engine_rule_id:
        parts.append(finding.engine_rule_id)
    if finding.heuristic:
        parts.append(finding.heuristic)
    if finding.wcag_criterion and finding.wcag_criterion.get("id"):
        parts.append(f"wcag:{finding.wcag_criterion['id']}")
    locator = next((str(loc[k]) for k in _STRUCTURAL_LOCATORS if loc.get(k)), "")
    if not locator and loc.get("targets"):
        locator = "|".join(str(t) for t in loc["targets"])
    parts.append(locator)
    if not locator:  # disambiguate locator-less, multi-instance signals
        disc = _content_discriminator(finding, loc)
        if disc:
            parts.append(disc)
    return "::".join(parts)


def _colliding_signals(findings: list[Finding]) -> list[str]:
    """Signals whose findings share a :func:`finding_key` within one run (ambiguous)."""
    by_key: dict[str, list[Finding]] = {}
    for f in findings:
        by_key.setdefault(finding_key(f), []).append(f)
    return sorted(
        {f.signal for group in by_key.values() if len(group) > 1 for f in group}
    )


def _severity_score(f: Finding) -> float | None:
    return f.severity.score if f.severity else None


def _severity_tier(f: Finding) -> str | None:
    return f.severity.impact_tier if f.severity else None


def _change_signature(f: Finding) -> tuple[Any, ...]:
    """The tuple whose inequality across runs defines a ``changed`` finding."""
    return (_severity_score(f), _severity_tier(f), f.observed, f.confidence)


def _change_detail(cur: Finding, base: Finding) -> str | None:
    """A short human-legible note on *what* changed between two matched findings."""
    bits: list[str] = []
    cs, bs = _severity_score(cur), _severity_score(base)
    if cs != bs:
        bits.append(f"severity {bs}→{cs}")
    ct, bt = _severity_tier(cur), _severity_tier(base)
    if ct != bt:
        bits.append(f"tier {bt}→{ct}")
    if cur.observed != base.observed:
        bits.append("observed signal changed")
    if cur.confidence != base.confidence:
        bits.append(f"confidence {base.confidence}→{cur.confidence}")
    return "; ".join(bits) or None


def _direction(status: str, cur_score: float | None, base_score: float | None) -> str:
    """Roll a per-finding status into regression/improvement/neutral.

    A resolved finding is an improvement; a new finding that carries severity is a
    regression; a changed finding follows its severity delta. Severity-less
    findings (e.g. ``undetermined`` manual-review items) stay neutral.
    """
    if status == "resolved":
        return "improvement"
    if status == "new":
        return "regression" if (cur_score or 0) > 0 else "neutral"
    if status == "changed":
        cur, base = cur_score or 0.0, base_score or 0.0
        if cur > base:
            return "regression"
        if cur < base:
            return "improvement"
    return "neutral"


def _delta_for(f: Finding, status: str, base: Finding | None) -> FindingDelta:
    """Build the :class:`FindingDelta` for a current finding (new/changed/unchanged)."""
    cs = _severity_score(f)
    bs = _severity_score(base) if base else None
    detail = (
        "not present in baseline"
        if status == "new"
        else _change_detail(f, base)
        if (status == "changed" and base)
        else None
    )
    return FindingDelta(
        key=finding_key(f),
        status=status,  # type: ignore[arg-type]
        direction=_direction(status, cs, bs),  # type: ignore[arg-type]
        signal=f.signal,
        category=f.category,
        title=f.title or f.observed,
        finding_id=f.finding_id,
        baseline_finding_id=base.finding_id if base else None,
        severity_score=cs,
        baseline_severity_score=bs,
        severity_tier=_severity_tier(f),
        detail=detail,
    )


def diff_runs(current: CaptureRun, baseline: CaptureRun) -> RunDiff:
    """Compare two analyzed runs; annotate ``current`` in place; return the diff.

    Side effect (by design, per issue #14): each ``current`` finding's
    ``diff_status`` is set to ``"new"``/``"changed"`` or cleared to ``None`` for
    unchanged ones. Resolved findings live only in the returned
    :class:`~ov.base.RunDiff` (they are absent from ``current``). The function is
    otherwise pure -- no store, no browser, no model.

    >>> from ov.base import CaptureRun, Finding, Severity
    >>> mk = lambda sig, sc: Finding(type="ux_issue", signal=sig, category="ux",
    ...     title=sig, location={"selector": "#" + sig},
    ...     severity=Severity(impact_tier="serious", score=sc))
    >>> base = CaptureRun(target_url="u", findings=[mk("a", 2.0), mk("b", 3.0)])
    >>> cur = CaptureRun(target_url="u", findings=[mk("a", 5.0), mk("c", 1.0)])
    >>> d = diff_runs(cur, base)
    >>> d.counts
    {'new': 1, 'changed': 1, 'resolved': 1, 'unchanged': 0}
    >>> cur.findings[0].diff_status, cur.findings[1].diff_status
    ('changed', 'new')
    >>> sorted(r.key.split("::")[1] for r in d.regressions)
    ['a', 'c']
    """
    base_by_key: dict[str, Finding] = {}
    for f in baseline.findings:
        base_by_key.setdefault(finding_key(f), f)

    deltas: list[FindingDelta] = []
    seen: set[str] = set()
    for f in current.findings:
        key = finding_key(f)
        seen.add(key)
        base = base_by_key.get(key)
        if base is None:
            f.diff_status = "new"
            deltas.append(_delta_for(f, "new", None))
        elif _change_signature(f) != _change_signature(base):
            f.diff_status = "changed"
            deltas.append(_delta_for(f, "changed", base))
        else:
            f.diff_status = None  # unchanged findings carry no review annotation
            deltas.append(_delta_for(f, "unchanged", base))

    for key, base in base_by_key.items():
        if key in seen:
            continue
        deltas.append(
            FindingDelta(
                key=key,
                status="resolved",
                direction="improvement",
                signal=base.signal,
                category=base.category,
                title=base.title or base.observed,
                baseline_finding_id=base.finding_id,
                baseline_severity_score=_severity_score(base),
                severity_tier=_severity_tier(base),
                detail="present in baseline, gone now",
            )
        )

    notes: list[str] = []
    if not baseline.findings:
        notes.append("baseline run had no analyzed findings; all current are 'new'")
    # Safety net: distinct findings sharing one key are matched ambiguously (and a
    # colliding baseline twin is dropped). With the content discriminator this is
    # rare, but surface it rather than under-report silently.
    for label, run in (("current", current), ("baseline", baseline)):
        collisions = _colliding_signals(run.findings)
        if collisions:
            notes.append(
                f"{label} run has findings sharing a diff key "
                f"(ambiguous match): {', '.join(collisions)}"
            )

    return RunDiff(
        run_id=current.run_id,
        baseline_run_id=baseline.run_id,
        target_url=current.target_url,
        finding_deltas=deltas,
        tech_added=sorted(
            {t.name for t in current.fingerprint}
            - {t.name for t in baseline.fingerprint}
        ),
        tech_removed=sorted(
            {t.name for t in baseline.fingerprint}
            - {t.name for t in current.fingerprint}
        ),
        endpoints_added=sorted(_endpoint_keys(current) - _endpoint_keys(baseline)),
        endpoints_removed=sorted(_endpoint_keys(baseline) - _endpoint_keys(current)),
        rendering_model_change=_field_change(current, baseline, "rendering_model"),
        source_maps_change=_field_change(current, baseline, "source_maps_present"),
        notes=notes,
    )


def _endpoint_keys(run: CaptureRun) -> set[str]:
    return {f"{e.method} {e.path_template}" for e in run.api_surface}


def _field_change(
    current: CaptureRun, baseline: CaptureRun, attr: str
) -> dict[str, Any] | None:
    cur_val, base_val = getattr(current, attr), getattr(baseline, attr)
    return {"from": base_val, "to": cur_val} if cur_val != base_val else None


def find_baseline_run(store: Any, current: CaptureRun) -> CaptureRun | None:
    """Return the latest stored run of the same target captured before ``current``.

    Linear scan over stored runs -- fine for the handful-of-runs case; a future
    run index could make this O(1) (see issue #13). Skips the current run, runs
    for a different ``target_url``, and runs not strictly older than ``current``.
    """
    candidates: list[CaptureRun] = []
    for run_id in store.run_ids():
        if run_id == current.run_id:
            continue
        try:
            prior = store.load_run(run_id)
        except (KeyError, ValueError):
            continue
        if prior.target_url != current.target_url:
            continue
        if prior.started_at >= current.started_at:
            continue
        candidates.append(prior)
    if not candidates:
        return None
    return max(candidates, key=lambda r: r.started_at)


def diff_analysis_id(run_id: str) -> str:
    """The store key under which a run's :class:`~ov.base.RunDiff` blob is saved.

    Single source of truth for the convention (``"diff_<run_id>"``) shared by the
    writer (:func:`build_diff`) and the readers (report render + synopsis), so the
    key lives in exactly one place.

    >>> diff_analysis_id("run_abc")
    'diff_run_abc'
    """
    return f"diff_{run_id}"


def load_diff(store: Any, run_id: str) -> dict[str, Any] | None:
    """Load a run's serialized :class:`~ov.base.RunDiff` blob, or ``None`` if absent."""
    try:
        return store.load_analysis(diff_analysis_id(run_id))
    except KeyError:
        return None


def build_diff(
    run_or_id: CaptureRun | str,
    *,
    baseline: CaptureRun | str | None = None,
    store: Any = None,
    persist: bool = True,
) -> RunDiff | None:
    """Diff a run against a baseline (explicit or auto-discovered) and persist it.

    ``baseline`` may be a :class:`~ov.base.CaptureRun`, a run id, or ``None`` (in
    which case the latest prior run of the same target is used). Returns ``None``
    when no baseline exists -- e.g. the first review run -- after appending a
    legible note to the run. Otherwise it annotates ``Finding.diff_status`` in
    place, persists the run + a ``diff_<run_id>`` analysis blob (which the review
    report section and synopsis read), and returns the :class:`~ov.base.RunDiff`.

    The run is assumed already analyzed (call :func:`ov.analyze` first).
    """
    store = resolve_store(store)
    current = (
        run_or_id if isinstance(run_or_id, CaptureRun) else store.load_run(run_or_id)
    )

    if isinstance(baseline, CaptureRun):
        base: CaptureRun | None = baseline
    elif isinstance(baseline, str):
        base = store.load_run(baseline)
    else:
        base = find_baseline_run(store, current)

    if base is None:
        current.notes.append("review diff: no prior baseline run found for this target")
        if persist:
            store.save_run(current)
        return None

    diff = diff_runs(current, base)
    if persist:
        store.save_run(current)  # persist the diff_status annotations
        store.save_analysis(
            diff_analysis_id(current.run_id), diff.model_dump(mode="json")
        )
    return diff
