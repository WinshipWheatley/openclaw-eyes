import json
import sqlite3
from pathlib import Path

from local_automation_registry import (
    NO_AUTHORITY_FLAGS,
    build_local_automation_report,
    local_automation_table_names,
    seed_local_automation_registry,
)


def test_local_automation_schema_initializes(tmp_path):
    db = tmp_path / "ledger.sqlite"

    tables = local_automation_table_names(db)

    assert "local_automation_runs" in tables
    assert "local_automation_tasks" in tables
    assert "local_automation_service_specs" in tables
    assert "local_automation_service_status" in tables
    assert "local_automation_receipts" in tables
    assert "local_automation_rejections" in tables


def test_seed_is_idempotent_and_creates_only_v0_tasks(tmp_path):
    db = tmp_path / "ledger.sqlite"

    first = seed_local_automation_registry(db_path=db, run_id="run_fixture")
    second = seed_local_automation_registry(db_path=db, run_id="run_fixture_2")

    assert first.task_count == 2
    assert second.task_count == 2
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute("SELECT task_id, machine, enabled_by_default FROM local_automation_tasks ORDER BY task_id").fetchall()
    finally:
        conn.close()
    assert rows == [
        ("read_model_mirror_mac_sync", "mac", 0),
        ("read_model_mirror_pc_import", "pc_wsl", 0),
    ]


def test_registry_tasks_have_no_runtime_or_arbitrary_authority(tmp_path):
    db = tmp_path / "ledger.sqlite"
    seed_local_automation_registry(db_path=db)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(row) for row in conn.execute("SELECT * FROM local_automation_tasks")]
    finally:
        conn.close()

    assert rows
    for row in rows:
        assert row["command_kind"] == "allowlisted_python_script"
        assert row["authority_scope"] == "local_maintenance_only"
        assert row["can_run_tools"] == 0
        assert row["can_execute_arbitrary_shell"] == 0
        assert row["can_call_network"] == 0
        assert row["can_run_docker"] == 0
        assert row["can_run_ollama"] == 0
        assert row["can_activate_runtime"] == 0
        assert row["can_activate_agents"] == 0


def test_report_includes_future_task_kinds_without_enabling_them(tmp_path):
    db = tmp_path / "ledger.sqlite"
    seed_local_automation_registry(db_path=db)

    report = build_local_automation_report(db_path=db, report="summary")

    assert report["task_count"] == 2
    assert report["counts_by_machine"] == {"mac": 1, "pc_wsl": 1}
    assert "file_event_snapshot_once" in report["future_task_kinds_supported_by_contract"]
    assert all(value is False for value in report["no_authority_flags"].values())
    assert report["no_authority_flags"] == NO_AUTHORITY_FLAGS


def test_registry_source_has_no_c_drive_or_forbidden_runtime_strings():
    text = Path("local_automation_registry.py").read_text(encoding="utf-8").lower()
    forbidden = [
        "/mnt/c/openclaw",
        "c:\\openclaw",
        "shell=true",
        "os.system",
        "docker run",
        "ollama run",
        "ollama pull",
        "apt install",
        "npm install",
        "pip install",
    ]
    for token in forbidden:
        assert token not in text
