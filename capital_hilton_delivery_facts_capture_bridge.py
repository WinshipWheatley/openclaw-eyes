"""Capital Hilton guided delivery-facts capture bridge.

This lane sits after the captured invoice-state and artifact-preview rails. It
models safe capture/readiness for the remaining delivery facts: PO/Coupa/payment
reference posture, AP/email route posture, and protected evidence references.

It does not log into Coupa or Gmail, read protected bodies, send email, submit
approval, write delivery-fact receipts, or mutate workflow state. Receipt/state
write authority remains false until a narrow writer is added for these blocks.
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


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
ARTIFACT_READ_MODEL_PATH = Path("generated/read_models/capital_hilton_invoice_artifact_generator.json")

SCHEMA_VERSION = "capital_hilton_delivery_facts_capture_bridge_v0"
READ_MODEL_ID = "capital_hilton_delivery_facts_capture_bridge"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DELIVERY_FACTS_CAPTURE_READINESS_ONLY"

WORKFLOW_SESSION_REF = "capital_hilton_invoice_workflow_session"
INVOICE_PACKET_REF = "capital_hilton_invoice_packet_four_show_local_capture"
ARTIFACT_READINESS_REF = "capital_hilton_invoice_artifact_candidate_markdown_preview_four_show"
WORLD = "Finance"
LANE = "Capital Hilton"

CAPTURED_DATES = ("2026-05-08", "2026-05-15", "2026-05-22", "2026-05-29")
RATE_PER_SHOW = {"amount": 400, "currency": "USD", "unit": "show", "display": "$400/show"}
SUBTOTAL = {"amount": 1600, "currency": "USD", "calculation": "4 shows x $400/show"}

PO_COUPA_POSTURES = (
    "PO_REFERENCE_KNOWN",
    "COUPA_REFERENCE_KNOWN",
    "NO_PO_KNOWN_PENDING_PROOF",
    "COUPA_REQUIRED_UNKNOWN",
    "NEEDS_DISCOVERY",
    "PROTECTED_ACCESS_REQUIRED",
    "UNKNOWN_FAIL_CLOSED",
)

AP_EMAIL_POSTURES = (
    "AP_EMAIL_CONFIRMED",
    "AP_EMAIL_CANDIDATE_NEEDS_CONFIRMATION",
    "AP_ROUTE_UNKNOWN",
    "AP_ROUTE_PROTECTED_REFERENCE_REQUIRED",
    "NEEDS_DISCOVERY",
    "UNKNOWN_FAIL_CLOSED",
)

PROTECTED_TARGET_KINDS = (
    "COUPA_PO_SCREEN_REFERENCE",
    "AP_EMAIL_ROUTE_REFERENCE",
    "EMAIL_THREAD_REFERENCE",
    "SOURCE_CARD_REFERENCE",
    "OPERATOR_TEXT_CONFIRMATION",
    "UNKNOWN_FAIL_CLOSED",
)

RECEIPT_TYPES = (
    "OPERATOR_PO_REFERENCE_CAPTURE",
    "OPERATOR_NO_PO_KNOWN_POSTURE",
    "OPERATOR_COUPA_REQUIRED_UNKNOWN",
    "OPERATOR_AP_EMAIL_ROUTE_CONFIRMATION",
    "PROTECTED_EVIDENCE_REFERENCE_RECEIPT",
    "DISCOVERY_REQUIRED_RECEIPT",
    "UNKNOWN_FAIL_CLOSED",
)

REQUIRED_BRIDGE_FIELDS = (
    "bridge_id",
    "workflow_session_ref",
    "invoice_packet_ref",
    "artifact_ref_or_readiness_ref",
    "current_delivery_status",
    "po_coupa_posture",
    "ap_email_route_posture",
    "protected_evidence_posture",
    "capture_blocks",
    "supported_capture_methods",
    "unsupported_external_actions",
    "next_safe_move",
)

REQUIRED_PO_BLOCK_FIELDS = (
    "block_id",
    "current_status",
    "question_text",
    "allowed_operator_answers",
    "supported_capture_paths",
    "protected_evidence_required",
    "required_fields",
    "known_fields",
    "missing_fields",
    "receipt_target",
    "guardian_review_required",
    "downstream_effects",
    "next_safe_move",
)

REQUIRED_AP_BLOCK_FIELDS = (
    "block_id",
    "current_status",
    "question_text",
    "allowed_operator_answers",
    "email_route_candidates",
    "confirmed_recipient",
    "required_confirmation",
    "proof_reference_required",
    "receipt_target",
    "downstream_effects",
    "next_safe_move",
)

REQUIRED_PROTECTED_REFERENCE_FIELDS = (
    "protected_reference_id",
    "target_kind",
    "source_hint",
    "allowed_metadata",
    "forbidden_material",
    "hash_required",
    "path_required_if_file",
    "redaction_required",
    "guardian_review_required",
    "normal_read_model_body_allowed",
    "receipt_target",
    "next_safe_move",
)

REQUIRED_RECEIPT_TARGET_FIELDS = (
    "receipt_target_id",
    "capture_block_ref",
    "receipt_type",
    "intended_state_update",
    "proof_refs",
    "protected_reference_refs",
    "required_validation",
    "required_guardian_review",
    "current_write_authority",
    "current_external_authority",
    "next_safe_move",
)

REQUIRED_READINESS_FIELDS = (
    "readiness_id",
    "invoice_packet_ref",
    "artifact_ref_or_readiness_ref",
    "po_coupa_status",
    "ap_email_route_status",
    "protected_evidence_status",
    "email_delivery_readiness",
    "coupa_submission_readiness",
    "approval_readiness",
    "remaining_blockers",
    "next_safe_move",
)

AUTHORITY_BOUNDARY: dict[str, Any] = {
    "local_generated_read_models_allowed": True,
    "local_receipt_target_modeling_allowed": True,
    "protected_evidence_reference_modeling_allowed": True,
    "tests_allowed": True,
    "local_delivery_fact_write_allowed": False,
    "browser_automation_allowed": False,
    "coupa_access_allowed": False,
    "credential_handling_allowed": False,
    "gmail_access_allowed": False,
    "email_send_allowed": False,
    "telegram_send_allowed": False,
    "approval_submission_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_operation_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}


@dataclass(frozen=True)
class CapitalHiltonDeliveryFactsCaptureBridge:
    bridge_id: str
    workflow_session_ref: str
    invoice_packet_ref: str
    artifact_ref_or_readiness_ref: str
    current_delivery_status: str
    po_coupa_posture: str
    ap_email_route_posture: str
    protected_evidence_posture: str
    capture_blocks: tuple[str, ...]
    supported_capture_methods: tuple[str, ...]
    unsupported_external_actions: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonPOCoupaCaptureBlock:
    block_id: str
    current_status: str
    question_text: str
    allowed_operator_answers: tuple[str, ...]
    supported_capture_paths: tuple[str, ...]
    protected_evidence_required: bool
    required_fields: tuple[str, ...]
    known_fields: dict[str, Any]
    missing_fields: tuple[str, ...]
    receipt_target: str
    guardian_review_required: bool
    downstream_effects: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonAPEmailRouteCaptureBlock:
    block_id: str
    current_status: str
    question_text: str
    allowed_operator_answers: tuple[str, ...]
    email_route_candidates: tuple[dict[str, Any], ...]
    confirmed_recipient: str | None
    required_confirmation: str
    proof_reference_required: bool
    receipt_target: str
    downstream_effects: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonProtectedEvidenceReferenceTarget:
    protected_reference_id: str
    target_kind: str
    source_hint: str
    allowed_metadata: tuple[str, ...]
    forbidden_material: tuple[str, ...]
    hash_required: bool
    path_required_if_file: bool
    redaction_required: bool
    guardian_review_required: bool
    normal_read_model_body_allowed: bool
    receipt_target: str
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonDeliveryFactsReceiptTarget:
    receipt_target_id: str
    capture_block_ref: str
    receipt_type: str
    intended_state_update: dict[str, Any]
    proof_refs: tuple[str, ...]
    protected_reference_refs: tuple[str, ...]
    required_validation: tuple[str, ...]
    required_guardian_review: bool
    current_write_authority: bool
    current_external_authority: bool
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonDeliveryFactsReadiness:
    readiness_id: str
    invoice_packet_ref: str
    artifact_ref_or_readiness_ref: str
    po_coupa_status: str
    ap_email_route_status: str
    protected_evidence_status: str
    email_delivery_readiness: str
    coupa_submission_readiness: str
    approval_readiness: str
    remaining_blockers: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonDeliveryFactsCaptureBridgeExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    current_delivery_status: str
    po_coupa_status: str
    ap_email_route_status: str
    external_authority_granted: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_payload(payload: Any) -> str:
    return _sha256_text(stable_json(payload))


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return _sha256_payload(clone)


def _repo_path(path: str | Path, *, repo_root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(repo_root) / candidate


def _load_artifact_readiness(*, repo_root: str | Path = ROOT) -> dict[str, Any]:
    path = _repo_path(ARTIFACT_READ_MODEL_PATH, repo_root=repo_root)
    if not path.is_file():
        return {
            "artifact_ref_or_readiness_ref": ARTIFACT_READINESS_REF,
            "artifact_status": "UNKNOWN_ARTIFACT_READ_MODEL_NOT_PRESENT",
            "artifact_path": None,
            "artifact_hash": None,
            "artifact_exists": False,
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    candidate = payload.get("artifact_candidate", {})
    readback = payload.get("artifact_readback", {})
    return {
        "artifact_ref_or_readiness_ref": candidate.get("artifact_candidate_id", ARTIFACT_READINESS_REF),
        "artifact_status": candidate.get("artifact_status"),
        "artifact_path": candidate.get("artifact_path"),
        "artifact_hash": candidate.get("artifact_hash"),
        "artifact_exists": readback.get("artifact_exists", False),
    }


def build_po_coupa_capture_block() -> CapitalHiltonPOCoupaCaptureBlock:
    return CapitalHiltonPOCoupaCaptureBlock(
        block_id="proof_po_reference",
        current_status="NEEDS_DISCOVERY",
        question_text="What should OpenClaw record for Capital Hilton PO/Coupa/payment reference?",
        allowed_operator_answers=(
            "enter PO/reference",
            "enter Coupa/payment reference",
            "mark no PO known pending proof",
            "mark Coupa required unknown",
            "prepare guided Coupa/AP discovery",
            "park for later",
        ),
        supported_capture_paths=(
            "operator_text_confirmation",
            "source_card_reference",
            "protected_coupa_po_screen_reference",
            "guided_discovery_request",
            "park_unresolved_block",
        ),
        protected_evidence_required=True,
        required_fields=(
            "po_or_coupa_posture",
            "operator decision or protected evidence reference",
            "proof posture after capture",
        ),
        known_fields={
            "client": "Capital Hilton",
            "captured_performance_dates": CAPTURED_DATES,
            "captured_rate_per_show": RATE_PER_SHOW,
            "captured_subtotal": SUBTOTAL,
            "invoice_artifact_preview_ref": ARTIFACT_READINESS_REF,
        },
        missing_fields=(
            "confirmed PO/reference",
            "confirmed Coupa required/not-required posture",
            "protected proof/reference metadata",
        ),
        receipt_target="delivery_receipt_target_po_coupa_discovery_posture",
        guardian_review_required=True,
        downstream_effects=(
            "Coupa submission readiness remains blocked until PO/Coupa posture resolves",
            "approval readiness remains blocked until delivery route and proof posture are coherent",
            "email delivery may proceed only after AP route, artifact, and approval gates resolve",
        ),
        next_safe_move="Ask operator for PO/Coupa posture or create a protected evidence reference target; do not access Coupa.",
    )


def build_ap_email_route_capture_block() -> CapitalHiltonAPEmailRouteCaptureBlock:
    return CapitalHiltonAPEmailRouteCaptureBlock(
        block_id="ap_email_route",
        current_status="AP_EMAIL_CANDIDATE_NEEDS_CONFIRMATION",
        question_text="Where should the Capital Hilton invoice be delivered by email, if email is allowed?",
        allowed_operator_answers=(
            "confirm Annette.Sunga@hilton.com as AP recipient",
            "enter different AP/email route",
            "mark AP route unknown",
            "use source card/protected reference",
            "park for later",
        ),
        email_route_candidates=(
            {
                "candidate_ref": "capital_hilton_annette_sunga_ap_candidate",
                "name": "Annette Sunga",
                "role_or_reason": "generated AP/contact candidate needing confirmation",
                "address": "Annette.Sunga@hilton.com",
                "candidate_status": "CANDIDATE_NEEDS_OPERATOR_CONFIRMATION",
            },
            {
                "candidate_ref": "capital_hilton_chyna_hardin_cc_candidate",
                "name": "Chyna Hardin",
                "role_or_reason": "generated finance CC candidate needing confirmation",
                "address": "Chyna.Hardin@hilton.com",
                "candidate_status": "CANDIDATE_NEEDS_OPERATOR_CONFIRMATION",
            },
            {
                "candidate_ref": "capital_hilton_lawrence_valcovic_cc_candidate",
                "name": "Lawrence / Will Valcovic",
                "role_or_reason": "generated CC/contact candidate needing confirmation",
                "address": "lawrencevalcovic@hilton.com",
                "candidate_status": "CANDIDATE_NEEDS_OPERATOR_CONFIRMATION",
            },
        ),
        confirmed_recipient=None,
        required_confirmation="Operator must confirm AP/email route before delivery readiness advances.",
        proof_reference_required=True,
        receipt_target="delivery_receipt_target_ap_email_route_confirmation",
        downstream_effects=(
            "Email delivery readiness remains blocked until recipient route is confirmed",
            "Approval packet can include candidate route but cannot mark send-ready",
            "No Gmail access or draft creation occurs in this bridge",
        ),
        next_safe_move="Ask operator to confirm or replace AP/email route; do not access Gmail or send.",
    )


def _forbidden_material() -> tuple[str, ...]:
    return (
        "image bytes",
        "base64 payloads",
        "email message contents",
        "credential fields",
        "session cookies",
        "access tokens",
        "bank/tax/remit/private material",
    )


def build_protected_reference_targets() -> tuple[CapitalHiltonProtectedEvidenceReferenceTarget, ...]:
    protected_common_metadata = (
        "workflow_session_ref",
        "target_kind",
        "redacted_source_label",
        "source_card_ref_or_file_ref",
        "sha256 hash when file-backed",
        "protected_storage_ref if available",
        "operator supplied note",
    )
    return (
        CapitalHiltonProtectedEvidenceReferenceTarget(
            protected_reference_id="protected_reference_target_coupa_po_screen",
            target_kind="COUPA_PO_SCREEN_REFERENCE",
            source_hint="A redacted Coupa screen/file reference may prove PO/payment reference posture.",
            allowed_metadata=protected_common_metadata,
            forbidden_material=_forbidden_material(),
            hash_required=True,
            path_required_if_file=True,
            redaction_required=True,
            guardian_review_required=True,
            normal_read_model_body_allowed=False,
            receipt_target="delivery_receipt_target_protected_coupa_reference",
            next_safe_move="Capture only metadata/path/hash/protected ref; no Coupa login or screenshot body ingestion.",
        ),
        CapitalHiltonProtectedEvidenceReferenceTarget(
            protected_reference_id="protected_reference_target_ap_email_route",
            target_kind="AP_EMAIL_ROUTE_REFERENCE",
            source_hint="A source-card or protected reference may back the AP route decision.",
            allowed_metadata=protected_common_metadata,
            forbidden_material=_forbidden_material(),
            hash_required=True,
            path_required_if_file=True,
            redaction_required=True,
            guardian_review_required=True,
            normal_read_model_body_allowed=False,
            receipt_target="delivery_receipt_target_protected_ap_route_reference",
            next_safe_move="Capture route proof metadata only; no Gmail access or email body ingestion.",
        ),
        CapitalHiltonProtectedEvidenceReferenceTarget(
            protected_reference_id="protected_reference_target_email_thread",
            target_kind="EMAIL_THREAD_REFERENCE",
            source_hint="A protected email-thread reference may identify AP route without exposing message contents.",
            allowed_metadata=protected_common_metadata,
            forbidden_material=_forbidden_material(),
            hash_required=True,
            path_required_if_file=False,
            redaction_required=True,
            guardian_review_required=True,
            normal_read_model_body_allowed=False,
            receipt_target="delivery_receipt_target_protected_email_thread_reference",
            next_safe_move="Capture thread/source ref metadata only; no Gmail API or message body access.",
        ),
        CapitalHiltonProtectedEvidenceReferenceTarget(
            protected_reference_id="protected_reference_target_source_card",
            target_kind="SOURCE_CARD_REFERENCE",
            source_hint="An existing source card may support PO/AP posture without exposing protected contents.",
            allowed_metadata=(
                "workflow_session_ref",
                "source_card_ref",
                "proof_item_id",
                "redacted source label",
                "operator supplied note",
            ),
            forbidden_material=_forbidden_material(),
            hash_required=False,
            path_required_if_file=False,
            redaction_required=False,
            guardian_review_required=False,
            normal_read_model_body_allowed=False,
            receipt_target="delivery_receipt_target_source_card_reference",
            next_safe_move="Link existing source-card reference only.",
        ),
        CapitalHiltonProtectedEvidenceReferenceTarget(
            protected_reference_id="protected_reference_target_operator_text_confirmation",
            target_kind="OPERATOR_TEXT_CONFIRMATION",
            source_hint="Operator may explicitly confirm no PO known or confirm AP route as a structured fact.",
            allowed_metadata=(
                "workflow_session_ref",
                "operator_confirmation_label",
                "confirmation_value",
                "proof_still_required flag",
            ),
            forbidden_material=_forbidden_material(),
            hash_required=False,
            path_required_if_file=False,
            redaction_required=False,
            guardian_review_required=False,
            normal_read_model_body_allowed=False,
            receipt_target="delivery_receipt_target_operator_text_confirmation",
            next_safe_move="Capture structured operator confirmation later through a delivery-facts writer.",
        ),
    )


def build_receipt_targets() -> tuple[CapitalHiltonDeliveryFactsReceiptTarget, ...]:
    return (
        CapitalHiltonDeliveryFactsReceiptTarget(
            receipt_target_id="delivery_receipt_target_po_coupa_discovery_posture",
            capture_block_ref="proof_po_reference",
            receipt_type="DISCOVERY_REQUIRED_RECEIPT",
            intended_state_update={
                "po_coupa_posture": "NEEDS_DISCOVERY",
                "proof_still_required": True,
                "coupa_access_performed": False,
            },
            proof_refs=("coupa_po_payment_reference_metadata",),
            protected_reference_refs=("protected_reference_target_coupa_po_screen",),
            required_validation=("supported PO/Coupa posture", "no protected body content", "operator confirmation"),
            required_guardian_review=True,
            current_write_authority=False,
            current_external_authority=False,
            next_safe_move="Future writer may record posture after validation; this contract only defines target.",
        ),
        CapitalHiltonDeliveryFactsReceiptTarget(
            receipt_target_id="delivery_receipt_target_no_po_known",
            capture_block_ref="proof_po_reference",
            receipt_type="OPERATOR_NO_PO_KNOWN_POSTURE",
            intended_state_update={
                "po_coupa_posture": "NO_PO_KNOWN_PENDING_PROOF",
                "proof_still_required": True,
                "coupa_access_performed": False,
            },
            proof_refs=("operator_confirmation_metadata",),
            protected_reference_refs=(),
            required_validation=("operator confirmation", "proof_still_required remains true"),
            required_guardian_review=False,
            current_write_authority=False,
            current_external_authority=False,
            next_safe_move="Future writer may record explicit no-PO-known posture without accessing Coupa.",
        ),
        CapitalHiltonDeliveryFactsReceiptTarget(
            receipt_target_id="delivery_receipt_target_coupa_required_unknown",
            capture_block_ref="proof_po_reference",
            receipt_type="OPERATOR_COUPA_REQUIRED_UNKNOWN",
            intended_state_update={
                "po_coupa_posture": "COUPA_REQUIRED_UNKNOWN",
                "proof_still_required": True,
                "submit_blocker": "Coupa route unresolved",
            },
            proof_refs=("coupa_po_payment_reference_metadata",),
            protected_reference_refs=("protected_reference_target_coupa_po_screen",),
            required_validation=("operator confirmation", "protected access not performed"),
            required_guardian_review=True,
            current_write_authority=False,
            current_external_authority=False,
            next_safe_move="Keep Coupa submission blocked until protected-access lane resolves.",
        ),
        CapitalHiltonDeliveryFactsReceiptTarget(
            receipt_target_id="delivery_receipt_target_ap_email_route_confirmation",
            capture_block_ref="ap_email_route",
            receipt_type="OPERATOR_AP_EMAIL_ROUTE_CONFIRMATION",
            intended_state_update={
                "ap_email_route_posture": "AP_EMAIL_CANDIDATE_NEEDS_CONFIRMATION",
                "confirmed_recipient": None,
                "email_send_allowed": False,
            },
            proof_refs=("ap_recipient_route_metadata",),
            protected_reference_refs=("protected_reference_target_ap_email_route",),
            required_validation=("operator confirmed recipient", "no email body content", "send remains gated"),
            required_guardian_review=False,
            current_write_authority=False,
            current_external_authority=False,
            next_safe_move="Future writer may record confirmed AP route; email send remains separately gated.",
        ),
        CapitalHiltonDeliveryFactsReceiptTarget(
            receipt_target_id="delivery_receipt_target_protected_evidence_reference",
            capture_block_ref="protected_evidence_reference",
            receipt_type="PROTECTED_EVIDENCE_REFERENCE_RECEIPT",
            intended_state_update={
                "protected_reference_recorded": True,
                "normal_read_model_body_allowed": False,
                "guardian_review_required": True,
            },
            proof_refs=("protected_reference_metadata",),
            protected_reference_refs=(
                "protected_reference_target_coupa_po_screen",
                "protected_reference_target_ap_email_route",
                "protected_reference_target_email_thread",
            ),
            required_validation=("metadata only", "hash/path if file-backed", "redaction posture"),
            required_guardian_review=True,
            current_write_authority=False,
            current_external_authority=False,
            next_safe_move="Future protected reference writer can store metadata-only reference after validation.",
        ),
    )


def build_delivery_readiness(artifact_readiness: dict[str, Any]) -> CapitalHiltonDeliveryFactsReadiness:
    artifact_status = artifact_readiness.get("artifact_status") or "UNKNOWN"
    artifact_ref = artifact_readiness.get("artifact_ref_or_readiness_ref") or ARTIFACT_READINESS_REF
    return CapitalHiltonDeliveryFactsReadiness(
        readiness_id="capital_hilton_delivery_facts_readiness_v0",
        invoice_packet_ref=INVOICE_PACKET_REF,
        artifact_ref_or_readiness_ref=artifact_ref,
        po_coupa_status="NEEDS_DISCOVERY",
        ap_email_route_status="AP_EMAIL_CANDIDATE_NEEDS_CONFIRMATION",
        protected_evidence_status="PROTECTED_REFERENCE_REQUIRED_FOR_PO_OR_AP_PROOF",
        email_delivery_readiness="BLOCKED_AP_ROUTE_NOT_CONFIRMED_AND_SEND_GATE_LOCKED",
        coupa_submission_readiness="BLOCKED_PO_COUPA_REFERENCE_AND_PROTECTED_ACCESS_UNRESOLVED",
        approval_readiness="BLOCKED_DELIVERY_FACTS_UNRESOLVED",
        remaining_blockers=(
            f"Invoice artifact/readiness status: {artifact_status}",
            "PO/Coupa/payment reference posture unresolved",
            "AP/email route candidates require operator confirmation",
            "Protected evidence references must be metadata-only and may require Guardian review",
            "Email send and Coupa submit remain external gates",
        ),
        next_safe_move="Render delivery-fact capture blocks; capture operator-confirmed facts later through a narrow writer.",
    )


def build_capture_bridge(artifact_readiness: dict[str, Any]) -> CapitalHiltonDeliveryFactsCaptureBridge:
    return CapitalHiltonDeliveryFactsCaptureBridge(
        bridge_id="capital_hilton_guided_delivery_facts_capture_bridge_v0",
        workflow_session_ref=WORKFLOW_SESSION_REF,
        invoice_packet_ref=INVOICE_PACKET_REF,
        artifact_ref_or_readiness_ref=artifact_readiness.get("artifact_ref_or_readiness_ref")
        or ARTIFACT_READINESS_REF,
        current_delivery_status="ARTIFACT_PREVIEW_READY_DELIVERY_FACTS_BLOCKED",
        po_coupa_posture="NEEDS_DISCOVERY",
        ap_email_route_posture="AP_EMAIL_CANDIDATE_NEEDS_CONFIRMATION",
        protected_evidence_posture="PROTECTED_REFERENCE_REQUIRED_FOR_PO_OR_AP_PROOF",
        capture_blocks=("proof_po_reference", "ap_email_route", "protected_evidence_reference"),
        supported_capture_methods=(
            "operator_text_confirmation",
            "protected_evidence_reference_metadata",
            "source_card_reference",
            "guided_discovery_request",
            "park_unresolved_block",
        ),
        unsupported_external_actions=(
            "Coupa login",
            "browser automation",
            "Gmail access",
            "email send",
            "approval submission",
            "credential handling",
            "raw screenshot or email body ingestion",
        ),
        next_safe_move="Ask for delivery facts and protected references; keep external delivery locked.",
    )


def build_examples() -> dict[str, Any]:
    return {
        "po_unknown_needs_discovery": {
            "current_status": "NEEDS_DISCOVERY",
            "operator_choices": (
                "enter PO/reference",
                "mark no PO known pending proof",
                "prepare guided Coupa/AP discovery",
                "park for later",
            ),
            "external_access": "No Coupa access, browser automation, or credential handling.",
            "expected_readiness": "Coupa submission remains blocked.",
        },
        "ap_email_route_candidate_needs_confirmation": {
            "current_status": "AP_EMAIL_CANDIDATE_NEEDS_CONFIRMATION",
            "candidate": "Annette.Sunga@hilton.com",
            "required_operator_action": "Confirm recipient or provide replacement AP route.",
            "external_access": "No Gmail access or email send.",
        },
        "protected_coupa_screen_reference": {
            "target_kind": "COUPA_PO_SCREEN_REFERENCE",
            "normal_read_model_body_allowed": False,
            "allowed_capture": "metadata/path/hash/protected ref only",
            "guardian_review_required": True,
        },
        "operator_text_confirmation": {
            "allowed_confirmation_examples": (
                "No PO known pending proof",
                "AP route confirmed as operator-provided address",
            ),
            "proof_still_possible": True,
            "external_send": False,
        },
        "delivery_readiness_after_facts_captured": {
            "if_po_or_ap_unresolved": "delivery remains blocked",
            "if_ap_confirmed_and_artifact_exists": "email draft readiness may advance in a future gated lane",
            "coupa_posture": "blocked until protected access and PO/reference posture resolve",
        },
    }


def _all_external_authority_false() -> bool:
    allowed_true = {
        "local_generated_read_models_allowed",
        "local_receipt_target_modeling_allowed",
        "protected_evidence_reference_modeling_allowed",
        "tests_allowed",
    }
    return all(
        value is False
        for key, value in AUTHORITY_BOUNDARY.items()
        if key not in allowed_true and isinstance(value, bool)
    )


def _protected_refs_have_guardian_when_required(
    targets: tuple[CapitalHiltonProtectedEvidenceReferenceTarget, ...],
) -> bool:
    protected_kinds = {"COUPA_PO_SCREEN_REFERENCE", "AP_EMAIL_ROUTE_REFERENCE", "EMAIL_THREAD_REFERENCE"}
    return all(
        target.guardian_review_required
        for target in targets
        if target.target_kind in protected_kinds
    )


def build_capital_hilton_delivery_facts_capture_bridge(
    *,
    generated_at: str | None = None,
    repo_root: str | Path = ROOT,
) -> dict[str, Any]:
    artifact_readiness = _load_artifact_readiness(repo_root=repo_root)
    bridge = build_capture_bridge(artifact_readiness)
    po_block = build_po_coupa_capture_block()
    ap_block = build_ap_email_route_capture_block()
    protected_targets = build_protected_reference_targets()
    receipt_targets = build_receipt_targets()
    readiness = build_delivery_readiness(artifact_readiness)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at or utc_now(),
        "operator_summary": (
            "Capital Hilton has captured invoice dates/rate and a local invoice preview rail. "
            "This bridge defines the remaining delivery-fact capture blocks for PO/Coupa, AP/email route, "
            "and protected evidence references without accessing external systems."
        ),
        "current_captured_invoice_state": {
            "workflow_session_ref": WORKFLOW_SESSION_REF,
            "performance_dates": CAPTURED_DATES,
            "show_count": 4,
            "rate_per_show": RATE_PER_SHOW,
            "subtotal": SUBTOTAL,
            "external_action_performed": False,
        },
        "artifact_readiness_source": artifact_readiness,
        "model_schemas": {
            "delivery_facts_capture_bridge": {
                "model_name": "CapitalHiltonDeliveryFactsCaptureBridge",
                "required_fields": list(REQUIRED_BRIDGE_FIELDS),
            },
            "po_coupa_capture_block": {
                "model_name": "CapitalHiltonPOCoupaCaptureBlock",
                "required_fields": list(REQUIRED_PO_BLOCK_FIELDS),
                "allowed_postures": list(PO_COUPA_POSTURES),
            },
            "ap_email_route_capture_block": {
                "model_name": "CapitalHiltonAPEmailRouteCaptureBlock",
                "required_fields": list(REQUIRED_AP_BLOCK_FIELDS),
                "allowed_postures": list(AP_EMAIL_POSTURES),
            },
            "protected_evidence_reference_target": {
                "model_name": "CapitalHiltonProtectedEvidenceReferenceTarget",
                "required_fields": list(REQUIRED_PROTECTED_REFERENCE_FIELDS),
                "target_kinds": list(PROTECTED_TARGET_KINDS),
            },
            "delivery_facts_receipt_target": {
                "model_name": "CapitalHiltonDeliveryFactsReceiptTarget",
                "required_fields": list(REQUIRED_RECEIPT_TARGET_FIELDS),
                "receipt_types": list(RECEIPT_TYPES),
            },
            "delivery_facts_readiness": {
                "model_name": "CapitalHiltonDeliveryFactsReadiness",
                "required_fields": list(REQUIRED_READINESS_FIELDS),
            },
        },
        "delivery_facts_capture_bridge": asdict(bridge),
        "po_coupa_capture_block": asdict(po_block),
        "ap_email_route_capture_block": asdict(ap_block),
        "protected_evidence_reference_targets": [asdict(target) for target in protected_targets],
        "delivery_facts_receipt_targets": [asdict(target) for target in receipt_targets],
        "delivery_facts_readiness": asdict(readiness),
        "examples": build_examples(),
        "relationship_to_existing_contracts": {
            "capital_hilton_invoice_delivery_steel_thread": "names delivery rails and external blockers",
            "capital_hilton_invoice_artifact_generator": "provides local artifact preview/readiness source",
            "capital_hilton_protected_proof_intake": "upstream protected proof metadata posture",
            "capital_hilton_coupa_po_retrieval_automation_candidate": "future Coupa/PO discovery automation candidate; no authority here",
            "guided_capture_protected_evidence_path_contract": "source posture for metadata-only protected references",
            "workflow_block_intent_live_draft_contract": "delivery fact blocks can later become live drafts",
            "mission_control_capture_request_intake": "pattern for future bounded capture requests",
            "bridge_routing_operator_attention_contract": "Finance World route, not Helm troubleshooting",
            "operator_question_assist_scope_expansion_contract": "can explain PO/Coupa/AP terms without hiding jargon",
        },
        "writer_posture": {
            "actual_local_receipt_state_write_performed": False,
            "existing_safe_writer_for_delivery_facts_found": False,
            "follow_up_writer_lane_required": (
                "Add a narrow delivery-facts writer for proof_po_reference and ap_email_route only after "
                "Mission Control emits structured operator-confirmed capture requests."
            ),
        },
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "all_external_authority_false": _all_external_authority_false(),
        },
        "machine_proof": {
            "po_coupa_capture_block_exists": True,
            "ap_email_route_capture_block_exists": True,
            "protected_evidence_reference_target_exists": True,
            "delivery_facts_receipt_target_exists": True,
            "delivery_facts_readiness_exists": True,
            "po_unknown_needs_discovery_example_exists": True,
            "ap_route_candidate_confirmation_example_exists": True,
            "protected_coupa_reference_example_exists": True,
            "operator_text_confirmation_example_exists": True,
            "normal_read_model_excludes_protected_body_content": all(
                not target.normal_read_model_body_allowed
                for target in protected_targets
                if target.target_kind != "OPERATOR_TEXT_CONFIRMATION"
            ),
            "credentials_cookies_tokens_forbidden": all(
                "credential fields" in target.forbidden_material
                and "session cookies" in target.forbidden_material
                and "access tokens" in target.forbidden_material
                for target in protected_targets
            ),
            "guardian_review_required_for_protected_evidence": _protected_refs_have_guardian_when_required(
                protected_targets
            ),
            "email_coupa_readiness_blocked_when_required_facts_missing": readiness.email_delivery_readiness.startswith(
                "BLOCKED"
            )
            and readiness.coupa_submission_readiness.startswith("BLOCKED"),
            "all_external_authority_false": _all_external_authority_false(),
            "credential_material_included": False,
            "protected_body_content_included": False,
            "raw_screenshot_or_email_body_included": False,
            "current_write_flags_false": all(
                target.current_write_authority is False and target.current_external_authority is False
                for target in receipt_targets
            ),
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_capital_hilton_delivery_facts_capture_bridge(payload: dict[str, Any]) -> str:
    state = payload["current_captured_invoice_state"]
    bridge = payload["delivery_facts_capture_bridge"]
    readiness = payload["delivery_facts_readiness"]
    ap_block = payload["ap_email_route_capture_block"]
    po_block = payload["po_coupa_capture_block"]
    lines = [
        "# Capital Hilton Delivery Facts Capture Bridge v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        (
            "OpenClaw already has the four Capital Hilton performance dates, $400/show, and a $1,600 "
            "subtotal in local captured state. This rail asks the remaining safe delivery questions: "
            "what is the PO/Coupa posture, who is the AP/email route, and what protected proof reference "
            "backs that up."
        ),
        "",
        "It does not log into Coupa or Gmail, read private bodies, send email, submit approval, or handle credentials.",
        "",
        "## Current Captured State",
        "",
        f"- Dates: `{', '.join(state['performance_dates'])}`",
        f"- Rate: `{state['rate_per_show']['display']}`",
        f"- Subtotal: `${state['subtotal']['amount']:,}`",
        f"- Artifact/readiness ref: `{bridge['artifact_ref_or_readiness_ref']}`",
        "",
        "## Capture Blocks",
        "",
        f"- PO/Coupa block: `{po_block['current_status']}`",
        f"- AP/email route block: `{ap_block['current_status']}`",
        "- Protected evidence: metadata references only, not raw protected content.",
        "",
        "## Candidate AP Route",
        "",
    ]
    lines.extend(
        f"- `{candidate['address']}` - {candidate['candidate_status']}"
        for candidate in ap_block["email_route_candidates"]
    )
    lines.extend(
        [
            "",
            "## Still Blocked",
            "",
        ]
    )
    lines.extend(f"- {blocker}" for blocker in readiness["remaining_blockers"])
    lines.extend(
        [
            "",
            "## Writer Posture",
            "",
            (
                "No delivery-fact receipt/state write happened in this lane. The next backend lane should add a "
                "narrow writer for PO/Coupa posture and AP/email route capture requests."
            ),
            "",
            "## Authority",
            "",
            f"- Coupa/browser access: `{str(payload['authority_boundary']['coupa_access_allowed'] or payload['authority_boundary']['browser_automation_allowed']).lower()}`",
            f"- Gmail/email send: `{str(payload['authority_boundary']['gmail_access_allowed'] or payload['authority_boundary']['email_send_allowed']).lower()}`",
            f"- Credential handling: `{str(payload['authority_boundary']['credential_handling_allowed']).lower()}`",
            f"- Model/tool/runtime: `{str(payload['authority_boundary']['model_call_allowed'] or payload['authority_boundary']['tool_execution_allowed'] or payload['authority_boundary']['runtime_dispatch_allowed']).lower()}`",
            f"- Raw body ingestion: `{str(payload['authority_boundary']['raw_body_ingestion_allowed']).lower()}`",
            "",
            "## Next Safe Move",
            "",
            readiness["next_safe_move"],
            "",
        ]
    )
    return "\n".join(lines)


def export_capital_hilton_delivery_facts_capture_bridge(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> CapitalHiltonDeliveryFactsCaptureBridgeExportResult:
    payload = build_capital_hilton_delivery_facts_capture_bridge(
        generated_at=generated_at,
        repo_root=repo_root,
    )
    root = _repo_path(export_root, repo_root=repo_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_capital_hilton_delivery_facts_capture_bridge(payload), encoding="utf-8")
    return CapitalHiltonDeliveryFactsCaptureBridgeExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        current_delivery_status=payload["delivery_facts_capture_bridge"]["current_delivery_status"],
        po_coupa_status=payload["delivery_facts_readiness"]["po_coupa_status"],
        ap_email_route_status=payload["delivery_facts_readiness"]["ap_email_route_status"],
        external_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Capital Hilton delivery facts capture bridge.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_capital_hilton_delivery_facts_capture_bridge(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "current_delivery_status": result.current_delivery_status,
        "po_coupa_status": result.po_coupa_status,
        "ap_email_route_status": result.ap_email_route_status,
        "external_authority_granted": result.external_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        payload = build_capital_hilton_delivery_facts_capture_bridge(repo_root=args.repo_root)
        print(format_capital_hilton_delivery_facts_capture_bridge(payload), end="")
    return 0


__all__ = [
    "AP_EMAIL_POSTURES",
    "ARTIFACT_READINESS_REF",
    "AUTHORITY_BOUNDARY",
    "CAPTURED_DATES",
    "CONTRACT_STATUS",
    "DEFAULT_EXPORT_ROOT",
    "JSON_EXPORT_NAME",
    "LANE",
    "OPERATOR_EXPORT_NAME",
    "PO_COUPA_POSTURES",
    "PROTECTED_TARGET_KINDS",
    "RATE_PER_SHOW",
    "READ_MODEL_ID",
    "RECEIPT_TYPES",
    "REQUIRED_AP_BLOCK_FIELDS",
    "REQUIRED_BRIDGE_FIELDS",
    "REQUIRED_PO_BLOCK_FIELDS",
    "REQUIRED_PROTECTED_REFERENCE_FIELDS",
    "REQUIRED_READINESS_FIELDS",
    "REQUIRED_RECEIPT_TARGET_FIELDS",
    "SCHEMA_VERSION",
    "SUBTOTAL",
    "WORKFLOW_SESSION_REF",
    "CapitalHiltonAPEmailRouteCaptureBlock",
    "CapitalHiltonDeliveryFactsCaptureBridge",
    "CapitalHiltonDeliveryFactsCaptureBridgeExportResult",
    "CapitalHiltonDeliveryFactsReadiness",
    "CapitalHiltonDeliveryFactsReceiptTarget",
    "CapitalHiltonPOCoupaCaptureBlock",
    "CapitalHiltonProtectedEvidenceReferenceTarget",
    "build_ap_email_route_capture_block",
    "build_capital_hilton_delivery_facts_capture_bridge",
    "build_capture_bridge",
    "build_delivery_readiness",
    "build_examples",
    "build_po_coupa_capture_block",
    "build_protected_reference_targets",
    "build_receipt_targets",
    "export_capital_hilton_delivery_facts_capture_bridge",
    "format_capital_hilton_delivery_facts_capture_bridge",
    "main",
    "stable_json",
]
