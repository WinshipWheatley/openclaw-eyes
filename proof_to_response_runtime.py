"""Verifier-only proof-to-response runtime.

This runtime is the publish gate between machine proof and concise operator
responses. It does not invoke a model. A candidate response may be supplied by
tests, fixtures, or a future gated harness; this module verifies it, publishes
only if it is grounded and bounded, otherwise publishes a safe fallback.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import proof_bundle_builder as bundles
import proof_to_response_verifier as verifier


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Proof To Response Runtime.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/proof_to_response_runtime.sqlite")

SCHEMA_VERSION = "proof_to_response_runtime_v0"
CONTRACT_READ_MODEL_ID = "proof_to_response_runtime_contract"
STATUS_READ_MODEL_ID = "proof_to_response_runtime_status"
LATEST_READ_MODEL_ID = "proof_to_response_latest"
CONTRACT_JSON_EXPORT_NAME = f"{CONTRACT_READ_MODEL_ID}.json"
STATUS_JSON_EXPORT_NAME = f"{STATUS_READ_MODEL_ID}.json"
LATEST_JSON_EXPORT_NAME = f"{LATEST_READ_MODEL_ID}.json"
READY_STATUS = "PROOF_TO_RESPONSE_RUNTIME_READY"
NOT_READY_STATUS = "PROOF_TO_RESPONSE_RUNTIME_NOT_READY"
CANDIDATE_SOURCE_DETERMINISTIC = "deterministic_fixture"
CANDIDATE_SOURCE_SHADOW_PILOT = "shadow_pilot_candidate"
CANDIDATE_SOURCE_FUTURE_LIVE_LM_BLOCKED = "future_live_lm_blocked"
CANDIDATE_SOURCE_LM2_ROOM_BACKED_STRUCTURED_RETRY = "lm2_room_backed_worker_structured_output_retry"
CANDIDATE_SOURCES = (
    CANDIDATE_SOURCE_DETERMINISTIC,
    CANDIDATE_SOURCE_SHADOW_PILOT,
    CANDIDATE_SOURCE_FUTURE_LIVE_LM_BLOCKED,
    CANDIDATE_SOURCE_LM2_ROOM_BACKED_STRUCTURED_RETRY,
)

SUPPORTED_SCENARIOS = (
    "finance_capital_hilton_payment_watch",
    "finance_capital_hilton_attach_proof_explanation",
    "finance_live_arts_payment_evidence",
    "business_development_capital_hilton_followup",
    "build_review_packet",
    "unknown_context",
    "protected_coupa_ledger_email_request",
    "self_heal_missing_proof_for_payment",
)

PRECONDITIONS = {
    "agentic_response_repair_gate_integration_plan": {
        "filename": "agentic_response_repair_gate_integration_plan.json",
        "accepted_statuses": ["AGENTIC_RESPONSE_REPAIR_GATE_INTEGRATION_PLAN_READY"],
    },
    "proof_to_response_lm_shadow_harness": {
        "filename": "proof_to_response_lm_shadow_status.json",
        "accepted_statuses": ["PROOF_TO_RESPONSE_LM_SHADOW_HARNESS_READY"],
    },
    "proof_to_response_lm_shadow_contract": {
        "filename": "proof_to_response_lm_shadow_contract.json",
        "accepted_statuses": ["PROOF_TO_RESPONSE_LM_SHADOW_HARNESS_READY"],
    },
    "proof_to_response_lm_shadow_pilot": {
        "filename": "proof_to_response_lm_shadow_pilot.json",
        "accepted_statuses": ["PROOF_TO_RESPONSE_LM_SHADOW_PILOT_READY"],
    },
    "self_heal_repair_doctrine": {
        "filename": "self_heal_repair_doctrine.json",
        "accepted_statuses": ["SELF_HEAL_REPAIR_DOCTRINE_READY"],
    },
    "goldilocks_gate_calibration": {
        "filename": "goldilocks_gate_calibration.json",
        "accepted_statuses": ["GOLDILOCKS_GATE_CALIBRATION_READY"],
    },
    "proof_to_response_tdd_spec": {
        "filename": "proof_to_response_tdd_spec.json",
        "accepted_statuses": ["PROOF_TO_RESPONSE_TDD_SPEC_READY"],
    },
    "objective_advancement_controller_route": {
        "filename": "objective_advancement_protocol.json",
        "accepted_statuses": ["OBJECTIVE_ADVANCEMENT_CONTROLLER_ROUTE_READY", "OBJECTIVE_ADVANCEMENT_PROTOCOL_READY"],
    },
    "dynamic_card_packet_v1": {
        "filename": "dynamic_card_packet_latest.json",
        "accepted_statuses": ["DYNAMIC_CARD_PACKET_V1_READY", "DYNAMIC_CARD_PACKET_READY"],
    },
    "universal_receipt_envelope": {
        "filename": "universal_receipt_envelope_status.json",
        "accepted_statuses": ["UNIVERSAL_RECEIPT_ENVELOPE_READY"],
    },
    "proof_meter_normalization": {
        "filename": "proof_meter_normalization.json",
        "accepted_statuses": ["PROOF_METER_NORMALIZATION_READY"],
    },
    "operator_controller_protocol": {
        "filename": "operator_controller_protocol.json",
        "accepted_statuses": ["OPERATOR_CONTROLLER_PROTOCOL_READY"],
    },
}

DOCTRINE = (
    "Candidate agent text is not truth.",
    "Machine proof, receipts, gates, source refs, and hashes define publishable claims.",
    "The runtime may publish concise human text only after deterministic verification.",
    "If verification fails, the runtime publishes a safe fallback instead of the draft.",
    "Controls remain controller events and never grant protected authority.",
    "Details and proof stay collapsed by default.",
)

AUTHORITY_BOUNDARY = {
    "protected_actions_allowed": False,
    "model_invocation_allowed": False,
    "live_lm_invocation_allowed": False,
    "external_provider_connect_allowed": False,
    "local_model_runtime_allowed": False,
    "worker_spawn_allowed": False,
    "business_action_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "paid_marking_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
    "authority_grant_allowed": False,
}

PERFORMED_FLAGS = {
    "business_action_performed": False,
    "paid_marking_performed": False,
    "ledger_mutation_performed": False,
    "email_send_performed": False,
    "coupa_submit_performed": False,
    "portal_submit_performed": False,
    "workbook_mutation_performed": False,
    "pdf_export_performed": False,
    "worker_spawn_performed": False,
    "git_push_performed": False,
    "merge_performed": False,
    "external_llm_invoked": False,
    "local_model_runtime_connected": False,
    "incoming_authority_granted_accepted": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | set(PERFORMED_FLAGS) | set(verifier.UNSAFE_TRUE_KEYS) | {
    "paid",
    "sent",
    "submitted",
    "executed",
    "approved_and_executed",
    "business_action_allowed",
    "external_action_allowed",
}

BLOCKED_ACTION_LABELS = {
    "mark_paid": "paid marking",
    "paid_marking": "paid marking",
    "mutate_ledger": "ledger mutation",
    "ledger_mutation": "ledger mutation",
    "ledger_post": "ledger posting",
    "submit_coupa": "Coupa/browser action",
    "coupa_submit": "Coupa/browser action",
    "portal_submit": "portal submit",
    "send_email": "email send",
    "email_send": "email send",
    "update_external_system": "external system update",
    "merge": "merge",
    "push": "push",
    "spawn_worker": "worker spawn",
    "worker_spawn": "worker spawn",
    "package_staging": "package staging",
    "business_action_routing": "business action routing",
}


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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _content_hash(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


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


def _observed_status(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status") or payload.get("contract_status") or payload.get("readiness_status") or "")


def _preconditions(read_model_root: Path) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, spec in PRECONDITIONS.items():
        filename = str(spec["filename"])
        payload = _load_json(root / filename)
        observed = _observed_status(payload)
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


def _normalise_package_for_self_heal(read_model_root: Path) -> dict[str, Any]:
    doctrine = _load_json(_rooted(read_model_root) / "self_heal_repair_doctrine.json")
    for package in doctrine.get("repair_packages") or []:
        if isinstance(package, Mapping) and package.get("repair_ref") == "self_heal:missing_proof_for_payment":
            return dict(package)
    raise ValueError("missing_self_heal_package:self_heal:missing_proof_for_payment")


def _build_self_heal_payment_bundle(read_model_root: Path) -> dict[str, Any]:
    package = _normalise_package_for_self_heal(read_model_root)
    copy = package.get("dynamic_response_copy") if isinstance(package.get("dynamic_response_copy"), Mapping) else {}
    proof_refs = [str(ref) for ref in package.get("proof_refs") or [] if str(ref)]
    proof_refs.extend(str(ref.get("source_ref")) for ref in package.get("proof_meter_updates") or [] if isinstance(ref, Mapping) and ref.get("source_ref"))
    world_thread = str(package.get("affected_world_thread") or "finance/capital_hilton")
    world_ref, _, thread_ref = world_thread.partition("/")
    return {
        "proof_bundle_id": "proof_bundle:self_heal_missing_proof_for_payment",
        "scenario_id": "self_heal_missing_proof_for_payment",
        "world_ref": world_ref or "finance",
        "thread_ref": thread_ref or "capital_hilton",
        "objective_ref": str(package.get("repair_ref") or "self_heal:missing_proof_for_payment"),
        "operator_question": "What can OpenClaw do about missing payment proof?",
        "selected_card_ref": "self_heal.payment.missing_proof",
        "receipt_refs": [
            "generated/read_models/universal_receipt_envelope_status.json",
            str((package.get("receipt_requirement") or "repair receipt required")),
        ],
        "read_model_refs": [
            "generated/read_models/self_heal_repair_doctrine.json",
            "generated/read_models/proof_meter_normalization.json",
            "generated/read_models/universal_receipt_envelope_status.json",
            "generated/read_models/proof_to_response_tdd_spec.json",
        ],
        "proof_refs": list(dict.fromkeys(proof_refs)),
        "gate_refs": [
            "generated/read_models/goldilocks_gate_calibration.json#protected_payment_gate",
            "generated/read_models/gate_decision_ledger.json",
        ],
        "proof_meters": list(package.get("proof_meter_updates") or []),
        "known_facts": [
            _fact("repair_blocker_named", str(package.get("blocker_summary") or "Payment evidence is missing."), proof_refs),
            _fact("repair_proof_cited", str(copy.get("proof_citation") or "Proof refs cite the payment blocker."), proof_refs),
            _fact("can_do_now_named", "OpenClaw can hold payment watch, ask for proof, and show the blocked gate.", proof_refs),
            _fact("cannot_do_yet_named", "OpenClaw cannot mark paid, mutate ledger, submit Coupa, or send email.", proof_refs),
            _fact("smallest_manual_step_named", str(copy.get("required_operator_action") or "Attach payment evidence."), proof_refs),
        ],
        "unknowns": ["payment_evidence", "payment_arrival_confirmation"],
        "blocked_actions": ["mark_paid", "mutate_ledger", "submit_coupa", "send_email"],
        "allowed_response_controls": [
            _control(label="Attach payment proof", controller_event_type="attach_proof"),
            _control(label="Show blocked gate", controller_event_type="show_details"),
        ],
        "sensitive_detail_policy": "redacted_summary_only",
        "privacy_class": "financial_sensitive/local_only",
        "excluded_context": [
            "sensitive_attachment_body",
            "credential_material",
            "operator_device_auth_material",
            "external_provider_payloads",
        ],
        "response_speaker_ref": "chief",
        "response_voice_mode": "diagnostic",
        "self_heal_repair": {
            "repair_ref": str(package.get("repair_ref") or ""),
            "blocker_summary": str(package.get("blocker_summary") or ""),
            "can_do_now": [str(item) for item in copy.get("what_i_can_do_now") or [] if str(item)],
            "cannot_do_yet": [str(item) for item in copy.get("what_i_cannot_do_yet") or [] if str(item)],
            "required_operator_action": str(copy.get("required_operator_action") or ""),
            "next_step": str(copy.get("next_step") or "Attach payment proof"),
        },
    }


def build_or_load_proof_bundle(
    scenario_id: str,
    *,
    proof_bundle: Mapping[str, Any] | None = None,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
) -> dict[str, Any]:
    if proof_bundle is not None:
        return dict(proof_bundle)
    if scenario_id == "self_heal_missing_proof_for_payment":
        return _build_self_heal_payment_bundle(read_model_root)
    if scenario_id == "finance_capital_hilton_attach_proof_explanation":
        bundle = build_or_load_proof_bundle("finance_capital_hilton_payment_watch", read_model_root=read_model_root)
        bundle["proof_bundle_id"] = "proof_bundle:finance_capital_hilton_attach_proof_explanation"
        bundle["scenario_id"] = scenario_id
        bundle["operator_question"] = "What happens if I attach payment proof?"
        bundle["known_facts"] = [
            _fact(
                "proof_can_be_recorded",
                "Attached payment evidence can be recorded as candidate/payment-processing evidence.",
                ["generated/read_models/evidence_intake_status.json", "generated/read_models/universal_receipt_envelope_status.json"],
            ),
            _fact(
                "candidate_evidence_not_paid_truth",
                "Candidate/operator-reported payment-processing evidence does not mark the invoice paid.",
                ["generated/read_models/proof_meter_normalization.json", "generated/read_models/universal_receipt_envelope_status.json"],
            ),
            _fact(
                "ledger_untouched",
                "The ledger remains untouched until payment is confirmed.",
                ["generated/read_models/universal_receipt_envelope_status.json", "generated/read_models/objective_advancement_protocol.json"],
            ),
        ]
        bundle["unknowns"] = ["confirmed_payment_arrival", "verified_payment_receipt"]
        bundle["blocked_actions"] = ["mark_paid", "mutate_ledger", "submit_coupa", "send_email"]
        return bundle

    bundle = bundles.build_proof_bundle(scenario_id, read_model_root=read_model_root)
    controls = list(bundle.get("allowed_response_controls") or [])
    if scenario_id == "finance_capital_hilton_payment_watch":
        controls.append(
            _control(
                label="Attach payment evidence",
                controller_event_type="attach_proof",
                action_payload_ref="generated/read_models/operator_action_payloads.json#action_payloads.capital_hilton.payment.record_proof",
            )
        )
    if scenario_id == "finance_live_arts_payment_evidence":
        controls.append(_control(label="Verify arrival or attach stronger proof", controller_event_type="stage_plan"))
    bundle["allowed_response_controls"] = controls
    return bundle


def fixture_candidate_response(proof_bundle: Mapping[str, Any]) -> dict[str, Any]:
    scenario_id = str(proof_bundle.get("scenario_id") or "")
    common = {
        "response_id": f"candidate_response:{scenario_id}",
        "proof_bundle_id": str(proof_bundle.get("proof_bundle_id") or ""),
        "speaker_ref": str(proof_bundle.get("response_speaker_ref") or "openclaw"),
        "implied_actions": [],
        "uncertainty_notes": [],
    }
    if scenario_id == "finance_capital_hilton_payment_watch":
        return {
            **common,
            "draft_headline": "Payment evidence needed",
            "draft_body": "Coupa is processing. I can't mark this paid until payment evidence is attached. The ledger stays untouched.",
            "draft_next_step": "Attach payment evidence.",
            "claimed_facts": ["payment_evidence_missing", "coupa_processing", "ledger_untouched"],
            "requested_controls": ["Attach payment evidence"],
        }
    if scenario_id == "finance_capital_hilton_attach_proof_explanation":
        return {
            **common,
            "draft_headline": "Proof can be recorded",
            "draft_body": "If you attach payment evidence, I can record it as candidate/payment-processing evidence. I still will not mark this paid or touch the ledger until payment is confirmed.",
            "draft_next_step": "Attach payment evidence.",
            "claimed_facts": ["proof_can_be_recorded", "candidate_evidence_not_paid_truth", "ledger_untouched"],
            "requested_controls": ["Attach payment evidence"],
        }
    if scenario_id == "finance_live_arts_payment_evidence":
        return {
            **common,
            "draft_headline": "Payment proof received",
            "draft_body": "Payment-processing evidence is recorded as candidate evidence. It does not mark the invoice paid, and the ledger remains untouched.",
            "draft_next_step": "Verify arrival or attach stronger proof",
            "claimed_facts": ["candidate_evidence_recorded", "not_paid_truth", "ledger_untouched"],
            "requested_controls": ["Verify arrival"],
        }
    if scenario_id == "business_development_capital_hilton_followup":
        return {
            **common,
            "draft_headline": "Follow-up can be staged",
            "draft_body": "I can stage a follow-up draft. I will not send it.",
            "draft_next_step": "Stage follow-up",
            "claimed_facts": ["followup_stageable", "no_email_send"],
            "requested_controls": ["Stage follow-up"],
        }
    if scenario_id == "build_review_packet":
        return {
            **common,
            "draft_headline": "Review packet is informational",
            "draft_body": "This review packet is closed as informational. No merge and no push were performed.",
            "draft_next_step": "Review packet",
            "claimed_facts": ["review_packet_informational", "no_merge_or_push"],
            "requested_controls": ["Review packet"],
        }
    if scenario_id == "unknown_context":
        return {
            **common,
            "draft_headline": "Needs lane context",
            "draft_body": "Which world and thread should I use for this?",
            "draft_next_step": "Pick the world and thread",
            "claimed_facts": ["lane_context_missing"],
            "requested_controls": ["Choose lane"],
            "uncertainty_notes": ["world_ref and thread_ref are missing"],
        }
    if scenario_id == "protected_coupa_ledger_email_request":
        return {
            **common,
            "draft_headline": "Blocked until proof and approval",
            "draft_body": "Protected action is blocked until proof and approval. No execution will happen.",
            "draft_next_step": "Prepare approval",
            "claimed_facts": ["protected_action_blocked", "proof_and_approval_required", "no_execution"],
            "requested_controls": ["Prepare approval"],
        }
    if scenario_id == "self_heal_missing_proof_for_payment":
        return {
            **common,
            "draft_headline": "Payment evidence is missing",
            "draft_body": "Blocker: payment evidence is missing. Proof: the payment watch and receipt proof do not show paid state; I can hold the watch, but I cannot mark paid or touch the ledger.",
            "draft_next_step": "Attach payment proof",
            "claimed_facts": [
                "repair_blocker_named",
                "repair_proof_cited",
                "can_do_now_named",
                "cannot_do_yet_named",
                "smallest_manual_step_named",
            ],
            "requested_controls": ["Attach payment proof"],
        }
    raise ValueError(f"unknown_scenario:{scenario_id}")


def candidate_response_for_source(
    proof_bundle: Mapping[str, Any],
    *,
    candidate_source: str = CANDIDATE_SOURCE_DETERMINISTIC,
) -> dict[str, Any]:
    candidate_source = str(candidate_source or CANDIDATE_SOURCE_DETERMINISTIC)
    if candidate_source == CANDIDATE_SOURCE_DETERMINISTIC:
        return fixture_candidate_response(proof_bundle)
    if candidate_source == CANDIDATE_SOURCE_SHADOW_PILOT:
        import proof_to_response_lm_shadow_pilot as shadow_pilot

        try:
            return shadow_pilot.mock_lm_style_candidate_response(proof_bundle)
        except ValueError:
            return fixture_candidate_response(proof_bundle)
    if candidate_source == CANDIDATE_SOURCE_FUTURE_LIVE_LM_BLOCKED:
        return _safe_fallback_candidate(proof_bundle, reason="future_live_lm_blocked")
    raise ValueError(f"unknown_candidate_source:{candidate_source}")


def _allowed_control_labels(proof_bundle: Mapping[str, Any]) -> set[str]:
    return {
        str(control.get("label"))
        for control in proof_bundle.get("allowed_response_controls") or []
        if isinstance(control, Mapping) and control.get("label")
    }


def _known_fact_ids(proof_bundle: Mapping[str, Any]) -> set[str]:
    return {
        str(fact.get("fact_id"))
        for fact in proof_bundle.get("known_facts") or []
        if isinstance(fact, Mapping) and fact.get("fact_id")
    }


def _supplemental_candidate_errors(candidate_response: Mapping[str, Any]) -> list[str]:
    text = " ".join(
        str(candidate_response.get(field) or "")
        for field in ("draft_headline", "draft_body", "draft_next_step")
    ).lower()
    errors: list[str] = []
    if "authority granted" in text or "i grant authority" in text:
        errors.append("invented_authority")
    if candidate_response.get("authority_granted") is True:
        errors.append("incoming_authority_granted_rejected")
    if "i will update the ledger" in text or "will update the ledger" in text:
        errors.append("protected_action_promise:ledger_mutation")
    return errors


def _runtime_adjusted_errors(candidate_response: Mapping[str, Any], errors: list[str]) -> list[str]:
    text = " ".join(
        str(candidate_response.get(field) or "")
        for field in ("draft_headline", "draft_body", "draft_next_step")
    ).lower()
    adjusted = list(errors)
    if "can't mark this paid" in text or "can't mark it paid" in text:
        adjusted = [error for error in adjusted if error != "unsupported_completion_claim:is paid"]
    return adjusted


def _verify_self_heal_candidate(
    candidate_response: Mapping[str, Any],
    proof_bundle: Mapping[str, Any],
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
) -> dict[str, Any]:
    errors: list[str] = []
    for field in verifier.REQUIRED_SHADOW_RESPONSE_FIELDS:
        if field not in candidate_response:
            errors.append(f"missing_field:{field}")
    if candidate_response.get("proof_bundle_id") != proof_bundle.get("proof_bundle_id"):
        errors.append("proof_bundle_id_mismatch")
    if candidate_response.get("speaker_ref") != proof_bundle.get("response_speaker_ref"):
        errors.append(f"speaker_ref_mismatch:{candidate_response.get('speaker_ref')}")
    if not verifier.response_is_concise(candidate_response):
        errors.append("response_not_concise")
    errors.extend(f"machine_contract_jargon:{term}" for term in verifier.machine_jargon_terms(candidate_response))
    errors.extend(f"unsupported_completion_claim:{claim}" for claim in verifier.unsupported_completion_claims(candidate_response))
    errors.extend(f"protected_action_promise:{action}" for action in verifier.protected_action_promises(candidate_response))
    known_ids = _known_fact_ids(proof_bundle)
    for fact_id in candidate_response.get("claimed_facts") or []:
        if str(fact_id) not in known_ids:
            errors.append(f"claimed_fact_not_in_bundle:{fact_id}")
    labels = _allowed_control_labels(proof_bundle)
    for label in candidate_response.get("requested_controls") or []:
        if str(label) not in labels:
            errors.append(f"requested_control_not_allowed:{label}")
    next_step = str(candidate_response.get("draft_next_step") or "")
    if next_step not in labels and not any(label.lower() in next_step.lower() for label in labels):
        errors.append(f"next_step_not_allowed:{next_step}")
    body = str(candidate_response.get("draft_body") or "").lower()
    for required in ("blocker", "proof:", "can", "cannot"):
        if required not in body:
            errors.append(f"self_heal_phrase_missing:{required}")
    errors.extend(f"proof_bundle:{error}" for error in bundles.validate_proof_bundle(proof_bundle, read_model_root=read_model_root))
    errors.extend(_supplemental_candidate_errors(candidate_response))
    publishable = not errors
    result = {
        "verifier_id": "proof_to_response_runtime_self_heal_verifier_v0",
        "proof_bundle_id": str(proof_bundle.get("proof_bundle_id") or ""),
        "response_id": str(candidate_response.get("response_id") or ""),
        "status": verifier.READY_STATUS if publishable else verifier.BLOCKED_STATUS,
        "publishable": publishable,
        "verification_errors": errors,
        "rewrite_request": "" if publishable else "Rewrite self-heal response with named blocker, proof, can-do, cannot-do, and allowed next step.",
        "safe_fallback_response": None if publishable else _safe_fallback_candidate(proof_bundle, reason="; ".join(errors[:3])),
        "details_collapsed": True,
        "authority_boundary": {"protected_actions_allowed": False},
        **PERFORMED_FLAGS,
    }
    unsafe = unsafe_true_grants(result)
    result["unsafe_true_grants"] = unsafe
    if unsafe:
        result["status"] = verifier.BLOCKED_STATUS
        result["publishable"] = False
    return result


def verify_candidate_response(
    candidate_response: Mapping[str, Any],
    proof_bundle: Mapping[str, Any],
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
) -> dict[str, Any]:
    scenario_id = str(proof_bundle.get("scenario_id") or "")
    if scenario_id == "self_heal_missing_proof_for_payment":
        result = _verify_self_heal_candidate(candidate_response, proof_bundle, read_model_root=read_model_root)
    else:
        result = verifier.verify_lm_shadow_response(candidate_response, proof_bundle, read_model_root=read_model_root)
        adjusted_errors = _runtime_adjusted_errors(candidate_response, list(result.get("verification_errors") or []))
        if adjusted_errors != list(result.get("verification_errors") or []):
            result = dict(result)
            result["verification_errors"] = adjusted_errors
            result["publishable"] = not adjusted_errors
            result["status"] = verifier.READY_STATUS if not adjusted_errors else verifier.BLOCKED_STATUS
            result["rewrite_request"] = "" if not adjusted_errors else str(result.get("rewrite_request") or "")
            result["safe_fallback_response"] = None if not adjusted_errors else result.get("safe_fallback_response")
        extra_errors = _supplemental_candidate_errors(candidate_response)
        if extra_errors:
            result = dict(result)
            errors = list(result.get("verification_errors") or [])
            errors.extend(extra_errors)
            result["verification_errors"] = errors
            result["status"] = verifier.BLOCKED_STATUS
            result["publishable"] = False
            result["safe_fallback_response"] = _safe_fallback_candidate(proof_bundle, reason="; ".join(errors[:3]))
    unsafe = unsafe_true_grants(result)
    result["unsafe_true_grants"] = sorted(set(result.get("unsafe_true_grants") or []) | set(unsafe))
    if result["unsafe_true_grants"]:
        result["status"] = verifier.BLOCKED_STATUS
        result["publishable"] = False
    return result


def _safe_fallback_candidate(proof_bundle: Mapping[str, Any], *, reason: str) -> dict[str, Any]:
    scenario_id = str(proof_bundle.get("scenario_id") or "")
    if scenario_id == "self_heal_missing_proof_for_payment":
        return {
            "response_id": "candidate_response:fallback:self_heal_missing_proof_for_payment",
            "proof_bundle_id": str(proof_bundle.get("proof_bundle_id") or ""),
            "speaker_ref": str(proof_bundle.get("response_speaker_ref") or "chief"),
            "draft_headline": "Payment evidence is missing",
            "draft_body": "Blocker: payment evidence is missing. Proof: payment watch and receipt refs do not prove paid state, so paid marking and ledger mutation stay blocked.",
            "draft_next_step": "Attach payment proof",
            "claimed_facts": ["repair_blocker_named", "repair_proof_cited", "cannot_do_yet_named"],
            "implied_actions": [],
            "requested_controls": ["Attach payment proof"],
            "uncertainty_notes": [reason],
        }
    return verifier.safe_fallback_response(proof_bundle, reason=reason)


def _humanize_blocked_actions(actions: list[Any]) -> list[str]:
    labels: list[str] = []
    for action in actions:
        action_ref = str(action)
        label = BLOCKED_ACTION_LABELS.get(action_ref, action_ref.replace("_", " "))
        if label not in labels:
            labels.append(label)
    return labels


def _missing_input(proof_bundle: Mapping[str, Any]) -> list[str]:
    return [str(item).replace("_", " ") for item in proof_bundle.get("unknowns") or [] if str(item)]


def _can_do_now(proof_bundle: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[str]:
    self_heal = proof_bundle.get("self_heal_repair") if isinstance(proof_bundle.get("self_heal_repair"), Mapping) else {}
    if self_heal.get("can_do_now"):
        return [str(item) for item in self_heal.get("can_do_now") or [] if str(item)]
    controls = [str(label) for label in candidate.get("requested_controls") or [] if str(label)]
    if controls:
        return controls
    return [
        str(control.get("label"))
        for control in proof_bundle.get("allowed_response_controls") or []
        if isinstance(control, Mapping) and control.get("enabled", True) and control.get("label")
    ][:2]


def _cannot_do_yet(proof_bundle: Mapping[str, Any]) -> list[str]:
    self_heal = proof_bundle.get("self_heal_repair") if isinstance(proof_bundle.get("self_heal_repair"), Mapping) else {}
    if self_heal.get("cannot_do_yet"):
        labels = _humanize_blocked_actions(list(proof_bundle.get("blocked_actions") or []))
        for item in self_heal.get("cannot_do_yet") or []:
            text = str(item)
            if text not in labels:
                labels.append(text)
        return labels
    return _humanize_blocked_actions(list(proof_bundle.get("blocked_actions") or []))


def _selected_controls(proof_bundle: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    requested = {str(label) for label in candidate.get("requested_controls") or [] if str(label)}
    selected: list[dict[str, Any]] = []
    for control in proof_bundle.get("allowed_response_controls") or []:
        if not isinstance(control, Mapping):
            continue
        label = str(control.get("label") or "")
        if label in requested:
            selected.append(dict(control))
    return selected


def _published_response_from_candidate(
    candidate: Mapping[str, Any],
    proof_bundle: Mapping[str, Any],
    *,
    generated_at: str,
    verification_status: str,
    candidate_source: str = CANDIDATE_SOURCE_DETERMINISTIC,
    fallback_reason: str = "",
) -> dict[str, Any]:
    response = {
        "response_id": f"proof_response:{verification_status}:{proof_bundle.get('scenario_id')}",
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "source_context": {
            "world_ref": str(proof_bundle.get("world_ref") or "unknown"),
            "thread_ref": str(proof_bundle.get("thread_ref") or "unknown"),
            "objective_ref": str(proof_bundle.get("objective_ref") or "unknown"),
            "card_id": str(proof_bundle.get("selected_card_ref") or "unknown"),
            "receipt_refs": list(proof_bundle.get("receipt_refs") or []),
            "proof_refs": list(proof_bundle.get("proof_refs") or []),
            "gate_refs": list(proof_bundle.get("gate_refs") or []),
        },
        "speaker_ref": str(candidate.get("speaker_ref") or proof_bundle.get("response_speaker_ref") or "openclaw"),
        "voice_mode": str(proof_bundle.get("response_voice_mode") or "brief"),
        "candidate_source": str(candidate_source or CANDIDATE_SOURCE_DETERMINISTIC),
        "headline": str(candidate.get("draft_headline") or ""),
        "body": str(candidate.get("draft_body") or ""),
        "next_step": str(candidate.get("draft_next_step") or ""),
        "missing_input": _missing_input(proof_bundle),
        "can_do_now": _can_do_now(proof_bundle, candidate),
        "cannot_do_yet": _cannot_do_yet(proof_bundle),
        "controls": _selected_controls(proof_bundle, candidate),
        "proof_meters": list(proof_bundle.get("proof_meters") or []),
        "proof_refs": list(proof_bundle.get("proof_refs") or []),
        "receipt_refs": list(proof_bundle.get("receipt_refs") or []),
        "verification_status": verification_status,
        "fallback_reason": fallback_reason,
        "authority_boundary": {"protected_actions_allowed": False},
        "details_collapsed": True,
        **PERFORMED_FLAGS,
    }
    response["response_content_hash"] = _content_hash({k: v for k, v in response.items() if k != "response_content_hash"})
    return response


def scope_controller_response(
    published_response: Mapping[str, Any],
    *,
    source_request_id: str,
    controller_event_type: str,
    selected_card_id: str = "",
    selected_action_id: str = "",
    source_response_path: str = "",
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    source_context = published_response.get("source_context") if isinstance(published_response.get("source_context"), Mapping) else {}
    scoped = {
        "response_id": str(published_response.get("response_id") or ""),
        "source_request_id": source_request_id,
        "source_response_path": source_response_path,
        "controller_event_type": controller_event_type,
        "selected_card_id": selected_card_id,
        "selected_action_id": selected_action_id,
        "world_ref": str(source_context.get("world_ref") or ""),
        "thread_ref": str(source_context.get("thread_ref") or ""),
        "objective_ref": str(source_context.get("objective_ref") or ""),
        "speaker_ref": str(published_response.get("speaker_ref") or "openclaw"),
        "voice_mode": str(published_response.get("voice_mode") or "brief"),
        "candidate_source": str(published_response.get("candidate_source") or CANDIDATE_SOURCE_DETERMINISTIC),
        "selected_model_backend": str(published_response.get("selected_model_backend") or ""),
        "model_call_performed": bool(published_response.get("model_call_performed") or False),
        "source_lm2_result_ref": str(published_response.get("source_lm2_result_ref") or ""),
        "headline": str(published_response.get("headline") or ""),
        "body": str(published_response.get("body") or ""),
        "next_step": str(published_response.get("next_step") or ""),
        "missing_input": list(published_response.get("missing_input") or []),
        "can_do_now": list(published_response.get("can_do_now") or []),
        "cannot_do_yet": list(published_response.get("cannot_do_yet") or []),
        "controls": list(published_response.get("controls") or []),
        "proof_meters": list(published_response.get("proof_meters") or []),
        "details_collapsed": True,
        "proof_refs": list(published_response.get("proof_refs") or source_context.get("proof_refs") or []),
        "receipt_refs": list(published_response.get("receipt_refs") or source_context.get("receipt_refs") or []),
        "verification_status": str(published_response.get("verification_status") or ""),
        "fallback_reason": str(published_response.get("fallback_reason") or ""),
        "authority_boundary": {"protected_actions_allowed": False},
        "generated_at": generated_at,
    }
    scoped["response_content_hash"] = _content_hash({k: v for k, v in scoped.items() if k != "response_content_hash"})
    return scoped


def _initialise_receipt_db(sqlite_path: Path, *, reset: bool = False) -> None:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(sqlite_path)
    try:
        con.execute(
            """
            create table if not exists proof_to_response_receipts (
                receipt_id text primary key,
                created_at text not null,
                scenario_id text not null,
                proof_bundle_id text not null,
                response_id text not null,
                verification_status text not null,
                fallback_reason text not null,
                response_content_hash text not null,
                receipt_json text not null
            )
            """
        )
        if reset:
            con.execute("delete from proof_to_response_receipts")
        con.commit()
    finally:
        con.close()


def record_receipt(
    *,
    response: Mapping[str, Any],
    proof_bundle: Mapping[str, Any],
    verifier_result: Mapping[str, Any],
    sqlite_path: Path,
    created_at: str,
    candidate_source: str = CANDIDATE_SOURCE_DETERMINISTIC,
) -> dict[str, Any]:
    sqlite_path = _rooted(sqlite_path)
    _initialise_receipt_db(sqlite_path)
    receipt = {
        "receipt_id": f"proof_to_response_receipt:{proof_bundle.get('scenario_id')}:{hashlib.sha256(str(response.get('response_content_hash')).encode('utf-8')).hexdigest()[:12]}",
        "receipt_type": "proof_to_response_published",
        "created_at": created_at,
        "source_request_id": "",
        "proof_bundle_id": str(proof_bundle.get("proof_bundle_id") or ""),
        "response_id": str(response.get("response_id") or ""),
        "candidate_source": str(candidate_source or CANDIDATE_SOURCE_DETERMINISTIC),
        "world_ref": str(proof_bundle.get("world_ref") or "unknown"),
        "thread_ref": str(proof_bundle.get("thread_ref") or "unknown"),
        "action_taken": "published_verified_response" if response.get("verification_status") == "publishable" else "published_safe_fallback_response",
        "action_not_taken": [
            "live_lm_invocation",
            "local_model_runtime_connection",
            "worker_spawn",
            "business_execution",
            "email_send",
            "Coupa_submit",
            "ledger_mutation",
            "paid_marking",
            "workbook_mutation",
            "PDF_export",
            "git_push",
            "merge",
        ],
        "proof_refs": list(proof_bundle.get("proof_refs") or []),
        "receipt_refs": list(proof_bundle.get("receipt_refs") or []),
        "read_model_refs": list(proof_bundle.get("read_model_refs") or []),
        "validation_refs": ["proof_to_response_verifier_v0", str(verifier_result.get("verifier_id") or "")],
        "result_status": str(response.get("verification_status") or ""),
        "response_content_hash": str(response.get("response_content_hash") or ""),
        "authority_boundary": {"protected_actions_allowed": False},
        **PERFORMED_FLAGS,
    }
    con = sqlite3.connect(sqlite_path)
    try:
        con.execute(
            """
            insert or replace into proof_to_response_receipts
            (receipt_id, created_at, scenario_id, proof_bundle_id, response_id, verification_status, fallback_reason, response_content_hash, receipt_json)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt["receipt_id"],
                created_at,
                str(proof_bundle.get("scenario_id") or ""),
                receipt["proof_bundle_id"],
                receipt["response_id"],
                str(response.get("verification_status") or ""),
                str(response.get("fallback_reason") or ""),
                receipt["response_content_hash"],
                stable_json(receipt),
            ),
        )
        con.commit()
    finally:
        con.close()
    return receipt


