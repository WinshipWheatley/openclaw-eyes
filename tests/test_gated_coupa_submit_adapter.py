import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gated_coupa_submit_adapter as adapter
from scripts.export_gated_coupa_submit_adapter import main as export_main
from scripts.run_gated_coupa_submit_adapter import main as run_main


FIXED_NOW = "2026-05-25T23:59:00+00:00"


def _payload() -> dict:
    return adapter.build_payload(generated_at=FIXED_NOW)


def test_required_models_exist():
    for name in [
        "GatedCoupaSubmitAdapter",
        "CoupaSubmitRequest",
        "CoupaSubmitGateCheck",
        "CoupaProviderBoundary",
        "CoupaSubmitReadinessReadback",
        "CoupaSubmitReceipt",
        "CoupaSubmitAdapterBlocker",
    ]:
        assert hasattr(adapter, name)


def test_capital_hilton_missing_po_blocks():
    example = _payload()["examples"]["capital_hilton_submit_blocked_missing_po"]

    assert example["readiness_readback"]["status"] == "SUBMIT_BLOCKED_MISSING_PO"
    assert "confirmed Coupa PO/reference" in example["gate_check"]["missing_gates"]
    assert "provide, attach, or confirm" in example["readiness_readback"]["how_to_fix"].lower()
    assert example["submit_receipt"]["submitted"] is False


def test_missing_secret_ref_blocks():
    example = _payload()["examples"]["capital_hilton_submit_blocked_missing_secret_ref"]

    assert example["readiness_readback"]["status"] == "SUBMIT_BLOCKED_MISSING_SECRET_REF"
    assert "protected Coupa credential/secret ref" in example["gate_check"]["missing_gates"]
    assert "future Enter Secret protected flow" in example["readiness_readback"]["how_to_fix"]
    assert example["gate_check"]["secret_ref_present"] is False


def test_missing_approval_blocks():
    example = _payload()["examples"]["capital_hilton_submit_blocked_missing_approval"]

    assert example["readiness_readback"]["status"] == "SUBMIT_BLOCKED_MISSING_GATES"
    assert "Guardian approval ref" in example["gate_check"]["missing_gates"]
    assert "exact operator approval receipt ref" in example["gate_check"]["missing_gates"]
    assert "Create the Guardian approval packet" in example["readiness_readback"]["how_to_fix"]


def test_dry_run_ready_but_not_executed():
    example = _payload()["examples"]["capital_hilton_dry_run_ready_not_executed"]

    assert example["readiness_readback"]["status"] == "SUBMIT_DRY_RUN_READY"
    assert example["gate_check"]["missing_gates"] == ()
    assert example["submit_request"]["requested_mode"] == "DRY_RUN_ONLY"
    assert example["submit_request"]["submit_authority"] is False
    assert example["provider_boundary"]["live_browser_allowed"] is False
    assert example["provider_boundary"]["live_submit_allowed"] is False
    assert example["submit_receipt"]["submitted"] is False
    assert example["submit_receipt"]["provider_confirmation_ref"] == ""
    assert "nothing was opened" in example["readiness_readback"]["operator_message"].lower()


def test_generic_submit_it_blocked_exact_approval_required():
    example = _payload()["examples"]["generic_submit_it_blocked"]

    assert example["readiness_readback"]["status"] == "SUBMIT_BLOCKED_MISSING_GATES"
    assert "exact approval phrase ref" in example["gate_check"]["missing_gates"]
    assert example["gate_check"]["exact_phrase_matched"] is False
    assert adapter.EXACT_APPROVAL_DISPLAY in example["readiness_readback"]["how_to_fix"]


def test_provider_missing_blocks():
    example = _payload()["examples"]["provider_missing"]

    assert example["submit_request"]["provider_target"] == "COUPA_BROWSER_ADAPTER"
    assert example["provider_boundary"]["provider_available"] is False
    assert example["provider_boundary"]["live_browser_allowed"] is False
    assert example["provider_boundary"]["live_submit_allowed"] is False
    assert example["readiness_readback"]["status"] == "SUBMIT_BLOCKED_MISSING_PROVIDER"
    assert "future gated Coupa/browser adapter" in example["readiness_readback"]["how_to_fix"]


