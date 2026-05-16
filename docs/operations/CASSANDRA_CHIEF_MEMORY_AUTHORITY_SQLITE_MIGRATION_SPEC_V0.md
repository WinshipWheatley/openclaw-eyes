# Cassandra/Chief Memory Authority SQLite Migration Spec v0

## Purpose

Move Cassandra/Chief memory authority toward Repo A SQLite/governed evidence without importing data in this lane.

Repo A is canonical. Repo B is reference-only. Ad hoc JSON, JSONL, CSV, Markdown, Windows-side logs, and vault files are import candidates or reference material, not authority.

Target spine:

```text
telegram_agent_intake
-> intent_records
-> Work Board / Agent Work Packet
-> Operator Action / Guardian
-> receipts/read-models
```

This spec does not modify runtime, activate agents, import data, read raw private files, send Telegram/Gmail/email, execute Repo B, or authorize old HITL state.

## Existing Repo A Authority Surfaces

Use these surfaces before creating new tables:

| concern | existing surface | authority posture |
| --- | --- | --- |
| Telegram/operator intake | `telegram_agent_intake.py` | Canonical metadata intake; no raw payload, no send. |
| Intent routing | `intent_router.py` | Canonical deterministic intent records; no execution. |
| Unified capture | `governed_intake_spine.py` | Bridge over intent/work-board/packet; no runtime authority. |
| Work planning | `work_board.py`, `agent_work_packet.py` | Canonical planning/projection; no execution. |
| Approved actions | `operator_action.py`, `operator_action_inbox.py` | Canonical action/approval/execution records for allowlisted local actions. |
| Finance evidence packets | `finance_invoice_evidence_packet.py`, `capital_hilton_invoice_packet.py`, `finance_invoice_reconciliation.py` | Canonical invoice/receivable evidence posture; no send, bank access, or financial truth claims. |
| Module/capsule posture | `module_registry.py`, `project_capsule.py` | Planning metadata only. |
| Estate/read-model posture | `estate_read_model.py` | Read-model visibility only; no authority. |

## Ad Hoc Memory Surfaces Found Or Referenced

No raw contents were read. This inventory comes from safe code/path references.

