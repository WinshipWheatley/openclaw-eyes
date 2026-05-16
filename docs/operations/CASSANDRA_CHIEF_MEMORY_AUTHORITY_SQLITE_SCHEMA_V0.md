# Cassandra/Chief Memory Authority SQLite Schema v0

## Purpose

This lane adds schema and read-model support for Cassandra/Chief memory
authority without importing legacy data. Repo A remains canonical. Old files are
evidence candidates, not truth.

## Tables

The implementation lives in `cassandra_chief_memory_authority.py` and creates
metadata-only tables:

- `cassandra_chief_memory_sources`
- `cassandra_chief_memory_entities`
- `cassandra_chief_memory_entity_aliases`
- `cassandra_chief_memory_entity_relationships`
- `cassandra_chief_memory_contact_channels`
- `cassandra_chief_memory_email_permissions`
- `cassandra_chief_memory_finance_source_links`
- `cassandra_chief_correspondence_threads`
- `cassandra_chief_correspondence_events`
- `cassandra_chief_calendar_note_metadata`
- `cassandra_chief_album_progress_refs`
- `cassandra_chief_notes`
- `cassandra_chief_session_snapshots`
- `cassandra_chief_legacy_task_refs`
- `cassandra_chief_legacy_approval_refs`
- `cassandra_chief_memory_dry_run_reviews`

Every source-specific table preserves source reference, source type, optional
source hash, sensitivity level, trust status, evidence status, owner scope,
tenant id, `no_send_authority`, `no_runtime_authority`, `approval_required`,
and `recommended_fate`.

## Hybrid Fates

Allowed fates:

- `import_structured_facts_to_sqlite`
- `register_as_evidence_source_only`
- `summarize_or_extract_only`
- `block_no_go`
- `delete_local_residue`
- `defer_operator_review`

Prompt 2 source-catalog rows are static metadata only and keep
`import_allowed_in_prompt_2=false`.

## Reusable Classification / Tagging Pattern

This schema follows
`docs/operations/OPENCLAW_CLASSIFICATION_TAGGING_PATTERN_V0.md`.

The reusable part is not Cassandra-specific:

- identify the source with a stable id and safe reference
- classify type, category/world, sensitivity, trust/evidence posture, and
  lifecycle status
- assign a reviewed fate before any import or deletion lane
- keep raw-content, retention, allowed-agent-use, approval, and authority flags
  explicit
- render concise operator buckets before any structured import happens

The Cassandra/Chief-specific part is the seeded source list. Future ingest lanes
should reuse the pattern without assuming every legacy file becomes SQLite truth.

## Boundaries

- No raw data import.
- No raw log/private file reading.
- No source file content hashing.
- No Repo B execution.
- No Telegram/Gmail/email send.
- No runtime activation.
- No active approval authority from old HITL JSON/JSONL.
- No generated `agent_presence` snapshot is treated as canonical memory.
- No untracked `polish_loop/tasks` residue is committed as evidence.

## Read-Models

The dedicated exporter writes:

- `generated/read_models/cassandra_chief_memory_authority.json`
- `generated/read_models/cassandra_chief_memory_authority_OPERATOR.md`
- `generated/read_models/cassandra_chief_memory_dry_run.json`
- `generated/read_models/cassandra_chief_memory_dry_run_OPERATOR.md`
- `generated/read_models/cassandra_chief_memory_operator_review.md`

The operator review packet is the human review surface for deciding what, if
anything, should be imported in a later approved structured import lane.
