"""Proof-to-Response TDD Spec V0.

Defines the deterministic contract for turning receipts, gates, dynamic cards,
proof meters, and package state into concise operator-facing responses. This is
a test-driven spec for a future phrasing layer; it does not call live LMs, local
model runtimes, workers, or external providers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Proof To Response TDD Spec.md")

SCHEMA_VERSION = "proof_to_response_tdd_spec_v0"
READ_MODEL_ID = "proof_to_response_tdd_spec"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "PROOF_TO_RESPONSE_TDD_SPEC_READY"
NOT_READY_STATUS = "PROOF_TO_RESPONSE_TDD_SPEC_NOT_READY"

SPEAKER_REFS = ("cassandra", "chief", "hermes", "guardian", "niles", "openclaw")
VOICE_MODES = ("brief", "diagnostic", "safety", "creative", "operations")
GROUNDING_ORDER = ("receipts", "gates", "cards", "proof_meters", "package_state", "generated_summary")

REQUIRED_RESPONSE_FIELDS = (
    "response_id",
    "source_context",
    "speaker_ref",
    "voice_mode",
    "human_response",
    "controls",
    "proof_meters",
    "authority_boundary",
    "details_collapsed",
)
REQUIRED_SOURCE_CONTEXT_FIELDS = (
    "world_ref",
    "thread_ref",
    "objective_ref",
    "card_id",
    "receipt_refs",
    "proof_refs",
    "gate_refs",
)
REQUIRED_HUMAN_RESPONSE_FIELDS = (
    "headline",
    "body",
    "next_step",
    "missing_input",
    "what_i_can_do_now",
    "what_i_cannot_do_yet",
)

MACHINE_CONTRACT_JARGON = (
    "card deck",
    "dynamic card",
    "dynamic_card",
    "machine proof",
    "read model",
    "read_model",
    "receipt_ref",
    "receipt refs",
    "proof_ref",
    "proof refs",
    "gate_ref",
    "gate refs",
    "source_context",
    "authority_boundary",
    "schema_version",
    "sqlite",
    "hash ref",
)

UNSAFE_TRUE_KEYS = {
    "protected_actions_allowed",
    "authority_granted",
    "authority_grant_allowed",
    "business_action_allowed",
    "business_action_performed",
    "paid",
    "paid_marking_allowed",
    "paid_marking_performed",
    "ledger_mutation_allowed",
    "ledger_mutation_performed",
    "ledger_posting_allowed",
    "email_send_allowed",
    "email_send_performed",
    "coupa_allowed",
    "coupa_submit_performed",
    "portal_submit_allowed",
    "workbook_mutation_allowed",
    "workbook_mutation_performed",
    "pdf_export_allowed",
    "pdf_export_performed",
    "git_push_allowed",
    "git_push_performed",
    "merge_allowed",
    "merge_performed",
    "worker_spawn_allowed",
    "worker_spawn_performed",
    "external_llm_allowed",
    "external_llm_invoked",
    "local_model_runtime_allowed",
    "local_model_runtime_connected",
    "external_action_allowed",
    "incoming_authority_granted_accepted",
    "lm_may_create_truth",
    "lm_may_create_authority",
    "cards_are_main_response",
    "details_expanded_by_default",
}

AUTHORITY_BOUNDARY = {
    "protected_actions_allowed": False,
    "authority_grant_allowed": False,
    "business_action_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "ledger_posting_allowed": False,
    "paid": False,
    "paid_marking_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
    "worker_spawn_allowed": False,
    "external_llm_allowed": False,
    "local_model_runtime_allowed": False,
    "external_action_allowed": False,
}

PRECONDITIONS = {
    "operator_controller_event_live_route": {
        "filename": "operator_controller_event_router_status.json",
        "accepted_statuses": ["OPERATOR_CONTROLLER_EVENT_LIVE_ROUTE_READY", "OPERATOR_CONTROLLER_EVENT_ROUTER_READY"],
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
    "objective_advancement_controller_route": {
        "filename": "objective_advancement_protocol.json",
        "accepted_statuses": ["OBJECTIVE_ADVANCEMENT_CONTROLLER_ROUTE_READY", "OBJECTIVE_ADVANCEMENT_PROTOCOL_READY"],
    },
    "mac_objective_advancement_playability": {
        "filename": "objective_advancement_protocol.json",
        "accepted_statuses": ["MAC_OBJECTIVE_ADVANCEMENT_PLAYABILITY_READY", "OBJECTIVE_ADVANCEMENT_PROTOCOL_READY"],
        "note": "No dedicated PC read model exists; the local protocol readiness is used as the available proxy source.",
    },
}

DOCTRINE = (
    "Cards are not the main response.",
    "The main response is concise human text from the appropriate agent.",
    "The response must be grounded in machine proof.",
    "The LM may phrase and prioritize.",
    "The LM may not create truth or authority.",
    "If proof is missing, the response must say what is missing.",
    "If protected action is blocked, the response must say what approval/proof is needed.",
    "Details/proof remain available but not primary.",
)

SOURCE_REFS = {
    "dynamic_cards": "generated/read_models/dynamic_card_packet_latest.json",
    "receipts": "generated/read_models/universal_receipt_envelope_status.json",
    "proof_meters": "generated/read_models/proof_meter_normalization.json",
    "gates": "generated/read_models/gate_decision_ledger.json",
    "actions": "generated/read_models/operator_action_payloads.json",
    "objective": "generated/read_models/objective_advancement_protocol.json",
    "controller_router": "generated/read_models/operator_controller_event_router_status.json",
    "workflow_package": "generated/read_models/workflow_package_request_consumer_status.json",
    "review_decisions": "generated/read_models/workroom_review_decision_status.json",
    "evidence_intake": "generated/read_models/evidence_intake_status.json",
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
    for ref, contract in PRECONDITIONS.items():
        filename = str(contract["filename"])
        payload = _load_json(root / filename)
        observed = _observed_status(payload)
        accepted = [str(status) for status in contract["accepted_statuses"]]
        row = {
            "precondition_ref": ref,
            "source_ref": f"generated/read_models/{filename}",
            "observed_status": observed,
            "accepted_statuses": accepted,
            "ready": observed in accepted,
        }
        if contract.get("note"):
            row["note"] = str(contract["note"])
        rows.append(row)
    return rows


def _source_context(
    *,
    world_ref: str,
    thread_ref: str,
    objective_ref: str,
    card_id: str,
    receipt_refs: list[str] | None = None,
    proof_refs: list[str] | None = None,
    gate_refs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "world_ref": world_ref,
        "thread_ref": thread_ref,
        "objective_ref": objective_ref,
        "card_id": card_id,
        "receipt_refs": receipt_refs or [],
        "proof_refs": proof_refs or [],
        "gate_refs": gate_refs or [],
    }


def _human(
    *,
    headline: str,
    body: str,
    next_step: str,
    missing_input: list[str] | None = None,
    what_i_can_do_now: list[str] | None = None,
    what_i_cannot_do_yet: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "headline": headline,
        "body": body,
        "next_step": next_step,
        "missing_input": missing_input or [],
        "what_i_can_do_now": what_i_can_do_now or [],
        "what_i_cannot_do_yet": what_i_cannot_do_yet or [],
    }


def _claim(claim: str, *source_refs: str) -> dict[str, Any]:
    return {"claim": claim, "source_refs": list(dict.fromkeys(source_refs))}


def _meter(card_id: str, meter_ref: str, meter_state: str, source_ref: str = SOURCE_REFS["proof_meters"]) -> dict[str, Any]:
    return {
        "card_id": card_id,
        "meter_ref": meter_ref,
        "meter_state": meter_state,
        "source_ref": source_ref,
        "opens_details": True,
    }


def _control(label: str, controller_event_type: str, enabled: bool = True, disabled_reason: str = "") -> dict[str, Any]:
    return {
        "label": label,
        "controller_event_type": controller_event_type,
        "enabled": enabled,
        "disabled_reason": disabled_reason,
        "authority_boundary": {"protected_actions_allowed": False},
    }


def _response(
    *,
    scenario_id: str,
    source_context: Mapping[str, Any],
    speaker_ref: str,
    voice_mode: str,
    human_response: Mapping[str, Any],
    controls: list[Mapping[str, Any]],
    proof_meters: list[Mapping[str, Any]],
    factual_claims: list[Mapping[str, Any]],
    source_refs: list[str],
    expected_lm_contract: str,
) -> dict[str, Any]:
    base = {
        "scenario_id": scenario_id,
        "response_id": f"proof_response:{scenario_id}",
        "source_context": dict(source_context),
        "speaker_ref": speaker_ref,
        "voice_mode": voice_mode,
        "human_response": dict(human_response),
        "controls": [dict(control) for control in controls],
        "proof_meters": [dict(meter) for meter in proof_meters],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "details_collapsed": True,
        "source_refs": list(dict.fromkeys(source_refs)),
        "factual_claims": [dict(claim) for claim in factual_claims],
        "grounding_order": list(GROUNDING_ORDER),
        "expected_lm_contract": expected_lm_contract,
        "forbidden_primary_response_terms": list(MACHINE_CONTRACT_JARGON),
    }
    return base


def example_responses() -> list[dict[str, Any]]:
    capital_card = "dynamic_card.finance.capital_hilton.payment_watch"
    live_arts_card = "dynamic_card.finance.live_arts_md.evidence_intake.payment_processing"
    bd_card = "dynamic_card.business_development.capital_hilton.proposal"
    review_card = "dynamic_card.build.review_packet.completed_historical_receipt"
    gate_card = "dynamic_card.finance.capital_hilton.approval_request.coupa_submit"
    return [
        _response(
            scenario_id="finance_capital_hilton_payment_watch",
            source_context=_source_context(
                world_ref="finance",
                thread_ref="capital_hilton",
                objective_ref="objective:finance:capital_hilton:payment_watch",
                card_id=capital_card,
                receipt_refs=["universal_receipt:dynamic_card_emitted:e811c126f7bdf8d4"],
                proof_refs=[SOURCE_REFS["dynamic_cards"], SOURCE_REFS["proof_meters"], SOURCE_REFS["objective"]],
                gate_refs=[],
            ),
            speaker_ref="chief",
            voice_mode="operations",
            human_response=_human(
                headline="Capital Hilton is still on payment watch",
                body="Payment evidence is missing, so the ledger remains untouched.",
                next_step="Attach proof",
                missing_input=["payment evidence"],
                what_i_can_do_now=["watch for proof", "show the detail drawer"],
                what_i_cannot_do_yet=["mark paid", "change the ledger"],
            ),
            controls=[_control("Attach proof", "attach_proof"), _control("Show details", "show_details")],
            proof_meters=[
                _meter(capital_card, "truth", "trusted_current"),
                _meter(capital_card, "authority", "no_grant"),
                _meter(capital_card, "risk", "watch"),
            ],
            factual_claims=[
                _claim("Payment evidence is missing.", SOURCE_REFS["dynamic_cards"], SOURCE_REFS["proof_meters"]),
                _claim("The ledger remains untouched.", SOURCE_REFS["receipts"], SOURCE_REFS["objective"]),
                _claim("Attach proof is the next safe control.", SOURCE_REFS["actions"], SOURCE_REFS["objective"]),
            ],
            source_refs=[SOURCE_REFS["dynamic_cards"], SOURCE_REFS["proof_meters"], SOURCE_REFS["receipts"], SOURCE_REFS["actions"], SOURCE_REFS["objective"]],
            expected_lm_contract="Phrase the payment-watch state briefly; do not imply paid state or ledger mutation.",
        ),
        _response(
            scenario_id="finance_live_arts_payment_evidence",
            source_context=_source_context(
                world_ref="finance",
                thread_ref="live_arts_md",
                objective_ref="objective:finance:live_arts_md:evidence_intake",
                card_id=live_arts_card,
                receipt_refs=["universal_receipt:evidence_recorded:d575c566537ac901"],
                proof_refs=[SOURCE_REFS["evidence_intake"], SOURCE_REFS["proof_meters"], SOURCE_REFS["receipts"]],
                gate_refs=[],
            ),
            speaker_ref="guardian",
            voice_mode="safety",
            human_response=_human(
                headline="Live Arts payment evidence recorded",
                body="Candidate evidence recorded. That does not mark paid, and the ledger stays untouched.",
                next_step="Verify arrival or review the ledger later",
                missing_input=["payment arrival confirmation", "ledger evidence"],
                what_i_can_do_now=["keep the evidence attached", "wait for verified arrival"],
                what_i_cannot_do_yet=["mark paid", "change the ledger"],
            ),
            controls=[_control("Show details", "show_details"), _control("Verify later", "stage_plan")],
            proof_meters=[
                _meter(live_arts_card, "truth", "operator_reported"),
                _meter(live_arts_card, "evidence", "operator_reported"),
                _meter(live_arts_card, "freshness", "waiting_external"),
            ],
            factual_claims=[
                _claim("Candidate evidence was recorded.", SOURCE_REFS["evidence_intake"], SOURCE_REFS["receipts"]),
                _claim("The evidence does not prove paid state.", SOURCE_REFS["proof_meters"], SOURCE_REFS["receipts"]),
                _claim("The ledger was not changed.", SOURCE_REFS["receipts"], SOURCE_REFS["evidence_intake"]),
            ],
            source_refs=[SOURCE_REFS["evidence_intake"], SOURCE_REFS["proof_meters"], SOURCE_REFS["receipts"]],
            expected_lm_contract="Report evidence intake without upgrading candidate/operator-reported proof into paid truth.",
        ),
        _response(
            scenario_id="business_development_capital_hilton_followup",
            source_context=_source_context(
                world_ref="business_development",
                thread_ref="capital_hilton",
                objective_ref="objective:business_development:capital_hilton:followup",
                card_id=bd_card,
                receipt_refs=["universal_receipt:package_staged:7901f9da098e3f3f"],
                proof_refs=[SOURCE_REFS["workflow_package"], SOURCE_REFS["dynamic_cards"]],
                gate_refs=[],
            ),
            speaker_ref="cassandra",
            voice_mode="operations",
            human_response=_human(
                headline="Capital Hilton follow-up can be staged",
                body="The follow-up draft can be staged for review. Nothing gets sent from this step.",
                next_step="Stage follow-up",
                missing_input=[],
                what_i_can_do_now=["stage the follow-up draft", "prepare review copy"],
                what_i_cannot_do_yet=["send email", "update external systems"],
            ),
            controls=[_control("Stage follow-up", "stage_plan"), _control("Show details", "show_details")],
            proof_meters=[
                _meter(bd_card, "truth", "trusted_current"),
                _meter(bd_card, "authority", "no_grant"),
                _meter(bd_card, "risk", "calm"),
            ],
            factual_claims=[
                _claim("The follow-up can be staged.", SOURCE_REFS["workflow_package"], SOURCE_REFS["dynamic_cards"]),
                _claim("No send is performed.", SOURCE_REFS["receipts"], SOURCE_REFS["actions"]),
            ],
            source_refs=[SOURCE_REFS["workflow_package"], SOURCE_REFS["dynamic_cards"], SOURCE_REFS["receipts"], SOURCE_REFS["actions"]],
            expected_lm_contract="Use Cassandra voice for correspondence prep while preserving the send lock.",
        ),
        _response(
            scenario_id="build_review_packet",
            source_context=_source_context(
                world_ref="build",
                thread_ref="build_openclaw_backend",
                objective_ref="objective:build:review_packet:decision",
                card_id=review_card,
                receipt_refs=["universal_receipt:review_decision_recorded:a8d1a6f2053629b9"],
                proof_refs=[SOURCE_REFS["review_decisions"], SOURCE_REFS["proof_meters"]],
                gate_refs=[],
            ),
            speaker_ref="chief",
            voice_mode="diagnostic",
            human_response=_human(
                headline="Review packet is informational",
                body="The review decision is recorded. No merge and no push were performed.",
                next_step="Review packet",
                missing_input=[],
                what_i_can_do_now=["show the packet", "record review-only decisions"],
                what_i_cannot_do_yet=["merge", "push", "spawn a worker"],
            ),
            controls=[_control("Review packet", "show_details"), _control("Request rework", "request_rework"), _control("Mark informational", "mark_informational")],
            proof_meters=[
                _meter(review_card, "truth", "trusted_current"),
                _meter(review_card, "freshness", "historical"),
                _meter(review_card, "risk", "calm"),
            ],
            factual_claims=[
                _claim("The review decision is recorded.", SOURCE_REFS["review_decisions"], SOURCE_REFS["receipts"]),
                _claim("No merge or push was performed.", SOURCE_REFS["review_decisions"], SOURCE_REFS["receipts"]),
            ],
            source_refs=[SOURCE_REFS["review_decisions"], SOURCE_REFS["receipts"], SOURCE_REFS["proof_meters"]],
            expected_lm_contract="Summarize review state only; never imply merge, push, or worker execution.",
        ),
        _response(
            scenario_id="unknown_context",
            source_context=_source_context(
                world_ref="unknown",
                thread_ref="unknown",
                objective_ref="unknown",
                card_id="unknown",
                receipt_refs=[],
                proof_refs=[SOURCE_REFS["controller_router"]],
                gate_refs=[],
            ),
            speaker_ref="openclaw",
            voice_mode="brief",
            human_response=_human(
                headline="Needs lane context",
                body="I need lane context before package staging. Which world and lane should this apply to?",
                next_step="Pick the world and thread",
                missing_input=["world_ref", "thread_ref"],
                what_i_can_do_now=["hold the request", "ask a precise context question"],
                what_i_cannot_do_yet=["stage a package", "route a business action"],
            ),
            controls=[_control("Choose lane", "open_lane"), _control("Stop", "stop_hold_cancel")],
            proof_meters=[
                _meter("unknown", "truth", "needs_verification"),
                _meter("unknown", "freshness", "needs_verification"),
                _meter("unknown", "authority", "needs_verification"),
            ],
            factual_claims=[
                _claim("Lane context is missing.", SOURCE_REFS["controller_router"]),
                _claim("Package staging is not available without context.", SOURCE_REFS["objective"], SOURCE_REFS["controller_router"]),
            ],
            source_refs=[SOURCE_REFS["controller_router"], SOURCE_REFS["objective"]],
            expected_lm_contract="Ask for the smallest missing context; do not stage packages or smooth over missing proof.",
        ),
        _response(
            scenario_id="protected_coupa_ledger_email_request",
            source_context=_source_context(
                world_ref="finance",
                thread_ref="capital_hilton",
                objective_ref="objective:finance:capital_hilton:protected_action",
                card_id=gate_card,
                receipt_refs=["universal_receipt:gate_blocked:6c271847b98e5c34"],
                proof_refs=[SOURCE_REFS["proof_meters"], SOURCE_REFS["receipts"]],
                gate_refs=[SOURCE_REFS["gates"]],
            ),
            speaker_ref="guardian",
            voice_mode="safety",
            human_response=_human(
                headline="Blocked until proof and approval",
                body="I cannot send, submit to Coupa, touch the ledger, or mark paid from this request.",
                next_step="Attach proof and prepare approval",
                missing_input=["specific approval", "supporting proof"],
                what_i_can_do_now=["prepare an approval packet", "show the blocked gate"],
                what_i_cannot_do_yet=["send email", "submit to Coupa", "change the ledger", "mark paid"],
            ),
            controls=[_control("Prepare approval", "stage_plan"), _control("Attach proof", "attach_proof"), _control("Execute", "do_it", enabled=False, disabled_reason="protected action blocked")],
            proof_meters=[
                _meter(gate_card, "authority", "blocked_gate"),
                _meter(gate_card, "risk", "protected"),
                _meter(gate_card, "evidence", "no_evidence"),
            ],
            factual_claims=[
                _claim("Protected action is blocked.", SOURCE_REFS["gates"], SOURCE_REFS["receipts"]),
                _claim("Approval and proof are required before execution.", SOURCE_REFS["gates"], SOURCE_REFS["actions"]),
                _claim("No send, Coupa submit, ledger change, or paid marking is performed.", SOURCE_REFS["receipts"], SOURCE_REFS["gates"]),
            ],
            source_refs=[SOURCE_REFS["gates"], SOURCE_REFS["receipts"], SOURCE_REFS["actions"], SOURCE_REFS["proof_meters"]],
            expected_lm_contract="Use Guardian voice; name the blocked protected action and the missing proof/approval.",
        ),
    ]


def response_grounding_refs(response: Mapping[str, Any]) -> set[str]:
    source_context = response.get("source_context")
    refs: set[str] = set()
    if isinstance(source_context, Mapping):
        for key in ("receipt_refs", "proof_refs", "gate_refs"):
            values = source_context.get(key)
            if isinstance(values, list):
                refs.update(str(value) for value in values if str(value))
    source_refs = response.get("source_refs")
    if isinstance(source_refs, list):
        refs.update(str(value) for value in source_refs if str(value))
    return refs


def response_is_concise(response: Mapping[str, Any]) -> bool:
    human = response.get("human_response")
    if not isinstance(human, Mapping):
        return False
    headline = str(human.get("headline") or "")
    body = str(human.get("body") or "")
    next_step = str(human.get("next_step") or "")
    paragraphs = [part for part in body.split("\n\n") if part.strip()]
    return (
        bool(headline)
        and "\n" not in headline
        and len(headline) <= 90
        and len(paragraphs) <= 2
        and all(len(part) <= 220 for part in paragraphs)
        and bool(next_step)
        and len(next_step) <= 120
    )


def _primary_response_text(response: Mapping[str, Any]) -> str:
    human = response.get("human_response")
    if not isinstance(human, Mapping):
        return ""
    parts = [
        str(human.get("headline") or ""),
        str(human.get("body") or ""),
        str(human.get("next_step") or ""),
        " ".join(str(item) for item in human.get("missing_input") or []),
        " ".join(str(item) for item in human.get("what_i_can_do_now") or []),
        " ".join(str(item) for item in human.get("what_i_cannot_do_yet") or []),
    ]
    return " ".join(parts).lower()


def machine_jargon_in_primary_response(response: Mapping[str, Any]) -> list[str]:
    text = _primary_response_text(response)
    return sorted(term for term in MACHINE_CONTRACT_JARGON if term in text)


def unproven_completion_claims(response: Mapping[str, Any]) -> list[str]:
    text = _primary_response_text(response)
    unsafe_phrases = (
        "is paid",
        "has been paid",
        "marked paid",
        "sent it",
        "was sent",
        "has been sent",
        "submitted it",
        "has been submitted",
        "ledger updated",
        "ledger changed",
    )
    allowed_negative_contexts = (
        "does not mark paid",
        "not paid",
        "cannot send",
        "no send",
        "nothing gets sent",
        "cannot submit",
        "ledger stays untouched",
        "ledger remains untouched",
        "ledger was not changed",
        "no merge",
        "no push",
    )
    failures: list[str] = []
    for phrase in unsafe_phrases:
        if phrase in text and not any(negative in text for negative in allowed_negative_contexts):
            failures.append(phrase)
    return failures


def validate_authority_boundary(response: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    boundary = response.get("authority_boundary")
    if not isinstance(boundary, Mapping):
        return ["authority_boundary_missing"]
    if boundary.get("protected_actions_allowed") is not False:
        errors.append("protected_actions_allowed_not_false")
    for key, value in boundary.items():
        if key.endswith("_allowed") and value is not False:
            errors.append(f"authority_boundary_not_false:{key}")
    return errors


def validate_response(response: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_RESPONSE_FIELDS:
        if field not in response:
            errors.append(f"missing_field:{field}")
    source_context = response.get("source_context")
    if not isinstance(source_context, Mapping):
        errors.append("source_context_not_object")
    else:
        for field in REQUIRED_SOURCE_CONTEXT_FIELDS:
            if field not in source_context:
                errors.append(f"source_context_missing:{field}")
        for field in ("receipt_refs", "proof_refs", "gate_refs"):
            if not isinstance(source_context.get(field), list):
                errors.append(f"source_context_not_list:{field}")
    human = response.get("human_response")
    if not isinstance(human, Mapping):
        errors.append("human_response_not_object")
    else:
        for field in REQUIRED_HUMAN_RESPONSE_FIELDS:
            if field not in human:
                errors.append(f"human_response_missing:{field}")
        for field in ("missing_input", "what_i_can_do_now", "what_i_cannot_do_yet"):
            if not isinstance(human.get(field), list):
                errors.append(f"human_response_not_list:{field}")
    if str(response.get("speaker_ref") or "") not in SPEAKER_REFS:
        errors.append(f"unknown_speaker_ref:{response.get('speaker_ref')}")
    if str(response.get("voice_mode") or "") not in VOICE_MODES:
        errors.append(f"unknown_voice_mode:{response.get('voice_mode')}")
    if not isinstance(response.get("controls"), list):
        errors.append("controls_not_list")
    if not isinstance(response.get("proof_meters"), list):
        errors.append("proof_meters_not_list")
    if response.get("details_collapsed") is not True:
        errors.append("details_not_collapsed")
    if not response_is_concise(response):
        errors.append("response_not_concise")
    errors.extend(f"machine_jargon:{term}" for term in machine_jargon_in_primary_response(response))
    errors.extend(f"unproven_completion_claim:{term}" for term in unproven_completion_claims(response))
    errors.extend(validate_authority_boundary(response))
    grounding_refs = response_grounding_refs(response)
    claims = response.get("factual_claims")
    if not isinstance(claims, list) or not claims:
        errors.append("factual_claims_missing")
    else:
        for idx, claim in enumerate(claims):
            if not isinstance(claim, Mapping):
                errors.append(f"factual_claim_not_object:{idx}")
                continue
            source_refs = claim.get("source_refs")
            if not isinstance(source_refs, list) or not source_refs:
                errors.append(f"factual_claim_missing_source_refs:{idx}")
            elif not set(str(ref) for ref in source_refs).issubset(grounding_refs):
                errors.append(f"factual_claim_source_ref_not_grounded:{idx}")
    return errors


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    root = _rooted(read_model_root)
    source_payloads = {
        name: _load_json(root / ref.split("generated/read_models/", 1)[1])
        for name, ref in SOURCE_REFS.items()
        if ref.startswith("generated/read_models/")
    }
    responses = example_responses()
    validation_errors: list[str] = []
    for response in responses:
        validation_errors.extend(f"{response.get('scenario_id')}:{error}" for error in validate_response(response))
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready and not validation_errors else NOT_READY_STATUS,
        "generated_at": generated_at,
        "mode": "tdd_spec_first_no_live_lm",
        "response_schema": {
            "required_fields": list(REQUIRED_RESPONSE_FIELDS),
            "source_context_fields": list(REQUIRED_SOURCE_CONTEXT_FIELDS),
            "human_response_fields": list(REQUIRED_HUMAN_RESPONSE_FIELDS),
            "speaker_refs": list(SPEAKER_REFS),
            "voice_modes": list(VOICE_MODES),
            "authority_boundary": {"protected_actions_allowed": False},
            "details_collapsed_default": True,
        },
        "doctrine": list(DOCTRINE),
        "rules": {
            "cards_are_not_main_response": True,
            "main_response_is_concise_human_text": True,
            "response_grounded_in_machine_proof": True,
            "lm_may_phrase_and_prioritize": True,
            "lm_may_not_create_truth_or_authority": True,
            "generated_summary_cannot_override_receipt": True,
            "missing_proof_must_be_named": True,
            "protected_action_block_must_name_needed_proof_or_approval": True,
            "details_collapsed_by_default": True,
        },
        "grounding_order": list(GROUNDING_ORDER),
        "source_refs": dict(SOURCE_REFS),
        "source_content_hashes": {name: _content_hash(payload) for name, payload in source_payloads.items()},
        "preconditions": preconditions,
        "example_responses": responses,
        "response_count": len(responses),
        "test_scenarios": [
            "finance_capital_hilton_payment_watch",
            "finance_live_arts_payment_evidence",
            "business_development_capital_hilton_followup",
            "build_review_packet",
            "unknown_context",
            "protected_coupa_ledger_email_request",
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": {
            "live_lm_invoked": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
            "email_send_performed": False,
            "coupa_submit_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "business_action_performed": False,
        },
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "response_validation_errors": validation_errors,
            "response_count_matches_required_scenarios": len(responses) == 6,
            "all_responses_concise": all(response_is_concise(response) for response in responses),
            "all_factual_claims_have_refs": all(
                all(claim.get("source_refs") for claim in response.get("factual_claims", []))
                for response in responses
            ),
            "unproven_paid_sent_submitted_claims": [
                {"scenario_id": response["scenario_id"], "claims": unproven_completion_claims(response)}
                for response in responses
                if unproven_completion_claims(response)
            ],
            "machine_contract_jargon_in_primary_response": [
                {"scenario_id": response["scenario_id"], "terms": machine_jargon_in_primary_response(response)}
                for response in responses
                if machine_jargon_in_primary_response(response)
            ],
            "authority_boundary_false": True,
            "details_collapsed": all(response.get("details_collapsed") is True for response in responses),
            "cards_are_main_response": False,
            "details_expanded_by_default": False,
            "incoming_authority_granted_accepted": False,
            "business_action_performed": False,
            "paid_marking_performed": False,
            "ledger_mutation_performed": False,
            "email_send_performed": False,
            "coupa_submit_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "worker_spawn_performed": False,
            "external_llm_invoked": False,
            "local_model_runtime_connected": False,
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Proof To Response TDD Spec",
        "",
        f"Status: {read_model.get('status')}",
        "",
        "Proof-to-Response TDD Spec V0 defines how deterministic proof becomes concise agent text. It is a contract for a future phrasing layer, not a live LM implementation.",
        "",
        "## Doctrine",
        "",
    ]
    for rule in read_model.get("doctrine") or []:
        lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "## Response Shape",
            "",
            "- `response_id`",
            "- `source_context` with world, thread, objective, card, receipt, proof, and gate refs",
            "- `speaker_ref`: `cassandra`, `chief`, `hermes`, `guardian`, `niles`, or `openclaw`",
            "- `voice_mode`: `brief`, `diagnostic`, `safety`, `creative`, or `operations`",
            "- `human_response` with headline, body, next step, missing input, can-do, and cannot-do lists",
            "- `controls`, `proof_meters`, `authority_boundary`, and `details_collapsed=true`",
            "",
            "## Scenario Contracts",
            "",
        ]
    )
    for response in read_model.get("example_responses") or []:
        human = response.get("human_response") if isinstance(response.get("human_response"), Mapping) else {}
        lines.append(
            f"- `{response.get('scenario_id')}`: `{response.get('speaker_ref')}` / `{response.get('voice_mode')}` - {human.get('headline')} -> {human.get('next_step')}"
        )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- No live LM call.",
            "- No local model runtime.",
            "- No worker spawn.",
            "- No email send, Coupa submit, ledger/workbook mutation, PDF export, or paid marking.",
            "- No primary-response machine-contract jargon.",
            "- Every factual claim has source refs.",
            "- Details remain collapsed.",
            "",
            "## Proof",
            "",
            f"- Response count: `{read_model.get('response_count')}`",
            f"- Preconditions ready: `{str((read_model.get('machine_proof') or {}).get('preconditions_ready')).lower()}`",
            f"- Validation errors: `{len((read_model.get('machine_proof') or {}).get('response_validation_errors') or [])}`",
            f"- Unsafe true grants absent: `{str((read_model.get('machine_proof') or {}).get('unsafe_true_grants_absent')).lower()}`",
            "",
        ]
    )
    return "\n".join(lines)


def export_proof_to_response_tdd_spec(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    export_path = export_root / JSON_EXPORT_NAME
    _write_json(export_path, read_model)

    bridge_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge = bridge_export_root / JSON_EXPORT_NAME
        shutil.copy2(export_path, bridge)
        bridge_path = bridge.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model["status"]),
        "read_model_path": export_path.as_posix(),
        "bridge_read_model_path": bridge_path,
        "wiki_path": wiki_path.as_posix(),
        "response_count": str(read_model["response_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Proof-to-Response TDD Spec V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_proof_to_response_tdd_spec(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result), end="")
    else:
        print(f"{result['status']}: {result['read_model_path']}")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
