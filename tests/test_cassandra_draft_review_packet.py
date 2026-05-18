import ast
import json
from pathlib import Path

import cassandra_draft_review_packet as packet
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_cassandra_draft_review_packet import main as export_main

FIXED_NOW = "2026-05-18T12:00:00+00:00"


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _reconciliation(path: Path) -> Path:
    return _write_json(
        path,
        {
            "schema_version": "cassandra_email_calendar_capability_reconciliation_v0",
            "status": "reconciled_review_only_no_live_authority",
            "classification_summary": {"KEEP_AND_BRIDGE": ["cassandra_send_status_dry_run"]},
        },
    )


def _proof_capture(path: Path, *, proof_present: bool = False, match_present: bool = False) -> Path:
    return _write_json(
        path,
        {
            "schema_version": "capital_hilton_external_artifact_proof_capture_v0",
            "proof_records": {
                "coupa_payment_invoice_proof": {
                    "proof_status": "captured" if proof_present else "pending_not_recorded",
                    "raw_artifact_stored": False,
                },
                "excel_companion_invoice_artifact": {
                    "proof_status": "captured" if proof_present else "pending_not_recorded",
                    "raw_artifact_stored": False,
                },
                "excel_coupa_match_proof": {
                    "proof_status": "verified" if match_present else "pending_not_recorded",
                    "raw_artifact_stored": False,
                },
            },
        },
    )


def _send_gate(path: Path, *, proof_present: bool = False, match_present: bool = False, draft_present: bool = False) -> Path:
    return _write_json(
        path,
        {
            "schema_version": "capital_hilton_send_approval_gate_v0",
            "current_approval_availability_state": "unavailable_missing_email_draft"
            if proof_present and match_present and not draft_present
            else "unavailable_missing_excel_match_proof"
            if proof_present and not match_present
            else "unavailable_missing_coupa_invoice_proof",
            "prerequisite_evidence_status": {
                "coupa_invoice_proof_exists": proof_present,
                "coupa_invoice_proof_references_expected_po_invoice_context": proof_present,
                "excel_companion_invoice_artifact_exists": proof_present,
                "excel_companion_invoice_verified_to_match_coupa": match_present,
                "cassandra_email_draft_exists": draft_present,
                "attachment_reference_exists": False,
                "draft_identity_hash_reference_exists": False,
                "attachment_identity_hash_reference_exists": False,
                "no_unresolved_critical_blockers": False,
            },
            "blocker_status": {
                "failure_reasons": [
                    "missing_email_draft",
                    "missing_attachment_reference",
                    "missing_draft_identity_hash_reference",
                    "missing_attachment_identity_hash_reference",
                ]
            },
        },
    )


def _build(tmp_path: Path, *, proof_present: bool = False, match_present: bool = False) -> dict:
    return packet.build_cassandra_draft_review_packet(
        reconciliation_json=_reconciliation(tmp_path / "reconciliation.json"),
        proof_capture_json=_proof_capture(tmp_path / "proof.json", proof_present=proof_present, match_present=match_present),
        send_gate_json=_send_gate(tmp_path / "gate.json", proof_present=proof_present, match_present=match_present),
        generated_at=FIXED_NOW,
    )


def test_draft_review_packet_is_deterministic_review_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)
    assert packet.stable_json(first) == packet.stable_json(second)
    assert first["schema_version"] == packet.SCHEMA_VERSION
    assert first["packet_kind"] == "cassandra_email_draft_review_packet"
    assert first["draft_status"] == "proposed_review_packet_not_gmail_draft"
    assert first["review_only"] is True
    assert first["read_model_only"] is True


def test_capital_hilton_missing_proofs_keep_final_send_blocked(tmp_path):
    payload = _build(tmp_path)
    proof_ids = {item["proof_type"]: item for item in payload["required_proofs"]}
    assert payload["send_eligibility"]["final_send_gate_state"] == "unavailable_missing_coupa_invoice_proof"
    assert payload["send_eligibility"]["send_available_now"] is False
    assert payload["receipt_proof_status"]["final_send_remains_blocked"] is True
    assert proof_ids["coupa_payment_invoice_proof"]["present_now"] is False
    assert proof_ids["excel_coupa_match_proof"]["present_now"] is False
    assert "missing_coupa_payment_invoice_proof" in payload["send_eligibility"]["why_blocked"]


def test_partial_proof_still_blocks_without_excel_match_and_draft_attachment(tmp_path):
    payload = _build(tmp_path, proof_present=True, match_present=False)
    assert payload["send_eligibility"]["final_send_gate_state"] == "unavailable_missing_excel_match_proof"
    assert any(blocker["blocker_id"] == "missing_excel_coupa_match_proof" for blocker in payload["blockers"])
    assert payload["gmail_draft_created"] is False
    assert payload["attachments_expected"][0]["raw_pdf_attached"] is False


