# Workroom Review Decision Contract

Status: `WORKROOM_REVIEW_DECISION_CONTRACT_READY`

This contract defines safe operator decisions for Workroom review packets. Decisions record review state only.

## Decision Actions

### `approve_review_packet_for_record`

- Effect: `operator_review_recorded_only`
- Status: `APPROVED_FOR_RECORD_ONLY`
- Next safe action: Record the operator review receipt only; do not merge or push.
- No push: `true`
- No merge: `true`
- No business action: `true`

### `request_review_packet_rework`

- Effect: `rework_request_receipt_only`
- Status: `REWORK_REQUESTED`
- Next safe action: Record a rework request receipt only; do not spawn a worker from this decision.
- No push: `true`
- No merge: `true`
- No business action: `true`

### `mark_review_packet_informational`

- Effect: `review_closed_without_action`
- Status: `MARKED_INFORMATIONAL`
- Next safe action: Close the review as informational; no work or business action follows from this decision.
- No push: `true`
- No merge: `true`
- No business action: `true`

## Boundary

- Approval records operator review only.
- No merge.
- No git push.
- No worker spawn or child agent run.
- No email send.
- No Gmail/browser/Coupa access.
- No ledger or workbook mutation.
- No PDF export.
- No submit or mark-paid.
- No business action.
- Worker output does not inherit speaker authority.
