import ast
import json
from pathlib import Path

import niles_stage1_schema_contract as contract
from scripts.export_niles_stage1_schema_contract import main as export_main


FIXED_NOW = "2026-06-18T22:45:00+00:00"


def _build() -> dict:
    return contract.build_niles_stage1_schema_contract(generated_at=FIXED_NOW)


def _schemas(payload: dict) -> dict:
    return payload["schema_contracts_by_id"]


def test_stage1_contract_is_deterministic_and_schema_only():
    first = _build()
    second = _build()

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == contract.READ_MODEL_ID
    assert first["contract_status"] == contract.CONTRACT_STATUS
    assert first["machine_proof"]["schema_count"] == 6
    assert first["machine_proof"]["stage_gate_count"] == 5
    assert first["machine_proof"]["all_authority_flags_safe"] is True
    assert first["authority_boundary"]["runtime_authority_added"] is False
    assert first["authority_boundary"]["schema_only"] is True


def test_all_schema_contracts_have_required_fields():
    payload = _build()

    assert payload["schema_required_fields"] == list(contract.REQUIRED_SCHEMA_FIELDS)
    assert payload["machine_proof"]["all_required_schema_fields_present"] is True
    for schema in payload["schema_contracts"]:
        assert set(contract.REQUIRED_SCHEMA_FIELDS) <= set(schema)
        assert schema["required_fields"]
        assert schema["allowed_sources"]
        assert schema["blocked_sources"]
        assert schema["validation_rules"]
        assert schema["authority_boundary"]["runtime_authority_added"] is False


def test_interview_memory_schema_covers_music_profile_without_hidden_memory():
    payload = _build()
    interview = _schemas(payload)["niles_operator_interview_memory_v0"]
    template = payload["operator_input_templates"]["interview_memory_template"]

    assert interview["covered_instruments"] == list(contract.INSTRUMENTS)
    assert [item["instrument"] for item in template["instrument_profiles"]] == list(contract.INSTRUMENTS)
    assert "tenor_sax" in interview["covered_instruments"]
    assert "hidden memory" in interview["blocked_sources"]
    assert "broad private media scan" in interview["blocked_sources"]
    assert "taste_profile_refs" in interview["required_fields"]
    assert payload["machine_proof"]["taste_calibration_deferred"] is True
    assert payload["authority_boundary"]["hidden_memory_capture_allowed"] is False


def test_practice_ledger_and_adaptive_plan_use_shared_progression_without_writes():
    payload = _build()
    ledger = _schemas(payload)["niles_practice_ledger_event_v0"]
    plan = _schemas(payload)["niles_adaptive_practice_plan_v0"]
    primitive_ids = {item["primitive_id"] for item in payload["shared_primitives"]}

    assert "progression_feedback_loop" in primitive_ids
    assert payload["machine_proof"]["niles_uses_shared_primitives"] is True
    assert "specs/niles-music/PAUL_GILBERT_PROGRESSION.md" in ledger["allowed_sources"]
    assert "niles_practice_ledger_event_v0" in plan["allowed_sources"]
    assert ledger["authority_boundary"]["practice_ledger_write_allowed"] is False
    assert plan["authority_boundary"]["practice_ledger_write_allowed"] is False
    assert "ledger writes require a later authority envelope" in ledger["validation_rules"]


def test_logic_note_update_request_is_dry_run_only_and_does_not_open_daw():
    payload = _build()
    logic = _schemas(payload)["niles_logic_note_update_request_v0"]
    template = payload["operator_input_templates"]["logic_note_update_request_template"]

    assert template["dry_run_only"] is True
    assert template["required_operator_approval"] is True
    assert template["no_daw_launch"] is True
    assert template["no_session_media_mutation"] is True
    assert "opening Logic during Stage 1" in logic["blocked_sources"]
    assert "mutating session media, stems, bounces, or artwork" in logic["blocked_sources"]
    assert logic["authority_boundary"]["logic_or_ableton_open_allowed"] is False
    assert logic["authority_boundary"]["session_media_mutation_allowed"] is False
    assert payload["machine_proof"]["logic_note_update_dry_run_only"] is True


