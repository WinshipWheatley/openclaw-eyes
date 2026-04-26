# OpenClaw Agent Boundary And Resource Audit

Date: 2026-04-26

Scope: audit-only pass over Chief, Cassandra, Guardian, Hermes, PI references, harness boundaries, and local LLM resource contention. This report does not change runtime behavior.

## Executive summary

- No critical issue was found that requires an immediate broad rewrite, but several high-risk boundary blurs are present.
- The strongest existing boundaries are the Guardian/approval gate, Google access broker policy, harness staging rules, deterministic reporter modules, and advisory-only task proposal store.
- The highest-risk blur is that some "brain" surfaces both evaluate and initiate action. Cassandra's public doctrine says it defers execution to Chief, but `cassandra_brain.py` currently creates tasks, queues future actions, creates/sends approval-gated email flows, and calls calendar/email broker actions.
- Chief routing also mixes routing, model calls, subprocess actions, background workers, file writes, and Telegram delivery in `chief_router.py` / `chief_listener.py`.
- Local model usage is decentralized. Many paths call Ollama directly or through `chief_llm.ollama_call()` with no shared queue, lock, priority budget, or clear starvation protection. A long local builder, Hermes annex, briefing stack, or 600 second Chief fallback can stall operator-facing work.
- Hermes has good sidecar doctrine in its own plans, but current dirty systemd/dashboard wiring can make it look closer to the canonical stack than intended. Hermes should remain non-canonical and non-blocking.
- No active PI planning authority implementation was found. Current `PII` references are privacy/data handling, not a Planning Intelligence agent. PI should remain future/reserved.

## Current intended architecture

- Chief is the operator-facing router, coordinator, and approval-facing execution authority.
- Cassandra is the personal assistant/context brain. Its own prompt boundary says it owns orientation, priorities, context, and relational continuity, while Chief handles routing, approvals, album, billing, task execution, and system commands.
- Guardian is an approval-only control surface and schema/policy validation concept. It is not a general assistant, planner, or executor.
- Hermes is a sidecar observer/annex generator. Existing Hermes plans say it is advisory, non-canonical, non-blocking, and must not govern, enqueue, deliver, or write canonical state.
- Harnesses validate evidence and schema without writing live state. The Guardian schema harness patches pending approval paths into staging and explicitly verifies live pending approval state is not written.
- Deterministic reporters and mirrors should parse, summarize, and write bounded artifacts without making policy decisions or consuming local LLM capacity.
- The Google access broker is the narrow policy gate for Google/Workspace operations. Unknown capability is denied by default; Cassandra has limited allowed capabilities; Chief remains denied for Google operations unless deliberately changed.
- The local LLM router should be policy, not scattered implementation detail. Model choice, fallback, timeout, and priority should converge in `chief_llm.py` or a small wrapper rather than being embedded in agent modules.

## Boundary blur findings

### High: Cassandra evaluates and initiates action in one brain surface

Evidence:

- `cassandra_brain.py:4-7` states Cassandra is not the router/executor and defers to Chief for approvals and execution.
- `cassandra_brain.py:1302-1330` reinforces that Chief handles execution and approval-gated actions.
- `cassandra_brain.py:462-486` logs conversations and queues debug tasks on error routes.
- `cassandra_brain.py:729-767` writes `polish_loop/tasks/cas-debug-*.md`.
- `cassandra_brain.py:2091-2153` detects future-action intent and queues requests through `future_action_queue.enqueue_request()`.
- `cassandra_brain.py:2376-2410` writes upgrade task files.
- `cassandra_brain.py:2936-3098` creates Gmail drafts and starts approval-gated send flows.
- `cassandra_brain.py:3254-3358` runs post-draft email send handling through `google_access_broker`.
- `cassandra_brain.py:3415-3505` handles calendar create/delete through the broker.
- `cassandra_brain.py:4217-4335` polls inbound Gmail replies and may draft/send replies after checks.
- `cassandra_brain.py:5269-5679` `handle()` performs many deterministic actions before the LLM reply path.

Finding:

Cassandra is not merely returning structured evaluation/proposals. It directly initiates several bounded but real side effects. Many are approval-gated or broker-gated, but the action initiation still lives inside the assistant brain.

