import json
from pathlib import Path

import openclaw_work_terrain_reconciliation_batch_manifest as manifest
from scripts.export_openclaw_work_terrain_reconciliation_batch_manifest import main as export_main


FIXED_NOW = "2026-05-23T14:10:00+00:00"


def _build() -> dict:
    return manifest.build_openclaw_work_terrain_reconciliation_batch_manifest(generated_at=FIXED_NOW)


def test_manifest_is_deterministic_and_complete_pending_stable_map_import():
    payload = _build()

    assert manifest.stable_json(payload) == manifest.stable_json(_build())
    assert payload["schema_version"] == manifest.SCHEMA_VERSION
    assert payload["read_model_id"] == manifest.READ_MODEL_ID
    assert payload["batch_id"] == "openclaw_work_terrain_reconciliation_v0"
    assert payload["batch_status"] == "COMPLETE_PENDING_STABLE_MAP_IMPORT"
    assert payload["stable_map_refresh_deferred"] is False
    assert payload["commit_deferred_until_final_prompt"] is False
    assert payload["current_prompt_index"] == 5
    assert payload["total_prompts"] == 5
    assert payload["machine_proof"]["batch_id_is_expected"] is True
    assert payload["machine_proof"]["status_is_complete_pending_stable_map_import"] is True
    assert payload["next_expected_actor"] == "mac_map_import_agent"


def test_planned_lanes_and_prompt_1_2_3_and_4_completion_are_recorded():
    payload = _build()

    assert payload["planned_lanes"] == list(manifest.PLANNED_LANES)
    assert payload["lanes_planned"] == list(manifest.PLANNED_LANES)
    assert len(payload["planned_lanes"]) == 5
    assert payload["lanes_completed"] == [
        "work_terrain_query_contract",
        "work_terrain_relationship_index",
        "work_terrain_classification_staleness_candidate",
        "work_terrain_gap_detector",
    ]
    assert payload["machine_proof"]["planned_lane_count"] == 5
    assert payload["machine_proof"]["prompt_1_marked_complete"] is True
    assert payload["machine_proof"]["prompt_2_marked_complete"] is True
    assert payload["machine_proof"]["prompt_3_marked_complete"] is True
    assert payload["machine_proof"]["prompt_4_marked_complete"] is True
    assert payload["machine_proof"]["all_four_contract_lanes_complete"] is True
    lane_status = {lane["lane_id"]: lane["lane_status"] for lane in payload["lanes"]}
    assert lane_status["work_terrain_query_contract"] == "COMPLETED"
    assert lane_status["work_terrain_relationship_index"] == "COMPLETED"
    assert lane_status["work_terrain_classification_staleness_candidate"] == "COMPLETED"
    assert lane_status["work_terrain_gap_detector"] == "COMPLETED"
    assert lane_status["integrated_checkpoint_and_stable_map_refresh"] == "PLANNED_NOT_STARTED"


