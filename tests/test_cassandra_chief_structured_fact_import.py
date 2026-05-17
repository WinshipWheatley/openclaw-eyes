import json
import sqlite3
from pathlib import Path

from cassandra_chief_memory_import_approval import build_cassandra_chief_memory_import_approval
from cassandra_chief_memory_authority import build_cassandra_chief_structured_import_plan
from cassandra_chief_structured_fact_import import (
    JSON_EXPORT_NAME,
    OPERATOR_EXPORT_NAME,
    apply_structured_fact_import,
    dry_run_structured_fact_import,
)
from scripts.import_cassandra_chief_structured_facts import main as import_main


FIXED_NOW = "2026-05-16T12:00:00+00:00"


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
    path = tmp_path / "approval.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _contact_file(tmp_path: Path) -> Path:
    path = tmp_path / "contact_nicknames.json"
    path.write_text(
        json.dumps(
            {
                "_note": "ignored",
                "clienta": {
                    "name": "Secret Client A",
                    "aliases": ["SC A"],
                    "pinned_email": "secret@example.com",
                    "pinned_phone": "555-0100",
                    "telegram_chat_id": "12345",
                    "tier": "business",
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
                    "secret_account": {
                        "label": "Secret Account",
                        "status": "open",
                        "workflow_summary": "Private workflow body",
                        "payment_summary": "Private payment body",
                        "invoice_summary": "Private invoice body",
                        "next_actions": ["Private next action"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _seed_finance_sqlite(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
CREATE TABLE capital_hilton_contact_candidates (
  contact_candidate_id TEXT PRIMARY KEY,
  packet_id TEXT,
  organization TEXT,
  contact_name TEXT,
  role TEXT,
  email TEXT,
  confidence TEXT,
  source_basis TEXT,
  allowed_use TEXT,
  external_send_allowed INTEGER,
  operator_approval_required INTEGER,
  verified INTEGER,
  created_at TEXT,
  updated_at TEXT
)
""".strip()
        )
        conn.execute(
            """
CREATE TABLE capital_hilton_invoice_fact_updates (
  fact_update_id TEXT PRIMARY KEY,
  packet_id TEXT,
  source_kind TEXT,
  source_ref TEXT,
  agent_internal TEXT,
  external_persona TEXT,
  field_name TEXT,
  value_text TEXT,
  confidence TEXT,
  truth_status TEXT,
  financial_truth_claimed INTEGER,
  raw_sensitive_body_stored INTEGER,
  created_at TEXT
)
""".strip()
        )
        conn.execute(
            """
CREATE TABLE finance_invoice_packet_facts (
  fact_id TEXT PRIMARY KEY,
  packet_id TEXT,
  fact_kind TEXT,
  label TEXT,
  value_text TEXT,
  amount_value REAL,
  currency TEXT,
  date_or_period TEXT,
  confidence TEXT,
  truth_status TEXT,
  source_ref TEXT,
  no_raw_sensitive_body INTEGER,
  financial_truth_claimed INTEGER,
  created_at TEXT
)
""".strip()
        )
        conn.execute(
            """
CREATE TABLE finance_invoice_packets (
  packet_id TEXT PRIMARY KEY,
  title TEXT,
  subject_entity TEXT,
  workflow_kind TEXT,
  status TEXT,
  next_safe_move TEXT
)
""".strip()
        )
        conn.execute(
            """
INSERT INTO capital_hilton_contact_candidates VALUES (
  'contact_1', 'finance_capital_hilton_invoice_packet_v0', 'Capital Hilton',
  'Private Contact', 'AP', 'private@example.com', 'operator_claim',
  'test_source', 'to_candidate_pending_review', 0, 1, 0, ?, ?
)
""".strip(),
            (FIXED_NOW, FIXED_NOW),
        )
        conn.execute(
            """
INSERT INTO capital_hilton_invoice_fact_updates VALUES (
  'fact_update_1', 'finance_capital_hilton_invoice_packet_v0', 'operator_supplied',
  'operator_prompt', 'cassandra', 'Clara Reid', 'rate_or_amount_per_gig',
  '$400 private value', 'operator_claim', 'unverified_claim', 0, 0, ?
)
""".strip(),
            (FIXED_NOW,),
        )
        conn.execute(
            """
INSERT INTO finance_invoice_packet_facts VALUES (
  'fact_1', 'finance_capital_hilton_invoice_packet_v0', 'operator_supplied',
  'invoice_count_preference', 'one invoice private value', NULL, NULL, NULL,
  'operator_claim', 'unverified_claim', 'operator_prompt', 1, 0, ?
)
""".strip(),
            (FIXED_NOW,),
        )
        conn.execute(
            """
INSERT INTO finance_invoice_packets VALUES (
  'finance_capital_hilton_invoice_packet_v0', 'Capital Hilton Packet',
  'Capital Hilton', 'invoice_prep', 'ready_for_draft_review', 'Review only'
)
""".strip()
        )
        conn.commit()
    finally:
        conn.close()


def _rows(db_path: Path, table_name: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in conn.execute(f"SELECT * FROM {table_name}").fetchall()]
    finally:
        conn.close()


def test_dry_run_requires_approval_and_does_not_import(tmp_path):
    approval = _approval_file(tmp_path)
    contacts = _contact_file(tmp_path)
    finance = _finance_state_file(tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    _seed_finance_sqlite(db_path)

    dry_run = dry_run_structured_fact_import(
        db_path=db_path,
        contact_nicknames_path=contacts,
        finance_state_path=finance,
        approval_path=approval,
    )

    assert dry_run["mode"] == "dry_run"
    assert dry_run["data_imported"] is False
    assert dry_run["runtime_authority_changed"] is False
    assert set(dry_run["would_import_categories"]) == {
        "contacts/nicknames",
        "company/contact relationships",
        "email permission posture",
        "invoice facts",
        "receivable/payment tracking",
    }


def test_apply_imports_only_approved_categories_as_parsed_evidence(tmp_path):
    approval = _approval_file(tmp_path)
    contacts = _contact_file(tmp_path)
    finance = _finance_state_file(tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"
    _seed_finance_sqlite(db_path)

    payload = apply_structured_fact_import(
        db_path=db_path,
        contact_nicknames_path=contacts,
        finance_state_path=finance,
        approval_path=approval,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )

    assert payload["schema_version"] == "cassandra_chief_structured_fact_import_v0"
    assert payload["data_imported"] is True
    assert payload["records_imported_count"] > 0
    assert payload["records_needing_operator_confirmation"] == payload["records_imported_count"]
    assert payload["categories_skipped"] == []
    assert payload["raw_logs_imported"] is False
    assert payload["old_hitl_imported"] is False
    assert payload["agent_presence_imported"] is False
    assert payload["spreadsheet_cells_read"] is False
    assert payload["send_authority_granted"] is False
    assert payload["runtime_authority_changed"] is False

    for table_name in (
        "cassandra_chief_memory_entities",
        "cassandra_chief_memory_entity_aliases",
        "cassandra_chief_memory_entity_relationships",
        "cassandra_chief_memory_contact_channels",
        "cassandra_chief_memory_email_permissions",
        "cassandra_chief_memory_finance_source_links",
    ):
        rows = _rows(db_path, table_name)
        assert rows
        assert all(row["evidence_status"] == "parsed_evidence_not_truth" for row in rows)
        assert all(row["trust_status"] == "needs_operator_confirmation" for row in rows)
        assert all(row["no_send_authority"] == 1 for row in rows)
        assert all(row["no_runtime_authority"] == 1 for row in rows)
        assert all(row["approval_required"] == 1 for row in rows)

    assert (export_root / JSON_EXPORT_NAME).is_file()
    assert (export_root / OPERATOR_EXPORT_NAME).is_file()


def test_import_does_not_store_raw_private_values_in_read_model_or_sqlite(tmp_path):
    approval = _approval_file(tmp_path)
    contacts = _contact_file(tmp_path)
    finance = _finance_state_file(tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"
    _seed_finance_sqlite(db_path)

    apply_structured_fact_import(
        db_path=db_path,
        contact_nicknames_path=contacts,
        finance_state_path=finance,
        approval_path=approval,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )
    combined = (export_root / JSON_EXPORT_NAME).read_text(encoding="utf-8")
    for table_name in (
        "cassandra_chief_memory_entities",
        "cassandra_chief_memory_entity_aliases",
        "cassandra_chief_memory_entity_relationships",
        "cassandra_chief_memory_contact_channels",
        "cassandra_chief_memory_email_permissions",
        "cassandra_chief_memory_finance_source_links",
    ):
        combined += json.dumps(_rows(db_path, table_name), sort_keys=True)

    forbidden = [
        "Secret Client A",
        "secret@example.com",
        "555-0100",
        "Private Contact",
        "private@example.com",
        "$400 private value",
        "one invoice private value",
        "Private payment body",
        "Private workflow body",
        "Private next action",
    ]
    for text in forbidden:
        assert text not in combined


def test_missing_source_files_skip_safely(tmp_path):
    approval = _approval_file(tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"

    payload = apply_structured_fact_import(
        db_path=db_path,
        contact_nicknames_path=tmp_path / "missing_contacts.json",
        finance_state_path=tmp_path / "missing_finance.json",
        approval_path=approval,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )

    skipped = {item["category"] for item in payload["categories_skipped"]}
    assert "contacts/nicknames" in skipped
    assert "receivable/payment tracking" in skipped
    assert payload["raw_logs_imported"] is False
    assert payload["old_hitl_imported"] is False


def test_cli_dry_run_and_apply(tmp_path, capsys):
    approval = _approval_file(tmp_path)
    contacts = _contact_file(tmp_path)
    finance = _finance_state_file(tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"
    _seed_finance_sqlite(db_path)

    assert import_main(
        [
            "--dry-run",
            "--db-path",
            str(db_path),
            "--contact-nicknames",
            str(contacts),
            "--finance-state",
            str(finance),
            "--approval",
            str(approval),
        ]
    ) == 0
    assert '"data_imported": false' in capsys.readouterr().out

    assert import_main(
        [
            "--apply-approved",
            "--db-path",
            str(db_path),
            "--contact-nicknames",
            str(contacts),
            "--finance-state",
            str(finance),
            "--approval",
            str(approval),
            "--export-root",
            str(export_root),
        ]
    ) == 0
    assert '"runtime_authority_changed": false' in capsys.readouterr().out
    json.loads((export_root / JSON_EXPORT_NAME).read_text(encoding="utf-8"))


def test_import_surface_does_not_import_repo_b_network_send_or_subprocess():
    source_files = [
        Path("cassandra_chief_structured_fact_import.py"),
        Path("scripts/import_cassandra_chief_structured_facts.py"),
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
