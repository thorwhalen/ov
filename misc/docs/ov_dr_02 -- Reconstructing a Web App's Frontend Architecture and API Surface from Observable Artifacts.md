# Reconstructing a Web App's Frontend Architecture and API Surface from Observable Artifacts

*A technical decision report for the `ov` Python tool — authored by Thor Whalen*

> 📄 **Downloadable Markdown file created in your Google Drive:** **"ov - Frontend Architecture and API Surface Inference (Deep Research Report).md"** (file ID `1qLnj8JA8Wrw05-RoJTcVDJe0UVx2TicM`).

## TL;DR

- **Build a three-stage pipeline — fingerprint → bundle recovery → API synthesis — where Python orchestrates and a thin Node sidecar runs the mature JS-only tooling (`source-map`, `webcrack`, schema/OpenAPI generators).** This is the cleanest separation: Python owns process control, scoring, and merging; Node owns the AST/source-map work it is uniquely good at.
- **Reconstruction quality is bimodal and hinges almost entirely on one variable: are source maps present?** With maps you recover the original module/file tree, component boundaries, comments, and often hardcoded config; without them you recover a beautified-but-renamed approximation. Fingerprinting and API synthesis degrade gracefully, but source-map presence is the single biggest lever on "reconstruction-grade."
- **Attach explicit confidence to every claim.** Wappalyzer-style rules already carry per-pattern confidence (0–100) and version capture groups; API-synthesis confidence is a coverage function (how many journeys exercised an endpoint, whether types were stable across samples). Treat all outputs as probabilistic, never as ground truth.

## Key Findings

1. **Fingerprinting has a clear winner for rules and for the Python runner.** The Wappalyzer ruleset lives on in maintained community forks — `enthec/webappanalyzer` (GPLv3) and `tunetheweb/wappalyzer` — after the original "went private in August 2023" (per the enthec README). For a Python tool, `wappalyzer-next` (PyPI: `wappalyzer`, GPL-3.0, by s0md3v) is the most capable runner: it drives headless Chromium via Playwright and runs the actual Wappalyzer extension, giving DOM + JS-global + header + cookie inspection on dynamic SPAs.
2. **`window` globals and DOM markers are the highest-signal, lowest-cost framework detectors.** `__NEXT_DATA__` (Next.js), `__NUXT__` (Nuxt), `__remixContext` (Remix), and the React/Vue devtools hooks are near-deterministic. They also reveal the rendering model: a populated `__NEXT_DATA__.props.pageProps` in the initial HTML means SSR/SSG; an empty root `<div>` plus a hydration call means CSR.
3. **Source maps are the crown jewel and are leaked far more often than developers realize.** When present (`//# sourceMappingURL=` or a guessable `.js.map`), the `sources`/`sourcesContent` fields reconstruct the original file tree, including `node_modules/...` paths that pin exact dependency versions. Tools: `unwebpack-sourcemap`, `sourcemapper`, and the Mozilla `source-map` library.
4. **When maps are absent, `webcrack` and `wakaru` are the state of the art** for unpacking webpack/browserify bundles back into per-module files and undoing minification — but variable names are gone forever unless a map supplies them.
5. **HAR → OpenAPI is solved-enough with three credible tools** — `mitmproxy2swagger` (Python, 9.5k GitHub stars as of April 2026; Starlog calls it "the de facto solution for API archaeology"), `har2openapi` (Node/JS, uses quicktype for schema inference), and `Optic` (Node, surgical patching, merges runs) — plus `GenSON` (Python) for raw JSON-Schema inference from observed examples.
6. **GraphQL is detectable and partially recoverable even when locked down.** Introspection (`__schema`) is often disabled in production, but `Clairvoyance` recovers schemas via field-suggestion fuzzing, and observed operations in captured traffic or in the JS bundle give you real query/mutation shapes.
7. **Realtime layers are visible in HAR.** WebSocket frames live in the `_webSocketMessages[]` array of HAR entries; SSE shows up as a long-lived `text/event-stream` response. Both yield message shapes you can schema-infer the same way as REST bodies.

## Details

### Frontend concepts for the Python expert (progressive disclosure)

