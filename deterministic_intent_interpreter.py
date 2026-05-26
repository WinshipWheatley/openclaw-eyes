"""Deterministic Intent Interpreter v0.

This module turns a narrow set of operator chat phrases into
MachineIntentCandidate records, validates them against the deterministic
validator and portable capability index, and emits a safe response plan.

It is not an LM interpreter, model caller, agent dispatcher, worker dispatcher,
workflow runner, external action lane, browser/Coupa/email integration, Mac
sync/import path, or credential/raw-body reader.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import machine_intent_candidate_validator as intent_validator
import openclaw_capability_index
import session_state_resolver
from machine_intent_candidate_validator import MachineIntentCandidate


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "deterministic_intent_interpreter_v0"
READ_MODEL_ID = "deterministic_intent_interpreter"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_INTENT_INTERPRETER_NO_EXECUTION"

INTERPRETER_ID = "deterministic_intent_interpreter:v0"

AUTHORITY_BOUNDARY = {
    "live_lm_interpreter_allowed": False,
    "live_model_call_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_worker_dispatch_allowed": False,
    "live_workflow_run_allowed": False,
    "live_external_action_allowed": False,
    "live_send_submit_allowed": False,
    "live_approval_execution_allowed": False,
    "live_candidate_promotion_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "live_browser_allowed": False,
    "live_coupa_access_allowed": False,
    "live_email_send_allowed": False,
    "live_file_mutation_allowed": False,
    "live_visual_provider_call_allowed": False,
    "live_video_generation_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "network_allowed": False,
}

VALIDATED_INTAKE_ELIWINSHIP = (
    "To move the Capital Hilton invoice forward, I need the Coupa PO/reference or a source file that proves it. "
    "Nothing will be submitted or sent from this step."
)


@dataclass(frozen=True)
class InterpreterResponsePlan:
    response_plan_id: str
    internal_status: str
    headline: str
    one_line_answer: str
    eliwinship: str
    primary_status: str
    primary_blocker: str
    next_action: str
    missing_items_short: tuple[str, ...]
    detail_summary: str
    operator_headline: str
    operator_message: str
    what_happened: tuple[str, ...]
    why_it_happened: str
    how_to_fix: str
    visible_cards: tuple[dict[str, Any], ...]
    response_author: str
    visual_event_package_requested: bool
    next_safe_move: str


@dataclass(frozen=True)
class DeterministicIntentInterpretation:
    interpreter_id: str
    matched: bool
    match_id: str
    operator_text: str
    source_request_id: str
    source_request_filename: str
    session_state: dict[str, Any]
    capability_query_trace: dict[str, Any]
    candidate: MachineIntentCandidate | None
    validation_result: dict[str, Any] | None
    missing_requirements: tuple[dict[str, Any], ...]
    build_cues: tuple[dict[str, Any], ...]
    context_gaps: tuple[dict[str, Any], ...]
    blockers: tuple[dict[str, Any], ...]
    response_plan: InterpreterResponsePlan | None
    authority_scout: dict[str, Any]
    machine_proof: dict[str, Any]


@dataclass(frozen=True)
class DeterministicIntentInterpreter:
    interpreter_id: str
    matching_policy: tuple[str, ...]
    session_policy: tuple[str, ...]
    capability_policy: tuple[str, ...]
    validation_policy: tuple[str, ...]
    response_policy: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str

    def interpret_request(
        self,
        raw_request: Mapping[str, Any],
        *,
        request_filename: str | None = None,
        export_root: Path = DEFAULT_EXPORT_ROOT,
        generated_at: str | None = None,
        session_state: session_state_resolver.ActiveSessionState | None = None,
        capability_query: openclaw_capability_index.CapabilityIndexQuery | None = None,
    ) -> DeterministicIntentInterpretation:
        generated_at = generated_at or utc_now()
        operator_text = _operator_text(raw_request)
        match_id = _match_operator_text(operator_text)
        source_request_id = str(raw_request.get("request_id") or f"deterministic_intent_{_short_hash(operator_text)}")
        source_request_filename = str(request_filename or raw_request.get("source_request_filename") or "")
        state = session_state or session_state_resolver.default_resolver().resolve(
            export_root=export_root,
            now=generated_at,
        )
        query = capability_query or _load_capability_query(export_root)

        if not match_id:
            return DeterministicIntentInterpretation(
                interpreter_id=self.interpreter_id,
                matched=False,
                match_id="UNMATCHED",
                operator_text=operator_text,
                source_request_id=source_request_id,
                source_request_filename=source_request_filename,
                session_state=asdict(state),
                capability_query_trace={},
                candidate=None,
                validation_result=None,
                missing_requirements=(),
                build_cues=(),
                context_gaps=(),
                blockers=(),
                response_plan=None,
                authority_scout=_authority_scout(),
                machine_proof=_machine_proof(matched=False),
            )

        candidate = _build_candidate(
            raw_request,
            operator_text=operator_text,
            match_id=match_id,
            source_request_id=source_request_id,
            session_state=state,
        )
        query_trace = _capability_query_trace(query, candidate, match_id, state)
        validation_result, missing, build_cues, context_gaps, blockers = intent_validator.validate_machine_intent_candidate(
            candidate,
            capability_index_payload=query.payload,
        )
        response_plan = _response_plan_for(
            match_id=match_id,
            candidate=candidate,
            validation_result=validation_result,
            missing_requirements=missing,
            build_cues=build_cues,
            context_gaps=context_gaps,
            blockers=blockers,
            session_state=state,
            query_trace=query_trace,
        )
        return DeterministicIntentInterpretation(
            interpreter_id=self.interpreter_id,
            matched=True,
            match_id=match_id,
            operator_text=operator_text,
            source_request_id=source_request_id,
            source_request_filename=source_request_filename,
            session_state=asdict(state),
            capability_query_trace=query_trace,
            candidate=candidate,
            validation_result=asdict(validation_result),
            missing_requirements=tuple(asdict(item) for item in missing),
            build_cues=tuple(asdict(item) for item in build_cues),
            context_gaps=tuple(asdict(item) for item in context_gaps),
            blockers=tuple(asdict(item) for item in blockers),
            response_plan=response_plan,
            authority_scout=_authority_scout(),
            machine_proof=_machine_proof(matched=True),
        )


def default_interpreter() -> DeterministicIntentInterpreter:
    return DeterministicIntentInterpreter(
        interpreter_id=INTERPRETER_ID,
        matching_policy=(
            "Match only narrow deterministic operator phrases.",
            "Fallback to existing request processor routes when no phrase matches.",
            "Do not treat ambient approval language as exact approval.",
        ),
        session_policy=(
            "Resolve safe generated response/read-model state before candidate generation.",
            "Use latest terminal state over heartbeat-only state.",
            "Ambiguous or missing active workflow asks clarification.",
        ),
        capability_policy=(
            "Use CapabilityIndexQuery before validator execution.",
            "Use generic safe capabilities for intent/task lookup.",
            "Use tenant/workflow bindings only when tenant scope matches.",
            "Reject proposed, fixture-only generic, future-gated, and live-provider records as usable live action.",
        ),
        validation_policy=(
            "Every matched candidate passes through DeterministicIntentValidator.",
            "Authority remains false even when the operator says go ahead.",
            "Missing capability and context outcomes become readback/build-cue posture only.",
        ),
        response_policy=(
            "Return terminal Mac-shaped response plans only.",
            "Do not call models, agents, workers, browser, Coupa, email, visual providers, or workflow runners.",
            "Preserve spoken/visual/taste payload compatibility through the request processor envelope.",
        ),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Wire this interpreter through the bounded request processor only.",
    )


def interpret_request(
    raw_request: Mapping[str, Any],
    *,
    request_filename: str | None = None,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
    session_state: session_state_resolver.ActiveSessionState | None = None,
    capability_query: openclaw_capability_index.CapabilityIndexQuery | None = None,
) -> DeterministicIntentInterpretation:
    return default_interpreter().interpret_request(
        raw_request,
        request_filename=request_filename,
        export_root=export_root,
        generated_at=generated_at,
        session_state=session_state,
        capability_query=capability_query,
    )


def should_interpret(raw_request: Mapping[str, Any]) -> bool:
    return bool(_match_operator_text(_operator_text(raw_request)))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _stable_id(prefix: str, *parts: object) -> str:
    return f"{prefix}:{_short_hash(prefix, *parts)}"


def _operator_text(raw_request: Mapping[str, Any]) -> str:
    for field in ("sanitized_message_summary", "operator_message", "operator_goal"):
        value = raw_request.get(field)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
    return ""


def _normalized_text(text: str) -> str:
    lowered = " ".join(str(text or "").lower().replace("'", "").split())
    return lowered.replace("’", "")


def _match_operator_text(operator_text: str) -> str:
    text = _normalized_text(operator_text)
    if not text:
        return ""
    if "ignore gates" in text and ("mark it sent" in text or "mark this sent" in text or "mark invoice sent" in text):
        return "PROMPT_INJECTION_MARK_SENT"
    if text in {"next", "continue"}:
        return "NEXT"
    if text in {"go ahead", "yeah do that", "yes do that", "do that"}:
        return "AMBIENT_GO_AHEAD"
    if "handle the coupa thing" in text or ("coupa thing" in text and "handle" in text):
        return "COUPA_MISSING_INPUT"
    if text in {"what do you need from me", "what do you need from me?", "what do you need"}:
        return "WHAT_DO_YOU_NEED"
    if "ask cassandra" in text and "email" in text and any(term in text for term in ("prep", "prepare", "draft")):
        return "CASSANDRA_PREP_EMAIL"
    if "show me" in text and any(term in text for term in ("blocking it", "blockers", "blocked by", "what is blocking")):
        return "SHOW_BLOCKING_STATUS"
    if "niles" in text and "x32" in text:
        return "NILES_X32"
    if "make a video" in text or "generate video" in text or "render video" in text:
        return "MAKE_VIDEO"
    return ""


def _load_capability_query(export_root: Path) -> openclaw_capability_index.CapabilityIndexQuery:
    index_path = Path(export_root) / openclaw_capability_index.JSON_EXPORT_NAME
    return openclaw_capability_index.CapabilityIndexQuery.load_index_from_generated_readmodel(index_path)


def _first_nonempty(*values: object) -> str:
    for value in values:
        if value not in (None, "", [], {}):
            return str(value)
    return ""


def _raw_workflow_ref(raw_request: Mapping[str, Any]) -> str:
    workflow = str(raw_request.get("workflow_ref") or "")
    return workflow if workflow and workflow.lower() != "unknown" else ""


def _workflow_for_candidate(match_id: str, raw_request: Mapping[str, Any], state: session_state_resolver.ActiveSessionState) -> str:
    if match_id == "NILES_X32":
        return "workflow:fixture:x32_source_refs"
    if match_id == "PROMPT_INJECTION_MARK_SENT":
        return _raw_workflow_ref(raw_request) or state.active_workflow_ref or "unknown"
    if match_id in {
        "NEXT",
        "AMBIENT_GO_AHEAD",
        "COUPA_MISSING_INPUT",
        "WHAT_DO_YOU_NEED",
        "SHOW_BLOCKING_STATUS",
        "CASSANDRA_PREP_EMAIL",
        "MAKE_VIDEO",
    }:
        return _raw_workflow_ref(raw_request) or (state.active_workflow_ref if not state.ambiguity_status else "unknown")
    return _raw_workflow_ref(raw_request) or "unknown"


def _world_folder_thread_for_candidate(
    match_id: str,
    state: session_state_resolver.ActiveSessionState,
) -> tuple[str, str, str]:
    if match_id == "NILES_X32":
        return ("world:fixture:creative_project", "folder_ref:x32", "thread_ref:unknown")
    return (
        state.active_world_ref if state.active_world_ref != "UNKNOWN" else "world_ref:unknown",
        state.active_folder_ref if state.active_folder_ref != "UNKNOWN" else "folder_ref:unknown",
        state.active_thread_ref if state.active_thread_ref != "UNKNOWN" else "thread_ref:unknown",
    )


def _ambient_go_ahead_needs_authority(state: session_state_resolver.ActiveSessionState) -> bool:
    text = _normalized_text(
        " ".join(
            (
                state.latest_next_action,
                state.latest_primary_blocker,
                state.latest_headline,
            )
        )
    )
    return any(term in text for term in ("send", "submit", "approval", "approve", "mark sent", "mark invoice sent"))


def _authority_false() -> dict[str, bool]:
    return dict(intent_validator.AUTHORITY_BOUNDARY)


def _authority_requested_for(match_id: str, state: session_state_resolver.ActiveSessionState) -> dict[str, bool]:
    requested = _authority_false()
    if match_id == "PROMPT_INJECTION_MARK_SENT" or (
        match_id == "AMBIENT_GO_AHEAD" and _ambient_go_ahead_needs_authority(state)
    ):
        requested.update(
            {
                "live_authority_allowed": True,
                "live_external_action_allowed": True,
                "live_outbound_message_send_allowed": True,
                "live_portal_submit_allowed": True,
            }
        )
    return requested


def _intent_for(match_id: str, state: session_state_resolver.ActiveSessionState) -> str:
    if match_id == "AMBIENT_GO_AHEAD" and _ambient_go_ahead_needs_authority(state):
        return "REQUEST_APPROVAL"
    return {
        "NEXT": "CONTINUE_CURRENT_WORKFLOW",
        "AMBIENT_GO_AHEAD": "CONTINUE_CURRENT_WORKFLOW",
        "COUPA_MISSING_INPUT": "CAPTURE_MISSING_INPUT",
        "WHAT_DO_YOU_NEED": "CAPTURE_MISSING_INPUT",
        "SHOW_BLOCKING_STATUS": "ANSWER_STATUS",
        "CASSANDRA_PREP_EMAIL": "PREPARE_DRAFT",
        "NILES_X32": "ROUTE_TO_AGENT",
        "MAKE_VIDEO": "SHOW_VISUAL_WORKSPACE",
        "PROMPT_INJECTION_MARK_SENT": "REQUEST_APPROVAL",
    }.get(match_id, "UNKNOWN_FAIL_CLOSED")


def _task_type_for(match_id: str) -> str:
    return {
        "NEXT": "capture_missing_input",
        "AMBIENT_GO_AHEAD": "send_or_submit_request" if match_id == "PROMPT_INJECTION_MARK_SENT" else "capture_missing_input",
        "COUPA_MISSING_INPUT": "capture_missing_input",
        "WHAT_DO_YOU_NEED": "missing_input",
        "SHOW_BLOCKING_STATUS": "status_readback",
        "CASSANDRA_PREP_EMAIL": "prepare outbound message draft",
        "NILES_X32": "source_ref",
        "MAKE_VIDEO": "make_video",
        "PROMPT_INJECTION_MARK_SENT": "send_or_submit_request",
    }.get(match_id, "unknown")


def _build_candidate(
    raw_request: Mapping[str, Any],
    *,
    operator_text: str,
    match_id: str,
    source_request_id: str,
    session_state: session_state_resolver.ActiveSessionState,
) -> MachineIntentCandidate:
    workflow_ref = _workflow_for_candidate(match_id, raw_request, session_state)
    world_ref, folder_ref, thread_ref = _world_folder_thread_for_candidate(match_id, session_state)
    intent_type = _intent_for(match_id, session_state)
    ambiguity = "UNAMBIGUOUS"
    confidence = "HIGH"
    required_clarification = ""
    missing_requirements: tuple[str, ...] = ()
    target_agent_role = "OPENCLAW_SYSTEM"
    target_worker_type = "PC_CODEX"
    referenced_next_action = session_state.latest_next_action
    evidence_refs = tuple(ref for ref in session_state.safe_readmodel_refs if ref)
    context_refs = tuple(
        ref
        for ref in (
            session_state.tenant_scope,
            session_state.client_scope,
            world_ref,
            folder_ref,
            thread_ref,
        )
        if ref and ref != "UNKNOWN"
    )
    forbidden_assumptions: tuple[str, ...] = (
        "natural language does not grant live authority",
        "do not execute send, submit, approval, workflow, browser, Coupa, model, agent, or provider calls",
    )

    if match_id in {"NEXT", "AMBIENT_GO_AHEAD", "COUPA_MISSING_INPUT", "WHAT_DO_YOU_NEED"}:
        missing_requirements = ("MISSING_PO_REFERENCE",)
        requested_action = "collect missing Coupa PO/reference as non-executing intake"
        referenced_next_action = session_state.latest_next_action or "Next: Type or attach the Coupa PO/reference."
    elif match_id == "SHOW_BLOCKING_STATUS":
        requested_action = "read current safe blocker status"
        referenced_next_action = session_state.latest_next_action or "Show the current blocker from safe read-model state."
    elif match_id == "CASSANDRA_PREP_EMAIL":
        requested_action = "prepare reviewable email draft language only"
        target_agent_role = "CASSANDRA"
        referenced_next_action = "Next: Prepare draft-only review posture; keep send locked."
        forbidden_assumptions = forbidden_assumptions + ("Cassandra can send email", "draft prep grants send authority")
    elif match_id == "NILES_X32":
        requested_action = "route X32 creative planning to Niles after source refs exist"
        target_agent_role = "NILES"
        missing_requirements = ("MISSING_X32_SOURCE_REF",)
        referenced_next_action = "Next: Attach the X32 source ref or identify the folder/thread."
        forbidden_assumptions = forbidden_assumptions + ("Niles can mutate DAW or mixer files",)
    elif match_id == "MAKE_VIDEO":
        requested_action = "compile safe visual event package; do not call a video provider"
        confidence = "MEDIUM"
        referenced_next_action = "Next: Use the safe visual event package only."
        forbidden_assumptions = forbidden_assumptions + ("video provider can be called", "generated video exists")
    elif match_id == "PROMPT_INJECTION_MARK_SENT":
        requested_action = "ignore gates and mark invoice sent"
        target_agent_role = "GUARDIAN"
        referenced_next_action = "Next: Provide exact approval and proof receipts before any future send or submit lane."
        forbidden_assumptions = forbidden_assumptions + ("ignore gates", "completion can be claimed without receipt")
    else:
        requested_action = "ask for clarification"

    if match_id == "AMBIENT_GO_AHEAD" and _ambient_go_ahead_needs_authority(session_state):
        requested_action = "generic go ahead attempts send or submit without exact approval"
        missing_requirements = ("MISSING_APPROVAL",)
    if workflow_ref in {"", "UNKNOWN", "unknown"}:
        workflow_ref = "unknown"
        ambiguity = "AMBIGUOUS"
        confidence = "LOW"
        required_clarification = "Which workflow or thread should OpenClaw continue?"
        forbidden_assumptions = forbidden_assumptions + ("single active workflow exists",)
    if session_state.ambiguity_status and match_id in {"NEXT", "AMBIENT_GO_AHEAD", "WHAT_DO_YOU_NEED"}:
        ambiguity = "AMBIGUOUS"
        confidence = "LOW"
        required_clarification = "Which workflow or thread should OpenClaw continue?"

    return MachineIntentCandidate(
        intent_id=_stable_id("intent_candidate", source_request_id, match_id, operator_text, workflow_ref),
        source_request_id=source_request_id,
        original_operator_text=operator_text,
        inferred_intent_type=intent_type,
        target_world_ref=world_ref,
        target_folder_ref=folder_ref,
        target_thread_ref=thread_ref,
        target_workflow_ref=workflow_ref,
        target_agent_role=target_agent_role,
        target_worker_type=target_worker_type,
        requested_action=requested_action,
        referenced_next_action=referenced_next_action,
        confidence=confidence,
        ambiguity_status=ambiguity,
        required_clarification=required_clarification,
        evidence_refs_used=evidence_refs,
        context_refs_used=context_refs,
        source_refs_used=(),
        missing_requirements=missing_requirements,
        forbidden_assumptions=forbidden_assumptions,
        authority_requested=_authority_requested_for(match_id, session_state),
        authority_granted=_authority_false(),
        validation_required=True,
        next_safe_move=required_clarification or referenced_next_action or "Validate the candidate before any response.",
    )


def _record_ids(records: list[Mapping[str, Any]], field: str = "capability_id") -> tuple[str, ...]:
    return tuple(str(record.get(field) or record.get("binding_id") or record.get("proposal_id") or "") for record in records if record)


def _primary_capability_id(candidate: MachineIntentCandidate, match_id: str) -> str:
    if match_id in {"NEXT", "AMBIENT_GO_AHEAD", "COUPA_MISSING_INPUT", "WHAT_DO_YOU_NEED"}:
        return "file_metadata_intake"
    if candidate.inferred_intent_type == "ANSWER_STATUS":
        return "status_readback"
    if candidate.inferred_intent_type == "PREPARE_DRAFT":
        return "outbound_message_draft"
    if candidate.inferred_intent_type == "ROUTE_TO_AGENT":
        return "worker_routing"
    if candidate.inferred_intent_type == "SHOW_VISUAL_WORKSPACE":
        return "visual_event_compilation"
    if candidate.inferred_intent_type == "REQUEST_APPROVAL":
        return "outbound_message_send_gate"
    return "machine_intent_validation"


def _capability_query_trace(
    query: openclaw_capability_index.CapabilityIndexQuery,
    candidate: MachineIntentCandidate,
    match_id: str,
    state: session_state_resolver.ActiveSessionState,
) -> dict[str, Any]:
    tenant_scope = state.tenant_scope
    if match_id == "NILES_X32":
        tenant_scope = "tenant_scope:fixture_creative_project"
    intent_records = query.find_by_intent_type(candidate.inferred_intent_type, tenant_scope=tenant_scope)
    task_records = query.find_by_task_type(_task_type_for(match_id), tenant_scope=tenant_scope)
    workflow_bindings = query.get_workflow_bindings(tenant_scope, candidate.target_workflow_ref)
    primary_capability_id = _primary_capability_id(candidate, match_id)
    provided_inputs: dict[str, Any] = {}
    if match_id in {"NEXT", "AMBIENT_GO_AHEAD", "COUPA_MISSING_INPUT", "WHAT_DO_YOU_NEED"}:
        provided_inputs = {"safe_response_ref": state.latest_response_ref}
    missing_inputs = query.find_missing_requirements(primary_capability_id, provided_inputs)
    authority_result = query.validate_authority_profile(primary_capability_id, candidate.authority_requested)

    records_for_rejection: list[Mapping[str, Any]] = list(intent_records) + list(task_records) + list(workflow_bindings)
    if match_id == "MAKE_VIDEO":
        records_for_rejection.append(
            {
                "capability_id": "live_visual_video_generation_provider",
                "capability_status": "FUTURE_GATED",
                "lifecycle_status": "FUTURE_GATED",
            }
        )
    if match_id == "PROMPT_INJECTION_MARK_SENT":
        records_for_rejection.extend(query.payload.get("proposal_candidates", ())[:1])
    usable, rejected = query.reject_unusable_capabilities(records_for_rejection)

    return {
        "query_api": "CapabilityIndexQuery",
        "capability_index_used": True,
        "tenant_scope": tenant_scope,
        "workflow_ref": candidate.target_workflow_ref,
        "intent_type": candidate.inferred_intent_type,
        "task_type": _task_type_for(match_id),
        "intent_lookup_ids": _record_ids(intent_records),
        "task_lookup_ids": _record_ids(task_records),
        "workflow_binding_ids": _record_ids(workflow_bindings, field="binding_id"),
        "primary_capability_id": primary_capability_id,
        "missing_inputs": tuple(dict(item) for item in missing_inputs),
        "authority_validation": authority_result,
        "usable_capability_ids": _record_ids(usable),
        "rejected_capability_ids": tuple(str(item.get("record_id") or "") for item in rejected),
        "rejected_capabilities": tuple(rejected),
        "fixture_only_generic_returned": False,
        "proposed_candidate_returned_as_usable": False,
        "query_mutated_index": False,
    }


def _authority_scout() -> dict[str, Any]:
    return {
        "duplicated_authority_risk": True,
        "duplicated_authority_boundary_sources": (
            "openclaw_request_processor.AUTHORITY_BOUNDARY",
            "openclaw_request_response_service.AUTHORITY_BOUNDARY",
            "openclaw_capability_index.AUTHORITY_BOUNDARY",
            "machine_intent_candidate_validator.AUTHORITY_BOUNDARY",
            "session_state_resolver.AUTHORITY_BOUNDARY",
            "deterministic_intent_interpreter.AUTHORITY_BOUNDARY",
        ),
        "recommendation": "Add a canonical AuthorityBoundary helper in a later lane; do not centralize behavior here.",
        "behavior_changed": False,
    }


def _machine_proof(*, matched: bool) -> dict[str, Any]:
    return {
        "deterministic_intent_interpreter_enabled": True,
        "matched_safe_fixture_phrase": matched,
        "session_resolver_used": True,
        "capability_query_used": matched,
        "validator_used": matched,
        "live_lm_interpreter_called": False,
        "model_call_performed": False,
        "agent_dispatch_performed": False,
        "worker_dispatch_performed": False,
        "workflow_run_performed": False,
        "external_action_performed": False,
        "send_submit_performed": False,
        "approval_execution_performed": False,
        "candidate_promotion_performed": False,
        "registry_mutation_performed": False,
        "credential_handling_performed": False,
        "raw_body_ingestion_performed": False,
        "browser_or_coupa_access_performed": False,
        "email_send_performed": False,
        "visual_provider_call_performed": False,
        "network_used": False,
        "mission_control_swift_changed": False,
        "mac_sync_import_run": False,
        "git_push_pull_fetch_run": False,
        "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "content_hash": "",
    }


def _status_tone(validation_verdict: str) -> str:
    if validation_verdict == "VALIDATED_INTENT":
        return "needs_input"
    if validation_verdict in {"CLARIFICATION_REQUIRED", "CONTEXT_GAP_CREATED", "BUILD_CUE_CREATED"}:
        return "clarify"
    return "blocked"


def _plan(
    *,
    match_id: str,
    candidate: MachineIntentCandidate,
    validation_verdict: str,
    headline: str,
    one_line_answer: str,
    eliwinship: str,
    primary_status: str,
    primary_blocker: str,
    next_action: str,
    missing_items_short: tuple[str, ...] = (),
    detail_summary: str,
    operator_headline: str,
    operator_message: str,
    why_it_happened: str,
    how_to_fix: str,
    response_author: str = "CHIEF",
    visual_event_package_requested: bool = False,
    internal_status: str | None = None,
) -> InterpreterResponsePlan:
    status = internal_status or ("RESPONSE_READY" if validation_verdict == "VALIDATED_INTENT" else "BLOCKED_WITH_REASON")
    return InterpreterResponsePlan(
        response_plan_id=_stable_id("interpreter_response_plan", candidate.intent_id, validation_verdict, headline),
        internal_status=status,
        headline=headline,
        one_line_answer=one_line_answer,
        eliwinship=eliwinship,
        primary_status=primary_status,
        primary_blocker=primary_blocker,
        next_action=next_action,
        missing_items_short=missing_items_short,
        detail_summary=detail_summary,
        operator_headline=operator_headline,
        operator_message=operator_message,
        what_happened=(
            "PC matched the operator text with the deterministic intent interpreter.",
            "PC resolved session state from safe generated read-models.",
            "PC queried the portable capability index and validated a MachineIntentCandidate.",
            "No model, agent, worker, workflow, browser, Coupa, email, approval, send, submit, provider, or external action ran.",
        ),
        why_it_happened=why_it_happened,
        how_to_fix=how_to_fix,
        visible_cards=(
            {
                "title": headline,
                "bullets": (
                    one_line_answer,
                    f"Validation: {validation_verdict}",
                    f"Next: {next_action.removeprefix('Next: ').strip()}",
                ),
                "status_tone": _status_tone(validation_verdict),
            },
        ),
        response_author=response_author,
        visual_event_package_requested=visual_event_package_requested,
        next_safe_move=next_action,
    )


def _response_plan_for(
    *,
    match_id: str,
    candidate: MachineIntentCandidate,
    validation_result: intent_validator.IntentValidationResult,
    missing_requirements: tuple[intent_validator.MissingRequirementCandidate, ...],
    build_cues: tuple[intent_validator.BuildCueCandidate, ...],
    context_gaps: tuple[intent_validator.ContextGapCandidate, ...],
    blockers: tuple[intent_validator.IntentValidationBlocker, ...],
    session_state: session_state_resolver.ActiveSessionState,
    query_trace: Mapping[str, Any],
) -> InterpreterResponsePlan:
    verdict = validation_result.verdict
    blocker = session_state.latest_primary_blocker or "Missing confirmed Coupa PO/reference"
    if verdict == "CLARIFICATION_REQUIRED":
        question = validation_result.clarification_question or "Which workflow or thread should OpenClaw continue?"
        return _plan(
            match_id=match_id,
            candidate=candidate,
            validation_verdict=verdict,
            headline="Which workflow continues?",
            one_line_answer="I need the target workflow or thread before continuing.",
            eliwinship="I do not have one clear active workflow. Pick the workflow or thread, and I will continue from safe read-model state only.",
            primary_status="Clarification needed",
            primary_blocker="No clear active workflow",
            next_action="Next: Name the workflow or thread.",
            missing_items_short=("Workflow or thread",),
            detail_summary=question,
            operator_headline="Which workflow should continue?",
            operator_message="I cannot safely treat this as the next step until the active workflow or thread is clear.",
            why_it_happened=question,
            how_to_fix="Name the workflow, thread, or world to continue. No workflow was guessed.",
            response_author="CHIEF",
        )

    if verdict == "BLOCKED_BY_AUTHORITY":
        reason = "; ".join(validation_result.blocked_reasons) or "Live authority is false."
        return _plan(
            match_id=match_id,
            candidate=candidate,
            validation_verdict=verdict,
            headline="Authority gate blocked",
            one_line_answer="I cannot mark completion, send, submit, or bypass gates from this wording.",
            eliwinship="Blocked. That wording tries to bypass proof or live-action gates. I will not claim completion, send, submit, or mark anything done.",
            primary_status="Blocked by authority",
            primary_blocker="Exact approval and proof receipts missing",
            next_action="Next: Provide exact proof refs.",
            missing_items_short=("Exact approval receipt", "Proof refs"),
            detail_summary=reason,
            operator_headline="Authority gate blocked",
            operator_message="The deterministic validator blocked this request before any action. No send, submit, approval, completion label, or external system was touched.",
            why_it_happened=reason,
            how_to_fix="Provide exact approval and proof refs for a future governed lane, or reframe this as a read-only status/intake request.",
            response_author="GUARDIAN",
        )

    if verdict in {"BLOCKED_BY_MISSING_CAPABILITY", "BUILD_CUE_CREATED"}:
        missing = tuple(validation_result.missing_capabilities) or tuple(cue.missing_capability for cue in build_cues)
        return _plan(
            match_id=match_id,
            candidate=candidate,
            validation_verdict=verdict,
            headline="Capability gap found",
            one_line_answer="The safe readback exists, but the requested live capability is not usable.",
            eliwinship="I can only return a gap/build-cue posture here. The missing or quarantined capability is not usable for live action.",
            primary_status="Build cue only",
            primary_blocker=", ".join(missing[:2]) if missing else "Missing capability",
            next_action="Next: Review the build cue.",
            missing_items_short=tuple(str(item) for item in missing[:3]),
            detail_summary="; ".join(validation_result.blocked_reasons) or "Capability lookup rejected the live capability.",
            operator_headline="Capability gap found",
            operator_message="The request was validated into a gap/build-cue posture only. Nothing was executed or promoted.",
            why_it_happened="Capability lookup and validation did not find a usable live capability.",
            how_to_fix="Add the missing deterministic capability in a later lane, then validate it before use.",
            response_author="GUARDIAN",
        )

    if verdict == "CONTEXT_GAP_CREATED" or context_gaps:
        gap = context_gaps[0] if context_gaps else None
        return _plan(
            match_id=match_id,
            candidate=candidate,
            validation_verdict=verdict,
            headline="X32 source needed",
            one_line_answer="Niles needs a source ref before this can be routed safely.",
            eliwinship="I can frame the X32 work for Niles, but I need a safe source ref first. No show file, DAW, or folder was changed.",
            primary_status="Context gap",
            primary_blocker="Missing X32 source ref",
            next_action="Next: Attach the X32 source ref.",
            missing_items_short=("X32 source ref",),
            detail_summary=gap.gap_summary if gap else "Niles/X32 context is missing a source ref.",
            operator_headline="X32 source ref needed",
            operator_message="Niles is the agent role for this context, but the live worker was not dispatched and no files were mutated.",
            why_it_happened=gap.gap_summary if gap else "The validator requires a source ref before Niles/X32 routing.",
            how_to_fix=gap.suggested_resolution if gap else "Attach the X32 source ref or identify the right folder/thread.",
            response_author="NILES",
        )

    if match_id == "SHOW_BLOCKING_STATUS":
        return _plan(
            match_id=match_id,
            candidate=candidate,
            validation_verdict=verdict,
            headline="Capital Hilton is blocked",
            one_line_answer=blocker,
            eliwinship="The current safe state says the Capital Hilton invoice is blocked by the missing Coupa PO/reference. Nothing was opened or submitted.",
            primary_status="Blocked on missing input",
            primary_blocker=blocker,
            next_action=session_state.latest_next_action or "Next: Confirm the Coupa PO/reference.",
            missing_items_short=tuple(session_state.missing_items[:3]) or ("Confirmed Coupa PO/reference",),
            detail_summary=session_state.latest_headline or "Current blocker read from safe session state.",
            operator_headline="Current blocker readback",
            operator_message="I read the current blocker from safe generated read-model state only.",
            why_it_happened="The operator asked for the current blocker, and validation allowed a read-only status response.",
            how_to_fix="Provide the Coupa PO/reference or a metadata-only source ref that proves it.",
            response_author="CHIEF",
        )

    if match_id == "CASSANDRA_PREP_EMAIL":
        draft_binding = "binding:fixture:capital_hilton:outbound_message" in query_trace.get("workflow_binding_ids", ())
        return _plan(
            match_id=match_id,
            candidate=candidate,
            validation_verdict=verdict,
            headline="Draft prep only",
            one_line_answer="Cassandra can be framed for draft review, but no send authority exists.",
            eliwinship="I can prepare this as draft-only posture for Cassandra. No email was drafted by a live worker, and no send authority exists.",
            primary_status="Draft route validated",
            primary_blocker="Live worker dispatch unavailable" if not draft_binding else "Send authority remains false",
            next_action="Next: Review draft-only requirements.",
            missing_items_short=("Send authority excluded",),
            detail_summary="Workflow draft binding present." if draft_binding else "Generic draft capability exists; workflow wrapper may need a build cue.",
            operator_headline="Cassandra draft prep is gated",
            operator_message="The interpreter produced a Cassandra draft candidate and validation kept it readback-only. No live Cassandra dispatch or email send occurred.",
            why_it_happened="The request matched draft-prep language, and the capability index supports draft/readback only.",
            how_to_fix="Use a future draft-wrapper lane for actual draft artifact creation; exact send approval would still be separate.",
            response_author="CASSANDRA",
        )

    if match_id == "MAKE_VIDEO":
        missing_provider = "live_visual_video_generation_provider" in validation_result.missing_capabilities or any(
            "live_visual_video_generation_provider" in str(item) for item in query_trace.get("rejected_capability_ids", ())
        )
        return _plan(
            match_id=match_id,
            candidate=candidate,
            validation_verdict=verdict,
            headline="Visual package only",
            one_line_answer="A safe visual event package can be shaped; live video generation is blocked.",
            eliwinship="I can return a safe visual event package for the current state. Live video or image generation is not available here.",
            primary_status="Safe visual readback",
            primary_blocker="Live video provider missing" if missing_provider else "No live provider authority",
            next_action="Next: Review the visual package.",
            missing_items_short=("Live video provider",),
            detail_summary="Capability query returned visual_event_compilation; live video provider is missing or rejected.",
            operator_headline="Safe visual package only",
            operator_message="The interpreter produced a visual workspace candidate and kept it to a local truth-backed package. No provider was called.",
            why_it_happened="The capability index supports visual event compilation, not live video generation.",
            how_to_fix="Use the safe visual package, or add a future-gated provider capability in a later lane.",
            response_author="CHIEF",
            visual_event_package_requested=True,
            internal_status="RESPONSE_READY",
        )

    return _plan(
        match_id=match_id,
        candidate=candidate,
        validation_verdict=verdict,
        headline="Coupa reference needed",
        one_line_answer="I need the Coupa PO/reference or source proof before anything can move.",
        eliwinship=VALIDATED_INTAKE_ELIWINSHIP,
        primary_status="Waiting on missing input",
        primary_blocker=blocker,
        next_action="Next: Type or attach the Coupa PO/reference.",
        missing_items_short=("Confirmed Coupa PO/reference",),
        detail_summary="Latest terminal response says the Capital Hilton invoice is blocked by a missing Coupa PO/reference.",
        operator_headline="Coupa reference needed",
        operator_message="I can continue only by collecting the missing Coupa PO/reference or a safe source ref. No Coupa access, browser use, submit, send, or approval execution occurred.",
        why_it_happened="The latest safe session state names the Coupa PO/reference as the current blocker, and validation allowed non-executing input capture.",
        how_to_fix="Type the Coupa PO/reference or attach a metadata-only source file that proves it.",
        response_author="CHIEF",
        internal_status="RESPONSE_READY",
    )


def build_payload_from_interpretation(
    interpretation: DeterministicIntentInterpretation,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "interpreter": asdict(default_interpreter()),
        "model_schemas": {
            "InterpreterResponsePlan": tuple(field.name for field in fields(InterpreterResponsePlan)),
            "DeterministicIntentInterpretation": tuple(field.name for field in fields(DeterministicIntentInterpretation)),
            "DeterministicIntentInterpreter": tuple(field.name for field in fields(DeterministicIntentInterpreter)),
        },
        "interpretation": _interpretation_payload(interpretation),
        "authority_scout": interpretation.authority_scout,
        "machine_proof": dict(interpretation.machine_proof),
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def _interpretation_payload(interpretation: DeterministicIntentInterpretation) -> dict[str, Any]:
    payload = asdict(interpretation)
    if interpretation.candidate is not None:
        payload["candidate"] = asdict(interpretation.candidate)
    if interpretation.response_plan is not None:
        payload["response_plan"] = asdict(interpretation.response_plan)
    return payload


def format_operator_markdown(payload: Mapping[str, Any]) -> str:
    interpretation = payload["interpretation"]
    response_plan = interpretation.get("response_plan") or {}
    validation = interpretation.get("validation_result") or {}
    lines = [
        "# Deterministic Intent Interpreter",
        "",
        f"Status: {payload['contract_status']}",
        f"Matched: {interpretation.get('matched')}",
        f"Match: {interpretation.get('match_id')}",
        f"Intent: {(interpretation.get('candidate') or {}).get('inferred_intent_type', 'UNKNOWN')}",
        f"Validation: {validation.get('verdict', 'UNKNOWN')}",
        f"Headline: {response_plan.get('headline', 'UNKNOWN')}",
        f"Next action: {response_plan.get('next_action', 'UNKNOWN')}",
        "",
        "## Boundary",
        "- No live LM interpretation.",
        "- No model call, agent dispatch, worker dispatch, workflow run, external action, send/submit, approval execution, provider call, credential handling, or raw-body ingestion.",
        "- Capability proposals remain candidate-only.",
        "",
        "## Authority Scout",
        "- Authority boundary schemas are duplicated.",
        "- Recommendation: add a canonical AuthorityBoundary helper later.",
        "- Behavior changed: no.",
        "",
    ]
    return "\n".join(lines)


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: Mapping[str, Any], paths: tuple[Path, Path]) -> dict[str, Any]:
    interpretation = payload["interpretation"]
    validation = interpretation.get("validation_result") or {}
    response_plan = interpretation.get("response_plan") or {}
    query = interpretation.get("capability_query_trace") or {}
    return {
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": paths[0].as_posix(),
        "operator_path": paths[1].as_posix(),
        "matched": interpretation["matched"],
        "match_id": interpretation["match_id"],
        "intent_type": (interpretation.get("candidate") or {}).get("inferred_intent_type", "UNKNOWN"),
        "validation_verdict": validation.get("verdict", "UNKNOWN"),
        "headline": response_plan.get("headline", ""),
        "next_action": response_plan.get("next_action", ""),
        "session_resolver_used": payload["machine_proof"]["session_resolver_used"],
        "capability_query_used": payload["machine_proof"]["capability_query_used"],
        "validator_used": payload["machine_proof"]["validator_used"],
        "workflow_bindings": query.get("workflow_binding_ids", ()),
        "rejected_capabilities": query.get("rejected_capability_ids", ()),
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def build_payload(
    *,
    operator_text: str = "next",
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> dict[str, Any]:
    raw_request = {
        "request_id": f"deterministic_intent_export_{_short_hash(operator_text)}",
        "workflow_ref": "",
        "operator_message": operator_text,
        "sanitized_message_summary": operator_text,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "created_at": generated_at,
    }
    interpretation = interpret_request(raw_request, export_root=export_root, generated_at=generated_at)
    return build_payload_from_interpretation(interpretation, generated_at=generated_at)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the deterministic OpenClaw intent interpreter read-model.")
    parser.add_argument("--format", choices=("json", "summary"), default="json")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--operator-text", default="next")
    args = parser.parse_args(argv)

    export_root = Path(args.export_root)
    payload = build_payload(operator_text=args.operator_text, export_root=export_root, generated_at=args.generated_at)
    paths = write_exports(payload, export_root)
    output: Mapping[str, Any] = payload if args.format == "json" else build_summary(payload, paths)
    sys.stdout.write(stable_json(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
