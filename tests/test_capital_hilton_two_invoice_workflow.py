import ast
import json
from pathlib import Path

import capital_hilton_two_invoice_workflow as workflow
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_capital_hilton_two_invoice_workflow import main as export_main


FIXED_NOW = "2026-05-17T19:30:00+00:00"


def _write_actionable_packet(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "capital_hilton_actionable_review_packet_v1",
                "packet_id": "finance_capital_hilton_invoice_packet_v0",
                "review_only": True,
                "ready_for_submission": False,
                "review_calculation": {
                    "known_completed_service_dates": ["2026-05-08", "2026-05-15"],
                    "rate_or_amount_per_gig": "$400 per gig",
                    "candidate_subtotal": "$800 for the two completed governed service-date facts",
                },
                "invoice_facts": [
                    {
                        "field_name": "invoice_count_preference",
                        "value_text": "one invoice for 2026-05-15 and 2026-05-08",
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_confirmation_receipt(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "capital_hilton_manual_confirmation_receipt_v0",
                "recorded_confirmation_count": 0,
                "pending_confirmation_count": 6,
                "real_confirmations_recorded": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_base_workflow_is_separate_from_hilton_specific_overlay(tmp_path):
    actionable = _write_actionable_packet(tmp_path / "capital_hilton_actionable_review_packet.json")
    receipt = _write_confirmation_receipt(tmp_path / "capital_hilton_manual_confirmation_receipt.json")

    payload = workflow.build_capital_hilton_two_invoice_workflow(
        actionable_packet_path=actionable,
        confirmation_receipt_path=receipt,
        generated_at=FIXED_NOW,
    )

    assert payload["schema_version"] == workflow.SCHEMA_VERSION
    assert payload["base_invoice_workflow"]["workflow_id"] == "base_invoice_workflow"
    assert payload["base_invoice_workflow"]["applies_to_all_clients"] is True
    assert payload["base_invoice_workflow"]["portal_overlay_is_default"] is False
    assert payload["client_specific_invoice_overlay"]["overlay_id"] == "hilton_coupa_supplier_portal"
    assert payload["client_specific_invoice_overlay"]["applies_to_all_clients"] is False
    assert payload["client_specific_invoice_overlay"]["generalized_to_all_clients"] is False
    assert payload["status_summary"]["hilton_two_invoice_flow_generalized_to_all_clients"] is False


def test_coupa_and_excel_invoice_artifacts_are_distinct(tmp_path):
    payload = workflow.build_capital_hilton_two_invoice_workflow(
        actionable_packet_path=_write_actionable_packet(tmp_path / "actionable.json"),
        confirmation_receipt_path=_write_confirmation_receipt(tmp_path / "receipt.json"),
        generated_at=FIXED_NOW,
    )
    artifacts = {item["artifact_type"]: item for item in payload["invoice_artifacts"]}

    assert set(artifacts) == {"coupa_payment_invoice", "excel_companion_invoice"}
    assert artifacts["coupa_payment_invoice"]["artifact_role"] == "payment_generating_invoice"
    assert artifacts["excel_companion_invoice"]["artifact_role"] == "companion_communication_reference_invoice"
    assert artifacts["excel_companion_invoice"]["payment_generating_for_hilton"] is False
    assert artifacts["coupa_payment_invoice"]["openclaw_submit_allowed"] is False


def test_payment_ready_depends_on_coupa_proof_not_excel_alone_and_paid_depends_on_money_ledger(tmp_path):
    payload = workflow.build_capital_hilton_two_invoice_workflow(
        actionable_packet_path=_write_actionable_packet(tmp_path / "actionable.json"),
        confirmation_receipt_path=_write_confirmation_receipt(tmp_path / "receipt.json"),
        generated_at=FIXED_NOW,
    )

    assert payload["payment_readiness"]["payment_ready"] is False
    assert payload["payment_readiness"]["excel_companion_invoice_alone_is_payment_ready"] is False
    assert "Coupa payment invoice created manually" in payload["payment_readiness"]["payment_ready_requires"]
    assert payload["payment_readiness"]["paid_verified"] is False
    assert payload["payment_readiness"]["paid_verified_requires"] == "money_ledger_payment_confirmation"
    assert payload["payment_marked_paid"] is False


def test_po_budget_context_is_evidence_not_final_accounting_truth(tmp_path):
    payload = workflow.build_capital_hilton_two_invoice_workflow(
        actionable_packet_path=_write_actionable_packet(tmp_path / "actionable.json"),
        confirmation_receipt_path=_write_confirmation_receipt(tmp_path / "receipt.json"),
        generated_at=FIXED_NOW,
    )
    po = payload["po_budget_context"]

    assert po["po_number"] == "DCASH00983536"
    assert po["total_po_amount"]["amount_text"] == "4000.00 USD"
    assert po["invoiced_to_date"]["amount_text"] == "2000.00 USD"
    assert po["apparent_remaining_amount"]["amount_text"] == "2000.00 USD"
    assert po["context_status"] == "screenshot_confirmed_evidence_not_final_accounting_truth"
    assert po["final_accounting_truth_claimed"] is False


def test_protected_evidence_slots_do_not_store_raw_blobs_or_secrets(tmp_path):
    payload = workflow.build_capital_hilton_two_invoice_workflow(
        actionable_packet_path=_write_actionable_packet(tmp_path / "actionable.json"),
        confirmation_receipt_path=_write_confirmation_receipt(tmp_path / "receipt.json"),
        generated_at=FIXED_NOW,
    )
    text = json.dumps(payload).lower()

    assert payload["protected_evidence_slots"]
    assert all(slot["raw_blob_stored_in_read_model"] is False for slot in payload["protected_evidence_slots"])
    assert payload["raw_pii_or_secret_stored"] is False
    assert payload["home_address_stored"] is False
    assert payload["bank_details_stored"] is False
    assert payload["portal_password_stored"] is False
    assert payload["token_material_stored"] is False
    assert payload["check_image_stored"] is False
    assert "@hilton.com" not in text
    assert "password is" not in text
    assert "token=" not in text
    assert "1009 smithville" not in text


def test_no_send_submit_spreadsheet_browser_runtime_authority_is_added(tmp_path):
    payload = workflow.build_capital_hilton_two_invoice_workflow(
        actionable_packet_path=_write_actionable_packet(tmp_path / "actionable.json"),
        confirmation_receipt_path=_write_confirmation_receipt(tmp_path / "receipt.json"),
        generated_at=FIXED_NOW,
    )

    for key in workflow.NO_AUTHORITY_FLAGS:
        expected = workflow.NO_AUTHORITY_FLAGS[key]
        assert payload[key] is expected
        assert payload["boundaries"][key] is expected
    assert payload["coupa_submit_triggered"] is False
    assert payload["email_send_triggered"] is False
    assert payload["spreadsheet_write_triggered"] is False
    assert payload["browser_automation_added"] is False
    assert payload["runtime_authority_added"] is False


def test_old_one_invoice_packet_fact_remains_compatible_but_not_payment_generating_for_excel(tmp_path):
    payload = workflow.build_capital_hilton_two_invoice_workflow(
        actionable_packet_path=_write_actionable_packet(tmp_path / "actionable.json"),
        confirmation_receipt_path=_write_confirmation_receipt(tmp_path / "receipt.json"),
        generated_at=FIXED_NOW,
    )
    compatibility = payload["legacy_one_invoice_packet_compatibility"]

    assert compatibility["old_one_invoice_packet_fact_preserved"] is True
    assert "one invoice" in compatibility["old_one_invoice_packet_fact_value"]
    assert compatibility["does_not_make_excel_payment_generating_for_hilton"] is True


def test_manual_confirmation_receipt_alignment_is_present(tmp_path):
    payload = workflow.build_capital_hilton_two_invoice_workflow(
        actionable_packet_path=_write_actionable_packet(tmp_path / "actionable.json"),
        confirmation_receipt_path=_write_confirmation_receipt(tmp_path / "receipt.json"),
        generated_at=FIXED_NOW,
    )
    alignment = payload["manual_confirmation_alignment"]

    assert alignment["receipt_model"] == "capital_hilton_manual_confirmation_receipt_v0"
    assert "coupa_invoice_created_manually" in alignment["field_alignment"]
    assert "Excel companion" in alignment["field_alignment"]["spreadsheet_invoice_number_checked"]
    assert alignment["confirmations_do_not_create_external_action_authority"] is True


def test_export_writes_valid_json_operator_and_cli_outputs(tmp_path, capsys):
    actionable = _write_actionable_packet(tmp_path / "capital_hilton_actionable_review_packet.json")
    receipt = _write_confirmation_receipt(tmp_path / "capital_hilton_manual_confirmation_receipt.json")
    export_root = tmp_path / "read_models"

    result = workflow.export_capital_hilton_two_invoice_workflow(
        actionable_packet_path=actionable,
        confirmation_receipt_path=receipt,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )
    payload = json.loads((export_root / workflow.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator_text = (export_root / workflow.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert result.hilton_coupa_overlay_modeled is True
    assert payload["status_summary"]["base_invoice_workflow_preserved"] is True
    assert "Capital Hilton Two-Invoice Workflow" in operator_text
    assert "Coupa payment invoice" in operator_text
    assert export_main(
        [
            "--actionable-packet-json",
            str(actionable),
            "--confirmation-receipt-json",
            str(receipt),
            "--export-root",
            str(export_root),
            "--format",
            "json",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["coupa_payment_invoice_modeled"] is True


def test_generated_read_model_files_are_safe_mirror_candidates(tmp_path):
    export_root = tmp_path / "generated" / "read_models"
    workflow.export_capital_hilton_two_invoice_workflow(
        actionable_packet_path=_write_actionable_packet(tmp_path / "actionable.json"),
        confirmation_receipt_path=_write_confirmation_receipt(tmp_path / "receipt.json"),
        export_root=export_root,
        generated_at=FIXED_NOW,
    )

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))
    assert workflow.JSON_EXPORT_NAME in expected
    assert workflow.OPERATOR_EXPORT_NAME in expected


def test_sources_do_not_execute_repo_b_send_submit_browser_or_subprocess():
    source_files = [
        Path("capital_hilton_two_invoice_workflow.py"),
        Path("scripts/export_capital_hilton_two_invoice_workflow.py"),
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

    tree = ast.parse(Path("capital_hilton_two_invoice_workflow.py").read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "subprocess" not in imported
