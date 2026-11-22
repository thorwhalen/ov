# ov

`ov` – OverView: agent-driven web reconnaissance & analysis.

Point `ov` at a URL and it drives the target like a user, recording two
parallel streams – the *behavioral* stream (what the app does) and the *static*
stream (what it is made of) – then runs two analysis lenses (UX and
software-design) and renders Markdown reports plus a single synopsis.

This module is the **progressive-disclosure facade**: the five top-level
functions below are all most callers need, and each works with sensible defaults.
Everything underneath (capture probes, operate primitives, analyzers, report
sections) is reachable but never required.

```pycon
>>> import ov
>>> callable(ov.observe) and callable(ov.overview)
True
```

The primary consumption model is a *host agent* (Claude Code) wielding these
functions via the skills in `.claude/skills/` – the deterministic core here
runs with no model and no host.

### Functions

| [`observe`](#ov.observe)(url, \*[, goal, journey, mode, ...])   | Drive the target and capture everything.                                    |
|-------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| [`analyze`](#ov.analyze)(run, \*[, lenses, llm, store])         | Run the deterministic UX + architecture analyzers over a captured run.      |
| [`diff`](#ov.diff)(run, \*[, baseline, store])               | Diff an analyzed run against a prior baseline run (own-target review mode). |
| [`report`](#ov.report)(run_or_analyses, \*[, sections, ...])   | Render Markdown reports from analyses.                                      |
| [`synopsis`](#ov.synopsis)(reports_or_dir, \*[, out, store])     | Extract-and-aggregate many reports into one synopsis for downstream agents. |
| [`overview`](#ov.overview)(url, \*\*kw)                          | `observe -> analyze -> report -> synopsis`, the one-liner.                  |
| [`check_requirements`](#ov.check_requirements)(\*[, components, verbose])  | Detect missing system dependencies and print exact install commands.        |

### Classes

| [`OvConfig`](#ov.OvConfig)(\*[, store_root, headed, browser, ...])   | Resolved settings for a capture/analysis run (keyword-only, env-overridable).   |
|-----------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| [`CaptureRun`](#ov.CaptureRun)(\*[, run_id, target_url, mode, ...])    | Everything one `observe` produced; artifacts live in the store by id.           |
| [`RunDiff`](#ov.RunDiff)(\*, run_id, baseline_run_id[, ...])        | Own-target regression: a run vs a stored prior baseline run (review mode, §10). |

### *class* ov.CaptureRun(\*, run_id=<factory>, target_url='', mode='reconstruct', started_at=<factory>, finished_at=None, steps=<factory>, artifacts=<factory>, fingerprint=<factory>, rendering_model=None, source_maps_present=None, api_surface=<factory>, findings=<factory>, settings_snapshot=<factory>, notes=<factory>)

Bases: `BaseModel`

Everything one `observe` produced; artifacts live in the store by id.

#### artifact_by_id(artifact_id)

Return the `Artifact` with `artifact_id` or `None`.

* **Return type:**
  [`Artifact`](ov.base.html.md#ov.base.Artifact) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'validate_assignment': False}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* ov.OvConfig(, store_root=default_store_root(), headed=False, browser='chromium', nav_timeout_ms=30000, default_probes=('navigation', 'network', 'dom', 'screenshot', 'console', 'fingerprint', 'assets', 'a11y'), max_body_bytes=2000000, console_text_cap=2000, ws_frame_cap=4096, capture_body_content_types=('application/json', 'application/javascript', 'text/javascript', 'text/html', 'text/css', 'text/event-stream', 'application/graphql', 'application/xml', 'text/plain'), max_steps=40, max_failures=6, wall_clock_s=300.0, no_progress_steps=3, redact_values=True, capture_secrets=False, respect_robots=True, polite_rate_s=0.3, authorized=False, use_proxy=False, stealth_profile=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Resolved settings for a capture/analysis run (keyword-only, env-overridable).

Construct with [`from_env()`](#ov.OvConfig.from_env) for the env-aware default, or pass explicit
fields to override. The instance is snapshotted into every
[`CaptureRun`](ov.base.html.md#ov.base.CaptureRun) (`settings_snapshot`) for provenance.

#### *classmethod* from_env(\*\*overrides)

Build a config from `OV_*` env vars, with explicit `overrides` winning.

```pycon
>>> isinstance(OvConfig.from_env().store_root, Path)
True
```

* **Return type:**
  [`OvConfig`](ov.config.html.md#ov.config.OvConfig)

#### snapshot()

Return a JSON-serializable snapshot for `CaptureRun.settings_snapshot`.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

### *class* ov.RunDiff(\*, run_id, baseline_run_id, target_url='', created_at=<factory>, finding_deltas=<factory>, tech_added=<factory>, tech_removed=<factory>, endpoints_added=<factory>, endpoints_removed=<factory>, rendering_model_change=None, source_maps_change=None, notes=<factory>)

Bases: `BaseModel`

Own-target regression: a run vs a stored prior baseline run (review mode, §10).

Produced by [`ov.analysis.diff.diff_runs()`](ov.analysis.diff.html.md#ov.analysis.diff.diff_runs) from two analyzed
`CaptureRun`s of the same target. The :attr:`finding_deltas` list is
the SSOT; [`counts`](#ov.RunDiff.counts)/[`has_drift`](#ov.RunDiff.has_drift) are *derived* (`@computed_field`,
so they serialize) and [`regressions`](#ov.RunDiff.regressions)/[`improvements`](#ov.RunDiff.improvements) are views over
the deltas – nothing is stored twice.

```pycon
>>> d = RunDiff(run_id="run_b", baseline_run_id="run_a", finding_deltas=[
...     FindingDelta(key="k1", status="new", direction="regression"),
...     FindingDelta(key="k2", status="resolved", direction="improvement"),
... ])
>>> d.counts["new"], d.counts["resolved"], d.has_drift
(1, 1, True)
>>> [r.key for r in d.regressions], [i.key for i in d.improvements]
(['k1'], ['k2'])
```

#### *property* counts *: [dict](https://docs.python.org/3/builtins/stdtypes.html#dict)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [int](https://docs.python.org/3/builtins/functions.html#int)]*

Per-status tallies derived from the deltas (the headline of a diff).

#### *property* has_drift *: [bool](https://docs.python.org/3/builtins/functions.html#bool)*

`True` if anything changed across runs (findings, stack, API, or model).

#### *property* improvements *: [list](https://docs.python.org/3/builtins/stdtypes.html#list)[[FindingDelta](ov.base.html.md#ov.base.FindingDelta)]*

Deltas that were resolved or got better since the baseline.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

#### *property* regressions *: [list](https://docs.python.org/3/builtins/stdtypes.html#list)[[FindingDelta](ov.base.html.md#ov.base.FindingDelta)]*

Deltas that got worse or are newly present (a downstream fix list).

### ov.analyze(run, , lenses=('ux', 'arch'), llm=None, store=None)

Run the deterministic UX + architecture analyzers over a captured run.

Runs fully without a model (`llm=None` is the default and the only path
needed in Phases 1-2). The host agent reasons over the returned analyses +
evidence bundle to add narrative judgment.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### ov.check_requirements(, components=None, verbose=True)

Detect missing system dependencies and print exact install commands.

`components` filters which groups to check (`"browser"`, `"node"`,
`"sidecar"`, `"clis"`); `None` checks all. The deterministic analysis
core needs none of these – they gate *capture* and the *arch sidecar*, so
every requirement here is reported as optional unless capture is requested.

```pycon
>>> rep = check_requirements(components=["clis"], verbose=False)
>>> isinstance(rep, RequirementReport)
True
```

* **Return type:**
  [`RequirementReport`](ov.util.html.md#ov.util.RequirementReport)

### ov.diff(run, , baseline=None, store=None)

Diff an analyzed run against a prior baseline run (own-target review mode).

The distinguishing capability of `mode="review"`: report what is *new*,
*changed*, or *resolved* versus a stored prior run of the same target
(regression/drift detection, §10). Fully deterministic – no browser, no model.

* **Parameters:**
  * **run** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – an analyzed [`CaptureRun`](ov.base.html.md#ov.base.CaptureRun) or a run id.
  * **baseline** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – a run/run-id to compare against, or `None` to auto-discover the
    latest prior run of the same target.
  * **store** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – a [`CaptureStore`](ov.capture.stores.html.md#ov.capture.stores.CaptureStore), a path, or `None`.
* **Return type:**
  [`RunDiff`](ov.base.html.md#ov.base.RunDiff) | [`None`](https://docs.python.org/3/builtins/constants.html#None)
* **Returns:**
  A [`RunDiff`](ov.base.html.md#ov.base.RunDiff), or `None` if no baseline exists yet (the
  first review run). Sets `Finding.diff_status` on the run in place and
  persists a `diff_<run_id>` blob that the review report + synopsis read.

### ov.observe(url, , goal=None, journey=None, mode='reconstruct', probes='default', headed=False, store=None, crawl_pages=None, config=None, authorized=None, read_only=False)

Drive the target and capture everything. Zero-config default works.

* **Parameters:**
  * **url** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – the target to study.
  * **goal** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – a natural-language objective (goal-pursuit is *host* policy; the
    deterministic core records it and does the baseline journey).
  * **journey** ([`list`](https://docs.python.org/3/builtins/stdtypes.html#list) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – an optional scripted action list (guided-replay), each item an
    [`Action`](ov.base.html.md#ov.base.Action) or a dict like `{"type": "click", "ref": "e3"}`.
  * **mode** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – `"reconstruct"` (foreign target) or `"review"` (own target).
  * **probes** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – `"default"`, `"all"`, or an iterable of probe names.
  * **headed** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – run the browser headed (default headless).
  * **store** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – a [`CaptureStore`](ov.capture.stores.html.md#ov.capture.stores.CaptureStore), a path, or `None`.
  * **crawl_pages** ([`int`](https://docs.python.org/3/builtins/functions.html#int) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – if set (>1), politely crawl that many same-origin pages.
  * **config** ([`OvConfig`](ov.config.html.md#ov.config.OvConfig) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – an explicit [`OvConfig`](#ov.OvConfig) (overrides `headed`).
  * **authorized** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – acknowledge authorization to study a *foreign* target.
  * **read_only** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – abort every non-GET/HEAD/OPTIONS request in the browser (pages
    that POST on load send nothing); the aborted ones are listed in a
    `blocked_requests` artifact and a run note.
* **Return type:**
  [`CaptureRun`](ov.base.html.md#ov.base.CaptureRun)
* **Returns:**
  The populated [`CaptureRun`](ov.base.html.md#ov.base.CaptureRun) (also persisted to the store).

### ov.overview(url, \*\*kw)

`observe -> analyze -> report -> synopsis`, the one-liner.

Returns the synopsis path/handle. This is the pit-of-success entry point.

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)

### ov.report(run_or_analyses, , sections='default', out_dir=None, store=None)

Render Markdown reports from analyses. Returns the written paths/keys.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)

### ov.synopsis(reports_or_dir, , out=None, store=None)

Extract-and-aggregate many reports into one synopsis for downstream agents.

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)

### Modules

| [`agents`](ov.agents.html.md#module-ov.agents)       | `ov.agents` — the optional in-package agent layer (Phase 4 productization).   |
|--------------------------------------------------------------------------------|-------------------------------------------------------------------------------|
| [`analysis`](ov.analysis.html.md#module-ov.analysis)   | Analysis layer: deterministic analyzers over captured artifacts (Phases 2-3). |
| [`base`](ov.base.html.md#module-ov.base)           | Single source of truth (SSOT) for the `ov` artifact schema.                   |
| [`capture`](ov.capture.html.md#module-ov.capture)     | Capture layer: drive a browser and record behavioral + static streams.        |
| [`config`](ov.config.html.md#module-ov.config)       | Configuration -- the single source of truth for `ov`'s defaults.              |
| [`operate`](ov.operate.html.md#module-ov.operate)     | The operate layer -- deterministic, LLM-free tool primitives (the "hands").   |
| [`registry`](ov.registry.html.md#module-ov.registry)   | The plugin mechanism: decorated functions registered into a dict (§3.2).      |
| [`reporting`](ov.reporting.html.md#module-ov.reporting) | Report layer: registered Markdown sections + the synopsis (Phase 2).          |
| [`util`](ov.util.html.md#module-ov.util)           | Internal helpers: content-addressing, hashing, redaction, and requirements.   |
