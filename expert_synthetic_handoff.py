from __future__ import annotations

"""Synthetic no-execution handoff flow for external expert rails."""

import re
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from expert_escalation_job_manifest import build_expert_job_manifest, hash_expert_job_manifest
from expert_escalation_lane_policy import select_expert_lane
from expert_escalation_packet import check_expert_escalation_packet
from expert_execution_approval_receipt import (
    EXPERT_EXECUTION_APPROVAL_RECEIPT_SCHEMA_VERSION,
    EXPERT_EXECUTION_APPROVAL_RECEIPT_TYPE,
    PROVIDER_ROLE,
    REQUIRED_FORBIDDEN_ACTION_ACKS,
    check_expert_execution_approval_receipt,
)
from expert_provider_policy import hash_expert_provider_plan, select_expert_provider
from expert_result_schema import EXPERT_RESULT_SCHEMA_VERSION, EXPERT_RESULT_TYPE, check_expert_result_artifact


EXPERT_SYNTHETIC_HANDOFF_SCHEMA_VERSION = 1
EXPERT_SYNTHETIC_HANDOFF_TYPE = "external_expert.synthetic_handoff"
SYNTHETIC_APPROVAL_EXPIRES_AT = "2099-01-01T00:00:00Z"

_SAFE_ID_CHARS = re.compile(r"[^A-Za-z0-9_.:-]+")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _packet_id(packet: Mapping[str, Any] | object) -> str:
    if not isinstance(packet, Mapping):
        return ""
    return str(packet.get("packet_id") or "").strip()


def _safe_id(value: str, *, fallback: str) -> str:
    cleaned = _SAFE_ID_CHARS.sub("-", str(value or "").strip()).strip("-._:")
    if len(cleaned) < 3:
        cleaned = fallback
    return cleaned[:127]


def _as_string_list(value: Sequence[str] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item).strip() for item in value if str(item).strip()]


def _unique_violations(violations: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(violation for violation in violations if violation))


def _check_payload(check: object) -> dict[str, Any]:
    return {
        "passed": bool(getattr(check, "passed", False)),
        "violations": list(getattr(check, "violations", []) or []),
        "recommended_action": str(getattr(check, "recommended_action", "reject") or "reject"),
    }


def _synthetic_receipt(
    *,
    packet: Mapping[str, Any] | object,
    manifest: Mapping[str, Any] | object,
    provider_plan: Mapping[str, Any] | object,
    created_at: str,
    expires_at: str,
) -> dict[str, Any]:
    packet_id = _packet_id(packet)
    approval_id = _safe_id(f"SYNTHETIC-{packet_id}", fallback="SYNTHETIC-EXPERT-HANDOFF")
    manifest_hash = str(manifest.get("manifest_hash") or "") if isinstance(manifest, Mapping) else ""
    provider_plan_hash = str(provider_plan.get("provider_plan_hash") or "") if isinstance(provider_plan, Mapping) else ""
    selected_provider = str(provider_plan.get("selected_provider") or "") if isinstance(provider_plan, Mapping) else ""
    provider_role = str(provider_plan.get("provider_role") or PROVIDER_ROLE) if isinstance(provider_plan, Mapping) else PROVIDER_ROLE

    return {
        "receipt_schema_version": EXPERT_EXECUTION_APPROVAL_RECEIPT_SCHEMA_VERSION,
        "receipt_type": EXPERT_EXECUTION_APPROVAL_RECEIPT_TYPE,
        "approval_id": approval_id,
        "packet_id": packet_id,
        "manifest_hash": manifest_hash,
        "provider_plan_hash": provider_plan_hash,
        "selected_provider": selected_provider,
        "provider_role": provider_role,
        "execution_scope": "single_expert_job",
        "execution_allowed": True,
        "artifact_root": f"expert_artifacts/{packet_id}",
        "approved_by": "synthetic-openclaw-proof",
        "requested_at": created_at,
        "approved_at": created_at,
        "expires_at": expires_at,
        "decision": "approved",
        "guardian_hmac_binding": {
            "binding_status": "synthetic",
            "packet_id": packet_id,
            "manifest_hash": manifest_hash,
            "provider_plan_hash": provider_plan_hash,
        },
        "forbidden_actions_acknowledged": {key: True for key in REQUIRED_FORBIDDEN_ACTION_ACKS},
        "synthetic_only": True,
        "live_guardian_request_made": False,
        "live_execution_allowed": False,
    }


