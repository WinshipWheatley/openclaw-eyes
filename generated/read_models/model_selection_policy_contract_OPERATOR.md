# Model Selection Policy Contract v0

## Operator Summary
OpenClaw now has a deterministic model-selection policy. It can say which model class would be appropriate, future-eligible, or blocked for an actor/package, but it cannot call any model. The safest valid answer remains blocked_no_model.

## Model Classes
- `local_small_fast`: Local Small Fast — Fast local/private triage, summarization, low-risk classification, and draft wording. (current authority: `recommendation_only_no_local_model_call`).
- `local_reasoning`: Local Reasoning — Private deeper reasoning on internal OpenClaw context when external exposure is not justified. (current authority: `recommendation_only_no_local_model_call`).
- `local_sensitive`: Local Sensitive — Private/offline handling posture for sensitive, finance, client, legal, and protected metadata work. (current authority: `recommendation_only_no_local_model_call`).
- `external_fast_worker`: External Fast Worker — Future fast external review for low-sensitivity, bounded packages with explicit preview and receipts. (current authority: `blocked_no_external_model_call`).
- `external_deep_reasoner`: External Deep Reasoner — Future high-depth external reasoning for non-sensitive architecture, doctrine, and synthesis. (current authority: `blocked_no_external_model_call`).
- `external_code_worker`: External Code Worker — Future scoped code/test worker for repo-safe implementation packages. (current authority: `blocked_no_external_model_call`).
- `external_multimodal`: External Multimodal — Future visual/audio/document interpretation for sanitized media or UI proof packages. (current authority: `blocked_no_external_model_call`).
- `human_operator`: Human Operator — Final human authority, taste judgment, approval/denial, and memory comparison. (current authority: `human_decision_authority_only`).
- `blocked_no_model`: Blocked / No Model — Safe fail-closed result when sensitivity, missing package fields, missing gates, or unclear authority blocks model choice. (current authority: `active_safe_default`).

## Actor / Model Rules
- `operator_winship`: current `human_operator`; future-eligible `human_operator`; Guardian gate `false`.
- `chief`: current `blocked_no_model`; future-eligible `local_reasoning`, `external_deep_reasoner`, `local_small_fast`; Guardian gate `false`.
- `guardian`: current `blocked_no_model`; future-eligible `local_sensitive`, `local_reasoning`; Guardian gate `true`.
- `cassandra`: current `blocked_no_model`; future-eligible `local_sensitive`, `local_reasoning`, `external_deep_reasoner`; Guardian gate `true`.
- `hermes`: current `blocked_no_model`; future-eligible `local_reasoning`, `external_deep_reasoner`, `local_small_fast`; Guardian gate `false`.
- `niles`: current `blocked_no_model`; future-eligible `local_small_fast`, `external_multimodal`, `external_deep_reasoner`; Guardian gate `false`.
- `codex`: current `blocked_no_model`; future-eligible `external_code_worker`, `local_reasoning`; Guardian gate `false`.
- `gemini_antigravity`: current `blocked_no_model`; future-eligible `external_fast_worker`, `external_code_worker`, `external_deep_reasoner`; Guardian gate `false`.

## Sensitivity Boundaries
- Unknown sensitivity defaults to `unknown_fail_closed`.
- Credentials/OAuth defaults to `blocked_no_model`.
- External model use is future-eligible only after explicit preview, classification, gates, and receipts.

## Blocked Model Uses
- `email_send`: Sending email is blocked; Cassandra communication work remains review/visibility until a later gate.
- `calendar_mutation`: Calendar mutation is blocked; calendar work may be reviewed only through approved metadata.
- `browser_coupa_portal_use`: Browser, Coupa, portal, and account flows are blocked before explicit protected-access gates.
- `credential_or_oauth_handling`: Credentials, OAuth tokens, secrets, and account setup cannot be handled by model selection.
- `protected_file_access_without_gate`: Protected files or private bodies cannot be exposed without Guardian/protected-context proof.
- `broad_filesystem_indexing`: Broad filesystem indexing is blocked; source inventories must stay bounded and approved.
- `hidden_memory_capture`: Hidden memory capture is blocked; memory surfaces must be explicit and receipt-backed.
- `surveillance_background_monitoring`: Background surveillance or always-on monitoring is not authorized by this contract.
- `autonomous_tool_execution`: Autonomous tool execution is blocked; model selection is metadata-only.
- `self_authorized_routing`: No model or actor may choose its own authority, clearance, workspace, or tool set.
- `external_model_sensitive_data_without_gate`: External model use on sensitive/private/protected data is blocked without explicit Operator and Guardian gates.

## Mission Control Guidance
- Top layer: Recommended model posture
- Middle layer: Why this model class fits, why other classes are blocked, and what gates are missing.
- Lower layer: Package sensitivity, actor fit, proof refs, Guardian/Operator gates, and receipt requirements.
- Do not imply models are currently callable.
- Show `blocked_no_model` as a safe, valid result.

## Next Lanes
- `agent_package_preview_contract_v0` (P1): Agent Package Preview Contract v0
- `agent_memory_scope_contract_v0` (P1): Agent Memory Scope Contract v0
- `tool_protocol_adapter_registry_v0` (P2): Tool Protocol Adapter Registry v0
- `mission_control_actor_routing_surface_v0` (P2): Mission Control Actor Routing Surface v0
- `model_selection_receipt_v0` (P3): Model Selection Receipt v0

## Authority Boundary
- `runtime_authority`: `false`
- `model_call_authority`: `false`
- `external_model_authority`: `false`
- `local_model_authority`: `false`
- `tool_execution_authority`: `false`
- `credential_authority`: `false`
- `routing_execution_authority`: `false`
- `operator_final_authority`: `true`
- `browser_oauth_account_access_enabled`: `false`
- `gmail_calendar_coupa_telegram_enabled`: `false`
- `send_submit_approval_enabled`: `false`
- `network_execution_enabled`: `false`
- `runtime_daemon_enabled`: `false`
- `autonomous_routing_enabled`: `false`
- `hidden_memory_capture_enabled`: `false`
- `background_surveillance_enabled`: `false`
- `pc_c_drive_artifact_write_allowed`: `false`
- `mission_control_app_authority_added`: `false`
