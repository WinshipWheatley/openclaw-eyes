import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

import operator_action
from operator_action import build_operator_actions_read_model, execute_operator_action
from operator_action import export_operator_actions_read_model
from operator_action_inbox import (
    DEFAULT_OPERATOR_ACTION_INBOX,
    INBOX_SCHEMA_VERSION,
    import_operator_action_request_file,
    import_operator_action_requests,
    operator_action_inbox_table_names,
    stable_json,
)
from scripts.import_operator_action_request import main as import_main
from scripts.query_operator_action_inbox import main as query_main


def _request_payload(**overrides):
    payload = {
        "schema_version": INBOX_SCHEMA_VERSION,
        "request_id": "fixture_refresh_report_bridge",
        "action_type": "export_report_bridge_read_model",
        "requested_by": "mission_control",
        "reason": "Refresh report bridge read-model",
        "created_at": "2026-05-14T23:50:00+00:00",
        "source": {
            "node_id": "mac_mission_control",
            "host_kind": "mac",
            "drop_path": "/Volumes/openclaw_e/operator_actions/inbox",
        },
        "authority": {
            "approval_required": True,
            "auto_approve": False,
            "execute_immediately": False,
            "arbitrary_shell_allowed": False,
            "runtime_activation_allowed": False,
            "agent_activation_allowed": False,
            "docker_allowed": False,
            "ollama_allowed": False,
            "network_allowed": False,
            "remote_control_allowed": False,
            "client_deployment_allowed": False,
            "file_delete_allowed": False,
            "file_move_allowed": False,
        },
    }
    for key, value in overrides.items():
        if key == "authority":
            payload["authority"].update(value)
        elif key == "source":
            payload["source"].update(value)
        else:
            payload[key] = value
    return payload


