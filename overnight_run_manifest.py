from __future__ import annotations

"""Pure no-execution manifest builder for one overnight OpenClaw cycle."""

from datetime import datetime, timezone
from typing import Any, Mapping


OVERNIGHT_RUN_MANIFEST_SCHEMA_VERSION = 1
OVERNIGHT_RUN_MANIFEST_TYPE = "openclaw.overnight_run_manifest"

_BAD_SECTION_STATUSES = {"", "missing", "unavailable", "failed", "failure", "error", "stale"}
_VALID_SEVERITIES = {"low", "medium", "high", "critical"}
_EXECUTABLE_FIELD_NAMES = {
    "command",
    "commands",
    "exec",
    "execute",
    "invoke",
    "shell",
    "shell_command",
    "provider_call",
    "service_action",
    "telegram_send",
    "gmail_action",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_token(value: object) -> str:
    return _clean_text(value).lower().replace("-", "_").replace(" ", "_")


def _slug(value: object) -> str:
    text = _clean_text(value).lower()
    chars: list[str] = []
    previous_dash = False
    for char in text:
        if char.isalnum():
            chars.append(char)
            previous_dash = False
        elif not previous_dash:
            chars.append("-")
            previous_dash = True
    return "".join(chars).strip("-") or "issue"


def _cycle_date_from(created_at: str) -> str:
    if len(created_at) >= 10 and _is_valid_date(created_at[:10]):
        return created_at[:10]
    return datetime.now(timezone.utc).date().isoformat()


def _as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: object) -> list[object]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _as_string_list(value: object) -> list[str]:
    return [_clean_text(item) for item in _as_list(value) if _clean_text(item)]


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _reference(section: Mapping[str, Any]) -> str:
    for key in ("artifact_ref", "reference", "source_artifact", "artifact", "path"):
        ref = _clean_text(section.get(key))
        if ref:
            return ref
    return ""


def _status(section: Mapping[str, Any], default: str = "unknown") -> str:
    return _normalize_token(section.get("status") or default)


def _section_available(section: Mapping[str, Any], *, require_ref: bool = True) -> bool:
    if require_ref and not _reference(section):
        return False
    explicit = section.get("available")
    if explicit is False:
        return False
    if explicit is True:
        return _status(section) not in _BAD_SECTION_STATUSES
    return _status(section) not in _BAD_SECTION_STATUSES


def _manifest_issue(
    *,
    cycle_date: str,
    code: str,
    severity: str,
    title: str,
    source_artifact: str,
    recommended_next_action: str,
    blocking_readiness: bool,
) -> dict[str, Any]:
    normalized_severity = _normalize_token(severity)
    if normalized_severity not in _VALID_SEVERITIES:
        normalized_severity = "medium"
    return {
        "id": f"overnight-{cycle_date.replace('-', '')}-{_slug(code)}",
        "severity": normalized_severity,
        "title": _clean_text(title),
        "source_artifact": _clean_text(source_artifact) or "input_manifest",
        "recommended_next_action": _clean_text(recommended_next_action),
        "blocking_readiness": bool(blocking_readiness),
    }


def _normalize_issue(raw: object, *, cycle_date: str, fallback_code: str, blocking: bool) -> dict[str, Any]:
    item = _as_mapping(raw)
    code = _clean_text(item.get("id") or item.get("code") or fallback_code)
    source_artifact = _clean_text(item.get("source_artifact") or item.get("artifact_ref") or item.get("reference"))
    return _manifest_issue(
        cycle_date=cycle_date,
        code=code,
        severity=_clean_text(item.get("severity") or "medium"),
        title=_clean_text(item.get("title") or code),
        source_artifact=source_artifact or "input_manifest",
        recommended_next_action=_clean_text(item.get("recommended_next_action") or "Review this overnight manifest issue."),
        blocking_readiness=bool(item.get("blocking_readiness", blocking)),
    )


def _normalize_eod_review(raw: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "artifact_ref": _reference(raw),
        "status": _status(raw),
        "available": _section_available(raw),
        "started_at": _clean_text(raw.get("started_at")),
        "finished_at": _clean_text(raw.get("finished_at")),
        "proposal_count": _as_int(raw.get("proposal_count")),
    }


def _normalize_eod_harness(raw: Mapping[str, Any]) -> dict[str, Any]:
    passed = _as_int(raw.get("passed"))
    failed = _as_int(raw.get("failed"))
    total_cases = _as_int(raw.get("total_cases"))
    status = _status(raw, default="not_provided")
    if failed is not None and failed > 0:
        status = "failed"
    elif status == "unknown" and passed is not None:
        status = "passed" if (failed or 0) == 0 else "failed"
    return {
        "artifact_ref": _reference(raw),
        "status": status,
        "harness_name": _clean_text(raw.get("harness_name")),
        "flow": _clean_text(raw.get("flow")),
        "passed": passed,
        "failed": failed,
        "total_cases": total_cases,
    }


