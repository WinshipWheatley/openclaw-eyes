# Active Machinery Operator Disposition v0

This is a review-only disposition packet for verified active-machinery findings. It does not modify runtime behavior, move files, delete files, enable sends, enable daemons, or bind findings to `module_registry` / `openclaw_nodes`.

## Disposition Vocabulary
- `keep_canonical`: keep as canonical docs/generated/read-model/support surface.
- `keep_test_only`: keep as test-only; do not treat as runtime machinery.
- `keep_reference_only`: keep as reference, not authority.
- `wrap_with_guardian`: may only run behind immutable Operator Action / Guardian approval and receipts.
- `replace_with_governed_path`: legacy runtime shape should be replaced by current governed substrate.
- `block_no_go`: do not run; needs explicit replacement or operator exception.
- `retire_later`: likely superseded, but do not delete until replacement proof exists.
- `operator_decision_required`: insufficient evidence or high consequence; decide later.

## High-Risk Disposition Table
| File | Disposition | Affects | What must happen before it can run |
| --- | --- | --- | --- |
| `builder_watcher.sh` | `block_no_go` | remote builder | Replace with Work Board / Operator Action handoff and prove bounded receipts; do not run as a watcher. |
| `cassandra_listener.py` | `replace_with_governed_path` | Cassandra, Guardian/HITL, send paths, sync | Route through governed intake, Operator Action, and Guardian/HITL receipts before any live listener use. |
| `cassandra_watcher.py` | `retire_later` | Cassandra, send paths | Prove it is still needed; otherwise retire after equivalent governed path is confirmed. |
| `chief_brainstorm_watcher.py` | `retire_later` | Chief | Keep disabled until an operator-approved use case proves it should become a governed Work Board source. |
| `chief_email_brain.py` | `wrap_with_guardian` | Chief, Guardian/HITL, send paths | Require immutable approved packet, no-send default, and Guardian receipt before any external send behavior. |
| `chief_guardian_listener.py` | `replace_with_governed_path` | Chief, Guardian/HITL, send paths, sync | Use SQLite-backed Operator Action/HITL surfaces; keep legacy listener compatibility-only until replacement proof exists. |
| `chief_guardian_sender.py` | `wrap_with_guardian` | Chief, Guardian/HITL, send paths | Allow only approved notification packets and receipts; no raw or freeform send authority. |
| `chief_listener.py` | `replace_with_governed_path` | Chief, Guardian/HITL, send paths, sync | Prove caller scope, HITL boundary, and receipt path before live listener activation. |
| `chief_sender.py` | `wrap_with_guardian` | Chief, send paths | Require approved immutable packet, recipient binding, no raw command text, and receipt proof. |
| `chief_watcher_brain.py` | `block_no_go` | Chief, Guardian/HITL | Replace with bounded Work Board / Operator Action workflow; do not run watcher/process behavior directly. |
| `producer_listener.py` | `replace_with_governed_path` | Producer/Niles, send paths, sync | Define Producer/Niles module boundary and route actions through Guardian/HITL before activation. |
| `retry_send_demo_dashboard.sh` | `keep_reference_only` | send paths | Retired from the runtime root; stale scan rows are historical evidence only. Restore only through a new no-send review fixture or approved bounded demo packet. |
| `scripts/run_producer_listener.sh` | `block_no_go` | Producer/Niles | Do not run until Producer listener has a governed contract and operator-approved activation lane. |
| `send_demo_dashboard.py` | `keep_reference_only` | send paths | Retired from the runtime root; stale scan rows are historical evidence only. Restore only through a new no-send review fixture or approved bounded demo packet. |
| `tests/test_cassandra_email_thread_analysis.py` | `keep_test_only` | Cassandra, send paths | Run only as a focused test under normal test validation; never treat it as runtime machinery. |
| `tests/test_chief_listener_lifecycle.py` | `keep_test_only` | Chief, send paths, sync | Run only as a focused test under normal test validation; never treat it as runtime machinery. |
| `tests/test_send_truth.py` | `keep_test_only` | send paths | Run only as a focused test under normal test validation; never treat it as runtime machinery. |

## Major Group Disposition
| Group | Count | Disposition | Next action |
| --- | ---: | --- | --- |
| Verified high-risk active machinery | 17 | `operator_decision_required` | Use the high-risk item table; tests stay test-only, live listeners/senders need governed replacement or Guardian wrapping. |
| Likely active machinery needing operator review | 76 | `operator_decision_required` | Run a later no-execution static review lane by subgroup: HITL, sync, importer/exporter, and plugin/tool surfaces. |
| False positives / safe docs and generated files | 316 | `keep_canonical` | Keep as documentation/generated artifacts unless a future lane proves a specific file is executable. |
| Repo B reference-only machinery | 1 | `keep_reference_only` | Inspect only as reference in explicit reconciliation lanes; never execute Repo B code. |
| Send/API surfaces | 7 | `wrap_with_guardian` | Keep no-send by default; require immutable packet, exact binding, Guardian approval, and receipts. |
| Sync/bridge surfaces | 151 | `operator_decision_required` | Review safe canonical sync paths separately from launchers/watchers before any activation. |
| Approval/HITL surfaces | 134 | `replace_with_governed_path` | Reconcile legacy paths against current Guardian/HITL contract before any caller switch. |
| Unknown / needs deeper review | 357 | `operator_decision_required` | Leave untouched until a narrower static review lane is approved. |

## Boundaries Preserved
- Runtime changed: `false`.
- Files moved or deleted: `false`.
- Repo B executed: `false`.
- Agents/sends/daemons enabled: `false`.
- Gemini output treated as truth: `false`.

## Next Recommended Lane
Active Machinery High-Risk Quarantine Spec v0
