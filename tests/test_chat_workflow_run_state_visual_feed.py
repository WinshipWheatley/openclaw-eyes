import json
import re
from pathlib import Path

import chat_workflow_run_state_visual_feed as feed
from scripts.export_chat_workflow_run_state_visual_feed import main as export_main


FIXED_NOW = "2026-05-25T02:00:00+00:00"
SOURCE_MIRROR = Path("generated/read_models/chat_readback_card_mirror.json")


def _build(source: Path = SOURCE_MIRROR) -> dict:
    return feed.build_chat_workflow_run_state_visual_feed(source_mirror_path=source, generated_at=FIXED_NOW)


def _visible_text(payload: dict) -> str:
    chunks = []
    narration = payload["agent_progress_narration"]
    chunks.extend(
        [
            narration["operator_line"],
            narration["what_happened"],
            narration["what_is_needed_next"],
            narration["what_is_locked"],
            narration["what_agent_will_do_next"],
            narration["what_agent_cannot_do"],
        ]
    )
    for event in payload["chat_workflow_visual_events"]:
        chunks.extend([event["title"], event["agent_line"], event["visual_summary"], event["next_safe_move"]])
        chunks.extend(event["proof_bullets"])
        chunks.extend(event["missing_bullets"])
        chunks.extend(event["blocked_bullets"])
        for choice in event["operator_choices"]:
            chunks.append(choice["label"])
            chunks.append(choice.get("disabled_reason") or "")
    return "\n".join(chunks)


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert feed.stable_json(first) == feed.stable_json(second)
    assert first["schema_version"] == feed.SCHEMA_VERSION
    assert first["read_model_id"] == feed.READ_MODEL_ID
    assert first["contract_status"] == feed.CONTRACT_STATUS
    assert first["machine_proof"]["all_live_authority_flags_false"] is True
    assert first["machine_proof"]["external_action_performed"] is False


def test_required_models_exist():
    payload = _build()
    proof = payload["machine_proof"]
    schemas = payload["model_schemas"]

    assert proof["chat_workflow_run_state_model_present"] is True
    assert proof["chat_workflow_visual_event_model_present"] is True
    assert proof["agent_progress_narration_model_present"] is True
    assert proof["visual_completion_receipt_model_present"] is True
    assert proof["chat_workflow_run_blocker_model_present"] is True
    assert proof["chat_workflow_visual_feed_elioperator_report_model_present"] is True
    assert schemas["chat_workflow_run_state"]["required_fields"] == list(feed.REQUIRED_RUN_STATE_FIELDS)
    assert schemas["chat_workflow_visual_event"]["required_fields"] == list(feed.REQUIRED_VISUAL_EVENT_FIELDS)
    assert schemas["visual_completion_receipt"]["required_fields"] == list(feed.REQUIRED_COMPLETION_FIELDS)


def test_phases_and_visual_event_types_exist():
    payload = _build()

    assert payload["machine_proof"]["phases_present"] is True
    assert payload["machine_proof"]["visual_event_types_present"] is True
    for expected in [
        "UNDERSTANDING_CAPTURED",
        "MISSING_INFO_NEEDED",
        "WORKFLOW_CHAIN_DRAFTED",
        "PACKAGE_READY",
        "COMPLETION_CONFIRMED",
        "UNKNOWN_FAIL_CLOSED",
    ]:
        assert expected in payload["phases"]
    for expected in ["UNDERSTANDING", "NEEDS_INPUT", "EXECUTION_LOCKED", "COMPLETION", "FAIL_CLOSED"]:
        assert expected in payload["visual_event_types"]


def test_capital_hilton_run_state_example_exists_and_is_correct():
    payload = _build()
    state = payload["chat_workflow_run_state"]

    assert payload["machine_proof"]["capital_hilton_run_state_present"] is True
    assert state["workflow_type"] == "invoice_delivery_workflow"
    assert state["world_ref"] == "finance"
    assert state["client_ref"] == "capital_hilton"
    assert state["current_phase"] == "MISSING_INFO_NEEDED"
    assert state["external_actions_locked"] is True
    assert payload["machine_proof"]["capital_hilton_known_facts_correct"] is True
    assert "4 dates at $400 each working basis" in state["known_facts"]
    assert "Excel/PDF companion invoice desired" in state["known_facts"]
    assert "Annette contact candidate" in state["known_facts"]
    assert "Coupa/PO payment rail candidate" in state["known_facts"]
    assert "invoice should be saved for records" in state["known_facts"]


def test_missing_and_locked_items_are_correct():
    payload = _build()
    state = payload["chat_workflow_run_state"]

    assert payload["machine_proof"]["capital_hilton_missing_items_correct"] is True
    assert "exact Coupa PO/reference" in state["missing_items"]
    assert "confirmation Annette is correct contact" in state["missing_items"]
    assert "final invoice artifact/hash" in state["missing_items"]
    assert "Guardian approval" in state["missing_items"]
    assert "send/submit receipts" in state["missing_items"]
    assert payload["machine_proof"]["capital_hilton_locked_items_correct"] is True
    for expected in [
        "email send",
        "Coupa access/submit",
        "browser",
        "approval request",
        "invoice generation",
        "attachment",
        "payment state update",
    ]:
        assert expected in state["blocked_items"]


