# Canonical Docs Knowledge Ingestion v0 Checkpoint

## Status
- **Current Commit:** `251dbe4`
- **Build Status:** Deterministic ingestion and read-only retrieval infrastructure complete.

## Built Capabilities
1. **Canonical Ledger:** SQLite-based append-only fact storage.
2. **Markdown Extractor:** Deterministic `#` and `##` section splitter with SHA-256 integrity.
3. **Ingestion Harness:** Single-file ingestion restricted to `docs/operations/OPENCLAW_RECEIPT_SPINE_CHECKPOINT_V9.md`.
4. **Retrieval Helpers:** Read-only retrieval functions via SQLite URI `mode=ro`.

## Not Built
- No query CLI.
- No agent context integration.
- No deterministic "where are we?" answer harness.
- No expanded source allowlist.
- No embeddings/vector search.
- No runtime wiring.
- No broad repository ingestion.

## Source Restrictions
- **Allowed Source:** `docs/operations/OPENCLAW_RECEIPT_SPINE_CHECKPOINT_V9.md`
- **Excluded Sources:** Secrets, `.env`, `.pii_vault.enc`, Gmail, PII, outreach, legal-private data, DAW, runtime, sidecars, generated files, private user data.

## Truth Boundary
Canonical facts are source-grounded reference facts. They are NOT receipts and do NOT carry runtime authority.

## Next Safe Chunks
5. **Query CLI / Inspect Facts:** Expose retrieval via CLI.
6. **"Where are we?" Answer Harness:** Deterministic fact-based synthesis.
7. **Context Packet Integration:** Wiring knowledge into the agent loop.
8. **Expanded Source Allowlist:** Gradual onboarding of additional documentation.

## Proof Commands
```bash
python3 -m pytest \
  tests/test_canonical_fact_retrieval.py \
  tests/test_canonical_docs_ingestion.py \
  tests/test_fact_extractor.py \
  tests/test_canonical_fact_ledger.py -q
```
