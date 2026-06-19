# Telegram Agent Intake v0

## Summary
- Intake status: `governed_storage_available`
- Governed storage available: `true`
- Updates: 100
- Routed: 99
- Receive-ready agents: 3
- Blocked agents: 2
- Raw payload stored: 0
- Full message text stored: 0

## Agents
- `chief` / Chief: desired=online, actual=online, receive=true, send=false, blocker=none
- `cassandra` / Clara Reid: desired=online, actual=online, receive=true, send=false, blocker=none
- `guardian` / Guardian: desired=online, actual=online, receive=true, send=false, blocker=none
- `niles` / Niles Mercer: desired=online, actual=offline, receive=false, send=false, blocker=presence_offline
- `hermes` / Hermes: desired=online, actual=online, receive=false, send=false, blocker=telegram_listener_not_found

## Dry-Run Proof
- None.

## Blockers
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
