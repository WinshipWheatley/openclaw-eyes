import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import operator_session_timeline as timeline


FIXED_NOW = "2026-06-05T20:00:00+00:00"


def _read_model(tmp_path):
    return timeline.build_read_model(
        sqlite_path=tmp_path / "operator_session_timeline.sqlite",
        generated_at=FIXED_NOW,
    )


def _events(read_model, event_type=None):
    events = read_model["timeline_events"]
    if event_type is None:
        return events
    return [event for event in events if event["timeline_event_type"] == event_type]


def test_live_arts_evidence_intake_appears_as_timeline_event(tmp_path):
    read_model = _read_model(tmp_path)
    evidence_events = _events(read_model, "evidence_recorded")

    assert any(event["world_ref"] == "finance" and event["thread_ref"] == "live_arts_md" for event in evidence_events)
    event = next(event for event in evidence_events if event["thread_ref"] == "live_arts_md")
    assert event["card_id"] == "dynamic_card.finance.live_arts_md.evidence_intake.payment_processing"
    assert event["controller_event_type"] == "attach_proof"
    assert "paid and ledger truth were not inferred" in event["human_summary"]
    assert event["privacy_class"] == "protected_reference"


def test_workroom_informational_review_appears_as_timeline_event(tmp_path):
    read_model = _read_model(tmp_path)
    review_events = _events(read_model, "review_decision_recorded")

    assert any(event["world_ref"] == "build" and event["thread_ref"] == "workroom_review" for event in review_events)
    event = next(event for event in review_events if event["thread_ref"] == "workroom_review")
    assert event["card_id"] == "dynamic_card.build.review_packet.completed_historical_receipt"
    assert "marked informational" in event["human_summary"]
    assert "merge or push" in event["human_summary"]


def test_finance_capital_hilton_ask_why_is_lane_aware(tmp_path):
    read_model = _read_model(tmp_path)
    controller_events = _events(read_model, "controller_event")

    event = next(
        event
        for event in controller_events
        if event["world_ref"] == "finance"
        and event["thread_ref"] == "capital_hilton"
        and event["controller_event_type"] == "ask_why"
    )
    assert "payment-watch context" in event["human_summary"]
    assert event["receipt_ref"]
    assert "generated/read_models/operator_controller_event_router_status.json" in event["hidden_machine_refs"]


def test_raw_prompt_body_not_stored(tmp_path):
    read_model = _read_model(tmp_path)
    serialized = json.dumps(read_model["timeline_events"], sort_keys=True)

    forbidden_terms = [
        "operator_message",
        "operator_text",
        "source_text",
        "raw_chat_dump",
        "raw_prompt_body",
        "Follow up on the Capital Hilton proposal.",
    ]
    assert all(term not in serialized for term in forbidden_terms)
    assert all(not timeline._contains_forbidden_raw_key(event) for event in read_model["timeline_events"])


def test_ledger_and_paid_state_not_inferred(tmp_path):
    read_model = _read_model(tmp_path)
    proof = read_model["machine_proof"]

    assert proof["timeline_creates_business_truth"] is False
    assert proof["paid_truth_inferred"] is False
    assert proof["ledger_truth_inferred"] is False
    assert proof["paid_marking_performed"] is False
    assert proof["ledger_mutation_performed"] is False
    assert all(value is False for value in read_model["authority_boundary"].values())


def test_sqlite_row_count_matches_json(tmp_path):
    sqlite_path = tmp_path / "operator_session_timeline.sqlite"
    read_model = timeline.build_read_model(sqlite_path=sqlite_path, generated_at=FIXED_NOW)
    conn = sqlite3.connect(sqlite_path)
    try:
        row_count = conn.execute("SELECT COUNT(*) FROM operator_session_timeline").fetchone()[0]
    finally:
        conn.close()

    assert row_count == read_model["event_count"]
    assert read_model["sqlite_row_count"] == read_model["event_count"]
    assert read_model["machine_proof"]["sqlite_row_count_matches_json"] is True


def test_unsafe_scan_clean(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["status"] == timeline.READY_STATUS
    assert read_model["machine_proof"]["validation_errors"] == []
    assert timeline.unsafe_true_grants(read_model) == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True
