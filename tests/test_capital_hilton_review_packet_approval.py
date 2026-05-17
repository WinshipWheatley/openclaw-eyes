import json
from pathlib import Path

import capital_hilton_review_packet_approval as approval
from scripts.export_capital_hilton_review_packet_approval import main as export_main


FIXED_NOW = "2026-05-17T12:00:00+00:00"


def _packet(**overrides):
    payload = {
        "schema_version": "cassandra_clara_fact_packet_v0",
        "generated_at": FIXED_NOW,
        "target_workflow": "capital_hilton_invoice",
        "packet_id": "finance_packet_capital_hilton_invoice_v0",
        "source_policy": "imported_cassandra_chief_memory_sqlite_only",
        "packet_kind": "capital_hilton_review_packet",
        "usable_capital_hilton_review_packet": True,
        "missing_required_fact_count": 0,
        "governed_fact_count": 40,
        "contact_candidate_count": 4,
        "receivable_posture_count": 10,
        "required_fact_status": [
            {
                "field_name": "po_numbers",
                "display_name": "PO number(s) or explicit none",
                "present": True,
                "evidence_status": "parsed_evidence_not_truth",
                "trust_status": "needs_operator_confirmation",
            }
        ],
        "invoice_facts_used": [
            {
                "field_name": "po_numbers",
                "display_name": "PO number(s) or explicit none",
                "value_text": "po_numbers has imported structured evidence (sha256:test)",
                "fact_id": "fact_po",
                "source_kind": "governed_finance_invoice_packet",
                "source_ref": "sqlite://finance_invoice_packet_facts",
                "evidence_status": "parsed_evidence_not_truth",
                "trust_status": "needs_operator_confirmation",
                "no_send_authority": True,
                "no_runtime_authority": True,
                "approval_required": True,
            }
        ],
        "artifacts": {
            "draft_email": "generated/finance_packets/cassandra_clara_fact_packet_v0/CAPITAL_HILTON_CLARA_DRAFT_EMAIL_REVIEW_ONLY.md",
            "portal_instructions": "generated/finance_packets/cassandra_clara_fact_packet_v0/CAPITAL_HILTON_PORTAL_FILL_INSTRUCTIONS_REVIEW_ONLY.md",
        },
        "artifact_root": "generated/finance_packets/cassandra_clara_fact_packet_v0",
        "boundaries": {
            "email_send_allowed": False,
            "invoice_send_allowed": False,
            "supplier_portal_login_allowed": False,
            "browser_automation_allowed": False,
            "spreadsheet_cell_read_allowed": False,
            "workbook_parsing_allowed": False,
            "no_send_authority": True,
            "no_runtime_authority": True,
        },
        "raw_data_imported": False,
        "raw_private_files_read": False,
        "ad_hoc_notes_read": False,
        "raw_messages_read": False,
        "spreadsheet_cells_read": False,
        "old_hitl_read": False,
        "agent_presence_read": False,
        "send_authority_granted": False,
        "runtime_authority_changed": False,
    }
    payload.update(overrides)
    return payload


def test_review_packet_approval_records_manual_coupa_scope_without_authority():
    receipt = approval.build_capital_hilton_review_packet_approval(
        packet=_packet(),
        generated_at=FIXED_NOW,
    )

    assert receipt["schema_version"] == approval.SCHEMA_VERSION
    assert receipt["packet_approved_for_manual_review_preparation"] is True
    assert receipt["manual_coupa_review_preparation_allowed"] is True
    assert receipt["approval_scope"] == "manual_coupa_review_preparation_only"
    assert receipt["facts_came_from_imported_sqlite_memory_facts"] is True
    assert receipt["facts_source_policy"] == "imported_cassandra_chief_memory_sqlite_only"
    assert receipt["ad_hoc_memory_used"] is False
    assert receipt["po_coupa_confirmation_required"] is True
    assert receipt["po_coupa_confirmation_gate"]["final_submission_allowed"] is False
    assert receipt["recipient_email_posture"]["email_send_allowed"] is False
    assert receipt["email_sent"] is False
    assert receipt["portal_submitted"] is False
    assert receipt["credentials_accessed"] is False
    assert receipt["spreadsheet_cells_read"] is False
    assert receipt["runtime_authority_changed"] is False
    assert receipt["send_authority_granted"] is False
    assert receipt["edits_needed_before_approval"] == []


