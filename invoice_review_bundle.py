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
    "excel_invoice_generated_receipt",
    "invoice_attachment_proof_receipt",
    "clara_email_draft_receipt",
    "purchase_order_confirmed_receipt",
    "portal_invoice_submission_receipt",
    "guardian_approval_receipt",
    "operator_approval_receipt",
    "email_send_receipt",
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
    proof_status: str


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


def _file_proof_status(path: Path) -> str:
    return "LOCAL_ARTIFACT_PRESENT_REVIEW_ONLY" if path.exists() else "MISSING_ARTIFACT_PROOF"


def _excel_invoice_artifact() -> InvoiceReviewArtifact:
    exists = CAPITAL_HILTON_EXCEL_PATH.exists()
    return InvoiceReviewArtifact(
        artifact_ref=_artifact_ref(CAPITAL_HILTON_EXCEL_PATH),
        display_name="Capital Hilton Excel invoice for review",
        preview_available=exists,
        preview_ref=CAPITAL_HILTON_EXCEL_PATH.as_posix() if exists else None,
        proof_status=_file_proof_status(CAPITAL_HILTON_EXCEL_PATH),
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


def build_capital_hilton_bundle(
    *,
    present_receipts: Mapping[str, Any] | set[str] | tuple[str, ...] | list[str] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    receipts = _normalize_receipts(present_receipts)
    excel = _excel_invoice_artifact()
    clara = _clara_draft()
    coupa = _coupa_invoice_proof(receipts)
    contacts_confirmed = "recipient_confirmation_receipt" in receipts
    ready_for_send_review = (
        excel.preview_available
        and "invoice_attachment_proof_receipt" in receipts
        and "clara_email_draft_receipt" in receipts
        and contacts_confirmed
    )
    guardian = _guardian_approval_request(CAPITAL_HILTON_BUNDLE_ID, ready_for_send_review=ready_for_send_review)
    missing_receipts = tuple(receipt for receipt in REQUIRED_RECEIPTS if receipt not in receipts)
    blockers = []
    if coupa.status == "MISSING":
        blockers.append("Coupa submission proof is still required.")
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
            "status": "CANDIDATE_PENDING_CONFIRMATION",
        },
        "status": "READY_FOR_REVIEW_BLOCKED_FOR_SEND",
        "helm_card": {
            "title": "Review the Capital Hilton invoice package.",
            "operator_summary": "Nothing has been sent.",
            "primary_warning": "Coupa submission proof is still required." if coupa.status == "MISSING" else None,
            "safe_next_move": "Review the draft, confirm recipients, and keep send locked until approval.",
            "button_labels": APPROVAL_BUTTONS,
        },
        "excel_invoice_artifact": asdict(excel),
        "clara_email_draft": asdict(clara),
        "coupa_invoice_proof": asdict(coupa),
        "recipients": {
            "to_candidates": tuple(asdict(item) for item in _capital_hilton_recipients(confirmed=contacts_confirmed) if item.lane == "to"),
            "cc_candidates": tuple(asdict(item) for item in _capital_hilton_recipients(confirmed=contacts_confirmed) if item.lane == "cc"),
            "confirmation_status": "CONFIRMED_BY_RECEIPT" if contacts_confirmed else "CANDIDATE_UNCONFIRMED",
        },
        "guardian_approval_request": asdict(guardian),
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
            "headline": "Review the Capital Hilton invoice package.",
            "body": (
                "Nothing has been sent. "
                + ("Coupa submission proof is still required. " if coupa.status == "MISSING" else "")
                + "Approve only after the invoice, draft, recipients, attachment, and Coupa proof are correct."
            ),
            "approval_question": guardian.operator_question,
            "button_labels": APPROVAL_BUTTONS,
        },
        "generated_at": generated_at,
    }
    bundle["machine_proof"] = {
        "excel_invoice_artifact_slot_present": True,
        "clara_draft_slot_present": True,
        "coupa_required_for_capital_hilton": True,
        "draft_does_not_imply_sent": clara.draft_only and not clara.sent,
        "approval_does_not_imply_send": guardian.approval_required and not guardian.send_allowed,
        "send_blocked_without_required_receipts": not _send_allowed(receipts),
        "all_action_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "operator_copy_jargon_free": not _contains_operator_jargon(bundle["operator_copy"]),
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
    lines = [
        "# Invoice Review Bundle",
        "",
        "Review the Capital Hilton invoice package.",
        "Nothing has been sent.",
        card["primary_warning"] or "Coupa proof is present.",
        "",
        "Approval card:",
        f"- Question: {capital['guardian_approval_request']['operator_question']}",
        f"- Buttons: {buttons}",
        f"- Excel invoice preview: {capital['excel_invoice_artifact']['display_name']}",
        f"- Clara draft subject: {capital['clara_email_draft']['subject']}",
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
