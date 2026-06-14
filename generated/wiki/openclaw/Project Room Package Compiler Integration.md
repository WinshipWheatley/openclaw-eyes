# Project Room Package Compiler Integration

Status: `PROJECT_ROOM_PACKAGE_COMPILER_INTEGRATION_READY`

Serious workflow, synthesis, repair, and LM2 packages must compile through source-room gates before synthesis or worker handoff.

## Package Classes

- `simple_answer`: project room `false`, proof bundle `false`. Trivial readback/system question may bypass project room when current proof supports the answer.
- `proof_to_response`: project room `false`, proof bundle `true`. Proof-to-response may use current proof bundle freshness/redaction without a full project room.
- `serious_synthesis`: project room `true`, proof bundle `false`. Serious synthesis packages require a project room.
- `client/business_draft`: project room `true`, proof bundle `false`. Client/business drafts require a project room when proposal/history or multiple sources are used.
- `code/build/repair`: project room `true`, proof bundle `false`. Code/build/repair packages require a project room or repair room before synthesis.
- `LM2 worker package`: project room `true`, proof bundle `true`. LM2 worker packages require a project/proof room unless explicitly trivial.

## Block Rules

- Block serious synthesis when source inventory is missing.
- Block synthesis on unresolved critical conflicts.
- Block unsupported claims when missing context is unresolved.
- Block stale/superseded sources treated as current truth.
- Block version-family work when duplicate/version report is missing.
- Block repeated or failed work when decision trace is missing.
- Block LM2 worker packages from raw folder dumps, full logs by default, stale truth, unreviewed duplicate weighting, and invention from missing context.

## Examples

- `finance_capital_hilton_payment_watch`: allowed; next safe action: Explain payment evidence is missing and invite proof attachment; do not mark paid or touch ledger.
- `business_development_capital_hilton_followup`: blocked; next safe action: Surface the conflict and request an operator decision.
- `build_review_packet`: allowed; next safe action: Summarize review history; keep resolved packet out of active work.
- `niles_controller_mapping`: blocked; next safe action: Name the missing context and avoid unsupported factual claims.
- `self_heal_repair`: allowed; next safe action: Propose repair package with validation and rollback plan; do not spawn workers.
- `lm2_pilot`: allowed; next safe action: Compile a bounded LM2 pilot package with project/proof refs only; do not spawn a worker.

## Boundary

No model invocation, local runtime connection, worker spawn, business action, email, browser/Gmail/Coupa, ledger/workbook mutation, paid marking, submission, PDF export, or push is granted.
