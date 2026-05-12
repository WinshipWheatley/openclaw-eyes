# OPENCLAW Knowledge Ingestion Checkpoint V4

**Date:** Monday, May 11, 2026
**Commit Hash:** `d85656a`
**Status:** Machine Contract Registry Expansion Complete

## What changed
- Added four core Machine Contract documents to the `SOURCE_REGISTRY`.
- Registry now governs explicit metadata (sensitivity, actors) for these specific files.
- Ingestion pipeline now automatically applies registry-derived metadata to all machine contract facts.

## Current Allowed Sources
1. `docs/operations/OPENCLAW_RECEIPT_SPINE_CHECKPOINT_V9.md`
2. `docs/operations/OPENCLAW_KNOWLEDGE_INGESTION_CHECKPOINT_V2.md`
3. `docs/operations/OPENCLAW_PACKET_TO_RECEIPT_MAPPING_V0.md`
4. `docs/operations/CASSANDRA_MACHINE_CONTRACT.md`
5. `docs/operations/CHIEF_MACHINE_CONTRACT.md`
6. `docs/operations/GUARDIAN_MACHINE_CONTRACT.md`
7. `docs/operations/HERMES_MACHINE_CONTRACT.md`

## Boundary
- Explicit allowlist only (no recursive ingestion or directory-level scanning).
- No globbing, wildcards, or folder-level automation.
- No embeddings, vector search, or machine learning components.
- No runtime agent or Telegram wiring.
- No automated hard-drive indexing.

## What is not built
- Producer/Niles documentation expansion.
- Source metadata database schema extension (metadata remains in source code registry).
- Broad repository markdown ingestion.
- Hard-drive/filesystem inventory automation.
- Music/studio hardware control wiring.

## Next Safe Lanes
1. Add Producer/Niles docs to registry.
2. Consider schema extension for source metadata columns.
3. Establish repo markdown category expansion plan.
4. Draft hard-drive inventory plan.
