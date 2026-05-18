import ast
import json
from pathlib import Path

import capital_hilton_external_artifact_proof_capture as proof
import capital_hilton_send_approval_gate as gate
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_capital_hilton_external_artifact_proof_capture import main as export_main


FIXED_NOW = "2026-05-18T02:20:00+00:00"


def _real_proof_inputs() -> dict:
    return {
        "proof_records": {
            "coupa_payment_invoice_proof": {
                "proof_status": "captured",
                "operator_supplied": True,
                "protected_artifact_reference": "protected://capital-hilton/coupa-invoice-proof/redacted-ref",
                "protected_artifact_type": "coupa_supplier_portal_invoice_pdf_reference",
                "artifact_identity_or_hash": "sha256:coupa-proof-redacted-metadata-hash",
                "invoice_number": "operator-supplied-invoice-number",
                "invoice_date": "2026-05-18",
                "invoice_amount": "800.00 USD",
                "po_number": "DCASH00983536",
                "source_basis": "operator_supplied_metadata_only",
            },
            "excel_companion_invoice_artifact": {
                "proof_status": "captured",
                "operator_supplied": True,
                "protected_artifact_reference": "protected://capital-hilton/excel-companion-invoice/redacted-ref",
                "protected_artifact_type": "excel_companion_invoice_pdf_reference",
                "artifact_identity_or_hash": "sha256:excel-companion-redacted-metadata-hash",
                "invoice_number": "operator-supplied-invoice-number",
                "invoice_date": "2026-05-18",
                "invoice_amount": "800.00 USD",
                "po_number": "DCASH00983536",
                "source_basis": "operator_supplied_metadata_only",
            },
            "excel_coupa_match_proof": {
                "proof_status": "verified",
                "operator_supplied": True,
                "protected_artifact_reference": "protected://capital-hilton/excel-coupa-match/redacted-ref",
                "protected_artifact_type": "excel_coupa_match_metadata_reference",
                "artifact_identity_or_hash": "sha256:match-proof-redacted-metadata-hash",
                "invoice_number": "operator-supplied-invoice-number",
                "invoice_amount": "800.00 USD",
                "po_number": "DCASH00983536",
                "match_status": "matched",
                "match_basis": "operator_supplied_redacted_metadata_match",
            },
        }
    }


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


def test_no_proof_is_captured_without_explicit_operator_input_or_safe_metadata():
    payload = proof.build_capital_hilton_external_artifact_proof_capture(generated_at=FIXED_NOW)
    rail = payload["capital_hilton_proof_evidence_rail"]

    assert payload["status_summary"]["real_proof_recorded"] is False
    assert payload["status_summary"]["proof_evidence_rail_status"] == "blocked_waiting_for_governed_proof"
    assert rail["expected_context"]["po_number"] == "DCASH00983536"
    assert rail["expected_context"]["excel_companion_invoice"]["invoice_number"] == "2026-1005"
    assert rail["final_send_approval_eligibility"]["payment_invoice_proof_present"] is False
    assert rail["final_send_approval_eligibility"]["companion_invoice_match_verified"] is False
    assert rail["protected_evidence_boundary"]["raw_coupa_pdf_stored"] is False
    assert payload["operator_proof_intake"]["intake_path_added"] is True
    assert payload["operator_proof_intake"]["proof_input_supplied"] is False
    assert payload["operator_proof_intake"]["recorded_real_proof_count"] == 0
    assert payload["final_send_approval_availability_state"] == "unavailable_missing_coupa_invoice_proof"
    assert all(record["proof_status"] == "pending_not_recorded" for record in payload["proof_records"].values())
    assert payload["proof_capture_requirements"]["proof_requires_explicit_operator_input_or_safe_metadata"] is True


