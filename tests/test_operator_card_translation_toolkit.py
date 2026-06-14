import json
import re
from pathlib import Path

import operator_card_translation_toolkit as toolkit
from scripts.export_operator_card_translation_mirror import main as export_main


FIXED_NOW = "2026-05-25T01:05:00+00:00"
SOURCE_MIRROR = Path("generated/read_models/chat_readback_card_mirror.json")


def _build(source: Path = SOURCE_MIRROR) -> dict:
    return toolkit.build_operator_card_translation_mirror(source_mirror_path=source, generated_at=FIXED_NOW)


def _normal_card_text(payload: dict) -> str:
    mirror = payload["operator_ready_card_mirror"]
    chunks = [mirror["assistant_lead_in"], mirror["truth_boundary"]]
    for card in mirror["cards"]:
        chunks.extend([card["human_title"], card["human_summary"]])
        chunks.extend(card["visible_bullets"])
        chunks.extend(card["detail_bullets"])
    for choice in mirror["operator_choices"]:
        chunks.extend([choice["human_label"], choice.get("disabled_reason") or ""])
    for choice in mirror["future_actions"]:
        chunks.extend([choice["human_label"], choice.get("disabled_reason") or ""])
    return "\n".join(chunks)


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert toolkit.stable_json(first) == toolkit.stable_json(second)
    assert first["schema_version"] == toolkit.SCHEMA_VERSION
    assert first["read_model_id"] == toolkit.READ_MODEL_ID
    assert first["contract_status"] == toolkit.CONTRACT_STATUS
    assert first["machine_proof"]["all_live_authority_flags_false"] is True
    assert first["machine_proof"]["external_action_performed"] is False


def test_required_models_exist():
    payload = _build()
    proof = payload["machine_proof"]
    schemas = payload["model_schemas"]

    assert proof["operator_card_translation_toolkit_model_present"] is True
    assert proof["operator_ready_card_mirror_model_present"] is True
    assert proof["operator_ready_card_model_present"] is True
    assert proof["machine_language_filter_model_present"] is True
    assert proof["operator_choice_translation_model_present"] is True
    assert proof["operator_card_translation_blocker_model_present"] is True
    assert schemas["operator_card_translation_toolkit"]["required_fields"] == list(toolkit.REQUIRED_TOOLKIT_FIELDS)
    assert schemas["operator_ready_card_mirror"]["required_fields"] == list(toolkit.REQUIRED_MIRROR_FIELDS)
    assert schemas["operator_ready_card"]["required_fields"] == list(toolkit.REQUIRED_CARD_FIELDS)


def test_source_mirror_loads_and_translation_is_ready():
    payload = _build()
    mirror = payload["operator_ready_card_mirror"]

    assert payload["machine_proof"]["source_mirror_loads"] is True
    assert mirror["source_mirror_ref"] == "chat_readback_card_mirror"
    assert mirror["translation_status"] == "READY_FOR_OPERATOR_RENDER"
    assert mirror["assistant_lead_in"] == "I got the PC readback. Here's what OpenClaw thinks you mean."
    assert payload["machine_language_filter"]["blocked_terms_found"] == ()


def test_capital_hilton_cards_translate_to_operator_ready_titles_and_copy():
    payload = _build()
    cards = {card["human_title"]: card for card in payload["operator_ready_card_mirror"]["cards"]}

    assert payload["machine_proof"]["capital_hilton_cards_translate"] is True
    assert set(cards) == {"What I understood", "The plan", "Still needed", "Still locked"}
    assert cards["What I understood"]["human_summary"] == (
        "Capital Hilton invoice: 4 dates at $400 each. OpenClaw thinks you want a Winship-branded "
        "Excel/PDF invoice sent to Annette, while Coupa/PO remains the official payment path."
    )
    assert cards["The plan"]["human_summary"] == (
        "Confirm the dates/rate, build the invoice artifact, confirm Coupa/PO, draft the email to "
        "Annette, get Guardian approval, then send/submit only after gates are satisfied."
    )
    assert cards["Still needed"]["human_summary"] == (
        "Exact Coupa PO/reference, confirmation that Annette is the right contact, final invoice "
        "artifact/hash, Guardian approval, and send/submit receipts."
    )
    assert cards["Still locked"]["human_summary"] == (
        "Nothing external happened. No email, Coupa access, browser, approval, invoice generation, "
        "attachment, or payment update."
    )


def test_visible_bullets_are_compressed_and_details_available():
    payload = _build()
    cards = payload["operator_ready_card_mirror"]["cards"]

    assert payload["machine_proof"]["visible_bullets_compressed"] is True
    assert payload["machine_proof"]["detail_bullets_available"] is True
    for card in cards:
        assert 1 <= len(card["visible_bullets"]) <= 5
        assert card["detail_available"] is True
        assert card["detail_bullets"]