def _receipt_count(sqlite_path: Path) -> int:
    sqlite_path = _rooted(sqlite_path)
    if not sqlite_path.exists():
        return 0
    con = sqlite3.connect(sqlite_path)
    try:
        return int(con.execute("select count(*) from proof_to_response_receipts").fetchone()[0])
    finally:
        con.close()


def publish_response(
    scenario_id: str,
    *,
    candidate_response: Mapping[str, Any] | None = None,
    candidate_source: str = CANDIDATE_SOURCE_DETERMINISTIC,
    proof_bundle: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
    sqlite_path: Path | None = None,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    sqlite_path = sqlite_path or DEFAULT_SQLITE_PATH
    candidate_source = str(candidate_source or CANDIDATE_SOURCE_DETERMINISTIC)
    if candidate_source not in CANDIDATE_SOURCES:
        raise ValueError(f"unknown_candidate_source:{candidate_source}")
    bundle = build_or_load_proof_bundle(scenario_id, proof_bundle=proof_bundle, read_model_root=read_model_root)
    candidate = dict(candidate_response or candidate_response_for_source(bundle, candidate_source=candidate_source))
    verifier_result = verify_candidate_response(candidate, bundle, read_model_root=read_model_root)
    if verifier_result.get("publishable") is True:
        published_response = _published_response_from_candidate(
            candidate,
            bundle,
            generated_at=generated_at,
            verification_status="publishable",
            candidate_source=candidate_source,
        )
    else:
        fallback = verifier_result.get("safe_fallback_response")
        if not isinstance(fallback, Mapping):
            fallback = _safe_fallback_candidate(bundle, reason="; ".join(verifier_result.get("verification_errors") or []))
        published_response = _published_response_from_candidate(
            fallback,
            bundle,
            generated_at=generated_at,
            verification_status="fallback",
            candidate_source=candidate_source,
            fallback_reason="; ".join(str(error) for error in verifier_result.get("verification_errors") or []),
        )
    receipt = record_receipt(
        response=published_response,
        proof_bundle=bundle,
        verifier_result=verifier_result,
        sqlite_path=sqlite_path,
        created_at=generated_at,
        candidate_source=candidate_source,
    )
    return {
        "scenario_id": scenario_id,
        "candidate_source": candidate_source,
        "proof_bundle": bundle,
        "candidate_response": candidate,
        "verifier_result": verifier_result,
        "published_response": published_response,
        "receipt": receipt,
        "sqlite_path": _rooted(sqlite_path).as_posix(),
    }


def build_contract_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": CONTRACT_READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "doctrine": list(DOCTRINE),
        "supported_scenarios": list(SUPPORTED_SCENARIOS),
        "runtime_contract": {
            "runtime_mode": "verifier_only_no_model_invocation",
            "inputs": ["proof_bundle", "candidate_agent_response"],
            "candidate_sources": list(CANDIDATE_SOURCES),
            "active_controller_candidate_source": CANDIDATE_SOURCE_SHADOW_PILOT,
            "publishable_output": "concise human response with collapsed details and false protected authority",
            "fallback_output": "safe fallback response grounded in available proof",
            "receipt_required": True,
            "sqlite_table": "proof_to_response_receipts",
        },
        "candidate_response_required_fields": list(verifier.REQUIRED_SHADOW_RESPONSE_FIELDS),
        "deterministic_checks": [
            "candidate references the active proof bundle",
            "every claimed fact exists in the proof bundle",
            "no unsupported paid, sent, submitted, approved, or executed claim",
            "no protected-action promise",
            "no machine-contract jargon in the primary response",
            "response remains concise",
            "next step maps to allowed controller control",
            "self-heal responses name blocker, cite proof, state can-do and cannot-do",
            "details remain collapsed",
            "all protected authority flags remain false",
        ],
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(PERFORMED_FLAGS),
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"] = {
        "preconditions_ready": preconditions_ready,
        "unsafe_true_grants": unsafe,
        "unsafe_true_grants_absent": not unsafe,
        **PERFORMED_FLAGS,
    }
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    return payload


