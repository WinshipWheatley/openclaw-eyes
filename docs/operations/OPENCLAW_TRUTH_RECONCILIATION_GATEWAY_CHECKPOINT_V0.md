# OPENCLAW TRUTH RECONCILIATION GATEWAY CHECKPOINT V0

- **Date:** 2026-05-12
- **Commit:** 3a54ed6
- **Status:** Stable — answer harness is truth-gated through reconciliation gateway

## Overview
The Truth Reconciliation Gateway v0 implements a deterministic, read-only safety gate that ensures no LLM/model receives canonical facts that are stale or unverified against their source documents.

## What was built
- **`scripts/truth_reconciliation_gateway.py`**: Core gateway implementation.
- **`tests/test_truth_reconciliation_gateway.py`**: Comprehensive test suite for integrity checks and packet generation.
- **`check_fact_source_integrity()`**: JIT integrity checker that compares disk hashes to recorded registry hashes.
- **`build_llm_truth_packet()`**: State-machine driven packet generator that withholds `fact_text` until integrity is proven.
- **`answer_harness.py` integration**: The operator question answer harness now uses `MODEL_ALLOWED` packets exclusively.

## Core Invariant
- **No model answer from pre-reconciliation data.**
- **No stale candidate packet may cross the model boundary.**
- **LLM/model input must be produced only from checked `MODEL_ALLOWED` truth packets.**

## Execution Chain
`question` -> `answer_harness intent match` -> `candidate facts` -> `truth_reconciliation_gateway` -> `source hash JIT check` -> `MODEL_ALLOWED/MODEL_BLOCKED` -> `answer payload`

## State Machine
- `CANDIDATE_SURFACED`: Facts identified in SQLite.
- `CHECK_RUNNING`: JIT source integrity check initiated.
- `NO_DIFF_FOUND`: Disk hash matches registry hash; integrity confirmed.
- `PACKET_READY`: Verified facts packaged with labels and provenance.
- `MODEL_ALLOWED`: Terminal success state; packet ready for model exposure.
- `CHECK_FAILED`: System error or missing metadata during check.
- `MODEL_BLOCKED`: Terminal failure state; integrity check failed (e.g., hash mismatch).

## Integrity Constraints
The gateway validates:
1. `canonical_facts` row existence.
2. `canonical_facts.truth_source_id` aligns with `truth_registry_entries.source_id`.
3. `canonical_facts.source_file` aligns with `truth_registry_entries.observed_path`.
4. `source_file` is present in `SOURCE_REGISTRY`.
5. `truth_registry_entries.hash_status == 'current'`.
6. Disk `sha256(source_file)` equals `truth_registry_entries.source_content_hash`.
7. `fact_text` is strictly withheld until all checks pass.

## Packet Composition
Successful answers now include:
- **Verified `fact_text`**: Surfaced only after `MODEL_ALLOWED`.
- **Labels**: `[REPO-SOURCE]`, `[HASH-CURRENT]`, `[DOCTRINE_REFERENCE]`, `[VERIFY_REQUIRED]`.
- **Provenance**: `source_file`, `source_commit`, `content_hash`, `truth_source_id`, `truth_status`, `verification_required`, `verification_evidence_id`.
- **Metadata**: Transition history for auditability.
- **Answer Boundary**: Strict instructions for the model to use only the provided facts.
- **Authority Flag**: `runtime_authority=false` (Default for v0).

## Current Boundaries (v0)
- **Read-Only**: No SQLite mutations or auto-reconciliation writes.
- **Blocking-Only**: Detects stale states and blocks model exposure; does not fix them.
- **Doctrine Focus**: Primarily manages `doctrine_reference` and `historical_checkpoint` facts.
- **No Agent Runtime Wiring**: Cassandra, Chief, and Niles are not yet consuming these gated packets.

## What is Not Built
- Auto-reconciliation writes on diff detection.
- Re-query/re-check loop after writes.
- Multi-fact grouping strategies beyond basic harness behavior.
- Advanced truth semantics (claim_type, action_authority, etc.).
- Runtime receipt/test evidence automated upgrades.

## Next Lanes
1. **Truth Reconciliation Gateway v1**: Implement controlled auto-reconciliation writes + re-query/re-check loop.
2. **Truth Semantics / Claim Ontology v0**: Define granular claim types and authority levels.
3. **Multi-Fact Grouping**: Hardening strategies for large multi-document truth packets.
4. **Agent Integration**: Plan for Cassandra/Chief truth-packet consumption.
5. **Markdown Intake Candidates v0**: Broadening the intake funnel with gateway protection.
