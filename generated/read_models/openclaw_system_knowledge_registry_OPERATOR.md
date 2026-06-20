# OpenClaw System Knowledge Registry

## Summary
- Registry ID: `openclaw_system_knowledge_registry`
- Schema version: `openclaw_system_knowledge_registry_v0`
- Component count: 33
- Spine steps: 7
- Router families: 6
- Brain route records: 10
- Orchestration decisions: 8
- Known unknown count: 12
- Build task count: 10
- Boundary: documentation/read-model/SQLite only.
- READY means registry artifacts validated; it does not grant runtime, business, model, or GitHub authority.

## Authority Boundaries
- `documentation_read_model_sqlite_only`: true
- `live_automation_granted`: false
- `runtime_service_mutation_allowed`: false
- `email_gmail_send_or_draft_allowed`: false
- `browser_coupa_bank_access_allowed`: false
- `workbook_pdf_ledger_invoice_mutation_allowed`: false
- `confirmed_reference_data_mutation_allowed`: false
- `daw_media_session_mutation_allowed`: false
- `live_model_invocation_allowed`: false
- `guardian_approval_bypass_allowed`: false
- `git_push_or_merge_allowed`: false
- `hermes_start_allowed`: false
- `niles_daw_daemon_start_allowed`: false

## Components
- `cassandra`: CONFIRMED_LOCAL - Cassandra owns operator communications, guided review, universal intake surfaces, and exact-send request state.
- `chief`: CONFIRMED_LOCAL - Chief coordinates system status, diagnostics, routing, and operator-facing build/readiness work.
- `guardian`: CONFIRMED_LOCAL - Guardian is the approval and protected-action boundary for high-risk requests.
- `niles`: CONFIRMED_LOCAL_LOGICAL - Niles is a logical/spawned creative lane for music and album context.
- `hermes`: CONFIRMED_LOCAL_BOUNDARY - Hermes is an architecture and adapter-boundary lane with sidecar planning artifacts.
- `watch_desk`: CONFIRMED_LOCAL - Watch Desk projects current operator-facing items from read models and receipts.
- `universal_intake`: CONFIRMED_LOCAL - Universal Intake classifies local operator messages into income, expense, gig, identity, lane, and approval-gated request records.
- `context_switchboard`: CONFIRMED_LOCAL - Context Switchboard maintains active/resumable operator contexts and protects lane switching.
- `guided_review_coach`: CONFIRMED_LOCAL - Guided Review and Coach Mode run provisional Data Room review sessions with explanatory coach replies.
- `data_room_form_fill_lane`: CONFIRMED_LOCAL - Packages the Data Room review as a redacted form and paste-ready manual ChatGPT 5.5 prompt.
- `model_work_package_router`: CONFIRMED_LOCAL - Routes model/work packages through bounded metadata and permission boundaries.
- `assignment_loop_contract`: CONFIRMED_LOCAL - Defines bounded worker assignments with goal, sources, standard, proof, permissions, and stop conditions.
- `worker_run_manager`: CONFIRMED_LOCAL - Manages package lifecycle, dispatch claims, ingest records, and package read models without calling external workers.
- `reference_data_hydration`: CONFIRMED_BLOCKED_UNTIL_CONFIRMED_DATA - Hydrates confirmed Data Room reference data when confirmed data exists.
- `artifact_link_normalizer`: CONFIRMED_LOCAL - Copies intended operator-facing artifacts to Windows-openable report folders and writes manifests.
- `pc_mac_sync`: PARTIAL_LOCAL - Tracks read-model shuttle and PC/Mac generated artifact sync posture.
- `invoice_ledger_discovery`: CONFIRMED_LOCAL_BOUNDARY - Finance routes can explain proof state, payment watch, and candidate evidence posture.
- `voice_kokoro_caveat`: CONFIRMED_DEGRADED_OR_NONCANONICAL - Voice/Kokoro may be degraded or side-effect-only; text route is canonical.
- `compose_gate_pipeline`: CONFIRMED_LOCAL - The compose front door routes redacted operator text to read-only handlers or G3 packet approval.
- `orbit_brain_map`: CONFIRMED_ORCHESTRATION_SOURCE - Structured inventory of old-router brains and their WIRE/RETIRE/VERIFY disposition into compose.
- `gig_intake_flow`: CONFIRMED_LOCAL - Cassandra can collect gig facts, persist session state, and stage approval packets for intro email and invoice.
- `correspondence_agent_plan`: PLANNED_SEND_HOLD - Design for watch, understand, calendar-aware draft, and gate loop for inbound correspondence.
- `approval_gate_convergence`: CONFIRMED_LOCAL - Legacy email/SMS/approval surfaces converge onto the G3 packet gate in compose preview metadata.
- `the_spine`: CONFIRMED_ORCHESTRATION_SOURCE - The canonical seven-step deterministic front door for intake, PII gating, intent routing, SQLite packet recording, approval, execution, and receipt closure.
- `maestro_protected_brain`: CONFIRMED_PARALLEL_BRANCH - Maestro's protected_generate path composes assistant text behind deterministic provenance and protected-action flags.
- `self_healing_polish_loop`: CONFIRMED_LOCAL - PC4 captures completed answers, audits claims against truth inputs, emits deterministic heal tasks, replays prompts, and routes proof/fail notifications.
- `cross_agent_truth_propagation`: CONFIRMED_LOCAL - Truth substrate records and reconciles operator facts so agents read shared proof instead of restating stale claims.
- `polish_loop_self_scaling`: CONFIRMED_LOCAL - Launcher metadata supports bounded worker lane scaling for the deterministic polish-loop/control-plane work.
- `sqlite_ledger_core`: CONFIRMED_LOCAL - SQLite runtime schema provides durable packet, evidence, validation, and handoff records for the backend control surface.
- `backend_package_request_schema`: CONFIRMED_LOCAL - BackendPackageRequest is the structured packet that carries sanitized workflow intent, target, readback, permissions, and validation metadata toward the ledger.
- `conversational_workflow_router_contract`: CONFIRMED_LOCAL - Router contract maps sanitized chat/workflow input to RoutedWorkflowIntent and BackendPackageRequest records.
- `map_room_markdown_atlas`: CONFIRMED_LOCAL - Read-only Map Room and Markdown Atlas references help agents discover system territory, file ownership posture, and registry truth sources.
- `system_knowledge_query`: CONFIRMED_LOCAL - Deterministic helper for agents to answer system-shape, known-unknown, orbit, and task questions from registry/ledger/atlas data.

