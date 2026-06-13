"""Live Gemini advisory wrapper for Cassandra's Data Room form lane.

This module owns Data Room-specific redaction, schema validation, and additive
Gemini form session artifacts. The actual provider call routes through the
systemwide LM Consult Spine. Gemini advises only; OpenClaw records only
deterministic, Winship-confirmed answers.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


ENABLE_ENV = "OPENCLAW_ENABLE_LIVE_GEMINI_FORM"
MODEL_ENV = "OPENCLAW_GEMINI_FORM_MODEL"
GENERIC_MODEL_ENV = "OPENCLAW_GEMINI_MODEL"
GEMINI_CREDENTIAL_ENVS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY")
DEFAULT_MODEL_LABEL = ""
GEMINI_GENERATE_CONTENT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

REQUEST_SCHEMA_VERSION = "DATA_ROOM_GEMINI_FORM_TURN_REQUEST_V0"
TURN_RESULT_SCHEMA_VERSION = "DATA_ROOM_GEMINI_FORM_TURN_RESULT_V0"
FORM_SESSION_SCHEMA_VERSION = "DATA_ROOM_GEMINI_FORM_SESSION_V0"
VALIDATION_SCHEMA_VERSION = "DATA_ROOM_GEMINI_FORM_TURN_VALIDATION_V0"
TURN_LOG_SCHEMA_VERSION = "DATA_ROOM_GEMINI_FORM_TURN_LOG_ENTRY_V0"

CODEX_FINALIZER_CAPABILITY_ID = "OPENCLAW_DATA_ROOM_CONFIRMED_REFERENCE_PROMOTION_AND_HYDRATION_V0"

DEFAULT_FORM_SESSION_READ_MODEL_PATH = Path("generated/read_models/data_room_gemini_form_session.json")
DEFAULT_FORM_PRIMARY_ROOT = Path("/tmp/openclaw-mission-control/operator_skill_factory_v0/data_room_gemini_form")
DEFAULT_FORM_DURABLE_ROOT = Path("generated/system_knowledge/operator_skill_factory/data_room_gemini_form")
DEFAULT_CODEX_FINALIZER_SQLITE_PATH = Path("generated/system_knowledge/codex_work_package_lifecycle.sqlite")
DEFAULT_CODEX_FINALIZER_PACKAGE_ROOT = Path("generated/system_knowledge/work_packages")

READINESS_PROMPT = "Acknowledge readiness for helping with this Data Room form. Do not answer the form yet."
GEMINI_FORM_READINESS_NOTIFICATION = (
    "I'm here. My Data Room brain is Gemini Flash, I have the form, and I'm ready to help you fill it out."
)

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


class GeminiFormAdapterError(RuntimeError):
    """Fail-closed adapter error with a machine-readable reason."""

    def __init__(
        self,
        reason: str,
        *,
        validation: Mapping[str, Any] | None = None,
        availability: Mapping[str, Any] | None = None,
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


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "")).strip("_") or "session"


def model_label(env: Mapping[str, str] | None = None) -> str:
    env = env or os.environ
    return str(model_label_resolution(env).get("effective_model_label") or "")


def model_label_resolution(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    import openclaw_lm_consult_spine as consult_spine

    return consult_spine.gemini_model_label_status(env or os.environ)


def _credential_present(env: Mapping[str, str]) -> bool:
    return any(bool(str(env.get(name) or "").strip()) for name in GEMINI_CREDENTIAL_ENVS)


def _credential_value_from_env() -> str:
    for name in GEMINI_CREDENTIAL_ENVS:
        value = os.environ.get(name, "")
        if str(value or "").strip():
            return value
    return ""


def is_live_gemini_form_available(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return booleans only; never expose credential values."""

    env = env or os.environ
    provider_enabled = _truthy(env.get(ENABLE_ENV))
    credential_present = _credential_present(env)
    model_status = model_label_resolution(env)
    model_label_present = bool(model_status.get("effective_model_label"))
    model_label_mismatch = bool(model_status.get("model_label_mismatch"))
    return {
        "adapter_present": True,
        "provider_enabled": provider_enabled,
        "credential_present": credential_present,
        "model_label_present": model_label_present,
        **model_status,
        "available": bool(provider_enabled and credential_present and model_label_present and not model_label_mismatch),
        "blocked_provider_disabled": not provider_enabled,
        "blocked_operator_config_required": provider_enabled and not credential_present,
        "blocked_model_missing": provider_enabled and credential_present and not model_label_present and not model_label_mismatch,
        "blocked_model_label_mismatch": model_label_mismatch,
    }


