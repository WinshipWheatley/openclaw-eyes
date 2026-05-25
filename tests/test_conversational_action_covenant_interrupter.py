import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import conversational_action_covenant_interrupter as interrupter
from scripts.export_conversational_action_covenant_interrupter import main as export_main


FIXED_NOW = "2026-05-25T23:55:00+00:00"


def _payload() -> dict:
    return interrupter.build_payload(generated_at=FIXED_NOW)


def test_required_models_exist():
    for name in [
        "ConversationalActionCovenantInterrupter",
        "ChatActionIntent",
        "ActionCovenantRequest",
        "ActionCovenantDecision",
        "ActionCovenantReceipt",
        "ActionCovenantBlocker",
        "ConversationalActionCovenantElioperatorReport",
    ]:
        assert hasattr(interrupter, name)


def test_low_risk_confirmation_example_exists():
    example = _payload()["examples"]["looks_right"]

    assert example["intent"]["operator_phrase"] == "looks right"
    assert example["intent"]["normalized_intent"] == "CONFIRM_DRAFT_UNDERSTANDING"
    assert example["intent"]["risk_level"] == "LOW"
    assert example["decision"]["decision_status"] == "ALLOWED_LOW_RISK_CONTINUE"
    assert example["receipt"]["action_executed"] is False
    assert example["receipt"]["external_authority"] is False


def test_ambiguous_go_ahead_blocked():
    example = _payload()["examples"]["go_ahead"]

    assert example["intent"]["operator_phrase"] == "go ahead"
    assert example["intent"]["normalized_intent"] == "APPROVE_GATED_ACTION"
    assert example["decision"]["decision_status"] == "BLOCKED_AMBIGUOUS_INTENT"
    assert example["decision"]["operator_message"] == "What should I go ahead with?"
    assert "specific action" in example["decision"]["how_to_fix"]


def test_send_it_blocked_without_covenant():
    example = _payload()["examples"]["send_it"]

    assert example["intent"]["candidate_action_type"] == "SEND_EMAIL"
    assert example["intent"]["risk_level"] == "HIGH"
    assert example["decision"]["decision_status"] == "NEEDS_COVENANT"
    assert "No pending covenant" in example["decision"]["why_blocked"]
    assert example["receipt"]["action_executed"] is False


def test_capital_hilton_send_covenant_example_exists():
    example = _payload()["examples"]["capital_hilton_send"]
    covenant = example["covenant_request"]

    assert covenant["source_workflow_ref"] == "capital_hilton_invoice_workflow"
    assert covenant["requested_action"] == "SEND_EMAIL"
    assert covenant["exact_approval_phrase"] == "APPROVE SEND_EMAIL capital_hilton_invoice_covenant_v0"
    assert "Guardian review if configured for external send" in covenant["required_approvals"]
    assert example["decision"]["decision_status"] == "NEEDS_GUARDIAN_REVIEW"
    assert example["receipt"]["action_authorized"] is False
    assert example["receipt"]["action_executed"] is False


def test_reveal_secret_gate_exists():
    example = _payload()["examples"]["reveal_secret"]

    assert example["intent"]["normalized_intent"] == "REVEAL_SECRET_REQUEST"
    assert example["intent"]["candidate_action_type"] == "REVEAL_SECRET"
    assert example["covenant_request"]["requested_action"] == "REVEAL_SECRET"
    assert "protected secret token ref" in example["covenant_request"]["required_inputs"]
    assert example["decision"]["decision_status"] == "NEEDS_GUARDIAN_REVIEW"
    assert example["receipt"]["external_authority"] is False


def test_test_package_case_exists():
    example = _payload()["examples"]["test_package"]

    assert example["intent"]["normalized_intent"] == "TEST_PACKAGE"
    assert example["intent"]["candidate_action_type"] == "TEST_WORKFLOW_PACKAGE"
    assert example["covenant_request"]["requested_action"] == "TEST_WORKFLOW_PACKAGE"
    assert example["decision"]["decision_status"] == "BLOCKED_MISSING_PROOF"
    assert "package ref" in example["covenant_request"]["required_inputs"]


def test_unsupported_destructive_action_blocked():
    example = _payload()["examples"]["destructive_action"]

    assert example["intent"]["operator_phrase"] == "delete that whole client folder"
    assert example["intent"]["normalized_intent"] == "MUTATE_FILE_REQUEST"
    assert example["intent"]["risk_level"] == "CRITICAL"
    assert example["decision"]["decision_status"] == "BLOCKED_UNSUPPORTED_ACTION"
    assert "scoped non-destructive" in example["decision"]["how_to_fix"]


def test_exact_approval_phrase_policy_exists():
    payload = _payload()
    policy = payload["interrupter"]["exact_signature_policy"]

    assert any("APPROVE <REQUESTED_ACTION> <covenant_id>" in line for line in policy)
    assert any("exact match" in line for line in policy)
    assert payload["examples"]["capital_hilton_send"]["covenant_request"]["exact_approval_phrase"].startswith("APPROVE SEND_EMAIL ")


def test_all_blockers_exist_and_fail_closed():
    blockers = {row["blocker_type"]: row for row in _payload()["action_covenant_blockers"]}

    for blocker_type in interrupter.BLOCKER_TYPES:
        assert blocker_type in blockers
        assert blockers[blocker_type]["fail_closed"] is True
    assert blockers["CASUAL_PHRASE_USED_FOR_EXTERNAL_ACTION"]["severity"] == "critical"
    assert blockers["SECRET_REVEAL_ATTEMPTED_WITHOUT_GATE"]["severity"] == "critical"


def test_all_live_authority_false():
    payload = _payload()

    assert payload["machine_proof"]["all_live_authority_false"] is True
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    for key in [
        "live_action_authorization_performed",
        "action_execution_performed",
        "email_send_performed",
        "coupa_submit_performed",
        "browser_access_performed",
        "file_mutation_performed",
        "secret_reveal_performed",
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
    payload = json.loads((tmp_path / interrupter.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / interrupter.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == interrupter.READ_MODEL_ID
    assert summary["all_live_authority_false"] is True
    assert "capital_hilton_send" in summary["examples"]
    assert payload["schema_version"] == interrupter.SCHEMA_VERSION
    assert "Conversational Action Covenant Interrupter" in operator
    assert "No live action authorization" in operator


def test_generated_outputs_have_no_credentials_or_private_bodies(tmp_path):
    payload = _payload()
    interrupter.write_exports(payload, tmp_path)
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())

    assert "actual secret value" not in text.lower()
    assert "raw private body value" not in text.lower()
    assert "credential value" not in text.lower()
    assert "token value" not in text.lower()
    assert "AKIA" not in text
    assert not re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)
