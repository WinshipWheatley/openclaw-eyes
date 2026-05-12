# OPENCLAW Knowledge Ingestion Checkpoint V3

**Date:** Monday, May 11, 2026
**Commit Hash:** `97413ee`
**Status:** Knowledge Source Registry V0 Complete

## What changed in Registry V0
- Transitioned from hardcoded allowlist to `SOURCE_REGISTRY` metadata mapping in `ingest_canonical_docs.py`.
- Metadata includes `doc_category`, `sensitivity_class`, `allowed_actors`, `temporal_or_doctrine`, and `description` for each allowed source.
- Ingestion pipeline now applies registry-defined metadata (`sensitivity_class`, `allowed_actors`) directly to canonical facts.

## Allowed Sources
1. `docs/operations/OPENCLAW_RECEIPT_SPINE_CHECKPOINT_V9.md`
2. `docs/operations/OPENCLAW_KNOWLEDGE_INGESTION_CHECKPOINT_V2.md`
3. `docs/operations/OPENCLAW_PACKET_TO_RECEIPT_MAPPING_V0.md`

## Metadata Boundary
- Registry metadata is strictly defined in code to govern ingestion inputs.
- Metadata application is verified via automated tests.

## Schema Boundary
- Note: `doc_category`, `temporal_or_doctrine`, and `description` are currently registry metadata only and are not yet reflected in the SQLite ledger schema.

## What is not built
- Broad Markdown ingestion
- Machine contract expansion
- Producer docs expansion
- Drive/local file system inventory
- Embeddings / vector search
- Telegram command bridge / agent wiring
- Hardware/DAW control wiring

## Next Safe Lanes
1. Add machine contract docs to registry allowlist.
2. Consider schema extension for source metadata columns.
3. Establish source inventory/read-model before broad hard-drive indexing.
