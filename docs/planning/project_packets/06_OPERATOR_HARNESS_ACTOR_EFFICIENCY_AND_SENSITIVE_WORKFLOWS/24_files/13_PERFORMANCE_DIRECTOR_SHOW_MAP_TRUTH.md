# Performance Director Show Map Truth

Status type: BUILT_TRUTH

## Purpose

Preserve the Performance Director / Show Map substrate as built truth while keeping all live performance control surfaces forbidden.

## Source Inputs

- Packet 05 `00_ACTIVE_HANDOFF.md`
- Packet 05 active handoff built-state ledger
- Packet 05 `05_operator_north_star_machine_contract_20260505.md`
- Packet 05 `07_04_CONTEXT_DEVELOPMENT_LIFECYCLE_AND_CONTEXT_FILTER_DOCTRINE.md`

## What It Governs

- Performance sessions, setlists, cues, action receipts, manual override events, and highlight markers as inert planning/map substrate.
- Cues as map markers, not live control.
- Receipts as evidence/logs, not authority.
- Manual override as first-class state.

## Repo Implementation Pointers

- `backend_storage_intelligence.py`
- `backend_sqlite_schema.py`
- `backend_sqlite_repository.py`
- `tests/test_backend_performance_repository.py`
- `tests/test_backend_performance_intelligence.py`

## Valid Future Lane Moves

- Operator Harness read-model planning that displays performance readiness without live control.
- Creative/operator asset extraction planning.
- Future performance artifact documentation lanes.

## Forbidden Drift

- No live MIDI listeners.
- No audio/chord/lyric analysis.
- No camera switching.
- No OBS WebSocket control.
- No X32 OSC control.
- No Dante routing.
- No DAW/looper integration.
- No Home Assistant/Hue/Matter/MQTT actions.
- No TTS headphone cue engines.
- No live performance runners.
- No adaptive inference engines.

## Review Boundary

Review before any future prompt mentions live shows, stage control, cue engines, performance runtime, or creative performance automation.

## Why It Should Last 10-20 Moves

This rail protects a real built substrate while preventing one of the riskiest drift paths: inert show maps turning into live control.
