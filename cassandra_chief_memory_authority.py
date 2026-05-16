"""Cassandra/Chief Memory Authority v0.

This module creates metadata-only SQLite/read-model support for Cassandra and
Chief memory authority. It does not import legacy file contents, treat old
files as truth, run Repo B, send messages, activate agents, or grant runtime
authority.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger


ROOT = Path(__file__).resolve().parent
AUTHORITY_VERSION = "cassandra_chief_memory_authority_v0"
DRY_RUN_VERSION = "cassandra_chief_memory_dry_run_v0"
READ_MODEL_VERSION = AUTHORITY_VERSION
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
AUTHORITY_JSON_EXPORT_NAME = "cassandra_chief_memory_authority.json"
AUTHORITY_OPERATOR_EXPORT_NAME = "cassandra_chief_memory_authority_OPERATOR.md"
DRY_RUN_JSON_EXPORT_NAME = "cassandra_chief_memory_dry_run.json"
DRY_RUN_OPERATOR_EXPORT_NAME = "cassandra_chief_memory_dry_run_OPERATOR.md"
OPERATOR_REVIEW_EXPORT_NAME = "cassandra_chief_memory_operator_review.md"

ALLOWED_FATES = {
    "import_structured_facts_to_sqlite",
    "register_as_evidence_source_only",
    "summarize_or_extract_only",
    "block_no_go",
    "delete_local_residue",
    "defer_operator_review",
}

EVIDENCE_STATUSES = {
    "parsed_evidence_not_truth",
    "operator_confirmed",
    "deprecated",
    "blocked",
}

NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "send_allowed": False,
    "telegram_send_allowed": False,
    "gmail_send_allowed": False,
    "email_send_allowed": False,
    "repo_b_execution_allowed": False,
    "agent_activation_allowed": False,
    "runtime_activation_allowed": False,
    "network_authority": False,
    "external_api_allowed": False,
    "arbitrary_shell_allowed": False,
    "data_import_allowed": False,
    "raw_file_ingest_allowed": False,
    "raw_private_data_imported": False,
    "raw_telegram_logs_read": False,
    "spreadsheet_cell_read_allowed": False,
    "bank_data_access_allowed": False,
    "old_files_are_truth": False,
    "old_hitl_json_active_approval_authority": False,
}

REQUIRED_AUTHORITY_COLUMNS = {
    "source_path",
    "source_ref",
    "source_type",
    "source_hash",
    "sensitivity_level",
    "trust_status",
    "evidence_status",
    "owner_scope",
    "tenant_id",
    "no_send_authority",
    "no_runtime_authority",
    "approval_required",
    "recommended_fate",
}

TABLE_NAMES = (
    "cassandra_chief_memory_sources",
    "cassandra_chief_memory_entities",
    "cassandra_chief_memory_entity_aliases",
    "cassandra_chief_memory_entity_relationships",
    "cassandra_chief_memory_contact_channels",
    "cassandra_chief_memory_email_permissions",
    "cassandra_chief_memory_finance_source_links",
    "cassandra_chief_correspondence_threads",
    "cassandra_chief_correspondence_events",
    "cassandra_chief_calendar_note_metadata",
    "cassandra_chief_album_progress_refs",
    "cassandra_chief_notes",
    "cassandra_chief_session_snapshots",
    "cassandra_chief_legacy_task_refs",
    "cassandra_chief_legacy_approval_refs",
    "cassandra_chief_memory_dry_run_reviews",
)


@dataclass(frozen=True)
class SourceCandidate:
    source_id: str
    category: str
    source_name: str
    source_ref: str
    source_type: str
    recommended_fate: str
    canonical_authority_target: str
    source_retention_policy: str
    raw_content_policy: str
    allowed_agent_use: str
    reason: str
    risk_level: str
    sensitivity_level: str
    trust_status: str
    evidence_status: str
    operator_confirmation_required: bool
    prompt_2_schema_needed: bool
    structured_import_possible_later: bool
    source_repo: str = "repo_a_or_legacy_static_reference"
    owner_scope: str = "operator_local"
    tenant_id: str | None = None


SOURCE_CANDIDATES = (
    SourceCandidate(
        source_id="memsrc_contacts_nicknames",
        category="contacts and nicknames",
        source_name="contact nicknames and contact list refs",
        source_ref="repo://contact_nicknames.json; redacted://business/contacts.json",
        source_type="contact_metadata_candidate",
        recommended_fate="import_structured_facts_to_sqlite",
        canonical_authority_target="cassandra_chief_memory_entities / aliases / contact_channels",
        source_retention_policy="Keep originals until reviewed structured rows have receipts.",
        raw_content_policy="No raw chat IDs, phone numbers, private identifiers, or contact bodies in read-models.",
        allowed_agent_use="Resolve bounded identity posture for draft review only.",
        reason="Aliases and identity posture are structured enough for later governed import.",
        risk_level="medium",
        sensitivity_level="sensitive_metadata",
        trust_status="legacy_unverified",
        evidence_status="parsed_evidence_not_truth",
        operator_confirmation_required=True,
        prompt_2_schema_needed=True,
        structured_import_possible_later=True,
    ),
    SourceCandidate(
        source_id="memsrc_company_contact_relationships",
        category="company/contact relationships",
        source_name="business contact relationship refs",
        source_ref="redacted://business/contact_relationships",
        source_type="relationship_metadata_candidate",
        recommended_fate="import_structured_facts_to_sqlite",
        canonical_authority_target="cassandra_chief_memory_entity_relationships",
        source_retention_policy="Keep source refs until relationships are operator-confirmed.",
        raw_content_policy="Summaries only; client/customer details stay redacted.",
        allowed_agent_use="Show relationship posture and missing confirmation only.",
        reason="Relationship edges are useful, but labels are not verified truth.",
        risk_level="medium",
        sensitivity_level="sensitive_metadata",
        trust_status="legacy_unverified",
        evidence_status="parsed_evidence_not_truth",
        operator_confirmation_required=True,
        prompt_2_schema_needed=True,
        structured_import_possible_later=True,
    ),
    SourceCandidate(
        source_id="memsrc_email_permission_posture",
        category="allowed email recipients / email permission posture",
        source_name="allowed-recipient and email-thread posture refs",
        source_ref="repo://contact_nicknames.json; redacted://legacy_email_thread_state",
        source_type="email_permission_metadata_candidate",
        recommended_fate="import_structured_facts_to_sqlite",
        canonical_authority_target="cassandra_chief_memory_email_permissions plus Operator Action / Guardian links",
        source_retention_policy="Keep source refs until permission rows have receipts.",
        raw_content_policy="Email addresses stay hashed/redacted unless explicitly approved.",
        allowed_agent_use="Draft eligibility and approval-required status only; no send.",
        reason="Send permission posture must be governed and cannot come from old files alone.",
        risk_level="high",
        sensitivity_level="sensitive_metadata",
        trust_status="legacy_unverified",
        evidence_status="parsed_evidence_not_truth",
        operator_confirmation_required=True,
        prompt_2_schema_needed=True,
        structured_import_possible_later=True,
    ),
    SourceCandidate(
        source_id="memsrc_invoice_facts",
        category="invoice facts",
        source_name="finance state and billing record refs",
        source_ref="repo://finance_state.json; repo://OpenClaw/exports/billing_records.*",
        source_type="finance_fact_candidate",
        recommended_fate="import_structured_facts_to_sqlite",
        canonical_authority_target="finance_invoice_packet_* / finance_invoice_reconciliation_*",
        source_retention_policy="Keep originals as evidence refs until packet receipts replace them.",
        raw_content_policy="No raw spreadsheet cells, bank data, tax/private bodies, or truth claims.",
        allowed_agent_use="Build missing-facts checklists and draft context only.",
        reason="Invoice facts belong in existing finance evidence packet surfaces.",
        risk_level="high",
        sensitivity_level="finance_sensitive_metadata",
        trust_status="legacy_unverified",
        evidence_status="parsed_evidence_not_truth",
        operator_confirmation_required=True,
        prompt_2_schema_needed=True,
        structured_import_possible_later=True,
    ),
    SourceCandidate(
        source_id="memsrc_receivable_payment_tracking",
        category="receivable/payment tracking",
        source_name="invoice tracker and payment status refs",
        source_ref="redacted://billing/invoice_tracker.csv; repo://OpenClaw/exports/billing_records.*",
        source_type="receivable_metadata_candidate",
        recommended_fate="import_structured_facts_to_sqlite",
        canonical_authority_target="finance_invoice_packet_* / finance_invoice_reconciliation_* / Work Board",
        source_retention_policy="Keep old trackers until reconciliation proves no loss.",
        raw_content_policy="Payment-provider and bank raw data blocked; payment facts are claims until confirmed.",
        allowed_agent_use="Receivable posture and next-safe-move only.",
        reason="Receivable status can reduce burden only when evidence status is explicit.",
        risk_level="high",
        sensitivity_level="finance_sensitive_metadata",
        trust_status="legacy_unverified",
        evidence_status="parsed_evidence_not_truth",
        operator_confirmation_required=True,
        prompt_2_schema_needed=True,
        structured_import_possible_later=True,
    ),
    SourceCandidate(
        source_id="memsrc_correspondence_metadata",
        category="correspondence metadata",
        source_name="conversation, correspondence, email, call, and SMS refs",
        source_ref="redacted://legacy_correspondence_metadata",
        source_type="correspondence_metadata_candidate",
        recommended_fate="summarize_or_extract_only",
        canonical_authority_target="cassandra_chief_correspondence_threads / events",
        source_retention_policy="Retain original logs outside SQLite unless a future approved lane says otherwise.",
        raw_content_policy="Do not ingest bodies; store metadata, hashes, and approved redacted excerpts only.",
        allowed_agent_use="Context/history posture only; no reply or send authority.",
        reason="Correspondence logs can contain private body text.",
        risk_level="high",
        sensitivity_level="private_metadata",
        trust_status="legacy_unverified",
        evidence_status="parsed_evidence_not_truth",
        operator_confirmation_required=True,
        prompt_2_schema_needed=True,
        structured_import_possible_later=False,
    ),
    SourceCandidate(
        source_id="memsrc_calendar_event_notes",
        category="calendar/event notes metadata",
        source_name="calendar and scheduler note refs",
        source_ref="redacted://calendar_and_scheduler_notes",
        source_type="calendar_metadata_candidate",
        recommended_fate="summarize_or_extract_only",
        canonical_authority_target="cassandra_chief_calendar_note_metadata",
        source_retention_policy="Keep originals; do not parse private calendar content in this lane.",
        raw_content_policy="Titles/details hashed or summarized only; no raw calendar bodies.",
        allowed_agent_use="Metadata availability and confirmation gaps only.",
        reason="Calendar notes can guide context but are not live calendar truth.",
        risk_level="medium",
        sensitivity_level="private_metadata",
        trust_status="legacy_unverified",
        evidence_status="parsed_evidence_not_truth",
        operator_confirmation_required=True,
        prompt_2_schema_needed=True,
        structured_import_possible_later=False,
    ),
    SourceCandidate(
        source_id="memsrc_album_song_progress",
        category="album/song progress state",
        source_name="album work, content, and scheduler refs",
        source_ref="redacted://album_progress_sources",
        source_type="music_progress_metadata_candidate",
        recommended_fate="defer_operator_review",
        canonical_authority_target="future Niles Album Production Matrix",
        source_retention_policy="Keep existing files; do not convert into Cassandra/Chief authority.",
        raw_content_policy="No raw album/session content in this lane.",
        allowed_agent_use="None for Cassandra/Chief except source-catalog posture.",
        reason="This belongs to Niles/music module authority.",
        risk_level="medium",
        sensitivity_level="operator_work_metadata",
        trust_status="legacy_unverified",
        evidence_status="parsed_evidence_not_truth",
        operator_confirmation_required=True,
        prompt_2_schema_needed=False,
        structured_import_possible_later=False,
    ),
    SourceCandidate(
        source_id="memsrc_cassandra_notes",
        category="Cassandra notes",
        source_name="Cassandra reality notes ref",
        source_ref="repo://cassandra_reality_notes.json",
        source_type="cassandra_note_candidate",
        recommended_fate="summarize_or_extract_only",
        canonical_authority_target="cassandra_chief_notes plus source catalog",
        source_retention_policy="Keep source file; extract bounded reviewed summaries later only.",
        raw_content_policy="No raw private notes by default.",
        allowed_agent_use="Briefing/context posture with trust labels only.",
        reason="Reality notes may be useful but messy notes remain evidence.",
        risk_level="medium",
        sensitivity_level="private_metadata",
        trust_status="legacy_unverified",
        evidence_status="parsed_evidence_not_truth",
        operator_confirmation_required=True,
        prompt_2_schema_needed=True,
        structured_import_possible_later=False,
    ),
    SourceCandidate(
        source_id="memsrc_chief_session_task_memory",
        category="Chief session/task memory",
        source_name="Chief session, queue, and route refs",
        source_ref="repo://OpenClaw/state/chief_session.json; redacted://chief_queue_and_route_logs",
        source_type="session_task_metadata_candidate",
        recommended_fate="register_as_evidence_source_only",
        canonical_authority_target="source catalog, session snapshot metadata, Work Board",
        source_retention_policy="Retain only as historical evidence until Work Board supersedes it.",
        raw_content_policy="No raw task bodies unless a later lane approves bounded excerpts.",
        allowed_agent_use="Historical context and migration blockers only.",
        reason="Session/task files are volatile runtime state.",
        risk_level="medium",
        sensitivity_level="runtime_metadata",
        trust_status="legacy_unverified",
        evidence_status="parsed_evidence_not_truth",
        operator_confirmation_required=True,
        prompt_2_schema_needed=True,
        structured_import_possible_later=False,
    ),
    SourceCandidate(
        source_id="memsrc_old_hitl_json_jsonl",
        category="old HITL JSON/JSONL state",
        source_name="legacy HITL approval JSON/JSONL refs",
        source_ref="redacted://legacy_hitl_approval_state",
        source_type="legacy_hitl_reference",
        recommended_fate="block_no_go",
        canonical_authority_target="operator_action_* plus historical legacy approval refs",
        source_retention_policy="Retain until Guardian/Operator Action consolidation decides archival/deletion.",
        raw_content_policy="Do not ingest payload bodies as current approvals.",
        allowed_agent_use="Historical audit reference only; cannot approve, execute, or send.",
        reason="Old approval files must not become active approval authority.",
        risk_level="critical",
        sensitivity_level="approval_sensitive_metadata",
        trust_status="blocked_legacy_authority",
        evidence_status="blocked",
        operator_confirmation_required=True,
        prompt_2_schema_needed=True,
        structured_import_possible_later=False,
    ),
    SourceCandidate(
        source_id="memsrc_windows_side_logs",
        category="Windows-side logs",
        source_name="Windows-side Cassandra/Chief runtime log refs",
        source_ref="redacted://windows_side_runtime_logs",
        source_type="legacy_runtime_log_reference",
        recommended_fate="register_as_evidence_source_only",
        canonical_authority_target="cassandra_chief_memory_sources",
        source_retention_policy="Keep in place; do not copy into SQLite in this lane.",
        raw_content_policy="No raw log ingestion; safe labels and path hashes only.",
        allowed_agent_use="Diagnostics/source availability only.",
        reason="Logs are useful for diagnosis but likely contain raw private/runtime content.",
        risk_level="high",
        sensitivity_level="private_runtime_metadata",
        trust_status="legacy_unverified",
        evidence_status="parsed_evidence_not_truth",
        operator_confirmation_required=True,
        prompt_2_schema_needed=True,
        structured_import_possible_later=False,
    ),
    SourceCandidate(
        source_id="memsrc_billing_tracker_paths",
        category="billing tracker CSV/PDF paths",
        source_name="billing tracker CSV and PDF refs",
        source_ref="redacted://billing_tracker_csv_and_pdf_paths",
        source_type="billing_tracker_reference",
        recommended_fate="summarize_or_extract_only",
        canonical_authority_target="finance source links / finance evidence packet metadata",
        source_retention_policy="Keep originals; later lane may extract approved metadata only.",
        raw_content_policy="No spreadsheet cells, PDF body extraction, bank details, or truth claims.",
        allowed_agent_use="Evidence pointer and missing-facts posture only.",
        reason="Trackers/PDFs can support finance packets but raw parsing can expose private finance data.",
        risk_level="high",
        sensitivity_level="finance_sensitive_metadata",
        trust_status="legacy_unverified",
        evidence_status="parsed_evidence_not_truth",
        operator_confirmation_required=True,
        prompt_2_schema_needed=True,
        structured_import_possible_later=False,
    ),
    SourceCandidate(
        source_id="memsrc_dirty_agent_presence_snapshots",
        category="dirty generated agent_presence snapshots",
        source_name="dirty generated agent_presence read-model snapshots",
        source_ref="generated/read_models/agent_presence.*",
        source_type="generated_volatile_snapshot",
        recommended_fate="defer_operator_review",
        canonical_authority_target="future agent presence volatile-snapshot cleanup",
        source_retention_policy="Keep uncommitted until regenerated/reworked; do not treat as truth.",
        raw_content_policy="Generated metadata only; do not derive live receive proof from it.",
        allowed_agent_use="Presence caveat/readiness context only after cleanup.",
        reason="Generated runtime presence snapshots are volatile and currently dirty.",
        risk_level="medium",
        sensitivity_level="generated_metadata",
        trust_status="volatile_unverified",
        evidence_status="deprecated",
        operator_confirmation_required=True,
        prompt_2_schema_needed=False,
        structured_import_possible_later=False,
        source_repo="repo_a_generated_residue",
    ),
    SourceCandidate(
        source_id="memsrc_polish_loop_cassandra_failure_tasks",
        category="untracked polish_loop Cassandra failure tasks",
        source_name="two untracked Cassandra failure task prompts",
        source_ref=(
            "polish_loop/tasks/chief-cassandra-failure-20260513T234214.md; "
            "polish_loop/tasks/chief-cassandra-failure-20260513T235844.md"
        ),
        source_type="local_residue_reference",
        recommended_fate="delete_local_residue",
        canonical_authority_target="none",
        source_retention_policy="Do not commit; delete only in an explicit cleanup lane/operator-approved action.",
        raw_content_policy="Do not read linked raw logs from these prompts.",
        allowed_agent_use="None.",
        reason="They are duplicate generated task prompts, not durable evidence.",
        risk_level="low",
        sensitivity_level="local_residue_metadata",
        trust_status="not_authority",
        evidence_status="deprecated",
        operator_confirmation_required=True,
        prompt_2_schema_needed=False,
        structured_import_possible_later=False,
        source_repo="repo_a_untracked_residue",
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _bool_int(value: bool) -> int:
    return 1 if value else 0


def _export_root_path(export_root: str | Path) -> Path:
    path = Path(export_root)
    if path.is_absolute():
        return path
    return ROOT / path


def _display_path(path: str | Path) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return path_obj.as_posix()


def _common_record_columns_sql() -> str:
    return """
  source_id TEXT NOT NULL,
  source_path TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  source_type TEXT NOT NULL,
  source_hash TEXT,
  source_hash_kind TEXT,
  source_path_hash TEXT NOT NULL,
  sensitivity_level TEXT NOT NULL,
  trust_status TEXT NOT NULL,
  evidence_status TEXT NOT NULL,
  owner_scope TEXT NOT NULL,
  tenant_id TEXT,
  no_send_authority INTEGER NOT NULL DEFAULT 1,
  no_runtime_authority INTEGER NOT NULL DEFAULT 1,
  approval_required INTEGER NOT NULL DEFAULT 1,
  recommended_fate TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (source_id) REFERENCES cassandra_chief_memory_sources(source_id)
