# Telegram Agent Runtime Readiness Rollup v0

Status: `not_ready`.

## What Was Verified
- `cassandra-listener.service` is running from `/home/openclaw/cassandra_listener.py`.
- Repo A governed intake storage is available.
- Cassandra has synthetic governed intake rows.
- Cassandra does **not** yet have a live `cassandra_listener` governed intake row.
- Send authority remains `false`.
- Reply authority remains `false`.
- Runtime authority changed: `false`.

## Current Blocker
`CASSANDRA_BOT_TOKEN` still resolves to the Niles producer bot identity.

That explains both symptoms:
- The Cassandra live test did not land in Repo A as a live Cassandra receive row.
- Cassandra/Chief-style briefing content can appear through the Niles Telegram bot surface.

No tokens, raw chat IDs, raw Telegram message bodies, or private log contents were included in this rollup.

## Counts
- Cassandra live listener records: `0`.
- Cassandra synthetic records: `5`.
- Raw payload stored count: `0`.
- Full message text stored count: `0`.

## Operator Decision Needed
- Correct `CASSANDRA_BOT_TOKEN` to the actual Cassandra Telegram bot token.
- Decide whether to set `CASSANDRA_CHAT_ID` explicitly.
- After correction, restart only the affected Cassandra services if they are intended to run.

## Next Live Test
Send this exact message to Cassandra after token mapping is corrected:

`Cassandra, receive-only governed intake test: You seeing this through Repo A?`

Then verify:

- `cd /home/openclaw`
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/query_telegram_agent_intake.py --report cassandra-live --format operator`
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/query_telegram_agent_intake.py --report cassandra-live --format json`

## Next Safe Lane
- Telegram Token Mapping Correction v0
