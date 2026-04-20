# Harness Index

OpenClaw uses specialized Python harnesses for high-fidelity staging and replaying of complex, time-sensitive, or external-dependent flows.

## Core Pattern
All harnesses share a common invocation pattern:
- **`--fixture <path>`**: Replay logic against a specific input bundle.
- **`--staging-root <path>`**: Redirect all file I/O to an isolated directory (defaults to `staging/<harness_name>/`).
- **`--reference-time <str>`**: Mock the clock for deterministic testing of time-aware logic.

## Available Harnesses

### 1. Morning Briefing Harness
- **Script**: `morning_brief_harness.py`
- **Purpose**: Validates the end-to-end morning briefing pipeline (Guardian -> Chief -> Cassandra).
- **Unique Flags**:
    - `--capture-fixture <name>`: Create a new fixture bundle from live repo state.
    - `--recorded-from <path>`: Reuse stage outputs from a previous run.

### 2. Chief EOD Harness
- **Script**: `chief_eod_harness.py`
- **Purpose**: Validates the end-of-day review context and synthesis.
- **Unique Flags**:
    - `--capture-fixture <name>`: Capture live EOD state for regression testing.

### 3. Guardian Schema Harness
- **Script**: `guardian_schema_harness.py`
- **Purpose**: Validates the Guardian approval input/output schema without requiring network or Telegram connectivity.
- **Usage**: Typically used for testing new approval types or parser corrections.

## Staging & Isolation
Harnesses are designed to be "safe" to run on any machine. They do not send real Telegram messages or emails.
- **Local Playback**: TTS outputs may be rendered to WAV files in the staging root but are not fanned out to hardware.
- **Vault Context**: Harnesses typically read deterministic excerpts from the vault but write results only to staging.
