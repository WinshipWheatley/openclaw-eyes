import ast
import json
import sqlite3
from pathlib import Path

import openclaw_estate_topology_registry as registry
from scripts.export_openclaw_estate_topology_registry import main as export_main


FIXED_NOW = "2026-05-30T18:30:00+00:00"


def _areas_by_id(payload: dict) -> dict[str, dict]:
    return {area["area_id"]: area for area in payload["source_of_truth_areas"]}


def test_registry_is_deterministic_and_counts_estate_topology():
    first = registry.build_openclaw_estate_topology_registry(generated_at=FIXED_NOW)
    second = registry.build_openclaw_estate_topology_registry(generated_at=FIXED_NOW)

    assert registry.stable_json(first) == registry.stable_json(second)
    assert first["schema_version"] == registry.READ_MODEL_VERSION
    assert first["contract_schema_version"] == registry.SCHEMA_VERSION
    assert first["machine_count"] == 2
    assert first["repo_working_copy_count"] == 5
    assert first["actual_repo_count"] == 3
    assert set(first["actual_repos"]) == {"openclaw-eyes", "openclaw-runtime", "openclaw-mission-control"}
    assert set(registry.REQUIRED_SQLITE_TABLES) == {
        "machine",
        "repo_working_copy",
        "repo_relationship",
        "bridge_path",
        "source_of_truth_area",
        "registry_presence",
        "codex_web_artifact",
        "known_unknown",
        "recommended_action",
    }


def test_five_working_copies_preserve_machine_repo_roles():
    payload = registry.build_openclaw_estate_topology_registry(generated_at=FIXED_NOW)
    copies = {copy["working_copy_id"]: copy for copy in payload["repo_working_copies"]}

    assert copies["pc_openclaw_eyes_backend"]["local_path"] == "/home/openclaw"
    assert copies["pc_openclaw_eyes_backend"]["classification"] == "PC_BACKEND"
    assert copies["pc_openclaw_eyes_backend"]["clean"] is False
    assert copies["pc_openclaw_eyes_backend"]["worktree_status"] == "DIRTY"
    assert copies["pc_openclaw_runtime"]["local_path"] == "/home/openclaw_external/openclaw-runtime"
    assert copies["pc_openclaw_runtime"]["classification"] == "RUNTIME_ACTORS"
    assert copies["pc_openclaw_runtime"]["worktree_status"] == "CLEAN"
    assert copies["mac_mission_control_app"]["classification"] == "MAC_APP"
    assert copies["mac_mission_control_app"]["swift"] is True
    assert copies["mac_mission_control_app"]["remote"] == "none/local-only"
    assert copies["mac_openclaw_eyes_context"]["classification"] == "EYES_CONTEXT_REPO"
    assert copies["mac_openclaw_runtime"]["classification"] == "RUNTIME_ACTORS"


def test_codex_web_commits_are_unreachable_artifacts_not_source_truth():
    payload = registry.build_openclaw_estate_topology_registry(generated_at=FIXED_NOW)
    artifacts = {artifact["commit_ref"]: artifact for artifact in payload["codex_web_artifacts"]}

    assert artifacts["33e00a6"]["status"] == "UNREACHABLE"
    assert artifacts["33e00a6"]["source_truth"] is False
    assert artifacts["4ca4ed42171c23d60ef89493559808ef2789a19e"]["status"] == "UNREACHABLE"
    assert artifacts["4ca4ed42171c23d60ef89493559808ef2789a19e"]["source_truth"] is False
    review_artifact = artifacts["1a6b7b0b463968f3161e048bd7936dc06505a3bb"]
    assert review_artifact["status"] == "PRESENT_ON_REVIEW_BRANCH"
    assert review_artifact["canonical_status"] == "PENDING_REVIEW"
    assert review_artifact["repo_name"] == "openclaw-eyes"
    assert review_artifact["branch_name"] == "codex/system-knowledge-registry-v0-local"
    assert review_artifact["source_truth"] is False


def test_source_of_truth_map_includes_required_ownership_boundaries():
    payload = registry.build_openclaw_estate_topology_registry(generated_at=FIXED_NOW)
    areas = _areas_by_id(payload)

    assert areas["mission_control_app"]["owner_classification"] == "MAC_APP"
    assert areas["mac_excel_edge_worker"]["primary_working_copy_id"] == "mac_mission_control_app"
    assert areas["access_broker"]["owner_classification"] == "SPLIT_MAC_UI_BACKEND_POLICY"
    assert areas["live_arts_invoice_bundle"]["primary_working_copy_id"] == "pc_openclaw_eyes_backend"
    assert areas["capital_hilton_invoice_bundle"]["primary_working_copy_id"] == "pc_openclaw_eyes_backend"
    assert areas["request_response_service"]["primary_working_copy_id"] == "pc_openclaw_eyes_backend"
    assert areas["hermes"]["primary_working_copy_id"] == "pc_openclaw_eyes_backend"
    assert areas["chief_guardian_cassandra_clara_runtime"]["owner_repo_key"] == "openclaw-runtime"
    assert areas["evidence_grounded_context_registry"]["status"] == "PRESENT_ON_REVIEW_BRANCH"
    assert areas["evidence_grounded_context_registry"]["current_state"] == "PRESENT_ON_REVIEW_BRANCH"
    assert areas["evidence_grounded_context_registry"]["canonical_status"] == "PENDING_REVIEW"
    assert areas["evidence_grounded_context_registry"]["owner_repo_key"] == "openclaw-eyes"
    assert areas["evidence_grounded_context_registry"]["primary_working_copy_id"] == "pc_openclaw_eyes_backend"
    assert areas["evidence_grounded_context_registry"]["review_branch"] == "codex/system-knowledge-registry-v0-local"
    assert (
        areas["evidence_grounded_context_registry"]["review_commit"]
        == "1a6b7b0b463968f3161e048bd7936dc06505a3bb"
    )
    assert areas["mac_openclaw_eyes_context_repo"]["owner_classification"] == "EYES_CONTEXT_REPO"
    assert areas["bridge_mirror_transport"]["ownership_rule"] == "/mnt/e/openclaw <-> /Volumes/openclaw_e is transport, not source truth."


