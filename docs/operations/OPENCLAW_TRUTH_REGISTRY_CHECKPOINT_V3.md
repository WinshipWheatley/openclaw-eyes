# OpenClaw Truth Registry Checkpoint V3

**Date:** 2026-05-12
**Commit Hash:** 71b163a
**Status:** Stable (Truth-aware Answer Harness V0)

## Overview
Checkpoint V3 upgrades the deterministic answer harness to be truth-aware. Every successful answer now includes provenance-linked truth metadata and a top-level summary of the truth posture of the retrieved facts, providing operators with immediate context on the reliability and verification status of the information provided.

## Changes Since V2
- **Truth-aware Payloads:** Answer payloads now include `truth_source_id`, `truth_status`, `verification_required`, and `verification_evidence_id` for every provenance item.
- **Payload Summary:** Added `truth_summary` (truth postures, verification counts, etc.) to the `SUCCESS` payload.
- **Heading Mappings:** Deterministic intent-to-heading mappings have been repaired to align with the current canonical documentation structure.

## Current Truth Chain
`SOURCE_REGISTRY` -> `truth_registry_entries` -> `canonical_facts` -> `truth_report` -> `truth-aware answer harness`

## Current Boundaries
- Answers are deterministic and generated from canonical facts.
- Answers cite provenance and associated truth posture.
- `truth_status` describes verification posture, not runtime authority.
- `doctrine_reference` is not runtime_verified.
- No automatic truth upgrade, LLM, or semantic search usage.

## What is NOT Built
- Natural-language broad Q&A (e.g., via LLMs).
- Agent/Telegram integration.
- Verification evidence upgrade CLI.
- Markdown intake candidates.
- Mac/PC mirror comparison and synchronization strategy.
- External drive strategy.

## Next Safe Lanes
1. Verification Evidence Attach CLI v0.
2. Markdown Intake Candidates v0.
3. Truth-aware operator status integration.
