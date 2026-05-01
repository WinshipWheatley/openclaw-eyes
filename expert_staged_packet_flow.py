from __future__ import annotations

"""Deterministic no-execution staging artifacts for expert synthetic handoffs."""

from typing import Any, Mapping, Sequence

from expert_synthetic_handoff import build_expert_synthetic_handoff


EXPERT_STAGED_PACKET_SCHEMA_VERSION = 1
EXPERT_STAGED_PACKET_ARTIFACT_TYPE = "external_expert.staged_packet_artifact"

FORBIDDEN_ACTIONS = (
    "provider_call",
    "concrete_model_selection",
    "runner_invocation",
    "telegram_return",
    "gmail_action",
    "live_guardian_approval_request",
    "service_timer_scheduler_wiring",
    "hermes_runtime_expansion",
    "private_data_or_secret_inspection",
)

_SUMMARY_LIMIT = 240
_NEXT_ALLOWED_ACTIONS = frozenset({
    "human_review_staged_artifact",
    "repair_sanitized_packet_and_rerun_checks",
})


def _is_mapping(value: object) -> bool:
    return isinstance(value, Mapping)


def _as_list(value: object) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return []


def _string_list(value: object) -> list[str]:
    return [str(item).strip() for item in _as_list(value) if str(item).strip()]


def _unique_violations(violations: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(violation for violation in violations if violation))


def _summary_for(handoff: Mapping[str, Any]) -> str:
    if handoff.get("passed") is True:
        return "Synthetic expert packet staged for human review; no external execution is authorized."
    return "Synthetic expert packet blocked by local validation; repair sanitized metadata before any handoff."


def _check_summary(check_payload: object) -> dict[str, Any]:
    if not isinstance(check_payload, Mapping):
        return {"passed": False, "violations": ["missing_check_summary"], "recommended_action": "reject"}
    return {
        "passed": check_payload.get("passed") is True,
        "violations": _string_list(check_payload.get("violations")),
        "recommended_action": str(check_payload.get("recommended_action") or "reject"),
    }


def _provider_plan_metadata(handoff: Mapping[str, Any]) -> dict[str, Any]:
    provider_plan = handoff.get("provider_plan")
    if not isinstance(provider_plan, Mapping):
        return {
            "provider_allowed": False,
            "execution_allowed": False,
            "model_selected": None,
            "refusal_reason": "missing_provider_plan",
            "violations": ["missing_provider_plan"],
        }
    return {
        "packet_id": str(provider_plan.get("packet_id") or ""),
        "task_type": str(provider_plan.get("task_type") or ""),
        "selected_lane": provider_plan.get("selected_lane"),
        "provider_allowed": provider_plan.get("provider_allowed") is True,
        "selected_provider": provider_plan.get("selected_provider"),
        "provider_role": provider_plan.get("provider_role"),
        "provider_candidate_is_metadata_only": provider_plan.get("provider_candidate_is_metadata_only") is True,
        "execution_allowed": provider_plan.get("execution_allowed") is True,
        "model_selected": provider_plan.get("model_selected"),
        "requires_operator_approval": provider_plan.get("requires_operator_approval") is True,
        "provider_plan_hash": str(provider_plan.get("provider_plan_hash") or ""),
        "refusal_reason": str(provider_plan.get("refusal_reason") or ""),
        "violations": _string_list(provider_plan.get("violations")),
    }


def _job_manifest_metadata(handoff: Mapping[str, Any]) -> dict[str, Any]:
    manifest = handoff.get("job_manifest")
    if not isinstance(manifest, Mapping):
        return {
            "execution_allowed": False,
            "approval_required": True,
            "refusal_reason": "missing_job_manifest",
            "violations": ["missing_job_manifest"],
        }
    return {
        "manifest_type": str(manifest.get("manifest_type") or ""),
        "packet_id": str(manifest.get("packet_id") or ""),
        "task_type": str(manifest.get("task_type") or ""),
        "selected_lane": manifest.get("selected_lane"),
        "runner_class": str(manifest.get("runner_class") or ""),
        "execution_allowed": manifest.get("execution_allowed") is True,
        "approval_required": manifest.get("approval_required") is True,
        "checker_passed": manifest.get("checker_passed") is True,
        "lane_policy_passed": manifest.get("lane_policy_passed") is True,
        "allowed_outputs": _string_list(manifest.get("allowed_outputs")),
        "manifest_hash": str(manifest.get("manifest_hash") or ""),
        "refusal_reason": str(manifest.get("refusal_reason") or ""),
        "violations": _string_list(manifest.get("violations")),
    }


def _receipt_validation_summary(handoff: Mapping[str, Any]) -> dict[str, Any]:
    receipt = handoff.get("synthetic_approval_receipt")
    check = _check_summary(handoff.get("receipt_check"))
    if not isinstance(receipt, Mapping):
        check["violations"] = _unique_violations(check["violations"] + ["missing_synthetic_receipt"])
        check["passed"] = False
        check["recommended_action"] = "reject"
        return check
    check.update({
        "approval_id": str(receipt.get("approval_id") or ""),
        "synthetic_only": receipt.get("synthetic_only") is True,
        "live_guardian_request_made": receipt.get("live_guardian_request_made") is True,
        "live_execution_allowed": receipt.get("live_execution_allowed") is True,
    })
    return check


