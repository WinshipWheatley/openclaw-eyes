import json
import sqlite3
from pathlib import Path

from module_registry import (
    DEFAULT_MODULE_SEEDS,
    build_module_registry_report,
    module_registry_table_names,
    seed_module_registry,
)
from project_capsule import DEMO_PROJECT_ID, create_demo_project_capsule, get_project_capsule
from scripts.build_module_registry import main as build_main
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
