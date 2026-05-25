import json
import re
from pathlib import Path

import openclaw_chat_responder_router as responder
from scripts.export_openclaw_chat_responder_readback import main as export_main


FIXED_NOW = "2026-05-25T03:00:00+00:00"


def _build(root: Path = Path(".")) -> dict:
    return responder.build_openclaw_chat_responder_payload(
        fixture="capital_hilton",
        root=root,
        generated_at=FIXED_NOW,
    )


def test_models_exist_and_payload_is_deterministic():
    first = _build()
    second = _build()

    assert responder.stable_json(first) == responder.stable_json(second)
    assert first["schema_version"] == responder.SCHEMA_VERSION
    assert first["read_model_id"] == responder.READ_MODEL_ID
    assert first["machine_proof"]["openclaw_chat_responder_request_model_present"] is True
    assert first["machine_proof"]["chat_responder_context_package_model_present"] is True
    assert first["machine_proof"]["responder_selection_model_present"] is True
    assert first["machine_proof"]["openclaw_chat_responder_policy_model_present"] is True
    assert first["machine_proof"]["openclaw_chat_responder_output_model_present"] is True
    assert first["machine_proof"]["openclaw_chat_responder_readback_model_present"] is True
    assert first["machine_proof"]["openclaw_chat_responder_blocker_model_present"] is True


def test_required_model_fields_exist():
    payload = _build()
    schemas = payload["model_schemas"]

    assert schemas["openclaw_chat_responder_request"]["required_fields"] == list(responder.REQUIRED_REQUEST_FIELDS)
    assert schemas["chat_responder_context_package"]["required_fields"] == list(responder.REQUIRED_CONTEXT_FIELDS)
    assert schemas["responder_selection"]["required_fields"] == list(responder.REQUIRED_SELECTION_FIELDS)
    assert schemas["openclaw_chat_responder_policy"]["required_fields"] == list(responder.REQUIRED_POLICY_FIELDS)
    assert schemas["openclaw_chat_responder_output"]["required_fields"] == list(responder.REQUIRED_OUTPUT_FIELDS)
    assert schemas["openclaw_chat_responder_readback"]["required_fields"] == list(responder.REQUIRED_READBACK_FIELDS)


def test_capital_hilton_route_and_context_package_are_built():
    payload = _build()
    request = payload["openclaw_chat_responder_request"]
    context = payload["chat_responder_context_package"]

    assert payload["machine_proof"]["route_context_package_built"] is True
    assert payload["machine_proof"]["capital_hilton_route_correct"] is True
    assert request["workflow_type"] == "invoice_delivery_workflow"
    assert request["world_ref"] == "finance"
    assert request["client_ref"] == "capital_hilton"
    assert context["package_type"] == "CHAT_RESPONSE_CONTEXT_PACKAGE"
    assert "4 dates at $400 each working basis" in context["known_facts"]
    assert "exact Coupa PO/reference or a decision to keep discovery open" in context["missing_items"]
    assert "email send" in context["locked_actions"]
    assert "Coupa access" in context["locked_actions"]


def test_context_package_excludes_private_bodies_and_credentials():
    payload = _build()
    context = payload["chat_responder_context_package"]

    assert payload["machine_proof"]["context_excludes_private_bodies"] is True
    assert "credentials and tokens" in context["excluded_context_summary"]
    assert "raw email bodies" in context["excluded_context_summary"]
    assert "raw PDFs or Excel bodies" in context["excluded_context_summary"]
    assert "protected evidence bodies" in context["excluded_context_summary"]
    assert "receipts/readbacks remain truth" in context["truth_boundary"]


def test_responder_selection_detects_missing_approved_local_model_rail():
    payload = _build()
    selection = payload["responder_selection"]

    assert payload["machine_proof"]["local_model_availability_detected"] is True
    assert selection["responder_role"] == "finance_workflow_responder"
    assert selection["local_only"] is True
    assert selection["model_available"] is False
    assert selection["selected"] is False
    assert selection["blocked_reason"] == "No approved local chat responder adapter is connected."


def test_unavailable_path_is_not_fake_success():
    payload = _build()
    output = payload["openclaw_chat_responder_output"]
    readback = payload["openclaw_chat_responder_readback"]

    assert payload["machine_proof"]["model_unavailable_status_not_fake_success"] is True
    assert output["response_status"] == "LOCAL_MODEL_UNAVAILABLE"
    assert output["model_used"] is None
    assert "No approved local responder model is available yet." in output["assistant_message"]
    assert readback["readback_status"] == "LOCAL_MODEL_UNAVAILABLE"
    assert "approved local-only chat responder adapter" in readback["missing_backend_rails"]


