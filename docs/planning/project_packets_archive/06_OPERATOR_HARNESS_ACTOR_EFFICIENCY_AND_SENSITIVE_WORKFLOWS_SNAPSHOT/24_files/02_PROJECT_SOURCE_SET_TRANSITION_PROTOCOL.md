# Project Source-Set Transition Protocol

Status type: OPERATING_DOCTRINE / RENEWAL_PROTOCOL

## Purpose

Define how Packet 05 hands authority to Packet 06, and how Packet 06 should later renew into Packet 07 without losing provenance, handoff continuity, or old source-set history.

## Source Inputs

- Packet 05 `02_24_PROJECT_SOURCE_SET_TRANSITION_PROTOCOL.md`
- Packet 05 `00_ACTIVE_HANDOFF.md`
- Packet 05 `README.md`
- Packet 05 `24_files/`
- `docs/planning/project_packets_archive/05_BACKEND_SQLITE_SCHEMA_ORCHESTRATION_SNAPSHOT/`
- `OPENCLAW_RUNTIME.md`
- `.gitignore`

## What It Governs

- Active handoff outside `24_files/`.
- Exactly 24 durable files inside `24_files/`.
- Old handoff plus old rails archived as one paired snapshot.
- New packet authority switching only after the new rails and handoff exist.
- Mac mirror or upload surfaces remaining non-canonical unless explicitly promoted.

## Repo Implementation Pointers

None required. This is docs/source-set doctrine. Use repo status and git log only as verification receipts.

## Valid Future Lane Moves

- Refresh the active handoff after substantial bounded moves.
- Add breadcrumbs as source inputs for a later renewal.
- Generate a Packet 07 blueprint before mutating Packet 06 rails.
- Archive Packet 06 handoff and rails together when Packet 07 is approved.

## Forbidden Drift

- Do not edit active `24_files/` as a routine handoff update.
- Do not bury the handoff inside `24_files/`.
- Do not archive rails without the final handoff.
- Do not let a Mac mirror, chat memory, or stale packet become canonical repo truth.
- Do not generate the next packet from vibes; use explicit source inputs.

## Review Boundary

Review this protocol when the handoff becomes mostly transition notes, when new work repeatedly needs sources outside Packet 06, or when the active chat spends more time re-explaining context than moving lanes.

## Why It Should Last 10-20 Moves

Transition mechanics should be boring and durable. This file avoids process reinvention while leaving the active handoff free to change.
