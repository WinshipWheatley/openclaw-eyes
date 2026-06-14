import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import dynamic_card_packet as cards


FIXED_NOW = "2026-06-05T13:45:00+00:00"


def _latest():
    return cards.build_latest_packet(generated_at=FIXED_NOW)


def _by_id(packet):
    return {card["card_id"]: card for card in packet["cards"]}


def _enabled_slots(card):
    return [
        slot
        for slot in card["action_slots"].values()
        if slot["enabled"] is True
    ]


def test_v1_packet_validates():
    packet = _latest()
    action_index = cards._action_index(cards._source_payloads()["operator_action_payloads"])
    validation = cards.validate_packet(packet, action_index)

    assert packet["schema_version"] == "dynamic_card_packet_v1"
    assert all(field in packet for field in cards.REQUIRED_PACKET_FIELDS)
    assert packet["status"] == "DYNAMIC_CARD_PACKET_READY"
    assert validation["valid"] is True
    assert packet["machine_proof"]["validation_errors"] == []


def test_all_cards_include_card_family_and_action_slots():
    packet = _latest()
    families = {card["card_family"] for card in packet["cards"]}

    assert families == set(cards.CARD_FAMILIES)
    for card in packet["cards"]:
        assert card["card_family"] in cards.CARD_FAMILIES
        assert set(card["action_slots"]) == set(cards.ACTION_SLOTS)
        for slot in card["action_slots"].values():
            assert all(field in slot for field in cards.REQUIRED_ACTION_SLOT_FIELDS)


def test_capital_hilton_payment_watch_has_no_enabled_coupa_or_ledger_action():
    card = _by_id(_latest())["dynamic_card.finance.capital_hilton.payment_watch"]

    assert card["card_family"] == "payment_watch_card"
    assert card["action_slots"]["primary"]["controller_event_type"] == "ask_why"
    assert card["action_slots"]["primary"]["control_scope"] == "lane"
    assert card["action_slots"]["primary"]["text_response_preferred"] is True
    assert card["action_slots"]["secondary"]["controller_event_type"] == "advance_objective"
    assert card["action_slots"]["secondary"]["control_scope"] == "lane"
    assert card["action_slots"]["secondary"]["text_response_preferred"] is True
    assert card["action_slots"]["detail"]["controller_event_type"] == "attach_proof"
    assert card["action_slots"]["detail"]["control_scope"] == "lane"
    assert card["action_slots"]["detail"]["text_response_preferred"] is True
    assert card["action_slots"]["danger_disabled"]["enabled"] is False
    assert card["authority_boundary"]["coupa_allowed"] is False
    assert card["authority_boundary"]["ledger_mutation_allowed"] is False
    for slot in _enabled_slots(card):
        text = f"{slot['action_id']} {slot['label']}".lower()
        assert "coupa" not in text
        assert "ledger" not in text


def test_capital_hilton_payment_watch_exposes_lane_level_text_controls():
    card = _by_id(_latest())["dynamic_card.finance.capital_hilton.payment_watch"]

    controls = {
        slot["controller_event_type"]: slot
        for slot in card["action_slots"].values()
        if slot["enabled"] is True
    }

    assert {"ask_why", "advance_objective", "attach_proof"} <= set(controls)
    assert controls["ask_why"]["action_id"] == "capital_hilton.payment.ask_why"
    assert controls["advance_objective"]["action_id"] == "capital_hilton.payment.advance_objective"
    assert controls["attach_proof"]["action_id"] == "capital_hilton.payment.record_proof"
    for event_type in ("ask_why", "advance_objective", "attach_proof"):
        assert controls[event_type]["control_scope"] == "lane"
        assert controls[event_type]["text_response_preferred"] is True
        assert controls[event_type]["authority_boundary"]["coupa_allowed"] is False
        assert controls[event_type]["authority_boundary"]["ledger_mutation_allowed"] is False


