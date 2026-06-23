import ast
import json
from pathlib import Path

import niles_album_review_packet as packet
from scripts.export_niles_album_review_packet import main as export_main


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


def test_packet_uses_governed_evidence_only_and_generic_shape():
    payload = packet.build_niles_album_review_packet(generated_at=FIXED_NOW)

    assert payload["schema_version"] == packet.SCHEMA_VERSION
    assert payload["packet_identity"]["packet_kind"] == "operator_review_packet"
    assert payload["workflow_domain"] == "music_art"
    assert payload["workflow_name"] == "Niles album progress review"
    assert payload["governed_evidence_only"] is True
    assert payload["repo_a_canonical"] is True
    assert payload["repo_b_reference_only"] is True
    assert payload["source_summary"]["all_sources_repo_a_read_models_or_docs"] is True
    assert payload["source_summary"]["broad_private_drive_scan_triggered"] is False
    assert payload["source_summary"]["raw_audio_ingested"] is False
    assert all(source["source_path"].startswith("generated/read_models/") for source in payload["source_evidence"])


def test_unknown_album_state_is_not_confirmed():
    payload = packet.build_niles_album_review_packet(generated_at=FIXED_NOW)

    assert payload["album_state_confirmed"] is False
    assert payload["unknown_album_state_not_treated_as_confirmed"] is True
    assert payload["evidence_sufficient_for_album_status"] is False
    # Status is partial when track registry is available, blocked when not.
    assert payload["packet_status"] in (
        "blocked_needs_governed_album_evidence",
        "partial_track_registry_only_operator_metadata_still_needed",
        "ready_for_review_from_governed_operator_metadata",
    )
    assert payload["metadata_consumption"]["metadata_consumed"] is False
    assert payload["metadata_consumption"]["metadata_record_count"] == 0
    assert any(item["item_id"] == "missing_current_album_source_of_truth" for item in payload["missing_evidence"])
    assert any(blocker["blocker_id"] == "album_source_of_truth_unconfirmed" for blocker in payload["blockers"])


def test_old_docs_and_repo_b_are_evidence_not_truth():
    payload = packet.build_niles_album_review_packet(generated_at=FIXED_NOW)

    assert payload["workflow_posture"]["old_files_treated_as_evidence_not_truth"] is True
    assert payload["memory_album_posture"]["album_state_confirmed"] is False
    assert payload["memory_album_posture"]["import_allowed_now"] is False
    assert payload["repo_b_music_candidate_posture"]["repo_b_reference_only"] is True
    assert payload["repo_b_music_candidate_posture"]["authority_status"] == "reference_only_not_runtime_authority"
    assert payload["stale_or_legacy_evidence"][0]["old_files_treated_as_evidence_not_truth"] is True


def test_review_packet_is_deterministic():
    first = packet.build_niles_album_review_packet(generated_at=FIXED_NOW)
    second = packet.build_niles_album_review_packet(generated_at=FIXED_NOW)

    assert packet.stable_json(first) == packet.stable_json(second)


def test_one_operator_metadata_record_produces_review_only_item(tmp_path):
    repo_root = _write_boundary(
        tmp_path,
        [
            _metadata_record(
                album_project_name="SYNTHETIC TEST PROJECT - not real",
                song_title="SYNTHETIC TEST SONG - not real",
                track_status_label="review",
                production_stage_label="mix_notes",
                blocker_labels=["synthetic_missing_reference_mix"],
                next_safe_move_labels=["synthetic_review_metadata_only"],
                confidence="medium",
                evidence_status="synthetic_operator_supplied_pending_review",
            )
        ],
    )

    payload = packet.build_niles_album_review_packet(repo_root=repo_root, generated_at=FIXED_NOW)
    item = payload["operator_metadata_review_items"][0]

    assert payload["packet_status"] == "ready_for_review_from_governed_operator_metadata"
    assert payload["metadata_consumption"]["metadata_consumed"] is True
    assert payload["metadata_consumption"]["metadata_record_count"] == 1
    assert payload["evidence_sufficient_for_review_packet"] is True
    assert item["album_project_name"] == "SYNTHETIC TEST PROJECT - not real"
    assert item["song_title"] == "SYNTHETIC TEST SONG - not real"
    assert item["track_status_label"] == "review"
    assert item["production_stage_label"] == "mix_notes"
    assert item["blocker_labels"] == ["synthetic_missing_reference_mix"]
    assert item["next_safe_move_labels"] == ["synthetic_review_metadata_only"]
    assert item["metadata_evidence_posture"] == "operator_supplied_metadata_evidence_not_album_truth"
    assert item["album_state_confirmed"] is False


def test_partial_operator_metadata_record_is_consumed_without_inventing_fields(tmp_path):
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

    payload = packet.build_niles_album_review_packet(repo_root=repo_root, generated_at=FIXED_NOW)
    item = payload["operator_metadata_review_items"][0]

    assert payload["packet_status"] == "ready_for_review_from_governed_operator_metadata"
    assert item["item_label"] == "synthetic_song_label_001"
    assert item["album_project_name"] is None
    assert item["song_title"] is None
    assert item["track_status_label"] is None
    assert item["partial_metadata_supported"] is True
    assert "album_project_name" in item["missing_or_unknown_fields"]
    assert "track_status_label" in item["missing_or_unknown_fields"]
    assert item["album_state_confirmed"] is False