def availability_blocked_reason(availability: Mapping[str, Any]) -> str:
    if not availability.get("provider_enabled"):
        return "blocked_provider_disabled"
    if not availability.get("credential_present"):
        return "blocked_operator_config_required"
    if availability.get("model_label_mismatch"):
        return "blocked_model_label_mismatch"
    if not availability.get("model_label_present"):
        return "blocked_model_missing"
    if not availability.get("available"):
        return "blocked_adapter_unavailable"
    return ""


def safe_next_operator_step(reason: str) -> str:
    if reason == "blocked_provider_disabled":
        return (
            "Set OPENCLAW_ENABLE_LIVE_GEMINI_FORM=1 in the approved cassandra-listener.service "
            "runtime environment, then restart only cassandra-listener.service."
        )
    if reason == "blocked_operator_config_required":
        return (
            "Provide an approved Gemini credential env var (GEMINI_API_KEY, GOOGLE_API_KEY, or "
            "GOOGLE_GENERATIVE_AI_API_KEY) in the cassandra-listener.service runtime environment "
            "without printing it, then restart only cassandra-listener.service."
        )
    if reason == "blocked_model_missing":
        return "Set OPENCLAW_GEMINI_MODEL to the operator-approved Gemini Flash-class model label, then retry."
    if reason == "blocked_model_label_mismatch":
        return (
            "OPENCLAW_GEMINI_MODEL and OPENCLAW_GEMINI_FORM_MODEL differ. "
            "Remove the Data Room override or set it to the same approved model label, then retry."
        )
    if reason == "blocked_provider_rate_limited":
        return (
            "Gemini credential/config was accepted far enough to reach the provider, but the provider returned 429. "
            "Check quota/rate limits/model availability or wait and retry."
        )
    if reason == "blocked_model_label":
        return (
            "Set OPENCLAW_GEMINI_MODEL and OPENCLAW_GEMINI_FORM_MODEL to a Gemini model available to this "
            "API key/project, then retry one bounded readiness call."
        )
    return "Review generated/read_models/data_room_gemini_form_session.json, fix the adapter failure, and retry the Cassandra command."


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
    if any(term in text.lower() for term in secret_terms):
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


def form_session_id_for(review_session_id: str) -> str:
    return f"data_room_gemini_form:{str(review_session_id or '').strip() or 'unknown'}"


def redact_data_room_package_for_lm(package: Mapping[str, Any]) -> dict[str, Any]:
    current = package.get("current_question") if isinstance(package.get("current_question"), Mapping) else {}
    coach_pack = package.get("coach_pack_summary") if isinstance(package.get("coach_pack_summary"), Mapping) else {}
    review_session_id = _redact_text(package.get("review_session_id") or "")
    return {
        "package_id": _redact_text(package.get("package_id") or ""),
        "form_session_id": form_session_id_for(review_session_id),
        "review_session_id": review_session_id,
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
            if key
            in {
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


def expected_gemini_turn_result_shape() -> dict[str, Any]:
    return {
        "schema_version": TURN_RESULT_SCHEMA_VERSION,
        "request_id": "",
        "form_session_id": "",
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
        "codex_finalization_recommended": False,
        "safety_flags": dict(SAFE_TURN_SAFETY_FLAGS),
    }


def gemini_turn_result_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "schema_version": {"type": "string", "enum": [TURN_RESULT_SCHEMA_VERSION]},
            "request_id": {"type": "string"},
            "form_session_id": {"type": "string"},
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
            "codex_finalization_recommended": {"type": "boolean"},
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
            "form_session_id",
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
            "codex_finalization_recommended",
            "safety_flags",
        ],
    }


