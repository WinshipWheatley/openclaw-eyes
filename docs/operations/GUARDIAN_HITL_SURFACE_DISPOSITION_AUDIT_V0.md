# Guardian HITL Surface Disposition Audit v0

## Purpose

This audit decides which current HITL/Guardian approval surfaces should remain,
be compatibility-only, be replaced, be retired later, be blocked, or require an
operator decision before any adapter/wiring work begins.

This is audit/spec work only. No adapters were wired. No runtime behavior was
modified. No old HITL JSON/JSONL was deleted. No approval path was disabled. No
data was imported. Repo B was inspected only as read-only filename/logic
evidence and was not executed.

## Source Basis

- `docs/operations/GUARDIAN_HITL_AUTHORITY_RECONCILIATION_V0.md`
- `docs/operations/GUARDIAN_HITL_SQLITE_AUTHORITY_CONTRACT_V0.md`
- `generated/read_models/guardian_hitl_authority_reconciliation.json`
- `generated/read_models/guardian_hitl_sqlite_authority_contract.json`
- `docs/operations/CROSS_REPO_SPLIT_HITL_AND_MODULE_BOUNDARY_RECONCILIATION_V0.md`
- Safe source inspection of Repo A approval, Guardian, Operator Action,
  Cassandra HITL, and recovery surfaces.
- Repo B approval/HITL filenames only as pre-split reference evidence.

No raw approval state files, Telegram logs, secrets, env files, private data,
client data, bank data, spreadsheet cells, or no-go roots were inspected.

## Disposition Vocabulary

Every surface is classified with exactly one disposition:

- `keep_canonical`
- `keep_compatibility_shim`
- `replace_with_sqlite_operator_action`
- `retire_after_migration`
- `block_no_go`
- `unknown_operator_decision`

## A. What Should Be Canonical?

Canonical now:

- `operator_action.py`
- `operator_action_inbox.py`
- `guardian_hitl_sqlite_authority_contract.py` and its docs/read-models
- Cassandra recovery clearance in `agent_presence.py`, but only as a
  fixed-scope Cassandra recovery special case

These are the surfaces that match the preferred direction: SQLite-backed,
receipt-aware, bounded, and explicit about no-authority flags.

## B. What Should Be Compatibility-Only?

Compatibility-only during transition:

- `chief_approval_brain.py`
- `chief_approval_policy.py`
- `chief_guardian_listener.py`
- `chief_guardian_sender.py`
- `chief_router.py` approval fallback
- `chief_watcher_brain.py` approval replay
- `/mnt/c/OpenClaw/logs/approval_pending.json`
- `/mnt/c/OpenClaw/logs/hitl_pending_state.json`
- `/mnt/c/OpenClaw/logs/hitl_audit.jsonl`
- `hitl_notification_service.py`

These paths should not be deleted or disabled yet because current Repo A code
still references them. They should not be treated as canonical long-term
authority either.

## C. What Should Be Replaced?

Replace with SQLite Operator Action / Guardian contract semantics:

- `hitl_pending_store.py`
- `hitl_action_service.py`
- Google broker's dependency on `chief_approval_brain.request_approval`

The concepts are useful: validation, idempotency, transaction guardrails, and
operator approval. The current backing authority is not acceptable long-term
because it remains JSON-backed and does not share one canonical receipt chain.

## D. What Should Be Retired Later?

Retire only after migration/replacement proof:

- `hitl_pending_action.py` and `hitl_pending_actions.json`
- direct Markdown approval authority in the vault Approval Log
- `hitl_notifications.jsonl` as notification authority once SQLite
  notification receipts exist

These are not safe to delete now. They should become evidence/history or be
retired after current callers have moved and operator review confirms no useful
pending authority is lost.

## E. What Should Be Blocked?

Blocked:

- Repo B approval/HITL runtime execution
- raw command/freeform shell approval patterns

Repo B remains useful pre-split reference evidence. It must not become current
runtime authority. Raw command approvals would create arbitrary execution
authority and must stay no-go.

## F. What Needs Operator Decision?

The Chief workflow choice bridge needs a separate operator decision:

- `chief_approval_bridge.py`
- `/mnt/c/OpenClawShared/album/choice_pending.json`

It may be useful UX, but it is not action approval. It should not be folded
into Guardian HITL authority without a deliberate decision about whether
OpenClaw needs a separate workflow-choice substrate.

## Surface Disposition Table

