import json
import re
from pathlib import Path

import make_winship_life_easier_batch_manifest as manifest
from scripts.export_make_winship_life_easier_batch_manifest import main as export_main


FIXED_NOW = "2026-05-23T14:05:00+00:00"


def _build() -> dict:
    return manifest.build_make_winship_life_easier_batch_manifest(generated_at=FIXED_NOW)


def test_manifest_is_deterministic_and_complete_pending_stable_map_import():
    first = _build()
    second = _build()

    assert manifest.stable_json(first) == manifest.stable_json(second)
    assert first["schema_version"] == manifest.SCHEMA_VERSION
    assert first["read_model_id"] == manifest.READ_MODEL_ID
    assert first["batch_id"] == "make_winship_life_easier_batch_v0"
    assert first["batch_status"] == "COMPLETE_PENDING_STABLE_MAP_IMPORT"
    assert first["stable_map_refresh_deferred"] is False
    assert first["commit_deferred_until_final_prompt"] is False
    assert first["current_prompt_index"] == 5
    assert first["total_prompts"] == 5
    assert first["machine_proof"]["batch_id_is_expected"] is True
    assert first["machine_proof"]["status_is_complete_pending_stable_map_import"] is True


def test_planned_lanes_and_prompt_1_completion_are_recorded():
    payload = _build()

    assert payload["lanes_planned"] == list(manifest.LANES_PLANNED)
    assert payload["lanes_completed"] == [
        "operator_work_mode_schema_bandwidth_policy",
        "operator_solve_path_and_decision_node_contract",
        "guided_capture_and_protected_evidence_path_contract",
        "workflow_session_channel_projection_approval_bus_contract",
        "automation_readiness_feasibility_and_integrated_stable_map_refresh",
    ]
    assert payload["machine_proof"]["planned_lane_count"] == 5
    assert payload["machine_proof"]["prompt_1_marked_complete"] is True
    assert payload["machine_proof"]["prompt_2_marked_complete"] is True
    assert payload["machine_proof"]["prompt_3_marked_complete"] is True
    assert payload["machine_proof"]["prompt_4_marked_complete"] is True
    assert payload["machine_proof"]["prompt_5_marked_complete"] is True
    assert payload["machine_proof"]["prompt_1_observed"] is True
    assert payload["machine_proof"]["prompt_2_observed"] is True
    assert payload["machine_proof"]["prompt_3_observed"] is True
    assert payload["machine_proof"]["prompt_4_observed"] is True
    assert payload["machine_proof"]["prompt_5_observed"] is True
    assert payload["machine_proof"]["completed_lane_count"] == 5
    lane_status = {lane["lane_id"]: lane["lane_status"] for lane in payload["lanes"]}
    assert lane_status["operator_work_mode_schema_bandwidth_policy"] == "COMPLETED"
    assert lane_status["operator_solve_path_and_decision_node_contract"] == "COMPLETED"
    assert lane_status["guided_capture_and_protected_evidence_path_contract"] == "COMPLETED"
    assert lane_status["workflow_session_channel_projection_approval_bus_contract"] == "COMPLETED"
    assert (
        lane_status["automation_readiness_feasibility_and_integrated_stable_map_refresh"]
        == "COMPLETED"
    )