def build_gemini_form_turn_request(
    package: Mapping[str, Any],
    user_turn: str,
    recent_chat_log: str = "",
    *,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    created = created_at_utc or utc_now()
    redacted = redact_data_room_package_for_lm(package)
    request_id = "gemini_data_room_form_turn:" + _short_hash(
        redacted.get("form_session_id"),
        redacted.get("current_question_id"),
        user_turn,
        created,
    )
    answered = redacted["answered_questions_summary"]
    skipped = redacted["skipped_questions_summary"]
    deferred = redacted["deferred_questions_summary"]
    unresolved = redacted["unresolved_questions_summary"]
    return {
        "schema_version": REQUEST_SCHEMA_VERSION,
        "request_id": request_id,
        "form_session_id": redacted["form_session_id"],
        "review_session_id": redacted["review_session_id"],
        "current_question_id": redacted["current_question_id"],
        "current_question_index": redacted["question_index"],
        "total_questions": redacted["total_questions"],
        "user_turn_redacted": _redact_text(user_turn),
        "recent_chat_log_summary": _redact_text(recent_chat_log or redacted.get("prior_chat_log_summary") or ""),
        "current_question": redacted["current_question"],
        "form_progress_summary": (
            f"{len(answered)} answered, {len(skipped)} skipped, {len(deferred)} deferred, "
            f"{len(unresolved)} unresolved."
        ),
        "answered_questions_summary": answered,
        "skipped_questions_summary": skipped,
        "deferred_questions_summary": deferred,
        "unresolved_questions_summary": unresolved,
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
        "expected_output_schema": expected_gemini_turn_result_shape(),
        "advisory_only": True,
        "execution_allowed": False,
        "runtime_mutation_allowed": False,
        "confirmed_reference_data_allowed": False,
        "hydration_allowed": False,
        "external_action_allowed": False,
    }


def _gemini_payload(request_payload: Mapping[str, Any]) -> dict[str, Any]:
    system = (
        "You are Cassandra's live Gemini Flash-class advisory brain for one OpenClaw Data Room form-fill lane. "
        "Return strict JSON only. You have no tools. You do not execute, mutate runtime, create confirmed "
        "reference data, hydrate data, create approvals, send email, or perform external actions. "
        "You may advise conversationally and propose answer candidates, but OpenClaw records only after "
        "Winship confirms through deterministic rails."
    )
    return {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": stable_json(request_payload)}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
            "responseSchema": gemini_turn_result_json_schema(),
        },
    }


