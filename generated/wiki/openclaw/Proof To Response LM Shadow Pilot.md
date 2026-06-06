# Proof To Response LM Shadow Pilot

Status: PROOF_TO_RESPONSE_LM_SHADOW_PILOT_READY

This pilot simulates the future proof-to-response path with fixture/mock LM-style text only. No model runtime, provider, worker, tool, or business executor is invoked.

## Doctrine

- LM-style text is not truth.
- Proof bundles, receipts, gates, hashes, and read models define truth.
- The mock LM draft may phrase, prioritize, diagnose, and explain next steps.
- The deterministic verifier decides publishability.
- Rejected drafts publish safe fallback text, not the unsafe draft.
- Dynamic cards remain support/display and details stay collapsed.

## Pilot Chain

1. Build a bounded proof bundle.
2. Generate an agent-style mock draft.
3. Run deterministic verification.
4. Publish concise text only if verified; otherwise publish safe fallback.
5. Keep dynamic cards as support and details collapsed.

## Scenarios

- `finance_capital_hilton_payment_watch`: chief / Payment evidence needed -> `VERIFIED_FOR_SHADOW_PUBLISH`
- `business_development_capital_hilton_followup`: cassandra / Follow-up can be staged -> `VERIFIED_FOR_SHADOW_PUBLISH`
- `finance_live_arts_payment_evidence`: guardian / Evidence recorded -> `VERIFIED_FOR_SHADOW_PUBLISH`
- `build_review_packet`: chief / Review packet is informational -> `VERIFIED_FOR_SHADOW_PUBLISH`
- `protected_coupa_ledger_email_request`: guardian / Blocked until proof and approval -> `VERIFIED_FOR_SHADOW_PUBLISH`
- `self_heal_missing_proof_for_payment`: chief / Payment evidence is missing -> `VERIFIED_FOR_SHADOW_PUBLISH`

## Boundary

- No external LM invocation.
- No unapproved local model runtime connection.
- No worker spawn.
- No email, Gmail, browser, Coupa, portal submit, ledger mutation, workbook mutation, PDF export, paid marking, merge, push, or business execution.

## Proof

- Pilot run count: `6`
- All pilot drafts verified: `true`
- Dynamic cards support only: `true`
- Unsafe true grants absent: `true`
