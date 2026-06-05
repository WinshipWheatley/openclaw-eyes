# Proof Meter Normalization

Status: PROOF_METER_NORMALIZATION_READY

Proof Meter Normalization V0 turns backend proof fields into operator-readable controller meters. Meters summarize proof posture and open details; they do not grant authority or execute anything.

## Meters

- `truth`: `receipt_backed`, `artifact_hash`, `trusted_current`, `operator_reported`, `candidate_evidence`, `generated_summary`, `inferred`, `needs_verification`, `test_only`, `rejected`, `unknown`
- `freshness`: `current`, `waiting_external`, `needs_verification`, `superseded`, `historical`, `unknown`
- `authority`: `verified_control`, `approval_required`, `blocked_gate`, `no_grant`, `needs_verification`, `rejected`
- `evidence`: `receipt_present`, `artifact_hash_present`, `candidate_evidence`, `operator_reported`, `no_evidence`, `test_only`, `rejected`
- `sync`: `bridge_synced`, `local_only`, `bridge_stale`, `needs_mount`, `mismatch`, `unknown`
- `risk`: `calm`, `watch`, `pileup_risk`, `blocked`, `protected`, `unknown`

## Rules

- Proof meters are operator-readable.
- Proof meters do not imply execution.
- Payment-processing evidence does not imply paid.
- Approval does not imply business action.
- LM output does not imply truth.
- Meter clicks open details/proof.

## Cards

- `dynamic_card.finance.capital_hilton.payment_watch`: truth=trusted_current, freshness=current, authority=no_grant, evidence=receipt_present, sync=bridge_synced, risk=watch
- `dynamic_card.finance.live_arts_md.evidence_intake.payment_processing`: truth=operator_reported, freshness=waiting_external, authority=no_grant, evidence=operator_reported, sync=bridge_synced, risk=watch
- `dynamic_card.finance.capital_hilton.contextual_question`: truth=trusted_current, freshness=current, authority=no_grant, evidence=no_evidence, sync=bridge_synced, risk=watch
- `dynamic_card.build.review_packet.current`: truth=generated_summary, freshness=current, authority=no_grant, evidence=no_evidence, sync=bridge_synced, risk=watch
- `dynamic_card.business_development.capital_hilton.proposal`: truth=trusted_current, freshness=current, authority=no_grant, evidence=receipt_present, sync=bridge_synced, risk=calm
- `dynamic_card.system.check_engine.diagnostic`: truth=generated_summary, freshness=current, authority=blocked_gate, evidence=no_evidence, sync=bridge_synced, risk=blocked
- `dynamic_card.finance.capital_hilton.workbook_registration`: truth=trusted_current, freshness=current, authority=no_grant, evidence=no_evidence, sync=bridge_synced, risk=calm
- `dynamic_card.finance.capital_hilton.approval_request.coupa_submit`: truth=generated_summary, freshness=historical, authority=blocked_gate, evidence=no_evidence, sync=bridge_synced, risk=protected
- `dynamic_card.controller.safe_next.what_should_i_do`: truth=trusted_current, freshness=current, authority=no_grant, evidence=no_evidence, sync=bridge_synced, risk=calm
- `dynamic_card.finance.st_annes.work_log_review`: truth=trusted_current, freshness=historical, authority=no_grant, evidence=no_evidence, sync=bridge_synced, risk=calm
- `dynamic_card.build.review_packet.completed_historical_receipt`: truth=trusted_current, freshness=historical, authority=no_grant, evidence=receipt_present, sync=bridge_synced, risk=calm
- `dynamic_card.memory.payment_evidence_candidate`: truth=candidate_evidence, freshness=historical, authority=no_grant, evidence=candidate_evidence, sync=bridge_synced, risk=watch
- `dynamic_card.artifact.evidence_intake.proof_only`: truth=operator_reported, freshness=historical, authority=no_grant, evidence=operator_reported, sync=bridge_synced, risk=watch

## Proof

- Card count: `13`
- Meter count: `78`
- Unsafe true grants absent: `true`
