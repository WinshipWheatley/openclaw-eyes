import ast
import sqlite3
from pathlib import Path

from finance_invoice_evidence_packet import (
    MAC_SPREADSHEET_FOLDER,
    NO_AUTHORITY_FLAGS,
    FinancePacketFactInput,
    build_finance_invoice_evidence_packet,
    build_finance_invoice_evidence_packet_report,
    export_finance_invoice_evidence_packets_read_model,
    finance_invoice_evidence_packet_table_names,
    spreadsheet_candidate_payload,
)
from scripts.build_finance_invoice_evidence_packet import main as build_main
from scripts.export_finance_invoice_evidence_packets_read_model import main as export_main
from scripts.query_finance_invoice_evidence_packets import main as query_main


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


def test_schema_initializes(tmp_path):
    tables = set(finance_invoice_evidence_packet_table_names(tmp_path / "ledger.sqlite"))

    assert {
        "finance_invoice_packet_runs",
        "finance_invoice_packets",
        "finance_invoice_packet_facts",
        "finance_invoice_packet_evidence_links",
        "finance_invoice_packet_missing_items",
        "finance_invoice_packet_risks",
        "finance_invoice_packet_outputs",
        "finance_invoice_packet_receipts",
        "finance_invoice_packet_query_receipts",
    } <= tables


