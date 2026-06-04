# Automated and Semi-Automated Evaluation of Web UX and Accessibility: A Programmatic Architecture for Agent-Driven Journeys

*Authored by Thor Whalen*

> **Deliverable note:** This report is provided as publication-ready Markdown. To save as a downloadable `.md` file, copy the content below into a file named `ux-a11y-evaluation-architecture.md` (the document is self-contained and uses only standard Markdown).

## TL;DR

- **A deterministic-first pipeline can reliably evidence a large share of UX and accessibility problems directly from agent-captured journey data (screenshots, DOM, accessibility tree, journey trace, console errors, performance timings)** — but automated accessibility tooling has a hard ceiling: Deque found automated issues for only 16 of the 50 WCAG 2.1 AA success criteria ("This supports the 20 to 30% automated coverage claims that many experts claim today"), and classic heuristic UX problems require an LLM judgment layer that is grounded strictly on an evidence bundle to avoid hallucination.
- **Core Web Vitals can be attributed to individual journey steps** using the Google `web-vitals` attribution build plus the underlying Event Timing, Layout Instability, and LCP browser APIs, timestamp-bucketing each PerformanceEntry into the step window in which it occurred and naming the offending DOM element — though true per-step LCP/FCP/TTFB on SPA route changes requires the experimental Soft Navigations API.
- **The recommended architecture is two-layered:** (1) a deterministic engine that runs axe-core injected per app state, computes journey metrics (task success, steps-to-goal, backtracking, form friction), maps every finding to a WCAG criterion or Nielsen heuristic, and assigns severity via severity × reach; then (2) a constrained LLM layer that adds narrative judgment over annotated screenshots and the deterministic findings, forbidden from inventing findings not traceable to an evidence ID.

---

## Key Findings

1. **The automatable ceiling is real and quantified.** Deque's *Automated Accessibility Coverage Report* states: "In our analysis we found automated issues for 16 out of the 50 Success Criteria under WCAG 2.1 Level AA. This supports the 20 to 30% automated coverage claims that many experts claim today." Measured against real-world *issue volume* the share is higher — across 2,000+ audits spanning 13,000+ pages and ~300,000 issues, Deque found "57.38% of total issues were identified using Deque's automated tests" — because high-frequency issues like contrast are automatable. The UK GDS put the practical ceiling at 40%. The honest planning number is 30–40% of issues; the rest needs manual/AT testing.

2. **Most real accessibility failures are a short, stable list.** The WebAIM Million (February 2026 report) states "96% of all errors detected fall into these six categories. These most common errors have been the same for the last 7 years": low-contrast text, missing alt text, missing form labels, empty links, empty buttons, missing document language. A deterministic engine that nails these covers the bulk of detectable volume.

3. **Heuristics map cleanly onto machine-observable signals.** Each of Nielsen's 10 heuristics and each cognitive-walkthrough question can be tied to concrete evidence in the captured data — e.g., "visibility of system status" → presence/absence of ARIA-live regions and loading indicators in the DOM after an action; "error prevention/recovery" → console errors plus error-state microcopy in the DOM; "user control" → backtracking and cancel/undo affordances in the journey trace.

