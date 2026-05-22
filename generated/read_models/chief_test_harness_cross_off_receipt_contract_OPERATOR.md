# Chief Test Harness / Cross-Off Receipt Contract v0

## ELIWINSHIP Summary

This contract defines when Chief can later say work is complete enough to quiet the helm. A worker saying done is not enough. Chief needs source refs, changed artifacts, tests or validation proof, receipts, boundary checks, and required Operator/Guardian/Hermes review. Cross-off never deletes the source note; it creates a completion receipt or candidate.

## Completion Statuses

- `NOT_STARTED`
- `IN_PROGRESS`
- `WORKER_REPORTED_DONE`
- `VALIDATION_PASSED`
- `VALIDATION_FAILED`
- `COMPLETED_WITH_PROOF`
- `COMPLETED_NEEDS_OPERATOR_REVIEW`
- `COMPLETED_NEEDS_GUARDIAN_REVIEW`
- `COMPLETED_NEEDS_HERMES_REVIEW`
- `PARTIAL_REQUEUE_REQUIRED`
- `FAILED_REPAIR_REQUIRED`
- `PARKED_WITH_PROOF`
- `DUPLICATE_OR_MERGED`
- `REJECTED_OR_OBSOLETE`
- `QUARANTINED`
- `UNKNOWN_FAIL_CLOSED`

## Reconciliation States

- `NOT_RECONCILED`
- `MATCHED_TO_MARKDOWN_ITEM`
- `MATCHED_TO_CUE_CANDIDATE`
- `MATCHED_TO_WORKER_REPORT`
- `MATCHED_TO_PACKAGE`
- `MATCHED_TO_STABLE_MAP_LANE`
- `MATCHED_TO_WORLD_LANE`
- `MATCHED_TO_RECEIPT`
- `BUILT_NOT_SURFACED`
- `SURFACED_NOT_VERIFIED`
- `RECONCILED_WITH_PROOF`
- `RECONCILED_NEEDS_REVIEW`
- `UNKNOWN_FAIL_CLOSED`

## Default Harness Receipts

- `security_pass_surface_checkpoint`: `COMPLETED_WITH_PROOF` / `RECONCILED_WITH_PROOF`. Recommendation: cross_off_allowed_with_proof.
- `security_pass_contract_pass_1`: `COMPLETED_WITH_PROOF` / `RECONCILED_WITH_PROOF`. Recommendation: cross_off_allowed_with_proof.
- `markdown_knowledge_atlas_capability`: `PARKED_WITH_PROOF` / `BUILT_NOT_SURFACED`. Recommendation: quiet_with_proof_or_future_visibility_surface.
- `future_invoicing_state_machine_audit`: `PARKED_WITH_PROOF` / `MATCHED_TO_WORKER_REPORT`. Recommendation: preserve_as_stress_test_artifact.
- `capital_hilton_finance_preview`: `COMPLETED_WITH_PROOF` / `MATCHED_TO_WORLD_LANE`. Recommendation: quiet_preview_with_proof_keep_action_blocked.
- `autonomous_capital_pipeline_experiment`: `PARKED_WITH_PROOF` / `MATCHED_TO_RECEIPT`. Recommendation: cross_off_only_as_experiment_parked.

## Cross-Off Decisions

- `security_pass_surface_checkpoint_cross_off`: `CROSS_OFF_ALLOWED_WITH_PROOF`. Source mutation: `false`; delete source: `false`.
- `security_pass_contract_pass_1_cross_off`: `CROSS_OFF_ALLOWED_WITH_PROOF`. Source mutation: `false`; delete source: `false`.
- `markdown_knowledge_atlas_visibility_cross_off`: `PARK_WITH_PROOF`. Source mutation: `false`; delete source: `false`.
- `future_invoicing_audit_cross_off`: `PARK_WITH_PROOF`. Source mutation: `false`; delete source: `false`.
- `capital_hilton_preview_cross_off`: `CROSS_OFF_ALLOWED_WITH_PROOF`. Source mutation: `false`; delete source: `false`.
- `autonomous_capital_pipeline_parked_cross_off`: `PARK_WITH_PROOF`. Source mutation: `false`; delete source: `false`.

## Repair / Requeue

- Repair and requeue records are recommendations only.
- They do not queue, run, repair, or grant unattended execution.

## Quiet With Proof

- Quiet receipts preserve proof refs, retrieval paths, reopen conditions, and evidence drawer refs.

## Security Delta And FULL_TRUST

- Any cross-off or repair path that requires new authority routes to Security Delta Review or fails closed.
- FULL_TRUST_CLEARANCE is referenced only as a future eligibility state and does not grant execution by itself.

## Machine Proof

- Default harness receipts: `6`.
- Cross-off decisions: `6`.
- Repair/requeue recommendations: `2`.
- Quiet receipts: `2`.
- Cross-off never deletes or mutates source: `true`.
- Automatic cross-off allowed: `false`.
- Chief self-authorization allowed: `false`.
- Action authority granted: `false`.
- Content hash: `sha256:c804cbefd55e88af4524773019659679742f7c5b6e1f965003c8aa62fbb49714`.
