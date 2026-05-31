import hashlib
import json
import sqlite3
from pathlib import Path

import openclaw_change_sentinel as sentinel
import openclaw_authority_semantics_registry as authority_registry
from scripts.export_openclaw_change_sentinel import main as export_main


FIXED_NOW = "2026-05-31T03:20:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _reference_resolver_payload(
    *,
    commit: str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    dirty_status: str = "CLEAN",
    mirror_status: str = "RESOLVED_LOCAL",
    mac_mirror_status: str = "LOCAL_PATH_UNREACHABLE",
) -> dict:
    hash_match = mirror_status == "RESOLVED_LOCAL"
    bridge_exists = mirror_status != "MISSING"
    return {
        "schema_version": "openclaw_reference_resolver_read_model_v0",
        "git_branch_refs": [
            {
                "target_ref": "openclaw_eyes_registry_review_branch",
                "repo_ref": "openclaw-eyes",
                "repo_name": "openclaw-eyes",
                "local_path": "/home/openclaw",
                "remote_url": "git@github.com:WinshipWheatley/openclaw-eyes.git",
                "branch": "codex/system-knowledge-registry-v0-local",
                "current_head_commit": commit,
                "resolution_status": "RESOLVED_REMOTE",
                "resolution_source": "configured_remote",
                "remote_status": "RESOLVED_REMOTE",
                "local_status": "UNREACHABLE",
                "dirty_status": dirty_status,
                "mac_mirror_path": "/Users/hwinshipwheatley/Eyes",
                "mac_mirror_status": mac_mirror_status,
                "mac_bridge_status": "MAC_BRIDGE_UNAVAILABLE",
                "mac_bridge_resolution_path": "",
            }
        ],
        "reference_resolutions": [
            {
                "target_ref": "estate_topology_registry_read_model_mirror",
                "resolved_status": mirror_status,
                "resolved_value": "sha256:source",
                "dirty_status": "",
                "error_message": "source and bridge hashes differ"
                if mirror_status == "DRIFT"
                else ("source or bridge counterpart missing" if mirror_status == "MISSING" else ""),
                "resolved_json": json.dumps(
                    {
                        "target_ref": "estate_topology_registry_read_model_mirror",
                        "target_type": "READ_MODEL_MIRROR",
                        "source_path": "generated/read_models/openclaw_estate_topology_registry.json",
                        "bridge_path": "/mnt/e/openclaw/generated/read_models/openclaw_estate_topology_registry.json",
                        "source_exists": True,
                        "bridge_exists": bridge_exists,
                        "hash_match": hash_match,
                        "resolved_status": mirror_status,
                    },
                    sort_keys=True,
                ),
            }
        ],
    }


def _estate_payload(*, unknown_count: int = 0, codex_artifact_count: int = 0) -> dict:
    return {
        "schema_version": "openclaw_estate_topology_registry_read_model_v0",
        "known_unknowns": [
            {"unknown_id": f"unknown_{index}", "status": "UNKNOWN"}
            for index in range(unknown_count)
        ],
        "codex_web_artifacts": [
            {
                "artifact_id": f"codex_web_{index}",
                "status": "UNREACHABLE",
                "source_truth": False,
            }
            for index in range(codex_artifact_count)
        ],
    }


