# Guardian HITL SQLite Compatibility Adapter Plan v0

## Executive Summary

This plan defines how legacy and compatibility Guardian/HITL approval surfaces should move toward the canonical SQLite Operator Action / Guardian contract without changing runtime behavior in this lane.

The target remains:

`operator_action_sqlite_guardian_contract`

The adapter doctrine is conservative:

- Operator Action and the Guardian SQLite contract stay canonical.
- Existing Chief/Guardian and Cassandra HITL JSON paths remain compatibility-only until replacement is proven.
- Old JSON/JSONL state is not deleted, blocked, or called obsolete while active Repo A code still references it.
- Adapter work must start with shadow/read-model visibility, then tests, then carefully bounded dual-write only after proof.
- No adapter may approve raw command text, freeform shell, send, deploy, runtime activation, or remote-builder actions without an explicit canonical packet.

## A. Canonical Surfaces

| Surface | Current role | Future caller target | Must not be bypassed |
| --- | --- | --- | --- |
| `operator_action.py` | SQLite-backed request, approval, allowlisted local execution, and receipt path. | New action-capable code should target immutable Operator Action / Guardian contract records rather than JSON approval files. | Do not treat allowlisted local execution as general remote, send, deploy, or shell authority. |
| `operator_action_inbox.py` | Strict JSON request intake into Operator Action; never approves or executes by itself. | Future request packets should use strict schema intake and then wait for explicit approval. | Do not let inbox import become approval or execution. |
| `guardian_hitl_sqlite_authority_contract.py` | Metadata/read-model definition of the canonical approval contract. | Adapter lanes should use its required payload, decision, receipt, TTL, idempotency, and forbidden-key rules. | Do not mistake the contract read-model for live runtime wiring. |
| Fixed-scope Cassandra recovery clearance | SQLite recovery clearance for one bounded recovery action. | Keep as a special-case clearance model, not a general approval API. | Do not generalize it into agent/runtime restart authority. |

Canonical future callers must provide an immutable action identity, payload hash, idempotency key, TTL, exact action binding, explicit risk/authority scope, and receipt target. Raw command strings and freeform shell are forbidden.

## B. Compatibility-Only Surfaces

These surfaces remain active compatibility or transport surfaces. The first adapter step should observe and classify them without changing behavior.

