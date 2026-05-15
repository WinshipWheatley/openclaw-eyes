"""Finance Invoice Evidence Packet v0 for OpenClaw.

This module creates governed finance evidence packets for invoice and
receivable work. It is an evidence/context workflow only: it does not send
email, create invoices for sending, access banks, write ledgers, parse
workbooks, read raw sensitive bodies, or claim financial truth.
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
from finance_invoice_reconciliation import init_finance_invoice_reconciliation_schema
from work_board import DEFAULT_BOARD_ID, init_work_board_schema


ROOT = Path(__file__).resolve().parent
FINANCE_PACKET_VERSION = "finance_invoice_evidence_packet_v0"
READ_MODEL_VERSION = "finance_invoice_evidence_packets_read_model_v0"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "finance_invoice_evidence_packets.json"
OPERATOR_EXPORT_NAME = "finance_invoice_evidence_packets_OPERATOR.md"

MAC_SPREADSHEET_FOLDER = "~/Documents/invoices/"
MAC_SPREADSHEET_NEXT_LANE = "Mac Finance Spreadsheet Evidence Intake v0"

WORKFLOW_KINDS = {
    "invoice_prep",
    "receivables_review",
    "reimbursement_review",
    "speaker_rental_review",
    "tech_work_review",
    "unknown",
}

PACKET_STATUSES = {
    "draft",
    "needs_operator_facts",
    "evidence_ready",
    "blocked_missing_info",
    "ready_for_draft_review",
    "completed_packet",
}

FACT_KINDS = {
    "operator_supplied",
    "approved_evidence_reference",
    "calculated_from_approved_evidence",
    "unknown_review",
}

CONFIDENCE_LEVELS = {"operator_claim", "evidence_backed", "calculated", "unknown_review"}
TRUTH_STATUSES = {"unverified_claim", "operator_confirmed", "evidence_backed", "needs_review"}

SOURCE_KINDS = {
    "markdown_evidence",
    "approved_file_metadata",
    "receipt_reference",
    "operator_note",
    "report_bridge_metadata",
    "mac_local_spreadsheet_candidate",
    "unknown_review",
}

ALLOWED_USES = {"cite_in_packet", "summarize_only", "metadata_only", "metadata_only_pending_review", "blocked"}
SENSITIVITY_STATUSES = {"approved_metadata", "bounded_evidence", "sensitive_metadata_only", "blocked_private", "unknown_review"}
INGESTION_POLICIES = {"approved_metadata_only", "approved_bounded_excerpt", "needs_operator_review", "blocked"}

RISK_KINDS = {
    "missing_amount",
    "missing_date",
    "unclear_client",
    "sensitive_data_needed",
    "tax_sensitive",
    "legal_sensitive",
    "bank_data_needed",
    "unsupported_claim",
    "send_not_allowed",
    "spreadsheet_needs_review",
    "unknown",
}

NO_AUTHORITY_FLAGS = {
    "invoice_send_allowed": False,
    "email_send_allowed": False,
    "bank_access_allowed": False,
    "ledger_write_allowed": False,
    "tax_filing_allowed": False,
    "external_api_allowed": False,
    "raw_sensitive_body_ingest_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "workbook_parsing_allowed": False,
    "financial_truth_claimed": False,
    "operator_approval_required": True,
}

REPORT_SECTIONS = {"summary", "packets", "missing", "risks", "spreadsheet"}


@dataclass(frozen=True)
class FinancePacketFactInput:
    label: str
    value_text: str
    fact_kind: str = "operator_supplied"
    amount_value: float | None = None
    currency: str | None = None
    date_or_period: str | None = None
    confidence: str = "operator_claim"
    truth_status: str = "unverified_claim"
    source_ref: str | None = None


@dataclass(frozen=True)
class FinanceInvoicePacketResult:
    packet_id: str
    run_id: str
    db_path: str
    title: str
    subject: str
    workflow_kind: str
    status: str
    synthetic_demo: bool
    fact_count: int
    evidence_link_count: int
    missing_item_count: int
    risk_count: int
    work_board_card_count: int
    spreadsheet_candidate_known: bool
    financial_truth_claimed: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


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


def _export_root_path(export_root: str | Path) -> Path:
    path = Path(export_root)
    if path.is_absolute():
        return path
    return ROOT / path


def _dict_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone() is not None


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS finance_invoice_packet_runs (
  run_id TEXT PRIMARY KEY,
  packet_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  packet_count INTEGER NOT NULL DEFAULT 0,
  fact_count INTEGER NOT NULL DEFAULT 0,
  evidence_link_count INTEGER NOT NULL DEFAULT 0,
  missing_item_count INTEGER NOT NULL DEFAULT 0,
  risk_count INTEGER NOT NULL DEFAULT 0,
  work_board_card_count INTEGER NOT NULL DEFAULT 0,
  invoice_send_allowed INTEGER NOT NULL DEFAULT 0,
  email_send_allowed INTEGER NOT NULL DEFAULT 0,
  bank_access_allowed INTEGER NOT NULL DEFAULT 0,
  ledger_write_allowed INTEGER NOT NULL DEFAULT 0,
  tax_filing_allowed INTEGER NOT NULL DEFAULT 0,
  external_api_allowed INTEGER NOT NULL DEFAULT 0,
  raw_sensitive_body_ingest_allowed INTEGER NOT NULL DEFAULT 0,
  spreadsheet_cell_read_allowed INTEGER NOT NULL DEFAULT 0,
  workbook_parsing_allowed INTEGER NOT NULL DEFAULT 0,
  financial_truth_claimed INTEGER NOT NULL DEFAULT 0,
  operator_approval_required INTEGER NOT NULL DEFAULT 1,
  notes TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS finance_invoice_packets (
  packet_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  title TEXT NOT NULL,
  subject_entity TEXT NOT NULL,
  workflow_kind TEXT NOT NULL,
  status TEXT NOT NULL,
  world TEXT NOT NULL DEFAULT 'finance',
  agent_lane TEXT NOT NULL,
  synthetic_demo INTEGER NOT NULL DEFAULT 0,
  financial_truth_claimed INTEGER NOT NULL DEFAULT 0,
  send_allowed INTEGER NOT NULL DEFAULT 0,
  bank_access_allowed INTEGER NOT NULL DEFAULT 0,
  ledger_write_allowed INTEGER NOT NULL DEFAULT 0,
  tax_filing_allowed INTEGER NOT NULL DEFAULT 0,
  source_basis TEXT NOT NULL,
  next_safe_move TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(title, subject_entity, workflow_kind, synthetic_demo)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS finance_invoice_packet_facts (
  fact_id TEXT PRIMARY KEY,
  packet_id TEXT NOT NULL,
  fact_kind TEXT NOT NULL,
  label TEXT NOT NULL,
  value_text TEXT NOT NULL,
  amount_value REAL,
  currency TEXT,
  date_or_period TEXT,
  confidence TEXT NOT NULL,
  truth_status TEXT NOT NULL,
  source_ref TEXT,
  no_raw_sensitive_body INTEGER NOT NULL DEFAULT 1,
  financial_truth_claimed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (packet_id) REFERENCES finance_invoice_packets(packet_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS finance_invoice_packet_evidence_links (
  evidence_id TEXT PRIMARY KEY,
  packet_id TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  likely_path TEXT,
  allowed_use TEXT NOT NULL,
  sensitivity_status TEXT NOT NULL,
  ingestion_policy TEXT NOT NULL,
  cell_read_allowed INTEGER NOT NULL DEFAULT 0,
  raw_body_read_allowed INTEGER NOT NULL DEFAULT 0,
  workbook_parsing_allowed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (packet_id) REFERENCES finance_invoice_packets(packet_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS finance_invoice_packet_missing_items (
  missing_item_id TEXT PRIMARY KEY,
  packet_id TEXT NOT NULL,
  description TEXT NOT NULL,
  why_needed TEXT NOT NULL,
  blocker_level TEXT NOT NULL,
  next_safe_move TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (packet_id) REFERENCES finance_invoice_packets(packet_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS finance_invoice_packet_risks (
  risk_id TEXT PRIMARY KEY,
  packet_id TEXT NOT NULL,
  risk_kind TEXT NOT NULL,
  severity TEXT NOT NULL,
  mitigation TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (packet_id) REFERENCES finance_invoice_packets(packet_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS finance_invoice_packet_outputs (
  output_id TEXT PRIMARY KEY,
  packet_id TEXT NOT NULL,
  output_kind TEXT NOT NULL,
  title TEXT NOT NULL,
  body_text TEXT NOT NULL,
  send_allowed INTEGER NOT NULL DEFAULT 0,
  invoice_creation_allowed INTEGER NOT NULL DEFAULT 0,
  raw_sensitive_body_included INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (packet_id) REFERENCES finance_invoice_packets(packet_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS finance_invoice_packet_receipts (
  receipt_id TEXT PRIMARY KEY,
  packet_id TEXT NOT NULL,
  receipt_kind TEXT NOT NULL,
  summary TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  send_allowed INTEGER NOT NULL DEFAULT 0,
  financial_truth_claimed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (packet_id) REFERENCES finance_invoice_packets(packet_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS finance_invoice_packet_query_receipts (
  query_receipt_id TEXT PRIMARY KEY,
  query_kind TEXT NOT NULL,
  filter_value TEXT,
  result_count INTEGER NOT NULL DEFAULT 0,
  generated_at TEXT NOT NULL,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  execution_allowed INTEGER NOT NULL DEFAULT 0
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_finance_packets_status ON finance_invoice_packets(status)",
        "CREATE INDEX IF NOT EXISTS idx_finance_packets_workflow ON finance_invoice_packets(workflow_kind)",
        "CREATE INDEX IF NOT EXISTS idx_finance_packet_missing_packet ON finance_invoice_packet_missing_items(packet_id)",
        "CREATE INDEX IF NOT EXISTS idx_finance_packet_risks_packet ON finance_invoice_packet_risks(packet_id)",
    )


def init_finance_invoice_evidence_packet_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path) if db_path is not None else DEFAULT_DB_PATH
    init_business_ops_ledger(path)
    init_finance_invoice_reconciliation_schema(path)
    conn = sqlite3.connect(path)
    try:
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def finance_invoice_evidence_packet_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_finance_invoice_evidence_packet_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name FROM sqlite_master
WHERE type = 'table' AND name LIKE 'finance_invoice_packet%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _normalize_workflow_kind(workflow_kind: str) -> str:
    value = workflow_kind.strip() or "unknown"
    if value not in WORKFLOW_KINDS:
        raise ValueError(f"unknown finance workflow kind: {workflow_kind}")
    return value


def _normalize_fact(fact: FinancePacketFactInput | dict[str, Any]) -> FinancePacketFactInput:
    if isinstance(fact, FinancePacketFactInput):
        payload = fact.__dict__
    else:
        payload = dict(fact)
    fact_kind = payload.get("fact_kind") or "operator_supplied"
    confidence = payload.get("confidence") or "operator_claim"
    truth_status = payload.get("truth_status") or "unverified_claim"
    if fact_kind not in FACT_KINDS:
        fact_kind = "unknown_review"
    if confidence not in CONFIDENCE_LEVELS:
        confidence = "unknown_review"
    if truth_status not in TRUTH_STATUSES:
        truth_status = "needs_review"
    return FinancePacketFactInput(
        label=str(payload.get("label") or "fact").strip()[:120],
        value_text=str(payload.get("value_text") or "").strip()[:800],
        fact_kind=fact_kind,
        amount_value=payload.get("amount_value"),
        currency=payload.get("currency"),
        date_or_period=payload.get("date_or_period"),
        confidence=confidence,
        truth_status=truth_status,
        source_ref=payload.get("source_ref"),
    )


def parse_fact_arg(raw: str) -> FinancePacketFactInput:
    if "=" not in raw:
        raise ValueError("--fact values must use label=value format")
    label, value = raw.split("=", 1)
    return FinancePacketFactInput(label=label.strip(), value_text=value.strip())


def parse_amount_arg(raw: str) -> FinancePacketFactInput:
    if "=" in raw:
        label, value = raw.split("=", 1)
    else:
        label, value = "amount", raw
    try:
        amount = float(value)
    except ValueError as exc:
        raise ValueError("--amount must be numeric or label=numeric") from exc
    return FinancePacketFactInput(
        label=label.strip() or "amount",
        value_text=value.strip(),
        amount_value=amount,
        currency="USD",
        confidence="operator_claim",
        truth_status="unverified_claim",
    )


def _insert_run(conn: sqlite3.Connection, *, run_id: str, now: str) -> None:
    conn.execute(
        """
