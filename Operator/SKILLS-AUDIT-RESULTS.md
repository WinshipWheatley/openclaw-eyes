# OpenClaw Skills Audit — results (2026-06-29, grounded/no-snowglobe)

# OpenClaw Skills Audit — Results

Grounded map of the brain layer, existing skill infrastructure, the skill catalog the fleet needs, capability-fabric readiness, and the #1 vertical slice. Labels are preserved as found — a STUB stays a STUB, an UNWIRED stays UNWIRED. No upgrades.

Scope: the 33 `*_brain.py` at `/home/openclaw` repo root are the only runtime brains. The two other copies (`generated/external_sources/openclaw-eyes/*_brain.py`, `openclaw_arko_review/*_brain.py`) are confirmed stale, non-runtime, imported by nothing.

---

## 1. Brain inventory

Dispatch spine: `chief_router.route_message` (chief_router.py:1351) — a ~40-intent keyword if/elif ladder — is called by both `chief_listener.py` and `cassandra_listener.py`. Front-door answers go through `maestro_cassandra_responder.protected_generate`.

| Brain | Purpose | WIRED? / authority | Call |
|---|---|---|---|
| cassandra_brain.py | Relational/executive brain; live persona brain | WIRED-LIVE (router + responder, `protected_generate`); read/draft, sends gated | KEEP-AS-BRAIN — already the protected_generate persona boundary; do not re-wrap |
| chief_approval_brain.py | Universal SEND/permission GATE | WIRED-LIVE; **GATE** authority | KEEP-AS-BRAIN — pure deterministic authority state machine; every skill routes sends through it |
| chief_backup_brain.py | git status/add/commit/push | WIRED-LIVE; **writes git (push)** | KEEP-AS-BRAIN — subprocess tool, no LLM |
| chief_scheduler_brain.py | Time-block timers + Telegram notify | WIRED-LIVE; writes state, notifies | KEEP-AS-BRAIN — timer/threads, deterministic |
| chief_ops_brain.py | Ops intake / save_deferred | WIRED-LIVE; writes ops log | KEEP-AS-BRAIN — intake/persist, deterministic |
| chief_watcher_brain.py | 900s daemon watching billing + replaying stuck approvals | WIRED-LIVE (daemon); sends replies/replays | KEEP-AS-BRAIN — monitor daemon, deterministic |
| chief_album_brain.py | Album session state machine (CSV/MD vault) | WIRED-LIVE; writes vault session | KEEP-AS-BRAIN (engine) — state+ledger writes stay deterministic; fill-prompts could be a thin skill |
| chief_billing_brain.py | Invoice/payment intake Q&A + tracker | WIRED-LIVE; writes billing tracker | KEEP-AS-BRAIN — flow+write deterministic; 1 prefill `ollama_call` is optional sugar |
| chief_invoice_brain.py | (superseded) | **RETIRED tombstone** (RETIRED=True, handle() fails closed) | LEAVE DEAD — superseded by billing_brain + invoice_send_executor + chief_compose |
| chief_cpa_brain.py | Tax/income/expense log + summary | WIRED-LIVE; read/compute, cloud-gated (`external_model_packet_policy`) | SPLIT — parse half = MAKE-SKILL (extraction); **tax math + log writes stay deterministic** |
| chief_email_brain.py | Draft/parse/send email | WIRED-LIVE; DRAFT-only, send Guardian-gated | SPLIT — draft body = MAKE-SKILL; send via approval gate stays a tool |
| chief_sms_brain.py | Draft/parse/send SMS | WIRED-LIVE; DRAFT-only, gated | SPLIT — draft = MAKE-SKILL; send gated tool |
| chief_phone_brain.py | Call-log parse + call script | WIRED-LIVE; writes call log | SPLIT — log-parse + script = MAKE-SKILL; log write deterministic |
| chief_calendar_brain.py | Fetch events (broker) + narrate | WIRED-LIVE; read | SPLIT — fetch stays a tool; weekly summary = MAKE-SKILL (narrate) |
| chief_financial_brain.py | Financial compute + narrative | WIRED-LIVE; read | SPLIT — compute = tool; narrative = MAKE-SKILL (narrate) |
| chief_analytics_brain.py | Analytics compute + narrate | WIRED-LIVE; read | SPLIT — aggregation = tool; narrate = MAKE-SKILL |
| chief_reporter_brain.py | Evidence synthesis narrative | WIRED-LIVE; read | MAKE-SKILL (narrate) over deterministic gather |
| chief_reflection_brain.py | Reflection compute + narrate | WIRED-LIVE; read | MAKE-SKILL (narrate) over deterministic compute |
| chief_momentum_brain.py | Momentum compute + narrate | WIRED-LIVE; read | MAKE-SKILL (narrate) over deterministic compute |
| chief_trinity_brain.py | System/brain audit + gap proposals | WIRED-LIVE; read/propose | MAKE-SKILL (narrate audit) over deterministic gather |
| chief_goals_brain.py | Goals read/update | WIRED-LIVE; read/update goals | MAKE-SKILL (narrate/draft); persist deterministic |
| chief_marketing_brain.py | Marketing idea/caption/hook generate | WIRED-LIVE; draft + log | MAKE-SKILL (generate); log stays a tool |
| chief_content_brain.py | Content-cal drafting | WIRED-LIVE; read/update | MAKE-SKILL (generate) |
| chief_brand_brain.py | Brand voice advisory | WIRED-LIVE; read/advisory | MAKE-SKILL (generate) |
| chief_musiclaw_brain.py | Music-law advisory + safety wrapper | WIRED-LIVE; advisory draft | MAKE-SKILL (generate) — keep `_ensure_musiclaw_safety` as the guard |
| chief_publishing_brain.py | Publishing catalog read/update | WIRED-LIVE; read/update catalog | SPLIT — extract = skill; catalog write deterministic |
| chief_brainstorm_brain.py | Idea generation (nemotron, cloud-gated) | WIRED-LIVE; writes ideas, cloud-gated | MAKE-SKILL (generate); keep `external_model_packet_policy` in front |
| chief_scout_brain.py | Findings synthesis | WIRED-LIVE; read | MAKE-SKILL (generate/synthesize) |
| chief_queue_brain.py | Writes feature queue | WIRED-LIVE; writes feature queue | MAKE-SKILL (generate); queue write deterministic |
| chief_integration_brain.py | Integration proposals (PROP-) | WIRED-LIVE; propose | SPLIT — proposal half = MAKE-SKILL; approve/reject stays a tool |
| cassandra_briefing_brain.py | Morning briefing narrative | WIRED-LIVE (scheduler/cron); read/brief | MAKE-SKILL (narrate) over deterministic fetch |
| chief_validator_brain.py | Output-guard middleware (soften severity) | WIRED-LIVE (listener middleware); output middleware | KEEP-AS-BRAIN (lean) — severity/length CHECKS stay deterministic (SEVERITY_KEYWORD_VARIANTS); only optional rewrite is skill-worthy |
| data_room_live_lm_brain.py | Codex/LM2 advisory adapter for Data Room | WIRED-LIVE; **advisory only, NO tool authority** (authoritative=False) | KEEP-AS-BRAIN — already the correct LM-skill boundary; do not re-wrap |

