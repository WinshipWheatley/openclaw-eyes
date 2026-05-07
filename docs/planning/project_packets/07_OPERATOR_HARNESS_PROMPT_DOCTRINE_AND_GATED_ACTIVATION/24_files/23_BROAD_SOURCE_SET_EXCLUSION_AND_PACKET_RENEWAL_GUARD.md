# Broad Source-Set Exclusion And Packet Renewal Guard

Status type: BOUNDARY_GUARD / RENEWAL_PROTOCOL

## Purpose

Prevent Packet 07 and future packets from laundering private roots, runtime residue, credentials, logs, provider prompts, MCP context, path metadata, or broad filesystem facts into source-set authority.

## Source Inputs

- Packet 06 `23_BROAD_SOURCE_SET_EXCLUSION_GUARD.md`
- Packet 06 `02_PROJECT_SOURCE_SET_TRANSITION_PROTOCOL.md`
- Packet 06 final `00_ACTIVE_HANDOFF.md`
- `openclaw_sensitive_policy.py`
- `.gitignore`

## What It Governs

- Source-set inclusion and exclusion.
- Private-root and sensitive-root non-browsing.
- Credential and secret avoidance.
- Exact source inputs for packet renewal.
- `.gitignore` allowlist discipline.
- No path-metadata-as-authority.

## Repo Implementation Pointers

- `.gitignore`
- `docs/planning/project_packets/`
- `docs/planning/project_packets_archive/`
- `scripts/openclaw_receipts.py`
- `openclaw_sensitive_policy.py`

## Valid Future Lane Moves

- Add narrow allowlist patterns for approved packet docs.
- Produce exact source-set receipts.
- Audit renewal inputs against explicit rails.
- Record withheld surfaces in handoffs and rail maps.

## Forbidden Drift

- No private roots.
- No secrets, credentials, tokens, `.chief.env`, `.google-secrets/`, env files, legal/client/private folders, or sensitive folders.
- No broad filesystem crawling.
- No source-set generation from hidden chat memory.
- No raw runtime/log/state/config content.
- No model/provider prompt or output as source truth.

## Review Boundary

Review before source-set generation, packet renewal, context packages, CLI receipts, or low-context prompt packs.

## Why It Should Last 10-20 Moves

Every Packet 07 lane needs context. This rail keeps context useful without leaking or laundering authority.
