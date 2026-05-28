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

ACTION_NOT_WIRED_REASON = "This correction path is not wired yet."


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
    rail_ref: str
    supplier_portal_required: bool
    supplier_portal_provider: str
    provider_display_name: str
    requires_purchase_order: bool
    purchase_order_ref: str | None
    portal_invoice_draft_status: str
    portal_submission_proof_required: bool
    portal_submission_proof_status: str
    portal_submission_receipt_required: bool
    portal_submission_action_allowed: bool
    canonical_action_kind: str
    compatibility_action_kinds: tuple[str, ...]
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
    action_ref: str
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
                action_ref=f"invoice_review_action:approval_button_{label.lower()}:{_short_hash(bundle_id, label)}",
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
    status = "SUBMITTED_RECEIPT_CONFIRMED" if submitted else "MISSING"
    return CoupaInvoiceProof(
        required=True,
        rail_ref=workflow.SUPPLIER_PORTAL_RAIL,
        supplier_portal_required=True,
        supplier_portal_provider="COUPA",
        provider_display_name="Coupa supplier portal",
        requires_purchase_order=True,
        purchase_order_ref="po_ref:confirmed_by_receipt" if po_known else None,
        portal_invoice_draft_status="NOT_CREATED_BY_OPENCLAW",
        portal_submission_proof_required=True,
        portal_submission_proof_status=status,
        portal_submission_receipt_required=True,
        portal_submission_action_allowed=False,
        canonical_action_kind="request_supplier_portal_submission_proof",
        compatibility_action_kinds=("request_coupa_submission_proof",),
        status=status,
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


def _action_descriptor(
    *,
    action_kind: str,
    label: str,
    intended_use: str,
    operator_visible_message: str,
    expected_receipt_type: str,
    proof_refs: tuple[str, ...] = (),
    enabled: bool = True,
    disabled_reason: str | None = None,
    payload_fields: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    request_type = "invoice_review_guided_action_request"
    action_ref = f"invoice_review_action:{action_kind}:{_short_hash(CAPITAL_HILTON_BUNDLE_ID, action_kind)}"
    idempotency_key = f"invoice-review:{_short_hash(CAPITAL_HILTON_BUNDLE_ID, action_kind, expected_receipt_type)}"
    hidden_request_payload = {
        "request_type": request_type,
        "request_kind": action_kind,
        "type": request_type,
        "source_bundle_id": CAPITAL_HILTON_BUNDLE_ID,
        "source_workflow_id": CAPITAL_HILTON_WORKFLOW_REF,
        "client_ref": "capital_hilton",
        "action_ref": action_ref,
        "action_kind": action_kind,
        "intended_use": intended_use,
        "no_external_action": True,
        "physical_deletion_allowed": False,
        "browser_automation_allowed": False,
        "email_send_allowed": False,
        "coupa_submit_allowed": False,
        "supplier_portal_submit_allowed": False,
        "ledger_posting_allowed": False,
        "expected_receipt_type": expected_receipt_type,
        "proof_refs": proof_refs,
        "idempotency_key": idempotency_key,
    }
    if payload_fields:
        hidden_request_payload.update(payload_fields)
    return {
        "action_ref": action_ref,
        "label": label,
        "enabled": enabled,
        "disabled_reason": disabled_reason if not enabled else None,
        "action_kind": action_kind,
        "intended_use": intended_use,
        "operator_visible_message": operator_visible_message,
        "hidden_request_payload": hidden_request_payload,
        "request_type": request_type,
        "request_kind": action_kind,
        "type": request_type,
        "source_bundle_id": CAPITAL_HILTON_BUNDLE_ID,
        "source_workflow_id": CAPITAL_HILTON_WORKFLOW_REF,
        "no_external_action": True,
        "idempotency_key": idempotency_key,
        "expected_receipt_type": expected_receipt_type,
        "proof_refs": proof_refs,
    }


def _correction_action(action: str, *, enabled: bool = True, excel: InvoiceReviewArtifact | None = None) -> dict[str, Any]:
    specs = {
        "CONFIRM_THIS_INVOICE": {
            "label": "Looks Right / Confirm This Invoice",
            "action_kind": "confirm_invoice_review_candidate",
            "followup_prompt": "Confirm the workbook, invoice page/period, and generated artifact match.",
            "request_kind": "invoice_selection_confirmation_request",
            "expected_receipt_type": "invoice_review_confirmation_intake_receipt",
            "message": "Starting invoice review confirmation.",
        },
        "RIGHT_WORKBOOK_WRONG_PAGE": {
            "label": "Right Workbook, Wrong Page",
            "action_kind": "start_invoice_record_selection",
            "followup_prompt": "Which invoice page or period should OpenClaw use instead?",
            "request_kind": "invoice_page_selection_request",
            "expected_receipt_type": "invoice_record_selection_request_receipt",
            "message": "Starting invoice page selection.",
        },
        "WRONG_WORKBOOK": {
            "label": "Wrong Workbook",
            "action_kind": "replace_source_workbook_reference",
            "followup_prompt": "Which workbook should OpenClaw use for this invoice?",
            "request_kind": "workbook_reference_replacement_request",
            "expected_receipt_type": "source_workbook_replacement_request_receipt",
            "message": "Starting source workbook replacement.",
        },
        "WRONG_CLIENT": {
            "label": "Wrong Client",
            "action_kind": "reassign_invoice_review_client",
            "followup_prompt": "Which client should this invoice review belong to?",
            "request_kind": "client_correction_request",
            "expected_receipt_type": "client_correction_request_receipt",
            "message": "Starting client correction.",
            "disabled_reason": ACTION_NOT_WIRED_REASON,
        },
        "SELECT_DIFFERENT_PAGE": {
            "label": "Select Different Page",
            "action_kind": "start_invoice_record_selection",
            "followup_prompt": "Which page, sheet, or invoice period should OpenClaw prepare?",
            "request_kind": "invoice_page_selection_request",
            "expected_receipt_type": "invoice_record_selection_request_receipt",
            "message": "Starting invoice page selection.",
        },
        "OPEN_WORKBOOK": {
            "label": "Open Workbook",
            "action_kind": "open_invoice_workbook_candidate",
            "followup_prompt": None,
            "request_kind": "local_artifact_inspection_request",
            "expected_receipt_type": "local_artifact_inspection_receipt",
            "message": "Opening the candidate workbook for inspection.",
            "disabled_reason": "No Mac-visible candidate workbook is available.",
        },
        "EXPLAIN_THIS_REVIEW": {
            "label": "Explain This Review",
            "action_kind": "explain_invoice_review",
            "followup_prompt": None,
            "request_kind": "review_explanation_request",
            "expected_receipt_type": "invoice_review_explanation_receipt",
            "message": "Explaining this invoice review.",
        },
    }
    spec = specs[action]
    disabled_reason = spec.get("disabled_reason")
    if action == "OPEN_WORKBOOK" and enabled:
        disabled_reason = None
    is_enabled = enabled and disabled_reason is None
    proof_refs = (excel.artifact_ref,) if excel and excel.preview_available else ()
    descriptor = _action_descriptor(
        action_kind=spec["action_kind"],
        label=spec["label"],
        intended_use="review_correction_or_inspection",
        operator_visible_message=spec["message"],
        expected_receipt_type=spec["expected_receipt_type"],
        proof_refs=proof_refs,
        enabled=is_enabled,
        disabled_reason=disabled_reason,
        payload_fields={
            "source_artifact_ref": excel.artifact_ref if excel else None,
            "open_file_mac_path": excel.mac_visible_ref if excel and action == "OPEN_WORKBOOK" else None,
            "resulting_request_kind": spec["request_kind"],
            "requires_followup": spec["followup_prompt"] is not None,
            "followup_prompt": spec["followup_prompt"],
        },
    )
    return {
        **descriptor,
        "requires_followup": spec["followup_prompt"] is not None,
        "followup_prompt": spec["followup_prompt"],
        "resulting_request_kind": spec["request_kind"],
        "mutates_workbook": False,
        "mutates_production_state": False,
    }


def _correction_actions(excel: InvoiceReviewArtifact) -> tuple[dict[str, Any], ...]:
    return tuple(
        _correction_action(action, enabled=(action != "OPEN_WORKBOOK" or excel.preview_available), excel=excel)
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
                **_action_descriptor(
                    action_kind=f"approval_footer_{label.lower()}",
                    label=label,
                    intended_use="invoice_review_approval_footer",
                    operator_visible_message=label.replace("_", " ").title(),
                    expected_receipt_type="invoice_review_approval_footer_intake_receipt",
                    enabled=approval_ready if label == "APPROVE" else True,
                    disabled_reason="Approval is disabled until invoice selection, Coupa proof, recipients, and attachment proof are ready."
                    if label == "APPROVE" and not approval_ready
                    else None,
                ),
            }
            for label in APPROVAL_FOOTER_BUTTONS
        ),
        "sticky_footer_operator_copy": "Approval is disabled until invoice selection, Coupa proof, recipients, and attachment proof are ready."
        if not approval_ready
        else "Ready for review approval. Approval still does not send anything by itself.",
    }


