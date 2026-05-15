import ast
import json
import sqlite3
from pathlib import Path

from capital_hilton_invoice_packet import (
    CAPITAL_HILTON_PACKET_ID,
    NO_AUTHORITY_FLAGS,
    build_capital_hilton_invoice_packet,
    draft_email_body,
    portal_fill_prompt,
    receivable_tracking_proposal,
)
from finance_invoice_evidence_packet import build_finance_invoice_evidence_packets_read_model
from scripts.build_capital_hilton_invoice_packet import main as build_main


def _row(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def _rows(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_capital_hilton_packet_builds_review_only_artifacts(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    artifact_root = tmp_path / "capital_hilton"

    result = build_capital_hilton_invoice_packet(
        db_path=db_path,
        artifact_root=artifact_root,
        run_id="capital_hilton_test_run",
        export_read_model=False,
    )
    packet = _row(
        db_path,
        """
SELECT packet_id, title, subject_entity, status, synthetic_demo,
       financial_truth_claimed, send_allowed, bank_access_allowed,
       ledger_write_allowed, tax_filing_allowed
FROM finance_invoice_packets
WHERE packet_id = ?
""",
        (CAPITAL_HILTON_PACKET_ID,),
    )

    assert result.packet_id == CAPITAL_HILTON_PACKET_ID
    assert result.financial_truth_claimed is False
    assert tuple(packet) == (
        CAPITAL_HILTON_PACKET_ID,
        "Capital Hilton Invoice Evidence Packet v0",
        "Capital Hilton / Capitol Hilton",
        "blocked_missing_info",
        0,
        0,
        0,
        0,
        0,
        0,
    )
    assert result.missing_required_fact_count == 9
    assert result.output_count == 4
    assert Path(result.draft_email_path).exists()
    assert Path(result.portal_prompt_path).exists()
    assert Path(result.receivable_proposal_path).exists()
    assert Path(result.packet_summary_path).exists()
    assert (artifact_root / "MANIFEST.json").exists()


def test_required_missing_facts_are_recorded(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    build_capital_hilton_invoice_packet(
        db_path=db_path,
        artifact_root=tmp_path / "artifacts",
        run_id="missing_fact_run",
        export_read_model=False,
    )

    descriptions = {
        row["description"]
        for row in _rows(
            db_path,
            "SELECT description FROM finance_invoice_packet_missing_items WHERE packet_id = ?",
            (CAPITAL_HILTON_PACKET_ID,),
        )
    }

    required_fragments = (
        "Exact date for tonight's gig",
        "Exact date for last Friday's gig",
        "Amount or rate per gig",
        "One invoice versus two invoices",
        "PO number(s)",
        "Billing/remit details",
        "Recipient and CC decision",
        "Supplier portal reference",
        "Invoice attachment/output path",
    )
    for fragment in required_fragments:
        assert any(fragment in description for description in descriptions)


def test_outputs_are_review_only_no_send_no_submit(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    build_capital_hilton_invoice_packet(
        db_path=db_path,
        artifact_root=tmp_path / "artifacts",
        run_id="outputs_run",
        export_read_model=False,
    )

    outputs = _rows(
        db_path,
        """
SELECT output_kind, body_text, send_allowed, invoice_creation_allowed,
       raw_sensitive_body_included
FROM finance_invoice_packet_outputs
WHERE packet_id = ?
""",
        (CAPITAL_HILTON_PACKET_ID,),
    )
    output_kinds = {row["output_kind"] for row in outputs}
    all_text = "\n".join(row["body_text"] for row in outputs)

    assert {
        "capital_hilton_draft_email_review_only",
        "capital_hilton_portal_fill_instruction_prompt",
        "capital_hilton_receivable_tracking_proposal",
        "capital_hilton_packet_summary",
    } <= output_kinds
    assert "Do Not Send" in draft_email_body()
    assert "Best,\nClara Reid" in draft_email_body()
    assert "Cassandra" not in draft_email_body()
    assert "No Submit" in portal_fill_prompt()
    assert "pending_invoice_approval" in receivable_tracking_proposal()
    assert "follow_up_owner_internal: Cassandra" in receivable_tracking_proposal()
    assert "follow_up_external_persona: Clara Reid" in receivable_tracking_proposal()
    assert "Do not submit anything." in all_text
    assert all(tuple(row[key] for key in ("send_allowed", "invoice_creation_allowed", "raw_sensitive_body_included")) == (0, 0, 0) for row in outputs)


def test_work_board_cards_are_metadata_only(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    result = build_capital_hilton_invoice_packet(
        db_path=db_path,
        artifact_root=tmp_path / "artifacts",
        run_id="work_board_run",
        export_read_model=False,
    )
    cards = _rows(
        db_path,
        """
SELECT title, source_kind, source_id, world_hint, agent_id, lane_id,
       board_column, status, execution_allowed, auto_approval_allowed,
       auto_execute_allowed, network_authority, file_move_allowed,
       file_delete_allowed
FROM work_board_cards
WHERE source_id LIKE 'capital_hilton_invoice_packet:%'
ORDER BY title
""",
    )

    assert result.work_board_card_count == 3
    assert {row["title"] for row in cards} == {
        "Capital Hilton invoice packet needs facts",
        "Capital Hilton portal-fill prompt pending approval",
        "Capital Hilton receivable tracking pending invoice send",
    }
    assert {row["world_hint"] for row in cards} == {"finance"}
    assert any(row["agent_id"] == "cassandra" and row["lane_id"] == "operator_comms" for row in cards)
    assert all(row["source_kind"] == "manual_seed" for row in cards)
    assert all(row["execution_allowed"] == 0 for row in cards)
    assert all(row["auto_approval_allowed"] == 0 for row in cards)
    assert all(row["auto_execute_allowed"] == 0 for row in cards)
    assert all(row["network_authority"] == 0 for row in cards)
    assert all(row["file_move_allowed"] == 0 for row in cards)
    assert all(row["file_delete_allowed"] == 0 for row in cards)


def test_read_model_includes_latest_outputs_and_capital_work_board_cards(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    build_capital_hilton_invoice_packet(
        db_path=db_path,
        artifact_root=tmp_path / "artifacts",
        run_id="read_model_run",
        export_read_model=False,
    )

    read_model = build_finance_invoice_evidence_packets_read_model(db_path=db_path)
    latest_outputs = read_model["latest_packet_outputs"]
    cards = read_model["work_board_linkage"]["cards"]

    assert read_model["latest_packet"]["packet_id"] == CAPITAL_HILTON_PACKET_ID
    assert {row["output_kind"] for row in latest_outputs} >= {
        "capital_hilton_draft_email_review_only",
        "capital_hilton_portal_fill_instruction_prompt",
        "capital_hilton_receivable_tracking_proposal",
    }
    assert any(row["title"] == "Capital Hilton invoice packet needs facts" for row in cards)
    assert read_model["spreadsheet_cell_read_allowed"] is False


def test_cli_and_manifest_work(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    artifact_root = tmp_path / "capital_hilton_cli"

    rc = build_main(
        [
            "--db",
            str(db_path),
            "--artifact-root",
            str(artifact_root),
            "--run-id",
            "cli_run",
            "--no-export",
            "--format",
            "operator",
        ]
    )
    output = capsys.readouterr().out
    manifest = json.loads((artifact_root / "MANIFEST.json").read_text(encoding="utf-8"))

    assert rc == 0
    assert "Capital Hilton Invoice Packet v0" in output
    assert manifest["packet_id"] == CAPITAL_HILTON_PACKET_ID
    assert manifest["no_authority_flags"]["email_send_allowed"] is False


def test_static_forbids_execution_network_portal_or_spreadsheet_behavior():
    source = Path("capital_hilton_invoice_packet.py").read_text(encoding="utf-8")
    script_source = Path("scripts/build_capital_hilton_invoice_packet.py").read_text(encoding="utf-8")
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
    assert all(value is False for key, value in NO_AUTHORITY_FLAGS.items() if key != "operator_approval_required")
    assert NO_AUTHORITY_FLAGS["operator_approval_required"] is True