""".rstrip()


def _metadata_table_sql(table_name: str, primary_key: str, extra_columns: tuple[str, ...]) -> str:
    extra = "\n".join(f"  {column}," for column in extra_columns)
    return f"""
CREATE TABLE IF NOT EXISTS {table_name} (
  {primary_key} TEXT PRIMARY KEY,
{extra}
{_common_record_columns_sql()}
)
""".strip()


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS cassandra_chief_memory_sources (
  source_id TEXT PRIMARY KEY,
  source_category TEXT NOT NULL,
  source_name TEXT NOT NULL,
  source_path TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  source_type TEXT NOT NULL,
  source_hash TEXT,
  source_hash_kind TEXT,
  source_path_hash TEXT NOT NULL,
  source_repo TEXT NOT NULL,
  source_owner TEXT NOT NULL,
  owner_scope TEXT NOT NULL,
  tenant_id TEXT,
  sensitivity_level TEXT NOT NULL,
  trust_status TEXT NOT NULL,
  evidence_status TEXT NOT NULL,
  import_status TEXT NOT NULL,
  recommended_fate TEXT NOT NULL,
  source_retention_policy TEXT NOT NULL,
  raw_content_policy TEXT NOT NULL,
  allowed_agent_use TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  why_it_matters TEXT NOT NULL,
  operator_confirmation_required INTEGER NOT NULL DEFAULT 1,
  prompt_2_schema_needed INTEGER NOT NULL DEFAULT 0,
  import_allowed_in_prompt_2 INTEGER NOT NULL DEFAULT 0,
  structured_import_possible_later INTEGER NOT NULL DEFAULT 0,
  raw_content_forbidden INTEGER NOT NULL DEFAULT 1,
  raw_content_read INTEGER NOT NULL DEFAULT 0,
  raw_content_imported INTEGER NOT NULL DEFAULT 0,
  old_files_are_truth INTEGER NOT NULL DEFAULT 0,
  no_send_authority INTEGER NOT NULL DEFAULT 1,
  no_runtime_authority INTEGER NOT NULL DEFAULT 1,
  approval_required INTEGER NOT NULL DEFAULT 1,
  redaction_policy TEXT NOT NULL,
  source_reviewed_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
)
""".strip(),
        _metadata_table_sql(
            "cassandra_chief_memory_entities",
            "entity_id",
            (
                "entity_kind TEXT NOT NULL",
                "display_label_redacted TEXT NOT NULL",
                "entity_status TEXT NOT NULL",
            ),
        ),
        _metadata_table_sql(
            "cassandra_chief_memory_entity_aliases",
            "alias_id",
            (
                "entity_id TEXT",
                "alias_kind TEXT NOT NULL",
                "alias_display TEXT NOT NULL",
                "alias_value_hash TEXT",
            ),
        ),
        _metadata_table_sql(
            "cassandra_chief_memory_entity_relationships",
            "relationship_id",
            (
                "from_entity_ref TEXT NOT NULL",
                "to_entity_ref TEXT NOT NULL",
                "relationship_kind TEXT NOT NULL",
                "relationship_status TEXT NOT NULL",
            ),
        ),
        _metadata_table_sql(
            "cassandra_chief_memory_contact_channels",
            "channel_id",
            (
                "entity_ref TEXT NOT NULL",
                "channel_kind TEXT NOT NULL",
                "channel_display_redacted TEXT NOT NULL",
                "channel_value_hash TEXT",
                "channel_verified INTEGER NOT NULL DEFAULT 0",
            ),
        ),
        _metadata_table_sql(
            "cassandra_chief_memory_email_permissions",
            "permission_id",
            (
                "entity_ref TEXT NOT NULL",
                "permission_kind TEXT NOT NULL",
                "draft_allowed INTEGER NOT NULL DEFAULT 0",
                "send_allowed INTEGER NOT NULL DEFAULT 0",
                "guardian_required INTEGER NOT NULL DEFAULT 1",
                "approval_link_ref TEXT",
            ),
        ),
        _metadata_table_sql(
            "cassandra_chief_memory_finance_source_links",
            "finance_link_id",
            (
                "finance_link_kind TEXT NOT NULL",
                "finance_surface TEXT NOT NULL",
                "finance_record_ref TEXT",
                "fact_authority_status TEXT NOT NULL",
            ),
        ),
        _metadata_table_sql(
            "cassandra_chief_correspondence_threads",
            "thread_id",
            (
                "thread_ref TEXT NOT NULL",
                "direction TEXT NOT NULL",
                "participant_ref TEXT NOT NULL",
                "body_import_allowed INTEGER NOT NULL DEFAULT 0",
            ),
        ),
        _metadata_table_sql(
            "cassandra_chief_correspondence_events",
            "event_id",
            (
                "event_ref TEXT NOT NULL",
                "thread_ref TEXT",
                "event_kind TEXT NOT NULL",
                "body_import_allowed INTEGER NOT NULL DEFAULT 0",
            ),
        ),
        _metadata_table_sql(
            "cassandra_chief_calendar_note_metadata",
            "calendar_note_id",
            (
                "event_ref TEXT NOT NULL",
                "calendar_ref TEXT",
                "title_hash TEXT",
                "note_body_import_allowed INTEGER NOT NULL DEFAULT 0",
            ),
        ),
        _metadata_table_sql(
            "cassandra_chief_album_progress_refs",
            "album_progress_ref_id",
            (
                "album_ref TEXT",
                "song_ref TEXT",
                "niles_authority_required INTEGER NOT NULL DEFAULT 1",
            ),
        ),
        _metadata_table_sql(
            "cassandra_chief_notes",
            "note_id",
            (
                "note_ref TEXT NOT NULL",
                "summary_ref TEXT",
                "raw_note_import_allowed INTEGER NOT NULL DEFAULT 0",
            ),
        ),
        _metadata_table_sql(
            "cassandra_chief_session_snapshots",
            "session_snapshot_id",
            (
                "session_ref TEXT NOT NULL",
                "superseded_by TEXT NOT NULL",
                "work_board_ref TEXT",
            ),
        ),
        _metadata_table_sql(
            "cassandra_chief_legacy_task_refs",
            "legacy_task_ref_id",
            (
                "legacy_task_ref TEXT NOT NULL",
                "residue_status TEXT NOT NULL",
                "delete_candidate INTEGER NOT NULL DEFAULT 0",
            ),
        ),
        _metadata_table_sql(
            "cassandra_chief_legacy_approval_refs",
            "legacy_approval_ref_id",
            (
                "legacy_approval_ref TEXT NOT NULL",
                "active_approval_authority INTEGER NOT NULL DEFAULT 0",
                "historical_reference_only INTEGER NOT NULL DEFAULT 1",
                "approval_block_reason TEXT NOT NULL",
            ),
        ),
        """
CREATE TABLE IF NOT EXISTS cassandra_chief_memory_dry_run_reviews (
  dry_run_id TEXT PRIMARY KEY,
  dry_run_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  source_count INTEGER NOT NULL DEFAULT 0,
  data_import_allowed INTEGER NOT NULL DEFAULT 0,
  raw_file_ingest_allowed INTEGER NOT NULL DEFAULT 0,
  old_files_are_truth INTEGER NOT NULL DEFAULT 0,
  repo_b_execution_allowed INTEGER NOT NULL DEFAULT 0,
  send_allowed INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  operator_review_packet_created INTEGER NOT NULL DEFAULT 0,
  notes TEXT NOT NULL
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_cc_memory_sources_category ON cassandra_chief_memory_sources(source_category)",
        "CREATE INDEX IF NOT EXISTS idx_cc_memory_sources_fate ON cassandra_chief_memory_sources(recommended_fate)",
        "CREATE INDEX IF NOT EXISTS idx_cc_memory_sources_risk ON cassandra_chief_memory_sources(risk_level)",
    )


def init_cassandra_chief_memory_authority_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path or DEFAULT_DB_PATH)
    parent = Path(path).parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    init_business_ops_ledger(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def cassandra_chief_memory_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_cassandra_chief_memory_authority_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'cassandra_chief%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _validate_candidate(candidate: SourceCandidate) -> None:
    if candidate.recommended_fate not in ALLOWED_FATES:
        raise ValueError(f"unsupported source fate: {candidate.source_id}")
    if candidate.evidence_status not in EVIDENCE_STATUSES:
        raise ValueError(f"unsupported evidence status: {candidate.source_id}")


def _source_row(candidate: SourceCandidate, *, now: str) -> dict[str, Any]:
    _validate_candidate(candidate)
    return {
        "source_id": candidate.source_id,
        "source_category": candidate.category,
        "source_name": candidate.source_name,
        "source_path": candidate.source_ref,
        "source_ref": candidate.source_ref,
        "source_type": candidate.source_type,
        "source_hash": None,
        "source_hash_kind": None,
        "source_path_hash": _hash_text(candidate.source_ref),
        "source_repo": candidate.source_repo,
        "source_owner": "cassandra_chief_memory_authority_dry_run",
        "owner_scope": candidate.owner_scope,
        "tenant_id": candidate.tenant_id,
        "sensitivity_level": candidate.sensitivity_level,
        "trust_status": candidate.trust_status,
        "evidence_status": candidate.evidence_status,
        "import_status": "dry_run_metadata_only",
        "recommended_fate": candidate.recommended_fate,
        "source_retention_policy": candidate.source_retention_policy,
        "raw_content_policy": candidate.raw_content_policy,
        "allowed_agent_use": candidate.allowed_agent_use,
        "risk_level": candidate.risk_level,
        "why_it_matters": candidate.reason,
        "operator_confirmation_required": _bool_int(candidate.operator_confirmation_required),
        "prompt_2_schema_needed": _bool_int(candidate.prompt_2_schema_needed),
        "import_allowed_in_prompt_2": 0,
        "structured_import_possible_later": _bool_int(candidate.structured_import_possible_later),
        "raw_content_forbidden": 1,
        "raw_content_read": 0,
        "raw_content_imported": 0,
        "old_files_are_truth": 0,
        "no_send_authority": 1,
        "no_runtime_authority": 1,
        "approval_required": 1,
        "redaction_policy": "metadata_only_redacted_refs_no_raw_content",
        "source_reviewed_at": None,
        "created_at": now,
        "updated_at": now,
    }


def seed_cassandra_chief_memory_dry_run_catalog(
    *,
    db_path: str | Path | None = None,
    dry_run_id: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    path = init_cassandra_chief_memory_authority_schema(db_path)
    now = generated_at or utc_now()
    resolved_dry_run_id = dry_run_id or _row_id("ccmemdryrun", AUTHORITY_VERSION, len(SOURCE_CANDIDATES))
    rows = [_source_row(candidate, now=now) for candidate in SOURCE_CANDIDATES]
    conn = sqlite3.connect(path)
    try:
        conn.executemany(
            """