def _perform_gemini_generate_content_call(
    *,
    request_payload: Mapping[str, Any],
    request_body: Mapping[str, Any],
    model_label: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    api_key = _credential_value_from_env()
    if not api_key:
        raise GeminiFormAdapterError("blocked_operator_config_required")
    normalized_model = str(model_label or "").strip()
    if normalized_model.startswith("models/"):
        normalized_model = normalized_model[len("models/") :]
    model_path = urllib.parse.quote(normalized_model, safe="")
    url = f"{GEMINI_GENERATE_CONTENT_BASE_URL}/{model_path}:generateContent?key={urllib.parse.quote(api_key, safe='')}"
    data = json.dumps(request_body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        import openclaw_lm_consult_spine as consult_spine

        reason, validation = consult_spine.provider_http_error_classification(
            exc,
            request_body=request_body,
            model_label=model_label,
        )
        raise GeminiFormAdapterError(reason, validation=validation) from exc
    except TimeoutError as exc:
        raise GeminiFormAdapterError("adapter_timeout") from exc
    except Exception as exc:
        raise GeminiFormAdapterError("adapter_api_error") from exc


def _extract_output_text(raw_response: Mapping[str, Any]) -> str:
    prompt_feedback = raw_response.get("promptFeedback")
    if isinstance(prompt_feedback, Mapping) and prompt_feedback.get("blockReason"):
        raise GeminiFormAdapterError("adapter_prompt_blocked")
    candidates = raw_response.get("candidates")
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                continue
            finish_reason = str(candidate.get("finishReason") or "")
            if finish_reason and finish_reason not in {"STOP", "MAX_TOKENS"}:
                raise GeminiFormAdapterError(f"adapter_response_{finish_reason.lower()}")
            content = candidate.get("content")
            if not isinstance(content, Mapping):
                continue
            parts = content.get("parts")
            if not isinstance(parts, list):
                continue
            for part in parts:
                if isinstance(part, Mapping) and isinstance(part.get("text"), str) and part["text"].strip():
                    return str(part["text"])
    output_text = raw_response.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text
    text = raw_response.get("text")
    if isinstance(text, str) and text.strip():
        return text
    raise GeminiFormAdapterError("adapter_missing_output_text")


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
    for key in ("conditions", "caveats", "professional_review_flags"):
        values = answer.get(key)
        if isinstance(values, list):
            parts.extend(str(value) for value in values)
    return "\n".join(parts)


def validate_gemini_form_turn_result(
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
    if request_payload and result.get("form_session_id") != request_payload.get("form_session_id"):
        errors.append("form_session_id_mismatch")
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


def call_gemini_data_room_form_turn(
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
    availability = is_live_gemini_form_available(env)
    reason = availability_blocked_reason(availability)
    if reason:
        raise GeminiFormAdapterError(reason, availability=availability)

    request_payload = build_gemini_form_turn_request(
        package,
        user_turn,
        recent_chat_log,
        created_at_utc=created_at_utc,
    )
    selected_model = model_label(env)
    consult_env = dict(env)
    consult_env.setdefault("OPENCLAW_ENABLE_LM_CONSULTS", "1")
    consult_env.setdefault("OPENCLAW_LM_PROVIDER", "gemini")
    consult_env.setdefault("OPENCLAW_GEMINI_MODEL", selected_model)
    import openclaw_lm_consult_spine as consult_spine

    try:
        consult_request = consult_spine.build_lm_consult_request(
            request_id=request_payload["request_id"],
            created_at_utc=created_at_utc,
            requested_by_agent="cassandra",
            owner_agent="cassandra",
            source_surface="cassandra_data_room_gemini_form",
            source_context_ref=str(package.get("review_session_id") or package.get("package_id") or ""),
            task_type="data_room_form_fill",
            consult_kind="form_fill",
            preferred_model_class="external_fast_worker",
            preferred_provider="gemini",
            provider_model_label=selected_model,
            reason_for_model_choice="Gemini Flash-class is the preferred fast advisory model for redacted Data Room form-fill.",
            context_refs=[
                str(package.get("package_id") or ""),
                str(package.get("review_session_id") or ""),
                str(package.get("current_question_id") or ""),
            ],
            redacted_context_summary=stable_json(request_payload),
            allowed_inputs=request_payload.get("allowed_inputs") or [],
            forbidden_inputs=request_payload.get("forbidden_inputs") or [],
            expected_output_schema=gemini_turn_result_json_schema(),
            stop_condition="Stop after returning a Data Room turn result. Do not record or confirm answers.",
            permission_required=False,
            status="ready_for_provider_call",
        )
        adapter = consult_spine.GeminiProviderAdapter(
            env=consult_env,
            transport=provider,
            legacy_request_payload=request_payload,
            model_label=selected_model,
        )
        consult_result = consult_spine.request_lm_consult(
            consult_request,
            provider_adapter=adapter,
            timeout_seconds=timeout_seconds,
        )
    except consult_spine.LMConsultError as exc:
        raise GeminiFormAdapterError(exc.reason, validation=exc.validation, availability=availability) from exc
    except TimeoutError as exc:
        raise GeminiFormAdapterError("adapter_timeout") from exc
    except Exception as exc:
        raise GeminiFormAdapterError("adapter_api_error") from exc
    if consult_result.get("status") != "result_accepted":
        reason = str(consult_result.get("status") or "adapter_api_error")
        validation_payload = consult_result.get("structured_payload")
        validation = validation_payload if isinstance(validation_payload, Mapping) else {}
        if reason == "result_rejected":
            reason = "adapter_validation_failed"
            nested = validation.get("validation")
            validation = nested if isinstance(nested, Mapping) else validation
        raise GeminiFormAdapterError(reason, validation=validation, availability=availability)

    parsed = consult_result.get("structured_payload")
    if not isinstance(parsed, dict):
        raise GeminiFormAdapterError("adapter_invalid_json")
    validation = validate_gemini_form_turn_result(parsed, package=package, request_payload=request_payload)
    if not validation["valid"]:
        raise GeminiFormAdapterError("adapter_validation_failed", validation=validation, availability=availability)
    parsed["_structured_output_mode"] = str(consult_result.get("structured_output_mode") or "native_schema")
    return parsed


def result_id_for(result: Mapping[str, Any]) -> str:
    return "data_room_gemini_form_turn_result:" + _short_hash(
        result.get("request_id"),
        result.get("form_session_id"),
        result.get("review_session_id"),
        result.get("question_id"),
        result.get("assistant_reply"),
    )


def _question_ids(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    ids: list[str] = []
    for item in values:
        if isinstance(item, Mapping):
            question_id = str(item.get("question_id") or "")
            if question_id:
                ids.append(question_id)
    return ids


def _turn_log_paths(review_session_id: str) -> dict[str, Path]:
    filename = f"data_room_gemini_form_turn_log_{_safe_filename(review_session_id)}.jsonl"
    return {
        "primary": DEFAULT_FORM_PRIMARY_ROOT / filename,
        "durable": DEFAULT_FORM_DURABLE_ROOT / filename,
    }


def running_chat_log_ref_for(review_session_id: str) -> str:
    return _turn_log_paths(review_session_id)["primary"].as_posix()


def _redacted_excerpt(text: str, limit: int = 220) -> str:
    return _redact_text(text).replace("\n", " ")[:limit]


def append_data_room_gemini_form_turn_log(
    *,
    package: Mapping[str, Any],
    result: Mapping[str, Any],
    user_turn: str,
    candidate_created: bool = False,
    confirmed_answer_id: str = "",
    created_at_utc: str | None = None,
) -> dict[str, str]:
    now = created_at_utc or utc_now()
    review_session_id = str(package.get("review_session_id") or result.get("review_session_id") or "")
    entry = {
        "schema_version": TURN_LOG_SCHEMA_VERSION,
        "turn_id": result_id_for(result) if result else "data_room_gemini_form_turn:" + _short_hash(user_turn, now),
        "created_at_utc": now,
        "user_turn_hash": "sha256:" + hashlib.sha256(str(user_turn or "").encode("utf-8")).hexdigest(),
        "redacted_user_excerpt": _redacted_excerpt(user_turn),
        "gemini_request_id": str(result.get("request_id") or ""),
        "gemini_result_id": result_id_for(result) if result else "",
        "assistant_reply": _redact_text(result.get("assistant_reply") or ""),
        "candidate_created": bool(candidate_created),
        "confirmed_answer_id": str(confirmed_answer_id or ""),
        "safety_flags": dict(result.get("safety_flags") or SAFE_TURN_SAFETY_FLAGS),
        "authoritative": False,
        "runtime_policy_changed": False,
        "confirmed_reference_data_created": False,
        "hydration_performed": False,
        "external_action_performed": False,
    }
    paths = _turn_log_paths(review_session_id)
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")
    return {key: path.as_posix() for key, path in paths.items()}


def build_watch_desk_items_for_session(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    review_session_id = str(state.get("review_session_id") or "")
    live_ready = bool(state.get("live_ready"))
    status = str(state.get("lane_status") or ("active" if live_ready else "blocked"))
    if live_ready:
        plain = f"Gemini Data Room form lane active for {review_session_id}."
        urgency = "watch"
        push_class = "info"
    else:
        reason = str(state.get("blocked_reason") or "unavailable")
        plain = f"Gemini Data Room form lane blocked for {review_session_id or 'the active review'}: {reason}."
        urgency = "blocked"
        push_class = "failure"
    items = [
        {
            "item_id": f"data_room_gemini_form:{review_session_id or 'no_active_session'}",
            "lane": "cassandra_ar",
            "urgency": urgency,
            "plain_line": plain,
            "source_receipt_ref": "generated/read_models/data_room_gemini_form_session.json#lane",
            "one_next_safe_action": (
                "Continue the Data Room review in Cassandra; Gemini advice remains advisory-only."
                if live_ready
                else safe_next_operator_step(str(state.get("blocked_reason") or "adapter_failure"))
            ),
            "push_class": push_class,
            "state": {
                "lane_status": status,
                "live_ready": live_ready,
                "model_label": str(state.get("model_label") or ""),
                "review_session_id": review_session_id,
                "current_question_id": str(state.get("current_question_id") or ""),
                "blocked_reason": str(state.get("blocked_reason") or ""),
                "external_action_allowed": False,
                "runtime_mutation_allowed": False,
                "confirmed_reference_data_allowed": False,
                "hydration_allowed": False,
                "execution_allowed": False,
            },
        }
    ]
    finalizer_status = str(state.get("codex_finalizer_status") or "")
    package_ref = str(state.get("codex_finalizer_package_ref") or "")
    if finalizer_status:
        items.append(
            {
                "item_id": f"data_room_gemini_form_codex_finalizer:{review_session_id or 'no_active_session'}",
                "lane": "cassandra_ar",
                "urgency": "watch" if finalizer_status != "blocked" else "blocked",
                "plain_line": f"Data Room Codex finalizer is {finalizer_status} for {review_session_id}.",
                "source_receipt_ref": "generated/read_models/data_room_gemini_form_session.json#codex_finalizer",
                "one_next_safe_action": (
                    "Dispatch the queued Codex work package through an approved Codex bridge."
                    if finalizer_status == "waiting_for_codex_dispatch"
                    else "Monitor the Codex finalizer lifecycle."
                ),
                "push_class": "info",
                "state": {
                    "codex_finalizer_status": finalizer_status,
                    "codex_finalizer_package_ref": package_ref,
                    "review_session_id": review_session_id,
                    "execution_allowed": False,
                    "external_action_allowed": False,
                    "runtime_mutation_allowed": False,
                    "confirmed_reference_data_allowed": False,
                    "hydration_allowed": False,
                },
            }
        )
    return items


def build_data_room_gemini_form_session_state(
    *,
    package: Mapping[str, Any] | None = None,
    result: Mapping[str, Any] | None = None,
    availability: Mapping[str, bool] | None = None,
    lane_status: str,
    live_ready: bool,
    blocked_reason: str = "",
    generated_at_utc: str | None = None,
    chat_log_summary: str = "",
    pending_candidate: Mapping[str, Any] | None = None,
    codex_finalizer_package_ref: str = "",
    codex_finalizer_status: str = "",
    model: str = "",
    provider_error: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    package = package or {}
    result = result or {}
    provider_error = dict(provider_error or {})
    nested_provider_error = provider_error.get("validation")
    if isinstance(nested_provider_error, Mapping):
        provider_error = dict(nested_provider_error)
    native_schema_error = provider_error.get("native_schema_error")
    if not isinstance(native_schema_error, Mapping):
        native_schema_error = {}
    availability = dict(availability or is_live_gemini_form_available())
    review_session_id = str(package.get("review_session_id") or result.get("review_session_id") or "")
    effective_model = model or str(availability.get("effective_model_label") or "")
    structured_output_mode = str(
        result.get("_structured_output_mode") or provider_error.get("structured_output_mode") or "native_schema"
    )
    state = {
        "schema_version": FORM_SESSION_SCHEMA_VERSION,
        "form_session_id": str(result.get("form_session_id") or form_session_id_for(review_session_id)),
        "review_session_id": review_session_id,
        "created_at_utc": str(package.get("created_at_utc") or generated_at_utc or utc_now()),
        "updated_at_utc": generated_at_utc or utc_now(),
        "model_class": "external_fast_worker",
        "model_label": effective_model,
        "effective_model_label": effective_model,
        "generic_model_label_present": bool(availability.get("generic_model_label_present")),
        "form_model_label_present": bool(availability.get("form_model_label_present")),
        "model_label_mismatch": bool(availability.get("model_label_mismatch")),
        "model_label_source": str(availability.get("model_label_source") or ""),
        "lane_status": lane_status,
        "live_ready": bool(live_ready),
        "availability_check": availability,
        "provider_status_code": provider_error.get("provider_status_code"),
        "provider_error_code": str(provider_error.get("provider_error_code") or ""),
        "provider_error_message_redacted": str(provider_error.get("provider_error_message_redacted") or ""),
        "provider_error_category": str(provider_error.get("provider_error_category") or ""),
        "endpoint_family": str(provider_error.get("endpoint_family") or "gemini_generate_content"),
        "structured_output_enabled": provider_error.get("structured_output_enabled"),
        "structured_output_mode": structured_output_mode,
        "request_shape_version": str(provider_error.get("request_shape_version") or "GEMINI_GENERATE_CONTENT_JSON_V1"),
        "native_schema_provider_status_code": native_schema_error.get("provider_status_code"),
        "native_schema_provider_error_code": str(native_schema_error.get("provider_error_code") or ""),
        "native_schema_provider_error_category": str(native_schema_error.get("provider_error_category") or ""),
        "native_schema_provider_error_message_redacted": str(
            native_schema_error.get("provider_error_message_redacted") or ""
        ),
        "request_body_logged": bool(provider_error.get("request_body_logged", False)),
        "credential_value_logged": bool(provider_error.get("credential_value_logged", False)),
        "current_question_id": str(package.get("current_question_id") or result.get("question_id") or ""),
        "current_question_index": int(package.get("current_question_index") or 0),
        "total_questions": int(package.get("total_questions") or 0),
        "answered_question_ids": _question_ids(package.get("answered_questions")),
        "skipped_question_ids": _question_ids(package.get("skipped_questions")),
        "deferred_question_ids": _question_ids(package.get("deferred_questions")),
        "unresolved_question_ids": _question_ids(package.get("unresolved_questions")),
        "running_chat_log_ref": running_chat_log_ref_for(review_session_id),
        "chat_log_summary": _redact_text(chat_log_summary or result.get("chat_log_summary_update") or ""),
        "pending_candidate": dict(pending_candidate or {}),
        "done_criteria": dict(package.get("done_criteria") or {}),
        "codex_finalizer_package_ref": codex_finalizer_package_ref,
        "codex_finalizer_status": codex_finalizer_status,
        "blocked_reason": blocked_reason,
        "last_gemini_request_id": str(result.get("request_id") or ""),
        "last_gemini_result_id": result_id_for(result) if result else "",
        "safety_flags": dict(SAFE_TURN_SAFETY_FLAGS),
        "advisory_only": True,
        "runtime_mutation_allowed": False,
        "execution_allowed": False,
        "confirmed_reference_data_allowed": False,
        "hydration_allowed": False,
        "external_action_allowed": False,
        "push_allowed": False,
    }
    state["watch_desk_items"] = build_watch_desk_items_for_session(state)
    return state


def write_data_room_gemini_form_session_state(
    state: Mapping[str, Any],
    *,
    read_model_path: str | Path | None = None,
    primary_root: str | Path | None = None,
    durable_root: str | Path | None = None,
) -> dict[str, str]:
    read_path = Path(read_model_path or DEFAULT_FORM_SESSION_READ_MODEL_PATH)
    primary = Path(primary_root or DEFAULT_FORM_PRIMARY_ROOT) / "data_room_gemini_form_session.json"
    durable = Path(durable_root or DEFAULT_FORM_DURABLE_ROOT) / "data_room_gemini_form_session.json"
    for path in (read_path, primary, durable):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(stable_json(dict(state)), encoding="utf-8")
    return {
        "read_model_path": read_path.as_posix(),
        "primary_path": primary.as_posix(),
        "durable_path": durable.as_posix(),
    }


def load_data_room_gemini_form_session_state(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path or DEFAULT_FORM_SESSION_READ_MODEL_PATH)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _confirmed_answer_summary(session: Mapping[str, Any]) -> list[dict[str, Any]]:
    answers = session.get("answer_records")
    if not isinstance(answers, list):
        return []
    safe_answers: list[dict[str, Any]] = []
    for answer in answers:
        if not isinstance(answer, Mapping):
            continue
        question_id = str(answer.get("question_id") or "")
        plain = _redact_text(answer.get("answer_text") or answer.get("plain_english") or "")
        if not question_id or not plain:
            continue
        safe_answers.append(
            {
                "answer_id": str(answer.get("answer_id") or ""),
                "question_id": question_id,
                "answer_text": plain,
                "source_refs": _safe_list(answer.get("source_refs") or answer.get("affected_record_ids") or []),
                "answer_source": str(answer.get("answer_source") or ""),
                "authoritative": False,
                "review_status": str(answer.get("review_status") or "answered_pending_promotion"),
            }
        )
    return safe_answers


def build_codex_finalizer_work_package(
    session: Mapping[str, Any],
    *,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    generated_at_utc = generated_at_utc or utc_now()
    review_session_id = str(session.get("review_session_id") or "")
    package_id = f"codex_work_package:{CODEX_FINALIZER_CAPABILITY_ID}:{review_session_id}:{_short_hash(review_session_id, generated_at_utc)}"
    return {
        "schema_version": "CODEX_WORK_PACKAGE_V0",
        "model_work_package_schema": "MODEL_WORK_PACKAGE_V0",
        "package_id": package_id,
        "objective_id": f"{CODEX_FINALIZER_CAPABILITY_ID}:{review_session_id}",
        "capability_id": CODEX_FINALIZER_CAPABILITY_ID,
        "run_mode": "production",
        "created_at": generated_at_utc,
        "worktree_root": "/home/openclaw",
        "operator_goal_text": "Promote only confirmed Data Room answers into confirmed reference data, then run hydration.",
        "requested_outcome": "Confirmed reference data and hydration proof artifacts, with skipped/deferred/unconfirmed items excluded.",
        "candidate_model": "Codex 5.5-class",
        "codex_model_label": "Codex 5.5",
        "form_session_id": str((session.get("data_room_gemini_form_session") or {}).get("form_session_id") or form_session_id_for(review_session_id)),
        "review_session_id": review_session_id,
        "confirmed_answers": _confirmed_answer_summary(session),
        "skipped_question_ids": _question_ids(session.get("skipped_questions")),
        "deferred_question_ids": _question_ids(session.get("deferred_questions")),
        "safety_flags": dict(SAFE_TURN_SAFETY_FLAGS),
        "source_refs": [
            str(session.get("session_artifact_ref") or ""),
            DEFAULT_FORM_SESSION_READ_MODEL_PATH.as_posix(),
        ],
        "allowed_file_paths": [
            "generated/system_knowledge/openclaw_confirmed_reference_data_v0.json",
            "generated/system_knowledge/operator_skill_factory/data_room_gemini_form/",
            "generated/read_models/",
            "openclaw_reference_data_hydrator.py",
            "tests/",
        ],
        "denied_file_paths": [
            ".chief.env",
            ".env",
            ".config/openclaw/",
            "generated/system_knowledge/workflow_package_queue.sqlite",
            "/mnt/c/OpenClaw/",
        ],
        "denied_commands": [
            "git push",
            "git merge",
            "send email",
            "open gmail",
            "open browser",
            "coupa",
            "mark paid",
            "curl ",
            "wget ",
            "ollama",
        ],
        "allowed_commands": [
            "python3 -m py_compile openclaw_reference_data_hydrator.py",
            "git diff --check",
        ],
        "validation_commands": [
            "python3 -m py_compile openclaw_reference_data_hydrator.py",
            "git diff --check",
        ],
        "unsafe_scan": "required",
        "hydration_only_after_confirmed_data": True,
        "confirmation_required": True,
        "confirmed_reference_data_created_before_finalization": False,
        "external_api_allowed": False,
        "email_send_allowed": False,
        "runtime_policy_mutation_allowed": False,
        "ledger_mutation_allowed": False,
        "workbook_mutation_allowed": False,
        "pdf_export_allowed": False,
        "tax_or_legal_advice_allowed": False,
    }


def queue_codex_finalizer_work_package(
    session: Mapping[str, Any],
    *,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    import codex_work_package_lifecycle as lifecycle

    generated_at_utc = generated_at_utc or utc_now()
    package = build_codex_finalizer_work_package(session, generated_at_utc=generated_at_utc)
    objective = {
        "objective_id": package["objective_id"],
        "operator_goal_text": package["operator_goal_text"],
        "requested_outcome": package["requested_outcome"],
    }
    authority_grant = {
        "schema_version": "DATA_ROOM_CODEX_FINALIZER_AUTHORITY_BOUNDARY_V0",
        "grant_id": "data_room_codex_finalizer_boundary:" + _short_hash(package["package_id"], generated_at_utc),
        "guardian_approval_created": False,
        "external_action_allowed": False,
        "runtime_policy_mutation_allowed": False,
        "confirmed_answers_only": True,
        "hydration_only_after_confirmed_data": True,
    }
    lifecycle_bundle = lifecycle.queue_codex_work_package(
        package,
        objective=objective,
        authority_grant=authority_grant,
        sqlite_path=DEFAULT_CODEX_FINALIZER_SQLITE_PATH,
        package_root=DEFAULT_CODEX_FINALIZER_PACKAGE_ROOT,
        generated_at=generated_at_utc,
    )
    return {
        "schema_version": "DATA_ROOM_GEMINI_CODEX_FINALIZER_QUEUE_RESULT_V0",
        "status": "waiting_for_codex_dispatch",
        "codex_automatic_dispatch_real": False,
        "package_id": package["package_id"],
        "codex_work_package": package,
        "codex_work_package_lifecycle": lifecycle_bundle,
        "next_safe_action": "Dispatch the queued Codex package through an approved Codex bridge; no automatic Codex invocation is configured.",
    }


__all__ = [
    "CODEX_FINALIZER_CAPABILITY_ID",
    "DEFAULT_CODEX_FINALIZER_PACKAGE_ROOT",
    "DEFAULT_CODEX_FINALIZER_SQLITE_PATH",
    "DEFAULT_FORM_DURABLE_ROOT",
    "DEFAULT_FORM_PRIMARY_ROOT",
    "DEFAULT_FORM_SESSION_READ_MODEL_PATH",
    "DEFAULT_MODEL_LABEL",
    "ENABLE_ENV",
    "GEMINI_CREDENTIAL_ENVS",
    "GEMINI_FORM_READINESS_NOTIFICATION",
    "GeminiFormAdapterError",
    "READINESS_PROMPT",
    "REQUEST_SCHEMA_VERSION",
    "SAFE_TURN_SAFETY_FLAGS",
    "TURN_RESULT_SCHEMA_VERSION",
    "append_data_room_gemini_form_turn_log",
    "availability_blocked_reason",
    "build_codex_finalizer_work_package",
    "build_data_room_gemini_form_session_state",
    "build_gemini_form_turn_request",
    "call_gemini_data_room_form_turn",
    "expected_gemini_turn_result_shape",
    "form_session_id_for",
    "gemini_turn_result_json_schema",
    "is_live_gemini_form_available",
    "load_data_room_gemini_form_session_state",
    "model_label",
    "queue_codex_finalizer_work_package",
    "redact_data_room_package_for_lm",
    "result_id_for",
    "running_chat_log_ref_for",
    "safe_next_operator_step",
    "stable_json",
    "validate_gemini_form_turn_result",
    "write_data_room_gemini_form_session_state",
]
