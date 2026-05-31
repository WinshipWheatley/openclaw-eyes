import json
import sqlite3
from pathlib import Path

import openclaw_system_knowledge_registry as registry
from scripts.export_openclaw_system_knowledge_registry import main as export_main


def test_registry_has_required_tables_and_no_sqlite_prefixes():
    payload = registry.build_registry(Path.cwd())

    assert payload["required_sqlite_tables"] == list(registry.REQUIRED_TABLES)
    assert len(payload["required_sqlite_tables"]) == 10
    assert not any(table.startswith("sqlite_") for table in payload["required_sqlite_tables"])
    assert set(payload["required_sqlite_tables"]) == set(registry.TABLE_COLUMNS)


def test_registry_counts_and_coverage_are_broader_than_eight_components():
    payload = registry.build_registry(Path.cwd())
    coverage = payload["coverage_assessment"]

    assert coverage["component_count"] == len(payload["component_inventory"])
    assert coverage["known_unknown_count"] == len(payload["known_unknowns"])
    assert coverage["component_count"] >= 12
    assert coverage["known_unknown_count"] >= 6
    assert coverage["eight_seeded_components_is_appropriate"] is False
    for expected_area in [
        "generated read-model system",
        "work terrain surfaces",
        "operator action / workflow surfaces",
        "Cassandra / Chief / Guardian references",
        "mac_eyes / bridge / shuttle surfaces",
        "polish_loop runtime task area",
        "legal module",
        "context / evidence / read-model substrate",
    ]:
        assert expected_area in coverage["covered_high_level_areas"]


def test_external_evidence_stays_unknown_not_confirmed():
    payload = registry.build_registry(Path.cwd())
    unknowns = {item["unknown_id"]: item for item in payload["known_unknowns"]}
    components = {item["component_id"]: item for item in payload["component_inventory"]}

    assert unknowns["unknown_external_repo_a"]["unknown_status"] == "UNKNOWN_EXTERNAL"
    assert unknowns["unknown_external_repo_b"]["unknown_status"] == "UNKNOWN_EXTERNAL"
    assert unknowns["unknown_runtime_state"]["unknown_status"] == "UNKNOWN_BY_BOUNDARY"
    assert unknowns["unknown_prior_codex_web_commit"]["unknown_status"] == "UNKNOWN_UNREACHABLE"
    assert components["external_repo_a_b_runtime_relationship"]["evidence_status"] == "UNKNOWN_EXTERNAL"
    assert components["prior_codex_web_registry_commit"]["evidence_status"] == "UNKNOWN_UNREACHABLE"


def test_boundary_blocks_live_and_sensitive_actions():
    payload = registry.build_registry(Path.cwd())
    boundary = payload["authority_boundary"]

    assert boundary["documentation_read_model_sqlite_only"] is True
    for key, value in boundary.items():
        if key != "documentation_read_model_sqlite_only":
            assert value is False, key


def test_top_build_tasks_are_present_in_practical_order():
    payload = registry.build_registry(Path.cwd())
    tasks = payload["top_build_tasks"]
    titles = [task["title"] for task in tasks]

    assert [task["task_rank"] for task in tasks] == list(range(1, 11))
    assert titles == [
        "Reconcile repo topology / cross-repo estate map",
        "Adopt registry into Hermes/Chief later",
        "Preserve Evidence-Grounded Context Registry as source of truth",
        "Avoid duplicating deterministic registry with generic vector RAG",
        "Mac/PC artifact transport policy",
        "Live Arts PDF export/helper architecture",
        "Access Broker permissions",
        "Request/response stability",
        "Payment watch / ledger readiness",
        "Stale UI/chat-card drift checks",
    ]
    assert all(task["model_class_recommendation"] for task in tasks)


def test_exporter_writes_all_artifacts_and_sqlite_tables(tmp_path):
    result = export_main(["--repo-root", tmp_path.as_posix(), "--format", "paths"])

    assert result == 0
    paths = registry.generated_paths(tmp_path)
    for path in paths.values():
        assert path.exists(), path

    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["registry_id"] == registry.READ_MODEL_ID
    assert payload["coverage_assessment"]["component_count"] >= 12
    assert "Top 10 Build Tasks" in paths["operator_markdown"].read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS system_component" in paths["schema_sql"].read_text(
        encoding="utf-8"
    )
    assert "INSERT INTO system_component" in paths["seed_sql"].read_text(encoding="utf-8")

    with sqlite3.connect(paths["sqlite"]) as conn:
        table_names = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert table_names == set(registry.REQUIRED_TABLES)
        assert not any(table.startswith("sqlite_") for table in table_names)
        component_count = conn.execute("SELECT COUNT(*) FROM system_component").fetchone()[0]
        unknown_count = conn.execute("SELECT COUNT(*) FROM known_unknown").fetchone()[0]

    assert component_count == payload["coverage_assessment"]["component_count"]
    assert unknown_count == payload["coverage_assessment"]["known_unknown_count"]


def test_source_has_no_live_action_imports_or_calls():
    source_paths = [
        Path("openclaw_system_knowledge_registry.py"),
        Path("scripts/export_openclaw_system_knowledge_registry.py"),
    ]
    joined = "\n".join(path.read_text(encoding="utf-8").lower() for path in source_paths)

    for token in [
        "import smtplib",
        "import requests",
        "import subprocess",
        "import webbrowser",
        "from smtplib",
        "from requests",
        "from subprocess",
        "from webbrowser",
        "shell=true",
        "os.system",
        ".unlink(",
        ".rename(",
        "shutil.move",
        "shutil.rmtree",
    ]:
        assert token not in joined
