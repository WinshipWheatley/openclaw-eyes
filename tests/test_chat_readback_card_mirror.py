import json
import re
from pathlib import Path

import chat_readback_card_mirror as mirror
from scripts.export_chat_readback_card_mirror import main as export_main


FIXED_NOW = "2026-05-25T00:45:00+00:00"
SOURCE_READBACK = Path("generated/read_models/conversational_workflow_router_readback.json")


def _build(source: Path = SOURCE_READBACK) -> dict:
    return mirror.build_chat_readback_card_mirror(source_readback_path=source, generated_at=FIXED_NOW)


def _visible_card_text(payload: dict) -> str:
    chunks = []
    for card in payload["chat_readback_card_mirror"]["cards"]:
        chunks.extend([card["title"], card["subtitle"]])
        chunks.extend(card["bullets"])
        chunks.extend(card["operator_actions"])
    return "\n".join(chunks).lower()


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert mirror.stable_json(first) == mirror.stable_json(second)
    assert first["schema_version"] == mirror.SCHEMA_VERSION
    assert first["read_model_id"] == mirror.READ_MODEL_ID
    assert first["contract_status"] == mirror.CONTRACT_STATUS
    assert first["machine_proof"]["all_live_authority_flags_false"] is True
    assert first["machine_proof"]["external_action_performed"] is False


def test_required_models_exist():
    payload = _build()
    proof = payload["machine_proof"]
    schemas = payload["model_schemas"]

    assert proof["chat_readback_card_mirror_model_present"] is True
    assert proof["chat_human_card_model_present"] is True
    assert proof["chat_readback_freshness_model_present"] is True
    assert proof["chat_readback_action_availability_model_present"] is True
    assert proof["chat_readback_mirror_blocker_model_present"] is True
    assert schemas["chat_readback_card_mirror"]["required_fields"] == list(mirror.REQUIRED_MIRROR_FIELDS)
    assert schemas["chat_human_card"]["required_fields"] == list(mirror.REQUIRED_CARD_FIELDS)
    assert schemas["chat_readback_freshness"]["required_fields"] == list(mirror.REQUIRED_FRESHNESS_FIELDS)
    assert schemas["chat_readback_action_availability"]["required_fields"] == list(mirror.REQUIRED_AVAILABILITY_FIELDS)


def test_mirror_reads_current_router_readback_and_is_ready():
    payload = _build()
    card_mirror = payload["chat_readback_card_mirror"]

    assert payload["source_readback_present"] is True
    assert card_mirror["mirror_status"] == "READY_FOR_MAC_RENDER"
    assert card_mirror["source_readback_ref"] == "conversational_workflow_router_readback"
    assert card_mirror["workflow_type"] == "invoice_delivery_workflow"
    assert card_mirror["client_ref"] == "capital_hilton"
    assert card_mirror["world_ref"] == "finance"
    assert payload["chat_readback_freshness"]["freshness_status"] == "CURRENT"
    assert payload["machine_proof"]["mirror_ready_for_mac_if_routed"] is True


def test_capital_hilton_cards_are_mirrored():
    payload = _build()
    cards = payload["chat_readback_card_mirror"]["cards"]
    titles = {card["title"] for card in cards}

    assert payload["machine_proof"]["capital_hilton_cards_mirrored"] is True
    assert {
        "OpenClaw understood",
        "Proposed workflow",
        "What still needs to be confirmed",
        "What is not happening yet",
    }.issubset(titles)
    understood = next(card for card in cards if card["title"] == "OpenClaw understood")
    assert "Excel/PDF invoice" in " ".join(understood["bullets"])
    assert "Annette" in " ".join(understood["bullets"])
    assert "Coupa supplier portal invoice from PO" in " ".join(understood["bullets"])
    assert understood["truth_status"] == "DRAFT_UNDERSTANDING_NOT_TRUTH"


def test_locked_actions_and_next_safe_move_are_preserved():
    payload = _build()
    card_mirror = payload["chat_readback_card_mirror"]

    for action in [
        "email send",
        "Coupa access",
        "browser automation",
        "invoice submission",
        "approval request",
        "invoice generation",
        "attachment",
        "payment state change",
    ]:
        assert action in card_mirror["locked_actions"]
    assert "ask whether the understanding looks right" in card_mirror["next_safe_move"]
    assert payload["machine_proof"]["external_actions_locked"] is True


