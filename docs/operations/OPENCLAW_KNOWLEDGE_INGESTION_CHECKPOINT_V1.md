# Canonical Knowledge Ingestion Checkpoint V1

**Date:** 2026-05-11
**Commit:** 7933bd2
**Status:** Operational (Verified via Live Smoke Test)

## Overview
This document checkpoints the formalization of the deterministic, agent-based canonical knowledge ingestion pipeline. The system provides a secure, read-only mechanism to ingest, store, and query canonical documentation while ensuring strict source immutability.

## Completed Chunks
1. **Canonical Fact Ledger:** Schema design and SQL-verified writer for `canonical_facts` table.
2. **Deterministic Markdown Extractor:** Section-splitting based on `##` headers.
3. **Ingestion Harness:** Single-doc, read-only ingestion script with path validation.
4. **Retrieval Helpers:** Read-only fact retrieval utilities enforcing `mode=ro` SQLite URI.
5. **Query CLI:** Deterministic tool for fact inspection (`query_canonical_facts.py`).
6. **Immutability Hardening:** Regression testing ensuring source files remain binary-identical post-ingestion.
7. **Live Smoke Flow:** Verified ingestion and retrieval of `docs/operations/OPENCLAW_RECEIPT_SPINE_CHECKPOINT_V9.md`.

## Current Scope & Boundaries
- **Source:** Limited strictly to `docs/operations/OPENCLAW_RECEIPT_SPINE_CHECKPOINT_V9.md`.
- **Nature of Facts:** Canonical, source-grounded reference material only.

### Exclusions & Prohibitions
- **Not Receipts:** Canonical facts are reference documents, not transaction receipts.
- **Not Runtime:** Does not constitute runtime authority or system control.
- **Not Memory:** These are not ingested into agent long-term memory or personality vectors.
- **Not Semantic:** No vector embeddings or semantic search implementations.
- **Prohibited Surfaces:** Access to secrets, `.env`, `.pii_vault.enc`, Gmail, PII, outreach, legal-private data, DAW, runtime state, sidecar services, generated files, or private user data is strictly forbidden.

## Roadmap & Next Steps
1. **Deterministic Answer Harness:** Build "Where are we?" query capability.
2. **Context Packet Integration:** Formalize knowledge ingestion into context packets.
3. **Source Expansion:** Carefully audit and expand the allowed source list.
