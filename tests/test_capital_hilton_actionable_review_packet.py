import json
import sqlite3
from pathlib import Path

import capital_hilton_actionable_review_packet as packet
from capital_hilton_finance_fact_intake import init_capital_hilton_fact_intake_schema
from capital_hilton_invoice_packet import CAPITAL_HILTON_PACKET_ID
from scripts.export_capital_hilton_actionable_review_packet import main as export_main


FIXED_NOW = "2026-05-17T12:00:00+00:00"


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _db(tmp_path: Path, *, complete: bool = True, credential_value: bool = False) -> Path:
    db_path = tmp_path / "ledger.sqlite"
    init_capital_hilton_fact_intake_schema(db_path)
    values = {
        "tonight_gig_date": "2026-05-15 (operator said this was yesterday relative to May 16, 2026)",
        "last_friday_gig_date": "2026-05-08",
        "rate_or_amount_per_gig": "$400 per gig",
        "invoice_count_preference": "one invoice for 2026-05-15 and 2026-05-08; operator also wants 2026-05-22 upcoming gig and older gigs reviewed for inclusion if applicable",
        "po_numbers": "unknown; PO must be confirmed in Coupa later; no portal login authorized",
        "billing_remit_details": "mail check to operator home address provided in prompt; full street address redacted from committed artifacts",
        "recipient_decision": "To: Annette Sunga (business email pending confirmation); CC: operator email, Chyna Hardin, Lawrence/Will Valcovic; no send authority",
        "supplier_portal_reference": "Coupa supplier portal reference provided by operator; credential use/storage not authorized",
        "invoice_attachment_output_path": "invoice must be created in Coupa against confirmed PO; existing Mac Documents/invoices spreadsheet is metadata-only source workbook; no spreadsheet cells read",
        "spreadsheet_selection": "Invoice Capitol Hilton 20260512 v2.xlsx",
        "contact_candidate_annette_sunga": "Annette Sunga | Finance/AP contact | email=Annette.Sunga@hilton.com | allowed_use=to_candidate_pending_review",
    }
    if not complete:
        values.pop("po_numbers")
    if credential_value:
        values["supplier_portal_reference"] = "login is user@example.com and password is secret"
    conn = sqlite3.connect(db_path)
    try:
        for field, value in values.items():
            conn.execute(
                """
INSERT OR REPLACE INTO capital_hilton_invoice_fact_updates (
  fact_update_id, packet_id, source_kind, source_ref, agent_internal,
  external_persona, field_name, value_text, confidence, truth_status,
  financial_truth_claimed, raw_sensitive_body_stored, created_at
) VALUES (?, ?, 'operator_prompt', 'test://operator', 'cassandra',
  'Clara Reid', ?, ?, 'operator_claim', 'unverified_claim', 0, 0, ?)
""".strip(),
                (f"capfact_{field}", CAPITAL_HILTON_PACKET_ID, field, value, FIXED_NOW),
            )
            conn.execute(
                """
INSERT OR REPLACE INTO finance_invoice_packet_facts (
  fact_id, packet_id, fact_kind, label, value_text, amount_value,
  currency, date_or_period, confidence, truth_status, source_ref,
  no_raw_sensitive_body, financial_truth_claimed, created_at
) VALUES (?, ?, 'operator_claim', ?, ?, NULL, NULL, NULL,
  'operator_claim', 'unverified_claim', 'test://operator', 1, 0, ?)
""".strip(),
                (f"finfact_{field}", CAPITAL_HILTON_PACKET_ID, field, value, FIXED_NOW),
            )
        conn.commit()
    finally:
        conn.close()
    return db_path


def _source_packets(tmp_path: Path, *, usable: bool = True, approved: bool = True) -> tuple[Path, Path]:
    fact_packet = _write_json(
        tmp_path / "cassandra_clara_fact_packet.json",
        {
            "schema_version": "cassandra_clara_fact_packet_v0",
            "target_workflow": "capital_hilton_invoice",
            "packet_kind": "capital_hilton_review_packet" if usable else "capital_hilton_missing_facts_packet",
            "usable_capital_hilton_review_packet": usable,
            "source_policy": "imported_cassandra_chief_memory_sqlite_only",
        },
    )
    approval = _write_json(
        tmp_path / "capital_hilton_review_packet_approval.json",
        {
            "schema_version": "capital_hilton_review_packet_approval_v0",
            "packet_approved_for_manual_review_preparation": approved,
        },
    )
    return fact_packet, approval