def test_receipt_surfaces_exact_edits_if_packet_is_not_approval_ready():
    receipt = approval.build_capital_hilton_review_packet_approval(
        packet=_packet(
            source_policy="ad_hoc_legacy_memory",
            usable_capital_hilton_review_packet=False,
            missing_required_fact_count=2,
        ),
        generated_at=FIXED_NOW,
    )

    assert receipt["packet_approved_for_manual_review_preparation"] is False
    assert receipt["manual_coupa_review_preparation_allowed"] is False
    assert receipt["facts_came_from_imported_sqlite_memory_facts"] is False
    assert any("source_policy" in item for item in receipt["edits_needed_before_approval"])
    assert any("usable_capital_hilton_review_packet" in item for item in receipt["edits_needed_before_approval"])
    assert any("missing_required_fact_count" in item for item in receipt["edits_needed_before_approval"])


def test_receipt_rejects_facts_that_claim_truth_or_authority():
    receipt = approval.build_capital_hilton_review_packet_approval(
        packet=_packet(
            invoice_facts_used=[
                {
                    "field_name": "po_numbers",
                    "evidence_status": "operator_confirmed_truth",
                    "trust_status": "confirmed",
                    "no_send_authority": False,
                    "no_runtime_authority": False,
                }
            ]
        ),
        generated_at=FIXED_NOW,
    )

    assert receipt["packet_approved_for_manual_review_preparation"] is False
    joined = "\n".join(receipt["edits_needed_before_approval"])
    assert "parsed evidence" in joined
    assert "operator confirmation" in joined
    assert "send authority" in joined
    assert "runtime authority" in joined


def test_operator_markdown_keeps_email_portal_credentials_and_spreadsheets_blocked():
    receipt = approval.build_capital_hilton_review_packet_approval(
        packet=_packet(),
        generated_at=FIXED_NOW,
    )
    rendered = approval.format_capital_hilton_review_packet_approval(receipt)

    assert "Approved for manual Coupa review preparation: `true`" in rendered
    assert "PO must still be confirmed in Coupa before any final submission." in rendered
    assert "No email send is authorized" in rendered
    assert "`credential_access`" in rendered
    assert "`spreadsheet_cell_read`" in rendered
    assert "None for manual review preparation." in rendered


def test_export_writes_valid_json_and_operator_outputs(tmp_path):
    packet_path = tmp_path / "cassandra_clara_fact_packet.json"
    packet_path.write_text(json.dumps(_packet()), encoding="utf-8")
    export_root = tmp_path / "read_models"

    result = approval.export_capital_hilton_review_packet_approval(
        packet_path=packet_path,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )

    assert result.packet_approved_for_manual_review_preparation is True
    payload = json.loads((export_root / approval.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / approval.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    assert payload["approval_receipt_id"] == result.approval_receipt_id
    assert payload["email_sent"] is False
    assert payload["portal_submitted"] is False
    assert payload["credentials_accessed"] is False
    assert payload["spreadsheet_cells_read"] is False
    assert "Capital Hilton Review Packet Approval v0" in operator

    assert export_main(
        [
            "--packet-json",
            str(packet_path),
            "--export-root",
            str(export_root),
            "--format",
            "json",
        ]
    ) == 0


def test_receipt_surface_does_not_import_repo_b_or_use_network_send_subprocess():
    source_files = [
        Path("capital_hilton_review_packet_approval.py"),
        Path("scripts/export_capital_hilton_review_packet_approval.py"),
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
        "eval(",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token.lower() not in text