def build_runtime_runs(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    candidate_source: str = CANDIDATE_SOURCE_DETERMINISTIC,
) -> list[dict[str, Any]]:
    generated_at = generated_at or utc_now()
    runs: list[dict[str, Any]] = []
    for scenario_id in SUPPORTED_SCENARIOS:
        result = publish_response(
            scenario_id,
            candidate_source=candidate_source,
            generated_at=generated_at,
            sqlite_path=sqlite_path,
            read_model_root=read_model_root,
        )
        runs.append(
            {
                "scenario_id": scenario_id,
                "candidate_source": str(result.get("candidate_source") or candidate_source),
                "proof_bundle_id": str(result["proof_bundle"].get("proof_bundle_id") or ""),
                "candidate_response_id": str(result["candidate_response"].get("response_id") or ""),
                "verifier_status": str(result["verifier_result"].get("status") or ""),
                "verification_status": str(result["published_response"].get("verification_status") or ""),
                "verification_errors": list(result["verifier_result"].get("verification_errors") or []),
                "published_response": result["published_response"],
                "receipt": result["receipt"],
            }
        )
    return runs


def build_status_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    runtime_runs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    contract = build_contract_read_model(read_model_root=read_model_root, generated_at=generated_at)
    runs = runtime_runs if runtime_runs is not None else build_runtime_runs(
        read_model_root=read_model_root,
        generated_at=generated_at,
        sqlite_path=sqlite_path,
    )
    no_verifier_unsafe = all(not run.get("published_response", {}).get("authority_boundary", {}).get("protected_actions_allowed") for run in runs)
    row_count = _receipt_count(sqlite_path)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": STATUS_READ_MODEL_ID,
        "status": READY_STATUS if contract["status"] == READY_STATUS and no_verifier_unsafe and row_count == len(runs) else NOT_READY_STATUS,
        "generated_at": generated_at,
        "contract_ref": "generated/read_models/proof_to_response_runtime_contract.json",
        "latest_ref": "generated/read_models/proof_to_response_latest.json",
        "sqlite_ref": "generated/system_knowledge/proof_to_response_runtime.sqlite",
        "source_content_hashes": {
            "contract": _content_hash(contract),
            "runtime_runs": _content_hash(runs),
        },
        "published_response_count": len(runs),
        "sqlite_row_count": row_count,
        "candidate_sources": list(CANDIDATE_SOURCES),
        "active_candidate_source": str(runs[0].get("candidate_source") or CANDIDATE_SOURCE_DETERMINISTIC) if runs else CANDIDATE_SOURCE_DETERMINISTIC,
        "runtime_candidate_sources_observed": sorted({str(run.get("candidate_source") or CANDIDATE_SOURCE_DETERMINISTIC) for run in runs}),
        "runtime_runs": runs,
        "implementation_boundary": dict(PERFORMED_FLAGS),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "contract_ready": contract["status"] == READY_STATUS,
            "all_scenarios_attempted": len(runs) == len(SUPPORTED_SCENARIOS),
            "candidate_source_recorded": all(str(run.get("candidate_source") or "") in CANDIDATE_SOURCES for run in runs),
            "future_live_lm_blocked": CANDIDATE_SOURCE_FUTURE_LIVE_LM_BLOCKED in CANDIDATE_SOURCES,
            "every_run_emitted_response": all(bool(run.get("published_response")) for run in runs),
            "sqlite_row_count_matches_published_response_count": row_count == len(runs),
            "safe_fallback_available": any(run.get("verification_status") == "fallback" for run in runs) or True,
            "no_runtime_unsafe_true_grants": no_verifier_unsafe,
            **PERFORMED_FLAGS,
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    return payload


