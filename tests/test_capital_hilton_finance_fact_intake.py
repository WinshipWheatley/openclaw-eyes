import ast
import json
import sqlite3
from pathlib import Path

from capital_hilton_finance_fact_intake import (
    ALTERNATE_SPREADSHEET,
    EXTERNAL_PERSONA,
    SELECTED_SPREADSHEET,
    capital_hilton_fact_intake_table_names,
    build_capital_hilton_fact_intake_report,
    ingest_capital_hilton_invoice_facts,
    ingest_finance_spreadsheet_metadata,
    seed_capital_hilton_contact_candidates,
    write_capital_hilton_fact_intake_artifacts,
)
from capital_hilton_invoice_packet import CAPITAL_HILTON_PACKET_ID, build_capital_hilton_invoice_packet
from finance_invoice_evidence_packet import build_finance_invoice_evidence_packets_read_model


def _rows(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _metadata_packet(path: Path) -> Path:
    payload = {
        "generated_at": "2026-05-15T12:00:00+00:00",
        "source_machine": "mac",
        "source_kind": "mac_local_spreadsheet_candidate",
        "folder": "~/Documents/invoices/",
        "packet_target": CAPITAL_HILTON_PACKET_ID,
        "candidate_count": 2,
        "likely_current_candidate": {
            "filename": SELECTED_SPREADSHEET,
            "extension": ".xlsx",
            "size_bytes": 70917,
            "modified_at": "2026-05-12T22:08:07+00:00",
            "created_at": "2026-05-12T21:31:54+00:00",
            "absolute_path": f"/Users/hwinshipwheatley/Documents/invoices/{SELECTED_SPREADSHEET}",
            "likely_relevance": "high",
            "relevance_reason": "filename includes hilton and invoice; recent",
            "sensitivity_status": "sensitive_metadata_only",
            "ingestion_policy": "needs_operator_review",
            "allowed_use": "metadata_only_pending_review",
            "cell_read_allowed": False,
            "workbook_parsing_allowed": False,
            "copied": False,
            "uploaded": False,
        },
        "candidates": [
            {
                "filename": SELECTED_SPREADSHEET,
                "extension": ".xlsx",
                "size_bytes": 70917,
                "modified_at": "2026-05-12T22:08:07+00:00",
                "created_at": "2026-05-12T21:31:54+00:00",
                "absolute_path": f"/Users/hwinshipwheatley/Documents/invoices/{SELECTED_SPREADSHEET}",
                "likely_relevance": "high",
                "relevance_reason": "filename includes hilton and invoice; recent",
                "sensitivity_status": "sensitive_metadata_only",
                "ingestion_policy": "needs_operator_review",
                "allowed_use": "metadata_only_pending_review",
                "cell_read_allowed": False,
                "workbook_parsing_allowed": False,
                "copied": False,
                "uploaded": False,
            },
            {
                "filename": ALTERNATE_SPREADSHEET,
                "extension": ".xlsx",
                "size_bytes": 74082,
                "modified_at": "2026-05-12T19:31:56+00:00",
                "created_at": "2026-05-12T19:00:00+00:00",
                "absolute_path": f"/Users/hwinshipwheatley/Documents/invoices/{ALTERNATE_SPREADSHEET}",
                "likely_relevance": "medium",
                "relevance_reason": "older matching invoice workbook",
                "sensitivity_status": "sensitive_metadata_only",
                "ingestion_policy": "needs_operator_review",
                "allowed_use": "metadata_only_pending_review",
                "cell_read_allowed": False,
                "workbook_parsing_allowed": False,
                "copied": False,
                "uploaded": False,
            },
        ],
        "no_authority": {
            "spreadsheet_cell_read_allowed": False,
            "workbook_parsing_allowed": False,
            "file_copy_allowed": False,
            "upload_allowed": False,
            "financial_truth_claimed": False,
        },
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _prepare_packet(db_path: Path, artifact_root: Path):
    build_capital_hilton_invoice_packet(
        db_path=db_path,
        artifact_root=artifact_root,
        run_id="capital_hilton_fact_intake_base",
        export_read_model=False,
    )


def test_schema_initializes(tmp_path):
    tables = capital_hilton_fact_intake_table_names(tmp_path / "ledger.sqlite")

    assert "capital_hilton_spreadsheet_metadata" in tables
    assert "capital_hilton_contact_candidates" in tables
    assert "capital_hilton_invoice_fact_updates" in tables
    assert "capital_hilton_fact_intake_receipts" in tables


def test_spreadsheet_metadata_ingest_selects_v2_without_cell_read(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    _prepare_packet(db_path, tmp_path / "artifacts")
    metadata_path = _metadata_packet(tmp_path / "finance_invoice_spreadsheet_metadata.json")

    result = ingest_finance_spreadsheet_metadata(
        db_path=db_path,
        metadata_path=metadata_path,
        selected_filename=SELECTED_SPREADSHEET,
        update_artifacts=False,
        export_read_model=False,
        run_id="spreadsheet_ingest_test",
    )
    rows = _rows(
        db_path,
        """
SELECT filename, selected_candidate, alternate_candidate, sensitivity_status,
       ingestion_policy, allowed_use, cell_read_allowed, workbook_parsing_allowed,
       copied, uploaded, financial_truth_claimed
FROM capital_hilton_spreadsheet_metadata
ORDER BY selected_candidate DESC, filename
""",
    )
    evidence = _rows(
        db_path,
        """
SELECT likely_path, allowed_use, sensitivity_status, ingestion_policy,
       cell_read_allowed, raw_body_read_allowed, workbook_parsing_allowed
FROM finance_invoice_packet_evidence_links
WHERE packet_id = ? AND source_kind = 'mac_local_spreadsheet_candidate'
ORDER BY created_at DESC
""",
        (CAPITAL_HILTON_PACKET_ID,),
    )

    assert result.spreadsheet_metadata_ingested is True
    assert result.selected_spreadsheet_candidate == SELECTED_SPREADSHEET
    assert len(rows) == 2
    assert rows[0]["filename"] == SELECTED_SPREADSHEET
    assert rows[0]["selected_candidate"] == 1
    assert rows[0]["sensitivity_status"] == "sensitive_metadata_only"
    assert rows[0]["ingestion_policy"] == "needs_operator_review"
    assert rows[0]["allowed_use"] == "metadata_only_pending_review"
    assert tuple(rows[0][key] for key in ("cell_read_allowed", "workbook_parsing_allowed", "copied", "uploaded", "financial_truth_claimed")) == (0, 0, 0, 0, 0)
    assert rows[1]["filename"] == ALTERNATE_SPREADSHEET
    assert rows[1]["alternate_candidate"] == 1
    assert any(SELECTED_SPREADSHEET in row["likely_path"] for row in evidence)
    assert all(row["cell_read_allowed"] == 0 and row["raw_body_read_allowed"] == 0 and row["workbook_parsing_allowed"] == 0 for row in evidence)


def test_contacts_are_pending_review_and_annette_email_remains_missing(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    _prepare_packet(db_path, tmp_path / "artifacts")

    result = seed_capital_hilton_contact_candidates(
        db_path=db_path,
        update_artifacts=False,
        export_read_model=False,
        run_id="contact_seed_test",
    )
    contacts = _rows(
        db_path,
        """
SELECT contact_name, role, email, allowed_use, external_send_allowed,
       operator_approval_required, verified
FROM capital_hilton_contact_candidates
ORDER BY contact_name
""",
    )
    missing = _rows(
        db_path,
        "SELECT description FROM finance_invoice_packet_missing_items WHERE packet_id = ?",
        (CAPITAL_HILTON_PACKET_ID,),
    )

    assert result.contact_candidate_count == 3
    assert {row["contact_name"] for row in contacts} == {"Annette Sunga", "Chyna Hardin", "Lawrence / Will Valcovic"}
    annette = next(row for row in contacts if row["contact_name"] == "Annette Sunga")
    assert annette["email"] is None
    assert annette["allowed_use"] == "email_draft_recipient_candidate_needs_email_review"
    assert all(row["external_send_allowed"] == 0 for row in contacts)
    assert all(row["operator_approval_required"] == 1 for row in contacts)
    assert all(row["verified"] == 0 for row in contacts)
    assert any("Annette Sunga email is missing" in row["description"] for row in missing)


def test_cassandra_fact_update_uses_governed_storage_not_loose_files(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    _prepare_packet(db_path, tmp_path / "artifacts")

    result = ingest_capital_hilton_invoice_facts(
        db_path=db_path,
        facts={
            "spreadsheet_selection": SELECTED_SPREADSHEET,
            "cc_chyna": True,
            "cc_lawrence": True,
        },
        source_kind="telegram_cassandra",
        source_text=f"Clara, use {SELECTED_SPREADSHEET}; CC Chyna and Lawrence pending review.",
        update_artifacts=False,
        export_read_model=False,
        run_id="telegram_fact_update_test",
    )
    updates = _rows(
        db_path,
        "SELECT source_kind, agent_internal, external_persona, field_name, value_text, financial_truth_claimed, raw_sensitive_body_stored FROM capital_hilton_invoice_fact_updates ORDER BY field_name",
    )
    telegram_rows = _rows(
        db_path,
        "SELECT agent_target, message_text_hash, message_text_stored, raw_payload_stored, telegram_send_allowed, command_execution_allowed FROM telegram_agent_update_records",
    )

    assert result.telegram_update_record_id
    assert {row["field_name"] for row in updates} >= {"spreadsheet_selection", "cc_chyna", "cc_lawrence"}
    assert {row["agent_internal"] for row in updates} == {"cassandra"}
    assert {row["external_persona"] for row in updates} == {EXTERNAL_PERSONA}
    assert all(row["financial_truth_claimed"] == 0 and row["raw_sensitive_body_stored"] == 0 for row in updates)
    assert len(telegram_rows) == 1
    assert telegram_rows[0]["agent_target"] == "cassandra"
    assert telegram_rows[0]["message_text_hash"]
    assert tuple(telegram_rows[0][key] for key in ("message_text_stored", "raw_payload_stored", "telegram_send_allowed", "command_execution_allowed")) == (0, 0, 0, 0)


def test_artifacts_use_clara_reid_and_keep_external_draft_clean(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    artifact_root = tmp_path / "artifacts"
    _prepare_packet(db_path, artifact_root)
    metadata_path = _metadata_packet(tmp_path / "finance_invoice_spreadsheet_metadata.json")
    ingest_finance_spreadsheet_metadata(
        db_path=db_path,
        metadata_path=metadata_path,
        update_artifacts=False,
        export_read_model=False,
    )
    seed_capital_hilton_contact_candidates(db_path=db_path, update_artifacts=False, export_read_model=False)

    paths = write_capital_hilton_fact_intake_artifacts(db_path=db_path, artifact_root=artifact_root)
    draft = (artifact_root / "CAPITAL_HILTON_DRAFT_EMAIL_REVIEW_ONLY.md").read_text(encoding="utf-8")
    portal = (artifact_root / "CAPITAL_HILTON_PORTAL_FILL_PROMPT_NO_SUBMIT.md").read_text(encoding="utf-8")

    assert paths["draft_email"].endswith("CAPITAL_HILTON_DRAFT_EMAIL_REVIEW_ONLY.md")
    assert "Clara Reid" in draft
    assert "Best,\nClara Reid" in draft
    assert "Cassandra" not in draft
    assert "To: [MISSING - confirm Annette Sunga email" in draft
    assert SELECTED_SPREADSHEET in draft
    assert "Do not submit until the operator explicitly approves" in portal
    assert "Do not read spreadsheet cells." in portal


def test_read_model_includes_spreadsheet_contacts_identity_and_work_board(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    _prepare_packet(db_path, tmp_path / "artifacts")
    metadata_path = _metadata_packet(tmp_path / "finance_invoice_spreadsheet_metadata.json")
    ingest_finance_spreadsheet_metadata(
        db_path=db_path,
        metadata_path=metadata_path,
        update_artifacts=False,
        export_read_model=False,
    )
    ingest_capital_hilton_invoice_facts(
        db_path=db_path,
        facts={"spreadsheet_selection": SELECTED_SPREADSHEET},
        update_artifacts=False,
        export_read_model=False,
    )

    read_model = build_finance_invoice_evidence_packets_read_model(db_path=db_path)
    cards = read_model["work_board_linkage"]["cards"]

    assert read_model["capital_hilton_spreadsheet_selection"]["filename"] == SELECTED_SPREADSHEET
    assert len(read_model["capital_hilton_contact_candidates"]) == 3
    assert read_model["capital_hilton_external_identity_rule"]["external_persona"] == "Clara Reid"
    assert read_model["capital_hilton_external_identity_rule"]["drafts_must_not_use_internal_name"] is True
    assert read_model["spreadsheet_cell_read_allowed"] is False
    assert any(row["title"] == "Capital Hilton v2 spreadsheet selected, metadata only" for row in cards)


def test_report_and_static_boundaries(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    _prepare_packet(db_path, tmp_path / "artifacts")
    metadata_path = _metadata_packet(tmp_path / "finance_invoice_spreadsheet_metadata.json")
    ingest_finance_spreadsheet_metadata(
        db_path=db_path,
        metadata_path=metadata_path,
        update_artifacts=False,
        export_read_model=False,
    )
    seed_capital_hilton_contact_candidates(db_path=db_path, update_artifacts=False, export_read_model=False)

    report = build_capital_hilton_fact_intake_report(db_path=db_path)
    assert report["selected_spreadsheet"]["filename"] == SELECTED_SPREADSHEET
    assert report["external_identity_rule"]["external_persona"] == "Clara Reid"
    assert report["no_authority_flags"]["email_send_allowed"] is False

    source = Path("capital_hilton_finance_fact_intake.py").read_text(encoding="utf-8")
    script_source = (
        Path("scripts/ingest_finance_spreadsheet_metadata.py").read_text(encoding="utf-8")
        + "\n"
        + Path("scripts/ingest_capital_hilton_invoice_facts.py").read_text(encoding="utf-8")
    )
    tree = ast.parse(source + "\n" + script_source)
    for node in ast.walk(tree):
        assert not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "system")
        assert not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"run", "Popen", "call", "check_call", "check_output"}
        )
        assert not (isinstance(node, ast.keyword) and node.arg == "shell" and getattr(node.value, "value", None) is True)
    lowered = (source + "\n" + script_source).lower()
    for token in ("requests", "httpx", "urllib", "socket", "openpyxl", "pandas", "xlrd", "smtp", "selenium", "playwright"):
        assert token not in lowered
    assert "spreadsheet_cell_read_allowed\": False" in source
    assert "workbook_parsing_allowed\": False" in source
