from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any


ROUTING_SCHEMA_VERSION = "polish_loop_task_routing_v1"

SIZE_CLASS_ORDER = ("small", "medium", "large", "architect", "unknown")
RISK_FLAG_ORDER = (
    "sensitive",
    "legal",
    "financial",
    "external_action",
    "credential",
    "production_mutation",
    "unknown",
)

_SIZE_RANK = {"small": 0, "medium": 1, "large": 2, "architect": 3, "unknown": 4}

_TEXT_KEYS_FOR_RISK = (
    "task_id",
    "task_type",
    "type",
    "domain",
    "category",
    "goal",
    "description",
    "summary",
    "scope",
    "success_criteria",
    "acceptance_ref",
    "tests_to_run",
    "allowed_files",
    "allowed_actions",
    "notes",
    "output_contract",
)

_TEXT_KEYS_FOR_SIZE = (
    "goal",
    "description",
    "summary",
    "scope",
    "success_criteria",
    "acceptance_ref",
    "tests_to_run",
    "allowed_files",
    "allowed_actions",
    "notes",
    "output_contract",
)

_LIST_KEY_GROUPS = {
    "allowed_files": ("allowed_files", "files", "files_to_touch", "exact_files", "source_files"),
    "forbidden_files": ("forbidden_files", "excluded_files", "out_of_scope_files"),
    "allowed_actions": ("allowed_actions",),
    "forbidden_actions": ("forbidden_actions", "prohibited_actions"),
    "tests_to_run": ("tests_to_run", "tests", "validation", "required_tests"),
    "stop_conditions": ("stop_conditions", "stop_if"),
    "scope": ("scope", "steps", "implementation_steps"),
    "success_criteria": ("success_criteria", "acceptance_criteria"),
}

_RISK_TERMS = {
    "sensitive": (
        "sensitive",
        "private",
        "pii",
        "personal data",
        "vault",
        "sealed",
        "raw text message",
        "text-message evidence",
    ),
    "legal": (
        "legal",
        "lawyer",
        "attorney",
        "court",
        "litigation",
        "evidence",
        "legal sealed",
    ),
    "financial": (
        "bank",
        "banking",
        "finance",
        "financial",
        "invoice",
        "payment",
        "payroll",
        "tax",
        "receivable",
        "real financial",
    ),
    "external_action": (
        "send email",
        "email sending",
        "send telegram",
        "telegram delivery",
        "post to slack",
        "webhook",
        "external action",
        "live action",
        "openrouter",
        "cloud model",
    ),
    "credential": (
        "credential",
        "credentials",
        "api key",
        "token",
        "password",
        "secret",
        ".chief.env",
        "ssh key",
        "bearer",
    ),
    "production_mutation": (
        "production",
        "prod db",
        "prod database",
        "prod ledger",
        "production db",
        "production database",
        "production ledger",
        "production queue",
        "systemd",
        "restart service",
        "reload daemon",
        "live loop",
        "enable flag",
        "deploy",
    ),
}


