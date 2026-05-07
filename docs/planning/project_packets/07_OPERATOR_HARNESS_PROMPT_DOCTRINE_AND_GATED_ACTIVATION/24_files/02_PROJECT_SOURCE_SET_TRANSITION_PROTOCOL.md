# Project Source-Set Transition Protocol

Status type: OPERATING_DOCTRINE / RENEWAL_PROTOCOL

## Purpose

Define how Packet 06 hands authority to Packet 07 and how Packet 07 should later renew without losing source provenance, final handoff history, or archive pairing.

## Source Inputs

- Packet 06 final `00_ACTIVE_HANDOFF.md`
- Packet 06 `02_PROJECT_SOURCE_SET_TRANSITION_PROTOCOL.md`
- Packet 06 `24_VISIBLE_ROAD_AND_BIG_STRIDES_DOCTRINE.md`
- `docs/planning/project_packets/README.md`
- `docs/planning/project_packets_archive/06_OPERATOR_HARNESS_ACTOR_EFFICIENCY_AND_SENSITIVE_WORKFLOWS_SNAPSHOT/`
- Packet 05 active packet `README.md`
- `.gitignore`

## What It Governs

- Packet 06 final handoff and rails archived as a paired snapshot.
- Packet 07 handoff outside `24_files/`.
- Exactly 24 durable Packet 07 rail files.
- Project packet index as active-packet pointer.
- Future renewal requiring a blueprint before mutation.

## Repo Implementation Pointers

- `docs/planning/project_packets/README.md`
- `docs/planning/project_packets_archive/`
- `.gitignore`

## Valid Future Lane Moves

- Refresh the active handoff after substantial bounded moves.
- Add validation receipts and detours to the handoff.
- Run a renewal audit when Packet 07 rails are exhausted.
- Draft a Packet 08 blueprint before any Packet 08 file generation.

## Forbidden Drift

- Do not edit active Packet 07 rails as routine handoff updates.
- Do not archive rails without the final handoff.
- Do not bury the handoff inside `24_files/`.
- Do not let a mirror, stale packet, chat memory, or receipt become source-set authority.
- Do not generate the next packet from vibes.

## Review Boundary

Review this protocol when the handoff becomes mostly transition notes, when new work repeatedly needs sources outside Packet 07, or when exact context setup takes more effort than lane movement.

## Why It Should Last 10-20 Moves

Transition mechanics should remain boring. This rail preserves the Packet 05 to Packet 06 pattern while making Packet 07 renewal explicit.
