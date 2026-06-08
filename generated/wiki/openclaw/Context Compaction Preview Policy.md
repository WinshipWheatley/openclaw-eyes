# Context Compaction Preview Policy

Status: CONTEXT_COMPACTION_PREVIEW_POLICY_READY

This policy keeps agent context scoped and high-signal. Large artifacts, raw logs, raw OCR, full history, and stale context are not dumped into agent context by default.

## Context Tiers

- `tier_0_operator_request`: The current operator request, exact explicit constraints, and latest instruction priority.
- `tier_1_current_lane_summary`: Redacted summary of the active world/thread/objective and current known facts.
- `tier_2_current_receipts_and_proof_meters`: Latest receipt refs, proof meter labels, freshness state, and missing input.
- `tier_3_decision_trace_summary`: Relevant attempted path, why it failed, what proof said, operator decision, and what changed.
- `tier_4_preview_snippets`: Short, safe snippets from large logs/artifacts when a preview is needed.
- `tier_5_full_artifact_or_log_reference`: Reference to full artifact/log with hash/path/ref, not embedded content.
- `tier_6_developer_proof_only`: Raw proof, hidden machine contracts, raw logs, and developer-only details.

## Preview Rules

- Large logs, files, and artifacts are not dumped into model context.
- Provide a short preview or snippet first.
- The full artifact remains referenced, not embedded.
- The agent asks or digs only when needed and allowed.
- Raw OCR or artifact text is excluded unless explicitly approved.

## Compaction Rules

- Old controller responses collapse into decision trace.
- Old tool outputs collapse into receipt and proof summaries.
- Stale summaries are demoted.
- Superseded receipts remain historical, not current truth.
- High-signal lessons are preserved.
- Low-signal chatter is archived.

## Agent-Visible Context

Allowed:
- `redacted_current_facts`
- `current_proof_meter_labels`
- `latest_receipt_refs`
- `relevant_decision_trace_summary`
- `missing_input`
- `blocked_action_summary`
- `allowed_next_controls`
- `preview_snippets_only_when_safe`

Forbidden by default:
- `full_logs`
- `raw_file_bodies`
- `raw_email_coupa_gmail_browser_content`
- `raw_ocr_artifact_text`
- `raw_workbook_ledger_bodies`
- `credentials_secrets`
- `operator_device_session_verification_material`
- `full_chat_history_dumps`
- `stale_context_as_current_truth`

## Required Scenarios

- `large_server_error_log`: Show a short error-window preview plus the log ref/hash.
- `local_lm_non_json_postmortem`: Model draft failed JSON shape; fallback receipt published; truth/authority checks were not loosened.
- `finance_payment_watch`: Payment evidence missing; processor processing; ledger untouched; next safe control is attach proof.
- `build_review_history`: Resolved or informational Build review packets are historical support, not active ready-for-review context.
- `niles_creative_mapping`: Creative goal, controller/software target, and allowed mapping context are visible when supplied.
- `remote_desktop_trace_log_leak`: Show resource/blocker summary and validation need; keep raw trace logs behind developer proof.
