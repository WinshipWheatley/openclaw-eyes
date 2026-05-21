import json
from pathlib import Path

import agent_platform_alignment as alignment
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_agent_platform_alignment import main as export_main


FIXED_NOW = "2026-05-21T21:30:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    read_models = root / "generated" / "read_models"
    fixtures = {
        "package_compiler_contract.json": {
            "schema_version": "package_compiler_contract_v0",
            "read_model_id": "package_compiler_contract",
        },
        "operator_workbench_actor_host_registry.json": {
            "schema_version": "operator_workbench_actor_host_registry_v0",
            "read_model_id": "operator_workbench_actor_host_registry",
        },
        "capability_skill_registry_metadata_delta.json": {
            "schema_version": "capability_skill_registry_metadata_delta_v0",
            "read_model_id": "capability_skill_registry_metadata_delta",
        },
        "protected_access_broker_concept.json": {
            "schema_version": "protected_access_broker_concept_v0",
            "read_model_id": "protected_access_broker_concept",
        },
        "guardian_protected_access_gate_spec.json": {
            "schema_version": "guardian_protected_access_gate_spec_v0",
            "read_model_id": "guardian_protected_access_gate_spec",
        },
        "protected_evidence_reference_receipt.json": {
            "schema_version": "protected_evidence_reference_receipt_v0",
            "read_model_id": "protected_evidence_reference_receipt",
        },
        "cassandra_email_calendar_delta_detangle.json": {
            "schema_version": "cassandra_email_calendar_delta_detangle_v0",
            "read_model_id": "cassandra_email_calendar_delta_detangle",
        },
        "work_board.json": {
            "schema_version": "work_board_read_model_v0",
            "read_model_id": "work_board",
        },
        "operator_awareness_agent_package_spine.json": {
            "schema_version": "operator_awareness_agent_package_spine_v0",
            "read_model_id": "operator_awareness_agent_package_spine",
        },
        "operator_nested_lane_mission_package_spine.json": {
            "schema_version": "operator_nested_lane_mission_package_spine_v0",
            "read_model_id": "operator_nested_lane_mission_package_spine",
        },
        "sync_health.json": {
            "schema_version": "sync_health_read_model_v0",
            "read_model_id": "sync_health",
            "app_visible_map_status": {"map_status": "map_current"},
        },
        "operator_map_bundle_contract.json": {
            "schema_version": "operator_map_bundle_contract_v0",
            "read_model_id": "operator_map_bundle_contract",
        },
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)


def _build(tmp_path: Path) -> dict:
    _fixture_repo(tmp_path)
    return alignment.build_agent_platform_alignment(repo_root=tmp_path, generated_at=FIXED_NOW)


def test_alignment_is_deterministic_metadata_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert alignment.stable_json(first) == alignment.stable_json(second)
    assert first["schema_version"] == alignment.SCHEMA_VERSION
    assert first["read_model_id"] == "agent_platform_alignment"
    assert first["alignment_status"] == "deterministic_read_model_only"
    assert first["runtime_authority"] is False
    assert first["activation_allowed"] is False
    assert first["backend_execution_authorized"] is False
    assert first["external_tool_authority"] is False
    assert first["credential_authority"] is False
    assert first["agent_self_authority"] is False
    assert first["platform_translation"]["always_on_agent_position"] == "future_gated_readiness_only"


def test_existing_primitives_map_to_openclaw_contracts(tmp_path):
    payload = _build(tmp_path)
    primitives = {item["primitive_id"]: item for item in payload["existing_openclaw_primitives"]}

    assert "package_compiler_contract" in primitives
    assert "capability_skill_registry" in primitives
    assert "protected_access_gates" in primitives
    assert "cassandra_comms_detangle" in primitives
    assert "chief_work_and_health_posture" in primitives
    assert "mission_control_awareness_spine" in primitives
    assert "stable_map_and_sync_receipts" in primitives
    assert primitives["package_compiler_contract"]["live_runtime_authority"] is False
    assert primitives["stable_map_and_sync_receipts"]["credential_or_external_tool_authority"] is False


