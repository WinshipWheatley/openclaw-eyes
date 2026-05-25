import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import repo_b_finance_budget_adapter as adapter
from scripts.export_repo_b_finance_budget_adapter import main as export_main


FIXED_NOW = "2026-05-25T22:00:00+00:00"


def _payload() -> dict:
    return adapter.build_payload(generated_at=FIXED_NOW)


def _capability(payload: dict, capability_id: str) -> dict:
    return next(row for row in payload["finance_capabilities"] if row["capability_id"] == capability_id)


def test_required_models_exist():
    for name in [
        "RepoBFinanceAdapterDecision",
        "FinanceCalculationCapability",
        "PromotedFinanceAdapterPlan",
        "FinanceAdapterReadback",
        "FinanceAdapterBlocker",
    ]:
        assert hasattr(adapter, name)


def test_adapter_decisions_classify_repo_b_modules():
    payload = _payload()
    decisions = {row["source_module"]: row for row in payload["adapter_decisions"]}

    assert decisions["budget_tracker.py"]["recommended_posture"] == "REBUILD_SMALL_SUBSET_IN_REPO_A"
    assert "budget_zone" in decisions["budget_tracker.py"]["promotion_scope"]
    assert decisions["chief_cpa_brain.py"]["recommended_posture"] == "REFERENCE_ONLY"
    assert "LLM/cloud formatting" in decisions["chief_cpa_brain.py"]["blocked_items"]


def test_safe_deterministic_capabilities_identified():
    payload = _payload()
    for capability in payload["finance_capabilities"]:
        assert capability["deterministic"] is True
        assert capability["external_authority"] is False
        assert capability["credential_required"] is False
        assert capability["raw_private_data_required"] is False
        assert capability["promotion_allowed"] is True


def test_show_budget_calculation_example_and_pure_allowance():
    payload = _payload()
    example = payload["examples"]["show_budget_calculation"]
    snapshot = adapter.budget_snapshot({"codex": 2.0}, {"codex": 10.0}, 25.0)
    allowance = adapter.runner_allowance(snapshot, "codex", "sonnet", "standard")

    assert _capability(payload, "finance_capability_show_budget_calculation")["capability_type"] == "SHOW_BUDGET_CALCULATION"
    assert example["snapshot"]["budget_zone"] == "green"
    assert allowance["allowed"] is True
    assert allowance["max_budget"] > 0
    assert example["no_external_authority"] is True


def test_expense_category_mapping_example_exists():
    payload = _payload()
    example = payload["examples"]["expense_category_mapping"]
    mapped = adapter.map_expense_category("new microphone cable")

    assert _capability(payload, "finance_capability_expense_category_mapping")["capability_type"] == "EXPENSE_CATEGORY_MAPPING"
    assert example["result"]["category"] == "software"
    assert mapped["category"] == "gear"
    assert mapped["operator_review_required"] is True


def test_capital_hilton_invoice_summary_example_exists():
    payload = _payload()
    summary = payload["examples"]["capital_hilton_invoice_summary"]

    assert summary["known_basis"]["performance_date_count"] == 4
    assert summary["known_basis"]["rate_per_date"] == 400
    assert summary["known_basis"]["subtotal"] == 1600
    assert summary["payment_tracking_summary"]["send_or_submit_status"] == "not_performed"


def test_tax_category_hint_is_not_professional_advice():
    payload = _payload()
    hint = payload["examples"]["tax_category_hint"]

    assert _capability(payload, "finance_capability_tax_category_hint")["capability_type"] == "TAX_CATEGORY_HINT"
    assert hint["professional_advice"] is False
    assert hint["filing_authority"] is False
    assert "Not tax advice" in hint["hint"]


def test_bank_payment_tax_filing_blockers_exist():
    payload = _payload()
    blockers = {row["blocker_type"]: row for row in payload["finance_adapter_blockers"]}

    assert blockers["BANK_ACCESS_ATTEMPTED"]["fail_closed"] is True
    assert blockers["PAYMENT_EXECUTION_ATTEMPTED"]["fail_closed"] is True
    assert blockers["TAX_FILING_ATTEMPTED"]["fail_closed"] is True
    assert payload["examples"]["unsafe_bank_payment_blocker"]["blocker_type"] == "BANK_ACCESS_ATTEMPTED"


def test_authority_boundary_all_false():
    payload = _payload()

    assert payload["machine_proof"]["all_live_authority_false"] is True
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    for key in [
        "bank_access_performed",
        "payment_execution_performed",
        "tax_filing_performed",
        "external_account_access_performed",
        "invoice_email_send_performed",
        "coupa_access_performed",
        "credential_handling_performed",
        "raw_private_ledger_exposure",
        "professional_advice_claim",
        "external_action_performed",
    ]:
        assert payload["machine_proof"][key] is False


def test_export_writes_json_and_operator_markdown(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / adapter.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / adapter.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["posture"] == "REBUILD_SMALL_SUBSET_IN_REPO_A"
    assert summary["capital_hilton_subtotal"] == 1600
    assert payload["schema_version"] == adapter.SCHEMA_VERSION
    assert "Repo B Finance Budget Adapter" in operator
    assert "Unsafe bank/payment action: blocked" in operator


def test_generated_outputs_have_no_credentials_private_bodies_or_advice_claims(tmp_path):
    payload = _payload()
    adapter.write_exports(payload, tmp_path)
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())

    assert "GMAIL_APP_PASSWORD" not in text
    assert "SMTP_PASSWORD" not in text
    assert "BEGIN OPENSSH PRIVATE KEY" not in text
    assert "raw ledger row value" not in text.lower()
    assert not __import__("re").search(r'"professional_advice"\s*:\s*true', text)
    assert "professional tax advice" not in text.lower()
    assert not __import__("re").search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)


def test_source_does_not_execute_repo_b_or_external_finance_actions():
    source = Path("repo_b_finance_budget_adapter.py").read_text(encoding="utf-8").lower()
    forbidden = [
        "subprocess.run",
        "from chief_cpa_brain",
        "import chief_cpa_brain",
        "from budget_tracker",
        "import budget_tracker",
        "requests.",
        "httpx.",
        "urllib.request",
        "smtplib",
        "selenium",
        "playwright",
        "webbrowser",
        "plaid",
        "stripe",
        "quickbooks",
        "os.system",
        "shell=true",
    ]
    for token in forbidden:
        assert token not in source
