from __future__ import annotations

import ast
import builtins
import importlib
import inspect
import json
import sys
from pathlib import Path

import pytest

import dashboard_evidence_adapter as adapter


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_loop_status_normalizes_to_dashboard_record(tmp_path):
    path = _write_json(
        tmp_path / "status.json",
        {
            "status": "blocked",
            "task_name": "dashboard-contract",
            "pass": 2,
            "block_reason": "chief_insufficient_evidence",
            "last_updated": "2026-04-30T05:00:00",
        },
    )

    record = adapter.normalize_dashboard_artifact(path)

    assert record["schema_version"] == adapter.DASHBOARD_RECORD_SCHEMA_VERSION
    assert record["record_type"] == "dashboard_card"
    assert record["artifact_type"] == "loop_status"
    assert record["artifact_id"] == "polish_loop_status"
    assert record["generated_at"] == "2026-04-30T05:00:00"
    assert record["status"] == "blocked"
    assert record["severity"] == "error"
    assert "chief_insufficient_evidence" in record["summary"]
    assert record["drilldown_refs"] == [
        {"label": "source_artifact", "reference_type": "path", "path": str(path)}
    ]


@pytest.mark.parametrize(
    ("harness_name", "task_name"),
    [
        ("chief_eod_harness", "chief_end_of_day_review"),
        ("morning_brief_harness", "morning_brief"),
    ],
)
def test_harness_manifest_normalizes_to_card_and_checks(tmp_path, harness_name, task_name):
    path = _write_json(
        tmp_path / harness_name / "manifest.json",
        {
            "harness_name": harness_name,
            "task_name": task_name,
            "flow": task_name,
            "generated_at": "2026-04-30T05:00:00",
            "fixture_path": "fixtures/sample.json",
            "passed": 2,
            "failed": 0,
            "total_cases": 2,
            "checks": [
                {"name": "fixture_has_inputs", "passed": True, "detail": "fixture inputs are present"},
                {"name": "staging_only", "passed": True, "detail": "staging root only"},
            ],
        },
    )

    record = adapter.normalize_dashboard_artifact(path)

    assert record["artifact_type"] == "harness_manifest"
    assert record["artifact_id"] == f"{harness_name}:{task_name}:2026-04-30T05:00:00"
    assert record["status"] == "passed"
    assert record["severity"] == "ok"
    assert record["summary"] == "2/2 checks passed; 0 failed."
    assert {check["name"] for check in record["checks"]} == {"fixture_has_inputs", "staging_only"}
    assert {ref["label"] for ref in record["drilldown_refs"]} >= {"source_artifact", "fixture"}


def test_expert_job_manifest_normalizes_as_no_execution_metadata(tmp_path):
    path = _write_json(
        tmp_path / "expert-job.json",
        {
            "manifest_type": "external_expert.job_manifest",
            "schema_version": 1,
            "manifest_created_at": "2026-04-30T13:00:00Z",
            "packet_id": "expert-20260430-code-review",
            "task_type": "code_review",
            "selected_lane": "code_review",
            "runner_class": "external_expert",
            "execution_allowed": False,
            "approval_required": True,
            "checker_passed": True,
            "lane_policy_passed": True,
            "allowed_outputs": ["risk_summary"],
            "prompt_body": "Review synthetic public code.",
            "input_paths": ["dashboard_evidence_adapter.py"],
            "forbidden_paths": ["private-vaults"],
            "candidate_runner_metadata": {"candidate_runner": "codex", "metadata_only": True},
            "refusal_reason": "",
            "violations": [],
        },
    )

    record = adapter.normalize_dashboard_artifact(path)

    assert record["artifact_type"] == "expert_job_manifest"
    assert record["artifact_id"] == "expert-20260430-code-review"
    assert record["status"] == "approval_required"
    assert record["severity"] == "info"
    assert record["privacy_classification"] == "sanitized_or_public_metadata_only"
    assert {check["name"]: check["passed"] for check in record["checks"]} == {
        "packet_checker_passed": True,
        "lane_policy_passed": True,
        "execution_not_allowed": True,
    }
    assert any(ref["path"] == "dashboard_evidence_adapter.py" for ref in record["drilldown_refs"])


def test_cassandra_briefing_json_normalizes_to_delivery_card(tmp_path):
    path = _write_json(
        tmp_path / "2026-04-30_morning.json",
        {
            "slot": "morning",
            "date": "2026-04-30",
            "text": "Morning priorities are ready.",
            "generated_at": "2026-04-30T08:00:00",
            "delivered": False,
            "delivered_at": None,
            "pending_reason": "focus_mode",
        },
    )

    record = adapter.normalize_dashboard_artifact(path)

    assert record["artifact_type"] == "cassandra_briefing"
    assert record["artifact_id"] == "2026-04-30:morning"
    assert record["status"] == "pending"
    assert record["severity"] == "warning"
    assert record["summary"] == "focus_mode"
    assert record["checks"][0]["name"] == "brief_text_present"