| surface | category | current role | proposed fate |
| --- | --- | --- | --- |
| `/home/openclaw/finance_state.json` | invoice/receivable/payment facts | Cassandra finance context and status answers | Import later into finance evidence packet/reconciliation tables as parsed evidence, not truth. |
| `/home/openclaw/cassandra_reality_notes.json` | Cassandra notes | Reality/briefing context | Import later into Cassandra note evidence table with sensitivity and trust labels. |
| `/home/openclaw/contact_nicknames.json` | contacts, nicknames, allowed-recipient posture | Cassandra contact lookup, identity, pins | Import later into contact/entity/channel tables; block raw chat IDs and private identifiers from operator read-models. |
| `/home/openclaw/OpenClaw/state/chief_session.json` | Chief session/task memory | Active workflow/session state | Import later only as session metadata snapshots; not authority for future routing. |
| `/mnt/c/OpenClaw/logs/chief_input.log` | Chief task/input log | Legacy listener input queue | Reference-only or metadata import after redaction; never raw authority. |
| `/mnt/c/OpenClaw/logs/chief_queue.log` | Chief task queue | Legacy queue/worker state | Reference-only; supersede with Work Board. |
| `/mnt/c/OpenClaw/logs/route_log.csv` | routing telemetry | Chief/Cassandra route logger | Optional telemetry import as route metadata only; not routing authority. |
| `/mnt/c/OpenClaw/logs/cassandra_state.json` | Cassandra runtime memory | Legacy state file | Import later as deprecated state metadata only; not authority. |
| `/mnt/c/OpenClaw/logs/cassandra_pending_followups.jsonl` | future action/follow-up | Pending reminders/follow-ups | Block from runtime use; import only as review items with no-send/no-runtime flags. |
| `/mnt/c/OpenClaw/logs/cassandra_conversations.jsonl` | correspondence/conversation history | Legacy conversation log | Metadata-only import candidate; raw body import blocked unless separately approved. |
| `/mnt/c/OpenClaw/logs/cassandra_correspondence.jsonl` | correspondence/send-state | Email/outreach/send-state history | Metadata-only import candidate; body/recipient raw values must be hashed/redacted. |
| `/mnt/c/OpenClaw/logs/cassandra_outreach.jsonl` | outreach history | Legacy outreach flow log | Reference-only until draft-only policy is formalized. |
| `/mnt/c/OpenClaw/logs/cassandra_email_thread_state.json` | email thread state | Known-contact/email thread tracking | Import later into correspondence state table after raw-body redaction. |
| `/mnt/c/OpenClaw/logs/cassandra_email_thread_analysis.jsonl` | email analysis | Thread analysis log | Reference-only unless metadata can be extracted without bodies. |
| `/mnt/c/OpenClaw/logs/approval_pending.json` | approval/HITL state | Legacy approval pending record | Block as authority; reconcile into Operator Action only through explicit migration receipts. |
| `/mnt/c/OpenClaw/logs/hitl_pending_state.json` | approval/HITL state | Old HITL action store | Block as authority; import only terminal/audit metadata after Operator Action reconciliation. |
| `/mnt/c/OpenClaw/logs/hitl_audit.jsonl` | approval/HITL audit | Old HITL audit log | Metadata import candidate for historical receipts only; no current approval authority. |
| `/mnt/c/OpenClaw/billing/tracker/invoice_tracker.csv` | invoice/receivable facts | Legacy invoice tracker | Import later into finance evidence packet/reconciliation tables if approved; raw CSV read requires separate lane. |
| `/mnt/c/OpenClaw/billing/invoices/` | invoice artifacts | Legacy generated PDFs | Reference-only metadata import; no PDF parsing in v0. |
| `/home/openclaw/OpenClaw/exports/billing_records.csv` and `.jsonl` | invoice/payment/expense facts | Legacy finance records | Import later through finance evidence schema with operator review. |
| `/mnt/c/OpenClawShared/business/contacts.json` | contacts/company/email/phone | Legacy contacts | Import later into contact/channel tables only after explicit approval; values redacted or hashed. |
| `/mnt/c/OpenClawShared/business/email_log.json` | email correspondence | Legacy email log | Metadata-only import candidate; body/raw recipient fields redacted. |
| `/mnt/c/OpenClawShared/business/sms_log.json` | correspondence/contact | Legacy SMS log | Reference-only for this lane; no send or phone-number exposure. |
| `/mnt/c/OpenClawShared/business/call_log.json` | contact/call notes | Legacy call log | Metadata-only import candidate; raw notes blocked by default. |
| `/mnt/c/OpenClawShared/business/expense_log.json` | finance/tax/payment facts | Legacy CPA/expense log | Import later only through finance/tax-sensitive evidence lane. |
| `/mnt/c/OpenClawShared/business/musiclaw_log.json` | advisory/legal-sensitive notes | Legacy music-law log | Reference-only; do not import into Cassandra/Chief memory v0. |
| `/mnt/c/OpenClawShared/album/album_work_log.csv` | album/song progress | Legacy album matrix | Future Niles album matrix import, not Cassandra/Chief v0. |
| `/mnt/c/OpenClawShared/album/content_log.json` | content progress | Legacy content state | Future music/marketing module import; reference-only here. |
| `/mnt/c/OpenClawShared/album/scheduler_state.json` | calendar/scheduler state | Legacy scheduler/focus state | Block runtime authority; metadata-only import if needed. |
| `/mnt/c/OpenClawShared/album/brainstorm_log.json` | planning/progress notes | Legacy brainstorm state | Future planning/music module import. |
| `/mnt/c/OpenClawShared/album/reflection_log.json` | advisory/reflection | Legacy reflection state | Future Hermes advisory import; not Cassandra/Chief authority. |
| `/mnt/c/OpenClawShared/album/goals.json` | goals/progress | Legacy goals state | Future planning import; not Cassandra/Chief authority. |
| `generated/read_models/agent_presence.*` | generated volatile snapshot | Runtime presence read-model residue | Do not commit as current truth until regenerated/reworked. |

## Category Designs

### 1. Source Catalog

Create `cassandra_chief_memory_sources` for every source considered by a future import lane.

Required fields:

- `source_id`
- `source_path`
- `source_type`
- `source_category`
- `source_hash`
- `source_hash_kind`
- `source_path_hash`
- `source_repo`
- `source_owner`
- `owner_scope`
- `tenant_id`
- `sensitivity_level`
- `trust_status`
- `evidence_status`
- `import_status`
- `redaction_policy`
- `raw_content_read`
- `raw_content_imported`
- `source_reviewed_at`
- `created_at`

Rules:

- `source_hash` is null unless the future lane is explicitly allowed to read the file bytes.
- `source_path_hash` may hash the path string without opening the file.
- `raw_content_read=false` and `raw_content_imported=false` by default.
- No source catalog row grants runtime, send, or approval authority.

### 2. Contacts, Nicknames, Companies, And Channels

Create:

- `cassandra_chief_memory_entities`
- `cassandra_chief_memory_entity_aliases`
- `cassandra_chief_memory_entity_relationships`
- `cassandra_chief_memory_contact_channels`
- `cassandra_chief_memory_email_permissions`

Use for:

- contacts and nicknames from `contact_nicknames.json`
- company/contact relationships from contact/business files
- allowed email recipient and draft/send posture
- Telegram/contact identity pins as hashes only

Required fields:

- `entity_id`, `entity_kind`, `display_label`, `display_label_redacted`
- `alias_id`, `alias_value_hash`, `alias_display`, `alias_kind`
- `relationship_id`, `from_entity_id`, `to_entity_id`, `relationship_kind`
- `channel_id`, `channel_kind`, `channel_value_hash`, `channel_display`, `channel_verified`
- `permission_id`, `permission_kind`, `draft_allowed`, `send_allowed`, `guardian_required`
- `source_id`, `source_path`, `source_type`, `source_hash`
- `sensitivity_level`, `trust_status`, `evidence_status`
- `owner_scope`, `tenant_id`
- `no_send_authority`, `no_runtime_authority`, `approval_required`
- `redaction_policy`, `created_at`, `updated_at`

Defaults:

- `send_allowed=false`
- `no_send_authority=true`
- `no_runtime_authority=true`
- `approval_required=true`
- raw chat IDs, phone numbers, email addresses, and private names are hashed or redacted in read-models.

### 3. Invoice, Receivable, And Payment Facts

Prefer existing finance surfaces:

- `finance_invoice_packets`
- `finance_invoice_packet_facts`
- `finance_invoice_packet_evidence_links`
- `finance_invoice_packet_missing_items`
- `finance_invoice_packet_risks`
- `finance_invoice_reconciliation_*`

Create only one linking table if needed:

- `cassandra_chief_memory_finance_source_links`

Use for:

- `finance_state.json`
- billing tracker CSV/PDF metadata
- billing records CSV/JSONL metadata
- Capital Hilton facts
- invoice/receivable/payment claims

Required added/link fields:

- `finance_link_id`
- `source_id`
- `packet_id`
- `fact_id`
- `legacy_record_ref_hash`
- `legacy_record_kind`
- `migration_status`
- `sensitivity_level`
- `trust_status`
- `evidence_status`
- `financial_truth_claimed`
- `invoice_send_allowed`
- `email_send_allowed`
- `bank_access_allowed`
- `spreadsheet_cell_read_allowed`
- `approval_required`

Defaults:

- `evidence_status=parsed_evidence_not_truth`
- `financial_truth_claimed=false`
- `invoice_send_allowed=false`
- `email_send_allowed=false`
- `bank_access_allowed=false`
- `spreadsheet_cell_read_allowed=false`
- `approval_required=true`

### 4. Correspondence, Email, Calendar, And Conversation Metadata

Create:

- `cassandra_chief_correspondence_threads`
- `cassandra_chief_correspondence_events`
- `cassandra_chief_calendar_note_metadata`

Use for:

- Cassandra conversations and correspondence logs
- email thread state/analysis metadata
- email log metadata
- call/SMS metadata if later approved
- calendar/event notes metadata

Required fields:

- `thread_id`, `thread_kind`, `external_thread_ref_hash`
- `event_id`, `event_kind`, `event_time`, `event_direction`
- `actor_agent`, `counterparty_entity_id`
- `subject_hash`, `subject_excerpt`, `body_hash`, `body_excerpt`
- `body_stored`
- `calendar_note_id`, `event_ref_hash`, `event_time_window`, `event_title_hash`
- `source_id`, `source_path`, `source_type`, `source_hash`
- `sensitivity_level`, `trust_status`, `evidence_status`
- `owner_scope`, `tenant_id`
- `no_send_authority`, `no_runtime_authority`, `approval_required`
- `redaction_policy`, `created_at`

