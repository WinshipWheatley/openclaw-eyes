# Agent Platform Alignment v0

## Operator Summary
OpenClaw already has many agent-platform primitives as deterministic contracts: packages, capabilities, gates, receipts, awareness maps, stable app map transport, and health proof. It does not yet have live persistent agents. The next safe step is to define agent identities and actor/model routing before any package dispatch or tool authority.

## What OpenClaw Already Has
- `package_compiler_contract`: deterministic mission/package compiler via package_compiler_contract (tracked_preview_only).
- `capability_skill_registry`: skill/capability registry via capability_skill_registry_metadata_delta (tracked_metadata_only).
- `protected_access_gates`: governed action and protected-context gates via Guardian protected access / protected evidence receipts (tracked_fail_closed).
- `cassandra_comms_detangle`: communications agent surface via cassandra_email_calendar_delta_detangle (tracked_visibility_only).
- `chief_work_and_health_posture`: coordination, work-board, and check-light posture via Chief work board / system health / sync health (tracked_read_model_only).
- `mission_control_awareness_spine`: operator awareness and gap map via operator awareness and nested lane spines (tracked_operator_surface).
- `stable_map_and_sync_receipts`: app-surface integration contract via stable map bundle / sync health (tracked_app_visible_contract).
- `domain_agent_future_mapping`: domain agent role mapping via Niles/Cassandra/Guardian/Chief/Hermes lane contracts (partly_tracked_future_gated).

## Missing Before Persistent Agents
- `durable_agent_identity_registry`: agent identity registry (NEEDS_CONTRACT).
- `actor_model_router_contract`: actor/model router and model-selection policy (NEEDS_CONTRACT).
- `memory_scope_contract`: per-agent memory and read-model scope contract (NEEDS_CONTRACT).
- `tool_protocol_adapter_registry`: tool protocol adapter registry (NEEDS_SECURITY_AUDIT).
- `per_agent_clearance_levels`: per-agent clearance and authority matrix (NEEDS_CONTRACT).
- `task_queue_lifecycle_receipts`: task queue lifecycle and result receipts (POST_SECURITY_FUTURE_GATED).
- `action_result_receipts`: action result receipt contract (NEEDS_CONTRACT).
- `revocation_kill_switch_contract`: revocation, disable, quarantine, and kill-switch contract (NEEDS_CONTRACT).
- `compromise_suspicion_posture`: compromise/suspicion posture (NEEDS_CONTRACT).

## Blocked Capabilities
- `autonomous_email_send`: blocked_or_future_gated. Autonomous email send remains blocked until a later security gate grants narrow authority.
- `calendar_mutation`: blocked_or_future_gated. Calendar mutation remains blocked; Cassandra calendar work is visibility/detangle only.
- `browser_coupa_credential_use`: blocked_or_future_gated. Browser, Coupa, OAuth, account, and credential use are not active platform capabilities.
- `oauth_tool_bridge_activation`: blocked_or_future_gated. Tool protocol or OAuth bridge activation requires a future governed adapter lane.
- `network_execution`: blocked_or_future_gated. Network execution is not part of this deterministic alignment read-model.
- `runtime_daemon_claims`: blocked_or_future_gated. Always-on or daemonized agents are future-gated readiness concepts only.
- `agent_self_assigned_authority`: blocked_or_future_gated. Actors and agents may not choose their own clearance, memory, tools, or action rights.
- `hidden_memory_capture`: blocked_or_future_gated. Memory capture must be explicit, scoped, visible, and receipt-backed.
- `background_surveillance`: blocked_or_future_gated. Background monitoring is blocked unless later represented by explicit gates and receipts.
- `broad_file_indexing`: blocked_or_future_gated. Broad filesystem indexing is blocked; approved source inventories remain bounded.

## Mission Control Guidance
- Top layer: OpenClaw is becoming an agent platform, but today this is only readiness mapping: what exists, what is missing, and what remains blocked.
- Middle layer: primitives, gaps, and blocked capabilities.
- Lower layer: proof and contract references.
- Do not make this a backend table wall or live control surface.

## Next Safe Lane
- `agent_identity_actor_router_contract_v0`: Agent Identity + Actor Router Contract v0
- Reason: Define durable agent characters and actor/model candidates before package routing, tool authority, persistent assistants, or workbench launch paths.

## Authority Boundary
- `runtime_authority`: `false`
- `activation_allowed`: `false`
- `backend_execution_authorized`: `false`
- `external_tool_authority`: `false`
- `credential_authority`: `false`
- `agent_self_authority`: `false`
- `persistent_agent_claimed_live`: `false`
- `always_on_assistant_claimed_live`: `false`
- `model_api_called`: `false`
- `agent_activated`: `false`
- `tool_protocol_activated`: `false`
- `browser_oauth_account_access_enabled`: `false`
- `gmail_calendar_coupa_telegram_enabled`: `false`
- `send_submit_approval_enabled`: `false`
- `network_execution_enabled`: `false`
- `hidden_memory_capture_enabled`: `false`
- `background_surveillance_enabled`: `false`
- `broad_file_indexing_enabled`: `false`
- `pc_c_drive_artifact_write_allowed`: `false`
- `mission_control_app_authority_added`: `false`
