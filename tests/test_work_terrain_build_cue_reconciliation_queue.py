import json
from pathlib import Path

import work_terrain_build_cue_reconciliation_queue as contract
from scripts.export_work_terrain_build_cue_reconciliation_queue import main as export_main


FIXED_NOW = "2026-05-23T16:00:00+00:00"


def _build(tmp_path: Path | None = None) -> dict:
    repo_root = tmp_path if tmp_path is not None else Path(".")
    return contract.build_work_terrain_build_cue_reconciliation_queue(
        repo_root=repo_root,
        generated_at=FIXED_NOW,
    )


def test_build_cue_candidate_model_exists(tmp_path):
    payload = _build(tmp_path)

    assert contract.stable_json(payload) == contract.stable_json(_build(tmp_path))
    assert payload["schema_version"] == contract.SCHEMA_VERSION
    assert payload["read_model_id"] == contract.READ_MODEL_ID
    assert payload["contract_status"] == "metadata_only_build_cue_reconciliation_queue_contract"
    assert payload["build_cue_candidate_model"]["model_name"] == "WorkTerrainBuildCueCandidate"

    fields = payload["build_cue_candidate_model"]["fields"]
    assert "build_cue_id" in fields
    assert "title" in fields
    assert "source_idea_refs" in fields
    assert "candidate_type" in fields
    assert "implementation_status" in fields

    assert "DOCTRINE_ONLY_BUILD_CANDIDATE" in payload["build_cue_candidate_model"]["candidate_types"]
    assert "PARTLY_BUILT_COMPLETION_CANDIDATE" in payload["build_cue_candidate_model"]["candidate_types"]
    assert "DOCTRINE_ONLY" in payload["build_cue_candidate_model"]["implementation_statuses"]
    assert "PARTLY_BUILT" in payload["build_cue_candidate_model"]["implementation_statuses"]

    assert payload["machine_proof"]["build_cue_candidate_model_exists"] is True


def test_build_cue_queue_model_exists(tmp_path):
    payload = _build(tmp_path)
    model = payload["build_cue_queue_model"]

    assert model["model_name"] == "WorkTerrainBuildCueQueue"
    assert "queue_id" in model["fields"]
    assert "priority_order" in model["fields"]
    assert payload["machine_proof"]["build_cue_queue_model_exists"] is True


def test_priority_assessment_model_exists(tmp_path):
    payload = _build(tmp_path)
    model = payload["priority_assessment_model"]

    assert model["model_name"] == "WorkTerrainBuildCuePriorityAssessment"
    assert "recommended_priority" in model["fields"]
    assert "BUILD_NOW" in model["recommended_priorities"]
    assert "BUILD_NEXT" in model["recommended_priorities"]
    assert payload["machine_proof"]["priority_assessment_model_exists"] is True


def test_default_cue_candidates_exist(tmp_path):
    payload = _build(tmp_path)
    candidates = {c["build_cue_id"]: c for c in payload["default_candidates"]}

    assert set(candidates) == {
        "packet_compiler_relationship_cue",
        "operator_question_assist_cue",
        "capital_hilton_capture_rail_cue",
        "starship_operating_model_cue",
        "screenshot_harness_accessibility_cue",
    }
    assert candidates["packet_compiler_relationship_cue"]["candidate_type"] == "RELATIONSHIP_NEEDS_ENCODING"
    assert candidates["operator_question_assist_cue"]["candidate_type"] == "DOCTRINE_ONLY_BUILD_CANDIDATE"
    assert candidates["capital_hilton_capture_rail_cue"]["candidate_type"] == "PARTLY_BUILT_COMPLETION_CANDIDATE"
    assert candidates["starship_operating_model_cue"]["candidate_type"] == "BUILT_MISSING_STABLE_MAP_CANDIDATE"
    assert candidates["screenshot_harness_accessibility_cue"]["candidate_type"] == "PARKED_REVISIT_CANDIDATE"

    assert payload["machine_proof"]["packet_compiler_relationship_cue_represented"] is True
    assert payload["machine_proof"]["operator_question_assist_cue_represented"] is True
    assert payload["machine_proof"]["capital_hilton_capture_rail_cue_represented"] is True
    assert payload["machine_proof"]["starship_operating_model_cue_represented"] is True
    assert payload["machine_proof"]["screenshot_harness_accessibility_cue_represented"] is True


def test_relationship_to_prior_lanes_represented(tmp_path):
    read_models = tmp_path / "generated" / "read_models"
    read_models.mkdir(parents=True)
    (read_models / "openclaw_work_terrain_query_contract.json").write_text("{}", encoding="utf-8")
    (read_models / "openclaw_work_terrain_relationship_index.json").write_text("{}", encoding="utf-8")
    (read_models / "openclaw_work_terrain_classification_candidate.json").write_text("{}", encoding="utf-8")
    (read_models / "openclaw_work_terrain_gap_detector.json").write_text("{}", encoding="utf-8")

    payload = _build(tmp_path)
    prior = payload["relationship_to_prior_lanes"]

    assert prior["openclaw_work_terrain_query_contract"]["status"] == "OBSERVED"
    assert prior["openclaw_work_terrain_relationship_index"]["status"] == "OBSERVED"
    assert prior["openclaw_work_terrain_classification_candidate"]["status"] == "OBSERVED"
    assert prior["openclaw_work_terrain_gap_detector"]["status"] == "OBSERVED"


def test_all_authority_flags_false(tmp_path):
    payload = _build(tmp_path)
    boundary = payload["authority_boundary"]

    assert boundary["all_authority_flags_false"] is True
    for key, value in contract.AUTHORITY_BOUNDARY.items():
        assert boundary[key] is False
    assert payload["machine_proof"]["safety_boundaries_all_false"] is True


def test_priorities_evaluation_and_unsafe_gating(tmp_path):
    payload = _build(tmp_path)
    priorities = {p["build_cue_ref"]: p for p in payload["default_priorities"]}

    # Stale/unsafe candidates are not BUILD_NOW
    assert priorities["operator_question_assist_cue"]["recommended_priority"] == "REVIEW_WITH_HERMES"
    assert priorities["screenshot_harness_accessibility_cue"]["recommended_priority"] == "PARK_FOR_LATER"

    # Valid candidates can be BUILD_NOW
    assert priorities["packet_compiler_relationship_cue"]["recommended_priority"] == "BUILD_NOW"
    assert priorities["starship_operating_model_cue"]["recommended_priority"] == "BUILD_NOW"