INSERT INTO finance_invoice_packet_runs (
  run_id, packet_version, created_at, notes
) VALUES (?, ?, ?, ?)
ON CONFLICT(run_id) DO UPDATE SET
  packet_version = excluded.packet_version,
  invoice_send_allowed = 0,
  email_send_allowed = 0,
  bank_access_allowed = 0,
  ledger_write_allowed = 0,
  tax_filing_allowed = 0,
  external_api_allowed = 0,
  raw_sensitive_body_ingest_allowed = 0,
  spreadsheet_cell_read_allowed = 0,
  workbook_parsing_allowed = 0,
  financial_truth_claimed = 0,
  operator_approval_required = 1,
  notes = excluded.notes
""".strip(),
        (
            run_id,
            FINANCE_PACKET_VERSION,
            now,
            "Finance packet build is metadata-only; no invoice/email/bank/ledger/tax action is authorized.",
        ),
    )


def _has_amount(facts: list[FinancePacketFactInput]) -> bool:
    return any(fact.amount_value is not None or any(token in fact.label.lower() for token in ("amount", "balance", "deposit", "rate")) for fact in facts)


def _has_date(facts: list[FinancePacketFactInput]) -> bool:
    return any(fact.date_or_period or any(token in fact.label.lower() for token in ("date", "period", "month", "range")) for fact in facts)


def _has_evidence_reference(facts: list[FinancePacketFactInput]) -> bool:
    return any(fact.fact_kind == "approved_evidence_reference" or fact.source_ref for fact in facts)


def _subject_is_unclear(subject: str) -> bool:
    lowered = subject.strip().lower()
    return lowered in {"", "manual review", "manual", "review", "unknown", "tbd"}


def _missing_items_for_packet(
    *,
    subject: str,
    facts: list[FinancePacketFactInput],
    spreadsheet_filename: str | None,
) -> list[dict[str, str]]:
    missing: list[dict[str, str]] = []
    if _subject_is_unclear(subject):
        missing.append(
            {
                "description": "Exact client/project/entity is not confirmed.",
                "why_needed": "Invoice and receivable packets need a clear subject before any draft context is useful.",
                "blocker_level": "blocks_invoice_draft",
                "next_safe_move": "Provide the client/project label or approve a safe metadata source that contains it.",
            }
        )
    if not _has_amount(facts):
        missing.append(
            {
                "description": "Amount, balance, deposit, or rate is missing.",
                "why_needed": "OpenClaw cannot prepare invoice or receivable context without an operator-provided or evidence-backed amount.",
                "blocker_level": "blocks_invoice_draft",
                "next_safe_move": "Provide the amount as an operator claim or approved evidence reference.",
            }
        )
    if not _has_date(facts):
        missing.append(
            {
                "description": "Service date, invoice date, due date, or period is missing.",
                "why_needed": "Dates keep invoice context reviewable and prevent unsupported assumptions.",
                "blocker_level": "blocks_invoice_draft",
                "next_safe_move": "Provide a date/period or approved evidence reference.",
            }
        )
    if not _has_evidence_reference(facts):
        missing.append(
            {
                "description": "Approved evidence reference is missing.",
                "why_needed": "The packet can record operator claims, but draft review should distinguish claims from evidence-backed facts.",
                "blocker_level": "optional",
                "next_safe_move": "Link an approved note, receipt reference, or sanitized metadata packet.",
            }
        )
    if not spreadsheet_filename:
        missing.append(
            {
                "description": "Mac invoice spreadsheet filename is not known.",
                "why_needed": "The operator reports a likely relevant spreadsheet under ~/Documents/invoices/, but this PC/WSL lane cannot read it.",
                "blocker_level": "optional",
                "next_safe_move": MAC_SPREADSHEET_NEXT_LANE,
            }
        )
    return missing


def _risk_items_for_packet(
    *,
    subject: str,
    facts: list[FinancePacketFactInput],
    missing_items: list[dict[str, str]],
) -> list[dict[str, str]]:
    risks = [
        {
            "risk_kind": "send_not_allowed",
            "severity": "high",
            "mitigation": "Keep all invoice/email outputs as draft context only until a later explicit approval path exists.",
        },
        {
            "risk_kind": "spreadsheet_needs_review",
            "severity": "medium",
            "mitigation": "Treat ~/Documents/invoices/ as sensitive metadata only; use a future Mac-side intake lane for filename metadata.",
        },
    ]
    for item in missing_items:
        text = item["description"].lower()
        if "amount" in text:
            risks.append({"risk_kind": "missing_amount", "severity": "high", "mitigation": item["next_safe_move"]})
        elif "date" in text:
            risks.append({"risk_kind": "missing_date", "severity": "medium", "mitigation": item["next_safe_move"]})
        elif "client" in text or "entity" in text:
            risks.append({"risk_kind": "unclear_client", "severity": "high", "mitigation": item["next_safe_move"]})
    for fact in facts:
        if fact.truth_status == "evidence_backed" and not fact.source_ref:
            risks.append(
                {
                    "risk_kind": "unsupported_claim",
                    "severity": "high",
                    "mitigation": f"Fact `{fact.label}` was marked evidence-backed without a source reference; downgrade to needs_review until evidence is linked.",
                }
            )
    return risks


def _packet_status(*, synthetic_demo: bool, missing_items: list[dict[str, str]], risks: list[dict[str, str]]) -> str:
    if synthetic_demo:
        return "needs_operator_facts"
    if any(item["blocker_level"] in {"blocks_packet", "blocks_invoice_draft"} for item in missing_items):
        return "blocked_missing_info"
    if any(risk["risk_kind"] == "unsupported_claim" for risk in risks):
        return "blocked_missing_info"
    if missing_items:
        return "ready_for_draft_review"
    return "ready_for_draft_review"


def _next_safe_move(status: str) -> str:
    if status == "needs_operator_facts":
        return "Provide one real receivable/invoice target with safe operator facts; do not use private raw files yet."
    if status == "blocked_missing_info":
        return "Fill the blocking missing items or link approved evidence before preparing draft invoice context."
    return "Review packet facts and missing items; draft context may be prepared later, but sending remains blocked."


def _insert_packet(
    conn: sqlite3.Connection,
    *,
    packet_id: str,
    run_id: str,
    title: str,
    subject: str,
    workflow_kind: str,
    status: str,
    synthetic_demo: bool,
    source_basis: str,
    next_safe_move: str,
    now: str,
) -> None:
    conn.execute(
        """