def test_partial_proof_intake_records_only_supplied_coupa_metadata():
    inputs = {
        "proof_records": {
            "coupa_payment_invoice_proof": {
                "proof_status": "captured",
                "operator_supplied": True,
                "protected_artifact_reference": "protected://capital-hilton/coupa-invoice-proof/redacted-ref",
                "protected_artifact_type": "coupa_supplier_portal_invoice_pdf_reference",
                "artifact_identity_or_hash": "sha256:coupa-proof-redacted-metadata-hash",
                "invoice_number": "operator-supplied-invoice-number",
                "invoice_date": "2026-05-18",
                "invoice_amount": "800.00 USD",
                "po_number": "DCASH00983536",
                "raw_artifact_contents": "RAW PDF BODY THAT MUST NOT BE STORED",
            }
        }
    }

    payload = proof.build_capital_hilton_external_artifact_proof_capture(
        proof_inputs=inputs,
        generated_at=FIXED_NOW,
    )
    text = json.dumps(payload).lower()

    assert payload["operator_proof_intake"]["partial_proof_intake_supported"] is True
    assert payload["operator_proof_intake"]["supplied_proof_count"] == 1
    assert payload["operator_proof_intake"]["recorded_real_proof_count"] == 1
    assert payload["proof_records"]["coupa_payment_invoice_proof"]["proof_status"] == "captured"
    assert payload["proof_records"]["excel_companion_invoice_artifact"]["proof_status"] == "pending_not_recorded"
    assert payload["proof_records"]["excel_coupa_match_proof"]["proof_status"] == "pending_not_recorded"
    assert payload["final_send_approval_availability_state"] == "unavailable_missing_excel_companion_invoice"
    assert "raw pdf body" not in text


def test_supplied_proof_metadata_is_evidence_only_and_raw_contents_are_not_stored():
    payload = proof.build_capital_hilton_external_artifact_proof_capture(
        proof_inputs=_real_proof_inputs(),
        generated_at=FIXED_NOW,
    )
    rail = payload["capital_hilton_proof_evidence_rail"]
    text = json.dumps(payload).lower()

    assert payload["status_summary"]["real_proof_recorded"] is True
    assert rail["rail_status"] == "blocked_waiting_for_governed_proof"
    assert rail["final_send_approval_eligibility"]["payment_invoice_proof_present"] is True
    assert rail["final_send_approval_eligibility"]["companion_invoice_match_verified"] is True
    assert rail["final_send_approval_eligibility"]["send_execution_available_now"] is False
    assert payload["proof_records"]["coupa_payment_invoice_proof"]["proof_status"] == "captured"
    assert payload["proof_records"]["excel_companion_invoice_artifact"]["proof_status"] == "captured"
    assert payload["proof_records"]["excel_coupa_match_proof"]["proof_status"] == "captured"
    assert payload["authority_boundary"]["evidence_only"] is True
    assert payload["raw_sensitive_artifact_stored_in_read_model"] is False
    assert "raw pdf body" not in text
    assert "password is" not in text
    assert "token=" not in text
    assert "1009 smithville" not in text


def test_excel_vs_coupa_match_is_not_verified_without_explicit_match_proof():
    inputs = _real_proof_inputs()
    inputs["proof_records"]["excel_coupa_match_proof"].pop("match_status")
    payload = proof.build_capital_hilton_external_artifact_proof_capture(
        proof_inputs=inputs,
        generated_at=FIXED_NOW,
    )

    assert payload["proof_records"]["excel_coupa_match_proof"]["proof_status"] == "pending_not_recorded"
    assert payload["final_send_approval_prerequisites"]["excel_companion_invoice_verified_to_match_coupa"] is False
    assert payload["final_send_approval_availability_state"] == "unavailable_missing_excel_match_proof"


def test_negative_match_proof_is_recorded_as_evidence_without_unlocking_send_gate():
    inputs = _real_proof_inputs()
    inputs["proof_records"]["excel_coupa_match_proof"]["match_status"] = "mismatch"
    inputs["proof_records"]["excel_coupa_match_proof"]["match_basis"] = "operator_supplied_difference_found"

    payload = proof.build_capital_hilton_external_artifact_proof_capture(
        proof_inputs=inputs,
        generated_at=FIXED_NOW,
    )

    assert payload["operator_proof_intake"]["supplied_proof_count"] == 3
    assert payload["proof_records"]["excel_coupa_match_proof"]["operator_supplied"] is True
    assert payload["proof_records"]["excel_coupa_match_proof"]["match_status"] == "mismatch"
    assert payload["proof_records"]["excel_coupa_match_proof"]["proof_status"] == "pending_not_recorded"
    assert payload["operator_proof_intake"]["recorded_real_proof_count"] == 2
    assert payload["final_send_approval_availability_state"] == "unavailable_missing_excel_match_proof"