def _synthetic_result_artifact(
    *,
    packet: Mapping[str, Any] | object,
    manifest: Mapping[str, Any] | object,
    provider_plan: Mapping[str, Any] | object,
    receipt: Mapping[str, Any],
    created_at: str,
) -> dict[str, Any]:
    packet_id = _packet_id(packet)
    artifact_root = str(receipt.get("artifact_root") or f"expert_artifacts/{packet_id}")
    selected_provider = str(provider_plan.get("selected_provider") or "") if isinstance(provider_plan, Mapping) else ""
    provider_role = str(provider_plan.get("provider_role") or PROVIDER_ROLE) if isinstance(provider_plan, Mapping) else PROVIDER_ROLE
    requested_outputs = list(manifest.get("allowed_outputs") or []) if isinstance(manifest, Mapping) else []
    manifest_hash = str(manifest.get("manifest_hash") or "") if isinstance(manifest, Mapping) else ""

    return {
        "result_schema_version": EXPERT_RESULT_SCHEMA_VERSION,
        "result_type": EXPERT_RESULT_TYPE,
        "packet_id": packet_id,
        "manifest_hash": manifest_hash,
        "approval_receipt_id": str(receipt.get("approval_id") or ""),
        "selected_provider": selected_provider,
        "provider_role": provider_role,
        "model_selected": None,
        "execution_status": "cancelled",
        "started_at": created_at,
        "completed_at": created_at,
        "summary": "Synthetic handoff validation path assembled without provider execution.",
        "findings": [
            {
                "severity": "info",
                "title": "Synthetic handoff proof",
                "detail": "Packet, provider plan, manifest, approval receipt, and result schema bindings were checked locally.",
                "evidence_refs": [artifact_root],
                "recommendation": "Keep this artifact metadata-only until a separate live approval lane is opened.",
            }
        ],
        "assumptions": ["Inputs are synthetic or sanitized public metadata."],
        "limitations": ["No live external system was invoked."],
        "requested_outputs": requested_outputs,
        "produced_outputs": [],
        "artifact_paths": [f"{artifact_root}/synthetic-result.json"],
        "stdout_excerpt": "",
        "stderr_excerpt": "",
        "safety_check": {
            "passed": True,
            "checked_at": created_at,
            "violations": [],
        },
        "synthetic_only": True,
        "execution_allowed": False,
    }


def build_expert_synthetic_handoff(
    packet: Mapping[str, Any] | object,
    *,
    created_at: str | None = None,
    expires_at: str = SYNTHETIC_APPROVAL_EXPIRES_AT,
    available_providers: Sequence[str] | str | None = None,
) -> dict[str, Any]:
    """Assemble a metadata-only external expert handoff proof from a sanitized packet."""
    handoff_created_at = created_at or _utc_now()
    packet_check = check_expert_escalation_packet(packet)
    lane_plan = select_expert_lane(packet)
    provider_plan = select_expert_provider(packet, lane_plan, available_providers=available_providers)
    manifest = build_expert_job_manifest(packet, created_at=handoff_created_at)
    receipt = _synthetic_receipt(
        packet=packet,
        manifest=manifest,
        provider_plan=provider_plan,
        created_at=handoff_created_at,
        expires_at=expires_at,
    )
    result_artifact = _synthetic_result_artifact(
        packet=packet,
        manifest=manifest,
        provider_plan=provider_plan,
        receipt=receipt,
        created_at=handoff_created_at,
    )

    receipt_check = check_expert_execution_approval_receipt(
        receipt,
        packet=packet,
        manifest=manifest,
        provider_plan=provider_plan,
        now=handoff_created_at,
    )
    result_check = check_expert_result_artifact(
        result_artifact,
        approval_receipt=receipt,
        manifest=manifest,
        provider_plan=provider_plan,
    )

    handoff: dict[str, Any] = {
        "handoff_type": EXPERT_SYNTHETIC_HANDOFF_TYPE,
        "schema_version": EXPERT_SYNTHETIC_HANDOFF_SCHEMA_VERSION,
        "created_at": handoff_created_at,
        "packet_id": _packet_id(packet),
        "synthetic_only": True,
        "execution_allowed": False,
        "service_wiring_allowed": False,
        "available_providers_supplied": available_providers is not None,
        "available_providers": _as_string_list(available_providers),
        "manifest_hash": str(manifest.get("manifest_hash") or "") if isinstance(manifest, Mapping) else "",
        "provider_plan_hash": str(provider_plan.get("provider_plan_hash") or "") if isinstance(provider_plan, Mapping) else "",
        "packet_check": _check_payload(packet_check),
        "lane_plan": lane_plan,
        "provider_plan": provider_plan,
        "job_manifest": manifest,
        "synthetic_approval_receipt": receipt,
        "synthetic_result_artifact": result_artifact,
        "receipt_check": _check_payload(receipt_check),
        "result_check": _check_payload(result_check),
    }
    handoff_check = check_expert_synthetic_handoff(handoff, packet=packet, now=handoff_created_at)
    handoff["handoff_check"] = handoff_check
    handoff["passed"] = handoff_check["passed"]
    handoff["violations"] = handoff_check["violations"]
    handoff["recommended_action"] = handoff_check["recommended_action"]
    return handoff


