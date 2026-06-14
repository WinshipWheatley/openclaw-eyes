"""Capital Hilton operator-run invoice status read model.

This module records an operator-assisted invoice run from local receipt files.
It does not submit Coupa, send email, mutate a ledger, or mark paid.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = Path("/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/capital_hilton_invoice_operator_run_status.sqlite")

SCHEMA_VERSION = "capital_hilton_invoice_operator_run_status_v1"
READ_MODEL_ID = "capital_hilton_invoice_operator_run_status"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
SQLITE_SCHEMA_NAME = f"{READ_MODEL_ID}_SCHEMA.sql"
SQLITE_SEED_NAME = f"{READ_MODEL_ID}_SEED.sql"
RECORDED_STATUS = "CAPITAL_HILTON_OPERATOR_RUN_RECORDED"

RECEIPT_PATTERN = "capital_hilton_invoice_operator_run_receipt_*.json"
REPORT_PATTERN = "capital_hilton_invoice_operator_run_report_*.md"
FULL_REPORT_PATTERN = "capital_hilton_invoice_operator_run_full_automation_report_*.md"
TIMESTAMP_RE = re.compile(r"_(\d{8}T\d{6}Z)\.")

AUTHORITY_FLAGS = {
    "coupa_submit_allowed": False,
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "paid_marking_allowed": False,
    "invoice_creation_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
}


@dataclass(frozen=True)
class SourcePair:
    receipt_path: Path
    run_report_path: Path
    timestamp: str


@dataclass(frozen=True)
class ExportResult:
    schema_version: str
    read_model_path: str
    bridge_read_model_path: str
    sqlite_path: str
    receipt_path: str
    run_report_path: str
    full_automation_report_path: str
    submitted_status: str
    email_status: str
    ledger_mutation_performed: bool
    paid: bool


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rooted(path: Path) -> Path:
    if path.is_absolute():
        return path
    return ROOT / path


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON at {path}")
    return payload


def _timestamp_from_name(path: Path) -> str:
    match = TIMESTAMP_RE.search(path.name)
    if not match:
        raise ValueError(f"Could not extract timestamp from {path.name}")
    return match.group(1)


def _bridge_path_from_mac_path(value: str) -> str:
    if value.startswith("/Volumes/openclaw_e/"):
        return "/mnt/e/openclaw/" + value.removeprefix("/Volumes/openclaw_e/")
    return value


def _resolve_pdf_path(receipt: Mapping[str, Any]) -> Path | None:
    for key in ("pc_bridge_pdf_path", "bridge_pdf_path", "pdf_path", "email_attachment_path"):
        value = str(receipt.get(key) or "").strip()
        if not value:
            continue
        translated = _bridge_path_from_mac_path(value)
        path = Path(translated)
        if path.exists() or key in {"pc_bridge_pdf_path", "bridge_pdf_path"}:
            return path
    return None


def _resolve_full_automation_report_path(receipt: Mapping[str, Any], input_dir: Path) -> Path | None:
    for key in ("pc_full_automation_report_path", "full_automation_report_path"):
        value = str(receipt.get(key) or "").strip()
        if not value:
            continue
        path = Path(_bridge_path_from_mac_path(value))
        if path.exists() or key == "pc_full_automation_report_path":
            return path
    reports = sorted(Path(input_dir).glob(FULL_REPORT_PATTERN), key=_timestamp_from_name)
    return reports[-1] if reports else None


def _source_status(receipt: Mapping[str, Any]) -> str:
    return str(receipt.get("status") or "")


def find_latest_source_pair(input_dir: Path = DEFAULT_INPUT_DIR) -> SourcePair:
    receipts = sorted(Path(input_dir).glob(RECEIPT_PATTERN), key=_timestamp_from_name)
    if not receipts:
        raise FileNotFoundError(f"No receipt matching {RECEIPT_PATTERN} in {input_dir}")
    receipt_path = receipts[-1]
    timestamp = _timestamp_from_name(receipt_path)
    report_path = Path(input_dir) / f"capital_hilton_invoice_operator_run_report_{timestamp}.md"
    if not report_path.exists():
        reports = sorted(Path(input_dir).glob(REPORT_PATTERN), key=_timestamp_from_name)
        report_names = ", ".join(path.name for path in reports) or "none"
        raise FileNotFoundError(f"No matching run report for {receipt_path.name}; available reports: {report_names}")
    return SourcePair(receipt_path=receipt_path, run_report_path=report_path, timestamp=timestamp)


def _validate_false(receipt: Mapping[str, Any], key: str, failures: list[str]) -> None:
    if receipt.get(key) is not False:
        failures.append(f"{key} expected false got {receipt.get(key)!r}")


def validate_operator_run_receipt(
    receipt: Mapping[str, Any],
    *,
    receipt_path: Path,
    run_report_path: Path,
    full_automation_report_path: Path | None,
    pdf_path: Path | None,
) -> dict[str, Any]:
    failures: list[str] = []
    if receipt.get("client_ref") != "capital_hilton":
        failures.append(f"client_ref expected capital_hilton got {receipt.get('client_ref')!r}")
    if receipt.get("may_29_corrected") is not True:
        failures.append("may_29_corrected expected true")
    if receipt.get("pdf_exported") is not True:
        failures.append("pdf_exported expected true")
    if receipt.get("coupa_submission_recorded") is not True and receipt.get("coupa_submitted") is not True:
        failures.append("Coupa submission was not recorded")
    if receipt.get("email_to_annette_recorded") is not True and receipt.get("email_to_annette_sent") is not True:
        failures.append("Email to Annette was not recorded")
    _validate_false(receipt, "ledger_mutation_performed", failures)
    _validate_false(receipt, "paid", failures)
    _validate_false(receipt, "autonomous_openclaw_coupa_submit", failures)
    _validate_false(receipt, "autonomous_openclaw_email_send", failures)

    if not receipt_path.exists():
        failures.append(f"receipt path missing: {receipt_path}")
    if not run_report_path.exists():
        failures.append(f"run report path missing: {run_report_path}")

    full_report_expected = any(
        str(receipt.get(key) or "").strip()
        for key in ("pc_full_automation_report_path", "full_automation_report_path")
    )
    full_report_present = False
    full_report_sha256 = ""
    if full_automation_report_path is not None:
        if not full_automation_report_path.exists():
            failures.append(f"full automation report path missing: {full_automation_report_path}")
        else:
            full_report_present = True
            full_report_sha256 = sha256_file(full_automation_report_path)
    elif full_report_expected:
        failures.append("full automation report path expected but could not be resolved")

    pdf_present = False
    pdf_sha256 = ""
    if pdf_path is not None:
        if not pdf_path.exists():
            failures.append(f"PDF path from receipt does not exist: {pdf_path}")
        else:
            pdf_present = True
            pdf_sha256 = sha256_file(pdf_path)
            receipt_sha = str(receipt.get("pdf_sha256") or receipt.get("email_attachment_sha256") or "")
            if receipt_sha and pdf_sha256 != receipt_sha:
                failures.append("PDF sha256 does not match receipt")

    source_status = _source_status(receipt)
    if not source_status:
        failures.append("receipt status is missing")

    if failures:
        raise ValueError("; ".join(failures))

    return {
        "receipt_path": str(receipt_path),
        "receipt_sha256": sha256_file(receipt_path),
        "run_report_path": str(run_report_path),
        "run_report_sha256": sha256_file(run_report_path),
        "full_automation_report_path": str(full_automation_report_path) if full_automation_report_path else "",
        "full_automation_report_present": full_report_present,
        "full_automation_report_sha256": full_report_sha256,
        "source_status": source_status,
        "pdf_path": str(pdf_path) if pdf_path is not None else "",
        "pdf_present": pdf_present,
        "pdf_sha256": pdf_sha256,
        "source_pdf_sha256": str(receipt.get("pdf_sha256") or ""),
        "pdf_page_count": receipt.get("pdf_page_count"),
        "source_files_validated": True,
    }


def _report_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def build_automation_report_summary(
    receipt: Mapping[str, Any],
    *,
    full_automation_report_path: Path | None,
) -> dict[str, Any]:
    report_text = _report_text(full_automation_report_path).lower()
    automation_notes = receipt.get("automation_notes") if isinstance(receipt.get("automation_notes"), list) else []
    note_text = "\n".join(str(note) for note in automation_notes).lower()
    combined = report_text + "\n" + note_text
    workbook_invoice_number = str(receipt.get("workbook_invoice_number") or "")
    coupa_invoice_number = str(receipt.get("coupa_invoice_number") or "")
    invoice_number_portal_normalized = bool(
        workbook_invoice_number
        and coupa_invoice_number
        and workbook_invoice_number != coupa_invoice_number
    )

    return {
        "full_automation_report_recorded": bool(full_automation_report_path and full_automation_report_path.exists()),
        "workbook_baseline_and_cell_mutation_recorded": "initial workbook metadata" in combined
        or "cell:" in combined,
        "excel_direct_export_success_without_pdf_recorded": "direct excel/applescript" in combined
        and "did not create" in combined,
        "excel_helper_open_workbook_fragility_recorded": "open_workbook" in combined,
        "print_to_pdf_ui_worked": "print-to-pdf" in combined,
        "artifact_validation_checks_recorded": "sha256" in combined and "page count" in combined,
        "openpyxl_missing_recorded": "openpyxl" in combined,
        "coupa_po_route_recorded": "create invoice from po" in combined,
        "remit_to_business_gate_recorded": "remit-to" in combined and "business decision" in combined,
        "coupa_field_reset_after_remit_to_recorded": "cleared the invoice number" in combined,
        "browser_virtual_clipboard_issue_recorded": "virtual clipboard" in combined,
        "invoice_number_portal_normalized": invoice_number_portal_normalized,
        "invoice_number_normalization_reason": "Hilton Coupa disallows special characters"
        if invoice_number_portal_normalized
        else "",
        "gmail_replacement_draft_recorded": "draft with attachment was recreated" in combined,
        "automation_backlog_recorded": "automation backlog" in combined,
    }


def build_read_model(
    *,
    input_dir: Path = DEFAULT_INPUT_DIR,
    generated_at: str | None = None,
) -> dict[str, Any]:
    pair = find_latest_source_pair(input_dir)
    receipt = _read_json(pair.receipt_path)
    pdf_path = _resolve_pdf_path(receipt)
    full_automation_report_path = _resolve_full_automation_report_path(receipt, input_dir)
    validation = validate_operator_run_receipt(
        receipt,
        receipt_path=pair.receipt_path,
        run_report_path=pair.run_report_path,
        full_automation_report_path=full_automation_report_path,
        pdf_path=pdf_path,
    )
    generated_at = generated_at or utc_now()
    coupa_status = str(receipt.get("coupa_status_observed") or "")
    email_sent = bool(receipt.get("email_to_annette_sent") or receipt.get("email_send_performed"))
    automation_report_summary = build_automation_report_summary(
        receipt,
        full_automation_report_path=full_automation_report_path,
    )
    automation_notes = receipt.get("automation_notes") if isinstance(receipt.get("automation_notes"), list) else []
    payload = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": RECORDED_STATUS,
        "world": "invoice_operations",
        "client_ref": "capital_hilton",
        "client_display_name": "Capital Hilton",
        "workflow_ref": str(receipt.get("workflow_ref") or "capital_hilton_invoice_operator_run"),
        "source_receipt_status": validation["source_status"],
        "operator_assisted": bool(receipt.get("operator_assisted")),
        "may_29_corrected": True,
        "corrected_cell": str(receipt.get("cell_changed") or ""),
        "cell_before": str(receipt.get("cell_before") or ""),
        "cell_after": str(receipt.get("cell_after") or ""),
        "future_gig_preserved": bool(receipt.get("june_5_future_gig_preserved")),
        "future_gig_cell": str(receipt.get("future_gig_cell") or ""),
        "future_gig_value": str(receipt.get("future_gig_value") or ""),
        "pdf_exported": True,
        "pdf_page_count": validation["pdf_page_count"],
        "pdf_sha256": validation["pdf_sha256"],
        "full_automation_report_recorded": validation["full_automation_report_present"],
        "workbook_invoice_number": str(receipt.get("workbook_invoice_number") or ""),
        "coupa_invoice_number": str(receipt.get("coupa_invoice_number") or ""),
        "invoice_number_portal_normalized": automation_report_summary["invoice_number_portal_normalized"],
        "invoice_number_normalization_reason": automation_report_summary["invoice_number_normalization_reason"],
        "invoice_number_note": str(receipt.get("invoice_number_note") or ""),
        "invoice_total": str(receipt.get("invoice_total") or ""),
        "coupa_submission_recorded": True,
        "coupa_submitted": bool(receipt.get("coupa_submitted")),
        "coupa_submission_status": coupa_status.lower() if coupa_status else "",
        "coupa_status_observed": coupa_status,
        "coupa_po_number": str(receipt.get("coupa_po_number") or ""),
        "coupa_customer": str(receipt.get("coupa_customer") or ""),
        "coupa_internal_invoice_id": str(receipt.get("coupa_internal_invoice_id") or ""),
        "coupa_confirmation_ref": str(receipt.get("coupa_confirmation_ref") or ""),
        "remit_to_selected": str(receipt.get("remit_to_selected") or ""),
        "remit_to_choice": str(receipt.get("remit_to_choice") or ""),
        "bank_remit_to_selected": bool(receipt.get("bank_remit_to_selected")),
        "email_to_annette_recorded": True,
        "email_to_annette_sent": email_sent,
        "email_status": "sent_operator_assisted" if email_sent else "not_recorded",
        "email_to": list(receipt.get("email_to") or []),
        "email_cc": list(receipt.get("email_cc") or []),
        "email_subject": str(receipt.get("email_subject") or ""),
        "sent_gmail_message_id": str(receipt.get("sent_gmail_message_id") or ""),
        "sent_gmail_thread_id": str(receipt.get("sent_gmail_thread_id") or ""),
        "autonomous_openclaw_coupa_submit": False,
        "autonomous_openclaw_email_send": False,
        "ledger_mutation_performed": False,
        "ledger_posting_allowed": False,
        "paid": False,
        "paid_marking_performed": False,
        "payment_received_recorded": False,
        "authority_boundary": dict(AUTHORITY_FLAGS),
        "automation_notes": [str(note) for note in automation_notes],
        "automation_report_summary": automation_report_summary,
        "artifact_refs": {
            "receipt": {
                "path": validation["receipt_path"],
                "sha256": validation["receipt_sha256"],
                "kind": "operator_run_receipt",
            },
            "run_report": {
                "path": validation["run_report_path"],
                "sha256": validation["run_report_sha256"],
                "kind": "operator_run_report",
            },
            "full_automation_report": {
                "path": validation["full_automation_report_path"],
                "sha256": validation["full_automation_report_sha256"],
                "kind": "operator_run_full_automation_report",
                "present": validation["full_automation_report_present"],
            },
            "pdf": {
                "path": validation["pdf_path"],
                "sha256": validation["pdf_sha256"],
                "kind": "operator_run_invoice_pdf",
                "present": validation["pdf_present"],
                "page_count": validation["pdf_page_count"],
            },
        },
        "proof_refs": {
            "collapsed_by_default": True,
            "receipt_ref": validation["receipt_path"],
            "run_report_ref": validation["run_report_path"],
            "full_automation_report_ref": validation["full_automation_report_path"],
            "pdf_ref": validation["pdf_path"],
        },
        "source_path_normalization": {
            "run_report_path": _bridge_path_from_mac_path(str(receipt.get("run_report_path") or "")),
            "full_automation_report_path": _bridge_path_from_mac_path(
                str(receipt.get("full_automation_report_path") or "")
            ),
            "pc_full_automation_report_path": str(receipt.get("pc_full_automation_report_path") or ""),
            "bridge_pdf_path": _bridge_path_from_mac_path(str(receipt.get("bridge_pdf_path") or "")),
            "pc_bridge_pdf_path": str(receipt.get("pc_bridge_pdf_path") or ""),
        },
        "machine_proof": {
            "receipt_parsed": True,
            "run_report_found": True,
            "full_automation_report_found": validation["full_automation_report_present"],
            "automation_report_compact_summary_recorded": automation_report_summary["full_automation_report_recorded"],
            "may_29_corrected": True,
            "pdf_exported": True,
            "pdf_exists": validation["pdf_present"],
            "pdf_sha256_matches_receipt": validation["pdf_sha256"] == validation["source_pdf_sha256"],
            "coupa_submission_recorded": True,
            "invoice_number_portal_normalized": automation_report_summary["invoice_number_portal_normalized"],
            "email_to_annette_recorded": True,
            "autonomous_openclaw_coupa_submit_false": True,
            "autonomous_openclaw_email_send_false": True,
            "ledger_mutation_performed_false": True,
            "paid_false": True,
            "authority_flags_all_false": all(value is False for value in AUTHORITY_FLAGS.values()),
            "raw_message_body_excluded": True,
        },
        "next_safe_action": "Operator may review recorded submission/email evidence; OpenClaw is not authorized to submit, send, post ledger, or mark paid from this read model.",
        "validation": validation,
    }
    payload["machine_proof"]["raw_message_body_excluded"] = "email_body" not in payload
    payload["content_hash"] = "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()
    return payload


def sqlite_schema_sql() -> str:
    return """CREATE TABLE IF NOT EXISTS capital_hilton_invoice_operator_run_status (
  receipt_sha256 TEXT PRIMARY KEY,
  generated_at TEXT NOT NULL,
  client_ref TEXT NOT NULL,
  workflow_ref TEXT NOT NULL,
  source_receipt_status TEXT NOT NULL,
  coupa_status_observed TEXT NOT NULL,
  workbook_invoice_number TEXT NOT NULL,
  coupa_invoice_number TEXT NOT NULL,
  invoice_number_portal_normalized INTEGER NOT NULL CHECK(invoice_number_portal_normalized IN (0, 1)),
  full_automation_report_path TEXT NOT NULL,
  full_automation_report_sha256 TEXT NOT NULL,
  run_report_path TEXT NOT NULL,
  pdf_path TEXT NOT NULL,
  pdf_sha256 TEXT NOT NULL,
  email_status TEXT NOT NULL,
  ledger_mutation_performed INTEGER NOT NULL CHECK(ledger_mutation_performed IN (0, 1)),
  paid INTEGER NOT NULL CHECK(paid IN (0, 1)),
  authority_flags_all_false INTEGER NOT NULL CHECK(authority_flags_all_false IN (0, 1)),
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS capital_hilton_invoice_operator_run_learning (
  receipt_sha256 TEXT NOT NULL,
  learning_key TEXT NOT NULL,
  learning_value TEXT NOT NULL,
  PRIMARY KEY (receipt_sha256, learning_key),
  FOREIGN KEY (receipt_sha256)
    REFERENCES capital_hilton_invoice_operator_run_status(receipt_sha256)
    ON DELETE CASCADE
);
"""


def _sql_literal(value: object) -> str:
    text = str(value)
    return "'" + text.replace("'", "''") + "'"


def sqlite_seed_sql(payload: Mapping[str, Any]) -> str:
    receipt_sha = str(payload["artifact_refs"]["receipt"]["sha256"])
    authority_flags_all_false = int(bool(payload["machine_proof"]["authority_flags_all_false"]))
    return (
        "INSERT OR REPLACE INTO capital_hilton_invoice_operator_run_status "
        "(receipt_sha256, generated_at, client_ref, workflow_ref, source_receipt_status, "
        "coupa_status_observed, workbook_invoice_number, coupa_invoice_number, "
        "invoice_number_portal_normalized, full_automation_report_path, full_automation_report_sha256, "
        "run_report_path, pdf_path, pdf_sha256, email_status, ledger_mutation_performed, paid, "
        "authority_flags_all_false, payload_json) VALUES ("
        f"{_sql_literal(receipt_sha)}, "
        f"{_sql_literal(payload['generated_at'])}, "
        f"{_sql_literal(payload['client_ref'])}, "
        f"{_sql_literal(payload['workflow_ref'])}, "
        f"{_sql_literal(payload['source_receipt_status'])}, "
        f"{_sql_literal(payload['coupa_status_observed'])}, "
        f"{_sql_literal(payload['workbook_invoice_number'])}, "
        f"{_sql_literal(payload['coupa_invoice_number'])}, "
        f"{int(bool(payload['invoice_number_portal_normalized']))}, "
        f"{_sql_literal(payload['artifact_refs']['full_automation_report']['path'])}, "
        f"{_sql_literal(payload['artifact_refs']['full_automation_report']['sha256'])}, "
        f"{_sql_literal(payload['artifact_refs']['run_report']['path'])}, "
        f"{_sql_literal(payload['artifact_refs']['pdf']['path'])}, "
        f"{_sql_literal(payload['artifact_refs']['pdf']['sha256'])}, "
        f"{_sql_literal(payload['email_status'])}, "
        "0, 0, "
        f"{authority_flags_all_false}, "
        f"{_sql_literal(stable_json(payload))}"
        ");\n"
        + "".join(
            "INSERT OR REPLACE INTO capital_hilton_invoice_operator_run_learning "
            "(receipt_sha256, learning_key, learning_value) VALUES ("
            f"{_sql_literal(receipt_sha)}, {_sql_literal(key)}, {_sql_literal(value)});\n"
            for key, value in payload["automation_report_summary"].items()
        )
    )


def record_sqlite_receipt(payload: Mapping[str, Any], sqlite_path: Path) -> None:
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_sha = str(payload["artifact_refs"]["receipt"]["sha256"])
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.executescript(sqlite_schema_sql())
        conn.execute(
            """
            INSERT OR REPLACE INTO capital_hilton_invoice_operator_run_status (
              receipt_sha256,
              generated_at,
              client_ref,
              workflow_ref,
              source_receipt_status,
              coupa_status_observed,
              workbook_invoice_number,
              coupa_invoice_number,
              invoice_number_portal_normalized,
              full_automation_report_path,
              full_automation_report_sha256,
              run_report_path,
              pdf_path,
              pdf_sha256,
              email_status,
              ledger_mutation_performed,
              paid,
              authority_flags_all_false,
              payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
            """,
            (
                receipt_sha,
                str(payload["generated_at"]),
                str(payload["client_ref"]),
                str(payload["workflow_ref"]),
                str(payload["source_receipt_status"]),
                str(payload["coupa_status_observed"]),
                str(payload["workbook_invoice_number"]),
                str(payload["coupa_invoice_number"]),
                int(bool(payload["invoice_number_portal_normalized"])),
                str(payload["artifact_refs"]["full_automation_report"]["path"]),
                str(payload["artifact_refs"]["full_automation_report"]["sha256"]),
                str(payload["artifact_refs"]["run_report"]["path"]),
                str(payload["artifact_refs"]["pdf"]["path"]),
                str(payload["artifact_refs"]["pdf"]["sha256"]),
                str(payload["email_status"]),
                int(bool(payload["machine_proof"]["authority_flags_all_false"])),
                stable_json(payload),
            ),
        )
        conn.execute(
            "DELETE FROM capital_hilton_invoice_operator_run_learning WHERE receipt_sha256 = ?",
            (receipt_sha,),
        )
        conn.executemany(
            """
            INSERT OR REPLACE INTO capital_hilton_invoice_operator_run_learning (
              receipt_sha256,
              learning_key,
              learning_value
            )
            VALUES (?, ?, ?)
            """,
            [
                (receipt_sha, str(key), str(value))
                for key, value in payload["automation_report_summary"].items()
            ],
        )
        conn.commit()
    finally:
        conn.close()


def write_sql_support_files(payload: Mapping[str, Any], sqlite_path: Path) -> None:
    schema_path = sqlite_path.with_name(SQLITE_SCHEMA_NAME)
    seed_path = sqlite_path.with_name(SQLITE_SEED_NAME)
    schema_path.write_text(sqlite_schema_sql(), encoding="utf-8")
    seed_path.write_text(sqlite_seed_sql(payload), encoding="utf-8")


def export_read_model(
    *,
    input_dir: Path = DEFAULT_INPUT_DIR,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path = DEFAULT_BRIDGE_EXPORT_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> ExportResult:
    payload = build_read_model(input_dir=input_dir, generated_at=generated_at)
    local_root = _rooted(export_root)
    local_root.mkdir(parents=True, exist_ok=True)
    read_model_path = local_root / JSON_EXPORT_NAME
    read_model_path.write_text(stable_json(payload), encoding="utf-8")

    bridge_export_root.mkdir(parents=True, exist_ok=True)
    bridge_path = bridge_export_root / JSON_EXPORT_NAME
    bridge_path.write_text(stable_json(payload), encoding="utf-8")

    resolved_sqlite_path = _rooted(sqlite_path)
    record_sqlite_receipt(payload, resolved_sqlite_path)
    write_sql_support_files(payload, resolved_sqlite_path)

    return ExportResult(
        schema_version=SCHEMA_VERSION,
        read_model_path=str(read_model_path),
        bridge_read_model_path=str(bridge_path),
        sqlite_path=str(resolved_sqlite_path),
        receipt_path=payload["artifact_refs"]["receipt"]["path"],
        run_report_path=payload["artifact_refs"]["run_report"]["path"],
        full_automation_report_path=payload["artifact_refs"]["full_automation_report"]["path"],
        submitted_status=str(payload["coupa_status_observed"] or payload["source_receipt_status"]),
        email_status=str(payload["email_status"]),
        ledger_mutation_performed=bool(payload["ledger_mutation_performed"]),
        paid=bool(payload["paid"]),
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest Capital Hilton operator-run invoice receipt.")
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_read_model(
        input_dir=Path(args.input_dir),
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
                    "status": RECORDED_STATUS,
                    "receipt_path": result.receipt_path,
                    "run_report_path": result.run_report_path,
                    "full_automation_report_path": result.full_automation_report_path,
                    "read_model_path": result.read_model_path,
                    "bridge_read_model_path": result.bridge_read_model_path,
                    "sqlite_path": result.sqlite_path,
                    "submitted_status": result.submitted_status,
                    "email_status": result.email_status,
                    "ledger_mutation_performed": result.ledger_mutation_performed,
                    "paid": result.paid,
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
