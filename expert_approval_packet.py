from __future__ import annotations

"""Pure no-execution approval packet shape for staged expert handoffs."""

import re
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from expert_escalation_packet import PROTECTED_DATA_MARKERS, check_expert_escalation_packet
from expert_staged_packet_flow import check_expert_staged_packet_artifact


EXPERT_APPROVAL_PACKET_SCHEMA_VERSION = 1
EXPERT_APPROVAL_PACKET_TYPE = "external_expert.approval_packet"

BOUNDARY_STATEMENT = (
    "This packet is for local human/Guardian review only; it is not live approval, "
    "not provider execution, and not authorization to send results."
)

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

REQUIRED_HUMAN_ACKNOWLEDGEMENTS = (
    "not_live_approval",
    "no_provider_call_authorized",
    "no_concrete_model_selection",
    "no_telegram_return",
    "no_gmail_actions",
    "no_services_or_schedulers",
    "no_hermes_runtime_expansion",
    "no_legal_matter_data",
    "review_only_before_separate_approval_slice",
)

_TITLE_LIMIT = 120
_SUMMARY_LIMIT = 480
_STAGED_SUMMARY_LIMIT = 360
_SAFE_REF_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,240}$")
_MONEY_AMOUNT_PATTERN = re.compile(
    r"\$\s*\d|\b\d+(?:\.\d+)?\s*(?:dollars?|usd|bucks?)\b",
    re.IGNORECASE,
)
_ABSOLUTE_PATH_PATTERN = re.compile(r"(?:^|\s)(?:/home/openclaw|/mnt/c|~[/\\])", re.IGNORECASE)
_TELEGRAM_BOT_TOKEN_PATTERN = re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b")
_NEXT_ALLOWED_ACTIONS = frozenset({
    "human_review_approval_packet",
    "repair_staged_artifact_and_rerun_checks",
})


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _bounded_text(value: object, *, limit: int, fallback: str) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        text = fallback
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _packet_id(packet: Mapping[str, Any] | object, staged_artifact: Mapping[str, Any] | object) -> str:
    if isinstance(packet, Mapping) and str(packet.get("packet_id") or "").strip():
        return str(packet.get("packet_id") or "").strip()
    if isinstance(staged_artifact, Mapping):
        return str(staged_artifact.get("packet_id") or "").strip()
    return ""


def _provider_role_metadata(staged_artifact: Mapping[str, Any] | object) -> dict[str, Any]:
    if not isinstance(staged_artifact, Mapping):
        return {
            "provider_role": "",
            "provider_allowed": False,
            "provider_candidate_is_metadata_only": False,
            "requires_operator_approval": True,
            "selected_lane": None,
            "task_type": "",
        }
    metadata = staged_artifact.get("provider_plan_metadata")
    if not isinstance(metadata, Mapping):
        metadata = {}
    return {
        "provider_role": str(metadata.get("provider_role") or ""),
        "provider_allowed": metadata.get("provider_allowed") is True,
        "provider_candidate_is_metadata_only": metadata.get("provider_candidate_is_metadata_only") is True,
        "requires_operator_approval": metadata.get("requires_operator_approval") is True,
        "selected_lane": metadata.get("selected_lane"),
        "task_type": str(metadata.get("task_type") or ""),
    }


def _check_summary(check_payload: object) -> dict[str, Any]:
    if not isinstance(check_payload, Mapping):
        return {"passed": False, "violations": ["missing_check_summary"], "recommended_action": "reject"}
    return {
        "passed": check_payload.get("passed") is True,
        "violations": _string_list(check_payload.get("violations")),
        "recommended_action": str(check_payload.get("recommended_action") or "reject"),
    }


def _staged_artifact_summary(staged_artifact: Mapping[str, Any] | object) -> dict[str, Any]:
    if not isinstance(staged_artifact, Mapping):
        return {
            "artifact_type": "",
            "artifact_schema_version": None,
            "passed": False,
            "summary": "Missing staged artifact.",
            "next_allowed_action": "repair_staged_artifact_and_rerun_checks",
            "synthetic_handoff_passed": False,
            "staged_packet_check": {"passed": False, "violations": ["missing_staged_artifact"], "recommended_action": "reject"},
        }
    return {
        "artifact_type": str(staged_artifact.get("artifact_type") or ""),
        "artifact_schema_version": staged_artifact.get("schema_version"),
        "passed": staged_artifact.get("passed") is True,
        "summary": _bounded_text(
            staged_artifact.get("summary"),
            limit=_STAGED_SUMMARY_LIMIT,
            fallback="Staged artifact did not provide a summary.",
        ),
        "next_allowed_action": str(staged_artifact.get("next_allowed_action") or ""),
        "synthetic_handoff_passed": staged_artifact.get("synthetic_handoff_passed") is True,
        "staged_packet_check": _check_summary(staged_artifact.get("staged_packet_check")),
    }


