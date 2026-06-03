# Workroom Review Decision Consumer

Status: `WORKROOM_REVIEW_DECISION_CONSUMER_READY`

This consumer records operator review decisions against Workroom review packets. It records receipts only.

## Decision Actions

- `approve_review_packet_for_record` -> `OPERATOR_REVIEW_RECORDED`
- `request_review_packet_rework` -> `REWORK_REQUEST_RECORDED`
- `mark_review_packet_informational` -> `INFORMATIONAL_REVIEW_CLOSED`

## Latest Decision

- Receipt: `workroom_review_decision_consumer:92254cebc0a326a9`
- Packet: `review_packet:1ec9dae46a22e6ae`
- Action: `approve_review_packet_for_record`
- Status: `OPERATOR_REVIEW_RECORDED`
- Speaker: `chief`
- Next safe action: Record complete. No merge or push performed.

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