Net: ~8 brains are correctly deterministic tools (KEEP). ~20 are LLM procedures (each owning a private prompt = drift surface) that should consolidate behind a small set of skills — `narrate(data, persona)` for the report family, `draft` for the generate family, `extract` for the parse family — reusing the existing gate, context, and data-fetch tools.

Biggest live brain-routing gap: `chief_router` is a 1369-line hand-maintained ladder; its LLM fallback classifier covers only 9 of ~40 intents (chief_router.py:683). Anything generative that misses a keyword drops to `_chief_fallback_reply` on **qwen3.6:latest (23GB)** (chief_router.py:1342), which per the known recitation root-cause times out on the ~16GB box → deterministic recitation. Confirm/fix this model before any skill migration; it is where un-keyworded generative asks land.

---

## 2. Existing skill infra

The machinery exists; the runtime consumer does not. "Machinery present, consumer absent."

| Component | Status | What it is |
|---|---|---|
| `skill_loader.py` + `skill_vetter.py` | **STUB** (maintainer/CI-only) | Real, tested SKILL.md YAML-frontmatter parser + vetter. Only consumer is `scripts/check_skill_metadata.py` (a CI preflight validating the **Codex plugin cache** `.codex/plugins/cache`) + tests. No agent-runtime importer. |
| `capability_skill_registry_metadata_delta.py` | **STUB / metadata-only** | SCHEMA `capability_skill_registry_metadata_delta_v0`; 14 hardcoded CapabilitySpec records = capability CLASSIFICATION + gate metadata, not invocable skills. All NO_AUTHORITY_FLAGS False; activation/execution_allowed_now=False. Emits read-models only. UNWIRED to runtime. |
| `agent_package` spine (`agent_package_preview_contract.py`, `operator_awareness_agent_package_spine.py`, `tool_protocol_adapter_registry_contract.py`) | **STUB / aspirational** | Docstrings: "deterministic read-model metadata only … does not activate tools/agents/models/runtime." Define the inspectable "package" shape; export-only. |
| `maestro_context_packet.py` (live packet builder) | — | **ZERO** skill/capability references (grep empty). `polish_loop/task_routing.py` also zero. The runtime packet ships **no skills today**. |
| skill-creator (vendored) | **REFERENCE ONLY** | Defines the standard format (`skill-name/SKILL.md`, YAML name+description, body, optional `scripts/`/`references/`/`assets/`). Present under npm `openclaw` pkg and `.claude/plugins`. |
| NemoClaw | — | CONFIRMED a guardrails/sandbox WRAPPER, not a skills platform. Nothing in runtime imports it. |
| Claude Code `.claude/commands/*.md` (cassandra/chief/guardian/hermes/niles/ops-intake) | — | Maintainer-side guides for the human's Claude Code/Codex session. Explicitly "not runtime code, not a policy source, not an authority grant." OpenClaw agents never read these. |
| `system_catalog.sqlite3` | — | Tables `scans` (1 row) + `repos` (134). **No skills table.** |
| Corpus on disk | — | `sidecars/hermes/skills/*` (large Anthropic-format library), `.codex/vendor_imports/skills/.curated/*`, `.codex/skills/feynman/*`, `.codex/plugins/cache/openai-curated*` — ready format, **none wired**. |

