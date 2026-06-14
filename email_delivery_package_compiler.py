"""Email Delivery Package Compiler v0.

This deterministic read-model assembles a safe email delivery package from
draft refs, recipient/contact refs, attachment/artifact refs, Guardian approval
requests, send gates, and proof requirements. It is the bridge between a
Cassandra draft worker, invoice/artifact refs, Guardian approval, and a future
gated send adapter.

It creates package/readback models only. It does not send email, create Gmail or
Mail drafts, send attachments, access Coupa, open browsers, handle credentials,
perform external action, run workflows, dispatch agents, inspect raw private
bodies, mutate Mission Control Swift, run Mac sync/import, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-25T00:00:00+00:00"

SCHEMA_VERSION = "email_delivery_package_compiler_v0"
READ_MODEL_ID = "email_delivery_package_compiler"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_SENDING_EMAIL_DELIVERY_PACKAGE_COMPILER"

RECIPIENT_STATUSES = (
    "RECIPIENT_CONFIRMED",
    "RECIPIENT_CANDIDATE",
    "RECIPIENT_MISSING",
    "RECIPIENT_BLOCKED_PRIVACY",
    "UNKNOWN_FAIL_CLOSED",
)

SEND_GATE_STATUSES = (
    "NOT_READY_MISSING_INPUTS",
    "READY_FOR_GUARDIAN_REVIEW",
    "WAITING_FOR_OPERATOR_APPROVAL",
    "APPROVED_NOT_SENT_FUTURE",
    "SEND_BLOCKED",
    "UNKNOWN_FAIL_CLOSED",
)

DELIVERY_STATUSES = (
    "NOT_SENT",
    "READY_PACKAGE_ONLY",
    "FUTURE_SEND_TARGET",
    "BLOCKED_MISSING_PROOF",
    "UNKNOWN_FAIL_CLOSED",
)

READBACK_STATUSES = (
    "DELIVERY_PACKAGE_READY_FOR_REVIEW",
    "NOT_READY_MISSING_RECIPIENT",
    "NOT_READY_MISSING_DRAFT",
    "NOT_READY_MISSING_ATTACHMENT",
    "NOT_READY_MISSING_APPROVAL",
    "BLOCKED_PRIVACY_BOUNDARY",
    "BLOCKED_SEND_GATE",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "RECIPIENT_MISSING",
    "RECIPIENT_UNCONFIRMED",
    "DRAFT_MISSING",
    "ATTACHMENT_REF_MISSING",
    "ATTACHMENT_HASH_MISSING",
    "APPROVAL_MISSING",
    "SEND_GATE_MISSING",
    "RAW_EMAIL_ADDRESS_EXPOSED",
    "RAW_ATTACHMENT_BODY_INCLUDED",
    "SEND_ATTEMPTED",
    "EXTERNAL_ACTION_ATTEMPTED",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_email_delivery_allowed": False,
    "live_email_send_allowed": False,
    "live_mail_send_allowed": False,
    "live_gmail_send_allowed": False,
    "live_gmail_draft_create_allowed": False,
    "live_attachment_send_allowed": False,
    "live_external_action_allowed": False,
    "live_approval_execution_allowed": False,
    "live_workflow_run_allowed": False,
    "live_agent_dispatch_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "live_coupa_access_allowed": False,
    "live_browser_allowed": False,
    "live_invoice_generation_allowed": False,
    "live_attachment_body_read_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

COMMON_BLOCKED_ACTIONS = (
    "email send",
    "Mail send",
    "Gmail send",
    "Gmail draft creation",
    "attachment send",
    "Coupa access",
    "browser automation",
    "approval execution",
    "workflow run",
    "agent dispatch",
    "external action",
)

CAPITAL_HILTON_PROOFS = (
    "confirmed recipient/contact ref",
    "reviewed email draft",
    "invoice artifact ref",
    "invoice artifact hash/fingerprint",
    "Guardian approval packet",
    "exact operator approval receipt",
    "future send receipt",
    "future attachment/send proof",
)


@dataclass(frozen=True)
class EmailDeliveryPackageCompiler:
    compiler_id: str
    doctrine: tuple[str, ...]
    source_draft_policy: tuple[str, ...]
    recipient_policy: tuple[str, ...]
    attachment_policy: tuple[str, ...]
    approval_policy: tuple[str, ...]
    send_gate_policy: tuple[str, ...]
    proof_policy: tuple[str, ...]
    delivery_readback_policy: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class EmailDeliveryPackage:
    package_id: str
    source_workflow_ref: str
    source_draft_ref: str
    source_approval_request_ref: str
    client_ref: str
    tenant_ref: str
    recipient_refs: tuple[str, ...]
    recipient_status: str
    subject: str
    body_ref_or_body_summary: str
    attachment_refs: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    required_approvals: tuple[str, ...]
    required_proofs: tuple[str, ...]
    send_gate_status: str
    delivery_status: str
    next_safe_move: str


@dataclass(frozen=True)
class EmailRecipientRef:
    recipient_ref: str
    safe_display_label: str
    tokenized_email_ref: str
    contact_source_ref: str
    confirmation_status: str
    privacy_class: str
    protected_ref_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class EmailAttachmentRef:
    attachment_ref: str
    artifact_ref: str
    safe_display_label: str
    artifact_type: str
    hash_or_fingerprint_ref: str
    source_file_ref: str
    exists_status: str
    approved_for_attachment: bool
    privacy_class: str
    next_safe_move: str


@dataclass(frozen=True)
class EmailSendGate:
    gate_id: str
    package_ref: str
    required_covenant_ref: str
    required_guardian_approval_ref: str
    exact_approval_phrase: str
    missing_items: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    send_allowed: bool
    send_executed: bool
    external_authority: bool
    next_safe_move: str


@dataclass(frozen=True)
class EmailDeliveryReadback:
    readback_id: str
    package_ref: str
    status: str
    operator_headline: str
    operator_message: str
    package_summary: str
    recipient_summary: str
    draft_summary: str
    attachment_summary: str
    missing_items: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    approval_status: str
    proof_status: str
    how_to_fix: str
    next_safe_move: str


@dataclass(frozen=True)
class EmailDeliveryProofPlan:
    proof_plan_id: str
    package_ref: str
    required_proofs: tuple[str, ...]
    available_proof_refs: tuple[str, ...]
    missing_proofs: tuple[str, ...]
    completion_label: str
    completion_allowed: bool
    final_readback_target: str
    next_safe_move: str


@dataclass(frozen=True)
class EmailDeliveryPackageBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:16]}"


def build_compiler() -> EmailDeliveryPackageCompiler:
    return EmailDeliveryPackageCompiler(
        compiler_id="email_delivery_package_compiler_v0",
        doctrine=(
            "Compiler creates a delivery package, not a send action.",
            "Package must bind recipient refs, draft refs, attachment refs, approval refs, send gate, and proof requirements.",
            "Package must state missing items and blocked actions clearly.",
            "Readbacks must never claim delivery or say sent.",
            "External authority remains false.",
        ),
        source_draft_policy=(
            "Draft comes from Cassandra draft worker or other scoped draft ref.",
            "Body may be summarized or referenced; raw private mail bodies are not included.",
            "A missing draft blocks package readiness.",
        ),
        recipient_policy=(
            "Recipient uses safe display labels and tokenized contact refs.",
            "Raw email address is not exposed in normal read-models.",
            "Candidate recipients can be packaged for review but cannot be considered send-ready.",
        ),
        attachment_policy=(
            "Attachments are refs to artifacts, never raw file bodies.",
            "Attachment hash/fingerprint proof is required.",
            "Missing attachment ref or hash blocks package readiness.",
        ),
        approval_policy=(
            "Action Covenant and Guardian approval request refs are required before future send.",
            "Operator approval receipt is future proof, not created here.",
            "Approval execution remains disabled.",
        ),
        send_gate_policy=(
            "Send gate records missing items and exact approval phrase.",
            "send_allowed false, send_executed false, external_authority false in this lane.",
            "A future gated adapter must produce send and attachment proof receipts.",
        ),
        proof_policy=(
            "Completion requires recipient confirmation, reviewed draft, invoice artifact ref, artifact hash/fingerprint, Guardian packet, exact operator approval receipt, future send receipt, and attachment/send proof.",
            "INVOICE SENT is a future target only.",
        ),
        delivery_readback_policy=(
            "Readback is human-readable.",
            "Blocked/not-ready readbacks include how_to_fix.",
            "Do not say email ready to send unless recipient, draft, attachment refs, and approval packet are present.",
            "Never say sent.",
        ),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Use this compiler after draft/artifact/contact refs exist and before Guardian/operator approval.",
    )


def build_recipient(
    *,
    recipient_ref: str = "recipient_ref:annette_capital_hilton_candidate",
    confirmation_status: str = "RECIPIENT_CANDIDATE",
    safe_display_label: str = "Annette at Capital Hilton",
    tokenized_email_ref: str = "email_token_ref:capital_hilton_annette_candidate",
    contact_source_ref: str = "google_readonly_contact_ref:annette_candidate_metadata",
) -> EmailRecipientRef:
    return EmailRecipientRef(
        recipient_ref=recipient_ref,
        safe_display_label=safe_display_label,
        tokenized_email_ref=tokenized_email_ref,
        contact_source_ref=contact_source_ref,
        confirmation_status=confirmation_status,
        privacy_class="client_contact_private_ref",
        protected_ref_required=True,
        next_safe_move="Confirm recipient/contact route before any future send gate can proceed.",
    )


def build_attachment(
    *,
    attachment_ref: str = "attachment_ref:capital_hilton_invoice_pdf",
    artifact_ref: str = "artifact_ref:winship_branded_capital_hilton_invoice_pdf",
    safe_display_label: str = "Winship-branded Capital Hilton invoice PDF",
    artifact_type: str = "invoice_pdf",
    hash_or_fingerprint_ref: str = "artifact_hash_ref:capital_hilton_invoice_pdf_v0",
    exists_status: str = "ARTIFACT_REF_EXISTS",
    approved_for_attachment: bool = True,
) -> EmailAttachmentRef:
    return EmailAttachmentRef(
        attachment_ref=attachment_ref,
        artifact_ref=artifact_ref,
        safe_display_label=safe_display_label,
        artifact_type=artifact_type,
        hash_or_fingerprint_ref=hash_or_fingerprint_ref,
        source_file_ref="source_file_ref:capital_hilton_invoice_pdf_metadata",
        exists_status=exists_status,
        approved_for_attachment=approved_for_attachment,
        privacy_class="client_invoice_artifact_private_ref",
        next_safe_move="Keep attachment as a ref; future send adapter needs artifact and hash proof.",
    )


def build_package(
    *,
    package_id: str,
    recipient_refs: tuple[str, ...],
    recipient_status: str,
    source_draft_ref: str,
    source_approval_request_ref: str,
    attachment_refs: tuple[str, ...],
    missing_inputs: tuple[str, ...],
    send_gate_status: str,
    delivery_status: str,
    subject: str = "Capital Hilton Invoice Follow-Up",
    body_summary: str = "Candidate invoice follow-up draft for local records and payment follow-up; official payment rail remains Coupa/PO if context supports it.",
) -> EmailDeliveryPackage:
    return EmailDeliveryPackage(
        package_id=package_id,
        source_workflow_ref="capital_hilton_invoice_workflow",
        source_draft_ref=source_draft_ref,
        source_approval_request_ref=source_approval_request_ref,
        client_ref="client_ref:capital_hilton",
        tenant_ref="tenant_ref:winship",
        recipient_refs=recipient_refs,
        recipient_status=recipient_status,
        subject=subject,
        body_ref_or_body_summary=body_summary,
        attachment_refs=attachment_refs,
        missing_inputs=missing_inputs,
        required_approvals=(
            "Action Covenant for SEND_EMAIL",
            "Guardian approval request packet",
            "future exact operator approval receipt",
        ),
        required_proofs=CAPITAL_HILTON_PROOFS,
        send_gate_status=send_gate_status,
        delivery_status=delivery_status,
        next_safe_move="Review package and resolve missing gate items; do not send.",
    )


def build_send_gate(package: EmailDeliveryPackage) -> EmailSendGate:
    covenant_ref = "capital_hilton_invoice_covenant_v0"
    approval_ref = package.source_approval_request_ref
    missing = list(package.missing_inputs)
    if not approval_ref:
        missing.append("Guardian approval request packet")
    if "future exact operator approval receipt" not in missing:
        missing.append("future exact operator approval receipt")
    if "future send receipt" not in missing:
        missing.append("future send receipt")
    return EmailSendGate(
        gate_id=_stable_id("email_send_gate", package.package_id),
        package_ref=package.package_id,
        required_covenant_ref=covenant_ref,
        required_guardian_approval_ref=approval_ref or "missing",
        exact_approval_phrase=f"APPROVE SEND_EMAIL {covenant_ref}",
        missing_items=tuple(dict.fromkeys(missing)),
        blocked_actions=COMMON_BLOCKED_ACTIONS,
        send_allowed=False,
        send_executed=False,
        external_authority=False,
        next_safe_move="Create/complete Guardian approval and future operator receipt before a gated send adapter could act.",
    )


def build_proof_plan(
    package: EmailDeliveryPackage,
    *,
    available_proof_refs: tuple[str, ...],
) -> EmailDeliveryProofPlan:
    missing = tuple(proof for proof in package.required_proofs if proof not in available_proof_refs)
    return EmailDeliveryProofPlan(
        proof_plan_id=_stable_id("email_delivery_proof_plan", package.package_id),
        package_ref=package.package_id,
        required_proofs=package.required_proofs,
        available_proof_refs=available_proof_refs,
        missing_proofs=missing,
        completion_label="INVOICE SENT",
        completion_allowed=False,
        final_readback_target="future final readback only after send/attachment receipts exist",
        next_safe_move=(
            "Collect missing proofs and approval receipts; INVOICE SENT remains a future target."
            if missing
            else "Proof refs are assembled, but future send receipt is still required outside this lane."
        ),
    )


def build_readback(
    package: EmailDeliveryPackage,
    recipient: EmailRecipientRef | None,
    attachment: EmailAttachmentRef | None,
    send_gate: EmailSendGate,
    proof_plan: EmailDeliveryProofPlan,
) -> EmailDeliveryReadback:
    if package.recipient_status == "RECIPIENT_MISSING":
        status = "NOT_READY_MISSING_RECIPIENT"
        headline = "Email package needs a recipient"
        message = "I cannot assemble the delivery package until the recipient/contact route is confirmed."
        fix = "Confirm Annette/contact route or use the Google read-only contact confirmation rail."
    elif not package.source_draft_ref:
        status = "NOT_READY_MISSING_DRAFT"
        headline = "Email package needs a draft"
        message = "The delivery package is missing a reviewed draft ref."
        fix = "Run or reference Cassandra draft-only worker output for this email."
    elif not package.attachment_refs:
        status = "NOT_READY_MISSING_ATTACHMENT"
        headline = "Email package needs an attachment ref"
        message = "The delivery package is missing the invoice artifact/attachment ref."
        fix = "Generate or attach the Winship-branded Excel/PDF invoice artifact and hash/fingerprint it."
    elif attachment and not attachment.hash_or_fingerprint_ref:
        status = "NOT_READY_MISSING_ATTACHMENT"
        headline = "Email package needs an attachment hash"
        message = "The invoice artifact ref exists, but its hash/fingerprint proof is missing."
        fix = "Hash/fingerprint the invoice artifact before packaging it for review."
    elif not package.source_approval_request_ref:
        status = "NOT_READY_MISSING_APPROVAL"
        headline = "Email package needs Guardian approval packet"
        message = "The draft and attachment refs are present, but the approval packet is missing."
        fix = "Create an Action Covenant and Guardian approval request packet."
    elif send_gate.send_allowed:
        status = "UNKNOWN_FAIL_CLOSED"
        headline = "Email package failed closed"
        message = "A send gate attempted to allow sending in a non-send lane."
        fix = "Reset send_allowed to false and regenerate the package."
    else:
        status = "DELIVERY_PACKAGE_READY_FOR_REVIEW"
        headline = "Capital Hilton delivery package assembled"
        message = (
            "OpenClaw has assembled a delivery package for the Capital Hilton invoice email. "
            "Nothing has been sent. The package still needs Guardian/operator approval before any future send adapter can act."
        )
        fix = "Review the package and complete Guardian/operator approval in a future gated lane."

    recipient_summary = (
        f"{recipient.safe_display_label} ({recipient.confirmation_status})"
        if recipient
        else "No recipient ref"
    )
    attachment_summary = (
        f"{attachment.safe_display_label}; hash ref: {attachment.hash_or_fingerprint_ref or 'missing'}"
        if attachment
        else "No attachment ref"
    )
    return EmailDeliveryReadback(
        readback_id=_stable_id("email_delivery_readback", package.package_id, status),
        package_ref=package.package_id,
        status=status,
        operator_headline=headline,
        operator_message=message,
        package_summary=f"{package.subject}; delivery status {package.delivery_status}; send gate {package.send_gate_status}",
        recipient_summary=recipient_summary,
        draft_summary=package.body_ref_or_body_summary if package.source_draft_ref else "No draft ref",
        attachment_summary=attachment_summary,
        missing_items=tuple(dict.fromkeys((*package.missing_inputs, *send_gate.missing_items, *proof_plan.missing_proofs))),
        blocked_actions=COMMON_BLOCKED_ACTIONS,
        approval_status=package.send_gate_status,
        proof_status="BLOCKED_MISSING_PROOF" if proof_plan.missing_proofs else "PROOF_REFS_MODELED_NOT_SENT",
        how_to_fix=fix,
        next_safe_move=fix,
    )


def build_blockers() -> tuple[EmailDeliveryPackageBlocker, ...]:
    return (
        EmailDeliveryPackageBlocker(
            blocker_id="email_delivery_blocker_recipient_missing",
            blocker_type="RECIPIENT_MISSING",
            condition="No recipient/contact ref is present.",
            severity="high",
            elioperator_warning="Recipient/contact route is missing.",
            fail_closed=True,
            next_safe_move="Confirm recipient or use read-only contact confirmation.",
        ),
        EmailDeliveryPackageBlocker(
            blocker_id="email_delivery_blocker_recipient_unconfirmed",
            blocker_type="RECIPIENT_UNCONFIRMED",
            condition="Recipient is only a candidate.",
            severity="medium",
            elioperator_warning="Recipient must be confirmed before any future send.",
            fail_closed=True,
            next_safe_move="Confirm Annette/contact route.",
        ),
        EmailDeliveryPackageBlocker(
            blocker_id="email_delivery_blocker_draft_missing",
            blocker_type="DRAFT_MISSING",
            condition="Reviewed draft ref is missing.",
            severity="high",
            elioperator_warning="Draft ref is missing.",
            fail_closed=True,
            next_safe_move="Create or attach Cassandra draft worker readback.",
        ),
        EmailDeliveryPackageBlocker(
            blocker_id="email_delivery_blocker_attachment_missing",
            blocker_type="ATTACHMENT_REF_MISSING",
            condition="Invoice artifact/attachment ref is missing.",
            severity="high",
            elioperator_warning="Attachment ref is missing.",
            fail_closed=True,
            next_safe_move="Attach invoice artifact ref.",
        ),
        EmailDeliveryPackageBlocker(
            blocker_id="email_delivery_blocker_attachment_hash_missing",
            blocker_type="ATTACHMENT_HASH_MISSING",
            condition="Attachment ref lacks hash/fingerprint proof.",
            severity="high",
            elioperator_warning="Attachment hash/fingerprint is missing.",
            fail_closed=True,
            next_safe_move="Hash/fingerprint the artifact before send review.",
        ),
        EmailDeliveryPackageBlocker(
            blocker_id="email_delivery_blocker_approval_missing",
            blocker_type="APPROVAL_MISSING",
            condition="Action Covenant or Guardian approval request is missing.",
            severity="critical",
            elioperator_warning="Approval packet is missing.",
            fail_closed=True,
            next_safe_move="Create Action Covenant and Guardian approval request.",
        ),
        EmailDeliveryPackageBlocker(
            blocker_id="email_delivery_blocker_send_gate_missing",
            blocker_type="SEND_GATE_MISSING",
            condition="Send gate model is absent.",
            severity="critical",
            elioperator_warning="Send gate is missing.",
            fail_closed=True,
            next_safe_move="Regenerate package with EmailSendGate.",
        ),
        EmailDeliveryPackageBlocker(
            blocker_id="email_delivery_blocker_raw_email",
            blocker_type="RAW_EMAIL_ADDRESS_EXPOSED",
            condition="Raw private email address appears in normal read-model output.",
            severity="critical",
            elioperator_warning="Raw email address exposure is blocked.",
            fail_closed=True,
            next_safe_move="Use tokenized recipient refs and safe labels.",
        ),
        EmailDeliveryPackageBlocker(
            blocker_id="email_delivery_blocker_raw_attachment",
            blocker_type="RAW_ATTACHMENT_BODY_INCLUDED",
            condition="Attachment body or file bytes are included in package/read-model.",
            severity="critical",
            elioperator_warning="Raw attachment body is blocked.",
            fail_closed=True,
            next_safe_move="Use attachment refs and hash/fingerprint refs only.",
        ),
        EmailDeliveryPackageBlocker(
            blocker_id="email_delivery_blocker_send_attempt",
            blocker_type="SEND_ATTEMPTED",
            condition="Package compiler attempts to send email or attachment.",
            severity="critical",
            elioperator_warning="Send attempt is blocked.",
            fail_closed=True,
            next_safe_move="Return package/readback only.",
        ),
        EmailDeliveryPackageBlocker(
            blocker_id="email_delivery_blocker_external_action",
            blocker_type="EXTERNAL_ACTION_ATTEMPTED",
            condition="Compiler attempts external account, browser, Coupa, Mail, Gmail, or runtime action.",
            severity="critical",
            elioperator_warning="External action is blocked.",
            fail_closed=True,
            next_safe_move="Stay in deterministic read-model generation.",
        ),
        EmailDeliveryPackageBlocker(
            blocker_id="email_delivery_blocker_unknown",
            blocker_type="UNKNOWN_FAIL_CLOSED",
            condition="Unknown package state or unsafe request.",
            severity="high",
            elioperator_warning="Unknown email delivery package state fails closed.",
            fail_closed=True,
            next_safe_move="Ask for scoped recipient/draft/attachment/approval refs.",
        ),
    )


def _package_bundle(
    *,
    package: EmailDeliveryPackage,
    recipient: EmailRecipientRef | None,
    attachment: EmailAttachmentRef | None,
    available_proofs: tuple[str, ...],
) -> dict[str, Any]:
    send_gate = build_send_gate(package)
    proof_plan = build_proof_plan(package, available_proof_refs=available_proofs)
    readback = build_readback(package, recipient, attachment, send_gate, proof_plan)
    return {
        "package": asdict(package),
        "recipient": asdict(recipient) if recipient else None,
        "attachment": asdict(attachment) if attachment else None,
        "send_gate": asdict(send_gate),
        "proof_plan": asdict(proof_plan),
        "readback": asdict(readback),
    }


def build_examples() -> dict[str, Any]:
    recipient_candidate = build_recipient(confirmation_status="RECIPIENT_CANDIDATE")
    recipient_confirmed = build_recipient(
        recipient_ref="recipient_ref:annette_capital_hilton_confirmed",
        confirmation_status="RECIPIENT_CONFIRMED",
        tokenized_email_ref="email_token_ref:capital_hilton_annette_confirmed",
    )
    attachment = build_attachment()
    complete_package = build_package(
        package_id="email_delivery_package_capital_hilton_ready_for_review_v0",
        recipient_refs=(recipient_candidate.recipient_ref,),
        recipient_status=recipient_candidate.confirmation_status,
        source_draft_ref="cassandra_draft_ref:capital_hilton_invoice_followup_candidate",
        source_approval_request_ref="guardian_approval_capital_hilton_email_v0",
        attachment_refs=(attachment.attachment_ref,),
        missing_inputs=("future exact operator approval receipt", "future send receipt", "future attachment/send proof"),
        send_gate_status="WAITING_FOR_OPERATOR_APPROVAL",
        delivery_status="NOT_SENT",
    )
    missing_recipient = build_package(
        package_id="email_delivery_package_missing_recipient_v0",
        recipient_refs=(),
        recipient_status="RECIPIENT_MISSING",
        source_draft_ref="cassandra_draft_ref:capital_hilton_invoice_followup_candidate",
        source_approval_request_ref="guardian_approval_capital_hilton_email_v0",
        attachment_refs=(attachment.attachment_ref,),
        missing_inputs=("confirmed recipient/contact ref",),
        send_gate_status="NOT_READY_MISSING_INPUTS",
        delivery_status="BLOCKED_MISSING_PROOF",
    )
    missing_draft = build_package(
        package_id="email_delivery_package_missing_draft_v0",
        recipient_refs=(recipient_confirmed.recipient_ref,),
        recipient_status=recipient_confirmed.confirmation_status,
        source_draft_ref="",
        source_approval_request_ref="guardian_approval_capital_hilton_email_v0",
        attachment_refs=(attachment.attachment_ref,),
        missing_inputs=("reviewed email draft",),
        send_gate_status="NOT_READY_MISSING_INPUTS",
        delivery_status="BLOCKED_MISSING_PROOF",
    )
    missing_attachment = build_package(
        package_id="email_delivery_package_missing_attachment_v0",
        recipient_refs=(recipient_confirmed.recipient_ref,),
        recipient_status=recipient_confirmed.confirmation_status,
        source_draft_ref="cassandra_draft_ref:capital_hilton_invoice_followup_candidate",
        source_approval_request_ref="guardian_approval_capital_hilton_email_v0",
        attachment_refs=(),
        missing_inputs=("invoice artifact ref", "invoice artifact hash/fingerprint"),
        send_gate_status="NOT_READY_MISSING_INPUTS",
        delivery_status="BLOCKED_MISSING_PROOF",
    )
    missing_hash_attachment = build_attachment(hash_or_fingerprint_ref="")
    missing_hash = build_package(
        package_id="email_delivery_package_missing_attachment_hash_v0",
        recipient_refs=(recipient_confirmed.recipient_ref,),
        recipient_status=recipient_confirmed.confirmation_status,
        source_draft_ref="cassandra_draft_ref:capital_hilton_invoice_followup_candidate",
        source_approval_request_ref="guardian_approval_capital_hilton_email_v0",
        attachment_refs=(missing_hash_attachment.attachment_ref,),
        missing_inputs=("invoice artifact hash/fingerprint",),
        send_gate_status="NOT_READY_MISSING_INPUTS",
        delivery_status="BLOCKED_MISSING_PROOF",
    )
    missing_approval = build_package(
        package_id="email_delivery_package_missing_approval_v0",
        recipient_refs=(recipient_confirmed.recipient_ref,),
        recipient_status=recipient_confirmed.confirmation_status,
        source_draft_ref="cassandra_draft_ref:capital_hilton_invoice_followup_candidate",
        source_approval_request_ref="",
        attachment_refs=(attachment.attachment_ref,),
        missing_inputs=("Guardian approval packet", "Action Covenant for SEND_EMAIL"),
        send_gate_status="READY_FOR_GUARDIAN_REVIEW",
        delivery_status="NOT_SENT",
    )
    attempted_send_package = build_package(
        package_id="email_delivery_package_send_attempt_blocked_v0",
        recipient_refs=(recipient_confirmed.recipient_ref,),
        recipient_status=recipient_confirmed.confirmation_status,
        source_draft_ref="cassandra_draft_ref:capital_hilton_invoice_followup_candidate",
        source_approval_request_ref="guardian_approval_capital_hilton_email_v0",
        attachment_refs=(attachment.attachment_ref,),
        missing_inputs=("send attempted but blocked",),
        send_gate_status="SEND_BLOCKED",
        delivery_status="NOT_SENT",
    )

    available_complete = (
        "confirmed recipient/contact ref",
        "reviewed email draft",
        "invoice artifact ref",
        "invoice artifact hash/fingerprint",
        "Guardian approval packet",
    )
    return {
        "capital_hilton_complete_except_approval": _package_bundle(
            package=complete_package,
            recipient=recipient_candidate,
            attachment=attachment,
            available_proofs=available_complete,
        ),
        "missing_recipient": _package_bundle(
            package=missing_recipient,
            recipient=None,
            attachment=attachment,
            available_proofs=("reviewed email draft", "invoice artifact ref", "invoice artifact hash/fingerprint", "Guardian approval packet"),
        ),
        "missing_draft": _package_bundle(
            package=missing_draft,
            recipient=recipient_confirmed,
            attachment=attachment,
            available_proofs=("confirmed recipient/contact ref", "invoice artifact ref", "invoice artifact hash/fingerprint", "Guardian approval packet"),
        ),
        "missing_attachment": _package_bundle(
            package=missing_attachment,
            recipient=recipient_confirmed,
            attachment=None,
            available_proofs=("confirmed recipient/contact ref", "reviewed email draft", "Guardian approval packet"),
        ),
        "missing_attachment_hash": _package_bundle(
            package=missing_hash,
            recipient=recipient_confirmed,
            attachment=missing_hash_attachment,
            available_proofs=("confirmed recipient/contact ref", "reviewed email draft", "invoice artifact ref", "Guardian approval packet"),
        ),
        "missing_approval": _package_bundle(
            package=missing_approval,
            recipient=recipient_confirmed,
            attachment=attachment,
            available_proofs=("confirmed recipient/contact ref", "reviewed email draft", "invoice artifact ref", "invoice artifact hash/fingerprint"),
        ),
        "attempted_send": _package_bundle(
            package=attempted_send_package,
            recipient=recipient_confirmed,
            attachment=attachment,
            available_proofs=available_complete,
        ),
    }


def build_payload(*, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    compiler = build_compiler()
    blockers = build_blockers()
    examples = build_examples()
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "recipient_statuses": RECIPIENT_STATUSES,
        "send_gate_statuses": SEND_GATE_STATUSES,
        "delivery_statuses": DELIVERY_STATUSES,
        "readback_statuses": READBACK_STATUSES,
        "blocker_types": BLOCKER_TYPES,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "compiler": asdict(compiler),
        "email_delivery_blockers": [asdict(blocker) for blocker in blockers],
        "examples": examples,
        "capital_hilton_required_package": {
            "known": (
                "client: Capital Hilton",
                "workflow: capital_hilton_invoice_workflow",
                "draft type: INVOICE_FOLLOWUP_EMAIL",
                "recipient: Annette candidate/confirmed ref",
                "attachment: Winship-branded Excel/PDF invoice artifact ref",
                "official payment rail: Coupa/PO",
                "purpose: local records and payment follow-up",
            ),
            "operator_readback": (
                "OpenClaw has assembled a delivery package for the Capital Hilton invoice email. "
                "Nothing has been sent. The package still needs Guardian/operator approval before any future send adapter can act."
            ),
        },
        "machine_proof": {
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "email_delivery_performed": False,
            "email_send_performed": False,
            "mail_send_performed": False,
            "gmail_send_performed": False,
            "gmail_draft_created": False,
            "attachment_send_performed": False,
            "coupa_access_performed": False,
            "browser_access_performed": False,
            "approval_execution_performed": False,
            "workflow_run_performed": False,
            "agent_dispatch_performed": False,
            "external_action_performed": False,
            "credential_handling_performed": False,
            "raw_attachment_body_included": False,
            "raw_body_ingestion_performed": False,
            "mac_sync_import_performed": False,
            "swift_change_performed": False,
            "git_push_performed": False,
        },
        "operator_summary": (
            "OpenClaw can now assemble a safe email delivery package from draft, recipient, attachment, "
            "approval, send-gate, and proof refs. Nothing is sent, no draft is created, and future send remains gated."
        ),
        "next_safe_move": "Use this package as the review surface before any future Guardian/operator-approved send adapter.",
    }


def format_operator_markdown(payload: dict[str, Any]) -> str:
    capital = payload["examples"]["capital_hilton_complete_except_approval"]
    readback = capital["readback"]
    lines = [
        "# Email Delivery Package Compiler",
        "",
        "## Summary",
        payload["operator_summary"],
        "",
        "## Capital Hilton Package",
        f"- Status: {readback['status']}",
        f"- Message: {readback['operator_message']}",
        f"- Recipient: {readback['recipient_summary']}",
        f"- Draft: {readback['draft_summary']}",
        f"- Attachment: {readback['attachment_summary']}",
        f"- Approval: {readback['approval_status']}",
        f"- Next: {readback['next_safe_move']}",
        "",
        "## Blocked",
    ]
    for blocker in payload["email_delivery_blockers"]:
        lines.append(f"- {blocker['blocker_type']}: {blocker['elioperator_warning']}")
    lines += [
        "",
        "## Boundary",
        "No email send, no Mail send, no Gmail send, no Gmail draft creation, no attachment send, no Coupa access, no browser, no approval execution, no workflow run, no agent dispatch, no external action, no credential handling, no raw attachment body, no raw-body ingestion.",
    ]
    return "\n".join(lines) + "\n"


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def _summary(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> dict[str, Any]:
    return {
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "examples": tuple(payload["examples"].keys()),
        "blocker_count": len(payload["email_delivery_blockers"]),
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "json_export": str(export_root / JSON_EXPORT_NAME),
        "operator_export": str(export_root / OPERATOR_EXPORT_NAME),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Email Delivery Package Compiler read-model.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    args = parser.parse_args(argv)

    export_root = Path(args.export_root)
    payload = build_payload(generated_at=args.generated_at)
    write_exports(payload, export_root)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(stable_json(_summary(payload, export_root)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
