# Guardian/HITL Surface Disposition v0

## Bottom Line

Operator Action stays canonical. Chief/Guardian JSON approval and Cassandra HITL JSON remain compatibility-only or replacement targets. Old JSON cannot be deleted yet. Memory import and remote-builder work remain unsafe.

## What Stays Canonical

- `operator_action_path`: Operator Action path
- `operator_action_inbox`: Operator Action Inbox
- `guardian_sqlite_contract`: Guardian HITL SQLite authority contract
- `cassandra_recovery_clearance`: Cassandra recovery clearance path

## Compatibility Only

- `chief_approval_brain`: Keep as compatibility shim while planning SQLite request/decision mirror.
- `chief_approval_policy`: Keep policy logic; future adapter should bind policy result into contract fields.
- `chief_guardian_listener`: Keep as approval-only transport shim; future adapter reads/writes SQLite contract.
- `chief_guardian_sender`: Keep transport shim; future contract records notification receipts separately.
- `chief_router_approval_reply`: Keep until Guardian listener and SQLite contract cover the same cases.
- `chief_watcher_approval_replay`: Model future replay as notification receipt, not approval authority.
- `approval_pending_json`: Catalog as legacy authority ref; mirror to SQLite only in a later adapter lane.
- `hitl_notification_service`: Keep as shim until it records notification and decision receipts in SQLite.
- `hitl_pending_state_json`: Keep untouched; later adapter should supersede with SQLite and prove no active use before retirement.
- `hitl_audit_jsonl`: Keep as compatibility/evidence ref; future SQLite receipts should replace it.

## Replace With SQLite Operator Action / Guardian Contract

- `hitl_pending_store`: The action proposal concept is useful, but authority must be moved to SQLite contract records.
- `hitl_action_service`: Validation/idempotency logic is useful, but the store and approval decision must move to SQLite.
- `google_access_broker_approval_hook`: External-action approval must bind to canonical packet and receipts before any expansion.

## Retire Later

- `hitl_notifications_jsonl`: Retire only after SQLite notification receipts exist and operator confirms.
- `hitl_pending_action_legacy`: Prove unused outside tests/docs, then retire after SQLite contract covers required behavior.
- `approval_log_md`: Replace with SQLite receipts plus generated operator read-model; retire direct writes later.

## Dangerous / Blocked

- `repo_b_approval_tree`: Repo B runtime must not be used as current approval authority.
- `raw_command_or_freeform_shell_approval`: Approving raw commands would create arbitrary execution authority.

## Cannot Touch Yet

- Do not delete `approval_pending.json`, `hitl_pending_state.json`, or HITL JSONL logs.
- Do not disable Chief/Guardian approval paths before compatibility adapters exist.
- Do not import Cassandra/Chief memory as authority.
- Do not enable remote-builder or new send paths.

## Needs Operator Decision

- `choice_pending_json_bridge`: Keep out of Guardian HITL adapter scope until operator chooses workflow-choice fate.

## Next Safe Move

Plan the Guardian HITL SQLite compatibility adapters without wiring runtime behavior yet.