def test_synthetic_demo_packet_is_labeled_and_claims_no_truth(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    result = build_finance_invoice_evidence_packet(
        db_path=db_path,
        title="Finance Invoice Evidence Packet v0 Demo",
        subject="Manual Review",
        workflow_kind="invoice_prep",
        run_id="demo_run",
    )
    packet = _row(
        db_path,
        """
SELECT synthetic_demo, status, financial_truth_claimed, send_allowed,
       bank_access_allowed, ledger_write_allowed, tax_filing_allowed
FROM finance_invoice_packets
WHERE packet_id = ?
""",
        (result.packet_id,),
    )
    fact = _row(db_path, "SELECT fact_kind, confidence, truth_status FROM finance_invoice_packet_facts WHERE packet_id = ?", (result.packet_id,))

    assert result.synthetic_demo is True
    assert result.status == "needs_operator_facts"
    assert tuple(packet) == (1, "needs_operator_facts", 0, 0, 0, 0, 0)
    assert tuple(fact) == ("unknown_review", "unknown_review", "needs_review")


def test_operator_supplied_fact_is_operator_claim_unless_evidence_backed(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    result = build_finance_invoice_evidence_packet(
        db_path=db_path,
        title="Packet",
        subject="Client A",
        workflow_kind="invoice_prep",
        facts=[
            FinancePacketFactInput(label="service_date", value_text="May 2026", date_or_period="May 2026"),
            FinancePacketFactInput(label="amount", value_text="100", amount_value=100.0, currency="USD"),
        ],
        run_id="operator_fact_run",
    )
    facts = _rows(
        db_path,
        "SELECT label, confidence, truth_status, financial_truth_claimed, no_raw_sensitive_body FROM finance_invoice_packet_facts WHERE packet_id = ?",
        (result.packet_id,),
    )

    assert result.synthetic_demo is False
    assert {row["confidence"] for row in facts} == {"operator_claim"}
    assert {row["truth_status"] for row in facts} == {"unverified_claim"}
    assert all(row["financial_truth_claimed"] == 0 for row in facts)
    assert all(row["no_raw_sensitive_body"] == 1 for row in facts)


def test_unsupported_financial_truth_claim_is_downgraded_and_risked(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    result = build_finance_invoice_evidence_packet(
        db_path=db_path,
        title="Packet",
        subject="Client A",
        workflow_kind="receivables_review",
        facts=[
            FinancePacketFactInput(
                label="amount",
                value_text="100",
                amount_value=100.0,
                currency="USD",
                confidence="evidence_backed",
                truth_status="evidence_backed",
            ),
            FinancePacketFactInput(label="service_date", value_text="May 2026", date_or_period="May 2026"),
        ],
        run_id="unsupported_claim_run",
    )
    amount_fact = _row(
        db_path,
        "SELECT confidence, truth_status FROM finance_invoice_packet_facts WHERE packet_id = ? AND label = 'amount'",
        (result.packet_id,),
    )
    risk = _row(
        db_path,
        "SELECT risk_kind, severity FROM finance_invoice_packet_risks WHERE packet_id = ? AND risk_kind = 'unsupported_claim'",
        (result.packet_id,),
    )

    assert tuple(amount_fact) == ("unknown_review", "needs_review")
    assert tuple(risk) == ("unsupported_claim", "high")


def test_missing_items_and_risks_are_tracked(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    result = build_finance_invoice_evidence_packet(
        db_path=db_path,
        title="Packet",
        subject="Manual Review",
        workflow_kind="invoice_prep",
        facts=[],
        run_id="missing_run",
    )
    missing = {row["description"] for row in _rows(db_path, "SELECT description FROM finance_invoice_packet_missing_items WHERE packet_id = ?", (result.packet_id,))}
    risks = {row["risk_kind"] for row in _rows(db_path, "SELECT risk_kind FROM finance_invoice_packet_risks WHERE packet_id = ?", (result.packet_id,))}

    assert any("Exact client" in item for item in missing)
    assert any("Amount" in item for item in missing)
    assert any("Service date" in item for item in missing)
    assert {"missing_amount", "missing_date", "unclear_client", "send_not_allowed", "spreadsheet_needs_review"} <= risks


def test_mac_spreadsheet_candidate_is_metadata_only_and_does_not_read_cells(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    result = build_finance_invoice_evidence_packet(
        db_path=db_path,
        title="Packet",
        subject="Client A",
        workflow_kind="invoice_prep",
        facts=[FinancePacketFactInput(label="amount", value_text="100", amount_value=100.0)],
        run_id="spreadsheet_run",
    )
    evidence = _row(
        db_path,
        """
SELECT source_kind, likely_path, allowed_use, sensitivity_status,
       ingestion_policy, cell_read_allowed, raw_body_read_allowed,
       workbook_parsing_allowed
FROM finance_invoice_packet_evidence_links
WHERE packet_id = ?
""",
        (result.packet_id,),
    )
    spreadsheet = spreadsheet_candidate_payload()

    assert evidence["source_kind"] == "mac_local_spreadsheet_candidate"
    assert evidence["likely_path"] == MAC_SPREADSHEET_FOLDER
    assert evidence["allowed_use"] == "metadata_only_pending_review"
    assert evidence["sensitivity_status"] == "sensitive_metadata_only"
    assert evidence["ingestion_policy"] == "needs_operator_review"
    assert tuple(evidence[key] for key in ("cell_read_allowed", "raw_body_read_allowed", "workbook_parsing_allowed")) == (0, 0, 0)
    assert spreadsheet["spreadsheet_candidate_known"] is True
    assert spreadsheet["spreadsheet_folder_known"] is True
    assert spreadsheet["spreadsheet_path_known"] is False
    assert spreadsheet["spreadsheet_ingestion_allowed"] is False
    assert spreadsheet["spreadsheet_cell_read_allowed"] is False


def test_exact_spreadsheet_filename_only_changes_metadata_path(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    result = build_finance_invoice_evidence_packet(
        db_path=db_path,
        title="Packet",
        subject="Client A",
        workflow_kind="invoice_prep",
        facts=[FinancePacketFactInput(label="amount", value_text="100", amount_value=100.0)],
        spreadsheet_filename="receivables.xlsx",
        run_id="spreadsheet_filename_run",
    )
    evidence = _row(
        db_path,
        "SELECT likely_path, cell_read_allowed, workbook_parsing_allowed FROM finance_invoice_packet_evidence_links WHERE packet_id = ?",
        (result.packet_id,),
    )

    assert evidence["likely_path"] == "~/Documents/invoices/receivables.xlsx"
    assert evidence["cell_read_allowed"] == 0
    assert evidence["workbook_parsing_allowed"] == 0


def test_no_send_bank_ledger_tax_or_raw_sensitive_ingest_allowed(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    result = build_finance_invoice_evidence_packet(
        db_path=db_path,
        title="Packet",
        subject="Client A",
        workflow_kind="invoice_prep",
        facts=[FinancePacketFactInput(label="amount", value_text="100", amount_value=100.0)],
        run_id="authority_run",
    )
    run = _row(
        db_path,
        """
SELECT invoice_send_allowed, email_send_allowed, bank_access_allowed,
       ledger_write_allowed, tax_filing_allowed, external_api_allowed,
       raw_sensitive_body_ingest_allowed, spreadsheet_cell_read_allowed,
       workbook_parsing_allowed, financial_truth_claimed,
       operator_approval_required
FROM finance_invoice_packet_runs
WHERE run_id = ?
""",
        (result.run_id,),
    )
    output = _row(
        db_path,
        "SELECT send_allowed, invoice_creation_allowed, raw_sensitive_body_included FROM finance_invoice_packet_outputs WHERE packet_id = ?",
        (result.packet_id,),
    )

    assert tuple(run) == (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1)
    assert tuple(output) == (0, 0, 0)


def test_reports_read_model_and_cli_work(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"
    result = build_finance_invoice_evidence_packet(
        db_path=db_path,
        title="Packet",
        subject="Manual Review",
        workflow_kind="invoice_prep",
        run_id="report_run",
    )

    summary = build_finance_invoice_evidence_packet_report(db_path=db_path, report="summary")
    packet_report = build_finance_invoice_evidence_packet_report(db_path=db_path, report="packets", packet_id=result.packet_id)
    export = export_finance_invoice_evidence_packets_read_model(db_path=db_path, export_root=export_root)
    build_rc = build_main(
        [
            "--db",
            str(db_path),
            "--title",
            "CLI Packet",
            "--subject",
            "Manual Review",
            "--workflow-kind",
            "invoice_prep",
            "--format",
            "operator",
        ]
    )
    query_rc = query_main(["--db", str(db_path), "--report", "spreadsheet", "--format", "operator"])
    export_rc = export_main(["--db", str(db_path), "--export-root", str(export_root), "--format", "operator"])
    output = capsys.readouterr().out

    assert summary["counts"]["packet_count"] >= 1
    assert packet_report["rows"][0]["packet_id"] == result.packet_id
    assert Path(export_root / "finance_invoice_evidence_packets.json").exists()
    assert Path(export_root / "finance_invoice_evidence_packets_OPERATOR.md").exists()
    assert export["spreadsheet_candidate_known"] is True
    assert export["spreadsheet_ingestion_allowed"] is False
    assert build_rc == 0
    assert query_rc == 0
    assert export_rc == 0
    assert "Finance Invoice Evidence" in output


def test_work_board_linkage_is_metadata_only(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    result = build_finance_invoice_evidence_packet(
        db_path=db_path,
        title="Packet",
        subject="Manual Review",
        workflow_kind="invoice_prep",
        run_id="work_board_run",
    )
    cards = _rows(
        db_path,
        """
SELECT source_kind, source_id, world_hint, agent_id, execution_allowed,
       auto_approval_allowed, auto_execute_allowed, direct_execution_allowed,
       network_authority
FROM work_board_cards
WHERE source_id LIKE 'finance_invoice_evidence_packet:%'
ORDER BY source_id
""",
    )

    assert result.work_board_card_count == 3
    assert len(cards) == 3
    assert {row["world_hint"] for row in cards} == {"finance"}
    assert {row["agent_id"] for row in cards} == {"chief"}
    assert all(row["source_kind"] == "manual_seed" for row in cards)
    assert all(row["execution_allowed"] == 0 for row in cards)
    assert all(row["auto_approval_allowed"] == 0 for row in cards)
    assert all(row["auto_execute_allowed"] == 0 for row in cards)
    assert all(row["direct_execution_allowed"] == 0 for row in cards)
    assert all(row["network_authority"] == 0 for row in cards)


def test_static_forbids_external_api_execution_spreadsheet_parsing_or_destructive_behavior():
    source = Path("finance_invoice_evidence_packet.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        assert not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "system")
        assert not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"run", "Popen", "call", "check_call", "check_output"}
        )
        assert not (isinstance(node, ast.keyword) and node.arg == "shell" and getattr(node.value, "value", None) is True)
    forbidden = ("requests", "httpx", "urllib", "socket", "openpyxl", "pandas", "xlrd", "smtp")
    lowered = source.lower()
    for token in forbidden:
        assert token not in lowered
    assert all(value is False for key, value in NO_AUTHORITY_FLAGS.items() if key != "operator_approval_required")
    assert NO_AUTHORITY_FLAGS["operator_approval_required"] is True
