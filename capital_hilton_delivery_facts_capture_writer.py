"""Capital Hilton delivery facts capture writer.

This is a narrow local SQLite writer for the delivery-fact postures that sit
after the Capital Hilton invoice preview rail:

- PO/Coupa/payment reference posture
- AP/email route posture
- protected evidence reference posture

It writes only local receipt/state rows for enabled Capital Hilton delivery-fact
adapters. It does not access Coupa, Gmail, browser sessions, credentials,
network services, agents, tools, queues, runtimes, invoice send, approval
submission, or raw protected bodies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "capital_hilton_delivery_facts_capture_writer_v0"
READ_MODEL_ID = "capital_hilton_delivery_facts_capture_writer"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "NARROW_LOCAL_SQLITE_CAPTURE_FOR_DELIVERY_FACT_POSTURES"

WORKFLOW_SESSION_REF = "capital_hilton_invoice_workflow_session"
WORLD = "Finance"
LANE = "Capital Hilton"
INVOICE_PACKET_REF = "capital_hilton_invoice_packet_four_show_local_capture"
ARTIFACT_PREVIEW_REF = "capital_hilton_invoice_artifact_candidate_markdown_preview_four_show"
ARTIFACT_PREVIEW_PATH = (
    "generated/finance_packets/capital_hilton_invoice_artifact_preview_v0/"
    "CAPITAL_HILTON_INVOICE_PREVIEW.md"
)
ARTIFACT_PREVIEW_HASH = "sha256:a135264f8df31f762170ea53f50d74d44d08cfe1ee95dfc8fd318fad178970fc"

CAPTURED_DATES = ("2026-05-08", "2026-05-15", "2026-05-22", "2026-05-29")
RATE_PER_SHOW = {"amount": 400, "currency": "USD", "unit": "show", "display": "$400/show"}
SUBTOTAL = {"amount": 1600, "currency": "USD", "calculation": "4 shows x $400/show"}

VALIDATION_STATUSES = (
    "VALID_FOR_LOCAL_CAPTURE",
    "DUPLICATE_NOOP",
    "NEEDS_CLARIFICATION",
    "NEEDS_PROOF",
    "UNSUPPORTED_BLOCK",
    "UNSUPPORTED_OPERATION",
    "BLOCKED_BY_AUTHORITY",
    "INVALID_PAYLOAD",
    "UNKNOWN_FAIL_CLOSED",
)

WRITE_STATUSES = (
    "WRITTEN_TO_LOCAL_LEDGER",
    "WRITTEN_TO_TEST_LEDGER",
    "VALIDATED_BUT_WRITE_BLOCKED",
    "DUPLICATE_NOOP",
    "BLOCKED_FAIL_CLOSED",
)

REQUIRED_CAPTURE_REQUEST_FIELDS = (
    "capture_request_id",
    "origin_surface",
    "origin_actor",
    "workflow_session_ref",
    "world",
    "lane",
    "block_id",
    "operation",
    "current_posture",
    "proposed_posture",
    "proposed_value",
    "protected_reference_metadata",
    "receipt_type_requested",
    "idempotency_key",
    "payload_hash",
    "authority_scope_requested",
    "blocked_actions",
    "next_safe_move",
)

OPTIONAL_CAPTURE_REQUEST_FIELDS = (
    "idempotency_key_basis",
    "payload_hash_basis",
    "request_created_at_policy",
    "source_channel",
    "client_ref",
    "tenant_ref",
    "world_ref",
    "lane_ref",
    "current_person_profile_ref",
    "origin_app",
    "fronting_agent",
    "addressed_actor",
    "assigned_roles",
    "role_based_actor_refs",
)

REQUIRED_VALIDATION_FIELDS = (
    "validation_id",
    "capture_request_ref",
    "validation_status",
    "normalized_request",
    "accepted_adapter_ref",
    "rejected_reason",
    "ambiguity_flags",
    "duplicate_detection",
    "precondition_results",
    "required_receipt_type",
    "write_allowed",
    "external_execution_allowed",
    "next_safe_move",
)

REQUIRED_RECEIPT_PAYLOAD_FIELDS = (
    "receipt_payload_id",
    "receipt_type",
    "workflow_session_ref",
    "block_id",
    "previous_posture",
    "new_posture",
    "proposed_value",
    "protected_reference_metadata",
    "source_capture_request_ref",
    "proof_status_after_capture",
    "payload_hash",
    "idempotency_key",
    "authority_boundary",
    "next_safe_move",
)

REQUIRED_STATE_UPDATE_TARGET_FIELDS = (
    "state_update_target_id",
    "receipt_payload_ref",
    "canonical_workflow_state_ref",
    "block_state_before",
    "block_state_after",
    "field_updates",
    "delivery_readiness_effect",
    "proof_requirements_after_update",
    "downstream_invalidations",
    "current_state_write_authority",
    "next_safe_move",
)

REQUIRED_READBACK_FIELDS = (
    "readback_id",
    "write_status",
    "workflow_session_ref",
    "block_id",
    "receipt_type",
    "previous_posture",
    "captured_posture",
    "captured_value",
    "protected_reference_refs",
    "payload_hash",
    "idempotency_key",
    "duplicate_retry_result",
    "delivery_readiness_after_capture",
    "external_action_performed",
    "next_safe_move",
)

REQUIRED_CLOSEOUT_FIELDS = (
    "closeout_id",
    "delivery_fact_readback_refs",
    "what_openclaw_knows_now",
    "what_remains_unknown",
    "what_delivery_can_do_now",
    "what_remains_blocked",
    "suggested_next_operator_question",
    "suggested_next_safe_build_step",
    "next_safe_move",
)

BLOCKED_ACTIONS = (
    "Coupa access",
    "browser automation",
    "Gmail access",
    "email draft or send",
    "approval submission",
    "credential handling",
    "model/agent/tool/runtime/queue execution",
    "raw screenshot or email body ingestion",
    "file cleanup/archive/promotion",
)

FORBIDDEN_REQUEST_KEYS = (
    "command",
    "command_string",
    "shell",
    "shell_command",
    "execute",
    "raw_body",
    "private_body",
    "screenshot_body",
    "email_body",
    "message_body",
    "full_text",
    "file_contents",
    "base64_payload",
    "credential",
    "password",
    "session_cookie",
    "access_token",
    "ui_component_name",
    "screen_coordinates",
    "button_id",
    "screen_x",
    "screen_y",
    "mac_layout",
    "view_frame",
    "control_id",
)

SAFE_AP_EMAIL_ROUTE_CANDIDATES = (
    {
        "candidate_ref": "capital_hilton_annette_sunga_ap_candidate",
        "name": "Annette Sunga",
        "address": "Annette.Sunga@hilton.com",
        "candidate_status": "CANDIDATE_NEEDS_OPERATOR_CONFIRMATION",
        "allowed_use": "to_candidate_pending_review",
    },
    {
        "candidate_ref": "capital_hilton_chyna_hardin_cc_candidate",
        "name": "Chyna Hardin",
        "address": "Chyna.Hardin@hilton.com",
        "candidate_status": "CANDIDATE_NEEDS_OPERATOR_CONFIRMATION",
        "allowed_use": "cc_candidate_pending_review",
    },
    {
        "candidate_ref": "capital_hilton_lawrence_valcovic_cc_candidate",
        "name": "Lawrence / Will Valcovic",
        "address": "lawrencevalcovic@hilton.com",
        "candidate_status": "CANDIDATE_NEEDS_OPERATOR_CONFIRMATION",
        "allowed_use": "cc_candidate_pending_review",
    },
)

PROTECTED_REFERENCE_ALLOWED_METADATA_KEYS = (
    "target_kind",
    "reference_status",
    "source_hint",
    "source_card_ref",
    "protected_storage_ref",
    "redacted_source_label",
    "path",
    "sha256",
    "normal_read_model_body_allowed",
    "guardian_review_required",
)

AUTHORITY_BOUNDARY = {
    "local_delivery_fact_write_allowed_for_enabled_adapters": True,
    "test_delivery_fact_write_allowed": True,
    "enabled_adapter_blocks": ("proof_po_reference", "ap_email_route", "protected_evidence_reference"),
    "generic_delivery_write_allowed": False,
    "unsupported_block_write_allowed": False,
    "email_send_allowed": False,
    "email_draft_allowed": False,
    "approval_submission_allowed": False,
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
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

SUPPORTED_BLOCK_ADAPTERS: dict[str, dict[str, Any]] = {
    "proof_po_reference": {
        "adapter_ref": "capital_hilton_delivery_facts_capture_writer.po_coupa_sqlite_adapter",
        "allowed_operations": (
            "set_needs_discovery",
            "set_no_po_known_pending_proof",
            "set_coupa_required_unknown",
            "set_po_reference_candidate",
            "set_coupa_reference_candidate",
        ),
        "receipt_types": (
            "OPERATOR_PROOF_PO_DISCOVERY_POSTURE",
            "OPERATOR_NO_PO_KNOWN_POSTURE",
            "OPERATOR_COUPA_REQUIRED_UNKNOWN",
            "OPERATOR_PO_REFERENCE_CANDIDATE",
            "OPERATOR_COUPA_REFERENCE_CANDIDATE",
        ),
        "operation_posture": {
            "set_needs_discovery": "NEEDS_DISCOVERY",
            "set_no_po_known_pending_proof": "NO_PO_KNOWN_PENDING_PROOF",
            "set_coupa_required_unknown": "COUPA_REQUIRED_UNKNOWN",
            "set_po_reference_candidate": "PO_REFERENCE_KNOWN",
            "set_coupa_reference_candidate": "COUPA_REFERENCE_KNOWN",
        },
    },
    "ap_email_route": {
        "adapter_ref": "capital_hilton_delivery_facts_capture_writer.ap_email_route_sqlite_adapter",
        "allowed_operations": (
            "set_ap_route_candidate_needs_confirmation",
            "confirm_ap_email_route",
            "set_ap_route_unknown",
            "set_ap_route_protected_reference_required",
        ),
        "receipt_types": (
            "OPERATOR_AP_EMAIL_ROUTE_CANDIDATE",
            "OPERATOR_AP_EMAIL_ROUTE_CONFIRMATION",
            "OPERATOR_AP_ROUTE_UNKNOWN",
            "OPERATOR_AP_ROUTE_PROTECTED_REFERENCE_REQUIRED",
        ),
        "operation_posture": {
            "set_ap_route_candidate_needs_confirmation": "AP_EMAIL_CANDIDATE_NEEDS_CONFIRMATION",
            "confirm_ap_email_route": "AP_EMAIL_CONFIRMED",
            "set_ap_route_unknown": "AP_ROUTE_UNKNOWN",
            "set_ap_route_protected_reference_required": "AP_ROUTE_PROTECTED_REFERENCE_REQUIRED",
        },
    },
    "protected_evidence_reference": {
        "adapter_ref": "capital_hilton_delivery_facts_capture_writer.protected_reference_sqlite_adapter",
        "allowed_operations": (
            "set_protected_evidence_reference_target",
            "set_protected_reference_required",
            "set_source_card_reference_candidate",
            "set_operator_text_confirmation_reference",
        ),
        "receipt_types": (
            "PROTECTED_EVIDENCE_REFERENCE_RECEIPT",
            "PROTECTED_EVIDENCE_REQUIRED_RECEIPT",
            "SOURCE_CARD_REFERENCE_CANDIDATE",
            "OPERATOR_TEXT_CONFIRMATION_REFERENCE",
        ),
        "operation_posture": {
            "set_protected_evidence_reference_target": "PROTECTED_EVIDENCE_REFERENCE_TARGET",
            "set_protected_reference_required": "PROTECTED_REFERENCE_REQUIRED",
            "set_source_card_reference_candidate": "SOURCE_CARD_REFERENCE_CANDIDATE",
            "set_operator_text_confirmation_reference": "OPERATOR_TEXT_CONFIRMATION_REFERENCE",
        },
    },
}


@dataclass(frozen=True)
class CapitalHiltonDeliveryFactCaptureRequest:
    capture_request_id: str
    origin_surface: str
    origin_actor: str
    workflow_session_ref: str
    world: str
    lane: str
    block_id: str
    operation: str
    current_posture: str
    proposed_posture: str
    proposed_value: dict[str, Any]
    protected_reference_metadata: dict[str, Any]
    receipt_type_requested: str
    idempotency_key: str
    payload_hash: str
    authority_scope_requested: dict[str, bool]
    blocked_actions: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonDeliveryFactIntakeValidation:
    validation_id: str
    capture_request_ref: str
    validation_status: str
    normalized_request: dict[str, Any]
    accepted_adapter_ref: str | None
    rejected_reason: str | None
    ambiguity_flags: tuple[str, ...]
    duplicate_detection: dict[str, Any]
    precondition_results: tuple[dict[str, Any], ...]
    required_receipt_type: str
    write_allowed: bool
    external_execution_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonDeliveryFactReceiptPayload:
    receipt_payload_id: str
    receipt_type: str
    workflow_session_ref: str
    block_id: str
    previous_posture: str
    new_posture: str
    proposed_value: dict[str, Any]
    protected_reference_metadata: dict[str, Any]
    source_capture_request_ref: str
    proof_status_after_capture: str
    payload_hash: str
    idempotency_key: str
    authority_boundary: dict[str, Any]
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonDeliveryFactStateUpdateTarget:
    state_update_target_id: str
    receipt_payload_ref: str
    canonical_workflow_state_ref: str
    block_state_before: str
    block_state_after: str
    field_updates: dict[str, Any]
    delivery_readiness_effect: dict[str, Any]
    proof_requirements_after_update: tuple[str, ...]
    downstream_invalidations: tuple[str, ...]
    current_state_write_authority: bool
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonDeliveryFactCaptureReadback:
    readback_id: str
    write_status: str
    workflow_session_ref: str
    block_id: str
    receipt_type: str
    previous_posture: str
    captured_posture: str
    captured_value: dict[str, Any]
    protected_reference_refs: tuple[str, ...]
    payload_hash: str
    idempotency_key: str
    duplicate_retry_result: str
    delivery_readiness_after_capture: dict[str, Any]
    external_action_performed: bool
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonDeliveryFactsCloseout:
    closeout_id: str
    delivery_fact_readback_refs: tuple[str, ...]
    what_openclaw_knows_now: dict[str, Any]
    what_remains_unknown: tuple[str, ...]
    what_delivery_can_do_now: tuple[str, ...]
    what_remains_blocked: tuple[str, ...]
    suggested_next_operator_question: str
    suggested_next_safe_build_step: str
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonDeliveryFactsCaptureWriterExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    validation_statuses: tuple[str, ...]
    write_statuses: tuple[str, ...]
    po_coupa_posture: str | None
    ap_email_route_posture: str | None
    external_action_performed: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _sha256(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _short_hash(payload: Any) -> str:
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()[:20]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return _sha256(clone)


def _ledger_path(db_path: str | Path | None = None) -> Path:
    path = Path(db_path or DEFAULT_DB_PATH)
    if path.is_absolute():
        return path
    return ROOT / path


def _json_loads(value: str | None) -> Any:
    if not value:
        return None
    return json.loads(value)


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _request_hash_basis(
    request_or_payload: CapitalHiltonDeliveryFactCaptureRequest | Mapping[str, Any],
) -> dict[str, Any]:
    request = (
        asdict(request_or_payload)
        if isinstance(request_or_payload, CapitalHiltonDeliveryFactCaptureRequest)
        else dict(request_or_payload)
    )
    return {
        "origin_surface": request.get("origin_surface"),
        "origin_actor": request.get("origin_actor"),
        "workflow_session_ref": request.get("workflow_session_ref"),
        "world": request.get("world"),
        "lane": request.get("lane"),
        "block_id": request.get("block_id"),
        "operation": request.get("operation"),
        "current_posture": request.get("current_posture"),
        "proposed_posture": request.get("proposed_posture"),
        "proposed_value": request.get("proposed_value"),
        "protected_reference_metadata": request.get("protected_reference_metadata"),
        "receipt_type_requested": request.get("receipt_type_requested"),
        "authority_scope_requested": request.get("authority_scope_requested"),
    }


def derive_payload_hash(request_or_payload: CapitalHiltonDeliveryFactCaptureRequest | Mapping[str, Any]) -> str:
    return _sha256(_request_hash_basis(request_or_payload))


def derive_idempotency_key(
    request_or_payload: CapitalHiltonDeliveryFactCaptureRequest | Mapping[str, Any],
) -> str:
    request = (
        asdict(request_or_payload)
        if isinstance(request_or_payload, CapitalHiltonDeliveryFactCaptureRequest)
        else dict(request_or_payload)
    )
    digest = _short_hash(
        {
            "workflow_session_ref": request.get("workflow_session_ref"),
            "block_id": request.get("block_id"),
            "operation": request.get("operation"),
            "receipt_type_requested": request.get("receipt_type_requested"),
            "proposed_posture": request.get("proposed_posture"),
            "proposed_value": request.get("proposed_value"),
            "protected_reference_metadata": request.get("protected_reference_metadata"),
        }
    )
    return (
        f"capital_hilton_delivery_fact:{request.get('workflow_session_ref')}:"
        f"{request.get('block_id')}:{request.get('operation')}:{request.get('receipt_type_requested')}:{digest}"
    )


def _authority_scope() -> dict[str, bool]:
    return {
        "local_delivery_fact_capture": True,
        "external_execution": False,
        "email_send": False,
        "email_draft": False,
        "coupa_access": False,
        "gmail_access": False,
        "protected_body_ingestion": False,
        "model_or_tool_execution": False,
    }


def make_capture_request(
    *,
    capture_request_id: str,
    block_id: str,
    operation: str,
    current_posture: str,
    proposed_posture: str,
    proposed_value: dict[str, Any],
    protected_reference_metadata: dict[str, Any],
    receipt_type_requested: str,
    origin_surface: str = "mission_control_future_or_local_fixture",
    origin_actor: str = "winship_operator",
) -> CapitalHiltonDeliveryFactCaptureRequest:
    basis: dict[str, Any] = {
        "capture_request_id": capture_request_id,
        "origin_surface": origin_surface,
        "origin_actor": origin_actor,
        "workflow_session_ref": WORKFLOW_SESSION_REF,
        "world": WORLD,
        "lane": LANE,
        "block_id": block_id,
        "operation": operation,
        "current_posture": current_posture,
        "proposed_posture": proposed_posture,
        "proposed_value": proposed_value,
        "protected_reference_metadata": protected_reference_metadata,
        "receipt_type_requested": receipt_type_requested,
        "authority_scope_requested": _authority_scope(),
        "blocked_actions": BLOCKED_ACTIONS,
        "next_safe_move": "Validate and write through the enabled local delivery-fact SQLite adapter.",
    }
    return CapitalHiltonDeliveryFactCaptureRequest(
        **basis,
        idempotency_key=derive_idempotency_key(basis),
        payload_hash=derive_payload_hash(basis),
    )


def fixture_po_coupa_needs_discovery_request() -> CapitalHiltonDeliveryFactCaptureRequest:
    return make_capture_request(
        capture_request_id="capital_hilton_po_coupa_needs_discovery",
        block_id="proof_po_reference",
        operation="set_needs_discovery",
        current_posture="NEEDS_DISCOVERY",
        proposed_posture="NEEDS_DISCOVERY",
        proposed_value={
            "po_reference": None,
            "coupa_reference": None,
            "proof_status": "needs_discovery",
            "coupa_access_performed": False,
        },
        protected_reference_metadata={},
        receipt_type_requested="OPERATOR_PROOF_PO_DISCOVERY_POSTURE",
    )


def fixture_ap_route_candidate_request() -> CapitalHiltonDeliveryFactCaptureRequest:
    return make_capture_request(
        capture_request_id="capital_hilton_ap_route_candidate_needs_confirmation",
        block_id="ap_email_route",
        operation="set_ap_route_candidate_needs_confirmation",
        current_posture="AP_EMAIL_CANDIDATE_NEEDS_CONFIRMATION",
        proposed_posture="AP_EMAIL_CANDIDATE_NEEDS_CONFIRMATION",
        proposed_value={
            "email_route_candidates": SAFE_AP_EMAIL_ROUTE_CANDIDATES,
            "confirmed_recipient": None,
            "proof_status": "candidate_not_confirmed",
        },
        protected_reference_metadata={},
        receipt_type_requested="OPERATOR_AP_EMAIL_ROUTE_CANDIDATE",
    )


def fixture_protected_reference_required_request() -> CapitalHiltonDeliveryFactCaptureRequest:
    return make_capture_request(
        capture_request_id="capital_hilton_protected_reference_required_for_delivery_facts",
        block_id="protected_evidence_reference",
        operation="set_protected_reference_required",
        current_posture="PROTECTED_REFERENCE_REQUIRED",
        proposed_posture="PROTECTED_REFERENCE_REQUIRED",
        proposed_value={
            "protected_reference_status": "required_before_delivery_finalization",
            "normal_read_model_body_allowed": False,
            "guardian_review_required": True,
        },
        protected_reference_metadata={
            "target_kind": "COUPA_PO_SCREEN_REFERENCE",
            "reference_status": "REQUIRED_NOT_CAPTURED",
            "source_hint": "PO/Coupa/payment reference evidence may require protected screen reference later.",
            "normal_read_model_body_allowed": False,
            "guardian_review_required": True,
        },
        receipt_type_requested="PROTECTED_EVIDENCE_REQUIRED_RECEIPT",
    )


def default_fixture_capture_requests() -> tuple[CapitalHiltonDeliveryFactCaptureRequest, ...]:
    return (
        fixture_po_coupa_needs_discovery_request(),
        fixture_ap_route_candidate_request(),
        fixture_protected_reference_required_request(),
    )


def _contains_forbidden_key(value: Any) -> str | None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_REQUEST_KEYS:
                return str(key)
            nested = _contains_forbidden_key(child)
            if nested:
                return nested
    elif isinstance(value, (list, tuple)):
        for child in value:
            nested = _contains_forbidden_key(child)
            if nested:
                return nested
    return None


def _request_from_payload(payload: Mapping[str, Any]) -> CapitalHiltonDeliveryFactCaptureRequest:
    required_direct_fields = tuple(
        field for field in REQUIRED_CAPTURE_REQUEST_FIELDS if field not in {"idempotency_key", "payload_hash"}
    )
    missing = [field for field in required_direct_fields if field not in payload]
    if "idempotency_key" not in payload and "idempotency_key_basis" not in payload:
        missing.append("idempotency_key")
    if "payload_hash" not in payload and "payload_hash_basis" not in payload:
        missing.append("payload_hash")
    if missing:
        raise ValueError(f"missing required field: {missing[0]}")
    unknown = sorted(set(payload) - set(REQUIRED_CAPTURE_REQUEST_FIELDS) - set(OPTIONAL_CAPTURE_REQUEST_FIELDS))
    if unknown:
        raise ValueError(f"unsupported top-level field: {unknown[0]}")
    forbidden = _contains_forbidden_key(payload)
    if forbidden:
        raise ValueError(f"request contains forbidden field: {forbidden}")
    authority = payload["authority_scope_requested"]
    if not isinstance(authority, Mapping):
        raise ValueError("authority_scope_requested must be an object")
    request = CapitalHiltonDeliveryFactCaptureRequest(
        capture_request_id=str(payload["capture_request_id"]),
        origin_surface=str(payload["origin_surface"]),
        origin_actor=str(payload["origin_actor"]),
        workflow_session_ref=str(payload["workflow_session_ref"]),
        world=str(payload["world"]),
        lane=str(payload["lane"]),
        block_id=str(payload["block_id"]),
        operation=str(payload["operation"]),
        current_posture=str(payload["current_posture"]),
        proposed_posture=str(payload["proposed_posture"]),
        proposed_value=dict(payload["proposed_value"]),
        protected_reference_metadata=dict(payload["protected_reference_metadata"]),
        receipt_type_requested=str(payload["receipt_type_requested"]),
        idempotency_key=str(payload.get("idempotency_key", "")),
        payload_hash=str(payload.get("payload_hash", "")),
        authority_scope_requested={str(key): bool(value) for key, value in authority.items()},
        blocked_actions=tuple(str(item) for item in payload["blocked_actions"]),
        next_safe_move=str(payload["next_safe_move"]),
    )
    return replace(
        request,
        idempotency_key=request.idempotency_key or derive_idempotency_key(request),
        payload_hash=request.payload_hash or derive_payload_hash(request),
    )


def load_capture_request_file(path: str | Path) -> CapitalHiltonDeliveryFactCaptureRequest:
    request_path = Path(path)
    if not request_path.is_file():
        raise ValueError(f"capture request file not found: {request_path}")
    try:
        payload = json.loads(request_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError("capture request file must contain a JSON object")
    return _request_from_payload(payload)


def _precondition(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"check": name, "passed": passed, "detail": detail}


def _validate_proposed_posture(
    request: CapitalHiltonDeliveryFactCaptureRequest,
    adapter: Mapping[str, Any],
) -> str | None:
    expected = adapter["operation_posture"].get(request.operation)
    if request.proposed_posture != expected:
        return "proposed posture does not match operation"
    if request.block_id == "proof_po_reference":
        if request.operation == "set_po_reference_candidate" and not request.proposed_value.get("po_reference"):
            return "PO reference candidate requires po_reference"
        if request.operation == "set_coupa_reference_candidate" and not request.proposed_value.get("coupa_reference"):
            return "Coupa reference candidate requires coupa_reference"
        if request.operation == "set_needs_discovery" and (
            request.proposed_value.get("po_reference") or request.proposed_value.get("coupa_reference")
        ):
            return "needs-discovery posture must not include a PO/Coupa reference value"
    if request.block_id == "ap_email_route":
        if request.operation == "confirm_ap_email_route":
            if not request.proposed_value.get("confirmed_recipient"):
                return "confirm_ap_email_route requires confirmed_recipient"
        if request.operation == "set_ap_route_candidate_needs_confirmation":
            if request.proposed_value.get("confirmed_recipient"):
                return "candidate-needs-confirmation must not mark a confirmed recipient"
            if not request.proposed_value.get("email_route_candidates"):
                return "candidate-needs-confirmation requires candidate route metadata"
    if request.block_id == "protected_evidence_reference":
        if request.protected_reference_metadata.get("normal_read_model_body_allowed") is not False:
            return "protected reference metadata must keep normal_read_model_body_allowed false"
        for key in request.protected_reference_metadata:
            if key not in PROTECTED_REFERENCE_ALLOWED_METADATA_KEYS:
                return f"unsupported protected reference metadata key: {key}"
    return None


def _normalized_delivery_value(request: CapitalHiltonDeliveryFactCaptureRequest) -> dict[str, Any]:
    if request.block_id == "proof_po_reference":
        return {
            "po_coupa_posture": request.proposed_posture,
            "po_reference": request.proposed_value.get("po_reference"),
            "coupa_reference": request.proposed_value.get("coupa_reference"),
            "proof_status": request.proposed_value.get("proof_status", "needs_proof"),
            "coupa_access_performed": False,
            "credential_handling_performed": False,
        }
    if request.block_id == "ap_email_route":
        return {
            "ap_email_route_posture": request.proposed_posture,
            "email_route_candidates": tuple(request.proposed_value.get("email_route_candidates", ())),
            "confirmed_recipient": request.proposed_value.get("confirmed_recipient"),
            "proof_status": request.proposed_value.get("proof_status", "needs_confirmation"),
            "gmail_access_performed": False,
            "email_send_performed": False,
        }
    if request.block_id == "protected_evidence_reference":
        return {
            "protected_evidence_posture": request.proposed_posture,
            "protected_reference_metadata": request.protected_reference_metadata,
            "normal_read_model_body_allowed": False,
            "guardian_review_required": bool(request.protected_reference_metadata.get("guardian_review_required")),
            "raw_body_stored": False,
        }
    raise ValueError(f"unsupported block: {request.block_id}")


def validate_capture_request(
    request: CapitalHiltonDeliveryFactCaptureRequest,
    *,
    existing_idempotency_keys: tuple[str, ...] = (),
) -> CapitalHiltonDeliveryFactIntakeValidation:
    status = "VALID_FOR_LOCAL_CAPTURE"
    rejected_reason: str | None = None
    normalized: dict[str, Any] = {}
    accepted_adapter_ref: str | None = None

    adapter = SUPPORTED_BLOCK_ADAPTERS.get(request.block_id)
    if request.idempotency_key in existing_idempotency_keys:
        status = "DUPLICATE_NOOP"
        rejected_reason = "Same idempotency key already captured; retry is a no-op."
    elif request.workflow_session_ref != WORKFLOW_SESSION_REF:
        status = "INVALID_PAYLOAD"
        rejected_reason = "Workflow session does not match Capital Hilton invoice workflow."
    elif request.world != WORLD or request.lane != LANE:
        status = "INVALID_PAYLOAD"
        rejected_reason = "World/lane does not match Finance / Capital Hilton."
    elif adapter is None:
        status = "UNSUPPORTED_BLOCK"
        rejected_reason = "Only delivery-fact adapters for PO/Coupa, AP/email route, and protected references are enabled."
    elif request.operation not in adapter["allowed_operations"]:
        status = "UNSUPPORTED_OPERATION"
        rejected_reason = "Operation is not enabled for this delivery-fact adapter."
    elif request.receipt_type_requested not in adapter["receipt_types"]:
        status = "INVALID_PAYLOAD"
        rejected_reason = "Requested receipt type is not allowed for this delivery-fact adapter."
    elif any(
        request.authority_scope_requested.get(key)
        for key in (
            "external_execution",
            "email_send",
            "email_draft",
            "approval_submission",
            "browser_automation",
            "coupa_access",
            "gmail_access",
            "telegram_send",
            "credential_handling",
            "protected_body_ingestion",
            "model_or_tool_execution",
            "runtime_dispatch",
        )
    ):
        status = "BLOCKED_BY_AUTHORITY"
        rejected_reason = "Capture request asked for authority outside local delivery-fact capture."
    elif request.idempotency_key != derive_idempotency_key(request):
        status = "INVALID_PAYLOAD"
        rejected_reason = "idempotency_key does not match stable request basis."
    elif request.payload_hash != derive_payload_hash(request):
        status = "INVALID_PAYLOAD"
        rejected_reason = "payload_hash does not match stable request basis."
    elif _contains_forbidden_key(asdict(request)):
        status = "INVALID_PAYLOAD"
        rejected_reason = "request includes forbidden protected/raw/private material key."
    else:
        posture_failure = _validate_proposed_posture(request, adapter)
        if posture_failure:
            status = "INVALID_PAYLOAD"
            rejected_reason = posture_failure
        else:
            normalized = _normalized_delivery_value(request)

    write_allowed = status == "VALID_FOR_LOCAL_CAPTURE"
    if write_allowed:
        accepted_adapter_ref = adapter["adapter_ref"] if adapter else None

    preconditions = (
        _precondition("supported_workflow", request.workflow_session_ref == WORKFLOW_SESSION_REF, "Capital Hilton invoice workflow only."),
        _precondition("supported_block", adapter is not None, "Only enabled delivery-fact blocks are writable."),
        _precondition("supported_operation", adapter is not None and request.operation in adapter["allowed_operations"], "Operation must match block adapter."),
        _precondition("stable_idempotency_key", request.idempotency_key == derive_idempotency_key(request), "Idempotency key binds session, block, operation, receipt type, posture, value, and metadata."),
        _precondition("stable_payload_hash", request.payload_hash == derive_payload_hash(request), "Payload hash excludes timestamps and raw bodies."),
        _precondition(
            "no_external_authority_requested",
            not any(
                request.authority_scope_requested.get(key)
                for key in (
                    "external_execution",
                    "email_send",
                    "email_draft",
                    "approval_submission",
                    "browser_automation",
                    "coupa_access",
                    "gmail_access",
                    "telegram_send",
                    "credential_handling",
                    "protected_body_ingestion",
                    "model_or_tool_execution",
                    "runtime_dispatch",
                )
            ),
            "Capture request is local only.",
        ),
    )

    return CapitalHiltonDeliveryFactIntakeValidation(
        validation_id=f"delivery_validation_{_short_hash((request.capture_request_id, request.payload_hash, status))}",
        capture_request_ref=request.capture_request_id,
        validation_status=status,
        normalized_request=normalized,
        accepted_adapter_ref=accepted_adapter_ref,
        rejected_reason=rejected_reason,
        ambiguity_flags=() if status in {"VALID_FOR_LOCAL_CAPTURE", "DUPLICATE_NOOP"} else ("fail_closed_until_corrected",),
        duplicate_detection={
            "idempotency_key": request.idempotency_key,
            "duplicate": status == "DUPLICATE_NOOP",
            "same_payload_policy": "no second receipt/state update",
        },
        precondition_results=preconditions,
        required_receipt_type=request.receipt_type_requested,
        write_allowed=write_allowed,
        external_execution_allowed=False,
        next_safe_move="Write to local delivery-fact SQLite adapter and read back state." if write_allowed else "Return fail-closed validation result.",
    )


def init_delivery_fact_capture_schema(db_path: str | Path | None = None) -> str:
    path_obj = _ledger_path(db_path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    init_business_ops_ledger(str(path_obj))
    conn = sqlite3.connect(str(path_obj))
    try:
        conn.execute(
            """
