from __future__ import annotations

"""Pure schema checks for external expert result artifacts."""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from expert_escalation_packet import PROTECTED_DATA_MARKERS
from expert_execution_approval_receipt import check_expert_execution_approval_receipt


EXPERT_RESULT_SCHEMA_VERSION = 1
EXPERT_RESULT_TYPE = "external_expert.result_artifact"
PROVIDER_ROLE = "external_advisory_review"
ALLOWED_EXECUTION_STATUSES = frozenset({"succeeded", "failed", "cancelled", "timed_out"})
ALLOWED_FINDING_SEVERITIES = frozenset({"info", "low", "medium", "high", "critical"})

_SUMMARY_LIMIT = 2000
_EXCERPT_LIMIT = 4000
_MAX_ARTIFACT_PATHS = 25
_MAX_ARTIFACT_PATH_LENGTH = 300

_MONEY_AMOUNT_PATTERN = re.compile(
    r"\$\s*\d|\b\d+(?:\.\d+)?\s*(?:dollars?|usd|bucks?)\b",
    re.IGNORECASE,
)
_ABSOLUTE_PATH_PATTERN = re.compile(r"(?:^|\s)(?:/home/openclaw|/mnt/c|~[/\\])", re.IGNORECASE)
_TELEGRAM_BOT_TOKEN_PATTERN = re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b")
_SAFE_PATH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*(?:/[A-Za-z0-9][A-Za-z0-9_.-]*)*$")
_RAW_PRIVATE_FIELD_NAMES = frozenset({"chat_id", "bot_token", "telegram_bot_token", "token", "gmail_body"})


@dataclass(frozen=True)
class ExpertResultArtifactCheck:
    passed: bool
    violations: list[str]
    recommended_action: str


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