Precise gap to a runtime skill system:
- **GAP A — Runtime skill STORE/REGISTRY** (deterministic, Chief-owned): no table of `(skill_id, path, name, description, scope, required_gate)`. Recommend a `skills` table in `system_catalog.sqlite3` (extend the scan, one truth store), populated by `skill_loader.load_skills()`.
- **GAP B — Runtime CONSUMER / injection point** (biggest gap): `maestro_context_packet.py` must select + inject matching skill content per request. Owner: Cassandra/Chief packet builder + responder. The selection step is an LLM step gated behind `protected_generate`, on the local ladder (mirror interpreter_lm).
- **GAP C — Skill ROUTER (per-agent scope)**: owner `agent_lane_registry.py`; mostly deterministic scope table + the GAP-B selection.
- **GAP D — Skill EXECUTOR for skills carrying `scripts/`**: Guardian-gated factory dispatch into a sandbox (NemoClaw/OpenShell or polish_loop factory isolation); billing/safety gated, default-canary.
- **GAP E — Activation posture**: read-only selection/injection can be default-ON behind a canary; anything that EXECUTES crosses the Guardian/execution gate + activation record.
- **GAP F — Authoring**: skill-creator exists but is maintainer-side; decide author-vs-consume.

Caveat: grep of the tracked tree shows no runtime consumer, but core responder/processor (`maestro_cassandra_responder`, `openclaw_request_processor`) are gitignored — a direct Read of those would fully confirm "no hidden skill consumer."

---

## 3. Ranked skill catalog