def _append_required_handoff_violations(handoff: Mapping[str, Any], violations: list[str]) -> None:
    required_fields = (
        "handoff_type",
        "schema_version",
        "created_at",
        "packet_id",
        "synthetic_only",
        "execution_allowed",
        "service_wiring_allowed",
        "manifest_hash",
        "provider_plan_hash",
        "lane_plan",
        "provider_plan",
        "job_manifest",
        "synthetic_approval_receipt",
        "synthetic_result_artifact",
    )
    for field in required_fields:
        if field not in handoff:
            violations.append(f"missing_required_field:{field}")


def _append_no_execution_violations(handoff: Mapping[str, Any], violations: list[str]) -> None:
    if handoff.get("execution_allowed") is not False:
        violations.append("handoff_execution_allowed")
    if handoff.get("service_wiring_allowed") is not False:
        violations.append("service_wiring_allowed")
    if handoff.get("synthetic_only") is not True:
        violations.append("synthetic_only_not_true")

    provider_plan = handoff.get("provider_plan")
    if isinstance(provider_plan, Mapping) and provider_plan.get("execution_allowed") is not False:
        violations.append("provider_plan_execution_allowed")

    manifest = handoff.get("job_manifest")
    if isinstance(manifest, Mapping) and manifest.get("execution_allowed") is not False:
        violations.append("manifest_execution_allowed")

    result_artifact = handoff.get("synthetic_result_artifact")
    if isinstance(result_artifact, Mapping) and result_artifact.get("execution_allowed") is not False:
        violations.append("result_execution_allowed")


def _append_hash_violations(handoff: Mapping[str, Any], violations: list[str]) -> None:
    provider_plan = handoff.get("provider_plan")
    if not isinstance(provider_plan, Mapping):
        violations.append("provider_plan_must_be_object")
    else:
        canonical_provider_hash = hash_expert_provider_plan(provider_plan)
        if str(provider_plan.get("provider_plan_hash") or "") != canonical_provider_hash:
            violations.append("provider_plan_hash_mismatch")
        if str(handoff.get("provider_plan_hash") or "") != canonical_provider_hash:
            violations.append("handoff_provider_plan_hash_mismatch")

    manifest = handoff.get("job_manifest")
    if not isinstance(manifest, Mapping):
        violations.append("manifest_must_be_object")
    else:
        canonical_manifest_hash = hash_expert_job_manifest(manifest)
        if str(manifest.get("manifest_hash") or "") != canonical_manifest_hash:
            violations.append("manifest_hash_mismatch")
        if str(handoff.get("manifest_hash") or "") != canonical_manifest_hash:
            violations.append("handoff_manifest_hash_mismatch")


