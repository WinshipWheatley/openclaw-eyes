# OpenClaw Agent Presence

Run: `agentpresence_e58f3a284713d94c2fc6`
Observed through: `2026-07-26T04:57:57+00:00`
Agents: 6
Expected online: 6
Online: 6
Unexpected offline/degraded/unknown: 0
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
- `maestro` desired=online actual=online source=service_check recovery=not_needed action=maestro_systemd_user_start
- `niles` desired=online actual=online source=service_check recovery=not_needed action=niles_systemd_user_start

Supplemental (not in agent denominator):
- `report_bridge` actual=metadata_available source=read_model included_in_agent_denominator=`false`

Recovery actions:
- `cassandra` `cassandra_systemd_user_start` kind=systemd_user_start safe_to_attempt=`false` classification=safe_start_candidate
- `chief` `chief_systemd_user_start` kind=systemd_user_start safe_to_attempt=`false` classification=safe_start_candidate
- `guardian` `guardian_systemd_user_start` kind=systemd_user_start safe_to_attempt=`false` classification=safe_start_candidate
- `hermes` `hermes_systemd_user_start` kind=systemd_user_start safe_to_attempt=`false` classification=safe_start_candidate
- `maestro` `maestro_systemd_user_start` kind=systemd_user_start safe_to_attempt=`false` classification=safe_start_candidate
- `niles` `niles_systemd_user_start` kind=systemd_user_start safe_to_attempt=`false` classification=safe_start_candidate
- `report_bridge` `report_bridge_status_only` kind=status_only safe_to_attempt=`true` classification=safe_status_check

Recovery clearances:
- `cassandra` `cassandra_systemd_user_start` status=`approved` used=0/1 expires=`2026-05-16T05:15:40+00:00`
- `cassandra` `cassandra_systemd_user_start` status=`used` used=1/1 expires=`2026-05-16T05:02:47+00:00`

Recent recovery attempts:
- `cassandra` action=cassandra_systemd_user_start attempted=`false` succeeded=`false` blocker=agent actual_state is online; recovery is not needed
- `cassandra` action=cassandra_systemd_user_start attempted=`true` succeeded=`false` blocker=recovery command returned non-zero exit code

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
