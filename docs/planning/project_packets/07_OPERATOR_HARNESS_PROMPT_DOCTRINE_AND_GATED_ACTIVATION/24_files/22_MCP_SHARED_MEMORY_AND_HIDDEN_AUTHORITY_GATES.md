# MCP Shared Memory And Hidden Authority Gates

Status type: FUTURE_LANE / BOUNDARY_GUARD

## Purpose

Define MCP/shared-memory review gates so shared context cannot become hidden authority, duplicate memory, private-data leakage, or invisible canonical writes.

## Source Inputs

- Packet 06 `21_MCP_SHARED_MEMORY_ARCHITECTURE_REVIEW.md`
- Packet 06 final `00_ACTIVE_HANDOFF.md`
- Packet 06 final static boundary contract
- `openclaw_sensitive_policy.py`
- `scripts/openclaw_receipts.py`

## What It Governs

- MCP/shared memory as architecture review, not implementation authority.
- Single-source-of-truth requirements.
- Context provenance and receipt requirements.
- Hidden canonical memory write prohibition.
- Receipts/read models as evidence, not approval.

## Repo Implementation Pointers

- `backend_knowledge_packet.py`
- `backend_sqlite_repository.py`
- `backend_storage_intelligence.py`
- `scripts/openclaw_receipts.py`
- `tests/test_backend_agent_context.py`

## Valid Future Lane Moves

- Compare MCP/shared memory approaches against existing substrate.
- Draft no-implementation architecture reviews.
- Add static tests or docs that assert receipts do not approve execution.
- Identify when the correct decision is no new layer.

## Forbidden Drift

- No MCP invocation.
- No MCP context ingestion.
- No external MCP calls.
- No hidden memory writes.
- No provider/model calls.
- No private-root exposure.
- No treating shared memory as accepted truth.

## Review Boundary

Review before any MCP, shared memory, external app connector, memory server, context registry, or cross-agent memory lane.

## Why It Should Last 10-20 Moves

Shared memory will remain tempting. This rail keeps review ahead of implementation and blocks hidden authority.
