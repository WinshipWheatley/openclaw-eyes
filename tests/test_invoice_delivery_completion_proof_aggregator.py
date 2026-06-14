import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import invoice_delivery_completion_proof_aggregator as aggregator
from scripts.export_invoice_delivery_completion_proof_aggregator import main as export_main


FIXED_NOW = "2026-05-25T23:59:00+00:00"


def _payload() -> dict:
    return aggregator.build_payload(generated_at=FIXED_NOW)


def test_required_models_exist():
    for name in [
        "InvoiceDeliveryCompletionProofAggregator",
        "InvoiceDeliveryCompletionProofSet",
        "CompletionReceiptRequirement",
        "InvoiceCompletionReadback",
        "FinalVisualReadbackTarget",
        "CompletionProofBlocker",
    ]:
        assert hasattr(aggregator, name)


def test_capital_hilton_not_complete_blocks():
    example = _payload()["examples"]["capital_hilton_not_complete"]

    assert example["proof_set"]["completion_allowed"] is False
    assert example["readback"]["status"] == "COMPLETION_BLOCKED_NO_RECEIPTS"
    assert "OpenClaw cannot mark the Capital Hilton invoice as sent yet" in example["readback"]["operator_message"]
    assert "EMAIL_SEND_RECEIPT" in example["proof_set"]["missing_receipts"]
    assert example["visual_target"]["should_spawn_visual_artifact"] is False


def test_email_only_incomplete_distinguishes_email_from_final_completion():
    example = _payload()["examples"]["capital_hilton_email_only_incomplete"]

    assert example["channel_completion"]["EMAIL_SENT"] is True
    assert example["channel_completion"]["INVOICE_SENT_AND_RECORDED"] is False
    assert example["proof_set"]["completion_allowed"] is False
    assert example["readback"]["status"] == "COMPLETION_BLOCKED_MISSING_COUPA_PROOF"
    assert "COUPA_SUBMIT_RECEIPT" in example["proof_set"]["missing_receipts"]


def test_coupa_only_incomplete_blocks_invoice_sent():
    example = _payload()["examples"]["capital_hilton_coupa_only_incomplete"]

    assert example["channel_completion"]["COUPA_INVOICE_SUBMITTED"] is True
    assert example["channel_completion"]["EMAIL_SENT"] is False
    assert example["proof_set"]["completion_allowed"] is False
    assert example["readback"]["status"] == "COMPLETION_BLOCKED_MISSING_EMAIL_PROOF"
    assert "EMAIL_SEND_RECEIPT" in example["proof_set"]["missing_receipts"]


def test_fully_complete_fixture_allows_completion_only_there():
    payload = _payload()
    complete = payload["examples"]["capital_hilton_fully_complete_fixture"]

    assert complete["proof_set"]["completion_allowed"] is True
    assert complete["proof_set"]["completion_label"] == "INVOICE_SENT_AND_RECORDED"
    assert complete["readback"]["status"] == "COMPLETION_CONFIRMED"
    assert "INVOICE SENT AND RECORDED" in complete["readback"]["operator_message"]
    assert "Email sent to Annette with Winship-branded invoice attachment." in complete["readback"]["proof_bullets"]
    assert complete["visual_target"]["should_spawn_visual_artifact"] is True
    assert complete["visual_target"]["factual_priority"] > complete["visual_target"]["style_priority"]

    for key, example in payload["examples"].items():
        if key != "capital_hilton_fully_complete_fixture":
            assert example["proof_set"]["completion_allowed"] is False


def test_false_completion_claim_blocked():
    example = _payload()["examples"]["false_completion_claim_blocked"]

    assert example["proof_set"]["completion_allowed"] is False
    assert "Invoice sent" in example["readback"]["blocked_completion_claims"]
    assert "INVOICE_SENT" in example["readback"]["blocked_completion_claims"]
    assert "EMAIL_SEND_RECEIPT" in example["proof_set"]["missing_receipts"]


def test_receipt_requirements_present_and_show_missing_how_to_fix():
    example = _payload()["examples"]["capital_hilton_not_complete"]
    rows = {row["receipt_type"]: row for row in example["receipt_requirements"]}

    for receipt_type in aggregator.FULL_COMPLETION_RECEIPTS:
        assert receipt_type in rows
        assert rows[receipt_type]["required"] is True
        assert rows[receipt_type]["present"] is False
        assert "rerun completion aggregation" in rows[receipt_type]["how_to_fix"]


def test_blockers_exist_and_fail_closed():
    blockers = {row["blocker_type"]: row for row in _payload()["completion_proof_blockers"]}

    for blocker_type in aggregator.BLOCKER_TYPES:
        assert blocker_type in blockers
        assert blockers[blocker_type]["fail_closed"] is True
    assert blockers["COMPLETION_CLAIM_WITHOUT_EMAIL_RECEIPT"]["severity"] == "critical"
    assert blockers["EXTERNAL_ACTION_ATTEMPTED"]["severity"] == "critical"


def test_all_live_authority_false():
    payload = _payload()

    assert payload["machine_proof"]["all_live_authority_false"] is True
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    for key in [
        "completion_write_performed",
        "email_send_performed",
        "mail_send_performed",
        "gmail_send_performed",
        "coupa_access_performed",
        "coupa_submit_performed",
        "browser_access_performed",
        "payment_tracking_write_performed",
        "visual_artifact_spawn_performed",
        "external_action_performed",
        "workflow_run_performed",
        "agent_dispatch_performed",
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
    payload = json.loads((tmp_path / aggregator.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / aggregator.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == aggregator.READ_MODEL_ID
    assert summary["not_complete_status"] == "COMPLETION_BLOCKED_NO_RECEIPTS"
    assert summary["complete_fixture_status"] == "COMPLETION_CONFIRMED"
    assert summary["all_live_authority_false"] is True
    assert payload["schema_version"] == aggregator.SCHEMA_VERSION
    assert "Invoice Delivery Completion Proof Aggregator" in operator
    assert "No completion write" in operator


def test_generated_outputs_have_no_raw_provider_ids_private_bodies_or_secrets(tmp_path):
    payload = _payload()
    aggregator.write_exports(payload, tmp_path)
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())

    assert "actual secret value" not in text.lower()
    assert "raw private body value" not in text.lower()
    assert "credential value" not in text.lower()
    assert "token value" not in text.lower()
    assert "raw provider id value" not in text.lower()
    assert "raw body payload" not in text.lower()
    assert "AKIA" not in text
    assert not re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)