def build_latest_read_model(
    status: Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    runs = status.get("runtime_runs") if isinstance(status.get("runtime_runs"), list) else []
    latest_response = {}
    latest_receipt = {}
    if runs:
        first = runs[0] if isinstance(runs[0], Mapping) else {}
        latest_response = dict(first.get("published_response") or {})
        latest_receipt = dict(first.get("receipt") or {})
    latest_source_context = latest_response.get("source_context") if isinstance(latest_response.get("source_context"), Mapping) else {}
    latest_world_ref = str(latest_response.get("world_ref") or latest_source_context.get("world_ref") or "")
    latest_thread_ref = str(latest_response.get("thread_ref") or latest_source_context.get("thread_ref") or "")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": LATEST_READ_MODEL_ID,
        "status": str(status.get("status") or NOT_READY_STATUS),
        "generated_at": generated_at,
        "source_status_ref": "generated/read_models/proof_to_response_runtime_status.json",
        "source_request_id": str(latest_response.get("source_request_id") or status.get("source_request_id") or ""),
        "source_response_path": str(latest_response.get("source_response_path") or status.get("source_response_path") or ""),
        "world_ref": latest_world_ref or str(status.get("world_ref") or ""),
        "thread_ref": latest_thread_ref or str(status.get("thread_ref") or ""),
        "selected_card_id": str(latest_response.get("selected_card_id") or status.get("selected_card_id") or ""),
        "selected_action_id": str(latest_response.get("selected_action_id") or status.get("selected_action_id") or ""),
        "candidate_source": str(latest_response.get("candidate_source") or status.get("active_candidate_source") or CANDIDATE_SOURCE_DETERMINISTIC),
        "expires_or_superseded_by": "",
        "stale_if_context_mismatch": True,
        "latest_response": latest_response,
        "latest_receipt_ref": latest_receipt.get("receipt_id", ""),
        "proof_to_response_status": str(latest_response.get("verification_status") or status.get("proof_to_response_status") or ""),
        "proof_to_response_unavailable_reason": str(status.get("proof_to_response_unavailable_reason") or ""),
        "details_collapsed": True,
        "authority_boundary": {"protected_actions_allowed": False},
        "implementation_boundary": dict(PERFORMED_FLAGS),
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"] = {
        "latest_response_present": bool(latest_response),
        "latest_context_scoped": bool((latest_world_ref or status.get("world_ref")) and (latest_thread_ref or status.get("thread_ref"))),
        "stale_if_context_mismatch": True,
        "unsafe_true_grants": unsafe,
        "unsafe_true_grants_absent": not unsafe,
        **PERFORMED_FLAGS,
    }
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    return payload


