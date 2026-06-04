# Architecting the Capture & Autonomous-Operation Layer for a Python Web-App Analysis System

*Author: Thor Whalen*
*Target stack: Playwright Python (current 1.5x line, mid-2026) on Chromium/CDP*

## TL;DR

- **Keep Playwright Python as the baseline, but treat it as a *facade* over a CDP escape hatch, not a wall.** Playwright cleanly handles ~80% of capture (request/response metadata, HAR, WebSocket frames, console/exceptions, cookies/localStorage/IndexedDB, tracing). The remaining ~20% — full accessibility trees, Server-Sent Events frames, guaranteed response bodies, TLS/cert detail — requires attaching a raw CDP session via `page.context.new_cdp_session(page)`, and a *minority* of cases justify a mitmproxy layer.
- **Design the operation layer as two cleanly separated planes: a deterministic tool layer your package owns, and a policy layer that lives in the Claude Code host.** Affordance extraction, action execution, journey/intent logging, and loop/no-progress detection are deterministic primitives belonging in the package; strategy selection, recovery judgment, and bounding belong in the host skill. This is the Playwright-MCP / browser-use shape and it maps directly onto facade + dependency-injection + plugin patterns.
- **Prefer accessibility/DOM-grounded perception, with vision as an injected fallback.** The benchmark record (WebArena, WebVoyager, Online-Mind2Web, Operator/CUA, browser-use) shows structured snapshots are cheaper and more deterministic than pixels, but neither alone is robust; expose both as pluggable perception strategies and let the host choose per-step.

---

## Key Findings