def test_capital_hilton_coupa_gate_ask_why_is_gate_detail_control():
    card = _by_id(_latest())["dynamic_card.finance.capital_hilton.approval_request.coupa_submit"]
    detail = card["action_slots"]["detail"]

    assert detail["controller_event_type"] == "ask_why"
    assert detail["action_id"] == "guardian_gate.coupa_submit.explain"
    assert detail["control_scope"] == "gate"
    assert detail["text_response_preferred"] is True
    assert card["visible_by_default"] is False


def test_live_arts_evidence_receipt_waiting_operator_reported_not_paid():
    packet = _latest()
    card = next(card for card in packet["cards"] if card["card_family"] == "evidence_intake_receipt_card")

    assert card["headline"] == "Payment proof received"
    assert card["trust_state"] == "operator_reported"
    assert card["lifecycle_state"] == "waiting"
    assert card["freshness_state"] == "waiting_on_external"
    assert card["authority_boundary"]["paid"] is False
    assert card["authority_boundary"]["paid_marking_allowed"] is False
    assert card["proof"]["sqlite_refs"]
    assert packet["machine_proof"]["paid_marking_performed"] is False
    assert packet["machine_proof"]["ledger_mutation_performed"] is False


def test_review_packet_uses_review_actions_only():
    card = _by_id(_latest())["dynamic_card.build.review_packet.current"]
    enabled_events = {slot["controller_event_type"] for slot in _enabled_slots(card)}

    assert card["card_family"] == "review_packet_card"
    assert enabled_events == {"approve", "request_rework", "mark_informational"}
    assert {action["action_type"] for action in card["actions"]} == {"review_decision"}
    assert card["authority_boundary"]["merge_allowed"] is False
    assert card["authority_boundary"]["git_push_allowed"] is False


def test_business_development_followup_has_no_send():
    packet = _latest()
    card = _by_id(packet)["dynamic_card.business_development.capital_hilton.proposal"]

    assert card["card_family"] == "workflow_composer_plan_card"
    assert card["action_slots"]["primary"]["action_id"] == "capital_hilton.proposal.stage_followup"
    assert card["action_slots"]["primary"]["controller_event_type"] == "do_it"
    assert card["action_slots"]["danger_disabled"]["enabled"] is False
    assert card["authority_boundary"]["email_send_allowed"] is False
    assert packet["machine_proof"]["email_send_performed"] is False


def test_proof_object_categorizes_refs():
    packet = _latest()
    payment = _by_id(packet)["dynamic_card.finance.capital_hilton.payment_watch"]
    evidence = next(card for card in packet["cards"] if card["card_family"] == "evidence_intake_receipt_card")

    for card in packet["cards"]:
        proof = card["proof"]
        assert all(field in proof for field in cards.REQUIRED_PROOF_FIELDS)
        assert isinstance(proof["receipt_refs"], list)
        assert isinstance(proof["artifact_refs"], list)
        assert isinstance(proof["hash_refs"], list)
        assert isinstance(proof["sqlite_refs"], list)
        assert isinstance(proof["read_model_refs"], list)
    assert payment["proof"]["receipt_refs"]
    assert payment["proof"]["read_model_refs"]
    assert evidence["proof"]["artifact_refs"]
    assert evidence["proof"]["sqlite_refs"]


def test_lifecycle_fields_present_on_every_card():
    packet = _latest()

    for card in packet["cards"]:
        assert all(field in card for field in cards.REQUIRED_CARD_FIELDS)
        assert card["lifecycle_state"] in cards.lifecycle_policy.LIFECYCLE_STATES
        assert card["freshness_state"] in cards.lifecycle_policy.FRESHNESS_STATES
        if card["visible_by_default"] is True:
            assert card["trust_state"] in cards.TRUST_STATES
            assert card["lifecycle_state"] != "archived"


def test_unsafe_true_grant_scan_clean():
    packet = _latest()
    contract = cards.build_contract_read_model(generated_at=FIXED_NOW)

    assert cards.unsafe_true_grants(packet) == []
    assert cards.unsafe_true_grants(contract) == []
    assert packet["machine_proof"]["unsafe_true_grants_absent"] is True
    assert contract["machine_proof"]["unsafe_true_grants_absent"] is True
    for card in packet["cards"]:
        for slot in card["action_slots"].values():
            assert all(value is False for value in slot["authority_boundary"].values())
