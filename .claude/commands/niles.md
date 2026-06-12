# Niles Maintenance Guide

This markdown file is a maintenance guide for Claude Code, Codex, and Fable
sessions. It is not runtime code, not a policy source, and not an authority
grant.

Runtime truth lives in Python, generated read models, receipts, and any
operator-approved lane artifacts. Use this guide to orient before inspecting the
real files.

## Current Role

Niles owns the music and creative lane:

- Music, creative, and audio planning.
- Live set prep.
- Song, session, and setlist notes.
- Struna and Fundo context when represented in OpenClaw metadata.
- Creative planning packets and review surfaces.

Niles work should be staged as metadata, notes, or review packets unless a
specific task safely authorizes more.

## Execution Mode

Niles' normal execution mode is:

- `logical_only`
- `spawned_worker`

Niles is not currently a live daemon in this repo, and there is no DAW control
service to start from maintenance work.

## Files to Inspect

Start with these files and metadata surfaces:

- `agent_lane_registry.py`
- `operator_universal_intake.py`
- `generated/read_models/niles_album_review_packet.json`
- `generated/read_models/niles_album_matrix_review.json`
- `generated/read_models/niles_album_metadata_intake_packet.json`
- `generated/read_models/niles_album_evidence_intake_boundary.json`
- `generated/read_models/repo_b_niles_music_worker_wrapper.json`
- `generated/read_models/struna_obscura_project_capsule.json`
- `chief_fundo_identity.py`
- `chief_fundo_session.py`
- `chief_fundo_release.py`

Inspect by file name and metadata contract first. Do not broadly scan private
media, session, stems, bounce, or DAW project folders.

## Hard Boundaries

Niles must not:

- Start DAW, Logic, Ableton, OBS, audio engines, or media tooling.
- Mutate session, media, audio, stems, bounce, or project files.
- Scan private media/session folders broadly.
- Export, bounce, publish, upload, or distribute audio.
- Treat creative notes as business authorization.
- Read secrets, env files, tokens, credentials, OAuth material, or account
  configuration.
- Execute Cassandra, Chief, Guardian, or Hermes lane work directly.

## Runtime Service Names

No dedicated Niles live daemon is expected for this repo.

Related service posture:

- No `niles-*` systemd service should be started from this maintenance guide.
- Niles work may appear through spawned workers, lane registry metadata, or
  generated read models.

## What Not to Start

Do not start:

- Logic, Ableton, OBS, DAW bridges, audio renderers, or media exporters.
- Generic Niles daemons.
- Hermes gateway or sidecars.
- Cassandra or Guardian listeners.
- Browser, email, calendar, contacts, Coupa, bank, or external API tools.

## What Not to Mutate

Do not mutate:

- DAW sessions, audio media, stems, bounces, exports, artwork, or release files.
- Private session folders or broad media libraries.
- Invoices, ledgers, workbooks, PDFs, Coupa records, bank records, or paid
  status.
- Runtime policy or confirmed reference data.
- Generated read models unless the active task is explicitly a read-model
  export/update task.

## Tests / Validation

Choose the narrowest local validation set for the change. Common Niles-adjacent
checks include:

```bash
.venv/bin/python -m pytest -s -q tests/test_agent_lane_registry.py
.venv/bin/python -m pytest -s -q tests/test_operator_universal_intake.py
.venv/bin/python -m pytest -s -q tests/test_niles_album_review_packet.py
.venv/bin/python -m pytest -s -q tests/test_niles_album_matrix_review.py
git diff --check
```

If a listed test file is absent or renamed, inspect the current `tests/`
directory and run the closest scoped test. Do not run DAW, media, or external
publish validation unless the active task explicitly authorizes it.

## Current Known Caveats

- Niles is logical/spawned, not a service to keep alive.
- Creative prep can be useful without touching media files.
- Struna/Fundo context should be handled as metadata unless the task clearly
  permits deeper work.
- Some Niles read models are generated artifacts; avoid committing unrelated
  generated drift.
- Public-facing identity or release decisions may require Cassandra/Guardian or
  explicit operator review depending on the action.

## Safety Checklist

Before making Niles-related changes:

- Confirm the active task allows code or doc edits.
- Run `git status --short` and isolate unrelated drift.
- Prefer metadata and review packets over media/session mutation.
- Do not inspect secrets/env/token/credential files.
- Do not start DAW, Logic, Ableton, OBS, or audio tooling.
- Do not export, bounce, publish, or upload audio.
- Add or run focused tests when code changes are made.
- Run `git diff --check` before committing.
