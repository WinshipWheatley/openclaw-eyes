import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import operator_controller_protocol as protocol


FIXED_NOW = "2026-06-04T21:45:00+00:00"


def _event(
    *,
    event_type: str = "show_details",
    input_surface: str = "card",
    current_world_ref: str = "finance",
    current_thread_ref: str = "live_arts_md",
    active_entity_ref: str = "dynamic_card.finance.live_arts_md.evidence_intake.payment_processing",
    authority_requested=(),
):
    return protocol.attach_verified_controller_envelope(
        {"operator_note": "Controller test event."},
        event_type=event_type,
        input_surface=input_surface,
        current_world_ref=current_world_ref,
        current_thread_ref=current_thread_ref,
        active_entity_ref=active_entity_ref,
        authority_requested=authority_requested,
        created_at=FIXED_NOW,
    )


def _assert_no_unsafe_true(payload):
    assert protocol.unsafe_true_grants(payload) == []


def test_verified_mac_controller_event_accepted():
    event = _event()

    result = protocol.validate_controller_event(event)

    assert result["event_status"] == "OPERATOR_CONTROLLER_EVENT_ACCEPTED"
    assert result["verification_status"] == "verified"
    assert result["device_class"] == "mac"
    assert result["input_surface"] == "card"
    assert result["request_hash"] == protocol.compute_request_hash(event)
    assert result["authority_granted"] == []
    assert result["machine_proof"]["lm_cannot_grant_authority"] is True
    _assert_no_unsafe_true(result)


def test_missing_device_ref_blocks():
    event = _event()
    event["operator_controller_envelope"]["device_ref"] = ""
    event["operator_controller_envelope"]["device_verified"] = False
    event["operator_controller_envelope"]["request_hash"] = protocol.compute_request_hash(event)

    result = protocol.validate_controller_event(event)

    assert result["event_status"] == "OPERATOR_CONTROLLER_EVENT_NEEDS_VERIFICATION"
    assert result["verified"] is False
    assert "device_ref_missing" in result["blockers"]
    assert "device_verified_false_or_missing" in result["blockers"]


def test_incoming_authority_granted_is_rejected_or_ignored():
    event = _event(authority_requested=["stage_plan"])
    event["authority_granted"] = ["email_send"]
    event["operator_controller_envelope"]["request_hash"] = protocol.compute_request_hash(event)

    result = protocol.validate_controller_event(event)

    assert result["event_status"] == "OPERATOR_CONTROLLER_EVENT_REJECTED"
    assert result["verification_status"] == "rejected"
    assert "incoming_backend_only_authority_fields_not_accepted" in result["rejected_reasons"]
    assert result["authority_granted"] == []
    assert result["incoming_authority_granted_accepted"] is False


def test_authority_requested_does_not_imply_authority_granted():
    event = _event(event_type="stage_plan", authority_requested=["stage_followup_draft"])

    result = protocol.validate_controller_event(event)
    record = protocol.build_controller_event_record(event, generated_at=FIXED_NOW)

    assert result["authority_requested"] == ["stage_followup_draft"]
    assert result["authority_granted"] == []
    assert record["authority_requested"] == ["stage_followup_draft"]
    assert record["authority_granted"] == []
    assert record["machine_proof"]["authority_granted_backend_only"] is True


def test_attach_proof_event_routes_to_evidence_intake_contract():
    event = _event(
        event_type="attach_proof",
        input_surface="dropzone",
        current_world_ref="finance",
        current_thread_ref="live_arts_md",
        active_entity_ref="invoice:2026-1001",
        authority_requested=["record_payment_proof_intake"],
    )

    record = protocol.build_controller_event_record(event, generated_at=FIXED_NOW)

    assert record["event_status"] == "OPERATOR_CONTROLLER_EVENT_ACCEPTED"
    assert record["route"]["contract_ref"] == "generated/read_models/evidence_intake_contract.json"
    assert record["route"]["route_ref"] == "evidence_intake.record_candidate_evidence"
    assert "record_payment_proof_intake" in record["route"]["allowed_action_payload_types"]
    assert record["route"]["payment"]["financial_sensitive"] is True
    assert record["route"]["payment"]["paid"] is False
    assert record["route"]["payment"]["ledger_mutation_performed"] is False
    assert record["route"]["dynamic_card_response"]["headline"] == "Payment proof received"


def test_build_approve_event_routes_to_review_decision_contract():
    event = _event(
        event_type="approve",
        input_surface="card",
        current_world_ref="build",
        current_thread_ref="review_packet",
        active_entity_ref="review_packet:current",
        authority_requested=["record_review_decision"],
    )

    record = protocol.build_controller_event_record(event, generated_at=FIXED_NOW)

    assert record["route"]["contract_ref"] == "generated/read_models/workroom_review_decision_contract.json"
    assert record["route"]["route_ref"] == "workroom_review_decision_consumer.record_review_decision"
    assert "review_decision" in record["route"]["allowed_action_payload_types"]
    assert "merge" in record["route"]["forbidden_action_payload_types"]
    assert "git_push" in record["route"]["forbidden_action_payload_types"]
    assert record["route"]["machine_proof"]["merge_performed"] is False
    assert record["route"]["machine_proof"]["git_push_performed"] is False


