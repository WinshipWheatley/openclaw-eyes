"""Live ChatGPT 5.5 advisory adapter for Cassandra's Data Room lane.

This adapter is intentionally narrow: one advisory-only Responses API call,
no tools, no runtime mutation, and strict validation before Cassandra can use
the model's reply.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


ENABLE_ENV = "OPENCLAW_ENABLE_LIVE_CHATGPT55"
MODEL_ENV = "OPENCLAW_CHATGPT55_MODEL"
API_KEY_ENV = "OPENAI_API_KEY"
DEFAULT_MODEL_LABEL = "gpt-5.5"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

REQUEST_SCHEMA_VERSION = "LIVE_CHATGPT55_DATA_ROOM_ADVISORY_REQUEST_V0"
TURN_RESULT_SCHEMA_VERSION = "DATA_ROOM_LIVE_CHATGPT55_TURN_RESULT_V0"
LANE_STATE_SCHEMA_VERSION = "DATA_ROOM_LIVE_CHATGPT55_LANE_STATE_V0"
VALIDATION_SCHEMA_VERSION = "DATA_ROOM_LIVE_CHATGPT55_TURN_VALIDATION_V0"

DEFAULT_LIVE_LANE_READ_MODEL_PATH = Path("generated/read_models/data_room_live_chatgpt55_lane.json")
DEFAULT_LIVE_LANE_PRIMARY_ROOT = Path("/tmp/openclaw-mission-control/operator_skill_factory_v0/data_room_live_chatgpt55")
DEFAULT_LIVE_LANE_DURABLE_ROOT = Path("generated/system_knowledge/operator_skill_factory/data_room_live_chatgpt55")

READINESS_PROMPT = "Acknowledge readiness for helping with this Data Room form. Do not answer the form yet."

OPERATOR_INTENTS = {
    "explain",
    "eli5",
    "analogy",
    "recommendation",
    "thought_dump",
    "answer_candidate",
    "confirm",
    "revise",
    "conditional",
    "skip",
    "defer",
    "summary",
    "done",
    "clarification",
}

SAFE_TURN_SAFETY_FLAGS = {
    "authoritative": False,
    "runtime_policy_changed": False,
    "confirmed_reference_data_created": False,
    "tax_or_legal_advice_given": False,
    "medical_advice_given": False,
    "external_action_performed": False,
    "execution_attempted": False,
}

_RAW_IDENTIFIER_PATTERNS = (
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b\d{2}-\d{7}\b"),
    re.compile(r"\b\d{9,}\b"),
    re.compile(r"\b(?:routing|account|ssn|ein|tax id|tax identifier)\s*(?:number)?\s*[:#-]?\s*\d", re.IGNORECASE),
)

_PROFESSIONAL_ADVICE_PATTERNS = (
    re.compile(r"\b(tax|legal|medical)\s+advice\b", re.IGNORECASE),
    re.compile(r"\byou\s+should\s+deduct\b", re.IGNORECASE),
    re.compile(r"\bdeduct(?:ion|ible)?\b", re.IGNORECASE),
    re.compile(r"\bdiagnos(?:e|is)\b", re.IGNORECASE),
    re.compile(r"\btreat(?:ment)?\b", re.IGNORECASE),
    re.compile(r"\btherapy\b", re.IGNORECASE),
)

_FORBIDDEN_ACTION_PATTERNS = (
    re.compile(r"<\s*/?\s*(?:script|html|iframe|object)\b", re.IGNORECASE),
    re.compile(r"\b(?:tool_call|function_call|call a tool|use a tool)\b", re.IGNORECASE),
    re.compile(r"\b(?:execute|run command|shell command)\b", re.IGNORECASE),
    re.compile(r"\b(?:send email|create gmail draft|gmail|calendar|contacts|coupa|browser|apple mail)\b", re.IGNORECASE),
    re.compile(r"\b(?:mark(?:ed)? paid|ledger|workbook|pdf|bank transfer)\b", re.IGNORECASE),
    re.compile(r"\b(?:logic|ableton|obs|daw)\b", re.IGNORECASE),
    re.compile(r"\b(?:create guardian approval|approval request)\b", re.IGNORECASE),
)


class ChatGPT55AdapterError(RuntimeError):
    """Fail-closed adapter error with a machine-readable reason."""

    def __init__(
        self,
        reason: str,
        *,
        validation: Mapping[str, Any] | None = None,
        availability: Mapping[str, bool] | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.validation = dict(validation or {})
        self.availability = dict(availability or {})


Provider = Callable[..., Mapping[str, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object, length: int = 20) -> str:
    blob = "\0".join(str(part) for part in parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:length]


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def model_label(env: Mapping[str, str] | None = None) -> str:
    env = env or os.environ
    return str(env.get(MODEL_ENV) or DEFAULT_MODEL_LABEL).strip() or DEFAULT_MODEL_LABEL


def is_live_chatgpt55_available(env: Mapping[str, str] | None = None) -> dict[str, bool]:
    """Return booleans only; never print or expose credential values."""

    env = env or os.environ
    provider_enabled = _truthy(env.get(ENABLE_ENV))
    credential_present = bool(str(env.get(API_KEY_ENV) or "").strip())
    model_label_present = bool(model_label(env))
    return {
        "adapter_present": True,
        "provider_enabled": provider_enabled,
        "credential_present": credential_present,
        "model_label_present": model_label_present,
        "available": bool(provider_enabled and credential_present and model_label_present),
        "blocked_provider_disabled": not provider_enabled,
        "blocked_operator_config_required": provider_enabled and not credential_present,
        "blocked_model_missing": provider_enabled and credential_present and not model_label_present,
    }


def availability_blocked_reason(availability: Mapping[str, bool]) -> str:
    if not availability.get("provider_enabled"):
        return "blocked_provider_disabled"
    if not availability.get("credential_present"):
        return "blocked_operator_config_required"
    if not availability.get("model_label_present"):
        return "blocked_model_missing"
    if not availability.get("available"):
        return "blocked_adapter_unavailable"
    return ""


def safe_next_operator_step(reason: str) -> str:
    if reason == "blocked_provider_disabled":
        return (
            "Set OPENCLAW_ENABLE_LIVE_CHATGPT55=1 in the approved cassandra-listener.service "
            "runtime environment, then restart only cassandra-listener.service."
        )
    if reason == "blocked_operator_config_required":
        return (
            "Provide OPENAI_API_KEY in the approved cassandra-listener.service runtime environment "
            "without printing it, then restart only cassandra-listener.service."
        )
    if reason == "blocked_model_missing":
        return "Set OPENCLAW_CHATGPT55_MODEL or allow the default gpt-5.5 model label, then retry the Cassandra command."
    return "Review generated/read_models/data_room_live_chatgpt55_lane.json, fix the adapter failure, and retry the Cassandra command."


def _redact_text(value: Any) -> str:
    text = str(value or "")
    for pattern in _RAW_IDENTIFIER_PATTERNS:
        text = pattern.sub("[REDACTED_SENSITIVE_DETAIL]", text)
    secret_terms = (
        "api key",
        "api_key",
        "credential",
        "credentials",
        "oauth",
        "password",
        "private key",
        "secret",
        "token",
    )
    lowered = text.lower()
    if any(term in lowered for term in secret_terms):
        text = re.sub(r"(?i)(api[_ ]?key|credential|oauth|password|private key|secret|token)[^,\n.]*", "[REDACTED_SECRET_REF]", text)
    return text


def _safe_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [_redact_text(value) for value in values if str(value or "").strip()]


def _safe_question(question: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "question_id": _redact_text(question.get("question_id") or ""),
        "category": _redact_text(question.get("category") or ""),
        "question_text": _redact_text(question.get("question_text") or ""),
        "context_summary": _redact_text(question.get("context_summary") or ""),
        "source_record_ids": _safe_list(question.get("source_record_ids") or question.get("affected_records") or []),
        "proposed_options": _safe_list(question.get("proposed_options") or []),
        "risk_if_wrong": _redact_text(question.get("risk_if_wrong") or ""),
        "recommended_action": _redact_text(question.get("recommended_action") or ""),
        "answer_status": _redact_text(question.get("answer_status") or ""),
        "authoritative": False,
    }


def _question_summaries(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    return [_safe_question(item) for item in values if isinstance(item, Mapping)]


def redact_data_room_package_for_lm(package: Mapping[str, Any]) -> dict[str, Any]:
    """Return only redacted Data Room context needed by the advisory model."""

    current = package.get("current_question") if isinstance(package.get("current_question"), Mapping) else {}
    coach_pack = package.get("coach_pack_summary") if isinstance(package.get("coach_pack_summary"), Mapping) else {}
    return {
        "package_id": _redact_text(package.get("package_id") or ""),
        "review_session_id": _redact_text(package.get("review_session_id") or ""),
        "current_question_id": _redact_text(package.get("current_question_id") or ""),
        "question_index": int(package.get("current_question_index") or 0),
        "total_questions": int(package.get("total_questions") or 0),
        "form_title": _redact_text(package.get("form_title") or ""),
        "current_question": _safe_question(current),
        "answered_questions_summary": _question_summaries(package.get("answered_questions") or []),
        "skipped_questions_summary": _question_summaries(package.get("skipped_questions") or []),
        "deferred_questions_summary": _question_summaries(package.get("deferred_questions") or []),
        "unresolved_questions_summary": _question_summaries(package.get("unresolved_questions") or []),
        "coach_pack_summary": {
            key: _safe_list(value) if isinstance(value, list) else _redact_text(value)
            for key, value in coach_pack.items()
            if key in {
                "question_id",
                "category",
                "plain_context",
                "recommended_default",
                "why_it_matters",
                "examples",
                "professional_review_flags",
            }
        },
        "prior_chat_log_summary": _redact_text(package.get("prior_chat_log_summary") or ""),
        "done_criteria": dict(package.get("done_criteria") or {}),
    }


def expected_live_turn_result_shape() -> dict[str, Any]:
    return {
        "schema_version": TURN_RESULT_SCHEMA_VERSION,
        "request_id": "",
        "review_session_id": "",
        "question_id": "",
        "assistant_reply": "",
        "operator_intent": "explain|eli5|analogy|recommendation|thought_dump|answer_candidate|confirm|revise|conditional|skip|defer|summary|done|clarification",
        "proposed_answer": {
            "plain_english": "",
            "normalized_decision": "",
            "confidence": "high|medium|low",
            "conditions": [],
            "caveats": [],
            "professional_review_flags": [],
        },
        "requires_winship_confirmation": True,
        "confirmed_by_winship": False,
        "should_record_now": False,
        "next_question_id": "",
        "chat_log_summary_update": "",
        "done_criteria_met": False,
        "facts_used": [],
        "safety_flags": dict(SAFE_TURN_SAFETY_FLAGS),
    }


def live_turn_result_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "schema_version": {"type": "string", "enum": [TURN_RESULT_SCHEMA_VERSION]},
            "request_id": {"type": "string"},
            "review_session_id": {"type": "string"},
            "question_id": {"type": "string"},
            "assistant_reply": {"type": "string"},
            "operator_intent": {"type": "string", "enum": sorted(OPERATOR_INTENTS)},
            "proposed_answer": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "plain_english": {"type": "string"},
                    "normalized_decision": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low", ""]},
                    "conditions": {"type": "array", "items": {"type": "string"}},
                    "caveats": {"type": "array", "items": {"type": "string"}},
                    "professional_review_flags": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "plain_english",
                    "normalized_decision",
                    "confidence",
                    "conditions",
                    "caveats",
                    "professional_review_flags",
                ],
            },
            "requires_winship_confirmation": {"type": "boolean"},
            "confirmed_by_winship": {"type": "boolean", "enum": [False]},
            "should_record_now": {"type": "boolean", "enum": [False]},
            "next_question_id": {"type": "string"},
            "chat_log_summary_update": {"type": "string"},
            "done_criteria_met": {"type": "boolean"},
            "facts_used": {"type": "array", "items": {"type": "string"}},
            "safety_flags": {
                "type": "object",
                "additionalProperties": False,
                "properties": {key: {"type": "boolean", "enum": [False]} for key in SAFE_TURN_SAFETY_FLAGS},
                "required": list(SAFE_TURN_SAFETY_FLAGS),
            },
        },
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
            "done_criteria_met",
            "facts_used",
            "safety_flags",
        ],
    }


def build_live_chatgpt55_advisory_request(
    package: Mapping[str, Any],
    user_turn: str,
    recent_chat_log: str = "",
    *,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    created = created_at_utc or utc_now()
    redacted = redact_data_room_package_for_lm(package)
    request_id = "live_chatgpt55_data_room_advisory:" + _short_hash(
        redacted.get("review_session_id"),
        redacted.get("current_question_id"),
        user_turn,
        created,
    )
    return {
        "schema_version": REQUEST_SCHEMA_VERSION,
        "request_id": request_id,
        "created_at_utc": created,
        "review_session_id": redacted["review_session_id"],
        "current_question_id": redacted["current_question_id"],
        "question_index": redacted["question_index"],
        "total_questions": redacted["total_questions"],
        "user_turn_redacted": _redact_text(user_turn),
        "recent_chat_log_summary": _redact_text(recent_chat_log or redacted.get("prior_chat_log_summary") or ""),
        "current_question": redacted["current_question"],
        "answered_questions_summary": redacted["answered_questions_summary"],
        "skipped_questions_summary": redacted["skipped_questions_summary"],
        "deferred_questions_summary": redacted["deferred_questions_summary"],
        "unresolved_questions_summary": redacted["unresolved_questions_summary"],
        "coach_pack_summary": redacted["coach_pack_summary"],
        "safety_boundaries": {
            "advisory_only": True,
            "no_tools": True,
            "no_external_action": True,
            "no_runtime_mutation": True,
            "no_confirmed_reference_data": True,
            "no_hydration": True,
            "no_tax_legal_medical_advice": True,
        },
        "allowed_inputs": [
            "redacted Data Room question summaries",
            "redacted recent chat summary",
            "coach pack summary",
            "expected output schema",
        ],
        "forbidden_inputs": [
            "credentials",
            "tokens",
            "secrets",
            "raw account or routing values",
            "raw tax identifiers",
            "Gmail bodies",
            "workbook bodies",
            "PDF bodies",
            "external action instructions",
        ],
        "expected_output_schema": expected_live_turn_result_shape(),
        "advisory_only": True,
        "runtime_mutation_allowed": False,
        "execution_allowed": False,
        "confirmed_reference_data_allowed": False,
        "hydration_allowed": False,
        "external_action_allowed": False,
    }


def _responses_payload(request_payload: Mapping[str, Any], *, model: str) -> dict[str, Any]:
    system = (
        "You are Cassandra's live ChatGPT 5.5 advisory brain for one OpenClaw Data Room form-fill lane. "
        "Return strict JSON only. You have no tools. You do not execute, mutate runtime, create confirmed "
        "reference data, hydrate data, create approvals, send email, or perform external actions. "
        "You may advise conversationally and propose answer candidates, but OpenClaw records only after "
        "Winship confirms through deterministic rails."
    )
    return {
        "model": model,
        "input": [
            {"role": "system", "content": system},
            {"role": "user", "content": stable_json(request_payload)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "data_room_live_chatgpt55_turn_result_v0",
                "strict": True,
                "schema": live_turn_result_json_schema(),
            }
        },
        "max_output_tokens": 1800,
    }


def _perform_openai_responses_call(
    *,
    request_payload: Mapping[str, Any],
    request_body: Mapping[str, Any],
    model_label: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    api_key = os.environ.get(API_KEY_ENV, "")
    if not api_key:
        raise ChatGPT55AdapterError("blocked_operator_config_required")
    data = json.dumps(request_body).encode("utf-8")
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ChatGPT55AdapterError(f"adapter_api_http_{exc.code}") from exc
    except TimeoutError as exc:
        raise ChatGPT55AdapterError("adapter_timeout") from exc
    except Exception as exc:
        raise ChatGPT55AdapterError("adapter_api_error") from exc


def _extract_output_text(raw_response: Mapping[str, Any]) -> str:
    status = str(raw_response.get("status") or "")
    if status and status != "completed":
        raise ChatGPT55AdapterError(f"adapter_response_{status}")
    output = raw_response.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, Mapping):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, Mapping):
                    continue
                if part.get("type") == "refusal":
                    raise ChatGPT55AdapterError("adapter_model_refusal")
                if part.get("type") in {"output_text", "text"} and isinstance(part.get("text"), str):
                    return str(part["text"])
    output_text = raw_response.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text
    raise ChatGPT55AdapterError("adapter_missing_output_text")


def _allowed_fact_refs(package: Mapping[str, Any]) -> set[str]:
    refs: set[str] = set()

    def add_question(question: Mapping[str, Any]) -> None:
        for key in ("question_id", "category"):
            value = str(question.get(key) or "").strip()
            if value:
                refs.add(value)
        for key in ("source_record_ids", "affected_records"):
            values = question.get(key)
            if isinstance(values, list):
                refs.update(str(value) for value in values if str(value or "").strip())

    for section in ("form_questions", "answered_questions", "skipped_questions", "deferred_questions", "unresolved_questions"):
        values = package.get(section)
        if isinstance(values, list):
            for item in values:
                if isinstance(item, Mapping):
                    add_question(item)
    current = package.get("current_question")
    if isinstance(current, Mapping):
        add_question(current)
    for key in ("package_id", "review_session_id", "current_question_id"):
        value = str(package.get(key) or "").strip()
        if value:
            refs.add(value)
    return refs


def _clean_safety_flags(flags: Mapping[str, Any]) -> bool:
    for key, expected in SAFE_TURN_SAFETY_FLAGS.items():
        if bool(flags.get(key, False)) != expected:
            return False
    for key, value in flags.items():
        if key not in SAFE_TURN_SAFETY_FLAGS and bool(value):
            return False
    return True


def _text_for_safety_scan(result: Mapping[str, Any]) -> str:
    answer = result.get("proposed_answer") if isinstance(result.get("proposed_answer"), Mapping) else {}
    parts = [
        str(result.get("assistant_reply") or ""),
        str(answer.get("plain_english") or ""),
        str(answer.get("normalized_decision") or ""),
    ]
    for key in ("conditions", "caveats"):
        values = answer.get(key)
        if isinstance(values, list):
            parts.extend(str(value) for value in values)
    return "\n".join(parts)


def validate_chatgpt55_turn_result(
    result: Mapping[str, Any],
    *,
    package: Mapping[str, Any] | None = None,
    request_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    if result.get("schema_version") != TURN_RESULT_SCHEMA_VERSION:
        errors.append("invalid_schema_version")
    if request_payload and result.get("request_id") != request_payload.get("request_id"):
        errors.append("request_id_mismatch")
    if request_payload and result.get("review_session_id") != request_payload.get("review_session_id"):
        errors.append("review_session_id_mismatch")
    if request_payload and result.get("question_id") != request_payload.get("current_question_id"):
        errors.append("question_id_mismatch")
    if not str(result.get("assistant_reply") or "").strip():
        errors.append("missing_assistant_reply")
    if str(result.get("operator_intent") or "") not in OPERATOR_INTENTS:
        errors.append("invalid_operator_intent")
    answer = result.get("proposed_answer")
    if not isinstance(answer, Mapping):
        errors.append("missing_proposed_answer")
    else:
        if str(answer.get("confidence") or "") not in {"high", "medium", "low", ""}:
            errors.append("invalid_confidence")
        for key in ("conditions", "caveats", "professional_review_flags"):
            if not isinstance(answer.get(key), list):
                errors.append(f"invalid_{key}")
    if bool(result.get("confirmed_by_winship")):
        errors.append("model_attempted_confirmation")
    if bool(result.get("should_record_now")):
        errors.append("model_attempted_record")
    flags = result.get("safety_flags")
    if not isinstance(flags, Mapping) or not _clean_safety_flags(flags):
        errors.append("safety_flags_not_clean")
    facts = result.get("facts_used")
    if not isinstance(facts, list):
        errors.append("invalid_facts_used")
    elif package is not None:
        allowed = _allowed_fact_refs(package)
        unknown = [str(fact) for fact in facts if str(fact or "").strip() and str(fact) not in allowed]
        if unknown:
            errors.append("facts_used_outside_package")
    text = _text_for_safety_scan(result)
    if any(pattern.search(text) for pattern in _RAW_IDENTIFIER_PATTERNS):
        errors.append("raw_identifier_detected")
    if any(pattern.search(text) for pattern in _PROFESSIONAL_ADVICE_PATTERNS):
        errors.append("professional_advice_detected")
    if any(pattern.search(text) for pattern in _FORBIDDEN_ACTION_PATTERNS):
        errors.append("forbidden_action_or_tool_instruction")
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "valid": not errors,
        "errors": errors,
        "confirmed_by_winship": bool(result.get("confirmed_by_winship")),
        "should_record_now": bool(result.get("should_record_now")),
        "safety_flags_clean": isinstance(flags, Mapping) and _clean_safety_flags(flags),
    }


def call_chatgpt55_data_room_advisory(
    package: Mapping[str, Any],
    user_turn: str,
    recent_chat_log: str = "",
    *,
    provider: Provider | None = None,
    created_at_utc: str | None = None,
    timeout_seconds: int = 45,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = env or os.environ
    availability = is_live_chatgpt55_available(env)
    reason = availability_blocked_reason(availability)
    if reason:
        raise ChatGPT55AdapterError(reason, availability=availability)

    request_payload = build_live_chatgpt55_advisory_request(
        package,
        user_turn,
        recent_chat_log,
        created_at_utc=created_at_utc,
    )
    selected_model = model_label(env)
    request_body = _responses_payload(request_payload, model=selected_model)
    call_provider = provider or _perform_openai_responses_call
    try:
        raw_response = call_provider(
            request_payload=request_payload,
            request_body=request_body,
            model_label=selected_model,
            timeout_seconds=timeout_seconds,
        )
    except ChatGPT55AdapterError:
        raise
    except TimeoutError as exc:
        raise ChatGPT55AdapterError("adapter_timeout") from exc
    except Exception as exc:
        raise ChatGPT55AdapterError("adapter_api_error") from exc

    output_text = _extract_output_text(raw_response)
    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise ChatGPT55AdapterError("adapter_invalid_json") from exc
    if not isinstance(parsed, dict):
        raise ChatGPT55AdapterError("adapter_invalid_json")
    validation = validate_chatgpt55_turn_result(parsed, package=package, request_payload=request_payload)
    if not validation["valid"]:
        raise ChatGPT55AdapterError("adapter_validation_failed", validation=validation, availability=availability)
    return parsed


def result_id_for(result: Mapping[str, Any]) -> str:
    return "data_room_live_chatgpt55_turn_result:" + _short_hash(
        result.get("request_id"),
        result.get("review_session_id"),
        result.get("question_id"),
        result.get("assistant_reply"),
    )


def build_watch_desk_item_for_lane(state: Mapping[str, Any]) -> dict[str, Any]:
    session_id = str(state.get("active_review_session_id") or "")
    live_ready = bool(state.get("live_ready"))
    status = str(state.get("lane_status") or ("active" if live_ready else "blocked"))
    item_id = f"data_room_live_chatgpt55:{session_id or 'no_active_session'}"
    if live_ready:
        plain = f"ChatGPT 5.5 Data Room lane active for {session_id}."
        urgency = "watch"
        push_class = "info"
    else:
        reason = str(state.get("blocked_reason") or "unavailable")
        plain = f"ChatGPT 5.5 Data Room lane blocked for {session_id or 'the active review'}: {reason}."
        urgency = "blocked"
        push_class = "failure"
    return {
        "item_id": item_id,
        "lane": "cassandra_ar",
        "urgency": urgency,
        "plain_line": plain,
        "source_receipt_ref": "generated/read_models/data_room_live_chatgpt55_lane.json#lane",
        "one_next_safe_action": (
            "Continue the Data Room review in Cassandra; model advice remains advisory-only."
            if live_ready
            else safe_next_operator_step(str(state.get("blocked_reason") or "adapter_failure"))
        ),
        "push_class": push_class,
        "state": {
            "lane_status": status,
            "live_ready": live_ready,
            "model_label": str(state.get("model_label") or ""),
            "active_review_session_id": session_id,
            "current_question_id": str(state.get("current_question_id") or ""),
            "blocked_reason": str(state.get("blocked_reason") or ""),
            "external_action_allowed": False,
            "runtime_mutation_allowed": False,
            "confirmed_reference_data_allowed": False,
            "hydration_allowed": False,
            "execution_allowed": False,
        },
    }


def build_data_room_live_chatgpt55_lane_state(
    *,
    package: Mapping[str, Any] | None = None,
    result: Mapping[str, Any] | None = None,
    availability: Mapping[str, bool] | None = None,
    lane_status: str,
    live_ready: bool,
    blocked_reason: str = "",
    generated_at_utc: str | None = None,
    recent_chat_summary: str = "",
    model: str = "",
) -> dict[str, Any]:
    package = package or {}
    result = result or {}
    availability = dict(availability or is_live_chatgpt55_available())
    state = {
        "schema_version": LANE_STATE_SCHEMA_VERSION,
        "lane_id": "data_room_live_chatgpt55",
        "generated_at_utc": generated_at_utc or utc_now(),
        "lane_status": lane_status,
        "live_ready": bool(live_ready),
        "model_label": model or model_label(),
        "availability_check": availability,
        "last_advisory_request_id": str(result.get("request_id") or ""),
        "last_result_id": result_id_for(result) if result else "",
        "active_review_session_id": str(package.get("review_session_id") or result.get("review_session_id") or ""),
        "current_question_id": str(package.get("current_question_id") or result.get("question_id") or ""),
        "recent_chat_summary": _redact_text(recent_chat_summary or result.get("chat_log_summary_update") or ""),
        "blocked_reason": blocked_reason,
        "safety_flags": dict(SAFE_TURN_SAFETY_FLAGS),
        "advisory_only": True,
        "runtime_mutation_allowed": False,
        "execution_allowed": False,
        "confirmed_reference_data_allowed": False,
        "hydration_allowed": False,
        "external_action_allowed": False,
        "push_allowed": False,
    }
    state["watch_desk_items"] = [build_watch_desk_item_for_lane(state)]
    return state


def write_data_room_live_chatgpt55_lane_state(
    state: Mapping[str, Any],
    *,
    read_model_path: str | Path | None = None,
    primary_root: str | Path | None = None,
    durable_root: str | Path | None = None,
) -> dict[str, str]:
    read_path = Path(read_model_path or DEFAULT_LIVE_LANE_READ_MODEL_PATH)
    primary = Path(primary_root or DEFAULT_LIVE_LANE_PRIMARY_ROOT) / "data_room_live_chatgpt55_lane.json"
    durable = Path(durable_root or DEFAULT_LIVE_LANE_DURABLE_ROOT) / "data_room_live_chatgpt55_lane.json"
    for path in (read_path, primary, durable):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(stable_json(dict(state)), encoding="utf-8")
    return {
        "read_model_path": read_path.as_posix(),
        "primary_path": primary.as_posix(),
        "durable_path": durable.as_posix(),
    }


def load_data_room_live_chatgpt55_lane_state(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path or DEFAULT_LIVE_LANE_READ_MODEL_PATH)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


__all__ = [
    "ChatGPT55AdapterError",
    "DEFAULT_LIVE_LANE_DURABLE_ROOT",
    "DEFAULT_LIVE_LANE_PRIMARY_ROOT",
    "DEFAULT_LIVE_LANE_READ_MODEL_PATH",
    "DEFAULT_MODEL_LABEL",
    "READINESS_PROMPT",
    "REQUEST_SCHEMA_VERSION",
    "SAFE_TURN_SAFETY_FLAGS",
    "TURN_RESULT_SCHEMA_VERSION",
    "availability_blocked_reason",
    "build_data_room_live_chatgpt55_lane_state",
    "build_live_chatgpt55_advisory_request",
    "build_watch_desk_item_for_lane",
    "call_chatgpt55_data_room_advisory",
    "expected_live_turn_result_shape",
    "is_live_chatgpt55_available",
    "live_turn_result_json_schema",
    "load_data_room_live_chatgpt55_lane_state",
    "model_label",
    "redact_data_room_package_for_lm",
    "result_id_for",
    "safe_next_operator_step",
    "stable_json",
    "validate_chatgpt55_turn_result",
    "write_data_room_live_chatgpt55_lane_state",
]
