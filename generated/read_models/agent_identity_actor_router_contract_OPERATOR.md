# Agent Identity + Actor Router Contract v0

## Operator Summary
OpenClaw now has a deterministic identity/routing contract for known actors. It can say who should inspect a lane, why, what package types they may preview, and what remains blocked. It does not launch agents or call models.

## Known Actors
- `operator_winship`: Operator / Winship — final human authority and memory comparison source (human_operator, clearance `operator_final_authority`).
- `chief`: Chief — coordination, work-board, check-engine, and queue posture (governed_agent, clearance `internal_operator_safe`).
- `guardian`: Guardian — safety, security, protected access, approval, and authority boundaries (governed_agent, clearance `protected_context_required_future_gate`).
- `cassandra`: Cassandra — communications, email/calendar review, and finance/AP-facing workflow visibility (governed_agent, clearance `sensitive_metadata_only`).
- `hermes`: Hermes — systems review, architecture, doctrine, horizon checks, and coherence review (advisory_actor, clearance `internal_operator_safe`).
- `niles`: Niles — music, art, producer, and creative operator context (governed_agent, clearance `internal_operator_safe`).
- `codex`: Codex — scoped implementation worker for backend/code/test lanes (implementation_worker, clearance `public_or_repo_safe`).
- `gemini_antigravity`: Gemini / Antigravity — scoped implementation, refactor, proof, planner/verifier worker (implementation_worker, clearance `public_or_repo_safe`).

## Routing Rules
- `safety_security_protected_access_first`: safety, security, protected access, approval, or authority ambiguity routes `guardian -> chief -> operator_winship`.
- `code_implementation_scoped_worker`: backend/code/test/read-model implementation routes `chief -> codex -> gemini_antigravity -> guardian -> operator_winship`.
- `music_art_creative_first`: music, art, Struna, album metadata, creative production routes `niles -> codex -> guardian -> operator_winship`.
- `communications_finance_ap_first`: communications, finance/AP, email, calendar, or Capital Hilton-style workflow review routes `cassandra -> guardian -> operator_winship`.
- `big_picture_architecture_doctrine`: doctrine, app architecture, system coherence, horizon checks routes `hermes -> chief -> guardian -> operator_winship`.
- `work_board_check_engine_queue`: work-board, check-engine, queue posture, active build coordination routes `chief -> guardian -> codex -> operator_winship`.
- `final_action_authority`: final action, approval, send, submit, credential, or irreversible decision routes `guardian -> operator_winship`.
- `whole_system_uncertainty`: cross-domain ambiguity, major doctrine shift, or pre-security audit review routes `chief -> hermes -> guardian -> cassandra -> niles -> codex -> gemini_antigravity -> operator_winship`.

## Mission Control Guidance
- Top layer: Who should look at this?
- Middle layer: Why this actor, what they can inspect, and what they must not do.
- Lower layer: Package preview, contract refs, proof refs, clearance, and receipt requirements.
- Do not imply live agents are running.

## Blocked Actor Authorities
- self-assign clearance, tools, memory, workspace, or authority
- call a model or agent from this contract
- activate a tool protocol, plugin, browser, OAuth, Gmail, calendar, Coupa, or Telegram bridge
- send, submit, approve, mutate accounts, or perform external actions
- handle, request, persist, or infer credentials
- run background surveillance, hidden memory capture, or broad file indexing
- write OpenClaw artifacts to PC C: drive
- convert future-gated package preview into live dispatch

## Next Lanes
- `model_selection_policy_contract_v0` (P0): Model Selection Policy Contract v0
- `agent_package_preview_contract_v0` (P1): Agent Package Preview Contract v0
- `mission_control_actor_routing_surface_v0` (P1): Mission Control Actor Routing Surface v0
- `tool_protocol_adapter_registry_v0` (P2): Tool Protocol Adapter Registry v0
- `agent_memory_scope_contract_v0` (P2): Agent Memory Scope Contract v0

## Authority Boundary
- `runtime_authority`: `false`
- `activation_allowed`: `false`
- `model_call_authority`: `false`
- `agent_call_authority`: `false`
- `external_tool_authority`: `false`
- `credential_authority`: `false`
- `actor_self_authority`: `false`
- `routing_execution_authority`: `false`
- `operator_final_authority`: `true`
- `browser_oauth_account_access_enabled`: `false`
- `gmail_calendar_coupa_telegram_enabled`: `false`
- `send_submit_approval_enabled`: `false`
- `network_execution_enabled`: `false`
- `runtime_daemon_enabled`: `false`
- `hidden_memory_capture_enabled`: `false`
- `background_surveillance_enabled`: `false`
- `pc_c_drive_artifact_write_allowed`: `false`
- `mission_control_app_authority_added`: `false`
