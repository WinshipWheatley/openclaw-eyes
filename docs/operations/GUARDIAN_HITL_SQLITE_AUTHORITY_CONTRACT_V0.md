# Guardian HITL SQLite Authority Contract v0

## Purpose

This contract defines the approval shape OpenClaw should converge on before
Cassandra/Chief memory import, remote-builder bridges, or new external-action
workflows proceed.

This lane defines the contract and read-model only. It does not delete old
HITL JSON/JSONL, disable existing approval paths, modify runtime services,
enable agents, send Telegram/Gmail/email, execute Repo B code, or create
general runtime execution authority.

## Contract Finding

Operator Action is the cleanest current SQLite-backed authority path, but it
only covers narrow allowlisted local actions. Chief/Guardian approval still
actively uses `approval_pending.json`. Cassandra HITL still uses JSON-backed
pending/action/notification state.

The correct target is one SQLite-backed Guardian/HITL authority contract using
the Operator Action request -> approval -> receipt pattern. This contract is
not yet wired into the live Chief/Guardian or Cassandra HITL callers, so it is
not yet safe to import Cassandra/Chief memory as authority, enable a
remote-builder bridge, or expand send paths.

## Canonical Approval Object

Every future action-capable approval request must include:

| field | rule |
| --- | --- |
| `approval_id` | Stable approval object id. |
| `action_type` | Typed action, not freeform text. |
| `actor` | Requesting agent/system/operator surface. |
| `target` | Bound target object/system/account/surface. |
| `payload_hash` | Hash of the immutable approved payload. |
| `payload_schema_version` | Versioned payload schema. |
| `source_intent_ref` | Link back to intent/action record or approved packet. |
| `idempotency_key` | Duplicate-safe key for retries. |
| `requested_at` | Request timestamp. |
| `expires_at` | Approval expiry timestamp. |
| `ttl_seconds` | Positive TTL. |
| `authority_scope` | What this approval can and cannot authorize. |
| `risk_tier` | Review tier/risk class. |

Every decision must include:

- `approval_id`
- `decision`
- `decided_by`
- `decided_at`
- `decision_receipt_id`
- `approved_payload_hash`

Every receipt must include:

- `receipt_id`
- `approval_id`
- `receipt_type`
- `status`
- `summary`
- `created_at`

## Canonical State Store

The canonical state store target is the existing OpenClaw SQLite business ops
ledger. The contract should reuse the Operator Action spine instead of creating
a parallel approval system.

Contract tables for a future wiring lane:

| table | purpose | status |
| --- | --- | --- |
| `guardian_hitl_approval_requests` | Immutable approval request record. | Contract defined, not runtime-wired. |
| `guardian_hitl_approval_decisions` | Approval/denial/expiry/revocation bound to the exact request payload hash. | Contract defined, not runtime-wired. |
| `guardian_hitl_approval_receipts` | Request, decision, notification, execution-attempt, and result receipts. | Contract defined, not runtime-wired. |
| `guardian_hitl_legacy_authority_refs` | Metadata-only catalog of old JSON/JSONL approval stores during transition. | Contract defined, not runtime-wired. |

No runtime DB migration was applied by this lane.

## Immutable Payload Requirements

- The request payload must be immutable after approval.
- The approval must bind to the exact `payload_hash`.
- A decision is invalid if it points to a different payload hash.
- Expired or denied approvals cannot be silently reactivated.
- Payload mutation requires a new approval request, a new hash, and a new
  receipt chain.

## Idempotency Key Rules

- The same actor, action type, target, payload hash, and source intent should
  map to one active approval request.
- Duplicate requests with the same idempotency key must return the existing
  active request instead of creating competing authority.
- Expired, denied, or completed records may be referenced by receipt, but must
  not be reused as fresh approval.

## TTL Rules

- Every approval request must include `expires_at` and `ttl_seconds`.
- `ttl_seconds` must be a positive integer.
- Approval after expiry requires a new request.
- TTL extension cannot mutate an already approved payload.

## Exact Action Binding

Approvals authorize only the exact typed action and payload they bind:

```text
approval_id + action_type + actor + target + payload_hash + source_intent_ref
```

Approval of unparsed text is not valid authority.

## Receipt Requirements

The contract requires:

- request receipt
- decision receipt
- expiry/revocation receipt when applicable
- notification receipt when Guardian/Telegram transport is used
- execution-attempt/result receipt only when a separately authorized executor
  exists

Execution receipt is not an approval by itself. Approval receipt is not
execution authority by itself.

## No Raw Command Text Rule

Approval payloads must not contain:

- `command`
- `command_text`
- `command_string`
- `raw_command`
- `raw_command_text`
- `shell`
- `shell_command`
- `freeform_shell`
- `argv`
- `cmd`
- `exec`
- `subprocess`

Existing Operator Action can store allowlisted argv internally for its bounded
local actions, but future approval packets must approve typed action identity
and payload hash, not raw command text.

## No Freeform Shell Approval Rule

The contract forbids approving arbitrary shell, eval, subprocess snippets, or
operator-supplied command strings. A future executor, if any, must be a separate
bounded allowlist with receipts.

## Send, Deploy, Runtime, And Remote Builder Rule

No send/deploy/runtime/remote-builder action may execute unless it has an
explicit approved packet. Classes that require explicit packets include:

- Telegram/Gmail/email send
- external API write
- deployment
- runtime activation
- remote-builder work

This lane did not make any of those safe.

## Relationship To Existing Surfaces

| surface | role now | contract relationship |
| --- | --- | --- |
| `operator_action.py` | Cleanest SQLite request/approval/receipt path for narrow allowlisted local actions. | Foundation to reuse. |
| `operator_action_inbox.py` | Strict request intake only; no approve/execute. | Intake pattern to preserve. |
| `chief_approval_brain.py` | Active Chief/Guardian gate backed by `approval_pending.json`. | Transition adapter candidate; must not be deleted or disabled yet. |
| `chief_guardian_listener.py` / `chief_guardian_sender.py` | Guardian transport for approval decisions. | Transport only; SQLite must own authority. |
| `hitl_pending_store.py` | JSON-backed Cassandra HITL pending store. | Transition adapter candidate; not canonical authority. |
| `hitl_action_service.py` | Wrapper over HITL pending store. | Service candidate only after SQLite receipts exist. |
| `agent_presence.py` Cassandra recovery clearance | Fixed-scope SQLite recovery special case. | Keep separate; not general runtime approval. |

## Legacy JSON During Transition

Old JSON/JSONL state remains `authority_conflict_reconcile_first`:

- `/mnt/c/OpenClaw/logs/approval_pending.json`
- `/mnt/c/OpenClaw/logs/hitl_pending_state.json`
- `/mnt/c/OpenClaw/logs/hitl_audit.jsonl`
- `/mnt/c/OpenClaw/logs/hitl_pending_actions.json`
- related HITL notification/choice files

These files are not canonical truth, but they are still referenced by current
Repo A code. They must not be deleted, migrated as truth, or labeled obsolete
until replacement is proven.

## Deprecation Proof Required

Before old JSON paths can be deprecated:

1. Every current non-test caller must read/write the SQLite contract instead.
2. Old JSON must no longer be read or written outside tests/docs.
3. Request, decision, expiry, notification, and result receipts must exist.
4. The exact action payload hash and idempotency key must be preserved.
5. Existing pending/active authority must not be silently lost.
6. Operator review must confirm transition safety.

## Safety Status

| question | answer |
| --- | --- |
| Runtime authority changed? | No. |
| Old HITL deleted? | No. |
| Legacy JSON still active? | Yes. |
| Cassandra/Chief memory import safe now? | No. |
| Remote-builder bridge safe now? | No. |
| Send-path expansion safe now? | No. |

## Next Safe Move

Recommended next lane:

**Guardian HITL SQLite Contract Adapter Plan v0**

Purpose: plan the narrow adapter sequence that lets Chief/Guardian and
Cassandra HITL write/read the SQLite contract without deleting old JSON,
changing live services, or expanding action authority.