CREATE TABLE IF NOT EXISTS capital_hilton_delivery_fact_capture_receipts (
  receipt_id TEXT PRIMARY KEY,
  capture_request_id TEXT NOT NULL,
  workflow_session_ref TEXT NOT NULL,
  world TEXT NOT NULL,
  lane TEXT NOT NULL,
  block_id TEXT NOT NULL,
  operation TEXT NOT NULL,
  receipt_type TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  payload_hash TEXT NOT NULL,
  origin_surface TEXT NOT NULL,
  origin_actor TEXT NOT NULL,
  previous_posture TEXT NOT NULL,
  captured_posture TEXT NOT NULL,
  captured_value_json TEXT NOT NULL,
  protected_reference_metadata_json TEXT NOT NULL,
  authority_scope_json TEXT NOT NULL,
  external_action_performed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
)
""".strip()
        )
        conn.execute(
            """
CREATE TABLE IF NOT EXISTS capital_hilton_delivery_fact_state (
  state_id TEXT PRIMARY KEY,
  workflow_session_ref TEXT NOT NULL,
  world TEXT NOT NULL,
  lane TEXT NOT NULL,
  block_id TEXT NOT NULL,
  posture TEXT NOT NULL,
  value_json TEXT NOT NULL,
  protected_reference_metadata_json TEXT NOT NULL,
  receipt_ref TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(workflow_session_ref, block_id)
)
""".strip()
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_capital_hilton_delivery_fact_receipts_session ON capital_hilton_delivery_fact_capture_receipts(workflow_session_ref)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_capital_hilton_delivery_fact_state_session ON capital_hilton_delivery_fact_state(workflow_session_ref)"
        )
        conn.commit()
    finally:
        conn.close()
    return str(path_obj)


def _receipt_id(request: CapitalHiltonDeliveryFactCaptureRequest) -> str:
    return _row_id("ch_delivery_receipt", request.idempotency_key, request.payload_hash)


def _state_id(request: CapitalHiltonDeliveryFactCaptureRequest) -> str:
    return _row_id("ch_delivery_state", request.workflow_session_ref, request.block_id)


def _read_state_row(conn: sqlite3.Connection, workflow_session_ref: str, block_id: str) -> dict[str, Any] | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
SELECT state_id, workflow_session_ref, world, lane, block_id, posture, value_json,
       protected_reference_metadata_json, receipt_ref, payload_hash, updated_at
FROM capital_hilton_delivery_fact_state
WHERE workflow_session_ref=? AND block_id=?
""".strip(),
        (workflow_session_ref, block_id),
    ).fetchone()
    if row is None:
        return None
    return {
        "state_id": row["state_id"],
        "workflow_session_ref": row["workflow_session_ref"],
        "world": row["world"],
        "lane": row["lane"],
        "block_id": row["block_id"],
        "posture": row["posture"],
        "value": _json_loads(row["value_json"]),
        "protected_reference_metadata": _json_loads(row["protected_reference_metadata_json"]),
        "receipt_ref": row["receipt_ref"],
        "payload_hash": row["payload_hash"],
        "updated_at": row["updated_at"],
    }


