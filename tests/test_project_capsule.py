import json
import sqlite3
from pathlib import Path

from project_capsule import (
    DEFAULT_SELECTED_MODULES,
    DEMO_PROJECT_ID,
    create_demo_project_capsule,
    get_project_capsule,
    link_project_capsule_modules,
    project_capsule_table_names,
)
from scripts.create_project_capsule import main as create_main
from scripts.query_project_capsules import main as query_main


def _row(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def test_schema_initializes(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    assert {
        "project_capsule_runs",
        "project_capsules",
        "project_capsule_worlds",
        "project_capsule_tools",
        "project_capsule_boundaries",
        "project_capsule_receipt_requirements",
        "project_capsule_read_model_requirements",
        "project_capsule_next_moves",
        "project_capsule_modules",
    } <= set(project_capsule_table_names(db_path))


def test_demo_capsule_is_idempotent_and_non_authorizing(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    first = create_demo_project_capsule(db_path=db_path, run_id="pcap_fixture")
    second = create_demo_project_capsule(db_path=db_path, run_id="pcap_fixture")

    assert first.project_id == DEMO_PROJECT_ID
    assert second.capsule_count == 1
    assert _row(db_path, "SELECT COUNT(*) FROM project_capsules")[0] == 1
    assert _row(
        db_path,
        """
SELECT COUNT(*)
FROM project_capsules
WHERE runtime_authority != 0
   OR deployment_authority != 0
   OR client_data_access != 0
   OR agent_activation_allowed != 0
   OR tool_execution_allowed != 0
   OR network_authority != 0
   OR approval_status != 'not_approved'
""",
    )[0] == 0


def test_demo_capsule_records_scope_requirements_and_next_move(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    create_demo_project_capsule(db_path=db_path, run_id="pcap_fixture")

    capsule = get_project_capsule(db_path=db_path, project_id=DEMO_PROJECT_ID)

    assert capsule is not None
    assert {item["world_id"] for item in capsule["worlds"]} == {
        "build",
        "communications",
        "operations",
    }
    assert {"copier", "pocketbase", "datasette", "sqlite_utils"} <= {
        item["tool_id"] for item in capsule["tools"]
    }
    assert {"real_client_data", "credentials_secrets_tokens"} <= {
        item["data_class"] for item in capsule["boundaries"]
        if item["boundary_kind"] == "forbidden"
    }
    assert {"project_capsules.json", "context_selection.json", "tool_intake.json"} <= {
        item["read_model_name"] for item in capsule["read_model_requirements"]
    }
    assert {"capsule_creation_receipt", "approval_gate_receipt"} <= {
        item["receipt_type"] for item in capsule["receipt_requirements"]
    }
    assert capsule["next_moves"][0]["move_label"] == "review_demo_capsule_boundaries"


def test_reports_work(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"

    exit_code = create_main(["--db", str(db_path), "--demo", "--run-id", "pcap_fixture", "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["run"]["capsule_count"] == 1

    detail_exit = query_main(
        ["--db", str(db_path), "--project-id", DEMO_PROJECT_ID, "--format", "operator"]
    )
    assert detail_exit == 0
    assert "Demo Client Operations Helper" in capsys.readouterr().out


def test_module_linkage_is_planning_only(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    create_demo_project_capsule(db_path=db_path, run_id="pcap_fixture")

    result = link_project_capsule_modules(db_path=db_path)
    capsule = get_project_capsule(db_path=db_path, project_id=DEMO_PROJECT_ID)

    assert result.selected_module_count == len(DEFAULT_SELECTED_MODULES)
    assert result.runtime_authority is False
    assert result.activation_count == 0
    assert {item["module_id"] for item in capsule["modules"]} == set(DEFAULT_SELECTED_MODULES)
    assert all(item["activation_status"] == "not_activated" for item in capsule["modules"])


def test_lane_sources_do_not_contain_external_or_activation_behavior():
    source_files = [
        Path("project_capsule.py"),
        Path("scripts/create_project_capsule.py"),
        Path("scripts/query_project_capsules.py"),
    ]
    forbidden = [
        "import subprocess",
        "subprocess.",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "git clone",
        "docker run",
        "ollama run",
        "ollama pull",
        "pip install",
        "npm install",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in text
