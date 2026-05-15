import json
import sqlite3
from pathlib import Path

from agent_runtime_readiness import (
    NO_AUTHORITY_FLAGS,
    REQUIRED_AGENT_IDS,
    agent_runtime_readiness_table_names,
    build_agent_runtime_readiness,
    build_agent_runtime_readiness_report,
    export_agent_runtime_readiness_read_model,
    run_agent_smoke_tests,
    run_agent_start_sequence,
)
from scripts.check_agent_runtime_readiness import main as check_main
from scripts.export_agent_runtime_readiness_read_model import main as export_main
from scripts.query_agent_runtime_readiness import main as query_main
from scripts.run_agent_smoke_tests import main as smoke_main
from scripts.run_agent_start_sequence import main as start_main


def _row(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def _rows(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_schema_initializes(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    assert {
        "agent_runtime_readiness_runs",
        "agent_runtime_components",
        "agent_runtime_checks",
        "agent_runtime_blockers",
        "agent_runtime_smoke_tests",
        "agent_runtime_start_sequence_steps",
        "agent_runtime_receipts",
    } <= agent_runtime_readiness_table_names(db_path)


def test_readiness_build_represents_required_agents_and_no_authority(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    result = build_agent_runtime_readiness(db_path=db_path, run_id="runtime_readiness_fixture")

    assert result.agent_count == len(REQUIRED_AGENT_IDS)
    assert result.ready_for_dry_run_count == len(REQUIRED_AGENT_IDS)
    assert result.blocked_count == 0
    rows = _rows(
        db_path,
        """
SELECT agent_id, registered_in_agent_lane_registry, readiness_status,
       telegram_wired, can_execute_directly, can_bypass_approval,
       can_read_no_go_raw
FROM agent_runtime_components
WHERE run_id = 'runtime_readiness_fixture'
ORDER BY agent_id
""",
    )
    assert {row["agent_id"] for row in rows} == set(REQUIRED_AGENT_IDS)
    assert all(row["registered_in_agent_lane_registry"] == 1 for row in rows)
    assert all(row["readiness_status"] == "ready_for_dry_run" for row in rows)
    assert all(row["telegram_wired"] == 0 for row in rows)
    assert all(row["can_execute_directly"] == 0 for row in rows)
    assert all(row["can_bypass_approval"] == 0 for row in rows)
    assert all(row["can_read_no_go_raw"] == 0 for row in rows)
    run = _row(
        db_path,
        """
SELECT live_agent_activation_allowed, autonomous_loop_allowed, telegram_api_allowed,
       gmail_api_allowed, model_call_allowed, arbitrary_shell_allowed,
       tool_execution_allowed, approval_bypass_allowed, no_go_raw_access_allowed,
       client_deployment_allowed
FROM agent_runtime_readiness_runs
WHERE run_id = 'runtime_readiness_fixture'
""",
    )
    assert tuple(run) == (0, 0, 0, 0, 0, 0, 0, 0, 0, 0)


def test_start_sequence_is_dry_run_and_records_steps(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    result = run_agent_start_sequence(
        db_path=db_path,
        dry_run=True,
        run_id="runtime_start_fixture",
    )

    assert result.dry_run is True
    assert result.block_count == 0
    assert result.pass_count >= 8
    steps = {
        row["step_name"]: row
        for row in _rows(
            db_path,
            "SELECT step_name, status, summary FROM agent_runtime_start_sequence_steps WHERE run_id = ?",
            (result.run_id,),
        )
    }
    assert "ledger_reachable" in steps
    assert "agent_no_authority_bounds" in steps
    assert steps["agent_no_authority_bounds"]["status"] == "pass"
    receipt = _row(
        db_path,
        "SELECT summary FROM agent_runtime_receipts WHERE run_id = ? AND receipt_kind = 'start_sequence'",
        (result.run_id,),
    )
    assert "no agents were activated" in receipt["summary"]


def test_smoke_tests_route_agents_without_execution(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    result = run_agent_smoke_tests(db_path=db_path, run_id="runtime_smoke_fixture")

    assert result.smoke_test_count == 6
    assert result.passed_count == 6
    assert result.failed_count == 0
    rows = _rows(
        db_path,
        """
SELECT agent_id, routed_agent_id, intent_status, pass_fail,
       no_execution_occurred, no_external_api_called
FROM agent_runtime_smoke_tests
WHERE run_id = 'runtime_smoke_fixture'
""",
    )
    assert {row["agent_id"] for row in rows} >= {
        "chief",
        "cassandra",
        "guardian",
        "niles",
        "hermes",
        "report_bridge",
    }
    assert all(row["pass_fail"] == "pass" for row in rows)
    assert all(row["no_execution_occurred"] == 1 for row in rows)
    assert all(row["no_external_api_called"] == 1 for row in rows)
    assert _row(db_path, "SELECT COUNT(*) AS count FROM operator_action_requests")["count"] == 0


def test_reports_and_scripts_work(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"

    assert check_main(["--db", str(db_path), "--run-id", "runtime_report_fixture", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["counts"]["agent_count"] == len(REQUIRED_AGENT_IDS)

    assert start_main(["--db", str(db_path), "--run-id", "runtime_start_script", "--dry-run"]) == 0
    assert "Overall status" in capsys.readouterr().out

    assert smoke_main(["--db", str(db_path), "--run-id", "runtime_smoke_script"]) == 0
    assert "Passed: 6" in capsys.readouterr().out

    assert query_main(["--db", str(db_path), "--report", "smoke-tests"]) == 0
    assert "Agent Runtime Readiness v0" in capsys.readouterr().out


def test_read_model_export_contains_blockers_smoke_results_and_no_authority(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"

    run_agent_start_sequence(db_path=db_path, dry_run=True, run_id="runtime_export_fixture")
    run_agent_smoke_tests(db_path=db_path, run_id="runtime_export_fixture")
    summary = export_agent_runtime_readiness_read_model(
        db_path=db_path,
        export_root=export_root,
        run_id="runtime_export_fixture",
    )
    assert export_main(
        [
            "--db",
            str(db_path),
            "--export-root",
            str(export_root),
            "--run-id",
            "runtime_export_fixture",
            "--format",
            "json",
        ]
    ) == 0
    script_summary = json.loads(capsys.readouterr().out)

    json_path = export_root / "agent_runtime_readiness.json"
    operator_path = export_root / "agent_runtime_readiness_OPERATOR.md"
    read_model = json.loads(json_path.read_text(encoding="utf-8"))
    assert summary["agent_count"] == len(REQUIRED_AGENT_IDS)
    assert script_summary["agent_count"] == len(REQUIRED_AGENT_IDS)
    assert read_model["agent_count"] == len(REQUIRED_AGENT_IDS)
    assert read_model["smoke_test_results"]["passed"] == 6
    assert "next_safe_morning_tests" in read_model
    assert read_model["blockers"]
    assert operator_path.exists()
    assert "not live agent activation" in operator_path.read_text(encoding="utf-8")
    for key, value in NO_AUTHORITY_FLAGS.items():
        assert read_model[key] is value
        assert read_model["no_authority_flags"][key] is value


def test_no_runtime_network_or_destructive_behavior_in_new_lane_files():
    text = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "agent_runtime_readiness.py",
            "scripts/check_agent_runtime_readiness.py",
            "scripts/query_agent_runtime_readiness.py",
            "scripts/export_agent_runtime_readiness_read_model.py",
            "scripts/run_agent_start_sequence.py",
            "scripts/run_agent_smoke_tests.py",
        ]
    )
    forbidden = [
        "import subprocess",
        "subprocess.",
        "shell=true",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "paramiko",
        "rsync",
        "scp ",
        "ssh ",
        "docker run",
        "ollama run",
        "apt install",
        "npm install",
        "pip install",
        ".unlink(",
        ".remove(",
        ".rmdir(",
        ".rename(",
    ]
    for token in forbidden:
        assert token not in text
    assert all(value is False for value in NO_AUTHORITY_FLAGS.values())