def _live_arts_payload(*, pdf_status: str = "PDF_EXPORT_PACKAGE_READY_FOR_MAC") -> dict:
    return {
        "schema_version": "live_arts_md_invoice_review_bundle_v0",
        "live_arts_md_bundle": {
            "status": "ARTIFACT_REQUIRED",
            "candidate_selection_rail": {
                "candidate_selection_status": "OPERATOR_CONFIRMED",
                "selected_invoice_ids": ["2026-1001"],
                "selected_invoice_summary": "2026-1001 - June 2026 Speaker Rental - $900",
            },
            "invoice_selection": {"status": "OPERATOR_CONFIRMED"},
            "invoice_artifact": {
                "artifact_review_status": "NOT_READY",
                "attachment_ready": False,
                "pdf_export_package": {
                    "workflow_ref": "live_arts_md_invoice_workflow",
                    "status": pdf_status,
                    "job_ref": "job_live_arts",
                    "request_payload_ready": True,
                    "invoice_id": "2026-1001",
                    "selected_sheet_label": "June 2026 Speaker Rental",
                    "selected_print_areas": ["June 2026 Speaker Rental!G2:G5"],
                    "result_intended_use": "selected_invoice_pdf_export_completed_candidate",
                },
            },
            "developer_end_to_end_card": {
                "payment_watch_status": "READINESS_ONLY_NOT_ACTIVE"
            },
        },
    }


def _capital_hilton_payload(*, workflow_status: str = "READY_FOR_REVIEW_BLOCKED_FOR_SELECTION") -> dict:
    return {
        "schema_version": "invoice_review_bundle_v0",
        "capital_hilton_bundle": {
            "status": workflow_status,
            "workflow_ref": "capital_hilton_invoice_workflow",
            "state_machine": {
                "state": {
                    "invoice_record_selection_status": "NEEDS_OPERATOR_SELECTION",
                    "invoice_period_status": "NEEDS_OPERATOR_SELECTION",
                    "generated_artifact_status": "GENERATION_AUTHORITY_REQUIRED",
                    "supplier_portal_proof_status": "PROOF_REQUESTED",
                    "recipient_review_status": "NEEDS_CONTACT_CONFIRMATION",
                    "payment_watch_status": "NOT_READY",
                }
            },
            "semantic_status": {
                "payment_watch_status": "NOT_RECEIVED",
                "excel_invoice_artifact_status": "GENERATED_INVOICE_ARTIFACT_CANDIDATE",
            },
        },
    }


def _sync_health_payload() -> dict:
    return {
        "schema_version": "sync_health_read_model_v0",
        "last_mac_heartbeat": "2026-05-31T03:00:00+00:00",
        "last_mac_completion": None,
        "mirror_status": "healthy",
        "trust_status": "healthy",
        "sync_lifecycle_state": "healthy",
        "missing_expected": [],
        "hash_mismatch": False,
    }


def _service_status_payload() -> dict:
    return {"schema_version": "openclaw_request_response_service_v1", "service_status": {}}


def _write_fixture_read_models(
    root: Path,
    *,
    commit: str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    dirty_status: str = "CLEAN",
    mirror_status: str = "RESOLVED_LOCAL",
    live_pdf_status: str = "PDF_EXPORT_PACKAGE_READY_FOR_MAC",
    capital_status: str = "READY_FOR_REVIEW_BLOCKED_FOR_SELECTION",
    unknown_count: int = 0,
    codex_artifact_count: int = 0,
) -> None:
    _write_json(
        root / "openclaw_reference_resolver.json",
        _reference_resolver_payload(
            commit=commit,
            dirty_status=dirty_status,
            mirror_status=mirror_status,
        ),
    )
    _write_json(root / "openclaw_estate_topology_registry.json", _estate_payload(unknown_count=unknown_count, codex_artifact_count=codex_artifact_count))
    _write_json(root / "live_arts_md_invoice_review_bundle.json", _live_arts_payload(pdf_status=live_pdf_status))
    _write_json(root / "invoice_review_bundle.json", _capital_hilton_payload(workflow_status=capital_status))
    _write_json(root / "sync_health.json", _sync_health_payload())
    _write_json(root / "openclaw_request_response_service_status.json", _service_status_payload())
    _write_json(
        root / "openclaw_authority_semantics_registry.json",
        authority_registry.build_registry_payload(generated_at="2026-05-31T03:00:00+00:00"),
    )
    _write_json(root / "openclaw_lane_capability_harvest.json", _lane_capability_harvest_payload())


