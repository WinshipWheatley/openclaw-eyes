import ast
import json
from pathlib import Path

import niles_album_matrix_review as matrix
from scripts.export_niles_album_matrix_review import main as export_main


FIXED_NOW = "2026-05-17T12:00:00+00:00"


def _write_boundary(tmp_path: Path, records: list[dict]) -> Path:
    read_models = tmp_path / "generated" / "read_models"
    read_models.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "niles_album_evidence_intake_boundary_v0",
        "boundary_status": "operator_metadata_recorded_partial_evidence" if records else "contract_ready_no_real_metadata_recorded",
        "real_album_metadata_recorded": bool(records),
        "unknown_album_state_remains_unknown": True,
        "operator_metadata_intake_status": {
            "real_album_metadata_recorded": bool(records),
            "metadata_record_count": len(records),
            "partial_metadata_intake_supported": True,
            "unknown_album_state_not_treated_as_confirmed": True,
            "album_state_confirmed": False,
        },
        "recorded_operator_metadata": records,
    }
    path = read_models / "niles_album_evidence_intake_boundary.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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


def test_no_metadata_keeps_matrix_blocked_and_empty(tmp_path):
    repo_root = _write_boundary(tmp_path, [])

    payload = matrix.build_niles_album_matrix_review(repo_root=repo_root, generated_at=FIXED_NOW)

    assert payload["schema_version"] == matrix.SCHEMA_VERSION
    assert payload["matrix_status"] == "blocked_needs_governed_album_metadata"
    assert payload["metadata_consumed"] is False
    assert payload["real_album_metadata_recorded"] is False
    assert payload["metadata_record_count"] == 0
    assert payload["rows"] == []
    assert "Provide governed operator metadata" in payload["next_safe_move"]
    assert payload["authority_boundary"]["raw_audio_ingest_allowed"] is False
    assert payload["authority_boundary"]["runtime_authority_added"] is False


def test_one_metadata_record_creates_one_matrix_row(tmp_path):
    repo_root = _write_boundary(
        tmp_path,
        [
            _metadata_record(
                album_project_name="SYNTHETIC TEST PROJECT - not real",
                song_title="SYNTHETIC TEST SONG - not real",
                song_id_or_stable_operator_label="synthetic_song_001",
                track_status_label="review",
                production_stage_label="mix_notes",
                blocker_labels=["synthetic_missing_reference_mix"],
                next_safe_move_labels=["synthetic_review_metadata_only"],
                confidence="medium",
                evidence_status="synthetic_operator_supplied_pending_review",
            )
        ],
    )

    payload = matrix.build_niles_album_matrix_review(repo_root=repo_root, generated_at=FIXED_NOW)
    row = payload["rows"][0]

    assert payload["matrix_status"] == "ready_for_review_from_governed_operator_metadata"
    assert payload["metadata_consumed"] is True
    assert payload["metadata_record_count"] == 1
    assert payload["row_count"] == 1
    assert row["album_project_name"] == "SYNTHETIC TEST PROJECT - not real"
    assert row["song_title"] == "SYNTHETIC TEST SONG - not real"
    assert row["track_status_label"] == "review"
    assert row["production_stage_label"] == "mix_notes"
    assert row["blocker_labels"] == ["synthetic_missing_reference_mix"]
    assert row["next_safe_move_labels"] == ["synthetic_review_metadata_only"]
    assert row["metadata_evidence_posture"] == "operator_supplied_metadata_evidence_not_album_truth"
    assert row["album_state_confirmed"] is False


def test_partial_metadata_row_supported_without_inventing_missing_fields(tmp_path):
    repo_root = _write_boundary(
        tmp_path,
        [
            _metadata_record(
                song_id_or_stable_operator_label="synthetic_song_label_001",
                blocker_labels=["synthetic_blocker_only"],
                evidence_status="operator_supplied_partial_metadata_evidence",
            )
        ],
    )

    payload = matrix.build_niles_album_matrix_review(repo_root=repo_root, generated_at=FIXED_NOW)
    row = payload["rows"][0]

    assert payload["matrix_status"] == "ready_for_review_from_governed_operator_metadata"
    assert row["row_label"] == "synthetic_song_label_001"
    assert row["album_project_name"] is None
    assert row["song_title"] is None
    assert row["track_status_label"] is None
    assert row["production_stage_label"] is None
    assert row["partial_metadata_supported"] is True
    assert row["review_readiness_status"] == "partial_metadata_review_ready"
    assert "album_project_name" in row["missing_fields"]
    assert "song_title" in row["missing_fields"]
    assert "track_status_label" in row["missing_fields"]
    assert row["blocker_labels"] == ["synthetic_blocker_only"]


