"""Mission Control capture request intake for Capital Hilton block drafts.

This module implements the first narrow backend bridge from a Mission
Control-shaped draft packet into durable local OpenClaw SQLite state. It is
intentionally visual-agnostic: the packet names workflow/session/block values,
not UI controls, so future Telegram or agent surfaces can reuse the same shape.

Scope for v0:
- Performance Dates
- Rate Confirmation

It does not implement batch capture, PO/Coupa capture, invoice generation,
email draft/send, approval submission, browser automation, model/agent/tool
execution, or Mac code changes.
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

SCHEMA_VERSION = "mission_control_capture_request_intake_v0"
READ_MODEL_ID = "mission_control_capture_request_intake"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "NARROW_DURABLE_SQLITE_CAPTURE_FOR_DATES_AND_RATE"

WORKFLOW_SESSION_REF = "capital_hilton_invoice_workflow_session"
WORLD = "Finance"
LANE = "Capital Hilton"
WORKFLOW_TYPE = "capital_hilton_invoice"

CURRENT_DATES = ("2026-05-08", "2026-05-15")
ADDED_DATES = ("2026-05-22", "2026-05-29")
CAPTURED_DATES = ("2026-05-08", "2026-05-15", "2026-05-22", "2026-05-29")
RATE_CAPTURE = {"amount": 400, "currency": "USD", "unit": "show", "display": "$400/show"}
DERIVED_SUBTOTAL = {"amount": 1600, "currency": "USD", "calculation": "4 shows x $400/show"}

VALIDATION_STATUSES = (
    "VALID_FOR_LOCAL_SQLITE_CAPTURE",
    "DUPLICATE_NOOP",
    "NEEDS_CLARIFICATION",
    "UNSUPPORTED_BLOCK",
    "UNSUPPORTED_OPERATION",
    "BLOCKED_BY_AUTHORITY",
    "INVALID_PAYLOAD",
    "UNKNOWN_FAIL_CLOSED",
)

WRITE_STATUSES = (
    "WRITTEN_TO_LOCAL_SQLITE",
    "DUPLICATE_NOOP",
    "VALIDATED_BUT_WRITE_BLOCKED",
    "BLOCKED_FAIL_CLOSED",
)

REQUIRED_CAPTURE_REQUEST_FIELDS = (
    "capture_request_id",
    "source_surface",
    "source_actor",
    "source_channel",
    "request_created_at_policy",
    "workflow_session_ref",
    "world",
    "lane",
    "workflow_type",
    "block_id",
    "operation",
    "draft_intent_ref",
    "current_value",
    "proposed_value",
    "normalized_updates",
    "operator_confirmation_text",
    "receipt_type_requested",
    "idempotency_key",
    "payload_hash",
    "authority_scope_requested",
    "preview_state_hash",
    "blocked_actions",
    "next_safe_move",
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
    "execution_allowed",
    "next_safe_move",
)

REQUIRED_READBACK_FIELDS = (
    "readback_id",
    "capture_request_ref",
    "write_status",
    "receipt_ref",
    "state_ref",
    "block_id",
    "previous_value",
    "committed_value",
    "added_values",
    "show_count_before",
    "show_count_after",
    "state_readback",
    "external_action_performed",
    "next_safe_move",
)

REQUIRED_CAPTURE_SESSION_RESULT_FIELDS = (
    "capture_session_result_id",
    "workflow_session_ref",
    "applied_capture_request_refs",
    "per_block_readbacks",
    "current_openclaw_state_summary",
    "derived_values",
    "unresolved_blocks",
    "external_action_performed",
    "next_safe_move",
)

REQUIRED_CLOSEOUT_FIELDS = (
    "closeout_id",
    "capture_session_result_ref",
    "title",
    "operator_summary",
    "what_openclaw_knows_now",
    "captured_blocks",
    "updated_values",
    "what_system_can_do_now",
    "what_remains_blocked",
    "proof_or_receipt_refs",
    "downstream_readiness",
    "suggested_next_action",
    "captain_message",
    "next_safe_move",
)

REQUIRED_OUTBOX_FIELDS = (
    "outbox_contract_id",
    "allowed_source_surfaces",
    "target_backend_intake",
    "allowed_write_location_policy",
    "request_schema_ref",
    "required_fields",
    "forbidden_fields",
    "idempotency_policy",
    "payload_hash_policy",
    "security_boundary",
    "operator_confirmation_required",
    "supported_blocks",
    "unsupported_in_this_lane",
    "closeout_schema_ref",
    "next_safe_move",
)

FORBIDDEN_REQUEST_KEYS = (
    "command",
    "command_string",
    "shell",
    "shell_command",
    "execute",
    "raw_body",
    "raw_private_body",
    "raw_message_body",
    "raw_email_body",
    "full_text",
    "file_contents",
    "credential",
    "password",
    "session_cookie",
)

BLOCKED_ACTIONS = (
    "batch capture",
    "PO/Coupa capture",
    "invoice packet readiness commit",
    "approval/send prerequisite commit",
    "invoice generation",
    "email draft or send",
    "approval submission",
    "browser/Coupa/Gmail/Telegram access",
    "credential handling",
    "model/agent/tool/runtime/queue execution",
    "raw private body ingestion",
    "file cleanup/archive/promotion",
)

AUTHORITY_BOUNDARY = {
    "local_sqlite_capture_write_allowed_for_enabled_adapters": True,
    "enabled_adapter_blocks": ("performance_dates", "rate_confirmation"),
    "generic_capture_write_allowed": False,
    "unsupported_block_write_allowed": False,
    "batch_capture_allowed": False,
    "po_coupa_capture_allowed": False,
    "invoice_packet_readiness_commit_allowed": False,
    "approval_send_prerequisite_commit_allowed": False,
    "invoice_generation_allowed": False,
    "email_draft_allowed": False,
    "smtp_send_allowed": False,
    "email_send_allowed": False,
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
    "performance_dates": {
        "adapter_ref": "mission_control_capture_request_intake.performance_dates_sqlite_adapter",
        "allowed_operations": ("add_dates", "confirm_dates", "correct_dates"),
        "receipt_types": (
            "OPERATOR_PERFORMANCE_DATES_ADDITION",
            "OPERATOR_PERFORMANCE_DATES_CONFIRMATION",
            "OPERATOR_PERFORMANCE_DATES_CORRECTION",
        ),
    },
    "rate_confirmation": {
        "adapter_ref": "mission_control_capture_request_intake.rate_confirmation_sqlite_adapter",
        "allowed_operations": ("confirm_rate", "correct_rate"),
        "receipt_types": ("OPERATOR_RATE_CONFIRMATION", "OPERATOR_RATE_CORRECTION"),
    },
}

UNRESOLVED_AFTER_CAPTURE = (
    "PO/Coupa/payment reference still needs discovery or operator confirmation",
    "invoice artifact/PDF/Excel generator is not run in this lane",
    "AP/email delivery route is not confirmed by this lane",
    "approval/send remains locked",
    "Coupa portal submission remains an external protected-access gate",
)


@dataclass(frozen=True)
class MissionControlBlockCaptureRequest:
    capture_request_id: str
    source_surface: str
    source_actor: str
    source_channel: str
    request_created_at_policy: str
    workflow_session_ref: str
    world: str
    lane: str
    workflow_type: str
    block_id: str
    operation: str
    draft_intent_ref: str
    current_value: dict[str, Any]
    proposed_value: dict[str, Any]
    normalized_updates: tuple[dict[str, Any], ...]
    operator_confirmation_text: str
    receipt_type_requested: str
    idempotency_key: str
    payload_hash: str
    authority_scope_requested: dict[str, bool]
    preview_state_hash: str
    blocked_actions: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class MissionControlCaptureIntakeValidation:
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
    execution_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class MissionControlCaptureIntakeReadback:
    readback_id: str
    capture_request_ref: str
    write_status: str
    receipt_ref: str | None
    state_ref: str | None
    block_id: str
    previous_value: dict[str, Any]
    committed_value: dict[str, Any]
    added_values: tuple[str, ...]
    show_count_before: int
    show_count_after: int
    state_readback: dict[str, Any]
    external_action_performed: bool
    next_safe_move: str


@dataclass(frozen=True)
class MissionControlCaptureSessionResult:
    capture_session_result_id: str
    workflow_session_ref: str
    applied_capture_request_refs: tuple[str, ...]
    per_block_readbacks: tuple[MissionControlCaptureIntakeReadback, ...]
    current_openclaw_state_summary: dict[str, Any]
    derived_values: dict[str, Any]
    unresolved_blocks: tuple[str, ...]
    external_action_performed: bool
    next_safe_move: str


@dataclass(frozen=True)
class MissionControlCaptureCompletionCloseout:
    closeout_id: str
    capture_session_result_ref: str
    title: str
    operator_summary: str
    what_openclaw_knows_now: dict[str, Any]
    captured_blocks: tuple[str, ...]
    updated_values: dict[str, Any]
    what_system_can_do_now: tuple[str, ...]
    what_remains_blocked: tuple[str, ...]
    proof_or_receipt_refs: tuple[str, ...]
    downstream_readiness: dict[str, Any]
    suggested_next_action: str
    captain_message: str
    next_safe_move: str


@dataclass(frozen=True)
class MissionControlCaptureOutboxContract:
    outbox_contract_id: str
    allowed_source_surfaces: tuple[str, ...]
    target_backend_intake: str
    allowed_write_location_policy: dict[str, Any]
    request_schema_ref: str
    required_fields: tuple[str, ...]
    forbidden_fields: tuple[str, ...]
    idempotency_policy: str
    payload_hash_policy: str
    security_boundary: dict[str, bool]
    operator_confirmation_required: bool
    supported_blocks: tuple[str, ...]
    unsupported_in_this_lane: tuple[str, ...]
    closeout_schema_ref: str
    next_safe_move: str


@dataclass(frozen=True)
class MissionControlCaptureIntakeExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    validation_statuses: tuple[str, ...]
    write_statuses: tuple[str, ...]
    final_show_count: int
    rate_display: str | None
    derived_subtotal: int | None
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


def _request_hash_basis(request_or_payload: MissionControlBlockCaptureRequest | Mapping[str, Any]) -> dict[str, Any]:
    request = asdict(request_or_payload) if isinstance(request_or_payload, MissionControlBlockCaptureRequest) else dict(request_or_payload)
    return {
        "source_surface": request.get("source_surface"),
        "source_channel": request.get("source_channel"),
        "workflow_session_ref": request.get("workflow_session_ref"),
        "world": request.get("world"),
        "lane": request.get("lane"),
        "workflow_type": request.get("workflow_type"),
        "block_id": request.get("block_id"),
        "operation": request.get("operation"),
        "current_value": request.get("current_value"),
        "proposed_value": request.get("proposed_value"),
        "normalized_updates": request.get("normalized_updates"),
        "receipt_type_requested": request.get("receipt_type_requested"),
        "authority_scope_requested": request.get("authority_scope_requested"),
    }


def derive_payload_hash(request_or_payload: MissionControlBlockCaptureRequest | Mapping[str, Any]) -> str:
    return _sha256(_request_hash_basis(request_or_payload))


def derive_preview_state_hash(request_or_payload: MissionControlBlockCaptureRequest | Mapping[str, Any]) -> str:
    request = asdict(request_or_payload) if isinstance(request_or_payload, MissionControlBlockCaptureRequest) else dict(request_or_payload)
    return _sha256(
        {
            "workflow_session_ref": request.get("workflow_session_ref"),
            "block_id": request.get("block_id"),
            "current_value": request.get("current_value"),
            "proposed_value": request.get("proposed_value"),
        }
    )


def derive_idempotency_key(request_or_payload: MissionControlBlockCaptureRequest | Mapping[str, Any]) -> str:
    request = asdict(request_or_payload) if isinstance(request_or_payload, MissionControlBlockCaptureRequest) else dict(request_or_payload)
    digest = _short_hash(
        {
            "workflow_session_ref": request.get("workflow_session_ref"),
            "block_id": request.get("block_id"),
            "operation": request.get("operation"),
            "receipt_type_requested": request.get("receipt_type_requested"),
            "proposed_value": request.get("proposed_value"),
        }
    )
    return (
        f"mc_capture:{request.get('workflow_session_ref')}:{request.get('block_id')}:"
        f"{request.get('operation')}:{request.get('receipt_type_requested')}:{digest}"
    )


def _authority_scope() -> dict[str, bool]:
    return {
        "local_sqlite_capture": True,
        "external_action": False,
        "invoice_generation": False,
        "email_send": False,
        "coupa_submit": False,
        "model_or_tool_execution": False,
    }


def make_capture_request(
    *,
    capture_request_id: str,
    block_id: str,
    operation: str,
    current_value: dict[str, Any],
    proposed_value: dict[str, Any],
    normalized_updates: tuple[dict[str, Any], ...],
    receipt_type_requested: str,
    draft_intent_ref: str,
    operator_confirmation_text: str,
    source_surface: str = "mission_control",
    source_actor: str = "winship_operator",
    source_channel: str = "local_desktop_capture",
) -> MissionControlBlockCaptureRequest:
    basis: dict[str, Any] = {
        "capture_request_id": capture_request_id,
        "source_surface": source_surface,
        "source_actor": source_actor,
        "source_channel": source_channel,
        "request_created_at_policy": "timestamp may be supplied by source but is excluded from payload hash",
        "workflow_session_ref": WORKFLOW_SESSION_REF,
        "world": WORLD,
        "lane": LANE,
        "workflow_type": WORKFLOW_TYPE,
        "block_id": block_id,
        "operation": operation,
        "draft_intent_ref": draft_intent_ref,
        "current_value": current_value,
        "proposed_value": proposed_value,
        "normalized_updates": normalized_updates,
        "operator_confirmation_text": operator_confirmation_text,
        "receipt_type_requested": receipt_type_requested,
        "authority_scope_requested": _authority_scope(),
        "blocked_actions": BLOCKED_ACTIONS,
        "next_safe_move": "Validate and write through the enabled local SQLite block adapter.",
    }
    return MissionControlBlockCaptureRequest(
        **basis,
        idempotency_key=derive_idempotency_key(basis),
        payload_hash=derive_payload_hash(basis),
        preview_state_hash=derive_preview_state_hash(basis),
    )


def fixture_performance_dates_request() -> MissionControlBlockCaptureRequest:
    return make_capture_request(
        capture_request_id="capital_hilton_performance_dates_add_may_22_29",
        block_id="performance_dates",
        operation="add_dates",
        current_value={"performance_dates": CURRENT_DATES},
        proposed_value={"performance_dates": CAPTURED_DATES},
        normalized_updates=(
            {"field": "performance_dates", "operation": "add", "value": "2026-05-22"},
            {"field": "performance_dates", "operation": "add", "value": "2026-05-29"},
        ),
        receipt_type_requested="OPERATOR_PERFORMANCE_DATES_ADDITION",
        draft_intent_ref="workflow_block_intent_live_draft_contract.capital_hilton_performance_dates_draft",
        operator_confirmation_text="Use these four performance dates",
    )


def fixture_rate_confirmation_request() -> MissionControlBlockCaptureRequest:
    return make_capture_request(
        capture_request_id="capital_hilton_rate_confirmation_400_per_show",
        block_id="rate_confirmation",
        operation="confirm_rate",
        current_value={"rate": None},
        proposed_value={"rate": RATE_CAPTURE},
        normalized_updates=({"field": "rate", "operation": "confirm", "value": RATE_CAPTURE},),
        receipt_type_requested="OPERATOR_RATE_CONFIRMATION",
        draft_intent_ref="workflow_block_intent_live_draft_contract.capital_hilton_rate_confirmation_draft",
        operator_confirmation_text="Use $400/show",
    )


def default_fixture_capture_requests() -> tuple[MissionControlBlockCaptureRequest, ...]:
    return (fixture_performance_dates_request(), fixture_rate_confirmation_request())


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


def _tuple_values(value: Any, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a list or tuple")
    values: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name} values must be non-empty strings")
        values.append(item.strip())
    return tuple(values)


def _request_from_payload(payload: Mapping[str, Any]) -> MissionControlBlockCaptureRequest:
    missing = [field for field in REQUIRED_CAPTURE_REQUEST_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"missing required field: {missing[0]}")
    unknown = sorted(set(payload) - set(REQUIRED_CAPTURE_REQUEST_FIELDS))
    if unknown:
        raise ValueError(f"unsupported top-level field: {unknown[0]}")
    forbidden = _contains_forbidden_key(payload)
    if forbidden:
        raise ValueError(f"request contains forbidden field: {forbidden}")
    normalized_updates = payload["normalized_updates"]
    if not isinstance(normalized_updates, (list, tuple)):
        raise ValueError("normalized_updates must be a list")
    authority = payload["authority_scope_requested"]
    if not isinstance(authority, Mapping):
        raise ValueError("authority_scope_requested must be an object")
    return MissionControlBlockCaptureRequest(
        capture_request_id=str(payload["capture_request_id"]),
        source_surface=str(payload["source_surface"]),
        source_actor=str(payload["source_actor"]),
        source_channel=str(payload["source_channel"]),
        request_created_at_policy=str(payload["request_created_at_policy"]),
        workflow_session_ref=str(payload["workflow_session_ref"]),
        world=str(payload["world"]),
        lane=str(payload["lane"]),
        workflow_type=str(payload["workflow_type"]),
        block_id=str(payload["block_id"]),
        operation=str(payload["operation"]),
        draft_intent_ref=str(payload["draft_intent_ref"]),
        current_value=dict(payload["current_value"]),
        proposed_value=dict(payload["proposed_value"]),
        normalized_updates=tuple(dict(item) for item in normalized_updates),
        operator_confirmation_text=str(payload["operator_confirmation_text"]),
        receipt_type_requested=str(payload["receipt_type_requested"]),
        idempotency_key=str(payload["idempotency_key"]),
        payload_hash=str(payload["payload_hash"]),
        authority_scope_requested={str(key): bool(value) for key, value in authority.items()},
        preview_state_hash=str(payload["preview_state_hash"]),
        blocked_actions=tuple(str(item) for item in payload["blocked_actions"]),
        next_safe_move=str(payload["next_safe_move"]),
    )


def load_capture_request_file(path: str | Path) -> MissionControlBlockCaptureRequest:
    request_path = Path(path)
    if not request_path.is_file():
        raise ValueError(f"capture request file not found: {request_path}")
    try:
        payload = json.loads(request_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError("capture request file must contain a JSON object")
    if "block_capture_requests" in payload:
        raise ValueError("batch capture packets are not supported in this lane")
    return _request_from_payload(payload)


def _precondition(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"check": name, "passed": passed, "detail": detail}


def _validate_performance_dates(request: MissionControlBlockCaptureRequest) -> tuple[str | None, dict[str, Any]]:
    current_dates = _tuple_values(request.current_value.get("performance_dates"), field_name="current performance_dates")
    proposed_dates = _tuple_values(request.proposed_value.get("performance_dates"), field_name="proposed performance_dates")
    added_dates = tuple(date for date in proposed_dates if date not in current_dates)
    if request.operation == "add_dates" and not added_dates:
        return "add_dates requires at least one added date", {}
    if request.operation == "add_dates" and tuple(update.get("value") for update in request.normalized_updates) != added_dates:
        return "normalized_updates must exactly match added dates", {}
    if len(set(proposed_dates)) != len(proposed_dates):
        return "proposed performance_dates must not contain duplicates", {}
    return None, {
        "performance_dates": proposed_dates,
        "added_dates": added_dates,
        "show_count_before": len(current_dates),
        "show_count_after": len(proposed_dates),
    }


def _validate_rate(request: MissionControlBlockCaptureRequest) -> tuple[str | None, dict[str, Any]]:
    rate = request.proposed_value.get("rate")
    if not isinstance(rate, Mapping):
        return "rate proposed_value must contain a rate object", {}
    amount = rate.get("amount")
    if not isinstance(amount, (int, float)) or amount <= 0:
        return "rate amount must be a positive number", {}
    if rate.get("currency") != "USD":
        return "rate currency must be USD for this adapter", {}
    if rate.get("unit") != "show":
        return "rate unit must be show for this adapter", {}
    return None, {"rate": dict(rate)}


def _adapter_payload_validation(request: MissionControlBlockCaptureRequest) -> tuple[str | None, dict[str, Any]]:
    if request.block_id == "performance_dates":
        return _validate_performance_dates(request)
    if request.block_id == "rate_confirmation":
        return _validate_rate(request)
    return "unsupported block", {}


def validate_capture_request(
    request: MissionControlBlockCaptureRequest,
    *,
    existing_idempotency_keys: tuple[str, ...] = (),
) -> MissionControlCaptureIntakeValidation:
    status = "VALID_FOR_LOCAL_SQLITE_CAPTURE"
    rejected_reason: str | None = None
    normalized: dict[str, Any] = {}
    accepted_adapter_ref: str | None = None

    adapter = SUPPORTED_BLOCK_ADAPTERS.get(request.block_id)
    if request.idempotency_key in existing_idempotency_keys:
        status = "DUPLICATE_NOOP"
        rejected_reason = "Same idempotency key already captured; retry is a no-op."
    elif request.workflow_session_ref != WORKFLOW_SESSION_REF or request.workflow_type != WORKFLOW_TYPE:
        status = "INVALID_PAYLOAD"
        rejected_reason = "Workflow session/type does not match the Capital Hilton invoice workflow."
    elif request.world != WORLD or request.lane != LANE:
        status = "INVALID_PAYLOAD"
        rejected_reason = "World/lane does not match Finance / Capital Hilton."
    elif adapter is None:
        status = "UNSUPPORTED_BLOCK"
        rejected_reason = "Only performance_dates and rate_confirmation are enabled in this lane."
    elif request.operation not in adapter["allowed_operations"]:
        status = "UNSUPPORTED_OPERATION"
        rejected_reason = "Operation is not enabled for this block adapter."
    elif request.receipt_type_requested not in adapter["receipt_types"]:
        status = "INVALID_PAYLOAD"
        rejected_reason = "Requested receipt type is not allowed for this block adapter."
    elif any(
        request.authority_scope_requested.get(key)
        for key in ("external_action", "invoice_generation", "email_send", "coupa_submit", "model_or_tool_execution")
    ):
        status = "BLOCKED_BY_AUTHORITY"
        rejected_reason = "Capture request asked for authority outside local SQLite block capture."
    elif request.idempotency_key != derive_idempotency_key(request):
        status = "INVALID_PAYLOAD"
        rejected_reason = "idempotency_key does not match stable request basis."
    elif request.payload_hash != derive_payload_hash(request):
        status = "INVALID_PAYLOAD"
        rejected_reason = "payload_hash does not match stable request basis."
    elif request.preview_state_hash != derive_preview_state_hash(request):
        status = "INVALID_PAYLOAD"
        rejected_reason = "preview_state_hash does not match current/proposed state."
    else:
        try:
            failure, normalized = _adapter_payload_validation(request)
        except ValueError as exc:
            failure, normalized = str(exc), {}
        if failure:
            status = "INVALID_PAYLOAD"
            rejected_reason = failure

    write_allowed = status == "VALID_FOR_LOCAL_SQLITE_CAPTURE"
    if write_allowed:
        accepted_adapter_ref = adapter["adapter_ref"] if adapter else None

    preconditions = (
        _precondition("supported_workflow", request.workflow_session_ref == WORKFLOW_SESSION_REF and request.workflow_type == WORKFLOW_TYPE, "Capital Hilton invoice workflow only."),
        _precondition("supported_block", adapter is not None, "Only Performance Dates and Rate Confirmation are enabled."),
        _precondition("supported_operation", adapter is not None and request.operation in adapter["allowed_operations"], "Operation must match block adapter."),
        _precondition("stable_idempotency_key", request.idempotency_key == derive_idempotency_key(request), "Idempotency key binds session, block, operation, receipt type, and proposed value."),
        _precondition("stable_payload_hash", request.payload_hash == derive_payload_hash(request), "Payload hash excludes timestamps and raw bodies."),
        _precondition("no_external_authority_requested", not any(request.authority_scope_requested.get(key) for key in ("external_action", "invoice_generation", "email_send", "coupa_submit", "model_or_tool_execution")), "Capture request is local only."),
    )

    return MissionControlCaptureIntakeValidation(
        validation_id=f"validation_{_short_hash((request.capture_request_id, request.payload_hash, status))}",
        capture_request_ref=request.capture_request_id,
        validation_status=status,
        normalized_request=normalized,
        accepted_adapter_ref=accepted_adapter_ref,
        rejected_reason=rejected_reason,
        ambiguity_flags=() if status in {"VALID_FOR_LOCAL_SQLITE_CAPTURE", "DUPLICATE_NOOP"} else ("fail_closed_until_corrected",),
        duplicate_detection={
            "idempotency_key": request.idempotency_key,
            "duplicate": status == "DUPLICATE_NOOP",
            "same_payload_policy": "no second receipt/state update",
        },
        precondition_results=preconditions,
        required_receipt_type=request.receipt_type_requested,
        write_allowed=write_allowed,
        execution_allowed=False,
        next_safe_move="Write to local SQLite adapter and read back state." if write_allowed else "Return fail-closed validation result.",
    )


def init_mission_control_capture_schema(db_path: str | Path | None = None) -> str:
    path_obj = _ledger_path(db_path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    init_business_ops_ledger(str(path_obj))
    path = str(path_obj)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
CREATE TABLE IF NOT EXISTS mission_control_capture_receipts (
  receipt_id TEXT PRIMARY KEY,
  capture_request_id TEXT NOT NULL,
  workflow_session_ref TEXT NOT NULL,
  world TEXT NOT NULL,
  lane TEXT NOT NULL,
  workflow_type TEXT NOT NULL,
  block_id TEXT NOT NULL,
  operation TEXT NOT NULL,
  receipt_type TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  payload_hash TEXT NOT NULL,
  source_surface TEXT NOT NULL,
  source_channel TEXT NOT NULL,
  source_actor TEXT NOT NULL,
  previous_value_json TEXT NOT NULL,
  committed_value_json TEXT NOT NULL,
  normalized_updates_json TEXT NOT NULL,
  authority_scope_json TEXT NOT NULL,
  external_action_performed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
)
""".strip()
        )
        conn.execute(
            """
CREATE TABLE IF NOT EXISTS mission_control_workflow_block_state (
  state_id TEXT PRIMARY KEY,
  workflow_session_ref TEXT NOT NULL,
  world TEXT NOT NULL,
  lane TEXT NOT NULL,
  workflow_type TEXT NOT NULL,
  block_id TEXT NOT NULL,
  value_json TEXT NOT NULL,
  receipt_ref TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(workflow_session_ref, block_id)
)
""".strip()
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mission_control_capture_receipts_session ON mission_control_capture_receipts(workflow_session_ref)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mission_control_capture_state_session ON mission_control_workflow_block_state(workflow_session_ref)"
        )
        conn.commit()
    finally:
        conn.close()
    return path


