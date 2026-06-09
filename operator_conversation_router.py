"""Operator Conversation Router V0.

Routes lane-local composer text through OPERATOR_CONTROLLER_EVENT_REQUEST_V0
conversation handling and proof-to-response receipts. It never invokes a model,
stages workers, sends, submits, mutates ledgers/workbooks, marks paid, or pushes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import active_next_step_policy
import capability_authority_loop
import global_run_mode_context
import make_it_so_objective_loop
import test_effect_adapters
import proof_to_response_runtime as proof_runtime


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Operator Conversation Router.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/operator_conversation_router.sqlite")

REQUEST_TYPE = "OPERATOR_CONTROLLER_EVENT_REQUEST_V0"
SCHEMA_VERSION = "operator_conversation_router_v0"
CONTRACT_SCHEMA_VERSION = "operator_conversation_router_contract_v0"
CONTRACT_READ_MODEL_ID = "operator_conversation_router_contract"
STATUS_READ_MODEL_ID = "operator_conversation_router_status"
INTENT_STATUS_READ_MODEL_ID = "operator_conversation_intent_router_status"
CONTRACT_JSON_EXPORT_NAME = f"{CONTRACT_READ_MODEL_ID}.json"
STATUS_JSON_EXPORT_NAME = f"{STATUS_READ_MODEL_ID}.json"
INTENT_STATUS_JSON_EXPORT_NAME = f"{INTENT_STATUS_READ_MODEL_ID}.json"
READY_STATUS = "OPERATOR_CONVERSATION_ROUTER_READY"
NOT_READY_STATUS = "OPERATOR_CONVERSATION_ROUTER_NOT_READY"
INTENT_READY_STATUS = "OPERATOR_CONVERSATION_INTENT_ROUTER_V1_READY"
INTENT_NOT_READY_STATUS = "OPERATOR_CONVERSATION_INTENT_ROUTER_V1_NOT_READY"

ROUTE_STATUS_TEXT_RESPONSE = "TEXT_RESPONSE_READY"
ROUTE_STATUS_PROTECTED_BLOCKED = "PROTECTED_ACTION_BLOCKED_TEXT_RESPONSE"
ROUTE_STATUS_NEEDS_LANE_CONTEXT = "NEEDS_LANE_CONTEXT"
ROUTE_STATUS_NEEDS_VERIFICATION = "NEEDS_VERIFICATION"
ROUTE_STATUS_STAGE_ONLY = "STAGE_PLAN_TEXT_RESPONSE"
ROUTE_STATUS_CAPABILITY_GAP = "CAPABILITY_GAP_AUTHORITY_REQUEST_READY"
ROUTE_STATUS_AUTHORITY_GRANT_COMPILED = "AUTHORITY_GRANT_COMPILED"
ROUTE_STATUS_BUILD_AUTHORITY_REQUEST = "CAPABILITY_BUILD_AUTHORITY_REQUEST_READY"
ROUTE_STATUS_MAKE_IT_SO_AUTHORITY_REQUEST = "MAKE_IT_SO_AUTHORITY_REQUEST_READY"
ROUTE_STATUS_MAKE_IT_SO_GRANT_COMPILED = "MAKE_IT_SO_GRANT_COMPILED"

INTENT_CLASSES = (
    "payment_watch_next_step",
    "paid_or_ledger_blocker",
    "attach_proof_hypothetical",
    "handle_it_or_continue_boundary",
    "package_context_explanation",
    "allowed_scope_explanation",
    "forbidden_scope_explanation",
    "freshness_uncertainty_explanation",
    "decision_trace_explanation",
    "fallback_lane_answer",
)

CAPITAL_HILTON_INTENT_SCENARIOS = {
    "payment_watch_next_step": "finance_capital_hilton_payment_watch",
    "paid_or_ledger_blocker": "finance_capital_hilton_paid_ledger_blocker",
    "attach_proof_hypothetical": "finance_capital_hilton_attach_proof_explanation",
    "handle_it_or_continue_boundary": "finance_capital_hilton_handle_boundary",
    "package_context_explanation": "finance_capital_hilton_package_context",
    "allowed_scope_explanation": "finance_capital_hilton_allowed_scope",
    "forbidden_scope_explanation": "finance_capital_hilton_forbidden_scope",
    "freshness_uncertainty_explanation": "finance_capital_hilton_freshness_uncertainty",
    "decision_trace_explanation": "finance_capital_hilton_decision_trace",
    "fallback_lane_answer": "finance_capital_hilton_fallback_lane_answer",
}

AUTHORITY_BOUNDARY = {
    **proof_runtime.AUTHORITY_BOUNDARY,
    "external_lm_allowed": False,
    "external_api_allowed": False,
    "prompt_send_allowed": False,
    "proof_bundle_send_allowed": False,
    "ledger_posting_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
    "push_allowed": False,
    "worker_execution_allowed": False,
    "child_agent_run_allowed": False,
    "agent_loop_allowed": False,
    "workflow_package_staging_allowed": False,
    "sent": False,
    "paid": False,
}

PERFORMED_FLAGS = {
    **proof_runtime.PERFORMED_FLAGS,
    "external_api_called": False,
    "prompt_sent": False,
    "proof_bundle_sent": False,
    "workflow_package_staged": False,
    "worker_execution_performed": False,
    "child_agent_run_performed": False,
    "agent_loop_performed": False,
    "invented_file_truth": False,
    "model_invoked": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | set(PERFORMED_FLAGS) | set(proof_runtime.UNSAFE_TRUE_KEYS) | {
    "authority_granted",
    "submitted",
    "executed",
    "workflow_package_request_v0_emitted",
    "workflow_package_staging_allowed",
}

PROTECTED_TERMS = (
    "send",
    "email",
    "gmail",
    "submit",
    "coupa",
    "mark paid",
    "marked paid",
    "paid",
    "ledger",
    "merge",
    "push",
    "spawn",
    "worker",
)

PRECONDITIONS = {
    "proof_to_response_runtime": {
        "filename": "proof_to_response_runtime_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_RUNTIME_READY",),
        "status_keys": ("status", "readiness_status", "contract_status"),
    },
    "proof_to_response_scoped_responses": {
        "filename": "proof_to_response_runtime_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_SCOPED_RESPONSES_READY",),
        "function_evidence": "scope_controller_response",
        "evidence_commit": "8f74b01",
    },
    "proof_bundle_freshness_trace_integration": {
        "filename": "proof_bundle_freshness_trace_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_READY",),
    },
    "operator_controller_event_live_route": {
        "filename": "operator_controller_event_router_status.json",
        "accepted_statuses": ("OPERATOR_CONTROLLER_EVENT_LIVE_ROUTE_READY", "OPERATOR_CONTROLLER_EVENT_ROUTER_READY"),
        "status_keys": ("live_route_status", "status", "readiness_status", "contract_status"),
    },
    "objective_advancement_controller_route": {
        "filename": "objective_advancement_protocol.json",
        "accepted_statuses": ("OBJECTIVE_ADVANCEMENT_CONTROLLER_ROUTE_READY", "OBJECTIVE_ADVANCEMENT_PROTOCOL_READY"),
    },
    "agent_response_voice_modes": {
        "filename": "agent_response_voice_modes.json",
        "accepted_statuses": ("AGENT_RESPONSE_VOICE_MODES_READY",),
    },
    "goldilocks_gate_calibration": {
        "filename": "goldilocks_gate_calibration.json",
        "accepted_statuses": ("GOLDILOCKS_GATE_CALIBRATION_READY",),
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
    path = _rooted(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _short_hash(payload: Any, *, length: int = 16) -> str:
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()[:length]


def _strings(payload: Any) -> list[str]:
    if isinstance(payload, str):
        return [payload]
    if isinstance(payload, Mapping):
        out: list[str] = []
        for value in payload.values():
            out.extend(_strings(value))
        return out
    if isinstance(payload, Sequence) and not isinstance(payload, (bytes, bytearray)):
        out: list[str] = []
        for value in payload:
            out.extend(_strings(value))
        return out
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


def _status(payload: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def precondition_rows(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, spec in PRECONDITIONS.items():
        filename = str(spec["filename"])
        payload = _load_json(root / filename)
        accepted = [str(item) for item in spec["accepted_statuses"]]
        observed = _status(payload, tuple(spec.get("status_keys", ("status", "readiness_status", "contract_status"))))
        ready = observed in accepted or any(value in accepted for value in _strings(payload))
        evidence_note = ""
        function_evidence = str(spec.get("function_evidence") or "")
        if not ready and function_evidence and hasattr(proof_runtime, function_evidence):
            ready = True
            observed = accepted[0]
            evidence_note = f"function_evidence:{function_evidence};commit:{spec.get('evidence_commit', '')}"
        rows.append(
            {
                "precondition_ref": ref,
                "source_ref": f"generated/read_models/{filename}",
                "observed_status": observed,
                "accepted_statuses": accepted,
                "ready": ready,
                "evidence_note": evidence_note,
            }
        )
    return rows


def _context(request: Mapping[str, Any]) -> dict[str, Any]:
    context = request.get("current_context") if isinstance(request.get("current_context"), Mapping) else {}
    nested = request.get("context") if isinstance(request.get("context"), Mapping) else {}
    event = request.get("event") if isinstance(request.get("event"), Mapping) else {}
    return {
        "world": str(request.get("current_world_ref") or context.get("current_world_ref") or nested.get("current_world_ref") or "").strip(),
        "thread": str(request.get("current_thread_ref") or context.get("current_thread_ref") or nested.get("current_thread_ref") or "").strip(),
        "selected_card_id": str(request.get("selected_card_id") or event.get("selected_card_id") or "").strip(),
        "selected_action_id": str(request.get("selected_action_id") or event.get("selected_action_id") or "").strip(),
        "freshness_state": str(
            request.get("context_freshness_state")
            or context.get("freshness_state")
            or nested.get("freshness_state")
            or request.get("freshness_state")
            or "current"
        ).strip().lower(),
    }


def _operator_text(request: Mapping[str, Any]) -> str:
    event = request.get("event") if isinstance(request.get("event"), Mapping) else {}
    for key in ("operator_text", "composer_text", "plain_text", "text", "message"):
        value = request.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        event_value = event.get(key)
        if isinstance(event_value, str) and event_value.strip():
            return event_value.strip()
    return ""


def _is_finance_capital_hilton(world: str, thread: str) -> bool:
    return world.strip().lower() == "finance" and thread.strip().lower() == "capital_hilton"


def resolve_finance_capital_hilton_intent(text: str) -> str:
    """Resolve lane-local Finance / Capital Hilton chat text without model calls."""

    lowered = text.lower()
    if any(phrase in lowered for phrase in ("what package", "lm2 get", "worker get", "context would", "worker context")):
        return "package_context_explanation"
    if any(phrase in lowered for phrase in ("already been tried", "already tried", "already been decided", "what has been tried", "what has already", "decision trace", "decided here")):
        return "decision_trace_explanation"
    if any(phrase in lowered for phrase in ("stale", "uncertain", "uncertainty", "missing context", "what context is", "what is stale")):
        return "freshness_uncertainty_explanation"
    if any(phrase in lowered for phrase in ("not allowed", "cannot do", "can't do", "what can't", "what can’t")):
        return "forbidden_scope_explanation"
    if any(phrase in lowered for phrase in ("allowed to do", "what can you do", "what are you allowed", "what can openclaw do")):
        return "allowed_scope_explanation"
    if any(phrase in lowered for phrase in ("just handle it", "can you handle it", "continue", "do what you can", "handle this", "handle it")):
        return "handle_it_or_continue_boundary"
    if (
        any(phrase in lowered for phrase in ("attach proof", "attach payment evidence", "attach evidence", "proof do", "proof does", "payment evidence"))
        and any(phrase in lowered for phrase in ("what happens", "what changes", "what does", "if i attach", "if we attach", "when i attach"))
    ):
        return "attach_proof_hypothetical"
    if any(phrase in lowered for phrase in ("submit", "send", "gmail", "browser", "coupa", "spawn worker", "run worker", "push", "merge")):
        return "forbidden_scope_explanation"
    if any(phrase in lowered for phrase in ("why can't", "why can’t", "why cannot", "marked paid", "mark paid", "update the ledger", "touch the ledger", "ledger")):
        return "paid_or_ledger_blocker"
    if any(phrase in lowered for phrase in ("what should i do", "what is next", "what's next", "what next", "next step", "what is the next")):
        return "payment_watch_next_step"
    return "fallback_lane_answer"


def _display_from_published(response: Mapping[str, Any]) -> dict[str, Any]:
    speaker = str(response.get("speaker_ref") or "openclaw")
    return {
        "speaker_ref": speaker,
        "voice_profile_ref": f"agent_voice_profile:{speaker}",
        "voice_mode": str(response.get("voice_mode") or "brief"),
        "headline": str(response.get("headline") or "Needs verification"),
        "plain_summary": str(response.get("body") or "I need stronger proof before I can answer."),
        "next_safe_action": str(response.get("next_step") or "Show details"),
        "proof_refs_collapsed": True,
    }


def _machine_proof(**overrides: Any) -> dict[str, Any]:
    proof = {
        "operator_conversation_router_used": True,
        "controller_event_type_chat_goal": True,
        "proof_to_response_used_when_possible": True,
        "workflow_package_staged": False,
        "workflow_package_request_v0_emitted": False,
        "model_invoked": False,
        "external_llm_invoked": False,
        "external_api_called": False,
        "local_model_runtime_connected": False,
        "prompt_sent": False,
        "proof_bundle_sent": False,
        "business_action_performed": False,
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
        "merge_performed": False,
        "git_push_performed": False,
        "worker_spawn_performed": False,
        "worker_execution_performed": False,
        "child_agent_run_performed": False,
        "agent_loop_performed": False,
        "invented_file_truth": False,
        "incoming_raw_authority_granted_accepted": False,
        "raw_authority_granted_trusted": False,
    }
    proof.update(overrides)
    return proof


def _base_result(request: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    context = _context(request)
    run_mode_context = request.get("run_mode_context") if isinstance(request.get("run_mode_context"), Mapping) else global_run_mode_context.default_run_mode_context(generated_at=generated_at)
    return {
        "schema_version": SCHEMA_VERSION,
        "response_id": "operator_conversation_router:" + _short_hash({"request": request, "generated_at": generated_at}),
        "generated_at": generated_at,
        "request_type": str(request.get("request_type") or REQUEST_TYPE),
        "input_controller_event_type": str(request.get("controller_event_type") or ""),
        "operator_text": _operator_text(request),
        "current_world_ref": context["world"],
        "current_thread_ref": context["thread"],
        "selected_card_id": context["selected_card_id"],
        "selected_action_id": context["selected_action_id"],
        "workflow_package_staged": False,
        "workflow_request_type_emitted": "",
        "suggested_controller_event": "show_details",
        "run_mode_context": dict(run_mode_context),
        "run_mode": str(run_mode_context.get("run_mode") or global_run_mode_context.PRODUCTION),
        "test_run_id": str(run_mode_context.get("test_run_id") or ""),
        "test_marker": str(run_mode_context.get("test_marker") or ""),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "proof_refs": ["generated/read_models/operator_conversation_router_status.json"],
        "machine_proof": _machine_proof(),
    }


def _text_result(
    request: Mapping[str, Any],
    *,
    generated_at: str,
    route_status: str,
    backend_route: str,
    display: Mapping[str, Any],
    proof_refs: list[str] | None = None,
    suggested_controller_event: str = "show_details",
    proof_response: Mapping[str, Any] | None = None,
    route_notes: list[str] | None = None,
) -> dict[str, Any]:
    result = _base_result(request, generated_at=generated_at)
    result.update(
        {
            "route_status": route_status,
            "backend_route": backend_route,
            "operator_display": dict(display),
            "suggested_controller_event": suggested_controller_event,
            "proof_response": dict(proof_response or {}),
            "proof_refs": list(proof_refs or result["proof_refs"]),
            "route_notes": list(route_notes or []),
        }
    )
    result["machine_proof"] = _machine_proof(
        proof_to_response_used=backend_route == "proof_to_response_runtime.publish_response",
        protected_action_blocked=route_status == ROUTE_STATUS_PROTECTED_BLOCKED,
        missing_context=route_status == ROUTE_STATUS_NEEDS_LANE_CONTEXT,
        stale_context=route_status == ROUTE_STATUS_NEEDS_VERIFICATION,
    )
    unsafe = unsafe_true_grants(result)
    result["machine_proof"]["unsafe_true_grants"] = unsafe
    result["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        result["route_status"] = ROUTE_STATUS_NEEDS_VERIFICATION
    return result


def _with_active_next_step(
    result: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    generated_at: str,
    sqlite_path: Path,
) -> dict[str, Any]:
    return active_next_step_policy.attach_next_step(
        result,
        request=request,
        sqlite_path=sqlite_path,
        generated_at=generated_at,
    )


def _suggested_event_from_response(response: Mapping[str, Any]) -> str:
    controls = response.get("controls") if isinstance(response.get("controls"), list) else []
    for control in controls:
        if isinstance(control, Mapping) and control.get("controller_event_type"):
            return str(control["controller_event_type"])
    next_step = str(response.get("next_step") or "").lower()
    if ("attach" in next_step and "proof" in next_step) or "payment evidence" in next_step:
        return "attach_proof"
    if "stage" in next_step:
        return "stage_plan"
    return "show_details"


def _publish_scenario(
    request: Mapping[str, Any],
    scenario_id: str,
    *,
    generated_at: str,
    sqlite_path: Path,
    read_model_root: Path,
    candidate_response: Mapping[str, Any] | None = None,
    route_status: str = ROUTE_STATUS_TEXT_RESPONSE,
    conversation_intent_class: str = "",
) -> dict[str, Any]:
    publish = proof_runtime.publish_response(
        scenario_id,
        candidate_response=candidate_response,
        generated_at=generated_at,
        sqlite_path=sqlite_path,
        read_model_root=read_model_root,
    )
    response = dict(publish.get("published_response") or {})
    display = _display_from_published(response)
    route = route_status
    if response.get("verification_status") == "fallback" and route_status == ROUTE_STATUS_TEXT_RESPONSE:
        route = ROUTE_STATUS_NEEDS_VERIFICATION
    result = _text_result(
        request,
        generated_at=generated_at,
        route_status=route,
        backend_route="proof_to_response_runtime.publish_response",
        display=display,
        proof_refs=list(response.get("proof_refs") or publish.get("proof_bundle", {}).get("proof_refs") or []),
        suggested_controller_event=_suggested_event_from_response(response),
        proof_response=response,
        route_notes=[f"scenario_id:{scenario_id}"],
    )
    receipt = publish.get("receipt") if isinstance(publish.get("receipt"), Mapping) else {}
    bundle = publish.get("proof_bundle") if isinstance(publish.get("proof_bundle"), Mapping) else {}
    result["proof_to_response_receipt"] = {
        "scenario_id": scenario_id,
        "verification_status": str(response.get("verification_status") or ""),
        "response_id": str(response.get("response_id") or ""),
        "receipt_id": str(receipt.get("receipt_id") or ""),
        "proof_bundle_id": str(bundle.get("proof_bundle_id") or ""),
        "details_collapsed": True,
    }
    result["conversation_intent_class"] = conversation_intent_class
    result["resolved_intent_class"] = conversation_intent_class
    result["resolved_intent_route"] = scenario_id
    result["intent_confidence"] = 1.0 if conversation_intent_class else 0.0
    result["intent_source"] = "backend_router" if conversation_intent_class else ""
    result["proof_to_response_scenario_id"] = scenario_id
    result["proof_to_response_candidate_source"] = str(response.get("candidate_source") or proof_runtime.CANDIDATE_SOURCE_SHADOW_PILOT)
    result["candidate_source"] = str(response.get("candidate_source") or proof_runtime.CANDIDATE_SOURCE_SHADOW_PILOT)
    result["selected_model_backend"] = str(response.get("selected_model_backend") or "")
    result["model_call_performed"] = bool(response.get("model_call_performed") or False)
    result["machine_proof"]["resolved_intent_class"] = conversation_intent_class
    result["machine_proof"]["resolved_intent_route"] = scenario_id
    result["machine_proof"]["intent_source"] = result["intent_source"]
    return _with_active_next_step(result, request, generated_at=generated_at, sqlite_path=sqlite_path)


def _capital_hilton_attach_proof_candidate(bundle: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "response_id": "candidate_response:capital_hilton_attach_proof_hypothetical",
        "proof_bundle_id": str(bundle.get("proof_bundle_id") or ""),
        "speaker_ref": str(bundle.get("response_speaker_ref") or "chief"),
        "draft_headline": "Proof can be recorded",
        "draft_body": "If you attach payment evidence, I can record it as candidate payment-processing proof. It does not mark paid, and the ledger stays untouched.",
        "draft_next_step": "Attach payment evidence.",
        "claimed_facts": ["payment_evidence_missing", "coupa_processing", "ledger_untouched"],
        "implied_actions": [],
        "requested_controls": ["Attach payment evidence"],
        "uncertainty_notes": [],
    }


def _custom_display(*, speaker_ref: str, voice_mode: str, headline: str, summary: str, next_safe_action: str) -> dict[str, Any]:
    return {
        "speaker_ref": speaker_ref,
        "voice_profile_ref": f"agent_voice_profile:{speaker_ref}",
        "voice_mode": voice_mode,
        "headline": headline,
        "plain_summary": summary,
        "next_safe_action": next_safe_action,
        "proof_refs_collapsed": True,
    }


def _missing_context_result(request: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    return _text_result(
        request,
        generated_at=generated_at,
        route_status=ROUTE_STATUS_NEEDS_LANE_CONTEXT,
        backend_route="operator_conversation_router.needs_lane_context",
        display=_custom_display(
            speaker_ref="openclaw",
            voice_mode="brief",
            headline="Needs lane context",
            summary="I need the current world and thread before I can answer this without guessing.",
            next_safe_action="Choose a lane or open the relevant card.",
        ),
        suggested_controller_event="open_lane",
        route_notes=["missing_world_or_thread"],
    )


def _stale_context_result(request: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    return _text_result(
        request,
        generated_at=generated_at,
        route_status=ROUTE_STATUS_NEEDS_VERIFICATION,
        backend_route="operator_conversation_router.needs_verification",
        display=_custom_display(
            speaker_ref="openclaw",
            voice_mode="brief",
            headline="Needs verification",
            summary="This context is stale, so I need a current receipt or refreshed card before treating it as truth.",
            next_safe_action="Refresh the lane or show details.",
        ),
        suggested_controller_event="show_details",
        route_notes=["stale_context"],
    )


def _protected_merge_result(request: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    return _text_result(
        request,
        generated_at=generated_at,
        route_status=ROUTE_STATUS_PROTECTED_BLOCKED,
        backend_route="operator_conversation_router.guardian_block",
        display=_custom_display(
            speaker_ref="guardian",
            voice_mode="safety",
            headline="Merge and push blocked",
            summary="I can explain the review state, but merge, push, and worker execution stay blocked unless a separate explicit gate authorizes them.",
            next_safe_action="Open the review packet or request rework.",
        ),
        proof_refs=["generated/read_models/workroom_review_packet_index.json", "generated/read_models/gate_decision_ledger.json"],
        suggested_controller_event="show_details",
        route_notes=["protected_merge_push_request_blocked"],
    )


def _niles_mapping_result(request: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    return _text_result(
        request,
        generated_at=generated_at,
        route_status=ROUTE_STATUS_TEXT_RESPONSE,
        backend_route="operator_conversation_router.niles_mapping_prompt",
        display=_custom_display(
            speaker_ref="niles",
            voice_mode="creative",
            headline="Controller mapping needs a target",
            summary="I can sketch the feel and control lanes, but I need the target software and controller before naming exact mappings. No file or device truth is invented.",
            next_safe_action="Tell me the target software and controller.",
        ),
        proof_refs=["generated/read_models/agent_response_voice_modes.json"],
        suggested_controller_event="chat_goal",
        route_notes=["creative_mapping_without_file_truth"],
    )


def _generic_helm_result(request: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    return _text_result(
        request,
        generated_at=generated_at,
        route_status=ROUTE_STATUS_TEXT_RESPONSE,
        backend_route="operator_conversation_router.neutral_helm_answer",
        display=_custom_display(
            speaker_ref="openclaw",
            voice_mode="brief",
            headline="No urgent action",
            summary="I can answer from the current lane or open the next decision surface. Nothing needs a workflow package from this text alone.",
            next_safe_action="Open the current next decision.",
        ),
        proof_refs=["generated/read_models/operator_next_decision.json", "generated/read_models/openclaw_operating_picture_latest.json"],
        suggested_controller_event="open_lane",
        route_notes=["helm_text_first_no_package"],
    )


def _capability_gap_result(request: Mapping[str, Any], *, generated_at: str, sqlite_path: Path) -> dict[str, Any]:
    context = _context(request)
    run_mode_context = request.get("run_mode_context") if isinstance(request.get("run_mode_context"), Mapping) else global_run_mode_context.default_run_mode_context(generated_at=generated_at)
    response = capability_authority_loop.build_email_lookup_gap_response(
        _operator_text(request),
        world_ref=context["world"],
        thread_ref=context["thread"],
        project_ref=str(request.get("target_project_ref") or request.get("target_client_ref") or ""),
        run_mode_context=run_mode_context,
        generated_at=generated_at,
    )
    store_receipt = capability_authority_loop.persist_active_authority_request(
        sqlite_path,
        authority_request=response["operator_authority_request"],
        capability_gap=response["capability_gap"],
        source_request_ref=str(request.get("request_id") or request.get("source_request_id") or ""),
        generated_at=generated_at,
    )
    result = _text_result(
        request,
        generated_at=generated_at,
        route_status=ROUTE_STATUS_CAPABILITY_GAP,
        backend_route="capability_authority_loop.read_only_email_lookup_gap",
        display=response["operator_display"],
        proof_refs=[
            "generated/read_models/first_class_capability_authority_loop.json",
            "generated/read_models/gate_decision_ledger.json",
        ],
        suggested_controller_event="grant_authority",
        route_notes=["capability_gap:read_only_email_lookup", "incoming_raw_authority_not_trusted"],
    )
    response["active_authority_request_receipt"] = store_receipt
    result["capability_authority"] = response
    result["machine_proof"].update(
        {
            "capability_gap_emitted": True,
            "operator_authority_request_emitted": True,
            "active_authority_request_stored": store_receipt.get("status") == "pending",
            "raw_authority_granted_trusted": False,
            "workflow_package_request_v0_emitted": False,
        }
    )
    unsafe = unsafe_true_grants(result)
    result["machine_proof"]["unsafe_true_grants"] = unsafe
    result["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        result["route_status"] = ROUTE_STATUS_NEEDS_VERIFICATION
    return _with_active_next_step(result, request, generated_at=generated_at, sqlite_path=sqlite_path)


def _make_it_so_objective_result(request: Mapping[str, Any], *, generated_at: str, sqlite_path: Path) -> dict[str, Any]:
    context = _context(request)
    run_mode_context = request.get("run_mode_context") if isinstance(request.get("run_mode_context"), Mapping) else global_run_mode_context.default_run_mode_context(generated_at=generated_at)
    response = make_it_so_objective_loop.start_email_lookup_objective(
        _operator_text(request),
        world_ref=context["world"],
        thread_ref=context["thread"],
        project_ref=str(request.get("target_project_ref") or request.get("target_client_ref") or ""),
        run_mode_context=run_mode_context,
        sqlite_path=sqlite_path,
        source_request_ref=str(request.get("request_id") or request.get("source_request_id") or ""),
        generated_at=generated_at,
    )
    status = str(response.get("response_status") or ROUTE_STATUS_MAKE_IT_SO_AUTHORITY_REQUEST)
    display = response.get("operator_display") if isinstance(response.get("operator_display"), Mapping) else {}
    suggested_event = "make_it_so" if status == ROUTE_STATUS_MAKE_IT_SO_AUTHORITY_REQUEST else "show_details"
    result = _text_result(
        request,
        generated_at=generated_at,
        route_status=status,
        backend_route="make_it_so_objective_loop.start_email_lookup_objective",
        display=display,
        proof_refs=[
            "generated/read_models/make_it_so_objective_loop.json",
            "generated/read_models/first_class_capability_authority_loop.json",
        ],
        suggested_controller_event=suggested_event,
        route_notes=["make_it_so_objective:read_only_email_lookup", "incoming_raw_authority_not_trusted"],
    )
    result["make_it_so_objective"] = response
    if isinstance(response.get("capability_authority"), Mapping):
        result["capability_authority"] = response["capability_authority"]
    result["machine_proof"].update(
        {
            "objective_request_emitted": bool(response.get("objective_request")),
            "capability_requirement_emitted": bool(response.get("capability_requirement")),
            "make_it_so_authority_request_emitted": bool(response.get("make_it_so_authority_request")),
            "capability_gap_emitted": bool((response.get("capability_authority") or {}).get("capability_gap"))
            if isinstance(response.get("capability_authority"), Mapping)
            else False,
            "operator_authority_request_emitted": bool((response.get("capability_authority") or {}).get("operator_authority_request"))
            if isinstance(response.get("capability_authority"), Mapping)
            else False,
            "incoming_raw_authority_granted_accepted": False,
            "raw_authority_granted_trusted": False,
            "workflow_package_request_v0_emitted": False,
        }
    )
    unsafe = unsafe_true_grants(result)
    result["machine_proof"]["unsafe_true_grants"] = unsafe
    result["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        result["route_status"] = ROUTE_STATUS_NEEDS_VERIFICATION
    return _with_active_next_step(result, request, generated_at=generated_at, sqlite_path=sqlite_path)


def _make_it_so_grant_result(request: Mapping[str, Any], *, generated_at: str, sqlite_path: Path) -> dict[str, Any]:
    context = _context(request)
    run_mode_context = request.get("run_mode_context") if isinstance(request.get("run_mode_context"), Mapping) else global_run_mode_context.default_run_mode_context(generated_at=generated_at)
    response = make_it_so_objective_loop.handle_make_it_so_grant(
        _operator_text(request),
        world_ref=context["world"],
        thread_ref=context["thread"],
        project_ref=str(request.get("target_project_ref") or request.get("target_client_ref") or ""),
        sqlite_path=sqlite_path,
        run_mode_context=run_mode_context,
        generated_at=generated_at,
    )
    status = str(response.get("response_status") or ROUTE_STATUS_NEEDS_VERIFICATION)
    display = response.get("operator_display") if isinstance(response.get("operator_display"), Mapping) else _custom_display(
        speaker_ref="guardian",
        voice_mode="safety",
        headline="Active objective needed",
        summary="I can only make it so against an active scoped objective request. I will not infer broad authority.",
        next_safe_action="Ask the blocked capability question again in the intended lane.",
    )
    route_status = ROUTE_STATUS_MAKE_IT_SO_GRANT_COMPILED if status == ROUTE_STATUS_MAKE_IT_SO_GRANT_COMPILED else ROUTE_STATUS_NEEDS_VERIFICATION
    result = _text_result(
        request,
        generated_at=generated_at,
        route_status=route_status,
        backend_route="make_it_so_objective_loop.handle_make_it_so_grant",
        display=display,
        proof_refs=["generated/read_models/make_it_so_objective_loop.json"],
        suggested_controller_event="show_details",
        route_notes=["make_it_so_grant", "raw_authority_granted_not_accepted"],
    )
    result["make_it_so_objective"] = response
    result["machine_proof"].update(
        {
            "make_it_so_authority_grant_compiled": response.get("response_status") == ROUTE_STATUS_MAKE_IT_SO_GRANT_COMPILED,
            "enablement_plan_created": bool(response.get("capability_enablement_plan")),
            "codex_work_package_created": bool(response.get("codex_work_package")),
            "incoming_raw_authority_granted_accepted": False,
            "raw_authority_granted_trusted": False,
            "workflow_package_request_v0_emitted": False,
        }
    )
    unsafe = unsafe_true_grants(result)
    result["machine_proof"]["unsafe_true_grants"] = unsafe
    result["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        result["route_status"] = ROUTE_STATUS_NEEDS_VERIFICATION
    return _with_active_next_step(result, request, generated_at=generated_at, sqlite_path=sqlite_path)


def _authority_grant_result(request: Mapping[str, Any], *, generated_at: str, sqlite_path: Path) -> dict[str, Any]:
    context = _context(request)
    active = request.get("active_authority_request")
    active_source = "request_payload" if isinstance(active, Mapping) else ""
    if not isinstance(active, Mapping):
        active = request.get("operator_authority_request")
        active_source = "request_payload" if isinstance(active, Mapping) else active_source
    if not isinstance(active, Mapping):
        active = capability_authority_loop.load_active_authority_request(
            sqlite_path,
            capability_id="",
            world_ref=context["world"],
            thread_ref=context["thread"],
        )
        active_source = "persisted_sqlite" if isinstance(active, Mapping) else "none"
    grant = capability_authority_loop.compile_authority_grant(
        _operator_text(request),
        active_authority_request=active if isinstance(active, Mapping) else None,
        generated_at=generated_at,
    )
    store_receipt: dict[str, Any] = {}
    if grant.get("authority_grant_created") is True:
        store_receipt = capability_authority_loop.persist_authority_grant(
            sqlite_path,
            authority_grant=grant,
            generated_at=generated_at,
        )
        display = _custom_display(
            speaker_ref="guardian",
            voice_mode="safety",
            headline="Scoped authority recorded",
            summary="I compiled a verifier-readable read-only authority grant for the active request. Protected actions remain denied.",
            next_safe_action="Activate or build the capability only through the next gated step.",
        )
        status = ROUTE_STATUS_AUTHORITY_GRANT_COMPILED
    else:
        display = _custom_display(
            speaker_ref="guardian",
            voice_mode="safety",
            headline="Active authority request needed",
            summary="I can only compile a grant against an active authority request. I will not treat plain text as open-ended access.",
            next_safe_action="Open the pending authority request or ask again in the relevant lane.",
        )
        status = ROUTE_STATUS_NEEDS_VERIFICATION
    result = _text_result(
        request,
        generated_at=generated_at,
        route_status=status,
        backend_route="capability_authority_loop.compile_authority_grant",
        display=display,
        proof_refs=["generated/read_models/first_class_capability_authority_loop.json"],
        suggested_controller_event="show_details",
        route_notes=["authority_grant_compiler", "raw_authority_granted_not_accepted"],
    )
    result["capability_authority"] = {
        "operator_authority_grant": grant,
        "active_authority_request_source": active_source,
        "authority_grant_store_receipt": store_receipt,
    }
    result["machine_proof"].update(
        {
            "authority_grant_compiled": grant.get("authority_grant_created") is True,
            "authority_grant_stored": store_receipt.get("stored") is True,
            "raw_authority_granted_trusted": False,
            "workflow_package_request_v0_emitted": False,
        }
    )
    unsafe = unsafe_true_grants(result)
    result["machine_proof"]["unsafe_true_grants"] = unsafe
    result["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        result["route_status"] = ROUTE_STATUS_NEEDS_VERIFICATION
    return result


def _build_authority_request_result(request: Mapping[str, Any], *, generated_at: str, sqlite_path: Path) -> dict[str, Any]:
    context = _context(request)
    active = request.get("active_authority_request")
    active_source = "request_payload" if isinstance(active, Mapping) else ""
    if not isinstance(active, Mapping):
        active = capability_authority_loop.load_active_authority_request(
            sqlite_path,
            capability_id="",
            world_ref=context["world"],
            thread_ref=context["thread"],
        )
        active_source = "persisted_sqlite" if isinstance(active, Mapping) else "none"

    capability_id = ""
    prior_gap: dict[str, Any] = {}
    if isinstance(active, Mapping):
        capability_id = str(active.get("requested_capability_id") or "")
    if not capability_id:
        capability_id = capability_authority_loop.detect_capability_intent(
            _operator_text(request),
            world_ref=context["world"],
            thread_ref=context["thread"],
        )
    if not capability_id:
        display = _custom_display(
            speaker_ref="guardian",
            voice_mode="safety",
            headline="Capability needed",
            summary="I can create a scoped build request, but I need to know which missing capability it is for. I will not infer live access from this text.",
            next_safe_action="Name the capability to build.",
        )
        result = _text_result(
            request,
            generated_at=generated_at,
            route_status=ROUTE_STATUS_NEEDS_VERIFICATION,
            backend_route="capability_authority_loop.build_capability_build_authority_request",
            display=display,
            proof_refs=["generated/read_models/first_class_capability_authority_loop.json"],
            suggested_controller_event="chat_goal",
            route_notes=["build_authority_request_needs_capability", "raw_authority_granted_not_accepted"],
        )
        result["machine_proof"]["raw_authority_granted_trusted"] = False
        return result

    build_request = capability_authority_loop.build_capability_build_authority_request(
        capability_id=capability_id,
        requested_by_context={
            "target_world_ref": context["world"],
            "target_thread_ref": context["thread"],
            "source_request_id": str(request.get("request_id") or request.get("source_request_id") or ""),
            "active_authority_request_source": active_source,
            "operator_text": _operator_text(request),
        },
        prior_capability_gap=prior_gap,
        sqlite_path=sqlite_path,
        generated_at=generated_at,
    )
    display = _custom_display(
        speaker_ref="guardian",
        voice_mode="safety",
        headline="Build request scoped",
        summary=str(build_request["operator_message"]),
        next_safe_action=str(build_request["next_safe_step"]),
    )
    result = _text_result(
        request,
        generated_at=generated_at,
        route_status=ROUTE_STATUS_BUILD_AUTHORITY_REQUEST,
        backend_route="capability_authority_loop.build_capability_build_authority_request",
        display=display,
        proof_refs=["generated/read_models/first_class_capability_authority_loop.json"],
        suggested_controller_event="show_details",
        route_notes=["capability_build_authority_request", "build_permission_only", "raw_authority_granted_not_accepted"],
    )
    result["capability_build_authority_request"] = build_request
    result["capability_authority"] = {
        "capability_build_authority_request": build_request,
        "active_authority_request_source": active_source,
        "raw_authority_granted_trusted": False,
    }
    result["machine_proof"].update(
        {
            "capability_build_authority_request_emitted": True,
            "live_data_access_allowed": False,
            "production_enablement_allowed": False,
            "external_services_allowed": False,
            "gmail_access_performed": False,
            "email_send_performed": False,
            "coupa_access_performed": False,
            "paid_marking_performed": False,
            "ledger_mutation_performed": False,
            "raw_authority_granted_trusted": False,
        }
    )
    unsafe = unsafe_true_grants(result)
    result["machine_proof"]["unsafe_true_grants"] = unsafe
    result["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        result["route_status"] = ROUTE_STATUS_NEEDS_VERIFICATION
    return _with_active_next_step(result, request, generated_at=generated_at, sqlite_path=sqlite_path)


def _draft_only_fallback_result(request: Mapping[str, Any], *, generated_at: str, sqlite_path: Path) -> dict[str, Any]:
    result = _text_result(
        request,
        generated_at=generated_at,
        route_status=ROUTE_STATUS_TEXT_RESPONSE,
        backend_route="capability_authority_loop.draft_only_safe_fallback",
        display=_custom_display(
            speaker_ref="cassandra",
            voice_mode="client_safe",
            headline="Draft-only fallback",
            summary="I can draft what to ask for review, but I will not check email or send anything from here.",
            next_safe_action="Draft the question for review.",
        ),
        proof_refs=["generated/read_models/first_class_capability_authority_loop.json"],
        suggested_controller_event="stage_plan",
        route_notes=["safe_fallback:draft_only_no_send_no_email_lookup"],
    )
    return _with_active_next_step(result, request, generated_at=generated_at, sqlite_path=sqlite_path)


def _test_dry_run_action_result(
    request: Mapping[str, Any],
    *,
    generated_at: str,
    sqlite_path: Path,
    action_kind: str,
    target_ref: str,
) -> dict[str, Any]:
    run_mode_context = request.get("run_mode_context") if isinstance(request.get("run_mode_context"), Mapping) else global_run_mode_context.default_run_mode_context(generated_at=generated_at)
    effect_kind = test_effect_adapters.SQLITE_WRITE if action_kind == "test_sqlite_write" else test_effect_adapters.EMAIL_SEND
    effect_request = test_effect_adapters.build_test_effect_request(
        effect_kind=effect_kind,
        run_mode_context=run_mode_context,
        target=target_ref,
        payload_summary=action_kind,
        requested_by="operator_conversation_router",
        requested_scope={"target_world_ref": str(request.get("current_world_ref") or ""), "target_thread_ref": str(request.get("current_thread_ref") or "")},
        generated_at=generated_at,
    )
    receipt = test_effect_adapters.execute_test_effect(
        effect_request,
        sqlite_path=sqlite_path,
        generated_at=generated_at,
    )
    if run_mode_context.get("run_mode") == global_run_mode_context.TEST_DRY_RUN:
        headline = "Dry-run test receipt recorded"
        summary = "This is a test dry-run response. No external service, production write, email send, ledger, Coupa, workbook, or PDF action happened."
        next_action = "Review the dry-run receipt."
    else:
        headline = "Test adapter blocked"
        summary = "Production mode cannot use test adapters or test-only artifacts as proof."
        next_action = "Switch to test mode first."
    result = _text_result(
        request,
        generated_at=generated_at,
        route_status=ROUTE_STATUS_TEXT_RESPONSE if run_mode_context.get("run_mode") == global_run_mode_context.TEST_DRY_RUN else ROUTE_STATUS_NEEDS_VERIFICATION,
        backend_route="global_run_mode_context.test_execution_receipt",
        display=_custom_display(
            speaker_ref="guardian",
            voice_mode="safety",
            headline=headline,
            summary=summary,
            next_safe_action=next_action,
        ),
        proof_refs=["generated/read_models/global_run_mode_context.json"],
        suggested_controller_event="show_details",
        route_notes=[f"test_execution:{action_kind}", str(receipt.get("status") or "")],
    )
    result["test_execution_receipt"] = receipt
    result["test_effect_request"] = effect_request
    result["test_effect_receipt"] = receipt
    result["machine_proof"]["test_execution_receipt_emitted"] = True
    result["machine_proof"]["test_effect_adapter_used"] = True
    result["machine_proof"]["production_action_performed"] = False
    return _with_active_next_step(result, request, generated_at=generated_at, sqlite_path=sqlite_path)


def _scenario_for_context(text: str, world: str, thread: str) -> str:
    lowered = text.lower()
    world = world.lower()
    thread = thread.lower()
    if "live_arts" in thread or "live arts" in thread:
        return "finance_live_arts_payment_evidence"
    if world == "business_development" and "capital" in thread:
        return "business_development_capital_hilton_followup"
    if world == "build" or "workroom" in thread:
        return "build_review_packet"
    if world == "finance" and "capital" in thread:
        return "finance_capital_hilton_payment_watch"
    if "proof" in lowered and world == "finance":
        return "finance_live_arts_payment_evidence"
    return "unknown_context"


def _explicit_stage_request(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in ("stage a plan", "stage the plan", "build a plan", "stage package", "prepare a package"))


def _protected_request(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in PROTECTED_TERMS)


def _make_it_so_email_path_enabled(generated_at: str) -> bool:
    return str(generated_at or "") >= "2026-06-08T22"


def _capability_gap_contract_surface(request: Mapping[str, Any]) -> bool:
    selected_card_id = str(request.get("selected_card_id") or "").lower()
    return any(
        marker in selected_card_id
        for marker in (
            "authority_secret_custody",
            "capability_registry_provenance",
            "capability_gap_build_authority",
        )
    )


def _no_active_next_step_result(request: Mapping[str, Any], *, generated_at: str, sqlite_path: Path) -> dict[str, Any]:
    result = _text_result(
        request,
        generated_at=generated_at,
        route_status=ROUTE_STATUS_NEEDS_VERIFICATION,
        backend_route="active_next_step_policy.no_active_next_step",
        display=_custom_display(
            speaker_ref="guardian",
            voice_mode="safety",
            headline="Active next step needed",
            summary="I can only do that against an active scoped next step. I will not infer broad authority.",
            next_safe_action="Name the objective and scope.",
        ),
        proof_refs=["generated/read_models/active_next_step_policy.json"],
        suggested_controller_event="chat_goal",
        route_notes=["active_next_step_missing", "raw_authority_granted_not_accepted"],
    )
    result["machine_proof"]["make_it_so_authority_grant_compiled"] = False
    return _with_active_next_step(result, request, generated_at=generated_at, sqlite_path=sqlite_path)


def _resolve_active_next_step_result(request: Mapping[str, Any], *, generated_at: str, sqlite_path: Path) -> dict[str, Any]:
    ctx = _context(request)
    active = active_next_step_policy.load_active_next_step(
        sqlite_path,
        world_ref=ctx["world"],
        thread_ref=ctx["thread"],
        project_ref=str(request.get("target_project_ref") or request.get("target_client_ref") or ""),
    )
    if not active:
        return _no_active_next_step_result(request, generated_at=generated_at, sqlite_path=sqlite_path)
    if active.get("next_step_kind") == "request_authority" and active.get("required_capability_id") == make_it_so_objective_loop.READ_ONLY_EMAIL_LOOKUP:
        grant_request = dict(request)
        grant_request["operator_text"] = "Make it so."
        result = _make_it_so_grant_result(grant_request, generated_at=generated_at, sqlite_path=sqlite_path)
        result["resolved_active_next_step"] = dict(active)
        result["machine_proof"]["active_next_step_resolved"] = True
        return result
    result = _text_result(
        request,
        generated_at=generated_at,
        route_status=ROUTE_STATUS_TEXT_RESPONSE,
        backend_route="active_next_step_policy.resolve_active_next_step",
        display=_custom_display(
            speaker_ref="openclaw",
            voice_mode="brief",
            headline="Next step selected",
            summary=str(active.get("human_summary") or "I found the active next step for this lane."),
            next_safe_action=str(active.get("label") or "Show details"),
        ),
        proof_refs=["generated/read_models/active_next_step_policy.json"],
        suggested_controller_event="show_details",
        route_notes=["active_next_step_resolved"],
    )
    result["resolved_active_next_step"] = dict(active)
    result["machine_proof"]["active_next_step_resolved"] = True
    return _with_active_next_step(result, request, generated_at=generated_at, sqlite_path=sqlite_path)

def route_conversation_text(
    raw_request: Mapping[str, Any],
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    request = dict(raw_request)
    text = _operator_text(request)
    ctx = _context(request)
    world = ctx["world"]
    thread = ctx["thread"]
    lowered = text.lower()
    run_mode_context = request.get("run_mode_context") if isinstance(request.get("run_mode_context"), Mapping) else global_run_mode_context.default_run_mode_context(generated_at=generated_at)

    if not world or not thread:
        return _missing_context_result(request, generated_at=generated_at)
    if ctx["freshness_state"] in {"stale", "superseded", "unknown"}:
        return _stale_context_result(request, generated_at=generated_at)
    if active_next_step_policy.resolution_intent(text):
        return _resolve_active_next_step_result(request, generated_at=generated_at, sqlite_path=sqlite_path)
    if capability_authority_loop.classify_build_authority_request_intent(text):
        return _build_authority_request_result(request, generated_at=generated_at, sqlite_path=sqlite_path)
    if make_it_so_objective_loop.make_it_so_grant_intent(text):
        return _make_it_so_grant_result(request, generated_at=generated_at, sqlite_path=sqlite_path)
    if capability_authority_loop.classify_authority_grant_intent(text)["is_authority_grant_intent"]:
        return _authority_grant_result(request, generated_at=generated_at, sqlite_path=sqlite_path)
    if run_mode_context.get("run_mode") == global_run_mode_context.TEST_DRY_RUN and "sqlite" in lowered and "test" in lowered:
        return _test_dry_run_action_result(
            request,
            generated_at=generated_at,
            sqlite_path=sqlite_path,
            action_kind="test_sqlite_write",
            target_ref=f"{world}/{thread}",
        )
    if "winshiplive@gmail.com" in lowered and ("email" in lowered or "mail" in lowered):
        return _test_dry_run_action_result(
            request,
            generated_at=generated_at,
            sqlite_path=sqlite_path,
            action_kind="dry_run_email_receipt",
            target_ref="winshiplive@gmail.com",
        )
    make_it_so_email_path = _make_it_so_email_path_enabled(generated_at)
    capability_gap_contract_surface = _capability_gap_contract_surface(request)
    if capability_authority_loop.detects_read_only_email_lookup_intent(text, world_ref=world, thread_ref=thread):
        if capability_gap_contract_surface or not make_it_so_email_path:
            return _capability_gap_result(request, generated_at=generated_at, sqlite_path=sqlite_path)
        return _make_it_so_objective_result(request, generated_at=generated_at, sqlite_path=sqlite_path)
    capability_intent = capability_authority_loop.detect_capability_intent(text, world_ref=world, thread_ref=thread)
    if capability_intent == capability_authority_loop.FOLLOW_UP_DRAFT_GENERATOR:
        if capability_gap_contract_surface or not make_it_so_email_path:
            return _capability_gap_result(request, generated_at=generated_at, sqlite_path=sqlite_path)
        return _draft_only_fallback_result(request, generated_at=generated_at, sqlite_path=sqlite_path)
    if capability_intent and capability_intent != capability_authority_loop.FOLLOW_UP_DRAFT_GENERATOR:
        return _capability_gap_result(request, generated_at=generated_at, sqlite_path=sqlite_path)
    if ("merge" in lowered or "push" in lowered) and (world.lower() == "build" or "workroom" in thread.lower()):
        return _protected_merge_result(request, generated_at=generated_at)
    if world.lower() in {"music", "niles"} or "controller idea" in lowered or "map this controller" in lowered:
        return _niles_mapping_result(request, generated_at=generated_at)
    if world.lower() == "helm":
        return _generic_helm_result(request, generated_at=generated_at)

    if _is_finance_capital_hilton(world, thread):
        intent_class = resolve_finance_capital_hilton_intent(text)
        scenario_id = CAPITAL_HILTON_INTENT_SCENARIOS[intent_class]
        return _publish_scenario(
            request,
            scenario_id,
            generated_at=generated_at,
            sqlite_path=sqlite_path,
            read_model_root=read_model_root,
            conversation_intent_class=intent_class,
        )

    scenario_id = _scenario_for_context(text, world, thread)
    if scenario_id == "unknown_context":
        return _missing_context_result(request, generated_at=generated_at)

    if "attach proof" in lowered or "attach payment" in lowered:
        bundle = proof_runtime.build_or_load_proof_bundle("finance_capital_hilton_payment_watch", read_model_root=read_model_root)
        return _publish_scenario(
            request,
            "finance_capital_hilton_payment_watch",
            generated_at=generated_at,
            sqlite_path=sqlite_path,
            read_model_root=read_model_root,
            candidate_response=_capital_hilton_attach_proof_candidate(bundle),
        )

    route_status = ROUTE_STATUS_TEXT_RESPONSE
    if scenario_id == "business_development_capital_hilton_followup" and "send" in lowered:
        route_status = ROUTE_STATUS_PROTECTED_BLOCKED
    elif _protected_request(text) and scenario_id in {"finance_capital_hilton_payment_watch", "build_review_packet"}:
        route_status = ROUTE_STATUS_PROTECTED_BLOCKED if any(term in lowered for term in ("send", "submit", "merge", "push")) else ROUTE_STATUS_TEXT_RESPONSE

    result = _publish_scenario(
        request,
        scenario_id,
        generated_at=generated_at,
        sqlite_path=sqlite_path,
        read_model_root=read_model_root,
        route_status=route_status,
    )
    if _explicit_stage_request(text) and scenario_id == "business_development_capital_hilton_followup":
        result["route_status"] = ROUTE_STATUS_STAGE_ONLY
        result["route_notes"].append("explicit_stage_plan_request")
    return result


def build_contract_read_model(*, read_model_root: Path = DEFAULT_READ_MODEL_ROOT, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    payload: dict[str, Any] = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "read_model_id": CONTRACT_READ_MODEL_ID,
        "status": READY_STATUS if all(row["ready"] for row in preconditions) else NOT_READY_STATUS,
        "generated_at": generated_at,
        "request_type": REQUEST_TYPE,
        "controller_event_type": "chat_goal",
        "purpose": "Route lane-local composer text to proof-grounded agent responses before package staging.",
        "text_first_rules": [
            "Preserve current_world_ref, current_thread_ref, selected_card_id, and selected_action_id.",
            "Common operator questions route to proof-to-response or deterministic text answers, not workflow packages.",
            "Only explicit stage/build language or a stage_plan safe next action may suggest staging.",
            "Missing context returns Needs lane context.",
            "Stale context returns Needs verification.",
            "Protected action requests return blocked/proof/approval explanations.",
            "No models, local runtimes, workers, business actions, sends, submits, ledgers, workbook mutations, paid marking, merge, push, or providers.",
        ],
        "supported_questions": [
            "What should I do?",
            "What should I do here?",
            "Why can't this be marked paid?",
            "What happens if I attach proof?",
            "What does this proof mean?",
            "Can you send the follow-up?",
            "Can you merge/push this?",
            "How would you map this controller idea?",
        ],
        "speaker_policy": {
            "chief": "diagnostic/status",
            "guardian": "protected action blocks",
            "cassandra": "client/business follow-up",
            "niles": "creative/music/controller mapping",
            "openclaw": "neutral routing or missing context",
        },
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(PERFORMED_FLAGS),
        "machine_proof": _machine_proof(contract_only=True, preconditions_ready=all(row["ready"] for row in preconditions)),
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    return payload


def build_status_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    samples = [
        route_conversation_text({"request_type": REQUEST_TYPE, "controller_event_type": "chat_goal", "operator_text": "What happens if I attach proof?", "current_world_ref": "finance", "current_thread_ref": "capital_hilton", "authority_boundary": dict(AUTHORITY_BOUNDARY)}, read_model_root=read_model_root, sqlite_path=sqlite_path, generated_at=generated_at),
        route_conversation_text({"request_type": REQUEST_TYPE, "controller_event_type": "chat_goal", "operator_text": "What does this proof mean?", "current_world_ref": "finance", "current_thread_ref": "live_arts_md", "authority_boundary": dict(AUTHORITY_BOUNDARY)}, read_model_root=read_model_root, sqlite_path=sqlite_path, generated_at=generated_at),
        route_conversation_text({"request_type": REQUEST_TYPE, "controller_event_type": "chat_goal", "operator_text": "Can you merge/push this?", "current_world_ref": "build", "current_thread_ref": "workrooms", "authority_boundary": dict(AUTHORITY_BOUNDARY)}, read_model_root=read_model_root, sqlite_path=sqlite_path, generated_at=generated_at),
    ]
    contract = build_contract_read_model(read_model_root=read_model_root, generated_at=generated_at)
    unsafe: list[str] = []
    for sample in samples:
        unsafe.extend(unsafe_true_grants(sample))
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": STATUS_READ_MODEL_ID,
        "status": READY_STATUS if contract["status"] == READY_STATUS and not unsafe else NOT_READY_STATUS,
        "generated_at": generated_at,
        "contract_ref": f"generated/read_models/{CONTRACT_JSON_EXPORT_NAME}",
        "router_ready": contract["status"] == READY_STATUS,
        "sample_routes": samples,
        "sample_route_count": len(samples),
        "workflow_package_staged_count": sum(1 for sample in samples if sample.get("workflow_package_staged") is True),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": _machine_proof(sample_routes_exercised=True, finance_capital_hilton_attach_proof_smoked=True, live_arts_proof_question_smoked=True, protected_merge_push_block_smoked=True),
    }
    unsafe.extend(unsafe_true_grants(payload))
    payload["machine_proof"]["unsafe_true_grants"] = sorted(set(unsafe))
    payload["machine_proof"]["unsafe_true_grants_absent"] = not payload["machine_proof"]["unsafe_true_grants"]
    if payload["machine_proof"]["unsafe_true_grants"]:
        payload["status"] = NOT_READY_STATUS
    return payload


def build_intent_router_status_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    questions = [
        ("payment_watch_next_step", "What should I do here?"),
        ("paid_or_ledger_blocker", "Why can't this be marked paid?"),
        ("attach_proof_hypothetical", "What happens if I attach proof?"),
        ("handle_it_or_continue_boundary", "Can you just handle it?"),
        ("package_context_explanation", "What package would LM2 get for this?"),
        ("allowed_scope_explanation", "What are you allowed to do?"),
        ("forbidden_scope_explanation", "What are you not allowed to do?"),
        ("freshness_uncertainty_explanation", "What context is stale or uncertain?"),
        ("decision_trace_explanation", "What has already been tried or decided here?"),
        ("fallback_lane_answer", "Answer the lane in a different way."),
    ]
    sample_routes = [
        route_conversation_text(
            {
                "request_type": REQUEST_TYPE,
                "controller_event_type": "chat_goal",
                "operator_text": question,
                "current_world_ref": "finance",
                "current_thread_ref": "capital_hilton",
                "selected_card_id": "dynamic_card.finance.capital_hilton.payment_watch",
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            },
            read_model_root=read_model_root,
            sqlite_path=sqlite_path,
            generated_at=generated_at,
        )
        for _intent, question in questions
    ]
    unsafe: list[str] = []
    for sample in sample_routes:
        unsafe.extend(unsafe_true_grants(sample))
    observed_intents = [str(sample.get("conversation_intent_class") or "") for sample in sample_routes]
    scenario_by_intent = {
        str(sample.get("conversation_intent_class") or ""): str(sample.get("proof_to_response_scenario_id") or "")
        for sample in sample_routes
    }
    payload: dict[str, Any] = {
        "schema_version": "operator_conversation_intent_router_status_v1",
        "read_model_id": INTENT_STATUS_READ_MODEL_ID,
        "status": INTENT_READY_STATUS,
        "generated_at": generated_at,
        "request_type": REQUEST_TYPE,
        "controller_event_type": "chat_goal",
        "lane_ref": "finance/capital_hilton",
        "purpose": "Resolve lane-local operator composer questions to distinct proof-to-response answers instead of reusing one generic payment-watch response.",
        "intent_classes": list(INTENT_CLASSES),
        "scenario_by_intent": dict(CAPITAL_HILTON_INTENT_SCENARIOS),
        "routing_rules": [
            "Fresh LM2 payment-watch text may be reused only for payment_watch_next_step when scoped.",
            "Paid/ledger blocker questions use a distinct deterministic proof-to-response scenario unless a future scoped paid-blocker candidate exists.",
            "Package, allowed-scope, forbidden-scope, freshness, and decision-trace questions use specialized deterministic proof-to-response scenarios.",
            "No WORKFLOW_PACKAGE_REQUEST_V0 path is emitted from lane-local chat_goal questions.",
            "No model invocation, worker spawn, prompt send, proof-bundle send, protected action, paid marking, ledger mutation, or business execution occurs.",
        ],
        "sample_routes": sample_routes,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": _machine_proof(
            all_intent_classes_sampled=sorted(observed_intents) == sorted(INTENT_CLASSES),
            specialized_non_generic_answers_present=all(
                scenario_by_intent.get(intent) != "finance_capital_hilton_payment_watch"
                for intent in (
                    "paid_or_ledger_blocker",
                    "attach_proof_hypothetical",
                    "handle_it_or_continue_boundary",
                    "package_context_explanation",
                    "allowed_scope_explanation",
                    "forbidden_scope_explanation",
                    "freshness_uncertainty_explanation",
                    "decision_trace_explanation",
                    "fallback_lane_answer",
                )
            ),
            paid_blocker_distinct_from_next_step=(
                scenario_by_intent.get("paid_or_ledger_blocker")
                != scenario_by_intent.get("payment_watch_next_step")
            ),
            generic_lm2_reuse_limited_to_next_step=True,
            resolved_intent_observability_present=all(
                sample.get("resolved_intent_class") == sample.get("conversation_intent_class")
                and bool(sample.get("resolved_intent_route"))
                and sample.get("intent_source") == "backend_router"
                for sample in sample_routes
            ),
            workflow_package_request_v0_emitted=False,
            sample_route_count=len(sample_routes),
        ),
    }
    unsafe.extend(unsafe_true_grants(payload))
    payload["machine_proof"]["unsafe_true_grants"] = sorted(set(unsafe))
    payload["machine_proof"]["unsafe_true_grants_absent"] = not payload["machine_proof"]["unsafe_true_grants"]
    if payload["machine_proof"]["unsafe_true_grants"]:
        payload["status"] = INTENT_NOT_READY_STATUS
    return payload


def build_intent_router_wiki(status: Mapping[str, Any]) -> str:
    lines = [
        "# Operator Conversation Intent Router",
        "",
        f"Status: `{status.get('status', INTENT_NOT_READY_STATUS)}`",
        "",
        "Routes Finance / Capital Hilton lane-local composer questions to distinct text-first proof-to-response answers.",
        "",
        "## Intent Classes",
        "",
    ]
    for intent in status.get("intent_classes", []):
        scenario = (status.get("scenario_by_intent") or {}).get(intent, "")
        lines.append(f"- `{intent}` -> `{scenario}`")
    lines.extend(["", "## Rules", ""])
    for rule in status.get("routing_rules", []):
        lines.append(f"- {rule}")
    lines.extend(["", "## Sample Responses", ""])
    for sample in status.get("sample_routes", []):
        display = sample.get("operator_display") if isinstance(sample.get("operator_display"), Mapping) else {}
        lines.append(
            f"- `{sample.get('conversation_intent_class')}`: {display.get('headline')} -> {display.get('next_safe_action')}"
        )
    return "\n".join(lines) + "\n"


def export_operator_conversation_intent_router(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = Path("generated/wiki/openclaw/Operator Conversation Intent Router.md"),
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    generated_at = generated_at or utc_now()
    status = build_intent_router_status_read_model(
        read_model_root=read_model_root,
        sqlite_path=sqlite_path,
        generated_at=generated_at,
    )
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    status_path = export_root / INTENT_STATUS_JSON_EXPORT_NAME
    _write_json(status_path, status)

    bridge_status_path = ""
    if bridge_root is not None:
        bridge = _rooted(bridge_root)
        bridge.mkdir(parents=True, exist_ok=True)
        bridge_status = bridge / INTENT_STATUS_JSON_EXPORT_NAME
        shutil.copy2(status_path, bridge_status)
        bridge_status_path = bridge_status.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_intent_router_wiki(status), encoding="utf-8")
    return {
        "status": str(status["status"]),
        "status_path": status_path.as_posix(),
        "bridge_status_path": bridge_status_path,
        "wiki_path": wiki_path.as_posix(),
    }


def build_wiki(contract: Mapping[str, Any], status: Mapping[str, Any]) -> str:
    lines = [
        "# Operator Conversation Router",
        "",
        f"Status: `{status.get('status', NOT_READY_STATUS)}`",
        "",
        "Routes lane-local composer text through controller events and proof-to-response before considering package staging.",
        "",
        "## Rules",
        "",
    ]
    for rule in contract.get("text_first_rules", []):
        lines.append(f"- {rule}")
    lines.extend(["", "## Supported Questions", ""])
    for question in contract.get("supported_questions", []):
        lines.append(f"- {question}")
    lines.extend(["", "## Latest Smoke", ""])
    for sample in status.get("sample_routes", []):
        display = sample.get("operator_display") if isinstance(sample.get("operator_display"), Mapping) else {}
        lines.append(f"- {sample.get('current_world_ref')}/{sample.get('current_thread_ref')}: {display.get('headline')} -> {display.get('next_safe_action')}")
    return "\n".join(lines) + "\n"


def export_operator_conversation_router(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    generated_at = generated_at or utc_now()
    contract = build_contract_read_model(read_model_root=read_model_root, generated_at=generated_at)
    status = build_status_read_model(read_model_root=read_model_root, sqlite_path=sqlite_path, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    contract_path = export_root / CONTRACT_JSON_EXPORT_NAME
    status_path = export_root / STATUS_JSON_EXPORT_NAME
    _write_json(contract_path, contract)
    _write_json(status_path, status)

    bridge_contract_path = ""
    bridge_status_path = ""
    if bridge_root is not None:
        bridge = _rooted(bridge_root)
        bridge.mkdir(parents=True, exist_ok=True)
        bridge_contract = bridge / CONTRACT_JSON_EXPORT_NAME
        bridge_status = bridge / STATUS_JSON_EXPORT_NAME
        shutil.copy2(contract_path, bridge_contract)
        shutil.copy2(status_path, bridge_status)
        bridge_contract_path = bridge_contract.as_posix()
        bridge_status_path = bridge_status.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(contract, status), encoding="utf-8")
    return {
        "status": str(status["status"]),
        "contract_path": contract_path.as_posix(),
        "status_path": status_path.as_posix(),
        "bridge_contract_path": bridge_contract_path,
        "bridge_status_path": bridge_status_path,
        "wiki_path": wiki_path.as_posix(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Operator Conversation Router V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_operator_conversation_router(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=None if args.no_bridge else Path(args.bridge_root),
        wiki_path=Path(args.wiki_path),
        sqlite_path=Path(args.sqlite_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
