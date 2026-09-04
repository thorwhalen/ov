---
name: ov-analyze-arch
description: >-
  How to run ov's deterministic architecture-reconstruction analyzers and turn the
  scored facts into a rebuild blueprint (reconstruct) or an architecture audit
  (review). Load this for the software-design lens: framework/rendering/state/routing
  detection, source-map recovery, API surface synthesis, dependency/CVE flags.
coact:
  model: opus
  tools: [Read, Grep, Glob]
  memory: project
  consumes: evidence_bundle
  returns:
    schema_ref: ov.base:Finding
    description: >-
      Architecture facts + reconstruction-blueprint / audit findings (a list of
      ov.base:Finding, source_layer="llm") grounded in captured artifacts. Design-
      intent reasoning is judgment-heavy, so Opus-routed (cost gate, §10).
---

# Software-architecture analysis

A deterministic `fingerprint → bundle-recovery → api-synthesis` pipeline produces
**scored facts** with provenance; you turn them into a blueprint or an audit.

## 1. Run the pipeline
```python
import ov

ov.analyze(run, lenses=("arch",))
```
Populates `run.fingerprint` (technologies, versions, confidence),
`run.rendering_model`, `run.source_maps_present`, `run.api_surface`, and arch
`Finding`s. The analyzers:
- **rendering** — CSR / SSR-or-SSG / hybrid via the captured **server-HTML vs
  rendered-DOM diff** (corroborated by `__NEXT_DATA__`/`__NUXT__`/`__remixContext`).
- **framework** — bundler (webpack/Vite/esbuild/Turbopack) + state-management
  signatures from bundle text; client route map from `<a href>`.
- **bundles** — source-map detection. **This is the decisive lever**:
  `source_maps_present=True` ⇒ reconstruction-grade (original file tree + source +
  `node_modules` versions, recoverable via the sidecar); `False` ⇒ beautified but
  identifiers lost. Gate every reconstruction claim's confidence on this.
- **api** — per-endpoint JSON Schemas merged (GenSON) across journey samples +
  REST/RPC/GraphQL class + auth scheme + coverage/confidence.
- **dependencies** — inventory (provenance: sourcemap path > bundle comment >
  global signature) + Retire.js CVEs when installed (else a human-review finding).

## 2. Source maps make or break reconstruction
Check `run.source_maps_present` first. If present and you need the file tree, the
Node sidecar recovers it:
```python
from ov.analysis.arch.sidecar import Sidecar

sc = Sidecar()
if sc.available():
    files = sc.consume_source_map(map_text)["files"]  # original paths + sourcesContent
    lits = sc.extract_literals(
        js_text
    )  # static AST: strings/urls/routes (never evals JS)
```
`ov check` shows whether the sidecar is installed (`cd sidecar && npm install`).

## 3. Produce the output (your judgment, grounded)
Reason over the scored facts (and the evidence bundle for any visual claims). Tag
every inference with evidence + confidence; **abstain** where there is no
client-detectable signal (pure-backend tech isn't observable).
- **reconstruct mode** → a *rebuild blueprint*: "to rebuild a comparable system use
  [stack], structured as [layers], with [these routes], talking to [this API shape],
  managing state via [pattern]" + a reusable interaction-pattern catalog. Mark
  map-backed claims as higher-confidence than name-lost ones.
- **review mode** → an *architecture audit*: coupling/risk observations, dependency
  currency + CVEs (advisory), and (when a prior run exists) drift vs. baseline.

## 4. Reliability
Architecture facts are probabilistic — never assert detected tech as certain;
carry the confidence. If you add narrative claims, gate them with
`ov.analysis.reliability.verify_findings` like the UX lens (cite-or-abstain).

## Boundary
`ov` analyzes publicly-served frontend material of authorized targets. Don't
implement auth bypass or anything that defeats access controls. Reverse-engineering
deployed JS you don't own can implicate ToS / DMCA §1201 — default to authorized
targets and keep provenance.
