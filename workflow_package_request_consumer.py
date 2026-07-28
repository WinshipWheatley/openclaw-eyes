"""Mission Control workflow package request consumer V0.

This adapter consumes ``WORKFLOW_PACKAGE_REQUEST_V0`` operator-instruction
envelopes and records a dry-run package in the Workflow Package Queue V0.
It does not execute workers beyond the queue's no-op result, mutate business
state, touch workbooks, export PDFs, send email, open browser/Gmail/Coupa, post
ledger entries, submit portals, or mark paid/sent.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import agent_voice_router
import business_ops_ledger
import dynamic_card_packet
import invoice_artifact_locator
import maestro_cassandra_responder as mcr
import system_question_answer
import workflow_package_queue
import workflow_dod_reconciler


REQUEST_TYPE = "WORKFLOW_PACKAGE_REQUEST_V0"
REQUEST_KIND = "OPERATOR_INSTRUCTION_PACKAGE_REQUEST"
REQUEST_FILENAME_PATTERNS = (
    "mission_control_operator_instruction_request_*.json",
    "mission_control_workflow_package_request_*.json",
)
DEFAULT_SQLITE_PATH = workflow_package_queue.DEFAULT_SQLITE_PATH
SQLITE_PATH_ENV = "OPENCLAW_WORKFLOW_PACKAGE_QUEUE_SQLITE_PATH"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_INVOICE_ARTIFACT_ROOTS = (
    Path("/mnt/e/openclaw/artifacts/invoice_workbooks"),
    Path("/mnt/e/openclaw/codex_mac_bridge/from-codex-mac/invoice_handoffs"),
)
STATUS_READ_MODEL_ID = "workflow_package_request_consumer_status"
STATUS_JSON_EXPORT_NAME = f"{STATUS_READ_MODEL_ID}.json"
FINANCE_THREAD_INDEX_READ_MODEL_ID = "finance_thread_index"
FINANCE_THREAD_INDEX_JSON_EXPORT_NAME = f"{FINANCE_THREAD_INDEX_READ_MODEL_ID}.json"

AUTHORITY_FALSE_FIELDS = (
    "email_send_allowed",
    "ledger_posting_allowed",
    "browser_access_allowed",
    "gmail_allowed",
    "coupa_allowed",
    "portal_submit_allowed",
    "sent",
    "paid",
    "coupa_submit_allowed",
    "gmail_access_allowed",
    "coupa_access_allowed",
    "browser_automation_allowed",
    "workbook_mutation_allowed",
    "workbook_open_allowed",
    "workbook_source_mutation_allowed",
    "excel_automation_allowed",
    "pdf_export_allowed",
    "email_draft_allowed",
    "ledger_mutation_allowed",
    "payment_marking_allowed",
    "business_action_allowed",
    "external_action_allowed",
    "model_call_allowed",
    "agent_activation_allowed",
    "tool_execution_allowed",
    "runtime_dispatch_allowed",
    "raw_body_ingestion_allowed",
)

TOP_LEVEL_FALSE_FIELDS = (
    "email_send_performed",
    "ledger_mutation_performed",
    "browser_access_performed",
    "browser_or_coupa_open_performed",
    "gmail_access_performed",
    "coupa_access_performed",
    "coupa_submit_performed",
    "submit_performed",
    "workbook_mutation_performed",
    "excel_automation_performed",
    "pdf_export_performed",
    "paid_marking_performed",
    "business_action_performed",
)

BLOCKING_PACKAGE_STATUSES = {
    "PERMISSION_REQUIRED",
    "ARTIFACT_REQUIRED",
    "PROVIDER_GATE_REQUIRED",
}

THREAD_TARGETS_BY_WORKFLOW_REF = {
    "st_annes_work_log_event": ("finance", "st_annes"),
    "st_annes_monthly_invoice_rollup": ("finance", "st_annes"),
    "live_arts_md_invoice_workflow": ("finance", "live_arts_md"),
    "cassandra_receivables_nudge_handoff": ("finance", "receivables"),
    "capital_hilton_invoice_operator_assist": ("finance", "capital_hilton"),
    "capital_hilton_proposal_followup": ("business_development", "capital_hilton"),
}

THREAD_DISPLAY_NAMES = {
    ("finance", "capital_hilton"): "Finance / Capital Hilton",
    ("finance", "live_arts_md"): "Finance / Live Arts MD!",
    ("finance", "st_annes"): "Finance / St. Anne's",
    ("business_development", "capital_hilton"): "Business Development / Capital Hilton",
}

THREAD_ALIASES = {
    "capital_hilton_invoice_workflow": "capital_hilton",
    "capital_hilton_business_development": "capital_hilton",
    "capital_hilton_proposal": "capital_hilton",
    "capital_hilton": "capital_hilton",
    "live_arts_md_invoice_workflow": "live_arts_md",
    "live_arts_md": "live_arts_md",
    "live_arts": "live_arts_md",
    "st_annes_work_log_event": "st_annes",
    "st_annes_invoice_workflow": "st_annes",
    "st_annes": "st_annes",
    "st_anne": "st_annes",
    "st_anne's": "st_annes",
    "church_sound": "st_annes",
}

WORLD_ALIASES = {
    "finance": "finance",
    "invoice_operations": "finance",
    "business_development": "business_development",
    "operations": "operations",
    "diagnostic": "diagnostic",
}

SYSTEM_QUESTION_HINTS = (
    "what should i do here",
    "what do i do here",
    "what is this",
    "what's this",
    "whats this",
    "what's next here",
    "whats next here",
    "what is next here",
    "why am i here",
    "what do i do with this",
    "what should i do with this",
    "is this done",
    "what is the difference between chief and a spawned worker",
    "why did submit capital hilton invoice block",
    "can this send email",
    "what does sqlite know about st. anne",
    "what does sqlite know about st anne",
    "what is safe next",
    "what are all these databases",
    "which database owns package truth",
    "which database owns st. anne",
    "which database owns st anne",
    "can we consolidate sqlite",
    "is the ledger mixed into this",
    "what is safe to clean up",
    "what should never be merged",
)

SYSTEM_QUESTION_TERMS = (
    "openclaw",
    "chief",
    "spawned worker",
    "system question",
    "system design",
    "architecture",
    "package",
    "gate",
    "block",
    "sqlite",
    "database",
    "databases",
    "truth",
    "ownership",
    "owns",
    "owner",
    "consolidate",
    "consolidation",
    "merge",
    "merged",
    "never merge",
    "never be merged",
    "ledger mixed",
    "clean up",
    "cleanup",
    "st. anne",
    "st anne",
    "capital hilton",
    "send email",
    "safe next",
)


@dataclass(frozen=True)
class WorkflowPackageRequestResult:
    status: str
    request_id: str
    request_filename: str
    package: dict[str, Any] | None
    blockers: tuple[str, ...]
    response_primary_status: str
    next_safe_action: str
    receipt: dict[str, Any]
    typed_contract_trace: dict[str, Any] | None = None


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_sqlite_path() -> Path:
    configured = os.environ.get(SQLITE_PATH_ENV)
    return Path(configured) if configured else DEFAULT_SQLITE_PATH


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else Path(__file__).resolve().parent / path


def _load_json_file(path: Path) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _protected_hash_digest(value: str) -> str:
    text = str(value or "").strip().lower()
    if text.startswith("protected_text_hash:"):
        text = text[len("protected_text_hash:") :]
    if text.startswith("sha256:"):
        text = text[len("sha256:") :]
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
        return text
    return ""


def is_workflow_package_request(raw_request: Mapping[str, Any]) -> bool:
    return (
        str(raw_request.get("request_type") or raw_request.get("envelope_type") or "").strip().upper()
        == REQUEST_TYPE
    ) or str(raw_request.get("kind") or "").strip().upper() == REQUEST_KIND


def _request_id(raw_request: Mapping[str, Any], filename: str) -> str:
    return str(
        raw_request.get("request_id")
        or raw_request.get("source_request_id")
        or f"workflow_package_request:{filename}"
    )


def _source_text(raw_request: Mapping[str, Any]) -> str:
    for key in ("source_text", "operator_message", "sanitized_message_summary", "operator_goal", "message", "text"):
        value = str(raw_request.get(key) or "").strip()
        if value:
            return value
    return ""


def _bounded_question_text(source_text: str) -> str:
    text = " ".join(str(source_text or "").strip().split())
    question_mark = text.find("?")
    if question_mark >= 0:
        return text[: question_mark + 1]
    return text[:240]


def is_system_question_request(raw_request: Mapping[str, Any]) -> bool:
    workflow_ref = str(raw_request.get("workflow_ref") or "").strip()
    if workflow_ref == system_question_answer.WORKFLOW_REF:
        return True
    source_text = _source_text(raw_request)
    text = source_text.lower()
    if system_question_answer.is_contextual_question(source_text):
        return True
    if any(hint in text for hint in SYSTEM_QUESTION_HINTS):
        return True
    intent = workflow_package_queue.classify_intent(source_text) if source_text else {}
    if str(intent.get("workflow_ref") or "") not in {"", "diagnostic_package_gate_smoke"}:
        return False
    question_like = "?" in text or text.strip().startswith(("what ", "why ", "can ", "how "))
    if not question_like:
        return False
    return any(term in text for term in SYSTEM_QUESTION_TERMS)


def _system_question_route_metadata(raw_request: Mapping[str, Any]) -> dict[str, Any]:
    raw_current_world = str(raw_request.get("current_world_ref") or raw_request.get("world_ref") or raw_request.get("world") or "")
    raw_current_thread = str(raw_request.get("current_thread_ref") or raw_request.get("thread_ref") or raw_request.get("thread") or "")
    current_world = normalize_world_ref(raw_current_world)
    current_thread = normalize_thread_ref(raw_current_thread)
    has_context = current_world not in {"", "unknown"} and current_thread not in {"", "unknown"}
    lane_display = routing_note_for_lane(current_world, current_thread).replace("Routed to ", "", 1).rstrip(".")
    return {
        "current_world_ref": current_world,
        "current_thread_ref": current_thread,
        "source_world_ref": raw_current_world,
        "source_thread_ref": raw_current_thread,
        "target_world_ref": current_world if has_context else "operations",
        "target_thread_ref": current_thread if has_context else "openclaw",
        "cross_lane_routed": False,
        "routing_note": f"Answered from {lane_display}." if has_context else "Routed to local system question answer.",
    }


def _system_question_routing_reason(answer_payload: Mapping[str, Any]) -> str:
    speaker_ref = str(answer_payload.get("speaker_ref") or "")
    voice_mode = str(answer_payload.get("voice_mode") or "")
    headline = str((answer_payload.get("answer") or {}).get("headline") or "").lower() if isinstance(answer_payload.get("answer"), Mapping) else ""
    if speaker_ref == "hermes":
        return "architecture/system design question"
    if speaker_ref == "chief":
        if "capital hilton" in headline or voice_mode == "diagnostic":
            return "provider gate, package block, or diagnostic question"
        return "diagnostic question"
    if speaker_ref == "guardian":
        return "safety or authority question"
    return "neutral status question"


def _operator_display_from_system_question(answer_payload: Mapping[str, Any]) -> dict[str, Any]:
    answer = answer_payload.get("answer") if isinstance(answer_payload.get("answer"), Mapping) else {}
    speaker_ref = str(answer_payload.get("speaker_ref") or "openclaw")
    voice_mode = str(answer_payload.get("voice_mode") or "operator_calm")
    confirmed = answer.get("confirmed") if isinstance(answer.get("confirmed"), list) else []
    primary_fact = str(confirmed[0]) if confirmed else "Local answer only."
    secondary_facts = [str(item) for item in confirmed[1:3]]
    if not secondary_facts:
        secondary_facts = ["No business action ran."]
    plain_summary = str(answer.get("plain_summary") or "Answered from local OpenClaw sources.")
    plain_summary = plain_summary.replace("St. Anne's", "St Anne's")
    return {
        "speaker_ref": speaker_ref,
        "voice_profile_ref": str(answer_payload.get("voice_profile_ref") or f"agent_voice_profile:{speaker_ref}"),
        "voice_mode": voice_mode,
        "audience": "internal_operator",
        "routing_reason": _system_question_routing_reason(answer_payload),
        "headline": str(answer.get("headline") or "System answer ready"),
        "subheadline": "Local-only OpenClaw answer.",
        "status_label": "Answer ready",
        "tone": "calm" if speaker_ref != "guardian" else "warning",
        "plain_summary": plain_summary,
        "next_safe_action": str(answer.get("next_safe_action") or "Review the local proof refs."),
        "why_it_matters": "Mission Control can ask about OpenClaw without invoking live providers or business actions.",
        "primary_fact": primary_fact,
        "secondary_facts": secondary_facts,
        "proof_caption": "Proof available.",
        "proof_refs_collapsed": True,
        "show_machine_details_by_default": False,
    }


def _system_question_receipt(
    raw_request: Mapping[str, Any],
    *,
    request_id: str,
    source_request_filename: str,
    generated_at: str,
    sqlite_path: Path,
) -> WorkflowPackageRequestResult:
    question = _bounded_question_text(_source_text(raw_request))
    route = _system_question_route_metadata(raw_request)
    answer_payload = system_question_answer.answer_system_question(
        question,
        current_world_ref=route["current_world_ref"],
        current_thread_ref=route["current_thread_ref"],
    )
    operator_display = _operator_display_from_system_question(answer_payload)
    proof_refs = (
        answer_payload.get("answer", {}).get("proof_refs", [])
        if isinstance(answer_payload.get("answer"), Mapping)
        else []
    )
    receipt = {
        "schema_version": "workflow_package_request_consumer_v0",
        "receipt_type": "WORKFLOW_PACKAGE_REQUEST_RESULT_RECEIPT",
        "request_id": request_id,
        "source_request_filename": source_request_filename,
        "raw_internal_status": "RESPONSE_READY",
        "primary_status": "ANSWER_READY",
        "package_id": "",
        "workflow_ref": system_question_answer.WORKFLOW_REF,
        "client_ref": None,
        "world": "system",
        "package_status": "ANSWER_READY",
        "capability_gate_status": "LOCAL_ONLY_SOURCES",
        "blocker": "",
        "next_safe_action": operator_display["next_safe_action"],
        "current_world_ref": route["current_world_ref"],
        "current_thread_ref": route["current_thread_ref"],
        "source_world_ref": route["source_world_ref"],
        "source_thread_ref": route["source_thread_ref"],
        "target_world_ref": route["target_world_ref"],
        "target_thread_ref": route["target_thread_ref"],
        "cross_lane_routed": route["cross_lane_routed"],
        "routing_note": route["routing_note"],
        "speaker_ref": operator_display["speaker_ref"],
        "voice_profile_ref": operator_display["voice_profile_ref"],
        "voice_mode": operator_display["voice_mode"],
        "audience": operator_display["audience"],
        "operator_display": operator_display,
        "system_question_answer": answer_payload,
        "proof_refs": list(dict.fromkeys(str(ref) for ref in proof_refs)),
        "proof_refs_collapsed": True,
        # Same carriage on the system-question path: both are grounded answers, and
        # wiring only the one that was caught in the battery is how the other keeps
        # the bug.
        **_grounded_answer_provenance(answer_payload, source_text=question),
        "authority_boundary": dict(workflow_package_queue.AUTHORITY_BOUNDARY_DEFAULT),
        "request_authority_boundary_all_false": not _authority_blockers(raw_request),
        "no_external_authority_granted": True,
        "result_receipt_required": raw_request.get("result_receipt_required") is True,
        "sqlite_path": str(sqlite_path),
        "created_at": generated_at,
        "machine_proof": {
            "workflow_package_request_v0_detected": is_workflow_package_request(raw_request),
            "system_question_intent_detected": True,
            "system_question_answer_local_only": True,
            "source_surface_mission_control": str(raw_request.get("source_surface") or "") == "mission_control",
            "requested_mode_operator": str(raw_request.get("requested_mode") or "") == "operator",
            "package_recorded": False,
            "queue_sqlite_mutated": False,
            "business_action_gate_closed": True,
            "authority_flags_all_false": all(
                value is False for value in workflow_package_queue.AUTHORITY_BOUNDARY_DEFAULT.values()
            ),
            "external_llm_called": False,
            "child_agent_spawned": False,
            "live_execution_performed": False,
            "email_send_performed": False,
            "ledger_mutation_performed": False,
            "browser_access_performed": False,
            "gmail_access_performed": False,
            "coupa_access_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "business_state_mutation_performed": False,
            "raw_text_stored_in_sqlite": False,
            "proof_refs_collapsed": True,
            "unsafe_true_grants_absent": not _authority_blockers(raw_request),
        },
    }
    receipt = dynamic_card_packet.add_rail_card_packet(
        receipt,
        "system_question_answer",
        read_model_root=DEFAULT_EXPORT_ROOT,
        generated_at=generated_at,
        source_key="system_question_answer",
    )
    return WorkflowPackageRequestResult(
        status="RECORDED",
        request_id=request_id,
        request_filename=source_request_filename,
        package=None,
        blockers=(),
        response_primary_status="ANSWER_READY",
        next_safe_action=str(operator_display["next_safe_action"]),
        receipt=receipt,
    )


_QUESTION_OPENERS = (
    "who", "what", "when", "where", "which", "how", "why",
    "does", "did", "is", "are", "can",
)


def _is_general_question_text(text: str) -> bool:
    """Task 129: interrogative texts route to the answer path, never instruction staging."""
    normalized = " ".join(str(text or "").strip().lower().split())
    if not normalized:
        return False
    if normalized.endswith("?"):
        return True
    first_word = normalized.split(" ", 1)[0].rstrip("?,.!;:")
    if first_word in _QUESTION_OPENERS:
        return True

    # A real message is rarely one clause. This looked only at the FIRST word and the
    # LAST character, so anything that opened with a framing line and closed with a
    # directive was read as an instruction even when it asked a question in the
    # middle — and instruction staging performs no lookup, so the operator got
    # UNKNOWN no matter how good the packet was.
    #
    # Now every sentence gets a vote. A question anywhere makes it a question,
    # because the safe error is answering something that was an instruction (the
    # answer path acts on nothing), not silently staging something that was a
    # question. Imperatives with no interrogative clause are untouched and still
    # stage, and the specific-client-workflow check above still runs first.
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", normalized):
        clause = sentence.strip()
        if not clause:
            continue
        if clause.endswith("?"):
            return True
        opener = clause.split(" ", 1)[0].rstrip("?,.!;:")
        if opener in _QUESTION_OPENERS:
            return True
    return False


def is_business_question_request(raw_request: Mapping[str, Any]) -> bool:
    """Task 129: a general operator BUSINESS question (money/gigs/contacts/status — not a
    meta/system question, and not a specific client instruction) must be answered through
    Maestro's real packet-grounded pipeline, never silently staged. System questions keep
    their own, more specific local answer path (is_system_question_request); a text that
    matches a specific client workflow keeps its existing instruction/dry-run-review
    semantics (classify_intent) untouched."""
    source_text = _business_question_source_text(raw_request)
    if not source_text:
        return False
    if is_system_question_request(raw_request):
        return False
    intent = workflow_package_queue.classify_intent(source_text)
    workflow_ref = str(intent.get("workflow_ref") or "")
    if workflow_ref not in {"", "diagnostic_package_gate_smoke"}:
        return False
    return _is_general_question_text(source_text)


def _business_question_source_text(raw_request: Mapping[str, Any]) -> str:
    """`_source_text` only checks this module's own narrower key list; real envelopes (e.g.
    Mission Control's own writer) may use `operator_text`/`operatorText`/etc instead, which
    `maestro_cassandra_responder.operator_text_from_request` already knows how to read. Try
    the narrower, already-tested key list first, then widen."""
    return _source_text(raw_request) or mcr.operator_text_from_request(raw_request)


def _grounded_answer_provenance(result: Any, *, source_text: str) -> dict[str, Any]:
    """The three fields the reply egress needs, extracted from the real result.

    Kept deliberately total: a missing packet, a result object without the
    attribute, or a malformed status must degrade to "carry nothing extra" rather
    than break a response that is otherwise fine. A response that fails to send is
    worse than one that lacks a citation.
    """

    payload: dict[str, Any] = {"source_text": str(source_text or "")}

    # Callers pass either a result object (maestro answer) or a plain payload
    # mapping (system question). Handle both, because wiring only the shape that
    # happened to fail in the battery is how the other one keeps the bug.
    def _get(obj: Any, key: str) -> Any:
        if isinstance(obj, Mapping):
            return obj.get(key)
        return getattr(obj, key, None)

    packet = _get(result, "packet")
    if not isinstance(packet, Mapping):
        packet = result if isinstance(result, Mapping) else {}

    refs: list[str] = []
    for key in ("source_refs", "packet_source_refs"):
        value = packet.get(key)
        if isinstance(value, (list, tuple)):
            refs.extend(str(v).strip() for v in value if str(v).strip())
    for row in packet.get("facts", ()) or ():
        if isinstance(row, Mapping):
            ref = str(row.get("source_ref") or "").strip()
            if ref:
                refs.append(ref)
    if refs:
        payload["source_refs"] = list(dict.fromkeys(refs))

    status = packet.get("retrieval_status")
    if not isinstance(status, Mapping):
        status = _get(result, "retrieval_status")
    if isinstance(status, Mapping) and str(status.get("status") or ""):
        payload["retrieval_status"] = {
            "status": str(status.get("status") or ""),
            "detail": str(status.get("detail") or ""),
            "source_path": str(status.get("source_path") or ""),
        }
    return payload


def _business_question_receipt(
    raw_request: Mapping[str, Any],
    *,
    request_id: str,
    source_request_filename: str,
    generated_at: str,
    sqlite_path: Path,
    typed_contract_trace: dict[str, Any] | None = None,
    first_touch_receipt: Mapping[str, Any] | None = None,
) -> WorkflowPackageRequestResult | None:
    source_text = _business_question_source_text(raw_request)
    session = mcr.session_from_request(raw_request)
    result = mcr.answer_frontdoor_chat(
        source_text,
        session=session,
        source_surface="mission_control",
        first_touch_receipt=first_touch_receipt,
    )
    result_trace = mcr.typed_contract_trace_for_result(result)
    if typed_contract_trace is not None:
        typed_contract_trace.update(result_trace)
    if result.status != "ANSWER_READY":
        return None
    route = _system_question_route_metadata(raw_request)
    machine_proof = mcr.machine_proof_for_result(result)
    proof_refs = mcr.proof_refs_for_result(result)
    answer_text = str(result.one_line_answer or result.plain_summary or "").strip()
    operator_display = {
        "speaker_ref": "maestro",
        "voice_profile_ref": "agent_voice_profile:maestro",
        "voice_mode": "operator_calm",
        "audience": "internal_operator",
        "routing_reason": "operator business question, answered from the grounded packet",
        "headline": answer_text or "Answer ready",
        "subheadline": "Answered from OpenClaw's grounded packet.",
        "status_label": "Answer ready",
        "tone": "calm",
        "plain_summary": str(result.plain_summary or answer_text),
        "next_safe_action": "Review the proof refs if you want the underlying facts.",
        "why_it_matters": "The operator's question is answered directly, never staged as an instruction.",
        "primary_fact": answer_text or "Answered.",
        "secondary_facts": [],
        "proof_caption": "Proof available.",
        "proof_refs_collapsed": True,
        "show_machine_details_by_default": False,
    }
    receipt = {
        "schema_version": "workflow_package_request_consumer_v0",
        "receipt_type": "WORKFLOW_PACKAGE_REQUEST_RESULT_RECEIPT",
        "request_id": request_id,
        "source_request_filename": source_request_filename,
        "raw_internal_status": "RESPONSE_READY",
        "primary_status": "ANSWER_READY",
        "package_id": "",
        "workflow_ref": "business_question_answer",
        "client_ref": None,
        "world": route["current_world_ref"] or "operations",
        "package_status": "ANSWER_READY",
        "capability_gate_status": "GROUNDED_PACKET_ANSWER",
        "blocker": "",
        "next_safe_action": operator_display["next_safe_action"],
        "current_world_ref": route["current_world_ref"],
        "current_thread_ref": route["current_thread_ref"],
        "source_world_ref": route["source_world_ref"],
        "source_thread_ref": route["source_thread_ref"],
        "target_world_ref": route["target_world_ref"],
        "target_thread_ref": route["target_thread_ref"],
        "cross_lane_routed": route["cross_lane_routed"],
        "routing_note": "Answered from Maestro's grounded packet (question, not staged).",
        "speaker_ref": operator_display["speaker_ref"],
        "voice_profile_ref": operator_display["voice_profile_ref"],
        "voice_mode": operator_display["voice_mode"],
        "audience": operator_display["audience"],
        "operator_display": operator_display,
        "maestro_answer": {
            "one_line_answer": result.one_line_answer,
            "plain_summary": result.plain_summary,
            "intent_class": result.intent_class,
        },
        "proof_refs": list(dict.fromkeys(str(ref) for ref in proof_refs)),
        "proof_refs_collapsed": True,
        # ── Carried to the shared reply egress ────────────────────────────────
        # The listener can only surface a retrieval failure or a citation if the
        # bridge actually sends them. Before this the response carried the ANSWER
        # and dropped everything needed to judge it: Maestro said UNKNOWN and the
        # operator had no way to learn that chief_status_rail.json had been
        # selected and had failed to load. source_text rides along so the egress
        # can tell a real answer from a persona changing the subject.
        **_grounded_answer_provenance(result, source_text=source_text),
        "authority_boundary": dict(workflow_package_queue.AUTHORITY_BOUNDARY_DEFAULT),
        "request_authority_boundary_all_false": not _authority_blockers(raw_request),
        "no_external_authority_granted": True,
        "result_receipt_required": raw_request.get("result_receipt_required") is True,
        "sqlite_path": str(sqlite_path),
        "created_at": generated_at,
        "machine_proof": {
            "workflow_package_request_v0_detected": is_workflow_package_request(raw_request),
            "business_question_intent_detected": True,
            "instruction_staging_bypassed": True,
            "source_surface_mission_control": str(raw_request.get("source_surface") or "") == "mission_control",
            "requested_mode_operator": str(raw_request.get("requested_mode") or "") == "operator",
            "package_recorded": False,
            "queue_sqlite_mutated": False,
            "business_action_gate_closed": True,
            "authority_flags_all_false": all(
                value is False for value in workflow_package_queue.AUTHORITY_BOUNDARY_DEFAULT.values()
            ),
            "external_llm_called": bool(machine_proof.get("external_llm_invoked", False)),
            "child_agent_spawned": False,
            "live_execution_performed": False,
            "email_send_performed": False,
            "ledger_mutation_performed": False,
            "browser_access_performed": False,
            "gmail_access_performed": False,
            "coupa_access_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "business_state_mutation_performed": False,
            "raw_text_stored_in_sqlite": False,
            "proof_refs_collapsed": True,
            "unsafe_true_grants_absent": not _authority_blockers(raw_request),
            "maestro_machine_proof": machine_proof,
        },
    }
    receipt = dynamic_card_packet.add_rail_card_packet(
        receipt,
        "business_question_answer",
        read_model_root=DEFAULT_EXPORT_ROOT,
        generated_at=generated_at,
        source_key="business_question_answer",
    )
    return WorkflowPackageRequestResult(
        status="RECORDED",
        request_id=request_id,
        request_filename=source_request_filename,
        package=None,
        blockers=(),
        response_primary_status="ANSWER_READY",
        next_safe_action=str(operator_display["next_safe_action"]),
        receipt=receipt,
        typed_contract_trace=dict(result_trace) or None,
    )


def _normalize_ref(value: str) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("&", "and")
    text = text.replace("’", "'")
    text = text.replace("!", "")
    text = text.replace("/", " ")
    text = text.replace("-", "_")
    text = "_".join(part for part in re_split_ref(text) if part)
    return text


def re_split_ref(value: str) -> tuple[str, ...]:
    return tuple(part for part in value.replace(".", "").replace("'", "").split() for part in part.split("_") if part)


def normalize_world_ref(value: str) -> str:
    normalized = _normalize_ref(value)
    return WORLD_ALIASES.get(normalized, normalized or "unknown")


def normalize_thread_ref(value: str) -> str:
    normalized = _normalize_ref(value)
    if normalized in THREAD_ALIASES:
        return THREAD_ALIASES[normalized]
    if "capital" in normalized and "hilton" in normalized:
        return "capital_hilton"
    if "live" in normalized and "arts" in normalized:
        return "live_arts_md"
    if "anne" in normalized or "church" in normalized:
        return "st_annes"
    return normalized or "unknown"


def target_lane_for_workflow(workflow_ref: str) -> tuple[str, str]:
    return THREAD_TARGETS_BY_WORKFLOW_REF.get(str(workflow_ref or ""), ("diagnostic", "workflow_package_queue"))


def routing_note_for_lane(world_ref: str, thread_ref: str) -> str:
    display = THREAD_DISPLAY_NAMES.get((world_ref, thread_ref), f"{world_ref.replace('_', ' ').title()} / {thread_ref.replace('_', ' ').title()}")
    return f"Routed to {display}."


def routing_metadata(raw_request: Mapping[str, Any], package: Mapping[str, Any] | None) -> dict[str, Any]:
    raw_current_world = str(raw_request.get("current_world_ref") or raw_request.get("world_ref") or raw_request.get("world") or "")
    raw_current_thread = str(raw_request.get("current_thread_ref") or raw_request.get("thread_ref") or raw_request.get("thread") or "")
    current_world = normalize_world_ref(raw_current_world)
    current_thread = normalize_thread_ref(raw_current_thread)
    workflow_ref = str((package or {}).get("workflow_ref") or raw_request.get("workflow_ref") or "")
    target_world, target_thread = target_lane_for_workflow(workflow_ref)
    cross_lane = package is not None and (current_world != target_world or current_thread != target_thread)
    return {
        "current_world_ref": current_world,
        "current_thread_ref": current_thread,
        "source_world_ref": raw_current_world,
        "source_thread_ref": raw_current_thread,
        "target_world_ref": target_world if package is not None else "",
        "target_thread_ref": target_thread if package is not None else "",
        "cross_lane_routed": bool(cross_lane),
        "routing_note": routing_note_for_lane(target_world, target_thread) if cross_lane else "",
    }


def build_finance_thread_index(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    threads = [
        {
            "world_ref": "finance",
            "thread_ref": "capital_hilton",
            "display_name": "Capital Hilton",
            "client_ref": "capital_hilton",
            "primary_workflow_refs": ["capital_hilton_invoice_operator_assist"],
            "aliases": ["capital_hilton_invoice_workflow", "Capital Hilton"],
        },
        {
            "world_ref": "finance",
            "thread_ref": "live_arts_md",
            "display_name": "Live Arts MD!",
            "client_ref": "live_arts_md",
            "primary_workflow_refs": ["live_arts_md_invoice_workflow"],
            "aliases": ["Live Arts MD!", "live_arts_md_invoice_workflow"],
        },
        {
            "world_ref": "finance",
            "thread_ref": "st_annes",
            "display_name": "St. Anne's",
            "client_ref": "st_annes",
            "primary_workflow_refs": ["st_annes_work_log_event", "st_annes_monthly_invoice_rollup"],
            "aliases": ["St. Anne's", "ST Anne's", "St Annes", "church_sound"],
        },
    ]
    return {
        "schema_version": "finance_thread_index_v0",
        "read_model_id": FINANCE_THREAD_INDEX_READ_MODEL_ID,
        "generated_at": generated_at,
        "status": "FINANCE_THREAD_INDEX_READY",
        "world_ref": "finance",
        "threads": threads,
        "routing_rules": {
            "current_context_is_bias_only": True,
            "router_determines_target_world_thread": True,
            "st_annes_work_log_events_belong_to": "finance/st_annes",
            "capital_hilton_invoice_operator_assist_belongs_to": "finance/capital_hilton",
            "capital_hilton_proposal_followup_belongs_to": "business_development/capital_hilton",
        },
        "authority_boundary": {
            "email_send_allowed": False,
            "ledger_posting_allowed": False,
            "browser_access_allowed": False,
            "gmail_allowed": False,
            "coupa_allowed": False,
            "workbook_mutation_allowed": False,
            "pdf_export_allowed": False,
            "paid": False,
            "sent": False,
        },
        "machine_proof": {
            "capital_hilton_thread_present": True,
            "live_arts_md_thread_present": True,
            "st_annes_thread_present": True,
            "business_action_performed": False,
            "email_send_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "unsafe_true_grants_absent": True,
        },
    }


def export_finance_thread_index(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_finance_thread_index(generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    local_path = export_root / FINANCE_THREAD_INDEX_JSON_EXPORT_NAME
    local_path.write_text(stable_json(read_model), encoding="utf-8")
    bridge_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge = bridge_export_root / FINANCE_THREAD_INDEX_JSON_EXPORT_NAME
        bridge.write_text(stable_json(read_model), encoding="utf-8")
        bridge_path = bridge.as_posix()
    return {
        "read_model_path": local_path.as_posix(),
        "bridge_read_model_path": bridge_path,
        "status": str(read_model["status"]),
    }


def build_status_read_model_from_existing(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    status_path = _rooted(export_root) / STATUS_JSON_EXPORT_NAME
    payload = _load_json_file(status_path)
    if not payload:
        payload = {
            "schema_version": "workflow_package_request_consumer_status_v0",
            "read_model_id": STATUS_READ_MODEL_ID,
            "status": "WORKFLOW_PACKAGE_RAIL_STATUS_READY",
            "consumer_status": "READY",
            "generated_at": generated_at or utc_now(),
            "legacy_status_file_missing": True,
            "authority_boundary": {key: False for key in AUTHORITY_FALSE_FIELDS},
            "machine_proof": {
                "no_live_business_actions": True,
                "unsafe_true_grants_absent": True,
            },
        }
    if generated_at is not None:
        payload["generated_at"] = generated_at
    return dynamic_card_packet.add_rail_card_packet(
        payload,
        "workflow_package_request_consumer",
        read_model_root=export_root,
        generated_at=str(payload.get("generated_at") or utc_now()),
        source_key="workflow_package_request_consumer_status",
    )


def export_workflow_package_request_consumer_status(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, str]:
    payload = build_status_read_model_from_existing(
        export_root=export_root,
        generated_at=generated_at,
    )
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    local_path = export_root / STATUS_JSON_EXPORT_NAME
    local_path.write_text(stable_json(payload), encoding="utf-8")
    bridge_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge = bridge_export_root / STATUS_JSON_EXPORT_NAME
        bridge.write_text(stable_json(payload), encoding="utf-8")
        bridge_path = bridge.as_posix()
    return {
        "read_model_path": local_path.as_posix(),
        "bridge_read_model_path": bridge_path,
        "status": str(payload.get("status") or ""),
        "dynamic_card_v1_card_count": str((payload.get("dynamic_card_packet_v1") or {}).get("card_count") or 0),
    }


def _authority_blockers(raw_request: Mapping[str, Any]) -> tuple[str, ...]:
    blockers: list[str] = []
    authority = raw_request.get("authority_boundary")
    if not isinstance(authority, Mapping):
        blockers.append("authority_boundary_missing_or_invalid")
    else:
        for key, value in authority.items():
            if value is True:
                blockers.append(f"authority_true:{key}")
        for key in AUTHORITY_FALSE_FIELDS:
            if authority.get(key) is True:
                blockers.append(f"unsafe_authority_true:{key}")
    for key in TOP_LEVEL_FALSE_FIELDS:
        if raw_request.get(key) is True:
            blockers.append(f"unsafe_action_performed_true:{key}")
    return tuple(dict.fromkeys(blockers))


def validate_envelope(raw_request: Mapping[str, Any], *, source_request_filename: str = "") -> tuple[bool, tuple[str, ...]]:
    blockers: list[str] = []
    if not is_workflow_package_request(raw_request):
        blockers.append("not_workflow_package_request_v0")
    if str(raw_request.get("source_surface") or "").strip() != "mission_control":
        blockers.append("source_surface_not_mission_control")
    if str(raw_request.get("requested_mode") or "").strip() != "operator":
        blockers.append("requested_mode_not_operator")
    if raw_request.get("result_receipt_required") is not True:
        blockers.append("result_receipt_required_not_true")
    if not _source_text(raw_request):
        blockers.append("source_text_missing")
    blockers.extend(_authority_blockers(raw_request))

    expected_hash = workflow_package_queue.protected_text_hash(_source_text(raw_request)) if _source_text(raw_request) else ""
    expected_digest = _protected_hash_digest(expected_hash)
    provided_hash = str(raw_request.get("protected_text_hash") or "").strip()
    source_text_ref = str(raw_request.get("source_text_ref") or "").strip()
    if provided_hash and expected_digest and _protected_hash_digest(provided_hash) != expected_digest:
        blockers.append("protected_text_hash_mismatch")
    if source_text_ref and expected_digest and _protected_hash_digest(source_text_ref) != expected_digest:
        blockers.append("source_text_ref_hash_mismatch")

    return not blockers, tuple(dict.fromkeys(blockers))


def _next_safe_action(package: Mapping[str, Any] | None, blockers: tuple[str, ...]) -> str:
    if package is None:
        return "Fix the safe Mission Control operator-instruction envelope and resend it."
    status = str(package.get("status") or "")
    workflow_ref = str(package.get("workflow_ref") or "")
    if status == "PROVIDER_GATE_REQUIRED":
        return "Stage the operator-assist provider and final Submit gate; no Coupa or email action ran."
    if status == "PERMISSION_REQUIRED":
        return "Stage permission and artifact prerequisites; no send, workbook, PDF, or ledger action ran."
    if status == "ARTIFACT_REQUIRED":
        return "Attach or approve the required artifact before operator review; no send action ran."
    if workflow_ref == "capital_hilton_proposal_followup":
        return "Review the staged Business Development follow-up package; V0 does not send email."
    if workflow_ref == "st_annes_work_log_event":
        return "Review the staged work-log package; invoice inclusion still requires separate operator confirmation."
    return "Review the staged dry-run package; the business action gate remains closed."


def _primary_status(package: Mapping[str, Any] | None, blockers: tuple[str, ...]) -> str:
    if package is None:
        return "BLOCKED_BY_ENVELOPE_VALIDATION"
    return str(package.get("status") or "UNKNOWN_FAIL_CLOSED")


def _blocker(package: Mapping[str, Any] | None, blockers: tuple[str, ...]) -> str:
    if blockers:
        return "; ".join(blockers)
    if package is None:
        return "package_not_created"
    if str(package.get("status") or "") in BLOCKING_PACKAGE_STATUSES:
        capability = package.get("capability_gate_result")
        if isinstance(capability, Mapping):
            return str(capability.get("reason") or capability.get("status") or package["status"])
    return ""


def _operator_display(
    package: Mapping[str, Any] | None,
    *,
    primary_status: str,
    blocker: str,
    next_safe_action: str,
    raw_request: Mapping[str, Any],
) -> dict[str, Any]:
    if package is not None and isinstance(package.get("operator_display"), Mapping):
        display = dict(package["operator_display"])
        display.setdefault("next_safe_action", next_safe_action)
        return display
    voice_fields = agent_voice_router.route_agent_voice_dict(
        workflow_ref=str(raw_request.get("workflow_ref") or ""),
        package_status=primary_status,
        source_text=_source_text(raw_request),
        source_surface=str(raw_request.get("source_surface") or ""),
        world=str(raw_request.get("world_ref") or raw_request.get("world") or ""),
        authority_boundary=raw_request.get("authority_boundary") if isinstance(raw_request.get("authority_boundary"), Mapping) else {},
        blocker=blocker,
    )
    return {
        **voice_fields,
        "headline": "Instruction needs a safety fix",
        "subheadline": "The request envelope did not pass local checks.",
        "status_label": "Blocked",
        "tone": "blocked",
        "plain_summary": "I could not stage this instruction because the safe request envelope is incomplete.",
        "next_safe_action": next_safe_action,
        "why_it_matters": "OpenClaw needs a valid local envelope before it records package intent.",
        "primary_fact": "Nothing ran.",
        "secondary_facts": [
            f"Missing or unsafe field: {blocker}" if blocker else f"Status: {primary_status}",
            "No business action ran.",
        ],
        "proof_caption": "Proof available",
        "show_machine_details_by_default": False,
    }


_DOD_FRONTIER_LABELS = {
    "invoice_artifact_verified": "verification of the canonical invoice PDF",
    "operator_confirmed_pdf": "operator confirmation of the PDF",
    "work_log_reconciled": "reconciliation of the workbook into the work-log mirror",
    "telegram_pdf_delivered": "delivery of the verified PDF proof to the operator",
}


def _dod_reconciliation_receipt(
    raw_request: Mapping[str, Any],
    *,
    workflow_ref: str,
    request_id: str,
    source_request_filename: str,
    generated_at: str,
) -> WorkflowPackageRequestResult:
    evidence = workflow_dod_reconciler.collect_trusted_evidence()
    ledger_path = Path(business_ops_ledger.resolve_business_ops_ledger_path())
    measured = workflow_dod_reconciler.reconcile_workflow(
        workflow_ref,
        evidence=evidence,
        db_path=ledger_path,
        generated_at=generated_at,
    )
    milestones = list(measured.get("milestones") or [])
    proven_count = sum(item.get("status") == "PROVEN" for item in milestones)
    frontier = measured.get("frontier") if isinstance(measured.get("frontier"), Mapping) else {}
    frontier_ref = str(frontier.get("milestone_ref") or "registry_entry_missing")
    frontier_label = _DOD_FRONTIER_LABELS.get(
        frontier_ref,
        str(frontier.get("label") or "installation of the measured workflow registry").lower(),
    )
    complete = measured.get("status") == "COMPLETE"
    blocked = measured.get("status") == "BLOCKED"
    if complete:
        plain_summary = (
            f"The St. Anne's invoice test is done. {proven_count} of {len(milestones)} "
            "milestones are proven."
        )
    elif blocked:
        plain_summary = (
            f"The St. Anne's invoice test is blocked. {proven_count} of {len(milestones)} "
            f"milestones are proven. The current frontier is {frontier_label}."
        )
    else:
        plain_summary = (
            f"The St. Anne's invoice test is not done. {proven_count} of {len(milestones)} "
            f"milestones {'is' if proven_count == 1 else 'are'} proven. "
            f"The current frontier is {frontier_label}."
        )
    operator_display = {
        **agent_voice_router.route_agent_voice_dict(
            workflow_ref="st_annes_monthly_invoice_rollup",
            package_status=str(measured.get("status") or "BLOCKED"),
            source_text=_source_text(raw_request),
            source_surface=str(raw_request.get("source_surface") or ""),
            world="invoice_operations",
            client_ref="st_annes",
            authority_boundary=raw_request.get("authority_boundary")
            if isinstance(raw_request.get("authority_boundary"), Mapping)
            else {},
            blocker="" if not blocked else str(measured.get("reason") or frontier.get("status") or ""),
        ),
        "headline": "St. Anne's invoice test measured",
        "subheadline": "Receipt-backed definition-of-done checklist.",
        "status_label": "Done" if complete else "Blocked" if blocked else "In progress",
        "tone": "calm" if not blocked else "warning",
        "plain_summary": plain_summary,
        "next_safe_action": str(frontier.get("advance") or "Install the versioned registry entry."),
        "why_it_matters": "The system can resume from the measured frontier without replaying earlier steps.",
        "primary_fact": f"{proven_count} of {len(milestones)} milestones proven.",
        "secondary_facts": [
            f"Frontier: {frontier_label}.",
            "No advance or business action ran.",
        ],
        "proof_caption": "Milestone receipt refs available.",
        "show_machine_details_by_default": False,
    }
    route = routing_metadata(
        raw_request,
        {"workflow_ref": "st_annes_monthly_invoice_rollup"},
    )
    primary_status = (
        "DOD_COMPLETE"
        if complete
        else "DOD_BLOCKED"
        if blocked
        else "DOD_IN_PROGRESS"
    )
    receipt = {
        "schema_version": "workflow_package_request_consumer_v0",
        "receipt_type": "WORKFLOW_DOD_RECONCILIATION_RESULT_RECEIPT",
        "request_id": request_id,
        "source_request_filename": source_request_filename,
        "raw_internal_status": "RESPONSE_READY",
        "primary_status": primary_status,
        "package_id": "",
        "workflow_ref": workflow_ref,
        "client_ref": "st_annes",
        "world": "invoice_operations",
        "package_status": primary_status,
        "capability_gate_status": "READ_ONLY_RECONCILIATION",
        "blocker": "" if not blocked else str(measured.get("reason") or frontier.get("status") or ""),
        "next_safe_action": operator_display["next_safe_action"],
        **route,
        "speaker_ref": operator_display["speaker_ref"],
        "voice_profile_ref": operator_display["voice_profile_ref"],
        "voice_mode": operator_display["voice_mode"],
        "audience": operator_display["audience"],
        "operator_display": operator_display,
        "dod_reconciliation": measured,
        "proof_refs": [
            ref
            for milestone in milestones
            for ref in milestone.get("receipt_refs") or []
        ],
        "authority_boundary": dict(workflow_package_queue.AUTHORITY_BOUNDARY_DEFAULT),
        "request_authority_boundary_all_false": not _authority_blockers(raw_request),
        "no_external_authority_granted": True,
        "result_receipt_required": raw_request.get("result_receipt_required") is True,
        "created_at": generated_at,
        "machine_proof": {
            "workflow_package_request_v0_detected": is_workflow_package_request(raw_request),
            "dod_reconciler_request_detected": True,
            "trusted_store_allowlist_enforced": True,
            "package_recorded": False,
            "queue_sqlite_mutated": False,
            "advance_performed": False,
            "business_action_performed": False,
            "email_send_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "approval_gate_activated": False,
            "operator_word_inferred": False,
            "unsafe_true_grants_absent": not _authority_blockers(raw_request),
        },
    }
    return WorkflowPackageRequestResult(
        status="RECORDED",
        request_id=request_id,
        request_filename=source_request_filename,
        package=None,
        blockers=(),
        response_primary_status=primary_status,
        next_safe_action=str(operator_display["next_safe_action"]),
        receipt=receipt,
    )


def _is_invoice_artifact_locator_request(source_text: str, workflow_ref: str) -> bool:
    if workflow_ref != "st_annes_monthly_invoice_rollup":
        return False
    text = " ".join(str(source_text or "").strip().lower().split())
    return (
        "pdf" in text
        and any(term in text for term in ("workbook", "excel", "excell"))
        and "june" in text
        and "2026" in text
    )


def _invoice_locator_operator_display(
    package: Mapping[str, Any],
    locator_result: Mapping[str, Any],
) -> dict[str, Any]:
    candidate = locator_result.get("canonical_candidate")
    if not isinstance(candidate, Mapping):
        return dict(package.get("operator_display") or {})
    copies = candidate.get("duplicate_pdf_paths")
    copy_count = len(copies) if isinstance(copies, list) else 1
    amount = float(candidate.get("amount") or 0)
    amount_text = f"${amount:,.0f}" if amount.is_integer() else f"${amount:,.2f}"
    status = str(candidate.get("invoice_status") or "unknown").strip().lower()
    send_text = "was sent" if candidate.get("send_receipt_present") is True else "was never sent"
    base = dict(package.get("operator_display") or {})
    base.update(
        {
            "headline": "St. Anne's June invoice PDF found",
            "subheadline": "Verified from allowlisted local manifests and file hashes.",
            "status_label": "Verified locally",
            "tone": "calm",
            "plain_summary": (
                f"I found one canonical St. Anne's June invoice PDF across {copy_count} verified copies. "
                f"It comes from invoice.xlsx sheet {candidate.get('source_sheet')}, invoice "
                f"{candidate.get('invoice_number')}, totals {amount_text}, is {status}, and {send_text}."
            ),
            "next_safe_action": "Review the verified local copies; attachment and delivery remain closed.",
            "why_it_matters": "Duplicate handoff copies collapse to one hash-verified invoice identity.",
            "primary_fact": f"Invoice {candidate.get('invoice_number')} totals {amount_text}.",
            "secondary_facts": [
                f"Source: invoice.xlsx sheet {candidate.get('source_sheet')}.",
                f"Status: {status}; {send_text}.",
            ],
            "proof_caption": "Manifest and SHA-256 proof available.",
            "show_machine_details_by_default": False,
        }
    )
    return base


def _agentic_invoice_locator_fallback_packet(
    locator_result: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "invoice_artifact_locator_agentic_fallback_v0",
        "status": "STAGED_NOT_EXECUTED",
        "normalized_query": {
            "client_ref": str(locator_result.get("client_ref") or ""),
            "service_period": str(locator_result.get("service_period") or ""),
        },
        "allowlisted_roots": list(locator_result.get("searched_roots") or []),
        "deterministic_status": str(locator_result.get("status") or "NOT_FOUND"),
        "rejections": list(locator_result.get("rejections") or []),
        "model_call_performed": False,
        "root_widening_performed": False,
        "external_action_performed": False,
    }


def _invoice_locator_fallback_operator_display(
    package: Mapping[str, Any],
    locator_result: Mapping[str, Any],
) -> dict[str, Any]:
    status = str(locator_result.get("status") or "NOT_FOUND")
    ambiguous = status == "AMBIGUOUS"
    base = dict(package.get("operator_display") or {})
    base.update(
        {
            "headline": "St. Anne's June invoice PDF needs resolution",
            "subheadline": "The deterministic allowlisted search did not yield one canonical artifact.",
            "status_label": "Ambiguous" if ambiguous else "Not found",
            "tone": "warning",
            "plain_summary": (
                "I found multiple different verified St. Anne's June invoice PDFs, so I did not pick one."
                if ambiguous
                else "I could not verify a St. Anne's June invoice PDF in the allowlisted artifact roots."
            ),
            "next_safe_action": "Review the bounded fallback packet; no model call or wider search ran.",
            "why_it_matters": "Artifact identity must be proved before OpenClaw presents a canonical invoice.",
            "primary_fact": f"Deterministic locator status: {status}.",
            "secondary_facts": [
                "The fallback packet is metadata only.",
                "No attachment, delivery, or external action ran.",
            ],
            "proof_caption": "Search roots and rejection reasons available.",
            "show_machine_details_by_default": False,
        }
    )
    return base


def consume_workflow_package_request(
    raw_request: Mapping[str, Any],
    *,
    source_request_filename: str = "",
    generated_at: str | None = None,
    sqlite_path: Path | None = None,
    lm1_shared_seam: Mapping[str, Any] | None = None,
    frontdoor_contract_already_attempted: bool = False,
    first_touch_receipt: Mapping[str, Any] | None = None,
) -> WorkflowPackageRequestResult:
    generated_at = generated_at or utc_now()
    sqlite_path = sqlite_path or default_sqlite_path()
    request_id = _request_id(raw_request, source_request_filename)
    ok, blockers = validate_envelope(raw_request, source_request_filename=source_request_filename)
    dod_workflow_ref = workflow_dod_reconciler.requested_workflow_ref(_source_text(raw_request))
    if ok and dod_workflow_ref:
        return _dod_reconciliation_receipt(
            raw_request,
            workflow_ref=dod_workflow_ref,
            request_id=request_id,
            source_request_filename=source_request_filename,
            generated_at=generated_at,
        )
    if ok and is_system_question_request(raw_request):
        return _system_question_receipt(
            raw_request,
            request_id=request_id,
            source_request_filename=source_request_filename,
            generated_at=generated_at,
            sqlite_path=sqlite_path,
        )
    business_contract_trace: dict[str, Any] = {}
    if ok and is_business_question_request(raw_request) and not frontdoor_contract_already_attempted:
        business_result = _business_question_receipt(
            raw_request,
            request_id=request_id,
            source_request_filename=source_request_filename,
            generated_at=generated_at,
            sqlite_path=sqlite_path,
            typed_contract_trace=business_contract_trace,
            first_touch_receipt=first_touch_receipt,
        )
        if business_result is not None:
            return business_result
    package: dict[str, Any] | None = None
    if ok:
        package_created_at = str(raw_request.get("created_at") or generated_at)
        package = workflow_package_queue.create_package(
            _source_text(raw_request),
            source_surface="mission_control",
            created_at=package_created_at,
            intent_override=(
                lm1_shared_seam.get("interpretation")
                if isinstance(lm1_shared_seam, Mapping)
                else None
            ),
            lm1_shared_packet=(
                lm1_shared_seam.get("workflow_context_packet")
                if isinstance(lm1_shared_seam, Mapping)
                else None
            ),
        )
        package["source_request_metadata"] = {
            "request_id": request_id,
            "source_request_filename": source_request_filename,
            "world_ref": str(raw_request.get("world_ref") or raw_request.get("world") or ""),
            "thread_ref": str(raw_request.get("thread_ref") or ""),
            "source_text_ref": str(raw_request.get("source_text_ref") or ""),
            "protected_text_hash": str(raw_request.get("protected_text_hash") or ""),
            "idempotency_key": str(raw_request.get("idempotency_key") or ""),
            "payload_hash": str(raw_request.get("payload_hash") or ""),
        }
        package["routing_metadata"] = routing_metadata(raw_request, package)
        if _is_invoice_artifact_locator_request(
            _source_text(raw_request),
            str(package.get("workflow_ref") or ""),
        ):
            locator_result = invoice_artifact_locator.locate_invoice_artifacts(
                "st_annes",
                "2026-06",
                roots=DEFAULT_INVOICE_ARTIFACT_ROOTS,
            )
            package["artifact_locator_result"] = locator_result
            if locator_result.get("status") == "FOUND":
                package["operator_display"] = _invoice_locator_operator_display(package, locator_result)
                package["agentic_fallback_packet"] = {}
            else:
                package["agentic_fallback_packet"] = _agentic_invoice_locator_fallback_packet(
                    locator_result
                )
                package["operator_display"] = _invoice_locator_fallback_operator_display(
                    package,
                    locator_result,
                )
        workflow_package_queue.record_package(sqlite_path, package)

    primary_status = _primary_status(package, blockers)
    blocker = _blocker(package, blockers)
    next_safe_action = _next_safe_action(package, blockers)
    operator_display = _operator_display(
        package,
        primary_status=primary_status,
        blocker=blocker,
        next_safe_action=next_safe_action,
        raw_request=raw_request,
    )
    route = routing_metadata(raw_request, package)
    receipt = {
        "schema_version": "workflow_package_request_consumer_v0",
        "receipt_type": "WORKFLOW_PACKAGE_REQUEST_RESULT_RECEIPT",
        "request_id": request_id,
        "source_request_filename": source_request_filename,
        "raw_internal_status": "RESPONSE_READY" if package is not None else "BLOCKED_WITH_REASON",
        "primary_status": primary_status,
        "package_id": package.get("package_id") if package else "",
        "workflow_ref": package.get("workflow_ref") if package else "",
        "client_ref": package.get("client_ref") if package else None,
        "world": package.get("world") if package else str(raw_request.get("world_ref") or raw_request.get("world") or ""),
        "package_status": package.get("status") if package else "NOT_CREATED",
        "capability_gate_status": (
            (package.get("capability_gate_result") or {}).get("status")
            if package
            else "NOT_EVALUATED"
        ),
        "blocker": blocker,
        "next_safe_action": next_safe_action,
        "current_world_ref": route["current_world_ref"],
        "current_thread_ref": route["current_thread_ref"],
        "source_world_ref": route["source_world_ref"],
        "source_thread_ref": route["source_thread_ref"],
        "target_world_ref": route["target_world_ref"],
        "target_thread_ref": route["target_thread_ref"],
        "cross_lane_routed": route["cross_lane_routed"],
        "routing_note": route["routing_note"],
        "speaker_ref": operator_display["speaker_ref"],
        "voice_profile_ref": operator_display["voice_profile_ref"],
        "voice_mode": operator_display["voice_mode"],
        "audience": operator_display["audience"],
        "operator_display": operator_display,
        "proof_refs": list((package or {}).get("proof_refs") or []),
        "dry_run_proof_bundle": dict((package or {}).get("dry_run_proof_bundle") or {}),
        "artifact_locator_result": dict((package or {}).get("artifact_locator_result") or {}),
        "agentic_fallback_packet": dict((package or {}).get("agentic_fallback_packet") or {}),
        "authority_boundary": dict(workflow_package_queue.AUTHORITY_BOUNDARY_DEFAULT),
        "request_authority_boundary_all_false": not _authority_blockers(raw_request),
        "no_external_authority_granted": True,
        "result_receipt_required": raw_request.get("result_receipt_required") is True,
        "sqlite_path": str(sqlite_path),
        "created_at": generated_at,
        "machine_proof": {
            "workflow_package_request_v0_detected": is_workflow_package_request(raw_request),
            "lm1_shared_seam_used": isinstance(lm1_shared_seam, Mapping)
            and bool(lm1_shared_seam.get("interpretation")),
            "lm1_workflow_packet_present": isinstance(lm1_shared_seam, Mapping)
            and bool(lm1_shared_seam.get("workflow_context_packet")),
            "source_surface_mission_control": str(raw_request.get("source_surface") or "") == "mission_control",
            "requested_mode_operator": str(raw_request.get("requested_mode") or "") == "operator",
            "package_recorded": package is not None,
            "queue_noop_worker_only": True,
            "dry_run_proof_bundle_emitted": bool((package or {}).get("dry_run_proof_bundle")),
            "local_pdf_proof_rendered": bool(
                package and (package.get("worker_result") or {}).get("local_pdf_proof_rendered") is True
            ),
            "business_action_gate_closed": bool(
                package and (package.get("business_action_gate_result") or {}).get("status") == "CLOSED"
            ),
            "authority_flags_all_false": all(
                value is False for value in workflow_package_queue.AUTHORITY_BOUNDARY_DEFAULT.values()
            ),
            "email_send_performed": False,
            "ledger_mutation_performed": False,
            "browser_access_performed": False,
            "gmail_access_performed": False,
            "coupa_access_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "business_state_mutation_performed": False,
            "raw_text_stored_in_sqlite": False,
            "cross_lane_routing_evaluated": True,
            "cross_lane_routed": route["cross_lane_routed"],
            "unsafe_true_grants_absent": not _authority_blockers(raw_request),
        },
    }
    receipt = dynamic_card_packet.add_rail_card_packet(
        receipt,
        "workflow_package_request_consumer",
        read_model_root=DEFAULT_EXPORT_ROOT,
        generated_at=generated_at,
        source_key="workflow_package_request_consumer_status",
    )
    return WorkflowPackageRequestResult(
        status="RECORDED" if package is not None else "BLOCKED",
        request_id=request_id,
        request_filename=source_request_filename,
        package=package,
        blockers=blockers,
        response_primary_status=primary_status,
        next_safe_action=next_safe_action,
        receipt=receipt,
        typed_contract_trace=dict(business_contract_trace) or None,
    )