def read_delivery_fact_state(
    workflow_session_ref: str = WORKFLOW_SESSION_REF,
    *,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    path = init_delivery_fact_capture_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
SELECT state_id, block_id, posture, value_json, protected_reference_metadata_json, receipt_ref, payload_hash, updated_at
FROM capital_hilton_delivery_fact_state
WHERE workflow_session_ref=?
ORDER BY block_id
""".strip(),
            (workflow_session_ref,),
        ).fetchall()
        return {
            row["block_id"]: {
                "state_id": row["state_id"],
                "posture": row["posture"],
                "value": _json_loads(row["value_json"]),
                "protected_reference_metadata": _json_loads(row["protected_reference_metadata_json"]),
                "receipt_ref": row["receipt_ref"],
                "payload_hash": row["payload_hash"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        }
    finally:
        conn.close()


def read_delivery_fact_receipts(
    workflow_session_ref: str = WORKFLOW_SESSION_REF,
    *,
    db_path: str | Path | None = None,
) -> tuple[dict[str, Any], ...]:
    path = init_delivery_fact_capture_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
SELECT receipt_id, capture_request_id, workflow_session_ref, world, lane, block_id,
       operation, receipt_type, idempotency_key, payload_hash, origin_surface,
       origin_actor, previous_posture, captured_posture, captured_value_json,
       protected_reference_metadata_json, external_action_performed, created_at
FROM capital_hilton_delivery_fact_capture_receipts
WHERE workflow_session_ref=?
ORDER BY created_at, receipt_id
""".strip(),
            (workflow_session_ref,),
        ).fetchall()
        return tuple(
            {
                "receipt_id": row["receipt_id"],
                "capture_request_id": row["capture_request_id"],
                "workflow_session_ref": row["workflow_session_ref"],
                "world": row["world"],
                "lane": row["lane"],
                "block_id": row["block_id"],
                "operation": row["operation"],
                "receipt_type": row["receipt_type"],
                "idempotency_key": row["idempotency_key"],
                "payload_hash": row["payload_hash"],
                "origin_surface": row["origin_surface"],
                "origin_actor": row["origin_actor"],
                "previous_posture": row["previous_posture"],
                "captured_posture": row["captured_posture"],
                "captured_value": _json_loads(row["captured_value_json"]),
                "protected_reference_metadata": _json_loads(row["protected_reference_metadata_json"]),
                "external_action_performed": bool(row["external_action_performed"]),
                "created_at": row["created_at"],
            }
            for row in rows
        )
    finally:
        conn.close()


