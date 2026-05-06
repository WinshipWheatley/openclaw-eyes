# Knowledge Substrate North Star

Status: docs/test-only planning contract. This file does not authorize ingestion, database creation, external model access, app implementation, backend/schema implementation, or private-data inspection.

## Definition

The Compiled Knowledge Substrate is the future local memory layer for Operator Harness. It should let the operator safely discover, classify, compile, and converse with durable knowledge while preserving evidence boundaries.

It is SQLite-backed, local-first, inspectable, and evidence-aware. It is not vanilla RAG and not classic flat chunk-vector RAG. Retrieval finds candidates. Compilation creates durable notes. Operator promotions decide what becomes accepted working context.

Core phrase:

> SQLite stores the memory; markdown speaks it; HTML preserves shape; FTS finds it; compiled notes make it useful.

## Why Operator Harness Needs It

Operator Harness will eventually span personal systems, client/company systems, Launch Ladders, evidence trails, source-set refreshes, app views, and historical context. A simple chat transcript or pile of embeddings cannot safely represent that.

The substrate should preserve:

- source basis and provenance;
- source shape where layout matters;
- extracted text and parsing warnings;
- classifications and sensitivity;
- evidence-backed claims;
- contradictions;
- compiled notes;
- explicit operator promotions;
- stale conditions and refresh triggers;
- conversation packets for safe handoff.

## Old Business Files Motivation

The operator has historical business-operation files from periods when they were not directly managing the business. The future system should provide a safe way to surface, classify, summarize, and converse with those records without overclaiming.

Those files may contain client names, contracts, payments, tax details, publishing splits, private correspondence, operational history, and sensitive music-law or business context. This planning package does not inspect those files.

## Evidence And Truth Boundary

- Raw files are evidence, not truth.
- Extracted text is parsed evidence, not truth.
- Rendered fragments preserve source shape, not truth.
- Classifications are system/operator labels, not truth.
- Claims are evidence-backed and confidence-bounded, not truth by default.
- Compiled notes are interpretation, not truth.
- Operator promotions are explicit acceptance, rejection, historical marking, sensitivity marking, or exclusion.

Unknown means unknown; do not soften it into confidence.

## Promotion Model

The substrate should make promotion explicit:

- `accepted`: operator accepts a compiled note or claim for current working context.
- `rejected`: operator rejects a note, claim, classification, or extraction.
- `marked_historical`: operator says the record matters as historical context but should not drive current-state claims.
- `marked_sensitive`: operator elevates sensitivity or blocks export.
- `excluded`: operator removes the artifact from active retrieval/compilation surfaces.

No compiled note, claim, or model summary becomes authority without an operator promotion or another explicit authority record.

## Non-Goals

- No real ingestion in this slice.
- No SQLite schema implementation in this slice.
- No file scanning in this slice.
- No provider/model calls in this slice.
- No external model access to raw or extracted sensitive content.
- No app or backend runtime implementation in this slice.
