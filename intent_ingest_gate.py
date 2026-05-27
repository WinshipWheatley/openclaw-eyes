"""Intent ingest gate v0.

Gate 2 in the OpenClaw chain receives an LM1-proposed MachineIntentCandidate
shape and decides whether OpenClaw may ingest it as a real bounded internal
intent. It validates schema, source/scope, capability, context, confidence, and
authority without calling models or executing the intent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import lm_intent_proposal_contract
import machine_intent_candidate_validator as intent_validator
import openclaw_capability_index
from machine_intent_candidate_validator import MachineIntentCandidate


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "intent_ingest_gate_v0"
READ_MODEL_ID = "intent_ingest_gate"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_INTENT_INGEST_GATE_NO_EXECUTION"
GATE_ID = "gate_2:intent_ingest"

ACCEPTED_INTENT = "ACCEPTED_INTENT"
NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
NEEDS_CONTEXT = "NEEDS_CONTEXT"
BLOCKED_AUTHORITY = "BLOCKED_AUTHORITY"
UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
LOW_CONFIDENCE = "LOW_CONFIDENCE"
PARKED_FOR_REVIEW = "PARKED_FOR_REVIEW"

OUTCOMES = (
    ACCEPTED_INTENT,
    NEEDS_CLARIFICATION,
    NEEDS_CONTEXT,
    BLOCKED_AUTHORITY,
    UNSUPPORTED_CAPABILITY,
    LOW_CONFIDENCE,
    PARKED_FOR_REVIEW,
)

AUTHORITY_BOUNDARY = {
    "live_lm_ingest_allowed": False,
    "live_model_call_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_worker_dispatch_allowed": False,
    "live_workflow_execution_allowed": False,
    "live_external_action_allowed": False,
    "live_send_submit_allowed": False,
    "live_approval_execution_allowed": False,
    "live_candidate_promotion_allowed": False,
    "live_tool_execution_allowed": False,
    "live_file_body_read_allowed": False,
    "live_workbook_body_read_allowed": False,
    "live_spreadsheet_cell_read_allowed": False,
    "live_file_mutation_allowed": False,
    "live_pdf_generation_allowed": False,
    "live_browser_allowed": False,
    "live_coupa_access_allowed": False,
    "live_email_send_allowed": False,
    "live_ledger_posting_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
}

LIVE_AUTHORITY_TERMS = (
    "send",
    "submit",
    "email send",
    "gmail send",
    "coupa",
    "browser",
    "post ledger",
    "ledger post",
    "ledger-post",
    "mark paid",
    "mark it paid",
    "mark sent",
    "mark it sent",
    "finalize",
    "print to pdf",
    "generate pdf",
)

PHYSICAL_DELETE_TERMS = (
    "delete from disk",
    "remove from disk",
    "trash the file",
    "physically delete",
    "unlink file",
    "erase file",
)

CLIENT_ALIASES = {
    "capital_hilton": ("capital_hilton", "capital hilton", "capitol hilton"),
    "st_annes": ("st_annes", "st anne", "st. anne", "st anne's", "st. anne's"),
    "live_arts_md": ("live_arts_md", "live arts md", "live arts"),
}


@dataclass(frozen=True)
class IntentIngestInput:
    ingest_input_id: str
    source_request_id: str
    source_request_filename: str
    proposal_package_ref: str
    device_ref: str
    thread_ref: str
    tenant_scope: str
    world_ref: str
    client_ref: str
    project_ref: str
    workflow_ref: str
    candidate: dict[str, Any]
    capability_index_ref: str
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class AcceptedMachineIntent:
    accepted_intent_id: str
    source_request_id: str
    source_candidate_ref: str
    intent_type: str
    safe_action_type: str
    requested_action: str
    target_agent_role: str
    target_worker_type: str
    world_ref: str
    client_ref: str
    project_ref: str
    workflow_ref: str
    confidence: str
    evidence_refs_used: tuple[str, ...]
    context_refs_used: tuple[str, ...]
    source_refs_used: tuple[str, ...]
    capability_refs: tuple[str, ...]
    authority_granted: dict[str, bool]
    validation_result_ref: str
    next_safe_move: str


@dataclass(frozen=True)
class IntentClarificationRequest:
    clarification_id: str
    source_request_id: str
    source_candidate_ref: str
    question: str
    reason: str
    missing_items: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class IntentAuthorityBlock:
    authority_block_id: str
    source_request_id: str
    source_candidate_ref: str
    blocked_authority: tuple[str, ...]
    blocker_reasons: tuple[str, ...]
    authority_granted: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class IntentContextRequirement:
    context_requirement_id: str
    source_request_id: str
    source_candidate_ref: str
    requirement_type: str
    requirement_label: str
    next_safe_move: str


@dataclass(frozen=True)
class IntentIngestTrace:
    trace_id: str
    source_request_id: str
    proposal_package_ref: str
    validator_ref: str
    capability_index_ref: str
    schema_validated: bool
    source_scope_checked: bool
    tenant_scope_checked: bool
    workflow_scope_checked: bool
    capability_checked: bool
    authority_checked: bool
    context_checked: bool
    blocked_reasons: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class IntentIngestResult:
    ingest_result_id: str
    gate_id: str
    outcome: str
    source_request_id: str
    source_candidate_ref: str
    validation_verdict: str
    accepted_intent: dict[str, Any] | None
    clarification_request: dict[str, Any] | None
    authority_block: dict[str, Any] | None
    context_requirements: tuple[dict[str, Any], ...]
    matched_capabilities: tuple[str, ...]
    missing_capabilities: tuple[str, ...]
    rejected_capabilities: tuple[str, ...]
    missing_items: tuple[str, ...]
    blocker_reasons: tuple[str, ...]
    trace: dict[str, Any]
    authority_boundary: dict[str, bool]
    next_safe_move: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _as_candidate(proposal: Mapping[str, Any] | MachineIntentCandidate) -> tuple[MachineIntentCandidate | None, tuple[str, ...]]:
    if isinstance(proposal, MachineIntentCandidate):
        return proposal, ()
    field_names = tuple(field.name for field in fields(MachineIntentCandidate))
    missing = tuple(name for name in field_names if name not in proposal)
    if missing:
        return None, tuple(f"MISSING_FIELD:{name}" for name in missing)
    tuple_fields = {
        "evidence_refs_used",
        "context_refs_used",
        "source_refs_used",
        "missing_requirements",
        "forbidden_assumptions",
    }
    values: dict[str, Any] = {}
    for name in field_names:
        value = proposal[name]
        if name in tuple_fields:
            values[name] = tuple(str(item) for item in (value or ()))
        elif name in {"authority_requested", "authority_granted"}:
            values[name] = {str(key): bool(flag) for key, flag in dict(value or {}).items()}
        elif name == "validation_required":
            values[name] = bool(value)
        else:
            values[name] = str(value)
    return MachineIntentCandidate(**values), ()


def _proposal_package(package_payload: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(package_payload, Mapping):
        return {}
    package = package_payload.get("proposal_package")
    if isinstance(package, Mapping):
        return package
    return package_payload


def _norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _unknown(value: object) -> bool:
    return _norm(value) in {"", "unknown", "unknown_fail_closed", "none", "null"}


def _client_from_text(*parts: object) -> str:
    text = " ".join(str(part or "") for part in parts).lower()
    for client_ref, aliases in CLIENT_ALIASES.items():
        if any(alias in text for alias in aliases):
            return client_ref
    return ""


def _package_client(package: Mapping[str, Any]) -> str:
    return _norm(package.get("client_ref") or "")


def _candidate_client(candidate: MachineIntentCandidate) -> str:
    return _client_from_text(
        candidate.target_folder_ref,
        candidate.target_workflow_ref,
        candidate.original_operator_text,
        " ".join(candidate.context_refs_used),
        " ".join(candidate.source_refs_used),
    )


def _workflow_matches(package_workflow: object, candidate_workflow: object) -> bool:
    package = _norm(package_workflow)
    candidate = _norm(candidate_workflow)
    if not package or not candidate or package == "unknown" or candidate == "unknown":
        return True
    return package == candidate or package in candidate or candidate in package


def _authority_terms(candidate: MachineIntentCandidate) -> tuple[str, ...]:
    text = " ".join((candidate.original_operator_text, candidate.requested_action)).lower()
    hits = [term for term in LIVE_AUTHORITY_TERMS if term in text]
    if "email" in text and not any(term in text for term in ("draft", "prep", "prepare", "review", "wording")):
        hits.append("email")
    if _safe_openclaw_reference_supersession(candidate):
        hits = [term for term in hits if term not in {"finalize"}]
    return tuple(dict.fromkeys(hits))


def _physical_delete_terms(candidate: MachineIntentCandidate) -> tuple[str, ...]:
    text = " ".join((candidate.original_operator_text, candidate.requested_action)).lower()
    return tuple(term for term in PHYSICAL_DELETE_TERMS if term in text)


def _safe_openclaw_reference_supersession(candidate: MachineIntentCandidate) -> bool:
    text = " ".join((candidate.original_operator_text, candidate.requested_action)).lower()
    has_delete_language = any(term in text for term in ("delete the other", "remove the other", "retire the other"))
    has_openclaw_scope = "from openclaw" in text or "in openclaw" in text or "active workflow" in text
    has_artifact_context = any(term in text for term in ("workbook", "file", "artifact", "newest", "just gave you", "current"))
    has_source_context = bool(candidate.source_refs_used or candidate.context_refs_used or candidate.target_workflow_ref not in {"", "unknown"})
    return has_delete_language and has_openclaw_scope and has_artifact_context and has_source_context


def _safe_action_type(candidate: MachineIntentCandidate) -> str:
    if _safe_openclaw_reference_supersession(candidate):
        return "SUPERSEDE_ACTIVE_REFERENCE_NOT_PHYSICAL_DELETE"
    if candidate.inferred_intent_type == "ANSWER_STATUS":
        return "ANSWER_STATUS_READBACK"
    if candidate.inferred_intent_type == "PREPARE_DRAFT":
        return "PREPARE_DRAFT_PACKAGE_ONLY"
    if candidate.inferred_intent_type in {"CAPTURE_MISSING_INPUT", "ATTACH_SOURCE_REF"}:
        return "CAPTURE_OR_ATTACH_SOURCE_REF"
    if candidate.inferred_intent_type == "SHOW_VISUAL_WORKSPACE":
        return "SHOW_LOCAL_VISUAL_WORKSPACE_PACKAGE"
    return candidate.inferred_intent_type


def _requested_live_authority(candidate: MachineIntentCandidate) -> tuple[str, ...]:
    requested = tuple(key for key, value in candidate.authority_requested.items() if bool(value))
    granted = tuple(key for key, value in candidate.authority_granted.items() if bool(value))
    terms = _authority_terms(candidate)
    physical_delete = _physical_delete_terms(candidate)
    if _safe_openclaw_reference_supersession(candidate) and not physical_delete:
        terms = tuple(term for term in terms if "delete" not in term)
    return tuple(dict.fromkeys(requested + granted + terms + physical_delete))


def _context_requirements(
    candidate: MachineIntentCandidate | None,
    source_request_id: str,
    missing_items: tuple[str, ...],
) -> tuple[IntentContextRequirement, ...]:
    if candidate is None:
        return ()
    requirements = []
    for item in missing_items:
        requirements.append(
            IntentContextRequirement(
                context_requirement_id=f"intent_context_requirement:{_short_hash(source_request_id, candidate.intent_id, item)}",
                source_request_id=source_request_id,
                source_candidate_ref=candidate.intent_id,
                requirement_type=_norm(item).upper() or "MISSING_CONTEXT",
                requirement_label=str(item),
                next_safe_move="Collect the missing context through a governed local surface or clarification; do not execute.",
            )
        )
    return tuple(requirements)


def _all_false_authority() -> dict[str, bool]:
    return {
        "model_call": False,
        "agent_dispatch": False,
        "worker_dispatch": False,
        "workflow_execution": False,
        "tool_execution": False,
        "external_action": False,
        "send_submit": False,
        "approval_execution": False,
        "candidate_promotion": False,
        "file_body_read": False,
        "workbook_body_read": False,
        "spreadsheet_cell_read": False,
        "file_mutation": False,
        "pdf_generation": False,
        "ledger_posting": False,
        "credential_handling": False,
        "raw_body_ingestion": False,
    }


def _blocked_result(
    *,
    outcome: str,
    source_request_id: str,
    candidate_ref: str = "",
    validation_verdict: str = "UNKNOWN_FAIL_CLOSED",
    blocker_reasons: tuple[str, ...],
    missing_items: tuple[str, ...] = (),
    matched_capabilities: tuple[str, ...] = (),
    missing_capabilities: tuple[str, ...] = (),
    rejected_capabilities: tuple[str, ...] = (),
    package_ref: str = "",
    capability_index_ref: str = "openclaw_capability_index",
    authority_block: IntentAuthorityBlock | None = None,
    context_requirements: tuple[IntentContextRequirement, ...] = (),
    next_safe_move: str = "Return a clarification or blocked readback; do not execute.",
) -> IntentIngestResult:
    trace = IntentIngestTrace(
        trace_id=f"intent_ingest_trace:{_short_hash(source_request_id, candidate_ref, outcome)}",
        source_request_id=source_request_id,
        proposal_package_ref=package_ref,
        validator_ref=intent_validator.READ_MODEL_ID,
        capability_index_ref=capability_index_ref,
        schema_validated=not any(reason.startswith("MISSING_FIELD:") for reason in blocker_reasons),
        source_scope_checked=True,
        tenant_scope_checked=True,
        workflow_scope_checked=True,
        capability_checked=True,
        authority_checked=True,
        context_checked=True,
        blocked_reasons=blocker_reasons,
        next_safe_move=next_safe_move,
    )
    return IntentIngestResult(
        ingest_result_id=f"intent_ingest_result:{_short_hash(source_request_id, candidate_ref, outcome)}",
        gate_id=GATE_ID,
        outcome=outcome,
        source_request_id=source_request_id,
        source_candidate_ref=candidate_ref,
        validation_verdict=validation_verdict,
        accepted_intent=None,
        clarification_request=None,
        authority_block=asdict(authority_block) if authority_block else None,
        context_requirements=tuple(asdict(item) for item in context_requirements),
        matched_capabilities=matched_capabilities,
        missing_capabilities=missing_capabilities,
        rejected_capabilities=rejected_capabilities,
        missing_items=missing_items,
        blocker_reasons=blocker_reasons,
        trace=asdict(trace),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move=next_safe_move,
    )


def ingest_intent_proposal(
    proposal: Mapping[str, Any] | MachineIntentCandidate,
    *,
    package_payload: Mapping[str, Any] | None = None,
    capability_index_payload: Mapping[str, Any] | None = None,
    source_request_filename: str = "",
    capability_index_ref: str = "generated/read_models/openclaw_capability_index.json",
) -> dict[str, Any]:
    """Validate and ingest an LM1-proposed MachineIntentCandidate, without execution."""

    package = _proposal_package(package_payload)
    candidate, schema_errors = _as_candidate(proposal)
    package_ref = str(package.get("package_id") or package.get("proposal_package_ref") or "")
    candidate_ref = candidate.intent_id if candidate else ""
    source_request_id = (
        str(candidate.source_request_id).strip()
        if candidate and str(candidate.source_request_id).strip()
        else str(package.get("source_request_id") or "").strip()
    )
    if not source_request_id:
        source_request_id = "unknown_source_request"

    if schema_errors:
        result = _blocked_result(
            outcome=PARKED_FOR_REVIEW,
            source_request_id=source_request_id,
            candidate_ref=candidate_ref,
            blocker_reasons=schema_errors,
            package_ref=package_ref,
            capability_index_ref=capability_index_ref,
            next_safe_move="Ask LM1 for a complete MachineIntentCandidate shape; do not ingest or execute.",
        )
        return asdict(result)

    assert candidate is not None
    blocker_reasons: list[str] = []
    missing_items: list[str] = []

    if _unknown(candidate.source_request_id):
        blocker_reasons.append("MISSING_SOURCE_REQUEST_ID")
        missing_items.append("source_request_id")
    if package.get("source_request_id") and candidate.source_request_id != str(package.get("source_request_id")):
        blocker_reasons.append("SOURCE_REQUEST_SCOPE_MISMATCH")
    package_workflow = package.get("workflow_ref")
    if package_workflow and not _workflow_matches(package_workflow, candidate.target_workflow_ref):
        blocker_reasons.append("WORKFLOW_SCOPE_MISMATCH")
        missing_items.append("matching workflow_ref")
    package_client = _package_client(package)
    candidate_client = _candidate_client(candidate)
    if package_client and candidate_client and package_client != candidate_client:
        blocker_reasons.append("CROSS_CLIENT_SCOPE_MISMATCH")
        missing_items.append("matching client_ref")
    if candidate.inferred_intent_type not in intent_validator.INTENT_TYPES:
        blocker_reasons.append(f"UNSUPPORTED_INTENT_TYPE:{candidate.inferred_intent_type}")

    requested_authority = _requested_live_authority(candidate)
    authority_block: IntentAuthorityBlock | None = None
    if requested_authority:
        authority_block = IntentAuthorityBlock(
            authority_block_id=f"intent_authority_block:{_short_hash(candidate.intent_id, requested_authority)}",
            source_request_id=candidate.source_request_id,
            source_candidate_ref=candidate.intent_id,
            blocked_authority=requested_authority,
            blocker_reasons=tuple(f"BLOCKED_LIVE_AUTHORITY:{item}" for item in requested_authority),
            authority_granted=_all_false_authority(),
            next_safe_move="Reframe as a non-executing package/readback or collect exact approval receipts; do not execute.",
        )
        blocker_reasons.extend(authority_block.blocker_reasons)

    if blocker_reasons:
        context_requirements = _context_requirements(candidate, source_request_id, tuple(missing_items))
        outcome = (
            BLOCKED_AUTHORITY
            if authority_block
            else UNSUPPORTED_CAPABILITY
            if any(reason.startswith("UNSUPPORTED_INTENT_TYPE:") for reason in blocker_reasons)
            else NEEDS_CONTEXT
            if missing_items
            else PARKED_FOR_REVIEW
        )
        result = _blocked_result(
            outcome=outcome,
            source_request_id=source_request_id,
            candidate_ref=candidate.intent_id,
            blocker_reasons=tuple(blocker_reasons),
            missing_items=tuple(missing_items),
            missing_capabilities=(
                (f"capability_for:{candidate.inferred_intent_type}",)
                if any(reason.startswith("UNSUPPORTED_INTENT_TYPE:") for reason in blocker_reasons)
                else ()
            ),
            package_ref=package_ref,
            capability_index_ref=capability_index_ref,
            authority_block=authority_block,
            context_requirements=context_requirements,
            next_safe_move=(
                authority_block.next_safe_move
                if authority_block
                else "Resolve source/client/workflow scope before ingesting the intent; do not execute."
            ),
        )
        return asdict(result)

    validation_result, missing, build_cues, context_gaps, blockers = intent_validator.validate_machine_intent_candidate(
        candidate,
        capability_index_payload=dict(capability_index_payload or openclaw_capability_index.build_payload()),
    )
    validator_blockers = tuple(blocker.condition for blocker in blockers)
    missing_labels = tuple(item.requirement_label for item in missing) + tuple(gap.missing_context_type for gap in context_gaps)

    if candidate.confidence in {"LOW", "UNKNOWN_FAIL_CLOSED"}:
        outcome = LOW_CONFIDENCE
        next_safe_move = candidate.required_clarification or "Ask a concise clarification before ingesting."
    elif validation_result.verdict == "VALIDATED_INTENT":
        outcome = ACCEPTED_INTENT
        next_safe_move = validation_result.next_safe_move
    elif validation_result.verdict == "CLARIFICATION_REQUIRED":
        outcome = NEEDS_CLARIFICATION
        next_safe_move = validation_result.clarification_question or "Ask one clarification question."
    elif validation_result.verdict in {"BLOCKED_BY_MISSING_CONTEXT", "CONTEXT_GAP_CREATED"}:
        outcome = NEEDS_CONTEXT
        next_safe_move = validation_result.next_safe_move
    elif validation_result.verdict == "BLOCKED_BY_AUTHORITY":
        outcome = BLOCKED_AUTHORITY
        next_safe_move = validation_result.next_safe_move
    elif validation_result.verdict in {"BLOCKED_BY_MISSING_CAPABILITY", "BUILD_CUE_CREATED"}:
        outcome = UNSUPPORTED_CAPABILITY
        next_safe_move = validation_result.next_safe_move
    else:
        outcome = PARKED_FOR_REVIEW
        next_safe_move = "Park for review; do not execute."

    accepted: AcceptedMachineIntent | None = None
    clarification: IntentClarificationRequest | None = None
    context_requirements = _context_requirements(candidate, source_request_id, missing_labels)
    if outcome == ACCEPTED_INTENT:
        accepted = AcceptedMachineIntent(
            accepted_intent_id=f"accepted_intent:{_short_hash(candidate.intent_id, validation_result.validation_result_id)}",
            source_request_id=candidate.source_request_id,
            source_candidate_ref=candidate.intent_id,
            intent_type=validation_result.validated_intent_type,
            safe_action_type=_safe_action_type(candidate),
            requested_action=(
                "Supersede/retire the previous OpenClaw reference only; do not delete any file from disk."
                if _safe_openclaw_reference_supersession(candidate)
                else candidate.requested_action
            ),
            target_agent_role=candidate.target_agent_role,
            target_worker_type=candidate.target_worker_type,
            world_ref=candidate.target_world_ref,
            client_ref=package_client or candidate_client or "unknown",
            project_ref=str(package.get("project_ref") or ""),
            workflow_ref=validation_result.resolved_workflow_ref,
            confidence=candidate.confidence,
            evidence_refs_used=candidate.evidence_refs_used,
            context_refs_used=candidate.context_refs_used,
            source_refs_used=candidate.source_refs_used,
            capability_refs=validation_result.matched_capabilities,
            authority_granted=_all_false_authority(),
            validation_result_ref=validation_result.validation_result_id,
            next_safe_move=next_safe_move,
        )
    elif outcome == NEEDS_CLARIFICATION:
        clarification = IntentClarificationRequest(
            clarification_id=f"intent_clarification:{_short_hash(candidate.intent_id, validation_result.validation_result_id)}",
            source_request_id=candidate.source_request_id,
            source_candidate_ref=candidate.intent_id,
            question=validation_result.clarification_question or candidate.required_clarification or "What should OpenClaw use here?",
            reason="Candidate is ambiguous or missing one clear context binding.",
            missing_items=missing_labels,
            next_safe_move=next_safe_move,
        )
    elif outcome == BLOCKED_AUTHORITY:
        authority_block = IntentAuthorityBlock(
            authority_block_id=f"intent_authority_block:{_short_hash(candidate.intent_id, validation_result.validation_result_id)}",
            source_request_id=candidate.source_request_id,
            source_candidate_ref=candidate.intent_id,
            blocked_authority=tuple(dict.fromkeys(requested_authority + ("validator_authority_block",))),
            blocker_reasons=validator_blockers,
            authority_granted=_all_false_authority(),
            next_safe_move=next_safe_move,
        )

    trace = IntentIngestTrace(
        trace_id=f"intent_ingest_trace:{_short_hash(candidate.intent_id, validation_result.validation_result_id)}",
        source_request_id=candidate.source_request_id,
        proposal_package_ref=package_ref,
        validator_ref=intent_validator.READ_MODEL_ID,
        capability_index_ref=capability_index_ref,
        schema_validated=True,
        source_scope_checked=True,
        tenant_scope_checked=validation_result.tenant_scope_checked,
        workflow_scope_checked=validation_result.fixture_scope_checked,
        capability_checked=validation_result.capability_index_used,
        authority_checked=validation_result.authority_profile_checked,
        context_checked=True,
        blocked_reasons=validator_blockers,
        next_safe_move=next_safe_move,
    )
    result = IntentIngestResult(
        ingest_result_id=f"intent_ingest_result:{_short_hash(candidate.intent_id, outcome, validation_result.validation_result_id)}",
        gate_id=GATE_ID,
        outcome=outcome,
        source_request_id=candidate.source_request_id,
        source_candidate_ref=candidate.intent_id,
        validation_verdict=validation_result.verdict,
        accepted_intent=asdict(accepted) if accepted else None,
        clarification_request=asdict(clarification) if clarification else None,
        authority_block=asdict(authority_block) if authority_block else None,
        context_requirements=tuple(asdict(item) for item in context_requirements),
        matched_capabilities=validation_result.matched_capabilities,
        missing_capabilities=validation_result.missing_capabilities,
        rejected_capabilities=validation_result.rejected_capabilities,
        missing_items=missing_labels,
        blocker_reasons=validator_blockers,
        trace=asdict(trace),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move=next_safe_move,
    )
    return asdict(result)


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    package_payload = lm_intent_proposal_contract.build_payload(
        {
            "request_id": "intent_ingest_gate_fixture_status",
            "operator_message": "What is blocking Capital Hilton?",
            "world_ref": "finance",
            "client_ref": "capital_hilton",
            "workflow_ref": "capital_hilton_invoice_workflow",
        },
        generated_at=generated_at,
    )
    candidate = MachineIntentCandidate(
        intent_id="intent_ingest_gate_fixture_status_candidate",
        source_request_id="intent_ingest_gate_fixture_status",
        original_operator_text="What is blocking Capital Hilton?",
        inferred_intent_type="ANSWER_STATUS",
        target_world_ref="finance",
        target_folder_ref="capital_hilton",
        target_thread_ref="thread_ref:finance_capital_hilton",
        target_workflow_ref="capital_hilton_invoice_workflow",
        target_agent_role="CHIEF",
        target_worker_type="PC_CODEX",
        requested_action="Answer current status from safe read-models.",
        referenced_next_action="",
        confidence="HIGH",
        ambiguity_status="UNAMBIGUOUS",
        required_clarification="",
        evidence_refs_used=(),
        context_refs_used=("tenant_scope:fixture_business_ops",),
        source_refs_used=(),
        missing_requirements=(),
        forbidden_assumptions=(),
        authority_requested={"send_submit": False, "external_action": False},
        authority_granted={"send_submit": False, "external_action": False},
        validation_required=True,
        next_safe_move="Validate before ingesting.",
    )
    accepted_result = ingest_intent_proposal(candidate, package_payload=package_payload)
    blocked_candidate = MachineIntentCandidate(
        intent_id="intent_ingest_gate_fixture_blocked_send",
        source_request_id="intent_ingest_gate_fixture_status",
        original_operator_text="Send and post the invoice.",
        inferred_intent_type="REQUEST_APPROVAL",
        target_world_ref="finance",
        target_folder_ref="capital_hilton",
        target_thread_ref="thread_ref:finance_capital_hilton",
        target_workflow_ref="capital_hilton_invoice_workflow",
        target_agent_role="CHIEF",
        target_worker_type="PC_CODEX",
        requested_action="Send invoice and post ledger.",
        referenced_next_action="",
        confidence="HIGH",
        ambiguity_status="UNAMBIGUOUS",
        required_clarification="",
        evidence_refs_used=(),
        context_refs_used=("tenant_scope:fixture_business_ops",),
        source_refs_used=(),
        missing_requirements=(),
        forbidden_assumptions=(),
        authority_requested={"send_submit": False, "external_action": False},
        authority_granted={"send_submit": False, "external_action": False},
        validation_required=True,
        next_safe_move="Validate before ingesting.",
    )
    blocked_result = ingest_intent_proposal(blocked_candidate, package_payload=package_payload)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "outcomes": OUTCOMES,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "examples": {
            "accepted_status_intent": accepted_result,
            "blocked_send_submit_intent": blocked_result,
        },
        "machine_proof": {
            "gate_2_present": True,
            "lm1_proposal_schema_supported": True,
            "accepted_example_is_accepted": accepted_result["outcome"] == ACCEPTED_INTENT,
            "blocked_example_is_blocked": blocked_result["outcome"] == BLOCKED_AUTHORITY,
            "model_call_performed": False,
            "agent_dispatch_performed": False,
            "worker_dispatch_performed": False,
            "workflow_execution_performed": False,
            "tool_execution_performed": False,
            "external_action_performed": False,
            "send_submit_performed": False,
            "approval_execution_performed": False,
            "candidate_promotion_performed": False,
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": "",
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def write_exports(payload: Mapping[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    accepted = payload.get("examples", {}).get("accepted_status_intent", {})
    blocked = payload.get("examples", {}).get("blocked_send_submit_intent", {})
    lines = [
        "# Intent Ingest Gate",
        "",
        f"Status: {CONTRACT_STATUS}",
        f"Accepted example: {accepted.get('outcome', '')}",
        f"Blocked example: {blocked.get('outcome', '')}",
        "",
        "Gate 2 accepts only validated MachineIntentCandidate proposals as internal intents.",
        "",
        "Boundary: no LM call, no execution, no send/submit, no authority grant.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Intent Ingest Gate read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)
    payload = build_payload(generated_at=args.generated_at)
    json_path, operator_path = write_exports(payload, args.export_root)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(
            stable_json(
                {
                    "read_model_id": READ_MODEL_ID,
                    "json_path": json_path.as_posix(),
                    "operator_path": operator_path.as_posix(),
                    "accepted_example": payload["machine_proof"]["accepted_example_is_accepted"],
                    "blocked_example": payload["machine_proof"]["blocked_example_is_blocked"],
                    "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