def test_synthetic_test_proof_never_counts_as_real():
    inputs = _real_proof_inputs()
    inputs["proof_records"]["coupa_payment_invoice_proof"]["synthetic_or_test"] = True
    payload = proof.build_capital_hilton_external_artifact_proof_capture(
        proof_inputs=inputs,
        generated_at=FIXED_NOW,
    )

    assert payload["proof_records"]["coupa_payment_invoice_proof"]["proof_status"] == "synthetic_test_recorded_not_real"
    assert payload["final_send_approval_prerequisites"]["coupa_invoice_proof_exists"] is False
    assert payload["status_summary"]["real_proof_recorded"] is True
    assert payload["boundaries"]["synthetic_or_test_proof_recorded"] is True


def test_final_send_approval_can_reference_proof_state_but_stays_blocked_without_draft_attachment_and_payment(tmp_path):
    proof_payload = proof.build_capital_hilton_external_artifact_proof_capture(
        proof_inputs=_real_proof_inputs(),
        generated_at=FIXED_NOW,
    )
    proof_path = tmp_path / "proof.json"
    proof_path.write_text(proof.stable_json(proof_payload), encoding="utf-8")

    gate_payload = gate.build_capital_hilton_send_approval_gate(
        execution_path_json=_write_execution_path(tmp_path / "execution.json"),
        start_approval_json=_write_start_approval(tmp_path / "start.json"),
        power_stage_json=_write_power_stage(tmp_path / "power.json"),
        proof_capture_json=proof_path,
        generated_at=FIXED_NOW,
    )

    assert gate_payload["external_artifact_proof_capture_context"]["source_present"] is True
    assert gate_payload["prerequisite_evidence_status"]["coupa_invoice_proof_exists"] is True
    assert gate_payload["prerequisite_evidence_status"]["excel_companion_invoice_verified_to_match_coupa"] is True
    assert gate_payload["current_approval_availability_state"] == "unavailable_missing_email_draft"
    assert gate_payload["blocker_status"]["send_execution_available_now"] is False
    assert proof_payload["status_summary"]["paid_status"] is False


def test_partial_proof_intake_keeps_final_send_gate_blocked_until_match_proof_exists(tmp_path):
    partial_payload = proof.build_capital_hilton_external_artifact_proof_capture(
        proof_inputs={
            "proof_records": {
                "coupa_payment_invoice_proof": _real_proof_inputs()["proof_records"]["coupa_payment_invoice_proof"],
                "excel_companion_invoice_artifact": _real_proof_inputs()["proof_records"][
                    "excel_companion_invoice_artifact"
                ],
            }
        },
        generated_at=FIXED_NOW,
    )
    proof_path = tmp_path / "proof.json"
    proof_path.write_text(proof.stable_json(partial_payload), encoding="utf-8")

    gate_payload = gate.build_capital_hilton_send_approval_gate(
        execution_path_json=_write_execution_path(tmp_path / "execution.json"),
        start_approval_json=_write_start_approval(tmp_path / "start.json"),
        power_stage_json=_write_power_stage(tmp_path / "power.json"),
        proof_capture_json=proof_path,
        generated_at=FIXED_NOW,
    )

    assert partial_payload["final_send_approval_availability_state"] == "unavailable_missing_excel_match_proof"
    assert gate_payload["current_approval_availability_state"] == "unavailable_missing_excel_match_proof"
    assert gate_payload["send_approval_executable"] is False


