# OpenClaw Telegram Agent Intake v0

Telegram Agent Intake v0 is the governed storage path for Telegram-facing operator updates. It is not a Telegram bot, sender, listener installer, runtime activator, or command executor.

## Purpose

When an operator message reaches a Telegram-facing listener, the message should not live only in legacy logs or ad hoc JSON files. The listener now has a best-effort governed intake hook that records bounded metadata in SQLite and routes operator-authored text through Intent Router when safe.

Preferred flow:

```text
Telegram listener
-> telegram_agent_update_records
-> intent_records / intent_router receipts
-> optional Work Board card for readiness/proof
-> generated/read_models/telegram_agent_intake.json
```

## Agents

- Chief: `chief_listener.py` hook available; runtime presence may be degraded.
- Cassandra / outward Clara Reid: `cassandra_listener.py` hook available; current presence may still be offline.
- Guardian: `chief_guardian_listener.py` hook available for approval/safety messages; not a general execution lane.
- Niles / outward Niles Mercer: `producer_listener.py` hook available; current presence may still be offline.
- Hermes: no current repo Telegram listener file was found; advisory gateway presence is separate.

## Storage Policy

- Full raw Telegram payloads are not stored.
- Chat IDs are not stored in readable records.
- Full message text is not stored by default.
- A bounded excerpt and salted hash are stored for operator-authored updates.
- Operator-authored updates can be routed through Intent Router as `source_kind=telegram`.
- Non-operator messages are metadata-only by default.

## Commands

```bash
python3 scripts/check_telegram_agent_intake.py --format operator
python3 scripts/query_telegram_agent_intake.py --report summary --format operator
python3 scripts/query_telegram_agent_intake.py --report agents --format operator
python3 scripts/export_telegram_agent_intake_read_model.py --format operator
```

## Current Boundary

This lane does not send Telegram messages. Cassandra/Clara Reid cannot be used as a completion notification channel unless a later lane verifies an approved status-only send path and current presence allows it.

No-authority flags:

- `telegram_send_allowed=false`
- `command_execution_allowed=false`
- `action_auto_execute_allowed=false`
- `approval_bypass_allowed=false`
- `raw_payload_storage_allowed=false`
- `token_exposure_allowed=false`
- `external_api_send_allowed=false`
- `agent_activation_allowed=false`
- `runtime_activation_allowed=false`
- `arbitrary_shell_allowed=false`