def _receipt_id(request: MissionControlBlockCaptureRequest) -> str:
    return _row_id("mc_receipt", request.idempotency_key, request.payload_hash)


def _state_id(request: MissionControlBlockCaptureRequest) -> str:
    return _row_id("mc_state", request.workflow_session_ref, request.block_id)


def _committed_value(request: MissionControlBlockCaptureRequest, normalized: Mapping[str, Any]) -> dict[str, Any]:
    if request.block_id == "performance_dates":
        return {
            "performance_dates": tuple(normalized["performance_dates"]),
            "show_count": normalized["show_count_after"],
            "proof_status": "operator_confirmed_dates_not_external_proof",
        }
    if request.block_id == "rate_confirmation":
        return {
            "rate": dict(normalized["rate"]),
            "proof_status": "operator_confirmed_rate_not_external_proof",
        }
    raise ValueError(f"unsupported block for commit: {request.block_id}")


def _read_state_row(conn: sqlite3.Connection, workflow_session_ref: str, block_id: str) -> dict[str, Any] | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
SELECT state_id, workflow_session_ref, world, lane, workflow_type, block_id, value_json, receipt_ref, payload_hash, updated_at
FROM mission_control_workflow_block_state
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
        "workflow_type": row["workflow_type"],
        "block_id": row["block_id"],
        "value": _json_loads(row["value_json"]),
        "receipt_ref": row["receipt_ref"],
        "payload_hash": row["payload_hash"],
        "updated_at": row["updated_at"],
    }


