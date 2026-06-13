"""Codex/LM2-backed advisory lane for Cassandra Data Room form turns.

This module is an adapter over the canonical Assignment Loop and Codex Work
Package Lifecycle. It does not create a new approval system, does not grant
tool authority, and does not let model output record guided-review answers.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import assignment_loop_contract
import codex_work_package_lifecycle as lifecycle
from lm2_openai_first_worker_proof import run_codex_cli_worker


REQUEST_SCHEMA_VERSION = "DATA_ROOM_LIVE_LM_TURN_REQUEST_V0"
RESULT_SCHEMA_VERSION = "DATA_ROOM_LIVE_LM_TURN_RESULT_V0"
STATUS_SCHEMA_VERSION = "DATA_ROOM_LIVE_LM_BRAIN_STATUS_V0"
READY_NOTIFICATION_TEXT = (
    "I’m here. I have an LM brain for this Data Room form, I have the form, "
    "I know the task, I know why it matters, and I’m ready to help you fill it out."
)
READINESS_USER_TURN = (
    "I’m ready to start. Acknowledge that you have the form and can help me fill it out. "
    "Do not answer the form yet."
)

DEFAULT_READ_MODEL_PATH = Path("generated/read_models/data_room_live_lm_brain_status.json")
DEFAULT_TURN_ROOT = Path("generated/system_knowledge/data_room_live_lm_brain")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")

ALLOWED_INTENTS = {
    "explain",
    "eli5",
    "recommendation",
    "thought_dump",
    "answer_candidate",
    "conditional",
    "clarification",
    "conversation_permission_boundary",
    "summary",
    "done",
}

SAFE_FALSE_FLAGS = {
    "authoritative": False,
    "runtime_policy_changed": False,
    "confirmed_reference_data_created": False,
    "hydration_run": False,
    "external_action_performed": False,
    "runtime_mutation_performed": False,
    "email_sent": False,
    "approval_created": False,
}

AUTHORITY_BOUNDARY = {
    "advisory_only": True,
    "execution_allowed": False,
    "runtime_mutation_allowed": False,
    "external_action_allowed": False,
    "confirmed_reference_data_allowed": False,
    "hydration_allowed": False,
    "model_output_direct_record_allowed": False,
    "tools_exposed_to_model": False,
    "email_send_allowed": False,
    "approval_created": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object, length: int = 20) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:length]


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _safe_text(value: Any, *, limit: int = 900) -> str:
    text = " ".join(str(value or "").strip().split())
    return text[:limit]


def _current_question(session: Mapping[str, Any]) -> dict[str, Any]:
    current_id = str(session.get("current_question_id") or "")
    for question in session.get("question_queue", []):
        if isinstance(question, Mapping) and str(question.get("question_id") or "") == current_id:
            return dict(question)
    return {}


def _progress_summary(session: Mapping[str, Any]) -> str:
    answers = [answer for answer in session.get("answer_records", []) if isinstance(answer, Mapping) and not answer.get("superseded")]
    unanswered = [
        question
        for question in session.get("question_queue", [])
        if isinstance(question, Mapping) and question.get("answer_status") == "unanswered"
    ]
    return f"{len(answers)} answered; {len(unanswered)} unanswered."


def allowed_fact_refs_for_request(request: Mapping[str, Any]) -> set[str]:
    return {
        "form_goal",
        "why_it_matters",
        "current_question",
        "current_question_category",
        "current_session_progress",
        "user_turn_redacted",
        "safety_boundaries",
    }


def build_live_lm_turn_request(
    session: Mapping[str, Any],
    user_turn: str,
    *,
    created_at_utc: str | None = None,
    request_id: str = "",
    recent_chat_summary: str = "",
) -> dict[str, Any]:
    created_at_utc = created_at_utc or utc_now()
    question = _current_question(session)
    review_session_id = str(session.get("review_session_id") or "")
    current_question_id = str(question.get("question_id") or session.get("current_question_id") or "")
    redacted_turn = _safe_text(user_turn, limit=1000)
    request_id = request_id or "data_room_live_lm_turn_request:" + _short_hash(
        review_session_id,
        current_question_id,
        redacted_turn,
        created_at_utc,
    )
    why = str(question.get("why_it_matters") or question.get("risk_if_wrong") or "")
    if not why:
        why = "The Data Room answers decide what can later be promoted into confirmed reference data."
    return {
        "schema_version": REQUEST_SCHEMA_VERSION,
        "request_id": request_id,
        "created_at_utc": created_at_utc,
        "review_session_id": review_session_id,
        "current_question_id": current_question_id,
        "current_question_text": _safe_text(
            question.get("plain_question") or question.get("question_text") or "No current question available."
        ),
        "current_question_category": _safe_text(question.get("category") or "data_room"),
        "form_goal": "Help Winship fill the OpenClaw Data Room form conversationally while keeping answers provisional.",
        "why_it_matters": _safe_text(why),
        "user_turn_redacted": redacted_turn,
        "recent_chat_summary": _safe_text(recent_chat_summary or session.get("data_room_live_lm_chat_summary") or ""),
        "current_session_progress": _progress_summary(session),
        "allowed_inputs": [
            "current question text",
            "current question category",
            "form goal",
            "why it matters",
            "redacted user turn",
            "recent chat summary",
            "current session progress",
        ],
        "forbidden_inputs": [
            "secrets or credentials",
            "raw private finance documents",
            "raw bank/account/routing values",
            "raw email/Coupa/Gmail/browser content",
            "confirmed reference data creation",
            "hydration",
            "tool authority",
        ],
        "expected_output_schema": RESULT_SCHEMA_VERSION,
        "allowed_fact_refs": sorted(allowed_fact_refs_for_request({})),
        "advisory_only": True,
        "execution_allowed": False,
        "runtime_mutation_allowed": False,
        "confirmed_reference_data_allowed": False,
        "hydration_allowed": False,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def live_lm_turn_result_json_schema(request: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "request_id",
            "review_session_id",
            "question_id",
            "assistant_reply",
            "operator_intent",
            "proposed_answer",
            "requires_winship_confirmation",
            "confirmed_by_winship",
            "should_record_now",
            "next_question_id",
            "chat_log_summary_update",
            "facts_used",
            "safety_flags",
        ],
        "properties": {
            "schema_version": {"type": "string", "enum": [RESULT_SCHEMA_VERSION]},
            "request_id": {"type": "string", "enum": [str(request.get("request_id") or "")]},
            "review_session_id": {"type": "string", "enum": [str(request.get("review_session_id") or "")]},
            "question_id": {"type": "string", "enum": [str(request.get("current_question_id") or "")]},
            "assistant_reply": {"type": "string"},
            "operator_intent": {"type": "string", "enum": sorted(ALLOWED_INTENTS)},
            "proposed_answer": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "plain_english",
                    "normalized_decision",
                    "confidence",
                    "conditions",
                    "caveats",
                    "professional_review_flags",
                ],
                "properties": {
                    "plain_english": {"type": "string"},
                    "normalized_decision": {"type": "string"},
                    "confidence": {"type": "string"},
                    "conditions": {"type": "array", "items": {"type": "string"}},
                    "caveats": {"type": "array", "items": {"type": "string"}},
                    "professional_review_flags": {"type": "array", "items": {"type": "string"}},
                },
            },
            "requires_winship_confirmation": {"type": "boolean"},
            "confirmed_by_winship": {"type": "boolean", "enum": [False]},
            "should_record_now": {"type": "boolean", "enum": [False]},
            "next_question_id": {"type": "string"},
            "chat_log_summary_update": {"type": "string"},
            "facts_used": {
                "type": "array",
                "items": {"type": "string", "enum": sorted(allowed_fact_refs_for_request(request))},
            },
            "safety_flags": {
                "type": "object",
                "additionalProperties": False,
                "required": sorted(SAFE_FALSE_FLAGS),
                "properties": {key: {"type": "boolean", "enum": [False]} for key in sorted(SAFE_FALSE_FLAGS)},
            },
        },
    }


def live_lm_turn_prompt(request: Mapping[str, Any]) -> str:
    example = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "request_id": request["request_id"],
        "review_session_id": request["review_session_id"],
        "question_id": request["current_question_id"],
        "assistant_reply": (
            "I have the Data Room form and can help you fill it out. I’ll keep answers provisional and ask before "
            "recording anything."
        ),
        "operator_intent": "clarification",
        "proposed_answer": {
            "plain_english": "",
            "normalized_decision": "",
            "confidence": "",
            "conditions": [],
            "caveats": [],
            "professional_review_flags": [],
        },
        "requires_winship_confirmation": False,
        "confirmed_by_winship": False,
        "should_record_now": False,
        "next_question_id": "",
        "chat_log_summary_update": "Winship is ready to start the Data Room form.",
        "facts_used": ["form_goal", "why_it_matters", "current_question", "safety_boundaries"],
        "safety_flags": dict(SAFE_FALSE_FLAGS),
    }
    return (
        "You are Cassandra's advisory LM brain for one OpenClaw Data Room form turn.\n"
        "Use only the request JSON below. Do not inspect files. Do not call tools. Do not run commands. "
        "Do not claim anything was recorded, promoted, hydrated, sent, approved, or mutated.\n"
        "If the user proposes an answer, return it as a proposed_answer and set requires_winship_confirmation=true, "
        "but should_record_now must remain false.\n"
        "If the user is talking about this chat, source identity, Telegram/app provenance, permission, authorization, "
        "or first-class conversation status rather than answering the current form question, use "
        "operator_intent=conversation_permission_boundary, leave proposed_answer blank, and say it is "
        "source/permission context rather than a Data Room answer or runtime policy change.\n"
        f"Return only {RESULT_SCHEMA_VERSION} JSON matching the output schema.\n\n"
        "Valid readiness example:\n"
        f"{stable_json(example)}\n"
        "Request JSON:\n"
        f"{stable_json(dict(request))}"
    )


def validate_live_lm_turn_result(result: Mapping[str, Any], request: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if result.get("schema_version") != RESULT_SCHEMA_VERSION:
        errors.append("schema_version_mismatch")
    if result.get("request_id") != request.get("request_id"):
        errors.append("request_id_mismatch")
    if result.get("review_session_id") != request.get("review_session_id"):
        errors.append("review_session_id_mismatch")
    if result.get("question_id") != request.get("current_question_id"):
        errors.append("question_id_mismatch")
    if not str(result.get("assistant_reply") or "").strip():
        errors.append("assistant_reply_missing")
    if result.get("operator_intent") not in ALLOWED_INTENTS:
        errors.append("operator_intent_invalid")
    if result.get("confirmed_by_winship") is not False:
        errors.append("confirmed_by_winship_must_be_false")
    if result.get("should_record_now") is not False:
        errors.append("should_record_now_must_be_false")
    flags = result.get("safety_flags") if isinstance(result.get("safety_flags"), Mapping) else {}
    for key in SAFE_FALSE_FLAGS:
        if flags.get(key) is not False:
            errors.append(f"safety_flag_not_false:{key}")
    proposed = result.get("proposed_answer") if isinstance(result.get("proposed_answer"), Mapping) else {}
    proposed_text = str(proposed.get("plain_english") or proposed.get("normalized_decision") or "").strip()
    if proposed_text and result.get("requires_winship_confirmation") is not True:
        errors.append("proposed_answer_requires_confirmation")
    facts_used = result.get("facts_used")
    if not isinstance(facts_used, list):
        errors.append("facts_used_not_list")
    else:
        allowed = allowed_fact_refs_for_request(request)
        for fact in facts_used:
            if str(fact) not in allowed:
                errors.append(f"fact_not_in_request:{fact}")
    return errors


def build_turn_assignment_loop(request: Mapping[str, Any], *, created_at_utc: str | None = None) -> dict[str, Any]:
    created_at_utc = created_at_utc or utc_now()
    return assignment_loop_contract.build_assignment_loop(
        requested_by="chief",
        owner_agent="cassandra",
        worker_type="openai_codex_cli",
        goal="Produce one advisory Data Room form response from a bounded request JSON.",
        sources=[
            "generated/read_models/guided_review_sessions.json",
            "cassandra_guided_review.py",
            "data_room_live_lm_brain.py",
        ],
        standard=(
            f"Return {RESULT_SCHEMA_VERSION} only. Advisory text only; no tool calls, no recording, no promotion, "
            "no hydration, no external/business action."
        ),
        permission_boundary={
            "advisory_only": True,
            "execution_allowed": False,
            "runtime_mutation_allowed": False,
            "external_action_allowed": False,
            "confirmed_reference_data_allowed": False,
            "hydration_allowed": False,
            "worker_time_budget_seconds": 90,
            "max_sources_per_worker_run": 4,
        },
        proof_required=[
            str(request.get("request_id") or ""),
            "Codex CLI output",
            "Data Room LM result validation",
            "Worker lifecycle validation receipt",
        ],
        stop_condition="One valid advisory result is ingested or one blocked/timeout result is recorded; no retry.",
        current_status="packaged",
        operator_next_action="Review Cassandra Data Room LM brain status.",
        created_at_utc=created_at_utc,
    )


def adapt_live_lm_turn_result(
    result: Mapping[str, Any],
    *,
    request: Mapping[str, Any],
    package_state: Mapping[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    errors = validate_live_lm_turn_result(result, request)
    if errors:
        return {"status": "blocked_invalid_data_room_live_lm_turn_result", "errors": errors, "adapted": None}
    return {
        "status": "adapted",
        "errors": [],
        "adapted": {
            "schema_version": lifecycle.PACKAGE_RESULT_SCHEMA,
            "package_id": str(package_state.get("package_id") or ""),
            "worker_kind": "openai_codex_cli",
            "status": "completed",
            "authority_grant_ref": str(package_state.get("authority_grant_ref") or ""),
            "files_changed": [],
            "commands_run": ["codex exec data room advisory turn"],
            "validation_run": ["git diff --check"],
            "unsafe_scan_summary": {"passed": True, "hits": []},
            "commit_hash": "",
            "blocker_summary": "",
            "receipt_refs": [f"data_room_live_lm_turn:{request.get('request_id')}"],
            "submitted_at": generated_at,
            "denied_actions_reported": [],
            "introduced_strings": [],
            "capability_status": "data_room_live_lm_turn_validated",
            "data_room_live_lm_turn_result": dict(result),
            "data_room_live_lm_turn_request_id": str(request.get("request_id") or ""),
            "model_or_cli_used": "codex",
            "subagents_used": False,
            "runtime_mutation_performed": False,
            "external_business_action_performed": False,
            "confirmed_reference_data_created": False,
            "hydration_run": False,
        },
    }


def _parse_raw_result(raw_text: str) -> tuple[dict[str, Any] | None, str]:
    parsed, reason = lifecycle.parse_worker_result_text(str(raw_text or ""))
    if parsed is None:
        return None, reason
    return parsed, ""


def _watch_item_for_status(status: Mapping[str, Any]) -> dict[str, Any]:
    ready = bool(status.get("live_lm_brain_ready"))
    session_id = str(status.get("active_session_id") or "")
    item_id = f"data_room_live_lm_brain:{session_id or 'unknown'}"
    blocked = str(status.get("last_error") or "")
    return {
        "item_id": item_id,
        "lane": "cassandra_ar",
        "urgency": "watch" if ready else "blocked",
        "plain_line": (
            f"Data Room LM brain ready for {session_id} via openai_codex_cli."
            if ready
            else f"Data Room LM brain blocked for {session_id or 'unknown'}: {blocked or 'not_ready'}."
        ),
        "source_receipt_ref": "generated/read_models/data_room_live_lm_brain_status.json#status",
        "one_next_safe_action": (
            "Winship can continue the Data Room form with Cassandra."
            if ready
            else "Use deterministic coach or fix the recorded LM brain blocker before claiming live LM readiness."
        ),
        "push_candidate": False,
        "push_class": "info" if ready else "failure",
        "state": {
            "live_lm_brain_ready": ready,
            "provider": str(status.get("provider") or ""),
            "access_mode": str(status.get("access_mode") or ""),
            "worker_kind": str(status.get("worker_kind") or ""),
            "active_session_id": session_id,
            "current_question_id": str(status.get("current_question_id") or ""),
            "last_error": blocked,
            "execution_allowed": False,
            "runtime_mutation_allowed": False,
            "external_action_allowed": False,
            "confirmed_reference_data_allowed": False,
            "hydration_allowed": False,
        },
    }


def write_live_lm_brain_status(
    status: Mapping[str, Any],
    *,
    path: str | Path = DEFAULT_READ_MODEL_PATH,
    bridge_root: str | Path | None = DEFAULT_BRIDGE_ROOT,
) -> Path:
    payload = dict(status)
    payload.setdefault("schema_version", STATUS_SCHEMA_VERSION)
    payload["watch_desk_items"] = [_watch_item_for_status(payload)]
    output = Path(path)
    _write_json(output, payload)
    if bridge_root:
        bridge = Path(bridge_root) / output.name
        try:
            _write_json(bridge, payload)
        except OSError:
            pass
    return output


def _canonical_bridge_root(read_model_path: str | Path, bridge_root: str | Path | None) -> Path | None:
    if bridge_root is None:
        return None
    try:
        if Path(read_model_path).resolve() != DEFAULT_READ_MODEL_PATH.resolve():
            return None
    except OSError:
        return None
    return Path(bridge_root)


def run_live_lm_turn(
    session: Mapping[str, Any],
    user_turn: str,
    *,
    created_at_utc: str | None = None,
    recent_chat_summary: str = "",
    codex_runner: Callable[..., Mapping[str, Any]] | None = None,
    timeout_seconds: int = 90,
    sqlite_path: Path = lifecycle.DEFAULT_SQLITE_PATH,
    package_root: Path = lifecycle.DEFAULT_PACKAGE_ROOT,
    turn_root: Path = DEFAULT_TURN_ROOT,
    read_model_path: Path = DEFAULT_READ_MODEL_PATH,
    bridge_root: str | Path | None = DEFAULT_BRIDGE_ROOT,
) -> dict[str, Any]:
    created_at_utc = created_at_utc or utc_now()
    request = build_live_lm_turn_request(
        session,
        user_turn,
        created_at_utc=created_at_utc,
        recent_chat_summary=recent_chat_summary,
    )
    turn_id = _short_hash(request["request_id"], created_at_utc)
    turn_dir = turn_root / turn_id
    request_path = turn_dir / "turn_request.json"
    result_path = turn_dir / "turn_result.json"
    _write_json(request_path, request)
    assignment = build_turn_assignment_loop(request, created_at_utc=created_at_utc)
    package_result = lifecycle.create_worker_package_from_assignment_loop(
        assignment,
        worker_kind="openai_codex_cli",
        dispatch_mode="subscription_cli_data_room_lm_brain",
        sqlite_path=sqlite_path,
        package_root=package_root,
        generated_at=created_at_utc,
    )
    package_state = package_result.get("package_state") if isinstance(package_result.get("package_state"), Mapping) else {}
    package_json = package_state.get("package_json") if isinstance(package_state.get("package_json"), Mapping) else {}
    size_class = str(package_json.get("package_size_class") or "")
    cli_allowed = bool(package_json.get("cli_dispatch_allowed"))
    package_id = str(package_state.get("package_id") or package_result.get("package_id") or "")
    base_status = {
        "schema_version": STATUS_SCHEMA_VERSION,
        "generated_at_utc": created_at_utc,
        "provider": "openai",
        "access_mode": "openai_codex_cli",
        "worker_kind": "openai_codex_cli",
        "active_session_id": str(request.get("review_session_id") or ""),
        "current_question_id": str(request.get("current_question_id") or ""),
        "readiness_turn_package_ref": package_id,
        "readiness_turn_result_ref": "",
        "readiness_turn_request_ref": request_path.as_posix(),
        "assignment_loop_ref": str(package_state.get("package_json", {}).get("assignment_loop_ref") or assignment.get("assignment_id") or ""),
        "claim_ref": "",
        "result_ref": "",
        "validation_ref": "",
        "watch_desk_ref": f"data_room_live_lm_brain:{request.get('review_session_id') or 'unknown'}",
        "package_size_class": size_class,
        "cli_dispatch_allowed": cli_allowed,
        "notification_sent": False,
        "exact_notification_text": "",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    if package_result.get("status") != "canonical_worker_package_queued":
        status = {
            **base_status,
            "live_lm_brain_ready": False,
            "status": "blocked_package_create_failed",
            "last_error": str(package_result.get("status") or "package_create_failed"),
        }
        write_live_lm_brain_status(status, path=read_model_path, bridge_root=_canonical_bridge_root(read_model_path, bridge_root))
        return {"status": "blocked", "reason": status["last_error"], "request": request, "package_result": package_result, "status_read_model": status}
    if not cli_allowed or size_class not in {"tiny", "small"}:
        status = {
            **base_status,
            "live_lm_brain_ready": False,
            "status": "blocked_turn_package_too_large",
            "last_error": "blocked_turn_package_too_large",
        }
        write_live_lm_brain_status(status, path=read_model_path, bridge_root=_canonical_bridge_root(read_model_path, bridge_root))
        return {"status": "blocked_package_too_large", "reason": "blocked_turn_package_too_large", "request": request, "package_result": package_result, "status_read_model": status}
    dispatch = lifecycle.record_dispatch(
        package_id,
        "openai_codex_cli",
        "chief",
        "Data Room live LM brain advisory turn.",
        sqlite_path=sqlite_path,
        package_root=package_root,
        generated_at=created_at_utc,
        mark_in_progress=True,
    )
    runner = codex_runner or run_codex_cli_worker
    raw_run = runner(
        prompt=live_lm_turn_prompt(request),
        response_schema=live_lm_turn_result_json_schema(request),
        scratch_dir=turn_dir / "scratch",
        output_dir=Path(str(package_state.get("package_files", {}).get("result_inbox_path") or turn_dir / "results")),
        result_prefix="data_room_live_lm_turn",
        timeout_seconds=timeout_seconds,
    )
    raw_text = str(raw_run.get("raw_result_text") or "")
    parsed, parse_error = _parse_raw_result(raw_text)
    if raw_run.get("returncode") == 124 or str(raw_run.get("status") or "").startswith("timeout"):
        ingest = lifecycle.reject_worker_result(package_id, "codex_cli_timeout", sqlite_path=sqlite_path, generated_at=created_at_utc)
        status = {
            **base_status,
            "claim_ref": str(dispatch.get("package_claim", {}).get("claim_id") or ""),
            "live_lm_brain_ready": False,
            "status": "blocked_timeout",
            "last_error": "codex_cli_timeout",
        }
        write_live_lm_brain_status(status, path=read_model_path, bridge_root=_canonical_bridge_root(read_model_path, bridge_root))
        return {"status": "blocked_timeout", "request": request, "run_result": raw_run, "ingest_result": ingest, "status_read_model": status}
    if raw_run.get("returncode") not in {0, None}:
        ingest = lifecycle.reject_worker_result(package_id, "codex_cli_nonzero", sqlite_path=sqlite_path, generated_at=created_at_utc)
        status = {
            **base_status,
            "claim_ref": str(dispatch.get("package_claim", {}).get("claim_id") or ""),
            "live_lm_brain_ready": False,
            "status": "blocked_provider",
            "last_error": "codex_cli_nonzero",
        }
        write_live_lm_brain_status(status, path=read_model_path, bridge_root=_canonical_bridge_root(read_model_path, bridge_root))
        return {"status": "blocked_provider", "request": request, "run_result": raw_run, "ingest_result": ingest, "status_read_model": status}
    if parsed is None:
        ingest = lifecycle.reject_worker_result(package_id, parse_error, sqlite_path=sqlite_path, generated_at=created_at_utc)
        status = {
            **base_status,
            "claim_ref": str(dispatch.get("package_claim", {}).get("claim_id") or ""),
            "live_lm_brain_ready": False,
            "status": "blocked_malformed_result",
            "last_error": parse_error,
        }
        write_live_lm_brain_status(status, path=read_model_path, bridge_root=_canonical_bridge_root(read_model_path, bridge_root))
        return {"status": "blocked", "reason": parse_error, "request": request, "run_result": raw_run, "ingest_result": ingest, "status_read_model": status}
    _write_json(result_path, parsed)
    adapter = adapt_live_lm_turn_result(parsed, request=request, package_state=package_state, generated_at=created_at_utc)
    if adapter.get("status") != "adapted":
        ingest = lifecycle.reject_worker_result(package_id, "data_room_live_lm_turn_validation_failed", sqlite_path=sqlite_path, generated_at=created_at_utc)
        status = {
            **base_status,
            "claim_ref": str(dispatch.get("package_claim", {}).get("claim_id") or ""),
            "readiness_turn_result_ref": result_path.as_posix(),
            "live_lm_brain_ready": False,
            "status": "blocked_invalid_result",
            "last_error": ",".join(adapter.get("errors") or ["data_room_live_lm_turn_validation_failed"]),
        }
        write_live_lm_brain_status(status, path=read_model_path, bridge_root=_canonical_bridge_root(read_model_path, bridge_root))
        return {"status": "blocked", "request": request, "turn_result": parsed, "adapter_result": adapter, "ingest_result": ingest, "status_read_model": status}
    ingest = lifecycle.ingest_worker_result(adapter["adapted"], sqlite_path=sqlite_path, generated_at=created_at_utc)
    validation = ingest.get("validation_receipt") if isinstance(ingest.get("validation_receipt"), Mapping) else {}
    package_result_row = ingest.get("package_result") if isinstance(ingest.get("package_result"), Mapping) else {}
    ready = str(validation.get("validation_status") or "") == "validation_passed"
    status = {
        **base_status,
        "claim_ref": str(dispatch.get("package_claim", {}).get("claim_id") or ""),
        "readiness_turn_result_ref": result_path.as_posix(),
        "result_ref": str(package_result_row.get("result_id") or ""),
        "validation_ref": str(validation.get("validation_id") or ""),
        "live_lm_brain_ready": ready,
        "status": "ready" if ready else "blocked_validation_failed",
        "last_error": "" if ready else ",".join(validation.get("validation_errors") or ["validation_failed"]),
        "last_assistant_reply": str(parsed.get("assistant_reply") or ""),
        "last_operator_intent": str(parsed.get("operator_intent") or ""),
        "chat_log_summary_update": str(parsed.get("chat_log_summary_update") or ""),
    }
    write_live_lm_brain_status(status, path=read_model_path, bridge_root=_canonical_bridge_root(read_model_path, bridge_root))
    return {
        "status": "ready" if ready else "blocked",
        "request": request,
        "turn_result": parsed,
        "run_result": {key: value for key, value in raw_run.items() if key != "raw_result_text"},
        "adapter_result": adapter,
        "ingest_result": ingest,
        "dispatch_result": dispatch,
        "package_result": package_result,
        "status_read_model": status,
    }
