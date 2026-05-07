# Performance Director Show Map Truth

Status type: BUILT_TRUTH

## Purpose

Preserve the Performance Director / Show Map substrate as built truth while keeping live performance control surfaces forbidden and outside Packet 07 activation.

## Source Inputs

- Packet 06 `13_PERFORMANCE_DIRECTOR_SHOW_MAP_TRUTH.md`
- Packet 06 `05_OPERATOR_NORTH_STAR_MACHINE_CONTRACT.md`
- Packet 06 final `00_ACTIVE_HANDOFF.md`

## What It Governs

- Performance sessions, setlists, cues, action receipts, manual override events, and highlight markers as inert planning/map substrate.
- Cues as map markers, not live control.
- Receipts as evidence, not authority.
- Manual override as first-class state.

## Repo Implementation Pointers

- `backend_storage_intelligence.py`
- `backend_sqlite_schema.py`
- `backend_sqlite_repository.py`
- `tests/test_backend_performance_repository.py`
- `tests/test_backend_performance_intelligence.py`

## Valid Future Lane Moves

- Operator Harness read-model planning for performance readiness.
- Creative asset extraction planning.
- Documentation lanes for performance artifacts.

## Forbidden Drift

- No live MIDI, audio, chord, lyric, camera, OBS, X32, Dante, DAW, looper, Home Assistant, Hue, Matter, MQTT, TTS, adaptive inference, or performance runner surfaces.
- No live show control through gated activation.

## Review Boundary

Review before any prompt mentions live shows, stage control, cue engines, performance runtime, or creative performance automation.

## Why It Should Last 10-20 Moves

This rail protects a built creative substrate while preventing inert maps from turning into live control.
