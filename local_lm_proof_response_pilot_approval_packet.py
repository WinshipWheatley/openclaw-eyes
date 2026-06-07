"""Local LM proof-to-response pilot approval packet V0.

Approval-packet/read-model only. This module prepares the operator review
packet for a future single local/approved proof-to-response pilot. It does not
invoke models, connect runtimes, spawn workers, send email, access external
providers, mutate ledgers/workbooks, export PDFs, mark paid, submit, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import local_lm_harness_inventory_receipts as harness_inventory
import local_lm_proof_to_response_pilot_plan as pilot_plan
import proof_bundle_redaction_policy as redaction_policy
import proof_to_response_runtime


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Local LM Proof Response Pilot Approval Packet.md")

SCHEMA_VERSION = "local_lm_proof_response_pilot_approval_packet_v0"
READ_MODEL_ID = "local_lm_proof_response_pilot_approval_packet"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "LOCAL_LM_PROOF_RESPONSE_PILOT_APPROVAL_PACKET_READY"
NOT_READY_STATUS = "LOCAL_LM_PROOF_RESPONSE_PILOT_APPROVAL_PACKET_NOT_READY"

APPROVAL_PACKET_STATUS = "pending_operator_review"
APPROVAL_PACKET_ID = "approval_packet:local_lm_proof_response:finance_capital_hilton:v0"
PILOT_REF = "local_lm_proof_to_response_pilot_plan:finance_capital_hilton_payment_watch:v0"
SELECTED_LANE = "finance/capital_hilton"
PILOT_QUESTION = "What should I do here?"
INTENDED_RESPONSE_TYPE = "proof_to_response"
DEFAULT_CANDIDATE_HARNESS_REF = "local_llm_shadow_mode"
DEFAULT_CANDIDATE_SOURCE_MODE = "local_lm_shadow_mode_once_pending_operator_approval"

OPERATOR_DECISION_OPTION_REFS = (
    "approve_local_lm_shadow_pilot_once",
    "request_more_detail",
    "reject_for_now",
)

REQUIRED_RECEIPTS = (
    "operator_approval_receipt",
    "model_harness_selected_receipt",
    "no_external_provider_receipt",
    "redacted_proof_bundle_receipt",
    "no_tool_authority_receipt",
    "verifier_pass_fail_receipt",
    "published_response_hash_receipt",
)

FORBIDDEN_LM_INPUTS = tuple(
    dict.fromkeys(
        (
            "raw_financial_details",
            "raw_finance_details",
            "raw_bank_details",
            "raw_bank_account_details",
            "bank_account_numbers",
            "routing_numbers",
            "credentials_tokens",
            "credentials_or_tokens",
            "operator_device_session_verification_secrets",
            "device_verification_material",
            "session_verification_material",
            "raw_request_paths_unredacted",
            "raw_prompt_dumps",
            "raw_prompt_bodies",
            "raw_artifact_ocr_text",
            "full_artifact_text_or_ocr",
            "full_workbook_contents",
            "source_workbook_bodies",
            "workbook_email_ledger_bodies",
            "raw_email_bodies_unapproved",
            "raw_ledger_rows_unapproved",
            "hidden_machine_contracts",
            "authority_granted_fields",
            "authority_grant_fields_from_user_or_model_input",
            *redaction_policy.FORBIDDEN_MATERIAL_CLASSES,
            *pilot_plan.FORBIDDEN_LM_INPUT,
        )
    )
)

FORBIDDEN_ACTIONS = (
    "external_llm_call",
    "tool_use",
    "worker_spawn",
    "business_action",
    "email_send",
    "gmail_access",
    "browser_access",
    "coupa_access",
    "portal_submit",
    "ledger_mutation",
    "ledger_posting",
    "paid_marking",
    "workbook_mutation",
    "workbook_body_read",
    "pdf_export",
    "memory_promotion_to_truth",
    "authority_grant",
    "git_push",
    "merge",
)

STOP_CONDITIONS = tuple(
    dict.fromkeys(
        (
            *pilot_plan.STOP_CONDITIONS,
            "model_claims_paid_sent_submitted",
            "model_proposes_protected_action",
            "model_requests_tool_or_external_access",
            "model_requests_hidden_context",
            "proof_bundle_contains_secret_or_raw_financial_detail",
            "verifier_fails",
            "external_provider_path_appears",
        )
    )
)

AUTHORITY_BOUNDARY = {
    "approval_packet_is_approval": False,
    "live_lm_invocation_allowed": False,
    "external_llm_allowed": False,
    "external_provider_connect_allowed": False,
    "local_model_runtime_allowed": False,
    "model_invocation_allowed": False,
    "tool_authority_allowed": False,
    "tool_execution_allowed": False,
    "worker_spawn_allowed": False,
    "business_action_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "ledger_posting_allowed": False,
    "paid_marking_allowed": False,
    "workbook_mutation_allowed": False,
    "workbook_body_read_allowed": False,
    "pdf_export_allowed": False,
    "memory_promotion_allowed": False,
    "authority_grant_allowed": False,
    "protected_actions_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
}

IMPLEMENTATION_BOUNDARY = {
    "model_invoked": False,
    "live_lm_invoked": False,
    "external_llm_invoked": False,
    "external_provider_connected": False,
    "local_model_runtime_connected": False,
    "tool_execution_performed": False,
    "worker_spawn_performed": False,
    "business_action_performed": False,
    "email_send_performed": False,
    "gmail_access_performed": False,
    "browser_access_performed": False,
    "coupa_access_performed": False,
    "portal_submit_performed": False,
    "ledger_mutation_performed": False,
    "ledger_posting_performed": False,
    "paid_marking_performed": False,
    "workbook_mutation_performed": False,
    "workbook_body_read_performed": False,
    "pdf_export_performed": False,
    "memory_promotion_performed": False,
    "authority_grant_performed": False,
    "git_push_performed": False,
    "merge_performed": False,
}

UNSAFE_TRUE_KEYS = (
    set(AUTHORITY_BOUNDARY)
    | set(IMPLEMENTATION_BOUNDARY)
    | set(harness_inventory.UNSAFE_TRUE_KEYS)
    | set(pilot_plan.UNSAFE_TRUE_KEYS)
    | set(proof_to_response_runtime.UNSAFE_TRUE_KEYS)
    | {
        "approval_granted",
        "operator_approved",
        "approved",
        "approved_for_live_invocation",
        "live_invocation_ready",
        "ready_for_live_invocation",
        "model_call_allowed",
        "tool_authority_granted",
        "authority_granted",
        "paid",
        "sent",
        "submitted",
        "executed",
    }
)

PRECONDITIONS = {
    "local_lm_proof_response_pilot_plan": {
        "filename": "local_lm_proof_to_response_pilot_plan.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_PILOT_PLAN_READY",),
    },
    "local_lm_harness_inventory_receipts": {
        "filename": "local_lm_harness_inventory_receipts.json",
        "accepted_statuses": ("LOCAL_LM_HARNESS_INVENTORY_RECEIPTS_READY",),
    },
    "proof_bundle_redaction_hardening": {
        "filename": "proof_bundle_redaction_policy.json",
        "accepted_statuses": ("PROOF_BUNDLE_REDACTION_HARDENING_READY",),
    },
    "proof_bundle_builder_redaction_integration": {
        "filename": "proof_bundle_builder_redaction_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY",),
    },
    "agent_response_voice_modes": {
        "filename": "agent_response_voice_modes.json",
        "accepted_statuses": ("AGENT_RESPONSE_VOICE_MODES_READY",),
    },
    "proof_to_response_runtime": {
        "filename": proof_to_response_runtime.STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (proof_to_response_runtime.READY_STATUS,),
    },
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


def _status(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status") or payload.get("readiness_status") or payload.get("contract_status") or "")


def _standard_precondition_rows(read_model_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ref, spec in PRECONDITIONS.items():
        filename = str(spec["filename"])
        payload = _load_json(read_model_root / filename)
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


def _shadow_runtime_row(read_model_root: Path) -> dict[str, Any]:
    runtime_status = _load_json(read_model_root / proof_to_response_runtime.STATUS_JSON_EXPORT_NAME)
    latest = _load_json(read_model_root / proof_to_response_runtime.LATEST_JSON_EXPORT_NAME)
    active_source = str(runtime_status.get("active_candidate_source") or latest.get("candidate_source") or "")
    ready = (
        runtime_status.get("status") == proof_to_response_runtime.READY_STATUS
        and active_source == proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT
    )
    return {
        "precondition_ref": "proof_to_response_shadow_pilot_runtime",
        "source_ref": "generated/read_models/proof_to_response_runtime_status.json",
        "observed_status": "PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_READY" if ready else "PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_NOT_READY",
        "accepted_statuses": ["PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_READY"],
        "ready": ready,
        "active_candidate_source": active_source,
    }


def _scoped_responses_row(read_model_root: Path) -> dict[str, Any]:
    latest = _load_json(read_model_root / proof_to_response_runtime.LATEST_JSON_EXPORT_NAME)
    response = latest.get("latest_response") if isinstance(latest.get("latest_response"), Mapping) else {}
    ready = (
        latest.get("status") == proof_to_response_runtime.READY_STATUS
        and latest.get("stale_if_context_mismatch") is True
        and bool(latest.get("source_request_id") or response.get("source_request_id"))
        and bool(latest.get("world_ref") or response.get("world_ref"))
        and bool(latest.get("thread_ref") or response.get("thread_ref"))
    )
    return {
        "precondition_ref": "proof_to_response_scoped_responses",
        "source_ref": "generated/read_models/proof_to_response_latest.json",
        "observed_status": "PROOF_TO_RESPONSE_SCOPED_RESPONSES_READY" if ready else "PROOF_TO_RESPONSE_SCOPED_RESPONSES_NOT_READY",
        "accepted_statuses": ["PROOF_TO_RESPONSE_SCOPED_RESPONSES_READY"],
        "ready": ready,
    }


def _finance_payment_watch_proof_response_row(read_model_root: Path) -> dict[str, Any]:
    bundle: dict[str, Any] = {}
    candidate: dict[str, Any] = {}
    verification: dict[str, Any] = {}
    try:
        bundle = proof_to_response_runtime.build_or_load_proof_bundle(
            "finance_capital_hilton_payment_watch",
            read_model_root=read_model_root,
        )
        candidate = proof_to_response_runtime.candidate_response_for_source(
            bundle,
            candidate_source=proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT,
        )
        verification = proof_to_response_runtime.verify_candidate_response(
            candidate,
            bundle,
            read_model_root=read_model_root,
        )
    except (OSError, ValueError, TypeError, KeyError):
        verification = {}
    text = " ".join(str(candidate.get(key) or "") for key in ("draft_headline", "draft_body", "draft_next_step")).lower()
    world = str(bundle.get("world_ref") or "")
    thread = str(bundle.get("thread_ref") or "")
    ready = (
        world == "finance"
        and thread == "capital_hilton"
        and "payment evidence" in text
        and "ledger stays untouched" in text
        and "attach payment evidence" in text
        and verification.get("publishable") is True
        and not verification.get("verification_errors")
    )
    return {
        "precondition_ref": "finance_payment_watch_proof_response",
        "source_ref": "proof_to_response_runtime.py#finance_capital_hilton_payment_watch",
        "observed_status": "FINANCE_PAYMENT_WATCH_PROOF_RESPONSE_READY" if ready else "FINANCE_PAYMENT_WATCH_PROOF_RESPONSE_NOT_READY",
        "accepted_statuses": ["FINANCE_PAYMENT_WATCH_PROOF_RESPONSE_READY"],
        "ready": ready,
        "verification_status": str(verification.get("status") or ""),
        "candidate_source": proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT,
    }


def _finance_payment_watch_controller_map_row(read_model_root: Path) -> dict[str, Any]:
    packet = _load_json(read_model_root / "dynamic_card_packet_latest.json")
    cards = packet.get("cards") if isinstance(packet.get("cards"), list) else []
    card = next(
        (
            item
            for item in cards
            if isinstance(item, Mapping)
            and item.get("card_id") == "dynamic_card.finance.capital_hilton.payment_watch"
        ),
        {},
    )
    action_slots = card.get("action_slots") if isinstance(card.get("action_slots"), Mapping) else {}
    events = {
        str(slot.get("controller_event_type") or ""): dict(slot)
        for slot in action_slots.values()
        if isinstance(slot, Mapping) and slot.get("enabled") is True
    }
    ready = all(
        event in events
        and events[event].get("control_scope") == "lane"
        and events[event].get("text_response_preferred") is True
        for event in ("ask_why", "advance_objective", "attach_proof")
    )
    return {
        "precondition_ref": "finance_payment_watch_controller_map",
        "source_ref": "generated/read_models/dynamic_card_packet_latest.json",
        "observed_status": "FINANCE_PAYMENT_WATCH_CONTROLLER_MAP_READY" if ready else "FINANCE_PAYMENT_WATCH_CONTROLLER_MAP_NOT_READY",
        "accepted_statuses": ["FINANCE_PAYMENT_WATCH_CONTROLLER_MAP_READY"],
        "ready": ready,
    }


def precondition_rows(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    return [
        *_standard_precondition_rows(root),
        _shadow_runtime_row(root),
        _scoped_responses_row(root),
        _finance_payment_watch_proof_response_row(root),
        _finance_payment_watch_controller_map_row(root),
    ]


def allowed_lm_inputs() -> list[dict[str, str]]:
    return [
        {"field_ref": field, "reason": reason}
        for field, reason in redaction_policy.ALLOWED_FIELD_REASONS.items()
    ]


def proof_bundle_summary() -> dict[str, Any]:
    return {
        "proof_bundle_ref": "redacted_proof_bundle:finance_capital_hilton_payment_watch",
        "scenario_id": "finance_capital_hilton_payment_watch",
        "world_ref": "finance",
        "thread_ref": "capital_hilton",
        "objective_ref": "objective:finance:capital_hilton:payment_watch",
        "privacy_class": "financial_sensitive/local_only_redacted",
        "human_safe_summary": "Payment evidence is missing; Coupa is processing; ledger and paid state remain untouched.",
        "missing_input": ["payment evidence"],
        "raw_sensitive_detail_included": False,
        "operator_device_session_secret_material_included": False,
        "source_refs": [
            "generated/read_models/proof_bundle_redaction_policy.json",
            "generated/read_models/proof_bundle_builder_redaction_status.json",
            "generated/read_models/proof_to_response_latest.json",
        ],
    }


def expected_response() -> dict[str, Any]:
    return {
        "speaker_ref": "chief",
        "voice_mode": "operations",
        "headline": "Payment evidence needed",
        "body": "Coupa is processing. I can't mark this paid until payment evidence is attached. The ledger stays untouched.",
        "next_step": "Attach payment evidence.",
        "must_not_claim": ["paid", "sent", "submitted", "ledger updated", "Coupa submitted"],
    }


def allowed_controls() -> list[dict[str, Any]]:
    return [
        {
            "controller_event_type": "ask_why",
            "action_payload_ref": "generated/read_models/operator_action_payloads.json#action_payloads.capital_hilton.payment.ask_why",
            "label": "Ask why",
            "control_scope": "lane",
            "text_response_preferred": True,
            "authority_boundary": {"protected_actions_allowed": False},
        },
        {
            "controller_event_type": "advance_objective",
            "action_payload_ref": "generated/read_models/operator_action_payloads.json#action_payloads.capital_hilton.payment.advance_objective",
            "label": "Advance payment watch",
            "control_scope": "lane",
            "text_response_preferred": True,
            "authority_boundary": {"protected_actions_allowed": False},
        },
        {
            "controller_event_type": "attach_proof",
            "action_payload_ref": "generated/read_models/operator_action_payloads.json#action_payloads.capital_hilton.payment.record_proof",
            "label": "Attach payment evidence",
            "control_scope": "lane",
            "text_response_preferred": True,
            "authority_boundary": {"protected_actions_allowed": False},
        },
    ]


def rollback_or_abort_plan() -> list[dict[str, str]]:
    return [
        {
            "step_ref": "do_not_invoke_model_without_operator_decision",
            "description": "If approval is absent or ambiguous, keep shadow-pilot fixture responses as the only candidate source.",
        },
        {
            "step_ref": "publish_safe_fallback_on_verifier_failure",
            "description": "If any model draft fails the verifier, publish the deterministic safe fallback and record the rejection reason.",
        },
        {
            "step_ref": "abort_on_boundary_violation",
            "description": "Abort immediately if forbidden input, external-provider path, tool request, protected-action proposal, or unsafe claim appears.",
        },
        {
            "step_ref": "restore_shadow_candidate_source",
            "description": "Return proof-to-response runtime to shadow_pilot_candidate/deterministic fixture source after the one approved pilot attempt.",
        },
    ]


def operator_decision_options() -> list[dict[str, Any]]:
    return [
        {
            "option_ref": "approve_local_lm_shadow_pilot_once",
            "label": "Approve one local shadow pilot",
            "review_only": True,
            "approval_record_required": True,
            "grants_live_invocation_now": False,
            "effect": "Records that the operator may approve one future local shadow-mode proof-to-response pilot after receipt checks.",
        },
        {
            "option_ref": "request_more_detail",
            "label": "Request more detail",
            "review_only": True,
            "approval_record_required": False,
            "grants_live_invocation_now": False,
            "effect": "Ask for more proof, harness, redaction, or verifier detail before any pilot approval.",
        },
        {
            "option_ref": "reject_for_now",
            "label": "Reject for now",
            "review_only": True,
            "approval_record_required": False,
            "grants_live_invocation_now": False,
            "effect": "Keep all live/local LM invocation blocked.",
        },
    ]


def build_approval_packet(generated_at: str) -> dict[str, Any]:
    return {
        "approval_packet_id": APPROVAL_PACKET_ID,
        "status": APPROVAL_PACKET_STATUS,
        "created_at": generated_at,
        "pilot_ref": PILOT_REF,
        "selected_lane": SELECTED_LANE,
        "pilot_question": PILOT_QUESTION,
        "intended_response_type": INTENDED_RESPONSE_TYPE,
        "candidate_harness_ref": DEFAULT_CANDIDATE_HARNESS_REF,
        "candidate_model_ref": "",
        "candidate_source_mode": DEFAULT_CANDIDATE_SOURCE_MODE,
        "proof_bundle_summary": proof_bundle_summary(),
        "allowed_lm_inputs": allowed_lm_inputs(),
        "forbidden_lm_inputs": list(FORBIDDEN_LM_INPUTS),
        "redaction_policy_ref": "generated/read_models/proof_bundle_redaction_policy.json",
        "verifier_ref": "proof_to_response_verifier.py#proof_to_response_verifier_v0",
        "expected_response": expected_response(),
        "allowed_controls": allowed_controls(),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "stop_conditions": list(STOP_CONDITIONS),
        "receipts_required": list(REQUIRED_RECEIPTS),
        "rollback_or_abort_plan": rollback_or_abort_plan(),
        "operator_decision_options": operator_decision_options(),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
        "safety_requirements": {
            "no_external_llm": True,
            "no_tool_use": True,
            "no_worker_spawn": True,
            "no_business_action": True,
            "no_ledger_or_workbook_mutation": True,
            "no_paid_marking": True,
            "no_browser_gmail_coupa": True,
            "no_secrets_or_raw_bank_details_or_device_verification_material": True,
            "verifier_must_gate_publish": True,
            "failed_verifier_returns_safe_fallback": True,
        },
    }


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    packet = build_approval_packet(generated_at)
    all_preconditions_ready = all(row["ready"] for row in preconditions)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if all_preconditions_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Operator approval packet for the first local/approved LM proof-to-response pilot.",
        "approval_packet": packet,
        "preconditions": preconditions,
        "source_refs": [
            "generated/read_models/local_lm_proof_to_response_pilot_plan.json",
            "generated/read_models/local_lm_harness_inventory_receipts.json",
            "generated/read_models/proof_bundle_redaction_policy.json",
            "generated/read_models/proof_bundle_builder_redaction_status.json",
            "generated/read_models/agent_response_voice_modes.json",
            "generated/read_models/proof_to_response_runtime_status.json",
            "generated/read_models/proof_to_response_latest.json",
            "generated/read_models/dynamic_card_packet_latest.json",
            "generated/read_models/operator_action_payloads.json",
        ],
        "source_content_hashes": {
            "preconditions": _content_hash(preconditions),
            "approval_packet": _content_hash(packet),
            "allowed_lm_inputs": _content_hash(packet["allowed_lm_inputs"]),
            "forbidden_lm_inputs": _content_hash(packet["forbidden_lm_inputs"]),
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
        "machine_proof": {
            "preconditions_ready": all_preconditions_ready,
            "approval_packet_created": True,
            "approval_packet_status": APPROVAL_PACKET_STATUS,
            "operator_approval_recorded": False,
            "packet_is_pending_review_not_approved": packet["status"] == APPROVAL_PACKET_STATUS,
            "selected_lane_is_finance_capital_hilton": packet["selected_lane"] == SELECTED_LANE,
            "allowed_fields_match_redaction_policy": [row["field_ref"] for row in packet["allowed_lm_inputs"]]
            == list(redaction_policy.ALLOWED_FIELD_REASONS),
            "external_llm_blocked": "external_llm_call" in packet["forbidden_actions"],
            "tool_authority_granted": False,
            "verifier_mandatory": bool(packet["verifier_ref"]),
            "operator_decision_options_review_only": all(row["review_only"] is True for row in packet["operator_decision_options"]),
            "unsafe_true_grants": [],
            "unsafe_true_grants_absent": True,
            **IMPLEMENTATION_BOUNDARY,
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    packet = read_model.get("approval_packet") if isinstance(read_model.get("approval_packet"), Mapping) else {}
    expected = packet.get("expected_response") if isinstance(packet.get("expected_response"), Mapping) else {}
    lines = [
        "# Local LM Proof Response Pilot Approval Packet",
        "",
        f"Status: `{read_model.get('status', NOT_READY_STATUS)}`",
        f"Approval packet status: `{packet.get('status', APPROVAL_PACKET_STATUS)}`",
        f"Selected lane: `{packet.get('selected_lane', SELECTED_LANE)}`",
        f"Pilot question: {packet.get('pilot_question', PILOT_QUESTION)}",
        "",
        "This is an approval packet only. It does not approve, invoke, connect, send, submit, mutate, export, mark paid, spawn workers, or push.",
        "",
        "## Expected Response",
        "",
        f"- Headline: {expected.get('headline')}",
        f"- Body: {expected.get('body')}",
        f"- Next step: {expected.get('next_step')}",
        "",
        "## Allowed Inputs",
        "",
    ]
    for row in packet.get("allowed_lm_inputs") or []:
        if isinstance(row, Mapping):
            lines.append(f"- `{row.get('field_ref')}` - {row.get('reason')}")
    lines.extend(["", "## Forbidden Actions", ""])
    for action in packet.get("forbidden_actions") or []:
        lines.append(f"- `{action}`")
    lines.extend(["", "## Stop Conditions", ""])
    for condition in packet.get("stop_conditions") or []:
        lines.append(f"- `{condition}`")
    lines.extend(["", "## Operator Decision Options", ""])
    for row in packet.get("operator_decision_options") or []:
        if isinstance(row, Mapping):
            lines.append(f"- `{row.get('option_ref')}`: {row.get('effect')}")
    proof = read_model.get("machine_proof") if isinstance(read_model.get("machine_proof"), Mapping) else {}
    lines.extend(
        [
            "",
            "## Machine Proof",
            "",
            f"- Pending review, not approved: `{str(proof.get('packet_is_pending_review_not_approved')).lower()}`",
            f"- Verifier mandatory: `{str(proof.get('verifier_mandatory')).lower()}`",
            f"- Unsafe true grants absent: `{str(proof.get('unsafe_true_grants_absent')).lower()}`",
            "",
        ]
    )
    return "\n".join(lines)


def export_local_lm_proof_response_pilot_approval_packet(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    _write_json(read_model_path, read_model)

    bridge_read_model_path = ""
    if bridge_root is not None:
        bridge_root = _rooted(bridge_root)
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_path = bridge_root / JSON_EXPORT_NAME
        shutil.copy2(read_model_path, bridge_path)
        bridge_read_model_path = bridge_path.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model.get("status") or NOT_READY_STATUS),
        "approval_packet_status": str(read_model.get("approval_packet", {}).get("status") or ""),
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_read_model_path,
        "wiki_path": wiki_path.as_posix(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Local LM Proof Response Pilot Approval Packet V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    bridge_root = Path(args.bridge_root) if args.bridge_root else None
    result = export_local_lm_proof_response_pilot_approval_packet(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=bridge_root,
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