def _default_staged_ref(packet_id: str) -> str:
    return f"staged_artifact:{packet_id or 'missing-packet-id'}"


def _source_refs(staged_ref: str, staged_artifact: Mapping[str, Any] | object) -> list[str]:
    refs = [staged_ref]
    if isinstance(staged_artifact, Mapping):
        provider_hash = str(staged_artifact.get("provider_plan_hash") or "").strip()
        manifest_hash = str(staged_artifact.get("manifest_hash") or "").strip()
        if provider_hash:
            refs.append(f"provider_plan_hash:{provider_hash}")
        if manifest_hash:
            refs.append(f"manifest_hash:{manifest_hash}")
    return refs


def build_expert_approval_packet(
    packet: Mapping[str, Any] | object,
    staged_artifact: Mapping[str, Any] | object,
    *,
    created_at: str | None = None,
    staged_artifact_ref: str | None = None,
    review_window_recommendation: str = "Review within 24 hours of created_at; rebuild if any source artifact changes.",
) -> dict[str, Any]:
    """Build a deterministic local review packet without authorizing execution."""
    packet_created_at = created_at or _utc_now()
    packet_id = _packet_id(packet, staged_artifact)
    staged_ref = str(staged_artifact_ref or _default_staged_ref(packet_id)).strip()
    staged_passed = staged_artifact.get("passed") is True if isinstance(staged_artifact, Mapping) else False
    task_title = _bounded_text(
        packet.get("operator_request_summary") if isinstance(packet, Mapping) else "",
        limit=_TITLE_LIMIT,
        fallback=f"Expert review packet {packet_id or 'missing-packet-id'}",
    )
    task_summary = _bounded_text(
        packet.get("prompt") if isinstance(packet, Mapping) else "",
        limit=_SUMMARY_LIMIT,
        fallback="No sanitized source summary was available.",
    )
    approval_packet: dict[str, Any] = {
        "packet_type": EXPERT_APPROVAL_PACKET_TYPE,
        "schema_version": EXPERT_APPROVAL_PACKET_SCHEMA_VERSION,
        "created_at": packet_created_at,
        "packet_id": packet_id,
        "task_title": task_title,
        "task_summary": task_summary,
        "provider_role_metadata": _provider_role_metadata(staged_artifact),
        "provider_plan_hash": str(staged_artifact.get("provider_plan_hash") or "") if isinstance(staged_artifact, Mapping) else "",
        "manifest_hash": str(staged_artifact.get("manifest_hash") or "") if isinstance(staged_artifact, Mapping) else "",
        "staged_artifact_ref": staged_ref,
        "staged_artifact_summary": _staged_artifact_summary(staged_artifact),
        "risk_sensitivity_class": str(packet.get("data_classification") or "unknown_review_required") if isinstance(packet, Mapping) else "unknown_review_required",
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "required_human_acknowledgements": list(REQUIRED_HUMAN_ACKNOWLEDGEMENTS),
        "execution_allowed": False,
        "provider_call_allowed": False,
        "telegram_return_allowed": False,
        "approval_request_allowed": False,
        "requires_human_review": True,
        "next_allowed_action": "human_review_approval_packet" if staged_passed else "repair_staged_artifact_and_rerun_checks",
        "review_window_recommendation": review_window_recommendation,
        "audit_refs": {
            "staged_packet_check": _check_summary(staged_artifact.get("staged_packet_check")) if isinstance(staged_artifact, Mapping) else {"passed": False, "violations": ["missing_staged_artifact"], "recommended_action": "reject"},
            "synthetic_handoff_passed": staged_artifact.get("synthetic_handoff_passed") is True if isinstance(staged_artifact, Mapping) else False,
            "source_packet_check_required": True,
        },
        "source_artifact_refs": _source_refs(staged_ref, staged_artifact),
        "boundary_statement": BOUNDARY_STATEMENT,
    }
    approval_check = check_expert_approval_packet(approval_packet, packet=packet, staged_artifact=staged_artifact)
    approval_packet["approval_packet_check"] = approval_check
    approval_packet["passed"] = approval_check["passed"]
    approval_packet["violations"] = approval_check["violations"]
    approval_packet["recommended_action"] = approval_check["recommended_action"]
    return approval_packet


def _append_required_field_violations(approval_packet: Mapping[str, Any], violations: list[str]) -> None:
    required_fields = (
        "packet_type",
        "schema_version",
        "created_at",
        "packet_id",
        "task_title",
        "task_summary",
        "provider_role_metadata",
        "provider_plan_hash",
        "manifest_hash",
        "staged_artifact_ref",
        "staged_artifact_summary",
        "risk_sensitivity_class",
        "forbidden_actions",
        "required_human_acknowledgements",
        "execution_allowed",
        "provider_call_allowed",
        "telegram_return_allowed",
        "approval_request_allowed",
        "next_allowed_action",
        "review_window_recommendation",
        "audit_refs",
        "source_artifact_refs",
        "boundary_statement",
    )
    for field in required_fields:
        if field not in approval_packet:
            violations.append(f"missing_required_field:{field}")


