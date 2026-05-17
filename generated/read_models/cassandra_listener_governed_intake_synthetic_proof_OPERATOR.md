# Cassandra Governed Intake Receive Wiring Proof v0

Status:
- Live receive wired: `true`.
- Synthetic receive proven: `true`.
- Live receive proven: `false`.
- Live test required: `true`.
- Raw body stored: `false`.
- Send authority added: `false`.
- Reply authority added: `false`.
- Runtime authority changed: `false`.

## What Is Proven
- A Cassandra-targeted synthetic Telegram-style update can be stored as governed Repo A intake metadata.
- The live `cassandra_listener.py` receive path calls the governed Cassandra intake helper.
- The live hook is before unverified-sender return, reply handling, and Cassandra runtime brain calls.
- The message is routed through deterministic intent records and surfaced on the Work Board.
- A planning-only Agent Work Packet can be built from the routed intent.
- Only hash and bounded excerpt metadata are retained; no full raw body is stored.

## Governed Path Observed
- `telegram_agent_intake`: observed.
- `intent_records`: observed.
- `work_board`: observed.
- `agent_work_packet`: observed.
- `operator_action_guardian_hitl_if_actionable`: not observed.

## Storage Proof
- Synthetic body length: `329` characters.
- Stored excerpt length: `180` characters.
- Excerpt truncated: `true`.
- Full raw body included in read-model: `false`.

## What Is Not Proven
- No live Telegram receive has been observed yet; Winship still needs to send the test message.
- The legacy listener was not imported, executed, changed, restarted, or replaced.
- No send, reply, runtime, sync, or shell authority was added.

## Live Test For Winship
Send this exact Telegram message to Cassandra:

`Cassandra, receive-only governed intake test: You seeing this through Repo A?`

Then verify from Repo A:

- `cd /home/openclaw`
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/query_telegram_agent_intake.py --report cassandra-live --format operator`
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/query_telegram_agent_intake.py --report cassandra-live --format json`

## Next Safe Move
- Operator live Telegram receive-only test
