# Evidence + Truth Contract v0

## Operator Summary
OpenClaw truth claims are only as strong as their receipts. DONE, GREEN, READY, and findings must cite artifacts; contradictions trigger diagnosis before action.

## Truth Doctrine
- `natural_language_done_is_not_proof`: `true`
- `green_requires_current_gate_receipt`: `true`
- `red_requires_first_hard_error_or_repro`: `true`
- `contradiction_promotes_to_diagnosis`: `true`
- `stale_receipts_require_recheck_before_ready`: `true`
- `private_raw_sources_are_not_imported_for_truth_claims`: `true`

## Claim Types
- `done_claim`
- `green_gate_claim`
- `finding_claim`
- `diagnosis_claim`
- `read_only_audit_claim`
- `blocked_claim`

## Truth Rules
- `done_claim_needs_artifact`: DONE must cite a commit, marker, receipt, or generated artifact.
- `green_gate_needs_receipt`: GREEN means a receipt/log with pass result, not a remembered claim.
- `finding_needs_falsifiable_pointer`: Findings need file:line, repro, error, or equivalent falsifiable evidence.
- `contradiction_forces_diag`: Contradictory green/red evidence is diagnosed before fixing or claiming DONE.

## Authority Boundary
- `contract_only`: `true`
- `truth_claim_authority_added`: `false`
- `approval_authority_added`: `false`
- `execution_authority_added`: `false`
- `test_execution_authority_added`: `false`
- `raw_private_artifact_access_added`: `false`
- `credential_authority_added`: `false`
- `external_send_authority_added`: `false`
- `legal_discovery_authority_added`: `false`
- `runtime_authority_added`: `false`
