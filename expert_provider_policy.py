from __future__ import annotations

"""Pure provider-candidate policy for checked external expert packets."""

from typing import Any, Mapping, Sequence

from expert_escalation_packet import ALLOWED_TASK_TYPES, check_expert_escalation_packet


PROVIDER_ROLE = "external_advisory_review"
ALLOWED_PROVIDERS = frozenset({"openrouter"})
OPENROUTER_ALLOWED_TASK_TYPES = frozenset(ALLOWED_TASK_TYPES)

_DANGEROUS_PROVIDER_NAMES = frozenset({
    "bash",
    "claude_code",
    "gmail",
    "hermes",
    "mcp",
    "openclaw_service",
    "shell",
    "ssh",
    "systemctl",
    "telegram",
})

_MODEL_SELECTION_FIELDS = frozenset({
    "candidate_model",
    "model",
    "model_name",
    "selected_model",
})


def _normalize_policy_value(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _truthy(value: object) -> bool:
    return value is True or str(value).strip().lower() in {"true", "yes", "1", "y", "on"}


def _execution_policy(packet: Mapping[str, Any]) -> Mapping[str, Any]:
    policy = packet.get("execution_policy")
    return policy if isinstance(policy, Mapping) else {}


def _as_provider_list(value: Sequence[str] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [_normalize_policy_value(value)]
    return [_normalize_policy_value(item) for item in value]


def _unique_violations(violations: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(violation for violation in violations if violation))


def _packet_candidate_provider(packet: Mapping[str, Any]) -> tuple[str, list[str]]:
    policy_provider = _normalize_policy_value(_execution_policy(packet).get("candidate_provider"))
    top_level_provider = _normalize_policy_value(packet.get("candidate_provider"))
    if policy_provider and top_level_provider and policy_provider != top_level_provider:
        return "", ["conflicting_candidate_provider"]
    return policy_provider or top_level_provider, []


def _has_model_selection(packet: Mapping[str, Any], lane_plan: Mapping[str, Any]) -> bool:
    policy = _execution_policy(packet)
    for field in _MODEL_SELECTION_FIELDS:
        if str(packet.get(field) or "").strip():
            return True
        if str(policy.get(field) or "").strip():
            return True
        if str(lane_plan.get(field) or "").strip():
            return True
    return False


def _provider_violations(provider: str) -> list[str]:
    if not provider:
        return ["missing_candidate_provider"]
    if provider in _DANGEROUS_PROVIDER_NAMES:
        return [f"unsafe_provider:{provider}"]
    if provider not in ALLOWED_PROVIDERS:
        return [f"unknown_provider:{provider}"]
    return []


def _refusal(
    *,
    packet: Mapping[str, Any] | object,
    lane_plan: Mapping[str, Any] | object,
    refusal_reason: str,
    violations: Sequence[str],
) -> dict[str, Any]:
    packet_id = packet.get("packet_id") if isinstance(packet, Mapping) else None
    task_type = packet.get("task_type") if isinstance(packet, Mapping) else None
    selected_lane = lane_plan.get("selected_lane") if isinstance(lane_plan, Mapping) else None
    return {
        "packet_id": str(packet_id or ""),
        "task_type": _normalize_policy_value(task_type),
        "selected_lane": _normalize_policy_value(selected_lane) or None,
        "provider_allowed": False,
        "selected_provider": None,
        "provider_role": None,
        "execution_allowed": False,
        "model_selected": None,
        "requires_operator_approval": True,
        "refusal_reason": refusal_reason,
        "violations": _unique_violations(violations),
    }


def _lane_plan_violations(packet: Mapping[str, Any], lane_plan: Mapping[str, Any] | object) -> list[str]:
    if not isinstance(lane_plan, Mapping):
        return ["lane_plan_must_be_object"]

    violations: list[str] = []
    task_type = _normalize_policy_value(packet.get("task_type"))
    selected_lane = _normalize_policy_value(lane_plan.get("selected_lane"))
    lane_task_type = _normalize_policy_value(lane_plan.get("task_type"))

    if lane_plan.get("execution_allowed") is not False:
        violations.append("lane_plan_execution_allowed")
    if _normalize_policy_value(lane_plan.get("runner_class")) != "external_expert":
        violations.append("invalid_lane_plan:runner_class")
    if lane_plan.get("requires_checker_pass") is not True:
        violations.append("invalid_lane_plan:requires_checker_pass")
    if selected_lane != task_type:
        violations.append("lane_plan_task_mismatch")
    if lane_task_type and lane_task_type != task_type:
        violations.append("lane_plan_task_mismatch")
    if selected_lane not in OPENROUTER_ALLOWED_TASK_TYPES:
        violations.append(f"provider_task_not_allowed:{selected_lane or task_type}")
    if str(lane_plan.get("refusal_reason") or "").strip():
        violations.append("lane_plan_refused")

    raw_lane_violations = lane_plan.get("violations")
    if isinstance(raw_lane_violations, Sequence) and not isinstance(raw_lane_violations, str):
        violations.extend(str(item) for item in raw_lane_violations if str(item).strip())
    return _unique_violations(violations)


def select_expert_provider(
    packet: Mapping[str, Any] | object,
    lane_plan: Mapping[str, Any] | object,
    *,
    available_providers: Sequence[str] | str | None = None,
) -> dict[str, Any]:
    """Return non-executing provider candidate metadata for a checked expert packet."""
    check = check_expert_escalation_packet(packet)
    if not check.passed:
        return _refusal(
            packet=packet,
            lane_plan=lane_plan,
            refusal_reason="packet_checker_failed",
            violations=check.violations,
        )
    if not isinstance(packet, Mapping):
        return _refusal(
            packet=packet,
            lane_plan=lane_plan,
            refusal_reason="packet_must_be_object",
            violations=["packet_must_be_object"],
        )

    task_type = _normalize_policy_value(packet.get("task_type"))
    if task_type not in OPENROUTER_ALLOWED_TASK_TYPES:
        return _refusal(
            packet=packet,
            lane_plan=lane_plan,
            refusal_reason="provider_task_not_allowed",
            violations=[f"provider_task_not_allowed:{task_type}"],
        )
    if not _truthy(packet.get("cloud_allowed")):
        return _refusal(
            packet=packet,
            lane_plan=lane_plan,
            refusal_reason="missing_explicit_cloud_allowed",
            violations=["missing_explicit_cloud_allowed"],
        )

    lane_violations = _lane_plan_violations(packet, lane_plan)
    if lane_violations:
        reason = "lane_plan_execution_allowed" if "lane_plan_execution_allowed" in lane_violations else "invalid_lane_plan"
        return _refusal(
            packet=packet,
            lane_plan=lane_plan,
            refusal_reason=reason,
            violations=lane_violations,
        )

    if not isinstance(lane_plan, Mapping):
        return _refusal(
            packet=packet,
            lane_plan=lane_plan,
            refusal_reason="lane_plan_must_be_object",
            violations=["lane_plan_must_be_object"],
        )
    if _has_model_selection(packet, lane_plan):
        return _refusal(
            packet=packet,
            lane_plan=lane_plan,
            refusal_reason="concrete_model_selection_not_allowed",
            violations=["concrete_model_selection_not_allowed"],
        )

    candidate_provider, provider_conflicts = _packet_candidate_provider(packet)
    availability_was_supplied = available_providers is not None
    available = list(dict.fromkeys(provider for provider in _as_provider_list(available_providers) if provider))
    available_violations: list[str] = []
    for provider in available:
        available_violations.extend(_provider_violations(provider))
    if available_violations:
        return _refusal(
            packet=packet,
            lane_plan=lane_plan,
            refusal_reason="provider_not_allowed",
            violations=available_violations,
        )

    selected_provider = candidate_provider or (available[0] if len(available) == 1 else "")
    violations = provider_conflicts + _provider_violations(selected_provider)
    if candidate_provider and availability_was_supplied and candidate_provider not in available:
        violations.append(f"candidate_provider_unavailable:{candidate_provider}")
    if violations:
        reason = "missing_candidate_provider" if "missing_candidate_provider" in violations else "provider_not_allowed"
        return _refusal(
            packet=packet,
            lane_plan=lane_plan,
            refusal_reason=reason,
            violations=violations,
        )

    return {
        "packet_id": str(packet.get("packet_id") or ""),
        "task_type": task_type,
        "selected_lane": _normalize_policy_value(lane_plan.get("selected_lane")),
        "provider_allowed": True,
        "selected_provider": selected_provider,
        "provider_role": PROVIDER_ROLE,
        "provider_candidate_is_metadata_only": True,
        "execution_allowed": False,
        "model_selected": None,
        "requires_operator_approval": True,
        "refusal_reason": "",
        "violations": [],
    }