def test_changed_files_and_validation_commands_include_required_prompt_1_artifacts():
    payload = _build()

    for path in manifest.PROMPT_1_CHANGED_FILES:
        assert path in payload["changed_files"]
    for path in manifest.PROMPT_2_CHANGED_FILES:
        assert path in payload["changed_files"]
    for path in manifest.PROMPT_3_CHANGED_FILES:
        assert path in payload["changed_files"]
    for path in manifest.PROMPT_4_CHANGED_FILES:
        assert path in payload["changed_files"]
    for path in manifest.PROMPT_5_CHANGED_FILES:
        assert path in payload["changed_files"]
    for command in manifest.PROMPT_1_VALIDATION_COMMANDS:
        assert command in payload["validation_commands"]
    for command in manifest.PROMPT_2_VALIDATION_COMMANDS:
        assert command in payload["validation_commands"]
    for command in manifest.PROMPT_3_VALIDATION_COMMANDS:
        assert command in payload["validation_commands"]
    for command in manifest.PROMPT_4_VALIDATION_COMMANDS:
        assert command in payload["validation_commands"]
    for command in manifest.PROMPT_5_VALIDATION_COMMANDS:
        assert command in payload["validation_commands"]
    for path in [
        ".gitignore",
        "operator_work_mode_schema_bandwidth_policy.py",
        "scripts/export_operator_work_mode_schema_bandwidth_policy.py",
        "tests/test_operator_work_mode_schema_bandwidth_policy.py",
        "generated/read_models/operator_work_mode_schema_bandwidth_policy.json",
        "generated/read_models/operator_work_mode_schema_bandwidth_policy_OPERATOR.md",
        "make_winship_life_easier_batch_manifest.py",
        "scripts/export_make_winship_life_easier_batch_manifest.py",
        "tests/test_make_winship_life_easier_batch_manifest.py",
        "generated/read_models/make_winship_life_easier_batch_manifest.json",
        "generated/read_models/make_winship_life_easier_batch_manifest_OPERATOR.md",
        "operator_solve_path_decision_node_contract.py",
        "scripts/export_operator_solve_path_decision_node_contract.py",
        "tests/test_operator_solve_path_decision_node_contract.py",
        "generated/read_models/operator_solve_path_decision_node_contract.json",
        "generated/read_models/operator_solve_path_decision_node_contract_OPERATOR.md",
        "guided_capture_protected_evidence_path_contract.py",
        "scripts/export_guided_capture_protected_evidence_path_contract.py",
        "tests/test_guided_capture_protected_evidence_path_contract.py",
        "generated/read_models/guided_capture_protected_evidence_path_contract.json",
        "generated/read_models/guided_capture_protected_evidence_path_contract_OPERATOR.md",
        "workflow_session_channel_projection_approval_bus_contract.py",
        "scripts/export_workflow_session_channel_projection_approval_bus_contract.py",
        "tests/test_workflow_session_channel_projection_approval_bus_contract.py",
        "generated/read_models/workflow_session_channel_projection_approval_bus_contract.json",
        "generated/read_models/workflow_session_channel_projection_approval_bus_contract_OPERATOR.md",
        "automation_readiness_feasibility_evaluator_contract.py",
        "scripts/export_automation_readiness_feasibility_evaluator_contract.py",
        "tests/test_automation_readiness_feasibility_evaluator_contract.py",
        "generated/read_models/automation_readiness_feasibility_evaluator_contract.json",
        "generated/read_models/automation_readiness_feasibility_evaluator_contract_OPERATOR.md",
    ]:
        assert path in payload["changed_files"]


