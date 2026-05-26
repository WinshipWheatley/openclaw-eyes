"""Domain-agnostic OpenClaw request router contract v0.

The router normalizes Mission Control request envelopes and selects a
registered handler. It does not execute handlers, read private files, call
models, launch apps, or publish responses.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "openclaw_request_router_v0"
READ_MODEL_ID = "openclaw_request_router"
CONTRACT_STATUS = "DETERMINISTIC_REQUEST_ROUTER_NO_EXECUTION"

ROUTE_STATUSES = (
    "ROUTE_MATCHED",
    "ROUTE_REJECTED_UNREGISTERED_INTENT",
    "ROUTE_BLOCKED_AUTHORITY",
    "ROUTE_UNSUPPORTED_KIND",
)

AUTHORITY_BOUNDARY = {
    "handler_execution_allowed": False,
    "workflow_execution_allowed": False,
    "model_call_allowed": False,
    "agent_dispatch_allowed": False,
    "worker_dispatch_allowed": False,
    "external_action_allowed": False,
    "file_body_read_allowed": False,
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "ocr_allowed": False,
    "browser_allowed": False,
    "network_allowed": False,
    "credential_handling_allowed": False,
    "response_publication_allowed": False,
}


@dataclass(frozen=True)
class RequestRouteEnvelope:
    source_request_id: str
    source_request_filename: str
    filename_request_family: str
    request_kind: str
    intended_use: str
    world_ref: str
    workflow_ref: str
    client_ref: str
    project_ref: str
    tenant_ref: str
    authority_boundary_present: bool
    all_authority_false: bool


@dataclass(frozen=True)
class RequestHandlerRegistration:
    handler_id: str
    handler_label: str
    request_kind: str
    intended_use: str
    world_refs: tuple[str, ...]
    workflow_refs: tuple[str, ...]
    client_refs: tuple[str, ...]
    project_refs: tuple[str, ...]
    adapter_available: bool
    next_safe_move: str


@dataclass(frozen=True)
class RequestRouterDecision:
    router_id: str
    route_status: str
    source_request_id: str
    request_kind: str
    intended_use: str
    world_ref: str
    workflow_ref: str
    client_ref: str
    project_ref: str
    selected_handler_id: str
    selected_handler_label: str
    matched_by: tuple[str, ...]
    rejected_reason: str
    parked: bool
    authority_boundary: dict[str, bool]
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _normalized_kind(raw_request: Mapping[str, Any], fallback: str) -> str:
    for key in ("kind", "type", "request_type", "result_type"):
        value = str(raw_request.get(key) or "").strip().upper()
        if value:
            return value
    return fallback


def envelope_from_request(
    raw_request: Mapping[str, Any],
    *,
    source_request_filename: str = "",
    filename_request_family: str = "UNKNOWN_FAIL_CLOSED",
) -> RequestRouteEnvelope:
    authority = raw_request.get("authority_boundary")
    authority_present = isinstance(authority, Mapping)
    all_authority_false = authority_present and all(value is False for value in authority.values())
    return RequestRouteEnvelope(
        source_request_id=str(raw_request.get("request_id") or "unknown_request"),
        source_request_filename=source_request_filename,
        filename_request_family=filename_request_family,
        request_kind=_normalized_kind(raw_request, filename_request_family),
        intended_use=str(raw_request.get("intended_use") or "").strip(),
        world_ref=str(raw_request.get("world_ref") or "unknown").strip(),
        workflow_ref=str(raw_request.get("workflow_ref") or "unknown").strip(),
        client_ref=str(raw_request.get("client_ref") or "unknown").strip(),
        project_ref=str(raw_request.get("project_ref") or raw_request.get("lane_ref") or "unknown").strip(),
        tenant_ref=str(raw_request.get("tenant_ref") or "unknown").strip(),
        authority_boundary_present=authority_present,
        all_authority_false=all_authority_false,
    )


def capital_hilton_field_mapping_handler() -> RequestHandlerRegistration:
    return RequestHandlerRegistration(
        handler_id="client_invoice_sheet_schema_mapping.capital_hilton",
        handler_label="Capital Hilton invoice sheet schema mapping",
        request_kind="LOCAL_SURFACE_RESULT",
        intended_use="client_invoice_sheet_schema_mapping",
        world_refs=("finance",),
        workflow_refs=("capital_hilton_invoice_workflow",),
        client_refs=("capital_hilton",),
        project_refs=(),
        adapter_available=True,
        next_safe_move="Consume the operator-provided mapping receipt and update audit handoff readiness.",
    )


def readable_artifact_approval_handlers() -> tuple[RequestHandlerRegistration, ...]:
    common = {
        "handler_id": "approve_readable_artifact_reference.generic",
        "handler_label": "Approved readable artifact reference",
        "intended_use": "approve_readable_artifact_reference",
        "world_refs": (),
        "workflow_refs": (),
        "client_refs": (),
        "project_refs": (),
        "adapter_available": True,
        "next_safe_move": "Record the approved readable artifact reference and recompute downstream readiness.",
    }
    return (
        RequestHandlerRegistration(request_kind="LOCAL_SURFACE_RESULT", **common),
        RequestHandlerRegistration(request_kind="ARTIFACT_REFERENCE_APPROVAL", **common),
    )


def default_handler_registrations() -> tuple[RequestHandlerRegistration, ...]:
    return (capital_hilton_field_mapping_handler(), *readable_artifact_approval_handlers())


def _matches_value(expected: str, actual: str) -> bool:
    return expected in {"", "*"} or expected == actual


def _matches_scope(allowed: tuple[str, ...], actual: str) -> bool:
    return not allowed or "*" in allowed or actual in allowed


def _specificity(handler: RequestHandlerRegistration) -> int:
    return sum(
        1
        for value in (
            handler.request_kind,
            handler.intended_use,
            *handler.world_refs,
            *handler.workflow_refs,
            *handler.client_refs,
            *handler.project_refs,
        )
        if value and value != "*"
    )


def _handler_matches(handler: RequestHandlerRegistration, envelope: RequestRouteEnvelope) -> tuple[str, ...]:
    matched: list[str] = []
    if not _matches_value(handler.request_kind, envelope.request_kind):
        return ()
    matched.append("request_kind")
    if not _matches_value(handler.intended_use, envelope.intended_use):
        return ()
    matched.append("intended_use")
    if not _matches_scope(handler.world_refs, envelope.world_ref):
        return ()
    if handler.world_refs:
        matched.append("world_ref")
    if not _matches_scope(handler.workflow_refs, envelope.workflow_ref):
        return ()
    if handler.workflow_refs:
        matched.append("workflow_ref")
    if not _matches_scope(handler.client_refs, envelope.client_ref):
        return ()
    if handler.client_refs:
        matched.append("client_ref")
    if not _matches_scope(handler.project_refs, envelope.project_ref):
        return ()
    if handler.project_refs:
        matched.append("project_ref")
    return tuple(matched)


def _handler_matches_kind_and_intent(handler: RequestHandlerRegistration, envelope: RequestRouteEnvelope) -> tuple[str, ...]:
    if not _matches_value(handler.request_kind, envelope.request_kind):
        return ()
    if not _matches_value(handler.intended_use, envelope.intended_use):
        return ()
    return ("request_kind", "intended_use")


def route_request(
    raw_request: Mapping[str, Any],
    *,
    source_request_filename: str = "",
    filename_request_family: str = "UNKNOWN_FAIL_CLOSED",
    handlers: tuple[RequestHandlerRegistration, ...] | None = None,
) -> tuple[RequestRouteEnvelope, RequestRouterDecision]:
    handlers = handlers if handlers is not None else default_handler_registrations()
    envelope = envelope_from_request(
        raw_request,
        source_request_filename=source_request_filename,
        filename_request_family=filename_request_family,
    )
    router_id = f"request_router:{_short_hash(envelope.source_request_id, envelope.request_kind, envelope.intended_use)}"
    if envelope.authority_boundary_present and not envelope.all_authority_false:
        decision = RequestRouterDecision(
            router_id=router_id,
            route_status="ROUTE_BLOCKED_AUTHORITY",
            source_request_id=envelope.source_request_id,
            request_kind=envelope.request_kind,
            intended_use=envelope.intended_use,
            world_ref=envelope.world_ref,
            workflow_ref=envelope.workflow_ref,
            client_ref=envelope.client_ref,
            project_ref=envelope.project_ref,
            selected_handler_id="",
            selected_handler_label="",
            matched_by=(),
            rejected_reason="Request authority boundary is not all false.",
            parked=True,
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Return a blocked response; do not call a handler.",
        )
        return envelope, decision

    matches: list[tuple[int, RequestHandlerRegistration, tuple[str, ...]]] = []
    scope_validation_matches: list[tuple[int, RequestHandlerRegistration, tuple[str, ...]]] = []
    for handler in handlers:
        matched_by = _handler_matches(handler, envelope)
        if matched_by and handler.adapter_available:
            matches.append((_specificity(handler), handler, matched_by))
            continue
        matched_by = _handler_matches_kind_and_intent(handler, envelope)
        if matched_by and handler.adapter_available:
            scope_validation_matches.append((_specificity(handler), handler, matched_by))
    if matches:
        _score, handler, matched_by = sorted(matches, key=lambda item: item[0], reverse=True)[0]
        decision = RequestRouterDecision(
            router_id=router_id,
            route_status="ROUTE_MATCHED",
            source_request_id=envelope.source_request_id,
            request_kind=envelope.request_kind,
            intended_use=envelope.intended_use,
            world_ref=envelope.world_ref,
            workflow_ref=envelope.workflow_ref,
            client_ref=envelope.client_ref,
            project_ref=envelope.project_ref,
            selected_handler_id=handler.handler_id,
            selected_handler_label=handler.handler_label,
            matched_by=matched_by,
            rejected_reason="",
            parked=False,
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move=handler.next_safe_move,
        )
        return envelope, decision
    if scope_validation_matches:
        _score, handler, matched_by = sorted(scope_validation_matches, key=lambda item: item[0], reverse=True)[0]
        decision = RequestRouterDecision(
            router_id=router_id,
            route_status="ROUTE_MATCHED",
            source_request_id=envelope.source_request_id,
            request_kind=envelope.request_kind,
            intended_use=envelope.intended_use,
            world_ref=envelope.world_ref,
            workflow_ref=envelope.workflow_ref,
            client_ref=envelope.client_ref,
            project_ref=envelope.project_ref,
            selected_handler_id=handler.handler_id,
            selected_handler_label=handler.handler_label,
            matched_by=matched_by,
            rejected_reason="Scope did not fully match router registration; handler must validate required bindings fail-closed.",
            parked=False,
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move=handler.next_safe_move,
        )
        return envelope, decision

    status = "ROUTE_REJECTED_UNREGISTERED_INTENT" if envelope.intended_use else "ROUTE_UNSUPPORTED_KIND"
    decision = RequestRouterDecision(
        router_id=router_id,
        route_status=status,
        source_request_id=envelope.source_request_id,
        request_kind=envelope.request_kind,
        intended_use=envelope.intended_use,
        world_ref=envelope.world_ref,
        workflow_ref=envelope.workflow_ref,
        client_ref=envelope.client_ref,
        project_ref=envelope.project_ref,
        selected_handler_id="",
        selected_handler_label="",
        matched_by=(),
        rejected_reason="No registered handler matched this request kind/intended_use/scope.",
        parked=True,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Return a safe parked response and register a bounded handler before retrying.",
    )
    return envelope, decision


def build_contract_payload() -> dict[str, Any]:
    handlers = default_handler_registrations()
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "route_statuses": ROUTE_STATUSES,
        "registered_handlers": tuple(asdict(handler) for handler in handlers),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "router_has_no_handler_execution": True,
            "router_has_no_response_publication": True,
            "handler_registration_boundary_present": True,
            "future_handlers_can_register_without_transport_change": True,
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }


def write_contract(export_root: Path) -> Path:
    export_root.mkdir(parents=True, exist_ok=True)
    path = export_root / f"{READ_MODEL_ID}.json"
    path.write_text(stable_json(build_contract_payload()), encoding="utf-8")
    return path
