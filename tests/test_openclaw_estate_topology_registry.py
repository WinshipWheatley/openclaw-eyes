import ast
import json
import re
import sqlite3
from pathlib import Path

import openclaw_estate_topology_registry as registry
from scripts.export_openclaw_estate_topology_registry import main as export_main


FIXED_NOW = "2026-05-30T18:30:00+00:00"
FIXED_REVIEW_COMMIT = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def _areas_by_id(payload: dict) -> dict[str, dict]:
    return {area["area_id"]: area for area in payload["source_of_truth_areas"]}


def _reference_payload(
    commit: str = FIXED_REVIEW_COMMIT,
    *,
    resolution_status: str = "RESOLVED_REMOTE",
    main_commit: str = "",
    main_resolution_status: str = "UNREACHABLE",
) -> dict:
    reachable = resolution_status in {
        "RESOLVED_LOCAL",
        "RESOLVED_REMOTE",
        "RESOLVED_MAC_BRIDGE",
    }
    main_reachable = main_resolution_status in {
        "RESOLVED_LOCAL",
        "RESOLVED_REMOTE",
        "RESOLVED_MAC_BRIDGE",
    }
    git_branch_refs = [
        {
            "target_ref": registry.OPENCLAW_EYES_SYSTEM_KNOWLEDGE_REVIEW_BRANCH_REF,
            "repo_ref": registry.OPENCLAW_EYES_SYSTEM_KNOWLEDGE_REVIEW_BRANCH_REF,
            "local_path": "/home/openclaw",
            "remote_url": "https://github.com/WinshipWheatley/openclaw-eyes.git",
            "branch": registry.OPENCLAW_EYES_SYSTEM_KNOWLEDGE_REVIEW_BRANCH,
            "current_head_commit": commit if reachable else "",
            "reachable": reachable,
            "resolution_status": resolution_status,
            "resolution_source": "configured_remote" if resolution_status == "RESOLVED_REMOTE" else "",
            "local_status": "LOCAL_PATH_UNREACHABLE",
            "remote_status": "RESOLVED_REMOTE"
            if resolution_status == "RESOLVED_REMOTE"
            else "REMOTE_UNAVAILABLE",
            "mac_mirror_path": "/Users/hwinshipwheatley/Eyes",
            "mac_mirror_status": "LOCAL_PATH_UNREACHABLE",
            "mac_bridge_status": "MAC_BRIDGE_UNAVAILABLE",
            "dirty_status": "CLEAN",
            "dirty": False,
            "last_resolved_at": FIXED_NOW,
        }
    ]
    if main_resolution_status != "UNREACHABLE" or main_commit:
        git_branch_refs.append(
            {
                "target_ref": registry.OPENCLAW_EYES_MAIN_BRANCH_TARGET_REF,
                "repo_ref": "openclaw-eyes-main",
                "local_path": "",
                "remote_url": "https://github.com/WinshipWheatley/openclaw-eyes.git",
                "branch": registry.OPENCLAW_EYES_MAIN_BRANCH,
                "current_head_commit": main_commit if main_reachable else "",
                "reachable": main_reachable,
                "resolution_status": main_resolution_status,
                "resolution_source": "configured_remote"
                if main_resolution_status == "RESOLVED_REMOTE"
                else "",
                "local_status": "LOCAL_PATH_UNREACHABLE",
                "remote_status": "RESOLVED_REMOTE"
                if main_resolution_status == "RESOLVED_REMOTE"
                else "REMOTE_UNAVAILABLE",
                "mac_mirror_path": "",
                "mac_mirror_status": "",
                "mac_bridge_status": "",
                "dirty_status": "CLEAN",
                "dirty": False,
                "last_resolved_at": FIXED_NOW,
            }
        )
    return {
        "schema_version": "openclaw_reference_resolver_read_model_v0",
        "generated_at": FIXED_NOW,
        "git_branch_refs": git_branch_refs,
    }


def _build_payload(commit: str = FIXED_REVIEW_COMMIT) -> dict:
    return registry.build_openclaw_estate_topology_registry(
        generated_at=FIXED_NOW,
        reference_resolver_payload=_reference_payload(commit),
    )


def test_registry_is_deterministic_and_counts_estate_topology():
    first = _build_payload()
    second = _build_payload()

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
        "external_registry_materialization",
        "codex_web_artifact",
        "known_unknown",
        "recommended_action",
    }


