import ast
import sqlite3
from pathlib import Path

from finance_invoice_reconciliation import (
    NO_AUTHORITY_FLAGS,
    build_finance_invoice_reconciliation,
    build_finance_invoice_reconciliation_report,
    export_finance_invoice_reconciliation_read_model,
    finance_invoice_reconciliation_table_names,
)
from scripts.build_finance_invoice_reconciliation import main as build_main
from scripts.export_finance_invoice_reconciliation_read_model import main as export_main
from scripts.query_finance_invoice_reconciliation import main as query_main


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture_repo_b(tmp_path: Path) -> Path:
    root = tmp_path / "openclaw-runtime"
    root.mkdir()
    _write(
        root / "chief_billing_brain.py",
        """
import csv
import json
import subprocess

BILLING_CSV = "/home/openclaw/OpenClaw/exports/billing_records.csv"

def record_payment(client_name, invoice_no, deposit, balance):
    with open(BILLING_CSV, "a") as handle:
        handle.write(client_name)
    subprocess.run(["python", "chief_sender.py", "payment followup"])
""",
    )
    _write(
        root / "chief_invoice_brain.py",
        """
from pathlib import Path
INVOICE_ROOT = "/mnt/c/OpenClaw/billing"

def create_invoice(client_name, amount):
    Path(INVOICE_ROOT, "invoice.txt").write_text(str(amount))
    return "invoice draft"
""",
    )
    _write(
        root / "chief_financial_brain.py",
        """
def build_financial_report():
    outstanding = ["unpaid invoice"]
    payment_history = ["payment received"]
    return {"outstanding": outstanding, "payment_history": payment_history}
""",
    )
    _write(
        root / "chief_cpa_brain.py",
        """
def cpa_support(expense, tax_year):
    # CPA tax deduction support. Do not treat examples as truth.
    return {"deduction": expense, "tax_year": tax_year}
""",
    )
    _write(
        root / "budget_tracker.py",
        """
from pathlib import Path
BUDGET_LOG = "/mnt/c/OpenClaw/logs/budget_spend.log"
def record_spend(cost):
    Path(BUDGET_LOG).write_text(str(cost))
""",
    )
    _write(root / ".env", "TOKEN=SECRET_SHOULD_NOT_BE_READ\n")
    return root


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
    tables = set(finance_invoice_reconciliation_table_names(tmp_path / "ledger.sqlite"))

    assert {
        "finance_invoice_reconciliation_runs",
        "finance_candidate_sources",
        "finance_candidate_capabilities",
        "finance_candidate_risks",
        "finance_workflow_proposals",
        "finance_evidence_requirements",
        "finance_next_safe_moves",
        "finance_query_receipts",
    } <= tables


