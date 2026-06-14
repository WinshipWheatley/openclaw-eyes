# Package Event Index

Status: `PACKAGE_EVENT_INDEX_READY`

This is a non-destructive reference index across workflow packages, Mission Control requests/responses, operator conversation journal entries, and selected read models.

## Outputs

- Read model: `generated/read_models/package_event_index.json`
- SQLite index: `generated/system_knowledge/package_event_index.sqlite`
- Bridge read model: `/mnt/e/openclaw/generated/read_models/package_event_index.json`

## Scope

- Rows indexed: `32`
- Workflow refs: `capital_hilton_invoice_operator_assist, capital_hilton_proposal_followup, st_annes_work_log_event`
- Existing SQLite databases are referenced only. They are not consolidated, moved, deleted, or rewritten.
- Business ledger databases are excluded.
- Raw prompt and request bodies are not stored.
- Email/Coupa/proposal events are only marked from already ingested operator-assisted read models.

## Consolidation Risk

The index reduces duplicate package concept risk by making one cross-reference surface without merging source databases.