def _normalize_proposal_promotion(raw: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "artifact_ref": _reference(raw),
        "status": _status(raw, default="unknown"),
        "proposal_ids": _as_string_list(raw.get("proposal_ids")),
        "promoted_task_ids": _as_string_list(raw.get("promoted_task_ids") or raw.get("promoted_tasks")),
        "metadata_only": True,
        "action_triggered": False,
    }


def _normalize_morning_synthesis(raw: Mapping[str, Any]) -> dict[str, Any]:
    freshness = _clean_text(raw.get("freshness"))
    stale = bool(raw.get("stale")) or "stale" in freshness.lower() or _status(raw) == "stale"
    available = _section_available(raw)
    return {
        "artifact_ref": _reference(raw),
        "status": "stale" if stale else _status(raw),
        "available": available and not stale,
        "freshness": freshness,
        "generated_at": _clean_text(raw.get("generated_at")),
    }


def _normalize_guardian_status(raw: Mapping[str, Any]) -> dict[str, Any]:
    approval_pending = bool(raw.get("approval_pending")) or _status(raw) == "pending"
    return {
        "artifact_ref": _reference(raw),
        "status": _status(raw, default="unknown"),
        "approval_pending": approval_pending,
        "approval_id": _clean_text(raw.get("approval_id") or raw.get("id")),
        "metadata_only": True,
        "action_triggered": False,
    }


def _is_valid_timestamp(value: object) -> bool:
    text = _clean_text(value)
    if not text:
        return False
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _is_valid_date(value: object) -> bool:
    try:
        datetime.strptime(_clean_text(value), "%Y-%m-%d")
        return True
    except ValueError:
        return False


def build_overnight_run_manifest(inputs: Mapping[str, Any] | object, *, created_at: str | None = None) -> dict[str, Any]:
    """Build a deterministic no-execution overnight run manifest from explicit dictionaries only."""
    manifest_created_at = created_at or _utc_now()
    source = _as_mapping(inputs)
    cycle_date = _clean_text(source.get("cycle_date")) or _cycle_date_from(manifest_created_at)
    if not _is_valid_date(cycle_date):
        cycle_date = _cycle_date_from(manifest_created_at)

    eod_review = _normalize_eod_review(_as_mapping(source.get("eod_review")))
    eod_harness = _normalize_eod_harness(_as_mapping(source.get("eod_harness")))
    proposal_promotion = _normalize_proposal_promotion(_as_mapping(source.get("proposal_promotion")))
    morning_synthesis = _normalize_morning_synthesis(_as_mapping(source.get("morning_synthesis")))
    guardian_status = _normalize_guardian_status(_as_mapping(source.get("guardian_status")))

    issues: list[dict[str, Any]] = []

    if not isinstance(inputs, Mapping):
        issues.append(_manifest_issue(
            cycle_date=cycle_date,
            code="inputs_not_mapping",
            severity="critical",
            title="Overnight manifest inputs must be an explicit dictionary.",
            source_artifact="inputs",
            recommended_next_action="Pass explicit synthetic dictionaries into the manifest builder.",
            blocking_readiness=True,
        ))

    if not eod_review["available"]:
        issues.append(_manifest_issue(
            cycle_date=cycle_date,
            code="eod_review_missing",
            severity="high",
            title="Chief EOD review artifact reference is missing or unavailable.",
            source_artifact=eod_review["artifact_ref"] or "eod_review",
            recommended_next_action="Provide a completed Chief EOD review artifact reference before morning synthesis readiness.",
            blocking_readiness=True,
        ))

    if eod_harness["status"] == "failed":
        issues.append(_manifest_issue(
            cycle_date=cycle_date,
            code="eod_harness_failed",
            severity="high",
            title="EOD harness evidence reported one or more failed checks.",
            source_artifact=eod_harness["artifact_ref"] or "eod_harness",
            recommended_next_action="Inspect the referenced EOD harness manifest and resolve failed checks before relying on the overnight cycle.",
            blocking_readiness=True,
        ))

    if not morning_synthesis["available"]:
        code = "morning_synthesis_stale" if morning_synthesis["artifact_ref"] else "morning_synthesis_missing"
        title = "Chief Morning Synthesis is stale." if morning_synthesis["artifact_ref"] else "Chief Morning Synthesis reference is missing."
        issues.append(_manifest_issue(
            cycle_date=cycle_date,
            code=code,
            severity="high",
            title=title,
            source_artifact=morning_synthesis["artifact_ref"] or "morning_synthesis",
            recommended_next_action="Refresh the bounded morning artifacts and Chief Morning Synthesis before Cassandra morning reporting.",
            blocking_readiness=True,
        ))

    for index, raw_issue in enumerate(_as_list(source.get("issues")), start=1):
        issues.append(_normalize_issue(raw_issue, cycle_date=cycle_date, fallback_code=f"input_issue_{index}", blocking=False))

    for index, raw_blocker in enumerate(_as_list(source.get("blockers")), start=1):
        issues.append(_normalize_issue(raw_blocker, cycle_date=cycle_date, fallback_code=f"input_blocker_{index}", blocking=True))

    blockers = [issue for issue in issues if issue["blocking_readiness"]]
    ready_for_morning_synthesis = not blockers

    return {
        "manifest_type": OVERNIGHT_RUN_MANIFEST_TYPE,
        "schema_version": OVERNIGHT_RUN_MANIFEST_SCHEMA_VERSION,
        "created_at": manifest_created_at,
        "cycle_date": cycle_date,
        "execution_allowed": False,
        "service_wiring_allowed": False,
        "eod_review": eod_review,
        "eod_harness": eod_harness,
        "proposal_promotion": proposal_promotion,
        "morning_synthesis": morning_synthesis,
        "guardian_status": guardian_status,
        "blockers": blockers,
        "issues": issues,
        "ready_for_morning_synthesis": ready_for_morning_synthesis,
        "ready_for_service_timer_wiring": False,
    }


