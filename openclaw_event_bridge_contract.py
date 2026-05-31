"""OpenClaw Event Bridge Contract v0.

This deterministic contract defines the hot-path event envelope shared by the
Mac app, Telegram, PC services, and future compact channels. It validates and
routes workflow events to structured action payloads only. It does not call a
model, start services, read workbook cells, export PDFs, send email, open
Gmail/Coupa/browser, post ledgers, print, or mutate production state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import openclaw_authority_semantics_registry as authority_registry
import simple_invoice_workflow_fixtures


DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "openclaw_event_bridge_contract_v0"
READ_MODEL_ID = "openclaw_event_bridge_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_HOT_PATH_EVENT_BRIDGE_CONTRACT_NO_EXECUTION"

APPROVED_INBOX = "/mnt/e/openclaw/mission_control_capture_requests/inbox"
APPROVED_RESPONSE_DIR = "/mnt/e/openclaw/mission_control_responses/to_mac"
REQUEST_RESPONSE_SERVICE_REF = "openclaw-request-response.service"
AUTHORITY_SEMANTICS_VERSION = authority_registry.AUTHORITY_SEMANTICS_VERSION
DEFAULT_AUTHORITY_PROFILE_REF = authority_registry.EVENT_BRIDGE_FINANCE_PROFILE_REF
DEFAULT_POSITIVE_OCCUPATION_TEMPLATE_REF = authority_registry.EVENT_BRIDGE_FINANCE_TEMPLATE_REF

EVENT_KINDS = (
    "OPERATOR_MESSAGE",
    "UI_BUTTON_CLICK",
    "WORKFLOW_ACTION_REQUEST",
    "LOCAL_SURFACE_RESULT",
    "FILE_PERMISSION_RESULT",
    "ARTIFACT_RESULT",
    "TELEGRAM_COMMAND",
    "SYSTEM_HEARTBEAT",
)

SOURCE_CHANNELS = (
    "MAC_APP",
    "TELEGRAM",
    "PC_SERVICE",
    "SYSTEM",
)

EVENT_ENVELOPE_FIELDS = (
    "authority_semantics_version",
    "authority_profile_ref",
    "positive_occupation_template_ref",
    "event_id",
    "event_kind",
    "source_channel",
    "client_ref",
    "workflow_ref",
    "world_ref",
    "thread_ref",
    "actor_ref",
    "idempotency_key",
    "created_at",
    "expires_at",
    "correlation_id",
    "parent_event_id",
    "payload",
    "safety_flags",
    "authority_boundary",
    "expected_response_kind",
    "result_receipt_required",
    "no_email_send",
    "no_gmail",
    "no_browser",
    "no_ledger_post",
    "no_coupa",
    "no_workbook_cell_read",
    "no_physical_printing",
)

RESPONSE_ENVELOPE_FIELDS = (
    "response_id",
    "event_id",
    "correlation_id",
    "route_status",
    "workflow_status",
    "operator_copy",
    "structured_actions",
    "receipt_refs",
    "next_expected_event",
    "error_code",
    "error_message",
    "retry_allowed",
    "stale_event",
    "superseded_by_event_id",
)

RESPONSE_SCOPE_FIELDS = (
    "client_ref",
    "workflow_ref",
    "world_ref",
    "thread_ref",
    "source_channel",
    "actor_ref",
)

NO_AUTHORITY_GUARD_FIELDS = (
    "no_email_send",
    "no_gmail",
    "no_browser",
    "no_ledger_post",
    "no_coupa",
    "no_workbook_cell_read",
    "no_physical_printing",
)

EXPECTED_RESPONSE_KINDS = (
    "WORKFLOW_ACTION_RESPONSE",
    "LOCAL_SURFACE_RESULT_RESPONSE",
    "ARTIFACT_RESULT_RESPONSE",
    "VALIDATION_ERROR_RESPONSE",
    "STALE_EVENT_RESPONSE",
    "SYSTEM_HEARTBEAT_RESPONSE",
)

ROUTE_STATUSES = (
    "ROUTE_MATCHED",
    "ROUTE_REJECTED_VALIDATION",
    "ROUTE_REJECTED_STALE_EVENT",
    "ROUTE_REJECTED_UNREGISTERED_INTENT",
    "ROUTE_UNSUPPORTED_KIND",
)

WORKFLOW_STATUSES = (
    "WORKFLOW_ACTION_ROUTED",
    "WORKFLOW_RESULT_CANDIDATE_RECORDED",
    "WORKFLOW_BLOCKED",
    "WORKFLOW_HEARTBEAT_ACK",
)

WORKFLOW_PAYLOAD_SHAPE_REF = "openclaw_event_bridge.workflow_action_payload.v0"
SIMPLE_INVOICE_EVENT_BRIDGE_PDF_ARTIFACT_RAIL_REF = "simple_invoice_event_bridge_pdf_artifact_rail_v0"
SIMPLE_INVOICE_PREPARE_PDF_ACTION_KIND = "prepare_selected_invoice_pdf_artifact"
SIMPLE_INVOICE_PDF_RESULT_ACTION_KIND = "selected_invoice_pdf_export_completed_candidate"
WORKFLOW_PAYLOAD_FIELDS = (
    "payload_shape_ref",
    "authority_semantics_version",
    "authority_profile_ref",
    "positive_occupation_template_ref",
    "request_type",
    "kind",
    "intended_use",
    "action_kind",
    "client_ref",
    "workflow_ref",
    "world_ref",
    "thread_ref",
    "actor_ref",
    "source_channel",
    "source_event_id",
    "parent_event_id",
    "idempotency_key",
    "correlation_id",
    "result_receipt_required",
    "required_receipts",
    "payload",
    "safety_flags",
    "authority_boundary",
    "no_email_send",
    "no_gmail",
    "no_browser",
    "no_ledger_post",
    "no_coupa",
    "no_workbook_cell_read",
    "no_physical_printing",
)

AUTHORITY_BOUNDARY = {
    "model_call_allowed": False,
    "agent_dispatch_allowed": False,
    "tool_execution_allowed": False,
    "workflow_execution_allowed": False,
    "business_mutation_allowed": False,
    "response_publication_allowed": False,
    "email_send_allowed": False,
    "gmail_access_allowed": False,
    "browser_access_allowed": False,
    "browser_automation_allowed": False,
    "coupa_access_allowed": False,
    "coupa_submit_allowed": False,
    "ledger_post_allowed": False,
    "workbook_body_read_allowed": False,
    "workbook_cell_read_allowed": False,
    "pdf_export_allowed": False,
    "artifact_attachment_allowed": False,
    "physical_printing_allowed": False,
    "credential_handling_allowed": False,
    "network_operation_allowed": False,
    "external_action_allowed": False,
    "production_state_mutation_allowed": False,
    "source_workbook_mutation_allowed": False,
}

DEFAULT_SAFETY_FLAGS = {
    "hot_path_event": True,
    "change_sentinel_cold_path": False,
    "telegram_compact_surface": False,
    "old_chat_card_live_action_source_allowed": False,
    "legacy_chat_card_live_action_source_allowed": False,
    "business_mutation_without_receipt_allowed": False,
    "structured_action_required": True,
    "operator_receipt_required_before_mutation": True,
    "result_receipt_required": True,
    **{field: True for field in authority_registry.PROHIBITION_FIELDS},
}

PAYLOAD_FORBIDDEN_TRUE_KEYS = {
    "email_send_allowed",
    "gmail_access_allowed",
    "browser_access_allowed",
    "browser_automation_allowed",
    "browser_allowed",
    "coupa_access_allowed",
    "coupa_submit_allowed",
    "ledger_post_allowed",
    "ledger_posting_allowed",
    "workbook_cell_read_allowed",
    "spreadsheet_cell_read_allowed",
    "physical_printing_allowed",
    "external_action_allowed",
    "business_mutation_allowed",
    "production_mutation_allowed",
}

TELEGRAM_COMMAND_ACTIONS = {
    "/prepare_live_arts_pdf": "prepare_selected_invoice_pdf_artifact",
    "prepare_live_arts_pdf": "prepare_selected_invoice_pdf_artifact",
    "/live_arts_pdf_candidate": "selected_invoice_pdf_export_completed_candidate",
    "live_arts_pdf_candidate": "selected_invoice_pdf_export_completed_candidate",
}


@dataclass(frozen=True)
class EventEnvelope:
    authority_semantics_version: str
    authority_profile_ref: str
    positive_occupation_template_ref: str
    event_id: str
    event_kind: str
    source_channel: str
    client_ref: str
    workflow_ref: str
    world_ref: str
    thread_ref: str
    actor_ref: str
    idempotency_key: str
    created_at: str
    expires_at: str
    correlation_id: str
    parent_event_id: str
    payload: dict[str, Any]
    safety_flags: dict[str, bool]
    authority_boundary: dict[str, bool]
    expected_response_kind: str
    result_receipt_required: bool
    no_email_send: bool
    no_gmail: bool
    no_browser: bool
    no_ledger_post: bool
    no_coupa: bool
    no_workbook_cell_read: bool
    no_physical_printing: bool


@dataclass(frozen=True)
class ResponseEnvelope:
    response_id: str
    event_id: str
    correlation_id: str
    route_status: str
    workflow_status: str
    operator_copy: str
    structured_actions: tuple[dict[str, Any], ...]
    receipt_refs: tuple[str, ...]
    next_expected_event: dict[str, Any]
    error_code: str
    error_message: str
    retry_allowed: bool
    stale_event: bool
    superseded_by_event_id: str
    scope: dict[str, str]


@dataclass(frozen=True)
class EventValidation:
    valid: bool
    errors: tuple[str, ...]
    stale_event: bool
    stale_reason: str
    superseded_by_event_id: str
    current_action: dict[str, Any]


@dataclass(frozen=True)
class WorkflowActionRegistration:
    handler_id: str
    handler_label: str
    action_kind: str
    request_type: str
    event_kinds: tuple[str, ...]
    source_channels: tuple[str, ...]
    world_refs: tuple[str, ...]
    workflow_refs: tuple[str, ...]
    client_refs: tuple[str, ...]
    structured_action_kind: str
    expected_response_kind: str
    workflow_status: str
    result_receipt_required: bool
    required_receipts: tuple[str, ...]
    result_intended_use: str
    operator_copy: str
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _short_hash(*parts: object) -> str:
    text = json.dumps(parts, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


def _parse_datetime(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _default_expires_at(created_at: str) -> str:
    created = _parse_datetime(created_at) or datetime.now(timezone.utc)
    return (created + timedelta(minutes=5)).isoformat(timespec="seconds")


def _scope(raw_event: Mapping[str, Any]) -> dict[str, str]:
    return {
        "client_ref": str(raw_event.get("client_ref") or ""),
        "workflow_ref": str(raw_event.get("workflow_ref") or ""),
        "world_ref": str(raw_event.get("world_ref") or ""),
        "thread_ref": str(raw_event.get("thread_ref") or ""),
        "source_channel": str(raw_event.get("source_channel") or ""),
        "actor_ref": str(raw_event.get("actor_ref") or ""),
    }


def event_scope_key(raw_event: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(raw_event.get("client_ref") or ""),
        str(raw_event.get("workflow_ref") or ""),
        str(raw_event.get("thread_ref") or ""),
    )


def no_authority_boundary(overrides: Mapping[str, bool] | None = None) -> dict[str, bool]:
    boundary = dict(AUTHORITY_BOUNDARY)
    if overrides:
        boundary.update({str(key): bool(value) for key, value in overrides.items()})
    return boundary


def safety_flags(overrides: Mapping[str, bool] | None = None, *, source_channel: str = "") -> dict[str, bool]:
    flags = dict(DEFAULT_SAFETY_FLAGS)
    if source_channel == "TELEGRAM":
        flags["telegram_compact_surface"] = True
    if overrides:
        flags.update({str(key): bool(value) for key, value in overrides.items()})
    return flags


def make_event_envelope(
    *,
    event_kind: str,
    source_channel: str,
    client_ref: str,
    workflow_ref: str,
    world_ref: str,
    thread_ref: str,
    actor_ref: str,
    payload: Mapping[str, Any],
    authority_semantics_version: str = AUTHORITY_SEMANTICS_VERSION,
    authority_profile_ref: str = DEFAULT_AUTHORITY_PROFILE_REF,
    positive_occupation_template_ref: str = DEFAULT_POSITIVE_OCCUPATION_TEMPLATE_REF,
    event_id: str | None = None,
    idempotency_key: str | None = None,
    correlation_id: str | None = None,
    parent_event_id: str = "",
    created_at: str | None = None,
    expires_at: str | None = None,
    safety_flag_overrides: Mapping[str, bool] | None = None,
    authority_boundary_overrides: Mapping[str, bool] | None = None,
    expected_response_kind: str = "WORKFLOW_ACTION_RESPONSE",
    result_receipt_required: bool = True,
    no_email_send: bool = True,
    no_gmail: bool = True,
    no_browser: bool = True,
    no_ledger_post: bool = True,
    no_coupa: bool = True,
    no_workbook_cell_read: bool = True,
    no_physical_printing: bool = True,
) -> dict[str, Any]:
    created = created_at or utc_now()
    expires = expires_at or _default_expires_at(created)
    event_payload = dict(payload)
    computed_event_id = event_id or f"event:{_short_hash(event_kind, source_channel, client_ref, workflow_ref, thread_ref, actor_ref, event_payload, created)}"
    envelope = EventEnvelope(
        authority_semantics_version=authority_semantics_version,
        authority_profile_ref=authority_profile_ref,
        positive_occupation_template_ref=positive_occupation_template_ref,
        event_id=computed_event_id,
        event_kind=event_kind,
        source_channel=source_channel,
        client_ref=client_ref,
        workflow_ref=workflow_ref,
        world_ref=world_ref,
        thread_ref=thread_ref,
        actor_ref=actor_ref,
        idempotency_key=idempotency_key or f"idempotency:{_short_hash(computed_event_id, event_payload)}",
        created_at=created,
        expires_at=expires,
        correlation_id=correlation_id or f"correlation:{_short_hash(client_ref, workflow_ref, thread_ref, computed_event_id)}",
        parent_event_id=parent_event_id,
        payload=event_payload,
        safety_flags=safety_flags(safety_flag_overrides, source_channel=source_channel),
        authority_boundary=no_authority_boundary(authority_boundary_overrides),
        expected_response_kind=expected_response_kind,
        result_receipt_required=result_receipt_required,
        no_email_send=no_email_send,
        no_gmail=no_gmail,
        no_browser=no_browser,
        no_ledger_post=no_ledger_post,
        no_coupa=no_coupa,
        no_workbook_cell_read=no_workbook_cell_read,
        no_physical_printing=no_physical_printing,
    )
    return asdict(envelope)


def make_simple_invoice_prepare_pdf_event(
    *,
    client_ref: str,
    workflow_ref: str,
    thread_ref: str,
    invoice_id: str,
    selected_invoice_summary: str | None = None,
    selected_sheet_label: str = "",
    selected_page_label: str | None = None,
    selected_print_areas: tuple[str, ...] = (),
    source_workbook_mac_path: str = "",
    output_bridge_path: str = "",
    output_mac_path: str = "",
    client_display_name: str = "",
    source_channel: str = "MAC_APP",
    event_kind: str = "WORKFLOW_ACTION_REQUEST",
    event_id: str | None = None,
    parent_event_id: str = "",
    actor_ref: str = "operator:winship",
    created_at: str | None = None,
    expires_at: str | None = None,
    telegram_command: str | None = None,
) -> dict[str, Any]:
    display_name = client_display_name or client_ref.replace("_", " ").title()
    payload: dict[str, Any] = {
        "rail_ref": SIMPLE_INVOICE_EVENT_BRIDGE_PDF_ARTIFACT_RAIL_REF,
        "request_type": "INVOICE_REVIEW_ACTION_REQUEST",
        "action_kind": SIMPLE_INVOICE_PREPARE_PDF_ACTION_KIND,
        "intended_use": SIMPLE_INVOICE_PREPARE_PDF_ACTION_KIND,
        "button_ref": f"{client_ref}.{SIMPLE_INVOICE_PREPARE_PDF_ACTION_KIND}",
        "workflow_payload_shape_ref": WORKFLOW_PAYLOAD_SHAPE_REF,
        "invoice_id": invoice_id,
        "selected_invoice_summary": selected_invoice_summary,
        "selected_sheet_label": selected_sheet_label,
        "selected_page_label": selected_page_label,
        "selected_print_areas": selected_print_areas,
        "source_workbook_mac_path": source_workbook_mac_path,
        "output_bridge_path": output_bridge_path,
        "output_mac_path": output_mac_path,
        "operator_copy": f"Prepare the scoped {display_name} invoice PDF package.",
        "no_email_send": True,
        "no_gmail": True,
        "no_browser": True,
        "no_ledger_post": True,
        "no_coupa": True,
        "no_workbook_cell_read": True,
        "no_physical_printing": True,
    }
    if source_channel == "TELEGRAM" and telegram_command:
        payload["command"] = telegram_command
        payload["compact_surface"] = True
    return make_event_envelope(
        event_id=event_id,
        event_kind=event_kind,
        source_channel=source_channel,
        client_ref=client_ref,
        workflow_ref=workflow_ref,
        world_ref="finance",
        thread_ref=thread_ref,
        actor_ref=actor_ref,
        payload=payload,
        parent_event_id=parent_event_id or f"current_{client_ref}_prepare_pdf_action",
        created_at=created_at,
        expires_at=expires_at,
        expected_response_kind="WORKFLOW_ACTION_RESPONSE",
        result_receipt_required=True,
    )


def make_simple_invoice_pdf_candidate_result_event(
    *,
    client_ref: str,
    workflow_ref: str,
    thread_ref: str,
    invoice_id: str,
    exported_pdf_mac_path: str,
    artifact_filename: str,
    receipt_ref: str,
    client_display_name: str = "",
    source_channel: str = "MAC_APP",
    event_id: str | None = None,
    parent_event_id: str = "",
    actor_ref: str = "operator:winship",
    created_at: str | None = None,
    expires_at: str | None = None,
) -> dict[str, Any]:
    return make_event_envelope(
        event_id=event_id,
        event_kind="LOCAL_SURFACE_RESULT",
        source_channel=source_channel,
        client_ref=client_ref,
        workflow_ref=workflow_ref,
        world_ref="finance",
        thread_ref=thread_ref,
        actor_ref=actor_ref,
        payload={
            "rail_ref": SIMPLE_INVOICE_EVENT_BRIDGE_PDF_ARTIFACT_RAIL_REF,
            "request_type": "LOCAL_SURFACE_RESULT",
            "action_kind": SIMPLE_INVOICE_PDF_RESULT_ACTION_KIND,
            "intended_use": SIMPLE_INVOICE_PDF_RESULT_ACTION_KIND,
            "invoice_id": invoice_id,
            "exported_pdf_mac_path": exported_pdf_mac_path,
            "artifact_filename": artifact_filename,
            "receipt_ref": receipt_ref,
            "artifact_review_status": "OPERATOR_REVIEW_REQUIRED",
            "attachment_ready": False,
            "approval_ready": False,
            "ledger_posting_allowed": False,
            "client_display_name": client_display_name,
            "no_email_send": True,
            "no_gmail": True,
            "no_browser": True,
            "no_ledger_post": True,
            "no_coupa": True,
            "no_workbook_cell_read": True,
            "no_physical_printing": True,
        },
        parent_event_id=parent_event_id or f"current_{client_ref}_prepare_pdf_action",
        created_at=created_at,
        expires_at=expires_at,
        expected_response_kind="LOCAL_SURFACE_RESULT_RESPONSE",
        result_receipt_required=True,
    )


def make_live_arts_prepare_pdf_event(
    *,
    source_channel: str = "MAC_APP",
    event_kind: str = "UI_BUTTON_CLICK",
    event_id: str | None = None,
    parent_event_id: str = "current_live_arts_md_prepare_pdf_action",
    created_at: str = "2026-05-31T14:00:00+00:00",
    expires_at: str = "2026-05-31T14:05:00+00:00",
) -> dict[str, Any]:
    return make_simple_invoice_prepare_pdf_event(
        event_id=event_id,
        event_kind=event_kind,
        source_channel=source_channel,
        client_ref="live_arts_md",
        workflow_ref="live_arts_md_invoice_workflow",
        thread_ref="live_arts_md_invoice_workflow:2026-1001",
        invoice_id="2026-1001",
        selected_sheet_label="June 2026 Speaker Rental",
        selected_print_areas=("A1:H42",),
        client_display_name="Live Arts MD",
        parent_event_id=parent_event_id,
        created_at=created_at,
        expires_at=expires_at,
        telegram_command="/prepare_live_arts_pdf",
    )


def make_live_arts_pdf_candidate_result_event(
    *,
    source_channel: str = "MAC_APP",
    event_id: str | None = None,
    created_at: str = "2026-05-31T14:02:00+00:00",
    expires_at: str = "2026-05-31T14:07:00+00:00",
) -> dict[str, Any]:
    return make_simple_invoice_pdf_candidate_result_event(
        event_id=event_id,
        source_channel=source_channel,
        client_ref="live_arts_md",
        workflow_ref="live_arts_md_invoice_workflow",
        thread_ref="live_arts_md_invoice_workflow:2026-1001",
        invoice_id="2026-1001",
        exported_pdf_mac_path="/Users/winship/Desktop/Live Arts MD Invoice 2026-1001.pdf",
        artifact_filename="Live Arts MD Invoice 2026-1001.pdf",
        receipt_ref="pdf_export_candidate_receipt:live_arts_md:2026-1001",
        client_display_name="Live Arts MD",
        parent_event_id="current_live_arts_md_prepare_pdf_action",
        created_at=created_at,
        expires_at=expires_at,
    )


def _simple_invoice_fixtures() -> tuple[simple_invoice_workflow_fixtures.SimpleInvoiceClientFixture, ...]:
    return tuple(
        fixture
        for fixture in simple_invoice_workflow_fixtures.SIMPLE_INVOICE_WORKFLOW_FIXTURES.values()
        if not fixture.allowed_send_coupa and not fixture.allowed_po
    )


def _simple_invoice_prepare_pdf_registration(
    fixture: simple_invoice_workflow_fixtures.SimpleInvoiceClientFixture,
) -> WorkflowActionRegistration:
    return WorkflowActionRegistration(
        handler_id=f"invoice_review_action_request.{fixture.client_ref}",
        handler_label=f"{fixture.client_display_name} invoice review guided action",
        action_kind=SIMPLE_INVOICE_PREPARE_PDF_ACTION_KIND,
        request_type="INVOICE_REVIEW_ACTION_REQUEST",
        event_kinds=("UI_BUTTON_CLICK", "WORKFLOW_ACTION_REQUEST", "TELEGRAM_COMMAND"),
        source_channels=("MAC_APP", "TELEGRAM"),
        world_refs=("finance",),
        workflow_refs=(fixture.workflow_ref,),
        client_refs=(fixture.client_ref,),
        structured_action_kind="ROUTE_TO_WORKFLOW_ACTION",
        expected_response_kind="WORKFLOW_ACTION_RESPONSE",
        workflow_status="WORKFLOW_ACTION_ROUTED",
        result_receipt_required=True,
        required_receipts=("selected_invoice_pdf_export_requested_receipt",),
        result_intended_use=SIMPLE_INVOICE_PDF_RESULT_ACTION_KIND,
        operator_copy=(
            f"Routed {fixture.client_display_name} Prepare PDF to the workflow action payload. "
            "No email, Gmail, browser, Coupa, ledger, workbook cell read, or printing authority is present."
        ),
        next_safe_move="Run the scoped Mac PDF export package, then return a candidate result receipt.",
    )


def _simple_invoice_pdf_result_registration(
    fixture: simple_invoice_workflow_fixtures.SimpleInvoiceClientFixture,
) -> WorkflowActionRegistration:
    return WorkflowActionRegistration(
        handler_id=f"selected_invoice_pdf_export_completed_candidate.{fixture.client_ref}",
        handler_label=f"{fixture.client_display_name} PDF export candidate result",
        action_kind=SIMPLE_INVOICE_PDF_RESULT_ACTION_KIND,
        request_type="LOCAL_SURFACE_RESULT",
        event_kinds=("LOCAL_SURFACE_RESULT", "ARTIFACT_RESULT"),
        source_channels=("MAC_APP", "PC_SERVICE"),
        world_refs=("finance",),
        workflow_refs=(fixture.workflow_ref,),
        client_refs=(fixture.client_ref,),
        structured_action_kind="REPORT_RESULT_CANDIDATE",
        expected_response_kind="LOCAL_SURFACE_RESULT_RESPONSE",
        workflow_status="WORKFLOW_RESULT_CANDIDATE_RECORDED",
        result_receipt_required=True,
        required_receipts=("selected_invoice_pdf_export_completed_candidate_receipt",),
        result_intended_use="operator_review_pdf_candidate",
        operator_copy=(
            f"Recorded a {fixture.client_display_name} PDF export candidate for operator review only. "
            "Attachment, approval, send, ledger, and workbook-cell authority remain locked."
        ),
        next_safe_move="Review the PDF candidate and provide an approval receipt before any attachment or send step.",
    )


def default_workflow_action_registrations() -> tuple[WorkflowActionRegistration, ...]:
    simple_invoice_registrations = tuple(
        registration
        for fixture in _simple_invoice_fixtures()
        for registration in (
            _simple_invoice_prepare_pdf_registration(fixture),
            _simple_invoice_pdf_result_registration(fixture),
        )
    )
    return (
        *simple_invoice_registrations,
        WorkflowActionRegistration(
            handler_id="invoice_review_action_request.capital_hilton",
            handler_label="Capital Hilton invoice review guided action",
            action_kind="start_invoice_record_selection",
            request_type="INVOICE_REVIEW_ACTION_REQUEST",
            event_kinds=("UI_BUTTON_CLICK", "WORKFLOW_ACTION_REQUEST", "TELEGRAM_COMMAND"),
            source_channels=("MAC_APP", "TELEGRAM"),
            world_refs=("finance",),
            workflow_refs=("capital_hilton_invoice_workflow",),
            client_refs=("capital_hilton",),
            structured_action_kind="ROUTE_TO_WORKFLOW_ACTION",
            expected_response_kind="WORKFLOW_ACTION_RESPONSE",
            workflow_status="WORKFLOW_ACTION_ROUTED",
            result_receipt_required=True,
            required_receipts=("invoice_record_selection_request_receipt",),
            result_intended_use="confirm_invoice_record_selection",
            operator_copy="Routed Capital Hilton invoice page selection to the workflow action payload.",
            next_safe_move="Choose the invoice page or period on the current Mac card.",
        ),
    )


def _walk_dict(value: Any, *, prefix: str = "") -> tuple[tuple[str, Any], ...]:
    entries: list[tuple[str, Any]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            entries.append((path, item))
            entries.extend(_walk_dict(item, prefix=path))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            entries.extend(_walk_dict(item, prefix=f"{prefix}[{index}]"))
    return tuple(entries)


def _action_kind(raw_event: Mapping[str, Any]) -> str:
    payload = raw_event.get("payload") if isinstance(raw_event.get("payload"), Mapping) else {}
    for key in ("action_kind", "intended_use", "request_kind"):
        value = str(payload.get(key) or raw_event.get(key) or "").strip()
        if value:
            return value
    command = str(payload.get("command") or "").strip()
    return TELEGRAM_COMMAND_ACTIONS.get(command, "")


def _matches_scope(allowed: tuple[str, ...], actual: str) -> bool:
    return not allowed or "*" in allowed or actual in allowed


def _matching_registration(
    raw_event: Mapping[str, Any],
    registrations: tuple[WorkflowActionRegistration, ...],
) -> WorkflowActionRegistration | None:
    action_kind = _action_kind(raw_event)
    event_kind = str(raw_event.get("event_kind") or "")
    source_channel = str(raw_event.get("source_channel") or "")
    for registration in registrations:
        if action_kind != registration.action_kind:
            continue
        if event_kind not in registration.event_kinds:
            continue
        if source_channel not in registration.source_channels:
            continue
        if not _matches_scope(registration.world_refs, str(raw_event.get("world_ref") or "")):
            continue
        if not _matches_scope(registration.workflow_refs, str(raw_event.get("workflow_ref") or "")):
            continue
        if not _matches_scope(registration.client_refs, str(raw_event.get("client_ref") or "")):
            continue
        return registration
    return None


def validate_event(
    raw_event: Mapping[str, Any],
    *,
    now: str | None = None,
    current_action_index: Mapping[tuple[str, str, str], Mapping[str, Any]] | None = None,
) -> EventValidation:
    errors: list[str] = []
    missing = [field for field in EVENT_ENVELOPE_FIELDS if field not in raw_event]
    for field in missing:
        errors.append(f"MISSING_FIELD:{field}")
    if not raw_event.get("idempotency_key"):
        errors.append("MISSING_IDEMPOTENCY_KEY")
    if not raw_event.get("correlation_id"):
        errors.append("MISSING_CORRELATION_ID")
    if str(raw_event.get("event_kind") or "") not in EVENT_KINDS:
        errors.append("UNSUPPORTED_EVENT_KIND")
    if str(raw_event.get("source_channel") or "") not in SOURCE_CHANNELS:
        errors.append("UNSUPPORTED_SOURCE_CHANNEL")
    if str(raw_event.get("expected_response_kind") or "") not in EXPECTED_RESPONSE_KINDS:
        errors.append("UNSUPPORTED_EXPECTED_RESPONSE_KIND")

    payload = raw_event.get("payload")
    if not isinstance(payload, Mapping):
        errors.append("INVALID_PAYLOAD")
        payload = {}
    safety = raw_event.get("safety_flags")
    if not isinstance(safety, Mapping):
        errors.append("INVALID_SAFETY_FLAGS")
        safety = {}
    authority = raw_event.get("authority_boundary")
    if not isinstance(authority, Mapping):
        errors.append("INVALID_AUTHORITY_BOUNDARY")
        authority = {}
    authority_validation = authority_registry.validate_authority_semantics(
        raw_event,
        profile_ref=str(raw_event.get("authority_profile_ref") or DEFAULT_AUTHORITY_PROFILE_REF),
    )
    errors.extend(authority_validation.errors)
    for field in NO_AUTHORITY_GUARD_FIELDS:
        if raw_event.get(field) is not True:
            errors.append(f"GUARD_NOT_TRUE:{field}")
    for key in (
        "old_chat_card_live_action_source_allowed",
        "legacy_chat_card_live_action_source_allowed",
        "business_mutation_without_receipt_allowed",
        "email_send_allowed",
        "gmail_access_allowed",
        "browser_access_allowed",
        "browser_automation_allowed",
        "coupa_access_allowed",
        "ledger_post_allowed",
        "workbook_cell_read_allowed",
        "physical_printing_allowed",
        "business_mutation_allowed",
    ):
        if safety.get(key) is True:
            errors.append(f"SAFETY_AUTHORITY_NOT_GRANTED:{key}")
    for path, value in _walk_dict(payload):
        key = path.rsplit(".", 1)[-1]
        if key in PAYLOAD_FORBIDDEN_TRUE_KEYS and value is True:
            errors.append(f"PAYLOAD_AUTHORITY_NOT_GRANTED:{path}")

    created_at = _parse_datetime(raw_event.get("created_at"))
    expires_at = _parse_datetime(raw_event.get("expires_at"))
    if created_at is None:
        errors.append("INVALID_CREATED_AT")
    if expires_at is None:
        errors.append("INVALID_EXPIRES_AT")

    now_dt = _parse_datetime(now) if now else datetime.now(timezone.utc)
    stale_event = False
    stale_reason = ""
    current_action: dict[str, Any] = {}
    superseded_by_event_id = ""
    if expires_at is not None and now_dt >= expires_at:
        stale_event = True
        stale_reason = "STALE_EVENT"
        errors.append("STALE_EVENT")
    if current_action_index:
        current = current_action_index.get(event_scope_key(raw_event))
        if current:
            current_action = dict(current)
            current_event_id = str(current_action.get("event_id") or "")
            parent_event_id = str(raw_event.get("parent_event_id") or "")
            if parent_event_id and current_event_id and parent_event_id != current_event_id:
                stale_event = True
                stale_reason = "SUPERSEDED_EVENT"
                superseded_by_event_id = current_event_id
                errors.append("SUPERSEDED_EVENT")
    return EventValidation(
        valid=not errors,
        errors=tuple(dict.fromkeys(errors)),
        stale_event=stale_event,
        stale_reason=stale_reason,
        superseded_by_event_id=superseded_by_event_id,
        current_action=current_action,
    )


def workflow_payload_from_event(
    raw_event: Mapping[str, Any],
    registration: WorkflowActionRegistration,
) -> dict[str, Any]:
    payload = raw_event.get("payload") if isinstance(raw_event.get("payload"), Mapping) else {}
    required_receipts = registration.required_receipts
    result_receipt_required = bool(raw_event.get("result_receipt_required")) or registration.result_receipt_required
    workflow_payload = {
        "payload_shape_ref": WORKFLOW_PAYLOAD_SHAPE_REF,
        "authority_semantics_version": str(raw_event.get("authority_semantics_version") or AUTHORITY_SEMANTICS_VERSION),
        "authority_profile_ref": str(raw_event.get("authority_profile_ref") or DEFAULT_AUTHORITY_PROFILE_REF),
        "positive_occupation_template_ref": str(
            raw_event.get("positive_occupation_template_ref") or DEFAULT_POSITIVE_OCCUPATION_TEMPLATE_REF
        ),
        "request_type": registration.request_type,
        "kind": registration.request_type,
        "intended_use": registration.action_kind,
        "action_kind": registration.action_kind,
        "client_ref": str(raw_event.get("client_ref") or ""),
        "workflow_ref": str(raw_event.get("workflow_ref") or ""),
        "world_ref": str(raw_event.get("world_ref") or ""),
        "thread_ref": str(raw_event.get("thread_ref") or ""),
        "actor_ref": str(raw_event.get("actor_ref") or ""),
        "source_channel": str(raw_event.get("source_channel") or ""),
        "source_event_id": str(raw_event.get("event_id") or ""),
        "parent_event_id": str(raw_event.get("parent_event_id") or ""),
        "idempotency_key": str(raw_event.get("idempotency_key") or ""),
        "correlation_id": str(raw_event.get("correlation_id") or ""),
        "result_receipt_required": result_receipt_required,
        "required_receipts": required_receipts,
        "payload": dict(payload),
        "safety_flags": dict(raw_event.get("safety_flags") or {}),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "no_email_send": True,
        "no_gmail": True,
        "no_browser": True,
        "no_ledger_post": True,
        "no_coupa": True,
        "no_workbook_cell_read": True,
        "no_physical_printing": True,
    }
    return {field: workflow_payload[field] for field in WORKFLOW_PAYLOAD_FIELDS}


def _next_expected_event(raw_event: Mapping[str, Any], registration: WorkflowActionRegistration) -> dict[str, Any]:
    if registration.structured_action_kind == "REPORT_RESULT_CANDIDATE":
        return {
            "event_kind": "WORKFLOW_ACTION_REQUEST",
            "source_channel": str(raw_event.get("source_channel") or ""),
            "client_ref": str(raw_event.get("client_ref") or ""),
            "workflow_ref": str(raw_event.get("workflow_ref") or ""),
            "thread_ref": str(raw_event.get("thread_ref") or ""),
            "expected_intended_use": "operator_review_pdf_candidate",
            "receipt_required": True,
        }
    return {
        "event_kind": "LOCAL_SURFACE_RESULT",
        "source_channel": str(raw_event.get("source_channel") or ""),
        "client_ref": str(raw_event.get("client_ref") or ""),
        "workflow_ref": str(raw_event.get("workflow_ref") or ""),
        "thread_ref": str(raw_event.get("thread_ref") or ""),
        "expected_intended_use": registration.result_intended_use,
        "receipt_required": registration.result_receipt_required,
    }


def _receipt_refs(raw_event: Mapping[str, Any], registration: WorkflowActionRegistration) -> tuple[str, ...]:
    payload = raw_event.get("payload") if isinstance(raw_event.get("payload"), Mapping) else {}
    refs: list[str] = []
    if registration.structured_action_kind == "REPORT_RESULT_CANDIDATE":
        for key in ("receipt_ref", "receipt_id"):
            if payload.get(key):
                refs.append(str(payload[key]))
    return tuple(dict.fromkeys(refs))


def _response(
    raw_event: Mapping[str, Any],
    *,
    route_status: str,
    workflow_status: str,
    operator_copy: str,
    structured_actions: tuple[dict[str, Any], ...] = (),
    receipt_refs: tuple[str, ...] = (),
    next_expected_event: Mapping[str, Any] | None = None,
    error_code: str = "",
    error_message: str = "",
    retry_allowed: bool = False,
    stale_event: bool = False,
    superseded_by_event_id: str = "",
) -> dict[str, Any]:
    response_id = f"response:{_short_hash(raw_event.get('event_id'), raw_event.get('correlation_id'), route_status, workflow_status, error_code)}"
    envelope = ResponseEnvelope(
        response_id=response_id,
        event_id=str(raw_event.get("event_id") or ""),
        correlation_id=str(raw_event.get("correlation_id") or ""),
        route_status=route_status,
        workflow_status=workflow_status,
        operator_copy=operator_copy,
        structured_actions=structured_actions,
        receipt_refs=receipt_refs,
        next_expected_event=dict(next_expected_event or {}),
        error_code=error_code,
        error_message=error_message,
        retry_allowed=retry_allowed,
        stale_event=stale_event,
        superseded_by_event_id=superseded_by_event_id,
        scope=_scope(raw_event),
    )
    return asdict(envelope)


def route_event(
    raw_event: Mapping[str, Any],
    *,
    now: str | None = None,
    current_action_index: Mapping[tuple[str, str, str], Mapping[str, Any]] | None = None,
    registrations: tuple[WorkflowActionRegistration, ...] | None = None,
) -> dict[str, Any]:
    validation = validate_event(raw_event, now=now, current_action_index=current_action_index)
    if validation.stale_event:
        next_expected = validation.current_action or {
            "event_kind": "WORKFLOW_ACTION_REQUEST",
            "client_ref": str(raw_event.get("client_ref") or ""),
            "workflow_ref": str(raw_event.get("workflow_ref") or ""),
            "thread_ref": str(raw_event.get("thread_ref") or ""),
        }
        return _response(
            raw_event,
            route_status="ROUTE_REJECTED_STALE_EVENT",
            workflow_status="WORKFLOW_BLOCKED",
            operator_copy="That action source is stale. Use the current workflow action instead.",
            next_expected_event=next_expected,
            error_code=validation.stale_reason or "STALE_EVENT",
            error_message="Old chat cards and expired events cannot be live action sources.",
            retry_allowed=False,
            stale_event=True,
            superseded_by_event_id=validation.superseded_by_event_id,
        )
    if not validation.valid:
        return _response(
            raw_event,
            route_status="ROUTE_REJECTED_VALIDATION",
            workflow_status="WORKFLOW_BLOCKED",
            operator_copy="OpenClaw rejected the event envelope before routing.",
            error_code=validation.errors[0] if validation.errors else "VALIDATION_FAILED",
            error_message="; ".join(validation.errors),
            retry_allowed=True,
        )
    if str(raw_event.get("event_kind")) == "SYSTEM_HEARTBEAT":
        return _response(
            raw_event,
            route_status="ROUTE_MATCHED",
            workflow_status="WORKFLOW_HEARTBEAT_ACK",
            operator_copy="Event bridge heartbeat acknowledged.",
            next_expected_event={"event_kind": "SYSTEM_HEARTBEAT", "source_channel": "SYSTEM"},
        )
    registrations = registrations if registrations is not None else default_workflow_action_registrations()
    registration = _matching_registration(raw_event, registrations)
    if registration is None:
        status = "ROUTE_REJECTED_UNREGISTERED_INTENT" if _action_kind(raw_event) else "ROUTE_UNSUPPORTED_KIND"
        return _response(
            raw_event,
            route_status=status,
            workflow_status="WORKFLOW_BLOCKED",
            operator_copy="No bounded workflow action registration matched this event.",
            error_code=status,
            error_message="Register a structured workflow action before this channel can invoke it.",
            retry_allowed=True,
        )
    workflow_payload = workflow_payload_from_event(raw_event, registration)
    structured_action = {
        "structured_action_id": f"structured_action:{_short_hash(raw_event.get('event_id'), registration.handler_id)}",
        "structured_action_kind": registration.structured_action_kind,
        "handler_id": registration.handler_id,
        "handler_label": registration.handler_label,
        "workflow_payload_shape_ref": WORKFLOW_PAYLOAD_SHAPE_REF,
        "workflow_payload": workflow_payload,
        "requires_receipt_before_business_mutation": True,
        "surface_semantics": (
            "COMPACT_SURFACE_NOT_WORKFLOW_BRAIN"
            if raw_event.get("source_channel") == "TELEGRAM"
            else "LOCAL_SURFACE_EVENT_SOURCE"
        ),
        "hot_path": True,
        "change_sentinel_required": False,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    return _response(
        raw_event,
        route_status="ROUTE_MATCHED",
        workflow_status=registration.workflow_status,
        operator_copy=registration.operator_copy,
        structured_actions=(structured_action,),
        receipt_refs=_receipt_refs(raw_event, registration),
        next_expected_event=_next_expected_event(raw_event, registration),
    )


def build_contract_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated = generated_at or utc_now()
    registrations = default_workflow_action_registrations()
    mac_event = make_live_arts_prepare_pdf_event(created_at=generated, expires_at=_default_expires_at(generated))
    telegram_event = make_live_arts_prepare_pdf_event(
        source_channel="TELEGRAM",
        event_kind="TELEGRAM_COMMAND",
        created_at=generated,
        expires_at=_default_expires_at(generated),
    )
    pdf_candidate_event = make_live_arts_pdf_candidate_result_event(created_at=generated, expires_at=_default_expires_at(generated))
    mac_response = route_event(mac_event, now=generated, registrations=registrations)
    telegram_response = route_event(telegram_event, now=generated, registrations=registrations)
    candidate_response = route_event(pdf_candidate_event, now=generated, registrations=registrations)
    mac_payload = mac_response["structured_actions"][0]["workflow_payload"]
    telegram_payload = telegram_response["structured_actions"][0]["workflow_payload"]
    no_gmail_browser_ledger_coupa = all(
        AUTHORITY_BOUNDARY[key] is False
        for key in (
            "gmail_access_allowed",
            "browser_automation_allowed",
            "ledger_post_allowed",
            "coupa_access_allowed",
            "coupa_submit_allowed",
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated,
        "authority_semantics_version": AUTHORITY_SEMANTICS_VERSION,
        "authority_profile_ref": DEFAULT_AUTHORITY_PROFILE_REF,
        "positive_occupation_template_ref": DEFAULT_POSITIVE_OCCUPATION_TEMPLATE_REF,
        "bridge_paths": {
            "approved_inbox": APPROVED_INBOX,
            "approved_response_dir": APPROVED_RESPONSE_DIR,
            "request_response_service_ref": REQUEST_RESPONSE_SERVICE_REF,
        },
        "doctrine": {
            "hot_path": "Immediate operator workflow events route through this envelope without waiting for Change Sentinel.",
            "cold_path": "Change Sentinel remains drift and health observation; it is not a live event router.",
            "telegram_rule": "Telegram is a compact surface that emits the same event contract, not a workflow brain.",
            "receipt_rule": "No business mutation is valid until the workflow-required result receipt is present.",
            "stale_card_rule": "Old chat cards and expired events are rejected or superseded by current action refs.",
        },
        "event_envelope_schema": {
            "required_fields": EVENT_ENVELOPE_FIELDS,
            "event_kinds": EVENT_KINDS,
            "source_channels": SOURCE_CHANNELS,
            "no_authority_guard_fields": NO_AUTHORITY_GUARD_FIELDS,
        },
        "response_envelope_schema": {
            "required_fields": RESPONSE_ENVELOPE_FIELDS,
            "scope_fields": RESPONSE_SCOPE_FIELDS,
            "route_statuses": ROUTE_STATUSES,
            "workflow_statuses": WORKFLOW_STATUSES,
        },
        "workflow_payload_schema": {
            "payload_shape_ref": WORKFLOW_PAYLOAD_SHAPE_REF,
            "required_fields": WORKFLOW_PAYLOAD_FIELDS,
            "mac_and_telegram_share_outer_payload_shape": tuple(mac_payload.keys()) == tuple(telegram_payload.keys()),
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "safety_flags": dict(DEFAULT_SAFETY_FLAGS),
        "authority_semantics": {
            "prohibition_flag_rule": "no_* true means prohibited and belongs in safety_flags or top-level compatibility fields.",
            "authority_grant_rule": "*_allowed true means granted authority and belongs in authority_boundary.",
            "incorrect_authority_boundary_no_browser_true_rejected": {
                "authority_boundary": {"no_browser": True},
                "rejection": "AUTHORITY_SEMANTICS_DRIFT:WRONG_BOOLEAN_POLARITY:authority_boundary.no_browser",
            },
            "correct_safety_flags": {
                "no_browser": True,
                "no_email_send": True,
                "no_ledger_post": True,
            },
            "correct_authority_boundary": {
                "browser_access_allowed": False,
                "email_send_allowed": False,
                "ledger_post_allowed": False,
            },
            "positive_replacement_guidance": authority_registry.positive_replacement_guidance(),
        },
        "registered_workflow_actions": tuple(asdict(registration) for registration in registrations),
        "examples": {
            "mac_prepare_pdf_event": mac_event,
            "mac_prepare_pdf_response": mac_response,
            "telegram_prepare_pdf_event": telegram_event,
            "telegram_prepare_pdf_response": telegram_response,
            "local_surface_pdf_candidate_event": pdf_candidate_event,
            "local_surface_pdf_candidate_response": candidate_response,
            "incorrect_authority_boundary_no_browser_true": {
                **mac_event,
                "authority_boundary": {"no_browser": True},
            },
            "corrected_replacement_envelope": {
                **mac_event,
                "safety_flags": {
                    **dict(mac_event["safety_flags"]),
                    "no_browser": True,
                    "no_email_send": True,
                    "no_ledger_post": True,
                },
                "authority_boundary": {
                    **dict(mac_event["authority_boundary"]),
                    "browser_access_allowed": False,
                    "email_send_allowed": False,
                    "ledger_post_allowed": False,
                },
            },
        },
        "machine_proof": {
            "mac_and_telegram_use_same_event_fields": tuple(mac_event.keys()) == tuple(telegram_event.keys()),
            "mac_and_telegram_same_workflow_payload_shape": tuple(mac_payload.keys()) == tuple(telegram_payload.keys()),
            "telegram_not_workflow_brain": telegram_response["structured_actions"][0]["surface_semantics"]
            == "COMPACT_SURFACE_NOT_WORKFLOW_BRAIN",
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "no_gmail_browser_ledger_coupa_authority": no_gmail_browser_ledger_coupa,
            "change_sentinel_not_in_hot_path": True,
            "service_keeper_may_keep_alive_but_not_required_by_contract": True,
            "result_receipt_required_before_business_mutation": True,
            "old_chat_cards_rejected_policy_present": True,
            "response_scoped_to_client_workflow_thread": True,
            "no_live_service_change_required": True,
            "model_call_performed": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_post_performed": False,
            "workbook_cell_read_performed": False,
            "pdf_export_performed": False,
            "production_mutation_performed": False,
        },
    }


def format_operator_readback(payload: Mapping[str, Any]) -> str:
    actions = payload.get("registered_workflow_actions") or ()
    lines = [
        "# OpenClaw Event Bridge Contract",
        "",
        f"- Status: {payload['contract_status']}",
        "- Hot path: Mac app, Telegram, PC service, and system events share one event envelope.",
        "- Cold path: Change Sentinel observes bridge health/drift; it is not in the event routing loop.",
        "- Telegram: compact surface only; it emits the same structured workflow payload shape.",
        "- Stale cards: expired or superseded events are rejected and point to the current action.",
        "- Authority: `no_*` fields are prohibition flags; `*_allowed` fields are authority grants.",
        "- Authority boundary: no email, Gmail, browser, Coupa, ledger, workbook cell read, PDF export, printing, model call, or production mutation authority is granted.",
        f"- Authority profile: {payload.get('authority_profile_ref', DEFAULT_AUTHORITY_PROFILE_REF)}.",
        "",
        "## Contract Shape",
        "",
        f"- Event fields: {', '.join(EVENT_ENVELOPE_FIELDS)}",
        f"- Response fields: {', '.join(RESPONSE_ENVELOPE_FIELDS)}",
        f"- Response scope fields: {', '.join(RESPONSE_SCOPE_FIELDS)}",
        "",
        "## Registered Hot-Path Actions",
    ]
    for action in actions:
        lines.append(
            f"- {action['handler_id']}: {action['action_kind']} -> {action['structured_action_kind']}"
        )
    lines.extend(
        [
            "",
            "## Readiness",
            "",
            "- READY for contract-level Mac/Telegram parity and deterministic validation.",
            "- NOT a live-service rollout; no service start or production mutation is included.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_exports(
    payload: Mapping[str, Any],
    export_root: Path = DEFAULT_EXPORT_ROOT,
) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_readback(payload), encoding="utf-8")
    return json_path, operator_path


def export_openclaw_event_bridge_contract(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> tuple[dict[str, Any], Path, Path]:
    payload = build_contract_payload(generated_at=generated_at)
    json_path, operator_path = write_exports(payload, export_root=export_root)
    return payload, json_path, operator_path


__all__ = [
    "AUTHORITY_BOUNDARY",
    "AUTHORITY_SEMANTICS_VERSION",
    "CONTRACT_STATUS",
    "DEFAULT_AUTHORITY_PROFILE_REF",
    "DEFAULT_POSITIVE_OCCUPATION_TEMPLATE_REF",
    "EVENT_ENVELOPE_FIELDS",
    "EVENT_KINDS",
    "EXPECTED_RESPONSE_KINDS",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_GUARD_FIELDS",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_ID",
    "RESPONSE_ENVELOPE_FIELDS",
    "RESPONSE_SCOPE_FIELDS",
    "ROUTE_STATUSES",
    "SCHEMA_VERSION",
    "SOURCE_CHANNELS",
    "WORKFLOW_PAYLOAD_FIELDS",
    "WORKFLOW_PAYLOAD_SHAPE_REF",
    "WORKFLOW_STATUSES",
    "SIMPLE_INVOICE_EVENT_BRIDGE_PDF_ARTIFACT_RAIL_REF",
    "SIMPLE_INVOICE_PDF_RESULT_ACTION_KIND",
    "SIMPLE_INVOICE_PREPARE_PDF_ACTION_KIND",
    "build_contract_payload",
    "default_workflow_action_registrations",
    "event_scope_key",
    "export_openclaw_event_bridge_contract",
    "format_operator_readback",
    "make_event_envelope",
    "make_live_arts_pdf_candidate_result_event",
    "make_live_arts_prepare_pdf_event",
    "make_simple_invoice_pdf_candidate_result_event",
    "make_simple_invoice_prepare_pdf_event",
    "no_authority_boundary",
    "route_event",
    "safety_flags",
    "stable_json",
    "validate_event",
    "workflow_payload_from_event",
    "write_exports",
]
