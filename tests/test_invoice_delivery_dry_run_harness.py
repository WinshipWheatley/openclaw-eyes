import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import invoice_delivery_dry_run_harness as harness
from scripts.export_invoice_delivery_dry_run_harness import main as export_main


FIXED_NOW = "2026-05-25T23:59:00+00:00"


def _payload() -> dict:
    return harness.build_payload(generated_at=FIXED_NOW)


def _step(example: dict, step_type: str) -> dict:
    for row in example["steps"]:
        if row["step_type"] == step_type:
            return row
    raise AssertionError(f"missing step {step_type}")


def _adapter(example: dict, adapter_type: str) -> dict:
    for row in example["adapter_checks"]:
        if row["adapter_type"] == adapter_type:
            return row
    raise AssertionError(f"missing adapter {adapter_type}")


def _proof(example: dict, proof_type: str) -> dict:
    for row in example["proof_checks"]:
        if row["proof_type"] == proof_type:
            return row
    raise AssertionError(f"missing proof {proof_type}")


def test_required_models_exist():
    for name in [
        "InvoiceDeliveryDryRunHarness",
        "InvoiceDeliveryDryRunRequest",
        "InvoiceDeliveryDryRunResult",
        "DryRunStep",
        "DryRunAdapterCheck",
        "DryRunProofCheck",
        "DryRunReadback",
        "InvoiceDeliveryDryRunBlocker",
    ]:
        assert hasattr(harness, name)


def test_capital_hilton_current_not_ready_example_exists():
    example = _payload()["examples"]["capital_hilton_current_not_ready"]
    result = example["result"]

    assert result["source_run_package_ref"] == "invoice_delivery_run_package_capital_hilton_not_ready_v0"
    assert result["status"] in ("DRY_RUN_BLOCKED_MISSING_INPUTS", "DRY_RUN_BLOCKED_MISSING_PROOF", "DRY_RUN_BLOCKED_MISSING_ADAPTER")
    assert "Validate Capital Hilton dates/rate basis" in result["ready_steps"]
    assert "Verify invoice artifact/hash" in result["blocked_steps"]
    assert "confirmed Coupa PO/reference" in result["missing_inputs"]
    assert "INVOICE_ARTIFACT_HASH" in result["missing_proofs"]
    assert "EMAIL_SEND_ADAPTER" in result["missing_adapters"]
    assert "Nothing was sent, submitted, opened, approved, or changed." in result["operator_message"]
    assert result["how_to_fix"]


def test_ready_for_review_not_execution_example_exists():
    example = _payload()["examples"]["capital_hilton_ready_for_review_not_execution"]
    result = example["result"]

    assert "Verify invoice artifact/hash" in result["ready_steps"]
    assert "Verify email package" in result["ready_steps"]
    assert "Verify Coupa package" in result["ready_steps"]
    assert "Verify Guardian approval" in result["blocked_steps"]
    assert result["status"] in ("DRY_RUN_BLOCKED_MISSING_APPROVAL", "DRY_RUN_BLOCKED_MISSING_ADAPTER")
    assert "package can be reviewed" not in result["operator_message"].lower()
    assert "not executable" in result["operator_message"]
    for row in example["steps"]:
        assert row["external_action"] is False


def test_dry_run_steps_have_expected_external_boundary():
    example = _payload()["examples"]["capital_hilton_current_not_ready"]

    assert _step(example, "VALIDATE_DELIVERY_FACTS")["ready"] is True
    assert _step(example, "VERIFY_EMAIL_PACKAGE")["would_run"] is True
    assert _step(example, "VERIFY_EMAIL_PACKAGE")["external_action"] is False
    assert _step(example, "VERIFY_COUPA_ADAPTER")["required_adapter"] == "COUPA_BROWSER_ADAPTER"
    for row in example["steps"]:
        assert row["external_action"] is False


