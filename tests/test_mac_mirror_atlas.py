import json
import sqlite3
from pathlib import Path

import pytest

from corpus_atlas import run_corpus_atlas
from mac_mirror_atlas import (
    EXPECTED_GENERATED_READ_MODEL_FILES,
    build_root_manifest,
    import_root_manifest,
    query_mac_mirror_report_section,
    reject_broad_root,
)
from scripts.build_root_manifest import main as build_manifest_main
from scripts.import_root_manifest import main as import_manifest_main
from scripts.query_corpus_atlas import main as query_corpus_main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _pc_root(tmp_path: Path) -> Path:
    root = tmp_path / "pc_openclaw"
    root.mkdir()
    _write_json(root / "generated" / "read_models" / "source_inventory.json", {"same": True})
    _write_json(root / "generated" / "read_models" / "helm_state.json", {"pc": True})
    _write_json(root / "generated" / "read_models" / "world_domain_registry.json", {"worlds": []})
    _write_json(root / "generated" / "read_models" / "world_status.json", {})
    _write_json(root / "generated" / "read_models" / "artifact_registry.json", {})
    _write_json(root / "generated" / "read_models" / "runtime_activation_gate.json", {})
    _write_json(root / "generated" / "read_models" / "evidence_freshness.json", {})
    return root


def _mac_generated_root(tmp_path: Path) -> Path:
    root = tmp_path / "mac_generated"
    root.mkdir()
    _write_json(root / "source_inventory.json", {"same": True})
    _write_json(root / "helm_state.json", {"mac": True})
    _write_json(root / "world_domain_registry.json", {"worlds": []})
    (root / ".ssh").mkdir()
    (root / ".ssh" / "id_rsa").write_text("private key fixture", encoding="utf-8")
    (root / "secrets").mkdir()
    (root / "secrets" / "token.txt").write_text("token fixture", encoding="utf-8")
    return root


def _mac_app_root(tmp_path: Path) -> Path:
    root = tmp_path / "mission_control"
    (root / "OpenClaw Mission Control").mkdir(parents=True)
    (root / "OpenClaw Mission Control" / "App.swift").write_text(
        "import SwiftUI\nstruct AppRoot {}\n",
        encoding="utf-8",
    )
    (root / "OpenClaw Mission Control.xcodeproj").mkdir()
    (root / "OpenClaw Mission Control.xcodeproj" / "project.pbxproj").write_text(
        "project fixture\n",
        encoding="utf-8",
    )
    (root / "DerivedData").mkdir()
    (root / "DerivedData" / "build.log").write_text("build product fixture", encoding="utf-8")
    (root / ".private").mkdir()
    (root / ".private" / "note.txt").write_text("private fixture", encoding="utf-8")
    return root


