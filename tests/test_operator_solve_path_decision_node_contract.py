import json
import re
from pathlib import Path

import operator_solve_path_decision_node_contract as contract
from scripts.export_operator_solve_path_decision_node_contract import main as export_main


FIXED_NOW = "2026-05-23T15:00:00+00:00"


def _build() -> dict:
    return contract.build_operator_solve_path_decision_node_contract(generated_at=FIXED_NOW)


def _paths(payload: dict) -> dict:
    return payload["solve_paths_by_id"]


def _nodes(payload: dict) -> dict:
    return payload["decision_nodes_by_id"]


def _choices(payload: dict) -> dict:
    return payload["decision_choices_by_id"]


def _targets(payload: dict) -> dict:
    return payload["receipt_targets_by_id"]


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == contract.READ_MODEL_ID
    assert first["contract_status"] == contract.CONTRACT_STATUS
    assert first["hard_rule"]["read_model_only"] is True
    assert first["hard_rule"]["does_not_implement_live_ui"] is True
    assert first["hard_rule"]["does_not_implement_persistence"] is True
    assert first["hard_rule"]["does_not_write_actual_answers"] is True
    assert first["hard_rule"]["does_not_create_mac_buttons"] is True
    assert first["hard_rule"]["does_not_refresh_stable_map"] is True
    assert first["hard_rule"]["may_write_receipts_now"] is False
    assert first["hard_rule"]["may_execute"] is False
    assert first["hard_rule"]["may_grant_authority"] is False


def test_models_and_required_fields_exist():
    payload = _build()

    assert payload["machine_proof"]["solve_path_model_present"] is True
    assert payload["machine_proof"]["decision_node_model_present"] is True
    assert payload["machine_proof"]["decision_choice_model_present"] is True
    assert payload["machine_proof"]["receipt_target_model_present"] is True
    assert payload["operator_solve_path_schema"]["required_fields"] == list(contract.REQUIRED_SOLVE_PATH_FIELDS)
    assert payload["operator_decision_node_schema"]["required_fields"] == list(contract.REQUIRED_DECISION_NODE_FIELDS)
    assert payload["operator_decision_choice_schema"]["required_fields"] == list(contract.REQUIRED_DECISION_CHOICE_FIELDS)
    assert payload["operator_choice_receipt_target_schema"]["required_fields"] == list(
        contract.REQUIRED_RECEIPT_TARGET_FIELDS
    )
    assert set(payload["decision_node_statuses"]) == set(contract.DECISION_NODE_STATUSES)
    assert set(payload["choice_types"]) == set(contract.CHOICE_TYPES)
    assert set(payload["receipt_types"]) == set(contract.RECEIPT_TYPES)


def test_relationship_to_prompt_1_is_referenced_not_duplicated():
    payload = _build()
    relation = payload["relationship_to_prompt_1"]

    assert relation["extends_read_model_id"] == "operator_work_mode_schema_bandwidth_policy"
    assert relation["read_model_ref"] == "generated/read_models/operator_work_mode_schema_bandwidth_policy.json"
    assert relation["operator_markdown_ref"] == (
        "generated/read_models/operator_work_mode_schema_bandwidth_policy_OPERATOR.md"
    )
    assert relation["does_not_duplicate_prompt_1"] is True


def test_capital_hilton_solve_path_and_confirm_dates_node_exist():
    payload = _build()
    paths = _paths(payload)
    nodes = _nodes(payload)

    assert "capital_hilton_invoice_solve_path" in paths
    capital = paths["capital_hilton_invoice_solve_path"]
    assert set(contract.REQUIRED_SOLVE_PATH_FIELDS) <= set(capital)
    assert capital["low_bandwidth_move"] == "Pick what is true about the invoice."
    assert capital["normal_bandwidth_explanation"] == (
        "OpenClaw has candidate invoice facts. Your choices tell the system what to treat as "
        "operator-confirmed, what needs proof, and what should happen next."
    )
    assert capital["operator_bandwidth_default"] == "LOW_BANDWIDTH"
    assert capital["current_decision_node_id"] == "confirm_performance_dates"
    assert capital["debug_detail_refs"]
    assert "confirm_performance_dates" in nodes
    node = nodes["confirm_performance_dates"]
    assert node["plain_language_prompt"] == (
        "OpenClaw thinks these were the Capital Hilton performance dates. What is true?"
    )
    assert node["what_system_thinks"] == ("May 8, 2026", "May 15, 2026")
    assert node["current_status"] == "ACTIVE"
    assert node["canonical_receipt_target"] == "capital_hilton_performance_dates_confirmation_target"
    assert payload["machine_proof"]["capital_hilton_example_present"] is True
    assert payload["machine_proof"]["confirm_performance_dates_node_present"] is True


