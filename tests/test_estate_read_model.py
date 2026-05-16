import json
import sqlite3
from pathlib import Path

from corpus_atlas import init_corpus_atlas_schema
from estate_read_model import (
    build_estate_read_model,
    export_estate_read_model,
    format_estate_read_model,
    stable_json,
)
from project_capsule import (
    DEMO_PROJECT_ID,
    create_demo_project_capsule,
    link_project_capsule_modules,
)
from scripts.export_estate_read_model import main as export_main
from scripts.query_estate_read_model import main as query_main


FIXED_NOW = "2026-05-16T12:00:00+00:00"


def _write_read_model_fixtures(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "world_status.json").write_text('{"worlds": []}\n', encoding="utf-8")
    (root / "agent_presence_OPERATOR.md").write_text("# Agent Presence\n", encoding="utf-8")
    (root / "client_private.json").write_text('{"raw": "do not include"}\n', encoding="utf-8")
    (root / "token_status.json").write_text('{"token": "do not include"}\n', encoding="utf-8")


def _insert_corpus_root_fixture(db_path: Path) -> None:
    init_corpus_atlas_schema(db_path)
    conn = sqlite3.connect(db_path)
    try:
        for row in (
            (
                "pc_wsl_home_openclaw",
                "operating_home_repo",
                "pc_wsl",
                "internal_platform",
                None,
                None,
                None,
                "/home/openclaw",
                "Canonical OpenClaw Core",
                "active",
                "canonical_current",
                "scanned_metadata_only",
                None,
                "pc_wsl_home_openclaw",
            ),
            (
                "client_project_root",
                "client_project_root",
                "unknown",
                "client_project",
                "client_project_alpha",
                "client_alpha",
                "instance_alpha",
                "/private/client/acme/bank.xlsx",
                "Client project root",
                "future_placeholder",
                "requires_client_allowlist",
                "not_scanned",
                None,
                "future_client_project_capsule",
            ),
        ):
            conn.execute(
                """
INSERT INTO corpus_roots (
  root_id, root_kind, host_kind, owner_scope, project_id, client_id, instance_id,
  absolute_root, root_label, status, canonical_status, import_status,
  mirror_of_root_id, lineage_source, created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(root_id) DO UPDATE SET
  root_kind = excluded.root_kind,
  host_kind = excluded.host_kind,
  owner_scope = excluded.owner_scope,
  project_id = excluded.project_id,
  client_id = excluded.client_id,
  instance_id = excluded.instance_id,
  absolute_root = excluded.absolute_root,
  root_label = excluded.root_label,
  status = excluded.status,
  canonical_status = excluded.canonical_status,
  import_status = excluded.import_status,
  mirror_of_root_id = excluded.mirror_of_root_id,
  lineage_source = excluded.lineage_source,
  updated_at = excluded.updated_at
""".strip(),
                (*row, FIXED_NOW, FIXED_NOW),
            )
        conn.execute(
            """
INSERT INTO corpus_atlas_runs (
  run_id, root_id, atlas_version, started_at, completed_at, git_head, git_branch,
  repo_root, scan_mode, max_depth_policy, path_count, top_level_count,
  body_ingested, raw_sensitive_data_stored, runtime_authority,
  activation_allowed, backend_execution_authorized, source_basis_json, notes
) VALUES (
  'estate_fixture_run', 'pc_wsl_home_openclaw', 'corpus_atlas_fixture_v0',
  ?, ?, 'fixture', 'main', '/home/openclaw', 'fixture_metadata_only',
  'fixture_only', 0, 0, 0, 0, 0, 0, 0, '{}', 'fixture'
)
""".strip(),
            (FIXED_NOW, FIXED_NOW),
        )
        conn.commit()
    finally:
        conn.close()


def _seed_db(db_path: Path) -> None:
    create_demo_project_capsule(db_path=db_path, run_id="project_capsule_fixture")
    link_project_capsule_modules(db_path=db_path, project_id=DEMO_PROJECT_ID)
    _insert_corpus_root_fixture(db_path)


