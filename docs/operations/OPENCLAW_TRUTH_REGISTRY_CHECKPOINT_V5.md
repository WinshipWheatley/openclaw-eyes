# OpenClaw Truth Registry Checkpoint V5

**Date:** 2026-05-12
**Commit Hash:** a0706dd
**Status:** Stable (Canonical Fact Truth Resync CLI V0)

## Overview
Checkpoint V5 adds the Canonical Fact Truth Resync CLI, enabling the deliberate propagation of verification-upgraded truth postures from the Truth Registry to existing `canonical_facts` records. This ensures that historical facts correctly reflect the latest governed truth status without requiring document re-ingestion or content re-reading.

## Changes Since V4
- **Canonical Fact Truth Resync CLI:** Added `scripts/resync_canonical_fact_truth.py` for propagating truth metadata.
- **Governed Propagation:** Existing facts now correctly reflect registry status upgrades, keeping the fact-level and registry-level trust postures synchronized.
- **Bounded Safety:** The resync operation is strictly bounded to metadata updates (`truth_status`, `verification_required`, `verification_evidence_id`) and preserves the integrity of all other fact fields (content, source, provenance).

## Current Truth Chain
`SOURCE_REGISTRY` -> `truth_registry_entries` -> `verification_evidence` -> `canonical_facts` -> `resync` -> `truth-aware answer harness`

## Current Boundaries
- Resync must be explicitly invoked by an operator.
- Fact content is immutable during the resync process.
- No Markdown reads, hashing, or file scanning performed.
- No automatic truth upgrades; evidence-based changes are propagated only on resync.

## What is NOT Built
- Automatic resync scheduling.
- Agent/Telegram integration.
- Markdown intake candidates.
- Mac/PC mirror comparison and synchronization strategy.
- Natural-language broad Q&A (e.g., via LLMs).

## Next Safe Lanes
1. Truth-aware Operator Status Integration v0.
2. Markdown Intake Candidates v0.
3. Mac/PC Mirror Handling Plan.