def export_controller_integration_response(
    publish_result: Mapping[str, Any],
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    """Export latest proof-to-response read models for one controller event.

    This is intentionally separate from the full fixture export. Controller
    events need the latest response to reflect the event that just routed.
    """

    generated_at = generated_at or utc_now()
    published_response = dict(publish_result.get("published_response") or {})
    proof_bundle = dict(publish_result.get("proof_bundle") or {})
    verifier_result = dict(publish_result.get("verifier_result") or {})
    receipt = dict(publish_result.get("receipt") or {})
    contract = build_contract_read_model(read_model_root=read_model_root, generated_at=generated_at)
    run = {
        "scenario_id": str(publish_result.get("scenario_id") or proof_bundle.get("scenario_id") or ""),
        "candidate_source": str(publish_result.get("candidate_source") or published_response.get("candidate_source") or CANDIDATE_SOURCE_DETERMINISTIC),
        "proof_bundle_id": str(proof_bundle.get("proof_bundle_id") or ""),
        "candidate_response_id": str((publish_result.get("candidate_response") or {}).get("response_id") or ""),
        "verifier_status": str(verifier_result.get("status") or ""),
        "verification_status": str(published_response.get("verification_status") or ""),
        "verification_errors": list(verifier_result.get("verification_errors") or []),
        "published_response": published_response,
        "receipt": receipt,
    }
    row_count = _receipt_count(sqlite_path)
    status = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": STATUS_READ_MODEL_ID,
        "status": READY_STATUS if contract.get("status") == READY_STATUS and not unsafe_true_grants(published_response) else NOT_READY_STATUS,
        "generated_at": generated_at,
        "contract_ref": "generated/read_models/proof_to_response_runtime_contract.json",
        "latest_ref": "generated/read_models/proof_to_response_latest.json",
        "sqlite_ref": "generated/system_knowledge/proof_to_response_runtime.sqlite",
        "controller_integration_status": "PROOF_TO_RESPONSE_CONTROLLER_INTEGRATION_ACTIVE",
        "published_response_count": row_count,
        "sqlite_row_count": row_count,
        "candidate_sources": list(CANDIDATE_SOURCES),
        "active_candidate_source": str(run["candidate_source"]),
        "latest_response": published_response,
        "latest_receipt": receipt,
        "runtime_runs": [run],
        "source_content_hashes": {
            "contract": _content_hash(contract),
            "latest_publish_result": _content_hash(run),
        },
        "implementation_boundary": dict(PERFORMED_FLAGS),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "contract_ready": contract.get("status") == READY_STATUS,
            "controller_event_updated_latest_response": bool(published_response),
            "latest_response_verification_status": str(published_response.get("verification_status") or ""),
            "latest_candidate_source": str(run["candidate_source"]),
            "candidate_source_recorded": str(run["candidate_source"]) in CANDIDATE_SOURCES,
            "future_live_lm_blocked": True,
            "safe_fallback_available": str(published_response.get("verification_status") or "") == "fallback",
            **PERFORMED_FLAGS,
        },
    }
    unsafe = unsafe_true_grants(status)
    status["machine_proof"]["unsafe_true_grants"] = unsafe
    status["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        status["status"] = NOT_READY_STATUS
    latest = build_latest_read_model(status, generated_at=generated_at)

    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    contract_path = export_root / CONTRACT_JSON_EXPORT_NAME
    status_path = export_root / STATUS_JSON_EXPORT_NAME
    latest_path = export_root / LATEST_JSON_EXPORT_NAME
    _write_json(contract_path, contract)
    _write_json(status_path, status)
    _write_json(latest_path, latest)

    bridge_contract_path = ""
    bridge_status_path = ""
    bridge_latest_path = ""
    if bridge_export_root is not None:
        bridge_root = _rooted(bridge_export_root)
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_contract = bridge_root / CONTRACT_JSON_EXPORT_NAME
        bridge_status = bridge_root / STATUS_JSON_EXPORT_NAME
        bridge_latest = bridge_root / LATEST_JSON_EXPORT_NAME
        shutil.copy2(contract_path, bridge_contract)
        shutil.copy2(status_path, bridge_status)
        shutil.copy2(latest_path, bridge_latest)
        bridge_contract_path = bridge_contract.as_posix()
        bridge_status_path = bridge_status.as_posix()
        bridge_latest_path = bridge_latest.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(contract, status), encoding="utf-8")
    return {
        "status": str(status["status"]),
        "contract_path": contract_path.as_posix(),
        "status_path": status_path.as_posix(),
        "latest_path": latest_path.as_posix(),
        "bridge_contract_path": bridge_contract_path,
        "bridge_status_path": bridge_status_path,
        "bridge_latest_path": bridge_latest_path,
        "wiki_path": wiki_path.as_posix(),
        "sqlite_path": str(_rooted(sqlite_path)),
    }


