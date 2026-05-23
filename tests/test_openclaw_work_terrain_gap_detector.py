import json
from pathlib import Path

import openclaw_work_terrain_gap_detector as contract
from scripts.export_openclaw_work_terrain_gap_detector import main as export_main


FIXED_NOW = "2026-05-23T17:00:00+00:00"


def _build(tmp_path: Path | None = None) -> dict:
    repo_root = tmp_path if tmp_path is not None else Path(".")
    return contract.build_openclaw_work_terrain_gap_detector(
        repo_root=repo_root,
        generated_at=FIXED_NOW,
    )


def test_gap_record_model_gap_types_and_priority_buckets_exist(tmp_path):
    payload = _build(tmp_path)

    assert contract.stable_json(payload) == contract.stable_json(_build(tmp_path))
    assert payload["schema_version"] == contract.SCHEMA_VERSION
    assert payload["read_model_id"] == contract.READ_MODEL_ID
    assert payload["contract_status"] == "metadata_only_gap_detector_contract"
    assert payload["gap_record_model"]["model_name"] == "WorkTerrainGapRecord"
    assert "gap_id" in payload["gap_record_model"]["fields"]
    for gap_type in [
        "PARTIALLY_BUILT",
        "BUILT_BUT_UNSAFE",
        "UNSAFE_EXECUTION_POSTURE",
        "CONCEPTUALLY_VALID_BUT_PREMATURE",
        "HISTORICAL_RESIDUE_ONLY",
        "IMPLEMENTATION_EXISTS_BUT_DOCTRINE_STALE",
        "DOCTRINE_EXISTS_BUT_IMPLEMENTATION_SUPERSEDED",
        "TEST_VALIDATION_MISSING",
        "UNKNOWN_FAIL_CLOSED",
    ]:
        assert gap_type in payload["gap_types"]
    for priority in [
        "CRITICAL_SECURITY_GAP",
        "INCOMPLETE_LINEAGE",
        "STABLE_MAP_VISIBILITY_GAP",
        "PARKED_OR_PREMATURE",
        "QUARANTINE_REQUIRED",
        "UNKNOWN_FAIL_CLOSED",
    ]:
        assert priority in payload["gap_priorities"]
    assert payload["machine_proof"]["gap_record_exists"] is True
    assert payload["machine_proof"]["gap_types_exist"] is True
    assert payload["machine_proof"]["gap_priority_buckets_exist"] is True


def test_negative_filters_prevent_old_generated_reference_and_unsafe_activation(tmp_path):
    payload = _build(tmp_path)
    filters = {item["filter_id"]: item for item in payload["negative_filters"]}

    assert set(filters) == {
        "old_prompt_filter",
        "generated_artifact_filter",
        "reference_only_filter",
        "historical_residue_filter",
        "premature_concept_filter",
        "unsafe_execution_filter",
    }
    assert "MARKDOWN_IDEA_HAS_NO_IMPLEMENTATION" in filters["old_prompt_filter"]["blocked_gap_types_after_filter"]
    assert "GENERATED_ARTIFACT_CONFUSED_AS_DOCTRINE" in filters["generated_artifact_filter"]["allowed_gap_types_after_filter"]
    assert "MARKDOWN_IDEA_HAS_NO_IMPLEMENTATION" in filters["reference_only_filter"]["blocked_gap_types_after_filter"]
    assert "CONCEPTUALLY_VALID_BUT_PREMATURE" in filters["premature_concept_filter"]["allowed_gap_types_after_filter"]
    assert "BUILT_BUT_UNSAFE" in filters["unsafe_execution_filter"]["allowed_gap_types_after_filter"]
    assert payload["machine_proof"]["old_prompt_filter_prevents_implementation_gap"] is True
    assert payload["machine_proof"]["generated_artifact_filter_prevents_doctrine_treatment"] is True
    assert payload["machine_proof"]["reference_only_filter_prevents_activation"] is True


