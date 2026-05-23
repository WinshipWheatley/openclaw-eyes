import json
from pathlib import Path

import capital_hilton_proof_resolution_batch_manifest as manifest
from scripts.export_capital_hilton_proof_resolution_batch_manifest import main as export_main


FIXED_NOW = "2026-05-23T13:30:00+00:00"


def _build() -> dict:
    return manifest.build_capital_hilton_proof_resolution_batch_manifest(generated_at=FIXED_NOW)


def test_manifest_is_deterministic_and_complete_pending_stable_map_import():
    first = _build()
    second = _build()

    assert manifest.stable_json(first) == manifest.stable_json(second)
    assert first["schema_version"] == manifest.SCHEMA_VERSION
    assert first["read_model_id"] == manifest.READ_MODEL_ID
    assert first["batch_id"] == "capital_hilton_proof_resolution_batch_v0"
    assert first["batch_status"] == "COMPLETE_PENDING_STABLE_MAP_IMPORT"
    assert first["stable_map_refresh_deferred"] is False
    assert first["commit_deferred_until_final_prompt"] is False
    assert first["current_prompt_index"] == 5
    assert first["total_prompts"] == 5
    assert first["machine_proof"]["batch_id_is_expected"] is True
    assert first["machine_proof"]["status_is_complete_pending_stable_map_import"] is True
    assert first["next_expected_actor"] == "mac_map_import_agent"


def test_planned_lanes_and_all_contract_lanes_are_recorded_complete():
    payload = _build()

    assert payload["lanes_planned"] == list(manifest.LANES_PLANNED)
    assert len(payload["lanes_planned"]) == 5
    assert payload["lanes_completed"] == [
        "capital_hilton_answer_candidate_receipt",
        "capital_hilton_protected_reference_placeholder",
        "capital_hilton_guardian_review_packet",
        "capital_hilton_proof_quieting_progress_state",
    ]
    assert payload["machine_proof"]["planned_lane_count"] == 5
    assert payload["machine_proof"]["prompt_1_marked_complete"] is True
    assert payload["machine_proof"]["prompt_2_marked_complete"] is True
    assert payload["machine_proof"]["prompt_3_marked_complete"] is True
    assert payload["machine_proof"]["prompt_4_marked_complete"] is True
    assert payload["machine_proof"]["all_four_contract_lanes_complete"] is True
    lane_status = {lane["lane_id"]: lane["lane_status"] for lane in payload["lanes"]}
    assert lane_status["capital_hilton_answer_candidate_receipt"] == "COMPLETED"
    assert lane_status["capital_hilton_protected_reference_placeholder"] == "COMPLETED"
    assert lane_status["capital_hilton_guardian_review_packet"] == "COMPLETED"
    assert lane_status["capital_hilton_proof_quieting_progress_state"] == "COMPLETED"
    assert lane_status["integrated_checkpoint_and_stable_map_refresh"] == "PLANNED_NOT_STARTED"