INSERT INTO finance_invoice_packets (
  packet_id, run_id, title, subject_entity, workflow_kind, status,
  world, agent_lane, synthetic_demo, financial_truth_claimed, send_allowed,
  bank_access_allowed, ledger_write_allowed, tax_filing_allowed, source_basis,
  next_safe_move, created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, 'finance', 'chief', ?, 0, 0, 0, 0, 0, ?, ?, ?, ?)
ON CONFLICT(packet_id) DO UPDATE SET
  run_id = excluded.run_id,
  title = excluded.title,
  subject_entity = excluded.subject_entity,
  workflow_kind = excluded.workflow_kind,
  status = excluded.status,
  agent_lane = excluded.agent_lane,
  synthetic_demo = excluded.synthetic_demo,
  financial_truth_claimed = 0,
  send_allowed = 0,
  bank_access_allowed = 0,
  ledger_write_allowed = 0,
  tax_filing_allowed = 0,
  source_basis = excluded.source_basis,
  next_safe_move = excluded.next_safe_move,
  updated_at = excluded.updated_at
""".strip(),
        (packet_id, run_id, title, subject, workflow_kind, status, _bool(synthetic_demo), source_basis, next_safe_move, now, now),
    )


def _replace_packet_children(conn: sqlite3.Connection, packet_id: str) -> None:
    for table in (
        "finance_invoice_packet_facts",
        "finance_invoice_packet_evidence_links",
        "finance_invoice_packet_missing_items",
        "finance_invoice_packet_risks",
        "finance_invoice_packet_outputs",
        "finance_invoice_packet_receipts",
    ):
        conn.execute(f"DELETE FROM {table} WHERE packet_id = ?", (packet_id,))


def _insert_facts(conn: sqlite3.Connection, *, packet_id: str, facts: list[FinancePacketFactInput], now: str) -> None:
    for fact in facts:
        truth_status = fact.truth_status
        confidence = fact.confidence
        if truth_status == "evidence_backed" and not fact.source_ref:
            truth_status = "needs_review"
            confidence = "unknown_review"
        conn.execute(
            """
