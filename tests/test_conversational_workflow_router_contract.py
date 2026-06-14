import json
import re
from pathlib import Path

import conversational_workflow_router_contract as router
from scripts.export_conversational_workflow_router_contract import main as export_main


FIXED_NOW = "2026-05-25T00:15:00+00:00"


def _build() -> dict:
    return router.build_conversational_workflow_router_contract(generated_at=FIXED_NOW)


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert router.stable_json(first) == router.stable_json(second)
    assert first["schema_version"] == router.SCHEMA_VERSION
    assert first["read_model_id"] == router.READ_MODEL_ID
    assert first["contract_status"] == router.CONTRACT_STATUS
    assert first["machine_proof"]["all_live_authority_flags_false"] is True
    assert first["machine_proof"]["external_action_performed"] is False


def test_required_models_exist():
    payload = _build()
    proof = payload["machine_proof"]
    schemas = payload["model_schemas"]

    assert proof["conversational_workflow_router_model_present"] is True
    assert proof["chat_workflow_message_model_present"] is True
    assert proof["routed_workflow_intent_model_present"] is True
    assert proof["model_or_role_package_target_model_present"] is True
    assert proof["human_card_readback_model_present"] is True
    assert proof["backend_package_request_model_present"] is True
    assert proof["router_blockers_model_present"] is True
    assert proof["router_elioperator_report_model_present"] is True
    assert schemas["conversational_workflow_router"]["required_fields"] == list(router.REQUIRED_ROUTER_FIELDS)
    assert schemas["chat_workflow_message"]["required_fields"] == list(router.REQUIRED_MESSAGE_FIELDS)
    assert schemas["routed_workflow_intent"]["required_fields"] == list(router.REQUIRED_INTENT_FIELDS)


def test_router_policy_blocks_live_parser_model_dispatch_and_external_actions():
    payload = _build()
    router_model = payload["conversational_workflow_router"]

    assert router_model["doctrine"]["chat_is_input_not_truth"] is True
    assert router_model["model_call_policy"]["live_model_call_allowed"] is False
    assert router_model["role_package_policy"]["live_agent_dispatch_allowed"] is False
    assert router_model["backend_package_policy"]["live_package_creation_allowed"] is False
    for value in router_model["current_live_authority"].values():
        assert value is False


def test_chat_message_is_sanitized_not_truth():
    payload = _build()
    message = payload["chat_workflow_message"]

    assert message["raw_message_allowed_in_normal_read_model"] is False
    assert "Capital Hilton invoice delivery" in message["sanitized_message_summary"]
    assert message["privacy_class"] == "sanitized_client_business_context"
    assert payload["machine_proof"]["message_is_not_treated_as_truth"] is True


def test_generic_examples_exist():
    payload = _build()
    examples = payload["generic_examples"]

    assert payload["machine_proof"]["generic_invoice_example_present"] is True
    assert payload["machine_proof"]["generic_debug_example_present"] is True
    assert payload["machine_proof"]["generic_creative_example_present"] is True
    assert payload["machine_proof"]["generic_unknown_example_present"] is True
    assert examples["generic_invoice_message"]["workflow_type"] == "invoice_delivery_workflow"
    assert examples["generic_system_debug_message"]["workflow_type"] == "system_debug_workflow"
    assert examples["generic_creative_release_message"]["workflow_type"] == "creative_release_workflow"
    assert examples["unknown_message"]["workflow_type"] == "unknown_needs_framing"


def test_capital_hilton_routes_to_expected_intent():
    payload = _build()
    intent = payload["capital_hilton_example"]["routed_intent"]

    assert intent["workflow_type"] == "invoice_delivery_workflow"
    assert intent["domain_ref"] == "finance"
    assert intent["client_ref"] == "Capital Hilton"
    assert intent["candidate_goal"] == "prepare/review invoice delivery workflow"
    assert intent["parser_mode"] == "deterministic_draft_router"
    assert intent["model_parser_available"] is False
    assert intent["operator_review_required"] is True
    assert payload["machine_proof"]["capital_hilton_routes_to_invoice_delivery"] is True


def test_capital_hilton_role_package_target_has_required_roles_and_external_locks():
    payload = _build()
    target = payload["capital_hilton_example"]["role_package_target"]

    for role in router.REQUIRED_ROLES:
        assert role in target["required_roles"]
    assert "Cassandra" in target["candidate_agents"]
    assert "Guardian" in target["candidate_agents"]
    assert target["can_dispatch_now"] is False
    assert "no live agent dispatch" in target["dispatch_block_reason"]
    assert payload["machine_proof"]["all_required_roles_present"] is True
    assert payload["machine_proof"]["backend_package_external_actions_locked"] is True


