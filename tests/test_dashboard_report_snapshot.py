from __future__ import annotations

import ast
import builtins
import importlib
import inspect
import json
import sys
from pathlib import Path

import pytest

import dashboard_report_snapshot as snapshot


def _evidence_record(**overrides):
    record = {
        "schema_version": 1,
        "record_type": "dashboard_card",
        "artifact_type": "harness_manifest",
        "artifact_id": "chief_eod_harness:chief_end_of_day_review:2026-04-30T05:00:00",
        "generated_at": "2026-04-30T05:00:00Z",
        "source_path": "artifacts/eod_harness/manifest.json",
        "status": "passed",
        "severity": "ok",
        "title": "chief_eod_harness: chief_end_of_day_review",
        "summary": "5/5 checks passed; 0 failed.",
        "checks": [],
        "drilldown_refs": [
            {"label": "source_artifact", "reference_type": "path", "path": "artifacts/eod_harness/manifest.json"}
        ],
        "allowed_surfaces": ["local_dashboard", "operator_report"],
    }
    record.update(overrides)
    return record


def _overnight_record(**overrides):
    record = _evidence_record(
        artifact_type="overnight_run_manifest",
        artifact_id="overnight_run_manifest:2026-04-30",
        generated_at="2026-04-30T06:00:00Z",
        source_path="artifacts/overnight/manifest.json",
        status="ready_for_morning_synthesis",
        severity="ok",
        title="Overnight run manifest: 2026-04-30",
        summary="2026-04-30: morning synthesis readiness is true; service/timer readiness is false; execution remains disabled.",
        cycle_date="2026-04-30",
        readiness_status="ready_for_morning_synthesis",
        ready_for_morning_synthesis=True,
        ready_for_service_timer_wiring=False,
        execution_allowed=False,
        service_wiring_allowed=False,
        dashboard_issues=[],
        issue_count=0,
        blocker_count=0,
    )
    record.update(overrides)
    return record


def _issue(**overrides):
    issue = {
        "record_type": "dashboard_issue",
        "artifact_type": "overnight_run_manifest_issue",
        "artifact_id": "overnight_run_manifest:2026-04-30:overnight-20260430-eod-harness-failed",
        "issue_id": "overnight-20260430-eod-harness-failed",
        "status": "blocking",
        "severity": "high",
        "title": "EOD harness evidence reported one or more failed checks.",
        "summary": "Inspect the referenced EOD harness manifest.",
        "blocking_readiness": True,
        "source_refs": [
            {"label": "source_artifact", "reference_type": "path", "path": "artifacts/eod_harness/manifest.json"}
        ],
    }
    issue.update(overrides)
    return issue


def test_valid_records_produce_deterministic_snapshot():
    records = [
        _overnight_record(),
        _evidence_record(
            artifact_type="cassandra_briefing",
            artifact_id="2026-04-30:morning",
            status="pending",
            severity="warning",
            title="Cassandra morning briefing",
            summary="focus_mode",
        ),
    ]

    first = snapshot.build_dashboard_report_snapshot(records, created_at="2026-05-01T12:00:00Z")
    second = snapshot.build_dashboard_report_snapshot(records, created_at="2026-05-01T12:00:00Z")

    assert first == second
    assert first["snapshot_type"] == "openclaw.dashboard_report_snapshot"
    assert first["schema_version"] == 1
    assert first["created_at"] == "2026-05-01T12:00:00Z"
    assert first["total_records"] == 2
    assert first["status_counts"] == {"pending": 1, "ready_for_morning_synthesis": 1}
    assert first["severity_counts"] == {"ok": 1, "warning": 1}
    assert first["ready_count"] == 1
    assert first["blocked_count"] == 0
    assert first["requires_review_count"] == 1
    assert len(first["records"]) == 2
    assert "Execution, service wiring, Telegram send, and dashboard control remain disabled." in first["summary"]