## The Spine
- Canonical name: `The Spine`; operator lock: `/mnt/e/openclaw/orchestration/SYSTEM-SPINE-7-STEP-FLOW.md`
1. `spine_step_01_intake_front_door` / Intake Front Door - Intake records the signal shape only; it does not execute, send, or mutate protected state.
2. `spine_step_02_pii_gate` / PII Gate - Raw PII is blocked from normal read-models; graded tokenization still requires the owning privacy/legal boundary.
3. `spine_step_03_intent_lm_gate` / Intent LM Gate - Deterministic routing or bounded draft-LM classification only; no execution authority.
4. `spine_step_04_sqlite_packet_maker` / SQLite Packet Maker - SQLite is an immutable receipt ledger and packet store, not runtime execution authority.
5. `spine_step_05_approval_guardian_gate` / Approval / Guardian Gate - SEND_HOLD, money gates, and operator/Guardian approval are absolute for protected actions.
6. `spine_step_06_lm2_responder_executor` / LM2 Responder / Executor - Responder output is candidate/proof-bearing text unless an approved executor and final gate accept it.
7. `spine_step_07_final_output_gate_receipt` / Final Output Gate / Receipt - Code and gates decide DONE; model claims alone never close the loop.

## Router Registry
- `router_chat` (Chat): Sanitized operator/chat text into read-only answer, workflow intent, or approval packet paths. Next: Classify through the Intent LM Gate, then packetize only if the Approval / Guardian Gate can own the protected boundary.
- `router_file_metadata` (FileMetadata): File/path territory terms into dependency, generated-output, unsafe-to-move, or manual-review postures. Next: Treat unknown or private-root terms as manual review; never auto-clean or move files from a lookup.
- `router_evidence_intake` (EvidenceIntake): Proof/evidence events into receipts, packet validation metadata, and read-only response posture. Next: Record sanitized proof posture and require owner approval before finance/legal/business mutation.
- `router_workflow_packages` (WorkflowPackages): RoutedWorkflowIntent records into BackendPackageRequest, model/role targets, and worker package lifecycle records. Next: Persist the packet to SQLite and wait for the declared gate before worker dispatch.
- `router_local_surface` (LocalSurface): Local worker, acceptance, and self-heal surfaces into deterministic ledger tasks and proof receipts. Next: Emit detector-origin heal tasks only when payload validation passes and acceptance tests remain immutable.
- `router_operator_events` (OperatorEvents): Operator event text into local receipts, active context, or approval-gated business packets. Next: Write local receipts/read-models and escalate protected operations through Approval / Guardian Gate.

