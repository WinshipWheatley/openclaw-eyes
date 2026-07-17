"""St. Anne's invoice status read model.

This module ingests an operator-provided manual-send receipt as evidence only.
It records that the invoice was sent outside OpenClaw without sending email,
posting ledger entries, marking payment, or granting finance authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_RECEIPT_DIR = Path("/mnt/e/openclaw/artifacts/invoice_workbooks/st_annes/2026-05")
DEFAULT_PDF_PATH = DEFAULT_RECEIPT_DIR / "Invoice_St_Annes_May_2026_OPERATOR_SENT.pdf"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/st_annes_invoice_status.sqlite")

SCHEMA_VERSION = "st_annes_invoice_status_v1"
READ_MODEL_ID = "st_annes_invoice_status"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
SQLITE_SCHEMA_NAME = f"{READ_MODEL_ID}_SCHEMA.sql"
SQLITE_SEED_NAME = f"{READ_MODEL_ID}_SEED.sql"

INVOICE_STATUS = "MANUAL_SEND_OUT_OF_BAND_RECORDED"
EXTERNAL_AGENT_SENT_STATUS = "SENT"
EXTERNAL_AGENT_RECEIPT_SCHEMA_VERSION = "st_annes_external_agent_send_receipt_v0"
CORRECTED_SEND_RECEIPT_SCHEMA_VERSION = (
    "st_annes_external_agent_corrected_send_receipt_v1"
)
CLIENT_REF = "st_annes"
CLIENT_DISPLAY_NAME = "St. Anne's"
INVOICE_PERIOD = "2026-05"
ARTIFACT_KIND = "operator_provided_pdf_invoice"

SAFETY_FLAGS = {
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "openclaw_send_allowed": False,
    "finance_invoice_allowed": False,
    "workbook_mutation_allowed": False,
    "paid": False,
}


@dataclass(frozen=True)
class ExportResult:
    schema_version: str
    read_model_path: str
    bridge_read_model_path: str
    sqlite_path: str
    source_receipt_path: str
    source_pdf_path: str
    source_pdf_sha256: str
    status: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _rooted(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return ROOT / candidate


def find_latest_manual_send_receipt(receipt_dir: Path = DEFAULT_RECEIPT_DIR) -> Path:
    receipts = sorted(
        receipt_dir.glob("st_annes_manual_invoice_sent_receipt_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not receipts:
        raise FileNotFoundError(f"No St. Anne's manual send receipt found in {receipt_dir}")
    return receipts[0]


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON at {path}")
    return payload


def pdf_page_count(path: Path) -> int | None:
    try:
        completed = subprocess.run(
            ["pdfinfo", str(path)],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    for line in completed.stdout.splitlines():
        if line.startswith("Pages:"):
            value = line.split(":", 1)[1].strip()
            return int(value)
    return None


def _validation_error(message: str) -> ValueError:
    return ValueError(f"St. Anne's manual send receipt validation failed: {message}")


def validate_manual_send_receipt(
    receipt: Mapping[str, Any],
    *,
    receipt_path: Path,
    pdf_path: Path,
) -> dict[str, Any]:
    receipt_schema = str(receipt.get("schema_version") or "")
    corrected_send = receipt_schema == CORRECTED_SEND_RECEIPT_SCHEMA_VERSION
    external_agent_send = receipt_schema in {
        EXTERNAL_AGENT_RECEIPT_SCHEMA_VERSION,
        CORRECTED_SEND_RECEIPT_SCHEMA_VERSION,
    }
    attachment = receipt.get("attachment")
    attachment = attachment if isinstance(attachment, Mapping) else {}
    local_artifact_available = attachment.get("local_artifact_available") is not False
    expected_values = {
        "client_ref": CLIENT_REF,
        "sent_by_openclaw": False,
        "manual_send_out_of_band_known": True,
        "email_send_allowed": False,
        "ledger_posting_allowed": False,
        "paid": False,
        "artifact_kind": ARTIFACT_KIND,
    }
    failures: list[str] = []
    for key, expected in expected_values.items():
        if receipt.get(key) != expected:
            failures.append(f"{key} expected {expected!r} got {receipt.get(key)!r}")
    if external_agent_send:
        if receipt.get("status") != EXTERNAL_AGENT_SENT_STATUS:
            failures.append("external-agent receipt status must be SENT")
        invoice_period = str(receipt.get("invoice_period") or "")
        if not re.fullmatch(r"20\d{2}-(?:0[1-9]|1[0-2])", invoice_period):
            failures.append("external-agent receipt invoice_period must be YYYY-MM")
        if receipt.get("service_period") != invoice_period:
            failures.append("external-agent receipt service_period must match invoice_period")
        if str(receipt.get("invoice_number") or "") != "3":
            failures.append("external-agent receipt invoice_number must be 3")
        if receipt.get("amount") != 875:
            failures.append("external-agent receipt amount must be 875")
        if receipt.get("service_count") != 7:
            failures.append("external-agent receipt service_count must be 7")
        if receipt.get("provenance") != "external_agent_send":
            failures.append("external-agent receipt provenance must be external_agent_send")
        if receipt.get("operator_authorized") is not True:
            failures.append("external-agent receipt must be operator authorized")
        if [str(item).casefold() for item in receipt.get("to") or []] != [
            "draper.carter@gmail.com"
        ]:
            failures.append("external-agent receipt recipient must be Draper")
        if sorted(str(item).casefold() for item in receipt.get("cc") or []) != [
            "winshiplive@gmail.com"
        ]:
            failures.append("external-agent receipt CC must be Winship")
        if list(receipt.get("bcc") or []):
            failures.append("external-agent receipt BCC must be empty")
        normalized_subject = re.sub(
            r"\s+",
            " ",
            str(receipt.get("subject") or "").replace("\u2014", "-").strip().casefold(),
        )
        expected_subject = (
            "corrected: st. anne's invoice - june 2026 services"
            if corrected_send
            else "st. anne's invoice - june 2026 services"
        )
        if normalized_subject != expected_subject:
            failures.append("external-agent receipt subject must identify the June 2026 invoice")
        if not str(receipt.get("gmail_message_id") or "").strip():
            failures.append("external-agent receipt gmail_message_id is required")
        try:
            sent_at = datetime.fromisoformat(
                str(receipt.get("sent_at_utc_iso") or "").replace("Z", "+00:00")
            )
        except ValueError:
            sent_at = None
        if sent_at is None or sent_at.tzinfo is None or sent_at.utcoffset() is None:
            failures.append("external-agent receipt sent_at_utc_iso must be timezone-aware")
        downstream = receipt.get("downstream")
        expected_downstream = {
            "draper_forwarded_to_glenn",
            "glenn_acknowledged",
            "check_received",
            "invoice_paid",
        }
        if not isinstance(downstream, Mapping) or set(downstream) != expected_downstream:
            failures.append("external-agent receipt downstream frontier is incomplete")
        elif any(
            not isinstance(downstream.get(key), Mapping)
            or str(downstream[key].get("status") or "").upper() != "UNKNOWN"
            or downstream[key].get("state") != "pending"
            for key in expected_downstream
        ):
            failures.append("external-agent receipt downstream milestones must be UNKNOWN/pending")
        if corrected_send:
            if not str(receipt.get("gmail_thread_id") or "").strip():
                failures.append("corrected receipt gmail_thread_id is required")
            authoritative = receipt.get("authoritative_source")
            authoritative = authoritative if isinstance(authoritative, Mapping) else {}
            authoritative_path = Path(str(authoritative.get("path") or ""))
            authoritative_sha = str(authoritative.get("sha256") or "")
            if not authoritative_path.is_file():
                failures.append("corrected receipt authoritative source is missing")
            elif sha256_file(authoritative_path) != authoritative_sha:
                failures.append("corrected receipt authoritative source sha256 does not match")
            if authoritative.get("gmail_sent_readback_confirmed") is not True:
                failures.append("corrected receipt Gmail sent readback must be confirmed")
            if authoritative.get("attachment_metadata_confirmed") is not True:
                failures.append("corrected receipt attachment metadata must be confirmed")
            superseded = receipt.get("superseded_send")
            superseded = superseded if isinstance(superseded, Mapping) else {}
            if superseded.get("disposition") != "SUPERSEDED":
                failures.append("corrected receipt must preserve the prior send as SUPERSEDED")
            if not str(superseded.get("gmail_message_id") or "").strip():
                failures.append("corrected receipt superseded gmail_message_id is required")
            if not re.fullmatch(r"[0-9a-f]{64}", str(superseded.get("attachment_sha256") or "")):
                failures.append("corrected receipt superseded attachment sha256 is required")
            workbook = receipt.get("workbook_finalization")
            workbook = workbook if isinstance(workbook, Mapping) else {}
            if workbook.get("semantic_diff_passed") is not True:
                failures.append("corrected receipt workbook semantic diff must pass")
            if list(workbook.get("changed_cells") or []) != ["June 2026!G2", "June 2026!G4"]:
                failures.append("corrected receipt workbook changed cells must be G2 and G4 only")
            if not re.fullmatch(r"[0-9a-f]{64}", str(workbook.get("backup_sha256") or "")):
                failures.append("corrected receipt workbook backup sha256 is required")
            closure = receipt.get("loop_closure")
            closure = closure if isinstance(closure, Mapping) else {}
            if closure.get("milestone_ref") != "glenn_acknowledged":
                failures.append("corrected receipt loop closure must target glenn_acknowledged")
            if closure.get("expected_evidence") != "reply_or_note_from_glenn":
                failures.append("corrected receipt expected evidence must be a Glenn reply or note")
    else:
        if receipt.get("status") != INVOICE_STATUS:
            failures.append(
                f"status expected {INVOICE_STATUS!r} got {receipt.get('status')!r}"
            )
        if receipt.get("invoice_period") != INVOICE_PERIOD:
            failures.append(
                f"invoice_period expected {INVOICE_PERIOD!r} got {receipt.get('invoice_period')!r}"
            )

    if local_artifact_available and not pdf_path.exists():
        failures.append(f"PDF missing at {pdf_path}")

    pdf_sha = sha256_file(pdf_path) if local_artifact_available and pdf_path.exists() else ""
    if external_agent_send:
        if local_artifact_available and Path(str(attachment.get("path") or "")).resolve() != pdf_path.resolve():
            failures.append("external-agent receipt attachment path must match the source PDF")
        if not str(attachment.get("filename") or "").strip():
            failures.append("external-agent receipt attachment filename is required")
    receipt_sha = str(receipt.get("sha256") or attachment.get("sha256") or "")
    source_sha = str(receipt.get("source_sha256") or "")
    attachment_sha = str(attachment.get("sha256") or "")
    if corrected_send and receipt_sha != attachment_sha:
        failures.append("corrected receipt attachment sha256 must match receipt sha256")
    if corrected_send and not re.fullmatch(r"[0-9a-f]{64}", receipt_sha):
        failures.append("corrected receipt attachment sha256 is invalid")
    if corrected_send and int(attachment.get("size_bytes") or 0) <= 0:
        failures.append("corrected receipt attachment size is required")
    if pdf_sha and pdf_sha != receipt_sha:
        failures.append(f"PDF sha256 {pdf_sha} does not match receipt sha256 {receipt_sha}")
    if source_sha and pdf_sha and source_sha != pdf_sha:
        failures.append(f"source_sha256 {source_sha} does not match PDF sha256 {pdf_sha}")

    observed_page_count = (
        pdf_page_count(pdf_path)
        if local_artifact_available and pdf_path.exists()
        else int(receipt.get("page_count") or 0) or None
    )
    if observed_page_count != 1:
        failures.append(f"PDF page_count expected 1 got {observed_page_count!r}")
    if receipt.get("page_count") != 1:
        failures.append(f"receipt page_count expected 1 got {receipt.get('page_count')!r}")

    if failures:
        raise _validation_error("; ".join(failures))

    return {
        "receipt_path": str(receipt_path),
        "pdf_path": str(pdf_path) if local_artifact_available else str(attachment.get("path") or ""),
        "pdf_exists": bool(local_artifact_available and pdf_path.exists()),
        "local_artifact_available": local_artifact_available,
        "artifact_validation_mode": (
            "local_file_sha256"
            if local_artifact_available
            else "authoritative_sent_readback"
        ),
        "receipt_status_ok": True,
        "pdf_sha256_matches_receipt": bool(
            local_artifact_available and pdf_sha == receipt_sha
        ),
        "attachment_sha256_receipt_consistent": bool(
            receipt_sha and attachment_sha == receipt_sha
        ),
        "receipt_source_sha256_matches_pdf": bool(
            (not source_sha or source_sha == pdf_sha)
            if local_artifact_available
            else (not source_sha or source_sha == receipt_sha)
        ),
        "observed_page_count": observed_page_count,
        "expected_page_count": 1,
        "page_count_ok": True,
        "field_checks_ok": True,
        "external_agent_send": external_agent_send,
        "corrected_send": corrected_send,
    }


def build_status_payload(
    *,
    receipt_path: Path,
    pdf_path: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    receipt = read_json(receipt_path)
    validation = validate_manual_send_receipt(receipt, receipt_path=receipt_path, pdf_path=pdf_path)
    attachment = receipt.get("attachment")
    attachment = attachment if isinstance(attachment, Mapping) else {}
    local_artifact_available = validation["local_artifact_available"] is True
    pdf_sha = (
        sha256_file(pdf_path)
        if local_artifact_available
        else str(receipt.get("sha256") or attachment.get("sha256") or "")
    )
    source_pdf_path = (
        str(pdf_path)
        if local_artifact_available
        else str(attachment.get("path") or "")
    )
    source_pdf_size = (
        pdf_path.stat().st_size
        if local_artifact_available
        else int(attachment.get("size_bytes") or 0)
    )
    receipt_sha = sha256_file(receipt_path)
    generated_at = generated_at or utc_now()
    invoice_period = str(receipt.get("invoice_period") or INVOICE_PERIOD)
    invoice_status = str(receipt.get("status") or INVOICE_STATUS)
    external_agent_send = validation["external_agent_send"] is True
    recipients = [str(item) for item in receipt.get("to") or []]
    downstream = receipt.get("downstream")
    if not isinstance(downstream, Mapping):
        downstream = {
            "draper_forwarded_to_glenn": {"status": "UNKNOWN", "state": "pending"},
            "glenn_acknowledged": {"status": "UNKNOWN", "state": "pending"},
            "check_received": {"status": "UNKNOWN", "state": "pending"},
            "invoice_paid": {"status": "UNKNOWN", "state": "pending"},
        }

    payload = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "client_ref": CLIENT_REF,
        "client_display_name": CLIENT_DISPLAY_NAME,
        "workflow_ref": "st_annes_invoice_workflow",
        "month": invoice_period,
        "invoice_period": invoice_period,
        "invoice_status": invoice_status,
        "invoice_ref": str(
            receipt.get("invoice_ref")
            or f"ST-ANNES-{invoice_period}-INVOICE-{receipt.get('invoice_number') or 'unknown'}"
        ),
        "payment_status": "NOT_MARKED_PAID",
        "artifact_kind": ARTIFACT_KIND,
        "source_pdf_path": source_pdf_path,
        "source_pdf_sha256": pdf_sha,
        "source_pdf_local_available": local_artifact_available,
        "source_pdf_page_count": 1,
        "source_pdf_file_size_bytes": source_pdf_size,
        "source_receipt_path": str(receipt_path),
        "source_receipt_sha256": receipt_sha,
        "source_receipt_generated_at": str(receipt.get("generated_at") or ""),
        "source_receipt_status": str(receipt.get("status") or ""),
        "status_as_of_utc_iso": str(
            receipt.get("sent_at_utc_iso") or receipt.get("generated_at") or ""
        ),
        "sent_at_utc_iso": str(receipt.get("sent_at_utc_iso") or ""),
        "manual_send_out_of_band_known": True,
        "sent_by_openclaw": False,
        "openclaw_send_performed": False,
        "email_send_performed_by_openclaw": False,
        "pdf_export_performed_by_openclaw": False,
        "source_workbook_mutated_by_openclaw": False,
        "ledger_mutation_performed": False,
        "browser_or_coupa_submit_performed": False,
        "paid": False,
        "recipient": recipients[0] if recipients else "",
        "to": recipients,
        "cc": [str(item) for item in receipt.get("cc") or []],
        "bcc": [str(item) for item in receipt.get("bcc") or []],
        "subject": str(receipt.get("subject") or ""),
        "gmail_message_id": str(receipt.get("gmail_message_id") or ""),
        "gmail_thread_id": str(receipt.get("gmail_thread_id") or ""),
        "send_provenance": str(receipt.get("provenance") or "manual_out_of_band"),
        "operator_authorized": receipt.get("operator_authorized") is True,
        "invoice_number": str(receipt.get("invoice_number") or ""),
        "amount": receipt.get("amount"),
        "service_count": receipt.get("service_count"),
        "downstream": {key: dict(value) for key, value in downstream.items()},
        "supersedes": dict(
            receipt.get("superseded_send")
            or receipt.get("supersedes")
            or {}
        ),
        "send_history": (
            [
                dict(receipt.get("superseded_send") or {}),
                {
                    "disposition": "OPERATIVE",
                    "gmail_message_id": str(receipt.get("gmail_message_id") or ""),
                    "gmail_thread_id": str(receipt.get("gmail_thread_id") or ""),
                    "sent_at_utc_iso": str(receipt.get("sent_at_utc_iso") or ""),
                    "subject": str(receipt.get("subject") or ""),
                    "attachment_filename": str(attachment.get("filename") or ""),
                    "attachment_sha256": pdf_sha,
                },
            ]
            if validation["corrected_send"] is True
            else []
        ),
        "workbook_finalization": dict(receipt.get("workbook_finalization") or {}),
        "loop_closure": dict(receipt.get("loop_closure") or {}),
        "authoritative_source": dict(receipt.get("authoritative_source") or {}),
        "ledger_posting_allowed": False,
        "email_send_allowed": False,
        "safety_flags": dict(SAFETY_FLAGS),
        "authority_boundary": dict(SAFETY_FLAGS),
        "line_item_checks": receipt.get("line_item_checks") if isinstance(receipt.get("line_item_checks"), dict) else {},
        "line_items_verified": bool(receipt.get("line_items_verified")),
        "invoice_amount_summary": {
            "may_service_subtotal_observed": bool(receipt.get("may_service_subtotal_observed")),
            "prior_balance_observed": bool(receipt.get("prior_balance_observed")),
            "total_outstanding_observed": bool(receipt.get("total_outstanding_observed")),
        },
        "validation": validation,
        "machine_proof": {
            "manual_send_out_of_band_recorded": True,
            "reconciliation_record_only": external_agent_send,
            "external_agent_send_provenance": external_agent_send,
            "operator_authorized_fact": receipt.get("operator_authorized") is True,
            "openclaw_send_performed": False,
            "ledger_mutation_performed": False,
            "paid_false": True,
            "email_send_allowed_false": True,
            "ledger_posting_allowed_false": True,
            "pdf_exists": bool(local_artifact_available),
            "local_pdf_inspected": bool(local_artifact_available),
            "artifact_metadata_receipt_verified": validation["artifact_validation_mode"] == "authoritative_sent_readback",
            "pdf_page_count_is_one": True,
            "pdf_sha256_matches_receipt": validation["pdf_sha256_matches_receipt"],
            "source_pdf_sha256_matches_receipt": validation["receipt_source_sha256_matches_pdf"],
            "attachment_sha256_receipt_consistent": validation["attachment_sha256_receipt_consistent"],
            "business_authority_flags_false": all(value is False for value in SAFETY_FLAGS.values()),
        },
        "next_safe_move": (
            "Await observed Glenn reply or note evidence. Keep forward, acknowledgment, check, and paid milestones pending; do not send or mark paid."
            if validation["corrected_send"] is True
            else "Await Draper's verified forward to Glenn. Monitoring only; do not mark paid or send."
            if external_agent_send
            else "Use this read model as manual-send evidence only; do not mark paid or post ledger without separate proof and approval."
        ),
    }
    payload["content_hash"] = "sha256:" + _sha256_bytes(stable_json(payload).encode("utf-8"))
    return payload


def sqlite_schema_sql() -> str:
    return """CREATE TABLE IF NOT EXISTS st_annes_invoice_status_receipt (
  receipt_sha256 TEXT PRIMARY KEY,
  generated_at TEXT NOT NULL,
  client_ref TEXT NOT NULL,
  invoice_period TEXT NOT NULL,
  invoice_status TEXT NOT NULL,
  source_receipt_path TEXT NOT NULL,
  source_pdf_path TEXT NOT NULL,
  source_pdf_sha256 TEXT NOT NULL,
  source_pdf_page_count INTEGER NOT NULL,
  openclaw_send_performed INTEGER NOT NULL CHECK(openclaw_send_performed IN (0, 1)),
  email_send_allowed INTEGER NOT NULL CHECK(email_send_allowed IN (0, 1)),
  ledger_posting_allowed INTEGER NOT NULL CHECK(ledger_posting_allowed IN (0, 1)),
  paid INTEGER NOT NULL CHECK(paid IN (0, 1)),
  payload_json TEXT NOT NULL
);
"""


def _sql_literal(value: object) -> str:
    text = str(value)
    return "'" + text.replace("'", "''") + "'"


def sqlite_seed_sql(payload: Mapping[str, Any]) -> str:
    return (
        "INSERT OR REPLACE INTO st_annes_invoice_status_receipt "
        "(receipt_sha256, generated_at, client_ref, invoice_period, invoice_status, "
        "source_receipt_path, source_pdf_path, source_pdf_sha256, source_pdf_page_count, "
        "openclaw_send_performed, email_send_allowed, ledger_posting_allowed, paid, payload_json) "
        "VALUES ("
        f"{_sql_literal(payload['source_receipt_sha256'])}, "
        f"{_sql_literal(payload['generated_at'])}, "
        f"{_sql_literal(payload['client_ref'])}, "
        f"{_sql_literal(payload['invoice_period'])}, "
        f"{_sql_literal(payload['invoice_status'])}, "
        f"{_sql_literal(payload['source_receipt_path'])}, "
        f"{_sql_literal(payload['source_pdf_path'])}, "
        f"{_sql_literal(payload['source_pdf_sha256'])}, "
        f"{int(payload['source_pdf_page_count'])}, "
        "0, 0, 0, 0, "
        f"{_sql_literal(stable_json(payload))}"
        ");\n"
    )


def record_sqlite_receipt(payload: Mapping[str, Any], sqlite_path: Path) -> None:
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.executescript(sqlite_schema_sql())
        conn.execute(
            """
            INSERT OR REPLACE INTO st_annes_invoice_status_receipt (
              receipt_sha256,
              generated_at,
              client_ref,
              invoice_period,
              invoice_status,
              source_receipt_path,
              source_pdf_path,
              source_pdf_sha256,
              source_pdf_page_count,
              openclaw_send_performed,
              email_send_allowed,
              ledger_posting_allowed,
              paid,
              payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, ?)
            """,
            (
                str(payload["source_receipt_sha256"]),
                str(payload["generated_at"]),
                str(payload["client_ref"]),
                str(payload["invoice_period"]),
                str(payload["invoice_status"]),
                str(payload["source_receipt_path"]),
                str(payload["source_pdf_path"]),
                str(payload["source_pdf_sha256"]),
                int(payload["source_pdf_page_count"]),
                stable_json(payload),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def write_sql_support_files(payload: Mapping[str, Any], sqlite_path: Path) -> None:
    schema_path = sqlite_path.with_name(SQLITE_SCHEMA_NAME)
    seed_path = sqlite_path.with_name(SQLITE_SEED_NAME)
    schema_path.write_text(sqlite_schema_sql(), encoding="utf-8")
    seed_path.write_text(sqlite_seed_sql(payload), encoding="utf-8")


def export_st_annes_invoice_status(
    *,
    receipt_path: Path | None = None,
    pdf_path: Path = DEFAULT_PDF_PATH,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path = DEFAULT_BRIDGE_EXPORT_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> ExportResult:
    receipt_path = receipt_path or find_latest_manual_send_receipt()
    payload = build_status_payload(receipt_path=receipt_path, pdf_path=pdf_path, generated_at=generated_at)

    local_export_root = _rooted(export_root)
    local_export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = local_export_root / JSON_EXPORT_NAME
    read_model_path.write_text(stable_json(payload), encoding="utf-8")

    bridge_export_root.mkdir(parents=True, exist_ok=True)
    bridge_read_model_path = bridge_export_root / JSON_EXPORT_NAME
    bridge_read_model_path.write_text(stable_json(payload), encoding="utf-8")

    resolved_sqlite_path = _rooted(sqlite_path)
    record_sqlite_receipt(payload, resolved_sqlite_path)
    write_sql_support_files(payload, resolved_sqlite_path)

    return ExportResult(
        schema_version=SCHEMA_VERSION,
        read_model_path=str(read_model_path),
        bridge_read_model_path=str(bridge_read_model_path),
        sqlite_path=str(resolved_sqlite_path),
        source_receipt_path=str(receipt_path),
        source_pdf_path=str(payload["source_pdf_path"]),
        source_pdf_sha256=str(payload["source_pdf_sha256"]),
        status=str(payload["invoice_status"]),
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest St. Anne's manual-send receipt into local read models.")
    parser.add_argument("--receipt-path", help="Manual send receipt JSON path. Defaults to latest receipt in bridge folder.")
    parser.add_argument("--pdf-path", default=str(DEFAULT_PDF_PATH), help="Operator-provided sent PDF path.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Local read model export root.")
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT), help="Bridge read model export root.")
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH), help="Local SQLite receipt path.")
    parser.add_argument("--generated-at", help="Override generated_at timestamp for deterministic tests.")
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    receipt_path = Path(args.receipt_path) if args.receipt_path else None
    result = export_st_annes_invoice_status(
        receipt_path=receipt_path,
        pdf_path=Path(args.pdf_path),
        export_root=Path(args.export_root),
        bridge_export_root=Path(args.bridge_export_root),
        sqlite_path=Path(args.sqlite_path),
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(
            stable_json(
                {
                    "status": result.status,
                    "read_model_path": result.read_model_path,
                    "bridge_read_model_path": result.bridge_read_model_path,
                    "sqlite_path": result.sqlite_path,
                    "source_receipt_path": result.source_receipt_path,
                    "source_pdf_path": result.source_pdf_path,
                    "source_pdf_sha256": result.source_pdf_sha256,
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