def test_overnight_manifest_records_contribute_readiness_and_blocker_counts():
    blocked = _overnight_record(
        status="blocked",
        severity="error",
        ready_for_morning_synthesis=False,
        dashboard_issues=[_issue()],
        issue_count=1,
        blocker_count=1,
    )

    report = snapshot.build_dashboard_report_snapshot([_overnight_record(), blocked], created_at="2026-05-01T12:00:00Z")

    assert report["ready_count"] == 1
    assert report["blocked_count"] == 1
    assert report["requires_review_count"] == 1
    assert report["status_counts"] == {"blocked": 1, "ready_for_morning_synthesis": 1}
    assert report["records"][1]["blocker_count"] == 1
    assert report["records"][1]["issue_count"] == 1
    assert report["records"][1]["dashboard_issue_ids"] == ["overnight-20260430-eod-harness-failed"]


def test_blockers_and_issues_appear_in_top_issues():
    medium_issue = _issue(
        artifact_id="overnight_run_manifest:2026-04-30:overnight-20260430-operator-note",
        issue_id="overnight-20260430-operator-note",
        status="open",
        severity="medium",
        blocking_readiness=False,
        title="Operator note carried for dashboard drill-down.",
    )
    blocked = _overnight_record(
        status="blocked",
        severity="error",
        ready_for_morning_synthesis=False,
        dashboard_issues=[medium_issue, _issue()],
        issue_count=2,
        blocker_count=1,
    )

    report = snapshot.build_dashboard_report_snapshot([blocked], created_at="2026-05-01T12:00:00Z")

    assert [issue["issue_id"] for issue in report["top_issues"]] == [
        "overnight-20260430-eod-harness-failed",
        "overnight-20260430-operator-note",
    ]
    assert report["top_issues"][0]["status"] == "blocking"
    assert report["top_issues"][0]["parent_artifact_type"] == "overnight_run_manifest"
    assert report["top_issues"][0]["source_refs"] == [
        {"label": "source_artifact", "reference_type": "path", "path": "artifacts/eod_harness/manifest.json", "status": "accepted"}
    ]


def test_control_flags_remain_false_even_if_record_requests_control():
    record = _overnight_record(
        execution_allowed=True,
        service_wiring_allowed=True,
        telegram_send_allowed=True,
        dashboard_control_allowed=True,
    )

    report = snapshot.build_dashboard_report_snapshot([record], created_at="2026-05-01T12:00:00Z")

    assert report["execution_allowed"] is False
    assert report["service_wiring_allowed"] is False
    assert report["telegram_send_allowed"] is False
    assert report["dashboard_control_allowed"] is False


def test_snapshot_builder_does_not_read_referenced_drilldown_files(tmp_path, monkeypatch):
    referenced = tmp_path / "drilldown.json"
    referenced.write_text('{"would": "fail if read"}', encoding="utf-8")
    record = _overnight_record(
        source_path="artifacts/overnight/manifest.json",
        drilldown_refs=[{"label": "eod_review", "reference_type": "path", "path": str(referenced)}],
        dashboard_issues=[_issue(source_refs=[{"label": "source_artifact", "reference_type": "path", "path": str(referenced)}])],
        issue_count=1,
    )
    original_read_text = Path.read_text

    def guarded_read_text(self, *args, **kwargs):
        if self == referenced:
            raise AssertionError("snapshot builder should not read drilldown references")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    report = snapshot.build_dashboard_report_snapshot([record], created_at="2026-05-01T12:00:00Z")

    assert report["top_issues"][0]["source_refs"][0]["path"] == str(referenced)


def test_write_snapshot_writes_only_explicit_json_path(tmp_path):
    report = snapshot.build_dashboard_report_snapshot([_overnight_record()], created_at="2026-05-01T12:00:00Z")
    output_path = tmp_path / "dashboard_snapshot.json"

    returned = snapshot.write_dashboard_report_snapshot(report, output_path)

    assert returned == output_path
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["snapshot_type"] == "openclaw.dashboard_report_snapshot"
    assert written["execution_allowed"] is False


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "../snapshot.json",
        "reports/*/snapshot.json",
        "/mnt/c/OpenClawLegalPrivate/snapshot.json",
        "/home/openclaw/.chief.env",
        "/tmp/dashboard_snapshot.log",
        "/tmp/private-dashboard/snapshot.json",
    ],
)
def test_write_snapshot_rejects_unsafe_private_output_paths(unsafe_path):
    report = snapshot.build_dashboard_report_snapshot([_overnight_record()], created_at="2026-05-01T12:00:00Z")

    with pytest.raises(snapshot.DashboardReportSnapshotPathError):
        snapshot.write_dashboard_report_snapshot(report, unsafe_path)


