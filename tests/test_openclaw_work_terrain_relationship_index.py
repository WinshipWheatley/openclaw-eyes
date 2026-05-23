import json
from pathlib import Path

import openclaw_work_terrain_relationship_index as contract
from scripts.export_openclaw_work_terrain_relationship_index import main as export_main


FIXED_NOW = "2026-05-23T15:00:00+00:00"


def _build(tmp_path: Path | None = None) -> dict:
    repo_root = tmp_path if tmp_path is not None else Path(".")
    return contract.build_openclaw_work_terrain_relationship_index(
        repo_root=repo_root,
        generated_at=FIXED_NOW,
    )


def test_relationship_record_model_types_statuses_and_artifacts_exist(tmp_path):
    payload = _build(tmp_path)

    assert contract.stable_json(payload) == contract.stable_json(_build(tmp_path))
    assert payload["schema_version"] == contract.SCHEMA_VERSION
    assert payload["read_model_id"] == contract.READ_MODEL_ID
    assert payload["contract_status"] == "metadata_only_relationship_index_contract"
    assert payload["relationship_record_model"]["model_name"] == "WorkTerrainRelationshipRecord"
    assert "relationship_id" in payload["relationship_record_model"]["fields"]
    assert "BUILT_NOT_SURFACED" in payload["relationship_types"]
    assert "SOURCE_NOTE_MATCHES_BUILT_ARTIFACT" in payload["relationship_types"]
    assert "UNKNOWN_FAIL_CLOSED" in payload["relationship_types"]
    assert "RECONCILED_WITH_PROOF" in payload["relationship_statuses"]
    assert "UNKNOWN_FAIL_CLOSED" in payload["relationship_statuses"]
    assert "MARKDOWN_FILE" in payload["entity_artifact_types"]
    assert "GENERATED_OPERATOR_DIGEST" in payload["entity_artifact_types"]
    assert "PROTECTED_REFERENCE" in payload["entity_artifact_types"]
    assert payload["machine_proof"]["relationship_record_model_exists"] is True
    assert payload["machine_proof"]["relationship_types_exist"] is True
    assert payload["machine_proof"]["relationship_statuses_exist"] is True
    assert payload["machine_proof"]["entity_artifact_types_exist"] is True


def test_output_shapes_cover_future_relationship_questions(tmp_path):
    payload = _build(tmp_path)
    shapes = {shape["query_name"]: shape for shape in payload["relationship_query_output_shapes"]["shapes"]}

    assert set(shapes) == set(contract.OUTPUT_SHAPE_NAMES)
    for name in [
        "SourceNotesDescribingBuiltArtifacts",
        "BuiltArtifactsLackingSourceNotes",
        "StableMapSectionsLackingSourceOrigin",
        "MarkdownIdeasWithoutImplementation",
        "GeneratedReadModelsAsProofDetail",
        "DuplicateOrOverlappingConcepts",
        "WorldLaneActorOwnership",
        "ReceiptsSupportingCompletion",
    ]:
        assert name in shapes
        assert "candidate_relationships" in shapes[name]
        assert "missing_relationships" in shapes[name]
        assert shapes[name]["next_safe_move"].startswith("Return candidate relationship")
    assert payload["relationship_query_output_shapes"]["live_query_engine_implemented"] is False
    assert payload["machine_proof"]["output_shapes_exist"] is True


def test_default_examples_include_required_relationships(tmp_path):
    payload = _build(tmp_path)
    examples = {record["relationship_id"]: record for record in payload["default_relationship_examples"]}

    assert set(examples) == {
        "chief_test_harness_source_to_contract",
        "capital_hilton_proof_intake_contract_to_surface",
        "capital_hilton_proof_resolution_backend_links",
        "markdown_knowledge_atlas_built_not_prominently_surfaced",
        "security_pass_contract_to_security_pass_surface",
        "future_invoicing_audit_to_parked_stress_test",
        "repo_b_planner_builder_reference_only",
        "generated_operator_markdown_is_proof_detail",
    }
    assert examples["chief_test_harness_source_to_contract"]["relationship_type"] == "SOURCE_NOTE_MATCHES_BUILT_ARTIFACT"
    assert examples["chief_test_harness_source_to_contract"]["requires_chief_reconciliation"] is True
    assert examples["capital_hilton_proof_resolution_backend_links"]["source_world"] == "Finance"
    assert examples["capital_hilton_proof_resolution_backend_links"]["requires_guardian_review"] is True
    assert examples["capital_hilton_proof_resolution_backend_links"]["authority_granted"] is False
    assert examples["markdown_knowledge_atlas_built_not_prominently_surfaced"]["relationship_type"] == "BUILT_NOT_SURFACED"
    assert examples["markdown_knowledge_atlas_built_not_prominently_surfaced"]["requires_hermes_review"] is True
    assert examples["security_pass_contract_to_security_pass_surface"]["relationship_status"] == "STABLE_MAP_LINKED"
    assert examples["future_invoicing_audit_to_parked_stress_test"]["source_actor"] == "Gemini / Agy"
    assert examples["repo_b_planner_builder_reference_only"]["confidence_posture"] == "REFERENCE_ONLY_METADATA"
    assert examples["generated_operator_markdown_is_proof_detail"]["source_artifact_type"] == "GENERATED_OPERATOR_DIGEST"
    assert examples["generated_operator_markdown_is_proof_detail"]["confidence_posture"] == "PROOF_DETAIL_NOT_HUMAN_DOCTRINE"
    assert payload["machine_proof"]["default_examples_exist"] is True
    assert payload["machine_proof"]["built_not_surfaced_relationship_exists"] is True
    assert payload["machine_proof"]["source_note_built_artifact_relationships_exist"] is True
    assert payload["machine_proof"]["generated_operator_markdown_is_proof_detail_not_doctrine"] is True
    assert payload["machine_proof"]["repo_b_reference_only"] is True


