import json
from pathlib import Path

import openclaw_work_terrain_classification_candidate as contract
from scripts.export_openclaw_work_terrain_classification_candidate import main as export_main


FIXED_NOW = "2026-05-23T16:00:00+00:00"


def _build(tmp_path: Path | None = None) -> dict:
    repo_root = tmp_path if tmp_path is not None else Path(".")
    return contract.build_openclaw_work_terrain_classification_candidate(
        repo_root=repo_root,
        generated_at=FIXED_NOW,
    )


def test_classification_candidate_model_and_vocab_exist(tmp_path):
    payload = _build(tmp_path)

    assert contract.stable_json(payload) == contract.stable_json(_build(tmp_path))
    assert payload["schema_version"] == contract.SCHEMA_VERSION
    assert payload["read_model_id"] == contract.READ_MODEL_ID
    assert payload["contract_status"] == "metadata_only_classification_candidate_contract"
    assert payload["classification_candidate_model"]["model_name"] == "WorkTerrainClassificationCandidate"
    assert "candidate_id" in payload["classification_candidate_model"]["fields"]
    for classification in [
        "CURRENT_CANONICAL",
        "CURRENT_SUPPORTING",
        "OLD_PROMPT",
        "STALE_SUPERSEDED",
        "GENERATED_ARTIFACT",
        "REFERENCE_ONLY",
        "CONSOLIDATION_CANDIDATE",
        "ARCHIVE_CANDIDATE",
        "QUARANTINE_CANDIDATE",
        "UNKNOWN_FAIL_CLOSED",
    ]:
        assert classification in payload["candidate_classifications"]
    assert payload["machine_proof"]["classification_candidate_model_exists"] is True
    assert payload["machine_proof"]["classifications_exist"] is True


def test_required_classification_rules_exist_and_block_forbidden_inferences(tmp_path):
    payload = _build(tmp_path)
    rules = {rule["rule_id"]: rule for rule in payload["classification_rules"]}

    assert set(rules) == {
        "generated_read_models_are_not_doctrine",
        "old_prompts_are_not_current_truth",
        "built_artifacts_need_source_lineage",
        "source_notes_need_built_artifact_check",
        "markdown_doctrine_needs_receipts",
        "repo_b_is_reference_only",
        "screenshots_are_validation_evidence",
        "handoffs_are_orientation_not_final_truth",
        "unknown_sensitive_private_fails_closed",
        "stable_map_is_app_facing_reflection",
    }
    assert rules["generated_read_models_are_not_doctrine"]["candidate_classification"] == "GENERATED_ARTIFACT"
    assert "source truth" in rules["generated_read_models_are_not_doctrine"]["forbidden_inference"]
    assert rules["old_prompts_are_not_current_truth"]["candidate_classification"] == "OLD_PROMPT"
    assert "current truth" in rules["old_prompts_are_not_current_truth"]["forbidden_inference"]
    assert rules["repo_b_is_reference_only"]["candidate_classification"] == "REFERENCE_ONLY"
    assert rules["unknown_sensitive_private_fails_closed"]["candidate_classification"] == "QUARANTINE_CANDIDATE"
    assert payload["machine_proof"]["rules_exist"] is True
    assert payload["machine_proof"]["generated_artifacts_not_source_truth"] is True
    assert payload["machine_proof"]["old_prompts_not_truth_by_default"] is True


def test_default_classification_examples_cover_current_stale_reference_generated_and_gaps(tmp_path):
    payload = _build(tmp_path)
    examples = {item["candidate_id"]: item for item in payload["default_classification_examples"]}

    assert set(examples) == {
        "security_pass_contract_current_canonical",
        "capital_hilton_proof_intake_current_supporting",
        "capital_hilton_proof_resolution_batch_current_supporting",
        "old_invoicing_automation_prompt_archive_candidate",
        "markdown_knowledge_atlas_built_not_surfaced",
        "repo_b_planner_builder_reference_only",
        "generated_operator_markdown_generated_artifact",
        "duplicated_chief_concepts_overlap",
        "source_note_matches_security_pass_surface",
        "built_artifact_lacks_source_note_example",
    }
    assert examples["security_pass_contract_current_canonical"]["candidate_classification"] == "CURRENT_CANONICAL"
    assert examples["capital_hilton_proof_intake_current_supporting"]["candidate_classification"] == "CURRENT_SUPPORTING"
    assert examples["capital_hilton_proof_resolution_batch_current_supporting"]["candidate_classification"] == "CURRENT_SUPPORTING"
    assert examples["old_invoicing_automation_prompt_archive_candidate"]["candidate_classification"] == "ARCHIVE_CANDIDATE"
    assert examples["old_invoicing_automation_prompt_archive_candidate"]["archive_action_allowed"] is False
    assert examples["markdown_knowledge_atlas_built_not_surfaced"]["candidate_classification"] == "BUILT_NOT_SURFACED"
    assert examples["repo_b_planner_builder_reference_only"]["candidate_classification"] == "REFERENCE_ONLY"
    assert examples["generated_operator_markdown_generated_artifact"]["candidate_classification"] == "GENERATED_ARTIFACT"
    assert examples["generated_operator_markdown_generated_artifact"]["confidence_posture"] == "PROOF_DETAIL_NOT_SOURCE_TRUTH"
    assert examples["duplicated_chief_concepts_overlap"]["candidate_classification"] == "OVERLAPPING_CONCEPT"
    assert examples["source_note_matches_security_pass_surface"]["candidate_classification"] == "SOURCE_NOTE_MATCHES_BUILT_ARTIFACT"
    assert examples["built_artifact_lacks_source_note_example"]["candidate_classification"] == "BUILT_ARTIFACT_LACKS_SOURCE_NOTE"
    assert payload["machine_proof"]["examples_exist"] is True
    assert payload["machine_proof"]["repo_b_reference_only"] is True