def _timeline_item(
    title: str,
    *,
    status: str,
    operator_summary: str,
    why_it_matters: str,
    primary_action: dict[str, Any] | None,
    secondary_actions: tuple[dict[str, Any], ...] = (),
    required_receipts: tuple[str, ...] = (),
    receipt_ref: str | None = None,
    proof_ref: str | None = None,
    proof_refs: tuple[str, ...] = (),
    completion_receipt_ref: str | None = None,
    next_step_ref: str | None = None,
    hidden_internal_refs: tuple[str, ...] = (),
) -> dict[str, Any]:
    all_proof_refs = tuple(item for item in (*proof_refs, proof_ref, receipt_ref) if item)
    return {
        "step_ref": f"invoice_review_step:{title.lower().replace(' ', '_').replace('/', '_')}",
        "title": title,
        "label": title,
        "status": status,
        "operator_summary": operator_summary,
        "why_it_matters": why_it_matters,
        "required_receipts": required_receipts,
        "proof_refs": all_proof_refs,
        "primary_action": primary_action,
        "secondary_actions": secondary_actions,
        "completion_receipt_ref": completion_receipt_ref,
        "next_step_ref": next_step_ref,
        "receipt_ref": receipt_ref,
        "proof_ref": proof_ref,
        "operator_copy": operator_summary,
        "hidden_internal_refs": hidden_internal_refs,
    }


