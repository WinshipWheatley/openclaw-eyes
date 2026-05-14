import json
import sqlite3
from pathlib import Path

import tool_inventory
from scripts.query_tool_inventory import main as query_main
from tool_inventory import (
    DEFAULT_TOOL_SPECS,
    FORBIDDEN_COMMAND_TOKENS,
    ProbeResult,
    ToolCommand,
    _build_tool_command,
    _validate_tool_command,
    build_tool_inventory_report,
    query_tool_inventory_report_section,
    run_allowed_command,
    run_tool_inventory,
    tool_inventory_table_names,
)


def _specs(*tool_ids):
    wanted = set(tool_ids)
    return tuple(spec for spec in DEFAULT_TOOL_SPECS if spec.tool_id in wanted)


def _resolver(installed_names):
    installed = set(installed_names)

    def resolve(name: str):
        return f"/usr/bin/{name}" if name in installed else None

    return resolve


def _rows(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _row(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def test_schema_initializes(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    assert {
        "tool_inventory_runs",
        "tool_observations",
        "tool_observation_labels",
        "tool_install_locations",
        "tool_version_observations",
        "tool_runtime_boundaries",
        "tool_future_candidates",
    } <= set(tool_inventory_table_names(db_path))


def test_tool_inventory_run_records_provenance_and_statuses(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    commands = []

    def runner(command: ToolCommand):
        commands.append(command.args)
        return ProbeResult(
            attempted=True,
            succeeded=True,
            timed_out=False,
            returncode=0,
            stdout=f"{Path(command.args[0]).name} version 1.0\n",
            stderr="",
        )

    result = run_tool_inventory(
        db_path=db_path,
        run_id="tool_fixture",
        tool_specs=_specs(
            "python3",
            "sqlite3",
            "sqlite_utils",
            "ollama",
            "docker",
            "docker_compose",
            "ansible",
            "tailscale",
        ),
        executable_resolver=_resolver({"python3", "sqlite3", "ollama", "docker", "ansible", "tailscale"}),
        command_runner=runner,
    )

    assert result.observed_count == 8
    assert result.detected_count == 7
    assert result.not_detected_count == 1
    assert len(commands) == 7
    assert _row(
        db_path,
        """
SELECT install_action_taken, integration_action_taken, runtime_authority,
       network_access_attempted, daemon_started, model_execution_attempted,
       container_execution_attempted, remote_access_attempted
FROM tool_inventory_runs
WHERE run_id = ?
""",
        ("tool_fixture",),
    ) == (0, 0, 0, 0, 0, 0, 0, 0)
    assert _row(
        db_path,
        "SELECT install_status FROM tool_observations WHERE run_id = ? AND tool_id = ?",
        ("tool_fixture", "python3"),
    )[0] == "observed_installed"
    assert _row(
        db_path,
        "SELECT install_status FROM tool_observations WHERE run_id = ? AND tool_id = ?",
        ("tool_fixture", "sqlite_utils"),
    )[0] == "not_detected"
    assert _row(
        db_path,
        "SELECT COUNT(*) FROM tool_observations WHERE run_id = ? AND detected = 1 AND integration_status != 'not_integrated'",
        ("tool_fixture",),
    )[0] == 0
    assert _row(
        db_path,
        "SELECT COUNT(*) FROM tool_observations WHERE run_id = ? AND action_status != 'no_action_taken'",
        ("tool_fixture",),
    )[0] == 0


def test_probe_specs_are_allowlisted_and_have_no_install_or_network_actions():
    forbidden = FORBIDDEN_COMMAND_TOKENS | {"clone"}

    for spec in DEFAULT_TOOL_SPECS:
        command = _build_tool_command(spec, f"/usr/bin/{spec.executable_names[0]}")
        _validate_tool_command(command)
        assert not (set(arg.lower() for arg in command.args) & forbidden)
        assert command.timeout_seconds <= 5


def test_subprocess_runner_uses_no_shell_true(monkeypatch):
    calls = []

    class Completed:
        returncode = 0
        stdout = "Python 3.11.0\n"
        stderr = ""

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return Completed()

    monkeypatch.setattr(tool_inventory.subprocess, "run", fake_run)

    result = run_allowed_command(
        ToolCommand(
            command_id="python3:version",
            args=("python3", "--version"),
            timeout_seconds=1,
            allowed_executable_names=("python3",),
        )
    )

    assert result.succeeded is True
    assert calls
    assert calls[0][0] == ["python3", "--version"]
    assert calls[0][1].get("shell") in (None, False)
    assert calls[0][1]["timeout"] == 1
    assert calls[0][1]["capture_output"] is True


def test_unknown_commands_cannot_be_executed():
    command = ToolCommand(
        command_id="bad",
        args=("curl", "https://example.invalid"),
        timeout_seconds=1,
        allowed_executable_names=("python3",),
    )

    try:
        run_allowed_command(command)
    except ValueError as exc:
        assert "allowlisted" in str(exc)
    else:
        raise AssertionError("unknown command executed")


def test_high_risk_boundaries_do_not_run_models_containers_or_remote_actions(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    commands_by_id = {}

    def runner(command: ToolCommand):
        commands_by_id[command.command_id] = command.args
        return ProbeResult(True, True, False, 0, "version 1.0\n", "")

    run_tool_inventory(
        db_path=db_path,
        run_id="risk_fixture",
        tool_specs=_specs("ollama", "docker", "docker_compose", "ansible", "tailscale", "wg"),
        executable_resolver=_resolver({"ollama", "docker", "ansible", "tailscale", "wg"}),
        command_runner=runner,
    )

    assert commands_by_id["ollama:version"][1:] == ("--version",)
    assert "pull" not in commands_by_id["ollama:version"]
    assert "run" not in commands_by_id["ollama:version"]
    assert commands_by_id["docker:version"][1:] == ("--version",)
    assert commands_by_id["docker_compose:version"][1:] == ("compose", "version")
    assert "run" not in commands_by_id["docker:version"]
    assert "up" not in commands_by_id["docker_compose:version"]
    assert commands_by_id["ansible:version"][1:] == ("--version",)
    assert commands_by_id["tailscale:version"][1:] == ("version",)
    assert commands_by_id["wg:version"][1:] == ("--version",)
    assert _row(
        db_path,
        """
SELECT COUNT(*)
FROM tool_observations
WHERE run_id = ? AND detected = 1
  AND category IN ('local_llm','container','deployment','remote_access')
  AND requires_operator_review != 1
""",
        ("risk_fixture",),
    )[0] == 0
    assert _row(
        db_path,
        "SELECT COUNT(*) FROM tool_runtime_boundaries WHERE boundary_text LIKE '%does not authorize%'",
    )[0] >= 6


def test_no_network_modules_are_imported_for_lane():
    source = Path(tool_inventory.__file__).read_text(encoding="utf-8")

    assert "import requests" not in source
    assert "import httpx" not in source
    assert "urllib.request" not in source
    assert "import socket" not in source


def test_reports_work(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"

    def runner(command: ToolCommand):
        return ProbeResult(True, True, False, 0, f"{Path(command.args[0]).name} version 1.0\n", "")

    run_tool_inventory(
        db_path=db_path,
        run_id="report_fixture",
        tool_specs=_specs("python3", "sqlite3", "ollama", "docker", "sqlite_utils"),
        executable_resolver=_resolver({"python3", "sqlite3", "ollama", "docker"}),
        command_runner=runner,
    )

    summary = build_tool_inventory_report(db_path=db_path, run_id="report_fixture")
    detected = query_tool_inventory_report_section(
        db_path=db_path, run_id="report_fixture", section="detected"
    )
    sqlite_report = query_tool_inventory_report_section(
        db_path=db_path, run_id="report_fixture", section="category", category="sqlite"
    )
    high_risk = query_tool_inventory_report_section(
        db_path=db_path, run_id="report_fixture", section="high-risk"
    )
    candidates = query_tool_inventory_report_section(
        db_path=db_path, run_id="report_fixture", section="future-candidates"
    )
    not_detected = query_tool_inventory_report_section(
        db_path=db_path, run_id="report_fixture", section="not-detected"
    )

    assert summary["run"]["detected_count"] == 4
    assert {item["tool_id"] for item in detected["items"]} == {"python3", "sqlite3", "ollama", "docker"}
    assert {item["tool_id"] for item in sqlite_report["items"]} == {"sqlite3", "sqlite_utils"}
    assert {item["tool_id"] for item in high_risk["items"]} == {"ollama", "docker"}
    assert {item["tool_id"] for item in candidates["items"]} >= {"python3", "sqlite3", "ollama", "docker"}
    assert {item["tool_id"] for item in not_detected["items"]} == {"sqlite_utils"}

    exit_code = query_main(
        [
            "--db",
            str(db_path),
            "--run-id",
            "report_fixture",
            "--report",
            "category",
            "--category",
            "sqlite",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["section"] == "category"

    summary_exit_code = query_main(
        [
            "--db",
            str(db_path),
            "--run-id",
            "report_fixture",
            "--report",
            "summary",
            "--format",
            "operator",
        ]
    )
    summary_output = capsys.readouterr().out
    assert summary_exit_code == 0
    assert "Local Tool Inventory v0" in summary_output
