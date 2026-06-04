"""Operator Controller Protocol V0.

Defines verified controller events for Mission Control-class surfaces. This is
the middle protocol between app events and OpenClaw backend packages/gates. It
verifies identity/request integrity, routes to deterministic contracts, and
keeps authority_requested separate from backend-only authority_granted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Operator Controller Protocol.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/operator_controller_protocol.sqlite")

SCHEMA_VERSION = "operator_controller_protocol_v0"
READ_MODEL_ID = "operator_controller_protocol"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "OPERATOR_CONTROLLER_PROTOCOL_READY"
NOT_READY_STATUS = "OPERATOR_CONTROLLER_PROTOCOL_NOT_READY"

REQUEST_TYPE = "OPERATOR_CONTROLLER_EVENT_V0"
EVENT_ACCEPTED_STATUS = "OPERATOR_CONTROLLER_EVENT_ACCEPTED"
EVENT_NEEDS_VERIFICATION_STATUS = "OPERATOR_CONTROLLER_EVENT_NEEDS_VERIFICATION"
EVENT_REJECTED_STATUS = "OPERATOR_CONTROLLER_EVENT_REJECTED"
VERIFICATION_STATUS_VERIFIED = "verified"
VERIFICATION_STATUS_NEEDS_VERIFICATION = "needs_verification"
VERIFICATION_STATUS_REJECTED = "rejected"

ENVELOPE_KEYS = (
    "operator_controller_envelope",
    "controller_envelope",
    "operator_authority_envelope",
)

REQUIRED_ENVELOPE_FIELDS = (
    "envelope_id",
    "operator_ref",
    "app_instance_ref",
    "device_ref",
    "device_class",
    "session_ref",
    "request_hash",
    "created_at",
    "input_surface",
    "current_world_ref",
    "current_thread_ref",
    "operator_verified",
    "app_instance_verified",
    "device_verified",
    "session_verified",
    "verification_status",
)

BACKEND_ONLY_FIELDS = (
    "authority_granted",
    "gate_decision_ref",
    "approval_receipt_ref",
)

DEVICE_CLASSES = ("mac", "ipad", "iphone", "unknown")
INPUT_SURFACES = ("chat", "pad", "card", "dropzone", "proof_drawer")
CONTROLLER_EVENT_TYPES = (
    "chat_goal",
    "do_it",
    "approve",
    "deny",
    "attach_proof",
    "ask_why",
    "open_lane",
    "stage_plan",
    "continue",
    "request_rework",
    "mark_informational",
    "stop_hold_cancel",
    "show_details",
)

ACTION_PAYLOAD_TYPES = (
    "navigate",
    "stage_package_request",
    "system_question",
    "inspect_proof",
    "review_decision",
    "workbook_registration",
    "record_payment_proof_intake",
    "explain_gate",
    "none",
)

FORBIDDEN_BUSINESS_ACTION_PAYLOAD_TYPES = (
    "email_send",
    "gmail_access",
    "browser_access",
    "coupa_access",
    "portal_submit",
    "ledger_post",
    "ledger_mutation",
    "workbook_mutation",
    "pdf_export",
    "mark_paid",
    "merge",
    "git_push",
    "worker_spawn",
    "external_provider_call",
)

PRECONDITIONS = {
    "operator_runtime_chain_current_state_audit": {
        "filename": "operator_runtime_chain_current_state_audit.json",
        "accepted_statuses": ("OPERATOR_RUNTIME_CHAIN_CURRENT_STATE_AUDIT_READY",),
    },
    "dynamic_card_packet": {
        "filename": "dynamic_card_packet_latest.json",
        "accepted_statuses": ("DYNAMIC_CARD_PACKET_READY",),
    },
    "operator_action_payloads": {
        "filename": "operator_action_payloads.json",
        "accepted_statuses": ("OPERATOR_ACTION_PAYLOADS_READY",),
    },
    "verified_evidence_intake": {
        "filename": "evidence_intake_status.json",
        "accepted_statuses": ("EVIDENCE_INTAKE_READY",),
    },
}

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_posting_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_source_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "business_action_allowed": False,
    "external_action_allowed": False,
    "authority_grant_allowed": False,
    "worker_spawn_allowed": False,
    "git_push_allowed": False,
    "sent": False,
    "paid": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | {
    "email_send_performed",
    "email_sent",
    "gmail_access_performed",
    "gmail_opened",
    "browser_access_performed",
    "browser_opened",
    "coupa_access_performed",
    "coupa_opened",
    "coupa_submit_performed",
    "portal_submit_performed",
    "ledger_posting_performed",
    "ledger_mutation_performed",
    "workbook_mutation_performed",
    "pdf_export_performed",
    "paid_marking_performed",
    "mark_paid_performed",
    "submit_performed",
    "business_action_performed",
    "authority_grant_performed",
    "authority_granted_by_event",
    "worker_spawn_performed",
    "worker_execution_performed",
    "child_agent_run_performed",
    "external_llm_invoked",
    "external_provider_connected",
    "local_model_runtime_connected",
    "model_invoked",
    "git_push_performed",
    "push_performed",
    "merge_performed",
}


EVENT_TYPE_CONTRACTS: dict[str, dict[str, Any]] = {
    "chat_goal": {
        "allowed_source_surfaces": ("chat", "pad"),
        "required_current_context": ("current_world_ref", "current_thread_ref"),
        "expected_backend_route": "openclaw_request_processor.contextual_goal_or_workflow_composer",
        "contract_ref": "generated/read_models/operator_action_payloads.json",
        "allowed_action_payload_types": ("system_question", "stage_package_request", "navigate"),
        "forbidden_action_payload_types": FORBIDDEN_BUSINESS_ACTION_PAYLOAD_TYPES,
        "receipt_required": False,
        "dynamic_card_response_required": True,
    },
    "do_it": {
        "allowed_source_surfaces": ("chat", "pad", "card"),
        "required_current_context": ("current_world_ref", "current_thread_ref"),
        "expected_backend_route": "operator_action_payload_gate.contextual_safe_action",
        "contract_ref": "generated/read_models/operator_action_payloads.json",
        "allowed_action_payload_types": ("system_question", "stage_package_request", "navigate"),
        "forbidden_action_payload_types": FORBIDDEN_BUSINESS_ACTION_PAYLOAD_TYPES,
        "receipt_required": True,
        "dynamic_card_response_required": True,
    },
    "approve": {
        "allowed_source_surfaces": ("card", "pad"),
        "required_current_context": ("current_world_ref", "current_thread_ref", "active_entity_ref"),
        "expected_backend_route": "workroom_review_decision_or_guardian_approval_queue",
        "contract_ref": "generated/read_models/workroom_review_decision_contract.json",
        "allowed_action_payload_types": ("review_decision", "explain_gate"),
        "forbidden_action_payload_types": FORBIDDEN_BUSINESS_ACTION_PAYLOAD_TYPES,
        "receipt_required": True,
        "dynamic_card_response_required": True,
    },
    "deny": {
        "allowed_source_surfaces": ("card", "pad"),
        "required_current_context": ("current_world_ref", "current_thread_ref", "active_entity_ref"),
        "expected_backend_route": "workroom_review_decision_or_approval_request_queue",
        "contract_ref": "generated/read_models/workroom_review_decision_contract.json",
        "allowed_action_payload_types": ("review_decision", "explain_gate"),
        "forbidden_action_payload_types": FORBIDDEN_BUSINESS_ACTION_PAYLOAD_TYPES,
        "receipt_required": True,
        "dynamic_card_response_required": True,
    },
    "attach_proof": {
        "allowed_source_surfaces": ("dropzone", "proof_drawer", "card"),
        "required_current_context": ("current_world_ref", "current_thread_ref"),
        "expected_backend_route": "evidence_intake.record_candidate_evidence",
        "contract_ref": "generated/read_models/evidence_intake_contract.json",
        "allowed_action_payload_types": ("record_payment_proof_intake", "inspect_proof"),
        "forbidden_action_payload_types": FORBIDDEN_BUSINESS_ACTION_PAYLOAD_TYPES,
        "receipt_required": True,
        "dynamic_card_response_required": True,
    },
    "ask_why": {
        "allowed_source_surfaces": ("chat", "pad", "card", "proof_drawer"),
        "required_current_context": ("current_world_ref", "current_thread_ref"),
        "expected_backend_route": "system_question_answer.contextual_answer",
        "contract_ref": "generated/read_models/system_question_answer_contract.json",
        "allowed_action_payload_types": ("system_question", "inspect_proof"),
        "forbidden_action_payload_types": FORBIDDEN_BUSINESS_ACTION_PAYLOAD_TYPES,
        "receipt_required": False,
        "dynamic_card_response_required": True,
    },
    "open_lane": {
        "allowed_source_surfaces": ("chat", "pad", "card"),
        "required_current_context": ("current_world_ref", "current_thread_ref"),
        "expected_backend_route": "operator_action_payloads.navigate",
        "contract_ref": "generated/read_models/operator_action_payloads.json",
        "allowed_action_payload_types": ("navigate",),
        "forbidden_action_payload_types": FORBIDDEN_BUSINESS_ACTION_PAYLOAD_TYPES,
        "receipt_required": False,
        "dynamic_card_response_required": True,
    },
    "stage_plan": {
        "allowed_source_surfaces": ("chat", "pad", "card"),
        "required_current_context": ("current_world_ref", "current_thread_ref"),
        "expected_backend_route": "workflow_composer_or_workflow_package_request_consumer.stage_only",
        "contract_ref": "generated/read_models/workflow_composer_contract.json",
        "allowed_action_payload_types": ("stage_package_request",),
        "forbidden_action_payload_types": FORBIDDEN_BUSINESS_ACTION_PAYLOAD_TYPES,
        "receipt_required": True,
        "dynamic_card_response_required": True,
    },
    "continue": {
        "allowed_source_surfaces": ("chat", "pad", "card"),
        "required_current_context": ("current_world_ref", "current_thread_ref"),
        "expected_backend_route": "operator_action_payload_gate.continue_safe_local_flow",
        "contract_ref": "generated/read_models/operator_action_payloads.json",
        "allowed_action_payload_types": ("system_question", "stage_package_request", "navigate"),
        "forbidden_action_payload_types": FORBIDDEN_BUSINESS_ACTION_PAYLOAD_TYPES,
        "receipt_required": True,
        "dynamic_card_response_required": True,
    },
    "request_rework": {
        "allowed_source_surfaces": ("card", "pad"),
        "required_current_context": ("current_world_ref", "current_thread_ref", "active_entity_ref"),
        "expected_backend_route": "workroom_review_decision_consumer.request_rework",
        "contract_ref": "generated/read_models/workroom_review_decision_contract.json",
        "allowed_action_payload_types": ("review_decision",),
        "forbidden_action_payload_types": FORBIDDEN_BUSINESS_ACTION_PAYLOAD_TYPES,
        "receipt_required": True,
        "dynamic_card_response_required": True,
    },
    "mark_informational": {
        "allowed_source_surfaces": ("card", "pad"),
        "required_current_context": ("current_world_ref", "current_thread_ref", "active_entity_ref"),
        "expected_backend_route": "workroom_review_decision_consumer.mark_informational",
        "contract_ref": "generated/read_models/workroom_review_decision_contract.json",
        "allowed_action_payload_types": ("review_decision",),
        "forbidden_action_payload_types": FORBIDDEN_BUSINESS_ACTION_PAYLOAD_TYPES,
        "receipt_required": True,
        "dynamic_card_response_required": True,
    },
    "stop_hold_cancel": {
        "allowed_source_surfaces": ("chat", "pad", "card"),
        "required_current_context": ("current_world_ref", "current_thread_ref"),
        "expected_backend_route": "approval_request_queue_or_workroom_review_decision_consumer.stop_hold_cancel",
        "contract_ref": "generated/read_models/approval_request_queue.json",
        "allowed_action_payload_types": ("review_decision", "explain_gate"),
        "forbidden_action_payload_types": FORBIDDEN_BUSINESS_ACTION_PAYLOAD_TYPES,
        "receipt_required": True,
        "dynamic_card_response_required": True,
    },
    "show_details": {
        "allowed_source_surfaces": ("card", "pad", "proof_drawer"),
        "required_current_context": ("current_world_ref", "current_thread_ref"),
        "expected_backend_route": "dynamic_card_packet.proof_drawer",
        "contract_ref": "generated/read_models/dynamic_card_packet_latest.json",
        "allowed_action_payload_types": ("inspect_proof", "none"),
        "forbidden_action_payload_types": FORBIDDEN_BUSINESS_ACTION_PAYLOAD_TYPES,
        "receipt_required": False,
        "dynamic_card_response_required": True,
    },
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _short_hash(*parts: object, length: int = 16) -> str:
    joined = "\0".join(str(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:length]


def _copy_without_request_hash(payload: Any) -> Any:
    if isinstance(payload, Mapping):
        return {
            str(key): _copy_without_request_hash(value)
            for key, value in payload.items()
            if key != "request_hash"
        }
    if isinstance(payload, list):
        return [_copy_without_request_hash(item) for item in payload]
    return payload


def compute_request_hash(request_payload: Mapping[str, Any]) -> str:
    canonical = _copy_without_request_hash(request_payload)
    digest = hashlib.sha256(stable_json(canonical).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _load_json(path: Path) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _status(payload: Mapping[str, Any]) -> str:
    for key in ("status", "readiness_status", "contract_status"):
        value = payload.get(key)
        if value:
            return str(value)
    return ""


def _source_ref(filename: str) -> str:
    return f"generated/read_models/{filename}"


def _precondition_rows(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for precondition_ref, spec in PRECONDITIONS.items():
        filename = str(spec["filename"])
        payload = _load_json(_rooted(read_model_root) / filename)
        observed = _status(payload)
        accepted = tuple(str(status) for status in spec["accepted_statuses"])
        rows.append(
            {
                "precondition_ref": precondition_ref,
                "observed_status": observed,
                "accepted_statuses": list(accepted),
                "ready": observed in accepted,
                "source_ref": _source_ref(filename),
            }
        )
    return rows


def _present(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _extract_envelope(payload: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    for key in ENVELOPE_KEYS:
        envelope = payload.get(key)
        if isinstance(envelope, Mapping):
            return key, dict(envelope)
    if any(field in payload for field in REQUIRED_ENVELOPE_FIELDS):
        return "top_level", dict(payload)
    return "", {}


def _incoming_backend_only_fields(payload: Mapping[str, Any], envelope: Mapping[str, Any]) -> list[str]:
    fields: list[str] = []
    for field in BACKEND_ONLY_FIELDS:
        if field in payload:
            fields.append(field)
        if field in envelope:
            fields.append(f"envelope.{field}")
    return fields


def _authority_requested(payload: Mapping[str, Any], envelope: Mapping[str, Any]) -> list[str]:
    top_level = _normalize_list(payload.get("authority_requested"))
    envelope_value = _normalize_list(envelope.get("authority_requested"))
    return top_level or envelope_value


def _event_type(payload: Mapping[str, Any], envelope: Mapping[str, Any]) -> str:
    return str(
        payload.get("event_type")
        or payload.get("controller_event_type")
        or envelope.get("event_type")
        or envelope.get("controller_event_type")
        or ""
    ).strip()


def _event_contract(event_type: str) -> dict[str, Any]:
    return dict(EVENT_TYPE_CONTRACTS.get(event_type) or {})


def validate_controller_event(payload: Mapping[str, Any], *, enforce_request_hash: bool = True) -> dict[str, Any]:
    blockers: list[str] = []
    rejected_reasons: list[str] = []
    envelope_key, envelope = _extract_envelope(payload)
    if not envelope:
        blockers.append("operator_controller_envelope_missing")

    for field in REQUIRED_ENVELOPE_FIELDS:
        if field in {"operator_verified", "app_instance_verified", "device_verified", "session_verified"}:
            if field not in envelope:
                blockers.append(f"{field}_missing")
            continue
        if not _present(envelope.get(field)):
            blockers.append(f"{field}_missing")

    event_type = _event_type(payload, envelope)
    if event_type not in CONTROLLER_EVENT_TYPES:
        blockers.append("event_type_invalid_or_missing")
    contract = _event_contract(event_type)

    device_class = str(envelope.get("device_class") or "")
    if device_class and device_class not in DEVICE_CLASSES:
        blockers.append("device_class_invalid")

    input_surface = str(envelope.get("input_surface") or payload.get("input_surface") or "")
    if input_surface and input_surface not in INPUT_SURFACES:
        blockers.append("input_surface_invalid")
    elif contract and input_surface not in contract["allowed_source_surfaces"]:
        blockers.append("input_surface_not_allowed_for_event_type")

    if contract:
        for context_field in contract["required_current_context"]:
            if not _present(envelope.get(context_field)):
                blockers.append(f"{context_field}_missing")

    incoming_backend_only_fields = _incoming_backend_only_fields(payload, envelope)
    if incoming_backend_only_fields:
        rejected_reasons.append("incoming_backend_only_authority_fields_not_accepted")

    verification_status_claim = str(envelope.get("verification_status") or "")
    local_dev_verified = envelope.get("local_dev_verified") is True
    verification_flags = {
        "operator_verified": envelope.get("operator_verified") is True,
        "app_instance_verified": envelope.get("app_instance_verified") is True,
        "device_verified": envelope.get("device_verified") is True,
        "session_verified": envelope.get("session_verified") is True,
    }
    production_verified = all(verification_flags.values()) and verification_status_claim == VERIFICATION_STATUS_VERIFIED
    if not production_verified and not local_dev_verified:
        for field, verified in verification_flags.items():
            if not verified:
                blockers.append(f"{field}_false_or_missing")
        if verification_status_claim != VERIFICATION_STATUS_VERIFIED:
            blockers.append("verification_status_not_verified")

    if verification_status_claim not in {
        VERIFICATION_STATUS_VERIFIED,
        VERIFICATION_STATUS_NEEDS_VERIFICATION,
        VERIFICATION_STATUS_REJECTED,
    }:
        blockers.append("verification_status_invalid")

    request_hash = str(envelope.get("request_hash") or "")
    expected_request_hash = ""
    request_hash_checked = False
    if enforce_request_hash and request_hash:
        expected_request_hash = compute_request_hash(payload)
        request_hash_checked = True
        if request_hash != expected_request_hash:
            blockers.append("request_hash_mismatch")

    authority_requested = _authority_requested(payload, envelope)
    if "authority_requested" in payload and not isinstance(payload.get("authority_requested"), list):
        blockers.append("authority_requested_not_list")
    if "authority_requested" in envelope and not isinstance(envelope.get("authority_requested"), list):
        blockers.append("envelope_authority_requested_not_list")

    if rejected_reasons:
        verification_status = VERIFICATION_STATUS_REJECTED
        event_status = EVENT_REJECTED_STATUS
    elif blockers:
        verification_status = VERIFICATION_STATUS_NEEDS_VERIFICATION
        event_status = EVENT_NEEDS_VERIFICATION_STATUS
    else:
        verification_status = VERIFICATION_STATUS_VERIFIED
        event_status = EVENT_ACCEPTED_STATUS

    verified = verification_status == VERIFICATION_STATUS_VERIFIED
    production_authority_eligible = verified and production_verified and not local_dev_verified
    return {
        "schema_version": SCHEMA_VERSION,
        "event_status": event_status,
        "verification_status": verification_status,
        "verified": verified,
        "envelope_key": envelope_key,
        "blockers": blockers,
        "rejected_reasons": rejected_reasons,
        "event_type": event_type,
        "envelope_id": str(envelope.get("envelope_id") or ""),
        "operator_ref": str(envelope.get("operator_ref") or ""),
        "app_instance_ref": str(envelope.get("app_instance_ref") or ""),
        "device_ref": str(envelope.get("device_ref") or ""),
        "device_class": device_class,
        "session_ref": str(envelope.get("session_ref") or ""),
        "request_hash": request_hash,
        "request_hash_checked": request_hash_checked,
        "expected_request_hash": expected_request_hash if request_hash_checked else "",
        "created_at": str(envelope.get("created_at") or ""),
        "input_surface": input_surface,
        "current_world_ref": str(envelope.get("current_world_ref") or ""),
        "current_thread_ref": str(envelope.get("current_thread_ref") or ""),
        "active_entity_ref": str(envelope.get("active_entity_ref") or ""),
        "authority_requested": authority_requested,
        "authority_granted": [],
        "gate_decision_ref": "",
        "approval_receipt_ref": "",
        "operator_verified": verification_flags["operator_verified"],
        "app_instance_verified": verification_flags["app_instance_verified"],
        "device_verified": verification_flags["device_verified"],
        "session_verified": verification_flags["session_verified"],
        "local_dev_verified": local_dev_verified,
        "production_authority_eligible": production_authority_eligible,
        "incoming_backend_only_fields": incoming_backend_only_fields,
        "incoming_authority_granted_accepted": False,
        "event_contract": contract,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "lm_cannot_generate_or_modify_verification": True,
            "lm_cannot_grant_authority": True,
            "incoming_authority_granted_rejected_or_ignored": bool(incoming_backend_only_fields),
            "authority_requested_does_not_imply_authority_granted": True,
            "authority_granted_backend_only": True,
            "missing_device_app_session_fails_closed_unless_local_dev": True,
            "local_dev_verified_not_production_authority": local_dev_verified and not production_authority_eligible,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "business_action_performed": False,
            "authority_grant_performed": False,
            "external_llm_invoked": False,
            "external_provider_connected": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
            "git_push_performed": False,
            "merge_performed": False,
        },
    }


def route_controller_event(validation: Mapping[str, Any], payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    event_type = str(validation.get("event_type") or "")
    contract = _event_contract(event_type)
    world_ref = str(validation.get("current_world_ref") or "")
    thread_ref = str(validation.get("current_thread_ref") or "")
    active_entity_ref = str(validation.get("active_entity_ref") or "")
    route_ref = str(contract.get("expected_backend_route") or "operator_controller_protocol.parked")
    contract_ref = str(contract.get("contract_ref") or "")
    route_label = "Generic verified controller event"

    if event_type == "attach_proof":
        route_label = "Verified proof attachment to evidence intake"
        contract_ref = "generated/read_models/evidence_intake_contract.json"
    elif event_type == "do_it" and world_ref == "finance" and thread_ref == "capital_hilton":
        route_ref = "system_question_answer.finance.capital_hilton.payment_watch"
        contract_ref = "generated/read_models/system_question_answer_contract.json"
        route_label = "Finance / Capital Hilton payment watch"
    elif event_type == "approve" and any(term in active_entity_ref for term in ("guardian", "approval", "gate")):
        route_ref = "approval_request_queue.record_decision_then_gate_decision_ledger"
        contract_ref = "generated/read_models/approval_request_queue.json"
        route_label = "Guardian approval decision recording only"
    elif event_type in {"approve", "request_rework", "mark_informational"}:
        route_ref = "workroom_review_decision_consumer.record_review_decision"
        contract_ref = "generated/read_models/workroom_review_decision_contract.json"
        route_label = "Build review packet decision recording only"
    elif event_type == "stage_plan" and world_ref == "business_development":
        route_ref = "workflow_composer.stage_business_development_followup"
        contract_ref = "generated/read_models/capital_hilton_business_development_proposal.json"
        route_label = "Business Development follow-up staging only"

    payment = {
        "financial_sensitive": event_type == "attach_proof" and world_ref == "finance",
        "paid": False,
        "ledger_mutation_performed": False,
        "paid_marking_performed": False,
    }
    dynamic_card = {
        "required": bool(contract.get("dynamic_card_response_required", True)),
        "headline": "Payment proof received" if event_type == "attach_proof" else "Controller event received",
        "trust_state": "operator_reported" if event_type == "attach_proof" else "trusted_current",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    if event_type == "do_it" and world_ref == "finance" and thread_ref == "capital_hilton":
        dynamic_card["headline"] = "Stay on payment watch"
        dynamic_card["summary"] = "Coupa is processing. Wait for payment evidence before anything touches the ledger."
    elif event_type == "stage_plan" and world_ref == "business_development":
        dynamic_card["headline"] = "Follow-up draft can be staged"
        dynamic_card["summary"] = "Stage a follow-up draft or plan only. No send authority is granted."
    elif event_type in {"approve", "request_rework", "mark_informational"}:
        dynamic_card["headline"] = "Review decision recorded"
        dynamic_card["summary"] = "Record review decision only. No merge, push, worker, or business action is granted."

    return {
        "route_ref": route_ref,
        "route_label": route_label,
        "contract_ref": contract_ref,
        "allowed_action_payload_types": list(contract.get("allowed_action_payload_types") or ()),
        "forbidden_action_payload_types": list(contract.get("forbidden_action_payload_types") or ()),
        "receipt_required": bool(contract.get("receipt_required")),
        "dynamic_card_response_required": bool(contract.get("dynamic_card_response_required", True)),
        "proof_required": True,
        "proof_requirements": [
            "verified operator/app/device/session envelope",
            "request_hash match",
            "current lane context",
            "backend route contract",
            "receipt when required by event type",
        ],
        "dynamic_card_response": dynamic_card,
        "payment": payment,
        "authority_requested": list(validation.get("authority_requested") or []),
        "authority_granted": [],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "ledger_mutation_performed": False,
            "paid_marking_performed": False,
            "email_send_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "business_action_performed": False,
            "merge_performed": False,
            "git_push_performed": False,
            "worker_spawn_performed": False,
            "external_llm_invoked": False,
            "external_provider_connected": False,
        },
    }


def build_controller_event_record(payload: Mapping[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    validation = validate_controller_event(payload)
    route = route_controller_event(validation, payload)
    event_id = "operator_controller_event:" + _short_hash(
        validation.get("envelope_id"),
        validation.get("event_type"),
        validation.get("request_hash"),
    )
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "event_id": event_id,
        "event_status": validation["event_status"],
        "verification_status": validation["verification_status"],
        "generated_at": generated_at,
        "event_type": validation["event_type"],
        "envelope": validation,
        "route": route,
        "authority_requested": list(validation["authority_requested"]),
        "authority_granted": [],
        "receipt_required": bool(route["receipt_required"]),
        "dynamic_card_response_required": bool(route["dynamic_card_response_required"]),
        "proof_required": True,
        "lm_interpretation_boundary": {
            "lm_may_summarize_goal": True,
            "lm_may_choose_candidate_route_from_contract": True,
            "lm_may_not_generate_verification": True,
            "lm_may_not_modify_verification": True,
            "lm_may_not_grant_authority": True,
            "lm_output_is_not_truth": True,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "authority_requested_does_not_imply_authority_granted": True,
            "authority_granted_backend_only": True,
            "dynamic_card_response_required_when_declared": bool(route["dynamic_card_response_required"]),
            "receipt_required_when_declared": bool(route["receipt_required"]),
            "proof_required": True,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "business_action_performed": False,
            "authority_grant_performed": False,
            "external_llm_invoked": False,
            "external_provider_connected": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
            "git_push_performed": False,
            "merge_performed": False,
        },
    }
    record["machine_proof"]["unsafe_true_grants"] = unsafe_true_grants(record)
    record["machine_proof"]["unsafe_true_grants_absent"] = not record["machine_proof"]["unsafe_true_grants"]
    return record


def attach_verified_controller_envelope(
    event_payload: Mapping[str, Any],
    *,
    event_type: str,
    operator_ref: str = "operator:winship",
    app_instance_ref: str = "mission_control:mac",
    device_ref: str = "device:macbook",
    device_class: str = "mac",
    session_ref: str = "session:operator-controller",
    input_surface: str = "card",
    current_world_ref: str = "mission_control",
    current_thread_ref: str = "operator_surface",
    active_entity_ref: str = "",
    authority_requested: Sequence[str] = (),
    created_at: str | None = None,
    local_dev_verified: bool = False,
) -> dict[str, Any]:
    created_at = created_at or utc_now()
    event = dict(event_payload)
    event["request_type"] = REQUEST_TYPE
    event["event_type"] = event_type
    event["authority_requested"] = [str(item) for item in authority_requested]
    envelope_id = "operator_controller_envelope:" + _short_hash(
        operator_ref,
        app_instance_ref,
        device_ref,
        session_ref,
        input_surface,
        current_world_ref,
        current_thread_ref,
        active_entity_ref,
        event_type,
        created_at,
    )
    event["operator_controller_envelope"] = {
        "envelope_id": envelope_id,
        "operator_ref": operator_ref,
        "app_instance_ref": app_instance_ref,
        "device_ref": device_ref,
        "device_class": device_class,
        "session_ref": session_ref,
        "request_hash": "",
        "created_at": created_at,
        "input_surface": input_surface,
        "current_world_ref": current_world_ref,
        "current_thread_ref": current_thread_ref,
        "active_entity_ref": active_entity_ref,
        "operator_verified": not local_dev_verified,
        "app_instance_verified": not local_dev_verified,
        "device_verified": not local_dev_verified,
        "session_verified": not local_dev_verified,
        "local_dev_verified": bool(local_dev_verified),
        "verification_status": VERIFICATION_STATUS_VERIFIED,
    }
    event["operator_controller_envelope"]["request_hash"] = compute_request_hash(event)
    return event


def example_events(*, generated_at: str | None = None) -> list[dict[str, Any]]:
    generated_at = generated_at or utc_now()
    return [
        attach_verified_controller_envelope(
            {
                "operator_note": "Live Arts MD payment proof for invoice 2026-1001 appears to be processing.",
                "intended_use": "payment_proof",
                "privacy_class": "financial_sensitive",
            },
            event_type="attach_proof",
            input_surface="dropzone",
            current_world_ref="finance",
            current_thread_ref="live_arts_md",
            active_entity_ref="invoice:2026-1001",
            authority_requested=["record_payment_proof_intake"],
            created_at=generated_at,
        ),
        attach_verified_controller_envelope(
            {"operator_note": "Do it from Finance / Capital Hilton."},
            event_type="do_it",
            input_surface="card",
            current_world_ref="finance",
            current_thread_ref="capital_hilton",
            active_entity_ref="dynamic_card.finance.capital_hilton.payment_watch",
            authority_requested=["do_it"],
            created_at=generated_at,
        ),
        attach_verified_controller_envelope(
            {"review_packet_id": "review_packet:current", "decision_action": "approve_review_packet_for_record"},
            event_type="approve",
            input_surface="card",
            current_world_ref="build",
            current_thread_ref="review_packet",
            active_entity_ref="review_packet:current",
            authority_requested=["record_review_decision"],
            created_at=generated_at,
        ),
        attach_verified_controller_envelope(
            {"operator_note": "Stage the Capital Hilton follow-up draft."},
            event_type="stage_plan",
            input_surface="card",
            current_world_ref="business_development",
            current_thread_ref="capital_hilton",
            active_entity_ref="capital_hilton_business_development_followup",
            authority_requested=["stage_followup_draft"],
            created_at=generated_at,
        ),
        attach_verified_controller_envelope(
            {"approval_request_ref": "guardian_approval_request:send_email", "operator_decision": "approve"},
            event_type="approve",
            input_surface="card",
            current_world_ref="governance",
            current_thread_ref="guardian",
            active_entity_ref="guardian_approval_request:send_email",
            authority_requested=["email_send"],
            created_at=generated_at,
        ),
    ]


def _init_schema(conn: sqlite3.Connection, *, replace: bool = False) -> None:
    if replace:
        conn.execute("DROP TABLE IF EXISTS operator_controller_events")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS operator_controller_events (
          event_id TEXT PRIMARY KEY,
          event_type TEXT NOT NULL,
          envelope_id TEXT NOT NULL,
          operator_ref TEXT NOT NULL,
          app_instance_ref TEXT NOT NULL,
          device_ref TEXT NOT NULL,
          device_class TEXT NOT NULL,
          session_ref TEXT NOT NULL,
          input_surface TEXT NOT NULL,
          current_world_ref TEXT NOT NULL,
          current_thread_ref TEXT NOT NULL,
          active_entity_ref TEXT NOT NULL,
          event_status TEXT NOT NULL,
          verification_status TEXT NOT NULL,
          route_ref TEXT NOT NULL,
          contract_ref TEXT NOT NULL,
          authority_requested_json TEXT NOT NULL,
          authority_granted_json TEXT NOT NULL,
          receipt_required INTEGER NOT NULL,
          dynamic_card_response_required INTEGER NOT NULL,
          proof_required INTEGER NOT NULL,
          ledger_mutation_allowed INTEGER NOT NULL,
          paid_marking_allowed INTEGER NOT NULL,
          business_action_allowed INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          recorded_at TEXT NOT NULL
        )
        """
    )


