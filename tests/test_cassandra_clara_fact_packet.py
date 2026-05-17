import json
import sqlite3
from pathlib import Path

import cassandra_clara_fact_packet as packet
from capital_hilton_invoice_packet import CAPITAL_HILTON_PACKET_ID
from capital_hilton_finance_fact_intake import init_capital_hilton_fact_intake_schema
from cassandra_chief_memory_authority import build_cassandra_chief_structured_import_plan
from cassandra_chief_memory_import_approval import build_cassandra_chief_memory_import_approval
from cassandra_chief_structured_fact_import import apply_structured_fact_import


FIXED_NOW = "2026-05-16T12:00:00+00:00"


def _id(prefix: str, value: str) -> str:
    return f"{prefix}_{abs(hash(value))}"


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
) VALUES (?, 'test_run', 'Capital Hilton test packet',
  'Capital Hilton / Capitol Hilton', 'invoice_prep', 'blocked_missing_info',
  'cassandra', 'test_sqlite_governed_fact', 'collect missing facts',
  ?, ?, 0, 0, 0, 0, 0)
""".strip(),
            (CAPITAL_HILTON_PACKET_ID, FIXED_NOW, FIXED_NOW),
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


def _insert_fact(db_path: Path, field_name: str, value_text: str, truth_status: str = "operator_confirmed") -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
INSERT OR REPLACE INTO capital_hilton_invoice_fact_updates (
  fact_update_id, packet_id, source_kind, source_ref, agent_internal,
  external_persona, field_name, value_text, confidence, truth_status,
  financial_truth_claimed, raw_sensitive_body_stored, created_at
) VALUES (?, ?, 'sqlite_test_fact', 'test://governed_sqlite_fact',
  'cassandra', 'Clara Reid', ?, ?, 'operator_claim', ?, 0, 0, ?)
""".strip(),
            (
                _id("capfact", field_name + value_text),
                CAPITAL_HILTON_PACKET_ID,
                field_name,
                value_text,
                truth_status,
                FIXED_NOW,
            ),
        )
        conn.execute(
            """
INSERT OR REPLACE INTO finance_invoice_packet_facts (
  fact_id, packet_id, fact_kind, label, value_text, amount_value,
  currency, date_or_period, confidence, truth_status, source_ref,
  no_raw_sensitive_body, financial_truth_claimed, created_at
) VALUES (?, ?, 'approved_evidence_reference', ?, ?, NULL, NULL, NULL,
  'operator_claim', ?, 'test://governed_sqlite_fact', 1, 0, ?)
""".strip(),
            (
                _id("finfact", field_name + value_text),
                CAPITAL_HILTON_PACKET_ID,
                field_name,
                value_text,
                truth_status,
                FIXED_NOW,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _insert_contact(db_path: Path, name: str = "Annette Sunga") -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
INSERT OR REPLACE INTO capital_hilton_contact_candidates (
  contact_candidate_id, packet_id, organization, contact_name, role, email,
  confidence, source_basis, allowed_use, external_send_allowed,
  operator_approval_required, verified, created_at, updated_at
) VALUES (?, ?, 'Capital Hilton / Capitol Hilton', ?, 'Finance/AP contact',
  NULL, 'operator_supplied_candidate', 'test://governed_sqlite_fact',
  'email_draft_recipient_candidate_needs_email_review', 0, 1, 0, ?, ?)
""".strip(),
            (_id("contact", name), CAPITAL_HILTON_PACKET_ID, name, FIXED_NOW, FIXED_NOW),
        )
        conn.commit()
    finally:
        conn.close()


def _approval_file(tmp_path: Path) -> Path:
    proof = {
        "safe_to_import_cassandra_chief_memory": True,
        "runtime_authority_changed": False,
        "caller_switched": False,
        "old_hitl_deleted": False,
        "raw_payload_stored": False,
        "callback_decision_shadow_support": True,
    }
    payload = build_cassandra_chief_memory_import_approval(
        structured_import_plan=build_cassandra_chief_structured_import_plan(generated_at=FIXED_NOW),
        hitl_proof=proof,
        generated_at=FIXED_NOW,
    )
    path = tmp_path / "memory_import_approval.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _contact_file(tmp_path: Path) -> Path:
    path = tmp_path / "contact_nicknames.json"
    path.write_text(
        json.dumps(
            {
                "winship": {
                    "name": "Winship Example",
                    "aliases": ["operator"],
                    "pinned_email": "operator@example.com",
                    "tier": "operator",
                }
            }
        ),
        encoding="utf-8",
    )
    return path


def _finance_state_file(tmp_path: Path) -> Path:
    path = tmp_path / "finance_state.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "accounts": {
                    "capital_hilton": {
                        "label": "Capital Hilton",
                        "status": "open",
                        "workflow_summary": "Synthetic fixture workflow",
                        "payment_summary": "Synthetic fixture payment",
                        "invoice_summary": "Synthetic fixture invoice",
                        "next_actions": ["Synthetic fixture action"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _import_structured_memory(db_path: Path, tmp_path: Path) -> None:
    apply_structured_fact_import(
        db_path=db_path,
        contact_nicknames_path=_contact_file(tmp_path),
        finance_state_path=_finance_state_file(tmp_path),
        approval_path=_approval_file(tmp_path),
        export_root=tmp_path / "structured_import_read_models",
        generated_at=FIXED_NOW,
    )


def test_missing_facts_packet_uses_governed_sqlite_only_and_blocks_send(tmp_path):
    db_path = _init_db(tmp_path)
    _insert_fact(db_path, "spreadsheet_selection", "Invoice Capitol Hilton 20260512 v2.xlsx")
    _insert_contact(db_path)
    _import_structured_memory(db_path, tmp_path)

    payload = packet.build_cassandra_clara_fact_packet(
        db_path=db_path,
        artifact_root=tmp_path / "artifacts",
        generated_at=FIXED_NOW,
    )

    assert payload["schema_version"] == "cassandra_clara_fact_packet_v0"
    assert payload["packet_kind"] == "capital_hilton_missing_facts_packet"
    assert payload["usable_capital_hilton_review_packet"] is False
    assert payload["missing_required_fact_count"] == len(packet.REQUIRED_FIELDS)
    assert payload["source_policy"] == "imported_cassandra_chief_memory_sqlite_only"
    assert payload["governed_fact_count"] >= 1
    assert payload["receivable_posture_count"] >= 1
    assert payload["send_authority_granted"] is False
    assert payload["runtime_authority_changed"] is False
    assert payload["raw_private_files_read"] is False
    assert payload["ad_hoc_notes_read"] is False
    assert payload["raw_messages_read"] is False
    assert payload["spreadsheet_cells_read"] is False
    assert payload["old_hitl_read"] is False
    assert payload["agent_presence_read"] is False
    assert payload["boundaries"]["no_send_authority"] is True
    assert payload["boundaries"]["no_runtime_authority"] is True
    assert Path(tmp_path / "artifacts" / "CAPITAL_HILTON_MISSING_FACTS_PACKET.md").is_file()
    assert "Capital Hilton Governed Fact Intake v1" == payload["next_safe_lane"]


def test_complete_fact_set_creates_usable_review_packet_without_authority(tmp_path):
    db_path = _init_db(tmp_path)
    for field_name, _label in packet.REQUIRED_FIELDS:
        _insert_fact(db_path, field_name, f"review value for {field_name}")
    _insert_contact(db_path)
    _import_structured_memory(db_path, tmp_path)

    payload = packet.build_cassandra_clara_fact_packet(
        db_path=db_path,
        artifact_root=tmp_path / "artifacts",
        generated_at=FIXED_NOW,
    )

    assert payload["packet_kind"] == "capital_hilton_review_packet"
    assert payload["usable_capital_hilton_review_packet"] is True
    assert payload["missing_required_fact_count"] == 0
    assert len(payload["invoice_facts_used"]) == len(packet.REQUIRED_FIELDS)
    assert payload["next_safe_lane"] == "Capital Hilton Invoice Review Packet Approval v0"
    assert payload["send_authority_granted"] is False
    assert payload["runtime_authority_changed"] is False
    assert payload["contact_candidate_count"] >= 1
    assert payload["governed_fact_count"] >= len(packet.REQUIRED_FIELDS)
    assert payload["receivable_posture_count"] >= 1
    for fact in payload["governed_facts"]:
        assert fact["evidence_status"] == "parsed_evidence_not_truth"
        assert fact["trust_status"] == "needs_operator_confirmation"
        assert fact["no_send_authority"] is True
        assert fact["no_runtime_authority"] is True
        assert "review value for" not in fact["value_text"]
    draft = (tmp_path / "artifacts" / "CAPITAL_HILTON_CLARA_DRAFT_EMAIL_REVIEW_ONLY.md").read_text(encoding="utf-8")
    portal = (tmp_path / "artifacts" / "CAPITAL_HILTON_PORTAL_FILL_INSTRUCTIONS_REVIEW_ONLY.md").read_text(encoding="utf-8")
    assert "Clara Reid" in draft
    assert "Do not send" in draft
    assert "has imported structured evidence" in draft
    assert "review value for" not in draft
    assert "Do not log in to Coupa" in portal
    assert "Do not use or store credentials" in portal
    assert "Do not read spreadsheet cells" in portal


def test_export_writes_json_operator_and_review_artifacts(tmp_path):
    db_path = _init_db(tmp_path)
    _insert_fact(db_path, "spreadsheet_selection", "Invoice Capitol Hilton 20260512 v2.xlsx")
    _import_structured_memory(db_path, tmp_path)

    result = packet.export_cassandra_clara_fact_packet(
        db_path=db_path,
        artifact_root=tmp_path / "artifacts",
        export_root=tmp_path / "read_models",
        generated_at=FIXED_NOW,
    )

    assert result.usable_capital_hilton_review_packet is False
    json_path = tmp_path / "read_models" / packet.JSON_EXPORT_NAME
    operator_path = tmp_path / "read_models" / packet.OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    rendered = operator_path.read_text(encoding="utf-8")
    assert payload["schema_version"] == packet.SCHEMA_VERSION
    assert payload["raw_data_imported"] is False
    assert payload["boundaries"]["email_send_allowed"] is False
    assert payload["source_policy"] == "imported_cassandra_chief_memory_sqlite_only"
    assert "invoice_facts_used" in payload
    assert "Cassandra/Clara Fact Packet v0" in rendered
    assert "Invoice Facts Used" in rendered
    assert "Contact / Recipient Posture" in rendered
    assert "Invoice / Receivable Posture" in rendered
    assert Path(tmp_path / "artifacts" / "MANIFEST.json").is_file()


def test_module_avoids_raw_sources_repo_b_network_and_send_paths():
    source = Path("cassandra_clara_fact_packet.py").read_text(encoding="utf-8")

    assert "contact_nicknames.json" not in source
    assert "finance_state.json" not in source
    assert "hitl_pending_state" not in source
    assert "agent_presence.py" not in source
    assert "agent_presence.json" not in source
    assert "openclaw_external" not in source
    assert "spreadsheet_metadata.json" not in source
    assert "chief_guardian_sender" not in source
    assert "send_approval" not in source
    assert "import requests" not in source
    assert "subprocess" not in source