def test_visual_events_exist_and_have_source_refs():
    payload = _build()
    events = {event["event_type"]: event for event in payload["chat_workflow_visual_events"]}

    assert payload["machine_proof"]["visual_events_exist"] is True
    assert payload["machine_proof"]["all_events_have_source_refs"] is True
    assert events["UNDERSTANDING"]["agent_line"] == (
        "I got the readback. OpenClaw understands the Capital Hilton invoice workflow draft."
    )
    assert events["NEEDS_INPUT"]["agent_line"] == (
        "To make this runnable, I still need the Coupa PO/reference, Annette confirmation, final invoice artifact, and Guardian approval."
    )
    assert events["EXECUTION_LOCKED"]["agent_line"] == (
        "Nothing external can happen yet. No email, Coupa, browser, approval, or payment update is active."
    )
    assert events["COMPLETION"]["title"] == "INVOICE SENT"


def test_future_completion_is_blocked_without_proof():
    payload = _build()
    completion = payload["visual_completion_receipt"]
    event = {item["event_type"]: item for item in payload["chat_workflow_visual_events"]}["COMPLETION"]

    assert payload["machine_proof"]["future_completion_blocked_without_proof"] is True
    assert completion["headline"] == "INVOICE SENT"
    assert completion["completion_allowed"] is False
    assert completion["blocked_reason"] == "Proof receipts do not exist yet."
    assert event["proof_status"] == "PROOF_REQUIRED"
    assert "Proof receipts do not exist yet." in event["blocked_bullets"]


def test_agent_progress_narration_does_not_claim_execution():
    payload = _build()
    narration = payload["agent_progress_narration"]

    assert payload["machine_proof"]["agent_narration_no_execution_claim"] is True
    assert "ready for your review, not execution" in narration["operator_line"]
    assert "cannot run the workflow" in narration["what_agent_cannot_do"]
    text = "\n".join(
        str(narration[key])
        for key in [
            "operator_line",
            "what_happened",
            "what_is_needed_next",
            "what_is_locked",
            "what_agent_will_do_next",
            "what_agent_cannot_do",
            "next_safe_move",
        ]
    ).lower()
    for forbidden_claim in [
        "email sent",
        "coupa submitted",
        "invoice generated",
        "approval requested",
        "payment state changed",
    ]:
        assert forbidden_claim not in text


def test_operator_choices_are_safe_and_future_actions_disabled():
    payload = _build()
    actions = [
        choice
        for event in payload["chat_workflow_visual_events"]
        for choice in event["operator_choices"]
    ]
    by_label = {choice["label"]: choice for choice in actions}

    assert payload["machine_proof"]["all_operator_actions_external_false"] is True
    assert by_label["Looks right"]["enabled"] is True
    assert by_label["Change something"]["enabled"] is True
    assert by_label["Tell me what is missing"]["enabled"] is True
    assert by_label["Build package later"]["enabled"] is False
    assert by_label["Test later"]["enabled"] is False
    assert all(choice["external_action"] is False for choice in actions)


def test_blockers_exist_and_fail_closed():
    payload = _build()
    blockers = payload["chat_workflow_run_blockers_by_id"]
    blocker_types = {blocker["blocker_type"] for blocker in blockers.values()}

    for expected in feed.BLOCKER_TYPES:
        assert expected in blocker_types
    assert payload["machine_proof"]["completion_without_proof_blocker_exists"] is True
    assert payload["machine_proof"]["agent_invented_progress_blocker_exists"] is True
    assert blockers["chat_workflow_run_blocker_unknown_fail_closed"]["fail_closed"] is True


def test_authority_boundary_all_live_flags_false():
    payload = _build()

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    assert payload["machine_proof"]["network_used"] is False
    assert payload["machine_proof"]["mac_sync_import_run"] is False
    assert payload["machine_proof"]["mission_control_swift_changed"] is False


def test_no_raw_pii_or_private_bodies_in_generated_outputs(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--source-mirror", str(SOURCE_MIRROR), "--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])
    data = json.loads(json_path.read_text(encoding="utf-8"))
    combined = json_path.read_text(encoding="utf-8") + "\n" + operator_path.read_text(encoding="utf-8")

    assert data["machine_proof"]["credentials_or_secrets_included"] is False
    assert data["machine_proof"]["raw_private_bodies_included"] is False
    assert data["machine_proof"]["raw_pii_in_visual_events"] is False
    assert "@" not in combined
    assert not re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", combined)
    assert "raw_email_body" not in combined
    assert "raw_pdf_body" not in combined
    assert "raw_screenshot_body" not in combined
    assert "ELIOPERATOR" in operator_path.read_text(encoding="utf-8")


def test_no_machine_language_in_visual_event_visible_content():
    payload = _build()
    visible = _visible_text(payload)

    assert payload["machine_proof"]["machine_language_terms_absent_from_visible_content"] is True
    for forbidden in feed.FORBIDDEN_VISIBLE_TERMS:
        assert forbidden.lower() not in visible.lower()


def test_operator_markdown_is_plain_and_boundary_focused():
    payload = _build()
    markdown = feed.format_operator_markdown(payload)

    assert "ELIOPERATOR" in markdown
    assert "Understanding captured" in markdown
    assert "Needs input" in markdown
    assert "Execution locked" in markdown
    assert "INVOICE SENT" in markdown
    assert "does not run a workflow" in markdown
    assert "payload_hash" not in markdown
    assert "idempotency" not in markdown.lower()
    assert "SQLite" not in markdown


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "chat_workflow_run_state_visual_feed.py",
            "scripts/export_chat_workflow_run_state_visual_feed.py",
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
