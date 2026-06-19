import ast
import json
from pathlib import Path

import niles_stage2_deterministic_backend as stage2
from scripts.export_niles_stage2_deterministic_backend import main as export_main


FIXED_NOW = "2026-05-17T12:00:00+00:00"


def _write_json(path: Path, payload: dict | list) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _boundary_root(tmp_path: Path, records: list[dict]) -> Path:
    read_models = tmp_path / "generated" / "read_models"
    _write_json(
        read_models / "niles_album_evidence_intake_boundary.json",
        {
            "schema_version": "niles_album_evidence_intake_boundary_v0",
            "boundary_status": "operator_metadata_recorded_partial_evidence" if records else "contract_ready_no_real_metadata_recorded",
            "recorded_operator_metadata": records,
        },
    )
    return tmp_path


def _metadata_record(**overrides):
    record = {
        "album_project_name": None,
        "song_title": None,
        "song_id_or_stable_operator_label": None,
        "track_status_label": None,
        "production_stage_label": None,
        "source_reference_path_label": None,
        "daw_session_existence_flag": None,
        "last_known_operator_update": None,
        "blocker_labels": [],
        "next_safe_move_labels": [],
        "confidence": None,
        "evidence_status": "operator_supplied_metadata_evidence",
        "operator_supplied": True,
        "no_external_action": True,
        "metadata_only": True,
        "raw_audio_stored": False,
        "daw_session_contents_stored": False,
        "file_opened_or_scanned": False,
        "album_state_confirmed": False,
    }
    record.update(overrides)
    return record


def test_no_records_stays_blocked_and_non_executing(tmp_path):
    repo_root = _boundary_root(tmp_path, [])

    payload = stage2.build_niles_stage2_deterministic_backend(repo_root=repo_root, generated_at=FIXED_NOW)

    assert payload["schema_version"] == stage2.SCHEMA_VERSION
    assert payload["stage2_status"] == "blocked_needs_governed_operator_metadata"
    assert payload["evaluated_record_count"] == 0
    assert payload["review_ready_count"] == 0
    assert payload["authority_boundary"]["runtime_authority_added"] is False
    assert payload["machine_proof"]["weighted_score_performed"] is True
    assert payload["machine_proof"]["runtime_authority_added"] is False


def test_complete_operator_metadata_becomes_review_ready_not_action_ready(tmp_path):
    repo_root = _boundary_root(
        tmp_path,
        [
            _metadata_record(
                album_project_name="SYNTHETIC TEST PROJECT - not real",
                song_title="SYNTHETIC TEST SONG - not real",
                track_status_label="review",
                production_stage_label="mix_notes",
                source_reference_path_label="operator://synthetic/reference-label",
                blocker_labels=["synthetic_missing_reference_mix"],
                next_safe_move_labels=["synthetic_review_metadata_only"],
                confidence="high",
                evidence_status="operator_supplied_metadata_evidence",
            )
        ],
    )

    payload = stage2.build_niles_stage2_deterministic_backend(repo_root=repo_root, generated_at=FIXED_NOW)
    evaluation = payload["evaluations"][0]

    assert payload["stage2_status"] == "ready_for_metadata_only_review"
    assert payload["review_ready_count"] == 1
    assert evaluation["normalized_input"]["input_label"] == "SYNTHETIC TEST SONG - not real"
    assert evaluation["evidence_classification"]["evidence_class"] == "operator_supplied_metadata_evidence"
    assert evaluation["weighted_score"]["score"] >= 70
    assert evaluation["weighted_score"]["score_is_review_readiness_not_taste_or_truth"] is True
    assert evaluation["gates"]["metadata_review_allowed"] is True
    assert evaluation["gates"]["runtime_execution_allowed"] is False
    assert evaluation["gates"]["daw_or_file_action_allowed"] is False
    assert evaluation["gates"]["send_or_submit_allowed"] is False
    assert evaluation["gates"]["approval_granted"] is False


def test_partial_metadata_without_identity_is_blocked_without_inventing_fields(tmp_path):
    repo_root = _boundary_root(
        tmp_path,
        [
            _metadata_record(
                album_project_name="SYNTHETIC TEST PROJECT - not real",
                confidence="medium",
                evidence_status="operator_supplied_unknown_incomplete",
            )
        ],
    )

    payload = stage2.build_niles_stage2_deterministic_backend(repo_root=repo_root, generated_at=FIXED_NOW)
    evaluation = payload["evaluations"][0]

    assert payload["stage2_status"] == "partial_needs_more_operator_metadata"
    assert evaluation["evidence_classification"]["identity_present"] is False
    assert evaluation["evidence_classification"]["unknown_fields_not_treated_as_confirmed"] is True
    assert evaluation["evidence_classification"]["album_state_confirmed"] is False
    assert evaluation["gates"]["gate_status"] == "blocked_missing_song_identity"
    assert evaluation["normalized_input"]["song_title"] is None
    assert evaluation["normalized_input"]["song_id_or_stable_operator_label"] is None