def test_capital_hilton_choices_include_required_branches_and_effects():
    payload = _build()
    choices = _choices(payload)

    for choice_id in [
        "both_dates_are_right",
        "one_date_is_wrong",
        "add_another_date",
        "i_dont_know_dates",
        "needs_discovery_dates",
        "date_set_is_wrong",
    ]:
        assert choice_id in choices
        assert set(contract.REQUIRED_DECISION_CHOICE_FIELDS) <= set(choices[choice_id])

    assert choices["both_dates_are_right"]["label"] == "Both are right"
    assert choices["both_dates_are_right"]["choice_type"] == "CONFIRM_TRUE"
    assert choices["both_dates_are_right"]["authority_granted"] is False
    assert choices["both_dates_are_right"]["workflow_state_effect"] == "moves workflow to confirm_rate"
    assert "not externally proven" in choices["both_dates_are_right"]["proof_effect"]

    assert choices["one_date_is_wrong"]["label"] == "One is wrong"
    assert choices["one_date_is_wrong"]["requires_followup"] is True
    assert choices["one_date_is_wrong"]["followup_node_id"] == "correct_performance_date"

    assert choices["add_another_date"]["label"] == "Add another date"
    assert choices["add_another_date"]["requires_followup"] is True
    assert choices["add_another_date"]["followup_node_id"] == "add_performance_date"

    assert choices["i_dont_know_dates"]["label"] == "I don't know"
    assert choices["i_dont_know_dates"]["choice_type"] == "I_DONT_KNOW"
    assert choices["i_dont_know_dates"]["creates_discovery_substep"] is True
    assert "keeps workflow alive" in choices["i_dont_know_dates"]["workflow_state_effect"]

    assert choices["needs_discovery_dates"]["label"] == "Needs discovery"
    assert choices["needs_discovery_dates"]["creates_discovery_substep"] is True
    assert "no action authority" in choices["needs_discovery_dates"]["workflow_state_effect"]

    assert choices["date_set_is_wrong"]["label"] == "This date set is wrong"
    assert choices["date_set_is_wrong"]["requires_followup"] is True
    assert choices["date_set_is_wrong"]["followup_node_id"] == "date_discovery_needed"


def test_followup_nodes_exist_for_corrections_additions_and_discovery():
    nodes = _nodes(_build())

    assert "correct_performance_date" in nodes
    assert "add_performance_date" in nodes
    assert "date_discovery_needed" in nodes
    assert nodes["correct_performance_date"]["optional_freeform_allowed"] is True
    assert nodes["add_performance_date"]["optional_freeform_allowed"] is True
    assert nodes["date_discovery_needed"]["optional_freeform_allowed"] is True
    assert nodes["correct_performance_date"]["current_status"] == "NOT_STARTED"
    assert nodes["add_performance_date"]["current_status"] == "NOT_STARTED"
    assert nodes["date_discovery_needed"]["current_status"] == "NOT_STARTED"


def test_receipt_targets_are_modeled_but_not_written_and_write_authority_is_false():
    payload = _build()
    targets = _targets(payload)

    assert payload["operator_choice_receipt_target_schema"]["models_receipt_targets_only"] is True
    assert payload["operator_choice_receipt_target_schema"]["writes_receipts_now"] is False
    assert "capital_hilton_performance_dates_confirmation_target" in targets
    confirmation = targets["capital_hilton_performance_dates_confirmation_target"]
    assert confirmation["receipt_type"] == "OPERATOR_CONFIRMATION_RECEIPT"
    assert confirmation["requires_sqlite_writer"] is True
    assert confirmation["current_write_authority_granted"] is False
    assert confirmation["would_quiet_step"] is True
    assert "without proving external truth" in confirmation["state_change_summary"]
    assert targets["capital_hilton_date_discovery_substep_target"]["would_create_discovery_substep"] is True
    assert targets["coupa_po_automation_candidate_choice_target"]["would_create_automation_candidate"] is True
    for target in targets.values():
        assert set(contract.REQUIRED_RECEIPT_TARGET_FIELDS) <= set(target)
        assert target["current_write_authority_granted"] is False
    assert payload["machine_proof"]["receipt_targets_modeled_not_written"] is True
    assert payload["machine_proof"]["current_write_authority_false"] is True


