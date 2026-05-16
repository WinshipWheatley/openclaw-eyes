# Guardian HITL SQLite Dual-Write Compatibility Spec v0

## Executive Summary

This spec defines how selected legacy Guardian/HITL request paths can dual-write observational records into the canonical SQLite Guardian/Operator Action contract while preserving current runtime behavior.

This is specification only. No dual-write code was wired. No runtime behavior changed. Old HITL JSON/JSONL remains active compatibility state. Callers were not switched.

Current target:

`operator_action_sqlite_guardian_contract`

Current doctrine:

- Old JSON remains the live authority during dual-write compatibility.
- SQLite dual-write records are observational until request, decision, notification, and receipt equivalence is proven.
- Dual-write must never approve, deny, execute, send, deploy, restart, or switch callers by itself.
- `choice_pending.json` remains `workflow_choice_substrate`, not Guardian approval authority.

## A. Dual-Write Eligibility

Disposition vocabulary for this spec:

- `eligible_for_dual_write`
- `not_eligible`
- `freeze_until_replaced`
- `retire_later`
- `block_no_go`
- `operator_decision_required`

| surface | decision | current role | current state store | canonical SQLite target | dual-write risk | required adapter behavior | idempotency requirement | TTL requirement | receipt requirement | rollback condition | tests needed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `chief_approval_brain` | `eligible_for_dual_write` | Creates active Chief Tier 2 approval request and polls old JSON for decision. | `approval_pending.json`, vault Approval Log Markdown. | `guardian_hitl_approval_requests`, later `guardian_hitl_approval_decisions`. | Medium: active blocking approval path; SQLite failure must not affect approval outcome. | Write legacy JSON first, then write an observational SQLite request mirror using safe metadata and payload hash. Old JSON remains live decision source. | Use legacy approval id plus action hash; duplicate key returns existing shadow record. | Preserve Chief 24 hour timeout as `ttl_seconds=86400`; record whether TTL was inferred from code. | `request_shadow_created`, later `decision_shadow_observed`; no execution receipt. | If legacy JSON write fails, do not create a live-looking SQLite request. If SQLite write fails, keep legacy runtime path unchanged and mark adapter unhealthy. | Synthetic Chief request creates mirror; SQLite failure does not block legacy path; raw command/freeform shell rejected; no send occurs. |
| `approval_pending_json` | `eligible_for_dual_write` | Active Chief pending approval state file. | `/mnt/c/OpenClaw/logs/approval_pending.json`. | `guardian_hitl_legacy_authority_refs`, `guardian_hitl_approval_requests`. | Medium: file is active authority and must not be read broadly or mutated by adapter. | Register source reference and mirror only request metadata already present in the Chief call path; do not independently scan raw file contents. | Bind to same legacy approval id/action hash as `chief_approval_brain`. | Same as Chief request; 24 hour timeout. | Legacy source reference receipt plus request shadow receipt. | Any mismatch between legacy id/hash and SQLite mirror marks SQLite record invalid, not legacy JSON invalid. | No direct raw file ingest; no deletion; legacy source is classified `authority_conflict_reconcile_first`. |
| `chief_approval_policy` | `not_eligible` | Policy classifier for approval tiers and hard Tier 2 rules. | Code constants only. | `guardian_hitl_legacy_authority_refs` or request risk metadata. | Low, but it is not a request source. | Read-only policy metadata may enrich `risk_tier`; it must not create records by itself. | None; use parent request id. | None; use parent request TTL. | None by itself. | If policy classification fails, adapter safe-defaults to review-required and does not downgrade. | Policy cannot approve; hard Tier 2 cannot be suppressed. |
| `chief_guardian_listener` | `eligible_for_dual_write` | Handles button/code decisions and HITL callbacks. | Delegates to `approval_pending.json` and HITL JSON. | `guardian_hitl_approval_decisions`, `guardian_hitl_approval_receipts`. | High if wired before request mirror exists; decisions must bind to exact request hash. | Later phase only: write decision receipt after matching request mirror exists; never create request from a callback alone. | Must reference canonical request id and legacy approval id/token. | Decision after expiry must become rejected/expired receipt, not approval. | Decision receipt and callback receipt. | If no matching request mirror exists, record compatibility warning only and leave old path unchanged. | Stale button/code rejected; mismatch cannot approve; callback cannot create request. |
| `chief_guardian_sender` | `eligible_for_dual_write` | Sends Guardian approval notifications. | No local approval state; Telegram transport. | `guardian_hitl_approval_receipts`. | Medium because it is send-capable; adapter must not call sender or expand sends. | Later phase only: when existing sender is already called, write notification receipt metadata after or around existing call; no new sends. | Reference parent request id. | Notification receipt inherits request expiry. | Notification attempted/sent/failed receipt. | Sender failure follows existing behavior; SQLite receipt failure never retries send. | No additional Telegram send; fail-closed button behavior preserved. |
| `chief_router_approval_reply` | `eligible_for_dual_write` | Fallback typed approval code and HITL command route. | Delegates to Chief/HITL JSON. | `guardian_hitl_approval_decisions`, `guardian_hitl_approval_receipts`. | High if it accepts decisions without a canonical request mirror. | Later phase only: record decision observation after old path applies or rejects decision. | Bind to legacy approval id/code and canonical request id. | Expired or unknown code becomes rejection/expired receipt. | Decision observed/rejected receipt. | If SQLite write fails, router reply stays unchanged. | Expired code remains rejected; workflow choice still lower priority than approval. |
| `chief_watcher_approval_replay` | `not_eligible` | Replays current approval notification on cooldown. | `approval_pending.json`, watcher state. | `guardian_hitl_approval_receipts`. | Medium: side-effectful replay via subprocess/send. | Do not dual-write requests. Later notification receipt may observe replay only after sender receipts exist. | Reference existing request id. | Inherit parent request TTL. | Replay notification receipt later. | Replay adapter failure must not trigger another replay. | Replay cannot decide or create approval. |
| `hitl_pending_store` | `eligible_for_dual_write` | Cassandra HITL proposal store and transaction guard. | `hitl_pending_state.json`, `hitl_audit.jsonl`. | `guardian_hitl_approval_requests`, `guardian_hitl_approval_decisions`. | High: may hold action payloads; disabled HITL behavior can currently return proceed for non-limit actions. | Later phase after Chief request mirror: write sanitized proposal request mirror when a pending/denied record is created; never turn proceed into approval. | Use existing `idempotency_key` when present, otherwise derive from source agent, action type, payload hash, and legacy action id. | Preserve `ttl_seconds` from proposal; record expiry in SQLite. | Request shadow and auto-deny/expiry receipts where applicable. | If SQLite write fails, old HITL behavior remains unchanged and dual-write health fails. | No raw payload persistence; no send authority; hard-limit auto-deny mirrored as denied-not-executed. |
| `hitl_action_service` | `eligible_for_dual_write` | Validation/idempotency wrapper over HITL pending store. | Delegates to HITL JSON store. | `guardian_hitl_approval_requests`, `guardian_hitl_approval_decisions`. | Medium: `_on_action_approved` exists as a placeholder and must not become execution. | Later phase: call canonical adapter through pending store/service boundary while keeping old JSON store authoritative. | Preserve or derive service idempotency key. | Preserve service/default 24 hour TTL. | Request/decision shadow only; no execution receipt. | Approval hook remains non-executing; adapter failure does not call hook. | Approved JSON action does not execute; idempotency deduplicates. |
| `hitl_notification_service` | `freeze_until_replaced` | Formats/sends HITL approval notifications and processes signed callbacks. | HITL JSON/JSONL plus Guardian sender. | Later `guardian_hitl_approval_receipts`. | High: token/callback path can apply approval decisions. | Freeze decision authority until request mirror and decision binding are proven. Notification receipt only after sender/decision adapter exists. | Reference parent action/request id and token hash only. | Token TTL must not extend request TTL. | Notification/callback receipt later. | Invalid token remains invalid; SQLite cannot override token validation. | Token validation remains required; callback cannot create approval. |
| `hitl_pending_state_json` | `eligible_for_dual_write` | Active Cassandra HITL pending state file. | `/mnt/c/OpenClaw/logs/hitl_pending_state.json`. | `guardian_hitl_legacy_authority_refs`, `guardian_hitl_approval_requests`. | High if scanned/imported directly. | Do not scan raw file. Mirror only through the proposing code path after a record is created. | Same as HITL pending store. | Same as HITL pending store. | Legacy source ref plus request shadow receipt. | Raw file read is a stop condition. | No raw file ingest; source remains `authority_conflict_reconcile_first`. |
| `hitl_audit_jsonl` | `not_eligible` | Transition audit event log. | `/mnt/c/OpenClaw/logs/hitl_audit.jsonl`. | Later `guardian_hitl_approval_receipts`, `guardian_hitl_legacy_authority_refs`. | Medium: log import can preserve stale/incomplete claims. | Do not dual-write from old log. Future live events should write SQLite receipts directly. | Reference parent request id when live event occurs. | Inherit parent request TTL. | Live event receipt only. | Do not backfill by reading JSONL in dual-write lane. | Old logs are evidence, not authority. |
| `hitl_notifications_jsonl` | `retire_later` | Notification audit log. | `/mnt/c/OpenClaw/logs/hitl_notifications.jsonl`. | Later `guardian_hitl_approval_receipts`. | Medium: evidence log can drift. | Do not dual-write old records. Replace with SQLite notification receipts after proof. | Reference parent request id later. | Inherit parent request TTL. | Notification receipt later. | Keep file untouched until replacement is proven. | No truncation/deletion; receipt parity test later. |
| `hitl_pending_action_legacy` | `retire_later` | Older parallel pending action queue. | `hitl_pending_actions.json`, shared audit JSONL. | `guardian_hitl_legacy_authority_refs`. | High: duplicate old authority path. | Do not dual-write; prove unused before retirement. | None. | None. | Legacy ref only if cataloged later. | If active caller found, stop and reconcile. | Static search proves no current runtime caller before retirement. |
| `approval_log_md` | `retire_later` | Human-readable approval log. | Vault Markdown Approval Log. | Later generated operator read-model from SQLite receipts. | Medium: Markdown may be incomplete or edited. | Do not dual-write from Markdown. Keep human log until SQLite receipt export is proven. | Reference parent request id later. | Inherit parent request TTL. | Human-readable receipt export later. | Do not edit vault log in adapter lane. | SQLite receipt export can regenerate operator log. |
| `google_access_broker_approval_hook` | `freeze_until_replaced` | External Google API Class B/C approval hook. | Chief JSON approval plus broker audit JSONL. | `guardian_hitl_approval_requests`, `guardian_hitl_approval_receipts`. | High: external API write/send surface. | Freeze until Chief request mirror and explicit approved packet binding are proven. No new API calls. | Must bind capability, target account/surface, payload hash, and broker audit ref. | Explicit request TTL required. | Request and broker action receipt later. | Any adapter ambiguity keeps broker on old protective gate and blocks expansion. | No external API call; no Gmail/send expansion; explicit packet required. |
| `choice_pending_json_bridge` | `operator_decision_required` | Non-blocking workflow choice prompt. | `choice_pending.json`. | Separate workflow-choice substrate, not Guardian HITL. | Medium if confused with approval. | Keep out of this adapter unless operator requests a workflow-choice lane. | Separate choice id, not approval id. | Separate choice timeout only. | Choice receipt, not approval receipt. | If any action approval semantics appear, stop and route to Guardian contract. | Choice cannot approve send/runtime/destructive actions. |
| `repo_b_approval_tree` | `block_no_go` | Pre-split reference approval runtime. | Repo B legacy state/code. | None. | Critical if executed or imported. | Reference only. Do not adapt directly. | None. | None. | None. | Any attempt to run/import Repo B stops the lane. | Repo B not imported/executed. |
| `raw_command_or_freeform_shell_approval` | `block_no_go` | Forbidden approval shape. | None allowed. | None. | Critical arbitrary execution risk. | Reject at contract validation. | None. | None. | Block receipt only if attempted in synthetic validation. | Any required shell approval stops the lane. | Forbidden keys rejected recursively. |

