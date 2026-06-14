import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "generated/read_models/helm_composer_contract.json"
BRIDGE_PATH = Path("/mnt/e/openclaw/generated/read_models/helm_composer_contract.json")


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def test_contract_json_parses_and_has_required_identity():
    payload = _contract()

    assert payload["schema_version"] == "helm_composer_contract_v0"
    assert payload["surface_ref"] == "helm_composer"
    assert payload["input_placeholder"] == "Ask OpenClaw what is next..."
    assert payload["default_mode"] == "operator_calm"
    assert payload["status"] == "HELM_COMPOSER_CONTRACT_READY"


def test_supported_request_types_include_system_question_answer():
    payload = _contract()

    assert "system_question_answer" in payload["supported_request_types"]
    assert "workflow_package_request" in payload["supported_request_types"]
    assert "capital_hilton_invoice_operator_assist" in payload["supported_request_types"]


def test_history_policy_hides_full_history_by_default():
    policy = _contract()["history_policy"]

    assert policy["show_full_history_by_default"] is False
    assert policy["show_recent_context_count"] == 3
    assert policy["proof_collapsed_by_default"] is True
    assert policy["raw_request_bodies_visible_by_default"] is False


def test_authority_flags_are_false():
    boundary = _contract()["authority_boundary"]

    assert boundary
    assert all(value is False for value in boundary.values())


def test_suggested_prompts_include_safe_questions_and_st_annes_work_log_intake():
    prompts = _contract()["suggested_quick_prompts"]

    assert "What is safe next?" in prompts
    assert "What is the difference between Chief and a spawned worker?" in prompts
    assert "Mark that I'm at church running sound." in prompts


def test_bridge_contract_matches_local_contract():
    local = _contract()
    bridge = json.loads(BRIDGE_PATH.read_text(encoding="utf-8"))

    assert bridge == local


def test_unsafe_true_grant_scan_is_clean():
    payload = _contract()
    unsafe_keys = {
        "email_send_allowed",
        "ledger_posting_allowed",
        "browser_access_allowed",
        "gmail_allowed",
        "coupa_allowed",
        "portal_submit_allowed",
        "sent",
        "paid",
        "business_action_performed",
    }

    assert not [
        (key, value)
        for key, value in _walk_values(payload)
        if key in unsafe_keys and value is True
    ]
    assert payload["machine_proof"]["unsafe_true_grants_absent"] is True
