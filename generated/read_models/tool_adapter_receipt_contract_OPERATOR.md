# Tool Adapter Receipt Contract v0

## Summary

OpenClaw now has a deterministic receipt grammar for tool/protocol adapter lookup, allow, block, quarantine, and future-gate decisions. It proves adapter posture without executing tools.

## Receipt Grammar

- Receipt types: `15`
- Receipt states: `20`
- Capability classes: `20`
- Required fields: `65`
- `ADAPTER_ALLOWED_READ_ONLY` means deterministic readback/static metadata only, not runtime execution.
- Tool execution, network/account/browser access, send/submit/approval, command execution, model calls, agent activation, and queue execution default to `false`.

## Example Adapter Receipts

- `stable_map_bundle_reader`: Stable Map Bundle Reader -> `ADAPTER_ALLOWED_READ_ONLY_RECEIPT`
  - capability: `READ_METADATA` / granted: `READ_METADATA` / blocked: `None`
  - blocked reasons: ``
- `package_preview_exporter`: Package Preview Exporter -> `ADAPTER_ALLOWED_PREVIEW_ONLY_RECEIPT`
  - capability: `RECEIPT_WRITE` / granted: `RECEIPT_WRITE` / blocked: `None`
  - blocked reasons: ``
- `codex_scoped_build_verifier`: Codex Scoped Build Verifier -> `ADAPTER_FUTURE_GATED_RECEIPT`
  - capability: `RUN_TEST` / granted: `None` / blocked: `RUN_TEST`
  - blocked reasons: `COMMAND_EXECUTION_BLOCKED, RUNTIME_AUTHORITY_BLOCKED`
- `cassandra_capital_hilton_invoice_proof_adapter`: Cassandra Capital Hilton Invoice Proof Adapter -> `ADAPTER_NEEDS_GUARDIAN_GATE_RECEIPT`
  - capability: `READ_REDACTED_CONTENT` / granted: `None` / blocked: `READ_REDACTED_CONTENT`
  - blocked reasons: `GUARDIAN_GATE_REQUIRED, ACCOUNT_ACCESS_BLOCKED, CREDENTIAL_MATERIAL_BLOCKED`
- `guardian_protected_access_gate`: Guardian Protected Access Gate -> `ADAPTER_ALLOWED_PREVIEW_ONLY_RECEIPT`
  - capability: `READ_METADATA` / granted: `READ_METADATA` / blocked: `None`
  - blocked reasons: ``
- `chief_test_harness_adapter`: Chief Test Harness Adapter -> `ADAPTER_FUTURE_GATED_RECEIPT`
  - capability: `RUN_TEST` / granted: `None` / blocked: `RUN_TEST`
  - blocked reasons: `COMMAND_EXECUTION_BLOCKED, RUNTIME_AUTHORITY_BLOCKED`
- `browser_oauth_adapter`: Browser / OAuth Adapter -> `ADAPTER_NEEDS_SECURITY_AUDIT_RECEIPT`
  - capability: `BROWSER_SESSION` / granted: `None` / blocked: `BROWSER_SESSION`
  - blocked reasons: `BROWSER_SESSION_BLOCKED, ACCOUNT_ACCESS_BLOCKED, SECURITY_AUDIT_REQUIRED`
- `gmail_calendar_adapter`: Gmail / Calendar Adapter -> `ADAPTER_NEEDS_SECURITY_AUDIT_RECEIPT`
  - capability: `MUTATE_ACCOUNT` / granted: `None` / blocked: `MUTATE_ACCOUNT`
  - blocked reasons: `ACCOUNT_ACCESS_BLOCKED, SEND_SUBMIT_APPROVAL_BLOCKED, RAW_PRIVATE_BODY_BLOCKED`
- `coupa_adapter`: Coupa Adapter -> `ADAPTER_NEEDS_SECURITY_AUDIT_RECEIPT`
  - capability: `MUTATE_ACCOUNT` / granted: `None` / blocked: `MUTATE_ACCOUNT`
  - blocked reasons: `ACCOUNT_ACCESS_BLOCKED, CREDENTIAL_MATERIAL_BLOCKED, SEND_SUBMIT_APPROVAL_BLOCKED`
- `telegram_adapter`: Telegram Adapter -> `ADAPTER_BLOCKED_RECEIPT`
  - capability: `SEND_MESSAGE` / granted: `None` / blocked: `SEND_MESSAGE`
  - blocked reasons: `SEND_SUBMIT_APPROVAL_BLOCKED, ACCOUNT_ACCESS_BLOCKED`
- `repo_b_planner_builder_adapter`: Repo B Planner / Builder Adapter -> `ADAPTER_FUTURE_GATED_RECEIPT`
  - capability: `QUEUE_EXECUTION` / granted: `None` / blocked: `QUEUE_EXECUTION`
  - blocked reasons: `UNKNOWN_ADAPTER, RUNTIME_AUTHORITY_BLOCKED, COMMAND_EXECUTION_BLOCKED`
- `memory_candidate_receipt_writer`: Memory Candidate Receipt Writer -> `ADAPTER_RECEIPT_ONLY_RECEIPT`
  - capability: `MEMORY_CANDIDATE_WRITE` / granted: `MEMORY_CANDIDATE_WRITE` / blocked: `None`
  - blocked reasons: ``

## Mission Control Guidance

- Show adapter name, package, actor, capability requested/granted/blocked, gates, blocked reasons, output receipt shape, and what would make it available later.
- In package preview, group requested, allowed, blocked, and future-gated adapters with required receipts and stop conditions.
- Hide live tool execution, browser/OAuth launch, Gmail/calendar/Coupa/Telegram controls, credential/account prompts, send/submit/approval, arbitrary commands, raw private context, and self-authorized adapter claims.

## Stable Map

- Summary included now: `false`
- Next stable-map refresh should include `tool_adapter_receipt_contract` summary.

## Boundary

- `runtime_authority` = `False`
- `tool_execution_authority` = `False`
- `live_tool_execution` = `False`
- `model_call_authority` = `False`
- `model_api_execution_authority` = `False`
- `model_router_runtime_authority` = `False`
- `actor_agent_activation_authority` = `False`
- `browser_oauth_account_access_enabled` = `False`
- `gmail_calendar_coupa_telegram_enabled` = `False`
- `credential_authority` = `False`
- `send_submit_approval_enabled` = `False`
- `queue_autonomy_execution_enabled` = `False`
- `planner_builder_execution_enabled` = `False`
- `runtime_daemon_enabled` = `False`
- `arbitrary_command_execution_enabled` = `False`
- `network_operation_enabled` = `False`
- `file_mutation_authority` = `False`
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
- `pc_c_drive_artifact_write_allowed` = `False`
- `adapter_self_authority_allowed` = `False`
- `operator_final_authority` = `True`
