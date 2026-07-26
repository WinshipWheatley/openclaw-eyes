# Cassandra Runtime Wiring Audit v0

## Status
- Cassandra live receive has governed storage evidence; governed Telegram reply remains blocked.
- Live receive proven: `true`
- Governed storage proven: `true`
- Reply-ready: `false`

## Services
- `cassandra-briefing-scheduler.service` active=`active` sub=`running` points_to_repo_a=`true`
- `cassandra-listener.service` active=`active` sub=`running` points_to_repo_a=`true`
- `cassandra-watcher.service` active=`active` sub=`running` points_to_repo_a=`true`

## Round Trip
- `cassandra_services_online`: status=`proven`, proven=`true`, blocker=none
- `listener_execstart_points_repo_a`: status=`proven`, proven=`true`, blocker=none
- `listener_has_governed_storage_hook`: status=`implemented`, proven=`true`, blocker=none
- `live_telegram_receive_to_governed_storage`: status=`proven`, proven=`true`, blocker=none
- `synthetic_you_online_yet_route_store`: status=`proven`, proven=`true`, blocker=none
- `capital_hilton_finance_fact_route`: status=`supported`, proven=`true`, blocker=none
- `safe_acknowledgment_policy`: status=`blocked_by_policy`, proven=`false`, blocker=telegram_send_allowed_false

## Repo B Comparison
- `cassandra_brain.py`: `reference_only`; already_ported_to_repo_a, blocked_no_go, needs_operator_review, reference_only, unsafe_direct_send, useful_ack_logic
- `cassandra_briefing_brain.py`: `already_present_review_before_changes`; already_ported_to_repo_a, reference_only, useful_ack_logic, useful_briefing_logic
- `cassandra_briefing_scheduler.py`: `candidate_to_wrap`; already_ported_to_repo_a, blocked_no_go, unsafe_direct_send, useful_ack_logic, useful_briefing_logic
- `cassandra_capability.py`: `already_present_review_before_changes`; already_ported_to_repo_a, candidate_to_port, useful_ack_logic
- `cassandra_listener.py`: `candidate_to_wrap`; already_ported_to_repo_a, candidate_to_wrap, needs_operator_review, reference_only, unsafe_direct_send, useful_ack_logic, useful_receive_logic
- `cassandra_outreach.py`: `reference_only`; already_ported_to_repo_a, blocked_no_go, needs_operator_review, reference_only, unsafe_direct_send, useful_outreach_logic
- `cassandra_watcher.py`: `blocked_no_go`; already_ported_to_repo_a, blocked_no_go, needs_operator_review, reference_only
- `cassandra_whisper_relay.py`: `already_present_review_before_changes`; already_ported_to_repo_a, candidate_to_port, reference_only
- `chief_listener.py`: `candidate_to_wrap`; already_ported_to_repo_a, candidate_to_wrap, needs_operator_review, reference_only, unsafe_direct_send, useful_ack_logic, useful_receive_logic
- `chief_router.py`: `reference_only`; already_ported_to_repo_a, blocked_no_go, needs_operator_review, reference_only, useful_ack_logic

## Gaps
- `high` `legacy_direct_send_present`: Legacy Cassandra listener has direct Telegram reply paths

## Recommendations
- `high` Run Cassandra receive-only proof lane: Cassandra Telegram Receive Proof v1
- `high` Wrap or block legacy direct replies: Cassandra Safe Ack Policy v1
- `normal` Review Repo B receive and ack logic: Repo B Cassandra Listener Wrap Review v1
- `normal` Route Capital Hilton facts through Clara/Cassandra metadata: Capital Hilton Cassandra Fact Intake v1

## Authority Boundary
- `telegram_send_allowed`: `false`.
- `arbitrary_command_allowed`: `false`.
- `repo_b_execution_allowed`: `false`.
- `secret_access_allowed`: `false`.
- `external_api_allowed`: `false`.
- `approval_bypass_allowed`: `false`.
