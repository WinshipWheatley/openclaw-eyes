import json
import os
import sqlite3
from pathlib import Path

from scripts.build_sync_health import main as build_main
from scripts.export_sync_health_read_model import main as export_main
from scripts.query_sync_health import main as query_main
from generated_read_model_files import canonical_generated_read_model_expected_files
from sync_health import (
    DEFAULT_MAP_SYNC_REQUEST_MARKER_PATH,
    STABLE_MAP_REQUIRED_FILES,
    NO_AUTHORITY_FLAGS,
    build_sync_health_map_raw_split,
    build_sync_health_read_model,
    build_sync_health_report,
    build_sync_health_snapshot,
    export_sync_health_read_model,
    refresh_sync_health_from_manifest,
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


def _write_map_bundle(read_models: Path, *, generation_id: str = "map_fixture", bundle_hash: str = "sha256:bundle") -> None:
    _write(
        read_models / "openclaw_map_manifest.json",
        json.dumps(
            {
                "schema_version": "openclaw_map_manifest_v0",
                "read_model_id": "openclaw_map_manifest",
                "map_generation_id": generation_id,
                "bundle_hash": bundle_hash,
            }
        )
        + "\n",
    )
    _write(
        read_models / "openclaw_map_snapshot.json",
        json.dumps(
            {
                "schema_version": "openclaw_map_snapshot_v0",
                "read_model_id": "openclaw_map_snapshot",
                "map_generation_id": generation_id,
                "threshold_map": {
                    "capital_hilton_finance_destiny": {
                        "current_phase": "HELM_THRESHOLD_LANE",
                        "resolution_route": "MOVE_TO_WORLD_ACTION",
                        "target_world": "Finance",
                    },
                    "system_awareness_discovery_steel_thread": {
                        "lane_id": "system_awareness_discovery",
                    },
                    "cue_autonomy_placement": {
                        "status": "post_threshold_post_security_candidate",
                    },
                },
                "authority_boundary": {
                    "future_gated_cue_autonomy": True,
                    "live_package_dispatch_allowed": False,
                },
            }
        )
        + "\n",
    )
    _write(read_models / "openclaw_map_OPERATOR.md", "# Stable Map\n")


def _write_security_ready_map_bundle(
    read_models: Path,
    *,
    generation_id: str = "map_3cf7a1d5f26147ae993a",
    bundle_hash: str = "sha256:3d59cfda37602e22a7cb02dab1afb899acb65fe043efadf032820d8f5bb7c1af",
) -> None:
    _write_map_bundle(read_models, generation_id=generation_id, bundle_hash=bundle_hash)
    _write(
        read_models / "openclaw_map_snapshot.json",
        json.dumps(
            {
                "schema_version": "openclaw_map_snapshot_v0",
                "read_model_id": "openclaw_map_snapshot",
                "map_generation_id": generation_id,
                "operator_memory_not_proof": True,
                "raw_private_bodies_included": False,
                "credentials_included": False,
                "secrets_included": False,
                "threshold_map": {
                    "capital_hilton_finance_destiny": {
                        "current_phase": "HELM_THRESHOLD_LANE",
                        "resolution_route": "MOVE_TO_WORLD_ACTION",
                        "target_world": "Finance",
                    },
                    "system_awareness_discovery_steel_thread": {
                        "lane_id": "system_awareness_discovery",
                    },
                    "cue_autonomy_placement": {
                        "status": "post_threshold_post_security_candidate",
                    },
                    "operator_memory_rule": "operator_memory_becomes_candidate_context_not_machine_proof",
                },
                "authority_boundary": {
                    "future_gated_cue_autonomy": True,
                    "live_package_dispatch_allowed": False,
                    "model_actor_execution_allowed": False,
                    "plugin_tool_execution_allowed": False,
                    "agent_activation_allowed": False,
                    "runtime_activation_allowed": False,
                    "send_submit_approval_allowed": False,
                },
                "security_audit_readiness": {
                    "present": True,
                    "ready_for_security_pass": True,
                    "security_approval_granted": False,
                    "action_authority_granted": False,
                    "all_authority_flags_false": True,
                    "zero_execution_authority_leaked": True,
                    "capital_hilton_security_readiness_present": True,
                    "coverage_gap_summary": {"coverage_gap_records_count": 5},
                    "parked_breadcrumb_summary": {"parked_breadcrumb_count": 15},
                },
                "capital_hilton_proof_metadata": {
                    "present": True,
                    "current_phase": "HELM_THRESHOLD_LANE",
                    "target_world": "Finance",
                    "lane_destiny": "MOVE_TO_WORLD_ACTION",
                    "missing_proof_count": 10,
                    "protected_proof_required": True,
                    "live_execution_authority": False,
                    "operator_answers_become_memory_candidate_receipts_not_proof": True,
                    "candidate_facts": [{"machine_proven": False}],
                    "operator_memory_questions": [{} for _ in range(7)],
                    "authority_boundary": {
                        "runtime_dispatch_allowed": False,
                        "tool_execution_allowed": False,
                        "agent_activation_allowed": False,
                        "model_call_allowed": False,
                        "send_submit_approval_allowed": False,
                    },
                },
                "package_preview_receipts": {
                    "present": True,
                    "example_package_previews_count": 8,
                },
                "tool_adapter_receipts": {
                    "present": True,
                    "adapter_examples_count": 12,
                },
                "agent_council": {
                    "present": True,
                    "image_body_embedded": False,
                    "agent_dossier_cards_count": 12,
                    "agent_dossier_cards": [
                        {"agent_id": "cassandra"},
                        {"agent_id": "chief"},
                        {"agent_id": "guardian"},
                        {"agent_id": "hermes"},
                        {"agent_id": "niles"},
                        {"agent_id": "struna"},
                        {"agent_id": "agentic_loop"},
                        {"agent_id": "cue_parser_brain_dump_parser"},
                        {"agent_id": "repo_b_planner_builder_orchestrator"},
                        {"agent_id": "package_compiler"},
                        {"agent_id": "model_router"},
                        {"agent_id": "tool_plugin_registry"},
                    ],
                },
            }
        )
        + "\n",
    )


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
        "request_marker": tmp_path / "share" / "shuttle" / "to_mac" / "read_model_sync_required.json",
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
        "request_marker": tmp_path / "share" / "shuttle" / "to_mac" / "read_model_sync_required.json",
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
    assert snapshot["sync_lifecycle_state"] == "trusted_current"
    assert snapshot["operator_action_required"] is False
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
    assert snapshot["can_request_fix_from_app"] is False
    assert snapshot["display_status"] == "needs_mac_sync"
    assert snapshot["sync_lifecycle_state"] == "actionable_sync_failure"
    assert snapshot["operator_action_required"] is True
    assert snapshot["next_expected_actor"] == "mac_sync_agent"
    assert snapshot["missing_files"] == ["beta_OPERATOR.md"]
    assert snapshot["request_marker_path"].endswith("read_model_sync_required.json")



def test_sync_requested_waiting_for_mac_does_not_bother_operator(tmp_path):
    root, read_models = _fixture_root(tmp_path)
    manifest = tmp_path / "share" / "mac_generated_read_models_manifest.json"
    _write(manifest, json.dumps(_manifest_for(read_models, omit={"beta_OPERATOR.md"})) + "\n")
    manifest_hash = sha256_file(manifest)
    paths = _proof_files(tmp_path, manifest_hash)
    request_marker = tmp_path / "share" / "shuttle" / "to_mac" / "read_model_sync_required.json"
    _write(
        request_marker,
        json.dumps(
            {
                "generated_at": "2026-05-15T00:05:00+00:00",
                "next_expected_responder": "mac_read_model_sync_agent",
            }
        )
        + "\n",
    )

    build_sync_health_snapshot(
        db_path=tmp_path / "ledger.sqlite",
        manifest_path=manifest,
        read_model_root=read_models,
        repo_root=root,
        mac_status_path=paths["mac_status"],
        mac_completion_path=paths["mac_completion"],
        pc_import_state_path=paths["pc_state"],
        pc_task_log_path=paths["pc_log"],
        windows_task_log_path=paths["windows_log"],
        request_marker_path=request_marker,
        run_id="sync_health_fixture",
    )
    snapshot = _latest(tmp_path / "ledger.sqlite")

    assert snapshot["mirror_status"] == "needs_mac_sync"
    assert snapshot["display_status"] == "sync_requested_waiting_for_mac"
    assert snapshot["sync_lifecycle_state"] == "sync_requested_waiting_for_mac"
    assert snapshot["operator_action_required"] is False
    assert snapshot["recommended_fix_kind"] == "wait_for_mac_sync"
    assert snapshot["can_request_fix_from_app"] is False

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
    assert snapshot["can_request_fix_from_app"] is False
    assert snapshot["display_status"] == "needs_mac_sync"
    assert snapshot["sync_lifecycle_state"] == "actionable_sync_failure"
    assert snapshot["operator_action_required"] is True
    assert snapshot["next_expected_actor"] == "mac_sync_agent"


def test_sync_health_self_export_hash_mismatch_does_not_make_health_stale(tmp_path):
    _root, read_models = _fixture_root(tmp_path)
    _write(read_models / "sync_health.json", '{"generated": "newer"}\n')
    _write(read_models / "sync_health_OPERATOR.md", "# Newer Sync Health\n")
    result, db_path, _paths = _build_with_manifest(
        tmp_path,
        manifest_payload=_manifest_for(
            read_models,
            mismatch={"sync_health.json", "sync_health_OPERATOR.md"},
        ),
    )
    snapshot = _latest(db_path)

    assert result.trust_status == "trusted"
    assert snapshot["mirror_status"] == "ok"
    assert snapshot["missing_expected"] == 0
    assert snapshot["hash_mismatch"] == 0
    assert snapshot["recommended_fix_kind"] == "none"
    assert snapshot["display_status"] == "current"
    assert snapshot["operator_action_required"] is False


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
    assert snapshot["sync_lifecycle_state"] == "mac_synced_waiting_for_pc_import"
    assert snapshot["operator_action_required"] is False
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
    assert snapshot["sync_lifecycle_state"] == "actionable_sync_failure"
    assert snapshot["operator_action_required"] is True
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
    assert snapshot["sync_lifecycle_state"] == "actionable_sync_failure"
    assert snapshot["operator_action_required"] is True
    assert snapshot["next_expected_actor"] == "operator_review"
    assert snapshot["extra_files"] == ["orphan.json"]


def test_read_model_export_exists_and_no_authority_flags_are_false(tmp_path):
    _root, read_models = _fixture_root(tmp_path)
    _result, db_path, _paths = _build_with_manifest(tmp_path, manifest_payload=_manifest_for(read_models))

    summary = export_sync_health_read_model(
        db_path=db_path,
        export_root=tmp_path / "exports",
        repo_root=tmp_path,
        manifest_path=tmp_path / "share" / "mac_generated_read_models_manifest.json",
        read_model_root=read_models,
    )
    payload = json.loads((tmp_path / summary["json_path"]).read_text(encoding="utf-8"))
    operator_text = (tmp_path / summary["operator_path"]).read_text(encoding="utf-8")

    assert payload["trust_status"] == "trusted"
    assert payload["recommended_fix"]["kind"] == "none"
    assert payload["display_status"] == "current"
    assert payload["sync_lifecycle_state"] == "trusted_current"
    assert payload["operator_action_required"] is False
    assert payload["next_expected_actor"] == "none"
    assert payload["recommended_fix"]["next_expected_actor"] == "none"
    assert payload["recommended_fix"]["operator_action_required"] is False
    assert "OpenClaw Sync Health" in operator_text
    assert all(value is False for value in payload["no_authority_flags"].values())
    assert all(value is False for value in NO_AUTHORITY_FLAGS.values())


def test_refresh_sync_health_from_manifest_builds_snapshot_and_exports(tmp_path):
    root, read_models = _fixture_root(tmp_path)
    manifest = tmp_path / "share" / "mac_generated_read_models_manifest.json"
    _write(manifest, json.dumps(_manifest_for(read_models)) + "\n")
    manifest_hash = sha256_file(manifest)
    paths = _proof_files(tmp_path, manifest_hash)
    export_root = tmp_path / "exports"

    summary = refresh_sync_health_from_manifest(
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
        export_root=export_root,
    )

    payload = json.loads((export_root / "sync_health.json").read_text(encoding="utf-8"))
    assert summary["sync_health_refreshed"] is True
    assert summary["canonical_expected"] == 2
    assert summary["observed"] == 2
    assert summary["missing_expected"] == 0
    assert summary["hash_mismatch"] == 0
    assert summary["mirror_status"] == "ok"
    assert payload["mirror_status"] == "ok"
    assert payload["display_status"] == "current"
    assert payload["sync_lifecycle_state"] == "trusted_current"
    assert payload["operator_action_required"] is False
    assert (export_root / "sync_health_OPERATOR.md").is_file()


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




def test_self_report_newer_than_manifest_is_routine_health_mirror_wait(tmp_path):
    root, read_models = _fixture_root(tmp_path)
    _write(read_models / "sync_health.json", '{"generated": "old"}\n')
    _write(read_models / "sync_health_OPERATOR.md", "# Old Sync Health\n")
    manifest = tmp_path / "share" / "mac_generated_read_models_manifest.json"
    _write(manifest, json.dumps(_manifest_for(read_models)) + "\n")
    manifest_hash = sha256_file(manifest)
    paths = _proof_files(tmp_path, manifest_hash)

    _write(read_models / "sync_health.json", '{"generated": "newer"}\n')
    _write(read_models / "sync_health_OPERATOR.md", "# Newer Sync Health\n")
    future_mtime = manifest.stat().st_mtime + 10
    os.utime(read_models / "sync_health.json", (future_mtime, future_mtime))
    os.utime(read_models / "sync_health_OPERATOR.md", (future_mtime, future_mtime))

    build_sync_health_snapshot(
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
    snapshot = _latest(tmp_path / "ledger.sqlite")

    assert snapshot["trust_status"] == "trusted"
    assert snapshot["mirror_status"] == "ok"
    assert snapshot["display_status"] == "current"
    assert snapshot["sync_lifecycle_state"] == "health_exported_waiting_for_mac_mirror"
    assert snapshot["operator_action_required"] is False
    assert snapshot["next_expected_actor"] == "mac_sync_agent"
    assert snapshot["recommended_fix_kind"] == "none"


def test_stable_map_files_are_expected_and_safe_exports(tmp_path):
    _root, read_models = _fixture_root(tmp_path)
    _write_map_bundle(read_models)

    expected = set(canonical_generated_read_model_expected_files(source_root=read_models, repo_root=tmp_path))

    for name in STABLE_MAP_REQUIRED_FILES:
        assert (read_models / name).is_file()
        assert name in expected


def test_sync_health_exposes_map_split_and_marker_when_mac_lacks_bundle(tmp_path):
    root, read_models = _fixture_root(tmp_path)
    _write_map_bundle(read_models, generation_id="map_pending", bundle_hash="sha256:pending")
    manifest = tmp_path / "share" / "mac_generated_read_models_manifest.json"
    _write(
        manifest,
        json.dumps(_manifest_for(read_models, omit=set(STABLE_MAP_REQUIRED_FILES))) + "\n",
    )
    manifest_hash = sha256_file(manifest)
    paths = _proof_files(tmp_path, manifest_hash)
    export_root = tmp_path / "exports"
    map_marker = tmp_path / "share" / "shuttle" / "to_mac" / "openclaw_map_sync_required.json"

    summary = refresh_sync_health_from_manifest(
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
        export_root=export_root,
        map_sync_request_path=map_marker,
        map_receipt_path=tmp_path / "share" / "shuttle" / "from_mac" / "openclaw_map_receipt.json",
    )
    payload = json.loads((export_root / "sync_health.json").read_text(encoding="utf-8"))
    marker = json.loads(map_marker.read_text(encoding="utf-8"))

    assert summary["app_visible_map_status"]["map_status"] == "map_generation_pending_mac_import"
    assert payload["app_visible_map_status"]["map_status"] == "map_generation_pending_mac_import"
    assert payload["app_visible_map_status"]["app_visible"] is False
    assert payload["raw_read_model_mirror_status"]["raw_mirror_blocks_app_visible_map"] is True
    assert payload["check_transmission_display"]["headline"] == "Stable map bundle pending"
    assert payload["check_transmission_display"]["lamp_state"] == "WARNING"
    assert marker["map_generation_id"] == "map_pending"
    assert marker["bundle_hash"] == "sha256:pending"
    assert [item["relative_path"] for item in marker["required_files"]] == list(STABLE_MAP_REQUIRED_FILES)
    assert marker["expected_next_actor"] == "mac_map_import_agent"
    assert marker["next_expected_actor"] == "mac_map_import_agent"
    assert marker["no_execution_no_credential_no_network_boundary"] == {
        "execution_authority": False,
        "credential_handling_allowed": False,
        "network_authority": False,
    }
    assert marker["credential_handling_allowed"] is False
    assert marker["source_path"].endswith("/shuttle/to_mac/map_bundle/map_pending")
    for item in marker["required_files"]:
        assert Path(item["source_path"]).is_file()
        assert item["canonical_source_path"].endswith(f"/generated/read_models/{item['relative_path']}")
        assert item["target_path"].endswith(f"/openclaw_generated_read_models/{item['relative_path']}")
    assert {item["relative_path"] for item in marker["bundle_files_written"]} == set(STABLE_MAP_REQUIRED_FILES)


def test_raw_mirror_mismatch_does_not_block_app_map_when_receipt_matches(tmp_path):
    root, read_models = _fixture_root(tmp_path)
    _write_map_bundle(read_models, generation_id="map_current", bundle_hash="sha256:current")
    manifest = tmp_path / "share" / "mac_generated_read_models_manifest.json"
    _write(manifest, json.dumps(_manifest_for(read_models, mismatch={"alpha.json"})) + "\n")
    receipt = tmp_path / "share" / "shuttle" / "from_mac" / "openclaw_map_receipt.json"
    _write(
        receipt,
        json.dumps(
            {
                "schema_version": "openclaw_map_receipt_v0",
                "map_generation_id": "map_current",
                "bundle_hash": "sha256:current",
                "parse_passed": True,
                "missing_files": [],
                "hash_mismatch": [],
            }
        )
        + "\n",
    )

    split = build_sync_health_map_raw_split(
        manifest_path=manifest,
        read_model_root=read_models,
        repo_root=root,
        map_receipt_path=receipt,
        map_sync_request_path=tmp_path / "share" / "shuttle" / "to_mac" / "openclaw_map_sync_required.json",
    )

    assert split["app_visible_map_status"]["map_status"] == "map_current"
    assert split["app_visible_map_status"]["app_visible"] is True
    assert split["raw_read_model_mirror_status"]["hash_mismatch"] == 1
    assert split["raw_read_model_mirror_status"]["raw_mirror_blocks_app_visible_map"] is False
    assert split["check_transmission_display"]["lamp_state"] == "QUIET"
    assert "proof/detail" in split["check_transmission_display"]["operator_summary"]


def test_map_current_is_not_claimed_without_matching_mac_receipt(tmp_path):
    root, read_models = _fixture_root(tmp_path)
    _write_map_bundle(read_models, generation_id="map_needs_receipt", bundle_hash="sha256:needsreceipt")
    manifest = tmp_path / "share" / "mac_generated_read_models_manifest.json"
    _write(manifest, json.dumps(_manifest_for(read_models)) + "\n")

    split = build_sync_health_map_raw_split(
        manifest_path=manifest,
        read_model_root=read_models,
        repo_root=root,
        map_receipt_path=tmp_path / "share" / "shuttle" / "from_mac" / "missing_receipt.json",
        map_sync_request_path=tmp_path / "share" / "shuttle" / "to_mac" / "openclaw_map_sync_required.json",
    )

    assert split["app_visible_map_status"]["map_status"] == "map_receipt_missing"
    assert split["app_visible_map_status"]["app_visible"] is False
    assert split["receipt_status"]["receipt_matches_pc_bundle"] is False
    assert split["check_transmission_display"]["lamp_state"] == "WARNING"


def test_mac_imported_receipt_shape_marks_app_visible_map_current(tmp_path):
    root, read_models = _fixture_root(tmp_path)
    _write_map_bundle(read_models, generation_id="map_imported", bundle_hash="sha256:imported")
    manifest = tmp_path / "share" / "mac_generated_read_models_manifest.json"
    _write(manifest, json.dumps(_manifest_for(read_models, mismatch={"alpha.json"})) + "\n")
    receipt = tmp_path / "share" / "shuttle" / "from_mac" / "openclaw_map_receipt.json"
    _write(
        receipt,
        json.dumps(
            {
                "receipt_status": "imported",
                "app_visible_candidate": True,
                "map_generation_id": "map_imported",
                "observed_map_generation_id": "map_imported",
                "bundle_hash": "sha256:imported",
                "observed_bundle_hash": "sha256:imported",
                "snapshot_present": True,
                "manifest_present": True,
                "operator_digest_present": True,
                "snapshot_parse_passed": True,
                "manifest_parse_passed": True,
                "operator_digest_non_empty": True,
                "missing_files": [],
                "hash_mismatch": False,
            }
        )
        + "\n",
    )

    split = build_sync_health_map_raw_split(
        manifest_path=manifest,
        read_model_root=read_models,
        repo_root=root,
        map_receipt_path=receipt,
        map_sync_request_path=tmp_path / "share" / "shuttle" / "to_mac" / "openclaw_map_sync_required.json",
    )

    assert split["app_visible_map_status"]["map_status"] == "map_current"
    assert split["app_visible_map_status"]["app_visible"] is True
    assert split["app_visible_map_status"]["next_expected_actor"] == "none"
    assert split["receipt_status"]["receipt_parse_passed"] is True
    assert split["receipt_status"]["receipt_matches_pc_bundle"] is True
    assert split["receipt_status"]["pc_readback_imported"] is True
    assert split["raw_read_model_mirror_status"]["hash_mismatch"] == 1
    assert split["check_transmission_display"]["lamp_state"] == "QUIET"


def test_agent_dossier_nested_path_receipt_is_accepted_as_current(tmp_path):
    root, read_models = _fixture_root(tmp_path)
    _write_map_bundle(
        read_models,
        generation_id="map_911cd302343946ad6369",
        bundle_hash="sha256:dfa1e6c95bc6b74cb64a5c4652a19005bbfb63033352b43e5fd109f6f344d061",
    )
    manifest = tmp_path / "share" / "mac_generated_read_models_manifest.json"
    _write(manifest, json.dumps(_manifest_for(read_models, omit=set(STABLE_MAP_REQUIRED_FILES))) + "\n")
    receipt = tmp_path / "share" / "shuttle" / "from_mac" / "openclaw_map_receipt.json"
    _write(
        receipt,
        json.dumps(
            {
                "receipt_status": "PARTIAL_TOP_LEVEL_AGENT_DOSSIER_CARDS_PATH_MISMATCH",
                "app_visible_candidate": False,
                "map_generation_id": "map_911cd302343946ad6369",
                "bundle_hash": "sha256:dfa1e6c95bc6b74cb64a5c4652a19005bbfb63033352b43e5fd109f6f344d061",
                "snapshot_present": True,
                "manifest_present": True,
                "operator_digest_present": True,
                "snapshot_parse_passed": True,
                "manifest_parse_passed": True,
                "operator_digest_non_empty": True,
                "missing_files": [],
                "hash_mismatch": False,
                "agent_dossier_cards_present": True,
                "agent_dossier_cards_top_level_present": False,
                "agent_dossier_cards_observed_path": "agent_council.agent_dossier_cards",
                "agent_dossier_cards_count": 12,
                "cassandra_card_present": True,
                "missing_system_loop_cards": [],
                "no_image_body_embedded": True,
                "cassandra_visual_archetype_metadata_only": True,
                "live_activation_flags_false": True,
                "live_agent_activation_false": True,
                "live_chat_launch_false": True,
                "model_launch_false": True,
                "tool_execution_false": True,
            }
        )
        + "\n",
    )

    split = build_sync_health_map_raw_split(
        manifest_path=manifest,
        read_model_root=read_models,
        repo_root=root,
        map_receipt_path=receipt,
        map_sync_request_path=tmp_path / "share" / "shuttle" / "to_mac" / "openclaw_map_sync_required.json",
    )
    app_status = split["app_visible_map_status"]
    receipt_status = split["receipt_status"]

    assert app_status["map_status"] == "map_current"
    assert app_status["app_visible"] is True
    assert app_status["receipt_matches_pc_bundle"] is True
    assert app_status["agent_dossier_cards_present"] is True
    assert app_status["agent_dossier_cards_count"] == 12
    assert app_status["agent_dossier_cards_path"] == "agent_council.agent_dossier_cards"
    assert app_status["agent_dossier_cards_path_status"] == "accepted_canonical_nested_path"
    assert app_status["cassandra_card_present"] is True
    assert app_status["system_loop_cards_present"] is True
    assert app_status["no_image_body_embedded"] is True
    assert app_status["live_activation_flags_false"] is True
    assert app_status["next_expected_actor"] == "none"
    assert app_status["operator_action_required"] is False
    assert app_status["recommended_fix"] == "none"
    assert receipt_status["receipt_status_accepted"] is True
    assert receipt_status["receipt_status_accepted_reason"] == "agent_dossier_cards_nested_path_is_canonical"
    assert receipt_status["pc_readback_imported"] is True
    assert split["check_transmission_display"]["lamp_state"] == "QUIET"


def test_package_preview_and_tool_receipt_map_receipt_is_accepted_as_current(tmp_path):
    root, read_models = _fixture_root(tmp_path)
    _write_map_bundle(
        read_models,
        generation_id="map_d49f3a6dd4a0eedc1777",
        bundle_hash="sha256:127b49cd02832950dceb9c9ff8943a1a790507a6c360806bbbf944cce3108211",
    )
    manifest = tmp_path / "share" / "mac_generated_read_models_manifest.json"
    _write(manifest, json.dumps(_manifest_for(read_models, omit=set(STABLE_MAP_REQUIRED_FILES))) + "\n")
    receipt = tmp_path / "share" / "shuttle" / "from_mac" / "openclaw_map_receipt.json"
    _write(
        receipt,
        json.dumps(
            {
                "receipt_status": "SUCCESS",
                "app_visible_candidate": True,
                "map_generation_id": "map_d49f3a6dd4a0eedc1777",
                "bundle_hash": "sha256:127b49cd02832950dceb9c9ff8943a1a790507a6c360806bbbf944cce3108211",
                "snapshot_present": True,
                "manifest_present": True,
                "operator_digest_present": True,
                "snapshot_parse_passed": True,
                "manifest_parse_passed": True,
                "operator_digest_non_empty": True,
                "missing_files": [],
                "hash_mismatch": False,
                "package_preview_summary_present": True,
                "package_preview_example_count": 8,
                "tool_adapter_receipt_summary_present": True,
                "tool_adapter_receipt_example_count": 12,
                "agent_council_present": True,
                "agent_dossier_cards_count": 12,
                "capital_hilton_finance_present": True,
                "system_awareness_present": True,
                "future_gated_cue_autonomy_present": True,
                "raw_private_body_absent": True,
                "no_credentials_secrets_embedded": True,
                "live_authority_flags_false": True,
                "validation_details": {
                    "package_preview_summary_present": True,
                    "package_preview_example_count_ok": True,
                    "cassandra_capital_hilton_package_preview_present": True,
                    "chief_check_engine_package_preview_present": True,
                    "agentic_loop_classification_package_preview_present": True,
                    "tool_adapter_receipt_summary_present": True,
                    "tool_adapter_receipt_example_count_ok": True,
                    "stable_map_reader_tool_adapter_present": True,
                    "cassandra_capital_hilton_tool_adapter_present": True,
                    "browser_oauth_blocked_adapter_present": True,
                    "gmail_calendar_blocked_adapter_present": True,
                    "coupa_blocked_adapter_present": True,
                    "telegram_blocked_adapter_present": True,
                    "agent_council_present": True,
                    "cassandra_card_present": True,
                    "capital_hilton_finance_present": True,
                    "system_awareness_present": True,
                    "future_gated_cue_autonomy_present": True,
                    "raw_private_body_absent": True,
                    "no_credentials_secrets_embedded": True,
                    "live_authority_flags_false": True,
                },
            }
        )
        + "\n",
    )

    split = build_sync_health_map_raw_split(
        manifest_path=manifest,
        read_model_root=read_models,
        repo_root=root,
        map_receipt_path=receipt,
        map_sync_request_path=tmp_path / "share" / "shuttle" / "to_mac" / "openclaw_map_sync_required.json",
    )
    app_status = split["app_visible_map_status"]
    receipt_status = split["receipt_status"]

    assert app_status["map_status"] == "map_current"
    assert app_status["app_visible"] is True
    assert app_status["receipt_matches_pc_bundle"] is True
    assert app_status["package_preview_summary_present"] is True
    assert app_status["package_preview_example_count"] == 8
    assert app_status["cassandra_capital_hilton_preview_present"] is True
    assert app_status["chief_check_engine_preview_present"] is True
    assert app_status["agentic_loop_classification_preview_present"] is True
    assert app_status["tool_adapter_receipt_summary_present"] is True
    assert app_status["tool_adapter_receipt_example_count"] == 12
    assert app_status["stable_map_reader_adapter_present"] is True
    assert app_status["cassandra_capital_hilton_adapter_present"] is True
    assert app_status["browser_oauth_blocked_adapter_present"] is True
    assert app_status["gmail_calendar_blocked_adapter_present"] is True
    assert app_status["coupa_blocked_adapter_present"] is True
    assert app_status["telegram_blocked_adapter_present"] is True
    assert app_status["agent_council_present"] is True
    assert app_status["agent_dossier_cards_count"] == 12
    assert app_status["raw_private_body_absent"] is True
    assert app_status["no_credentials_secrets_embedded"] is True
    assert app_status["live_activation_flags_false"] is True
    assert app_status["next_expected_actor"] == "none"
    assert app_status["operator_action_required"] is False
    assert app_status["recommended_fix"] == "none"
    assert receipt_status["receipt_status_accepted"] is True
    assert receipt_status["receipt_matches_pc_bundle"] is True
    assert receipt_status["pc_readback_imported"] is True
    assert split["raw_read_model_mirror_status"]["raw_mirror_blocks_app_visible_map"] is False
    assert split["check_transmission_display"]["lamp_state"] == "QUIET"


def test_capital_hilton_map_receipt_is_accepted_as_current(tmp_path):
    root, read_models = _fixture_root(tmp_path)
    _write_map_bundle(
        read_models,
        generation_id="map_fbda77b8af4e9c796c03",
        bundle_hash="sha256:d54194ee82f05e41724f26bb3def93f048f4552e6ff40914cfdf6227445bdb39",
    )
    manifest = tmp_path / "share" / "mac_generated_read_models_manifest.json"
    _write(manifest, json.dumps(_manifest_for(read_models, omit=set(STABLE_MAP_REQUIRED_FILES))) + "\n")
    receipt = tmp_path / "share" / "shuttle" / "from_mac" / "openclaw_map_receipt.json"
    _write(
        receipt,
        json.dumps(
            {
                "receipt_status": "SUCCESS",
                "schema_version": "openclaw_map_receipt_v0",
                "app_visible_candidate": True,
                "map_generation_id": "map_fbda77b8af4e9c796c03",
                "bundle_hash": "sha256:d54194ee82f05e41724f26bb3def93f048f4552e6ff40914cfdf6227445bdb39",
                "snapshot_present": True,
                "manifest_present": True,
                "operator_digest_present": True,
                "snapshot_parse_passed": True,
                "manifest_parse_passed": True,
                "operator_digest_non_empty": True,
                "missing_files": [],
                "hash_mismatch": False,
                "capital_hilton_summary_present": True,
                "capital_hilton_current_phase": "HELM_THRESHOLD_LANE",
                "capital_hilton_target_world": "Finance",
                "capital_hilton_lane_destiny": "MOVE_TO_WORLD_ACTION",
                "capital_hilton_missing_proof_count": 10,
                "capital_hilton_protected_proof_required": True,
                "capital_hilton_candidate_facts_marked_not_proven": True,
                "capital_hilton_operator_questions_count": 7,
                "capital_hilton_authority_flags_false": True,
                "package_preview_summary_present": True,
                "package_preview_cards_count": 8,
                "tool_adapter_receipt_summary_present": True,
                "tool_adapter_receipt_cards_count": 12,
                "agent_council_present": True,
                "agent_council_card_count": 12,
                "system_awareness_discovery_present": True,
                "no_live_execution_authority": True,
            }
        )
        + "\n",
    )

    split = build_sync_health_map_raw_split(
        manifest_path=manifest,
        read_model_root=read_models,
        repo_root=root,
        map_receipt_path=receipt,
        map_sync_request_path=tmp_path / "share" / "shuttle" / "to_mac" / "openclaw_map_sync_required.json",
    )
    app_status = split["app_visible_map_status"]
    receipt_status = split["receipt_status"]

    assert app_status["map_status"] == "map_current"
    assert app_status["app_visible"] is True
    assert app_status["receipt_matches_pc_bundle"] is True
    assert app_status["capital_hilton_summary_present"] is True
    assert app_status["capital_hilton_current_phase"] == "HELM_THRESHOLD_LANE"
    assert app_status["capital_hilton_target_world"] == "Finance"
    assert app_status["capital_hilton_lane_destiny"] == "MOVE_TO_WORLD_ACTION"
    assert app_status["capital_hilton_missing_proof_count"] == 10
    assert app_status["capital_hilton_protected_proof_required"] is True
    assert app_status["capital_hilton_candidate_facts_marked_not_proven"] is True
    assert app_status["capital_hilton_operator_questions_count"] == 7
    assert app_status["capital_hilton_authority_flags_false"] is True
    assert app_status["package_preview_summary_present"] is True
    assert app_status["package_preview_example_count"] == 8
    assert app_status["tool_adapter_receipt_summary_present"] is True
    assert app_status["tool_adapter_receipt_example_count"] == 12
    assert app_status["agent_council_present"] is True
    assert app_status["agent_dossier_cards_count"] == 12
    assert app_status["live_activation_flags_false"] is True
    assert app_status["next_expected_actor"] == "none"
    assert app_status["operator_action_required"] is False
    assert app_status["recommended_fix"] == "none"
    assert receipt_status["receipt_matches_pc_bundle"] is True
    assert receipt_status["capital_hilton_receipt_validation_passed"] is True
    assert receipt_status["pc_readback_imported"] is True
    assert split["raw_read_model_mirror_status"]["raw_mirror_blocks_app_visible_map"] is False
    assert split["check_transmission_display"]["lamp_state"] == "QUIET"


def test_security_audit_readiness_map_receipt_is_accepted_as_current(tmp_path):
    root, read_models = _fixture_root(tmp_path)
    _write_security_ready_map_bundle(read_models)
    manifest = tmp_path / "share" / "mac_generated_read_models_manifest.json"
    _write(manifest, json.dumps(_manifest_for(read_models, omit=set(STABLE_MAP_REQUIRED_FILES))) + "\n")
    receipt = tmp_path / "share" / "shuttle" / "from_mac" / "openclaw_map_receipt.json"
    _write(
        receipt,
        json.dumps(
            {
                "receipt_status": "SUCCESS",
                "app_visible_candidate": True,
                "map_generation_id": "map_3cf7a1d5f26147ae993a",
                "bundle_hash": "sha256:3d59cfda37602e22a7cb02dab1afb899acb65fe043efadf032820d8f5bb7c1af",
                "snapshot_present": True,
                "manifest_present": True,
                "operator_digest_present": True,
                "snapshot_parse_passed": True,
                "manifest_parse_passed": True,
                "operator_digest_non_empty": True,
                "missing_files": [],
                "hash_mismatch": False,
                "security_audit_readiness_present": True,
                "ready_for_security_pass": True,
                "security_approval_granted": False,
                "action_authority_granted": False,
                "coverage_gap_records_count": 5,
                "parked_breadcrumb_count": 15,
                "capital_hilton_security_readiness_present": True,
                "package_preview_summary_present": True,
                "tool_adapter_receipt_summary_present": True,
                "agent_council_present": True,
                "observed": {
                    "agent_council_card_count": 12,
                    "all_live_authority_flags_false": True,
                    "capital_hilton_proof_metadata_present": True,
                    "coverage_gap_summary_present": True,
                    "parked_breadcrumb_summary_present": True,
                    "system_awareness_discovery_present": True,
                },
            }
        )
        + "\n",
    )

    split = build_sync_health_map_raw_split(
        manifest_path=manifest,
        read_model_root=read_models,
        repo_root=root,
        map_receipt_path=receipt,
        map_sync_request_path=tmp_path / "share" / "shuttle" / "to_mac" / "openclaw_map_sync_required.json",
    )
    app_status = split["app_visible_map_status"]
    receipt_status = split["receipt_status"]

    assert app_status["map_status"] == "map_current"
    assert app_status["app_visible"] is True
    assert app_status["receipt_matches_pc_bundle"] is True
    assert app_status["security_audit_readiness_present"] is True
    assert app_status["ready_for_security_pass"] is True
    assert app_status["security_approval_granted"] is False
    assert app_status["action_authority_granted"] is False
    assert app_status["coverage_gap_records_count"] == 5
    assert app_status["parked_breadcrumb_count"] == 15
    assert app_status["capital_hilton_security_readiness_present"] is True
    assert app_status["capital_hilton_summary_present"] is True
    assert app_status["package_preview_summary_present"] is True
    assert app_status["package_preview_example_count"] == 8
    assert app_status["tool_adapter_receipt_summary_present"] is True
    assert app_status["tool_adapter_receipt_example_count"] == 12
    assert app_status["agent_council_present"] is True
    assert app_status["agent_dossier_cards_count"] == 12
    assert app_status["all_live_authority_flags_false"] is True
    assert app_status["no_live_execution_authority"] is True
    assert app_status["next_expected_actor"] == "none"
    assert app_status["operator_action_required"] is False
    assert app_status["recommended_fix"] == "none"
    assert receipt_status["security_audit_receipt_validation_passed"] is True
    assert receipt_status["receipt_matches_pc_bundle"] is True
    assert receipt_status["pc_readback_imported"] is True
    assert split["raw_read_model_mirror_status"]["raw_mirror_blocks_app_visible_map"] is False
    assert split["check_transmission_display"]["lamp_state"] == "QUIET"


def test_stable_map_receipt_clears_app_block_even_if_raw_manifest_lacks_map_files(tmp_path):
    root, read_models = _fixture_root(tmp_path)
    _write_map_bundle(read_models, generation_id="map_imported", bundle_hash="sha256:imported")
    manifest = tmp_path / "share" / "mac_generated_read_models_manifest.json"
    _write(
        manifest,
        json.dumps(_manifest_for(read_models, omit=set(STABLE_MAP_REQUIRED_FILES))) + "\n",
    )
    receipt = tmp_path / "share" / "shuttle" / "from_mac" / "openclaw_map_receipt.json"
    _write(
        receipt,
        json.dumps(
            {
                "receipt_status": "imported",
                "app_visible_candidate": True,
                "map_generation_id": "map_imported",
                "bundle_hash": "sha256:imported",
                "snapshot_present": True,
                "manifest_present": True,
                "operator_digest_present": True,
                "snapshot_parse_passed": True,
                "manifest_parse_passed": True,
                "operator_digest_non_empty": True,
                "missing_files": [],
                "hash_mismatch": False,
            }
        )
        + "\n",
    )

    split = build_sync_health_map_raw_split(
        manifest_path=manifest,
        read_model_root=read_models,
        repo_root=root,
        map_receipt_path=receipt,
        map_sync_request_path=tmp_path / "share" / "shuttle" / "to_mac" / "openclaw_map_sync_required.json",
    )

    assert split["app_visible_map_status"]["map_status"] == "map_current"
    assert split["raw_read_model_mirror_status"]["missing_expected"] == len(STABLE_MAP_REQUIRED_FILES)
    assert split["raw_read_model_mirror_status"]["raw_mirror_blocks_app_visible_map"] is False
    assert split["raw_read_model_mirror_status"]["raw_mirror_app_visible_block_cleared_by_receipt"] is True
    assert split["check_transmission_display"]["lamp_state"] == "QUIET"


def test_niles_metadata_packet_and_matrix_are_expected_read_models():
    expected = set(canonical_generated_read_model_expected_files())

    assert "niles_album_metadata_intake_packet.json" in expected
    assert "niles_album_metadata_intake_packet_OPERATOR.md" in expected
    assert "niles_album_matrix_review.json" in expected
    assert "niles_album_matrix_review_OPERATOR.md" in expected
    assert "niles_album_review_packet.json" in expected
    assert "niles_album_review_packet_OPERATOR.md" in expected

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