def test_raw_credential_blocks():
    example = _payload()["examples"]["raw_credential_blocked"]

    assert example["readiness_readback"]["status"] == "SUBMIT_BLOCKED_PRIVACY_BOUNDARY"
    assert "raw credential" in example["readiness_readback"]["operator_message"].lower()
    assert "raw credential removed from request" in example["gate_check"]["missing_gates"]
    assert example["submit_receipt"]["submitted"] is False


def test_submit_receipts_are_not_submitted_and_external_false():
    for example in _payload()["examples"].values():
        receipt = example["submit_receipt"]
        assert receipt["submitted"] is False
        assert receipt["external_authority"] is False
        assert receipt["provider_confirmation_ref"] == ""


def test_all_blockers_exist_and_fail_closed():
    blockers = {row["blocker_type"]: row for row in _payload()["coupa_submit_adapter_blockers"]}

    for blocker_type in adapter.BLOCKER_TYPES:
        assert blocker_type in blockers
        assert blockers[blocker_type]["fail_closed"] is True
    assert blockers["GENERIC_APPROVAL_USED"]["severity"] == "critical"
    assert blockers["PROVIDER_CALLED_IN_TEST"]["severity"] == "critical"


def test_all_live_authority_false_and_no_provider_call():
    payload = _payload()

    assert payload["machine_proof"]["all_live_authority_false"] is True
    assert payload["machine_proof"]["provider_call_performed"] is False
    assert payload["machine_proof"]["browser_open_performed"] is False
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    for key in [
        "coupa_access_performed",
        "coupa_submit_performed",
        "portal_login_performed",
        "secret_reveal_performed",
        "payment_action_performed",
        "external_action_performed",
        "workflow_run_performed",
        "agent_dispatch_performed",
        "credential_handling_performed",
        "raw_credential_included",
        "raw_body_ingestion_performed",
        "mac_sync_import_performed",
        "swift_change_performed",
        "git_push_performed",
    ]:
        assert payload["machine_proof"][key] is False


def test_static_provider_audit_is_reference_only():
    audit = _payload()["coupa_provider_static_audit"]

    assert audit["repo_b_coupa_or_browser_adapter_found"] is False
    assert audit["repo_a_future_candidate_ref"] == "capital_hilton_coupa_po_retrieval_automation_candidate"
    assert audit["called"] is False
    assert audit["browser_opened"] is False


def test_export_and_run_scripts_write_outputs(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / adapter.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / adapter.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == adapter.READ_MODEL_ID
    assert summary["dry_run_status"] == "SUBMIT_DRY_RUN_READY"
    assert summary["all_live_authority_false"] is True
    assert payload["schema_version"] == adapter.SCHEMA_VERSION
    assert "Gated Coupa Submit Adapter" in operator
    assert "No Coupa access" in operator

    assert run_main(["--fixture", "capital_hilton_dry_run", "--export-root", str(tmp_path), "--format", "json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["examples"]["capital_hilton_dry_run_ready_not_executed"]["submit_receipt"]["submitted"] is False


def test_generated_outputs_have_no_raw_po_credentials_or_secrets(tmp_path):
    payload = _payload()
    adapter.write_exports(payload, tmp_path)
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())

    assert "actual secret value" not in text.lower()
    assert "raw private body value" not in text.lower()
    assert "credential value" not in text.lower()
    assert "token value" not in text.lower()
    assert "raw password value" not in text.lower()
    assert "raw credential value" not in text.lower()
    assert "session cookie value" not in text.lower()
    assert "AKIA" not in text
    assert not re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)
    assert not re.search(r"\bPO[-_ ]?\d{5,}\b", text)