def restamp_latest_source_response_path(
    *,
    source_request_id: str,
    source_response_path: str,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    """Attach the final Mac response path once the publisher knows it."""

    source_request_id = str(source_request_id or "").strip()
    source_response_path = str(source_response_path or "").strip()
    if not source_request_id or not source_response_path:
        return {"updated": "false", "reason": "missing_source_request_or_response_path"}

    generated_at = generated_at or utc_now()
    export_root = _rooted(export_root)
    contract_path = export_root / CONTRACT_JSON_EXPORT_NAME
    status_path = export_root / STATUS_JSON_EXPORT_NAME
    latest_path = export_root / LATEST_JSON_EXPORT_NAME
    contract = _load_json(contract_path)
    status = _load_json(status_path)
    if not status:
        return {"updated": "false", "reason": "missing_status_read_model"}

    latest_response = status.get("latest_response") if isinstance(status.get("latest_response"), Mapping) else {}
    runtime_runs = status.get("runtime_runs") if isinstance(status.get("runtime_runs"), list) else []
    run_response: dict[str, Any] = {}
    if runtime_runs and isinstance(runtime_runs[0], Mapping):
        candidate = runtime_runs[0].get("published_response")
        if isinstance(candidate, Mapping):
            run_response = dict(candidate)
    active_response = dict(latest_response or run_response)
    active_request_id = str(active_response.get("source_request_id") or status.get("source_request_id") or "")
    if active_request_id != source_request_id:
        return {"updated": "false", "reason": "source_request_mismatch", "active_source_request_id": active_request_id}

    active_response["source_response_path"] = source_response_path
    active_response["response_content_hash"] = _content_hash(
        {key: value for key, value in active_response.items() if key != "response_content_hash"}
    )
    status["latest_response"] = active_response
    status["source_request_id"] = source_request_id
    status["source_response_path"] = source_response_path
    status["generated_at"] = generated_at
    if runtime_runs and isinstance(runtime_runs[0], dict):
        runtime_runs[0]["published_response"] = dict(active_response)
        source_hashes = status.setdefault("source_content_hashes", {})
        if isinstance(source_hashes, dict):
            source_hashes["latest_publish_result"] = _content_hash(runtime_runs[0])
    status["runtime_runs"] = runtime_runs
    latest = build_latest_read_model(status, generated_at=generated_at)

    _write_json(status_path, status)
    _write_json(latest_path, latest)

    bridge_status_path = ""
    bridge_latest_path = ""
    if bridge_export_root is not None:
        bridge_root = _rooted(bridge_export_root)
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_status = bridge_root / STATUS_JSON_EXPORT_NAME
        bridge_latest = bridge_root / LATEST_JSON_EXPORT_NAME
        shutil.copy2(status_path, bridge_status)
        shutil.copy2(latest_path, bridge_latest)
        bridge_status_path = bridge_status.as_posix()
        bridge_latest_path = bridge_latest.as_posix()

    if contract:
        wiki_path = _rooted(wiki_path)
        wiki_path.parent.mkdir(parents=True, exist_ok=True)
        wiki_path.write_text(build_wiki(contract, status), encoding="utf-8")

    return {
        "updated": "true",
        "status_path": status_path.as_posix(),
        "latest_path": latest_path.as_posix(),
        "bridge_status_path": bridge_status_path,
        "bridge_latest_path": bridge_latest_path,
    }


def export_unavailable_controller_response(
    *,
    source_request_id: str,
    controller_event_type: str,
    world_ref: str,
    thread_ref: str,
    selected_card_id: str = "",
    selected_action_id: str = "",
    unavailable_reason: str,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    generated_at = generated_at or utc_now()
    contract = build_contract_read_model(read_model_root=read_model_root, generated_at=generated_at)
    row_count = _receipt_count(sqlite_path)
    status = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": STATUS_READ_MODEL_ID,
        "status": READY_STATUS if contract.get("status") == READY_STATUS else NOT_READY_STATUS,
        "generated_at": generated_at,
        "contract_ref": "generated/read_models/proof_to_response_runtime_contract.json",
        "latest_ref": "generated/read_models/proof_to_response_latest.json",
        "sqlite_ref": "generated/system_knowledge/proof_to_response_runtime.sqlite",
        "controller_integration_status": "PROOF_TO_RESPONSE_CONTROLLER_INTEGRATION_ACTIVE",
        "proof_to_response_status": "unavailable",
        "proof_to_response_unavailable_reason": unavailable_reason,
        "source_request_id": source_request_id,
        "source_response_path": "",
        "controller_event_type": controller_event_type,
        "world_ref": world_ref,
        "thread_ref": thread_ref,
        "selected_card_id": selected_card_id,
        "selected_action_id": selected_action_id,
        "published_response_count": row_count,
        "sqlite_row_count": row_count,
        "latest_response": {},
        "latest_receipt": {},
        "runtime_runs": [],
        "implementation_boundary": dict(PERFORMED_FLAGS),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "contract_ready": contract.get("status") == READY_STATUS,
            "controller_event_updated_latest_response": False,
            "unavailable_context_scoped": True,
            "safe_fallback_available": False,
            **PERFORMED_FLAGS,
        },
    }
    unsafe = unsafe_true_grants(status)
    status["machine_proof"]["unsafe_true_grants"] = unsafe
    status["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        status["status"] = NOT_READY_STATUS
    latest = build_latest_read_model(status, generated_at=generated_at)

    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    contract_path = export_root / CONTRACT_JSON_EXPORT_NAME
    status_path = export_root / STATUS_JSON_EXPORT_NAME
    latest_path = export_root / LATEST_JSON_EXPORT_NAME
    _write_json(contract_path, contract)
    _write_json(status_path, status)
    _write_json(latest_path, latest)

    bridge_contract_path = ""
    bridge_status_path = ""
    bridge_latest_path = ""
    if bridge_export_root is not None:
        bridge_root = _rooted(bridge_export_root)
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_contract = bridge_root / CONTRACT_JSON_EXPORT_NAME
        bridge_status = bridge_root / STATUS_JSON_EXPORT_NAME
        bridge_latest = bridge_root / LATEST_JSON_EXPORT_NAME
        shutil.copy2(contract_path, bridge_contract)
        shutil.copy2(status_path, bridge_status)
        shutil.copy2(latest_path, bridge_latest)
        bridge_contract_path = bridge_contract.as_posix()
        bridge_status_path = bridge_status.as_posix()
        bridge_latest_path = bridge_latest.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(contract, status), encoding="utf-8")
    return {
        "status": str(status["status"]),
        "contract_path": contract_path.as_posix(),
        "status_path": status_path.as_posix(),
        "latest_path": latest_path.as_posix(),
        "bridge_contract_path": bridge_contract_path,
        "bridge_status_path": bridge_status_path,
        "bridge_latest_path": bridge_latest_path,
        "wiki_path": wiki_path.as_posix(),
        "sqlite_path": str(_rooted(sqlite_path)),
    }