1. **Playwright's high-level network API is excellent for metadata and good-but-leaky for bodies.** `page.on("request"/"response")`, `request.timing`, `response.body()`, initiator data, and HAR export (`record_har_path`, `routeFromHAR`, `tracing.start_har`) cover the common case, with `.zip` HAR embedding response bodies as separate entries. But `response.body()` returns empty for some resources and throws `Request content was evicted from inspector cache` for large bodies — a structural limitation, not a bug you can wait around.
2. **CDP is the supplementation layer, not a competitor.** Attaching `new_cdp_session` unlocks `Accessibility.getFullAXTree`, `Network.eventSourceMessageReceived` (SSE), `Fetch.enable`/`Fetch.getResponseBody` (eviction-proof body capture), `Network.getCertificate`, and `Performance.getMetrics` — all from inside the same Playwright process.
3. **A proxy (mitmproxy) is justified only for a specific tail:** guaranteed full-fidelity bodies at scale, TLS/JA3-level detail, service-worker traffic that escapes `page.route`, or non-browser/native traffic. It adds CA-trust and infra complexity, so make it an opt-in plugin.
4. **Playwright's own accessibility snapshot is deprecated; the modern path is ARIA snapshots (`aria_snapshot`, including ref-bearing modes) or raw `Accessibility.getFullAXTree` via CDP.** This matters because the accessibility tree is now the *primary control surface* for AI agents, not just a compliance artifact.
5. **The host-agent tool shape already has two reference implementations:** Playwright-MCP (snapshot mode with deterministic `ref` IDs, `browser_snapshot`/`browser_click`/`browser_network_requests`) and browser-use (full observe→plan→act→verify loop with `max_steps`, `max_failures`, dedup, and no-progress guards). The CLI+Skills variant — Playwright CLI (`@playwright/cli`), which shipped in v1.58 in January 2026 — consumes roughly **27,000 tokens versus ~114,000 for the same task via streaming MCP** (a 4× reduction per Microsoft's own measurements), which is decisive for a Claude Code host.
6. **Grounding is a solved-enough trade-off, reliability is not.** OpenAI's Computer-Using Agent (CUA, powering Operator) reported "a 38.1% success rate on OSWorld... and 58.1% on WebArena and 87% on WebVoyager," explicitly noting WebVoyager tasks are "relatively simple." Browser Use's open-source agent "achieved state-of-the-art performance on the WebVoyager benchmark, with an impressive 89.1% success rate across 586 diverse web tasks." But the Online-Mind2Web re-evaluation showed that "many recent agents, except for Claude Computer Use 3.7 and Operator, do not outperform the simple SeeAct agent released in early 2024. Even Operator only achieves a success rate of 61%." The lesson: instrument per-step intent and progress, don't trust end-to-end success rates.

---

## Details

### PART A — The Capture Stack

#### A.0 The candidates, briefly

| Tool | Network bodies | WS/SSE | AX tree | Storage | Cross-browser | Verdict for this system |
|---|---|---|---|---|---|---|
| **Playwright Python** | Metadata excellent; bodies leaky (eviction) | WS native; SSE weak | Deprecated high-level; CDP for full | cookies/local/IndexedDB via `storage_state` | Chromium/FF/WebKit | **Baseline. Adopt.** |
| **Puppeteer** | Same CDP basis, JS-only | Same | Same CDP route | Similar | Chromium-centric | No — Node, no Python story |
| **Selenium / WebDriver BiDi** | BiDi network intercept maturing | BiDi events | No first-class full AX API | Cookies; storage manual | Best breadth, W3C standard | Watch, don't adopt yet |
| **Raw CDP** | Full control | Full control | `getFullAXTree` | Full | Chromium only | Use *through* Playwright, not standalone |

Playwright wins because it gives a stable, Pythonic, cross-browser facade **and** a first-class CDP escape hatch in the same object graph. WebDriver BiDi is the strategically interesting standard (Selenium 4 ships low-level BiDi; high-level APIs are slated for Selenium 5), and it's where the cross-browser, vendor-blessed event-streaming future lives — but the high-level ergonomics aren't there yet for mid-2026, so treat it as a future pluggable backend behind your capture interface.

#### A.1 Full network stream

Playwright surfaces request method/URL/headers/`post_data`/`resource_type`, response status/headers, `request.timing` (request/response timing), redirect/initiator chains, and `response.body()`. HAR export has three routes:

- `browser.new_context(record_har_path=..., record_har_content="embed")` — context-wide capture;
- `page.route_from_har(..., update=True)` — record/replay;
- `context.tracing.start_har()` — one HAR per context (only one active at a time).

A `.har` whose name ends in `.zip` stores response bodies as separate entries. **The hard limit:** `response.body()` is empty for certain resources (observed for static CSS/JS behind CDNs) and raises `Request content was evicted from inspector cache` for large bodies (reported at ~13MB and ~24.9MB) or after navigation evicts the buffer. The deterministic fix is CDP `Fetch`-stage interception (below), which captures the body *at* interception time rather than retrieving it later from the renderer cache.

#### A.2 WebSocket and SSE

**WebSocket** is first-class: `page.on("websocket")` → `ws.on("framesent"/"framereceived"/"close")`, each frame carrying `payload`. This is sufficient for full WS capture; buffer frames and flush in batches for high-frequency streams.

**SSE (`text/event-stream`) is the weak spot.** `page.on("response")` fires once on headers and does not stream incremental SSE messages; `response.body()` on a long-lived stream hangs or hits eviction. The correct route is CDP: enable `Network` and subscribe to **`Network.eventSourceMessageReceived`**, whose params are `requestId`, `timestamp`, `eventName` (the SSE `event:` field), `eventId` (the `id:` field), and `data` (the `data:` payload). `Network.enable` is required or the event never fires. `page.route` also does not reliably intercept EventSource connections, so don't rely on routing for SSE.

#### A.3 Console / errors / page exceptions

Fully covered by Playwright: `page.on("console")` (messages with type/text/location), `page.on("pageerror")` (uncaught exceptions), `page.on("requestfailed")`. No CDP needed. (For parity, BiDi exposes the same via `log.entryAdded` and `Runtime` exception events, and Playwright's trace viewer aggregates console + network + DOM snapshots per action.)

#### A.4 Accessibility tree — the CDP route that matters most

Playwright's `page.accessibility.snapshot()` is **deprecated** (confirmed on the official API pages; the precise deprecation version is not cleanly documented but predates mid-2026). Two replacements:

- **High-level:** `locator.aria_snapshot()` / `expect(...).to_match_aria_snapshot(...)` produce a YAML accessibility tree (roles, names, attributes). A ref-bearing mode (`mode="ai"`) yields `[ref=e2]`-style handles — exactly what Playwright-MCP and Playwright-CLI emit for deterministic targeting.
- **Full fidelity:** CDP **`Accessibility.getFullAXTree`** (experimental), params `depth` (omit for full tree) and `frameId` (omit for root). Returns `nodes`: each `AXNode` has `nodeId`, `ignored`/`ignoredReasons`, `role`, `name`, `description`, `value`, `properties`, `parentId`, `childIds`, `backendDOMNodeId`, `frameId`. **Critical implementation note:** `role`/`name`/`value` are `AXValue` *objects*, not strings — the accessible name string is at `node["name"]["value"]`. Call `Accessibility.enable` first to keep `AXNodeId`s stable across calls; `getFullAXTree` does not walk into cross-origin iframes, so you must recurse per frame.

The high-level ARIA snapshot is what the *agent* should usually see — concise, semantically meaningful, and (per ytyng.com's 2026 token benchmark of comparable accessibility-tree representations) on the order of **200–400 tokens per page** versus thousands for full DOM dumps or screenshots; the full AX tree is what the *analysis/evidence* layer should record (structural completeness). This is a natural progressive-disclosure split.

#### A.5 Cookies / localStorage / sessionStorage / IndexedDB

`context.storage_state(path=...)` captures cookies + localStorage + (with the `indexed_db=True` option) IndexedDB into one JSON. Gaps to design around:
- **sessionStorage is not captured** by `storage_state`; extract/restore manually via `page.evaluate` reading `window.sessionStorage`.
- **IndexedDB serialization is fragile** — there are reported failures (e.g., empty `storeNames` with Firebase Auth) and extension-context (`chrome-extension://`) object-store visibility bugs. For deep IndexedDB capture, read via `page.evaluate` or CDP `IndexedDB` domain rather than trusting `storage_state` alone.

#### A.6 Tracing / perf hooks

`context.tracing.start(screenshots=True, snapshots=True, sources=True)` → `.zip` viewable at trace.playwright.dev: action timeline, before/after DOM snapshots, network, console. For runtime metrics, attach CDP and call `Performance.enable` then `Performance.getMetrics` (returns `Documents`, `Nodes`, `JSEventListeners`, `LayoutCount`, `LayoutDuration`, `ScriptDuration`, etc.). Playwright tracing is framework-level (works on WebKit/FF without CDP); `Performance.getMetrics` is Chromium-only.

#### A.7 When a proxy (mitmproxy) is justified

mitmproxy is an SSL/TLS-capable intercepting proxy (HTTP/1, HTTP/2, WebSockets) that becomes its own CA to decrypt traffic. Add it **only** when you need one of:
- **Guaranteed full bodies at scale** without eviction risk and without per-request Fetch pausing overhead;
- **TLS / JA3 / HTTP-2 framing detail** the browser APIs don't expose;
- **Service-worker traffic** that `page.route` misses (Playwright recommends `service_workers="block"` precisely because SW-intercepted requests escape routing);
- **Non-browser or native traffic** (mitmproxy local/WireGuard modes).

The cost is CA-trust provisioning, cert lifecycle, and an extra network hop. So make it an **opt-in plugin behind the same capture interface** — most runs won't need it.

#### A.8 Anti-bot / fingerprint evasion — optional, off by default

This is a capability you *expose but do not center*, with an explicit ethical/ToS gate. The 2026 landscape: **Camoufox** (source-patched Firefox, C++-level fingerprint spoofing, Playwright-compatible; note a maintenance gap and Firefox-only lock-in), **undetected-chromedriver / Nodriver** (Selenium-lineage, CDP-minimal), and **playwright-stealth** (JS-level patches, easiest to detect). All require IP-reputation/proxy hygiene to matter, none are truly undetectable, and all demand ongoing maintenance against Cloudflare/DataDome/Akamai. Architecturally: a `StealthProfile` plugin, default `None`, with a clear docstring that legitimate use (testing your own apps, authorized research) is the intended scope and that bypassing access controls may violate ToS or law.

#### A.9 Concrete code patterns

**CDP attach + eviction-proof body capture (async):**

```python
from playwright.async_api import async_playwright

async def capture(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        client = await page.context.new_cdp_session(page)   # CDP escape hatch
        await client.send("Network.enable")

        bodies = {}

        async def on_finished(params):
            rid = params["requestId"]
            try:
                res = await client.send("Network.getResponseBody", {"requestId": rid})
                bodies[rid] = (res["body"], res["base64Encoded"])
            except Exception:
                pass  # redirects / no body

        client.on("Network.loadingFinished",
                  lambda params: page.context._loop.create_task(on_finished(params)))

        await page.goto(url)
        await client.detach()
        return bodies
```

For bodies that still evict, switch to Fetch-stage interception: `await client.send("Fetch.enable", {"patterns": [{"urlPattern": "*", "requestStage": "Response"}]})`, then on `Fetch.requestPaused` call `Fetch.getResponseBody` (requires the request be paused in the **Response** stage) and `Fetch.continueRequest`.

**SSE frame capture (CDP):**

```python
client.on("Network.eventSourceMessageReceived",
          lambda e: sse_log.append({
              "requestId": e["requestId"], "ts": e["timestamp"],
              "event": e["eventName"], "id": e["eventId"], "data": e["data"],
          }))
# requires await client.send("Network.enable")
```

**WebSocket frame capture (high-level):**

```python
def on_ws(ws):
    ws.on("framesent",     lambda f: ws_log.append(("sent", ws.url, f.payload)))
    ws.on("framereceived", lambda f: ws_log.append(("recv", ws.url, f.payload)))
    ws.on("close",         lambda _: ws_log.append(("close", ws.url, None)))
page.on("websocket", on_ws)
```

**HAR + embedded bodies:**

```python
context = browser.new_context(
    record_har_path="run.har.zip",        # .zip embeds bodies as separate entries
    record_har_content="embed",
)
# ... drive the app ...
context.close()   # HAR flushed on context close
```

**Full AX tree (CDP), per frame:**

```python
ax = page.context.new_cdp_session(page)
ax.send("Accessibility.enable")            # stabilizes AXNodeIds
tree = ax.send("Accessibility.getFullAXTree")   # {"nodes": [AXNode, ...]}
# accessible name of a node: node["name"]["value"]  (AXValue, not str)
```

### PART B — The Operation Loop (host-agent-orchestrated)

#### B.1 Framing: tool layer vs policy layer

The manager/control loop lives in the **Claude Code host**, not your package. So the package must expose **deterministic tool primitives**, and the host carries **policy/judgment**. This is exactly the Playwright-MCP and browser-use division of labor, and it maps onto the architect's vocabulary:

- **Tool layer = a Facade** over Playwright+CDP exposing a small, stable, side-effect-honest verb set. Each tool is a pure-ish function of (browser state, args) → (result, fresh observation). **SOLID**: single-responsibility tools, open for extension via a **plugin registry** (perception strategies, stealth profiles, proxy backends), depended-upon through **interfaces** so the host (or a future in-package agent) is the injected client.
- **Policy layer = the Claude Code skill**: a prompt + rules that decide *which* tool, *when* to switch strategy, *how* to recover, and *when* to stop.

The dividing principle: **anything that can be specified deterministically and tested without an LLM goes in the tool layer; anything requiring goal-relative judgment goes in the policy layer.**

#### B.2 How LLM host agents perceive and act (the grounding spectrum)

- **Vision-grounded** (screenshot + coordinates): Operator/CUA, Claude Computer Use. Universal (works on `<canvas>`, exotic renderers) but error-prone on precise targeting and costly in tokens; "click empty/incorrect component" errors compound without a feedback loop.
- **Accessibility/DOM-grounded** (set-of-marks, role+name targeting, ref IDs): Playwright-MCP, Playwright-CLI, MindAct/SeeAct candidate-selection. Compact, deterministic, refactor-stable (`getByRole` survives CSS churn), but blind to canvas and dependent on app A11Y quality.
- **Hybrid**: ground in the AX tree, fall back to vision when the tree is thin (canvas, image-only controls). SeeAct-V and OSCAR-style dual-grounding show this is the robust default.

**Recommendation:** make perception a **strategy plugin** with three implementations — `AxSnapshot`, `Screenshot`, `Hybrid` — all returning a uniform `Observation` (list of affordances with stable refs + optional bbox + optional pixels). The host picks per step; the package stays declarative about *what* an observation is, not *how* it's grounded.

#### B.3 Benchmarks → design constraints (not marketing)

| System | WebArena | WebVoyager | Note |
|---|---|---|---|
| Vanilla GPT-4 (2023) | ~14% | — | humans ~78% on WebArena |
| Operator / CUA (2025) | 58.1% | 87% | also 38.1% OSWorld (human OSWorld ~72.4%) |
| browser-use (GPT-4o) | — | 89.1% (586 tasks) | open-source, edged Operator |
| Specialized RL agents (2026) | ~71–74% | — | OpAgent 71.6%, planner-grounder-reflector pipelines |

The Online-Mind2Web re-evaluation ("An Illusion of Progress?", Xue et al., COLM 2025) is the sobering counterweight: WebVoyager is near-saturated and partly solvable by search shortcuts — the paper notes "WebVoyager's tasks, 50% of which can be completed using [search shortcuts]," and its search-baseline agent scored just 22% on Online-Mind2Web versus 51% on WebVoyager. And as quoted above, most "advanced" agents underperform the simple 2024 SeeAct baseline. **Design implication:** do not encode a belief that the agent "usually succeeds." Instrument *every step* with intent + progress signals so the journey trace is evidence regardless of outcome.

#### B.4 The tool-layer primitives (what the package owns)

Deterministic, LLM-free, individually testable:

1. **`observe(strategy) -> Observation`** — affordance extraction. Pulls the ARIA snapshot (refs) and/or AX tree and/or screenshot; returns affordances `{ref, role, name, bbox?, enabled, editable}`. Pure read.
2. **`act(action) -> ActionResult`** — action execution. `click(ref)`, `type(ref, text)`, `select(ref, values)`, `navigate(url)`, `key(...)`, `scroll(...)`. Each returns success/error + a fresh `Observation`. Mirrors Playwright-MCP's `browser_click`/`browser_type` (which require both a human-readable description *and* a `ref` for safety).
3. **`journal(step) -> None`** — journey/intent logging. Appends a structured record per step: `{t, strategy, intent, action, target_ref, target_name, pre_obs_hash, post_obs_hash, network_delta, console_delta, screenshot_ref, outcome}`. This is the artifact that doubles as UX evidence.
4. **`progress(history) -> ProgressSignal`** — loop & no-progress detection. Deterministic signals: repeated `(tool, args_hash)` dedup, unchanged `post_obs_hash` across N steps, repeated identical errors, URL/AX-tree stasis. Returns `{repeated_action, no_new_signal_steps, loop_suspected}` — the *facts*; the host decides what to do with them.
5. **`snapshot_state() -> EvidenceBundle`** — bundles network/HAR/WS/SSE/console/storage/AX for the current step (the PART A machinery), keyed to the journal entry.

These compose functionally: `journal(progress(act(observe())))` per step, with the host choosing the action.

#### B.5 The host-agent policy layer (what the Claude Code skill instructs)

Judgment that should NOT be hard-coded in the package:

- **Strategy switching** — start with `AxSnapshot`; escalate to `Hybrid`/`Screenshot` when affordances are thin or an action fails to change state.
- **Next-action selection** toward the goal — the core LLM decision, fed `Observation` + `journal` tail.
- **Error recovery** — interpret an `ActionResult` error (stale ref → re-`observe`; element-not-found → scroll/disambiguate; auth wall → pause). browser-use's `_handle_step_error` (format error, store in history, retry with feedback, exponential backoff on rate limits) is the reference pattern, but the *decisions* are policy.
- **Bounding** — enforce `max_steps`, `max_failures`, wall-clock, and token/$ budgets; decide to stop on a `loop_suspected` signal. browser-use forces termination by restricting available actions to `done` when limits hit; the LoopGuard pattern (`max_steps`, `max_repeat`, `max_flat_steps`) is a good template the host applies using the package's `ProgressSignal`.

The split: the package *detects and reports* no-progress; the host *decides to abort*. The package *executes and validates* an action; the host *chooses* it and *interprets failure*.

#### B.6 Three operating strategies and their per-step intent logging

The package supports all three by varying *what intent the host writes to the journal*, while reusing the same primitives:

- **Crawl-and-map** — intent per step is *exploration*: `{intent: "enumerate", frontier_ref, why: "unvisited nav link"}`. The journal becomes a site/affordance map; progress = new URLs/AX-subtrees discovered.
- **Goal-pursuit** — intent is *goal-relative*: `{intent: "advance", subgoal, expected_effect}`. Progress = movement toward a success predicate; this is the WebArena/WebVoyager shape.
- **Guided-replay** — intent is *conformance*: `{intent: "replay", scripted_step_id, deviation?}`. Progress = steps matched vs. drift detected; pairs naturally with `route_from_har` for deterministic replay.

In all three, the per-step intent + pre/post observation + evidence bundle make the **journey trace itself the UX evidence** — you can answer "what did the user (agent) try, what did the app afford, what did it cost, where did it stall" without re-running.

#### B.7 What an optional later in-package agent would add

Lifting the loop into a self-contained Python agent (productizing later) would add, *on top of* the tool layer: an internal planner/policy (the LLM client now a dependency-injected component rather than the external host), a persistent memory/summary manager (browser-use's procedural-memory summaries), the LoopGuard/budget enforcement now owned internally, retry/backoff policy, and a `done`-validation step. Architecturally it's the same Facade with a new **default policy object injected** — the tool layer doesn't change, which is the payoff of the split.

---

## Recommendations

**Stage 1 — Adopt and wrap (now).** Build the capture facade on Playwright Python. Implement `observe/act/journal/progress/snapshot_state`. Use high-level APIs for request/response metadata, WS frames, console/exceptions, HAR (`.har.zip`, `record_har_content="embed"`), storage_state, and tracing. *Benchmark to advance:* you can drive a known multi-page app and reconstruct its full journey + network from the journal alone.

**Stage 2 — Attach CDP for the known gaps.** Add a `CdpCapture` plugin: `Accessibility.getFullAXTree` (per frame), `Network.eventSourceMessageReceived` (SSE), `Fetch`-stage body capture (eviction-proof), `Performance.getMetrics`, `Network.getCertificate`. *Threshold to trigger:* first time `response.body()` returns empty/evicts, or first SSE/full-AX requirement.

**Stage 3 — Add proxy only on evidence.** Introduce a mitmproxy plugin **only** when you hit one of: body-fidelity-at-scale, TLS/JA3 needs, service-worker traffic, or native traffic. *Threshold:* CDP Fetch interception is too slow or misses SW traffic in your workload.

**Stage 4 — Perception strategies + host skill.** Ship `AxSnapshot`/`Screenshot`/`Hybrid` perception plugins behind one `Observation` interface. Write the Claude Code skill that drives strategy-switching, recovery, and bounding using the package's `ProgressSignal`. Prefer the CLI+Skills shape (≈4× fewer tokens than streaming MCP) for the Claude Code host.

**Stage 5 (optional) — In-package agent.** Inject a default policy object (planner + memory + LoopGuard) implementing the same interface the host used. Keep stealth (`StealthProfile=None` default) and proxy as opt-in plugins with explicit ethical/ToS gating.

**Decision table — where does capability X live?**

| Capability | Playwright high-level | CDP session | Proxy | Tool layer | Policy layer |
|---|:--:|:--:|:--:|:--:|:--:|
| Request/response metadata, timings | ✅ | | | ✅ | |
| Response bodies (small) | ✅ | | | ✅ | |
| Response bodies (large/evicted) | | ✅ (Fetch) | ✅ | ✅ | |
| HAR export | ✅ | | | ✅ | |
| WebSocket frames | ✅ | | | ✅ | |
| SSE frames | | ✅ | ✅ | ✅ | |
| Console/exceptions | ✅ | | | ✅ | |
| Full accessibility tree | ⚠️ ARIA only | ✅ | | ✅ | |
| cookies/local/IndexedDB | ✅ | ⚠️ deep | | ✅ | |
| sessionStorage | ⚠️ manual | | | ✅ | |
| TLS/JA3 detail | | ⚠️ cert only | ✅ | ✅ | |
| Affordance extraction | ✅ | ✅ | | ✅ | |
| Action execution | ✅ | | | ✅ | |
| No-progress/loop detection | | | | ✅ | reports→ |
| Strategy switching | | | | | ✅ |
| Recovery / next action | | | | | ✅ |
| Bounding (steps/time/$) | | | | ⚠️ enforce hooks | ✅ |

---

## Caveats

- **Benchmark numbers are directional, not contractual.** WebVoyager is near-saturated and partly solvable by search shortcuts (~50% of tasks); the Online-Mind2Web work shows reported success rates are inflated and ranking is sensitive to evaluation method. Treat 87–89% figures as "good agents on easy tasks," not a reliability guarantee for arbitrary apps.
- **CDP is Chromium-only.** Every `new_cdp_session`-dependent capability (full AX tree, SSE via CDP, Fetch bodies, Performance metrics, certificate) does not exist on Firefox/WebKit under Playwright. If cross-browser capture matters, that tail must come from WebDriver BiDi (immature high-level APIs in mid-2026) or a proxy.
- **`Accessibility.getFullAXTree` is experimental and does not traverse cross-origin iframes;** you must recurse per frame, and `AXValue` objects (not strings) require careful field access.
- **IndexedDB/sessionStorage capture is partial in `storage_state`;** budget for `page.evaluate`/CDP fallbacks and expect provider-specific breakage (e.g., Firebase).
- **The exact deprecation version of `page.accessibility.snapshot()` is not cleanly documented;** it is confirmed deprecated and predates mid-2026, but pin your minimum Playwright version in CI rather than trusting a specific changelog entry.
- **Stealth tooling is an arms race with legal/ethical limits.** Treat anti-detect capability as off-by-default, scope it to authorized testing/research, and assume it requires continuous maintenance and clean IP reputation to function at all.

---

## REFERENCES

[1] [Network | Playwright Python](https://playwright.dev/python/docs/network)
[2] [Mock APIs | Playwright Python](https://playwright.dev/python/docs/mock)
[3] [Tracing | Playwright Python](https://playwright.dev/python/docs/api/class-tracing)
[4] [CDPSession | Playwright Python](https://playwright.dev/python/docs/api/class-cdpsession)
[5] [BrowserContext | Playwright Python](https://playwright.dev/python/docs/api/class-browsercontext)
[6] [WebSocket | Playwright Python](https://playwright.dev/python/docs/api/class-websocket)
[7] [Closer to the Metal: Leaving Playwright for CDP | Browser Use](https://browser-use.com/posts/playwright-to-cdp)
[8] [BUG: Response body missing for some responses · microsoft/playwright #23750](https://github.com/microsoft/playwright/issues/23750)
[9] [BUG: Request content was evicted from inspector cache · microsoft/playwright #13449](https://github.com/microsoft/playwright/issues/13449)
[10] [Authentication | Playwright](https://playwright.dev/docs/auth)
[11] [Feature: Save Session Storage when extracting Storage State · microsoft/playwright #38682](https://github.com/microsoft/playwright/issues/38682)
[12] [Feature: Support IndexedDB for shared auth · microsoft/playwright #11164](https://github.com/microsoft/playwright/issues/11164)
[13] [Snapshot testing (ARIA snapshots) | Playwright](https://playwright.dev/docs/aria-snapshots)
[14] [Internal: deprecate old accessibility API · microsoft/playwright #16159](https://github.com/microsoft/playwright/issues/16159)
[15] [How mitmproxy works](https://docs.mitmproxy.org/stable/concepts/how-mitmproxy-works/)
[16] [Proxy Modes | mitmproxy](https://docs.mitmproxy.org/stable/concepts/modes/)
[17] [Playwright MCP server | GitHub microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp)
[18] [Playwright MCP | Playwright](https://playwright.dev/docs/getting-started-mcp)
[19] [Snapshots | Playwright MCP](https://playwright.dev/mcp/snapshots)
[20] [Browser Use vs Stagehand vs Playwright MCP Compared (2026)](https://fp8.co/articles/Browser-Use-vs-Stagehand-vs-Playwright-MCP-AI-Agent-Browser-Automation)
[21] [Agent Execution Lifecycle | browser-use DeepWiki](https://deepwiki.com/browser-use/browser-use/2.1-agent-system)
[22] [Error handling and recovery | browser-use DeepWiki](https://deepwiki.com/browser-use/browser-use/2.4-error-handling-and-recovery)
[23] [Infinite Agent Loop: when an AI agent does not stop | Agent Patterns](https://www.agentpatterns.tech/en/failures/infinite-loop)
[24] [Computer-Using Agent | OpenAI](https://openai.com/index/computer-using-agent/)
[25] [An Illusion of Progress? Assessing the Current State of Web Agents (Online-Mind2Web), COLM 2025](https://arxiv.org/pdf/2504.01382)
[26] [WebVoyager: Autonomous Web Agent Benchmark | Emergent Mind](https://www.emergentmind.com/topics/webvoyager-benchmark)
[27] [Navigating the Digital World as Humans Do: Universal Visual Grounding for GUI Agents (SeeAct-V/UGround)](https://arxiv.org/pdf/2410.05243)
[28] [State-of-the-Art Autonomous Web Agents (2024–2025) | Medium](https://medium.com/@learning_37638/state-of-the-art-autonomous-web-agents-2024-2025-3d9d93a5dde2)
[29] [Web Agent Benchmarks Leaderboard: Apr 2026 | Awesome Agents](https://awesomeagents.ai/leaderboards/web-agent-benchmarks-leaderboard/)
[30] [Mind2Web | GitHub OSU-NLP-Group](https://github.com/OSU-NLP-Group/Mind2Web)
[31] [WebDriver BiDi Network Features | Selenium](https://www.selenium.dev/documentation/webdriver/bidi/network/)
[32] [BiDirectional functionality | Selenium](https://www.selenium.dev/documentation/webdriver/bidi/)
[33] [Stealth Overview | Camoufox](https://camoufox.com/stealth/)
[34] [Stealth Browsers for Scraping comparison | Scraping Central](https://scrapingcentral.com/blogs/stealth-browser-comparison)
[35] [Why less is more: The Playwright proliferation problem with MCP | Speakeasy](https://www.speakeasy.com/blog/playwright-tool-proliferation)
[36] [Playwright MCP and CLI: Making Browser Automation AI-Agent Friendly | ByteTunnels](https://bytetunnels.com/posts/playwright-mcp-and-cli-making-browser-automation-ai-agent-friendly/)
[37] [Performance Testing using Playwright | BrowserStack](https://www.browserstack.com/guide/playwright-performance-testing)
[38] [Interaction | Playwright MCP](https://playwright.dev/mcp/tools/interaction)
[39] [Why AI Can't Write Good Playwright Tests (And How To Fix It) | DEV](https://dev.to/johnonline35/why-ai-cant-write-good-playwright-tests-and-how-to-fix-it-knn)
[40] [Browser Use SOTA Technical Report (89.1% WebVoyager)](https://browser-use.com/posts/sota-technical-report)
[41] [Playwright MCP Server: How to Set Up, Configure & Use It (2026) | TestCollab](https://testcollab.com/blog/playwright-mcp)
[42] [AI Browser Automation Tools Comparison 2026 (token benchmarks) | ytyng](https://ytyng.com/en/blog/ai-browser-automation-tools-comparison-2026)