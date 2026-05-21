# Model Selection Receipt Contract v0

## Operator Summary
OpenClaw now has a deterministic receipt grammar for actor/model choice. It proves why a package selected, blocked, deferred, escalated, or failed closed for a model class. It does not call models, activate agents, or grant dispatch authority.

## Decision Types
- `MODEL_SELECTED`: Future state: a model class is selected by policy and receipts, without implying a current call.
- `MODEL_BLOCKED`: Policy blocks model selection.
- `MODEL_DEFERRED`: Model selection is plausible later but prerequisites are missing.
- `MODEL_ESCALATED_TO_OPERATOR`: Human operator must decide or approve.
- `MODEL_ESCALATED_TO_GUARDIAN`: Guardian gate must review sensitive/protected posture.
- `MODEL_REQUIRES_REDACTION`: Context must be redacted/reference-only before selection.
- `MODEL_REQUIRES_LOCAL_ONLY`: Context requires local/private handling or blocking.
- `MODEL_REQUIRES_PACKAGE_RECOMPILE`: Package lacks required model-selection inputs.
- `MODEL_REQUIRES_MEMORY_SCOPE_REVIEW`: Memory/context scope must be reviewed first.
- `MODEL_REQUIRES_TOOL_GATE_REVIEW`: Requested adapters need registry/gate review first.
- `MODEL_POLICY_CONFLICT`: Inputs conflict with model policy.
- `MODEL_UNKNOWN_FAIL_CLOSED`: Unknown or incomplete inputs fail closed.

## Selection States
- `SELECTION_REQUESTED`: A package requested a model-selection decision.
- `POLICY_INPUTS_COLLECTED`: Required policy inputs have been collected.
- `SENSITIVITY_CLASSIFIED`: Sensitivity has been classified.
- `MEMORY_SCOPE_CHECKED`: Memory scope has been checked.
- `TOOL_ADAPTERS_CHECKED`: Tool adapter posture has been checked.
- `ACTOR_ELIGIBILITY_CHECKED`: Actor eligibility has been checked.
- `MODEL_CLASS_EVALUATED`: Requested model class has been evaluated.
- `GATES_IDENTIFIED`: Operator/Guardian/tool/memory gates have been identified.
- `RECEIPT_READY`: Receipt has enough fields for review.
- `SELECTION_ALLOWED_PREVIEW_ONLY`: Selection may be shown as preview only; no dispatch.
- `SELECTION_BLOCKED`: Selection is blocked.
- `SELECTION_DEFERRED`: Selection is deferred until future gates/proof exist.
- `SELECTION_ESCALATED`: Selection is escalated to operator or Guardian.
- `SELECTION_REVOKED`: Selection receipt has been revoked.
- `SELECTION_QUARANTINED`: Selection receipt is quarantined.
- `UNKNOWN_FAIL_CLOSED`: Selection cannot be trusted and fails closed.

## Model Classes
- `local_small_fast`: `metadata_only_future_eligible_no_local_call`; ceiling `INTERNAL_SYSTEM`.
- `local_reasoning`: `metadata_only_future_eligible_no_local_call`; ceiling `CREATIVE_PRIVATE`.
- `local_sensitive`: `metadata_only_future_eligible_no_local_call`; ceiling `LEGAL_OR_COMPLIANCE`.
- `external_fast_worker`: `blocked_no_external_model_call`; ceiling `PUBLIC_OR_LOW`.
- `external_deep_reasoner`: `blocked_no_external_model_call`; ceiling `PUBLIC_OR_LOW`.
- `external_code_worker`: `blocked_no_external_model_call`; ceiling `INTERNAL_SYSTEM`.
- `external_multimodal`: `blocked_no_external_model_call`; ceiling `PUBLIC_OR_LOW`.
- `human_operator`: `human_decision_authority_only`; ceiling `UNKNOWN_SENSITIVE_FAIL_CLOSED`.
- `blocked_no_model`: `active_safe_default`; ceiling `UNKNOWN_SENSITIVE_FAIL_CLOSED`.

