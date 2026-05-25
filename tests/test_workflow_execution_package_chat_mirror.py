import json
import re
from pathlib import Path

import workflow_execution_package_chat_mirror as mirror
from scripts.export_workflow_execution_package_chat_mirror import main as export_main


FIXED_NOW = "2026-05-25T08:00:00+00:00"
SOURCE_READMODEL = Path("generated/read_models/workflow_execution_package_compiler.json")


def _build(source: Path = SOURCE_READMODEL) -> dict:
    return mirror.build_workflow_execution_package_chat_mirror(source_readmodel_path=source, generated_at=FIXED_NOW)


def _visible_text(payload: dict) -> str:
    chunks = []
    card_mirror = payload["workflow_execution_package_chat_mirror"]
    chunks.append(card_mirror["assistant_lead_in"])
    chunks.append(card_mirror["safe_display_summary"])
    for card in card_mirror["cards"]:
        chunks.extend([card["title"], card["summary"]])
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
    assert first["machine_proof"]["package_execution_performed"] is False


def test_required_models_exist():
    payload = _build()

    assert payload["machine_proof"]["workflow_execution_package_chat_mirror_model_present"] is True
    assert payload["machine_proof"]["workflow_execution_chat_card_model_present"] is True
    assert payload["model_schemas"]["workflow_execution_package_chat_mirror"]["required_fields"] == list(mirror.REQUIRED_MIRROR_FIELDS)
    assert payload["model_schemas"]["workflow_execution_chat_card"]["required_fields"] == list(mirror.REQUIRED_CARD_FIELDS)


def test_source_compiler_loads_and_mirror_ready():
    payload = _build()
    card_mirror = payload["workflow_execution_package_chat_mirror"]

    assert payload["source_readmodel_present"] is True
    assert card_mirror["source_readmodel_ref"] == "workflow_execution_package_compiler"
    assert card_mirror["workflow_type"] == "invoice_delivery_workflow"
    assert card_mirror["client_ref"] == "Capital Hilton"
    assert card_mirror["mirror_status"] == "READY_FOR_MAC_RENDER"
    assert payload["machine_proof"]["ready_for_mac_render"] is True


def test_required_cards_exist_with_human_titles():
    payload = _build()
    cards = payload["workflow_execution_package_chat_mirror"]["cards"]
    titles = {card["title"] for card in cards}

    assert payload["machine_proof"]["required_cards_present"] is True
    assert {
        "Make it happen status",
        "Known",
        "Still needed",
        "Worker packages",
        "Still locked",
        "Completion target",
    }.issubset(titles)


def test_make_it_happen_status_card_says_nothing_ran():
    payload = _build()
    status = next(card for card in payload["workflow_execution_package_chat_mirror"]["cards"] if card["title"] == "Make it happen status")

    assert "Nothing has run." in status["summary"]
    assert "External actions remain locked." in status["bullets"]
    assert status["truth_status"] == "BACKEND_READBACK_READY"
    assert status["proof_status"] == "PROOF_REQUIRED_BEFORE_COMPLETION"


def test_known_still_needed_and_locked_cards_are_correct():
    payload = _build()
    cards = {card["title"]: card for card in payload["workflow_execution_package_chat_mirror"]["cards"]}

    assert "4 performance dates are captured." in cards["Known"]["bullets"]
    assert "$400 per show, $1,600 working basis." in cards["Known"]["bullets"]
    assert "Exact Coupa PO/reference." in cards["Still needed"]["bullets"]
    assert "Confirmation that Annette is the correct contact." in cards["Still needed"]["bullets"]
    assert "No email draft or send." in cards["Still locked"]["bullets"]
    assert "No Coupa access or submit." in cards["Still locked"]["bullets"]
    assert cards["Still locked"]["truth_status"] == "LOCKED_EXTERNAL_ACTION"


def test_worker_packages_card_uses_human_labels_not_package_ids():
    payload = _build()
    card = next(card for card in payload["workflow_execution_package_chat_mirror"]["cards"] if card["title"] == "Worker packages")
    text = "\n".join([card["summary"], *card["bullets"], *card["detail_bullets"]])

    assert "7 worker package plans would be needed" in card["summary"]
    assert "PC backend validation." in card["bullets"]
    assert "Mac artifact preparation." in card["bullets"]
    assert "package_plan_" not in text
    assert "PC_BACKEND_VALIDATION_PACKAGE" not in text
    assert "MAC_ARTIFACT_PREP_PACKAGE" not in text


def test_completion_target_is_future_only_and_blocked():
    payload = _build()
    card = next(card for card in payload["workflow_execution_package_chat_mirror"]["cards"] if card["title"] == "Completion target")

    assert "INVOICE SENT is the future target" in card["summary"]
    assert card["truth_status"] == "FUTURE_TARGET_ONLY"
    assert card["proof_status"] == "COMPLETION_BLOCKED_MISSING_PROOF"
    assert "Email send receipt with invoice attachment." in card["bullets"]


def test_operator_choices_and_disabled_future_action():
    payload = _build()
    choices = {choice["label"]: choice for choice in payload["workflow_execution_package_chat_mirror"]["operator_choices"]}

    assert choices["Answer missing info"]["enabled"] is True
    assert choices["Review package plan"]["enabled"] is True
    assert choices["Cancel"]["enabled"] is True
    assert choices["Prepare/send packages"]["enabled"] is False
    assert choices["Prepare/send packages"]["external_authority"] is False


def test_visible_card_text_has_no_machine_terms():
    payload = _build()
    visible = _visible_text(payload)

    assert payload["machine_proof"]["human_copy_only"] is True
    for term in mirror.FORBIDDEN_VISIBLE_TERMS:
        assert term not in visible
    assert "workflow_execution_package_compiler" not in visible


def test_authority_boundary_all_false():
    payload = _build()

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    assert payload["machine_proof"]["agent_dispatch_performed"] is False
    assert payload["machine_proof"]["workflow_run_performed"] is False
    assert payload["machine_proof"]["invoice_generation_performed"] is False


def test_missing_source_fails_closed(tmp_path):
    payload = _build(tmp_path / "missing.json")

    assert payload["workflow_execution_package_chat_mirror"]["mirror_status"] == "SOURCE_READMODEL_MISSING"
    assert payload["machine_proof"]["ready_for_mac_render"] is False
    assert payload["workflow_execution_package_chat_mirror"]["cards"][0]["title"] == "Waiting on PC readback"


def test_export_writes_parseable_json(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--source-readmodel", str(SOURCE_READMODEL), "--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    data = json.loads(json_path.read_text(encoding="utf-8"))

    assert summary["mirror_status"] == "READY_FOR_MAC_RENDER"
    assert "Make it happen status" in summary["card_titles"]
    assert summary["required_cards_present"] is True
    assert data["machine_proof"]["all_live_authority_flags_false"] is True


def test_generated_output_has_no_raw_pii_or_secrets(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--source-readmodel", str(SOURCE_READMODEL), "--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    data = json.loads(json_path.read_text(encoding="utf-8"))
    text = json_path.read_text(encoding="utf-8")

    assert data["machine_proof"]["credentials_or_secrets_included"] is False
    assert data["machine_proof"]["raw_private_bodies_included"] is False
    assert data["machine_proof"]["raw_pii_in_cards"] is False
    assert "@" not in text
    assert not re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", text)
    assert "access_token" not in text.lower()
    assert "private key" not in text.lower()


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "workflow_execution_package_chat_mirror.py",
            "scripts/export_workflow_execution_package_chat_mirror.py",
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
