import json
import sqlite3
from pathlib import Path

import cassandra_governed_review_packet_request as proof
from capital_hilton_finance_fact_intake import init_capital_hilton_fact_intake_schema
from capital_hilton_invoice_packet import CAPITAL_HILTON_PACKET_ID
from cassandra_chief_memory_authority import build_cassandra_chief_structured_import_plan
from cassandra_chief_memory_import_approval import build_cassandra_chief_memory_import_approval
from cassandra_chief_structured_fact_import import apply_structured_fact_import
from cassandra_clara_fact_packet import REQUIRED_FIELDS


FIXED_NOW = "2026-05-17T14:00:00+00:00"


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _init_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "ledger.sqlite"
    init_capital_hilton_fact_intake_schema(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
INSERT OR REPLACE INTO finance_invoice_packets (
  packet_id, run_id, title, subject_entity, workflow_kind, status,
  agent_lane, source_basis, next_safe_move, created_at, updated_at,
  financial_truth_claimed, send_allowed, bank_access_allowed, ledger_write_allowed,
  tax_filing_allowed
) VALUES (?, 'test_run', 'Capital Hilton governed proof packet',
  'Capital Hilton / Capitol Hilton', 'invoice_prep', 'review_only',
  'cassandra', 'test_sqlite_governed_fact', 'manual Coupa PO confirmation',
  ?, ?, 0, 0, 0, 0, 0)
""".strip(),
            (CAPITAL_HILTON_PACKET_ID, FIXED_NOW, FIXED_NOW),
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


def _insert_fact(db_path: Path, field_name: str, value_text: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
INSERT OR REPLACE INTO capital_hilton_invoice_fact_updates (
  fact_update_id, packet_id, source_kind, source_ref, agent_internal,
  external_persona, field_name, value_text, confidence, truth_status,
  financial_truth_claimed, raw_sensitive_body_stored, created_at
) VALUES (?, ?, 'sqlite_test_fact', 'test://governed_sqlite_fact',
  'cassandra', 'Clara Reid', ?, ?, 'operator_claim', 'unverified_claim', 0, 0, ?)
""".strip(),
            (f"capfact_{field_name}", CAPITAL_HILTON_PACKET_ID, field_name, value_text, FIXED_NOW),
        )
        conn.execute(
            """
INSERT OR REPLACE INTO finance_invoice_packet_facts (
  fact_id, packet_id, fact_kind, label, value_text, amount_value,
  currency, date_or_period, confidence, truth_status, source_ref,
  no_raw_sensitive_body, financial_truth_claimed, created_at
) VALUES (?, ?, 'approved_evidence_reference', ?, ?, NULL, NULL, NULL,
  'operator_claim', 'unverified_claim', 'test://governed_sqlite_fact', 1, 0, ?)
""".strip(),
            (f"finfact_{field_name}", CAPITAL_HILTON_PACKET_ID, field_name, value_text, FIXED_NOW),
        )
        conn.commit()
    finally:
        conn.close()


def _seed_capital_hilton_facts(db_path: Path) -> None:
    values = {
        "tonight_gig_date": "2026-05-15 (operator said this was yesterday relative to May 16, 2026)",
        "last_friday_gig_date": "2026-05-08",
        "rate_or_amount_per_gig": "$400 per gig",
        "invoice_count_preference": "one invoice for 2026-05-15 and 2026-05-08; 2026-05-22 and older gigs blocked until operator confirms inclusion",
        "po_numbers": "unknown; PO must be confirmed in Coupa later; no portal login authorized",
        "billing_remit_details": "mail check to operator home address provided in prompt; full street address redacted from committed artifacts",
        "recipient_decision": "To: Annette Sunga; CC: operator email, Chyna Hardin, Lawrence/Will Valcovic; no send authority",
        "supplier_portal_reference": "Coupa supplier portal reference provided by operator; credential use/storage not authorized",
        "invoice_attachment_output_path": "invoice must be created in Coupa against confirmed PO; no spreadsheet cells read",
        "spreadsheet_selection": "Invoice Capitol Hilton 20260512 v2.xlsx",
    }
    for field_name, value_text in values.items():
        _insert_fact(db_path, field_name, value_text)


def _memory_approval(tmp_path: Path) -> Path:
    proof_payload = {
        "safe_to_import_cassandra_chief_memory": True,
        "runtime_authority_changed": False,
        "caller_switched": False,
        "old_hitl_deleted": False,
        "raw_payload_stored": False,
        "callback_decision_shadow_support": True,
    }
    payload = build_cassandra_chief_memory_import_approval(
        structured_import_plan=build_cassandra_chief_structured_import_plan(generated_at=FIXED_NOW),
        hitl_proof=proof_payload,
        generated_at=FIXED_NOW,
    )
    return _write_json(tmp_path / "memory_import_approval.json", payload)


def _contact_file(tmp_path: Path) -> Path:
    return _write_json(
        tmp_path / "contact_nicknames.json",
        {
            "annette_sunga": {
                "name": "Annette Sunga",
                "aliases": ["Annette"],
                "pinned_email": "annette@example.invalid",
                "tier": "finance_contact",
            }
        },
    )


def _finance_state_file(tmp_path: Path) -> Path:
    return _write_json(
        tmp_path / "finance_state.json",
        {
            "schema_version": 1,
            "accounts": {
                "capital_hilton": {
                    "label": "Capital Hilton",
                    "status": "open",
                    "workflow_summary": "Synthetic governed proof workflow",
                    "payment_summary": "Synthetic governed proof payment",
                    "invoice_summary": "Synthetic governed proof invoice",
                    "next_actions": ["Confirm Coupa PO manually"],
                }
            },
        },
    )


