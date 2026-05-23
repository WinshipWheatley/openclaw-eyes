import json
import re
from pathlib import Path

import operator_work_mode_schema_bandwidth_policy as contract
from scripts.export_operator_work_mode_schema_bandwidth_policy import main as export_main


FIXED_NOW = "2026-05-23T14:00:00+00:00"


def _build() -> dict:
    return contract.build_operator_work_mode_schema_bandwidth_policy(generated_at=FIXED_NOW)


def _bandwidth(payload: dict) -> dict:
    return payload["bandwidth_modes_by_id"]


def _work_modes(payload: dict) -> dict:
    return payload["work_mode_types_by_id"]


def _issues(payload: dict) -> dict:
    return payload["issue_classifications_by_id"]


def _instances(payload: dict) -> dict:
    return payload["work_mode_instances_by_id"]


def test_contract_is_deterministic_and_read_model_only():
    first = _build()
    second = _build()

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == contract.READ_MODEL_ID
    assert first["contract_status"] == contract.CONTRACT_STATUS
    assert first["hard_rule"]["read_model_only"] is True
    assert first["hard_rule"]["does_not_implement_solve_paths_yet"] is True
    assert first["hard_rule"]["does_not_implement_decision_nodes_yet"] is True
    assert first["hard_rule"]["does_not_implement_mac_ui"] is True
    assert first["hard_rule"]["does_not_refresh_stable_map"] is True
    assert first["hard_rule"]["may_execute"] is False
    assert first["hard_rule"]["may_persist_operator_input"] is False
    assert first["hard_rule"]["may_grant_authority"] is False


def test_bandwidth_modes_exist_and_helm_default_is_not_debug_or_high():
    payload = _build()
    modes = _bandwidth(payload)

    assert set(modes) == set(contract.BANDWIDTH_MODE_IDS)
    assert payload["helm_default_bandwidth_mode"] in {"LOW_BANDWIDTH", "NORMAL_BANDWIDTH"}
    assert payload["helm_default_bandwidth_mode"] not in {"HIGH_BANDWIDTH", "DEBUG_MODE"}
    assert modes["LOW_BANDWIDTH"]["default_for_helm"] is True
    assert modes["HIGH_BANDWIDTH"]["default_for_helm"] is False
    assert modes["DEBUG_MODE"]["default_for_helm"] is False
    assert any("one next human move" in item for item in modes["LOW_BANDWIDTH"]["visible_content_policy"])
    assert "contracts" in modes["DEBUG_MODE"]["visible_content_policy"]
    assert payload["machine_proof"]["helm_default_is_low_or_normal"] is True
    assert payload["machine_proof"]["debug_mode_is_not_default"] is True
    assert payload["machine_proof"]["high_bandwidth_is_not_default"] is True


def test_work_mode_types_exist_and_define_human_progress_and_blockers():
    payload = _build()
    work_modes = _work_modes(payload)

    assert set(work_modes) == set(contract.WORK_MODE_TYPE_IDS)
    for work_mode_id, work_mode in work_modes.items():
        assert set(contract.REQUIRED_WORK_MODE_TYPE_FIELDS) <= set(work_mode), work_mode_id
        assert work_mode["human_purpose"]
        assert work_mode["default_hidden_sections"]
        assert work_mode["blocked_actions"]
        assert work_mode["completion_condition"]
        assert work_mode["proof_depth_policy"]
        assert work_mode["progress_condition"]
    assert work_modes["PROOF_WORK_MODE"]["default_bandwidth_mode"] == "LOW_BANDWIDTH"
    assert "mark proof complete" in work_modes["PROOF_WORK_MODE"]["blocked_actions"]
    assert "grant authority" in work_modes["DECISION_WORK_MODE"]["blocked_actions"]
    assert "repair execution" in work_modes["REPAIR_DIAGNOSTIC_WORK_MODE"]["blocked_actions"]
    assert "email send" in work_modes["DRAFT_COMMUNICATION_WORK_MODE"]["blocked_actions"]
    assert "automation execution" in work_modes["AUTOMATION_CANDIDATE_WORK_MODE"]["blocked_actions"]