INSERT INTO finance_invoice_packet_facts (
  fact_id, packet_id, fact_kind, label, value_text, amount_value,
  currency, date_or_period, confidence, truth_status, source_ref,
  no_raw_sensitive_body, financial_truth_claimed, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?)
""".strip(),
            (
                _row_id("finpktfact", packet_id, fact.label, fact.value_text),
                packet_id,
                fact.fact_kind,
                fact.label,
                fact.value_text,
                fact.amount_value,
                fact.currency,
                fact.date_or_period,
                confidence,
                truth_status,
                fact.source_ref,
                now,
            ),
        )


def _spreadsheet_likely_path(spreadsheet_filename: str | None) -> str:
    if spreadsheet_filename:
        return f"{MAC_SPREADSHEET_FOLDER.rstrip('/')}/{Path(spreadsheet_filename).name}"
    return MAC_SPREADSHEET_FOLDER


def _insert_spreadsheet_evidence_link(
    conn: sqlite3.Connection,
    *,
    packet_id: str,
    spreadsheet_filename: str | None,
    now: str,
) -> str:
    likely_path = _spreadsheet_likely_path(spreadsheet_filename)
    evidence_id = _row_id("finpktev", packet_id, "mac_local_spreadsheet_candidate", likely_path)
    conn.execute(
        """
INSERT INTO finance_invoice_packet_evidence_links (
  evidence_id, packet_id, source_kind, source_ref, likely_path,
  allowed_use, sensitivity_status, ingestion_policy, cell_read_allowed,
  raw_body_read_allowed, workbook_parsing_allowed, created_at
) VALUES (?, ?, 'mac_local_spreadsheet_candidate', ?, ?, 'metadata_only_pending_review',
  'sensitive_metadata_only', 'needs_operator_review', 0, 0, 0, ?)
""".strip(),
        (evidence_id, packet_id, "mac:~/Documents/invoices/", likely_path, now),
    )
    return evidence_id


def _insert_missing_items(conn: sqlite3.Connection, *, packet_id: str, missing_items: list[dict[str, str]], now: str) -> None:
    for item in missing_items:
        conn.execute(
            """
INSERT INTO finance_invoice_packet_missing_items (
  missing_item_id, packet_id, description, why_needed,
  blocker_level, next_safe_move, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?)
""".strip(),
            (
                _row_id("finpktmiss", packet_id, item["description"]),
                packet_id,
                item["description"],
                item["why_needed"],
                item["blocker_level"],
                item["next_safe_move"],
                now,
            ),
        )


def _insert_risks(conn: sqlite3.Connection, *, packet_id: str, risks: list[dict[str, str]], now: str) -> None:
    for risk in risks:
        risk_kind = risk["risk_kind"] if risk["risk_kind"] in RISK_KINDS else "unknown"
        conn.execute(
            """
INSERT INTO finance_invoice_packet_risks (
  risk_id, packet_id, risk_kind, severity, mitigation, created_at
) VALUES (?, ?, ?, ?, ?, ?)
""".strip(),
            (
                _row_id("finpktrisk", packet_id, risk_kind, risk["mitigation"]),
                packet_id,
                risk_kind,
                risk["severity"],
                risk["mitigation"],
                now,
            ),
        )


def _insert_outputs(conn: sqlite3.Connection, *, packet_id: str, status: str, next_safe_move: str, now: str) -> None:
    body = (
        f"Packet status: {status}. Next safe move: {next_safe_move} "
        "This is context only. No invoice, email, bank access, ledger write, tax filing, or financial truth claim is authorized."
    )
    conn.execute(
        """
INSERT INTO finance_invoice_packet_outputs (
  output_id, packet_id, output_kind, title, body_text,
  send_allowed, invoice_creation_allowed, raw_sensitive_body_included, created_at
) VALUES (?, ?, 'bounded_context_packet', 'Finance packet context for Chief/Cassandra', ?, 0, 0, 0, ?)
""".strip(),
        (_row_id("finpktout", packet_id, "bounded_context_packet"), packet_id, body, now),
    )


def _insert_receipt(conn: sqlite3.Connection, *, packet_id: str, run_id: str, now: str) -> None:
    payload = {
        "packet_id": packet_id,
        "run_id": run_id,
        "invoice_send_allowed": False,
        "email_send_allowed": False,
        "bank_access_allowed": False,
        "ledger_write_allowed": False,
        "tax_filing_allowed": False,
        "financial_truth_claimed": False,
    }
    conn.execute(
        """
INSERT INTO finance_invoice_packet_receipts (
  receipt_id, packet_id, receipt_kind, summary, payload_json,
  execution_allowed, send_allowed, financial_truth_claimed, created_at
) VALUES (?, ?, 'packet_build_receipt', ?, ?, 0, 0, 0, ?)
""".strip(),
        (
            _row_id("finpktreceipt", packet_id, run_id),
            packet_id,
            "Finance packet created as metadata-only context; no finance action was executed.",
            stable_json(payload),
            now,
        ),
    )


def _ensure_work_board_cards(conn: sqlite3.Connection, *, packet_id: str, status: str, now: str) -> int:
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
        (board_id, "Local review board over OpenClaw control-plane metadata, including finance evidence packets.", now, now),
    )
    specs = [
        (
            f"finance_invoice_evidence_packet:{packet_id}",
            "Finance Invoice Evidence Packet Builder",
            "Review the finance evidence packet and fill missing invoice/receivable facts.",
            "planned" if status == "ready_for_draft_review" else "needs_review",
            "packet_context_only",
            "Review packet facts and missing items; no invoice/email/bank/ledger action is authorized.",
        ),
        (
            f"finance_invoice_evidence_packet:{packet_id}:missing",
            "Review missing finance evidence",
            "Resolve missing amount/date/client/evidence references before draft review.",
            "needs_review",
            "missing_evidence",
            "Provide safe operator facts or approved evidence references.",
        ),
        (
            f"finance_invoice_evidence_packet:{packet_id}:spreadsheet",
            "Mac spreadsheet evidence intake needed",
            "The Mac folder ~/Documents/invoices/ is known, but no workbook cells or filenames are ingested here.",
            "needs_review",
            "spreadsheet_metadata_pending",
            MAC_SPREADSHEET_NEXT_LANE,
        ),
    ]
    count = 0
    for source_id, title, summary, column, status_label, next_safe_move in specs:
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
) VALUES (?, ?, ?, ?, 'manual_seed', ?, 'finance', 'chief',
  'system_orchestration', 'finance_invoice_evidence_packet', ?, ?, 'high',
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
            (card_id, board_id, title, summary, source_id, column, status_label, next_safe_move, f"finance_invoice_evidence_packet:{packet_id}", now, now),
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
) VALUES (?, ?, 'chief', 'system_orchestration', 'assigned_lane', 0, 0, ?)
""".strip(),
            (_row_id("wbagent", card_id, "chief"), card_id, now),
        )
        conn.execute(
            """
INSERT OR REPLACE INTO work_board_card_worlds (
  card_world_id, card_id, world_hint, confidence, created_at
) VALUES (?, ?, 'finance', 'metadata_hint', ?)
""".strip(),
            (_row_id("wbworld", card_id, "finance"), card_id, now),
        )
        count += 1
    return count


