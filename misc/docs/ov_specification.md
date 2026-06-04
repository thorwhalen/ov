# `ov` — Specification for an Agent-Driven Web Reconnaissance & Analysis System

*Author: Thor Whalen*
*Status: Build specification (hand to an autonomous coding agent)*
*Primary consumption model: a host agent (Claude Code) wields `ov`'s tools via its skills — see §0.1. The package is a tool+skill library with a deterministic, model-free core; in-package agents are an optional Phase-4 lift.*
*Research status: all four deep-research reports integrated — D1 (capture & operation), D2 (architecture inference), D3 (UX & accessibility), D4 (grounded LLM analysis & orchestration). See §2/§3.3/§5/§6/§8/§9 and Phases 1–4.*

---

## 0. Reading guide for the implementing agent

This is a **build brief**, not pseudocode to transcribe verbatim. Your job is to deliver a package that **works end-to-end at every phase boundary** while being structured so the later phases slot in without rewrites. Prefer to ship Phase 1 fully working before scaffolding Phase 2.

Apply the loaded `python-coding-standards` and `python-package-architecture` skills throughout. The non-negotiables for this project:

- **Progressive disclosure.** `ov.observe(url)` must work with zero config and return something useful. Everything else is opt-in keyword arguments.
- **Facades over the messy tools.** Playwright, CDP, HAR parsing, etc. are dependencies hidden behind clean interfaces. The user (and the agents) never touch Playwright objects directly.
- **`Mapping`/`MutableMapping` stores** for everything persisted (artifacts, runs, traces). Capture is a *store of stores* (a Mall).
- **Plugin architecture** for both *probes* (what we collect) and *analyzers* (what we conclude). Adding a new analysis = registering a function, never editing a dispatcher.
- **Functions as data.** Capture steps, analyzers, and report sections are all just registered callables with declared inputs/outputs.
- **SSOT** for the artifact schema. One Pydantic model tree defines what a capture is; everything reads from it.
- **Host-agent oriented (read §0.1 — this overrides any contrary instinct below).** `ov` is a library of clean, individually-callable, tool-shaped functions plus a **skill layer** that teaches a host agent (Claude Code) how to orchestrate them. The orchestration/manager intelligence lives in the host, **not** in the package. Do **not** build an in-package multi-agent system in the near term.

---

## 0.1 Primary consumption model: a host agent (Claude Code) with skills

The near-term, primary way `ov` is used is **not** a standalone Python agent. It is this:

> The user tells Claude Code (or a similar capable host agent) *"go study this website/app,"* naming an `ov` skill. Claude Code loads that skill, which references the relevant `ov` tools and sibling skills, and **Claude Code itself is the manager** — it plans, calls the tools, observes results, decides next steps, recovers from failures, and assembles the output. `ov` supplies the **hands and eyes (tools)** and the **procedural knowledge (skills)**; the host supplies the **control loop**.

This is a deliberate architecture choice ("the harness is the agent"): a strong general host agent + well-scoped tools + a thin skill layer gets us a working agentic system *faster* than building a bespoke multi-agent orchestrator, and the tool+skill set it produces **is itself most of the specification** of the eventual productized agent system. Lifting it later = binding the same tools+skills under our own manager agent (a known, mechanical path; Thor already has a skills-with-tools → agents transform).

**Consequences for you, the implementer — apply these throughout:**

1. **Every capability is a clean, composable, individually-callable function** with a typed signature, a docstring written so an agent (and a human) knows exactly when and how to call it, informative errors, and structured (Pydantic) returns. Each is "tool-shaped": does one thing, states its inputs/outputs, no hidden global state. These are what get exposed to the host.
2. **The deterministic core must run with no model and no host.** Capture, deterministic analyzers, report rendering, and synopsis must be fully usable as plain Python / CLI. The host agent adds judgment *on top*; it is never required for the mechanical work. This is what keeps the system testable, cheap, and repeatable.
3. **Skills are a first-class deliverable**, shipped in `ov/.claude/skills/` (see §3.5). They are the orchestration spec in prose-for-an-agent form. The main skill (`study-web-app`) teaches the end-to-end workflow and points to focused sub-skills (operate, capture, analyze-ux, analyze-arch, report). Authoring these well *is* authoring the agent's policy.
4. **The in-package Python agents (`agents/`) are demoted to OPTIONAL and deferred to Phase 4** — they are the eventual "productize it as a self-contained agent" step, built by lifting the same tools+skills under a manager. Do not build them in Phases 1–3. Where the original draft below describes `agents/llm.py`, an in-package Operator agent, and Analyst agents as core, treat that as **Phase-4 / optional** and read "agent" as "the host (Claude Code), driven by our skills" for Phases 1–3.
5. **A CLI is still wanted** (`argh` dispatch) — but as a *second* interface over the same tool functions (dispatch-to-interface), and in the longer run the CLI may itself forward to a manager agent. Near-term it's the deterministic, scriptable face of the library.
6. **Host integration: prefer the CLI + Skills shape over an MCP server for the Claude Code host** *(revised per D1 research)*. The skills instruct the host to invoke `ov`'s CLI/functions directly. D1 cites Microsoft's own measurement that the Playwright **CLI** shape uses ~27k tokens vs ~114k for the equivalent **streaming MCP** on the same task (~4× reduction) — decisive for a Claude Code host. Treat an **MCP server (`py2mcp`) as the option for *other* hosts** or when you want per-tool schemas surfaced automatically — not the default path. (This reverses the earlier lean toward MCP-first.)

---

## 1. What `ov` is

`ov` (OverView / Observability Vehicle / Operator Vision) takes a **URL** (and optionally a *goal* or *journey script*), drives the target web app like a user, and records two parallel streams:

1. **The behavioral stream** — what the app *does*: pages, DOM snapshots, screenshots, navigation events, XHR/fetch/WebSocket traffic, console logs, performance timings, the user-journey trace.
2. **The static stream** — what the app *is made of*: HTML, bundled/unbundled JS/TS, CSS, source maps (when present), framework fingerprints, dependency manifests, asset inventory.

It then runs **two analysis lenses** over those streams:

- **UX analysis** — heuristics + LLM judgment about the experience: flows, friction, affordances, accessibility, information architecture, interaction patterns.
- **Software-design analysis** — frontend architecture reconstruction: framework, state management, routing, data-fetching patterns, component structure (as far as recoverable), API surface, build tooling.

Output is a set of **Markdown report files** plus the structured artifact store they're derived from. Reports are usable standalone, or fed to an **extract-and-aggregate** step that produces a single synopsis suitable for an AI agent to "re-create something similar" or "review our own system."

In the near term the "agent" is the **host (Claude Code), driven by `ov`'s skills** — `ov` supplies the **hands (operate tools)** and **eyes (observe/analyze tools)**, and the host supplies the manager/control loop (see §0.1). The conceptual roles are an **Operator** (drives the target) and an **Analyst** (observes and reasons, splittable into UX-Analyst and Arch-Analyst), but in Phases 1–3 these are *roles the host plays via skills*, not Python agent classes. Productizing them as in-package agents is the optional Phase-4 lift.

### The two target modes

- **Foreign target** (not ours): goal is *reconstruction-grade intelligence* — enough to rebuild a comparable system.
- **Own target** (ours): goal is *review* — UX critique, architecture audit, regression/drift detection over time.

These differ only in the *report framing* and the *baseline* (own-target runs can diff against a stored prior run). The capture and analysis machinery is identical. Keep this a parameter (`mode: "reconstruct" | "review"`), not a fork.

---

## 2. Capture taxonomy — what intelligence to gather

