import json
from pathlib import Path

import helm_calm_surface as calm


FIXED_NOW = "2026-06-01T12:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_read_models(read_root: Path) -> None:
    _write_json(
        read_root / "helm_operator_attention_package.json",
        {
            "schema_version": "helm_operator_attention_package_v0",
            "read_model_id": "helm_operator_attention_package",
            "check_engine": {
                "status": "ACTION_REQUIRED",
                "active_count": 2,
                "operator_action_required": True,
                "operator_summary": "Check Engine needs attention.",
                "safe_next_move": "Open Chief diagnostic/system health lane; do not run repair automatically.",
            },
        },
    )
    _write_json(
        read_root / "openclaw_hermes_sidecar.json",
        {
            "schema_version": "openclaw_hermes_sidecar_v0",
            "read_model_id": "openclaw_hermes_sidecar",
            "readiness": "READY_FOR_RECOMMENDATION_NOT_EXECUTION",
            "confidence": "HIGH",
            "current_posture": {
                "recommends_only": True,
                "executes": False,
                "launches_chief": False,
                "calls_lm": False,
            },
            "recommended_next_package": {
                "recommended_next_lane": "finish_invoice_steel_thread_sequence",
                "package_ref": "chief_build_task:finish_invoice_steel_thread_sequence",
            },
            "machine_proof": {
                "hermes_daemon_launched": False,
                "chief_launched": False,
                "lm_called": False,
                "services_started": False,
                "live_action_recommended": False,
            },
        },
    )
    _write_json(
        read_root / "chief_check_engine_diagnostic_package.json",
        {
            "schema_version": "chief_check_engine_diagnostic_package_v0",
            "package_id": "chief_check_engine_diagnostic_package_v0",
            "current_status": "blocked_needs_chief_diagnostic_package",
            "check_engine_on": True,
            "diagnostic_mission": "Diagnose workbench, bridge, and tooling degradation without repair authority.",
            "signal_count": 4,
            "future_gated_repair_cleanup_remount_posture": {
                "this_package_may_execute_repair": False,
                "this_package_may_delete": False,
                "this_package_may_remount": False,
                "this_package_may_handle_credentials": False,
            },
            "no_authority_flags": {
                "backend_repair_authority_added": False,
            },
            "backend_repair_authority_added": False,
        },
    )


def _payload(tmp_path: Path) -> dict:
    read_root = tmp_path / "read_models"
    _fixture_read_models(read_root)
    return calm.build_helm_calm_surface(read_model_root=read_root, generated_at=FIXED_NOW)


def _unsafe_true_grants(payload: object, path: str = "$") -> list[str]:
    matches: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            child_path = f"{path}.{key}"
            if key in calm.UNSAFE_TRUE_GRANT_KEYS and value is True:
                matches.append(child_path)
            matches.extend(_unsafe_true_grants(value, child_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            matches.extend(_unsafe_true_grants(value, f"{path}[{index}]"))
    return matches


def test_export_writes_json_under_provided_read_model_root(tmp_path: Path) -> None:
    read_root = tmp_path / "read_models"
    _fixture_read_models(read_root)

    result = calm.export_helm_calm_surface(
        read_model_root=read_root,
        export_root=read_root,
        generated_at=FIXED_NOW,
    )

    json_path = read_root / calm.JSON_EXPORT_NAME
    assert result["json_path"] == json_path.as_posix()
    assert json_path.is_file()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == calm.SCHEMA_VERSION
    assert payload["read_model_id"] == calm.READ_MODEL_ID
    assert not (tmp_path / "generated").exists()


def test_required_top_level_fields_are_present(tmp_path: Path) -> None:
    payload = _payload(tmp_path)

    for key in (
        "schema_version",
        "read_model_id",
        "generated_at",
        "surface_mode",
        "source_manifest",
        "authority_flags",
        "privacy_impact",
        "check_engine_summary",
        "hermes_summary",
        "chief_summary",
        "check_engine",
        "hermes",
        "chief",
        "proof_drawer",
        "machine_proof",
    ):
        assert key in payload


def test_authority_flags_and_unsafe_grants_are_false(tmp_path: Path) -> None:
    payload = _payload(tmp_path)

    assert all(value is False for value in payload["authority_flags"].values())
    for key in calm.UNSAFE_TRUE_GRANT_KEYS:
        assert payload["authority_flags"][key] is False
    assert _unsafe_true_grants(payload) == []
    assert payload["machine_proof"]["authority_flags_all_false"] is True
    assert payload["machine_proof"]["unsafe_true_grants_absent"] is True


def test_proof_drawer_is_collapsed_refs_only(tmp_path: Path) -> None:
    payload = _payload(tmp_path)
    drawer = payload["proof_drawer"]

    assert drawer["collapsed_by_default"] is True
    assert drawer["raw_proof_visible_by_default"] is False
    assert payload["machine_proof"]["proof_drawer_collapsed"] is True
    assert {link["proof_ref"] for link in drawer["links"]} == {
        "generated/read_models/helm_operator_attention_package.json",
        "generated/read_models/openclaw_hermes_sidecar.json",
        "generated/read_models/chief_check_engine_diagnostic_package.json",
    }
    assert all(link["collapsed_by_default"] is True for link in drawer["links"])
    assert all(link["body_included"] is False for link in drawer["links"])
    assert payload["machine_proof"]["source_payloads_embedded"] is False


def test_hermes_chief_and_privacy_contract_are_safe(tmp_path: Path) -> None:
    payload = _payload(tmp_path)

    assert payload["hermes"]["execution_authority"] is False
    assert payload["chief"]["repair_authority"] is False
    assert payload["privacy_impact"]["final_provider_decision"] == "local_only"
    assert payload["machine_proof"]["hermes_execution_authority_false"] is True
    assert payload["machine_proof"]["chief_repair_authority_false"] is True
    assert payload["machine_proof"]["privacy_impact_local_only"] is True


def test_generated_fixture_includes_required_summaries(tmp_path: Path) -> None:
    payload = _payload(tmp_path)

    assert payload["check_engine_summary"] == "Check Engine needs attention."
    assert "Hermes recommends finish_invoice_steel_thread_sequence" in payload["hermes_summary"]
    assert "Chief diagnostic package is blocked_needs_chief_diagnostic_package" in payload["chief_summary"]
