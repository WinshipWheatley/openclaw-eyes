# Tool Protocol Adapter Registry Contract v0

## Operator Summary
OpenClaw now has a deterministic tool/protocol adapter registry. It lists which adapters are read-only, preview-only, receipt-only, candidate, future-gated, blocked, or quarantined before any runtime wiring. Tools are not authority by themselves; packages must satisfy actor, model, memory, Guardian, Operator, and receipt gates before future use.

## Adapter States
- `ACTIVE_READ_ONLY`: Adapter may inspect deterministic metadata/proof refs in bounded scope.
- `ACTIVE_PREVIEW_ONLY`: Adapter may produce preview metadata or draft-only package content.
- `RECEIPT_ONLY`: Adapter may define or validate metadata receipts without executing the underlying action.
- `CANDIDATE_UNMAPPED`: Adapter is named as possible future terrain but lacks sufficient mapping.
- `FUTURE_GATED`: Adapter may be useful later but needs security, operator, Guardian, and receipt gates.
- `BLOCKED_SENSITIVE`: Adapter touches sensitive/protected/account material and is blocked now.
- `BLOCKED_NO_AUTHORITY`: No current authority exists for this adapter class.
- `BLOCKED_NO_RECEIPT`: Adapter lacks required receipt shape.
- `BLOCKED_NO_GUARDIAN_GATE`: Adapter needs Guardian protected-access review before future use.
- `BLOCKED_NO_OPERATOR_APPROVAL`: Adapter needs explicit operator approval before future use.
- `QUARANTINED`: Adapter is isolated due to contradiction, leakage, authority drift, or malformed proof.
- `RETIRED`: Adapter is intentionally inactive and should not be offered.
- `UNKNOWN_FAIL_CLOSED`: Adapter status cannot be trusted.

## Current Authority Matrix
### Allowed Now
- read-model inspection
- stable map inspection
- deterministic package preview
- contract export
- focused test/build verification in bounded worker tasks
- receipt-only metadata generation
- static validation
- forbidden-authority scans
- proof/reference display

### Blocked Now
- live browser/OAuth/account flows
- Gmail/calendar/Coupa/Telegram access
- credentials/tokens/cookies
- autonomous sends/submits/approvals
- live model calls from OpenClaw runtime
- agent launch/runtime daemon
- planner/builder execution
- queue/autonomy execution
- arbitrary shell execution
- broad filesystem indexing
- raw private body ingestion
- external retained memory
- hidden monitoring
- PC C-drive artifact writes
- file delete/move authority
- broad repair/remount authority

