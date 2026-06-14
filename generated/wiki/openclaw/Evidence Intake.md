# Evidence Intake

Status: `EVIDENCE_INTAKE_READY`

Evidence Intake records operator-dropped screenshots and files as candidate evidence. It is a local read-model and SQLite path, not business truth.

## Boundary

- Requires a verified Mission Control operator envelope.
- Classifies payment screenshots as `financial_sensitive` and `local_only`.
- Blocks external providers for financial screenshots.
- Does not store raw OCR/text in general memory.
- Does not mutate ledger, workbooks, Coupa, browser, Gmail, PDFs, send state, or paid truth.

## Payment Proof

- Evidence status: `CANDIDATE_EVIDENCE_RECORDED`
- Payment state: `payment_processing_evidence_received`
- Payment-processing evidence is not paid proof.
- Paid truth requires payment or ledger confirmation and operator review.

## Dynamic Card

- Headline: `Payment proof received`
- Status label: `Processing evidence`
- Trust state: `operator_reported`
- Summary: This appears to show payment processing for invoice 2026-1001. Ledger remains untouched until payment is confirmed.

## Artifacts

- Contract read model: `generated/read_models/evidence_intake_contract.json`
- Status read model: `generated/read_models/evidence_intake_status.json`
- SQLite: `/home/openclaw/worktrees/integrate/generated/system_knowledge/evidence_intake.sqlite`

## Machine Proof

- Unsafe true grants absent: `true`
- Ledger mutation performed: `false`
- Paid marking performed: `false`