def _append_shape_violations(approval_packet: Mapping[str, Any], violations: list[str]) -> None:
    if approval_packet.get("packet_type") != EXPERT_APPROVAL_PACKET_TYPE:
        violations.append("invalid_packet_type")
    if approval_packet.get("schema_version") != EXPERT_APPROVAL_PACKET_SCHEMA_VERSION:
        violations.append("invalid_schema_version")
    if not str(approval_packet.get("created_at") or "").strip():
        violations.append("missing_created_at")
    if not str(approval_packet.get("packet_id") or "").strip():
        violations.append("missing_packet_id")
    title = approval_packet.get("task_title")
    if not isinstance(title, str) or not title.strip():
        violations.append("missing_task_title")
    elif len(title) > _TITLE_LIMIT + 3:
        violations.append("task_title_too_long")
    summary = approval_packet.get("task_summary")
    if not isinstance(summary, str) or not summary.strip():
        violations.append("missing_task_summary")
    elif len(summary) > _SUMMARY_LIMIT + 3:
        violations.append("task_summary_too_long")
    if approval_packet.get("next_allowed_action") not in _NEXT_ALLOWED_ACTIONS:
        violations.append("invalid_next_allowed_action")
    if approval_packet.get("boundary_statement") != BOUNDARY_STATEMENT:
        violations.append("invalid_boundary_statement")
    if not str(approval_packet.get("review_window_recommendation") or "").strip():
        violations.append("missing_review_window_recommendation")


def _append_no_execution_violations(approval_packet: Mapping[str, Any], violations: list[str]) -> None:
    if approval_packet.get("execution_allowed") is not False:
        violations.append("execution_allowed")
    if approval_packet.get("provider_call_allowed") is not False:
        violations.append("provider_call_allowed")
    if approval_packet.get("telegram_return_allowed") is not False:
        violations.append("telegram_return_allowed")
    if approval_packet.get("approval_request_allowed") is not False:
        violations.append("approval_request_allowed")
    if approval_packet.get("requires_human_review") is not True:
        violations.append("human_review_not_required")


def _append_action_violations(approval_packet: Mapping[str, Any], violations: list[str]) -> None:
    forbidden_actions = _string_list(approval_packet.get("forbidden_actions"))
    for action in FORBIDDEN_ACTIONS:
        if action not in forbidden_actions:
            violations.append(f"missing_forbidden_action:{action}")
    acknowledgements = _string_list(approval_packet.get("required_human_acknowledgements"))
    for acknowledgement in REQUIRED_HUMAN_ACKNOWLEDGEMENTS:
        if acknowledgement not in acknowledgements:
            violations.append(f"missing_required_acknowledgement:{acknowledgement}")


def _append_metadata_violations(approval_packet: Mapping[str, Any], staged_artifact: Mapping[str, Any] | object | None, violations: list[str]) -> None:
    role_metadata = approval_packet.get("provider_role_metadata")
    if not isinstance(role_metadata, Mapping):
        violations.append("provider_role_metadata_must_be_object")
    else:
        if str(role_metadata.get("provider_role") or "") != "external_advisory_review":
            violations.append("invalid_provider_role")
        if role_metadata.get("provider_candidate_is_metadata_only") is not True:
            violations.append("provider_candidate_not_metadata_only")
        if role_metadata.get("requires_operator_approval") is not True:
            violations.append("provider_operator_approval_not_required")
        for field in role_metadata:
            if "model" in str(field).lower():
                violations.append("provider_role_metadata_model_field")

    staged_summary = approval_packet.get("staged_artifact_summary")
    if not isinstance(staged_summary, Mapping):
        violations.append("staged_artifact_summary_must_be_object")
    else:
        summary = staged_summary.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            violations.append("missing_staged_artifact_summary")
        elif len(summary) > _STAGED_SUMMARY_LIMIT + 3:
            violations.append("staged_artifact_summary_too_long")
        if staged_summary.get("passed") is not True:
            violations.append("staged_artifact_not_passed")
        if staged_summary.get("staged_packet_check", {}).get("passed") is not True:
            violations.append("staged_packet_check_not_passed")

    if staged_artifact is not None and isinstance(staged_artifact, Mapping):
        provider_metadata = staged_artifact.get("provider_plan_metadata")
        if isinstance(provider_metadata, Mapping) and provider_metadata.get("model_selected") is not None:
            violations.append("staged_provider_model_selected")
        receipt_validation = staged_artifact.get("synthetic_receipt_validation")
        if isinstance(receipt_validation, Mapping):
            if receipt_validation.get("live_guardian_request_made") is not False:
                violations.append("live_guardian_request_made")
            if receipt_validation.get("live_execution_allowed") is not False:
                violations.append("live_execution_allowed")


