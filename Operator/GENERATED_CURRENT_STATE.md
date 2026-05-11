<!--
GENERATED FILE - DO NOT EDIT MANUALLY
This file is programmatically generated from repository evidence.
Durable truth comes from receipts, tests, and committed source.
-->

# GENERATED CURRENT STATE
## 1. Confirmed System State
- Ledger Status: active (62 events)
- Active Handoff: This handoff is the train. The roadmap authority is 24_files/01_PROJECT_SOURCE_SET_INDEX_AND_RAIL_MAP.md.
- SQLite Ledger v0 exists, and Cassandra `handle()` is wired to record event/packet receipts.
- Business Ops Packet v0 is defined for intent-based capability gating.
- Operator Doctrine root files exist in `Operator/`.
- Orientation Snapshot v0 tool exists and is verified (read-only).
- The current checkpoint may use the active handoff, but durable truth comes from committed repo docs/source, receipts, tests, and explicit operator promotions.

## 2. Recent Verification Receipts
Deterministic evidence proofs from the ledger (excludes status self-checks).
Strongest recent clean proof: [PASS] business_ops_ledger_tests head=80225524

- 2026-05-10 21:08 [PASS] business_ops_ledger_tests exit=0 head=80225524
- 2026-05-10 21:07 [PASS] cassandra_status_wiring_tests exit=0 head=80225524
- 2026-05-10 21:07 [PASS] orientation_snapshot_smoke exit=0 head=80225524
- 2026-05-10 21:07 [PASS] ledger_inspector_summary exit=0 head=80225524
- 2026-05-10 21:06 [PASS] [DIRTY] business_ops_ledger_tests exit=0 head=56ba011b

> **Note**: Proof receipts prove only that specific checks ran at a commit/environment. They do not claim whole-system health.

## 3. Active Lane & Doctrine
Hardening the "Business Ops Spine" (deterministic intent, bounded capability, SQLite Ledger) and canonicalizing the "Operator Doctrine" (North Star, Manifesto, Anti-drift) into a concise Orientation Contract.

## 4. Tool & Surface Boundaries
### Allowed Tools
- Repository-local file reading and surgical editing.
   - Shell commands for status, testing, and non-destructive operations.
   - Read-only repo inspection and test commands are allowed for Orientation Snapshot; ledger writes require a separate bounded lane.
   - Classification of intent via `operator_intent_core.py`.

### Forbidden Surfaces
- Private roots (`.google-secrets`, `.chief.env`, etc.).
   - Legal/Client/Private folders.
   - External provider/model APIs without an Action Covenant.
   - Credentials, tokens, and billing logic.

## 5. North Star
Make daily life lighter without becoming hidden authority. The computer becomes a natural extension of the operator. The machine carries the weight; the operator keeps the crown.

## 6. Safety & Staleness
- **Runtime Health**: Not checked by this generator. Refer to `docs/operations/` or live diagnostics.
- **Staleness**: This file is stale if the git HEAD has changed or if confirmed facts (e.g. active lane, contract items) have been modified since the generation timestamp.
- **Privacy**: No PII or raw sensitive data is stored in this read-model.