4. **Journey traces yield rigorous quantitative UX metrics.** Task success, time-on-task, error rate, steps-to-goal, backtracking/dead-ends, and form friction are all computable from the trace + DOM, and benchmarkable (MeasuringU's analysis of 1,189 tasks across 115 usability tests from 3,472 users found an average completion rate of 78%; form completion collapses past ~5–7 fields).

5. **CWV attribution to a step is an engineering-solved problem (mostly).** The `web-vitals` attribution build exposes element-level and phase-level breakdowns for INP, LCP, and CLS; the only genuinely hard part is segmenting metrics across SPA soft navigations, which needs the experimental Soft Navigations API.

6. **LLM/vision usability evaluation is promising but unreliable unmonitored.** On HallusionBench, Guan et al. report "a 31.42% question-pair accuracy achieved by the state-of-the-art GPT-4V. Notably, all other evaluated models achieve accuracy below 16%." Vision models hallucinate objects, chart values, and colors. They are useful for *narrative synthesis over grounded evidence*, not for *detecting* facts unaided.

---

## Details

### Part A — UX Evaluation

#### A.1 Mapping heuristic frameworks onto machine-observable signals

Heuristic evaluation against Nielsen's 10 heuristics is the default low-cost usability-inspection method. Nielsen and Landauer's classic model holds that three to five evaluators identify roughly 75% of a product's usability problems (a single evaluator ≈35%); practitioner summaries put three evaluators at around 60% of the issues a wider study would find. The cognitive walkthrough is its task-specific complement, asking four questions at each step. Neither was designed for automation, but each heuristic has observable correlates in the agent-captured data.

**Table 1 — Nielsen heuristics → machine-observable evidence**

| # | Heuristic | Machine-observable signal(s) | Primary data source |
|---|-----------|------------------------------|---------------------|
| 1 | Visibility of system status | After an action, is there a status/loading indicator, an `aria-live`/`role=status` region update, or a state change in DOM within N ms? Long gaps with no feedback = violation. | DOM diff, a11y tree, journey trace timestamps, performance timings |
| 2 | Match between system & real world | System/internal jargon in visible text; cryptic error codes vs. human language | DOM text nodes, screenshots (OCR), error-state DOM |
| 3 | User control & freedom | Presence of cancel/undo/back affordances; observed backtracking and dead-ends in trace; keyboard trap detection | Journey trace, DOM, a11y tree |
| 4 | Consistency & standards | Inconsistent labels for the same destination/action across states; divergent component markup for same function | DOM across states, navigation graph |
| 5 | Error prevention | Console errors on submit; missing inline validation (no `aria-invalid`/error node before submit); destructive actions without confirm | Console errors, DOM, journey trace |
| 6 | Recognition rather than recall | Reliance on remembered values across steps; absence of autofill/affordances; high steps-to-goal | Journey trace, DOM form attributes |
| 7 | Flexibility & efficiency | Absence of shortcuts/skip links; long steps-to-goal for expert path | a11y tree (skip links), trace |
| 8 | Aesthetic & minimalist design | Visual density / element count per viewport; competing CTAs | Screenshots, DOM element counts |
| 9 | Help users recognize, diagnose, recover from errors | Error message specificity; is the error tied to the offending field (`aria-describedby`)? recovery path present? | Error-state DOM, console errors, screenshots |
| 10 | Help and documentation | Presence/findability of help affordances when stuck (after detected dead-end) | DOM, trace |

**Cognitive walkthrough → signals.** The four canonical questions (Will the user try to achieve the right effect? Will they notice the correct action is available? Will they associate the action with their goal? Will they see progress after acting?) map respectively to: (Q1) does the agent's stated intent per step match an available affordance in the DOM/a11y tree; (Q2) is that affordance present, visible, and in the accessibility tree with an accessible name; (Q3) does the affordance's accessible name/label semantically match the intent (an LLM-suited comparison, grounded on the actual label string); (Q4) does a DOM/URL/status change follow the action within a feedback window. The agent's **stated intent per step** is the key enabler — it gives a ground-truth "expected action" to compare against what the interface actually affords.

#### A.2 Quantitative UX metrics from the journey trace

- **Task success rate** = successfully completed tasks / attempted, ×100. Benchmark: MeasuringU's analysis of 1,189 tasks across 115 usability tests (3,472 users) found an average completion rate of 78%; scores below 70% indicate serious usability problems. For an agent, "success" = terminal goal state reached (target URL/DOM assertion).
- **Time-on-task**: derived from trace timestamps between task start and goal state; interpret with care — extremely short times can mean error or skipped steps, not efficiency.
- **Error rate**: count of slips (wrong clicks, corrected inputs) + mistakes (wrong path) per task; correlate with console errors and validation events.
- **Steps-to-goal**: number of agent actions to reach goal vs. the optimal path length; ratio > 1 quantifies inefficiency.
- **Backtracking / dead-ends**: detect via the navigation graph — revisited states, "back" actions, and states with no progress toward goal. A dead-end is a state from which the agent had to reverse without advancing.
- **Form friction**: visible field count vs. truly required fields; per-field correction counts; abandonment point. Evidence base: average online-form completion sits around 51–54%, with a sharp non-linear "cliff" between 5 and 7 fields (per Digital Applied's 2026 benchmark synthesis, conversion drops from ~17.0% at 5 fields to ~11.4% at 7 fields and ~6.9% at 10+ fields), and field count matters more than step count. Compute friction = f(field_count, required_field_count, corrections, time_per_field).

#### A.3 Performance-as-UX: Core Web Vitals attributed per step

The metrics: **LCP** (loading; good < 2.5 s), **INP** (responsiveness; good < 200 ms, replaced FID March 2024), **CLS** (visual stability; good < 0.1), plus **TTFB** (good < 800 ms) and **FCP** as diagnostics. Field thresholds are evaluated at the 75th percentile.

**Per-step attribution mechanism.** Use the Google `web-vitals` library **attribution build** (`web-vitals/attribution`), whose callbacks return a `MetricWithAttribution` object adding an `attribution` object of debugging detail. The relevant fields:

- **INP** (`INPAttribution`): `interactionTarget` (CSS selector of the interacted element), `interactionTargetElement` (live element, added in v4), `interactionType` (`'pointer'|'keyboard'`), `interactionTime`, and a phase breakdown — `inputDelay`, `processingDuration`, `presentationDelay` — plus `longAnimationFrameEntries` and `longestScript` (the specific slow script and which subpart it ran in) from the Long Animation Frame API.
- **LCP** (`LCPAttribution`): `element` (the LCP element), `url`, and a phase breakdown — `timeToFirstByte`, `resourceLoadDelay`, `resourceLoadDuration`, `elementRenderDelay`.
- **CLS** (`CLSAttribution`): `largestShiftTarget` (selector of the element that shifted most), `largestShiftTime`, `largestShiftValue`, `largestShiftSource` (with `node`, `previousRect`, `currentRect`).

**How to assign each metric to a journey step.** All metrics are collected through `PerformanceObserver` with `buffered: true` (the library "uses the buffered flag for PerformanceObserver, allowing it to access performance entries that occurred before the library was loaded"). Every `PerformanceEntry` carries a `startTime` relative to navigation. The harness records the wall-clock boundary of each agent step, then buckets entries into the step window `[stepStart, stepEnd)`:
- **INP**: group `event`-timing entries by `interactionId` (the Event Timing API field that ties pointerdown→pointerup→click into one interaction — MDN: "the events share the same `interactionId`"), take the max `duration` per interaction, assign by interaction time; name the offending element via `interactionTarget`.
- **CLS**: bucket `layout-shift` entries by `startTime`, summing `value` per step but **excluding** entries with `hadRecentInput === true` (shifts within 500 ms of input, per the Layout Instability spec); name the culprit via `sources[0].node` (the source list is "sorted in descending order by impact area").
- **LCP/FCP/TTFB**: per-page-load by nature, so for classic CWV only the initial load step gets them.

**SPA caveat.** Per Google's SPA Vitals FAQ, "Metric values are not reset, and the URL associated with each metric measurement is the URL the user navigated to that initiated the page load." True per-route LCP/FCP and segmented INP/CLS require the **experimental Soft Navigations API** (Chrome origin trial), which adds a `SoftNavigationEntry` and an `interaction-contentful-paint` entry and tags performance timings with a `navigationId`. Chrome's guidance: "To measure Core Web Vitals, listen to soft-navigation entries, reset the metrics on receiving these." The `web-vitals` `soft-navs` branch implements this but is experimental and "will likely remain in a separate branch... rather than be included in any production builds." Note that soft-nav TTFB "is always reported as 0 because TTFB is a server-side metric." Use the `generateTarget()` attribution option to replace fragile compiled CSS selectors with stable, component- or ARIA-based identifiers for cross-build aggregation.

#### A.4 Information architecture / navigation-graph analysis

Treat the set of visited states as a directed graph (nodes = states/URLs, edges = agent transitions). Compute:
- **Depth** (clicks from entry to goal) and **breadth** (branching factor per state); excessive depth or breadth signals IA problems.
- **Labeling consistency**: same destination reached via differently-labeled links (heuristic 4); compute by clustering edges by target and comparing visible/accessible link text.
- **Orientation cues**: presence of breadcrumbs, current-page indicators, page `<title>`/`<h1>` per state. Tree-testing research (findability of items in a hierarchy) provides the conceptual model; here the agent's traversal is the "test." A well-structured accessibility tree is also what AI agents and screen readers both rely on, so a broken tree degrades both.

#### A.5 Microcopy, empty-state, and error-state evaluation — and how to drive into those states

These states are high-value and frequently un-tested. **Deliberately drive the app into them:**
- **Empty states**: have the agent reach lists/dashboards with no data (new account, filtered-to-zero search, cleared cart).
- **Error states**: submit forms with invalid/blank/oversized inputs; trigger 404 by navigating to a bad route; force network/permission failures where possible; submit wrong credentials.
- **Loading/latency states**: capture intermediate states during slow transitions.

Then evaluate the captured DOM/screenshots: Is the error message specific and human (heuristics 2, 9)? Is it tied to the field via `aria-describedby`/`aria-invalid`? Is there a recovery path? Do empty states explain what to do next rather than showing a blank panel? Console errors captured at these moments corroborate broken states.

#### A.6 State of the art: ML/LLM-based usability evaluation

Recent systems use LLM agents as simulated users: **UXAgent** (CHI 2025, Lu et al.) generates thousands of persona-driven simulated users with an LLM-Agent module and a universal browser connector, producing qualitative and quantitative logs for researchers; **AgentA/B** runs automated A/B tests with LLM agents; **AXNav** (Taeb et al.) converts manual accessibility test instructions into replayable navigable videos; and frameworks like **WebProber** use a VLM (e.g., Claude 3.7 Sonnet) over screenshots. The consistent research position (UXAgent's authors included) is that these agents are **not** replacements for human participants but tools to pre-evaluate study design and scale exploration.

**Reliability vs. hallucination.** Vision-language models are unreliable as unmonitored *detectors*. On HallusionBench, state-of-the-art GPT-4V achieved only 31.42% question-pair accuracy with all other evaluated models below 16%; multi-object recognition induces fabricated objects; chart/value retrieval and color discrimination are weak points. Mitigations from the literature: image-grounded guidance (e.g., MARINE), structured/constrained output, and requiring every claim to be backed by retrieved evidence — grounding reduces hallucination materially (commonly cited 30–50% reductions in RAG settings). **Conclusion:** use vision models to *describe and judge* an explicitly provided, deterministically-detected evidence bundle, never to free-form "find problems."

### Part B — Accessibility Auditing

#### B.1 Engine comparison

**Table 2 — Accessibility engines**

| Engine | Vendor | Form factors | Engine basis | Notable strengths | Limits |
|--------|--------|--------------|--------------|-------------------|--------|
| **axe-core** | Deque | JS library; injectable; Playwright/Cypress/Selenium integrations; browser ext (axe DevTools) | Own rules engine; design goal of zero false positives | Industry standard; component-level scoping; CI-friendly; per-state injection | Conservative (avoids false positives → may under-report); automatable subset only |
| **Lighthouse a11y** | Google | Chrome DevTools, CLI, CI, Node | **Uses axe-core under the hood** but runs a reduced subset, not the full axe ruleset | Easy, bundled, combines with perf/SEO | Basic subset; scoring can mislead |
| **Pa11y** | Open source (orig. Nature) | CLI, dashboard, CI | Runs HTML_CodeSniffer by default; can use axe-core | Simple smoke audits; dashboards for continuous testing | CLI-only; fewer features |
| **IBM Equal Access** | IBM | Browser ext (Chrome/Firefox/Edge), Node, CI; engine injectable via `ace.js` CDN | IBM accessibility-rules engine; rulesets map to WCAG 2.0/2.1/2.2 A&AA, IBM v7.2, EN 301 549, US 508; harmonized with W3C ACT rules | Maps issues to specific WCAG requirements; ACT-aligned; JSON report with violation/potentialviolation/recommendation levels | Less ubiquitous in tooling ecosystems |
| **WAVE** | WebAIM | Browser ext, HTTP API, web app | Own engine; powers the WebAIM Million | Visual in-page overlays; great for education/manual review | Limited automation/integration options |

A practical stance: **axe-core is the deterministic workhorse** (injectable per state, zero-false-positive design, WCAG-tagged rules); **IBM Equal Access** is a strong second engine because its rules explicitly map to WCAG requirements and ACT rule IDs, useful for conformance reporting; **WAVE** and **Lighthouse** are supplements; **Pa11y** is a lightweight CI smoke test.

#### B.2 The automatable ceiling — what cannot be detected

Automated tools catch roughly **30–40% of WCAG issues** (Deque: automated issues for 16/50 WCAG 2.1 AA criteria → 20–30% of *criteria*, but 57.38% of real-world issue *volume* because high-frequency issues are automatable; UK GDS practical ceiling 40%). What automation **cannot** reliably determine, requiring human/AT testing:
- Whether alt text is *meaningful* (not just present).
- Whether reading/focus order is *logical and meaningful* (2.4.3) — tools detect tabindex misuse but not semantic order quality.
- Whether link/button text is *descriptive in context*.
- Whether content is *understandable*, error messages *helpful*, and instructions *clear* (much of Understandable/POUR).
- Correct use of ARIA in *intent* (WebAIM Million: pages using ARIA averaged more than twice the errors of pages without — ARIA is frequently misused).
- Screen-reader announcement *quality* and keyboard *operability* of complex widgets.

#### B.3 Running axe-core injected per app state

With `@axe-core/playwright`, the `AxeBuilder` class injects axe automatically (no separate `injectAxe()` step) and `analyze()` scans the page **in its current state at the moment it is called** ("AxeBuilder.analyze() will scan the page in its current state when you call it"). The pattern for agent journeys:

1. Agent drives to a state (after interactions that reveal dynamic content).
2. Call `new AxeBuilder({ page }).analyze()` — scoping with `.include()/.exclude()` and filtering with `.withTags(['wcag2a','wcag21aa','wcag22aa'])`.
3. Persist the violations array (each violation has a rule `id`, `impact` of minor/moderate/serious/critical, WCAG tags, and per-node `target` selectors + HTML snippet) keyed to the state/evidence ID.
4. Repeat per state across the journey. Because axe scans current DOM, this captures SPA states, modals, and revealed menus that a single page-load scan would miss.

For IBM Equal Access, inject `ace.js` and call `new ace.Checker().check(document, ["IBM_Accessibility"])`, which returns a JSON report mapping `ruleId`s to WCAG requirements.

#### B.4 Mapping violations to WCAG criteria

axe rules carry WCAG tags (e.g., `wcag143` = 1.4.3 Contrast, `wcag412` = 4.1.2 Name/Role/Value); IBM rules map to ACT rule IDs and WCAG requirements. The finding schema should store the WCAG success criterion (number + level) alongside the engine rule ID so findings roll up to a conformance view. The W3C ACT (Accessibility Conformance Testing) rules provide the harmonization layer across engines.

#### B.5 Keyboard-navigation and focus-order via the accessibility tree

Evaluate from the a11y tree + DOM, corroborated by driving Tab/Shift+Tab/Enter/Space/Escape/arrow keys:
- **Reachability**: every interactive element (role button/link/textbox/etc.) must be focusable and in the tab order; flag interactive elements not reachable by keyboard.
- **Focus order (2.4.3)**: compare DOM/tab order against visual reading order; flag positive `tabindex` and order mismatches. The standard cannot be fully automated (logical order is semantic) but disordered/positive-tabindex patterns are detectable.
- **Focus visibility (2.4.7 / 2.4.11)**: check for a visible focus indicator with ≥3:1 contrast (screenshot diff of focused vs unfocused state).
- **Keyboard traps (2.1.2)**: detect when focus cannot leave a component and Escape fails — directly observable when the agent drives keys.
- **Modals**: focus should move into the dialog, be trapped while open, and return to the trigger on close (with `role=dialog`/`alertdialog`).

Microsoft's `@playwright/mcp` exposes structured accessibility snapshots (the same tree screen readers use), so an agent navigating by the tree fails in the same ways a screen-reader user would — making the tree both the test surface and the artifact.

#### B.6 Color-contrast computation

WCAG contrast is deterministic and fully computable. For each text node, get foreground and background sRGB, linearize each channel (`c ≤ 0.03928 ? c/12.92 : ((c+0.055)/1.055)^2.4`), compute relative luminance `L = 0.2126·R + 0.7152·G + 0.0722·B`, then contrast ratio `(L1 + 0.05)/(L2 + 0.05)` (1:1 to 21:1). Thresholds: **4.5:1** normal text, **3:1** large text (≥18 pt, or 14 pt bold) and UI components/graphics (1.4.11), **7:1** for AAA. Caveats requiring care: gradient/image backgrounds, text over images, and partially-transparent layers — these are where automated contrast checks become unreliable and a screenshot-based check helps. Contrast is the single most common real-world failure (WebAIM Million 2026: low-contrast text on 83.9% of home pages, averaging 34 distinct instances per page).

#### B.7 ARIA-live / dynamic-content checks (4.1.3 Status Messages)

After agent actions that produce status/error/results without focus change, verify the update was exposed via a live region:
- Presence of `aria-live="polite"|"assertive"`, `role="status"` (implicit polite), `role="alert"` (implicit assertive), `role="log"`.
- The live region should exist in the DOM **before** the update (regions injected and immediately populated may not announce; best practice waits ~2 s after injection).
- Flag `aria-live="assertive"`/`role="alert"` overuse (interrupts the user) and dynamically hidden messages (`visibility:hidden` content isn't in the a11y tree).
- Detection method: diff the a11y tree before/after the action; if visible content changed but no live region carried the change, flag a 4.1.3 risk. (Whether the announcement is actually *useful* still needs AT testing.)

---

### Required Deliverable (i): Signal Catalog

**Table 3 — UX/A11y signal catalog (data source · computation · severity)**

| Signal | Type | Data source | How to compute | Severity assignment |
|--------|------|-------------|----------------|---------------------|
| Color-contrast failure | A11y (1.4.3/1.4.11) | DOM + computed styles / screenshot | Luminance ratio vs 4.5:1 / 3:1 | severity = impact(serious) × reach(# nodes × page frequency) |
| Missing alt text | A11y (1.1.1) | DOM `<img>` | `alt` absent (not `alt=""`) | serious × count |
| Missing form label | A11y (1.3.1/4.1.2) | DOM + a11y tree | input lacks accessible name | critical (blocks task) × count |
| Empty link/button | A11y (2.4.4/4.1.2) | a11y tree | interactive node, no accessible name | serious × count |
| Missing doc language | A11y (3.1.1) | DOM `<html lang>` | attribute absent | moderate × 1/page |
| Keyboard unreachable control | A11y (2.1.1) | a11y tree + key-drive | interactive, not in tab order | critical × count |
| Keyboard trap | A11y (2.1.2) | journey trace (keys) | focus cannot exit; Esc fails | critical × occurrence |
| Focus-order mismatch | A11y (2.4.3) | DOM order vs visual | positive tabindex / order divergence | serious × occurrence |
| No visible focus indicator | A11y (2.4.7) | screenshot diff focused state | no indicator / <3:1 | serious × count |
| Missing status-message live region | A11y (4.1.3) | a11y tree diff | content changed, no live region | moderate–serious × occurrence |
| LCP slow (per step) | Perf/UX | web-vitals attribution | LCP > 2.5 s; `element`, phase breakdown | severity by threshold band × step traffic |
| INP slow (per step) | Perf/UX | web-vitals + Event Timing | INP > 200 ms; `interactionTarget`, phase | band × interaction frequency |
| CLS high (per step) | Perf/UX | web-vitals + Layout Instability | CLS > 0.1; `largestShiftTarget` | band × step reach |
| No system-status feedback | UX (H1) | DOM diff + timings | action → no status/indicator within window | impact × frequency of action |
| Backtracking / dead-end | UX (H3) | navigation graph | revisited/no-progress states | impact × # affected tasks |
| Excessive steps-to-goal | UX (H6/7) | journey trace | actual/optimal path ratio | impact × task criticality |
| Form friction | UX | DOM + trace | field count, corrections, abandon point | impact × form criticality |
| Unhelpful error message | UX (H9) | error-state DOM | specificity, field association, recovery | LLM-judged, grounded × frequency |
| Console error on action | UX/Robustness | console log | error emitted during step | impact (broken) × frequency |
| Inconsistent labels | UX (H4) | DOM + nav graph | same target, different labels | moderate × occurrence |

**Severity model.** Adopt Nielsen's definition: severity = f(**frequency**, **impact**, **persistence**), with market impact as an overlay. Operationalize as a **severity × reach** score: map each finding to an impact tier (axe's minor/moderate/serious/critical for a11y; Nielsen 0–4 cosmetic→catastrophe for UX) and multiply by **reach** = number of affected nodes/states × fraction of journeys/users encountering the state. This prioritizes a serious issue on a high-traffic step above a critical issue on a rarely-reached state. Where possible average severity over multiple evaluators/runs, since single-evaluator severity is noisy.

### Required Deliverable (ii): Deterministic-first pipeline + bounded LLM layer

**Stage 0 — Capture (given):** per-state screenshots, journey trace with per-step intent, DOM + a11y tree, console errors, performance timings.

**Stage 1 — Deterministic engine (no LLM):**
1. **A11y scan**: inject axe-core (and optionally IBM Equal Access) per captured state; collect violations with rule ID, impact, WCAG tags, node targets.
2. **Contrast & focus**: compute contrast ratios from styles; analyze a11y-tree tab order and key-drive logs for reachability/traps/focus order.
3. **CWV attribution**: collect `web-vitals` attribution build output; bucket PerformanceEntries into step windows; attach offending element + phase breakdown per step.
4. **Journey metrics**: compute task success, time-on-task, steps-to-goal, backtracking/dead-ends, form friction from the trace + nav graph.
5. **Heuristic signals (rule-based subset)**: feedback-after-action, console-error-on-step, label inconsistency, live-region presence.
6. **Normalize** every finding into the finding schema; assign WCAG/heuristic mapping and severity × reach. This stage is deterministic, reproducible, and the source of truth.

**Stage 2 — Evidence bundle assembly:** for each finding, build a bundle: the annotated screenshot(s) (bounding boxes/marks on the offending element — "set-of-mark"-style prompting improves grounding), the finding record(s), the relevant DOM/a11y snippet, and the step's stated intent.

**Stage 3 — Bounded LLM layer (narrative judgment only):**
- The LLM receives **only** the evidence bundle and the deterministic findings. Its job: (a) write human-readable explanations and suggested fixes; (b) judge the genuinely subjective items that have no deterministic detector — alt-text *meaningfulness*, error-message *helpfulness*, label/intent semantic match, microcopy/empty-state quality, focus-order *logicality*; (c) cluster and prioritize.
- **Grounding rules to prevent invented findings:** every LLM statement must reference an `evidence-id`; the LLM may not assert a finding that lacks a backing evidence ID or deterministic signal; require structured output (JSON conforming to the finding schema) with type checking; discard any output whose claimed evidence cannot be matched back to the bundle (attribution-style verification); use vision only to *describe/judge provided marked regions*, never to scan for new issues. These mirror documented hallucination-mitigation practice (search/evidence grounding, structured extraction, citation/attribution verification) and the VLM reliability limits above.
- **Confidence & escalation:** LLM findings carry a confidence and a `needs-human-review` flag; anything in the ~60–70% non-automatable space is explicitly routed to manual/AT testing rather than asserted as resolved.

This division keeps the reproducible, legally-relevant conformance facts deterministic while using the LLM where it genuinely adds value — narrative and grounded subjective judgment.

### Required Deliverable (iii): Finding schema

```json
{
  "finding_id": "string (uuid)",
  "signal": "string (catalog key, e.g. 'contrast.text')",
  "category": "a11y | ux | performance | robustness",
  "wcag_criterion": { "id": "1.4.3", "level": "AA" },
  "heuristic": "nielsen-1 | cw-q3 | null",
  "engine_rule_id": "axe: color-contrast | ibm: <ruleId> | null",
  "severity": {
    "impact_tier": "minor|moderate|serious|critical (a11y) or 0-4 (ux)",
    "reach": { "nodes": 12, "states_affected": 3, "journey_fraction": 0.8 },
    "score": "number (impact × reach)"
  },
  "evidence_ids": ["screenshot:state12#bbox3", "dom:state12#node45", "trace:step7", "cwv:step7:inp"],
  "location": {
    "state_id": "state12",
    "url_or_route": "/checkout",
    "step_index": 7,
    "selector": "#confirm",
    "accessible_name": "Confirm",
    "bounding_box": [12, 340, 120, 44]
  },
  "observed": "string — what the deterministic signal detected",
  "metric_detail": { "value": 312, "unit": "ms", "threshold": 200, "attribution": { "interactionTarget": "#confirm", "inputDelay": 27, "processingDuration": 264, "presentationDelay": 21 } },
  "suggested_fix": "string (LLM-generated, grounded)",
  "source_layer": "deterministic | llm",
  "confidence": 0.0,
  "needs_human_review": true
}
```

The schema satisfies the required fields (signal, severity, evidence-ids, location, suggested-fix) and adds the WCAG/heuristic mapping, attribution detail, and the deterministic-vs-LLM provenance flag that keeps the two layers auditable.

---

## Recommendations

**Stage 1 (now) — Stand up the deterministic core.** Wire `@axe-core/playwright` to scan every captured state with `wcag2a/wcag21aa/wcag22aa` tags; add the contrast, focus-order, and live-region checks; compute the journey metrics. Emit everything in the finding schema with severity × reach. *Benchmark that changes the plan:* if axe + IBM dual-engine agreement is high and false positives near zero, you can trust auto-fail gating in CI; if false positives appear, downgrade to advisory.

**Stage 2 — Add per-step CWV attribution.** Ship the `web-vitals` attribution build in the instrumented app build and bucket entries by step. *Threshold:* INP > 200 ms, LCP > 2.5 s, or CLS > 0.1 on any high-traffic step becomes a tracked finding. Adopt the Soft Navigations API (behind a flag) only once you need true per-route LCP/FCP on SPA transitions — until then, label LCP/FCP as initial-load-only.

**Stage 3 — Add the bounded LLM layer.** Only after the deterministic findings and evidence bundles are stable. Start with narrative explanations + suggested fixes (low risk), then enable grounded subjective judgments (alt-text quality, error microcopy, focus-order logic) with mandatory evidence-id citation and JSON-schema output. *Benchmark:* spot-audit a sample of LLM findings against human review; if invented-finding rate exceeds a small tolerance, tighten grounding (drop to describe-only) before expanding scope.

**Stage 4 — Drive deliberately into empty/error/loading states** as part of the agent's scripted journeys, since these are where microcopy and recovery problems concentrate and where automated coverage is otherwise blind.

**Always:** treat the 30–40% automatable ceiling as a hard planning constraint — explicitly route the remaining ~60–70% (screen-reader behavior, meaningful order, cognitive load) to human/AT testing, and never report "no automated violations" as "accessible."

## Caveats

- **Automated ≠ conformant.** WebAIM and Deque both stress that absence of detected errors does not mean a page is accessible; automated tools cover only a minority of WCAG criteria.
- **Vendor coverage claims are often inflated.** In *FTC v. accessiBe* (filed January 2025; final order April 2025, with a $1M monetary penalty), the FTC challenged the overlay vendor's claim that its widget "makes a website compliant with 30% of WCAG's requirements immediately and initiates an AI process that makes the website fully compliant with the remaining 70%... within 48 hours." Treat any coverage claim above ~80% without "with semi-automated/manual testing" as suspect.
- **VLM/LLM findings can be confidently wrong** (HallusionBench: 31.42% SOTA question-pair accuracy; object/color/value hallucinations); this is why the architecture forbids ungrounded LLM detection.
- **CWV attribution on SPAs is not fully standardized** — the Soft Navigations API is experimental and subject to change; per-route LCP/FCP should be flagged as provisional, and soft-nav TTFB is reported as 0.
- **Selectors drift across builds**; use stable component/ARIA identifiers (`generateTarget()`) for longitudinal aggregation.
- **Severity is inherently noisy** from a single evaluator; average across runs/engines where feasible.
- **Some 2026-dated figures** (e.g., evolving form-conversion benchmarks) come from secondary aggregators and should be re-verified against primary reports before external publication.

## REFERENCES

[1] Nielsen J. *10 Usability Heuristics for User Interface Design*. Nielsen Norman Group. [https://www.nngroup.com/articles/ten-usability-heuristics/](https://www.nngroup.com/articles/ten-usability-heuristics/)
[2] Nielsen J. *Severity Ratings for Usability Problems*. NN/G. [https://www.nngroup.com/articles/how-to-rate-the-severity-of-usability-problems/](https://www.nngroup.com/articles/how-to-rate-the-severity-of-usability-problems/)
[3] Nielsen Norman Group. *Evaluate Interface Learnability with Cognitive Walkthroughs*. [https://www.nngroup.com/articles/cognitive-walkthroughs/](https://www.nngroup.com/articles/cognitive-walkthroughs/)
[4] Deque Systems. *The Automated Accessibility Coverage Report*. [https://www.deque.com/automated-accessibility-coverage-report/](https://www.deque.com/automated-accessibility-coverage-report/)
[5] WebAIM. *The WebAIM Million 2025*. [https://webaim.org/projects/million/2025](https://webaim.org/projects/million/2025)
[6] WebAIM. *The WebAIM Million 2026*. [https://webaim.org/projects/million/](https://webaim.org/projects/million/)
[7] Google. *Understanding Core Web Vitals and Google search results*. [https://developers.google.com/search/docs/appearance/core-web-vitals](https://developers.google.com/search/docs/appearance/core-web-vitals)
[8] GoogleChrome. *web-vitals library (attribution build)*. GitHub. [https://github.com/GoogleChrome/web-vitals](https://github.com/GoogleChrome/web-vitals)
[9] Chrome for Developers. *Soft Navigations*. [https://developer.chrome.com/docs/web-platform/soft-navigations](https://developer.chrome.com/docs/web-platform/soft-navigations)
[10] web.dev. *Vitals and Single Page Application FAQ*. [https://web.dev/articles/vitals-spa-faq](https://web.dev/articles/vitals-spa-faq)
[11] W3C. *Event Timing API*. [https://www.w3.org/TR/event-timing/](https://www.w3.org/TR/event-timing/)
[12] WICG. *Layout Instability API*. [https://wicg.github.io/layout-instability/](https://wicg.github.io/layout-instability/)
[13] Playwright. *Accessibility testing*. [https://playwright.dev/docs/accessibility-testing](https://playwright.dev/docs/accessibility-testing)
[14] Deque. *@axe-core/playwright*. npm. [https://www.npmjs.com/package/@axe-core/playwright](https://www.npmjs.com/package/@axe-core/playwright)
[15] IBMa. *equal-access accessibility-checker-engine*. GitHub. [https://github.com/IBMa/equal-access](https://github.com/IBMa/equal-access)
[16] W3C WAI. *Equal Access Accessibility Checker ACT Implementation*. [https://www.w3.org/WAI/standards-guidelines/act/implementations/equal-access/](https://www.w3.org/WAI/standards-guidelines/act/implementations/equal-access/)
[17] CKEditor. *Comparing the 6 best tools for automated accessibility testing*. [https://ckeditor.com/blog/automated-accessibility-testing/](https://ckeditor.com/blog/automated-accessibility-testing/)
[18] W3C. *Understanding Success Criterion 2.4.3 Focus Order*. [https://www.w3.org/TR/UNDERSTANDING-WCAG20/navigation-mechanisms-focus-order.html](https://www.w3.org/TR/UNDERSTANDING-WCAG20/navigation-mechanisms-focus-order.html)
[19] WebAIM. *Keyboard Accessibility*. [https://webaim.org/techniques/keyboard/](https://webaim.org/techniques/keyboard/)
[20] W3C. *G17: Ensuring contrast ratio (luminance formula)*. [https://www.w3.org/TR/WCAG20-TECHS/G17.html](https://www.w3.org/TR/WCAG20-TECHS/G17.html)
[21] MDN. *ARIA live regions*. [https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions)
[22] Lu Y, et al. *UXAgent: An LLM Agent-Based Usability Testing Framework for Web Design*. arXiv:2502.12561. [https://arxiv.org/abs/2502.12561](https://arxiv.org/abs/2502.12561)
[23] Guan T, et al. *HallusionBench: An Advanced Diagnostic Suite for Entangled Language Hallucination and Visual Illusion in LVLMs*. arXiv:2310.14566. [https://arxiv.org/pdf/2310.14566](https://arxiv.org/pdf/2310.14566)
[24] MeasuringU. *Rating the Severity of Usability Problems*. [https://measuringu.com/rating-severity/](https://measuringu.com/rating-severity/)
[25] NN/G. *Tree Testing: Fast, Iterative Evaluation of Menu Labels and Categories*. [https://www.nngroup.com/articles/tree-testing/](https://www.nngroup.com/articles/tree-testing/)
[26] A11yProof. *What Automated Accessibility Testing Actually Catches*. [https://a11yproof.com/resources/guides/automated-accessibility-testing-accuracy](https://a11yproof.com/resources/guides/automated-accessibility-testing-accuracy)
[27] Digital Applied. *Form Conversion Rate Benchmarks 2026*. [https://www.digitalapplied.com/blog/form-conversion-rate-benchmarks-2026-data-points](https://www.digitalapplied.com/blog/form-conversion-rate-benchmarks-2026-data-points)
[28] MDN. *PerformanceEventTiming.interactionId*. [https://developer.mozilla.org/en-US/docs/Web/API/PerformanceEventTiming/interactionId](https://developer.mozilla.org/en-US/docs/Web/API/PerformanceEventTiming/interactionId)
[29] Firecrawl. *Reduce hallucinations with search-grounded LLM responses*. [https://www.firecrawl.dev/glossary/web-search-apis/reduce-hallucinations-search-grounded-llm-responses](https://www.firecrawl.dev/glossary/web-search-apis/reduce-hallucinations-search-grounded-llm-responses)