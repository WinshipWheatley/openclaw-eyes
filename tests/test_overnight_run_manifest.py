import ast
import builtins
import copy
import inspect
import sys

import overnight_run_manifest as orm
from overnight_run_manifest import build_overnight_run_manifest, check_overnight_run_manifest


def _valid_inputs(**overrides):
    data = {
        "cycle_date": "2026-04-30",
        "eod_review": {
            "artifact_ref": "/mnt/c/OpenClaw/logs/chief_end_of_day/2026-04-30.json",
            "status": "completed",
            "available": True,
            "started_at": "2026-04-30T01:00:00-04:00",
            "finished_at": "2026-04-30T01:01:00-04:00",
            "proposal_count": 1,
        },
        "eod_harness": {
            "artifact_ref": "/home/openclaw/staging/chief_eod_harness/runs/20260430T010000/manifest.json",
            "status": "passed",
            "harness_name": "chief_eod_harness",
            "flow": "chief_end_of_day_review",
            "passed": 5,
            "failed": 0,
            "total_cases": 5,
        },
        "proposal_promotion": {
            "artifact_ref": "/mnt/c/OpenClaw/logs/agent_task_proposals.json",
            "status": "promoted",
            "proposal_ids": ["ATP-CHIEF-20260430-001"],
            "promoted_task_ids": ["atp-chief-20260430-001-morning-brief-harness-retest"],
        },
        "morning_synthesis": {
            "artifact_ref": "/mnt/c/OpenClawShared/openclaw-vault/System/Chief Morning Synthesis.md",
            "status": "fresh",
            "available": True,
            "freshness": "fresh: source last changed 2026-04-30T05:00:00-04:00",
            "generated_at": "2026-04-30T05:00:00-04:00",
        },
        "guardian_status": {
            "artifact_ref": "/mnt/c/OpenClaw/logs/approval_pending.json",
            "status": "clear",
            "approval_pending": False,
        },
        "issues": [
            {
                "id": "operator-note",
                "severity": "low",
                "title": "Operator note carried for dashboard drill-down.",
                "source_artifact": "synthetic-note",
                "recommended_next_action": "Review during morning standup.",
            }
        ],
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            merged = dict(data[key])
            merged.update(value)
            data[key] = merged
        else:
            data[key] = value
    return data


def test_valid_synthetic_inputs_produce_deterministic_manifest_output():
    inputs = _valid_inputs()

    first = build_overnight_run_manifest(inputs, created_at="2026-04-30T06:00:00Z")
    second = build_overnight_run_manifest(inputs, created_at="2026-04-30T06:00:00Z")

    assert first == second
    assert first["manifest_type"] == "openclaw.overnight_run_manifest"
    assert first["schema_version"] == 1
    assert first["cycle_date"] == "2026-04-30"
    assert first["ready_for_morning_synthesis"] is True
    assert first["ready_for_service_timer_wiring"] is False
    assert first["blockers"] == []
    assert check_overnight_run_manifest(first) == {"passed": True, "violations": []}


def test_missing_eod_artifact_fails_closed():
    inputs = _valid_inputs(eod_review={"artifact_ref": "", "available": False})

    manifest = build_overnight_run_manifest(inputs, created_at="2026-04-30T06:00:00Z")

    assert manifest["ready_for_morning_synthesis"] is False
    assert manifest["execution_allowed"] is False
    assert manifest["service_wiring_allowed"] is False
    assert manifest["blockers"]
    blocker = manifest["blockers"][0]
    assert blocker["id"] == "overnight-20260430-eod-review-missing"
    assert blocker["severity"] == "high"
    assert blocker["source_artifact"] == "eod_review"
    assert "Chief EOD review" in blocker["title"]
    assert check_overnight_run_manifest(manifest)["passed"] is True


def test_stale_or_missing_chief_morning_synthesis_marks_readiness_false():
    stale = build_overnight_run_manifest(
        _valid_inputs(morning_synthesis={"freshness": "stale: source last changed yesterday"}),
        created_at="2026-04-30T06:00:00Z",
    )
    missing = build_overnight_run_manifest(
        _valid_inputs(morning_synthesis={"artifact_ref": "", "available": False, "status": "missing"}),
        created_at="2026-04-30T06:00:00Z",
    )

    assert stale["ready_for_morning_synthesis"] is False
    assert missing["ready_for_morning_synthesis"] is False
    assert {blocker["id"] for blocker in stale["blockers"]} == {"overnight-20260430-morning-synthesis-stale"}
    assert {blocker["id"] for blocker in missing["blockers"]} == {"overnight-20260430-morning-synthesis-missing"}


def test_harness_failures_surface_as_structured_blockers():
    inputs = _valid_inputs(eod_harness={"status": "failed", "passed": 4, "failed": 1, "total_cases": 5})

    manifest = build_overnight_run_manifest(inputs, created_at="2026-04-30T06:00:00Z")

    assert manifest["ready_for_morning_synthesis"] is False
    assert manifest["blockers"] == [
        {
            "id": "overnight-20260430-eod-harness-failed",
            "severity": "high",
            "title": "EOD harness evidence reported one or more failed checks.",
            "source_artifact": "/home/openclaw/staging/chief_eod_harness/runs/20260430T010000/manifest.json",
            "recommended_next_action": "Inspect the referenced EOD harness manifest and resolve failed checks before relying on the overnight cycle.",
            "blocking_readiness": True,
        }
    ]
    assert manifest["blockers"][0] in manifest["issues"]


def test_approval_pending_state_remains_metadata_only():
    inputs = _valid_inputs(guardian_status={"status": "pending", "approval_pending": True, "approval_id": "GUARD-1"})

    manifest = build_overnight_run_manifest(inputs, created_at="2026-04-30T06:00:00Z")

    assert manifest["guardian_status"] == {
        "artifact_ref": "/mnt/c/OpenClaw/logs/approval_pending.json",
        "status": "pending",
        "approval_pending": True,
        "approval_id": "GUARD-1",
        "metadata_only": True,
        "action_triggered": False,
    }
    assert manifest["ready_for_morning_synthesis"] is True
    assert not any("approval" in blocker["id"] for blocker in manifest["blockers"])


def test_input_dictionaries_are_not_mutated():
    inputs = _valid_inputs(guardian_status={"status": "pending", "approval_pending": True})
    original = copy.deepcopy(inputs)

    build_overnight_run_manifest(inputs, created_at="2026-04-30T06:00:00Z")

    assert inputs == original


def test_issue_entries_include_dashboard_friendly_fields():
    inputs = _valid_inputs(eod_harness={"status": "failed", "failed": 1})

    manifest = build_overnight_run_manifest(inputs, created_at="2026-04-30T06:00:00Z")

    required = {"id", "severity", "title", "source_artifact", "recommended_next_action"}

    assert manifest["issues"]
    for issue in manifest["issues"]:
        assert required <= set(issue)
        assert issue["id"].startswith("overnight-20260430-")
        assert issue["severity"] in {"low", "medium", "high", "critical"}
        assert issue["source_artifact"]
        assert issue["recommended_next_action"]


def test_execution_and_service_wiring_flags_are_always_false():
    valid = build_overnight_run_manifest(_valid_inputs(), created_at="2026-04-30T06:00:00Z")
    invalid = build_overnight_run_manifest("not a dict", created_at="2026-04-30T06:00:00Z")

    assert valid["execution_allowed"] is False
    assert valid["service_wiring_allowed"] is False
    assert valid["ready_for_service_timer_wiring"] is False
    assert invalid["execution_allowed"] is False
    assert invalid["service_wiring_allowed"] is False
    assert invalid["ready_for_service_timer_wiring"] is False


def test_checker_rejects_invalid_shape_and_execution_flags():
    manifest = build_overnight_run_manifest(_valid_inputs(), created_at="2026-04-30T06:00:00Z")
    manifest["execution_allowed"] = True
    manifest["service_wiring_allowed"] = True
    manifest["ready_for_service_timer_wiring"] = True
    manifest["created_at"] = "not-a-timestamp"
    manifest["issues"] = [{"id": "bad", "severity": "loud"}]

    check = check_overnight_run_manifest(manifest)

    assert check["passed"] is False
    assert "execution_allowed_must_be_false" in check["violations"]
    assert "service_wiring_allowed_must_be_false" in check["violations"]
    assert "ready_for_service_timer_wiring_must_be_false" in check["violations"]
    assert "invalid_created_at" in check["violations"]
    assert "issue_0_invalid_severity" in check["violations"]
    assert "issue_0_missing_source_artifact" in check["violations"]
    assert "issue_0_missing_recommended_next_action" in check["violations"]


def test_overnight_manifest_module_has_no_forbidden_imports_or_runtime_calls(monkeypatch):
    source = inspect.getsource(orm)
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

    assert imported_modules <= {"__future__", "datetime", "typing"}
    assert "open" not in called_names
    assert "read_text" not in called_names
    assert "write_text" not in called_names
    assert "eval" not in called_names
    assert "exec" not in called_names
    assert "os.environ" not in source
    assert "getenv" not in source
    assert "OPENROUTER_API_KEY" not in source

    forbidden_modules = {
        "builder_watcher",
        "cassandra_briefing_scheduler",
        "cassandra_sender",
        "chief_end_of_day_worker",
        "chief_llm",
        "chief_notify",
        "chief_sender",
        "codex",
        "gmail",
        "googleapiclient",
        "hermes",
        "mcp",
        "openai",
        "openrouter",
        "os",
        "requests",
        "runner_profiles",
        "runner_registry",
        "run_agent",
        "service",
        "smtplib",
        "subprocess",
        "systemd",
        "telegram",
        "urllib",
    }
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        assert name.split(".")[0] not in forbidden_modules
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    manifest = build_overnight_run_manifest(_valid_inputs(), created_at="2026-04-30T06:00:00Z")

    assert manifest["execution_allowed"] is False
    assert manifest["service_wiring_allowed"] is False
    assert "overnight_run_manifest" in sys.modules