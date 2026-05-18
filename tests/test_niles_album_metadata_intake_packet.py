import ast
import json
from pathlib import Path

import niles_album_evidence_intake_boundary as boundary
import niles_album_metadata_intake_packet as packet
from scripts.export_niles_album_metadata_intake_packet import main as export_main


FIXED_NOW = "2026-05-17T12:00:00+00:00"


def test_intake_packet_template_is_deterministic():
    first = packet.build_niles_album_metadata_intake_packet(generated_at=FIXED_NOW)
    second = packet.build_niles_album_metadata_intake_packet(generated_at=FIXED_NOW)

    assert packet.stable_json(first) == packet.stable_json(second)
    assert first["schema_version"] == packet.SCHEMA_VERSION
    assert first["intake_packet_status"] == "template_ready_no_real_metadata_recorded"


def test_template_uses_placeholders_nulls_and_no_invented_album_facts():
    payload = packet.build_niles_album_metadata_intake_packet(generated_at=FIXED_NOW)
    template = payload["operator_facing_input_template"]
    record = template["metadata_records"][0]
    serialized = json.dumps(template)

    assert payload["template_uses_placeholders_not_facts"] is True
    assert payload["real_album_metadata_recorded"] is False
    assert payload["receipt_proof_status"]["template_contains_real_album_claims"] is False
    assert record["album_project_name"] is None
    assert record["song_title"] is None
    assert record["song_id_or_stable_operator_label"] is None
    assert record["blocker_labels"] == []
    assert record["next_safe_move_labels"] == []
    assert "SYNTHETIC TEST" not in serialized
    assert "real album" not in serialized.lower()


def test_allowed_fields_match_intake_boundary():
    payload = packet.build_niles_album_metadata_intake_packet(generated_at=FIXED_NOW)

    assert tuple(payload["allowed_fields"]) == boundary.ALLOWED_FIELD_NAMES
    assert payload["allowed_metadata_types"] == list(boundary.ALLOWED_METADATA_TYPES)
    assert "operator_supplied" in payload["allowed_fields"]
    assert "no_external_action" in payload["allowed_fields"]


def test_minimum_and_optional_fields_are_operator_facing():
    payload = packet.build_niles_album_metadata_intake_packet(generated_at=FIXED_NOW)

    assert payload["minimum_useful_fields"] == [
        "song_title",
        "song_id_or_stable_operator_label",
        "blocker_labels",
    ]
    assert "album_project_name" in payload["optional_fields"]
    assert "confidence" in payload["optional_fields"]
    assert "source_reference_path_label" in payload["optional_fields"]
    assert "raw_audio_path" not in payload["allowed_fields"]


def test_forbidden_raw_audio_daw_broad_scan_mutation_boundaries_are_present():
    payload = packet.build_niles_album_metadata_intake_packet(generated_at=FIXED_NOW)
    forbidden = payload["forbidden_boundaries"]
    flags = payload["authority_boundary"]

    assert forbidden["raw_audio_ingest"] == "forbidden"
    assert forbidden["daw_session_content_ingest"] == "forbidden"
    assert forbidden["broad_private_drive_scan"] == "forbidden"
    assert forbidden["daw_automation"] == "forbidden"
    assert forbidden["audio_or_session_file_mutation"] == "forbidden"
    assert forbidden["metadata_as_final_truth"] == "forbidden"
    assert flags["raw_audio_ingest_allowed"] is False
    assert flags["daw_session_content_ingest_allowed"] is False
    assert flags["broad_private_drive_scan_allowed"] is False
    assert flags["daw_automation_allowed"] is False
    assert flags["audio_file_mutation_allowed"] is False


def test_operator_metadata_is_evidence_not_truth():
    payload = packet.build_niles_album_metadata_intake_packet(generated_at=FIXED_NOW)

    assert payload["operator_metadata_treated_as_evidence_not_truth"] is True
    assert payload["unknown_fields_not_treated_as_confirmed"] is True
    assert payload["forbidden_boundaries"]["metadata_as_final_truth"] == "forbidden"


def test_backend_flow_connects_existing_command_and_consumers_without_executing_them():
    payload = packet.build_niles_album_metadata_intake_packet(generated_at=FIXED_NOW)
    flow_text = json.dumps(payload["backend_flow"])

    assert "scripts/export_niles_album_evidence_intake_boundary.py --metadata-input-json <path>" in flow_text
    assert "review packet" in flow_text
    assert "matrix review" in flow_text
    assert "documented_command_path_only_not_executed_by_this_packet" in flow_text
    assert payload["receipt_proof_status"]["external_action_taken"] is False


def test_no_runtime_send_submit_or_approval_authority_added():
    payload = packet.build_niles_album_metadata_intake_packet(generated_at=FIXED_NOW)
    flags = payload["authority_boundary"]

    assert flags["runtime_authority_added"] is False
    assert flags["tool_execution_authority_added"] is False
    assert flags["model_execution_authority_added"] is False
    assert flags["send_or_submit_authority_added"] is False
    assert flags["approval_authority_added"] is False
    assert flags["repo_b_authority_allowed"] is False


def test_export_writes_json_operator_and_cli_outputs(tmp_path, capsys):
    export_root = "generated/read_models"

    result = packet.export_niles_album_metadata_intake_packet(
        repo_root=tmp_path,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )
    payload = json.loads((tmp_path / export_root / packet.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / export_root / packet.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert result.intake_packet_status == "template_ready_no_real_metadata_recorded"
    assert result.real_album_metadata_recorded is False
    assert payload["schema_version"] == packet.SCHEMA_VERSION
    assert "Niles Album Metadata Intake Packet v0" in operator
    assert "Raw audio ingest allowed: `false`" in operator
    assert export_main(["--repo-root", str(tmp_path), "--export-root", export_root, "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["intake_packet_status"] == "template_ready_no_real_metadata_recorded"


def test_source_does_not_import_forbidden_execution_or_mutation_apis():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "niles_album_metadata_intake_packet.py",
            "scripts/export_niles_album_metadata_intake_packet.py",
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
    tree = ast.parse(Path("niles_album_metadata_intake_packet.py").read_text(encoding="utf-8"))
    write_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write_text"
    ]

    assert len(write_calls) == 2


def test_mission_control_app_code_is_not_referenced_or_changed():
    source = Path("niles_album_metadata_intake_packet.py").read_text(encoding="utf-8").lower()

    assert "openclaw mission controle" not in source
    assert "mission_control_app_changed\": true" not in source
