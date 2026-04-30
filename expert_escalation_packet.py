from __future__ import annotations

"""Pure schema helpers for sanitized Hermes-to-external-expert escalation packets."""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


EXPERT_ESCALATION_SCHEMA_VERSION = 1
EXPERT_ESCALATION_CREATED_BY = "hermes_openclaw_gateway"

ALLOWED_TASK_TYPES = frozenset({
    "architecture_review",
    "code_review",
    "test_design",
    "implementation_plan",
    "model_routing_review",
    "prompt_hardening",
    "security_review",
    "local_model_benchmark_design",
})

ALLOWED_DATA_CLASSIFICATIONS = frozenset({
    "synthetic_public",
    "sanitized_public",
    "public",
    "public_fixture",
    "non_sensitive",
})

REQUIRED_SENSITIVITY_ATTESTATIONS = (
    "no_secrets",
    "no_private_logs",
    "no_gmail_bodies",
    "no_legal_matter_data",
    "no_cpa_data",
    "no_music_law_data",
    "no_publishing_sensitive_data",
    "no_private_vault_paths",
)

REQUIRED_EXECUTION_POLICY = {
    "runner_class": "external_expert",
    "mode": "sequential_external_runner_only",
    "hermes_may_execute": False,
    "requires_checker_pass": True,
}

PROTECTED_DATA_MARKERS = frozenset({
    "/mnt/c/openclawlegalprivate",
    "/mnt/c/openclaw/logs",
    "openclawlegalprivate",
    ".env",
    "api key",
    "attorney",
    "billing record",
    "bot token",
    "catalog registration",
    "client",
    "client identity",
    "client identities",
    "client matter",
    "confidential",
    "contract",
    "cpa",
    "credential",
    "dispute",
    "disputes",
    "expense",
    "gmail",
    "gmail body",
    "income",
    "invoice",
    "law firm",
    "legal matter",
    "matter data",
    "music law",
    "oauth",
    "password",
    "payment",
    "pii",
    "pii vault",
    "private",
    "private correspondence",
    "private deal terms",
    "private key",
    "private logs",
    "private rights",
    "private vault",
    "publishing",
    "publishing catalog",
    "registration",
    "registrations",
    "rights admin",
    "royalties",
    "royalty",
    "secret",
    "split sheet",
    "split sheets",
    "splits",
    "ssn",
    "tax",
    "telegram_bot_token",
    "token file",
})

_MONEY_AMOUNT_PATTERN = re.compile(
    r"\$\s*\d|\b\d+(?:\.\d+)?\s*(?:dollars?|usd|bucks?)\b",
    re.IGNORECASE,
)
_PATH_TRAVERSAL_PATTERN = re.compile(r"(?:^|[\s/\\])\.\.(?:[/\\]|$)")
_ABSOLUTE_PATH_PATTERN = re.compile(r"(?:^|\s)(?:/home/openclaw|/mnt/c|~[/\\])", re.IGNORECASE)
_MODEL_RUNNER_LAUNCH_PATTERN = re.compile(
    r"\b(?:hermes\s+should\s+)?(?:run|launch|invoke|execute|start)\s+"
    r"(?:any\s+|the\s+|an?\s+|approved\s+)?"
    r"(?:codex|claude|gemini|aider|runner|model|model\s+runner|cloud\s+model|external\s+runner|external\s+expert)\b"
    r"|\b(?:codex|claude|gemini|aider)\s+(?:exec|run|launch)\b"
    r"|\b(?:shell|terminal)\b.{0,100}\b(?:codex|claude|gemini|aider|runner|model|external)\b",
    re.IGNORECASE | re.DOTALL,
)
_TELEGRAM_SEND_PATTERN = re.compile(
    r"\b(?:send|post|deliver)\b.{0,80}\btelegram\b|\btelegram\b.{0,80}\b(?:send|post|deliver)\b",
    re.IGNORECASE | re.DOTALL,
)
_RAW_TELEGRAM_CHAT_ID_PATTERN = re.compile(r"^-?\d{7,}$")
_TELEGRAM_BOT_TOKEN_PATTERN = re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b")
_SAFE_CANDIDATE_RUNNER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

_SCAN_EXCLUDED_FIELDS = frozenset({"forbidden_paths"})
_RAW_TELEGRAM_FIELD_NAMES = frozenset({"chat_id", "bot_token", "telegram_bot_token", "token"})
_UNSAFE_CANDIDATE_RUNNERS = frozenset({
    "bash",
    "cloud_shell",
    "powershell",
    "service",
    "shell",
    "subprocess",
    "telegram",
    "terminal",
})


@dataclass(frozen=True)
class ExpertEscalationCheck:
    passed: bool
    violations: list[str]
    recommended_action: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _truthy(value: object) -> bool:
    return value is True or str(value).strip().lower() in {"true", "yes", "1", "y", "on"}


def _normalize_policy_value(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:40] or "packet"