def test_actionable_packet_uses_governed_facts_and_keeps_authority_blocked(tmp_path):
    db_path = _db(tmp_path)
    fact_packet, approval = _source_packets(tmp_path)

    payload = packet.build_capital_hilton_actionable_review_packet(
        db_path=db_path,
        fact_packet_path=fact_packet,
        approval_path=approval,
        generated_at=FIXED_NOW,
    )

    assert payload["schema_version"] == packet.SCHEMA_VERSION
    assert payload["actionable_for_manual_review"] is True
    assert payload["ready_for_submission"] is False
    assert payload["missing_required_fact_count"] == 0
    assert payload["email_sent"] is False
    assert payload["portal_submitted"] is False
    assert payload["credentials_accessed"] is False
    assert payload["spreadsheet_cells_read"] is False
    assert payload["runtime_authority_changed"] is False
    assert payload["send_authority_granted"] is False
    assert any(fact["field_name"] == "rate_or_amount_per_gig" and "$400" in fact["value_text"] for fact in payload["invoice_facts"])
    assert payload["review_calculation"]["candidate_subtotal"].startswith("$800")
    assert any(blocker["blocker_id"] == "po_coupa_confirmation_required" for blocker in payload["remaining_blockers"])
    assert any("Do not access" in item for item in payload["what_not_to_do"])


def test_missing_required_fact_produces_checklist_instead_of_guessing(tmp_path):
    db_path = _db(tmp_path, complete=False)
    fact_packet, approval = _source_packets(tmp_path, usable=False)

    payload = packet.build_capital_hilton_actionable_review_packet(
        db_path=db_path,
        fact_packet_path=fact_packet,
        approval_path=approval,
        generated_at=FIXED_NOW,
    )

    assert payload["actionable_for_manual_review"] is False
    assert payload["missing_required_fact_count"] == 1
    assert any(blocker["blocker_id"] == "missing_po_numbers" for blocker in payload["remaining_blockers"])
    rendered = packet.format_capital_hilton_actionable_review_packet(payload)
    assert "PO number(s) or explicit none: MISSING" in rendered
    assert "Do not submit" in rendered


def test_credential_bearing_values_are_redacted(tmp_path):
    db_path = _db(tmp_path, credential_value=True)
    fact_packet, approval = _source_packets(tmp_path)

    payload = packet.build_capital_hilton_actionable_review_packet(
        db_path=db_path,
        fact_packet_path=fact_packet,
        approval_path=approval,
        generated_at=FIXED_NOW,
    )
    supplier = next(fact for fact in payload["invoice_facts"] if fact["field_name"] == "supplier_portal_reference")
    rendered = packet.format_capital_hilton_actionable_review_packet(payload)

    assert "secret" not in json.dumps(payload).lower()
    assert "password is" not in rendered.lower()
    assert supplier["value_text"].startswith("[REDACTED credential-bearing value")


def test_export_writes_json_operator_and_cli_outputs(tmp_path, capsys):
    db_path = _db(tmp_path)
    fact_packet, approval = _source_packets(tmp_path)
    export_root = tmp_path / "read_models"

    result = packet.export_capital_hilton_actionable_review_packet(
        db_path=db_path,
        fact_packet_path=fact_packet,
        approval_path=approval,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )
    payload = json.loads((export_root / packet.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / packet.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert result.actionable_for_manual_review is True
    assert payload["boundaries"]["email_send_allowed"] is False
    assert "Capital Hilton Actionable Review Packet v1" in operator
    assert "Exact Manual Steps" in operator
    assert export_main(
        [
            "--db",
            str(db_path),
            "--fact-packet-json",
            str(fact_packet),
            "--approval-json",
            str(approval),
            "--export-root",
            str(export_root),
            "--format",
            "json",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["actionable_for_manual_review"] is True


def test_source_does_not_import_repo_b_network_send_or_subprocess():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "capital_hilton_actionable_review_packet.py",
            "scripts/export_capital_hilton_actionable_review_packet.py",
        ]
    )
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
    for token in forbidden:
        assert token not in source
