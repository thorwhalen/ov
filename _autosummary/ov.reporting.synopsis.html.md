# ov.reporting.synopsis

Synopsis: structured map-reduce over findings into one agent-consumable file (§8.4).

Maps each [`Finding`](ov.base.html.md#ov.base.Finding) into a compact synopsis record, \*\*deduplicates
deterministically\*\* (cluster on type + evidence-ref overlap + normalized summary;
merge to the union of evidence refs and the max severity), and emits two
renderings from one source: `synopsis.json` (the SSOT a downstream agent
consumes) and `SYNOPSIS.md` derived from it (never hand-authored). Evidence-id
overlap is a model-free check, more reliable than LLM similarity-judging.

### Functions

| [`build_synopsis`](#ov.reporting.synopsis.build_synopsis)(run_or_id, \*[, out, store])   | Build + persist `synopsis.json` and the derived `SYNOPSIS.md`; return the md path/key.   |
|------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------|
| [`build_synopsis_doc`](#ov.reporting.synopsis.build_synopsis_doc)(run, \*[, diff])           | Build the `synopsis.json` SSOT document from a run's findings (pure).                    |
| [`dedupe_findings`](#ov.reporting.synopsis.dedupe_findings)(findings)                     | Cluster + merge findings deterministically; return synopsis records (pure).              |
| [`render_synopsis_md`](#ov.reporting.synopsis.render_synopsis_md)(doc)                       | Derive SYNOPSIS.md from the synopsis JSON (never hand-authored).                         |

### ov.reporting.synopsis.build_synopsis(run_or_id, , out=None, store=None)

Build + persist `synopsis.json` and the derived `SYNOPSIS.md`; return the md path/key.

`run_or_id` may be a `CaptureRun` or a run id. The JSON is the SSOT;
the Markdown is derived. Both are written to the store (and `out` dir if given).

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### ov.reporting.synopsis.build_synopsis_doc(run, , diff=None)

Build the `synopsis.json` SSOT document from a run’s findings (pure).

When `diff` (a serialized [`RunDiff`](ov.base.html.md#ov.base.RunDiff)) is given – review mode
with a baseline – a `regression` block is appended so the synopsis tells a
downstream agent what changed since the prior run, not just the current state.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

### ov.reporting.synopsis.dedupe_findings(findings)

Cluster + merge findings deterministically; return synopsis records (pure).

Two findings cluster when they share `type` and either overlap on evidence
refs or share a normalized summary. Each cluster yields one record holding the
union of evidence refs, the max severity, and the highest-severity representative.

```pycon
>>> from ov.base import Finding, Severity
>>> a = Finding(type="ux_issue", signal="contrast.text", category="a11y",
...             title="low contrast", evidence_refs=["x"],
...             severity=Severity(impact_tier="serious", score=3.0))
>>> b = Finding(type="ux_issue", signal="contrast.text", category="a11y",
...             title="low contrast", evidence_refs=["y"],
...             severity=Severity(impact_tier="serious", score=5.0))
>>> recs = dedupe_findings([a, b])
>>> len(recs), sorted(recs[0]["evidence_refs"]), recs[0]["severity_score"]
(1, ['x', 'y'], 5.0)
```

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]]

### ov.reporting.synopsis.render_synopsis_md(doc)

Derive SYNOPSIS.md from the synopsis JSON (never hand-authored).

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
