# Operator Harness Knowledge Substrate

Status: docs/test-only planning package. This package does not create a database, ingest files, scan business archives, call providers/models, or authorize app/backend/runtime implementation.

## Purpose

This lane defines the future SQLite-backed Compiled Knowledge Substrate for Operator Harness app planning. It gives future chats and implementers a recoverable product contract before `03_BACKEND_AND_DATA_MODEL` starts.

This is not vanilla RAG. It is not classic flat chunk-vector RAG. The substrate is a compile-first local memory system inspired by Karpathy-style LLM Wiki thinking: retrieval finds candidates, compilation creates durable inspectable knowledge, and operator promotions decide what becomes accepted working context.

Core phrase:

> SQLite stores the memory; markdown speaks it; HTML preserves shape; FTS finds it; compiled notes make it useful.

## Authority

SQLite should be treated as the canonical local memory substrate. Markdown is an export and handoff surface, not the database authority. HTML or rich fragments preserve source shape where structure matters. FTS5/search finds relevant records quickly. Compiled notes make recurring knowledge useful.

Raw files are evidence, not truth. Extracted text is parsed evidence, not truth. Compiled notes are interpretation, not truth. Claims are evidence-backed and confidence-bounded, not truth by default. Operator promotions determine what is accepted, rejected, marked historical, marked sensitive, or excluded.

Unknown means unknown; do not soften it into confidence.

## Hard Boundary

This package is app-planning only and does not authorize ingestion.

It must not:

- create a real SQLite database;
- create ingestion scripts;
- perform real business-file scanning. No real business-file scanning is authorized here;
- scan old business files;
- inspect private paths, vault paths, logs, LegalPrivate, secrets, Gmail, or cloud drives;
- call external providers/models;
- summarize secrets or credentials into prompts;
- imply Mac desktop app, backend/API/schema, or runtime implementation has started.

## Package Files

- `01_NORTH_STAR.md`: why this substrate exists and how truth/interpretation boundaries work.
- `02_SQLITE_LAYER_MODEL.md`: conceptual SQLite layers/tables and what they must not imply.
- `03_SAFETY_AND_SENSITIVITY_LEVELS.md`: local-first safety levels and restricted defaults.
- `04_APP_CARDS_AND_UI_STATES.md`: future app cards and evidence-backed state language.
- `05_FIXTURE_PLAN.md`: synthetic fixture names and validation meanings.
- `06_STATIC_VALIDATION_EXPECTATIONS.md`: static checks for this package.
- `INDEX.md`: short navigation index.

## Mirror Posture

The Mac mirror for review is adjacent to Operator Harness readiness:

```text
~/OpenClaw_Watch/operator_harness_knowledge_substrate/
```

It is not inside:

```text
~/OpenClaw_Watch/operator_harness_readiness/
```

Do not create a numbered ChatGPT Project source-set folder for this package yet.
