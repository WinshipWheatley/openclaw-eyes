# External LM Synthetic Response Verification Smoke

Status: `EXTERNAL_LM_SYNTHETIC_RESPONSE_VERIFICATION_READY`

This smoke verified a manually pasted synthetic external LLM response through the local schema adapter and deterministic proof-to-response verifier.
No external API was called, no model was invoked, no prompt or proof bundle was sent, and no private proof was accepted.

## Result

- Candidate input present: `true`
- Adapter parse status: `PARSED`
- Verifier run: `true`
- Verifier pass: `false`
- Publishable: `false`
- Blocking reason: Deterministic verifier rejected claimed facts that are not present in the synthetic verifier proof bundle.

## Rejection Reasons

- `claimed_fact_not_in_bundle:no_coupa_submit`
- `claimed_fact_not_in_bundle:no_email_sent`
- `claimed_fact_not_in_bundle:no_ledger_mutation`
- `claimed_fact_not_in_bundle:no_paid_marking`

## Boundary

- Synthetic data only.
- Candidate text is not truth.
- The verifier remains the publish gate.
- A verifier failure is recorded without loosening truth or authority checks.
- No external provider, browser, Gmail, Coupa, ledger, workbook, PDF, paid marking, submit, push, or business-system mutation occurred.

## Next Safe Action

Revise the synthetic response so claimed_facts contains only fact ids present in the synthetic verifier proof bundle, then rerun the local adapter/verifier smoke.
