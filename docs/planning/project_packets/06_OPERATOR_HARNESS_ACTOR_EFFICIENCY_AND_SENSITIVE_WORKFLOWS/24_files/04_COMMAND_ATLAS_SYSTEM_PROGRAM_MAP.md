# Command Atlas System Program Map

Status type: OPERATING_DOCTRINE

## Purpose

Preserve Command Atlas as the top planning layer. Operator Harness is a lane and cockpit under the system program, not the whole system.

## Source Inputs

- Packet 05 `06_00_COMMAND_ATLAS_SYSTEM_PROGRAM_MAP.md`
- Packet 05 `14_24_OPERATOR_HARNESS_PLANNING_INDEX.md`
- Packet 05 `13_19_OPERATOR_WORLD_MODEL_BUILD_READINESS_ADDENDUM.md`
- `OPENCLAW_RUNTIME.md`
- `CORE_ARCHITECTURE_PRINCIPLES.md`
- Sensitive Root Registry breadcrumb
- CLI Receipt Layer breadcrumb

## What It Governs

- Lane identity.
- Private and sensitive root boundaries.
- Operator Harness as view/cockpit, not authority.
- Chief, Cassandra, Guardian, Hermes, runtime, legal, finance, music-law, bridge, and build-loop separation.
- Future runtime, MCP, and sidecar work as reviewed architecture lanes before implementation.

## Repo Implementation Pointers

- `backend_knowledge_packet.py`
- `backend_storage_intelligence.py`
- `backend_sqlite_repository.py`
- `tests/test_backend_agent_context.py`

## Valid Future Lane Moves

- Operator Harness read-model planning.
- Runtime integration architecture review.
- MCP/shared memory architecture review.
- Sensitive-root registry planning as metadata and policy, not content access.
- External communication and billing draft policy through explicit authority classes.

## Forbidden Drift

- Do not flatten Command Atlas into the Operator Harness screen.
- Do not treat UI display as authority.
- Do not let bridge visibility, mirror paths, or receipt availability become canon.
- Do not treat Cassandra, billing, legal, or communications lanes as send/action authority.

## Review Boundary

Review this file before any prompt touches lane identity, runtime surfaces, sidecars, MCP/shared memory, sensitive roots, or Operator Harness scope.

## Why It Should Last 10-20 Moves

The lane map changes slowly. It should absorb multiple future prompts while preventing each lane from swallowing the others.
