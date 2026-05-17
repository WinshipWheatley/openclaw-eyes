import ast
import json
from pathlib import Path

import capital_hilton_manual_confirmation_receipt as receipt
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_capital_hilton_manual_confirmation_receipt import main as export_main


FIXED_NOW = "2026-05-17T18:45:00+00:00"


def _write_actionable_packet(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "capital_hilton_actionable_review_packet_v1",
                "packet_id": "finance_capital_hilton_invoice_packet_v0",
                "review_only": True,
                "actionable_for_manual_review": True,
                "ready_for_submission": False,
                "remaining_blockers": [
                    {
                        "blocker_id": "po_coupa_confirmation_required",
                        "severity": "blocks_final_submission",
                        "description": "PO number is still unknown and must be confirmed manually in Coupa.",
                        "next_safe_move": "Operator confirms PO/available credit in Coupa.",
                    },
                    {
                        "blocker_id": "recipient_confirmation_required",
                        "severity": "blocks_email_send",
                        "description": "Recipient posture is review-only and needs operator confirmation.",
                        "next_safe_move": "Operator confirms To/CC list.",
                    },
                    {
                        "blocker_id": "coupa_invoice_creation_manual_only",
                        "severity": "blocks_openclaw_submission",
                        "description": "Invoice must be created in Coupa manually.",
                        "next_safe_move": "Operator manually prepares/reviews Coupa entry.",
                    },
                    {
                        "blocker_id": "spreadsheet_invoice_number_manual_check",
                        "severity": "blocks_final_invoice_number_claim",
                        "description": "Invoice workbook was not read by OpenClaw.",
                        "next_safe_move": "Operator manually confirms next invoice number.",
                    },
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_default_receipt_does_not_invent_confirmations(tmp_path):
    packet_path = _write_actionable_packet(tmp_path / "capital_hilton_actionable_review_packet.json")

    payload = receipt.build_capital_hilton_manual_confirmation_receipt(
        actionable_packet_path=packet_path,
        generated_at=FIXED_NOW,
    )

    assert payload["schema_version"] == receipt.SCHEMA_VERSION
    assert payload["real_confirmations_recorded"] is False
    assert payload["recorded_confirmation_count"] == 0
    assert payload["pending_confirmation_count"] == len(receipt.SUPPORTED_CONFIRMATION_FIELDS)
    assert payload["read_model_posture"]["confirmations_invented"] is False
    assert payload["packet_ready_after_confirmations"]["packet_ready_for_manual_preparation"] is False
    assert payload["packet_ready_after_confirmations"]["packet_ready_for_submission"] is False
    assert payload["coupa_submit_triggered"] is False
    assert payload["spreadsheet_write_triggered"] is False
    assert payload["send_or_submit_authority_added"] is False
    assert all(item["operator_supplied"] is False for item in payload["confirmation_items"])
    assert all(item["evidence_status"] == "manual_confirmation_pending" for item in payload["pending_items"])
    assert all(item["no_external_action"] is True for item in payload["confirmation_items"])
    assert payload["remaining_blocked_item_count"] == 4


def test_supplied_confirmations_are_recorded_as_evidence_only(tmp_path):
    packet_path = _write_actionable_packet(tmp_path / "capital_hilton_actionable_review_packet.json")
    inputs = {
        "confirmations": {
            "po_coupa_requirement_confirmed": True,
            "recipient_confirmed": {"confirmed": True, "evidence_ref": "operator_manual_review:test"},
            "coupa_invoice_created_manually": True,
            "spreadsheet_invoice_number_checked": True,
            "include_2026_05_22": False,
            "include_older_gigs": {"decision": "exclude", "value_label": "do not include older gigs"},
        }
    }

    payload = receipt.build_capital_hilton_manual_confirmation_receipt(
        actionable_packet_path=packet_path,
        confirmation_inputs=inputs,
        generated_at=FIXED_NOW,
    )

    assert payload["real_confirmations_recorded"] is True
    assert payload["recorded_confirmation_count"] == len(receipt.SUPPORTED_CONFIRMATION_FIELDS)
    assert payload["pending_confirmation_count"] == 0
    assert payload["hard_blockers_cleared_by_receipt"] is True
    assert payload["scope_decision_pending"] is False
    assert payload["packet_ready_after_confirmations"]["packet_ready_for_manual_preparation"] is True
    assert payload["packet_ready_after_confirmations"]["packet_ready_for_submission"] is False
    assert payload["manual_confirmation_evidence"]
    assert all(item["receipts_are_evidence_only"] is True for item in payload["manual_confirmation_evidence"])
    assert all(item["operator_supplied"] is True for item in payload["manual_confirmation_evidence"])
    assert all(item["evidence_status"] == "operator_confirmation_evidence" for item in payload["manual_confirmation_evidence"])
    assert all(item["no_external_action"] is True for item in payload["manual_confirmation_evidence"])
    assert payload["remaining_blocked_item_count"] == 0
    assert payload["portal_submitted"] is False
    assert payload["approval_authority_added"] is False
    assert payload["runtime_authority_added"] is False


def test_partial_capture_records_only_supplied_value_and_preserves_pending(tmp_path):
    packet_path = _write_actionable_packet(tmp_path / "capital_hilton_actionable_review_packet.json")
    inputs = {
        "confirmations": {
            "recipient_confirmed": {"confirmed": True, "evidence_ref": "operator_manual_review:recipient_only"}
        }
    }

    payload = receipt.build_capital_hilton_manual_confirmation_receipt(
        actionable_packet_path=packet_path,
        confirmation_inputs=inputs,
        generated_at=FIXED_NOW,
    )

    assert payload["real_confirmations_recorded"] is True
    assert payload["recorded_confirmation_count"] == 1
    assert payload["pending_confirmation_count"] == len(receipt.SUPPORTED_CONFIRMATION_FIELDS) - 1
    assert payload["recorded_confirmation_keys"] == ["recipient_confirmed"]
    assert "po_coupa_requirement_confirmed" in payload["pending_confirmation_keys"]
    assert "include_2026_05_22" in payload["pending_confirmation_keys"]
    assert "include_older_gigs" in payload["pending_confirmation_keys"]
    assert payload["hard_blockers_cleared_by_receipt"] is False
    assert payload["packet_ready_after_confirmations"]["packet_ready_for_manual_preparation"] is False
    assert any(item["blocker_id"] == "po_coupa_confirmation_required" for item in payload["remaining_blocked_items"])


def test_false_confirmation_is_recorded_but_does_not_clear_blocker(tmp_path):
    packet_path = _write_actionable_packet(tmp_path / "capital_hilton_actionable_review_packet.json")
    inputs = {"confirmations": {"po_coupa_requirement_confirmed": False}}

    payload = receipt.build_capital_hilton_manual_confirmation_receipt(
        actionable_packet_path=packet_path,
        confirmation_inputs=inputs,
        generated_at=FIXED_NOW,
    )
    po_item = next(item for item in payload["confirmation_items"] if item["confirmation_key"] == "po_coupa_requirement_confirmed")
    po_blocker = next(item for item in payload["remaining_blocked_items"] if item["blocker_id"] == "po_coupa_confirmation_required")

    assert po_item["status"] == "recorded"
    assert po_item["confirmation_value"] is False
    assert po_item["operator_supplied"] is True
    assert po_item["confirmation_satisfied"] is False
    assert po_blocker["status"] == "explicit_negative_or_unsatisfied_confirmation_recorded"
    assert payload["hard_blockers_cleared_by_receipt"] is False
    assert payload["packet_ready_after_confirmations"]["packet_ready_for_submission"] is False


def test_credential_like_confirmation_values_are_redacted(tmp_path):
    packet_path = _write_actionable_packet(tmp_path / "capital_hilton_actionable_review_packet.json")
    inputs = {
        "confirmations": {
            "po_coupa_requirement_confirmed": {
                "confirmed": True,
                "value_label": "login is user@example.com and password is secret",
            }
        }
    }

    payload = receipt.build_capital_hilton_manual_confirmation_receipt(
        actionable_packet_path=packet_path,
        confirmation_inputs=inputs,
        generated_at=FIXED_NOW,
    )
    text = json.dumps(payload).lower()

    assert "password is" not in text
    assert "secret" not in text
    assert "[redacted credential-bearing confirmation value]" in text
    po_item = next(item for item in payload["confirmation_items"] if item["confirmation_key"] == "po_coupa_requirement_confirmed")
    assert po_item["confirmation_value"] is True


def test_read_model_output_is_deterministic(tmp_path):
    packet_path = _write_actionable_packet(tmp_path / "capital_hilton_actionable_review_packet.json")
    inputs = {"po_coupa_requirement_confirmed": True}

    first = receipt.build_capital_hilton_manual_confirmation_receipt(
        actionable_packet_path=packet_path,
        confirmation_inputs=inputs,
        generated_at=FIXED_NOW,
    )
    second = receipt.build_capital_hilton_manual_confirmation_receipt(
        actionable_packet_path=packet_path,
        confirmation_inputs=inputs,
        generated_at=FIXED_NOW,
    )

    assert receipt.stable_json(first) == receipt.stable_json(second)


def test_export_writes_json_operator_and_cli_outputs(tmp_path, capsys):
    packet_path = _write_actionable_packet(tmp_path / "capital_hilton_actionable_review_packet.json")
    export_root = tmp_path / "read_models"

    result = receipt.export_capital_hilton_manual_confirmation_receipt(
        actionable_packet_path=packet_path,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )
    payload = json.loads((export_root / receipt.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator_text = (export_root / receipt.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert result.real_confirmations_recorded is False
    assert payload["confirmation_contract"]["generalizable_to_other_review_packets"] is True
    assert "Capital Hilton Manual Confirmation Receipts" in operator_text
    assert "No operator confirmation values were supplied" in operator_text
    assert export_main(
        [
            "--actionable-packet-json",
            str(packet_path),
            "--export-root",
            str(export_root),
            "--format",
            "json",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["real_confirmations_recorded"] is False


def test_cli_confirmations_json_records_partial_capture(tmp_path, capsys):
    packet_path = _write_actionable_packet(tmp_path / "capital_hilton_actionable_review_packet.json")
    export_root = tmp_path / "read_models"
    confirmations_path = tmp_path / "confirmations.json"
    confirmations_path.write_text(
        json.dumps(
            {
                "confirmations": {
                    "recipient_confirmed": {
                        "confirmed": True,
                        "evidence_ref": "operator_manual_review:cli_partial",
                    }
                }
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    assert export_main(
        [
            "--actionable-packet-json",
            str(packet_path),
            "--confirmations-json",
            str(confirmations_path),
            "--export-root",
            str(export_root),
            "--format",
            "json",
        ]
    ) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((export_root / receipt.JSON_EXPORT_NAME).read_text(encoding="utf-8"))

    assert summary["real_confirmations_recorded"] is True
    assert payload["recorded_confirmation_keys"] == ["recipient_confirmed"]
    assert payload["pending_confirmation_count"] == len(receipt.SUPPORTED_CONFIRMATION_FIELDS) - 1
    assert payload["confirmation_contract"]["explicit_operator_values_required"] is True
    assert payload["confirmation_contract"]["client_specific_overlay"] == "hilton_coupa_supplier_portal"
    assert payload["confirmation_contract"]["two_invoice_workflow_contract"] == "capital_hilton_two_invoice_workflow_v0"
    assert (
        "Manual Coupa payment invoice"
        in payload["confirmation_contract"]["field_alignment"]["coupa_invoice_created_manually"]
    )


def test_generated_read_model_files_are_safe_mirror_candidates(tmp_path):
    packet_path = _write_actionable_packet(tmp_path / "capital_hilton_actionable_review_packet.json")
    export_root = tmp_path / "generated" / "read_models"
    receipt.export_capital_hilton_manual_confirmation_receipt(
        actionable_packet_path=packet_path,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))
    assert receipt.JSON_EXPORT_NAME in expected
    assert receipt.OPERATOR_EXPORT_NAME in expected


def test_source_does_not_execute_repo_b_send_submit_spreadsheet_or_subprocess():
    source_files = [
        Path("capital_hilton_manual_confirmation_receipt.py"),
        Path("scripts/export_capital_hilton_manual_confirmation_receipt.py"),
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
        "openpyxl",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in text

    tree = ast.parse(Path("capital_hilton_manual_confirmation_receipt.py").read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "subprocess" not in imported
