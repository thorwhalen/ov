# Grounding LLM Analysis in Captured Web-Application Evidence: A Reliability-First Architecture for UX and Software-Architecture Reports

*Author: Thor Whalen*
*Date: June 4, 2026*

> **How to use this document.** It is written for a Python architect / AI R&D practitioner. Progressive disclosure is applied throughout: each Part opens with the simple decision, then exposes the mechanisms and trade-offs. If you read only the TL;DR and Recommendations you have the actionable plan; the Details justify it from primary sources.

## TL;DR

- **Build the system as a deterministic tool library wrapped by a thin skill layer that a host agent (Claude Code) orchestrates — not as a bespoke in-package multi-agent system.** The "harness is the agent" pattern lets Claude Code supply planning, delegation, and recovery for free; your job is to write well-scoped tools and `SKILL.md` procedural knowledge, keep the factual core callable with zero model calls, and emit schema-validated structured outputs. This is the fastest path to a working, testable, cheap system, and the lift to optional in-package agents later is mechanical (wrap the same tool functions in thin role agents).
- **Hallucination is controlled architecturally, not by prompt-wishing:** hard-separate deterministic facts (computed upstream — stack detection, network facts, a11y/perf metrics) from LLM judgment (interpretation only), force every claim to cite an evidence ID, use Set-of-Mark-style annotated screenshots so the vision model grounds on marked regions, validate all returns against JSON Schema/Pydantic, and add a cite-or-abstain rule plus a chain-of-verification pass.
- **Compress per-section reports into one machine-readable synopsis via map-reduce with a stable schema**, deduplicating findings and preserving provenance links back to evidence IDs, so a downstream creation/modification agent consumes structured findings (not prose) to build or change a related system.

## Key Findings

1. **Annotated screenshots are a Set-of-Mark (SoM) visual prompt.** The upstream system's bounding boxes + captions are exactly the technique shown to "unleash extraordinary visual grounding" and to "effectively reduce the hallucination commonly encountered in Large Multimodal Models." This is the single highest-leverage grounding decision already made; the architecture should exploit it by referring to marks by ID in both prompts and outputs.
2. **Claude reasons best with images before text, and image token cost is computable and boundable.** Anthropic gives an exact estimate — an image uses approximately `width × height / 750` tokens — and caps native resolution (1568 px long edge / ~1568 tokens on standard models; 2576 px long edge / 4784 tokens on Opus 4.7/4.8). This makes a token budget a deterministic upstream computation, not a guess.
3. **Structured outputs are now a hard guarantee, not a prompt hope.** Both Anthropic (JSON outputs + strict tool use, GA on Opus/Sonnet 4.5+) and OpenAI (Structured Outputs) compile your JSON Schema into a grammar and constrain decoding. Per OpenAI's August 6, 2024 launch post, "gpt-4o-2024-08-06 with Structured Outputs scores a perfect 100%. In comparison, gpt-4-0613 scores less than 40%" on complex JSON-schema-following evals. Use Pydantic/Zod as the single source of truth (SSOT) for the schema.
4. **The deterministic/judgment split maps cleanly onto Skills + code.** Anthropic's own Skills guidance says code in a skill provides "the deterministic reliability that only code can provide… consistent and repeatable," while the model supplies judgment. This is the SOLID-friendly seam: facts are pure functions; judgment is an LLM call over those facts.
5. **Map-reduce / hierarchical merging is the validated pattern for compressing many reports**, and "decompose-then-verify" (atomic claims checked against source) is the validated pattern for keeping the synopsis faithful.
6. **Orchestrator-worker multi-agent systems outperform single agents but cost ~15× the tokens.** Per Anthropic's "How we built our multi-agent research system," a multi-agent system with Claude Opus 4 as the lead agent and Claude Sonnet 4 subagents "outperformed single-agent Claude Opus 4 by 90.2% on our internal research eval," while "multi-agent systems use about 15× more tokens than chats" — which is exactly why you defer in-package agents until the host-orchestrated version proves value.

