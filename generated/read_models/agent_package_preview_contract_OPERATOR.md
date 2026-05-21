# Agent Package Preview Contract v0

## Operator Summary
OpenClaw now has a deterministic package-preview contract. Mission Control can show what would be sent, to whom, why, which context is included/excluded, what gates are required, and what remains blocked before any future model, agent, tool, or runtime action.

## Package Preview Layers
- Top layer: what would be sent, to whom, and why
- Middle layer: what context/evidence is included and excluded
- Lower layer: gates, authority, proof, and receipts
- Full inspection: complete package preview payload

## Required Package Fields
- `package_id`
- `package_type`
- `proposed_actor_id`
- `proposed_actor_role`
- `proposed_model_class`
- `model_selection_status`
- `task_summary`
- `operator_intent`
- `evidence_sources`
- `included_context_refs`
- `excluded_context_refs`
- `sensitivity_classification`
- `clearance_level`
- `requested_authority`
- `blocked_authority`
- `required_gates`
- `relevant_capabilities`
- `inactive_tool_protocols`
- `expected_outputs`
- `stop_conditions`
- `validation_requirements`
- `future_pre_action_receipts`
- `future_post_action_receipts`
- `mission_control_display_layers`

## Example Package Previews
- `example_codex_backend_read_model_implementation`: Codex backend read-model implementation package -> actor `codex`, model `external_code_worker`, authority `inspect_only`.
- `example_gemini_antigravity_refactor_proof`: Gemini/Antigravity refactor/proof package -> actor `gemini_antigravity`, model `external_fast_worker`, authority `review_only`.
- `example_cassandra_capital_hilton_invoice_review`: Cassandra Capital Hilton invoice review package -> actor `cassandra`, model `local_sensitive`, authority `blocked`.
- `example_guardian_protected_evidence_review`: Guardian protected evidence review package -> actor `guardian`, model `local_sensitive`, authority `inspect_only`.
- `example_niles_struna_tracking_creative`: Niles Struna tracking/creative package -> actor `niles`, model `external_multimodal`, authority `review_only`.
- `example_hermes_architecture_review`: Hermes architecture review package -> actor `hermes`, model `external_deep_reasoner`, authority `review_only`.
- `example_chief_check_engine_diagnostic`: Chief check-engine diagnostic package -> actor `chief`, model `local_reasoning`, authority `inspect_only`.

## Context And Sensitivity Boundary
- Include refs, receipts, source cards, and context packet refs; do not include raw private bodies by default.
- Block `hidden_memory`.
- Block `broad_filesystem_indexing`.
- Block `private_raw_body_ingestion`.
- Block `credential_or_token_inclusion`.
- Block `browser_or_session_cookies`.
- Block `unredacted_client_legal_finance_private_documents`.
- Block `home_bank_check_remit_sensitive_raw_data`.
- Block `email_calendar_raw_bodies_without_gate`.
- Block `tool_outputs_without_receipts`.

## Authority Boundary
- `runtime_authority`: `false`
- `model_call_authority`: `false`
- `agent_call_authority`: `false`
- `tool_execution_authority`: `false`
- `external_tool_authority`: `false`
- `credential_authority`: `false`
- `routing_execution_authority`: `false`
- `package_send_authority`: `false`
- `operator_final_authority`: `true`
- `browser_oauth_account_access_enabled`: `false`
- `gmail_calendar_coupa_telegram_enabled`: `false`
- `send_submit_approval_enabled`: `false`
- `network_execution_enabled`: `false`
- `runtime_daemon_enabled`: `false`
- `autonomous_routing_enabled`: `false`
- `raw_private_body_ingestion_enabled`: `false`
- `hidden_memory_capture_enabled`: `false`
- `background_surveillance_enabled`: `false`
- `pc_c_drive_artifact_write_allowed`: `false`
- `mission_control_app_authority_added`: `false`

## Next Lanes
- `agent_memory_scope_contract_v0` (P1): Agent Memory Scope Contract v0
- `tool_protocol_adapter_registry_v0` (P1): Tool Protocol Adapter Registry v0
- `model_selection_receipt_v0` (P2): Model Selection Receipt v0
- `mission_control_actor_routing_surface_v0` (P2): Mission Control Actor Routing Surface v0
- `package_preview_receipt_v0` (P3): Package Preview Receipt v0