def test_missing_platform_primitives_include_identity_router_memory_and_kill_switch(tmp_path):
    payload = _build(tmp_path)
    missing = {item["primitive_id"]: item for item in payload["missing_platform_primitives"]}

    assert "durable_agent_identity_registry" in missing
    assert "actor_model_router_contract" in missing
    assert "memory_scope_contract" in missing
    assert "tool_protocol_adapter_registry" in missing
    assert "per_agent_clearance_levels" in missing
    assert "task_queue_lifecycle_receipts" in missing
    assert "action_result_receipts" in missing
    assert "revocation_kill_switch_contract" in missing
    assert "compromise_suspicion_posture" in missing
    assert missing["task_queue_lifecycle_receipts"]["readiness_state"] == "POST_SECURITY_FUTURE_GATED"


def test_blocked_capabilities_remain_blocked_and_future_gated(tmp_path):
    payload = _build(tmp_path)
    blocked = {item["capability_id"]: item for item in payload["blocked_capabilities"]}

    for capability_id in [
        "autonomous_email_send",
        "calendar_mutation",
        "browser_coupa_credential_use",
        "oauth_tool_bridge_activation",
        "network_execution",
        "runtime_daemon_claims",
        "agent_self_assigned_authority",
        "hidden_memory_capture",
        "background_surveillance",
        "broad_file_indexing",
    ]:
        assert blocked[capability_id]["status"] == "blocked_or_future_gated"
    assert payload["gmail_calendar_coupa_telegram_enabled"] is False
    assert payload["browser_oauth_account_access_enabled"] is False
    assert payload["network_execution_enabled"] is False


def test_recommended_next_lane_is_agent_identity_actor_router(tmp_path):
    payload = _build(tmp_path)

    assert payload["next_safe_lane"]["lane_id"] == "agent_identity_actor_router_contract_v0"
    assert payload["recommended_next_lanes"][0]["lane_id"] == "agent_identity_actor_router_contract_v0"
    assert "durable agent identity records" in payload["recommended_next_lanes"][0]["output_should_define"]
    assert "No package-routing" in payload["missing_platform_primitives"][0]["blocked_until"]


def test_mission_control_guidance_is_helm_oriented_not_backend_table_wall(tmp_path):
    payload = _build(tmp_path)
    guidance = payload["mission_control_surface_guidance"]

    assert "readiness mapping" in guidance["top_layer_what_this_means"]
    assert "do not render this as a backend table wall" in guidance["lower_layer_proof_contract_refs"]
    assert "show uncertainty only when it changes the next safe move" in guidance["confidence_display_rule"]
    assert guidance["helm_guidance"].endswith("not an execution or chat surface.")


def test_evidence_sources_are_bounded_and_report_presence(tmp_path):
    payload = _build(tmp_path)
    sources = {item["source_id"]: item for item in payload["evidence_sources"]}

    assert sources["package_compiler_contract"]["present"] is True
    assert sources["operator_map_bundle_contract"]["present"] is True
    assert all(item["raw_private_body_imported"] is False for item in sources.values())
    assert all(item["authority_granted_by_source_presence"] is False for item in sources.values())


def test_export_script_writes_json_and_operator_outputs(tmp_path, capsys):
    _fixture_repo(tmp_path)
    export_root = tmp_path / "generated" / "read_models"

    exit_code = export_main(
        [
            "--repo-root",
            tmp_path.as_posix(),
            "--export-root",
            export_root.as_posix(),
            "--format",
            "summary",
        ]
    )

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["schema_version"] == alignment.SCHEMA_VERSION
    assert summary["runtime_authority_added"] is False
    assert summary["credential_authority_added"] is False
    payload = json.loads((export_root / alignment.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / alignment.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    assert payload["read_model_id"] == "agent_platform_alignment"
    assert "Agent Platform Alignment v0" in operator


def test_generated_outputs_are_canonical_read_model_files(tmp_path):
    _fixture_repo(tmp_path)
    export_root = tmp_path / "generated" / "read_models"
    alignment.export_agent_platform_alignment(repo_root=tmp_path, export_root=export_root, generated_at=FIXED_NOW)

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))

    assert alignment.JSON_EXPORT_NAME in expected
    assert alignment.OPERATOR_EXPORT_NAME in expected


def test_source_has_no_runtime_or_c_drive_authority_strings():
    text = Path("agent_platform_alignment.py").read_text(encoding="utf-8").lower()
    for token in [
        "subprocess",
        "shell=true",
        "os.system",
        "import requests",
        "httpx.",
        "urllib.request",
        "/mnt/" + "c/openclaw",
        "c:\\openclaw",
        ".unlink(",
        "shutil.rmtree",
        "shutil.move",
    ]:
        assert token not in text