Risk:

High. This creates authority ambiguity for future work: a developer may add more direct tool behavior to Cassandra because the pattern already exists.

Smallest Phase 2 direction:

Introduce a thin action-proposal boundary for one workflow at a time. Start with future-action or upgrade-task creation: Cassandra returns a structured proposal, and a Chief-owned or broker-owned executor writes/queues it.

### High: Chief router mixes routing, model work, subprocess action, file writes, and delivery

Evidence:

- `chief_router.py:816-851` uses `ollama_json()` to infer structured intent from natural language.
- `chief_router.py:1278-1296` starts `/home/openclaw/start_chief.sh` via `subprocess.Popen()` for stack restart intent.
- `chief_router.py:1461-1524` `_artifact_transform_worker()` calls a hardcoded local model, writes `inventory-normalized.md`, and sends Telegram notification.
- `chief_router.py:1558` `handle_inventory_summary()` hardcodes `gemma4:e4b`.
- `chief_router.py:1567-1584` `_chief_fallback_reply()` pulls context from `cassandra_brain.build_context_snapshot()` and hardcodes `qwen3.6:latest`.
- `chief_listener.py:104-120` runs `route_message()` in a thread.
- `chief_listener.py:136-156` directly invokes `/home/openclaw/chief-inspect` for inspection intent.

Finding:

Chief routing is both a classifier and an executor/worker host. Some paths hardcode models instead of using router policy. One fallback also depends on Cassandra context, which blurs Chief/Cassandra ownership.

Risk:

High. Routing changes can accidentally become execution changes, and model contention policy is bypassed.

Smallest Phase 2 direction:

Move one background worker path behind a small service function with an explicit contract. Keep Chief router as caller, but remove hardcoded model selection and side-effect details from the router.

### High: PC review fallback can fail open when the local model path is unavailable or ambiguous

Evidence:

- `polish_loop/pc_review_fallback.py:229-295` `_llm_code_review()` calls `ollama_call()` with a deep model.
- The same block treats unavailable, error, empty, and ambiguous responses as "pass/skip" instead of requiring evidence.

Finding:

This is a harness/evidence boundary risk. A model-backed review lane can silently degrade to pass.

Risk:

High. It can create false confidence in code review or patch acceptance when the model path is unavailable.

Smallest Phase 2 direction:

Change this lane to fail neutral or produce an explicit "review unavailable" artifact that cannot be interpreted as pass. Do this separately from broad boundary refactors.

### Medium: Agent outputs do not all pass through the same evidence validation surface

Evidence:

- `chief_listener.py:242-246`, `260-266`, `284-295`, `304-315`, `318-336`, `339-343`, and `406-417` call `validate_reply()` for selected intents.
- Other listener intents send replies without the same validation step, including ops intake, Cassandra delegation, artifact transform, inventory summary, backup/status/reporting, calendar query, scheduler, brainstorm, focus, choice response, mix brief, stack restart, HITL decision, and generic fallback paths.
- `docs/testing/HARNESS_INDEX.md` describes harnessed paths for Morning Brief, EOD, and Guardian schema.

Finding:

Validation exists, but it is not a universal output boundary. Some direct action or summary paths bypass the same reply validator.

Risk:

Medium. The biggest risk is inconsistent proof standards and accidental overclaiming in operator-facing messages.

Smallest Phase 2 direction:

Inventory Chief listener response paths and add a single helper that records whether each path is deterministic, validated, or exempt with a reason.

### Medium: Raw tool, log, and source parsing remains inside brain modules

Evidence:

- `cassandra_brain.py:1178-1297` `build_context_snapshot()` reads/parses finance reports, reality notes, vault ops, sentry gate, Chief CPA, album CSV, and route logs.
- `cassandra_briefing_brain.py:137-184` checks pending approvals and protected-window state directly.
- `docs/operations/DEPENDENCY_HYGIENE.md` says raw parsing and file reads should live in utility layers; brains should orchestrate and apply high-level judgment.
- `chief_ops_reporter.py:1-7` is a good deterministic counterexample: parsing/writing is isolated outside a brain.

Finding:

Some parsing has already been moved into deterministic reporters, but Cassandra and briefing brains still own raw file/tool context ingestion.

