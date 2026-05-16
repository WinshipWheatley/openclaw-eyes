# Guardian HITL Authority Reconciliation v0

## Purpose

This reconciliation makes OpenClaw approval authority visible before any
Cassandra/Chief memory import, remote-builder bridge, or external-action
workflow proceeds.

This is read-model/spec work only. No runtime authority changed. No old HITL
JSON/JSONL was deleted, migrated, imported, or treated as truth. Repo B was
inspected only as pre-split source evidence and was not executed.

## Source Basis

- Repo A source under `/home/openclaw`.
- Prior split/module audit:
  `docs/operations/CROSS_REPO_SPLIT_HITL_AND_MODULE_BOUNDARY_RECONCILIATION_V0.md`.
- Cassandra/Chief memory authority specs and structured import plan.
- Repo B approval filenames and broad logic references only.
- Static `rg` reference map across Repo A approval/HITL terms, excluding
  generated/private/log/task roots where appropriate.

No raw approval state file bodies, Telegram logs, secrets, env values, private
client data, bank data, spreadsheet cells, or no-go roots were inspected.

## A. Surfaces Found

| surface | file/path | current classification | authority posture |
| --- | --- | --- | --- |
| Operator Action Path | `operator_action.py` | `active_runtime_path` | Best current SQLite-backed request/approval/execution/receipt path for narrow allowlisted local actions. |
| Operator Action Inbox | `operator_action_inbox.py` | `active_runtime_path` | Strict JSON request import into Operator Action; import never approves or executes. |
| Chief tiered approval gate | `chief_approval_brain.py` | `active_runtime_path` with authority conflict | Current active Tier 0/1/2 approval gate, but backed by old JSON/Markdown state. |
| Guardian approval listener | `chief_guardian_listener.py` | `active_runtime_path` with authority conflict | Telegram approval intake for Chief gate and HITL token callbacks. |
| Guardian approval sender | `chief_guardian_sender.py` | `active_runtime_path` with authority conflict | External approval send path; fail-closed for button approvals without Guardian token. |
| Chief router approval reply path | `chief_router.py` | `active_runtime_path` with authority conflict | Typed approval code fallback and HITL token command route. |
| Chief watcher approval replay | `chief_watcher_brain.py` | `active_special_case` with authority conflict | Bounded resend of an existing pending approval; does not decide. |
| Google broker approval hook | `google_access_broker.py` | `active_runtime_path` with authority conflict | Class B/C Google actions depend on `chief_approval_brain.request_approval`. |
| Cassandra HITL pending store | `hitl_pending_store.py` | `mixed_or_conflicting` | Current Repo A Cassandra action queue candidate, but JSON-backed and toggle-dependent. |
| HITL action service | `hitl_action_service.py` | `mixed_or_conflicting` | Validation/idempotency wrapper over HITL JSON store; approval hook is not a proven executor. |
| HITL notification service | `hitl_notification_service.py` | `mixed_or_conflicting` | Guardian notification/token flow over JSON-backed HITL action state. |
| Chief workflow choice bridge | `chief_approval_bridge.py` | `mixed_or_conflicting` | Non-blocking workflow choice prompt, not action approval. |
| Older HITL pending action store | `hitl_pending_action.py` | `legacy_reference` | Parallel older JSON pending action queue; not proven active, not proven obsolete. |
| Cassandra recovery clearance | `agent_presence.py` and recovery scripts | `active_special_case` | Fixed-scope SQLite recovery clearance for Cassandra only. |
| Guardian schema harness | `guardian_schema_harness.py` | `test_only` | Staging-only validation harness; does not write live approval state. |
| HITL flowchart generator | `hitl_flowchart_gen.py` | `docs_only` | Reference diagram generator; not runtime authority. |
| Repo B approval tree | `/home/openclaw_external/openclaw-runtime/chief_approval*.py`, `chief_guardian*.py` | `legacy_reference` | Pre-split capability tree, reference-only. |
| Live service use of every approval path | systemd/runtime status/logs | `unknown` | Static code proves possible paths, not current live use. |