INSERT INTO cassandra_chief_memory_sources (
  source_id, source_category, source_name, source_path, source_ref, source_type,
  source_hash, source_hash_kind, source_path_hash, source_repo, source_owner,
  owner_scope, tenant_id, sensitivity_level, trust_status, evidence_status,
  import_status, recommended_fate, source_retention_policy, raw_content_policy,
  allowed_agent_use, risk_level, why_it_matters, operator_confirmation_required,
  prompt_2_schema_needed, import_allowed_in_prompt_2, structured_import_possible_later,
  raw_content_forbidden, raw_content_read, raw_content_imported, old_files_are_truth,
  no_send_authority, no_runtime_authority, approval_required, redaction_policy,
  source_reviewed_at, created_at, updated_at
) VALUES (
  :source_id, :source_category, :source_name, :source_path, :source_ref, :source_type,
  :source_hash, :source_hash_kind, :source_path_hash, :source_repo, :source_owner,
  :owner_scope, :tenant_id, :sensitivity_level, :trust_status, :evidence_status,
  :import_status, :recommended_fate, :source_retention_policy, :raw_content_policy,
  :allowed_agent_use, :risk_level, :why_it_matters, :operator_confirmation_required,
  :prompt_2_schema_needed, :import_allowed_in_prompt_2, :structured_import_possible_later,
  :raw_content_forbidden, :raw_content_read, :raw_content_imported, :old_files_are_truth,
  :no_send_authority, :no_runtime_authority, :approval_required, :redaction_policy,
  :source_reviewed_at, :created_at, :updated_at
)
ON CONFLICT(source_id) DO UPDATE SET
  source_category = excluded.source_category,
  source_name = excluded.source_name,
  source_path = excluded.source_path,
  source_ref = excluded.source_ref,
  source_type = excluded.source_type,
  source_hash = excluded.source_hash,
  source_hash_kind = excluded.source_hash_kind,
  source_path_hash = excluded.source_path_hash,
  source_repo = excluded.source_repo,
  source_owner = excluded.source_owner,
  owner_scope = excluded.owner_scope,
  tenant_id = excluded.tenant_id,
  sensitivity_level = excluded.sensitivity_level,
  trust_status = excluded.trust_status,
  evidence_status = excluded.evidence_status,
  import_status = excluded.import_status,
  recommended_fate = excluded.recommended_fate,
  source_retention_policy = excluded.source_retention_policy,
  raw_content_policy = excluded.raw_content_policy,
  allowed_agent_use = excluded.allowed_agent_use,
  risk_level = excluded.risk_level,
  why_it_matters = excluded.why_it_matters,
  operator_confirmation_required = excluded.operator_confirmation_required,
  prompt_2_schema_needed = excluded.prompt_2_schema_needed,
  import_allowed_in_prompt_2 = excluded.import_allowed_in_prompt_2,
  structured_import_possible_later = excluded.structured_import_possible_later,
  raw_content_forbidden = excluded.raw_content_forbidden,
  raw_content_read = excluded.raw_content_read,
  raw_content_imported = excluded.raw_content_imported,
  old_files_are_truth = excluded.old_files_are_truth,
  no_send_authority = excluded.no_send_authority,
  no_runtime_authority = excluded.no_runtime_authority,
  approval_required = excluded.approval_required,
  redaction_policy = excluded.redaction_policy,
  source_reviewed_at = excluded.source_reviewed_at,
  updated_at = excluded.updated_at
