# Backend Retrieval Strategy Breadcrumb

Generated/reviewed: 2026-05-06

## 1. Status / Non-Authority

This is a docs-only planning breadcrumb. It captures future retrieval-strategy considerations—specifically PageIndex and vectorless RAG concepts—to ensure current data-contract and schema work preserves necessary document structures.

It does not authorize implementation. It strictly forbids implementing PageIndex, RAG, retrieval logic, indexing, embeddings, ingestion, SQLite runtime behavior, SQL execution, database behavior, APIs, provider/model calls, MCPs, Hermes, sync routines, frontend/app behavior, or private-root inspection.

## 2. Retrieval Architecture Flexibility

OpenClaw’s future retrieval layer should not assume vector embeddings are the only retrieval primitive.

While vector search may still be useful for broad cross-document discovery, complex and long structured documents (like legal contracts, financial filings, source-set bridges, planning packets, and operator-system docs) often degrade when flattened into raw text chunks. They may need:

- Tree-structured section navigation.
- Summaries at multiple levels (document, section, paragraph).
- Provenance tracking and explicit references.
- LLM-guided hierarchical traversal.

PageIndex (and the broader category of vectorless RAG) is a future retrieval-strategy candidate that demonstrates why preserving document shape is critical for high-accuracy reasoning.

## 3. Hybrid Routing Future

A future retrieval architecture should recommend hybrid routing across several primitives:

- Metadata search (exact match, state, tags)
- Keyword / Full-Text Search (FTS)
- Vector search (semantic proximity)
- Tree / hierarchical reasoning (navigating document structure)
- Provenance / relationship traversal (following edges between semantic records)

## 4. Tie to Current SQLite / Schema Work

This future flexibility relies heavily on the foundational SQLite schema-contract work happening now. To support tree-structured retrieval later, the current schema concepts must:

- Preserve document hierarchy.
- Preserve section and page references.
- Preserve summaries at multiple levels.
- Preserve explicit provenance references (`provenance_refs`).
- Preserve relationship edges (`semantic_relationships`).
- Preserve freshness, confidence, authority, sensitivity, and review labels (`semantic_labels`).

If the baseline SQLite tables flatten all knowledge into detached, context-free chunks, future hierarchical traversal becomes impossible.

## 5. Explicit Forbids

This breadcrumb explicitly forbids implementation now. There must be:

- No PageIndex dependency added.
- No RAG implementation.
- No indexing logic.
- No embedding generation or storage.
- No retrieval runtime.
- No provider or model calls.
- No file ingestion or parsing.
- No database changes, SQLite runtime, or SQL execution.

## 6. Source Caution

PageIndex’s 98.7% FinanceBench accuracy claim should be treated as a vendor/ecosystem claim unless independently verified. The actionable lesson for OpenClaw is the necessity of retrieval architecture flexibility and structural preservation, not benchmark chasing.