## B. Old JSON/JSONL State References

Old HITL JSON/JSONL may not be labeled obsolete unless no current Repo A code
path reads or writes it outside tests/docs. Current source evidence shows that
some of it is still active or potentially active.

| state file | current Repo A reference | classification | deletion/migration posture |
| --- | --- | --- | --- |
| `/mnt/c/OpenClaw/logs/approval_pending.json` | `chief_approval_brain.py`, `chief_router.py`, `chief_guardian_listener.py`, `chief_watcher_brain.py`, `cassandra_listener.py` | `authority_conflict_reconcile_first` | Do not delete, block, or migrate as truth until replacement is proven. |
| `/mnt/c/OpenClawShared/openclaw-vault/System/Approval Log.md` | `chief_approval_brain.py` | `mixed_or_conflicting` | Historical/current log sink, not complete receipt authority. |
| `/mnt/c/OpenClaw/logs/hitl_pending_state.json` | `hitl_pending_store.py`, `hitl_action_service.py`, `hitl_notification_service.py` | `authority_conflict_reconcile_first` | Do not delete or treat as canonical approval authority. |
| `/mnt/c/OpenClaw/logs/hitl_pending_actions.json` | `hitl_pending_action.py` | `authority_conflict_reconcile_first` | Prove no runtime caller before deprecation. |
| `/mnt/c/OpenClaw/logs/hitl_audit.jsonl` | `hitl_pending_store.py`, `hitl_pending_action.py` | `authority_conflict_reconcile_first` | Historical audit candidate only after reconciliation. |
| `/mnt/c/OpenClaw/logs/hitl_notifications.jsonl` | `hitl_notification_service.py` | `mixed_or_conflicting` | Notification audit, not approval source of truth. |
| `/mnt/c/OpenClawShared/album/choice_pending.json` | `chief_approval_bridge.py`, `chief_listener.py`, `chief_router.py` | `mixed_or_conflicting` | Workflow choice state, not action approval. |
| SQLite `operator_action_*` | `operator_action.py`, `operator_action_inbox.py` | `active_runtime_path` | Preferred governed target for narrow local actions. |
| SQLite `agent_recovery_*` | `agent_presence.py` | `active_special_case` | Fixed Cassandra recovery clearance only. |

## C. Does Current Code Treat Old JSON As Active Authority?

Yes, for at least the Chief/Guardian approval gate.

`chief_approval_brain.py` reads and writes `approval_pending.json` for current
Tier 2 approval state. `chief_router.py` and `chief_guardian_listener.py`
resolve decisions against the active pending record. `chief_watcher_brain.py`
can resend a current pending request from that same state file.

The HITL action queue also uses JSON/JSONL state in current Repo A files:
`hitl_pending_store.py`, `hitl_action_service.py`, and
`hitl_notification_service.py`. That does not make the old files clean
authority. It means they are authority-conflict surfaces until a replacement is
defined and proven.

## D. Operator Action Path vs HITL Stores

The Operator Action Path is the cleanest current model:

```text
request -> SQLite action record -> explicit approval -> allowlisted argv execution -> receipt
```

The HITL stores are not the same model:

```text
Cassandra/action proposal -> JSON pending store -> optional Guardian notification/token -> JSON state transition
```

Key differences:

- Operator Action is SQLite-backed and command allowlisted.
- HITL pending store can return proceed when HITL is disabled for non-limit
  actions.
- HITL notification tokens are tied to JSON-backed action state.
- HITL approval hook currently does not prove an execution receipt boundary.
- Neither path should be silently treated as replacing the other.

## E. Cassandra Recovery Trace

The Cassandra recovery path is a fixed-scope special case, not general Guardian
authority.

