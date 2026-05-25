import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import coupa_supplier_portal_package_compiler as compiler
from scripts.export_coupa_supplier_portal_package_compiler import main as export_main


FIXED_NOW = "2026-05-25T23:59:00+00:00"


def _payload() -> dict:
    return compiler.build_payload(generated_at=FIXED_NOW)


def test_required_models_exist():
    for name in [
        "CoupaSupplierPortalPackageCompiler",
        "CoupaSupplierPortalPackage",
        "CoupaPOReference",
        "CoupaInvoiceValueSet",
        "CoupaPortalGate",
        "CoupaPackageReadback",
        "CoupaProofPlan",
        "CoupaPackageBlocker",
    ]:
        assert hasattr(compiler, name)


def test_capital_hilton_missing_po_example_exists():
    example = _payload()["examples"]["capital_hilton_missing_po"]

    assert example["package"]["source_workflow_ref"] == "capital_hilton_invoice_workflow"
    assert example["package"]["po_status"] == "PO_MISSING"
    assert example["readback"]["status"] == "NOT_READY_MISSING_PO"
    assert "Coupa PO/reference" in example["readback"]["how_to_fix"]
    assert "Nothing has been opened or submitted" in example["readback"]["operator_message"]


def test_complete_except_approval_example_exists_and_does_not_submit():
    example = _payload()["examples"]["capital_hilton_complete_except_approval"]

    assert example["package"]["po_status"] == "PO_CONFIRMED"
    assert example["package"]["credential_ref_status"] == "PROTECTED_SECRET_REF_PRESENT_FUTURE_GATED"
    assert example["package"]["submit_gate_status"] == "READY_FOR_GUARDIAN_REVIEW"
    assert example["package"]["portal_action_status"] == "PACKAGE_ONLY"
    assert example["readback"]["status"] == "NOT_READY_MISSING_APPROVAL"
    assert example["portal_gate"]["coupa_access_allowed"] is False
    assert example["portal_gate"]["coupa_submit_allowed"] is False
    assert example["portal_gate"]["browser_allowed"] is False
    assert example["portal_gate"]["external_authority"] is False
    assert example["portal_gate"]["action_executed"] is False


def test_po_reference_uses_tokenized_safe_ref():
    example = _payload()["examples"]["capital_hilton_complete_except_approval"]
    po = example["po_reference"]

    assert po["safe_display_label"] == "Capital Hilton Coupa PO/reference confirmed"
    assert po["tokenized_po_ref"].startswith("po_token_ref:")
    assert po["protected_ref_required"] is True
    assert po["confirmation_status"] == "PO_CONFIRMED"


def test_invoice_values_are_confirmed_from_refs():
    values = _payload()["examples"]["capital_hilton_complete_except_approval"]["invoice_values"]

    assert values["dates_ref"].startswith("dates_ref:")
    assert values["rate_ref"].startswith("rate_ref:")
    assert values["subtotal_ref"].startswith("subtotal_ref:")
    assert values["currency"] == "USD"
    assert values["confirmation_status"] == "VALUES_CONFIRMED"
    assert values["proof_refs"]


def test_missing_secret_ref_blocks_without_raw_credential_request():
    example = _payload()["examples"]["missing_secret_ref"]

    assert example["package"]["credential_ref_status"] == "PROTECTED_SECRET_REF_MISSING"
    assert example["readback"]["status"] == "NOT_READY_MISSING_SECRET_REF"
    assert "Enter Secret" in example["readback"]["how_to_fix"]
    assert "raw credential hidden" in example["readback"]["how_to_fix"]
    assert example["portal_gate"]["required_secret_ref"] == "missing"


def test_attempted_coupa_submit_blocks():
    example = _payload()["examples"]["attempted_coupa_submit"]

    assert example["package"]["submit_gate_status"] == "SUBMIT_BLOCKED"
    assert "Coupa submit attempted but blocked" in example["package"]["missing_inputs"]
    assert example["readback"]["status"] == "BLOCKED_SUBMIT_GATE"
    assert example["portal_gate"]["coupa_submit_allowed"] is False
    assert example["portal_gate"]["action_executed"] is False


def test_attempted_browser_blocks():
    example = _payload()["examples"]["attempted_browser"]

    assert example["package"]["browser_gate_status"] == "BROWSER_BLOCKED"
    assert "browser attempted but blocked" in example["package"]["missing_inputs"]
    assert example["readback"]["status"] == "BLOCKED_BROWSER_GATE"
    assert example["portal_gate"]["browser_allowed"] is False


def test_proof_plan_has_future_completion_target_only():
    proof_plan = _payload()["examples"]["capital_hilton_complete_except_approval"]["proof_plan"]

    assert proof_plan["completion_label"] == "COUPA INVOICE SUBMITTED"
    assert proof_plan["completion_allowed"] is False
    assert "exact operator approval receipt" in proof_plan["missing_proofs"]
    assert "future portal submission receipt" in proof_plan["missing_proofs"]
    assert "future Coupa confirmation/proof" in proof_plan["missing_proofs"]


def test_all_blockers_exist_and_fail_closed():
    blockers = {row["blocker_type"]: row for row in _payload()["coupa_package_blockers"]}

    for blocker_type in compiler.BLOCKER_TYPES:
        assert blocker_type in blockers
        assert blockers[blocker_type]["fail_closed"] is True
    assert blockers["COUPA_SUBMIT_ATTEMPTED"]["severity"] == "critical"
    assert blockers["BROWSER_ATTEMPTED"]["severity"] == "critical"
    assert blockers["RAW_CREDENTIAL_INCLUDED"]["severity"] == "critical"


def test_all_live_authority_false():
    payload = _payload()

    assert payload["machine_proof"]["all_live_authority_false"] is True
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    for key in [
        "coupa_access_performed",
        "coupa_submit_performed",
        "browser_access_performed",
        "portal_login_performed",
        "secret_reveal_performed",
        "payment_action_performed",
        "approval_execution_performed",
        "workflow_run_performed",
        "agent_dispatch_performed",
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
    payload = json.loads((tmp_path / compiler.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / compiler.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == compiler.READ_MODEL_ID
    assert summary["all_live_authority_false"] is True
    assert "capital_hilton_missing_po" in summary["examples"]
    assert payload["schema_version"] == compiler.SCHEMA_VERSION
    assert "Coupa Supplier Portal Package Compiler" in operator
    assert "No Coupa access" in operator


def test_generated_outputs_have_no_raw_credentials_secrets_or_private_bodies(tmp_path):
    payload = _payload()
    compiler.write_exports(payload, tmp_path)
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())

    assert "actual secret value" not in text.lower()
    assert "raw private body value" not in text.lower()
    assert "credential value" not in text.lower()
    assert "token value" not in text.lower()
    assert "raw credential value" not in text.lower()
    assert "raw po value" not in text.lower()
    assert "AKIA" not in text
    assert not re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)
