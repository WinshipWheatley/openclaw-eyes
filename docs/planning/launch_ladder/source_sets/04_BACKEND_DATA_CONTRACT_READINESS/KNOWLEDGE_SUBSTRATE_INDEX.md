# Knowledge Substrate Index

Status: index for the docs/test-only Operator Harness knowledge-substrate planning package.

Use this package when the work concerns future SQLite-backed local memory, compiled notes, safe historical business-file context, synthetic knowledge fixtures, app-state cards for knowledge records, or the boundary between retrieval and durable compiled knowledge.

Do not use this package to authorize ingestion, database creation, provider/model calls, private-data inspection, or app/backend/runtime implementation.

## Files

- `README.md`: package purpose, doctrine, mirror posture, and hard boundary.
- `01_NORTH_STAR.md`: Compiled Knowledge Substrate definition, old business files motivation, evidence/truth boundary, and promotion model.
- `02_SQLITE_LAYER_MODEL.md`: conceptual layers/tables from `source_files` through `audit_events` or `substrate_events`.
- `03_SAFETY_AND_SENSITIVITY_LEVELS.md`: sensitivity levels and local-first restrictions.
- `04_APP_CARDS_AND_UI_STATES.md`: future read-only app cards and state language.
- `05_FIXTURE_PLAN.md`: synthetic fixture names and expected validation rules.
- `06_STATIC_VALIDATION_EXPECTATIONS.md`: static checks and implementation blockers.

## Current Source-Set Posture

This package is created while the active baseline is `02_MAC_IOS_APP_BUILD`. It prepares future backend/data-model thinking, but it does not move the project to `03_BACKEND_AND_DATA_MODEL` by itself.

Before moving this lane to `03_BACKEND_AND_DATA_MODEL`, preserve these doctrines:

- SQLite is canonical local memory.
- Markdown is export/handoff.
- HTML/rich fragments preserve shape.
- FTS/search finds candidates.
- Compiled notes make recurring knowledge useful.
- Operator promotions determine accepted working context.
- Unknown remains unknown.
