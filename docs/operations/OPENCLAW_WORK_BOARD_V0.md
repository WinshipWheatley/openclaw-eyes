# OpenClaw Work Board v0

## Purpose

OpenClaw Work Board v0 is a local SQLite-backed control-plane surface for
reviewing work across the current substrate.

It turns safe metadata from existing systems into board cards:

- Intent Router records.
- Dropped Intent Registry rows.
- Agent Work Packets.
- Operator Actions.
- Report Bridge package/rejection metadata.
- Project Capsules.

The board supports the local workflow:

```text
intent -> routed lane -> work packet -> review/approval -> allowlisted action -> receipt -> helm state
```

## What This Is Not

- Not Linear, Symphony, Hermes, or any external API integration.
- Not remote control.
- Not agent activation.
- Not action execution.
- Not approval.
- Not file movement/reorganization.
- Not a raw private/no-go data surface.

## Commands

Build cards:

```bash
python3 scripts/build_work_board.py --format operator
```

Query:

```bash
python3 scripts/query_work_board.py --report summary --format operator
python3 scripts/query_work_board.py --report cards --format operator
python3 scripts/query_work_board.py --report needs-review --format operator
python3 scripts/query_work_board.py --report pending-approval --format operator
python3 scripts/query_work_board.py --report blocked --format operator
python3 scripts/query_work_board.py --report completed --format operator
python3 scripts/query_work_board.py --agent chief --format operator
python3 scripts/query_work_board.py --world build --format operator
python3 scripts/query_work_board.py --column routed --format operator
```

Safe metadata-only update:

```bash
python3 scripts/update_work_board_card.py --card-id <card_id> --column deferred --metadata-only --format operator
python3 scripts/update_work_board_card.py --card-id <card_id> --blocker "Waiting on operator review" --format operator
```

Export read-model:

```bash
python3 scripts/export_work_board_read_model.py --format operator
```

## Board Columns

- `captured_intent`
- `routed`
- `planned`
- `needs_review`
- `pending_approval`
- `approved`
- `in_progress`
- `blocked`
- `completed_with_receipt`
- `deferred`
- `rejected`
- `superseded`

## Source Mapping

- Intent Router:
  - `routed` -> `routed`
  - `needs_operator_review` -> `needs_review`
  - `rejected` -> `rejected`
- Dropped Intent Registry:
  - `unresolved` / `unknown_review` -> `needs_review`
  - `deferred` -> `deferred`
  - `built` -> `completed_with_receipt`
  - `rejected` -> `rejected`
  - `superseded` -> `superseded`
- Agent Work Packets:
  - `draft` / `proposed` -> `planned`
- Operator Actions:
  - `requested` -> `pending_approval`
  - `approved` -> `approved`
  - `running` -> `in_progress`
  - `completed` -> `completed_with_receipt`
  - `failed` -> `blocked`
  - `rejected` -> `rejected`
- Report Bridge:
  - imported package metadata -> `completed_with_receipt`
  - rejection metadata -> `rejected`
- Project Capsules:
  - draft demo/planning capsule -> `planned`

## Read-Model

Generated surfaces:

- `generated/read_models/work_board.json`
- `generated/read_models/work_board_OPERATOR.md`

The read-model includes card counts, counts by column/agent/world, latest cards,
top next safe moves, and no-authority flags.

## Boundaries

- `direct_execution_allowed=false`
- `arbitrary_shell_allowed=false`
- `auto_approval_allowed=false`
- `auto_execute_allowed=false`
- `agent_activation_allowed=false`
- `model_call_allowed=false`
- `tool_execution_allowed=false`
- `network_authority=false`
- `no_go_raw_access_allowed=false`
- `file_move_allowed=false`
- `file_delete_allowed=false`
- `client_deployment_allowed=false`

Work Board cards are review/control-plane metadata. They never execute work or
grant authority.

