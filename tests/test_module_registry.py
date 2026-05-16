import json
import sqlite3
from pathlib import Path

from module_registry import (
    DEFAULT_MODULE_SEEDS,
    build_approved_module_registry_read_model,
    build_module_registry_report,
    export_approved_module_registry_read_model,
    module_registry_table_names,
    seed_module_registry,
)
from project_capsule import DEMO_PROJECT_ID, create_demo_project_capsule, get_project_capsule
from scripts.build_module_registry import main as build_main
from scripts.export_approved_module_registry_read_model import main as export_approved_main
from scripts.query_module_registry import main as query_main
from scripts.update_project_capsule_modules import main as update_modules_main


def _row(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def test_schema_initializes(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    assert {
        "module_registry_runs",
        "module_registry_modules",
        "module_registry_required_inputs",
        "module_registry_generated_outputs",
        "module_registry_dependencies",
    } <= set(module_registry_table_names(db_path))


def test_registry_is_idempotent_and_non_authorizing(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    first = seed_module_registry(db_path=db_path, run_id="module_fixture")
    second = seed_module_registry(db_path=db_path, run_id="module_fixture")

    assert first.module_count == len(DEFAULT_MODULE_SEEDS)
    assert second.module_count == len(DEFAULT_MODULE_SEEDS)
    assert _row(db_path, "SELECT COUNT(*) FROM module_registry_modules")[0] == len(DEFAULT_MODULE_SEEDS)
    assert _row(
        db_path,
        """
SELECT COUNT(*)
FROM module_registry_modules
WHERE runtime_authority_required != 0
""",
    )[0] == 0
    assert _row(
        db_path,
        """
SELECT runtime_authority, activation_allowed, tool_execution_allowed, network_authority
FROM module_registry_runs
WHERE run_id = 'module_fixture'
""",
    ) == (0, 0, 0, 0)


def test_reports_and_dependencies_work(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"

    exit_code = build_main(["--db", str(db_path), "--run-id", "module_fixture", "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["run"]["module_count"] == len(DEFAULT_MODULE_SEEDS)

    deps = build_module_registry_report(
        db_path=db_path,
        run_id="module_fixture",
        section="dependencies",
    )
    assert {"evidence_kettle", "context_selection", "project_capsule"} <= {
        item["module_id"] for item in deps["dependencies"]
    }

    category_exit = query_main(
        [
            "--db",
            str(db_path),
            "--run-id",
            "module_fixture",
            "--report",
            "client-capsule",
            "--format",
            "operator",
        ]
    )
    assert category_exit == 0
    assert "project_capsule" in capsys.readouterr().out

    approved_exit = query_main(
        [
            "--db",
            str(db_path),
            "--run-id",
            "module_fixture",
            "--report",
            "approved",
            "--format",
            "operator",
        ]
    )
    assert approved_exit == 0
    assert "cassandra_clara_fact_intake" in capsys.readouterr().out


def test_approved_module_records_expose_stage_2_contract_fields(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    seed_module_registry(db_path=db_path, run_id="module_fixture")

    read_model = build_approved_module_registry_read_model(db_path=db_path)
    by_id = {item["module_id"]: item for item in read_model["modules"]}

    assert {
        "chief_intent_routing",
        "cassandra_clara_fact_intake",
        "guardian_hitl_gate",
        "niles_album_matrix",
        "hermes_next_lane_advisory",
        "planner_runner_registry",
        "report_bridge_sanitized_summary",
        "project_capsule_bundle_blueprint",
    } <= set(by_id)
    for item in by_id.values():
        assert item["version"]
        assert item["display_name"]
        assert item["world"]
        assert isinstance(item["capabilities"], list)
        assert isinstance(item["required_inputs"], list)
        assert isinstance(item["optional_inputs"], list)
        assert item["sensitive_input_policy"]
        assert isinstance(item["no_go_data_classes"], list)
        assert item["allowed_authority_level"] in {"read_only", "metadata_only", "planning_only", "future_gated"}
        assert isinstance(item["dependencies"], list)
        assert isinstance(item["tests_required"], list)
        assert isinstance(item["client_safe"], bool)
        assert isinstance(item["core_only"], bool)
        assert isinstance(item["report_bridge_summary_allowed"], bool)
        assert item["status"] in {"approved", "draft", "blocked", "deprecated"}
        assert item["runtime_authority"] is False

    assert by_id["planner_runner_registry"]["status"] == "blocked"
    assert by_id["planner_runner_registry"]["client_safe"] is False
    assert by_id["report_bridge_sanitized_summary"]["status"] == "approved"
    assert read_model["runtime_authority"] is False
    assert read_model["no_authority_flags"]["send_allowed"] is False


def test_approved_module_registry_export_writes_read_model(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"

    summary = export_approved_module_registry_read_model(db_path=db_path, export_root=export_root)
    payload = json.loads((export_root / "approved_module_registry.json").read_text(encoding="utf-8"))

    assert summary["module_count"] >= 8
    assert payload["schema_version"] == "approved_module_registry_read_model_v0"
    assert payload["runtime_authority"] is False
    assert (export_root / "approved_module_registry_OPERATOR.md").is_file()

    exit_code = export_approved_main(
        [
            "--db",
            str(db_path),
            "--export-root",
            str(export_root),
            "--format",
            "operator",
        ]
    )
    assert exit_code == 0
    assert "Approved Module Registry Read-Model v0" in capsys.readouterr().out


def test_demo_capsule_module_selection_does_not_activate_modules(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    create_demo_project_capsule(db_path=db_path, run_id="pcap_fixture")
    seed_module_registry(db_path=db_path, run_id="module_fixture")

    exit_code = update_modules_main(
        [
            "--db",
            str(db_path),
            "--project-id",
            DEMO_PROJECT_ID,
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    capsule = get_project_capsule(db_path=db_path, project_id=DEMO_PROJECT_ID)

    assert exit_code == 0
    assert payload["selected_module_count"] == 7
    assert payload["runtime_authority"] is False
    assert payload["activation_count"] == 0
    assert all(item["activation_status"] == "not_activated" for item in capsule["modules"])
    assert all(not item["runtime_authority"] for item in capsule["modules"])


def test_module_registry_sources_have_no_external_or_activation_behavior():
    source_files = [
        Path("module_registry.py"),
        Path("scripts/build_module_registry.py"),
        Path("scripts/query_module_registry.py"),
        Path("scripts/export_approved_module_registry_read_model.py"),
        Path("scripts/update_project_capsule_modules.py"),
    ]
    forbidden = [
        "import subprocess",
        "subprocess.",
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
        "pip install",
        "npm install",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in text