def test_app_wide_solve_path_examples_exist_with_bandwidth_rendering():
    payload = _build()
    paths = _paths(payload)

    expected = {
        "capital_hilton_invoice_solve_path": "Pick what is true about the invoice.",
        "check_engine_diagnostic_solve_path": "Check what is actually broken.",
        "chief_terrain_reconciliation_solve_path": "Pick what should stay current.",
        "security_delta_solve_path": "Decide if this needs security review.",
        "coupa_po_automation_candidate_solve_path": "Choose manual capture now or build the automation path.",
    }
    assert set(paths) == set(expected)
    for path_id, low_move in expected.items():
        path = paths[path_id]
        assert path["low_bandwidth_move"] == low_move
        assert path["normal_bandwidth_explanation"]
        assert path["high_bandwidth_proof_refs"]
        assert path["debug_detail_refs"]
        assert ".json" not in path["low_bandwidth_move"]
        assert "generated/" not in path["low_bandwidth_move"]
    assert payload["machine_proof"]["low_bandwidth_moves_present"] is True
    assert payload["machine_proof"]["machine_contracts_not_default_surface"] is True


def test_lm_boundary_prevents_choice_authority_proof_approval_and_blocker_hiding():
    payload = _build()
    boundary = payload["lm_rendering_boundary"]

    assert boundary["lm_may_rephrase"] is True
    assert boundary["lm_may_generate_plain_language"] is True
    assert boundary["lm_may_create_new_choices"] is False
    assert boundary["lm_may_decide_authority"] is False
    assert boundary["lm_may_mark_proof_complete"] is False
    assert boundary["lm_may_approve_action"] is False
    assert boundary["lm_may_hide_blockers"] is False
    assert boundary["deterministic_choice_source_required"] is True
    assert payload["machine_proof"]["lm_cannot_create_choices"] is True
    assert payload["machine_proof"]["lm_cannot_decide_authority"] is True
    assert payload["machine_proof"]["lm_cannot_mark_proof_complete"] is True
    assert payload["machine_proof"]["lm_cannot_approve_action"] is True
    assert payload["machine_proof"]["lm_cannot_hide_blockers"] is True


def test_no_live_authority_credentials_or_raw_private_bodies():
    payload = _build()
    text = contract.stable_json(payload)

    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    assert payload["machine_proof"]["all_authority_flags_false"] is True
    assert payload["machine_proof"]["action_authority_granted"] is False
    assert payload["machine_proof"]["credentials_or_secrets_included"] is False
    assert payload["machine_proof"]["raw_private_bodies_included"] is False
    assert payload["authority_boundary"]["operator_input_persistence_allowed"] is False
    assert payload["authority_boundary"]["sqlite_answer_write_allowed"] is False
    assert payload["authority_boundary"]["receipt_write_allowed"] is False
    assert payload["authority_boundary"]["workflow_execution_allowed"] is False
    assert payload["authority_boundary"]["model_call_allowed"] is False
    assert payload["authority_boundary"]["agent_activation_allowed"] is False
    assert payload["authority_boundary"]["tool_execution_allowed"] is False
    assert payload["authority_boundary"]["queue_execution_allowed"] is False
    assert payload["authority_boundary"]["runtime_dispatch_allowed"] is False
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
    assert payload["machine_proof"]["solve_path_count"] == 5
    assert payload["machine_proof"]["receipt_targets_modeled_not_written"] is True
    assert "ELIWINSHIP Summary" in operator
    assert "A solve path is the plain-language route" in operator
    assert "I don't know is not a dead end" in operator


def test_source_has_no_disallowed_runtime_behavior():
    text = Path("operator_solve_path_decision_node_contract.py").read_text(encoding="utf-8").lower()
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