def _business_object_audit_payload(root: Path) -> dict:
    return {
        "schema_version": "openclaw_business_object_layer_audit_read_model_v0",
        "freshness_status": "FRESH",
        "fresh_for_minutes": 60,
        "input_manifest": [
            {
                "input_ref": "live_arts_bundle",
                "path": "generated/read_models/live_arts_md_invoice_review_bundle.json",
                "required": True,
                "status": "PRESENT",
                "sha256": _file_hash(root / "live_arts_md_invoice_review_bundle.json"),
                "schema_version": "live_arts_md_invoice_review_bundle_v0",
                "generated_at": "",
                "source_ref": "generated/read_models/live_arts_md_invoice_review_bundle.json",
            },
            {
                "input_ref": "change_sentinel",
                "path": "generated/read_models/openclaw_change_sentinel.json",
                "required": True,
                "status": "PRESENT",
                "sha256": "sha256:self-referential-skip",
                "schema_version": "openclaw_change_sentinel_read_model_v0",
                "generated_at": "",
                "source_ref": "generated/read_models/openclaw_change_sentinel.json",
            },
        ],
        "input_hashes": {},
        "stale_reasons": [],
    }


def _lane_capability_harvest_payload(*, recommendation: str = "finish_invoice_steel_thread_sequence") -> dict:
    return {
        "schema_version": "openclaw_lane_capability_harvest_read_model_v0",
        "readiness": "READY_FOR_PLANNING_NOT_EXECUTION",
        "missing_inputs": [],
        "lanes": [
            {"lane_ref": "live_arts_md_invoice_lane", "status": "ACTIVE_STEEL_THREAD"},
            {"lane_ref": "capital_hilton_invoice_lane", "status": "PARTIAL"},
            {"lane_ref": "st_annes_invoice_lane", "status": "PARTIAL"},
        ],
        "harvested_capabilities": [
            {"capability_ref": "capability:simple_invoice_rail", "status": "PROVEN"},
            {"capability_ref": "capability:payment_watch", "status": "PARTIAL"},
        ],
        "hermes_recommendation": {
            "recommended_next_lane": recommendation,
            "reason": "Live Arts, Capital Hilton, and St. Anne's are not all proven yet.",
        },
    }


def _service_snapshot(n_restarts: int = 1) -> dict:
    return {
        "service_name": sentinel.SERVICE_NAME,
        "available": True,
        "active_state": "active",
        "sub_state": "running",
        "n_restarts": str(n_restarts),
        "exec_main_status": "0",
        "result": "success",
        "error": "",
    }


def _build(root: Path, *, previous: dict | None = None, n_restarts: int = 1) -> dict:
    return sentinel.build_openclaw_change_sentinel(
        read_model_root=root,
        generated_at=FIXED_NOW,
        previous_snapshot=previous,
        systemd_snapshot=_service_snapshot(n_restarts),
    )


def _status_set(payload: dict) -> set[str]:
    return {row["material_status"] for row in payload["material_changes"]}


def test_no_change_run_emits_no_material_change(tmp_path):
    read_root = tmp_path / "read_models"
    _write_fixture_read_models(read_root)
    baseline = _build(read_root)
    second = _build(read_root, previous=baseline)

    assert second["run_status"] == "NO_MATERIAL_CHANGE"
    assert second["observed_change_count"] == 0
    assert second["chief_queue_candidate_count"] == 0
    assert "No material change" in second["hermes_summary"]["what_changed"]