This is the substantive answer to "what should the observing agent gather." Group it into **probes**. Each probe is an independent, registerable unit that writes typed artifacts into the capture store.

### 2.1 Behavioral / runtime probes

| Probe | Captures | Primary tool |
|---|---|---|
| `dom_snapshot` | Full serialized DOM per significant state; **ARIA snapshot** (concise, ~200–400 tokens — the *agent's* view) plus full **AX tree** (`Accessibility.getFullAXTree`, recorded as *evidence*). Note: `name`/`role`/`value` are `AXValue` objects; tree doesn't cross-origin-recurse — recurse per frame | Playwright ARIA snapshot + CDP |
| `screenshot` | Full-page + viewport PNGs at each step; element screenshots for focal components | Playwright |
| `network` | Every request/response: URL, method, status, type, timing, headers, response bodies (size-capped, content-type-filtered), initiator chain. HAR via `.har.zip` + `record_har_content="embed"`. **Body caveat:** `response.body()` evicts for large/CDN'd bodies — fall back to CDP `Fetch`-stage capture | Playwright events + HAR; CDP `Fetch` for evicted bodies |
| `websocket` | WS frames (sent/received), open/close — first-class | Playwright `page.on("websocket")` → `framesent`/`framereceived` |
| `sse` | Server-Sent-Event frames (`event`/`id`/`data`) — **not** reliably reachable via `page.route` or `response.body()` | CDP `Network.eventSourceMessageReceived` (requires `Network.enable`) |
| `console` | console.log/warn/error, page errors, unhandled rejections | Playwright `console`/`pageerror` |
| `navigation` | URL changes (incl. SPA history pushState), redirects, frame tree | Playwright + CDP `Page.frameNavigated` |
| `perf` | Navigation Timing, Web Vitals (LCP/CLS/INP/TTFB/FCP), long tasks, resource timing; runtime counters via CDP `Performance.getMetrics` (Chromium) | `web-vitals` injected + Performance API + optional Lighthouse |
| `storage` | cookies, localStorage via `storage_state`; **sessionStorage manual** (not in `storage_state`); **deep IndexedDB** via `page.evaluate`/CDP (storage_state serialization is fragile). Values redacted by default — privacy | `storage_state` + evaluate/CDP fallbacks |
| `runtime_globals` | `window` keys, detected framework hooks (`__NEXT_DATA__`, `__NUXT__`, `__remixContext`, React/Vue devtools globals) | injected JS |
| `interaction_trace` | The ordered journey: per step intent, action, target ref/name, pre/post observation hash, network/console deltas, screenshot ids, outcome | `operate/journal` emits these |

### 2.2 Static / resource probes *(tool choices validated by D2 research)*

Every inferred fact below carries a **confidence score (0–100)** and **provenance** (which artifact/journey produced it). Treat all outputs as probabilistic, never ground truth — map-backed reconstructions rank strictly above name-lost (un-mapped) ones.

| Probe | Captures | Primary tool |
|---|---|---|
| `assets` | All loaded resources saved to disk, content-addressed; MIME, size, hash, URL | from `network` stream |
| `rendering_model` | CSR vs SSR vs SSG vs streaming-SSR. **Deterministic test:** fetch raw HTML with JS disabled and diff against the JS-rendered DOM (large divergence ⇒ CSR; near-identity ⇒ SSR/SSG; distinguish SSG/SSR by varying a request); corroborate with state-injection globals | raw-fetch + DOM diff |
| `tech_fingerprint` | Framework/library/CDN/analytics/hosting + **versions**, each with confidence | `wappalyzer-next` (PyPI `wappalyzer`, `full` mode = Wappalyzer extension in Playwright Chromium) over `enthec/webappanalyzer` rules; prefer `js`/`dom` signals over loose `html` regex (false-positive source) |
| `vuln_inventory` | Known-vulnerable library versions, CVE/OSV-backed; CycloneDX SBOM | **Retire.js** CLI (shell out to maintained Node CLI; don't run page JS in-process) |
| `js_bundles` | **Source maps are the decisive variable (bimodal):** if present, recover original file tree + source text + `node_modules/` version paths; if absent, unpack to per-module files (names lost) | maps: `source-map` / `unwebpack-sourcemap` / `source-map-explorer`; no-maps: `webcrack` / `wakaru` + beautify |
| `in_bundle_data` | Route tables, API base URLs, feature flags, embedded config surviving as string literals | static **AST extraction** (Babel/acorn in sidecar) — never `eval` downloaded JS |
| `dependency_inventory` | Libraries + versions, with provenance (sourcemap path > bundle comment > global signature) | sourcemap `node_modules/` paths + heuristics |
| `api_surface` | Endpoints, inferred request/response **JSON Schemas**, REST/RPC/GraphQL class, auth scheme, realtime shapes — merged across journeys with **coverage/confidence** | `GenSON` (the schema-merge primitive `ov` owns) + `mitmproxy2swagger` (path discovery) + `Optic` (stable patchable master spec); GraphQL: introspection → `Clairvoyance` |
| `routing_map` | Client routes (from in-bundle router config, nav trace, `<a href>` crawl) | static + dynamic merge |
| `build_artifacts` | Bundler signatures (webpack `__webpack_require__`/`webpackChunk`; Vite `import.meta.hot`/`modulepreload`; Turbopack; esbuild `__esm`; Rollup), chunking, hashing | bundle signature scan |

### 2.3 The operate primitives and the tool/policy boundary *(refined per D1 research)*

The operation layer is **two cleanly separated planes**. The package owns the deterministic, LLM-free, individually-testable **tool layer**; the host (Claude Code, via skills) owns the **policy layer**. The dividing principle: *anything specifiable deterministically and testable without an LLM is a tool; anything requiring goal-relative judgment is policy.*

**Tool-layer primitives (`operate/`, no model, composable as `journal(progress(act(observe())))`):**

1. `observe(strategy) -> Observation` — affordance extraction; returns `{ref, role, name, bbox?, enabled, editable}` per element. Pure read. `strategy` selects perception (below).
2. `act(action) -> ActionResult` — `click(ref)`, `type(ref, text)`, `select`, `navigate(url)`, `key`, `scroll`. Each returns success/error **plus a fresh `Observation`**. (Mirrors Playwright-MCP's require-description-and-ref safety.)
3. `journal(step) -> None` — appends the structured per-step record (the `interaction_trace` artifact; doubles as UX evidence).
4. `progress(history) -> ProgressSignal` — deterministic loop/no-progress **facts**: repeated `(tool, args_hash)`, unchanged post-observation hash across N steps, repeated errors, URL/AX stasis. Returns the signal; **does not decide to stop**.
5. `snapshot_state() -> EvidenceBundle` — bundles the §2.1/2.2 capture for the current step, keyed to the journal entry.

**Perception is a strategy plugin** returning a uniform `Observation`: `AxSnapshot` (ARIA refs — cheap, deterministic, default), `Screenshot` (pixels + bbox — universal, for canvas/exotic renderers), `Hybrid` (AX-grounded with vision fallback — the robust default when AX is thin). The host picks per step; the package stays declarative about *what* an observation is, not *how* it's grounded.

**Policy layer (the host, via the `ov-operate` skill) decides:** which strategy and when to escalate; the next action toward the goal; how to interpret/recover from an `ActionResult` error (stale ref → re-observe; not-found → scroll/disambiguate; auth wall → pause); and when to stop (enforcing `max_steps`/`max_failures`/wall-clock/$ budgets, aborting on a `loop_suspected` signal). **The package detects and reports no-progress; the host decides to abort.**

**The three strategies reuse the same primitives, varying only the intent written to the journal:** crawl-and-map (`intent: enumerate`, progress = new URLs/AX-subtrees), goal-pursuit (`intent: advance` toward a success predicate), guided-replay (`intent: replay` a scripted step, pairs with `route_from_har` for deterministic replay). In all three the per-step intent + pre/post observation + evidence bundle make **the journey trace itself the UX evidence**.

**Design note (don't over-trust the agent):** web-agent benchmarks show even strong agents are unreliable on arbitrary apps (Online-Mind2Web found many underperform a simple 2024 baseline). So `ov` instruments *every step* with intent + progress facts and treats the trace as evidence **regardless of task success** — never assume the agent "usually succeeds."

---

## 3. Package architecture

### 3.1 File structure

```
ov/
  pyproject.toml
  README.md
  CLAUDE.md
  ov/
    __init__.py            # progressive-disclosure facade: observe(), analyze(), report()
    base.py                # SSOT artifact schema (Pydantic models), core dataclasses
    util.py                # internal helpers, check_requirements
    __main__.py            # argh CLI dispatch
    config.py              # settings (keyword-only defaults, env overrides)

    capture/
      __init__.py
      session.py           # CaptureSession: owns the browser, orchestrates probes
      browser.py           # Playwright facade (launch, context) — the baseline driver
      cdp.py               # CDP "escape hatch" plugin: full AX tree, SSE, Fetch bodies,
                           #   Performance.getMetrics, cert. Chromium-only. (see §9, D1)
      proxy.py             # OPTIONAL opt-in mitmproxy plugin (off by default; see §6/§9)
      probes/
        __init__.py        # PROBE_REGISTRY + register_probe decorator
        network.py         # request/response metadata + HAR(.zip, embed); body via cdp.py
        dom.py             # DOM + ARIA snapshot (agent view) + full AX tree (evidence)
        screenshot.py
        console.py
        perf.py            # Performance.getMetrics via cdp.py (Chromium)
        storage.py         # storage_state; sessionStorage + deep IndexedDB via evaluate/CDP
        websocket.py       # high-level page.on("websocket") frame capture
        sse.py             # SSE frames via CDP Network.eventSourceMessageReceived
        fingerprint.py
        assets.py
        sourcemaps.py
      stores.py            # CaptureStore (Mall): MutableMapping facades over the run dir

    operate/               # deterministic, LLM-free tool primitives (the "hands")
      __init__.py
      observe.py           # observe(strategy) -> Observation  (affordances {ref,role,name,bbox?,...})
      act.py               # act(action) -> ActionResult  (click/type/select/navigate/key/scroll)
      journal.py           # journal(step) -> None  (per-step intent + pre/post hashes + deltas)
      progress.py          # progress(history) -> ProgressSignal  (loop/no-progress FACTS, no LLM)
      perception.py        # perception strategy plugins: AxSnapshot | Screenshot | Hybrid
      strategies.py        # journey-strategy helpers (crawl / goal / guided) — intent shaping
      driver.py            # scripted/guided driver (Phase 1, no model); composes the above

    analyze/
      __init__.py          # ANALYZER_REGISTRY + register_analyzer decorator
      ux/
        __init__.py
        a11y.py            # axe-core (per state) + IBM Equal Access; WCAG/ACT mapping
        contrast_focus.py  # contrast ratios, tab order, keyboard traps, focus visibility
        cwv.py             # per-step Core Web Vitals attribution (web-vitals/attribution)
        metrics.py         # journey metrics: success, steps-to-goal, backtracking, form friction
        heuristics.py      # rule-based Nielsen/CW subset (feedback, console-on-step, labels, live-region)
        severity.py        # severity = impact_tier × reach scoring
        llm.py             # OPTIONAL/Phase-4: bounded LLM judgment (grounded, evidence-id-cited)
      arch/
        __init__.py
        pipeline.py        # fingerprint >> bundle_recovery >> api_synthesis (composable transforms)
        rendering.py       # CSR/SSR/SSG classifier (JS-disabled HTML vs rendered DOM diff)
        framework.py       # framework/state/routing detection (globals, signatures)
        bundles.py         # source-map detection/recovery; no-maps unpack; literal extraction
        api.py             # API surface synthesis (GenSON merge, REST/RPC/GraphQL, auth, realtime)
        dependencies.py    # dependency + vuln (Retire.js) + build/bundler analysis
        sidecar.py         # Python facade over the Node JS-RPC sidecar (§6.1)
        llm.py             # OPTIONAL/Phase-4: LLM architecture reconstruction
      evidence.py          # evidence-bundle assembler (§8.1): SoM marks, image-first,
                           #   w×h/750 token budget, full-vs-crop, facts-by-id, cite-or-abstain

    agents/                # OPTIONAL — Phase 4 only. NOT built in Phases 1-3.
      __init__.py          #   (the near-term "agent" is the host: Claude Code + skills)
      llm.py               #   provider-agnostic LLM facade, structured-output helper
      operator_agent.py    #   productized: binds Operator tools + LLM into an agent loop
      analyst_agent.py     #   productized: binds Analyzers + LLM into UX/Arch analysts

    report/
      __init__.py          # REPORT_SECTION_REGISTRY + register_section decorator
      render.py            # assemble Markdown from analysis artifacts
      synopsis.py          # extract-and-aggregate across reports -> single synopsis
      templates/           # Markdown section templates (data/ resources)

    data/                  # rulesets (fingerprints), prompt templates, injectables:
                           #   axe-core, IBM ace.js, web-vitals/attribution bundles
  sidecar/                 # thin Node sidecar (§6.1): JS-only reverse-eng tooling
    package.json           #   source-map, webcrack, wakaru, quicktype, optic, retire
    server.js              #   newline-delimited JSON-RPC 2.0 over stdio; stateless pure fns
  .claude/
    skills/                # FIRST-CLASS DELIVERABLE — the orchestration spec for the host
      study-web-app/       #   main skill: end-to-end "go study this app" workflow
        SKILL.md           #   teaches the workflow; points to the sub-skills below
      ov-operate/SKILL.md  #   how to drive the target (crawl/goal/guided) via ov tools
      ov-capture/SKILL.md  #   how to run capture probes & inspect the store
      ov-analyze-ux/SKILL.md
      ov-analyze-arch/SKILL.md
      ov-report/SKILL.md   #   how to render reports + synopsis
  tests/
  ov/misc/
    docs/                  # architecture notes, research outputs land here
    CHANGELOG.md
```

> **`agents/` is optional and deferred.** In Phases 1–3 the manager is Claude Code, orchestrating via `.claude/skills/`. The `agents/` package is the Phase-4 "productize as a self-contained agent" lift — built by binding the *same* tool functions + skill logic under our own manager and an `llm.py` facade. Build it only when that productization is the goal.

### 3.2 The three core registries (plugin architecture)

Everything extensible is a **decorated function registered into a dict**. This is the open-closed mechanism.

```python
# capture/probes/__init__.py
PROBE_REGISTRY: dict[str, Probe] = {}

def register_probe(name, *, requires=(), produces=()):
    """Register a capture probe. `requires`/`produces` declare artifact deps for ordering."""
    def deco(fn):
        PROBE_REGISTRY[name] = Probe(name=name, fn=fn, requires=requires, produces=produces)
        return fn
    return deco
```

Identical pattern for `ANALYZER_REGISTRY` (analyze/) and `REPORT_SECTION_REGISTRY` (report/). A run is then just: resolve registry → topologically order by declared deps → execute → write artifacts. The DAG ordering is exactly the `meshed`-style dataflow you favor; use `meshed` if it fits cleanly, else a minimal local topo-sort (keep the dependency optional).

### 3.3 SSOT artifact schema (`base.py`)

One Pydantic v2 model tree is the single source of truth for "what a capture contains." Sketch:

```python
class Scored(BaseModel):
    """Mixin for every inferred (non-observed) fact. D2: outputs are probabilistic."""
    confidence: int         # 0-100 (Wappalyzer-style; API coverage maps onto this)
    provenance: list[str]   # artifact/journey ids that produced this fact
    # map-backed reconstructions must rank above name-lost (un-mapped) ones

class Artifact(BaseModel):
    kind: str               # "screenshot" | "dom" | "request" | "ax_tree" | "sse" | ...
    step_id: str | None     # links to a journey step
    uri: str                # content-addressed path in the store
    meta: dict

class Evidence(BaseModel):  # D4: the addressable unit an LLM claim must cite
    evidence_id: str        # stable id: "mark:state12#R3" | "net:fact88" | "metric:step7:inp"
    kind: Literal["mark", "network", "stack", "metric", "dom", "trace"]
    artifact_id: str | None # resolves (via a tool) to the screenshot crop / record / metric
    summary: str            # the derived fact (NOT raw bytes) the model is allowed to see

class JourneyStep(BaseModel):
    id: str
    intent: str             # the step's stated goal (enumerate | advance | replay)
    action: Action          # what it did
    affordances_seen: list[Affordance]
    outcome: Literal["ok", "blocked", "error", "noop"]
    artifact_ids: list[str]
    t_ms: float

class TechFinding(Scored):  # one detected technology
    name: str; categories: list[str]; version: str | None

class Endpoint(Scored):     # one synthesized API endpoint
    method: str; path_template: str
    kind: Literal["rest", "rpc", "graphql"]
    request_schema: dict | None; response_schema: dict | None  # GenSON-merged
    auth: str | None        # bearer | cookie | oauth | api-key | None

class Severity(BaseModel):  # D3: severity = impact_tier × reach
    impact_tier: str        # a11y: minor|moderate|serious|critical ; ux: "0".."4"
    reach: dict             # {nodes, states_affected, journey_fraction}
    score: float            # impact × reach (prioritizes high-reach over rare-critical)

class Finding(BaseModel):   # SSOT for every UX / a11y / perf / arch / robustness finding (D3+D4)
    finding_id: str
    type: Literal["ux_issue", "arch_fact", "interaction_pattern", "risk", "undetermined"]
    signal: str             # catalog key, e.g. "contrast.text", "form.friction"
    category: Literal["a11y", "ux", "performance", "robustness", "architecture"]
    wcag_criterion: dict | None     # {id: "1.4.3", level: "AA"}
    heuristic: str | None           # "nielsen-1" | "cw-q3" | None
    engine_rule_id: str | None      # "axe:color-contrast" | "ibm:<id>" | None
    severity: Severity | None
    # D4: hard split — facts are CITED, never authored, by the model
    evidence_refs: list[str]        # Evidence ids; a finding with none is rejected (cite-or-abstain)
    judgment: str | None            # model interpretation ONLY (never a fact field)
    location: dict | None           # {state_id, url_or_route, step_index, selector, ...}
    observed: str                   # what the deterministic signal detected
    metric_detail: dict | None      # e.g. CWV value/threshold/attribution phases
    suggested_fix: str | None       # LLM-generated, grounded
    source_layer: Literal["deterministic", "llm"]   # auditable provenance
    confidence: float
    needs_human_review: bool        # routes the non-automatable ~60-70% to humans
    diff_status: Literal["new", "changed", "resolved"] | None  # review-mode vs prior run

class CaptureRun(BaseModel):
    run_id: str
    target_url: str
    mode: Literal["reconstruct", "review"]
    started_at: datetime
    steps: list[JourneyStep]
    fingerprint: list[TechFinding]
    rendering_model: str | None    # csr | ssr | ssg | streaming-ssr (Scored elsewhere)
    source_maps_present: bool | None   # the decisive reconstruction-grade lever (D2)
    api_surface: list[Endpoint]
    findings: list[Finding]        # UX + a11y + perf findings (D3)
    # artifacts live in the store, referenced by id; not inlined
```

### 3.4 Stores — `MutableMapping` Mall (`capture/stores.py`)

A run directory is exposed as a Mall of stores. Use `dol` for the filesystem-backed mappings (you already favor this).

```python
class CaptureStore:
    """A store of stores for one or many runs (XDG-aligned root by default)."""
    def __init__(self, root):
        self.runs        = ...  # MutableMapping[run_id, CaptureRun JSON]
        self.artifacts   = ...  # MutableMapping[artifact_id, bytes]  (content-addressed)
        self.reports     = ...  # MutableMapping[report_name, markdown_str]
        self.analyses    = ...  # MutableMapping[analysis_id, analysis JSON]
```

Content-address artifacts by hash so identical assets dedupe across runs; this makes own-target diffing cheap.

### 3.5 The skill layer (`ov/.claude/skills/`) — first-class deliverable

This is how the host agent (Claude Code) is taught to orchestrate `ov`. The skills *are* the near-term agent's policy; treat authoring them with the same care as code. Each is a `SKILL.md` (with optional supporting files) following the standard skill format. Keep each skill focused; the main one composes the rest.

- **`study-web-app/SKILL.md`** (main) — triggered by requests like *"go study/audit this web app."* Teaches the full workflow: confirm authorization & mode (reconstruct vs review), call capture, decide a journey strategy, drive it, run analyzers, render reports + synopsis. It explicitly **points to the sub-skills** below and tells the host when to load each. It also encodes the manager behaviors that would otherwise be agent code: bounding (max steps/time), no-progress detection, when to go breadth (crawl) vs depth (goal), and how to recover from a blocked/error step.
- **`ov-operate/SKILL.md`** — how to drive the target: the three strategies (crawl-and-map / goal-pursuit / guided-replay), how to read affordances from a page, how to choose and execute the next action, and how to **log per-step intent** into the journey trace.
- **`ov-capture/SKILL.md`** — how to launch a capture session, which probes to enable for a given goal, and how to inspect the resulting store.
- **`ov-analyze-ux/SKILL.md`** and **`ov-analyze-arch/SKILL.md`** — how to run the deterministic analyzers, assemble an **evidence bundle**, and (when judgment is wanted) reason over it directly as the host to produce narrative UX critique / architecture blueprint. In Phases 1–3 *the host performs this reasoning*; no in-package LLM call is needed.
- **`ov-report/SKILL.md`** — how to render report sections and produce the synopsis.

Design rule: **the skills call the same tool functions the CLI calls.** A skill should never need package internals that a normal caller couldn't reach. If a skill wants something awkward to express as a tool call, that's a signal to improve the tool's API, not to special-case the skill. This keeps the eventual `agents/` lift mechanical — the manager agent will bind the very same tools.

Authoring notes (D4): follow the Agent Skills format (`SKILL.md` with `name`/`description` frontmatter + Markdown body; optional `scripts/`/`references/`/`assets/`). Only `name`+`description` load at startup and the body loads on trigger, so a many-skill library stays light on context. Write a **trigger-rich `description`** (hosts under-trigger), prefer "explain-the-why" over ALL-CAPS imperatives, keep skills small and split files past ~300 lines. **Audit any third-party skill before bundling** — Snyk's Feb-2026 "ToxicSkills" audit found a large fraction of public skills carried security flaws; treat skills as executable supply chain.

---

## 4. The top-level facade (progressive disclosure)

`ov/__init__.py` exposes a tiny surface. Everything below is reachable but not required.

```python
def observe(url, *, goal=None, journey=None, mode="reconstruct",
            probes="default", headed=False, store=None) -> CaptureRun:
    """Drive the target and capture everything. Zero-config default works."""

def analyze(run, *, lenses=("ux", "arch"), llm=None) -> dict[str, Analysis]:
    """Run the deterministic UX + architecture analyzers over a captured run.
    Runs fully without a model (llm=None) — this is the default and the only path
    needed in Phases 1-2. The host agent (Phase 3) reasons over the returned
    analyses + evidence bundle to add narrative judgment; an in-package `llm` is
    only wired in the optional Phase-4 productization."""

def report(run_or_analyses, *, sections="default", out_dir=None) -> list[Path]:
    """Render Markdown reports from analyses."""

def synopsis(reports_or_dir, *, out=None) -> Path:
    """Extract-and-aggregate many reports into one synopsis for downstream agents."""

def overview(url, **kw) -> Path:
    """observe -> analyze -> report -> synopsis, the one-liner. Returns synopsis path."""
```

`ov.overview("https://example.com")` is the pit-of-success entry point.

CLI mirrors this via `argh` (`__main__.py`): `ov observe <url>`, `ov analyze <run_id>`, `ov report <run_id>`, `ov synopsis <dir>`, `ov overview <url>`. Same functions, dispatched — the dispatch-to-interface pattern.

---

## 5. UX & accessibility analysis — what to observe and how to derive intelligence *(structure validated by D3 research)*

Two layers in strict order: a **deterministic engine** (fast, reproducible, the source of truth) then a **bounded LLM layer** (narrative + grounded subjective judgment only). The deterministic stage is the legally/conformance-relevant one; the LLM never *detects* facts, it interprets the evidence bundle. All output normalizes into the `Finding` schema (§3.3) with `severity × reach`.

**Hard honesty constraint (D3):** automated accessibility tooling catches only ~30–40% of WCAG issues (Deque: automatable for 16/50 WCAG 2.1 AA criteria). `ov` must **never report "no automated violations" as "accessible"** — the non-automatable ~60–70% (meaningful alt text, logical reading/focus order, descriptive-in-context link text, screen-reader announcement quality, ARIA *intent*) is explicitly routed to humans via the `needs_human_review` flag, never asserted as resolved.

### 5.1 The deterministic engine (no LLM)

Runs over the captured states (screenshots, DOM, a11y tree, journey trace, console, perf) and emits normalized `Finding`s:

1. **Accessibility scan** — inject **axe-core** (`@axe-core/playwright`, `.analyze()` scans current DOM, so run it *per captured state* to catch SPA/modal/revealed-menu states) with `wcag2a/wcag21aa/wcag22aa` tags; optionally **IBM Equal Access** as a second engine for explicit WCAG-criterion/ACT mapping. Persist each violation's rule id, impact, WCAG tags, node targets. The six WebAIM-Million perennials (low contrast, missing alt, missing form labels, empty links, empty buttons, missing doc language) are ~96% of detected errors — nail these.
2. **Contrast & focus** — compute WCAG contrast ratios from computed styles (deterministic luminance formula; 4.5:1 normal / 3:1 large+UI); analyze a11y-tree tab order + key-drive logs for reachability, keyboard traps, focus-order divergence, visible-focus indicator.
3. **Per-step CWV attribution** — see §5.3.
4. **Journey metrics** — from the trace + nav graph: task success (terminal goal state reached), time-on-task, steps-to-goal (actual/optimal ratio), backtracking/dead-ends (revisited/no-progress states), **form friction** = f(field_count, required_count, corrections, time_per_field) — note the sharp conversion cliff at 5–7 fields.
5. **Rule-based heuristic signals** — the automatable subset of Nielsen/cognitive-walkthrough: feedback-after-action (DOM/`aria-live` change within a window), console-error-on-step, inconsistent labels for same target, live-region presence (4.1.3).
6. **Normalize** each into the `Finding` schema; attach WCAG/heuristic mapping and `severity × reach`. **Source of truth.**

Each Nielsen heuristic and cognitive-walkthrough question maps to a machine-observable signal — crucially, the Operator's **stated per-step intent** gives a ground-truth "expected action" to compare against what the interface actually afforded (the cognitive-walkthrough Q1–Q4 enabler).

### 5.2 The bounded LLM layer (narrative + grounded judgment only)

Receives **only** the evidence bundle (annotated screenshots with bounding boxes / set-of-marks on the offending element + step intent, the deterministic findings, relevant DOM/a11y snippets) — never raw bytes, never the live page. Its jobs: (a) human-readable explanations + suggested fixes; (b) the genuinely subjective items with no deterministic detector — alt-text *meaningfulness*, error-message *helpfulness*, label↔intent semantic match, microcopy/empty-state quality, focus-order *logicality*; (c) cluster and prioritize.

**Anti-hallucination grounding rules (mandatory — D3 + D4; constructed by the §8.1 evidence-bundle assembler):**
- **Fact/judgment split.** Each `Finding` separates `evidence_refs` (citations into the deterministic `Evidence` store) from `judgment` (model text). The model **may cite a fact field, never populate one**.
- **Cite-or-abstain.** Every claim references at least one `evidence_ref`; a finding with no resolvable evidence is **rejected**, and "can't tell from the evidence" is a first-class schema value (`type="undetermined"`), not an error.
- **Set-of-Mark grounding.** Vision is used **only to describe/judge marked regions** (each carries a stable mark id like `R3` that also appears in the facts and is required in the output), **never to scan for new issues**.
- **Structured output guarantees shape, not truth.** Constrain decoding to the Pydantic `Finding` schema, then run a **factored Chain-of-Verification** pass over high-severity findings (re-check each against the deterministic store) and an **NLI/faithfulness gate**; discard or downgrade to `undetermined` any finding whose cited evidence doesn't entail it.
- LLM findings carry `confidence` and `needs_human_review`; `source_layer="llm"` keeps the two layers auditable. Single-pass severity is noisy — prefer multiple sampled passes or the verification pass, and state uncertainty.

For *reconstruct* mode the LLM also infers **design intent** and produces a reusable **interaction-pattern catalog**; for *review* mode, a **critique with concrete fixes** and (if a prior run exists) a **UX regression diff**.

### 5.3 Performance-as-UX: per-step CWV attribution (D3)

Use the **`web-vitals` attribution build** (`web-vitals/attribution`) injected into the page; collect via `PerformanceObserver` with `buffered:true`. The harness records each step's wall-clock window and **buckets `PerformanceEntry`s into the step they occurred in**, naming the offending DOM element:
- **INP** — group `event`-timing entries by `interactionId`, max duration per interaction; attribute via `interactionTarget` + phase breakdown (`inputDelay`/`processingDuration`/`presentationDelay`). Threshold 200 ms.
- **CLS** — sum `layout-shift` `value` per step **excluding `hadRecentInput`**; culprit via `largestShiftTarget`. Threshold 0.1.
- **LCP/FCP/TTFB** — per-page-load by nature; for classic CWV only the initial-load step gets them. True per-route values on SPA soft navigations need the experimental **Soft Navigations API** — until adopted, **label LCP/FCP as initial-load-only** (provisional). Use `generateTarget()` for stable cross-build element identifiers.

### 5.4 Driving into empty/error/loading states (an Operator instruction)

Microcopy and recovery problems concentrate in states automation is otherwise blind to. The `ov-operate` skill should deliberately drive the agent into them: empty states (new account, filtered-to-zero, cleared cart), error states (invalid/blank/oversized form input, bad route → 404, wrong credentials), and loading/latency states. The deterministic engine then checks: is the error specific + human, tied to the field via `aria-describedby`/`aria-invalid`, with a recovery path; do empty states explain next steps; do console errors corroborate broken states.

---

## 6. Software-design analysis — reconstructing the frontend

Implemented as a **three-stage deterministic pipeline** (D2): `fingerprint → bundle-recovery → api-synthesis`, each a composable `Artifacts → Artifacts` transform accumulating confidence. Python orchestrates, scores, and merges; a thin **Node sidecar** runs the JS-only tooling (see §6.1). The Arch-Analyst (host or, later, the in-package agent) reasons over the resulting scored facts.

**The single biggest lever is source-map presence — reconstruction quality is bimodal.** With maps you recover the original file/module tree, source text, component boundaries, and `node_modules/` version paths (reconstruction-grade). Without them you get a beautified-but-renamed approximation — structure and string literals, not original identifiers. So **Stage-1 attempts source-map recovery before anything harder** (read `//# sourceMappingURL=`, try appending `.js.map`, probe staging/dev hosts), and the `source_maps_present` flag gates the reconstruction-confidence ceiling everywhere downstream.

What the pipeline reconstructs:

- **Framework & rendering model:** React/Vue/Svelte/Angular/vanilla; CSR/SSR/SSG/streaming via the JS-disabled-HTML-vs-rendered-DOM diff plus state-injection globals (`__NEXT_DATA__`, `__NUXT__`, `__remixContext`).
- **State management:** Redux/Zustand/Recoil/Pinia/Vuex/signals — runtime globals, devtools hooks, bundle signatures.
- **Routing:** client router + recovered route map (in-bundle router config + nav trace + `<a href>` crawl).
- **Data layer:** REST vs GraphQL vs RPC (classifier: single-endpoint+`query` ⇒ GraphQL; verb-paths+all-POST ⇒ RPC; noun-paths+method-diversity ⇒ REST); synthesized **API surface** (`GenSON`-merged schemas across journeys, with coverage/confidence); auth scheme (bearer/cookie/OAuth/api-key from headers); caching (React Query/SWR/Apollo signatures); realtime (WS frames from HAR `_webSocketMessages[]`, SSE from `text/event-stream`).
- **Component structure:** from source maps when present (file tree is gold); otherwise inferred from DOM + bundle module graph (`webcrack`/`wakaru`).
- **Build & delivery:** bundler signature, code-splitting/chunking, hashing, CDN/edge.
- **Dependency inventory + known vulns:** versions with provenance (sourcemap path > bundle comment > global signature); Retire.js for CVE-backed vulnerable libraries + CycloneDX SBOM.

Deterministic detectors produce **scored** structured facts; the LLM layer turns the fact set into a **reconstruction blueprint** ("to rebuild a comparable system, use [stack], structured as [layers], with [these routes], talking to [this API shape], managing state via [pattern]") — explicitly marking map-backed claims as higher-confidence than name-lost ones. For *review* mode it produces an **architecture audit**: coupling/risk observations, drift vs. prior run, dependency-currency/security flags (advisory only).

### 6.1 The Node sidecar boundary (D2)

The mature reverse-engineering tooling (`source-map`, `webcrack`, `wakaru`, Optic, quicktype) is JavaScript; orchestration/scoring/persistence is Python's. Keep the boundary **coarse, declarative, stateless**:

- A long-lived Node sidecar exposing a small versioned set of **pure functions** — `consumeSourceMap(mapJson) → {files}`, `unpackBundle(jsText) → {modules}`, `extractLiterals(jsText) → {strings, urls, routes}`, `inferSchema(samples) → jsonSchema`, `patchOpenAPI(spec, har) → spec` — over **newline-delimited JSON-RPC 2.0 on stdio** (same transport MCP uses; no port/HTTP overhead; sub-process-bound, no network exposure of a tool ingesting untrusted JS). If `ov` ever scales out, the same JSON-RPC contract moves to HTTP.
- **Define the wire contract once** as Pydantic models mirroring the sidecar's types — dependency inversion at the process level, a single swappable interface.
- **Safety: never `eval` or run downloaded JS in-process.** Static AST extraction only (Babel/acorn). If dynamic execution is ever truly needed, it goes in a disposable, network-isolated headless browser — never the sidecar process.

### 6.2 Tool-availability caveats (verify at build time — D2)

`Optic` was acquired by Atlassian (Apr 2024; standalone site gone, folded into Compass) and Akita by Postman (2023) — prefer the self-hostable OSS core (`GenSON`, `mitmproxy2swagger`, `source-map`, `webcrack`) and verify any hosted tool before depending on it. `wappalyzer-next` packaging is in flux — pin a known-good version. The original Wappalyzer ruleset went private in 2023; use the `enthec/webappanalyzer` (GPLv3) fork. Note GPL-3.0 licensing on `wappalyzer-next` and the rules — check compatibility with `ov`'s intended license.

> **Boundary note for the agent:** `ov` collects and analyzes *publicly served* frontend material and observable network behavior of targets the user is authorized to inspect. Do **not** implement credential bruteforcing, auth bypass, rate-abusive crawling, or anything that defeats access controls. Reverse-engineering deployed JS you don't own can implicate ToS / anti-circumvention (DMCA §1201) / computer-misuse law — default to authorized targets and record provenance. Respect `robots.txt`-style intent as a configurable default, add a polite-rate default, and surface an explicit `authorized=True` acknowledgement in the API for foreign targets. Keep secret/PII capture off by default (storage probe redacts values); be aware that API-synthesis examples/headers and unverified JWTs in captured traffic can embed secrets — redact before persisting. (L1 will set the full default-settings checklist.)

---

## 7. The "agents": host-first now, in-package later

The manager intelligence is **not** in the package in Phases 1–3. It is the **host agent (Claude Code) driven by the skills in §3.5.** The Operator and Analyst are *roles the host plays*, not classes you build yet.

**Phases 1–3 (primary product):**
- **Operator role** = the host, following `ov-operate`, calling the deterministic `operate/` tool functions (affordance extraction, action execution, journey logging). The host supplies the perceive→decide→act→record loop; the package supplies each step as a callable.
- **Analyst roles** = the host, following `ov-analyze-ux` / `ov-analyze-arch`, calling the deterministic analyzers and assembling an **evidence bundle**, then reasoning over it directly to produce narrative critique / blueprint. No in-package LLM call required.
- Because the mechanical work is all plain functions, the system is **fully testable without a model**: a scripted strategy drives the Operator tools; heuristics-only analyzers produce reports.

**Phase 4 (optional productization) — `agents/`:**
When you want a self-contained agent system (e.g. behind the CLI, or for parallel breadth / deployment isolation), lift the *same* tools + skill logic into Python. D4's framing: **skills and thin agents are two serializations of the same procedural knowledge over the same tool functions — you are re-hosting, not rewriting.**
- **Reused unchanged:** the entire deterministic tool library, the Pydantic/JSON schemas (SSOT), the evidence-bundle assembler (§8.1), the prompt templates embedded in the skills, the synopsis map-reduce (§8.4).
- **What changes:** each `SKILL.md` becomes a thin agent definition; an **orchestrator** sequences Operator → UX/Arch-Analyst → synopsis. Keep the orchestrator a **pure coordinator** (plans and delegates, does not analyze — plan quality degrades when it also does work). Model routing: Opus-class for orchestration/architecture reasoning, Sonnet/Haiku for parallel workers. Structured output via the Agent SDK gives validated JSON at the end of multi-turn tool use.
- **`agents/llm.py`** — provider-agnostic LLM facade, `structured(prompt, schema) -> model` helper, dependency-injected, no provider lock-in.
- **`agents/operator_agent.py`** / **`agents/analyst_agent.py`** — encode the loops the skills describe; analysts consume evidence bundles, never the live browser.

**Cost gate:** multi-agent fan-out runs ~15× the tokens of a single agent (Anthropic's figure) for an uplift measured on breadth-first *research*, not this more-interdependent analysis task — so treat in-package agents as an optimization triggered by a real throughput/isolation need, not a default. The lift stays mechanical precisely because the skills already specify the policy and the tools already exist.

---

## 8. The LLM analysis layer, reports & synopsis *(structure validated by D4 research)*

The judgment work is performed by the host (Claude Code via skills) in Phases 1–3, or by the optional in-package analysts in Phase 4 — either way over the **same deterministic evidence**, with the same reliability discipline. The seam is Anthropic's own Skills philosophy: code provides deterministic reliability, the model supplies interpretation.

### 8.1 The evidence-bundle assembler (`analyze/evidence.py`) — deterministic

Builds the grounded bundle a vision LLM reasons over. **All of this is model-free code**, so token cost and grounding are computed, not hoped for:

- **Set-of-Mark.** Every region the model may discuss carries a stable mark id (e.g. `R3`) overlaid on the screenshot; the same id appears in the facts and is *required* in the output. This converts "describe what you see" into "interpret marked region R3."
- **Order: images before text.** Bundle layout is `[role/system + cite-or-abstain contract] → [marked image(s)] → [facts keyed to mark/fact ids] → [task instruction last]`.
- **Token budget is deterministic.** Project cost as `Σ(w×h/750)` per image against the model's cap (≈1568 px long edge on standard models; ≈2576 px / 4784 tokens on Opus 4.7/4.8) *before* the call; downsample to fit.
- **Full vs. crop.** Always send the full marked screenshot for layout context; attach crops for any region whose text would be sub-readable after downsampling. Prefer many small targeted crops over one huge image.
- **Omit raw bytes.** No raw HAR, full DOM, or minified bundle text in the model context — those stay in deterministic tools, reachable by `evidence_id` through a lookup tool only if a verification pass needs them (just-in-time retrieval). The model receives *derived facts* labeled as `evidence`, never `assumptions`.

### 8.2 Prompt/task patterns — two jobs × two modes (D4 Part 3)

The grounding discipline is constant; the **mode changes the goal and output**:

- **Arch-Analyst / reconstruct** — infer architecture + **design intent** (why this stack, what the team optimized for) and emit a **rebuild blueprint** + reusable **interaction-pattern catalog**, each inference tagged with evidence + confidence, abstaining where signals are absent (pure-backend tech isn't client-detectable).
- **Arch-Analyst / review** — critique architecture, flag risks (CVEs, lock-in, perf), give concrete fixes, **diff against a prior run**; severity-ranked remediation tied to evidence ids.
- **UX-Analyst / review** — severity-ranked usability issues with fixes, Nielsen's 10 heuristics as the rubric and 0–4 severity, each issue citing the heuristic + mark + rationale.
- **UX-Analyst / reconstruct** — shift from "fix" to "catalog": infer design intent per interaction, extract reusable patterns, note what a rebuild should preserve vs. improve.

Shared scaffolding: delineated prompt sections (`<background_information>`, `<instructions>`, output schema), images-before-text, cite-every-claim, abstain-when-unsupported, emit-only-schema-valid-JSON, low temperature.

### 8.3 Report sections

Registered functions (`register_section`) each take analyses + run and return a Markdown fragment; `render.py` concatenates selected sections. Default set:

- `00_overview.md` — target, mode, journey summary, headline findings.
- `10_ux_analysis.md` — flows, findings, a11y, perf-as-UX, prioritized issues.
- `20_architecture.md` — stack, rendering, state, routing, data layer, build.
- `30_api_surface.md` — endpoints & inferred schemas.
- `40_reconstruction_blueprint.md` (reconstruct mode) **or** `40_review_audit.md` (review mode).
- `90_appendix.md` — asset inventory, dependency table, raw metrics.

### 8.4 Synopsis — structured map-reduce (`report/synopsis.py`)

**Extract-and-aggregate over structured findings, not prose:**
- **Map** each section's `Finding`s into the synopsis schema; **reduce** by hierarchical merging.
- **Deduplicate deterministically** — cluster on `(type, evidence_refs overlap, normalized summary)` and merge into one finding holding the union of evidence refs and the max severity. Evidence-id overlap is a model-free check, more reliable than LLM similarity-judging.
- **Preserve provenance** — every synopsis finding resolves, via a tool, back to the screenshot crop / network record / metric it cites. This is what lets a downstream creation/modification agent *act on and verify* a finding.
- **Two renderings from one source** — emit machine-readable `synopsis.json` (the SSOT a downstream agent consumes) and **derive** `SYNOPSIS.md` from it (never hand-author the Markdown). Top-level carries run metadata, target (foreign/own), the findings array, and a rolled-up severity histogram. Markdown deliverables authored as "Thor Whalen" (standing preference).

---

## 9. Tooling choices (what to use so we don't reinvent the wheel)

Hard recommendations for the implementing agent. The capture/operation layer (this section's first items) is **validated by the D1 research report** — follow its staging.

- **Driving & capture:** **Playwright (Python)** as the baseline, treated as a **facade over a CDP escape hatch, not a wall**. Playwright high-level APIs cleanly handle ~80% of capture: request/response metadata + timings, **HAR** (`record_har_path` with `.har.zip` + `record_har_content="embed"` to embed bodies), **WebSocket** frames (`page.on("websocket")` — first-class, *not* CDP), console/`pageerror`, `storage_state`, tracing. Attach a **CDP session** (`page.context.new_cdp_session(page)`) — implemented as a `capture/cdp.py` plugin — for the ~20% the high-level API can't reach: full **AX tree** (`Accessibility.getFullAXTree`), **SSE** frames (`Network.eventSourceMessageReceived`), **eviction-proof bodies** (`Fetch`-stage interception — `response.body()` evicts for large/CDN'd bodies, design around it from day one), `Performance.getMetrics`, and certificate. CDP is **Chromium-only** — that's an accepted constraint for the capture tail.
- **Accessibility tree, two views (progressive disclosure):** the concise **ARIA snapshot** (`locator.aria_snapshot`, ref-bearing `mode="ai"`) is what the *agent* sees per step (~200–400 tokens); the full CDP **AX tree** is recorded as *evidence*. Note `page.accessibility.snapshot()` is deprecated — use ARIA snapshot / `getFullAXTree`. (Distinct from axe-core, which is the a11y *audit* engine; see D3.)
- **Network archive:** built-in **HAR** as the canonical network artifact; parse with a HAR model.
- **Proxy (`capture/proxy.py`) — opt-in, off by default:** add **mitmproxy** *only* for a specific tail — guaranteed full bodies at scale, TLS/JA3/HTTP-2 detail, **service-worker traffic** that `page.route` misses, or non-browser traffic. It adds CA-trust + an extra hop; most runs won't need it. Behind the same capture interface.
- **Stealth/anti-detect — opt-in, off by default, ToS-gated:** a `StealthProfile` plugin defaulting to `None`, with a docstring scoping it to authorized testing/research. Note it's an arms race (Camoufox/Nodriver/playwright-stealth), none are truly undetectable, all need maintenance. Do not center the package on it.
- **Future backend:** design the capture interface so **WebDriver BiDi** (W3C-standard, cross-browser event streaming) can slot in as a pluggable backend later — its high-level ergonomics aren't ready for mid-2026, so baseline on Playwright now.
- **Accessibility audit (distinct from the AX-tree capture above):** **axe-core** via `@axe-core/playwright` is the deterministic workhorse — `.analyze()` scans the *current* DOM, so run it **per captured state** (catches SPA/modal/revealed states a single page-load scan misses); filter `wcag2a/wcag21aa/wcag22aa`. Add **IBM Equal Access** (`ace.js`) as a second engine for explicit WCAG-criterion + ACT-rule mapping; Lighthouse/Pa11y/WAVE are supplements. Compute contrast deterministically (WCAG luminance formula). **Hard ceiling: ~30–40% of WCAG issues are automatable** — flag the rest `needs_human_review`, never equate "no violations" with "accessible". (D3.)
- **Performance (per-step CWV):** inject the **`web-vitals` attribution build** (`web-vitals/attribution`); collect via `PerformanceObserver` `buffered:true` and **bucket entries into each step's wall-clock window**, naming the offending element (INP `interactionTarget`, CLS `largestShiftTarget`). LCP/FCP/TTFB are initial-load-only until the experimental **Soft Navigations API** is adopted for SPA routes — label them provisional. Optional **Lighthouse** probe for a lab audit. (D3.)
- **Tech fingerprinting:** **`wappalyzer-next`** (PyPI `wappalyzer`, `full` mode runs the Wappalyzer extension in Playwright Chromium — the only tier that sees JS-executed DOM + window globals) over the **`enthec/webappanalyzer`** ruleset; prefer `js`/`dom` signals over loose `html` regex. Add **Retire.js** (Node CLI) for vulnerable libraries. Each finding carries Wappalyzer-style confidence + version. (D2; note GPL-3.0 licensing.)
- **Bundle/source-map recovery:** **source maps are the decisive variable.** Maps present → `source-map` / `unwebpack-sourcemap` / `source-map-explorer` to rebuild the file tree + harvest `node_modules` versions. Maps absent → `webcrack` / `wakaru` to unpack + unminify (names lost) + beautify. Static literal extraction via Babel/acorn. All JS tooling runs in the **Node sidecar** (§6.1) — never `eval` downloaded JS in-process.
- **API synthesis:** **`GenSON`** (Python — the per-endpoint schema-merge primitive `ov` owns) + **`mitmproxy2swagger`** (path discovery) + **`Optic`** (stable, patchable master spec, merges journeys). GraphQL: introspection → **`Clairvoyance`** (field-suggestion fuzzing, wordlist from the target's own bundle). Realtime shapes from HAR `_webSocketMessages[]` and `text/event-stream`. Per-endpoint coverage/confidence score. (D2.)
- **Static crawl complement:** lightweight HTML parsing (`selectolax`/`lxml`) for `<a>`/route discovery on top of the dynamic trace.
- **Schemas/validation:** **Pydantic v2** for the SSOT artifact tree and all structured LLM outputs.
- **Storage:** **`dol`** for filesystem-backed `MutableMapping` stores; content-addressing via hashlib.
- **Dataflow:** **`meshed`** (optional) for the probe/analyzer DAG, else minimal topo-sort.
- **CLI:** **`argh`** dispatch.
- **System deps:** Playwright browsers + a Node runtime hosting the **sidecar** (§6.1; `source-map`, `webcrack`, `wakaru`, `quicktype`, `optic`) and the `wappalyzer-next` / Retire.js CLIs. Provide a `check_requirements()` that detects missing browsers/Node/sidecar-npm-deps and prints exact install commands (`playwright install`, `npm install` in `sidecar/`, `pipx install wappalyzer`, Node version note), offering to run them with permission.

---

## 10. Build phases (ship working software at each boundary)

**Phase 1 — Capture spine (no LLM, no host required, fully usable).**
Browser facade (`browser.py`), `CaptureSession`, stores/Mall, SSOT schema, and probes: `network`(HAR `.zip`/embed)+`dom`(ARIA snapshot)+`screenshot`+`console`+`navigation`+`fingerprint`+`assets`. The five `operate/` primitives — `observe` / `act` / `journal` / `progress` / `snapshot_state` — with `AxSnapshot` perception, plus a **scripted/guided** driver (replay + simple crawl, no model). Follow D1's capture staging: Playwright high-level first; add the `capture/cdp.py` plugin (full AX tree, SSE, Fetch-stage bodies, perf) the first time a body evicts or an SSE/full-AX need appears; proxy/stealth deferred and opt-in. `ov observe <url>` produces a populated run store. Deliverable: point it at a URL and inspect a complete capture, purely deterministically.

**Phase 2 — Deterministic analysis + reports (no LLM, no host required).**
The UX/a11y **deterministic engine** (§5.1): axe-core per state + contrast/focus + per-step CWV attribution + journey metrics + rule-based heuristics, all normalized into the `Finding` schema with `severity × reach` and `needs_human_review` for the non-automatable tail. The arch **three-stage pipeline** (`fingerprint → bundle-recovery → api-synthesis`) with the Node sidecar (§6.1) and confidence/provenance on every inferred fact. Report sections + Markdown render; `synopsis`. Land the rendering-model classifier and source-map detection early — `source_maps_present` gates reconstruction grade. `ov overview <url>` produces real reports with **zero LLM**. Deliverable: usable UX + arch reports today.

**Phase 3 — Host-agent orchestration via skills (the "AI-strong" system).**
Author `.claude/skills/` (§3.5): `study-web-app` + the sub-skills, with the §8.2 prompt patterns embedded. Build the deterministic **evidence-bundle assembler** (§8.1: Set-of-Mark, images-before-text, `w×h/750` token budget, full-vs-crop) and the **reliability passes** (cite-or-abstain, factored Chain-of-Verification over high-severity findings, NLI/faithfulness gate) so every LLM `Finding` cites resolvable `evidence_refs` or is downgraded to `undetermined`. Claude Code now does goal-pursuit operation and narrative UX/arch judgment by orchestrating the Phase-1/2 tools — *no in-package agent code*. Every tool a skill needs has a clean, agent-legible API and structured (Pydantic) returns. Deliverable: *"Claude, go study this app"* works end-to-end, with the host as manager.

**Phase 4 — Productization + depth + review mode.**
*Productization (optional):* lift the skills' policy into in-package `agents/` (`llm.py` facade, `operator_agent.py`, `analyst_agent.py`) so the system runs self-contained behind the CLI / as a manager-of-agents. *Depth:* source-map recovery sidecar, WebSocket/perf/storage probes, GraphQL introspection, Lighthouse probe. *Review mode:* own-target **diff/regression** against stored prior runs, richer synopsis for downstream creation agents.

Each phase is independently shippable. Do not start Phase *n+1* code paths in ways that break Phase *n* defaults.

---

## 11. Testing & quality

- **pytest**, doctests on public functions, fixtures using a tiny **local test app** (a static site + a small SPA you serve in-process) so capture tests are hermetic and offline.
- Golden-file tests for report sections (deterministic analyzers → stable Markdown).
- **Keep the model out of unit tests.** Test tools deterministically (golden inputs → golden facts); the whole deterministic core (capture, analyzers, evidence-bundle assembler, synopsis dedup) is model-free and so fully testable. Test skills with eval scenarios (with-skill vs. without-skill: grounded-claim fraction up, unsupported-claim rate down).
- Agents (Phase 4, if built) tested with the **scripted** Operator and **heuristics-only** Analysts so the suite runs without any model or network.
- `check_requirements()` covered by a test that asserts helpful messaging when Playwright browsers/Node are absent.
