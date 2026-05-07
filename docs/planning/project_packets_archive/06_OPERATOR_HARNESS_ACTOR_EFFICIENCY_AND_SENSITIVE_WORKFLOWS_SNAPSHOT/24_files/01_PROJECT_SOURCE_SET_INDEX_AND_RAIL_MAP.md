# Project Source-Set Index And Rail Map

Status type: OPERATING_DOCTRINE / RENEWAL_PROTOCOL

## Purpose

This is the roadmap authority for Packet 06. It explains what the 24 rails are, how they relate to each other, and which future lane moves are valid while this packet is active.

The handoff is the train log. This file is the track map.

## Source Inputs

- `docs/planning/project_packets/05_BACKEND_SQLITE_SCHEMA_ORCHESTRATION/00_ACTIVE_HANDOFF.md`
- `docs/planning/project_packets/05_BACKEND_SQLITE_SCHEMA_ORCHESTRATION/README.md`
- Packet 05 `24_files/`
- `docs/planning/chase_money/INVOICE_RECONCILIATION_BREADCRUMB_LIVE_ARTS_20260507.md`
- `docs/planning/sensitive_roots/SENSITIVE_ROOT_REGISTRY_BREADCRUMB_20260507.md`
- `docs/planning/agent_efficiency/CLI_RECEIPT_LAYER_LOW_CONTEXT_BREADCRUMB_20260507.md`
- `AGENTS.md`
- `OPENCLAW_RUNTIME.md`
- `USER.md`
- `CORE_ARCHITECTURE_PRINCIPLES.md`
- `.gitignore`

## What It Governs

- Packet 06 source-set membership.
- The distinction between durable rails and the active handoff train.
- Which files are built truth, doctrine, future lanes, boundary guards, or renewal protocol.
- The candidate continuation list used by the active handoff.
- The rule that repo files prove details while 24 files guide decisions.

## Rail Map

| File | Status type | Role |
| --- | --- | --- |
| 01 | OPERATING_DOCTRINE / RENEWAL_PROTOCOL | Packet map and candidate continuations. |
| 02 | OPERATING_DOCTRINE / RENEWAL_PROTOCOL | How Packet 05 becomes Packet 06 and later Packet 07. |
| 03 | OPERATING_DOCTRINE | Architecture guardrails. |
| 04 | OPERATING_DOCTRINE | Command Atlas system/lane map. |
| 05 | OPERATING_DOCTRINE | Operator North Star and mastery-to-assets doctrine. |
| 06 | OPERATING_DOCTRINE | Project chat operator experience. |
| 07 | OPERATING_DOCTRINE / BOUNDARY_GUARD | Validation and test boundaries. |
| 08 | BUILT_TRUTH | Backend data contract and schema substrate. |
| 09 | BUILT_TRUTH | Repository and runtime substrate. |
| 10 | BUILT_TRUTH | Context substrate and traversal. |
| 11 | BUILT_TRUTH | Actor registry and trust bridge. |
| 12 | BUILT_TRUTH | Storage intelligence and authorization. |
| 13 | BUILT_TRUTH | Performance Director / Show Map substrate. |
| 14 | FUTURE_LANE | CLI receipts and low-context interface. |
| 15 | FUTURE_LANE / BOUNDARY_GUARD | Sensitive root registry and quarantine policy. |
| 16 | FUTURE_LANE | Invoice Artifact v0 / Billing Bridge. |
| 17 | FUTURE_LANE / BOUNDARY_GUARD | Actor sidecar and context export hardening. |
| 18 | FUTURE_LANE | Operator Harness read-model plan. |
| 19 | FUTURE_LANE / BOUNDARY_GUARD | Legal context export policy plan. |
| 20 | FUTURE_LANE | Runtime integration and recovery architecture. |
| 21 | FUTURE_LANE | MCP shared memory architecture review. |
| 22 | FUTURE_LANE / BOUNDARY_GUARD | Runtime authority and legacy gating. |
| 23 | BOUNDARY_GUARD | Broad source-set exclusion guard. |
| 24 | RENEWAL_PROTOCOL / BOUNDARY_GUARD | Visible road and Packet 07 renewal doctrine. |

## Candidate Continuations

1. CLI Receipt Layer / Low-Context Interface v0 planning.
2. Sensitive Root Registry / Quarantine Intake static contract planning.
3. Invoice Artifact v0 / Billing Bridge draft-only reconciliation planning.
4. Actor Sidecar and Context Export hardening plan.
5. Operator Harness read-model assembly plan.
6. Legal Context Export policy plan.
7. Runtime Integration and Recovery architecture review.
8. MCP Shared Memory architecture review.
9. Runtime Authority and Legacy Gating review.
10. Broad Source-Set Exclusion Guard audit.

## Repo Implementation Pointers

- `backend_data_contract.py`
- `backend_sqlite_schema.py`
- `backend_sqlite_runtime.py`
- `backend_sqlite_repository.py`
- `backend_knowledge_packet.py`
- `backend_storage_intelligence.py`
- `tests/test_backend_data_contract.py`
- `tests/test_backend_sqlite_schema.py`
- `tests/test_backend_sqlite_runtime.py`
- `tests/test_backend_sqlite_repository.py`
- `tests/test_backend_knowledge_packet.py`
- `tests/test_backend_storage_intelligence.py`
- `tests/test_backend_performance_repository.py`
- `tests/test_backend_performance_intelligence.py`
- `tests/test_backend_agent_context.py`

Pointers are proof locations, not preload requirements.

## Valid Future Lane Moves

- Choose one candidate continuation and read its governing file.
- Add a breadcrumb to the active handoff after a bounded move.
- Add validation receipts to the active handoff when checks are run.
- Prepare a Packet 07 blueprint only after the current rails become exhausted.

## Forbidden Drift

- Do not treat this packet as 24 tasks to build from scratch.
- Do not make the active handoff the roadmap.
- Do not use old Packet 05 rails as current authority except through the archive/source-input role.
- Do not turn future lanes into implementation authority without a later exact prompt.

## Review Boundary

Review this file when candidate lanes feel stale, a new breadcrumb appears, or Packet 06 is nearing renewal.

## Why It Should Last 10-20 Moves

This file is high-level enough to survive multiple implementation or planning strides, but concrete enough to keep each future prompt on the correct track.
