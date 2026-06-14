import json
import sqlite3
from pathlib import Path

import chief_session_manager
from compose_contract import GateState
from gig_intake import (
    booking_text_from_fixture,
    confirm_gig_intake_slots,
    emit_gig_handoff_packets,
    extract_gig_slots,
    start_gig_intake_session,
)
from intent_router import route_operator_intent
from scripts.land_reynolds_gig import land_reynolds_gig


FIXTURE = {
    "record_type": "gig_intake",
    "source": "forwarded text message from Mike Heuer, pasted by Winship 2026-06-13",
    "status": "facts_captured_two_defaults_pending_confirm",
    "gig": {
        "performer_covering_for": "Mike Heuer",
        "venue_name": "Reynolds Tavern",
        "venue_address": "7 Church Circle, Annapolis, MD",
        "date": "2026-06-27",
        "start_time": "19:00",
        "end_time": "22:00",
        "fee_amount": "250.00",
        "currency": "USD",
    },
    "contact": {
        "name": "Sally",
        "role": "owner",
        "email": "reservations@reynoldstavern.com",
        "note": "Sally has Winship's phone number.",
    },
    "open_slots_for_cassandra_to_ask": ["invoice_business_identity", "payment_terms"],
}


def _db(tmp_path: Path) -> str:
    return str(tmp_path / "gig_intake.sqlite")


def test_reynolds_booking_text_classifies_as_gig_intake(tmp_path):
    text = booking_text_from_fixture(FIXTURE)

    result = route_operator_intent(
        text=text,
        source_kind="mission_control",
        source_channel="gig_intake_test",
        requested_by="winship",
        db_path=_db(tmp_path),
    )

    assert result.intent_category == "gig_intake"
    assert result.routed_agent_id == "cassandra"
    assert result.candidate_action_type is None
    assert result.approval_required is False
    assert result.execution_allowed is False
    assert result.action_request_created is False


def test_reynolds_slot_fill_asks_only_invoice_identity_and_terms():
    text = booking_text_from_fixture(FIXTURE)

    state = extract_gig_slots(text, fixture=FIXTURE)
    payload = state.to_dict()
    fields = payload["fields"]

    assert fields["venue_name"] == "Reynolds Tavern"
    assert fields["venue_address"] == "7 Church Circle, Annapolis, MD"
    assert fields["date"] == "2026-06-27"
    assert fields["start_time"] == "19:00"
    assert fields["end_time"] == "22:00"
    assert fields["fee_amount"] == "250.00"
    assert fields["currency"] == "USD"
    assert fields["contact_email"] == "reservations@reynoldstavern.com"
    assert fields["contact_name"] == "Sally"
    assert fields["covering_for"] == "Mike Heuer"
    assert payload["slots_to_ask"] == ["invoice_business_identity", "payment_terms"]
    assert payload["confirmation_slots"] == ["fee_amount", "contact_email"]

    question = payload["follow_up_question"].lower()
    assert "name should go on the invoice" in question
    assert "due upon receipt" in question
    assert "what is the address" not in question
    assert "what is the fee" not in question
    assert "what is the contact email" not in question


def test_gig_intake_uses_chief_session_manager_without_sending(tmp_path, monkeypatch):
    session_path = tmp_path / "chief_session.json"
    monkeypatch.setattr(chief_session_manager, "SESSION_FILE", session_path)

    state = start_gig_intake_session(booking_text_from_fixture(FIXTURE), fixture=FIXTURE)
    session = chief_session_manager.load_session()

    assert state.status == "needs_confirmation"
    assert session["active_workflow"] == "gig_intake"
    assert session["active_mode"] == "slot_fill"
    assert session["fields"]["venue_name"] == "Reynolds Tavern"
    assert session["workflow_state"]["slots_to_ask"] == ["invoice_business_identity", "payment_terms"]
    assert session["workflow_state"]["no_send_performed"] is True
    assert session["workflow_state"]["no_invoice_sent"] is True
    assert "due upon receipt" in session["last_question"]