""".strip(),
            rows,
        )
        conn.execute(
            """
INSERT INTO cassandra_chief_memory_dry_run_reviews (
  dry_run_id, dry_run_version, created_at, source_count, data_import_allowed,
  raw_file_ingest_allowed, old_files_are_truth, repo_b_execution_allowed,
  send_allowed, runtime_authority, operator_review_packet_created, notes
) VALUES (?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 1, ?)
ON CONFLICT(dry_run_id) DO UPDATE SET
  dry_run_version = excluded.dry_run_version,
  created_at = excluded.created_at,
  source_count = excluded.source_count,
  data_import_allowed = excluded.data_import_allowed,
  raw_file_ingest_allowed = excluded.raw_file_ingest_allowed,
  old_files_are_truth = excluded.old_files_are_truth,
  repo_b_execution_allowed = excluded.repo_b_execution_allowed,
  send_allowed = excluded.send_allowed,
  runtime_authority = excluded.runtime_authority,
  operator_review_packet_created = excluded.operator_review_packet_created,
  notes = excluded.notes
""".strip(),
            (
                resolved_dry_run_id,
                DRY_RUN_VERSION,
                now,
                len(rows),
                "Metadata-only dry-run. No raw source files were opened, parsed, hashed, or imported.",
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "dry_run_id": resolved_dry_run_id,
        "db_path": _display_path(path),
        "source_count": len(rows),
        **NO_AUTHORITY_FLAGS,
    }


def _dict_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [row[1] for row in rows]


def _table_payloads(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    payloads = []
    for table_name in TABLE_NAMES:
        columns = _table_columns(conn, table_name)
        payloads.append(
            {
                "table_name": table_name,
                "available": bool(columns),
                "columns": columns,
                "required_authority_columns_present": sorted(
                    REQUIRED_AUTHORITY_COLUMNS & set(columns)
                ),
            }
        )
    return payloads


def _counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "unknown") for row in rows).items()))


def _safe_source_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": row["source_id"],
        "category": row["source_category"],
        "source_name": row["source_name"],
        "source_path": row["source_path"],
        "source_ref": row["source_ref"],
        "source_type": row["source_type"],
        "source_hash": row["source_hash"],
        "source_hash_kind": row["source_hash_kind"],
        "source_path_hash": row["source_path_hash"],
        "sensitivity_level": row["sensitivity_level"],
        "trust_status": row["trust_status"],
        "evidence_status": row["evidence_status"],
        "recommended_fate": row["recommended_fate"],
        "canonical_authority_target": _candidate_by_id(row["source_id"]).canonical_authority_target,
        "reason": row["why_it_matters"],
        "risk_level": row["risk_level"],
        "operator_approval_required": bool(row["operator_confirmation_required"]),
        "raw_content_forbidden": bool(row["raw_content_forbidden"]),
        "raw_content_read": bool(row["raw_content_read"]),
        "raw_content_imported": bool(row["raw_content_imported"]),
        "structured_import_possible_later": bool(row["structured_import_possible_later"]),
        "import_allowed_in_prompt_2": bool(row["import_allowed_in_prompt_2"]),
        "old_files_are_truth": bool(row["old_files_are_truth"]),
        "no_send_authority": bool(row["no_send_authority"]),
        "no_runtime_authority": bool(row["no_runtime_authority"]),
        "approval_required": bool(row["approval_required"]),
        "allowed_agent_use": row["allowed_agent_use"],
        "raw_content_policy": row["raw_content_policy"],
        "source_retention_policy": row["source_retention_policy"],
    }


def _candidate_by_id(source_id: str) -> SourceCandidate:
    for candidate in SOURCE_CANDIDATES:
        if candidate.source_id == source_id:
            return candidate
    raise KeyError(source_id)


def _bucket_sources(sources: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets = {
        "safe_to_structure_later": [],
        "keep_as_evidence_source_only": [],
        "block_do_not_trust": [],
        "delete_local_residue_candidate": [],
        "needs_operator_decision": [],
    }
    for source in sources:
        fate = source["recommended_fate"]
        if fate == "import_structured_facts_to_sqlite":
            buckets["safe_to_structure_later"].append(source)
        elif fate in {"register_as_evidence_source_only", "summarize_or_extract_only"}:
            buckets["keep_as_evidence_source_only"].append(source)
        elif fate == "block_no_go":
            buckets["block_do_not_trust"].append(source)
        elif fate == "delete_local_residue":
            buckets["delete_local_residue_candidate"].append(source)
        elif fate == "defer_operator_review":
            buckets["needs_operator_decision"].append(source)
    return buckets


def build_cassandra_chief_memory_authority_read_model(
    *,
    db_path: str | Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    now = generated_at or utc_now()
    seed = seed_cassandra_chief_memory_dry_run_catalog(db_path=db_path, generated_at=now)
    path = init_cassandra_chief_memory_authority_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = _dict_rows(
            conn,
            """
