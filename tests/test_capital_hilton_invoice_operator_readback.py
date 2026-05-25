import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import capital_hilton_invoice_operator_readback as readback
from scripts.export_capital_hilton_invoice_operator_readback import main as export_main


FIXED_NOW = "2026-05-25T23:59:00+00:00"


def _payload() -> dict:
    return readback.build_payload(generated_at=FIXED_NOW)


def test_required_models_exist():
    for name in [
        "CapitalHiltonInvoiceOperatorReadbackAggregator",
        "CapitalHiltonInvoiceUnifiedStatus",
        "InvoiceWorkflowRailSummary",
        "OperatorChatResponse",
        "InvoiceStatusBlocker",
    ]:
        assert hasattr(readback, name)
        assert name in _payload()["model_schemas"]


def test_all_required_rail_summaries_exist():
    payload = _payload()
    rails = {row["rail_name"]: row for row in payload["rail_summaries"]}

    assert set(readback.RAIL_NAMES).issubset(rails)
    assert len(payload["rail_summaries"]) == len(readback.RAIL_NAMES)
    assert rails["EMAIL_SEND"]["ready"] is False
    assert rails["COUPA_SUBMIT"]["ready"] is False
    assert rails["COMPLETION_PROOF"]["ready"] is False


def test_current_capital_hilton_not_ready_example():
    example = _payload()["examples"]["current_capital_hilton_not_ready"]
    status = example["unified_status"]

    assert status["headline"] == "Capital Hilton invoice workflow is not ready yet"
    assert status["can_mark_invoice_sent"] is False
    assert status["can_send_email"] is False
    assert status["can_submit_coupa"] is False
    assert status["can_run_workflow"] is False
    assert "confirmed Coupa PO/reference" in status["missing_items"]
    assert "email send" in status["blocked_items"]
    assert "Nothing has been sent, submitted, opened, approved, or marked complete" in example["chat_response"]["operator_message"]


def test_email_draft_ready_send_blocked_example():
    example = _payload()["examples"]["email_draft_ready_send_blocked"]

    assert example["unified_status"]["can_send_email"] is False
    assert "Email draft is ready for review" in example["unified_status"]["headline"]
    assert "sending is still locked" in example["chat_response"]["operator_message"]
    assert any(row["rail_name"] == "EMAIL_DRAFT" and row["ready"] is True for row in example["rail_summaries"])


def test_coupa_package_submit_blocked_example():
    example = _payload()["examples"]["coupa_package_submit_blocked"]

    assert example["unified_status"]["can_submit_coupa"] is False
    assert "Coupa package exists" in example["unified_status"]["headline"]
    assert "Coupa access and submit are blocked" in example["chat_response"]["operator_message"]
    assert any(row["rail_name"] == "COUPA_SUBMIT" and row["ready"] is False for row in example["rail_summaries"])


def test_completion_proof_blocked_and_false_claim_blocked():
    payload = _payload()
    blocked = payload["examples"]["completion_proof_blocked"]
    false_claim = payload["examples"]["false_invoice_sent_claim_blocked"]

    assert blocked["unified_status"]["can_mark_invoice_sent"] is False
    assert "cannot mark INVOICE SENT" in blocked["chat_response"]["operator_message"]
    assert false_claim["unified_status"]["can_mark_invoice_sent"] is False
    assert "INVOICE SENT without proof receipts" in false_claim["unified_status"]["blocked_items"]


def test_fully_complete_fixture_is_the_only_completion_true():
    payload = _payload()
    complete = payload["examples"]["fully_complete_fixture"]

    assert complete["unified_status"]["can_mark_invoice_sent"] is True
    assert complete["unified_status"]["completion_label_status"] == "COMPLETION_CONFIRMED_FIXTURE_ONLY"
    assert "INVOICE SENT AND RECORDED" in complete["chat_response"]["operator_message"]
    assert complete["unified_status"]["can_send_email"] is False
    assert complete["unified_status"]["can_submit_coupa"] is False

    for key, example in payload["examples"].items():
        if key != "fully_complete_fixture":
            assert example["unified_status"]["can_mark_invoice_sent"] is False


def test_operator_chat_response_is_concise_human_readable():
    chat = _payload()["chat_response"]

    assert chat["operator_headline"] == "Capital Hilton invoice workflow is not ready yet"
    assert len(chat["operator_message"]) < 420
    assert not chat["operator_message"].startswith("BLOCKED_")
    assert not chat["operator_message"].startswith("NOT_READY_")
    assert chat["mac_chat_render_hint"] == "single_concise_status_card_with_detail_refs"
    assert chat["detail_refs"]


def test_blockers_exist_and_fail_closed():
    blockers = {row["blocker_type"]: row for row in _payload()["invoice_status_blockers"]}

    for blocker_type in readback.BLOCKER_TYPES:
        assert blocker_type in blockers
        assert blockers[blocker_type]["fail_closed"] is True
    assert blockers["COMPLETION_CLAIM_WITHOUT_PROOF"]["severity"] == "critical"
    assert blockers["EXTERNAL_ACTION_ATTEMPTED"]["severity"] == "critical"


def test_all_live_authority_false():
    payload = _payload()

    assert payload["machine_proof"]["all_live_authority_false"] is True
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    for key in [
        "workflow_run_performed",
        "email_send_performed",
        "mail_send_performed",
        "gmail_send_performed",
        "coupa_access_performed",
        "coupa_submit_performed",
        "browser_access_performed",
        "secret_reveal_performed",
        "approval_execution_performed",
        "payment_tracking_write_performed",
        "completion_write_performed",
        "external_action_performed",
        "credential_handling_performed",
        "raw_body_ingestion_performed",
        "mac_sync_import_performed",
        "swift_change_performed",
        "git_push_performed",
    ]:
        assert payload["machine_proof"][key] is False


def test_export_writes_json_and_operator_markdown(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / readback.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / readback.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == readback.READ_MODEL_ID
    assert summary["headline"] == "Capital Hilton invoice workflow is not ready yet"
    assert summary["can_mark_invoice_sent"] is False
    assert summary["all_live_authority_false"] is True
    assert payload["schema_version"] == readback.SCHEMA_VERSION
    assert "Capital Hilton Invoice Operator Readback" in operator
    assert "No workflow run" in operator


def test_generated_outputs_have_no_credentials_private_bodies_or_raw_emails(tmp_path):
    payload = _payload()
    readback.write_exports(payload, tmp_path)
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())

    assert "actual secret value" not in text.lower()
    assert "raw private body value" not in text.lower()
    assert "credential value" not in text.lower()
    assert "token value" not in text.lower()
    assert "raw password value" not in text.lower()
    assert "raw body payload" not in text.lower()
    assert "AKIA" not in text
    assert not re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)