def test_all_classification_examples_deny_archive_delete_rewrite_and_authority(tmp_path):
    payload = _build(tmp_path)

    for example in payload["default_classification_examples"]:
        assert example["archive_action_allowed"] is False
        assert example["rewrite_action_allowed"] is False
        assert example["delete_action_allowed"] is False
        assert example["authority_granted"] is False
    assert payload["machine_proof"]["archive_delete_rewrite_false"] is True
    assert payload["machine_proof"]["no_action_authority"] is True


def test_consolidation_candidates_are_review_only(tmp_path):
    payload = _build(tmp_path)
    model = payload["consolidation_candidate_model"]
    examples = {item["consolidation_id"]: item for item in model["examples"]}

    assert model["model_name"] == "WorkTerrainConsolidationCandidate"
    assert model["rules"]["rewrite_allowed"] is False
    assert model["rules"]["archive_old_fragments_allowed"] is False
    assert model["rules"]["delete_old_fragments_allowed"] is False
    assert model["rules"]["receipt_required_before_action"] is True
    assert set(examples) == {
        "chief_concepts_consolidation_candidate",
        "invoice_automation_prompts_consolidation_candidate",
        "mission_control_design_doctrine_consolidation_candidate",
    }
    for item in examples.values():
        assert item["requires_hermes_review"] is True
        assert item["requires_chief_reconciliation"] is True
        assert item["requires_operator_approval"] is True
        assert item["rewrite_allowed"] is False
        assert item["archive_old_fragments_allowed"] is False
        assert item["delete_old_fragments_allowed"] is False
        assert item["receipt_required_before_action"] is True
    assert payload["machine_proof"]["consolidation_candidate_exists"] is True


def test_supersession_candidates_keep_old_refs_traceable_without_archive_or_delete(tmp_path):
    payload = _build(tmp_path)
    model = payload["supersession_candidate_model"]
    examples = {item["supersession_id"]: item for item in model["examples"]}

    assert model["model_name"] == "WorkTerrainSupersessionCandidate"
    assert model["rules"]["archive_action_allowed"] is False
    assert model["rules"]["delete_action_allowed"] is False
    assert model["rules"]["receipt_required"] is True
    assert model["rules"]["old_refs_remain_traceable"] is True
    assert set(examples) == {
        "security_pass_prompt_to_contract_supersession_candidate",
        "capital_hilton_old_invoice_prompt_to_proof_intake_candidate",
    }
    for item in examples.values():
        assert item["receipt_required"] is True
        assert item["operator_approval_required"] is True
        assert item["archive_action_allowed"] is False
        assert item["delete_action_allowed"] is False
    assert payload["machine_proof"]["supersession_candidate_exists"] is True


def test_future_ai_judgment_policy_exists_and_blocks_ai_action_now(tmp_path):
    payload = _build(tmp_path)
    policy = payload["future_ai_judgment_policy"]

    assert "compare selected safe excerpts" in policy["allowed_later_after_metadata_and_relationship_classification"]
    assert "recommend source-card promotion" in policy["allowed_later_after_metadata_and_relationship_classification"]
    assert "broad body summarization" in policy["blocked_now"]
    assert "moving/deleting/rewriting files" in policy["blocked_now"]
    assert "AI deciding final doctrine without Hermes/Chief/Operator review" in policy["blocked_now"]
    assert policy["broad_ai_semantic_review_allowed_now"] is False
    assert policy["final_doctrine_decision_by_ai_allowed"] is False
    assert policy["operator_final_authority_required"] is True
    assert payload["machine_proof"]["future_ai_judgment_policy_exists"] is True
    assert payload["machine_proof"]["ai_judgment_blocked_now"] is True


def test_prior_lane_refs_are_represented_when_available(tmp_path):
    read_models = tmp_path / "generated" / "read_models"
    read_models.mkdir(parents=True)
    (read_models / "openclaw_work_terrain_query_contract.json").write_text("{}", encoding="utf-8")
    (read_models / "openclaw_work_terrain_relationship_index.json").write_text("{}", encoding="utf-8")
    payload = _build(tmp_path)
    prior = payload["relationship_to_prior_lanes"]

    assert prior["openclaw_work_terrain_query_contract"]["read_model_ref"] == "generated/read_models/openclaw_work_terrain_query_contract.json"
    assert prior["openclaw_work_terrain_query_contract"]["status"] == "OBSERVED"
    assert prior["openclaw_work_terrain_relationship_index"]["read_model_ref"] == "generated/read_models/openclaw_work_terrain_relationship_index.json"
    assert prior["openclaw_work_terrain_relationship_index"]["status"] == "OBSERVED"
    assert payload["machine_proof"]["prior_lane_refs_represented"] is True


def test_authority_boundary_blocks_runtime_network_file_mutation_and_stable_map(tmp_path):
    payload = _build(tmp_path)
    boundary = payload["authority_boundary"]

    assert boundary["all_action_authority_flags_false"] is True
    for key, value in contract.AUTHORITY_BOUNDARY.items():
        assert value is False
        assert boundary[key] is False, key
    assert boundary["stable_map_refresh_allowed"] is False
    assert boundary["broad_ai_semantic_review_allowed"] is False
    assert boundary["file_archive_allowed"] is False


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
    assert len(payload["default_classification_examples"]) == 10
    assert "ELIWINSHIP Summary" in operator
    assert "Consolidation / Supersession Boundary" in operator
    assert "Prompt 4" in operator


def test_source_does_not_contain_broad_scan_mutation_runtime_or_network_calls():
    text = Path("openclaw_work_terrain_classification_candidate.py").read_text(encoding="utf-8").lower()
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
