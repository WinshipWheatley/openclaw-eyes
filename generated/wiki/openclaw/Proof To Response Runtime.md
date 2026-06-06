# Proof To Response Runtime

Status: PROOF_TO_RESPONSE_RUNTIME_READY

Verifier-only runtime for publishing concise agent responses from machine proof. It does not call an LM; it verifies a candidate response, publishes it when safe, or publishes a safe fallback.

## Doctrine

- Candidate agent text is not truth.
- Machine proof, receipts, gates, source refs, and hashes define publishable claims.
- The runtime may publish concise human text only after deterministic verification.
- If verification fails, the runtime publishes a safe fallback instead of the draft.
- Controls remain controller events and never grant protected authority.
- Details and proof stay collapsed by default.

## Publish Gate

- candidate references the active proof bundle
- every claimed fact exists in the proof bundle
- no unsupported paid, sent, submitted, approved, or executed claim
- no protected-action promise
- no machine-contract jargon in the primary response
- response remains concise
- next step maps to allowed controller control
- self-heal responses name blocker, cite proof, state can-do and cannot-do
- details remain collapsed
- all protected authority flags remain false

## Runtime Scenarios

- `finance_capital_hilton_payment_watch`: Payment evidence needed -> `publishable`
- `finance_live_arts_payment_evidence`: Evidence recorded -> `publishable`
- `business_development_capital_hilton_followup`: Follow-up can be staged -> `publishable`
- `build_review_packet`: Review packet is informational -> `publishable`
- `unknown_context`: Needs lane context -> `publishable`
- `protected_coupa_ledger_email_request`: Blocked until proof and approval -> `publishable`
- `self_heal_missing_proof_for_payment`: Payment evidence is missing -> `publishable`

## Receipt Store

- SQLite: `generated/system_knowledge/proof_to_response_runtime.sqlite`
- Published responses: `7`
- SQLite rows: `7`

## Boundary

- No live LM invocation.
- No local model runtime connection.
- No worker spawn.
- No email, Gmail, browser, Coupa, submit, ledger mutation, workbook mutation, PDF export, paid marking, merge, push, or business execution.
- Details remain collapsed; proof and receipts are available through refs.