Risk:

Medium. It makes brain behavior harder to test and encourages action logic to grow around raw data reads.

Smallest Phase 2 direction:

Extract one read-only context collector from `cassandra_brain.build_context_snapshot()` without changing output shape.

### Medium: Capability truth is split across registry, flags, and policy

Evidence:

- `capability_registry.py:1-19` is the shared machine-readable registry to avoid guessing capabilities.
- `capability_registry.py:48-132` describes Cassandra capabilities and denied/unconnected surfaces.
- `capability_registry.py:134-205` describes Chief capabilities and denied surfaces.
- `cassandra_capability.py:1-27` defines two-stage capability gates and runtime reply gates.
- `cassandra_capability.py:34-45` contains separate boolean connection flags such as `FUTURE_ACTION_CONNECTED`, `FINANCIAL_LOG_CONNECTED`, `PII_VAULT_CONNECTED`, and `VOICE_NOTE_CONNECTED`.
- `google_access_policy.py:1-15` is a separate policy table for Google operations, denied by default.

Finding:

There are multiple capability surfaces with overlapping authority. The split is understandable but creates drift risk.

Risk:

Medium. An assistant can cite one surface while another blocks or permits behavior.

Smallest Phase 2 direction:

Add a read-only consistency check that compares registry claims, capability flags, and Google policy for known actors. Do not collapse the systems yet.

### Medium: Hermes sidecar doctrine is clear, but wiring can imply canonical influence

Evidence:

- `sidecars/hermes/.plans/hermes-morning-annex-plan.md:1-46` says Hermes is a final, non-blocking, non-canonical synthesis stage and must never block, delay, interfere, govern, enqueue, or write canonical state.
- `sidecars/hermes/.plans/hermes-loop-observer-role.md:1-46` says Hermes is advisory only and cannot write queue tasks directly.
- `sidecars/hermes/scripts/run_morning_annex.sh:1-77` writes only `Hermes Morning Annex.md`, prompts Hermes not to act/enqueue/deliver/govern, and exits 0.
- `dashboard_gen.py:1856-1884` triggers the Hermes morning annex after the Morning Brief mirror is written.
- Dirty `systemd/user/hermes-gateway.service.in` and dirty `systemd/user/openclaw-stack.target.in:12` indicate Hermes gateway/stack wiring is being introduced.

Finding:

Hermes is well-described as sidecar, but dashboard and systemd wiring can make it look like part of the canonical stack if not labeled and isolated carefully.

Risk:

Medium. Future work may treat Hermes outputs as canonical or give Hermes planning authority.

Smallest Phase 2 direction:

Keep Hermes outputs labeled "non-canonical sidecar". If a service remains in the stack, make non-blocking/failure-isolated behavior explicit in service docs and dashboard labels.

### Medium: Local builder and auto-balancer can influence work without a single planning authority surface

Evidence:

- `polish_loop/orchestrator.py:1-14` says the orchestrator is the central loop controller and sole status writer.
- `polish_loop/orchestrator.py:85-91` says future Cassandra tool additions must use `cassandra_custom_tools.py`, not direct `cassandra_brain.py`.
- `polish_loop/local_builder.py:1-16` is a local Ollama builder wrapper that can read files, run safe commands, and write `pc_output`.
- `builder_watcher.sh:107-123` builds a local builder command for `runner=ollama`.
- `builder_watcher.sh:300-329` executes the builder command.
- `queue_balancer.py:188-263` and `queue_balancer.py:430-560` can generate optimization task templates involving Chief/Cassandra modules.
- `agent_task_proposals.py:1-19`, `112-155`, and `337-364` correctly mark task proposals advisory-only until promoted.

Finding:

The loop has useful constraints, but local builder and queue-balancer generated tasks can create planning pressure near canonical modules. The advisory proposal store is a good model; not all generated work appears equally bounded by a single authority description.

Risk:

Medium. The risk is not current execution bypass, but future confusion about whether generated tasks are advisory, scheduled, or authoritative.

Smallest Phase 2 direction:

Add a task-origin field/check for generated tasks: human, harness, queue_balancer, Cassandra proposal, Hermes proposal, or builder rework. Keep promotion explicit.

