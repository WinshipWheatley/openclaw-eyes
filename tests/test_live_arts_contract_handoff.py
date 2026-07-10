from __future__ import annotations

import sqlite3

import pytest

import workflow_package_queue as queue
import workflow_package_request_consumer as consumer


PHRASINGS = (
    "Can you please hand the Live Arts PA rental invoice to Cassandra so she can get it out the door?",
    "The Live Arts PA rental invoice needs to be handled. Which agent are you routing it to, and can you stage that handoff now?",
    "the PA rental invoice for Live Arts needs to go out — get it to the right agent",
    "The Live Arts PA rental invoice needs to be sent out—can you route it to whoever should handle it?",
)


@pytest.mark.parametrize("text", PHRASINGS)
def test_live_arts_phrasings_classify_to_supported_workflow(text):
    intent = queue.classify_intent(text)
    assert intent["workflow_ref"] == "live_arts_md_invoice_workflow"
    assert intent["world"] == "invoice_operations"
    assert intent["client_ref"] == "live_arts_md"
    assert "live_arts_md_invoice_workflow" in queue.SUPPORTED_PACKAGE_TYPES


def test_live_arts_workflow_targets_existing_finance_thread():
    assert consumer.THREAD_TARGETS_BY_WORKFLOW_REF["live_arts_md_invoice_workflow"] == (
        "finance",
        "live_arts_md",
    )
    assert consumer.target_lane_for_workflow("live_arts_md_invoice_workflow") == (
        "finance",
        "live_arts_md",
    )


def test_stage_live_arts_handoff_persists_unclaimed_dry_run_and_receipt(tmp_path):
    sqlite_path = tmp_path / "workflow_package_queue.sqlite"
    result = queue.stage_live_arts_invoice_handoff(
        PHRASINGS[0],
        source_surface="operator_maestro_chat",
        sqlite_path=sqlite_path,
        created_at="2026-07-10T02:15:00+00:00",
    )
    package = result["package"]
    receipt = result["receipt"]

    assert package["workflow_ref"] == "live_arts_md_invoice_workflow"
    assert package["client_ref"] == "live_arts_md"
    assert package["status"] == "OPERATOR_REVIEW_REQUIRED"
    assert package["worker_assignment"]["assigned"] is False
    assert package["worker_assignment"]["live_action_authority"] is False
    assert package["worker_result"]["live_worker_executed"] is False
    assert package["worker_result"]["email_send_performed"] is False
    assert package["worker_result"]["ledger_mutation_performed"] is False
    assert package["worker_result"]["workbook_mutation_performed"] is False
    assert package["worker_result"]["pdf_export_performed"] is False
    assert package["operator_review_receipt"]["business_action_authority_granted"] is False
    assert package["business_action_gate_result"]["email_send_allowed"] is False
    assert package["business_action_gate_result"]["ledger_posting_allowed"] is False
    assert package["authority_boundary"]["email_send_allowed"] is False
    assert package["authority_boundary"]["ledger_posting_allowed"] is False
    assert receipt["receipt_ref"] == package["operator_review_receipt"]["receipt_ref"]
    assert receipt["target_agent"] == "cassandra"
    assert receipt["worker_claimed"] is False
    assert receipt["send_performed"] is False
    assert receipt["ledger_mutation_performed"] is False

    with sqlite3.connect(sqlite_path) as conn:
        package_row = conn.execute(
            "select workflow_ref, client_ref, status from packages where package_id = ?",
            (package["package_id"],),
        ).fetchone()
        assignment_row = conn.execute(
            "select worker_ref, assigned, live_action_authority from worker_assignments where package_id = ?",
            (package["package_id"],),
        ).fetchone()
        review_row = conn.execute(
            "select receipt_ref, operator_review_required, business_action_authority_granted "
            "from operator_review_receipts where package_id = ?",
            (package["package_id"],),
        ).fetchone()
        raw_text_stored = conn.execute(
            "select raw_text_stored from package_inputs where package_id = ?",
            (package["package_id"],),
        ).fetchone()[0]

    assert package_row == ("live_arts_md_invoice_workflow", "live_arts_md", "OPERATOR_REVIEW_REQUIRED")
    assert assignment_row == ("cassandra_invoice_lane", 0, 0)
    assert review_row == (receipt["receipt_ref"], 1, 0)
    assert raw_text_stored == 0


def test_live_arts_operator_copy_names_cassandra_but_not_claim_or_send(tmp_path):
    result = queue.stage_live_arts_invoice_handoff(
        PHRASINGS[1],
        sqlite_path=tmp_path / "queue.sqlite",
        created_at="2026-07-10T02:16:00+00:00",
    )
    reply = queue.render_live_arts_handoff_reply(result)
    assert "Cassandra" in reply
    assert "dry-run" in reply
    assert result["receipt"]["receipt_ref"] in reply
    assert "has not claimed" in reply
    assert "Nothing was sent" in reply
    assert "is preparing" not in reply
    assert "is handling" not in reply


@pytest.mark.parametrize(
    "near_miss",
    (
        "Should I send the Live Arts invoice?",
        "What is Live Arts' invoice balance?",
        "Can you get me the Live Arts invoice balance?",
        "Review my Live Arts rates.",
        "Cassandra sent the Live Arts invoice yesterday.",
    ),
)
def test_live_arts_advisory_and_nonhandoff_near_misses_do_not_stage(near_miss):
    assert queue.classify_intent(near_miss)["workflow_ref"] != "live_arts_md_invoice_workflow"


@pytest.mark.parametrize(
    ("text", "workflow_ref", "worker_ref"),
    (
        (PHRASINGS[0], "live_arts_md_invoice_workflow", "cassandra_invoice_lane"),
        (
            "who owes me money right now, and draft the nudge for whichever one's biggest?",
            "cassandra_receivables_nudge_handoff",
            "cassandra_receivables_lane",
        ),
    ),
)
def test_direct_create_package_never_preassigns_bounded_handoff(text, workflow_ref, worker_ref):
    package = queue.create_package(text, created_at="2026-07-10T02:17:00+00:00")
    assert package["workflow_ref"] == workflow_ref
    assert package["worker_assignment"] == {
        "assignment_ref": package["worker_assignment"]["assignment_ref"],
        "worker_ref": worker_ref,
        "worker_kind": "bounded_handoff_target",
        "assigned": False,
        "live_action_authority": False,
    }
    assert package["worker_result"]["live_worker_executed"] is False
    assert package["worker_result"]["email_send_performed"] is False
    assert package["worker_result"]["ledger_mutation_performed"] is False
