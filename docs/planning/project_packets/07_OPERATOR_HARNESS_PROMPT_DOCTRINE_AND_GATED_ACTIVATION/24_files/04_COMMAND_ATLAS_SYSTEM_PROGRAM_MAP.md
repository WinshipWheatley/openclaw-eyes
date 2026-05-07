# Command Atlas System Program Map

Status type: OPERATING_DOCTRINE

## Purpose

Preserve Command Atlas as the top planning layer. Operator Harness, receipt rails, prompt doctrine, and gated activation are lanes within the system, not replacements for the system.

## Source Inputs

- Packet 06 `04_COMMAND_ATLAS_SYSTEM_PROGRAM_MAP.md`
- Packet 06 final `00_ACTIVE_HANDOFF.md`
- Packet 06 `18_OPERATOR_HARNESS_READ_MODEL_PLAN.md`
- Packet 06 `22_RUNTIME_AUTHORITY_AND_LEGACY_GATING.md`
- `OPENCLAW_RUNTIME.md`
- `CORE_ARCHITECTURE_PRINCIPLES.md`

## What It Governs

- Lane identity and separation.
- Operator Harness as cockpit/read model, not execution authority.
- Chief, Cassandra, legal, finance, runtime, MCP, storage, and creative lanes as separate authority classes.
- Gated activation work as reviewed architecture before implementation.

## Repo Implementation Pointers

- `backend_knowledge_packet.py`
- `backend_storage_intelligence.py`
- `backend_sqlite_repository.py`
- `scripts/openclaw_receipts.py`
- `tests/test_backend_agent_context.py`

## Valid Future Lane Moves

- Prompt doctrine and review routing.
- Operator Harness read-model compatibility review.
- Runtime activation readiness audit.
- Sensitive/legal/billing boundary planning.
- MCP/shared-memory architecture review.

## Forbidden Drift

- Do not flatten Command Atlas into one screen, one receipt, or one hidden memory.
- Do not treat UI visibility as authority.
- Do not let Cassandra, billing, legal, runtime, or communications lanes send or act without explicit approval.
- Do not let packet renewal rewrite lane ownership.

## Review Boundary

Review before prompts touch lane identity, authority routing, runtime surfaces, sidecars, MCP/shared memory, or Operator Harness scope.

## Why It Should Last 10-20 Moves

The lane map changes slowly. It should absorb Packet 07 work while preventing gated activation from swallowing doctrine and authority boundaries.
