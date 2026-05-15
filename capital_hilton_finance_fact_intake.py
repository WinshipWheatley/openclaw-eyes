"""Capital Hilton finance fact intake v0.

This module attaches Mac spreadsheet metadata, operator-provided invoice facts,
and contact candidates to the governed Capital Hilton finance packet. It never
reads workbook cells, sends email, opens portals, writes ledgers, or treats
unverified finance data as truth.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger
from capital_hilton_invoice_packet import (
    CAPITAL_HILTON_PACKET_ID,
    DEFAULT_ARTIFACT_ROOT,
    build_capital_hilton_invoice_packet,
)
from finance_invoice_evidence_packet import (
    FinancePacketFactInput,
    export_finance_invoice_evidence_packets_read_model,
    init_finance_invoice_evidence_packet_schema,
    stable_json,
)
from telegram_agent_intake import record_telegram_update
from work_board import DEFAULT_BOARD_ID, init_work_board_schema


ROOT = Path(__file__).resolve().parent
FACT_INTAKE_VERSION = "capital_hilton_finance_fact_intake_v0"
DEFAULT_METADATA_PATH = Path("/mnt/e/openclaw/shuttle/from_mac/finance_invoice_spreadsheet_metadata.json")
SELECTED_SPREADSHEET = "Invoice Capitol Hilton 20260512 v2.xlsx"
ALTERNATE_SPREADSHEET = "Invoice Capitol Hilton 20260512.xlsx"
EXTERNAL_PERSONA = "Clara Reid"
INTERNAL_AGENT = "cassandra"

NO_AUTHORITY_FLAGS = {
    "email_send_allowed": False,
    "invoice_send_allowed": False,
    "supplier_portal_login_allowed": False,
    "browser_automation_allowed": False,
    "bank_access_allowed": False,
    "ledger_write_allowed": False,
    "external_api_allowed": False,
    "telegram_send_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "workbook_parsing_allowed": False,
    "spreadsheet_copy_allowed": False,
    "spreadsheet_upload_allowed": False,
    "financial_truth_claimed": False,
    "operator_approval_required": True,
}

CONTACT_CANDIDATES = (
    {
        "contact_name": "Annette Sunga",
        "organization": "Capital Hilton / Capitol Hilton",
        "role": "Finance/AP contact",
        "email": None,
        "confidence": "operator_supplied_candidate",
        "source_basis": "operator_prompt:capital_hilton_cassandra_finance_fact_intake_v0",
        "allowed_use": "email_draft_recipient_candidate_needs_email_review",
        "missing_item": "Annette Sunga email is missing if Annette is selected as To recipient.",
    },
    {
        "contact_name": "Chyna Hardin",
        "organization": "Capital Hilton / Capitol Hilton",
        "role": "Director of Finance",
        "email": "Chyna.Hardin@hilton.com",
        "confidence": "operator_supplied_candidate",
        "source_basis": "operator_prompt:capital_hilton_cassandra_finance_fact_intake_v0",
        "allowed_use": "cc_candidate_pending_review",
        "missing_item": None,
    },
    {
        "contact_name": "Lawrence / Will Valcovic",
        "organization": "Capital Hilton / Capitol Hilton",
        "role": "Hilton contact",
        "email": "lawrencevalcovic@hilton.com",
        "confidence": "operator_supplied_candidate",
        "source_basis": "operator_prompt:capital_hilton_cassandra_finance_fact_intake_v0",
        "allowed_use": "cc_candidate_pending_review",
        "missing_item": None,
    },
)

FACT_FIELD_LABELS = {
    "spreadsheet_selection": "spreadsheet_selection",
    "tonight_gig_date": "tonight_gig_date",
    "last_friday_gig_date": "last_friday_gig_date",
    "rate_or_amount_per_gig": "rate_or_amount_per_gig",
    "invoice_count_preference": "invoice_count_preference",
    "po_numbers": "po_numbers",
    "billing_remit_details": "billing_remit_details",
    "recipient_decision": "recipient_cc_decision",
    "supplier_portal_reference": "supplier_portal_reference",
    "invoice_attachment_output_path": "invoice_attachment_output_path",
    "send_to_annette": "send_to_annette",
    "cc_chyna": "cc_chyna",
    "cc_lawrence": "cc_lawrence",
}

MISSING_ITEM_DELETE_PATTERNS = {
    "spreadsheet_selection": (
        "Mac invoice spreadsheet filename%",
        "Mac invoice spreadsheet exact filename%",
    ),
    "tonight_gig_date": ("Exact date for tonight's gig%",),
    "last_friday_gig_date": ("Exact date for last Friday's gig%",),
    "rate_or_amount_per_gig": ("Amount or rate per gig%",),
    "invoice_count_preference": ("One invoice versus two invoices%",),
    "po_numbers": ("PO number(s)%",),
    "billing_remit_details": ("Billing/remit details%",),
    "recipient_decision": ("Recipient and CC decision%",),
    "supplier_portal_reference": ("Supplier portal reference%",),
    "invoice_attachment_output_path": ("Invoice attachment/output path%",),
}


@dataclass(frozen=True)
class CapitalHiltonFactIntakeResult:
    run_id: str
    db_path: str
    packet_id: str
    spreadsheet_metadata_ingested: bool
    selected_spreadsheet_candidate: str | None
    contact_candidate_count: int
    fact_update_count: int
    missing_fact_count: int
    work_board_card_count: int
    draft_email_path: str
    portal_prompt_path: str
    packet_status: str
    telegram_update_record_id: str | None
    financial_truth_claimed: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _bool(value: bool) -> int:
    return 1 if value else 0


def _display_path(path: str | Path) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return path_obj.as_posix()


def _dict_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS capital_hilton_fact_intake_runs (
  run_id TEXT PRIMARY KEY,
  intake_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  packet_id TEXT NOT NULL,
  spreadsheet_metadata_ingested INTEGER NOT NULL DEFAULT 0,
  contact_candidate_count INTEGER NOT NULL DEFAULT 0,
  fact_update_count INTEGER NOT NULL DEFAULT 0,
  missing_fact_count INTEGER NOT NULL DEFAULT 0,
  work_board_card_count INTEGER NOT NULL DEFAULT 0,
  email_send_allowed INTEGER NOT NULL DEFAULT 0,
  invoice_send_allowed INTEGER NOT NULL DEFAULT 0,
  supplier_portal_login_allowed INTEGER NOT NULL DEFAULT 0,
  bank_access_allowed INTEGER NOT NULL DEFAULT 0,
  ledger_write_allowed INTEGER NOT NULL DEFAULT 0,
  telegram_send_allowed INTEGER NOT NULL DEFAULT 0,
  spreadsheet_cell_read_allowed INTEGER NOT NULL DEFAULT 0,
  workbook_parsing_allowed INTEGER NOT NULL DEFAULT 0,
  financial_truth_claimed INTEGER NOT NULL DEFAULT 0,
  notes TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS capital_hilton_spreadsheet_metadata (
  metadata_id TEXT PRIMARY KEY,
  packet_id TEXT NOT NULL,
  source_metadata_path TEXT NOT NULL,
  source_json_hash TEXT NOT NULL,
  filename TEXT NOT NULL,
  extension TEXT,
  size_bytes INTEGER,
  modified_at TEXT,
  created_at_source TEXT,
  absolute_path TEXT,
  selected_candidate INTEGER NOT NULL DEFAULT 0,
  alternate_candidate INTEGER NOT NULL DEFAULT 0,
  operator_selection_status TEXT NOT NULL,
  likely_relevance TEXT,
  relevance_reason TEXT,
  sensitivity_status TEXT NOT NULL,
  ingestion_policy TEXT NOT NULL,
  allowed_use TEXT NOT NULL,
  cell_read_allowed INTEGER NOT NULL DEFAULT 0,
  workbook_parsing_allowed INTEGER NOT NULL DEFAULT 0,
  copied INTEGER NOT NULL DEFAULT 0,
  uploaded INTEGER NOT NULL DEFAULT 0,
  financial_truth_claimed INTEGER NOT NULL DEFAULT 0,
  ingested_at TEXT NOT NULL,
  UNIQUE(packet_id, filename)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS capital_hilton_contact_candidates (
  contact_candidate_id TEXT PRIMARY KEY,
  packet_id TEXT NOT NULL,
  organization TEXT NOT NULL,
  contact_name TEXT NOT NULL,
  role TEXT NOT NULL,
  email TEXT,
  confidence TEXT NOT NULL,
  source_basis TEXT NOT NULL,
  allowed_use TEXT NOT NULL,
  external_send_allowed INTEGER NOT NULL DEFAULT 0,
  operator_approval_required INTEGER NOT NULL DEFAULT 1,
  verified INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(packet_id, contact_name, email)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS capital_hilton_invoice_fact_updates (
  fact_update_id TEXT PRIMARY KEY,
  packet_id TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  source_ref TEXT,
  agent_internal TEXT NOT NULL DEFAULT 'cassandra',
  external_persona TEXT NOT NULL DEFAULT 'Clara Reid',
  field_name TEXT NOT NULL,
  value_text TEXT NOT NULL,
  confidence TEXT NOT NULL,
  truth_status TEXT NOT NULL,
  financial_truth_claimed INTEGER NOT NULL DEFAULT 0,
  raw_sensitive_body_stored INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  UNIQUE(packet_id, field_name, value_text, source_kind)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS capital_hilton_fact_intake_receipts (
  receipt_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  packet_id TEXT NOT NULL,
  receipt_kind TEXT NOT NULL,
  summary TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  send_allowed INTEGER NOT NULL DEFAULT 0,
  financial_truth_claimed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_cap_hilton_spreadsheet_packet ON capital_hilton_spreadsheet_metadata(packet_id)",
        "CREATE INDEX IF NOT EXISTS idx_cap_hilton_contacts_packet ON capital_hilton_contact_candidates(packet_id)",
        "CREATE INDEX IF NOT EXISTS idx_cap_hilton_fact_updates_packet ON capital_hilton_invoice_fact_updates(packet_id)",
    )


def init_capital_hilton_fact_intake_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path or DEFAULT_DB_PATH)
    init_business_ops_ledger(path)
    init_finance_invoice_evidence_packet_schema(path)
    init_work_board_schema(path)
    conn = sqlite3.connect(path)
    try:
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def capital_hilton_fact_intake_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_capital_hilton_fact_intake_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name FROM sqlite_master
WHERE type = 'table' AND name LIKE 'capital_hilton_%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _ensure_packet(path: str) -> None:
    conn = sqlite3.connect(path)
    try:
        row = conn.execute(
            "SELECT 1 FROM finance_invoice_packets WHERE packet_id = ?",
            (CAPITAL_HILTON_PACKET_ID,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        build_capital_hilton_invoice_packet(db_path=path, export_read_model=False)


def _insert_run(conn: sqlite3.Connection, *, run_id: str, now: str) -> None:
    conn.execute(
        """
