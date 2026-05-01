from __future__ import annotations

"""Pure dashboard report snapshot building from normalized evidence records."""

import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping


DASHBOARD_REPORT_SNAPSHOT_SCHEMA_VERSION = 1
DASHBOARD_REPORT_SNAPSHOT_TYPE = "openclaw.dashboard_report_snapshot"

_DEFAULT_CREATED_AT = "unspecified"
_DEFAULT_MAX_RECORDS = 50
_DEFAULT_MAX_TOP_ISSUES = 10
_TEXT_LIMIT = 240
_SUMMARY_LIMIT = 360
_MARKDOWN_MAX_RECORDS = 20
_MARKDOWN_MAX_TOP_ISSUES = 10
_MARKDOWN_MAX_COUNT_ITEMS = 25
_MARKDOWN_MAX_CHARS = 12000
_DISABLED_CONTROL_FLAGS = (
    "execution_allowed",
    "service_wiring_allowed",
    "telegram_send_allowed",
    "dashboard_control_allowed",
)
_READY_STATUSES = frozenset({
    "completed",
    "delivered",
    "idle",
    "metadata_only",
    "passed",
    "ready_for_morning_synthesis",
    "ready_for_service_timer_wiring",
})
_BLOCKED_STATUSES = frozenset({"blocked", "error", "failed", "unsafe_execution_enabled"})
_REVIEW_STATUSES = frozenset({
    "approval_required",
    "blocked",
    "failed",
    "missing",
    "not_ready",
    "parked",
    "pending",
    "refused",
    "unsupported",
    "unsafe_execution_enabled",
})
_REVIEW_SEVERITIES = frozenset({"error", "warning"})
_ISSUE_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "error": 1, "warning": 2, "info": 4, "ok": 5}
_FORBIDDEN_PATH_MARKERS = (
    ".chief.env",
    ".env",
    ".google-secrets",
    "credentials",
    "gmail",
    "hermes",
    "legal",
    "legalprivate",
    "openclawlegalprivate",
    "private",
    "secret",
    "token",
    "vault",
)
_FORBIDDEN_OUTPUT_SUFFIXES = frozenset({".csv", ".db", ".jsonl", ".log", ".out", ".sqlite", ".sqlite3"})
_GLOB_MARKERS = frozenset({"*", "?", "[", "]"})


class DashboardReportSnapshotPathError(ValueError):
    """Raised when an explicit dashboard snapshot output path is unsafe."""


class DashboardReportSnapshotRenderError(ValueError):
    """Raised when a snapshot cannot be safely rendered as Markdown."""


def build_dashboard_report_snapshot(
    evidence_records: Iterable[Mapping[str, Any] | object],
    *,
    created_at: str | None = None,
    max_records: int = _DEFAULT_MAX_RECORDS,
    max_top_issues: int = _DEFAULT_MAX_TOP_ISSUES,
) -> dict[str, Any]:
    """Build a deterministic bounded report snapshot from normalized records."""
    records = [record for record in evidence_records if isinstance(record, Mapping)]
    record_limit = _bounded_int(max_records, default=_DEFAULT_MAX_RECORDS, lower=0, upper=250)
    issue_limit = _bounded_int(max_top_issues, default=_DEFAULT_MAX_TOP_ISSUES, lower=0, upper=100)
    status_counts = _count_tokens(record.get("status") for record in records)
    severity_counts = _count_tokens(record.get("severity") for record in records)
    ready_count = sum(1 for record in records if _record_is_ready(record))
    blocked_count = sum(1 for record in records if _record_is_blocked(record))
    requires_review_count = sum(1 for record in records if _record_requires_review(record))
    normalized_records = [_snapshot_record(record) for record in records[:record_limit]]
    top_issues = _top_issues(records, limit=issue_limit)

    return {
        "snapshot_type": DASHBOARD_REPORT_SNAPSHOT_TYPE,
        "schema_version": DASHBOARD_REPORT_SNAPSHOT_SCHEMA_VERSION,
        "created_at": _optional_text(created_at) or _DEFAULT_CREATED_AT,
        "total_records": len(records),
        "status_counts": status_counts,
        "severity_counts": severity_counts,
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "requires_review_count": requires_review_count,
        "records": normalized_records,
        "top_issues": top_issues,
        "execution_allowed": False,
        "service_wiring_allowed": False,
        "telegram_send_allowed": False,
        "dashboard_control_allowed": False,
        "summary": _snapshot_summary(
            total_records=len(records),
            ready_count=ready_count,
            blocked_count=blocked_count,
            requires_review_count=requires_review_count,
            top_issue_count=len(top_issues),
        ),
    }


