---
name: ov-capture
description: >-
  How to run an `ov` capture session against a web app — launch the browser, choose
  which probes to enable, and inspect the resulting artifact store. Load this when you
  are capturing a target with ov (step 1 of study-web-app), choosing probes, or
  looking at what was captured.
---

# Capturing with `ov`

Capture drives a browser (Playwright + a Chromium CDP escape hatch) and writes
**typed, content-addressed artifacts** into a store. It is deterministic and needs
no model.

## The simple path
```python
import ov
run = ov.observe("https://target", mode="reconstruct", authorized=True)
```
or from the shell: `ov observe https://target`.

`ov.observe(url, *, goal=None, journey=None, mode="reconstruct", probes="default",
headed=False, store=None, crawl_pages=None, config=None, authorized=None)`.

- `crawl_pages=N` does a polite same-origin breadth crawl of N pages.
- `journey=[{"type":"click","ref":"e3"}, ...]` replays a scripted action list.
- `headed=True` shows the browser (debugging).
- `store=` a path or a `CaptureStore`; defaults to an XDG-aligned root.

## Probes — what gets gathered
`probes="default"` enables: `navigation`, `network`, `dom` (DOM + ARIA snapshot +
full AX tree), `screenshot`, `console`, `fingerprint`, `assets`, `a11y` (computed
text styles for contrast + axe-core if available). `probes="all"` adds `perf`
(Core Web Vitals), `storage` (redacted), `websocket`, `sse`. Or pass an explicit
list. Unknown names are ignored with a note on the run.

Pick probes by goal: UX/accessibility → keep `a11y` + add `perf`; API
reconstruction → ensure `network` (default); realtime app → add `websocket`/`sse`.

## Privacy + safety defaults (already on)
Redaction is on (cookies/auth headers/storage values become `<redacted:N>`),
secret capture is off, a polite rate is applied, robots intent is respected, and a
foreign target needs `authorized=True`. Request bodies are captured *shape-only*
(type-preserving) so API schemas synthesize without leaking values.

## Inspecting the store
```python
from ov.capture.stores import CaptureStore
store = CaptureStore()                 # same root observe() used
store.run_ids()                        # list runs
run = store.load_run(run_id)
[a.kind for a in run.artifacts]        # what was captured
store.artifact_bytes(run.artifacts[0]) # raw bytes by artifact
```
Artifact kinds: `dom`, `aria_snapshot`, `ax_tree`, `screenshot`, `network`,
`request` (bodies), `console`, `navigation`, `fingerprint`, `assets`,
`a11y_styles`, `axe`, `perf`, `storage`, `websocket`, `sse`, `har`.

## System requirements
`ov check` (or `ov.check_requirements()`) reports missing Playwright browsers /
Node / sidecar / optional CLIs with exact install commands. Capture needs
`playwright install chromium`. The deterministic analysis layer needs none of it.

## Gotchas
- Capture needs a browser; the deterministic analyzers do **not** (they read the
  stored artifacts). Keep that seam in mind when something is missing.
- CDP-only signals (full AX tree, SSE, perf counters) are Chromium-only.
- Large/CDN'd response bodies may evict; the network probe records the eviction as
  a fact rather than failing.
