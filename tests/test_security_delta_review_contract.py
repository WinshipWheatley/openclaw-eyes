import json
import re
from pathlib import Path

import security_delta_review_contract as contract


FIXED_NOW = "2026-05-22T19:00:00+00:00"


def _build() -> dict:
    return contract.build_security_delta_review_contract(generated_at=FIXED_NOW)


def _examples(payload: dict) -> dict:
    return {item["delta_id"]: item for item in payload["default_examples"]}


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == contract.READ_MODEL_ID
    assert first["contract_status"] == "DETERMINISTIC_NON_EXECUTING_SECURITY_DELTA_REVIEW"
    assert first["core_doctrine"]["full_security_pass_establishes_security_law"] is True
    assert first["core_doctrine"]["security_delta_review_checks_new_item_against_that_law"] is True
    assert first["core_doctrine"]["security_delta_review_grants_live_authority"] is False


def test_all_delta_classes_and_decision_outcomes_exist():
    payload = _build()

    assert payload["security_delta_classes"] == list(contract.SECURITY_DELTA_CLASSES)
    assert payload["decision_outcomes"] == list(contract.DECISION_OUTCOMES)
    assert payload["machine_proof"]["all_delta_classes_present"] is True
    assert payload["machine_proof"]["all_decision_outcomes_present"] is True
    for required in [
        "READ_ONLY_DELTA",
        "PREVIEW_SURFACE_DELTA",
        "METADATA_ONLY_DELTA",
        "ACCOUNT_ACCESS_DELTA",
        "QUEUE_AUTONOMY_DELTA",
        "RUNTIME_EXECUTION_DELTA",
        "FINANCIAL_AUTHORITY_DELTA",
        "SECURITY_REPASS_REQUIRED",
        "UNKNOWN_FAIL_CLOSED",
    ]:
        assert required in payload["security_delta_classes"]
    for required in [
        "ALLOWED_READ_ONLY",
        "ALLOWED_PREVIEW_ONLY",
        "ALLOWED_METADATA_ONLY",
        "ALLOWED_CAPTURE_ONLY",
        "REQUIRES_SECURITY_DELTA_REVIEW",
        "REQUIRES_SECURITY_REPASS",
        "BLOCKED_ACCOUNT",
        "BLOCKED_EXECUTION",
        "UNKNOWN_FAIL_CLOSED",
    ]:
        assert required in payload["decision_outcomes"]


def test_required_record_schema_and_default_examples_exist():
    payload = _build()
    examples = _examples(payload)

    assert payload["security_delta_review_record_schema"]["required_fields"] == list(contract.REQUIRED_RECORD_FIELDS)
    assert payload["machine_proof"]["default_example_count"] == 14
    assert set(examples) == {
        "new_read_only_mission_control_card",
        "new_preview_surface_from_stable_map",
        "new_package_preview_type",
        "new_memory_candidate_capture_surface",
        "new_operator_answer_popup",
        "new_markdown_visibility_surface",
        "new_browser_oauth_coupa_adapter",
        "new_gmail_calendar_adapter",
        "new_invoice_generation_or_ledger_write",
        "new_queue_autonomy_lane",
        "new_runtime_agent_activation",
        "external_open_source_dependency_recommendation",
        "new_stable_map_summary_only",
        "new_world_preview_surface",
    }
    for example in examples.values():
        assert set(contract.REQUIRED_RECORD_FIELDS) <= set(example)


def test_read_only_preview_metadata_and_world_deltas_do_not_grant_action_authority():
    examples = _examples(_build())

    for key in [
        "new_read_only_mission_control_card",
        "new_preview_surface_from_stable_map",
        "new_markdown_visibility_surface",
        "new_stable_map_summary_only",
        "new_world_preview_surface",
    ]:
        example = examples[key]
        assert example["authority_change_requested"] is False
        assert example["authority_change_allowed"] is False
        assert "live execution" in example["blocked_actions"]
    assert examples["new_read_only_mission_control_card"]["decision"] == "ALLOWED_READ_ONLY"
    assert examples["new_preview_surface_from_stable_map"]["decision"] == "ALLOWED_PREVIEW_ONLY"
    assert examples["new_markdown_visibility_surface"]["decision"] == "ALLOWED_METADATA_ONLY"
    assert examples["new_world_preview_surface"]["decision"] == "ALLOWED_PREVIEW_ONLY"


