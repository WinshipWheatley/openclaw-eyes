from __future__ import annotations

"""Pure approval receipt checks for external expert execution handoff."""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from expert_escalation_packet import check_expert_escalation_packet


EXPERT_EXECUTION_APPROVAL_RECEIPT_SCHEMA_VERSION = 1
EXPERT_EXECUTION_APPROVAL_RECEIPT_TYPE = "external_expert.execution_approval_receipt"
PROVIDER_ROLE = "external_advisory_review"
ALLOWED_PROVIDERS = frozenset({"openrouter"})
ALLOWED_EXECUTION_SCOPES = frozenset({"single_expert_job"})

REQUIRED_FORBIDDEN_ACTION_ACKS = (
    "no_provider_or_model_drift",
    "no_telegram_return_without_result_check",
    "no_gmail_actions",
    "no_services_or_schedulers",
    "no_hermes_runtime_expansion",
    "no_legal_matter_data",
    "no_secret_or_env_inspection",
)

_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
_SAFE_HASH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,191}$")
_SAFE_ARTIFACT_ROOT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*(?:/[A-Za-z0-9][A-Za-z0-9_.-]*)*$")


@dataclass(frozen=True)
class ExpertExecutionApprovalReceiptCheck:
    passed: bool
    violations: list[str]
    recommended_action: str


def _truthy(value: object) -> bool:
    return value is True or str(value).strip().lower() in {"true", "yes", "1", "y", "on"}


def _normalize_policy_value(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _unique_violations(violations: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(violation for violation in violations if violation))


def _parse_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _now_value(now: datetime | str | None) -> datetime:
    if isinstance(now, datetime):
        current = now
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc)
    parsed = _parse_timestamp(now)
    return parsed or _utc_now()


def _safe_id(value: object) -> str:
    return str(value or "").strip()


def _append_required_field_violations(receipt: Mapping[str, Any], violations: list[str]) -> None:
    required_fields = (
        "receipt_schema_version",
        "receipt_type",
        "approval_id",
        "packet_id",
        "manifest_hash",
        "provider_plan_hash",
        "selected_provider",
        "provider_role",
        "execution_scope",
        "execution_allowed",
        "artifact_root",
        "approved_by",
        "requested_at",
        "approved_at",
        "expires_at",
        "decision",
        "guardian_hmac_binding",
        "forbidden_actions_acknowledged",
    )
    for field in required_fields:
        if field not in receipt:
            violations.append(f"missing_required_field:{field}")


def _append_shape_violations(receipt: Mapping[str, Any], violations: list[str]) -> None:
    if receipt.get("receipt_schema_version") != EXPERT_EXECUTION_APPROVAL_RECEIPT_SCHEMA_VERSION:
        violations.append("invalid_receipt_schema_version")
    if receipt.get("receipt_type") != EXPERT_EXECUTION_APPROVAL_RECEIPT_TYPE:
        violations.append("invalid_receipt_type")

    approval_id = _safe_id(receipt.get("approval_id"))
    packet_id = _safe_id(receipt.get("packet_id"))
    if not approval_id:
        violations.append("missing_approval_id")
    elif not _SAFE_ID_PATTERN.fullmatch(approval_id):
        violations.append("unsafe_approval_id")
    if not packet_id:
        violations.append("missing_packet_id")
    elif not _SAFE_ID_PATTERN.fullmatch(packet_id):
        violations.append("unsafe_packet_id")

    for field in ("manifest_hash", "provider_plan_hash"):
        value = _safe_id(receipt.get(field))
        if not value:
            violations.append(f"missing_{field}")
        elif not _SAFE_HASH_PATTERN.fullmatch(value):
            violations.append(f"invalid_{field}")

    provider = _normalize_policy_value(receipt.get("selected_provider"))
    if provider not in ALLOWED_PROVIDERS:
        violations.append(f"unknown_provider:{provider or 'missing'}")
    if _normalize_policy_value(receipt.get("provider_role")) != PROVIDER_ROLE:
        violations.append("invalid_provider_role")
    if _normalize_policy_value(receipt.get("execution_scope")) not in ALLOWED_EXECUTION_SCOPES:
        violations.append("invalid_execution_scope")
    if receipt.get("execution_allowed") is not True:
        violations.append("execution_not_approved")
    if _normalize_policy_value(receipt.get("decision")) != "approved":
        violations.append("decision_not_approved")

    approved_by = _safe_id(receipt.get("approved_by"))
    if not approved_by:
        violations.append("missing_approved_by")
    elif not _SAFE_ID_PATTERN.fullmatch(approved_by):
        violations.append("unsafe_approved_by")


