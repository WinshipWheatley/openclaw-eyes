# OpenClaw Agent Presence

Agents: 6
Expected online: 5
Online: 4
Unexpected offline/degraded/unknown: 1
Recovery available: 0

Cassandra:
- desired: `online`
- actual: `online`
- source: `service_check`
- recovery: `not_needed`
- recovery action: `cassandra_systemd_user_start`
- blocker: none
- next: No recovery needed.

Agents:
- `cassandra` desired=online actual=online source=service_check recovery=not_needed action=cassandra_systemd_user_start
- `chief` desired=online actual=online source=service_check recovery=not_needed action=chief_systemd_user_start
- `guardian` desired=online actual=online source=service_check recovery=not_needed action=guardian_systemd_user_start
- `hermes` desired=online actual=online source=service_check recovery=not_needed action=hermes_systemd_user_start
- `niles` desired=online actual=offline source=runtime_surface recovery=blocked action=niles_producer_script_start
- `report_bridge` desired=unknown_review actual=metadata_available source=read_model recovery=not_needed action=report_bridge_status_only

Recovery actions:
- `cassandra` `cassandra_systemd_user_start` kind=systemd_user_start safe_to_attempt=`false` classification=safe_start_candidate
- `chief` `chief_systemd_user_start` kind=systemd_user_start safe_to_attempt=`false` classification=safe_start_candidate
- `guardian` `guardian_systemd_user_start` kind=systemd_user_start safe_to_attempt=`false` classification=safe_start_candidate
- `hermes` `hermes_systemd_user_start` kind=systemd_user_start safe_to_attempt=`false` classification=safe_start_candidate
- `niles` `niles_producer_script_start` kind=script_start safe_to_attempt=`false` classification=needs_operator_review
- `report_bridge` `report_bridge_status_only` kind=status_only safe_to_attempt=`true` classification=safe_status_check

Recovery clearances:
- `cassandra` `cassandra_systemd_user_start` status=`approved` used=0/1 expires=`2026-05-16T05:15:40+00:00`
- `cassandra` `cassandra_systemd_user_start` status=`used` used=1/1 expires=`2026-05-16T05:02:47+00:00`

Recent recovery attempts:
- `cassandra` action=cassandra_systemd_user_start attempted=`false` succeeded=`false` blocker=agent actual_state is online; recovery is not needed
- `cassandra` action=cassandra_systemd_user_start attempted=`true` succeeded=`false` blocker=recovery command returned non-zero exit code

Blockers:
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