Candidate skills the fleet needs. `id | owner (agent_lane_registry lane) | tier | EXISTS/PARTIAL/GAP | value | collision`. The "procedure bodies" already exist as ~28 live `chief_*_brain.py` + `cassandra_brain`; the missing piece is a tiered, router-orchestrated skill layer over them. Items colliding with Codex's current E/F (vision/finance) work are excluded from #1.

| Rank | id | Owner lane | Tier | Status | Value | Collision |
|---|---|---|---|---|---|---|
| 1 | check_to_books_reconcile | Cassandra (operator_comms/finance) | rich | PARTIAL (payment-verify LIVE; G2C UNWIRED) | 10 | **COLLIDES — Codex F (`check_evidence_books_bridge.py`). EXCLUDE** |
| 2 | vision_ocr_intake (photo→fields) | Cassandra | rich/simple | GAP (Tesseract siloed in legal_process) | 10 | **COLLIDES — Codex E (PHOTO handler + chief_llm vision). EXCLUDE** |
| 3 | invoice_followup_plan (AR chase) | Cassandra | rich | PARTIAL (billing LIVE; AR-plan reasoning absent) | 9 | partial (billing/G2C path Codex F). DEFER |
| 4 | weekly_briefing_synthesis | Cassandra | rich | PARTIAL (briefing scheduler + calendar LIVE) | 9 | soft (Bug B: calendar/briefing must stay deterministic + fail-closed). DEFER |
| 5 | schedule_qa ("what's on my schedule") | Chief/Cassandra | simple→rich | PARTIAL (calendar; live broker reply-routing gap) | 8 | constrained (Bug B). DEFER |
| 6 | email_draft | Cassandra | rich | PARTIAL (`_draft_email` LIVE; send gated) | 8 | partial (send/Gmail loopback). DEFER |
| **7** | **music_law_advisory** | **Chief (musiclaw) surfaced via Maestro/Niles music_art** | **rich** | **EXISTS (WIRED-LIVE, LLM+safety wrapper)** | **8** | **NO COLLISION — #1 PICK** |
| 8 | marketing_content_draft | Chief (marketing/content/brand) surfaced via Cassandra | rich | EXISTS (WIRED-LIVE) | 7 | NO collision. Runner-up |
| 9 | expense_capture ("I spent $X on Y") | Cassandra (cpa) | simple | EXISTS (`log_expense_from_text` LIVE) | 7 | partial finance; better kept DETERMINISTIC |
| 10 | operator_status_capability_readback | Maestro (operator_frontdoor) | simple→rich | EXISTS (`build_truthful_status_capability_answer`) | 7 | **COLLIDES — Codex Bug B. EXCLUDE** |
| 11 | fleet_systems_qa | Hermes (advisory_synthesis) | rich | PARTIAL (`observe_fleet` exists; inbound chat being wired) | 6 | soft (Codex C + Hermes addendum). DEFER |
| 12 | legal_review_triage | Cassandra/Guardian (legal bridge) | rich | PARTIAL (legal_process + bridge Phase-0) | 6 | no collision; separate heavy program. DEFER |
| 13 | deep_research_synthesis | Hermes | rich | PARTIAL (Claude-harness skill; no runtime skill) | 5 | no collision; lower operator-value |

Gap summary: the highest-value procedures (1, 2, 3) are exactly what Codex owns right now. The highest-value NON-colliding ones with a live brain to wrap are **#7 music_law_advisory** and **#8 marketing_content_draft**.

---

## 4. Capability-fabric readiness

