# OpenClaw Truth Registry Checkpoint V1

**Date:** 2026-05-12
**Commit Hash:** a35b65b
**Status:** Stable (Canonical Facts Truth-Status Inheritance V0)

## Overview
Checkpoint V1 implements truth-status inheritance for individual `canonical_facts` by linking them to the governed entries in the Truth Registry. Every ingested fact now carries its own trust posture, enabling downstream consumers to assess fact provenance and verification requirements independently.

## Changes Since V0
- **Canonical Facts Metadata:** Added `truth_source_id`, `truth_status`, `verification_required`, and `verification_evidence_id` to the `canonical_facts` schema (total 15 columns).
- **Inheritance Logic:** `scripts/ingest_canonical_docs.py` now maps ingested facts to associated `truth_registry_entries`.
- **Conservative Fallback:** Unregistered sources automatically default to `truth_status='declared'` and `verification_required=1`.
- **Retrieval:** Canonical facts can be queried with their associated trust posture.

## Current Truth Chain
`SOURCE_REGISTRY` -> `truth_registry_entries` -> `canonical_facts`

## Current Boundaries
- Approved-for-ingestion does not imply verified true.
- `doctrine_reference` is not runtime_verified.
- `runtime_verified` / `test_verified` status still require documented evidence.
- No automatic truth upgrades.
- No mirror auto-promotion.

## What is NOT Built
- Canonical fact truth report.
- Verification evidence upgrade CLI.
- Markdown intake candidates.
- Mac/PC mirror comparison and synchronization strategy.
- External drive strategy.
- Agent/Telegram truth-aware answering.

## Next Safe Lane
Canonical Fact Truth Report v0
