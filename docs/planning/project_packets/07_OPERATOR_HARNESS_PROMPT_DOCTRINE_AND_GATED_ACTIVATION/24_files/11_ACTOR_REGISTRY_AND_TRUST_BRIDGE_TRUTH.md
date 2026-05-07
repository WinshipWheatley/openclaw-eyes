# Actor Registry And Trust Bridge Truth

Status type: BUILT_TRUTH

## Purpose

Preserve actor registry and context export trust bridge as built truth for Packet 07 sidecar, billing, legal, prompt-routing, and Operator Harness planning.

## Source Inputs

- Packet 06 `11_ACTOR_REGISTRY_AND_TRUST_BRIDGE_TRUTH.md`
- Packet 06 `17_ACTOR_SIDECAR_AND_CONTEXT_EXPORT_HARDENING_PLAN.md`
- Packet 06 final `00_ACTIVE_HANDOFF.md`
- `tests/test_backend_agent_context.py`

## What It Governs

- Actor profiles, lanes, classes, trust tiers, and sensitivity ceilings.
- Context export receipts and deny-by-default behavior.
- Profile access is not runtime authority.
- Export is not action.
- Cloud sidecars deny by default unless context is approved, public/sanitized, and receipt-backed.

## Repo Implementation Pointers

- `backend_data_contract.py`
- `backend_sqlite_schema.py`
- `backend_sqlite_repository.py`
- `backend_knowledge_packet.py`
- `tests/test_backend_agent_context.py`

## Valid Future Lane Moves

- Actor context export no-echo hardening.
- Sensitive/legal policy integration with actor classes.
- Billing actor draft-only context planning.
- Tool-specific prompt routing by actor role.

## Forbidden Drift

- No fake sanitizer.
- No cloud sidecar access to private or sensitive content.
- No actor profile becoming approval, runtime authority, send authority, or MCP authority.
- No external LLM access to sensitive roots.

## Review Boundary

Review before sidecar, Cassandra, billing, legal, cloud, MCP, or external-agent context export work.

## Why It Should Last 10-20 Moves

Trust boundaries recur across Packet 07. This rail keeps actor identity, context export, and action authority separate.
