# OpenClaw Truth Registry Checkpoint V0

**Date:** 2026-05-12
**Commit Hash:** 9156a7b
**Status:** Stable (Foundational Registry Layer)

## Overview
Checkpoint V0 establishes the Canonical Truth Registry, a new governed substrate for tracking source truth independently from file inventory and fact ingestion. This milestone implements the schema, ledger helpers, backfill utilities, and a read-only query interface.

## System Distinctions
- **File Inventory:** Tracks physical file metadata (size, path, modification time).
- **Canonical Facts:** Stores decomposed, ingestable facts extracted from source files.
- **Truth Registry:** Governs the truth-status of the files/facts themselves (e.g., doctrine status, commit boundaries, verification evidence).
- **Verification Evidence:** Links registry entries to specific proofs (test logs, runtime receipts).

## Truth Model
The registry employs conservative statuses to ensure governed growth:
- **`declared`**: Initial registry entry without additional verification.
- **`doctrine_reference`**: Intended operational/machine-readable doctrine.
- **`historical_checkpoint`**: Bounded to a specific commit.
- **`test_verified` / `runtime_verified`**: Requires documented `verification_evidence_id` linked to the source.

## Current Backfill
- **Total entries backfilled:** 9 (from `SOURCE_REGISTRY`).

## Current Boundaries
- No file content reads or hashing.
- No scanner behavior changes.
- No ingestion/promotion logic automation.
- No external drive awareness.
- No agent/Telegram/runtime wiring.

## Next Safe Lanes
1. **Fact Inheritance:** Enable truth-status inheritance for individual canonical facts.
2. **Evidence Workflow:** Implement verification evidence attach/query CLI workflow.
3. **Markdown Candidates:** Develop candidates for new source intake.
4. **Mirror Handling:** Design the Mac/PC mirror comparison and synchronization plan.
