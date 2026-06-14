import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import repo_b_telegram_intake_bridge as bridge
from scripts.export_repo_b_telegram_intake_bridge import main as export_main


FIXED_NOW = "2026-05-25T23:59:00+00:00"


def _payload() -> dict:
    return bridge.build_payload(generated_at=FIXED_NOW)


def test_required_models_exist():
    for name in [
        "RepoBTelegramIntakeBridgeDecision",
        "TelegramIntakeCapability",
        "TelegramIntakeEnvelope",
        "TelegramToOpenClawRequestMapping",
        "TelegramIntakeReadback",
        "TelegramIntakeBlocker",
    ]:
        assert hasattr(bridge, name)


def test_telegram_components_are_classified():
    decisions = {row["source_module"]: row for row in _payload()["telegram_intake_bridge_decisions"]}

    assert decisions["chief_listener.py"]["recommended_posture"] == "REBUILD_SMALL_SUBSET_IN_REPO_A"
    assert "live Telegram listener startup" in decisions["chief_listener.py"]["blocked_items"]
    assert "outbound Telegram replies" in decisions["chief_listener.py"]["blocked_items"]
    assert decisions["cassandra_listener.py"]["recommended_posture"] == "REFERENCE_ONLY"
    assert "voice file download" in decisions["cassandra_listener.py"]["blocked_items"]
    assert decisions["chief_sender.py"]["recommended_posture"] == "UNSAFE_DO_NOT_CONNECT"
    assert decisions["chief_notify.py"]["recommended_posture"] == "UNSAFE_DO_NOT_CONNECT"
    assert decisions["chief_approval_bridge.py"]["recommended_posture"] == "REFERENCE_ONLY"


def test_capabilities_include_safe_intake_and_blocked_outbound_dispatch():
    capabilities = {row["capability_type"]: row for row in _payload()["telegram_intake_capabilities"]}

    for required in [
        "OPERATOR_MESSAGE_INTAKE",
        "COMMAND_NORMALIZATION",
        "SESSION_MAPPING",
        "FOLLOWUP_INTENT_PARSE",
        "REQUEST_ENVELOPE_CREATION",
        "INTAKE_DIRECTORY_WRITE",
        "OUTBOUND_REPLY",
        "PENDING_ACTION_DISPATCH",
    ]:
        assert required in capabilities

    assert capabilities["OPERATOR_MESSAGE_INTAKE"]["wrapper_allowed"] is True
    assert capabilities["REQUEST_ENVELOPE_CREATION"]["external_authority"] is False
    assert capabilities["OUTBOUND_REPLY"]["wrapper_allowed"] is False
    assert capabilities["OUTBOUND_REPLY"]["outbound_required"] is True
    assert capabilities["OUTBOUND_REPLY"]["credential_required"] is True
    assert capabilities["PENDING_ACTION_DISPATCH"]["wrapper_allowed"] is False


def test_fixture_operator_message_maps_to_chat_request_without_outbound():
    example = _payload()["examples"]["operator_message"]

    assert example["input"] == "Make the Capital Hilton invoice workflow happen."
    assert example["envelope"]["command_hint"] == "workflow_make_it_happen"
    assert example["mapping"]["target_request_type"] == "CHAT_REQUEST"
    assert example["mapping"]["target_request_shape"]["workflow_ref"] == "capital_hilton_invoice_workflow"
    assert example["readback"]["status"] == "FIXTURE_MAPPING_READY"
    assert "Telegram outbound reply" in example["readback"]["blocked_items"]
    assert "no workflow ran" in example["readback"]["operator_message"]


def test_fixture_followup_maps_without_executing():
    example = _payload()["examples"]["followup"]

    assert example["input"] == "looks right"
    assert example["envelope"]["command_hint"] == "followup_confirmation_candidate"
    assert example["mapping"]["target_request_type"] == "CHAT_REQUEST"
    assert example["mapping"]["target_request_shape"]["workflow_ref"] == "active_thread_context_future"
    assert "pending action dispatch" in example["readback"]["blocked_items"]
    assert "will not approve, send, dispatch" in example["readback"]["operator_message"]


def test_blocker_examples_exist():
    examples = _payload()["examples"]

    assert examples["outbound_blocker"]["readback"]["status"] == "BLOCKED_OUTBOUND_TELEGRAM"
    assert examples["listener_blocker"]["readback"]["status"] == "BLOCKED_LIVE_LISTENER"
    assert examples["token_blocker"]["readback"]["status"] == "BLOCKED_TOKEN_REQUIRED"
    assert "Use Protected Secret Intake" in examples["token_blocker"]["readback"]["how_to_fix"]


def test_required_blockers_exist_and_fail_closed():
    blockers = {row["blocker_type"]: row for row in _payload()["telegram_intake_blockers"]}

    for required in bridge.BLOCKER_TYPES:
        assert required in blockers
        assert blockers[required]["fail_closed"] is True
    assert blockers["TELEGRAM_OUTBOUND_ATTEMPTED"]["severity"] == "critical"
    assert blockers["LIVE_TELEGRAM_LISTENER_START_ATTEMPTED"]["severity"] == "critical"
    assert blockers["BOT_TOKEN_INCLUDED"]["severity"] == "critical"


def test_mapping_excludes_private_and_credential_fields():
    mapping = _payload()["examples"]["operator_message"]["mapping"]

    assert mapping["tokenization_required"] is True
    assert "bot token value" in mapping["excluded_fields"]
    assert "raw Telegram update object" in mapping["excluded_fields"]
    assert "raw private message body" in mapping["excluded_fields"]
    assert "outbound reply target" in mapping["excluded_fields"]


def test_authority_boundary_all_false():
    payload = _payload()

    assert payload["machine_proof"]["all_live_authority_false"] is True
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    for key in [
        "repo_b_code_imported",
        "repo_b_runtime_executed",
        "telegram_listener_started",
        "telegram_outbound_performed",
        "bot_token_access_performed",
        "pending_action_dispatch_performed",
        "queue_mutation_performed",
        "external_action_performed",
        "credential_handling_performed",
        "raw_private_message_exposure",
        "mac_sync_import_performed",
        "swift_change_performed",
        "git_push_performed",
    ]:
        assert payload["machine_proof"][key] is False


def test_export_writes_json_and_operator_markdown(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / bridge.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / bridge.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["posture"] == "INTAKE_ONLY_BRIDGE_WITH_REPO_A_REBUILT_REQUEST_ENVELOPE_ADAPTER"
    assert summary["operator_message_target"] == "CHAT_REQUEST"
    assert payload["schema_version"] == bridge.SCHEMA_VERSION
    assert "Repo B Telegram Intake Bridge" in operator
    assert "No live Telegram listener" in operator


def test_generated_outputs_have_no_credentials_or_private_bodies(tmp_path):
    payload = _payload()
    bridge.write_exports(payload, tmp_path)
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())

    assert "telegram bot token value" not in text.lower()
    assert "bot123:" not in text.lower()
    assert "xoxb-" not in text.lower()
    assert "openai_api_key" not in text.lower()
    assert "raw private telegram message body value" not in text.lower()
    assert not re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)


def test_source_does_not_run_telegram_or_repo_b_code():
    source = Path("repo_b_telegram_intake_bridge.py").read_text(encoding="utf-8").lower()
    forbidden = [
        "subprocess.run",
        "from chief_",
        "import chief_",
        "from cassandra_",
        "import cassandra_",
        "telegram.ext",
        "applicationbuilder",
        "run_polling",
        "requests.post",
        "urllib.request",
        "os.environ[",
    ]
    for item in forbidden:
        assert item not in source
