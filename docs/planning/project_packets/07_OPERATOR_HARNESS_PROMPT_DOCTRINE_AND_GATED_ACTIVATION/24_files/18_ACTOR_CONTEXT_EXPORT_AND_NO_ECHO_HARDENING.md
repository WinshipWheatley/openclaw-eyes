# Actor Context Export And No-Echo Hardening

Status type: BOUNDARY_GUARD / FUTURE_LANE

## Purpose

Carry forward actor/context export hardening so agents, sidecars, receipts, and review packets cannot leak denied sensitive/private path hints or treat exported context as action authority.

## Source Inputs

- Packet 06 `17_ACTOR_SIDECAR_AND_CONTEXT_EXPORT_HARDENING_PLAN.md`
- Packet 06 `11_ACTOR_REGISTRY_AND_TRUST_BRIDGE_TRUTH.md`
- Packet 06 final `00_ACTIVE_HANDOFF.md`
- `backend_knowledge_packet.py`
- `tests/test_backend_agent_context.py`

## What It Governs

- Deny-by-default context export behavior.
- No-echo handling for denied seed/path hints.
- Distinction between receipts, summaries, context packets, and authority.
- Sidecar trust tiers and sensitivity ceilings.

## Repo Implementation Pointers

- `backend_knowledge_packet.py`
- `backend_data_contract.py`
- `backend_sqlite_schema.py`
- `backend_sqlite_repository.py`
- `tests/test_backend_agent_context.py`

## Valid Future Lane Moves

- Add focused no-echo tests for denied export paths.
- Review sidecar profile read models.
- Bridge sensitive/legal policy into export decisions.
- Add receipt language for withheld surfaces.

## Forbidden Drift

- No cloud sidecar private data access.
- No fake sanitizer.
- No actor treating export as approval, runtime authority, send authority, or MCP authority.
- No provider/model call or MCP invocation from this rail.

## Review Boundary

Review before any sidecar receives context, any actor expands trust, or any prompt says "sanitized" without proof and receipt semantics.

## Why It Should Last 10-20 Moves

Context export is a repeated leak surface. Packet 07 should keep it fail-closed while prompt doctrine improves routing.
