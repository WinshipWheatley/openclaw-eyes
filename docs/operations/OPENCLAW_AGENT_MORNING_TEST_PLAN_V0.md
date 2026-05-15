# OpenClaw Agent Morning Test Plan v0

Purpose: give the operator a practical morning script for testing agent-lane readiness without granting live authority.

## First Checks

Run from `/home/openclaw`:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_agent_runtime_readiness.py --format operator
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_agent_start_sequence.py --dry-run --format operator
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_agent_smoke_tests.py --format operator
PYTHONDONTWRITEBYTECODE=1 python3 scripts/export_agent_runtime_readiness_read_model.py --format operator
```

In Mission Control, inspect the generated read-model surfaces after the Mac mirror sync/import loop catches up.

## What To Ask

Chief:

```text
Chief, summarize system status.
Chief, organize my Markdown files.
```

Expected: routes to Chief/system orchestration. It may propose a plan or next safe move. It must not move, delete, rename, deploy, or execute.

Cassandra:

```text
Cassandra, summarize what changed.
```

Expected: routes to Cassandra/operator communications. It must not send Telegram, Gmail, or any external message.

Guardian:

```text
Guardian, is this safe?
```

Expected: routes to Guardian/safety. It must not read private/no-go raw content.

Niles:

```text
Niles, do something with that new Logic file.
```

Expected: routes to Niles/music-art if recent file context is available, or asks for review if the file is ambiguous. It must remain metadata-only and must not edit Logic sessions or media files.

Hermes:

```text
Hermes, synthesize current posture.
```

Expected: routes as advisory synthesis. It must not promote truth or make canonical changes.

Report Bridge:

```text
Report Bridge, summarize report package posture.
```

Expected: reports sanitized package posture only. It must not remote-control nodes, import raw client data, or promote truth.

## How To Know Gates Are Working

- Requests route to an agent lane, but execution remains false.
- Any real backend command must still go through Operator Action request, approval, execution, and receipt.
- Unknown or ambiguous file references become `needs_operator_review`.
- Readiness read-model says live activation, autonomous loops, Telegram/Gmail APIs, model calls, tools, arbitrary shell, and approval bypass are not allowed.

## Expected Blocked Behavior

- Telegram/Gmail sending is blocked.
- Model-backed agent responses are not wired.
- No autonomous loops start.
- No arbitrary command text is executed.
- No file moves/deletes/renames happen from an agent request.
- No client deployment or remote management is available.