## Receipt Fields
- `model_selection_receipt_id`
- `package_id`
- `package_type`
- `actor_id`
- `agent_character`
- `requested_model_class`
- `selected_model_class`
- `decision_type`
- `selection_state`
- `selection_reason`
- `policy_version`
- `actor_router_reference`
- `model_policy_reference`
- `package_preview_reference`
- `memory_scope_reference`
- `memory_candidate_receipt_refs`
- `tool_adapter_registry_reference`
- `requested_tool_adapters`
- `allowed_tool_adapters`
- `blocked_tool_adapters`
- `sensitivity`
- `context_included_refs`
- `context_excluded_refs`
- `redaction_status`
- `operator_gate_status`
- `guardian_gate_status`
- `external_model_allowed`
- `local_model_required`
- `retention_policy`
- `authority_level_required`
- `authority_level_granted`
- `runtime_dispatch_allowed`
- `model_call_performed`
- `blocked_reasons`
- `stop_conditions`
- `receipt_requirements`
- `created_at`
- `expires_or_review_after`
- `revocation_status`
- `quarantine_status`
- `receipt_hash`
- `what_would_make_selection_valid`
- `what_keeps_selection_blocked`

## Actor Model Posture
- `operator_winship` as Operator / Winship: current live model `human_operator`; future eligible human_operator.
- `chief` as Chief: current live model `blocked_no_model`; future eligible local_reasoning, external_deep_reasoner.
- `guardian` as Guardian: current live model `blocked_no_model`; future eligible local_sensitive, local_reasoning.
- `cassandra` as Cassandra: current live model `blocked_no_model`; future eligible local_sensitive, local_reasoning.
- `hermes` as Hermes: current live model `blocked_no_model`; future eligible local_reasoning, external_deep_reasoner.
- `niles` as Niles: current live model `blocked_no_model`; future eligible local_reasoning, external_multimodal, external_deep_reasoner.
- `codex` as Codex: current live model `blocked_no_model`; future eligible external_code_worker, local_reasoning.
- `gemini_antigravity` as Gemini / Antigravity: current live model `blocked_no_model`; future eligible external_fast_worker, external_code_worker, external_deep_reasoner, external_multimodal.

## Package Binding
- package preview exists
- actor/agent is known
- model policy exists
- memory scope permits included context
- sensitivity is classified
- requested tools/adapters are known and allowed or explicitly blocked
- Guardian/Operator gates are identified
- receipt requirements exist
- stop conditions exist
- runtime authority is explicit and currently false unless future-approved

## Mission Control Guidance
- Show requested/selected-or-blocked model class, actor, sensitivity, gates, blocked reasons, and what would make selection valid.
- Hide model launch controls, provider credential prompts, browser/OAuth prompts, hidden routing, and agent-self-selected claims.

## Stable Map Integration
- Summary included in stable map now: `false`
- Next requirement: Include this summary in the next stable map bundle refresh after this contract lands.

## Authority Boundary
- `runtime_authority`: `false`
- `model_call_authority`: `false`
- `model_api_execution_authority`: `false`
- `model_router_runtime_authority`: `false`
- `agent_activation_authority`: `false`
- `tool_execution_authority`: `false`
- `external_api_access_authority`: `false`
- `browser_oauth_account_access_enabled`: `false`
- `gmail_calendar_coupa_telegram_enabled`: `false`
- `credential_authority`: `false`
- `send_submit_approval_enabled`: `false`
- `network_execution_enabled`: `false`
- `runtime_daemon_enabled`: `false`
- `planner_builder_execution_enabled`: `false`
- `queue_autonomy_execution_enabled`: `false`
- `hidden_model_routing_enabled`: `false`
- `hidden_memory_capture_enabled`: `false`
- `external_retained_memory_enabled`: `false`
- `raw_private_body_ingestion_enabled`: `false`
- `vector_memory_expansion_enabled`: `false`
- `broad_filesystem_indexing_enabled`: `false`
- `repo_b_mutation_enabled`: `false`
- `mission_control_app_authority_added`: `false`
- `mac_sync_or_import_triggered`: `false`
- `pc_c_drive_artifact_write_allowed`: `false`
- `operator_final_authority`: `true`

## Next Lanes
- `package_preview_receipt_v0` (P1): Package Preview Receipt v0
- `tool_adapter_receipt_v0` (P1): Tool Adapter Receipt v0
- `memory_review_promotion_surface_v0` (P2): Memory Review / Promotion Surface v0
- `mission_control_package_preview_actor_routing_surface_v0` (P2): Mission Control Package Preview / Actor Routing Surface v0
- `model_router_implementation_plan_v0` (P3): Model Router Implementation Plan v0