| Component | Label | State |
|---|---|---|
| Decomposer — **planner** | **STUB-IN-PRODUCTION** | `model_aware_decomposer.py` `plan_for_request` (L233): derives ModelProfile from the live router (`model_router_policy.select_model_class`), returns a Plan of scoped Steps. Produces series (deps=prev) AND parallel (deps=()); `Plan.waves()` (L159) topo-groups into execution waves. Optional injected `generate_fn` LLM-refines, falls to deterministic `split_steps` on any failure. Built + tested, **UNWIRED from every live agent path**. |
| Decomposer — **step-executor** | **STUB-IN-PRODUCTION** | `step_executor.py` `execute_plan` (L74) walks `plan.waves()`, skips dep-failed steps, threads prior outputs; `run_request` (L111) = decompose+execute; `_default_local_generate` (L52) hard-codes qwen3:8b-q4_K_M. Memory note "executor is the remaining wiring" is **STALE** — it IS built and tested. Real gap: only importers are the two modules + their tests; **no responder/processor/listener/brain imports it.** |
| Model ladder | **WIRED-LIVE** (class ladder) / **STUB** (resource gating) | `select_model_class` (model_router_policy.py:248) WIRED-LIVE with fail-closed-to-local ladder (NO_SAFE_MODEL / LOCAL_ONLY / LOCAL_FALLBACK). `select_frontdoor_model` (chief_llm.py:750) WIRED-LIVE, picks largest allowlisted model within budget; allowlist = qwen3.5:4b, qwen3:8b-q4_K_M, qwen3.5:9b; gemma4:26b/31b HARD-DENIED. **Resource gating is a STUB**: `available_ram_gb` defaults to None → budget collapses to a static 12GB constant; the live caller (protected_generate.py:1136) passes only `max_gb`, never `available_ram_gb` → **no live RAM/VRAM gating today.** `_LANE_CANDIDATES` (chief_llm.py:123) is partly STALE (references absent qwen2.5-coder:14b + timeout-prone gemma4:26b/31b). |
| Local models + capacity-probe | **WORKING but UNWIRED to selection** | 14 local models. 6GB-VRAM fit: qwen3:4b 2.5G, nemotron-3-nano:4b 2.8G, qwen3.5:4b 3.4G, qwen3:8b-q4 5.2G, ornith:9b 5.6G, qwen3.5:9b 6.6G; CPU-spill: gemma4:26b 17G, qwen3.6 23G. Probes all read-only + working, **none feed the router**: `ollama ps`/`api/ps` size_vram (used only by chief_chat.py:71 `/vram`); nvidia-smi via `/usr/lib/wsl/lib/nvidia-smi` → 5164/6144 MiB free (used by monitoring, not router); `/proc/meminfo` MemAvailable ≈20GB (no runtime reads it). |
| Deferred / honest-defer queue | **ABSENT / MISMATCH** | The prompt's "operator_file_metadata_intake pending markers" don't exist as a queue — that module is a privacy intake gate (extraction/readback statuses), not a reprocess queue. `dropped_intent_registry.py` = WIRED durable RECORD of unresolved/deferred directions (not an auto-requeue engine). `chief_dynamic_workflow_deferred_build.py` = **STUB/aspirational** (one hardcoded `DEFERRED_WAITING_FOR_CODEX_5_5_CAPACITY` packet, exact honest-defer-on-capacity shape, no queue). `polish_loop` control-plane + lane ledger = the real task queue/engine. |