### Low: Guardian boundary is mostly clean, with a naming/fallback clarity risk

Evidence:

- `chief_approval_brain.py:1-27` defines the approval gate and approval tiers.
- `chief_approval_brain.py:650-696` records decisions with ID binding.
- `chief_guardian_sender.py:1-17` states Cassandra is excluded and Guardian is an approval gate.
- `chief_guardian_listener.py:1-32` says Guardian is approval-only and not for operational, Chief, or Cassandra queries.
- `chief_guardian_listener.py:62-194` and `197-234` enforce auth and approval code binding.
- `guardian_schema_harness.py:1-11` is a validation harness only.
- `guardian_schema_harness.py:211-222` verifies live pending approval state is not written.

Finding:

Guardian is one of the clearest boundaries. The only clarity risk is that the sender may fall back to the Chief bot for approval delivery when no dedicated Guardian bot is configured.

Risk:

Low. It is mostly naming/operator clarity, not an architectural defect.

Smallest Phase 2 direction:

Keep the fallback, but make approval messages visibly say "Guardian approval delivered through Chief transport" when applicable.

### Low: PI appears reserved, not active

Evidence:

- Searches for `PI`, `Planning Intelligence`, and `planning intelligence` found no active planning-authority code.
- Existing `pii_vault.py`, `PII_VAULT_CONNECTED`, and related references are privacy/PII surfaces, not a PI agent.

Finding:

No active PI planning authority was found.

Risk:

Low, provided PI remains reserved and no "PI" code is added without a formal boundary.

Smallest Phase 2 direction:

Do not implement PI. If PI is later introduced, require a boundary doc before code.

## Local LLM contention findings

### Current model router and model selection surfaces

- `chief_llm.py:63` defines the local Ollama generate endpoint.
- `chief_llm.py:66-85` defines lane candidates.
- `chief_llm.py:87-153` defines task-class model candidates.
- `chief_llm.py:155-170` defines preferred lanes by task class.
- `chief_llm.py:248-249` preserves legacy model constants.
- `chief_llm.py:308-334` shells out to `ollama list` and caches installed models.
- `chief_llm.py:337-394` resolves local model lanes and route reasons.
- `chief_llm.py:397-432` resolves a local model and provides agent default lanes.
- `chief_llm.py:435-510` performs synchronous local Ollama calls with retries and diagnostics.
- `chief_llm.py:522+` blocks Claude/cloud calls by policy unless explicitly overridden.

Finding:

`chief_llm.py` is the closest thing to a model router, but it is not a contention manager. It chooses models and timeouts, but does not enforce a central queue, priority, per-agent budget, or heavy-model lock.

### Direct or semi-direct local model consumers

- `cassandra_brain.py:5119-5182` calls `resolve_local_model()` and `ollama_call()` in `_call()`, with cloud fallback policy paths.
- `cassandra_brain.py:1511-1568` contains Cassandra-specific deep/small model selection and route logging.
- `cassandra_briefing_brain.py:871-908` runs briefing stages through local model calls.
- `cassandra_briefing_brain.py:966-1042` generates Guardian, Chief, and Cassandra briefing stages.
- `cassandra_briefing_brain.py:1229-1260` uses a newer JSON generation path for morning briefs and a fallback non-morning model.
- `chief_router.py:1461-1524` hardcodes `gemma4:e4b` for artifact transformation with `timeout=600`.
- `chief_router.py:1567-1584` hardcodes `qwen3.6:latest` for Chief fallback with `timeout=600`.
- `chief_acceptance_gate.py:66-85` calls the local Ollama HTTP endpoint directly for a fast acceptance verdict.
- `polish_loop/local_builder.py:43-51` allows up to 40 turns and 900 seconds per local builder API call.
- `polish_loop/pc_review_fallback.py:229-295` uses a deep model review fallback.
- `chief_album_brain.py:9-10`, `257-282`, and `1081-1105` call the local Ollama API directly with module-local model constants.
- `sidecars/hermes/scripts/run_morning_annex.sh:1-77` runs Hermes with `qwen3.6:latest`.

Finding:

Several paths bypass task-class routing or use it without central contention control. The heaviest risk comes from long-running background or sidecar calls competing with operator-facing Chief/Cassandra requests.

