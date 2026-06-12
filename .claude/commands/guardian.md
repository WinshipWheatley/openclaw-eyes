# Guardian Maintenance Guide

This markdown file is a maintenance guide for Claude Code, Codex, and Fable
sessions. It is not runtime code, not a policy source, and not an authority
grant.

Runtime truth lives in Python, systemd units, HITL stores, generated read
models, and receipts. Use this guide to orient before inspecting the real files.

## Current Role

Guardian owns the human-in-the-loop authorization boundary:

- HITL approval authority.
- Approve, Deny, and Why Now operator controls.
- Exact-send approval capture.
- Risk and safety boundary enforcement.
- Operator-facing authorization records.
- Receipt-backed approval or denial state.

Guardian records decisions. Guardian does not execute business logic.

## Execution Mode

Guardian's normal execution mode is:

- `human_approval`
- `live_listener`

The live listener can receive operator decisions. The approval service/store is
the durable substrate for pending and resolved actions.

## Files to Inspect

Start with these files when debugging Guardian:

- `chief_guardian_listener.py`
- `chief_guardian_sender.py`
- `hitl_action_service.py`
- `hitl_pending_store.py`
- `tests/test_cassandra_telegram_draft_approval_send_authority.py`
- `tests/test_guardian_packet_templates.py`
- `templates/agent/guardian_approval_request_packet_template.json`
- `templates/agent/guardian_approval_decision_packet_template.json`

Also inspect current operator action approval request files only when the task
explicitly asks for that approval lane and the files are not secrets.

## Hard Boundaries

Guardian must not:

- Execute business logic after approval.
- Send email itself.
- Mutate Cassandra, Niles, Hermes, or Chief lane state directly.
- Bypass its own approval records.
- Create a second approval system.
- Disclose secrets, env values, tokens, credentials, OAuth material, or account
  configuration.
- Approve vague actions that lack exact action text, target, and scope where
  the runtime requires exact approval.

## Runtime Service Names

Likely Guardian-related user service:

- `chief-guardian-listener.service`

Related service template:

- `systemd/user/chief-guardian-listener.service.in`

Inspect service state only when the task asks for runtime verification. Do not
restart services from this maintenance guide alone.

## What Not to Start

Do not start from a Guardian maintenance task unless explicitly scoped:

- Cassandra listener.
- Chief workers.
- Hermes gateway or sidecars.
- Niles workers or DAW/audio tools.
- Browser, email, calendar, contacts, Coupa, bank, or external API tools.

## What Not to Mutate

Do not mutate:

- Business objects after a decision is recorded.
- Invoices, ledgers, workbooks, PDFs, Coupa records, bank records, or paid
  status.
- Cassandra/Niles/Hermes runtime state.
- Runtime policy or confirmed reference data.
- Approval records outside the existing `hitl_action_service.py` and
  `hitl_pending_store.py` patterns.

## Tests / Validation

Choose the narrowest local validation set for the change. Common
Guardian-adjacent checks include:

```bash
.venv/bin/python -m pytest -s -q tests/test_cassandra_telegram_draft_approval_send_authority.py
.venv/bin/python -m pytest -s -q tests/test_guardian_packet_templates.py
.venv/bin/python -m pytest -s -q tests/test_guardian_protected_access_gate_spec.py
python3 -m py_compile chief_guardian_listener.py chief_guardian_sender.py hitl_action_service.py hitl_pending_store.py
git diff --check
```

If a listed test file is absent or renamed, inspect the current `tests/`
directory and run the closest scoped test. Do not perform live approvals unless
the active task explicitly asks for a live smoke.

## Current Known Caveats

- Exact-send tests can create local fixture HITL records; that is not the same
  as a live send.
- Guardian approval means permission for a bounded action path, not that
  Guardian executes the action.
- Denials and expired actions must remain terminal.
- Duplicate callbacks must not double-execute.
- Approval state must remain receipt-backed and auditable.

## Safety Checklist

Before making Guardian-related changes:

- Confirm the active task allows code or doc edits.
- Run `git status --short` and isolate unrelated drift.
- Verify the difference between approval capture, approval decision, and action
  execution.
- Do not inspect secrets/env/token/credential files.
- Do not send email or mutate business records.
- Do not add a bypass or parallel approval path.
- Add or run focused tests when code changes are made.
- Run `git diff --check` before committing.