def test_capital_hilton_human_cards_contain_expected_plain_understanding():
    payload = _build()
    cards = payload["capital_hilton_example"]["human_card_readback"]
    understood = next(card for card in cards["cards"] if card["card_type"] == "OPENCLAW_UNDERSTOOD")
    proposed = next(card for card in cards["cards"] if card["card_type"] == "PROPOSED_WORKFLOW")
    blocked = next(card for card in cards["cards"] if card["card_type"] == "BLOCKED")

    assert cards["machine_contract_visible"] is False
    assert "Goal: prepare Capital Hilton invoice workflow." in understood["bullets"]
    assert "Destination/contact: Annette appears to be the payment follow-up contact candidate." in understood["bullets"]
    assert "Companion invoice: Excel-generated / Winship-branded PDF invoice." in understood["bullets"]
    assert "Official payment rail: Coupa supplier portal / PO." in understood["bullets"]
    assert "External actions: locked." in understood["bullets"]
    assert "Confirm PO/Coupa." in proposed["bullets"]
    assert "No email sent." in blocked["bullets"]
    assert "No Coupa access." in blocked["bullets"]
    assert payload["machine_proof"]["machine_contract_visible_false"] is True
    assert payload["machine_proof"]["machine_terms_absent_from_normal_cards"] is True


def test_backend_package_request_is_workflow_memory_proposal_and_not_created_now():
    payload = _build()
    package = payload["capital_hilton_example"]["backend_package_request"]

    assert package["package_type"] == "WORKFLOW_MEMORY_PROPOSAL"
    assert package["workflow_type"] == "invoice_delivery_workflow"
    assert "drafting_agent" in package["role_targets"]
    assert "finance_delivery_agent" in package["role_targets"]
    assert "protected_evidence_agent" in package["role_targets"]
    assert "approval_agent" in package["role_targets"]
    assert "artifact_generation_agent" in package["role_targets"]
    assert "post_office_handoff" in package["role_targets"]
    assert "final_readback_agent" in package["role_targets"]
    assert package["can_create_now"] is False
    assert "email draft/send" in package["blocked_actions"]
    assert "Coupa access/submit" in package["blocked_actions"]


def test_router_blockers_exist_and_fail_closed():
    payload = _build()
    blockers = payload["router_blockers_by_id"]
    blocker_types = {blocker["blocker_type"] for blocker in blockers.values()}

    for expected in router.BLOCKER_TYPES:
        assert expected in blocker_types
    for blocker in blockers.values():
        assert blocker["fail_closed"] is True
        assert "ELIOPERATOR" in blocker["elioperator_warning"]
    assert "MESSAGE_TREATED_AS_TRUTH" in blocker_types
    assert "MACHINE_CONTRACT_VISIBLE_TO_OPERATOR" in blocker_types


def test_authority_boundary_all_live_flags_false():
    payload = _build()

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    assert payload["machine_proof"]["no_live_model_call"] is True
    assert payload["machine_proof"]["no_live_agent_dispatch"] is True
    assert payload["machine_proof"]["no_live_workflow_run"] is True
    assert payload["machine_proof"]["no_live_external_action"] is True
    for key, value in payload["authority_boundary"].items():
        assert value is False, key


def test_generated_outputs_have_no_raw_pii_or_secret_like_values(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])

    data = json.loads(json_path.read_text(encoding="utf-8"))
    combined = json_path.read_text(encoding="utf-8") + "\n" + operator_path.read_text(encoding="utf-8")
    assert data["machine_proof"]["credentials_or_secrets_included"] is False
    assert data["machine_proof"]["raw_private_bodies_included"] is False
    assert data["machine_proof"]["raw_sensitive_fixture_values_included"] is False
    assert "@" not in combined
    assert not re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", combined)
    assert "PO-" not in combined
    assert "ELIOPERATOR" in operator_path.read_text(encoding="utf-8")


def test_operator_markdown_is_plain_and_has_no_machine_ui_terms():
    payload = _build()
    markdown = router.format_operator_markdown(payload)

    assert "ELIOPERATOR" in markdown
    assert "No email sent." in markdown
    assert "schema_version" not in markdown
    assert "handler" not in markdown.lower()
    assert "manifest" not in markdown.lower()


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "conversational_workflow_router_contract.py",
            "scripts/export_conversational_workflow_router_contract.py",
        ]
    )
    forbidden = [
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "subprocess.",
        "os.system",
        "smtplib",
        "selenium",
        "playwright",
        "coupa.login",
        "send_message",
        "shell=true",
        "eval(",
    ]
    for token in forbidden:
        assert token not in source