INSERT INTO capital_hilton_fact_intake_runs (
  run_id, intake_version, created_at, packet_id, notes
) VALUES (?, ?, ?, ?, ?)
ON CONFLICT(run_id) DO UPDATE SET
  intake_version = excluded.intake_version,
  packet_id = excluded.packet_id,
  email_send_allowed = 0,
  invoice_send_allowed = 0,
  supplier_portal_login_allowed = 0,
  bank_access_allowed = 0,
  ledger_write_allowed = 0,
  telegram_send_allowed = 0,
  spreadsheet_cell_read_allowed = 0,
  workbook_parsing_allowed = 0,
  financial_truth_claimed = 0,
  notes = excluded.notes
""".strip(),
        (
            run_id,
            FACT_INTAKE_VERSION,
            now,
            CAPITAL_HILTON_PACKET_ID,
            "Capital Hilton fact intake is governed metadata only; no send, submit, bank, ledger, or workbook parsing authority.",
        ),
    )


def _read_metadata_payload(metadata_path: str | Path) -> tuple[dict[str, Any], str, str]:
    path = Path(metadata_path)
    if not path.exists():
        raise FileNotFoundError(f"spreadsheet metadata packet not found: {path}")
    raw = path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    return payload, raw, hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _candidate_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = payload.get("candidates") or []
    if not isinstance(candidates, list):
        raise ValueError("metadata packet candidates must be a list")
    return [candidate for candidate in candidates if isinstance(candidate, dict)]


def _selected_candidate(candidates: list[dict[str, Any]], selected_filename: str) -> dict[str, Any] | None:
    for candidate in candidates:
        if candidate.get("filename") == selected_filename:
            return candidate
    return None


def _insert_finance_fact(
    conn: sqlite3.Connection,
    *,
    label: str,
    value_text: str,
    source_ref: str | None,
    truth_status: str = "unverified_claim",
    confidence: str = "operator_claim",
    now: str,
) -> None:
    if not value_text:
        return
    conn.execute(
        """
INSERT OR REPLACE INTO finance_invoice_packet_facts (
  fact_id, packet_id, fact_kind, label, value_text, amount_value,
  currency, date_or_period, confidence, truth_status, source_ref,
  no_raw_sensitive_body, financial_truth_claimed, created_at
) VALUES (?, ?, 'operator_supplied', ?, ?, NULL, NULL, NULL, ?, ?, ?, 1, 0, ?)
""".strip(),
        (
            _row_id("finpktfact", CAPITAL_HILTON_PACKET_ID, label, value_text),
            CAPITAL_HILTON_PACKET_ID,
            label,
            value_text[:800],
            confidence,
            truth_status,
            source_ref,
            now,
        ),
    )


def _record_fact_update(
    conn: sqlite3.Connection,
    *,
    field_name: str,
    value_text: str,
    source_kind: str,
    source_ref: str | None,
    truth_status: str,
    now: str,
) -> int:
    if not value_text:
        return 0
    conn.execute(
        """
