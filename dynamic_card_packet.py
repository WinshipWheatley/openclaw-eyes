"""Dynamic Card Packet V1.

Backend-generated operator card packets for Mission Control. This module
renders local read-model state into compact card contracts. It does not build
live LM1/LM2, invoke models, spawn workers, connect providers, send email, open
browser/Gmail/Coupa, mutate ledgers or workbooks, export PDFs, submit portals,
mark paid/sent, push git, or grant authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import dynamic_card_lifecycle_policy as lifecycle_policy


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Dynamic Card Packet.md")

SCHEMA_VERSION = "dynamic_card_packet_v1"
CONTRACT_SCHEMA_VERSION = "dynamic_card_packet_contract_v1"
CONTRACT_READ_MODEL_ID = "dynamic_card_packet_contract"
LATEST_READ_MODEL_ID = "dynamic_card_packet_latest"
CONTRACT_JSON_EXPORT_NAME = f"{CONTRACT_READ_MODEL_ID}.json"
LATEST_JSON_EXPORT_NAME = f"{LATEST_READ_MODEL_ID}.json"
READY_STATUS = "DYNAMIC_CARD_PACKET_READY"
NOT_READY_STATUS = "DYNAMIC_CARD_PACKET_NOT_READY"
FIRST_CLASS_OPERATOR_ENVELOPE_CONTRACT_REF = "generated/read_models/first_class_operator_envelope_contract.json"
FIRST_CLASS_OPERATOR_ENVELOPE_STATUS_REF = "generated/read_models/first_class_operator_envelope_status.json"
LIFECYCLE_POLICY_REF = "generated/read_models/dynamic_card_lifecycle_policy.json"

CARD_TYPES = (
    "answer",
    "status",
    "next_action",
    "approval",
    "review_packet",
    "workflow_plan",
    "gate",
    "memory",
    "artifact",
    "evidence_intake",
    "payment_watch",
    "question",
    "workbook_registration",
)

CARD_FAMILIES = (
    "current_focus_card",
    "answer_card",
    "payment_watch_card",
    "evidence_intake_receipt_card",
    "approval_request_card",
    "review_packet_card",
    "workflow_composer_plan_card",
    "gate_lock_card",
    "memory_candidate_card",
    "artifact_proof_card",
    "contextual_what_should_i_do_card",
    "completed_historical_receipt_card",
)

ACTION_SLOTS = ("primary", "secondary", "detail", "dismiss", "danger_disabled")

REQUIRED_PACKET_FIELDS = (
    "schema_version",
    "packet_id",
    "generated_at",
    "surface_context",
    "source_request_id",
    "packet_source_read_model_refs",
    "packet_content_hash",
    "cards",
)

REQUIRED_CARD_FIELDS = (
    "card_id",
    "card_family",
    "card_type",
    "world_ref",
    "thread_ref",
    "entity_refs",
    "object_refs",
    "speaker_ref",
    "headline",
    "plain_summary",
    "supporting_lines",
    "status_label",
    "tone",
    "trust_state",
    "confidence_class",
    "confidence_score",
    "freshness_state",
    "lifecycle_state",
    "operator_attention_required",
    "visible_by_default",
    "collapse_when_resolved",
    "source_read_model_refs",
    "source_statuses",
    "source_generated_at",
    "source_content_hash",
    "action_slots",
    "proof",
    "accessibility_text",
    "device_render_hints",
)

REQUIRED_ACTION_SLOT_FIELDS = (
    "action_payload_ref",
    "controller_event_type",
    "label",
    "enabled",
    "disabled_reason",
    "requires_operator_envelope",
    "receipt_required",
    "authority_boundary",
    "proof_refs",
)

REQUIRED_PROOF_FIELDS = (
    "receipt_refs",
    "artifact_refs",
    "hash_refs",
    "sqlite_refs",
    "read_model_refs",
    "request_refs",
    "response_refs",
    "redacted_summary",
    "sensitive_detail_policy",
    "developer_proof_only",
)

SPEAKER_REFS = ("cassandra", "chief", "hermes", "guardian", "niles", "openclaw")
TONES = ("calm", "success", "warning", "blocked", "neutral")
TRUST_STATES = (
    "trusted_current",
    "preview_only",
    "future_gated",
    "stale_needs_proof",
    "operator_reported",
    "candidate_evidence",
    "unknown",
)
ACTION_TYPES = (
    "navigate",
    "stage_package_request",
    "system_question",
    "inspect_proof",
    "review_decision",
    "workbook_registration",
    "explain_gate",
    "none",
)

SOURCE_FILENAMES = {
    "operator_runtime_chain_current_state_audit": "operator_runtime_chain_current_state_audit.json",
    "operator_action_payloads": "operator_action_payloads.json",
    "operator_controller_design_brief": "operator_controller_design_brief.json",
    "operator_controller_protocol": "operator_controller_protocol.json",
    "dynamic_card_lifecycle_policy": "dynamic_card_lifecycle_policy.json",
    "lm_bounded_operator_orchestration": "lm_bounded_operator_orchestration_latest.json",
    "operator_next_decision": "operator_next_decision.json",
    "capital_hilton_invoice_operator_run_status": "capital_hilton_invoice_operator_run_status.json",
    "capital_hilton_business_development_proposal": "capital_hilton_business_development_proposal.json",
    "st_annes_work_log_review_surface": "st_annes_work_log_review_surface.json",
    "workroom_review_packet_index": "workroom_review_packet_index.json",
    "workroom_review_decision_status": "workroom_review_decision_status.json",
    "system_question_answer": "system_question_answer_contract.json",
    "client_invoice_workbook_registry": "client_invoice_workbook_registry.json",
    "package_event_index": "package_event_index.json",
    "chief_check_engine_diagnostic_package": "chief_check_engine_diagnostic_package.json",
    "evidence_intake": "evidence_intake_status.json",
    "evidence_confidence_scoring": "evidence_confidence_scoring.json",
    "gate_decision_ledger": "gate_decision_ledger.json",
    "workroom_wip_limits": "workroom_wip_limits.json",
    "first_class_operator_envelope_contract": "first_class_operator_envelope_contract.json",
    "first_class_operator_envelope_status": "first_class_operator_envelope_status.json",
}

PRECONDITIONS = {
    "operator_runtime_chain_current_state_audit": {
        "filename": "operator_runtime_chain_current_state_audit.json",
        "required_status": "OPERATOR_RUNTIME_CHAIN_CURRENT_STATE_AUDIT_READY",
    },
    "operator_action_payloads": {
        "filename": "operator_action_payloads.json",
        "required_status": "OPERATOR_ACTION_PAYLOADS_READY",
    },
    "operator_controller_design_brief": {
        "filename": "operator_controller_design_brief.json",
        "required_status": "OPERATOR_CONTROLLER_DESIGN_BRIEF_READY",
    },
    "operator_controller_protocol": {
        "filename": "operator_controller_protocol.json",
        "required_status": "OPERATOR_CONTROLLER_PROTOCOL_READY",
    },
    "dynamic_card_lifecycle_policy": {
        "filename": "dynamic_card_lifecycle_policy.json",
        "required_status": "DYNAMIC_CARD_LIFECYCLE_POLICY_READY",
    },
    "first_class_operator_envelope": {
        "filename": "first_class_operator_envelope_status.json",
        "required_status": "FIRST_CLASS_OPERATOR_ENVELOPE_READY",
    },
    "verified_evidence_intake": {
        "filename": "evidence_intake_status.json",
        "required_status": "EVIDENCE_INTAKE_LIVE_ROUTE_READY",
        "accepted_statuses": ("EVIDENCE_INTAKE_READY", "EVIDENCE_INTAKE_LIVE_ROUTE_READY"),
    },
    "lm_bounded_operator_orchestration": {
        "filename": "lm_bounded_operator_orchestration_latest.json",
        "required_status": "LM_BOUNDED_OPERATOR_ORCHESTRATION_READY",
        "status_keys": ("readiness_status", "status"),
        "accepted_statuses": ("LM_BOUNDED_OPERATOR_ORCHESTRATION_READY", "READY"),
    },
    "system_question_route": {
        "filename": "system_question_answer_contract.json",
        "required_status": "SYSTEM_QUESTION_ROUTE_READY",
        "equivalent_status": "SYSTEM_QUESTION_ANSWER_V0_READY",
    },
    "workroom_review_decision_consumer": {
        "filename": "workroom_review_decision_status.json",
        "required_status": "WORKROOM_REVIEW_DECISION_CONSUMER_READY",
    },
    "workbook_registration_route": {
        "filename": "client_invoice_workbook_registry.json",
        "required_status": "WORKBOOK_REGISTRATION_ROUTE_READY",
        "equivalent_status": "DETERMINISTIC_CLIENT_INVOICE_WORKBOOK_REGISTRY_NO_CELL_READ",
        "status_keys": ("status", "contract_status"),
    },
    "package_event_index": {
        "filename": "package_event_index.json",
        "required_status": "PACKAGE_EVENT_INDEX_READY",
    },
}

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "workbook_source_mutation_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "business_action_allowed": False,
    "external_action_allowed": False,
    "authority_grant_allowed": False,
    "worker_spawn_allowed": False,
    "child_agent_run_allowed": False,
    "agent_loop_allowed": False,
    "merge_allowed": False,
    "git_push_allowed": False,
    "push_allowed": False,
    "repair_authority_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "workbook_body_read_allowed": False,
    "workbook_open_allowed": False,
    "sent": False,
    "paid": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | {
    "authority_granted",
    "authority_granted_by_action",
    "coupa_submit_allowed",
    "gmail_access_allowed",
    "coupa_access_allowed",
    "browser_automation_allowed",
    "workbook_open_allowed",
    "workbook_body_read_allowed",
    "spreadsheet_cell_read_allowed",
    "workbook_mutation_allowed",
    "excel_automation_allowed",
    "email_draft_allowed",
    "ledger_mutation_allowed",
    "payment_marking_allowed",
    "paid_marking_allowed",
    "model_call_allowed",
    "agent_activation_allowed",
    "tool_execution_allowed",
    "runtime_dispatch_allowed",
    "raw_body_ingestion_allowed",
    "merge_allowed",
    "push_allowed",
    "git_push_allowed",
    "worker_spawn_allowed",
    "child_agent_run_allowed",
    "agent_loop_allowed",
    "external_action_allowed",
    "business_action_allowed",
    "repair_authority_allowed",
    "email_send_performed",
    "gmail_access_performed",
    "browser_access_performed",
    "coupa_access_performed",
    "coupa_submit_performed",
    "portal_submit_performed",
    "ledger_posting_performed",
    "ledger_mutation_performed",
    "workbook_open_performed",
    "workbook_body_read_performed",
    "spreadsheet_cell_read_performed",
    "workbook_mutation_performed",
    "excel_automation_performed",
    "pdf_export_performed",
    "paid_marking_performed",
    "payment_marking_performed",
    "mark_paid_performed",
    "submit_performed",
    "business_action_performed",
    "authority_grant_performed",
    "worker_spawn_performed",
    "worker_execution_performed",
    "child_agent_run_performed",
    "agent_loop_started",
    "external_llm_invoked",
    "external_llm_called",
    "local_model_runtime_connected",
    "model_invoked",
    "external_provider_connected",
    "merge_performed",
    "git_push_performed",
    "push_performed",
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:12]


def _slug(value: object) -> str:
    text = str(value or "").strip().lower()
    cleaned = "".join(char if char.isalnum() else "_" for char in text).strip("_")
    return cleaned or "card"


def _status(payload: Mapping[str, Any], keys: tuple[str, ...] = ("status", "readiness_status", "contract_status")) -> str:
    for key in keys:
        value = payload.get(key)
        if value:
            return str(value)
    return ""


def _source_ref(filename: str) -> str:
    return f"generated/read_models/{filename}"


SOURCE_REF_TO_NAME = {
    _source_ref(filename): name
    for name, filename in SOURCE_FILENAMES.items()
}


def _content_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _source_payload_for_ref(ref: str, source_payloads: Mapping[str, Mapping[str, Any]] | None) -> Mapping[str, Any]:
    if source_payloads is None:
        return {}
    payload = source_payloads.get(SOURCE_REF_TO_NAME.get(ref, ""))
    return payload if isinstance(payload, Mapping) else {}


def _source_statuses(
    refs: list[str],
    source_payloads: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, str]:
    return {
        ref: _status(_source_payload_for_ref(ref, source_payloads))
        for ref in refs
    }


def _source_generated_at(
    refs: list[str],
    source_payloads: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, str]:
    generated: dict[str, str] = {}
    for ref in refs:
        payload = _source_payload_for_ref(ref, source_payloads)
        generated[ref] = str(payload.get("generated_at") or payload.get("created_at") or "")
    return generated


def _source_content_hash(
    refs: list[str],
    source_payloads: Mapping[str, Mapping[str, Any]] | None,
) -> str:
    source_hashes = {
        ref: _content_hash(_source_payload_for_ref(ref, source_payloads))
        for ref in refs
    }
    return _content_hash(source_hashes)


def _infer_world_thread(card_id: str) -> tuple[str, str]:
    parts = card_id.split(".")
    if len(parts) >= 3 and parts[0] == "dynamic_card":
        return parts[1] or "mission_control", parts[2] or "operator_surface"
    return "mission_control", "operator_surface"


CARD_FAMILY_BY_ID = {
    "dynamic_card.finance.capital_hilton.payment_watch": "payment_watch_card",
    "dynamic_card.finance.capital_hilton.contextual_question": "answer_card",
    "dynamic_card.build.review_packet.current": "review_packet_card",
    "dynamic_card.business_development.capital_hilton.proposal": "workflow_composer_plan_card",
    "dynamic_card.system.check_engine.diagnostic": "gate_lock_card",
    "dynamic_card.finance.capital_hilton.workbook_registration": "current_focus_card",
    "dynamic_card.finance.st_annes.work_log_review": "completed_historical_receipt_card",
}


CARD_FAMILY_BY_TYPE = {
    "answer": "answer_card",
    "approval": "approval_request_card",
    "review_packet": "review_packet_card",
    "workflow_plan": "workflow_composer_plan_card",
    "gate": "gate_lock_card",
    "memory": "memory_candidate_card",
    "artifact": "artifact_proof_card",
    "evidence_intake": "evidence_intake_receipt_card",
    "payment_watch": "payment_watch_card",
    "question": "contextual_what_should_i_do_card",
}


def _card_family(card_id: str, card_type: str, override: str | None = None) -> str:
    family = override or CARD_FAMILY_BY_ID.get(card_id) or CARD_FAMILY_BY_TYPE.get(card_type) or "current_focus_card"
    if family not in CARD_FAMILIES:
        raise ValueError(f"unsupported card_family: {family}")
    return family


def _confidence_for_trust(trust_state: str) -> tuple[str, float]:
    return {
        "trusted_current": ("trusted_current", 0.86),
        "operator_reported": ("operator_reported", 0.56),
        "candidate_evidence": ("candidate_evidence", 0.46),
        "preview_only": ("generated_summary", 0.38),
        "future_gated": ("approval_required", 0.32),
        "stale_needs_proof": ("stale_needs_proof", 0.18),
        "unknown": ("unknown", 0.0),
    }.get(trust_state, ("unknown", 0.0))


def _classify_ref(ref: str) -> str:
    lowered = ref.lower()
    if ref.startswith("generated/read_models/"):
        return "read_model_refs"
    if lowered.endswith(".sqlite") or "sqlite:" in lowered or "/sqlite" in lowered:
        return "sqlite_refs"
    if lowered.startswith("sha256:") or lowered.startswith("hash:"):
        return "hash_refs"
    if "request" in lowered and lowered.endswith(".json"):
        return "request_refs"
    if "response" in lowered and lowered.endswith(".json"):
        return "response_refs"
    if "receipt" in lowered:
        return "receipt_refs"
    if ref.startswith("artifact:") or ref.startswith("/mnt/") or ref.startswith("/home/"):
        return "artifact_refs"
    return "artifact_refs"


def _controller_event_type_for_action(action: Mapping[str, Any]) -> str:
    action_id = str(action.get("action_id") or "")
    action_type = str(action.get("action_type") or "none")
    if action_type == "navigate":
        return "open_lane"
    if action_type in {"system_question", "explain_gate"}:
        return "ask_why"
    if "ask_what_this_means" in action_id:
        return "ask_why"
    if "show_details" in action_id:
        return "show_details"
    if "mark_as_test" in action_id:
        return "mark_informational"
    if action_type == "record_payment_proof_intake" or "evidence_intake" in action_id:
        return "attach_proof"
    if action_type == "review_decision":
        if "approve" in action_id:
            return "approve"
        if "request" in action_id or "rework" in action_id:
            return "request_rework"
        if "informational" in action_id:
            return "mark_informational"
        if "deny" in action_id:
            return "deny"
    if action_type == "stage_package_request":
        return "do_it"
    if action_type == "workbook_registration":
        return "do_it"
    if action_type == "inspect_proof":
        return "show_details"
    return "show_details"


def _receipt_required(controller_event_type: str) -> bool:
    return controller_event_type in {
        "do_it",
        "approve",
        "deny",
        "attach_proof",
        "stage_plan",
        "continue",
        "request_rework",
        "mark_informational",
        "stop_hold_cancel",
    }


def _source_payloads(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> dict[str, dict[str, Any]]:
    root = _rooted(read_model_root)
    return {
        name: _load_json(root / filename)
        for name, filename in SOURCE_FILENAMES.items()
    }


def _proof_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == "collapsed_by_default":
                continue
            if isinstance(item, str) and item:
                refs.append(item)
            elif isinstance(item, list):
                refs.extend(str(ref) for ref in item if str(ref))
    elif isinstance(value, list):
        refs.extend(str(ref) for ref in value if str(ref))
    elif isinstance(value, str) and value:
        refs.append(value)
    return list(dict.fromkeys(refs))


def _action_index(operator_action_payloads: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    actions = operator_action_payloads.get("action_payloads")
    if not isinstance(actions, list):
        return {}
    return {
        str(action.get("action_id")): dict(action)
        for action in actions
        if isinstance(action, Mapping) and action.get("action_id")
    }


def action_payload_ref(action_id: str) -> str:
    return f"generated/read_models/operator_action_payloads.json#action_payloads.{action_id}"


def _action_from_payload(
    action_index: Mapping[str, Mapping[str, Any]],
    action_id: str,
    *,
    enabled_override: bool | None = None,
    disabled_reason_override: str | None = None,
) -> dict[str, Any]:
    source = action_index.get(action_id)
    if not isinstance(source, Mapping):
        return _disabled_action(
            action_id=action_id,
            label=action_id.replace("_", " ").replace(".", " ").title(),
            action_type="none",
            disabled_reason="No deterministic operator_action_payload exists for this action.",
        )
    enabled = bool(source.get("enabled"))
    if enabled_override is not None:
        enabled = enabled_override
    disabled_reason = source.get("disabled_reason")
    if disabled_reason_override is not None:
        disabled_reason = disabled_reason_override
    if not enabled and not disabled_reason:
        disabled_reason = "Action is disabled by the backend gate."
    return {
        "action_id": str(source["action_id"]),
        "label": str(source.get("label") or source["action_id"]),
        "action_type": str(source.get("action_type") or "none"),
        "enabled": enabled,
        "disabled_reason": None if enabled else str(disabled_reason),
        "payload_ref": action_payload_ref(str(source["action_id"])),
        "business_action": bool(source.get("business_action")),
    }


def _disabled_action(
    *,
    action_id: str,
    label: str,
    action_type: str = "none",
    disabled_reason: str,
) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "label": label,
        "action_type": action_type if action_type in ACTION_TYPES else "none",
        "enabled": False,
        "disabled_reason": disabled_reason,
        "payload_ref": "",
        "business_action": False,
    }


def _proof(
    *,
    proof_refs: list[str] | tuple[str, ...] = (),
    receipt_refs: list[str] | tuple[str, ...] = (),
    read_model_refs: list[str] | tuple[str, ...] = (),
    artifact_refs: list[str] | tuple[str, ...] = (),
    hash_refs: list[str] | tuple[str, ...] = (),
    sqlite_refs: list[str] | tuple[str, ...] = (),
    request_refs: list[str] | tuple[str, ...] = (),
    response_refs: list[str] | tuple[str, ...] = (),
    label: str = "Details",
    redacted_summary: str = "",
    sensitive_detail_policy: str = "redacted_by_default",
    developer_proof_only: bool = False,
) -> dict[str, Any]:
    all_refs = list(dict.fromkeys(str(ref) for ref in [*proof_refs, *receipt_refs, *read_model_refs, *artifact_refs, *hash_refs, *sqlite_refs, *request_refs, *response_refs] if str(ref)))
    categorized = {
        "receipt_refs": list(dict.fromkeys(str(ref) for ref in receipt_refs if str(ref))),
        "artifact_refs": list(dict.fromkeys(str(ref) for ref in artifact_refs if str(ref))),
        "hash_refs": list(dict.fromkeys(str(ref) for ref in hash_refs if str(ref))),
        "sqlite_refs": list(dict.fromkeys(str(ref) for ref in sqlite_refs if str(ref))),
        "read_model_refs": list(dict.fromkeys(str(ref) for ref in read_model_refs if str(ref))),
        "request_refs": list(dict.fromkeys(str(ref) for ref in request_refs if str(ref))),
        "response_refs": list(dict.fromkeys(str(ref) for ref in response_refs if str(ref))),
    }
    for ref in all_refs:
        category = _classify_ref(ref)
        if ref not in categorized[category]:
            categorized[category].append(ref)
    source_content_hash = _content_hash(
        {
            key: value
            for key, value in categorized.items()
        }
    )
    return {
        "label": label,
        "collapsed_by_default": True,
        "proof_refs": all_refs,
        **categorized,
        "redacted_summary": redacted_summary or "Proof is available in categorized refs; raw sensitive details are not primary UI.",
        "sensitive_detail_policy": sensitive_detail_policy,
        "developer_proof_only": bool(developer_proof_only),
        "raw_detail_available": False,
        "source_content_hash": source_content_hash,
        "validation_commands": [],
        "unsafe_scan_result": "clean",
    }


def _empty_action_slot(
    *,
    slot: str,
    controller_event_type: str = "show_details",
    label: str | None = None,
    disabled_reason: str | None = None,
    proof_refs: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    if slot not in ACTION_SLOTS:
        raise ValueError(f"unsupported action slot: {slot}")
    return {
        "action_id": "",
        "action_payload_ref": "",
        "controller_event_type": controller_event_type,
        "label": label or f"No {slot.replace('_', ' ')} action",
        "enabled": False,
        "disabled_reason": disabled_reason or f"No {slot.replace('_', ' ')} action for this card.",
        "requires_operator_envelope": True,
        "receipt_required": _receipt_required(controller_event_type),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "proof_refs": list(dict.fromkeys(str(ref) for ref in proof_refs if str(ref))),
    }


def _action_slot_from_action(action: Mapping[str, Any], proof_refs: list[str] | tuple[str, ...]) -> dict[str, Any]:
    controller_event_type = _controller_event_type_for_action(action)
    enabled = bool(action.get("enabled") is True)
    disabled_reason = action.get("disabled_reason")
    if not enabled and not disabled_reason:
        disabled_reason = "Action is disabled by the backend gate."
    return {
        "action_id": str(action.get("action_id") or ""),
        "action_payload_ref": str(action.get("payload_ref") or ""),
        "controller_event_type": controller_event_type,
        "label": str(action.get("label") or action.get("action_id") or "Action"),
        "enabled": enabled,
        "disabled_reason": None if enabled else str(disabled_reason),
        "requires_operator_envelope": True,
        "receipt_required": _receipt_required(controller_event_type),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "proof_refs": list(dict.fromkeys(str(ref) for ref in proof_refs if str(ref))),
    }


def _action_slots(
    actions: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    proof: Mapping[str, Any],
    *,
    danger_label: str = "Protected action unavailable",
    danger_reason: str = "Protected actions require a separate backend gate and are not executable from this card.",
) -> dict[str, dict[str, Any]]:
    proof_refs = _proof_refs(proof)
    action_list = [action for action in actions if isinstance(action, Mapping)]
    slots: dict[str, dict[str, Any]] = {
        "primary": _empty_action_slot(slot="primary", proof_refs=proof_refs),
        "secondary": _empty_action_slot(slot="secondary", proof_refs=proof_refs),
        "detail": _empty_action_slot(
            slot="detail",
            controller_event_type="show_details",
            label="Show details",
            disabled_reason="No deterministic inspect-proof payload exists for this card.",
            proof_refs=proof_refs,
        ),
        "dismiss": _empty_action_slot(
            slot="dismiss",
            controller_event_type="show_details",
            label="Dismiss",
            disabled_reason="Dismiss is a local client view preference; backend does not record dismissal from this packet.",
            proof_refs=proof_refs,
        ),
        "danger_disabled": _empty_action_slot(
            slot="danger_disabled",
            controller_event_type="do_it",
            label=danger_label,
            disabled_reason=danger_reason,
            proof_refs=proof_refs,
        ),
    }
    if action_list:
        slots["primary"] = _action_slot_from_action(action_list[0], proof_refs)
    if len(action_list) > 1:
        slots["secondary"] = _action_slot_from_action(action_list[1], proof_refs)
    if len(action_list) > 2:
        slots["detail"] = _action_slot_from_action(action_list[2], proof_refs)
    return slots


def _card(
    *,
    card_id: str,
    card_type: str,
    card_family: str | None = None,
    speaker_ref: str,
    headline: str,
    plain_summary: str,
    supporting_lines: list[str] | tuple[str, ...],
    status_label: str,
    tone: str,
    trust_state: str,
    priority: int,
    visible_by_default: bool,
    actions: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    proof: Mapping[str, Any],
    source_payloads: Mapping[str, Mapping[str, Any]] | None = None,
    world_ref: str | None = None,
    thread_ref: str | None = None,
    lane_ref: str = "",
    workflow_ref: str = "",
    client_ref: str = "",
    entity_refs: list[str] | tuple[str, ...] = (),
    object_refs: list[str] | tuple[str, ...] = (),
    confidence_class: str | None = None,
    confidence_score: float | None = None,
    developer_proof_only: bool = False,
    machine_contract_visible: bool = False,
    danger_label: str = "Protected action unavailable",
    danger_reason: str = "Protected actions require a separate backend gate and are not executable from this card.",
) -> dict[str, Any]:
    if card_type not in CARD_TYPES:
        raise ValueError(f"unsupported card_type: {card_type}")
    if speaker_ref not in SPEAKER_REFS:
        raise ValueError(f"unsupported speaker_ref: {speaker_ref}")
    if tone not in TONES:
        raise ValueError(f"unsupported tone: {tone}")
    if trust_state not in TRUST_STATES:
        raise ValueError(f"unsupported trust_state: {trust_state}")
    family = _card_family(card_id, card_type, card_family)
    inferred_world_ref, inferred_thread_ref = _infer_world_thread(card_id)
    world_ref = world_ref or inferred_world_ref
    thread_ref = thread_ref or inferred_thread_ref
    lane_ref = lane_ref or f"{world_ref}/{thread_ref}"
    proof_payload = dict(proof)
    source_read_model_refs = list(dict.fromkeys(str(ref) for ref in proof_payload.get("read_model_refs") or [] if str(ref)))
    proof_payload["source_content_hash"] = str(proof_payload.get("source_content_hash") or _source_content_hash(source_read_model_refs, source_payloads))
    confidence_class, confidence_score = (
        (confidence_class, confidence_score)
        if confidence_class is not None and confidence_score is not None
        else _confidence_for_trust(trust_state)
    )
    action_slots = _action_slots(
        actions,
        proof_payload,
        danger_label=danger_label,
        danger_reason=danger_reason,
    )
    card = {
        "card_id": card_id,
        "card_family": family,
        "card_type": card_type,
        "world_ref": world_ref,
        "thread_ref": thread_ref,
        "lane_ref": lane_ref,
        "workflow_ref": workflow_ref,
        "client_ref": client_ref,
        "entity_refs": list(entity_refs),
        "object_refs": list(object_refs),
        "speaker_ref": speaker_ref,
        "headline": headline,
        "plain_summary": plain_summary,
        "supporting_lines": list(supporting_lines),
        "status_label": status_label,
        "tone": tone,
        "trust_state": trust_state,
        "confidence_class": confidence_class,
        "confidence_score": float(confidence_score),
        "priority": int(priority),
        "visible_by_default": bool(visible_by_default),
        "visibility_reason": "shown_by_lifecycle_policy" if visible_by_default else "hidden_by_lifecycle_policy",
        "attention_cost": "operator_attention" if visible_by_default else "collapsed_history_or_proof",
        "actions": list(actions),
        "action_slots": action_slots,
        "proof": proof_payload,
        "source_read_model_refs": source_read_model_refs,
        "source_statuses": _source_statuses(source_read_model_refs, source_payloads),
        "source_generated_at": _source_generated_at(source_read_model_refs, source_payloads),
        "source_content_hash": _source_content_hash(source_read_model_refs, source_payloads),
        "developer_proof_only": bool(developer_proof_only),
        "operator_mode_visible": bool(visible_by_default and not developer_proof_only),
        "machine_contract_visible": bool(machine_contract_visible),
        "accessibility_text": f"{headline}. {status_label}. {plain_summary}",
        "device_render_hints": {
            "mac": {"layout": "full_width_controller_card", "proof_drawer": "available"},
            "ipad": {"layout": "compact_controller_card", "proof_drawer": "available"},
            "iphone": {"layout": "single_column_summary", "proof_drawer": "collapsed"},
        },
        "device_render_hint": {
            "preferred_height": "compact",
            "primary_interaction": "controller_event",
        },
        "history_group_ref": f"history.{world_ref}.{thread_ref}",
        "superseded_by_card_ref": "",
        "stale_after": "",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    return lifecycle_policy.apply_lifecycle_policy(card)


def _capital_hilton_payment_watch_card(sources: Mapping[str, Mapping[str, Any]], action_index: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    invoice = sources.get("capital_hilton_invoice_operator_run_status", {})
    lm = sources.get("lm_bounded_operator_orchestration", {})
    status = str(invoice.get("coupa_submission_status") or invoice.get("coupa_status_observed") or "processing")
    proof_refs = [
        _source_ref("capital_hilton_invoice_operator_run_status.json"),
        _source_ref("operator_action_payloads.json"),
        _source_ref("lm_bounded_operator_orchestration_latest.json"),
        *_proof_refs(invoice.get("proof_refs")),
        *_proof_refs((lm.get("lm_recommended_action") or {}).get("proof_refs") if isinstance(lm.get("lm_recommended_action"), Mapping) else []),
    ]
    return _card(
        card_id="dynamic_card.finance.capital_hilton.payment_watch",
        card_type="payment_watch",
        speaker_ref="chief",
        headline="Stay on payment watch",
        plain_summary="Coupa is processing. Wait for payment evidence before anything touches the ledger.",
        supporting_lines=[
            f"Coupa status: {status}.",
            "Payment evidence is not recorded as ledger truth.",
            "No Coupa, browser, ledger, or paid action is available from this card.",
        ],
        status_label="Payment watch",
        tone="calm",
        trust_state="trusted_current",
        priority=100,
        visible_by_default=True,
        actions=[
            _action_from_payload(action_index, "capital_hilton.payment.open_finance"),
        ],
        proof=_proof(
            proof_refs=proof_refs,
            receipt_refs=_proof_refs(invoice.get("proof_refs")),
            read_model_refs=[
                _source_ref("capital_hilton_invoice_operator_run_status.json"),
                _source_ref("lm_bounded_operator_orchestration_latest.json"),
            ],
        ),
        source_payloads=sources,
        workflow_ref="capital_hilton_invoice_payment_watch",
        client_ref="capital_hilton",
        entity_refs=["client:capital_hilton"],
        object_refs=["invoice:capital_hilton:2026-06-01"],
        danger_label="Submit in Coupa",
        danger_reason="Coupa submit is protected and unavailable from payment watch cards.",
    )


def _contextual_question_card(
    sources: Mapping[str, Mapping[str, Any]],
    action_index: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return _card(
        card_id="dynamic_card.finance.capital_hilton.contextual_question",
        card_type="answer",
        speaker_ref="chief",
        headline="Stay on payment watch",
        plain_summary="Coupa is processing. Wait for payment evidence before anything touches the ledger.",
        supporting_lines=[
            "Answered from current lane metadata: Finance / Capital Hilton.",
            "This is a local answer, not package staging.",
            "Diagnostic workflow queue routing is not needed for this question.",
        ],
        status_label="Answer ready",
        tone="calm",
        trust_state="trusted_current",
        priority=95,
        visible_by_default=True,
        actions=[
            _action_from_payload(action_index, "capital_hilton.payment.open_finance"),
        ],
        proof=_proof(
            proof_refs=[
                _source_ref("system_question_answer_contract.json"),
                _source_ref("capital_hilton_invoice_operator_run_status.json"),
                _source_ref("finance_thread_index.json"),
            ],
            read_model_refs=[
                _source_ref("system_question_answer_contract.json"),
                _source_ref("finance_thread_index.json"),
            ],
        ),
        source_payloads=sources,
        workflow_ref="capital_hilton_payment_watch_question",
        client_ref="capital_hilton",
        entity_refs=["client:capital_hilton"],
        object_refs=["thread:finance/capital_hilton"],
    )


def _open_review_packet(packet_index: Mapping[str, Any]) -> dict[str, Any]:
    packets = packet_index.get("packets")
    if not isinstance(packets, list):
        return {}
    for packet in packets:
        if not isinstance(packet, Mapping):
            continue
        status = str(packet.get("status") or packet.get("review_decision_status") or "")
        if (
            packet.get("operator_decision_required") is True
            and packet.get("completed") is not True
            and status not in {"OPERATOR_REVIEW_RECORDED", "INFORMATIONAL_REVIEW_CLOSED"}
        ):
            return dict(packet)
    return {}


def _review_packet_card(sources: Mapping[str, Mapping[str, Any]], action_index: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    packet = _open_review_packet(sources.get("workroom_review_packet_index", {}))
    packet_id = str(packet.get("review_packet_id") or "review_packet:unknown")
    packet_slug = _slug(packet_id)
    action_ids = [
        f"review_packet.{packet_slug}.approve_review_packet_for_record",
        f"review_packet.{packet_slug}.request_review_packet_rework",
        f"review_packet.{packet_slug}.mark_review_packet_informational",
    ]
    proof_refs = [
        _source_ref("workroom_review_packet_index.json"),
        _source_ref("workroom_review_decision_status.json"),
        *_proof_refs(packet.get("proof_refs")),
    ]
    return _card(
        card_id="dynamic_card.build.review_packet.current",
        card_type="review_packet",
        speaker_ref="chief",
        headline="Review packet needs local decision",
        plain_summary=str(packet.get("human_summary") or "A review packet is ready for operator review."),
        supporting_lines=[
            f"Packet: {packet_id}.",
            f"Worker: {packet.get('worker_ref', 'unknown')}.",
            "Use review controls only; no merge or push is authorized.",
        ],
        status_label=str(packet.get("status") or "Review required"),
        tone="warning",
        trust_state="preview_only",
        priority=90,
        visible_by_default=bool(packet),
        actions=[_action_from_payload(action_index, action_id) for action_id in action_ids],
        proof=_proof(
            proof_refs=proof_refs,
            read_model_refs=[
                _source_ref("workroom_review_packet_index.json"),
                _source_ref("workroom_review_decision_status.json"),
            ],
        ),
        source_payloads=sources,
        workflow_ref=str(packet.get("workflow_ref") or "workroom_review_packet"),
        entity_refs=[f"review_packet:{packet_id}"],
        object_refs=[packet_id],
        danger_label="Merge or push",
        danger_reason="Review decisions record local verdicts only; merge and push are not available from cards.",
    )


def _business_development_card(sources: Mapping[str, Mapping[str, Any]], action_index: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    proposal = sources.get("capital_hilton_business_development_proposal", {})
    status = str(proposal.get("proposal_status") or "proposal status unknown")
    pending = proposal.get("client_review_pending") is True
    return _card(
        card_id="dynamic_card.business_development.capital_hilton.proposal",
        card_type="status",
        speaker_ref="cassandra",
        headline="Proposal follow-up is review-only",
        plain_summary="Capital Hilton proposal context is business development. Draft or stage a follow-up only for review; do not send.",
        supporting_lines=[
            f"Proposal status: {status}.",
            f"Client review pending: {str(pending).lower()}.",
            "Email send, finance handoff, ledger posting, and accepted/paid truth are closed.",
        ],
        status_label="Proposal status",
        tone="calm",
        trust_state="trusted_current",
        priority=80,
        visible_by_default=True,
        actions=[
            _action_from_payload(action_index, "capital_hilton.proposal.stage_followup"),
        ],
        proof=_proof(
            proof_refs=[
                _source_ref("capital_hilton_business_development_proposal.json"),
                *_proof_refs(proposal.get("proof_refs")),
            ],
            read_model_refs=[_source_ref("capital_hilton_business_development_proposal.json")],
        ),
        source_payloads=sources,
        workflow_ref="capital_hilton_proposal_followup",
        client_ref="capital_hilton",
        entity_refs=["client:capital_hilton"],
        object_refs=["proposal:capital_hilton:fight_weekend_2026"],
        danger_label="Send follow-up",
        danger_reason="Email send is protected and not available from proposal follow-up cards.",
    )


def _check_engine_card(
    sources: Mapping[str, Mapping[str, Any]],
    action_index: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return _card(
        card_id="dynamic_card.system.check_engine.diagnostic",
        card_type="status",
        speaker_ref="chief",
        headline="Chief diagnostic only",
        plain_summary="Open the Check Engine diagnostic or ask Chief; no repair authority is granted.",
        supporting_lines=[
            "This card can explain or open diagnostics only.",
            "No repair, worker spawn, push, or business action follows from this card.",
        ],
        status_label="Diagnostic",
        tone="neutral",
        trust_state="preview_only",
        priority=70,
        visible_by_default=True,
        actions=[
            _action_from_payload(action_index, "chief_diagnostic.open"),
            _action_from_payload(action_index, "helm_question.hardwired_vs_spawned.ask"),
        ],
        proof=_proof(
            proof_refs=[
                _source_ref("chief_check_engine_diagnostic_package.json"),
                _source_ref("operator_action_payloads.json"),
            ],
            read_model_refs=[
                _source_ref("chief_check_engine_diagnostic_package.json"),
                _source_ref("operator_action_payloads.json"),
            ],
        ),
        source_payloads=sources,
        workflow_ref="chief_check_engine_diagnostic",
        entity_refs=["speaker:chief"],
        object_refs=["diagnostic:check_engine"],
        danger_label="Run repair",
        danger_reason="Repair authority is not granted by a diagnostic card.",
    )


def _workbook_registration_card(sources: Mapping[str, Mapping[str, Any]], action_index: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    registry = sources.get("client_invoice_workbook_registry", {})
    active = registry.get("active_record") if isinstance(registry.get("active_record"), Mapping) else {}
    workbook_name = str(active.get("workbook_display_name") or "selected workbook reference")
    status = str(active.get("workbook_status") or registry.get("contract_status") or "workbook reference")
    return _card(
        card_id="dynamic_card.finance.capital_hilton.workbook_registration",
        card_type="workbook_registration",
        speaker_ref="chief",
        headline="Workbook reference can be registered",
        plain_summary="Register the workbook reference as metadata only; do not read workbook body, run Excel, or mutate the file.",
        supporting_lines=[
            f"Workbook: {workbook_name}.",
            f"Status: {status}.",
            "Metadata registration is separate from any governed sheet audit.",
        ],
        status_label="Workbook registration",
        tone="calm",
        trust_state="trusted_current",
        priority=60,
        visible_by_default=True,
        actions=[
            _action_from_payload(action_index, "client_invoice_workbook.register"),
        ],
        proof=_proof(
            proof_refs=[_source_ref("client_invoice_workbook_registry.json")],
            read_model_refs=[_source_ref("client_invoice_workbook_registry.json")],
        ),
        source_payloads=sources,
        workflow_ref="client_invoice_workbook_registration",
        client_ref="capital_hilton",
        entity_refs=["client:capital_hilton"],
        object_refs=[f"workbook:{workbook_name}"],
        danger_label="Open workbook body",
        danger_reason="Workbook body reads and mutations are protected and unavailable from metadata-registration cards.",
    )


def _st_annes_work_log_card(sources: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    surface = sources.get("st_annes_work_log_review_surface", {})
    counts = surface.get("event_counts") if isinstance(surface.get("event_counts"), Mapping) else {}
    pending = int(counts.get("pending_operator_review") or 0)
    test_only = int(counts.get("smoke_or_test_not_included") or 0)
    actions: list[dict[str, Any]] = []
    if pending:
        disabled_reason = "No deterministic operator_action_payload exists yet for St. Anne's review actions."
        actions = [
            _disabled_action(
                action_id="st_annes.work_log.confirm",
                label="Confirm",
                disabled_reason=disabled_reason,
            ),
            _disabled_action(
                action_id="st_annes.work_log.discard",
                label="Discard",
                disabled_reason=disabled_reason,
            ),
            _disabled_action(
                action_id="st_annes.work_log.mark_as_test",
                label="Mark as test",
                disabled_reason=disabled_reason,
            ),
        ]
    return _card(
        card_id="dynamic_card.finance.st_annes.work_log_review",
        card_type="status",
        speaker_ref="chief",
        headline="St. Anne's work-log review",
        plain_summary="St. Anne's work-log review stays local; completed or test-only items are not primary active blockers.",
        supporting_lines=[
            f"Pending review: {pending}.",
            f"Smoke/test not included: {test_only}.",
            "Excel, PDF, email, ledger, and invoice inclusion remain gated.",
        ],
        status_label="No active blocker" if pending == 0 else "Review pending",
        tone="neutral" if pending == 0 else "warning",
        trust_state="trusted_current",
        priority=20 if pending == 0 else 75,
        visible_by_default=pending > 0,
        actions=actions,
        proof=_proof(
            proof_refs=[_source_ref("st_annes_work_log_review_surface.json")],
            read_model_refs=[_source_ref("st_annes_work_log_review_surface.json")],
        ),
        source_payloads=sources,
        workflow_ref="st_annes_work_log_review",
        client_ref="st_annes",
        entity_refs=["client:st_annes"],
        object_refs=["work_log:st_annes"],
        danger_label="Include in invoice",
        danger_reason="Invoice inclusion, PDF export, email, ledger, and workbook mutation remain gated.",
    )


def _evidence_envelope_required_action(*, action_id: str, label: str, disabled_reason: str) -> dict[str, Any]:
    action = _disabled_action(
        action_id=action_id,
        label=label,
        disabled_reason=disabled_reason,
    )
    action.update(
        {
            "requires_operator_authority_envelope": True,
            "operator_authority_envelope_contract_ref": FIRST_CLASS_OPERATOR_ENVELOPE_CONTRACT_REF,
            "operator_authority_envelope_status_ref": FIRST_CLASS_OPERATOR_ENVELOPE_STATUS_REF,
            "authority_granted_by_action": False,
        }
    )
    return action


def _evidence_intake_card(sources: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    status = sources.get("evidence_intake", {})
    record = status.get("latest_record") if isinstance(status.get("latest_record"), Mapping) else {}
    card = status.get("dynamic_card") if isinstance(status.get("dynamic_card"), Mapping) else {}
    artifact = record.get("artifact") if isinstance(record.get("artifact"), Mapping) else {}
    payment = record.get("payment") if isinstance(record.get("payment"), Mapping) else {}
    world_ref = str(record.get("current_world_ref") or "finance")
    thread_ref = str(record.get("current_thread_ref") or "evidence_intake")
    disabled_reason = "No deterministic operator_action_payload exists yet for evidence intake card actions."
    summary = str(
        card.get("summary")
        or "This appears to show payment processing for invoice 2026-1001. Ledger remains untouched until payment is confirmed."
    )
    return _card(
        card_id=f"dynamic_card.{_slug(world_ref)}.{_slug(thread_ref)}.evidence_intake.payment_processing",
        card_type="evidence_intake",
        speaker_ref="chief",
        headline=str(card.get("headline") or "Payment proof received"),
        plain_summary=summary,
        supporting_lines=[
            f"Evidence status: {record.get('evidence_status', 'unknown')}.",
            f"Payment state: {payment.get('payment_state', 'unknown')}.",
            "Candidate evidence does not mark paid or touch the ledger.",
        ],
        status_label=str(card.get("status_label") or "Processing evidence"),
        tone="calm",
        trust_state=str(card.get("trust_state") or "operator_reported"),
        priority=97,
        visible_by_default=bool(record),
        actions=[
            _evidence_envelope_required_action(
                action_id="evidence_intake.attach_to_lane",
                label="Attach to lane",
                disabled_reason=disabled_reason,
            ),
            _evidence_envelope_required_action(
                action_id="evidence_intake.ask_what_this_means",
                label="Ask what this means",
                disabled_reason=disabled_reason,
            ),
            _evidence_envelope_required_action(
                action_id="evidence_intake.mark_as_test",
                label="Mark as test",
                disabled_reason=disabled_reason,
            ),
            _evidence_envelope_required_action(
                action_id="evidence_intake.show_details",
                label="Show details",
                disabled_reason=disabled_reason,
            ),
        ],
        proof=_proof(
            proof_refs=[
                _source_ref("evidence_intake_status.json"),
                str(artifact.get("artifact_ref") or record.get("artifact_ref") or ""),
            ],
            read_model_refs=[_source_ref("evidence_intake_status.json")],
            artifact_refs=[
                str(artifact.get("artifact_ref") or record.get("artifact_ref") or ""),
                str(artifact.get("bridge_artifact_ref") or ""),
                str(artifact.get("path") or ""),
            ],
            hash_refs=[f"sha256:{artifact.get('sha256')}" if artifact.get("sha256") else ""],
            sqlite_refs=[str(status.get("sqlite_path") or "generated/system_knowledge/evidence_intake.sqlite")],
            redacted_summary="Payment-processing proof was recorded as local candidate evidence; raw sensitive detail stays out of primary UI.",
            sensitive_detail_policy="financial_sensitive/local_only_redacted",
        ),
        source_payloads=sources,
        world_ref=world_ref,
        thread_ref=thread_ref,
        lane_ref=f"{world_ref}/{thread_ref}",
        workflow_ref=str(record.get("claimed_workflow_ref") or "evidence_intake"),
        client_ref=str(record.get("claimed_client_ref") or thread_ref),
        entity_refs=[f"client:{record.get('claimed_client_ref') or thread_ref}"],
        object_refs=[str(record.get("artifact_ref") or artifact.get("artifact_ref") or "")],
        danger_label="Mark paid",
        danger_reason="Payment-processing evidence never marks paid or mutates the ledger.",
    )


def _approval_request_card(
    sources: Mapping[str, Mapping[str, Any]],
    action_index: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return _card(
        card_id="dynamic_card.finance.capital_hilton.approval_request.coupa_submit",
        card_family="approval_request_card",
        card_type="approval",
        speaker_ref="guardian",
        headline="Coupa submit requires a protected gate",
        plain_summary="The controller may stage an approval request or explain the gate, but it cannot submit to Coupa.",
        supporting_lines=[
            "Protected provider submit remains blocked.",
            "Staging an approval request is not execution proof.",
            "No browser, Coupa, portal submit, ledger, PDF, or paid action is available.",
        ],
        status_label="Approval required",
        tone="blocked",
        trust_state="future_gated",
        priority=55,
        visible_by_default=False,
        actions=[
            _action_from_payload(action_index, "guardian_gate.coupa_submit.stage_approval_request"),
            _action_from_payload(action_index, "guardian_gate.coupa_submit.open"),
            _action_from_payload(action_index, "guardian_gate.coupa_submit.explain"),
        ],
        proof=_proof(
            proof_refs=[
                _source_ref("gate_decision_ledger.json"),
                _source_ref("operator_action_payloads.json"),
                _source_ref("operator_controller_protocol.json"),
            ],
            read_model_refs=[
                _source_ref("gate_decision_ledger.json"),
                _source_ref("operator_action_payloads.json"),
                _source_ref("operator_controller_protocol.json"),
            ],
            redacted_summary="Protected Coupa submit is represented as a gate/approval card only.",
            sensitive_detail_policy="gate_metadata_only",
        ),
        source_payloads=sources,
        workflow_ref="capital_hilton_coupa_submit_gate",
        client_ref="capital_hilton",
        entity_refs=["client:capital_hilton", "gate:coupa_submit"],
        object_refs=["gate:capital_hilton:coupa_submit"],
        danger_label="Submit in Coupa",
        danger_reason="Coupa submit is protected; this card can only stage approval or explain the gate.",
    )


def _memory_candidate_card(sources: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return _card(
        card_id="dynamic_card.memory.payment_evidence_candidate",
        card_family="memory_candidate_card",
        card_type="memory",
        speaker_ref="openclaw",
        headline="Candidate memory stays unpromoted",
        plain_summary="Payment-processing evidence can become a reviewed memory candidate, but candidate memory is not business truth.",
        supporting_lines=[
            "Memory promotion requires explicit proof and review.",
            "Generated summaries cannot override receipts, hashes, or source rows.",
            "Candidate memory never marks paid or sent.",
        ],
        status_label="Candidate only",
        tone="neutral",
        trust_state="candidate_evidence",
        priority=10,
        visible_by_default=False,
        actions=[],
        proof=_proof(
            proof_refs=[
                _source_ref("evidence_confidence_scoring.json"),
                _source_ref("evidence_intake_status.json"),
            ],
            read_model_refs=[
                _source_ref("evidence_confidence_scoring.json"),
                _source_ref("evidence_intake_status.json"),
            ],
            redacted_summary="Memory candidate is hidden until a backend review route makes it operator-actionable.",
            sensitive_detail_policy="candidate_memory_no_raw_sensitive_detail",
            developer_proof_only=True,
        ),
        source_payloads=sources,
        workflow_ref="memory_candidate_review",
        entity_refs=["memory:payment_evidence_candidate"],
        object_refs=["candidate_memory:payment_evidence"],
        developer_proof_only=True,
        danger_label="Promote memory",
        danger_reason="Memory promotion is gated and unavailable from proof-only cards.",
    )


def _artifact_proof_card(sources: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    evidence = sources.get("evidence_intake", {})
    latest = evidence.get("latest_record") if isinstance(evidence.get("latest_record"), Mapping) else {}
    artifact = latest.get("artifact") if isinstance(latest.get("artifact"), Mapping) else {}
    artifact_ref = str(artifact.get("artifact_ref") or latest.get("artifact_ref") or "artifact:evidence_intake_candidate")
    return _card(
        card_id="dynamic_card.artifact.evidence_intake.proof_only",
        card_family="artifact_proof_card",
        card_type="artifact",
        speaker_ref="openclaw",
        headline="Artifact proof is available",
        plain_summary="Artifact refs, hashes, and SQLite lineage are available in Developer Proof, not as primary controller UI.",
        supporting_lines=[
            "Raw artifact body is not read by this packet.",
            "Financial-sensitive detail remains local-only and redacted.",
            "Artifact proof does not mark paid or mutate ledgers.",
        ],
        status_label="Proof only",
        tone="neutral",
        trust_state="operator_reported",
        priority=9,
        visible_by_default=False,
        actions=[],
        proof=_proof(
            proof_refs=[
                _source_ref("evidence_intake_status.json"),
                artifact_ref,
            ],
            artifact_refs=[
                artifact_ref,
                str(artifact.get("bridge_artifact_ref") or ""),
                str(artifact.get("path") or ""),
            ],
            hash_refs=[f"sha256:{artifact.get('sha256')}" if artifact.get("sha256") else ""],
            sqlite_refs=[str(evidence.get("sqlite_path") or "generated/system_knowledge/evidence_intake.sqlite")],
            read_model_refs=[_source_ref("evidence_intake_status.json")],
            redacted_summary="Artifact proof metadata is categorized for the proof drawer; raw content is not primary UI.",
            sensitive_detail_policy="financial_sensitive/local_only_redacted",
            developer_proof_only=True,
        ),
        source_payloads=sources,
        workflow_ref="evidence_intake_artifact_lineage",
        entity_refs=["artifact:evidence_intake"],
        object_refs=[artifact_ref],
        developer_proof_only=True,
        danger_label="Read raw artifact",
        danger_reason="Raw artifact body reads require a separate explicit gate.",
    )


def _contextual_safe_next_card(
    sources: Mapping[str, Mapping[str, Any]],
    action_index: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return _card(
        card_id="dynamic_card.controller.safe_next.what_should_i_do",
        card_family="contextual_what_should_i_do_card",
        card_type="question",
        speaker_ref="chief",
        headline="Ask what is safe next",
        plain_summary="The controller can ask for a contextual safe-next answer without staging a package or executing a business action.",
        supporting_lines=[
            "Answer from current world/thread context.",
            "LM output is not truth; receipts and read models define truth.",
            "If protected action is needed, the backend returns a blocked gate or staged approval path.",
        ],
        status_label="Contextual control",
        tone="calm",
        trust_state="trusted_current",
        priority=50,
        visible_by_default=True,
        actions=[
            _action_from_payload(action_index, "helm_question.safe_next.ask"),
        ],
        proof=_proof(
            proof_refs=[
                _source_ref("operator_controller_design_brief.json"),
                _source_ref("operator_controller_protocol.json"),
                _source_ref("system_question_answer_contract.json"),
            ],
            read_model_refs=[
                _source_ref("operator_controller_design_brief.json"),
                _source_ref("operator_controller_protocol.json"),
                _source_ref("system_question_answer_contract.json"),
            ],
            redacted_summary="Safe-next answers are controller guidance, not authority grants.",
            sensitive_detail_policy="read_model_summary_only",
        ),
        source_payloads=sources,
        workflow_ref="contextual_safe_next_question",
        entity_refs=["controller:mission_control"],
        object_refs=["question:safe_next"],
        danger_label="Execute protected action",
        danger_reason="Protected action execution is never available from a contextual answer card.",
    )


def _precondition_rows(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for precondition_ref, spec in PRECONDITIONS.items():
        payload = _load_json(root / str(spec["filename"]))
        status_keys = tuple(spec.get("status_keys") or ("status", "readiness_status", "contract_status"))
        observed = _status(payload, status_keys)
        accepted = tuple(spec.get("accepted_statuses") or (str(spec["required_status"]), str(spec.get("equivalent_status") or "")))
        accepted = tuple(status for status in accepted if status)
        rows.append(
            {
                "precondition_ref": precondition_ref,
                "required_status": str(spec["required_status"]),
                "observed_status": observed,
                "equivalent_status_accepted": str(spec.get("equivalent_status") or ""),
                "ready": observed in accepted,
                "source_ref": _source_ref(str(spec["filename"])),
            }
        )
    return rows


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


def validate_packet(packet: Mapping[str, Any], action_index: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    for field in REQUIRED_PACKET_FIELDS:
        if field not in packet:
            errors.append(f"packet:{field}_missing")
    if packet.get("schema_version") != SCHEMA_VERSION:
        errors.append("packet:schema_version_not_v1")
    cards = packet.get("cards")
    if not isinstance(cards, list) or not cards:
        errors.append("cards_missing")
        cards = []
    enabled_action_ids: list[str] = []
    disabled_action_ids: list[str] = []
    families_present: set[str] = set()
    for card in cards:
        if not isinstance(card, Mapping):
            errors.append("card_not_object")
            continue
        card_id = str(card.get("card_id") or "unknown_card")
        for field in REQUIRED_CARD_FIELDS:
            if field not in card:
                errors.append(f"{card_id}:{field}_missing")
        if card.get("card_family") not in CARD_FAMILIES:
            errors.append(f"{card_id}:card_family_missing_or_invalid")
        else:
            families_present.add(str(card["card_family"]))
        if card.get("trust_state") not in TRUST_STATES:
            errors.append(f"{card_id}:trust_state_missing_or_invalid")
        errors.extend(lifecycle_policy.validate_card_lifecycle(card))
        if card.get("card_type") not in CARD_TYPES:
            errors.append(f"{card_id}:card_type_invalid")
        if card.get("speaker_ref") not in SPEAKER_REFS:
            errors.append(f"{card_id}:speaker_ref_invalid")
        proof = card.get("proof")
        if not isinstance(proof, Mapping) or proof.get("collapsed_by_default") is not True:
            errors.append(f"{card_id}:proof_not_collapsed_by_default")
            proof = {}
        for field in REQUIRED_PROOF_FIELDS:
            if field not in proof:
                errors.append(f"{card_id}:proof.{field}_missing")
        if proof and proof.get("sensitive_detail_policy") in {"", None}:
            errors.append(f"{card_id}:proof.sensitive_detail_policy_missing")
        authority = card.get("authority_boundary")
        if not isinstance(authority, Mapping) or any(value is not False for value in authority.values()):
            errors.append(f"{card_id}:authority_boundary_not_all_false")
        action_slots = card.get("action_slots")
        if not isinstance(action_slots, Mapping):
            errors.append(f"{card_id}:action_slots_missing")
            action_slots = {}
        for slot_name in ACTION_SLOTS:
            slot = action_slots.get(slot_name) if isinstance(action_slots, Mapping) else None
            if not isinstance(slot, Mapping):
                errors.append(f"{card_id}:action_slot.{slot_name}_missing")
                continue
            for field in REQUIRED_ACTION_SLOT_FIELDS:
                if field not in slot:
                    errors.append(f"{card_id}:action_slot.{slot_name}.{field}_missing")
            slot_authority = slot.get("authority_boundary")
            if not isinstance(slot_authority, Mapping) or any(value is not False for value in slot_authority.values()):
                errors.append(f"{card_id}:action_slot.{slot_name}.authority_boundary_not_all_false")
            slot_action_id = str(slot.get("action_id") or "")
            slot_payload_ref = str(slot.get("action_payload_ref") or "")
            if slot.get("enabled") is True:
                enabled_action_ids.append(slot_action_id)
                if not slot_action_id:
                    errors.append(f"{card_id}:action_slot.{slot_name}.enabled_action_id_missing")
                if slot_action_id not in action_index:
                    errors.append(f"{card_id}:action_slot.{slot_name}.{slot_action_id}:enabled_action_missing_deterministic_payload")
                if not slot_payload_ref.startswith("generated/read_models/operator_action_payloads.json#"):
                    errors.append(f"{card_id}:action_slot.{slot_name}.{slot_action_id}:enabled_action_payload_ref_missing")
            else:
                disabled_action_ids.append(slot_action_id)
                if not slot.get("disabled_reason"):
                    errors.append(f"{card_id}:action_slot.{slot_name}.disabled_reason_missing")
        for action in card.get("actions") or []:
            if not isinstance(action, Mapping):
                errors.append(f"{card_id}:action_not_object")
                continue
            action_id = str(action.get("action_id") or "")
            if action.get("action_type") not in ACTION_TYPES:
                errors.append(f"{card_id}:{action_id}:action_type_invalid")
            if action.get("enabled") is True:
                enabled_action_ids.append(action_id)
                if action_id not in action_index:
                    errors.append(f"{card_id}:{action_id}:enabled_action_missing_deterministic_payload")
                if not str(action.get("payload_ref") or "").startswith("generated/read_models/operator_action_payloads.json#"):
                    errors.append(f"{card_id}:{action_id}:enabled_action_payload_ref_missing")
                if action.get("business_action") is True:
                    errors.append(f"{card_id}:{action_id}:enabled_business_action")
            else:
                disabled_action_ids.append(action_id)
                if not action.get("disabled_reason"):
                    errors.append(f"{card_id}:{action_id}:disabled_reason_missing")
    missing_families = sorted(set(CARD_FAMILIES) - families_present)
    if missing_families:
        errors.extend(f"missing_card_family:{family}" for family in missing_families)
    unsafe = unsafe_true_grants(packet)
    if unsafe:
        errors.extend(f"unsafe_true_grant:{key}" for key in unsafe)
    return {
        "valid": not errors,
        "errors": errors,
        "enabled_action_ids": enabled_action_ids,
        "disabled_action_ids": disabled_action_ids,
        "all_visible_cards_have_trust_state": all(
            isinstance(card, Mapping) and card.get("trust_state") in TRUST_STATES
            for card in cards
            if isinstance(card, Mapping) and card.get("visible_by_default") is True
        ),
        "enabled_actions_reference_deterministic_payloads": all(action_id in action_index for action_id in enabled_action_ids),
        "all_required_card_families_present": not missing_families,
        "required_card_families_present": sorted(families_present),
        "missing_card_families": missing_families,
        "proof_collapsed_by_default": all(
            isinstance(card, Mapping)
            and isinstance(card.get("proof"), Mapping)
            and card["proof"].get("collapsed_by_default") is True
            for card in cards
        ),
        "proof_categorized": all(
            isinstance(card, Mapping)
            and isinstance(card.get("proof"), Mapping)
            and all(field in card["proof"] for field in REQUIRED_PROOF_FIELDS)
            for card in cards
        ),
        "action_slots_present": all(
            isinstance(card, Mapping)
            and isinstance(card.get("action_slots"), Mapping)
            and all(slot in card["action_slots"] for slot in ACTION_SLOTS)
            for card in cards
        ),
        "lifecycle_fields_present": all(
            isinstance(card, Mapping)
            and all(field in card for field in lifecycle_policy.REQUIRED_CARD_FIELDS)
            and all(field in card for field in REQUIRED_CARD_FIELDS)
            for card in cards
        ),
        "unsafe_true_grants": unsafe,
        "unsafe_true_grants_absent": not unsafe,
    }


def build_latest_packet(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    sources = _source_payloads(read_model_root)
    action_index = _action_index(sources.get("operator_action_payloads", {}))
    preconditions = _precondition_rows(read_model_root)
    cards = [
        _capital_hilton_payment_watch_card(sources, action_index),
        _evidence_intake_card(sources),
        _contextual_question_card(sources, action_index),
        _review_packet_card(sources, action_index),
        _business_development_card(sources, action_index),
        _approval_request_card(sources, action_index),
        _check_engine_card(sources, action_index),
        _workbook_registration_card(sources, action_index),
        _contextual_safe_next_card(sources, action_index),
        _st_annes_work_log_card(sources),
        _memory_candidate_card(sources),
        _artifact_proof_card(sources),
    ]
    cards = sorted(cards, key=lambda card: (-int(card["priority"]), str(card["card_id"])))
    packet: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": LATEST_READ_MODEL_ID,
        "status": READY_STATUS if all(row["ready"] for row in preconditions) else NOT_READY_STATUS,
        "packet_id": f"dynamic_card_packet:{_short_hash(generated_at, len(cards))}",
        "generated_at": generated_at,
        "surface_context": {
            "world_ref": "mission_control",
            "thread_ref": "operator_surface",
            "workflow_ref": "dynamic_card_packet",
            "client_ref": "mixed",
            "active_entity_ref": "operator_current_surface",
        },
        "source_request_id": "read_model_export:dynamic_card_packet_v1",
        "packet_source_read_model_refs": [_source_ref(filename) for filename in SOURCE_FILENAMES.values()],
        "cards": cards,
        "packet_content_hash": _content_hash(
            {
                "schema_version": SCHEMA_VERSION,
                "source_refs": [_source_ref(filename) for filename in SOURCE_FILENAMES.values()],
                "cards": cards,
            }
        ),
        "card_count": len(cards),
        "visible_card_count": sum(1 for card in cards if card.get("visible_by_default") is True),
        "history_card_count": sum(
            1 for card in cards if card.get("lifecycle_state") in {"resolved", "archived"}
        ),
        "operator_attention_card_count": sum(
            1 for card in cards if card.get("operator_attention_required") is True
        ),
        "source_refs": [_source_ref(filename) for filename in SOURCE_FILENAMES.values()],
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    validation = validate_packet(packet, action_index)
    packet["machine_proof"] = {
        "preconditions_ready": all(row["ready"] for row in preconditions),
        "dynamic_card_packet_generated": True,
        "backend_generated_operator_surface": True,
        "human_copy_first": True,
        "machine_contracts_hidden_by_default": True,
        "proof_collapsed_by_default": validation["proof_collapsed_by_default"],
        "proof_categorized": validation["proof_categorized"],
        "action_slots_present": validation["action_slots_present"],
        "all_required_card_families_present": validation["all_required_card_families_present"],
        "required_card_families_present": validation["required_card_families_present"],
        "missing_card_families": validation["missing_card_families"],
        "all_visible_cards_have_trust_state": validation["all_visible_cards_have_trust_state"],
        "enabled_actions_reference_deterministic_payloads": validation["enabled_actions_reference_deterministic_payloads"],
        "lifecycle_fields_present": validation["lifecycle_fields_present"],
        "lifecycle_policy_ref": LIFECYCLE_POLICY_REF,
        "no_card_invents_authority": validation["valid"],
        "incoming_authority_granted_accepted": False,
        "incoming_authority_granted_rejected_or_ignored": True,
        "mac_does_not_need_client_specific_card_ids": True,
        "controller_shell_not_brain": True,
        "cards_cost_attention": True,
        "controller_95_control_5_status": True,
        "proof_is_metering_and_detail_drawer_not_primary_ui": True,
        "lm_output_is_not_truth": True,
        "receipts_read_models_proof_refs_define_truth": True,
        "payment_truth_requires_payment_evidence": True,
        "generated_summaries_do_not_override_receipts": True,
        "memory_candidates_do_not_become_truth": True,
        "external_llm_invoked": False,
        "local_model_runtime_connected": False,
        "worker_spawn_performed": False,
        "worker_execution_performed": False,
        "child_agent_run_performed": False,
        "email_send_performed": False,
        "gmail_access_performed": False,
        "browser_access_performed": False,
        "coupa_access_performed": False,
        "coupa_submit_performed": False,
        "ledger_mutation_performed": False,
        "workbook_open_performed": False,
        "workbook_body_read_performed": False,
        "spreadsheet_cell_read_performed": False,
        "workbook_mutation_performed": False,
        "excel_automation_performed": False,
        "pdf_export_performed": False,
        "paid_marking_performed": False,
        "submit_performed": False,
        "business_action_performed": False,
        "repair_performed": False,
        "merge_performed": False,
        "git_push_performed": False,
        "unsafe_true_grants": validation["unsafe_true_grants"],
        "unsafe_true_grants_absent": validation["unsafe_true_grants_absent"],
        "validation_errors": validation["errors"],
    }
    return packet


def build_contract_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    latest = build_latest_packet(read_model_root=read_model_root, generated_at=generated_at)
    preconditions = latest["preconditions"]
    payload: dict[str, Any] = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "read_model_id": CONTRACT_READ_MODEL_ID,
        "status": READY_STATUS if latest["status"] == READY_STATUS else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Backend-generated operator cards for Mission Control without custom SwiftUI per workflow.",
        "latest_packet_ref": _source_ref(LATEST_JSON_EXPORT_NAME),
        "output_schema_version": SCHEMA_VERSION,
        "required_top_level_fields": list(REQUIRED_PACKET_FIELDS),
        "card_schema": {
            "card_families": list(CARD_FAMILIES),
            "card_types": list(CARD_TYPES),
            "speaker_refs": list(SPEAKER_REFS),
            "tones": list(TONES),
            "trust_states": list(TRUST_STATES),
            "action_types": list(ACTION_TYPES),
            "action_slots": list(ACTION_SLOTS),
            "required_card_fields": list(REQUIRED_CARD_FIELDS),
            "required_action_slot_fields": list(REQUIRED_ACTION_SLOT_FIELDS),
            "required_proof_fields": list(REQUIRED_PROOF_FIELDS),
            "lifecycle_states": list(lifecycle_policy.LIFECYCLE_STATES),
            "freshness_states": list(lifecycle_policy.FRESHNESS_STATES),
            "required_lifecycle_fields": list(lifecycle_policy.REQUIRED_CARD_FIELDS),
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        },
        "rules": [
            "Mac must not need client-specific card ids.",
            "Every visible card has trust, freshness, and lifecycle fields.",
            "Every card must have card_family.",
            "Every card must have fixed action_slots: primary, secondary, detail, dismiss, and danger_disabled.",
            "Proof is metering and detail drawer metadata, not primary UI.",
            "Every card must have trust_state.",
            "Every enabled action must reference an existing operator_action_payload.",
            "Incoming authority_granted is never accepted from card/action input.",
            "Disabled actions must include disabled_reason.",
            "No card may invent authority.",
            "Proof/details are collapsed by default.",
            "Machine contracts are hidden by default.",
            "Human copy appears before backend ids.",
            "Generated summaries cannot override receipts.",
            "Memory candidates cannot become truth.",
            "Payment truth cannot come from email, Coupa, or proposal status without payment evidence.",
            "Every card must include lifecycle_state, freshness_state, operator_attention_required, collapse_when_resolved, and primary_control_ref.",
            "Resolved and archived cards are hidden by default and collapse into Completed / History.",
            "Stale cards must say Needs verification.",
            "Proof-only and machine-contract cards are hidden in operator mode unless requested.",
        ],
        "required_example_cards": [
            "Finance / Capital Hilton payment watch",
            "Contextual question answer for Finance / Capital Hilton",
            "Build review packet",
            "Business Development / Capital Hilton proposal",
            "Protected Coupa submit approval request",
            "Check Engine diagnostic",
            "Workbook registration",
            "Contextual safe-next question",
            "St. Anne's work-log review",
            "Evidence intake payment-processing artifact",
            "Memory candidate hidden card",
            "Artifact proof hidden card",
        ],
        "example_packet_digest": {
            "packet_id": latest["packet_id"],
            "card_count": latest["card_count"],
            "visible_card_count": latest["visible_card_count"],
            "card_ids": [card["card_id"] for card in latest["cards"]],
        },
        "preconditions": preconditions,
        "source_refs": latest["source_refs"],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "preconditions_ready": all(row["ready"] for row in preconditions),
            "contract_only": True,
            "latest_packet_valid": latest["machine_proof"]["no_card_invents_authority"],
            "all_visible_cards_have_trust_state": latest["machine_proof"]["all_visible_cards_have_trust_state"],
            "enabled_actions_reference_deterministic_payloads": latest["machine_proof"]["enabled_actions_reference_deterministic_payloads"],
            "proof_collapsed_by_default": latest["machine_proof"]["proof_collapsed_by_default"],
            "proof_categorized": latest["machine_proof"]["proof_categorized"],
            "action_slots_present": latest["machine_proof"]["action_slots_present"],
            "all_required_card_families_present": latest["machine_proof"]["all_required_card_families_present"],
            "lifecycle_fields_present": latest["machine_proof"]["lifecycle_fields_present"],
            "lifecycle_policy_ref": LIFECYCLE_POLICY_REF,
            "incoming_authority_granted_accepted": False,
            "incoming_authority_granted_rejected_or_ignored": True,
            "mac_does_not_need_client_specific_card_ids": True,
            "controller_shell_not_brain": True,
            "external_llm_invoked": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
            "worker_execution_performed": False,
            "child_agent_run_performed": False,
            "email_send_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_body_read_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "business_action_performed": False,
            "merge_performed": False,
            "git_push_performed": False,
            "unsafe_true_grants": unsafe_true_grants(latest),
            "unsafe_true_grants_absent": not unsafe_true_grants(latest),
        },
    }
    return payload


def build_wiki(contract: Mapping[str, Any], latest: Mapping[str, Any]) -> str:
    lines = [
        "# Dynamic Card Packet",
        "",
        f"Status: `{latest.get('status', NOT_READY_STATUS)}`",
        "",
        "The Dynamic Card Packet is the backend-generated operator card surface for Mission Control. It lets the Mac render current answers, status, safe next actions, proof drawers, trust state, and safe buttons without custom SwiftUI for every workflow.",
        "",
        "`dynamic_card_packet_v1` is a controller-grade packet: the Mac renders card families and action slots, not workflow-specific card ids.",
        "",
        "## Boundary",
        "",
        "- No live LM1 or LM2.",
        "- No worker spawn or child-agent run.",
        "- No external LLM or local model runtime.",
        "- No email, Gmail, browser, Coupa, ledger, workbook, PDF, submit, mark-paid, merge, push, or repair authority.",
        "- Enabled actions only reference deterministic `operator_action_payloads.json` payloads.",
        "- Proof/details are collapsed by default.",
        "- Incoming `authority_granted` is rejected or ignored; cards never grant authority.",
        "- Payment-processing evidence never marks paid or mutates the ledger.",
        "",
        "## Cards",
        "",
    ]
    for card in latest.get("cards") or []:
        if not isinstance(card, Mapping):
            continue
        lines.extend(
            [
                f"### {card.get('headline')}",
                "",
                f"- Card id: `{card.get('card_id')}`",
                f"- Family: `{card.get('card_family')}`",
                f"- Type: `{card.get('card_type')}`",
                f"- Speaker: `{card.get('speaker_ref')}`",
                f"- Trust: `{card.get('trust_state')}`",
                f"- Freshness: `{card.get('freshness_state')}`",
                f"- Lifecycle: `{card.get('lifecycle_state')}`",
                f"- Confidence: `{card.get('confidence_class')}` / `{card.get('confidence_score')}`",
                f"- Summary: {card.get('plain_summary')}",
                f"- Next/status: `{card.get('status_label')}`",
                f"- Visible by default: `{str(card.get('visible_by_default')).lower()}`",
                "",
            ]
        )
        action_slots = card.get("action_slots") if isinstance(card.get("action_slots"), Mapping) else {}
        if action_slots:
            lines.append("Action slots:")
            for slot_name in ACTION_SLOTS:
                slot = action_slots.get(slot_name)
                if isinstance(slot, Mapping):
                    lines.append(
                        f"- `{slot_name}`: `{slot.get('controller_event_type')}` / `{slot.get('label')}` / enabled=`{str(slot.get('enabled')).lower()}`"
                    )
            lines.append("")
        proof = card.get("proof") if isinstance(card.get("proof"), Mapping) else {}
        if proof:
            lines.extend(
                [
                    "Proof categories:",
                    f"- receipts=`{len(proof.get('receipt_refs') or [])}` artifacts=`{len(proof.get('artifact_refs') or [])}` hashes=`{len(proof.get('hash_refs') or [])}` sqlite=`{len(proof.get('sqlite_refs') or [])}` read_models=`{len(proof.get('read_model_refs') or [])}`",
                    "",
                ]
            )
    lines.extend(
        [
            "## Contract",
            "",
            f"- Contract read model: `generated/read_models/{CONTRACT_JSON_EXPORT_NAME}`",
            f"- Latest packet: `generated/read_models/{LATEST_JSON_EXPORT_NAME}`",
            f"- Required example cards: `{len(contract.get('required_example_cards') or [])}`",
            f"- Required card families: `{len(CARD_FAMILIES)}`",
            f"- Required action slots: `{', '.join(ACTION_SLOTS)}`",
            "",
            "## Machine Proof",
            "",
            f"- All visible cards have trust state: `{str((latest.get('machine_proof') or {}).get('all_visible_cards_have_trust_state')).lower()}`",
            f"- Enabled actions reference deterministic payloads: `{str((latest.get('machine_proof') or {}).get('enabled_actions_reference_deterministic_payloads')).lower()}`",
            f"- Action slots present: `{str((latest.get('machine_proof') or {}).get('action_slots_present')).lower()}`",
            f"- Proof categorized: `{str((latest.get('machine_proof') or {}).get('proof_categorized')).lower()}`",
            f"- Required families present: `{str((latest.get('machine_proof') or {}).get('all_required_card_families_present')).lower()}`",
            f"- Unsafe true grants absent: `{str((latest.get('machine_proof') or {}).get('unsafe_true_grants_absent')).lower()}`",
        ]
    )
    return "\n".join(lines) + "\n"


def export_dynamic_card_packet(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    generated_at = generated_at or utc_now()
    contract = build_contract_read_model(read_model_root=read_model_root, generated_at=generated_at)
    latest = build_latest_packet(read_model_root=read_model_root, generated_at=generated_at)

    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    contract_path = export_root / CONTRACT_JSON_EXPORT_NAME
    latest_path = export_root / LATEST_JSON_EXPORT_NAME
    contract_path.write_text(stable_json(contract), encoding="utf-8")
    latest_path.write_text(stable_json(latest), encoding="utf-8")

    bridge_contract_path = ""
    bridge_latest_path = ""
    if bridge_root is not None:
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_contract = bridge_root / CONTRACT_JSON_EXPORT_NAME
        bridge_latest = bridge_root / LATEST_JSON_EXPORT_NAME
        shutil.copy2(contract_path, bridge_contract)
        shutil.copy2(latest_path, bridge_latest)
        bridge_contract_path = bridge_contract.as_posix()
        bridge_latest_path = bridge_latest.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(contract, latest), encoding="utf-8")

    return {
        "status": str(latest["status"]),
        "contract_read_model_path": contract_path.as_posix(),
        "latest_read_model_path": latest_path.as_posix(),
        "bridge_contract_read_model_path": bridge_contract_path,
        "bridge_latest_read_model_path": bridge_latest_path,
        "wiki_path": wiki_path.as_posix(),
        "card_count": str(latest["card_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Dynamic Card Packet V1.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_dynamic_card_packet(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=None if args.no_bridge else Path(args.bridge_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result), end="")
    else:
        print(f"{result['status']}: {result['card_count']} cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