def test_account_runtime_queue_and_financial_deltas_require_repass_or_remain_blocked():
    examples = _examples(_build())

    for key in [
        "new_browser_oauth_coupa_adapter",
        "new_gmail_calendar_adapter",
        "new_invoice_generation_or_ledger_write",
        "new_queue_autonomy_lane",
        "new_runtime_agent_activation",
    ]:
        example = examples[key]
        assert example["decision"] == "REQUIRES_SECURITY_REPASS"
        assert example["required_review_type"] == "security_repass"
        assert example["authority_change_requested"] is True
        assert example["authority_change_allowed"] is False
        assert example["guardian_gate_required"] is True
        assert example["operator_approval_required"] is True
    assert "invoice generation" in examples["new_invoice_generation_or_ledger_write"]["blocked_actions"]
    assert "ledger write" in examples["new_invoice_generation_or_ledger_write"]["blocked_actions"]
    assert "unattended execution" in examples["new_queue_autonomy_lane"]["blocked_actions"]
    assert "live agent activation" in examples["new_runtime_agent_activation"]["blocked_actions"]


def test_package_preview_operator_capture_and_memory_candidate_rules():
    examples = _examples(_build())

    assert examples["new_package_preview_type"]["decision"] == "REQUIRES_SECURITY_DELTA_REVIEW"
    assert examples["new_package_preview_type"]["authority_change_allowed"] is False
    assert examples["new_memory_candidate_capture_surface"]["decision"] == "ALLOWED_CAPTURE_ONLY"
    assert "operator answers as proof" in examples["new_memory_candidate_capture_surface"]["blocked_actions"]
    assert examples["new_operator_answer_popup"]["decision"] == "REQUIRES_SECURITY_DELTA_REVIEW"
    assert "proof by statement alone" in examples["new_operator_answer_popup"]["blocked_actions"]


def test_external_dependency_recommendations_are_advisory_only():
    example = _examples(_build())["external_open_source_dependency_recommendation"]

    assert example["change_type"] == "EXTERNAL_DEPENDENCY_DELTA"
    assert example["decision"] == "REQUIRES_HERMES_REVIEW"
    assert example["hermes_review_recommended"] is True
    assert example["operator_approval_required"] is True
    assert example["authority_change_allowed"] is False
    assert "dependency adoption" in example["blocked_actions"]
    assert "license review" in example["future_gated_actions"]


def test_stable_map_summary_delta_does_not_make_stable_map_source_truth():
    payload = _build()
    example = _examples(payload)["new_stable_map_summary_only"]

    assert example["decision"] == "ALLOWED_UNDER_EXISTING_SECURITY_CLASS"
    assert example["stable_map_update_required"] is True
    assert "stable map as source truth" in example["blocked_actions"]
    assert payload["stable_map_rule"]["stable_map_is_source_truth"] is False
    assert payload["stable_map_rule"]["stable_map_auto_promotion_allowed"] is False
    assert payload["machine_proof"]["stable_map_is_source_truth"] is False


def test_no_auto_promotion_execution_or_live_authority():
    payload = _build()

    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    assert payload["machine_proof"]["action_authority_granted"] is False
    assert payload["machine_proof"]["execution_authority_granted"] is False
    assert payload["machine_proof"]["auto_promotion_allowed"] is False
    assert payload["machine_proof"]["auto_queueing_allowed"] is False
    assert "execute changes" in payload["must_not"]
    assert "promote stable-map state automatically" in payload["must_not"]


def test_operator_answers_are_memory_candidates_not_proof():
    payload = _build()

    assert payload["operator_answer_rule"]["operator_answers_become"] == "MEMORY_CANDIDATE_RECEIPT"
    assert payload["operator_answer_rule"]["operator_answers_are_proof"] is False
    assert payload["operator_answer_rule"]["automatic_truth_promotion_allowed"] is False
    assert payload["machine_proof"]["operator_answers_are_not_proof"] is True


def test_no_credentials_or_raw_private_bodies_are_included():
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


def test_export_writes_json_and_operator_markdown(tmp_path):
    result = contract.export_security_delta_review_contract(
        repo_root=tmp_path,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )
    json_path = Path(result.json_path)
    operator_path = Path(result.operator_path)

    assert json_path.exists()
    assert operator_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator_text = operator_path.read_text(encoding="utf-8")
    assert payload["contract_id"] == "security_delta_review_contract_v0"
    assert payload["machine_proof"]["default_example_count"] == 14
    assert payload["machine_proof"]["action_authority_granted"] is False
    assert "ELIWINSHIP Summary" in operator_text
    assert "Security Delta Review" in operator_text