- **Bundler.** Frontend source is many small `.ts`/`.tsx`/`.vue` modules. A *bundler* (webpack, Vite, Turbopack, esbuild, Rollup) compiles, tree-shakes, and concatenates them into a few large `.js` files — conceptually a build/link step with dead-code elimination. The bundler leaves fingerprints (runtime wrapper functions, chunk-loading globals like `webpackChunk`/`__webpack_require__`) that betray which one was used.
- **Minification.** The bundler renames `getUserProfile` → `a`, strips whitespace and comments. Lossy and, for names, irreversible. The only thing that reverses it is a *source map*.
- **Source map.** A side-car JSON file (`.js.map`) emitted at build time that maps every position in the minified bundle back to original file + line + column + name. It is the "debug symbols" of the web; if shipped to production (very common), it is a near-complete source disclosure.
- **Rendering model.** *CSR*: server sends an empty shell, JS builds the DOM. *SSR*: server sends full HTML per request, then *hydrates* (attaches JS handlers to existing DOM). *SSG*: same as SSR but HTML built at deploy time. *Streaming SSR*: HTML flushed in chunks.

### Part A — Tech & dependency fingerprinting

**The ruleset.** Each Wappalyzer fingerprint is a JSON object with signal-typed pattern fields: `headers` (e.g. `X-Powered-By`, `Server`), `cookies`, `scriptSrc`/`script`, `js` (`window`-global property checks like `Next.router`), `dom` (CSS-selector inspection of attributes/properties/text), `meta` (notably `generator`), `html`, `css`, `text`, `dns`, `url`, `robots`, plus relationship operators `implies`, `requires`, `requiresCategory`, `excludes`.

**Confidence and versions are built into the rule syntax.** A pattern can append `\;confidence:50` (defaults to 100) and `\;version:\1` (a capture group). The engine sums per-pattern confidence per app toward a combined total. This is exactly the probabilistic-output model `ov` should adopt. The spec warns "short or generic patterns can cause applications to be identified incorrectly" — the primary false-positive source; mitigate by preferring `js`/`dom` signals over loose `html` regexes.

**Running it programmatically in Python.**
- **`wappalyzer-next`** (PyPI `wappalyzer`, GPL-3.0). Install `pipx install wappalyzer` then `playwright install chromium`. CLI: `wappalyzer -i https://example.com -oJ results.json`. Python API: `from wappalyzer import analyze; analyze(url=..., scan_type='full', cookie=..., timeout=30)`. Three tiers — `fast` (single HTTP request, no browser), `balanced` (adds `.js`, `robots.txt`, DNS), `full` (runs the Wappalyzer extension in headless Chromium — the only tier that sees JS-executed DOM and window globals). Returns a dict of technologies with `version`, `confidence`, `categories`, `groups`. For batch work use the reusable `Wappalyzer(...).analyze_many([...])` context manager rather than `analyze()` in a loop.
- **Legacy `chorsley/python-Wappalyzer`** is archived/inactive — reference only, useful for its confidence/version-parsing implementation.

**Complementary detectors.**
- **Retire.js** — detects *vulnerable* library versions via filename, URL, file-content regex, and (last resort) content hashes, cross-referenced to a CVE/OSV-backed repo. The CLI scanner deliberately does *not* run untrusted JS in node (only the Chrome extension does, sandboxed). Emits a CycloneDX SBOM. A Python port (`retirejslib`) exists but is dated; shelling to the maintained Node CLI is safer.
- **BuiltWith / WhatRuns / SimilarTech** — hosted services adding larger fingerprint counts, historical adoption data, and crawl-based coverage of sites you haven't visited. Commercial, and crawl data can lag reality. For `ov`'s "audit one target deeply" use case the OSS ruleset suffices; these matter only for breadth/market-share questions.

