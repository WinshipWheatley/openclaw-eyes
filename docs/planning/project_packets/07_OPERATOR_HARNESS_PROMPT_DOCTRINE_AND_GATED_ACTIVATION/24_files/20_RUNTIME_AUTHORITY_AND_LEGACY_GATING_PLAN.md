# Runtime Authority And Legacy Gating Plan

Status type: FUTURE_LANE / BOUNDARY_GUARD

## Purpose

Define future static review and hardening for legacy runtime surfaces, launch scripts, service ownership, and authority gates without launching services or mutating runtime state.

## Source Inputs

- Packet 06 `22_RUNTIME_AUTHORITY_AND_LEGACY_GATING.md`
- Packet 06 final `00_ACTIVE_HANDOFF.md`
- Packet 06 final consolidation boundary notes
- `OPENCLAW_RUNTIME.md`
- `.gitignore`

## What It Governs

- Legacy launch/process surfaces as frozen until reviewed.
- Runtime authority classes.
- Dry-run/refusal-first posture.
- Separation of approval, execution, success, and evidence.
- Avoiding hidden execution through old scripts or status cards.

## Repo Implementation Pointers

- `tests/test_service_inventory_audit.py`
- `tests/test_legacy_launch_script_safety.py`
- `tests/test_chief_listener_lifecycle.py`
- `chief_listener.py`

Pointers are for future exact-file static review only. They are not permission to run services.

## Valid Future Lane Moves

- Metadata-only legacy gating review from tracked docs/tests.
- Static tests for launch script safety.
- Operator Harness Engine Room read-only status planning.
- Activation gate checklist drafts.

## Forbidden Drift

- No service starts, restarts, enables, disables, scans, or runtime mutation.
- No editing launchers, timers, systemd units, SSH settings, credentials, env files, or runtime state without exact authority.
- No process/service crawling.
- No hidden repair from visibility.

## Review Boundary

Review before touching launch scripts, runtime controls, service templates, process status, queue state, or legacy automation.

## Why It Should Last 10-20 Moves

Legacy/runtime mistakes are costly. Packet 07 should keep runtime authority visible but gated.