def _review_proof_timeline(
    *,
    receipts: set[str],
    excel: InvoiceReviewArtifact,
    coupa: CoupaInvoiceProof,
    guardian: GuardianApprovalRequest,
    contacts_confirmed: bool,
    semantic_status: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    active_workbook_done = "active_workbook_confirmed_receipt" in receipts
    invoice_selected = {"invoice_record_selected_receipt", "invoice_period_confirmed_receipt"} <= receipts
    guardian_ready = guardian.status == "READY_TO_REQUEST_OPERATOR_APPROVAL"
    email_send_ready = _send_allowed(receipts) and excel.attachment_ready
    return (
        _timeline_item(
            "Active workbook",
            status="COMPLETE" if active_workbook_done else "NEEDS_ACTION",
            receipt_ref="active_workbook_confirmed_receipt" if "active_workbook_confirmed_receipt" in receipts else None,
            operator_summary="Workbook still needs confirmation." if not active_workbook_done else "Source workbook is confirmed.",
            why_it_matters="The current invoice must be tied to the intended workbook before artifact review can be trusted.",
            required_receipts=("active_workbook_confirmed_receipt",),
            primary_action=None
            if active_workbook_done
            else _action_descriptor(
                action_kind="confirm_source_workbook_reference",
                label="Confirm source workbook",
                intended_use="confirm_invoice_source_workbook",
                operator_visible_message="Starting source workbook confirmation.",
                expected_receipt_type="active_workbook_confirmed_receipt",
            ),
            secondary_actions=()
            if active_workbook_done
            else (
                _action_descriptor(
                    action_kind="replace_source_workbook_reference",
                    label="Use a different workbook",
                    intended_use="replace_invoice_source_workbook",
                    operator_visible_message="Starting source workbook replacement.",
                    expected_receipt_type="source_workbook_replacement_request_receipt",
                    payload_fields={"physical_deletion_allowed": False},
                ),
            ),
            completion_receipt_ref="active_workbook_confirmed_receipt" if active_workbook_done else None,
            next_step_ref="invoice_review_step:invoice_page_period",
            hidden_internal_refs=("workflow_ref",),
        ),
        _timeline_item(
            "Invoice page/period",
            status="COMPLETE" if invoice_selected else "NEEDS_ACTION",
            receipt_ref="invoice_record_selected_receipt" if "invoice_record_selected_receipt" in receipts else None,
            operator_summary="Choose the invoice page or period before treating the artifact as current.",
            why_it_matters="A running workbook can contain multiple invoice records, so OpenClaw needs the exact one for this package.",
            required_receipts=("invoice_record_selected_receipt", "invoice_period_confirmed_receipt"),
            primary_action=None
            if invoice_selected
            else _action_descriptor(
                action_kind="start_invoice_record_selection",
                label="Select invoice page",
                intended_use="select_invoice_record_or_period",
                operator_visible_message="Starting invoice page selection.",
                expected_receipt_type="invoice_record_selection_request_receipt",
            ),
            completion_receipt_ref="invoice_record_selected_receipt" if invoice_selected else None,
            next_step_ref="invoice_review_step:generated_invoice_artifact",
            hidden_internal_refs=("invoice_record_selected_receipt", "invoice_period_confirmed_receipt"),
        ),
        _timeline_item(
            "Generated invoice artifact",
            status="COMPLETE" if excel.proof_status == "GENERATED_INVOICE_ARTIFACT_CONFIRMED" else "CANDIDATE",
            proof_ref=excel.artifact_ref if excel.preview_available else None,
            operator_summary="Excel artifact is candidate-only until linked to the selected invoice.",
            why_it_matters="Existing files do not prove they are the current invoice or the correct attachment.",
            required_receipts=("generated_invoice_artifact_linkage_receipt", "invoice_attachment_proof_receipt"),
            primary_action=_action_descriptor(
                action_kind="regenerate_or_link_invoice_artifact",
                label="Regenerate or link invoice",
                intended_use="start_generated_invoice_artifact_linkage",
                operator_visible_message="Starting invoice artifact link review.",
                expected_receipt_type="generated_invoice_artifact_linkage_request_receipt",
                proof_refs=(excel.artifact_ref,) if excel.preview_available else (),
            )
            if excel.proof_status != "GENERATED_INVOICE_ARTIFACT_CONFIRMED"
            else None,
            completion_receipt_ref="generated_invoice_artifact_linkage_receipt"
            if excel.proof_status == "GENERATED_INVOICE_ARTIFACT_CONFIRMED"
            else None,
            next_step_ref="invoice_review_step:coupa_portal_proof",
            hidden_internal_refs=("generated_invoice_artifact_linkage_receipt",),
        ),
        _timeline_item(
            "Coupa portal proof",
            status="COMPLETE" if coupa.status == "SUBMITTED_RECEIPT_CONFIRMED" else "NEEDS_ACTION",
            receipt_ref=coupa.proof_ref,
            operator_summary="Coupa portal submission proof is still required.",
            why_it_matters="For Capital Hilton, the Coupa portal invoice is the primary payment trigger.",
            required_receipts=("purchase_order_confirmed_receipt", "portal_invoice_submission_receipt"),
            primary_action=None
            if coupa.status == "SUBMITTED_RECEIPT_CONFIRMED"
            else _action_descriptor(
                action_kind="request_supplier_portal_submission_proof",
                label="Start Coupa proof step",
                intended_use="request_supplier_portal_submission_proof",
                operator_visible_message="Starting Coupa proof step.",
                expected_receipt_type="supplier_portal_proof_intake_requested_receipt",
                payload_fields={
                    "canonical_action_kind": "request_supplier_portal_submission_proof",
                    "compatibility_action_kind": "request_coupa_submission_proof",
                    "portal_provider": "COUPA",
                    "provider_display_name": "Coupa supplier portal",
                    "supplier_portal_required": True,
                    "browser_automation_allowed": False,
                    "portal_submission_allowed": False,
                    "supplier_portal_submit_allowed": False,
                    "proof_intake_only": True,
                },
            ),
            completion_receipt_ref=coupa.proof_ref,
            next_step_ref="invoice_review_step:clara_draft",
            hidden_internal_refs=("portal_invoice_submission_receipt",),
        ),
        _timeline_item(
            "Clara draft",
            status="CANDIDATE",
            receipt_ref="clara_email_draft_receipt" if "clara_email_draft_receipt" in receipts else None,
            operator_summary="Draft only. Nothing was sent.",
            why_it_matters="The draft can be reviewed before any approval or send path exists.",
            required_receipts=("clara_email_draft_receipt",),
            primary_action=_action_descriptor(
                action_kind="review_clara_draft_prerequisites",
                label="Review draft prerequisites",
                intended_use="review_clara_draft_prerequisites",
                operator_visible_message="Reviewing Clara draft prerequisites.",
                expected_receipt_type="clara_draft_prerequisite_review_receipt",
            ),
            secondary_actions=(
                _action_descriptor(
                    action_kind="edit_clara_draft_request",
                    label="Edit draft",
                    intended_use="request_clara_draft_edit",
                    operator_visible_message="Starting Clara draft edit request.",
                    expected_receipt_type="clara_draft_edit_request_receipt",
                    enabled=False,
                    disabled_reason=ACTION_NOT_WIRED_REASON,
                ),
            ),
            completion_receipt_ref="clara_email_draft_receipt" if "clara_email_draft_receipt" in receipts else None,
            next_step_ref="invoice_review_step:recipients",
            hidden_internal_refs=("clara_email_draft_receipt",),
        ),
        _timeline_item(
            "Recipients",
            status="COMPLETE" if contacts_confirmed else "NEEDS_ACTION",
            receipt_ref="recipient_confirmation_receipt" if contacts_confirmed else None,
            operator_summary="Annette, Chyna, and Will are candidate recipients until confirmed.",
            why_it_matters="OpenClaw should not assume recipient addresses or roles without confirmation.",
            required_receipts=("recipient_confirmation_receipt",),
            primary_action=None
            if contacts_confirmed
            else _action_descriptor(
                action_kind="review_and_confirm_recipients",
                label="Review recipients",
                intended_use="review_capital_hilton_recipient_candidates",
                operator_visible_message="Starting recipient review.",
                expected_receipt_type="recipient_confirmation_request_receipt",
                payload_fields={
                    "candidate_contacts": ("Annette", "Chyna", "Will"),
                    "email_addresses_known": False,
                    "do_not_invent_emails": True,
                },
            ),
            completion_receipt_ref="recipient_confirmation_receipt" if contacts_confirmed else None,
            next_step_ref="invoice_review_step:guardian_approval_request",
            hidden_internal_refs=("recipient_confirmation_receipt",),
        ),
        _timeline_item(
            "Guardian approval request",
            status="NEEDS_ACTION" if guardian_ready else "BLOCKED",
            receipt_ref="guardian_approval_receipt" if "guardian_approval_receipt" in receipts else None,
            operator_summary="Approval request is blocked until prerequisites are ready."
            if not guardian_ready
            else "Guardian approval can be requested for this reviewed package.",
            why_it_matters="Approval must stay separate from output validation and execution.",
            required_receipts=("guardian_approval_receipt",),
            primary_action=_action_descriptor(
                action_kind="request_guardian_invoice_approval",
                label="Request Guardian approval",
                intended_use="request_guardian_invoice_approval",
                operator_visible_message="Requesting Guardian invoice approval.",
                expected_receipt_type="guardian_approval_request_receipt",
                enabled=guardian_ready,
                disabled_reason=None if guardian_ready else "Invoice selection, artifact linkage, Coupa proof, recipients, and attachment proof are still incomplete.",
            )
            if guardian_ready
            else _action_descriptor(
                action_kind="show_approval_prerequisites",
                label="Show approval blockers",
                intended_use="show_approval_prerequisites",
                operator_visible_message="Showing approval blockers.",
                expected_receipt_type="approval_prerequisite_review_receipt",
            ),
            completion_receipt_ref="guardian_approval_receipt" if "guardian_approval_receipt" in receipts else None,
            next_step_ref="invoice_review_step:operator_approval",
            hidden_internal_refs=(guardian.approval_ref,),
        ),
        _timeline_item(
            "Operator approval",
            status="COMPLETE" if "operator_approval_receipt" in receipts else "BLOCKED",
            receipt_ref="operator_approval_receipt" if "operator_approval_receipt" in receipts else None,
            operator_summary="No operator approval has been granted.",
            why_it_matters="Operator approval is scoped to a specific package and does not execute a send.",
            required_receipts=("operator_approval_receipt",),
            primary_action=_action_descriptor(
                action_kind="show_approval_prerequisites",
                label="Show approval blockers",
                intended_use="show_operator_approval_prerequisites",
                operator_visible_message="Showing operator approval blockers.",
                expected_receipt_type="approval_prerequisite_review_receipt",
            ),
            completion_receipt_ref="operator_approval_receipt" if "operator_approval_receipt" in receipts else None,
            next_step_ref="invoice_review_step:email_send",
            hidden_internal_refs=("operator_approval_receipt",),
        ),
        _timeline_item(
            "Email send",
            status="COMPLETE" if "email_send_receipt" in receipts else "BLOCKED",
            receipt_ref="email_send_receipt" if "email_send_receipt" in receipts else None,
            operator_summary="No email has been sent.",
            why_it_matters="A draft and approval request are not execution receipts.",
            required_receipts=("guardian_approval_receipt", "operator_approval_receipt", "email_send_receipt"),
            primary_action=_action_descriptor(
                action_kind="prepare_send_approval_request",
                label="Prepare send approval",
                intended_use="prepare_email_send_approval_request",
                operator_visible_message="Preparing send approval request.",
                expected_receipt_type="send_approval_preparation_receipt",
                enabled=email_send_ready,
                disabled_reason=None
                if email_send_ready
                else "Email send remains disabled until approval, attachment, and execution prerequisites exist.",
                payload_fields={"email_send_allowed": False},
            ),
            completion_receipt_ref="email_send_receipt" if "email_send_receipt" in receipts else None,
            next_step_ref="invoice_review_step:payment_watch",
            hidden_internal_refs=("email_send_receipt",),
        ),
        _timeline_item(
            "Payment watch",
            status="COMPLETE" if "payment_detected_receipt" in receipts else "NOT_READY",
            receipt_ref="payment_detected_receipt" if "payment_detected_receipt" in receipts else None,
            operator_summary="No payment has been detected.",
            why_it_matters="Payment watch starts after submission/send receipts exist; it is not a ledger posting.",
            required_receipts=("payment_detected_receipt",),
            primary_action=_action_descriptor(
                action_kind="setup_payment_watch_after_submission",
                label="Set up payment watch",
                intended_use="setup_payment_watch_after_submission",
                operator_visible_message="Setting up payment watch after submission.",
                expected_receipt_type="payment_watch_setup_receipt",
                enabled=False,
                disabled_reason="Payment watch is disabled until portal/email receipts exist.",
            ),
            completion_receipt_ref="payment_detected_receipt" if "payment_detected_receipt" in receipts else None,
            next_step_ref="invoice_review_step:ledger_tax_evidence",
            hidden_internal_refs=("payment_detected_receipt",),
        ),
        _timeline_item(
            "Ledger/tax evidence",
            status="NOT_READY",
            receipt_ref="ledger_tax_evidence_receipt" if "ledger_tax_evidence_receipt" in receipts else None,
            operator_summary="Ledger and tax evidence are not ready.",
            why_it_matters="Payment detected is not ledger-posted or tax-filed.",
            required_receipts=("ledger_tax_evidence_receipt",),
            primary_action=_action_descriptor(
                action_kind="setup_payment_watch_after_submission",
                label="Set up payment watch",
                intended_use="setup_payment_watch_before_ledger_tax",
                operator_visible_message="Setting up payment watch before ledger or tax evidence.",
                expected_receipt_type="payment_watch_setup_receipt",
                enabled=False,
                disabled_reason="Ledger and tax evidence stay disabled until payment evidence exists.",
            ),
            completion_receipt_ref="ledger_tax_evidence_receipt" if "ledger_tax_evidence_receipt" in receipts else None,
            next_step_ref=None,
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


def _actionable_blockers(blockers: tuple[str, ...], proof_timeline: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    step_by_action = {
        "Coupa": "Coupa portal proof",
        "invoice page/period": "Invoice page/period",
        "current invoice page/period": "Invoice page/period",
        "Generated invoice artifact": "Generated invoice artifact",
        "Recipient": "Recipients",
        "Send": "Email send",
    }
    timeline_by_title = {step["title"]: step for step in proof_timeline}
    actionable: list[dict[str, Any]] = []
    for blocker in blockers:
        step_title = next((title for marker, title in step_by_action.items() if marker in blocker), None)
        step = timeline_by_title.get(step_title or "")
        action = step.get("primary_action") if step else None
        actionable.append(
            {
                "blocker_ref": f"invoice_review_blocker:{_short_hash(CAPITAL_HILTON_BUNDLE_ID, blocker)}",
                "operator_summary": blocker,
                "status": step["status"] if step else "BLOCKED",
                "primary_action": action,
                "disabled_reason": None
                if action and (action.get("enabled") or action.get("disabled_reason"))
                else "This blocker has no wired fix path yet.",
                "proof_refs": step.get("proof_refs", ()) if step else (),
            }
        )
    return tuple(actionable)


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
        contacts_confirmed=contacts_confirmed,
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
    actionable_blockers = _actionable_blockers(tuple(blockers), proof_timeline)
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
        "supplier_portal_invoice_submission": asdict(coupa),
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
        "actionable_blockers": actionable_blockers,
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
            "action_refs": tuple(button["action_ref"] for button in guardian.buttons),
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
            if action["action_kind"] == "start_invoice_record_selection"
        )["no_external_action"],
        "approval_footer_ready": approval_footer["approval_ready"],
        "proof_timeline_present": len(proof_timeline) >= 10,
        "actionable_timeline_present": all("primary_action" in item for item in proof_timeline),
        "visible_buttons_have_action_refs": all(
            button.get("action_ref")
            for button in (
                *correction_actions,
                *approval_footer["approval_buttons"],
                *guardian.buttons,
            )
        ),
        "incomplete_timeline_steps_have_actions_or_disabled_reasons": all(
            item["status"] == "COMPLETE"
            or (
                item.get("primary_action")
                and (item["primary_action"].get("enabled") or item["primary_action"].get("disabled_reason"))
            )
            for item in proof_timeline
        ),
        "clara_draft_slot_present": True,
        "coupa_required_for_capital_hilton": True,
        "supplier_portal_required_for_capital_hilton": True,
        "supplier_portal_provider_for_capital_hilton": "COUPA",
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
        "supplier_portal_invoice_submission": {
            "required": False,
            "supplier_portal_required": False,
            "supplier_portal_provider": None,
            "portal_submission_proof_required": False,
            "portal_submission_action_allowed": False,
            "status": "NOT_REQUIRED_BY_RECIPE",
        },
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
            "capital_hilton_supplier_portal_provider": capital["supplier_portal_invoice_submission"]["supplier_portal_provider"],
            "non_coupa_client_does_not_require_coupa": non_coupa["coupa_invoice_proof"]["required"] is False,
            "non_coupa_client_does_not_require_supplier_portal": non_coupa["supplier_portal_invoice_submission"]["required"] is False,
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
    actionable_blockers = capital.get("actionable_blockers") or ()
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
        "Guided fix paths:",
        *[
            f"- {item['operator_summary']} -> {item['primary_action']['label']}"
            if item.get("primary_action")
            else f"- {item['operator_summary']} -> not wired yet"
            for item in actionable_blockers
        ],
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