SELECT *
FROM cassandra_chief_memory_sources
ORDER BY source_category, source_id
""".strip(),
        )
        sources = [_safe_source_payload(row) for row in rows]
        tables = _table_payloads(conn)
    finally:
        conn.close()

    counts_by_fate = _counts(rows, "recommended_fate")
    buckets = _bucket_sources(sources)
    blockers = [
        "No raw data import is allowed in this lane.",
        "Old files are not truth.",
        "Old HITL JSON/JSONL cannot approve, execute, or send.",
        "Dirty generated agent_presence snapshots are volatile and not canonical memory.",
        "Untracked polish_loop Cassandra failure tasks remain local residue only.",
    ]
    return {
        "schema_version": AUTHORITY_VERSION,
        "read_model_version": READ_MODEL_VERSION,
        "dry_run_schema_version": DRY_RUN_VERSION,
        "generated_at": now,
        "source_basis": "static_repo_a_memory_authority_spec_and_ready_packet",
        "source_ledger_path": seed["db_path"],
        "source_count": len(sources),
        "import_candidate_count": counts_by_fate.get("import_structured_facts_to_sqlite", 0),
        "blocked_source_count": counts_by_fate.get("block_no_go", 0),
        "deferred_source_count": counts_by_fate.get("defer_operator_review", 0),
        "delete_local_residue_candidate_count": counts_by_fate.get("delete_local_residue", 0),
        "counts_by_category": _counts(rows, "source_category"),
        "counts_by_fate": counts_by_fate,
        "counts_by_sensitivity": _counts(rows, "sensitivity_level"),
        "counts_by_evidence_status": _counts(rows, "evidence_status"),
        "tables": tables,
        "sources": sources,
        "operator_review_buckets": {
            key: [
                {
                    "source_id": item["source_id"],
                    "category": item["category"],
                    "source_name": item["source_name"],
                    "recommended_fate": item["recommended_fate"],
                    "risk_level": item["risk_level"],
                }
                for item in value
            ]
            for key, value in buckets.items()
        },
        "blockers": blockers,
        "recommended_next_lane": "Operator-reviewed Cassandra/Chief structured import plan",
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def build_cassandra_chief_memory_dry_run(
    *,
    db_path: str | Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    authority = build_cassandra_chief_memory_authority_read_model(
        db_path=db_path,
        generated_at=generated_at,
    )
    return {
        "schema_version": DRY_RUN_VERSION,
        "read_model_version": DRY_RUN_VERSION,
        "generated_at": authority["generated_at"],
        "source_basis": authority["source_basis"],
        "source_count": authority["source_count"],
        "counts_by_category": authority["counts_by_category"],
        "counts_by_fate": authority["counts_by_fate"],
        "sources": authority["sources"],
        "operator_review_buckets": authority["operator_review_buckets"],
        "blockers": authority["blockers"],
        "recommended_next_lane": authority["recommended_next_lane"],
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def _count_line(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in counts.items()) or "none"


def format_cassandra_chief_memory_authority_read_model(read_model: dict[str, Any]) -> str:
    lines = [
        "# Cassandra/Chief Memory Authority Read-Model v0",
        "",
        "What this is:",
        "- Metadata-only SQLite schema and source-catalog visibility for Cassandra/Chief memory authority.",
        "",
        "What this is not:",
        "- It is not data import, runtime authority, send authority, Repo B execution, or approval authority.",
        "",
        "Summary:",
        f"- Sources cataloged: {read_model['source_count']}.",
        f"- Structured-fact candidates: {read_model['import_candidate_count']}.",
        f"- Blocked sources: {read_model['blocked_source_count']}.",
        f"- Deferred sources: {read_model['deferred_source_count']}.",
        f"- Delete-residue candidates: {read_model['delete_local_residue_candidate_count']}.",
        f"- Fates: {_count_line(read_model['counts_by_fate'])}.",
        "",
        "Boundary:",
        "- Old files are import candidates or evidence references, not truth.",
        "- Old HITL JSON/JSONL is blocked as active approval authority.",
        "- No raw private contents were imported.",
        "- `send_allowed=false`; `runtime_authority=false`; `repo_b_execution_allowed=false`.",
        "",
        "Next Safe Move:",
        f"- {read_model['recommended_next_lane']}.",
    ]
    return "\n".join(lines) + "\n"


def format_cassandra_chief_memory_dry_run(read_model: dict[str, Any]) -> str:
    lines = [
        "# Cassandra/Chief Memory Import Dry-Run v0",
        "",
        "This is a metadata-only dry-run. No legacy file bodies were opened, parsed, hashed, or imported.",
        "",
        "Fate Summary:",
        f"- {_count_line(read_model['counts_by_fate'])}.",
        "",
        "Categories:",
    ]
    for category, count in read_model["counts_by_category"].items():
        lines.append(f"- {category}: {count}")
    lines.extend(
        [
            "",
            "Blocked Facts:",
            "- Old files are not truth.",
            "- Cassandra/Chief cannot use these sources as authority yet.",
            "- Old HITL JSON cannot approve, execute, or send.",
            "",
            "Next Safe Move:",
            f"- {read_model['recommended_next_lane']}.",
        ]
    )
    return "\n".join(lines) + "\n"


def format_cassandra_chief_memory_operator_review(read_model: dict[str, Any]) -> str:
    buckets = read_model["operator_review_buckets"]

    def bucket_lines(name: str, items: list[dict[str, Any]]) -> list[str]:
        lines = [f"## {name}"]
        if not items:
            return lines + ["- None."]
        return lines + [
            f"- {item['category']}: {item['source_name']} (`{item['recommended_fate']}`, risk={item['risk_level']})"
            for item in items
        ]

    lines = [
        "# Cassandra/Chief Memory Operator Review Packet v0",
        "",
        "Plain-English status:",
        "- We found old Cassandra/Chief memory sources by name and category only.",
        "- No raw data was imported.",
        "- Old files are not truth.",
        "- Cassandra/Chief cannot use these as authority yet.",
        "- Next step is only an operator-approved structured import plan.",
        "",
    ]
    lines.extend(bucket_lines("1. Safe to structure later", buckets["safe_to_structure_later"]))
    lines.append("")
    lines.extend(bucket_lines("2. Keep as evidence source only", buckets["keep_as_evidence_source_only"]))
    lines.append("")
    lines.extend(bucket_lines("3. Block / do not trust", buckets["block_do_not_trust"]))
    lines.append("")
    lines.extend(bucket_lines("4. Delete local residue candidate", buckets["delete_local_residue_candidate"]))
    lines.append("")
    lines.extend(bucket_lines("5. Needs operator decision", buckets["needs_operator_decision"]))
    lines.extend(
        [
            "",
            "Safe next move:",
            "- Review these buckets, then approve only the structured categories that should get a later import lane.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_cassandra_chief_memory_authority_read_model(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    out_root = _export_root_path(export_root)
    out_root.mkdir(parents=True, exist_ok=True)
    authority = build_cassandra_chief_memory_authority_read_model(db_path=db_path)
    dry_run = build_cassandra_chief_memory_dry_run(
        db_path=db_path,
        generated_at=authority["generated_at"],
    )

    authority_json_path = out_root / AUTHORITY_JSON_EXPORT_NAME
    authority_operator_path = out_root / AUTHORITY_OPERATOR_EXPORT_NAME
    dry_run_json_path = out_root / DRY_RUN_JSON_EXPORT_NAME
    dry_run_operator_path = out_root / DRY_RUN_OPERATOR_EXPORT_NAME
    review_path = out_root / OPERATOR_REVIEW_EXPORT_NAME

    authority_json_path.write_text(stable_json(authority), encoding="utf-8")
    authority_operator_path.write_text(
        format_cassandra_chief_memory_authority_read_model(authority),
        encoding="utf-8",
    )
    dry_run_json_path.write_text(stable_json(dry_run), encoding="utf-8")
    dry_run_operator_path.write_text(
        format_cassandra_chief_memory_dry_run(dry_run),
        encoding="utf-8",
    )
    review_path.write_text(
        format_cassandra_chief_memory_operator_review(dry_run),
        encoding="utf-8",
    )
    return {
        "export_version": READ_MODEL_VERSION,
        "authority_json_path": _display_path(authority_json_path),
        "authority_operator_path": _display_path(authority_operator_path),
        "dry_run_json_path": _display_path(dry_run_json_path),
        "dry_run_operator_path": _display_path(dry_run_operator_path),
        "operator_review_path": _display_path(review_path),
        "source_count": authority["source_count"],
        "import_candidate_count": authority["import_candidate_count"],
        "blocked_source_count": authority["blocked_source_count"],
        **NO_AUTHORITY_FLAGS,
    }


__all__ = [
    "ALLOWED_FATES",
    "AUTHORITY_JSON_EXPORT_NAME",
    "AUTHORITY_OPERATOR_EXPORT_NAME",
    "AUTHORITY_VERSION",
    "DEFAULT_EXPORT_ROOT",
    "DRY_RUN_JSON_EXPORT_NAME",
    "DRY_RUN_OPERATOR_EXPORT_NAME",
    "DRY_RUN_VERSION",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_REVIEW_EXPORT_NAME",
    "READ_MODEL_VERSION",
    "REQUIRED_AUTHORITY_COLUMNS",
    "SOURCE_CANDIDATES",
    "TABLE_NAMES",
    "build_cassandra_chief_memory_authority_read_model",
    "build_cassandra_chief_memory_dry_run",
    "cassandra_chief_memory_table_names",
    "export_cassandra_chief_memory_authority_read_model",
    "format_cassandra_chief_memory_authority_read_model",
    "format_cassandra_chief_memory_dry_run",
    "format_cassandra_chief_memory_operator_review",
    "init_cassandra_chief_memory_authority_schema",
    "seed_cassandra_chief_memory_dry_run_catalog",
    "stable_json",
]
