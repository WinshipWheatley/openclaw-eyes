from __future__ import annotations

"""Pure dashboard evidence normalization for explicit JSON artifact paths.

This module does not discover files. Callers must pass exact artifact paths.
It reads only the provided stable JSON-like artifacts and returns bounded
records suitable for a future local dashboard/report surface.
"""

import json
import re
from pathlib import Path
from typing import Any, Iterable


DASHBOARD_RECORD_SCHEMA_VERSION = 1

_HARNESS_REQUIRED_KEYS = frozenset({
    "harness_name",
    "task_name",
    "generated_at",
    "checks",
    "passed",
    "failed",
    "total_cases",
})
_VALID_LOOP_STATES = frozenset({"idle", "pc_turn", "mac_turn", "approved", "blocked", "parked"})
_FORBIDDEN_PATH_MARKERS = (
    ".chief.env",
    ".env",
    ".google-secrets",
    "credentials",
    "gmail",
    "hermes",
    "legalprivate",
    "openclawlegalprivate",
    "secret",
    "token",
)
_RAW_PRIVATE_SUFFIXES = frozenset({".csv", ".db", ".jsonl", ".log", ".out", ".sqlite", ".sqlite3"})
_GLOB_MARKERS = frozenset({"*", "?", "[", "]"})


class DashboardEvidencePathError(ValueError):
    """Raised when an explicit source path is unsafe for dashboard evidence."""


def normalize_dashboard_artifacts(artifact_paths: Iterable[str | Path]) -> list[dict[str, Any]]:
    """Return normalized dashboard records for explicit artifact paths only."""
    return [normalize_dashboard_artifact(path) for path in artifact_paths]


def load_dashboard_evidence(artifact_paths: Iterable[str | Path]) -> list[dict[str, Any]]:
    """Compatibility alias for callers that prefer a load-style entry point."""
    return normalize_dashboard_artifacts(artifact_paths)


def normalize_dashboard_artifact(artifact_path: str | Path) -> dict[str, Any]:
    """Normalize one explicit artifact path into a dashboard evidence record."""
    path = _validated_explicit_path(artifact_path)
    source_path = str(path)

    if not path.exists():
        return _base_record(
            record_type="artifact_error",
            artifact_type="missing",
            artifact_id=f"missing:{path.name or source_path}",
            generated_at=None,
            source_path=source_path,
            status="missing",
            severity="warning",
            title="Missing dashboard artifact",
            summary="Artifact path does not exist.",
            allowed_surfaces=[],
        )

    if path.suffix.lower() == ".md":
        return _unsupported_record(
            path,
            "Markdown reports are not canonical dashboard evidence for this adapter.",
        )
    if path.suffix.lower() != ".json":
        return _unsupported_record(
            path,
            "Only stable JSON-like artifacts are supported by this adapter.",
        )

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _base_record(
            record_type="artifact_error",
            artifact_type="json_parse_error",
            artifact_id=f"parse-error:{path.name}",
            generated_at=None,
            source_path=source_path,
            status="error",
            severity="error",
            title="Unusable JSON artifact",
            summary=f"Artifact JSON could not be parsed: {exc.msg}.",
            allowed_surfaces=[],
        )

    if not isinstance(payload, dict):
        return _unsupported_record(path, "JSON artifact must contain an object to be dashboard evidence.")

    if _is_harness_manifest(payload):
        return _normalize_harness_manifest(path, payload)
    if _is_expert_job_manifest(payload):
        return _normalize_expert_job_manifest(path, payload)
    if _is_cassandra_briefing(payload):
        return _normalize_cassandra_briefing(path, payload)
    if _is_eod_review(payload):
        return _normalize_eod_review(path, payload)
    if _is_loop_status(payload):
        return _normalize_loop_status(path, payload)

    return _unsupported_record(path, "JSON object does not match a supported stable dashboard artifact schema.")


