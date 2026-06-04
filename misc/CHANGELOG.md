# Changelog

All notable changes to `ov` are documented here. The project is built in phases
(see the GitHub issues); each phase is independently shippable.

## [Unreleased]

### Phase 1 — Capture spine (no LLM, no host required)

- **SSOT** Pydantic v2 model tree (`ov/base.py`): operate value types, capture
  artifacts, inferred facts (`Scored`/`TechFinding`/`Endpoint`), and analysis
  outputs (`Evidence`/`Severity`/`Finding`/`EvidenceBundle`/`CaptureRun`).
- **Config** (`ov/config.py`): keyword-only, env-overridable defaults + the
  default-safety checklist (redaction on, authorization gate, polite rate, robots
  intent, secret capture off).
- **Stores** (`ov/capture/stores.py`): `dol`-backed Mall with content-addressed,
  deduplicating artifacts.
- **Registries** (`ov/registry.py`): plugin mechanism + minimal topo-sort by
  `requires`/`produces`.
- **Capture**: Playwright facade (`browser.py`), CDP escape hatch (`cdp.py`,
  Chromium-only), `CaptureSession` orchestrator, and 11 probes — `network`,
  `console`, `navigation`, `websocket`, `sse`, `dom`, `screenshot`, `perf`,
  `storage`, `fingerprint` (built-in, license-clean), `assets`.
- **Operate**: the five model-free primitives (`observe`/`act`/`journal`/
  `progress`/`snapshot_state`), three perception strategies, and a scripted/guided
  driver (replay + same-origin crawl).
- **Facade + CLI**: `ov.observe(...)` and `ov observe|check|runs` (argh dispatch).
- **Tests**: hermetic local test app; deterministic core fully tested; real-browser
  capture tests gated on Chromium availability.
- **Decision**: wads auto-publish disabled (unpublished package); re-enable on a
  deliberate release.

### Phase 2 — Deterministic analysis + reports + Node sidecar (no LLM)

- **Analysis foundation**: `AnalysisContext` (artifact-reading helpers) +
  `AnalyzerOutput`; `run_analysis` orchestrator (lens selection, dependency
  ordering, merge-into-run, idempotent re-analysis). Analyzers register with a
  `lens` and are eagerly loaded.
- **UX engine** (`analysis/ux/`): `severity` (`impact_tier x reach`), `a11y`
  (WebAIM perennials from the DOM + optional axe mapping + honesty
  `needs_human_review` routing), `contrast_focus` (WCAG luminance from captured
  computed styles), `cwv` (INP/CLS/LCP/TTFB thresholds), `metrics` (form-friction
  5-7 field cliff, backtracking), `heuristics` (console-on-step, missing feedback,
  live-region absence).
- **Arch pipeline** (`analysis/arch/`): `rendering` (CSR/SSR/SSG via captured
  server-HTML vs rendered-DOM diff — hermetic, no re-fetch), `framework` (bundler/
  state-management signatures + route map), `api` (GenSON schema merge +
  REST/RPC/GraphQL classifier + auth inference + coverage), `bundles` (source-map
  detection — the bimodal lever — + optional sidecar recovery), `dependencies`
  (inventory + optional Retire.js CVEs), `sidecar` (Python facade), `pipeline`.
- **Capture**: new `a11y` probe (computed text styles for contrast + optional
  axe-core when resolvable); network probe now records request-body *shape*
  (type-preserving redaction) for API request schemas.
- **Reporting**: registered sections (overview / UX / architecture / API /
  reconstruction-blueprint | review-audit / appendix), `render`, and the
  `synopsis` map-reduce (deterministic dedup on type + evidence-ref overlap +
  normalized summary; emits `synopsis.json` SSOT and derives `SYNOPSIS.md`).
  `analyze`/`report`/`synopsis`/`overview` facade + CLI now functional.
- **Node sidecar** (`sidecar/`): JSON-RPC 2.0 over stdio; `consumeSourceMap` /
  `extractLiterals` (static `@babel/parser` AST — never evals JS) / `unpackBundle`.
- **Deps**: `httpx`, `genson`, `selectolax` promoted to core.
- **Tests**: deterministic analyzers + reporting tested on synthetic artifacts;
  full `overview` pipeline tested end-to-end (browser-gated).