### Current running model-adjacent processes observed

Observed by `pgrep -af 'ollama|chief_|cassandra_|hermes|guardian'`:

- `ollama serve`
- `chief_listener.py`
- `cassandra_listener.py`
- `ceo_briefing_worker.py`
- `chief_memory_worker.py`
- `cassandra_briefing_scheduler.py`
- `cassandra_watcher.py`
- `chief_state_worker.py`
- `chief_watcher_brain.py`
- `chief_worker.py`
- `chief_album_brain.py`
- `chief_billing_brain.py`
- `hermes_cli.main gateway run --replace`

Finding:

Many always-on processes can initiate or sit near model work. No observed path showed a shared local-model semaphore or priority queue.

### Installed local model footprint observed

Observed by `ollama list`:

- 2.5 GB to 5.2 GB models: `qwen3:4b`, `nemotron-3-nano:4b`, `qwen3:8b-q4_K_M`, `mistral-nemo:12b-instruct-2407-q2_K`
- 9.6 GB to 14 GB models: `gemma4:e4b`, `magistral:latest`, `mistral-small:latest`
- 17 GB to 24 GB models: `gemma4:26b`, `gemma4:31b`, `qwen3.6:latest`, `nemotron-3-nano:30b`

Finding:

The large models can plausibly monopolize memory/compute and stall small interactive work if called concurrently or back-to-back without prioritization.

### Paths that should remain deterministic

These surfaces should not consume local model capacity unless deliberately redesigned:

- `chief_morning_synthesis.py:1-10`, `185-310`: deterministic artifact-first Morning Synthesis writer.
- `chief_ops_reporter.py:1-7`, `34-145`: deterministic ops parsing and reporting.
- `guardian_schema_harness.py:1-11`, `152-222`: staging-only validation harness.
- `agent_task_proposals.py:112-177`, `199-250`, `337-364`: advisory proposal normalization, promotion, and markdown.
- `google_access_policy.py:1-15`, `42-117`: deterministic policy table and denied-by-default decisions.

### Priority and queue gaps

- No central model queue was found.
- No central heavy-model lock was found.
- No per-agent quota or deadline policy was found.
- Some timeouts are long enough to block useful work: `chief_router.py` uses 600 second calls, local builder can use 900 second calls, and briefing/Hermes paths can use heavy models.
- Acceptance/approval, intent classification, and operator-facing acknowledgements should have higher priority than background transforms, Hermes annex generation, local builder loops, and deep review fallback.

Recommended priority policy for Phase 2:

1. P0: approval/Guardian text, operator acknowledgement, emergency/stop/status. Prefer deterministic or fast lane only.
2. P1: Chief/Cassandra intent classification and short interactive replies. Fast lane with short timeout.
3. P2: scheduled briefing generation. Bounded intentional lane.
4. P3: reports, artifact transforms, review fallback. Background lane.
5. P4: local builder, Hermes heavy annex, large-model experiments. Heavy lane with explicit lock and cancellable status.

## Severity summary

- Critical: none found in this audit.
- High: Cassandra action initiation inside brain logic; Chief router execution/model/file-write mix; PC review fallback fail-open.
- Medium: inconsistent reply validation coverage; raw parsing inside brain modules; split capability truth; Hermes canonical blur through service/dashboard wiring; generated task authority clarity; decentralized local LLM contention.
- Low: Guardian transport fallback naming clarity; PI reserved-state clarity.

## Recommended Phase 2 fixes, smallest-safe-first

1. Add a read-only local model usage inventory check.
   - Purpose: list direct Ollama callers, hardcoded model names, long timeouts, and bypasses of `chief_llm`.
   - Why first: no behavior change, immediate visibility into contention.

2. Add a small model contention gate in `chief_llm.py`.
   - Purpose: preserve existing synchronous API while adding priority labels, a heavy-lane lock, and visible "busy" diagnostics.
   - Start with logging/diagnostics before blocking behavior.

3. Make PC review fallback fail neutral instead of pass on unavailable/ambiguous LLM review.
   - Purpose: close the highest-risk harness fail-open path.
   - Keep it isolated to `polish_loop/pc_review_fallback.py` and tests.