def _result_validation_summary(handoff: Mapping[str, Any]) -> dict[str, Any]:
    result = handoff.get("synthetic_result_artifact")
    check = _check_summary(handoff.get("result_check"))
    if not isinstance(result, Mapping):
        check["violations"] = _unique_violations(check["violations"] + ["missing_synthetic_result"])
        check["passed"] = False
        check["recommended_action"] = "reject"
        return check
    check.update({
        "execution_status": str(result.get("execution_status") or ""),
        "model_selected": result.get("model_selected"),
        "execution_allowed": result.get("execution_allowed") is True,
        "artifact_paths": _string_list(result.get("artifact_paths")),
    })
    return check


def build_expert_staged_packet_artifact(
    packet: Mapping[str, Any] | object,
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Return a deterministic staged packet artifact for a synthetic expert handoff."""
    handoff = build_expert_synthetic_handoff(packet, created_at=created_at)
    artifact_created_at = str(handoff.get("created_at") or created_at or "")
    handoff_passed = handoff.get("passed") is True
    artifact: dict[str, Any] = {
        "artifact_type": EXPERT_STAGED_PACKET_ARTIFACT_TYPE,
        "schema_version": EXPERT_STAGED_PACKET_SCHEMA_VERSION,
        "created_at": artifact_created_at,
        "packet_id": str(handoff.get("packet_id") or ""),
        "provider_plan_metadata": _provider_plan_metadata(handoff),
        "provider_plan_hash": str(handoff.get("provider_plan_hash") or ""),
        "job_manifest_metadata": _job_manifest_metadata(handoff),
        "manifest_hash": str(handoff.get("manifest_hash") or ""),
        "synthetic_receipt_validation": _receipt_validation_summary(handoff),
        "synthetic_result_validation": _result_validation_summary(handoff),
        "execution_allowed": False,
        "provider_call_allowed": False,
        "telegram_return_allowed": False,
        "requires_human_review": True,
        "next_allowed_action": "human_review_staged_artifact" if handoff_passed else "repair_sanitized_packet_and_rerun_checks",
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "summary": _summary_for(handoff),
        "synthetic_handoff_passed": handoff_passed,
        "synthetic_handoff_violations": _string_list(handoff.get("violations")),
    }
    artifact_check = check_expert_staged_packet_artifact(artifact, packet=packet)
    artifact["staged_packet_check"] = artifact_check
    artifact["passed"] = artifact_check["passed"]
    artifact["violations"] = artifact_check["violations"]
    artifact["recommended_action"] = artifact_check["recommended_action"]
    return artifact


def _append_required_field_violations(artifact: Mapping[str, Any], violations: list[str]) -> None:
    required_fields = (
        "artifact_type",
        "schema_version",
        "created_at",
        "packet_id",
        "provider_plan_metadata",
        "provider_plan_hash",
        "job_manifest_metadata",
        "manifest_hash",
        "synthetic_receipt_validation",
        "synthetic_result_validation",
        "execution_allowed",
        "provider_call_allowed",
        "telegram_return_allowed",
        "requires_human_review",
        "next_allowed_action",
        "forbidden_actions",
        "summary",
    )
    for field in required_fields:
        if field not in artifact:
            violations.append(f"missing_required_field:{field}")


def _append_no_execution_violations(artifact: Mapping[str, Any], violations: list[str]) -> None:
    if artifact.get("execution_allowed") is not False:
        violations.append("execution_allowed")
    if artifact.get("provider_call_allowed") is not False:
        violations.append("provider_call_allowed")
    if artifact.get("telegram_return_allowed") is not False:
        violations.append("telegram_return_allowed")
    if artifact.get("requires_human_review") is not True:
        violations.append("human_review_not_required")


def _append_shape_violations(artifact: Mapping[str, Any], violations: list[str]) -> None:
    if artifact.get("artifact_type") != EXPERT_STAGED_PACKET_ARTIFACT_TYPE:
        violations.append("invalid_artifact_type")
    if artifact.get("schema_version") != EXPERT_STAGED_PACKET_SCHEMA_VERSION:
        violations.append("invalid_schema_version")
    summary = artifact.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        violations.append("missing_summary")
    elif len(summary) > _SUMMARY_LIMIT:
        violations.append("summary_too_long")
    if artifact.get("next_allowed_action") not in _NEXT_ALLOWED_ACTIONS:
        violations.append("invalid_next_allowed_action")
    forbidden_actions = _string_list(artifact.get("forbidden_actions"))
    for action in FORBIDDEN_ACTIONS:
        if action not in forbidden_actions:
            violations.append(f"missing_forbidden_action:{action}")


def _append_metadata_violations(artifact: Mapping[str, Any], violations: list[str]) -> None:
    provider_metadata = artifact.get("provider_plan_metadata")
    if not isinstance(provider_metadata, Mapping):
        violations.append("provider_plan_metadata_must_be_object")
    else:
        if provider_metadata.get("execution_allowed") is not False:
            violations.append("provider_plan_metadata_execution_allowed")
        if provider_metadata.get("model_selected") is not None:
            violations.append("provider_plan_metadata_model_selected")
        if str(provider_metadata.get("provider_plan_hash") or "") != str(artifact.get("provider_plan_hash") or ""):
            violations.append("provider_plan_hash_mismatch")

    manifest_metadata = artifact.get("job_manifest_metadata")
    if not isinstance(manifest_metadata, Mapping):
        violations.append("job_manifest_metadata_must_be_object")
    else:
        if manifest_metadata.get("execution_allowed") is not False:
            violations.append("job_manifest_metadata_execution_allowed")
        if str(manifest_metadata.get("manifest_hash") or "") != str(artifact.get("manifest_hash") or ""):
            violations.append("manifest_hash_mismatch")

    receipt_validation = artifact.get("synthetic_receipt_validation")
    if not isinstance(receipt_validation, Mapping):
        violations.append("synthetic_receipt_validation_must_be_object")
    else:
        if receipt_validation.get("passed") is not True:
            violations.append("synthetic_receipt_validation_failed")
        if receipt_validation.get("live_guardian_request_made") is not False:
            violations.append("live_guardian_request_made")
        if receipt_validation.get("live_execution_allowed") is not False:
            violations.append("live_execution_allowed")

    result_validation = artifact.get("synthetic_result_validation")
    if not isinstance(result_validation, Mapping):
        violations.append("synthetic_result_validation_must_be_object")
    else:
        if result_validation.get("passed") is not True:
            violations.append("synthetic_result_validation_failed")
        if result_validation.get("execution_allowed") is not False:
            violations.append("synthetic_result_execution_allowed")
        if result_validation.get("model_selected") is not None:
            violations.append("synthetic_result_model_selected")


def _append_handoff_binding_violations(
    artifact: Mapping[str, Any],
    packet: Mapping[str, Any] | object | None,
    violations: list[str],
) -> None:
    if packet is None:
        violations.append("missing_source_packet")
        return
    if not _is_mapping(packet):
        violations.append("packet_must_be_object")
        return

    expected_handoff = build_expert_synthetic_handoff(packet, created_at=str(artifact.get("created_at") or ""))
    if expected_handoff.get("passed") is not True:
        violations.append("synthetic_handoff_failed")
        violations.extend(_string_list(expected_handoff.get("violations")))

    if str(artifact.get("packet_id") or "") != str(expected_handoff.get("packet_id") or ""):
        violations.append("packet_id_mismatch")
    if str(artifact.get("provider_plan_hash") or "") != str(expected_handoff.get("provider_plan_hash") or ""):
        violations.append("provider_plan_hash_mismatch")
    if str(artifact.get("manifest_hash") or "") != str(expected_handoff.get("manifest_hash") or ""):
        violations.append("manifest_hash_mismatch")

    expected_provider_metadata = _provider_plan_metadata(expected_handoff)
    provider_metadata = artifact.get("provider_plan_metadata")
    if isinstance(provider_metadata, Mapping):
        for field in ("packet_id", "selected_provider", "provider_role", "provider_allowed", "model_selected"):
            if provider_metadata.get(field) != expected_provider_metadata.get(field):
                violations.append("provider_plan_metadata_mismatch")
                break

    expected_manifest_metadata = _job_manifest_metadata(expected_handoff)
    manifest_metadata = artifact.get("job_manifest_metadata")
    if isinstance(manifest_metadata, Mapping):
        for field in ("packet_id", "task_type", "selected_lane", "runner_class", "approval_required"):
            if manifest_metadata.get(field) != expected_manifest_metadata.get(field):
                violations.append("job_manifest_metadata_mismatch")
                break


def check_expert_staged_packet_artifact(
    artifact: Mapping[str, Any] | object,
    *,
    packet: Mapping[str, Any] | object | None = None,
) -> dict[str, Any]:
    """Validate a staged expert packet artifact without authorizing execution."""
    if not _is_mapping(artifact):
        return {
            "passed": False,
            "violations": ["artifact_must_be_object"],
            "recommended_action": "reject",
        }

    artifact_map: Mapping[str, Any] = artifact
    violations: list[str] = []
    _append_required_field_violations(artifact_map, violations)
    _append_shape_violations(artifact_map, violations)
    _append_no_execution_violations(artifact_map, violations)
    _append_metadata_violations(artifact_map, violations)
    _append_handoff_binding_violations(artifact_map, packet, violations)

    unique_violations = _unique_violations(violations)
    return {
        "passed": not unique_violations,
        "violations": unique_violations,
        "recommended_action": "pass" if not unique_violations else "reject",
    }