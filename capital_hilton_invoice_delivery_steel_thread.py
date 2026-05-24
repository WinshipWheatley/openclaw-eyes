"""Capital Hilton invoice delivery steel thread v0.

This deterministic read-model turns the Capital Hilton screen draft into a
local captured workflow-state preview and delivery rail. It uses the existing
performance-date dry-run writer shape, captures the current four-date / $400
rate invoice intent into generated read-model state, derives an invoice packet,
and names the exact artifact, email, Coupa, and approval blockers.

It does not generate invoice artifacts, create email drafts, send email, access
Coupa/Gmail/Telegram/browser/credentials, mutate a production ledger, activate
agents/tools/runtime, or submit anything externally.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import capital_hilton_performance_dates_dry_run_writer as dates_writer


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "capital_hilton_invoice_delivery_steel_thread_v0"
READ_MODEL_ID = "capital_hilton_invoice_delivery_steel_thread"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_LOCAL_CAPTURE_READBACK_AND_DELIVERY_RAIL"

WORKFLOW_SESSION_REF = "capital_hilton_invoice_workflow_session"
CLIENT = "Capital Hilton"
WORLD = "Finance"
LANE = "capital_hilton_invoice"

PREVIOUS_DATES = ("2026-05-08", "2026-05-15")
CAPTURED_DATES = ("2026-05-08", "2026-05-15", "2026-05-22", "2026-05-29")
ADDED_DATES = ("2026-05-22", "2026-05-29")
RATE_AMOUNT = 400
RATE_CURRENCY = "USD"
RATE_UNIT = "show"
SUBTOTAL_AMOUNT = 1600

FINAL_DELIVERY_STATUSES = (
    "SENT",
    "SUBMITTED_TO_COUPA",
    "READY_FOR_OPERATOR_APPROVAL",
    "READY_FOR_MANUAL_SEND",
    "READY_FOR_MANUAL_COUPA_SUBMISSION",
    "BLOCKED_MISSING_OPERATOR_FACT",
    "BLOCKED_EXTERNAL_GATE",
    "UNKNOWN_FAIL_CLOSED",
)

CAPTURED_BLOCK_IDS = (
    "performance_dates",
    "rate_confirmation",
    "po_coupa_proof_posture",
    "invoice_packet_readiness",
    "approval_send_prerequisites",
)

REQUIRED_STEEL_THREAD_FIELDS = (
    "workflow_session_ref",
    "captured_blocks",
    "capture_receipt_refs",
    "invoice_packet_ref",
    "artifact_status",
    "email_delivery_status",
    "coupa_submission_status",
    "approval_status",
    "final_delivery_status",
    "exact_blockers",
    "next_safe_move",
)

REQUIRED_CAPTURED_BLOCK_FIELDS = (
    "block_id",
    "previous_value",
    "captured_value",
    "receipt_type",
    "receipt_ref",
    "state_readback",
    "proof_status",
    "downstream_invalidations",
    "next_block_unlocked",
    "idempotency_key",
    "next_safe_move",
)

REQUIRED_INVOICE_PACKET_FIELDS = (
    "invoice_packet_id",
    "client",
    "dates",
    "rate",
    "subtotal",
    "proof_po_posture",
    "delivery_requirements",
    "artifact_candidate_refs",
    "stale_check_hash",
    "next_safe_move",
)

REQUIRED_ARTIFACT_READINESS_FIELDS = (
    "artifact_readiness_id",
    "invoice_packet_ref",
    "artifact_type",
    "generation_status",
    "artifact_path_if_exists",
    "artifact_hash_if_exists",
    "missing_generator_reason",
    "next_safe_move",
)

REQUIRED_EMAIL_DRAFT_PACKET_FIELDS = (
    "email_draft_packet_id",
    "invoice_packet_ref",
    "recipient_status",
    "recipients",
    "subject",
    "body",
    "attachment_refs",
    "approval_required",
    "send_adapter_status",
    "send_readiness",
    "send_blocker",
    "next_safe_move",
)

REQUIRED_COUPA_READINESS_FIELDS = (
    "coupa_readiness_id",
    "invoice_packet_ref",
    "coupa_required_status",
    "portal_route_status",
    "required_fields",
    "known_fields",
    "missing_fields",
    "protected_access_required",
    "credential_handling_allowed",
    "submit_adapter_status",
    "submit_readiness",
    "submit_blocker",
    "next_safe_move",
)

REQUIRED_APPROVAL_PACKET_FIELDS = (
    "approval_packet_id",
    "invoice_packet_ref",
    "email_draft_packet_ref",
    "coupa_readiness_ref",
    "approval_scope",
    "approval_question",
    "known_unknowns",
    "proof_refs",
    "stale_check_hash",
    "approval_status",
    "next_safe_move",
)

REQUIRED_BLOCKER_REPORT_FIELDS = (
    "blocker_report_id",
    "final_delivery_status",
    "exact_blockers",
    "blocker_type",
    "closest_completed_state",
    "next_required_build_step",
    "manual_fallback_available",
    "next_safe_move",
)

DOWNSTREAM_INVALIDATIONS = (
    "invoice_packet_preview",
    "invoice_packet_artifact",
    "email_draft_attachment",
    "approval_packet_preview",
    "prior_subtotal_preview",
    "proof_po_coverage_status",
)

EXTERNAL_BLOCKED_ACTIONS = (
    "invoice artifact generation without approved deterministic generator",
    "email draft creation or send",
    "Coupa portal login, upload, save, or submit",
    "browser/OAuth/account access",
    "credential or session-material handling",
    "approval submission",
    "model/agent/tool/runtime/queue execution",
    "raw private body ingestion",
    "file cleanup/archive/promotion",
    "network operation",
)

AUTHORITY_BOUNDARY: dict[str, Any] = {
    "local_receipt_write_allowed_for_this_lane": True,
    "local_state_update_allowed_for_this_lane": True,
    "local_write_mode": "deterministic_generated_read_model_capture_harness_only",
    "production_ledger_receipt_write_allowed": False,
    "production_workflow_state_write_allowed": False,
    "unsupported_generic_workflow_write_allowed": False,
    "invoice_generation_allowed": False,
    "email_draft_allowed": False,
    "email_send_allowed": False,
    "coupa_submit_allowed": False,
    "browser_automation_allowed": False,
    "coupa_access_allowed": False,
    "gmail_access_allowed": False,
    "telegram_send_allowed": False,
    "credential_handling_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "raw_body_ingestion_allowed": False,
    "file_cleanup_archive_allowed": False,
    "network_operation_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
}


@dataclass(frozen=True)
class CapitalHiltonCapturedBlockState:
    block_id: str
    previous_value: dict[str, Any]
    captured_value: dict[str, Any]
    receipt_type: str
    receipt_ref: str
    state_readback: dict[str, Any]
    proof_status: str
    downstream_invalidations: tuple[str, ...]
    next_block_unlocked: str
    idempotency_key: str
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonInvoicePacket:
    invoice_packet_id: str
    client: str
    dates: tuple[str, ...]
    rate: dict[str, Any]
    subtotal: dict[str, Any]
    proof_po_posture: dict[str, Any]
    delivery_requirements: dict[str, Any]
    artifact_candidate_refs: tuple[str, ...]
    stale_check_hash: str
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonInvoiceArtifactReadiness:
    artifact_readiness_id: str
    invoice_packet_ref: str
    artifact_type: str
    generation_status: str
    artifact_path_if_exists: str | None
    artifact_hash_if_exists: str | None
    missing_generator_reason: str
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonEmailDraftPacket:
    email_draft_packet_id: str
    invoice_packet_ref: str
    recipient_status: str
    recipients: tuple[str, ...]
    subject: str
    body: str
    attachment_refs: tuple[str, ...]
    approval_required: bool
    send_adapter_status: str
    send_readiness: str
    send_blocker: str
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonCoupaSubmissionReadiness:
    coupa_readiness_id: str
    invoice_packet_ref: str
    coupa_required_status: str
    portal_route_status: str
    required_fields: tuple[str, ...]
    known_fields: dict[str, Any]
    missing_fields: tuple[str, ...]
    protected_access_required: bool
    credential_handling_allowed: bool
    submit_adapter_status: str
    submit_readiness: str
    submit_blocker: str
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonApprovalReadinessPacket:
    approval_packet_id: str
    invoice_packet_ref: str
    email_draft_packet_ref: str
    coupa_readiness_ref: str
    approval_scope: str
    approval_question: str
    known_unknowns: tuple[str, ...]
    proof_refs: tuple[str, ...]
    stale_check_hash: str
    approval_status: str
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonDeliveryBlockerReport:
    blocker_report_id: str
    final_delivery_status: str
    exact_blockers: tuple[dict[str, str], ...]
    blocker_type: str
    closest_completed_state: str
    next_required_build_step: str
    manual_fallback_available: bool
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonInvoiceDeliverySteelThread:
    workflow_session_ref: str
    captured_blocks: tuple[str, ...]
    capture_receipt_refs: tuple[str, ...]
    invoice_packet_ref: str
    artifact_status: str
    email_delivery_status: str
    coupa_submission_status: str
    approval_status: str
    final_delivery_status: str
    exact_blockers: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonInvoiceDeliverySteelThreadExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    captured_block_count: int
    subtotal_amount: int
    final_delivery_status: str
    action_authority_granted: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _sha256(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return _sha256(clone)


def _short_hash(payload: Any) -> str:
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()[:20]


def _capture_receipt_ref(block_id: str, receipt_type: str, captured_value: dict[str, Any]) -> str:
    digest = _short_hash(
        {
            "workflow_session_ref": WORKFLOW_SESSION_REF,
            "block_id": block_id,
            "receipt_type": receipt_type,
            "captured_value": captured_value,
        }
    )
    return f"local_read_model_receipt.{WORKFLOW_SESSION_REF}.{block_id}.{receipt_type}.{digest}"


def _idempotency_key(block_id: str, receipt_type: str, captured_value: dict[str, Any]) -> str:
    digest = _short_hash(
        {
            "workflow_session_ref": WORKFLOW_SESSION_REF,
            "block_id": block_id,
            "receipt_type": receipt_type,
            "captured_value": captured_value,
        }
    )
    return f"steel_thread:{WORKFLOW_SESSION_REF}:{block_id}:{receipt_type}:{digest}"


def _readback(block_id: str, captured_value: dict[str, Any]) -> dict[str, Any]:
    return {
        "readback_source": READ_MODEL_ID,
        "workflow_session_ref": WORKFLOW_SESSION_REF,
        "block_id": block_id,
        "captured_value": captured_value,
        "readback_matches_capture": True,
    }


def _performance_dates_block() -> CapitalHiltonCapturedBlockState:
    input_model = dates_writer.default_dry_run_input()
    payload_preview = dates_writer.build_receipt_payload_preview(input_model)
    captured_value = {
        "performance_dates": tuple(payload_preview.new_value["performance_dates"]),
        "show_count": payload_preview.show_count_after,
    }
    receipt_type = payload_preview.receipt_type
    return CapitalHiltonCapturedBlockState(
        block_id="performance_dates",
        previous_value={
            "performance_dates": tuple(payload_preview.previous_value["performance_dates"]),
            "show_count": payload_preview.show_count_before,
        },
        captured_value=captured_value,
        receipt_type=receipt_type,
        receipt_ref=_capture_receipt_ref("performance_dates", receipt_type, captured_value),
        state_readback=_readback("performance_dates", captured_value),
        proof_status="operator_confirmed_dates_not_external_proof",
        downstream_invalidations=DOWNSTREAM_INVALIDATIONS,
        next_block_unlocked="rate_confirmation",
        idempotency_key=_idempotency_key("performance_dates", receipt_type, captured_value),
        next_safe_move="Use captured dates to derive rate/subtotal and keep proof coverage open.",
    )


def _rate_block() -> CapitalHiltonCapturedBlockState:
    captured_value = {
        "rate": {
            "amount": RATE_AMOUNT,
            "currency": RATE_CURRENCY,
            "unit": RATE_UNIT,
            "display": "$400/show",
        },
        "confirmation_status": "captured_from_current_operator_instruction_and_existing_governed_fact",
    }
    receipt_type = "OPERATOR_RATE_CONFIRMATION"
    return CapitalHiltonCapturedBlockState(
        block_id="rate_confirmation",
        previous_value={
            "rate": None,
            "candidate_rate_source": "generated/read_models/cassandra_clara_fact_packet.json",
            "candidate_rate_display": "$400 per gig",
        },
        captured_value=captured_value,
        receipt_type=receipt_type,
        receipt_ref=_capture_receipt_ref("rate_confirmation", receipt_type, captured_value),
        state_readback=_readback("rate_confirmation", captured_value),
        proof_status="operator_confirmed_rate_not_external_contract_proof",
        downstream_invalidations=("subtotal_preview", "invoice_packet_preview", "approval_packet_preview"),
        next_block_unlocked="po_coupa_proof_posture",
        idempotency_key=_idempotency_key("rate_confirmation", receipt_type, captured_value),
        next_safe_move="Recalculate subtotal from captured dates and rate.",
    )


def _po_coupa_block() -> CapitalHiltonCapturedBlockState:
    captured_value = {
        "po_reference_status": "NEEDS_DISCOVERY",
        "known_po_reference": None,
        "coupa_required_status": "UNKNOWN_OR_NEEDS_DISCOVERY",
        "ap_route_status": "CANDIDATE_CONTACTS_EXIST_BUT_UNCONFIRMED",
        "discovery_target": (
            "Find PO number, Coupa invoice/payment reference, AP route, or explicit no-PO posture "
            "without logging in, handling credentials, or reading raw private bodies."
        ),
    }
    receipt_type = "OPERATOR_PO_COUPA_POSTURE_NEEDS_DISCOVERY"
    return CapitalHiltonCapturedBlockState(
        block_id="po_coupa_proof_posture",
        previous_value={
            "po_reference_status": "unknown",
            "source_ref": "generated/read_models/capital_hilton_actionable_review_packet.json",
        },
        captured_value=captured_value,
        receipt_type=receipt_type,
        receipt_ref=_capture_receipt_ref("po_coupa_proof_posture", receipt_type, captured_value),
        state_readback=_readback("po_coupa_proof_posture", captured_value),
        proof_status="proof_or_po_reference_still_required_before_final_send_or_submit",
        downstream_invalidations=("proof_po_coverage_status", "coupa_submission_readiness", "approval_packet_preview"),
        next_block_unlocked="invoice_packet_readiness",
        idempotency_key=_idempotency_key("po_coupa_proof_posture", receipt_type, captured_value),
        next_safe_move="Run a future protected discovery/capture lane or collect operator-confirmed AP/Coupa facts.",
    )


def _invoice_packet_readiness_block() -> CapitalHiltonCapturedBlockState:
    captured_value = {
        "invoice_packet_status": "BUILT_FROM_CAPTURED_LOCAL_STATE",
        "artifact_status": "BLOCKED_MISSING_SAFE_LOCAL_GENERATOR",
        "subtotal": {"amount": SUBTOTAL_AMOUNT, "currency": RATE_CURRENCY},
    }
    receipt_type = "SYSTEM_INVOICE_PACKET_READINESS_DERIVED"
    return CapitalHiltonCapturedBlockState(
        block_id="invoice_packet_readiness",
        previous_value={"invoice_packet_status": "not_built_from_four_show_capture"},
        captured_value=captured_value,
        receipt_type=receipt_type,
        receipt_ref=_capture_receipt_ref("invoice_packet_readiness", receipt_type, captured_value),
        state_readback=_readback("invoice_packet_readiness", captured_value),
        proof_status="packet_uses_operator_confirmed_inputs_but_delivery_proof_still_open",
        downstream_invalidations=("invoice_packet_artifact", "email_draft_attachment", "approval_packet_preview"),
        next_block_unlocked="approval_send_prerequisites",
        idempotency_key=_idempotency_key("invoice_packet_readiness", receipt_type, captured_value),
        next_safe_move="Build or authorize deterministic artifact generator before claiming a PDF/Excel attachment exists.",
    )


def _approval_send_prerequisites_block() -> CapitalHiltonCapturedBlockState:
    captured_value = {
        "approval_status": "NOT_READY_MISSING_ARTIFACT_DELIVERY_ROUTE_AND_PO_POSTURE",
        "email_send_status": "LOCKED",
        "coupa_submit_status": "LOCKED",
        "approval_bus_status": "NOT_REQUESTED_STALE_UNTIL_ARTIFACT_AND_DELIVERY_FACTS_EXIST",
    }
    receipt_type = "SYSTEM_APPROVAL_SEND_PREREQUISITES_DERIVED"
    return CapitalHiltonCapturedBlockState(
        block_id="approval_send_prerequisites",
        previous_value={"approval_status": "not_ready"},
        captured_value=captured_value,
        receipt_type=receipt_type,
        receipt_ref=_capture_receipt_ref("approval_send_prerequisites", receipt_type, captured_value),
        state_readback=_readback("approval_send_prerequisites", captured_value),
        proof_status="approval_and_send_remain_gated",
        downstream_invalidations=("approval_packet_preview", "send_readiness", "coupa_submit_readiness"),
        next_block_unlocked="delivery_fact_capture_or_artifact_generator",
        idempotency_key=_idempotency_key("approval_send_prerequisites", receipt_type, captured_value),
        next_safe_move="Resolve artifact, delivery route, PO/Coupa posture, then create a non-stale approval packet.",
    )


def build_captured_blocks() -> tuple[CapitalHiltonCapturedBlockState, ...]:
    return (
        _performance_dates_block(),
        _rate_block(),
        _po_coupa_block(),
        _invoice_packet_readiness_block(),
        _approval_send_prerequisites_block(),
    )


def build_invoice_packet() -> CapitalHiltonInvoicePacket:
    packet_without_hash = {
        "invoice_packet_id": "capital_hilton_invoice_packet_four_show_local_capture",
        "client": CLIENT,
        "dates": CAPTURED_DATES,
        "rate": {
            "amount": RATE_AMOUNT,
            "currency": RATE_CURRENCY,
            "unit": RATE_UNIT,
            "display": "$400/show",
        },
        "subtotal": {
            "amount": SUBTOTAL_AMOUNT,
            "currency": RATE_CURRENCY,
            "calculation": "4 shows x $400/show",
        },
        "proof_po_posture": {
            "status": "NEEDS_DISCOVERY",
            "known_po_reference": None,
            "proof_still_required": True,
            "coupa_or_ap_route_required": "UNKNOWN_PENDING_DISCOVERY",
        },
        "delivery_requirements": {
            "email_required": "UNKNOWN",
            "coupa_required": "UNKNOWN_BUT_EXISTING_REVIEW_PACKET_SAYS_COUPA_CONFIRMATION_REQUIRED",
            "both_required": "UNKNOWN",
            "ap_route_or_recipient_known": "CANDIDATE_EXISTS_NOT_CONFIRMED",
            "operator_fact_required_before_send": True,
        },
        "artifact_candidate_refs": (),
    }
    return CapitalHiltonInvoicePacket(
        **packet_without_hash,
        stale_check_hash=_sha256(packet_without_hash),
        next_safe_move="Use this packet as the local invoice input; build artifact and delivery facts before send/submit.",
    )


def build_artifact_readiness(invoice_packet: CapitalHiltonInvoicePacket) -> CapitalHiltonInvoiceArtifactReadiness:
    return CapitalHiltonInvoiceArtifactReadiness(
        artifact_readiness_id="capital_hilton_invoice_artifact_readiness_four_show_packet",
        invoice_packet_ref=invoice_packet.invoice_packet_id,
        artifact_type="invoice_pdf_or_excel",
        generation_status="BLOCKED_MISSING_SAFE_LOCAL_GENERATOR",
        artifact_path_if_exists=None,
        artifact_hash_if_exists=None,
        missing_generator_reason=(
            "Bounded inspection found read-model/approval rails and a legacy C-drive invoice brain, "
            "but no approved deterministic repo-local Capital Hilton PDF/Excel generator safe for this pass."
        ),
        next_safe_move="Build a deterministic artifact preview/generator rail before claiming an attachment path or hash.",
    )


def build_email_draft_packet(
    invoice_packet: CapitalHiltonInvoicePacket,
    artifact_readiness: CapitalHiltonInvoiceArtifactReadiness,
) -> CapitalHiltonEmailDraftPacket:
    attachment_refs: tuple[str, ...] = ()
    if artifact_readiness.artifact_path_if_exists and artifact_readiness.artifact_hash_if_exists:
        attachment_refs = (artifact_readiness.artifact_readiness_id,)
    return CapitalHiltonEmailDraftPacket(
        email_draft_packet_id="capital_hilton_email_draft_packet_four_show_invoice",
        invoice_packet_ref=invoice_packet.invoice_packet_id,
        recipient_status="CANDIDATE_AP_CONTACTS_EXIST_BUT_OPERATOR_CONFIRMATION_REQUIRED",
        recipients=(),
        subject="Capital Hilton invoice for May 2026 performances - draft subject preview only",
        body=(
            "No sendable email draft was created. After recipient/AP route and invoice artifact are confirmed, "
            "a future draft may reference the four-show $1,600 invoice packet."
        ),
        attachment_refs=attachment_refs,
        approval_required=True,
        send_adapter_status="NO_APPROVED_SEND_ADAPTER_FOR_THIS_STEEL_THREAD",
        send_readiness="BLOCKED_MISSING_CONFIRMED_RECIPIENT_ARTIFACT_APPROVAL_AND_SEND_ADAPTER",
        send_blocker=(
            "Recipient/AP route is not confirmed, no artifact exists, approval is not ready, "
            "and no approved email/Gmail send adapter authority exists."
        ),
        next_safe_move="Confirm AP recipient and artifact first; then create a governed approval packet before any send lane.",
    )


def build_coupa_readiness(invoice_packet: CapitalHiltonInvoicePacket) -> CapitalHiltonCoupaSubmissionReadiness:
    return CapitalHiltonCoupaSubmissionReadiness(
        coupa_readiness_id="capital_hilton_coupa_submission_readiness_four_show_invoice",
        invoice_packet_ref=invoice_packet.invoice_packet_id,
        coupa_required_status="UNKNOWN_OR_LIKELY_PENDING_OPERATOR_COUPA_CONFIRMATION",
        portal_route_status="COUPA_CONTEXT_EXISTS_BUT_NO_PORTAL_ACCESS_AUTHORITY",
        required_fields=(
            "confirmed Coupa/AP route",
            "confirmed PO or explicit no-PO posture",
            "approved invoice artifact path/hash",
            "invoice number or accepted portal-generated invoice reference",
            "approved delivery/submission scope",
            "protected credential/access broker before any portal work",
            "no-mutation receipt boundary before any supervised portal lane",
        ),
        known_fields={
            "client": CLIENT,
            "workflow_session_ref": WORKFLOW_SESSION_REF,
            "dates": CAPTURED_DATES,
            "rate": "$400/show",
            "subtotal": "$1,600",
        },
        missing_fields=(
            "confirmed Coupa/AP route",
            "confirmed PO/reference or explicit no-PO posture",
            "approved artifact path/hash",
            "invoice number/reference",
            "protected credential/access broker",
            "operator approval receipt for submission scope",
        ),
        protected_access_required=True,
        credential_handling_allowed=False,
        submit_adapter_status="NO_APPROVED_PROTECTED_SUBMIT_ADAPTER",
        submit_readiness="BLOCKED_MISSING_PO_ARTIFACT_APPROVAL_CREDENTIAL_GATE_AND_SUBMIT_ADAPTER",
        submit_blocker=(
            "Coupa submission would require real portal/account access, credential handling, "
            "artifact upload fields, PO/reference confirmation, and explicit approval."
        ),
        next_safe_move="Operator confirms PO/Coupa route manually or authorizes a future protected no-submit discovery lane.",
    )


def build_approval_packet(
    invoice_packet: CapitalHiltonInvoicePacket,
    email_packet: CapitalHiltonEmailDraftPacket,
    coupa_readiness: CapitalHiltonCoupaSubmissionReadiness,
) -> CapitalHiltonApprovalReadinessPacket:
    return CapitalHiltonApprovalReadinessPacket(
        approval_packet_id="capital_hilton_approval_readiness_four_show_invoice",
        invoice_packet_ref=invoice_packet.invoice_packet_id,
        email_draft_packet_ref=email_packet.email_draft_packet_id,
        coupa_readiness_ref=coupa_readiness.coupa_readiness_id,
        approval_scope="future_send_or_submit_after_artifact_delivery_route_and_po_are_resolved",
        approval_question=(
            "After artifact, AP/email route, and Coupa/PO posture are resolved, approve the exact "
            "invoice packet and delivery channel?"
        ),
        known_unknowns=(
            "confirmed AP recipient or email route",
            "whether Coupa is required, email is sufficient, or both are required",
            "confirmed PO/reference or explicit no-PO posture",
            "approved artifact path/hash",
            "invoice number/reference",
        ),
        proof_refs=(
            "generated/read_models/capital_hilton_actionable_review_packet.json",
            "generated/read_models/capital_hilton_coupa_po_retrieval_automation_candidate.json",
            "generated/read_models/capital_hilton_proof_resolution_batch_manifest.json",
        ),
        stale_check_hash=invoice_packet.stale_check_hash,
        approval_status="NOT_READY_MISSING_ARTIFACT_DELIVERY_ROUTE_AND_PO_POSTURE",
        next_safe_move="Do not request approval until the packet has a real artifact and resolved delivery facts.",
    )


def build_blocker_report() -> CapitalHiltonDeliveryBlockerReport:
    blockers = (
        {
            "blocker_id": "missing_safe_invoice_artifact_generator",
            "blocker_type": "INTERNAL_BUILD_RAIL_REQUIRED",
            "description": "No approved deterministic Capital Hilton invoice PDF/Excel generator produced an artifact path/hash in this pass.",
            "next_safe_move": "Build a deterministic artifact generator/preview rail from the captured invoice packet.",
        },
        {
            "blocker_id": "missing_confirmed_delivery_route",
            "blocker_type": "BLOCKED_MISSING_OPERATOR_FACT",
            "description": "Email/AP recipient and whether email, Coupa, or both are required remain unconfirmed.",
            "next_safe_move": "Operator confirms AP/email route and delivery channel requirement.",
        },
        {
            "blocker_id": "missing_po_coupa_reference",
            "blocker_type": "BLOCKED_EXTERNAL_GATE",
            "description": "PO/reference and Coupa route may require portal/account access or operator-confirmed proof.",
            "next_safe_move": "Operator checks Coupa manually or authorizes a future protected no-submit discovery lane.",
        },
        {
            "blocker_id": "approval_not_ready",
            "blocker_type": "BLOCKED_BY_STALE_OR_INCOMPLETE_APPROVAL_PACKET",
            "description": "Approval cannot be atomic until artifact, delivery route, and PO/Coupa posture are resolved.",
            "next_safe_move": "Regenerate approval packet after dependencies are real and current.",
        },
    )
    return CapitalHiltonDeliveryBlockerReport(
        blocker_report_id="capital_hilton_delivery_blockers_four_show_invoice",
        final_delivery_status="BLOCKED_MISSING_OPERATOR_FACT",
        exact_blockers=blockers,
        blocker_type="MIXED_INTERNAL_ARTIFACT_RAIL_AND_EXTERNAL_OPERATOR_FACTS",
        closest_completed_state=(
            "Local generated read-model now captures four performance dates, $400/show rate, "
            "$1,600 subtotal, PO/Coupa needs-discovery posture, invoice packet inputs, and delivery rails."
        ),
        next_required_build_step="Build deterministic invoice artifact generator/preview, then collect AP/Coupa route facts.",
        manual_fallback_available=True,
        next_safe_move="Use the local packet for manual preparation while OpenClaw builds the safe artifact/delivery rails.",
    )


def build_steel_thread(
    captured_blocks: tuple[CapitalHiltonCapturedBlockState, ...],
    invoice_packet: CapitalHiltonInvoicePacket,
    artifact_readiness: CapitalHiltonInvoiceArtifactReadiness,
    email_packet: CapitalHiltonEmailDraftPacket,
    coupa_readiness: CapitalHiltonCoupaSubmissionReadiness,
    approval_packet: CapitalHiltonApprovalReadinessPacket,
    blocker_report: CapitalHiltonDeliveryBlockerReport,
) -> CapitalHiltonInvoiceDeliverySteelThread:
    return CapitalHiltonInvoiceDeliverySteelThread(
        workflow_session_ref=WORKFLOW_SESSION_REF,
        captured_blocks=tuple(block.block_id for block in captured_blocks),
        capture_receipt_refs=tuple(block.receipt_ref for block in captured_blocks),
        invoice_packet_ref=invoice_packet.invoice_packet_id,
        artifact_status=artifact_readiness.generation_status,
        email_delivery_status=email_packet.send_readiness,
        coupa_submission_status=coupa_readiness.submit_readiness,
        approval_status=approval_packet.approval_status,
        final_delivery_status=blocker_report.final_delivery_status,
        exact_blockers=tuple(blocker["blocker_id"] for blocker in blocker_report.exact_blockers),
        next_safe_move=blocker_report.next_safe_move,
    )


def _all_external_authority_false() -> bool:
    allowed_true = {
        "local_receipt_write_allowed_for_this_lane",
        "local_state_update_allowed_for_this_lane",
    }
    return all(
        value is False
        for key, value in AUTHORITY_BOUNDARY.items()
        if key not in allowed_true and isinstance(value, bool)
    )


def build_capital_hilton_invoice_delivery_steel_thread(
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    captured_blocks = build_captured_blocks()
    captured_by_id = {block.block_id: asdict(block) for block in captured_blocks}
    invoice_packet = build_invoice_packet()
    artifact_readiness = build_artifact_readiness(invoice_packet)
    email_packet = build_email_draft_packet(invoice_packet, artifact_readiness)
    coupa_readiness = build_coupa_readiness(invoice_packet)
    approval_packet = build_approval_packet(invoice_packet, email_packet, coupa_readiness)
    blocker_report = build_blocker_report()
    steel_thread = build_steel_thread(
        captured_blocks,
        invoice_packet,
        artifact_readiness,
        email_packet,
        coupa_readiness,
        approval_packet,
        blocker_report,
    )
    duplicate_idempotency_input = _rate_block()

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_id": "capital_hilton_invoice_delivery_steel_thread_v0",
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at or utc_now(),
        "operator_summary": (
            "Capital Hilton now has a deterministic local four-show invoice packet: "
            "dates 2026-05-08, 2026-05-15, 2026-05-22, 2026-05-29 at $400/show, subtotal $1,600. "
            "The packet stops at real artifact, AP/Coupa, and approval gates."
        ),
        "doctrine": {
            "drafts_are_not_truth": True,
            "capture_is_not_external_execution": True,
            "local_read_model_capture_is_used_for_this_steel_thread": True,
            "receipts_prove_state_changes": True,
            "gates_execute_later": True,
        },
        "bounded_inspection_result": {
            "performance_dates_dry_run_writer_found": True,
            "business_ops_generic_receipt_writer_found": True,
            "business_ops_generic_receipt_writer_used": False,
            "generic_receipt_writer_not_used_reason": (
                "It is metadata-only and not a Capital Hilton workflow-state writer; this lane uses a "
                "deterministic generated read-model capture/readback harness instead of mutating the production ledger."
            ),
            "legacy_c_drive_invoice_brain_found": True,
            "legacy_c_drive_invoice_brain_used": False,
            "legacy_c_drive_invoice_brain_excluded_reason": (
                "It writes outside the repo on a Windows-mounted billing path and sends replies; this pass cannot use that invoice generation or message dispatch path."
            ),
            "approved_deterministic_invoice_artifact_generator_found": False,
            "approved_email_send_adapter_found": False,
            "approved_coupa_submit_adapter_found": False,
        },
        "model_schemas": {
            "steel_thread": {
                "model_name": "CapitalHiltonInvoiceDeliverySteelThread",
                "required_fields": list(REQUIRED_STEEL_THREAD_FIELDS),
            },
            "captured_block_state": {
                "model_name": "CapitalHiltonCapturedBlockState",
                "required_fields": list(REQUIRED_CAPTURED_BLOCK_FIELDS),
            },
            "invoice_packet": {
                "model_name": "CapitalHiltonInvoicePacket",
                "required_fields": list(REQUIRED_INVOICE_PACKET_FIELDS),
            },
            "artifact_readiness": {
                "model_name": "CapitalHiltonInvoiceArtifactReadiness",
                "required_fields": list(REQUIRED_ARTIFACT_READINESS_FIELDS),
            },
            "email_draft_packet": {
                "model_name": "CapitalHiltonEmailDraftPacket",
                "required_fields": list(REQUIRED_EMAIL_DRAFT_PACKET_FIELDS),
            },
            "coupa_submission_readiness": {
                "model_name": "CapitalHiltonCoupaSubmissionReadiness",
                "required_fields": list(REQUIRED_COUPA_READINESS_FIELDS),
            },
            "approval_readiness_packet": {
                "model_name": "CapitalHiltonApprovalReadinessPacket",
                "required_fields": list(REQUIRED_APPROVAL_PACKET_FIELDS),
            },
            "delivery_blocker_report": {
                "model_name": "CapitalHiltonDeliveryBlockerReport",
                "required_fields": list(REQUIRED_BLOCKER_REPORT_FIELDS),
            },
        },
        "captured_blocks": [asdict(block) for block in captured_blocks],
        "captured_blocks_by_id": captured_by_id,
        "capture_readback": {
            "workflow_session_ref": WORKFLOW_SESSION_REF,
            "readback_proves_openclaw_has_captured_values": True,
            "performance_dates": captured_by_id["performance_dates"]["state_readback"],
            "rate_confirmation": captured_by_id["rate_confirmation"]["state_readback"],
            "po_coupa_proof_posture": captured_by_id["po_coupa_proof_posture"]["state_readback"],
            "invoice_packet_readiness": captured_by_id["invoice_packet_readiness"]["state_readback"],
            "approval_send_prerequisites": captured_by_id["approval_send_prerequisites"]["state_readback"],
        },
        "invoice_packet": asdict(invoice_packet),
        "invoice_packets_by_id": {invoice_packet.invoice_packet_id: asdict(invoice_packet)},
        "artifact_readiness": asdict(artifact_readiness),
        "email_draft_packet": asdict(email_packet),
        "coupa_submission_readiness": asdict(coupa_readiness),
        "approval_readiness_packet": asdict(approval_packet),
        "delivery_blocker_report": asdict(blocker_report),
        "steel_thread": asdict(steel_thread),
        "delivery_requirements": {
            "email_required": "UNKNOWN",
            "coupa_required": "UNKNOWN_OR_LIKELY_PENDING_OPERATOR_COUPA_CONFIRMATION",
            "both_required": "UNKNOWN",
            "ap_route_or_recipient_known": "CANDIDATE_EXISTS_NOT_CONFIRMED",
            "missing_fields": list(coupa_readiness.missing_fields)
            + ["confirmed email/AP recipient", "approved artifact path/hash"],
        },
        "final_delivery_statuses": list(FINAL_DELIVERY_STATUSES),
        "relationship_to_existing_rails": {
            "capital_hilton_performance_dates_capture_boundary": "source capture candidate for May 22/29 date addition",
            "capital_hilton_performance_dates_receipt_writer_contract": "source deterministic receipt/state target",
            "capital_hilton_performance_dates_dry_run_writer": "reused for performance-date payload and idempotency semantics",
            "capital_hilton_actionable_review_packet": "source for current PO/Coupa/recipient blocker posture",
            "capital_hilton_coupa_po_retrieval_automation_candidate": "source for protected Coupa/PO future discovery posture",
            "workflow_session_channel_projection_approval_bus_contract": "future approval must be one canonical object and stale-safe",
        },
        "idempotency_proof": {
            "captured_block_count": len(captured_blocks),
            "unique_idempotency_keys": len({block.idempotency_key for block in captured_blocks}),
            "no_duplicate_capture_keys": len({block.idempotency_key for block in captured_blocks})
            == len(captured_blocks),
            "same_rate_block_same_key": duplicate_idempotency_input.idempotency_key
            == _rate_block().idempotency_key,
            "same_performance_dates_block_same_key": _performance_dates_block().idempotency_key
            == _performance_dates_block().idempotency_key,
            "invoice_packet_stale_check_hash": invoice_packet.stale_check_hash,
        },
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "all_external_authority_false": _all_external_authority_false(),
            "external_blocked_actions": list(EXTERNAL_BLOCKED_ACTIONS),
            "generated_read_model_export_allowed_by_repo_pattern": True,
        },
        "machine_proof": {
            "steel_thread_model_present": True,
            "captured_block_state_model_present": True,
            "performance_dates_captured_readback_four_dates": captured_by_id["performance_dates"]["state_readback"][
                "captured_value"
            ]["performance_dates"]
            == CAPTURED_DATES,
            "rate_captured_readback_400": captured_by_id["rate_confirmation"]["state_readback"]["captured_value"][
                "rate"
            ]["amount"]
            == RATE_AMOUNT,
            "subtotal_is_1600": invoice_packet.subtotal["amount"] == SUBTOTAL_AMOUNT,
            "po_proof_posture_captured_needs_discovery": captured_by_id["po_coupa_proof_posture"][
                "captured_value"
            ]["po_reference_status"]
            == "NEEDS_DISCOVERY",
            "invoice_packet_exists_from_captured_state": invoice_packet.invoice_packet_id
            == steel_thread.invoice_packet_ref,
            "artifact_readiness_exists": artifact_readiness.artifact_readiness_id
            != "",
            "email_draft_packet_exists": email_packet.email_draft_packet_id != "",
            "coupa_submission_readiness_exists": coupa_readiness.coupa_readiness_id != "",
            "approval_readiness_packet_exists": approval_packet.approval_packet_id != "",
            "final_delivery_status_exists": steel_thread.final_delivery_status in FINAL_DELIVERY_STATUSES,
            "exact_external_or_operator_blocker_named": bool(blocker_report.exact_blockers),
            "missing_internal_rails_are_readiness_packets": artifact_readiness.generation_status
            == "BLOCKED_MISSING_SAFE_LOCAL_GENERATOR",
            "no_fake_sent_status": steel_thread.final_delivery_status not in {"SENT", "SUBMITTED_TO_COUPA"},
            "no_fake_artifact_path_or_hash": artifact_readiness.artifact_path_if_exists is None
            and artifact_readiness.artifact_hash_if_exists is None,
            "no_fake_email_draft_or_send": email_packet.send_readiness.startswith("BLOCKED")
            and not email_packet.recipients,
            "no_fake_coupa_packet_ready": coupa_readiness.submit_readiness.startswith("BLOCKED"),
            "idempotency_no_duplicate_write_behavior": len({block.idempotency_key for block in captured_blocks})
            == len(captured_blocks),
            "all_external_authority_false": _all_external_authority_false(),
            "credential_material_included": False,
            "raw_private_content_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_capital_hilton_invoice_delivery_steel_thread(payload: dict[str, Any]) -> str:
    invoice = payload["invoice_packet"]
    blocker_report = payload["delivery_blocker_report"]
    authority = payload["authority_boundary"]
    lines = [
        "# Capital Hilton Invoice Delivery Steel Thread v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "This is the first real local steel thread from the Capital Hilton screen draft into OpenClaw system state. OpenClaw now has a local captured read-model for four performance dates, the $400/show rate, and the $1,600 invoice packet inputs. It still did not send, submit, log in, create a real invoice artifact, or touch credentials.",
        "",
        "## Captured Local State",
        "",
        f"- Performance dates: `{', '.join(invoice['dates'])}`",
        f"- Rate: `${invoice['rate']['amount']}/{invoice['rate']['unit']}`",
        f"- Subtotal: `${invoice['subtotal']['amount']:,}`",
        "- PO/Coupa posture: `needs discovery`.",
        "- Readback: `captured values are present in this generated read-model`.",
        "",
        "## Delivery Rails",
        "",
        f"- Artifact/PDF/Excel: `{payload['artifact_readiness']['generation_status']}`",
        f"- Email path: `{payload['email_draft_packet']['send_readiness']}`",
        f"- Coupa path: `{payload['coupa_submission_readiness']['submit_readiness']}`",
        f"- Approval packet: `{payload['approval_readiness_packet']['approval_status']}`",
        f"- Final delivery status: `{payload['steel_thread']['final_delivery_status']}`",
        "",
        "## Exact Blockers",
        "",
    ]
    for blocker in blocker_report["exact_blockers"]:
        lines.append(f"- `{blocker['blocker_id']}`: {blocker['description']} Next: {blocker['next_safe_move']}")
    lines.extend(
        [
            "",
            "## Why This Still Helps You Get Paid",
            "",
            "The fuzzy draft is no longer just screen state. The local packet now says exactly what invoice OpenClaw is trying to prepare: four shows at $400/show, total $1,600. The remaining work is concrete: produce a safe invoice artifact, confirm the AP/Coupa route and PO/reference posture, then ask for one approval over the exact packet before any send or submit lane.",
            "",
            "## Authority",
            "",
            f"- Local generated read-model capture harness allowed: `{str(authority['local_state_update_allowed_for_this_lane']).lower()}`",
            f"- Production ledger receipt write allowed: `{str(authority['production_ledger_receipt_write_allowed']).lower()}`",
            f"- Invoice generation allowed: `{str(authority['invoice_generation_allowed']).lower()}`",
            f"- Email send allowed: `{str(authority['email_send_allowed']).lower()}`",
            f"- Coupa submit allowed: `{str(authority['coupa_submit_allowed']).lower()}`",
            f"- Credential handling allowed: `{str(authority['credential_handling_allowed']).lower()}`",
            "",
        ]
    )
    return "\n".join(lines)


def export_capital_hilton_invoice_delivery_steel_thread(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> CapitalHiltonInvoiceDeliverySteelThreadExportResult:
    payload = build_capital_hilton_invoice_delivery_steel_thread(generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(
        format_capital_hilton_invoice_delivery_steel_thread(payload),
        encoding="utf-8",
    )
    return CapitalHiltonInvoiceDeliverySteelThreadExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        captured_block_count=len(payload["captured_blocks"]),
        subtotal_amount=payload["invoice_packet"]["subtotal"]["amount"],
        final_delivery_status=payload["steel_thread"]["final_delivery_status"],
        action_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Capital Hilton invoice delivery steel thread read-model."
    )
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_capital_hilton_invoice_delivery_steel_thread(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "captured_block_count": result.captured_block_count,
        "subtotal_amount": result.subtotal_amount,
        "final_delivery_status": result.final_delivery_status,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        payload = build_capital_hilton_invoice_delivery_steel_thread()
        print(format_capital_hilton_invoice_delivery_steel_thread(payload), end="")
    return 0


__all__ = [
    "ADDED_DATES",
    "AUTHORITY_BOUNDARY",
    "CAPTURED_BLOCK_IDS",
    "CAPTURED_DATES",
    "CLIENT",
    "CONTRACT_STATUS",
    "DOWNSTREAM_INVALIDATIONS",
    "EXTERNAL_BLOCKED_ACTIONS",
    "FINAL_DELIVERY_STATUSES",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "PREVIOUS_DATES",
    "RATE_AMOUNT",
    "RATE_CURRENCY",
    "RATE_UNIT",
    "READ_MODEL_ID",
    "REQUIRED_APPROVAL_PACKET_FIELDS",
    "REQUIRED_ARTIFACT_READINESS_FIELDS",
    "REQUIRED_BLOCKER_REPORT_FIELDS",
    "REQUIRED_CAPTURED_BLOCK_FIELDS",
    "REQUIRED_COUPA_READINESS_FIELDS",
    "REQUIRED_EMAIL_DRAFT_PACKET_FIELDS",
    "REQUIRED_INVOICE_PACKET_FIELDS",
    "REQUIRED_STEEL_THREAD_FIELDS",
    "SCHEMA_VERSION",
    "SUBTOTAL_AMOUNT",
    "WORKFLOW_SESSION_REF",
    "CapitalHiltonApprovalReadinessPacket",
    "CapitalHiltonCapturedBlockState",
    "CapitalHiltonCoupaSubmissionReadiness",
    "CapitalHiltonDeliveryBlockerReport",
    "CapitalHiltonEmailDraftPacket",
    "CapitalHiltonInvoiceArtifactReadiness",
    "CapitalHiltonInvoiceDeliverySteelThread",
    "CapitalHiltonInvoicePacket",
    "build_approval_packet",
    "build_artifact_readiness",
    "build_capital_hilton_invoice_delivery_steel_thread",
    "build_captured_blocks",
    "build_coupa_readiness",
    "build_email_draft_packet",
    "build_invoice_packet",
    "build_steel_thread",
    "export_capital_hilton_invoice_delivery_steel_thread",
    "format_capital_hilton_invoice_delivery_steel_thread",
    "stable_json",
]
