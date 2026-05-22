import json
from pathlib import Path

import post_security_governance_batch_manifest as manifest


FIXED_NOW = "2026-05-22T18:00:00+00:00"


def _build() -> dict:
    return manifest.build_post_security_governance_batch_manifest(generated_at=FIXED_NOW)


def test_batch_manifest_is_deterministic_and_in_progress_not_committed():
    first = _build()
    second = _build()

    assert manifest.stable_json(first) == manifest.stable_json(second)
    assert first["schema_version"] == manifest.SCHEMA_VERSION
    assert first["read_model_id"] == manifest.READ_MODEL_ID
    assert first["batch_id"] == "post_security_governance_batch_v0"
    assert first["batch_status"] == "COMPLETE_PENDING_STABLE_MAP_IMPORT"
    assert first["current_prompt_index"] == 5
    assert first["total_prompts"] == 5
    assert first["machine_proof"]["batch_id_expected"] is True
    assert first["machine_proof"]["batch_status_expected"] is True


def test_commit_staging_and_stable_map_refresh_are_enabled_only_for_prompt_5_closure():
    payload = _build()

    assert payload["commit_deferred_until_prompt_5"] is False
    assert payload["stable_map_refresh_deferred"] is False
    assert payload["staging_deferred_until_prompt_5"] is False
    assert payload["batch_commit_policy"]["commit_now_allowed"] is True
    assert payload["batch_commit_policy"]["stage_now_allowed"] is True
    assert payload["stable_map_refresh_policy"]["refresh_now_allowed"] is True
    assert payload["stable_map_refresh_policy"]["refresh_prompt_index"] == 5
    assert payload["stable_map_refresh_policy"]["mac_import_now_allowed"] is False
    assert payload["stable_map_refresh_policy"]["next_expected_actor"] == "mac_map_import_agent"
    assert payload["machine_proof"]["stable_map_refresh_required"] is True
    assert payload["machine_proof"]["mac_import_performed"] is False


def test_planned_lanes_count_and_all_batch_lanes_completed():
    payload = _build()
    lanes = {lane["lane_id"]: lane for lane in payload["lanes_planned"]}

    assert len(payload["lanes_planned"]) == 5
    assert payload["machine_proof"]["planned_lane_count"] == 5
    assert set(lanes) == set(manifest.LANES_PLANNED)
    assert lanes["parked_autonomous_capital_pipeline_experiment"]["prompt_index"] == 1
    assert lanes["parked_autonomous_capital_pipeline_experiment"]["lane_status"] == "COMPLETED_PROMPT_1"
    assert lanes["security_delta_review_contract"]["prompt_index"] == 2
    assert lanes["security_delta_review_contract"]["lane_status"] == "COMPLETED_PROMPT_2"
    assert lanes["operator_attention_promotion_contract"]["prompt_index"] == 3
    assert lanes["operator_attention_promotion_contract"]["lane_status"] == "COMPLETED_PROMPT_3"
    assert lanes["chief_test_harness_cross_off_receipt_contract"]["prompt_index"] == 4
    assert lanes["chief_test_harness_cross_off_receipt_contract"]["lane_status"] == "COMPLETED_PROMPT_4"
    assert lanes["integrated_checkpoint_and_stable_map_refresh"]["prompt_index"] == 5
    assert lanes["integrated_checkpoint_and_stable_map_refresh"]["lane_status"] == "COMPLETED_PROMPT_5_PENDING_MAC_IMPORT"
    assert payload["lanes_completed"][0]["lane_id"] == "parked_autonomous_capital_pipeline_experiment"
    assert payload["lanes_completed"][1]["lane_id"] == "security_delta_review_contract"
    assert payload["lanes_completed"][2]["lane_id"] == "operator_attention_promotion_contract"
    assert payload["lanes_completed"][3]["lane_id"] == "chief_test_harness_cross_off_receipt_contract"
    assert payload["lanes_completed"][4]["lane_id"] == "integrated_checkpoint_and_stable_map_refresh"
    assert payload["machine_proof"]["prompt_1_lane_marked_complete"] is True
    assert payload["machine_proof"]["prompt_1_observed"] is True
    assert payload["machine_proof"]["prompt_2_lane_marked_complete"] is True
    assert payload["machine_proof"]["prompt_2_observed"] is True
    assert payload["machine_proof"]["prompt_3_lane_marked_complete"] is True
    assert payload["machine_proof"]["prompt_3_observed"] is True
    assert payload["machine_proof"]["prompt_4_lane_marked_complete"] is True
    assert payload["machine_proof"]["prompt_4_observed"] is True
    assert payload["machine_proof"]["prompt_5_lane_marked_complete_pending_mac_import"] is True


