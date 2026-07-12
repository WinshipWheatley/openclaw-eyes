"""Operator Controller Event Router V0.

Maps verified Mission Control controller events to existing safe OpenClaw
routes. The router records receipts and card responses only; it never sends,
submits, opens external providers, mutates ledgers/workbooks, marks paid, pushes
git state, invokes LMs, or connects local model runtimes.
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

import evidence_intake
import first_class_operator_envelope as operator_authority
import global_run_mode_context
import maestro_cassandra_responder
import objective_advancement_protocol
import operator_conversation_router
import proof_to_response_runtime
import workroom_review_decision_consumer


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Operator Controller Event Router.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/operator_controller_event_router.sqlite")

REQUEST_TYPE = "OPERATOR_CONTROLLER_EVENT_REQUEST_V0"
REQUEST_FILENAME_PATTERNS = (
    "mission_control_controller_event_request_*.json",
    "mission_control_operator_controller_event_request_*.json",
    "mission_control_capture_request_*controller_event*.json",
)
SCHEMA_VERSION = "operator_controller_event_router_v0"
CONTRACT_SCHEMA_VERSION = "operator_controller_event_router_contract_v0"
CONTRACT_READ_MODEL_ID = "operator_controller_event_router_contract"
STATUS_READ_MODEL_ID = "operator_controller_event_router_status"
CONTRACT_JSON_EXPORT_NAME = f"{CONTRACT_READ_MODEL_ID}.json"
STATUS_JSON_EXPORT_NAME = f"{STATUS_READ_MODEL_ID}.json"
LM2_STRUCTURED_RETRY_READ_MODEL = "lm2_room_backed_worker_structured_output_retry.json"
LM2_STRUCTURED_RETRY_REF = f"generated/read_models/{LM2_STRUCTURED_RETRY_READ_MODEL}"
LM2_STRUCTURED_RETRY_BACKEND = "ollama:qwen3:8b-q4_K_M"

READY_STATUS = "OPERATOR_CONTROLLER_EVENT_ROUTER_READY"
NOT_READY_STATUS = "OPERATOR_CONTROLLER_EVENT_ROUTER_NOT_READY"

RESPONSE_READY = "RESPONSE_READY"
BLOCKED_WITH_REASON = "BLOCKED_WITH_REASON"

EVENT_TYPES = (
    "chat_goal",
    "do_it",
    "advance_objective",
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
    "set_run_mode",
)

_FRONTDOOR_AGENT_FIELDS = (
    "agent",
    "agent_id",
    "target_agent",
    "target_agent_id",
    "selected_agent",
    "selected_agent_id",
    "active_agent",
    "active_agent_id",
    "response_agent",
    "response_agent_id",
)
_FRONTDOOR_AGENT_ALIASES = {
    "maestro": "maestro",
    "cassandra": "cassandra",
    "clara": "clara",
    "clara_reid": "clara",
    "clara reid": "clara",
    "chief": "chief",
    "guardian": "guardian",
    "niles": "niles",
    "hermes": "hermes",
}


def _normalize_frontdoor_agent(value: object) -> str:
    key = str(value or "").strip().lower()
    if not key:
        return ""
    key = key.replace("-", "_")
    return _FRONTDOOR_AGENT_ALIASES.get(key, "")


def _frontdoor_agent_from_mapping(payload: Mapping[str, Any] | None) -> str:
    if not isinstance(payload, Mapping):
        return ""
    for field in _FRONTDOOR_AGENT_FIELDS:
        agent = _normalize_frontdoor_agent(payload.get(field))
        if agent:
            return agent
    for field in ("context", "current_context", "event", "payload", "session"):
        nested = payload.get(field)
        if isinstance(nested, Mapping):
            agent = _frontdoor_agent_from_mapping(nested)
            if agent:
                return agent
    return ""


def _resolved_frontdoor_agent(request: Mapping[str, Any], *, session: Mapping[str, Any] | None = None) -> str:
    return _frontdoor_agent_from_mapping(request) or _frontdoor_agent_from_mapping(session) or "maestro"

WORKROOM_DECISION_BY_EVENT = {
    "approve": "approve_review_packet_for_record",
    "deny": "request_review_packet_rework",
    "request_rework": "request_review_packet_rework",
    "mark_informational": "mark_review_packet_informational",
}

ACTION_TYPES_WITH_PAYLOAD_REQUIRED = {
    "do_it",
    "approve",
    "deny",
    "request_rework",
    "mark_informational",
}

PRECONDITIONS = {
    "operator_controller_protocol": {
        "filename": "operator_controller_protocol.json",
        "accepted_statuses": ("OPERATOR_CONTROLLER_PROTOCOL_READY",),
    },
    "first_class_operator_envelope": {
        "filename": "first_class_operator_envelope_status.json",
        "accepted_statuses": ("FIRST_CLASS_OPERATOR_ENVELOPE_READY",),
    },
    "dynamic_card_packet": {
        "filename": "dynamic_card_packet_latest.json",
        "accepted_statuses": ("DYNAMIC_CARD_PACKET_READY",),
    },
    "dynamic_card_lifecycle_policy": {
        "filename": "dynamic_card_lifecycle_policy.json",
        "accepted_statuses": ("DYNAMIC_CARD_LIFECYCLE_POLICY_READY",),
    },
    "verified_evidence_intake": {
        "filename": "evidence_intake_status.json",
        "accepted_statuses": ("EVIDENCE_INTAKE_READY", "EVIDENCE_INTAKE_LIVE_ROUTE_READY"),
    },
    "operator_action_payloads": {
        "filename": "operator_action_payloads.json",
        "accepted_statuses": ("OPERATOR_ACTION_PAYLOADS_READY",),
    },
    "objective_advancement_protocol": {
        "filename": "objective_advancement_protocol.json",
        "accepted_statuses": ("OBJECTIVE_ADVANCEMENT_PROTOCOL_READY",),
    },
    "contextual_system_questions": {
        "filename": "system_question_answer_contract.json",
        "accepted_statuses": ("CONTEXTUAL_SYSTEM_QUESTIONS_READY", "SYSTEM_QUESTION_ANSWER_V0_READY"),
        "status_keys": ("contextual_status", "status", "readiness_status", "contract_status"),
    },
    "workroom_review_decision_consumer": {
        "filename": "workroom_review_decision_status.json",
        "accepted_statuses": ("WORKROOM_REVIEW_DECISION_CONSUMER_READY",),
    },
}

AUTHORITY_BOUNDARY = {
    **operator_authority.AUTHORITY_BOUNDARY,
    "merge_allowed": False,
    "push_allowed": False,
    "agent_loop_allowed": False,
    "child_agent_run_allowed": False,
    "worker_execution_allowed": False,
    "workbook_open_allowed": False,
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "excel_automation_allowed": False,
    "repair_authority_allowed": False,
}

UNSAFE_TRUE_KEYS = set(operator_authority.UNSAFE_TRUE_KEYS) | set(evidence_intake.UNSAFE_TRUE_KEYS) | {
    "merge_allowed",
    "push_allowed",
    "agent_loop_allowed",
    "child_agent_run_allowed",
    "worker_execution_allowed",
    "workbook_open_allowed",
    "workbook_body_read_allowed",
    "spreadsheet_cell_read_allowed",
    "excel_automation_allowed",
    "repair_authority_allowed",
    "merge_performed",
    "business_state_mutation_performed",
    "child_agent_run_performed",
    "worker_execution_performed",
    "live_external_provider_action_performed",
    "package_staged_without_operator_review",
    "approval_granted",
}

OBJECTIVE_ADVANCEMENT_EVENT_TYPES = {"advance_objective", "continue", "stage_plan"}
OBJECTIVE_ADVANCEMENT_DO_IT_ACTION_IDS = {
    "capital_hilton.payment.advance_objective",
    "capital_hilton.payment.open_finance",
    "capital_hilton.proposal.stage_followup",
}
OBJECTIVE_ADVANCEMENT_DO_IT_ACTION_PREFIXES = (
    "review_packet.",
)

PROTECTED_TERMS = (
    "email",
    "gmail",
    "browser",
    "coupa",
    "submit",
    "ledger",
    "workbook",
    "excel",
    "pdf",
    "mark_paid",
    "paid",
    "merge",
    "push",
    "worker",
    "external_provider",
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _short_hash(*parts: object, length: int = 16) -> str:
    joined = "\0".join(str(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:length]


def _load_json(path: Path) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _status(payload: Mapping[str, Any], keys: Sequence[str] = ("status", "readiness_status", "contract_status")) -> str:
    for key in keys:
        value = payload.get(key)
        if value:
            return str(value)
    return ""


def _precondition_rows(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    root = _rooted(read_model_root)
    for ref, spec in PRECONDITIONS.items():
        filename = str(spec["filename"])
        payload = _load_json(root / filename)
        accepted = tuple(str(item) for item in spec["accepted_statuses"])
        keys = tuple(str(item) for item in spec.get("status_keys", ("status", "readiness_status", "contract_status")))
        observed = _status(payload, keys)
        rows.append(
            {
                "precondition_ref": ref,
                "observed_status": observed,
                "accepted_statuses": list(accepted),
                "ready": observed in accepted,
                "source_ref": f"generated/read_models/{filename}",
            }
        )
    return rows


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _walk(payload: Any):
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield str(key), value
            yield from _walk(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk(value)


def unsafe_true_grants(payload: Mapping[str, Any]) -> list[str]:
    return sorted({key for key, value in _walk(payload) if key in UNSAFE_TRUE_KEYS and value is True})


def _incoming_authority_granted_fields(payload: Mapping[str, Any]) -> list[str]:
    fields: list[str] = []

    def scan(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                if key in {"authority_granted", "gate_decision_ref", "approval_receipt_ref"}:
                    fields.append(child_path)
                scan(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                scan(child, f"{path}[{index}]")

    scan(payload, "")
    return sorted(dict.fromkeys(fields))


def _boundary_all_false(boundary: Any) -> bool:
    if not isinstance(boundary, Mapping):
        return False
    for key in AUTHORITY_BOUNDARY:
        if key not in boundary or boundary.get(key) is not False:
            return False
    return True


def _canonical_action_id(value: str) -> str:
    action_id = str(value or "").strip()
    if "#action_payloads." in action_id:
        action_id = action_id.split("#action_payloads.", 1)[1]
    if action_id.startswith("action_payloads."):
        action_id = action_id[len("action_payloads.") :]
    return action_id


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _first_present(*values: Any) -> Any:
    for value in values:
        if isinstance(value, str):
            if value.strip():
                return value
        elif value not in (None, ""):
            return value
    return ""


def _request_context(request: Mapping[str, Any]) -> dict[str, Any]:
    current_context = _mapping(request.get("current_context"))
    if current_context:
        return current_context
    return _mapping(request.get("context"))


def _request_event(request: Mapping[str, Any]) -> dict[str, Any]:
    return _mapping(request.get("event"))


def _normalize_source_surface(value: Any) -> str:
    surface = str(value or "").strip()
    if surface in operator_authority.SOURCE_SURFACES:
        return surface
    surface_lower = surface.lower()
    if "drop" in surface_lower:
        return "dropzone"
    if "proof" in surface_lower:
        return "proof_drawer"
    if "card" in surface_lower:
        return "card"
    if "chat" in surface_lower:
        return "chat"
    if "pad" in surface_lower:
        return "pad"
    return ""


def _existing_envelope(request: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    for key in operator_authority.ENVELOPE_KEYS:
        envelope = request.get(key)
        if isinstance(envelope, Mapping):
            return key, dict(envelope)
    if str(request.get("operator_envelope_ref") or request.get("operator_authority_envelope_ref") or "").strip():
        return "operator_authority_envelope", {}
    top_level_identity_fields = {
        "operator_ref",
        "app_instance_ref",
        "device_ref",
        "device_class",
        "session_ref",
        "operator_verified",
        "app_instance_verified",
        "device_verified",
        "session_verified",
        "verification_status",
    }
    if any(field in request for field in top_level_identity_fields):
        return "operator_authority_envelope", {}
    return "", {}


def _normalize_authority_requested(request: Mapping[str, Any], envelope: Mapping[str, Any], event: Mapping[str, Any]) -> list[str]:
    if isinstance(envelope.get("authority_requested"), list):
        return [str(item).strip() for item in envelope.get("authority_requested", []) if str(item).strip()]
    if isinstance(request.get("authority_requested"), list):
        return [str(item).strip() for item in request.get("authority_requested", []) if str(item).strip()]
    if isinstance(event.get("authority_requested"), list):
        return [str(item).strip() for item in event.get("authority_requested", []) if str(item).strip()]
    return []


def _review_packet_id_from_request(request: Mapping[str, Any], action: Mapping[str, Any] | None = None) -> str:
    candidates: list[Any] = [
        request.get("review_packet_id"),
        request.get("active_entity_ref"),
        request.get("selected_card_id"),
        request.get("selected_action_id"),
    ]
    if isinstance(action, Mapping):
        payload = action.get("payload") if isinstance(action.get("payload"), Mapping) else {}
        candidates.extend([payload.get("review_packet_id"), action.get("action_id")])
    for candidate in candidates:
        text = str(candidate or "").strip()
        if not text:
            continue
        if text.startswith("review_packet:"):
            return text
        if "review_packet_" in text:
            token = text.split("review_packet_", 1)[1].split(".", 1)[0].split("/", 1)[0]
            if token:
                return f"review_packet:{token}"
        if "review_packet:" in text:
            return "review_packet:" + text.split("review_packet:", 1)[1].split(".", 1)[0].split("/", 1)[0]
    return ""


def _packet_by_review_packet_id(read_model_root: Path, review_packet_id: str) -> dict[str, Any] | None:
    if not review_packet_id:
        return None
    index = _load_json(_rooted(read_model_root) / "workroom_review_packet_index.json")
    packets = index.get("packets")
    if not isinstance(packets, list):
        return None
    for packet in packets:
        if isinstance(packet, Mapping) and str(packet.get("review_packet_id") or "") == review_packet_id:
            return dict(packet)
    return None


def _apply_context_from_read_models(request: dict[str, Any], *, read_model_root: Path) -> None:
    if request.get("current_world_ref") and request.get("current_thread_ref"):
        return

    context_sources: list[tuple[str, Mapping[str, Any]]] = []
    selected_action = _action_payload_by_id(read_model_root, str(request.get("selected_action_id") or ""))
    if selected_action:
        context_sources.append(("selected_action_payload", selected_action))
        selected_payload = selected_action.get("payload") if isinstance(selected_action.get("payload"), Mapping) else {}
        if selected_payload:
            context_sources.append(("selected_action_payload.payload", selected_payload))

    review_packet_id = _review_packet_id_from_request(request, selected_action)
    packet = _packet_by_review_packet_id(read_model_root, review_packet_id)
    if packet:
        context_sources.append(("workroom_review_packet_index", packet))
        request.setdefault("review_packet_id", review_packet_id)

    selected_card = _card_by_id(read_model_root, str(request.get("selected_card_id") or ""))
    if selected_card:
        context_sources.append(("selected_dynamic_card", selected_card))

    inferred: list[str] = []
    for source_name, source in context_sources:
        if not request.get("current_world_ref"):
            world = _first_present(
                source.get("target_world_ref"),
                source.get("world_ref"),
                "build" if source.get("channel_ref") else "",
            )
            if world:
                request["current_world_ref"] = world
                inferred.append(f"current_world_ref:{source_name}")
        if not request.get("current_thread_ref"):
            thread = _first_present(
                source.get("target_thread_ref"),
                source.get("thread_ref"),
                source.get("lane_ref"),
                source.get("channel_ref"),
                source.get("target_lane_ref"),
            )
            if thread:
                request["current_thread_ref"] = thread
                inferred.append(f"current_thread_ref:{source_name}")
        if request.get("current_world_ref") and request.get("current_thread_ref"):
            break

    if inferred:
        request["_controller_event_context_normalization"] = {
            "applied": True,
            "inferred_fields": sorted(dict.fromkeys(inferred)),
            "review_packet_id": review_packet_id,
            "selected_action_id": _canonical_action_id(str(request.get("selected_action_id") or "")),
            "selected_card_id": str(request.get("selected_card_id") or ""),
        }


def _normalize_controller_envelope(request: dict[str, Any]) -> None:
    context = _request_context(request)
    event = _request_event(request)
    envelope_key, envelope = _existing_envelope(request)
    if not envelope_key:
        return

    request_hash = _first_present(envelope.get("request_hash"), request.get("request_hash"), request.get("payload_hash"))
    operator_envelope_ref = str(request.get("operator_envelope_ref") or request.get("operator_authority_envelope_ref") or "").strip()
    lifted_fields: list[str] = []

    def fill(field: str, *values: Any) -> None:
        if field in envelope and envelope.get(field) not in (None, ""):
            return
        value = _first_present(*values)
        if value not in (None, ""):
            envelope[field] = value
            lifted_fields.append(field)

    fill("envelope_id", operator_envelope_ref, f"operator_authority_envelope:{_short_hash(request_hash)}" if request_hash else "")
    fill("operator_ref", request.get("operator_ref"))
    fill("app_instance_ref", request.get("app_instance_ref"))
    fill("device_ref", request.get("device_ref"))
    fill("device_class", request.get("device_class"))
    fill("session_ref", request.get("session_ref"))
    fill("request_hash", request_hash)
    fill("created_at", request.get("created_at"))
    normalized_source_surface = _first_present(
        _normalize_source_surface(envelope.get("source_surface")),
        _normalize_source_surface(request.get("input_surface")),
        _normalize_source_surface(request.get("active_surface_ref")),
        _normalize_source_surface(context.get("active_surface_ref")),
        _normalize_source_surface(request.get("source_surface")),
        _normalize_source_surface(context.get("source_surface")),
    )
    if normalized_source_surface and envelope.get("source_surface") != normalized_source_surface:
        envelope["source_surface"] = normalized_source_surface
        lifted_fields.append("source_surface")
    fill("current_world_ref", request.get("current_world_ref"), context.get("current_world_ref"))
    fill("current_thread_ref", request.get("current_thread_ref"), context.get("current_thread_ref"))
    fill(
        "active_entity_ref",
        request.get("active_entity_ref"),
        request.get("selected_entity_ref"),
        context.get("selected_entity_ref"),
        request.get("selected_card_id"),
    )

    if "authority_requested" not in envelope:
        envelope["authority_requested"] = _normalize_authority_requested(request, envelope, event)
        lifted_fields.append("authority_requested")

    for field in ("operator_verified", "app_instance_verified", "device_verified", "session_verified"):
        if field not in envelope and field in request:
            envelope[field] = request.get(field)
            lifted_fields.append(field)

    fill("verification_status", request.get("verification_status"))

    if "proof_refs" not in envelope:
        proof_refs = []
        if operator_envelope_ref:
            proof_refs.append(operator_envelope_ref)
        for field in ("app_instance_ref", "device_ref", "session_ref", "request_hash"):
            value = str(envelope.get(field) or "").strip()
            if value:
                proof_refs.append(value)
        envelope["proof_refs"] = list(dict.fromkeys(proof_refs))
        lifted_fields.append("proof_refs")

    request[envelope_key] = envelope
    if lifted_fields:
        request["_controller_event_envelope_normalization"] = {
            "applied": True,
            "source": "mac_compact_controller_event_envelope",
            "lifted_fields": sorted(dict.fromkeys(lifted_fields)),
            "request_hash_enforcement": "deferred_for_compact_mac_dispatcher_hash",
            "operator_envelope_ref": operator_envelope_ref,
        }


def normalize_controller_event_request(
    raw_request: Mapping[str, Any],
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
) -> dict[str, Any]:
    request = dict(raw_request)
    if str(request.get("request_type") or request.get("kind") or request.get("type") or "").strip().upper() == global_run_mode_context.RUN_MODE_SET_REQUEST_SCHEMA:
        request["_original_request_type"] = global_run_mode_context.RUN_MODE_SET_REQUEST_SCHEMA
        request["request_type"] = REQUEST_TYPE
        request.setdefault("controller_event_type", global_run_mode_context.RUN_MODE_SET_EVENT_TYPE)
        request.setdefault("controller_action_type", global_run_mode_context.RUN_MODE_SET_EVENT_TYPE)
    context = _request_context(request)
    event = _request_event(request)
    if not request.get("request_type"):
        request["request_type"] = str(request.get("kind") or request.get("type") or "").strip()
    if not request.get("current_world_ref") and context.get("current_world_ref"):
        request["current_world_ref"] = context.get("current_world_ref")
    if not request.get("current_thread_ref") and context.get("current_thread_ref"):
        request["current_thread_ref"] = context.get("current_thread_ref")
    for key in ("controller_event_type", "selected_card_id", "selected_action_id", "artifact_ref", "authority_boundary"):
        if not request.get(key) and event.get(key) not in (None, ""):
            request[key] = event.get(key)
    if "authority_requested" not in request and "authority_requested" in event:
        request["authority_requested"] = event.get("authority_requested")
    event_type = str(request.get("controller_event_type") or request.get("controller_action_type") or "").strip()
    if event_type and not request.get("controller_action_type"):
        request["controller_action_type"] = event_type
    _apply_context_from_read_models(request, read_model_root=read_model_root)
    _normalize_controller_envelope(request)
    if request.get("_original_request_type") == global_run_mode_context.RUN_MODE_SET_REQUEST_SCHEMA:
        normalization = _mapping(request.get("_controller_event_envelope_normalization"))
        normalization.update(
            {
                "applied": True,
                "source": "run_mode_set_request_envelope_normalization",
                "request_hash_enforcement": "deferred_for_run_mode_set_request_normalization",
            }
        )
        request["_controller_event_envelope_normalization"] = normalization
    return request


def _validate_controller_event(request: Mapping[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    rejected_reasons: list[str] = []
    event_type = str(request.get("controller_event_type") or "").strip()
    requested_scope = str(request.get("requested_scope") or "").strip().lower()
    lane_context_required = event_type != global_run_mode_context.RUN_MODE_SET_EVENT_TYPE or requested_scope not in {
        "session",
        "global",
    }
    normalization = _mapping(request.get("_controller_event_envelope_normalization"))
    enforce_request_hash = normalization.get("request_hash_enforcement") not in {
        "deferred_for_compact_mac_dispatcher_hash",
        "deferred_for_run_mode_set_request_normalization",
    }
    envelope_result = operator_authority.validate_operator_authority_envelope(
        request,
        enforce_request_hash=enforce_request_hash,
    )

    if str(request.get("request_type") or "") != REQUEST_TYPE:
        blockers.append("request_type_invalid")
    if lane_context_required and not str(request.get("current_world_ref") or "").strip():
        blockers.append("current_world_ref_missing")
    if lane_context_required and not str(request.get("current_thread_ref") or "").strip():
        blockers.append("current_thread_ref_missing")
    if not _boundary_all_false(request.get("authority_boundary")):
        blockers.append("authority_boundary_not_all_false")

    incoming_grant_fields = _incoming_authority_granted_fields(request)
    if incoming_grant_fields:
        rejected_reasons.append("incoming_authority_granted_or_backend_gate_fields_not_accepted")

    true_grants = unsafe_true_grants(request)
    if true_grants:
        rejected_reasons.append("unsafe_true_grants_present")

    if envelope_result.get("verification_status") != operator_authority.VERIFICATION_STATUS_VERIFIED:
        blockers.append("verified_operator_envelope_required")

    status = "verified"
    if rejected_reasons:
        status = "rejected"
    elif blockers:
        status = "needs_verification"

    return {
        "status": status,
        "verified": status == "verified",
        "blockers": blockers,
        "rejected_reasons": rejected_reasons,
        "unsafe_true_grants": true_grants,
        "incoming_authority_granted_fields": incoming_grant_fields,
        "operator_authority_envelope": envelope_result,
        "operator_envelope_normalization": normalization,
        "context_normalization": _mapping(request.get("_controller_event_context_normalization")),
    }


def _action_payloads(read_model_root: Path) -> list[dict[str, Any]]:
    payload = _load_json(_rooted(read_model_root) / "operator_action_payloads.json")
    actions = payload.get("action_payloads")
    if not isinstance(actions, list):
        return []
    return [dict(item) for item in actions if isinstance(item, Mapping)]


def _action_payload_by_id(read_model_root: Path, action_id: str) -> dict[str, Any] | None:
    wanted = _canonical_action_id(action_id)
    if not wanted:
        return None
    for action in _action_payloads(read_model_root):
        if str(action.get("action_id") or "") == wanted:
            return action
    return None


def _find_review_action_payload(read_model_root: Path, event_type: str, request: Mapping[str, Any]) -> dict[str, Any] | None:
    selected = _action_payload_by_id(read_model_root, str(request.get("selected_action_id") or ""))
    if selected:
        return selected
    wanted_decision = WORKROOM_DECISION_BY_EVENT.get(event_type, "")
    if not wanted_decision:
        return None
    world = str(request.get("current_world_ref") or "")
    thread = str(request.get("current_thread_ref") or "")
    for action in _action_payloads(read_model_root):
        payload = action.get("payload") if isinstance(action.get("payload"), Mapping) else {}
        if str(action.get("action_type") or "") != "review_decision":
            continue
        if str(payload.get("decision_action") or "") != wanted_decision:
            continue
        if world and str(action.get("target_world_ref") or "") != world:
            continue
        if thread and str(action.get("target_thread_ref") or "") != thread:
            continue
        return action
    return None


def _default_do_it_action_id(request: Mapping[str, Any]) -> str:
    joined = " ".join(
        str(request.get(key) or "")
        for key in ("selected_action_id", "selected_card_id", "active_entity_ref", "operator_text")
    ).lower()
    world = str(request.get("current_world_ref") or "").strip().lower()
    thread = str(request.get("current_thread_ref") or "").strip().lower()
    if "coupa" in joined and "submit" in joined:
        return "guardian_gate.coupa_submit.stage_approval_request"
    if world == "finance" and thread == "capital_hilton":
        return "capital_hilton.payment.open_finance"
    if world == "business_development" and thread == "capital_hilton":
        return "capital_hilton.proposal.stage_followup"
    return ""


def _resolve_action_payload(read_model_root: Path, event_type: str, request: Mapping[str, Any]) -> dict[str, Any] | None:
    selected = _action_payload_by_id(read_model_root, str(request.get("selected_action_id") or ""))
    if selected:
        return selected
    if event_type == "do_it":
        return _action_payload_by_id(read_model_root, _default_do_it_action_id(request))
    if event_type in WORKROOM_DECISION_BY_EVENT:
        return _find_review_action_payload(read_model_root, event_type, request)
    return None


def _contextual_answer(read_model_root: Path, request: Mapping[str, Any]) -> dict[str, Any]:
    contract = _load_json(_rooted(read_model_root) / "system_question_answer_contract.json")
    answers = contract.get("contextual_lane_answers") if isinstance(contract.get("contextual_lane_answers"), Mapping) else {}
    world = str(request.get("current_world_ref") or "").strip()
    thread = str(request.get("current_thread_ref") or "").strip()
    key = f"{world}/{thread}"
    answer = answers.get(key)
    if not isinstance(answer, Mapping):
        answer = answers.get(f"{world}/*")
    if not isinstance(answer, Mapping):
        answer = {
            "headline": "Needs context",
            "plain_summary": "I need a known world and thread before I can answer this controller question.",
            "next_safe_action": "Select a lane or card and ask again.",
        }
    return {
        "workflow_ref": "system_question_answer",
        "question": str(request.get("operator_text") or "Why is this here?"),
        "speaker_ref": "chief",
        "voice_mode": "diagnostic",
        "headline": str(answer.get("headline") or "Context answer"),
        "plain_summary": str(answer.get("plain_summary") or ""),
        "confirmed": [str(answer.get("plain_summary") or "")] if answer.get("plain_summary") else [],
        "inferred": [],
        "unknown": [],
        "next_safe_action": str(answer.get("next_safe_action") or ""),
        "proof_refs": [
            "generated/read_models/system_question_answer_contract.json",
            "generated/read_models/dynamic_card_packet_latest.json",
        ],
        "package_staged": False,
    }


def _cards(read_model_root: Path) -> list[dict[str, Any]]:
    packet = _load_json(_rooted(read_model_root) / "dynamic_card_packet_latest.json")
    cards = packet.get("cards")
    if not isinstance(cards, list):
        return []
    return [dict(item) for item in cards if isinstance(item, Mapping)]


def _card_by_id(read_model_root: Path, card_id: str) -> dict[str, Any] | None:
    for card in _cards(read_model_root):
        if str(card.get("card_id") or "") == card_id:
            return card
    return None


def _proof_refs_from_card(card: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(card, Mapping):
        return ["generated/read_models/dynamic_card_packet_latest.json"]
    proof = card.get("proof") if isinstance(card.get("proof"), Mapping) else {}
    refs: list[str] = ["generated/read_models/dynamic_card_packet_latest.json"]
    for key in ("proof_refs", "read_model_refs", "receipt_refs"):
        refs.extend(_as_list(proof.get(key)))
    return list(dict.fromkeys(ref for ref in refs if ref))


def _card_response(
    *,
    receipt_id: str,
    event_type: str,
    headline: str,
    summary: str,
    status_label: str,
    route_status: str,
    current_world_ref: str,
    current_thread_ref: str,
    actions: list[dict[str, Any]] | None = None,
    proof_refs: list[str] | None = None,
    tone: str = "calm",
) -> dict[str, Any]:
    return {
        "schema_version": "operator_controller_dynamic_card_response_v0",
        "card_id": f"dynamic_card.operator_controller_event.{_short_hash(receipt_id, event_type, length=12)}",
        "card_type": "controller_event_response",
        "controller_event_type": event_type,
        "headline": headline,
        "plain_summary": summary,
        "summary": summary,
        "status_label": status_label,
        "tone": tone,
        "trust_state": "trusted_current" if route_status == "ROUTED" else "needs_verification",
        "lifecycle_state": "active" if route_status == "ROUTED" else "needs_operator",
        "freshness_state": "current",
        "visible_by_default": True,
        "operator_attention_required": route_status != "ROUTED",
        "target_world_ref": current_world_ref,
        "target_thread_ref": current_thread_ref,
        "actions": actions or [],
        "proof": {
            "collapsed_by_default": True,
            "label": "Details",
            "proof_refs": proof_refs or ["generated/read_models/operator_controller_event_router_status.json"],
            "read_model_refs": [
                "generated/read_models/operator_controller_event_router_status.json",
                "generated/read_models/operator_controller_event_router_contract.json",
            ],
            "receipt_refs": [receipt_id],
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": _machine_proof(),
    }


def _machine_proof(**overrides: Any) -> dict[str, Any]:
    proof = {
        "verified_operator_envelope_required": True,
        "authority_requested_does_not_imply_authority_granted": True,
        "incoming_authority_granted_accepted": False,
        "dynamic_card_response_emitted": True,
        "no_live_external_provider_action": True,
        "no_business_execution": True,
        "email_send_performed": False,
        "gmail_access_performed": False,
        "browser_access_performed": False,
        "coupa_access_performed": False,
        "portal_submit_performed": False,
        "ledger_posting_performed": False,
        "ledger_mutation_performed": False,
        "workbook_mutation_performed": False,
        "pdf_export_performed": False,
        "paid_marking_performed": False,
        "submit_performed": False,
        "business_action_performed": False,
        "business_state_mutation_performed": False,
        "merge_performed": False,
        "git_push_performed": False,
        "worker_spawn_performed": False,
        "child_agent_run_performed": False,
        "external_llm_invoked": False,
        "external_provider_connected": False,
        "local_model_runtime_connected": False,
        "live_external_provider_action_performed": False,
    }
    proof.update(overrides)
    return proof


def _request_id(request: Mapping[str, Any]) -> str:
    return str(request.get("request_id") or request.get("source_request_id") or "operator_controller_event_request")


def _request_run_mode_context(request: Mapping[str, Any], generated_at: str) -> dict[str, Any]:
    context = request.get("run_mode_context")
    if isinstance(context, Mapping):
        return dict(context)
    return global_run_mode_context.default_run_mode_context(
        source="backend_default",
        generated_at=generated_at,
    )


def _attach_card_run_mode(card: dict[str, Any], run_mode_context: Mapping[str, Any]) -> dict[str, Any]:
    context = dict(run_mode_context)
    card["run_mode_context"] = context
    card["run_mode"] = str(context.get("run_mode") or global_run_mode_context.PRODUCTION)
    card["test_run_id"] = str(context.get("test_run_id") or "")
    card["test_marker"] = str(context.get("test_marker") or "")
    return card


def _base_receipt(
    request: Mapping[str, Any],
    *,
    receipt_id: str,
    generated_at: str,
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    event_type = str(request.get("controller_event_type") or "")
    run_mode_context = _request_run_mode_context(request, generated_at)
    return {
        "schema_version": SCHEMA_VERSION,
        "receipt_type": "OPERATOR_CONTROLLER_EVENT_ROUTER_RECEIPT",
        "receipt_id": receipt_id,
        "generated_at": generated_at,
        "request_id": _request_id(request),
        "request_type": str(request.get("request_type") or ""),
        "controller_event_type": event_type,
        "current_world_ref": str(request.get("current_world_ref") or ""),
        "current_thread_ref": str(request.get("current_thread_ref") or ""),
        "active_entity_ref": str(request.get("active_entity_ref") or ""),
        "selected_card_id": str(request.get("selected_card_id") or ""),
        "selected_action_id": _canonical_action_id(str(request.get("selected_action_id") or "")),
        "operator_text": str(request.get("operator_text") or ""),
        "run_mode_context": run_mode_context,
        "run_mode": str(run_mode_context.get("run_mode") or global_run_mode_context.PRODUCTION),
        "test_run_id": str(run_mode_context.get("test_run_id") or ""),
        "test_marker": str(run_mode_context.get("test_marker") or ""),
        "authority_requested": _as_list(request.get("authority_requested")),
        "authority_granted": [],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "operator_authority_envelope": dict(validation.get("operator_authority_envelope") or {}),
        "operator_envelope_normalization": dict(validation.get("operator_envelope_normalization") or {}),
        "context_normalization": dict(validation.get("context_normalization") or {}),
        "incoming_authority_granted_fields": list(validation.get("incoming_authority_granted_fields") or []),
        "incoming_authority_granted_accepted": False,
        "blockers": list(validation.get("blockers") or []),
        "rejected_reasons": list(validation.get("rejected_reasons") or []),
        "unsafe_true_grants": list(validation.get("unsafe_true_grants") or []),
        "route_status": "PENDING",
        "raw_internal_status": BLOCKED_WITH_REASON,
        "backend_route": "",
        "route_ref": "",
        "route_receipt_ref": "",
        "dynamic_card_response": {},
        "proof_refs": ["generated/read_models/operator_controller_event_router_status.json"],
        "machine_proof": _machine_proof(dynamic_card_response_emitted=False),
    }


def _blocked_receipt(
    request: Mapping[str, Any],
    *,
    receipt_id: str,
    generated_at: str,
    validation: Mapping[str, Any],
    route_status: str,
    headline: str,
    summary: str,
    blocker: str,
) -> dict[str, Any]:
    receipt = _base_receipt(request, receipt_id=receipt_id, generated_at=generated_at, validation=validation)
    blockers = list(receipt.get("blockers") or [])
    if blocker and blocker not in blockers:
        blockers.append(blocker)
    receipt.update(
        {
            "route_status": route_status,
            "raw_internal_status": BLOCKED_WITH_REASON,
            "blockers": blockers,
            "backend_route": "fail_closed",
            "route_ref": "operator_controller_event_router.fail_closed",
        }
    )
    card = _card_response(
        receipt_id=receipt_id,
        event_type=str(request.get("controller_event_type") or ""),
        headline=headline,
        summary=summary,
        status_label="Needs verification" if route_status == "NEEDS_VERIFICATION" else "Blocked",
        route_status=route_status,
        current_world_ref=str(request.get("current_world_ref") or ""),
        current_thread_ref=str(request.get("current_thread_ref") or ""),
        tone="blocked",
    )
    _attach_card_run_mode(card, receipt["run_mode_context"])
    receipt["dynamic_card_response"] = card
    receipt["proof_refs"] = list(card["proof"]["proof_refs"])
    receipt["machine_proof"] = _machine_proof(
        dynamic_card_response_emitted=True,
        incoming_authority_granted_accepted=False,
    )
    receipt["machine_proof"]["unsafe_true_grants"] = unsafe_true_grants(receipt)
    receipt["machine_proof"]["unsafe_true_grants_absent"] = not receipt["machine_proof"]["unsafe_true_grants"]
    return receipt


def _safe_action_summary(action: Mapping[str, Any]) -> dict[str, Any]:
    payload = action.get("payload") if isinstance(action.get("payload"), Mapping) else {}
    return {
        "action_id": str(action.get("action_id") or ""),
        "action_type": str(action.get("action_type") or ""),
        "label": str(action.get("label") or ""),
        "enabled": action.get("enabled") is True,
        "business_action": action.get("business_action") is True,
        "target_world_ref": str(action.get("target_world_ref") or ""),
        "target_thread_ref": str(action.get("target_thread_ref") or ""),
        "payload": dict(payload),
        "proof_refs": _as_list(action.get("proof_refs")),
    }


def _action_safe(action: Mapping[str, Any]) -> bool:
    if action.get("business_action") is True:
        return False
    if action.get("enabled") is False:
        return False
    boundary = action.get("authority_boundary")
    if isinstance(boundary, Mapping) and any(value is True for value in boundary.values()):
        return False
    payload = action.get("payload") if isinstance(action.get("payload"), Mapping) else {}
    payload_boundary = payload.get("authority_boundary")
    if isinstance(payload_boundary, Mapping) and any(value is True for value in payload_boundary.values()):
        return False
    return not unsafe_true_grants(action)


def _route_ask_why(
    request: Mapping[str, Any],
    *,
    read_model_root: Path,
    receipt_id: str,
    generated_at: str,
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    answer = _contextual_answer(read_model_root, request)
    receipt = _base_receipt(request, receipt_id=receipt_id, generated_at=generated_at, validation=validation)
    card = _card_response(
        receipt_id=receipt_id,
        event_type="ask_why",
        headline=answer["headline"],
        summary=answer["plain_summary"],
        status_label="Context answer",
        route_status="ROUTED",
        current_world_ref=str(request.get("current_world_ref") or ""),
        current_thread_ref=str(request.get("current_thread_ref") or ""),
        actions=[],
        proof_refs=list(answer["proof_refs"]),
    )
    receipt.update(
        {
            "route_status": "ROUTED",
            "raw_internal_status": RESPONSE_READY,
            "backend_route": "system_question_answer.contextual_answer",
            "route_ref": "system_question_answer:contextual_lane_answer",
            "route_result": answer,
            "dynamic_card_response": card,
            "proof_refs": list(card["proof"]["proof_refs"]),
            "machine_proof": _machine_proof(package_staged=False),
        }
    )
    return receipt


def _route_open_lane(
    request: Mapping[str, Any],
    *,
    read_model_root: Path,
    receipt_id: str,
    generated_at: str,
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    action = _action_payload_by_id(read_model_root, str(request.get("selected_action_id") or ""))
    if action and str(action.get("action_type") or "") != "navigate":
        action = None
    if action and not _action_safe(action):
        return _blocked_receipt(
            request,
            receipt_id=receipt_id,
            generated_at=generated_at,
            validation=validation,
            route_status="NEEDS_VERIFICATION",
            headline="Needs verification",
            summary="The selected lane action is not a safe navigation payload.",
            blocker="selected_action_payload_not_safe_navigation",
        )
    target_world = str((action or {}).get("target_world_ref") or request.get("current_world_ref") or "")
    target_thread = str((action or {}).get("target_thread_ref") or request.get("current_thread_ref") or "")
    action_summary = _safe_action_summary(action) if action else {
        "action_id": "controller.open_current_lane",
        "action_type": "navigate",
        "label": "Open lane",
        "enabled": True,
        "business_action": False,
        "target_world_ref": target_world,
        "target_thread_ref": target_thread,
        "payload": {"open_lane_only": True},
        "proof_refs": ["generated/read_models/dynamic_card_packet_latest.json"],
    }
    receipt = _base_receipt(request, receipt_id=receipt_id, generated_at=generated_at, validation=validation)
    card = _card_response(
        receipt_id=receipt_id,
        event_type=str(request.get("controller_event_type") or "open_lane"),
        headline="Lane navigation ready",
        summary=f"Mission Control can navigate to {target_world}/{target_thread}. No business action is attached.",
        status_label="Navigation only",
        route_status="ROUTED",
        current_world_ref=target_world,
        current_thread_ref=target_thread,
        actions=[action_summary],
        proof_refs=action_summary["proof_refs"],
    )
    receipt.update(
        {
            "route_status": "ROUTED",
            "raw_internal_status": RESPONSE_READY,
            "backend_route": "operator_action_payloads.navigate",
            "route_ref": str(action_summary["action_id"]),
            "route_result": {"navigation": action_summary, "business_action": False},
            "dynamic_card_response": card,
            "proof_refs": list(card["proof"]["proof_refs"]),
            "machine_proof": _machine_proof(navigation_only=True),
        }
    )
    return receipt


def _route_attach_proof(
    request: Mapping[str, Any],
    *,
    receipt_id: str,
    generated_at: str,
    validation: Mapping[str, Any],
    evidence_sqlite_path: Path,
    artifact_lineage_sqlite_path: Path | None,
) -> dict[str, Any]:
    envelope = validation.get("operator_authority_envelope") if isinstance(validation.get("operator_authority_envelope"), Mapping) else {}
    note = str(request.get("operator_text") or "")
    intended_use = str(request.get("intended_use") or "")
    text = " ".join(
        str(request.get(key) or "")
        for key in ("operator_text", "artifact_ref", "selected_card_id", "selected_action_id", "active_entity_ref")
    ).lower()
    if not intended_use:
        intended_use = "payment_proof" if "payment" in text or str(request.get("current_world_ref") or "") == "finance" else "general_reference"
    evidence_request = {
        "request_id": f"controller_event_evidence_intake_{_short_hash(receipt_id)}",
        "request_type": evidence_intake.VERIFIED_REQUEST_TYPE,
        "kind": evidence_intake.VERIFIED_REQUEST_TYPE,
        "type": evidence_intake.VERIFIED_REQUEST_TYPE,
        "source_surface": "mission_control",
        "current_world_ref": str(request.get("current_world_ref") or ""),
        "current_thread_ref": str(request.get("current_thread_ref") or ""),
        "world_ref": str(request.get("current_world_ref") or ""),
        "thread_ref": str(request.get("current_thread_ref") or ""),
        "claimed_client_ref": str(request.get("current_thread_ref") or ""),
        "claimed_workflow_ref": str(request.get("claimed_workflow_ref") or request.get("workflow_ref") or f"{request.get('current_thread_ref', '')}_payment_watch"),
        "operator_ref": str(envelope.get("operator_ref") or ""),
        "app_instance_ref": str(envelope.get("app_instance_ref") or ""),
        "device_ref": str(envelope.get("device_ref") or ""),
        "session_ref": str(envelope.get("session_ref") or ""),
        "created_at": generated_at,
        "request_hash": str(envelope.get("request_hash") or operator_authority.compute_request_hash(request)),
        "artifact_path": str(request.get("artifact_path") or ""),
        "bridge_artifact_ref": str(request.get("bridge_artifact_ref") or request.get("artifact_ref") or ""),
        "artifact_kind": str(request.get("artifact_kind") or "screenshot"),
        "operator_note": note or "Operator attached proof from Mission Control.",
        "privacy_class": "financial_sensitive" if intended_use == "payment_proof" else str(request.get("privacy_class") or "internal_reference"),
        "intended_use": intended_use,
        "authority_boundary": dict(evidence_intake.AUTHORITY_BOUNDARY),
    }
    record = evidence_intake.record_evidence_intake(
        evidence_request,
        sqlite_path=evidence_sqlite_path,
        artifact_lineage_sqlite_path=artifact_lineage_sqlite_path,
        generated_at=generated_at,
    )
    receipt = _base_receipt(request, receipt_id=receipt_id, generated_at=generated_at, validation=validation)
    if record.get("status") != evidence_intake.READY_STATUS:
        return _blocked_receipt(
            request,
            receipt_id=receipt_id,
            generated_at=generated_at,
            validation=validation,
            route_status="NEEDS_VERIFICATION",
            headline="Needs verification",
            summary="Evidence intake blocked because the proof request was incomplete or unverified.",
            blocker="evidence_intake_blocked",
        )
    card = dict(record.get("dynamic_card") or {})
    card["controller_event_type"] = "attach_proof"
    card.setdefault("authority_boundary", dict(AUTHORITY_BOUNDARY))
    receipt.update(
        {
            "route_status": "ROUTED",
            "raw_internal_status": RESPONSE_READY,
            "backend_route": "evidence_intake.record_candidate_evidence",
            "route_ref": str(record.get("intake_id") or ""),
            "route_receipt_ref": str(record.get("request_ref") or ""),
            "route_result": record,
            "dynamic_card_response": card,
            "proof_refs": [
                "generated/read_models/evidence_intake_status.json",
                str(record.get("artifact_ref") or ""),
                str(record.get("request_ref") or ""),
            ],
            "machine_proof": _machine_proof(
                evidence_intake_recorded=True,
                payment_processing_evidence_does_not_mark_paid=(record.get("payment") or {}).get("paid") is False,
                ledger_mutation_performed=False,
                paid_marking_performed=False,
            ),
        }
    )
    return receipt


def _route_workroom_decision(
    request: Mapping[str, Any],
    *,
    read_model_root: Path,
    export_root: Path,
    bridge_root: Path | None,
    workroom_wiki_path: Path | None,
    receipt_id: str,
    generated_at: str,
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    event_type = str(request.get("controller_event_type") or "")
    action = _find_review_action_payload(read_model_root, event_type, request)
    if not action:
        return _blocked_receipt(
            request,
            receipt_id=receipt_id,
            generated_at=generated_at,
            validation=validation,
            route_status="NEEDS_VERIFICATION",
            headline="Needs verification",
            summary="No deterministic review decision action payload matched the selected card/action.",
            blocker="missing_action_payload",
        )
    if not _action_safe(action):
        return _blocked_receipt(
            request,
            receipt_id=receipt_id,
            generated_at=generated_at,
            validation=validation,
            route_status="NEEDS_VERIFICATION",
            headline="Needs verification",
            summary="The selected review decision payload requested unsafe authority.",
            blocker="unsafe_action_payload",
        )
    payload = dict(action.get("payload") or {})
    payload["reason"] = str(request.get("operator_text") or payload.get("reason") or "")
    payload["request_id"] = f"controller_event_workroom_review_{_short_hash(receipt_id)}"
    result = workroom_review_decision_consumer.consume_workroom_review_decision_request(
        payload,
        source_request_filename=f"{payload['request_id']}.json",
        generated_at=generated_at,
        read_model_root=read_model_root,
        export_root=export_root,
        bridge_export_root=bridge_root,
        wiki_path=workroom_wiki_path or workroom_review_decision_consumer.DEFAULT_WIKI_PATH,
    )
    workroom_receipt = result.receipt
    receipt = _base_receipt(request, receipt_id=receipt_id, generated_at=generated_at, validation=validation)
    routed = str(workroom_receipt.get("raw_internal_status") or "") == RESPONSE_READY
    display = workroom_receipt.get("operator_display") if isinstance(workroom_receipt.get("operator_display"), Mapping) else {}
    card = _card_response(
        receipt_id=receipt_id,
        event_type=event_type,
        headline=str(display.get("headline") or workroom_receipt.get("response_primary_status") or "Review decision recorded"),
        summary=str(display.get("plain_summary") or "Review decision receipt recorded only."),
        status_label=str(workroom_receipt.get("response_primary_status") or "Review decision"),
        route_status="ROUTED" if routed else "NEEDS_VERIFICATION",
        current_world_ref=str(request.get("current_world_ref") or ""),
        current_thread_ref=str(request.get("current_thread_ref") or ""),
        proof_refs=_as_list(workroom_receipt.get("proof_refs")),
        tone="calm" if routed else "blocked",
    )
    receipt.update(
        {
            "route_status": "ROUTED" if routed else "NEEDS_VERIFICATION",
            "raw_internal_status": RESPONSE_READY if routed else BLOCKED_WITH_REASON,
            "backend_route": "workroom_review_decision_consumer.record_decision_only",
            "route_ref": str(action.get("action_id") or ""),
            "route_receipt_ref": str(workroom_receipt.get("receipt_id") or ""),
            "route_result": workroom_receipt,
            "dynamic_card_response": card,
            "proof_refs": list(card["proof"]["proof_refs"]),
            "machine_proof": _machine_proof(
                review_decision_recorded=bool(workroom_receipt.get("decision_recorded") is True),
                merge_performed=False,
                git_push_performed=False,
            ),
        }
    )
    return receipt


def _route_show_details(
    request: Mapping[str, Any],
    *,
    read_model_root: Path,
    receipt_id: str,
    generated_at: str,
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    card = _card_by_id(read_model_root, str(request.get("selected_card_id") or ""))
    proof_refs = _proof_refs_from_card(card)
    headline = "Proof details"
    summary = "Proof/details are available in the drawer. No action was performed."
    if card:
        headline = f"Details: {card.get('headline', 'Selected card')}"
        summary = str(card.get("plain_summary") or summary)
    receipt = _base_receipt(request, receipt_id=receipt_id, generated_at=generated_at, validation=validation)
    response_card = _card_response(
        receipt_id=receipt_id,
        event_type="show_details",
        headline=headline,
        summary=summary,
        status_label="Details",
        route_status="ROUTED",
        current_world_ref=str(request.get("current_world_ref") or ""),
        current_thread_ref=str(request.get("current_thread_ref") or ""),
        proof_refs=proof_refs,
    )
    receipt.update(
        {
            "route_status": "ROUTED",
            "raw_internal_status": RESPONSE_READY,
            "backend_route": "dynamic_card_packet.proof_drawer",
            "route_ref": str(request.get("selected_card_id") or ""),
            "route_result": {"selected_card": card or {}, "proof_refs": proof_refs},
            "dynamic_card_response": response_card,
            "proof_refs": proof_refs,
            "machine_proof": _machine_proof(details_only=True),
        }
    )
    return receipt



def _selected_action_permits_objective_advancement(
    read_model_root: Path,
    event_type: str,
    request: Mapping[str, Any],
) -> bool:
    if event_type != "do_it":
        return False
    selected_action_id = _canonical_action_id(str(request.get("selected_action_id") or ""))
    if not selected_action_id:
        return False
    action = _action_payload_by_id(read_model_root, selected_action_id)
    if not action or not _action_safe(action):
        return False
    action_id = str(action.get("action_id") or "")
    if action_id in OBJECTIVE_ADVANCEMENT_DO_IT_ACTION_IDS:
        return True
    return any(action_id.startswith(prefix) for prefix in OBJECTIVE_ADVANCEMENT_DO_IT_ACTION_PREFIXES)


def _class_a_approved(request: Mapping[str, Any]) -> bool:
    if request.get("class_a_approved") is True or request.get("class_a_approval_present") is True:
        return True
    scope = request.get("class_a_approval_scope")
    return isinstance(scope, Mapping) and scope.get("class_a_approval_present") is True


def _objective_current_state(
    *,
    read_model_root: Path,
    request: Mapping[str, Any],
    world: str,
    thread: str,
) -> dict[str, Any]:
    state = dict(request.get("current_state") or {}) if isinstance(request.get("current_state"), Mapping) else {}
    root = _rooted(read_model_root)
    if world == "finance" and thread == "capital_hilton":
        status = _load_json(root / "capital_hilton_invoice_operator_run_status.json")
        state.setdefault("invoice_submitted", bool(status.get("coupa_submitted") or status.get("coupa_submission_recorded")))
        state.setdefault("coupa_processing", str(status.get("coupa_submission_status") or status.get("coupa_status_observed") or "").lower() == "processing")
        state.setdefault("payment_evidence_present", bool(status.get("payment_received_recorded") or status.get("payment_evidence_present")))
        state.setdefault("paid", bool(status.get("paid") is True))
        state.setdefault("ledger_untouched", not bool(status.get("ledger_mutation_performed") or status.get("ledger_posting_performed")))
        state.setdefault("source_status_ref", "generated/read_models/capital_hilton_invoice_operator_run_status.json")
    elif world == "finance" and thread == "live_arts_md":
        evidence_attached = bool(
            state.get("evidence_attached")
            or request.get("evidence_attached")
            or request.get("artifact_ref")
            or request.get("bridge_artifact_ref")
            or request.get("artifact_path")
        )
        state.setdefault("evidence_attached", evidence_attached)
        state.setdefault("paid", False)
        state.setdefault("ledger_untouched", True)
    elif world == "business_development" and thread == "capital_hilton":
        proposal = _load_json(root / "capital_hilton_business_development_proposal.json")
        state.setdefault("proposal_sent_recorded", bool(proposal.get("proposal_sent_recorded")))
        state.setdefault("client_review_pending", bool(proposal.get("client_review_pending")))
        state.setdefault("email_send_allowed", False)
    return state


def _objective_context_from_request(
    request: Mapping[str, Any],
    *,
    read_model_root: Path,
) -> dict[str, Any]:
    action = _action_payload_by_id(read_model_root, str(request.get("selected_action_id") or ""))
    payload = action.get("payload") if isinstance(action, Mapping) and isinstance(action.get("payload"), Mapping) else {}
    world = str((action or {}).get("target_world_ref") or request.get("current_world_ref") or "").strip().lower()
    thread = str((action or {}).get("target_thread_ref") or request.get("current_thread_ref") or "").strip().lower()
    review_packet_id = _review_packet_id_from_request(request, action)
    requested_review_action = str(payload.get("decision_action") or request.get("decision_action") or "")
    state = _objective_current_state(read_model_root=read_model_root, request=request, world=world, thread=thread)
    if review_packet_id:
        state.setdefault("review_packet_id", review_packet_id)
    action_label = str((action or {}).get("label") or "")
    return {
        "objective_ref": str(
            request.get("objective_ref")
            or payload.get("objective_ref")
            or f"objective:{world or 'unknown'}:{thread or 'unknown'}:advance"
        ),
        "current_world_ref": world,
        "current_thread_ref": thread,
        "current_state": state,
        "desired_outcome": str(request.get("desired_outcome") or request.get("operator_text") or action_label or "advance current objective safely"),
        "selected_action_id": str((action or {}).get("action_id") or request.get("selected_action_id") or ""),
        "selected_action_type": str((action or {}).get("action_type") or ""),
        "selected_action_label": action_label,
        "review_packet_id": review_packet_id,
        "requested_review_action": requested_review_action,
        "class_a_approved": _class_a_approved(request),
    }


def _adapt_objective_card_for_controller(
    decision: Mapping[str, Any],
    *,
    event_type: str,
) -> tuple[dict[str, Any], str]:
    card = json.loads(json.dumps(decision.get("dynamic_card") or {}))
    next_state = str(decision.get("next_safe_state") or "")
    suggested_event = "continue"
    card["controller_event_type"] = event_type
    card["authority_boundary"] = dict(AUTHORITY_BOUNDARY)
    card.setdefault("proof", {})["collapsed_by_default"] = True
    card.setdefault("proof", {})["label"] = "Details"
    card["machine_proof"] = _machine_proof(objective_advancement_response=True)

    if next_state == "REQUEST_PAYMENT_EVIDENCE":
        suggested_event = "attach_proof"
        card["headline"] = "Payment evidence needed"
        card["plain_summary"] = "I can't complete payment yet. Attach payment evidence before anything touches the ledger."
        card["summary"] = card["plain_summary"]
        card["next_safe_action"] = "Attach payment evidence."
        card["status_label"] = "Payment evidence needed"
    elif next_state == "EVIDENCE_RECORDED_WAITING_FOR_CONFIRMATION":
        card["headline"] = "Evidence waiting for confirmation"
        card["summary"] = str(card.get("plain_summary") or "")
    elif next_state == "FOLLOWUP_DRAFT_STAGED":
        card["headline"] = "Follow-up draft can be staged"
        card["summary"] = str(card.get("plain_summary") or "")
    elif next_state == "NEEDS_VERIFICATION":
        card["headline"] = "Needs verification"
        card["summary"] = str(card.get("plain_summary") or "")

    slots = card.get("action_slots") if isinstance(card.get("action_slots"), list) else []
    if slots:
        primary = slots[0]
        if isinstance(primary, dict):
            primary["controller_event_type"] = suggested_event
            primary["authority_boundary"] = dict(AUTHORITY_BOUNDARY)
            if suggested_event == "attach_proof":
                primary["label"] = "Attach payment evidence"
    card["suggested_controller_event"] = suggested_event
    card["actions"] = [slot for slot in slots if isinstance(slot, Mapping)]
    return card, suggested_event


def _route_objective_advancement(
    request: Mapping[str, Any],
    *,
    read_model_root: Path,
    receipt_id: str,
    generated_at: str,
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    context = _objective_context_from_request(request, read_model_root=read_model_root)
    decision = objective_advancement_protocol.advance_objective(context, generated_at=generated_at)
    card, suggested_event = _adapt_objective_card_for_controller(
        decision,
        event_type=str(request.get("controller_event_type") or "advance_objective"),
    )
    route_status = "ROUTED"
    if decision.get("blocked") is True:
        route_status = "NEEDS_PROOF" if decision.get("missing_input") == "payment_evidence" else "NEEDS_VERIFICATION"
    route_result = json.loads(json.dumps(decision))
    route_result["suggested_controller_event"] = suggested_event
    route_result["controller_route_status"] = route_status
    if context.get("review_packet_id"):
        route_result["review_packet_id"] = context["review_packet_id"]
    route_result["class_a_approval_bypasses_guardian"] = False
    receipt = _base_receipt(request, receipt_id=receipt_id, generated_at=generated_at, validation=validation)
    receipt.update(
        {
            "route_status": route_status,
            "raw_internal_status": RESPONSE_READY,
            "backend_route": "objective_advancement_protocol.advance_objective",
            "route_ref": str(decision.get("objective_ref") or ""),
            "route_receipt_ref": str(decision.get("dynamic_card_ref") or ""),
            "route_result": route_result,
            "dynamic_card_response": card,
            "proof_refs": list(decision.get("proof_refs") or card.get("proof", {}).get("read_model_refs") or []),
            "machine_proof": _machine_proof(
                objective_advancement_performed=True,
                suggested_controller_event=suggested_event,
                protected_final_action_blocked=True,
                class_a_approval_bypasses_guardian=False,
                payment_evidence_missing=decision.get("missing_input") == "payment_evidence",
                ledger_mutation_performed=False,
                paid_marking_performed=False,
                coupa_access_performed=False,
                browser_access_performed=False,
                submit_performed=False,
                merge_performed=False,
                git_push_performed=False,
            ),
        }
    )
    return receipt

def _route_action_payload(
    request: Mapping[str, Any],
    *,
    read_model_root: Path,
    receipt_id: str,
    generated_at: str,
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    event_type = str(request.get("controller_event_type") or "")
    action = _resolve_action_payload(read_model_root, event_type, request)
    if not action:
        protected_text = " ".join(str(request.get(key) or "") for key in ("operator_text", "selected_action_id", "selected_card_id")).lower()
        if any(term in protected_text for term in PROTECTED_TERMS):
            route_status = "PROTECTED_ACTION_STAGED_OR_BLOCKED"
            summary = "This looks like a protected action, but no deterministic safe staging payload matched it. No execution ran."
        else:
            route_status = "NEEDS_VERIFICATION"
            summary = "No deterministic operator_action_payload matched the selected card/action."
        return _blocked_receipt(
            request,
            receipt_id=receipt_id,
            generated_at=generated_at,
            validation=validation,
            route_status=route_status,
            headline="Needs verification",
            summary=summary,
            blocker="missing_action_payload",
        )
    if not _action_safe(action):
        return _blocked_receipt(
            request,
            receipt_id=receipt_id,
            generated_at=generated_at,
            validation=validation,
            route_status="NEEDS_VERIFICATION",
            headline="Needs verification",
            summary="The deterministic action payload is disabled or requests unsafe authority.",
            blocker="unsafe_or_disabled_action_payload",
        )

    action_type = str(action.get("action_type") or "")
    action_summary = _safe_action_summary(action)
    if action_type == "navigate":
        backend_route = "operator_action_payloads.navigate"
        headline = action_summary["label"] or "Navigation ready"
        summary = "Mission Control can navigate to the target lane. No business action was performed."
        status_label = "Navigation only"
        route_status = "ROUTED"
    elif action_type == "stage_package_request":
        payload = action_summary["payload"]
        if payload.get("approval_request_id") or payload.get("gate_ref"):
            backend_route = "approval_request_queue.stage_only"
            headline = "Approval staged for review"
            summary = "A protected action was staged as an approval/gate reference only. No Coupa, browser, send, submit, ledger, workbook, or paid action ran."
            status_label = "Stage only"
            route_status = "PROTECTED_ACTION_STAGED_OR_BLOCKED"
        else:
            backend_route = "workflow_package_request_consumer.stage_only"
            headline = action_summary["label"] or "Package staged for review"
            summary = "The request is limited to drafting/staging for operator review. No send or business execution ran."
            status_label = "Stage only"
            route_status = "ROUTED"
    elif action_type == "explain_gate":
        backend_route = "guardian_gate.explain"
        headline = action_summary["label"] or "Gate explanation"
        summary = str(action_summary["payload"].get("why_it_matters") or "Protected action remains gated.")
        status_label = "Gate"
        route_status = "ROUTED"
    else:
        return _blocked_receipt(
            request,
            receipt_id=receipt_id,
            generated_at=generated_at,
            validation=validation,
            route_status="NEEDS_VERIFICATION",
            headline="Needs verification",
            summary=f"Action type {action_type or 'unknown'} is not executable through this controller router.",
            blocker="unsupported_action_payload_type",
        )

    receipt = _base_receipt(request, receipt_id=receipt_id, generated_at=generated_at, validation=validation)
    card = _card_response(
        receipt_id=receipt_id,
        event_type=event_type,
        headline=headline,
        summary=summary,
        status_label=status_label,
        route_status="ROUTED" if route_status == "ROUTED" else route_status,
        current_world_ref=str(action.get("target_world_ref") or request.get("current_world_ref") or ""),
        current_thread_ref=str(action.get("target_thread_ref") or request.get("current_thread_ref") or ""),
        actions=[action_summary],
        proof_refs=action_summary["proof_refs"] or ["generated/read_models/operator_action_payloads.json"],
        tone="calm" if route_status == "ROUTED" else "warning",
    )
    route_result: dict[str, Any] = {"action_payload": action_summary, "stage_only": action_type == "stage_package_request"}
    if action_type == "navigate":
        route_result["navigation"] = action_summary
    receipt.update(
        {
            "route_status": route_status,
            "raw_internal_status": RESPONSE_READY,
            "backend_route": backend_route,
            "route_ref": str(action.get("action_id") or ""),
            "route_result": route_result,
            "dynamic_card_response": card,
            "proof_refs": list(card["proof"]["proof_refs"]),
            "machine_proof": _machine_proof(
                stage_only=action_type == "stage_package_request",
                navigation_only=action_type == "navigate",
                protected_action_staged_only=route_status == "PROTECTED_ACTION_STAGED_OR_BLOCKED",
            ),
        }
    )
    return receipt


def _route_operator_conversation(
    request: Mapping[str, Any],
    *,
    read_model_root: Path,
    receipt_id: str,
    generated_at: str,
    validation: Mapping[str, Any],
    proof_to_response_sqlite_path: Path | None = None,
) -> dict[str, Any]:
    conversation = operator_conversation_router.route_conversation_text(
        request,
        read_model_root=read_model_root,
        sqlite_path=proof_to_response_sqlite_path or operator_conversation_router.DEFAULT_SQLITE_PATH,
        generated_at=generated_at,
    )
    display = conversation.get("operator_display") if isinstance(conversation.get("operator_display"), Mapping) else {}
    next_event = str(conversation.get("suggested_controller_event") or "show_details")
    actions = []
    primary_next_step = conversation.get("primary_next_step") if isinstance(conversation.get("primary_next_step"), Mapping) else {}
    next_safe_action = str(primary_next_step.get("label") or display.get("next_safe_action") or "Show details")
    if primary_next_step.get("next_step_kind") == "request_authority":
        next_event = "make_it_so"
    elif primary_next_step.get("next_step_kind") in {"pick_up_work_package", "configure_connector", "provide_proof"}:
        next_event = "show_details"
    if next_safe_action:
        actions.append(
            {
                "label": next_safe_action,
                "controller_event_type": next_event,
                "enabled": True,
                "business_action": False,
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            }
        )
    route_status = str(conversation.get("route_status") or "TEXT_RESPONSE_READY")
    routed_conversation_statuses = {
        "TEXT_RESPONSE_READY",
        "PROTECTED_ACTION_BLOCKED_TEXT_RESPONSE",
        "STAGE_PLAN_TEXT_RESPONSE",
        "CAPABILITY_GAP_AUTHORITY_REQUEST_READY",
        "AUTHORITY_GRANT_COMPILED",
    }
    card = _card_response(
        receipt_id=receipt_id,
        event_type="chat_goal",
        headline=str(display.get("headline") or "OpenClaw response"),
        summary=str(display.get("plain_summary") or "I routed this text through the conversation router."),
        status_label=str(display.get("headline") or "Conversation"),
        route_status="ROUTED" if route_status in routed_conversation_statuses else "NEEDS_VERIFICATION",
        current_world_ref=str(request.get("current_world_ref") or ""),
        current_thread_ref=str(request.get("current_thread_ref") or ""),
        actions=actions,
        proof_refs=list(conversation.get("proof_refs") or []),
        tone="blocked" if "BLOCKED" in route_status else "calm",
    )
    if primary_next_step:
        card["primary_next_step"] = dict(primary_next_step)
        card["next_step_status_receipt"] = dict(conversation.get("next_step_status_receipt") or {})
    if isinstance(conversation.get("capability_authority"), Mapping):
        card["capability_authority"] = dict(conversation["capability_authority"])
        request_obj = conversation["capability_authority"].get("operator_authority_request")
        if isinstance(request_obj, Mapping):
            card["authority_request_ref"] = str(request_obj.get("request_id") or "")
            card["capability_gap_ref"] = str(
                (conversation["capability_authority"].get("capability_gap") or {}).get("gap_id")
                if isinstance(conversation["capability_authority"].get("capability_gap"), Mapping)
                else ""
            )
    _attach_card_run_mode(card, conversation.get("run_mode_context") if isinstance(conversation.get("run_mode_context"), Mapping) else _request_run_mode_context(request, generated_at))
    receipt = _base_receipt(request, receipt_id=receipt_id, generated_at=generated_at, validation=validation)
    receipt.update(
        {
            "route_status": route_status,
            "raw_internal_status": RESPONSE_READY,
            "backend_route": "operator_conversation_router.route_conversation_text",
            "route_ref": str(conversation.get("response_id") or ""),
            "route_receipt_ref": str(conversation.get("proof_response", {}).get("response_id") or ""),
            "route_result": conversation,
            "dynamic_card_response": card,
            "proof_refs": list(card["proof"]["proof_refs"]),
            "machine_proof": _machine_proof(
                operator_conversation_router_performed=True,
                text_first_response=True,
                package_staged=False,
                workflow_package_staged=False,
                workflow_package_request_v0_emitted=False,
                model_invoked=False,
                external_llm_invoked=False,
                local_model_runtime_connected=False,
                worker_spawn_performed=False,
                business_action_performed=False,
            ),
        }
    )
    return receipt


def _attach_typed_contract_trace_to_receipt(
    receipt: dict[str, Any],
    trace: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(trace, Mapping):
        return receipt
    decision = trace.get("typed_contract_decision")
    if not isinstance(decision, Mapping) or not str(decision.get("decision_id") or ""):
        return receipt
    matches = trace.get("typed_contract_matches")
    receipt["typed_contract_decision"] = dict(decision)
    receipt["typed_contract_matches"] = (
        [str(item) for item in matches if str(item)]
        if isinstance(matches, (list, tuple))
        else []
    )
    machine_proof = dict(receipt.get("machine_proof") or {})
    machine_proof["typed_contract_decision"] = dict(decision)
    machine_proof["typed_contract_matches"] = list(receipt["typed_contract_matches"])
    model_call_status = str(decision.get("model_call_status") or "")
    if model_call_status == "unknown":
        machine_proof["model_invoked"] = None
        machine_proof["model_call_performed"] = None
        machine_proof["local_model_runtime_connected"] = None
        machine_proof["typed_contract_model_call_status"] = "unknown"
    receipt["machine_proof"] = machine_proof
    return receipt


def _route_maestro_cassandra_conversation(
    request: Mapping[str, Any],
    *,
    read_model_root: Path,
    receipt_id: str,
    generated_at: str,
    validation: Mapping[str, Any],
    _typed_contract_trace_sink: dict[str, Any] | None = None,
    first_touch_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    operator_text = maestro_cassandra_responder.operator_text_from_request(request)
    session = maestro_cassandra_responder.session_from_request(request)
    source_surface = str(
        request.get("active_surface_ref")
        or request.get("source_surface")
        or request.get("source_channel")
        or "operator_controller_event_router"
    )
    try:
        agent = _resolved_frontdoor_agent(request, session=session)
        result = maestro_cassandra_responder.answer_frontdoor_chat(
            operator_text,
            session=session,
            source_surface=source_surface,
            agent=agent,
            first_touch_receipt=first_touch_receipt,
        )
    except TypeError as exc:
        if "source_surface" not in str(exc) and "first_touch_receipt" not in str(exc):
            raise
        result = maestro_cassandra_responder.answer_frontdoor_chat(operator_text, session=session)
    typed_contract_trace = maestro_cassandra_responder.typed_contract_trace_for_result(result)
    if _typed_contract_trace_sink is not None:
        _typed_contract_trace_sink.update(typed_contract_trace)
    if result.status != "ANSWER_READY":
        return None

    backend_route = maestro_cassandra_responder.backend_route_for_result(result)
    proof_refs = maestro_cassandra_responder.proof_refs_for_result(
        result,
        "generated/read_models/operator_controller_event_router_status.json",
    )
    external_llm_invoked = maestro_cassandra_responder.external_llm_invoked_for_result(result)
    result_payload = maestro_cassandra_responder.result_dict_for_receipt(result)
    card = _card_response(
        receipt_id=receipt_id,
        event_type="chat_goal",
        headline=result.one_line_answer or "Maestro response",
        summary=result.plain_summary,
        status_label="Maestro",
        route_status="ROUTED",
        current_world_ref=str(request.get("current_world_ref") or ""),
        current_thread_ref=str(request.get("current_thread_ref") or ""),
        actions=[],
        proof_refs=list(proof_refs),
        tone="calm",
    )
    card["mac_render_hint"] = result.mac_render_hint
    card["maestro_cassandra_responder"] = result_payload
    _attach_card_run_mode(
        card,
        _request_run_mode_context(request, generated_at),
    )
    machine_proof = _machine_proof(
        maestro_cassandra_responder_performed=True,
        text_first_response=True,
        operator_conversation_router_performed=False,
        package_staged=False,
        workflow_package_staged=False,
        workflow_package_request_v0_emitted=False,
        model_invoked=False,
        external_llm_invoked=external_llm_invoked,
        local_model_runtime_connected=False,
        worker_spawn_performed=False,
        business_action_performed=False,
    )
    machine_proof.update(maestro_cassandra_responder.machine_proof_for_result(result))
    receipt = _base_receipt(request, receipt_id=receipt_id, generated_at=generated_at, validation=validation)
    receipt.update(
        {
            "route_status": "TEXT_RESPONSE_READY",
            "raw_internal_status": RESPONSE_READY,
            "backend_route": backend_route,
            "route_ref": f"maestro_cassandra_{_short_hash(receipt_id, operator_text, length=12)}",
            "route_receipt_ref": receipt_id,
            "route_result": result_payload,
            "primary_response_kind": "maestro_cassandra_chat_answer",
            "one_line_answer": result.one_line_answer,
            "plain_summary": result.plain_summary,
            "mac_render_hint": result.mac_render_hint,
            "dynamic_card_response": card,
            "proof_refs": list(card["proof"]["proof_refs"]),
            "machine_proof": machine_proof,
        }
    )
    return _attach_typed_contract_trace_to_receipt(receipt, typed_contract_trace)


def _route_run_mode_set(
    request: Mapping[str, Any],
    *,
    router_sqlite_path: Path,
    receipt_id: str,
    generated_at: str,
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    result = global_run_mode_context.handle_run_mode_set_request(
        router_sqlite_path,
        request,
        generated_at=generated_at,
    )
    run_mode_context = result.get("run_mode_context") if isinstance(result.get("run_mode_context"), Mapping) else {}
    request_with_mode = dict(request)
    request_with_mode["run_mode_context"] = run_mode_context
    status = str(result.get("status") or "RUN_MODE_SET_BLOCKED")
    blocked = status != "RUN_MODE_SET"
    state = result.get("run_mode_state") if isinstance(result.get("run_mode_state"), Mapping) else {}
    active_mode = str(state.get("active_run_mode") or run_mode_context.get("run_mode") or global_run_mode_context.PRODUCTION)
    card = _card_response(
        receipt_id=receipt_id,
        event_type=global_run_mode_context.RUN_MODE_SET_EVENT_TYPE,
        headline="Run mode change blocked" if blocked else "Run mode set",
        summary=(
            "The requested run-mode change was blocked because explicit test-live authority and allowlists are required."
            if blocked
            else f"OpenClaw is now in {active_mode} for the requested scope."
        ),
        status_label="Blocked" if blocked else "Run mode",
        route_status="BLOCKED" if blocked else "ROUTED",
        current_world_ref=str(request.get("current_world_ref") or ""),
        current_thread_ref=str(request.get("current_thread_ref") or ""),
        proof_refs=[
            "generated/read_models/global_run_mode_context.json",
            "generated/read_models/operator_controller_event_router_status.json",
        ],
        tone="blocked" if blocked else "calm",
    )
    _attach_card_run_mode(card, run_mode_context or _request_run_mode_context(request_with_mode, generated_at))
    receipt = _base_receipt(
        request_with_mode,
        receipt_id=receipt_id,
        generated_at=generated_at,
        validation=validation,
    )
    receipt.update(
        {
            "route_status": status,
            "raw_internal_status": BLOCKED_WITH_REASON if blocked else RESPONSE_READY,
            "backend_route": "global_run_mode_context.handle_run_mode_set_request",
            "route_ref": str(state.get("state_ref") or ""),
            "route_receipt_ref": str(state.get("receipt_ref") or ""),
            "route_result": result,
            "run_mode_state": state,
            "run_mode_transition_receipt": dict(result.get("transition_receipt") or {}),
            "dynamic_card_response": card,
            "proof_refs": list(card["proof"]["proof_refs"]),
            "machine_proof": _machine_proof(
                dynamic_card_response_emitted=True,
                production_default_preserved=active_mode == global_run_mode_context.PRODUCTION,
                test_live_requires_explicit_authority=True,
                incoming_authority_granted_accepted=False,
                business_action_performed=False,
                live_external_provider_action_performed=False,
            ),
        }
    )
    return receipt


def _route_event(
    request: Mapping[str, Any],
    *,
    read_model_root: Path,
    export_root: Path,
    bridge_root: Path | None,
    workroom_wiki_path: Path | None,
    receipt_id: str,
    generated_at: str,
    validation: Mapping[str, Any],
    evidence_sqlite_path: Path,
    artifact_lineage_sqlite_path: Path | None,
    proof_to_response_sqlite_path: Path | None = None,
    router_sqlite_path: Path = DEFAULT_SQLITE_PATH,
    first_touch_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    event_type = str(request.get("controller_event_type") or "")
    if event_type == global_run_mode_context.RUN_MODE_SET_EVENT_TYPE:
        return _route_run_mode_set(
            request,
            router_sqlite_path=router_sqlite_path,
            receipt_id=receipt_id,
            generated_at=generated_at,
            validation=validation,
        )
    if event_type == "chat_goal":
        typed_contract_trace: dict[str, Any] = {}
        maestro_receipt = _route_maestro_cassandra_conversation(
            request,
            read_model_root=read_model_root,
            receipt_id=receipt_id,
            generated_at=generated_at,
            validation=validation,
            _typed_contract_trace_sink=typed_contract_trace,
            first_touch_receipt=first_touch_receipt,
        )
        if maestro_receipt is not None:
            return maestro_receipt
        fallback_receipt = _route_operator_conversation(
            request,
            read_model_root=read_model_root,
            receipt_id=receipt_id,
            generated_at=generated_at,
            validation=validation,
            proof_to_response_sqlite_path=proof_to_response_sqlite_path,
        )
        return _attach_typed_contract_trace_to_receipt(fallback_receipt, typed_contract_trace)
    if event_type in OBJECTIVE_ADVANCEMENT_EVENT_TYPES:
        return _route_objective_advancement(
            request,
            read_model_root=read_model_root,
            receipt_id=receipt_id,
            generated_at=generated_at,
            validation=validation,
        )
    if _selected_action_permits_objective_advancement(read_model_root, event_type, request):
        return _route_objective_advancement(
            request,
            read_model_root=read_model_root,
            receipt_id=receipt_id,
            generated_at=generated_at,
            validation=validation,
        )
    if event_type == "ask_why":
        return _route_ask_why(
            request,
            read_model_root=read_model_root,
            receipt_id=receipt_id,
            generated_at=generated_at,
            validation=validation,
        )
    if event_type == "open_lane":
        return _route_open_lane(
            request,
            read_model_root=read_model_root,
            receipt_id=receipt_id,
            generated_at=generated_at,
            validation=validation,
        )
    if event_type == "attach_proof":
        return _route_attach_proof(
            request,
            receipt_id=receipt_id,
            generated_at=generated_at,
            validation=validation,
            evidence_sqlite_path=evidence_sqlite_path,
            artifact_lineage_sqlite_path=artifact_lineage_sqlite_path,
        )
    if event_type in {"approve", "deny", "request_rework", "mark_informational"}:
        return _route_workroom_decision(
            request,
            read_model_root=read_model_root,
            export_root=export_root,
            bridge_root=bridge_root,
            workroom_wiki_path=workroom_wiki_path,
            receipt_id=receipt_id,
            generated_at=generated_at,
            validation=validation,
        )
    if event_type == "show_details":
        return _route_show_details(
            request,
            read_model_root=read_model_root,
            receipt_id=receipt_id,
            generated_at=generated_at,
            validation=validation,
        )
    if event_type in {"do_it", "chat_goal", "stage_plan", "continue", "stop_hold_cancel"}:
        return _route_action_payload(
            request,
            read_model_root=read_model_root,
            receipt_id=receipt_id,
            generated_at=generated_at,
            validation=validation,
        )
    return _blocked_receipt(
        request,
        receipt_id=receipt_id,
        generated_at=generated_at,
        validation=validation,
        route_status="UNKNOWN_EVENT_BLOCKED",
        headline="Controller event blocked",
        summary="Unknown controller events fail closed.",
        blocker="unknown_controller_event_type",
    )


def _proof_to_response_sqlite_path(router_sqlite_path: Path) -> Path:
    path = _rooted(router_sqlite_path)
    return path.parent / "proof_to_response_runtime.sqlite"


def _proof_to_response_wiki_path(router_wiki_path: Path) -> Path:
    path = _rooted(router_wiki_path)
    return path.parent / "Proof To Response Runtime.md"


def _looks_protected_controller_request(request: Mapping[str, Any], receipt: Mapping[str, Any]) -> bool:
    text = " ".join(
        str(value or "")
        for value in (
            request.get("operator_text"),
            request.get("selected_action_id"),
            request.get("selected_card_id"),
            receipt.get("route_ref"),
            receipt.get("route_status"),
            receipt.get("backend_route"),
        )
    ).lower()
    return (
        "protected" in text
        or "coupa" in text
        or "submit" in text
        or "ledger" in text and "payment" in text
        or str(receipt.get("route_status") or "") == "PROTECTED_ACTION_STAGED_OR_BLOCKED"
    )


def _selected_capital_hilton_payment_watch_context(request: Mapping[str, Any], receipt: Mapping[str, Any]) -> bool:
    refs = [
        str(request.get("selected_card_id") or ""),
        str(request.get("active_entity_ref") or ""),
        str(receipt.get("selected_card_id") or ""),
        str(receipt.get("active_entity_ref") or ""),
    ]
    for ref in (item.lower() for item in refs if item):
        if ref in {
            "dynamic_card.finance.capital_hilton.payment_watch",
            "dynamic_card.finance.capital_hilton.contextual_question",
        }:
            return True
        if "capital_hilton" in ref and "payment_watch" in ref and "approval_request" not in ref and "coupa_submit" not in ref:
            return True
        if "capital_hilton" in ref and "current_focus" in ref and "coupa_submit" not in ref:
            return True
    return False


def _selected_coupa_gate_context(request: Mapping[str, Any], receipt: Mapping[str, Any]) -> bool:
    refs = [
        str(request.get("selected_card_id") or ""),
        str(request.get("active_entity_ref") or ""),
        str(receipt.get("selected_card_id") or ""),
        str(receipt.get("active_entity_ref") or ""),
        str(request.get("selected_action_id") or ""),
        str(receipt.get("selected_action_id") or ""),
        str(receipt.get("route_ref") or ""),
    ]
    text = " ".join(refs).lower()
    return (
        "guardian_gate.coupa_submit" in text
        or "approval_request.coupa_submit" in text
        or "capital_hilton_coupa_submit_gate" in text
    )


def _asks_about_attach_proof_effect(request: Mapping[str, Any]) -> bool:
    text = " ".join(
        str(request.get(key) or "")
        for key in ("operator_text", "selected_action_id", "selected_card_id", "active_entity_ref")
    ).lower()
    if not text:
        return False
    has_proof_subject = (
        "attach proof" in text
        or "attach payment evidence" in text
        or "attach evidence" in text
        or "payment evidence" in text
        or "proof do" in text
        or "proof does" in text
    )
    asks_effect = (
        "what happens" in text
        or "what changes" in text
        or "what does" in text
        or "if i attach" in text
        or "if we attach" in text
        or "when i attach" in text
        or "does proof do" in text
    )
    return has_proof_subject and asks_effect


def _proof_to_response_scenario_id(request: Mapping[str, Any], receipt: Mapping[str, Any]) -> str:
    world = str(receipt.get("current_world_ref") or request.get("current_world_ref") or "").strip().lower()
    thread = str(receipt.get("current_thread_ref") or request.get("current_thread_ref") or "").strip().lower()
    event_type = str(receipt.get("controller_event_type") or request.get("controller_event_type") or "").strip()
    route_result = receipt.get("route_result") if isinstance(receipt.get("route_result"), Mapping) else {}
    routed_scenario_id = str(route_result.get("proof_to_response_scenario_id") or "").strip()
    if event_type == "chat_goal" and routed_scenario_id:
        return routed_scenario_id
    if event_type == "attach_proof" and world == "finance" and thread == "live_arts_md":
        return "finance_live_arts_payment_evidence"
    if world == "business_development" and thread == "capital_hilton":
        return "business_development_capital_hilton_followup"
    if world == "finance" and thread == "capital_hilton":
        if event_type == "ask_why" and _selected_capital_hilton_payment_watch_context(request, receipt):
            if _asks_about_attach_proof_effect(request):
                return "finance_capital_hilton_attach_proof_explanation"
            return "finance_capital_hilton_payment_watch"
        if _selected_coupa_gate_context(request, receipt):
            return "protected_coupa_ledger_email_request"
        if event_type in OBJECTIVE_ADVANCEMENT_EVENT_TYPES and _selected_capital_hilton_payment_watch_context(request, receipt):
            return "finance_capital_hilton_payment_watch"
        if _looks_protected_controller_request(request, receipt):
            return "protected_coupa_ledger_email_request"
        return "finance_capital_hilton_payment_watch"
    if _looks_protected_controller_request(request, receipt):
        return "protected_coupa_ledger_email_request"
    if world == "build" and "review" in str(receipt.get("backend_route") or ""):
        return "build_review_packet"
    if str(receipt.get("route_status") or "") == "NEEDS_LANE_CONTEXT":
        return "unknown_context"
    return ""


def _lm2_retry_backend(payload: Mapping[str, Any]) -> str:
    for key in ("structured_output_attempt", "invocation_result", "model_backend"):
        candidate = payload.get(key)
        if not isinstance(candidate, Mapping):
            continue
        runtime_ref = str(candidate.get("runtime_ref") or "ollama").strip() or "ollama"
        model_name = str(candidate.get("model_name") or "").strip()
        if model_name:
            return f"{runtime_ref}:{model_name}"
    return LM2_STRUCTURED_RETRY_BACKEND


def _lm2_retry_is_stale(payload: Mapping[str, Any], latest: Mapping[str, Any]) -> bool:
    stale_markers = (
        payload.get("expires_or_superseded_by"),
        payload.get("superseded_by"),
        latest.get("expires_or_superseded_by"),
        latest.get("superseded_by"),
    )
    if any(bool(marker) for marker in stale_markers):
        return True
    machine_proof = payload.get("machine_proof") if isinstance(payload.get("machine_proof"), Mapping) else {}
    latest_machine_proof = latest.get("machine_proof") if isinstance(latest.get("machine_proof"), Mapping) else {}
    return bool(
        payload.get("stale") is True
        or latest.get("stale") is True
        or machine_proof.get("stale_source_current_truth_allowed") is True
        or latest_machine_proof.get("stale_source_current_truth_allowed") is True
    )


def _matching_lm2_retry_publish_result(
    request: Mapping[str, Any],
    receipt: Mapping[str, Any],
    *,
    scenario_id: str,
    read_model_root: Path,
) -> dict[str, Any]:
    event_type = str(receipt.get("controller_event_type") or request.get("controller_event_type") or "").strip()
    if event_type != "chat_goal" or scenario_id != "finance_capital_hilton_payment_watch":
        return {}

    payload = _load_json(_rooted(read_model_root) / LM2_STRUCTURED_RETRY_READ_MODEL)
    if not payload or payload.get("status") != "LM2_ROOM_BACKED_WORKER_STRUCTURED_OUTPUT_RETRY_READY":
        return {}
    latest = payload.get("proof_to_response_latest") if isinstance(payload.get("proof_to_response_latest"), Mapping) else {}
    published = payload.get("published_response") if isinstance(payload.get("published_response"), Mapping) else {}
    latest_response = latest.get("latest_response") if isinstance(latest.get("latest_response"), Mapping) else {}
    source_response = dict(published or latest_response)
    if not source_response:
        return {}
    if str(source_response.get("candidate_source") or "") != proof_to_response_runtime.CANDIDATE_SOURCE_LM2_ROOM_BACKED_STRUCTURED_RETRY:
        return {}
    if str(source_response.get("verification_status") or "") not in {"publishable", "verified"}:
        return {}
    if _lm2_retry_is_stale(payload, latest):
        return {}

    source_context = source_response.get("source_context") if isinstance(source_response.get("source_context"), Mapping) else {}
    world_ref = str(source_context.get("world_ref") or latest.get("world_ref") or "").strip().lower()
    thread_ref = str(source_context.get("thread_ref") or latest.get("thread_ref") or "").strip().lower()
    objective_ref = str(source_context.get("objective_ref") or source_response.get("objective_ref") or "").strip().lower()
    if world_ref != "finance" or thread_ref != "capital_hilton" or "payment_watch" not in objective_ref:
        return {}

    source_response["candidate_source"] = proof_to_response_runtime.CANDIDATE_SOURCE_LM2_ROOM_BACKED_STRUCTURED_RETRY
    source_response["selected_model_backend"] = _lm2_retry_backend(payload)
    source_response["model_call_performed"] = False
    source_response["source_lm2_result_ref"] = LM2_STRUCTURED_RETRY_REF
    source_response["source_response_path"] = LM2_STRUCTURED_RETRY_REF
    return {
        "scenario_id": scenario_id,
        "candidate_source": proof_to_response_runtime.CANDIDATE_SOURCE_LM2_ROOM_BACKED_STRUCTURED_RETRY,
        "proof_bundle": {},
        "candidate_response": {},
        "verifier_result": {
            "status": "VERIFIED_EXISTING_LM2_PROOF_RESPONSE_REUSED",
            "verification_errors": [],
        },
        "published_response": source_response,
        "receipt": {
            "receipt_id": str(latest.get("latest_receipt_ref") or payload.get("latest_receipt_ref") or "lm2_structured_output_retry:published_response_hash_receipt"),
            "receipt_type": "proof_to_response_reused_existing_lm2_result",
            "candidate_source": proof_to_response_runtime.CANDIDATE_SOURCE_LM2_ROOM_BACKED_STRUCTURED_RETRY,
            "source_lm2_result_ref": LM2_STRUCTURED_RETRY_REF,
            "model_call_performed": False,
            "approval_consumed": False,
        },
        "source_lm2_result_ref": LM2_STRUCTURED_RETRY_REF,
        "source_response_path": LM2_STRUCTURED_RETRY_REF,
        "reused_existing_lm2_result": True,
    }


def _attach_proof_to_response(
    receipt: dict[str, Any],
    request: Mapping[str, Any],
    *,
    read_model_root: Path,
    export_root: Path,
    bridge_root: Path | None,
    wiki_path: Path,
    router_sqlite_path: Path,
    proof_to_response_sqlite_path: Path | None,
    generated_at: str,
) -> None:
    runtime_sqlite_path = proof_to_response_sqlite_path or _proof_to_response_sqlite_path(router_sqlite_path)
    source_request_id = str(receipt.get("request_id") or request.get("request_id") or "")
    controller_event_type = str(receipt.get("controller_event_type") or request.get("controller_event_type") or "")
    selected_card_id = str(receipt.get("selected_card_id") or request.get("selected_card_id") or "")
    selected_action_id = str(receipt.get("selected_action_id") or request.get("selected_action_id") or "")
    world_ref = str(receipt.get("current_world_ref") or request.get("current_world_ref") or "")
    thread_ref = str(receipt.get("current_thread_ref") or request.get("current_thread_ref") or "")
    if not receipt.get("dynamic_card_response"):
        receipt["proof_to_response_status"] = "unavailable:no_dynamic_card_response"
        return
    route_result = receipt.get("route_result") if isinstance(receipt.get("route_result"), Mapping) else {}
    backend_route = str(route_result.get("backend_route") or "")
    if backend_route.startswith("capability_authority_loop.") or backend_route.startswith("make_it_so_objective_loop."):
        receipt["primary_response_kind"] = "make_it_so_objective" if backend_route.startswith("make_it_so_objective_loop.") else "capability_authority"
        receipt["proof_to_response_status"] = "not_applicable:structured_authority_route"
        receipt["proof_to_response_unavailable_reason"] = "capability_gap_or_make_it_so_route_is_structured_route_result"
        receipt["dynamic_card_role"] = "primary_display"
        receipt["details_collapsed"] = True
        receipt["machine_proof"]["proof_to_response_bypassed_for_capability_authority"] = True
        receipt["machine_proof"]["proof_to_response_primary_emitted"] = False
        return
    scenario_id = _proof_to_response_scenario_id(request, receipt)
    if not scenario_id:
        export_result = proof_to_response_runtime.export_unavailable_controller_response(
            source_request_id=source_request_id,
            controller_event_type=controller_event_type,
            world_ref=world_ref,
            thread_ref=thread_ref,
            selected_card_id=selected_card_id,
            selected_action_id=selected_action_id,
            unavailable_reason="no_supported_proof_to_response_scenario_for_controller_route",
            read_model_root=read_model_root,
            export_root=export_root,
            bridge_export_root=bridge_root,
            wiki_path=_proof_to_response_wiki_path(wiki_path),
            sqlite_path=runtime_sqlite_path,
            generated_at=generated_at,
        )
        receipt["proof_to_response_status"] = "unavailable:no_supported_scenario"
        receipt["proof_to_response_unavailable_reason"] = "no_supported_proof_to_response_scenario_for_controller_route"
        receipt["proof_to_response_runtime_export"] = export_result
        return
    candidate = request.get("proof_to_response_candidate")
    if not isinstance(candidate, Mapping):
        candidate = None
    publish_result = _matching_lm2_retry_publish_result(
        request,
        receipt,
        scenario_id=scenario_id,
        read_model_root=read_model_root,
    )
    lm2_reused = bool(publish_result.get("reused_existing_lm2_result"))
    source_response_path = str(publish_result.get("source_response_path") or "")
    if not publish_result:
        publish_result = proof_to_response_runtime.publish_response(
            scenario_id,
            candidate_response=candidate,
            candidate_source=proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT,
            generated_at=generated_at,
            sqlite_path=runtime_sqlite_path,
            read_model_root=read_model_root,
        )
    primary_response = proof_to_response_runtime.scope_controller_response(
        publish_result.get("published_response") if isinstance(publish_result.get("published_response"), Mapping) else {},
        source_request_id=source_request_id,
        controller_event_type=controller_event_type,
        selected_card_id=selected_card_id,
        selected_action_id=selected_action_id,
        source_response_path=source_response_path,
        generated_at=generated_at,
    )
    resolved_intent_class = str(route_result.get("resolved_intent_class") or route_result.get("conversation_intent_class") or "")
    resolved_intent_route = str(route_result.get("resolved_intent_route") or route_result.get("proof_to_response_scenario_id") or scenario_id)
    intent_source = str(route_result.get("intent_source") or ("backend_router" if resolved_intent_class else ""))
    intent_confidence = route_result.get("intent_confidence")
    if resolved_intent_class:
        primary_response["resolved_intent_class"] = resolved_intent_class
        primary_response["resolved_intent_route"] = resolved_intent_route
        primary_response["intent_source"] = intent_source
        primary_response["intent_confidence"] = intent_confidence if isinstance(intent_confidence, (int, float)) else 1.0
        primary_response["response_content_hash"] = proof_to_response_runtime._content_hash(
            {k: v for k, v in primary_response.items() if k != "response_content_hash"}
        )
    scoped_publish_result = dict(publish_result)
    scoped_publish_result["published_response"] = primary_response
    export_result = proof_to_response_runtime.export_controller_integration_response(
        scoped_publish_result,
        read_model_root=read_model_root,
        export_root=export_root,
        bridge_export_root=bridge_root,
        wiki_path=_proof_to_response_wiki_path(wiki_path),
        sqlite_path=runtime_sqlite_path,
        generated_at=generated_at,
    )
    runtime_receipt = dict(publish_result.get("receipt") or {})
    receipt["primary_response_kind"] = "proof_to_response"
    receipt["proof_to_response"] = primary_response
    receipt["proof_to_response_receipt"] = runtime_receipt
    receipt["proof_to_response_runtime_export"] = export_result
    receipt["proof_to_response_scenario_id"] = scenario_id
    if resolved_intent_class:
        receipt["resolved_intent_class"] = resolved_intent_class
        receipt["resolved_intent_route"] = resolved_intent_route
        receipt["intent_source"] = intent_source
        receipt["intent_confidence"] = primary_response.get("intent_confidence")
    receipt["proof_to_response_candidate_source"] = str(
        publish_result.get("candidate_source")
        or primary_response.get("candidate_source")
        or proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT
    )
    receipt["candidate_source"] = receipt["proof_to_response_candidate_source"]
    receipt["selected_model_backend"] = str(primary_response.get("selected_model_backend") or "")
    receipt["model_call_performed"] = bool(primary_response.get("model_call_performed") or False)
    receipt["proof_to_response_status"] = str(primary_response.get("verification_status") or "unavailable")
    receipt["dynamic_card_role"] = "support_display"
    receipt["details_collapsed"] = True
    receipt.setdefault("proof_refs", [])
    for ref in primary_response.get("proof_refs") or []:
        if ref and ref not in receipt["proof_refs"]:
            receipt["proof_refs"].append(ref)
    receipt["machine_proof"]["proof_to_response_primary_emitted"] = bool(primary_response)
    receipt["machine_proof"]["proof_to_response_verification_status"] = str(primary_response.get("verification_status") or "")
    receipt["machine_proof"]["proof_to_response_candidate_source"] = receipt["proof_to_response_candidate_source"]
    receipt["machine_proof"]["resolved_intent_class"] = resolved_intent_class
    receipt["machine_proof"]["resolved_intent_route"] = resolved_intent_route
    receipt["machine_proof"]["intent_source"] = intent_source
    receipt["machine_proof"]["lm2_proof_response_reused"] = lm2_reused
    receipt["machine_proof"]["source_lm2_result_ref"] = str(publish_result.get("source_lm2_result_ref") or "")
    receipt["machine_proof"]["model_invoked"] = False
    receipt["machine_proof"]["approval_consumed"] = False
    receipt["machine_proof"]["live_lm_invoked"] = False
    receipt["machine_proof"]["local_model_runtime_connected"] = False
    receipt["machine_proof"]["details_collapsed"] = primary_response.get("details_collapsed") is not False
    receipt["machine_proof"]["dynamic_card_role"] = "support_display"


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS controller_event_receipts (
          receipt_id TEXT PRIMARY KEY,
          request_id TEXT NOT NULL,
          controller_event_type TEXT NOT NULL,
          route_status TEXT NOT NULL,
          raw_internal_status TEXT NOT NULL,
          backend_route TEXT NOT NULL,
          route_ref TEXT NOT NULL,
          route_receipt_ref TEXT NOT NULL,
          current_world_ref TEXT NOT NULL,
          current_thread_ref TEXT NOT NULL,
          active_entity_ref TEXT NOT NULL,
          selected_card_id TEXT NOT NULL,
          selected_action_id TEXT NOT NULL,
          authority_requested_json TEXT NOT NULL,
          authority_granted_json TEXT NOT NULL,
          dynamic_card_json TEXT NOT NULL,
          proof_refs_json TEXT NOT NULL,
          blockers_json TEXT NOT NULL,
          email_send_performed INTEGER NOT NULL,
          coupa_access_performed INTEGER NOT NULL,
          browser_access_performed INTEGER NOT NULL,
          ledger_mutation_performed INTEGER NOT NULL,
          workbook_mutation_performed INTEGER NOT NULL,
          paid_marking_performed INTEGER NOT NULL,
          submit_performed INTEGER NOT NULL,
          business_action_performed INTEGER NOT NULL,
          external_llm_invoked INTEGER NOT NULL,
          local_model_runtime_connected INTEGER NOT NULL,
          generated_at TEXT NOT NULL
        )
        """
    )


