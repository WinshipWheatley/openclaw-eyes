# Cassandra Listener Governed Shadow v0

Status:
- Shadow/read-model only: `true`.
- Runtime authority changed: `false`.
- Caller switched: `false`.
- Live listener replaced: `false`.
- Raw Telegram body stored: `false`.

## Current Listener
- Surface: `cassandra_listener.py`.
- Risk: `high`.
- Static references: systemd/user/cassandra-listener.service.in references cassandra_listener.py; start_cassandra_core.sh starts cassandra_listener.py and cassandra_watcher.py.
- The live listener was not imported, executed, edited, or replaced.

## Governed Replacement Path
- `telegram_agent_intake`: store bounded Telegram-facing metadata and hashes
- `governed_intake_spine`: bridge metadata into deterministic intent routing
- `intent_records`: record deterministic route or needs-review result
- `work_board`: surface a review/planning card when useful
- `agent_work_packet`: draft bounded work packet only after route is safe
- `operator_action_guardian_hitl_if_actionable`: required for any send, runtime, sync bridge, or external action

## Expected Input
- Telegram/update metadata only.
- Hashes and sanitized preview only where needed.
- No raw Telegram body, private content, token, or credential material.

## Still Legacy
- `cassandra_listener.py`
- `systemd/user/cassandra-listener.service.in`
- `start_cassandra_core.sh`

## Blocked Until Proven
- direct listener activation
- caller switch
- service disable or edit
- launcher edit
- reply/send path
- runtime recovery action
- shell/process execution
- sync bridge authority
- raw Telegram body storage

## Proof Needed Before Caller Switch
- metadata-only intake fixture maps to telegram_agent_intake shape
- governed_intake_spine route is deterministic
- unknown input routes to review/triage
- Work Board / Agent Work Packet outputs are deterministic
- Operator Action is required for any action-capable proposal
- no raw Telegram body or private content is stored
- service/start references are represented but untouched

## Next Safe Move
- Cassandra Listener Governed Intake Synthetic Proof v0