**Inferring the bundler:** webpack (`__webpack_require__`, `webpackChunk`, numeric module IDs); Vite (dev `/@vite/client`, `import.meta.hot`; prod Rollup/Rolldown chunks + `modulepreload`); Turbopack (Vercel's Rust bundler, Next.js 15+ dev default — but prod builds were still stabilizing per 2026 sources, so a Next.js prod build may still be webpack-emitted); esbuild (`__esm`/`__commonJS` helpers); Rollup (hoisted, comment-annotated chunks).

**Inferring the rendering model:** empty `<div id="root">`/`<div id="__next">` ⇒ CSR; full markup + state-injection global (`__NEXT_DATA__`, `__NUXT__`) ⇒ SSR/SSG (distinguish by varying a request — SSG is identical and build-time-stamped, SSR re-renders per request; the Nuxt route-rules vocabulary `ssr`/`isr`/`swr`/`prerender` shows how granular this gets); chunked `Transfer-Encoding` + inline Suspense-resolving scripts ⇒ streaming SSR. Robust test: **fetch raw HTML with JS disabled and diff against the JS-rendered DOM** — large divergence ⇒ CSR, near-identity ⇒ SSR/SSG.

### Part B — Bundle & source-map reverse-engineering

**The decisive question: are source maps present?**

*Maps present (best case).* Detection: read each `<script src>`, fetch the JS, look for the trailing `//# sourceMappingURL=` comment; also try appending `.map` to each bundle URL (maps are often deployed even when the comment is stripped); check staging/dev hosts. Then:
- `sources` gives the **original file tree**; `sourcesContent` gives the **original source text** (comments, original names, dead code).
- `node_modules/<pkg>/...` paths reveal **exact dependency identity and often version** — enabling precise SBOM reconstruction and Retire.js cross-referencing.
- **Component boundaries** fall out of the directory structure (`src/components/Foo.tsx`).
- Tools: **`unwebpack-sourcemap`** (Python, by rarecoil; maintained PyPI fork by James Mishra; `--detect` mode walks a page's scripts); **`sourcemapper`** (Go); the Mozilla **`source-map`** npm library (`SourceMapConsumer.originalPositionFor`, `SourceNode.fromStringWithSourceMap`) as the programmatic primitive, including position-by-position name recovery when `sourcesContent` is absent; **`source-map-explorer`** maps every byte to its origin file (module-tree treemap, duplicate-dependency detection).

*Maps absent (degraded case).* You cannot recover original names or files, but you can:
- **Unpack into per-module files**: **`webcrack`** (j4k0xb, TypeScript) deobfuscates obfuscator.io output, unminifies, and unpacks webpack/browserify; uses `isolated-vm` for safety and auto-detects patterns. **`wakaru`** (pionxzh) decompiles webpack 4/5, esbuild, Bun, and Browserify, recovers Terser/Babel/SWC/TypeScript transforms, offers three rewrite levels (`minimal`/`standard`/`aggressive`), and consumes a source map if supplied for name recovery and import dedup.
- **Beautify** with prettier/`js-beautify` as a baseline.

**Recovering in-bundle data safely.** Route tables, API base URLs, feature flags, and config frequently survive minification as string literals. Recover them by **static AST extraction** (Babel/acorn in the sidecar) harvesting string/object literals; regex for `https?://` hosts, GraphQL `query`/`mutation` keywords, route-path patterns, and flag-shape keys. **Never `eval` or run downloaded JS in your own process** — this is precisely why Retire.js's CLI refuses to run page JS in node and why `webcrack` uses `isolated-vm`. If dynamic evaluation is ever required, it belongs in a disposable, network-isolated headless browser, never the sidecar process.

**Legal/ethical (brief).** Reverse-engineering deployed JS you don't own can implicate terms-of-service, anti-circumvention (DMCA §1201 in the US), and computer-misuse statutes; `wakaru` states plainly that use against targets without consent may be illegal. `ov` should default to auditing systems the operator controls or is authorized to assess, and record provenance. Not legal advice.

### Part C — API-surface synthesis from traffic

**HAR → OpenAPI.** Capture a HAR (DevTools "Export HAR", or a `mitmproxy`/Playwright capture), then synthesize:
- **`mitmproxy2swagger`** (Python, 9.5k stars). Two-pass, human-in-the-loop: first pass emits all observed paths prefixed `ignore:`; you un-ignore real paths and rename `{param0}`; second pass with `--examples` infers schemas and attaches examples. Recognizes UUID/int/slug IDs, templates versioned prefixes, and **safely merges multiple capture sessions**. Conservative inference widens types or marks fields optional on conflict — it encodes uncertainty rather than overfitting. Caution: `--examples`/`--headers` can embed secrets.
- **`har2openapi`** (Node/JS, dcarr178, ISC). Uses **quicktype** for JSON-Schema inference; query-string params auto-move to parameters, but collapsing `/account/1` and `/account/2` into `/account/{id}` requires user-supplied regex `pathReplace` rules in `config.json`. Targets OpenAPI 3.0.3 (3.1 unsupported per the open issue); output is "noisy" initially by the author's own admission. **No PyPI `har2openapi`** — for Python it's a shell-out, or the npm derivative `har-to-openapi`.
- **`Optic`** (Node). Does not generate from scratch — it **surgically patches** an existing spec to match observed traffic, preserving manual edits/descriptions; `--update interactive|automatic|documented` controls undocumented-endpoint handling; ingests HAR/Postman and computes coverage. Ideal for the **merge-multiple-journeys** requirement and a stable long-lived spec.
- **`GenSON`** (Python) is the right low-level primitive for `ov` to own directly: feed it many observed JSON bodies per endpoint and it builds a single merged JSON Schema (design goal: every observed object validates; schema as strict as examples allow). `SchemaBuilder().add_object(...)` is effectively a monoidal merge over samples — composition-friendly.

**Distinguishing REST vs RPC vs GraphQL.** GraphQL = single endpoint (`/graphql`), POST body with `query`/`mutation`/`variables`, responses `{ "data": {...}, "errors": [...] }`. RPC = verb-like non-resource paths (`/createUser`, `/api.Service/Method`), usually all POST; JSON-RPC bodies `{"jsonrpc","method","params","id"}`; gRPC-web uses `application/grpc-web+proto`. REST = resource-noun paths + HTTP-verb semantics + method diversity + cache headers. Classifier: single-endpoint+`query` ⇒ GraphQL; verb-paths+all-POST ⇒ RPC; noun-paths+method-diversity ⇒ REST.

**GraphQL introspection & inference.** Enabled → send the standard `__schema` query → full SDL → GraphQL Voyager/InQL for visualization. Disabled (common) → **`Clairvoyance`** (Python, `pip install clairvoyance`, by Nikita Stupin / Escape) recovers schemas via **field-suggestion fuzzing**: malformed field names trigger "Did you mean…" suggestions (an Apollo default) that leak valid fields; with a good wordlist it reconstructs much of the schema as introspection-shaped JSON. Build the wordlist from the target's own JS bundle (grep `query`/`mutation`, regex `[_A-Za-z][_0-9A-Za-z]*`). Independently, **operations observed in traffic or extracted from the bundle** give real, used shapes — often more valuable than the full schema.

**Recovering auth schemes.** `Authorization: Bearer <jwt>` ⇒ token auth (decode the unverified JWT for issuer/algorithm/scopes); `Cookie:` + `Set-Cookie: HttpOnly; Secure; SameSite` ⇒ session-cookie auth; OAuth/OIDC ⇒ `/authorize`, `/token`, `/.well-known/openid-configuration`, `state`/`code`/`redirect_uri`; API keys ⇒ custom headers (`X-API-Key`) or query params. Traffic-to-OpenAPI tools auto-detect Bearer/Basic/API-key and emit `securitySchemes`.

**Detecting realtime layers.** WebSocket: the HTTP `Upgrade: websocket` handshake; in HAR, frames are in the `_webSocketMessages[]` array per entry, each with `type` (send/receive), `time`, and `data` — schema-infer the (usually JSON) payloads with GenSON, grouped by a message-`type` discriminator. SSE: a long-lived `Content-Type: text/event-stream` response — parse `event:`/`data:` lines and schema-infer.

**Merging multiple journey runs with coverage/confidence.** Run several journeys, capture each, merge with Optic (spec-patching) or GenSON (per-endpoint schema union). Attach a per-endpoint **coverage/confidence score** = f(number of journeys hitting it, number of distinct samples, type stability across samples, whether both success and error responses were seen). One endpoint seen once with one 200 ⇒ low; one seen across five journeys with stable types and an observed 4xx ⇒ high.

### Recommended three-stage pipeline

| Stage | Goal | Primary tools | Python role | Node-sidecar role |
|---|---|---|---|---|
| **1. Fingerprint** | Frameworks, libs, bundler, rendering model, versions, vulns | `wappalyzer-next` (enthec rules), Retire.js | orchestrate, score, dedupe, SBOM | run Wappalyzer extension in Playwright Chromium; run Retire.js CLI |
| **2. Bundle recovery** | Module/file tree, component boundaries, in-bundle config | `source-map`, `unwebpack-sourcemap`, `webcrack`, `wakaru`, `source-map-explorer` | detect/fetch maps, drive recovery, static-extract literals, store provenance | consume maps, unpack/unminify, AST-parse for literals |
| **3. API synthesis** | OpenAPI + JSON Schemas + GraphQL SDL + realtime shapes, scored | `mitmproxy2swagger`, `Optic`, `GenSON`, `Clairvoyance`, `har2openapi`/`har-to-openapi` | own GenSON merge, journey-merge, confidence scoring, GraphQL fuzz orchestration | quicktype-based inference, Optic patching |

### Recommended Python ↔ Node sidecar boundary

The mature reverse-engineering tooling (`source-map`, `webcrack`, `wakaru`, Optic, quicktype) is JavaScript; orchestration, scoring, and data-model work is Python's strength. Keep the boundary **coarse and declarative**:

- **Pattern:** a long-lived Node sidecar exposing a small, versioned set of pure functions — `consumeSourceMap(mapJson) → {files}`, `unpackBundle(jsText) → {modules}`, `inferSchema(samples) → jsonSchema`, `patchOpenAPI(spec, har) → spec`. Communicate over **newline-delimited JSON-RPC 2.0 on stdio** (the same transport MCP uses) — avoids HTTP overhead on the high-call-count schema path while staying language-neutral.
- **Why stdio over a localhost HTTP server:** simpler lifecycle, no port management, sub-process-bound security, no accidental network exposure of a tool ingesting untrusted JS. The one caveat (well documented in the MCP-on-Kubernetes literature) is that stdio is single-host and breaks under pod restarts — irrelevant for `ov`'s single-machine runs, but if `ov` scales out, switch the same JSON-RPC contract to HTTP.
- **SOLID/functional framing:** treat the sidecar as a **stateless, referentially-transparent function library** (inputs in, JSON out, no hidden state). Python owns all orchestration, retries, scoring, persistence. Define the wire contract once (Pydantic models mirroring the sidecar's types) so the boundary is a single swappable interface — Dependency-Inversion at the process level. Each stage is a composable transform `Artifacts → Artifacts`, enabling a declarative pipeline (`fingerprint >> recover >> synthesize`) with per-stage confidence accumulation.
- **The JS side is the source of truth** for logic that exists only in JS (quicktype inference, source-map math); Python marshals JSON to it, never reimplements it. For untrusted-JS *execution* (almost never needed), use a disposable network-isolated headless browser — never the sidecar process itself.

## Recommendations

**Stage 0 — always first (cheap, deterministic):**
1. Fetch raw HTML (JS disabled) + the JS-rendered DOM; diff them to classify CSR vs SSR/SSG.
2. Scan `window` globals and response headers for high-signal markers (`__NEXT_DATA__`, `__NUXT__`, `__remixContext`, `X-Powered-By`, `Server`, `Set-Cookie` flags).
3. Run `wappalyzer-next` in `full` mode for the tech/version baseline; run Retire.js for known-vuln libraries.

**Stage 1 — attempt source-map recovery before anything harder:**
4. For every bundle, check for `sourceMappingURL`, try `.js.map`, and probe staging/dev hosts. If maps exist, run `unwebpack-sourcemap`/`source-map` to rebuild the file tree and harvest `node_modules` versions — the highest-ROI step in the whole pipeline.
5. **Threshold that changes the plan:** maps present *with* `sourcesContent` ⇒ reconstruction-grade source; proceed to static literal extraction directly. Maps absent ⇒ fall back to `webcrack`/`wakaru` and lower your reconstruction-confidence ceiling (no original names).

**Stage 2 — synthesize the API surface from multiple journeys:**
6. Drive several representative user journeys through a capturing proxy; export one HAR per journey.
7. Use `GenSON` (Python-owned) as the per-endpoint schema-merge core; use Optic to keep a stable, patchable master OpenAPI spec across runs; use `mitmproxy2swagger` for the initial path-discovery pass.
8. Classify each endpoint REST/RPC/GraphQL; for any `/graphql`, first try introspection, then `Clairvoyance` with a bundle-derived wordlist.
9. Parse `_webSocketMessages[]` and `text/event-stream` responses for realtime message shapes; schema-infer them too.

**Always:**
10. Emit confidence on every node (detector 0–100; endpoint coverage score). Record provenance (which artifact/journey produced each fact). Mark speculative reconstructions (un-mapped, name-lost code) as explicitly lower-confidence than map-backed ones.

**Benchmarks that would change these recommendations:** if Turbopack production builds become the Next.js default (watch the 2026 stabilization), update bundler fingerprints. If a target disables Apollo field suggestions (`hideSchemaDetailsFromClientErrors`), drop `Clairvoyance` and rely on observed/bundle-extracted operations. If source maps are reliably absent across a target, invest more in `webcrack`/`wakaru` AST extraction and lower the promised reconstruction grade.

## Caveats

- **Passive observation documents what happened, not what's possible.** Every API tool here (mitmproxy2swagger explicitly) is bounded by traffic coverage: an optional field never seen won't appear; an unexercised error path won't be in the spec. Intrinsic, not a defect — hence coverage/confidence scoring.
- **Fingerprint false positives are real.** Short/generic regexes misidentify; prefer `js`/`dom` signals and rule-supplied confidence. Hosted services (BuiltWith) can serve stale data.
- **Source-map presence is environmental and may change between visits.** Maps on staging today may be gone tomorrow; capture provenance and timestamps.
- **Minification name loss is irreversible without maps.** "Reconstruction-grade" without source maps means structure and strings, not original identifiers.
- **`wappalyzer-next` packaging is in flux** — the live README documents Playwright/Chromium and `pipx install wappalyzer`, while some cached `setup.py` metadata still lists Selenium/Firefox; pin a known-good version (PyPI `wappalyzer` 1.0.22 was the latest signed artifact at research time). Its README claims it bundles the official Wappalyzer extension/fingerprints; the specific linkage to `enthec/webappanalyzer` is asserted by secondary sources, not the primary README.
- **Legal exposure varies by jurisdiction and target ownership.** Default to authorized targets; not legal advice.
- **Tool maturity varies.** Atlassian acquired Optic on April 30, 2024 ("Optic will be integrated into Compass, Atlassian's developer experience platform"); the standalone useoptic.com site is no longer public. Postman acquired Akita Software on July 19, 2023 (an earlier HAR→spec option). Verify current availability before depending on any single hosted tool, and prefer the self-hostable OSS core (`GenSON`, `mitmproxy2swagger`, `source-map`, `webcrack`).

## References

[1] enthec/webappanalyzer — https://github.com/enthec/webappanalyzer
[2] Wappalyzer specification — https://docs.wappalyzer.com/dev/specification
[3] wappalyzer-next (PyPI `wappalyzer`) — https://github.com/s0md3v/wappalyzer-next
[4] Retire.js — https://github.com/RetireJS/retire.js
[5] unwebpack-sourcemap — https://github.com/rarecoil/unwebpack-sourcemap
[6] Mozilla source-map — https://www.npmjs.com/package/source-map
[7] webcrack — https://github.com/j4k0xb/webcrack
[8] wakaru — https://github.com/pionxzh/wakaru
[9] mitmproxy2swagger — https://github.com/alufers/mitmproxy2swagger
[10] har2openapi — https://github.com/dcarr178/har2openapi
[11] Optic — https://github.com/opticdev/optic
[12] GenSON — https://github.com/wolverdude/GenSON
[13] Clairvoyance — https://github.com/nikitastupin/clairvoyance
[14] GraphQL introspection — https://graphql.org/learn/introspection/
[15] sourcemapper — https://github.com/tehryanx/sourcemapper
[16] source-map-explorer — https://www.npmjs.com/package/source-map-explorer
[17] quicktype — https://github.com/glideapps/quicktype
[18] traffic2openapi (auth/security detection) — https://github.com/grokify/traffic2openapi
[19] WebSocket frames in HAR — https://www.keysight.com/blogs/en/tech/nwvs/2022/07/23/looking-into-websocket-traffic-in-har-capture
[20] Apollo: disabling GraphQL introspection — https://www.apollographql.com/blog/why-you-should-disable-graphql-introspection-in-production