## Details

### Part 1 — Evidence-bundle assembly for multimodal models

**Goal.** Package annotated screenshots + structured facts so a vision-capable LLM reasons over grounded inputs rather than guessing, while controlling token cost.

**1.1 Exploit the annotations as Set-of-Mark prompting.** The captured artifacts (bounding boxes marking the element each journey step targeted, captioned with intent) are a textbook Set-of-Mark (SoM) visual prompt. Yang et al. (2023) overlay alphanumeric marks on image regions and show GPT-4V then answers questions requiring visual grounding far more reliably; follow-up work confirms marks "effectively reduce the hallucination commonly encountered in Large Multimodal Models." **Architectural consequence:** every region the model is allowed to talk about should carry a stable mark ID (e.g., `R3`), and that same ID should appear in the structured facts and be required in the model's output. This turns "describe what you see" (hallucination-prone) into "interpret marked region R3" (grounded).

**1.2 Order: images before text.** Anthropic's vision guidance is explicit: "Claude works best when images come before text. Images placed after text or interpolated with text still perform well, but if your use case allows it, prefer an image-then-text structure." So the bundle ordering is: `[system/role] → [image(s) with marks] → [structured facts keyed to marks] → [task instruction]`.

**1.3 Token budgeting is deterministic.** Anthropic's documentation states an image "uses approximately `width * height / 750` tokens, where the width and height are expressed in pixels." Native resolution caps are explicit: "For other models: 1568 tokens, and at most 1568 pixels on the long edge"; "For Claude Opus 4.7 [and] 4.8: 4784 tokens, and at most 2576 pixels on the long edge." Anthropic adds: "High-resolution images on Claude Opus 4.7 and Claude Opus 4.8 can use up to approximately 3x more image tokens than on prior models (4784 versus 1568 tokens per image). If you don't need the additional fidelity, downsample images before sending to control token costs." Practical limits (verbatim from the docs): "20 per message on claude.ai"; "100 per request on the API, for models with a 200k-token context window"; "600 per request on the API, for all other models"; "The maximal dimensions per image are 8000x8000 px. If you submit more than 20 images in one API request, this limit is reduced to 2000x2000 px." File-size limits are "10 MB (base64-encoded) when using the Claude API directly" and "5 MB (base64-encoded) on Amazon Bedrock and Vertex AI." Because all of these are knowable before the call, the bundle assembler (deterministic code) should compute the projected token cost and enforce a budget.

