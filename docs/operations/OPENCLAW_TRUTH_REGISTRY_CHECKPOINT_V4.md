# OpenClaw Truth Registry Checkpoint V4

**Date:** 2026-05-12
**Commit Hash:** 9975c0f
**Status:** Stable (Verification Evidence Attach CLI V0)

## Overview
Checkpoint V4 adds the Verification Evidence Attach CLI, providing a governed path for operators to attach formal verification evidence (test proofs, runtime receipts, etc.) to registry entries and optionally trigger rule-governed truth status upgrades.

## Changes Since V3
- **Verification Evidence Attach CLI:** Added `scripts/attach_verification_evidence.py`.
- **Governed Upgrades:** Truth status upgrades are now restricted by valid evidence types (e.g., `test_verified` requires `test_proof`).
- **Separation of Concerns:** Evidence attachment updates the Truth Registry but does not directly mutate `canonical_facts` (reserved for future sync cycles).

## Current Truth Chain
`SOURCE_REGISTRY` -> `truth_registry_entries` -> `verification_evidence` -> `canonical_facts` -> `truth-aware answer harness`

## Current Boundaries
- Evidence upgrades are explicit and governed by strict type mapping.
- No auto-upgrade from prose.
- `runtime_verified` requires `runtime_receipt` evidence.
- `test_verified` requires `test_proof` evidence.
- `canonical_facts` require a separate resync/re-ingest cycle to inherit updated truth status.

## What is NOT Built
- Canonical fact truth resync.
- Automatic evidence detection.
- Agent/Telegram integration.
- Markdown intake candidates.
- Mac/PC mirror comparison and synchronization strategy.

## Next Safe Lane
Canonical Fact Truth Resync v0
