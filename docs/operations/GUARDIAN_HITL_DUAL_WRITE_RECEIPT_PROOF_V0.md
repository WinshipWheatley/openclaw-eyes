# Guardian HITL Dual-Write Receipt Proof v0

Generated: `2026-05-16`

Evidence basis:

- `guardian_hitl_dual_write_compatibility.py`
- `chief_approval_brain.py`
- `tests/test_guardian_hitl_dual_write_compatibility.py`
- `tests/test_chief_approval_brain.py`
- `tests/test_guardian_hitl_sqlite_authority_contract.py`
- `generated/read_models/guardian_hitl_dual_write_compatibility.json`
- `generated/read_models/guardian_hitl_dual_write_compatibility_OPERATOR.md`

No runtime behavior was changed by this proof lane. No data was imported. No old HITL JSON/JSONL was deleted. No callers were switched.

## Summary

The Chief approval dual-write path is now coherent as an observational SQLite proof path for request mirrors and decision receipt shadows.

This means the code can mirror:

- Chief approval requests as `request_shadow_created` receipts.
- Chief approval decisions as `decision_shadow_observed` receipts.
- Chief denial decisions as `decision_shadow_rejected` receipts.
- Chief timeout outcomes as `decision_shadow_expired` receipts.
- Hash/id mismatches as `legacy_sqlite_mismatch` receipts.

The proof is synthetic/test-backed and read-model-backed. It is not yet live operational proof: the current generated read-model shows zero live request mirrors and zero live decision receipts.

## What Is Proven

| claim | proof |
| --- | --- |
| Request mirror support exists. | `guardian_hitl_approval_requests` and `request_shadow_created` are implemented and tested. |
| Decision receipt support exists. | `decision_shadow_observed`, `decision_shadow_rejected`, and `decision_shadow_expired` are implemented and tested. |
| Receipts are observational only. | Records keep `runtime_authority=false`, `caller_switched=false`, `old_hitl_deleted=false`, and `legacy_json_authoritative=true`. |
| Old JSON remains authority. | `approval_pending.json` remains the live state store; SQLite failure is fail-open and cannot block legacy approval flow. |
| Missing request mirror cannot create authority. | Decision receipt helper returns `missing_request_mirror` and creates no request/receipt rows when no bound request mirror exists. |
| Mismatched request/decision context is visible. | Mismatch creates `legacy_sqlite_mismatch` instead of trusting SQLite or approving anything. |
| Raw approval content is not stored. | Tests assert raw action text, raw command text, full approval context, raw callback payloads, and sensitive command-looking strings are not persisted. |
| Adapter failure is fail-open. | Tests prove request and decision mirror failures do not alter Chief approval outcomes. |
| No send/runtime/remote-builder authority was added. | Read-model flags keep Cassandra/Chief memory import, remote-builder, and send-path expansion unsafe. |

## What Remains Unproven

- No live request mirror has been observed in the generated read-model yet.
- No live decision receipt has been observed in the generated read-model yet.
- Notification/sender receipts are still not implemented.
- Cassandra HITL proposal mirrors are still not implemented.
- Caller switching from old JSON to SQLite is not proven and remains out of scope.
- Old HITL JSON/JSONL retirement is not proven and remains out of scope.

## Still Blocked

- Cassandra/Chief memory import remains blocked.
- Remote-builder bridge remains blocked.
- Send-path expansion remains blocked.
- General runtime approval authority expansion remains blocked.
- Old HITL JSON/JSONL deletion remains blocked.

## Current Read-Model Posture

`generated/read_models/guardian_hitl_dual_write_compatibility.json` currently reports:

- `runtime_authority_changed=false`
- `legacy_json_authoritative=true`
- `callers_switched=false`
- `old_hitl_deleted=false`
- `raw_action_text_stored=false`
- `raw_command_text_stored=false`
- `request_mirror_count=0`
- `decision_receipt_count=0`
- `mismatch_count=0`
- `safe_to_import_cassandra_chief_memory=false`
- `safe_to_enable_remote_builder=false`
- `safe_to_expand_send_paths=false`

Zero counts are acceptable for this proof lane. They mean no live mirrored Chief approval lifecycle has been captured in the default ledger yet, not that support is absent.

## Import / Bridge Decision

Cassandra/Chief memory import is **not safe yet**.

Reason: Chief request/decision receipt support exists, but live receipt parity, Cassandra HITL proposal mirrors, and operator memory import approval are still missing.

Remote-builder bridge is **not safe yet**.

Reason: remote-builder requires explicit packet binding, approval receipts, result receipts, and no raw command/freeform shell authority. This lane proves only Chief approval request/decision shadow support.

## Next Safe Lane

Recommended next lane:

`Cassandra HITL Proposal Shadow v0`

Goal: mirror Cassandra HITL proposal requests into the same observational SQLite contract shape using safe hashes/metadata only. No raw payload import, no send path, no runtime authority, and no caller switch.