def _check_issue_shape(kind: str, index: int, issue: object) -> list[str]:
    if not isinstance(issue, Mapping):
        return [f"{kind}_{index}_must_be_object"]
    violations: list[str] = []
    for field in ("id", "severity", "title", "source_artifact", "recommended_next_action"):
        if not _clean_text(issue.get(field)):
            violations.append(f"{kind}_{index}_missing_{field}")
    if _normalize_token(issue.get("severity")) not in _VALID_SEVERITIES:
        violations.append(f"{kind}_{index}_invalid_severity")
    if not isinstance(issue.get("blocking_readiness"), bool):
        violations.append(f"{kind}_{index}_blocking_readiness_must_be_bool")
    return violations


def check_overnight_run_manifest(manifest: Mapping[str, Any] | object) -> dict[str, Any]:
    """Validate the no-execution overnight run manifest contract."""
    if not isinstance(manifest, Mapping):
        return {"passed": False, "violations": ["manifest_must_be_object"]}

    violations: list[str] = []
    required_fields = (
        "manifest_type",
        "schema_version",
        "created_at",
        "cycle_date",
        "execution_allowed",
        "service_wiring_allowed",
        "eod_review",
        "eod_harness",
        "proposal_promotion",
        "morning_synthesis",
        "guardian_status",
        "blockers",
        "issues",
        "ready_for_morning_synthesis",
        "ready_for_service_timer_wiring",
    )
    for field in required_fields:
        if field not in manifest:
            violations.append(f"missing_required_field:{field}")

    if manifest.get("manifest_type") != OVERNIGHT_RUN_MANIFEST_TYPE:
        violations.append("invalid_manifest_type")
    if manifest.get("schema_version") != OVERNIGHT_RUN_MANIFEST_SCHEMA_VERSION:
        violations.append("invalid_schema_version")
    if not _is_valid_timestamp(manifest.get("created_at")):
        violations.append("invalid_created_at")
    if not _is_valid_date(manifest.get("cycle_date")):
        violations.append("invalid_cycle_date")
    if manifest.get("execution_allowed") is not False:
        violations.append("execution_allowed_must_be_false")
    if manifest.get("service_wiring_allowed") is not False:
        violations.append("service_wiring_allowed_must_be_false")
    if manifest.get("ready_for_service_timer_wiring") is not False:
        violations.append("ready_for_service_timer_wiring_must_be_false")
    if not isinstance(manifest.get("ready_for_morning_synthesis"), bool):
        violations.append("ready_for_morning_synthesis_must_be_bool")

    for field in ("eod_review", "eod_harness", "proposal_promotion", "morning_synthesis", "guardian_status"):
        if field in manifest and not isinstance(manifest.get(field), Mapping):
            violations.append(f"{field}_must_be_object")

    for field in _EXECUTABLE_FIELD_NAMES:
        if field in manifest:
            violations.append(f"forbidden_executable_field:{field}")

    issues = manifest.get("issues")
    blockers = manifest.get("blockers")
    if not isinstance(issues, list):
        violations.append("issues_must_be_list")
    else:
        for index, issue in enumerate(issues):
            violations.extend(_check_issue_shape("issue", index, issue))
    if not isinstance(blockers, list):
        violations.append("blockers_must_be_list")
    else:
        for index, blocker in enumerate(blockers):
            violations.extend(_check_issue_shape("blocker", index, blocker))

    if isinstance(issues, list) and isinstance(blockers, list):
        issue_ids = {_clean_text(issue.get("id")) for issue in issues if isinstance(issue, Mapping)}
        for blocker in blockers:
            if isinstance(blocker, Mapping) and _clean_text(blocker.get("id")) not in issue_ids:
                violations.append(f"blocker_not_present_in_issues:{_clean_text(blocker.get('id'))}")

    return {"passed": not violations, "violations": violations}