## Brain Route Inventory
- `chief_musiclaw_brain`: WIRE / read_only_category_added - read-only Q&A; no legal advice authority
- `chief_publishing_brain`: WIRE / read_only_category_added - read-only rights/catalog posture only
- `chief_cpa_brain`: WIRE / read_only_category_added - read-only tax/accounting orientation; no tax advice or filing
- `chief_financial_brain`: WIRE / read_only_category_added - read-only finance reports; no ledger mutation
- `chief_invoice_brain`: RETIRE / not_wired_retire_candidate - do not use for invoice authority; superseded by billing/gig flows
- `chief_email_brain`: WIRE_G3_GATE / g3_convergence_metadata_added - draft/gate only; no executor registered under SEND_HOLD
- `chief_sms_brain`: WIRE_G3_GATE / g3_convergence_metadata_added - draft/gate only; no executor registered under SEND_HOLD
- `chief_watcher_brain`: VERIFY / verified_active_service_not_compose_wired - background alerter only; no send or mutation authority
- `chief_billing_brain`: PARK_FOR_GATED_BILLING_FLOW / surveyed_mixed_write_session_surface - must route through gated billing/gig/invoice flows, not generic read-only
- `read_only_orbit_brain_group`: WIRE / pc12_categories_added - read-only categories only; write-like phrases fail closed to gated paths

## Orchestration Decisions
- `decision_compose_front_door`: accepted - compose(text) is the one operator front door. Next: Keep adding intent categories and packet previews through compose.
- `decision_generated_churn_not_authority`: accepted - Volatile generated snapshots are not source-of-truth changes by themselves. Next: Commit source/test/read-model artifacts intentionally by task.
- `decision_square_payment_rail`: approved_direction_not_executor - Square is approved as a payment rail, while branded invoice artifacts remain what the client sees. Next: Use Square sandbox/spec work only until hold is lifted and executor is approved.
- `decision_first_real_send_reynolds`: accepted_planning_target - First real send target is Reynolds Tavern, not Capital Hilton. Next: Stage Reynolds packets; do not send under SEND_HOLD.
- `decision_send_hold_active`: active_boundary - No external sends of any kind until the hold is explicitly lifted. Next: Continue drafting, designing, contract tests, and safetied wiring only.
- `decision_the_spine_canonical_front_door`: operator_locked - The Spine is the canonical deterministic seven-step intake-to-receipt front door. Next: Keep new router/ledger work mapped to one of the seven Spine steps.
- `decision_sqlite_ledger_not_execution_authority`: active_boundary - SQLite stores immutable packet, evidence, validation, handoff, and receipt rows. Next: Route protected packets through Approval / Guardian Gate before responder or executor use.
- `decision_maestro_protected_brain_requires_gates`: parallel_branch_recorded - Maestro protected_generate output remains candidate/advisory until deterministic gates accept it. Next: On deploy, reconcile the protected brain code into the canonical branch and refresh this registry evidence status.

