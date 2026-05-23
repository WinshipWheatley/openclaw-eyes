import json
import re
from pathlib import Path

import guided_capture_protected_evidence_path_contract as contract
from scripts.export_guided_capture_protected_evidence_path_contract import main as export_main


FIXED_NOW = "2026-05-23T16:00:00+00:00"


def _build() -> dict:
    return contract.build_guided_capture_protected_evidence_path_contract(generated_at=FIXED_NOW)


def _paths(payload: dict) -> dict:
    return payload["capture_paths_by_id"]


def _moments(payload: dict) -> dict:
    return payload["capture_moments_by_id"]


def _targets(payload: dict) -> dict:
    return payload["artifact_targets_by_id"]


def _outcomes(payload: dict) -> dict:
    return payload["capture_outcomes_by_id"]


def _guards(payload: dict) -> dict:
    return payload["privacy_guards_by_id"]


def test_contract_is_deterministic_and_read_model_only():
    first = _build()
    second = _build()

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == contract.READ_MODEL_ID
    assert first["contract_status"] == contract.CONTRACT_STATUS
    assert first["hard_rule"]["read_model_only"] is True
    assert first["hard_rule"]["does_not_implement_actual_capture"] is True
    assert first["hard_rule"]["does_not_implement_screenshot_buttons"] is True
    assert first["hard_rule"]["does_not_write_files"] is True
    assert first["hard_rule"]["does_not_create_file_pickers"] is True
    assert first["hard_rule"]["does_not_access_browser_coupa_email_accounts"] is True
    assert first["hard_rule"]["does_not_persist_operator_answers"] is True
    assert first["hard_rule"]["does_not_refresh_stable_map"] is True
    assert first["hard_rule"]["may_capture_screenshot_now"] is False
    assert first["hard_rule"]["may_write_protected_evidence_now"] is False
    assert first["hard_rule"]["may_write_receipt_now"] is False
    assert first["hard_rule"]["may_write_workflow_state_now"] is False


def test_guided_capture_models_and_required_fields_exist():
    payload = _build()

    assert payload["machine_proof"]["guided_capture_path_model_present"] is True
    assert payload["machine_proof"]["capture_moment_model_present"] is True
    assert payload["machine_proof"]["artifact_target_model_present"] is True
    assert payload["machine_proof"]["capture_outcome_model_present"] is True
    assert payload["machine_proof"]["privacy_guards_present"] is True
    assert payload["guided_capture_path_schema"]["required_fields"] == list(contract.REQUIRED_CAPTURE_PATH_FIELDS)
    assert payload["guided_capture_moment_schema"]["required_fields"] == list(contract.REQUIRED_CAPTURE_MOMENT_FIELDS)
    assert payload["protected_evidence_artifact_target_schema"]["required_fields"] == list(
        contract.REQUIRED_ARTIFACT_TARGET_FIELDS
    )
    assert payload["guided_capture_outcome_schema"]["required_fields"] == list(
        contract.REQUIRED_CAPTURE_OUTCOME_FIELDS
    )
    assert payload["capture_privacy_guard_schema"]["required_fields"] == list(
        contract.REQUIRED_PRIVACY_GUARD_FIELDS
    )
    assert set(payload["recommended_capture_methods"]) == set(contract.RECOMMENDED_CAPTURE_METHODS)
    assert set(payload["artifact_types"]) == set(contract.ARTIFACT_TYPES)
    assert set(payload["outcome_types"]) == set(contract.OUTCOME_TYPES)


def test_capital_hilton_coupa_po_capture_path_exists_and_is_protected():
    payload = _build()
    paths = _paths(payload)
    moments = _moments(payload)

    assert "capital_hilton_coupa_po_screen_capture_path" in paths
    path = paths["capital_hilton_coupa_po_screen_capture_path"]
    assert set(contract.REQUIRED_CAPTURE_PATH_FIELDS) <= set(path)
    assert path["world"] == "Finance"
    assert path["lane"] == "Capital Hilton"
    assert path["truth_needed"] == "PO/reference metadata or confirmation none exists."
    assert path["recommended_capture_method"] == "GUIDED_SCREENSHOT_CAPTURE"
    assert path["operator_goal"] == "Get to the Coupa/PO/reference screen."
    assert path["capture_moment_prompt"] == "Is this the Capital Hilton PO/reference screen we should capture?"
    assert path["protected_evidence_required"] is True
    assert path["guardian_review_required"] is True
    assert path["authority_granted"] is False
    assert "credentials" in path["blocked_capture_inputs"]
    assert "raw portal scrape" in path["blocked_capture_inputs"]
    assert "log in" not in " ".join(path["system_can_do_now"]).lower()
    assert "capital_hilton_coupa_po_screen_capture_path_moment" in moments
    moment = moments["capital_hilton_coupa_po_screen_capture_path_moment"]
    assert moment["display_prompt"] == path["capture_moment_prompt"]
    assert moment["ready_phrase"] == "Is this the thing we are supposed to capture?"
    assert moment["confirm_button_label"] == "Yes, this is it"
    assert moment["cancel_button_label"] == "Cancel"
    assert moment["not_the_right_thing_label"] == "Not the right thing"
    assert moment["capture_authority_currently_granted"] is False
    assert payload["machine_proof"]["capital_hilton_coupa_po_example_present"] is True


