# Proof To Response TDD Spec

Status: PROOF_TO_RESPONSE_TDD_SPEC_READY

Proof-to-Response TDD Spec V0 defines how deterministic proof becomes concise agent text. It is a contract for a future phrasing layer, not a live LM implementation.

## Doctrine

- Cards are not the main response.
- The main response is concise human text from the appropriate agent.
- The response must be grounded in machine proof.
- The LM may phrase and prioritize.
- The LM may not create truth or authority.
- If proof is missing, the response must say what is missing.
- If protected action is blocked, the response must say what approval/proof is needed.
- Details/proof remain available but not primary.

## Response Shape

- `response_id`
- `source_context` with world, thread, objective, card, receipt, proof, and gate refs
- `speaker_ref`: `cassandra`, `chief`, `hermes`, `guardian`, `niles`, or `openclaw`
- `voice_mode`: `brief`, `diagnostic`, `safety`, `creative`, or `operations`
- `human_response` with headline, body, next step, missing input, can-do, and cannot-do lists
- `controls`, `proof_meters`, `authority_boundary`, and `details_collapsed=true`

## Scenario Contracts

- `finance_capital_hilton_payment_watch`: `chief` / `operations` - Capital Hilton is still on payment watch -> Attach proof
- `finance_live_arts_payment_evidence`: `guardian` / `safety` - Live Arts payment evidence recorded -> Verify arrival or review the ledger later
- `business_development_capital_hilton_followup`: `cassandra` / `operations` - Capital Hilton follow-up can be staged -> Stage follow-up
- `build_review_packet`: `chief` / `diagnostic` - Review packet is informational -> Review packet
- `unknown_context`: `openclaw` / `brief` - Needs lane context -> Pick the world and thread
- `protected_coupa_ledger_email_request`: `guardian` / `safety` - Blocked until proof and approval -> Attach proof and prepare approval

## Guardrails

- No live LM call.
- No local model runtime.
- No worker spawn.
- No email send, Coupa submit, ledger/workbook mutation, PDF export, or paid marking.
- No primary-response machine-contract jargon.
- Every factual claim has source refs.
- Details remain collapsed.

## Proof

- Response count: `6`
- Preconditions ready: `true`
- Validation errors: `0`
- Unsafe true grants absent: `true`
