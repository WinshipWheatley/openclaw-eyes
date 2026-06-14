# Conversational Action Covenant Interrupter

## Summary
OpenClaw can now interrupt casual chat approvals before high-consequence actions. Low-risk confirmations can continue, but send/submit/mutate/reveal/run requests require a concrete Action Covenant and exact phrase, with no live authorization or execution in v0.

## How It Works
- Casual phrases are classified before action.
- High-consequence actions require a concrete covenant.
- Gated actions require an exact phrase bound to the covenant id.
- Receipts record that nothing executed in this lane.

## Examples
- looks right: ALLOWED_LOW_RISK_CONTINUE
- go ahead: What should I go ahead with?
- send it: NEEDS_COVENANT
- Capital Hilton send covenant: APPROVE SEND_EMAIL capital_hilton_invoice_covenant_v0
- reveal-secret request: NEEDS_GUARDIAN_REVIEW
- test package: BLOCKED_MISSING_PROOF
- destructive action: BLOCKED_UNSUPPORTED_ACTION

## Blocked
- CASUAL_PHRASE_USED_FOR_EXTERNAL_ACTION: Casual chat approval cannot authorize external action.
- NO_PENDING_COVENANT: There is no pending covenant to approve.
- AMBIGUOUS_APPROVAL: Ambiguous approval must be clarified.
- EXACT_SIGNATURE_MISSING: Exact covenant signature is missing.
- COVENANT_EXPIRED: Expired covenants cannot be approved.
- PROOF_MISSING: Proof is missing.
- GUARDIAN_REQUIRED: Guardian review is required.
- UNSUPPORTED_ACTION: Unsupported high-consequence action is blocked.
- EXTERNAL_ACTION_ATTEMPTED: External action is blocked.
- SECRET_REVEAL_ATTEMPTED_WITHOUT_GATE: Secret reveal requires a protected covenant and adapter gate.
- UNKNOWN_FAIL_CLOSED: Unknown action approval fails closed.

## Boundary
No live action authorization, no action execution, no email send, no Coupa submit, no browser, no file mutation, no secret reveal, no workflow run, no agent dispatch, no external action, no credential handling, no raw-body ingestion.