def test_changed_files_and_validation_commands_include_prompt_1_2_3_and_4_outputs():
    payload = _build()

    for path in [
        "capital_hilton_answer_candidate_receipt.py",
        "scripts/export_capital_hilton_answer_candidate_receipt.py",
        "tests/test_capital_hilton_answer_candidate_receipt.py",
        "generated/read_models/capital_hilton_answer_candidate_receipt.json",
        "generated/read_models/capital_hilton_answer_candidate_receipt_OPERATOR.md",
        "capital_hilton_protected_reference_placeholder.py",
        "scripts/export_capital_hilton_protected_reference_placeholder.py",
        "tests/test_capital_hilton_protected_reference_placeholder.py",
        "generated/read_models/capital_hilton_protected_reference_placeholder.json",
        "generated/read_models/capital_hilton_protected_reference_placeholder_OPERATOR.md",
        "capital_hilton_guardian_review_packet.py",
        "scripts/export_capital_hilton_guardian_review_packet.py",
        "tests/test_capital_hilton_guardian_review_packet.py",
        "generated/read_models/capital_hilton_guardian_review_packet.json",
        "generated/read_models/capital_hilton_guardian_review_packet_OPERATOR.md",
        "capital_hilton_proof_quieting_progress_state.py",
        "scripts/export_capital_hilton_proof_quieting_progress_state.py",
        "tests/test_capital_hilton_proof_quieting_progress_state.py",
        "generated/read_models/capital_hilton_proof_quieting_progress_state.json",
        "generated/read_models/capital_hilton_proof_quieting_progress_state_OPERATOR.md",
        "capital_hilton_proof_resolution_batch_manifest.py",
        "scripts/export_capital_hilton_proof_resolution_batch_manifest.py",
        "tests/test_capital_hilton_proof_resolution_batch_manifest.py",
    ]:
        assert path in payload["changed_files"]
    assert (
        "python3 scripts/export_capital_hilton_answer_candidate_receipt.py --format summary"
        in payload["validation_commands"]
    )
    assert (
        "python3 -m pytest tests/test_capital_hilton_answer_candidate_receipt.py tests/test_capital_hilton_proof_resolution_batch_manifest.py -q"
        in payload["validation_commands"]
    )
    assert (
        "python3 scripts/export_capital_hilton_protected_reference_placeholder.py --format summary"
        in payload["validation_commands"]
    )
    assert (
        "python3 -m pytest tests/test_capital_hilton_protected_reference_placeholder.py tests/test_capital_hilton_proof_resolution_batch_manifest.py -q"
        in payload["validation_commands"]
    )
    assert (
        "python3 scripts/export_capital_hilton_guardian_review_packet.py --format summary"
        in payload["validation_commands"]
    )
    assert (
        "python3 -m pytest tests/test_capital_hilton_guardian_review_packet.py tests/test_capital_hilton_proof_resolution_batch_manifest.py -q"
        in payload["validation_commands"]
    )
    assert (
        "python3 scripts/export_capital_hilton_proof_quieting_progress_state.py --format summary"
        in payload["validation_commands"]
    )
    assert (
        "python3 -m pytest tests/test_capital_hilton_proof_quieting_progress_state.py tests/test_capital_hilton_proof_resolution_batch_manifest.py -q"
        in payload["validation_commands"]
    )


def test_authority_boundary_denies_live_action_and_stable_map_commit_now():
    payload = _build()
    boundary = payload["authority_boundary"]

    assert boundary["all_authority_flags_false"] is True
    for key, value in manifest.AUTHORITY_BOUNDARY.items():
        assert boundary[key] is False, key
    assert payload["batch_commit_policy"]["commit_allowed_now"] is True
    assert payload["batch_commit_policy"]["stage_only_capital_hilton_proof_resolution_files"] is True
    assert payload["stable_map_refresh_policy"]["stable_map_refresh_allowed_now"] is True
    assert payload["stable_map_refresh_policy"]["final_prompt_handles_single_stable_map_refresh"] is True
    assert payload["machine_proof"]["no_live_execution_or_external_authority"] is True


def test_next_prompt_points_to_integrated_checkpoint_and_stable_map_refresh():
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
    assert payload["batch_id"] == "capital_hilton_proof_resolution_batch_v0"
    assert payload["lanes_completed"] == [
        "capital_hilton_answer_candidate_receipt",
        "capital_hilton_protected_reference_placeholder",
        "capital_hilton_guardian_review_packet",
        "capital_hilton_proof_quieting_progress_state",
    ]
    assert "ELIWINSHIP Summary" in operator
    assert "mac_map_import_agent" in operator


def test_source_has_no_disallowed_runtime_behavior():
    text = Path("capital_hilton_proof_resolution_batch_manifest.py").read_text(encoding="utf-8").lower()
    for token in [
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