def _append_timestamp_violations(
    receipt: Mapping[str, Any],
    violations: list[str],
    *,
    now: datetime | str | None,
) -> None:
    requested_at = _parse_timestamp(receipt.get("requested_at"))
    approved_at = _parse_timestamp(receipt.get("approved_at"))
    expires_at = _parse_timestamp(receipt.get("expires_at"))

    if requested_at is None:
        violations.append("malformed_timestamp:requested_at")
    if approved_at is None:
        violations.append("malformed_timestamp:approved_at")
    if expires_at is None:
        violations.append("malformed_timestamp:expires_at")
    if requested_at and approved_at and approved_at < requested_at:
        violations.append("invalid_receipt_timeline")
    if approved_at and expires_at and expires_at <= approved_at:
        violations.append("invalid_receipt_expiration")
    if expires_at and expires_at <= _now_value(now):
        violations.append("stale_approval_receipt")


def _append_artifact_root_violations(receipt: Mapping[str, Any], violations: list[str]) -> None:
    packet_id = _safe_id(receipt.get("packet_id"))
    artifact_root = str(receipt.get("artifact_root") or "").strip()
    if not artifact_root:
        violations.append("missing_artifact_root")
        return
    if (
        artifact_root.startswith(("/", "~"))
        or "\\" in artifact_root
        or ".." in artifact_root.split("/")
        or not _SAFE_ARTIFACT_ROOT_PATTERN.fullmatch(artifact_root)
    ):
        violations.append("unsafe_artifact_root")
        return
    if packet_id and packet_id not in artifact_root.split("/"):
        violations.append("artifact_root_not_packet_scoped")


def _append_guardian_binding_violations(receipt: Mapping[str, Any], violations: list[str]) -> None:
    binding = receipt.get("guardian_hmac_binding")
    if isinstance(binding, Mapping):
        if not binding:
            violations.append("missing_guardian_hmac_binding")
        elif not any(str(value or "").strip() for value in binding.values()):
            violations.append("missing_guardian_hmac_binding")
        return
    if not str(binding or "").strip():
        violations.append("missing_guardian_hmac_binding")


def _append_forbidden_ack_violations(receipt: Mapping[str, Any], violations: list[str]) -> None:
    acknowledged = receipt.get("forbidden_actions_acknowledged")
    if not isinstance(acknowledged, Mapping):
        violations.append("invalid_forbidden_actions_acknowledged")
        return
    for action in REQUIRED_FORBIDDEN_ACTION_ACKS:
        if not _truthy(acknowledged.get(action)):
            violations.append(f"missing_forbidden_action_ack:{action}")


def _append_packet_binding_violations(
    receipt: Mapping[str, Any],
    packet: Mapping[str, Any] | object | None,
    violations: list[str],
) -> None:
    if packet is None:
        return
    if not isinstance(packet, Mapping):
        violations.append("packet_must_be_object")
        return
    packet_check = check_expert_escalation_packet(packet)
    if not packet_check.passed:
        violations.append("packet_checker_failed")
        violations.extend(packet_check.violations)
    if str(packet.get("packet_id") or "") != str(receipt.get("packet_id") or ""):
        violations.append("packet_id_mismatch")