def test_missing_email_adapter_detected():
    example = _payload()["examples"]["missing_email_adapter"]
    adapter = _adapter(example, "EMAIL_SEND_ADAPTER")

    assert adapter["required"] is True
    assert adapter["available"] is False
    assert adapter["gated"] is True
    assert "gated email send adapter" in adapter["next_safe_move"]
    assert "EMAIL_SEND_ADAPTER" in example["result"]["missing_adapters"]


def test_missing_coupa_adapter_detected():
    example = _payload()["examples"]["missing_coupa_adapter"]
    browser_adapter = _adapter(example, "COUPA_BROWSER_ADAPTER")
    submit_adapter = _adapter(example, "COUPA_SUBMIT_ADAPTER")

    assert browser_adapter["available"] is False
    assert submit_adapter["available"] is False
    assert browser_adapter["gated"] is True
    assert submit_adapter["gated"] is True
    assert "COUPA_BROWSER_ADAPTER" in example["result"]["missing_adapters"]
    assert "COUPA_SUBMIT_ADAPTER" in example["result"]["missing_adapters"]


def test_proof_checks_capture_missing_receipts():
    example = _payload()["examples"]["capital_hilton_ready_for_review_not_execution"]

    assert _proof(example, "DELIVERY_FACTS_RECEIPT")["available"] is True
    assert _proof(example, "INVOICE_ARTIFACT_HASH")["available"] is True
    assert _proof(example, "EMAIL_SEND_RECEIPT")["available"] is False
    assert _proof(example, "COUPA_SUBMIT_RECEIPT")["available"] is False
    assert _proof(example, "PAYMENT_TRACKING_RECEIPT")["available"] is False


def test_completion_claim_blocked():
    example = _payload()["examples"]["completion_claim_blocked"]

    assert example["result"]["status"] == "DRY_RUN_BLOCKED_MISSING_PROOF"
    assert example["readback"]["status"] == "DRY_RUN_BLOCKED_MISSING_PROOF"
    assert "completion" in example["result"]["operator_headline"].lower()
    assert "Collect future send, submit, approval, attachment, and payment receipts" in example["result"]["how_to_fix"]
    assert _payload()["machine_proof"]["completion_claimed"] is False


def test_all_blockers_exist_and_fail_closed():
    blockers = {row["blocker_type"]: row for row in _payload()["invoice_delivery_dry_run_blockers"]}

    for blocker_type in harness.BLOCKER_TYPES:
        assert blocker_type in blockers
        assert blockers[blocker_type]["fail_closed"] is True
    assert blockers["EXTERNAL_ACTION_ATTEMPTED"]["severity"] == "critical"
    assert blockers["COMPLETION_CLAIM_ATTEMPTED"]["severity"] == "critical"
    assert blockers["SEND_ADAPTER_MISSING"]["severity"] == "critical"


def test_all_external_action_flags_false():
    payload = _payload()

    assert payload["machine_proof"]["all_live_authority_false"] is True
    assert payload["machine_proof"]["completion_claimed"] is False
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    for example in payload["examples"].values():
        for row in example["steps"]:
            assert row["external_action"] is False


def test_export_writes_json_and_operator_markdown(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / harness.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / harness.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == harness.READ_MODEL_ID
    assert summary["all_live_authority_false"] is True
    assert "capital_hilton_current_not_ready" in summary["examples"]
    assert payload["schema_version"] == harness.SCHEMA_VERSION
    assert "Invoice Delivery Dry-Run Harness" in operator
    assert "No dry-run external action" in operator


def test_generated_outputs_have_no_raw_credentials_secrets_or_private_bodies(tmp_path):
    payload = _payload()
    harness.write_exports(payload, tmp_path)
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())

    assert "actual secret value" not in text.lower()
    assert "raw private body value" not in text.lower()
    assert "credential value" not in text.lower()
    assert "token value" not in text.lower()
    assert "raw credential value" not in text.lower()
    assert "private body" not in text.lower()
    assert "AKIA" not in text
    assert not re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)
