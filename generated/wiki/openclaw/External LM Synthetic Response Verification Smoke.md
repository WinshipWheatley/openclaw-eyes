# External LM Synthetic Response Verification Smoke

Status: `EXTERNAL_SYNTHETIC_FACT_ALIGNMENT_READY`

The synthetic external response fixture is now aligned with the verifier proof bundle. The four no-action facts are canonical synthetic facts, not real Finance truth.

## Canonical Fact IDs

- `payment_evidence_missing`
- `processor_processing`
- `ledger_untouched`
- `paid_false`
- `no_email_sent`
- `no_coupa_submit`
- `no_ledger_mutation`
- `no_paid_marking`

## Verification Result

- Adapter parse status: `PARSED`
- Verifier run: `true`
- Verifier pass: `true`
- Publishable as synthetic test response: `true`
- Published as real Finance truth: `false`

## Boundary

- Synthetic data only.
- Candidate text is not truth.
- The verifier remains the publish gate.
- Real/private proof verification was not loosened.
- No external provider, model runtime, browser, Gmail, Coupa, ledger, workbook, PDF, paid marking, submit, push, or business-system mutation occurred.