INSERT OR REPLACE INTO capital_hilton_invoice_fact_updates (
  fact_update_id, packet_id, source_kind, source_ref, agent_internal,
  external_persona, field_name, value_text, confidence, truth_status,
  financial_truth_claimed, raw_sensitive_body_stored, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'operator_claim', ?, 0, 0, ?)
""".strip(),
        (
            _row_id("capfact", CAPITAL_HILTON_PACKET_ID, field_name, value_text, source_kind),
            CAPITAL_HILTON_PACKET_ID,
            source_kind,
            source_ref,
            INTERNAL_AGENT,
            EXTERNAL_PERSONA,
            field_name,
            value_text[:800],
            truth_status,
            now,
        ),
    )
    _insert_finance_fact(
        conn,
        label=FACT_FIELD_LABELS.get(field_name, field_name),
        value_text=value_text,
        source_ref=source_ref,
        truth_status=truth_status,
        now=now,
    )
    return 1


def _delete_satisfied_missing_items(conn: sqlite3.Connection, field_name: str) -> None:
    for pattern in MISSING_ITEM_DELETE_PATTERNS.get(field_name, ()):
        conn.execute(
            """
DELETE FROM finance_invoice_packet_missing_items
WHERE packet_id = ? AND description LIKE ?
""".strip(),
            (CAPITAL_HILTON_PACKET_ID, pattern),
        )


def _insert_missing_item(
    conn: sqlite3.Connection,
    *,
    description: str,
    why_needed: str,
    blocker_level: str,
    next_safe_move: str,
    now: str,
) -> None:
    conn.execute(
        """
INSERT OR REPLACE INTO finance_invoice_packet_missing_items (
  missing_item_id, packet_id, description, why_needed,
  blocker_level, next_safe_move, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?)
""".strip(),
        (
            _row_id("finpktmiss", CAPITAL_HILTON_PACKET_ID, description),
            CAPITAL_HILTON_PACKET_ID,
            description,
            why_needed,
            blocker_level,
            next_safe_move,
            now,
        ),
    )


def _upsert_spreadsheet_evidence_link(
    conn: sqlite3.Connection,
    *,
    selected: dict[str, Any] | None,
    metadata_path: str | Path,
    now: str,
) -> None:
    filename = selected.get("filename") if selected else SELECTED_SPREADSHEET
    likely_path = selected.get("absolute_path") if selected else f"~/Documents/invoices/{filename}"
    evidence_id = _row_id("finpktev", CAPITAL_HILTON_PACKET_ID, "selected_spreadsheet_metadata", filename)
    conn.execute(
        """
INSERT OR REPLACE INTO finance_invoice_packet_evidence_links (
  evidence_id, packet_id, source_kind, source_ref, likely_path,
  allowed_use, sensitivity_status, ingestion_policy, cell_read_allowed,
  raw_body_read_allowed, workbook_parsing_allowed, created_at
) VALUES (?, ?, 'mac_local_spreadsheet_candidate', ?, ?,
  'metadata_only_pending_review', 'sensitive_metadata_only',
  'needs_operator_review', 0, 0, 0, ?)
""".strip(),
        (
            evidence_id,
            CAPITAL_HILTON_PACKET_ID,
            f"mac_metadata_packet:{metadata_path}",
            likely_path,
            now,
        ),
    )


def ingest_finance_spreadsheet_metadata(
    *,
    db_path: str | Path | None = None,
    metadata_path: str | Path = DEFAULT_METADATA_PATH,
    selected_filename: str = SELECTED_SPREADSHEET,
    run_id: str | None = None,
    update_artifacts: bool = True,
    export_read_model: bool = True,
    read_model_export_root: str | Path = "generated/read_models",
) -> CapitalHiltonFactIntakeResult:
    path = init_capital_hilton_fact_intake_schema(db_path)
    _ensure_packet(path)
    now = utc_now()
    payload, _raw, json_hash = _read_metadata_payload(metadata_path)
    candidates = _candidate_rows(payload)
    selected = _selected_candidate(candidates, selected_filename)
    resolved_run_id = run_id or _row_id("capfinrun", "spreadsheet_metadata", json_hash, now)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        _insert_run(conn, run_id=resolved_run_id, now=now)
        for candidate in candidates:
            filename = str(candidate.get("filename") or "")
            if not filename:
                continue
            is_selected = filename == selected_filename
            is_alternate = filename == ALTERNATE_SPREADSHEET
            conn.execute(
                """
INSERT INTO capital_hilton_spreadsheet_metadata (
  metadata_id, packet_id, source_metadata_path, source_json_hash,
  filename, extension, size_bytes, modified_at, created_at_source,
  absolute_path, selected_candidate, alternate_candidate,
  operator_selection_status, likely_relevance, relevance_reason,
  sensitivity_status, ingestion_policy, allowed_use,
  cell_read_allowed, workbook_parsing_allowed, copied, uploaded,
  financial_truth_claimed, ingested_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, ?)
ON CONFLICT(packet_id, filename) DO UPDATE SET
  source_metadata_path = excluded.source_metadata_path,
  source_json_hash = excluded.source_json_hash,
  extension = excluded.extension,
  size_bytes = excluded.size_bytes,
  modified_at = excluded.modified_at,
  created_at_source = excluded.created_at_source,
  absolute_path = excluded.absolute_path,
  selected_candidate = excluded.selected_candidate,
  alternate_candidate = excluded.alternate_candidate,
  operator_selection_status = excluded.operator_selection_status,
  likely_relevance = excluded.likely_relevance,
  relevance_reason = excluded.relevance_reason,
  sensitivity_status = excluded.sensitivity_status,
  ingestion_policy = excluded.ingestion_policy,
  allowed_use = excluded.allowed_use,
  cell_read_allowed = 0,
  workbook_parsing_allowed = 0,
  copied = 0,
  uploaded = 0,
  financial_truth_claimed = 0,
  ingested_at = excluded.ingested_at
""".strip(),
                (
                    _row_id("capxls", CAPITAL_HILTON_PACKET_ID, filename),
                    CAPITAL_HILTON_PACKET_ID,
                    str(metadata_path),
                    json_hash,
                    filename,
                    candidate.get("extension"),
                    candidate.get("size_bytes"),
                    candidate.get("modified_at"),
                    candidate.get("created_at"),
                    candidate.get("absolute_path"),
                    _bool(is_selected),
                    _bool(is_alternate),
                    "operator_selected_v2" if is_selected else "alternate_candidate" if is_alternate else "metadata_candidate",
                    candidate.get("likely_relevance"),
                    candidate.get("relevance_reason"),
                    "sensitive_metadata_only",
                    "needs_operator_review",
                    "metadata_only_pending_review",
                    now,
                ),
            )
        if selected:
            _upsert_spreadsheet_evidence_link(conn, selected=selected, metadata_path=metadata_path, now=now)
            _record_fact_update(
                conn,
                field_name="spreadsheet_selection",
                value_text=selected_filename,
                source_kind="operator_prompt",
                source_ref=f"mac_metadata_packet:{metadata_path}",
                truth_status="operator_confirmed",
                now=now,
            )
            _delete_satisfied_missing_items(conn, "spreadsheet_selection")
        else:
            _insert_missing_item(
                conn,
                description=f"Selected spreadsheet `{selected_filename}` was not found in the Mac metadata packet.",
                why_needed="The operator selected a workbook by name, but the metadata packet must contain that filename before OpenClaw can link it.",
                blocker_level="blocks_invoice_draft",
                next_safe_move="Re-run Mac Finance Spreadsheet Evidence Intake v0 or confirm the exact filename.",
                now=now,
            )
        conn.execute(
            """