def _rows(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_manifest_builder_rejects_broad_roots(tmp_path):
    for root in ("", "/", "/home", "/Users", "C:\\"):
        with pytest.raises(ValueError):
            reject_broad_root(root)

    missing = tmp_path / "missing"
    with pytest.raises(ValueError):
        reject_broad_root(str(missing))


def test_manifest_builder_scans_explicit_root_only_and_contains_no_raw_bodies(tmp_path):
    root = _mac_generated_root(tmp_path)
    result = build_root_manifest(
        root=root,
        root_id="mac_generated_read_models",
        root_kind="generated_read_model_mirror",
        host_kind="mac",
        owner_scope="internal_platform",
    )

    relatives = {record["relative_path"] for record in result.manifest["path_records"]}

    assert "source_inventory.json" in relatives
    assert ".ssh" in relatives
    assert ".ssh/id_rsa" not in relatives
    assert "secrets" in relatives
    assert "secrets/token.txt" not in relatives
    assert all(not str(path).startswith(str(tmp_path.parent)) for path in relatives)
    for record in result.manifest["path_records"]:
        assert {"body", "content", "raw_body", "file_body", "text"}.isdisjoint(record)


def test_no_go_sensitive_files_are_metadata_only_and_not_hashed(tmp_path):
    root = _mac_generated_root(tmp_path)
    result = build_root_manifest(
        root=root,
        root_id="mac_generated_read_models",
        root_kind="generated_read_model_mirror",
        host_kind="mac",
        owner_scope="internal_platform",
    )
    by_path = {record["relative_path"]: record for record in result.manifest["path_records"]}

    assert by_path["source_inventory.json"]["content_hash"]
    assert by_path["source_inventory.json"]["hash_algorithm"] == "sha256"
    assert by_path[".ssh"]["raw_content_eligibility"] == "no_go"
    assert by_path[".ssh"]["content_hash"] is None
    assert by_path["secrets"]["raw_content_eligibility"] == "no_go"
    assert by_path["secrets"]["content_hash"] is None


def test_mission_control_app_manifest_classifies_source_as_noncanonical_metadata(tmp_path):
    root = _mac_app_root(tmp_path)
    result = build_root_manifest(
        root=root,
        root_id="mac_mission_control_app",
        root_kind="app_repo",
        host_kind="mac",
        owner_scope="internal_platform",
    )
    by_path = {record["relative_path"]: record for record in result.manifest["path_records"]}
    swift = by_path["OpenClaw Mission Control/App.swift"]

    assert swift["source_role"] == "source_code"
    assert swift["freshness_label"] == "source_claim"
    assert swift["canonicality"] == "tracked_source"
    assert swift["retrieval_eligibility"] == "metadata_only"
    assert swift["ingestion_eligibility"] == "metadata_only"
    assert by_path["DerivedData"]["content_hash"] is None
    assert "DerivedData/build.log" not in by_path
    assert by_path[".private"]["content_hash"] is None


def test_import_upserts_mac_root_and_paths_without_truth_authority(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    root = _mac_generated_root(tmp_path)
    manifest_path = tmp_path / "mac_generated_manifest.json"
    build_root_manifest(
        root=root,
        root_id="mac_generated_read_models",
        root_kind="generated_read_model_mirror",
        host_kind="mac",
        owner_scope="internal_platform",
        output=manifest_path,
    )

    result = import_root_manifest(
        manifest_path=manifest_path,
        db_path=db_path,
        run_id="manifest_import_run",
    )

    root_row = _rows(
        db_path,
        """
SELECT root_kind, host_kind, owner_scope, canonical_status, import_status
FROM corpus_roots
WHERE root_id = 'mac_generated_read_models'
""",
    )[0]
    run_row = _rows(
        db_path,
        """
SELECT atlas_version, body_ingested, raw_sensitive_data_stored, runtime_authority,
       activation_allowed, backend_execution_authorized
FROM corpus_atlas_runs
WHERE run_id = 'manifest_import_run'
""",
    )[0]
    path_count = _rows(
        db_path,
        "SELECT COUNT(*) FROM corpus_paths WHERE root_id = 'mac_generated_read_models' AND run_id = 'manifest_import_run'",
    )[0][0]

    assert result.root_id == "mac_generated_read_models"
    assert root_row == (
        "generated_read_model_mirror",
        "mac",
        "internal_platform",
        "non_canonical_mirror",
        "manifest_imported_metadata",
    )
    assert run_row == ("mac_mirror_atlas_v0", 0, 0, 0, 0, 0)
    assert path_count == result.path_count


def test_import_creates_mirror_matches_and_mismatches(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    pc_root = _pc_root(tmp_path)
    run_corpus_atlas(db_path=db_path, root=pc_root, run_id="pc_run")

    mac_root = _mac_generated_root(tmp_path)
    manifest_path = tmp_path / "mac_generated_manifest.json"
    build_root_manifest(
        root=mac_root,
        root_id="mac_generated_read_models",
        root_kind="generated_read_model_mirror",
        host_kind="mac",
        owner_scope="internal_platform",
        output=manifest_path,
    )
    result = import_root_manifest(
        manifest_path=manifest_path,
        db_path=db_path,
        run_id="mac_import_run",
    )

    mirror_rows = _rows(
        db_path,
        """
SELECT m.suggested_relative_path, m.status, m.mirror_kind
FROM corpus_mirror_candidates m
JOIN corpus_paths p ON p.path_id = m.path_id
WHERE m.mirror_root_id = 'mac_generated_read_models'
ORDER BY m.suggested_relative_path, m.status
""",
    )

    assert result.matched_mirror_candidates >= 1
    assert result.mismatched_mirror_candidates >= 1
    assert ("source_inventory.json", "matched_hash", "safe_content_hash_match") in mirror_rows
    assert ("helm_state.json", "hash_mismatch", "same_relative_path_hash_mismatch") in mirror_rows


def test_generated_read_model_mirror_report_lists_missing_extra_and_counts(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    pc_root = _pc_root(tmp_path)
    run_corpus_atlas(db_path=db_path, root=pc_root, run_id="pc_run")
    mac_root = _mac_generated_root(tmp_path)
    manifest_path = tmp_path / "mac_generated_manifest.json"
    build_root_manifest(
        root=mac_root,
        root_id="mac_generated_read_models",
        root_kind="generated_read_model_mirror",
        host_kind="mac",
        owner_scope="internal_platform",
        output=manifest_path,
    )
    import_root_manifest(manifest_path=manifest_path, db_path=db_path, run_id="mac_import_run")

    report = query_mac_mirror_report_section(
        db_path=db_path,
        section="generated-read-model-mirror",
    )

    assert report["run_id"] == "mac_import_run"
    assert "source_inventory.json" not in report["missing_expected_files"]
    assert "tool_inventory.json" in report["missing_expected_files"]
    assert set(report["missing_expected_files"]) <= set(EXPECTED_GENERATED_READ_MODEL_FILES)
    assert report["counts"]["observed"] >= 3
    assert report["counts"]["matched_hash"] >= 1
    assert report["counts"]["hash_mismatch"] >= 1


def test_query_corpus_atlas_mac_reports_work(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    mac_root = _mac_generated_root(tmp_path)
    manifest_path = tmp_path / "mac_generated_manifest.json"
    build_root_manifest(
        root=mac_root,
        root_id="mac_generated_read_models",
        root_kind="generated_read_model_mirror",
        host_kind="mac",
        owner_scope="internal_platform",
        output=manifest_path,
    )
    import_root_manifest(manifest_path=manifest_path, db_path=db_path, run_id="mac_import_run")

    exit_code = query_corpus_main(["--db", str(db_path), "--report", "mac-roots", "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["section"] == "mac-roots"
    assert any(item["root_id"] == "mac_generated_read_models" for item in payload["items"])


def test_cli_manifest_build_and_import_work_against_fixture(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    root = _mac_generated_root(tmp_path)
    manifest_path = tmp_path / "manifest.json"

    build_exit = build_manifest_main(
        [
            "--root-id",
            "mac_generated_read_models",
            "--root",
            str(root),
            "--root-kind",
            "generated_read_model_mirror",
            "--host-kind",
            "mac",
            "--owner-scope",
            "internal_platform",
            "--output",
            str(manifest_path),
            "--format",
            "json",
        ]
    )
    build_payload = json.loads(capsys.readouterr().out)
    import_exit = import_manifest_main(
        [
            "--manifest",
            str(manifest_path),
            "--db",
            str(db_path),
            "--run-id",
            "cli_import_run",
            "--format",
            "json",
        ]
    )
    import_payload = json.loads(capsys.readouterr().out)

    assert build_exit == 0
    assert import_exit == 0
    assert build_payload["raw_file_bodies_included"] is False
    assert import_payload["raw_file_bodies_imported"] is False
    assert import_payload["canonical_truth_promoted"] is False


def test_no_file_moves_deletes_or_raw_private_reads(tmp_path):
    root = _mac_generated_root(tmp_path)
    secret = root / ".ssh" / "id_rsa"
    manifest_path = tmp_path / "manifest.json"
    build_root_manifest(
        root=root,
        root_id="mac_generated_read_models",
        root_kind="generated_read_model_mirror",
        host_kind="mac",
        owner_scope="internal_platform",
        output=manifest_path,
    )
    import_root_manifest(manifest_path=manifest_path, db_path=tmp_path / "ledger.sqlite")

    assert secret.is_file()
    assert secret.read_text(encoding="utf-8") == "private key fixture"


def test_static_forbids_no_network_remote_copy_or_destructive_behavior():
    paths = [
        Path("mac_mirror_atlas.py"),
        Path("scripts/build_root_manifest.py"),
        Path("scripts/import_root_manifest.py"),
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    for forbidden in ("import requests", "import httpx", "urllib.request", "import socket", "import paramiko"):
        assert forbidden not in text
    assert "shell=True" not in text
    assert '["ssh"' not in text
    assert '["scp"' not in text
    assert '["rsync"' not in text
    assert ".rename(" not in text
    assert ".unlink(" not in text
    assert ".remove(" not in text
    assert ".rmdir(" not in text
    assert "shutil." not in text