def test_issue_classifications_exist_for_all_issue_types():
    payload = _build()
    issues = _issues(payload)

    assert set(contract.ISSUE_TYPES) == {item["issue_type"] for item in issues.values()}
    for issue_id, issue in issues.items():
        assert set(contract.REQUIRED_ISSUE_CLASSIFICATION_FIELDS) <= set(issue), issue_id
        assert issue["primary_work_mode"] in contract.WORK_MODE_TYPE_IDS
        assert issue["operator_bandwidth_default"] in contract.BANDWIDTH_MODE_IDS
        assert issue["human_summary_required"] is True
        assert issue["authority_granted"] is False
    assert issues["capital_hilton_invoice_issue"]["issue_type"] == "FINANCE_WORKFLOW"
    assert issues["terrain_reconciliation_issue"]["issue_type"] == "CONCEPT_TERRAIN_RECONCILIATION"
    assert issues["developer_system_repair_issue"]["issue_type"] == "DEVELOPER_SYSTEM_REPAIR"
    assert issues["security_delta_review_issue"]["issue_type"] == "SECURITY_GUARDIAN_REVIEW"
    assert issues["creative_music_project_issue"]["issue_type"] == "CREATIVE_MUSIC_PROJECT"
    assert issues["communication_draft_send_issue"]["issue_type"] == "COMMUNICATION_DRAFT_SEND_WORKFLOW"


def test_app_wide_work_mode_instances_exist_with_required_examples_and_defaults():
    payload = _build()
    instances = _instances(payload)

    expected = {
        "capital_hilton_invoice_work_mode",
        "chief_terrain_reconciliation_work_mode",
        "check_engine_diagnostic_work_mode",
        "security_delta_review_work_mode",
        "niles_struna_project_work_mode",
        "cassandra_clara_draft_work_mode",
    }
    assert set(instances) == expected
    for instance_id, instance in instances.items():
        assert set(contract.REQUIRED_WORK_MODE_INSTANCE_FIELDS) <= set(instance), instance_id
        assert instance["operator_inputs_active"] is False
        assert instance["authority_granted"] is False
        assert instance["current_action_status"] == "LOCKED"
        assert instance["one_next_human_move"]
        assert instance["plain_language_choices"]
        assert instance["blocked_actions"]
        assert instance["hidden_context"]
    assert instances["capital_hilton_invoice_work_mode"]["primary_work_mode_type"] == "PROOF_WORK_MODE"
    assert instances["capital_hilton_invoice_work_mode"]["secondary_work_mode_types"] == (
        "ARTIFACT_WORK_MODE",
        "APPROVAL_WORK_MODE",
        "AUTOMATION_CANDIDATE_WORK_MODE",
    )
    assert instances["capital_hilton_invoice_work_mode"]["one_next_human_move"] == (
        "Pick what is true about the invoice."
    )
    assert instances["chief_terrain_reconciliation_work_mode"]["one_next_human_move"] == (
        "Review what should stay current."
    )
    assert instances["check_engine_diagnostic_work_mode"]["one_next_human_move"] == (
        "Check what is actually broken."
    )
    assert instances["security_delta_review_work_mode"]["one_next_human_move"] == (
        "Decide if this needs security review."
    )
    assert instances["niles_struna_project_work_mode"]["one_next_human_move"] == (
        "Pick up where you left off."
    )
    assert instances["cassandra_clara_draft_work_mode"]["one_next_human_move"] == (
        "Review the draft before anything sends."
    )


def test_human_translation_policy_exists_and_lm_cannot_decide_authority_proof_or_approval():
    payload = _build()
    policy = payload["human_translation_policy"]

    assert policy["translation_source"] == "deterministic_work_mode_packet"
    assert policy["lm_render_allowed"] is True
    assert policy["lm_render_role"] == "plain-language renderer of deterministic solve-path packet only"
    assert policy["lm_can_decide_authority"] is False
    assert policy["lm_can_mark_proof_complete"] is False
    assert policy["lm_can_approve_action"] is False
    assert policy["lm_can_create_hidden_memory"] is False
    assert policy["receipt_required_before_display"] is True
    assert policy["dynamic_hallucinated_buttons_allowed"] is False
    assert payload["machine_proof"]["lm_cannot_decide_authority"] is True
    assert payload["machine_proof"]["lm_cannot_mark_proof_complete"] is True
    assert payload["machine_proof"]["lm_cannot_approve_action"] is True