def _write_request(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")
    return path


def test_schema_initializes(tmp_path):
    tables = set(operator_action_inbox_table_names(tmp_path / "ledger.sqlite"))

    assert {
        "operator_action_inbox_imports",
        "operator_action_inbox_rejections",
    } <= tables


def test_valid_request_imports_pending_action_and_cannot_execute_without_approval(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    request_path = _write_request(tmp_path / "inbox" / "valid.json", _request_payload())

    item = import_operator_action_request_file(file_path=request_path, db_path=db_path)

    assert item.status == "imported"
    assert item.action_id == "opact_inbox_fixture_refresh_report_bridge"
    with pytest.raises(ValueError, match="must be approved"):
        execute_operator_action(action_id=item.action_id, db_path=db_path)

    conn = sqlite3.connect(db_path)
    try:
        request = conn.execute(
            "SELECT status, approval_required FROM operator_action_requests WHERE action_id = ?",
            (item.action_id,),
        ).fetchone()
        imported = conn.execute(
            "SELECT status, execution_started FROM operator_action_inbox_imports"
        ).fetchone()
    finally:
        conn.close()
    assert request == ("requested", 1)
    assert imported == ("imported", 0)


def test_dangerous_or_invalid_requests_are_rejected(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    cases = {
        "unknown_action.json": _request_payload(
            request_id="unknown_action",
            action_type="run_anything",
        ),
        "auto_approve.json": _request_payload(
            request_id="auto_approve",
            authority={"auto_approve": True},
        ),
        "execute_immediately.json": _request_payload(
            request_id="execute_immediately",
            authority={"execute_immediately": True},
        ),
        "network_allowed.json": _request_payload(
            request_id="network_allowed",
            authority={"network_allowed": True},
        ),
        "command_string.json": _request_payload(
            request_id="command_string",
            command="python3 -c 'print(1)'",
        ),
    }

    results = []
    for filename, payload in cases.items():
        results.append(
            import_operator_action_request_file(
                file_path=_write_request(tmp_path / "bad" / filename, payload),
                db_path=db_path,
                import_run_id="bad_request_run",
            )
        )

    assert all(item.status == "rejected" for item in results)
    assert any("unknown allowlisted action_type" in item.rejection_reason for item in results)
    assert any("auto_approve" in item.rejection_reason for item in results)
    assert any("execute_immediately" in item.rejection_reason for item in results)
    assert any("network_allowed" in item.rejection_reason for item in results)
    assert any("forbidden command/control key" in item.rejection_reason for item in results)

    conn = sqlite3.connect(db_path)
    try:
        action_count = conn.execute("SELECT COUNT(*) FROM operator_action_requests").fetchone()[0]
        rejection_count = conn.execute(
            "SELECT COUNT(*) FROM operator_action_inbox_rejections"
        ).fetchone()[0]
    finally:
        conn.close()
    assert action_count == 0
    assert rejection_count == len(cases)


def test_malformed_json_is_rejected(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    request_path = tmp_path / "inbox" / "malformed.json"
    request_path.parent.mkdir(parents=True, exist_ok=True)
    request_path.write_text("{not json", encoding="utf-8")

    item = import_operator_action_request_file(file_path=request_path, db_path=db_path)

    assert item.status == "rejected"
    assert "malformed JSON" in item.rejection_reason


def test_inbox_import_cli_and_query_work_without_execution(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "ledger.sqlite"
    inbox = tmp_path / "inbox"
    _write_request(
        inbox / "valid.json",
        _request_payload(request_id="cli_valid", action_type="query_generated_read_model_mirror"),
    )
    _write_request(
        inbox / "bad.json",
        _request_payload(request_id="cli_bad", authority={"docker_allowed": True}),
    )

    def fail_if_executed(*args, **kwargs):
        raise AssertionError("inbox import must not execute subprocess commands")

    monkeypatch.setattr(operator_action.subprocess, "run", fail_if_executed)

    exit_code = import_main(
        [
            "--db",
            str(db_path),
            "--inbox",
            str(inbox),
            "--import-run-id",
            "cli_inbox_run",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["imported_request_count"] == 1
    assert payload["rejected_request_count"] == 1
    assert payload["no_execution_occurred"] is True
    assert payload["approval_still_required"] is True
    assert payload["action_ids"] == ["opact_inbox_cli_valid"]

    query_main(["--db", str(db_path), "--report", "summary", "--format", "operator"])
    output = capsys.readouterr().out
    assert "Operator Action Inbox v0 - summary" in output
    assert "Imported: 1" in output
    assert "Rejected: 1" in output


def test_operator_actions_read_model_reflects_imported_pending_request(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"
    request_path = _write_request(
        tmp_path / "inbox" / "pending.json",
        _request_payload(request_id="pending_read_model", action_type="prepare_mac_read_model_shuttle"),
    )

    import_operator_action_request_file(file_path=request_path, db_path=db_path)
    summary = export_operator_actions_read_model(db_path=db_path, export_root=export_root)
    payload = build_operator_actions_read_model(db_path=db_path)

    assert summary["request_count"] == 1
    assert payload["pending_approval_count"] == 1
    assert payload["completed_count"] == 0
    assert payload["latest_action"]["action_id"] == "opact_inbox_pending_read_model"
    assert (export_root / "operator_actions.json").is_file()
    assert (export_root / "operator_actions_OPERATOR.md").is_file()


def test_default_inbox_uses_e_drive_not_c_drive():
    assert DEFAULT_OPERATOR_ACTION_INBOX.as_posix() == "/mnt/e/openclaw/operator_actions/inbox"
    assert not DEFAULT_OPERATOR_ACTION_INBOX.as_posix().startswith("/mnt/c/openclaw")


def test_static_forbids_for_operator_action_inbox_lane():
    paths = [
        Path("operator_action_inbox.py"),
        Path("scripts/import_operator_action_request.py"),
        Path("scripts/query_operator_action_inbox.py"),
    ]
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in paths)
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
        "ollama pull",
        "apt install",
        "npm install",
        "pip install",
        "git clone",
        ".unlink(",
        ".remove(",
        ".rmdir(",
        ".rename(",
    ]
    for token in forbidden:
        assert token not in text