Rules:

- Body text is not stored by default.
- Subject/body excerpts must be bounded and redacted.
- Calendar records are notes/metadata only, not live calendar truth.
- No row authorizes reply, send, calendar write, or follow-up.

### 5. Cassandra Notes And Chief Session/Task Memory

Create:

- `cassandra_chief_notes`
- `cassandra_chief_session_snapshots`
- `cassandra_chief_legacy_task_refs`

Use for:

- Cassandra reality notes
- Chief session state
- legacy task/queue references
- route logs as telemetry

Required fields:

- `note_id` or `snapshot_id`
- `note_kind` or `session_kind`
- `summary`
- `raw_body_hash`
- `raw_body_stored`
- `source_id`, `source_path`, `source_type`, `source_hash`
- `sensitivity_level`, `trust_status`, `evidence_status`
- `owner_scope`, `tenant_id`
- `superseded_by`
- `no_send_authority`, `no_runtime_authority`, `approval_required`
- `created_at`, `observed_at`

Rules:

- Chief queue/session files do not become routing authority.
- Import creates reviewable memory/evidence only.
- Work Board is the canonical replacement for legacy queue/task state.

### 6. Approval And HITL State

Do not import old HITL JSON as active approval authority.

Use existing or future-consolidated surfaces:

- `operator_action_requests`
- `operator_action_approvals`
- `operator_action_receipts`
- a new `cassandra_chief_legacy_approval_refs` table only for historical reference.

Create:

- `cassandra_chief_legacy_approval_refs`

Required fields:

- `legacy_approval_ref_id`
- `source_id`
- `legacy_action_hash`
- `legacy_status`
- `mapped_operator_action_id`
- `migration_status`
- `authority_status`
- `reason_not_authority`
- `sensitivity_level`
- `trust_status`
- `evidence_status`
- `approval_required`
- `no_send_authority`
- `no_runtime_authority`
- `created_at`

Rules:

- `authority_status=historical_reference_only` by default.
- Old `approval_pending.json`, `hitl_pending_state.json`, and `hitl_audit.jsonl` cannot approve anything.
- Prompt 2 must block old HITL import as active state until Operator Action reconciliation is explicit and test-backed.

### 7. Album, Music, Planning, And Advisory State

Do not bring album/music/advisory state into Cassandra/Chief memory authority tables except as blocked/reference source rows.

Use future lanes:

- Niles Album Production Matrix v0 for `album_work_log.csv`, content log, scheduler/focus, song/album state.
- Hermes Next Lane Stratifier v0 for reflection/scout/integration proposal logs.
- Guardian Approval Gate Consolidation v0 for choice/focus/approval files.

Prompt 2 may catalog these paths in `cassandra_chief_memory_sources` with `import_status=deferred_to_other_module`.

## Evidence Status Vocabulary

Use only:

- `parsed_evidence_not_truth`
- `operator_confirmed`
- `deprecated`
- `blocked`

Default for imported legacy facts is `parsed_evidence_not_truth`. Operator confirmation requires an explicit receipt or approved action path.

## Sensitivity Levels

Use:

- `public_metadata`
- `operator_private_metadata`
- `contact_private_metadata`
- `client_private_metadata`
- `finance_sensitive_metadata`
- `tax_legal_sensitive`
- `raw_private_blocked`
- `unknown_review`

Prompt 2 should default unknown or body-bearing sources to `unknown_review` or `raw_private_blocked`.

## Trust Status

Use:

- `operator_supplied`
- `legacy_runtime_claim`
- `generated_runtime_snapshot`
- `approved_evidence_reference`
- `external_unverified`
- `deprecated`
- `unknown_review`

Legacy runtime claims are not truth until operator-confirmed or linked to approved evidence.

## Redaction Requirements

Never export raw:

- credentials, env values, tokens
- chat IDs or Telegram raw payloads
- private message bodies
- email bodies
- phone numbers
- raw email addresses unless separately approved for display
- bank/payment account data
- spreadsheet cells
- tax/legal private content
- no-go root contents

Read-models may show:

- counts
- source categories
- redacted path labels
- hashes
- bounded non-sensitive excerpts where approved
- trust/evidence/sensitivity posture
- next safe move

## Read-Model Output Needed

Prompt 2 should add a dedicated read-model, not central export integration yet:

- `generated/read_models/cassandra_chief_memory_authority.json`
- `generated/read_models/cassandra_chief_memory_authority_OPERATOR.md`

Required JSON fields:

- `schema_version: cassandra_chief_memory_authority_v0`
- `runtime_authority: false`
- `send_allowed: false`
- `repo_b_execution_allowed: false`
- `raw_private_data_imported: false`
- `source_count`
- `import_candidate_count`
- `blocked_source_count`
- `deferred_source_count`
- `counts_by_category`
- `counts_by_sensitivity`
- `counts_by_evidence_status`
- `tables`
- `sources`
- `blockers`
- `recommended_next_lane`

Operator Markdown must state:

- this is memory/evidence visibility only
- old files are import candidates, not authority
- old HITL JSON is not approval authority
- no send/runtime authority is granted
- raw private contents were not imported

## Prompt 2 Exact Implementation Scope

Create/update:

- `cassandra_chief_memory_authority.py`
- `scripts/export_cassandra_chief_memory_authority_read_model.py`
- `scripts/query_cassandra_chief_memory_authority.py`
- `tests/test_cassandra_chief_memory_authority.py`
- `docs/operations/CASSANDRA_CHIEF_MEMORY_AUTHORITY_SQLITE_SCHEMA_V0.md`

Do not create import scripts yet. Prompt 2 is schema/read-model only.

Prompt 2 should initialize the SQLite schema and seed source-catalog rows from safe static path references only. It should not open, parse, hash contents, or import records from the ad hoc files.

## Prompt 2 Tests

Add tests proving:

- all proposed tables initialize in a temp SQLite database
- source catalog rows are metadata-only
- required fields exist
- `runtime_authority=false`
- `send_allowed=false`
- old HITL JSON rows are `historical_reference_only` or `blocked`
- finance facts route to existing finance packet/reconciliation surfaces rather than duplicate finance authority
- contact/channel values are hashed/redacted in read-models
- generated volatile `agent_presence` files are not treated as truth
- no Repo B import/execution occurs
- no network/API/subprocess/send path exists in the new module/scripts
- no raw private contents are read or stored

## Validation Commands For Prompt 2

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_cassandra_chief_memory_authority.py -q
PYTHONDONTWRITEBYTECODE=1 python3 scripts/query_cassandra_chief_memory_authority.py --report summary --format operator
PYTHONDONTWRITEBYTECODE=1 python3 scripts/export_cassandra_chief_memory_authority_read_model.py --format operator
git diff --check
git diff --cached --check
git status -sb --untracked-files=all
```

Only integrate with `scripts/export_read_models.py` or `scripts/generate_operator_status.py` after the dedicated read-model is stable and generated-state drift is understood.

## Import Stop Conditions

Any future import lane must stop if:

- it needs env files, secrets, tokens, or credential paths
- it needs raw Telegram logs or raw message bodies
- it needs bank data or spreadsheet cells
- it needs client/private raw contents without explicit approval
- it needs to run Repo B code
- it needs to modify live runtime services
- it needs to send Telegram/Gmail/email/SMS
- it needs to approve actions from old HITL JSON
- it cannot distinguish old HITL state from Operator Action authority
- it would create a generic CRM instead of OpenClaw evidence/memory authority
- generated file handling is unclear
- current dirty `agent_presence` files would be committed as truth

## Blocked Or Deferred Sources

Blocked from active authority:

- old HITL JSON state
- direct send logs
- future-action/follow-up queues
- route CSV as routing authority
- Chief queue logs as task authority
- any raw body logs
- billing PDFs as truth without approved evidence

Deferred:

- album/song/content state to Niles module lanes
- reflection/scout/integration logs to Hermes module lanes
- legal/tax/music-law state to a separate sensitive advisory lane
- dashboard/raw runtime snapshot surfaces until read-model safety is reworked

## Prompt 2 Readiness

Prompt 2 is ready for schema/read-model work only.

It is not ready for importing real data. It must not parse or ingest the listed ad hoc files. It should catalog safe static source references and create the schema/read-model boundary that a later import lane can use.
