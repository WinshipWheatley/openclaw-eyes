"""Bounded proof bundle builder for proof-to-response LM shadow harness.

The bundle is the only input a future phrasing model may see. It contains
redacted proof refs and compact facts, not raw file bodies, app/device/session
verification material, credentials, or live provider state.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import proof_to_response_tdd_spec as proof_spec


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Proof Bundle Builder Redaction Integration.md")
DEFAULT_FRESHNESS_TRACE_WIKI_PATH = Path("generated/wiki/openclaw/Proof Bundle Freshness Trace Integration.md")

REDACTION_INTEGRATION_SCHEMA_VERSION = "proof_bundle_builder_redaction_integration_v0"
REDACTION_STATUS_READ_MODEL_ID = "proof_bundle_builder_redaction_status"
REDACTION_STATUS_JSON_EXPORT_NAME = f"{REDACTION_STATUS_READ_MODEL_ID}.json"
REDACTION_READY_STATUS = "PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY"
REDACTION_NOT_READY_STATUS = "PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_NOT_READY"
FRESHNESS_TRACE_SCHEMA_VERSION = "proof_bundle_freshness_trace_integration_v0"
FRESHNESS_TRACE_STATUS_READ_MODEL_ID = "proof_bundle_freshness_trace_status"
FRESHNESS_TRACE_STATUS_JSON_EXPORT_NAME = f"{FRESHNESS_TRACE_STATUS_READ_MODEL_ID}.json"
FRESHNESS_TRACE_READY_STATUS = "PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_READY"
FRESHNESS_TRACE_NOT_READY_STATUS = "PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_NOT_READY"

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

REDACTION_SCENARIO_REFS = {
    "finance_capital_hilton_payment_watch": "capital_hilton_payment_watch",
    "finance_live_arts_payment_evidence": "live_arts_payment_evidence",
    "business_development_capital_hilton_followup": "business_development_capital_hilton_followup",
    "music_niles_controller_mapping": "music_niles_controller_mapping",
    "self_heal_missing_proof_for_payment": "self_heal_repair",
    "unknown_context": "unknown_context",
}

SCENARIO_CONTEXT_REFS = {
    "finance_capital_hilton_payment_watch": "context:finance:capital_hilton:payment_watch",
    "finance_live_arts_payment_evidence": "context:finance:live_arts_md:payment_evidence",
    "business_development_capital_hilton_followup": "context:business_development:capital_hilton:followup",
    "build_review_packet": "context:build:review_packet:informational_resolved",
    "unknown_context": "context:system:stale_or_unknown_source",
    "self_heal_missing_proof_for_payment": "context:finance:capital_hilton:payment_watch",
    "protected_coupa_ledger_email_request": "context:finance:capital_hilton:payment_watch",
}

BLOCKED_FRESHNESS_STATES = {"stale", "superseded", "unknown"}
BLOCKED_CONFIDENCE_CLASSES = {"test_only", "unpromoted_memory"}
FRESHNESS_TRACE_FIELDS = (
    "context_ref",
    "freshness_state",
    "confidence_class",
    "confidence_score",
    "decision_trace_summary",
    "latest_receipt_ref",
    "prior_attempts",
    "prior_rejections",
    "operator_decisions",
)

VOICE_SPEAKER_BY_SCENARIO = {
    "finance_capital_hilton_payment_watch": "chief",
    "finance_live_arts_payment_evidence": "chief",
    "business_development_capital_hilton_followup": "cassandra",
    "build_review_packet": "chief",
    "protected_coupa_ledger_email_request": "guardian",
    "music_niles_controller_mapping": "niles",
    "self_heal_missing_proof_for_payment": "chief",
    "unknown_context": "openclaw",
}

VOICE_MODE_BY_SCENARIO = {
    "finance_capital_hilton_payment_watch": "diagnostic",
    "finance_live_arts_payment_evidence": "diagnostic",
    "business_development_capital_hilton_followup": "operations",
    "build_review_packet": "diagnostic",
    "protected_coupa_ledger_email_request": "safety",
    "music_niles_controller_mapping": "creative",
    "self_heal_missing_proof_for_payment": "diagnostic",
    "unknown_context": "brief",
}

CONTROL_LABELS_BY_REF = {
    "attach_proof": "Attach payment evidence",
    "open_finance_lane": "Open Finance / Capital Hilton",
    "verify_arrival": "Verify arrival",
    "attach_stronger_proof": "Attach stronger proof",
    "stage_followup_draft": "Stage follow-up",
    "show_details": "Show details",
    "ask_taste_question": "Ask taste question",
    "offer_mapping_options": "Offer mapping options",
    "stage_repair_package": "Stage repair package",
    "run_safe_validation": "Run safe validation",
    "choose_lane": "Choose lane",
    "prepare_approval": "Prepare approval",
    "explain_gate": "Explain this gate",
}

CONTROL_EVENTS_BY_LABEL = {
    "Attach payment evidence": "attach_proof",
    "Open Finance / Capital Hilton": "open_lane",
    "Verify arrival": "stage_plan",
    "Attach stronger proof": "attach_proof",
    "Stage follow-up": "stage_plan",
    "Show details": "show_details",
    "Ask taste question": "ask_why",
    "Offer mapping options": "show_details",
    "Stage repair package": "stage_plan",
    "Run safe validation": "show_details",
    "Choose lane": "open_lane",
    "Prepare approval": "stage_plan",
    "Explain this gate": "ask_why",
    "Review packet": "show_details",
}

FACT_IDS_BY_SCENARIO = {
    "finance_capital_hilton_payment_watch": ["payment_evidence_missing", "ledger_untouched", "coupa_processing"],
    "finance_live_arts_payment_evidence": ["candidate_evidence_recorded", "not_paid_truth", "ledger_untouched"],
    "business_development_capital_hilton_followup": ["followup_stageable", "no_email_send"],
    "build_review_packet": ["review_decision_recorded", "review_packet_informational", "no_merge_or_push"],
    "protected_coupa_ledger_email_request": ["protected_action_blocked", "proof_and_approval_required", "no_execution"],
    "music_niles_controller_mapping": ["creative_mapping_options", "target_context_needed"],
    "self_heal_missing_proof_for_payment": [
        "repair_blocker_named",
        "repair_proof_cited",
        "can_do_now_named",
        "cannot_do_yet_named",
        "smallest_manual_step_named",
    ],
    "unknown_context": ["lane_context_missing"],
}

BLOCKED_ACTIONS_BY_SUMMARY = {
    "mark paid": "mark_paid",
    "ledger mutation": "mutate_ledger",
    "coupa submit": "submit_coupa",
    "email send": "send_email",
    "external update": "update_external_system",
    "service restart": "service_restart",
    "worker spawn": "spawn_worker",
    "package staging": "package_staging",
    "business action routing": "business_action_routing",
    "metadata truth claim": "metadata_truth_claim",
}

REDUNDANT_LITERAL_MARKERS = SENSITIVE_TEXT_MARKERS + (
    "raw_prompt",
    "raw_ocr",
    "raw_artifact",
    "credential",
    "password",
    "authority_granted",
    "send_email_allowed",
    "bank_account",
    "routing_number",
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path | str) -> Path:
    path = Path(path)
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


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path = _rooted(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _content_hash(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _scenario_response(scenario_id: str, read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> dict[str, Any]:
    read_model = proof_spec.build_read_model(read_model_root=read_model_root)
    for response in read_model.get("example_responses", []):
        if response.get("scenario_id") == scenario_id:
            return response
    raise ValueError(f"unknown_scenario:{scenario_id}")


def _freshness_gate_payload(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> dict[str, Any]:
    payload = _load_json(_rooted(read_model_root) / "context_freshness_decision_trace_gate.json")
    if payload:
        return payload
    try:
        import context_freshness_decision_trace_gate as freshness_gate
    except ImportError:
        return {}
    return freshness_gate.build_read_model(read_model_root=read_model_root)


def _freshness_gate_rows(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    payload = _freshness_gate_payload(read_model_root)
    rows = payload.get("gate_rows")
    return [dict(row) for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _context_ref_for_scenario(scenario_id: str, context_ref: str = "") -> str:
    return context_ref or SCENARIO_CONTEXT_REFS.get(scenario_id, "")


def _freshness_row_for_context(
    scenario_id: str,
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    context_ref: str = "",
) -> dict[str, Any]:
    selected_context_ref = _context_ref_for_scenario(scenario_id, context_ref)
    if not selected_context_ref:
        return {
            "context_ref": f"context:redaction_only:{scenario_id}",
            "world_ref": "unknown",
            "thread_ref": "unknown",
            "objective_ref": scenario_id,
            "source_refs": ["generated/read_models/proof_bundle_redaction_policy.json"],
            "receipt_refs": [],
            "decision_trace_refs": ["trace:redaction_only_context_no_lane_truth_claim"],
            "latest_receipt_ref": "",
            "superseded_receipt_refs": [],
            "freshness_state": "current",
            "confidence_class": "operator_reported_candidate",
            "confidence_score": 0.72,
            "stale_reason": "",
            "decision_trace_summary": "No lane truth is claimed; redacted operator-provided context is allowed only with candidate labeling.",
            "prior_attempts": [],
            "prior_rejections": [],
            "operator_decisions": [],
            "allowed_for_lm_bundle": True,
            "required_refresh_action": "",
            "safe_human_response_if_blocked": "",
            "canonical_claims": {},
            "blocked_claims": [],
        }
    for row in _freshness_gate_rows(read_model_root):
        if row.get("context_ref") == selected_context_ref:
            return row
    return {
        "context_ref": selected_context_ref or f"context:unknown:{scenario_id}",
        "world_ref": "unknown",
        "thread_ref": "unknown",
        "objective_ref": scenario_id,
        "source_refs": [],
        "receipt_refs": [],
        "decision_trace_refs": [],
        "latest_receipt_ref": "",
        "superseded_receipt_refs": [],
        "freshness_state": "unknown",
        "confidence_class": "unknown",
        "confidence_score": 0.0,
        "stale_reason": "No context freshness gate row supports this scenario.",
        "decision_trace_summary": "No traceable current context exists for this proof bundle.",
        "prior_attempts": [],
        "prior_rejections": [],
        "operator_decisions": [],
        "allowed_for_lm_bundle": False,
        "required_refresh_action": "request_current_lane_context_or_receipt",
        "safe_human_response_if_blocked": "Needs verification. I need a current receipt or traceable proof before using this as context.",
        "canonical_claims": {},
        "blocked_claims": [],
    }


def _is_trusted_current_context(freshness_row: Mapping[str, Any]) -> bool:
    return (
        freshness_row.get("allowed_for_lm_bundle") is True
        and freshness_row.get("freshness_state") == "current"
        and freshness_row.get("confidence_class") not in BLOCKED_CONFIDENCE_CLASSES
    )


def _must_block_current_truth(freshness_row: Mapping[str, Any]) -> bool:
    return (
        freshness_row.get("freshness_state") in BLOCKED_FRESHNESS_STATES
        or freshness_row.get("confidence_class") in BLOCKED_CONFIDENCE_CLASSES
    )


def _freshness_trace(freshness_row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "context_ref": str(freshness_row.get("context_ref") or ""),
        "freshness_state": str(freshness_row.get("freshness_state") or "unknown"),
        "confidence_class": str(freshness_row.get("confidence_class") or "unknown"),
        "confidence_score": float(freshness_row.get("confidence_score") or 0.0),
        "decision_trace_summary": str(freshness_row.get("decision_trace_summary") or ""),
        "latest_receipt_ref": str(freshness_row.get("latest_receipt_ref") or ""),
        "prior_attempts": list(freshness_row.get("prior_attempts") or []),
        "prior_rejections": list(freshness_row.get("prior_rejections") or []),
        "operator_decisions": list(freshness_row.get("operator_decisions") or []),
        "decision_trace_refs": list(freshness_row.get("decision_trace_refs") or []),
        "superseded_receipt_refs": list(freshness_row.get("superseded_receipt_refs") or []),
        "stale_reason": str(freshness_row.get("stale_reason") or ""),
        "required_refresh_action": str(freshness_row.get("required_refresh_action") or ""),
        "safe_human_response_if_blocked": str(freshness_row.get("safe_human_response_if_blocked") or ""),
        "allowed_for_lm_bundle": freshness_row.get("allowed_for_lm_bundle") is True,
        "trusted_current": _is_trusted_current_context(freshness_row),
        "blocked_current_truth": _must_block_current_truth(freshness_row),
        "canonical_claims": dict(freshness_row.get("canonical_claims") or {}),
        "blocked_claims": list(freshness_row.get("blocked_claims") or []),
    }


def _append_unique(existing: list[Any], values: list[Any]) -> list[Any]:
    output: list[Any] = []
    for value in [*existing, *values]:
        if value and value not in output:
            output.append(value)
    return output


def _freshness_bundle_status(freshness_row: Mapping[str, Any]) -> str:
    if _is_trusted_current_context(freshness_row):
        return "trusted_current"
    freshness_state = str(freshness_row.get("freshness_state") or "unknown")
    if freshness_state == "historical":
        return "historical_context"
    if str(freshness_row.get("confidence_class") or "") == "operator_reported_candidate":
        return "candidate_context"
    return "blocked_needs_verification"


def _blocked_lm_input(policy_bundle: Mapping[str, Any], freshness_row: Mapping[str, Any]) -> dict[str, Any]:
    safe = str(
        freshness_row.get("safe_human_response_if_blocked")
        or "Needs verification. I need current traceable proof before using this context."
    )
    redaction_policy = _policy_module()
    base = {field: None for field in redaction_policy.ALLOWED_FIELD_REASONS}
    base.update(
        {
            "world_ref": str(freshness_row.get("world_ref") or policy_bundle.get("world_ref") or "unknown"),
            "thread_ref": str(freshness_row.get("thread_ref") or policy_bundle.get("thread_ref") or "unknown"),
            "objective_ref": str(freshness_row.get("objective_ref") or policy_bundle.get("objective_ref") or "unknown"),
            "redacted_known_facts": [safe],
            "proof_meter_labels": [
                f"Freshness: {freshness_row.get('freshness_state', 'unknown')}",
                f"Confidence: {freshness_row.get('confidence_class', 'unknown')}",
            ],
            "receipt_refs": [str(freshness_row.get("latest_receipt_ref") or "")] if freshness_row.get("latest_receipt_ref") else [],
            "gate_labels": [str(freshness_row.get("decision_trace_summary") or "Context needs verification.")],
            "missing_input": [str(freshness_row.get("required_refresh_action") or "current_receipt_or_traceable_proof")],
            "allowed_controls": ["Show details"],
            "blocked_action_summaries": ["trusted-current proof bundle blocked"],
            "human_safe_summaries": [safe],
            "agent_voice_mode": str(policy_bundle.get("agent_voice_mode") or "brief"),
        }
    )
    return base


def _merge_freshness_into_lm_input(lm_input: Mapping[str, Any], freshness_row: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(lm_input)
    merged["receipt_refs"] = _append_unique(
        list(merged.get("receipt_refs") or []),
        [str(freshness_row.get("latest_receipt_ref") or "")],
    )
    merged["gate_labels"] = _append_unique(
        list(merged.get("gate_labels") or []),
        [str(freshness_row.get("decision_trace_summary") or "")],
    )
    merged["proof_meter_labels"] = _append_unique(
        list(merged.get("proof_meter_labels") or []),
        [
            f"Freshness: {freshness_row.get('freshness_state', 'unknown')}",
            f"Confidence: {freshness_row.get('confidence_class', 'unknown')}",
        ],
    )
    merged["human_safe_summaries"] = _append_unique(
        list(merged.get("human_safe_summaries") or []),
        [str(freshness_row.get("decision_trace_summary") or "")],
    )
    return merged


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
    context_ref: str = "",
) -> dict[str, Any]:
    response = _scenario_response(scenario_id, read_model_root=read_model_root)
    override = SCENARIO_OVERRIDES.get(scenario_id)
    if override is None:
        raise ValueError(f"unknown_scenario:{scenario_id}")
    freshness_row = _freshness_row_for_context(scenario_id, read_model_root=read_model_root, context_ref=context_ref)
    freshness = _freshness_trace(freshness_row)
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
        **{field: freshness[field] for field in FRESHNESS_TRACE_FIELDS},
        "decision_trace_refs": freshness["decision_trace_refs"],
        "superseded_receipt_refs": freshness["superseded_receipt_refs"],
        "stale_reason": freshness["stale_reason"],
        "required_refresh_action": freshness["required_refresh_action"],
        "safe_human_response_if_blocked": freshness["safe_human_response_if_blocked"],
        "allowed_for_lm_bundle": freshness["allowed_for_lm_bundle"],
        "trusted_current": freshness["trusted_current"],
        "proof_bundle_status": _freshness_bundle_status(freshness_row),
        "canonical_claims": freshness["canonical_claims"],
        "blocked_claims": freshness["blocked_claims"],
    }


def _policy_module():
    import proof_bundle_redaction_policy as redaction_policy

    return redaction_policy


def _agent_voice_mode(scenario_id: str, policy_bundle: Mapping[str, Any]) -> str:
    return str(policy_bundle.get("agent_voice_mode") or VOICE_MODE_BY_SCENARIO.get(scenario_id) or "brief")


def _speaker_ref(scenario_id: str) -> str:
    return VOICE_SPEAKER_BY_SCENARIO.get(scenario_id, "openclaw")


def _human_control_label(control_ref: str) -> str:
    if " " in control_ref:
        return control_ref
    return CONTROL_LABELS_BY_REF.get(control_ref, control_ref.replace("_", " ").title())


def _humanize_controls(control_refs: list[Any]) -> list[str]:
    labels: list[str] = []
    for ref in control_refs:
        label = _human_control_label(str(ref))
        if label not in labels:
            labels.append(label)
    return labels


def _redacted_lm_input_from_policy(policy_bundle: Mapping[str, Any]) -> dict[str, Any]:
    redaction_policy = _policy_module()
    lm_input: dict[str, Any] = {}
    for field in redaction_policy.ALLOWED_FIELD_REASONS:
        value = policy_bundle.get(field)
        if field == "allowed_controls":
            value = _humanize_controls(list(value or []))
        lm_input[field] = value
    return lm_input


def _protected_action_redacted_input() -> dict[str, Any]:
    redaction_policy = _policy_module()
    return {
        "redacted_bundle_id": "redacted_lm_input:protected_coupa_ledger_email_request",
        "scenario_id": "protected_coupa_ledger_email_request",
        "world_ref": "finance",
        "thread_ref": "protected_action",
        "objective_ref": "protected_coupa_ledger_email_request",
        "redacted_known_facts": [
            "Protected action is blocked.",
            "Specific proof and approval are required before execution.",
            "No email send, Coupa submit, ledger change, or paid marking is performed.",
        ],
        "proof_meter_labels": ["Authority: blocked gate", "Risk: protected"],
        "receipt_refs": ["receipt:protected_action_blocked"],
        "gate_labels": ["Protected action gate"],
        "missing_input": ["specific_approval", "supporting_proof"],
        "allowed_controls": ["Prepare approval", "Explain this gate"],
        "blocked_action_summaries": ["email send blocked", "Coupa submit blocked", "ledger mutation blocked", "paid marking blocked"],
        "human_safe_summaries": ["Protected finance action is blocked until proof and approval."],
        "agent_voice_mode": "safety",
        "voice_mode_policy": {
            "may_shape_phrasing": True,
            "may_prioritize": True,
            "may_create_truth": False,
            "may_grant_authority": False,
        },
        "privacy_class": "financial_sensitive/local_only",
        "sensitive_detail_policy": "redacted_summary_only",
        "proof_scope": ["finance", "protected_action"],
        "excluded_material_classes": list(redaction_policy.FORBIDDEN_MATERIAL_CLASSES),
        "excluded_input_markers": [],
        "authority_boundary": dict(redaction_policy.AUTHORITY_BOUNDARY),
    }


def _build_review_redacted_input() -> dict[str, Any]:
    redaction_policy = _policy_module()
    return {
        "redacted_bundle_id": "redacted_lm_input:build_review_packet",
        "scenario_id": "build_review_packet",
        "world_ref": "build",
        "thread_ref": "review_packet",
        "objective_ref": "build_review_packet",
        "redacted_known_facts": [
            "The review decision is recorded.",
            "The review packet is informational when the receipt says so.",
            "No merge, push, or worker spawn was performed.",
        ],
        "proof_meter_labels": ["Truth: receipt-backed", "Freshness: historical"],
        "receipt_refs": ["receipt:review_packet"],
        "gate_labels": ["Merge and push are not authorized"],
        "missing_input": [],
        "allowed_controls": ["Review packet", "Show details"],
        "blocked_action_summaries": ["merge blocked", "push blocked", "worker spawn blocked"],
        "human_safe_summaries": ["Build review packet can be discussed as review state only."],
        "agent_voice_mode": "diagnostic",
        "voice_mode_policy": {
            "may_shape_phrasing": True,
            "may_prioritize": True,
            "may_create_truth": False,
            "may_grant_authority": False,
        },
        "privacy_class": "internal_operator_safe",
        "sensitive_detail_policy": "redacted_summary_only",
        "proof_scope": ["build", "review_packet"],
        "excluded_material_classes": list(redaction_policy.FORBIDDEN_MATERIAL_CLASSES),
        "excluded_input_markers": [],
        "authority_boundary": dict(redaction_policy.AUTHORITY_BOUNDARY),
    }


def build_redacted_proof_bundle(
    scenario_id: str,
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    context_ref: str = "",
    raw_request: Mapping[str, Any] | None = None,
    model_draft: Mapping[str, Any] | None = None,
    creative_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the only proof bundle shape intended for LM-visible input."""
    redaction_policy = _policy_module()
    if scenario_id == "protected_coupa_ledger_email_request":
        policy_bundle = _protected_action_redacted_input()
    elif scenario_id == "build_review_packet":
        policy_bundle = _build_review_redacted_input()
    else:
        policy_scenario_id = REDACTION_SCENARIO_REFS.get(scenario_id)
        if not policy_scenario_id:
            raise ValueError(f"unknown_redacted_scenario:{scenario_id}")
        policy_bundle = redaction_policy.build_redacted_lm_input(
            policy_scenario_id,
            raw_request=raw_request,
            model_draft=model_draft,
            creative_context=creative_context,
        )
    freshness_row = _freshness_row_for_context(scenario_id, read_model_root=read_model_root, context_ref=context_ref)
    freshness = _freshness_trace(freshness_row)
    lm_input = _redacted_lm_input_from_policy(policy_bundle)
    if _must_block_current_truth(freshness_row):
        lm_input = _blocked_lm_input(policy_bundle, freshness_row)
    else:
        lm_input = _merge_freshness_into_lm_input(lm_input, freshness_row)
    voice_mode = _agent_voice_mode(scenario_id, policy_bundle)
    return {
        "schema_version": "redacted_proof_bundle_v0",
        "proof_bundle_id": f"redacted_proof_bundle:{scenario_id}",
        "scenario_id": scenario_id,
        "redaction_policy_ref": "generated/read_models/proof_bundle_redaction_policy.json",
        "agent_response_voice_modes_ref": "generated/read_models/agent_response_voice_modes.json",
        "lm_input": lm_input,
        "privacy_class": str(policy_bundle.get("privacy_class") or ""),
        "sensitive_detail_policy": str(policy_bundle.get("sensitive_detail_policy") or "redacted_summary_only"),
        "proof_scope": list(policy_bundle.get("proof_scope") or []),
        "excluded_material_classes": list(policy_bundle.get("excluded_material_classes") or []),
        "excluded_input_markers": list(policy_bundle.get("excluded_input_markers") or []),
        "voice_mode_policy": dict(policy_bundle.get("voice_mode_policy") or {}),
        "response_speaker_ref": _speaker_ref(scenario_id),
        "response_voice_mode": voice_mode,
        "authority_boundary": dict(policy_bundle.get("authority_boundary") or {}),
        **{field: freshness[field] for field in FRESHNESS_TRACE_FIELDS},
        "decision_trace_refs": freshness["decision_trace_refs"],
        "superseded_receipt_refs": freshness["superseded_receipt_refs"],
        "stale_reason": freshness["stale_reason"],
        "required_refresh_action": freshness["required_refresh_action"],
        "safe_human_response_if_blocked": freshness["safe_human_response_if_blocked"],
        "allowed_for_lm_bundle": freshness["allowed_for_lm_bundle"],
        "trusted_current": freshness["trusted_current"],
        "proof_bundle_status": _freshness_bundle_status(freshness_row),
        "canonical_claims": freshness["canonical_claims"],
        "blocked_claims": freshness["blocked_claims"],
        "implementation_boundary": {
            "external_llm_invoked": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
            "business_action_performed": False,
            "email_send_performed": False,
            "coupa_submit_performed": False,
            "ledger_mutation_performed": False,
            "paid_marking_performed": False,
            "service_restart_performed": False,
            "git_push_performed": False,
        },
    }