def test_final_send_approval_remains_unavailable_until_required_proof_exists(tmp_path):
    proof_payload = proof.build_capital_hilton_external_artifact_proof_capture(generated_at=FIXED_NOW)
    proof_path = tmp_path / "proof.json"
    proof_path.write_text(proof.stable_json(proof_payload), encoding="utf-8")

    gate_payload = gate.build_capital_hilton_send_approval_gate(
        execution_path_json=_write_execution_path(tmp_path / "execution.json"),
        start_approval_json=_write_start_approval(tmp_path / "start.json"),
        power_stage_json=_write_power_stage(tmp_path / "power.json"),
        proof_capture_json=proof_path,
        generated_at=FIXED_NOW,
    )

    assert gate_payload["current_approval_availability_state"] == "unavailable_missing_coupa_invoice_proof"
    assert gate_payload["send_approval_executable"] is False


def test_export_writes_deterministic_safe_read_model_operator_and_cli_outputs(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    result = proof.export_capital_hilton_external_artifact_proof_capture(
        export_root=export_root,
        generated_at=FIXED_NOW,
    )
    payload = json.loads((export_root / proof.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator_text = (export_root / proof.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert result.coupa_invoice_proof_modeled is True
    assert result.excel_companion_artifact_modeled is True
    assert result.excel_coupa_match_proof_modeled is True
    assert result.real_proof_recorded is False
    assert result.operator_proof_intake_enabled is True
    assert result.partial_proof_intake_supported is True
    assert payload["status_summary"]["no_submit_no_browser_no_email_no_spreadsheet_no_secret_storage"] is True
    assert payload["capital_hilton_proof_evidence_rail"]["rail_status"] == "blocked_waiting_for_governed_proof"
    assert "Capital Hilton External Artifact Proof Capture" in operator_text
    assert "Proof Evidence Rail" in operator_text
    assert export_main(["--export-root", str(export_root), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["schema_version"] == proof.SCHEMA_VERSION


def test_cli_proof_input_json_records_partial_metadata_without_raw_artifact_storage(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    proof_input = tmp_path / "operator_proof_input.json"
    proof_input.write_text(
        json.dumps(
            {
                "proof_records": {
                    "coupa_payment_invoice_proof": {
                        "proof_status": "captured",
                        "operator_supplied": True,
                        "protected_artifact_reference": "protected://capital-hilton/coupa-invoice-proof/redacted-ref",
                        "protected_artifact_type": "coupa_supplier_portal_invoice_pdf_reference",
                        "artifact_identity_or_hash": "sha256:coupa-proof-redacted-metadata-hash",
                        "invoice_number": "operator-supplied-invoice-number",
                        "invoice_amount": "800.00 USD",
                        "po_number": "DCASH00983536",
                        "password": "password is not allowed here",
                        "raw_artifact_contents": "RAW PDF BODY THAT MUST NOT BE STORED",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    assert export_main(
        [
            "--proof-input-json",
            str(proof_input),
            "--export-root",
            str(export_root),
            "--format",
            "summary",
        ]
    ) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((export_root / proof.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator_text = (export_root / proof.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    text = json.dumps(payload).lower()

    assert summary["supplied_proof_count"] == 1
    assert summary["recorded_real_proof_count"] == 1
    assert payload["proof_records"]["coupa_payment_invoice_proof"]["proof_status"] == "captured"
    assert payload["proof_records"]["excel_companion_invoice_artifact"]["proof_status"] == "pending_not_recorded"
    assert payload["final_send_approval_availability_state"] == "unavailable_missing_excel_companion_invoice"
    assert "Operator Proof Intake" in operator_text
    assert "raw pdf body" not in text
    assert "password is" not in text


def test_generated_read_model_files_are_safe_mirror_candidates(tmp_path):
    export_root = tmp_path / "generated" / "read_models"
    proof.export_capital_hilton_external_artifact_proof_capture(
        export_root=export_root,
        generated_at=FIXED_NOW,
    )

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))
    assert proof.JSON_EXPORT_NAME in expected
    assert proof.OPERATOR_EXPORT_NAME in expected


def test_source_does_not_invoke_coupa_browser_email_spreadsheet_runtime_or_approval_authority():
    source_files = [
        Path("capital_hilton_external_artifact_proof_capture.py"),
        Path("scripts/export_capital_hilton_external_artifact_proof_capture.py"),
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

    tree = ast.parse(Path("capital_hilton_external_artifact_proof_capture.py").read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "subprocess" not in imported
