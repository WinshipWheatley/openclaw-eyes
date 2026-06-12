# Hermes Maintenance Guide

This markdown file is a maintenance guide for Claude Code, Codex, and Fable
sessions. It is not runtime code, not a policy source, and not an authority
grant.

Runtime truth lives in Python, systemd units, generated read models, receipts,
and adapter contracts. Use this guide to orient before inspecting the real
files.

## Current Role

Hermes owns adapter and protocol boundaries:

- Adapter/protocol boundary review.
- Bridge health and advisory posture.
- Connector/tool wrapper readiness.
- Sidecar contract inventory.
- Capability and authority fit checks before any tool execution path.

Hermes is not the business logic owner. Hermes should describe, stage, or review
adapter capability boundaries rather than execute business actions.

## Execution Mode

Hermes' default maintenance posture is:

- `unsafe_to_start` unless explicitly bounded and approved.
- `sidecar_adapter` only when a task names a bounded adapter inspection or
  contract path.

`hermes-gateway.service` may exist, but it should remain stopped if crash-looping
or policy-unbounded. Do not launch generic Hermes sidecars from stale
assumptions.

## Files to Inspect

Start with metadata and contract surfaces:

- `openclaw_hermes_sidecar.py`
- `tool_protocol_adapter_registry_contract.py`
- `tool_adapter_receipt_contract.py`
- `openclaw_event_bridge_adapter.py`
- `openclaw_event_bridge_contract.py`
- `bridge_routing_operator_attention_contract.py`
- `sidecars/hermes/` as metadata/contract inspection only.
- `generated/read_models/openclaw_hermes_sidecar.json`
- `generated/read_models/hermes_sidecar_inventory.json`
- `generated/read_models/hermes_mission_sentinel.json`
- `generated/read_models/hermes_gravity_controller.json`
- `generated/read_models/tool_protocol_adapter_registry_contract.json`

Do not inspect connector secrets, env files, token stores, or credential files.

## Hard Boundaries

Hermes must not:

- Launch a generic sidecar or MCP/gateway agent without explicit bounded
  authorization.
- Read connector secrets, tokens, credentials, OAuth material, or env files.
- Own or execute business logic.
- Hold raw secrets.
- Approve actions.
- Execute tools directly without capability and authority checks.
- Mutate Cassandra, Niles, Chief, Guardian, invoices, ledgers, workbooks, PDFs,
  runtime policy, confirmed reference data, or external systems.

## Runtime Service Names

Likely Hermes-related user service:

- `hermes-gateway.service`

Related service template:

- `systemd/user/hermes-gateway.service.in`

Inspect service state only when the task asks for runtime verification. Do not
restart or start Hermes from this maintenance guide alone.

## What Not to Start

Do not start:

- `hermes-gateway.service` unless the active task explicitly authorizes a
  bounded smoke or recovery.
- `sidecars/hermes/mcp_serve.py`
- `sidecars/hermes/run_agent.py`
- Generic MCP/gateway agents.
- Browser, email, calendar, contacts, Coupa, bank, DAW, Logic, Ableton, OBS, or
  external API tools.

## What Not to Mutate

Do not mutate:

- Connector configuration, secrets, tokens, credentials, or env files.
- Adapter runtime state unless explicitly scoped.
- Invoices, ledgers, workbooks, PDFs, Coupa records, bank records, or paid
  status.
- Runtime policy or confirmed reference data.
- Approval records.
- Generated read models unless the active task is explicitly an export/update
  task for those artifacts.

## Tests / Validation

Choose the narrowest local validation set for the change. Common
Hermes-adjacent checks include:

```bash
.venv/bin/python -m pytest -s -q tests/test_openclaw_hermes_sidecar.py
.venv/bin/python -m pytest -s -q tests/test_tool_protocol_adapter_registry_contract.py
.venv/bin/python -m pytest -s -q tests/test_tool_adapter_receipt_contract.py
.venv/bin/python -m pytest -s -q tests/test_openclaw_event_bridge_adapter.py
python3 -m py_compile openclaw_hermes_sidecar.py tool_protocol_adapter_registry_contract.py tool_adapter_receipt_contract.py
git diff --check
```

If a listed test file is absent or renamed, inspect the current `tests/`
directory and run the closest scoped test. Do not run a live gateway smoke
unless the active task explicitly authorizes it.

## Current Known Caveats

- Hermes gateway may be unsafe to start if crash-looping or policy-unbounded.
- Some `sidecars/hermes/` files look like runnable agent or MCP entry points;
  treat them as off-limits unless explicitly scoped.
- Read-model inventory can describe sidecar posture without launching it.
- Adapter readiness does not grant execution authority.
- Hermes cannot approve actions; Guardian owns approval decisions.

## Safety Checklist

Before making Hermes-related changes:

- Confirm the active task allows code or doc edits.
- Run `git status --short` and isolate unrelated drift.
- Prefer metadata/contract inspection over runtime launch.
- Do not inspect secrets/env/token/credential files.
- Do not start MCP, gateway, or generic sidecar agents.
- Do not execute connector tools without explicit capability and authority.
- Add or run focused tests when code changes are made.
- Run `git diff --check` before committing.
