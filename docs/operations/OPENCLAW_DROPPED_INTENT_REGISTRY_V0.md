# OpenClaw Dropped Intent Registry v0

Dropped Intent Registry v0 records old unresolved, deferred, built, or
unknown-review operator directions so Chief can later ask whether a thread still
matters.

It is a registry and read-model layer over safe existing OpenClaw surfaces. It
does not notify the operator, create action requests, approve work, execute
commands, activate agents, call models, scan private/no-go raw content, or move
files.

## Sources

The v0 builder reads only bounded safe surfaces:

- `docs/operations/*.md` when classified safe/retrievable by Markdown Knowledge Atlas
- `generated/read_models/*.json`, `*.md`, and `*.txt`
- `generated/context_packets/*.json` and `*.md`
- existing `intent_router_*` metadata rows

It stores short excerpts only. It does not store full document bodies.

## SQLite Namespace

Tables are written into `.openclaw/business_ops/ledger.sqlite` under:

- `dropped_intent_runs`
- `dropped_intents`
- `dropped_intent_evidence_links`
- `dropped_intent_status_links`
- `dropped_intent_resolution_candidates`
- `dropped_intent_query_receipts`

Each item preserves title, short summary, source pointer, source kind, source
hash, agent/world/lane hints, category, status, evidence basis, next question,
and next lane. Every row keeps `approval_required=true`,
`action_created=false`, `notification_sent=false`, and `raw_body_stored=false`.

## Statuses

- `unresolved`: the desire appears not to be built yet.
- `deferred`: a substrate or placeholder exists, but live work remains a future lane.
- `built`: the original missing capability appears built.
- `rejected`: the thread was explicitly rejected.
- `superseded`: newer substrate replaced the older direction.
- `unknown_review`: the system found a candidate but cannot classify it safely.

## Commands

Build and export:

```bash
python3 scripts/build_dropped_intent_registry.py --format operator
```

Query:

```bash
python3 scripts/query_dropped_intents.py --report summary --format operator
python3 scripts/query_dropped_intents.py --report unresolved --format operator
python3 scripts/query_dropped_intents.py --report built --format operator
python3 scripts/query_dropped_intents.py --report deferred --format operator
python3 scripts/query_dropped_intents.py --report unknown-review --format operator
python3 scripts/query_dropped_intents.py --agent chief --format operator
python3 scripts/query_dropped_intents.py --world build --format operator
```

Export only:

```bash
python3 scripts/export_dropped_intents_read_model.py --format operator
```

Generated read-models:

- `generated/read_models/dropped_intents.json`
- `generated/read_models/dropped_intents_OPERATOR.md`

## Boundary

- `notification_allowed=false`
- `autonomous_prompting_allowed=false`
- `action_auto_create_allowed=false`
- `action_auto_approve_allowed=false`
- `action_auto_execute_allowed=false`
- `agent_activation_allowed=false`
- `network_authority=false`
- `model_call_allowed=false`
- `raw_private_scan_allowed=false`
- `file_move_allowed=false`
- `file_delete_allowed=false`

The registry can inform a future Chief planning surface. It does not itself ask
the operator, start a lane, create an Operator Action request, or execute work.