## Adapter Examples
- `generated_read_model_reader`: `ACTIVE_READ_ONLY`; category `read_model_stable_map`; sensitivity `internal_operator_safe`.
- `stable_map_bundle_reader`: `ACTIVE_READ_ONLY`; category `read_model_stable_map`; sensitivity `internal_operator_safe`.
- `receipt_reader`: `ACTIVE_READ_ONLY`; category `read_model_stable_map`; sensitivity `internal_operator_safe`.
- `proof_reference_reader`: `ACTIVE_READ_ONLY`; category `read_model_stable_map`; sensitivity `protected_reference_only`.
- `scoped_repo_file_reader`: `ACTIVE_READ_ONLY`; category `local_code_workspace`; sensitivity `internal_operator_safe`.
- `scoped_code_patch_proposal`: `ACTIVE_PREVIEW_ONLY`; category `local_code_workspace`; sensitivity `internal_operator_safe`.
- `focused_test_runner`: `ACTIVE_PREVIEW_ONLY`; category `local_code_workspace`; sensitivity `internal_operator_safe`.
- `bounded_build_verifier`: `ACTIVE_PREVIEW_ONLY`; category `local_code_workspace`; sensitivity `internal_operator_safe`.
- `package_compiler`: `ACTIVE_PREVIEW_ONLY`; category `package_compiler`; sensitivity `internal_operator_safe`.
- `package_preview_exporter`: `ACTIVE_PREVIEW_ONLY`; category `package_compiler`; sensitivity `internal_operator_safe`.
- `package_receipt_validator`: `RECEIPT_ONLY`; category `package_compiler`; sensitivity `internal_operator_safe`.
- `memory_candidate_receipt_generator`: `RECEIPT_ONLY`; category `package_compiler`; sensitivity `operator_memory_candidate`.
- `model_selection_receipt_generator`: `RECEIPT_ONLY`; category `package_compiler`; sensitivity `internal_operator_safe`.
- `finance_invoice_proof_metadata_adapter`: `FUTURE_GATED`; category `domain_workflow`; sensitivity `finance_or_ap_sensitive`.
- `cassandra_capital_hilton_invoice_proof_adapter`: `FUTURE_GATED`; category `domain_workflow`; sensitivity `finance_or_ap_sensitive`.
- `excel_workbook_proof_adapter_candidate`: `FUTURE_GATED`; category `domain_workflow`; sensitivity `finance_or_ap_sensitive`.
- `communications_email_metadata_adapter_candidate`: `FUTURE_GATED`; category `domain_workflow`; sensitivity `sensitive_private`.
- `calendar_metadata_adapter_candidate`: `FUTURE_GATED`; category `domain_workflow`; sensitivity `sensitive_private`.
- `music_art_metadata_adapter`: `ACTIVE_PREVIEW_ONLY`; category `domain_workflow`; sensitivity `internal_operator_safe`.
- `browser_oauth_adapter`: `BLOCKED_NO_AUTHORITY`; category `external_account_browser_api`; sensitivity `credential_or_token`.
- `gmail_calendar_adapter`: `BLOCKED_NO_AUTHORITY`; category `external_account_browser_api`; sensitivity `sensitive_private`.
- `coupa_adapter`: `BLOCKED_SENSITIVE`; category `external_account_browser_api`; sensitivity `finance_or_ap_sensitive`.
- `telegram_adapter`: `BLOCKED_NO_AUTHORITY`; category `external_account_browser_api`; sensitivity `sensitive_private`.
- `web_api_adapter_candidate`: `CANDIDATE_UNMAPPED`; category `external_account_browser_api`; sensitivity `unknown_fail_closed`.
- `planner_adapter_candidate`: `FUTURE_GATED`; category `runtime_agent`; sensitivity `internal_operator_safe`.
- `builder_adapter_candidate`: `FUTURE_GATED`; category `runtime_agent`; sensitivity `internal_operator_safe`.
- `chief_test_harness_adapter`: `FUTURE_GATED`; category `runtime_agent`; sensitivity `internal_operator_safe`.
- `repo_b_planner_builder_adapter`: `CANDIDATE_UNMAPPED`; category `runtime_agent`; sensitivity `unknown_fail_closed`.
- `guardian_protected_access_gate`: `RECEIPT_ONLY`; category `safety_security`; sensitivity `protected_reference_only`.
- `redaction_adapter`: `ACTIVE_PREVIEW_ONLY`; category `safety_security`; sensitivity `protected_reference_only`.
- `secret_scanner`: `ACTIVE_READ_ONLY`; category `safety_security`; sensitivity `internal_operator_safe`.
- `authority_revocation_kill_switch_adapter_candidate`: `CANDIDATE_UNMAPPED`; category `safety_security`; sensitivity `internal_operator_safe`.
- `suspicious_output_quarantine_adapter_candidate`: `CANDIDATE_UNMAPPED`; category `safety_security`; sensitivity `internal_operator_safe`.