def test_business_development_followup_has_no_send_authority():
    event = _event(
        event_type="stage_plan",
        input_surface="card",
        current_world_ref="business_development",
        current_thread_ref="capital_hilton",
        active_entity_ref="capital_hilton_business_development_followup",
        authority_requested=["stage_followup_draft"],
    )

    record = protocol.build_controller_event_record(event, generated_at=FIXED_NOW)

    assert record["route"]["contract_ref"] == "generated/read_models/capital_hilton_business_development_proposal.json"
    assert record["route"]["route_label"] == "Business Development follow-up staging only"
    assert "email_send" in record["route"]["forbidden_action_payload_types"]
    assert record["authority_boundary"]["email_send_allowed"] is False
    assert record["route"]["dynamic_card_response"]["summary"] == (
        "Stage a follow-up draft or plan only. No send authority is granted."
    )


def test_finance_capital_hilton_do_it_resolves_to_payment_watch_no_coupa_browser_ledger():
    event = _event(
        event_type="do_it",
        input_surface="card",
        current_world_ref="finance",
        current_thread_ref="capital_hilton",
        active_entity_ref="dynamic_card.finance.capital_hilton.payment_watch",
        authority_requested=["do_it"],
    )

    record = protocol.build_controller_event_record(event, generated_at=FIXED_NOW)

    assert record["route"]["route_ref"] == "system_question_answer.finance.capital_hilton.payment_watch"
    assert record["route"]["dynamic_card_response"]["headline"] == "Stay on payment watch"
    assert record["authority_boundary"]["coupa_allowed"] is False
    assert record["authority_boundary"]["browser_access_allowed"] is False
    assert record["authority_boundary"]["ledger_mutation_allowed"] is False
    assert record["route"]["machine_proof"]["coupa_access_performed"] is False
    assert record["route"]["machine_proof"]["browser_access_performed"] is False
    assert record["route"]["machine_proof"]["ledger_mutation_performed"] is False


def test_guardian_approval_records_decision_only_requires_final_gate():
    event = _event(
        event_type="approve",
        input_surface="card",
        current_world_ref="governance",
        current_thread_ref="guardian",
        active_entity_ref="guardian_approval_request:send_email",
        authority_requested=["email_send"],
    )

    record = protocol.build_controller_event_record(event, generated_at=FIXED_NOW)

    assert record["route"]["route_ref"] == "approval_request_queue.record_decision_then_gate_decision_ledger"
    assert record["route"]["contract_ref"] == "generated/read_models/approval_request_queue.json"
    assert record["authority_requested"] == ["email_send"]
    assert record["authority_granted"] == []
    assert record["route"]["authority_granted"] == []
    assert record["machine_proof"]["business_action_performed"] is False


def test_export_writes_json_bridge_sqlite_and_wiki(tmp_path):
    result = protocol.export_operator_controller_protocol(
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Operator Controller Protocol.md",
        sqlite_path=tmp_path / "system_knowledge" / "operator_controller_protocol.sqlite",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))

    assert local == bridge
    assert local["status"] == "OPERATOR_CONTROLLER_PROTOCOL_READY"
    assert len(local["examples"]) == 5
    assert local["machine_proof"]["authority_requested_does_not_imply_authority_granted"] is True
    conn = sqlite3.connect(result["sqlite_path"])
    try:
        count = conn.execute("SELECT COUNT(*) FROM operator_controller_events").fetchone()[0]
        row = conn.execute(
            """
            SELECT event_type, verification_status, authority_granted_json,
                   ledger_mutation_allowed, paid_marking_allowed, business_action_allowed
            FROM operator_controller_events
            WHERE event_type='attach_proof'
            """
        ).fetchone()
    finally:
        conn.close()
    assert count == 5
    assert row[0] == "attach_proof"
    assert row[1] == "verified"
    assert json.loads(row[2]) == []
    assert row[3:] == (0, 0, 0)
    assert Path(result["wiki_path"]).exists()
    _assert_no_unsafe_true(local)


def test_no_unsafe_true_grants(tmp_path):
    event = _event(event_type="attach_proof", input_surface="dropzone", authority_requested=["record_payment_proof_intake"])
    result = protocol.validate_controller_event(event)
    record = protocol.build_controller_event_record(event, generated_at=FIXED_NOW)
    read_model = protocol.build_read_model(
        sqlite_path=tmp_path / "operator_controller_protocol.sqlite",
        generated_at=FIXED_NOW,
    )

    assert protocol.unsafe_true_grants(result) == []
    assert protocol.unsafe_true_grants(record) == []
    assert protocol.unsafe_true_grants(read_model) == []
