# Telegram Agent Intake v0

## Summary
- Intake status: `governed_storage_available`
- Governed storage available: `true`
- Updates: 2
- Routed: 2
- Receive-ready agents: 0
- Blocked agents: 6
- Raw payload stored: 0
- Full message text stored: 0

## Agents
- `chief` / Chief: desired=unknown_review, actual=unknown, receive=false, send=false, blocker=presence_unknown
- `cassandra` / Clara Reid: desired=unknown_review, actual=unknown, receive=false, send=false, blocker=presence_unknown
- `guardian` / Guardian: desired=unknown_review, actual=unknown, receive=false, send=false, blocker=presence_unknown
- `niles` / Niles Mercer: desired=unknown_review, actual=unknown, receive=false, send=false, blocker=presence_unknown
- `hermes` / Hermes: desired=unknown_review, actual=unknown, receive=false, send=false, blocker=telegram_listener_not_found
- `maestro` / Maestro: desired=unknown_review, actual=unknown, receive=false, send=false, blocker=presence_unknown

## Dry-Run Proof
- `tgupdate_ae186ebd5ed237ed226b` channel=synthetic_dry_run target=chief intent=intent_5bb1c8ca57894955ef1a routed=true

## Blockers
- `cassandra` presence_unknown: Use agent presence/recovery policy to resolve Cassandra state; do not bypass recovery gates.
- `chief` presence_unknown: Use agent presence/recovery policy to resolve Chief state; do not bypass recovery gates.
- `guardian` presence_unknown: Use agent presence/recovery policy to resolve Guardian state; do not bypass recovery gates.
- `hermes` telegram_listener_not_found: Create or approve a Telegram listener surface for Hermes before expecting live receive.
- `niles` presence_unknown: Use agent presence/recovery policy to resolve Niles state; do not bypass recovery gates.

## Authority Boundary
- `telegram_send_allowed`: `false`.
- `command_execution_allowed`: `false`.
- `action_auto_execute_allowed`: `false`.
- `approval_bypass_allowed`: `false`.
- `raw_payload_storage_allowed`: `false`.
- `token_exposure_allowed`: `false`.
- `external_api_send_allowed`: `false`.
- `agent_activation_allowed`: `false`.
- `runtime_activation_allowed`: `false`.
- `arbitrary_shell_allowed`: `false`.