4. Normalize Chief listener validation coverage.
   - Purpose: every response path is validated, deterministic-exempt, or explicitly labeled as transport/status-only.
   - Avoid changing route decisions in this slice.

5. Extract one Cassandra context collector from `build_context_snapshot()`.
   - Purpose: separate raw file/log parsing from brain judgment.
   - Keep output shape unchanged.

6. Convert one Cassandra side-effect workflow into a structured proposal.
   - Start with future-action queue or upgrade-task creation.
   - Purpose: prove a proposal-first pattern without breaking email/calendar flows.

7. Reconcile capability surfaces with a consistency checker.
   - Purpose: detect drift across `capability_registry.py`, `cassandra_capability.py`, and `google_access_policy.py`.
   - Do not collapse authority tables yet.

8. Keep Hermes visibly sidecar-only.
   - Purpose: label outputs/services as non-canonical and non-blocking.
   - Do not let Hermes write queues, vault state, or canonical operator docs.

9. Add task-origin metadata for generated tasks/proposals.
   - Purpose: distinguish human requests, queue balancer, Cassandra proposal, Hermes proposal, harness rework, and builder output.

## Do not change yet

- Do not rename Chief, Cassandra, Guardian, or Hermes.
- Do not implement PI or give PI planning authority.
- Do not move large agent files or perform broad architecture refactors.
- Do not change approval tiers or Google broker policy while doing boundary cleanup.
- Do not alter Legal product files as part of this audit.
- Do not wire Hermes into canonical vault, queue, approval, or planning authority.
- Do not make Hermes output required for Morning Brief completion.
- Do not replace the local model stack or install model dependencies.
- Do not introduce cloud model fallback as a contention fix.
- Do not convert every Cassandra action path in one PR.
- Do not stage, revert, clean, or commit unrelated Cassandra/Chief/Hermes/systemd dirty files as part of this report.

## Verification commands run

Read-only audit commands:

```bash
pwd
git status --short
sed -n '1,220p' OPENCLAW_RUNTIME.md
sed -n '1,220p' USER.md
sed -n '1,260p' CORE_ARCHITECTURE_PRINCIPLES.md
test -f docs/planning/agent_boundary_resource_audit.md && sed -n '1,260p' docs/planning/agent_boundary_resource_audit.md
sed -n '1,240p' docs/operations/DEPENDENCY_HYGIENE.md
sed -n '1,240p' docs/testing/VALIDATION_POLICY.md
sed -n '1,260p' docs/testing/VALIDATION_MAP.md
sed -n '1,260p' docs/testing/HARNESS_INDEX.md
rg -n "Chief|Cassandra|Guardian|Hermes|\\bPI\\b|Planning Intelligence|planning intelligence" --glob '!/.git/**' --glob '!chief_env/**' --glob '!sidecars/hermes/.venv/**' .
rg -n "ollama|OLLAMA|model=|task_class|timeout=|qwen|gemma|nemotron|mistral|magistral|claude|openai" --glob '!/.git/**' --glob '!chief_env/**' --glob '!sidecars/hermes/.venv/**' .
rg -n "subprocess|Popen|os\\.system|broker_call|google_access_broker|request_approval|propose_action|enqueue|write_text|open\\(" chief_*.py cassandra_*.py capability_registry.py google_access_*.py polish_loop scripts dashboard_gen.py
rg -n "validate_reply|harness|Guardian|approval|evidence|artifact|canonical|non-canonical|advisory|proposal" chief_*.py cassandra_*.py guardian_*.py agent_task_proposals.py polish_loop dashboard_gen.py sidecars/hermes
find sidecars -maxdepth 4 -type f | sort
pgrep -af 'ollama|chief_|cassandra_|hermes|guardian'
ollama list
```

Targeted file reads included:

