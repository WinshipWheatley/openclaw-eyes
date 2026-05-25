import json
import re
from pathlib import Path

import workflow_readback_concierge_contract as concierge
from scripts.export_workflow_readback_concierge_contract import main as export_main


FIXED_NOW = "2026-05-25T00:30:00+00:00"


def _build() -> dict:
    return concierge.build_workflow_readback_concierge_contract(generated_at=FIXED_NOW)


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert concierge.stable_json(first) == concierge.stable_json(second)
    assert first["schema_version"] == concierge.SCHEMA_VERSION
    assert first["read_model_id"] == concierge.READ_MODEL_ID
    assert first["contract_status"] == concierge.CONTRACT_STATUS
    assert first["machine_proof"]["all_live_authority_flags_false"] is True
    assert first["machine_proof"]["external_action_performed"] is False


def test_required_models_exist():
    payload = _build()
    proof = payload["machine_proof"]
    schemas = payload["model_schemas"]

    assert proof["workflow_readback_concierge_contract_model_present"] is True
    assert proof["readback_correlation_model_present"] is True
    assert proof["readback_freshness_check_model_present"] is True
    assert proof["agent_readback_responsibility_model_present"] is True
    assert proof["operator_readback_card_model_present"] is True
    assert proof["readback_navigator_blocker_model_present"] is True
    assert proof["workflow_readback_concierge_elioperator_report_model_present"] is True
    assert schemas["workflow_readback_concierge_contract"]["required_fields"] == list(concierge.REQUIRED_CONTRACT_FIELDS)
    assert schemas["readback_correlation"]["required_fields"] == list(concierge.REQUIRED_CORRELATION_FIELDS)
    assert schemas["readback_freshness_check"]["required_fields"] == list(concierge.REQUIRED_FRESHNESS_FIELDS)


def test_correlation_and_freshness_statuses_exist():
    payload = _build()

    assert payload["machine_proof"]["correlation_statuses_present"] is True
    assert payload["machine_proof"]["freshness_statuses_present"] is True
    for expected in [
        "MATCHED_READY",
        "WAITING_FOR_BACKEND",
        "NO_REQUEST_FOUND",
        "NO_READBACK_FOUND",
        "STALE_READBACK",
        "HASH_OR_IDEMPOTENCY_MISMATCH",
        "MULTIPLE_CANDIDATES_NEED_REVIEW",
        "BLOCKED_UNSUPPORTED_TYPE",
        "UNKNOWN_FAIL_CLOSED",
    ]:
        assert expected in payload["correlation_statuses"]
    for expected in ["CURRENT", "STALE", "UNKNOWN_TIMESTAMP", "SOURCE_MISMATCH", "FUTURE_TIMESTAMP_INVALID"]:
        assert expected in payload["freshness_statuses"]


def test_agent_responsibility_and_operator_cards_exist():
    payload = _build()
    responsibility = payload["agent_readback_responsibility"]
    card = payload["operator_readback_card"]

    assert payload["machine_proof"]["agent_roles_present"] is True
    assert payload["machine_proof"]["operator_cards_present"] is True
    assert responsibility["active_agent_role"] == "chat_router_agent"
    assert "invent success without readback" in responsibility["what_agent_must_not_do"]
    assert card["card_type"] == "READY_FOR_REVIEW"
    assert card["truth_status"] == "READBACK_MATCHED_DRAFT_UNDERSTANDING"
    assert card["detail_disclosure_available"] is True


def test_capital_hilton_waiting_example_exists():
    payload = _build()
    waiting = payload["examples"]["capital_hilton_waiting"]

    assert payload["machine_proof"]["capital_hilton_waiting_example_present"] is True
    assert waiting["correlation"]["correlation_status"] == "WAITING_FOR_BACKEND"
    assert waiting["operator_card"]["card_type"] == "WAITING"
    assert "No understanding has returned yet." in waiting["operator_card"]["summary"]