def test_authority_boundary_denies_live_action_and_external_work():
    payload = _build()

    assert set(payload["authority_boundary"]) == set(manifest.BATCH_AUTHORITY_BOUNDARY)
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    assert payload["machine_proof"]["authority_boundary_all_false"] is True
    assert payload["machine_proof"]["live_authority_created"] is False
    assert payload["authority_boundary"]["model_api_execution_allowed"] is False
    assert payload["authority_boundary"]["actor_agent_activation_allowed"] is False
    assert payload["authority_boundary"]["tool_execution_allowed"] is False
    assert payload["authority_boundary"]["financial_payment_account_access_allowed"] is False
    assert payload["authority_boundary"]["mac_sync_import_allowed"] is False
    assert payload["authority_boundary"]["network_operation_allowed"] is False
    assert payload["authority_boundary"]["git_push_pull_fetch_allowed"] is False


def test_next_expected_actor_is_mac_map_import_agent():
    payload = _build()

    assert payload["next_prompt"]["prompt_index"] is None
    assert payload["next_prompt"]["lane_id"] == "mac_map_import_agent"
    assert payload["next_expected_actor"] == "mac_map_import_agent"
    assert payload["machine_proof"]["next_expected_actor_is_mac_map_import_agent"] is True


def test_changed_files_and_validation_commands_cover_prompt_1_outputs():
    payload = _build()

    for expected in [
        "parked_autonomous_capital_pipeline_experiment.py",
        "post_security_governance_batch_manifest.py",
        "scripts/export_post_security_governance_batch_manifest.py",
        "tests/test_post_security_governance_batch_manifest.py",
        "generated/read_models/post_security_governance_batch_manifest.json",
        "generated/read_models/post_security_governance_batch_manifest_OPERATOR.md",
        "security_delta_review_contract.py",
        "scripts/export_security_delta_review_contract.py",
        "tests/test_security_delta_review_contract.py",
        "generated/read_models/security_delta_review_contract.json",
        "generated/read_models/security_delta_review_contract_OPERATOR.md",
        "operator_attention_promotion_contract.py",
        "scripts/export_operator_attention_promotion_contract.py",
        "tests/test_operator_attention_promotion_contract.py",
        "generated/read_models/operator_attention_promotion_contract.json",
        "generated/read_models/operator_attention_promotion_contract_OPERATOR.md",
        "chief_test_harness_cross_off_receipt_contract.py",
        "scripts/export_chief_test_harness_cross_off_receipt_contract.py",
        "tests/test_chief_test_harness_cross_off_receipt_contract.py",
        "generated/read_models/chief_test_harness_cross_off_receipt_contract.json",
        "generated/read_models/chief_test_harness_cross_off_receipt_contract_OPERATOR.md",
        "operator_map_bundle_contract.py",
        "tests/test_operator_map_bundle_contract.py",
        "generated/read_models/openclaw_map_snapshot.json",
        "generated/read_models/openclaw_map_manifest.json",
        "generated/read_models/openclaw_map_OPERATOR.md",
    ]:
        assert expected in payload["changed_files"]
    assert "python3 scripts/export_post_security_governance_batch_manifest.py --format summary" in payload["validation_commands"]
    assert "python3 scripts/export_security_delta_review_contract.py --format summary" in payload["validation_commands"]
    assert "python3 scripts/export_operator_attention_promotion_contract.py --format summary" in payload["validation_commands"]
    assert "python3 scripts/export_chief_test_harness_cross_off_receipt_contract.py --format summary" in payload["validation_commands"]
    assert "python3 scripts/export_operator_map_bundle.py --format summary" in payload["validation_commands"]
    assert "git diff --check" in payload["validation_commands"]


def test_export_writes_json_and_operator_markdown(tmp_path):
    result = manifest.export_post_security_governance_batch_manifest(
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
    assert payload["batch_id"] == "post_security_governance_batch_v0"
    assert payload["batch_status"] == "COMPLETE_PENDING_STABLE_MAP_IMPORT"
    assert payload["current_prompt_index"] == 5
    assert payload["machine_proof"]["authority_boundary_all_false"] is True
    assert payload["machine_proof"]["prompt_2_lane_marked_complete"] is True
    assert payload["machine_proof"]["prompt_3_lane_marked_complete"] is True
    assert payload["machine_proof"]["prompt_4_lane_marked_complete"] is True
    assert payload["machine_proof"]["prompt_5_lane_marked_complete_pending_mac_import"] is True
    assert payload["next_expected_actor"] == "mac_map_import_agent"
    assert "ELIWINSHIP Summary" in operator_text
    assert "leaves actual Mac import to `mac_map_import_agent`" in operator_text
