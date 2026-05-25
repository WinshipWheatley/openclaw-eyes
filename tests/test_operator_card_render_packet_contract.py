import json
import re
from pathlib import Path

import operator_card_render_packet_contract as render
from scripts.export_operator_card_render_packet_contract import main as export_main


FIXED_NOW = "2026-05-25T01:25:00+00:00"
SOURCE_TRANSLATION = Path("generated/read_models/operator_card_translation_mirror.json")


def _build(source: Path = SOURCE_TRANSLATION) -> dict:
    return render.build_operator_card_render_packet_contract(source_translation_path=source, generated_at=FIXED_NOW)


def _visible_text(payload: dict) -> str:
    chunks = []
    for packet in payload["capital_hilton_examples"].values():
        visible = packet["visible_content"]
        semantic = packet["semantic_payload"]
        detail = packet["detail_content"]
        chunks.extend([visible["title"], visible["short_summary"], visible["primary_message"]])
        chunks.extend(visible["bullets"])
        chunks.extend(semantic["key_facts"])
        chunks.extend(semantic["missing_items"])
        chunks.extend(semantic["proof_bullets"])
        chunks.extend(semantic["blocked_items"])
        chunks.extend(detail["detail_bullets"])
        chunks.extend(detail["proof_bullets"])
        for action in packet["operator_actions"]:
            chunks.extend([action["label"], action.get("disabled_reason") or ""])
    return "\n".join(chunks)


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert render.stable_json(first) == render.stable_json(second)
    assert first["schema_version"] == render.SCHEMA_VERSION
    assert first["read_model_id"] == render.READ_MODEL_ID
    assert first["contract_status"] == render.CONTRACT_STATUS
    assert first["machine_proof"]["all_live_authority_flags_false"] is True
    assert first["machine_proof"]["external_action_performed"] is False


def test_required_models_exist():
    payload = _build()
    proof = payload["machine_proof"]
    schemas = payload["model_schemas"]

    assert proof["operator_card_render_packet_contract_model_present"] is True
    assert proof["operator_card_render_packet_model_present"] is True
    assert proof["semantic_card_payload_model_present"] is True
    assert proof["device_aware_card_spec_model_present"] is True
    assert proof["visual_style_directive_model_present"] is True
    assert proof["operator_action_render_spec_model_present"] is True
    assert proof["card_translation_and_filter_policy_model_present"] is True
    assert proof["render_packet_blocker_model_present"] is True
    assert proof["operator_card_render_packet_elioperator_report_model_present"] is True
    assert schemas["operator_card_render_packet_contract"]["required_fields"] == list(render.REQUIRED_CONTRACT_FIELDS)
    assert schemas["operator_card_render_packet"]["required_fields"] == list(render.REQUIRED_RENDER_PACKET_FIELDS)
    assert schemas["semantic_card_payload"]["required_fields"] == list(render.REQUIRED_SEMANTIC_FIELDS)


def test_card_types_and_truth_statuses_exist():
    payload = _build()

    assert payload["machine_proof"]["card_types_present"] is True
    assert payload["machine_proof"]["truth_statuses_present"] is True
    for expected in ["UNDERSTANDING", "PLAN", "MISSING_INFO", "BLOCKED", "COMPLETION", "WAITING", "ERROR_FAIL_CLOSED"]:
        assert expected in payload["card_types"]
    for expected in ["DRAFT_NOT_TRUTH", "BACKEND_READBACK_READY", "NEEDS_OPERATOR_REVIEW", "NEEDS_PROOF", "LOCKED_EXTERNAL_ACTION"]:
        assert expected in payload["truth_statuses"]


def test_device_style_action_and_filter_specs_exist():
    payload = _build()
    device = payload["device_aware_card_spec"]
    style = payload["visual_style_directive"]
    actions = payload["operator_action_render_specs"]
    policy = payload["card_translation_and_filter_policy"]

    assert payload["machine_proof"]["device_aware_spec_present"] is True
    assert device["target_surface"] == "mac_chat"
    assert device["preferred_layout"] == "compact_chat_card"
    assert device["max_visible_bullets"] == 5
    assert device["detail_disclosure_mode"] == "collapsed_by_default"
    assert payload["machine_proof"]["visual_style_directive_present"] is True
    assert style["tone"] == "calm"
    assert payload["machine_proof"]["action_render_spec_present"] is True
    assert all(action["external_action"] is False for action in actions)
    assert payload["machine_proof"]["filter_policy_present"] is True
    assert policy["fail_closed_on_machine_language"] is True


