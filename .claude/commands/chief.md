# Chief Maintenance Guide

This markdown file is a maintenance guide for Claude Code, Codex, and Fable
sessions. It is not runtime code, not a policy source, and not an authority
grant.

Runtime truth lives in Python, systemd units, generated read models, and
receipts. Use this guide to orient before inspecting the real files.

## Current Role

Chief owns system-level coordination:

- System orchestration and runtime triage.
- Model routing policy and model work package routing.
- Proof harnesses, acceptance checks, and validation posture.
- Codex work packet preparation.
- Service health, sync health, and Watch Desk input preparation.
- Routing operator requests to the correct lane instead of doing every lane's
  work directly.

## Execution Mode

Chief's normal execution mode is:

- `systemd_service`
- `hardcoded_route`

Chief can prepare packets, route work, summarize health, and coordinate local
validation. Chief should not treat orientation docs as permission to perform
external, destructive, or approval-gated actions.

## Files to Inspect

Start with these files when debugging Chief:

- `chief_listener.py`
- `chief_worker.py`
- `chief_memory_worker.py`
- `chief_state_worker.py`
- `chief_watcher_brain.py`
- `model_selection_policy_contract.py`
- `model_router_policy.py`
- `model_work_package_router.py`
- `watch_desk_feed.py`

Related service templates:

- `systemd/user/chief-listener.service.in`
- `systemd/user/chief-worker.service.in`
- `systemd/user/chief-memory-worker.service.in`
- `systemd/user/chief-state-worker.service.in`
- `systemd/user/chief-watcher-brain.service.in`

## Hard Boundaries

Chief must not:

- Bypass Guardian or exact-action approval rails.
- Execute Cassandra, Niles, Guardian, or Hermes lane work directly.
- Create approvals except through approved HITL patterns already present in
  runtime code.
- Read secrets, env files, tokens, credentials, SSH keys, OAuth material, or
  account configuration secrets.
- Mutate runtime systems, external systems, ledgers, invoices, workbooks, PDFs,
  generated reference truth, or policy state unless the active task explicitly
  allows it.
- Treat generated read models as writable source truth unless the active task is
  specifically a read-model export/update task.

## Runtime Service Names

Likely Chief-related user services:

- `chief-listener.service`
- `chief-worker.service`
- `chief-memory-worker.service`
- `chief-state-worker.service`
- `chief-watcher-brain.service`

Inspect service state only when the task asks for runtime verification. Do not
restart services from this maintenance guide alone.

## What Not to Start

Do not start from a Chief maintenance task unless explicitly scoped:

- Cassandra listener or Cassandra lane workers.
- Guardian listener.
- Hermes gateway or generic sidecars.
- Niles workers or any DAW/audio tools.
- Browser, email, calendar, contacts, Coupa, bank, or external API tools.

## What Not to Mutate

Do not mutate:

- Invoices, ledgers, workbooks, PDFs, Coupa records, bank records, or paid
  status.
- Runtime policy or confirmed reference data.
- Generated read models or SQLite files unless the task is explicitly an export
  or migration task for those artifacts.
- Approval queues outside the existing HITL service/store patterns.
- Another agent's lane-specific state.

## Tests / Validation

Choose the narrowest local validation set for the change. Common Chief-adjacent
checks include:

```bash
.venv/bin/python -m pytest -s -q tests/test_agent_lane_registry.py
.venv/bin/python -m pytest -s -q tests/test_watch_desk_feed.py
.venv/bin/python -m pytest -s -q tests/test_cassandra_make_it_so_objective_loop.py
.venv/bin/python -m pytest -s -q tests/test_model_work_package_router.py
python3 -m py_compile chief_listener.py chief_worker.py chief_memory_worker.py chief_state_worker.py chief_watcher_brain.py
git diff --check
```

If a listed test file is absent or renamed, inspect the current `tests/`
directory and run the closest scoped test. Do not expand into live service
tests unless the active task asks for that.

## Current Known Caveats

- Chief is a coordinator, not the business executor for every lane.
- Watch Desk is read-only aggregation over existing receipts/read models.
- Model work packages are metadata/advisory unless an explicit gate grants more
  authority.
- Some generated read models may be dirty from prior local runtime activity; do
  not reset or commit unrelated generated drift.
- Service health claims should be backed by current systemd/process/log checks,
  not stale assumptions.

## Safety Checklist

Before making Chief-related changes:

- Confirm the active task allows code or doc edits.
- Run `git status --short` and isolate unrelated drift.
- Identify whether the problem is listener, worker, state, memory, model
  routing, Watch Desk, or lane routing.
- Do not inspect secrets/env/token/credential files.
- Do not bypass Guardian or create a second approval path.
- Do not mutate external systems or business records.
- Add or run focused tests when code changes are made.
- Run `git diff --check` before committing.