## Known Unknowns
- `unknown_missing_prior_commit`: Reported local registry commit - UNKNOWN_UNREACHABLE. Next: Use this rebuilt branch/patch as the review source unless the original commit is later restored.
- `unknown_live_chatgpt55_adapter`: Live ChatGPT 5.5 advisory path - NOT_VERIFIED_AS_LIVE_ADAPTER. Next: Build a separate approved adapter readiness lane before claiming a live ChatGPT brain.
- `unknown_external_repo_a`: External Repo A - UNKNOWN_EXTERNAL. Next: Inspect the intended external repository in its own checkout when provided.
- `unknown_external_repo_b`: External Repo B - UNKNOWN_EXTERNAL. Next: Reconcile the cross-repo estate map with explicit repo paths or remotes.
- `unknown_mac_map_import_agent`: Mac stable map import - KNOWN_GAP. Next: Create or run mac_map_import_agent in a separate sync lane.
- `unknown_confirmed_reference_data`: Confirmed reference data - BLOCKING_ABSENCE_OR_NOT_CONFIRMED_HERE. Next: Run a separate promotion task over confirmed guided-review answers.
- `unknown_runtime_service_freshness`: Runtime service state - OUT_OF_SCOPE. Next: Use a verify-only runtime readiness lane if service freshness matters.
- `unknown_private_finance_truth`: Private finance proofs - BLOCKED_BY_BOUNDARY. Next: Use redacted proof-bundle and evidence-intake lanes with explicit permission.
- `unknown_correspondence_gmail_scope`: Correspondence watcher Gmail scope - OPERATOR_SCOPE_DECISION_REQUIRED. Next: Ask Winship whether Gmail readonly body scope is allowed for the correspondence watcher.
- `unknown_reynolds_canonical_ledger_row`: Reynolds gig canonical ledger row - RESOLVED_PC16. Next: Use the pending approval packet ids for future approved draft/send work; do not send under SEND_HOLD.
- `unknown_graphiffy_atlas_staleness`: Graphiffy/atlas freshness - RESOLVED_PC17. Next: Refresh again after major new source roots or compose/API spine changes.
- `unknown_registry_pr_source`: Codex Web PR source - UNKNOWN_UNPUBLISHED. Next: Use the pushed local branch or compare URL as the review source after validation succeeds.

## Build Tasks
1. Apply and validate registry patch on Mac (Mac Codex) - ready_for_mac_apply
2. Promote confirmed Data Room reference answers (Cassandra / Codex) - blocked_until_operator_confirmation
3. Prove or reject live ChatGPT 5.5 advisory adapter (Hermes / Guardian) - future_gated
4. Resolve Mac map import gap separately (PC/Mac Sync) - separate_lane_required
5. Keep voice/Kokoro caveat separate (Cassandra) - known_caveat
6. Wire correspondence watcher loop safely (PC Codex) - scaffolded_pc9_send_hold_safetied
7. Scaffold email_send executor unregistered (PC Codex) - scaffolded_pc10_send_hold_safetied
8. Land Reynolds gig as canonical business record (PC Codex) - completed_pc16
9. Refresh atlas/Graphiffy after compose/orchestration wiring (PC Codex) - completed_pc17
10. Wire ledger tracking, live registry query, and parked polish-loop package design (PC Codex) - in_progress_pc18_pc19_pc20

## Current Safety Posture
- `posture_no_external_calls`: enforced_by_design - Registry exporter writes local artifacts only.
- `posture_no_live_grants`: closed - Registry output cannot authorize model, tool, runtime, finance, or business action.

## Generated Outputs
- `json`: `generated/read_models/openclaw_system_knowledge_registry.json`
- `operator_markdown`: `generated/read_models/openclaw_system_knowledge_registry_OPERATOR.md`
- `sqlite`: `generated/system_knowledge/openclaw_system_knowledge_registry.sqlite`
- `schema_sql`: `generated/system_knowledge/openclaw_system_knowledge_registry_SCHEMA.sql`
- `seed_sql`: `generated/system_knowledge/openclaw_system_knowledge_registry_SEED.sql`