def read_workflow_block_state(
    workflow_session_ref: str = WORKFLOW_SESSION_REF,
    *,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    path = init_mission_control_capture_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
SELECT state_id, block_id, value_json, receipt_ref, payload_hash, updated_at
FROM mission_control_workflow_block_state
WHERE workflow_session_ref=?
ORDER BY block_id
""".strip(),
            (workflow_session_ref,),
        ).fetchall()
        return {
            row["block_id"]: {
                "state_id": row["state_id"],
                "value": _json_loads(row["value_json"]),
                "receipt_ref": row["receipt_ref"],
                "payload_hash": row["payload_hash"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        }
    finally:
        conn.close()


def existing_idempotency_keys(*, db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_mission_control_capture_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            "SELECT idempotency_key FROM mission_control_capture_receipts ORDER BY idempotency_key"
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def write_capture_request(
    request: MissionControlBlockCaptureRequest,
    validation: MissionControlCaptureIntakeValidation | None = None,
    *,
    db_path: str | Path | None = None,
    created_at: str | None = None,
) -> MissionControlCaptureIntakeReadback:
    validation = validation or validate_capture_request(request)
    if validation.validation_status == "DUPLICATE_NOOP":
        path = init_mission_control_capture_schema(db_path)
        conn = sqlite3.connect(path)
        try:
            row = _read_state_row(conn, request.workflow_session_ref, request.block_id)
        finally:
            conn.close()
        value = row["value"] if row else {}
        return MissionControlCaptureIntakeReadback(
            readback_id=f"readback_{_short_hash((request.capture_request_id, 'duplicate'))}",
            capture_request_ref=request.capture_request_id,
            write_status="DUPLICATE_NOOP",
            receipt_ref=row["receipt_ref"] if row else _receipt_id(request),
            state_ref=row["state_id"] if row else _state_id(request),
            block_id=request.block_id,
            previous_value=request.current_value,
            committed_value=value,
            added_values=tuple(value.get("performance_dates", ())[len(CURRENT_DATES):]) if request.block_id == "performance_dates" else (),
            show_count_before=len(CURRENT_DATES) if request.block_id == "performance_dates" else 0,
            show_count_after=int(value.get("show_count", 0)) if request.block_id == "performance_dates" else 0,
            state_readback=row or {},
            external_action_performed=False,
            next_safe_move="Duplicate retry confirmed as no-op.",
        )
    if not validation.write_allowed:
        return MissionControlCaptureIntakeReadback(
            readback_id=f"readback_{_short_hash((request.capture_request_id, validation.validation_status))}",
            capture_request_ref=request.capture_request_id,
            write_status="BLOCKED_FAIL_CLOSED",
            receipt_ref=None,
            state_ref=None,
            block_id=request.block_id,
            previous_value=request.current_value,
            committed_value={},
            added_values=(),
            show_count_before=0,
            show_count_after=0,
            state_readback={},
            external_action_performed=False,
            next_safe_move="Correct request before attempting local capture.",
        )

    path = init_mission_control_capture_schema(db_path)
    now = created_at or utc_now()
    receipt_id = _receipt_id(request)
    state_id = _state_id(request)
    committed = _committed_value(request, validation.normalized_request)

    conn = sqlite3.connect(path)
    try:
        existing = conn.execute(
            "SELECT receipt_id FROM mission_control_capture_receipts WHERE idempotency_key=?",
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
INSERT INTO mission_control_capture_receipts (
  receipt_id, capture_request_id, workflow_session_ref, world, lane, workflow_type,
  block_id, operation, receipt_type, idempotency_key, payload_hash,
  source_surface, source_channel, source_actor, previous_value_json,
  committed_value_json, normalized_updates_json, authority_scope_json,
  external_action_performed, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
            (
                receipt_id,
                request.capture_request_id,
                request.workflow_session_ref,
                request.world,
                request.lane,
                request.workflow_type,
                request.block_id,
                request.operation,
                request.receipt_type_requested,
                request.idempotency_key,
                request.payload_hash,
                request.source_surface,
                request.source_channel,
                request.source_actor,
                stable_json(request.current_value),
                stable_json(committed),
                stable_json(request.normalized_updates),
                stable_json(request.authority_scope_requested),
                0,
                now,
            ),
        )
        conn.execute(
            """
INSERT INTO mission_control_workflow_block_state (
  state_id, workflow_session_ref, world, lane, workflow_type, block_id,
  value_json, receipt_ref, payload_hash, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(workflow_session_ref, block_id) DO UPDATE SET
  value_json=excluded.value_json,
  receipt_ref=excluded.receipt_ref,
  payload_hash=excluded.payload_hash,
  updated_at=excluded.updated_at
""".strip(),
            (
                state_id,
                request.workflow_session_ref,
                request.world,
                request.lane,
                request.workflow_type,
                request.block_id,
                stable_json(committed),
                receipt_id,
                request.payload_hash,
                now,
            ),
        )
        conn.commit()
        row = _read_state_row(conn, request.workflow_session_ref, request.block_id)
    finally:
        conn.close()

    return MissionControlCaptureIntakeReadback(
        readback_id=f"readback_{_short_hash((request.capture_request_id, receipt_id))}",
        capture_request_ref=request.capture_request_id,
        write_status="WRITTEN_TO_LOCAL_SQLITE",
        receipt_ref=receipt_id,
        state_ref=state_id,
        block_id=request.block_id,
        previous_value=request.current_value,
        committed_value=committed,
        added_values=tuple(validation.normalized_request.get("added_dates", ())),
        show_count_before=int(validation.normalized_request.get("show_count_before", 0)),
        show_count_after=int(validation.normalized_request.get("show_count_after", 0)),
        state_readback=row or {},
        external_action_performed=False,
        next_safe_move="Read back local SQLite workflow block state and derive closeout.",
    )


def apply_fixture_capture_requests(
    *,
    db_path: str | Path | None = None,
    created_at: str | None = None,
) -> tuple[MissionControlCaptureIntakeValidation, ...]:
    validations: list[MissionControlCaptureIntakeValidation] = []
    for request in default_fixture_capture_requests():
        validation = validate_capture_request(
            request,
            existing_idempotency_keys=existing_idempotency_keys(db_path=db_path),
        )
        validations.append(validation)
        write_capture_request(request, validation, db_path=db_path, created_at=created_at)
    return tuple(validations)


def _state_summary_from_rows(rows: Mapping[str, Any]) -> dict[str, Any]:
    date_value = rows.get("performance_dates", {}).get("value") if rows.get("performance_dates") else None
    rate_value = rows.get("rate_confirmation", {}).get("value") if rows.get("rate_confirmation") else None
    dates = tuple(date_value.get("performance_dates", ())) if date_value else ()
    rate = rate_value.get("rate") if rate_value else None
    subtotal = None
    if dates and rate:
        subtotal = {
            "amount": len(dates) * int(rate["amount"]),
            "currency": rate["currency"],
            "calculation": f"{len(dates)} shows x ${int(rate['amount'])}/show",
        }
    return {
        "performance_dates": dates,
        "show_count": len(dates),
        "rate": rate,
        "derived_subtotal": subtotal,
        "po_coupa_posture": "UNRESOLVED_NOT_CAPTURED_IN_THIS_LANE",
        "invoice_artifact_status": "NOT_GENERATED_IN_THIS_LANE",
        "approval_send_status": "LOCKED_EXTERNAL_GATE",
    }


def build_capture_session_result(
    readbacks: tuple[MissionControlCaptureIntakeReadback, ...],
    *,
    db_path: str | Path | None = None,
) -> MissionControlCaptureSessionResult:
    rows = read_workflow_block_state(db_path=db_path)
    state_summary = _state_summary_from_rows(rows)
    return MissionControlCaptureSessionResult(
        capture_session_result_id=f"capture_session_{_short_hash(tuple(item.readback_id for item in readbacks))}",
        workflow_session_ref=WORKFLOW_SESSION_REF,
        applied_capture_request_refs=tuple(item.capture_request_ref for item in readbacks if item.write_status in {"WRITTEN_TO_LOCAL_SQLITE", "DUPLICATE_NOOP"}),
        per_block_readbacks=readbacks,
        current_openclaw_state_summary=state_summary,
        derived_values={"subtotal": state_summary["derived_subtotal"]},
        unresolved_blocks=UNRESOLVED_AFTER_CAPTURE,
        external_action_performed=any(item.external_action_performed for item in readbacks),
        next_safe_move="Use captured dates/rate to prepare the next safe invoice packet/artifact rail; keep delivery locked.",
    )


def build_completion_closeout(result: MissionControlCaptureSessionResult) -> MissionControlCaptureCompletionCloseout:
    state = result.current_openclaw_state_summary
    subtotal = state["derived_subtotal"] or DERIVED_SUBTOTAL
    receipt_refs = tuple(
        item.receipt_ref or ""
        for item in result.per_block_readbacks
        if item.receipt_ref
    )
    return MissionControlCaptureCompletionCloseout(
        closeout_id=f"closeout_{_short_hash(result.capture_session_result_id)}",
        capture_session_result_ref=result.capture_session_result_id,
        title="Capital Hilton capture landed",
        operator_summary=(
            "OpenClaw now has the Capital Hilton invoice draft captured locally with "
            f"{state['show_count']} performance dates, $400/show, and a ${subtotal['amount']:,} subtotal."
        ),
        what_openclaw_knows_now={
            "workflow_session_ref": WORKFLOW_SESSION_REF,
            "performance_dates": state["performance_dates"],
            "rate": state["rate"],
            "derived_subtotal": subtotal,
            "state_source": "mission_control_capture_request_intake local SQLite readback",
        },
        captured_blocks=("performance_dates", "rate_confirmation"),
        updated_values={
            "performance_dates": state["performance_dates"],
            "rate": state["rate"],
            "subtotal": subtotal,
        },
        what_system_can_do_now=(
            "prepare an invoice packet from captured dates and rate in a later safe rail",
            "ask only for unresolved delivery/proof facts",
            "detect stale invoice previews against local captured state",
        ),
        what_remains_blocked=UNRESOLVED_AFTER_CAPTURE,
        proof_or_receipt_refs=receipt_refs,
        downstream_readiness={
            "invoice_packet_data_basis": "DATES_AND_RATE_CAPTURED",
            "subtotal_basis": subtotal,
            "invoice_artifact": "BLOCKED_NOT_GENERATED",
            "email_delivery": "BLOCKED_NO_APPROVED_SEND_PATH",
            "coupa_submission": "BLOCKED_NO_PROTECTED_ACCESS_OR_PO_ROUTE",
            "approval_send": "LOCKED",
        },
        suggested_next_action="Build or invoke the safe invoice packet/artifact rail, then gather PO/Coupa/AP delivery facts.",
        captain_message=(
            "Nice. OpenClaw now has the Capital Hilton invoice draft captured with 4 performance dates, "
            "$400/show, and a $1,600 subtotal. Still blocked: PO/Coupa route, invoice artifact generation, "
            "and approval/send."
        ),
        next_safe_move="Show this closeout to the operator; do not send, submit, or generate external artifacts.",
    )


def build_outbox_contract() -> MissionControlCaptureOutboxContract:
    return MissionControlCaptureOutboxContract(
        outbox_contract_id="mission_control_capture_outbox_contract_v0",
        allowed_source_surfaces=("mission_control", "telegram_future", "cassandra_clara_future"),
        target_backend_intake="scripts/import_mission_control_capture_request.py --file <capture_request.json>",
        allowed_write_location_policy={
            "future_controlled_outbox_path": "/mnt/e/openclaw/mission_control_capture_requests/inbox",
            "source_may_write_arbitrary_files": False,
            "one_json_object_per_request": True,
            "backend_validates_before_write": True,
        },
        request_schema_ref="mission_control_capture_request_intake.MissionControlBlockCaptureRequest",
        required_fields=REQUIRED_CAPTURE_REQUEST_FIELDS,
        forbidden_fields=FORBIDDEN_REQUEST_KEYS,
        idempotency_policy="idempotency key binds workflow/session/block/operation/receipt type/proposed value",
        payload_hash_policy="payload hash excludes timestamps and binds only normalized capture fields",
        security_boundary={
            "network_required": False,
            "shell_required": False,
            "external_account_access_required": False,
            "backend_mutation_from_ui_required": False,
            "raw_private_body_allowed": False,
        },
        operator_confirmation_required=True,
        supported_blocks=("performance_dates", "rate_confirmation"),
        unsupported_in_this_lane=(
            "batch capture",
            "PO/Coupa capture",
            "invoice packet readiness commit",
            "approval/send prerequisite commit",
        ),
        closeout_schema_ref="mission_control_capture_request_intake.MissionControlCaptureCompletionCloseout",
        next_safe_move="Future UI or Telegram surface emits this packet; backend handles validation/write/readback.",
    )


def _negative_validation_examples() -> dict[str, dict[str, Any]]:
    base = fixture_performance_dates_request()
    unsupported_block = replace(base, block_id="proof_po_reference")
    unsupported_operation = replace(base, operation="set_needs_discovery")
    invalid_payload = replace(base, payload_hash="sha256:bad")
    blocked_authority = replace(
        fixture_rate_confirmation_request(),
        authority_scope_requested={
            **fixture_rate_confirmation_request().authority_scope_requested,
            "email_send": True,
        },
    )
    return {
        "unsupported_block": asdict(validate_capture_request(unsupported_block)),
        "unsupported_operation": asdict(validate_capture_request(unsupported_operation)),
        "invalid_payload": asdict(validate_capture_request(invalid_payload)),
        "blocked_by_authority": asdict(validate_capture_request(blocked_authority)),
    }


def _apply_and_build_payload(
    *,
    db_path: str | Path | None = None,
    created_at: str | None = None,
) -> tuple[
    tuple[MissionControlCaptureIntakeValidation, ...],
    tuple[MissionControlCaptureIntakeReadback, ...],
    MissionControlCaptureSessionResult,
    MissionControlCaptureCompletionCloseout,
]:
    validations: list[MissionControlCaptureIntakeValidation] = []
    readbacks: list[MissionControlCaptureIntakeReadback] = []
    for request in default_fixture_capture_requests():
        validation = validate_capture_request(
            request,
            existing_idempotency_keys=existing_idempotency_keys(db_path=db_path),
        )
        readback = write_capture_request(request, validation, db_path=db_path, created_at=created_at)
        validations.append(validation)
        readbacks.append(readback)
    result = build_capture_session_result(tuple(readbacks), db_path=db_path)
    closeout = build_completion_closeout(result)
    return tuple(validations), tuple(readbacks), result, closeout


def build_mission_control_capture_request_intake(
    *,
    generated_at: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    db_path_used = init_mission_control_capture_schema(db_path)
    validations, readbacks, session_result, closeout = _apply_and_build_payload(
        db_path=db_path_used,
        created_at=generated_at,
    )
    state_rows = read_workflow_block_state(db_path=db_path_used)
    state_summary = _state_summary_from_rows(state_rows)
    duplicate_request = fixture_performance_dates_request()
    duplicate_validation = validate_capture_request(
        duplicate_request,
        existing_idempotency_keys=(duplicate_request.idempotency_key,),
    )
    duplicate_readback = write_capture_request(
        duplicate_request,
        duplicate_validation,
        db_path=db_path_used,
        created_at=generated_at,
    )

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_summary": (
            "Mission Control-shaped single-block capture packets for Capital Hilton Performance Dates and "
            "Rate Confirmation now validate, write to local SQLite, and read back captured state. "
            "OpenClaw knows 4 dates, $400/show, and a derived $1,600 subtotal; external delivery remains locked."
        ),
        "model_schemas": {
            "capture_request": {
                "model_name": "MissionControlBlockCaptureRequest",
                "required_fields": list(REQUIRED_CAPTURE_REQUEST_FIELDS),
                "visual_agnostic_payload_keys": True,
            },
            "intake_validation": {
                "model_name": "MissionControlCaptureIntakeValidation",
                "required_fields": list(REQUIRED_VALIDATION_FIELDS),
            },
            "readback": {
                "model_name": "MissionControlCaptureIntakeReadback",
                "required_fields": list(REQUIRED_READBACK_FIELDS),
            },
            "capture_session_result": {
                "model_name": "MissionControlCaptureSessionResult",
                "required_fields": list(REQUIRED_CAPTURE_SESSION_RESULT_FIELDS),
            },
            "completion_closeout": {
                "model_name": "MissionControlCaptureCompletionCloseout",
                "required_fields": list(REQUIRED_CLOSEOUT_FIELDS),
            },
            "outbox_contract": {
                "model_name": "MissionControlCaptureOutboxContract",
                "required_fields": list(REQUIRED_OUTBOX_FIELDS),
            },
        },
        "supported_block_adapters": SUPPORTED_BLOCK_ADAPTERS,
        "unsupported_in_this_lane": (
            "multi-block batch capture",
            "PO/Coupa/proof posture capture",
            "invoice packet readiness commit",
            "approval/send prerequisite commit",
            "agent package context",
        ),
        "fixture_capture_requests": [asdict(item) for item in default_fixture_capture_requests()],
        "validations": [asdict(item) for item in validations],
        "readbacks": [asdict(item) for item in readbacks],
        "duplicate_retry_result": asdict(duplicate_readback),
        "sqlite_readback": {
            "db_path": str(_ledger_path(db_path_used)),
            "state_rows_by_block": state_rows,
            "current_openclaw_state_summary": state_summary,
        },
        "capture_session_result": asdict(session_result),
        "completion_closeout": asdict(closeout),
        "outbox_contract": asdict(build_outbox_contract()),
        "negative_validation_examples": _negative_validation_examples(),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "machine_proof": {
            "capture_request_model_exists": True,
            "intake_validation_model_exists": True,
            "readback_model_exists": True,
            "capture_session_result_model_exists": True,
            "completion_closeout_exists": True,
            "outbox_contract_exists": True,
            "only_performance_dates_and_rate_enabled": tuple(SUPPORTED_BLOCK_ADAPTERS) == ("performance_dates", "rate_confirmation"),
            "batch_capture_not_implemented": AUTHORITY_BOUNDARY["batch_capture_allowed"] is False,
            "po_coupa_capture_not_implemented": AUTHORITY_BOUNDARY["po_coupa_capture_allowed"] is False,
            "invoice_packet_readiness_not_directly_committed": AUTHORITY_BOUNDARY["invoice_packet_readiness_commit_allowed"] is False,
            "approval_send_prerequisite_not_directly_committed": AUTHORITY_BOUNDARY["approval_send_prerequisite_commit_allowed"] is False,
            "visual_agnostic_payload_keys": all(
                key not in REQUIRED_CAPTURE_REQUEST_FIELDS
                for key in ("screen_x", "screen_y", "button_id", "view_id", "mac_window_id")
            ),
            "fixture_requests_match_mission_control_screen_draft": (
                default_fixture_capture_requests()[0].proposed_value["performance_dates"] == CAPTURED_DATES
                and default_fixture_capture_requests()[1].proposed_value["rate"] == RATE_CAPTURE
            ),
            "validations_allow_local_sqlite_capture": all(item.validation_status in {"VALID_FOR_LOCAL_SQLITE_CAPTURE", "DUPLICATE_NOOP"} for item in validations),
            "durable_sqlite_state_readback_has_4_dates": state_summary["performance_dates"] == CAPTURED_DATES,
            "durable_sqlite_state_readback_has_400_rate": state_summary["rate"] == RATE_CAPTURE,
            "derived_subtotal_is_1600": state_summary["derived_subtotal"] == DERIVED_SUBTOTAL,
            "duplicate_retry_does_not_duplicate": duplicate_readback.write_status == "DUPLICATE_NOOP",
            "closeout_says_what_openclaw_knows": bool(closeout.what_openclaw_knows_now),
            "closeout_says_what_remains_blocked": bool(closeout.what_remains_blocked),
            "external_action_performed_false": not session_result.external_action_performed and not any(item.external_action_performed for item in readbacks),
            "smtp_coupa_model_tool_send_authority_false": (
                AUTHORITY_BOUNDARY["email_send_allowed"] is False
                and AUTHORITY_BOUNDARY["smtp_send_allowed"] is False
                and AUTHORITY_BOUNDARY["coupa_access_allowed"] is False
                and AUTHORITY_BOUNDARY["model_call_allowed"] is False
                and AUTHORITY_BOUNDARY["tool_execution_allowed"] is False
            ),
            "credential_material_included": False,
            "raw_private_content_included": False,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_mission_control_capture_request_intake(payload: dict[str, Any]) -> str:
    closeout = payload["completion_closeout"]
    state = payload["sqlite_readback"]["current_openclaw_state_summary"]
    boundary = payload["authority_boundary"]
    lines = [
        "# Mission Control Capture Request Intake",
        "",
        "## What Landed",
        (
            "This is the backend bridge for a future Capture / Use This Draft button. "
            "The packet is visual-agnostic, so Mission Control, Telegram, or Cassandra can later send the same shape."
        ),
        "",
        "## Captured State",
        f"- Performance dates: `{', '.join(state['performance_dates'])}`",
        f"- Rate: `{state['rate']['display'] if state['rate'] else 'missing'}`",
        f"- Derived subtotal: `${state['derived_subtotal']['amount']:,}`",
        f"- SQLite state source: `{payload['sqlite_readback']['db_path']}`",
        "",
        "## Closeout",
        closeout["captain_message"],
        "",
        "## Still Blocked",
    ]
    lines.extend(f"- {item}" for item in closeout["what_remains_blocked"])
    lines.extend(
        [
            "",
            "## Boundaries",
            f"- Local SQLite capture write: `{str(boundary['local_sqlite_capture_write_allowed_for_enabled_adapters']).lower()}`",
            f"- Batch capture: `{str(boundary['batch_capture_allowed']).lower()}`",
            f"- PO/Coupa capture: `{str(boundary['po_coupa_capture_allowed']).lower()}`",
            f"- Invoice generation: `{str(boundary['invoice_generation_allowed']).lower()}`",
            f"- Email send: `{str(boundary['email_send_allowed']).lower()}`",
            f"- Coupa/browser/Gmail/Telegram access: `{str(boundary['coupa_access_allowed'] or boundary['browser_automation_allowed'] or boundary['gmail_access_allowed'] or boundary['telegram_send_allowed']).lower()}`",
            f"- Model/tool/runtime execution: `{str(boundary['model_call_allowed'] or boundary['tool_execution_allowed'] or boundary['runtime_dispatch_allowed']).lower()}`",
            "",
            "## Next Safe Move",
            closeout["suggested_next_action"],
            "",
        ]
    )
    return "\n".join(lines)


def export_mission_control_capture_request_intake(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
    db_path: str | Path | None = None,
) -> MissionControlCaptureIntakeExportResult:
    root = Path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    payload = build_mission_control_capture_request_intake(
        generated_at=generated_at,
        db_path=db_path,
    )
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_mission_control_capture_request_intake(payload), encoding="utf-8")
    state = payload["sqlite_readback"]["current_openclaw_state_summary"]
    return MissionControlCaptureIntakeExportResult(
        schema_version=payload["schema_version"],
        json_path=str(json_path),
        operator_path=str(operator_path),
        validation_statuses=tuple(item["validation_status"] for item in payload["validations"]),
        write_statuses=tuple(item["write_status"] for item in payload["readbacks"]),
        final_show_count=state["show_count"],
        rate_display=state["rate"]["display"] if state["rate"] else None,
        derived_subtotal=state["derived_subtotal"]["amount"] if state["derived_subtotal"] else None,
        external_action_performed=payload["capture_session_result"]["external_action_performed"],
    )


def _summary(result: MissionControlCaptureIntakeExportResult) -> dict[str, Any]:
    return {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "validation_statuses": result.validation_statuses,
        "write_statuses": result.write_statuses,
        "final_show_count": result.final_show_count,
        "rate_display": result.rate_display,
        "derived_subtotal": result.derived_subtotal,
        "external_action_performed": result.external_action_performed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import/export Mission Control capture request intake.")
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--db", default=None, help="SQLite ledger path. Defaults to Business Ops ledger.")
    parser.add_argument("--file", help="Single visual-agnostic capture request JSON to import.")
    args = parser.parse_args(argv)

    if args.file:
        request = load_capture_request_file(args.file)
        path = init_mission_control_capture_schema(args.db)
        validation = validate_capture_request(
            request,
            existing_idempotency_keys=existing_idempotency_keys(db_path=path),
        )
        readback = write_capture_request(request, validation, db_path=path)
        result = build_capture_session_result((readback,), db_path=path)
        closeout = build_completion_closeout(result)
        output = {
            "validation": asdict(validation),
            "readback": asdict(readback),
            "capture_session_result": asdict(result),
            "completion_closeout": asdict(closeout),
        }
        if args.format == "operator":
            print(closeout.captain_message)
        else:
            print(stable_json(output), end="")
        return 0

    result = export_mission_control_capture_request_intake(
        export_root=args.export_root,
        db_path=args.db,
    )
    if args.format == "summary":
        print(json.dumps(_summary(result), indent=2, sort_keys=True))
    elif args.format == "json":
        print(Path(result.json_path).read_text(encoding="utf-8"), end="")
    else:
        print(Path(result.operator_path).read_text(encoding="utf-8"), end="")
    return 0


__all__ = [
    "ADDED_DATES",
    "AUTHORITY_BOUNDARY",
    "CAPTURED_DATES",
    "CONTRACT_STATUS",
    "CURRENT_DATES",
    "DEFAULT_EXPORT_ROOT",
    "DERIVED_SUBTOTAL",
    "JSON_EXPORT_NAME",
    "MissionControlBlockCaptureRequest",
    "MissionControlCaptureCompletionCloseout",
    "MissionControlCaptureIntakeExportResult",
    "MissionControlCaptureIntakeReadback",
    "MissionControlCaptureIntakeValidation",
    "MissionControlCaptureOutboxContract",
    "MissionControlCaptureSessionResult",
    "OPERATOR_EXPORT_NAME",
    "RATE_CAPTURE",
    "READ_MODEL_ID",
    "REQUIRED_CAPTURE_REQUEST_FIELDS",
    "REQUIRED_CAPTURE_SESSION_RESULT_FIELDS",
    "REQUIRED_CLOSEOUT_FIELDS",
    "REQUIRED_OUTBOX_FIELDS",
    "REQUIRED_READBACK_FIELDS",
    "REQUIRED_VALIDATION_FIELDS",
    "SCHEMA_VERSION",
    "SUPPORTED_BLOCK_ADAPTERS",
    "WORKFLOW_SESSION_REF",
    "build_capture_session_result",
    "build_completion_closeout",
    "build_mission_control_capture_request_intake",
    "build_outbox_contract",
    "default_fixture_capture_requests",
    "derive_idempotency_key",
    "derive_payload_hash",
    "derive_preview_state_hash",
    "existing_idempotency_keys",
    "export_mission_control_capture_request_intake",
    "fixture_performance_dates_request",
    "fixture_rate_confirmation_request",
    "format_mission_control_capture_request_intake",
    "init_mission_control_capture_schema",
    "load_capture_request_file",
    "main",
    "read_workflow_block_state",
    "stable_json",
    "validate_capture_request",
    "write_capture_request",
]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
