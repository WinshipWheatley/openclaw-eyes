# Actor Registry And Trust Bridge Truth

Status type: BUILT_TRUTH

## Purpose

Preserve the actor registry and context export trust bridge as built truth for future sidecar, billing actor, legal export, and Operator Harness planning.

## Source Inputs

- Packet 05 `00_ACTIVE_HANDOFF.md`
- Packet 05 `07_04_CONTEXT_DEVELOPMENT_LIFECYCLE_AND_CONTEXT_FILTER_DOCTRINE.md`
- Packet 05 `19_backend_data_contract_semantic_contract_matrix_20260505.md`
- Sensitive Root Registry breadcrumb
- Live Arts invoice reconciliation breadcrumb

## What It Governs

- Actor profiles, lanes, classes, trust tiers, and sensitivity ceilings.
- Context export receipts and deny-by-default behavior.
- The rule that profile access is not runtime authority.
- The rule that export is not action.
- Cloud sidecars deny by default unless context is approved, public/sanitized, and receipt-backed.

## Repo Implementation Pointers

- `backend_data_contract.py`
- `backend_sqlite_schema.py`
- `backend_sqlite_repository.py`
- `backend_knowledge_packet.py`
- `tests/test_backend_agent_context.py`

## Valid Future Lane Moves

- Actor sidecar and context export hardening.
- Sensitive-root policy integration with actor classes.
- Billing actor draft-only context planning.
- Legal context export policy planning.

## Forbidden Drift

- No fake `sanitize_packet()` placeholder.
- No cloud sidecar access to private or sensitive content.
- No actor profile treating itself as approval, runtime authority, or send authority.
- No external LLM access to sensitive roots.

## Review Boundary

Review before any sidecar, Cassandra, billing, legal, cloud, MCP, or external-agent context export lane.

## Why It Should Last 10-20 Moves

Trust boundaries will recur across Packet 06. This rail keeps actor identity and context export authority separate from action.