def test_built_status_validation_requires_tests_receipts_or_surfaces(tmp_path):
    payload = _build(tmp_path)
    rules = {rule["rule_id"]: rule for rule in payload["built_status_validation_rules"]}

    assert "WorkTerrainBuiltStatusValidationRule" == payload["built_status_validation_rule_model"]["model_name"]
    for status in [
        "NOT_BUILT",
        "PARTIALLY_BUILT",
        "BUILT_UNVALIDATED",
        "BUILT_WITH_TESTS",
        "BUILT_WITH_RECEIPTS",
        "BUILT_AND_SURFACED",
        "BUILT_BUT_UNSAFE",
        "UNKNOWN_FAIL_CLOSED",
    ]:
        assert status in payload["built_statuses"]
    assert rules["file_existence_is_not_built"]["can_claim_built"] is False
    assert "test refs" in rules["file_existence_is_not_built"]["missing_validation"]
    assert rules["validated_by_test_signal"]["built_claim_source"] == "VALIDATED_BY_TEST"
    assert rules["validated_by_test_signal"]["can_claim_built"] is True
    assert rules["built_but_unsafe_requires_quarantine"]["built_status"] == "BUILT_BUT_UNSAFE"
    assert rules["built_but_unsafe_requires_quarantine"]["can_claim_built"] is False
    assert payload["machine_proof"]["built_status_requires_validation"] is True
    assert payload["machine_proof"]["validated_by_test_signal_represented"] is True


def test_default_gap_examples_cover_required_gap_shapes_and_no_action(tmp_path):
    payload = _build(tmp_path)
    examples = {gap["gap_id"]: gap for gap in payload["default_gap_examples"]}

    assert set(examples) == {
        "chief_source_notes_vs_built_contracts_gap",
        "markdown_knowledge_atlas_visibility_gap",
        "capital_hilton_proof_resolution_surface_gap",
        "repo_b_planner_builder_reference_gap",
        "future_invoicing_audit_parked_gap",
        "generated_operator_markdown_truth_gap",
        "stable_map_summary_missing_for_work_terrain",
        "old_prompt_not_implementation_gap",
        "built_artifact_missing_test_receipt_gap",
        "implementation_exists_but_doctrine_stale_gap",
        "doctrine_exists_but_implementation_superseded_gap",
        "built_but_unsafe_execution_gap",
    }
    assert examples["chief_source_notes_vs_built_contracts_gap"]["gap_priority"] == "CHIEF_RECONCILIATION_NEEDED"
    assert examples["markdown_knowledge_atlas_visibility_gap"]["gap_type"] == "STABLE_MAP_REPRESENTATION_MISSING"
    assert examples["capital_hilton_proof_resolution_surface_gap"]["missing_visibility"] == ("Mac UI answer capture surface",)
    assert examples["repo_b_planner_builder_reference_gap"]["negative_filter_applied"] is True
    assert examples["future_invoicing_audit_parked_gap"]["recommended_resolution_type"] == "KEEP_PARKED"
    assert examples["generated_operator_markdown_truth_gap"]["recommended_resolution_type"] == "KEEP_AS_PROOF_DETAIL"
    assert examples["old_prompt_not_implementation_gap"]["gap_type"] == "HISTORICAL_RESIDUE_ONLY"
    assert examples["built_artifact_missing_test_receipt_gap"]["gap_type"] == "TEST_VALIDATION_MISSING"
    assert examples["implementation_exists_but_doctrine_stale_gap"]["gap_type"] == "IMPLEMENTATION_EXISTS_BUT_DOCTRINE_STALE"
    assert examples["doctrine_exists_but_implementation_superseded_gap"]["gap_type"] == "DOCTRINE_EXISTS_BUT_IMPLEMENTATION_SUPERSEDED"
    assert examples["built_but_unsafe_execution_gap"]["gap_priority"] == "CRITICAL_SECURITY_GAP"
    for gap in examples.values():
        assert gap["action_allowed"] is False
    assert payload["machine_proof"]["default_gap_examples_exist"] is True
    assert payload["machine_proof"]["built_but_unsafe_routes_to_security_or_quarantine"] is True
    assert payload["machine_proof"]["no_action_authority"] is True


