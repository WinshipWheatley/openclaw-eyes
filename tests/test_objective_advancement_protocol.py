import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import objective_advancement_protocol as protocol


FIXED_NOW = "2026-06-05T13:30:00+00:00"


def _assert_no_unsafe_true(payload):
    assert protocol.unsafe_true_grants(payload) == []


def _assert_dynamic_card(decision):
    card = decision["dynamic_card"]
    assert card["schema_version"] == "dynamic_card_packet_v1"
    assert card["card_type"] == "objective_advancement"
    assert card["headline"]
    assert card["plain_summary"]
    assert card["next_safe_action"]
    assert card["authority_boundary"]["email_send_allowed"] is False


def test_capital_hilton_missing_payment_evidence_returns_attach_proof_next_not_dead_disabled_state():
    decision = protocol.advance_objective(
        {
            "objective_ref": "objective:finance:capital_hilton:payment_watch",
            "current_world_ref": "finance",
            "current_thread_ref": "capital_hilton",
            "current_state": {
                "invoice_submitted": True,
                "coupa_processing": True,
                "payment_evidence_present": False,
                "paid": False,
                "ledger_touched": False,
            },
        },
        generated_at=FIXED_NOW,
    )

    assert decision["next_safe_state"] == "REQUEST_PAYMENT_EVIDENCE"
    assert decision["operator_response"] == "I can't complete payment yet. I need payment evidence first."
    assert decision["suggested_operator_action"]["label"] == "Attach proof"
    assert decision["missing_input"] == "payment_evidence"
    assert decision["blocked"] is True
    assert decision["dynamic_card"]["next_safe_action"] == "Attach proof"
    assert decision["dynamic_card"]["action_slots"][0]["label"] == "Attach proof"
    _assert_dynamic_card(decision)


def test_capital_hilton_advancement_does_not_mark_paid_or_mutate_ledger_or_open_coupa():
    decision = protocol.advance_objective(
        {
            "current_world_ref": "finance",
            "current_thread_ref": "capital_hilton",
            "current_state": {"payment_evidence_present": False},
        },
        generated_at=FIXED_NOW,
    )

    assert decision["authority_boundary"]["paid"] is False
    assert decision["authority_boundary"]["ledger_mutation_allowed"] is False
    assert decision["authority_boundary"]["ledger_posting_allowed"] is False
    assert decision["authority_boundary"]["coupa_allowed"] is False
    assert decision["authority_boundary"]["browser_access_allowed"] is False
    assert decision["machine_proof"]["paid_marking_performed"] is False
    assert decision["machine_proof"]["ledger_mutation_performed"] is False
    assert decision["machine_proof"]["coupa_access_performed"] is False
    _assert_no_unsafe_true(decision)


def test_live_arts_evidence_advancement_records_waiting_state_not_paid():
    decision = protocol.advance_objective(
        {
            "objective_ref": "objective:finance:live_arts_md:payment_evidence",
            "current_world_ref": "finance",
            "current_thread_ref": "live_arts_md",
            "current_state": {"evidence_attached": True, "paid": False},
        },
        generated_at=FIXED_NOW,
    )

    assert decision["next_safe_state"] == "EVIDENCE_RECORDED_WAITING_FOR_CONFIRMATION"
    assert decision["operator_response"] == "I recorded this as payment-processing evidence. Ledger remains untouched."
    assert decision["allowed_internal_advance"] == ["record_candidate_evidence", "prepare_confirmation_review"]
    assert decision["authority_boundary"]["paid"] is False
    assert decision["machine_proof"]["ledger_mutation_performed"] is False
    assert decision["machine_proof"]["paid_marking_performed"] is False
    _assert_dynamic_card(decision)


def test_business_development_advancement_stages_followup_no_send():
    decision = protocol.advance_objective(
        {
            "current_world_ref": "business_development",
            "current_thread_ref": "capital_hilton",
            "desired_outcome": "follow up on proposal",
        },
        generated_at=FIXED_NOW,
    )

    assert decision["next_safe_state"] == "FOLLOWUP_DRAFT_STAGED"
    assert "stage_followup_draft" in decision["allowed_internal_advance"]
    assert decision["protected_final_action"] == "email_send"
    assert decision["final_approval_required"] is True
    assert decision["authority_boundary"]["email_send_allowed"] is False
    assert decision["machine_proof"]["email_send_performed"] is False
    _assert_dynamic_card(decision)