def test_blockers_exist_and_fail_closed():
    payload = _build()
    blockers = payload["render_packet_blockers_by_id"]
    blocker_types = {blocker["blocker_type"] for blocker in blockers.values()}

    assert payload["machine_proof"]["blockers_present"] is True
    for expected in render.BLOCKER_TYPES:
        assert expected in blocker_types
    assert "COMPLETION_WITHOUT_PROOF" in blocker_types
    assert "MACHINE_LANGUAGE_VISIBLE" in blocker_types
    assert "UNKNOWN_FAIL_CLOSED" in blocker_types
    assert blockers["render_packet_blocker_unknown_fail_closed"]["fail_closed"] is True


def test_capital_hilton_example_cards_exist():
    payload = _build()
    examples = payload["capital_hilton_examples"]

    assert payload["machine_proof"]["capital_hilton_understanding_present"] is True
    assert examples["understanding"]["visible_content"]["title"] == "What I understood"
    assert examples["understanding"]["card_type"] == "UNDERSTANDING"
    assert examples["understanding"]["truth_status"] == "DRAFT_NOT_TRUTH"
    assert "Capital Hilton invoice: 4 dates at $400 each" in examples["understanding"]["visible_content"]["short_summary"]
    assert payload["machine_proof"]["capital_hilton_plan_present"] is True
    assert examples["plan"]["visible_content"]["title"] == "The plan"
    assert payload["machine_proof"]["capital_hilton_still_needed_present"] is True
    assert examples["still_needed"]["visible_content"]["title"] == "Still needed"
    assert payload["machine_proof"]["capital_hilton_still_locked_present"] is True
    assert examples["still_locked"]["visible_content"]["title"] == "Still locked"


def test_completion_card_is_blocked_without_proof():
    payload = _build()
    completion = payload["capital_hilton_examples"]["completion_blocked"]

    assert payload["machine_proof"]["completion_card_blocked_without_proof"] is True
    assert completion["visible_content"]["title"] == "INVOICE SENT"
    assert completion["truth_status"] == "UNKNOWN_FAIL_CLOSED"
    assert completion["proof_status"] == "NEEDS_PROOF"
    assert "Completion is blocked." in completion["visible_content"]["bullets"]
    assert "Proof receipts are missing." in completion["visible_content"]["bullets"]


def test_waiting_card_is_not_success():
    payload = _build()
    waiting = payload["capital_hilton_examples"]["waiting"]

    assert payload["machine_proof"]["waiting_is_not_success"] is True
    assert waiting["visible_content"]["title"] == "Waiting on PC"
    assert waiting["card_type"] == "WAITING"
    assert waiting["style_directive"]["tone"] == "waiting"
    assert "Waiting is not success." in waiting["visible_content"]["primary_message"]


def test_visible_bullets_are_compact():
    payload = _build()

    assert payload["machine_proof"]["visible_bullets_compact"] is True
    for packet in payload["capital_hilton_examples"].values():
        assert len(packet["visible_content"]["bullets"]) <= 5
        assert packet["device_profile"]["detail_disclosure_mode"] == "collapsed_by_default"


def test_machine_language_terms_are_forbidden_and_absent_from_visible_content():
    payload = _build()
    visible = _visible_text(payload)

    assert payload["machine_proof"]["machine_language_terms_absent"] is True
    for forbidden in render.FORBIDDEN_VISIBLE_TERMS:
        assert forbidden.lower() not in visible.lower()


def test_no_raw_pii_or_private_bodies_in_generated_outputs(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--source-translation", str(SOURCE_TRANSLATION), "--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])
    data = json.loads(json_path.read_text(encoding="utf-8"))
    combined = json_path.read_text(encoding="utf-8") + "\n" + operator_path.read_text(encoding="utf-8")

    assert data["machine_proof"]["credentials_or_secrets_included"] is False
    assert data["machine_proof"]["raw_private_bodies_included"] is False
    assert data["machine_proof"]["raw_pii_in_visible_content"] is False
    assert "@" not in combined
    assert not re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", combined)
    assert "raw_email_body" not in combined
    assert "raw_screenshot_body" not in combined
    assert "ELIOPERATOR" in operator_path.read_text(encoding="utf-8")


def test_authority_boundary_all_live_flags_false():
    payload = _build()

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    assert payload["machine_proof"]["all_operator_actions_external_false"] is True
    assert payload["machine_proof"]["network_used"] is False
    assert payload["machine_proof"]["mac_sync_import_run"] is False
    assert payload["machine_proof"]["mission_control_swift_changed"] is False


def test_operator_markdown_is_plain_and_boundary_focused():
    payload = _build()
    markdown = render.format_operator_markdown(payload)

    assert "ELIOPERATOR" in markdown
    assert "What I understood" in markdown
    assert "Still locked" in markdown
    assert "INVOICE SENT" in markdown
    assert "Waiting on PC" in markdown
    assert "No live visual agent" in markdown
    assert "payload_hash" not in markdown
    assert "idempotency" not in markdown.lower()
    assert "SQLite" not in markdown


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "operator_card_render_packet_contract.py",
            "scripts/export_operator_card_render_packet_contract.py",
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
