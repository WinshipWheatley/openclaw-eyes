import ast
import json
from pathlib import Path

import niles_album_review_packet as packet
from scripts.export_niles_album_review_packet import main as export_main


FIXED_NOW = "2026-05-17T12:00:00+00:00"


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
    assert payload["packet_status"] == "blocked_needs_governed_album_evidence"
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


def test_missing_evidence_produces_blocked_needs_ingestion_status_not_hallucinated_state():
    payload = packet.build_niles_album_review_packet(generated_at=FIXED_NOW)
    rendered = packet.format_niles_album_review_packet(payload)

    assert "blocked_needs_governed_album_evidence" in rendered
    assert "Album state confirmed: `false`" in rendered
    assert "No governed album/project metadata packet exists yet" in rendered
    assert "metadata-only Niles album evidence intake boundary" in rendered


def test_export_writes_json_operator_and_cli_outputs(tmp_path, capsys):
    export_root = tmp_path / "read_models"

    result = packet.export_niles_album_review_packet(export_root=export_root, generated_at=FIXED_NOW)
    payload = json.loads((export_root / packet.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / packet.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert result.packet_status == "blocked_needs_governed_album_evidence"
    assert payload["schema_version"] == packet.SCHEMA_VERSION
    assert "Niles Album Review Packet v0" in operator
    assert "DAW automation added: `false`" in operator
    assert export_main(["--export-root", str(export_root), "--format", "json"]) == 0
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