| step | surface | what happens | proof status |
| --- | --- | --- | --- |
| Request | `scripts/request_agent_recovery_clearance.py` -> `agent_presence.request_agent_recovery_clearance` | Creates a SQLite `agent_recovery_clearances` row with status `requested`; no recovery command runs. | Proven by code/tests. |
| Guardian approval | `scripts/request_cassandra_recovery_guardian_approval.py` -> `chief_approval_brain.request_approval` | Requests Tier 2 approval for one Cassandra fixed systemd start clearance. | Proven by code/tests. |
| Approval result | `approve_agent_recovery_clearance` or `reject_agent_recovery_clearance` | Marks the exact clearance approved or rejected; still no recovery command runs. | Proven by code/tests. |
| Execution attempt | `scripts/recover_agent.py --execute` -> `agent_presence.recover_agent` | May use only fixed seeded argv for `cassandra_systemd_user_start` after clearance/policy checks. | Static code trace; live attempt not proven here. |
| Receipt | `agent_recovery_attempts`, `agent_recovery_receipts`, agent presence read-model | Records attempt/result and marks clearance used when applicable. | Receipt path proven by tests; current dirty generated presence snapshots are not committed truth. |

Missing without raw logs or runtime activation:

- whether a live recovery was recently attempted;
- whether systemd state changed after any attempt;
- whether dirty generated `agent_presence` snapshots reflect current truth.

## F. Authority Decision Table

| surface | file/path | caller/callee | state store | approval object | TTL/idempotency | classification | risk | next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Operator Action Path | `operator_action.py` | request -> approve -> execute | SQLite `operator_action_*` | action request/approval/receipt | no TTL; unique action id; allowlisted argv | `active_runtime_path` | Narrow but clean. | Preferred future local-action target. |
| Operator Action Inbox | `operator_action_inbox.py` | strict JSON -> request action | SQLite inbox/import/action tables | request file normalized into action | request id/action id; no execution | `active_runtime_path` | Not a remote builder. | Keep import-only. |
| Chief tiered approval gate | `chief_approval_brain.py` | request_approval -> Guardian -> record_decision | `approval_pending.json`, `Approval Log.md` | approval id/action/hash/context | 24h TTL, single slot, HMAC when configured | `active_runtime_path` | Active but old JSON-backed. | Reconcile into SQLite contract. |
| Guardian approval listener | `chief_guardian_listener.py` | Telegram callback/code -> record_decision | Chief/HITL delegated stores | callback id or typed code | pending id or token TTL | `active_runtime_path` | External listener. | Do not expand before contract. |
| Guardian approval sender | `chief_guardian_sender.py` | send_approval | none local | Telegram approval message | TTL belongs elsewhere | `active_runtime_path` | Send-capable. | No new sends. |
| Chief router approval reply | `chief_router.py` | route_message -> approval/HITL handlers | Chief/HITL delegated stores | typed code or HITL token | pending id/token TTL | `active_runtime_path` | Overlaps listener semantics. | Keep fallback, reconcile later. |
| Chief watcher approval replay | `chief_watcher_brain.py` | resend pending request | approval pending plus watcher state | existing approval only | 120s age, 600s cooldown, max 3 | `active_special_case` | Runtime side effect, no decision. | Model as notification receipt later. |
| Google broker approval hook | `google_access_broker.py` | Class B/C -> request_approval | Chief approval JSON | broker action label/context | Chief TTL | `active_runtime_path` | External actions depend on old gate. | Do not expand send/write. |
| Cassandra HITL pending store | `hitl_pending_store.py` | Cassandra propose_action | `hitl_pending_state.json`, `hitl_audit.jsonl` | pending action record | 24h TTL, optional idempotency | `mixed_or_conflicting` | Toggle/default can allow proceed. | Quarantine until unified. |
| HITL action service | `hitl_action_service.py` | service approve/deny -> store | HITL JSON/JSONL | action id/status | 24h TTL, derived idempotency | `mixed_or_conflicting` | Approval hook is not a receipt boundary. | No execution wiring. |
| HITL notification service | `hitl_notification_service.py` | notification/token -> service | HITL JSON/JSONL | signed approve/deny token | 24h token TTL | `mixed_or_conflicting` | Send-capable over JSON authority. | Do not expand. |
| Chief workflow choice bridge | `chief_approval_bridge.py` | send_choice -> router/listener handle | `choice_pending.json` | workflow choice | 30m choice timeout | `mixed_or_conflicting` | Choice can be confused with approval. | Keep separate. |
| Older HITL pending action | `hitl_pending_action.py` | no current runtime caller proven | `hitl_pending_actions.json`, `hitl_audit.jsonl` | old pending action | 24h expiry, no idempotency | `legacy_reference` | Parallel old queue. | Prove obsolete before deprecating. |
| Cassandra recovery clearance | `agent_presence.py` | request -> approve -> recover | SQLite `agent_recovery_*` | fixed clearance | 30m, single use | `active_special_case` | Not general action approval. | Keep fixed-scope. |
| Guardian schema harness | `guardian_schema_harness.py` | fixture replay | staging only | synthetic fixture | fixture-defined | `test_only` | Safe only as staging harness. | Keep test-only. |
| HITL flowchart generator | `hitl_flowchart_gen.py` | render docs | none | diagram metadata | n/a | `docs_only` | Descriptive only. | Reference only. |
| Repo B approval tree | `/home/openclaw_external/openclaw-runtime` | reference only | legacy patterns | legacy concepts | not evaluated | `legacy_reference` | Unsafe as runtime. | Keep reference-only. |
| Live service use | systemd/runtime | not checked | unknown | unknown | unknown | `unknown` | Static map is not live proof. | Future redacted status check only. |

