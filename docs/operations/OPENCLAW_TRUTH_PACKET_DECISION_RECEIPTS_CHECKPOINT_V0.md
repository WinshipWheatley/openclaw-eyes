# OPENCLAW TRUTH PACKET DECISION RECEIPTS CHECKPOINT V0

- **Date:** 2026-05-12
- **Commit:** 7c4d68a
- **Status:** Operational — Durable decision logging and operator visibility are active.

## Overview
Truth Packet Decision Receipt Logging v0 introduces the audit trail for every decision made by the Truth Reconciliation Gateway. Every time a canonical fact is evaluated for a model packet—whether it is verified, uncertain, or blocked—a structured receipt is recorded in the SQLite ledger. This ensures that the system's "boundary logic" is fully transparent, auditable, and surfaced to the operator without exposing sensitive fact content.

## 1. What is Now Built

- **`truth_packet_decision_receipt` Contract**: A formal specification for audit metadata that records packet status, boundary-crossing decisions, and provenance without storing raw content.
- **Decision Writer (`append_truth_packet_decision_receipt`)**: A hardened writer in `business_ops_ledger.py` that enforces redaction and ensures `MODEL_BLOCKED` packets never report a boundary crossing.
- **Fact Content Redaction**: Mechanical enforcement that `fact_text` is never stored in the audit ledger, even if accidentally passed to the writer.
- **Gateway Integration**: `scripts/truth_reconciliation_gateway.py` now supports opt-in receipt logging via `--record-receipt` and `--receipt-db`.
- **Harness Integration**: `scripts/answer_harness.py` now supports opt-in receipt logging for every fact evaluated during an operator query.
- **Receipt Visibility Layer**:
    - **`truth_substrate_status.py`**: Surfaces total decision counts, breakdown by status (VERIFIED/UNCERTAIN/BLOCKED), and metadata from the latest decision.
    - **`generate_operator_status.py`**: Injects `[TRUTH_DECISION]` receipts into the recent verification timeline.
    - **`orientation_snapshot.py`**: Integrates decision receipt counts into the core truth substrate report.
- **Read-Only Visibility**: All visibility tools use `mode=ro` (URI mode) to ensure status checks never trigger side effects or writes.

## 2. Safety Invariants

- **Default Opt-In**: Receipt logging is strictly opt-in; no receipts are written by default unless explicit flags are provided.
- **Fact Privacy**: Blocked receipts never expose `fact_text`. Verified/Uncertain receipts only record that content *passed* the boundary, not the content itself.
- **Non-Authoritative**: Receipts are audit metadata only. `runtime_authority` is strictly `false`, and `execution_authority` is `0`.
- **Passive Logging**: Recording a receipt does not mutate truth tables, source hashes, or registry entries. It is a descriptive observer, not a controller.
- **Audit != Health**: Receipt visibility proves that the gateway logic is running, but it does not independently prove live agent health or "authority."

## 3. Commit Trail

- **1c83081** docs(knowledge): define truth packet decision receipts
- **1259317** feat(ledger): add truth packet decision receipt writer
- **9e06c2c** feat(knowledge): record truth packet decision receipts
- **b871143** feat(knowledge): add answer harness receipt opt-in
- **7c4d68a** feat(knowledge): surface truth packet decision receipts

## 4. What is Intentionally NOT Built

- **No Default Writes**: No mandatory production receipt logging yet.
- **No Cassandra/Chief/Niles Wiring**: Agents do not yet consume or react to receipt counts.
- **No Runtime Authority**: The system does not grant execution power based on receipt volume.
- **No Truth Upgrades**: Decision receipts do not promote facts or rebaseline hashes.
- **No Raw Content Storage**: `fact_text` remains strictly outside the receipt layer.
- **No Live Agent Health Claims**: The status reports verify the *substrate*, not the active reasoning state of an LLM.

## 5. Tests and Checks

- **Contract Test**: `tests/test_truth_packet_decision_receipts_contract.py` (Doc-contract alignment).
- **Writer Test**: `tests/test_truth_packet_decision_receipts_writer.py` (Redaction and boundary enforcement).
- **Gateway Integration Test**: `tests/test_truth_gateway_receipt_integration.py` (Terminal state logging).
- **Answer Harness Test**: `tests/test_answer_harness.py` (Harness-to-gateway receipt propagation).
- **Visibility Test**: `tests/test_truth_packet_visibility.py` (Read-only status reporting and privacy).
- **Status Consistency**: `python3 scripts/generate_operator_status.py --check` (Verified current).

## 6. Recommended Next Safe Lanes

1. **Operator Query Path**: Broaden the use of `answer_harness.py` for standard operator inquiries, utilizing `--record-receipt` for manual audit-trails.
2. **Manual Smoke Test**: Perform a controlled, one-off query against the production ledger with `--record-receipt` to verify visibility in the live operator status.
3. **Agent Read-Only Consumption**: Introduce logic in Chief or Cassandra to display "Recently Verified Truths" based on the last N success receipts.
4. **Additional Uncertain Cases**: Expand the Gateway to handle further narrow cases (e.g., stale timestamps) now that every outcome is auditable.
