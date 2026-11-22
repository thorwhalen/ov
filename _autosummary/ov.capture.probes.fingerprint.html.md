# ov.capture.probes.fingerprint

Fingerprint probe: a built-in, license-clean technology detector.

The spec flags `wappalyzer-next` and the `enthec/webappanalyzer` ruleset as
GPL-3.0, incompatible with `ov`’s MIT license (§6.2). So rather than depend on
them, this probe ships a small deterministic detector over the highest-signal,
lowest-false-positive sources: framework state-injection globals
(`__NEXT_DATA__`/`__NUXT__`/`__remixContext` …), devtools hooks, bundler
signatures, the `<meta name=generator>` tag, `ng-version`, and response
headers. `wappalyzer`/Retire.js remain available as *optional* external CLIs.

Each detection is a [`TechFinding`](ov.base.html.md#ov.base.TechFinding) carrying confidence + provenance
and is appended to `ctx.run.fingerprint` so `ov observe` populates the run
immediately; the raw signals are also stored as an artifact for re-analysis.

### Functions

| [`detect_technologies`](#ov.capture.probes.fingerprint.detect_technologies)(signals[, headers])   | Map captured fingerprint signals (+ headers) into scored :class:<br/><br/>```<br/>`<br/>```<br/><br/>TechFinding\`s.   |
|--------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------|

### Classes

| [`FingerprintProbe`](#ov.capture.probes.fingerprint.FingerprintProbe)()   | Gather in-page signals + headers and populate `run.fingerprint`.   |
|-----------------------------------------------------------------------|--------------------------------------------------------------------|

### *class* ov.capture.probes.fingerprint.FingerprintProbe

Bases: [`Probe`](ov.capture.probes.html.md#ov.capture.probes.Probe)

Gather in-page signals + headers and populate `run.fingerprint`.

#### finalize(ctx)

Flush accumulated state into artifacts at run end. Default: nothing.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Artifact`](ov.base.html.md#ov.base.Artifact)]

### ov.capture.probes.fingerprint.detect_technologies(signals, headers=None)

Map captured fingerprint signals (+ headers) into scored :class:

```
`
```

TechFinding\`s.

Reusable across modules (the arch analyzer enriches these with bundle/source
-map evidence). Prefers `js`/`dom` signals over loose header regex.

```pycon
>>> findings = detect_technologies({"globals": {"__NEXT_DATA__": True}})
>>> sorted(f.name for f in findings)
['Next.js', 'React']
```

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`TechFinding`](ov.base.html.md#ov.base.TechFinding)]