def test_operator_metadata_is_evidence_not_truth_even_when_consumed(tmp_path):
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

    payload = packet.build_niles_album_review_packet(repo_root=repo_root, generated_at=FIXED_NOW)

    assert payload["metadata_consumption"]["metadata_evidence_posture"] == "operator_supplied_metadata_evidence_not_album_truth"
    assert payload["metadata_consumption"]["unknown_fields_not_treated_as_confirmed"] is True
    assert payload["album_state_confirmed"] is False
    assert payload["evidence_sufficient_for_album_status"] is False
    assert payload["operator_metadata_review_items"][0]["album_state_confirmed"] is False


def test_metadata_consumption_does_not_add_raw_audio_daw_scan_mutation_or_runtime_authority(tmp_path):
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

    payload = packet.build_niles_album_review_packet(repo_root=repo_root, generated_at=FIXED_NOW)
    item = payload["operator_metadata_review_items"][0]
    flags = payload["authority_boundary"]

    assert item["daw_session_existence_flag"] is True
    assert item["daw_session_contents_stored"] is False
    assert item["file_opened_or_scanned"] is False
    assert flags["raw_audio_ingest_allowed"] is False
    assert flags["logic_or_ableton_open_allowed"] is False
    assert flags["daw_automation_allowed"] is False
    assert flags["audio_file_mutation_allowed"] is False
    assert flags["runtime_authority_added"] is False
    assert flags["send_or_submit_authority_added"] is False


def test_generated_json_with_metadata_is_deterministic(tmp_path):
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

    first = packet.build_niles_album_review_packet(repo_root=repo_root, generated_at=FIXED_NOW)
    second = packet.build_niles_album_review_packet(repo_root=repo_root, generated_at=FIXED_NOW)

    assert packet.stable_json(first) == packet.stable_json(second)


def test_no_audio_daw_file_mutation_or_runtime_authority_added():
    payload = packet.build_niles_album_review_packet(generated_at=FIXED_NOW)
    flags = payload["authority_boundary"]

    assert flags["review_only"] is True
    assert flags["daw_automation_allowed"] is False
    assert flags["audio_file_mutation_allowed"] is False
    assert flags["broad_private_drive_scan_allowed"] is False
    assert flags["raw_audio_ingest_allowed"] is False
    assert flags["logic_or_ableton_open_allowed"] is False
    assert flags["finder_file_operation_allowed"] is False
    assert flags["repo_b_authority_allowed"] is False
    assert flags["runtime_authority_added"] is False
    assert flags["send_or_submit_authority_added"] is False
    assert payload["runtime_readiness_posture"]["can_execute_directly"] is False
    assert payload["runtime_readiness_posture"]["can_bypass_approval"] is False


def test_missing_evidence_produces_no_hallucinated_album_state(tmp_path):
    # Use a tmp_path with no track registry to verify truly-blocked state.
    repo_root = tmp_path
    (tmp_path / "generated" / "read_models").mkdir(parents=True, exist_ok=True)
    payload = packet.build_niles_album_review_packet(repo_root=repo_root, generated_at=FIXED_NOW)
    rendered = packet.format_niles_album_review_packet(payload)

    assert payload["packet_status"] == "blocked_needs_governed_album_evidence"
    assert "blocked_needs_governed_album_evidence" in rendered
    assert "Album state confirmed: `false`" in rendered
    assert "No governed album/project metadata packet exists yet" in rendered
    assert "metadata-only Niles album evidence intake boundary" in rendered


def test_export_writes_json_operator_and_cli_outputs(tmp_path, capsys):
    # Use tmp_path as repo_root so no live read-models bleed in.
    export_root = tmp_path / "read_models"
    (tmp_path / "generated" / "read_models").mkdir(parents=True, exist_ok=True)

    result = packet.export_niles_album_review_packet(repo_root=tmp_path, export_root=export_root, generated_at=FIXED_NOW)
    payload = json.loads((export_root / packet.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / packet.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert result.packet_status == "blocked_needs_governed_album_evidence"
    assert payload["schema_version"] == packet.SCHEMA_VERSION
    assert "Niles Album Review Packet v0" in operator
    assert "DAW automation added: `false`" in operator
    assert export_main(["--repo-root", str(tmp_path), "--export-root", str(export_root), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["packet_status"] == "blocked_needs_governed_album_evidence"


def test_source_does_not_import_forbidden_execution_or_file_mutation_apis():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "niles_album_review_packet.py",
            "scripts/export_niles_album_review_packet.py",
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
    tree = ast.parse(Path("niles_album_review_packet.py").read_text(encoding="utf-8"))
    write_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write_text"
    ]

    assert len(write_calls) == 2
