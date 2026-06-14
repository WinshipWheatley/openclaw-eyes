import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import universal_receipt_envelope as envelope


FIXED_NOW = "2026-06-05T17:00:00+00:00"


def _receipt(receipt_type, **overrides):
    params = {
        "created_at": FIXED_NOW,
        "source_request_id": f"test:{receipt_type}",
        "world_ref": "finance",
        "thread_ref": "capital_hilton",
        "workflow_ref": "test_workflow",
        "actor_ref": "guardian",
        "agent_character": "Guardian",
        "action_taken": "Test receipt recorded.",
        "action_not_taken": ["No business execution."],
        "authority_requested": [],
        "proof_refs": ["generated/read_models/universal_receipt_envelope_status.json"],
        "result_status": "recorded",
        "next_safe_action": "Keep the receipt as proof metadata only.",
    }
    params.update(overrides)
    return envelope.build_receipt(receipt_type, **params)


def test_evidence_intake_receipt_records_ledger_and_paid_false():
    receipt = _receipt(
        "evidence_recorded",
        source_request_id="evidence:test:live_arts_md",
        thread_ref="live_arts_md",
        client_ref="live_arts_md",
        action_taken="Payment-processing evidence candidate recorded.",
        action_not_taken=["No ledger mutation.", "No paid marking."],
        authority_requested=["record_evidence_candidate", "mark_paid", "ledger_post"],
        incoming_authority_granted=["mark_paid"],
        sqlite_refs=["generated/system_knowledge/evidence_intake.sqlite"],
        read_model_refs=["generated/read_models/evidence_intake_status.json"],
        result_status="evidence_recorded",
    )

    assert receipt["paid_marking_performed"] is False
    assert receipt["ledger_mutation_performed"] is False
    assert receipt["business_action_performed"] is False
    assert receipt["authority_granted"] == []
    assert "mark_paid" in receipt["authority_denied"]
    assert receipt["machine_proof"]["incoming_authority_granted_accepted"] is False
    assert receipt["machine_proof"]["evidence_is_paid_truth"] is False
    assert receipt["validation"]["valid"] is True


def test_review_decision_receipt_records_no_merge_or_push():
    receipt = _receipt(
        "review_decision_recorded",
        world_ref="build",
        thread_ref="workroom_review",
        package_id="review_packet:test",
        actor_ref="chief",
        agent_character="Chief",
        action_taken="Review decision recorded.",
        action_not_taken=["No merge.", "No git push.", "No worker spawn."],
        authority_requested=["record_review_decision", "merge_code", "git_push"],
        result_status="decision_recorded",
    )

    assert receipt["merge_performed"] is False
    assert receipt["git_push_performed"] is False
    assert receipt["worker_spawn_performed"] is False
    assert "merge_code" in receipt["authority_denied"]
    assert "git_push" in receipt["authority_denied"]
    assert receipt["validation"]["valid"] is True


def test_approval_receipt_does_not_imply_execution():
    receipt = _receipt(
        "approval_recorded",
        action_taken="Approval need recorded.",
        action_not_taken=["No Coupa submit.", "No portal access.", "No execution."],
        authority_requested=["coupa_submit"],
        sqlite_refs=["generated/system_knowledge/approval_request_queue.sqlite"],
        read_model_refs=["generated/read_models/approval_request_queue.json"],
        result_status="approval_recorded_not_executed",
    )

    assert receipt["coupa_submit_performed"] is False
    assert receipt["business_action_performed"] is False
    assert receipt["authority_granted"] == []
    assert receipt["machine_proof"]["approval_is_execution_proof"] is False
    assert receipt["validation"]["valid"] is True


def test_dynamic_card_emitted_receipt_references_card_hash():
    receipt = _receipt(
        "dynamic_card_emitted",
        card_id="dynamic_card.finance.capital_hilton.payment_watch",
        action_taken="Dynamic card emitted.",
        action_not_taken=["No source truth changed."],
        hash_refs=["sha256:test-card-content-hash"],
        read_model_refs=["generated/read_models/dynamic_card_packet_latest.json"],
        result_status="card_emitted",
    )

    assert receipt["card_id"] == "dynamic_card.finance.capital_hilton.payment_watch"
    assert receipt["hash_refs"] == ["sha256:test-card-content-hash"]
    assert receipt["business_action_performed"] is False
    assert receipt["validation"]["valid"] is True


def test_unknown_receipt_type_rejected():
    try:
        _receipt("unknown_receipt_type")
    except ValueError as exc:
        assert "unknown receipt type" in str(exc)
    else:
        raise AssertionError("unknown receipt type should fail closed")


def test_unsafe_true_grant_scan_clean(tmp_path):
    status = envelope.build_status_read_model(
        sqlite_path=tmp_path / "universal_receipts.sqlite",
        generated_at=FIXED_NOW,
    )

    assert envelope.unsafe_true_grants(status) == []
    assert status["machine_proof"]["unsafe_true_grants_absent"] is True
    for receipt in status["receipts"]:
        assert envelope.unsafe_true_grants(receipt) == []
        assert receipt["validation"]["valid"] is True


def test_sqlite_row_count_matches_status(tmp_path):
    sqlite_path = tmp_path / "universal_receipts.sqlite"
    status = envelope.build_status_read_model(
        sqlite_path=sqlite_path,
        generated_at=FIXED_NOW,
    )
    conn = sqlite3.connect(sqlite_path)
    try:
        row_count = conn.execute("SELECT COUNT(*) FROM universal_receipts").fetchone()[0]
    finally:
        conn.close()

    assert row_count == status["receipt_count"]
    assert status["sqlite_row_count"] == status["receipt_count"]
    assert status["machine_proof"]["sqlite_row_count_matches_status"] is True
