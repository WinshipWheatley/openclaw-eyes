# Guardian HITL Cassandra Proposal Shadow v0

## Bottom Line

Cassandra HITL pending-action proposals can now be mirrored into SQLite as observational records. Old `hitl_pending_state.json` remains runtime-authoritative. No caller switched, no old HITL file was deleted, and no raw payload content is stored.

## Status

- Shared Guardian HITL tables used: `true`
- Runtime authority changed: `false`
- Source surface: `hitl_pending_store`
- Canonical action type: `cassandra_hitl_proposal`
- Legacy state authority: `hitl_pending_state_json`
- Legacy JSON authoritative: `true`
- Callers switched: `false`
- Old HITL deleted: `false`
- Raw payload stored: `false`
- Raw command text stored: `false`
- Adapter health: `healthy`

## Counts

- Proposal shadows: `0`
- Receipts: `0`
- Unsafe payload key count: `0`

## Recent Proposal Shadows

- No Cassandra HITL proposal shadows recorded yet.

## Still Blocked

- Cassandra/Chief memory import safe now: `false`
- Remote-builder bridge safe now: `false`
- Send-path expansion safe now: `false`

## Next Safe Move

Mirror Cassandra HITL decisions/expiry as observational receipts, then prove request and decision parity before any caller switch.
