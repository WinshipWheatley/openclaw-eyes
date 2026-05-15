# Telegram Agent Intake v0

## Summary
- Intake status: `governed_storage_available`
- Governed storage available: `true`
- Updates: 1
- Routed: 1
- Receive-ready agents: 1
- Blocked agents: 4
- Raw payload stored: 0
- Full message text stored: 0

## Agents
- `chief` / Chief: desired=online, actual=degraded, receive=false, send=false, blocker=presence_degraded
- `cassandra` / Clara Reid: desired=online, actual=offline, receive=false, send=false, blocker=presence_offline
- `guardian` / Guardian: desired=online, actual=online, receive=true, send=false, blocker=none
- `niles` / Niles Mercer: desired=online, actual=offline, receive=false, send=false, blocker=presence_offline
- `hermes` / Hermes: desired=online, actual=online, receive=false, send=false, blocker=telegram_listener_not_found

## Dry-Run Proof
- `tgupdate_3445dc101ac24cd99910` channel=synthetic_dry_run target=chief intent=intent_f0cef86588945f7dbbdb routed=true

## Blockers
- `cassandra` presence_offline: Use agent presence/recovery policy to resolve Cassandra state; do not bypass recovery gates.
- `chief` presence_degraded: Use agent presence/recovery policy to resolve Chief state; do not bypass recovery gates.
- `hermes` telegram_listener_not_found: Create or approve a Telegram listener surface for Hermes before expecting live receive.
- `niles` presence_offline: Use agent presence/recovery policy to resolve Niles state; do not bypass recovery gates.

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
