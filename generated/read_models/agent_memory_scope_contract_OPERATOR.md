# Agent Memory Scope Contract v0

## Operator Summary
OpenClaw now has a deterministic memory-scope contract. It says what memory surfaces are canonical, what is only residue, what actors may read as context, what they may propose as memory candidates, and what requires operator promotion or Guardian review. It does not create model memory or ingest raw chat.

## Canonical Memory Surfaces
- `vault`: canonical only when explicitly promoted into this surface with proof/receipt
- `handoff`: canonical only when explicitly promoted into this surface with proof/receipt
- `mac_eyes`: canonical only when explicitly promoted into this surface with proof/receipt
- `polish_loop`: canonical only when explicitly promoted into this surface with proof/receipt
- `CLAUDE.md`: canonical only when explicitly promoted into this surface with proof/receipt

## Non-Canonical Residue
- `session-local memory`: `non_authoritative_residue`
- `workspace artifacts`: `non_authoritative_residue`
- `assistant checkpoint files`: `non_authoritative_residue`
- `Copilot workspace memory`: `non_authoritative_residue`
- `temporary scratch files`: `non_authoritative_residue`
- `unpromoted chat summaries`: `non_authoritative_residue`
- `unreceipted worker notes`: `non_authoritative_residue`
- `unverified generated artifacts`: `non_authoritative_residue`

## Actor Memory Scopes
- `operator_winship`: reads 5 allowed context groups, blocks 3, promotion required `false`.
- `chief`: reads 4 allowed context groups, blocks 4, promotion required `true`.
- `guardian`: reads 4 allowed context groups, blocks 3, promotion required `true`.
- `cassandra`: reads 4 allowed context groups, blocks 4, promotion required `true`.
- `hermes`: reads 4 allowed context groups, blocks 3, promotion required `true`.
- `niles`: reads 4 allowed context groups, blocks 4, promotion required `true`.
- `codex`: reads 4 allowed context groups, blocks 5, promotion required `true`.
- `gemini_antigravity`: reads 4 allowed context groups, blocks 5, promotion required `true`.

## Context / Sensitivity Boundary
- Allowed context is refs, receipts, source cards, accepted packets, project capsules, and operator handoffs.
- Raw private bodies are blocked by default.
- Protected material uses metadata-only references unless a future Guardian gate and receipt allow otherwise.

## Mission Control Guidance
- Top layer: what memory would this actor see?
- Middle layer: what is excluded and why?
- Lower layer: promotion, sensitivity, proof, receipts
- Full inspection: complete memory scope decision
- Show non-canonical residue as non-authoritative.

## Authority Boundary
- `runtime_authority`: `false`
- `model_memory_authority`: `false`
- `hidden_memory_authority`: `false`
- `autonomous_memory_capture`: `false`
- `raw_chat_ingestion_authority`: `false`
- `vector_memory_authority`: `false`
- `external_tool_memory_authority`: `false`
- `credential_memory_authority`: `false`
- `operator_final_authority`: `true`
- `model_call_authority`: `false`
- `agent_call_authority`: `false`
- `tool_execution_authority`: `false`
- `routing_execution_authority`: `false`
- `browser_oauth_account_access_enabled`: `false`
- `gmail_calendar_coupa_telegram_enabled`: `false`
- `send_submit_approval_enabled`: `false`
- `network_execution_enabled`: `false`
- `runtime_daemon_enabled`: `false`
- `background_surveillance_enabled`: `false`
- `pc_c_drive_artifact_write_allowed`: `false`

## Next Lanes
- `tool_protocol_adapter_registry_v0` (P1): Tool Protocol Adapter Registry v0
- `memory_candidate_receipt_v0` (P1): Memory Candidate Receipt v0
- `mission_control_package_preview_surface_v0` (P2): Mission Control Package Preview Surface v0
- `mission_control_actor_routing_surface_v0` (P2): Mission Control Actor Routing Surface v0
- `model_selection_receipt_v0` (P3): Model Selection Receipt v0
