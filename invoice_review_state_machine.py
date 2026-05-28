"""Invoice review state machine v0.

Local receipt-backed progress for invoice review guided actions. This module
does not access Coupa/browser/Gmail, send email, generate/export invoices, read
workbook cells, post ledgers, delete files, call models, or mutate production
business state.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import zipfile
from dataclasses import dataclass
from importlib import util as importlib_util
from pathlib import Path
from typing import Any, Mapping

import invoice_review_bundle
import client_invoice_workbook_registry
import local_artifact_reference


SCHEMA_VERSION = "invoice_review_state_machine_v0"
DEFAULT_DB_PATH = Path(".openclaw/invoice_review/invoice_review_state.sqlite")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")

ACTION_TO_RECEIPT = {
    "confirm_source_workbook_reference": "source_workbook_reference_confirmed_receipt",
    "replace_source_workbook_reference": "source_workbook_replacement_request_receipt",
    "operator_reported_wrong_source_workbook": "wrong_source_workbook_operator_correction_receipt",
    "start_invoice_record_selection": "invoice_record_selection_started_receipt",
    "regenerate_or_link_invoice_artifact": "invoice_artifact_link_or_regeneration_requested_receipt",
    "request_supplier_portal_submission_proof": "supplier_portal_proof_intake_requested_receipt",
    "request_coupa_submission_proof": "coupa_proof_intake_requested_receipt",
    "review_and_confirm_recipients": "recipient_review_started_receipt",
    "show_approval_prerequisites": "approval_prerequisite_review_receipt",
    "review_clara_draft_prerequisites": "clara_draft_prerequisite_review_receipt",
    "edit_clara_draft_request": "clara_draft_edit_request_receipt",
    "prepare_send_approval_request": "send_approval_preparation_receipt",
    "setup_payment_watch_after_submission": "payment_watch_setup_receipt",
    "explain_invoice_review": "invoice_review_explanation_receipt",
    "confirm_invoice_review_candidate": "invoice_review_confirmation_intake_receipt",
    "open_invoice_workbook_candidate": "local_artifact_inspection_receipt",
    "confirm_invoice_record_selection": "invoice_record_selection_operator_confirmed_receipt",
    "confirm_source_workbook_selection": "source_workbook_reference_confirmed_receipt",
}

ACTION_TO_RECEIPT_EVENT = {
    "confirm_source_workbook_reference": "source_workbook_reference_confirmed",
    "replace_source_workbook_reference": "source_workbook_replacement_requested",
    "operator_reported_wrong_source_workbook": "operator_reported_wrong_source_workbook",
    "start_invoice_record_selection": "invoice_record_selection_started",
    "regenerate_or_link_invoice_artifact": "invoice_artifact_link_or_regeneration_requested",
    "request_supplier_portal_submission_proof": "supplier_portal_proof_intake_requested",
    "request_coupa_submission_proof": "coupa_proof_intake_requested",
    "review_and_confirm_recipients": "recipient_review_started",
    "show_approval_prerequisites": "approval_prerequisites_readback",
    "review_clara_draft_prerequisites": "clara_draft_prerequisites_readback",
    "edit_clara_draft_request": "clara_draft_edit_requested",
    "prepare_send_approval_request": "send_approval_preparation_requested",
    "setup_payment_watch_after_submission": "payment_watch_setup_requested",
    "explain_invoice_review": "invoice_review_explained",
    "confirm_invoice_review_candidate": "invoice_review_confirmation_intake_requested",
    "open_invoice_workbook_candidate": "local_artifact_inspection_requested",
    "confirm_invoice_record_selection": "invoice_record_selection_operator_confirmed",
    "confirm_source_workbook_selection": "source_workbook_reference_confirmed",
}

ARTIFACT_GENERATOR_NOT_WIRED_RECEIPT = "invoice_artifact_generator_not_wired_receipt"

COMPLETION_RECEIPTS = {
    "active_workbook_confirmed_receipt",
    "source_workbook_reference_confirmed_receipt",
    "invoice_record_selected_receipt",
    "invoice_period_confirmed_receipt",
    "generated_invoice_artifact_linkage_receipt",
    "invoice_attachment_proof_receipt",
    "portal_invoice_submission_receipt",
    "recipient_confirmation_receipt",
    "guardian_approval_receipt",
    "operator_approval_receipt",
    "email_send_receipt",
    "payment_detected_receipt",
    "ledger_tax_evidence_receipt",
}

AUTHORITY_BOUNDARY = {
    "coupa_browser_automation_performed": False,
    "coupa_submission_performed": False,
    "email_send_performed": False,
    "gmail_access_performed": False,
    "ledger_posting_performed": False,
    "invoice_generation_performed": False,
    "pdf_export_performed": False,
    "workbook_body_read_performed": False,
    "spreadsheet_cell_read_performed": False,
    "file_deletion_performed": False,
    "production_business_mutation_performed": False,
    "live_model_call_performed": False,
    "tool_execution_performed": False,
}


@dataclass(frozen=True)
class InvoiceReviewActionResult:
    source_request_id: str
    action_kind: str
    status: str
    headline: str
    body: str
    detail: str
    next_action: str
    action_receipt: dict[str, Any]
    state_snapshot: dict[str, Any]
    refreshed_bundle: dict[str, Any]
    source_bundle_path: str
    bridge_bundle_path: str | None
    bridge_mirror_written: bool


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_store(db_path: Path = DEFAULT_DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS invoice_review_states (
              bundle_id TEXT PRIMARY KEY,
              client_ref TEXT NOT NULL,
              workflow_ref TEXT NOT NULL,
              source_workbook_status TEXT NOT NULL,
              invoice_record_selection_status TEXT NOT NULL,
              invoice_period_status TEXT NOT NULL,
              invoice_period_label TEXT,
              invoice_record_label TEXT,
              generated_candidate_disposition TEXT,
              operator_notes TEXT,
              generated_artifact_metadata_status TEXT,
              generated_artifact_metadata_hash TEXT,
              generated_artifact_metadata_size INTEGER,
              generated_artifact_generator_status TEXT,
              generated_artifact_generator_reason TEXT,
              generated_artifact_status TEXT NOT NULL,
              source_workbook_ref TEXT,
              source_workbook_pc_path TEXT,
              source_workbook_mac_path TEXT,
              coupa_proof_status TEXT NOT NULL,
              supplier_portal_provider TEXT,
              supplier_portal_proof_status TEXT,
              recipient_confirmation_status TEXT NOT NULL,
              recipient_review_status TEXT,
              clara_draft_status TEXT NOT NULL,
              approval_readiness_status TEXT NOT NULL,
              email_send_status TEXT NOT NULL,
              payment_watch_status TEXT NOT NULL,
              ledger_tax_status TEXT NOT NULL,
              last_action_kind TEXT,
              last_receipt_id TEXT,
              last_updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS invoice_review_receipts (
              receipt_id TEXT PRIMARY KEY,
              receipt_type TEXT NOT NULL,
              source_request_id TEXT NOT NULL,
              bundle_id TEXT NOT NULL,
              client_ref TEXT NOT NULL,
              workflow_ref TEXT NOT NULL,
              action_kind TEXT NOT NULL,
              status TEXT NOT NULL,
              completion_receipt_written INTEGER NOT NULL CHECK (completion_receipt_written IN (0,1)),
              underlying_blocker_completed INTEGER NOT NULL CHECK (underlying_blocker_completed IN (0,1)),
              external_action_performed INTEGER NOT NULL CHECK (external_action_performed IN (0,1)),
              receipt_name TEXT NOT NULL,
              receipt_event TEXT,
              generated_at TEXT
            );
            """
        )
        _ensure_column(conn, "invoice_review_states", "recipient_review_status", "TEXT")
        _ensure_column(conn, "invoice_review_states", "supplier_portal_provider", "TEXT")
        _ensure_column(conn, "invoice_review_states", "supplier_portal_proof_status", "TEXT")
        _ensure_column(conn, "invoice_review_states", "invoice_period_label", "TEXT")
        _ensure_column(conn, "invoice_review_states", "invoice_record_label", "TEXT")
        _ensure_column(conn, "invoice_review_states", "generated_candidate_disposition", "TEXT")
        _ensure_column(conn, "invoice_review_states", "operator_notes", "TEXT")
        _ensure_column(conn, "invoice_review_states", "generated_artifact_metadata_status", "TEXT")
        _ensure_column(conn, "invoice_review_states", "generated_artifact_metadata_hash", "TEXT")
        _ensure_column(conn, "invoice_review_states", "generated_artifact_metadata_size", "INTEGER")
        _ensure_column(conn, "invoice_review_states", "generated_artifact_generator_status", "TEXT")
        _ensure_column(conn, "invoice_review_states", "generated_artifact_generator_reason", "TEXT")
        _ensure_column(conn, "invoice_review_states", "source_workbook_ref", "TEXT")
        _ensure_column(conn, "invoice_review_states", "source_workbook_pc_path", "TEXT")
        _ensure_column(conn, "invoice_review_states", "source_workbook_mac_path", "TEXT")
        _ensure_column(conn, "invoice_review_receipts", "receipt_event", "TEXT")


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
    columns = {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def _client_invoice_scope(client_ref: str | None = None, workflow_ref: str | None = None) -> dict[str, str | None]:
    client = (client_ref or "capital_hilton").strip() or "capital_hilton"
    if client == "live_arts_md":
        return {
            "client_ref": "live_arts_md",
            "client_display_name": "Live Arts MD",
            "workflow_ref": workflow_ref or "live_arts_md_invoice_workflow",
            "bundle_id": "invoice_review_bundle:live_arts_md:v0",
            "supplier_portal_provider": None,
            "supplier_portal_proof_status": "NOT_REQUIRED_BY_RECIPE",
            "coupa_proof_status": "NOT_REQUIRED_BY_RECIPE",
            "source_workbook_status": "SOURCE_WORKBOOK_REQUIRED",
            "generated_artifact_status": "ARTIFACT_REQUIRED",
        }
    return {
        "client_ref": "capital_hilton",
        "client_display_name": "Capital Hilton",
        "workflow_ref": workflow_ref or invoice_review_bundle.CAPITAL_HILTON_WORKFLOW_REF,
        "bundle_id": invoice_review_bundle.CAPITAL_HILTON_BUNDLE_ID,
        "supplier_portal_provider": "COUPA",
        "supplier_portal_proof_status": "MISSING",
        "coupa_proof_status": "MISSING",
        "source_workbook_status": "CANDIDATE_PRESENT",
        "generated_artifact_status": "CANDIDATE_NEEDS_LINKAGE",
    }


def _default_state(
    *,
    generated_at: str | None = None,
    client_ref: str | None = None,
    workflow_ref: str | None = None,
) -> dict[str, Any]:
    scope = _client_invoice_scope(client_ref, workflow_ref)
    return {
        "bundle_id": scope["bundle_id"],
        "client_ref": scope["client_ref"],
        "workflow_ref": scope["workflow_ref"],
        "source_workbook_status": scope["source_workbook_status"],
        "invoice_record_selection_status": "NEEDS_OPERATOR_SELECTION",
        "invoice_period_status": "NEEDS_OPERATOR_SELECTION",
        "invoice_period_label": None,
        "invoice_record_label": None,
        "generated_candidate_disposition": None,
        "operator_notes": None,
        "generated_artifact_metadata_status": None,
        "generated_artifact_metadata_hash": None,
        "generated_artifact_metadata_size": None,
        "generated_artifact_generator_status": None,
        "generated_artifact_generator_reason": None,
        "generated_artifact_status": scope["generated_artifact_status"],
        "source_workbook_ref": None,
        "source_workbook_pc_path": None,
        "source_workbook_mac_path": None,
        "coupa_proof_status": scope["coupa_proof_status"],
        "supplier_portal_provider": scope["supplier_portal_provider"],
        "supplier_portal_proof_status": scope["supplier_portal_proof_status"],
        "recipient_confirmation_status": "CANDIDATE_UNCONFIRMED",
        "recipient_review_status": "NOT_STARTED",
        "clara_draft_status": "DRAFT_ONLY",
        "approval_readiness_status": "BLOCKED_PREREQUISITES",
        "email_send_status": "NOT_SENT",
        "payment_watch_status": "NOT_READY",
        "ledger_tax_status": "NOT_READY",
        "last_action_kind": None,
        "last_receipt_id": None,
        "last_updated_at": generated_at,
    }


def load_state(
    db_path: Path = DEFAULT_DB_PATH,
    *,
    generated_at: str | None = None,
    client_ref: str | None = None,
    workflow_ref: str | None = None,
) -> dict[str, Any]:
    init_store(db_path)
    scope = _client_invoice_scope(client_ref, workflow_ref)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM invoice_review_states WHERE bundle_id = ?",
            (scope["bundle_id"],),
        ).fetchone()
        if row:
            state = dict(row)
            if not state.get("recipient_review_status"):
                state["recipient_review_status"] = (
                    "NEEDS_CONTACT_CONFIRMATION"
                    if state.get("recipient_confirmation_status") == "REVIEW_REQUESTED_EMAILS_MISSING"
                    else "NOT_STARTED"
                )
            if not state.get("supplier_portal_provider") and state.get("client_ref") == "capital_hilton":
                state["supplier_portal_provider"] = "COUPA"
            if not state.get("supplier_portal_proof_status"):
                state["supplier_portal_proof_status"] = state.get("coupa_proof_status") or scope["supplier_portal_proof_status"]
            return state
        state = _default_state(generated_at=generated_at, client_ref=str(scope["client_ref"]), workflow_ref=str(scope["workflow_ref"]))
        _upsert_state(conn, state)
        return state