| Surface | Current role | Current state store | Why compatibility-only | Adapter strategy | Risks | Required tests before wiring | Runtime behavior unchanged during adapter introduction |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `chief_approval_brain.py` | Tiered Chief/Guardian approval gate; blocking poll for operator decision. | `/mnt/c/OpenClaw/logs/approval_pending.json` plus vault approval log. | Active callers still depend on it, but it stores mutable action text instead of canonical immutable payloads. | `shadow_write_to_sqlite` first, then `translate_legacy_request_to_operator_action` after contract mapping is proven. | JSON drift, single pending slot, action text as authority. | Legacy pending request maps to immutable shadow record; no decision changes; stale ID rejection preserved; raw command strings rejected. | Yes for shadow/read-model phase. Dual-write must preserve old JSON as the live decision source until switch-over. |
| `chief_approval_policy.py` | Tier classifier and hard Tier 2 rules. | Code constants only. | Useful policy logic, not authority state. | `read_only_reference` then bind policy results into canonical risk fields. | String classification can be mistaken for complete authorization. | Policy tier appears as metadata only; no policy result can approve by itself. | Yes. |
| `chief_guardian_listener.py` | Telegram approval response listener for buttons and typed codes. | Delegates to Chief JSON and HITL JSON paths. | It is a transport/control surface, not the authority store. | `translate_legacy_request_to_operator_action` later; start with `read_only_reference` and callback classification. | Telegram listener can keep old JSON authority alive indefinitely. | Callback ID binding preserved; no raw messages exported; no send/reply expansion; SQLite decision receipts not required until adapter lane. | Yes for read-only classification. |
| `chief_guardian_sender.py` | Guardian bot approval notification transport. | No local approval state; external send transport. | Transport is useful, but sends are not authority. | `read_only_reference`, then notification receipt shadow records in a later lane. | Send-capable surface can be misused if treated as approval. | Button-bearing sends fail closed when Guardian token is unavailable; Cassandra bot is never fallback. | Yes if not called by new code. |
| `chief_router.py` approval fallback | Typed approval code fallback and HITL command route. | Delegates to Chief JSON and HITL JSON. | Compatibility UX fallback, not a canonical approval path. | `translate_legacy_request_to_operator_action` only after listener/contract parity is proven. | Router and listener semantics can diverge. | Approval brain has priority over workflow choice; stale approval codes are rejected; no freeform command is approved. | Yes for shadow/read-model phase. |
| `chief_watcher_brain.py` approval replay | Re-sends pending approval on cooldown. | `approval_pending.json` plus watcher state. | Notification replay only; it should not decide approval. | `read_only_reference`, then future notification receipt mirror. | Can keep `approval_pending.json` central longer than necessary. | Replay creates no approval decision; future mirror records notification-only event. | Yes. |
| `approval_pending.json` | Active Chief pending approval state. | Windows-side JSON file. | Active but noncanonical. Must not be deleted yet. | `shadow_write_to_sqlite` as legacy authority reference, later `retire_after_equivalent_proven`. | Mutable stale JSON remains authority. | Old JSON remains source of live decision during shadow phase; shadow records cannot execute. | Yes for shadow phase. |
| `hitl_pending_state.json` | Cassandra HITL pending action state. | Windows-side JSON file. | Active transition state for Cassandra HITL proposals. | `shadow_write_to_sqlite` first, then `translate_legacy_request_to_operator_action`. | JSON queue can be mistaken for truth and may allow proceed behavior when HITL is disabled. | Pending/action status, TTL, idempotency, no-send flags, and no-runtime flags are mirrored; shadow does not approve. | Yes for shadow phase. |
| `hitl_audit.jsonl` | HITL transition audit events. | Windows-side JSONL file. | Evidence-only while transition exists; not approval authority. | `read_only_reference` then SQLite receipts after canonical decisions exist. | JSONL may be mistaken for complete receipt authority. | Audit reference is evidence-only; missing JSONL cannot make an action safe. | Yes. |
| `hitl_notification_service.py` | Formats HITL approval notifications, signs callbacks, updates HITL action service. | `hitl_pending_state.json`, `hitl_audit.jsonl`, `hitl_notifications.jsonl`. | Token and notification ideas can survive, but decisions must move to SQLite. | `freeze_until_replaced` for approval decisions; notification receipt shadow later. | Send-capable JSON-backed action authority persists. | Token validation cannot become canonical decision without SQLite request binding; payload previews are not exported as raw authority. | Yes if not expanded. |

## C. Replace Surfaces

| Surface | Why replacement is required | Target equivalent | Migration risk | Required proof before replacement |
| --- | --- | --- | --- | --- |
| `hitl_pending_store.py` | JSON store backs Cassandra proposals and can return proceed when HITL is disabled for non-limit actions. | Canonical Guardian/Operator Action request, decision, and receipt tables with no-send/no-runtime defaults. | Breaking Cassandra proposal flow or accidentally enabling sends. | Synthetic Cassandra proposal creates canonical pending request; old JSON remains untouched during compatibility; approval cannot execute without explicit canonical receipt. |
| `hitl_action_service.py` | Useful validation/idempotency wrapper, but delegates authority to JSON state and has a placeholder approval hook. | Thin compatibility adapter over canonical contract records. | Treating approved JSON action as execution handoff. | Idempotency and TTL preserved; `_on_action_approved` cannot execute; approval records create receipts only. |
| Google broker approval dependency on `chief_approval_brain.request_approval` | External API writes are gated by mixed Chief JSON approval rather than immutable approved packets. | Explicit canonical approved packet for each Class B/C action. | Weak action binding for external API calls. | Broker calls require exact action binding, payload hash, and receipt; no send/API expansion occurs in adapter phase. |