def test_readback_prefix_and_machine_language_removed_from_normal_output():
    payload = _build()
    text = _normal_card_text(payload)

    assert payload["machine_proof"]["readback_prefix_removed"] is True
    assert payload["machine_proof"]["machine_language_absent_from_normal_cards"] is True
    assert "Readback:" not in text
    for forbidden in toolkit.FORBIDDEN_NORMAL_UI_TERMS:
        assert forbidden.lower() not in text.lower()


def test_operator_choices_translated_and_future_actions_disabled():
    payload = _build()
    choices = {choice["human_label"]: choice for choice in payload["operator_ready_card_mirror"]["operator_choices"]}
    future = {choice["human_label"]: choice for choice in payload["operator_ready_card_mirror"]["future_actions"]}

    assert payload["machine_proof"]["operator_choices_translated"] is True
    assert set(choices) == {"Looks right", "Change something", "What's missing?"}
    assert choices["Looks right"]["enabled"] is True
    assert choices["Looks right"]["truth_effect"] == "does not write backend truth by itself"
    assert choices["Change something"]["action_scope"] == "return to chat input/edit"
    assert choices["What's missing?"]["action_scope"] == "explain missing info"
    assert payload["machine_proof"]["future_actions_disabled"] is True
    assert future["Store as procedure"]["enabled"] is False
    assert future["Store as procedure"]["disabled_reason"] == "Backend procedure memory write is not connected yet."
    assert future["Prepare package"]["enabled"] is False
    assert future["Prepare package"]["disabled_reason"] == "Backend package creation is not connected yet."


def test_truth_boundary_and_external_locks_are_preserved():
    payload = _build()
    mirror = payload["operator_ready_card_mirror"]

    assert payload["machine_proof"]["truth_boundary_preserved"] is True
    assert mirror["truth_boundary"] == toolkit.TRUTH_BOUNDARY
    assert toolkit.TRUTH_BOUNDARY in _normal_card_text(payload)
    assert payload["machine_proof"]["external_actions_locked"] is True
    still_locked = next(card for card in mirror["cards"] if card["human_title"] == "Still locked")
    assert "Nothing external happened." in still_locked["visible_bullets"]
    assert "External actions remain locked." in still_locked["visible_bullets"]


def test_source_missing_fails_closed(tmp_path):
    missing = tmp_path / "missing_mirror.json"
    payload = _build(missing)

    assert payload["operator_ready_card_mirror"]["translation_status"] == "SOURCE_MISSING"
    assert "SOURCE_MIRROR_MISSING" in {
        blocker["blocker_type"] for blocker in payload["active_blockers_by_id"].values()
    }


def test_source_stale_fails_closed(tmp_path):
    source = json.loads(SOURCE_MIRROR.read_text(encoding="utf-8"))
    source["chat_readback_card_mirror"]["mirror_status"] = "STALE_SOURCE_READBACK"
    path = tmp_path / "stale_mirror.json"
    path.write_text(toolkit.stable_json(source), encoding="utf-8")
    payload = _build(path)

    assert payload["operator_ready_card_mirror"]["translation_status"] == "SOURCE_STALE"
    assert "SOURCE_MIRROR_STALE" in {
        blocker["blocker_type"] for blocker in payload["active_blockers_by_id"].values()
    }


def test_authority_boundary_all_live_flags_false():
    payload = _build()

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    assert payload["machine_proof"]["network_used"] is False
    assert payload["machine_proof"]["mac_sync_import_run"] is False
    assert payload["machine_proof"]["mission_control_swift_changed"] is False


def test_generated_outputs_have_no_raw_pii_or_secret_like_values(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--source-mirror", str(SOURCE_MIRROR), "--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])
    data = json.loads(json_path.read_text(encoding="utf-8"))
    combined = json_path.read_text(encoding="utf-8") + "\n" + operator_path.read_text(encoding="utf-8")

    assert data["machine_proof"]["credentials_or_secrets_included"] is False
    assert data["machine_proof"]["raw_private_bodies_included"] is False
    assert data["machine_proof"]["raw_pii_in_cards"] is False
    assert "@" not in combined
    assert not re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", combined)
    assert "raw_email_body" not in combined
    assert "raw_screenshot_body" not in combined
    assert "ELIOPERATOR" in operator_path.read_text(encoding="utf-8")


def test_operator_markdown_is_operator_ready():
    payload = _build()
    markdown = toolkit.format_operator_markdown(payload)

    assert "ELIOPERATOR" in markdown
    assert "What I understood" in markdown
    assert "The plan" in markdown
    assert "Still needed" in markdown
    assert "Still locked" in markdown
    assert "Readback:" not in markdown
    assert "payload_hash" not in markdown
    assert "idempotency" not in markdown.lower()
    assert "SQLite" not in markdown


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "operator_card_translation_toolkit.py",
            "scripts/export_operator_card_translation_mirror.py",
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