UPDATE finance_invoice_packets
SET status = 'blocked_missing_info',
    next_safe_move = ?,
    financial_truth_claimed = 0,
    send_allowed = 0,
    updated_at = ?
WHERE packet_id = ?
""".strip(),
            (
                "Spreadsheet metadata is attached as sensitive metadata only; operator still needs dates, amount/rate, invoice grouping, PO, recipient, portal reference, and attachment path.",
                now,
                CAPITAL_HILTON_PACKET_ID,
            ),
        )
        _insert_receipt(
            conn,
            run_id=resolved_run_id,
            receipt_kind="spreadsheet_metadata_ingest",
            summary="Mac spreadsheet metadata JSON was ingested without reading workbook cells.",
            payload={
                "metadata_path": str(metadata_path),
                "candidate_count": len(candidates),
                "selected_candidate": selected_filename if selected else None,
                "cell_read_allowed": False,
                "workbook_parsing_allowed": False,
                "copied": False,
                "uploaded": False,
            },
            now=now,
        )
        card_count = _upsert_work_board_cards(conn, now=now)
        missing_count = _missing_count(conn)
        conn.execute(
            """
UPDATE capital_hilton_fact_intake_runs
SET completed_at = ?, spreadsheet_metadata_ingested = ?,
    fact_update_count = (
      SELECT COUNT(*) FROM capital_hilton_invoice_fact_updates WHERE packet_id = ?
    ),
    missing_fact_count = ?, work_board_card_count = ?,
    financial_truth_claimed = 0
WHERE run_id = ?
""".strip(),
            (utc_now(), _bool(bool(selected)), CAPITAL_HILTON_PACKET_ID, missing_count, card_count, resolved_run_id),
        )
        conn.commit()
    finally:
        conn.close()

    return _finalize_result(
        db_path=path,
        run_id=resolved_run_id,
        update_artifacts=update_artifacts,
        export_read_model=export_read_model,
        read_model_export_root=read_model_export_root,
        telegram_update_record_id=None,
    )


def seed_capital_hilton_contact_candidates(
    *,
    db_path: str | Path | None = None,
    run_id: str | None = None,
    update_artifacts: bool = True,
    export_read_model: bool = True,
    read_model_export_root: str | Path = "generated/read_models",
) -> CapitalHiltonFactIntakeResult:
    path = init_capital_hilton_fact_intake_schema(db_path)
    _ensure_packet(path)
    now = utc_now()
    resolved_run_id = run_id or _row_id("capfinrun", "contacts", now)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        _insert_run(conn, run_id=resolved_run_id, now=now)
        _seed_contacts(conn, now=now)
        _insert_receipt(
            conn,
            run_id=resolved_run_id,
            receipt_kind="contact_candidate_seed",
            summary="Capital Hilton contact candidates were stored for operator review only.",
            payload={"contact_candidate_count": len(CONTACT_CANDIDATES), "external_send_allowed": False},
            now=now,
        )
        card_count = _upsert_work_board_cards(conn, now=now)
        conn.execute(
            """
UPDATE capital_hilton_fact_intake_runs
SET completed_at = ?, contact_candidate_count = ?,
    missing_fact_count = ?, work_board_card_count = ?,
    financial_truth_claimed = 0
WHERE run_id = ?
""".strip(),
            (utc_now(), len(CONTACT_CANDIDATES), _missing_count(conn), card_count, resolved_run_id),
        )
        conn.commit()
    finally:
        conn.close()
    return _finalize_result(
        db_path=path,
        run_id=resolved_run_id,
        update_artifacts=update_artifacts,
        export_read_model=export_read_model,
        read_model_export_root=read_model_export_root,
        telegram_update_record_id=None,
    )


def ingest_capital_hilton_invoice_facts(
    *,
    db_path: str | Path | None = None,
    facts: dict[str, str | bool | None] | None = None,
    source_kind: str = "operator_prompt",
    source_ref: str | None = "operator_prompt:capital_hilton_cassandra_finance_fact_intake_v0",
    source_text: str | None = None,
    source_channel: str = "cassandra_listener",
    run_id: str | None = None,
    seed_contacts: bool = True,
    update_artifacts: bool = True,
    export_read_model: bool = True,
    read_model_export_root: str | Path = "generated/read_models",
) -> CapitalHiltonFactIntakeResult:
    path = init_capital_hilton_fact_intake_schema(db_path)
    _ensure_packet(path)
    now = utc_now()
    resolved_facts = facts or {}
    text_for_intake = source_text or _facts_to_message(resolved_facts)
    telegram_update_id: str | None = None
    if source_kind in {"telegram_cassandra", "cassandra_governed_intake"} and text_for_intake:
        result = record_telegram_update(
            text=text_for_intake,
            source_channel=source_channel,
            agent_target=INTERNAL_AGENT,
            source_user_label="operator",
            operator_message=True,
            route_intent=True,
            create_work_board_card=False,
            db_path=path,
        )
        telegram_update_id = result.update_record_id
        source_ref = f"telegram_agent_update:{telegram_update_id}"

    resolved_run_id = run_id or _row_id("capfinrun", "facts", source_ref or "", now)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    fact_count = 0
    try:
        _insert_run(conn, run_id=resolved_run_id, now=now)
        if seed_contacts:
            _seed_contacts(conn, now=now)
        for field_name, raw_value in resolved_facts.items():
            value_text = _fact_value_to_text(raw_value)
            if not value_text:
                continue
            fact_count += _record_fact_update(
                conn,
                field_name=field_name,
                value_text=value_text,
                source_kind=source_kind,
                source_ref=source_ref,
                truth_status="operator_confirmed" if field_name == "spreadsheet_selection" else "unverified_claim",
                now=now,
            )
            _delete_satisfied_missing_items(conn, field_name)
        _insert_receipt(
            conn,
            run_id=resolved_run_id,
            receipt_kind="operator_fact_intake",
            summary="Capital Hilton operator facts were stored in governed finance packet tables; no send or execution occurred.",
            payload={
                "fact_fields": sorted(key for key, value in resolved_facts.items() if _fact_value_to_text(value)),
                "source_kind": source_kind,
                "source_ref": source_ref,
                "telegram_update_record_id": telegram_update_id,
                "financial_truth_claimed": False,
            },
            now=now,
        )
        card_count = _upsert_work_board_cards(conn, now=now)
        missing_count = _missing_count(conn)
        conn.execute(
            """
UPDATE capital_hilton_fact_intake_runs
SET completed_at = ?, contact_candidate_count = (
      SELECT COUNT(*) FROM capital_hilton_contact_candidates WHERE packet_id = ?
    ),
    fact_update_count = ?, missing_fact_count = ?,
    work_board_card_count = ?, financial_truth_claimed = 0
