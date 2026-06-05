import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import dynamic_card_packet as cards


FIXED_NOW = "2026-06-04T16:30:00+00:00"


def _latest():
    return cards.build_latest_packet(generated_at=FIXED_NOW)


def _by_id(packet):
    return {card["card_id"]: card for card in packet["cards"]}


def _assert_no_unsafe_true(payload):
    assert cards.unsafe_true_grants(payload) == []


def _enabled_actions(packet):
    for card in packet["cards"]:
        for action in card["actions"]:
            if action["enabled"] is True:
                yield card, action


def test_capital_hilton_payment_watch_card_generated_no_coupa_or_ledger_action():
    packet = _latest()
    card = _by_id(packet)["dynamic_card.finance.capital_hilton.payment_watch"]

    assert card["card_type"] == "payment_watch"
    assert card["headline"] == "Stay on payment watch"
    assert card["plain_summary"] == (
        "Coupa is processing. Wait for payment evidence before anything touches the ledger."
    )
    assert card["trust_state"] == "trusted_current"
    assert card["actions"] == [
        {
            "action_id": "capital_hilton.payment.open_finance",
            "label": "Open Finance / Capital Hilton",
            "action_type": "navigate",
            "enabled": True,
            "disabled_reason": None,
            "payload_ref": (
                "generated/read_models/operator_action_payloads.json#"
                "action_payloads.capital_hilton.payment.open_finance"
            ),
            "business_action": False,
        }
    ]
    assert card["authority_boundary"]["coupa_allowed"] is False
    assert card["authority_boundary"]["ledger_posting_allowed"] is False
    assert packet["machine_proof"]["coupa_access_performed"] is False
    assert packet["machine_proof"]["ledger_mutation_performed"] is False
    _assert_no_unsafe_true(packet)


def test_contextual_question_answer_card_generated_for_finance_capital_hilton():
    packet = _latest()
    card = _by_id(packet)["dynamic_card.finance.capital_hilton.contextual_question"]

    assert card["card_type"] == "answer"
    assert card["headline"] == "Stay on payment watch"
    assert card["plain_summary"] == (
        "Coupa is processing. Wait for payment evidence before anything touches the ledger."
    )
    assert "not package staging" in " ".join(card["supporting_lines"])
    assert card["trust_state"] == "trusted_current"


def test_evidence_intake_card_example_generated_no_ledger_or_paid_action():
    packet = _latest()
    card = _by_id(packet)["dynamic_card.finance.live_arts_md.evidence_intake.payment_processing"]

    assert card["card_type"] == "evidence_intake"
    assert card["headline"] == "Payment proof received"
    assert card["plain_summary"] == (
        "This appears to show payment processing for invoice 2026-1001. "
        "Ledger remains untouched until payment is confirmed."
    )
    assert card["status_label"] == "Processing evidence"
    assert card["trust_state"] == "operator_reported"
    assert {action["label"] for action in card["actions"]} == {
        "Attach to lane",
        "Ask what this means",
        "Mark as test",
        "Show details",
    }
    assert all(action["enabled"] is False for action in card["actions"])
    assert card["authority_boundary"]["ledger_mutation_allowed"] is False
    assert card["authority_boundary"]["paid_marking_allowed"] is False
    assert packet["machine_proof"]["ledger_mutation_performed"] is False
    assert packet["machine_proof"]["paid_marking_performed"] is False


def test_review_packet_card_uses_review_decision_actions_only_no_merge_push():
    packet = _latest()
    card = _by_id(packet)["dynamic_card.build.review_packet.current"]
    actions = card["actions"]

    assert card["card_type"] == "review_packet"
    assert actions
    assert {action["action_type"] for action in actions} == {"review_decision"}
    assert {action["label"] for action in actions} == {
        "Approve for record",
        "Request rework",
        "Mark informational",
    }
    assert card["authority_boundary"]["email_send_allowed"] is False
    assert packet["machine_proof"]["merge_performed"] is False
    assert packet["machine_proof"]["git_push_performed"] is False


