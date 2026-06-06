"""Bounded proof bundle builder for proof-to-response LM shadow harness.

The bundle is the only input a future phrasing model may see. It contains
redacted proof refs and compact facts, not raw file bodies, app/device/session
verification material, credentials, or live provider state.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import proof_to_response_tdd_spec as proof_spec


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")

REQUIRED_BUNDLE_FIELDS = (
    "proof_bundle_id",
    "world_ref",
    "thread_ref",
    "objective_ref",
    "operator_question",
    "selected_card_ref",
    "receipt_refs",
    "read_model_refs",
    "proof_refs",
    "gate_refs",
    "proof_meters",
    "known_facts",
    "unknowns",
    "blocked_actions",
    "allowed_response_controls",
    "sensitive_detail_policy",
    "privacy_class",
    "excluded_context",
    "response_speaker_ref",
    "response_voice_mode",
)

SAFE_CONTROLLER_EVENTS = {
    "ask_why",
    "open_lane",
    "attach_proof",
    "stage_plan",
    "show_details",
    "mark_informational",
    "request_rework",
    "stop_hold_cancel",
}

SENSITIVE_TEXT_MARKERS = (
    "raw_file_body",
    "operator_envelope",
    "device_verification",
    "session_verification",
    "secret",
    "token",
)

SOURCE_REFS = proof_spec.SOURCE_REFS


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


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


def _scenario_response(scenario_id: str, read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> dict[str, Any]:
    read_model = proof_spec.build_read_model(read_model_root=read_model_root)
    for response in read_model.get("example_responses", []):
        if response.get("scenario_id") == scenario_id:
            return response
    raise ValueError(f"unknown_scenario:{scenario_id}")


def _control(
    *,
    label: str,
    controller_event_type: str,
    action_payload_ref: str = "",
    enabled: bool = True,
    disabled_reason: str = "",
) -> dict[str, Any]:
    return {
        "label": label,
        "controller_event_type": controller_event_type,
        "action_payload_ref": action_payload_ref,
        "enabled": enabled,
        "disabled_reason": disabled_reason,
        "authority_boundary": {"protected_actions_allowed": False},
    }


def _fact(fact_id: str, text: str, source_refs: list[str]) -> dict[str, Any]:
    return {"fact_id": fact_id, "text": text, "source_refs": list(dict.fromkeys(source_refs))}


SCENARIO_OVERRIDES: dict[str, dict[str, Any]] = {
    "finance_capital_hilton_payment_watch": {
        "operator_question": "What should I know about Capital Hilton payment status?",
        "known_facts": [
            _fact("payment_evidence_missing", "Payment evidence is missing.", [SOURCE_REFS["dynamic_cards"], SOURCE_REFS["proof_meters"]]),
            _fact("coupa_processing", "Coupa is processing or under watch, not a completed payment truth.", [SOURCE_REFS["dynamic_cards"], SOURCE_REFS["objective"]]),
            _fact("ledger_untouched", "The ledger remains untouched until payment is confirmed.", [SOURCE_REFS["receipts"], SOURCE_REFS["objective"]]),
        ],
        "unknowns": ["payment_arrival_confirmation"],
        "blocked_actions": ["mark_paid", "mutate_ledger", "submit_coupa"],
        "allowed_response_controls": [
            _control(
                label="Attach proof",
                controller_event_type="attach_proof",
                action_payload_ref="generated/read_models/operator_action_payloads.json#action_payloads.capital_hilton.payment.record_proof",
            ),
            _control(
                label="Open Finance / Capital Hilton",
                controller_event_type="open_lane",
                action_payload_ref="generated/read_models/operator_action_payloads.json#action_payloads.capital_hilton.payment.open_finance",
            ),
        ],
        "privacy_class": "financial_sensitive/local_only",
    },
    "finance_live_arts_payment_evidence": {
        "operator_question": "What did this Live Arts MD payment proof change?",
        "known_facts": [
            _fact("candidate_evidence_recorded", "Payment-processing evidence was recorded as candidate/operator-reported evidence.", [SOURCE_REFS["evidence_intake"], SOURCE_REFS["receipts"]]),
            _fact("not_paid_truth", "The evidence does not mark the invoice paid.", [SOURCE_REFS["proof_meters"], SOURCE_REFS["receipts"]]),
            _fact("ledger_untouched", "The ledger remains untouched.", [SOURCE_REFS["receipts"], SOURCE_REFS["evidence_intake"]]),
        ],
        "unknowns": ["payment_arrival_confirmation", "ledger_evidence"],
        "blocked_actions": ["mark_paid", "mutate_ledger"],
        "allowed_response_controls": [
            _control(label="Verify arrival", controller_event_type="stage_plan"),
            _control(label="Attach stronger proof", controller_event_type="attach_proof"),
        ],
        "privacy_class": "financial_sensitive/local_only",
    },
    "business_development_capital_hilton_followup": {
        "operator_question": "Can we move the Capital Hilton follow-up forward?",
        "known_facts": [
            _fact("followup_stageable", "A Capital Hilton follow-up draft can be staged.", [SOURCE_REFS["workflow_package"], SOURCE_REFS["dynamic_cards"]]),
            _fact("no_email_send", "No email send is performed by this step.", [SOURCE_REFS["receipts"], SOURCE_REFS["actions"]]),
        ],
        "unknowns": [],
        "blocked_actions": ["send_email", "update_external_system"],
        "allowed_response_controls": [
            _control(
                label="Stage follow-up",
                controller_event_type="stage_plan",
                action_payload_ref="generated/read_models/operator_action_payloads.json#action_payloads.capital_hilton.proposal.stage_followup",
            ),
            _control(label="Show details", controller_event_type="show_details"),
        ],
        "privacy_class": "internal_operator_safe",
    },
    "build_review_packet": {
        "operator_question": "What is the review packet state?",
        "known_facts": [
            _fact("review_decision_recorded", "The review decision is recorded.", [SOURCE_REFS["review_decisions"], SOURCE_REFS["receipts"]]),
            _fact("review_packet_informational", "The review packet is closed or informational when the receipt says so.", [SOURCE_REFS["review_decisions"], SOURCE_REFS["proof_meters"]]),
            _fact("no_merge_or_push", "No merge, push, or worker spawn was performed.", [SOURCE_REFS["review_decisions"], SOURCE_REFS["receipts"]]),
        ],
        "unknowns": [],
        "blocked_actions": ["merge", "push", "spawn_worker"],
        "allowed_response_controls": [
            _control(label="Review packet", controller_event_type="show_details"),
            _control(label="Request rework", controller_event_type="request_rework"),
            _control(label="Mark informational", controller_event_type="mark_informational"),
        ],
        "privacy_class": "internal_operator_safe",
    },
    "unknown_context": {
        "operator_question": "Where should this response apply?",
        "known_facts": [
            _fact("lane_context_missing", "World and thread context are missing.", [SOURCE_REFS["controller_router"], SOURCE_REFS["objective"]]),
        ],
        "unknowns": ["world_ref", "thread_ref"],
        "blocked_actions": ["package_staging", "business_action_routing"],
        "allowed_response_controls": [
            _control(label="Choose lane", controller_event_type="open_lane"),
            _control(label="Stop", controller_event_type="stop_hold_cancel"),
        ],
        "privacy_class": "internal_operator_safe",
    },
    "protected_coupa_ledger_email_request": {
        "operator_question": "Can the protected finance action run?",
        "known_facts": [
            _fact("protected_action_blocked", "Protected action is blocked.", [SOURCE_REFS["gates"], SOURCE_REFS["receipts"]]),
            _fact("proof_and_approval_required", "Specific proof and approval are required before execution.", [SOURCE_REFS["gates"], SOURCE_REFS["actions"]]),
            _fact("no_execution", "No email send, Coupa submit, ledger change, or paid marking is performed.", [SOURCE_REFS["receipts"], SOURCE_REFS["gates"]]),
        ],
        "unknowns": ["specific_approval", "supporting_proof"],
        "blocked_actions": ["send_email", "coupa_submit", "mutate_ledger", "mark_paid"],
        "allowed_response_controls": [
            _control(
                label="Prepare approval",
                controller_event_type="stage_plan",
                action_payload_ref="generated/read_models/operator_action_payloads.json#action_payloads.guardian_gate.coupa_submit.stage_approval_request",
            ),
            _control(label="Attach proof", controller_event_type="attach_proof"),
            _control(
                label="Explain this gate",
                controller_event_type="ask_why",
                action_payload_ref="generated/read_models/operator_action_payloads.json#action_payloads.guardian_gate.coupa_submit.explain",
            ),
        ],
        "privacy_class": "financial_sensitive/local_only",
    },
}


def _read_model_refs(response: Mapping[str, Any]) -> list[str]:
    refs = list(response.get("source_refs") or [])
    refs.extend(
        [
            "generated/read_models/proof_to_response_tdd_spec.json",
            "generated/read_models/operator_action_payloads.json",
            "generated/read_models/operator_controller_protocol.json",
        ]
    )
    return list(dict.fromkeys(str(ref) for ref in refs if str(ref)))


def build_proof_bundle(
    scenario_id: str,
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
) -> dict[str, Any]:
    response = _scenario_response(scenario_id, read_model_root=read_model_root)
    override = SCENARIO_OVERRIDES.get(scenario_id)
    if override is None:
        raise ValueError(f"unknown_scenario:{scenario_id}")
    source_context = response.get("source_context") if isinstance(response.get("source_context"), Mapping) else {}
    receipt_refs = [str(ref) for ref in source_context.get("receipt_refs") or [] if str(ref)]
    proof_refs = [str(ref) for ref in source_context.get("proof_refs") or [] if str(ref)]
    gate_refs = [str(ref) for ref in source_context.get("gate_refs") or [] if str(ref)]
    proof_refs.extend(str(meter.get("source_ref")) for meter in response.get("proof_meters") or [] if meter.get("source_ref"))
    return {
        "proof_bundle_id": f"proof_bundle:{scenario_id}",
        "scenario_id": scenario_id,
        "world_ref": str(source_context.get("world_ref") or "unknown"),
        "thread_ref": str(source_context.get("thread_ref") or "unknown"),
        "objective_ref": str(source_context.get("objective_ref") or "unknown"),
        "operator_question": str(override["operator_question"]),
        "selected_card_ref": str(source_context.get("card_id") or "unknown"),
        "receipt_refs": receipt_refs,
        "read_model_refs": _read_model_refs(response),
        "proof_refs": list(dict.fromkeys(proof_refs)),
        "gate_refs": list(dict.fromkeys(gate_refs)),
        "proof_meters": list(response.get("proof_meters") or []),
        "known_facts": list(override["known_facts"]),
        "unknowns": list(override["unknowns"]),
        "blocked_actions": list(override["blocked_actions"]),
        "allowed_response_controls": list(override["allowed_response_controls"]),
        "sensitive_detail_policy": "redacted_summary_only",
        "privacy_class": str(override["privacy_class"]),
        "excluded_context": [
            "sensitive_attachment_body",
            "credential_material",
            "operator_device_session_auth_material",
            "external_provider_payloads",
        ],
        "response_speaker_ref": str(response.get("speaker_ref") or "openclaw"),
        "response_voice_mode": str(response.get("voice_mode") or "brief"),
    }


def _action_payload_ids(read_model_root: Path) -> set[str]:
    payload = _load_json(_rooted(read_model_root) / "operator_action_payloads.json")
    values = payload.get("action_payload_ids")
    if isinstance(values, list):
        return {str(value) for value in values}
    rows = payload.get("action_payloads")
    if isinstance(rows, list):
        return {str(row.get("action_id")) for row in rows if isinstance(row, Mapping) and row.get("action_id")}
    return set()


def validate_proof_bundle(
    bundle: Mapping[str, Any],
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_BUNDLE_FIELDS:
        if field not in bundle:
            errors.append(f"missing_field:{field}")
    for field in ("receipt_refs", "read_model_refs", "proof_refs", "gate_refs", "proof_meters", "known_facts", "unknowns", "blocked_actions", "allowed_response_controls", "excluded_context"):
        if field in bundle and not isinstance(bundle.get(field), list):
            errors.append(f"not_list:{field}")
    text = stable_json(bundle).lower()
    for marker in SENSITIVE_TEXT_MARKERS:
        if marker in text:
            errors.append(f"sensitive_marker_present:{marker}")
    allowed_action_ids = _action_payload_ids(read_model_root)
    for idx, control in enumerate(bundle.get("allowed_response_controls") or []):
        if not isinstance(control, Mapping):
            errors.append(f"control_not_object:{idx}")
            continue
        event_type = str(control.get("controller_event_type") or "")
        if event_type not in SAFE_CONTROLLER_EVENTS:
            errors.append(f"control_unsafe_event:{idx}:{event_type}")
        boundary = control.get("authority_boundary")
        if not isinstance(boundary, Mapping) or boundary.get("protected_actions_allowed") is not False:
            errors.append(f"control_boundary_not_false:{idx}")
        ref = str(control.get("action_payload_ref") or "")
        if ref.startswith("generated/read_models/operator_action_payloads.json#action_payloads."):
            action_id = ref.split("#action_payloads.", 1)[1]
            if action_id not in allowed_action_ids:
                errors.append(f"control_action_payload_missing:{idx}:{action_id}")
    return errors
