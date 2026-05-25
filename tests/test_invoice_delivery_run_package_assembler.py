import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import invoice_delivery_run_package_assembler as assembler
from scripts.export_invoice_delivery_run_package_assembler import main as export_main


FIXED_NOW = "2026-05-25T23:59:00+00:00"


def _payload() -> dict:
    return assembler.build_payload(generated_at=FIXED_NOW)


def _component(example: dict, component_type: str) -> dict:
    for row in example["components"]:
        if row["component_type"] == component_type:
            return row
    raise AssertionError(f"missing component {component_type}")


def test_required_models_exist():
    for name in [
        "InvoiceDeliveryRunPackageAssembler",
        "InvoiceDeliveryRunPackage",
        "InvoiceDeliveryComponentStatus",
        "InvoiceDeliveryReadinessReadback",
        "InvoiceDeliveryExecutionGate",
        "InvoiceDeliveryCompletionTarget",
        "InvoiceDeliveryRunPackageBlocker",
    ]:
        assert hasattr(assembler, name)


def test_capital_hilton_not_ready_example_exists():
    example = _payload()["examples"]["capital_hilton_not_ready"]
    package = example["run_package"]
    readback = example["readiness_readback"]

    assert package["source_workflow_ref"] == "capital_hilton_invoice_workflow"
    assert package["readiness_status"] == "NOT_READY_MISSING_INPUTS"
    assert "confirmed Coupa PO/reference" in package["missing_items"]
    assert "final invoice artifact/hash" in package["missing_items"]
    assert "confirmed recipient/contact route" in package["missing_items"]
    assert "Guardian approval" in package["missing_items"]
    assert "OpenClaw has assembled the Capital Hilton invoice delivery run package shape" in readback["operator_message"]
    assert "Nothing has been sent, submitted, opened, approved, or recorded as complete." in readback["operator_message"]
    assert readback["how_to_fix"]


def test_ready_for_review_not_execution_example_exists():
    example = _payload()["examples"]["capital_hilton_ready_for_review_not_execution"]
    package = example["run_package"]
    gate = example["execution_gate"]
    readback = example["readiness_readback"]

    assert package["readiness_status"] == "WAITING_FOR_OPERATOR_APPROVAL"
    assert package["invoice_artifact_ref"].startswith("invoice_artifact_ref:")
    assert package["email_delivery_package_ref"].startswith("email_delivery_package_")
    assert package["coupa_package_ref"].startswith("coupa_package_")
    assert package["guardian_approval_ref"].startswith("guardian_approval_")
    assert readback["status"] == "RUN_PACKAGE_READY_FOR_REVIEW"
    assert gate["external_action_allowed"] is False
    assert gate["workflow_run_allowed"] is False
    assert gate["email_send_allowed"] is False
    assert gate["coupa_submit_allowed"] is False
    assert gate["browser_allowed"] is False
    assert gate["action_executed"] is False


def test_missing_artifact_blocks_attachment():
    example = _payload()["examples"]["missing_artifact_blocks_attachment"]
    artifact = _component(example, "INVOICE_ARTIFACT")

    assert artifact["ready"] is False
    assert artifact["status"] == "MISSING_ARTIFACT_AND_HASH"
    assert "Winship-branded invoice PDF/XLSX" in artifact["how_to_fix"]
    assert example["readiness_readback"]["status"] == "NOT_READY_MISSING_ARTIFACT"


def test_missing_coupa_package_blocks_official_payment_rail():
    example = _payload()["examples"]["missing_coupa_package_blocks_payment_rail"]
    coupa = _component(example, "COUPA_PACKAGE")

    assert coupa["ready"] is False
    assert coupa["status"] == "MISSING_COUPA_PACKAGE"
    assert "Confirm PO/reference" in coupa["how_to_fix"]
    assert example["readiness_readback"]["status"] == "NOT_READY_MISSING_COUPA_PACKAGE"


def test_completion_target_blocked_without_receipts():
    example = _payload()["examples"]["completion_target_blocked"]
    completion = example["completion_target"]

    assert completion["completion_label"] == "INVOICE_SENT_AND_RECORDED"
    assert completion["completion_allowed"] is False
    assert "email send receipt, future" in completion["missing_receipts"]
    assert "Coupa submit/confirmation receipt, future if Coupa required" in completion["missing_receipts"]
    assert "payment tracking update receipt, future" in completion["missing_receipts"]
    assert "Nothing has been sent, submitted, opened, approved, or recorded as complete." in completion["completion_readback"]


def test_all_blockers_exist_and_fail_closed():
    blockers = {row["blocker_type"]: row for row in _payload()["invoice_delivery_run_package_blockers"]}

    for blocker_type in assembler.BLOCKER_TYPES:
        assert blocker_type in blockers
        assert blockers[blocker_type]["fail_closed"] is True
    assert blockers["EMAIL_SEND_ATTEMPTED"]["severity"] == "critical"
    assert blockers["COUPA_SUBMIT_ATTEMPTED"]["severity"] == "critical"
    assert blockers["COMPLETION_CLAIM_WITHOUT_RECEIPTS"]["severity"] == "critical"


def test_all_action_flags_false_and_no_completion_claim():
    payload = _payload()
    example = payload["examples"]["capital_hilton_ready_for_review_not_execution"]
    gate = example["execution_gate"]

    assert payload["machine_proof"]["all_live_authority_false"] is True
    assert payload["machine_proof"]["completion_claimed"] is False
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    for key in [
        "external_action_allowed",
        "workflow_run_allowed",
        "email_send_allowed",
        "coupa_submit_allowed",
        "browser_allowed",
        "action_executed",
    ]:
        assert gate[key] is False


def test_export_writes_json_and_operator_markdown(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / assembler.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / assembler.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == assembler.READ_MODEL_ID
    assert summary["all_live_authority_false"] is True
    assert "capital_hilton_not_ready" in summary["examples"]
    assert payload["schema_version"] == assembler.SCHEMA_VERSION
    assert "Invoice Delivery Run Package Assembler" in operator
    assert "No run package execution" in operator


def test_generated_outputs_have_no_raw_credentials_secrets_or_private_bodies(tmp_path):
    payload = _payload()
    assembler.write_exports(payload, tmp_path)
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())

    assert "actual secret value" not in text.lower()
    assert "raw private body value" not in text.lower()
    assert "credential value" not in text.lower()
    assert "token value" not in text.lower()
    assert "raw credential value" not in text.lower()
    assert "private body" not in text.lower()
    assert "AKIA" not in text
    assert not re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)
