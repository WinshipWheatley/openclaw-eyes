import ast
import json
from pathlib import Path

import niles_album_evidence_intake_boundary as boundary
import niles_album_review_packet as review_packet
from scripts.export_niles_album_evidence_intake_boundary import main as export_main


FIXED_NOW = "2026-05-17T12:00:00+00:00"


def test_allowed_metadata_types_are_metadata_only():
    payload = boundary.build_niles_album_evidence_intake_boundary(generated_at=FIXED_NOW)
    fields = {item["field_name"]: item for item in payload["allowed_metadata_types"]}

    expected = {
        "album_project_name",
        "song_title",
        "song_id_or_stable_operator_label",
        "track_status_label",
        "production_stage_label",
        "source_reference_path_label",
        "daw_session_existence_flag",
        "last_known_operator_update",
        "blocker_labels",
        "next_safe_move_labels",
        "confidence",
        "evidence_status",
    }
    assert expected <= set(fields)
    assert all(item["metadata_only"] is True for item in fields.values())
    assert all("operator_supplied" in item["value_policy"] for item in fields.values())


def test_blocked_raw_private_daw_audio_types_remain_blocked():
    payload = boundary.build_niles_album_evidence_intake_boundary(generated_at=FIXED_NOW)
    blocked = set(payload["blocked_evidence_types"])

    assert "raw_audio" in blocked
    assert "daw_session_contents" in blocked
    assert "stems_mixes_masters" in blocked
    assert "broad_folder_scans" in blocked
    assert "private_drive_crawl" in blocked
    assert "inferred_song_status_without_evidence" in blocked
    assert "automatic_file_mutation" in blocked
    assert "unapproved_lyrics_ingest" in blocked
    assert "unapproved_private_notes_ingest" in blocked
    assert payload["authority_boundary"]["raw_audio_ingest_allowed"] is False
    assert payload["authority_boundary"]["daw_session_content_ingest_allowed"] is False
    assert payload["authority_boundary"]["broad_private_drive_scan_allowed"] is False


def test_unknown_album_state_remains_unknown_and_no_real_metadata_recorded():
    payload = boundary.build_niles_album_evidence_intake_boundary(generated_at=FIXED_NOW)

    assert payload["boundary_status"] == "contract_ready_no_real_metadata_recorded"
    assert payload["real_album_metadata_recorded"] is False
    assert payload["unknown_album_state_remains_unknown"] is True
    assert payload["receipt_proof_status"]["real_metadata_recorded"] is False
    assert payload["operator_supplied_metadata_packet_shape"]["empty_pending_template"]["template_status"] == "empty_pending_no_real_metadata_recorded"


def test_synthetic_example_is_labeled_synthetic_test():
    payload = boundary.build_niles_album_evidence_intake_boundary(generated_at=FIXED_NOW)
    example = payload["operator_supplied_metadata_packet_shape"]["synthetic_test_example"]

    assert payload["synthetic_examples_labeled"] is True
    assert example["synthetic_or_test"] is True
    assert example["operator_supplied"] is False
    assert "SYNTHETIC" in json.dumps(example)
    assert example["metadata_records"][0]["evidence_status"] == "synthetic_test_only_not_real_evidence"


def test_no_broad_scan_daw_audio_file_mutation_runtime_or_send_authority_added():
    payload = boundary.build_niles_album_evidence_intake_boundary(generated_at=FIXED_NOW)
    flags = payload["authority_boundary"]

    assert flags["metadata_only_intake_contract"] is True
    assert flags["daw_automation_allowed"] is False
    assert flags["audio_file_mutation_allowed"] is False
    assert flags["finder_file_operation_allowed"] is False
    assert flags["repo_b_authority_allowed"] is False
    assert flags["runtime_authority_added"] is False
    assert flags["tool_execution_authority_added"] is False
    assert flags["model_execution_authority_added"] is False
    assert flags["send_or_submit_authority_added"] is False
    assert flags["mission_control_app_changed"] is False


def test_niles_review_packet_references_boundary_but_remains_blocked_without_real_metadata():
    boundary.export_niles_album_evidence_intake_boundary(generated_at=FIXED_NOW)
    review_packet.export_niles_album_review_packet(generated_at=FIXED_NOW)
    payload = json.loads(Path("generated/read_models/niles_album_review_packet.json").read_text(encoding="utf-8"))

    assert payload["packet_status"] == "blocked_needs_governed_album_evidence"
    assert payload["album_state_confirmed"] is False
    assert payload["evidence_sufficient_for_album_status"] is False
    assert payload["evidence_intake_boundary_posture"]["boundary_present"] is True
    assert payload["evidence_intake_boundary_posture"]["real_album_metadata_recorded"] is False
    assert any(item["item_id"] == "missing_real_governed_album_metadata" for item in payload["missing_evidence"])
    assert any(source["source_id"] == "niles_album_evidence_intake_boundary" for source in payload["source_evidence"])


def test_boundary_output_is_deterministic():
    first = boundary.build_niles_album_evidence_intake_boundary(generated_at=FIXED_NOW)
    second = boundary.build_niles_album_evidence_intake_boundary(generated_at=FIXED_NOW)

    assert boundary.stable_json(first) == boundary.stable_json(second)


def test_export_writes_json_operator_and_cli_outputs(tmp_path, capsys):
    export_root = tmp_path / "read_models"

    result = boundary.export_niles_album_evidence_intake_boundary(export_root=export_root, generated_at=FIXED_NOW)
    payload = json.loads((export_root / boundary.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / boundary.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert result.boundary_status == "contract_ready_no_real_metadata_recorded"
    assert result.real_album_metadata_recorded is False
    assert payload["schema_version"] == boundary.SCHEMA_VERSION
    assert "Niles Album Evidence Intake Boundary v0" in operator
    assert "Raw audio ingest allowed: `false`" in operator
    assert export_main(["--export-root", str(export_root), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["boundary_status"] == "contract_ready_no_real_metadata_recorded"


def test_source_does_not_import_forbidden_execution_or_mutation_apis():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "niles_album_evidence_intake_boundary.py",
            "scripts/export_niles_album_evidence_intake_boundary.py",
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
    tree = ast.parse(Path("niles_album_evidence_intake_boundary.py").read_text(encoding="utf-8"))
    write_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write_text"
    ]

    assert len(write_calls) == 2
