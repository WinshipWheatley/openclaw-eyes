# Operator Attention Promotion Contract v0

## ELIWINSHIP Summary

This contract decides what should happen to a stored thing now. A SQLite row, read-model, Markdown note, worker report, receipt, or stable-map summary does not automatically deserve helm attention. It must be classified into helm attention, world lane, proof detail, holding cell, memory candidate, cue candidate, quiet-with-proof, quarantine, or rejection.

## Lifecycle

- `OBSERVED`
- `CLASSIFIED`
- `PROOF_LINKED`
- `MEMORY_CANDIDATE`
- `HELM_ATTENTION`
- `WORLD_LANE`
- `PROOF_DETAIL`
- `HOLDING_CELL_ITEM`
- `CUE_CANDIDATE`
- `READY_FOR_SECURITY_DELTA_REVIEW`
- `READY_FOR_WORLD_PREVIEW`
- `QUIET_WITH_PROOF`
- `PARKED`
- `QUARANTINED`
- `OBSOLETE_OR_REJECTED`
- `UNKNOWN_FAIL_CLOSED`

## Destinations

- `HELM_ATTENTION`
- `WORLD_LANE`
- `PROOF_EVIDENCE_DRAWER`
- `HOLDING_CELL`
- `MEMORY_CANDIDATE_INBOX`
- `CUE_CANDIDATE`
- `SECURITY_DELTA_REVIEW`
- `CHIEF_RECONCILIATION`
- `HERMES_ARCHITECTURE_REVIEW`
- `GUARDIAN_REVIEW`
- `QUIET_WITH_PROOF`
- `QUARANTINE`
- `REJECT_OR_OBSOLETE`

## Attention Classes

- `NEEDS_OPERATOR_DECISION`
- `NEEDS_PROOF`
- `NEEDS_CONTEXT`
- `NEEDS_SECURITY_GATE`
- `NEEDS_WORLD_TRANSITION`
- `NEEDS_CHIEF_RECONCILIATION`
- `NEEDS_HERMES_REVIEW`
- `NEEDS_GUARDIAN_REVIEW`
- `SYSTEM_HEALTH_WARNING`
- `BUILT_NOT_SURFACED`
- `DUPLICATE_OR_OVERLAP`
- `BLOCKED_NOT_AUTHORIZED`
- `HOLDING_CELL`
- `CUE_CANDIDATE`
- `QUIET_WITH_PROOF`
- `UNKNOWN_FAIL_CLOSED`

## Default Records

- `capital_hilton_proof_gap`: `NEEDS_PROOF` -> `HELM_ATTENTION`. Next: Classify protected finance proof metadata; Finance World remains preview-only.
- `stable_map_receipt_current`: `QUIET_WITH_PROOF` -> `PROOF_EVIDENCE_DRAWER`. Next: None; keep raw mirror mismatch as proof/detail.
- `markdown_knowledge_atlas_visibility_gap`: `BUILT_NOT_SURFACED` -> `PROOF_EVIDENCE_DRAWER`. Next: Consider stable-map/app visibility later; no new crawler needed.
- `future_invoicing_state_machine_audit`: `HOLDING_CELL` -> `HOLDING_CELL`. Next: Keep parked until finance/account/payment gates exist.
- `autonomous_capital_pipeline_experiment`: `HOLDING_CELL` -> `HOLDING_CELL`. Next: No action; preserve until future gates exist.
- `orphaned_capability_found`: `BUILT_NOT_SURFACED` -> `CHIEF_RECONCILIATION`. Next: Classify, reconcile, and do not activate.
- `operator_missing_terrain_memory`: `NEEDS_CONTEXT` -> `MEMORY_CANDIDATE_INBOX`. Next: Capture as candidate, not proof.
- `security_delta_needed_for_new_tool`: `NEEDS_SECURITY_GATE` -> `SECURITY_DELTA_REVIEW`. Next: Fail closed until reviewed.

## Quiet Helm

- Quiet means classified, receipted, and retrievable. It does not mean forgotten.
- Quiet items stay available in proof drawers, holding cells, memory inboxes, or lane drill-downs.

## Shared Fix Paths

- `protected_finance_proof_metadata_intake` links Capital Hilton, Cassandra and Finance World; solving once may update several lanes only after receipts and gates exist.

## Capture And Security Delta

- Operator answers are memory candidates, not proof.
- A cue candidate is not executable.
- A holding-cell item is not queued.
- New authority, tool use, account access, automation, runtime behavior, or financial action routes to Security Delta Review or fails closed.

## Machine Proof

- Default record count: `8`.
- Quiet helm policy present: `true`.
- Shared fix path present: `true`.
- All authority flags false: `true`.
- Action authority granted: `false`.
- Auto-promotion allowed: `false`.
- Content hash: `sha256:2c132f3d84b0f76cddfc4d6d4b809f186b5ba13d3926653c5b2253d6441c4707`.