def test_five_working_copies_preserve_machine_repo_roles():
    payload = _build_payload()
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
    payload = _build_payload()
    artifacts = {artifact["artifact_id"]: artifact for artifact in payload["codex_web_artifacts"]}

    assert artifacts["codex_web_registry_commit_33e00a6"]["status"] == "UNREACHABLE"
    assert artifacts["codex_web_registry_commit_33e00a6"]["source_truth"] is False
    assert artifacts["codex_web_registry_commit_4ca4ed42171c23d60ef89493559808ef2789a19e"]["status"] == "UNREACHABLE"
    assert artifacts["codex_web_registry_commit_4ca4ed42171c23d60ef89493559808ef2789a19e"]["source_truth"] is False
    review_artifact = artifacts["openclaw_eyes_system_knowledge_registry_review_branch"]
    assert review_artifact["status"] == "PRESENT_ON_REVIEW_BRANCH"
    assert review_artifact["canonical_status"] == "PENDING_REVIEW"
    assert review_artifact["repo_name"] == "openclaw-eyes"
    assert review_artifact["branch_name"] == "codex/system-knowledge-registry-v0-local"
    assert review_artifact["commit_ref"] == FIXED_REVIEW_COMMIT
    assert review_artifact["source_truth"] is False


def test_source_of_truth_map_includes_required_ownership_boundaries():
    payload = _build_payload()
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
        == FIXED_REVIEW_COMMIT
    )
    assert areas["mac_openclaw_eyes_context_repo"]["owner_classification"] == "EYES_CONTEXT_REPO"
    assert areas["bridge_mirror_transport"]["ownership_rule"] == "/mnt/e/openclaw <-> /Volumes/openclaw_e is transport, not source truth."


def test_known_unknowns_and_recommended_actions_are_complete():
    payload = _build_payload()
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


def test_matching_main_head_marks_system_knowledge_registry_canonical():
    payload = registry.build_openclaw_estate_topology_registry(
        generated_at=FIXED_NOW,
        reference_resolver_payload=_reference_payload(
            FIXED_REVIEW_COMMIT,
            main_commit=FIXED_REVIEW_COMMIT,
            main_resolution_status="RESOLVED_REMOTE",
        ),
    )
    areas = _areas_by_id(payload)
    registries = {row["registry_id"]: row for row in payload["registry_presence"]}
    artifacts = {row["artifact_id"]: row for row in payload["codex_web_artifacts"]}
    unknown_ids = {item["unknown_id"] for item in payload["known_unknowns"]}
    actions = {item["action_id"]: item for item in payload["recommended_actions"]}
    area = areas["evidence_grounded_context_registry"]
    registry_row = registries["evidence_grounded_context_registry"]
    artifact = artifacts["openclaw_eyes_system_knowledge_registry_review_branch"]
    summary = payload["reference_resolver_summary"]

    assert area["status"] == "CANONICAL_ON_MAIN"
    assert area["current_state"] == "CANONICAL_ON_MAIN"
    assert area["canonical_status"] == "CANONICAL"
    assert area["owner_classification"] == "PC_BACKEND_CANONICAL_MAIN"
    assert area["review_branch"] == "main"
    assert area["review_commit"] == FIXED_REVIEW_COMMIT
    assert "main is canonical" in area["ownership_rule"]
    assert registry_row["status"] == "CANONICAL_ON_MAIN"
    assert registry_row["canonical_status"] == "CANONICAL"
    assert registry_row["branch_name"] == "main"
    assert registry_row["commit_ref"] == FIXED_REVIEW_COMMIT
    assert artifact["status"] == "CANONICAL_ON_MAIN"
    assert artifact["canonical_status"] == "CANONICAL"
    assert artifact["source_truth"] is True
    assert artifact["branch_name"] == "main"
    assert payload["known_unknown_count"] == 6
    assert "canonical_system_knowledge_registry_home" not in unknown_ids
    assert actions["record_system_knowledge_registry_canonical_main"]["status"] == "CONFIRMED"
    assert summary["system_knowledge_registry_branch"] == "main"
    assert summary["system_knowledge_registry_current_head_commit"] == FIXED_REVIEW_COMMIT
    assert summary["system_knowledge_registry_current_state"] == "CANONICAL_ON_MAIN"
    assert summary["system_knowledge_registry_canonical_status"] == "CANONICAL"
    assert summary["system_knowledge_registry_main_contains_review_commit"] is True
    assert summary["system_knowledge_registry_review_commit"] == FIXED_REVIEW_COMMIT
    assert summary["system_knowledge_registry_main_commit"] == FIXED_REVIEW_COMMIT


def test_external_registry_materialization_keeps_openclaw_eyes_canonical_owner():
    external_index = {
        "import_status": "IMPORTED",
        "canonical_owner": "openclaw-eyes",
        "local_role": "READ_ONLY_EXTERNAL_INPUT",
        "commit_match": True,
        "source_repo": "openclaw-eyes",
        "source_branch": "main",
        "source_commit": FIXED_REVIEW_COMMIT,
        "artifact_count": 2,
        "artifacts": [
            {
                "cache_path": "generated/external_registries/openclaw-eyes/openclaw_system_knowledge_registry.json",
                "sha256": "sha256:json",
            },
            {
                "cache_path": "generated/external_registries/openclaw-eyes/openclaw_system_knowledge_registry.sqlite",
                "sha256": "sha256:sqlite",
            },
        ],
    }
    payload = registry.build_openclaw_estate_topology_registry(
        generated_at=FIXED_NOW,
        reference_resolver_payload=_reference_payload(
            FIXED_REVIEW_COMMIT,
            main_commit=FIXED_REVIEW_COMMIT,
            main_resolution_status="RESOLVED_REMOTE",
        ),
        external_registry_index_payload=external_index,
    )
    registries = {row["registry_id"]: row for row in payload["registry_presence"]}
    materialized = payload["external_registry_materialization"][0]

    assert registries["openclaw_eyes_system_knowledge_registry_external_input"]["status"] == "EXTERNAL_REGISTRY_MATERIALIZED"
    assert registries["openclaw_eyes_system_knowledge_registry_external_input"]["canonical_status"] == "CANONICAL"
    assert materialized["local_status"] == "EXTERNAL_REGISTRY_MATERIALIZED"
    assert materialized["canonical_owner"] == "openclaw-eyes"
    assert materialized["local_role"] == "READ_ONLY_EXTERNAL_INPUT"
    assert materialized["source_commit"] == FIXED_REVIEW_COMMIT
    assert "sha256:sqlite" in materialized["artifact_hashes_json"]


