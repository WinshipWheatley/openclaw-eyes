import json
import sqlite3
from pathlib import Path

from scripts.build_sync_health import main as build_main
from scripts.export_sync_health_read_model import main as export_main
from scripts.query_sync_health import main as query_main
from sync_health import (
    NO_AUTHORITY_FLAGS,
    build_sync_health_read_model,
    build_sync_health_report,
    build_sync_health_snapshot,
    export_sync_health_read_model,
    sha256_file,
    sync_health_table_names,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture_root(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "openclaw"
    read_models = root / "generated" / "read_models"
    read_models.mkdir(parents=True, exist_ok=True)
    _write(read_models / "alpha.json", '{"alpha": true}\n')
    _write(read_models / "beta_OPERATOR.md", "# Beta\n")
    return root, read_models


def _manifest_for(read_models: Path, *, omit: set[str] | None = None, mismatch: set[str] | None = None, extra: bool = False) -> dict:
    omit = omit or set()
    mismatch = mismatch or set()
    records = []
    for path in sorted(read_models.iterdir()):
        if not path.is_file() or path.name in omit:
            continue
        digest = sha256_file(path)
        if path.name in mismatch:
            digest = "0" * 64
        records.append({"relative_path": path.name, "content_hash": digest, "size_bytes": path.stat().st_size})
    if extra:
        records.append({"relative_path": "orphan.json", "content_hash": "1" * 64, "size_bytes": 1})
    return {"path_records": records}


def _proof_files(tmp_path: Path, manifest_hash: str) -> dict[str, Path]:
    paths = {
        "mac_status": tmp_path / "share" / "shuttle" / "from_mac" / "read_model_sync_agent_status.json",
        "mac_completion": tmp_path / "share" / "shuttle" / "from_mac" / "read_model_sync_completed.json",
        "pc_state": tmp_path / "state" / "read_model_import_agent_state.json",
        "pc_log": tmp_path / "logs" / "windows_task_read_model_import.log",
        "windows_log": tmp_path / "share" / "windows_tasks" / "logs" / "OpenClawReadModelImport.log",
        "request_marker": Path("/mnt/e/openclaw/shuttle/to_mac/read_model_sync_required.json"),
    }
    _write(
        paths["mac_status"],
        json.dumps(
            {
                "status": "idle",
                "generated_at": "2026-05-15T00:00:00+00:00",
                "marker_seen": True,
                "manifest_written": True,
            }
        )
        + "\n",
    )
    _write(
        paths["mac_completion"],
        json.dumps(
            {
                "status": "synced",
                "generated_at": "2026-05-15T00:01:00+00:00",
                "manifest_sha256": manifest_hash,
            }
        )
        + "\n",
    )
    _write(
        paths["pc_state"],
        json.dumps(
            {
                "status": "success",
                "last_imported_at": "2026-05-15T00:02:00+00:00",
                "last_successful_manifest_sha256": manifest_hash,
            }
        )
        + "\n",
    )
    _write(paths["pc_log"], "pc import ok\n")
    _write(paths["windows_log"], "windows task ok\n")
    return paths


def _build_with_manifest(
    tmp_path: Path,
    *,
    manifest_payload: dict,
    proof: bool = True,
    pc_import_time: str | None = None,
    pc_import_hash: str | None = None,
):
    root, read_models = _fixture_root(tmp_path)
    manifest = tmp_path / "share" / "mac_generated_read_models_manifest.json"
    _write(manifest, json.dumps(manifest_payload) + "\n")
    manifest_hash = sha256_file(manifest)
    paths = _proof_files(tmp_path, manifest_hash) if proof else {
        "mac_status": tmp_path / "missing_status.json",
        "mac_completion": tmp_path / "missing_completion.json",
        "pc_state": tmp_path / "missing_state.json",
        "pc_log": tmp_path / "missing.log",
        "windows_log": tmp_path / "missing_windows.log",
        "request_marker": Path("/mnt/e/openclaw/shuttle/to_mac/read_model_sync_required.json"),
    }
    if proof and (pc_import_time or pc_import_hash):
        state = json.loads(paths["pc_state"].read_text(encoding="utf-8"))
        if pc_import_time:
            state["last_imported_at"] = pc_import_time
        if pc_import_hash:
            state["last_successful_manifest_sha256"] = pc_import_hash
        paths["pc_state"].write_text(json.dumps(state) + "\n", encoding="utf-8")
    result = build_sync_health_snapshot(
        db_path=tmp_path / "ledger.sqlite",
        manifest_path=manifest,
        read_model_root=read_models,
        repo_root=root,
        mac_status_path=paths["mac_status"],
        mac_completion_path=paths["mac_completion"],
        pc_import_state_path=paths["pc_state"],
        pc_task_log_path=paths["pc_log"],
        windows_task_log_path=paths["windows_log"],
        request_marker_path=paths["request_marker"],
        run_id="sync_health_fixture",
    )
    return result, tmp_path / "ledger.sqlite", paths


def _latest(db_path: Path) -> dict:
    report = build_sync_health_report(db_path=db_path, report="summary")
    return report["latest_snapshot"]


def test_schema_initializes(tmp_path):
    tables = set(sync_health_table_names(tmp_path / "ledger.sqlite"))

    assert {
        "sync_health_runs",
        "sync_health_snapshots",
        "sync_health_sources",
        "sync_health_recommendations",
        "sync_health_receipts",
    } <= tables


def test_trusted_mirror_produces_trusted_status(tmp_path):
    root, read_models = _fixture_root(tmp_path)
    manifest_payload = _manifest_for(read_models)
    result, db_path, _paths = _build_with_manifest(tmp_path, manifest_payload=manifest_payload)
    snapshot = _latest(db_path)

    assert result.trust_status == "trusted"
    assert snapshot["trust_status"] == "trusted"
    assert snapshot["mirror_status"] == "ok"
    assert snapshot["missing_expected"] == 0
    assert snapshot["hash_mismatch"] == 0
    assert snapshot["recommended_fix_kind"] == "none"
    assert snapshot["can_request_fix_from_app"] is False
    assert snapshot["display_status"] == "current"
    assert snapshot["next_expected_actor"] == "none"
    assert root.is_dir()


def test_missing_expected_produces_stale_needs_mac_sync(tmp_path):
    _root, read_models = _fixture_root(tmp_path)
    result, db_path, _paths = _build_with_manifest(
        tmp_path,
        manifest_payload=_manifest_for(read_models, omit={"beta_OPERATOR.md"}),
    )
    snapshot = _latest(db_path)

    assert result.trust_status == "stale_needs_mac_sync"
    assert snapshot["mirror_status"] == "needs_mac_sync"
    assert snapshot["recommended_fix_kind"] == "request_mac_sync"
    assert snapshot["can_request_fix_from_app"] is True
    assert snapshot["display_status"] == "needs_mac_sync"
    assert snapshot["next_expected_actor"] == "mac_sync_agent"
    assert snapshot["missing_files"] == ["beta_OPERATOR.md"]
    assert snapshot["request_marker_path"].endswith("read_model_sync_required.json")


def test_hash_mismatch_produces_stale_needs_mac_sync(tmp_path):
    _root, read_models = _fixture_root(tmp_path)
    result, db_path, _paths = _build_with_manifest(
        tmp_path,
        manifest_payload=_manifest_for(read_models, mismatch={"alpha.json"}),
    )
    snapshot = _latest(db_path)

    assert result.trust_status == "stale_needs_mac_sync"
    assert snapshot["mirror_status"] == "needs_mac_sync"
    assert snapshot["recommended_fix_kind"] == "request_mac_sync"
    assert snapshot["stale_files"] == ["alpha.json"]
    assert snapshot["can_request_fix_from_app"] is True
    assert snapshot["display_status"] == "needs_mac_sync"
    assert snapshot["next_expected_actor"] == "mac_sync_agent"


def test_mac_completion_newer_than_pc_import_produces_needs_pc_import(tmp_path):
    _root, read_models = _fixture_root(tmp_path)
    result, db_path, _paths = _build_with_manifest(
        tmp_path,
        manifest_payload=_manifest_for(read_models),
        pc_import_time="2026-05-15T00:00:10+00:00",
    )
    snapshot = _latest(db_path)

    assert result.trust_status == "stale_needs_pc_import"
    assert snapshot["mirror_status"] == "needs_pc_import"
    assert snapshot["recommended_fix_kind"] == "wait_for_pc_import"
    assert snapshot["can_request_fix_from_app"] is False
    assert snapshot["display_status"] == "waiting_for_pc_import"
    assert snapshot["next_expected_actor"] == "pc_import_task"
    assert snapshot["next_safe_move"] == "Mac sync appears complete. Waiting for PC import task."


def test_degraded_if_proof_files_missing(tmp_path):
    _root, read_models = _fixture_root(tmp_path)
    result, db_path, _paths = _build_with_manifest(
        tmp_path,
        manifest_payload=_manifest_for(read_models),
        proof=False,
    )
    snapshot = _latest(db_path)

    assert result.trust_status == "degraded"
    assert snapshot["mirror_status"] == "ok"
    assert snapshot["recommended_fix_kind"] == "inspect_automation"
    assert snapshot["can_request_fix_from_app"] is False
    assert snapshot["display_status"] == "degraded"
    assert snapshot["next_expected_actor"] == "operator_review"
    assert snapshot["windows_task_log_present"] is False


def test_extra_files_require_manual_review(tmp_path):
    _root, read_models = _fixture_root(tmp_path)
    result, db_path, _paths = _build_with_manifest(
        tmp_path,
        manifest_payload=_manifest_for(read_models, extra=True),
    )
    snapshot = _latest(db_path)

    assert result.trust_status == "mismatch"
    assert snapshot["mirror_status"] == "error"
    assert snapshot["recommended_fix_kind"] == "manual_review"
    assert snapshot["can_request_fix_from_app"] is False
    assert snapshot["display_status"] == "manual_review"
    assert snapshot["next_expected_actor"] == "operator_review"
    assert snapshot["extra_files"] == ["orphan.json"]


def test_read_model_export_exists_and_no_authority_flags_are_false(tmp_path):
    _root, read_models = _fixture_root(tmp_path)
    _result, db_path, _paths = _build_with_manifest(tmp_path, manifest_payload=_manifest_for(read_models))

    summary = export_sync_health_read_model(
        db_path=db_path,
        export_root=tmp_path / "exports",
        repo_root=tmp_path,
    )
    payload = json.loads((tmp_path / summary["json_path"]).read_text(encoding="utf-8"))
    operator_text = (tmp_path / summary["operator_path"]).read_text(encoding="utf-8")

    assert payload["trust_status"] == "trusted"
    assert payload["recommended_fix"]["kind"] == "none"
    assert payload["display_status"] == "current"
    assert payload["next_expected_actor"] == "none"
    assert payload["recommended_fix"]["next_expected_actor"] == "none"
    assert "OpenClaw Sync Health" in operator_text
    assert all(value is False for value in payload["no_authority_flags"].values())
    assert all(value is False for value in NO_AUTHORITY_FLAGS.values())


def test_reports_and_scripts_work(tmp_path, capsys):
    _root, read_models = _fixture_root(tmp_path)
    _result, db_path, _paths = _build_with_manifest(tmp_path, manifest_payload=_manifest_for(read_models))
    assert query_main(["--db", str(db_path), "--report", "summary", "--format", "operator"]) == 0
    assert export_main(["--db", str(db_path), "--export-root", str(tmp_path / "exports"), "--format", "operator"]) == 0
    out = capsys.readouterr().out

    assert "Trust status: `trusted`" in out
    assert "Sync Health Read-Model Export v0" in out


def test_build_script_accepts_fixture_paths_without_destructive_behavior(tmp_path, capsys):
    root, read_models = _fixture_root(tmp_path)
    manifest = tmp_path / "share" / "mac_generated_read_models_manifest.json"
    _write(manifest, json.dumps(_manifest_for(read_models)) + "\n")
    manifest_hash = sha256_file(manifest)
    paths = _proof_files(tmp_path, manifest_hash)

    assert build_main(
        [
            "--db",
            str(tmp_path / "ledger.sqlite"),
            "--manifest",
            str(manifest),
            "--read-model-root",
            str(read_models),
            "--repo-root",
            str(root),
            "--mac-status",
            str(paths["mac_status"]),
            "--mac-completion",
            str(paths["mac_completion"]),
            "--pc-state",
            str(paths["pc_state"]),
            "--pc-log",
            str(paths["pc_log"]),
            "--windows-log",
            str(paths["windows_log"]),
            "--request-marker",
            str(paths["request_marker"]),
            "--format",
            "json",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["trust_status"] == "trusted"


def test_source_has_no_c_drive_defaults_or_disallowed_runtime_behavior():
    text = Path("sync_health.py").read_text(encoding="utf-8").lower()
    for token in [
        "/mnt/c/openclaw",
        "c:\\openclaw",
        "subprocess",
        "shell=true",
        "os.system",
        "docker run",
        "ollama run",
        "shutil.rmtree",
        "shutil.move",
        ".unlink(",
    ]:
        assert token not in text
