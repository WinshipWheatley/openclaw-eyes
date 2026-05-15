import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

import operator_action
from operator_action import approve_operator_action, init_operator_action_schema
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
            "source_kind": "mission_control",
            "source_channel": "mac_app",
            "source_message_id": None,
            "source_user_label": "operator",
            "source_node_id": "mac_mission_control",
            "source_raw_text_present": False,
            "source_raw_text_stored": False,
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


def test_source_migrations_work_on_existing_v0_tables(tmp_path):
    db_path = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
CREATE TABLE operator_action_requests (
  action_id TEXT PRIMARY KEY,
  action_type TEXT NOT NULL,
  requested_by TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  status TEXT NOT NULL,
  approval_required INTEGER NOT NULL DEFAULT 1,
  validation_status TEXT NOT NULL,
  validation_summary TEXT NOT NULL,
  request_receipt_id TEXT,
  approval_id TEXT,
  execution_id TEXT
)
"""
        )
        conn.execute(
            """
CREATE TABLE operator_action_inbox_imports (
  import_id TEXT PRIMARY KEY,
  import_run_id TEXT NOT NULL,
  request_file_path TEXT NOT NULL,
  request_file_hash TEXT,
  request_id TEXT,
  action_id TEXT,
  action_type TEXT,
  requested_by TEXT,
  source_node_id TEXT,
  source_host_kind TEXT,
  source_drop_path TEXT,
  status TEXT NOT NULL,
  rejection_reason TEXT,
  imported_at TEXT NOT NULL,
  approval_required INTEGER NOT NULL DEFAULT 1,
  auto_approve INTEGER NOT NULL DEFAULT 0,
  execute_immediately INTEGER NOT NULL DEFAULT 0,
  execution_started INTEGER NOT NULL DEFAULT 0,
  raw_request_body_stored INTEGER NOT NULL DEFAULT 0,
  runtime_activation_allowed INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  arbitrary_shell_allowed INTEGER NOT NULL DEFAULT 0,
  network_allowed INTEGER NOT NULL DEFAULT 0,
  docker_allowed INTEGER NOT NULL DEFAULT 0,
  ollama_allowed INTEGER NOT NULL DEFAULT 0,
  remote_control_allowed INTEGER NOT NULL DEFAULT 0,
  client_deployment_allowed INTEGER NOT NULL DEFAULT 0,
  file_delete_allowed INTEGER NOT NULL DEFAULT 0,
  file_move_allowed INTEGER NOT NULL DEFAULT 0,
  notes TEXT
)
"""
        )
        conn.commit()
    finally:
        conn.close()

    init_operator_action_schema(db_path)
    operator_action_inbox_table_names(db_path)

    conn = sqlite3.connect(db_path)
    try:
        request_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(operator_action_requests)")
        }
        inbox_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(operator_action_inbox_imports)")
        }
    finally:
        conn.close()
    for column in (
        "source_kind",
        "source_channel",
        "source_message_id",
        "source_user_label",
        "source_node_id",
        "source_raw_text_present",
        "source_raw_text_stored",
    ):
        assert column in request_columns
    for column in (
        "source_kind",
        "source_channel",
        "source_message_id",
        "source_user_label",
        "source_raw_text_present",
        "source_raw_text_stored",
    ):
        assert column in inbox_columns


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
            "SELECT status, execution_started, source_kind, source_channel FROM operator_action_inbox_imports"
        ).fetchone()
    finally:
        conn.close()
    assert request == ("requested", 1)
    assert imported == ("imported", 0, "mission_control", "mac_app")


def test_reimport_does_not_downgrade_approved_action_and_updates_source_metadata(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    request_path = _write_request(
        tmp_path / "inbox" / "reimport.json",
        _request_payload(request_id="reimport_safe"),
    )
    first = import_operator_action_request_file(file_path=request_path, db_path=db_path)
    approve_operator_action(
        action_id=first.action_id,
        approved_by="operator",
        approval_note="Approved before reimport.",
        db_path=db_path,
    )
    request_path.write_text(
        stable_json(
            _request_payload(
                request_id="reimport_safe",
                source={
                    "source_kind": "telegram",
                    "source_channel": "telegram_metadata",
                    "source_message_id": "tg_reimport",
                    "source_raw_text_present": True,
                    "source_raw_text_stored": False,
                },
            )
        ),
        encoding="utf-8",
    )

    second = import_operator_action_request_file(file_path=request_path, db_path=db_path)

    assert second.status == "imported"
    assert second.action_id == first.action_id
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            """
SELECT status, source_kind, source_channel, source_raw_text_present, source_raw_text_stored
FROM operator_action_requests
WHERE action_id = ?
""",
            (first.action_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row == ("approved", "telegram", "telegram_metadata", 1, 0)


def test_all_supported_source_kinds_import_as_metadata_only(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    source_shapes = {
        "mission_control": {"source_channel": "mac_app", "source_node_id": "mac_mission_control"},
        "telegram": {
            "source_channel": "telegram_metadata",
            "source_message_id": "tg_msg_123",
            "source_user_label": "operator",
            "source_node_id": "telegram_future_source",
            "source_raw_text_present": True,
            "source_raw_text_stored": False,
        },
        "cli": {"source_channel": "backend_cli", "source_node_id": "pc_wsl_cli"},
        "report_bridge": {"source_channel": "report_bridge_package", "source_node_id": "report_bridge"},
        "future_client_node": {
            "source_channel": "client_node_drop",
            "source_node_id": "future_client_node_demo",
        },
        "unknown": {"source_channel": "unknown", "source_node_id": None},
    }

    for source_kind, source in source_shapes.items():
        request_path = _write_request(
            tmp_path / "sources" / f"{source_kind}.json",
            _request_payload(
                request_id=f"source_{source_kind}",
                action_type="query_generated_read_model_mirror",
                requested_by=source_kind,
                source={"source_kind": source_kind, **source},
            ),
        )
        item = import_operator_action_request_file(file_path=request_path, db_path=db_path)
        assert item.status == "imported"
        assert item.source_kind == source_kind

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
SELECT source_kind, source_channel, source_raw_text_present, source_raw_text_stored
FROM operator_action_requests
ORDER BY source_kind
"""
        ).fetchall()
    finally:
        conn.close()
    assert {row[0] for row in rows} == set(source_shapes)
    assert any(row == ("telegram", "telegram_metadata", 1, 0) for row in rows)
    assert all(row[3] == 0 for row in rows)


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
        "telegram_auto_approve.json": _request_payload(
            request_id="telegram_auto_approve",
            source={"source_kind": "telegram", "source_channel": "telegram_metadata"},
            authority={"auto_approve": True},
        ),
        "telegram_execute_immediately.json": _request_payload(
            request_id="telegram_execute_immediately",
            source={"source_kind": "telegram", "source_channel": "telegram_metadata"},
            authority={"execute_immediately": True},
        ),
        "network_allowed.json": _request_payload(
            request_id="network_allowed",
            authority={"network_allowed": True},
        ),
        "raw_text_stored.json": _request_payload(
            request_id="raw_text_stored",
            source={"source_raw_text_stored": True},
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
    assert any("source_raw_text_stored" in item.rejection_reason for item in results)
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
    assert payload["latest_action"]["source_kind"] == "mission_control"
    assert payload["latest_request_source"]["source_channel"] == "mac_app"
    assert payload["request_count_by_source_kind"] == {"mission_control": 1}
    assert payload["pending_approval_by_source_kind"] == {"mission_control": 1}
    assert payload["source_channel_posture"]["telegram_ready_metadata_only"] is True
    assert payload["source_channel_posture"]["telegram_api_wired"] is False
    assert payload["source_channel_posture"]["all_sources_require_approval"] is True
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
