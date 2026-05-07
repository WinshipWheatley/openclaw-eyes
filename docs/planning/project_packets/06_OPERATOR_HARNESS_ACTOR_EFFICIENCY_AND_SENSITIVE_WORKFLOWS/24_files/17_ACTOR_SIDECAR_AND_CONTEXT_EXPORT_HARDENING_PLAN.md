# Actor Sidecar And Context Export Hardening Plan

Status type: FUTURE_LANE / BOUNDARY_GUARD

## Purpose

Define a future hardening lane for actor sidecars and context export so external or cloud-adjacent agents remain deny-by-default, scoped, receipt-backed, and unable to receive fake-sanitized sensitive context.

## Source Inputs

- Packet 05 `00_ACTIVE_HANDOFF.md`
- Packet 05 `07_04_CONTEXT_DEVELOPMENT_LIFECYCLE_AND_CONTEXT_FILTER_DOCTRINE.md`
- Packet 05 `19_backend_data_contract_semantic_contract_matrix_20260505.md`
- Sensitive Root Registry breadcrumb
- Live Arts invoice reconciliation breadcrumb

## What It Governs

- Actor profile and context export semantics.
- Sidecar trust tiers and sensitivity ceilings.
- Receipt requirements for context export.
- Local-only versus cloud-sidecar behavior.
- Sanitization as real, approved, and receipt-backed.

## Repo Implementation Pointers

- `backend_data_contract.py`
- `backend_sqlite_schema.py`
- `backend_sqlite_repository.py`
- `backend_knowledge_packet.py`
- `tests/test_backend_agent_context.py`

## Valid Future Lane Moves

- Add hardening tests for deny-by-default export behavior after explicit implementation authority.
- Plan sidecar profile read models.
- Plan context export receipts that include withheld surfaces.
- Bridge sensitive-root registry policy into actor access decisions.

## Forbidden Drift

- No cloud sidecar private data access.
- No fake sanitizer.
- No external LLM access to sensitive roots.
- No actor or sidecar treating context as action authority.
- No provider/model call or MCP invocation from this plan.

## Review Boundary

Review before any sidecar receives context, any actor lane expands trust, or any future prompt says "sanitized" without proof and receipt semantics.

## Why It Should Last 10-20 Moves

Sidecar and export boundaries are a repeated risk surface. This rail should keep many future prompts fail-closed.