def _policy_text(value: object) -> str:
    if isinstance(value, Mapping):
        return " ".join(_policy_text(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_policy_text(item) for item in value)
    return str(value or "")


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _append_required_field_violations(result: Mapping[str, Any], violations: list[str]) -> None:
    required_fields = (
        "result_schema_version",
        "result_type",
        "packet_id",
        "manifest_hash",
        "approval_receipt_id",
        "selected_provider",
        "provider_role",
        "model_selected",
        "execution_status",
        "started_at",
        "completed_at",
        "summary",
        "findings",
        "assumptions",
        "limitations",
        "requested_outputs",
        "produced_outputs",
        "artifact_paths",
        "stdout_excerpt",
        "stderr_excerpt",
        "safety_check",
    )
    for field in required_fields:
        if field not in result:
            violations.append(f"missing_required_field:{field}")


def _append_shape_violations(
    result: Mapping[str, Any],
    violations: list[str],
    *,
    allow_model_selected: bool,
) -> None:
    if result.get("result_schema_version") != EXPERT_RESULT_SCHEMA_VERSION:
        violations.append("invalid_result_schema_version")
    if result.get("result_type") != EXPERT_RESULT_TYPE:
        violations.append("invalid_result_type")
    if not str(result.get("packet_id") or "").strip():
        violations.append("missing_packet_id")
    if not str(result.get("manifest_hash") or "").strip():
        violations.append("missing_manifest_hash")
    if not str(result.get("approval_receipt_id") or "").strip():
        violations.append("missing_approval_receipt_id")
    if not str(result.get("selected_provider") or "").strip():
        violations.append("missing_selected_provider")
    if _normalize_policy_value(result.get("provider_role")) != PROVIDER_ROLE:
        violations.append("invalid_provider_role")
    if result.get("model_selected") is not None and not allow_model_selected:
        violations.append("concrete_model_selection_not_allowed")

    status = _normalize_policy_value(result.get("execution_status"))
    if status not in ALLOWED_EXECUTION_STATUSES:
        violations.append(f"unknown_execution_status:{status or 'missing'}")


def _append_timestamp_violations(result: Mapping[str, Any], violations: list[str]) -> None:
    started_at = _parse_timestamp(result.get("started_at"))
    completed_at = _parse_timestamp(result.get("completed_at"))
    if started_at is None:
        violations.append("malformed_timestamp:started_at")
    if completed_at is None:
        violations.append("malformed_timestamp:completed_at")
    if started_at and completed_at and completed_at < started_at:
        violations.append("invalid_result_timeline")


def _append_text_field_violations(result: Mapping[str, Any], violations: list[str]) -> None:
    summary = result.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        violations.append("missing_summary")
    elif len(summary) > _SUMMARY_LIMIT:
        violations.append("summary_too_long")

    for field in ("stdout_excerpt", "stderr_excerpt"):
        value = result.get(field)
        if not isinstance(value, str):
            violations.append(f"invalid_text_field:{field}")
        elif len(value) > _EXCERPT_LIMIT:
            violations.append(f"{field}_too_long")


def _append_findings_violations(result: Mapping[str, Any], violations: list[str]) -> None:
    findings = result.get("findings")
    if not isinstance(findings, list):
        violations.append("invalid_findings")
        return
    for index, finding in enumerate(findings):
        if not isinstance(finding, Mapping):
            violations.append(f"invalid_finding:{index}")
            continue
        severity = _normalize_policy_value(finding.get("severity"))
        if severity not in ALLOWED_FINDING_SEVERITIES:
            violations.append(f"invalid_finding_severity:{index}")
        if not str(finding.get("title") or "").strip():
            violations.append(f"missing_finding_title:{index}")
        if not str(finding.get("detail") or "").strip():
            violations.append(f"missing_finding_detail:{index}")
        evidence_refs = finding.get("evidence_refs", [])
        if not isinstance(evidence_refs, list):
            violations.append(f"invalid_finding_evidence_refs:{index}")


def _append_list_field_violations(result: Mapping[str, Any], violations: list[str]) -> None:
    for field in ("assumptions", "limitations", "requested_outputs", "produced_outputs"):
        if not isinstance(result.get(field), list):
            violations.append(f"invalid_list_field:{field}")
    if _normalize_policy_value(result.get("execution_status")) == "succeeded" and not _as_string_list(result.get("produced_outputs")):
        violations.append("missing_produced_outputs")


def _unsafe_artifact_path(path: str) -> bool:
    return (
        not path
        or path.startswith(("/", "~"))
        or "\\" in path
        or ".." in path.split("/")
        or len(path) > _MAX_ARTIFACT_PATH_LENGTH
        or not _SAFE_PATH_PATTERN.fullmatch(path)
    )


def _append_artifact_path_violations(
    result: Mapping[str, Any],
    approval_receipt: Mapping[str, Any] | None,
    violations: list[str],
) -> None:
    artifact_paths = result.get("artifact_paths")
    if not isinstance(artifact_paths, list):
        violations.append("invalid_artifact_paths")
        return
    if len(artifact_paths) > _MAX_ARTIFACT_PATHS:
        violations.append("too_many_artifact_paths")
    packet_id = str(result.get("packet_id") or "").strip()
    artifact_root = ""
    if isinstance(approval_receipt, Mapping):
        artifact_root = str(approval_receipt.get("artifact_root") or "").strip()
    for raw_path in artifact_paths[:_MAX_ARTIFACT_PATHS]:
        path = str(raw_path or "").strip()
        if _unsafe_artifact_path(path):
            violations.append("unsafe_artifact_path")
            continue
        if artifact_root and not (path == artifact_root or path.startswith(artifact_root + "/")):
            violations.append("artifact_path_outside_receipt_root")
        elif packet_id and packet_id not in path.split("/"):
            violations.append("artifact_path_not_packet_scoped")


def _append_safety_check_violations(result: Mapping[str, Any], violations: list[str]) -> None:
    safety_check = result.get("safety_check")
    if not isinstance(safety_check, Mapping):
        violations.append("missing_safety_check")
        return
    if safety_check.get("passed") is not True:
        violations.append("safety_check_not_passed")
    raw_violations = safety_check.get("violations")
    if not isinstance(raw_violations, list):
        violations.append("invalid_safety_check_violations")
    elif raw_violations:
        violations.append("safety_check_has_violations")
    if _parse_timestamp(safety_check.get("checked_at")) is None:
        violations.append("malformed_timestamp:safety_check.checked_at")


def _append_private_field_name_violations(value: object, violations: list[str]) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized_key = _normalize_policy_value(key)
            if normalized_key in _RAW_PRIVATE_FIELD_NAMES:
                violations.append(f"raw_private_field:{normalized_key}")
            _append_private_field_name_violations(item, violations)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _append_private_field_name_violations(item, violations)


def _append_protected_marker_violations(result: Mapping[str, Any], violations: list[str]) -> None:
    scan_text = _policy_text(result)
    lowered = scan_text.lower()
    for marker in sorted(PROTECTED_DATA_MARKERS, key=len, reverse=True):
        if marker in lowered:
            violations.append(f"protected_marker:{marker}")
    if _MONEY_AMOUNT_PATTERN.search(scan_text):
        violations.append("protected_pattern:money_amount")
    if _ABSOLUTE_PATH_PATTERN.search(scan_text):
        violations.append("absolute_private_path")
    if _TELEGRAM_BOT_TOKEN_PATTERN.search(scan_text):
        violations.append("telegram_bot_token")
    _append_private_field_name_violations(result, violations)


def _append_receipt_binding_violations(
    result: Mapping[str, Any],
    approval_receipt: Mapping[str, Any] | object | None,
    manifest: Mapping[str, Any] | object | None,
    provider_plan: Mapping[str, Any] | object | None,
    violations: list[str],
) -> Mapping[str, Any] | None:
    if approval_receipt is None:
        violations.append("missing_approval_receipt")
        return None
    if not isinstance(approval_receipt, Mapping):
        violations.append("approval_receipt_must_be_object")
        return None

    receipt_check = check_expert_execution_approval_receipt(
        approval_receipt,
        manifest=manifest,
        provider_plan=provider_plan,
    )
    if not receipt_check.passed:
        violations.append("approval_receipt_failed")
        violations.extend(receipt_check.violations)

    if str(result.get("approval_receipt_id") or "") != str(approval_receipt.get("approval_id") or ""):
        violations.append("approval_receipt_id_mismatch")
    if str(result.get("packet_id") or "") != str(approval_receipt.get("packet_id") or ""):
        violations.append("packet_id_mismatch")
    if str(result.get("manifest_hash") or "") != str(approval_receipt.get("manifest_hash") or ""):
        violations.append("manifest_hash_mismatch")
    if _normalize_policy_value(result.get("selected_provider")) != _normalize_policy_value(approval_receipt.get("selected_provider")):
        violations.append("provider_drift")
    if _normalize_policy_value(result.get("provider_role")) != _normalize_policy_value(approval_receipt.get("provider_role")):
        violations.append("provider_role_drift")
    return approval_receipt


def _append_manifest_binding_violations(
    result: Mapping[str, Any],
    manifest: Mapping[str, Any] | object | None,
    violations: list[str],
) -> None:
    if manifest is None:
        return
    if not isinstance(manifest, Mapping):
        violations.append("manifest_must_be_object")
        return
    if str(manifest.get("packet_id") or "") != str(result.get("packet_id") or ""):
        violations.append("manifest_packet_id_mismatch")
    manifest_hash = str(manifest.get("manifest_hash") or "").strip()
    if manifest_hash and manifest_hash != str(result.get("manifest_hash") or ""):
        violations.append("manifest_hash_mismatch")


def _append_provider_binding_violations(
    result: Mapping[str, Any],
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
    if str(provider_plan.get("packet_id") or "") != str(result.get("packet_id") or ""):
        violations.append("provider_plan_packet_id_mismatch")
    if _normalize_policy_value(provider_plan.get("selected_provider")) != _normalize_policy_value(result.get("selected_provider")):
        violations.append("provider_drift")
    if _normalize_policy_value(provider_plan.get("provider_role")) != _normalize_policy_value(result.get("provider_role")):
        violations.append("provider_role_drift")
    if str(provider_plan.get("model_selected") or "").strip():
        violations.append("provider_plan_model_selected")


def check_expert_result_artifact(
    result: Mapping[str, Any] | object,
    *,
    approval_receipt: Mapping[str, Any] | object | None = None,
    manifest: Mapping[str, Any] | object | None = None,
    provider_plan: Mapping[str, Any] | object | None = None,
    allow_model_selected: bool = False,
) -> ExpertResultArtifactCheck:
    """Validate an expert result artifact before any summary handoff."""
    if not isinstance(result, Mapping):
        return ExpertResultArtifactCheck(
            passed=False,
            violations=["result_must_be_object"],
            recommended_action="reject",
        )

    violations: list[str] = []
    bound_receipt = _append_receipt_binding_violations(
        result,
        approval_receipt,
        manifest,
        provider_plan,
        violations,
    )
    _append_required_field_violations(result, violations)
    _append_shape_violations(result, violations, allow_model_selected=allow_model_selected)
    _append_timestamp_violations(result, violations)
    _append_text_field_violations(result, violations)
    _append_findings_violations(result, violations)
    _append_list_field_violations(result, violations)
    _append_artifact_path_violations(result, bound_receipt, violations)
    _append_safety_check_violations(result, violations)
    _append_manifest_binding_violations(result, manifest, violations)
    _append_provider_binding_violations(result, provider_plan, violations)
    _append_protected_marker_violations(result, violations)

    unique_violations = _unique_violations(violations)
    return ExpertResultArtifactCheck(
        passed=not unique_violations,
        violations=unique_violations,
        recommended_action="pass" if not unique_violations else "reject",
    )