def test_studio_control_is_separate_gated_and_disabled_by_default():
    payload = _build()
    control = _schemas(payload)["niles_studio_control_authority_envelope_v0"]

    assert "operator_approval_receipt_ref" in control["required_fields"]
    assert "rollback_plan_ref" in control["required_fields"]
    assert "autonomous live control" in control["blocked_sources"]
    assert "ungated X32/DAW/MIDI/OSC action" in control["blocked_sources"]
    assert control["authority_boundary"]["studio_control_enabled"] is False
    assert control["authority_boundary"]["hardware_control_allowed"] is False
    assert payload["machine_proof"]["studio_control_separate_and_blocked"] is True


def test_maestro_handoff_is_metadata_only_not_tool_activation():
    payload = _build()
    handoff = _schemas(payload)["maestro_to_niles_handoff_packet_v0"]

    assert "blocked_authority" in handoff["required_fields"]
    assert "Niles cannot activate tools from a handoff" in handoff["validation_rules"]
    assert "agent self-assigned authority" in handoff["blocked_sources"]
    assert handoff["authority_boundary"]["tool_execution_allowed"] is False
    assert handoff["authority_boundary"]["agent_activation_allowed"] is False


def test_reference_docs_are_declared_without_raw_body_ingest():
    payload = _build()
    refs = {item["ref_id"]: item for item in payload["reference_docs"]}

    assert refs["producer_rubric"]["exists"] is True
    assert refs["producer_reference_map"]["exists"] is True
    assert refs["niles_album_metadata_intake_packet"]["exists"] is True
    assert refs["niles_music_subsystem_spec"]["used_as_contract_evidence"] is True
    assert refs["paul_gilbert_progression"]["used_as_contract_evidence"] is True
    assert all(item["raw_body_ingested"] is False for item in refs.values())


def test_no_live_or_external_authority_is_added():
    payload = _build()
    boundary = payload["authority_boundary"]

    assert boundary["send_hold_bypass_allowed"] is False
    assert boundary["external_send_allowed"] is False
    assert boundary["money_authority_allowed"] is False
    assert boundary["legal_discovery_allowed"] is False
    assert boundary["credential_access_allowed"] is False
    assert boundary["raw_audio_ingest_allowed"] is False
    assert boundary["broad_private_drive_scan_allowed"] is False
    assert payload["machine_proof"]["raw_private_bodies_included"] is False
    assert payload["machine_proof"]["credentials_or_secrets_included"] is False


def test_operator_markdown_contains_required_statuses():
    payload = _build()
    markdown = contract.format_niles_stage1_schema_contract(payload)

    assert "Niles Stage 1 Schema Contract v0" in markdown
    assert "Runtime authority added: `false`" in markdown
    assert "Studio control enabled: `false`" in markdown
    assert "SEND_HOLD bypass allowed: `false`" in markdown
    assert "Shared, Not Niles-Private" in markdown


def test_export_writes_json_operator_and_cli_outputs(tmp_path, capsys):
    export_root = "generated/read_models"

    result = contract.export_niles_stage1_schema_contract(
        repo_root=tmp_path,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )
    payload = json.loads((tmp_path / export_root / contract.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / export_root / contract.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert result.contract_status == contract.CONTRACT_STATUS
    assert result.schema_count == 6
    assert result.runtime_authority_added is False
    assert payload["schema_version"] == contract.SCHEMA_VERSION
    assert "Niles Stage 1 Schema Contract v0" in operator
    assert export_main(
        [
            "--repo-root",
            str(tmp_path),
            "--export-root",
            export_root,
            "--format",
            "json",
            "--generated-at",
            FIXED_NOW,
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["contract_status"] == contract.CONTRACT_STATUS


def test_source_does_not_import_forbidden_execution_or_mutation_apis():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "niles_stage1_schema_contract.py",
            "scripts/export_niles_stage1_schema_contract.py",
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
    tree = ast.parse(Path("niles_stage1_schema_contract.py").read_text(encoding="utf-8"))
    write_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write_text"
    ]

    assert len(write_calls) == 2
