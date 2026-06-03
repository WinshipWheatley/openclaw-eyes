# SQLite Consolidation Plan

Status: `SQLITE_CONSOLIDATION_PLAN_READY`

This is a planning-only consolidation map. It does not migrate, move, delete, or mutate existing databases.

## Do Not Touch

- `protected_business_ledger`: 438 DBs. Business ledger and ledger-shaped databases are protected; consolidation risk is forbidden.
- `legacy_archives`: 0 DBs. Archives/backups remain historical evidence until separately reviewed.
- `unknown_needs_review`: 10 DBs. Unknown ownership defaults to no writes and manual review.
- `protected_evidence`: 1 DBs. Privacy/protected evidence such as token vaults must never enter read-model consolidation.
- `token_secret_credential_stores`: 3 DBs. Token, secret, credential, and vault stores must not enter read-model or workflow consolidation.

## Keep Isolated

- `test_harness`: 186 DBs. Test harness and pytest databases cannot become canonical truth.
- `generated_proof_status_dbs`: 17 DBs. Generated proof/status stores are evidence unless a future owner map proves otherwise.
- `one_off_read_model_proof_dbs`: 10 DBs. One-off proof/read-model databases should stay as source evidence, not merged into canonical workflow state.
- `dry_run_warmup_dbs`: 2 DBs. Dry-run, smoke, and warmup databases are validation artifacts, not canonical state.

## Consolidation Candidates

- `package_queue_event_concepts` (medium): Create a read-only package_event_overlay view/index plan over package queue and package_event_index refs; do not migrate source DB rows.
- `request_response_index_concepts` (low): Use package_event_index as the first overlay; add derived views/indexes only after proving request/response refs and counts.
- `operator_conversation_index_concepts` (medium): Create a derived index that joins journal entry refs to package_event_index refs; keep journal as canonical history.
- `work_log_staging_if_safe` (medium): Keep staged work logs isolated until operator confirmation; future overlay may expose package/work-log staging indexes without workbook mutation.

## Recommended First Low-Risk Move

Create views/indexes over existing package/event/journal refs, not a data migration; use package_event_index as the cross-reference layer. This remains plan-only here.

## Migration Requirements

- `backup`: Create verified backups of every source database before any future write.
- `schema_diff`: Compare schemas and table contracts before creating any overlay or migration target.
- `row_count_proof`: Record pre/post row counts for every affected table.
- `checksum_or_sample_row_proof`: Record checksums or sample-row proof for every affected table before and after any future write.
- `rollback_plan`: Document exact rollback steps and owners before changes.
- `focused_tests`: Add focused tests for joins, refs, permissions, and forbidden state mixing.
- `no_business_ledger_mixing`: Prove protected ledger databases are excluded from package/agent/read-model stores.
- `operator_approval`: Require explicit operator approval for any database write, index, view, migration, move, or delete.

## Never Consolidate

- Never consolidate ledger into package DB.
- Never consolidate secrets/tokens into read models.
- Never consolidate raw prompt bodies into operator journal.
- Never consolidate test harness into canonical state.

## Boundary

- No database consolidation, move, delete, migration, or existing DB mutation.
- No ledger, workbook, email, Gmail, browser, Coupa, paid marking, submit, or push.
