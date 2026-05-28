"""Live Arts MD operator-provided workbook handoff fixture.

The facts in this module are operator-provided structured handoff facts. This
module does not read workbook bodies, parse cells, generate/export invoices,
send email, read bank ledgers, post ledgers, or mutate production business
state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "live_arts_md_workbook_handoff_v0"
READ_MODEL_ID = "live_arts_md_invoice_candidate_register"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-28T00:00:00+00:00"

CLIENT_REF = "live_arts_md"
CLIENT_DISPLAY_NAME = "Live Arts MD"
WORKFLOW_REF = "live_arts_md_invoice_workflow"
SOURCE_WORKBOOK_MAC_PATH = "/Users/hwinshipwheatley/Documents/Invoices/Invoice Clinets/Invoice Live Arts MD! Running.xlsx"
SOURCE_WORKBOOK_REF = "workbook_ref:client_invoice:live_arts_md:running_operator_confirmed"

AUTHORITY_BOUNDARY = {
    "operator_provided": True,
    "workbook_body_read_performed": False,
    "spreadsheet_cell_read_performed": False,
    "ocr_performed": False,
    "invoice_generation_performed": False,
    "pdf_export_performed": False,
    "email_send_performed": False,
    "gmail_access_performed": False,
    "browser_automation_performed": False,
    "coupa_access_performed": False,
    "bank_ledger_read_performed": False,
    "ledger_posting_performed": False,
    "production_business_mutation_performed": False,
    "live_model_call_performed": False,
    "tool_action_performed": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: Mapping[str, Any]) -> str:
    clone = json.loads(stable_json(dict(payload)))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def build_handoff_receipt(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    receipt_id = f"operator_handoff:live_arts_md_workbook:{_short_hash(SOURCE_WORKBOOK_MAC_PATH, generated_at)}"
    return {
        "receipt_id": receipt_id,
        "receipt_event": "operator_provided_live_arts_md_workbook_handoff",
        "receipt_type": "operator_provided_workbook_handoff_receipt",
        "client_ref": CLIENT_REF,
        "workflow_ref": WORKFLOW_REF,
        "source_workbook_ref": SOURCE_WORKBOOK_REF,
        "source_workbook_mac_path": SOURCE_WORKBOOK_MAC_PATH,
        "workbook_body_read": False,
        "cell_read": False,
        "operator_provided": True,
        "confidence": "operator_handoff",
        "proof_refs": (
            "June 2026 Speaker Rental!G2:G5",
            "June 2026 Speaker Rental!F40:G43",
            "June 2026 Speaker Rental!B49:G53",
            "June 2026 AV Tech!G2:G5",
            "June 2026 AV Tech!F40:G43",
            "June 2026 AV Tech!B49:G53",
            "July 2026!G2:G5",
            "July 2026!B49:G54",
            "Invoice Register!A1:K7",
        ),
        "generated_at": generated_at,
    }


def _candidate(
    *,
    invoice_id: str,
    sheet_label: str,
    work_type: str,
    amount: int,
    invoice_status: str,
    receipt_status: str,
    review_status: str,
    readiness_status: str,
    ranges: tuple[str, ...],
    send_ready: bool,
) -> dict[str, Any]:
    return {
        "invoice_id": invoice_id,
        "sheet_label": sheet_label,
        "work_type": work_type,
        "amount": amount,
        "amount_display": f"${amount:,.0f}",
        "client": CLIENT_DISPLAY_NAME,
        "invoice_status": invoice_status,
        "receipt_status": receipt_status,
        "review_status": review_status,
        "readiness_status": readiness_status,
        "operator_provided_ranges": ranges,
        "send_readiness": "BLOCKED_NEEDS_ARTIFACT_RECIPIENT_GUARDIAN_APPROVAL"
        if send_ready
        else "NOT_SEND_READY",
        "sent": False,
        "submitted": False,
        "paid": False,
        "ledger_posted": False,
        "artifact_status": "NOT_READY_REQUIRES_MANUAL_EXPORT_OR_LINK",
        "payment_watch_status": "READINESS_ONLY_NOT_ACTIVE",
        "ledger_handoff_status": "PLANNING_ONLY_NO_MUTATION",
        "bank_ledger_source_of_truth_for_actual_receipts": True,
        "workbook_source_of_truth_for_invoice_intent": True,
    }


def invoice_candidates() -> tuple[dict[str, Any], ...]:
    return (
        _candidate(
            invoice_id="2026-1001",
            sheet_label="June 2026 Speaker Rental",
            work_type="Speaker Rental",
            amount=900,
            invoice_status="Draft - ready to send",
            receipt_status="UNPAID",
            review_status="OPERATOR_HANDOFF_DRAFT_READY_TO_SEND",
            readiness_status="NEEDS_ARTIFACT_RECIPIENT_GUARDIAN_APPROVAL",
            ranges=(
                "June 2026 Speaker Rental!G2:G5",
                "June 2026 Speaker Rental!F40:G43",
                "June 2026 Speaker Rental!B49:G53",
            ),
            send_ready=True,
        ),
        _candidate(
            invoice_id="2026-1002",
            sheet_label="June 2026 AV Tech",
            work_type="AV Tech",
            amount=4625,
            invoice_status="Draft - verify before send",
            receipt_status="UNPAID",
            review_status="VERIFY_BEFORE_SEND",
            readiness_status="NEEDS_OPERATOR_VERIFICATION",
            ranges=(
                "June 2026 AV Tech!G2:G5",
                "June 2026 AV Tech!F40:G43",
                "June 2026 AV Tech!B49:G53",
            ),
            send_ready=False,
        ),
        _candidate(
            invoice_id="2026-1003",
            sheet_label="July 2026",
            work_type="Future invoice",
            amount=0,
            invoice_status="Future/draft",
            receipt_status="UNPAID",
            review_status="FUTURE_DRAFT_CHECK_JUNE_PAYMENT_STATUS_FIRST",
            readiness_status="FUTURE_NOT_SEND_READY",
            ranges=("July 2026!G2:G5", "July 2026!B49:G54"),
            send_ready=False,
        ),
    )


def _select_action(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "action_ref": f"live_arts_md_invoice_candidate_select:{candidate['invoice_id']}",
        "action_kind": "select_invoice_candidate",
        "label": f"Select {candidate['sheet_label']}",
        "enabled": candidate["invoice_id"] in {"2026-1001", "2026-1002"},
        "disabled_reason": None
        if candidate["invoice_id"] in {"2026-1001", "2026-1002"}
        else "Review this future invoice later after June payment status is known.",
        "operator_visible_message": f"Selecting Live Arts MD invoice {candidate['invoice_id']}.",
        "hidden_request_payload": {
            "request_type": "INVOICE_REVIEW_ACTION_REQUEST",
            "client_ref": CLIENT_REF,
            "workflow_ref": WORKFLOW_REF,
            "intended_use": "select_live_arts_md_invoice_candidate",
            "invoice_id": candidate["invoice_id"],
            "sheet_label": candidate["sheet_label"],
            "work_type": candidate["work_type"],
            "operator_provided": True,
            "no_workbook_body_read": True,
            "no_cell_read": True,
            "no_external_action": True,
            "no_generation_export": True,
            "email_send_allowed": False,
            "ledger_posting_allowed": False,
        },
    }


def build_candidate_register(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    candidates = tuple({**candidate, "selection_action": _select_action(candidate)} for candidate in invoice_candidates())
    receipt = build_handoff_receipt(generated_at=generated_at)
    register = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "client_ref": CLIENT_REF,
        "client_display_name": CLIENT_DISPLAY_NAME,
        "workflow_ref": WORKFLOW_REF,
        "source_workbook": {
            "source_workbook_ref": SOURCE_WORKBOOK_REF,
            "source_workbook_mac_path": SOURCE_WORKBOOK_MAC_PATH,
            "source_workbook_status": "CONFIRMED_BY_OPERATOR_HANDOFF",
            "workbook_body_read": False,
            "cell_read": False,
        },
        "operator_handoff_receipt": receipt,
        "candidate_count": len(candidates),
        "invoice_candidates": candidates,
        "primary_next_action": "Choose which Live Arts MD invoice to prepare.",
        "urgent_actions": (
            candidates[0]["selection_action"],
            candidates[1]["selection_action"],
            {
                **candidates[2]["selection_action"],
                "label": "Review July 2026 later",
            },
        ),
        "receipt_payment_block_pattern": {
            "invoice_status": "C50",
            "amount_received": "E50",
            "balance_due": "G50",
            "receipt_status": "C51",
            "payment_date": "E51",
            "ledger_match": "G51",
        },
        "contact_ambiguity": {
            "status": "NEEDS_OPERATOR_CONFIRMATION",
            "ambiguous_names": ("Dance", "Dane"),
            "reason": "Operator target said Dance; handoff mentioned Dane in alias-table context.",
            "do_not_silently_choose": True,
            "emails_invented": False,
        },
        "expected_receivable_payment_watch_readiness": {
            "expected_ar_layer_required": True,
            "actual_bank_transactions_separate": True,
            "payment_watch_status": "READINESS_ONLY_NOT_ACTIVE",
            "active_only_after_send_or_manual_send_receipt": True,
            "bank_ledger_read_performed": False,
            "ledger_posting_allowed": False,
        },
        "ledger_planning": {
            "current_ledger_pointer_manifest_required": True,
            "hardcoded_dated_ledger_path_allowed": False,
            "alias_map_requires_human_approval": True,
            "handles_partial_multi_invoice_multi_deposit_overpayment_credit_writeoff_variance": True,
            "speaker_rental_variance_note": "$900 accepted vs. $1,100 internal record issue requires operator-approved handling.",
            "silent_ledger_mutation_allowed": False,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "operator_provided_not_workbook_parsed": True,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "workbook_existence_does_not_mark_sent_paid_or_ledger_posted": True,
            "no_action_authority": all(value is False for key, value in AUTHORITY_BOUNDARY.items() if key != "operator_provided"),
            "content_hash": "",
        },
    }
    register["machine_proof"]["content_hash"] = _content_hash(register)
    return register


def process_invoice_candidate_selection(
    payload: Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    invoice_id = str(payload.get("invoice_id") or "")
    by_id = {candidate["invoice_id"]: candidate for candidate in invoice_candidates()}
    candidate = by_id.get(invoice_id)
    validation_errors: list[str] = []
    if payload.get("client_ref") != CLIENT_REF:
        validation_errors.append("WRONG_CLIENT")
    if payload.get("workflow_ref") != WORKFLOW_REF:
        validation_errors.append("WRONG_WORKFLOW")
    if payload.get("operator_provided") is not True:
        validation_errors.append("OPERATOR_PROVIDED_REQUIRED")
    for flag in ("no_workbook_body_read", "no_cell_read", "no_external_action"):
        if payload.get(flag) is not True:
            validation_errors.append(f"{flag.upper()}_REQUIRED")
    if candidate is None:
        validation_errors.append("UNKNOWN_INVOICE_CANDIDATE")
    status = "BLOCKED" if validation_errors else "SELECTED_REQUIRES_ARTIFACT_AND_APPROVAL"
    receipt = {
        "receipt_id": f"live_arts_md_invoice_candidate_selected:{_short_hash(invoice_id, status)}",
        "receipt_event": "live_arts_md_invoice_candidate_selected_receipt",
        "client_ref": CLIENT_REF,
        "workflow_ref": WORKFLOW_REF,
        "invoice_id": invoice_id,
        "sheet_label": candidate.get("sheet_label") if candidate else None,
        "status": status,
        "validation_errors": tuple(validation_errors),
        "workbook_body_read": False,
        "cell_read": False,
        "sent": False,
        "paid": False,
        "ledger_posted": False,
        "artifact_ready": False,
        "approval_ready": False,
        "generated_at": generated_at,
    }
    return {
        "status": status,
        "receipt": receipt,
        "selected_candidate": candidate,
        "next_action": "Export or link the selected invoice artifact manually."
        if not validation_errors
        else "Choose a valid Live Arts MD invoice candidate.",
    }


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    return build_candidate_register(generated_at=generated_at)


def format_operator(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Live Arts MD Invoice Candidate Register",
        "",
        "Facts are operator-provided workbook handoff facts; OpenClaw did not parse workbook cells.",
        f"- Next action: {payload['primary_next_action']}",
        f"- Candidates: {payload['candidate_count']}",
    ]
    for candidate in payload["invoice_candidates"]:
        lines.append(
            f"- {candidate['sheet_label']} / {candidate['invoice_id']}: {candidate['amount_display']} - {candidate['invoice_status']} / sent=false / paid=false"
        )
    lines.extend(
        [
            "",
            "No workbook body/cell read, invoice generation/export, email send, bank ledger read, or ledger mutation occurred.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_exports(
    payload: Mapping[str, Any],
    export_root: Path = DEFAULT_EXPORT_ROOT,
    *,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
) -> tuple[Path, Path, Path | None]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator(payload), encoding="utf-8")
    bridge_path = None
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_path = bridge_export_root / JSON_EXPORT_NAME
        shutil.copy2(json_path, bridge_path)
    return json_path, operator_path, bridge_path


def export_register(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_payload(generated_at=generated_at)
    json_path, operator_path, bridge_path = write_exports(payload, export_root, bridge_export_root=bridge_export_root)
    return {
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "bridge_path": bridge_path.as_posix() if bridge_path else None,
        "candidate_count": payload["candidate_count"],
        "primary_next_action": payload["primary_next_action"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Live Arts MD invoice candidate register.")
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--bridge-export-root", default=DEFAULT_BRIDGE_EXPORT_ROOT.as_posix())
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--generated-at")
    args = parser.parse_args(argv)
    result = export_register(
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
