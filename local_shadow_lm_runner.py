"""Local-only shadow LM runner for Reality Bounce.

This module is deliberately narrow: it may call a local Ollama server over
loopback for isolated shadow/test runs, and it never uses provider keys, cloud
models, tools, agents, external actions, or production authority.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Mapping

import model_router_policy


SCHEMA_VERSION = "local_shadow_lm_runner_v0"
RUNNER_ID = "local_shadow_lm_runner.ollama_loopback_v0"
OLLAMA_LOOPBACK_GENERATE_URL = "http://127.0.0.1:11434/api/generate"

RESULT_OK = "SHADOW_LM_RESULT"
RESULT_POLICY_BLOCKED = "SHADOW_LM_POLICY_BLOCKED"
RESULT_MODEL_UNAVAILABLE = "SHADOW_LM_MODEL_UNAVAILABLE"
RESULT_CALL_FAILED = "SHADOW_LM_CALL_FAILED"
RESULT_JSON_PARSE_FAILED = "SHADOW_LM_JSON_PARSE_FAILED"

AUTHORITY_BOUNDARY = {
    "production_live_model_call_allowed": False,
    "cloud_model_call_allowed": False,
    "provider_key_material_access_allowed": False,
    "tool_execution_allowed": False,
    "external_action_allowed": False,
    "send_submit_allowed": False,
    "workflow_execution_allowed": False,
    "production_state_mutation_allowed": False,
    "credential_handling_allowed": False,
}

LOCAL_SHADOW_POLICY = {
    "local_loopback_ollama_allowed": True,
    "shadow_only": True,
    "production_authority": False,
    "raw_values_allowed": False,
}


@dataclass(frozen=True)
class LocalShadowLMCallResult:
    schema_version: str
    runner_id: str
    status: str
    lane: str
    request_id: str
    provider_policy_id: str
    provider_ref: str
    selected_model_class: str
    local_model: str
    prompt_hash: str
    parsed_json: dict[str, Any]
    raw_response_text: str
    error: str
    duration_ms: int
    authority_boundary: dict[str, bool]
    shadow_policy: dict[str, bool]


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _prompt_hash(prompt: str) -> str:
    return "sha256:" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _result(
    *,
    status: str,
    lane: str,
    request_id: str,
    provider_policy_id: str,
    provider_ref: str,
    selected_model_class: str,
    local_model: str = "",
    prompt: str = "",
    parsed_json: Mapping[str, Any] | None = None,
    raw_response_text: str = "",
    error: str = "",
    started_at: float | None = None,
) -> dict[str, Any]:
    duration_ms = int((time.monotonic() - started_at) * 1000) if started_at else 0
    return asdict(
        LocalShadowLMCallResult(
            schema_version=SCHEMA_VERSION,
            runner_id=RUNNER_ID,
            status=status,
            lane=lane,
            request_id=request_id,
            provider_policy_id=provider_policy_id,
            provider_ref=provider_ref,
            selected_model_class=selected_model_class,
            local_model=local_model,
            prompt_hash=_prompt_hash(prompt),
            parsed_json=dict(parsed_json or {}),
            raw_response_text=raw_response_text,
            error=error,
            duration_ms=duration_ms,
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            shadow_policy=dict(LOCAL_SHADOW_POLICY),
        )
    )


def shadow_policy_allows_route(route_decision: Mapping[str, Any]) -> tuple[bool, tuple[str, ...]]:
    """Return whether a model-route decision is allowed for local shadow calls."""

    reasons: list[str] = []
    selected_class = str(route_decision.get("selected_model_class") or "")
    provider_ref = str(route_decision.get("selected_provider_ref") or "")
    provider_policy = str(route_decision.get("selected_provider_policy_id") or "")
    if not selected_class or selected_class == model_router_policy.NO_SAFE_MODEL:
        reasons.append("NO_SAFE_MODEL_CLASS")
    if not provider_policy:
        reasons.append("MISSING_PROVIDER_POLICY")
    if "local_or_private" not in provider_ref:
        reasons.append("PROVIDER_IS_NOT_LOCAL_PRIVATE")
    if route_decision.get("blocked_reasons"):
        reasons.append("MODEL_ROUTER_BLOCKED")
    return (not reasons, tuple(dict.fromkeys(reasons)))


def installed_ollama_models(timeout_seconds: int = 5) -> tuple[str, ...]:
    """List locally installed Ollama models without touching provider credentials."""

    if not shutil.which("ollama"):
        return ()
    try:
        completed = subprocess.run(
            ["ollama", "list"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError):
        return ()
    if completed.returncode != 0:
        return ()
    names: list[str] = []
    for line in completed.stdout.splitlines()[1:]:
        parts = line.split()
        if parts:
            names.append(parts[0])
    return tuple(dict.fromkeys(names))


def select_local_model_for_class(
    selected_model_class: str,
    *,
    installed_models: tuple[str, ...] | None = None,
) -> str:
    installed = installed_models if installed_models is not None else installed_ollama_models()
    preferences = {
        model_router_policy.FAST_STRUCTURED_INTENT_SMALL: (
            "qwen3:4b",
            "nemotron-3-nano:4b",
            "qwen3:8b-q4_K_M",
            "mistral-nemo:12b-instruct-2407-q2_K",
        ),
        model_router_policy.STRONG_STRUCTURED_ROLE_REASONER: (
            "qwen3:8b-q4_K_M",
            "qwen3:4b",
            "mistral-nemo:12b-instruct-2407-q2_K",
            "mistral-small:latest",
        ),
        model_router_policy.CONSERVATIVE_SENSITIVE_STRUCTURED: (
            "qwen3:4b",
            "nemotron-3-nano:4b",
            "qwen3:8b-q4_K_M",
        ),
    }
    for preferred in preferences.get(selected_model_class, ()):
        if preferred in installed:
            return preferred
    for fallback_prefix in ("qwen", "nemotron", "mistral", "gemma"):
        for model in installed:
            if model.startswith(fallback_prefix):
                return model
    return ""


def _extract_json_object(raw_text: str) -> tuple[dict[str, Any], str]:
    text = str(raw_text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.replace("json\n", "", 1).strip()
    try:
        parsed = json.loads(text)
        return (parsed if isinstance(parsed, dict) else {}, "")
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            return (parsed if isinstance(parsed, dict) else {}, "")
        except json.JSONDecodeError as exc:
            return ({}, str(exc))
    return ({}, "No JSON object found in model response.")


def generate_json(
    *,
    prompt: str,
    lane: str,
    request_id: str,
    route_decision: Mapping[str, Any],
    timeout_seconds: int = 90,
    installed_models: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Call local Ollama in explicit shadow mode and parse a JSON object."""

    started = time.monotonic()
    allowed, reasons = shadow_policy_allows_route(route_decision)
    selected_class = str(route_decision.get("selected_model_class") or "")
    provider_policy = str(route_decision.get("selected_provider_policy_id") or "")
    provider_ref = str(route_decision.get("selected_provider_ref") or "")
    if not allowed:
        return _result(
            status=RESULT_POLICY_BLOCKED,
            lane=lane,
            request_id=request_id,
            provider_policy_id=provider_policy,
            provider_ref=provider_ref,
            selected_model_class=selected_class,
            prompt=prompt,
            error=", ".join(reasons),
            started_at=started,
        )

    local_model = select_local_model_for_class(selected_class, installed_models=installed_models)
    if not local_model:
        return _result(
            status=RESULT_MODEL_UNAVAILABLE,
            lane=lane,
            request_id=request_id,
            provider_policy_id=provider_policy,
            provider_ref=provider_ref,
            selected_model_class=selected_class,
            prompt=prompt,
            error="No installed local Ollama model matched the provider/model policy.",
            started_at=started,
        )

    payload = {
        "model": local_model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
            "num_predict": 900,
        },
    }
    request = urllib.request.Request(
        OLLAMA_LOOPBACK_GENERATE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return _result(
            status=RESULT_CALL_FAILED,
            lane=lane,
            request_id=request_id,
            provider_policy_id=provider_policy,
            provider_ref=provider_ref,
            selected_model_class=selected_class,
            local_model=local_model,
            prompt=prompt,
            error=str(exc),
            started_at=started,
        )

    raw_text = str(body.get("response") or body.get("thinking") or "")
    parsed, parse_error = _extract_json_object(raw_text)
    if not parsed:
        return _result(
            status=RESULT_JSON_PARSE_FAILED,
            lane=lane,
            request_id=request_id,
            provider_policy_id=provider_policy,
            provider_ref=provider_ref,
            selected_model_class=selected_class,
            local_model=local_model,
            prompt=prompt,
            raw_response_text=raw_text,
            error=parse_error or "Parsed JSON was empty.",
            started_at=started,
        )
    return _result(
        status=RESULT_OK,
        lane=lane,
        request_id=request_id,
        provider_policy_id=provider_policy,
        provider_ref=provider_ref,
        selected_model_class=selected_class,
        local_model=local_model,
        prompt=prompt,
        parsed_json=parsed,
        raw_response_text=raw_text,
        started_at=started,
    )


__all__ = [
    "AUTHORITY_BOUNDARY",
    "LOCAL_SHADOW_POLICY",
    "RESULT_CALL_FAILED",
    "RESULT_JSON_PARSE_FAILED",
    "RESULT_MODEL_UNAVAILABLE",
    "RESULT_OK",
    "RESULT_POLICY_BLOCKED",
    "RUNNER_ID",
    "generate_json",
    "installed_ollama_models",
    "select_local_model_for_class",
    "shadow_policy_allows_route",
]