## D. Retire-Later Surfaces

| Surface | Retirement condition | Proof needed before retirement | Must remain untouched now |
| --- | --- | --- | --- |
| `hitl_pending_action.py` and `hitl_pending_actions.json` | No current non-test/docs callers and equivalent SQLite request/receipt path exists. | Static reference map plus tests proving no runtime caller depends on it. | Do not delete old files or imports in this lane. |
| `hitl_notifications.jsonl` | SQLite notification receipts cover send/callback audit needs. | Notification receipt read-model matches or exceeds old audit visibility. | Do not truncate or rewrite JSONL. |
| Direct vault Approval Log Markdown authority | SQLite receipts are canonical and operator Markdown is generated from them. | Approval receipt read-model proves human log can be regenerated. | Do not edit the vault log or remove direct writes yet. |

## E. Blocked Surfaces

| Surface | Why blocked | Must never be adapted |
| --- | --- | --- |
| Repo B approval runtime | Repo B is pre-split reference only, not current authority. | Do not import, execute, or bridge directly to Repo B approval runtime. Port concepts only through Repo A contract/tests. |
| Raw command/freeform shell approval | This creates arbitrary execution authority and bypasses action binding. | Do not allow `command`, `cmd`, `shell`, `argv`, `exec`, `subprocess`, or freeform shell payloads into approval packets. |

## F. `chief_approval_bridge.py` / `choice_pending.json` Decision

Recommendation: treat `chief_approval_bridge.py` and `choice_pending.json` as a separate workflow-choice substrate, not as Guardian HITL approval authority.

Evidence:

- The file describes non-blocking multi-step Chief workflow choices.
- Its state is `choice_pending.json`, with prompt/options/answer/chosen fields.
- It has no immutable action payload hash, no approval receipt, and no exact action execution binding.
- `chief_router.py` gives actual approval replies priority over workflow-choice replies, which supports separation.

Disposition:

- Keep out of the Guardian HITL SQLite adapter scope.
- Do not block or delete it in this lane.
- Future work should decide whether workflow choices need their own SQLite-backed choice record/read-model.
- It should not approve sends, external actions, runtime actions, or destructive actions.

Short recommendation: `separate_workflow_choice_substrate`.

## G. Adapter Sequence

1. `shadow/read-model adapter`
   - Add a read-only or shadow metadata adapter that describes legacy JSON approval state as compatibility references.
   - It must not approve, deny, send, execute, migrate, or delete anything.

2. `tests`
   - Prove every compatibility surface maps to a canonical target or explicit non-target.
   - Prove raw command/freeform shell approval remains rejected.
   - Prove old JSON remains active compatibility until replacement is proven.

3. `dual-write compatibility`
   - Only after shadow records are tested, write canonical SQLite request/receipt shadows while old JSON remains the live runtime decision source.
   - This step is runtime behavior adjacent and needs a separate implementation lane.

4. `prove receipts`
   - Demonstrate canonical request, decision, notification, and receipt records cover the same cases as old JSON/JSONL without raw/private content export.

5. `switch canonical callers`
   - Move callers to canonical Operator Action / Guardian contract records only after receipts and fallback behavior are proven.

6. `retire old JSON only after proof`
   - Delete, disable, or mark obsolete only after no current Repo A code path reads/writes the old state outside tests/docs and the operator approves retirement.

## H. Safety Gates

These remain unsafe until adapters are implemented and proven:

- Cassandra/Chief memory import as authority.
- Remote-builder bridge.
- Send-path expansion.
- General recovery/runtime approvals.
- External API/model/deploy actions.
- Any approval of raw command text or freeform shell.

The next safe lane should be the first sequence step only: a non-executing Guardian HITL SQLite shadow/read-model adapter.