def existing_idempotency_keys(*, db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_delivery_fact_capture_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            "SELECT idempotency_key FROM capital_hilton_delivery_fact_capture_receipts ORDER BY idempotency_key"
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _protected_reference_refs(request: CapitalHiltonDeliveryFactCaptureRequest) -> tuple[str, ...]:
    metadata = request.protected_reference_metadata
    refs = []
    for key in ("source_card_ref", "protected_storage_ref", "path"):
        value = metadata.get(key)
        if value:
            refs.append(str(value))
    if request.block_id == "protected_evidence_reference" and not refs:
        refs.append(f"protected_reference_metadata:{request.capture_request_id}")
    return tuple(refs)


def _delivery_readiness_effect(rows: Mapping[str, Any]) -> dict[str, Any]:
    po = rows.get("proof_po_reference", {}).get("posture", "NEEDS_DISCOVERY")
    ap = rows.get("ap_email_route", {}).get("posture", "AP_ROUTE_UNKNOWN")
    protected = rows.get("protected_evidence_reference", {}).get("posture", "PROTECTED_REFERENCE_REQUIRED")
    return {
        "po_coupa_status": po,
        "ap_email_route_status": ap,
        "protected_evidence_status": protected,
        "email_delivery_readiness": "BLOCKED_AP_ROUTE_NOT_CONFIRMED_AND_SEND_GATE_LOCKED"
        if ap != "AP_EMAIL_CONFIRMED"
        else "BLOCKED_APPROVAL_AND_SEND_GATE_LOCKED",
        "coupa_submission_readiness": "BLOCKED_PO_COUPA_REFERENCE_AND_PROTECTED_ACCESS_UNRESOLVED",
        "approval_readiness": "BLOCKED_DELIVERY_FACTS_UNRESOLVED",
        "external_action_performed": False,
    }


def build_receipt_payload(
    request: CapitalHiltonDeliveryFactCaptureRequest,
    validation: CapitalHiltonDeliveryFactIntakeValidation,
) -> CapitalHiltonDeliveryFactReceiptPayload:
    proof_status = {
        "proof_po_reference": "delivery_fact_posture_captured_proof_still_required",
        "ap_email_route": "candidate_route_captured_confirmation_still_required"
        if request.proposed_posture == "AP_EMAIL_CANDIDATE_NEEDS_CONFIRMATION"
        else "ap_route_posture_captured_proof_may_still_be_required",
        "protected_evidence_reference": "protected_reference_posture_captured_no_raw_body",
    }.get(request.block_id, "unknown_fail_closed")
    return CapitalHiltonDeliveryFactReceiptPayload(
        receipt_payload_id=f"delivery_receipt_payload_{_short_hash((request.capture_request_id, request.payload_hash))}",
        receipt_type=request.receipt_type_requested,
        workflow_session_ref=request.workflow_session_ref,
        block_id=request.block_id,
        previous_posture=request.current_posture,
        new_posture=request.proposed_posture,
        proposed_value=validation.normalized_request,
        protected_reference_metadata=request.protected_reference_metadata,
        source_capture_request_ref=request.capture_request_id,
        proof_status_after_capture=proof_status,
        payload_hash=request.payload_hash,
        idempotency_key=request.idempotency_key,
        authority_boundary=AUTHORITY_BOUNDARY,
        next_safe_move="Write local receipt/state row only; keep external gates closed.",
    )


def build_state_update_target(
    request: CapitalHiltonDeliveryFactCaptureRequest,
    receipt_payload: CapitalHiltonDeliveryFactReceiptPayload,
) -> CapitalHiltonDeliveryFactStateUpdateTarget:
    return CapitalHiltonDeliveryFactStateUpdateTarget(
        state_update_target_id=f"delivery_state_target_{_short_hash((request.capture_request_id, request.proposed_posture))}",
        receipt_payload_ref=receipt_payload.receipt_payload_id,
        canonical_workflow_state_ref=f"capital_hilton_delivery_fact_state:{request.workflow_session_ref}:{request.block_id}",
        block_state_before=request.current_posture,
        block_state_after=request.proposed_posture,
        field_updates=receipt_payload.proposed_value,
        delivery_readiness_effect={
            "email_delivery": "blocked until AP route confirmed, artifact/final packet approved, and send gate exists",
            "coupa_submission": "blocked until PO/Coupa posture and protected access resolve",
            "approval": "blocked until coherent delivery route and proof posture exist",
        },
        proof_requirements_after_update=(
            "PO/Coupa proof still required unless explicit confirmed reference is later captured",
            "AP/email route proof or operator confirmation still required before send",
            "protected evidence references require metadata-only posture and Guardian review when protected",
        ),
        downstream_invalidations=(
            "delivery_readiness_recomputed_from_delivery_fact_state",
            "approval_packet_stays_locked",
            "send_submit_stays_locked",
        ),
        current_state_write_authority=True,
        next_safe_move="Apply state update only through enabled delivery-fact adapter.",
    )


def write_capture_request(
    request: CapitalHiltonDeliveryFactCaptureRequest,
    validation: CapitalHiltonDeliveryFactIntakeValidation | None = None,
    *,
    db_path: str | Path | None = None,
    created_at: str | None = None,
) -> CapitalHiltonDeliveryFactCaptureReadback:
    validation = validation or validate_capture_request(request)
    if validation.validation_status == "DUPLICATE_NOOP":
        path = init_delivery_fact_capture_schema(db_path)
        conn = sqlite3.connect(path)
        try:
            row = _read_state_row(conn, request.workflow_session_ref, request.block_id)
            rows = read_delivery_fact_state(db_path=path)
        finally:
            conn.close()
        return CapitalHiltonDeliveryFactCaptureReadback(
            readback_id=f"delivery_readback_{_short_hash((request.capture_request_id, 'duplicate'))}",
            write_status="DUPLICATE_NOOP",
            workflow_session_ref=request.workflow_session_ref,
            block_id=request.block_id,
            receipt_type=request.receipt_type_requested,
            previous_posture=request.current_posture,
            captured_posture=(row or {}).get("posture", request.proposed_posture),
            captured_value=(row or {}).get("value", {}),
            protected_reference_refs=_protected_reference_refs(request),
            payload_hash=request.payload_hash,
            idempotency_key=request.idempotency_key,
            duplicate_retry_result="DUPLICATE_NOOP_NO_SECOND_RECEIPT_OR_STATE_ROW",
            delivery_readiness_after_capture=_delivery_readiness_effect(rows),
            external_action_performed=False,
            next_safe_move="Duplicate retry confirmed as no-op.",
        )
    if not validation.write_allowed:
        return CapitalHiltonDeliveryFactCaptureReadback(
            readback_id=f"delivery_readback_{_short_hash((request.capture_request_id, validation.validation_status))}",
            write_status="BLOCKED_FAIL_CLOSED",
            workflow_session_ref=request.workflow_session_ref,
            block_id=request.block_id,
            receipt_type=request.receipt_type_requested,
            previous_posture=request.current_posture,
            captured_posture=request.current_posture,
            captured_value={},
            protected_reference_refs=(),
            payload_hash=request.payload_hash,
            idempotency_key=request.idempotency_key,
            duplicate_retry_result="not_attempted",
            delivery_readiness_after_capture={
                "email_delivery_readiness": "BLOCKED_FAIL_CLOSED",
                "coupa_submission_readiness": "BLOCKED_FAIL_CLOSED",
                "approval_readiness": "BLOCKED_FAIL_CLOSED",
            },
            external_action_performed=False,
            next_safe_move="Correct request before attempting local delivery-fact capture.",
        )

    path = init_delivery_fact_capture_schema(db_path)
    now = created_at or utc_now()
    receipt_payload = build_receipt_payload(request, validation)
    state_target = build_state_update_target(request, receipt_payload)
    receipt_id = _receipt_id(request)
    state_id = _state_id(request)
    committed = dict(validation.normalized_request)

    conn = sqlite3.connect(path)
    try:
        existing = conn.execute(
            "SELECT receipt_id FROM capital_hilton_delivery_fact_capture_receipts WHERE idempotency_key=?",
            (request.idempotency_key,),
        ).fetchone()
        if existing:
            duplicate_validation = validate_capture_request(
                request,
                existing_idempotency_keys=(request.idempotency_key,),
            )
            return write_capture_request(request, duplicate_validation, db_path=path, created_at=now)

        conn.execute(
            """
INSERT INTO capital_hilton_delivery_fact_capture_receipts (
  receipt_id, capture_request_id, workflow_session_ref, world, lane,
  block_id, operation, receipt_type, idempotency_key, payload_hash,
  origin_surface, origin_actor, previous_posture, captured_posture,
  captured_value_json, protected_reference_metadata_json, authority_scope_json,
  external_action_performed, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
            (
                receipt_id,
                request.capture_request_id,
                request.workflow_session_ref,
                request.world,
                request.lane,
                request.block_id,
                request.operation,
                request.receipt_type_requested,
                request.idempotency_key,
                request.payload_hash,
                request.origin_surface,
                request.origin_actor,
                request.current_posture,
                request.proposed_posture,
                stable_json(committed),
                stable_json(request.protected_reference_metadata),
                stable_json(request.authority_scope_requested),
                0,
                now,
            ),
        )
        conn.execute(
            """
INSERT INTO capital_hilton_delivery_fact_state (
  state_id, workflow_session_ref, world, lane, block_id, posture,
  value_json, protected_reference_metadata_json, receipt_ref, payload_hash, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(workflow_session_ref, block_id) DO UPDATE SET
  posture=excluded.posture,
  value_json=excluded.value_json,
  protected_reference_metadata_json=excluded.protected_reference_metadata_json,
  receipt_ref=excluded.receipt_ref,
  payload_hash=excluded.payload_hash,
  updated_at=excluded.updated_at
""".strip(),
            (
                state_id,
                request.workflow_session_ref,
                request.world,
                request.lane,
                request.block_id,
                request.proposed_posture,
                stable_json(committed),
                stable_json(request.protected_reference_metadata),
                receipt_id,
                request.payload_hash,
                now,
            ),
        )
        conn.commit()
        row = _read_state_row(conn, request.workflow_session_ref, request.block_id)
    finally:
        conn.close()
    rows = read_delivery_fact_state(db_path=path)
    return CapitalHiltonDeliveryFactCaptureReadback(
        readback_id=f"delivery_readback_{_short_hash((request.capture_request_id, receipt_id, state_target.state_update_target_id))}",
        write_status="WRITTEN_TO_LOCAL_LEDGER",
        workflow_session_ref=request.workflow_session_ref,
        block_id=request.block_id,
        receipt_type=request.receipt_type_requested,
        previous_posture=request.current_posture,
        captured_posture=row["posture"] if row else request.proposed_posture,
        captured_value=row["value"] if row else committed,
        protected_reference_refs=_protected_reference_refs(request),
        payload_hash=request.payload_hash,
        idempotency_key=request.idempotency_key,
        duplicate_retry_result="not_duplicate_first_write",
        delivery_readiness_after_capture=_delivery_readiness_effect(rows),
        external_action_performed=False,
        next_safe_move="Read back local delivery-fact state and derive closeout.",
    )


def apply_fixture_capture_requests(
    *,
    db_path: str | Path | None = None,
    created_at: str | None = None,
) -> tuple[CapitalHiltonDeliveryFactIntakeValidation, tuple[CapitalHiltonDeliveryFactCaptureReadback, ...]]:
    validations: list[CapitalHiltonDeliveryFactIntakeValidation] = []
    readbacks: list[CapitalHiltonDeliveryFactCaptureReadback] = []
    for request in default_fixture_capture_requests():
        validation = validate_capture_request(
            request,
            existing_idempotency_keys=existing_idempotency_keys(db_path=db_path),
        )
        validations.append(validation)
        readbacks.append(write_capture_request(request, validation, db_path=db_path, created_at=created_at))
    return tuple(validations), tuple(readbacks)


def _state_summary_from_rows(rows: Mapping[str, Any]) -> dict[str, Any]:
    po = rows.get("proof_po_reference", {})
    ap = rows.get("ap_email_route", {})
    protected = rows.get("protected_evidence_reference", {})
    return {
        "workflow_session_ref": WORKFLOW_SESSION_REF,
        "invoice_state": {
            "performance_dates": CAPTURED_DATES,
            "show_count": 4,
            "rate_per_show": RATE_PER_SHOW,
            "subtotal": SUBTOTAL,
            "artifact_preview_path": ARTIFACT_PREVIEW_PATH,
            "artifact_preview_hash": ARTIFACT_PREVIEW_HASH,
        },
        "po_coupa_posture": po.get("posture", "UNKNOWN_NOT_CAPTURED"),
        "po_coupa_value": po.get("value", {}),
        "ap_email_route_posture": ap.get("posture", "UNKNOWN_NOT_CAPTURED"),
        "ap_email_route_value": ap.get("value", {}),
        "protected_evidence_posture": protected.get("posture", "UNKNOWN_NOT_CAPTURED"),
        "protected_evidence_value": protected.get("value", {}),
    }


def build_closeout(
    readbacks: tuple[CapitalHiltonDeliveryFactCaptureReadback, ...],
    *,
    db_path: str | Path | None = None,
) -> CapitalHiltonDeliveryFactsCloseout:
    rows = read_delivery_fact_state(db_path=db_path)
    summary = _state_summary_from_rows(rows)
    receipt_refs = tuple(item.readback_id for item in readbacks)
    po_posture = summary["po_coupa_posture"]
    ap_posture = summary["ap_email_route_posture"]
    return CapitalHiltonDeliveryFactsCloseout(
        closeout_id=f"delivery_closeout_{_short_hash(receipt_refs)}",
        delivery_fact_readback_refs=receipt_refs,
        what_openclaw_knows_now={
            "po_coupa_posture": po_posture,
            "ap_email_route_posture": ap_posture,
            "ap_route_confirmed": ap_posture == "AP_EMAIL_CONFIRMED",
            "po_or_coupa_reference_obtained": po_posture in {"PO_REFERENCE_KNOWN", "COUPA_REFERENCE_KNOWN"},
            "protected_evidence_posture": summary["protected_evidence_posture"],
            "invoice_basis": summary["invoice_state"],
        },
        what_remains_unknown=(
            "confirmed PO/Coupa/payment reference",
            "confirmed AP/email recipient",
            "whether Coupa submission is required",
            "protected proof reference supporting PO/AP route",
        ),
        what_delivery_can_do_now=(
            "show delivery-fact capture closeout from local SQLite state",
            "ask a narrower next operator question for PO/reference and AP route confirmation",
            "keep invoice preview attached to delivery-readiness context",
        ),
        what_remains_blocked=(
            "email draft/send remains blocked",
            "Coupa submit remains blocked",
            "approval/send remains blocked",
            "external access remains blocked",
        ),
        suggested_next_operator_question=(
            "Do you have a PO/Coupa/payment reference, and should the invoice go to Annette.Sunga@hilton.com?"
        ),
        suggested_next_safe_build_step="Build email draft packet/final artifact rail only after AP route and PO/Coupa posture are confirmed or explicitly parked.",
        next_safe_move="Render closeout and next delivery-fact questions; do not send or submit.",
    )


def build_capital_hilton_delivery_facts_capture_writer(
    *,
    generated_at: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    validations, readbacks = apply_fixture_capture_requests(db_path=db_path, created_at=generated_at)
    rows = read_delivery_fact_state(db_path=db_path)
    receipts = read_delivery_fact_receipts(db_path=db_path)
    closeout = build_closeout(readbacks, db_path=db_path)
    receipt_payloads = tuple(
        build_receipt_payload(request, validation)
        for request, validation in zip(default_fixture_capture_requests(), validations)
    )
    state_targets = tuple(
        build_state_update_target(request, receipt_payload)
        for request, receipt_payload in zip(default_fixture_capture_requests(), receipt_payloads)
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at or utc_now(),
        "operator_summary": (
            "Capital Hilton delivery-fact postures were captured locally: PO/Coupa remains needs-discovery, "
            "AP/email route remains a candidate needing confirmation, and protected evidence remains metadata-only."
        ),
        "model_schemas": {
            "capture_request": {
                "model_name": "CapitalHiltonDeliveryFactCaptureRequest",
                "required_fields": list(REQUIRED_CAPTURE_REQUEST_FIELDS),
                "optional_visual_agnostic_fields": list(OPTIONAL_CAPTURE_REQUEST_FIELDS),
                "hash_key_alternatives": {
                    "idempotency": ("idempotency_key", "idempotency_key_basis"),
                    "payload_hash": ("payload_hash", "payload_hash_basis"),
                },
            },
            "intake_validation": {
                "model_name": "CapitalHiltonDeliveryFactIntakeValidation",
                "required_fields": list(REQUIRED_VALIDATION_FIELDS),
                "validation_statuses": list(VALIDATION_STATUSES),
            },
            "receipt_payload": {
                "model_name": "CapitalHiltonDeliveryFactReceiptPayload",
                "required_fields": list(REQUIRED_RECEIPT_PAYLOAD_FIELDS),
            },
            "state_update_target": {
                "model_name": "CapitalHiltonDeliveryFactStateUpdateTarget",
                "required_fields": list(REQUIRED_STATE_UPDATE_TARGET_FIELDS),
            },
            "capture_readback": {
                "model_name": "CapitalHiltonDeliveryFactCaptureReadback",
                "required_fields": list(REQUIRED_READBACK_FIELDS),
                "write_statuses": list(WRITE_STATUSES),
            },
            "closeout": {
                "model_name": "CapitalHiltonDeliveryFactsCloseout",
                "required_fields": list(REQUIRED_CLOSEOUT_FIELDS),
            },
        },
        "supported_adapters": SUPPORTED_BLOCK_ADAPTERS,
        "fixture_capture_requests": [asdict(item) for item in default_fixture_capture_requests()],
        "fixture_validations": [asdict(item) for item in validations],
        "receipt_payloads": [asdict(item) for item in receipt_payloads],
        "state_update_targets": [asdict(item) for item in state_targets],
        "readbacks": [asdict(item) for item in readbacks],
        "sqlite_receipt_readback": list(receipts),
        "sqlite_state_readback": rows,
        "delivery_facts_closeout": asdict(closeout),
        "known_unknown_facts_after_capture": {
            "confirmed": (
                "performance dates: 2026-05-08, 2026-05-15, 2026-05-22, 2026-05-29",
                "rate: $400/show",
                "subtotal basis: $1,600",
                "local invoice preview hash exists",
            ),
            "candidate": (
                "AP route candidate: Annette.Sunga@hilton.com",
                "CC candidates: Chyna.Hardin@hilton.com and lawrencevalcovic@hilton.com",
            ),
            "unknown": (
                "confirmed PO/Coupa/payment reference",
                "confirmed AP/email recipient",
                "whether Coupa submission is required",
            ),
            "needs_proof": (
                "PO/Coupa posture",
                "AP/email route",
                "protected evidence reference",
            ),
            "protected_access_gated": (
                "Coupa portal/screens",
                "email threads",
                "credential-protected source material",
            ),
        },
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "all_external_authority_false": _all_external_authority_false(),
        },
        "machine_proof": {
            "capture_request_model_exists": True,
            "validation_model_exists": True,
            "receipt_payload_exists": True,
            "state_update_target_exists": True,
            "readback_exists": True,
            "closeout_exists": True,
            "po_coupa_needs_discovery_fixture_validates": validations[0].validation_status in {"VALID_FOR_LOCAL_CAPTURE", "DUPLICATE_NOOP"},
            "ap_route_candidate_needs_confirmation_fixture_validates": validations[1].validation_status in {"VALID_FOR_LOCAL_CAPTURE", "DUPLICATE_NOOP"},
            "protected_evidence_reference_fixture_validates": validations[2].validation_status in {"VALID_FOR_LOCAL_CAPTURE", "DUPLICATE_NOOP"},
            "local_write_readback_worked": all(item.write_status in {"WRITTEN_TO_LOCAL_LEDGER", "DUPLICATE_NOOP"} for item in readbacks),
            "sqlite_receipt_readback_exists": bool(receipts),
            "po_coupa_posture_readback_needs_discovery": rows.get("proof_po_reference", {}).get("posture") == "NEEDS_DISCOVERY",
            "ap_route_remains_candidate_not_confirmed": rows.get("ap_email_route", {}).get("posture") == "AP_EMAIL_CANDIDATE_NEEDS_CONFIRMATION"
            and not rows.get("ap_email_route", {}).get("value", {}).get("confirmed_recipient"),
            "delivery_readiness_remains_blocked": closeout.what_remains_blocked == (
                "email draft/send remains blocked",
                "Coupa submit remains blocked",
                "approval/send remains blocked",
                "external access remains blocked",
            ),
            "normal_read_models_exclude_raw_protected_bodies": True,
            "credentials_cookies_tokens_forbidden": True,
            "guardian_review_required_for_protected_evidence": rows.get("protected_evidence_reference", {})
            .get("value", {})
            .get("guardian_review_required")
            is True,
            "all_external_authority_false": _all_external_authority_false(),
            "credential_material_included": False,
            "raw_private_content_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def _all_external_authority_false() -> bool:
    allowed_true = {
        "local_delivery_fact_write_allowed_for_enabled_adapters",
        "test_delivery_fact_write_allowed",
        "all_external_authority_false",
    }
    return all(
        value is False
        for key, value in AUTHORITY_BOUNDARY.items()
        if key not in allowed_true and isinstance(value, bool)
    )


def format_capital_hilton_delivery_facts_capture_writer(payload: dict[str, Any]) -> str:
    closeout = payload["delivery_facts_closeout"]
    rows = payload["sqlite_state_readback"]
    lines = [
        "# Capital Hilton Delivery Facts Capture Writer v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        (
            "OpenClaw wrote the safe delivery-fact postures into local SQLite. It now records that "
            "PO/Coupa still needs discovery, the AP/email route is only a candidate needing confirmation, "
            "and protected evidence must stay metadata-only."
        ),
        "",
        "This did not log into Coupa or Gmail, send email, submit approval, call agents/tools/models, or ingest raw protected content.",
        "",
        "## Readback",
        "",
        f"- PO/Coupa posture: `{rows.get('proof_po_reference', {}).get('posture')}`",
        f"- AP/email route posture: `{rows.get('ap_email_route', {}).get('posture')}`",
        f"- Protected evidence posture: `{rows.get('protected_evidence_reference', {}).get('posture')}`",
        "",
        "## What OpenClaw Knows Now",
        "",
    ]
    for key, value in closeout["what_openclaw_knows_now"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Still Blocked",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in closeout["what_remains_blocked"])
    lines.extend(
        [
            "",
            "## Next Operator Question",
            "",
            closeout["suggested_next_operator_question"],
            "",
            "## Authority",
            "",
            f"- Local enabled delivery-fact write: `{str(payload['authority_boundary']['local_delivery_fact_write_allowed_for_enabled_adapters']).lower()}`",
            f"- Coupa/browser/Gmail: `{str(payload['authority_boundary']['coupa_access_allowed'] or payload['authority_boundary']['browser_automation_allowed'] or payload['authority_boundary']['gmail_access_allowed']).lower()}`",
            f"- Email send/approval: `{str(payload['authority_boundary']['email_send_allowed'] or payload['authority_boundary']['approval_submission_allowed']).lower()}`",
            f"- Credential handling: `{str(payload['authority_boundary']['credential_handling_allowed']).lower()}`",
            f"- Raw body ingestion: `{str(payload['authority_boundary']['raw_body_ingestion_allowed']).lower()}`",
            "",
            "## Next Safe Move",
            "",
            closeout["next_safe_move"],
            "",
        ]
    )
    return "\n".join(lines)


def export_capital_hilton_delivery_facts_capture_writer(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    db_path: str | Path | None = None,
    generated_at: str | None = None,
) -> CapitalHiltonDeliveryFactsCaptureWriterExportResult:
    payload = build_capital_hilton_delivery_facts_capture_writer(generated_at=generated_at, db_path=db_path)
    root = _ledger_path(export_root) if not Path(export_root).is_absolute() else Path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_capital_hilton_delivery_facts_capture_writer(payload), encoding="utf-8")
    return CapitalHiltonDeliveryFactsCaptureWriterExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        validation_statuses=tuple(item["validation_status"] for item in payload["fixture_validations"]),
        write_statuses=tuple(item["write_status"] for item in payload["readbacks"]),
        po_coupa_posture=payload["sqlite_state_readback"].get("proof_po_reference", {}).get("posture"),
        ap_email_route_posture=payload["sqlite_state_readback"].get("ap_email_route", {}).get("posture"),
        external_action_performed=any(item["external_action_performed"] for item in payload["readbacks"]),
    )


def _fixture_requests_for_name(name: str) -> tuple[CapitalHiltonDeliveryFactCaptureRequest, ...]:
    if name == "default":
        return default_fixture_capture_requests()
    if name == "po":
        return (fixture_po_coupa_needs_discovery_request(),)
    if name == "ap":
        return (fixture_ap_route_candidate_request(),)
    if name == "protected":
        return (fixture_protected_reference_required_request(),)
    raise ValueError(f"unsupported fixture: {name}")


def import_capture_requests(
    requests: tuple[CapitalHiltonDeliveryFactCaptureRequest, ...],
    *,
    db_path: str | Path | None = None,
    created_at: str | None = None,
) -> tuple[tuple[CapitalHiltonDeliveryFactIntakeValidation, ...], tuple[CapitalHiltonDeliveryFactCaptureReadback, ...]]:
    validations: list[CapitalHiltonDeliveryFactIntakeValidation] = []
    readbacks: list[CapitalHiltonDeliveryFactCaptureReadback] = []
    for request in requests:
        validation = validate_capture_request(
            request,
            existing_idempotency_keys=existing_idempotency_keys(db_path=db_path),
        )
        validations.append(validation)
        readbacks.append(write_capture_request(request, validation, db_path=db_path, created_at=created_at))
    return tuple(validations), tuple(readbacks)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import Capital Hilton delivery facts capture requests.")
    parser.add_argument("--file", default=None, help="Optional single delivery fact capture request JSON file.")
    parser.add_argument("--fixture", choices=("default", "po", "ap", "protected"), default="default")
    parser.add_argument("--db", default=None)
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.file:
        requests = (load_capture_request_file(args.file),)
        validations, readbacks = import_capture_requests(requests, db_path=args.db)
        closeout = build_closeout(readbacks, db_path=args.db)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "validation": [asdict(item) for item in validations],
            "readback": [asdict(item) for item in readbacks],
            "delivery_facts_closeout": asdict(closeout),
            "external_action_performed": any(item.external_action_performed for item in readbacks),
        }
        if args.format == "operator":
            print(stable_json(payload), end="")
        else:
            print(stable_json(payload), end="")
        return 0

    result = export_capital_hilton_delivery_facts_capture_writer(
        export_root=args.export_root,
        db_path=args.db,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "validation_statuses": result.validation_statuses,
        "write_statuses": result.write_statuses,
        "po_coupa_posture": result.po_coupa_posture,
        "ap_email_route_posture": result.ap_email_route_posture,
        "external_action_performed": result.external_action_performed,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        payload = build_capital_hilton_delivery_facts_capture_writer(db_path=args.db)
        print(format_capital_hilton_delivery_facts_capture_writer(payload), end="")
    return 0


__all__ = [
    "ARTIFACT_PREVIEW_HASH",
    "ARTIFACT_PREVIEW_PATH",
    "AUTHORITY_BOUNDARY",
    "BLOCKED_ACTIONS",
    "CAPTURED_DATES",
    "CONTRACT_STATUS",
    "DEFAULT_EXPORT_ROOT",
    "JSON_EXPORT_NAME",
    "LANE",
    "OPERATOR_EXPORT_NAME",
    "RATE_PER_SHOW",
    "READ_MODEL_ID",
    "REQUIRED_CAPTURE_REQUEST_FIELDS",
    "REQUIRED_CLOSEOUT_FIELDS",
    "REQUIRED_READBACK_FIELDS",
    "REQUIRED_RECEIPT_PAYLOAD_FIELDS",
    "REQUIRED_STATE_UPDATE_TARGET_FIELDS",
    "REQUIRED_VALIDATION_FIELDS",
    "SAFE_AP_EMAIL_ROUTE_CANDIDATES",
    "SCHEMA_VERSION",
    "SUBTOTAL",
    "SUPPORTED_BLOCK_ADAPTERS",
    "VALIDATION_STATUSES",
    "WORKFLOW_SESSION_REF",
    "WRITE_STATUSES",
    "CapitalHiltonDeliveryFactCaptureReadback",
    "CapitalHiltonDeliveryFactCaptureRequest",
    "CapitalHiltonDeliveryFactIntakeValidation",
    "CapitalHiltonDeliveryFactReceiptPayload",
    "CapitalHiltonDeliveryFactStateUpdateTarget",
    "CapitalHiltonDeliveryFactsCaptureWriterExportResult",
    "CapitalHiltonDeliveryFactsCloseout",
    "apply_fixture_capture_requests",
    "build_capital_hilton_delivery_facts_capture_writer",
    "build_closeout",
    "build_receipt_payload",
    "build_state_update_target",
    "default_fixture_capture_requests",
    "derive_idempotency_key",
    "derive_payload_hash",
    "existing_idempotency_keys",
    "export_capital_hilton_delivery_facts_capture_writer",
    "fixture_ap_route_candidate_request",
    "fixture_po_coupa_needs_discovery_request",
    "fixture_protected_reference_required_request",
    "format_capital_hilton_delivery_facts_capture_writer",
    "import_capture_requests",
    "init_delivery_fact_capture_schema",
    "load_capture_request_file",
    "main",
    "make_capture_request",
    "read_delivery_fact_state",
    "read_delivery_fact_receipts",
    "stable_json",
    "validate_capture_request",
    "write_capture_request",
]