def write_dashboard_report_snapshot(snapshot: Mapping[str, Any], output_path: str | Path) -> Path:
    """Write a snapshot JSON document to one caller-supplied safe path."""
    path = _validated_output_path(output_path)
    path.write_text(json.dumps(dict(snapshot), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def render_dashboard_report_snapshot_markdown(
    snapshot: Mapping[str, Any] | object,
    *,
    max_records: int = _MARKDOWN_MAX_RECORDS,
    max_top_issues: int = _MARKDOWN_MAX_TOP_ISSUES,
) -> str:
    """Render a validated dashboard report snapshot as bounded report-only Markdown."""
    checked_snapshot = _validated_markdown_snapshot(snapshot)
    record_limit = _bounded_int(max_records, default=_MARKDOWN_MAX_RECORDS, lower=0, upper=_MARKDOWN_MAX_RECORDS)
    issue_limit = _bounded_int(max_top_issues, default=_MARKDOWN_MAX_TOP_ISSUES, lower=0, upper=_MARKDOWN_MAX_TOP_ISSUES)
    records = _markdown_mapping_list(checked_snapshot.get("records"), "records")
    top_issues = _markdown_mapping_list(checked_snapshot.get("top_issues"), "top_issues")
    lines = [
        "# OpenClaw Dashboard Report Snapshot",
        "",
        "## Snapshot",
        f"- snapshot_type: `{_markdown_code_text(checked_snapshot.get('snapshot_type'), DASHBOARD_REPORT_SNAPSHOT_TYPE)}`",
        f"- schema_version: `{_markdown_int_text(checked_snapshot.get('schema_version'), 'schema_version')}`",
        f"- created_at: `{_markdown_code_text(checked_snapshot.get('created_at'), _DEFAULT_CREATED_AT)}`",
        f"- total_records: `{_markdown_int_text(checked_snapshot.get('total_records'), 'total_records')}`",
        "",
        "## Status Counts",
    ]
    _append_markdown_counts(lines, checked_snapshot.get("status_counts"), "status_counts")
    lines.extend(["", "## Severity Counts"])
    _append_markdown_counts(lines, checked_snapshot.get("severity_counts"), "severity_counts")
    lines.extend([
        "",
        "## Readiness Counts",
        f"- ready_count: {_markdown_int_text(checked_snapshot.get('ready_count'), 'ready_count')}",
        f"- blocked_count: {_markdown_int_text(checked_snapshot.get('blocked_count'), 'blocked_count')}",
        f"- requires_review_count: {_markdown_int_text(checked_snapshot.get('requires_review_count'), 'requires_review_count')}",
        "",
        "## Disabled Controls",
    ])
    for flag in _DISABLED_CONTROL_FLAGS:
        lines.append(f"- {flag}: false")
    lines.extend([
        "",
        "## Boundary",
        "This Markdown export is report-only and is not an execution surface.",
        "",
        "## Top Issues",
    ])
    _append_markdown_issues(lines, top_issues[:issue_limit], omitted_count=max(0, len(top_issues) - issue_limit))
    lines.extend(["", "## Record Summaries"])
    _append_markdown_records(lines, records[:record_limit], omitted_count=max(0, len(records) - record_limit))
    markdown = "\n".join(lines).rstrip() + "\n"
    if len(markdown) > _MARKDOWN_MAX_CHARS:
        return markdown[: _MARKDOWN_MAX_CHARS - 6].rstrip() + "\n...\n"
    return markdown


def _snapshot_record(record: Mapping[str, Any]) -> dict[str, Any]:
    blocker_count = _record_blocker_count(record)
    issue_count = _record_issue_count(record)
    safe_source_path = _safe_path_text(record.get("source_path"))
    snapshot = {
        "record_type": _text(record.get("record_type"), "dashboard_record"),
        "artifact_type": _text(record.get("artifact_type"), "unknown"),
        "artifact_id": _text(record.get("artifact_id"), "unknown"),
        "generated_at": _optional_text(record.get("generated_at")),
        "status": _token(record.get("status"), "unknown"),
        "severity": _token(record.get("severity"), "info"),
        "title": _bounded_text(record.get("title") or record.get("artifact_id") or "Dashboard evidence record"),
        "summary": _bounded_text(record.get("summary") or ""),
        "source_path": safe_source_path,
        "source_path_status": "accepted" if safe_source_path else "rejected" if _optional_text(record.get("source_path")) else "absent",
        "ready_for_morning_synthesis": _optional_bool(record.get("ready_for_morning_synthesis")),
        "ready_for_service_timer_wiring": _optional_bool(record.get("ready_for_service_timer_wiring")),
        "execution_allowed": _optional_bool(record.get("execution_allowed")),
        "service_wiring_allowed": _optional_bool(record.get("service_wiring_allowed")),
        "blocker_count": blocker_count,
        "issue_count": issue_count,
    }
    dashboard_issue_ids = _dashboard_issue_ids(record)
    if dashboard_issue_ids:
        snapshot["dashboard_issue_ids"] = dashboard_issue_ids
    drilldown_refs = _snapshot_refs(record.get("drilldown_refs"))
    if drilldown_refs:
        snapshot["drilldown_refs"] = drilldown_refs
    return snapshot


def _top_issues(records: list[Mapping[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for record_index, record in enumerate(records):
        parent_artifact_id = _text(record.get("artifact_id"), f"record_{record_index + 1}")
        parent_artifact_type = _text(record.get("artifact_type"), "unknown")
        raw_issues = record.get("dashboard_issues") if isinstance(record.get("dashboard_issues"), list) else []
        for issue_index, issue in enumerate(raw_issues, start=1):
            if isinstance(issue, Mapping):
                issues.append(_snapshot_issue(
                    issue,
                    parent_artifact_id=parent_artifact_id,
                    parent_artifact_type=parent_artifact_type,
                    issue_index=issue_index,
                ))
    issues.sort(key=_issue_sort_key)
    return issues[:limit]


def _snapshot_issue(
    issue: Mapping[str, Any],
    *,
    parent_artifact_id: str,
    parent_artifact_type: str,
    issue_index: int,
) -> dict[str, Any]:
    issue_id = _text(issue.get("issue_id") or issue.get("artifact_id"), f"issue_{issue_index}")
    blocking = issue.get("blocking_readiness") is True or _token(issue.get("status"), "open") == "blocking"
    return {
        "record_type": "dashboard_issue",
        "parent_artifact_id": parent_artifact_id,
        "parent_artifact_type": parent_artifact_type,
        "artifact_id": _text(issue.get("artifact_id"), f"{parent_artifact_id}:{issue_id}"),
        "issue_id": issue_id,
        "status": "blocking" if blocking else _token(issue.get("status"), "open"),
        "severity": _token(issue.get("severity"), "medium"),
        "title": _bounded_text(issue.get("title") or issue_id, limit=180),
        "summary": _bounded_text(issue.get("summary") or "", limit=220),
        "blocking_readiness": blocking,
        "source_refs": _snapshot_refs(issue.get("source_refs")),
    }


def _snapshot_refs(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    refs: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        ref = {
            "label": _text(item.get("label"), "source_ref"),
            "reference_type": _text(item.get("reference_type"), "reference"),
        }
        identifier = _optional_text(item.get("id"))
        if identifier:
            ref["id"] = _bounded_text(identifier, limit=160)
        path = _safe_path_text(item.get("path"))
        if path:
            ref["path"] = path
            ref["status"] = _text(item.get("status"), "accepted")
        elif _optional_text(item.get("path")):
            ref["status"] = "rejected"
        elif _optional_text(item.get("status")):
            ref["status"] = _text(item.get("status"), "recorded")
        refs.append(ref)
    return refs[:10]


def _record_is_ready(record: Mapping[str, Any]) -> bool:
    if _record_is_blocked(record):
        return False
    if record.get("ready_for_service_timer_wiring") is True or record.get("ready_for_morning_synthesis") is True:
        return True
    return _token(record.get("status"), "unknown") in _READY_STATUSES and _token(record.get("severity"), "info") != "error"


def _record_is_blocked(record: Mapping[str, Any]) -> bool:
    return _record_blocker_count(record) > 0 or _token(record.get("status"), "unknown") in _BLOCKED_STATUSES


def _record_requires_review(record: Mapping[str, Any]) -> bool:
    return (
        _record_is_blocked(record)
        or _record_issue_count(record) > 0
        or _token(record.get("status"), "unknown") in _REVIEW_STATUSES
        or _token(record.get("severity"), "info") in _REVIEW_SEVERITIES
    )


def _record_blocker_count(record: Mapping[str, Any]) -> int:
    explicit = _optional_int(record.get("blocker_count"))
    if explicit is not None:
        return max(explicit, 0)
    raw_issues = record.get("dashboard_issues") if isinstance(record.get("dashboard_issues"), list) else []
    return sum(1 for issue in raw_issues if isinstance(issue, Mapping) and issue.get("blocking_readiness") is True)


def _record_issue_count(record: Mapping[str, Any]) -> int:
    explicit = _optional_int(record.get("issue_count"))
    if explicit is not None:
        return max(explicit, 0)
    raw_issues = record.get("dashboard_issues") if isinstance(record.get("dashboard_issues"), list) else []
    return sum(1 for issue in raw_issues if isinstance(issue, Mapping))


def _dashboard_issue_ids(record: Mapping[str, Any]) -> list[str]:
    raw_issues = record.get("dashboard_issues") if isinstance(record.get("dashboard_issues"), list) else []
    ids: list[str] = []
    for index, issue in enumerate(raw_issues, start=1):
        if isinstance(issue, Mapping):
            ids.append(_text(issue.get("issue_id") or issue.get("artifact_id"), f"issue_{index}"))
    return ids[:25]


def _snapshot_summary(
    *,
    total_records: int,
    ready_count: int,
    blocked_count: int,
    requires_review_count: int,
    top_issue_count: int,
) -> str:
    return _bounded_text(
        (
            f"{total_records} dashboard evidence record(s); {ready_count} ready; "
            f"{blocked_count} blocked; {requires_review_count} require review; "
            f"{top_issue_count} top issue(s). Execution, service wiring, Telegram send, and dashboard control remain disabled."
        ),
        limit=_SUMMARY_LIMIT,
    )


def _count_tokens(values: Iterable[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        token = _token(value, "unknown")
        counts[token] = counts.get(token, 0) + 1
    return dict(sorted(counts.items()))


def _issue_sort_key(issue: Mapping[str, Any]) -> tuple[int, int, str]:
    severity = _token(issue.get("severity"), "medium")
    blocking_rank = 0 if issue.get("blocking_readiness") is True else 1
    return (_ISSUE_SEVERITY_RANK.get(severity, 6), blocking_rank, _text(issue.get("issue_id"), "issue"))


def _validated_markdown_snapshot(snapshot: Mapping[str, Any] | object) -> Mapping[str, Any]:
    if not isinstance(snapshot, Mapping):
        raise DashboardReportSnapshotRenderError("snapshot_must_be_mapping")
    if _text(snapshot.get("snapshot_type"), "") != DASHBOARD_REPORT_SNAPSHOT_TYPE:
        raise DashboardReportSnapshotRenderError("invalid_snapshot_type")
    if _optional_int(snapshot.get("schema_version")) != DASHBOARD_REPORT_SNAPSHOT_SCHEMA_VERSION:
        raise DashboardReportSnapshotRenderError("invalid_schema_version")
    for field_name in ("total_records", "ready_count", "blocked_count", "requires_review_count"):
        _markdown_int_text(snapshot.get(field_name), field_name)
    _markdown_counts(snapshot.get("status_counts"), "status_counts")
    _markdown_counts(snapshot.get("severity_counts"), "severity_counts")
    _markdown_mapping_list(snapshot.get("records"), "records")
    _markdown_mapping_list(snapshot.get("top_issues"), "top_issues")
    for flag in _DISABLED_CONTROL_FLAGS:
        if snapshot.get(flag) is not False:
            raise DashboardReportSnapshotRenderError(f"{flag}_must_be_false")
    _markdown_code_text(snapshot.get("created_at"), _DEFAULT_CREATED_AT)
    return snapshot


def _append_markdown_counts(lines: list[str], counts: object, field_name: str) -> None:
    count_items = _markdown_counts(counts, field_name)
    if not count_items:
        lines.append("- none")
        return
    for token, count in count_items:
        lines.append(f"- {token}: {count}")


def _append_markdown_issues(lines: list[str], issues: list[Mapping[str, Any]], *, omitted_count: int) -> None:
    if not issues:
        lines.append("- none")
    for issue_index, issue in enumerate(issues, start=1):
        severity = _markdown_code_text(_token(issue.get("severity"), "medium"), "medium", limit=80)
        status = _markdown_code_text(_token(issue.get("status"), "open"), "open", limit=80)
        title = _markdown_inline_text(issue.get("title"), "Untitled issue", limit=180)
        issue_id = _markdown_code_text(issue.get("issue_id") or issue.get("artifact_id"), f"issue_{issue_index}", limit=160)
        parent = _markdown_code_text(issue.get("parent_artifact_id"), "unknown", limit=180)
        summary = _markdown_inline_text(issue.get("summary"), "", limit=220)
        lines.append(f"{issue_index}. `{severity}` / `{status}` - {title}")
        lines.append(f"   - issue_id: `{issue_id}`")
        lines.append(f"   - parent_artifact_id: `{parent}`")
        if summary:
            lines.append(f"   - summary: {summary}")
        _append_markdown_ref_lines(lines, issue.get("source_refs"), indent="   ")
    if omitted_count:
        lines.append(f"- {omitted_count} additional issue(s) omitted by Markdown bound.")


def _append_markdown_records(lines: list[str], records: list[Mapping[str, Any]], *, omitted_count: int) -> None:
    if not records:
        lines.append("- none")
    for record_index, record in enumerate(records, start=1):
        artifact_type = _markdown_code_text(record.get("artifact_type"), "unknown", limit=120)
        artifact_id = _markdown_code_text(record.get("artifact_id"), f"record_{record_index}", limit=180)
        status = _markdown_code_text(_token(record.get("status"), "unknown"), "unknown", limit=80)
        severity = _markdown_code_text(_token(record.get("severity"), "info"), "info", limit=80)
        title = _markdown_inline_text(record.get("title"), "Dashboard evidence record", limit=180)
        summary = _markdown_inline_text(record.get("summary"), "", limit=220)
        generated_at = _optional_text(record.get("generated_at"))
        source_path = _markdown_path_text(record.get("source_path"))
        source_status = _markdown_code_text(record.get("source_path_status"), "absent", limit=80)
        lines.append(f"{record_index}. `{artifact_type}` / `{artifact_id}`")
        lines.append(f"   - status: `{status}`; severity: `{severity}`; title: {title}")
        if generated_at:
            lines.append(f"   - generated_at: `{_markdown_code_text(generated_at, 'unspecified')}`")
        if summary:
            lines.append(f"   - summary: {summary}")
        if source_path:
            lines.append(f"   - source_ref: `{source_path}` (`{source_status}`)")
        elif source_status != "absent":
            lines.append(f"   - source_ref: `{source_status}`")
        _append_markdown_ref_lines(lines, record.get("drilldown_refs"), indent="   ", label="drilldown_refs")
    if omitted_count:
        lines.append(f"- {omitted_count} additional record(s) omitted by Markdown bound.")


def _append_markdown_ref_lines(lines: list[str], refs: object, *, indent: str, label: str = "source_refs") -> None:
    ref_lines = _markdown_ref_lines(refs, label)
    if ref_lines:
        lines.append(f"{indent}- {label}:")
        for ref_line in ref_lines:
            lines.append(f"{indent}  - {ref_line}")


def _markdown_counts(counts: object, field_name: str) -> list[tuple[str, int]]:
    if not isinstance(counts, Mapping):
        raise DashboardReportSnapshotRenderError(f"{field_name}_must_be_mapping")
    count_items: list[tuple[str, int]] = []
    for raw_key, raw_count in sorted(counts.items(), key=lambda item: str(item[0]))[:_MARKDOWN_MAX_COUNT_ITEMS]:
        count = _optional_int(raw_count)
        if count is None or count < 0:
            raise DashboardReportSnapshotRenderError(f"{field_name}_contains_invalid_count")
        count_items.append((_markdown_code_text(_token(raw_key, "unknown"), "unknown", limit=80), count))
    return count_items


def _markdown_mapping_list(value: object, field_name: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        raise DashboardReportSnapshotRenderError(f"{field_name}_must_be_list")
    mappings: list[Mapping[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise DashboardReportSnapshotRenderError(f"{field_name}_contains_non_mapping")
        mappings.append(item)
    return mappings


def _markdown_ref_lines(refs: object, field_name: str) -> list[str]:
    if refs is None:
        return []
    if not isinstance(refs, list):
        raise DashboardReportSnapshotRenderError(f"{field_name}_must_be_list")
    lines: list[str] = []
    for ref in refs[:10]:
        if not isinstance(ref, Mapping):
            raise DashboardReportSnapshotRenderError(f"{field_name}_contains_non_mapping")
        label = _markdown_inline_text(ref.get("label"), "source_ref", limit=80)
        reference_type = _markdown_inline_text(ref.get("reference_type"), "reference", limit=80)
        status = _markdown_inline_text(ref.get("status"), "recorded", limit=80)
        path = _markdown_path_text(ref.get("path"))
        identifier = _optional_text(ref.get("id"))
        if path:
            lines.append(f"{label} {reference_type} `{path}` ({status})")
        elif identifier:
            lines.append(f"{label} {reference_type} `{_markdown_code_text(identifier, 'ref', limit=160)}` ({status})")
        else:
            lines.append(f"{label} {reference_type} {status}")
    return lines


def _markdown_int_text(value: object, field_name: str) -> str:
    parsed = _optional_int(value)
    if parsed is None or parsed < 0:
        raise DashboardReportSnapshotRenderError(f"{field_name}_must_be_nonnegative_int")
    return str(parsed)


def _markdown_path_text(value: object) -> str | None:
    text = _optional_text(value)
    if not text:
        return None
    if not _path_text_is_safe(text):
        raise DashboardReportSnapshotRenderError("unsafe_reference_path")
    return _markdown_code_text(text, "reference", limit=240)


def _markdown_code_text(value: object, fallback: str, *, limit: int = _TEXT_LIMIT) -> str:
    return _markdown_inline_text(value, fallback, limit=limit).replace("`", "'")


def _markdown_inline_text(value: object, fallback: str, *, limit: int = _TEXT_LIMIT) -> str:
    text = _bounded_text(value if _optional_text(value) else fallback, limit=limit).replace("|", "/")
    if _markdown_text_has_forbidden_marker(text):
        raise DashboardReportSnapshotRenderError("unsafe_private_marker")
    return text


def _markdown_text_has_forbidden_marker(text: str) -> bool:
    lowered = text.lower().replace("\\", "/")
    return any(marker in lowered for marker in _FORBIDDEN_PATH_MARKERS)


def _validated_output_path(value: str | Path) -> Path:
    raw = str(value or "").strip()
    if not raw:
        raise DashboardReportSnapshotPathError("missing_output_path")
    if not _path_text_is_safe(raw):
        raise DashboardReportSnapshotPathError("unsafe_output_path")
    path = Path(raw)
    if path.suffix.lower() != ".json" or path.suffix.lower() in _FORBIDDEN_OUTPUT_SUFFIXES:
        raise DashboardReportSnapshotPathError("unsupported_output_suffix")
    return path


def _safe_path_text(value: object) -> str | None:
    text = _optional_text(value)
    if not text or not _path_text_is_safe(text):
        return None
    return text


def _path_text_is_safe(value: str) -> bool:
    if "\x00" in value or any(marker in value for marker in _GLOB_MARKERS):
        return False
    path = Path(value)
    if any(part == ".." for part in path.parts):
        return False
    lowered = value.lower().replace("\\", "/")
    return not any(marker in lowered for marker in _FORBIDDEN_PATH_MARKERS)


def _bounded_int(value: object, *, default: int, lower: int, upper: int) -> int:
    parsed = _optional_int(value)
    if parsed is None:
        return default
    return max(lower, min(parsed, upper))


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _token(value: object, fallback: str) -> str:
    return _text(value, fallback).lower().replace("-", "_").replace(" ", "_")


def _text(value: object, fallback: str) -> str:
    return _optional_text(value) or fallback


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _bounded_text(value: object, *, limit: int = _TEXT_LIMIT) -> str:
    text = re.sub(r"\s+", " ", str(value or "").replace("\x00", " ")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


__all__ = [
    "DASHBOARD_REPORT_SNAPSHOT_SCHEMA_VERSION",
    "DASHBOARD_REPORT_SNAPSHOT_TYPE",
    "DashboardReportSnapshotPathError",
    "DashboardReportSnapshotRenderError",
    "build_dashboard_report_snapshot",
    "render_dashboard_report_snapshot_markdown",
    "write_dashboard_report_snapshot",
]