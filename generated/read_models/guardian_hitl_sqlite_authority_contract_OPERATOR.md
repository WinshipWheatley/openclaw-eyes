# Guardian/HITL SQLite Authority Contract v0

## Bottom Line

The canonical approval contract is now defined, but it is not wired into live runtime paths. Operator Action remains the cleanest SQLite-backed foundation. Chief/Guardian and Cassandra HITL still actively depend on legacy JSON-backed approval state.

## Contract Rules

- Approval requests need immutable action identity, payload hash, idempotency key, TTL, exact action binding, and receipts.
- Raw command text and freeform shell approval are forbidden.
- Send, deploy, remote-builder, and runtime actions require an explicit approved packet before they can ever execute.
- Old HITL JSON/JSONL is transition evidence, not canonical truth.

## Current Status

- Runtime authority changed: `false`
- Old HITL deleted: `false`
- Legacy JSON still active: `true`
- Cassandra/Chief memory import safe now: `false`
- Remote-builder bridge safe now: `false`
- Send-path expansion safe now: `false`

## Transition Shape

- `operator_action_path`: current clean SQLite foundation for narrow allowlisted local actions - Preserve as existing governed path; future Guardian contract should reuse its request/approval/receipt spine rather than duplicate it.
- `chief_approval_brain`: transition adapter candidate - Do not delete or disable. First add a SQLite request/decision mirror, then prove every active caller reads the contract before deprecation.
- `hitl_pending_store`: transition adapter candidate for Cassandra action proposals - Do not treat approved JSON records as execution authority until exact payload hash, TTL, idempotency, and receipt fields land in SQLite.
- `hitl_action_service`: service wrapper candidate - Keep as non-executing wrapper until approval decisions are bound to canonical SQLite receipts.
- `guardian_listener_sender`: transport adapter only - Guardian can carry decisions, but SQLite contract must own authority and receipts.
- `cassandra_recovery_clearance`: fixed-scope special case - Keep separate and fixed to Cassandra recovery; do not generalize into runtime action approval.

## Must Wait

- Do not import Cassandra/Chief memory as authority yet.
- Do not enable a remote-builder bridge yet.
- Do not expand Telegram/Gmail/email send paths yet.
- Do not delete or deprecate old HITL JSON until the active callers have moved.

## Next Safe Move

Implement a non-runtime Guardian/HITL SQLite contract schema adapter plan before wiring Chief/Guardian or Cassandra HITL callers.