def build_finance_invoice_evidence_packet(
    *,
    db_path: str | Path | None = None,
    title: str,
    subject: str,
    workflow_kind: str = "invoice_prep",
    facts: list[FinancePacketFactInput | dict[str, Any]] | None = None,
    packet_id: str | None = None,
    run_id: str | None = None,
    spreadsheet_filename: str | None = None,
    synthetic_demo: bool | None = None,
    create_work_board_cards: bool = True,
) -> FinanceInvoicePacketResult:
    workflow = _normalize_workflow_kind(workflow_kind)
    normalized_facts = [_normalize_fact(fact) for fact in (facts or [])]
    resolved_synthetic = not normalized_facts if synthetic_demo is None else bool(synthetic_demo)
    if resolved_synthetic and not normalized_facts:
        normalized_facts = [
            FinancePacketFactInput(
                label="synthetic_demo_context",
                value_text="Synthetic placeholder only. Replace with operator-supplied invoice/receivable facts.",
                fact_kind="unknown_review",
                confidence="unknown_review",
                truth_status="needs_review",
            )
        ]
    path = init_finance_invoice_evidence_packet_schema(db_path)
    if create_work_board_cards:
        init_work_board_schema(path)
    now = utc_now()
    resolved_run_id = run_id or _row_id("finpktrun", title, subject, workflow, now)
    resolved_packet_id = packet_id or _row_id("finpkt", title, subject, workflow, resolved_synthetic)
    missing_items = _missing_items_for_packet(subject=subject, facts=normalized_facts, spreadsheet_filename=spreadsheet_filename)
    risks = _risk_items_for_packet(subject=subject, facts=normalized_facts, missing_items=missing_items)
    status = _packet_status(synthetic_demo=resolved_synthetic, missing_items=missing_items, risks=risks)
    next_safe_move = _next_safe_move(status)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        _insert_run(conn, run_id=resolved_run_id, now=now)
        _insert_packet(
            conn,
            packet_id=resolved_packet_id,
            run_id=resolved_run_id,
            title=title,
            subject=subject,
            workflow_kind=workflow,
            status=status,
            synthetic_demo=resolved_synthetic,
            source_basis="operator_cli_or_synthetic_demo; finance_reconciliation_proposal; spreadsheet_candidate_metadata_only",
            next_safe_move=next_safe_move,
            now=now,
        )
        _replace_packet_children(conn, resolved_packet_id)
        _insert_facts(conn, packet_id=resolved_packet_id, facts=normalized_facts, now=now)
        _insert_spreadsheet_evidence_link(conn, packet_id=resolved_packet_id, spreadsheet_filename=spreadsheet_filename, now=now)
        _insert_missing_items(conn, packet_id=resolved_packet_id, missing_items=missing_items, now=now)
        _insert_risks(conn, packet_id=resolved_packet_id, risks=risks, now=now)
        _insert_outputs(conn, packet_id=resolved_packet_id, status=status, next_safe_move=next_safe_move, now=now)
        _insert_receipt(conn, packet_id=resolved_packet_id, run_id=resolved_run_id, now=now)
        work_board_count = _ensure_work_board_cards(conn, packet_id=resolved_packet_id, status=status, now=now) if create_work_board_cards else 0
        conn.execute(
            """
UPDATE finance_invoice_packet_runs
SET completed_at = ?, packet_count = 1, fact_count = ?,
    evidence_link_count = 1, missing_item_count = ?, risk_count = ?,
    work_board_card_count = ?, invoice_send_allowed = 0,
    email_send_allowed = 0, bank_access_allowed = 0,
    ledger_write_allowed = 0, tax_filing_allowed = 0,
    external_api_allowed = 0, raw_sensitive_body_ingest_allowed = 0,
    spreadsheet_cell_read_allowed = 0, workbook_parsing_allowed = 0,
    financial_truth_claimed = 0, operator_approval_required = 1
WHERE run_id = ?
""".strip(),
            (utc_now(), len(normalized_facts), len(missing_items), len(risks), work_board_count, resolved_run_id),
        )
        conn.commit()
        return FinanceInvoicePacketResult(
            packet_id=resolved_packet_id,
            run_id=resolved_run_id,
            db_path=path,
            title=title,
            subject=subject,
            workflow_kind=workflow,
            status=status,
            synthetic_demo=resolved_synthetic,
            fact_count=len(normalized_facts),
            evidence_link_count=1,
            missing_item_count=len(missing_items),
            risk_count=len(risks),
            work_board_card_count=work_board_count,
            spreadsheet_candidate_known=True,
            financial_truth_claimed=False,
        )
    finally:
        conn.close()


def _latest_packet_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
SELECT packet_id FROM finance_invoice_packets
ORDER BY updated_at DESC, created_at DESC, packet_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row["packet_id"] if row else None


def _packet_counts(conn: sqlite3.Connection) -> dict[str, Any]:
    packets = conn.execute("SELECT * FROM finance_invoice_packets").fetchall()
    status_counts = Counter(row["status"] for row in packets)
    risks = conn.execute("SELECT severity, COUNT(*) AS count FROM finance_invoice_packet_risks GROUP BY severity").fetchall()
    return {
        "packet_count": len(packets),
        "open_packet_count": sum(1 for row in packets if row["status"] != "completed_packet"),
        "blocked_missing_info_count": status_counts.get("blocked_missing_info", 0),
        "ready_for_draft_review_count": status_counts.get("ready_for_draft_review", 0),
        "needs_operator_facts_count": status_counts.get("needs_operator_facts", 0),
        "missing_items_count": conn.execute("SELECT COUNT(*) AS count FROM finance_invoice_packet_missing_items").fetchone()["count"],
        "high_risk_count": sum(row["count"] for row in risks if row["severity"] == "high"),
        "counts_by_status": dict(sorted(status_counts.items())),
    }