def _insert_row(conn: sqlite3.Connection, record: Mapping[str, Any]) -> None:
    envelope = record["envelope"]
    route = record["route"]
    conn.execute(
        """
        INSERT OR REPLACE INTO operator_controller_events (
          event_id, event_type, envelope_id, operator_ref, app_instance_ref,
          device_ref, device_class, session_ref, input_surface,
          current_world_ref, current_thread_ref, active_entity_ref,
          event_status, verification_status, route_ref, contract_ref,
          authority_requested_json, authority_granted_json, receipt_required,
          dynamic_card_response_required, proof_required, ledger_mutation_allowed,
          paid_marking_allowed, business_action_allowed, created_at, recorded_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record["event_id"],
            record["event_type"],
            envelope["envelope_id"],
            envelope["operator_ref"],
            envelope["app_instance_ref"],
            envelope["device_ref"],
            envelope["device_class"],
            envelope["session_ref"],
            envelope["input_surface"],
            envelope["current_world_ref"],
            envelope["current_thread_ref"],
            envelope["active_entity_ref"],
            record["event_status"],
            record["verification_status"],
            route["route_ref"],
            route["contract_ref"],
            stable_json(record["authority_requested"]),
            stable_json(record["authority_granted"]),
            1 if record["receipt_required"] else 0,
            1 if record["dynamic_card_response_required"] else 0,
            1 if record["proof_required"] else 0,
            1 if AUTHORITY_BOUNDARY["ledger_mutation_allowed"] else 0,
            1 if AUTHORITY_BOUNDARY["paid_marking_allowed"] else 0,
            1 if AUTHORITY_BOUNDARY["business_action_allowed"] else 0,
            envelope["created_at"],
            record["generated_at"],
        ),
    )


def record_controller_events(
    events: Sequence[Mapping[str, Any]],
    *,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
    replace: bool = False,
) -> list[dict[str, Any]]:
    generated_at = generated_at or utc_now()
    records = [build_controller_event_record(event, generated_at=generated_at) for event in events]
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    try:
        _init_schema(conn, replace=replace)
        for record in records:
            if record["event_status"] == EVENT_ACCEPTED_STATUS:
                _insert_row(conn, record)
        conn.commit()
    finally:
        conn.close()
    return records


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
    replace_sqlite: bool = True,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _precondition_rows(read_model_root)
    examples = record_controller_events(
        example_events(generated_at=generated_at),
        sqlite_path=sqlite_path,
        generated_at=generated_at,
        replace=replace_sqlite,
    )
    status = READY_STATUS if all(row["ready"] for row in preconditions) and all(example["event_status"] == EVENT_ACCEPTED_STATUS for example in examples) else NOT_READY_STATUS
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": status,
        "generated_at": generated_at,
        "purpose": "Verified controller event protocol for Mission Control, iPad, and iPhone surfaces without business authority grants.",
        "request_type": REQUEST_TYPE,
        "controller_envelope": {
            "envelope_keys": list(ENVELOPE_KEYS),
            "required_fields": list(REQUIRED_ENVELOPE_FIELDS),
            "device_classes": list(DEVICE_CLASSES),
            "input_surfaces": list(INPUT_SURFACES),
            "verification_statuses": [
                VERIFICATION_STATUS_VERIFIED,
                VERIFICATION_STATUS_NEEDS_VERIFICATION,
                VERIFICATION_STATUS_REJECTED,
            ],
            "backend_only_fields": list(BACKEND_ONLY_FIELDS),
        },
        "authority_rules": [
            "Incoming authority_requested is a request only.",
            "Incoming authority_granted is not trusted and is rejected or ignored.",
            "authority_granted is backend-only.",
            "LMs cannot generate or modify verification.",
            "LMs cannot grant authority.",
            "Missing device/app/session proof fails closed except explicit local_dev_verified mode.",
            "Business actions require separate package, gate, Guardian, receipt, and operator review.",
        ],
        "event_type_contracts": [
            {"event_type": event_type, **dict(contract)}
            for event_type, contract in EVENT_TYPE_CONTRACTS.items()
        ],
        "examples": examples,
        "sqlite_path": str(_rooted(sqlite_path)),
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "preconditions_ready": all(row["ready"] for row in preconditions),
            "example_events_accepted": all(example["event_status"] == EVENT_ACCEPTED_STATUS for example in examples),
            "authority_requested_does_not_imply_authority_granted": all(example["authority_granted"] == [] for example in examples),
            "incoming_authority_granted_trusted": False,
            "lm_can_grant_authority": False,
            "dynamic_card_response_requirements_declared": True,
            "receipt_requirements_declared": True,
            "proof_requirements_declared": True,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "business_action_performed": False,
            "authority_grant_performed": False,
            "external_llm_invoked": False,
            "external_provider_connected": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
            "git_push_performed": False,
            "merge_performed": False,
        },
    }
    payload["machine_proof"]["unsafe_true_grants"] = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants_absent"] = not payload["machine_proof"]["unsafe_true_grants"]
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Operator Controller Protocol",
        "",
        f"Status: `{read_model.get('status', NOT_READY_STATUS)}`",
        "",
        "This protocol lets Mission Control, iPad, and iPhone send verified controller events into OpenClaw.",
        "It verifies operator/app/device/session identity and request integrity, then maps the event to a deterministic backend contract.",
        "",
        "## Authority",
        "",
        "- `authority_requested` is allowed on incoming events.",
        "- `authority_granted` is backend-only and is not trusted from incoming events.",
        "- LMs may summarize and choose candidate routes from the protocol, but cannot create verification or grant authority.",
        "",
        "## Event Types",
        "",
    ]
    for event_type, contract in EVENT_TYPE_CONTRACTS.items():
        lines.append(
            f"- `{event_type}` -> `{contract['expected_backend_route']}`; receipt required: `{str(contract['receipt_required']).lower()}`; dynamic card required: `{str(contract['dynamic_card_response_required']).lower()}`"
        )
    lines.extend(
        [
            "",
            "## Examples",
            "",
        ]
    )
    for example in read_model.get("examples", []):
        if not isinstance(example, Mapping):
            continue
        route = example.get("route") if isinstance(example.get("route"), Mapping) else {}
        lines.append(
            f"- `{example.get('event_type')}` / `{route.get('route_label')}` -> `{route.get('contract_ref')}`; authority granted: `{example.get('authority_granted')}`"
        )
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "Email, Gmail, browser, Coupa, ledger, workbook, PDF, paid, submit, push, worker, provider, and business-action authority remain false in this protocol.",
            "",
        ]
    )
    return "\n".join(lines)


def export_operator_controller_protocol(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(
        read_model_root=read_model_root,
        sqlite_path=sqlite_path,
        generated_at=generated_at,
        replace_sqlite=True,
    )
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    export_path = export_root / JSON_EXPORT_NAME
    export_path.write_text(stable_json(read_model), encoding="utf-8")
    bridge_path = ""
    if bridge_root is not None:
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge = bridge_root / JSON_EXPORT_NAME
        shutil.copy2(export_path, bridge)
        bridge_path = bridge.as_posix()
    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model["status"]),
        "read_model_path": export_path.as_posix(),
        "bridge_read_model_path": bridge_path,
        "sqlite_path": str(_rooted(sqlite_path)),
        "wiki_path": wiki_path.as_posix(),
    }


def _walk_values(payload: Any):
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield str(key), value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def unsafe_true_grants(payload: Mapping[str, Any]) -> list[str]:
    return sorted({key for key, value in _walk_values(payload) if key in UNSAFE_TRUE_KEYS and value is True})


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Operator Controller Protocol V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_operator_controller_protocol(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=None if args.no_bridge else Path(args.bridge_root),
        wiki_path=Path(args.wiki_path),
        sqlite_path=Path(args.sqlite_path),
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result), end="")
    else:
        print(f"{result['status']}: {result['read_model_path']}")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
