# Workroom Review Decision Consumer

Status: `WORKROOM_REVIEW_DECISION_CONSUMER_READY`

This consumer records operator review decisions against Workroom review packets. It records receipts only.

## Decision Actions

- `approve_review_packet_for_record` -> `OPERATOR_REVIEW_RECORDED`
- `request_review_packet_rework` -> `REWORK_REQUEST_RECORDED`
- `mark_review_packet_informational` -> `INFORMATIONAL_REVIEW_CLOSED`

## Latest Decision

- Receipt: ``
- Packet: ``
- Action: ``
- Status: ``
- Speaker: ``
- Next safe action:

## Boundary

- No merge.
- No git push.
- No worker spawn or child agent run.
- No email send.
- No Gmail/browser/Coupa access.
- No ledger or workbook mutation.
- No PDF export.
- No submit or mark-paid.
- No business action.
- PC_CODEX and MAC_CODEX remain worker refs, not speakers.
- Proof refs are collapsed by default.