def build_finance_invoice_evidence_packet_report(
    *,
    db_path: str | Path | None = None,
    report: str = "summary",
    packet_id: str | None = None,
) -> dict[str, Any]:
    if report not in REPORT_SECTIONS:
        raise ValueError(f"unknown finance packet report: {report}")
    path = init_finance_invoice_evidence_packet_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        resolved_packet_id = packet_id
        if packet_id and report == "summary":
            report = "packets"
        clauses = []
        params: list[Any] = []
        if resolved_packet_id:
            clauses.append("packet_id = ?")
            params.append(resolved_packet_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        if report == "packets" or (packet_id and report == "packets"):
            rows = _dict_rows(conn, f"SELECT * FROM finance_invoice_packets {where} ORDER BY updated_at DESC LIMIT 100", tuple(params))
        elif report == "missing":
            if resolved_packet_id:
                rows = _dict_rows(
                    conn,
                    """
SELECT m.*, p.title, p.subject_entity
FROM finance_invoice_packet_missing_items m
JOIN finance_invoice_packets p ON p.packet_id = m.packet_id
WHERE m.packet_id = ?
ORDER BY m.blocker_level, m.description
""".strip(),
                    (resolved_packet_id,),
                )
            else:
                rows = _dict_rows(
                    conn,
                    """
SELECT m.*, p.title, p.subject_entity
FROM finance_invoice_packet_missing_items m
JOIN finance_invoice_packets p ON p.packet_id = m.packet_id
ORDER BY m.blocker_level, m.description
LIMIT 200
""".strip(),
                )
        elif report == "risks":
            if resolved_packet_id:
                rows = _dict_rows(
                    conn,
                    """
SELECT r.*, p.title, p.subject_entity
FROM finance_invoice_packet_risks r
JOIN finance_invoice_packets p ON p.packet_id = r.packet_id
WHERE r.packet_id = ?
ORDER BY CASE r.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, r.risk_kind
""".strip(),
                    (resolved_packet_id,),
                )
            else:
                rows = _dict_rows(
                    conn,
                    """
SELECT r.*, p.title, p.subject_entity
FROM finance_invoice_packet_risks r
JOIN finance_invoice_packets p ON p.packet_id = r.packet_id
ORDER BY CASE r.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, r.risk_kind
LIMIT 200
""".strip(),
                )
        elif report == "spreadsheet":
            rows = _dict_rows(
                conn,
                """
SELECT e.*, p.title, p.subject_entity
FROM finance_invoice_packet_evidence_links e
JOIN finance_invoice_packets p ON p.packet_id = e.packet_id
WHERE e.source_kind = 'mac_local_spreadsheet_candidate'
ORDER BY e.created_at DESC
LIMIT 100
""".strip(),
            )
        else:
            rows = _dict_rows(
                conn,
                """
SELECT packet_id, title, subject_entity, workflow_kind, status,
       synthetic_demo, next_safe_move, updated_at
FROM finance_invoice_packets
ORDER BY updated_at DESC
LIMIT 12
""".strip(),
            )
        counts = _packet_counts(conn)
        conn.execute(
            """
INSERT OR REPLACE INTO finance_invoice_packet_query_receipts (
  query_receipt_id, query_kind, filter_value, result_count,
  generated_at, raw_body_stored, execution_allowed
) VALUES (?, ?, ?, ?, ?, 0, 0)
""".strip(),
            (_row_id("finpktquery", report, packet_id or "", utc_now()), report, packet_id, len(rows), utc_now()),
        )
        conn.commit()
        return {
            "status": "ok",
            "report": report,
            "packet_id": packet_id,
            "counts": counts,
            "rows": rows,
            "spreadsheet_candidate": spreadsheet_candidate_payload(),
            "no_authority_flags": NO_AUTHORITY_FLAGS,
        }
    finally:
        conn.close()


def spreadsheet_candidate_payload(spreadsheet_filename: str | None = None) -> dict[str, Any]:
    return {
        "spreadsheet_candidate_known": True,
        "spreadsheet_folder_known": True,
        "spreadsheet_folder": MAC_SPREADSHEET_FOLDER,
        "spreadsheet_path_known": bool(spreadsheet_filename),
        "spreadsheet_path": _spreadsheet_likely_path(spreadsheet_filename) if spreadsheet_filename else None,
        "spreadsheet_metadata_available": False,
        "spreadsheet_ingestion_allowed": False,
        "spreadsheet_cell_read_allowed": False,
        "workbook_parsing_allowed": False,
        "source_kind": "mac_local_spreadsheet_candidate",
        "sensitivity_status": "sensitive_metadata_only",
        "ingestion_policy": "needs_operator_review",
        "allowed_use": "metadata_only_pending_review",
        "next_safe_move": MAC_SPREADSHEET_NEXT_LANE,
    }


def format_finance_invoice_evidence_packet_result(result: FinanceInvoicePacketResult) -> str:
    return "\n".join(
        [
            "Finance Invoice Evidence Packet v0",
            "",
            f"Packet: `{result.packet_id}`",
            f"Run: `{result.run_id}`",
            f"Title: {result.title}",
            f"Subject: {result.subject}",
            f"Workflow: `{result.workflow_kind}`",
            f"Status: `{result.status}`",
            f"Synthetic demo: `{str(result.synthetic_demo).lower()}`",
            f"Facts: {result.fact_count}",
            f"Evidence links: {result.evidence_link_count}",
            f"Missing items: {result.missing_item_count}",
            f"Risks: {result.risk_count}",
            f"Work Board cards: {result.work_board_card_count}",
            "",
            "Spreadsheet candidate:",
            f"- folder: `{MAC_SPREADSHEET_FOLDER}`",
            "- ingestion allowed: `false`",
            "- cell read allowed: `false`",
            f"- next safe move: {MAC_SPREADSHEET_NEXT_LANE}",
            "",
            "Boundary:",
            "- No invoice/email send, bank access, workbook parsing, ledger write, tax filing, or financial truth claim was performed.",
        ]
    )


def _counts_line(counts: dict[str, Any]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def format_finance_invoice_evidence_packet_report(payload: dict[str, Any]) -> str:
    counts = payload["counts"]
    lines = [
        f"Finance Invoice Evidence Packets v0 - {payload['report']}",
        "",
        f"Packets: {counts.get('packet_count', 0)}",
        f"Open packets: {counts.get('open_packet_count', 0)}",
        f"Blocked missing info: {counts.get('blocked_missing_info_count', 0)}",
        f"Ready for draft review: {counts.get('ready_for_draft_review_count', 0)}",
        f"Missing items: {counts.get('missing_items_count', 0)}",
        f"High risk: {counts.get('high_risk_count', 0)}",
        f"By status: {_counts_line(counts.get('counts_by_status', {}))}",
        "",
        "Rows:",
    ]
    for row in payload.get("rows") or []:
        if payload["report"] == "missing":
            lines.append(f"- `{row['packet_id']}` {row['blocker_level']}: {row['description']} -> {row['next_safe_move']}")
        elif payload["report"] == "risks":
            lines.append(f"- `{row['packet_id']}` {row['risk_kind']} ({row['severity']}): {row['mitigation']}")
        elif payload["report"] == "spreadsheet":
            lines.append(
                f"- `{row['packet_id']}` likely_path=`{row['likely_path']}` sensitivity={row['sensitivity_status']} ingestion={row['ingestion_policy']} cell_read={bool(row['cell_read_allowed'])}"
            )
        elif payload["report"] == "packets":
            lines.append(f"- `{row['packet_id']}` {row['status']} subject={row['subject_entity']} next={row['next_safe_move']}")
        else:
            lines.append(f"- `{row['packet_id']}` {row['status']} {row['title']}: {row['next_safe_move']}")
    if not payload.get("rows"):
        lines.append("- none")
    spreadsheet = payload["spreadsheet_candidate"]
    lines.extend(
        [
            "",
            "Spreadsheet candidate:",
            f"- known: `{str(spreadsheet['spreadsheet_candidate_known']).lower()}`",
            f"- folder: `{spreadsheet['spreadsheet_folder']}`",
            f"- path known: `{str(spreadsheet['spreadsheet_path_known']).lower()}`",
            f"- ingestion allowed: `{str(spreadsheet['spreadsheet_ingestion_allowed']).lower()}`",
            f"- cell read allowed: `{str(spreadsheet['spreadsheet_cell_read_allowed']).lower()}`",
            f"- next safe move: {spreadsheet['next_safe_move']}",
            "",
            "Authority boundary:",
        ]
    )
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`.")
    return "\n".join(lines)


def build_finance_invoice_evidence_packets_read_model(db_path: str | Path | None = None) -> dict[str, Any]:
    path = init_finance_invoice_evidence_packet_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        counts = _packet_counts(conn)
        latest_packet_id = _latest_packet_id(conn)
        latest_packet = (
            dict(conn.execute("SELECT * FROM finance_invoice_packets WHERE packet_id = ?", (latest_packet_id,)).fetchone())
            if latest_packet_id
            else None
        )
        latest_facts = _dict_rows(
            conn,
            """
SELECT label, value_text, amount_value, currency, date_or_period,
       confidence, truth_status, source_ref
FROM finance_invoice_packet_facts
WHERE packet_id = ?
ORDER BY label
""".strip(),
            (latest_packet_id,),
        ) if latest_packet_id else []
        latest_outputs = _dict_rows(
            conn,
            """
SELECT output_id, output_kind, title, body_text, send_allowed,
       invoice_creation_allowed, raw_sensitive_body_included, created_at
FROM finance_invoice_packet_outputs
WHERE packet_id = ?
ORDER BY created_at, output_kind
""".strip(),
            (latest_packet_id,),
        ) if latest_packet_id else []
        missing_items = _dict_rows(
            conn,
            """
SELECT packet_id, description, why_needed, blocker_level, next_safe_move
FROM finance_invoice_packet_missing_items
ORDER BY CASE blocker_level WHEN 'blocks_packet' THEN 0 WHEN 'blocks_invoice_draft' THEN 1 WHEN 'blocks_send' THEN 2 ELSE 3 END,
         description
LIMIT 30
""".strip(),
        )
        risks = _dict_rows(
            conn,
            """
SELECT packet_id, risk_kind, severity, mitigation
FROM finance_invoice_packet_risks
ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, risk_kind
LIMIT 30
""".strip(),
        )
        next_safe_moves = _dict_rows(
            conn,
            """
SELECT packet_id, title, status, next_safe_move
FROM finance_invoice_packets
WHERE status != 'completed_packet'
ORDER BY updated_at DESC
LIMIT 12
""".strip(),
        )
        work_board_cards = _dict_rows(
            conn,
            """
SELECT card_id, title, board_column, status, next_safe_move
FROM work_board_cards
WHERE source_kind = 'manual_seed'
	  AND (
	    source_id LIKE 'finance_invoice_evidence_packet:%'
	    OR source_id LIKE 'capital_hilton_invoice_packet:%'
	    OR source_id LIKE 'capital_hilton_fact_intake:%'
	  )
ORDER BY title
""".strip(),
        ) if _table_exists(conn, "work_board_cards") else []
        capital_hilton_spreadsheet_rows = _dict_rows(
            conn,
            """
SELECT filename, absolute_path, selected_candidate, alternate_candidate,
       operator_selection_status, sensitivity_status, ingestion_policy,
       allowed_use, cell_read_allowed, workbook_parsing_allowed, copied,
       uploaded, financial_truth_claimed, ingested_at
FROM capital_hilton_spreadsheet_metadata
WHERE packet_id = ?
ORDER BY selected_candidate DESC, modified_at DESC, filename
""".strip(),
            ("finance_capital_hilton_invoice_packet_v0",),
        ) if _table_exists(conn, "capital_hilton_spreadsheet_metadata") else []
        capital_hilton_selected_spreadsheet = next((row for row in capital_hilton_spreadsheet_rows if row["selected_candidate"]), None)
        capital_hilton_contact_candidates = _dict_rows(
            conn,
            """
SELECT organization, contact_name, role, email, confidence, source_basis,
       allowed_use, external_send_allowed, operator_approval_required, verified
FROM capital_hilton_contact_candidates
WHERE packet_id = ?
ORDER BY contact_name
""".strip(),
            ("finance_capital_hilton_invoice_packet_v0",),
        ) if _table_exists(conn, "capital_hilton_contact_candidates") else []
        capital_hilton_fact_updates = _dict_rows(
            conn,
            """
SELECT field_name, value_text, source_kind, source_ref, agent_internal,
       external_persona, confidence, truth_status, financial_truth_claimed,
       raw_sensitive_body_stored, created_at
FROM capital_hilton_invoice_fact_updates
WHERE packet_id = ?
ORDER BY field_name
""".strip(),
            ("finance_capital_hilton_invoice_packet_v0",),
        ) if _table_exists(conn, "capital_hilton_invoice_fact_updates") else []
        spreadsheet = spreadsheet_candidate_payload()
        if capital_hilton_selected_spreadsheet:
            spreadsheet = {
                **spreadsheet,
                "spreadsheet_path_known": True,
                "spreadsheet_path": capital_hilton_selected_spreadsheet["absolute_path"],
                "spreadsheet_metadata_available": True,
                "selected_candidate": capital_hilton_selected_spreadsheet["filename"],
                "operator_selection_status": capital_hilton_selected_spreadsheet["operator_selection_status"],
            }
        return {
            "schema_version": READ_MODEL_VERSION,
            "read_model_version": READ_MODEL_VERSION,
            "generated_at": utc_now(),
            "counts": counts,
            "latest_packet": latest_packet,
            "latest_packet_facts": latest_facts,
            "latest_packet_outputs": latest_outputs,
            "missing_items": missing_items,
            "risks": risks,
            "next_safe_moves": next_safe_moves,
            "spreadsheet_candidate": spreadsheet,
            "spreadsheet_candidate_known": spreadsheet["spreadsheet_candidate_known"],
            "spreadsheet_folder_known": spreadsheet["spreadsheet_folder_known"],
            "spreadsheet_folder": spreadsheet["spreadsheet_folder"],
            "spreadsheet_path_known": spreadsheet["spreadsheet_path_known"],
            "spreadsheet_metadata_available": spreadsheet["spreadsheet_metadata_available"],
            "spreadsheet_ingestion_allowed": spreadsheet["spreadsheet_ingestion_allowed"],
            "spreadsheet_cell_read_allowed": spreadsheet["spreadsheet_cell_read_allowed"],
            "capital_hilton_spreadsheet_selection": capital_hilton_selected_spreadsheet,
            "capital_hilton_spreadsheet_candidates": capital_hilton_spreadsheet_rows,
            "capital_hilton_contact_candidates": capital_hilton_contact_candidates,
            "capital_hilton_fact_updates": capital_hilton_fact_updates,
            "capital_hilton_external_identity_rule": {
                "internal_agent": "cassandra",
                "external_persona": "Clara Reid",
                "external_draft_signature": "Best,\nClara Reid",
                "drafts_must_not_use_internal_name": True,
            },
            "work_board_linkage": {"implemented": bool(work_board_cards), "cards": work_board_cards},
            "bounded_context_output": {
                "for_agents": ["chief", "cassandra"],
                "packet_summary": latest_packet["next_safe_move"] if latest_packet else "No packet has been built.",
                "facts_truth_posture": "Facts remain operator claims unless explicitly evidence-backed by an approved source_ref.",
                "disallowed_actions": [
                    "invoice send",
                    "email send",
                    "bank access",
                    "ledger write",
                    "tax filing",
                    "spreadsheet cell read",
                    "workbook parsing",
                ],
            },
            "recommended_next_lane": MAC_SPREADSHEET_NEXT_LANE,
            "no_authority_flags": NO_AUTHORITY_FLAGS,
        }
    finally:
        conn.close()


def _operator_markdown(read_model: dict[str, Any]) -> str:
    counts = read_model["counts"]
    lines = [
        "# Finance Invoice Evidence Packets v0",
        "",
        "## Counts",
        f"- Packets: {counts.get('packet_count', 0)}",
        f"- Open packets: {counts.get('open_packet_count', 0)}",
        f"- Blocked missing info: {counts.get('blocked_missing_info_count', 0)}",
        f"- Ready for draft review: {counts.get('ready_for_draft_review_count', 0)}",
        f"- Missing items: {counts.get('missing_items_count', 0)}",
        f"- High risk: {counts.get('high_risk_count', 0)}",
        "",
        "## Latest Packet",
    ]
    latest = read_model.get("latest_packet")
    if latest:
        lines.append(f"- Packet: `{latest['packet_id']}`")
        lines.append(f"- Title: {latest['title']}")
        lines.append(f"- Subject: {latest['subject_entity']}")
        lines.append(f"- Status: `{latest['status']}`")
        lines.append(f"- Next safe move: {latest['next_safe_move']}")
    else:
        lines.append("- None.")
    lines.extend(["", "## Missing Items"])
    for row in read_model.get("missing_items") or []:
        lines.append(f"- `{row['packet_id']}` {row['blocker_level']}: {row['description']} -> {row['next_safe_move']}")
    if not read_model.get("missing_items"):
        lines.append("- None.")
    lines.extend(["", "## Risks"])
    for row in read_model.get("risks") or []:
        lines.append(f"- `{row['packet_id']}` {row['risk_kind']} ({row['severity']}): {row['mitigation']}")
    if not read_model.get("risks"):
        lines.append("- None.")
    lines.extend(["", "## Latest Packet Outputs"])
    for row in read_model.get("latest_packet_outputs") or []:
        lines.append(
            f"- `{row['output_kind']}` send_allowed={bool(row['send_allowed'])} invoice_creation_allowed={bool(row['invoice_creation_allowed'])}: {row['title']}"
        )
    if not read_model.get("latest_packet_outputs"):
        lines.append("- None.")
    spreadsheet = read_model["spreadsheet_candidate"]
    lines.extend(
        [
            "",
            "## Mac Spreadsheet Candidate",
            f"- Candidate known: `{str(spreadsheet['spreadsheet_candidate_known']).lower()}`",
            f"- Folder known: `{str(spreadsheet['spreadsheet_folder_known']).lower()}`",
            f"- Folder: `{spreadsheet['spreadsheet_folder']}`",
            f"- Exact path known: `{str(spreadsheet['spreadsheet_path_known']).lower()}`",
            f"- Metadata available: `{str(spreadsheet['spreadsheet_metadata_available']).lower()}`",
            f"- Ingestion allowed: `{str(spreadsheet['spreadsheet_ingestion_allowed']).lower()}`",
            f"- Cell read allowed: `{str(spreadsheet['spreadsheet_cell_read_allowed']).lower()}`",
            f"- Next safe move: {spreadsheet['next_safe_move']}",
            "",
            "## Capital Hilton Spreadsheet Selection",
        ]
    )
    selection = read_model.get("capital_hilton_spreadsheet_selection")
    if selection:
        lines.append(f"- Selected candidate: `{selection['filename']}`")
        lines.append(f"- Absolute path: `{selection['absolute_path']}`")
        lines.append(f"- Selection status: `{selection['operator_selection_status']}`")
        lines.append("- Sensitivity: `sensitive_metadata_only`")
        lines.append("- Cell read allowed: `false`")
        lines.append("- Workbook parsing allowed: `false`")
        lines.append("- Copied/uploaded: `false`")
    else:
        lines.append("- None.")
    lines.extend(["", "## Capital Hilton Contact Candidates"])
    for row in read_model.get("capital_hilton_contact_candidates") or []:
        lines.append(
            f"- {row['contact_name']} ({row['role']}), email={row['email'] or 'unknown'}, allowed_use={row['allowed_use']}, verified={bool(row['verified'])}"
        )
    if not read_model.get("capital_hilton_contact_candidates"):
        lines.append("- None.")
    identity = read_model.get("capital_hilton_external_identity_rule") or {}
    if identity:
        lines.extend(
            [
                "",
                "## Capital Hilton External Identity",
                f"- Internal agent: `{identity['internal_agent']}`",
                f"- External persona: `{identity['external_persona']}`",
                "- Draft signature:",
                "```text",
                identity["external_draft_signature"],
                "```",
            ]
        )
    lines.extend(
        [
            "",
            "## Work Board Linkage",
        ]
    )
    for row in (read_model.get("work_board_linkage") or {}).get("cards") or []:
        lines.append(f"- `{row['card_id']}` {row['board_column']}: {row['title']}")
    if not (read_model.get("work_board_linkage") or {}).get("cards"):
        lines.append("- None.")
    lines.extend(["", "## Authority Boundary"])
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`.")
    return "\n".join(lines) + "\n"


def export_finance_invoice_evidence_packets_read_model(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    out_root = _export_root_path(export_root)
    out_root.mkdir(parents=True, exist_ok=True)
    read_model = build_finance_invoice_evidence_packets_read_model(db_path)
    json_path = out_root / JSON_EXPORT_NAME
    operator_path = out_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(_operator_markdown(read_model), encoding="utf-8")
    return {
        "export_version": READ_MODEL_VERSION,
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "packet_count": read_model.get("counts", {}).get("packet_count", 0),
        "missing_items_count": read_model.get("counts", {}).get("missing_items_count", 0),
        "spreadsheet_candidate_known": read_model.get("spreadsheet_candidate_known", False),
        "spreadsheet_ingestion_allowed": read_model.get("spreadsheet_ingestion_allowed", True),
        "no_authority_flags": NO_AUTHORITY_FLAGS,
    }


__all__ = [
    "MAC_SPREADSHEET_FOLDER",
    "MAC_SPREADSHEET_NEXT_LANE",
    "NO_AUTHORITY_FLAGS",
    "READ_MODEL_VERSION",
    "REPORT_SECTIONS",
    "WORKFLOW_KINDS",
    "FinanceInvoicePacketResult",
    "FinancePacketFactInput",
    "build_finance_invoice_evidence_packet",
    "build_finance_invoice_evidence_packet_report",
    "build_finance_invoice_evidence_packets_read_model",
    "export_finance_invoice_evidence_packets_read_model",
    "finance_invoice_evidence_packet_table_names",
    "format_finance_invoice_evidence_packet_report",
    "format_finance_invoice_evidence_packet_result",
    "init_finance_invoice_evidence_packet_schema",
    "parse_amount_arg",
    "parse_fact_arg",
    "spreadsheet_candidate_payload",
    "stable_json",
]