def test_known_unknowns_and_recommended_actions_are_complete():
    payload = registry.build_openclaw_estate_topology_registry(generated_at=FIXED_NOW)
    unknown_ids = {item["unknown_id"] for item in payload["known_unknowns"]}
    actions = {item["action_id"]: item for item in payload["recommended_actions"]}

    assert payload["known_unknown_count"] == 7
    assert "canonical_system_knowledge_registry_home" in unknown_ids
    assert "codex_web_commits_unreachable" in unknown_ids
    assert "mac_app_remote_backup_strategy" in unknown_ids
    assert "dual_openclaw_eyes_long_term" in unknown_ids
    assert "runtime_actor_canonical_home" in unknown_ids
    assert "hermes_first_read_repo" in unknown_ids
    assert "mac_bridge_permission_model" in unknown_ids
    assert actions["install_estate_topology_registry"]["status"] == "CONFIRMED"
    assert actions["keep_live_arts_pdf_blocked_until_mac_architecture_resolved"]["status"] == "PLANNED"


def test_export_writes_json_operator_sqlite_schema_and_seed(tmp_path, capsys):
    read_root = tmp_path / "generated" / "read_models"
    system_root = tmp_path / "generated" / "system_knowledge"

    result = registry.export_openclaw_estate_topology_registry(
        read_model_root=read_root,
        system_knowledge_root=system_root,
        generated_at=FIXED_NOW,
    )

    json_path = read_root / registry.JSON_EXPORT_NAME
    operator_path = read_root / registry.OPERATOR_EXPORT_NAME
    sqlite_path = system_root / registry.SQLITE_EXPORT_NAME
    schema_path = system_root / registry.SCHEMA_EXPORT_NAME
    seed_path = system_root / registry.SEED_EXPORT_NAME

    assert result.machine_count == 2
    assert json.loads(json_path.read_text(encoding="utf-8"))["repo_working_copy_count"] == 5
    operator_text = operator_path.read_text(encoding="utf-8")
    assert "OpenClaw Estate Topology Registry" in operator_text
    assert "CREATE TABLE" not in operator_text
    assert "INSERT INTO" not in operator_text
    assert sqlite_path.exists()
    assert schema_path.read_text(encoding="utf-8").count("CREATE TABLE") == len(registry.REQUIRED_SQLITE_TABLES)
    assert "INSERT INTO repo_working_copy" in seed_path.read_text(encoding="utf-8")

    assert export_main(
        [
            "--read-model-root",
            str(read_root),
            "--system-knowledge-root",
            str(system_root),
            "--format",
            "json",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["schema_version"] == registry.READ_MODEL_VERSION


def test_sqlite_required_tables_queries_and_integrity(tmp_path):
    read_root = tmp_path / "generated" / "read_models"
    system_root = tmp_path / "generated" / "system_knowledge"
    registry.export_openclaw_estate_topology_registry(
        read_model_root=read_root,
        system_knowledge_root=system_root,
        generated_at=FIXED_NOW,
    )

    db_path = system_root / registry.SQLITE_EXPORT_NAME
    connection = sqlite3.connect(db_path)
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert set(registry.REQUIRED_SQLITE_TABLES).issubset(tables)
        assert connection.execute("SELECT COUNT(*) FROM machine").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM repo_working_copy").fetchone()[0] == 5
        assert connection.execute("SELECT COUNT(DISTINCT repo_key) FROM repo_working_copy").fetchone()[0] == 3
        assert connection.execute("SELECT COUNT(*) FROM known_unknown").fetchone()[0] == 7
        assert connection.execute(
            "SELECT owner_classification FROM source_of_truth_area WHERE area_id = 'live_arts_invoice_bundle'"
        ).fetchone()[0] == "PC_BACKEND"
        assert connection.execute(
            "SELECT status FROM codex_web_artifact WHERE commit_ref = '33e00a6'"
        ).fetchone()[0] == "UNREACHABLE"
        assert connection.execute(
            "SELECT source_truth FROM codex_web_artifact WHERE commit_ref = '4ca4ed42171c23d60ef89493559808ef2789a19e'"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT canonical_status FROM codex_web_artifact WHERE commit_ref = '1a6b7b0b463968f3161e048bd7936dc06505a3bb'"
        ).fetchone()[0] == "PENDING_REVIEW"
        assert connection.execute(
            "SELECT branch_name FROM registry_presence WHERE registry_id = 'evidence_grounded_context_registry'"
        ).fetchone()[0] == "codex/system-knowledge-registry-v0-local"
    finally:
        connection.close()


def test_registry_adds_no_runtime_or_external_authority():
    payload = registry.build_openclaw_estate_topology_registry(generated_at=FIXED_NOW)

    for key, expected in registry.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected


def test_source_does_not_import_or_call_live_authority_surfaces():
    source_files = [
        Path("openclaw_estate_topology_registry.py"),
        Path("scripts/export_openclaw_estate_topology_registry.py"),
    ]
    forbidden = [
        "import subprocess",
        "subprocess.",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "smtplib",
        "selenium",
        "playwright",
        "pyautogui",
        "openpyxl",
        "systemctl",
        "launchctl",
        "shell=True",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for forbidden_text in forbidden:
            assert forbidden_text not in text

    tree = ast.parse(Path("openclaw_estate_topology_registry.py").read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "subprocess" not in imported