## Actor / Adapter Rules
- `operator_winship`: Final human authority; may request context or approve gates, but does not become an adapter. Blocked: operator_is_not_a_tool_adapter.
- `chief`: Chief can inspect and diagnose; no repair or execution authority is granted. Blocked: repair, remount, cleanup/delete, send/account access, self-authorized tools.
- `guardian`: Guardian recommends block/redact/quarantine/revoke and validates gates; it cannot bypass Operator. Blocked: self-authorization, execution bypass, raw secret storage, approval execution.
- `cassandra`: Cassandra handles review posture only until account/protected gates exist. Blocked: Coupa access, Gmail/calendar raw bodies, send/submit/approve, OAuth/session handling.
- `hermes`: Hermes reviews systems/doctrine coherence, not live runtime tools. Blocked: runtime execution, private raw body ingestion, account/tool activation.
- `niles`: Niles receives scoped creative refs only. Blocked: broad private library ingestion, release/upload/account action, unrelated private/client context.
- `codex`: Codex may do scoped implementation work when explicitly prompted; this registry adds no runtime authority. Blocked: credentials, network, arbitrary execution, hidden memory, scope expansion, PC C-drive writes.
- `gemini_antigravity`: Gemini/Antigravity remains package-bounded and cannot write canonical state directly. Blocked: retained memory, broad context, direct canonical writes, raw protected material.

## Package Binding Rule
- adapter exists in registry
- adapter state allows package use
- package type is allowed
- actor is eligible
- model class is eligible
- memory scope permits the context
- sensitivity ceiling is not exceeded
- Guardian gate passes if required
- Operator approval exists if required
- receipt requirements are defined
- stop conditions are explicit

If any requirement fails, package binding fails closed with one of:
- `TOOL_NOT_MAPPED`
- `TOOL_BLOCKED_BY_MEMORY_SCOPE`
- `TOOL_BLOCKED_BY_SENSITIVITY`
- `TOOL_BLOCKED_BY_GUARDIAN_GATE`
- `TOOL_BLOCKED_BY_OPERATOR_APPROVAL`
- `TOOL_BLOCKED_BY_RECEIPT_REQUIREMENT`
- `TOOL_UNKNOWN_FAIL_CLOSED`

## Receipt / Quarantine
- Every future adapter execution must return a receipt.
- Metadata-only receipt definitions are allowed only when they do not claim execution.
- Quarantine is non-destructive and proof-preserving.

## Mission Control Guidance
- Show adapter overview by active, preview-only, future-gated, blocked, and quarantined state.
- In package preview, show tools included/excluded, gates, receipts, and stop conditions.
- Do not show live execute buttons, credential prompts, or account launch controls.

## Stable Map Integration
- Summary included in stable map now: `false`
- Next requirement: Include this summary in the next stable map bundle refresh after this contract lands.

## Operator Field Notes
- `powershell_window_did_not_close`: Operator observed a PowerShell window did not close; treat as bridge/process lifecycle evidence for future Check Transmission or Chief diagnostics, not as repair authority. Action now: none.

## Authority Boundary
- `runtime_authority`: `false`
- `tool_execution_authority`: `false`
- `external_tool_authority`: `false`
- `model_call_authority`: `false`
- `agent_call_authority`: `false`
- `browser_oauth_account_access_enabled`: `false`
- `gmail_calendar_coupa_telegram_enabled`: `false`
- `credential_authority`: `false`
- `send_submit_approval_enabled`: `false`
- `network_execution_enabled`: `false`
- `runtime_daemon_enabled`: `false`
- `planner_builder_execution_enabled`: `false`
- `queue_autonomy_execution_enabled`: `false`
- `raw_private_body_ingestion_enabled`: `false`
- `vector_memory_expansion_enabled`: `false`
- `external_retained_memory_enabled`: `false`
- `broad_filesystem_indexing_enabled`: `false`
- `repo_b_mutation_enabled`: `false`
- `mission_control_app_authority_added`: `false`
- `mac_sync_or_import_triggered`: `false`
- `pc_c_drive_artifact_write_allowed`: `false`
- `adapter_self_authority_allowed`: `false`
- `actor_self_tool_grant_allowed`: `false`
- `operator_final_authority`: `true`

## Next Lanes
- `memory_candidate_receipt_v0` (P1): Memory Candidate Receipt v0
- `model_selection_receipt_v0` (P1): Model Selection Receipt v0
- `package_preview_receipt_v0` (P1): Package Preview Receipt v0
- `mission_control_package_preview_actor_routing_surface_v0` (P2): Mission Control Package Preview / Actor Routing Surface v0
