# Context Substrate And Traversal Truth

Status type: BUILT_TRUTH

## Purpose

Preserve the built knowledge packet, seed, traversal, and context substrate as proof that OpenClaw already has deterministic context machinery to build on.

## Source Inputs

- Packet 05 `00_ACTIVE_HANDOFF.md`
- Packet 05 `07_04_CONTEXT_DEVELOPMENT_LIFECYCLE_AND_CONTEXT_FILTER_DOCTRINE.md`
- Packet 05 `19_backend_data_contract_semantic_contract_matrix_20260505.md`
- Packet 05 active handoff built-state ledger
- CLI Receipt Layer breadcrumb

## What It Governs

- Deterministic seeds and bounded traversal as built context substrate.
- Context packets as non-authorizing, policy-bound summaries.
- Context lifecycle doctrine: generated, validated, packaged, observed, and regenerated.
- The principle that context-visible does not mean authorized.

## Repo Implementation Pointers

- `backend_knowledge_packet.py`
- `tests/test_backend_knowledge_packet.py`
- `tests/test_backend_agent_context.py`

## Valid Future Lane Moves

- Plan context export hardening.
- Plan low-context prompt packs and receipts.
- Plan Operator Harness read models that show packet provenance and withheld surfaces.
- Review MCP/shared memory as an architecture layer, not an authority bypass.

## Forbidden Drift

- Do not treat context packets as complete truth.
- Do not use context summaries to launder excluded or private data.
- Do not invoke providers, MCPs, Hermes, sync, ingestion, extraction, indexing, or embeddings from this rail.
- Do not create fake sanitization.

## Review Boundary

Review when a future prompt assembles context for an agent, sidecar, Project chat, MCP surface, or Operator Harness view.

## Why It Should Last 10-20 Moves

Most Packet 06 lanes depend on context being cheap, precise, and policy-bound. This rail should remain useful across those moves.