def _as_list(value: object) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _policy_text(value: object) -> str:
    if isinstance(value, Mapping):
        return " ".join(_policy_text(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_policy_text(item) for item in value)
    return str(value or "")


def _packet_scan_payload(packet: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in packet.items() if key not in _SCAN_EXCLUDED_FIELDS}


def _is_mapping(value: object) -> bool:
    return isinstance(value, Mapping)


def _default_execution_policy(task_type: str) -> dict[str, object]:
    policy = dict(REQUIRED_EXECUTION_POLICY)
    policy["preferred_lane"] = _normalize_policy_value(task_type)
    return policy


def build_expert_escalation_packet(
    *,
    operator_request_summary: str,
    task_type: str,
    data_classification: str,
    cloud_allowed: bool,
    sensitivity_attestation: Mapping[str, object],
    allowed_paths: Sequence[str] = (),
    forbidden_paths: Sequence[str] = (),
    prompt: str,
    expected_outputs: Sequence[str] = (),
    source_channel: str = "manual_hermes_gateway",
    packet_id: str | None = None,
    created_at: str | None = None,
    created_by: str = EXPERT_ESCALATION_CREATED_BY,
    execution_policy: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Build a packet candidate. Safety is decided by the checker, not here."""
    timestamp = created_at or _utc_now()
    normalized_task_type = _normalize_policy_value(task_type)
    safe_packet_id = packet_id or f"expert-{timestamp.replace(':', '').replace('-', '')}-{_safe_slug(task_type)}"

    return {
        "schema_version": EXPERT_ESCALATION_SCHEMA_VERSION,
        "packet_id": safe_packet_id,
        "created_at": timestamp,
        "created_by": str(created_by or ""),
        "source_channel": str(source_channel or ""),
        "operator_request_summary": str(operator_request_summary or "").strip(),
        "task_type": normalized_task_type,
        "data_classification": _normalize_policy_value(data_classification),
        "cloud_allowed": bool(cloud_allowed),
        "sensitivity_attestation": dict(sensitivity_attestation or {}),
        "allowed_paths": [str(path) for path in allowed_paths],
        "forbidden_paths": [str(path) for path in forbidden_paths],
        "prompt": str(prompt or "").strip(),
        "expected_outputs": [str(item) for item in expected_outputs],
        "execution_policy": dict(execution_policy or _default_execution_policy(normalized_task_type)),
    }


def _append_required_field_violations(packet: Mapping[str, Any], violations: list[str]) -> None:
    required_fields = (
        "schema_version",
        "packet_id",
        "created_at",
        "created_by",
        "source_channel",
        "operator_request_summary",
        "task_type",
        "data_classification",
        "cloud_allowed",
        "sensitivity_attestation",
        "allowed_paths",
        "forbidden_paths",
        "prompt",
        "expected_outputs",
        "execution_policy",
    )
    for field in required_fields:
        if field not in packet:
            violations.append(f"missing_required_field:{field}")


def _append_task_type_violations(packet: Mapping[str, Any], violations: list[str]) -> None:
    task_type = _normalize_policy_value(packet.get("task_type"))
    if not task_type:
        violations.append("missing_task_type")
    elif task_type not in ALLOWED_TASK_TYPES:
        violations.append(f"unknown_task_type:{task_type}")


def _append_classification_violations(packet: Mapping[str, Any], violations: list[str]) -> None:
    classification = _normalize_policy_value(packet.get("data_classification"))
    if not classification:
        violations.append("missing_data_classification")
    elif classification not in ALLOWED_DATA_CLASSIFICATIONS:
        violations.append(f"unknown_data_classification:{classification}")

    if not _truthy(packet.get("cloud_allowed")):
        violations.append("missing_explicit_cloud_allowed")


def _append_attestation_violations(packet: Mapping[str, Any], violations: list[str]) -> None:
    attestation = packet.get("sensitivity_attestation")
    if not _is_mapping(attestation):
        violations.append("invalid_sensitivity_attestation")
        return
    for key in REQUIRED_SENSITIVITY_ATTESTATIONS:
        if not _truthy(attestation.get(key)):
            violations.append(f"missing_sensitivity_attestation:{key}")


def _append_execution_policy_violations(packet: Mapping[str, Any], violations: list[str]) -> None:
    policy = packet.get("execution_policy")
    if not _is_mapping(policy):
        violations.append("invalid_execution_policy")
        return

    if _normalize_policy_value(policy.get("runner_class")) != "external_expert":
        violations.append("invalid_execution_policy:runner_class")
    if _normalize_policy_value(policy.get("mode")) != "sequential_external_runner_only":
        violations.append("invalid_execution_policy:mode")
    if policy.get("hermes_may_execute") is not False:
        violations.append("hermes_may_execute_not_false")
    if policy.get("requires_checker_pass") is not True:
        violations.append("checker_pass_not_required")

    preferred_lane = _normalize_policy_value(policy.get("preferred_lane"))
    if preferred_lane and preferred_lane not in ALLOWED_TASK_TYPES:
        violations.append(f"unknown_preferred_lane:{preferred_lane}")

    if "candidate_runner" in policy:
        candidate_runner = _normalize_policy_value(policy.get("candidate_runner"))
        if not candidate_runner:
            violations.append("empty_candidate_runner")
        elif candidate_runner in _UNSAFE_CANDIDATE_RUNNERS:
            violations.append(f"unsafe_candidate_runner:{candidate_runner}")
        elif not _SAFE_CANDIDATE_RUNNER_PATTERN.fullmatch(candidate_runner):
            violations.append("invalid_candidate_runner")


def _append_path_violations(packet: Mapping[str, Any], violations: list[str]) -> None:
    for field in ("allowed_paths", "forbidden_paths"):
        if not isinstance(packet.get(field), list):
            violations.append(f"invalid_path_list:{field}")
            continue
        for raw_path in _as_list(packet.get(field)):
            path = str(raw_path or "").strip()
            if not path:
                violations.append(f"empty_path:{field}")
                continue
            if _PATH_TRAVERSAL_PATTERN.search(path):
                violations.append(f"path_traversal:{field}")
            if field == "allowed_paths" and _ABSOLUTE_PATH_PATTERN.search(path):
                violations.append("absolute_allowed_path")


def _append_content_violations(packet: Mapping[str, Any], violations: list[str]) -> None:
    scan_text = _policy_text(_packet_scan_payload(packet))
    lowered = scan_text.lower()

    for marker in sorted(PROTECTED_DATA_MARKERS, key=len, reverse=True):
        if marker in lowered:
            violations.append(f"protected_marker:{marker}")
    if _MONEY_AMOUNT_PATTERN.search(scan_text):
        violations.append("protected_pattern:money_amount")
    if _PATH_TRAVERSAL_PATTERN.search(scan_text):
        violations.append("path_traversal:packet_body")
    if _ABSOLUTE_PATH_PATTERN.search(scan_text):
        violations.append("absolute_private_path")
    if _MODEL_RUNNER_LAUNCH_PATTERN.search(scan_text):
        violations.append("model_runner_launch_instruction")
    if _TELEGRAM_SEND_PATTERN.search(scan_text):
        violations.append("telegram_send_instruction")
    if _TELEGRAM_BOT_TOKEN_PATTERN.search(scan_text):
        violations.append("telegram_bot_token")


def _append_raw_telegram_violations(value: object, violations: list[str]) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized_key = _normalize_policy_value(key)
            if normalized_key in _RAW_TELEGRAM_FIELD_NAMES:
                violations.append(f"raw_telegram_field:{normalized_key}")
            _append_raw_telegram_violations(item, violations)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _append_raw_telegram_violations(item, violations)
        return

    text = str(value or "").strip()
    if _RAW_TELEGRAM_CHAT_ID_PATTERN.fullmatch(text):
        violations.append("raw_telegram_chat_id")
    if _TELEGRAM_BOT_TOKEN_PATTERN.search(text):
        violations.append("telegram_bot_token")


def _recommended_action_for(violations: Sequence[str]) -> str:
    if not violations:
        return "pass"
    return "reject"


def check_expert_escalation_packet(packet: Mapping[str, Any] | object) -> ExpertEscalationCheck:
    """Deterministically decide whether an expert escalation packet may be queued."""
    if not _is_mapping(packet):
        return ExpertEscalationCheck(
            passed=False,
            violations=["packet_must_be_object"],
            recommended_action="reject",
        )

    packet_map: Mapping[str, Any] = packet
    violations: list[str] = []

    _append_required_field_violations(packet_map, violations)
    if packet_map.get("schema_version") != EXPERT_ESCALATION_SCHEMA_VERSION:
        violations.append("invalid_schema_version")
    if not str(packet_map.get("prompt", "") or "").strip():
        violations.append("missing_prompt")
    if not str(packet_map.get("operator_request_summary", "") or "").strip():
        violations.append("missing_operator_request_summary")

    _append_task_type_violations(packet_map, violations)
    _append_classification_violations(packet_map, violations)
    _append_attestation_violations(packet_map, violations)
    _append_execution_policy_violations(packet_map, violations)
    _append_path_violations(packet_map, violations)
    _append_content_violations(packet_map, violations)
    _append_raw_telegram_violations(packet_map, violations)

    unique_violations = list(dict.fromkeys(violations))
    return ExpertEscalationCheck(
        passed=not unique_violations,
        violations=unique_violations,
        recommended_action=_recommended_action_for(unique_violations),
    )


def render_expert_prompt(packet: Mapping[str, Any]) -> str:
    """Return the sanitized prompt body only after the packet passes checks."""
    result = check_expert_escalation_packet(packet)
    if not result.passed:
        raise ValueError("unsafe expert escalation packet: " + ", ".join(result.violations))
    return str(packet.get("prompt", "") or "").strip()