def _status_dry_run(tmp_path: Path) -> Path:
    return _write_json(
        tmp_path / "cassandra_send_status_dry_run.json",
        {
            "schema_version": "cassandra_send_status_dry_run_v0",
            "services": {
                "watcher": {"advanced_beyond_startup_guard": True},
                "briefing_scheduler": {"advanced_beyond_startup_guard": True},
            },
            "real_telegram_send_triggered": False,
            "real_gmail_or_email_send_triggered": False,
            "real_briefing_delivery_triggered": False,
            "real_voice_delivery_triggered": False,
            "send_authority_added": False,
            "niles_used_for_cassandra_path": False,
        },
    )


def _approval_file(tmp_path: Path) -> Path:
    return _write_json(
        tmp_path / "capital_hilton_review_packet_approval.json",
        {
            "schema_version": "capital_hilton_review_packet_approval_v0",
            "packet_approved_for_manual_review_preparation": True,
        },
    )


def _setup(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    db_path = _init_db(tmp_path)
    _seed_capital_hilton_facts(db_path)
    memory_approval = _memory_approval(tmp_path)
    structured_import = apply_structured_fact_import(
        db_path=db_path,
        contact_nicknames_path=_contact_file(tmp_path),
        finance_state_path=_finance_state_file(tmp_path),
        approval_path=memory_approval,
        export_root=tmp_path / "structured_import",
        generated_at=FIXED_NOW,
    )
    structured_import_path = _write_json(tmp_path / "cassandra_chief_structured_fact_import.json", structured_import)
    return db_path, memory_approval, structured_import_path, _status_dry_run(tmp_path)


def test_governed_request_refreshes_review_packet_and_emits_receipt(tmp_path):
    db_path, memory_approval, structured_import, status_path = _setup(tmp_path)
    export_root = tmp_path / "read_models"
    artifact_root = tmp_path / "artifacts"
    approval = _approval_file(tmp_path)

    payload = proof.build_governed_review_packet_request_proof(
        db_path=db_path,
        export_root=export_root,
        artifact_root=artifact_root,
        status_dry_run_path=status_path,
        structured_fact_import_path=structured_import,
        memory_approval_path=memory_approval,
        approval_path=approval,
        generated_at=FIXED_NOW,
    )

    assert payload["schema_version"] == proof.SCHEMA_VERSION
    assert payload["prior_lane_status"]["advanced_beyond_startup_guard"] is True
    assert payload["route"]["selected_route"] == "cassandra_clara_capital_hilton_review_packet"
    assert payload["capital_hilton_packet_ready_for_operator_review"] is True
    assert payload["packet_review_only"] is True
    assert payload["used_ad_hoc_memory_as_authority"] is False
    assert payload["telegram_send_triggered"] is False
    assert payload["gmail_reply_sent"] is False
    assert payload["portal_submitted"] is False
    assert payload["runtime_execution_triggered"] is False
    assert payload["send_authority_added"] is False
    assert payload["capital_hilton_fact_summary"]["completed_service_dates"] == [
        "2026-05-08",
        "2026-05-15 (operator said this was yesterday relative to May 16, 2026)",
    ]
    assert "$400" in payload["capital_hilton_fact_summary"]["rate_or_amount_per_gig"]
    assert "$800" in payload["capital_hilton_fact_summary"]["review_subtotal"]
    assert any(item["blocker_id"] == "po_coupa_confirmation_required" for item in payload["blocked_or_manual_confirmation"])
    assert (artifact_root / "CAPITAL_HILTON_CLARA_DRAFT_EMAIL_REVIEW_ONLY.md").exists()


def test_export_writes_json_operator_and_keeps_boundaries(tmp_path):
    db_path, memory_approval, structured_import, status_path = _setup(tmp_path)
    export_root = tmp_path / "read_models"
    artifact_root = tmp_path / "artifacts"
    approval = _approval_file(tmp_path)

    paths = proof.export_governed_review_packet_request_proof(
        db_path=db_path,
        export_root=export_root,
        artifact_root=artifact_root,
        status_dry_run_path=status_path,
        structured_fact_import_path=structured_import,
        memory_approval_path=memory_approval,
        approval_path=approval,
        generated_at=FIXED_NOW,
    )
    payload = json.loads((export_root / proof.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / proof.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert paths["json"].endswith(proof.JSON_EXPORT_NAME)
    assert payload["email_sent"] is False
    assert payload["portal_submitted"] is False
    assert payload["credentials_accessed"] is False
    assert payload["spreadsheet_cells_read"] is False
    assert payload["repo_b_executed"] is False
    assert "Cassandra Governed Request -> Review Packet Proof" in operator
    assert "No Telegram send" in operator


def test_source_avoids_network_send_portal_and_repo_b_execution():
    source = Path("cassandra_governed_review_packet_request.py").read_text(encoding="utf-8").lower()
    forbidden = [
        "/home/openclaw_external/openclaw-runtime",
        "import requests",
        "import httpx",
        "urllib.request",
        "subprocess",
        "smtplib",
        "send_message",
        "reply_text",
        "portal_submit(",
        "browser",
        "shell=true",
    ]
    for token in forbidden:
        assert token not in source