def test_git_branch_head_change_emits_remote_ref_moved(tmp_path):
    read_root = tmp_path / "read_models"
    _write_fixture_read_models(read_root, commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    baseline = _build(read_root)
    _write_fixture_read_models(read_root, commit="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    changed = _build(read_root, previous=baseline)

    assert "REMOTE_REF_MOVED" in _status_set(changed)
    assert changed["chief_queue_candidate_count"] > 0


def test_bridge_hash_mismatch_emits_drift_detected(tmp_path):
    read_root = tmp_path / "read_models"
    _write_fixture_read_models(read_root, mirror_status="RESOLVED_LOCAL")
    baseline = _build(read_root)
    _write_fixture_read_models(read_root, mirror_status="DRIFT")
    changed = _build(read_root, previous=baseline)

    assert "DRIFT_DETECTED" in _status_set(changed)


def test_authority_semantics_registry_change_emits_authority_drift_without_lm(tmp_path):
    read_root = tmp_path / "read_models"
    _write_fixture_read_models(read_root)
    baseline = _build(read_root)
    registry_payload = authority_registry.build_registry_payload(generated_at="2026-05-31T03:10:00+00:00")
    registry_payload["active_drift_signals"] = [
        {
            "drift_type": "WRONG_BOOLEAN_POLARITY",
            "severity": "BLOCKER",
            "field_name": "authority_boundary.no_browser",
        }
    ]
    _write_json(read_root / "openclaw_authority_semantics_registry.json", registry_payload)

    changed = _build(read_root, previous=baseline)

    assert "AUTHORITY_SEMANTICS_DRIFT" in _status_set(changed)
    assert changed["lm_called"] is False
    assert changed["chief_launched"] is False
    target = {
        row["target_ref"]: row for row in changed["observed_targets"]
    }["authority_semantics_registry:fingerprint"]
    assert target["observation_status"] == "AUTHORITY_SEMANTICS_DRIFT"


def test_lane_capability_harvest_is_observed_and_recommendation_change_is_material(tmp_path):
    read_root = tmp_path / "read_models"
    _write_fixture_read_models(read_root)
    baseline = _build(read_root)
    _write_json(
        read_root / "openclaw_lane_capability_harvest.json",
        _lane_capability_harvest_payload(recommendation="payment_proof_intake_lane"),
    )

    changed = _build(read_root, previous=baseline)

    assert "LANE_CAPABILITY_HARVEST_STALE" in _status_set(changed)
    target = {
        row["target_ref"]: row for row in changed["observed_targets"]
    }["lane_capability_harvest:recommendation"]
    assert target["observed_value"] == "payment_proof_intake_lane"
    assert any(
        row["validation_command"] == "python3 scripts/export_openclaw_lane_capability_harvest.py"
        for row in changed["recommended_actions"]
    )


def test_missing_lane_capability_harvest_input_is_recorded(tmp_path):
    read_root = tmp_path / "read_models"
    _write_fixture_read_models(read_root)
    (read_root / "openclaw_lane_capability_harvest.json").unlink()

    payload = _build(read_root)
    target = {
        row["target_ref"]: row for row in payload["observed_targets"]
    }["input_read_model:lane_capability_harvest"]

    assert target["observed_value"] == "missing"
    assert target["unreachable_reason"] == "input read model missing or not JSON"


def test_dirty_repo_change_emits_repo_dirty(tmp_path):
    read_root = tmp_path / "read_models"
    _write_fixture_read_models(read_root, dirty_status="CLEAN")
    baseline = _build(read_root)
    _write_fixture_read_models(read_root, dirty_status="DIRTY")
    changed = _build(read_root, previous=baseline)

    assert "REPO_DIRTY" in _status_set(changed)


def test_live_arts_bundle_state_change_emits_workflow_state_changed(tmp_path):
    read_root = tmp_path / "read_models"
    _write_fixture_read_models(read_root, live_pdf_status="PDF_EXPORT_PACKAGE_READY_FOR_MAC")
    baseline = _build(read_root)
    _write_fixture_read_models(read_root, live_pdf_status="BLOCKED_MISSING_EXPORT_SCOPE")
    changed = _build(read_root, previous=baseline)

    assert "WORKFLOW_STATE_CHANGED" in _status_set(changed)


def test_service_restart_count_increase_emits_service_unstable(tmp_path):
    read_root = tmp_path / "read_models"
    _write_fixture_read_models(read_root)
    baseline = _build(read_root, n_restarts=10)
    changed = _build(read_root, previous=baseline, n_restarts=11)

    assert "SERVICE_UNSTABLE" in _status_set(changed)


def test_unavailable_service_snapshot_does_not_emit_false_material_change(tmp_path):
    read_root = tmp_path / "read_models"
    _write_fixture_read_models(read_root)
    baseline = _build(read_root, n_restarts=10)
    unavailable_service = {
        "service_name": sentinel.SERVICE_NAME,
        "available": False,
        "error": "Failed to connect to bus: Operation not permitted",
    }

    changed = sentinel.build_openclaw_change_sentinel(
        read_model_root=read_root,
        generated_at=FIXED_NOW,
        previous_snapshot=baseline,
        systemd_snapshot=unavailable_service,
    )

    assert changed["run_status"] == "NO_MATERIAL_CHANGE"
    assert all(
        not row["material_ref"].startswith("material:service_")
        for row in changed["material_changes"]
    )


def test_same_mac_heartbeat_status_does_not_emit_false_bridge_stale(tmp_path):
    read_root = tmp_path / "read_models"
    _write_fixture_read_models(read_root)
    stale_sync_health = _sync_health_payload()
    stale_sync_health.update(
        {
            "last_mac_heartbeat": "2026-05-31T03:00:00+00:00",
            "mirror_status": "needs_mac_sync",
            "trust_status": "stale_needs_mac_sync",
            "sync_lifecycle_state": "actionable_sync_failure",
            "missing_expected": 259,
            "hash_mismatch": 7,
        }
    )
    _write_json(read_root / "sync_health.json", stale_sync_health)
    baseline = _build(read_root)
    stale_sync_health["last_mac_heartbeat"] = "2026-05-31T03:10:00+00:00"
    _write_json(read_root / "sync_health.json", stale_sync_health)

    changed = _build(read_root, previous=baseline)

    assert changed["run_status"] == "NO_MATERIAL_CHANGE"
    assert "BRIDGE_STALE" not in _status_set(changed)


def test_unreachable_mac_path_is_recorded_without_guessing(tmp_path):
    read_root = tmp_path / "read_models"
    _write_fixture_read_models(read_root)
    payload = _build(read_root)
    target = {
        row["target_ref"]: row for row in payload["observed_targets"]
    }["mac_mirror:openclaw_eyes_registry_review_branch"]

    assert target["observed_value"] == "LOCAL_PATH_UNREACHABLE"
    assert target["observation_status"] == "UNKNOWN"
    assert target["unreachable_reason"] == "LOCAL_PATH_UNREACHABLE"


def test_chief_queue_candidate_only_for_material_changes(tmp_path):
    read_root = tmp_path / "read_models"
    _write_fixture_read_models(read_root)
    baseline = _build(read_root)
    unchanged = _build(read_root, previous=baseline)
    _write_fixture_read_models(read_root, commit="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    changed = _build(read_root, previous=baseline)

    assert unchanged["chief_queue_candidates"] == []
    assert changed["chief_queue_candidates"]
    assert all(candidate["launch_chief"] is False for candidate in changed["chief_queue_candidates"])


def test_business_object_audit_input_hash_change_emits_stale(tmp_path):
    read_root = tmp_path / "read_models"
    _write_fixture_read_models(read_root)
    _write_json(
        read_root / "openclaw_business_object_layer_audit.json",
        _business_object_audit_payload(read_root),
    )
    baseline = _build(read_root)
    live_payload = json.loads(
        (read_root / "live_arts_md_invoice_review_bundle.json").read_text(encoding="utf-8")
    )
    live_payload["ignored_test_marker"] = "hash-only-change"
    _write_json(read_root / "live_arts_md_invoice_review_bundle.json", live_payload)

    changed = _build(read_root, previous=baseline)
    actions = {row["material_status"]: row for row in changed["material_changes"]}

    assert "BUSINESS_OBJECT_AUDIT_STALE" in _status_set(changed)
    assert actions["BUSINESS_OBJECT_AUDIT_STALE"]["action_required"] is True
    assert any(
        row["validation_command"] == "python3 scripts/export_openclaw_business_object_layer_audit.py"
        for row in changed["recommended_actions"]
    )


def test_business_object_audit_refresh_to_fresh_clears_stale_alert(tmp_path):
    read_root = tmp_path / "read_models"
    _write_fixture_read_models(read_root)
    stale_payload = _business_object_audit_payload(read_root)
    stale_payload["freshness_status"] = "STALE_INPUT_CHANGED"
    stale_payload["stale_reasons"] = ["Audit input hashes changed: live_arts_bundle"]
    _write_json(read_root / "openclaw_business_object_layer_audit.json", stale_payload)
    baseline = _build(read_root)

    _write_json(
        read_root / "openclaw_business_object_layer_audit.json",
        _business_object_audit_payload(read_root),
    )
    changed = _build(read_root, previous=baseline)

    assert changed["run_status"] == "NO_MATERIAL_CHANGE"
    assert "BUSINESS_OBJECT_AUDIT_STALE" not in _status_set(changed)


def test_no_lm_call_occurs(tmp_path):
    read_root = tmp_path / "read_models"
    _write_fixture_read_models(read_root)
    payload = _build(read_root)

    assert payload["lm_called"] is False
    assert payload["no_authority_flags"]["lm_called"] is False
    assert payload["lm_summary_candidate"]["lm_call_performed"] is False


def test_export_writes_json_operator_sqlite_schema_seed_and_cli_outputs(tmp_path, capsys):
    read_root = tmp_path / "generated" / "read_models"
    system_root = tmp_path / "generated" / "system_knowledge"
    _write_fixture_read_models(read_root)
    result = sentinel.export_openclaw_change_sentinel(
        read_model_root=read_root,
        system_knowledge_root=system_root,
        generated_at=FIXED_NOW,
        systemd_snapshot=_service_snapshot(),
    )

    json_path = read_root / sentinel.JSON_EXPORT_NAME
    sqlite_path = system_root / sentinel.SQLITE_EXPORT_NAME
    assert result.run_status == "NO_MATERIAL_CHANGE"
    assert json.loads(json_path.read_text(encoding="utf-8"))["schema_version"] == sentinel.READ_MODEL_VERSION
    assert (read_root / sentinel.OPERATOR_EXPORT_NAME).exists()
    assert (system_root / sentinel.SCHEMA_EXPORT_NAME).exists()
    assert (system_root / sentinel.SEED_EXPORT_NAME).exists()

    connection = sqlite3.connect(sqlite_path)
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert set(sentinel.REQUIRED_SQLITE_TABLES).issubset(tables)
    finally:
        connection.close()

    assert export_main(
        [
            "--read-model-root",
            str(read_root),
            "--system-knowledge-root",
            str(system_root),
            "--no-systemd",
            "--format",
            "json",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["schema_version"] == sentinel.READ_MODEL_VERSION


def test_source_does_not_call_forbidden_live_surfaces():
    source_files = [
        Path("openclaw_change_sentinel.py"),
        Path("scripts/export_openclaw_change_sentinel.py"),
    ]
    forbidden = [
        "git push",
        "git fetch",
        "git pull",
        "openai",
        "anthropic",
        "import requests",
        "import httpx",
        "urllib.request",
        "smtplib",
        "selenium",
        "playwright",
        "pyautogui",
        "openpyxl",
        "systemctl --user start",
        "systemctl --user restart",
        "systemctl --user enable",
        "shell=True",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for forbidden_text in forbidden:
            assert forbidden_text not in text
