import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "generated/read_models/openclaw_readiness_status_alias_registry.json"


def _load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _resolve_status(status: str, registry: dict) -> str | None:
    for entry in registry["canonical_statuses"]:
        if status == entry["canonical"] or status in entry.get("aliases", []):
            return entry["canonical"]
    return None


def test_workflow_package_rail_status_resolves_to_request_consumer_ready():
    registry = _load_registry()

    assert (
        _resolve_status("WORKFLOW_PACKAGE_RAIL_STATUS_READY", registry)
        == "WORKFLOW_PACKAGE_REQUEST_CONSUMER_READY"
    )


def test_pc_workflow_package_consumer_status_resolves_to_request_consumer_ready():
    registry = _load_registry()

    assert (
        _resolve_status("PC_WORKFLOW_PACKAGE_REQUEST_CONSUMER_READY", registry)
        == "WORKFLOW_PACKAGE_REQUEST_CONSUMER_READY"
    )


def test_pc_operator_copy_layer_resolves_to_display_copy_ready():
    registry = _load_registry()

    assert _resolve_status("PC_OPERATOR_COPY_LAYER_READY", registry) == "PC_OPERATOR_DISPLAY_COPY_READY"


def test_mac_helm_composer_ready_resolves_to_itself():
    registry = _load_registry()

    assert _resolve_status("MAC_HELM_COMPOSER_READY", registry) == "MAC_HELM_COMPOSER_READY"
    assert _resolve_status("HELM_COMPOSER_UI_READY", registry) == "MAC_HELM_COMPOSER_READY"


def test_system_question_e2e_alias_resolves_to_route_ready():
    registry = _load_registry()

    assert _resolve_status("SYSTEM_QUESTION_E2E_READY", registry) == "SYSTEM_QUESTION_ROUTE_READY"


def test_system_question_route_ready_resolves_to_itself():
    registry = _load_registry()

    assert _resolve_status("SYSTEM_QUESTION_ROUTE_READY", registry) == "SYSTEM_QUESTION_ROUTE_READY"


def test_package_event_index_ready_resolves_to_itself():
    registry = _load_registry()

    assert _resolve_status("PACKAGE_EVENT_INDEX_READY", registry) == "PACKAGE_EVENT_INDEX_READY"


def test_unknown_status_does_not_resolve():
    registry = _load_registry()

    assert _resolve_status("MADE_UP_STATUS_READY", registry) is None


def test_registry_is_guidance_only_and_has_clean_authority_flags():
    registry = _load_registry()
    rendered = json.dumps(registry, sort_keys=True)
    unsafe_true_fragments = [
        '"email_send_allowed": true',
        '"gmail_allowed": true',
        '"coupa_allowed": true',
        '"ledger_posting_allowed": true',
        '"paid": true',
        '"sent": true',
        '"portal_submit_allowed": true',
        '"business_action_performed": true',
    ]

    assert registry["schema_version"] == "openclaw_readiness_status_alias_registry_v0"
    assert registry["registry_mode"] == "read_only_guidance"
    assert registry["does_not_grant_business_authority"] is True
    assert not any(fragment in rendered for fragment in unsafe_true_fragments)
