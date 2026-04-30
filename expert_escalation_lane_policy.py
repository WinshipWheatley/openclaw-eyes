from __future__ import annotations

"""No-execution lane policy for checked external expert escalation packets."""

from typing import Any, Mapping

from expert_escalation_packet import ALLOWED_TASK_TYPES, check_expert_escalation_packet


EXPERT_LANE_MAP = {task_type: task_type for task_type in ALLOWED_TASK_TYPES}

LANE_ALLOWED_OUTPUTS = {
    "architecture_review": ("risk_summary", "architecture_notes", "recommendations"),
    "code_review": ("risk_summary", "correctness_notes", "test_suggestions"),
    "test_design": ("coverage_gaps", "test_scenarios", "fixture_plan"),
    "implementation_plan": ("implementation_steps", "risk_summary", "verification_plan"),
    "model_routing_review": ("routing_assessment", "policy_risks", "recommendations"),
    "prompt_hardening": ("boundary_risks", "hardened_prompt_notes", "test_cases"),
    "security_review": ("threat_notes", "risk_summary", "mitigations"),
    "local_model_benchmark_design": ("benchmark_plan", "fixture_plan", "success_criteria"),
}

_DANGEROUS_CANDIDATE_RUNNERS = frozenset({
    "bash",
    "claude",
    "claude_cli",
    "claude_code",
    "gmail",
    "mcp",
    "powershell",
    "rsync",
    "scp",
    "service",
    "shell",
    "ssh",
    "systemctl",
    "telegram",
    "zsh",
})


def _normalize_policy_value(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _execution_policy(packet: Mapping[str, Any]) -> Mapping[str, Any]:
    policy = packet.get("execution_policy")
    return policy if isinstance(policy, Mapping) else {}


def _expected_outputs(packet: Mapping[str, Any], selected_lane: str) -> list[str]:
    raw_outputs = packet.get("expected_outputs")
    if isinstance(raw_outputs, list):
        outputs = [str(item).strip() for item in raw_outputs if str(item).strip()]
    else:
        outputs = []
    return outputs or list(LANE_ALLOWED_OUTPUTS[selected_lane])


def _candidate_runner_violation(packet: Mapping[str, Any] | object) -> str:
    if not isinstance(packet, Mapping):
        return ""
    candidate_runner = _normalize_policy_value(_execution_policy(packet).get("candidate_runner"))
    if candidate_runner in _DANGEROUS_CANDIDATE_RUNNERS:
        return f"unsafe_candidate_runner:{candidate_runner}"
    return ""


def _refusal(
    *,
    packet: Mapping[str, Any] | object,
    refusal_reason: str,
    violations: list[str],
) -> dict[str, Any]:
    packet_id = packet.get("packet_id") if isinstance(packet, Mapping) else None
    task_type = packet.get("task_type") if isinstance(packet, Mapping) else None
    return {
        "packet_id": str(packet_id or ""),
        "selected_lane": None,
        "task_type": _normalize_policy_value(task_type),
        "runner_class": "external_expert",
        "execution_allowed": False,
        "requires_human_or_runner_approval": True,
        "requires_checker_pass": True,
        "allowed_outputs": [],
        "refusal_reason": refusal_reason,
        "violations": list(dict.fromkeys(violations)),
    }


def select_expert_lane(packet: Mapping[str, Any] | object) -> dict[str, Any]:
    """Return an abstract no-execution expert lane plan or a refusal."""
    check = check_expert_escalation_packet(packet)
    if not check.passed:
        violations = list(check.violations)
        candidate_violation = _candidate_runner_violation(packet)
        if candidate_violation:
            violations.append(candidate_violation)
        return _refusal(
            packet=packet,
            refusal_reason="packet_checker_failed",
            violations=violations,
        )

    if not isinstance(packet, Mapping):
        return _refusal(
            packet=packet,
            refusal_reason="packet_must_be_object",
            violations=["packet_must_be_object"],
        )

    task_type = _normalize_policy_value(packet.get("task_type"))
    selected_lane = EXPERT_LANE_MAP.get(task_type)
    if not selected_lane:
        return _refusal(
            packet=packet,
            refusal_reason="unknown_task_type",
            violations=[f"unknown_task_type:{task_type}"],
        )

    policy = _execution_policy(packet)
    candidate_runner = _normalize_policy_value(policy.get("candidate_runner"))
    candidate_violation = _candidate_runner_violation(packet)
    if candidate_violation:
        return _refusal(
            packet=packet,
            refusal_reason="unsafe_candidate_runner",
            violations=[candidate_violation],
        )

    plan: dict[str, Any] = {
        "packet_id": str(packet.get("packet_id") or ""),
        "selected_lane": selected_lane,
        "task_type": task_type,
        "runner_class": "external_expert",
        "execution_allowed": False,
        "requires_human_or_runner_approval": True,
        "requires_checker_pass": True,
        "allowed_outputs": _expected_outputs(packet, selected_lane),
        "refusal_reason": "",
        "violations": [],
    }
    if candidate_runner:
        plan["candidate_runner"] = candidate_runner
        plan["candidate_runner_is_metadata_only"] = True
    return plan