def test_app_wide_capture_examples_exist():
    payload = _build()
    paths = _paths(payload)

    expected = {
        "capital_hilton_coupa_po_screen_capture_path",
        "capital_hilton_rate_source_capture_path",
        "check_engine_diagnostic_screenshot_capture_path",
        "chief_terrain_source_note_capture_path",
        "cassandra_draft_review_capture_path",
        "niles_struna_project_reference_capture_path",
        "client_project_delivery_reference_capture_path",
    }
    assert expected <= set(paths)
    assert paths["check_engine_diagnostic_screenshot_capture_path"]["world"] == "Build"
    assert paths["chief_terrain_source_note_capture_path"]["world"] == "Operations"
    assert paths["cassandra_draft_review_capture_path"]["world"] == "Communications"
    assert paths["niles_struna_project_reference_capture_path"]["world"] == "Creative"
    assert paths["client_project_delivery_reference_capture_path"]["world"] == "Delivery"
    assert payload["machine_proof"]["app_wide_examples_present"] is True
    for path_id in expected:
        path = paths[path_id]
        assert path["authority_granted"] is False
        assert path["target_storage_policy"]
        assert path["next_safe_move"]


def test_artifact_targets_are_metadata_first_and_raw_body_blocked():
    payload = _build()
    targets = _targets(payload)

    expected_types = set(contract.ARTIFACT_TYPES)
    assert expected_types == {item["artifact_type"] for item in targets.values()}
    for target_id, target in targets.items():
        assert set(contract.REQUIRED_ARTIFACT_TARGET_FIELDS) <= set(target), target_id
        assert target["hash_required"] is True
        assert target["receipt_required"] is True
        assert target["metadata_only_default"] is True
        assert target["raw_body_allowed"] is False
        assert target["operator_final_authority_required"] is True
    protected = targets["protected_screenshot_reference_target"]
    assert protected["artifact_type"] == "SCREENSHOT_PROTECTED_REFERENCE"
    assert protected["protected_reference_required"] is True
    assert protected["guardian_review_required"] is True
    assert "credentials" in protected["blocked_material"]
    assert payload["machine_proof"]["raw_body_capture_blocked"] is True


def test_capture_outcomes_are_targets_only_and_do_not_execute():
    payload = _build()
    outcomes = _outcomes(payload)

    assert payload["guided_capture_outcome_schema"]["models_outcome_targets_only"] is True
    assert payload["guided_capture_outcome_schema"]["executes_outcomes_now"] is False
    assert outcomes["capital_hilton_coupa_po_capture_success_target"]["would_create_artifact"] is True
    assert outcomes["capital_hilton_coupa_po_capture_success_target"]["would_create_receipt"] is True
    assert outcomes["capital_hilton_coupa_po_capture_success_target"]["would_trigger_guardian_review"] is True
    assert outcomes["capital_hilton_coupa_po_capture_success_target"]["would_advance_workflow"] is True
    assert outcomes["capital_hilton_coupa_po_not_available"]["would_create_discovery_substep"] is True
    assert outcomes["coupa_po_automation_candidate_created_target"]["would_create_automation_candidate"] is True
    for outcome_id, outcome in outcomes.items():
        assert set(contract.REQUIRED_CAPTURE_OUTCOME_FIELDS) <= set(outcome), outcome_id
        assert outcome["current_execution_authority"] is False
    assert payload["machine_proof"]["outcome_execution_authority_false"] is True


def test_privacy_guards_block_leakage_and_prefer_targeted_capture():
    payload = _build()
    guards = _guards(payload)

    expected = {
        "full_desktop_screenshot_leakage",
        "browser_tab_leakage",
        "credential_field_leakage",
        "session_cookie_token_leakage",
        "bank_check_remit_leakage",
        "raw_customer_private_data_leakage",
        "unrelated_app_window_leakage",
        "private_directory_path_exposure",
    }
    assert set(guards) == expected
    full_desktop = guards["full_desktop_screenshot_leakage"]
    assert "full desktop" in full_desktop["blocked_capture_scope"]
    assert any("targeted window or region" in scope for scope in full_desktop["allowed_capture_scope"])
    credentials = guards["credential_field_leakage"]
    assert "Credentials must never be captured" in credentials["required_guardrail"]
    assert "password fields" in credentials["blocked_capture_scope"]
    raw_body = guards["raw_customer_private_data_leakage"]
    assert "raw private body" in raw_body["blocked_capture_scope"]
    assert "metadata-only reference" in raw_body["allowed_capture_scope"]
    assert payload["machine_proof"]["targeted_capture_preferred_over_full_desktop"] is True
    assert payload["machine_proof"]["credentials_capture_blocked"] is True


