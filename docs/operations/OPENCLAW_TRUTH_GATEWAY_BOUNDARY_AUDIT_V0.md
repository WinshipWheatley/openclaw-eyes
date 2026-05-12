# Truth Gateway Boundary Audit v0

This document defines and guarantees the deterministic boundaries between truth packet classifications in the OpenClaw Truth Reconciliation Gateway.

## 1. Classification Guarantees

- **MODEL_ALLOWED_VERIFIED**: Reserved for facts with passing source integrity, intact provenance, and either no verification required or verification evidence present. These are emitted as "hard truth" verified facts.
- **MODEL_ALLOWED_UNCERTAIN**: Emitted when source integrity and provenance are intact, but verification is required and evidence is missing. These MUST be prefixed with qualified language in the operator harness.
- **MODEL_BLOCKED**: Triggered by source hash mismatches, missing files, registry misalignment, or broken provenance. No `fact_text` from a blocked packet may ever reach the model or operator.

## 2. Audit Requirements (Automated)

The following guarantees are verified by `tests/test_truth_gateway_boundary_audit.py`:

1. **Isolation**: `MODEL_ALLOWED_UNCERTAIN` and `MODEL_ALLOWED_VERIFIED` are distinct constants and handled as distinct paths.
2. **Qualification**: Uncertain answers in `answer_harness.py` include provisional prefixes and metadata.
3. **Secrecy**: Blocked packets explicitly empty the `verified_facts` list and omit `fact_text`.
4. **Integrity Precedence**: Source hash mismatches result in `MODEL_BLOCKED` even if the fact would otherwise be classified as `UNCERTAIN`.
5. **No Runtime Authority**: Both Verified and Uncertain packets explicitly set `runtime_authority=False`.
6. **Visibility**: Status tools must preserve the boundary note explaining that truth status describes verification posture, not runtime authority.

## 3. Boundary Note

> Truth status describes verification posture, not runtime health or agent authority.

*Audit performed: Tuesday, May 12, 2026*