def test_follow_up_questions_and_locked_actions_are_present():
    payload = _build()
    output = payload["openclaw_chat_responder_output"]
    readback = payload["openclaw_chat_responder_readback"]

    assert any("Coupa PO" in question for question in output["follow_up_questions"])
    assert any("Annette" in question for question in output["follow_up_questions"])
    assert any("Guardian approval" in question for question in output["follow_up_questions"])
    assert payload["machine_proof"]["external_actions_locked"] is True
    for expected in ["email send", "Coupa access", "Coupa submit", "browser automation", "invoice generation"]:
        assert expected in readback["locked_actions"]


def test_policy_blocks_cloud_network_tools_agents_workflow_and_external_action():
    payload = _build()
    policy = payload["openclaw_chat_responder_policy"]

    assert policy["local_model_allowed"] is True
    assert policy["cloud_model_allowed"] is False
    assert policy["network_allowed"] is False
    assert policy["tool_execution_allowed"] is False
    assert policy["agent_dispatch_allowed"] is False
    assert policy["workflow_run_allowed"] is False
    assert policy["state_write_allowed"] is False
    assert policy["external_action_allowed"] is False
    assert payload["machine_proof"]["cloud_model_allowed_false"] is True
    assert payload["machine_proof"]["network_allowed_false"] is True
    assert payload["machine_proof"]["tool_execution_allowed_false"] is True


def test_authority_boundary_all_live_flags_false():
    payload = _build()

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    assert payload["machine_proof"]["no_cloud_model_api_used"] is True
    assert payload["machine_proof"]["no_network_used"] is True
    assert payload["machine_proof"]["no_tool_execution_used"] is True
    assert payload["machine_proof"]["no_agent_dispatch_used"] is True
    assert payload["machine_proof"]["no_workflow_run_used"] is True


def test_blockers_exist_and_fail_closed():
    payload = _build()
    blockers = payload["openclaw_chat_responder_blockers_by_id"]
    blocker_types = {blocker["blocker_type"] for blocker in blockers.values()}

    for expected in responder.BLOCKER_TYPES:
        assert expected in blocker_types
    assert blockers["openclaw_chat_responder_blocker_unknown_fail_closed"]["fail_closed"] is True
    assert "NO_APPROVED_LOCAL_MODEL" in blocker_types
    assert "CLOUD_MODEL_ATTEMPTED" in blocker_types
    assert "NETWORK_ATTEMPTED" in blocker_types
    assert "FAKE_TRUTH_CLAIM" in blocker_types


def test_no_fake_truth_claims_in_unavailable_visible_text():
    payload = _build()

    assert payload["machine_proof"]["no_fake_truth_claims"] is True
    visible = responder._visible_text(payload).lower()
    for forbidden in [
        "invoice generated",
        "email sent",
        "coupa accessed",
        "coupa submitted",
        "approval requested",
        "procedure stored",
        "invoice sent",
    ]:
        assert forbidden not in visible


def test_export_scripts_write_parseable_readback(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--fixture", "capital_hilton", "--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])
    data = json.loads(json_path.read_text(encoding="utf-8"))

    assert summary["response_status"] == "LOCAL_MODEL_UNAVAILABLE"
    assert data["openclaw_chat_responder_readback"]["readback_status"] == "LOCAL_MODEL_UNAVAILABLE"
    assert "ELIOPERATOR" in operator_path.read_text(encoding="utf-8")


def test_no_raw_pii_or_private_bodies_in_generated_outputs(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--fixture", "capital_hilton", "--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])
    data = json.loads(json_path.read_text(encoding="utf-8"))
    combined = json_path.read_text(encoding="utf-8") + "\n" + operator_path.read_text(encoding="utf-8")

    assert data["machine_proof"]["credentials_or_secrets_included"] is False
    assert data["machine_proof"]["raw_private_bodies_included"] is False
    assert data["machine_proof"]["raw_pii_included"] is False
    assert "@" not in combined
    assert not re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", combined)
    assert "raw_email_body" not in combined
    assert "raw_pdf_body" not in combined
    assert "raw private body:" not in combined.lower()
    assert "access_token" not in combined.lower()


def test_source_does_not_import_network_or_cloud_model_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "openclaw_chat_responder_router.py",
            "scripts/run_openclaw_chat_responder_router.py",
            "scripts/export_openclaw_chat_responder_readback.py",
        ]
    )
    forbidden = [
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "ollama_call(",
        "nemotron_call(",
        "openrouter_call(",
        "subprocess.",
        "os.system",
        "smtplib",
        "selenium",
        "playwright",
        "api/generate",
        "integrate.api",
        "openrouter.ai",
    ]
    for token in forbidden:
        assert token not in source