def test_estate_read_model_is_deterministic_and_non_authorizing(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    read_model_root = tmp_path / "generated" / "read_models"
    _write_read_model_fixtures(read_model_root)
    _seed_db(db_path)

    first = build_estate_read_model(
        db_path=db_path,
        generated_read_model_root=read_model_root,
        generated_at=FIXED_NOW,
    )
    second = build_estate_read_model(
        db_path=db_path,
        generated_read_model_root=read_model_root,
        generated_at=FIXED_NOW,
    )

    assert stable_json(first) == stable_json(second)
    assert first["schema_version"] == "estate_topology_v0"
    assert first["runtime_authority"] is False
    assert first["estate_registry_schema_created"] is False
    assert first["repo_split_allowed"] is False
    assert first["raw_data_visibility"] is False
    assert first["client_private_contents_exported"] is False
    assert first["backend_node_schema"]["openclaw_nodes_schema_available"] is True
    assert first["backend_node_schema"]["node_records_proven"] is False


def test_estate_read_model_uses_existing_primitives_and_redacts_client_paths(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    read_model_root = tmp_path / "generated" / "read_models"
    _write_read_model_fixtures(read_model_root)
    _seed_db(db_path)

    payload = build_estate_read_model(
        db_path=db_path,
        generated_read_model_root=read_model_root,
        generated_at=FIXED_NOW,
    )
    roots = {item["root_id"]: item for item in payload["corpus_roots"]["roots"]}
    capsule = payload["project_capsules"]["capsules"][0]
    generated_files = {item["relative_path"] for item in payload["generated_read_models"]["files"]}
    rendered_json = stable_json(payload)
    rendered_operator = format_estate_read_model(payload)

    assert roots["pc_wsl_home_openclaw"]["path_display"] == "/home/openclaw"
    assert roots["client_project_root"]["path_redacted"] is True
    assert roots["client_project_root"]["path_display"] == "redacted://client_project_root"
    assert "bank.xlsx" not in rendered_json
    assert "/private/client/acme" not in rendered_json
    assert "bank.xlsx" not in rendered_operator
    assert "project_capsule.py" == payload["project_capsules"]["source"]
    assert capsule["project_id"] == DEMO_PROJECT_ID
    assert capsule["selected_modules"]
    assert all(item["runtime_authority"] is False for item in capsule["selected_modules"])
    assert "world_status.json" in generated_files
    assert "agent_presence_OPERATOR.md" in generated_files
    assert "client_private.json" not in generated_files
    assert "token_status.json" not in generated_files


def test_estate_export_and_query_scripts_write_expected_files(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    read_model_root = tmp_path / "generated" / "read_models"
    export_root = tmp_path / "exports"
    _write_read_model_fixtures(read_model_root)
    _seed_db(db_path)

    summary = export_estate_read_model(
        db_path=db_path,
        export_root=export_root,
        generated_read_model_root=read_model_root,
    )
    payload = json.loads((export_root / "estate_topology.json").read_text(encoding="utf-8"))

    assert summary["estate_registry_schema_created"] is False
    assert payload["schema_version"] == "estate_topology_v0"
    assert (export_root / "estate_topology_OPERATOR.md").is_file()

    export_exit = export_main(
        [
            "--db",
            str(db_path),
            "--export-root",
            str(export_root),
            "--generated-read-model-root",
            str(read_model_root),
            "--format",
            "operator",
        ]
    )
    assert export_exit == 0
    assert "Estate Read-Model v0" in capsys.readouterr().out

    query_exit = query_main(
        [
            "--db",
            str(db_path),
            "--generated-read-model-root",
            str(read_model_root),
            "--format",
            "json",
        ]
    )
    assert query_exit == 0
    assert '"schema_version": "estate_topology_v0"' in capsys.readouterr().out


def test_estate_read_model_creates_no_estate_schema(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    read_model_root = tmp_path / "generated" / "read_models"
    _write_read_model_fixtures(read_model_root)
    _seed_db(db_path)

    build_estate_read_model(
        db_path=db_path,
        generated_read_model_root=read_model_root,
        generated_at=FIXED_NOW,
    )
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'estate_%'"
        ).fetchall()
    finally:
        conn.close()

    assert rows == []


def test_estate_sources_have_no_legacy_runtime_network_or_send_paths():
    source_files = [
        Path("estate_read_model.py"),
        Path("scripts/export_estate_read_model.py"),
        Path("scripts/query_estate_read_model.py"),
    ]
    forbidden = [
        "/home/openclaw_external/openclaw-runtime",
        "import subprocess",
        "subprocess.",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "send_message",
        "reply_text",
        "smtplib",
        "git clone",
        "git push",
        "docker run",
        "shell=true",
        "eval(",
        "exec(",
    ]
    for path in source_files:
        lowered = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in lowered