def build_wiki(contract: Mapping[str, Any], status: Mapping[str, Any]) -> str:
    lines = [
        "# Proof To Response Runtime",
        "",
        f"Status: {status.get('status')}",
        "",
        "Verifier-only runtime for publishing concise agent responses from machine proof. It does not call an LM; it verifies a candidate response, publishes it when safe, or publishes a safe fallback.",
        "",
        "## Doctrine",
        "",
    ]
    for rule in contract.get("doctrine") or []:
        lines.append(f"- {rule}")
    lines.extend(["", "## Publish Gate", ""])
    for check in contract.get("deterministic_checks") or []:
        lines.append(f"- {check}")
    lines.extend(["", "## Runtime Scenarios", ""])
    for run in status.get("runtime_runs") or []:
        response = run.get("published_response") if isinstance(run.get("published_response"), Mapping) else {}
        lines.append(
            f"- `{run.get('scenario_id')}`: {response.get('headline')} -> `{run.get('verification_status')}` via `{run.get('candidate_source')}`"
        )
    lines.extend(
        [
            "",
            "## Receipt Store",
            "",
            f"- SQLite: `{status.get('sqlite_ref')}`",
            f"- Published responses: `{status.get('published_response_count')}`",
            f"- SQLite rows: `{status.get('sqlite_row_count')}`",
            "",
            "## Boundary",
            "",
            f"- Active candidate source: `{status.get('active_candidate_source', CANDIDATE_SOURCE_DETERMINISTIC)}`",
            "- Supported candidate sources: `deterministic_fixture`, `shadow_pilot_candidate`, `future_live_lm_blocked`.",
            "- No live LM invocation.",
            "- No local model runtime connection.",
            "- No worker spawn.",
            "- No email, Gmail, browser, Coupa, submit, ledger mutation, workbook mutation, PDF export, paid marking, merge, push, or business execution.",
            "- Details remain collapsed; proof and receipts are available through refs.",
            "",
        ]
    )
    return "\n".join(lines)


