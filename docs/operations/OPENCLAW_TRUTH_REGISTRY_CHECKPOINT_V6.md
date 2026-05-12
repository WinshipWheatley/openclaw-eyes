# OpenClaw Truth Registry Checkpoint V6

**Date:** 2026-05-12
**Commit Hash:** 218c619
**Status:** Stable — real-ledger controlled SOURCE_REGISTRY ingest complete.

## Overview
Checkpoint V6 marks the transition from conceptual framework to active governance. We have completed the first real-ledger controlled ingestion of the foundational `SOURCE_REGISTRY` documents. This cycle establishes the integrity baseline for canonical content using hash-aware ingestion guards, ensuring that truth postures (like `doctrine_reference`) are anchored to specific content states and protected against stale inheritance if files are modified on disk.

## What Changed Since V5
- **Hash Metadata Schema:** Expanded the truth registry to track `source_content_hash` and `hash_status`.
- **Baseline Hash Tool:** Implemented `scripts/baseline_truth_registry_hashes.py` to establish integrity baselines.
- **Hash Invalidation Tool:** Implemented `scripts/check_truth_registry_hashes.py` to detect content drift and downgrade truth postures automatically.
- **Ingestion Guard:** Refactored `scripts/ingest_canonical_docs.py` to block inheritance of verified statuses if hash integrity is not verified (`current`).
- **Readiness Report:** Added `scripts/truth_ingest_readiness_report.py` to provide a safety gate before real-ledger mutation.
- **Reporting Repair:** Fixed `scripts/generate_canonical_fact_truth_report.py` to correctly handle empty or nascent ledgers.
- **Real-Ledger Execution:** Successfully completed the first controlled ingestion into the live production ledger.

## Real Ledger Result
- **Path:** `.openclaw/business_ops/ledger.sqlite`
- **Registry Coverage:** 9 `SOURCE_REGISTRY` documents registered and hashed.
- **Fact Volume:** 83 total canonical facts ingested.
- **Truth Posture Distribution:**
  - `doctrine_reference`: 71 facts (foundational operating rules).
  - `historical_checkpoint`: 12 facts (state-in-time references).
- **Verification Posture:** `verification_required=True` for all 83 facts (pending evidence attachment).

## Current Truth Chain
`SOURCE_REGISTRY` -> `truth_registry_entries` -> `source_content_hash`/`hash_status` -> `canonical_facts` -> `truth-aware answer_harness`

## Current Boundaries
- **No Broad Ingest:** Markdown ingestion is strictly limited to the defined `SOURCE_REGISTRY`.
- **No Mirror Intake:** Mac/PC mirror intake is not yet active.
- **No Scanning:** No recursive drive or directory scanning for "facts".
- **No Cleanup:** No duplicate cleanup or file deletion authority granted.
- **No LLM Upgrades:** Truth statuses are governed by registry logic, not LLM inference.
- **Evidence Required:** No `runtime_verified` status is granted without explicit, linkable runtime evidence.

## What is Now Possible
- **Deterministic Answers:** Reliable retrieval of canonical facts via the `answer_harness`.
- **Provenance Awareness:** Truth posture and source provenance are surfaced in answer payloads.
- **Integrity Protection:** Hash-aware guards prevent stale verified statuses from being inherited after content changes.
- **Safety Gates:** Controlled re-ingest is governed by explicit readiness checks.

## What is NOT Built
- **Markdown Intake Candidates:** Identification of new candidate docs for the registry.
- **Mac/PC Mirror Handling:** Reconciliation of cross-platform document states.
- **Duplicate Drive Cleanup:** Identification and safe removal of redundant content.
- **Auto-Resync:** Scheduled synchronization between disk, registry, and facts.
- **Broad Semantic Q&A:** Natural-language "chat" across the entire knowledge base.
- **Runtime Integration:** Direct integration into Cassandra or Chief worker loops.

## Do Not Overclaim
- **POSTURE IS NOT VERIFICATION:** `doctrine_reference` indicates a document's role, not its empirical validation in the current runtime environment.
- **CONTEXTUAL BOUNDARIES:** `historical_checkpoint` facts are only valid within their specific temporal or versioned context.
- **PENDING EVIDENCE:** `verification_required=True` means these facts, while canonical, require supporting evidence before they can be used for high-stakes autonomous decision-making.

## Next Safe Lanes
1. **Truth-Aware Operator Status Integration:** Surfacing knowledge-backed status in CLI/UI.
2. **Markdown Intake Candidates v0 Plan:** Strategizing the expansion of the registry.
3. **Duplicate File Discovery and Safe Cleanup Machine Contract:** Defining the safety rules for file consolidation.
4. **Mac/PC Mirror Handling Plan:** Establishing the cross-platform source-of-truth logic.
