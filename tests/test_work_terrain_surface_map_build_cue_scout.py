import json
from pathlib import Path

import work_terrain_surface_map_build_cue_scout as contract
from scripts.export_work_terrain_surface_map_build_cue_scout import main as export_main


FIXED_NOW = "2026-05-23T16:00:00+00:00"


def _build(tmp_path: Path | None = None) -> dict:
    repo_root = tmp_path if tmp_path is not None else Path(".")
    return contract.build_work_terrain_surface_map_build_cue_scout(
        repo_root=repo_root,
        generated_at=FIXED_NOW,
    )


def test_surface_terrain_record_model_exists(tmp_path):
    payload = _build(tmp_path)

    assert contract.stable_json(payload) == contract.stable_json(_build(tmp_path))
    assert payload["schema_version"] == contract.SCHEMA_VERSION
    assert payload["read_model_id"] == contract.READ_MODEL_ID
    assert payload["contract_status"] == "metadata_only_surface_map_build_cue_scout_contract"
    assert payload["surface_terrain_record_model"]["model_name"] == "WorkTerrainSurfaceRecord"

    fields = payload["surface_terrain_record_model"]["fields"]
    assert "terrain_record_id" in fields
    assert "title" in fields
    assert "artifact_type" in fields
    assert "implementation_hint" in fields

    assert "CONTRACT_CODE" in payload["surface_terrain_record_model"]["artifact_types"]
    assert "SOURCE_NOTE" in payload["surface_terrain_record_model"]["artifact_types"]
    assert "IMPLEMENTED_CONTRACT" in payload["surface_terrain_record_model"]["implementation_hints"]
    assert "DOCTRINE_ONLY" in payload["surface_terrain_record_model"]["implementation_hints"]

    assert payload["machine_proof"]["surface_terrain_record_model_exists"] is True


def test_surface_cluster_model_exists(tmp_path):
    payload = _build(tmp_path)
    model = payload["surface_cluster_model"]

    assert model["model_name"] == "WorkTerrainSurfaceCluster"
    assert "cluster_id" in model["fields"]
    assert "cluster_type" in model["fields"]
    assert "likely_theme" in model["fields"]
    assert "AGENT_WORKFLOW_CLUSTER" in model["cluster_types"]
    assert "BUILT_NOT_SURFACED_CLUSTER" in model["cluster_types"]
    assert payload["machine_proof"]["surface_cluster_model_exists"] is True


def test_deep_dive_candidate_model_exists(tmp_path):
    payload = _build(tmp_path)
    model = payload["deep_dive_candidate_model"]

    assert model["model_name"] == "WorkTerrainDeepDiveCandidate"
    assert "deep_dive_id" in model["fields"]
    assert "allowed_scope" in model["fields"]
    assert "forbidden_scope" in model["fields"]
    assert payload["machine_proof"]["deep_dive_candidate_model_exists"] is True


def test_build_cue_scout_recommendation_model_exists(tmp_path):
    payload = _build(tmp_path)
    model = payload["build_cue_scout_recommendation_model"]

    assert model["model_name"] == "WorkTerrainBuildCueScoutRecommendation"
    assert "scout_recommendation_id" in model["fields"]
    assert "candidate_kind" in model["fields"]
    assert "ready_for_build_cue_queue" in model["fields"]
    assert "BUILD_CUE_READY" in model["candidate_kinds"]
    assert "DEEP_DIVE_FIRST" in model["candidate_kinds"]
    assert payload["machine_proof"]["build_cue_scout_recommendation_model_exists"] is True


def test_default_records_and_clusters_exist(tmp_path):
    payload = _build(tmp_path)
    records = {r["terrain_record_id"]: r for r in payload["default_records"]}
    clusters = {c["cluster_id"]: c for c in payload["default_clusters"]}

    assert set(records) == {
        "workflow_block_intent_contract",
        "operator_question_assist_note",
        "capital_hilton_protected_proof_intake_contract",
        "starship_operating_model_contract",
        "screenshot_harness_accessibility_harness",
    }

    assert set(clusters) == {
        "workflow_packet_cluster",
        "operator_question_assist_cluster",
        "capital_hilton_cluster",
        "starship_operating_model_cluster",
        "screenshot_harness_cluster",
    }

    assert payload["machine_proof"]["workflow_packet_cluster_represented"] is True
    assert payload["machine_proof"]["operator_question_assist_cluster_represented"] is True
    assert payload["machine_proof"]["capital_hilton_cluster_represented"] is True
    assert payload["machine_proof"]["starship_operating_model_cluster_represented"] is True
    assert payload["machine_proof"]["screenshot_harness_cluster_represented"] is True


def test_deep_dives_and_recommendations_exist(tmp_path):
    payload = _build(tmp_path)
    dives = {d["deep_dive_id"]: d for d in payload["default_deep_dives"]}
    recs = {rec["scout_recommendation_id"]: rec for rec in payload["default_scout_recommendations"]}

    assert set(dives) == {"operator_question_assist_dive"}
    assert set(recs) == {
        "rec_packet_compiler_relationship",
        "rec_operator_question_assist",
        "rec_capital_hilton_capture_rail",
        "rec_starship_operating_model",
        "rec_screenshot_harness",
    }


def test_shallow_first_doctrine_represented(tmp_path):
    payload = _build(tmp_path)
    doctrine = payload["core_doctrine"]

    assert doctrine["surface_map_broadly"] is True
    assert doctrine["deep_dive_selectively"] is True
    assert doctrine["body_not_ingested_by_default"] is True
    assert payload["machine_proof"]["shallow_first_doctrine_represented"] is True


def test_body_not_ingested_by_default(tmp_path):
    payload = _build(tmp_path)
    for record in payload["default_records"]:
        assert record["body_not_ingested"] is True


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