def test_synthetic_test_evidence_is_capped_and_not_review_ready(tmp_path):
    repo_root = _boundary_root(
        tmp_path,
        [
            _metadata_record(
                song_title="SYNTHETIC TEST SONG - not real",
                track_status_label="review",
                production_stage_label="mix_notes",
                confidence="high",
                evidence_status="synthetic_test_only_not_real_evidence",
            )
        ],
    )

    payload = stage2.build_niles_stage2_deterministic_backend(repo_root=repo_root, generated_at=FIXED_NOW)
    evaluation = payload["evaluations"][0]

    assert evaluation["evidence_classification"]["evidence_class"] == "synthetic_test_only_not_real_metadata"
    assert evaluation["weighted_score"]["score"] <= 40
    assert evaluation["gates"]["gate_status"] == "synthetic_review_only_not_real_metadata"
    assert evaluation["gates"]["metadata_review_allowed"] is False


def test_blocked_keys_and_runtime_flags_trigger_hard_block_without_storing_raw_values(tmp_path):
    input_path = _write_json(
        tmp_path / "unsafe.json",
        {
            "song_title": "Unsafe",
            "raw_audio": "raw-body-must-not-be-carried-forward",
            "operator_supplied": True,
            "no_external_action": True,
            "metadata_only": True,
            "runtime_authority_added": True,
        },
    )

    payload = stage2.build_niles_stage2_deterministic_backend(
        metadata_input_json=input_path,
        generated_at=FIXED_NOW,
    )
    evaluation = payload["evaluations"][0]
    serialized = json.dumps(payload)

    assert payload["stage2_status"] == "blocked_hard_flags_present"
    assert evaluation["gates"]["gate_status"] == "blocked_hard_flags_present"
    assert "blocked_input_keys_present" in evaluation["hard_flags"]
    assert "runtime_authority_added_true" in evaluation["hard_flags"]
    assert evaluation["normalized_input"]["blocked_input_keys"] == ["raw_audio"]
    assert "raw-body-must-not-be-carried-forward" not in serialized
    assert evaluation["weighted_score"]["score"] == 0


def test_export_writes_json_operator_and_cli_outputs(tmp_path, capsys):
    repo_root = _boundary_root(tmp_path, [_metadata_record(song_id_or_stable_operator_label="synthetic_song_001", confidence="medium")])
    export_root = "generated/read_models"

    result = stage2.export_niles_stage2_deterministic_backend(
        repo_root=repo_root,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )
    payload = json.loads((repo_root / export_root / stage2.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (repo_root / export_root / stage2.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert result.schema_version == stage2.SCHEMA_VERSION
    assert payload["schema_version"] == stage2.SCHEMA_VERSION
    assert "Niles Stage 2 Deterministic Backend v0" in operator
    assert "Runtime authority added: `false`" in operator
    assert export_main(["--repo-root", str(repo_root), "--export-root", export_root, "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["schema_version"] == stage2.SCHEMA_VERSION


def test_generated_json_is_deterministic(tmp_path):
    repo_root = _boundary_root(
        tmp_path,
        [
            _metadata_record(
                song_id_or_stable_operator_label="synthetic_song_001",
                blocker_labels=["synthetic_blocker"],
                confidence="low",
            )
        ],
    )

    first = stage2.build_niles_stage2_deterministic_backend(repo_root=repo_root, generated_at=FIXED_NOW)
    second = stage2.build_niles_stage2_deterministic_backend(repo_root=repo_root, generated_at=FIXED_NOW)

    assert stage2.stable_json(first) == stage2.stable_json(second)


def test_source_does_not_import_forbidden_execution_or_mutation_apis():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "niles_stage2_deterministic_backend.py",
            "scripts/export_niles_stage2_deterministic_backend.py",
        ]
    )
    forbidden = [
        "subprocess",
        "os.system",
        "shutil.",
        "copy2",
        "rename(",
        "unlink(",
        "remove(",
        "rmtree",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "smtplib",
        "send_message",
        "reply_text",
        "shell=true",
        "eval(",
    ]
    for token in forbidden:
        assert token not in source


def test_source_write_calls_are_limited_to_generated_read_model_exports():
    tree = ast.parse(Path("niles_stage2_deterministic_backend.py").read_text(encoding="utf-8"))
    write_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write_text"
    ]

    assert len(write_calls) == 2
