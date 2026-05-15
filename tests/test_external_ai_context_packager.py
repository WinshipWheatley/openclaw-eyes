import json
import sqlite3
from pathlib import Path

from external_ai_context_packager import (
    NO_AUTHORITY_FLAGS,
    build_external_ai_context_pack,
    build_external_ai_context_pack_report,
    context_pack_table_names,
    export_external_ai_context_pack_read_model,
    select_context_pack_read_model_records,
)
from scripts.build_external_ai_context_pack import main as build_main
from scripts.export_external_ai_context_pack_read_model import main as export_main
from scripts.query_external_ai_context_packs import main as query_main


def _write_read_model(root: Path, name: str, content: str | dict):
    path = root / "generated" / "read_models" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, dict):
        path.write_text(json.dumps(content, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        path.write_text(content, encoding="utf-8")
    return path


def _fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    read_models = repo / "generated" / "read_models"
    read_models.mkdir(parents=True)
    _write_read_model(repo, "generated_current_state.md", "# Current\n\nMission Control state.")
    _write_read_model(repo, "generated_next_actions.md", "# Next\n\nRun bounded lanes only.")
    _write_read_model(
        repo,
        "agent_runtime_readiness.json",
        {
            "schema_version": "fixture",
            "agent_count": 6,
            "ready_for_dry_run_count": 6,
            "latest_start_sequence_status": "ready_for_dry_run",
            "smoke_test_results": {"passed": 6, "failed": 0},
        },
    )
    _write_read_model(repo, "agent_runtime_readiness_OPERATOR.md", "# Runtime\n\nDry-run ready.")
    _write_read_model(repo, "intent_router.json", {"schema_version": "fixture", "intent_count": 2})
    _write_read_model(repo, "intent_router_OPERATOR.md", "# Router\n\nRoutes only.")
    _write_read_model(repo, "agent_lanes.json", {"schema_version": "fixture", "agent_count": 6, "lane_count": 6})
    _write_read_model(repo, "agent_lanes_OPERATOR.md", "# Lanes\n\nNo direct execution.")
    _write_read_model(repo, "operator_actions.json", {"schema_version": "fixture", "request_count": 1})
    _write_read_model(repo, "operator_actions_OPERATOR.md", "# Actions\n\nApproval required.")
    _write_read_model(repo, "new_safe_surface_OPERATOR.md", "# New Surface\n\nAutomatically selected operator summary.")
    _write_read_model(repo, "new_safe_surface.json", {"schema_version": "not_selected_raw_json"})
    _write_read_model(repo, "mac_generated_read_models_manifest.json", {"manifest": True})
    _write_read_model(repo, "ledger.sqlite", "not really sqlite")
    _write_read_model(repo, "temp_context.json", {"temp": True})
    _write_read_model(repo, ".hidden.md", "hidden")
    _write_read_model(repo, "secret_OPERATOR.md", "secret-ish path should be excluded")
    return repo


def _row(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def _rows(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_schema_initializes(tmp_path):
    tables = set(context_pack_table_names(tmp_path / "ledger.sqlite"))

    assert {
        "context_pack_runs",
        "context_packs",
        "context_pack_files",
        "context_pack_sources",
        "context_pack_profiles",
        "context_pack_safety_checks",
        "context_pack_receipts",
    } <= tables


def test_context_pack_builds_upload_ready_files_and_zip(tmp_path):
    repo = _fixture_repo(tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    export_root = repo / "generated" / "context_packs"

    result = build_external_ai_context_pack(
        db_path=db_path,
        repo_root=repo,
        read_model_root="generated/read_models",
        export_root=export_root,
        profile="chatgpt_project",
        world="build",
        focus="mission_control_current",
        run_id="context_pack_run_fixture",
    )

    pack_dir = export_root / "mission_control_current"
    manifest = json.loads((pack_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    selected_names = {path.name for path in (pack_dir / "selected_read_models").iterdir()}

    assert result.pack_id == "mission_control_current"
    assert (pack_dir / "00_START_HERE.md").exists()
    assert (pack_dir / "CURRENT_STATE.md").exists()
    assert (pack_dir / "UPLOAD_INSTRUCTIONS.md").exists()
    assert (pack_dir / "OpenClaw_ContextPack_mission_control_current.zip").exists()
    assert manifest["external_upload_allowed"] is False
    assert manifest["network_authority"] is False
    assert "agent_runtime_readiness.json" in selected_names
    assert "agent_runtime_readiness_OPERATOR.md" in selected_names
    assert "new_safe_surface_OPERATOR.md" in selected_names
    assert "new_safe_surface.json" not in selected_names
    assert "secret_OPERATOR.md" not in selected_names

    pack = _row(db_path, "SELECT * FROM context_packs WHERE pack_id = ?", ("mission_control_current",))
    assert pack["profile"] == "chatgpt_project"
    assert pack["raw_private_included"] == 0
    assert pack["no_go_included"] == 0
    assert pack["secrets_included"] == 0
    assert pack["external_upload_allowed"] == 0


def test_safe_dynamic_selection_excludes_manifests_temp_hidden_and_sensitive(tmp_path):
    repo = _fixture_repo(tmp_path)

    selected = select_context_pack_read_model_records(
        repo_root=repo,
        read_model_root="generated/read_models",
    )
    names = {record["relative_path"] for record in selected}

    assert "new_safe_surface_OPERATOR.md" in names
    assert "new_safe_surface.json" not in names
    assert "mac_generated_read_models_manifest.json" not in names
    assert "ledger.sqlite" not in names
    assert "temp_context.json" not in names
    assert ".hidden.md" not in names
    assert "secret_OPERATOR.md" not in names


def test_profile_limit_warning_is_recorded(tmp_path):
    repo = _fixture_repo(tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    for index in range(45):
        _write_read_model(repo, f"bulk_{index:02d}_OPERATOR.md", f"# Bulk {index}\n")

    result = build_external_ai_context_pack(
        db_path=db_path,
        repo_root=repo,
        export_root=repo / "generated" / "context_packs",
        read_model_root="generated/read_models",
        profile="chatgpt_project",
        run_id="context_pack_warning_fixture",
    )
    instructions = (
        repo / "generated" / "context_packs" / "mission_control_current" / "UPLOAD_INSTRUCTIONS.md"
    ).read_text(encoding="utf-8")

    assert result.warning_count >= 1
    assert "exceeds the chatgpt_project target" in instructions


def test_query_scripts_and_read_model_export_work(tmp_path, capsys):
    repo = _fixture_repo(tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    export_root = repo / "generated" / "context_packs"
    read_model_export_root = repo / "generated" / "read_models_export"

    assert build_main(
        [
            "--db",
            str(db_path),
            "--export-root",
            str(export_root),
            "--read-model-root",
            str(repo / "generated" / "read_models"),
            "--profile",
            "chatgpt_project",
            "--format",
            "operator",
        ]
    ) == 0
    assert "External AI Context Packager v0" in capsys.readouterr().out

    assert query_main(["--db", str(db_path), "--pack-id", "mission_control_current", "--format", "operator"]) == 0
    assert "Pack files:" in capsys.readouterr().out

    summary = export_external_ai_context_pack_read_model(db_path=db_path, export_root=read_model_export_root)
    assert summary["pack_count"] == 1
    payload = json.loads((read_model_export_root / "external_ai_context_packs.json").read_text(encoding="utf-8"))
    assert payload["pack_count"] == 1
    assert payload["latest_pack"]["pack_id"] == "mission_control_current"
    assert payload["external_upload_allowed"] is False
    assert payload["browser_automation_allowed"] is False
    assert payload["network_authority"] is False
    assert all(value is False for value in payload["no_authority_flags"].values())

    assert export_main(["--db", str(db_path), "--export-root", str(read_model_export_root), "--format", "operator"]) == 0
    assert "External AI Context Packs Read-Model Export v0" in capsys.readouterr().out


def test_no_forbidden_external_or_destructive_behavior():
    text = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "external_ai_context_packager.py",
            "scripts/build_external_ai_context_pack.py",
            "scripts/query_external_ai_context_packs.py",
            "scripts/export_external_ai_context_pack_read_model.py",
        ]
    )
    forbidden = [
        "subprocess.",
        "shell=true",
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
        "apt install",
        "npm install",
        "pip install",
        ".unlink(",
        ".remove(",
        ".rmdir(",
        ".rename(",
        "selenium",
        "playwright",
    ]
    for token in forbidden:
        assert token not in text
    assert all(value is False for value in NO_AUTHORITY_FLAGS.values())