def _validated_explicit_path(value: str | Path) -> Path:
    raw = str(value or "").strip()
    if not raw:
        raise DashboardEvidencePathError("missing_artifact_path")
    if "\x00" in raw:
        raise DashboardEvidencePathError("unsafe_artifact_path:nul_byte")
    if any(marker in raw for marker in _GLOB_MARKERS):
        raise DashboardEvidencePathError("unsafe_artifact_path:glob_pattern")

    path = Path(raw)
    normalized_parts = tuple(part.lower() for part in path.parts)
    if any(part == ".." for part in normalized_parts):
        raise DashboardEvidencePathError("unsafe_artifact_path:traversal")

    lowered = raw.lower().replace("\\", "/")
    if any(marker in lowered for marker in _FORBIDDEN_PATH_MARKERS):
        raise DashboardEvidencePathError("forbidden_artifact_path")
    if path.suffix.lower() in _RAW_PRIVATE_SUFFIXES:
        raise DashboardEvidencePathError("forbidden_raw_private_artifact")
    return path


def _is_harness_manifest(payload: dict[str, Any]) -> bool:
    return _HARNESS_REQUIRED_KEYS.issubset(payload) and isinstance(payload.get("checks"), list)


def _is_expert_job_manifest(payload: dict[str, Any]) -> bool:
    return payload.get("manifest_type") == "external_expert.job_manifest"


def _is_cassandra_briefing(payload: dict[str, Any]) -> bool:
    return all(key in payload for key in ("slot", "date", "text", "generated_at", "delivered"))


def _is_eod_review(payload: dict[str, Any]) -> bool:
    return all(key in payload for key in ("started_at", "finished_at", "summary", "findings", "proposal_ids"))


def _is_loop_status(payload: dict[str, Any]) -> bool:
    return str(payload.get("status", "")).strip().lower() in _VALID_LOOP_STATES