def test_authority_boundary_denies_actions_commit_staging_and_stable_map_refresh():
    payload = _build()

    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    assert payload["authority_boundary"]["workflow_execution_allowed"] is False
    assert payload["authority_boundary"]["session_state_write_allowed"] is False
    assert payload["authority_boundary"]["channel_message_send_allowed"] is False
    assert payload["authority_boundary"]["screenshot_capture_allowed"] is False
    assert payload["authority_boundary"]["file_write_allowed"] is False
    assert payload["authority_boundary"]["file_upload_allowed"] is False
    assert payload["authority_boundary"]["automation_execution_allowed"] is False
    assert payload["authority_boundary"]["approval_submission_allowed"] is False
    assert payload["authority_boundary"]["invoice_generation_allowed"] is False
    assert payload["authority_boundary"]["ledger_write_allowed"] is False
    assert payload["authority_boundary"]["artifact_generation_allowed"] is False
    assert payload["authority_boundary"]["email_send_allowed"] is False
    assert payload["authority_boundary"]["telegram_send_allowed"] is False
    assert payload["authority_boundary"]["browser_automation_allowed"] is False
    assert payload["authority_boundary"]["coupa_access_allowed"] is False
    assert payload["authority_boundary"]["credential_handling_allowed"] is False
    assert payload["authority_boundary"]["protected_evidence_write_allowed"] is False
    assert payload["authority_boundary"]["receipt_write_allowed"] is False
    assert payload["authority_boundary"]["workflow_state_write_allowed"] is False
    assert payload["authority_boundary"]["live_model_calls_allowed"] is False
    assert payload["authority_boundary"]["model_call_allowed"] is False
    assert payload["authority_boundary"]["agent_activation_allowed"] is False
    assert payload["authority_boundary"]["tool_execution_allowed"] is False
    assert payload["authority_boundary"]["queue_execution_allowed"] is False
    assert payload["authority_boundary"]["runtime_dispatch_allowed"] is False
    assert payload["authority_boundary"]["stable_map_refresh_allowed"] is False
    assert payload["authority_boundary"]["commit_allowed"] is False
    assert payload["authority_boundary"]["staging_allowed"] is False
    assert payload["authority_boundary"]["supervised_browser_execution_allowed"] is False
    assert payload["authority_boundary"]["read_only_portal_lookup_allowed"] is False
    assert payload["authority_boundary"]["credential_broker_active"] is False
    assert payload["machine_proof"]["authority_boundary_false"] is True
    assert payload["machine_proof"]["no_live_execution_or_external_authority"] is True
    assert payload["batch_commit_policy"]["commit_allowed_now"] is False
    assert payload["batch_commit_policy"]["staging_allowed_now"] is False
    assert payload["batch_commit_policy"]["commit_deferred_until_final_prompt"] is False
    assert payload["stable_map_refresh_policy"]["stable_map_refresh_allowed_now"] is False
    assert payload["stable_map_refresh_policy"]["stable_map_refresh_deferred"] is False


def test_next_prompt_points_to_mac_map_import_agent():
    payload = _build()

    assert payload["next_prompt"] == "Mac map import/sync agent - import staged stable map bundle"
    assert payload["next_expected_actor"] == "mac_map_import_agent"
    assert payload["next_recommended_worker"] == "Mac map import/sync agent"


def test_no_credentials_secrets_private_bodies_or_c_drive_paths():
    payload = _build()
    text = manifest.stable_json(payload)

    assert payload["machine_proof"]["credentials_or_secrets_included"] is False
    assert payload["machine_proof"]["raw_private_bodies_included"] is False
    secret_patterns = [
        r"sk-[A-Za-z0-9_-]{20,}",
        r"xox[baprs]-[A-Za-z0-9-]{10,}",
        r"ghp_[A-Za-z0-9_]{20,}",
        r"AKIA[0-9A-Z]{16}",
        r"AIza[0-9A-Za-z_-]{20,}",
        r"BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY",
    ]
    for pattern in secret_patterns:
        assert re.search(pattern, text) is None


def test_exporter_writes_json_and_operator_markdown(tmp_path):
    result = export_main(
        [
            "--repo-root",
            tmp_path.as_posix(),
            "--export-root",
            "generated/read_models",
            "--format",
            "summary",
        ]
    )

    assert result == 0
    json_path = tmp_path / "generated" / "read_models" / manifest.JSON_EXPORT_NAME
    operator_path = tmp_path / "generated" / "read_models" / manifest.OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator = operator_path.read_text(encoding="utf-8")
    assert payload["batch_id"] == "make_winship_life_easier_batch_v0"
    assert payload["batch_status"] == "COMPLETE_PENDING_STABLE_MAP_IMPORT"
    assert payload["lanes_completed"] == [
        "operator_work_mode_schema_bandwidth_policy",
        "operator_solve_path_and_decision_node_contract",
        "guided_capture_and_protected_evidence_path_contract",
        "workflow_session_channel_projection_approval_bus_contract",
        "automation_readiness_feasibility_and_integrated_stable_map_refresh",
    ]
    assert "ELIWINSHIP Summary" in operator
    assert "Mac map import/sync agent" in operator


def test_source_has_no_disallowed_runtime_behavior():
    text = Path("make_winship_life_easier_batch_manifest.py").read_text(encoding="utf-8").lower()
    for token in [
        "subprocess",
        "shell=true",
        "os.system",
        "requests.",
        "urllib",
        "shutil.rmtree",
        "shutil.move",
        ".unlink(",
        ".rename(",
        "openai",
    ]:
        assert token not in text
