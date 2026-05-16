# Guardian HITL SQLite Shadow Adapter v0

## Bottom Line

Legacy Guardian/HITL surfaces were mapped into the canonical SQLite contract shape for visibility only. No runtime behavior changed, no live JSON was read or written, no approval request was created, and callers were not switched.

## What Was Mapped

- `chief_approval_brain` -> `guardian_hitl_approval_requests, guardian_hitl_approval_decisions` (shadow_write_to_sqlite_later)
- `chief_approval_policy` -> `guardian_hitl_legacy_authority_refs` (read_only_reference)
- `chief_guardian_listener` -> `guardian_hitl_approval_decisions, guardian_hitl_approval_receipts` (read_only_reference_then_translate_legacy_request_to_operator_action)
- `chief_guardian_sender` -> `guardian_hitl_approval_receipts` (read_only_reference_then_notification_receipt_shadow)
- `chief_router_approval_reply` -> `guardian_hitl_approval_decisions, guardian_hitl_approval_receipts` (read_only_reference_then_translate_legacy_request_to_operator_action)
- `chief_watcher_approval_replay` -> `guardian_hitl_approval_receipts` (read_only_reference_then_notification_receipt_shadow)
- `approval_pending_json` -> `guardian_hitl_approval_requests, guardian_hitl_legacy_authority_refs` (shadow_write_to_sqlite_later)
- `hitl_pending_store` -> `guardian_hitl_approval_requests, guardian_hitl_approval_decisions` (shadow_write_to_sqlite_later_then_translate_legacy_request_to_operator_action)
- `hitl_action_service` -> `guardian_hitl_approval_requests, guardian_hitl_approval_decisions` (replace_backing_store_with_sqlite_contract_later)
- `hitl_notification_service` -> `guardian_hitl_approval_receipts` (freeze_until_replaced_then_notification_receipt_shadow)
- `hitl_pending_state_json` -> `guardian_hitl_approval_requests, guardian_hitl_legacy_authority_refs` (shadow_write_to_sqlite_later)
- `hitl_audit_jsonl` -> `guardian_hitl_approval_receipts, guardian_hitl_legacy_authority_refs` (read_only_reference_then_sqlite_receipts)
- `hitl_notifications_jsonl` -> `guardian_hitl_approval_receipts, guardian_hitl_legacy_authority_refs` (retire_after_equivalent_receipts_proven)
- `hitl_pending_action_legacy` -> `guardian_hitl_legacy_authority_refs` (retire_after_equivalent_proven)
- `approval_log_md` -> `guardian_hitl_approval_receipts, guardian_hitl_legacy_authority_refs` (retire_after_receipt_export_proven)
- `google_access_broker_approval_hook` -> `guardian_hitl_approval_requests, guardian_hitl_approval_receipts` (translate_legacy_request_to_operator_action_later)

## Still Legacy Or Mixed

- `chief_approval_brain` remains `authority_conflict_reconcile_first`.
- `chief_guardian_listener` remains `authority_conflict_reconcile_first`.
- `chief_router_approval_reply` remains `authority_conflict_reconcile_first`.
- `chief_watcher_approval_replay` remains `authority_conflict_reconcile_first`.
- `approval_pending_json` remains `authority_conflict_reconcile_first`.
- `hitl_pending_store` remains `authority_conflict_reconcile_first`.
- `hitl_action_service` remains `authority_conflict_reconcile_first`.
- `hitl_notification_service` remains `authority_conflict_reconcile_first`.
- `hitl_pending_state_json` remains `authority_conflict_reconcile_first`.
- `hitl_audit_jsonl` remains `authority_conflict_reconcile_first`.
- `hitl_notifications_jsonl` remains `authority_conflict_reconcile_first`.
- `hitl_pending_action_legacy` remains `authority_conflict_reconcile_first`.
- `google_access_broker_approval_hook` remains `authority_conflict_reconcile_first`.

## Shadow Only

- Runtime authority changed: `false`
- Shadow only: `true`
- Dual-write enabled: `false`
- Callers switched: `false`
- Old HITL deleted: `false`
- Real approval request created: `false`

## Not Guardian Approval Authority

- `choice_pending_json_bridge`: `workflow_choice_substrate`.

## Blocked

- `repo_b_approval_tree`: Repo B runtime must not be used as current approval authority.
- `raw_command_or_freeform_shell_approval`: Approving raw commands would create arbitrary execution authority.

## Before Dual-Write

- operator review of shadow mapping
- fixture coverage for Chief JSON, Cassandra HITL, Guardian transport, and Google broker mappings
- proof that shadow records do not mutate live JSON stores
- approval contract receipt fields proven without raw private/log content
- separate decision on workflow-choice substrate if needed

## Next Safe Move

Review the shadow mapping, then plan a bounded dual-write compatibility spec without switching callers.
