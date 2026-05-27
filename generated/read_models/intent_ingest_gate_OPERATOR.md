# Intent Ingest Gate

Status: DETERMINISTIC_INTENT_INGEST_GATE_NO_EXECUTION
Accepted example: ACCEPTED_INTENT
Blocked example: BLOCKED_AUTHORITY

Gate 2 accepts only validated MachineIntentCandidate proposals as internal intents.

Operator-visible readbacks:
- safe_status_next_step: ACCEPTED_INTENT - OpenClaw can ingest this as a bounded internal intent. Nothing runs yet.
- send_invoice_now: BLOCKED_AUTHORITY - OpenClaw understood the request, but it asks for authority this lane does not have.
- ambiguous_do_the_thing: NEEDS_CLARIFICATION - OpenClaw needs one clear answer before this can become an internal intent.
- delete_other_from_openclaw: ACCEPTED_INTENT - OpenClaw can ingest this as a bounded internal intent. Nothing runs yet.
- cross_client_mismatch: NEEDS_CONTEXT - OpenClaw needs matching scope or context before this can move forward.

Boundary: no LM call, no execution, no send/submit, no authority grant.
