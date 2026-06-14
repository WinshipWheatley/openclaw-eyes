import json
from pathlib import Path

import helm_operator_attention_package as helm
from scripts.export_helm_operator_attention_package import main as export_main


FIXED_NOW = "2026-05-27T20:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(
    root: Path,
    *,
    check_engine_status: str = "QUIET",
    check_engine_operator_action_required: bool | None = False,
) -> None:
    read_models = root / "generated" / "read_models"
    health_light = {
        "light_id": "check_engine",
        "display_name": "Check Engine",
        "current_status": check_engine_status,
        "opens_lane": "Chief diagnostic lane",
        "safe_next_move": "Review the issue." if check_engine_status != "QUIET" else "No action needed.",
        "evidence_inputs": ["generated/read_models/system_health_lights_taxonomy.json"],
        "forbidden_actions": ["perform automatic repair"],
    }
    if check_engine_operator_action_required is not None:
        health_light["operator_action_required"] = check_engine_operator_action_required
    _write_json(
        read_models / "system_health_lights_taxonomy.json",
        {
            "schema_version": "system_health_lights_taxonomy_v0",
            "generated_at": FIXED_NOW,
            "current_light_states": {
                "check_engine": check_engine_status,
                "check_transmission": "QUIET",
            },
            "lights": [
                health_light,
                {
                    "light_id": "check_transmission",
                    "display_name": "Check Transmission",
                    "current_status": "QUIET",
                    "operator_action_required": False,
                    "opens_lane": "Bridge status",
                    "safe_next_move": "No action needed.",
                    "evidence_inputs": ["generated/read_models/sync_health.json"],
                },
            ],
            "next_recommended_lane": {"operator_action_required_now": False},
        },
    )
    _write_json(
        read_models / "operator_mission_priority_helm_declutter.json",
        {
            "schema_version": "operator_mission_priority_helm_declutter_v0",
            "generated_at": FIXED_NOW,
            "classification_items": [
                {
                    "item_id": "agent_awareness_tracking",
                    "display_name": "Agent awareness tracking",
                    "bucket": "helm_lanes",
                    "current_status_from_source": "PARKED",
                    "next_safe_move": "Keep collapsed unless an agent lane needs attention.",
                    "source_refs": ["generated/read_models/agent_terrain_awareness_readback_contract.json"],
                },
                {
                    "item_id": "package_preview_detour_flow",
                    "display_name": "Package preview",
                    "bucket": "helm_lanes",
                    "current_status_from_source": "PARKED",
                    "next_safe_move": "Keep package detail behind disclosure.",
                    "source_refs": ["generated/read_models/package_preview_receipt_contract.json"],
                },
                {
                    "item_id": "raw_contracts_receipts_long_paths",
                    "display_name": "Proof shelf",
                    "bucket": "proof_detail",
                    "current_status_from_source": "PARKED",
                    "next_safe_move": "Show proof only when asked.",
                    "source_refs": ["generated/read_models/operator_mission_priority_helm_declutter.json"],
                },
                {
                    "item_id": "deep_domain_work",
                    "display_name": "Deep domain work",
                    "bucket": "parked",
                    "current_status_from_source": "PARKED",
                    "next_safe_move": "Keep parked until it blocks the current issue.",
                    "source_refs": ["generated/read_models/cross_repo_awareness_matrix.json"],
                },
            ],
        },
    )
    _write_json(
        read_models / "request_response_bridge_readiness.json",
        {
            "schema_version": "request_response_bridge_readiness_v0",
            "readiness_status": "READY_FOR_LIVE_REVIEW",
            "machine_proof": {"per_request_response_written": True},
        },
    )
    _write_json(
        read_models / "openclaw_request_response_service_status.json",
        {
            "schema_version": "openclaw_request_response_service_status_v0",
            "machine_proof": {
                "response_path_present": True,
                "per_request_response_written": True,
            },
        },
    )
    _write_json(
        read_models / "floor_gap_reconciliation.json",
        {
            "schema_version": "floor_gap_reconciliation_v0",
            "generated_at": FIXED_NOW,
            "dashboard_honesty": {
                "next_blockers": [
                    "provider_activation_receipts_missing",
                    "live_model_enablement_receipt_missing",
                ]
            },
        },
    )
    for name in (
        "lm_readiness_dashboard.json",
        "operator_readiness_surface.json",
        "openclaw_map_manifest.json",
        "security_pass_contract.json",
        "package_preview_receipt_contract.json",
        "agent_terrain_awareness_readback_contract.json",
    ):
        _write_json(read_models / name, {"schema_version": f"{name}_fixture"})


def _build(tmp_path: Path, **kwargs) -> dict:
    repo = tmp_path / "repo"
    _fixture_repo(repo, **kwargs)
    return helm.build_helm_operator_attention_package(repo_root=repo, generated_at=FIXED_NOW)


def _surface(payload: dict, surface_ref: str) -> dict:
    return next(item for item in payload["hidden_or_collapsed_surfaces"] if item["surface_ref"] == surface_ref)


def test_helm_package_renders_chat_first_by_default(tmp_path):
    payload = _build(tmp_path)

    assert payload["schema_version"] == helm.SCHEMA_VERSION
    assert payload["read_model_id"] == helm.READ_MODEL_ID
    assert payload["helm_mode"] == "CHAT_FIRST"
    assert payload["connection_state"]["openclaw_connected"] is True
    assert payload["connection_state"]["operator_copy"] == "OpenClaw is connected."