def test_synthetic_finance_candidates_classify_and_stay_non_executable(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_b = _fixture_repo_b(tmp_path)

    result = build_finance_invoice_reconciliation(
        db_path=db_path,
        repo_root=repo_b,
        run_id="finance_fixture",
        require_expected_remote=False,
    )
    invoice = _row(
        db_path,
        """
SELECT source_path, future_home, reuse_policy, risk_level, execution_allowed,
       financial_truth_claimed, send_allowed, bank_access_allowed,
       operator_approval_required, raw_body_stored
FROM finance_candidate_sources
WHERE source_path = 'chief_invoice_brain.py'
""",
    )
    capabilities = {
        row["capability_kind"]
        for row in _rows(
            db_path,
            """
SELECT capability_kind
FROM finance_candidate_capabilities c
JOIN finance_candidate_sources s ON s.candidate_id = c.candidate_id
WHERE s.source_path = 'chief_billing_brain.py'
""",
        )
    }

    assert result.finance_candidate_count == 5
    assert result.safe_source_reviewed_count == 5
    assert invoice["future_home"] == "invoice_helper"
    assert invoice["reuse_policy"] in {"candidate_to_port", "needs_operator_review"}
    assert invoice["risk_level"] in {"medium", "high"}
    assert tuple(invoice[key] for key in ("execution_allowed", "financial_truth_claimed", "send_allowed", "bank_access_allowed")) == (0, 0, 0, 0)
    assert invoice["operator_approval_required"] == 1
    assert invoice["raw_body_stored"] == 0
    assert {"invoice_drafting", "billing_tracking", "client_payment_status", "email_draft_support"} <= capabilities


def test_filename_classes_map_to_expected_capabilities(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_b = _fixture_repo_b(tmp_path)
    build_finance_invoice_reconciliation(db_path=db_path, repo_root=repo_b, run_id="finance_fixture", require_expected_remote=False)

    by_path = {
        row["source_path"]: row["capability_kind"]
        for row in _rows(
            db_path,
            """
SELECT s.source_path, c.capability_kind
FROM finance_candidate_sources s
JOIN finance_candidate_capabilities c ON c.candidate_id = s.candidate_id
WHERE c.capability_kind IN ('invoice_drafting', 'cpa_tax_support', 'budget_tracking', 'receivable_tracking')
""",
        )
    }

    assert by_path["chief_invoice_brain.py"] == "invoice_drafting"
    assert by_path["chief_cpa_brain.py"] == "cpa_tax_support"
    assert by_path["budget_tracker.py"] == "budget_tracking"
    assert by_path["chief_financial_brain.py"] == "receivable_tracking"


def test_risks_flag_direct_write_send_bank_tax_client_and_stale_architecture(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_b = _fixture_repo_b(tmp_path)
    build_finance_invoice_reconciliation(db_path=db_path, repo_root=repo_b, run_id="finance_fixture", require_expected_remote=False)

    risks = {
        (row["source_path"], row["risk_reason"])
        for row in _rows(
            db_path,
            """
SELECT s.source_path, r.risk_reason
FROM finance_candidate_risks r
JOIN finance_candidate_sources s ON s.candidate_id = r.candidate_id
""",
        )
    }

    assert ("chief_billing_brain.py", "direct_file_write") in risks
    assert ("chief_billing_brain.py", "external_send") in risks
    assert ("chief_billing_brain.py", "bank_or_payment_data") in risks
    assert ("chief_billing_brain.py", "client_sensitive") in risks
    assert ("chief_invoice_brain.py", "stale_architecture") in risks
    assert ("chief_cpa_brain.py", "tax_sensitive") in risks


def test_no_private_secret_raw_content_or_financial_truth_is_stored(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_b = _fixture_repo_b(tmp_path)
    build_finance_invoice_reconciliation(db_path=db_path, repo_root=repo_b, run_id="finance_fixture", require_expected_remote=False)

    conn = sqlite3.connect(db_path)
    try:
        dump = "\n".join(line for line in conn.iterdump())
    finally:
        conn.close()

    assert "SECRET_SHOULD_NOT_BE_READ" not in dump
    assert "financial_truth_claimed,send_allowed,bank_access_allowed" not in dump
    assert _row(db_path, "SELECT SUM(financial_truth_claimed) AS count FROM finance_candidate_sources")["count"] == 0
    assert _row(db_path, "SELECT SUM(email_send_allowed) AS count FROM finance_workflow_proposals")["count"] == 0
    assert _row(db_path, "SELECT SUM(bank_access_allowed) AS count FROM finance_workflow_proposals")["count"] == 0


def test_first_workflow_proposal_is_proposal_only_and_evidence_bound(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_b = _fixture_repo_b(tmp_path)
    build_finance_invoice_reconciliation(db_path=db_path, repo_root=repo_b, run_id="finance_fixture", require_expected_remote=False)

    workflow = _row(
        db_path,
        """
SELECT title, proposal_only, execution_allowed, invoice_send_allowed,
       email_send_allowed, bank_access_allowed, operator_approval_required,
       no_send_policy, no_bank_scrape_policy, next_safe_move
FROM finance_workflow_proposals
""",
    )
    blocked_evidence = _row(
        db_path,
        "SELECT COUNT(*) AS count FROM finance_evidence_requirements WHERE allowed = 0 AND raw_private_ingest_allowed = 0",
    )

    assert "Evidence Packet Builder" in workflow["title"]
    assert tuple(workflow[key] for key in ("proposal_only", "execution_allowed", "invoice_send_allowed", "email_send_allowed", "bank_access_allowed")) == (1, 0, 0, 0, 0)
    assert workflow["operator_approval_required"] == 1
    assert "No invoice" in workflow["no_send_policy"]
    assert "No bank" in workflow["no_bank_scrape_policy"]
    assert "evidence packet" in workflow["next_safe_move"].lower()
    assert blocked_evidence["count"] >= 2


def test_work_board_linkage_is_metadata_only(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_b = _fixture_repo_b(tmp_path)
    result = build_finance_invoice_reconciliation(db_path=db_path, repo_root=repo_b, run_id="finance_fixture", require_expected_remote=False)

    cards = _rows(
        db_path,
        """
SELECT source_kind, source_id, world_hint, agent_id, board_column,
       execution_allowed, auto_approval_allowed, auto_execute_allowed,
       direct_execution_allowed, network_authority
FROM work_board_cards
WHERE source_id LIKE 'finance_invoice_reconciliation:%'
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


def test_reports_and_read_model_export_work(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"
    repo_b = _fixture_repo_b(tmp_path)
    build_finance_invoice_reconciliation(db_path=db_path, repo_root=repo_b, run_id="finance_fixture", require_expected_remote=False)

    summary = build_finance_invoice_reconciliation_report(db_path=db_path, report="summary")
    capability = build_finance_invoice_reconciliation_report(db_path=db_path, capability="invoice_drafting")
    export = export_finance_invoice_reconciliation_read_model(db_path=db_path, export_root=export_root)
    query_rc = query_main(["--db", str(db_path), "--report", "workflow", "--format", "operator"])
    export_rc = export_main(["--db", str(db_path), "--export-root", str(export_root), "--format", "operator"])
    build_rc = build_main(
        [
            "--db",
            str(db_path),
            "--repo-root",
            str(repo_b),
            "--run-id",
            "finance_fixture_cli",
            "--allow-unknown-remote",
            "--format",
            "operator",
        ]
    )
    output = capsys.readouterr().out

    assert summary["counts"]["finance_candidate_count"] == 5
    assert capability["rows"]
    assert Path(export_root / "finance_invoice_reconciliation.json").exists()
    assert Path(export_root / "finance_invoice_reconciliation_OPERATOR.md").exists()
    assert export["finance_candidate_count"] == 5
    assert query_rc == 0
    assert export_rc == 0
    assert build_rc == 0
    assert "Finance Invoice Helper Reconciliation" in output


def test_static_forbids_no_execution_send_bank_api_or_destructive_behavior():
    source = Path("finance_invoice_reconciliation.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        assert not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "system")
        assert not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"run", "Popen", "call", "check_call", "check_output"}
        )
        assert not (isinstance(node, ast.keyword) and node.arg == "shell" and getattr(node.value, "value", None) is True)
    forbidden = ("requests", "httpx", "urllib", "socket", "smtp")
    lowered = source.lower()
    for token in forbidden:
        assert token not in lowered
    assert all(value is False for key, value in NO_AUTHORITY_FLAGS.items() if key != "operator_approval_required")
    assert NO_AUTHORITY_FLAGS["operator_approval_required"] is True
