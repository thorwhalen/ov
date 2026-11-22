# ov.analysis.diff

Own-target diffing: a run vs a stored prior baseline run (review mode, §10).

Review mode’s distinguishing capability is *regression/drift detection*: compare
an analyzed [`CaptureRun`](ov.base.html.md#ov.base.CaptureRun) against a stored prior run of the same
target and report what is **new**, **changed**, or **resolved**. Because
artifacts are content-addressed (identical bytes dedupe across runs), this
comparison is cheap by design (spec §3.4).

The matching unit is the [`Finding`](ov.base.html.md#ov.base.Finding). Finding ids are regenerated
every run, so cross-run identity is derived from *stable semantic fields*
([`finding_key()`](#ov.analysis.diff.finding_key)) – category, signal, engine/heuristic/WCAG identifiers, and
a stable locator – explicitly excluding per-run ids (`finding_id`, `step_id`,
`state_id`) that would make every finding look brand new.

Two entry points:

* [`diff_runs()`](#ov.analysis.diff.diff_runs) – **pure**: compare two in-memory runs, annotate the current
  run’s `Finding.diff_status` in place, and return a [`RunDiff`](ov.base.html.md#ov.base.RunDiff).
* [`build_diff()`](#ov.analysis.diff.build_diff) – **store-aware**: resolve a baseline (explicit id/run or
  the latest prior run of the same target via [`find_baseline_run()`](#ov.analysis.diff.find_baseline_run)), run
  [`diff_runs()`](#ov.analysis.diff.diff_runs), and persist both the annotated run and a `diff_<run_id>`
  > analysis blob so the review report section + the synopsis can read it.

### Functions

| [`build_diff`](#ov.analysis.diff.build_diff)(run_or_id, \*[, baseline, store, ...])   | Diff a run against a baseline (explicit or auto-discovered) and persist it.                                                 |
|------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------|
| [`diff_analysis_id`](#ov.analysis.diff.diff_analysis_id)(run_id)                            | The store key under which a run's [`RunDiff`](ov.base.html.md#ov.base.RunDiff) blob is saved.   |
| [`diff_runs`](#ov.analysis.diff.diff_runs)(current, baseline)                        | Compare two analyzed runs; annotate `current` in place; return the diff.                                                    |
| [`find_baseline_run`](#ov.analysis.diff.find_baseline_run)(store, current)                   | Return the latest stored run of the same target captured before `current`.                                                  |
| [`finding_key`](#ov.analysis.diff.finding_key)(finding)                                | Return a stable cross-run identity for a finding (pure, model-free).                                                        |
| [`load_diff`](#ov.analysis.diff.load_diff)(store, run_id)                            | Load a run's serialized [`RunDiff`](ov.base.html.md#ov.base.RunDiff) blob, or `None` if absent. |

### ov.analysis.diff.build_diff(run_or_id, , baseline=None, store=None, persist=True)

Diff a run against a baseline (explicit or auto-discovered) and persist it.

`baseline` may be a [`CaptureRun`](ov.base.html.md#ov.base.CaptureRun), a run id, or `None` (in
which case the latest prior run of the same target is used). Returns `None`
when no baseline exists – e.g. the first review run – after appending a
legible note to the run. Otherwise it annotates `Finding.diff_status` in
place, persists the run + a `diff_<run_id>` analysis blob (which the review
report section and synopsis read), and returns the [`RunDiff`](ov.base.html.md#ov.base.RunDiff).

The run is assumed already analyzed (call [`ov.analyze()`](ov.html.md#ov.analyze) first).

* **Return type:**
  [`RunDiff`](ov.base.html.md#ov.base.RunDiff) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

### ov.analysis.diff.diff_analysis_id(run_id)

The store key under which a run’s [`RunDiff`](ov.base.html.md#ov.base.RunDiff) blob is saved.

Single source of truth for the convention (`"diff_<run_id>"`) shared by the
writer ([`build_diff()`](#ov.analysis.diff.build_diff)) and the readers (report render + synopsis), so the
key lives in exactly one place.

```pycon
>>> diff_analysis_id("run_abc")
'diff_run_abc'
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### ov.analysis.diff.diff_runs(current, baseline)

Compare two analyzed runs; annotate `current` in place; return the diff.

Side effect (by design, per issue #14): each `current` finding’s
`diff_status` is set to `"new"`/`"changed"` or cleared to `None` for
unchanged ones. Resolved findings live only in the returned
[`RunDiff`](ov.base.html.md#ov.base.RunDiff) (they are absent from `current`). The function is
otherwise pure – no store, no browser, no model.

```pycon
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
```

* **Return type:**
  [`RunDiff`](ov.base.html.md#ov.base.RunDiff)

### ov.analysis.diff.find_baseline_run(store, current)

Return the latest stored run of the same target captured before `current`.

Linear scan over stored runs – fine for the handful-of-runs case; a future
run index could make this O(1) (see issue #13). Skips the current run, runs
for a different `target_url`, and runs not strictly older than `current`.

* **Return type:**
  [`CaptureRun`](ov.base.html.md#ov.base.CaptureRun) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

### ov.analysis.diff.finding_key(finding)

Return a stable cross-run identity for a finding (pure, model-free).

Built from semantic fields that survive re-capture – category, signal, any
engine/heuristic/WCAG rule id, a structural locator, and (only when no
structural locator pins identity) a stable content discriminator. Never from
per-run ids. Two findings describing the same issue in two runs share a key;
two *distinct* findings of the same locator-less signal do not collapse.

```pycon
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
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### ov.analysis.diff.load_diff(store, run_id)

Load a run’s serialized [`RunDiff`](ov.base.html.md#ov.base.RunDiff) blob, or `None` if absent.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)] | [`None`](https://docs.python.org/3/builtins/constants.html#None)