def test_packet_supports_review_draft_fields_without_live_account_access(tmp_path):
    payload = _build(tmp_path)
    assert payload["draft_id"].startswith("cass_draft_review_")
    assert payload["recipient_group"]["recipient_roles_only"] is True
    assert payload["recipient_group"]["raw_private_contact_expanded"] is False
    assert payload["subject"]["subject_status"] == "generated_from_governed_workflow_state"
    assert payload["body"]["body_mode"] == "summary_preview_only"
    assert payload["body"]["live_gmail_content_used"] is False
    assert payload["attachments_expected"][0]["status"] == "protected_reference_placeholder_only"


def test_approval_is_specific_action_scoped_not_generic_send_authority(tmp_path):
    payload = _build(tmp_path)
    approval = payload["approval_requirements"]
    assert approval["guardian_required_before_any_send"] is True
    assert approval["approval_scope"] == "specific_draft_specific_attachment_specific_workflow_only"
    assert approval["generic_send_authority_allowed"] is False
    assert approval["approval_request_created_in_this_lane"] is False
    assert approval["approval_receipt_present"] is False
    assert payload["receipt_proof_status"]["approval_specific_action_scoped"] is True
    assert payload["receipt_proof_status"]["generic_send_authority_added"] is False


def test_no_live_gmail_draft_send_calendar_oauth_pdf_spreadsheet_or_runtime_authority(tmp_path):
    payload = _build(tmp_path)
    for key, expected in packet.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["authority_boundary"][key] is expected
    assert payload["gmail_draft_created"] is False
    assert payload["email_sent"] is False
    assert payload["pdf_generated_or_attached"] is False
    assert payload["spreadsheet_mutation_triggered"] is False
    assert payload["runtime_authority_added"] is False


def test_export_writes_json_operator_and_cli(tmp_path, capsys):
    export_root = tmp_path / "generated/read_models"
    result = packet.export_cassandra_draft_review_packet(
        repo_root=tmp_path,
        export_root="generated/read_models",
        reconciliation_json=_reconciliation(tmp_path / "reconciliation.json"),
        proof_capture_json=_proof_capture(tmp_path / "proof.json"),
        send_gate_json=_send_gate(tmp_path / "gate.json"),
        generated_at=FIXED_NOW,
    )
    payload = json.loads((export_root / packet.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / packet.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    assert result.gmail_draft_created is False
    assert payload["receipt_proof_status"]["draft_review_packet_created"] is True
    assert "Cassandra Draft Review Packet v0" in operator
    assert "Gmail draft created: `false`" in operator
    assert export_main(
        [
            "--repo-root",
            str(tmp_path),
            "--export-root",
            "generated/read_models",
            "--reconciliation-json",
            str(tmp_path / "reconciliation.json"),
            "--proof-capture-json",
            str(tmp_path / "proof.json"),
            "--send-gate-json",
            str(tmp_path / "gate.json"),
            "--format",
            "json",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["gmail_draft_created"] is False


def test_generated_read_model_files_are_safe_mirror_candidates(tmp_path):
    export_root = tmp_path / "generated/read_models"
    packet.export_cassandra_draft_review_packet(
        repo_root=tmp_path,
        export_root="generated/read_models",
        reconciliation_json=_reconciliation(tmp_path / "reconciliation.json"),
        proof_capture_json=_proof_capture(tmp_path / "proof.json"),
        send_gate_json=_send_gate(tmp_path / "gate.json"),
        generated_at=FIXED_NOW,
    )
    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))
    assert packet.JSON_EXPORT_NAME in expected
    assert packet.OPERATOR_EXPORT_NAME in expected


def test_source_does_not_import_or_call_forbidden_live_authority():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in ["cassandra_draft_review_packet.py", "scripts/export_cassandra_draft_review_packet.py"]
    )
    forbidden = [
        "from google_access_broker",
        "import google_access_broker",
        "broker_call(",
        "smtplib",
        "imaplib",
        "poplib",
        "import oauth",
        "oauthlib",
        "subprocess",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "webbrowser",
        "selenium",
        "playwright",
        "openpyxl",
        "pyautogui",
        "shell=true",
    ]
    for token in forbidden:
        assert token not in source


def test_write_calls_are_limited_to_generated_read_model_exports():
    tree = ast.parse(Path("cassandra_draft_review_packet.py").read_text(encoding="utf-8"))
    write_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write_text"
    ]
    assert len(write_calls) == 2
