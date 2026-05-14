import json
from pathlib import Path

from scripts.export_tool_intake_read_model import (
    JSON_EXPORT_NAME,
    OPERATOR_EXPORT_NAME,
    build_tool_intake_read_model,
    export_tool_intake_read_model,
    main,
)
from tool_intake import DEFAULT_CANDIDATE_SEEDS, seed_tool_intake_registry
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
        "docker": "Docker version fixture\n",
        "ollama": "ollama version is fixture\n",
    }
    return ProbeResult(True, True, False, 0, versions.get(tool_name, "version fixture\n"), "")


def _fixture(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    run_tool_inventory(
        db_path=db_path,
        run_id="inventory_fixture",
        tool_specs=_specs(
            "docker",
            "ollama",
            "datasette",
            "sqlite_utils",
            "litestream",
            "sqlite3",
            "syncthing",
            "pocketbase",
            "copier",
            "devbox",
            "trivy",
            "syft",
            "grype",
            "caddy",
            "netdata",
            "uptime_kuma",
            "llama_cpp",
        ),
        executable_resolver=_resolver({"docker", "ollama"}),
        command_runner=_runner,
    )
    seed_tool_intake_registry(db_path=db_path, run_id="intake_fixture")
    return db_path


def test_tool_intake_json_and_operator_markdown_are_generated(tmp_path):
    db_path = _fixture(tmp_path)
    export_root = tmp_path / "generated" / "read_models"

    summary = export_tool_intake_read_model(db_path=db_path, export_root=export_root)

    assert summary["candidate_count"] == len(DEFAULT_CANDIDATE_SEEDS)
    assert summary["installed_candidate_count"] == 2
    assert (export_root / JSON_EXPORT_NAME).is_file()
    assert (export_root / OPERATOR_EXPORT_NAME).is_file()


def test_read_model_represents_candidate_counts_and_sections(tmp_path):
    db_path = _fixture(tmp_path)
    payload = build_tool_intake_read_model(db_path=db_path)

    assert payload["latest_tool_intake_run_id"] == "intake_fixture"
    assert payload["candidate_count"] == len(DEFAULT_CANDIDATE_SEEDS)
    assert payload["installed_candidate_count"] == 2
    assert payload["counts_by_candidate_status"] == {
        "candidate": 11,
        "deferred": 21,
        "observed_only": 2,
        "sandbox_later": 5,
    }
    assert payload["counts_by_risk_level"]["high"] == 9
    assert {"datasette", "sqlite_utils", "litestream", "copier", "devbox"} <= {
        item["tool_id"] for item in payload["high_fit_candidates"]
    }
    assert {"syncthing", "caddy", "netdata", "uptime_kuma", "llama_cpp"} <= {
        item["tool_id"] for item in payload["sandbox_later_candidates"]
    }
    assert {"pocketbase", "copier"} <= {
        item["tool_id"] for item in payload["client_capsule_candidates"]
    }


def test_installed_candidates_are_not_approved_or_integrated(tmp_path):
    db_path = _fixture(tmp_path)
    payload = build_tool_intake_read_model(db_path=db_path)
    installed = {item["tool_id"]: item for item in payload["installed_candidates"]}

    assert set(installed) == {"docker", "ollama"}
    for item in installed.values():
        assert item["approval_status"] == "not_approved"
        assert item["integration_status"] == "not_integrated"
        assert item["candidate_status"] == "observed_only"
        assert item["inventory_status"]["linked"] is True
        assert item["inventory_status"]["detected"] is True


def test_docker_and_ollama_remain_high_risk_and_not_authorized(tmp_path):
    db_path = _fixture(tmp_path)
    payload = build_tool_intake_read_model(db_path=db_path)
    high_risk = {item["tool_id"]: item for item in payload["high_risk_candidates"]}

    assert {"docker", "ollama"} <= set(high_risk)
    assert high_risk["docker"]["risk_level"] == "high"
    assert high_risk["ollama"]["risk_level"] == "high"
    assert high_risk["docker"]["approval_status"] == "not_approved"
    assert high_risk["ollama"]["approval_status"] == "not_approved"
    assert payload["container_execution_allowed"] is False
    assert payload["model_execution_allowed"] is False


def test_no_authority_flags_are_true(tmp_path):
    db_path = _fixture(tmp_path)
    payload = build_tool_intake_read_model(db_path=db_path)

    for key in [
        "tool_install_allowed",
        "tool_execution_allowed",
        "integration_authority",
        "approval_authority",
        "runtime_authority",
        "network_authority",
        "model_execution_allowed",
        "container_execution_allowed",
        "remote_access_allowed",
    ]:
        assert payload[key] is False
        assert payload["authority_flags"][key] is False
    assert payload["run_action_flags"] == {
        "install_action_taken": False,
        "integration_action_taken": False,
        "runtime_authority": False,
        "network_access_attempted": False,
        "tool_execution_attempted": False,
    }


def test_unknown_url_license_and_install_commands_are_not_exported(tmp_path):
    db_path = _fixture(tmp_path)
    payload = build_tool_intake_read_model(db_path=db_path)

    assert payload["official_urls_guessed"] is False
    assert payload["licenses_guessed"] is False
    assert payload["latest_versions_guessed"] is False
    for item in payload["candidates"]:
        assert "official_url" not in item
        assert "license" not in item
        assert "install_command" not in item
        assert "latest_version" not in item


def test_export_output_is_deterministic_for_same_intake_run(tmp_path):
    db_path = _fixture(tmp_path)
    export_root = tmp_path / "generated" / "read_models"

    export_tool_intake_read_model(db_path=db_path, export_root=export_root)
    first_json = (export_root / JSON_EXPORT_NAME).read_text(encoding="utf-8")
    first_operator = (export_root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    export_tool_intake_read_model(db_path=db_path, export_root=export_root)

    assert (export_root / JSON_EXPORT_NAME).read_text(encoding="utf-8") == first_json
    assert (export_root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8") == first_operator


def test_operator_markdown_states_boundaries_and_next_safe_move(tmp_path):
    db_path = _fixture(tmp_path)
    export_root = tmp_path / "generated" / "read_models"
    export_tool_intake_read_model(db_path=db_path, export_root=export_root)
    text = (export_root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert "What this is:" in text
    assert "What this is not:" in text
    assert "Installed candidates:" in text
    assert "High-fit candidates:" in text
    assert "High-risk candidates:" in text
    assert "Sandbox-later candidates:" in text
    assert "Client-capsule candidates:" in text
    assert "No candidate is approved" in text
    assert "No candidate is integrated" in text
    assert "Docker remains high-risk observed-only metadata" in text
    assert "Ollama remains high-risk observed-only metadata" in text
    assert "Next safe move:" in text


def test_cli_exports_json_and_operator_markdown(tmp_path, capsys):
    db_path = _fixture(tmp_path)
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
    assert summary["candidate_count"] == len(DEFAULT_CANDIDATE_SEEDS)
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
    assert "Tool Intake Read-Model Export v0" in operator_output


def test_export_script_has_no_external_tool_or_network_behavior():
    text = Path("scripts/export_tool_intake_read_model.py").read_text(encoding="utf-8").lower()
    forbidden = [
        "import subprocess",
        "subprocess.",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "git clone",
        "pip install",
        "pipx install",
        "npm install",
        "apt install",
        "apt-get install",
        "uv pip install",
        "docker run",
        "ollama run",
        "ollama pull",
    ]
    for token in forbidden:
        assert token not in text
