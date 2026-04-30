from __future__ import annotations

"""No-execution job manifests for checked external expert escalation packets."""

from datetime import datetime, timezone
from typing import Any, Mapping

from expert_escalation_lane_policy import select_expert_lane
from expert_escalation_packet import check_expert_escalation_packet, render_expert_prompt


EXPERT_JOB_MANIFEST_SCHEMA_VERSION = 1
EXPERT_JOB_MANIFEST_TYPE = "external_expert.job_manifest"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_policy_value(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _as_string_list(value: object) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _safe_metadata(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _safe_metadata(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_metadata(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _execution_policy(packet: Mapping[str, Any]) -> Mapping[str, Any]:
    policy = packet.get("execution_policy")
    return policy if isinstance(policy, Mapping) else {}


def _base_manifest(
    *,
    packet: Mapping[str, Any] | object,
    manifest_created_at: str,
    checker_passed: bool,
    lane_policy_passed: bool,
) -> dict[str, Any]:
    packet_id = packet.get("packet_id") if isinstance(packet, Mapping) else ""
    task_type = packet.get("task_type") if isinstance(packet, Mapping) else ""
    return {
        "manifest_type": EXPERT_JOB_MANIFEST_TYPE,
        "schema_version": EXPERT_JOB_MANIFEST_SCHEMA_VERSION,
        "manifest_created_at": manifest_created_at,
        "packet_id": str(packet_id or ""),
        "task_type": _normalize_policy_value(task_type),
        "selected_lane": None,
        "runner_class": "external_expert",
        "execution_allowed": False,
        "approval_required": True,
        "checker_passed": checker_passed,
        "lane_policy_passed": lane_policy_passed,
        "allowed_outputs": [],
        "prompt_body": "",
        "input_paths": [],
        "forbidden_paths": [],
        "candidate_runner_metadata": {},
        "refusal_reason": "",
        "violations": [],
    }


def _refusal_manifest(
    *,
    packet: Mapping[str, Any] | object,
    manifest_created_at: str,
    checker_passed: bool,
    lane_policy_passed: bool,
    refusal_reason: str,
    violations: list[str],
) -> dict[str, Any]:
    manifest = _base_manifest(
        packet=packet,
        manifest_created_at=manifest_created_at,
        checker_passed=checker_passed,
        lane_policy_passed=lane_policy_passed,
    )
    manifest["refusal_reason"] = refusal_reason
    manifest["violations"] = list(dict.fromkeys(violations))
    return manifest


def _candidate_runner_metadata(packet: Mapping[str, Any], lane_plan: Mapping[str, Any]) -> dict[str, Any]:
    policy = _execution_policy(packet)
    candidate_runner = lane_plan.get("candidate_runner") or policy.get("candidate_runner")
    normalized_candidate = _normalize_policy_value(candidate_runner)
    if not normalized_candidate:
        return {}
    return {
        "candidate_runner": normalized_candidate,
        "metadata_only": True,
        "execution_allowed": False,
    }


def build_expert_job_manifest(packet: Mapping[str, Any] | object, *, created_at: str | None = None) -> dict[str, Any]:
    """Return a deterministic no-execution manifest or refusal for an expert packet."""
    manifest_created_at = created_at or _utc_now()
    packet_check = check_expert_escalation_packet(packet)
    if not packet_check.passed:
        return _refusal_manifest(
            packet=packet,
            manifest_created_at=manifest_created_at,
            checker_passed=False,
            lane_policy_passed=False,
            refusal_reason="packet_checker_failed",
            violations=list(packet_check.violations),
        )

    if not isinstance(packet, Mapping):
        return _refusal_manifest(
            packet=packet,
            manifest_created_at=manifest_created_at,
            checker_passed=False,
            lane_policy_passed=False,
            refusal_reason="packet_must_be_object",
            violations=["packet_must_be_object"],
        )

    lane_plan = select_expert_lane(packet)
    if lane_plan.get("refusal_reason") or lane_plan.get("execution_allowed") is not False:
        return _refusal_manifest(
            packet=packet,
            manifest_created_at=manifest_created_at,
            checker_passed=True,
            lane_policy_passed=False,
            refusal_reason=str(lane_plan.get("refusal_reason") or "lane_policy_failed"),
            violations=_as_string_list(lane_plan.get("violations")) or ["lane_policy_failed"],
        )

    manifest = _base_manifest(
        packet=packet,
        manifest_created_at=manifest_created_at,
        checker_passed=True,
        lane_policy_passed=True,
    )
    manifest.update({
        "selected_lane": str(lane_plan.get("selected_lane") or ""),
        "task_type": str(lane_plan.get("task_type") or _normalize_policy_value(packet.get("task_type"))),
        "allowed_outputs": _as_string_list(lane_plan.get("allowed_outputs")),
        "prompt_body": render_expert_prompt(packet),
        "input_paths": _as_string_list(packet.get("allowed_paths")),
        "forbidden_paths": _as_string_list(packet.get("forbidden_paths")),
        "candidate_runner_metadata": _candidate_runner_metadata(packet, lane_plan),
    })

    provider_metadata = packet.get("provider_metadata")
    if provider_metadata is not None:
        manifest["provider_metadata"] = _safe_metadata(provider_metadata)

    return manifest