def _normalize_harness_manifest(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    failed = _int_value(payload.get("failed"))
    passed = _int_value(payload.get("passed"))
    total = _int_value(payload.get("total_cases"))
    status = "passed" if failed == 0 and total > 0 else "failed" if failed > 0 else "unknown"
    severity = "ok" if status == "passed" else "error" if status == "failed" else "warning"
    harness_name = _text(payload.get("harness_name"), "unknown_harness")
    task_name = _text(payload.get("task_name"), "unknown_task")
    checks = _normalize_checks(payload.get("checks"))
    refs = _source_ref(path)
    refs.extend(_safe_path_refs("fixture", [payload.get("fixture_path")]))
    refs.extend(_safe_path_refs("recorded_source", [payload.get("recorded_source")]))

    return _base_record(
        record_type="dashboard_card",
        artifact_type="harness_manifest",
        artifact_id=f"{harness_name}:{task_name}:{_text(payload.get('generated_at'), 'unknown')}",
        generated_at=_optional_text(payload.get("generated_at")),
        source_path=str(path),
        status=status,
        severity=severity,
        title=f"{harness_name}: {task_name}",
        summary=f"{passed}/{total} checks passed; {failed} failed.",
        checks=checks,
        drilldown_refs=refs,
    )


def _normalize_expert_job_manifest(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    checker_passed = payload.get("checker_passed") is True
    lane_policy_passed = payload.get("lane_policy_passed") is True
    execution_blocked = payload.get("execution_allowed") is False
    refusal_reason = _optional_text(payload.get("refusal_reason"))
    status = "refused" if refusal_reason else "approval_required" if payload.get("approval_required") else "metadata_only"
    severity = "warning" if refusal_reason else "info"
    packet_id = _text(payload.get("packet_id"), "unknown_packet")
    selected_lane = _text(payload.get("selected_lane"), "none")
    checks = [
        _check("packet_checker_passed", checker_passed, "expert packet checker result"),
        _check("lane_policy_passed", lane_policy_passed, "expert lane policy result"),
        _check("execution_not_allowed", execution_blocked, "manifest is metadata-only and no-execution"),
    ]
    refs = _source_ref(path)
    refs.extend(_safe_path_refs("input_path", payload.get("input_paths")))

    return _base_record(
        record_type="dashboard_card",
        artifact_type="expert_job_manifest",
        artifact_id=packet_id,
        generated_at=_optional_text(payload.get("manifest_created_at")),
        source_path=str(path),
        status=status,
        severity=severity,
        title=f"Expert job manifest: {packet_id}",
        summary=_bounded_text(refusal_reason or f"Selected lane: {selected_lane}; execution allowed: false."),
        checks=checks,
        drilldown_refs=refs,
        privacy_classification="sanitized_or_public_metadata_only",
        allowed_surfaces=["local_dashboard", "operator_report"],
    )


def _normalize_cassandra_briefing(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    slot = _text(payload.get("slot"), "briefing")
    date = _text(payload.get("date"), "unknown-date")
    delivered = payload.get("delivered") is True
    pending_reason = _optional_text(payload.get("pending_reason"))
    status = "delivered" if delivered else "pending" if pending_reason else "generated"
    severity = "ok" if delivered else "warning" if pending_reason else "info"
    checks = [
        _check("brief_text_present", bool(_optional_text(payload.get("text"))), "briefing text is present"),
        _check("delivery_state_recorded", "delivered" in payload, "delivery state is recorded"),
    ]

    return _base_record(
        record_type="dashboard_card",
        artifact_type="cassandra_briefing",
        artifact_id=f"{date}:{slot}",
        generated_at=_optional_text(payload.get("generated_at")),
        source_path=str(path),
        status=status,
        severity=severity,
        title=f"Cassandra {slot} briefing",
        summary=_bounded_text(pending_reason or payload.get("text") or "Briefing record has no text."),
        checks=checks,
        drilldown_refs=_source_ref(path),
    )


def _normalize_eod_review(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    summary = _optional_text(payload.get("summary"))
    empty_cause = _optional_text(payload.get("empty_output_cause"))
    findings = payload.get("findings") if isinstance(payload.get("findings"), list) else []
    proposal_ids = [str(item).strip() for item in payload.get("proposal_ids", []) if str(item).strip()]
    status = "completed" if summary else "empty"
    severity = "warning" if empty_cause else "info"
    checks = [
        _check("summary_present", bool(summary), "EOD summary is present"),
        _check("structured_lane_recorded", bool(_optional_text(payload.get("structured_output_lane"))), "structured output lane is recorded"),
        _check("findings_are_list", isinstance(findings, list), "findings field is a list"),
    ]
    refs = _source_ref(path)
    refs.extend({"label": "proposal", "reference_type": "proposal_id", "id": proposal_id} for proposal_id in proposal_ids)

    return _base_record(
        record_type="dashboard_card",
        artifact_type="chief_eod_review",
        artifact_id=_eod_artifact_id(payload),
        generated_at=_optional_text(payload.get("finished_at") or payload.get("started_at")),
        source_path=str(path),
        status=status,
        severity=severity,
        title="Chief end-of-day review",
        summary=_bounded_text(summary or empty_cause or "EOD review did not include a summary."),
        checks=checks,
        drilldown_refs=refs,
    )


def _normalize_loop_status(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    state = _text(payload.get("status"), "unknown")
    task_name = _text(payload.get("task_name"), "no active task")
    block_reason = _optional_text(payload.get("block_reason"))
    parked_reason = _optional_text(payload.get("parked_reason"))
    severity = "error" if state == "blocked" else "warning" if state == "parked" else "ok" if state == "idle" else "info"
    summary = block_reason or parked_reason or f"Current loop task: {task_name}."
    checks = [
        _check("state_is_known", state in _VALID_LOOP_STATES, "loop state is one of the accepted states"),
        _check("task_identity_recorded", bool(task_name), "task_name is recorded"),
    ]

    return _base_record(
        record_type="dashboard_card",
        artifact_type="loop_status",
        artifact_id="polish_loop_status",
        generated_at=_optional_text(payload.get("last_updated")),
        source_path=str(path),
        status=state,
        severity=severity,
        title=f"Loop status: {state}",
        summary=_bounded_text(summary),
        checks=checks,
        drilldown_refs=_source_ref(path),
    )


def _base_record(
    *,
    record_type: str,
    artifact_type: str,
    artifact_id: str,
    generated_at: str | None,
    source_path: str,
    status: str,
    severity: str,
    title: str,
    summary: str,
    checks: list[dict[str, Any]] | None = None,
    drilldown_refs: list[dict[str, Any]] | None = None,
    privacy_classification: str = "local_operational_metadata",
    allowed_surfaces: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": DASHBOARD_RECORD_SCHEMA_VERSION,
        "record_type": record_type,
        "artifact_type": artifact_type,
        "artifact_id": artifact_id,
        "generated_at": generated_at,
        "source_path": source_path,
        "status": status,
        "severity": severity,
        "title": title,
        "summary": summary,
        "checks": checks or [],
        "drilldown_refs": drilldown_refs or _source_ref(Path(source_path)),
        "privacy_classification": privacy_classification,
        "allowed_surfaces": allowed_surfaces if allowed_surfaces is not None else ["local_dashboard", "operator_report"],
    }


def _unsupported_record(path: Path, summary: str) -> dict[str, Any]:
    return _base_record(
        record_type="unsupported_artifact",
        artifact_type="unsupported",
        artifact_id=f"unsupported:{path.name}",
        generated_at=None,
        source_path=str(path),
        status="unsupported",
        severity="warning",
        title="Unsupported dashboard artifact",
        summary=summary,
        allowed_surfaces=[],
    )


def _normalize_checks(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    checks: list[dict[str, Any]] = []
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            checks.append(_check(f"check_{idx + 1}", False, "check entry is not an object"))
            continue
        name = _text(item.get("name"), f"check_{idx + 1}")
        passed = item.get("passed") is True
        detail = _bounded_text(item.get("detail") or item.get("summary") or "")
        checks.append(_check(name, passed, detail))
    return checks


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "severity": "ok" if passed else "error",
        "detail": _bounded_text(detail, limit=220),
    }


def _source_ref(path: Path) -> list[dict[str, Any]]:
    return [{"label": "source_artifact", "reference_type": "path", "path": str(path)}]


def _safe_path_refs(label: str, value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    refs: list[dict[str, Any]] = []
    for item in values:
        text = str(item or "").strip()
        if not text:
            continue
        try:
            _validated_reference_path(text)
        except DashboardEvidencePathError:
            refs.append({"label": label, "reference_type": "rejected_path", "path": text, "status": "rejected"})
            continue
        refs.append({"label": label, "reference_type": "path", "path": text})
    return refs


def _validated_reference_path(value: str) -> None:
    if "\x00" in value or any(marker in value for marker in _GLOB_MARKERS):
        raise DashboardEvidencePathError("unsafe_reference_path")
    path = Path(value)
    if any(part == ".." for part in path.parts):
        raise DashboardEvidencePathError("unsafe_reference_path")
    lowered = value.lower().replace("\\", "/")
    if any(marker in lowered for marker in _FORBIDDEN_PATH_MARKERS):
        raise DashboardEvidencePathError("forbidden_reference_path")


def _eod_artifact_id(payload: dict[str, Any]) -> str:
    for key in ("finished_at", "started_at"):
        value = _optional_text(payload.get(key))
        if value:
            return f"chief_eod_review:{value[:10]}"
    return "chief_eod_review:unknown"


def _int_value(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _text(value: object, fallback: str) -> str:
    return _optional_text(value) or fallback


def _bounded_text(value: object, *, limit: int = 280) -> str:
    text = re.sub(r"\s+", " ", str(value or "").replace("\x00", " ")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


__all__ = [
    "DASHBOARD_RECORD_SCHEMA_VERSION",
    "DashboardEvidencePathError",
    "load_dashboard_evidence",
    "normalize_dashboard_artifact",
    "normalize_dashboard_artifacts",
]