def _insert_receipt(conn: sqlite3.Connection, receipt: Mapping[str, Any]) -> None:
    proof = receipt.get("machine_proof") if isinstance(receipt.get("machine_proof"), Mapping) else {}
    conn.execute(
        """
        INSERT OR REPLACE INTO controller_event_receipts (
          receipt_id, request_id, controller_event_type, route_status,
          raw_internal_status, backend_route, route_ref, route_receipt_ref,
          current_world_ref, current_thread_ref, active_entity_ref,
          selected_card_id, selected_action_id, authority_requested_json,
          authority_granted_json, dynamic_card_json, proof_refs_json,
          blockers_json, email_send_performed, coupa_access_performed,
          browser_access_performed, ledger_mutation_performed,
          workbook_mutation_performed, paid_marking_performed,
          submit_performed, business_action_performed, external_llm_invoked,
          local_model_runtime_connected, generated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(receipt.get("receipt_id") or ""),
            str(receipt.get("request_id") or ""),
            str(receipt.get("controller_event_type") or ""),
            str(receipt.get("route_status") or ""),
            str(receipt.get("raw_internal_status") or ""),
            str(receipt.get("backend_route") or ""),
            str(receipt.get("route_ref") or ""),
            str(receipt.get("route_receipt_ref") or ""),
            str(receipt.get("current_world_ref") or ""),
            str(receipt.get("current_thread_ref") or ""),
            str(receipt.get("active_entity_ref") or ""),
            str(receipt.get("selected_card_id") or ""),
            str(receipt.get("selected_action_id") or ""),
            stable_json(receipt.get("authority_requested") or []),
            stable_json(receipt.get("authority_granted") or []),
            stable_json(receipt.get("dynamic_card_response") or {}),
            stable_json(receipt.get("proof_refs") or []),
            stable_json(receipt.get("blockers") or []),
            1 if proof.get("email_send_performed") is True else 0,
            1 if proof.get("coupa_access_performed") is True else 0,
            1 if proof.get("browser_access_performed") is True else 0,
            1 if proof.get("ledger_mutation_performed") is True else 0,
            1 if proof.get("workbook_mutation_performed") is True else 0,
            1 if proof.get("paid_marking_performed") is True else 0,
            1 if proof.get("submit_performed") is True else 0,
            1 if proof.get("business_action_performed") is True else 0,
            1 if proof.get("external_llm_invoked") is True else 0,
            1 if proof.get("local_model_runtime_connected") is True else 0,
            str(receipt.get("generated_at") or ""),
        ),
    )


def record_router_receipt(
    receipt: Mapping[str, Any],
    *,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
) -> None:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        _init_schema(conn)
        _insert_receipt(conn, receipt)
        conn.commit()
    finally:
        conn.close()


def _latest_receipts(sqlite_path: Path, *, limit: int = 20) -> list[dict[str, Any]]:
    path = _rooted(sqlite_path)
    if not path.exists():
        return []
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        _init_schema(conn)
        rows = conn.execute(
            """
            SELECT receipt_id, request_id, controller_event_type, route_status,
                   raw_internal_status, backend_route, route_ref, route_receipt_ref,
                   current_world_ref, current_thread_ref, selected_card_id,
                   selected_action_id, dynamic_card_json, proof_refs_json,
                   blockers_json, generated_at
            FROM controller_event_receipts
            ORDER BY generated_at DESC, receipt_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    receipts: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        for key in ("dynamic_card_json", "proof_refs_json", "blockers_json"):
            try:
                item[key.replace("_json", "")] = json.loads(str(item.pop(key) or "[]"))
            except json.JSONDecodeError:
                item[key.replace("_json", "")] = [] if key != "dynamic_card_json" else {}
        receipts.append(item)
    return receipts


def route_controller_event(
    raw_request: Mapping[str, Any],
    *,
    source_request_filename: str = "",
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    workroom_wiki_path: Path | None = None,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    evidence_sqlite_path: Path = evidence_intake.DEFAULT_SQLITE_PATH,
    artifact_lineage_sqlite_path: Path | None = evidence_intake.DEFAULT_ARTIFACT_LINEAGE_SQLITE_PATH,
    proof_to_response_sqlite_path: Path | None = None,
    generated_at: str | None = None,
    export_read_models: bool = True,
    first_touch_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    request = normalize_controller_event_request(raw_request, read_model_root=read_model_root)
    validation = _validate_controller_event(request)
    receipt_id = "operator_controller_event_router:" + _short_hash(
        _request_id(request),
        source_request_filename,
        str(request.get("controller_event_type") or ""),
        str(request.get("selected_action_id") or ""),
        str(request.get("artifact_ref") or ""),
        generated_at,
    )

    if not validation["verified"]:
        context_missing = any(
            blocker in validation["blockers"]
            for blocker in ("current_world_ref_missing", "current_thread_ref_missing")
        )
        route_status = "NEEDS_LANE_CONTEXT" if context_missing else (
            "NEEDS_VERIFICATION" if "verified_operator_envelope_required" in validation["blockers"] else "REJECTED"
        )
        headline = "Needs lane context" if context_missing else "Needs verification"
        summary = (
            "I need the Build lane or review packet thread before I can record this review decision."
            if context_missing
            else "Controller events require a verified first-class operator envelope and a false authority boundary."
        )
        blocker = "current_thread_ref_missing" if context_missing else "verified_operator_envelope_required"
        receipt = _blocked_receipt(
            request,
            receipt_id=receipt_id,
            generated_at=generated_at,
            validation=validation,
            route_status=route_status,
            headline=headline,
            summary=summary,
            blocker=blocker,
        )
    elif str(request.get("controller_event_type") or "") not in EVENT_TYPES:
        receipt = _blocked_receipt(
            request,
            receipt_id=receipt_id,
            generated_at=generated_at,
            validation=validation,
            route_status="UNKNOWN_EVENT_BLOCKED",
            headline="Controller event blocked",
            summary="Unknown controller events fail closed.",
            blocker="unknown_controller_event_type",
        )
    else:
        event_type = str(request.get("controller_event_type") or "")
        if event_type != global_run_mode_context.RUN_MODE_SET_EVENT_TYPE:
            run_mode_context = global_run_mode_context.resolve_run_mode_context(
                sqlite_path,
                request,
                generated_at=generated_at,
            )
            request["run_mode_context"] = run_mode_context
            if run_mode_context.get("resolution_status") == "rejected":
                blockers = list(run_mode_context.get("blockers") or [])
                receipt = _blocked_receipt(
                    request,
                    receipt_id=receipt_id,
                    generated_at=generated_at,
                    validation=validation,
                    route_status="RUN_MODE_CONTEXT_REJECTED",
                    headline="Run mode blocked",
                    summary="This request conflicts with the backend run-mode state or contains a test-only marker in production.",
                    blocker=blockers[0] if blockers else "run_mode_context_rejected",
                )
            else:
                receipt = _route_event(
                    request,
                    read_model_root=read_model_root,
                    export_root=export_root,
                    bridge_root=bridge_root,
                    workroom_wiki_path=workroom_wiki_path,
                    receipt_id=receipt_id,
                    generated_at=generated_at,
                    validation=validation,
                    evidence_sqlite_path=evidence_sqlite_path,
                    artifact_lineage_sqlite_path=artifact_lineage_sqlite_path,
                    proof_to_response_sqlite_path=proof_to_response_sqlite_path,
                    router_sqlite_path=sqlite_path,
                    first_touch_receipt=first_touch_receipt,
                )
        else:
            receipt = _route_event(
                request,
                read_model_root=read_model_root,
                export_root=export_root,
                bridge_root=bridge_root,
                workroom_wiki_path=workroom_wiki_path,
                receipt_id=receipt_id,
                generated_at=generated_at,
                validation=validation,
                evidence_sqlite_path=evidence_sqlite_path,
                artifact_lineage_sqlite_path=artifact_lineage_sqlite_path,
                proof_to_response_sqlite_path=proof_to_response_sqlite_path,
                router_sqlite_path=sqlite_path,
                first_touch_receipt=first_touch_receipt,
            )

    receipt["source_request_filename"] = source_request_filename
    _attach_proof_to_response(
        receipt,
        request,
        read_model_root=read_model_root,
        export_root=export_root,
        bridge_root=bridge_root,
        wiki_path=wiki_path,
        router_sqlite_path=sqlite_path,
        proof_to_response_sqlite_path=proof_to_response_sqlite_path,
        generated_at=generated_at,
    )
    receipt["machine_proof"]["unsafe_true_grants"] = unsafe_true_grants(receipt)
    receipt["machine_proof"]["unsafe_true_grants_absent"] = not receipt["machine_proof"]["unsafe_true_grants"]
    record_router_receipt(receipt, sqlite_path=sqlite_path)
    if export_read_models:
        export_operator_controller_event_router(
            latest_receipt=receipt,
            read_model_root=read_model_root,
            export_root=export_root,
            bridge_root=bridge_root,
            wiki_path=wiki_path,
            sqlite_path=sqlite_path,
            generated_at=generated_at,
        )
    return receipt


def build_contract_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _precondition_rows(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    route_table = [
        {
            "controller_event_type": "ask_why",
            "backend_route": "system_question_answer.contextual_answer",
            "effect": "contextual answer only; no package staging unless explicitly required",
        },
        {
            "controller_event_type": "open_lane",
            "backend_route": "operator_action_payloads.navigate",
            "effect": "navigation card/action only",
        },
        {
            "controller_event_type": "attach_proof",
            "backend_route": "evidence_intake.record_candidate_evidence",
            "effect": "candidate evidence only; no paid or ledger mutation",
        },
        {
            "controller_event_type": "advance_objective|continue|stage_plan",
            "backend_route": "objective_advancement_protocol.advance_objective",
            "effect": "advance to next safe internal state or explain missing proof/approval; no protected final action",
        },
        {
            "controller_event_type": "approve|deny",
            "backend_route": "workroom_review_decision_consumer or approval_request_queue.stage_only",
            "effect": "decision/staging receipt only; no business execution",
        },
        {
            "controller_event_type": "request_rework|mark_informational",
            "backend_route": "workroom_review_decision_consumer.record_decision_only",
            "effect": "review decision receipt only; no merge or push",
        },
        {
            "controller_event_type": "do_it",
            "backend_route": "operator_action_payloads deterministic safe route or objective_advancement_protocol when selected payload permits",
            "effect": "safe internal route, objective advancement, or protected action staged/blocked",
        },
        {
            "controller_event_type": "show_details",
            "backend_route": "dynamic_card_packet.proof_drawer",
            "effect": "proof/details card only",
        },
        {
            "controller_event_type": "set_run_mode",
            "backend_route": "global_run_mode_context.handle_run_mode_set_request",
            "effect": "backend-persisted run-mode state and transition receipt only; no business execution",
        },
    ]
    payload = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "read_model_id": CONTRACT_READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "request_type": REQUEST_TYPE,
        "purpose": "Map verified generic Mission Control controller events into existing safe OpenClaw routes.",
        "controller_event_types": list(EVENT_TYPES),
        "rules": [
            "Verified first-class operator envelope required.",
            "Mac compact controller dispatcher envelopes are normalized from inline envelope, current_context, top-level verified identity fields, and operator_envelope_ref before validation.",
            "Incoming authority_granted, gate_decision_ref, and approval_receipt_ref are backend-only and rejected or ignored.",
            "authority_requested does not imply authority_granted.",
            "Unknown events fail closed.",
            "Missing deterministic action payload returns Needs verification.",
            "Every route emits a receipt/ref and dynamic card response.",
            "Objective advancement means next safe state or exact blocker; it never executes protected final actions.",
            "No live external provider action and no business execution.",
            "Protected actions are staged for approval/gate review or blocked; never directly sent, submitted, posted, marked paid, merged, or pushed.",
        ],
        "route_table": route_table,
        "examples": [
            {
                "name": "Finance / Capital Hilton advance_objective",
                "expected": "payment evidence needed with attach_proof suggestion; no ledger or paid mutation",
            },
            {
                "name": "Finance / Capital Hilton ask_why",
                "expected": "payment-watch explanation",
            },
            {
                "name": "Finance / Live Arts MD attach_proof",
                "expected": "evidence intake records payment-processing proof while ledger remains untouched",
            },
            {
                "name": "Build review packet mark_informational",
                "expected": "workroom review decision recorded; no merge or push",
            },
            {
                "name": "Business Development follow-up do_it",
                "expected": "draft/stage only; no send",
            },
            {
                "name": "Protected Coupa submit do_it",
                "expected": "stage approval/gate or block; no Coupa/browser submit",
            },
        ],
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "contract_only": True,
            "verified_operator_envelope_required": True,
            "incoming_authority_granted_accepted": False,
            "authority_requested_does_not_imply_authority_granted": True,
            "external_llm_invoked": False,
            "external_provider_connected": False,
            "local_model_runtime_connected": False,
            "business_action_performed": False,
        },
    }
    payload["machine_proof"]["unsafe_true_grants"] = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants_absent"] = not payload["machine_proof"]["unsafe_true_grants"]
    return payload


def build_status_read_model(
    *,
    latest_receipt: Mapping[str, Any] | None = None,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _precondition_rows(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    history = _latest_receipts(sqlite_path, limit=20)
    latest = dict(latest_receipt) if isinstance(latest_receipt, Mapping) else (history[0] if history else None)
    routed_count = sum(1 for item in history if str(item.get("raw_internal_status") or "") == RESPONSE_READY)
    blocked_count = sum(1 for item in history if str(item.get("raw_internal_status") or "") != RESPONSE_READY)
    status = READY_STATUS if preconditions_ready else NOT_READY_STATUS
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": STATUS_READ_MODEL_ID,
        "status": status,
        "generated_at": generated_at,
        "request_type": REQUEST_TYPE,
        "live_route_status": "OPERATOR_CONTROLLER_EVENT_LIVE_ROUTE_READY" if preconditions_ready else "OPERATOR_CONTROLLER_EVENT_LIVE_ROUTE_NOT_READY",
        "envelope_normalization_status": "CONTROLLER_EVENT_ENVELOPE_NORMALIZATION_READY"
        if preconditions_ready
        else "CONTROLLER_EVENT_ENVELOPE_NORMALIZATION_NOT_READY",
        "latest_receipt": latest,
        "recent_receipts": history,
        "recent_receipt_count": len(history),
        "recent_routed_count": routed_count,
        "recent_blocked_count": blocked_count,
        "sqlite_path": str(_rooted(sqlite_path)),
        "bridge_contract_ref": f"/mnt/e/openclaw/generated/read_models/{CONTRACT_JSON_EXPORT_NAME}",
        "bridge_status_ref": f"/mnt/e/openclaw/generated/read_models/{STATUS_JSON_EXPORT_NAME}",
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "router_ready": status == READY_STATUS,
            "live_route_consumes_operator_controller_event_request_v0": preconditions_ready,
            "mac_compact_controller_event_envelope_normalization_supported": True,
            "objective_advancement_route_supported": True,
            "latest_dynamic_card_response_emitted": bool(latest and latest.get("dynamic_card_response")),
            "authority_requested_does_not_imply_authority_granted": True,
            "incoming_authority_granted_accepted": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "portal_submit_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "business_action_performed": False,
            "external_llm_invoked": False,
            "external_provider_connected": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
            "git_push_performed": False,
        },
    }
    payload["machine_proof"]["unsafe_true_grants"] = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants_absent"] = not payload["machine_proof"]["unsafe_true_grants"]
    return payload


def build_wiki(contract: Mapping[str, Any], status: Mapping[str, Any]) -> str:
    latest = status.get("latest_receipt") if isinstance(status.get("latest_receipt"), Mapping) else {}
    lines = [
        "# Operator Controller Event Router",
        "",
        f"Status: `{status.get('status', NOT_READY_STATUS)}`",
        "",
        "This router maps verified generic Mission Control controller events into existing safe backend routes.",
        "It is a controller layer, not a business executor.",
        "",
        "## Rules",
        "",
    ]
    for rule in contract.get("rules", []):
        lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "## Routes",
            "",
        ]
    )
    for route in contract.get("route_table", []):
        lines.append(
            f"- `{route.get('controller_event_type', '')}` -> `{route.get('backend_route', '')}`: {route.get('effect', '')}"
        )
    lines.extend(
        [
            "",
            "## Latest Delivery Result",
            "",
            "- Machine evidence: retained below deck.",
            f"- Event: `{latest.get('controller_event_type', '')}`",
            f"- Status: `{latest.get('route_status', '')}`",
            f"- Backend route: `{latest.get('backend_route', '')}`",
            f"- Route ref: `{latest.get('route_ref', '')}`",
            "",
            "## Safety Boundary",
            "",
            "- No email/Gmail/browser/Coupa/portal submit.",
            "- No ledger or workbook mutation.",
            "- No PDF export or paid marking.",
            "- No merge, push, worker spawn, external LLM, or local model runtime.",
            "- Incoming `authority_requested` is only a request; incoming `authority_granted` is rejected or ignored.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_operator_controller_event_router(
    *,
    latest_receipt: Mapping[str, Any] | None = None,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    generated_at = generated_at or utc_now()
    contract = build_contract_read_model(read_model_root=read_model_root, generated_at=generated_at)
    status = build_status_read_model(
        latest_receipt=latest_receipt,
        read_model_root=read_model_root,
        sqlite_path=sqlite_path,
        generated_at=generated_at,
    )
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    contract_path = export_root / CONTRACT_JSON_EXPORT_NAME
    status_path = export_root / STATUS_JSON_EXPORT_NAME
    contract_path.write_text(stable_json(contract), encoding="utf-8")
    status_path.write_text(stable_json(status), encoding="utf-8")

    bridge_contract_path = ""
    bridge_status_path = ""
    if bridge_root is not None:
        bridge_root = _rooted(bridge_root)
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_contract = bridge_root / CONTRACT_JSON_EXPORT_NAME
        bridge_status = bridge_root / STATUS_JSON_EXPORT_NAME
        shutil.copy2(contract_path, bridge_contract)
        shutil.copy2(status_path, bridge_status)
        bridge_contract_path = bridge_contract.as_posix()
        bridge_status_path = bridge_status.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(contract, status), encoding="utf-8")
    return {
        "status": str(status["status"]),
        "contract_read_model_path": contract_path.as_posix(),
        "status_read_model_path": status_path.as_posix(),
        "bridge_contract_read_model_path": bridge_contract_path,
        "bridge_status_read_model_path": bridge_status_path,
        "wiki_path": wiki_path.as_posix(),
        "sqlite_path": str(_rooted(sqlite_path)),
    }


def _load_request_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("request file must contain a JSON object")
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export or consume Operator Controller Event Router V0.")
    parser.add_argument("--request-file", help="Optional OPERATOR_CONTROLLER_EVENT_REQUEST_V0 JSON file to route.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--workroom-wiki-path")
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--evidence-sqlite-path", default=str(evidence_intake.DEFAULT_SQLITE_PATH))
    parser.add_argument("--artifact-lineage-sqlite-path", default=str(evidence_intake.DEFAULT_ARTIFACT_LINEAGE_SQLITE_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    bridge_root = None if args.no_bridge else Path(args.bridge_root)
    if args.request_file:
        request_path = Path(args.request_file)
        receipt = route_controller_event(
            _load_request_file(request_path),
            source_request_filename=request_path.name,
            read_model_root=Path(args.read_model_root),
            export_root=Path(args.export_root),
            bridge_root=bridge_root,
            wiki_path=Path(args.wiki_path),
            workroom_wiki_path=Path(args.workroom_wiki_path) if args.workroom_wiki_path else None,
            sqlite_path=Path(args.sqlite_path),
            evidence_sqlite_path=Path(args.evidence_sqlite_path),
            artifact_lineage_sqlite_path=Path(args.artifact_lineage_sqlite_path),
            generated_at=args.generated_at,
        )
        print(stable_json(receipt), end="")
        return 0 if receipt.get("raw_internal_status") == RESPONSE_READY else 2
    result = export_operator_controller_event_router(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=bridge_root,
        wiki_path=Path(args.wiki_path),
        sqlite_path=Path(args.sqlite_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
