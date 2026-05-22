# Package Preview Receipt Contract v0

## Summary

OpenClaw now has a deterministic receipt grammar proving that a mission package was compiled, bounded, checked, and displayable without dispatching it.

## Receipt Grammar

- Receipt types: `14`
- Preview states: `19`
- Required fields: `56`
- `PREVIEW_READY` means displayable, not executable.
- Runtime dispatch, model calls, tool execution, agent activation, queue execution, account access, and send/submit/approval all default to `false`.

## Example Package Previews

- `cassandra_capital_hilton_invoice_review`: Cassandra Capital Hilton Invoice Review -> `PACKAGE_PREVIEW_NEEDS_PROOF`
  - actor: `cassandra` / model posture: `blocked_no_model`
  - blocked: `GUARDIAN_GATE_REQUIRED, OPERATOR_APPROVAL_REQUIRED, PROTECTED_PROOF_MISSING, ACCOUNT_ACCESS_BLOCKED`
- `chief_check_engine_diagnostic`: Chief Check Engine Diagnostic -> `PACKAGE_PREVIEW_COMPILED`
  - actor: `chief` / model posture: `blocked_no_model`
  - blocked: `RUNTIME_REPAIR_BLOCKED`
- `guardian_protected_evidence_review`: Guardian Protected Evidence Review -> `PACKAGE_PREVIEW_NEEDS_GUARDIAN_GATE`
  - actor: `guardian` / model posture: `blocked_no_model`
  - blocked: `RAW_PRIVATE_CONTEXT_BLOCKED, GUARDIAN_GATE_REQUIRED`
- `niles_struna_creative_metadata_review`: Niles / Struna Creative Metadata Review -> `PACKAGE_PREVIEW_NEEDS_PROOF`
  - actor: `niles` / model posture: `blocked_no_model`
  - blocked: `MISSING_PROJECT_PROOF, BROAD_ARCHIVE_INGESTION_BLOCKED`
- `hermes_architecture_doctrine_review`: Hermes Architecture Doctrine Review -> `PACKAGE_PREVIEW_COMPILED`
  - actor: `hermes` / model posture: `blocked_no_model`
  - blocked: `CANONICAL_MEMORY_PROMOTION_BLOCKED`
- `codex_backend_contract_implementation`: Codex Backend Contract Implementation -> `PACKAGE_PREVIEW_FUTURE_GATED`
  - actor: `codex` / model posture: `blocked_no_model`
  - blocked: `OPENCLAW_RUNTIME_DISPATCH_BLOCKED, NETWORK_CREDENTIAL_SCOPE_BLOCKED`
- `gemini_antigravity_visual_polish`: Gemini / Antigravity Visual Polish Package -> `PACKAGE_PREVIEW_FUTURE_GATED`
  - actor: `gemini_antigravity` / model posture: `blocked_no_model`
  - blocked: `EXTERNAL_RETENTION_BLOCKED, OPERATOR_APPROVAL_REQUIRED`
- `agentic_loop_classification`: Agentic Loop Classification Package -> `PACKAGE_PREVIEW_NEEDS_CONTEXT`
  - actor: `chief` / model posture: `blocked_no_model`
  - blocked: `REPO_B_DISCOVERY_NEEDED, AUTONOMY_BLOCKED, NO_EXECUTION_AUTHORITY`

## Mission Control Guidance

- Show mission, actor, package type, preview status, authority boundary, included/excluded context counts, missing proof, gates, stop conditions, and receipt requirements.
- Route full inspection into operator orientation, machine proof, and future action path layers.
- Hide live dispatch, model launch, tool execution, browser/OAuth/account prompts, Gmail/calendar/Coupa/Telegram controls, send/submit/approval, raw private context, credentials, fake confidence percentages, and self-authorized package claims.

## Stable Map

- Summary included now: `false`
- Next stable-map refresh should include `package_preview_receipt_contract` summary.

## Boundary

- `runtime_authority` = `False`
- `live_dispatch_authority` = `False`
- `model_call_authority` = `False`
- `model_api_execution_authority` = `False`
- `model_router_runtime_authority` = `False`
- `actor_agent_activation_authority` = `False`
- `tool_execution_authority` = `False`
- `queue_autonomy_execution_authority` = `False`
- `planner_builder_execution_authority` = `False`
- `browser_oauth_account_access_enabled` = `False`
- `gmail_calendar_coupa_telegram_enabled` = `False`
- `credential_authority` = `False`
- `send_submit_approval_enabled` = `False`
- `raw_private_body_ingestion_enabled` = `False`
- `external_retained_memory_enabled` = `False`
- `hidden_model_routing_enabled` = `False`
- `hidden_memory_capture_enabled` = `False`
- `vector_memory_expansion_enabled` = `False`
- `broad_filesystem_indexing_enabled` = `False`
- `repo_b_mutation_enabled` = `False`
- `repo_b_body_inspection_enabled` = `False`
- `mission_control_app_authority_added` = `False`
- `mac_sync_or_import_triggered` = `False`
- `network_operation_enabled` = `False`
- `pc_c_drive_artifact_write_allowed` = `False`
- `operator_final_authority` = `True`
