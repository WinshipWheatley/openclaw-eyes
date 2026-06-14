import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_hermes_sidecar as sidecar
from scripts.export_openclaw_hermes_sidecar import main as export_main


FIXED_NOW = "2026-05-31T23:00:00+00:00"


def _write_json(read_root: Path, path_value: str, payload: dict) -> None:
    path = read_root / path_value.removeprefix("generated/read_models/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixtures(read_root: Path, *, stale: bool = False, material_change: bool = False) -> None:
    _write_json(
        read_root,
        "generated/read_models/hermes_mission_sentinel.json",
        {"schema_version": "hermes_mission_sentinel_v0", "machine_proof": {"read_model_only": True}},
    )
    _write_json(
        read_root,
        "generated/read_models/hermes_gravity_controller.json",
        {"schema_version": "hermes_gravity_controller_v0", "machine_proof": {"read_model_only": True}},
    )
    _write_json(
        read_root,
        "generated/read_models/purpose_bound_automation_charter.json",
        {"schema_version": "purpose_bound_automation_charter_v0", "machine_proof": {"read_model_only": True}},
    )
    _write_json(
        read_root,
        "generated/read_models/hermes_chief_build_handoff.json",
        {"schema_version": "hermes_chief_build_handoff_v0", "recommended_chief_tasks": []},
    )
    _write_json(
        read_root,
        "generated/read_models/openclaw_change_sentinel.json",
        {
            "schema_version": "openclaw_change_sentinel_read_model_v0",
            "run_status": "MATERIAL_CHANGE" if material_change else "NO_MATERIAL_CHANGE",
            "material_change_count": 1 if material_change else 0,
            "material_changes": (
                [{"change_ref": "change:fixture", "change_kind": "SOURCE_CHANGE", "summary": "Fixture material change."}]
                if material_change
                else []
            ),
        },
    )
    _write_json(
        read_root,
        "generated/read_models/openclaw_lane_capability_harvest.json",
        {
            "schema_version": "openclaw_lane_capability_harvest_read_model_v0",
            "confidence": "HIGH",
            "lanes": [
                {"lane_ref": "live_arts_md_invoice_lane", "status": "ACTIVE_STEEL_THREAD"},
                {"lane_ref": "capital_hilton_invoice_lane", "status": "PARTIAL"},
                {"lane_ref": "st_annes_invoice_lane", "status": "PARTIAL"},
            ],
            "do_not_work_now": [
                "ledger posting before proof and approval gates are proven",
                "generic Telegram polish before object rails are stable",
            ],
            "hermes_recommendation": {
                "recommended_next_lane": "finish_invoice_steel_thread_sequence",
                "chief_build_task_ref": "chief_build_task:finish_invoice_steel_thread_sequence",
                "confidence": "HIGH",
                "reason": "Live Arts, Capital Hilton, and St. Anne's are not all proven.",
                "expected_new_capability": "completed reusable invoice steel-thread sequence",
            },
        },
    )
    _write_json(
        read_root,
        "generated/read_models/openclaw_business_object_layer_audit.json",
        {
            "schema_version": "openclaw_business_object_layer_audit_read_model_v0",
            "readiness": "READY_FOR_BUILD_PLANNING_NOT_EXECUTION",
            "freshness_status": "STALE" if stale else "FRESH",
            "stale_reasons": ["fixture stale audit"] if stale else [],
        },
    )
    _write_json(
        read_root,
        "generated/read_models/openclaw_context_wiki_index.json",
        {
            "schema_version": "openclaw_context_wiki_compiler_v0",
            "business_object_audit_freshness_status": "STALE" if stale else "FRESH",
            "business_object_audit_stale_reasons": ["fixture stale wiki"] if stale else [],
            "missing_inputs": [],
        },
    )
    _write_json(
        read_root,
        "generated/read_models/openclaw_authority_semantics_registry.json",
        {
            "schema_version": "openclaw_authority_semantics_registry_v0",
            "active_drift_signals": [],
            "authority_profiles": [
                {
                    "dangerous_authorities": ["ledger_post_allowed", "email_send_allowed", "browser_access_allowed"],
                    "blocked_actions": ["post ledger", "send email", "access browser", "access Gmail", "access Coupa"],
                }
            ],
        },
    )
    _write_json(
        read_root,
        "generated/read_models/openclaw_lm_child_package_gate.json",
        {
            "schema_version": "openclaw_lm_child_package_gate_v0",
            "readiness": "READY_FOR_CONTRACT_NOT_RUNTIME_SPAWNING",
            "machine_proof": {"child_spawning_enabled": False, "runtime_swarm_enabled": False},
        },
    )
    _write_json(
        read_root,
        "generated/read_models/openclaw_estate_topology_registry.json",
        {"schema_version": "openclaw_estate_topology_registry_read_model_v0"},
    )
    _write_json(
        read_root,
        "generated/read_models/openclaw_reference_resolver.json",
        {"schema_version": "openclaw_reference_resolver_read_model_v0", "drift_count": 0},
    )
    _write_json(
        read_root,
        "generated/read_models/openclaw_service_keeper_status.json",
        {
            "schema_version": "openclaw_service_keeper_status_v0",
            "run_status": "NO_ACTION_REQUIRED",
            "checked_units": ["openclaw-request-response.service"],
            "unit_results": [
                {
                    "unit_name": "openclaw-request-response.service",
                    "status": "NO_ACTION_REQUIRED",
                    "active_state_after": "active",
                    "started": False,
                }
            ],
            "starts_arbitrary_services": False,
            "restarts_active_services": False,
        },
    )


def _payload(tmp_path: Path, **kwargs) -> dict:
    read_root = tmp_path / "read_models"
    _fixtures(read_root, **kwargs)
    return sidecar.build_hermes_sidecar(read_model_root=read_root, generated_at=FIXED_NOW)


def test_hermes_sidecar_exports_json_md_and_sqlite(tmp_path: Path) -> None:
    read_root = tmp_path / "read_models"
    system_root = tmp_path / "system_knowledge"
    _fixtures(read_root)

    assert export_main(
        [
            "--read-model-root",
            str(read_root),
            "--system-knowledge-root",
            str(system_root),
            "--generated-at",
            FIXED_NOW,
        ]
    ) == 0

    assert (read_root / sidecar.JSON_EXPORT_NAME).is_file()
    assert (read_root / sidecar.OPERATOR_EXPORT_NAME).is_file()
    assert (system_root / sidecar.SQLITE_EXPORT_NAME).is_file()
    assert (system_root / sidecar.SCHEMA_EXPORT_NAME).is_file()
    assert (system_root / sidecar.SEED_EXPORT_NAME).is_file()


def test_reads_lane_harvest_and_recommends_finish_invoice_sequence(tmp_path: Path) -> None:
    payload = _payload(tmp_path)

    assert payload["active_steel_thread"]["steel_thread_ref"] == "invoice_steel_thread_sequence"
    assert payload["recommended_next_package"]["recommended_next_lane"] == "finish_invoice_steel_thread_sequence"
    assert payload["recommended_next_package"]["package_ref"] == "chief_build_task:finish_invoice_steel_thread_sequence"


def test_cites_authority_semantics_registry(tmp_path: Path) -> None:
    payload = _payload(tmp_path)

    assert "generated/read_models/openclaw_authority_semantics_registry.json" in payload["source_refs"]
    assert payload["authority_drift"]["source_ref"] == "generated/read_models/openclaw_authority_semantics_registry.json"


def test_includes_do_not_touch_list(tmp_path: Path) -> None:
    payload = _payload(tmp_path)

    assert "ledger posting before proof and approval gates are proven" in payload["do_not_touch"]
    assert "launch Chief" in payload["do_not_touch"]
    assert "call LM" in payload["do_not_touch"]


def test_refuses_live_ledger_email_browser_actions(tmp_path: Path) -> None:
    payload = _payload(tmp_path)
    forbidden = " ".join(payload["chief_forbidden_actions"]).lower()
    allowed = " ".join(payload["recommended_next_package"]["allowed_actions"]).lower()

    assert "ledger" in forbidden
    assert "email" in forbidden
    assert "browser" in forbidden
    assert "ledger" not in allowed
    assert "email" not in allowed
    assert "browser" not in allowed
    assert payload["machine_proof"]["live_action_recommended"] is False


def test_reduces_confidence_on_stale_audit_or_wiki(tmp_path: Path) -> None:
    payload = _payload(tmp_path, stale=True)

    assert payload["confidence"] == "MEDIUM"
    assert payload["current_posture"]["stale_confidence_reduced"] is True
    assert {row["surface_ref"] for row in payload["stale_surfaces"]} == {
        "business_object_audit",
        "context_wiki_index",
    }


def test_material_change_prioritizes_diagnosis_over_feature_work(tmp_path: Path) -> None:
    payload = _payload(tmp_path, material_change=True)

    assert payload["recommended_next_package"]["recommended_next_lane"] == "diagnose_material_change_before_feature_work"
    assert payload["recommended_next_package"]["package_ref"] == "hermes_package:diagnose_material_change"
    assert payload["current_posture"]["material_change_priority_active"] is True


def test_does_not_call_lm_or_chief(tmp_path: Path) -> None:
    payload = _payload(tmp_path)

    assert payload["current_posture"]["calls_lm"] is False
    assert payload["current_posture"]["launches_chief"] is False
    assert payload["machine_proof"]["lm_called"] is False
    assert payload["machine_proof"]["chief_launched"] is False
    assert payload["machine_proof"]["hermes_daemon_launched"] is False


def test_json_parses_and_sqlite_integrity_passes(tmp_path: Path) -> None:
    read_root = tmp_path / "read_models"
    system_root = tmp_path / "system_knowledge"
    _fixtures(read_root)

    assert export_main(
        [
            "--read-model-root",
            str(read_root),
            "--system-knowledge-root",
            str(system_root),
            "--generated-at",
            FIXED_NOW,
        ]
    ) == 0

    payload = json.loads((read_root / sidecar.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    assert payload["schema_version"] == sidecar.SCHEMA_VERSION

    connection = sqlite3.connect(system_root / sidecar.SQLITE_EXPORT_NAME)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert set(sidecar.REQUIRED_SQLITE_TABLES).issubset(tables)
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()