def test_build_review_advancement_does_not_merge_or_push():
    decision = protocol.advance_objective(
        {
            "current_world_ref": "build",
            "current_thread_ref": "review_packet",
            "active_entity_ref": "review_packet:c4ec166103f9aa35",
            "requested_review_action": "mark_review_packet_informational",
        },
        generated_at=FIXED_NOW,
    )

    assert decision["next_safe_state"] == "REVIEW_DECISION_READY_TO_RECORD"
    assert "record_review_decision_receipt" in decision["allowed_internal_advance"]
    assert decision["authority_boundary"]["merge_allowed"] is False
    assert decision["authority_boundary"]["git_push_allowed"] is False
    assert decision["machine_proof"]["merge_performed"] is False
    assert decision["machine_proof"]["git_push_performed"] is False
    _assert_dynamic_card(decision)


def test_st_annes_work_log_review_surfaces_choices_without_invoice_pdf_email():
    decision = protocol.advance_objective(
        {
            "current_world_ref": "finance",
            "current_thread_ref": "st_annes",
            "active_entity_ref": "st_annes_work_log_event:pending",
        },
        generated_at=FIXED_NOW,
    )

    assert decision["next_safe_state"] == "SURFACE_WORK_LOG_REVIEW_CHOICES"
    assert decision["operator_question"] == "Confirm, discard, edit, or mark this St. Anne's work-log event as test?"
    assert decision["authority_boundary"]["pdf_export_allowed"] is False
    assert decision["authority_boundary"]["email_send_allowed"] is False
    assert decision["machine_proof"]["workbook_mutation_performed"] is False
    _assert_dynamic_card(decision)


def test_class_a_approval_never_grants_protected_actions():
    scope = protocol.class_a_approval_scope()

    assert "stage package" in scope["may_allow"]
    assert "prepare review packet" in scope["may_allow"]
    assert "email send" in scope["must_not_allow"]
    assert "ledger mutation" in scope["must_not_allow"]
    assert "worker spawn" in scope["must_not_allow"]

    decision = protocol.advance_objective(
        {
            "current_world_ref": "business_development",
            "current_thread_ref": "capital_hilton",
            "class_a_approved": True,
        },
        generated_at=FIXED_NOW,
    )
    assert decision["class_a_approval_scope"]["class_a_approval_present"] is True
    assert decision["authority_boundary"]["email_send_allowed"] is False
    assert decision["authority_boundary"]["worker_spawn_allowed"] is False
    _assert_no_unsafe_true(decision)


def test_unknown_context_fails_closed_with_needs_verification():
    decision = protocol.advance_objective(
        {"current_world_ref": "unknown", "current_thread_ref": ""},
        generated_at=FIXED_NOW,
    )

    assert decision["next_safe_state"] == "NEEDS_VERIFICATION"
    assert decision["blocked"] is True
    assert decision["operator_question"] == "Which lane or objective should I advance?"
    assert decision["allowed_internal_advance"] == ["readback", "ask_context_question"]
    assert "stage_package" not in decision["allowed_internal_advance"]
    _assert_dynamic_card(decision)
    _assert_no_unsafe_true(decision)


def test_build_protocol_accepts_mac_real_use_smoke_bridge_proof():
    read_model = protocol.build_protocol_read_model(generated_at=FIXED_NOW)
    preconditions = {item["precondition_ref"]: item for item in read_model["preconditions"]}

    assert preconditions["mac_controller_real_use_smoke"]["ready"] is True
    assert preconditions["mac_controller_real_use_smoke"]["observed_status"] == "MAC_CONTROLLER_REAL_USE_SMOKE_READY"
    assert preconditions["mac_controller_real_use_smoke"]["source_ref"] == "/mnt/e/openclaw/generated/read_models/mac_controller_real_use_smoke_status.json"


def test_export_writes_json_bridge_sqlite_and_wiki(tmp_path):
    result = protocol.export_objective_advancement_protocol(
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Objective Advancement Protocol.md",
        sqlite_path=tmp_path / "system_knowledge" / "objective_advancement_protocol.sqlite",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    assert local == bridge
    assert local["status"] == "OBJECTIVE_ADVANCEMENT_PROTOCOL_READY"
    assert len(local["examples"]) >= 6
    assert local["machine_proof"]["unsafe_true_grants_absent"] is True

    conn = sqlite3.connect(result["sqlite_path"])
    try:
        rows = conn.execute("SELECT COUNT(*) FROM objective_advancement_examples").fetchone()[0]
        assert rows == len(local["examples"])
    finally:
        conn.close()

    assert Path(result["wiki_path"]).exists()


def test_unsafe_true_grant_scan_clean_for_protocol_read_model():
    read_model = protocol.build_protocol_read_model(generated_at=FIXED_NOW)

    assert protocol.unsafe_true_grants(read_model) == []
