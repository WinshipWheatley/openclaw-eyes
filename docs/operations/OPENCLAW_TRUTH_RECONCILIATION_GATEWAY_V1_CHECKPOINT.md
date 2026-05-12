# OPENCLAW TRUTH RECONCILIATION GATEWAY V1 CHECKPOINT

- **Date:** 2026-05-12
- **Commit:** b12a3ff
- **Status:** Stable — Deterministic reconciliation and uncertainty-aware model packets are operational.

## Overview
The Truth Reconciliation Gateway v1 extends the read-only safety gate of v0 into a system capable of controlled mechanical repair, deterministic mismatch invalidation, and uncertainty-aware truth packets. It ensures that the agent receives the best possible evidence—ranging from hard verified truth to qualified provisional facts—while maintaining absolute boundaries against corrupted or mismatched data.

## 1. What is Now Built

- **v0 Read-Only JIT Source Integrity Gate**: The foundational check that ensures disk state matches recorded registry state before any fact is surfaced.
- **v1 Mechanical Repair Path**: Controlled path to update `hash_status` to `'current'` if the disk hash matches the recorded `source_content_hash` but the status was stale.
- **v1 Mismatch Invalidation Path**: Deterministic path to mark a source as `'changed'`, set `verification_required = 1`, and downgrade `truth_status` upon detection of a JIT hash mismatch.
- **Post-Reconciliation State Machine**: Implementation of the **discard / re-query / re-check** loop, ensuring that facts are never surfaced from a session that performed a database mutation.
- **Truth Packet Posture**:
    - **MODEL_ALLOWED_VERIFIED**: Hard truth facts with passing integrity and no pending verification requirements.
    - **MODEL_ALLOWED_UNCERTAIN**: Provisional facts where provenance is intact but verification evidence is missing.
    - **MODEL_BLOCKED**: Terminal failure where integrity or provenance checks fail; `fact_text` is strictly withheld.
- **Narrow Uncertain Path**: Implementation of the first uncertainty trigger: `verification_required = 1` with missing `verification_evidence_id`.
- **Answer Harness Qualification**: `answer_harness.py` now detects `MODEL_ALLOWED_UNCERTAIN` packets and automatically prefixes answers with qualified language (e.g., "Based on currently available evidence...").
- **Operator Visibility**: Integrated Truth Gateway posture (VERIFIED/UNCERTAIN/BLOCKED counts) into Orientation Snapshots and `Operator/GENERATED_CURRENT_STATE.md`.
- **Boundary Audit**: Comprehensive test suite ensuring that verified, uncertain, and blocked paths remain strictly isolated and cannot be blurred.

## 2. Safety Invariants

- **No model answer from pre-reconciliation data**: If a database mutation occurs, the gateway forces a fresh query.
- **Source hash mismatch remains MODEL_BLOCKED**: Uncertainty does not excuse integrity failures.
- **Blocked packets never expose fact_text**: If a fact is blocked, its content is zeroed out before reaching the model.
- **Uncertain packets are provisional, not verified**: Must use qualified language and cannot be used for high-stakes authority.
- **Uncertain packets do not imply runtime authority**: `runtime_authority` is explicitly `False`.
- **No LLM-authored truth writes**: Reconciliation is purely mechanical and deterministic.
- **No source_content_hash replacement on mismatch**: Rebaselining requires an explicit, separate ingestion process.

## 3. Commit Trail

- **2b09a6d** docs(knowledge): checkpoint truth reconciliation gateway (v0)
- **f1582a2** docs(knowledge): plan truth reconciliation gateway v1
- **297bb4f** feat(knowledge): add truth gateway mechanical repair
- **73d0b55** docs(knowledge): clarify uncertainty-aware truth packets
- **7fecf69** feat(knowledge): add truth gateway mismatch invalidation
- **576f323** docs(knowledge): plan uncertainty-aware truth packets
- **a8e2962** feat(knowledge): add uncertainty packet status contract
- **41acbef** feat(knowledge): add narrow uncertain truth packet path
- **dcbdc22** feat(knowledge): qualify uncertain truth answers
- **b61f3cb** feat(knowledge): surface truth gateway packet posture
- **b12a3ff** test(knowledge): audit truth gateway packet boundaries

## 4. What is Intentionally NOT Built

- **No broad uncertain routing**: Uncertainty is limited to specifically defined narrow paths (missing evidence).
- **No stale/historical candidate exposure after mismatch**: Mismatched facts are terminal blocks, not downgraded to uncertain.
- **No Cassandra/Chief/Niles wiring**: These agents do not yet consume truth packets directly; consumption remains gated and read-only.
- **No runtime authority**: The system remains descriptive of truth, not an execution engine.
- **No SQLite mutation except allowed reconciliation paths**: Broad database writes are forbidden.
- **No semantic truth upgrades**: The system does not automatically promote facts to `test_verified` without evidence.
- **No automatic source hash rebaseline**: Changes to source documents must be acknowledged through ingestion.

## 5. Tests and Checks

- **Gateway Tests**: `tests/test_truth_reconciliation_gateway.py` (25 PASS)
- **Answer Harness Tests**: `tests/test_answer_harness.py` (7 PASS)
- **Boundary Audit Tests**: `tests/test_truth_gateway_boundary_audit.py` (6 PASS)
- **Status Checks**: `python3 scripts/generate_operator_status.py --check` (Verified)

## 6. Recommended Next Safe Lanes

1. **Truth Packet Decision Receipt Logging**: Record every gateway decision (Allow/Block/Uncertain) into the SQLite Ledger for auditability.
2. **Additional Narrow Uncertain Cases**: Introduce further uncertainty triggers (e.g., stale timestamps or partial provenance) only after receipt logging is in place.
3. **Operator Query Path**: Broaden the use of `answer_harness.py` as the primary natural-language query interface for the operator.
4. **Agent Consumption**: Begin read-only consumption of truth packets by Cassandra or Chief, ensuring they respect the qualified boundaries of uncertain packets.