def test_current_capture_file_receipt_workflow_browser_coupa_network_authority_false():
    payload = _build()

    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    assert payload["authority_boundary"]["screenshot_capture_allowed"] is False
    assert payload["authority_boundary"]["file_write_allowed"] is False
    assert payload["authority_boundary"]["file_upload_allowed"] is False
    assert payload["authority_boundary"]["browser_automation_allowed"] is False
    assert payload["authority_boundary"]["coupa_access_allowed"] is False
    assert payload["authority_boundary"]["credential_handling_allowed"] is False
    assert payload["authority_boundary"]["network_operation_allowed"] is False
    assert payload["authority_boundary"]["raw_body_ingestion_allowed"] is False
    assert payload["authority_boundary"]["protected_evidence_write_allowed"] is False
    assert payload["authority_boundary"]["receipt_write_allowed"] is False
    assert payload["authority_boundary"]["workflow_state_write_allowed"] is False
    assert payload["authority_boundary"]["model_call_allowed"] is False
    assert payload["authority_boundary"]["agent_activation_allowed"] is False
    assert payload["authority_boundary"]["tool_execution_allowed"] is False
    assert payload["authority_boundary"]["queue_execution_allowed"] is False
    assert payload["authority_boundary"]["runtime_dispatch_allowed"] is False
    assert payload["machine_proof"]["capture_authority_currently_false"] is True
    assert payload["machine_proof"]["capture_path_authority_false"] is True
    assert payload["machine_proof"]["all_authority_flags_false"] is True
    assert payload["machine_proof"]["action_authority_granted"] is False


def test_future_automation_candidate_is_non_authority():
    payload = _build()

    assert payload["future_non_authority_flags"]["future_supervised_automation_candidate"] is True
    assert payload["future_non_authority_flags"]["future_flags_grant_current_authority"] is False
    assert payload["machine_proof"]["future_automation_candidate_does_not_grant_authority"] is True
    coupa = _paths(payload)["capital_hilton_coupa_po_screen_capture_path"]
    assert coupa["system_future_automation_candidate"] is True
    assert coupa["authority_granted"] is False


def test_prior_lane_refs_are_represented_if_available():
    payload = _build()
    relationships = {item["lane_id"]: item for item in payload["relationship_to_prior_lanes"]}

    expected = {
        "operator_work_mode_schema_bandwidth_policy",
        "operator_solve_path_decision_node_contract",
        "capital_hilton_coupa_po_retrieval_automation_candidate",
        "capital_hilton_protected_reference_placeholder",
        "capital_hilton_guardian_review_packet",
        "capital_hilton_proof_quieting_progress_state",
        "openclaw_work_terrain_gap_detector",
    }
    assert set(relationships) == expected
    assert relationships["operator_work_mode_schema_bandwidth_policy"]["observation_status"] == "OBSERVED"
    assert relationships["operator_solve_path_decision_node_contract"]["observation_status"] == "OBSERVED"
    for relationship in relationships.values():
        assert relationship["read_model_ref"]
        assert "does not duplicate prior content" in relationship["relationship"]
    assert payload["machine_proof"]["prior_lane_ref_count"] == len(expected)


def test_no_credentials_secrets_or_raw_private_bodies_are_included():
    payload = _build()
    text = contract.stable_json(payload)

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


def test_exporter_writes_json_and_eliwinship_operator_markdown(tmp_path):
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
    json_path = tmp_path / "generated" / "read_models" / contract.JSON_EXPORT_NAME
    operator_path = tmp_path / "generated" / "read_models" / contract.OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator = operator_path.read_text(encoding="utf-8")
    assert payload["read_model_id"] == contract.READ_MODEL_ID
    assert payload["machine_proof"]["capture_path_count"] >= 7
    assert payload["machine_proof"]["all_authority_flags_false"] is True
    assert "ELIWINSHIP Summary" in operator
    assert "Guided capture means" in operator
    assert "This prompt does not capture screenshots" in operator
    assert "Prompt 4 should add" in operator


def test_source_has_no_disallowed_runtime_behavior():
    text = Path("guided_capture_protected_evidence_path_contract.py").read_text(encoding="utf-8").lower()
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