def test_ownership_map_exists_for_common_actors_worlds_and_lanes(tmp_path):
    payload = _build(tmp_path)
    ownership = payload["ownership_map"]
    actors = {item["actor"] for item in ownership["actors"]}
    worlds = {item["world"] for item in ownership["worlds"]}
    lanes = {item["lane_or_concept"] for item in ownership["lanes_and_concepts"]}

    for actor in ["Chief", "Guardian", "Cassandra", "Hermes", "Niles", "Codex", "Gemini / Agy", "Operator / Winship"]:
        assert actor in actors
    for world in ["Finance", "Build", "Security", "Music / Art", "Communications", "Operations", "Research", "Business Development"]:
        assert world in worlds
    for lane in ["Capital Hilton", "Security Pass", "Work Terrain", "Markdown Atlas", "Agent Council", "Package Preview", "Tool Adapter Receipt", "Stable Map", "Mission Control", "Repo B Planner / Builder", "Struna", "Niles Producer lane"]:
        assert lane in lanes
    assert ownership["metadata_only"] is True
    assert ownership["unknowns_fail_closed"] is True
    assert payload["machine_proof"]["ownership_map_exists"] is True


def test_relationship_policy_blocks_body_ingestion_mutation_and_auto_promotion(tmp_path):
    payload = _build(tmp_path)
    policy = payload["work_terrain_relationship_policy"]
    boundary = payload["authority_boundary"]

    assert policy["metadata_only"] is True
    assert policy["body_ingestion_allowed"] is False
    assert policy["relationship_truth_status"] == "candidate_until_receipted"
    assert policy["auto_promotion_allowed"] is False
    assert policy["auto_archive_allowed"] is False
    assert policy["auto_rewrite_allowed"] is False
    assert policy["auto_delete_allowed"] is False
    assert policy["stable_map_update_allowed"] is False
    assert "Chief" in policy["chief_reconciliation_role"]
    assert "Hermes" in policy["hermes_review_role"]
    assert "Operator" in policy["operator_final_authority"]
    assert boundary["all_action_authority_flags_false"] is True
    for key, value in contract.AUTHORITY_BOUNDARY.items():
        assert value is False
        assert boundary[key] is False, key
    assert payload["machine_proof"]["no_action_authority"] is True
    assert payload["machine_proof"]["no_body_ingestion"] is True
    assert payload["machine_proof"]["no_file_mutation"] is True
    assert payload["machine_proof"]["no_auto_stable_map_promotion"] is True


def test_relationship_to_prompt_1_is_reference_only(tmp_path):
    read_models = tmp_path / "generated" / "read_models"
    read_models.mkdir(parents=True)
    (read_models / "openclaw_work_terrain_query_contract.json").write_text("{}", encoding="utf-8")
    (read_models / "openclaw_work_terrain_query_contract_OPERATOR.md").write_text("# prompt 1\n", encoding="utf-8")
    payload = _build(tmp_path)
    linkage = payload["relationship_to_prompt_1"]

    assert linkage["extends"] == "openclaw_work_terrain_query_contract"
    assert linkage["source_read_model_ref"] == "generated/read_models/openclaw_work_terrain_query_contract.json"
    assert linkage["source_operator_ref"] == "generated/read_models/openclaw_work_terrain_query_contract_OPERATOR.md"
    assert linkage["prompt_1_observed"] is True
    assert linkage["does_not_duplicate_prompt_1"] is True


def test_review_fields_exist_on_every_relationship_record(tmp_path):
    payload = _build(tmp_path)

    for record in payload["default_relationship_examples"]:
        assert "requires_chief_reconciliation" in record
        assert "requires_hermes_review" in record
        assert "requires_guardian_review" in record
        assert "operator_review_required" in record
        assert record["authority_granted"] is False
    assert payload["machine_proof"]["chief_hermes_guardian_review_fields_exist"] is True


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
    assert len(payload["default_relationship_examples"]) == 8
    assert "ELIWINSHIP Summary" in operator
    assert "Default Relationship Examples" in operator
    assert "Prompt 3" in operator


def test_source_does_not_contain_broad_scan_mutation_or_runtime_calls():
    text = Path("openclaw_work_terrain_relationship_index.py").read_text(encoding="utf-8").lower()
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
