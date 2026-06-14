import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gated_email_send_adapter as adapter
from scripts.export_gated_email_send_adapter import main as export_main
from scripts.run_gated_email_send_adapter import main as run_main


FIXED_NOW = "2026-05-25T23:59:00+00:00"


def _payload() -> dict:
    return adapter.build_payload(generated_at=FIXED_NOW)


def test_required_models_exist():
    for name in [
        "GatedEmailSendAdapter",
        "EmailSendRequest",
        "EmailSendGateCheck",
        "EmailSendProviderBoundary",
        "EmailSendReadinessReadback",
        "EmailSendReceipt",
        "EmailSendAdapterBlocker",
    ]:
        assert hasattr(adapter, name)


def test_capital_hilton_missing_approval_blocks():
    example = _payload()["examples"]["capital_hilton_send_blocked_missing_approval"]

    assert example["readiness_readback"]["status"] == "SEND_BLOCKED_MISSING_GATES"
    assert "Guardian approval ref" in example["gate_check"]["missing_gates"]
    assert "exact operator approval receipt ref" in example["gate_check"]["missing_gates"]
    assert "Create the Guardian approval packet" in example["readiness_readback"]["how_to_fix"]
    assert example["send_receipt"]["sent"] is False


def test_missing_attachment_hash_blocks():
    example = _payload()["examples"]["capital_hilton_send_blocked_missing_attachment_hash"]

    assert example["readiness_readback"]["status"] == "SEND_BLOCKED_MISSING_GATES"
    assert "attachment hash/fingerprint ref" in example["gate_check"]["missing_gates"]
    assert "hash/fingerprint" in example["readiness_readback"]["how_to_fix"]
    assert example["gate_check"]["attachment_hashes_present"] is False


def test_dry_run_ready_but_not_executed():
    example = _payload()["examples"]["capital_hilton_dry_run_ready_not_executed"]

    assert example["readiness_readback"]["status"] == "SEND_DRY_RUN_READY"
    assert example["gate_check"]["missing_gates"] == ()
    assert example["send_request"]["requested_mode"] == "DRY_RUN_ONLY"
    assert example["send_request"]["send_authority"] is False
    assert example["send_receipt"]["sent"] is False
    assert example["send_receipt"]["provider_message_id_ref"] == ""
    assert "nothing was sent" in example["readiness_readback"]["operator_message"].lower()


def test_generic_send_it_blocked_exact_approval_required():
    example = _payload()["examples"]["generic_send_it_blocked"]

    assert example["readiness_readback"]["status"] == "SEND_BLOCKED_MISSING_GATES"
    assert "exact approval phrase ref" in example["gate_check"]["missing_gates"]
    assert example["gate_check"]["exact_phrase_matched"] is False
    assert adapter.EXACT_APPROVAL_DISPLAY in example["readiness_readback"]["how_to_fix"]


def test_provider_missing_blocks():
    example = _payload()["examples"]["provider_missing"]

    assert example["send_request"]["provider_target"] == "GMAIL_SEND"
    assert example["provider_boundary"]["provider_available"] is False
    assert example["provider_boundary"]["live_send_allowed"] is False
    assert example["readiness_readback"]["status"] == "SEND_BLOCKED_MISSING_PROVIDER"
    assert "future gated provider adapter" in example["readiness_readback"]["how_to_fix"]


def test_raw_attachment_body_blocks():
    example = _payload()["examples"]["raw_attachment_body_blocked"]

    assert example["readiness_readback"]["status"] == "SEND_BLOCKED_PRIVACY_BOUNDARY"
    assert "raw attachment body" in example["readiness_readback"]["operator_message"].lower()
    assert "raw attachment body removed from request" in example["gate_check"]["missing_gates"]
    assert example["send_receipt"]["sent"] is False


def test_send_receipts_are_not_sent_and_external_false():
    for example in _payload()["examples"].values():
        receipt = example["send_receipt"]
        assert receipt["sent"] is False
        assert receipt["external_authority"] is False
        assert receipt["provider_message_id_ref"] == ""


def test_all_blockers_exist_and_fail_closed():
    blockers = {row["blocker_type"]: row for row in _payload()["email_send_adapter_blockers"]}

    for blocker_type in adapter.BLOCKER_TYPES:
        assert blocker_type in blockers
        assert blockers[blocker_type]["fail_closed"] is True
    assert blockers["GENERIC_APPROVAL_USED"]["severity"] == "critical"
    assert blockers["SEND_PROVIDER_CALLED_IN_TEST"]["severity"] == "critical"


def test_all_live_authority_false_and_no_provider_call():
    payload = _payload()

    assert payload["machine_proof"]["all_live_authority_false"] is True
    assert payload["machine_proof"]["provider_send_call_performed"] is False
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    for key in [
        "email_send_performed",
        "gmail_send_performed",
        "mail_send_performed",
        "smtp_send_performed",
        "attachment_send_performed",
        "external_action_performed",
        "workflow_run_performed",
        "agent_dispatch_performed",
        "credential_handling_performed",
        "raw_attachment_body_included",
        "raw_body_ingestion_performed",
        "mac_sync_import_performed",
        "swift_change_performed",
        "git_push_performed",
    ]:
        assert payload["machine_proof"][key] is False


def test_repo_b_send_method_is_static_reference_only():
    audit = _payload()["repo_b_provider_static_audit"]

    assert audit["identified_send_method_ref"] == "google_access_broker._exec_gmail_send/google.gmail.send"
    assert audit["policy_class"] == "CLASS_C"
    assert audit["called"] is False


def test_export_and_run_scripts_write_outputs(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / adapter.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / adapter.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == adapter.READ_MODEL_ID
    assert summary["dry_run_status"] == "SEND_DRY_RUN_READY"
    assert summary["all_live_authority_false"] is True
    assert payload["schema_version"] == adapter.SCHEMA_VERSION
    assert "Gated Email Send Adapter" in operator
    assert "No email send" in operator

    assert run_main(["--fixture", "capital_hilton_dry_run", "--export-root", str(tmp_path), "--format", "json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["examples"]["capital_hilton_dry_run_ready_not_executed"]["send_receipt"]["sent"] is False


def test_generated_outputs_have_no_raw_email_attachment_or_secrets(tmp_path):
    payload = _payload()
    adapter.write_exports(payload, tmp_path)
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())

    assert "actual secret value" not in text.lower()
    assert "raw private body value" not in text.lower()
    assert "credential value" not in text.lower()
    assert "token value" not in text.lower()
    assert "raw attachment body value" not in text.lower()
    assert "attachment bytes" not in text.lower()
    assert "AKIA" not in text
    assert not re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)