def test_eod_review_json_normalizes_to_review_card(tmp_path):
    path = _write_json(
        tmp_path / "2026-04-30.json",
        {
            "started_at": "2026-04-30T01:00:00",
            "finished_at": "2026-04-30T01:01:00",
            "duration_ms": 60000,
            "summary": "Chief found one follow-up.",
            "findings": ["Retest the morning harness."],
            "proposal_ids": ["ATP-CHIEF-20260430-001"],
            "proposal_count": 1,
            "auto_promoted_task": "morning-brief-retest",
            "auto_promoted_proposal_id": "ATP-CHIEF-20260430-001",
            "structured_output_lane": "fallback",
            "fast_attempt_structured": False,
            "strong_attempt_structured": False,
            "empty_output_cause": "empty_or_unparseable_fast_and_strong",
        },
    )

    record = adapter.normalize_dashboard_artifact(path)

    assert record["artifact_type"] == "chief_eod_review"
    assert record["artifact_id"] == "chief_eod_review:2026-04-30"
    assert record["generated_at"] == "2026-04-30T01:01:00"
    assert record["status"] == "completed"
    assert record["severity"] == "warning"
    assert any(ref.get("id") == "ATP-CHIEF-20260430-001" for ref in record["drilldown_refs"])


def test_missing_artifact_returns_deterministic_error_record(tmp_path):
    path = tmp_path / "missing.json"

    record = adapter.normalize_dashboard_artifact(path)

    assert record["record_type"] == "artifact_error"
    assert record["artifact_type"] == "missing"
    assert record["artifact_id"] == "missing:missing.json"
    assert record["status"] == "missing"
    assert record["allowed_surfaces"] == []


def test_unknown_markdown_report_is_not_parsed_as_canonical_data(tmp_path, monkeypatch):
    path = tmp_path / "Daily Report.md"
    path.write_text("# Daily Report\n\nPrivate-ish human prose should not be parsed.\n", encoding="utf-8")
    original_read_text = Path.read_text

    def guarded_read_text(self, *args, **kwargs):
        if self == path:
            raise AssertionError("markdown report should not be read")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    record = adapter.normalize_dashboard_artifact(path)

    assert record["record_type"] == "unsupported_artifact"
    assert record["artifact_type"] == "unsupported"
    assert record["status"] == "unsupported"
    assert "Markdown reports are not canonical" in record["summary"]


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "../status.json",
        "staging/*/manifest.json",
        "/mnt/c/OpenClawLegalPrivate/matter.json",
        "/home/openclaw/.chief.env",
        "/home/openclaw/sidecars/hermes/session.json",
        "/mnt/c/OpenClaw/logs/orchestrator.log",
    ],
)
def test_unsafe_paths_are_rejected(unsafe_path):
    with pytest.raises(adapter.DashboardEvidencePathError):
        adapter.normalize_dashboard_artifact(unsafe_path)


def test_drilldown_references_are_preserved_without_file_reads(tmp_path, monkeypatch):
    referenced = tmp_path / "fixture.json"
    referenced.write_text('{"would": "fail if parsed"}', encoding="utf-8")
    manifest = _write_json(
        tmp_path / "manifest.json",
        {
            "harness_name": "morning_brief_harness",
            "task_name": "morning_brief",
            "generated_at": "2026-04-30T05:00:00",
            "fixture_path": str(referenced),
            "passed": 1,
            "failed": 0,
            "total_cases": 1,
            "checks": [{"name": "fixture_has_inputs", "passed": True, "detail": "ok"}],
        },
    )
    original_read_text = Path.read_text

    def guarded_read_text(self, *args, **kwargs):
        if self == referenced:
            raise AssertionError("drilldown reference should not be read")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    record = adapter.normalize_dashboard_artifact(manifest)

    assert any(ref.get("path") == str(referenced) for ref in record["drilldown_refs"])


def test_multiple_explicit_paths_are_normalized_without_discovery(tmp_path):
    status_path = _write_json(tmp_path / "status.json", {"status": "idle", "task_name": "none"})
    missing_path = tmp_path / "missing.json"

    records = adapter.normalize_dashboard_artifacts([status_path, missing_path])

    assert [record["artifact_type"] for record in records] == ["loop_status", "missing"]


def test_no_execution_no_network_import_guard(monkeypatch):
    source = inspect.getsource(adapter)
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
    assert not {"glob", "iglob", "iterdir", "walk", "urlopen", "request", "Popen", "run"} & called_names

    forbidden_modules = {
        "cassandra_briefing_brain",
        "chief_llm",
        "codex",
        "googleapiclient",
        "hermes",
        "openai",
        "openrouter",
        "requests",
        "smtplib",
        "subprocess",
        "telegram",
        "urllib",
    }
    sys.modules.pop("dashboard_evidence_adapter", None)
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        assert name.split(".")[0] not in forbidden_modules
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    try:
        imported = importlib.import_module("dashboard_evidence_adapter")
        assert imported.DASHBOARD_RECORD_SCHEMA_VERSION == 1
    finally:
        sys.modules["dashboard_evidence_adapter"] = adapter