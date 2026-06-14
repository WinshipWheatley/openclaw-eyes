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

- `finance_capital_hilton_payment_watch`: Payment evidence needed -> `publishable` via `shadow_pilot_candidate`
- `finance_capital_hilton_paid_ledger_blocker`: Paid marking is blocked -> `publishable` via `shadow_pilot_candidate`
- `finance_capital_hilton_attach_proof_explanation`: Proof can be recorded -> `publishable` via `shadow_pilot_candidate`
- `finance_capital_hilton_handle_boundary`: I can handle the safe part -> `publishable` via `shadow_pilot_candidate`
- `finance_capital_hilton_package_context`: LM2 would get bounded context -> `publishable` via `shadow_pilot_candidate`
- `finance_capital_hilton_allowed_scope`: Allowed: explain and collect proof -> `publishable` via `shadow_pilot_candidate`
- `finance_capital_hilton_forbidden_scope`: Protected actions stay blocked -> `publishable` via `shadow_pilot_candidate`
- `finance_capital_hilton_freshness_uncertainty`: Evidence is the uncertainty -> `publishable` via `shadow_pilot_candidate`
- `finance_capital_hilton_decision_trace`: Payment watch is still active -> `publishable` via `shadow_pilot_candidate`
- `finance_capital_hilton_fallback_lane_answer`: Payment watch is the safe lane -> `publishable` via `shadow_pilot_candidate`
- `finance_live_arts_payment_evidence`: Evidence recorded -> `publishable` via `shadow_pilot_candidate`
- `business_development_capital_hilton_followup`: Follow-up can be staged -> `publishable` via `shadow_pilot_candidate`
- `build_review_packet`: Review packet is informational -> `publishable` via `shadow_pilot_candidate`
- `unknown_context`: Needs lane context -> `publishable` via `shadow_pilot_candidate`
- `protected_coupa_ledger_email_request`: Blocked until proof and approval -> `publishable` via `shadow_pilot_candidate`
- `self_heal_missing_proof_for_payment`: Payment evidence is missing -> `fallback` via `shadow_pilot_candidate`

## Receipt Store

- SQLite: `generated/system_knowledge/proof_to_response_runtime.sqlite`
- Published responses: `16`
- SQLite rows: `16`

## Boundary

- Active candidate source: `shadow_pilot_candidate`
- Supported candidate sources: `deterministic_fixture`, `shadow_pilot_candidate`, `future_live_lm_blocked`.
- No live LM invocation.
- No local model runtime connection.
- No worker spawn.
- No email, Gmail, browser, Coupa, submit, ledger mutation, workbook mutation, PDF export, paid marking, merge, push, or business execution.
- Details remain collapsed; proof and receipts are available through refs.
