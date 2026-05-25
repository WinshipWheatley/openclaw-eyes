"""Invoice Delivery Completion Proof Aggregator v0.

This deterministic read-model decides whether OpenClaw may truthfully display
final invoice completion labels such as INVOICE_SENT or
INVOICE_SENT_AND_RECORDED. It aggregates receipt/proof refs only.

It does not execute workflows, send email, submit Coupa, open browsers, execute
approvals, write payment tracking, spawn visual artifacts, handle credentials,
ingest raw bodies, mutate Mission Control Swift, run Mac sync/import, or push.
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

SCHEMA_VERSION = "invoice_delivery_completion_proof_aggregator_v0"
READ_MODEL_ID = "invoice_delivery_completion_proof_aggregator"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_FINAL_COMPLETION_PROOF_AGGREGATOR_NO_EXECUTION"

COMPLETION_LABELS = (
    "INVOICE_SENT",
    "INVOICE_SENT_AND_RECORDED",
    "EMAIL_SENT",
    "COUPA_INVOICE_SUBMITTED",
    "PAYMENT_TRACKING_UPDATED",
    "UNKNOWN_FAIL_CLOSED",
)

RECEIPT_TYPES = (
    "EMAIL_SEND_RECEIPT",
    "EMAIL_ATTACHMENT_PROOF",
    "GMAIL_PROVIDER_MESSAGE_REF",
    "MAIL_PROVIDER_MESSAGE_REF",
    "COUPA_SUBMIT_RECEIPT",
    "COUPA_CONFIRMATION_PROOF",
    "INVOICE_ARTIFACT_SAVED_RECEIPT",
    "INVOICE_ARTIFACT_HASH_PROOF",
    "GUARDIAN_APPROVAL_RECEIPT",
    "OPERATOR_APPROVAL_RECEIPT",
    "PAYMENT_TRACKING_UPDATE_RECEIPT",
    "LOCAL_RECORD_SAVED_RECEIPT",
    "UNKNOWN",
)

READBACK_STATUSES = (
    "COMPLETION_CONFIRMED",
    "COMPLETION_BLOCKED_MISSING_EMAIL_PROOF",
    "COMPLETION_BLOCKED_MISSING_COUPA_PROOF",
    "COMPLETION_BLOCKED_MISSING_ARTIFACT_PROOF",
    "COMPLETION_BLOCKED_MISSING_APPROVAL_PROOF",
    "COMPLETION_BLOCKED_MISSING_PAYMENT_TRACKING",
    "COMPLETION_BLOCKED_NO_RECEIPTS",
    "UNKNOWN_FAIL_CLOSED",
)

VISUAL_ARTIFACT_TYPES = (
    "INVOICE_SENT_PROOF_CARD",
    "INVOICE_DELIVERY_TIMELINE",
    "PAYMENT_RAIL_STATUS",
    "BLOCKED_COMPLETION_CARD",
    "UNKNOWN",
)

BLOCKER_TYPES = (
    "COMPLETION_CLAIM_WITHOUT_EMAIL_RECEIPT",
    "COMPLETION_CLAIM_WITHOUT_COUPA_RECEIPT",
    "COMPLETION_CLAIM_WITHOUT_ARTIFACT_HASH",
    "COMPLETION_CLAIM_WITHOUT_APPROVAL",
    "COMPLETION_CLAIM_WITHOUT_LOCAL_RECORD",
    "STALE_PROOF",
    "RAW_PROVIDER_ID_EXPOSED",
    "RAW_PRIVATE_BODY_EXPOSED",
    "EXTERNAL_ACTION_ATTEMPTED",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_completion_write_allowed": False,
    "live_email_send_allowed": False,
    "live_mail_send_allowed": False,
    "live_gmail_send_allowed": False,
    "live_coupa_access_allowed": False,
    "live_coupa_submit_allowed": False,
    "live_browser_allowed": False,
    "live_payment_tracking_write_allowed": False,
    "live_visual_artifact_spawn_allowed": False,
    "live_external_action_allowed": False,
    "live_workflow_run_allowed": False,
    "live_agent_dispatch_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "live_approval_execution_allowed": False,
    "live_provider_call_allowed": False,
    "live_secret_reveal_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

BLOCKED_ACTIONS = (
    "completion write",
    "email send",
    "Mail/Gmail send",
    "Coupa access or submit",
    "browser automation",
    "payment tracking write",
    "visual artifact spawn",
    "external action",
    "workflow run",
    "agent dispatch",
    "credential handling",
)

FULL_COMPLETION_RECEIPTS = (
    "EMAIL_SEND_RECEIPT",
    "EMAIL_ATTACHMENT_PROOF",
    "GMAIL_PROVIDER_MESSAGE_REF",
    "COUPA_SUBMIT_RECEIPT",
    "COUPA_CONFIRMATION_PROOF",
    "INVOICE_ARTIFACT_SAVED_RECEIPT",
    "INVOICE_ARTIFACT_HASH_PROOF",
    "GUARDIAN_APPROVAL_RECEIPT",
    "OPERATOR_APPROVAL_RECEIPT",
    "PAYMENT_TRACKING_UPDATE_RECEIPT",
    "LOCAL_RECORD_SAVED_RECEIPT",
)

RECEIPT_REF_BY_TYPE = {
    "EMAIL_SEND_RECEIPT": "email_send_receipt_ref:capital_hilton_annette_invoice_sent_v0",
    "EMAIL_ATTACHMENT_PROOF": "email_attachment_proof_ref:capital_hilton_invoice_pdf_attached_v0",
    "GMAIL_PROVIDER_MESSAGE_REF": "provider_message_ref:gmail_capital_hilton_safe_ref_v0",
    "MAIL_PROVIDER_MESSAGE_REF": "provider_message_ref:mail_capital_hilton_safe_ref_v0",
    "COUPA_SUBMIT_RECEIPT": "coupa_submit_receipt_ref:capital_hilton_invoice_submitted_v0",
    "COUPA_CONFIRMATION_PROOF": "coupa_confirmation_ref:capital_hilton_submission_confirmation_v0",
    "INVOICE_ARTIFACT_SAVED_RECEIPT": "invoice_artifact_saved_receipt_ref:capital_hilton_invoice_2026-05-25",
    "INVOICE_ARTIFACT_HASH_PROOF": "artifact_hash_ref:capital_hilton_invoice_pdf_v0",
    "GUARDIAN_APPROVAL_RECEIPT": "guardian_approval_receipt_ref:capital_hilton_invoice_delivery_v0",
    "OPERATOR_APPROVAL_RECEIPT": "operator_approval_receipt_ref:capital_hilton_exact_approval_v0",
    "PAYMENT_TRACKING_UPDATE_RECEIPT": "payment_tracking_update_receipt_ref:capital_hilton_invoice_marked_sent_v0",
    "LOCAL_RECORD_SAVED_RECEIPT": "local_record_saved_receipt_ref:capital_hilton_invoice_delivery_packet_v0",
}

PROOF_SUMMARY_BY_TYPE = {
    "EMAIL_SEND_RECEIPT": "Email send receipt exists.",
    "EMAIL_ATTACHMENT_PROOF": "Attachment proof shows the invoice artifact was included.",
    "GMAIL_PROVIDER_MESSAGE_REF": "Provider message is represented by a protected/safe ref.",
    "MAIL_PROVIDER_MESSAGE_REF": "Mail provider message is represented by a protected/safe ref.",
    "COUPA_SUBMIT_RECEIPT": "Coupa submit receipt exists.",
    "COUPA_CONFIRMATION_PROOF": "Coupa confirmation proof exists.",
    "INVOICE_ARTIFACT_SAVED_RECEIPT": "Invoice artifact saved receipt exists.",
    "INVOICE_ARTIFACT_HASH_PROOF": "Invoice artifact hash/fingerprint proof exists.",
    "GUARDIAN_APPROVAL_RECEIPT": "Guardian approval receipt exists.",
    "OPERATOR_APPROVAL_RECEIPT": "Exact operator approval receipt exists.",
    "PAYMENT_TRACKING_UPDATE_RECEIPT": "Payment tracking update receipt exists.",
    "LOCAL_RECORD_SAVED_RECEIPT": "Local record saved receipt exists.",
}


@dataclass(frozen=True)
class InvoiceDeliveryCompletionProofAggregator:
    aggregator_id: str
    doctrine: tuple[str, ...]
    source_workflow_policy: tuple[str, ...]
    receipt_policy: tuple[str, ...]
    proof_policy: tuple[str, ...]
    completion_label_policy: tuple[str, ...]
    false_completion_block_policy: tuple[str, ...]
    final_readback_policy: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class InvoiceDeliveryCompletionProofSet:
    proof_set_id: str
    source_workflow_ref: str
    client_ref: str
    tenant_ref: str
    delivery_goal: str
    required_receipts: tuple[str, ...]
    available_receipts: tuple[str, ...]
    missing_receipts: tuple[str, ...]
    required_proofs: tuple[str, ...]
    available_proofs: tuple[str, ...]
    missing_proofs: tuple[str, ...]
    completion_allowed: bool
    completion_label: str
    next_safe_move: str


@dataclass(frozen=True)
class CompletionReceiptRequirement:
    requirement_id: str
    proof_set_ref: str
    receipt_type: str
    required: bool
    receipt_ref: str
    present: bool
    stale: bool
    proof_summary: str
    missing_reason: str
    how_to_fix: str
    next_safe_move: str


@dataclass(frozen=True)
class InvoiceCompletionReadback:
    readback_id: str
    proof_set_ref: str
    status: str
    operator_headline: str
    operator_message: str
    completed_items: tuple[str, ...]
    missing_items: tuple[str, ...]
    proof_bullets: tuple[str, ...]
    blocked_completion_claims: tuple[str, ...]
    how_to_fix: str
    next_safe_move: str


@dataclass(frozen=True)
class FinalVisualReadbackTarget:
    visual_target_id: str
    completion_readback_ref: str
    should_spawn_visual_artifact: bool
    visual_artifact_type: str
    source_truth_refs: tuple[str, ...]
    proof_bullets: tuple[str, ...]
    target_surface: str
    factual_priority: int
    style_priority: int
    next_safe_move: str


@dataclass(frozen=True)
class CompletionProofBlocker:
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


def build_aggregator() -> InvoiceDeliveryCompletionProofAggregator:
    return InvoiceDeliveryCompletionProofAggregator(
        aggregator_id="invoice_delivery_completion_proof_aggregator_v0",
        doctrine=(
            "Aggregator reads and compares proof refs only.",
            "Aggregator does not execute actions, create missing receipts, or write completion state.",
            "Package readiness and dry-run readiness are not completion proof.",
            "Completion requires actual receipt/proof refs.",
            "False completion claims fail closed.",
        ),
        source_workflow_policy=(
            "Proof sets bind to one workflow, client, and tenant.",
            "Capital Hilton is the v0 proof case.",
            "Cross-workflow completion claims are not inferred.",
        ),
        receipt_policy=(
            "Each completion label declares required receipt types.",
            "Provider ids are safe/protected refs only.",
            "Missing receipts remain missing; this lane does not fabricate them.",
        ),
        proof_policy=(
            "INVOICE_SENT requires email send and attachment proof.",
            "COUPA_INVOICE_SUBMITTED requires Coupa submit and confirmation proof.",
            "INVOICE_SENT_AND_RECORDED requires all required channel proofs and local record proof.",
            "Payment tracking requires a payment-tracking receipt if included.",
        ),
        completion_label_policy=(
            "COMPLETION_CONFIRMED is available only when all required receipts/proofs are present.",
            "Blocked labels remain visible as blocked claims, not truth.",
            "Never say sent unless the relevant send receipt exists.",
        ),
        false_completion_block_policy=(
            "Invoice sent claims without email receipt fail closed.",
            "Coupa submitted claims without Coupa receipt fail closed.",
            "Recorded claims without local record receipt fail closed.",
            "Approval-only proof never equals completion.",
        ),
        final_readback_policy=(
            "Readbacks are human-readable.",
            "Blocked states include how_to_fix.",
            "Final proof bullets must cite receipt/proof refs, not raw provider payloads.",
        ),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Use this aggregator only after send/submit/local record/payment receipts exist.",
    )


def _required_proofs_for(receipts: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(PROOF_SUMMARY_BY_TYPE[receipt_type] for receipt_type in receipts if receipt_type in PROOF_SUMMARY_BY_TYPE)


def _available_proofs_for(receipts: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        f"{receipt_type}:{RECEIPT_REF_BY_TYPE[receipt_type]}"
        for receipt_type in receipts
        if receipt_type in RECEIPT_REF_BY_TYPE
    )


def build_proof_set(
    *,
    proof_set_id: str,
    available_receipts: tuple[str, ...],
    required_receipts: tuple[str, ...] = FULL_COMPLETION_RECEIPTS,
    completion_label: str = "INVOICE_SENT_AND_RECORDED",
) -> InvoiceDeliveryCompletionProofSet:
    missing_receipts = tuple(receipt for receipt in required_receipts if receipt not in available_receipts)
    required_proofs = _required_proofs_for(required_receipts)
    available_proofs = _available_proofs_for(available_receipts)
    missing_proofs = tuple(PROOF_SUMMARY_BY_TYPE[receipt] for receipt in missing_receipts if receipt in PROOF_SUMMARY_BY_TYPE)
    completion_allowed = not missing_receipts and completion_label != "UNKNOWN_FAIL_CLOSED"
    return InvoiceDeliveryCompletionProofSet(
        proof_set_id=proof_set_id,
        source_workflow_ref="capital_hilton_invoice_workflow",
        client_ref="client_ref:capital_hilton",
        tenant_ref="tenant_ref:winship",
        delivery_goal="Complete Capital Hilton invoice delivery proof for local records, email follow-up, Coupa payment rail, and payment tracking.",
        required_receipts=required_receipts,
        available_receipts=available_receipts,
        missing_receipts=missing_receipts,
        required_proofs=required_proofs,
        available_proofs=available_proofs,
        missing_proofs=missing_proofs,
        completion_allowed=completion_allowed,
        completion_label=completion_label,
        next_safe_move=(
            "Completion is proof-backed; display final readback only."
            if completion_allowed
            else "Collect the missing receipt/proof refs before claiming completion."
        ),
    )


def build_requirements(proof_set: InvoiceDeliveryCompletionProofSet) -> tuple[CompletionReceiptRequirement, ...]:
    rows: list[CompletionReceiptRequirement] = []
    for receipt_type in proof_set.required_receipts:
        present = receipt_type in proof_set.available_receipts
        receipt_ref = RECEIPT_REF_BY_TYPE.get(receipt_type, "") if present else ""
        summary = PROOF_SUMMARY_BY_TYPE.get(receipt_type, "Unknown proof requirement.")
        missing_reason = "" if present else f"{receipt_type} is required before {proof_set.completion_label} can be claimed."
        fix = "Receipt/proof ref is present." if present else f"Produce or attach {receipt_type} from the governed lane, then rerun completion aggregation."
        rows.append(
            CompletionReceiptRequirement(
                requirement_id=_stable_id("completion_receipt_requirement", proof_set.proof_set_id, receipt_type),
                proof_set_ref=proof_set.proof_set_id,
                receipt_type=receipt_type,
                required=True,
                receipt_ref=receipt_ref,
                present=present,
                stale=False,
                proof_summary=summary,
                missing_reason=missing_reason,
                how_to_fix=fix,
                next_safe_move=fix,
            )
        )
    return tuple(rows)


def _completed_items(available: tuple[str, ...]) -> tuple[str, ...]:
    completed: list[str] = []
    if {"EMAIL_SEND_RECEIPT", "EMAIL_ATTACHMENT_PROOF", "GMAIL_PROVIDER_MESSAGE_REF"}.issubset(set(available)):
        completed.append("EMAIL_SENT")
    if {"COUPA_SUBMIT_RECEIPT", "COUPA_CONFIRMATION_PROOF"}.issubset(set(available)):
        completed.append("COUPA_INVOICE_SUBMITTED")
    if {"INVOICE_ARTIFACT_SAVED_RECEIPT", "INVOICE_ARTIFACT_HASH_PROOF", "LOCAL_RECORD_SAVED_RECEIPT"}.issubset(set(available)):
        completed.append("LOCAL_RECORD_SAVED")
    if "PAYMENT_TRACKING_UPDATE_RECEIPT" in available:
        completed.append("PAYMENT_TRACKING_UPDATED")
    return tuple(completed)


def _readback_status(proof_set: InvoiceDeliveryCompletionProofSet) -> str:
    missing = set(proof_set.missing_receipts)
    if proof_set.completion_allowed:
        return "COMPLETION_CONFIRMED"
    if not proof_set.available_receipts:
        return "COMPLETION_BLOCKED_NO_RECEIPTS"
    if missing.intersection({"EMAIL_SEND_RECEIPT", "EMAIL_ATTACHMENT_PROOF", "GMAIL_PROVIDER_MESSAGE_REF", "MAIL_PROVIDER_MESSAGE_REF"}):
        return "COMPLETION_BLOCKED_MISSING_EMAIL_PROOF"
    if missing.intersection({"COUPA_SUBMIT_RECEIPT", "COUPA_CONFIRMATION_PROOF"}):
        return "COMPLETION_BLOCKED_MISSING_COUPA_PROOF"
    if missing.intersection({"INVOICE_ARTIFACT_SAVED_RECEIPT", "INVOICE_ARTIFACT_HASH_PROOF", "LOCAL_RECORD_SAVED_RECEIPT"}):
        return "COMPLETION_BLOCKED_MISSING_ARTIFACT_PROOF"
    if missing.intersection({"GUARDIAN_APPROVAL_RECEIPT", "OPERATOR_APPROVAL_RECEIPT"}):
        return "COMPLETION_BLOCKED_MISSING_APPROVAL_PROOF"
    if "PAYMENT_TRACKING_UPDATE_RECEIPT" in missing:
        return "COMPLETION_BLOCKED_MISSING_PAYMENT_TRACKING"
    return "UNKNOWN_FAIL_CLOSED"


def build_readback(
    proof_set: InvoiceDeliveryCompletionProofSet,
    *,
    false_completion_claim: str = "",
) -> InvoiceCompletionReadback:
    status = _readback_status(proof_set)
    completed = _completed_items(proof_set.available_receipts)
    missing_items = proof_set.missing_receipts
    blocked_claims: list[str] = []
    if false_completion_claim:
        blocked_claims.append(false_completion_claim)
    if "EMAIL_SEND_RECEIPT" in missing_items or "EMAIL_ATTACHMENT_PROOF" in missing_items:
        blocked_claims.append("INVOICE_SENT")
    if "COUPA_SUBMIT_RECEIPT" in missing_items or "COUPA_CONFIRMATION_PROOF" in missing_items:
        blocked_claims.append("COUPA_INVOICE_SUBMITTED")
    if "LOCAL_RECORD_SAVED_RECEIPT" in missing_items:
        blocked_claims.append("INVOICE_SENT_AND_RECORDED")

    if status == "COMPLETION_CONFIRMED":
        headline = "INVOICE SENT AND RECORDED"
        proof_bullets = (
            "Email sent to Annette with Winship-branded invoice attachment.",
            "Coupa invoice submitted/confirmed from PO if required.",
            "Invoice artifact saved with date.",
            "Guardian/operator approval receipts present.",
            "Payment tracking updated if required.",
        )
        message = "INVOICE SENT AND RECORDED. Proofs show: " + " ".join(proof_bullets)
        fix = "No fix needed; preserve proof refs and final readback."
    elif status == "COMPLETION_BLOCKED_NO_RECEIPTS":
        headline = "Invoice completion blocked: no receipts"
        proof_bullets = ("No final send, submit, approval, local record, or payment tracking receipts are present.",)
        message = (
            "OpenClaw cannot mark the Capital Hilton invoice as sent yet. "
            "The final proof receipts are missing: " + ", ".join(missing_items) + ". "
            "Nothing new was sent, submitted, or recorded by this check."
        )
        fix = "Complete the governed send/submit/local-record lanes and attach their receipt refs, then rerun this aggregator."
    elif status == "COMPLETION_BLOCKED_MISSING_EMAIL_PROOF":
        headline = "Invoice completion blocked: email proof missing"
        proof_bullets = tuple(f"Missing: {item}" for item in missing_items if item in {"EMAIL_SEND_RECEIPT", "EMAIL_ATTACHMENT_PROOF", "GMAIL_PROVIDER_MESSAGE_REF", "MAIL_PROVIDER_MESSAGE_REF"})
        message = "OpenClaw cannot claim INVOICE_SENT because email send and attachment proof refs are missing."
        fix = "Attach the email send receipt and attachment proof from the gated email send lane."
    elif status == "COMPLETION_BLOCKED_MISSING_COUPA_PROOF":
        headline = "Invoice completion blocked: Coupa proof missing"
        proof_bullets = tuple(f"Missing: {item}" for item in missing_items if item in {"COUPA_SUBMIT_RECEIPT", "COUPA_CONFIRMATION_PROOF"})
        message = "OpenClaw cannot claim INVOICE_SENT_AND_RECORDED because Coupa submit/confirmation proof is missing."
        fix = "Attach the Coupa submit receipt and confirmation proof from the gated Coupa submit lane."
    elif status == "COMPLETION_BLOCKED_MISSING_ARTIFACT_PROOF":
        headline = "Invoice completion blocked: artifact/local record proof missing"
        proof_bullets = tuple(f"Missing: {item}" for item in missing_items if item in {"INVOICE_ARTIFACT_SAVED_RECEIPT", "INVOICE_ARTIFACT_HASH_PROOF", "LOCAL_RECORD_SAVED_RECEIPT"})
        message = "OpenClaw cannot claim final invoice recording because artifact/hash/local-record proof is missing."
        fix = "Attach invoice artifact saved/hash proof and local record saved receipt."
    elif status == "COMPLETION_BLOCKED_MISSING_APPROVAL_PROOF":
        headline = "Invoice completion blocked: approval proof missing"
        proof_bullets = tuple(f"Missing: {item}" for item in missing_items if item in {"GUARDIAN_APPROVAL_RECEIPT", "OPERATOR_APPROVAL_RECEIPT"})
        message = "OpenClaw cannot claim completion because Guardian/operator approval proof is missing."
        fix = "Attach Guardian and exact operator approval receipt refs."
    elif status == "COMPLETION_BLOCKED_MISSING_PAYMENT_TRACKING":
        headline = "Invoice completion blocked: payment tracking proof missing"
        proof_bullets = ("Payment tracking update receipt is missing.",)
        message = "OpenClaw cannot claim recorded completion because payment tracking proof is missing."
        fix = "Attach payment tracking update receipt if payment tracking is required."
    else:
        headline = "Invoice completion failed closed"
        proof_bullets = ("Unknown proof aggregation state.",)
        message = "OpenClaw cannot prove a safe completion state."
        fix = "Regenerate with scoped receipt refs."

    return InvoiceCompletionReadback(
        readback_id=_stable_id("invoice_completion_readback", proof_set.proof_set_id, status, false_completion_claim),
        proof_set_ref=proof_set.proof_set_id,
        status=status,
        operator_headline=headline,
        operator_message=message,
        completed_items=completed,
        missing_items=missing_items,
        proof_bullets=proof_bullets,
        blocked_completion_claims=tuple(dict.fromkeys(blocked_claims)),
        how_to_fix=fix,
        next_safe_move=fix,
    )


def build_visual_target(
    readback: InvoiceCompletionReadback,
    proof_set: InvoiceDeliveryCompletionProofSet,
) -> FinalVisualReadbackTarget:
    complete = readback.status == "COMPLETION_CONFIRMED"
    return FinalVisualReadbackTarget(
        visual_target_id=_stable_id("final_visual_readback_target", readback.readback_id),
        completion_readback_ref=readback.readback_id,
        should_spawn_visual_artifact=complete,
        visual_artifact_type="INVOICE_SENT_PROOF_CARD" if complete else "BLOCKED_COMPLETION_CARD",
        source_truth_refs=proof_set.available_proofs,
        proof_bullets=readback.proof_bullets,
        target_surface="Mac chat completion readback future target",
        factual_priority=10,
        style_priority=2,
        next_safe_move=(
            "A future visual lane may render a proof card from these refs; no live render happens here."
            if complete
            else "Do not spawn visual artifact until proof-backed completion exists."
        ),
    )


def build_blockers() -> tuple[CompletionProofBlocker, ...]:
    return (
        CompletionProofBlocker("completion_blocker_email_receipt", "COMPLETION_CLAIM_WITHOUT_EMAIL_RECEIPT", "INVOICE_SENT is claimed without email send receipt and attachment proof.", "critical", "Email completion claim lacks receipt proof.", True, "Attach email send receipt and attachment proof."),
        CompletionProofBlocker("completion_blocker_coupa_receipt", "COMPLETION_CLAIM_WITHOUT_COUPA_RECEIPT", "Coupa completion is claimed without submit/confirmation proof.", "critical", "Coupa completion claim lacks receipt proof.", True, "Attach Coupa submit and confirmation proof refs."),
        CompletionProofBlocker("completion_blocker_artifact_hash", "COMPLETION_CLAIM_WITHOUT_ARTIFACT_HASH", "Completion is claimed without invoice artifact hash proof.", "high", "Artifact hash proof is missing.", True, "Attach invoice artifact hash/fingerprint proof."),
        CompletionProofBlocker("completion_blocker_approval", "COMPLETION_CLAIM_WITHOUT_APPROVAL", "Completion is claimed without Guardian/operator approval receipts.", "critical", "Approval proof is missing.", True, "Attach Guardian and exact operator approval receipts."),
        CompletionProofBlocker("completion_blocker_local_record", "COMPLETION_CLAIM_WITHOUT_LOCAL_RECORD", "Recorded completion is claimed without local record receipt.", "high", "Local record proof is missing.", True, "Attach local record saved receipt."),
        CompletionProofBlocker("completion_blocker_stale_proof", "STALE_PROOF", "A required receipt/proof is stale.", "high", "Stale proof blocks completion.", True, "Refresh or replace stale proof refs."),
        CompletionProofBlocker("completion_blocker_raw_provider_id", "RAW_PROVIDER_ID_EXPOSED", "Raw provider id appears instead of protected/safe ref.", "critical", "Raw provider id exposure is blocked.", True, "Use protected provider message refs only."),
        CompletionProofBlocker("completion_blocker_raw_body", "RAW_PRIVATE_BODY_EXPOSED", "Raw private body appears in proof/readback.", "critical", "Raw private body exposure is blocked.", True, "Use receipt refs and safe summaries only."),
        CompletionProofBlocker("completion_blocker_external_action", "EXTERNAL_ACTION_ATTEMPTED", "Aggregator attempts send, submit, browser, payment, visual spawn, or workflow action.", "critical", "External action is blocked.", True, "Return proof/readback only."),
        CompletionProofBlocker("completion_blocker_unknown", "UNKNOWN_FAIL_CLOSED", "Unknown completion proof state.", "high", "Unknown completion state fails closed.", True, "Ask for scoped receipt refs."),
    )


def _bundle(
    proof_set: InvoiceDeliveryCompletionProofSet,
    *,
    false_completion_claim: str = "",
) -> dict[str, Any]:
    requirements = build_requirements(proof_set)
    readback = build_readback(proof_set, false_completion_claim=false_completion_claim)
    visual_target = build_visual_target(readback, proof_set)
    return {
        "proof_set": asdict(proof_set),
        "receipt_requirements": tuple(asdict(requirement) for requirement in requirements),
        "readback": asdict(readback),
        "visual_target": asdict(visual_target),
        "channel_completion": {
            "EMAIL_SENT": "EMAIL_SENT" in readback.completed_items,
            "COUPA_INVOICE_SUBMITTED": "COUPA_INVOICE_SUBMITTED" in readback.completed_items,
            "PAYMENT_TRACKING_UPDATED": "PAYMENT_TRACKING_UPDATED" in readback.completed_items,
            "INVOICE_SENT_AND_RECORDED": proof_set.completion_allowed,
        },
    }


def build_examples() -> dict[str, Any]:
    not_complete = build_proof_set(
        proof_set_id="completion_proof_set_capital_hilton_not_complete_v0",
        available_receipts=(),
    )
    email_only = build_proof_set(
        proof_set_id="completion_proof_set_capital_hilton_email_only_v0",
        available_receipts=(
            "EMAIL_SEND_RECEIPT",
            "EMAIL_ATTACHMENT_PROOF",
            "GMAIL_PROVIDER_MESSAGE_REF",
            "INVOICE_ARTIFACT_SAVED_RECEIPT",
            "INVOICE_ARTIFACT_HASH_PROOF",
            "GUARDIAN_APPROVAL_RECEIPT",
            "OPERATOR_APPROVAL_RECEIPT",
            "LOCAL_RECORD_SAVED_RECEIPT",
        ),
    )
    coupa_only = build_proof_set(
        proof_set_id="completion_proof_set_capital_hilton_coupa_only_v0",
        available_receipts=(
            "COUPA_SUBMIT_RECEIPT",
            "COUPA_CONFIRMATION_PROOF",
            "INVOICE_ARTIFACT_SAVED_RECEIPT",
            "INVOICE_ARTIFACT_HASH_PROOF",
            "GUARDIAN_APPROVAL_RECEIPT",
            "OPERATOR_APPROVAL_RECEIPT",
            "LOCAL_RECORD_SAVED_RECEIPT",
        ),
    )
    complete = build_proof_set(
        proof_set_id="completion_proof_set_capital_hilton_complete_v0",
        available_receipts=FULL_COMPLETION_RECEIPTS,
    )
    false_claim = build_proof_set(
        proof_set_id="completion_proof_set_capital_hilton_false_invoice_sent_claim_v0",
        available_receipts=("INVOICE_ARTIFACT_SAVED_RECEIPT", "INVOICE_ARTIFACT_HASH_PROOF"),
    )
    return {
        "capital_hilton_not_complete": _bundle(not_complete),
        "capital_hilton_email_only_incomplete": _bundle(email_only),
        "capital_hilton_coupa_only_incomplete": _bundle(coupa_only),
        "capital_hilton_fully_complete_fixture": _bundle(complete),
        "false_completion_claim_blocked": _bundle(false_claim, false_completion_claim="Invoice sent"),
    }


def build_payload(generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    aggregator = build_aggregator()
    examples = build_examples()
    blockers = build_blockers()
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "completion_labels": COMPLETION_LABELS,
        "receipt_types": RECEIPT_TYPES,
        "readback_statuses": READBACK_STATUSES,
        "visual_artifact_types": VISUAL_ARTIFACT_TYPES,
        "blocker_types": BLOCKER_TYPES,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "aggregator": asdict(aggregator),
        "completion_proof_blockers": tuple(asdict(blocker) for blocker in blockers),
        "examples": examples,
        "capital_hilton_blocked_operator_readback": (
            "OpenClaw cannot mark the Capital Hilton invoice as sent yet. "
            "The final proof receipts are missing: [missing items]. Nothing new was sent, submitted, or recorded by this check."
        ),
        "capital_hilton_complete_operator_readback": "INVOICE SENT AND RECORDED. Proofs show: [proof bullets].",
        "machine_proof": {
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "completion_write_performed": False,
            "email_send_performed": False,
            "mail_send_performed": False,
            "gmail_send_performed": False,
            "coupa_access_performed": False,
            "coupa_submit_performed": False,
            "browser_access_performed": False,
            "payment_tracking_write_performed": False,
            "visual_artifact_spawn_performed": False,
            "external_action_performed": False,
            "workflow_run_performed": False,
            "agent_dispatch_performed": False,
            "credential_handling_performed": False,
            "raw_body_ingestion_performed": False,
            "mac_sync_import_performed": False,
            "swift_change_performed": False,
            "git_push_performed": False,
        },
        "operator_summary": (
            "OpenClaw can now aggregate final invoice delivery proof refs and decide whether INVOICE_SENT or "
            "INVOICE_SENT_AND_RECORDED may be displayed. Missing receipts block completion."
        ),
        "next_safe_move": "Attach real send/submit/artifact/approval/local-record/payment receipts, then rerun this proof aggregator.",
    }


def format_operator_markdown(payload: dict[str, Any]) -> str:
    not_complete = payload["examples"]["capital_hilton_not_complete"]["readback"]
    email_only = payload["examples"]["capital_hilton_email_only_incomplete"]["readback"]
    coupa_only = payload["examples"]["capital_hilton_coupa_only_incomplete"]["readback"]
    complete = payload["examples"]["capital_hilton_fully_complete_fixture"]["readback"]
    false_claim = payload["examples"]["false_completion_claim_blocked"]["readback"]
    false_claims = ", ".join(false_claim["blocked_completion_claims"])
    lines = [
        "# Invoice Delivery Completion Proof Aggregator",
        "",
        "## Summary",
        payload["operator_summary"],
        "",
        "## Capital Hilton",
        f"- Not complete: {not_complete['status']} - {not_complete['operator_message']}",
        f"- Email-only: {email_only['status']} - {email_only['operator_message']}",
        f"- Coupa-only: {coupa_only['status']} - {coupa_only['operator_message']}",
        f"- Fully complete fixture: {complete['status']} - {complete['operator_message']}",
        f"- False claim: {false_claim['status']} - {false_claims}",
        "",
        "## Blockers",
    ]
    for blocker in payload["completion_proof_blockers"]:
        lines.append(f"- {blocker['blocker_type']}: {blocker['elioperator_warning']}")
    lines += [
        "",
        "## Boundary",
        "No completion write, no email send, no Mail/Gmail send, no Coupa access/submit, no browser, no payment tracking write, no visual artifact spawn, no external action, no workflow run, no agent dispatch, no credential handling, no raw-body ingestion.",
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
    complete = payload["examples"]["capital_hilton_fully_complete_fixture"]["readback"]
    not_complete = payload["examples"]["capital_hilton_not_complete"]["readback"]
    return {
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "not_complete_status": not_complete["status"],
        "complete_fixture_status": complete["status"],
        "blocker_count": len(payload["completion_proof_blockers"]),
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "json_export": str(export_root / JSON_EXPORT_NAME),
        "operator_export": str(export_root / OPERATOR_EXPORT_NAME),
    }


def build_and_export(
    *,
    generated_at: str = DEFAULT_GENERATED_AT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    format_name: str = "summary",
) -> dict[str, Any]:
    payload = build_payload(generated_at=generated_at)
    write_exports(payload, export_root)
    return payload if format_name == "json" else _summary(payload, export_root)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export invoice delivery completion proof aggregator.")
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = build_and_export(
        generated_at=args.generated_at,
        export_root=Path(args.export_root),
        format_name=args.format,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
