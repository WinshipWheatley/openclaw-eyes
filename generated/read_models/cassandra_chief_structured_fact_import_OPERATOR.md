# Cassandra/Chief Structured Fact Import v0

Plain-English status:
- Imported only the operator-approved structured categories.
- Imported rows are parsed evidence, not truth.
- Every imported row needs operator confirmation before use.
- No send or runtime authority was granted.

## Categories Imported
- contacts/nicknames: 38 rows; parsed_evidence_not_truth; needs_operator_confirmation.
- company/contact relationships: 3 rows; parsed_evidence_not_truth; needs_operator_confirmation.
- email permission posture: 8 rows; parsed_evidence_not_truth; needs_operator_confirmation.
- invoice facts: 40 rows; parsed_evidence_not_truth; needs_operator_confirmation.
- receivable/payment tracking: 10 rows; parsed_evidence_not_truth; needs_operator_confirmation.

## Categories Skipped
- None.

## Boundaries Proven
- Raw logs imported: `false`
- Old HITL imported: `false`
- Agent presence imported: `false`
- Spreadsheet cells read: `false`
- Send authority granted: `false`
- Runtime authority changed: `false`

## Next Safe Move
- Cassandra/Clara SQLite Fact Packet Refresh v0.
