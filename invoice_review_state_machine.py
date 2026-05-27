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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import invoice_review_bundle


SCHEMA_VERSION = "invoice_review_state_machine_v0"
DEFAULT_DB_PATH = Path(".openclaw/invoice_review/invoice_review_state.sqlite")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")

ACTION_TO_RECEIPT = {
    "confirm_source_workbook_reference": "active_workbook_confirmed_receipt",
    "replace_source_workbook_reference": "source_workbook_replacement_request_receipt",
    "start_invoice_record_selection": "invoice_record_selection_started_receipt",
    "regenerate_or_link_invoice_artifact": "generated_invoice_artifact_linkage_request_receipt",
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
}

COMPLETION_RECEIPTS = {
    "active_workbook_confirmed_receipt",
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
              generated_artifact_status TEXT NOT NULL,
              coupa_proof_status TEXT NOT NULL,
              recipient_confirmation_status TEXT NOT NULL,
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
              generated_at TEXT
            );
            """
        )


def _default_state(*, generated_at: str | None = None) -> dict[str, Any]:
    return {
        "bundle_id": invoice_review_bundle.CAPITAL_HILTON_BUNDLE_ID,
        "client_ref": "capital_hilton",
        "workflow_ref": invoice_review_bundle.CAPITAL_HILTON_WORKFLOW_REF,
        "source_workbook_status": "CANDIDATE_PRESENT",
        "invoice_record_selection_status": "NEEDS_OPERATOR_SELECTION",
        "invoice_period_status": "NEEDS_OPERATOR_SELECTION",
        "generated_artifact_status": "CANDIDATE_NEEDS_LINKAGE",
        "coupa_proof_status": "MISSING",
        "recipient_confirmation_status": "CANDIDATE_UNCONFIRMED",
        "clara_draft_status": "DRAFT_ONLY",
        "approval_readiness_status": "BLOCKED_PREREQUISITES",
        "email_send_status": "NOT_SENT",
        "payment_watch_status": "NOT_READY",
        "ledger_tax_status": "NOT_READY",
        "last_action_kind": None,
        "last_receipt_id": None,
        "last_updated_at": generated_at,
    }


def load_state(db_path: Path = DEFAULT_DB_PATH, *, generated_at: str | None = None) -> dict[str, Any]:
    init_store(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM invoice_review_states WHERE bundle_id = ?",
            (invoice_review_bundle.CAPITAL_HILTON_BUNDLE_ID,),
        ).fetchone()
        if row:
            return dict(row)
        state = _default_state(generated_at=generated_at)
        _upsert_state(conn, state)
        return state


def _upsert_state(conn: sqlite3.Connection, state: Mapping[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO invoice_review_states (
          bundle_id, client_ref, workflow_ref, source_workbook_status,
          invoice_record_selection_status, invoice_period_status,
          generated_artifact_status, coupa_proof_status,
          recipient_confirmation_status, clara_draft_status,
          approval_readiness_status, email_send_status, payment_watch_status,
          ledger_tax_status, last_action_kind, last_receipt_id, last_updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(bundle_id) DO UPDATE SET
          source_workbook_status=excluded.source_workbook_status,
          invoice_record_selection_status=excluded.invoice_record_selection_status,
          invoice_period_status=excluded.invoice_period_status,
          generated_artifact_status=excluded.generated_artifact_status,
          coupa_proof_status=excluded.coupa_proof_status,
          recipient_confirmation_status=excluded.recipient_confirmation_status,
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
            state["generated_artifact_status"],
            state["coupa_proof_status"],
            state["recipient_confirmation_status"],
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


def receipt_names(db_path: Path = DEFAULT_DB_PATH) -> tuple[str, ...]:
    init_store(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT receipt_name FROM invoice_review_receipts ORDER BY receipt_name"
        ).fetchall()
    return tuple(str(row["receipt_name"]) for row in rows)


def _completion_receipts_for_bundle(db_path: Path) -> tuple[str, ...]:
    names = receipt_names(db_path)
    return tuple(name for name in names if name in COMPLETION_RECEIPTS)


def _receipt(
    *,
    source_request_id: str,
    action_kind: str,
    receipt_name: str,
    status: str,
    completion: bool,
    generated_at: str | None,
) -> dict[str, Any]:
    receipt_id = f"invoice_review:{receipt_name}:{_short_hash(source_request_id, action_kind, status)}"
    return {
        "receipt_id": receipt_id,
        "receipt_type": "invoice_review_action_progress_receipt",
        "receipt_name": receipt_name,
        "source_request_id": source_request_id,
        "bundle_id": invoice_review_bundle.CAPITAL_HILTON_BUNDLE_ID,
        "workflow_ref": invoice_review_bundle.CAPITAL_HILTON_WORKFLOW_REF,
        "client_ref": "capital_hilton",
        "action_kind": action_kind,
        "status": status,
        "underlying_blocker_completed": completion,
        "completion_receipt_written": completion,
        "external_action_performed": False,
        "generated_at": generated_at,
    }


def _write_receipt(conn: sqlite3.Connection, receipt: Mapping[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO invoice_review_receipts (
          receipt_id, receipt_type, source_request_id, bundle_id, client_ref,
          workflow_ref, action_kind, status, completion_receipt_written,
          underlying_blocker_completed, external_action_performed, receipt_name,
          generated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            receipt.get("generated_at"),
        ),
    )


def _apply_action(state: dict[str, Any], action_kind: str) -> tuple[str, str, str, str, str, bool]:
    if action_kind == "confirm_source_workbook_reference":
        if state["source_workbook_status"] not in {"CANDIDATE_PRESENT", "REPLACEMENT_REQUESTED", "CONFIRMED"}:
            return ("BLOCKED_SOURCE_WORKBOOK_MISSING", "Source workbook missing", "OpenClaw needs a source workbook candidate first.", "Choose the source workbook in Mission Control.", "source_workbook_missing_receipt", False)
        state["source_workbook_status"] = "CONFIRMED"
        return ("COMPLETED", "Source workbook confirmed", "Source workbook reference is confirmed.", "Next: select the Capital Hilton invoice page/period.", "active_workbook_confirmed_receipt", True)
    if action_kind == "replace_source_workbook_reference":
        state["source_workbook_status"] = "REPLACEMENT_REQUESTED"
        return ("REQUESTED", "Choose the correct source workbook", "Choose the replacement source workbook. No file will be deleted.", "Select the replacement workbook in Mission Control.", "source_workbook_replacement_request_receipt", False)
    if action_kind == "start_invoice_record_selection":
        state["invoice_record_selection_status"] = "NEEDS_OPERATOR_SELECTION"
        state["invoice_period_status"] = "NEEDS_OPERATOR_SELECTION"
        return ("REQUESTED", "Starting invoice page selection", "Let's select the Capital Hilton invoice page/period.", "Choose the invoice page or period in Mission Control.", "invoice_record_selection_started_receipt", False)
    if action_kind == "regenerate_or_link_invoice_artifact":
        if state["invoice_record_selection_status"] != "SELECTED" or state["invoice_period_status"] != "CONFIRMED":
            state["generated_artifact_status"] = "BLOCKED_NEEDS_INVOICE_RECORD_SELECTION"
            return ("BLOCKED_NEEDS_INVOICE_RECORD_SELECTION", "Invoice artifact needs linkage", "OpenClaw needs the invoice page/period before it can link or regenerate an artifact. No invoice was generated or exported from this step.", "Select the invoice page/period first.", "generated_invoice_artifact_linkage_request_receipt", False)
        state["generated_artifact_status"] = "GENERATOR_NOT_WIRED"
        return ("BLOCKED_GENERATOR_NOT_WIRED", "Artifact generation rail not wired yet", "Artifact generation/linkage is not wired in this safe pass.", "Use the governed artifact rail when it is available.", "generated_invoice_artifact_linkage_request_receipt", False)
    if action_kind == "request_coupa_submission_proof":
        state["coupa_proof_status"] = "PROOF_REQUESTED"
        return ("REQUESTED", "Starting Coupa proof step", "Upload or provide Coupa submission proof when available. Nothing will be submitted from this step.", "Provide Coupa submission proof when available.", "coupa_proof_intake_requested_receipt", False)
    if action_kind == "review_and_confirm_recipients":
        state["recipient_confirmation_status"] = "REVIEW_REQUESTED_EMAILS_MISSING"
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
    if state["source_workbook_status"] == "REPLACEMENT_REQUESTED":
        status_by_title["Active workbook"] = "REQUESTED"
    if state["invoice_record_selection_status"] == "NEEDS_OPERATOR_SELECTION":
        status_by_title["Invoice page/period"] = "IN_PROGRESS" if receipt["receipt_name"] == "invoice_record_selection_started_receipt" else "NEEDS_ACTION"
    if state["generated_artifact_status"].startswith("BLOCKED"):
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
) -> tuple[dict[str, Any], Path, Path | None, bool]:
    completion_receipts = _completion_receipts_for_bundle(db_path)
    state = load_state(db_path, generated_at=generated_at)
    payload = invoice_review_bundle.build_payload(generated_at=generated_at)
    payload["capital_hilton_bundle"] = invoice_review_bundle.build_capital_hilton_bundle(
        present_receipts=completion_receipts,
        generated_at=generated_at,
    )
    if last_receipt:
        payload = _overlay_bundle_state(
            payload,
            state,
            last_receipt,
            action_receipt_names=receipt_names(db_path),
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
    state = load_state(db_path, generated_at=generated_at)
    status, headline, body, next_action, receipt_name, completion = _apply_action(state, action_kind)
    detail = body if status.startswith("BLOCKED") else next_action
    receipt = _receipt(
        source_request_id=source_request_id,
        action_kind=action_kind,
        receipt_name=receipt_name,
        status=status,
        completion=completion,
        generated_at=generated_at,
    )
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


def read_receipt(db_path: Path, receipt_id: str) -> dict[str, Any] | None:
    init_store(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM invoice_review_receipts WHERE receipt_id = ?",
            (receipt_id,),
        ).fetchone()
    return dict(row) if row else None