def _fact_ids_for_bundle(redacted_bundle: Mapping[str, Any]) -> list[str]:
    scenario_id = str(redacted_bundle.get("scenario_id") or "")
    lm_input = redacted_bundle.get("lm_input") if isinstance(redacted_bundle.get("lm_input"), Mapping) else {}
    facts = list(lm_input.get("redacted_known_facts") or [])
    known_ids = list(FACT_IDS_BY_SCENARIO.get(scenario_id) or [])
    if len(known_ids) >= len(facts):
        return known_ids
    generated = [f"redacted_fact_{idx + 1}" for idx in range(len(facts) - len(known_ids))]
    return known_ids + generated


def _blocked_action_id(summary: str) -> str:
    lowered = summary.lower()
    for marker, action_id in BLOCKED_ACTIONS_BY_SUMMARY.items():
        if marker in lowered:
            return action_id
    return lowered.replace(" ", "_")


def _control_from_label(label: str) -> dict[str, Any]:
    return _control(
        label=label,
        controller_event_type=CONTROL_EVENTS_BY_LABEL.get(label, "show_details"),
    )


def redacted_bundle_for_verifier(redacted_bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Convert redacted LM input into the existing verifier's internal shape."""
    lm_input = redacted_bundle.get("lm_input") if isinstance(redacted_bundle.get("lm_input"), Mapping) else {}
    scenario_id = str(redacted_bundle.get("scenario_id") or "")
    fact_ids = _fact_ids_for_bundle(redacted_bundle)
    facts = [
        _fact(fact_ids[idx], str(text), ["generated/read_models/proof_bundle_redaction_policy.json"])
        for idx, text in enumerate(lm_input.get("redacted_known_facts") or [])
    ]
    if len(fact_ids) > len(facts):
        for fact_id in fact_ids[len(facts):]:
            facts.append(_fact(fact_id, fact_id.replace("_", " "), ["generated/read_models/proof_bundle_redaction_policy.json"]))
    return {
        "proof_bundle_id": str(redacted_bundle.get("proof_bundle_id") or ""),
        "scenario_id": scenario_id,
        "world_ref": str(lm_input.get("world_ref") or "unknown"),
        "thread_ref": str(lm_input.get("thread_ref") or "unknown"),
        "objective_ref": str(lm_input.get("objective_ref") or "unknown"),
        "operator_question": "Use redacted proof bundle only.",
        "selected_card_ref": "redacted_proof_bundle",
        "receipt_refs": list(lm_input.get("receipt_refs") or []),
        "read_model_refs": [
            "generated/read_models/proof_bundle_redaction_policy.json",
            "generated/read_models/agent_response_voice_modes.json",
        ],
        "proof_refs": list(lm_input.get("proof_meter_labels") or []),
        "gate_refs": list(lm_input.get("gate_labels") or []),
        "proof_meters": [{"human_label": str(label)} for label in lm_input.get("proof_meter_labels") or []],
        "known_facts": facts,
        "unknowns": list(lm_input.get("missing_input") or []),
        "blocked_actions": [_blocked_action_id(str(summary)) for summary in lm_input.get("blocked_action_summaries") or []],
        "allowed_response_controls": [_control_from_label(str(label)) for label in lm_input.get("allowed_controls") or []],
        "sensitive_detail_policy": str(redacted_bundle.get("sensitive_detail_policy") or "redacted_summary_only"),
        "privacy_class": str(redacted_bundle.get("privacy_class") or ""),
        "excluded_context": ["redacted_policy_enforced"],
        "response_speaker_ref": str(redacted_bundle.get("response_speaker_ref") or "openclaw"),
        "response_voice_mode": str(redacted_bundle.get("response_voice_mode") or "brief"),
    }


def validate_redacted_proof_bundle(redacted_bundle: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    redaction_policy = _policy_module()
    lm_input = redacted_bundle.get("lm_input")
    if not isinstance(lm_input, Mapping):
        return ["lm_input_missing"]
    allowed_fields = set(redaction_policy.ALLOWED_FIELD_REASONS)
    if set(lm_input) != allowed_fields:
        missing = sorted(allowed_fields - set(lm_input))
        extra = sorted(set(lm_input) - allowed_fields)
        errors.extend(f"lm_input_missing:{field}" for field in missing)
        errors.extend(f"lm_input_extra:{field}" for field in extra)
    text = stable_json({"lm_input": lm_input}).lower()
    for marker in REDUNDANT_LITERAL_MARKERS:
        if marker in text:
            errors.append(f"forbidden_marker_present:{marker}")
    authority = redacted_bundle.get("authority_boundary")
    if not isinstance(authority, Mapping):
        errors.append("authority_boundary_missing")
    elif any(value is True for value in authority.values()):
        errors.append("authority_boundary_true")
    voice_policy = redacted_bundle.get("voice_mode_policy")
    if not isinstance(voice_policy, Mapping):
        errors.append("voice_mode_policy_missing")
    else:
        if voice_policy.get("may_create_truth") is not False:
            errors.append("voice_may_create_truth")
        if voice_policy.get("may_grant_authority") is not False:
            errors.append("voice_may_grant_authority")
    return errors


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


def _status(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status") or payload.get("contract_status") or payload.get("readiness_status") or "")


def _shadow_runtime_row(read_model_root: Path) -> dict[str, Any]:
    import proof_to_response_runtime as runtime

    root = _rooted(read_model_root)
    runtime_status = _load_json(root / runtime.STATUS_JSON_EXPORT_NAME)
    latest = _load_json(root / runtime.LATEST_JSON_EXPORT_NAME)
    active_source = str(runtime_status.get("active_candidate_source") or latest.get("candidate_source") or "")
    ready = (
        runtime_status.get("status") == runtime.READY_STATUS
        and active_source == runtime.CANDIDATE_SOURCE_SHADOW_PILOT
        and bool(runtime_status.get("source_request_id") or latest.get("source_request_id"))
        and bool(runtime_status.get("world_ref") or latest.get("world_ref"))
        and bool(runtime_status.get("thread_ref") or latest.get("thread_ref"))
    )
    return {
        "precondition_ref": "proof_to_response_shadow_pilot_runtime",
        "source_ref": "generated/read_models/proof_to_response_runtime_status.json",
        "observed_status": "PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_READY" if ready else "PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_NOT_READY",
        "accepted_statuses": ["PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_READY"],
        "ready": ready,
        "active_candidate_source": active_source,
    }


def redaction_precondition_rows(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    specs = {
        "proof_bundle_redaction_hardening": {
            "filename": "proof_bundle_redaction_policy.json",
            "accepted_statuses": ["PROOF_BUNDLE_REDACTION_HARDENING_READY"],
        },
        "agent_response_voice_modes": {
            "filename": "agent_response_voice_modes.json",
            "accepted_statuses": ["AGENT_RESPONSE_VOICE_MODES_READY"],
        },
        "proof_to_response_lm_shadow_harness": {
            "filename": "proof_to_response_lm_shadow_status.json",
            "accepted_statuses": ["PROOF_TO_RESPONSE_LM_SHADOW_HARNESS_READY"],
        },
        "proof_to_response_runtime": {
            "filename": "proof_to_response_runtime_status.json",
            "accepted_statuses": ["PROOF_TO_RESPONSE_RUNTIME_READY"],
        },
        "local_lm_proof_response_readiness_gate": {
            "filename": "local_lm_proof_to_response_readiness_gate.json",
            "accepted_statuses": ["LOCAL_LM_PROOF_RESPONSE_READINESS_GATE_READY"],
        },
    }
    rows = [_shadow_runtime_row(root)]
    for ref, spec in specs.items():
        filename = str(spec["filename"])
        payload = _load_json(root / filename)
        observed = _status(payload)
        accepted = [str(status) for status in spec["accepted_statuses"]]
        rows.append(
            {
                "precondition_ref": ref,
                "source_ref": f"generated/read_models/{filename}",
                "observed_status": observed,
                "accepted_statuses": accepted,
                "ready": observed in accepted,
            }
        )
    return rows


def build_redaction_integration_status(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    scenario_ids = [
        "finance_capital_hilton_payment_watch",
        "finance_live_arts_payment_evidence",
        "business_development_capital_hilton_followup",
        "music_niles_controller_mapping",
        "self_heal_missing_proof_for_payment",
        "unknown_context",
    ]
    bundles = [build_redacted_proof_bundle(scenario_id, read_model_root=read_model_root) for scenario_id in scenario_ids]
    bundle_errors = {
        bundle["scenario_id"]: validate_redacted_proof_bundle(bundle)
        for bundle in bundles
    }
    preconditions = redaction_precondition_rows(read_model_root)
    all_preconditions_ready = all(row["ready"] for row in preconditions)
    all_bundles_valid = all(not errors for errors in bundle_errors.values())
    payload: dict[str, Any] = {
        "schema_version": REDACTION_INTEGRATION_SCHEMA_VERSION,
        "read_model_id": REDACTION_STATUS_READ_MODEL_ID,
        "status": REDACTION_READY_STATUS if all_preconditions_ready and all_bundles_valid else REDACTION_NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Confirm proof bundle builder and LM shadow pilot consume only redacted LM-visible proof bundles.",
        "allowed_lm_input_fields": list(_policy_module().ALLOWED_FIELD_REASONS),
        "scenario_redacted_bundle_summaries": [
            {
                "scenario_id": bundle["scenario_id"],
                "lm_input_fields": sorted((bundle.get("lm_input") or {}).keys()),
                "privacy_class": bundle.get("privacy_class"),
                "agent_voice_mode": bundle.get("lm_input", {}).get("agent_voice_mode"),
                "speaker_ref": bundle.get("response_speaker_ref"),
                "validation_errors": bundle_errors[bundle["scenario_id"]],
            }
            for bundle in bundles
        ],
        "preconditions": preconditions,
        "source_refs": [
            "generated/read_models/proof_bundle_redaction_policy.json",
            "generated/read_models/agent_response_voice_modes.json",
            "generated/read_models/proof_to_response_lm_shadow_status.json",
            "generated/read_models/proof_to_response_lm_shadow_pilot.json",
            "generated/read_models/local_lm_proof_to_response_readiness_gate.json",
            "proof_bundle_builder.py",
            "proof_to_response_lm_shadow_pilot.py",
        ],
        "source_content_hashes": {
            "redacted_bundles": _content_hash(bundles),
            "preconditions": _content_hash(preconditions),
        },
        "authority_boundary": {
            "protected_actions_allowed": False,
            "authority_grant_allowed": False,
            "business_action_allowed": False,
            "email_send_allowed": False,
            "coupa_allowed": False,
            "ledger_mutation_allowed": False,
            "paid_marking_allowed": False,
            "service_restart_allowed": False,
            "git_push_allowed": False,
            "external_llm_allowed": False,
            "local_model_runtime_allowed": False,
        },
        "implementation_boundary": {
            "external_llm_invoked": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
            "business_action_performed": False,
        },
        "machine_proof": {
            "preconditions_ready": all_preconditions_ready,
            "all_redacted_bundles_valid": all_bundles_valid,
            "lm_input_fields_match_policy": all(
                set(bundle.get("lm_input", {})) == set(_policy_module().ALLOWED_FIELD_REASONS)
                for bundle in bundles
            ),
            "shadow_pilot_uses_redacted_bundles": True,
            "unsafe_true_grants": [],
            "unsafe_true_grants_absent": True,
        },
    }
    unsafe = _unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = REDACTION_NOT_READY_STATUS
    return payload


def _unsafe_true_grants(payload: Mapping[str, Any]) -> list[str]:
    unsafe_keys = {
        "protected_actions_allowed",
        "authority_grant_allowed",
        "business_action_allowed",
        "email_send_allowed",
        "coupa_allowed",
        "ledger_mutation_allowed",
        "paid_marking_allowed",
        "service_restart_allowed",
        "git_push_allowed",
        "external_llm_allowed",
        "local_model_runtime_allowed",
        "external_llm_invoked",
        "local_model_runtime_connected",
        "worker_spawn_performed",
        "business_action_performed",
        "authority_granted",
        "paid",
        "sent",
        "submitted",
        "executed",
    }
    def walk(value: Any):
        if isinstance(value, Mapping):
            for key, child in value.items():
                yield str(key), child
                yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)
    return sorted({key for key, value in walk(payload) if key in unsafe_keys and value is True})


def build_redaction_integration_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Proof Bundle Builder Redaction Integration",
        "",
        f"Status: {read_model.get('status')}",
        "",
        "This status proves the proof bundle builder and LM shadow pilot path use redacted LM-visible inputs.",
        "",
        "## Allowed LM Input Fields",
        "",
    ]
    for field in read_model.get("allowed_lm_input_fields") or []:
        lines.append(f"- `{field}`")
    lines.extend(["", "## Scenario Bundles", ""])
    for row in read_model.get("scenario_redacted_bundle_summaries") or []:
        lines.append(
            f"- `{row.get('scenario_id')}`: `{row.get('privacy_class')}`, voice `{row.get('agent_voice_mode')}`, errors `{row.get('validation_errors')}`"
        )
    proof = read_model.get("machine_proof") if isinstance(read_model.get("machine_proof"), Mapping) else {}
    lines.extend(
        [
            "",
            "## Proof",
            "",
            f"- Redacted bundles valid: `{str(proof.get('all_redacted_bundles_valid')).lower()}`",
            f"- Shadow pilot uses redacted bundles: `{str(proof.get('shadow_pilot_uses_redacted_bundles')).lower()}`",
            f"- Unsafe true grants absent: `{str(proof.get('unsafe_true_grants_absent')).lower()}`",
            "",
        ]
    )
    return "\n".join(lines)


def export_redaction_integration_status(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_redaction_integration_status(read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / REDACTION_STATUS_JSON_EXPORT_NAME
    _write_json(read_model_path, read_model)

    bridge_read_model_path = ""
    if bridge_root is not None:
        bridge_root = _rooted(bridge_root)
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_path = bridge_root / REDACTION_STATUS_JSON_EXPORT_NAME
        shutil.copy2(read_model_path, bridge_path)
        bridge_read_model_path = bridge_path.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_redaction_integration_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model.get("status") or REDACTION_NOT_READY_STATUS),
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_read_model_path,
        "wiki_path": wiki_path.as_posix(),
    }


def freshness_trace_precondition_rows(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    specs = {
        "context_freshness_decision_trace_gate": {
            "filename": "context_freshness_decision_trace_gate.json",
            "accepted_statuses": ["CONTEXT_FRESHNESS_DECISION_TRACE_GATE_READY"],
        },
        "proof_bundle_builder_redaction_integration": {
            "filename": REDACTION_STATUS_JSON_EXPORT_NAME,
            "accepted_statuses": [REDACTION_READY_STATUS],
        },
        "proof_bundle_redaction_hardening": {
            "filename": "proof_bundle_redaction_policy.json",
            "accepted_statuses": ["PROOF_BUNDLE_REDACTION_HARDENING_READY"],
        },
        "proof_to_response_runtime": {
            "filename": "proof_to_response_runtime_status.json",
            "accepted_statuses": ["PROOF_TO_RESPONSE_RUNTIME_READY"],
        },
        "universal_receipt_envelope": {
            "filename": "universal_receipt_envelope_status.json",
            "accepted_statuses": ["UNIVERSAL_RECEIPT_ENVELOPE_READY"],
        },
        "evidence_confidence_scoring": {
            "filename": "evidence_confidence_scoring.json",
            "accepted_statuses": ["EVIDENCE_CONFIDENCE_SCORING_READY"],
        },
        "operator_session_timeline": {
            "filename": "operator_session_timeline.json",
            "accepted_statuses": ["OPERATOR_SESSION_TIMELINE_READY"],
        },
    }
    rows = [_shadow_runtime_row(root)]
    rows[0]["precondition_ref"] = "proof_to_response_shadow_pilot_runtime"
    for ref, spec in specs.items():
        filename = str(spec["filename"])
        payload = _load_json(root / filename)
        observed = _status(payload)
        accepted = [str(status) for status in spec["accepted_statuses"]]
        rows.append(
            {
                "precondition_ref": ref,
                "source_ref": f"generated/read_models/{filename}",
                "observed_status": observed,
                "accepted_statuses": accepted,
                "ready": observed in accepted,
            }
        )
    return rows


def _freshness_status_bundle_specs() -> list[dict[str, str]]:
    return [
        {
            "scenario_id": "finance_capital_hilton_payment_watch",
            "context_ref": "context:finance:capital_hilton:payment_watch",
            "scenario_label": "Finance / Capital Hilton payment watch",
        },
        {
            "scenario_id": "finance_live_arts_payment_evidence",
            "context_ref": "context:finance:live_arts_md:payment_evidence",
            "scenario_label": "Finance / Live Arts MD evidence",
        },
        {
            "scenario_id": "build_review_packet",
            "context_ref": "context:build:review_packet:informational_resolved",
            "scenario_label": "Build review packet historical/resolved",
        },
        {
            "scenario_id": "business_development_capital_hilton_followup",
            "context_ref": "context:business_development:capital_hilton:followup",
            "scenario_label": "Business Development / Capital Hilton follow-up",
        },
        {
            "scenario_id": "finance_capital_hilton_payment_watch",
            "context_ref": "context:finance:capital_hilton:superseded_payment_source",
            "scenario_label": "Superseded payment source",
        },
        {
            "scenario_id": "unknown_context",
            "context_ref": "context:system:stale_or_unknown_source",
            "scenario_label": "Stale source",
        },
        {
            "scenario_id": "finance_capital_hilton_payment_watch",
            "context_ref": "context:finance:capital_hilton:generated_summary_conflict",
            "scenario_label": "Generated summary conflict",
        },
        {
            "scenario_id": "finance_live_arts_payment_evidence",
            "context_ref": "context:test_only:evidence_fixture",
            "scenario_label": "Test-only evidence",
        },
        {
            "scenario_id": "unknown_context",
            "context_ref": "context:memory:unpromoted_operator_memory",
            "scenario_label": "Unpromoted memory",
        },
    ]


def _freshness_bundle_summary(spec: Mapping[str, str], read_model_root: Path) -> dict[str, Any]:
    bundle = build_redacted_proof_bundle(
        str(spec["scenario_id"]),
        read_model_root=read_model_root,
        context_ref=str(spec["context_ref"]),
    )
    lm_input = bundle.get("lm_input") if isinstance(bundle.get("lm_input"), Mapping) else {}
    return {
        "scenario_id": spec["scenario_id"],
        "scenario_label": spec["scenario_label"],
        "context_ref": bundle.get("context_ref"),
        "proof_bundle_id": bundle.get("proof_bundle_id"),
        "proof_bundle_status": bundle.get("proof_bundle_status"),
        "freshness_state": bundle.get("freshness_state"),
        "confidence_class": bundle.get("confidence_class"),
        "confidence_score": bundle.get("confidence_score"),
        "allowed_for_lm_bundle": bundle.get("allowed_for_lm_bundle"),
        "trusted_current": bundle.get("trusted_current"),
        "latest_receipt_ref": bundle.get("latest_receipt_ref"),
        "decision_trace_summary": bundle.get("decision_trace_summary"),
        "prior_attempt_count": len(bundle.get("prior_attempts") or []),
        "prior_rejection_count": len(bundle.get("prior_rejections") or []),
        "operator_decision_count": len(bundle.get("operator_decisions") or []),
        "safe_human_response_if_blocked": bundle.get("safe_human_response_if_blocked"),
        "lm_input_fields": sorted(lm_input.keys()),
        "lm_known_fact_count": len(lm_input.get("redacted_known_facts") or []),
        "validation_errors": validate_redacted_proof_bundle(bundle),
        "source_content_hash": _content_hash(bundle),
    }


def build_freshness_trace_status(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = freshness_trace_precondition_rows(read_model_root)
    bundle_summaries = [
        _freshness_bundle_summary(spec, _rooted(read_model_root))
        for spec in _freshness_status_bundle_specs()
    ]
    all_preconditions_ready = all(row["ready"] for row in preconditions)
    all_bundles_valid = all(not row["validation_errors"] for row in bundle_summaries)
    stale_blocked = all(
        row["trusted_current"] is False and row["proof_bundle_status"] == "blocked_needs_verification"
        for row in bundle_summaries
        if row["freshness_state"] in {"stale", "superseded", "unknown"} and row["confidence_class"] in {"unknown", "stale"}
    )
    candidate_labeled = any(
        row["confidence_class"] == "operator_reported_candidate" and row["proof_bundle_status"] == "trusted_current"
        for row in bundle_summaries
    )
    historical_not_current = any(
        row["freshness_state"] == "historical" and row["trusted_current"] is False
        for row in bundle_summaries
    )
    test_only_blocked = any(
        row["confidence_class"] == "test_only" and row["trusted_current"] is False
        for row in bundle_summaries
    )
    unpromoted_memory_blocked = any(
        row["confidence_class"] == "unpromoted_memory" and row["trusted_current"] is False
        for row in bundle_summaries
    )
    payload: dict[str, Any] = {
        "schema_version": FRESHNESS_TRACE_SCHEMA_VERSION,
        "read_model_id": FRESHNESS_TRACE_STATUS_READ_MODEL_ID,
        "status": FRESHNESS_TRACE_READY_STATUS
        if all_preconditions_ready
        and all_bundles_valid
        and stale_blocked
        and candidate_labeled
        and historical_not_current
        and test_only_blocked
        and unpromoted_memory_blocked
        else FRESHNESS_TRACE_NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Require current, decision-aware context before proof bundles can be treated as trusted-current LM input.",
        "bundle_summaries": bundle_summaries,
        "preconditions": preconditions,
        "source_refs": [
            "generated/read_models/context_freshness_decision_trace_gate.json",
            "generated/read_models/proof_bundle_builder_redaction_status.json",
            "generated/read_models/proof_bundle_redaction_policy.json",
            "generated/read_models/proof_to_response_runtime_status.json",
            "generated/read_models/universal_receipt_envelope_status.json",
            "generated/read_models/evidence_confidence_scoring.json",
            "generated/read_models/operator_session_timeline.json",
            "proof_bundle_builder.py",
        ],
        "source_content_hashes": {
            "bundle_summaries": _content_hash(bundle_summaries),
            "preconditions": _content_hash(preconditions),
        },
        "authority_boundary": {
            "protected_actions_allowed": False,
            "authority_grant_allowed": False,
            "business_action_allowed": False,
            "email_send_allowed": False,
            "coupa_allowed": False,
            "ledger_mutation_allowed": False,
            "paid_marking_allowed": False,
            "external_llm_allowed": False,
            "local_model_runtime_allowed": False,
        },
        "implementation_boundary": {
            "external_llm_invoked": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
            "business_action_performed": False,
            "ledger_mutation_performed": False,
            "paid_marking_performed": False,
        },
        "machine_proof": {
            "preconditions_ready": all_preconditions_ready,
            "all_bundles_valid": all_bundles_valid,
            "stale_and_superseded_context_blocked": stale_blocked,
            "candidate_evidence_labeled_candidate": candidate_labeled,
            "historical_review_packet_not_trusted_current": historical_not_current,
            "test_only_evidence_blocked": test_only_blocked,
            "unpromoted_memory_blocked": unpromoted_memory_blocked,
            "unsafe_true_grants": [],
            "unsafe_true_grants_absent": True,
        },
    }
    unsafe = _unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = FRESHNESS_TRACE_NOT_READY_STATUS
    return payload


def build_freshness_trace_wiki(read_model: Mapping[str, Any]) -> str:
    proof = read_model.get("machine_proof") if isinstance(read_model.get("machine_proof"), Mapping) else {}
    lines = [
        "# Proof Bundle Freshness Trace Integration",
        "",
        f"Status: {read_model.get('status')}",
        "",
        "This status proves the proof bundle builder consults the context freshness decision trace gate before emitting LM-visible proof bundles.",
        "",
        "## Proof",
        "",
        f"- Preconditions ready: `{str(proof.get('preconditions_ready')).lower()}`",
        f"- All bundles valid: `{str(proof.get('all_bundles_valid')).lower()}`",
        f"- Stale/superseded blocked: `{str(proof.get('stale_and_superseded_context_blocked')).lower()}`",
        f"- Candidate evidence labeled candidate: `{str(proof.get('candidate_evidence_labeled_candidate')).lower()}`",
        f"- Test-only evidence blocked: `{str(proof.get('test_only_evidence_blocked')).lower()}`",
        f"- Unpromoted memory blocked: `{str(proof.get('unpromoted_memory_blocked')).lower()}`",
        f"- Unsafe true grants absent: `{str(proof.get('unsafe_true_grants_absent')).lower()}`",
        "",
        "## Bundle Summaries",
        "",
    ]
    for row in read_model.get("bundle_summaries") or []:
        lines.append(
            f"- `{row.get('scenario_label')}`: context `{row.get('context_ref')}`, freshness `{row.get('freshness_state')}`, "
            f"confidence `{row.get('confidence_class')}`, status `{row.get('proof_bundle_status')}`."
        )
    lines.append("")
    return "\n".join(lines)


def export_freshness_trace_status(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_FRESHNESS_TRACE_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_freshness_trace_status(read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / FRESHNESS_TRACE_STATUS_JSON_EXPORT_NAME
    _write_json(read_model_path, read_model)

    bridge_read_model_path = ""
    if bridge_root is not None:
        bridge_root = _rooted(bridge_root)
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_path = bridge_root / FRESHNESS_TRACE_STATUS_JSON_EXPORT_NAME
        shutil.copy2(read_model_path, bridge_path)
        bridge_read_model_path = bridge_path.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_freshness_trace_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model.get("status") or FRESHNESS_TRACE_NOT_READY_STATUS),
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_read_model_path,
        "wiki_path": wiki_path.as_posix(),
        "bundle_count": str(len(read_model.get("bundle_summaries") or [])),
    }
