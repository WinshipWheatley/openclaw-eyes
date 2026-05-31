# OpenClaw Event Bridge Contract

- Status: DETERMINISTIC_HOT_PATH_EVENT_BRIDGE_CONTRACT_NO_EXECUTION
- Hot path: Mac app, Telegram, PC service, and system events share one event envelope.
- Cold path: Change Sentinel observes bridge health/drift; it is not in the event routing loop.
- Telegram: compact surface only; it emits the same structured workflow payload shape.
- Stale cards: expired or superseded events are rejected and point to the current action.
- Authority: `no_*` fields are prohibition flags; `*_allowed` fields are authority grants.
- Authority boundary: no email, Gmail, browser, Coupa, ledger, workbook cell read, PDF export, printing, model call, or production mutation authority is granted.
- Authority profile: event_bridge_finance_workflow_action_v0.

## Contract Shape

- Event fields: authority_semantics_version, authority_profile_ref, positive_occupation_template_ref, event_id, event_kind, source_channel, client_ref, workflow_ref, world_ref, thread_ref, actor_ref, idempotency_key, created_at, expires_at, correlation_id, parent_event_id, payload, safety_flags, authority_boundary, expected_response_kind, result_receipt_required, no_email_send, no_gmail, no_browser, no_ledger_post, no_coupa, no_workbook_cell_read, no_physical_printing
- Response fields: response_id, event_id, correlation_id, route_status, workflow_status, operator_copy, structured_actions, receipt_refs, next_expected_event, error_code, error_message, retry_allowed, stale_event, superseded_by_event_id
- Response scope fields: client_ref, workflow_ref, world_ref, thread_ref, source_channel, actor_ref

## Registered Hot-Path Actions
- invoice_review_action_request.live_arts_md: prepare_selected_invoice_pdf_artifact -> ROUTE_TO_WORKFLOW_ACTION
- selected_invoice_pdf_export_completed_candidate.live_arts_md: selected_invoice_pdf_export_completed_candidate -> REPORT_RESULT_CANDIDATE
- invoice_review_action_request.capital_hilton: start_invoice_record_selection -> ROUTE_TO_WORKFLOW_ACTION

## Readiness

- READY for contract-level Mac/Telegram parity and deterministic validation.
- NOT a live-service rollout; no service start or production mutation is included.