def test_helm_declutter_policy_hides_machine_contracts_by_default():
    payload = _build()
    policy = payload["helm_declutter_policy"]

    assert "urgent operator decisions" in policy["helm_should_show"]
    assert "blocked workflows needing human action" in policy["helm_should_show"]
    assert "raw machine contracts" in policy["helm_should_hide"]
    assert "generated read-model details" in policy["helm_should_hide"]
    assert policy["proof_should_live"] == "one level down, inspectable, not default visual noise"
    assert policy["machine_contract_visibility"] == "hidden by default; inspectable in high bandwidth or debug"
    assert payload["machine_proof"]["machine_contracts_not_default_app_surface"] is True
    assert payload["machine_proof"]["helm_declutter_policy_present"] is True


def test_stable_map_exposure_policy_splits_app_surface_from_proof_detail():
    payload = _build()
    policy = payload["stable_map_exposure_policy"]

    assert "active workflow sessions" in policy["stable_map_should_expose"]
    assert "current work mode" in policy["stable_map_should_expose"]
    assert "one next human move" in policy["stable_map_should_expose"]
    assert "raw screenshots" in policy["stable_map_should_not_expose"]
    assert "draft email payloads" in policy["stable_map_should_not_expose"]
    assert "full contract internals" in policy["stable_map_should_not_expose"]
    assert "plain choices from deterministic packet" in policy["mac_should_render"]
    assert "machine contract wall" in policy["mac_should_hide"]
    assert payload["machine_proof"]["stable_map_exposure_policy_present"] is True


def test_authority_boundary_all_false_and_operator_inputs_inactive():
    payload = _build()

    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    assert payload["machine_proof"]["all_authority_flags_false"] is True
    assert payload["machine_proof"]["action_authority_granted"] is False
    assert payload["machine_proof"]["operator_inputs_active_default_false"] is True
    assert payload["machine_proof"]["authority_granted_default_false"] is True
    assert payload["authority_boundary"]["workflow_execution_allowed"] is False
    assert payload["authority_boundary"]["operator_input_persistence_allowed"] is False
    assert payload["authority_boundary"]["automation_execution_allowed"] is False
    assert payload["authority_boundary"]["approval_submission_allowed"] is False
    assert payload["authority_boundary"]["invoice_generation_allowed"] is False
    assert payload["authority_boundary"]["email_send_allowed"] is False
    assert payload["authority_boundary"]["telegram_send_allowed"] is False
    assert payload["authority_boundary"]["browser_automation_allowed"] is False
    assert payload["authority_boundary"]["credential_handling_allowed"] is False
    assert payload["authority_boundary"]["live_model_calls_allowed"] is False
    assert payload["authority_boundary"]["model_call_allowed"] is False
    assert payload["authority_boundary"]["agent_activation_allowed"] is False
    assert payload["authority_boundary"]["tool_execution_allowed"] is False
    assert payload["authority_boundary"]["queue_execution_allowed"] is False
    assert payload["authority_boundary"]["runtime_dispatch_allowed"] is False


def test_existing_rail_refs_are_represented_without_duplication():
    payload = _build()
    rails = {item["rail_id"]: item for item in payload["relationship_to_existing_rails"]}

    expected_rails = {
        "capital_hilton_proof_intake_resolution",
        "coupa_po_automation_candidate",
        "work_terrain_reconciliation",
        "security_pass",
        "operator_attention_promotion",
        "chief_test_harness_cross_off",
        "governance_batch",
        "agent_council",
        "package_preview",
        "tool_adapter_receipt",
    }
    assert set(rails) == expected_rails
    for rail in rails.values():
        assert rail["read_model_refs"]
        assert "substrate" in rail["relationship"]
    assert payload["machine_proof"]["relationship_to_existing_rails_count"] == len(expected_rails)


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
    assert payload["machine_proof"]["bandwidth_mode_count"] == 4
    assert payload["machine_proof"]["work_mode_type_count"] == 10
    assert payload["machine_proof"]["work_mode_instance_count"] == 6
    assert "ELIWINSHIP Summary" in operator
    assert "The helm feels overloaded" in operator
    assert "Prompt 2 should add" in operator


def test_source_has_no_disallowed_runtime_behavior():
    text = Path("operator_work_mode_schema_bandwidth_policy.py").read_text(encoding="utf-8").lower()
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
