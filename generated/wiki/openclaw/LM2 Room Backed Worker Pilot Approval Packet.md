# LM2 Room Backed Worker Pilot Approval Packet

Status: LM2_ROOM_BACKED_WORKER_PILOT_APPROVAL_PACKET_READY
Packet status: pending_operator_review

This packet is not approval and does not run LM2. It prepares a review-only operator decision for one future room-backed LM2 worker pilot.

## Pilot Scope

- Worker class: `lm2_bounded_worker`
- Runtime: `ollama`
- Model: `qwen3:8b-q4_K_M`
- Lane: `finance/capital_hilton`
- Question: What should I do here?
- Mode: `proof_to_response_only`

## Required Room Refs

- `project_room_ref`: `finance_capital_hilton_payment_watch`
- `source_inventory_ref`: `source_inventory:finance_capital_hilton_payment_watch`
- `conflict_log_ref`: `conflict_log:finance_capital_hilton_payment_watch`
- `missing_context_ref`: `missing_context:finance_payment_evidence`
- `duplicate_report_ref`: `version_family:finance_payment_watch`
- `decision_trace_ref`: `decision_trace:finance_capital_hilton_payment_watch`
- `freshness_gate_ref`: `freshness_gate:receipt_current_or_needs_verification`
- `compaction_policy_ref`: `generated/read_models/context_compaction_preview_policy.json`
- `redacted_proof_bundle_ref`: `generated/read_models/proof_bundle_freshness_trace_status.json#finance_capital_hilton_payment_watch_redacted`

## Operator Decision Options

- `approve_one_time_room_backed_lm2_worker_pilot`
- `request_more_detail`
- `reject_for_now`

## Rules

- This packet is not approval.
- This packet does not run LM2.
- invocation_allowed=false.
- worker_spawn_allowed=false.
- proof_bundle_allowed=false.
- No protected business action.
- No external provider.
- No tool authority.