def classify_task_routing(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a deterministic routing contract for a parsed Polish Loop payload."""

    normalized_payload: Mapping[str, Any] = payload or {}
    if not isinstance(normalized_payload, Mapping):
        normalized_payload = {"raw_payload": normalized_payload}

    allowed_files = _first_list(normalized_payload, _LIST_KEY_GROUPS["allowed_files"])
    forbidden_files = _first_list(normalized_payload, _LIST_KEY_GROUPS["forbidden_files"])
    allowed_actions = _first_list(normalized_payload, _LIST_KEY_GROUPS["allowed_actions"])
    forbidden_actions = _first_list(normalized_payload, _LIST_KEY_GROUPS["forbidden_actions"])
    tests_to_run = _first_list(normalized_payload, _LIST_KEY_GROUPS["tests_to_run"])
    stop_conditions = _first_list(normalized_payload, _LIST_KEY_GROUPS["stop_conditions"])
    scope_items = _first_list(normalized_payload, _LIST_KEY_GROUPS["scope"])
    success_criteria = _first_list(normalized_payload, _LIST_KEY_GROUPS["success_criteria"])

    stable_payload_text = _stable_json_text(normalized_payload)
    size_basis = _size_basis(
        normalized_payload,
        allowed_files=allowed_files,
        tests_to_run=tests_to_run,
        scope_items=scope_items,
        success_criteria=success_criteria,
        stable_payload_text=stable_payload_text,
    )
    size_class = _size_class(size_basis)
    risk_flags = _risk_flags(
        normalized_payload,
        forbidden_actions=forbidden_actions,
        stable_payload_text=stable_payload_text,
    )
    readiness, holding_reason = _readiness(size_class, size_basis, risk_flags)
    target_runner_tier = _target_runner_tier(size_class, size_basis)
    minimum_model_tier = _minimum_model_tier(size_class)
    local_model_allowed = readiness == "ready" and size_class in {"small", "medium"}
    cloud_allowed = _cloud_allowed(normalized_payload, risk_flags)

    return {
        "schema_version": ROUTING_SCHEMA_VERSION,
        "size_class": size_class,
        "size_basis": size_basis,
        "task_type": _task_type(normalized_payload),
        "risk_flags": risk_flags,
        "readiness": readiness,
        "holding_reason": holding_reason,
        "target_runner_tier": target_runner_tier,
        "minimum_model_tier": minimum_model_tier,
        "local_model_allowed": local_model_allowed,
        "cloud_allowed": cloud_allowed,
        "token_budget": _token_budget(size_class),
        "tool_call_budget": _tool_call_budget(size_class),
        "decomposition_required": size_class in {"large", "architect"},
        "allowed_files": allowed_files,
        "forbidden_files": forbidden_files,
        "allowed_actions": allowed_actions,
        "forbidden_actions": forbidden_actions,
        "tests_to_run": tests_to_run,
        "stop_conditions": stop_conditions,
    }


def _size_basis(
    payload: Mapping[str, Any],
    *,
    allowed_files: list[str],
    tests_to_run: list[str],
    scope_items: list[str],
    success_criteria: list[str],
    stable_payload_text: str,
) -> dict[str, Any]:
    char_count = len(_join_text_keys(payload, _TEXT_KEYS_FOR_SIZE)) or len(stable_payload_text)
    estimated_token_count = 0 if char_count == 0 else max(1, (char_count + 3) // 4)
    estimated_minutes = _estimated_minutes(payload)
    missing_bounds = []
    if not _value_to_text(payload.get("goal")) and not _value_to_text(payload.get("description")):
        missing_bounds.append("goal")
    if not allowed_files:
        missing_bounds.append("allowed_files")
    if not tests_to_run:
        missing_bounds.append("tests_to_run")
    if not success_criteria and "acceptance_ref" not in payload:
        missing_bounds.append("success_criteria")

    return {
        "file_count": len(allowed_files),
        "scope_bullet_count": len(scope_items) + len(success_criteria),
        "test_count": len(tests_to_run),
        "char_count": char_count,
        "estimated_token_count": estimated_token_count,
        "estimated_minutes": estimated_minutes,
        "missing_bounds": missing_bounds,
        "drivers": [],
    }


def _size_class(size_basis: dict[str, Any]) -> str:
    if size_basis["missing_bounds"]:
        basis = dict(size_basis)
        basis["drivers"] = [f"missing:{name}" for name in size_basis["missing_bounds"]]
        size_basis.clear()
        size_basis.update(basis)
        return "unknown"

    drivers: list[str] = []
    size_class = "small"
    metric_thresholds = (
        ("file_count", 3, "medium", 7, "large", 12, "architect"),
        ("scope_bullet_count", 4, "medium", 10, "large", 16, "architect"),
        ("test_count", 3, "medium", 7, "large", 12, "architect"),
        ("estimated_token_count", 1200, "medium", 4000, "large", 8000, "architect"),
        ("estimated_minutes", 90, "medium", 240, "large", 480, "architect"),
    )
    for metric, medium_at, medium_class, large_at, large_class, architect_at, architect_class in metric_thresholds:
        value = size_basis.get(metric)
        if value is None:
            continue
        if value >= architect_at:
            size_class = _max_size(size_class, architect_class)
            drivers.append(f"{metric}>={architect_at}")
        elif value >= large_at:
            size_class = _max_size(size_class, large_class)
            drivers.append(f"{metric}>={large_at}")
        elif value >= medium_at:
            size_class = _max_size(size_class, medium_class)
            drivers.append(f"{metric}>={medium_at}")

    size_basis["drivers"] = drivers or ["bounded_small"]
    return size_class


def _risk_flags(
    payload: Mapping[str, Any],
    *,
    forbidden_actions: list[str],
    stable_payload_text: str,
) -> list[str]:
    risk_values = set(_explicit_risk_flags(payload))
    risk_text = _join_text_keys(payload, _TEXT_KEYS_FOR_RISK).lower()
    if not risk_text:
        risk_text = stable_payload_text.lower()

    for flag, terms in _RISK_TERMS.items():
        if any(_contains_term(risk_text, term) for term in terms):
            risk_values.add(flag)

    if not _has_explicit_risk_statement(payload, forbidden_actions) and not risk_values:
        risk_values.add("unknown")

    return [flag for flag in RISK_FLAG_ORDER if flag in risk_values]


def _readiness(size_class: str, size_basis: Mapping[str, Any], risk_flags: Sequence[str]) -> tuple[str, str]:
    blocking_flags = [flag for flag in risk_flags if flag != "unknown"]
    if blocking_flags:
        return "blocked", "blocked_risk_flags:" + ",".join(blocking_flags)
    if "unknown" in risk_flags or size_class == "unknown":
        reasons = []
        if "unknown" in risk_flags:
            reasons.append("unknown_risk")
        for missing in size_basis.get("missing_bounds", []):
            reasons.append(f"missing_{missing}")
        return "holding", "needs_human_classification:" + ",".join(reasons)
    if size_class in {"large", "architect"}:
        return "holding", f"{size_class}_requires_decomposition"
    return "ready", ""


def _target_runner_tier(size_class: str, size_basis: Mapping[str, Any]) -> str:
    if size_class == "small":
        if (
            size_basis.get("file_count", 0) <= 1
            and size_basis.get("scope_bullet_count", 0) <= 2
            and size_basis.get("test_count", 0) <= 1
        ):
            return "quick"
        return "surgical"
    if size_class == "medium":
        return "standard"
    return "architect"


def _minimum_model_tier(size_class: str) -> str:
    return {
        "small": "small",
        "medium": "medium",
        "large": "large",
        "architect": "architect",
        "unknown": "human_classification",
    }[size_class]


def _token_budget(size_class: str) -> int:
    return {
        "small": 4_000,
        "medium": 8_000,
        "large": 16_000,
        "architect": 32_000,
        "unknown": 0,
    }[size_class]


def _tool_call_budget(size_class: str) -> int:
    return {
        "small": 8,
        "medium": 15,
        "large": 30,
        "architect": 60,
        "unknown": 0,
    }[size_class]


def _cloud_allowed(payload: Mapping[str, Any], risk_flags: Sequence[str]) -> bool:
    if any(flag in risk_flags for flag in ("sensitive", "legal", "financial", "credential", "unknown")):
        return False
    return _truthy(payload.get("cloud_allowed")) or _truthy(payload.get("external_model_allowed"))


def _task_type(payload: Mapping[str, Any]) -> str:
    for key in ("task_type", "type", "category", "domain"):
        value = _value_to_text(payload.get(key)).strip().lower()
        if value:
            return re.sub(r"[^a-z0-9_]+", "_", value).strip("_") or "unknown"
    return "unknown"


def _explicit_risk_flags(payload: Mapping[str, Any]) -> list[str]:
    if "risk_flags" not in payload:
        return []
    explicit = []
    for value in _as_list(payload.get("risk_flags")):
        normalized = _value_to_text(value).strip().lower()
        normalized = re.sub(r"[^a-z0-9_]+", "_", normalized).strip("_")
        if normalized in RISK_FLAG_ORDER:
            explicit.append(normalized)
    return explicit


def _has_explicit_risk_statement(payload: Mapping[str, Any], forbidden_actions: Sequence[str]) -> bool:
    return (
        "risk_flags" in payload
        or bool(_value_to_text(payload.get("risk_level")).strip())
        or bool(_value_to_text(payload.get("risk_assessment")).strip())
        or bool(forbidden_actions)
    )


def _estimated_minutes(payload: Mapping[str, Any]) -> int:
    for key in ("estimated_minutes", "minutes", "estimated_duration_minutes"):
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float):
            return max(0, int(value))
        text = _value_to_text(value)
        if text:
            match = re.search(r"\d+", text)
            if match:
                return int(match.group(0))
    return 0


def _max_size(left: str, right: str) -> str:
    return right if _SIZE_RANK[right] > _SIZE_RANK[left] else left


def _first_list(payload: Mapping[str, Any], keys: Sequence[str]) -> list[str]:
    for key in keys:
        if key in payload:
            items = _as_list(payload.get(key))
            if items:
                return items
    return []


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        lines = [_clean_item(line) for line in value.splitlines()]
        return [line for line in lines if line]
    if isinstance(value, Mapping):
        return [_stable_json_text(value)]
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        items = []
        for item in value:
            text = _value_to_text(item).strip()
            if text:
                items.append(text)
        return items
    text = _value_to_text(value).strip()
    return [text] if text else []


def _clean_item(value: str) -> str:
    return re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", value).strip()


def _join_text_keys(payload: Mapping[str, Any], keys: Sequence[str]) -> str:
    return "\n".join(
        text
        for key in keys
        for text in [_value_to_text(payload.get(key)).strip()]
        if text
    )


def _value_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return _stable_json_text(value)
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return "\n".join(_value_to_text(item) for item in value)
    return str(value)


def _stable_json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), default=str)


def _contains_term(text: str, term: str) -> bool:
    return re.search(rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])", text) is not None


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "allowed"}
    return False


__all__ = ["ROUTING_SCHEMA_VERSION", "classify_task_routing"]