## B. Dual-Write Contract

### Legacy Request Input

The adapter receives a legacy request only from an existing in-process caller. It must not scan raw JSON/JSONL files or import old state.

Allowed input fields:

- `source_surface_id`
- legacy request id, such as Chief approval id or HITL action id
- `actor` / requester / source agent
- typed action label or action type
- target label when safe
- payload hash
- payload schema version
- requested timestamp
- expiry timestamp or TTL
- risk tier / policy tier
- legacy source reference

Forbidden input and persistence:

- raw private payloads
- raw Telegram messages/logs
- secrets or env values
- raw file bodies
- raw command text or freeform shell
- bank/spreadsheet/private/client content

### Canonical Immutable Payload Output

Each dual-write request record must produce a canonical-shaped payload with:

- `approval_id`
- `action_type`
- `actor`
- `target`
- `payload_hash`
- `payload_schema_version`
- `source_intent_ref`
- `idempotency_key`
- `requested_at`
- `expires_at`
- `ttl_seconds`
- `authority_scope`
- `risk_tier`

The payload is observational until caller switch. It does not grant runtime authority.

### Idempotency Key Derivation

Preferred derivation:

```text
guardian_hitl_dual_write:<source_surface_id>:<legacy_id>:<payload_hash>
```

Fallback derivation when no stable legacy id exists:

```text
guardian_hitl_dual_write:<source_surface_id>:<actor>:<action_type>:<target>:<payload_hash>
```

Rules:

- Do not include raw payload text in persisted idempotency keys.
- Duplicate keys return the existing shadow/compatibility record.
- A completed, expired, or denied record must not be silently reactivated.

### TTL Rules

- Preserve the legacy TTL when it exists.
- Chief approval currently uses a 24 hour timeout; mirror that as `ttl_seconds=86400`.
- HITL pending actions carry `ttl_seconds`; preserve it.
- Notification token TTL must not extend the parent request TTL.
- Missing TTL is a stop condition for action-capable dual-write unless a code-defined default is explicitly documented.

### Exact Action Binding

Each SQLite record must bind:

```text
approval_id + action_type + actor + target + payload_hash + source_surface_id + source_intent_ref
```

Approval of unparsed text is invalid. Decision records must point to the same payload hash as the request.

### Receipt Record

Minimum receipts:

- `request_shadow_created`
- `request_shadow_failed`
- `decision_shadow_observed`
- `decision_shadow_rejected`
- `notification_shadow_observed`
- `legacy_sqlite_mismatch`

Receipts are proof/read-model records only until caller switch. They are not execution receipts.

### Legacy JSON Write Behavior

During compatibility dual-write:

- legacy JSON remains the live runtime state
- existing legacy write order and locking remain unchanged
- old JSON is not deleted, renamed, truncated, or reclassified as obsolete
- SQLite write failure must not corrupt or clear old JSON

For the first implementation slice, write the legacy record first, then attempt the SQLite observational record.

### SQLite Write Behavior

SQLite write behavior must be append-or-upsert by idempotency key:

- request mirror row
- legacy authority reference row
- request receipt row
- later decision/notification receipt rows

SQLite rows must be marked:

- `runtime_authority=false`
- `shadow_only=false` only after real dual-write wiring is active
- `dual_write_enabled=true` only for the exact implemented surface
- `caller_switched=false`
- `old_hitl_deleted=false`
- `legacy_json_authoritative=true`
- `raw_content_stored=false`

### Failure Handling

- Legacy write failure: do not create a valid-looking SQLite request.
- SQLite write failure after successful legacy write: legacy behavior continues, adapter health is marked failed, and callers are not switched.
- SQLite mismatch with legacy id/hash: mark SQLite record invalid and require operator review.
- Forbidden payload key: reject SQLite mirror and keep legacy behavior unchanged.
- Any need to read raw logs/private content/secrets: stop.

### Rollback Behavior

Rollback means disabling or not calling the adapter, not deleting old JSON.

Allowed rollback:

- stop dual-writing for the surface
- mark adapter health as failed in read-model
- leave legacy runtime behavior unchanged
- keep existing SQLite receipts as historical compatibility evidence

Forbidden rollback:

- delete old HITL JSON/JSONL
- clear pending approvals
- change old approval decisions
- switch callers back and forth without receipts

### Audit / Read-Model Output

Future implementation should produce:

- `generated/read_models/guardian_hitl_dual_write_compatibility.json`
- `generated/read_models/guardian_hitl_dual_write_compatibility_OPERATOR.md`

Required fields:

- `schema_version`
- `dual_write_enabled_surfaces`
- `legacy_json_authoritative=true`
- `runtime_authority_changed=false`
- `callers_switched=false`
- `old_hitl_deleted=false`
- `request_mirror_count`
- `decision_receipt_count`
- `notification_receipt_count`
- `mismatch_count`
- `adapter_health`
- `safe_to_import_cassandra_chief_memory=false`
- `safe_to_enable_remote_builder=false`
- `safe_to_expand_send_paths=false`

## C. What Dual-Write Must Not Do

Dual-write must not:

- switch callers
- delete old JSON/JSONL
- disable existing approval paths
- expand runtime authority
- approve raw command text
- approve freeform shell
- send Telegram/Gmail/email
- deploy
- activate runtime services
- enable remote-builder
- import Cassandra/Chief memory as authority
- treat `choice_pending.json` as Guardian approval authority
- execute Repo B code

Cassandra/Chief memory import remains unsafe unless a later lane proves request, decision, notification, and receipt equivalence for the relevant action classes.

## D. First Safe Implementation Slice

Recommended next lane:

**Guardian HITL SQLite Chief Approval Request Dual-Write v0**

Scope:

- Implement the SQLite dual-write compatibility helper and tables/read-model needed for request mirrors.
- Wire only the Chief approval request creation path if and only if tests prove fail-open legacy behavior.
- First eligible surfaces:
  - `chief_approval_brain`
  - `approval_pending_json`
- Old JSON remains authoritative.
- SQLite records are observational.
- No decision/callback/sender/caller switch yet.

Minimum behavior:

1. Chief builds the same legacy pending approval object it already builds.
2. Chief writes old JSON exactly as before.
3. Adapter writes a SQLite request mirror using safe metadata and payload hash.
4. Adapter failure does not block existing approval behavior.
5. Read-model reports mirror health and mismatches.

Why not start with Cassandra HITL:

- `hitl_pending_store` may carry richer action payloads and financial/send context.
- It currently has disabled-HITL proceed behavior for non-limit actions.
- It should wait until Chief request mirror and forbidden-payload tests are proven.

Why not start with Guardian listener/sender:

- Listener/sender paths deal with decisions and external notification transport.
- Decision receipts should wait until request mirrors exist.
- Sender instrumentation must not create new sends or retries.

## E. Safety Gates

Before `dual_write_enabled=true`:

- exact surface is named and tested
- old JSON remains authoritative
- SQLite write failure cannot change legacy behavior
- idempotency key deduplication is proven
- raw command/freeform shell is rejected
- generated read-model shows health and mismatch count

Before `callers_switched=true`:

- request, decision, notification, expiry, denial, and mismatch receipts are proven
- every current non-test caller has a canonical path
- old JSON and SQLite consistency is proven under synthetic failure cases
- operator approves the switch

Before `old_hitl_deleted=true`:

- no current Repo A non-test code reads/writes old JSON/JSONL
- legacy pending state is either resolved, expired, or explicitly reviewed
- SQLite receipts replace the required diagnostic value
- operator approves deletion/retirement

Before `safe_to_import_cassandra_chief_memory=true`:

- Chief request mirror is proven
- Cassandra HITL proposal mirror is proven
- old HITL authority conflicts are resolved or quarantined
- memory import creates no approval/send/runtime authority

Before `safe_to_enable_remote_builder=true`:

- remote-builder packet schema exists
- Guardian approval binds exact packet payload hash
- receipts prove approval without raw command/freeform shell
- executor boundary is separate, allowlisted, and explicitly approved

Before `safe_to_expand_send_paths=true`:

- send packet schema exists
- Guardian approval binds exact recipient/body hash/target
- notification and decision receipts are proven
- no send occurs without explicit approved packet
