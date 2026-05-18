import ast
import json
from pathlib import Path

import capital_hilton_operator_proof_input_packet as packet
import capital_hilton_external_artifact_proof_capture as proof
import capital_hilton_send_approval_gate as gate
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_capital_hilton_operator_proof_input_packet import main as export_main


FIXED_NOW = "2026-05-18T03:30:00+00:00"


def _write_execution_path(path: Path) -> Path:
    path.write_text(json.dumps({"schema_version": "capital_hilton_coupa_execution_path_v0"}) + "\n", encoding="utf-8")
    return path


def _write_start_approval(path: Path) -> Path:
    path.write_text(json.dumps({"schema_version": "capital_hilton_coupa_start_approval_packet_v0"}) + "\n", encoding="utf-8")
    return path


def _write_power_stage(path: Path) -> Path:
    path.write_text(
        json.dumps({"schema_version": "operator_sovereignty_power_stage_gate_read_model_v0"}) + "\n",
        encoding="utf-8",
    )
    return path


def test_operator_proof_input_packet_is_deterministic_template_only():
    first = packet.build_capital_hilton_operator_proof_input_packet(generated_at=FIXED_NOW)
    second = packet.build_capital_hilton_operator_proof_input_packet(generated_at=FIXED_NOW)

    assert packet.stable_json(first) == packet.stable_json(second)
    assert first["schema_version"] == packet.SCHEMA_VERSION
    assert first["template_status"] == "template_only_no_real_proof_recorded"
    assert first["real_proof_recorded"] is False
    assert first["proof_receipt_created"] is False
    assert first["proof_input_template_added"] is True


def test_template_sections_and_fields_align_with_proof_intake_command():
    payload = packet.build_capital_hilton_operator_proof_input_packet(generated_at=FIXED_NOW)
    shape = payload["proof_input_shape"]["proof_records"]

    assert payload["proof_intake_command"] == packet.PROOF_INTAKE_COMMAND
    assert payload["template_alignment"]["aligns_with_proof_intake_command"] is True
    assert set(shape) == set(proof.PROOF_TYPES)
    for proof_type, record in shape.items():
        assert record["proof_type"] == proof_type
        assert set(packet.TEMPLATE_FIELDS).issubset(record)
        assert record["proof_status"] == "pending_not_recorded"
        assert record["operator_supplied"] is False
        assert record["no_external_action"] is True
        assert "service_dates" in record
        assert "mismatch_reasons" in record
        assert "operator_confirmed" in record
        assert "redaction_status" in record
        assert "protection_status" in record


def test_empty_template_does_not_record_real_proof_and_send_gate_stays_blocked(tmp_path):
    payload = packet.build_capital_hilton_operator_proof_input_packet(generated_at=FIXED_NOW)
    baseline = proof.build_capital_hilton_external_artifact_proof_capture(generated_at=FIXED_NOW)
    proof_path = tmp_path / "proof.json"
    proof_path.write_text(proof.stable_json(baseline), encoding="utf-8")

    gate_payload = gate.build_capital_hilton_send_approval_gate(
        execution_path_json=_write_execution_path(tmp_path / "execution.json"),
        start_approval_json=_write_start_approval(tmp_path / "start.json"),
        power_stage_json=_write_power_stage(tmp_path / "power.json"),
        proof_capture_json=proof_path,
        generated_at=FIXED_NOW,
    )

    assert payload["proof_capture_baseline"]["real_proof_recorded"] is False
    assert payload["final_send_gate_posture"]["final_send_gate_remains_blocked"] is True
    assert gate_payload["current_approval_availability_state"] == "unavailable_missing_coupa_invoice_proof"
    assert gate_payload["send_approval_executable"] is False


def test_examples_are_labeled_and_synthetic_examples_never_count_as_real():
    payload = packet.build_capital_hilton_operator_proof_input_packet(generated_at=FIXED_NOW)
    examples = payload["example_payloads"]
    partial = examples["partial_coupa_proof_only_example"]
    full = examples["full_synthetic_test_metadata_example"]

    assert partial["example_is_real_proof"] is False
    assert partial["proof_records"]["coupa_payment_invoice_proof"]["synthetic_or_test"] is True
    assert partial["proof_records"]["coupa_payment_invoice_proof"]["service_dates"] == ["<YYYY-MM-DD>", "<YYYY-MM-DD>"]
    assert partial["proof_records"]["coupa_payment_invoice_proof"]["redaction_status"] == "redacted_or_protected_reference_only"
    assert full["example_is_real_proof"] is False
    assert full["all_records_are_synthetic_test_examples"] is True
    assert all(record["synthetic_or_test"] is True for record in full["proof_records"].values())
    assert all(record["protection_status"] == "synthetic_protected_reference" for record in full["proof_records"].values())

    synthetic_capture = proof.build_capital_hilton_external_artifact_proof_capture(
        proof_inputs=full,
        generated_at=FIXED_NOW,
    )
    assert synthetic_capture["status_summary"]["real_proof_recorded"] is False
    assert all(
        record["proof_status"] == "synthetic_test_recorded_not_real"
        for record in synthetic_capture["proof_records"].values()
    )


def test_template_avoids_raw_sensitive_artifact_content():
    payload = packet.build_capital_hilton_operator_proof_input_packet(generated_at=FIXED_NOW)
    text = json.dumps(payload).lower()

    forbidden_raw_values = [
        "raw pdf body",
        "excel binary",
        "1009 smithville",
        "bearer ",
        "api_key=",
        "token=",
        "portal_password_value",
        "check image bytes",
    ]
    for token in forbidden_raw_values:
        assert token not in text
    assert payload["authority_boundary"]["raw_sensitive_artifact_included"] is False
    assert payload["authority_boundary"]["raw_sensitive_artifact_stored_in_read_model"] is False


def test_export_writes_json_operator_and_safe_mirror_candidates(tmp_path, capsys):
    export_root = tmp_path / "generated" / "read_models"
    result = packet.export_capital_hilton_operator_proof_input_packet(
        export_root=export_root,
        generated_at=FIXED_NOW,
    )
    payload = json.loads((export_root / packet.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator_text = (export_root / packet.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert result.proof_input_template_added is True
    assert result.synthetic_examples_labeled is True
    assert result.real_proof_recorded is False
    assert result.final_send_approval_availability_state == "unavailable_missing_coupa_invoice_proof"
    assert "Capital Hilton Operator Proof Input Packet" in operator_text
    assert "Template only; no real proof was recorded" in operator_text

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))
    assert packet.JSON_EXPORT_NAME in expected
    assert packet.OPERATOR_EXPORT_NAME in expected

    assert export_main(["--export-root", str(export_root), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["schema_version"] == packet.SCHEMA_VERSION


def test_source_does_not_invoke_coupa_browser_email_spreadsheet_runtime_or_approval_authority():
    source_files = [
        Path("capital_hilton_operator_proof_input_packet.py"),
        Path("scripts/export_capital_hilton_operator_proof_input_packet.py"),
    ]
    forbidden = [
        "/home/openclaw_external/openclaw-runtime",
        "import subprocess",
        "subprocess.",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "send_message",
        "reply_text",
        "smtplib",
        "shell=True",
        "selenium",
        "playwright",
        "pyautogui",
        "openpyxl",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in text

    tree = ast.parse(Path("capital_hilton_operator_proof_input_packet.py").read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "subprocess" not in imported