| surface | file/path | current role | current state store | approval object shape | actively referenced | safe | depends on | disposition | reason | risk if kept | risk if removed | recommended next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Operator Action path | `operator_action.py` | SQLite-backed request, approval, allowlisted local execution, and receipt path. | SQLite `operator_action_*` tables | action id/type, approval row, allowlisted argv, receipt | yes | safe for existing narrow local actions only | business ops ledger | `keep_canonical` | Cleanest current SQLite-backed approval/receipt model. | Mistaken for general remote/send authority. | Lose strongest action spine. | Keep as canonical foundation. |
| Operator Action Inbox | `operator_action_inbox.py` | Strict JSON request intake into Operator Action. | SQLite inbox/import tables | request JSON normalized into pending action | yes | safe as import-only metadata | Operator Action | `keep_canonical` | Preserves request vs approval separation. | Auto-execution drift. | Lose governed intake pattern. | Keep canonical; no remote-builder broadening. |
| Guardian SQLite contract | `guardian_hitl_sqlite_authority_contract.py` | Defines future approval contract. | generated read-models only | immutable payload hash, idempotency, TTL, exact binding, receipts | yes, not runtime-wired | safe as spec/read-model | Operator Action concepts | `keep_canonical` | Target authority shape is defined without runtime mutation. | Confusing contract with live wiring. | Lose adapter target. | Keep canonical contract. |
| Cassandra recovery clearance | `agent_presence.py`; recovery scripts | Fixed Cassandra recovery clearance. | SQLite `agent_recovery_*` tables | single-use fixed action clearance | yes | safe only as fixed-scope special case | agent presence policy | `keep_canonical` | Already receipt-backed and bounded. | Generalization risk. | Lose governed recovery path. | Keep fixed-scope; exclude from generic HITL. |
| Chief approval brain | `chief_approval_brain.py` | Active Tier 0/1/2 gate. | `approval_pending.json`, Approval Log.md | action text/id/requester/status/decision/hash/context | yes | current compatibility only | policy, Guardian sender | `keep_compatibility_shim` | Current callers still depend on it. | JSON/action-text authority persists. | Break current approvals. | Keep while planning SQLite mirror. |
| Chief approval policy | `chief_approval_policy.py` | Approval tier classifier. | code rules | policy result only | yes | useful policy, not authority | Chief approval brain | `keep_compatibility_shim` | Logic may be reused. | String classifier becomes overtrusted. | Weaken current tiering. | Bind policy results into future contract. |
| Guardian listener | `chief_guardian_listener.py` | Telegram approval intake. | delegated Chief/HITL stores | callback id/code/token decision | yes | transport only | Telegram, Chief/HITL state | `keep_compatibility_shim` | Transport should survive; SQLite owns authority later. | Old JSON remains center. | Remove phone approval response path. | Keep as approval-only transport shim. |
| Guardian sender | `chief_guardian_sender.py` | Approval request transport. | no local state | Telegram message/keyboard | yes | only inside existing gates | Telegram config, requests | `keep_compatibility_shim` | Useful transport, not authority. | Send transport misuse. | Break approval delivery. | Keep transport shim; record receipts later. |
| Chief router approval reply | `chief_router.py` | Typed approval/HITL fallback route. | delegated Chief/HITL stores | code decision or signed token | yes | compatibility fallback only | Chief/HITL services | `keep_compatibility_shim` | Protects stale approval replies today. | Divergent listener/router semantics. | Lose fallback UX. | Keep until contract covers same cases. |
| Chief watcher approval replay | `chief_watcher_brain.py` | Re-sends pending approvals on cooldown. | `approval_pending.json`, watcher state | existing pending approval id only | yes/code path | notification side effect only | Chief approval brain | `keep_compatibility_shim` | Does not decide approvals but is coupled to JSON. | Perpetuates JSON center. | Reduce stuck approval visibility. | Model as notification receipt later. |
| Chief pending approval JSON | `/mnt/c/OpenClaw/logs/approval_pending.json` | Active pending approval state. | Windows-side JSON | single pending approval dict | yes | not canonical, must not delete | Chief/Guardian paths | `keep_compatibility_shim` | Active transition state. | Mutable JSON authority. | Break approvals/lose pending state. | Catalog legacy ref; mirror later. |
| Cassandra HITL pending store | `hitl_pending_store.py` | JSON pending action store and transaction guard. | `hitl_pending_state.json`, `hitl_audit.jsonl` | action id/type/payload/status/review/TTL | yes | not canonical | Cassandra brain, HITL toggle | `replace_with_sqlite_operator_action` | Concept useful; authority must move to SQLite. | Disabled HITL can allow proceed; JSON drift. | Break current compatibility. | Plan SQLite adapter before retirement. |
| HITL action service | `hitl_action_service.py` | Validation/idempotency wrapper over HITL store. | delegated HITL JSON | action id/type/payload/idempotency/approved_by | yes/mixed | not executor boundary | HITL pending store | `replace_with_sqlite_operator_action` | API shape useful; store must change. | No-op approval hook mistaken for execution. | Remove service wrapper prematurely. | Replace backing store with contract later. |
| HITL notification service | `hitl_notification_service.py` | Sends/handles HITL notifications and tokens. | HITL JSON/JSONL | HMAC token bound to action/decision/expiry | yes | transport compatibility only | HITL action service, Guardian sender | `keep_compatibility_shim` | Token transport can survive; SQLite owns decisions. | JSON-backed send-capable path persists. | Break HITL callbacks. | Keep until SQLite notification/decision receipts exist. |
| HITL pending state JSON | `/mnt/c/OpenClaw/logs/hitl_pending_state.json` | Current HITL pending action state. | Windows-side JSON | action id map | yes | not canonical, must not delete | HITL pending store | `keep_compatibility_shim` | Active transition state. | Mistaken for canonical truth. | Break compatibility/lose context. | Keep untouched until superseded. |
| HITL audit JSONL | `/mnt/c/OpenClaw/logs/hitl_audit.jsonl` | Transition audit log. | Windows-side JSONL | transition event records | yes | evidence-only | HITL JSON stores | `keep_compatibility_shim` | May contain useful evidence. | Treated as complete receipts. | Lose transition evidence. | Replace with SQLite receipts later. |
| HITL notifications JSONL | `/mnt/c/OpenClaw/logs/hitl_notifications.jsonl` | Notification audit path. | Windows-side JSONL | notification event records | yes | evidence-only | HITL notification service | `retire_after_migration` | Future receipts should replace it. | Drift from receipts. | Lose troubleshooting evidence. | Retire after SQLite notification receipts exist. |
| Older HITL pending action store | `hitl_pending_action.py`; `hitl_pending_actions.json` | Older parallel queue. | JSON and shared audit JSONL | older pending action list | not proven active | not live authority | chief_file_io | `retire_after_migration` | Parallel store should not survive. | Duplicate HITL authority. | Unknown dormant caller risk. | Prove unused, then retire. |
| Vault Approval Log Markdown | `/mnt/c/OpenClawShared/openclaw-vault/System/Approval Log.md` | Human-readable Chief approval log. | Markdown | decision entry | yes | not authority | Chief approval brain | `retire_after_migration` | SQLite receipts should become canonical. | Markdown drift. | Lose human trail. | Replace direct writes with receipt export later. |
| Chief workflow choice bridge | `chief_approval_bridge.py`; `choice_pending.json` | Non-blocking workflow choice prompt. | JSON choice state | prompt/options/answer | yes | not action approval | Chief workflows | `unknown_operator_decision` | May be useful UX but not HITL authority. | Blurs approval vs choice. | Disrupt workflow prompts. | Decide separate workflow-choice substrate fate. |
| Google broker approval hook | `google_access_broker.py` | Class B/C Google approval hook. | Chief JSON gate plus audit JSONL | action label/context | yes | not safe to expand | Chief approval brain | `replace_with_sqlite_operator_action` | External writes need packet/receipt binding. | External APIs tied to JSON action-text approvals. | Break current protection. | Require explicit approved packet in future adapter. |
| Repo B approval/HITL tree | `/home/openclaw_external/openclaw-runtime/*approval*`; `*guardian*`; HITL task files | Pre-split reference evidence. | legacy Repo B patterns | legacy concepts | reference-only | safe only read-only | none current | `block_no_go` | Repo B runtime is not current authority. | Direct execution/bulk port temptation. | Lose design evidence. | Keep reference-only. |
| Raw command/freeform shell approval | no canonical file | Forbidden approval shape. | none allowed | raw shell/command text | blocked by contract | unsafe | none | `block_no_go` | Creates arbitrary execution authority. | Critical execution/bypass risk. | No downside. | Keep blocked in tests/contract. |

## G. Minimum Safe Path Before Memory Import Or Remote Builder

Minimum path:

1. Keep Operator Action and the Guardian SQLite contract as canonical.
2. Keep old JSON-backed Chief/Guardian and Cassandra HITL paths as
   compatibility-only while they remain active.
3. Plan adapters before wiring anything.
4. Do not delete old JSON/JSONL.
5. Do not treat old JSON/JSONL as canonical truth.
6. Do not import Cassandra/Chief memory as authority.
7. Do not enable a remote-builder bridge.
8. Do not expand Telegram/Gmail/email send paths.

## Readiness

Adapter planning is now safe as a documentation/test planning lane:

`safe_to_plan_adapters=true`

Implementation wiring is not yet approved:

- `safe_to_import_cassandra_chief_memory=false`
- `safe_to_enable_remote_builder=false`
- `runtime_authority_changed=false`
- `old_hitl_deleted=false`

## Next Safe Move

Recommended next lane:

**Guardian HITL SQLite Compatibility Adapter Plan v0**

Purpose: define the sequence and tests for compatibility adapters that can
mirror or translate Chief/Guardian and Cassandra HITL requests into the SQLite
contract without changing runtime behavior yet.