def test_capital_hilton_ready_example_exists():
    payload = _build()
    ready = payload["examples"]["capital_hilton_ready"]

    assert payload["machine_proof"]["capital_hilton_ready_example_present"] is True
    assert ready["correlation"]["correlation_status"] == "MATCHED_READY"
    assert ready["freshness"]["freshness_status"] == "CURRENT"
    assert ready["operator_card"]["title"] == "OpenClaw understood"
    assert "This is ready for review, not execution." in ready["operator_card"]["bullets"]


def test_stale_readback_example_exists_and_is_not_current_truth():
    payload = _build()
    stale = payload["examples"]["stale_readback"]

    assert payload["machine_proof"]["stale_readback_example_present"] is True
    assert stale["correlation"]["correlation_status"] == "STALE_READBACK"
    assert stale["freshness"]["freshness_status"] == "STALE"
    assert stale["operator_card"]["truth_status"] == "STALE_NOT_CURRENT_TRUTH"
    assert "I will not use it as current." in stale["operator_card"]["summary"]


def test_duplicate_noop_and_blocked_external_examples_exist():
    payload = _build()
    duplicate = payload["examples"]["duplicate_noop"]
    blocked = payload["examples"]["blocked_external_action"]

    assert payload["machine_proof"]["duplicate_noop_example_present"] is True
    assert duplicate["operator_card"]["card_type"] == "DUPLICATE_NOOP"
    assert "no duplicate was written" in duplicate["operator_card"]["summary"]
    assert payload["machine_proof"]["external_action_blocked_example_present"] is True
    assert blocked["operator_card"]["card_type"] == "BLOCKED"
    assert "No email was sent." in blocked["operator_card"]["bullets"]
    assert "No Coupa or browser access occurred." in blocked["operator_card"]["bullets"]


def test_blockers_exist_and_fail_closed():
    payload = _build()
    blockers = payload["readback_navigator_blockers_by_id"]
    blocker_types = {blocker["blocker_type"] for blocker in blockers.values()}

    for expected in concierge.BLOCKER_TYPES:
        assert expected in blocker_types
    assert payload["machine_proof"]["agent_invented_truth_blocker_present"] is True
    assert "AGENT_INVENTED_TRUTH" in blocker_types
    for blocker in blockers.values():
        assert blocker["fail_closed"] is True
        assert "ELIOPERATOR" in blocker["elioperator_warning"]


def test_agent_invented_truth_example_fails_closed():
    payload = _build()
    invented = payload["examples"]["agent_invented_truth_blocker"]

    assert invented["blocker_ref"] == "readback_navigator_blocker_agent_invented_truth"
    assert invented["operator_card"]["card_type"] == "UNKNOWN_FAIL_CLOSED"
    assert invented["operator_card"]["truth_status"] == "FAIL_CLOSED_NO_READBACK_PROOF"
    assert "must not invent state" in " ".join(invented["operator_card"]["bullets"])


def test_authority_boundary_all_live_flags_false():
    payload = _build()

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    assert payload["machine_proof"]["no_live_polling"] is True
    assert payload["machine_proof"]["no_watcher"] is True
    assert payload["machine_proof"]["no_agent_dispatch"] is True
    assert payload["machine_proof"]["no_model_call"] is True
    assert payload["machine_proof"]["no_workflow_run"] is True
    assert payload["machine_proof"]["no_external_action"] is True
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
    assert "@" not in combined
    assert not re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", combined)
    assert "raw_email_body" not in combined
    assert "raw_screenshot_body" not in combined
    assert "ELIOPERATOR" in operator_path.read_text(encoding="utf-8")


def test_operator_markdown_is_plain_language():
    payload = _build()
    markdown = concierge.format_operator_markdown(payload)

    assert "ELIOPERATOR" in markdown
    assert "Waiting for PC backend" in markdown
    assert "OpenClaw understood" in markdown
    assert "No live polling" in markdown
    assert "schema_version" not in markdown
    assert "payload_hash" not in markdown
    assert "idempotency_key" not in markdown


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "workflow_readback_concierge_contract.py",
            "scripts/export_workflow_readback_concierge_contract.py",
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