Exact wiring the router/scheduler still needs:
- **(A) Live-capacity feed** — a tiny non-model probe (nvidia-smi `--query-gpu=memory.free` + `/proc/meminfo` MemAvailable + `api/ps` size_vram) PASSED as `available_ram_gb` (and a new `available_vram_gb`) into `select_frontdoor_model`; today the "resource-aware" budget is a dead 12GB constant. Deterministic, fail-open.
- **(B) Wire decomposer+executor into a live path** — the seam already emits the signal: `polish_loop/task_routing.py:193` sets `decomposition_required` for size_class in {large, architect} and `:305` returns `holding` with `{size}_requires_decomposition`, but **nothing calls** `plan_for_request`. Connect holding → `plan_for_request` → `step_executor.execute_plan`.
- **(C) Resource-aware serial/parallel gate** — `Plan.waves()` declares which steps CAN run in parallel; the scheduler must decide whether to actually run a wave in parallel (sum of model sizes in wave vs free VRAM; collapse to serial when models won't co-resident-fit on 6GB). No such gate exists. Reuse `polish_loop/lane_launcher.py max_parallel_lanes` shape but add the VRAM/RAM dimension (it is lane-count + gate-lock aware, not memory-aware).
- **(D) Prune stale lane candidates** — validate `_LANE_CANDIDATES` against live `ollama list`/`api/tags` before dispatch (drop absent qwen2.5-coder:14b + timeout-prone gemma4:26b/31b).
- **(E) Honest-defer queue** — generalize `chief_dynamic_workflow_deferred_build`'s static `why_deferred` into a real defer record keyed off `select_model_class` NO_SAFE_MODEL / `select_frontdoor_model` no-fitting-model (live trigger: protected_generate.py:1139 `route='deterministic_fallback_no_fitting_model'`), persisted via the `dropped_intent_registry` durable-row shape instead of silently reciting.

Rule: the scheduler/router decides WHICH model + serial-or-parallel deterministically from live numbers; the LLM only decides HOW to phrase/split the work, never whether there is capacity to run it. Keep the deterministic `split_steps` fallback so a model timeout never blocks.

---

## 5. #1 vertical-slice recommendation

**Build `music_law_advisory` (catalog #7) first.**

Why it is the best first skill:
- **High operator value** — Winship is a working music artist; splits, sync, sample-clearance, and publishing questions recur and genuinely need multi-step reasoning + a knowledge tier.
- **Self-contained** — pure knowledge + reasoning, zero side effects: no money, send, ledger, calendar, or vision I/O.
- **Wire-not-rebuild** — `chief_musiclaw_brain.py` already exists WIRED-LIVE (chief_router:77,987) with a local `ollama_call` (`_ask_llm` 200), embedded `MUSIC_LAW_KNOWLEDGE` + `TEN_FINGERS_CASE`, a built-in safety wrapper (`_ensure_musiclaw_safety` 183, appends "not legal advice / consult an entertainment lawyer") and a fail-closed fallback. It is the perfect demonstrator that authority/safety never travels with the skill.
- **Exercises the full router cleanly** — match → cheapest-sufficient local model → DECOMPOSE a question the front-door 8b can't answer whole (identify legal area → enumerate options → apply safety framing → assemble) → honest-defer on local timeout. It proves all three acceptance gates (decompose-completes, serial-resource-aware, honest-defer) on a $0 local path.

Why it does NOT collide with Codex's E/F finance/vision work: Codex (CODEX-MAESTRO-BRAIN-ROUTING-FIX) is editing `maestro_cassandra_responder` + `openclaw_request_processor` (A/B), `sidecars/hermes` gateway (C), `no_response_watchdog` (D), the listeners + `chief_llm` vision (E), and `check_evidence_books_bridge` + G2C + `cassandra_brain` payment (F). `chief_musiclaw_brain.py` and the music_art world are touched by **none** of those files/paths. Finance ledger, check images, vision/OCR, calendar, send, and the status-readback path are all untouched by a music-law skill — so the registry + router + decomposer machinery can be built in parallel against a safe slice while Codex finishes F.

Thin end-to-end proof:
1. A real music-law question arrives at the front door (e.g., a sample-clearance / split scenario the 8b can't answer whole).
2. The skill matcher (deterministic description prefilter → small-model selection step, gated behind `protected_generate`) selects `music_law_advisory` and attaches the `chief_musiclaw_brain` knowledge tier into the packet.
3. `model_aware_decomposer.plan_for_request` splits it (area → options → safety framing → assemble); `step_executor.execute_plan` runs the waves on a 6GB-fit local model (qwen3:8b-q4_K_M / qwen3.5:9b), **not** gemma4:26b/qwen3.6:23b.
4. `_ensure_musiclaw_safety` wraps the assembled answer (proves safety lives in the tool, not the skill).
5. On local timeout, it honest-defers (records, not recites) instead of dropping to the 23GB fallback.

Owner note: `chief_musiclaw_brain` lives under `chief_` but the music_art world is Niles' lane — surface it via the **Maestro front-door** (which answers, calling the brain) without minting a new lane/agent. Runner-up if music-law proves awkward: `marketing_content_draft` (#8, also non-colliding, also a live brain) — but music-law is the sharper "small model can't do the whole thing" + cleaner safety-boundary demo.

---

## 6. Honest gaps / risks

What is NOT there:
- **No runtime skill consumer at all.** The live packet builder `maestro_context_packet.py` has zero skill/capability references. Nothing in the agent runtime loads, selects, or executes a skill today. (One caveat: the gitignored `maestro_cassandra_responder` / `openclaw_request_processor` should be Read directly to fully rule out a hidden consumer.)
- **No runtime skill STORE/REGISTRY** holding `(skill_id, path, name, description, scope, required_gate)`. Only the `capability_skill_registry_metadata_delta` read-model (metadata/classification, no invocable skills) and the legacy `capability_registry.py` (Actor/Capability lookup, "reference evidence not authority"). `system_catalog.sqlite3` has no skills table.
- **No live resource-aware gating.** `select_frontdoor_model`'s budget collapses to a static 12GB constant because the live caller never passes `available_ram_gb`. The capacity probes (nvidia-smi, MemAvailable, api/ps) all work but feed monitoring, not the router.
- **No honest-defer queue / live drainer.** Records exist (`dropped_intent_registry`); the reprocess engine does not. The honest-defer shape is a single hardcoded packet.

Only spec'd / STUB (do not present as live):
- The decomposer + step-executor are **built and unit-tested but UNWIRED** to any live request — STUB-IN-PRODUCTION.
- The agent_package spine, `capability_skill_registry_metadata_delta`, and the agent_package preview contracts are **read-models / export-only**, explicitly no-authority.
- `chief_dynamic_workflow_deferred_build.py` is aspirational (one static deferral).
- `chief_invoice_brain.py` is **RETIRED** — leave dead.
- The `.claude/commands/*.md` and skill-creator are **maintainer-side**, never runtime authority.

What should stay deterministic (do NOT LLM-ify):
- The skill ingestion/validation spine (`skill_loader`, `skill_vetter`), the skill store table, gate CLASSIFICATION (`capability_skill_registry_metadata_delta`), per-agent scope table, and packet assembly/budgeting.
- The capacity probe; `select_model_class` ladder + fail-closed-to-local; `select_frontdoor_model` largest-fitting math; `Plan.waves()` topo-order + the VRAM-fit serial/parallel collapse (arithmetic, not an LLM guess); candidate-vs-installed validation; honest-defer record writes.
- All ledger/authority ops: expense/income logging (exact-amount parse + `find_duplicate_today` idempotency), invoice send (Guardian-gated `invoice_send_executor`), calendar fetch (broker call), G2C store mutations (append-only), paid-marking + receivable lifecycle, and the status/capability data source. A wrong amount or a hallucinated "paid" is unacceptable.
- `chief_approval_brain` (universal gate), `chief_backup_brain` (git push), `chief_scheduler_brain`, `chief_ops_brain`, `chief_watcher_brain`. Authority always routes to Guardian regardless of skill tier.

Key risks / open items:
- **Model-fit is the live blocker.** Confirm whether qwen3.6:latest (23GB) is still the live `_chief_fallback_reply` model (chief_router.py:1342) — it times out on the ~16GB box and is where un-keyworded generative asks land (recitation root-cause). Rich tier on this box must route to qwen3:8b-q4_K_M / qwen3.5:9b, never gemma4:26b/qwen3.6:23b.
- **VRAM-vs-RAM budgeting ambiguity.** 6GB VRAM (forces serial for any >~5GB model) vs ~20GB RAM (allows slow CPU-spill). `select_frontdoor_model`'s headroom-4/12GB default implies a RAM budget, which over-promises GPU concurrency. Calibrate the serial/parallel estimator from `ollama ps` + `free` before enabling parallel.
- **Activation posture.** Read-only selection + injection can ship default-ON behind a canary; anything carrying `scripts/` that EXECUTES crosses the Guardian/execution gate and stays sandboxed (no postpaid/cloud, local-ladder fail-closed) with an activation record.
- **Skill creation must stay operator/Guardian-gated**, with a phantom-actor validator (the Fin lesson) so a skill can't claim an actor/authority it doesn't own.
- **Two stale brain duplicate trees** (`generated/external_sources/openclaw-eyes/`, `openclaw_arko_review/`) shadow the canonical 33 — confirmed not imported, but worth confirming they can't be accidentally picked up on `sys.path`.