## G. Safe To Use Now

Safe, within current limits:

- Operator Action Path for already allowlisted local actions.
- Operator Action Inbox for strict pending-request intake only.
- Cassandra recovery clearance as a fixed, single-use, receipt-backed special
  case.
- Existing Chief/Guardian gates as current runtime paths, without expanding
  their authority.

Not safe yet:

- Cassandra/Chief memory import as current authority.
- Remote-builder bridge.
- New send/reply/Gmail/Telegram paths.
- Generalizing Cassandra recovery clearance into generic runtime activation.
- Treating old HITL JSON/JSONL as canonical truth.

## H. Authority Conflict Surfaces

Treat these as `authority_conflict_reconcile_first`:

- `approval_pending.json`
- `hitl_pending_state.json`
- `hitl_pending_actions.json`
- `hitl_audit.jsonl`
- JSON-backed Chief/Guardian runtime approval state
- JSON-backed Cassandra HITL pending action state
- workflow choice state when it is described as approval

These must not be deleted or blocked yet. They should be deprecated only after
a replacement path proves:

1. equivalent current callers have moved;
2. immutable payloads and idempotency keys exist;
3. TTL and exact action binding exist;
4. approval/denial receipts exist;
5. execution receipts exist where execution is separately allowed;
6. old JSON files are no longer read/written by non-test, non-doc Repo A code.

## I. Minimum Future Approval Contract

All future action-capable paths should use one contract with:

- immutable payload;
- idempotency key;
- TTL;
- operator/Guardian approval;
- exact action binding;
- request, decision, and result receipts;
- no raw command text;
- no approval of freeform shell;
- no action mutation after approval;
- no send/deploy/runtime action without an explicit authorized packet;
- no old HITL JSON/JSONL as standalone current authority.

Minimum fields:

- `action_type`
- `actor`
- `target`
- `payload_hash`
- `source_intent_ref`
- `approval_id`
- `idempotency_key`
- `expires_at`
- `approved_by`
- `approved_at`
- `decision`
- `receipt_id`

## J. Next Safe Move

Recommended next lane:

**Guardian HITL SQLite Authority Contract v0**

Purpose: define the SQLite-backed contract and migration plan that lets Chief,
Guardian, Cassandra HITL, Google broker, and future remote-builder packets
share one approval spine without mutating runtime yet.

It should avoid:

- reading raw old HITL file contents;
- deleting or migrating old state;
- changing services;
- adding sends;
- running Repo B;
- approving freeform shell;
- expanding runtime activation.
