import json
from pathlib import Path

import operator_next_decision as decision


ROOT = Path(__file__).resolve().parents[1]
DECISION_PATH = ROOT / "generated/read_models/operator_next_decision.json"
BRIDGE_PATH = Path("/mnt/e/openclaw/generated/read_models/operator_next_decision.json")


def _surface(cards: list[dict], *, primary: dict | None = None) -> dict:
    return {
        "status": "HELM_ACTIONABILITY_SURFACE_READY",
        "primary_next_action": primary or {},
        "action_cards": cards,
        "history_policy": {
            "proof_collapsed_by_default": True,
            "show_full_history_by_default": False,
        },
    }


def _st_annes_card(**overrides) -> dict:
    card = {
        "card_id": "st_annes_smoke_work_log_event",
        "speaker_ref": "cassandra",
        "headline": "St. Anne's church sound entry is staged.",
        "plain_summary": "Review the event.",
        "action_label": "Open St. Anne's review",
        "action_type": "review_event",
        "target_world_ref": "finance",
        "target_thread_ref": "st_annes",
        "payload_ref": "generated/read_models/st_annes_work_log_review_surface.json#event-1",
        "business_action": False,
    }
    card.update(overrides)
    return card


def _capital_payment_card(**overrides) -> dict:
    card = {
        "card_id": "capital_hilton_payment_watch",
        "speaker_ref": "chief",
        "headline": "Capital Hilton payment watch is finance-only.",
        "plain_summary": "The invoice run is recorded, payment truth is not created here.",
        "action_label": "Open Capital Hilton",
        "action_type": "navigate",
        "target_world_ref": "finance",
        "target_thread_ref": "capital_hilton",
        "payload_ref": "generated/read_models/capital_hilton_invoice_operator_run_status.json",
        "business_action": False,
    }
    card.update(overrides)
    return card


def _workboard() -> dict:
    return {"status": "READY_FOR_OPERATOR_REVIEW"}


def test_unresolved_st_annes_review_becomes_next_decision():
    payload = decision.choose_next_decision(
        actionability_surface=_surface([_st_annes_card(), _capital_payment_card()]),
        lifecycle_status={"resolved_actions": []},
        overnight_workboard=_workboard(),
        st_annes_events={"staged_events": [{"event_id": "event-1", "invoice_inclusion_status": "NOT_INCLUDED_OPERATOR_CONFIRMATION_REQUIRED"}]},
    )

    assert payload["headline"] == "Clear the St. Anne's work-log item"
    assert payload["plain_summary"] == "Mark it as test or confirm it as real work."
    assert payload["action_label"] == "Open St. Anne's review"
    assert payload["target_world_ref"] == "finance"
    assert payload["target_thread_ref"] == "st_annes"
    assert payload["action_type"] == "review_event"


def test_resolved_test_event_is_excluded_and_capital_payment_watch_can_win():
    payload = decision.choose_next_decision(
        actionability_surface=_surface(
            [
                _st_annes_card(lifecycle_status="RESOLVED_TEST_EVENT", visible_by_default=False),
                _capital_payment_card(),
            ]
        ),
        lifecycle_status={
            "resolved_actions": [{"card_id": "st_annes_smoke_work_log_event", "status": "RESOLVED_TEST_EVENT"}]
        },
        overnight_workboard=_workboard(),
        st_annes_events={"staged_events": [{"event_id": "event-1", "invoice_inclusion_status": "NOT_INCLUDED_SMOKE_EVENT"}]},
    )

    assert payload["headline"] == "Watch Capital Hilton payment"
    assert payload["plain_summary"] == "Coupa is processing. Ledger stays untouched until payment proof arrives."
    assert payload["action_label"] == "Open Capital Hilton"
    assert payload["target_thread_ref"] == "capital_hilton"
    assert "st_annes_smoke_work_log_event" in payload["excluded_items"]


def test_send_coupa_and_ledger_actions_are_never_next_safe_action():
    cards = [
        _capital_payment_card(card_id="send_email", action_label="Send email", action_type="send_email"),
        _capital_payment_card(card_id="submit_coupa", action_label="Submit Coupa", action_type="coupa_submit"),
        _capital_payment_card(card_id="post_ledger", action_label="Post ledger", action_type="ledger_post"),
    ]

    payload = decision.choose_next_decision(
        actionability_surface=_surface(cards),
        lifecycle_status={"resolved_actions": []},
        overnight_workboard=_workboard(),
        st_annes_events={"staged_events": []},
    )

    assert payload["action_type"] == "open_workboard"
    assert payload["business_action"] is False
    assert payload["target_world_ref"] != "coupa"
    assert all(word not in payload["action_label"].lower() for word in ("send", "coupa", "ledger"))


def test_no_active_items_returns_no_urgent_action():
    payload = decision.choose_next_decision(
        actionability_surface=_surface([]),
        lifecycle_status={"resolved_actions": []},
        overnight_workboard=_workboard(),
        st_annes_events={"staged_events": []},
    )

    assert payload["headline"] == "No urgent action"
    assert payload["plain_summary"] == "Client work is recorded. Review the workboard when you are ready."
    assert payload["action_label"] == "Open workboard"
    assert payload["action_type"] == "open_workboard"


def test_generated_decision_json_parse_and_bridge_match():
    local = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    bridge = json.loads(BRIDGE_PATH.read_text(encoding="utf-8"))

    assert bridge == local
    assert local["schema_version"] == "operator_next_decision_v0"
    assert local["status"] == "READY"
    if local["action_type"] == "navigate":
        assert local["target_world_ref"]
        assert local["target_thread_ref"]


def test_authority_flags_and_unsafe_scan_are_clean():
    payload = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
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

    assert all(value is False for value in payload["authority_boundary"].values())
    assert not [
        key
        for key, value in payload["authority_boundary"].items()
        if key in unsafe_keys and value is True
    ]
    assert payload["machine_proof"]["unsafe_true_grants_absent"] is True
