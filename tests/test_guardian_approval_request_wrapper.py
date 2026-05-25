import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import guardian_approval_request_wrapper as wrapper
from scripts.export_guardian_approval_request_wrapper import main as export_main


FIXED_NOW = "2026-05-25T23:58:00+00:00"


def _payload() -> dict:
    return wrapper.build_payload(generated_at=FIXED_NOW)


def test_required_models_exist():
    for name in [
        "GuardianApprovalRequestWrapper",
        "GuardianApprovalRequest",
        "GuardianRiskReview",
        "GuardianProofReview",
        "GuardianApprovalReadback",
        "GuardianApprovalReceipt",
        "GuardianApprovalBlocker",
    ]:
        assert hasattr(wrapper, name)


def test_capital_hilton_email_approval_packet_exists():
    example = _payload()["examples"]["capital_hilton_email_approval"]
    request = example["approval_request"]

    assert request["requested_action"] == "SEND_EMAIL"
    assert request["risk_level"] == "HIGH"
    assert request["exact_approval_phrase"] == "APPROVE SEND_EMAIL capital_hilton_invoice_covenant_v0"
    assert "recipient/contact confirmed" in request["required_proofs"]
    assert "invoice artifact/hash exists" in request["required_proofs"]
    assert "attachment ref exists" in request["required_proofs"]
    assert "send body reviewed" in request["required_proofs"]
    assert example["readback"]["status"] == "APPROVAL_PACKET_READY"
    assert example["receipt"]["action_authorized"] is False
    assert example["receipt"]["action_executed"] is False


def test_coupa_submit_packet_exists_and_has_no_live_access():
    example = _payload()["examples"]["coupa_submit_approval"]
    request = example["approval_request"]

    assert request["requested_action"] == "SUBMIT_COUPA"
    assert request["risk_level"] == "CRITICAL"
    assert "PO/reference confirmed" in request["required_proofs"]
    assert "invoice values confirmed" in request["required_proofs"]
    assert "portal action reviewed" in request["required_proofs"]
    assert example["readback"]["status"] == "NEEDS_MORE_PROOF"
    assert example["receipt"]["external_authority"] is False
    assert "Coupa submit" in request["blocked_actions"]
    assert "browser automation" in request["blocked_actions"]


def test_secret_reveal_packet_exists_and_uses_refs_only():
    example = _payload()["examples"]["secret_reveal"]
    request = example["approval_request"]

    assert request["requested_action"] == "REVEAL_SECRET"
    assert request["risk_level"] == "CRITICAL"
    assert "protected secret token ref" in request["required_inputs"]
    assert request["protected_refs"] == ("secret_ref:coupa_password_task_scoped",)
    assert example["proof_review"]["proof_status"] == "PROOF_PROTECTED_REVIEW_REQUIRED"
    assert example["receipt"]["operator_approved"] is False
    assert example["receipt"]["action_authorized"] is False


def test_test_package_packet_exists():
    example = _payload()["examples"]["test_package"]
    request = example["approval_request"]

    assert request["requested_action"] == "TEST_WORKFLOW_PACKAGE"
    assert request["risk_level"] == "MEDIUM"
    assert example["proof_review"]["proof_status"] == "PROOF_READY"
    assert example["proof_review"]["completion_allowed"] is True
    assert example["receipt"]["action_executed"] is False
    assert example["receipt"]["external_authority"] is False


def test_missing_proof_blocker_exists_in_example():
    example = _payload()["examples"]["missing_proof"]

    assert example["readback"]["status"] == "NEEDS_MORE_PROOF"
    assert "invoice artifact/hash exists" in example["readback"]["missing_items"]
    assert "attachment ref exists" in example["readback"]["missing_items"]
    assert "missing proof refs" in example["readback"]["how_to_fix"]


def test_destructive_action_blocked():
    example = _payload()["examples"]["destructive_action"]

    assert example["approval_request"]["requested_action"] == "MUTATE_FILE"
    assert example["approval_request"]["risk_level"] == "CRITICAL"
    assert example["risk_review"]["recommendation"] == "BLOCKED_UNSAFE"
    assert example["readback"]["status"] == "BLOCKED_UNSAFE"
    assert "scoped non-destructive" in example["readback"]["how_to_fix"]


def test_exact_approval_phrase_modeled():
    payload = _payload()

    assert payload["examples"]["capital_hilton_email_approval"]["approval_request"]["exact_approval_phrase"].startswith("APPROVE SEND_EMAIL ")
    assert payload["examples"]["coupa_submit_approval"]["approval_request"]["exact_approval_phrase"].startswith("APPROVE SUBMIT_COUPA ")
    assert "approval phrase" in " ".join(payload["wrapper"]["approval_phrase_policy"]).lower()


def test_operator_approval_and_execution_flags_false():
    for example in _payload()["examples"].values():
        receipt = example["receipt"]
        assert receipt["operator_approved"] is False
        assert receipt["action_authorized"] is False
        assert receipt["action_executed"] is False
        assert receipt["external_authority"] is False


def test_all_blockers_exist_and_fail_closed():
    blockers = {row["blocker_type"]: row for row in _payload()["guardian_approval_blockers"]}

    for blocker_type in wrapper.BLOCKER_TYPES:
        assert blocker_type in blockers
        assert blockers[blocker_type]["fail_closed"] is True
    assert blockers["MISSING_PROOF"]["severity"] == "critical"
    assert blockers["SECRET_REVEAL_UNGATED"]["severity"] == "critical"


def test_all_live_authority_false():
    payload = _payload()

    assert payload["machine_proof"]["all_live_authority_false"] is True
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    for key in [
        "approval_execution_performed",
        "action_authorization_performed",
        "email_send_performed",
        "coupa_submit_performed",
        "browser_access_performed",
        "secret_reveal_performed",
        "file_mutation_performed",
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
    payload = json.loads((tmp_path / wrapper.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / wrapper.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == wrapper.READ_MODEL_ID
    assert summary["all_live_authority_false"] is True
    assert "capital_hilton_email_approval" in summary["examples"]
    assert payload["schema_version"] == wrapper.SCHEMA_VERSION
    assert "Guardian Approval Request Wrapper" in operator
    assert "No live approval execution" in operator


def test_generated_outputs_have_no_credentials_or_private_bodies(tmp_path):
    payload = _payload()
    wrapper.write_exports(payload, tmp_path)
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())

    assert "actual secret value" not in text.lower()
    assert "raw private body value" not in text.lower()
    assert "credential value" not in text.lower()
    assert "token value" not in text.lower()
    assert "AKIA" not in text
    assert not re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)
