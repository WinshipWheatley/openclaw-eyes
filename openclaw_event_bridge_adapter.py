"""OpenClaw Event Bridge runtime adapter v0.

This adapter is the narrow hot-path bridge from Event Bridge envelopes into the
existing request router shape. It validates, maps, and selects the registered
handler only. It does not execute handlers, start services, call models, export
PDFs, send email, open Gmail/browser/Coupa, read workbook cells, mutate ledgers,
or publish responses.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any, Mapping

import openclaw_authority_semantics_registry as authority_registry
import openclaw_event_bridge_contract as contract
import openclaw_request_router


SCHEMA_VERSION = "openclaw_event_bridge_adapter_v0"
ADAPTER_ID = "openclaw_event_bridge_adapter"
CONTRACT_STATUS = "DETERMINISTIC_EVENT_BRIDGE_TO_REQUEST_ROUTER_ADAPTER_NO_EXECUTION"

SUPPORTED_EVENT_KINDS = (
    "UI_BUTTON_CLICK",
    "WORKFLOW_ACTION_REQUEST",
    "LOCAL_SURFACE_RESULT",
    "ARTIFACT_RESULT",
    "TELEGRAM_COMMAND",
)

REQUIRED_SCOPE_FIELDS = (
    "client_ref",
    "workflow_ref",
)

REQUIRED_TRUE_GUARDS = contract.NO_AUTHORITY_GUARD_FIELDS

REQUIRED_TRUE_SAFETY_FLAGS = (
    "hot_path_event",
    "structured_action_required",
    "operator_receipt_required_before_mutation",
)

REQUIRED_FALSE_SAFETY_FLAGS = (
    "old_chat_card_live_action_source_allowed",
    "business_mutation_without_receipt_allowed",
)

REQUEST_FAMILY_BY_REQUEST_TYPE = {
    "INVOICE_REVIEW_ACTION_REQUEST": "LOCAL_SURFACE_RESULT",
    "INVOICE_REVIEW_ACTION_RESULT": "INVOICE_REVIEW_ACTION_RESULT",
    "LOCAL_SURFACE_RESULT": "LOCAL_SURFACE_RESULT",
    "ARTIFACT_RESULT": "LOCAL_SURFACE_RESULT",
}

ADAPTER_AUTHORITY_BOUNDARY = {
    **{key: False for key in contract.AUTHORITY_BOUNDARY},
    **{key: False for key in openclaw_request_router.AUTHORITY_BOUNDARY},
    "handler_execution_allowed": False,
    "processor_execution_allowed": False,
    "service_start_allowed": False,
    "telegram_runtime_allowed": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256(stable_json(parts).encode("utf-8")).hexdigest()[:20]


def _payload(raw_event: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = raw_event.get("payload")
    return payload if isinstance(payload, Mapping) else {}


def _action_kind(raw_event: Mapping[str, Any]) -> str:
    payload = _payload(raw_event)
    for key in ("action_kind", "intended_use", "request_kind"):
        value = str(payload.get(key) or raw_event.get(key) or "").strip()
        if value:
            return value
    command = str(payload.get("command") or "").strip()
    return contract.TELEGRAM_COMMAND_ACTIONS.get(command, "")


def _request_type(raw_event: Mapping[str, Any]) -> str:
    payload = _payload(raw_event)
    for key in ("request_type", "kind", "type", "result_type"):
        value = str(payload.get(key) or "").strip().upper()
        if value:
            return value
    event_kind = str(raw_event.get("event_kind") or "")
    if event_kind in {"UI_BUTTON_CLICK", "WORKFLOW_ACTION_REQUEST", "TELEGRAM_COMMAND"}:
        return "INVOICE_REVIEW_ACTION_REQUEST"
    if event_kind in {"LOCAL_SURFACE_RESULT", "ARTIFACT_RESULT"}:
        return "LOCAL_SURFACE_RESULT"
    return event_kind or "UNKNOWN_FAIL_CLOSED"


def _filename_family(request_type: str) -> str:
    return REQUEST_FAMILY_BY_REQUEST_TYPE.get(request_type, "UNKNOWN_FAIL_CLOSED")


def _source_filename(raw_event: Mapping[str, Any]) -> str:
    event_id = str(raw_event.get("event_id") or "unknown_event")
    safe = "".join(char if char.isalnum() or char in "._-" else "_" for char in event_id)
    return f"event_bridge_{safe[:140]}.json"


def _payload_hash(raw_event: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(stable_json(raw_event).encode("utf-8")).hexdigest()


def _scope(raw_event: Mapping[str, Any]) -> dict[str, str]:
    return {
        "client_ref": str(raw_event.get("client_ref") or ""),
        "workflow_ref": str(raw_event.get("workflow_ref") or ""),
        "world_ref": str(raw_event.get("world_ref") or ""),
        "thread_ref": str(raw_event.get("thread_ref") or ""),
        "source_channel": str(raw_event.get("source_channel") or ""),
        "actor_ref": str(raw_event.get("actor_ref") or ""),
    }


def _base_response(
    raw_event: Mapping[str, Any],
    *,
    route_status: str,
    workflow_status: str,
    operator_copy: str,
    structured_actions: tuple[dict[str, Any], ...] = (),
    processor_request: Mapping[str, Any] | None = None,
    router_envelope: Mapping[str, Any] | None = None,
    router_decision: Mapping[str, Any] | None = None,
    authority_drift_signals: tuple[dict[str, Any], ...] = (),
    positive_replacement_guidance: Mapping[str, Any] | None = None,
    error_code: str = "",
    error_message: str = "",
    retry_allowed: bool = False,
    stale_event: bool = False,
    superseded_by_event_id: str = "",
    next_expected_event: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    response_id = f"event_bridge_adapter_response:{_short_hash(raw_event.get('event_id'), raw_event.get('correlation_id'), route_status, error_code)}"
    return {
        "schema_version": SCHEMA_VERSION,
        "adapter_id": ADAPTER_ID,
        "contract_status": CONTRACT_STATUS,
        "response_id": response_id,
        "event_id": str(raw_event.get("event_id") or ""),
        "correlation_id": str(raw_event.get("correlation_id") or ""),
        "route_status": route_status,
        "workflow_status": workflow_status,
        "operator_copy": operator_copy,
        "structured_actions": structured_actions,
        "processor_request": dict(processor_request or {}),
        "router_envelope": dict(router_envelope or {}),
        "router_decision": dict(router_decision or {}),
        "receipt_refs": (),
        "next_expected_event": dict(next_expected_event or {}),
        "error_code": error_code,
        "error_message": error_message,
        "retry_allowed": retry_allowed,
        "stale_event": stale_event,
        "superseded_by_event_id": superseded_by_event_id,
        "scope": _scope(raw_event),
        "authority_semantics_version": str(
            raw_event.get("authority_semantics_version") or contract.AUTHORITY_SEMANTICS_VERSION
        ),
        "authority_profile_ref": str(
            raw_event.get("authority_profile_ref") or contract.DEFAULT_AUTHORITY_PROFILE_REF
        ),
        "positive_occupation_template_ref": str(
            raw_event.get("positive_occupation_template_ref") or contract.DEFAULT_POSITIVE_OCCUPATION_TEMPLATE_REF
        ),
        "authority_drift_signals": authority_drift_signals,
        "positive_replacement_guidance": dict(
            positive_replacement_guidance or authority_registry.positive_replacement_guidance()
        ),
        "authority_boundary": dict(ADAPTER_AUTHORITY_BOUNDARY),
        "machine_proof": {
            "event_validated": not error_code,
            "processor_request_built": processor_request is not None,
            "router_called": router_decision is not None,
            "handler_selected": bool((router_decision or {}).get("selected_handler_id")),
            "handler_execution_performed": False,
            "processor_execution_performed": False,
            "service_started": False,
            "telegram_runtime_started": False,
            "model_call_performed": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_post_performed": False,
            "workbook_cell_read_performed": False,
            "pdf_export_performed": False,
            "all_authority_false": all(value is False for value in ADAPTER_AUTHORITY_BOUNDARY.values()),
        },
    }


def _scope_errors(raw_event: Mapping[str, Any]) -> tuple[str, ...]:
    errors = []
    for field in REQUIRED_SCOPE_FIELDS:
        if not str(raw_event.get(field) or "").strip():
            errors.append(f"MISSING_SCOPE:{field}")
    return tuple(errors)


def _guard_errors(raw_event: Mapping[str, Any]) -> tuple[str, ...]:
    errors = []
    for field in REQUIRED_TRUE_GUARDS:
        if raw_event.get(field) is not True:
            errors.append(f"GUARD_NOT_TRUE:{field}")
    safety = raw_event.get("safety_flags")
    if not isinstance(safety, Mapping):
        return tuple(errors)
    for field in REQUIRED_TRUE_SAFETY_FLAGS:
        if safety.get(field) is not True:
            errors.append(f"SAFETY_GUARD_NOT_TRUE:{field}")
    for field in REQUIRED_FALSE_SAFETY_FLAGS:
        if safety.get(field) is not False:
            errors.append(f"SAFETY_GUARD_NOT_FALSE:{field}")
    return tuple(errors)


def validate_event_for_adapter(
    raw_event: Mapping[str, Any],
    *,
    now: str | None = None,
    current_action_index: Mapping[tuple[str, str, str], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    authority_validation = authority_registry.validate_authority_semantics(
        raw_event,
        profile_ref=str(raw_event.get("authority_profile_ref") or contract.DEFAULT_AUTHORITY_PROFILE_REF),
        component_ref="openclaw_event_bridge_adapter",
    )
    validation = contract.validate_event(
        raw_event,
        now=now,
        current_action_index=current_action_index,
    )
    errors = list(authority_validation.errors)
    errors.extend(validation.errors)
    errors.extend(_scope_errors(raw_event))
    errors.extend(_guard_errors(raw_event))
    event_kind = str(raw_event.get("event_kind") or "")
    if event_kind and event_kind not in SUPPORTED_EVENT_KINDS:
        errors.append(f"UNSUPPORTED_ADAPTER_EVENT_KIND:{event_kind}")
    return {
        "valid": not errors,
        "errors": tuple(dict.fromkeys(errors)),
        "warnings": authority_validation.warnings,
        "authority_drift_signals": authority_validation.drift_signals,
        "positive_replacement_guidance": authority_validation.positive_replacement_guidance,
        "stale_event": validation.stale_event,
        "stale_reason": validation.stale_reason,
        "superseded_by_event_id": validation.superseded_by_event_id,
        "current_action": validation.current_action,
    }


def processor_request_from_event(raw_event: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(_payload(raw_event))
    action_kind = _action_kind(raw_event)
    request_type = _request_type(raw_event)
    hidden_request_payload = {
        **payload,
        "event_id": str(raw_event.get("event_id") or ""),
        "source_event_id": str(raw_event.get("event_id") or ""),
        "request_id": str(raw_event.get("event_id") or ""),
        "source_request_id": str(raw_event.get("event_id") or ""),
        "idempotency_key": str(raw_event.get("idempotency_key") or ""),
        "correlation_id": str(raw_event.get("correlation_id") or ""),
        "client_ref": str(raw_event.get("client_ref") or ""),
        "workflow_ref": str(raw_event.get("workflow_ref") or ""),
        "source_workflow_id": str(raw_event.get("workflow_ref") or ""),
        "world_ref": str(raw_event.get("world_ref") or ""),
        "thread_ref": str(raw_event.get("thread_ref") or ""),
        "actor_ref": str(raw_event.get("actor_ref") or ""),
        "source_channel": str(raw_event.get("source_channel") or ""),
        "parent_event_id": str(raw_event.get("parent_event_id") or ""),
        "authority_semantics_version": str(raw_event.get("authority_semantics_version") or contract.AUTHORITY_SEMANTICS_VERSION),
        "authority_profile_ref": str(raw_event.get("authority_profile_ref") or contract.DEFAULT_AUTHORITY_PROFILE_REF),
        "positive_occupation_template_ref": str(
            raw_event.get("positive_occupation_template_ref") or contract.DEFAULT_POSITIVE_OCCUPATION_TEMPLATE_REF
        ),
        "request_type": request_type,
        "kind": request_type,
        "type": request_type,
        "action_kind": action_kind,
        "request_kind": action_kind,
        "intended_use": action_kind,
        "no_external_action": True,
        "no_workbook_body_read": True,
        "no_cell_read": True,
        "physical_deletion_allowed": False,
        "no_email_send": True,
        "no_gmail": True,
        "no_browser": True,
        "no_ledger_post": True,
        "no_coupa": True,
        "no_workbook_cell_read": True,
        "no_physical_printing": True,
        "safety_flags": dict(raw_event.get("safety_flags") or {}),
        "authority_boundary": dict(ADAPTER_AUTHORITY_BOUNDARY),
    }
    request = {
        **payload,
        "request_id": str(raw_event.get("event_id") or ""),
        "event_id": str(raw_event.get("event_id") or ""),
        "source_event_id": str(raw_event.get("event_id") or ""),
        "event_kind": str(raw_event.get("event_kind") or ""),
        "source_channel": str(raw_event.get("source_channel") or ""),
        "request_type": request_type,
        "type": request_type,
        "kind": request_type,
        "intended_use": action_kind,
        "action_kind": action_kind,
        "client_ref": str(raw_event.get("client_ref") or ""),
        "workflow_ref": str(raw_event.get("workflow_ref") or ""),
        "world_ref": str(raw_event.get("world_ref") or ""),
        "thread_ref": str(raw_event.get("thread_ref") or ""),
        "actor_ref": str(raw_event.get("actor_ref") or ""),
        "parent_event_id": str(raw_event.get("parent_event_id") or ""),
        "authority_semantics_version": str(raw_event.get("authority_semantics_version") or contract.AUTHORITY_SEMANTICS_VERSION),
        "authority_profile_ref": str(raw_event.get("authority_profile_ref") or contract.DEFAULT_AUTHORITY_PROFILE_REF),
        "positive_occupation_template_ref": str(
            raw_event.get("positive_occupation_template_ref") or contract.DEFAULT_POSITIVE_OCCUPATION_TEMPLATE_REF
        ),
        "idempotency_key": str(raw_event.get("idempotency_key") or ""),
        "correlation_id": str(raw_event.get("correlation_id") or ""),
        "created_at": str(raw_event.get("created_at") or ""),
        "expires_at": str(raw_event.get("expires_at") or ""),
        "payload_hash": _payload_hash(raw_event),
        "safety_flags": dict(raw_event.get("safety_flags") or {}),
        "authority_boundary": dict(ADAPTER_AUTHORITY_BOUNDARY),
        "event_authority_boundary": dict(raw_event.get("authority_boundary") or {}),
        "expected_response_kind": str(raw_event.get("expected_response_kind") or ""),
        "result_receipt_required": bool(raw_event.get("result_receipt_required")),
        "no_email_send": True,
        "no_gmail": True,
        "no_browser": True,
        "no_ledger_post": True,
        "no_coupa": True,
        "no_workbook_cell_read": True,
        "no_physical_printing": True,
        "no_external_action": True,
        "physical_deletion_allowed": False,
        "hidden_request_payload": hidden_request_payload,
    }
    return request


def route_event_bridge_envelope(
    raw_event: Mapping[str, Any],
    *,
    now: str | None = None,
    current_action_index: Mapping[tuple[str, str, str], Mapping[str, Any]] | None = None,
    handlers: tuple[openclaw_request_router.RequestHandlerRegistration, ...] | None = None,
) -> dict[str, Any]:
    validation = validate_event_for_adapter(
        raw_event,
        now=now,
        current_action_index=current_action_index,
    )
    if validation["stale_event"]:
        return _base_response(
            raw_event,
            route_status="ROUTE_REJECTED_STALE_EVENT",
            workflow_status="WORKFLOW_BLOCKED",
            operator_copy="That Event Bridge envelope is stale. Use the current workflow action source.",
            error_code=str(validation["stale_reason"] or "STALE_EVENT"),
            error_message="Old or expired hot-path events are not live action sources.",
            stale_event=True,
            superseded_by_event_id=str(validation["superseded_by_event_id"] or ""),
            next_expected_event=validation["current_action"] or {},
            authority_drift_signals=validation["authority_drift_signals"],
            positive_replacement_guidance=validation["positive_replacement_guidance"],
        )
    if not validation["valid"]:
        errors = tuple(validation["errors"])
        return _base_response(
            raw_event,
            route_status="ROUTE_REJECTED_VALIDATION",
            workflow_status="WORKFLOW_BLOCKED",
            operator_copy="Event Bridge rejected the envelope before request-router adaptation.",
            error_code=errors[0] if errors else "VALIDATION_FAILED",
            error_message="; ".join(errors),
            retry_allowed=True,
            authority_drift_signals=validation["authority_drift_signals"],
            positive_replacement_guidance=validation["positive_replacement_guidance"],
        )

    processor_request = processor_request_from_event(raw_event)
    request_type = str(processor_request.get("request_type") or "")
    router_envelope, router_decision = openclaw_request_router.route_request(
        processor_request,
        source_request_filename=_source_filename(raw_event),
        filename_request_family=_filename_family(request_type),
        handlers=handlers,
    )
    router_envelope_dict = asdict(router_envelope)
    router_decision_dict = asdict(router_decision)
    matched = router_decision.route_status == "ROUTE_MATCHED"
    if matched and request_type in {"LOCAL_SURFACE_RESULT", "INVOICE_REVIEW_ACTION_RESULT", "ARTIFACT_RESULT"}:
        workflow_status = "WORKFLOW_RESULT_ROUTE_MATCHED"
    elif matched:
        workflow_status = "WORKFLOW_ACTION_ROUTED"
    else:
        workflow_status = "WORKFLOW_BLOCKED"
    structured_actions = ()
    if matched:
        structured_actions = (
            {
                "structured_action_kind": "REQUEST_ROUTER_HANDLER_SELECTED",
                "handler_id": router_decision.selected_handler_id,
                "handler_label": router_decision.selected_handler_label,
                "processor_request": processor_request,
                "handler_execution_allowed": False,
                "processor_execution_allowed": False,
                "service_start_allowed": False,
                "authority_boundary": dict(ADAPTER_AUTHORITY_BOUNDARY),
            },
        )
    return _base_response(
        raw_event,
        route_status=router_decision.route_status,
        workflow_status=workflow_status,
        operator_copy=(
            "Event Bridge envelope validated and mapped to the existing request router. "
            "No handler execution or business action was performed."
            if matched
            else "Event Bridge envelope validated, but the existing request router did not select a handler."
        ),
        structured_actions=structured_actions,
        processor_request=processor_request,
        router_envelope=router_envelope_dict,
        router_decision=router_decision_dict,
        error_code="" if matched else router_decision.route_status,
        error_message="" if matched else router_decision.rejected_reason,
        retry_allowed=not matched,
        next_expected_event={
            "event_id": str(raw_event.get("event_id") or ""),
            "correlation_id": str(raw_event.get("correlation_id") or ""),
            "selected_handler_id": router_decision.selected_handler_id,
            "request_type": request_type,
            "intended_use": str(processor_request.get("intended_use") or ""),
        },
        authority_drift_signals=validation["authority_drift_signals"],
        positive_replacement_guidance=validation["positive_replacement_guidance"],
    )


__all__ = [
    "ADAPTER_AUTHORITY_BOUNDARY",
    "ADAPTER_ID",
    "CONTRACT_STATUS",
    "SCHEMA_VERSION",
    "processor_request_from_event",
    "route_event_bridge_envelope",
    "stable_json",
    "validate_event_for_adapter",
]
