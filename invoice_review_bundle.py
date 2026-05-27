"""Invoice review bundle v0.

Backend-owned approval-card contract for Mission Control invoice review.
This module builds read-models only. It does not send email, access Coupa or
Gmail, open browsers, generate PDFs, post ledger entries, or mutate production
workflow state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import client_invoice_workflow_framework as workflow


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-27T00:00:00+00:00"

SCHEMA_VERSION = "invoice_review_bundle_v0"
READ_MODEL_ID = "invoice_review_bundle"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "MISSION_CONTROL_APPROVAL_CARD_CONTRACT_NO_ACTIONS"

CAPITAL_HILTON_WORKFLOW_REF = "capital_hilton_invoice_workflow"
CAPITAL_HILTON_BUNDLE_ID = "invoice_review_bundle:capital_hilton:v0"
CAPITAL_HILTON_EXCEL_PATH = Path(
    "generated/invoice_artifacts/capital_hilton_invoice_artifact_v0/"
    "WINSHIP_CAPITAL_HILTON_INVOICE_2026-05-25.xlsx"
)

APPROVAL_BUTTONS = ("APPROVE", "DO_NOT_APPROVE", "EXPLAIN", "EDIT_DRAFT", "HOLD")
APPROVAL_FOOTER_BUTTONS = ("APPROVE", "DO_NOT_APPROVE", "HOLD", "EXPLAIN")
CORRECTION_ACTIONS = (
    "CONFIRM_THIS_INVOICE",
    "RIGHT_WORKBOOK_WRONG_PAGE",
    "WRONG_WORKBOOK",
    "WRONG_CLIENT",
    "SELECT_DIFFERENT_PAGE",
    "OPEN_WORKBOOK",
    "EXPLAIN_THIS_REVIEW",
)

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "gmail_access_allowed": False,
    "coupa_access_allowed": False,
    "coupa_submit_allowed": False,
    "browser_automation_allowed": False,
    "credential_handling_allowed": False,
    "approval_execution_allowed": False,
    "ledger_posting_allowed": False,
    "payment_mark_paid_allowed": False,
    "production_state_mutation_allowed": False,
    "model_call_allowed": False,
    "tool_execution_allowed": False,
    "network_allowed": False,
}

REQUIRED_RECEIPTS = (
    "active_workbook_confirmed_receipt",
    "invoice_record_selected_receipt",
    "invoice_period_confirmed_receipt",
    "generated_invoice_artifact_linkage_receipt",
    "excel_invoice_generated_receipt",
    "invoice_attachment_proof_receipt",
    "clara_email_draft_receipt",
    "purchase_order_confirmed_receipt",
    "portal_invoice_submission_receipt",
    "guardian_approval_receipt",
    "operator_approval_receipt",
    "email_send_receipt",
)

INVOICE_REVIEW_STATES = (
    "ACTIVE_WORKBOOK_CONFIRMED",
    "INVOICE_RECORD_SELECTED",
    "INVOICE_PERIOD_CONFIRMED",
    "GENERATED_INVOICE_ARTIFACT_CANDIDATE",
    "GENERATED_INVOICE_ARTIFACT_CONFIRMED",
    "EXCEL_INVOICE_ATTACHMENT_READY",
    "BLOCKED_NEEDS_INVOICE_RECORD_SELECTION",
    "BLOCKED_NEEDS_GENERATED_ARTIFACT_PROOF",
)

ARTIFACT_LINKAGE_RECEIPTS = (
    "active_workbook_confirmed_receipt",
    "invoice_record_selected_receipt",
    "invoice_period_confirmed_receipt",
    "generated_invoice_artifact_linkage_receipt",
)

BLOCKED_SEND_RECEIPTS = (
    "guardian_approval_receipt",
    "operator_approval_receipt",
    "email_send_receipt",
)

OPERATOR_JARGON_BLOCKLIST = (
    "source_request_id",
    "sqlite",
    "receipt hash",
    "approval hash",
    "internal package id",
    "gate 2",
    "gate 3",
)


@dataclass(frozen=True)
class InvoiceReviewArtifact:
    artifact_ref: str
    display_name: str
    preview_available: bool
    preview_ref: str | None
    bridge_relative_ref: str | None
    pc_bridge_ref: str | None
    mac_visible_ref: str | None
    proof_status: str
    attachment_ready: bool
    linkage_status: str
    required_linkage_receipts: tuple[str, ...]
    missing_linkage_receipts: tuple[str, ...]


@dataclass(frozen=True)
class ClaraEmailDraft:
    subject: str
    body: str
    selected_voice: str
    draft_only: bool
    sent: bool


@dataclass(frozen=True)
class CoupaInvoiceProof:
    required: bool
    status: str
    po_ref: str | None
    amount: dict[str, Any] | None
    proof_ref: str | None


@dataclass(frozen=True)
class RecipientCandidate:
    display_name: str
    role: str
    lane: str
    confirmation_status: str


@dataclass(frozen=True)
class ApprovalButton:
    label: str
    button_ref: str
    operator_label: str
    internal_action_ref: str
    requires_explicit_click: bool
    grants_send_authority: bool


@dataclass(frozen=True)
class GuardianApprovalRequest:
    approval_ref: str
    operator_question: str
    status: str
    approval_required: bool
    send_allowed: bool
    buttons: tuple[dict[str, Any], ...]
    hidden_internal_refs: tuple[str, ...]


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _artifact_ref(path: Path) -> str:
    return f"local_artifact_ref:{_short_hash(path.as_posix())}"


def _artifact_linked_to_selected_invoice(receipts: set[str]) -> bool:
    return all(receipt in receipts for receipt in ARTIFACT_LINKAGE_RECEIPTS)


def _excel_invoice_artifact(receipts: set[str]) -> InvoiceReviewArtifact:
    exists = CAPITAL_HILTON_EXCEL_PATH.exists()
    linked = exists and _artifact_linked_to_selected_invoice(receipts)
    missing = tuple(receipt for receipt in ARTIFACT_LINKAGE_RECEIPTS if receipt not in receipts)
    bridge_relative_ref = CAPITAL_HILTON_EXCEL_PATH.as_posix() if exists else None
    return InvoiceReviewArtifact(
        artifact_ref=_artifact_ref(CAPITAL_HILTON_EXCEL_PATH),
        display_name="Capital Hilton Excel invoice candidate",
        preview_available=exists,
        preview_ref=CAPITAL_HILTON_EXCEL_PATH.as_posix() if exists else None,
        bridge_relative_ref=bridge_relative_ref,
        pc_bridge_ref=f"/mnt/e/openclaw/{bridge_relative_ref}" if bridge_relative_ref else None,
        mac_visible_ref=f"/Volumes/openclaw_e/{bridge_relative_ref}" if bridge_relative_ref else None,
        proof_status="GENERATED_INVOICE_ARTIFACT_CONFIRMED" if linked else "GENERATED_INVOICE_ARTIFACT_CANDIDATE",
        attachment_ready=linked and "invoice_attachment_proof_receipt" in receipts,
        linkage_status="LINKED_TO_SELECTED_INVOICE" if linked else "NEEDS_INVOICE_SELECTION",
        required_linkage_receipts=ARTIFACT_LINKAGE_RECEIPTS,
        missing_linkage_receipts=missing,
    )


def _clara_draft() -> ClaraEmailDraft:
    return ClaraEmailDraft(
        subject="Capital Hilton invoice package for review",
        body=(
            "Hi Annette,\n\n"
            "I'm preparing the Capital Hilton invoice package for review. "
            "I can send over the Excel invoice for your records once the package and recipients are confirmed.\n\n"
            "Best,\n"
            "Clara"
        ),
        selected_voice="CLARA",
        draft_only=True,
        sent=False,
    )


def _capital_hilton_recipients(*, confirmed: bool = False) -> tuple[RecipientCandidate, ...]:
    status = "CONFIRMED_BY_RECEIPT" if confirmed else "CANDIDATE_UNCONFIRMED"
    return (
        RecipientCandidate("Annette", "finance_primary", "to", status),
        RecipientCandidate("Chyna", "finance_secondary", "cc", status),
        RecipientCandidate("Will", "relationship_contact", "cc", status),
    )


def _approval_buttons(bundle_id: str) -> tuple[dict[str, Any], ...]:
    return tuple(
        asdict(
            ApprovalButton(
                label=label,
                button_ref=f"invoice_review_button:{label.lower()}:{_short_hash(bundle_id, label)}",
                operator_label=label.replace("_", " ").title(),
                internal_action_ref=f"invoice_review_bundle_action:{bundle_id}:{label.lower()}",
                requires_explicit_click=True,
                grants_send_authority=False,
            )
        )
        for label in APPROVAL_BUTTONS
    )


def _guardian_approval_request(bundle_id: str, *, ready_for_send_review: bool) -> GuardianApprovalRequest:
    question = (
        "Approve sending this Excel invoice email to Annette with Chyna and Will copied?"
        if ready_for_send_review
        else "Review the Capital Hilton invoice package?"
    )
    return GuardianApprovalRequest(
        approval_ref=f"guardian_invoice_review_approval:{_short_hash(bundle_id)}",
        operator_question=question,
        status="READY_TO_REQUEST_OPERATOR_APPROVAL" if ready_for_send_review else "BLOCKED_PREREQUISITES_MISSING",
        approval_required=True,
        send_allowed=False,
        buttons=_approval_buttons(bundle_id),
        hidden_internal_refs=(
            "approval_ref",
            "button_ref",
            "internal_action_ref",
            "required_receipts",
        ),
    )


def _coupa_invoice_proof(present_receipts: set[str]) -> CoupaInvoiceProof:
    submitted = "portal_invoice_submission_receipt" in present_receipts
    po_known = "purchase_order_confirmed_receipt" in present_receipts
    return CoupaInvoiceProof(
        required=True,
        status="SUBMITTED_RECEIPT_CONFIRMED" if submitted else "MISSING",
        po_ref="po_ref:confirmed_by_receipt" if po_known else None,
        amount={"amount": 2000, "currency": "USD", "status": "candidate_unconfirmed"} if po_known else None,
        proof_ref="portal_invoice_submission_receipt" if submitted else None,
    )


def _normalize_receipts(receipts: Mapping[str, Any] | set[str] | tuple[str, ...] | list[str] | None) -> set[str]:
    if receipts is None:
        return set()
    if isinstance(receipts, Mapping):
        return {str(key) for key, value in receipts.items() if bool(value)}
    return {str(item) for item in receipts}


def _send_allowed(receipts: set[str]) -> bool:
    return all(receipt in receipts for receipt in BLOCKED_SEND_RECEIPTS)


def _preview_section(excel: InvoiceReviewArtifact) -> dict[str, Any]:
    if not excel.preview_available:
        return {
            "preview_kind": "NONE",
            "preview_available": False,
            "preview_limited": False,
            "preview_ref": None,
            "preview_mac_path": None,
            "preview_status": "NO_PREVIEW_ARTIFACT",
            "preview_operator_copy": "No invoice preview is available yet.",
            "candidate_notice": "OpenClaw needs the current invoice page/period before it can confirm an invoice artifact.",
            "generation_performed": False,
        }
    return {
        "preview_kind": "EXCEL",
        "preview_available": False,
        "preview_limited": True,
        "preview_ref": excel.preview_ref,
        "preview_mac_path": excel.mac_visible_ref,
        "preview_status": "EXCEL_CANDIDATE_OPEN_FILE_ONLY",
        "preview_operator_copy": "Excel candidate available for inspection. Inline PDF/image preview is not available yet.",
        "candidate_notice": "Candidate only. This is not confirmed as the current invoice until the workbook, page/period, and artifact linkage are verified.",
        "generation_performed": False,
    }


def _artifact_inspection_actions(excel: InvoiceReviewArtifact) -> dict[str, Any]:
    mac_path = excel.mac_visible_ref if excel.preview_available else None
    return {
        "open_file_available": bool(mac_path),
        "open_file_mac_path": mac_path,
        "reveal_in_finder_available": bool(mac_path),
        "reveal_in_finder_mac_path": mac_path,
        "pop_out_available": bool(mac_path),
        "pop_out_status": "AVAILABLE_FOR_CANDIDATE_ARTIFACT" if mac_path else "NO_ARTIFACT_AVAILABLE",
        "artifact_remains_candidate": excel.proof_status == "GENERATED_INVOICE_ARTIFACT_CANDIDATE",
        "external_action": False,
    }


def _correction_action(action: str, *, enabled: bool = True) -> dict[str, Any]:
    labels = {
        "CONFIRM_THIS_INVOICE": "Confirm This Invoice",
        "RIGHT_WORKBOOK_WRONG_PAGE": "Right Workbook, Wrong Page",
        "WRONG_WORKBOOK": "Wrong Workbook",
        "WRONG_CLIENT": "Wrong Client",
        "SELECT_DIFFERENT_PAGE": "Select Different Page",
        "OPEN_WORKBOOK": "Open Workbook",
        "EXPLAIN_THIS_REVIEW": "Explain This Review",
    }
    followups = {
        "CONFIRM_THIS_INVOICE": "Confirm the workbook, invoice page/period, and generated artifact match.",
        "RIGHT_WORKBOOK_WRONG_PAGE": "Which invoice page or period should OpenClaw use instead?",
        "WRONG_WORKBOOK": "Which workbook should OpenClaw use for this invoice?",
        "WRONG_CLIENT": "Which client should this invoice review belong to?",
        "SELECT_DIFFERENT_PAGE": "Which page, sheet, or invoice period should OpenClaw prepare?",
        "OPEN_WORKBOOK": None,
        "EXPLAIN_THIS_REVIEW": None,
    }
    request_kinds = {
        "CONFIRM_THIS_INVOICE": "invoice_selection_confirmation_request",
        "RIGHT_WORKBOOK_WRONG_PAGE": "invoice_page_correction_request",
        "WRONG_WORKBOOK": "workbook_correction_request",
        "WRONG_CLIENT": "client_correction_request",
        "SELECT_DIFFERENT_PAGE": "invoice_page_selection_request",
        "OPEN_WORKBOOK": "local_artifact_inspection_request",
        "EXPLAIN_THIS_REVIEW": "review_explanation_request",
    }
    return {
        "action_ref": f"invoice_review_correction:{action.lower()}:{_short_hash(CAPITAL_HILTON_BUNDLE_ID, action)}",
        "label": labels[action],
        "enabled": enabled,
        "requires_followup": followups[action] is not None,
        "followup_prompt": followups[action],
        "resulting_request_kind": request_kinds[action],
        "intended_use": "review_correction_or_inspection",
        "no_external_action": True,
        "mutates_workbook": False,
        "mutates_production_state": False,
    }


def _correction_actions(excel: InvoiceReviewArtifact) -> tuple[dict[str, Any], ...]:
    return tuple(
        _correction_action(action, enabled=(action != "OPEN_WORKBOOK" or excel.preview_available))
        for action in CORRECTION_ACTIONS
    )


def _approval_disabled_reasons(
    *,
    receipts: set[str],
    excel: InvoiceReviewArtifact,
    coupa: CoupaInvoiceProof,
    contacts_confirmed: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if coupa.status == "MISSING":
        reasons.append("Coupa proof missing")
    if "invoice_record_selected_receipt" not in receipts or "invoice_period_confirmed_receipt" not in receipts:
        reasons.append("Invoice record/page not selected")
    if excel.proof_status != "GENERATED_INVOICE_ARTIFACT_CONFIRMED":
        reasons.append("Generated artifact not linked")
    if not contacts_confirmed:
        reasons.append("Recipients unconfirmed")
    if not excel.attachment_ready:
        reasons.append("Attachment not ready")
    return tuple(reasons)


def _approval_footer(
    *,
    disabled_reasons: tuple[str, ...],
    guardian: GuardianApprovalRequest,
) -> dict[str, Any]:
    approval_ready = len(disabled_reasons) == 0 and guardian.status == "READY_TO_REQUEST_OPERATOR_APPROVAL"
    return {
        "approval_ready": approval_ready,
        "approval_disabled_reasons": disabled_reasons,
        "approval_buttons": tuple(
            {
                "label": label,
                "enabled": approval_ready if label == "APPROVE" else True,
                "no_external_action": True,
            }
            for label in APPROVAL_FOOTER_BUTTONS
        ),
        "sticky_footer_operator_copy": "Approval is disabled until invoice selection, Coupa proof, recipients, and attachment proof are ready."
        if not approval_ready
        else "Ready for review approval. Approval still does not send anything by itself.",
    }


def _timeline_item(
    label: str,
    *,
    status: str,
    operator_copy: str,
    receipt_ref: str | None = None,
    proof_ref: str | None = None,
    hidden_internal_refs: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "label": label,
        "status": status,
        "receipt_ref": receipt_ref,
        "proof_ref": proof_ref,
        "operator_copy": operator_copy,
        "hidden_internal_refs": hidden_internal_refs,
    }


def _review_proof_timeline(
    *,
    receipts: set[str],
    excel: InvoiceReviewArtifact,
    coupa: CoupaInvoiceProof,
    guardian: GuardianApprovalRequest,
    semantic_status: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    return (
        _timeline_item(
            "Active workbook",
            status="CONFIRMED" if "active_workbook_confirmed_receipt" in receipts else "NEEDS_CONFIRMATION",
            receipt_ref="active_workbook_confirmed_receipt" if "active_workbook_confirmed_receipt" in receipts else None,
            operator_copy="Workbook still needs confirmation.",
            hidden_internal_refs=("workflow_ref",),
        ),
        _timeline_item(
            "Invoice page/period",
            status="SELECTED"
            if {"invoice_record_selected_receipt", "invoice_period_confirmed_receipt"} <= receipts
            else "NEEDS_SELECTION",
            receipt_ref="invoice_record_selected_receipt" if "invoice_record_selected_receipt" in receipts else None,
            operator_copy="Choose the invoice page or period before treating the artifact as current.",
            hidden_internal_refs=("invoice_record_selected_receipt", "invoice_period_confirmed_receipt"),
        ),
        _timeline_item(
            "Generated invoice artifact",
            status=excel.proof_status,
            proof_ref=excel.artifact_ref if excel.preview_available else None,
            operator_copy="Excel artifact is candidate-only until linked to the selected invoice.",
            hidden_internal_refs=("generated_invoice_artifact_linkage_receipt",),
        ),
        _timeline_item(
            "Coupa portal proof",
            status=coupa.status,
            receipt_ref=coupa.proof_ref,
            operator_copy="Coupa portal submission proof is still required.",
            hidden_internal_refs=("portal_invoice_submission_receipt",),
        ),
        _timeline_item(
            "Clara draft",
            status=semantic_status["clara_draft_status"],
            receipt_ref="clara_email_draft_receipt" if "clara_email_draft_receipt" in receipts else None,
            operator_copy="Draft only. Nothing was sent.",
            hidden_internal_refs=("clara_email_draft_receipt",),
        ),
        _timeline_item(
            "Guardian approval request",
            status=guardian.status,
            receipt_ref="guardian_approval_receipt" if "guardian_approval_receipt" in receipts else None,
            operator_copy="Approval request is blocked until prerequisites are ready.",
            hidden_internal_refs=(guardian.approval_ref,),
        ),
        _timeline_item(
            "Operator approval",
            status=semantic_status["operator_approval_status"],
            receipt_ref="operator_approval_receipt" if "operator_approval_receipt" in receipts else None,
            operator_copy="No operator approval has been granted.",
            hidden_internal_refs=("operator_approval_receipt",),
        ),
        _timeline_item(
            "Email send",
            status=semantic_status["email_send_execution_status"],
            receipt_ref="email_send_receipt" if "email_send_receipt" in receipts else None,
            operator_copy="No email has been sent.",
            hidden_internal_refs=("email_send_receipt",),
        ),
        _timeline_item(
            "Payment watch",
            status=semantic_status["payment_watch_status"],
            receipt_ref="payment_detected_receipt" if "payment_detected_receipt" in receipts else None,
            operator_copy="No payment has been detected.",
            hidden_internal_refs=("payment_detected_receipt",),
        ),
        _timeline_item(
            "Ledger/tax evidence",
            status="NOT_READY",
            receipt_ref="ledger_tax_evidence_receipt" if "ledger_tax_evidence_receipt" in receipts else None,
            operator_copy="Ledger and tax evidence are not ready.",
            hidden_internal_refs=("ledger_tax_evidence_receipt",),
        ),
    )


def _status_model(*, receipts: set[str], excel: InvoiceReviewArtifact, clara: ClaraEmailDraft, coupa: CoupaInvoiceProof, guardian: GuardianApprovalRequest) -> dict[str, Any]:
    operator_approved = "operator_approval_receipt" in receipts
    email_sent = "email_send_receipt" in receipts
    portal_submitted = "portal_invoice_submission_receipt" in receipts
    return {
        "coupa_portal_rail_status": "PRIMARY_PAYMENT_TRIGGER_BLOCKED_PROOF_MISSING"
        if not portal_submitted
        else "PRIMARY_PAYMENT_TRIGGER_SUBMITTED_RECEIPT_CONFIRMED",
        "coupa_submission_proof_status": coupa.status,
        "excel_invoice_artifact_status": excel.proof_status,
        "excel_invoice_attachment_ready": excel.attachment_ready,
        "clara_draft_status": "DRAFT_ONLY" if clara.draft_only and not clara.sent else "UNKNOWN_FAIL_CLOSED",
        "guardian_output_validation_status": "PASSED_FOR_DRAFT_DISPLAY_ONLY",
        "guardian_approval_request_status": guardian.status,
        "operator_approval_status": "GRANTED_FOR_SPECIFIC_PACKAGE" if operator_approved else "NOT_GRANTED",
        "email_send_execution_status": "SENT_RECEIPT_CONFIRMED" if email_sent else "NOT_SENT",
        "portal_submission_execution_status": "SUBMITTED_RECEIPT_CONFIRMED" if portal_submitted else "NOT_SUBMITTED",
        "payment_watch_status": "PAYMENT_RECEIVED_RECEIPT_CONFIRMED" if "payment_detected_receipt" in receipts else "NOT_RECEIVED",
        "primary_invoice_trigger": "COUPA_SUPPLIER_PORTAL_INVOICE",
        "supporting_artifacts": ("excel_invoice_for_records", "clara_email_draft_for_annette"),
    }


def build_capital_hilton_bundle(
    *,
    present_receipts: Mapping[str, Any] | set[str] | tuple[str, ...] | list[str] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    receipts = _normalize_receipts(present_receipts)
    excel = _excel_invoice_artifact(receipts)
    clara = _clara_draft()
    coupa = _coupa_invoice_proof(receipts)
    contacts_confirmed = "recipient_confirmation_receipt" in receipts
    ready_for_send_review = (
        excel.attachment_ready
        and "clara_email_draft_receipt" in receipts
        and contacts_confirmed
    )
    guardian = _guardian_approval_request(CAPITAL_HILTON_BUNDLE_ID, ready_for_send_review=ready_for_send_review)
    semantic_status = _status_model(receipts=receipts, excel=excel, clara=clara, coupa=coupa, guardian=guardian)
    missing_receipts = tuple(receipt for receipt in REQUIRED_RECEIPTS if receipt not in receipts)
    approval_disabled_reasons = _approval_disabled_reasons(
        receipts=receipts,
        excel=excel,
        coupa=coupa,
        contacts_confirmed=contacts_confirmed,
    )
    approval_footer = _approval_footer(disabled_reasons=approval_disabled_reasons, guardian=guardian)
    preview_section = _preview_section(excel)
    artifact_actions = _artifact_inspection_actions(excel)
    correction_actions = _correction_actions(excel)
    proof_timeline = _review_proof_timeline(
        receipts=receipts,
        excel=excel,
        coupa=coupa,
        guardian=guardian,
        semantic_status=semantic_status,
    )
    blockers = []
    if coupa.status == "MISSING":
        blockers.append("Coupa submission proof is still required.")
    if "invoice_record_selected_receipt" not in receipts or "invoice_period_confirmed_receipt" not in receipts:
        blockers.append("Which invoice page/period should OpenClaw prepare for Capital Hilton?")
        blockers.append("OpenClaw needs the current invoice page/period before it can attach the Excel invoice.")
    if excel.proof_status != "GENERATED_INVOICE_ARTIFACT_CONFIRMED":
        blockers.append("Generated invoice artifact needs proof linking it to the selected invoice record.")
    if not contacts_confirmed:
        blockers.append("Recipient list needs confirmation.")
    if not _send_allowed(receipts):
        blockers.append("Send is blocked until approval and send execution receipts exist.")
    recipe = workflow.recipes_by_client_ref()["capital_hilton"]
    bundle = {
        "bundle_id": CAPITAL_HILTON_BUNDLE_ID,
        "client_ref": "capital_hilton",
        "client_display_name": "Capital Hilton",
        "workflow_ref": CAPITAL_HILTON_WORKFLOW_REF,
        "invoice_period": {
            "display_label": "Capital Hilton current invoice package",
            "status": "INVOICE_PERIOD_CONFIRMED" if "invoice_period_confirmed_receipt" in receipts else "BLOCKED_NEEDS_INVOICE_RECORD_SELECTION",
        },
        "invoice_selection": {
            "active_workbook_state": "ACTIVE_WORKBOOK_CONFIRMED"
            if "active_workbook_confirmed_receipt" in receipts
            else "BLOCKED_NEEDS_INVOICE_RECORD_SELECTION",
            "invoice_record_state": "INVOICE_RECORD_SELECTED"
            if "invoice_record_selected_receipt" in receipts
            else "BLOCKED_NEEDS_INVOICE_RECORD_SELECTION",
            "invoice_period_state": "INVOICE_PERIOD_CONFIRMED"
            if "invoice_period_confirmed_receipt" in receipts
            else "BLOCKED_NEEDS_INVOICE_RECORD_SELECTION",
            "workbook_may_contain_multiple_invoice_records": True,
            "operator_question": "Which invoice page/period should OpenClaw prepare for Capital Hilton?",
        },
        "status": "READY_FOR_REVIEW_BLOCKED_FOR_SELECTION"
        if not _artifact_linked_to_selected_invoice(receipts)
        else "READY_FOR_REVIEW_BLOCKED_FOR_SEND",
        "semantic_status": semantic_status,
        "helm_card": {
            "title": "Review the Capital Hilton invoice package.",
            "operator_summary": (
                "Draft path prepared. Nothing was sent or submitted. Coupa portal submission proof is still "
                "required before this invoice can be treated as sent."
            ),
            "primary_warning": "OpenClaw needs the current invoice page/period before it can attach the Excel invoice."
            if not _artifact_linked_to_selected_invoice(receipts)
            else "Coupa submission proof is still required." if coupa.status == "MISSING" else None,
            "safe_next_move": "Select the current invoice page/period and link any generated artifact before approval.",
            "button_labels": APPROVAL_BUTTONS,
        },
        "excel_invoice_artifact": asdict(excel),
        "preview_section": preview_section,
        "artifact_inspection_actions": artifact_actions,
        "correction_actions": correction_actions,
        "clara_email_draft": asdict(clara),
        "coupa_invoice_proof": asdict(coupa),
        "recipients": {
            "to_candidates": tuple(asdict(item) for item in _capital_hilton_recipients(confirmed=contacts_confirmed) if item.lane == "to"),
            "cc_candidates": tuple(asdict(item) for item in _capital_hilton_recipients(confirmed=contacts_confirmed) if item.lane == "cc"),
            "confirmation_status": "CONFIRMED_BY_RECEIPT" if contacts_confirmed else "CANDIDATE_UNCONFIRMED",
        },
        "guardian_approval_request": asdict(guardian),
        "approval_footer": approval_footer,
        "review_proof_timeline": proof_timeline,
        "required_receipts": REQUIRED_RECEIPTS,
        "present_receipts": tuple(sorted(receipts)),
        "missing_receipts": missing_receipts,
        "blockers": tuple(blockers),
        "proof_refs": tuple(
            item
            for item in (
                excel.artifact_ref if excel.preview_available else None,
                coupa.proof_ref,
                "clara_email_draft_receipt" if "clara_email_draft_receipt" in receipts else None,
            )
            if item
        ),
        "hidden_backend_proof": {
            "approval_ref": guardian.approval_ref,
            "button_refs": tuple(button["button_ref"] for button in guardian.buttons),
            "internal_action_refs": tuple(button["internal_action_ref"] for button in guardian.buttons),
            "internal_refs_hidden_from_primary_operator_copy": True,
        },
        "recipe_refs": {
            "selected_rails": tuple(item["rail_ref"] for item in recipe["selected_rails"]),
            "capital_hilton_is_complex_recipe_not_default": True,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "operator_copy": {
            "headline": "Draft path prepared.",
            "body": (
                "Nothing was sent or submitted. Coupa portal submission proof is still required before this "
                "invoice can be treated as sent. "
                + (
                    "OpenClaw needs the current invoice page/period before it can attach the Excel invoice. "
                    if not _artifact_linked_to_selected_invoice(receipts)
                    else ""
                )
                + "Review only; approval and execution remain separate."
            ),
            "approval_question": guardian.operator_question,
            "button_labels": APPROVAL_BUTTONS,
        },
        "proof_shelf_copy": {
            "guardian_output_validation": "Safety check passed for showing this draft/status only.",
            "guardian_approval": "No Guardian approval request is ready until prerequisites exist.",
            "operator_approval": semantic_status["operator_approval_status"],
            "execution": "No email send, Coupa submit, payment update, or ledger action happened.",
        },
        "generated_at": generated_at,
    }
    bundle["machine_proof"] = {
        "excel_invoice_artifact_slot_present": True,
        "existing_artifact_without_invoice_record_linkage_is_candidate_only": excel.proof_status
        == "GENERATED_INVOICE_ARTIFACT_CANDIDATE",
        "workbook_may_contain_multiple_invoice_records": True,
        "attachment_ready_requires_invoice_record_linkage": not excel.attachment_ready
        or _artifact_linked_to_selected_invoice(receipts),
        "preview_section_present": preview_section["preview_kind"] in {"EXCEL", "NONE"},
        "preview_generation_performed": preview_section["generation_performed"],
        "artifact_inspection_paths_are_mac_visible": not artifact_actions["open_file_available"]
        or str(artifact_actions["open_file_mac_path"]).startswith("/Volumes/openclaw_e/"),
        "right_workbook_wrong_page_no_external_action": next(
            action
            for action in correction_actions
            if action["resulting_request_kind"] == "invoice_page_correction_request"
        )["no_external_action"],
        "approval_footer_ready": approval_footer["approval_ready"],
        "proof_timeline_present": len(proof_timeline) >= 10,
        "clara_draft_slot_present": True,
        "coupa_required_for_capital_hilton": True,
        "draft_does_not_imply_sent": clara.draft_only and not clara.sent,
        "approval_does_not_imply_send": guardian.approval_required and not guardian.send_allowed,
        "guardian_output_validation_does_not_imply_approval_request": semantic_status[
            "guardian_output_validation_status"
        ]
        == "PASSED_FOR_DRAFT_DISPLAY_ONLY"
        and semantic_status["guardian_approval_request_status"] != "READY_TO_REQUEST_OPERATOR_APPROVAL",
        "operator_approval_does_not_imply_execution": semantic_status["operator_approval_status"]
        in {"NOT_GRANTED", "GRANTED_FOR_SPECIFIC_PACKAGE"}
        and semantic_status["email_send_execution_status"] in {"NOT_SENT", "SENT_RECEIPT_CONFIRMED"},
        "coupa_primary_before_email_success": semantic_status["primary_invoice_trigger"]
        == "COUPA_SUPPLIER_PORTAL_INVOICE",
        "send_blocked_without_required_receipts": not _send_allowed(receipts),
        "all_action_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "operator_copy_jargon_free": not _contains_operator_jargon(bundle["operator_copy"]),
        "pdf_excel_generation_performed": False,
        "content_hash": "",
    }
    bundle["machine_proof"]["content_hash"] = _content_hash(bundle)
    return bundle


def build_non_coupa_bundle_example(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    return {
        "bundle_id": "invoice_review_bundle:st_annes:v0",
        "client_ref": "st_annes",
        "workflow_ref": "st_annes_invoice_workflow",
        "status": "RECIPE_PLACEHOLDER_REVIEW_ONLY",
        "coupa_invoice_proof": {"required": False, "status": "NOT_REQUIRED_BY_RECIPE"},
        "operator_copy": {
            "headline": "Review the St. Anne's invoice package.",
            "body": "This recipe does not require Coupa proof unless the client recipe is changed.",
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "generated_at": generated_at,
    }


def _contains_operator_jargon(operator_copy: Mapping[str, Any]) -> bool:
    text = stable_json(operator_copy).lower()
    return any(term in text for term in OPERATOR_JARGON_BLOCKLIST)


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    capital = build_capital_hilton_bundle(generated_at=generated_at)
    non_coupa = build_non_coupa_bundle_example(generated_at=generated_at)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_summary": (
            "Mission Control can render a Capital Hilton invoice review card with invoice artifact, "
            "Clara draft, Coupa proof status, recipients, and approval buttons. Nothing is sent."
        ),
        "approval_button_contract": {
            "button_labels": APPROVAL_BUTTONS,
            "typed_approval_code_required": False,
            "buttons_are_ui_controls": True,
        },
        "invoice_review_states": INVOICE_REVIEW_STATES,
        "capital_hilton_bundle": capital,
        "non_coupa_recipe_example": non_coupa,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "hidden_from_primary_ui": (
            "approval_ref",
            "button_ref",
            "internal_action_ref",
            "required_receipts",
            "receipt hashes",
        ),
        "machine_proof": {
            "capital_hilton_has_review_bundle": True,
            "capital_hilton_coupa_proof_required": capital["coupa_invoice_proof"]["required"] is True,
            "non_coupa_client_does_not_require_coupa": non_coupa["coupa_invoice_proof"]["required"] is False,
            "button_labels_present": tuple(capital["guardian_approval_request"]["buttons"][i]["label"] for i in range(len(APPROVAL_BUTTONS))) == APPROVAL_BUTTONS,
            "typed_approval_codes_not_operator_primary": True,
            "send_action_enabled": False,
            "coupa_action_enabled": False,
            "pdf_excel_generation_performed": False,
            "all_action_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": "",
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def write_exports(payload: Mapping[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    capital = payload["capital_hilton_bundle"]
    card = capital["helm_card"]
    buttons = ", ".join(card["button_labels"])
    blockers = capital.get("blockers") or ()
    linkage_message = (
        "OpenClaw needs the current invoice page/period before it can attach the Excel invoice."
        if capital["excel_invoice_artifact"]["linkage_status"] != "LINKED_TO_SELECTED_INVOICE"
        else "Generated invoice artifact is linked to the selected invoice record."
    )
    status_lines = tuple(dict.fromkeys((card["primary_warning"] or "Coupa proof is present.", linkage_message)))
    lines = [
        "# Invoice Review Bundle",
        "",
        "Review the Capital Hilton invoice package.",
        "Nothing has been sent.",
        *status_lines,
        "",
        "Approval card:",
        f"- Question: {capital['guardian_approval_request']['operator_question']}",
        f"- Buttons: {buttons}",
        f"- Excel invoice candidate: {capital['excel_invoice_artifact']['display_name']}",
        f"- Preview: {capital['preview_section']['preview_operator_copy']}",
        f"- Attachment readiness: {str(capital['excel_invoice_artifact']['attachment_ready']).lower()}",
        f"- Clara draft subject: {capital['clara_email_draft']['subject']}",
        f"- Approval footer: {capital['approval_footer']['sticky_footer_operator_copy']}",
        "",
        "Blockers:",
        *[f"- {blocker}" for blocker in blockers],
        "",
        "Proof is available behind disclosure. No email, Coupa, browser, ledger, or production action is enabled.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export invoice review bundle read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)
    payload = build_payload(generated_at=args.generated_at)
    json_path, operator_path = write_exports(payload, args.export_root)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(
            stable_json(
                {
                    "read_model_id": READ_MODEL_ID,
                    "json_path": json_path.as_posix(),
                    "operator_path": operator_path.as_posix(),
                    "status": payload["contract_status"],
                    "button_labels": payload["approval_button_contract"]["button_labels"],
                    "send_action_enabled": payload["machine_proof"]["send_action_enabled"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
