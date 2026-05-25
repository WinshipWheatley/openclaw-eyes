import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import email_delivery_package_compiler as compiler
from scripts.export_email_delivery_package_compiler import main as export_main


FIXED_NOW = "2026-05-25T23:59:00+00:00"


def _payload() -> dict:
    return compiler.build_payload(generated_at=FIXED_NOW)


def test_required_models_exist():
    for name in [
        "EmailDeliveryPackageCompiler",
        "EmailDeliveryPackage",
        "EmailRecipientRef",
        "EmailAttachmentRef",
        "EmailSendGate",
        "EmailDeliveryReadback",
        "EmailDeliveryProofPlan",
        "EmailDeliveryPackageBlocker",
    ]:
        assert hasattr(compiler, name)


def test_capital_hilton_example_exists_and_is_not_sent():
    example = _payload()["examples"]["capital_hilton_complete_except_approval"]

    assert example["package"]["source_workflow_ref"] == "capital_hilton_invoice_workflow"
    assert example["package"]["source_draft_ref"].startswith("cassandra_draft_ref:")
    assert example["package"]["source_approval_request_ref"] == "guardian_approval_capital_hilton_email_v0"
    assert example["package"]["delivery_status"] == "NOT_SENT"
    assert example["send_gate"]["send_allowed"] is False
    assert example["send_gate"]["send_executed"] is False
    assert example["send_gate"]["external_authority"] is False
    assert "Nothing has been sent" in example["readback"]["operator_message"]
    assert "Guardian/operator approval" in example["readback"]["operator_message"]


def test_recipient_ref_is_tokenized_and_safe():
    recipient = _payload()["examples"]["capital_hilton_complete_except_approval"]["recipient"]

    assert recipient["safe_display_label"] == "Annette at Capital Hilton"
    assert recipient["tokenized_email_ref"].startswith("email_token_ref:")
    assert recipient["protected_ref_required"] is True
    assert recipient["confirmation_status"] in ("RECIPIENT_CANDIDATE", "RECIPIENT_CONFIRMED")


def test_attachment_ref_has_hash_and_no_body():
    attachment = _payload()["examples"]["capital_hilton_complete_except_approval"]["attachment"]

    assert attachment["artifact_ref"].startswith("artifact_ref:")
    assert attachment["hash_or_fingerprint_ref"].startswith("artifact_hash_ref:")
    assert attachment["approved_for_attachment"] is True
    assert "body" not in attachment


def test_missing_recipient_blocks_with_how_to_fix():
    example = _payload()["examples"]["missing_recipient"]

    assert example["package"]["recipient_status"] == "RECIPIENT_MISSING"
    assert example["readback"]["status"] == "NOT_READY_MISSING_RECIPIENT"
    assert "confirm" in example["readback"]["how_to_fix"].lower()


def test_missing_draft_blocks():
    example = _payload()["examples"]["missing_draft"]

    assert example["package"]["source_draft_ref"] == ""
    assert example["readback"]["status"] == "NOT_READY_MISSING_DRAFT"
    assert "Cassandra" in example["readback"]["how_to_fix"]


def test_missing_attachment_and_hash_block():
    missing_attachment = _payload()["examples"]["missing_attachment"]
    missing_hash = _payload()["examples"]["missing_attachment_hash"]

    assert missing_attachment["readback"]["status"] == "NOT_READY_MISSING_ATTACHMENT"
    assert "generate or attach" in missing_attachment["readback"]["how_to_fix"].lower()
    assert missing_hash["attachment"]["hash_or_fingerprint_ref"] == ""
    assert missing_hash["readback"]["status"] == "NOT_READY_MISSING_ATTACHMENT"
    assert "Hash/fingerprint" in missing_hash["readback"]["how_to_fix"]


def test_missing_approval_blocks():
    example = _payload()["examples"]["missing_approval"]

    assert example["package"]["source_approval_request_ref"] == ""
    assert example["readback"]["status"] == "NOT_READY_MISSING_APPROVAL"
    assert "Action Covenant" in example["readback"]["how_to_fix"]
    assert "Guardian approval request packet" in example["send_gate"]["missing_items"]


def test_send_attempt_blocks_and_all_gate_flags_false():
    example = _payload()["examples"]["attempted_send"]

    assert example["package"]["send_gate_status"] == "SEND_BLOCKED"
    assert "send attempted but blocked" in example["package"]["missing_inputs"]
    assert example["send_gate"]["send_allowed"] is False
    assert example["send_gate"]["send_executed"] is False
    assert example["send_gate"]["external_authority"] is False


def test_proof_plan_has_future_completion_target_only():
    example = _payload()["examples"]["capital_hilton_complete_except_approval"]
    proof_plan = example["proof_plan"]

    assert proof_plan["completion_label"] == "INVOICE SENT"
    assert proof_plan["completion_allowed"] is False
    assert "future send receipt" in proof_plan["missing_proofs"]
    assert "future attachment/send proof" in proof_plan["missing_proofs"]


def test_all_blockers_exist_and_fail_closed():
    blockers = {row["blocker_type"]: row for row in _payload()["email_delivery_blockers"]}

    for blocker_type in compiler.BLOCKER_TYPES:
        assert blocker_type in blockers
        assert blockers[blocker_type]["fail_closed"] is True
    assert blockers["SEND_ATTEMPTED"]["severity"] == "critical"
    assert blockers["RAW_ATTACHMENT_BODY_INCLUDED"]["severity"] == "critical"


def test_all_live_authority_false():
    payload = _payload()

    assert payload["machine_proof"]["all_live_authority_false"] is True
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    for key in [
        "email_delivery_performed",
        "email_send_performed",
        "mail_send_performed",
        "gmail_send_performed",
        "gmail_draft_created",
        "attachment_send_performed",
        "coupa_access_performed",
        "browser_access_performed",
        "approval_execution_performed",
        "workflow_run_performed",
        "agent_dispatch_performed",
        "external_action_performed",
        "credential_handling_performed",
        "raw_attachment_body_included",
        "raw_body_ingestion_performed",
        "mac_sync_import_performed",
        "swift_change_performed",
        "git_push_performed",
    ]:
        assert payload["machine_proof"][key] is False


def test_export_writes_json_and_operator_markdown(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / compiler.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / compiler.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == compiler.READ_MODEL_ID
    assert summary["all_live_authority_false"] is True
    assert "capital_hilton_complete_except_approval" in summary["examples"]
    assert payload["schema_version"] == compiler.SCHEMA_VERSION
    assert "Email Delivery Package Compiler" in operator
    assert "No email send" in operator


def test_generated_outputs_have_no_raw_email_attachment_or_secrets(tmp_path):
    payload = _payload()
    compiler.write_exports(payload, tmp_path)
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())

    assert "actual secret value" not in text.lower()
    assert "raw private body value" not in text.lower()
    assert "credential value" not in text.lower()
    assert "token value" not in text.lower()
    assert "raw attachment body value" not in text.lower()
    assert "attachment bytes" not in text.lower()
    assert "AKIA" not in text
    assert not re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)