def test_unknown_fields_are_not_treated_as_confirmed(tmp_path):
    repo_root = _write_boundary(
        tmp_path,
        [
            _metadata_record(
                song_id_or_stable_operator_label="synthetic_song_label_002",
                evidence_status="operator_supplied_unknown_incomplete",
            )
        ],
    )

    payload = matrix.build_niles_album_matrix_review(repo_root=repo_root, generated_at=FIXED_NOW)
    row = payload["rows"][0]

    assert payload["evidence_posture"]["unknown_fields_not_treated_as_confirmed"] is True
    assert payload["evidence_posture"]["album_state_confirmed"] is False
    assert row["album_state_confirmed"] is False
    assert row["missing_fields"]


def test_operator_metadata_is_evidence_not_truth(tmp_path):
    repo_root = _write_boundary(
        tmp_path,
        [
            _metadata_record(
                album_project_name="SYNTHETIC TEST PROJECT - not real",
                confidence="low",
                evidence_status="operator_supplied_unknown_incomplete",
            )
        ],
    )

    payload = matrix.build_niles_album_matrix_review(repo_root=repo_root, generated_at=FIXED_NOW)

    assert payload["evidence_posture"]["operator_metadata_treated_as_evidence_not_truth"] is True
    assert payload["evidence_posture"]["review_readiness_is_not_release_or_audio_truth"] is True
    assert payload["real_album_metadata_recorded"] is True
    assert payload["rows"][0]["metadata_evidence_posture"] == "operator_supplied_metadata_evidence_not_album_truth"
    assert payload["rows"][0]["album_state_confirmed"] is False


def test_no_raw_audio_daw_broad_scan_mutation_runtime_send_or_approval_authority_added(tmp_path):
    repo_root = _write_boundary(
        tmp_path,
        [
            _metadata_record(
                song_title="SYNTHETIC TEST SONG - not real",
                daw_session_existence_flag=True,
                blocker_labels=["synthetic_metadata_only_blocker"],
            )
        ],
    )

    payload = matrix.build_niles_album_matrix_review(repo_root=repo_root, generated_at=FIXED_NOW)
    row = payload["rows"][0]
    flags = payload["authority_boundary"]

    assert row["daw_session_existence_flag"] is True
    assert row["daw_session_contents_stored"] is False
    assert row["file_opened_or_scanned"] is False
    assert flags["raw_audio_ingest_allowed"] is False
    assert flags["daw_session_content_ingest_allowed"] is False
    assert flags["broad_private_drive_scan_allowed"] is False
    assert flags["logic_or_ableton_open_allowed"] is False
    assert flags["daw_automation_allowed"] is False
    assert flags["audio_file_mutation_allowed"] is False
    assert flags["runtime_authority_added"] is False
    assert flags["send_or_submit_authority_added"] is False
    assert flags["approval_authority_added"] is False


def test_generated_json_is_deterministic(tmp_path):
    repo_root = _write_boundary(
        tmp_path,
        [
            _metadata_record(
                song_title="SYNTHETIC TEST SONG - not real",
                blocker_labels=["synthetic_blocker"],
                next_safe_move_labels=["synthetic_next"],
            )
        ],
    )

    first = matrix.build_niles_album_matrix_review(repo_root=repo_root, generated_at=FIXED_NOW)
    second = matrix.build_niles_album_matrix_review(repo_root=repo_root, generated_at=FIXED_NOW)

    assert matrix.stable_json(first) == matrix.stable_json(second)


def test_export_writes_json_operator_and_cli_outputs(tmp_path, capsys):
    repo_root = _write_boundary(tmp_path, [])
    export_root = "generated/read_models"

    result = matrix.export_niles_album_matrix_review(
        repo_root=repo_root,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )
    payload = json.loads((repo_root / export_root / matrix.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (repo_root / export_root / matrix.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert result.matrix_status == "blocked_needs_governed_album_metadata"
    assert result.real_album_metadata_recorded is False
    assert payload["schema_version"] == matrix.SCHEMA_VERSION
    assert "Niles Album Matrix Review v0" in operator
    assert "Raw audio ingest allowed: `false`" in operator
    assert export_main(["--repo-root", str(repo_root), "--export-root", export_root, "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["matrix_status"] == "blocked_needs_governed_album_metadata"


def test_source_does_not_import_forbidden_execution_or_mutation_apis():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "niles_album_matrix_review.py",
            "scripts/export_niles_album_matrix_review.py",
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
    tree = ast.parse(Path("niles_album_matrix_review.py").read_text(encoding="utf-8"))
    write_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write_text"
    ]

    assert len(write_calls) == 2


def test_mission_control_app_code_is_not_referenced_or_changed():
    source = Path("niles_album_matrix_review.py").read_text(encoding="utf-8").lower()

    assert "openclaw mission controle" not in source
    assert "mission_control_app_changed\": true" not in source