def test_confirmed_reynolds_gig_emits_intro_and_invoice_pending_packets(tmp_path):
    state = start_gig_intake_session(booking_text_from_fixture(FIXTURE), fixture=FIXTURE, persist_session=False)
    confirmed = confirm_gig_intake_slots(
        state,
        invoice_business_identity="Winship Wheatley",
        payment_terms="due upon receipt",
    )

    handoff = emit_gig_handoff_packets(confirmed, db_path=_db(tmp_path), source_channel="gig_intake_test")

    assert handoff["status"] == "packets_pending_approval"
    assert handoff["email_send_performed"] is False
    assert handoff["invoice_send_performed"] is False
    assert handoff["external_send_performed"] is False
    assert handoff["ledger_record"]["recorded"] is True
    packets = handoff["deliverable_packets"]
    assert [packet["deliverable_type"] for packet in packets] == ["intro_email", "invoice_send"]
    assert [packet["intent"] for packet in packets] == ["email_send", "invoice_send"]
    assert [packet["gate_state"] for packet in packets] == [GateState.PENDING_APPROVAL.value, GateState.PENDING_APPROVAL.value]
    assert all(packet["pending_approval"]["preview"]["execution_allowed"] is False for packet in packets)
    assert all("Nothing has been sent yet." in packet["segments"] for packet in packets)

    conn = sqlite3.connect(_db(tmp_path))
    try:
        rows = conn.execute(
            "SELECT intent_category, candidate_action_type, approval_required, execution_allowed, action_created "
            "FROM agent_work_packets ORDER BY created_at, packet_id"
        ).fetchall()
        assert sorted((row[0], row[1], row[2], row[3], row[4]) for row in rows) == [
            ("email_send", "email_send", 1, 0, 0),
            ("invoice_send", "invoice_send", 1, 0, 0),
        ]
        events = conn.execute(
            "SELECT event_type, operator_visible_summary FROM events WHERE event_type = 'gig_intake_recorded'"
        ).fetchall()
        assert len(events) == 1
        assert "draft sends remain approval-gated" in events[0][1]
        facts = conn.execute(
            "SELECT fact_text, source_file, source_commit, truth_status, verification_required "
            "FROM canonical_facts WHERE doc_category = 'gig_intake'"
        ).fetchall()
        assert len(facts) == 1
        fact_text, source_file, source_commit, truth_status, verification_required = facts[0]
        assert "Reynolds Tavern gig on 2026-06-27" in fact_text
        assert "no send performed" in fact_text
        assert "@" not in fact_text
        assert source_file == "operator_provided_gig_intake"
        assert source_commit == "operator_provided_unversioned"
        assert truth_status == "operator_reported_candidate"
        assert verification_required == 1
    finally:
        conn.close()


def test_land_reynolds_gig_script_is_idempotent_and_no_send(tmp_path):
    fixture_path = tmp_path / "gig_facts.json"
    fixture_path.write_text(json.dumps(FIXTURE, indent=2), encoding="utf-8")
    db_path = _db(tmp_path)

    first = land_reynolds_gig(fixture_path=fixture_path, db_path=db_path, source_commit="test_commit")
    second = land_reynolds_gig(fixture_path=fixture_path, db_path=db_path, source_commit="test_commit")

    assert first["status"] == "recorded"
    assert first["ledger_record"]["canonical_fact_recorded"] is True
    assert first["email_send_performed"] is False
    assert first["invoice_send_performed"] is False
    assert first["external_send_performed"] is False
    assert second["status"] == "already_recorded"
    assert second["after_counts"] == first["after_counts"]

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM events WHERE event_type = 'gig_intake_recorded'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM canonical_facts WHERE doc_category = 'gig_intake'").fetchone()[0] == 1
        packets = conn.execute(
            "SELECT intent_category, execution_allowed, action_created FROM agent_work_packets ORDER BY intent_category"
        ).fetchall()
        assert sorted((row[0], row[1], row[2]) for row in packets) == [
            ("email_send", 0, 0),
            ("invoice_send", 0, 0),
        ]
    finally:
        conn.close()


def test_handoff_payload_is_json_safe(tmp_path):
    state = extract_gig_slots(booking_text_from_fixture(FIXTURE), fixture=FIXTURE)
    confirmed = confirm_gig_intake_slots(
        state,
        invoice_business_identity="Winship Wheatley",
        payment_terms="due upon receipt",
    )

    payload = emit_gig_handoff_packets(confirmed, db_path=_db(tmp_path), source_channel="gig_intake_json_test")

    json.dumps(payload, sort_keys=True)