```bash
nl -ba chief_llm.py | sed -n '1,560p'
nl -ba chief_router.py | sed -n '780,1660p'
nl -ba chief_listener.py | sed -n '1,470p'
nl -ba cassandra_brain.py | sed -n '1,220p'
nl -ba cassandra_brain.py | sed -n '430,790p'
nl -ba cassandra_brain.py | sed -n '1160,1585p'
nl -ba cassandra_brain.py | sed -n '2060,2425p'
nl -ba cassandra_brain.py | sed -n '2480,3105p'
nl -ba cassandra_brain.py | sed -n '3240,3510p'
nl -ba cassandra_brain.py | sed -n '4200,4345p'
nl -ba cassandra_brain.py | sed -n '5100,5685p'
nl -ba cassandra_listener.py | sed -n '120,410p'
nl -ba cassandra_briefing_brain.py | sed -n '1,220p'
nl -ba cassandra_briefing_brain.py | sed -n '850,1265p'
nl -ba chief_morning_synthesis.py | sed -n '1,330p'
nl -ba chief_ops_reporter.py | sed -n '1,170p'
nl -ba chief_acceptance_gate.py | sed -n '1,140p'
nl -ba polish_loop/pc_review_fallback.py | sed -n '220,305p'
nl -ba polish_loop/orchestrator.py | sed -n '1,230p'
nl -ba agent_task_proposals.py | sed -n '1,380p'
nl -ba chief_approval_brain.py | sed -n '1,120p'
nl -ba chief_approval_brain.py | sed -n '640,830p'
nl -ba chief_guardian_sender.py | sed -n '1,110p'
nl -ba chief_guardian_listener.py | sed -n '1,250p'
nl -ba guardian_schema_harness.py | sed -n '1,235p'
nl -ba google_access_policy.py | sed -n '1,135p'
nl -ba google_access_broker.py | sed -n '120,165p'
nl -ba google_access_broker.py | sed -n '610,815p'
nl -ba capability_registry.py | sed -n '1,310p'
nl -ba cassandra_capability.py | sed -n '1,120p'
nl -ba cassandra_capability.py | sed -n '390,470p'
nl -ba dashboard_gen.py | sed -n '130,190p'
nl -ba dashboard_gen.py | sed -n '1160,1230p'
nl -ba dashboard_gen.py | sed -n '1700,1905p'
nl -ba sidecars/hermes/.plans/hermes-morning-annex-plan.md | sed -n '1,120p'
nl -ba sidecars/hermes/.plans/hermes-loop-observer-role.md | sed -n '1,120p'
nl -ba sidecars/hermes/scripts/run_morning_annex.sh | sed -n '1,120p'
nl -ba polish_loop/local_builder.py | sed -n '1,220p'
nl -ba builder_watcher.sh | sed -n '90,130p'
nl -ba builder_watcher.sh | sed -n '292,335p'
nl -ba runner_registry.py | sed -n '120,190p'
nl -ba queue_balancer.py | sed -n '1,270p'
nl -ba queue_balancer.py | sed -n '420,565p'
nl -ba chief_album_brain.py | sed -n '1,45p'
nl -ba chief_album_brain.py | sed -n '250,290p'
nl -ba chief_album_brain.py | sed -n '1070,1110p'
```

Post-report verification commands:

```bash
git diff -- docs/planning/agent_boundary_resource_audit.md
git status --short
ls -l docs/planning/agent_boundary_resource_audit.md
git status --short --untracked-files=all docs/planning/agent_boundary_resource_audit.md
git check-ignore -v docs/planning/agent_boundary_resource_audit.md
wc -l docs/planning/agent_boundary_resource_audit.md
```

Git status at report creation time:

```text
 M .gitignore
 M capability_registry.py
 M cassandra_brain.py
 M cassandra_briefing_brain.py
 M cassandra_capability.py
 M cassandra_listener.py
 M chief_listener.py
 M chief_llm.py
 M chief_morning_synthesis.py
 M chief_router.py
 M dashboard_gen.py
 M polish_loop/status.json
 M systemd/user/openclaw-stack.target.in
 M tests/test_cassandra_briefing_context.py
 M tests/test_cassandra_payment_verify.py
 M tests/test_chief_llm_router.py
?? scripts/check_cassandra_capability_drift.py
?? systemd/user/hermes-gateway.service.in
```

Note: `docs/planning/agent_boundary_resource_audit.md` exists, but normal `git status --short` does not show it because `.gitignore:1:*` ignores it. `git check-ignore -v docs/planning/agent_boundary_resource_audit.md` reported:

```text
.gitignore:1:*	docs/planning/agent_boundary_resource_audit.md
```