def test_operator_choices_are_disabled_unless_supported():
    payload = _build()
    choices = {choice["operator_action"]: choice for choice in payload["chat_readback_action_availability"]}

    assert choices["Looks right"]["enabled"] is True
    assert choices["Edit understanding"]["enabled"] is True
    assert choices["Cancel"]["enabled"] is True
    assert choices["Store as procedure"]["enabled"] is False
    assert choices["Store as procedure"]["disabled_reason"] == "Backend procedure memory write is not connected yet."
    assert choices["Prepare package"]["enabled"] is False
    assert choices["Prepare package"]["disabled_reason"] == "Backend package creation is not connected yet."
    assert payload["machine_proof"]["operator_choices_disabled_unless_supported"] is True


def test_waiting_status_when_source_readback_missing(tmp_path):
    missing = tmp_path / "missing_router_readback.json"
    payload = _build(missing)
    card_mirror = payload["chat_readback_card_mirror"]

    assert card_mirror["mirror_status"] == "SOURCE_READBACK_MISSING"
    assert payload["chat_readback_freshness"]["freshness_status"] == "WAITING"
    assert card_mirror["cards"][0]["card_type"] == "WAITING"
    assert "No current understanding has returned yet" in card_mirror["cards"][0]["subtitle"]
    assert "SOURCE_READBACK_MISSING" in {
        blocker["blocker_type"] for blocker in payload["active_blockers_by_id"].values()
    }
    assert payload["machine_proof"]["waiting_status_modelled"] is True


def test_source_request_missing_status_when_router_has_no_request(tmp_path):
    source = {
        "read_model_id": "conversational_workflow_router_readback",
        "route_mode": "NO_REQUEST_AVAILABLE",
        "intake_result": {"parse_status": "NEEDS_MORE_DETAIL"},
        "router_readback_package": {
            "cards": [],
            "operator_choices": [],
            "source_request_ref": None,
        },
    }
    path = tmp_path / "no_request.json"
    path.write_text(mirror.stable_json(source), encoding="utf-8")
    payload = _build(path)

    assert payload["chat_readback_card_mirror"]["mirror_status"] == "SOURCE_REQUEST_MISSING"
    assert payload["chat_readback_card_mirror"]["cards"][0]["card_type"] == "WAITING"
    assert payload["chat_readback_freshness"]["freshness_status"] == "WAITING"


def test_stale_source_mismatch_blocker_exists(tmp_path):
    source = json.loads(SOURCE_READBACK.read_text(encoding="utf-8"))
    source["router_readback_package"]["source_request_ref"] = "different_request"
    path = tmp_path / "stale.json"
    path.write_text(mirror.stable_json(source), encoding="utf-8")
    payload = _build(path)

    assert payload["chat_readback_card_mirror"]["mirror_status"] == "STALE_SOURCE_READBACK"
    assert payload["chat_readback_freshness"]["freshness_status"] == "SOURCE_MISMATCH"
    assert payload["chat_readback_card_mirror"]["cards"][0]["card_type"] == "STALE"
    assert payload["machine_proof"]["stale_source_blocker_exists"] is True
    assert "SOURCE_READBACK_STALE" in {
        blocker["blocker_type"] for blocker in payload["active_blockers_by_id"].values()
    }


def test_machine_contract_language_is_absent_from_normal_cards():
    payload = _build()
    visible = _visible_card_text(payload)

    for term in mirror.FORBIDDEN_NORMAL_CARD_TERMS:
        assert term not in visible
    assert payload["machine_proof"]["machine_contract_language_absent_from_cards"] is True


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
    assert export_main(["--source-readback", str(SOURCE_READBACK), "--export-root", str(export_root), "--format", "summary"]) == 0
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


def test_operator_markdown_explains_mirror_boundary():
    payload = _build()
    markdown = mirror.format_operator_markdown(payload)

    assert "ELIOPERATOR" in markdown
    assert "Mac-renderable human cards" in markdown
    assert "does not run workflows" in markdown
    assert "does not send, submit, approve" in markdown
    assert "OpenClaw understood" in markdown
    assert "schema" not in markdown.lower()
    assert "handler" not in markdown.lower()
    assert "manifest" not in markdown.lower()
    assert "payload_hash" not in markdown


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "chat_readback_card_mirror.py",
            "scripts/export_chat_readback_card_mirror.py",
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
