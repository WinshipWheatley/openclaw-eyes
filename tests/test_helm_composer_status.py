import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "generated/read_models/helm_composer_status.json"
BRIDGE_PATH = Path("/mnt/e/openclaw/generated/read_models/helm_composer_status.json")


def _status() -> dict:
    return json.loads(STATUS_PATH.read_text(encoding="utf-8"))


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def test_status_surface_records_required_readiness():
    payload = _status()

    assert payload["schema_version"] == "helm_composer_status_v0"
    assert payload["status"] == "HELM_COMPOSER_STATUS_READY"
    assert payload["composer_ready"] is True
    assert payload["contract_ready"] is True
    assert payload["mac_ui_ready"] is True
    assert payload["system_question_route_ready"] is True
    assert payload["package_event_index_ready"] is True
    assert payload["actionability_surface_ready"] is True


def test_required_capabilities_resolve_through_alias_registry():
    resolutions = _status()["readiness_resolution"]

    assert resolutions["MAC_HELM_COMPOSER_READY"]["canonical"] == "MAC_HELM_COMPOSER_READY"
    assert "HELM_COMPOSER_UI_READY" in resolutions["MAC_HELM_COMPOSER_READY"]["accepted_aliases"]
    assert resolutions["SYSTEM_QUESTION_ROUTE_READY"]["canonical"] == "SYSTEM_QUESTION_ROUTE_READY"
    assert "SYSTEM_QUESTION_E2E_READY" in resolutions["SYSTEM_QUESTION_ROUTE_READY"]["accepted_aliases"]


def test_supported_modes_and_latest_safe_smoke_are_recorded():
    payload = _status()
    prompts = [item["prompt"] for item in payload["latest_safe_smoke"]]

    assert payload["supported_modes"] == [
        "system_question_answer",
        "workflow_package_request",
        "St. Anne's work-log intake",
        "Capital Hilton proposal follow-up",
        "Capital Hilton invoice operator assist",
    ]
    assert prompts == [
        "What is safe next?",
        "Mark that I'm at church running sound.",
        "What is the difference between Chief and a spawned worker?",
        "Why did Submit Capital Hilton invoice block?",
        "Can this send email?",
    ]
    assert all(item["business_action_performed"] is False for item in payload["latest_safe_smoke"])


def test_history_proof_and_authority_boundaries_are_locked():
    payload = _status()

    assert payload["history_policy"]["show_full_history_by_default"] is False
    assert payload["history_policy"]["proof_collapsed_by_default"] is True
    assert payload["history_policy"]["raw_request_bodies_visible_by_default"] is False
    assert all(value is False for value in payload["authority_boundary"].values())
    assert payload["machine_proof"]["no_business_actions_performed"] is True


def test_bridge_status_matches_local_status():
    local = _status()
    bridge = json.loads(BRIDGE_PATH.read_text(encoding="utf-8"))

    assert bridge == local


def test_unsafe_true_grant_scan_is_clean():
    payload = _status()
    unsafe_keys = {
        "email_send_allowed",
        "ledger_posting_allowed",
        "browser_access_allowed",
        "gmail_allowed",
        "coupa_allowed",
        "portal_submit_allowed",
        "sent",
        "paid",
    }

    assert not [
        (key, value)
        for key, value in _walk_values(payload)
        if key in unsafe_keys and value is True
    ]
    assert payload["machine_proof"]["unsafe_true_grants_absent"] is True
