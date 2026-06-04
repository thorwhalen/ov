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