WHERE run_id = ?
""".strip(),
            (utc_now(), CAPITAL_HILTON_PACKET_ID, fact_count, missing_count, card_count, resolved_run_id),
        )
        conn.commit()
    finally:
        conn.close()
    return _finalize_result(
        db_path=path,
        run_id=resolved_run_id,
        update_artifacts=update_artifacts,
        export_read_model=export_read_model,
        read_model_export_root=read_model_export_root,
        telegram_update_record_id=telegram_update_id,
    )


def _fact_value_to_text(value: str | bool | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else ""
    return str(value).strip()


def _facts_to_message(facts: dict[str, str | bool | None]) -> str:
    parts = []
    for key in sorted(facts):
        value = _fact_value_to_text(facts[key])
        if value:
            parts.append(f"{key}: {value}")
    if not parts:
        return "Clara, Capital Hilton invoice fact update."
    return "Clara, Capital Hilton invoice fact update. " + "; ".join(parts)


def _seed_contacts(conn: sqlite3.Connection, *, now: str) -> None:
    for contact in CONTACT_CANDIDATES:
        conn.execute(
            """
INSERT OR REPLACE INTO capital_hilton_contact_candidates (
  contact_candidate_id, packet_id, organization, contact_name, role, email,
  confidence, source_basis, allowed_use, external_send_allowed,
  operator_approval_required, verified, created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, 0, ?, ?)
""".strip(),
            (
                _row_id("capcontact", CAPITAL_HILTON_PACKET_ID, contact["contact_name"], contact.get("email") or "unknown"),
                CAPITAL_HILTON_PACKET_ID,
                contact["organization"],
                contact["contact_name"],
                contact["role"],
                contact.get("email"),
                contact["confidence"],
                contact["source_basis"],
                contact["allowed_use"],
                now,
                now,
            ),
        )
        _insert_finance_fact(
            conn,
            label=f"contact_candidate_{contact['contact_name'].lower().replace(' ', '_').replace('/', '_')}",
            value_text=f"{contact['contact_name']} | {contact['role']} | email={contact.get('email') or 'unknown'} | allowed_use={contact['allowed_use']}",
            source_ref=contact["source_basis"],
            truth_status="needs_review",
            confidence="operator_claim",
            now=now,
        )
        if contact.get("missing_item"):
            _insert_missing_item(
                conn,
                description=contact["missing_item"],
                why_needed="The packet cannot use Annette as the final To recipient until the exact email address is operator-confirmed or evidence-backed.",
                blocker_level="blocks_send",
                next_safe_move="Operator confirms Annette Sunga's email or chooses a different reviewed recipient.",
                now=now,
            )
    _insert_finance_fact(
        conn,
        label="supplier_portal_candidate",
        value_text="SmartSpend / Coupa previously associated with this supplier flow; needs operator review for this invoice.",
        source_ref="operator_prompt:capital_hilton_cassandra_finance_fact_intake_v0",
        truth_status="needs_review",
        confidence="operator_claim",
        now=now,
    )
    _insert_finance_fact(
        conn,
        label="operator_remit_email_candidate",
        value_text="winshiplive@gmail.com",
        source_ref="operator_prompt:capital_hilton_cassandra_finance_fact_intake_v0",
        truth_status="needs_review",
        confidence="operator_claim",
        now=now,
    )


def _insert_receipt(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    receipt_kind: str,
    summary: str,
    payload: dict[str, Any],
    now: str,
) -> None:
    conn.execute(
        """
INSERT OR REPLACE INTO capital_hilton_fact_intake_receipts (
  receipt_id, run_id, packet_id, receipt_kind, summary, payload_json,
  execution_allowed, send_allowed, financial_truth_claimed, created_at
) VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, ?)
""".strip(),
        (
            _row_id("capfinreceipt", run_id, receipt_kind),
            run_id,
            CAPITAL_HILTON_PACKET_ID,
            receipt_kind,
            summary,
            stable_json({**payload, **NO_AUTHORITY_FLAGS}),
            now,
        ),
    )


def _upsert_work_board_cards(conn: sqlite3.Connection, *, now: str) -> int:
    board_id = DEFAULT_BOARD_ID
    conn.execute(
        """
INSERT INTO work_boards (
  board_id, board_name, board_version, description, created_at, updated_at,
  direct_execution_allowed, auto_approval_allowed, auto_execute_allowed,
  agent_activation_allowed
) VALUES (?, 'OpenClaw Work Board', 'openclaw_work_board_v0', ?, ?, ?, 0, 0, 0, 0)
ON CONFLICT(board_id) DO UPDATE SET updated_at = excluded.updated_at
""".strip(),
        (board_id, "Local review board over OpenClaw control-plane metadata, including Capital Hilton finance intake.", now, now),
    )
    specs = (
        (
            "capital_hilton_fact_intake:missing_facts",
            "Capital Hilton invoice facts needed from operator/Clara",
            "Capital Hilton packet has governed intake, but dates, rate/amount, invoice grouping, PO, recipient decision, portal reference, and attachment path remain pending unless explicitly supplied.",
            "needs_review",
            "missing_invoice_facts",
            "Message Clara/Cassandra with the structured Capital Hilton facts or use the CLI fallback.",
        ),
        (
            "capital_hilton_fact_intake:v2_spreadsheet_selected",
            "Capital Hilton v2 spreadsheet selected, metadata only",
            f"{SELECTED_SPREADSHEET} is selected as sensitive metadata only. No workbook cells were read or copied.",
            "planned",
            "spreadsheet_metadata_attached",
            "Use selected spreadsheet only as metadata until a future approved Mac workbook intake authorizes more.",
        ),
        (
            "capital_hilton_fact_intake:contact_review",
            "Capital Hilton recipient/contact review needed",
            "Annette, Chyna, and Lawrence/Will are stored as contact candidates only; Annette email is still missing.",
            "needs_review",
            "contact_candidates_pending_review",
            "Operator confirms To/CC list and Annette email before any external draft is used.",
        ),
        (
            "capital_hilton_fact_intake:portal_prompt_pending",
            "Capital Hilton portal-fill prompt pending facts/approval",
            "Portal prompt remains no-submit and should stop if PO/date/amount/attachment is missing.",
            "needs_review",
            "portal_prompt_waiting_for_facts",
            "Fill missing facts first; no browser, portal login, upload, save, or submit is authorized.",
        ),
    )
    for source_id, title, summary, column, status, next_safe_move in specs:
        card_id = _row_id("wbcard", board_id, "manual_seed", source_id)
        conn.execute(
            """