def _append_expected_rail_violations(
    handoff: Mapping[str, Any],
    packet: Mapping[str, Any] | object | None,
    violations: list[str],
) -> None:
    if packet is None:
        violations.append("missing_source_packet")
        return
    if not isinstance(packet, Mapping):
        violations.append("packet_must_be_object")
        return

    packet_check = check_expert_escalation_packet(packet)
    if not packet_check.passed:
        violations.append("packet_checker_failed")
        violations.extend(packet_check.violations)
    if str(handoff.get("packet_id") or "") != str(packet.get("packet_id") or ""):
        violations.append("handoff_packet_id_mismatch")

    expected_lane_plan = select_expert_lane(packet)
    lane_plan = handoff.get("lane_plan")
    if not isinstance(lane_plan, Mapping):
        violations.append("lane_plan_must_be_object")
    else:
        for field in ("packet_id", "selected_lane", "task_type", "runner_class", "execution_allowed"):
            if lane_plan.get(field) != expected_lane_plan.get(field):
                violations.append("lane_plan_mismatch")
                break

    available_arg: Sequence[str] | None = None
    if handoff.get("available_providers_supplied") is True:
        available_arg = _as_string_list(handoff.get("available_providers"))
    expected_provider_plan = select_expert_provider(packet, expected_lane_plan, available_providers=available_arg)
    provider_plan = handoff.get("provider_plan")
    if isinstance(provider_plan, Mapping):
        if hash_expert_provider_plan(provider_plan) != hash_expert_provider_plan(expected_provider_plan):
            violations.append("provider_plan_mismatch")

    manifest = handoff.get("job_manifest")
    if isinstance(manifest, Mapping):
        expected_manifest = build_expert_job_manifest(packet, created_at=str(manifest.get("manifest_created_at") or ""))
        if hash_expert_job_manifest(manifest) != hash_expert_job_manifest(expected_manifest):
            violations.append("manifest_mismatch")


def _append_synthetic_artifact_violations(handoff: Mapping[str, Any], packet: Mapping[str, Any] | object | None, violations: list[str], now: str | None) -> None:
    receipt = handoff.get("synthetic_approval_receipt")
    manifest = handoff.get("job_manifest")
    provider_plan = handoff.get("provider_plan")
    result_artifact = handoff.get("synthetic_result_artifact")

    if not isinstance(receipt, Mapping):
        violations.append("approval_receipt_must_be_object")
        return
    if receipt.get("synthetic_only") is not True:
        violations.append("receipt_synthetic_only_not_true")
    if receipt.get("live_guardian_request_made") is not False:
        violations.append("live_guardian_request_made")
    if receipt.get("live_execution_allowed") is not False:
        violations.append("live_execution_allowed")

    receipt_check = check_expert_execution_approval_receipt(
        receipt,
        packet=packet,
        manifest=manifest,
        provider_plan=provider_plan,
        now=now,
    )
    if not receipt_check.passed:
        violations.append("approval_receipt_failed")
        violations.extend(receipt_check.violations)

    if not isinstance(result_artifact, Mapping):
        violations.append("result_artifact_must_be_object")
        return
    result_check = check_expert_result_artifact(
        result_artifact,
        approval_receipt=receipt,
        manifest=manifest,
        provider_plan=provider_plan,
    )
    if not result_check.passed:
        violations.append("result_artifact_failed")
        violations.extend(result_check.violations)


def check_expert_synthetic_handoff(
    handoff: Mapping[str, Any] | object,
    *,
    packet: Mapping[str, Any] | object | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Validate the synthetic handoff proof without executing any provider or runner."""
    if not isinstance(handoff, Mapping):
        return {
            "passed": False,
            "violations": ["handoff_must_be_object"],
            "recommended_action": "reject",
        }

    violations: list[str] = []
    _append_required_handoff_violations(handoff, violations)
    if handoff.get("handoff_type") != EXPERT_SYNTHETIC_HANDOFF_TYPE:
        violations.append("invalid_handoff_type")
    if handoff.get("schema_version") != EXPERT_SYNTHETIC_HANDOFF_SCHEMA_VERSION:
        violations.append("invalid_schema_version")
    _append_no_execution_violations(handoff, violations)
    _append_hash_violations(handoff, violations)
    _append_expected_rail_violations(handoff, packet, violations)
    _append_synthetic_artifact_violations(handoff, packet, violations, now)

    unique_violations = _unique_violations(violations)
    return {
        "passed": not unique_violations,
        "violations": unique_violations,
        "recommended_action": "pass" if not unique_violations else "reject",
    }