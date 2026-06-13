from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import openclaw_system_knowledge_registry as registry
from scripts.export_openclaw_system_knowledge_registry import main as export_main


REQUIRED_COMPONENTS = {
    "cassandra",
    "chief",
    "guardian",
    "niles",
    "hermes",
    "watch_desk",
    "universal_intake",
    "context_switchboard",
    "guided_review_coach",
    "data_room_form_fill_lane",
    "model_work_package_router",
    "assignment_loop_contract",
    "worker_run_manager",
    "reference_data_hydration",
    "artifact_link_normalizer",
    "pc_mac_sync",
    "invoice_ledger_discovery",
    "voice_kokoro_caveat",
}


def test_registry_has_required_tables_and_no_sqlite_prefixes() -> None:
    payload = registry.build_registry(Path.cwd())

    assert tuple(payload["required_tables"]) == registry.REQUIRED_TABLES
    assert set(payload["sqlite_contract"]["required_tables"]) == set(registry.REQUIRED_TABLES)
    assert not any(table.startswith("sqlite_") for table in registry.REQUIRED_TABLES)
    assert payload["sqlite_contract"]["explicit_sqlite_internal_tables_defined"] is False


def test_registry_includes_required_current_components() -> None:
    payload = registry.build_registry(Path.cwd())
    components = {component["component_id"]: component for component in payload["component_inventory"]}

    assert REQUIRED_COMPONENTS <= set(components)
    assert "unsafe_to_start" in components["hermes"]["authority_boundary"]
    assert "logical/spawned" in components["niles"]["summary"]
    assert "does not execute business logic" in components["guardian"]["authority_boundary"]


def test_authority_boundary_blocks_live_and_sensitive_actions() -> None:
    payload = registry.build_registry(Path.cwd())
    boundary = payload["authority_boundary"]

    assert boundary["documentation_read_model_sqlite_only"] is True
    for key, value in boundary.items():
        if key != "documentation_read_model_sqlite_only":
            assert value is False, key


def test_known_unknowns_and_build_tasks_present() -> None:
    payload = registry.build_registry(Path.cwd())
    unknowns = {item["unknown_id"] for item in payload["known_unknowns"]}
    tasks = {item["task_id"] for item in payload["build_tasks"]}

    assert "unknown_missing_prior_commit" in unknowns
    assert "unknown_live_chatgpt55_adapter" in unknowns
    assert "unknown_mac_map_import_agent" in unknowns
    assert "unknown_confirmed_reference_data" in unknowns
    assert "task_verify_mac_patch_apply" in tasks
    assert "task_promote_confirmed_reference_data" in tasks


def test_exporter_writes_artifacts_and_sqlite_tables(tmp_path: Path) -> None:
    assert export_main(["--repo-root", str(tmp_path), "--format", "paths"]) == 0
    paths = registry.generated_paths(tmp_path)

    for path in paths.values():
        assert path.exists(), path

    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    operator_markdown = paths["operator_markdown"].read_text(encoding="utf-8")
    schema_sql = paths["schema_sql"].read_text(encoding="utf-8")
    seed_sql = paths["seed_sql"].read_text(encoding="utf-8")

    assert payload["schema_version"] == registry.SCHEMA_VERSION
    assert "## Components" in operator_markdown
    assert "## Known Unknowns" in operator_markdown
    assert "## Authority Boundaries" in operator_markdown
    assert "CREATE TABLE IF NOT EXISTS system_component" in schema_sql
    assert "INSERT INTO system_component" in seed_sql

    with sqlite3.connect(paths["sqlite"]) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        }
        component_count = conn.execute("SELECT COUNT(*) FROM system_component").fetchone()[0]

    assert integrity == "ok"
    assert set(registry.REQUIRED_TABLES) <= tables
    assert not any(table.startswith("sqlite_") for table in tables if table in registry.REQUIRED_TABLES)
    assert component_count == len(payload["component_inventory"])


def test_source_has_no_live_action_imports_or_calls() -> None:
    source_paths = [
        Path("openclaw_system_knowledge_registry.py"),
        Path("scripts/export_openclaw_system_knowledge_registry.py"),
    ]
    forbidden_fragments = (
        "import requests",
        "from requests",
        "subprocess",
        "webbrowser",
        "smtplib",
        "googleapiclient",
        "openai",
        "anthropic",
        "ollama",
        "os.system",
        ".unlink(",
        ".rename(",
        "shutil.move",
        "shutil.rmtree",
    )
    for path in source_paths:
        text = path.read_text(encoding="utf-8")
        for fragment in forbidden_fragments:
            assert fragment not in text, f"{fragment} found in {path}"


def test_registry_declares_safe_posture() -> None:
    payload = registry.build_registry(Path.cwd())
    posture_ids = {item["posture_id"] for item in payload["current_safety_posture"]}

    assert payload["current_status"] == "OPENCLAW_SYSTEM_KNOWLEDGE_REGISTRY_REBUILT"
    assert payload["safety_assertions"]["no_runtime_mutation"] is True
    assert payload["safety_assertions"]["no_external_calls"] is True
    assert "posture_no_external_calls" in posture_ids
    assert "posture_no_live_grants" in posture_ids
