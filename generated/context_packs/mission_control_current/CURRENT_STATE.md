# Current State

This file summarizes selected generated read-models for an external AI/context consumer.
It is a source bundle summary, not truth promotion.

Selected posture:
- Agent runtime readiness: agents=6, ready=6, status=ready_for_dry_run, smoke_passed=6, smoke_failed=0.
- Intent Router: intents=5, needs_review=1.
- Agent Lanes: agents=6, lanes=6.
- Operator Actions: requests=2, pending=1, completed=1.
- Agent Work Packets: packets=1, execution_allowed=false.
- `context_selection.json`: schema=context_selection_read_model_v0.
- Dropped Intents: total=9, unresolved=2, deferred=6.
- Markdown Evidence: sources=6, items=103, truth_promotion=false.
- Project Capsules: capsules=1, client_data_access=false.
- Recent File Context: candidates=100, latest_resolution=none.
- Report Bridge: packages=0, rejected=0.

Generated Current State excerpt:

<!--
GENERATED FILE - DO NOT EDIT MANUALLY
This file is programmatically generated from repository evidence.
Durable truth comes from receipts, tests, and committed source.
-->

# GENERATED CURRENT STATE
## 1. Confirmed System State
- Ledger Status: active
- Active Handoff: This handoff is the train. The roadmap authority is 24_files/01_PROJECT_SOURCE_SET_INDEX_AND_RAIL_MAP.md.
- SQLite Ledger v0 exists, and Cassandra `handle()` is wired to record event/packet receipts.
- Business Ops Packet v0 is defined for intent-based capability gating.
- Operator Doctrine root files exist in `Operator/`.
- Orientation Snapshot v0 tool exists and is verified (read-only).
- The current checkpoint may use the active handoff, but durable truth comes from committed repo docs/source, receipts, tests, and explicit operator promotions.

## 2. Recent Verification Receipts
Deterministic evidence proofs from the ledger (excludes status self-checks).
Strongest recent clean proof: [PASS] business_ops_ledger_tests head=942d3e00

- 2026-05-11 17:09 [APPROVAL_REQUEST] [SQLITE_VERIFIED] Manual test of approval request visibility (No Decision/No Execution)
- 2026-05-10 22:37 [PASS] business_ops_ledger_tests exit=0 head=942d3e00
- 2026-05-10 22:37 [PASS] cassandra_status_wiring_tests exit=0 head=942d3e00
- 2026-05-10 22:37 [PASS] orientation_snapshot_smoke exit=0 head=942d3e00
- 2026-05-10 22:37 [PASS] ledger_inspector_summary exit=0 head=942d3e00

### Module Atlas Artifact Checkpoints
**Evidence:** committed docs/code artifacts have metadata-only SQLite checkpoint receipts.
**Boundary:** recorded checkpoint only; not runtime authority. No full Markdown/code body is ingested.
**Blocked:** no module, agent, broker, customer deployment, or runtime behavior is activated or authorized by these receipts.
**Next safe move:** review docs/tests/receipts; runtime activation still requires a separate approved lane.

| Artifact | Receipt Time | Checkpoint | Authority Boundary |
| --- | --- | --- | --- |
| `tests/test_module_manifest_validation.py` | 2026-05-12 21:40 | recorded `validation-proven` | `authority=no-runtime-authority`; `runtime_activation=false`; `sqlite=receipt-record-only`; `body=not-ingested` |
| `scripts/validate_module_manifests.py` | 2026-05-12 21:40 | recorded `validation-proven` | `authority=no-runtime-authority`; `runtime_activation=false`; `sqlite=receipt-record-only`; `bod...
