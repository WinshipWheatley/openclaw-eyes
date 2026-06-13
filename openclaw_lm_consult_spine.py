"""Systemwide LM Consult Spine v0.

This module is the provider-neutral advisory spine for OpenClaw agents. LMs
advise; OpenClaw records deterministic state after receipts, confirmation, and
the existing approval/execution rails. The spine exposes no model tools and
does not grant runtime, business, external-action, or mutation authority.
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
from typing import Any, Callable, Mapping, Protocol, Sequence


LM_CONSULT_REQUEST_SCHEMA_VERSION = "LM_CONSULT_REQUEST_V0"
LM_CONSULT_RESULT_SCHEMA_VERSION = "LM_CONSULT_RESULT_V0"
LM_CONSULT_SPINE_STATUS_SCHEMA_VERSION = "LM_CONSULT_SPINE_STATUS_V0"
REVIEW_ANSWER_SCHEMA_VERSION = "REVIEW_ANSWER_V0"
CODEX_FINALIZER_SCHEMA_VERSION = "LM_CONSULT_CODEX_FINALIZER_V0"

DEFAULT_STATUS_PATH = Path("generated/read_models/openclaw_lm_consult_spine_status.json")

CONSULT_KINDS = {
    "explain",
    "eli5",
    "analogy",
    "recommendation",
    "thought_dump",
    "form_fill",
    "code_package",
    "architecture_review",
    "safety_review",
    "synthesis",
}

MODEL_CLASSES = {
    "external_fast_worker",
    "external_code_worker",
    "external_deep_reasoner",
    "local_sensitive",
    "manual_handoff",
}

PROVIDERS = {"gemini", "openai", "local", "manual"}
USED_FOR = {"explanation", "candidate_decision", "work_package", "review", "synthesis"}
AGENTS = {"cassandra", "chief", "hermes", "guardian", "niles", "openclaw", "watch_desk"}

GENERIC_ENABLE_ENV = "OPENCLAW_ENABLE_LM_CONSULTS"
GENERIC_PROVIDER_ENV = "OPENCLAW_LM_PROVIDER"
GEMINI_MODEL_ENV = "OPENCLAW_GEMINI_MODEL"
GEMINI_FORM_MODEL_ENV = "OPENCLAW_GEMINI_FORM_MODEL"
GEMINI_CREDENTIAL_ENVS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY")
GEMINI_GENERATE_CONTENT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

DEFAULT_STOP_CONDITION = "Stop after advisory output. Do not execute, record, approve, submit, hydrate, or mutate runtime."
DEFAULT_EXPECTED_OUTPUT_SCHEMA = "concise_advisory_response_v0"

AUTHORITY_FALSE = {
    "advisory_only": True,
    "execution_allowed": False,
    "runtime_mutation_allowed": False,
    "external_action_allowed": False,
    "sensitive_data_excluded": True,
}

FORBIDDEN_INPUTS = (
    "credentials",
    "tokens",
    "secrets",
    "raw bank/account/routing details",
    "operator/device/session verification secrets",
    "raw prompt dumps",
    "raw OCR/artifact text",
    "workbook/email/ledger bodies",
    "browser/Gmail/Coupa content",
    "tool access",
)

FORBIDDEN_OUTPUT_PATTERNS = (
    re.compile(r"\b(tool_call|function_call|call a tool|use a tool)\b", re.IGNORECASE),
    re.compile(r"\b(send email|create gmail draft|submit to coupa|open browser|open gmail)\b", re.IGNORECASE),
    re.compile(r"\b(mark(?:ed)? paid|post to (?:the )?ledger|mutate workbook|export pdf)\b", re.IGNORECASE),
    re.compile(r"\b(create guardian approval|bypass guardian)\b", re.IGNORECASE),
    re.compile(r"\b(create confirmed reference data|hydrate reference data)\b", re.IGNORECASE),
)

ProviderTransport = Callable[..., Mapping[str, Any]]


class LMConsultError(RuntimeError):
    """Fail-closed consult error with a stable reason."""

    def __init__(self, reason: str, *, validation: Mapping[str, Any] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.validation = dict(validation or {})


class LMProviderAdapter(Protocol):
    provider: str

    def is_available(self) -> dict[str, Any]:
        ...

    def build_payload(self, request: Mapping[str, Any]) -> dict[str, Any]:
        ...

    def call(self, request: Mapping[str, Any], *, timeout_seconds: int = 45) -> dict[str, Any]:
        ...

    def validate_result(self, result: Mapping[str, Any], request: Mapping[str, Any]) -> dict[str, Any]:
        ...


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _compact_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _short_hash(*parts: object, length: int = 20) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:length]


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_list(values: Sequence[str] | None) -> list[str]:
    return [str(value) for value in values or [] if str(value).strip()]


def _provider_model_label(provider: str, model_label: str = "", env: Mapping[str, str] | None = None) -> str:
    env = env or os.environ
    if model_label:
        return model_label
    if provider == "gemini":
        return str(env.get(GEMINI_MODEL_ENV) or "").strip()
    if provider == "manual":
        return "manual_handoff"
    if provider == "local":
        return "local_stub"
    return "provider_stub"


def gemini_model_label_status(
    env: Mapping[str, str] | None = None,
    *,
    explicit_model_label: str = "",
) -> dict[str, Any]:
    """Return Gemini model-label metadata without exposing credential values."""

    env = env or os.environ
    explicit = str(explicit_model_label or "").strip()
    generic = str(env.get(GEMINI_MODEL_ENV) or "").strip()
    form = str(env.get(GEMINI_FORM_MODEL_ENV) or "").strip()
    mismatch = bool(generic and form and generic != form)
    if mismatch:
        effective = ""
        source = "blocked_model_label_mismatch"
    elif explicit:
        effective = explicit
        source = "explicit_request_model_label"
    elif form:
        effective = form
        source = GEMINI_FORM_MODEL_ENV
    elif generic:
        effective = generic
        source = GEMINI_MODEL_ENV
    else:
        effective = ""
        source = ""
    return {
        "effective_model_label": effective,
        "generic_model_label_present": bool(generic),
        "form_model_label_present": bool(form),
        "model_label_mismatch": mismatch,
        "model_label_source": source,
    }


def build_lm_consult_request(
    *,
    request_id: str = "",
    created_at_utc: str | None = None,
    requested_by_agent: str,
    owner_agent: str | None = None,
    source_surface: str,
    source_context_ref: str,
    task_type: str,
    consult_kind: str,
    preferred_model_class: str,
    preferred_provider: str,
    provider_model_label: str = "",
    reason_for_model_choice: str = "",
    context_refs: Sequence[str] | None = None,
    redacted_context_summary: str = "",
    allowed_inputs: Sequence[str] | None = None,
    forbidden_inputs: Sequence[str] | None = None,
    expected_output_schema: Any = DEFAULT_EXPECTED_OUTPUT_SCHEMA,
    stop_condition: str = DEFAULT_STOP_CONDITION,
    permission_required: bool = False,
    assignment_loop_ref: str = "",
    model_work_package_ref: str = "",
    status: str = "staged",
) -> dict[str, Any]:
    created = created_at_utc or utc_now()
    owner = owner_agent or requested_by_agent
    provider = preferred_provider if preferred_provider in PROVIDERS else "manual"
    model_class = preferred_model_class if preferred_model_class in MODEL_CLASSES else "manual_handoff"
    kind = consult_kind if consult_kind in CONSULT_KINDS else "explain"
    refs = _as_list(context_refs)
    request_id = request_id or "lm_consult_request:" + _short_hash(created, owner, source_context_ref, task_type, kind, refs)
    return {
        "schema_version": LM_CONSULT_REQUEST_SCHEMA_VERSION,
        "request_id": request_id,
        "created_at_utc": created,
        "requested_by_agent": str(requested_by_agent),
        "owner_agent": str(owner),
        "source_surface": str(source_surface),
        "source_context_ref": str(source_context_ref),
        "task_type": str(task_type),
        "consult_kind": kind,
        "preferred_model_class": model_class,
        "preferred_provider": provider,
        "provider_model_label": _provider_model_label(provider, provider_model_label),
        "reason_for_model_choice": str(reason_for_model_choice or "Selected by systemwide LM Consult Spine policy."),
        "context_refs": refs,
        "redacted_context_summary": str(redacted_context_summary or ""),
        "allowed_inputs": _as_list(allowed_inputs) or ["redacted summaries", "source refs", "expected output schema"],
        "forbidden_inputs": _as_list(forbidden_inputs) or list(FORBIDDEN_INPUTS),
        "expected_output_schema": expected_output_schema,
        "stop_condition": str(stop_condition or DEFAULT_STOP_CONDITION),
        "advisory_only": True,
        "execution_allowed": False,
        "runtime_mutation_allowed": False,
        "external_action_allowed": False,
        "sensitive_data_excluded": True,
        "permission_required": bool(permission_required),
        "assignment_loop_ref": str(assignment_loop_ref or ""),
        "model_work_package_ref": str(model_work_package_ref or ""),
        "status": str(status or "staged"),
        "tools_exposed": False,
    }


def validate_lm_consult_request(request: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    required = (
        "request_id",
        "requested_by_agent",
        "owner_agent",
        "source_surface",
        "source_context_ref",
        "task_type",
        "consult_kind",
        "preferred_model_class",
        "preferred_provider",
        "expected_output_schema",
    )
    for key in required:
        if not str(request.get(key) or "").strip():
            errors.append(f"missing_{key}")
    if request.get("schema_version") != LM_CONSULT_REQUEST_SCHEMA_VERSION:
        errors.append("invalid_schema_version")
    if request.get("consult_kind") not in CONSULT_KINDS:
        errors.append("invalid_consult_kind")
    if request.get("preferred_model_class") not in MODEL_CLASSES:
        errors.append("invalid_model_class")
    if request.get("preferred_provider") not in PROVIDERS:
        errors.append("invalid_provider")
    if request.get("advisory_only") is not True:
        errors.append("advisory_only_must_be_true")
    for key in ("execution_allowed", "runtime_mutation_allowed", "external_action_allowed", "tools_exposed"):
        if bool(request.get(key)):
            errors.append(f"{key}_must_be_false")
    if request.get("sensitive_data_excluded") is not True:
        errors.append("sensitive_data_excluded_must_be_true")
    return {"valid": not errors, "errors": errors}


def build_lm_consult_result(
    request: Mapping[str, Any],
    *,
    provider: str,
    model_class: str,
    model_label: str,
    assistant_reply: str,
    structured_payload: Mapping[str, Any] | None = None,
    output_summary: str = "",
    confidence: str = "medium",
    used_for: str = "explanation",
    receipt_ref: str = "",
    status: str = "result_ready",
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    created = created_at_utc or utc_now()
    payload = dict(structured_payload or {})
    result_id = "lm_consult_result:" + _short_hash(request.get("request_id"), provider, assistant_reply, payload, created)
    return {
        "schema_version": LM_CONSULT_RESULT_SCHEMA_VERSION,
        "result_id": result_id,
        "request_id": str(request.get("request_id") or ""),
        "created_at_utc": created,
        "provider": str(provider),
        "model_class": str(model_class),
        "model_label": str(model_label),
        "assistant_reply": str(assistant_reply or ""),
        "structured_payload": payload,
        "output_summary": str(output_summary or assistant_reply or "")[:500],
        "confidence": str(confidence or "medium"),
        "used_for": used_for if used_for in USED_FOR else "explanation",
        "execution_attempted": False,
        "runtime_mutation_performed": False,
        "external_action_performed": False,
        "authoritative": False,
        "receipt_ref": str(receipt_ref or f"{result_id}#receipt"),
        "status": str(status or "result_ready"),
    }


def _result_text(result: Mapping[str, Any]) -> str:
    payload = result.get("structured_payload") if isinstance(result.get("structured_payload"), Mapping) else {}
    parts = [str(result.get("assistant_reply") or ""), str(result.get("output_summary") or "")]
    for key in ("assistant_reply", "body", "headline", "next_step"):
        if key in payload:
            parts.append(str(payload.get(key) or ""))
    answer = payload.get("proposed_answer") if isinstance(payload.get("proposed_answer"), Mapping) else {}
    parts.extend(str(answer.get(key) or "") for key in ("plain_english", "normalized_decision"))
    return "\n".join(parts)


def validate_lm_consult_result(result: Mapping[str, Any], request: Mapping[str, Any] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    if result.get("schema_version") != LM_CONSULT_RESULT_SCHEMA_VERSION:
        errors.append("invalid_schema_version")
    if request and result.get("request_id") != request.get("request_id"):
        errors.append("request_id_mismatch")
    if not str(result.get("assistant_reply") or "").strip() and not isinstance(result.get("structured_payload"), Mapping):
        errors.append("missing_assistant_reply")
    for key in ("execution_attempted", "runtime_mutation_performed", "external_action_performed", "authoritative"):
        if bool(result.get(key)):
            errors.append(f"{key}_must_be_false")
    payload = result.get("structured_payload") if isinstance(result.get("structured_payload"), Mapping) else {}
    if bool(payload.get("should_record_now")):
        errors.append("model_attempted_record")
    if bool(payload.get("confirmed_by_winship")):
        errors.append("model_attempted_confirmation")
    if bool(payload.get("tool_access")) or bool(payload.get("tools_exposed")):
        errors.append("model_tool_access_requested")
    flags = payload.get("safety_flags")
    if isinstance(flags, Mapping):
        for key, value in flags.items():
            if bool(value):
                errors.append(f"safety_flag_true:{key}")
    text = _result_text(result)
    if any(pattern.search(text) for pattern in FORBIDDEN_OUTPUT_PATTERNS):
        errors.append("forbidden_action_or_tool_text")
    return {"valid": not errors, "errors": errors}


class LocalStubProviderAdapter:
    provider = "local"

    def __init__(self, reply: str = "Local stub advisory response.", structured_payload: Mapping[str, Any] | None = None) -> None:
        self.reply = reply
        self.structured_payload = dict(structured_payload or {"assistant_reply": reply})

    def is_available(self) -> dict[str, Any]:
        return {"adapter_present": True, "available": True, "provider": self.provider, "live_model": False}

    def build_payload(self, request: Mapping[str, Any]) -> dict[str, Any]:
        return {"request": dict(request), "tools": []}

    def call(self, request: Mapping[str, Any], *, timeout_seconds: int = 45) -> dict[str, Any]:
        return build_lm_consult_result(
            request,
            provider=self.provider,
            model_class=str(request.get("preferred_model_class") or "local_sensitive"),
            model_label=str(request.get("provider_model_label") or "local_stub"),
            assistant_reply=self.reply,
            structured_payload=self.structured_payload,
            used_for="explanation",
            status="result_ready",
        )

    def validate_result(self, result: Mapping[str, Any], request: Mapping[str, Any]) -> dict[str, Any]:
        return validate_lm_consult_result(result, request)


class ManualHandoffProviderAdapter:
    provider = "manual"

    def is_available(self) -> dict[str, Any]:
        return {"adapter_present": True, "available": True, "provider": self.provider, "live_model": False}

    def build_payload(self, request: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": "LM_CONSULT_MANUAL_HANDOFF_PACKAGE_V0",
            "request_id": str(request.get("request_id") or ""),
            "provider": self.provider,
            "redacted_context_summary": str(request.get("redacted_context_summary") or ""),
            "expected_output_schema": request.get("expected_output_schema"),
            "tools_exposed": False,
            "advisory_only": True,
            "execution_allowed": False,
        }

    def call(self, request: Mapping[str, Any], *, timeout_seconds: int = 45) -> dict[str, Any]:
        package = self.build_payload(request)
        return build_lm_consult_result(
            request,
            provider=self.provider,
            model_class="manual_handoff",
            model_label="manual_handoff",
            assistant_reply="Manual LM handoff package is ready; no live model was called.",
            structured_payload={"manual_handoff_package": package, "live_model_called": False},
            output_summary="Manual handoff package created.",
            used_for="work_package",
            status="manual_handoff_package_created",
        )

    def validate_result(self, result: Mapping[str, Any], request: Mapping[str, Any]) -> dict[str, Any]:
        return validate_lm_consult_result(result, request)


class OpenAIProviderAdapter:
    provider = "openai"

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self.env = dict(env or os.environ)

    def is_available(self) -> dict[str, Any]:
        return {
            "adapter_present": True,
            "available": False,
            "provider": self.provider,
            "blocked_reason": "adapter_stub_not_live",
            "interchangeable_contract_level": True,
        }

    def build_payload(self, request: Mapping[str, Any]) -> dict[str, Any]:
        return {"request": dict(request), "tools": [], "provider": self.provider}

    def call(self, request: Mapping[str, Any], *, timeout_seconds: int = 45) -> dict[str, Any]:
        raise LMConsultError("adapter_stub_not_live")

    def validate_result(self, result: Mapping[str, Any], request: Mapping[str, Any]) -> dict[str, Any]:
        return validate_lm_consult_result(result, request)


def _credential_present(env: Mapping[str, str], names: Sequence[str]) -> bool:
    return any(bool(str(env.get(name) or "").strip()) for name in names)


def _credential_value(env: Mapping[str, str], names: Sequence[str]) -> str:
    for name in names:
        value = env.get(name, "")
        if str(value or "").strip():
            return str(value)
    return ""


def _retry_after_seconds(headers: Any) -> int | None:
    try:
        value = headers.get("Retry-After")
    except Exception:
        return None
    if value is None:
        return None
    text = str(value).strip()
    return int(text) if text.isdigit() else None


def _safe_provider_error_text(exc: urllib.error.HTTPError) -> str:
    try:
        raw = exc.read(4096)
    except Exception:
        return ""
    try:
        text = raw.decode("utf-8", errors="ignore")
    except Exception:
        return ""
    text = re.sub(r"AIza[0-9A-Za-z_-]+", "[REDACTED_CREDENTIAL]", text)
    text = re.sub(r"(?i)(api[_ -]?key|token|secret|credential)[^,\n.]*", "[REDACTED_SECRET_REF]", text)
    return text[:500]


def provider_http_error_classification(exc: urllib.error.HTTPError) -> tuple[str, dict[str, Any]]:
    status_code = int(getattr(exc, "code", 0) or 0)
    provider_text = _safe_provider_error_text(exc)
    lower = provider_text.lower()
    category = "provider_http_error"
    reason = f"adapter_api_http_{status_code}" if status_code else "adapter_api_http_error"
    if status_code == 429:
        category = "rate_limited"
        reason = "blocked_provider_rate_limited"
    elif status_code in {400, 404} and (
        status_code == 404
        or ("model" in lower and any(term in lower for term in ("not found", "not supported", "invalid", "unsupported")))
    ):
        category = "model_label"
        reason = "blocked_model_label"
    elif status_code in {401, 403}:
        category = "credential_or_permission"
    validation: dict[str, Any] = {
        "provider_status_code": status_code,
        "provider_error_category": category,
        "request_body_logged": False,
        "credential_value_logged": False,
    }
    retry_after = _retry_after_seconds(getattr(exc, "headers", None))
    if retry_after is not None:
        validation["retry_after_seconds"] = retry_after
    return reason, validation


class GeminiProviderAdapter:
    provider = "gemini"

    def __init__(
        self,
        *,
        env: Mapping[str, str] | None = None,
        transport: ProviderTransport | None = None,
        legacy_request_payload: Mapping[str, Any] | None = None,
        model_label: str = "",
    ) -> None:
        self.env = dict(env or os.environ)
        self.transport = transport
        self.legacy_request_payload = dict(legacy_request_payload or {})
        self.model_label_status = gemini_model_label_status(self.env, explicit_model_label=model_label)
        self.model_label = str(self.model_label_status.get("effective_model_label") or "")

    def is_available(self) -> dict[str, Any]:
        provider_enabled = _truthy(self.env.get(GENERIC_ENABLE_ENV))
        provider_selected = str(self.env.get(GENERIC_PROVIDER_ENV) or "").strip().lower() in {"", "gemini"}
        credential_present = _credential_present(self.env, GEMINI_CREDENTIAL_ENVS)
        model_label_present = bool(str(self.model_label or "").strip())
        model_label_mismatch = bool(self.model_label_status.get("model_label_mismatch"))
        available = bool(provider_enabled and provider_selected and credential_present and model_label_present and not model_label_mismatch)
        missing: list[str] = []
        if not provider_enabled:
            missing.append(GENERIC_ENABLE_ENV)
        if not provider_selected:
            missing.append(GENERIC_PROVIDER_ENV)
        if not credential_present:
            missing.append("gemini_credential_env")
        if not model_label_present:
            missing.append(GEMINI_MODEL_ENV)
        blocked_reason = ""
        if model_label_mismatch:
            blocked_reason = "blocked_model_label_mismatch"
        elif not available:
            blocked_reason = "blocked_provider_config_required"
        return {
            "adapter_present": True,
            "available": available,
            "provider": self.provider,
            "provider_enabled": provider_enabled,
            "provider_selected": provider_selected,
            "credential_present": credential_present,
            "model_label_present": model_label_present,
            **self.model_label_status,
            "missing_config": missing,
            "blocked_reason": blocked_reason,
        }

    def build_payload(self, request: Mapping[str, Any]) -> dict[str, Any]:
        input_payload = self.legacy_request_payload or dict(request)
        system = (
            "You are an advisory model inside the OpenClaw LM Consult Spine. Return JSON only. "
            "You have no tools. You may advise, explain, prioritize, or draft candidate text. "
            "You must not execute, mutate runtime, create confirmed data, create approvals, send, submit, "
            "hydrate, mark paid, or perform external actions."
        )
        generation_config: dict[str, Any] = {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        }
        expected_schema = request.get("expected_output_schema") or input_payload.get("expected_output_schema")
        if isinstance(expected_schema, Mapping):
            generation_config["responseSchema"] = dict(expected_schema)
        return {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": stable_json(input_payload)}]}],
            "generationConfig": generation_config,
        }

    def _perform_http_call(
        self,
        *,
        request_payload: Mapping[str, Any],
        request_body: Mapping[str, Any],
        model_label: str,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        api_key = _credential_value(self.env, GEMINI_CREDENTIAL_ENVS)
        if not api_key:
            raise LMConsultError("blocked_provider_config_required")
        model_path = urllib.parse.quote(model_label, safe="")
        url = f"{GEMINI_GENERATE_CONTENT_BASE_URL}/{model_path}:generateContent?key={urllib.parse.quote(api_key, safe='')}"
        request = urllib.request.Request(
            url,
            data=json.dumps(request_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            reason, validation = provider_http_error_classification(exc)
            raise LMConsultError(reason, validation=validation) from exc
        except TimeoutError as exc:
            raise LMConsultError("adapter_timeout") from exc
        except Exception as exc:
            raise LMConsultError("adapter_api_error") from exc

    def _extract_text(self, raw_response: Mapping[str, Any]) -> str:
        prompt_feedback = raw_response.get("promptFeedback")
        if isinstance(prompt_feedback, Mapping) and prompt_feedback.get("blockReason"):
            raise LMConsultError("adapter_prompt_blocked")
        candidates = raw_response.get("candidates")
        if isinstance(candidates, list):
            for candidate in candidates:
                if not isinstance(candidate, Mapping):
                    continue
                content = candidate.get("content")
                if not isinstance(content, Mapping):
                    continue
                parts = content.get("parts")
                if not isinstance(parts, list):
                    continue
                for part in parts:
                    if isinstance(part, Mapping) and isinstance(part.get("text"), str) and part["text"].strip():
                        return str(part["text"])
        for key in ("output_text", "text"):
            value = raw_response.get(key)
            if isinstance(value, str) and value.strip():
                return value
        raise LMConsultError("adapter_missing_output_text")

    def call(self, request: Mapping[str, Any], *, timeout_seconds: int = 45) -> dict[str, Any]:
        availability = self.is_available()
        if not availability.get("available"):
            raise LMConsultError(str(availability.get("blocked_reason") or "blocked_provider_config_required"))
        request_body = self.build_payload(request)
        request_payload = self.legacy_request_payload or dict(request)
        transport = self.transport or self._perform_http_call
        try:
            raw_response = transport(
                request_payload=request_payload,
                request_body=request_body,
                model_label=self.model_label,
                timeout_seconds=timeout_seconds,
            )
        except LMConsultError:
            raise
        except TimeoutError as exc:
            raise LMConsultError("adapter_timeout") from exc
        except Exception as exc:
            raise LMConsultError("adapter_api_error") from exc
        output_text = self._extract_text(raw_response)
        try:
            structured = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise LMConsultError("adapter_invalid_json") from exc
        if not isinstance(structured, dict):
            raise LMConsultError("adapter_invalid_json")
        return build_lm_consult_result(
            request,
            provider=self.provider,
            model_class=str(request.get("preferred_model_class") or "external_fast_worker"),
            model_label=self.model_label,
            assistant_reply=str(structured.get("assistant_reply") or structured.get("body") or output_text[:500]),
            structured_payload=structured,
            output_summary=str(structured.get("chat_log_summary_update") or structured.get("assistant_reply") or "")[:500],
            confidence=str((structured.get("proposed_answer") or {}).get("confidence") if isinstance(structured.get("proposed_answer"), Mapping) else "medium"),
            used_for="candidate_decision" if request.get("consult_kind") == "form_fill" else "explanation",
            status="result_ready",
        )

    def validate_result(self, result: Mapping[str, Any], request: Mapping[str, Any]) -> dict[str, Any]:
        return validate_lm_consult_result(result, request)


def provider_adapter_for(
    request: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    transport: ProviderTransport | None = None,
) -> LMProviderAdapter:
    provider = str(request.get("preferred_provider") or "manual").strip().lower()
    if provider == "gemini":
        return GeminiProviderAdapter(env=env, transport=transport, model_label=str(request.get("provider_model_label") or ""))
    if provider == "openai":
        return OpenAIProviderAdapter(env=env)
    if provider == "local":
        return LocalStubProviderAdapter()
    return ManualHandoffProviderAdapter()


def request_lm_consult(
    request: Mapping[str, Any],
    *,
    provider_adapter: LMProviderAdapter | None = None,
    env: Mapping[str, str] | None = None,
    transport: ProviderTransport | None = None,
    timeout_seconds: int = 45,
) -> dict[str, Any]:
    request_validation = validate_lm_consult_request(request)
    if not request_validation["valid"]:
        return build_lm_consult_result(
            request,
            provider=str(request.get("preferred_provider") or "manual"),
            model_class=str(request.get("preferred_model_class") or "manual_handoff"),
            model_label=str(request.get("provider_model_label") or ""),
            assistant_reply="LM consult request is invalid.",
            structured_payload={"request_validation": request_validation},
            status="request_invalid",
        )
    adapter = provider_adapter or provider_adapter_for(request, env=env, transport=transport)
    availability = adapter.is_available()
    if not availability.get("available"):
        status = str(availability.get("blocked_reason") or "blocked_provider_config_required")
        return build_lm_consult_result(
            request,
            provider=str(availability.get("provider") or request.get("preferred_provider") or "manual"),
            model_class=str(request.get("preferred_model_class") or "manual_handoff"),
            model_label=str(request.get("provider_model_label") or ""),
            assistant_reply="The LM consult spine is built, but the provider is not configured yet.",
            structured_payload={"availability": availability},
            output_summary=status,
            used_for="explanation",
            status=status,
        )
    try:
        result = adapter.call(request, timeout_seconds=timeout_seconds)
    except LMConsultError as exc:
        return build_lm_consult_result(
            request,
            provider=str(getattr(adapter, "provider", request.get("preferred_provider") or "manual")),
            model_class=str(request.get("preferred_model_class") or "manual_handoff"),
            model_label=str(request.get("provider_model_label") or ""),
            assistant_reply="The LM consult failed closed.",
            structured_payload={"error_reason": exc.reason, "validation": exc.validation},
            output_summary=exc.reason,
            used_for="explanation",
            status=exc.reason,
        )
    validation = adapter.validate_result(result, request)
    if not validation["valid"]:
        result = dict(result)
        result["status"] = "result_rejected"
        result["structured_payload"] = dict(result.get("structured_payload") or {})
        result["structured_payload"]["validation"] = validation
        return result
    result = dict(result)
    if result.get("status") == "result_ready":
        result["status"] = "result_accepted"
    return result


def build_data_room_form_fill_consult_request(
    package: Mapping[str, Any],
    *,
    user_turn: str,
    recent_chat_log: str = "",
    created_at_utc: str | None = None,
    provider: str = "gemini",
    model_label: str = "",
) -> dict[str, Any]:
    context_summary = {
        "package_id": package.get("package_id", ""),
        "review_session_id": package.get("review_session_id", ""),
        "current_question_id": package.get("current_question_id", ""),
        "current_question": package.get("current_question", {}),
        "progress": {
            "current_question_index": package.get("current_question_index", 0),
            "total_questions": package.get("total_questions", 0),
        },
        "recent_chat_log_summary": recent_chat_log or package.get("prior_chat_log_summary", ""),
        "user_turn_redacted": str(user_turn or ""),
    }
    return build_lm_consult_request(
        created_at_utc=created_at_utc,
        requested_by_agent="cassandra",
        owner_agent="cassandra",
        source_surface="cassandra_data_room_guided_review",
        source_context_ref=str(package.get("review_session_id") or package.get("package_id") or ""),
        task_type="data_room_form_fill",
        consult_kind="form_fill",
        preferred_model_class="external_fast_worker" if provider == "gemini" else "manual_handoff",
        preferred_provider=provider,
        provider_model_label=model_label or ("Gemini Flash-class" if provider == "gemini" else "manual_handoff"),
        reason_for_model_choice="Data Room form-fill is low-action-risk advisory work over redacted context.",
        context_refs=[
            str(package.get("package_id") or ""),
            str(package.get("review_session_id") or ""),
            str(package.get("current_question_id") or ""),
        ],
        redacted_context_summary=stable_json(context_summary),
        allowed_inputs=["redacted Data Room form summary", "current question", "recent chat summary", "expected output schema"],
        forbidden_inputs=list(FORBIDDEN_INPUTS),
        expected_output_schema=package.get("expected_output_schema") or DEFAULT_EXPECTED_OUTPUT_SCHEMA,
        stop_condition="Stop after returning a candidate Data Room form-fill response. Do not record or confirm answers.",
        permission_required=False,
        status="ready_for_provider_call",
    )


def build_review_answer_from_consult_result(
    result: Mapping[str, Any],
    *,
    question_id: str,
    confirmed_by_winship: bool,
    source_refs: Sequence[str] | None = None,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    payload = result.get("structured_payload") if isinstance(result.get("structured_payload"), Mapping) else {}
    proposed = payload.get("proposed_answer") if isinstance(payload.get("proposed_answer"), Mapping) else {}
    plain_answer = str(proposed.get("plain_english") or result.get("assistant_reply") or "").strip()
    answer = {
        "schema_version": REVIEW_ANSWER_SCHEMA_VERSION,
        "answer_id": "review_answer:" + _short_hash(result.get("result_id"), question_id, plain_answer),
        "created_at_utc": created_at_utc or utc_now(),
        "source_lm_consult_result_id": str(result.get("result_id") or ""),
        "question_id": str(question_id),
        "answer_text": plain_answer,
        "source_refs": _as_list(source_refs),
        "confirmed_by_winship": bool(confirmed_by_winship),
        "record_review_answer": bool(confirmed_by_winship),
        "authoritative": False,
        "runtime_policy_changed": False,
        "confirmed_reference_data_created": False,
        "hydration_performed": False,
    }
    if not confirmed_by_winship:
        answer["status"] = "candidate_pending_winship_confirmation"
    else:
        answer["status"] = "review_answer_ready_for_deterministic_recording"
    return answer


def maybe_build_codex_finalizer_package(
    *,
    review_session_id: str,
    done_criteria: Mapping[str, Any],
    confirmed_answer_refs: Sequence[str] | None = None,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    created = created_at_utc or utc_now()
    done = bool(done_criteria.get("done"))
    refs = _as_list(confirmed_answer_refs)
    if not done:
        return {
            "schema_version": CODEX_FINALIZER_SCHEMA_VERSION,
            "status": "blocked_until_done_criteria",
            "review_session_id": str(review_session_id),
            "codex_finalizer_package_ref": "",
            "waiting_for_codex_dispatch": False,
            "confirmed_reference_data_created": False,
            "hydration_performed": False,
        }
    package_id = "codex_work_package:data_room_consult_finalizer:" + _short_hash(review_session_id, refs, created)
    return {
        "schema_version": CODEX_FINALIZER_SCHEMA_VERSION,
        "status": "waiting_for_codex_dispatch",
        "review_session_id": str(review_session_id),
        "codex_finalizer_package_ref": package_id,
        "created_at_utc": created,
        "confirmed_answer_refs": refs,
        "waiting_for_codex_dispatch": True,
        "automatic_codex_dispatch": False,
        "confirmed_reference_data_created": False,
        "hydration_performed": False,
    }


def build_lm_consult_spine_status(
    *,
    env: Mapping[str, str] | None = None,
    latest_request: Mapping[str, Any] | None = None,
    latest_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    env = dict(env or os.environ)
    provider = str(env.get(GENERIC_PROVIDER_ENV) or "gemini").strip().lower() or "gemini"
    probe_request = build_lm_consult_request(
        requested_by_agent="openclaw",
        owner_agent="openclaw",
        source_surface="lm_consult_spine_status",
        source_context_ref="status_probe",
        task_type="readiness_check",
        consult_kind="explain",
        preferred_model_class="external_fast_worker" if provider == "gemini" else "manual_handoff",
        preferred_provider=provider if provider in PROVIDERS else "manual",
    )
    adapter = provider_adapter_for(probe_request, env=env)
    availability = adapter.is_available()
    provider_config_ready = bool(availability.get("available"))
    latest_status = str((latest_result or {}).get("status") or "")
    readiness_validated = provider_config_ready and latest_status in {"result_accepted", "readiness_validated"}
    live_ready = bool(readiness_validated)
    latest_payload = latest_result.get("structured_payload") if isinstance(latest_result, Mapping) else {}
    latest_validation = latest_payload.get("validation") if isinstance(latest_payload, Mapping) else {}
    if not isinstance(latest_validation, Mapping):
        latest_validation = {}
    blocked_reason = ""
    if not live_ready:
        if not provider_config_ready:
            blocked_reason = str(availability.get("blocked_reason") or "blocked_provider_config_required")
        elif latest_status:
            blocked_reason = latest_status
        else:
            blocked_reason = "readiness_call_required"
    status = {
        "schema_version": LM_CONSULT_SPINE_STATUS_SCHEMA_VERSION,
        "read_model_id": "openclaw_lm_consult_spine_status",
        "generated_at_utc": utc_now(),
        "spine_built": True,
        "live_ready": live_ready,
        "provider_config_ready": provider_config_ready,
        "readiness_call_succeeded": readiness_validated,
        "provider": str(availability.get("provider") or provider),
        "preferred_provider": provider,
        "blocked_reason": blocked_reason,
        "effective_model_label": str(availability.get("effective_model_label") or ""),
        "generic_model_label_present": bool(availability.get("generic_model_label_present")),
        "form_model_label_present": bool(availability.get("form_model_label_present")),
        "model_label_mismatch": bool(availability.get("model_label_mismatch")),
        "model_label_source": str(availability.get("model_label_source") or ""),
        "provider_status_code": latest_validation.get("provider_status_code"),
        "provider_error_category": str(latest_validation.get("provider_error_category") or ""),
        "retry_after_seconds": latest_validation.get("retry_after_seconds"),
        "availability": availability,
        "latest_request_id": str((latest_request or {}).get("request_id") or ""),
        "latest_result_id": str((latest_result or {}).get("result_id") or ""),
        "latest_result_status": latest_status,
        "advisory_only": True,
        "tools_exposed": False,
        "execution_allowed": False,
        "runtime_mutation_allowed": False,
        "external_action_allowed": False,
        "confirmed_reference_data_allowed": False,
        "hydration_allowed": False,
    }
    status["watch_desk_items"] = build_watch_desk_items_for_status(status)
    return status


def build_watch_desk_items_for_status(status: Mapping[str, Any]) -> list[dict[str, Any]]:
    live_ready = bool(status.get("live_ready"))
    provider = str(status.get("provider") or "unknown")
    if live_ready:
        item_id = f"lm_consult_spine:{provider}:ready"
        plain = f"LM consult spine ready with {provider}."
        urgency = "watch"
        push_class = "info"
        next_action = "Use the generic consult spine for advisory-only model help; deterministic rails still record state."
    else:
        reason = str(status.get("blocked_reason") or "blocked_provider_config_required")
        item_id = f"lm_consult_spine:{provider}:blocked"
        plain = f"LM consult spine built, but {provider} is blocked: {reason}."
        urgency = "blocked"
        push_class = "failure"
        if reason == "blocked_provider_rate_limited":
            next_action = (
                "Gemini credential/config reached the provider, but the provider returned 429. "
                "Check quota/rate limits/model availability or wait and retry."
            )
        elif reason in {"blocked_model_label", "blocked_model_label_mismatch"}:
            next_action = "Fix the approved Gemini model label configuration, then retry one bounded readiness call."
        else:
            next_action = "Configure the provider through approved env/config, without printing credential values."
    return [
        {
            "item_id": item_id,
            "lane": "chief_runtime",
            "urgency": urgency,
            "plain_line": plain,
            "source_receipt_ref": "generated/read_models/openclaw_lm_consult_spine_status.json#status",
            "one_next_safe_action": next_action,
            "push_class": push_class,
            "state": {
                "provider": provider,
                "live_ready": live_ready,
                "blocked_reason": str(status.get("blocked_reason") or ""),
                "advisory_only": True,
                "tools_exposed": False,
                "execution_allowed": False,
                "runtime_mutation_allowed": False,
                "external_action_allowed": False,
            },
        }
    ]


def write_lm_consult_spine_status(payload: Mapping[str, Any], *, path: str | Path = DEFAULT_STATUS_PATH) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(stable_json(dict(payload)), encoding="utf-8")
    return target


def cassandra_lm_brain_claim(status: Mapping[str, Any]) -> str:
    if (
        status.get("live_ready") is True
        and status.get("provider") == "gemini"
        and status.get("latest_result_status") in {"result_accepted", "readiness_validated", ""}
    ):
        return "My Data Room brain is Gemini Flash."
    if status.get("provider_config_ready") is True and status.get("blocked_reason") == "readiness_call_required":
        return "The LM consult spine is built, but Gemini readiness has not succeeded yet."
    return "The LM consult spine is built, but Gemini is not configured yet."


__all__ = [
    "AUTHORITY_FALSE",
    "CONSULT_KINDS",
    "DEFAULT_STATUS_PATH",
    "FORBIDDEN_INPUTS",
    "GEMINI_CREDENTIAL_ENVS",
    "GEMINI_FORM_MODEL_ENV",
    "GEMINI_MODEL_ENV",
    "GENERIC_ENABLE_ENV",
    "GENERIC_PROVIDER_ENV",
    "LM_CONSULT_REQUEST_SCHEMA_VERSION",
    "LM_CONSULT_RESULT_SCHEMA_VERSION",
    "LM_CONSULT_SPINE_STATUS_SCHEMA_VERSION",
    "LMConsultError",
    "GeminiProviderAdapter",
    "LocalStubProviderAdapter",
    "ManualHandoffProviderAdapter",
    "OpenAIProviderAdapter",
    "build_codex_finalizer_package",
    "build_data_room_form_fill_consult_request",
    "build_lm_consult_request",
    "build_lm_consult_result",
    "build_lm_consult_spine_status",
    "build_review_answer_from_consult_result",
    "build_watch_desk_items_for_status",
    "cassandra_lm_brain_claim",
    "gemini_model_label_status",
    "provider_adapter_for",
    "provider_http_error_classification",
    "request_lm_consult",
    "stable_json",
    "utc_now",
    "validate_lm_consult_request",
    "validate_lm_consult_result",
    "write_lm_consult_spine_status",
]