def test_gap_detector_policy_blocks_mutation_ai_review_and_auto_promotion(tmp_path):
    payload = _build(tmp_path)
    policy = payload["gap_detector_policy"]
    boundary = payload["authority_boundary"]

    assert policy["metadata_only"] is True
    assert policy["body_ingestion_allowed"] is False
    assert policy["semantic_review_allowed"] is False
    assert policy["file_mutation_allowed"] is False
    assert policy["auto_archive_allowed"] is False
    assert policy["auto_consolidation_allowed"] is False
    assert policy["auto_stable_map_promotion_allowed"] is False
    assert policy["auto_implementation_allowed"] is False
    assert policy["negative_filtering_required"] is True
    assert policy["built_status_requires_validation"] is True
    assert policy["operator_attention_dedup_required"] is True
    assert boundary["all_action_authority_flags_false"] is True
    for key, value in contract.AUTHORITY_BOUNDARY.items():
        assert value is False
        assert boundary[key] is False, key
    assert payload["machine_proof"]["auto_archive_consolidation_stable_map_implementation_false"] is True


def test_prior_lane_refs_are_represented_when_available(tmp_path):
    read_models = tmp_path / "generated" / "read_models"
    read_models.mkdir(parents=True)
    (read_models / "openclaw_work_terrain_query_contract.json").write_text("{}", encoding="utf-8")
    (read_models / "openclaw_work_terrain_relationship_index.json").write_text("{}", encoding="utf-8")
    (read_models / "openclaw_work_terrain_classification_candidate.json").write_text("{}", encoding="utf-8")
    payload = _build(tmp_path)
    prior = payload["relationship_to_prior_lanes"]

    assert prior["openclaw_work_terrain_query_contract"]["status"] == "OBSERVED"
    assert prior["openclaw_work_terrain_relationship_index"]["status"] == "OBSERVED"
    assert prior["openclaw_work_terrain_classification_candidate"]["status"] == "OBSERVED"
    assert payload["machine_proof"]["prior_lane_refs_represented"] is True


def test_no_credentials_raw_private_bodies_or_literal_c_drive_paths_are_included(tmp_path):
    payload = _build(tmp_path)
    text = contract.stable_json(payload)

    assert payload["machine_proof"]["credential_or_secret_included"] is False
    assert payload["machine_proof"]["raw_private_body_included"] is False
    assert "/" + "mnt" + "/" + "c" not in text
    assert "c:" + "\\" not in text.lower()
    assert "sk-" not in text
    assert "BEGIN " + "PRIVATE KEY" not in text


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
    json_path = tmp_path / "generated" / "read_models" / contract.JSON_EXPORT_NAME
    operator_path = tmp_path / "generated" / "read_models" / contract.OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator = operator_path.read_text(encoding="utf-8")
    assert payload["read_model_id"] == contract.READ_MODEL_ID
    assert len(payload["default_gap_examples"]) == 12
    assert "ELIWINSHIP Summary" in operator
    assert "Negative Filters" in operator
    assert "Prompt 5" in operator


def test_source_does_not_contain_broad_scan_mutation_runtime_or_network_calls():
    text = Path("openclaw_work_terrain_gap_detector.py").read_text(encoding="utf-8").lower()
    for token in [
        "os.walk",
        ".rglob(",
        ".glob(",
        "subprocess",
        "shell=true",
        "os.system",
        "requests.",
        "shutil.rmtree",
        "shutil.move",
        ".unlink(",
        ".rename(",
        "openai",
    ]:
        assert token not in text
