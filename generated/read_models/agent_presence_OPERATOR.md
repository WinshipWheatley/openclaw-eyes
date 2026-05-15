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
- recovery action: `cassandra_systemd_user_start`
- blocker: expected runtime evidence missing
- next: Inspect the documented service/process surface and choose a bounded recovery lane if needed.

Agents:
- `cassandra` desired=online actual=offline source=runtime_surface recovery=blocked action=cassandra_systemd_user_start
- `chief` desired=online actual=degraded source=process_check recovery=blocked action=chief_systemd_user_start
- `guardian` desired=online actual=online source=process_check recovery=not_needed action=guardian_systemd_user_start
- `hermes` desired=online actual=online source=process_check recovery=not_needed action=hermes_systemd_user_start
- `niles` desired=online actual=offline source=runtime_surface recovery=blocked action=niles_producer_script_start
- `report_bridge` desired=unknown_review actual=metadata_available source=read_model recovery=not_needed action=report_bridge_status_only

Recovery actions:
- `cassandra` `cassandra_systemd_user_start` kind=systemd_user_start safe_to_attempt=`false` classification=safe_start_candidate
- `chief` `chief_systemd_user_start` kind=systemd_user_start safe_to_attempt=`false` classification=safe_start_candidate
- `guardian` `guardian_systemd_user_start` kind=systemd_user_start safe_to_attempt=`false` classification=safe_start_candidate
- `hermes` `hermes_systemd_user_start` kind=systemd_user_start safe_to_attempt=`false` classification=safe_start_candidate
- `niles` `niles_producer_script_start` kind=script_start safe_to_attempt=`false` classification=needs_operator_review
- `report_bridge` `report_bridge_status_only` kind=status_only safe_to_attempt=`true` classification=safe_status_check

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