def test_business_development_card_has_stage_followup_no_send():
    packet = _latest()
    card = _by_id(packet)["dynamic_card.business_development.capital_hilton.proposal"]

    assert card["speaker_ref"] == "cassandra"
    assert card["headline"] == "Proposal follow-up is review-only"
    assert "do not send" in card["plain_summary"].lower()
    assert card["actions"][0]["action_id"] == "capital_hilton.proposal.stage_followup"
    assert card["actions"][0]["action_type"] == "stage_package_request"
    assert card["actions"][0]["business_action"] is False
    assert card["authority_boundary"]["email_send_allowed"] is False
    assert packet["machine_proof"]["email_send_performed"] is False


def test_check_engine_card_has_explain_or_open_only_no_repair():
    packet = _latest()
    card = _by_id(packet)["dynamic_card.system.check_engine.diagnostic"]

    assert card["headline"] == "Chief diagnostic only"
    assert {action["action_type"] for action in card["actions"]} <= {"navigate", "system_question"}
    assert all("repair" not in action["label"].lower() for action in card["actions"])
    assert all(action["business_action"] is False for action in card["actions"])
    assert packet["machine_proof"]["repair_performed"] is False


def test_workbook_registration_card_does_not_read_workbook_body():
    packet = _latest()
    card = _by_id(packet)["dynamic_card.finance.capital_hilton.workbook_registration"]

    assert card["card_type"] == "workbook_registration"
    assert card["actions"][0]["action_id"] == "client_invoice_workbook.register"
    assert card["actions"][0]["action_type"] == "workbook_registration"
    assert card["authority_boundary"]["workbook_source_mutation_allowed"] is False
    assert packet["machine_proof"]["workbook_open_performed"] is False
    assert packet["machine_proof"]["workbook_body_read_performed"] is False
    assert packet["machine_proof"]["spreadsheet_cell_read_performed"] is False
    assert packet["machine_proof"]["workbook_mutation_performed"] is False


def test_st_annes_test_only_items_are_not_primary_active_blockers():
    packet = _latest()
    card = _by_id(packet)["dynamic_card.finance.st_annes.work_log_review"]

    assert card["headline"] == "St. Anne's work-log review"
    assert card["visible_by_default"] is False
    assert card["status_label"] == "No active blocker"
    assert card["actions"] == []


def test_every_visible_card_has_trust_state():
    packet = _latest()

    assert all(
        card["trust_state"] in cards.TRUST_STATES
        for card in packet["cards"]
        if card["visible_by_default"] is True
    )
    assert packet["machine_proof"]["all_visible_cards_have_trust_state"] is True


def test_every_enabled_action_references_deterministic_payload():
    packet = _latest()
    action_index = cards._action_index(cards._source_payloads()["operator_action_payloads"])
    validation = cards.validate_packet(packet, action_index)

    assert validation["valid"] is True
    assert validation["enabled_actions_reference_deterministic_payloads"] is True
    for _card, action in _enabled_actions(packet):
        assert action["action_id"] in action_index
        assert action["payload_ref"].startswith(
            "generated/read_models/operator_action_payloads.json#action_payloads."
        )


def test_unsafe_true_grant_scan_clean():
    packet = _latest()
    contract = cards.build_contract_read_model(generated_at=FIXED_NOW)

    assert cards.unsafe_true_grants(packet) == []
    assert cards.unsafe_true_grants(contract) == []
    assert packet["machine_proof"]["unsafe_true_grants_absent"] is True
    assert contract["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_writes_json_local_bridge_and_wiki(tmp_path):
    result = cards.export_dynamic_card_packet(
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Dynamic Card Packet.md",
        generated_at=FIXED_NOW,
    )

    contract = json.loads(Path(result["contract_read_model_path"]).read_text(encoding="utf-8"))
    latest = json.loads(Path(result["latest_read_model_path"]).read_text(encoding="utf-8"))
    bridge_contract = json.loads(Path(result["bridge_contract_read_model_path"]).read_text(encoding="utf-8"))
    bridge_latest = json.loads(Path(result["bridge_latest_read_model_path"]).read_text(encoding="utf-8"))

    assert contract == bridge_contract
    assert latest == bridge_latest
    assert contract["status"] == "DYNAMIC_CARD_PACKET_READY"
    assert latest["status"] == "DYNAMIC_CARD_PACKET_READY"
    assert latest["schema_version"] == "dynamic_card_packet_v1"
    assert latest["card_count"] >= 7
    assert Path(result["wiki_path"]).exists()