def test_agent_council_and_package_preview_are_not_primary_without_action(tmp_path):
    payload = _build(tmp_path)

    assert _surface(payload, "agent_council")["visibility"] != "PRIMARY"
    assert _surface(payload, "package_preview_bay")["visibility"] != "PRIMARY"
    assert not any("agent council" in card["title"].lower() for card in payload["primary_cards"])
    assert not any("package preview" in card["title"].lower() for card in payload["primary_cards"])


def test_stable_map_security_and_boundary_proofs_are_not_primary_by_default(tmp_path):
    payload = _build(tmp_path)

    assert _surface(payload, "stable_map_proof")["visibility"] == "PROOF_ONLY"
    assert _surface(payload, "security_pass_details")["visibility"] == "PROOF_ONLY"
    assert _surface(payload, "boundary_proof")["visibility"] == "PROOF_ONLY"
    assert _surface(payload, "readiness_internals")["visibility"] == "PROOF_ONLY"


def test_check_engine_quiet_produces_no_urgent_primary_card(tmp_path):
    payload = _build(tmp_path, check_engine_status="QUIET", check_engine_operator_action_required=False)

    assert payload["check_engine"]["status"] == "QUIET"
    assert payload["primary_cards"] == []
    assert payload["operator_copy"]["headline"] == "Check Engine is quiet."


def test_check_engine_warning_with_operator_action_required_selects_one_primary_card(tmp_path):
    payload = _build(tmp_path, check_engine_status="WARNING", check_engine_operator_action_required=True)

    assert payload["check_engine"]["status"] == "ACTION_REQUIRED"
    assert len(payload["primary_cards"]) == 1
    card = payload["primary_cards"][0]
    assert card["title"] == "Check Engine"
    assert card["actionability"] == "FIX_REQUIRED"
    assert card["button_suggestions"]


def test_proof_shelf_retains_refs(tmp_path):
    payload = _build(tmp_path)
    refs = {item["proof_ref"] for item in payload["proof_shelf"]}

    assert "generated/read_models/operator_mission_priority_helm_declutter.json" in refs
    assert "generated/read_models/system_health_lights_taxonomy.json" in refs
    assert "generated/read_models/openclaw_map_manifest.json" in refs
    assert "generated/read_models/security_pass_contract.json" in refs


def test_operator_copy_contains_no_backend_sludge_terms(tmp_path):
    payload = _build(tmp_path, check_engine_status="WARNING", check_engine_operator_action_required=True)
    text = json.dumps(payload["operator_copy"], sort_keys=True).lower()

    for term in helm.BACKEND_SLUDGE_TERMS:
        assert term not in text
    assert payload["machine_proof"]["operator_copy_backend_sludge_free"] is True


def test_awareness_matrix_summarizes_signals_instead_of_exposing_full_cards(tmp_path):
    payload = _build(tmp_path)
    matrix = payload["awareness_matrix"]

    assert matrix["summary_only"] is True
    assert "classification_items" not in matrix
    assert matrix["counts"]["total_signals_considered"] >= 4
    assert isinstance(matrix["active_signals"], list)
    assert isinstance(matrix["proof_only_signals"], list)


def test_missing_operator_action_required_is_derived_and_reported(tmp_path):
    payload = _build(tmp_path, check_engine_status="WARNING", check_engine_operator_action_required=None)

    assert payload["missing_upstream_fields"]
    assert any(item["missing_field"] == "operator_action_required" for item in payload["missing_upstream_fields"])
    assert payload["check_engine"]["status"] == "ACTION_REQUIRED"


def test_attention_policy_is_explicit_and_primary_cards_are_limited(tmp_path):
    payload = _build(tmp_path, check_engine_status="WARNING", check_engine_operator_action_required=True)

    assert payload["attention_policy"]["default_helm_mode"] == "CHAT_FIRST"
    assert payload["attention_policy"]["max_primary_cards"] == 3
    assert len(payload["primary_cards"]) <= 3
    assert "operator_action_required=true" in payload["attention_policy"]["primary_only_if"]


def test_generated_read_model_parses(tmp_path):
    repo = tmp_path / "repo"
    _fixture_repo(repo, check_engine_status="WARNING", check_engine_operator_action_required=True)
    export_root = repo / "generated" / "read_models"

    assert export_main([
        "--repo-root",
        repo.as_posix(),
        "--export-root",
        export_root.as_posix(),
        "--generated-at",
        FIXED_NOW,
    ]) == 0

    payload = json.loads((export_root / helm.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator_text = (export_root / helm.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    assert payload["read_model_id"] == helm.READ_MODEL_ID
    assert payload["check_engine"]["status"] == "ACTION_REQUIRED"
    assert "Helm Operator Attention Package" in operator_text


def test_no_action_authority_is_enabled(tmp_path):
    payload = _build(tmp_path, check_engine_status="WARNING", check_engine_operator_action_required=True)

    assert all(value is False for value in payload["authority_boundary"].values())
    assert payload["machine_proof"]["live_lm_call_performed"] is False
    assert payload["machine_proof"]["tool_execution_performed"] is False
    assert payload["machine_proof"]["external_action_performed"] is False