def _unsafe_ref(value: str) -> bool:
    return (
        not value
        or value.startswith(("/", "~"))
        or "\\" in value
        or ".." in value.split("/")
        or not _SAFE_REF_PATTERN.fullmatch(value)
    )


def _append_ref_violations(approval_packet: Mapping[str, Any], violations: list[str]) -> None:
    staged_ref = str(approval_packet.get("staged_artifact_ref") or "").strip()
    if _unsafe_ref(staged_ref):
        violations.append("unsafe_staged_artifact_ref")
    refs = _string_list(approval_packet.get("source_artifact_refs"))
    if staged_ref and staged_ref not in refs:
        violations.append("staged_ref_missing_from_source_refs")
    for ref in refs:
        if _unsafe_ref(ref):
            violations.append("unsafe_source_artifact_ref")


def _append_packet_binding_violations(
    approval_packet: Mapping[str, Any],
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
        violations.append("source_packet_check_failed")
        violations.extend(packet_check.violations)
    if str(packet.get("packet_id") or "") != str(approval_packet.get("packet_id") or ""):
        violations.append("packet_id_mismatch")


def _append_staged_artifact_binding_violations(
    approval_packet: Mapping[str, Any],
    packet: Mapping[str, Any] | object | None,
    staged_artifact: Mapping[str, Any] | object | None,
    violations: list[str],
) -> None:
    if staged_artifact is None:
        violations.append("missing_staged_artifact")
        return
    if not isinstance(staged_artifact, Mapping):
        violations.append("staged_artifact_must_be_object")
        return

    staged_check = check_expert_staged_packet_artifact(staged_artifact, packet=packet)
    if staged_check.get("passed") is not True:
        violations.append("staged_artifact_check_failed")
        violations.extend(_string_list(staged_check.get("violations")))

    if str(staged_artifact.get("packet_id") or "") != str(approval_packet.get("packet_id") or ""):
        violations.append("staged_packet_id_mismatch")
    if str(staged_artifact.get("provider_plan_hash") or "") != str(approval_packet.get("provider_plan_hash") or ""):
        violations.append("provider_plan_hash_mismatch")
    if str(staged_artifact.get("manifest_hash") or "") != str(approval_packet.get("manifest_hash") or ""):
        violations.append("manifest_hash_mismatch")

    expected_metadata = _provider_role_metadata(staged_artifact)
    role_metadata = approval_packet.get("provider_role_metadata")
    if isinstance(role_metadata, Mapping):
        for field in ("provider_role", "provider_allowed", "provider_candidate_is_metadata_only", "requires_operator_approval", "selected_lane", "task_type"):
            if role_metadata.get(field) != expected_metadata.get(field):
                violations.append("provider_role_metadata_mismatch")
                break


def _append_protected_text_violations(approval_packet: Mapping[str, Any], violations: list[str]) -> None:
    scan_parts = [
        str(approval_packet.get("task_title") or ""),
        str(approval_packet.get("task_summary") or ""),
        str(approval_packet.get("risk_sensitivity_class") or ""),
    ]
    staged_summary = approval_packet.get("staged_artifact_summary")
    if isinstance(staged_summary, Mapping):
        scan_parts.append(str(staged_summary.get("summary") or ""))
    scan_text = " ".join(scan_parts)
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


def check_expert_approval_packet(
    approval_packet: Mapping[str, Any] | object,
    *,
    packet: Mapping[str, Any] | object | None = None,
    staged_artifact: Mapping[str, Any] | object | None = None,
) -> dict[str, Any]:
    """Validate a local approval packet without sending approval or executing providers."""
    if not isinstance(approval_packet, Mapping):
        return {
            "passed": False,
            "violations": ["approval_packet_must_be_object"],
            "recommended_action": "reject",
        }

    violations: list[str] = []
    _append_required_field_violations(approval_packet, violations)
    _append_shape_violations(approval_packet, violations)
    _append_no_execution_violations(approval_packet, violations)
    _append_action_violations(approval_packet, violations)
    _append_metadata_violations(approval_packet, staged_artifact, violations)
    _append_ref_violations(approval_packet, violations)
    _append_packet_binding_violations(approval_packet, packet, violations)
    _append_staged_artifact_binding_violations(approval_packet, packet, staged_artifact, violations)
    _append_protected_text_violations(approval_packet, violations)

    unique_violations = _unique_violations(violations)
    return {
        "passed": not unique_violations,
        "violations": unique_violations,
        "recommended_action": "pass" if not unique_violations else "reject",
    }