def test_private_refs_are_not_copied_into_snapshot_top_issues():
    record = _overnight_record(
        source_path="/mnt/c/OpenClawLegalPrivate/overnight_manifest.json",
        dashboard_issues=[
            _issue(source_refs=[{"label": "source_artifact", "reference_type": "path", "path": "/mnt/c/OpenClawLegalPrivate/matter.json"}])
        ],
        issue_count=1,
        blocker_count=1,
    )

    report = snapshot.build_dashboard_report_snapshot([record], created_at="2026-05-01T12:00:00Z")

    assert report["records"][0]["source_path"] is None
    assert report["records"][0]["source_path_status"] == "rejected"
    assert report["top_issues"][0]["source_refs"] == [
        {"label": "source_artifact", "reference_type": "path", "status": "rejected"}
    ]


def test_valid_snapshot_renders_deterministic_markdown():
    records = [
        _overnight_record(),
        _evidence_record(
            artifact_type="cassandra_briefing",
            artifact_id="2026-04-30:morning",
            status="pending",
            severity="warning",
            title="Cassandra morning briefing",
            summary="focus_mode",
        ),
    ]
    report = snapshot.build_dashboard_report_snapshot(records, created_at="2026-05-01T12:00:00Z")

    first = snapshot.render_dashboard_report_snapshot_markdown(report)
    second = snapshot.render_dashboard_report_snapshot_markdown(report)

    assert first == second
    assert first.startswith("# OpenClaw Dashboard Report Snapshot\n")
    assert "snapshot_type: `openclaw.dashboard_report_snapshot`" in first
    assert "schema_version: `1`" in first
    assert "created_at: `2026-05-01T12:00:00Z`" in first
    assert "total_records: `2`" in first
    assert "- pending: 1" in first
    assert "- ready_for_morning_synthesis: 1" in first
    assert "- warning: 1" in first
    assert "- ready_count: 1" in first
    assert "- blocked_count: 0" in first
    assert "- requires_review_count: 1" in first
    assert "execution_allowed: false" in first
    assert "service_wiring_allowed: false" in first
    assert "telegram_send_allowed: false" in first
    assert "dashboard_control_allowed: false" in first
    assert "This Markdown export is report-only and is not an execution surface." in first


def test_top_issues_render_without_private_or_raw_content():
    record = _overnight_record(
        status="blocked",
        severity="error",
        ready_for_morning_synthesis=False,
        dashboard_issues=[
            _issue(
                summary="Inspect the referenced sanitized harness manifest.",
                raw_content="PRIVATE SECRET FULL TEXT SHOULD NOT RENDER",
                source_refs=[
                    {"label": "source_artifact", "reference_type": "path", "path": "/mnt/c/OpenClawLegalPrivate/matter.json"}
                ],
            )
        ],
        issue_count=1,
        blocker_count=1,
    )
    report = snapshot.build_dashboard_report_snapshot([record], created_at="2026-05-01T12:00:00Z")

    markdown = snapshot.render_dashboard_report_snapshot_markdown(report)

    assert "overnight-20260430-eod-harness-failed" in markdown
    assert "Inspect the referenced sanitized harness manifest." in markdown
    assert "PRIVATE SECRET FULL TEXT" not in markdown
    assert "OpenClawLegalPrivate" not in markdown
    assert "source_artifact path rejected" in markdown


