import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SURFACE_PATH = ROOT / "generated/read_models/helm_actionability_surface.json"
BRIDGE_PATH = Path("/mnt/e/openclaw/generated/read_models/helm_actionability_surface.json")


def _surface() -> dict:
    return json.loads(SURFACE_PATH.read_text(encoding="utf-8"))


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def _question(surface: dict, text: str) -> dict:
    return next(
        item
        for item in surface["suggested_questions"]
        if item["question_text"] == text
    )


def _card(surface: dict, card_id: str) -> dict:
    return next(item for item in surface["action_cards"] if item["card_id"] == card_id)


def test_safe_next_question_has_concrete_action():
    surface = _surface()
    question = _question(surface, "What is safe next?")

    assert surface["schema_version"] == "helm_actionability_surface_v0"
    assert surface["surface_ref"] == "helm_actionability_surface"
    assert surface["mode"] == "operator_calm"
    assert question["action"]["action_type"] == "navigate"
    assert question["action"]["target_world_ref"] == "finance"
    assert question["action"]["target_thread_ref"] == "st_annes"
    assert question["action"]["payload_ref"] == "generated/read_models/st_annes_work_log_review_surface.json"


def test_st_annes_smoke_event_has_mark_test_or_discard_action():
    surface = _surface()
    card = _card(surface, "st_annes_smoke_work_log_event")
    labels = {card["action_label"]} | {
        action["label"] for action in card.get("secondary_actions", [])
    }

    assert card["speaker_ref"] == "cassandra"
    assert card["business_action"] is False
    assert "Mark as test" in labels or "Discard smoke event" in labels
    assert "Confirm as real work" in labels
    assert card["invoice_inclusion_allowed"] is False


def test_guardian_checklist_has_ordered_safe_items():
    surface = _surface()
    labels = [item["plain_label"] for item in surface["guardian_checklist"]]

    assert labels == [
        "Email send locked",
        "Coupa submit locked",
        "Ledger posting locked",
        "Excel mutation locked",
        "PDF export locked",
    ]
    assert all(item["status"] == "locked" for item in surface["guardian_checklist"])
    assert all(item["safe_action"] for item in surface["guardian_checklist"])


def test_capital_hilton_proposal_navigates_to_business_development_without_send():
    surface = _surface()
    card = _card(surface, "capital_hilton_proposal_watch")

    assert card["action_type"] == "navigate"
    assert card["target_world_ref"] == "business_development"
    assert card["target_thread_ref"] == "capital_hilton"
    assert card["business_action"] is False
    assert "send" not in card["action_label"].lower()


def test_capital_hilton_payment_watch_navigates_to_finance_without_coupa():
    surface = _surface()
    card = _card(surface, "capital_hilton_payment_watch")

    assert card["action_type"] == "navigate"
    assert card["target_world_ref"] == "finance"
    assert card["target_thread_ref"] == "capital_hilton"
    assert card["business_action"] is False
    assert "coupa" not in card["action_label"].lower()


def test_proof_explainers_exist_but_proof_is_collapsed():
    surface = _surface()

    assert surface["history_policy"]["proof_collapsed_by_default"] is True
    assert surface["proof_explainers"]
    assert all("raw_proof" not in item for item in surface["proof_explainers"])
    assert all(item["question_text"] == "What does this proof mean?" for item in surface["proof_explainers"])


def test_authority_flags_are_false():
    boundary = _surface()["authority_boundary"]

    assert boundary
    assert all(value is False for value in boundary.values())


def test_json_parse_local_and_bridge_match():
    local = _surface()
    bridge = json.loads(BRIDGE_PATH.read_text(encoding="utf-8"))

    assert bridge == local


def test_unsafe_true_grant_scan_is_clean():
    surface = _surface()
    unsafe_keys = {
        "email_send_allowed",
        "ledger_posting_allowed",
        "browser_access_allowed",
        "gmail_allowed",
        "coupa_allowed",
        "portal_submit_allowed",
        "sent",
        "paid",
    }

    assert not [
        (key, value)
        for key, value in _walk_values(surface)
        if key in unsafe_keys and value is True
    ]
    assert surface["machine_proof"]["unsafe_true_grants_absent"] is True