def _upsert_state(conn: sqlite3.Connection, state: Mapping[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO invoice_review_states (
          bundle_id, client_ref, workflow_ref, source_workbook_status,
          invoice_record_selection_status, invoice_period_status,
          invoice_period_label, invoice_record_label, generated_candidate_disposition,
          operator_notes, generated_artifact_metadata_status,
          generated_artifact_metadata_hash, generated_artifact_metadata_size,
          generated_artifact_generator_status, generated_artifact_generator_reason,
          generated_artifact_status, source_workbook_ref, source_workbook_pc_path,
          source_workbook_mac_path, coupa_proof_status,
          supplier_portal_provider, supplier_portal_proof_status,
          recipient_confirmation_status, recipient_review_status, clara_draft_status,
          approval_readiness_status, email_send_status, payment_watch_status,
          ledger_tax_status, last_action_kind, last_receipt_id, last_updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(bundle_id) DO UPDATE SET
          source_workbook_status=excluded.source_workbook_status,
          invoice_record_selection_status=excluded.invoice_record_selection_status,
          invoice_period_status=excluded.invoice_period_status,
          invoice_period_label=excluded.invoice_period_label,
          invoice_record_label=excluded.invoice_record_label,
          generated_candidate_disposition=excluded.generated_candidate_disposition,
          operator_notes=excluded.operator_notes,
          generated_artifact_metadata_status=excluded.generated_artifact_metadata_status,
          generated_artifact_metadata_hash=excluded.generated_artifact_metadata_hash,
          generated_artifact_metadata_size=excluded.generated_artifact_metadata_size,
          generated_artifact_generator_status=excluded.generated_artifact_generator_status,
          generated_artifact_generator_reason=excluded.generated_artifact_generator_reason,
          generated_artifact_status=excluded.generated_artifact_status,
          source_workbook_ref=excluded.source_workbook_ref,
          source_workbook_pc_path=excluded.source_workbook_pc_path,
          source_workbook_mac_path=excluded.source_workbook_mac_path,
          coupa_proof_status=excluded.coupa_proof_status,
          supplier_portal_provider=excluded.supplier_portal_provider,
          supplier_portal_proof_status=excluded.supplier_portal_proof_status,
          recipient_confirmation_status=excluded.recipient_confirmation_status,
          recipient_review_status=excluded.recipient_review_status,
          clara_draft_status=excluded.clara_draft_status,
          approval_readiness_status=excluded.approval_readiness_status,
          email_send_status=excluded.email_send_status,
          payment_watch_status=excluded.payment_watch_status,
          ledger_tax_status=excluded.ledger_tax_status,
          last_action_kind=excluded.last_action_kind,
          last_receipt_id=excluded.last_receipt_id,
          last_updated_at=excluded.last_updated_at
        """,
        (
            state["bundle_id"],
            state["client_ref"],
            state["workflow_ref"],
            state["source_workbook_status"],
            state["invoice_record_selection_status"],
            state["invoice_period_status"],
            state.get("invoice_period_label"),
            state.get("invoice_record_label"),
            state.get("generated_candidate_disposition"),
            state.get("operator_notes"),
            state.get("generated_artifact_metadata_status"),
            state.get("generated_artifact_metadata_hash"),
            state.get("generated_artifact_metadata_size"),
            state.get("generated_artifact_generator_status"),
            state.get("generated_artifact_generator_reason"),
            state["generated_artifact_status"],
            state.get("source_workbook_ref"),
            state.get("source_workbook_pc_path"),
            state.get("source_workbook_mac_path"),
            state["coupa_proof_status"],
            state.get("supplier_portal_provider", "COUPA"),
            state.get("supplier_portal_proof_status", state["coupa_proof_status"]),
            state["recipient_confirmation_status"],
            state.get("recipient_review_status", "NOT_STARTED"),
            state["clara_draft_status"],
            state["approval_readiness_status"],
            state["email_send_status"],
            state["payment_watch_status"],
            state["ledger_tax_status"],
            state.get("last_action_kind"),
            state.get("last_receipt_id"),
            state.get("last_updated_at"),
        ),
    )


def receipt_names(db_path: Path = DEFAULT_DB_PATH, *, bundle_id: str | None = None) -> tuple[str, ...]:
    init_store(db_path)
    with _connect(db_path) as conn:
        if bundle_id:
            rows = conn.execute(
                "SELECT DISTINCT receipt_name FROM invoice_review_receipts WHERE bundle_id = ? ORDER BY receipt_name",
                (bundle_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT DISTINCT receipt_name FROM invoice_review_receipts ORDER BY receipt_name"
            ).fetchall()
    return tuple(str(row["receipt_name"]) for row in rows)


def _completion_receipts_for_bundle(db_path: Path, *, bundle_id: str | None = None) -> tuple[str, ...]:
    names = receipt_names(db_path, bundle_id=bundle_id)
    return tuple(name for name in names if name in COMPLETION_RECEIPTS)


def _receipt(
    *,
    source_request_id: str,
    action_kind: str,
    receipt_name: str,
    status: str,
    completion: bool,
    generated_at: str | None,
    client_ref: str = "capital_hilton",
    workflow_ref: str | None = None,
    bundle_id: str | None = None,
) -> dict[str, Any]:
    scope = _client_invoice_scope(client_ref, workflow_ref)
    receipt_id = f"invoice_review:{receipt_name}:{_short_hash(source_request_id, action_kind, status)}"
    if receipt_name == ARTIFACT_GENERATOR_NOT_WIRED_RECEIPT:
        receipt_event = "invoice_artifact_generator_not_wired"
    elif receipt_name == "selected_record_invoice_artifact_generation_authority_required_receipt":
        receipt_event = "selected_record_invoice_artifact_generation_authority_required"
    elif receipt_name == "source_workbook_confirmation_needed_receipt":
        receipt_event = "source_workbook_confirmation_needed"
    else:
        receipt_event = ACTION_TO_RECEIPT_EVENT.get(action_kind, receipt_name.removesuffix("_receipt"))
    return {
        "receipt_id": receipt_id,
        "receipt_type": "invoice_review_action_progress_receipt",
        "receipt_name": receipt_name,
        "receipt_event": receipt_event,
        "source_request_id": source_request_id,
        "bundle_id": bundle_id or scope["bundle_id"],
        "workflow_ref": workflow_ref or str(scope["workflow_ref"]),
        "client_ref": str(scope["client_ref"]),
        "action_kind": action_kind,
        "status": status,
        "underlying_blocker_completed": completion,
        "completion_receipt_written": completion,
        "external_action_performed": False,
        "generated_at": generated_at,
    }


def inspect_generated_invoice_artifact_metadata(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "artifact_path": path.as_posix(),
        "artifact_ref": invoice_review_bundle._artifact_ref(path),
        "metadata_status": "GENERATED_ARTIFACT_INVALID",
        "exists": path.exists(),
        "file_size": None,
        "file_extension": path.suffix.lower(),
        "sha256": None,
        "xlsx_package_valid": False,
        "workbook_business_cells_read": False,
        "workbook_business_contents_parsed": False,
        "generation_or_export_performed": False,
    }
    if not path.exists() or not path.is_file():
        result["invalid_reason"] = "ARTIFACT_FILE_MISSING"
        return result
    stat = path.stat()
    result["file_size"] = stat.st_size
    result["mtime_ns"] = stat.st_mtime_ns
    result["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    if path.suffix.lower() != ".xlsx":
        result["invalid_reason"] = "UNSUPPORTED_EXTENSION"
        return result
    try:
        with zipfile.ZipFile(path) as package:
            names = set(package.namelist())
            result["xlsx_package_valid"] = "[Content_Types].xml" in names and any(
                name.startswith("xl/") for name in names
            )
            result["package_file_count"] = len(names)
    except zipfile.BadZipFile:
        result["invalid_reason"] = "BAD_XLSX_ZIP_CONTAINER"
        return result
    if not result["xlsx_package_valid"]:
        result["invalid_reason"] = "MISSING_XLSX_PACKAGE_PARTS"
        return result
    result["metadata_status"] = "GENERATED_ARTIFACT_METADATA_VALID"
    result["invalid_reason"] = None
    return result


def inspect_workbook_candidate_metadata(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": path.as_posix(),
        "exists": path.exists(),
        "file_extension": path.suffix.lower(),
        "file_size": None,
        "sha256": None,
        "xlsx_package_valid": False,
        "workbook_business_cells_read": False,
        "spreadsheet_cell_read_performed": False,
    }
    if path.suffix.lower() != ".xlsx":
        result["metadata_status"] = "INVALID_EXTENSION"
        return result
    if not path.exists() or not path.is_file():
        result["metadata_status"] = "PATH_NOT_READABLE"
        return result
    stat = path.stat()
    result["file_size"] = stat.st_size
    result["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        with zipfile.ZipFile(path) as package:
            names = set(package.namelist())
            result["xlsx_package_valid"] = "[Content_Types].xml" in names and any(
                name.startswith("xl/") for name in names
            )
    except zipfile.BadZipFile:
        result["metadata_status"] = "BAD_XLSX_ZIP_CONTAINER"
        return result
    result["metadata_status"] = "METADATA_VALID" if result["xlsx_package_valid"] else "MISSING_XLSX_PACKAGE_PARTS"
    return result


def _source_workbook_linkage_readiness() -> dict[str, Any]:
    registry_payload = client_invoice_workbook_registry.load_existing_payload()
    artifact_payload = local_artifact_reference.load_existing_payload()
    active = None
    if isinstance(registry_payload, Mapping):
        active_record = registry_payload.get("active_record")
        if isinstance(active_record, Mapping):
            active = dict(active_record)
    approved = local_artifact_reference.find_approved_readable_artifact(
        artifact_payload,
        world_ref="finance",
        workflow_ref=invoice_review_bundle.CAPITAL_HILTON_WORKFLOW_REF,
        client_ref="capital_hilton",
        artifact_kind="invoice_workbook",
        intended_use="client_invoice_sheet_audit",
    )
    registry_ref = str(active.get("workbook_ref")) if active else None
    approved_ref = str(approved.get("artifact_ref")) if approved else None
    confirmed = bool(active and approved and registry_ref == approved_ref)
    if confirmed:
        blocker = None
    elif active and approved:
        blocker = "ACTIVE_WORKBOOK_REF_DIFFERS_FROM_APPROVED_READABLE_ARTIFACT_REF"
    elif active:
        blocker = "APPROVED_READABLE_WORKBOOK_ARTIFACT_MISSING"
    elif approved:
        blocker = "WORKBOOK_REGISTRY_ACTIVE_RECORD_MISSING"
    else:
        blocker = "SOURCE_WORKBOOK_REFERENCE_MISSING"
    return {
        "source_workbook_found": bool(active or approved),
        "source_workbook_confirmed": confirmed,
        "registry_workbook_ref": registry_ref,
        "approved_artifact_ref": approved_ref,
        "source_workbook_pc_path": str(approved.get("pc_path") or approved.get("approved_path_ref") or "") if approved else "",
        "source_workbook_mac_path": str(approved.get("mac_path") or "") if approved else "",
        "blocker": blocker,
        "no_workbook_body_read": True,
        "no_cell_read": True,
    }


def source_workbook_candidates() -> tuple[dict[str, Any], ...]:
    linkage = _source_workbook_linkage_readiness()
    candidates = []
    registry_payload = client_invoice_workbook_registry.load_existing_payload()
    candidate_record = registry_payload.get("candidate_record") if isinstance(registry_payload, Mapping) else None
    if isinstance(candidate_record, Mapping) and candidate_record.get("workbook_ref"):
        candidates.append(
            {
                "candidate_ref": str(candidate_record["workbook_ref"]),
                "candidate_kind": "staged_workbook_candidate",
                "display_name": str(candidate_record.get("workbook_display_name") or ""),
                "extension": str(candidate_record.get("workbook_extension") or ""),
                "source_request_id": str(candidate_record.get("source_request_id") or ""),
                "confirmation_status": "CANDIDATE_ONLY",
            }
        )
    if linkage.get("registry_workbook_ref"):
        candidates.append(
            {
                "candidate_ref": linkage["registry_workbook_ref"],
                "candidate_kind": "active_registry_workbook_ref",
                "confirmation_status": "CANDIDATE_ONLY",
            }
        )
    if linkage.get("approved_artifact_ref"):
        candidates.append(
            {
                "candidate_ref": linkage["approved_artifact_ref"],
                "candidate_kind": "approved_readable_artifact_ref",
                "pc_path": linkage.get("source_workbook_pc_path") or "",
                "mac_path": linkage.get("source_workbook_mac_path") or "",
                "confirmation_status": "CANDIDATE_ONLY",
            }
        )
    return tuple(candidates)


def audit_current_invoice_artifact_generator(state: Mapping[str, Any]) -> dict[str, Any]:
    builder_spec = importlib_util.find_spec("invoice_artifact_builder")
    preview_spec = importlib_util.find_spec("capital_hilton_invoice_artifact_generator")
    found_refs = tuple(
        ref
        for ref, present in (
            ("invoice_artifact_builder", builder_spec is not None),
            ("capital_hilton_invoice_artifact_generator", preview_spec is not None),
        )
        if present
    )
    required_linkage_inputs = {
        "client_ref": state.get("client_ref"),
        "workflow_ref": state.get("workflow_ref"),
        "invoice_period_label": state.get("invoice_period_label"),
        "invoice_record_label": state.get("invoice_record_label"),
        "source_workbook_status": state.get("source_workbook_status"),
    }
    reason_codes: list[str] = []
    if not found_refs:
        reason_codes.append("NO_LOCAL_GENERATOR_MODULE_FOUND")
    if state.get("source_workbook_status") != "CONFIRMED":
        reason_codes.append("SOURCE_WORKBOOK_REFERENCE_NOT_CONFIRMED")
    if not state.get("invoice_period_label") or not state.get("invoice_record_label"):
        reason_codes.append("SELECTED_INVOICE_RECORD_LABELS_MISSING")
    reason_codes.extend(
        (
            "EXISTING_GENERATORS_USE_STATIC_FIXTURE_FACTS",
            "NO_GENERATOR_ACCEPTS_SELECTED_INVOICE_RECORD_AND_SOURCE_WORKBOOK_RECEIPT",
            "WORKBOOK_BODY_READ_NOT_AUTHORIZED",
            "GENERATION_AUTHORITY_RECEIPT_REQUIRED",
        )
    )
    return {
        "existing_generator_found": bool(found_refs),
        "generator_refs": found_refs,
        "safe_generator_available": False,
        "generator_status": "GENERATOR_NOT_WIRED",
        "reason_codes": tuple(dict.fromkeys(reason_codes)),
        "required_linkage_inputs": required_linkage_inputs,
        "workbook_business_cells_read": False,
        "generation_or_export_performed": False,
        "artifact_created": False,
        "artifact_linked": False,
    }


def _write_receipt(conn: sqlite3.Connection, receipt: Mapping[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO invoice_review_receipts (
          receipt_id, receipt_type, source_request_id, bundle_id, client_ref,
          workflow_ref, action_kind, status, completion_receipt_written,
          underlying_blocker_completed, external_action_performed, receipt_name,
          receipt_event, generated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            receipt["receipt_id"],
            receipt["receipt_type"],
            receipt["source_request_id"],
            receipt["bundle_id"],
            receipt["client_ref"],
            receipt["workflow_ref"],
            receipt["action_kind"],
            receipt["status"],
            1 if receipt["completion_receipt_written"] else 0,
            1 if receipt["underlying_blocker_completed"] else 0,
            1 if receipt["external_action_performed"] else 0,
            receipt["receipt_name"],
            receipt["receipt_event"],
            receipt.get("generated_at"),
        ),
    )


def _apply_action(state: dict[str, Any], action_kind: str) -> tuple[str, str, str, str, str, bool]:
    if action_kind == "confirm_source_workbook_reference":
        linkage = _source_workbook_linkage_readiness()
        if not linkage["source_workbook_confirmed"]:
            state["source_workbook_status"] = "NEEDS_CONFIRMATION"
            return (
                "BLOCKED_SOURCE_WORKBOOK_CONFIRMATION_NEEDED",
                "Source workbook needs confirmation",
                "Choose or confirm the Capital Hilton source workbook before generating the invoice artifact. OpenClaw found workbook metadata, but it is not yet linked by matching registry and approved-readable artifact proof. No workbook body or cells were read.",
                "Choose or confirm the Capital Hilton source workbook.",
                "source_workbook_confirmation_needed_receipt",
                False,
            )
        state["source_workbook_status"] = "CONFIRMED"
        return ("COMPLETED", "Source workbook confirmed", "Source workbook reference is confirmed. No workbook body or cells were read.", "Next: request selected-record generation authority.", "source_workbook_reference_confirmed_receipt", True)
    if action_kind == "replace_source_workbook_reference":
        state["source_workbook_status"] = "REPLACEMENT_REQUESTED"
        return ("REQUESTED", "Choose the correct source workbook", "Choose the replacement source workbook. No file will be deleted.", "Select the replacement workbook in Mission Control.", "source_workbook_replacement_request_receipt", False)
    if action_kind == "operator_reported_wrong_source_workbook":
        state["source_workbook_status"] = "OPERATOR_REPORTED_WRONG_WORKBOOK"
        state["invoice_record_selection_status"] = "NEEDS_RESELECTION_AFTER_SOURCE_WORKBOOK_CORRECTION"
        state["invoice_period_status"] = "NEEDS_RESELECTION_AFTER_SOURCE_WORKBOOK_CORRECTION"
        state["generated_candidate_disposition"] = "wrong_source_workbook"
        state["generated_artifact_status"] = "INVALIDATED_BY_WRONG_SOURCE_WORKBOOK"
        state["approval_readiness_status"] = "BLOCKED_WRONG_SOURCE_WORKBOOK"
        return (
            "STOP_LINE_WRONG_SOURCE_WORKBOOK",
            "Choose the correct source workbook",
            "OpenClaw recorded that the Capital Hilton workflow is pointed at the wrong workbook. Choose or confirm the correct source workbook before any invoice artifact generation, linking, approval, send, Coupa, or ledger step continues. No file was deleted and no workbook body or cells were read.",
            "Choose the correct Capital Hilton source workbook.",
            "wrong_source_workbook_operator_correction_receipt",
            False,
        )
    if action_kind == "start_invoice_record_selection":
        state["invoice_record_selection_status"] = "NEEDS_OPERATOR_SELECTION"
        state["invoice_period_status"] = "NEEDS_OPERATOR_SELECTION"
        return ("REQUESTED", "Starting invoice page selection", "Let's pick the Capital Hilton invoice page/period. Choose the page or period from the running workbook so OpenClaw can link the generated invoice artifact correctly.", "Choose the invoice page or period in Mission Control.", "invoice_record_selection_started_receipt", False)
    if action_kind == "regenerate_or_link_invoice_artifact":
        if state["source_workbook_status"] != "CONFIRMED":
            state["generated_artifact_status"] = "BLOCKED_NEEDS_CORRECT_SOURCE_WORKBOOK"
            return (
                "BLOCKED_NEEDS_CORRECT_SOURCE_WORKBOOK",
                "Choose the correct source workbook first",
                "Choose the correct Capital Hilton source workbook before regenerating or linking the invoice artifact. Nothing was generated, exported, linked, attached, or approved.",
                "Choose or confirm the correct source workbook.",
                "generated_invoice_artifact_linkage_request_receipt",
                False,
            )
        if state["invoice_record_selection_status"] not in {"OPERATOR_CONFIRMED", "SELECTED"} or state["invoice_period_status"] not in {"OPERATOR_CONFIRMED", "CONFIRMED"}:
            state["generated_artifact_status"] = "BLOCKED_NEEDS_INVOICE_RECORD_SELECTION"
            return ("BLOCKED_NEEDS_INVOICE_RECORD_SELECTION", "Select the invoice page first", "Select the invoice page/period from the confirmed source workbook before regenerating or linking an artifact. No invoice was generated or exported from this step.", "Select the invoice page/period first.", "generated_invoice_artifact_linkage_request_receipt", False)
        metadata = inspect_generated_invoice_artifact_metadata(invoice_review_bundle.CAPITAL_HILTON_EXCEL_PATH)
        state["generated_artifact_metadata_status"] = metadata["metadata_status"]
        state["generated_artifact_metadata_hash"] = metadata.get("sha256")
        state["generated_artifact_metadata_size"] = metadata.get("file_size")
        if metadata["metadata_status"] == "GENERATED_ARTIFACT_INVALID":
            state["generated_artifact_status"] = "GENERATED_ARTIFACT_INVALID"
            return ("GENERATED_ARTIFACT_INVALID", "Invoice artifact is not attach-ready", "OpenClaw has the selected invoice page/period, but the existing generated invoice artifact failed metadata/package checks. Nothing was generated, exported, linked, attached, or approved.", "Next: regenerate the invoice artifact for the selected record when the generator rail is wired.", "generated_invoice_artifact_invalid_receipt", False)
        import selected_record_invoice_artifact_generator_readiness as generator_readiness

        readiness = generator_readiness.evaluate_readiness(
            state=state,
            receipts=tuple(state.get("_receipt_names") or ()),
            source_workbook_ref=state.get("source_workbook_ref"),
            source_workbook_path=state.get("source_workbook_pc_path") or state.get("source_workbook_mac_path"),
        )
        state["generated_artifact_generator_status"] = "GENERATION_AUTHORITY_REQUIRED"
        state["generated_artifact_generator_reason"] = ", ".join(readiness.missing_inputs)
        if not readiness.safe_to_generate and generator_readiness.GENERATION_AUTHORITY_RECEIPT in readiness.missing_inputs:
            state["generated_artifact_status"] = "GENERATION_AUTHORITY_REQUIRED"
            return (
                "GENERATION_AUTHORITY_REQUIRED",
                "Generation authority required",
                "OpenClaw has the correct workbook and invoice page. It still needs generation/export authority before creating the invoice artifact. Nothing was generated, exported, linked, attached, or approved.",
                "Next: request generation/export authority or attach a generated invoice artifact through a governed intake path.",
                "selected_record_invoice_artifact_generation_authority_required_receipt",
                False,
            )
        generator_audit = audit_current_invoice_artifact_generator(state)
        state["generated_artifact_generator_status"] = generator_audit["generator_status"]
        state["generated_artifact_generator_reason"] = ", ".join(generator_audit["reason_codes"])
        if not generator_audit["safe_generator_available"]:
            state["generated_artifact_status"] = "ARTIFACT_GENERATOR_NOT_WIRED"
            period = state.get("invoice_period_label") or "the selected period"
            record = state.get("invoice_record_label") or "the selected record"
            return (
                "GENERATOR_NOT_WIRED",
                "Invoice artifact generator is not wired",
                f"OpenClaw has the selected invoice page/period ({period} / {record}), but no safe generator can create or link a current artifact from that selection without guessing or reading workbook cells. Nothing was generated, exported, linked, attached, or approved.",
                "Next: wire a generator that accepts the selected invoice record, source workbook reference, and linkage receipt.",
                ARTIFACT_GENERATOR_NOT_WIRED_RECEIPT,
                False,
            )
        state["generated_artifact_status"] = "GENERATED_ARTIFACT_NEEDS_REGENERATION"
        period = state.get("invoice_period_label") or "the selected period"
        record = state.get("invoice_record_label") or "the selected record"
        return ("GENERATED_ARTIFACT_NEEDS_REGENERATION", "Invoice artifact needs regeneration", f"OpenClaw has the selected invoice page/period. The existing generated invoice artifact is not ready to attach yet. Next: regenerate or link the invoice artifact for {period} / {record}.", "Next: regenerate or link the invoice artifact for the selected record.", "invoice_artifact_link_or_regeneration_requested_receipt", False)
    if action_kind in {"request_supplier_portal_submission_proof", "request_coupa_submission_proof"}:
        state["coupa_proof_status"] = "PROOF_REQUESTED"
        state["supplier_portal_provider"] = "COUPA"
        state["supplier_portal_proof_status"] = "PROOF_REQUESTED"
        receipt_name = (
            "supplier_portal_proof_intake_requested_receipt"
            if action_kind == "request_supplier_portal_submission_proof"
            else "coupa_proof_intake_requested_receipt"
        )
        return ("REQUESTED", "Starting Coupa proof step", "Upload or provide Coupa submission proof when available. Nothing will be submitted from this step.", "Provide supplier portal submission proof when available.", receipt_name, False)
    if action_kind == "review_and_confirm_recipients":
        state["recipient_confirmation_status"] = "REVIEW_REQUESTED_EMAILS_MISSING"
        state["recipient_review_status"] = "NEEDS_CONTACT_CONFIRMATION"
        return ("REQUESTED", "Review recipients", "Review the Capital Hilton recipient candidates: Annette, Chyna, and Will. No email addresses were invented.", "Confirm or provide recipient contact details.", "recipient_review_started_receipt", False)
    if action_kind == "show_approval_prerequisites":
        return ("READBACK", "Approval is not ready yet", "Missing: Coupa proof missing, Invoice record/page not selected, Generated artifact not linked, Recipients unconfirmed, Attachment not ready.", "Resolve the listed blockers first.", "approval_prerequisite_review_receipt", False)
    if action_kind == "review_clara_draft_prerequisites":
        return ("READBACK", "Review Clara draft prerequisites", "Clara's draft remains draft-only until recipients, invoice selection, artifact linkage, Coupa proof, approval, and send rails exist.", "Review the missing prerequisites before requesting approval.", "clara_draft_prerequisite_review_receipt", False)
    if action_kind == "prepare_send_approval_request":
        state["approval_readiness_status"] = "BLOCKED_PREREQUISITES"
        return ("BLOCKED_PREREQUISITES", "Send approval is blocked", "Prepare-send is blocked until prerequisites are ready. No send approval, email send, or Coupa submission happened.", "Resolve the invoice review blockers first.", "send_approval_preparation_receipt", False)
    if action_kind == "setup_payment_watch_after_submission":
        state["payment_watch_status"] = "BLOCKED_UNTIL_SUBMISSION_OR_SEND_RECEIPT"
        return ("BLOCKED_PREREQUISITES", "Payment watch is not ready", "Payment watch is disabled until portal/email receipts exist. No ledger or payment state changed.", "Capture portal/email receipts first.", "payment_watch_setup_receipt", False)
    if action_kind == "edit_clara_draft_request":
        return ("BLOCKED_NOT_WIRED", "Draft edit is not wired yet", "The Clara draft edit path is not wired yet. Nothing was changed or sent.", "Use the visible draft text for manual review until the edit path is connected.", "clara_draft_edit_request_receipt", False)
    if action_kind == "explain_invoice_review":
        return ("READBACK", "Invoice review explained", "This review separates Coupa portal proof, Excel artifact linkage, Clara draft, Guardian approval, operator approval, execution receipts, payment watch, and ledger/tax evidence.", "Use a timeline action to start the next safe fix path.", "invoice_review_explanation_receipt", False)
    if action_kind == "confirm_invoice_review_candidate":
        return ("BLOCKED_PREREQUISITES", "Invoice review confirmation is blocked", "Confirm this invoice only after workbook, page/period, artifact linkage, Coupa proof, recipients, and attachment are ready.", "Resolve the missing prerequisites before approval.", "invoice_review_confirmation_intake_receipt", False)
    if action_kind == "open_invoice_workbook_candidate":
        return ("READBACK", "Open workbook candidate", "Open the Mac-visible candidate file for inspection. This does not mark it current or attachment-ready.", "Inspect the candidate file, then confirm or correct the invoice page.", "local_artifact_inspection_receipt", False)
    return ("BLOCKED_UNSUPPORTED_ACTION", "Invoice review action not wired", "That invoice review action is not wired yet.", "Use one of the visible enabled invoice review actions.", ACTION_TO_RECEIPT.get(action_kind, "unsupported_invoice_review_action_receipt"), False)


def _overlay_bundle_state(
    bundle_payload: dict[str, Any],
    state: Mapping[str, Any],
    receipt: Mapping[str, Any],
    *,
    action_receipt_names: tuple[str, ...],
) -> dict[str, Any]:
    capital = bundle_payload["capital_hilton_bundle"]
    capital["state_machine"] = {
        "schema_version": SCHEMA_VERSION,
        "store_status": "LOCAL_SQLITE_RECEIPT_BACKED",
        "state": dict(state),
        "last_action_receipt": dict(receipt),
        "completion_receipts_only_turn_steps_complete": True,
    }
    status_by_title: dict[str, str] = {}
    if state["source_workbook_status"] in {
        "OPERATOR_REPORTED_WRONG_WORKBOOK",
        "SOURCE_WORKBOOK_REPLACEMENT_REQUIRED",
        "REPLACEMENT_REQUESTED",
    }:
        status_by_title["Active workbook"] = "NEEDS_ACTION"
        status_by_title["Invoice page/period"] = "BLOCKED"
        status_by_title["Generated invoice artifact"] = "BLOCKED"
    if state["source_workbook_status"] == "CONFIRMED":
        status_by_title["Active workbook"] = "COMPLETE"
    if state["invoice_record_selection_status"] == "OPERATOR_CONFIRMED":
        status_by_title["Invoice page/period"] = "OPERATOR_CONFIRMED"
    if state["invoice_record_selection_status"] == "NEEDS_OPERATOR_SELECTION":
        status_by_title["Invoice page/period"] = "IN_PROGRESS" if receipt["receipt_name"] == "invoice_record_selection_started_receipt" else "NEEDS_ACTION"
    if state["generated_artifact_status"].startswith("BLOCKED"):
        status_by_title["Generated invoice artifact"] = "BLOCKED"
    if state["generated_artifact_status"] in {
        "GENERATED_ARTIFACT_NEEDS_REGENERATION",
        "ARTIFACT_GENERATOR_NOT_WIRED",
    }:
        status_by_title["Generated invoice artifact"] = "NEEDS_ACTION"
    if state["generated_artifact_status"] == "GENERATED_ARTIFACT_INVALID":
        status_by_title["Generated invoice artifact"] = "BLOCKED"
    if state["generated_artifact_status"] == "INVALIDATED_BY_WRONG_SOURCE_WORKBOOK":
        status_by_title["Generated invoice artifact"] = "BLOCKED"
    if state["coupa_proof_status"] == "PROOF_REQUESTED":
        status_by_title["Coupa portal proof"] = "REQUESTED"
    if state["recipient_confirmation_status"] == "REVIEW_REQUESTED_EMAILS_MISSING":
        status_by_title["Recipients"] = "IN_PROGRESS"
    if state["payment_watch_status"].startswith("BLOCKED"):
        status_by_title["Payment watch"] = "BLOCKED"
    updated = []
    for step in capital["review_proof_timeline"]:
        step = dict(step)
        if step["title"] in status_by_title and step["status"] != "COMPLETE":
            step["status"] = status_by_title[step["title"]]
            step["operator_summary"] = f"{step['operator_summary']} Current guided status: {status_by_title[step['title']].replace('_', ' ').lower()}."
            step["operator_copy"] = step["operator_summary"]
            refs = tuple(step.get("proof_refs") or ())
            step["proof_refs"] = tuple(dict.fromkeys((*refs, receipt["receipt_id"])))
        updated.append(step)
    capital["review_proof_timeline"] = tuple(updated)
    if state["invoice_record_selection_status"] == "OPERATOR_CONFIRMED":
        capital["invoice_selection"]["invoice_record_state"] = "INVOICE_RECORD_OPERATOR_CONFIRMED"
        capital["invoice_selection"]["invoice_period_state"] = "INVOICE_PERIOD_OPERATOR_CONFIRMED"
        capital["invoice_selection"]["invoice_period_label"] = state.get("invoice_period_label")
        capital["invoice_selection"]["invoice_record_label"] = state.get("invoice_record_label")
        capital["invoice_selection"]["operator_confirmed_selection"] = True
        capital["invoice_selection"]["completion_receipt_still_required"] = "invoice_record_selected_receipt"
        capital["invoice_selection"]["no_workbook_body_read"] = True
        capital["invoice_selection"]["no_cell_read"] = True
        capital["excel_invoice_artifact"]["linkage_status"] = "NEEDS_REGENERATION_OR_LINK"
        capital["excel_invoice_artifact"]["attachment_ready"] = False
    if state["source_workbook_status"] in {
        "OPERATOR_REPORTED_WRONG_WORKBOOK",
        "SOURCE_WORKBOOK_REPLACEMENT_REQUIRED",
        "REPLACEMENT_REQUESTED",
    }:
        capital["source_workbook_correction"] = {
            "status": state["source_workbook_status"],
            "operator_reported_wrong_workbook": state["source_workbook_status"] == "OPERATOR_REPORTED_WRONG_WORKBOOK",
            "replacement_requested": state["source_workbook_status"] == "REPLACEMENT_REQUESTED",
            "superseded": False,
            "physical_deletion_allowed": False,
            "no_workbook_body_read": True,
            "no_cell_read": True,
            "stop_line_active": True,
        }
        capital["invoice_selection"]["invoice_record_state"] = "NEEDS_RESELECTION_AFTER_SOURCE_WORKBOOK_CORRECTION"
        capital["invoice_selection"]["invoice_period_state"] = "NEEDS_RESELECTION_AFTER_SOURCE_WORKBOOK_CORRECTION"
        capital["invoice_selection"]["previous_invoice_period_label"] = state.get("invoice_period_label")
        capital["invoice_selection"]["previous_invoice_record_label"] = state.get("invoice_record_label")
        capital["invoice_selection"]["operator_confirmed_selection"] = False
        capital["excel_invoice_artifact"]["proof_status"] = "INVALIDATED_BY_WRONG_SOURCE_WORKBOOK"
        capital["excel_invoice_artifact"]["linkage_status"] = "STALE_WRONG_SOURCE"
        capital["excel_invoice_artifact"]["attachment_ready"] = False
        capital["approval_footer"]["approval_ready"] = False
        capital["approval_footer"]["approval_disabled_reasons"] = tuple(
            dict.fromkeys(
                (
                    "Correct source workbook required",
                    *tuple(capital["approval_footer"].get("approval_disabled_reasons") or ()),
                )
            )
        )
        replacement_action = next(
            (
                dict(action)
                for action in capital.get("correction_actions", ())
                if action.get("action_kind") == "replace_source_workbook_reference"
            ),
            None,
        )
        if replacement_action:
            replacement_action["label"] = "Choose correct workbook"
            replacement_action["operator_visible_message"] = "Starting source workbook replacement."
            hidden = dict(replacement_action.get("hidden_request_payload") or {})
            hidden.update(
                {
                    "intended_use": "replace_source_workbook_reference",
                    "physical_deletion_allowed": False,
                    "expected_next_surface": "local_file_picker_or_artifact_intake_for_replacement_workbook",
                }
            )
            replacement_action["hidden_request_payload"] = hidden
        primary_blocker = "Choose the correct Capital Hilton source workbook."
        blockers = tuple(dict.fromkeys((primary_blocker, *tuple(capital.get("blockers") or ()))))
        capital["blockers"] = blockers
        capital["actionable_blockers"] = tuple(
            dict.fromkeys(
                (
                    json.dumps(
                        {
                            "blocker_ref": f"invoice_review_blocker:{_short_hash(primary_blocker)}",
                            "operator_summary": primary_blocker,
                            "status": "NEEDS_ACTION",
                            "primary_action": replacement_action,
                            "disabled_reason": None,
                            "proof_refs": (receipt["receipt_id"],),
                        },
                        sort_keys=True,
                    ),
                    *[
                        json.dumps(item, sort_keys=True)
                        for item in tuple(capital.get("actionable_blockers") or ())
                    ],
                )
            )
        )
        capital["actionable_blockers"] = tuple(json.loads(item) for item in capital["actionable_blockers"])
    if (
        state["source_workbook_status"] == "CONFIRMED"
        and state["invoice_record_selection_status"] == "NEEDS_RESELECTION_AFTER_SOURCE_WORKBOOK_CORRECTION"
    ):
        capital["source_workbook_correction"] = {
            "status": "SOURCE_WORKBOOK_CONFIRMED_RESELECTION_REQUIRED",
            "source_workbook_ref": state.get("source_workbook_ref"),
            "source_workbook_pc_path": state.get("source_workbook_pc_path"),
            "source_workbook_mac_path": state.get("source_workbook_mac_path"),
            "operator_reported_wrong_workbook": False,
            "superseded": True,
            "physical_deletion_allowed": False,
            "no_workbook_body_read": True,
            "no_cell_read": True,
            "stop_line_active": False,
        }
        capital["invoice_selection"]["active_workbook_state"] = "SOURCE_WORKBOOK_CONFIRMED"
        capital["invoice_selection"]["invoice_record_state"] = "NEEDS_RESELECTION_AFTER_SOURCE_WORKBOOK_CORRECTION"
        capital["invoice_selection"]["invoice_period_state"] = "NEEDS_RESELECTION_AFTER_SOURCE_WORKBOOK_CORRECTION"
        capital["invoice_selection"]["operator_question"] = (
            "The source workbook was corrected. Select the invoice page/period again from the confirmed workbook."
        )
        capital["invoice_selection"]["previous_invoice_period_label"] = state.get("invoice_period_label")
        capital["invoice_selection"]["previous_invoice_record_label"] = state.get("invoice_record_label")
        capital["invoice_selection"]["operator_confirmed_selection"] = False
        primary_blocker = "Select the Capital Hilton invoice page/period from the confirmed workbook."
        selection_action = next(
            (
                dict(step.get("primary_action"))
                for step in capital.get("review_proof_timeline", ())
                if step.get("title") == "Invoice page/period" and isinstance(step.get("primary_action"), Mapping)
            ),
            None,
        )
        capital["blockers"] = tuple(dict.fromkeys((primary_blocker, *tuple(capital.get("blockers") or ()))))
        capital["actionable_blockers"] = (
            {
                "blocker_ref": f"invoice_review_blocker:{_short_hash(primary_blocker)}",
                "operator_summary": primary_blocker,
                "status": "NEEDS_ACTION",
                "primary_action": selection_action,
                "disabled_reason": None,
                "proof_refs": (receipt["receipt_id"],),
            },
            *tuple(capital.get("actionable_blockers") or ()),
        )
    if state["generated_artifact_status"] in {
        "GENERATED_ARTIFACT_NEEDS_REGENERATION",
        "ARTIFACT_GENERATOR_NOT_WIRED",
        "GENERATED_ARTIFACT_INVALID",
        "INVALIDATED_BY_WRONG_SOURCE_WORKBOOK",
        "GENERATION_AUTHORITY_REQUIRED",
    }:
        capital["excel_invoice_artifact"]["proof_status"] = state["generated_artifact_status"]
        capital["excel_invoice_artifact"]["linkage_status"] = (
            "INVALID_METADATA"
            if state["generated_artifact_status"] == "GENERATED_ARTIFACT_INVALID"
            else "STALE_WRONG_SOURCE"
            if state["generated_artifact_status"] == "INVALIDATED_BY_WRONG_SOURCE_WORKBOOK"
            else "GENERATION_AUTHORITY_REQUIRED"
            if state["generated_artifact_status"] == "GENERATION_AUTHORITY_REQUIRED"
            else "NEEDS_REGENERATION_OR_LINK"
        )
        capital["excel_invoice_artifact"]["attachment_ready"] = False
        capital["excel_invoice_artifact"]["metadata_status"] = state.get("generated_artifact_metadata_status")
        capital["excel_invoice_artifact"]["metadata_sha256"] = state.get("generated_artifact_metadata_hash")
        capital["excel_invoice_artifact"]["metadata_file_size"] = state.get("generated_artifact_metadata_size")
        if state["generated_artifact_status"] == "GENERATION_AUTHORITY_REQUIRED":
            capital["excel_invoice_artifact"]["generation_strategy"] = "MANUAL_EXPORT_OR_GOVERNED_LINK_REQUIRED"
            capital["excel_invoice_artifact"]["generation_authority_required"] = True
            capital["excel_invoice_artifact"]["manual_operator_actions"] = (
                {
                    "action_ref": f"invoice_review_action:{_short_hash('export_selected_invoice_page', state.get('invoice_period_label'), state.get('invoice_record_label'))}",
                    "label": "Export selected invoice page",
                    "action_kind": "export_selected_invoice_page",
                    "intended_use": "manual_operator_export_selected_invoice_page",
                    "enabled": False,
                    "disabled_reason": "This manual export authority path is not wired yet.",
                    "no_external_action": True,
                    "no_workbook_body_read": True,
                    "no_cell_read": True,
                },
                {
                    "action_ref": f"invoice_review_action:{_short_hash('attach_generated_invoice_artifact', state.get('invoice_period_label'), state.get('invoice_record_label'))}",
                    "label": "Attach generated invoice artifact",
                    "action_kind": "attach_generated_invoice_artifact",
                    "intended_use": "manual_operator_link_generated_invoice_artifact",
                    "enabled": False,
                    "disabled_reason": "This artifact-link intake path is not wired yet.",
                    "no_external_action": True,
                    "no_workbook_body_read": True,
                    "no_cell_read": True,
                },
            )
            authority_blocker = "Generation/export authority is required before creating the selected invoice artifact."
            capital["blockers"] = tuple(dict.fromkeys((authority_blocker, *tuple(capital.get("blockers") or ()))))
            capital["actionable_blockers"] = (
                {
                    "blocker_ref": f"invoice_review_blocker:{_short_hash(authority_blocker)}",
                    "operator_summary": authority_blocker,
                    "status": "NOT_READY",
                    "primary_action": capital["excel_invoice_artifact"]["manual_operator_actions"][0],
                    "disabled_reason": "Generation/export authority intake is not wired yet.",
                    "proof_refs": (receipt["receipt_id"],),
                },
                *tuple(capital.get("actionable_blockers") or ()),
            )
        capital["approval_footer"]["approval_ready"] = False
    capital["present_action_receipts"] = action_receipt_names
    capital["machine_proof"]["state_machine_overlay_applied"] = True
    capital["machine_proof"]["last_action_completion_receipt_written"] = receipt["completion_receipt_written"]
    capital["machine_proof"]["last_action_underlying_blocker_completed"] = receipt["underlying_blocker_completed"]
    capital["machine_proof"]["all_state_machine_authority_false"] = all(value is False for value in AUTHORITY_BOUNDARY.values())
    capital["machine_proof"]["content_hash"] = invoice_review_bundle._content_hash(capital)
    bundle_payload["machine_proof"]["state_machine_overlay_applied"] = True
    bundle_payload["machine_proof"]["content_hash"] = invoice_review_bundle._content_hash(bundle_payload)
    return bundle_payload


def refresh_bundle(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    generated_at: str | None = None,
    last_receipt: Mapping[str, Any] | None = None,
    client_ref: str | None = None,
    workflow_ref: str | None = None,
) -> tuple[dict[str, Any], Path, Path | None, bool]:
    state = load_state(db_path, generated_at=generated_at, client_ref=client_ref, workflow_ref=workflow_ref)
    completion_receipts = _completion_receipts_for_bundle(db_path, bundle_id=str(state["bundle_id"]))
    if state.get("client_ref") == "live_arts_md":
        import live_arts_md_invoice_review_bundle

        source_override = {
            "status": state.get("source_workbook_status") or "SOURCE_WORKBOOK_REQUIRED",
            "client_ref": "live_arts_md",
            "workflow_ref": state.get("workflow_ref") or "live_arts_md_invoice_workflow",
            "expected_display_name": live_arts_md_invoice_review_bundle.EXPECTED_WORKBOOK_NAME,
            "workbook_ref": state.get("source_workbook_ref"),
            "workbook_display_name": Path(str(state.get("source_workbook_mac_path") or state.get("source_workbook_pc_path") or "")).name
            or live_arts_md_invoice_review_bundle.EXPECTED_WORKBOOK_NAME
            if state.get("source_workbook_status") == "CONFIRMED"
            else None,
            "workbook_path_ref": state.get("source_workbook_mac_path") or state.get("source_workbook_pc_path"),
            "source_workbook_mac_path": state.get("source_workbook_mac_path"),
            "source_workbook_pc_path": state.get("source_workbook_pc_path"),
            "approved_for_metadata_read": state.get("source_workbook_status") == "CONFIRMED",
            "approved_for_cell_read": False,
            "no_workbook_body_read": True,
            "no_cell_read": True,
            "next_action": (
                "Select the Live Arts MD invoice page/period."
                if state.get("source_workbook_status") == "CONFIRMED"
                else "Choose the Live Arts MD source workbook."
            ),
        }
        payload = live_arts_md_invoice_review_bundle.build_payload(
            generated_at=generated_at,
            source_workbook_override=source_override,
            present_receipts=completion_receipts,
        )
        source_json, source_operator, bridge_json = live_arts_md_invoice_review_bundle.write_exports(
            payload,
            export_root,
            bridge_export_root=bridge_export_root,
        )
        return payload, source_json, bridge_json, bridge_json is not None

    payload = invoice_review_bundle.build_payload(generated_at=generated_at)
    payload["capital_hilton_bundle"] = invoice_review_bundle.build_capital_hilton_bundle(
        present_receipts=completion_receipts,
        generated_at=generated_at,
    )
    if last_receipt is None and state.get("last_receipt_id"):
        last_receipt = read_receipt(db_path, str(state["last_receipt_id"]))
    if last_receipt:
        payload = _overlay_bundle_state(
            payload,
            state,
            last_receipt,
            action_receipt_names=receipt_names(db_path, bundle_id=str(state["bundle_id"])),
        )
    source_json, source_operator = invoice_review_bundle.write_exports(payload, export_root)
    bridge_json: Path | None = None
    bridge_written = False
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_json = bridge_export_root / invoice_review_bundle.JSON_EXPORT_NAME
        shutil.copy2(source_json, bridge_json)
        operator_bridge = bridge_export_root / invoice_review_bundle.OPERATOR_EXPORT_NAME
        shutil.copy2(source_operator, operator_bridge)
        bridge_written = True
    return payload, source_json, bridge_json, bridge_written


def process_action(
    raw_request: Mapping[str, Any],
    *,
    db_path: Path = DEFAULT_DB_PATH,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    generated_at: str | None = None,
) -> InvoiceReviewActionResult:
    init_store(db_path)
    payload = raw_request.get("hidden_request_payload") if isinstance(raw_request.get("hidden_request_payload"), Mapping) else raw_request
    source_request_id = str(raw_request.get("request_id") or payload.get("request_id") or payload.get("source_request_id") or "unknown_invoice_review_action")
    action_kind = str(payload.get("action_kind") or payload.get("request_kind") or raw_request.get("action_kind") or raw_request.get("intended_use") or "")
    requested_client_ref = str(payload.get("client_ref") or raw_request.get("client_ref") or "capital_hilton")
    requested_workflow_ref = str(payload.get("workflow_ref") or raw_request.get("workflow_ref") or "")
    scope = _client_invoice_scope(requested_client_ref, requested_workflow_ref or None)
    state = load_state(
        db_path,
        generated_at=generated_at,
        client_ref=str(scope["client_ref"]),
        workflow_ref=str(scope["workflow_ref"]),
    )
    current_receipt_names = receipt_names(db_path, bundle_id=str(state["bundle_id"]))
    state["_receipt_names"] = current_receipt_names
    if (
        action_kind == "regenerate_or_link_invoice_artifact"
        and state.get("source_workbook_status") == "CONFIRMED"
        and "invoice_record_selection_operator_confirmed_receipt" not in current_receipt_names
    ):
        state["generated_artifact_status"] = "BLOCKED_NEEDS_INVOICE_RECORD_SELECTION"
        status, headline, body, next_action, receipt_name, completion = (
            "BLOCKED_NEEDS_INVOICE_RECORD_SELECTION",
            "Invoice artifact needs selection receipt",
            "OpenClaw needs the operator-confirmed invoice record selection receipt before it can inspect, regenerate, or link an invoice artifact. No invoice was generated or exported from this step.",
            "Confirm the invoice page/period first.",
            "generated_invoice_artifact_linkage_request_receipt",
            False,
        )
    else:
        status, headline, body, next_action, receipt_name, completion = _apply_action(state, action_kind)
    detail = body if status.startswith("BLOCKED") else next_action
    receipt = _receipt(
        source_request_id=source_request_id,
        action_kind=action_kind,
        receipt_name=receipt_name,
        status=status,
        completion=completion,
        generated_at=generated_at,
        client_ref=str(state["client_ref"]),
        workflow_ref=str(state["workflow_ref"]),
        bundle_id=str(state["bundle_id"]),
    )
    if action_kind == "regenerate_or_link_invoice_artifact":
        generator_audit = audit_current_invoice_artifact_generator(state)
        receipt["artifact_metadata"] = {
            "metadata_status": state.get("generated_artifact_metadata_status"),
            "sha256": state.get("generated_artifact_metadata_hash"),
            "file_size": state.get("generated_artifact_metadata_size"),
            "workbook_business_cells_read": False,
            "workbook_business_contents_parsed": False,
            "generation_or_export_performed": False,
        }
        receipt["generator_audit"] = {
            "existing_generator_found": generator_audit["existing_generator_found"],
            "generator_refs": generator_audit["generator_refs"],
            "generator_status": state.get("generated_artifact_generator_status"),
            "reason": state.get("generated_artifact_generator_reason") or ", ".join(generator_audit["reason_codes"]),
            "required_linkage_inputs": generator_audit["required_linkage_inputs"],
            "artifact_created": False,
            "artifact_linked": False,
        }
    if action_kind == "operator_reported_wrong_source_workbook":
        receipt["operator_correction"] = {
            "receipt_event": "operator_reported_wrong_source_workbook",
            "client_ref": "capital_hilton",
            "workflow_ref": invoice_review_bundle.CAPITAL_HILTON_WORKFLOW_REF,
            "no_file_deleted": True,
            "no_workbook_body_read": True,
            "no_cell_read": True,
            "no_generation_export": True,
            "no_external_action": True,
            "physical_deletion_allowed": False,
        }
    state["last_action_kind"] = action_kind
    state["last_receipt_id"] = receipt["receipt_id"]
    state["last_updated_at"] = generated_at
    with _connect(db_path) as conn:
        _upsert_state(conn, state)
        _write_receipt(conn, receipt)
    refreshed, source_bundle_path, bridge_bundle_path, bridge_written = refresh_bundle(
        db_path=db_path,
        export_root=export_root,
        bridge_export_root=bridge_export_root,
        generated_at=generated_at,
        last_receipt=receipt,
        client_ref=str(state["client_ref"]),
        workflow_ref=str(state["workflow_ref"]),
    )
    return InvoiceReviewActionResult(
        source_request_id=source_request_id,
        action_kind=action_kind,
        status=status,
        headline=headline,
        body=body,
        detail=detail,
        next_action=next_action,
        action_receipt=receipt,
        state_snapshot=state,
        refreshed_bundle=refreshed,
        source_bundle_path=source_bundle_path.as_posix(),
        bridge_bundle_path=bridge_bundle_path.as_posix() if bridge_bundle_path else None,
        bridge_mirror_written=bridge_written,
    )


def _selection_result_payload(raw_request: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = raw_request.get("hidden_request_payload")
    if isinstance(nested, Mapping):
        merged = dict(nested)
        merged.update({key: value for key, value in raw_request.items() if key not in merged})
        return merged
    return raw_request


def process_invoice_record_selection_result(
    raw_request: Mapping[str, Any],
    *,
    db_path: Path = DEFAULT_DB_PATH,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    generated_at: str | None = None,
) -> InvoiceReviewActionResult:
    init_store(db_path)
    payload = _selection_result_payload(raw_request)
    source_request_id = str(raw_request.get("request_id") or payload.get("source_request_id") or "unknown_invoice_record_selection_result")
    state = load_state(db_path, generated_at=generated_at)
    invoice_period_label = str(payload.get("invoice_period_label") or "").strip()
    invoice_record_label = str(
        payload.get("invoice_record_label") or payload.get("invoice_page_label") or payload.get("sheet_label") or ""
    ).strip()
    disposition = str(payload.get("generated_candidate_disposition") or "").strip()
    validation_errors: list[str] = []
    if str(payload.get("client_ref") or raw_request.get("client_ref") or "") != "capital_hilton":
        validation_errors.append("WRONG_CLIENT")
    if str(payload.get("workflow_ref") or raw_request.get("workflow_ref") or "") != invoice_review_bundle.CAPITAL_HILTON_WORKFLOW_REF:
        validation_errors.append("WRONG_WORKFLOW")
    if str(payload.get("source_action_ref") or payload.get("action_ref") or "") != "start_invoice_record_selection":
        validation_errors.append("WRONG_SOURCE_ACTION")
    if payload.get("operator_provided") is not True:
        validation_errors.append("OPERATOR_PROVIDED_REQUIRED")
    if payload.get("operator_confirmed") is not True:
        validation_errors.append("OPERATOR_CONFIRMED_REQUIRED")
    if not invoice_period_label:
        validation_errors.append("INVOICE_PERIOD_LABEL_REQUIRED")
    if not invoice_record_label:
        validation_errors.append("INVOICE_RECORD_OR_PAGE_LABEL_REQUIRED")
    for flag in (
        "no_workbook_body_read",
        "no_cell_read",
        "no_ocr",
        "no_external_action",
        "no_generation_export",
    ):
        if payload.get(flag) is not True:
            validation_errors.append(f"{flag.upper()}_REQUIRED")

    if validation_errors:
        status = "BLOCKED_INVALID_SELECTION_RESULT"
        headline = "Invoice page selection blocked"
        body = "OpenClaw could not record the invoice page/period because the selection result was incomplete or unsafe."
        next_action = "Send the invoice page/period result again with the required labels and safety flags."
        receipt_name = "invoice_record_selection_result_blocked_receipt"
    else:
        status = "REQUESTED"
        headline = "Invoice page/period recorded"
        body = "Invoice page/period recorded. Next: regenerate or link the invoice artifact for the selected record."
        next_action = "Next: regenerate or link the invoice artifact for the selected record."
        receipt_name = "invoice_record_selection_operator_confirmed_receipt"
        state["invoice_record_selection_status"] = "OPERATOR_CONFIRMED"
        state["invoice_period_status"] = "OPERATOR_CONFIRMED"
        state["invoice_period_label"] = invoice_period_label
        state["invoice_record_label"] = invoice_record_label
        state["generated_candidate_disposition"] = disposition or "unsure"
        state["operator_notes"] = str(payload.get("operator_notes") or "").strip() or None
        state["generated_artifact_status"] = "CANDIDATE_NEEDS_REGENERATION_OR_LINK"
        state["approval_readiness_status"] = "BLOCKED_PREREQUISITES"

    receipt = _receipt(
        source_request_id=source_request_id,
        action_kind="confirm_invoice_record_selection",
        receipt_name=receipt_name,
        status=status,
        completion=False,
        generated_at=generated_at,
    )
    receipt["validation_errors"] = tuple(validation_errors)
    state["last_action_kind"] = "confirm_invoice_record_selection"
    state["last_receipt_id"] = receipt["receipt_id"]
    state["last_updated_at"] = generated_at
    with _connect(db_path) as conn:
        _upsert_state(conn, state)
        _write_receipt(conn, receipt)
    refreshed, source_bundle_path, bridge_bundle_path, bridge_written = refresh_bundle(
        db_path=db_path,
        export_root=export_root,
        bridge_export_root=bridge_export_root,
        generated_at=generated_at,
        last_receipt=receipt,
    )
    return InvoiceReviewActionResult(
        source_request_id=source_request_id,
        action_kind="confirm_invoice_record_selection",
        status=status,
        headline=headline,
        body=body,
        detail="; ".join(validation_errors) if validation_errors else next_action,
        next_action=next_action,
        action_receipt=receipt,
        state_snapshot=state,
        refreshed_bundle=refreshed,
        source_bundle_path=source_bundle_path.as_posix(),
        bridge_bundle_path=bridge_bundle_path.as_posix() if bridge_bundle_path else None,
        bridge_mirror_written=bridge_written,
    )


def _source_workbook_result_payload(raw_request: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = raw_request.get("hidden_request_payload")
    if isinstance(nested, Mapping):
        merged = dict(nested)
        merged.update({key: value for key, value in raw_request.items() if key not in merged})
        return merged
    return raw_request


def _pc_path_from_mac_path(mac_path: str) -> str:
    if mac_path.startswith("/Volumes/openclaw_e/"):
        return "/mnt/e/openclaw/" + mac_path.removeprefix("/Volumes/openclaw_e/")
    return ""


def process_source_workbook_selection_result(
    raw_request: Mapping[str, Any],
    *,
    db_path: Path = DEFAULT_DB_PATH,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    generated_at: str | None = None,
) -> InvoiceReviewActionResult:
    init_store(db_path)
    payload = _source_workbook_result_payload(raw_request)
    source_request_id = str(raw_request.get("request_id") or payload.get("source_request_id") or "unknown_source_workbook_selection_result")
    requested_client_ref = str(payload.get("client_ref") or raw_request.get("client_ref") or "capital_hilton")
    requested_workflow_ref = str(payload.get("workflow_ref") or raw_request.get("workflow_ref") or "")
    scope = _client_invoice_scope(requested_client_ref, requested_workflow_ref or None)
    state = load_state(
        db_path,
        generated_at=generated_at,
        client_ref=str(scope["client_ref"]),
        workflow_ref=str(scope["workflow_ref"]),
    )
    client_display_name = str(scope["client_display_name"])
    selected_mac_path = str(payload.get("selected_workbook_mac_path") or payload.get("source_workbook_mac_path") or "").strip()
    selected_pc_path = str(payload.get("selected_workbook_pc_path") or payload.get("source_workbook_pc_path") or "").strip()
    artifact_ref = str(payload.get("artifact_ref") or payload.get("selected_artifact_ref") or "").strip()
    workbook_extension = str(payload.get("workbook_extension") or payload.get("selected_workbook_extension") or "").strip().lower()
    workbook_display_name = str(payload.get("workbook_display_name") or payload.get("selected_workbook_display_name") or "").strip()
    workbook_size = payload.get("workbook_size_bytes") or payload.get("file_size_bytes")
    if not selected_pc_path and selected_mac_path:
        selected_pc_path = _pc_path_from_mac_path(selected_mac_path)
    validation_errors: list[str] = []
    if requested_client_ref != scope["client_ref"]:
        validation_errors.append("WRONG_CLIENT")
    if requested_workflow_ref != scope["workflow_ref"]:
        validation_errors.append("WRONG_WORKFLOW")
    if scope["client_ref"] not in {"capital_hilton", "live_arts_md"}:
        validation_errors.append("UNSUPPORTED_CLIENT")
    if str(payload.get("intended_use") or "") not in {"confirm_source_workbook_reference", "replace_source_workbook_reference_result"}:
        validation_errors.append("WRONG_INTENDED_USE")
    if payload.get("operator_provided") is not True:
        validation_errors.append("OPERATOR_PROVIDED_REQUIRED")
    if payload.get("operator_confirmed") is not True:
        validation_errors.append("OPERATOR_CONFIRMED_REQUIRED")
    for flag in (
        "no_workbook_body_read",
        "no_cell_read",
        "no_external_action",
        "physical_deletion_allowed",
    ):
        expected = False if flag == "physical_deletion_allowed" else True
        if payload.get(flag) is not expected:
            validation_errors.append(f"{flag.upper()}_{'FALSE' if expected is False else 'REQUIRED'}")
    if not artifact_ref and not selected_mac_path and not selected_pc_path:
        validation_errors.append("WORKBOOK_PATH_OR_ARTIFACT_REF_REQUIRED")
    metadata: dict[str, Any] = {
        "metadata_status": "NOT_CHECKED",
        "workbook_business_cells_read": False,
        "spreadsheet_cell_read_performed": False,
    }
    if selected_pc_path:
        metadata = inspect_workbook_candidate_metadata(Path(selected_pc_path))
        if metadata["metadata_status"] != "METADATA_VALID":
            validation_errors.append(str(metadata["metadata_status"]))
    elif selected_mac_path and not selected_mac_path.lower().endswith(".xlsx"):
        validation_errors.append("INVALID_EXTENSION")
    elif artifact_ref:
        if workbook_extension and workbook_extension not in {".xlsx", ".xlsm", ".xls"}:
            validation_errors.append("INVALID_EXTENSION")
        metadata = {
            "metadata_status": "ARTIFACT_REF_METADATA_VALID" if not validation_errors else "ARTIFACT_REF_METADATA_BLOCKED",
            "artifact_ref": artifact_ref,
            "workbook_display_name": workbook_display_name,
            "workbook_extension": workbook_extension,
            "workbook_size_bytes": workbook_size,
            "workbook_business_cells_read": False,
            "spreadsheet_cell_read_performed": False,
        }
    if validation_errors:
        status = "BLOCKED_INVALID_SOURCE_WORKBOOK_SELECTION"
        headline = "Source workbook selection blocked"
        body = "OpenClaw could not confirm the source workbook because the selection result was incomplete or unsafe."
        next_action = f"Choose the correct {client_display_name} source workbook with the required safety flags."
        receipt_name = "source_workbook_selection_blocked_receipt"
        completion = False
    else:
        status = "COMPLETED"
        headline = "Source workbook confirmed"
        body = "Source workbook reference recorded. No workbook body or cells were read. Select the invoice page/period again from the confirmed workbook."
        next_action = "Select the invoice page/period again from the confirmed workbook."
        receipt_name = "source_workbook_reference_confirmed_receipt"
        completion = True
        state["source_workbook_status"] = "CONFIRMED"
        state["source_workbook_ref"] = artifact_ref or f"operator_selected_workbook:{_short_hash(selected_mac_path, selected_pc_path)}"
        state["source_workbook_mac_path"] = selected_mac_path or None
        state["source_workbook_pc_path"] = selected_pc_path or None
        state["invoice_record_selection_status"] = "NEEDS_RESELECTION_AFTER_SOURCE_WORKBOOK_CORRECTION"
        state["invoice_period_status"] = "NEEDS_RESELECTION_AFTER_SOURCE_WORKBOOK_CORRECTION"
        state["generated_artifact_status"] = "INVALIDATED_BY_WRONG_SOURCE_WORKBOOK"
        state["approval_readiness_status"] = "BLOCKED_PREREQUISITES"
    receipt = _receipt(
        source_request_id=source_request_id,
        action_kind="confirm_source_workbook_selection",
        receipt_name=receipt_name,
        status=status,
        completion=completion,
        generated_at=generated_at,
        client_ref=str(scope["client_ref"]),
        workflow_ref=str(scope["workflow_ref"]),
        bundle_id=str(scope["bundle_id"]),
    )
    receipt["validation_errors"] = tuple(validation_errors)
    receipt["source_workbook_selection"] = {
        "artifact_ref": artifact_ref,
        "selected_workbook_mac_path": selected_mac_path,
        "selected_workbook_pc_path": selected_pc_path,
        "workbook_display_name": workbook_display_name,
        "workbook_extension": workbook_extension,
        "workbook_size_bytes": workbook_size,
        "metadata": metadata,
        "no_workbook_body_read": True,
        "no_cell_read": True,
        "no_external_action": True,
        "physical_deletion_allowed": False,
    }
    state["last_action_kind"] = "confirm_source_workbook_selection"
    state["last_receipt_id"] = receipt["receipt_id"]
    state["last_updated_at"] = generated_at
    with _connect(db_path) as conn:
        _upsert_state(conn, state)
        _write_receipt(conn, receipt)
    refreshed, source_bundle_path, bridge_bundle_path, bridge_written = refresh_bundle(
        db_path=db_path,
        export_root=export_root,
        bridge_export_root=bridge_export_root,
        generated_at=generated_at,
        last_receipt=receipt,
        client_ref=str(scope["client_ref"]),
        workflow_ref=str(scope["workflow_ref"]),
    )
    return InvoiceReviewActionResult(
        source_request_id=source_request_id,
        action_kind="confirm_source_workbook_selection",
        status=status,
        headline=headline,
        body=body,
        detail="; ".join(validation_errors) if validation_errors else next_action,
        next_action=next_action,
        action_receipt=receipt,
        state_snapshot=state,
        refreshed_bundle=refreshed,
        source_bundle_path=source_bundle_path.as_posix(),
        bridge_bundle_path=bridge_bundle_path.as_posix() if bridge_bundle_path else None,
        bridge_mirror_written=bridge_written,
    )


def read_receipt(db_path: Path, receipt_id: str) -> dict[str, Any] | None:
    init_store(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM invoice_review_receipts WHERE receipt_id = ?",
            (receipt_id,),
        ).fetchone()
    return dict(row) if row else None
