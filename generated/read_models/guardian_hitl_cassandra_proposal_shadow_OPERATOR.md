# Guardian HITL Cassandra Proposal Shadow v0

## Bottom Line

Cassandra HITL pending-action proposals and decisions can now be mirrored into SQLite as observational records. Old `hitl_pending_state.json` remains runtime-authoritative. No caller switched, no old HITL file was deleted, and no raw payload content is stored.

## Status

- Shared Guardian HITL tables used: `true`
- Runtime authority changed: `false`
- Source surface: `hitl_pending_store`
- Canonical action type: `cassandra_hitl_proposal`
- Legacy state authority: `hitl_pending_state_json`
- Proposal shadow support: `true`
- Decision receipt shadow support: `true`
- Callback decision shadow support: `true`
- Legacy JSON authoritative: `true`
- Callers switched: `false`
- Old HITL deleted: `false`
- Raw payload stored: `false`
- Raw command text stored: `false`
- Adapter health: `healthy`

## Counts

- Proposal shadows: `0`
- Decision receipts: `0`
- Receipts: `0`
- Mismatches: `0`
- Unsafe payload key count: `0`

## Recent Proposal Shadows

- No Cassandra HITL proposal shadows recorded yet.

## Remaining Gates

- Cassandra/Chief memory import safe now: `true`
- Real data import still requires the operator-approved memory import decision receipt.
- Remote-builder bridge safe now: `false`
- Send-path expansion safe now: `false`

## Next Safe Move

Record the operator-approved Cassandra/Chief memory import decision receipt; do not import real data until that receipt exists.
