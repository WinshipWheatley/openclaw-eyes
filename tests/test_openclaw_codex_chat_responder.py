import json
import re
from pathlib import Path

import openclaw_codex_chat_responder as codex_responder
from scripts.export_openclaw_codex_chat_response_readback import main as export_main


FIXED_NOW = "2026-05-25T04:00:00+00:00"


def _build() -> dict:
    return codex_responder.build_openclaw_codex_chat_response_readback(
        fixture="capital_hilton",
        generated_at=FIXED_NOW,
    )


def test_models_exist_and_payload_is_deterministic():
    first = _build()
    second = _build()

    assert codex_responder.stable_json(first) == codex_responder.stable_json(second)
    assert first["schema_version"] == codex_responder.SCHEMA_VERSION
    assert first["read_model_id"] == codex_responder.READ_MODEL_ID
    assert first["machine_proof"]["request_model_present"] is True
    assert first["machine_proof"]["context_package_model_present"] is True
    assert first["machine_proof"]["codex_target_model_present"] is True
    assert first["machine_proof"]["codex_handoff_packet_model_present"] is True
    assert first["machine_proof"]["codex_readback_model_present"] is True
    assert first["machine_proof"]["codex_blocker_model_present"] is True


def test_required_fields_exist():
    payload = _build()
    schemas = payload["model_schemas"]

    assert schemas["openclaw_codex_chat_responder_request"]["required_fields"] == list(
        codex_responder.REQUIRED_REQUEST_FIELDS
    )
    assert schemas["codex_chat_context_package"]["required_fields"] == list(codex_responder.REQUIRED_CONTEXT_FIELDS)
    assert schemas["codex_responder_target"]["required_fields"] == list(codex_responder.REQUIRED_TARGET_FIELDS)
    assert schemas["codex_handoff_packet"]["required_fields"] == list(codex_responder.REQUIRED_HANDOFF_FIELDS)
    assert schemas["openclaw_codex_chat_response_readback"]["required_fields"] == list(
        codex_responder.REQUIRED_READBACK_FIELDS
    )


def test_codex_target_and_handoff_are_ready():
    payload = _build()
    target = payload["codex_responder_target"]
    handoff = payload["codex_handoff_packet"]

    assert payload["machine_proof"]["codex_path_present"] is True
    assert payload["machine_proof"]["selected_target_is_codex"] is True
    assert target["preferred_target"] == "codex_5_5"
    assert target["selected_target"] == "pc_codex_current_worker"
    assert target["model_target_label"] == "codex_current_session"
    assert target["selected"] is True
    assert handoff["handoff_status"] == "CODEX_HANDOFF_READY"
    assert handoff["cli_execution_required_now"] is False
    assert handoff["tool_execution_allowed"] is False


def test_context_package_is_safe_and_complete():
    payload = _build()
    context = payload["codex_chat_context_package"]

    assert payload["machine_proof"]["context_package_built"] is True
    assert context["package_type"] == "CODEX_CHAT_RESPONSE_CONTEXT_PACKAGE"
    assert "4 dates at $400 each working basis" in context["known_facts"]
    assert "exact Coupa PO/reference or a decision to keep discovery open" in context["missing_items"]
    assert "email send" in context["locked_actions"]
    assert payload["machine_proof"]["private_context_excluded"] is True
    for excluded in codex_responder.EXCLUDED_CONTEXT:
        assert excluded in context["excluded_context_summary"]


def test_codex_response_ready_with_capital_hilton_reply():
    payload = _build()
    readback = payload["openclaw_codex_chat_response_readback"]

    assert payload["machine_proof"]["response_status_ready"] is True
    assert readback["response_status"] == "CODEX_RESPONSE_READY"
    assert readback["selected_responder"] == "Codex"
    assert payload["machine_proof"]["capital_hilton_reply_present"] is True
    assert "I understand the workflow" in readback["assistant_message"]
    assert "Nothing has been sent or submitted." in readback["assistant_message"]
    assert payload["machine_proof"]["follow_up_present"] is True
    assert "Coupa PO/reference" in readback["suggested_next_question"]


def test_locked_actions_and_truth_boundary_are_preserved():
    payload = _build()
    readback = payload["openclaw_codex_chat_response_readback"]

    assert payload["machine_proof"]["external_actions_locked"] is True
    assert payload["machine_proof"]["truth_boundary_present"] is True
    for expected in [
        "email draft",
        "email send",
        "Coupa access",
        "Coupa submit",
        "browser automation",
        "approval request",
        "invoice generation",
        "attachment",
        "payment state update",
    ]:
        assert expected in readback["locked_actions"]
    assert "receipts/readbacks remain truth" in readback["truth_boundary"]


def test_no_false_execution_claims():
    payload = _build()
    visible = codex_responder._visible_text(payload).lower()

    assert payload["machine_proof"]["no_false_execution_claims"] is True
    for forbidden in [
        "email sent",
        "coupa submitted",
        "coupa accessed",
        "approval granted",
        "workflow executed",
        "procedure stored",
    ]:
        assert forbidden not in visible


def test_blockers_exist_and_fail_closed():
    payload = _build()
    blockers = payload["openclaw_codex_chat_responder_blockers_by_id"]
    blocker_types = {blocker["blocker_type"] for blocker in blockers.values()}

    for expected in codex_responder.BLOCKER_TYPES:
        assert expected in blocker_types
    assert blockers["openclaw_codex_chat_responder_blocker_unknown_fail_closed"]["fail_closed"] is True
    assert "CREDENTIAL_INCLUDED" in blocker_types
    assert "RAW_PRIVATE_BODY_INCLUDED" in blocker_types
    assert "FAKE_TRUTH_CLAIM" in blocker_types


def test_authority_boundary_all_false():
    payload = _build()

    assert payload["machine_proof"]["all_authority_flags_false"] is True
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    assert payload["machine_proof"]["codex_cli_not_executed"] is True
    assert payload["machine_proof"]["tool_execution_not_allowed"] is True
    assert payload["machine_proof"]["cloud_model_api_used"] is False
    assert payload["machine_proof"]["network_used"] is False
    assert payload["machine_proof"]["workflow_executed"] is False


def test_export_scripts_write_parseable_readback(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--fixture", "capital_hilton", "--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])
    data = json.loads(json_path.read_text(encoding="utf-8"))

    assert summary["response_status"] == "CODEX_RESPONSE_READY"
    assert summary["selected_target"] == "pc_codex_current_worker"
    assert data["openclaw_codex_chat_response_readback"]["response_status"] == "CODEX_RESPONSE_READY"
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
    assert "raw email body:" not in combined.lower()
    assert "raw pdf body:" not in combined.lower()
    assert "access_token" not in combined.lower()


def test_source_does_not_call_cloud_api_network_or_codex_cli():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "openclaw_codex_chat_responder.py",
            "scripts/run_openclaw_codex_chat_responder.py",
            "scripts/export_openclaw_codex_chat_response_readback.py",
        ]
    )
    forbidden = [
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "subprocess.",
        "os.system",
        "ollama_call(",
        "nemotron_call(",
        "openrouter_call(",
        "codex exec",
        "api/generate",
        "integrate.api",
        "openrouter.ai",
        "https://",
    ]
    for token in forbidden:
        assert token not in source
