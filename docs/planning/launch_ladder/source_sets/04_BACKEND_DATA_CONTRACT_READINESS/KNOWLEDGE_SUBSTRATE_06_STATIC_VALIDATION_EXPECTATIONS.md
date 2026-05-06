# Static Validation Expectations

Status: docs/test-only validation plan. These checks describe the contract the repo should preserve before implementation.

## Expected Checks

The lightweight static checker should verify:

- package files exist;
- required terms are present;
- no language authorizes real ingestion;
- no language authorizes external model use on sensitive data;
- no language collapses raw/extracted/compiled/promoted into one truth state;
- app cards preserve evidence/freshness boundaries;
- safety levels include unknown restricted default;
- fixtures are synthetic only;
- no commands scan user directories;
- no private/vault/legal/business files are inspected.

## Required Doctrine Terms

The package must include:

- Compiled Knowledge Substrate;
- SQLite stores the memory; markdown speaks it; HTML preserves shape; FTS finds it; compiled notes make it useful;
- not vanilla RAG;
- not classic flat chunk-vector RAG;
- compile-first knowledge substrate;
- Karpathy-style LLM Wiki thinking;
- retrieval finds candidates;
- compilation creates durable inspectable knowledge;
- SQLite should be treated as the canonical local memory substrate;
- Markdown should be an export/handoff surface, not the database authority;
- HTML/rich fragments preserve source shape where structure matters;
- FTS5/search finds relevant records quickly;
- Compiled notes make recurring knowledge useful;
- Operator promotions determine what is accepted, rejected, marked historical, marked sensitive, or excluded;
- Raw files are evidence, not truth;
- Extracted text is parsed evidence, not truth;
- Compiled notes are interpretation, not truth;
- Claims are evidence-backed and confidence-bounded, not truth by default;
- Unknown means unknown.

## Forbidden Implementation Claims

The package must not claim:

- a real SQLite database exists;
- ingestion has started;
- old business files were scanned;
- sensitive content is safe for external model use;
- generated summaries are truth;
- app/backend/runtime implementation has started;
- provider/model calls, Gmail/Telegram actions, Hermes runtime expansion, service control, approval mutation, vault access, log inspection, LegalPrivate inspection, or secrets handling are authorized.

## Acceptance Before 03_BACKEND_AND_DATA_MODEL

Before this lane moves to `03_BACKEND_AND_DATA_MODEL`, the operator should decide:

- which synthetic fixtures become JSON contract fixtures;
- whether SQLite schema work starts as SQL DDL, JSON schema, or Markdown table contracts;
- how Mac desktop app planning will display blocked/unknown/sensitive records;
- how conversation packets can be sanitized without becoming hidden provider/model calls;
- where operator promotions live in the broader Operator Harness authority model.
