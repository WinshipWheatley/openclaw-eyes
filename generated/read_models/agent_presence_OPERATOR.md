# OpenClaw Agent Presence

Agents: 6
Expected online: 5
Online: 2
Unexpected offline/degraded/unknown: 3
Recovery available: 0

Cassandra:
- desired: `online`
- actual: `offline`
- source: `runtime_surface`
- recovery: `blocked`
- blocker: expected runtime evidence missing
- next: Inspect the documented service/process surface and choose a bounded recovery lane if needed.

Agents:
- `cassandra` desired=online actual=offline source=runtime_surface recovery=blocked
- `chief` desired=online actual=degraded source=process_check recovery=blocked
- `guardian` desired=online actual=online source=process_check recovery=not_needed
- `hermes` desired=online actual=online source=process_check recovery=not_needed
- `niles` desired=online actual=offline source=runtime_surface recovery=blocked
- `report_bridge` desired=unknown_review actual=metadata_available source=read_model recovery=not_needed

Blockers:
- `cassandra`: expected runtime evidence missing -> Inspect the documented service/process surface and choose a bounded recovery lane if needed.
- `chief`: only some expected runtime surfaces show active evidence -> Inspect the documented service/process surface and choose a bounded recovery lane if needed.
- `niles`: expected runtime evidence missing -> Inspect the documented service/process surface and choose a bounded recovery lane if needed.

No-authority posture:
- `broad_agent_activation_allowed`: `false`
- `telegram_api_allowed`: `false`
- `message_send_allowed`: `false`
- `arbitrary_command_allowed`: `false`
- `secret_access_allowed`: `false`
- `recovery_without_policy_allowed`: `false`
- `hard_kill_bypass_allowed`: `false`
- `network_authority`: `false`
- `model_call_allowed`: `false`
- `client_deployment_allowed`: `false`

Boundary:
- Presence is evidence/status only.
- This read-model does not send Telegram messages, inspect secrets, start agents, restart services, call models, or run recovery commands.
