import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

import operator_action
from operator_action import (
    ALLOWED_ACTIONS,
    NO_AUTHORITY_FLAGS,
    approve_operator_action,
    build_operator_action_report,
    build_operator_actions_read_model,
    execute_operator_action,
    export_operator_actions_read_model,
    init_operator_action_schema,
    operator_action_table_names,
    request_operator_action,
)
from scripts.approve_operator_action import main as approve_main
from scripts.execute_operator_action import main as execute_main
from scripts.export_operator_actions_read_model import main as export_main
from scripts.query_operator_actions import main as query_main
from scripts.request_operator_action import main as request_main


def test_schema_initializes_and_allowed_actions_seed_idempotently(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    tables = set(operator_action_table_names(db_path))

    assert {
        "operator_action_requests",
        "operator_action_approvals",
        "operator_action_executions",
        "operator_action_receipts",
        "operator_action_allowed_commands",
        "operator_action_rejections",
    } <= tables

    init_operator_action_schema(db_path)
    conn = sqlite3.connect(db_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM operator_action_allowed_commands").fetchone()[0]
        enabled = conn.execute(
            "SELECT COUNT(*) FROM operator_action_allowed_commands WHERE enabled = 1"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == len(ALLOWED_ACTIONS)
    assert enabled == len(ALLOWED_ACTIONS)


def test_request_created_and_unknown_action_rejected(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    result = request_operator_action(
        action_id="opact_fixture_request",
        action_type="export_report_bridge_read_model",
        requested_by="operator",
        reason="Refresh report bridge read-model.",
        db_path=db_path,
    )

    assert result.status == "requested"
    assert result.validation_status == "allowlisted"
    assert result.approval_required is True
    assert result.request_receipt_id == "opact_approval_request_opact_fixture_request"

    rejected = request_operator_action(
        action_id="opact_bad_request",
        action_type="run_arbitrary_command",
        requested_by="operator",
        reason="Should be rejected.",
        db_path=db_path,
    )
    assert rejected.status == "rejected"
    assert rejected.validation_status == "rejected"
    assert "unknown operator action type" in rejected.rejection_reason

    report = build_operator_action_report(db_path=db_path, report="rejections")
    assert report["counts"]["rejected"] == 1
    assert report["items"][0]["action_type"] == "run_arbitrary_command"


def test_action_cannot_execute_before_explicit_approval(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    request_operator_action(
        action_id="opact_no_approval",
        action_type="export_context_selection_read_model",
        requested_by="operator",
        reason="Try to execute without approval.",
        db_path=db_path,
    )

    with pytest.raises(ValueError, match="must be approved"):
        execute_operator_action(action_id="opact_no_approval", db_path=db_path)


def test_approval_is_explicit_and_execution_uses_allowlisted_command_array(tmp_path, monkeypatch):
    db_path = tmp_path / "ledger.sqlite"
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        assert command == list(ALLOWED_ACTIONS["export_report_bridge_read_model"].command)
        assert kwargs["shell"] is False
        assert kwargs["env"] == {"PYTHONDONTWRITEBYTECODE": "1"}
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        return subprocess.CompletedProcess(command, 0, stdout="export ok\n", stderr="")

    monkeypatch.setattr(operator_action.subprocess, "run", fake_run)

    request_operator_action(
        action_id="opact_execute_ok",
        action_type="export_report_bridge_read_model",
        requested_by="operator",
        reason="Refresh report bridge read-model.",
        db_path=db_path,
    )
    approval = approve_operator_action(
        action_id="opact_execute_ok",
        approved_by="operator",
        approval_note="Approved bounded read-model refresh.",
        db_path=db_path,
    )
    execution = execute_operator_action(action_id="opact_execute_ok", db_path=db_path)

    assert approval.status == "approved"
    assert execution.status == "completed"
    assert execution.exit_code == 0
    assert execution.receipt_id == "opreceipt_opact_execute_ok"
    assert calls

    conn = sqlite3.connect(db_path)
    try:
        status = conn.execute(
            "SELECT status FROM operator_action_requests WHERE action_id = ?",
            ("opact_execute_ok",),
        ).fetchone()[0]
        receipt = conn.execute(
            "SELECT result, stdout_excerpt FROM operator_action_receipts WHERE receipt_id = ?",
            ("opreceipt_opact_execute_ok",),
        ).fetchone()
    finally:
        conn.close()
    assert status == "completed"
    assert receipt[0] == "completed"
    assert "export ok" in receipt[1]


def test_failed_command_is_recorded_not_hidden(tmp_path, monkeypatch):
    db_path = tmp_path / "ledger.sqlite"

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 7, stdout="", stderr="fixture failure\n")

    monkeypatch.setattr(operator_action.subprocess, "run", fake_run)
    request_operator_action(
        action_id="opact_execute_failed",
        action_type="query_generated_read_model_mirror",
        requested_by="operator",
        reason="Query mirror status.",
        db_path=db_path,
    )
    approve_operator_action(
        action_id="opact_execute_failed",
        approved_by="operator",
        approval_note="Approved bounded mirror query.",
        db_path=db_path,
    )

    execution = execute_operator_action(action_id="opact_execute_failed", db_path=db_path)

    assert execution.status == "failed"
    assert execution.exit_code == 7
    assert "fixture failure" in execution.stderr_text
    read_model = build_operator_actions_read_model(db_path=db_path)
    assert read_model["failed_count"] == 1
    assert read_model["last_execution_receipt_summary"]["result"] == "failed"


def test_read_model_export_and_cli_reports_work(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(operator_action.subprocess, "run", fake_run)

    request_main(
        [
            "--db",
            str(db_path),
            "--action-id",
            "opact_cli",
            "--action-type",
            "export_context_selection_read_model",
            "--requested-by",
            "operator",
            "--reason",
            "Refresh context read-model.",
            "--format",
            "json",
        ]
    )
    assert json.loads(capsys.readouterr().out)["status"] == "requested"

    approve_main(
        [
            "--db",
            str(db_path),
            "--action-id",
            "opact_cli",
            "--approved-by",
            "operator",
            "--approval-note",
            "Approved bounded export.",
            "--format",
            "json",
        ]
    )
    assert json.loads(capsys.readouterr().out)["status"] == "approved"

    execute_main(["--db", str(db_path), "--action-id", "opact_cli", "--format", "json"])
    assert json.loads(capsys.readouterr().out)["status"] == "completed"

    summary = export_operator_actions_read_model(db_path=db_path, export_root=export_root)
    json_path = export_root / "operator_actions.json"
    markdown_path = export_root / "operator_actions_OPERATOR.md"
    assert json_path.is_file()
    assert markdown_path.is_file()
    assert summary["request_count"] == 1

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "operator_actions_read_model_v0"
    assert payload["latest_action"]["action_id"] == "opact_cli"
    assert payload["completed_count"] == 1
    assert payload["pending_approval_count"] == 0
    assert payload["last_execution_receipt_summary"]["result"] == "completed"
    assert all(value is False for value in payload["authority_flags"].values())
    assert "bounded backend actions" in markdown_path.read_text(encoding="utf-8")

    query_main(["--db", str(db_path), "--report", "allowed", "--format", "operator"])
    assert "Operator Action Path v0 - allowed" in capsys.readouterr().out
    query_main(["--db", str(db_path), "--report", "summary", "--format", "operator"])
    summary_output = capsys.readouterr().out
    assert "Operator Action Path v0 - summary" in summary_output
    assert "opact_cli export_context_selection_read_model: completed" in summary_output

    export_main(["--db", str(db_path), "--export-root", str(export_root), "--format", "json"])
    cli_export = json.loads(capsys.readouterr().out)
    assert cli_export["json_path"].endswith("operator_actions.json")


def test_no_authority_flags_are_false():
    assert all(value is False for value in NO_AUTHORITY_FLAGS.values())
    for action in ALLOWED_ACTIONS.values():
        assert isinstance(action.command, tuple)
        assert action.command[0] == "python3"
        assert all(" " not in part for part in action.command)
        assert "|" not in action.command
        assert "&&" not in action.command


def test_static_forbids_for_operator_action_lane():
    paths = [
        Path("operator_action.py"),
        Path("scripts/request_operator_action.py"),
        Path("scripts/approve_operator_action.py"),
        Path("scripts/execute_operator_action.py"),
        Path("scripts/query_operator_actions.py"),
        Path("scripts/export_operator_actions_read_model.py"),
    ]
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in paths)
    forbidden_source_tokens = [
        "shell=true",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
    ]
    for token in forbidden_source_tokens:
        assert token not in text

    forbidden_command_fragments = [
        "docker run",
        "ollama run",
        "ollama pull",
        " ssh ",
        " scp ",
        "rsync",
        "apt install",
        "npm install",
        "pip install",
        "git clone",
        " rm ",
        " mv ",
    ]
    command_text = "\n".join(
        " ".join(action.command).lower() for action in ALLOWED_ACTIONS.values()
    )
    for token in forbidden_command_fragments:
        assert token not in command_text