**1.4 Full screenshot vs. crop vs. both.** Send the full annotated screenshot for layout/flow context; send crops when detail density defeats the resolution cap. Anthropic ships an official crop-tool pattern (cookbook *"Giving Claude a crop tool for better image analysis,"* Nov 22, 2025) using normalized 0–1 coordinates and an agentic "zoom-in" loop, motivated verbatim by: "For detailed tasks—like reading small text, comparing similar values in a chart, or examining fine details—this can be limiting. The solution: Give Claude a tool that lets it 'zoom in' by cropping regions of interest." Recommended default: send the full marked screenshot always; attach crops for any region whose rendered text/detail would be sub-readable after downsampling to the resolution cap. For dense flows, prefer many small targeted crops over one huge image (mirrors Anthropic's "many small, targeted searches" tool guidance).

**1.5 Interleaving images and structured facts.** Keep images first, then a compact structured-facts block that references mark IDs. Don't restate in prose what is already a fact; the model's job is interpretation. Use the upstream-computed facts (network/API, tech-stack, a11y/perf) as the authoritative ground truth and label them as such in the bundle (`evidence`, not `assumptions`).

**1.6 What to omit.** Omit raw HAR dumps, full DOM, and minified bundle text from the model context — these belong to deterministic tools, not the model's window. Anthropic restricts tool responses to 25,000 tokens by default in Claude Code and recommends pagination/filtering/truncation; apply the same discipline. The model should receive *derived facts*, with the raw artifacts reachable by ID through a tool if a verification pass needs them (just-in-time retrieval / progressive disclosure).

### Part 2 — Hallucination-reduction techniques for this setting

**2.1 The architectural separation (the core principle).** Compute facts deterministically upstream; let the LLM only interpret. This is the strongest lever and aligns with Anthropic's Skills philosophy that code provides "deterministic reliability… consistent and repeatable" while the model reasons. In schema terms, every output object has two kinds of fields: `evidence_refs` (IDs into the deterministic fact store) and `judgment` (model interpretation). The model may never populate a fact field; it may only cite one.

**2.2 Cite-the-evidence prompting.** Require each finding to carry one or more evidence IDs (mark ID, network-fact ID, metric ID). In Amazon's Conversational Shopping Agent work (Zeng, Liu, Dai et al., *"Cite Before You Speak,"* arXiv:2503.04830), the citation-generation paradigm "substantially improves grounding performance by 13.83%" on real-world data, with online A/B tests showing a 3%–10% customer-engagement lift; importantly it also produced natural "refusal signals" ("the reviews do not provide information about…") when evidence was insufficient. Fine-grained grounded citation (FRONT: select supporting quotes first, then generate conditioned on them) is the research-backed version of this.

**2.3 Structured outputs via JSON Schema / tool use / Pydantic.** Use constrained decoding to guarantee shape. Anthropic's structured outputs (JSON outputs + strict tool use) "compile your JSON schema into a grammar and actively restrict token generation during inference"; OpenAI reports a perfect 100% on complex JSON-schema-following with gpt-4o-2024-08-06 versus under 40% for gpt-4-0613. Caveat to state plainly: schema compliance guarantees *shape, not truth* — "you might get perfectly formatted incorrect answers." That is why structure is necessary but not sufficient, and must be paired with citation + verification.

**2.4 Abstention.** Make "I cannot determine this from the evidence" a first-class, schema-valid output value (an enum member or a dedicated `undetermined` finding type), not an error. Uncertainty-based abstention research (Tomani, Chaudhuri, Evtimov, Cremers & Ibrahim, arXiv:2404.10960) reports: "By sacrificing only a few highly uncertain samples we can improve correctness by 2% to 8%, avoid 50% hallucinations via correctly identifying unanswerable questions" (their In-Dialogue Uncertainty measure filters ~50% of unanswerable questions while refusing only 10% of answerable ones). Knowledge-aware refusal is fragile in raw models, so make abstention *cheap and legal* in the schema rather than relying on the model's instinct.

**2.5 Verification passes (Chain-of-Verification).** Add a CoVe stage: after drafting findings, the system plans verification questions, answers them independently (ideally with a fact lookup tool over the deterministic store), and revises. Per Dhuliawala et al. (Meta AI / ETH Zurich, arXiv:2309.11495, Table 3), Llama 65B FactScore rose 55.9 (few-shot) → 63.7 (CoVe factored) → 71.4 (CoVe factor+revise) — a 28% gain over few-shot, with factor+revise the most effective variant. The "factored" design (answer verification questions independently of the original answer) is a natural fit because your facts are already addressable by ID. Pair with a faithfulness check that decomposes the report into atomic claims and tests each for entailment against cited evidence (NLI-style; RAGAS-style faithfulness = fraction of grounded claims).

**2.6 Confidence calibration.** Attach a calibrated confidence to each judgment and a coverage rule (report only above a threshold; abstain below). Treat single-pass model confidence as weak; prefer evidence-sufficiency signals (does the cited evidence exist and entail the claim?) over verbalized confidence alone.

### Part 3 — Prompt-and-task patterns for the two analytical jobs, in two modes

Two jobs (Arch-Analyst, UX-Analyst) × two modes (reconstruction of a foreign target; review of your own system). The mode changes the *goal and output*, not the grounding discipline.

**3.1 Arch-Analyst — reconstruction mode (foreign target).** Input: deterministic stack/bundle/API facts. Task: "From these facts, infer the architecture and produce a reusable interaction-pattern catalog and a rebuild blueprint." Tooling note: tech-stack facts come from fingerprinting (Wappalyzer-style: HTTP headers, JS globals like `window.__NUXT__`, file paths like `/_next/`, cookies, meta tags), each with a confidence score. The prompt must instruct the model to **infer design intent** (why this stack, what the team optimized for) but to tag each inference with the evidence and a confidence, and to abstain where signals are absent (pure backend technologies without client-facing signatures are not detectable). Output: a blueprint of components, data flow, and an interaction-pattern catalog (reusable patterns abstracted from observed journeys), each pattern linked to the marks/journey steps that evidence it.

**3.2 Arch-Analyst — review mode (own system).** Same facts, different goal: critique the architecture, flag risks (outdated libraries/CVEs, vendor lock-in, perf risk), give concrete fixes, and **diff against a prior run** if present (what changed: CDN swap, framework migration, new API dependency). Output is severity-ranked remediation tied to evidence IDs.

**3.3 UX-Analyst — review mode (own system).** Input: findings + annotated screenshots. Task: produce severity-ranked usability issues with concrete fixes, grounded in marks. Use Nielsen's 10 heuristics as the rubric and Nielsen's 0–4 severity scale (0 = not a problem; 1 = cosmetic; 2 = minor; 3 = major; 4 = catastrophe). Each issue cites the violated heuristic, the mark/region, and a severity with rationale. Reliability note from the HCI literature (Nielsen, Bellcore, CHI'92 *"Reliability of severity estimates"*): "Ratings from single evaluators are very unreliable… but the mean severity rating from four evaluators gets within half a rating point of the true severity 95% of the time" — which motivates either multiple sampled passes or a verification pass for severity, and explicit humility in the output.

**3.4 UX-Analyst — reconstruction mode (foreign target).** Goal shifts from "fix" to "catalog": infer the design intent behind each interaction, extract reusable interaction patterns, and note what a rebuild should preserve vs. improve. Still grounded in marks and journey steps.

**3.5 Shared prompt scaffolding.** Organize every analysis prompt into delineated sections (Anthropic recommends `<background_information>`, `<instructions>`, tool guidance, output description via XML/Markdown). Fix the "altitude": specific enough to guide, flexible enough to reason — avoid both brittle if-else prompts and vague guidance. Bake in: (a) images-before-text, (b) cite-every-claim, (c) abstain-when-unsupported, (d) emit only schema-valid JSON.

### Part 4 — Orchestration: host-agent-via-skills vs. in-package agents

**4.1 The "harness is the agent" thesis.** Claude Code's own docs state it "serves as the agentic harness around Claude"; the community framing is **Agent = Model + Harness**. The harness — not the model — supplies tool dispatch, context management, permission gating, recovery ladders, and termination logic; as Anthropic's engineering writing notes, even a frontier model running in a loop across multiple context windows will underperform without a well-designed harness. The strategic implication for this system: **you do not need to build a harness. You need to supply tools + procedural knowledge to an existing one.**

**4.2 Author the procedural knowledge as Agent Skills (SKILL.md).** A skill is a directory with a `SKILL.md` (YAML frontmatter: `name`, `description`; Markdown body) plus optional `scripts/`, `references/`, `assets/`. Progressive disclosure is the core mechanism: only `name`+`description` load at startup; the body loads when relevant; bundled files load only as needed — so a tool library of many skills has a small context footprint. The open standard (agentskills.io, released Dec 18 2025) makes skills portable across Claude Code, Codex CLI, Gemini CLI, and others. Authoring guidance from Anthropic and practitioners: write a "pushy," trigger-rich `description` (Claude under-triggers); prefer "explain-the-why" over ALL-CAPS imperatives; split files past ~300 lines; keep skills small (the median public skill is ~1,414 tokens).

**4.3 Expose the deterministic core as tools (MCP or local scripts).** MCP standardizes "what the agent can access"; Skills standardize "how the agent should work" — complementary layers. Tools should be model-controlled, return errors in-result (not as protocol errors) so the model can react, and follow Anthropic's tool-writing guidance: unambiguous names (`screenshot_id`, not `id`), strict data models, token-bounded responses with pagination/filtering, and prompt-engineered error messages. Crucially, **the tools are callable with no model at all** — they're pure Python functions with Pydantic I/O — which is what keeps the system testable and cheap.

**4.4 Conceptual role split, expressed first as skills.** Three roles map to three skills the host follows in sequence:
- **Operator skill** — assemble the evidence bundle (apply token budget, choose full vs. crop, order images-before-facts), call deterministic tools, and hand a grounded bundle to the analysts.
- **UX-Analyst skill** — run the UX critique/reconstruction prompt patterns (Part 3), emit schema-valid findings with evidence refs.
- **Arch-Analyst skill** — run the architecture reconstruction/review prompt patterns, emit schema-valid blueprint/remediation with evidence refs.

Each skill instructs the host *which tool functions to call in what order, what schema to emit, and when to abstain*. The host (Claude Code) supplies planning, retries, and recovery.

**4.5 Trade-offs: host-orchestration vs. self-contained agent.**
- *Speed-to-working-system:* host-orchestration wins decisively — no harness to build, no agent loop, no context-management code (the SDK handles compaction, tool dispatch, stop reasons).
- *Cost:* host-orchestration is cheaper for the single-report case; multi-agent fan-out costs ~15× tokens (Anthropic's figure) and is only worth it for breadth-heavy parallel work.
- *Determinism/repeatability:* the *deterministic core* is fully repeatable regardless; the model layer is not, but constrained decoding + fixed skills + low temperature narrow the variance. A self-contained orchestrator gives you more control over the loop but you must re-implement the recovery ladder, compaction, and typed terminal states that Claude Code already has.
- *Testability:* keep the model out of the unit tests. Test tools deterministically (golden inputs → golden facts). Test skills with eval scenarios (with-skill vs. without-skill). This is only possible because the core is model-free.

**4.6 The mechanical lift path to optional in-package agents.** When/if you productize a self-contained system, what *changes* is small and what's *reused* is large:
- **Reused unchanged:** the entire deterministic tool library, the Pydantic/JSON schemas (SSOT), the evidence-bundle assembler, the prompt templates embedded in skills, the synopsis map-reduce.
- **Changes:** the `SKILL.md` procedural files become thin agent definitions (`.claude/agents/*.md` with `name`, `description`, restricted `tools`, system prompt) or Agent-SDK `agents` parameter entries; an orchestrator agent (the former "host" role) sequences Operator → UX-Analyst/Arch-Analyst → synopsis using the Task tool / orchestrator-worker pattern. The orchestrator must stay a *pure coordinator* (it plans and delegates, it does not analyze) — practitioners report plan quality degrades when the orchestrator also does work. Model routing: Opus-class for orchestration/architecture reasoning, Sonnet/Haiku for parallel workers. Structured outputs via the Agent SDK (`output_format` / `structured_output`) give validated JSON at the end of multi-turn tool use.

The key insight: **skills and thin agents are two serializations of the same procedural knowledge over the same tool functions.** You are not rewriting the system; you are re-hosting it.

### Part 5 — Extract-and-aggregate / synopsis patterns

**5.1 Map-reduce over per-section reports.** Map: summarize each section report independently into structured findings. Reduce: merge into one synopsis. For many reports, use hierarchical merging (pair and re-summarize through layers) — research shows this matches or beats full-context processing at lower cost. Crucially, the map and reduce steps here operate on *structured findings*, not prose, which makes dedup and provenance tractable.

**5.2 Schema design for the synopsis.** The synopsis is machine-readable first. A finding object should carry: stable `id`; `type` (`ux_issue` | `arch_fact` | `interaction_pattern` | `risk` | `undetermined`); `mode` (`reconstruction` | `review`); `severity` (0–4 for UX; risk tier for arch); `heuristic`/`category`; `summary` (one line); `evidence_refs` (array of evidence IDs — marks, network/metric/stack fact IDs); `confidence`; `recommendation`; and optional `diff_status` (`new` | `changed` | `resolved` vs. prior run). Top-level: run metadata, the target (foreign/own), and an array of findings plus a rolled-up severity histogram.

**5.3 Deduplication.** The same issue often surfaces across sections (e.g., a slow API showing up in perf metrics, network facts, and a UX wait). Dedup by clustering on `(type, evidence_refs overlap, normalized summary)`; merge into one finding that retains the union of evidence refs and the max severity. A simple deterministic overlap check on evidence IDs is more reliable than LLM-judging similarity, and is model-free.

**5.4 Provenance.** Every synopsis finding must link back to evidence IDs that resolve, via a tool, to the actual screenshot crop, network record, or metric. This is the property that lets a downstream creation/modification agent *act* on a finding and verify it, and it is what makes the whole pipeline auditable (decompose-then-verify works only if claims point at sources).

**5.5 Two renderings from one source.** Emit the synopsis as machine-readable JSON (the SSOT, consumed by downstream agents) and render a human-readable Markdown view from it (never hand-author the Markdown — derive it). This preserves SSOT and progressive disclosure: humans skim the Markdown; agents consume the JSON.

### Recommended evidence-bundle spec (Deliverable i)

```
EvidenceBundle
├── role/system block            # who the model is, the cite-or-abstain contract
├── images (ordered first)
│   ├── full_screenshot[mark_id…]   # SoM marks overlaid; always included
│   └── crops[mark_id]              # only where detail < resolution cap
├── facts (keyed to mark_id / fact_id)
│   ├── journey_trace[step→mark_id]
│   ├── network_api_facts[fact_id]
│   ├── stack_facts[fact_id, confidence]
│   └── a11y_perf_metrics[metric_id]
└── task instruction (last)
```
Token budget computed deterministically before the call via `Σ (w×h/750)` per image against the model's cap.

### Recommended structured-output schema approach (Deliverable i)

Define Pydantic models as the SSOT (auto-derive JSON Schema), bind them to Anthropic JSON outputs / strict tool use (or OpenAI `response_format`), and validate on return. Every `Finding` separates `evidence_refs` (citations into the deterministic store) from `judgment` (model text), carries a `confidence`, and permits `type = "undetermined"` as a legal abstention.

## Recommendations

**Stage 0 — Lock the schemas (SSOT) and the deterministic core.** Define Pydantic models for: `Evidence` (mark, network fact, stack fact, metric — each with a stable ID), `Finding`, `Blueprint`, `Synopsis`. Implement the fact-producing tools as pure functions with these I/O types and 100% deterministic tests. *Benchmark to proceed:* every fact field is produced by code, never by a model; tools pass golden-file tests with no network/model calls.

**Stage 1 — Build the evidence-bundle assembler (Operator).** Deterministic code that: orders images-before-facts; applies the `w×h/750` token budget; decides full vs. crop using the resolution caps; emits a bundle that references mark IDs. *Threshold to add crops:* any region whose text would be sub-readable after downsampling to 1568 px (standard) / 2576 px (Opus 4.7/4.8) long edge.

**Stage 2 — Write three skills (Operator, UX-Analyst, Arch-Analyst).** Each `SKILL.md`: trigger-rich description; explicit tool-call sequence; the Part-3 prompt patterns; mandatory cite-every-claim, abstain-when-unsupported, emit-schema-valid-JSON. Use Claude Code structured outputs (strict tool use + JSON outputs) bound to the Pydantic schemas. *Benchmark:* with-skill vs. without-skill eval shows higher grounded-claim fraction and lower unsupported-claim rate.

**Stage 3 — Add the reliability passes.** Cite-the-evidence (reject any finding lacking resolvable `evidence_refs`), abstention as a schema-legal value, and a factored Chain-of-Verification pass that re-checks high-severity findings against the deterministic store. Add an NLI/RAGAS-style faithfulness score gate. *Threshold to ship a finding:* it cites resolvable evidence, passes entailment against that evidence, and clears the confidence floor — else it is downgraded to `undetermined`.

**Stage 4 — Synopsis map-reduce.** Implement structured map-reduce with deterministic dedup on evidence-ref overlap and provenance preservation; render Markdown from the JSON. *Benchmark:* every synopsis finding resolves to at least one evidence artifact; no duplicate findings survive dedup.

**Stage 5 (optional, gated) — Productize in-package agents.** Only if you need parallel breadth or a self-contained deployable. Convert skills → thin agent definitions; add a pure-coordinator orchestrator; route Opus for orchestration/arch, Sonnet/Haiku for workers. *Trigger to do this:* single-host throughput or deployment isolation becomes the bottleneck, and the ~15× token cost of fan-out is justified by parallel value. *What must not change:* the tool library, schemas, prompt templates, and synopsis logic are reused verbatim.

**Cross-cutting:** keep temperature low for analysis; keep the model out of unit tests; treat structured-output schema compliance as necessary-but-not-sufficient (it guarantees shape, not truth); and audit any third-party skills before use — Snyk Labs' "ToxicSkills" audit (Feb 5, 2026) found 36.82% of scanned skills (1,467 of 3,984) had at least one security flaw, 534 critical-severity, and 76 carrying confirmed malicious payloads.

## Caveats

- **Schema compliance ≠ correctness.** Constrained decoding guarantees the JSON shape; the values can still be wrong. Citation + verification + abstention are what address truth.
- **Fingerprint-based stack facts are probabilistic.** Wappalyzer-style detection carries confidence and can false-positive (e.g., reporting jQuery on a migrated site) or miss obfuscated/backend tech. Propagate confidence; never present a detected technology as certain.
- **Severity ratings from a single pass are noisy.** The HCI evidence is that single-evaluator severity is unreliable; consider multiple sampled passes or a verification pass and state uncertainty in the output.
- **Vision models still err on small/dense images.** Anthropic notes possible hallucination on low-quality, rotated, or sub-200px images; the crop tool and dedicated OCR for hard numeric extraction mitigate this. Use the vision model for the semantic layer and route precise extraction to deterministic tooling where it matters.
- **Multi-agent is not free.** The 90.2% uplift figure is from Anthropic's internal research eval and comes at ~15× tokens; it does not automatically transfer to this analysis task, which is more interdependent than breadth-first research. Treat in-package agents as an optimization, not a default.
- **Some cited figures are model- and date-specific** (token caps, pricing, model names like Opus 4.7/4.8, structured-output GA status, per-image file-size limits — 10 MB via the direct API vs. 5 MB on Bedrock/Vertex). Re-verify against current Anthropic/OpenAI docs at implementation time, as these evolve quickly.
- **Forward-looking items flagged:** "dynamic workflows" and "agent teams" in Claude Code are described by Anthropic as research preview; do not build hard dependencies on preview features.

## References

[1] Anthropic. *Equipping agents for the real world with Agent Skills.* [anthropic.com](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
[2] Anthropic. *Agent Skills overview.* Claude API Docs. [platform.claude.com](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
[3] Agent Skills. *Overview / open standard.* [agentskills.io](https://agentskills.io/home)
[4] Anthropic. *Vision.* Claude API Docs. [platform.claude.com](https://platform.claude.com/docs/en/build-with-claude/vision)
[5] Anthropic. *Giving Claude a crop tool for better image analysis* (cookbook). [github.com](https://github.com/anthropics/claude-cookbooks/blob/main/multimodal/crop_tool.ipynb)
[6] Yang J., Zhang H., Li F., Zou X., Li C., Gao J. *Set-of-Mark Prompting Unleashes Extraordinary Visual Grounding in GPT-4V.* arXiv:2310.11441. [arxiv.org](https://arxiv.org/pdf/2310.11441)
[7] Anthropic. *Structured outputs.* Claude API Docs. [platform.claude.com](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
[8] OpenAI. *Introducing Structured Outputs in the API.* [openai.com](https://openai.com/index/introducing-structured-outputs-in-the-api/)
[9] Dhuliawala S., Komeili M., Xu J., Raileanu R., Li X., Celikyilmaz A., Weston J. *Chain-of-Verification Reduces Hallucination in Large Language Models.* arXiv:2309.11495. [arxiv.org](https://arxiv.org/pdf/2309.11495)
[10] Zeng et al. *Cite Before You Speak: Enhancing Context-Response Grounding in E-commerce Conversational LLM-Agents.* arXiv:2503.04830. [arxiv.org](https://arxiv.org/pdf/2503.04830)
[11] Huang L. et al. *Learning Fine-Grained Grounded Citations for Attributed Large Language Models (FRONT).* arXiv:2408.04568. [arxiv.org](https://arxiv.org/pdf/2408.04568)
[12] Tomani C., Chaudhuri K., Evtimov I., Cremers D., Ibrahim M. *Uncertainty-Based Abstention in LLMs Improves Safety and Reduces Hallucinations.* arXiv:2404.10960. [arxiv.org](https://arxiv.org/pdf/2404.10960)
[13] Nielsen J. *Severity Ratings for Usability Problems.* Nielsen Norman Group. [nngroup.com](https://www.nngroup.com/articles/how-to-rate-the-severity-of-usability-problems/)
[14] Nielsen J. *Reliability of severity estimates for usability problems found by heuristic evaluation* (CHI'92). ACM. [dl.acm.org](https://dl.acm.org/doi/10.1145/1125021.1125117)
[15] Anthropic. *How we built our multi-agent research system.* [anthropic.com](https://www.anthropic.com/engineering/multi-agent-research-system)
[16] Anthropic. *Effective context engineering for AI agents.* [anthropic.com](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
[17] Anthropic. *Writing effective tools for AI agents.* [anthropic.com](https://www.anthropic.com/engineering/writing-tools-for-agents)
[18] Model Context Protocol. *Tools (server specification).* [modelcontextprotocol.io](https://modelcontextprotocol.io/specification/draft/server/tools)
[19] Kim Y. et al. *Context-Aware Hierarchical Merging for Long Document Summarization.* arXiv:2502.00977. [arxiv.org](https://arxiv.org/pdf/2502.00977)
[20] Google Cloud. *Summarization techniques: iterative refinement and map-reduce for document workflows.* [cloud.google.com](https://cloud.google.com/blog/products/ai-machine-learning/long-document-summarization-with-workflows-and-gemini-models)
[21] Anthropic. *Building Effective AI Agents.* [anthropic.com](https://www.anthropic.com/research/building-effective-agents)
[22] Hugging Face. *Harness, Scaffold, and the AI Agent Terms Worth Getting Right.* [huggingface.co](https://huggingface.co/blog/agent-glossary)
[23] Anthropic / Claude Code. *Get structured output from agents (Agent SDK).* [platform.claude.com](https://platform.claude.com/docs/en/agent-sdk/structured-outputs)
[24] Set-of-Mark follow-up: Yan A. et al. *List Items One by One: A New Data Source and Learning Paradigm for Multimodal LLMs.* arXiv:2404.16375. [arxiv.org](https://arxiv.org/pdf/2404.16375)
[25] Wappalyzer fingerprinting (detection signals reference). [github.com](https://github.com/tomnomnom/wappalyzer)
[26] Snyk Labs. *ToxicSkills: malicious AI agent skills audit* (Feb 5, 2026). [snyk.io](https://snyk.io/blog/)
[27] OpenAI. *Structured model outputs guide (Pydantic/Zod, function calling).* [developers.openai.com](https://developers.openai.com/api/docs/guides/structured-outputs)

*Note on figures marked "approximately/≈": all token counts in Anthropic's vision docs are explicitly labeled approximate; per-image dollar costs are tied to specific quoted per-token prices ($3/M for Sonnet 4.6; $5/M for Opus 4.7/4.8) and should be recomputed for the model you deploy.*