INSERT INTO work_board_cards (
  card_id, board_id, title, summary, source_kind, source_id, world_hint,
  agent_id, lane_id, intent_category, board_column, status, priority_hint,
  approval_required, execution_allowed, action_request_id, work_packet_id,
  receipt_id, blocker_reason, next_safe_move, evidence_basis, created_at,
  updated_at, raw_body_stored, direct_execution_allowed, arbitrary_shell_allowed,
  auto_approval_allowed, auto_execute_allowed, agent_activation_allowed,
  model_call_allowed, tool_execution_allowed, network_authority,
  no_go_raw_access_allowed, file_move_allowed, file_delete_allowed,
  client_deployment_allowed
) VALUES (?, ?, ?, ?, 'manual_seed', ?, 'finance', 'cassandra',
  'operator_comms', 'capital_hilton_invoice_fact_update', ?, ?, 'high',
  1, 0, NULL, NULL, NULL, NULL, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
ON CONFLICT(board_id, source_kind, source_id) DO UPDATE SET
  title = excluded.title,
  summary = excluded.summary,
  world_hint = excluded.world_hint,
  agent_id = excluded.agent_id,
  lane_id = excluded.lane_id,
  intent_category = excluded.intent_category,
  board_column = excluded.board_column,
  status = excluded.status,
  approval_required = 1,
  execution_allowed = 0,
  next_safe_move = excluded.next_safe_move,
  evidence_basis = excluded.evidence_basis,
  updated_at = excluded.updated_at,
  raw_body_stored = 0,
  direct_execution_allowed = 0,
  arbitrary_shell_allowed = 0,
  auto_approval_allowed = 0,
  auto_execute_allowed = 0,
  agent_activation_allowed = 0,
  model_call_allowed = 0,
  tool_execution_allowed = 0,
  network_authority = 0,
  no_go_raw_access_allowed = 0,
  file_move_allowed = 0,
  file_delete_allowed = 0,
  client_deployment_allowed = 0
""".strip(),
            (card_id, board_id, title, summary, source_id, column, status, next_safe_move, "capital_hilton_finance_fact_intake", now, now),
        )
        conn.execute(
            """
INSERT OR REPLACE INTO work_board_card_sources (
  card_source_id, card_id, source_kind, source_id, source_path,
  source_summary, raw_body_stored, created_at
) VALUES (?, ?, 'manual_seed', ?, NULL, ?, 0, ?)
""".strip(),
            (_row_id("wbsrc", card_id, source_id), card_id, source_id, summary, now),
        )
        conn.execute(
            """
INSERT OR REPLACE INTO work_board_card_agents (
  card_agent_id, card_id, agent_id, lane_id, role,
  can_execute, can_bypass_approval, created_at
) VALUES (?, ?, 'cassandra', 'operator_comms', 'assigned_lane', 0, 0, ?)
""".strip(),
            (_row_id("wbagent", card_id, "cassandra"), card_id, now),
        )
        conn.execute(
            """
INSERT OR REPLACE INTO work_board_card_worlds (
  card_world_id, card_id, world_hint, confidence, created_at
) VALUES (?, ?, 'finance', 'metadata_hint', ?)
""".strip(),
            (_row_id("wbworld", card_id, "finance"), card_id, now),
        )
    return len(specs)


def _missing_count(conn: sqlite3.Connection) -> int:
    return int(
        conn.execute(
            "SELECT COUNT(*) AS count FROM finance_invoice_packet_missing_items WHERE packet_id = ?",
            (CAPITAL_HILTON_PACKET_ID,),
        ).fetchone()["count"]
    )


def _packet_status(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT status FROM finance_invoice_packets WHERE packet_id = ?",
        (CAPITAL_HILTON_PACKET_ID,),
    ).fetchone()
    return row["status"] if row else "unknown"


def _latest_selected_spreadsheet(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute(
        """
SELECT * FROM capital_hilton_spreadsheet_metadata
WHERE packet_id = ? AND selected_candidate = 1
ORDER BY ingested_at DESC
LIMIT 1
""".strip(),
        (CAPITAL_HILTON_PACKET_ID,),
    ).fetchone()
    return dict(row) if row else None


def _contact_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return _dict_rows(
        conn,
        """
SELECT * FROM capital_hilton_contact_candidates
WHERE packet_id = ?
ORDER BY contact_name
""".strip(),
        (CAPITAL_HILTON_PACKET_ID,),
    )


def _missing_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return _dict_rows(
        conn,
        """
SELECT description, blocker_level, next_safe_move
FROM finance_invoice_packet_missing_items
WHERE packet_id = ?
ORDER BY CASE blocker_level WHEN 'blocks_packet' THEN 0 WHEN 'blocks_invoice_draft' THEN 1 WHEN 'blocks_send' THEN 2 ELSE 3 END,
         description
""".strip(),
        (CAPITAL_HILTON_PACKET_ID,),
    )


def _render_draft_email(conn: sqlite3.Connection) -> str:
    contacts = _contact_rows(conn)
    chyna = next((row for row in contacts if row["contact_name"] == "Chyna Hardin"), None)
    lawrence = next((row for row in contacts if row["contact_name"] == "Lawrence / Will Valcovic"), None)
    cc_parts = [row["email"] for row in (chyna, lawrence) if row and row.get("email")]
    cc_line = "; ".join(cc_parts) if cc_parts else "[MISSING - confirm CC]"
    selected = _latest_selected_spreadsheet(conn)
    selected_line = selected["filename"] if selected else "[MISSING - confirm spreadsheet selection]"
    return f"""# Capital Hilton Draft Email - Review Only, Do Not Send

To: [MISSING - confirm Annette Sunga email or alternate recipient]
CC: [PENDING REVIEW - {cc_line}]
From/Remit email context: winshiplive@gmail.com
External preparer identity: {EXTERNAL_PERSONA}
Subject: Invoice for music services - [CONFIRM DATE(S)]

Hi [CONFIRM NAME],

I am preparing invoice documentation for the Capital Hilton music services and need the final invoice details confirmed before anything is sent or uploaded.

Known metadata-only context:
- Selected invoice workbook candidate: {selected_line}
- Spreadsheet status: sensitive metadata only; no workbook cells have been read.

Missing items to confirm:
- Tonight's gig date: [CONFIRM EXACT DATE]
- Last Friday's gig date: [CONFIRM EXACT DATE]
- Rate/amount per gig: [CONFIRM AMOUNT/RATE]
- One invoice or two: [CONFIRM]
- PO number(s): [CONFIRM OR NONE]
- Correct To/CC recipients: [CONFIRM]
- SmartSpend/Coupa or other portal reference: [CONFIRM]
- Invoice attachment/output path: [CONFIRM]

No total is filled here because the amount/rate is not yet approved.

Best,
{EXTERNAL_PERSONA}

Boundary: This is a draft for operator review only. Do not send, attach, submit, or treat any amount/date/recipient as final until approved.
"""


def _render_portal_prompt(conn: sqlite3.Connection) -> str:
    selected = _latest_selected_spreadsheet(conn)
    selected_line = selected["filename"] if selected else "[MISSING]"
    return f"""# Codex Desktop Prompt - Capital Hilton Portal Fill Prep, No Submit

You are helping prepare a supplier portal invoice entry for Capital Hilton on the Mac/Safari side.

Hard boundaries:
- Do not submit anything.
- Do not send email.
- Do not access bank portals.
- Do not read spreadsheet cells.
- Do not parse workbook sheets.
- Do not upload or copy the spreadsheet unless a later approval explicitly allows it.
- Do not invent dates, amounts, PO numbers, recipient details, or totals.
- Stop before any irreversible action, final save, upload, or submit button.

Approved packet metadata:
- Packet id: {CAPITAL_HILTON_PACKET_ID}
- Selected spreadsheet candidate: {selected_line}
- Spreadsheet use: metadata-only pending review.
- External finance persona for drafts: {EXTERNAL_PERSONA}
- Contact candidates are pending operator review.

Stop immediately if any required field is missing:
- Exact date for tonight's gig.
- Exact date for last Friday's gig.
- Amount/rate per gig.
- One invoice or two.
- PO number(s).
- Billing/remit details.
- Recipient/CC decision.
- Supplier portal reference.
- Invoice attachment/output path.

Fill only after operator supplies approved packet fields. Do not submit until the operator explicitly approves in a later lane.
"""


def _render_receivable_proposal() -> str:
    return f"""# Capital Hilton Receivable Tracking Proposal - Review Only

status: pending_invoice_approval
follow_up_owner_internal: Cassandra
follow_up_external_persona: {EXTERNAL_PERSONA}
follow_up_email_sent: false
invoice_sent: false
payment_tracking_status: not_started

Scope:
- Track the Capital Hilton receivable only after invoice details are approved.
- Do not send follow-up email yet.
- Do not claim payment is due, paid, unpaid, or overdue without approved invoice and payment evidence.
- Payment tracking requires later approved bank/ledger evidence or operator-provided payment confirmation.

Next safe moves:
1. Operator confirms missing invoice facts through governed intake.
2. OpenClaw prepares draft invoice context only.
3. Operator approves send/submission path in a later lane.
4. After approved send/submission, Clara Reid may own follow-up reminders as metadata only until sending is separately approved.
"""


def _render_packet_summary(conn: sqlite3.Connection) -> str:
    selected = _latest_selected_spreadsheet(conn)
    contacts = _contact_rows(conn)
    missing = _missing_rows(conn)
    lines = [
        "# Capital Hilton Invoice Packet v0 - Summary",
        "",
        "Purpose: prepare a reviewable evidence packet for Capital Hilton invoice work without sending anything or making financial truth claims.",
        "",
        f"Packet id: `{CAPITAL_HILTON_PACKET_ID}`",
        f"Internal agent: `{INTERNAL_AGENT}`",
        f"External finance persona: `{EXTERNAL_PERSONA}`",
        "",
        "## Spreadsheet Metadata",
    ]
    if selected:
        lines.extend(
            [
                f"- Selected candidate: `{selected['filename']}`",
                f"- Alternate candidate known: `{ALTERNATE_SPREADSHEET}`",
                f"- Absolute path from Mac metadata: `{selected['absolute_path']}`",
                "- Sensitivity: `sensitive_metadata_only`",
                "- Cell read allowed: `false`",
                "- Workbook parsing allowed: `false`",
                "- Copied/uploaded: `false`",
            ]
        )
    else:
        lines.append("- No selected spreadsheet metadata attached.")
    lines.extend(["", "## Contact Candidates"])
    for contact in contacts:
        lines.append(
            f"- {contact['contact_name']} ({contact['role']}), email={contact['email'] or 'unknown'}, allowed_use={contact['allowed_use']}, confidence={contact['confidence']}"
        )
    if not contacts:
        lines.append("- None.")
    lines.extend(["", "## Missing Facts Remaining"])
    for row in missing:
        lines.append(f"- {row['blocker_level']}: {row['description']} -> {row['next_safe_move']}")
    if not missing:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Boundaries",
            "- No email send.",
            "- No invoice send.",
            "- No supplier portal login or submit.",
            "- No bank access.",
            "- No ledger write.",
            "- No spreadsheet cell read.",
            "- No financial truth claim.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_capital_hilton_fact_intake_artifacts(
    *,
    db_path: str | Path | None = None,
    artifact_root: str | Path = DEFAULT_ARTIFACT_ROOT,
) -> dict[str, str]:
    path = init_capital_hilton_fact_intake_schema(db_path)
    root = Path(artifact_root)
    if not root.is_absolute():
        root = ROOT / root
    root.mkdir(parents=True, exist_ok=True)
    paths = {
        "draft_email": root / "CAPITAL_HILTON_DRAFT_EMAIL_REVIEW_ONLY.md",
        "portal_prompt": root / "CAPITAL_HILTON_PORTAL_FILL_PROMPT_NO_SUBMIT.md",
        "receivable_proposal": root / "CAPITAL_HILTON_RECEIVABLE_TRACKING_PROPOSAL.md",
        "packet_summary": root / "CAPITAL_HILTON_PACKET_SUMMARY.md",
        "manifest": root / "MANIFEST.json",
    }
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        draft = _render_draft_email(conn)
        portal = _render_portal_prompt(conn)
        receivable = _render_receivable_proposal()
        summary = _render_packet_summary(conn)
        paths["draft_email"].write_text(draft, encoding="utf-8")
        paths["portal_prompt"].write_text(portal, encoding="utf-8")
        paths["receivable_proposal"].write_text(receivable, encoding="utf-8")
        paths["packet_summary"].write_text(summary, encoding="utf-8")
        manifest = {
            "schema_version": FACT_INTAKE_VERSION,
            "generated_at": utc_now(),
            "packet_id": CAPITAL_HILTON_PACKET_ID,
            "external_persona": EXTERNAL_PERSONA,
            "internal_agent": INTERNAL_AGENT,
            "files": {key: _display_path(value) for key, value in paths.items() if key != "manifest"},
            "no_authority_flags": NO_AUTHORITY_FLAGS,
        }
        paths["manifest"].write_text(stable_json(manifest), encoding="utf-8")
        now = utc_now()
        outputs = (
            ("capital_hilton_draft_email_review_only", "Draft email body for operator review only", draft, paths["draft_email"]),
            ("capital_hilton_portal_fill_instruction_prompt", "Codex Desktop portal-fill instruction prompt, no submit", portal, paths["portal_prompt"]),
            ("capital_hilton_receivable_tracking_proposal", "Receivable tracking proposal pending invoice approval", receivable, paths["receivable_proposal"]),
            ("capital_hilton_packet_summary", "Capital Hilton packet summary and missing facts", summary, paths["packet_summary"]),
        )
        for output_kind, title, body, file_path in outputs:
            conn.execute(
                """
INSERT OR REPLACE INTO finance_invoice_packet_outputs (
  output_id, packet_id, output_kind, title, body_text,
  send_allowed, invoice_creation_allowed, raw_sensitive_body_included,
  created_at
) VALUES (?, ?, ?, ?, ?, 0, 0, 0, ?)
""".strip(),
                (
                    _row_id("finpktout", CAPITAL_HILTON_PACKET_ID, output_kind),
                    CAPITAL_HILTON_PACKET_ID,
                    output_kind,
                    f"{title} (`{_display_path(file_path)}`)",
                    body,
                    now,
                ),
            )
        conn.commit()
        return {key: _display_path(value) for key, value in paths.items()}
    finally:
        conn.close()


def _finalize_result(
    *,
    db_path: str,
    run_id: str,
    update_artifacts: bool,
    export_read_model: bool,
    read_model_export_root: str | Path,
    telegram_update_record_id: str | None,
) -> CapitalHiltonFactIntakeResult:
    artifacts = (
        write_capital_hilton_fact_intake_artifacts(db_path=db_path)
        if update_artifacts
        else {
            "draft_email": _display_path(DEFAULT_ARTIFACT_ROOT / "CAPITAL_HILTON_DRAFT_EMAIL_REVIEW_ONLY.md"),
            "portal_prompt": _display_path(DEFAULT_ARTIFACT_ROOT / "CAPITAL_HILTON_PORTAL_FILL_PROMPT_NO_SUBMIT.md"),
        }
    )
    if export_read_model:
        export_finance_invoice_evidence_packets_read_model(db_path=db_path, export_root=read_model_export_root)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        selected = _latest_selected_spreadsheet(conn)
        result = CapitalHiltonFactIntakeResult(
            run_id=run_id,
            db_path=db_path,
            packet_id=CAPITAL_HILTON_PACKET_ID,
            spreadsheet_metadata_ingested=bool(selected),
            selected_spreadsheet_candidate=selected["filename"] if selected else None,
            contact_candidate_count=int(conn.execute("SELECT COUNT(*) AS count FROM capital_hilton_contact_candidates WHERE packet_id = ?", (CAPITAL_HILTON_PACKET_ID,)).fetchone()["count"]),
            fact_update_count=int(conn.execute("SELECT COUNT(*) AS count FROM capital_hilton_invoice_fact_updates WHERE packet_id = ?", (CAPITAL_HILTON_PACKET_ID,)).fetchone()["count"]),
            missing_fact_count=_missing_count(conn),
            work_board_card_count=int(conn.execute("SELECT COUNT(*) AS count FROM work_board_cards WHERE source_id LIKE 'capital_hilton_fact_intake:%'").fetchone()["count"]),
            draft_email_path=artifacts["draft_email"],
            portal_prompt_path=artifacts["portal_prompt"],
            packet_status=_packet_status(conn),
            telegram_update_record_id=telegram_update_record_id,
            financial_truth_claimed=False,
        )
        return result
    finally:
        conn.close()


def build_capital_hilton_fact_intake_report(
    *,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    path = init_capital_hilton_fact_intake_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        return {
            "status": "ok",
            "packet_id": CAPITAL_HILTON_PACKET_ID,
            "selected_spreadsheet": _latest_selected_spreadsheet(conn),
            "spreadsheet_candidates": _dict_rows(
                conn,
                "SELECT * FROM capital_hilton_spreadsheet_metadata WHERE packet_id = ? ORDER BY selected_candidate DESC, modified_at DESC",
                (CAPITAL_HILTON_PACKET_ID,),
            ),
            "contact_candidates": _contact_rows(conn),
            "fact_updates": _dict_rows(
                conn,
                "SELECT * FROM capital_hilton_invoice_fact_updates WHERE packet_id = ? ORDER BY field_name",
                (CAPITAL_HILTON_PACKET_ID,),
            ),
            "missing_items": _missing_rows(conn),
            "external_identity_rule": {
                "internal_agent": INTERNAL_AGENT,
                "external_persona": EXTERNAL_PERSONA,
                "draft_signature": f"Best,\n{EXTERNAL_PERSONA}",
            },
            "no_authority_flags": NO_AUTHORITY_FLAGS,
        }
    finally:
        conn.close()


def format_capital_hilton_fact_intake_result(result: CapitalHiltonFactIntakeResult) -> str:
    return "\n".join(
        [
            "Capital Hilton Cassandra Finance Fact Intake v0",
            "",
            f"Packet: `{result.packet_id}`",
            f"Run: `{result.run_id}`",
            f"Spreadsheet metadata ingested: `{str(result.spreadsheet_metadata_ingested).lower()}`",
            f"Selected spreadsheet: `{result.selected_spreadsheet_candidate or 'none'}`",
            f"Contact candidates: {result.contact_candidate_count}",
            f"Fact updates: {result.fact_update_count}",
            f"Missing facts remaining: {result.missing_fact_count}",
            f"Packet status: `{result.packet_status}`",
            f"Draft email: `{result.draft_email_path}`",
            f"Portal prompt: `{result.portal_prompt_path}`",
            f"Telegram update record: `{result.telegram_update_record_id or 'none'}`",
            "",
            "External identity:",
            f"- Internal agent: `{INTERNAL_AGENT}`",
            f"- External finance/AP drafts use: `{EXTERNAL_PERSONA}`",
            "",
            "Boundary:",
            "- No email send, invoice send, portal access, bank access, ledger write, spreadsheet cell read, workbook parsing, or financial truth claim occurred.",
        ]
    )


def format_capital_hilton_fact_intake_report(payload: dict[str, Any]) -> str:
    selected = payload.get("selected_spreadsheet")
    lines = [
        "Capital Hilton Finance Fact Intake v0 - Report",
        "",
        f"Packet: `{payload['packet_id']}`",
        f"Selected spreadsheet: `{selected['filename'] if selected else 'none'}`",
        "",
        "Contact candidates:",
    ]
    for row in payload.get("contact_candidates") or []:
        lines.append(f"- {row['contact_name']} ({row['role']}), email={row['email'] or 'unknown'}, allowed_use={row['allowed_use']}")
    if not payload.get("contact_candidates"):
        lines.append("- none")
    lines.extend(["", "Missing facts remaining:"])
    for row in payload.get("missing_items") or []:
        lines.append(f"- {row['blocker_level']}: {row['description']} -> {row['next_safe_move']}")
    if not payload.get("missing_items"):
        lines.append("- none")
    identity = payload["external_identity_rule"]
    lines.extend(
        [
            "",
            "External identity rule:",
            f"- Internal agent: `{identity['internal_agent']}`",
            f"- External persona: `{identity['external_persona']}`",
            "- Draft signature:",
            "```text",
            identity["draft_signature"],
            "```",
            "",
            "Authority boundary:",
        ]
    )
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`.")
    return "\n".join(lines)


__all__ = [
    "ALTERNATE_SPREADSHEET",
    "CONTACT_CANDIDATES",
    "DEFAULT_METADATA_PATH",
    "EXTERNAL_PERSONA",
    "INTERNAL_AGENT",
    "NO_AUTHORITY_FLAGS",
    "SELECTED_SPREADSHEET",
    "CapitalHiltonFactIntakeResult",
    "build_capital_hilton_fact_intake_report",
    "capital_hilton_fact_intake_table_names",
    "format_capital_hilton_fact_intake_report",
    "format_capital_hilton_fact_intake_result",
    "ingest_capital_hilton_invoice_facts",
    "ingest_finance_spreadsheet_metadata",
    "init_capital_hilton_fact_intake_schema",
    "seed_capital_hilton_contact_candidates",
    "write_capital_hilton_fact_intake_artifacts",
]