def test_export_writes_json_operator_sqlite_schema_and_seed(tmp_path, capsys):
    read_root = tmp_path / "generated" / "read_models"
    system_root = tmp_path / "generated" / "system_knowledge"

    result = registry.export_openclaw_estate_topology_registry(
        read_model_root=read_root,
        system_knowledge_root=system_root,
        generated_at=FIXED_NOW,
        reference_resolver_payload=_reference_payload(),
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
        reference_resolver_payload=_reference_payload(),
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
            f"SELECT canonical_status FROM codex_web_artifact WHERE commit_ref = '{FIXED_REVIEW_COMMIT}'"
        ).fetchone()[0] == "PENDING_REVIEW"
        assert connection.execute(
            "SELECT branch_name FROM registry_presence WHERE registry_id = 'evidence_grounded_context_registry'"
        ).fetchone()[0] == "codex/system-knowledge-registry-v0-local"
    finally:
        connection.close()


def test_estate_registry_uses_branch_ref_as_canonical_and_generated_commit_field(tmp_path):
    source_text = Path("openclaw_estate_topology_registry.py").read_text(encoding="utf-8")
    assert re.search(r"(review_commit|commit_ref)=\"[a-f0-9]{40}\"", source_text) is None

    read_root = tmp_path / "generated" / "read_models"
    system_root = tmp_path / "generated" / "system_knowledge"
    first_commit = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    second_commit = "cccccccccccccccccccccccccccccccccccccccc"
    registry.export_openclaw_estate_topology_registry(
        read_model_root=read_root,
        system_knowledge_root=system_root,
        generated_at=FIXED_NOW,
        reference_resolver_payload=_reference_payload(first_commit),
    )
    first = json.loads((read_root / registry.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    registry.export_openclaw_estate_topology_registry(
        read_model_root=read_root,
        system_knowledge_root=system_root,
        generated_at=FIXED_NOW,
        reference_resolver_payload=_reference_payload(second_commit),
    )
    second = json.loads((read_root / registry.JSON_EXPORT_NAME).read_text(encoding="utf-8"))

    first_area = _areas_by_id(first)["evidence_grounded_context_registry"]
    second_area = _areas_by_id(second)["evidence_grounded_context_registry"]
    assert first_area["review_branch"] == registry.OPENCLAW_EYES_SYSTEM_KNOWLEDGE_REVIEW_BRANCH
    assert first_area["review_commit"] == first_commit
    assert second_area["review_commit"] == second_commit
    assert first_area["review_commit"] != second_area["review_commit"]


def test_remote_unavailable_is_preserved_in_estate_registry():
    payload = registry.build_openclaw_estate_topology_registry(
        generated_at=FIXED_NOW,
        reference_resolver_payload=_reference_payload(
            "dddddddddddddddddddddddddddddddddddddddd",
            resolution_status="REMOTE_UNAVAILABLE",
        ),
    )
    areas = _areas_by_id(payload)
    artifact = {
        row["artifact_id"]: row for row in payload["codex_web_artifacts"]
    }["openclaw_eyes_system_knowledge_registry_review_branch"]

    assert areas["evidence_grounded_context_registry"]["status"] == "REMOTE_UNAVAILABLE"
    assert areas["evidence_grounded_context_registry"]["review_commit"] == ""
    assert artifact["status"] == "REMOTE_UNAVAILABLE"
    assert payload["reference_resolver_summary"][
        "system_knowledge_registry_resolution_status"
    ] == "REMOTE_UNAVAILABLE"


def test_mac_mirror_unreachable_is_represented_separately_from_remote_resolution():
    payload = _build_payload()
    summary = payload["reference_resolver_summary"]

    assert summary["system_knowledge_registry_resolution_status"] == "RESOLVED_REMOTE"
    assert summary["system_knowledge_registry_mac_mirror_status"] == "LOCAL_PATH_UNREACHABLE"
    assert summary["system_knowledge_registry_resolution_source"] == "configured_remote"


def test_registry_adds_no_runtime_or_external_authority():
    payload = _build_payload()

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
