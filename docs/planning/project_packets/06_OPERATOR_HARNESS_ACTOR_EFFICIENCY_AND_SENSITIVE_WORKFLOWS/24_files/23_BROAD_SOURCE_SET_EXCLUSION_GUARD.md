# Broad Source-Set Exclusion Guard

Status type: BOUNDARY_GUARD

## Purpose

Prevent Packet 06 and future packets from laundering private roots, runtime residue, credentials, logs, provider prompts, MCP context, or broad filesystem facts into source-set authority.

## Source Inputs

- Packet 05 `15_30_BACKEND_SOURCE_SET_BRIDGE_AND_EXCLUSION_PLAN.md`
- Packet 05 `07_04_CONTEXT_DEVELOPMENT_LIFECYCLE_AND_CONTEXT_FILTER_DOCTRINE.md`
- Packet 05 `02_24_PROJECT_SOURCE_SET_TRANSITION_PROTOCOL.md`
- Sensitive Root Registry breadcrumb
- CLI Receipt Layer breadcrumb
- `.gitignore`
- `AGENTS.md`
- `OPENCLAW_RUNTIME.md`

## What It Governs

- Source-set inclusion and exclusion.
- Private-root and sensitive-root non-browsing.
- Credential and secret avoidance.
- No broad crawling.
- Repo files as proof pointers, not wholesale preload.
- `.gitignore` allowlist discipline.

## Repo Implementation Pointers

- `.gitignore`
- `docs/planning/project_packets/`
- `docs/planning/project_packets_archive/`

## Valid Future Lane Moves

- Add narrow allowlist patterns for approved docs/source-set files.
- Produce source-set status receipts that list exact included files.
- Audit candidate packet sources against explicit inputs.
- Record withheld surfaces in handoffs and manifests.

## Forbidden Drift

- No private roots.
- No secrets, credentials, tokens, `.chief.env`, `.google-secrets/`, env files, legal/client/private folders, or sensitive folders.
- No broad filesystem crawling.
- No source-set generation from hidden chat memory.
- No raw runtime/log/state/config content.
- No model/provider prompt or output as source truth.

## Review Boundary

Review before any source-set generation, packet renewal, context package, CLI receipt, or low-context prompt pack.

## Why It Should Last 10-20 Moves

Every future lane needs context. This guard keeps context useful without becoming a leak or authority laundering surface.
