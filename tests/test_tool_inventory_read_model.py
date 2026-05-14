import json
from pathlib import Path

from scripts.export_tool_inventory_read_model import (
    JSON_EXPORT_NAME,
    OPERATOR_EXPORT_NAME,
    build_tool_inventory_read_model,
    export_tool_inventory_read_model,
    main,
)
from tool_inventory import DEFAULT_TOOL_SPECS, ProbeResult, ToolCommand, run_tool_inventory


def _specs(*tool_ids):
    wanted = set(tool_ids)
    return tuple(spec for spec in DEFAULT_TOOL_SPECS if spec.tool_id in wanted)


def _resolver(installed_names):
    installed = set(installed_names)

    def resolve(name: str):
        return f"/usr/bin/{name}" if name in installed else None

    return resolve


def _runner(command: ToolCommand):
    tool_name = Path(command.args[0]).name
    versions = {
        "ollama": "ollama version is 0.20.2\n",
        "docker": "Docker version 28.2.2, build fixture\n",
        "python3": "Python 3.12.3\n",
    }
    return ProbeResult(
        attempted=True,
        succeeded=True,
        timed_out=False,
        returncode=0,
        stdout=versions.get(tool_name, f"{tool_name} version fixture\n"),
        stderr="",
    )


def _inventory_fixture(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    run_tool_inventory(
        db_path=db_path,
        run_id="tool_fixture",
        tool_specs=_specs(
            "python3",
            "ollama",
            "docker",
            "sqlite3",
            "sqlite_utils",
            "datasette",
            "litestream",
        ),
        executable_resolver=_resolver({"python3", "ollama", "docker"}),
        command_runner=_runner,
    )
    return db_path


def test_tool_inventory_json_and_operator_markdown_are_generated(tmp_path):
    db_path = _inventory_fixture(tmp_path)
    export_root = tmp_path / "generated" / "read_models"

    summary = export_tool_inventory_read_model(db_path=db_path, export_root=export_root)

    assert summary["detected_count"] == 3
    assert summary["not_detected_count"] == 4
    assert (export_root / JSON_EXPORT_NAME).is_file()
    assert (export_root / OPERATOR_EXPORT_NAME).is_file()


def test_read_model_represents_detected_tools_as_observed_only(tmp_path):
    db_path = _inventory_fixture(tmp_path)
    payload = build_tool_inventory_read_model(db_path=db_path)
    detected = {tool["tool_id"]: tool for tool in payload["detected_tools"]}

    assert detected["ollama"]["version_text"] == "ollama version is 0.20.2"
    assert detected["ollama"]["install_status"] == "observed_installed"
    assert detected["ollama"]["integration_status"] == "not_integrated"
    assert detected["ollama"]["action_status"] == "no_action_taken"
    assert detected["ollama"]["approval_status"] == "not_approved"
    assert detected["ollama"]["authorization_status"] == "not_authorized"
    assert detected["docker"]["integration_status"] == "not_integrated"
    assert detected["docker"]["approval_status"] == "not_approved"


def test_sqlite_not_detected_tools_are_represented_without_failure(tmp_path):
    db_path = _inventory_fixture(tmp_path)
    payload = build_tool_inventory_read_model(db_path=db_path)
    sqlite_tools = {tool["tool_id"]: tool for tool in payload["sqlite_findings"]["tools"]}

    assert set(sqlite_tools) == {"datasette", "litestream", "sqlite3", "sqlite_utils"}
    assert all(tool["install_status"] == "not_detected" for tool in sqlite_tools.values())
    assert payload["sqlite_findings"]["detected_count"] == 0


def test_no_activation_or_network_authority_is_claimed(tmp_path):
    db_path = _inventory_fixture(tmp_path)
    payload = build_tool_inventory_read_model(db_path=db_path)

    for key in [
        "tool_activation_allowed",
        "runtime_authority",
        "integration_authority",
        "model_execution_allowed",
        "container_execution_allowed",
        "remote_access_allowed",
        "network_authority",
        "tool_install_allowed",
        "tool_upgrade_allowed",
        "tool_remove_allowed",
        "agent_activation_allowed",
        "body_ingested",
        "raw_sensitive_data_stored",
    ]:
        assert payload[key] is False
    assert payload["inventory_action_flags"] == {
        "install_action_taken": False,
        "integration_action_taken": False,
        "runtime_authority": False,
        "network_access_attempted": False,
        "daemon_started": False,
        "model_execution_attempted": False,
        "container_execution_attempted": False,
        "remote_access_attempted": False,
    }
    assert "model_execution" in payload["claims_not_made"]
    assert "container_execution" in payload["claims_not_made"]
    assert "network_authority" in payload["claims_not_made"]


def test_missing_ledger_does_not_create_sqlite_or_claim_authority(tmp_path):
    db_path = tmp_path / "missing.sqlite"
    payload = build_tool_inventory_read_model(db_path=db_path)

    assert not db_path.exists()
    assert payload["latest_tool_inventory_run_id"] is None
    assert payload["detected_count"] == 0
    assert payload["runtime_authority"] is False
    assert payload["network_authority"] is False


def test_export_output_is_deterministic_for_same_inventory_run(tmp_path):
    db_path = _inventory_fixture(tmp_path)
    export_root = tmp_path / "generated" / "read_models"

    export_tool_inventory_read_model(db_path=db_path, export_root=export_root)
    first_json = (export_root / JSON_EXPORT_NAME).read_text(encoding="utf-8")
    first_operator = (export_root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    export_tool_inventory_read_model(db_path=db_path, export_root=export_root)

    assert (export_root / JSON_EXPORT_NAME).read_text(encoding="utf-8") == first_json
    assert (export_root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8") == first_operator


def test_operator_markdown_states_boundaries_and_next_safe_move(tmp_path):
    db_path = _inventory_fixture(tmp_path)
    export_root = tmp_path / "generated" / "read_models"
    export_tool_inventory_read_model(db_path=db_path, export_root=export_root)
    text = (export_root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert "Evidence:" in text
    assert "Boundary:" in text
    assert "Blocked:" in text
    assert "Next safe move:" in text
    assert "Installed does not mean approved" in text
    assert "Detected does not mean integrated" in text
    assert "Available does not mean authorized" in text
    assert "Ollama installed does not mean models may be listed, pulled, run, or used by agents" in text
    assert "Docker installed does not mean containers may be built, pulled, run, or composed" in text


def test_cli_exports_json_and_operator_markdown(tmp_path, capsys):
    db_path = _inventory_fixture(tmp_path)
    export_root = tmp_path / "generated" / "read_models"

    exit_code = main(
        [
            "--db",
            str(db_path),
            "--export-root",
            str(export_root),
            "--format",
            "json",
        ]
    )
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["detected_count"] == 3
    assert (export_root / JSON_EXPORT_NAME).is_file()
    assert (export_root / OPERATOR_EXPORT_NAME).is_file()

    operator_exit_code = main(
        [
            "--db",
            str(db_path),
            "--export-root",
            str(export_root),
            "--format",
            "operator",
        ]
    )
    operator_output = capsys.readouterr().out
    assert operator_exit_code == 0
    assert "Tool Inventory Read-Model Export v0" in operator_output
