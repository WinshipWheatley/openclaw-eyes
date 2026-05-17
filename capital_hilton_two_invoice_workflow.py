"""Capital Hilton two-invoice workflow contract v0.

This read-model describes the Hilton-specific invoice overlay:
Coupa is the payment-generating invoice path, while the Excel/generated
invoice is a companion communication/reference artifact. It does not submit
Coupa, create invoices, send email, write spreadsheets, store secrets/PII blobs,
run browser automation, or grant runtime/send/submit authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from capital_hilton_actionable_review_packet import DEFAULT_EXPORT_ROOT, stable_json


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "capital_hilton_two_invoice_workflow_v0"
JSON_EXPORT_NAME = "capital_hilton_two_invoice_workflow.json"
OPERATOR_EXPORT_NAME = "capital_hilton_two_invoice_workflow_OPERATOR.md"
DEFAULT_ACTIONABLE_PACKET_PATH = DEFAULT_EXPORT_ROOT / "capital_hilton_actionable_review_packet.json"
DEFAULT_CONFIRMATION_RECEIPT_PATH = DEFAULT_EXPORT_ROOT / "capital_hilton_manual_confirmation_receipt.json"

HILTON_COUPA_OVERLAY_ID = "hilton_coupa_supplier_portal"
BASE_INVOICE_WORKFLOW_ID = "base_invoice_workflow"

NO_AUTHORITY_FLAGS = {
    "review_only": True,
    "external_action_authorized": False,
    "coupa_invoice_created": False,
    "coupa_submit_triggered": False,
    "portal_submitted": False,
    "portal_submit_allowed": False,
    "browser_automation_added": False,
    "email_send_triggered": False,
    "email_send_allowed": False,
    "spreadsheet_cells_read": False,
    "spreadsheet_write_triggered": False,
    "spreadsheet_write_allowed": False,
    "credentials_accessed": False,
    "credential_storage_allowed": False,
    "raw_pii_or_secret_stored": False,
    "home_address_stored": False,
    "bank_details_stored": False,
    "portal_password_stored": False,
    "token_material_stored": False,
    "check_image_stored": False,
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "approval_authority_added": False,
    "repo_b_executed": False,
    "financial_truth_claimed": False,
    "payment_marked_paid": False,
}


@dataclass(frozen=True)
class TwoInvoiceWorkflowExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    base_invoice_workflow_preserved: bool
    hilton_coupa_overlay_modeled: bool
    coupa_payment_invoice_modeled: bool
    excel_companion_invoice_modeled: bool
    po_budget_context_modeled: bool
    protected_evidence_slots_modeled: bool
    runtime_authority_added: bool
    send_or_submit_authority_added: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _rooted(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return ROOT / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _read_json_if_present(path: str | Path) -> dict[str, Any]:
    target = _rooted(path)
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _amount(value: str) -> dict[str, Any]:
    decimal = Decimal(value)
    return {
        "amount_text": f"{decimal:.2f} USD",
        "currency": "USD",
        "amount_value": f"{decimal:.2f}",
    }


def _invoice_fact_value(actionable_packet: dict[str, Any], field_name: str) -> str:
    for fact in actionable_packet.get("invoice_facts") or []:
        if fact.get("field_name") == field_name:
            return str(fact.get("value_text") or "")
    return ""


def _base_invoice_workflow() -> dict[str, Any]:
    return {
        "workflow_id": BASE_INVOICE_WORKFLOW_ID,
        "applies_to_all_clients": True,
        "default_invoice_model": (
            "A client-agnostic invoice workflow may use one operator invoice artifact as the payment-generating "
            "invoice unless a client-specific portal/PO rule overrides it."
        ),
        "client_specific_overlay_required_by_default": False,
        "portal_overlay_is_default": False,
        "payment_generating_artifact_rule": (
            "Default artifact can be payment-generating only when no client-specific portal/PO rule says otherwise."
        ),
        "client_specific_overlays": [HILTON_COUPA_OVERLAY_ID],
        "send_or_submit_authority_added": False,
        "runtime_authority_added": False,
    }


def _hilton_overlay() -> dict[str, Any]:
    return {
        "overlay_id": HILTON_COUPA_OVERLAY_ID,
        "client_scope": "Hilton / Capital Hilton only",
        "applies_to_all_clients": False,
        "generalized_to_all_clients": False,
        "overlay_rule": (
            "For Hilton/Capital Hilton, the Coupa Supplier Portal invoice created from the Hilton PO is the "
            "payment-generating invoice. The Excel/generated invoice is a companion/reference invoice."
        ),
        "portal": "Coupa Supplier Portal",
        "payment_generating_invoice_artifact_type": "coupa_payment_invoice",
        "companion_invoice_artifact_type": "excel_companion_invoice",
        "automation_allowed": False,
        "browser_automation_allowed": False,
        "portal_submit_allowed": False,
        "credential_flow_allowed": False,
    }


def _invoice_artifacts(actionable_packet: dict[str, Any]) -> list[dict[str, Any]]:
    subtotal = (actionable_packet.get("review_calculation") or {}).get("candidate_subtotal") or ""
    return [
        {
            "artifact_type": "coupa_payment_invoice",
            "artifact_role": "payment_generating_invoice",
            "client_specific_overlay": HILTON_COUPA_OVERLAY_ID,
            "current_state": "not_created_by_openclaw_proof_not_captured",
            "manual_operator_action_required": True,
            "proof_required_before_payment_ready": True,
            "payment_ready_source": "Coupa invoice proof/download, not Excel invoice alone",
            "candidate_amount_context": subtotal,
            "openclaw_create_allowed": False,
            "openclaw_submit_allowed": False,
            "browser_automation_allowed": False,
            "credential_access_allowed": False,
        },
        {
            "artifact_type": "excel_companion_invoice",
            "artifact_role": "companion_communication_reference_invoice",
            "client_specific_overlay": HILTON_COUPA_OVERLAY_ID,
            "current_state": "screenshot_confirmed_companion_context_only",
            "invoice_number": "2026-1005",
            "invoice_date": "2026-05-17",
            "total_due_context": _amount("800.00"),
            "payment_generating_for_hilton": False,
            "may_include_richer_context": [
                "older completed gigs",
                "PO budget remaining",
                "multiple PO and balance context when confirmed",
                "stakeholder context for payment coordination and future gig planning",
            ],
            "must_mirror_coupa_invoice_after_coupa_invoice_exists": True,
            "spreadsheet_cells_read": False,
            "spreadsheet_write_allowed": False,
            "email_send_allowed": False,
        },
    ]


def _po_budget_context() -> dict[str, Any]:
    total = Decimal("4000.00")
    invoiced = Decimal("2000.00")
    remaining = total - invoiced
    return {
        "context_status": "screenshot_confirmed_evidence_not_final_accounting_truth",
        "po_number": "DCASH00983536",
        "customer": "Hilton | Smart Spend",
        "status": "Issued - Pending Manual",
        "order_date": "2026-04-23",
        "revision_date": "2026-04-24",
        "total_po_amount": _amount("4000.00"),
        "invoiced_to_date": _amount("2000.00"),
        "apparent_remaining_amount": _amount(f"{remaining:.2f}"),
        "line_item": {
            "label": "Musician",
            "quantity": 2,
            "unit_price": _amount("2000.00"),
        },
        "requester": {
            "role": "po_requester_evidence_from_coupa",
            "display_label": "Sam G.",
            "raw_email_stored": False,
            "email_domain_only": "hilton.com",
        },
        "create_invoice_action_visible": True,
        "multiple_po_support": "future_optional_not_assumed",
        "final_accounting_truth_claimed": False,
        "money_ledger_verification_required_for_paid_status": True,
    }


def _stakeholder_roles() -> list[dict[str, Any]]:
    return [
        {
            "role_id": "annette_payment_coordination",
            "role_summary": "Coupa/payment coordination and checking/rushing payment if needed.",
            "display_label": "Annette",
            "raw_email_stored": False,
            "send_allowed": False,
        },
        {
            "role_id": "chyna_redundant_awareness",
            "role_summary": "Redundant finance awareness.",
            "display_label": "Chyna",
            "raw_email_stored": False,
            "send_allowed": False,
        },
        {
            "role_id": "will_budget_gig_planning_awareness",
            "role_summary": "Budget and additional-gig planning awareness.",
            "display_label": "Will",
            "raw_email_stored": False,
            "send_allowed": False,
        },
        {
            "role_id": "sam_po_requester",
            "role_summary": "PO requester evidence from Coupa screenshot.",
            "display_label": "Sam G.",
            "raw_email_stored": False,
            "email_domain_only": "hilton.com",
            "send_allowed": False,
        },
    ]


def _lifecycle_states() -> dict[str, Any]:
    return {
        "po_identified": {
            "state": "identified_from_operator_screenshot_facts",
            "evidence_required_to_upgrade": "protected Coupa PO screenshot/proof reference",
        },
        "coupa_invoice": {
            "state": "not_created_by_openclaw_proof_not_captured",
            "allowed_next_state": "created_manually_proof_captured",
            "openclaw_may_create_or_submit": False,
        },
        "excel_companion_invoice": {
            "state": "prepared_or_visible_as_companion_context",
            "payment_generating_for_hilton": False,
            "allowed_next_state": "sent_manually_and_archived_proof_captured",
            "openclaw_may_write_or_send": False,
        },
        "payment": {
            "state": "payment_pending_not_money_ledger_verified",
            "paid_status_requires": "money_ledger_payment_confirmation",
            "payment_marked_paid": False,
        },
    }


def _protected_evidence_slots() -> list[dict[str, Any]]:
    return [
        {
            "slot_id": "coupa_invoice_pdf_or_download",
            "artifact_type": "coupa_payment_invoice",
            "required_for": "payment_ready_status",
            "storage_policy": "protected_local_or_operator_approved_artifact_reference_only",
            "raw_blob_stored_in_read_model": False,
        },
        {
            "slot_id": "excel_companion_invoice_file_or_pdf",
            "artifact_type": "excel_companion_invoice",
            "required_for": "companion_reference_archive",
            "storage_policy": "protected_local_file_reference_only",
            "raw_blob_stored_in_read_model": False,
        },
        {
            "slot_id": "check_image_or_deposit_proof",
            "artifact_type": "payment_evidence",
            "required_for": "payment_reconciliation_review",
            "storage_policy": "protected_local_only_no_normal_repo_storage",
            "raw_blob_stored_in_read_model": False,
        },
        {
            "slot_id": "money_ledger_payment_confirmation",
            "artifact_type": "money_ledger_receipt",
            "required_for": "paid_verified_status",
            "storage_policy": "money_ledger_reference_only_no_bank_details",
            "raw_blob_stored_in_read_model": False,
        },
    ]


def _manual_confirmation_alignment() -> dict[str, Any]:
    return {
        "receipt_model": "capital_hilton_manual_confirmation_receipt_v0",
        "confirmation_fields_remain_supported": True,
        "field_alignment": {
            "po_coupa_requirement_confirmed": "PO identified and Coupa requirement understood; not portal submission.",
            "recipient_confirmed": "Companion communication recipient posture only; not email send authority.",
            "coupa_invoice_created_manually": "Manual Coupa payment invoice creation proof slot; not OpenClaw creation.",
            "spreadsheet_invoice_number_checked": "Excel companion invoice number/workbook review; not spreadsheet write authority.",
            "include_2026_05_22": "Scope decision for companion/reference context and future invoice planning.",
            "include_older_gigs": "Scope decision for companion/reference context and historical context.",
        },
        "confirmations_do_not_create_external_action_authority": True,
    }


def _legacy_one_invoice_compatibility(actionable_packet: dict[str, Any]) -> dict[str, Any]:
    invoice_count = _invoice_fact_value(actionable_packet, "invoice_count_preference")
    return {
        "old_one_invoice_packet_fact_preserved": bool(invoice_count),
        "old_one_invoice_packet_fact_value": invoice_count,
        "compatibility_interpretation": (
            "The prior one-invoice posture remains compatible as the review/service-scope posture. "
            "For Hilton, payment still requires the Coupa payment invoice plus an Excel companion/reference invoice overlay."
        ),
        "does_not_make_excel_payment_generating_for_hilton": True,
    }


def _payment_readiness() -> dict[str, Any]:
    return {
        "payment_ready": False,
        "payment_ready_requires": [
            "Coupa payment invoice created manually",
            "Coupa invoice PDF/download/proof captured in protected evidence slot",
            "PO and line-item context confirmed",
        ],
        "excel_companion_invoice_alone_is_payment_ready": False,
        "paid_verified": False,
        "paid_verified_requires": "money_ledger_payment_confirmation",
    }


def build_capital_hilton_two_invoice_workflow(
    *,
    actionable_packet_path: str | Path = DEFAULT_ACTIONABLE_PACKET_PATH,
    confirmation_receipt_path: str | Path = DEFAULT_CONFIRMATION_RECEIPT_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    actionable_packet = _read_json_if_present(actionable_packet_path)
    confirmation_receipt = _read_json_if_present(confirmation_receipt_path)
    service_dates = (actionable_packet.get("review_calculation") or {}).get("known_completed_service_dates") or []
    rate = (actionable_packet.get("review_calculation") or {}).get("rate_or_amount_per_gig") or ""
    subtotal = (actionable_packet.get("review_calculation") or {}).get("candidate_subtotal") or ""
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "target_workflow": "capital_hilton_invoice",
        "workflow_domain": "finance_ap_invoice",
        "contract_kind": "client_specific_invoice_overlay_contract",
        "base_invoice_workflow": _base_invoice_workflow(),
        "client_specific_invoice_overlay": _hilton_overlay(),
        "invoice_artifacts": _invoice_artifacts(actionable_packet),
        "lifecycle_states": _lifecycle_states(),
        "po_budget_context": _po_budget_context(),
        "stakeholder_roles": _stakeholder_roles(),
        "protected_evidence_slots": _protected_evidence_slots(),
        "manual_confirmation_alignment": _manual_confirmation_alignment(),
        "legacy_one_invoice_packet_compatibility": _legacy_one_invoice_compatibility(actionable_packet),
        "current_review_packet_context": {
            "source_packet_path": _display_path(actionable_packet_path),
            "source_packet_present": bool(actionable_packet),
            "service_dates": service_dates,
            "rate_or_amount_per_gig": rate,
            "candidate_subtotal": subtotal,
            "review_only": True,
            "ready_for_submission": False,
        },
        "current_confirmation_receipt_context": {
            "source_receipt_path": _display_path(confirmation_receipt_path),
            "source_receipt_present": bool(confirmation_receipt),
            "recorded_confirmation_count": confirmation_receipt.get("recorded_confirmation_count", 0),
            "pending_confirmation_count": confirmation_receipt.get("pending_confirmation_count", 0),
            "real_confirmations_recorded": bool(confirmation_receipt.get("real_confirmations_recorded", False)),
        },
        "payment_readiness": _payment_readiness(),
        "status_summary": {
            "base_invoice_workflow_preserved": True,
            "hilton_coupa_overlay_modeled": True,
            "coupa_payment_invoice_modeled": True,
            "excel_companion_invoice_modeled": True,
            "po_budget_context_modeled": True,
            "protected_evidence_slots_modeled": True,
            "hilton_two_invoice_flow_generalized_to_all_clients": False,
            "raw_pii_or_secret_stored": False,
        },
        "next_recommended_lane": "Capital Hilton Coupa Payment Invoice Proof Capture v0",
        "boundaries": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def format_capital_hilton_two_invoice_workflow(payload: dict[str, Any]) -> str:
    po = payload["po_budget_context"]
    artifacts = {item["artifact_type"]: item for item in payload["invoice_artifacts"]}
    lines = [
        "# Capital Hilton Two-Invoice Workflow",
        "",
        "Status:",
        "- Base invoice workflow preserved: `true`.",
        "- Hilton Coupa overlay modeled: `true`.",
        "- Coupa payment invoice modeled: `true`.",
        "- Excel companion invoice modeled: `true`.",
        "- Ready for submission: `false`.",
        "- Email sent: `false`.",
        "- Coupa submitted: `false`.",
        "- Spreadsheet write triggered: `false`.",
        "",
        "## Base vs Hilton Overlay",
        f"- Base workflow: {payload['base_invoice_workflow']['default_invoice_model']}",
        f"- Hilton overlay: {payload['client_specific_invoice_overlay']['overlay_rule']}",
        "",
        "## Invoice Artifacts",
        f"- Coupa payment invoice: `{artifacts['coupa_payment_invoice']['current_state']}`; payment-generating for Hilton.",
        f"- Excel companion invoice: `{artifacts['excel_companion_invoice']['current_state']}`; not payment-generating for Hilton.",
        f"- Excel invoice number evidence: `{artifacts['excel_companion_invoice']['invoice_number']}`; total due context: `{artifacts['excel_companion_invoice']['total_due_context']['amount_text']}`.",
        "",
        "## PO Budget Context",
        f"- PO: `{po['po_number']}`; status: `{po['status']}`.",
        f"- Total: `{po['total_po_amount']['amount_text']}`; invoiced-to-date: `{po['invoiced_to_date']['amount_text']}`; apparent remaining: `{po['apparent_remaining_amount']['amount_text']}`.",
        "- Budget context is screenshot evidence, not final accounting truth.",
        "",
        "## Protected Evidence Slots",
    ]
    for slot in payload["protected_evidence_slots"]:
        lines.append(f"- `{slot['slot_id']}`: {slot['storage_policy']}")
    lines.extend(
        [
            "",
            "## Boundary",
            "- No Coupa submit, invoice creation, email send, spreadsheet write, browser automation, secret storage, or runtime authority.",
            "- Payment-ready requires Coupa invoice proof; paid requires money-ledger confirmation.",
            "",
            f"Next safe lane: {payload['next_recommended_lane']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_capital_hilton_two_invoice_workflow(
    *,
    actionable_packet_path: str | Path = DEFAULT_ACTIONABLE_PACKET_PATH,
    confirmation_receipt_path: str | Path = DEFAULT_CONFIRMATION_RECEIPT_PATH,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> TwoInvoiceWorkflowExportResult:
    payload = build_capital_hilton_two_invoice_workflow(
        actionable_packet_path=actionable_packet_path,
        confirmation_receipt_path=confirmation_receipt_path,
        generated_at=generated_at,
    )
    root = _rooted(export_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_capital_hilton_two_invoice_workflow(payload), encoding="utf-8")
    status = payload["status_summary"]
    return TwoInvoiceWorkflowExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        base_invoice_workflow_preserved=status["base_invoice_workflow_preserved"],
        hilton_coupa_overlay_modeled=status["hilton_coupa_overlay_modeled"],
        coupa_payment_invoice_modeled=status["coupa_payment_invoice_modeled"],
        excel_companion_invoice_modeled=status["excel_companion_invoice_modeled"],
        po_budget_context_modeled=status["po_budget_context_modeled"],
        protected_evidence_slots_modeled=status["protected_evidence_slots_modeled"],
        runtime_authority_added=False,
        send_or_submit_authority_added=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Capital Hilton two-invoice workflow contract.")
    parser.add_argument("--actionable-packet-json", default=str(DEFAULT_ACTIONABLE_PACKET_PATH))
    parser.add_argument("--confirmation-receipt-json", default=str(DEFAULT_CONFIRMATION_RECEIPT_PATH))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_capital_hilton_two_invoice_workflow(
        actionable_packet_path=args.actionable_packet_json,
        confirmation_receipt_path=args.confirmation_receipt_json,
        export_root=args.export_root,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        payload = build_capital_hilton_two_invoice_workflow(
            actionable_packet_path=args.actionable_packet_json,
            confirmation_receipt_path=args.confirmation_receipt_json,
        )
        print(format_capital_hilton_two_invoice_workflow(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
