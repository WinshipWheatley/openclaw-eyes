# Guardian Approval Request Wrapper

## Summary
Guardian can now turn Action Covenants into deterministic review packets that show the requested action, risk, proofs, missing items, protected refs, blocked actions, and exact approval phrase. No approval is executed and no action is authorized.

## Packets
- Capital Hilton email: APPROVAL_PACKET_READY
- Coupa submit: NEEDS_MORE_PROOF
- Protected credential use: NEEDS_MORE_PROOF
- Test package: APPROVAL_PACKET_READY
- Missing proof: NEEDS_MORE_PROOF
- Destructive action: BLOCKED_UNSAFE

## Exact Phrase Example
APPROVE SEND_EMAIL capital_hilton_invoice_covenant_v0

## Blocked
- MISSING_COVENANT: Guardian cannot review approval without a covenant.
- AMBIGUOUS_ACTION: Ambiguous actions require operator clarification.
- MISSING_PROOF: Required proof is missing.
- PROTECTED_REF_UNREVIEWED: Protected refs need Guardian review before use.
- SECRET_REVEAL_UNGATED: Secret use requires a protected ref and future adapter gate.
- EXTERNAL_ACTION_ATTEMPTED: External action is blocked in the Guardian request wrapper.
- APPROVAL_PHRASE_MISSING: Exact approval phrase is required.
- CLIENT_BOUNDARY_RISK: Client/workflow boundary risk must be resolved.
- UNSUPPORTED_ACTION: Unsupported action is blocked.
- UNKNOWN_FAIL_CLOSED: Unknown approval request fails closed.

## Boundary
No live approval execution, no action authorization, no email send, no Coupa submit, no browser, no secret reveal, no file mutation, no workflow run, no agent dispatch, no external action, no credential handling, no raw-body ingestion.