def test_markdown_drilldown_refs_are_rendered_without_file_reads(tmp_path, monkeypatch):
    referenced = tmp_path / "drilldown.json"
    referenced.write_text('{"would": "fail if read"}', encoding="utf-8")
    record = _overnight_record(
        drilldown_refs=[{"label": "overnight_manifest", "reference_type": "path", "path": str(referenced)}],
    )
    original_read_text = Path.read_text

    def guarded_read_text(self, *args, **kwargs):
        if self == referenced:
            raise AssertionError("markdown renderer should not read drilldown references")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    report = snapshot.build_dashboard_report_snapshot([record], created_at="2026-05-01T12:00:00Z")
    markdown = snapshot.render_dashboard_report_snapshot_markdown(report)

    assert str(referenced) in markdown
    assert "overnight_manifest path" in markdown


def test_markdown_renderer_rejects_protected_private_markers():
    report = snapshot.build_dashboard_report_snapshot([_overnight_record()], created_at="2026-05-01T12:00:00Z")
    report["records"][0]["summary"] = "Legal private matter text must never render."

    with pytest.raises(snapshot.DashboardReportSnapshotRenderError):
        snapshot.render_dashboard_report_snapshot_markdown(report)


@pytest.mark.parametrize(
    "malformed_snapshot",
    [
        "not a snapshot",
        {},
        {"snapshot_type": "wrong", "schema_version": 1},
        {
            "snapshot_type": "openclaw.dashboard_report_snapshot",
            "schema_version": 1,
            "created_at": "2026-05-01T12:00:00Z",
            "total_records": 0,
            "status_counts": {},
            "severity_counts": {},
            "ready_count": 0,
            "blocked_count": 0,
            "requires_review_count": 0,
            "records": [],
            "top_issues": [],
            "execution_allowed": True,
            "service_wiring_allowed": False,
            "telegram_send_allowed": False,
            "dashboard_control_allowed": False,
        },
        {
            "snapshot_type": "openclaw.dashboard_report_snapshot",
            "schema_version": 1,
            "created_at": "2026-05-01T12:00:00Z",
            "total_records": 0,
            "status_counts": [],
            "severity_counts": {},
            "ready_count": 0,
            "blocked_count": 0,
            "requires_review_count": 0,
            "records": [],
            "top_issues": [],
            "execution_allowed": False,
            "service_wiring_allowed": False,
            "telegram_send_allowed": False,
            "dashboard_control_allowed": False,
        },
    ],
)
def test_markdown_renderer_malformed_snapshots_fail_closed(malformed_snapshot):
    with pytest.raises(snapshot.DashboardReportSnapshotRenderError):
        snapshot.render_dashboard_report_snapshot_markdown(malformed_snapshot)


def test_no_execution_no_discovery_no_service_control_import_guard(monkeypatch):
    source = inspect.getsource(snapshot)
    tree = ast.parse(source)
    imported_modules = set()
    called_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            called = node.func
            if isinstance(called, ast.Name):
                called_names.add(called.id)
            elif isinstance(called, ast.Attribute):
                called_names.add(called.attr)

    assert imported_modules <= {"__future__", "json", "pathlib", "re", "typing"}
    assert not {
        "glob",
        "iglob",
        "iterdir",
        "read_text",
        "request",
        "run",
        "system",
        "urlopen",
        "walk",
    } & called_names
    assert "sync_legal_planning_to_mac" not in source

    forbidden_modules = {
        "cassandra_briefing_brain",
        "chief_end_of_day_worker",
        "chief_llm",
        "codex",
        "gmail",
        "googleapiclient",
        "hermes",
        "legal",
        "mcp",
        "openai",
        "openrouter",
        "requests",
        "service",
        "smtplib",
        "subprocess",
        "systemd",
        "telegram",
        "urllib",
    }
    sys.modules.pop("dashboard_report_snapshot", None)
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        assert name.split(".")[0] not in forbidden_modules
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    try:
        imported = importlib.import_module("dashboard_report_snapshot")
        assert imported.DASHBOARD_REPORT_SNAPSHOT_SCHEMA_VERSION == 1
    finally:
        sys.modules["dashboard_report_snapshot"] = snapshot