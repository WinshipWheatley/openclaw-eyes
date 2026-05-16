# Guardian HITL SQLite Chief Approval Dual-Write v0

## Bottom Line

Chief approval requests can now be mirrored into SQLite as observational records. Old `approval_pending.json` remains runtime-authoritative. No caller switched, no old HITL file was deleted, and no raw action or command text is stored.

## Status

- Runtime authority changed: `false`
- Dual-write surfaces: `chief_approval_brain, approval_pending_json`
- Legacy JSON authoritative: `true`
- Callers switched: `false`
- Old HITL deleted: `false`
- Raw action text stored: `false`
- Raw command text stored: `false`
- Adapter health: `healthy`

## Counts

- Request mirrors: `0`
- Decision receipts: `0`
- Notification receipts: `0`
- Mismatches: `0`

## Recent Mirrors

- No Chief approval request mirrors recorded yet.

## Still Blocked

- Cassandra/Chief memory import safe now: `false`
- Remote-builder bridge safe now: `false`
- Send-path expansion safe now: `false`

## Next Safe Move

Prove Chief request mirrors under live-safe synthetic tests, then plan decision/notification receipts without switching callers.
