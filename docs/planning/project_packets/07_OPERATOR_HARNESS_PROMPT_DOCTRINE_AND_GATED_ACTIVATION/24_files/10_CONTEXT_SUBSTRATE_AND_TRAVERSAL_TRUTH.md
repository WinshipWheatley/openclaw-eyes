# Context Substrate And Traversal Truth

Status type: BUILT_TRUTH

## Purpose

Preserve deterministic knowledge packet, seed, traversal, and context substrate as built truth for Packet 07 prompt, receipt, actor, and MCP review work.

## Source Inputs

- Packet 06 `10_CONTEXT_SUBSTRATE_AND_TRAVERSAL_TRUTH.md`
- Packet 06 `17_ACTOR_SIDECAR_AND_CONTEXT_EXPORT_HARDENING_PLAN.md`
- Packet 06 `21_MCP_SHARED_MEMORY_ARCHITECTURE_REVIEW.md`
- Packet 06 final `00_ACTIVE_HANDOFF.md`

## What It Governs

- Deterministic seeds and bounded traversal as context substrate.
- Context packets as non-authorizing, policy-bound summaries.
- Generated, validated, packaged, observed, and regenerated context lifecycle.
- Context-visible does not mean authorized.

## Repo Implementation Pointers

- `backend_knowledge_packet.py`
- `tests/test_backend_knowledge_packet.py`
- `tests/test_backend_agent_context.py`

## Valid Future Lane Moves

- Plan context export hardening.
- Plan low-context prompt packs and receipt-fed read models.
- Review MCP/shared memory as architecture, not authority.
- Add no-echo/no-content tests only through bounded implementation prompts.

## Forbidden Drift

- Do not treat context packets as complete truth.
- Do not launder excluded or private data through summaries.
- Do not invoke providers, MCPs, sync, ingestion, indexing, extraction, or embeddings from this rail.
- Do not create fake sanitization.

## Review Boundary

Review when assembling context for agents, sidecars, Project chats, MCP surfaces, or Operator Harness views.

## Why It Should Last 10-20 Moves

Packet 07 depends on cheap, precise, policy-bound context. This rail preserves that substrate without reopening implementation.