def _append_manifest_binding_violations(
    receipt: Mapping[str, Any],
    manifest: Mapping[str, Any] | object | None,
    violations: list[str],
) -> None:
    if manifest is None:
        return
    if not isinstance(manifest, Mapping):
        violations.append("manifest_must_be_object")
        return
    if str(manifest.get("packet_id") or "") != str(receipt.get("packet_id") or ""):
        violations.append("manifest_packet_id_mismatch")
    manifest_hash = str(manifest.get("manifest_hash") or "").strip()
    if manifest_hash and manifest_hash != str(receipt.get("manifest_hash") or ""):
        violations.append("manifest_hash_mismatch")
    if manifest.get("approval_required") is not True:
        violations.append("manifest_approval_not_required")
    if str(manifest.get("refusal_reason") or "").strip():
        violations.append("manifest_refused")


def _append_provider_binding_violations(
    receipt: Mapping[str, Any],
    provider_plan: Mapping[str, Any] | object | None,
    violations: list[str],
) -> None:
    if provider_plan is None:
        return
    if not isinstance(provider_plan, Mapping):
        violations.append("provider_plan_must_be_object")
        return
    if provider_plan.get("provider_allowed") is not True:
        violations.append("provider_plan_not_allowed")
    if str(provider_plan.get("packet_id") or "") != str(receipt.get("packet_id") or ""):
        violations.append("provider_plan_packet_id_mismatch")
    if _normalize_policy_value(provider_plan.get("selected_provider")) != _normalize_policy_value(receipt.get("selected_provider")):
        violations.append("provider_drift")
    if _normalize_policy_value(provider_plan.get("provider_role")) != _normalize_policy_value(receipt.get("provider_role")):
        violations.append("provider_role_drift")
    provider_hash = str(
        provider_plan.get("provider_plan_hash")
        or provider_plan.get("provider_policy_hash")
        or ""
    ).strip()
    if provider_hash and provider_hash != str(receipt.get("provider_plan_hash") or ""):
        violations.append("provider_plan_hash_mismatch")
    if provider_plan.get("execution_allowed") is not False:
        violations.append("provider_plan_execution_not_metadata_only")
    if str(provider_plan.get("model_selected") or "").strip():
        violations.append("provider_plan_model_selected")


def check_expert_execution_approval_receipt(
    receipt: Mapping[str, Any] | object | None,
    *,
    packet: Mapping[str, Any] | object | None = None,
    manifest: Mapping[str, Any] | object | None = None,
    provider_plan: Mapping[str, Any] | object | None = None,
    now: datetime | str | None = None,
) -> ExpertExecutionApprovalReceiptCheck:
    """Validate a bound approval receipt without executing anything."""
    if receipt is None:
        return ExpertExecutionApprovalReceiptCheck(
            passed=False,
            violations=["missing_approval_receipt"],
            recommended_action="reject",
        )
    if not isinstance(receipt, Mapping):
        return ExpertExecutionApprovalReceiptCheck(
            passed=False,
            violations=["approval_receipt_must_be_object"],
            recommended_action="reject",
        )

    violations: list[str] = []
    _append_required_field_violations(receipt, violations)
    _append_shape_violations(receipt, violations)
    _append_timestamp_violations(receipt, violations, now=now)
    _append_artifact_root_violations(receipt, violations)
    _append_guardian_binding_violations(receipt, violations)
    _append_forbidden_ack_violations(receipt, violations)
    _append_packet_binding_violations(receipt, packet, violations)
    _append_manifest_binding_violations(receipt, manifest, violations)
    _append_provider_binding_violations(receipt, provider_plan, violations)

    unique_violations = _unique_violations(violations)
    return ExpertExecutionApprovalReceiptCheck(
        passed=not unique_violations,
        violations=unique_violations,
        recommended_action="pass" if not unique_violations else "reject",
    )