def test_changed_files_and_validation_commands_include_prompt_1_2_3_and_4_outputs():
    payload = _build()

    for path in [
        ".gitignore",
        "openclaw_work_terrain_query_contract.py",
        "scripts/export_openclaw_work_terrain_query_contract.py",
        "tests/test_openclaw_work_terrain_query_contract.py",
        "generated/read_models/openclaw_work_terrain_query_contract.json",
        "generated/read_models/openclaw_work_terrain_query_contract_OPERATOR.md",
        "openclaw_work_terrain_relationship_index.py",
        "scripts/export_openclaw_work_terrain_relationship_index.py",
        "tests/test_openclaw_work_terrain_relationship_index.py",
        "generated/read_models/openclaw_work_terrain_relationship_index.json",
        "generated/read_models/openclaw_work_terrain_relationship_index_OPERATOR.md",
        "openclaw_work_terrain_classification_candidate.py",
        "scripts/export_openclaw_work_terrain_classification_candidate.py",
        "tests/test_openclaw_work_terrain_classification_candidate.py",
        "generated/read_models/openclaw_work_terrain_classification_candidate.json",
        "generated/read_models/openclaw_work_terrain_classification_candidate_OPERATOR.md",
        "openclaw_work_terrain_gap_detector.py",
        "scripts/export_openclaw_work_terrain_gap_detector.py",
        "tests/test_openclaw_work_terrain_gap_detector.py",
        "generated/read_models/openclaw_work_terrain_gap_detector.json",
        "generated/read_models/openclaw_work_terrain_gap_detector_OPERATOR.md",
        "openclaw_work_terrain_reconciliation_batch_manifest.py",
        "scripts/export_openclaw_work_terrain_reconciliation_batch_manifest.py",
        "tests/test_openclaw_work_terrain_reconciliation_batch_manifest.py",
        "generated/read_models/openclaw_work_terrain_reconciliation_batch_manifest.json",
        "generated/read_models/openclaw_work_terrain_reconciliation_batch_manifest_OPERATOR.md",
    ]:
        assert path in payload["changed_files"]
    assert (
        "python3 scripts/export_openclaw_work_terrain_query_contract.py --format summary"
        in payload["validation_commands"]
    )
    assert (
        "python3 scripts/export_openclaw_work_terrain_reconciliation_batch_manifest.py --format summary"
        in payload["validation_commands"]
    )
    assert (
        "python3 scripts/export_openclaw_work_terrain_relationship_index.py --format summary"
        in payload["validation_commands"]
    )
    assert (
        "python3 -m pytest tests/test_openclaw_work_terrain_relationship_index.py tests/test_openclaw_work_terrain_reconciliation_batch_manifest.py -q"
        in payload["validation_commands"]
    )
    assert (
        "python3 scripts/export_openclaw_work_terrain_classification_candidate.py --format summary"
        in payload["validation_commands"]
    )
    assert (
        "python3 -m pytest tests/test_openclaw_work_terrain_classification_candidate.py tests/test_openclaw_work_terrain_reconciliation_batch_manifest.py -q"
        in payload["validation_commands"]
    )
    assert (
        "python3 scripts/export_openclaw_work_terrain_gap_detector.py --format summary"
        in payload["validation_commands"]
    )
    assert (
        "python3 -m pytest tests/test_openclaw_work_terrain_gap_detector.py tests/test_openclaw_work_terrain_reconciliation_batch_manifest.py -q"
        in payload["validation_commands"]
    )


def test_authority_boundary_denies_commit_staging_stable_map_and_live_action():
    payload = _build()
    boundary = payload["authority_boundary"]

    assert boundary["all_authority_flags_false"] is True
    for key, value in manifest.AUTHORITY_BOUNDARY.items():
        assert value is False
        assert boundary[key] is False, key
    assert payload["batch_commit_policy"]["commit_allowed_now"] is True
    assert payload["batch_commit_policy"]["stage_only_work_terrain_reconciliation_files"] is True
    assert payload["stable_map_refresh_policy"]["stable_map_refresh_allowed_now"] is True
    assert payload["machine_proof"]["next_expected_actor_is_mac_map_import_agent"] is True


def test_next_prompt_points_to_mac_map_import_agent():
    payload = _build()

    assert payload["next_expected_actor"] == "mac_map_import_agent"
    assert "Mac map import/sync agent" in payload["next_prompt"]


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
    json_path = tmp_path / "generated" / "read_models" / manifest.JSON_EXPORT_NAME
    operator_path = tmp_path / "generated" / "read_models" / manifest.OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator = operator_path.read_text(encoding="utf-8")
    assert payload["batch_id"] == "openclaw_work_terrain_reconciliation_v0"
    assert payload["lanes_completed"] == [
        "work_terrain_query_contract",
        "work_terrain_relationship_index",
        "work_terrain_classification_staleness_candidate",
        "work_terrain_gap_detector",
    ]
    assert "ELIWINSHIP Summary" in operator
    assert "mac_map_import_agent" in operator


def test_source_has_no_disallowed_runtime_or_mutation_behavior():
    text = Path("openclaw_work_terrain_reconciliation_batch_manifest.py").read_text(encoding="utf-8").lower()
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
