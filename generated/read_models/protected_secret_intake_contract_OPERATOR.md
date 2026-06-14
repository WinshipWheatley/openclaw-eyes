# Protected Secret Intake Contract v0

ELIOPERATOR: Enter Secret should create a protected reference. It must not put a value into chat, prompts, logs, cards, tests, or normal read-models.

## What This Enables

OpenClaw can plan for secrets without exposing them to chats, models, logs, cards, tests, or normal read-models.

## What This Does Not Do Yet

This does not capture, store, reveal, use, or transmit real credentials. No browser/login/external action is added.

## How It Should Work

The future plus-menu intake accepts the value inside a secure envelope, creates a protected ref, and immediately hides the raw value from normal surfaces.

## Modes

- `USE_ONCE`
- `STORE_PROTECTED`
- `SESSION_TTL`
- `TASK_SCOPED`
- `NEVER_STORE`

## Agent View

Agents see a token ref, safe label, kind, scope, TTL policy, and gate status. They never see the value.

Example protected ref:
- secret_ref:coupa_use_once_capital_hilton

## Required Blocks

- Raw value in normal chat is blocked.
- Raw value in read-models is blocked.
- Raw value in model context is blocked.
- Raw value in logs or tests is blocked.
- Adapter use requires future approval, scope, and receipts.

## Boundary

No live secret capture, store, reveal, adapter use, login, browser, external action, model exposure, credential handling, raw-body ingestion, Mac sync/import, Swift change, or push was added.

Next safe move: Use fake token refs only and build future adapter gates before any live secret handling.
