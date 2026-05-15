# OpenClaw Intent Router v0

Intent Router v0 is the deterministic routing layer between operator/source text and role-scoped Agent Lane Registry lanes.

It records:
- source kind and channel
- short sanitized intent preview and text hash
- explicit or inferred agent/lane
- world hint
- intent category
- confidence
- metadata-only context links
- next safe move
- candidate Operator Action type when applicable

It does not:
- activate agents
- call models
- call Telegram APIs
- create, approve, or execute Operator Actions
- execute tools or arbitrary commands
- read no-go raw content
- move, delete, or reorganize files
- promote truth

## Source Kinds

Supported source metadata kinds:
- `mission_control`
- `telegram`
- `cli`
- `report_bridge`
- `future_client_node`
- `unknown`

Telegram is represented as future metadata only. There is no Telegram API, polling, sending, or source-text storage.

## Categories

The router uses deterministic phrase/path rules only:
- `markdown_reorg_request`
- `file_context_request`
- `read_model_refresh_request`
- `report_bridge_request`
- `safety_review_request`
- `communication_summary_request`
- `music_project_request`
- `project_capsule_request`
- `status_orientation_request`
- `unknown_review`

Unknown or ambiguous intents are marked `needs_operator_review`.

## Commands

Route:

```bash
python3 scripts/route_operator_intent.py \
  --text "Chief, organize my Markdown files" \
  --source-kind cli \
  --source-channel local_terminal \
  --requested-by operator \
  --format operator
```

Query:

```bash
python3 scripts/query_intent_router.py --report summary --format operator
python3 scripts/query_intent_router.py --report latest --format operator
python3 scripts/query_intent_router.py --report by-agent --agent chief --format operator
python3 scripts/query_intent_router.py --report needs-review --format operator
```

Export:

```bash
python3 scripts/export_intent_router_read_model.py --format operator
```

Generated read-models:
- `generated/read_models/intent_router.json`
- `generated/read_models/intent_router_OPERATOR.md`

## Boundary

All v0 routes require approval for any future bounded execution path. The router may identify a candidate allowlisted Operator Action type, but it does not create an action request automatically.
