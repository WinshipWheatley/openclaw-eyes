# OpenClaw Cassandra Runtime Wiring Audit v0

## Purpose

Map Cassandra service/runtime evidence without claiming Telegram round-trip or
reply readiness.

This audit separates:

- service/process online
- live Telegram receive proven
- governed SQLite storage proven
- Intent Router route proven
- Capital Hilton fact-intake route supported
- governed Telegram reply allowed

## Boundary

The audit does not send Telegram messages, execute Repo B code, read secrets,
start or stop services, approve actions, call external APIs, or bypass Guardian.

No-authority flags are fixed false:

- `telegram_send_allowed`
- `arbitrary_command_allowed`
- `repo_b_execution_allowed`
- `secret_access_allowed`
- `external_api_allowed`
- `approval_bypass_allowed`

## Tables

- `cassandra_runtime_wiring_runs`
- `cassandra_runtime_surfaces`
- `cassandra_runtime_comparison`
- `cassandra_roundtrip_steps`
- `cassandra_wiring_gaps`
- `cassandra_wiring_recommendations`
- `cassandra_wiring_query_receipts`

## Commands

```bash
python3 scripts/build_cassandra_runtime_wiring_audit.py --format operator
python3 scripts/query_cassandra_runtime_wiring_audit.py --report summary --format operator
python3 scripts/query_cassandra_runtime_wiring_audit.py --report roundtrip --format operator
python3 scripts/query_cassandra_runtime_wiring_audit.py --report gaps --format operator
python3 scripts/export_cassandra_runtime_wiring_audit_read_model.py --format operator
```

## Expected v0 Interpretation

If Cassandra services are active but `live_telegram_receive_to_governed_storage`
is `not_proven`, the correct operator-facing statement is:

> Cassandra service is online, and local governed storage/routing can be proven
> synthetically, but live Telegram receive is not proven and governed reply is
> not allowed.

Legacy listener files may still contain direct reply paths. Those paths are
classified as unsafe runtime behavior until wrapped behind an explicit
Guardian-approved send/ack policy.

## Next Lane

Run a receive-only proof lane:

1. Operator sends one prefixed Cassandra/Clara test message in Telegram.
2. Query governed intake for `source_channel=cassandra_listener`.
3. Do not send an automated reply.
4. If storage is proven, design a narrow status-only acknowledgment path under
   Guardian approval.