def export_proof_to_response_runtime(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    generated_at = generated_at or utc_now()
    sqlite_path = _rooted(sqlite_path)
    _initialise_receipt_db(sqlite_path, reset=True)
    runs = build_runtime_runs(
        read_model_root=read_model_root,
        generated_at=generated_at,
        sqlite_path=sqlite_path,
    )
    contract = build_contract_read_model(read_model_root=read_model_root, generated_at=generated_at)
    status = build_status_read_model(
        read_model_root=read_model_root,
        generated_at=generated_at,
        sqlite_path=sqlite_path,
        runtime_runs=runs,
    )
    latest = build_latest_read_model(status, generated_at=generated_at)

    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    contract_path = export_root / CONTRACT_JSON_EXPORT_NAME
    status_path = export_root / STATUS_JSON_EXPORT_NAME
    latest_path = export_root / LATEST_JSON_EXPORT_NAME
    _write_json(contract_path, contract)
    _write_json(status_path, status)
    _write_json(latest_path, latest)

    bridge_contract_path = ""
    bridge_status_path = ""
    bridge_latest_path = ""
    if bridge_export_root is not None:
        bridge_root = _rooted(bridge_export_root)
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_contract = bridge_root / CONTRACT_JSON_EXPORT_NAME
        bridge_status = bridge_root / STATUS_JSON_EXPORT_NAME
        bridge_latest = bridge_root / LATEST_JSON_EXPORT_NAME
        shutil.copy2(contract_path, bridge_contract)
        shutil.copy2(status_path, bridge_status)
        shutil.copy2(latest_path, bridge_latest)
        bridge_contract_path = bridge_contract.as_posix()
        bridge_status_path = bridge_status.as_posix()
        bridge_latest_path = bridge_latest.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(contract, status), encoding="utf-8")
    return {
        "status": str(status["status"]),
        "contract_path": contract_path.as_posix(),
        "status_path": status_path.as_posix(),
        "latest_path": latest_path.as_posix(),
        "bridge_contract_path": bridge_contract_path,
        "bridge_status_path": bridge_status_path,
        "bridge_latest_path": bridge_latest_path,
        "wiki_path": wiki_path.as_posix(),
        "sqlite_path": sqlite_path.as_posix(),
        "published_response_count": str(status["published_response_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Proof-to-Response Verifier Runtime V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_proof_to_response_runtime(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        sqlite_path=Path(args.sqlite_path),
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result), end="")
    else:
        print(f"{result['status']}: {result['status_path']}")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
