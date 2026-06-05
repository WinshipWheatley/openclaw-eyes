import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import approval_request_queue
import client_invoice_workbook_registry as workbook_registry
import dynamic_card_packet
import evidence_intake
import gate_decision_ledger
import memory_promotion_gate
import system_question_answer
import workflow_composer
import workflow_package_queue
import workflow_package_request_consumer
import workroom_review_decision_consumer


FIXED_NOW = "2026-06-05T16:00:00+00:00"


def _workflow_package_receipt(tmp_path):
    source_text = "Follow up on the Capital Hilton proposal."
    request = {
        "request_id": "dynamic_card_v1_rail_population_workflow_package",
        "request_type": workflow_package_request_consumer.REQUEST_TYPE,
        "kind": workflow_package_request_consumer.REQUEST_KIND,
        "source_surface": "mission_control",
        "requested_mode": "operator",
        "result_receipt_required": True,
        "world_ref": "business_development",
        "thread_ref": "capital_hilton",
        "source_text": source_text,
        "operator_message": source_text,
        "protected_text_hash": workflow_package_queue.protected_text_hash(source_text),
        "authority_boundary": {key: False for key in workflow_package_request_consumer.AUTHORITY_FALSE_FIELDS},
        "created_at": FIXED_NOW,
    }
    result = workflow_package_request_consumer.consume_workflow_package_request(
        request,
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "workflow_package_queue.sqlite",
    )
    return result.receipt


def _rail_payloads(tmp_path):
    return {
        "system_question_answer": system_question_answer.build_contract_read_model(generated_at=FIXED_NOW),
        "workflow_package_request_consumer": _workflow_package_receipt(tmp_path),
        "workroom_review_decision_consumer": workroom_review_decision_consumer.build_read_model(
            generated_at=FIXED_NOW,
            export_root=tmp_path / "workroom",
        ),
        "evidence_intake": evidence_intake.build_status_read_model(
            generated_at=FIXED_NOW,
            sqlite_path=tmp_path / "evidence_intake.sqlite",
            artifact_lineage_sqlite_path=tmp_path / "artifact_lineage.sqlite",
        ),
        "workbook_registration": workbook_registry.register_workbook_request(
            workbook_registry.make_capital_hilton_fixture_request(created_at=FIXED_NOW),
            export_root=tmp_path / "workbooks",
            generated_at=FIXED_NOW,
        ),
        "approval_request_queue": approval_request_queue.build_read_model(
            generated_at=FIXED_NOW,
            sqlite_path=tmp_path / "approval_request_queue.sqlite",
        ),
        "gate_decision_ledger": gate_decision_ledger.build_read_model(
            generated_at=FIXED_NOW,
            sqlite_path=tmp_path / "gate_decision_ledger.sqlite",
        ),
        "workflow_composer": workflow_composer.build_latest_read_model(generated_at=FIXED_NOW),
        "memory_promotion_gate": memory_promotion_gate.build_read_model(generated_at=FIXED_NOW),
    }


def _cards(payload):
    return payload["dynamic_card_packet_v1"]["cards"]


def _card_by_family(payload, family):
    return next(card for card in _cards(payload) if card["card_family"] == family)


def test_each_active_rail_emits_valid_v1_card_packet(tmp_path):
    for rail_ref, payload in _rail_payloads(tmp_path).items():
        packet = payload.get("dynamic_card_packet_v1")
        validation = dynamic_card_packet.validate_rail_card_packet(packet or {})

        assert packet is not None, rail_ref
        assert packet["schema_version"] == "dynamic_card_packet_v1"
        assert packet["rail_ref"] == rail_ref
        assert packet["card_count"] >= 1
        assert validation["valid"] is True, validation["errors"]
        assert payload["machine_proof"]["dynamic_card_packet_v1_emitted"] is True
        assert payload["machine_proof"]["dynamic_card_packet_v1_valid"] is True


def test_workflow_package_status_read_model_emits_valid_v1_card_packet(tmp_path):
    root = tmp_path / "read_models"
    root.mkdir()
    status_payload = {
        "schema_version": "workflow_package_request_consumer_status_v0",
        "read_model_id": workflow_package_request_consumer.STATUS_READ_MODEL_ID,
        "status": "WORKFLOW_PACKAGE_RAIL_STATUS_READY",
        "consumer_status": "READY",
        "generated_at": FIXED_NOW,
        "operator_display_schema": ["headline", "plain_summary", "next_safe_action"],
        "machine_proof": {
            "no_live_business_actions": True,
            "unsafe_true_grants_absent": True,
        },
        "authority_boundary": {key: False for key in workflow_package_request_consumer.AUTHORITY_FALSE_FIELDS},
    }
    (root / workflow_package_request_consumer.STATUS_JSON_EXPORT_NAME).write_text(
        json.dumps(status_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    enriched = workflow_package_request_consumer.build_status_read_model_from_existing(
        export_root=root,
        generated_at=FIXED_NOW,
    )
    validation = dynamic_card_packet.validate_rail_card_packet(enriched["dynamic_card_packet_v1"])

    assert enriched["operator_display_schema"] == status_payload["operator_display_schema"]
    assert enriched["dynamic_card_packet_v1"]["rail_ref"] == "workflow_package_request_consumer"
    assert enriched["dynamic_card_packet_v1"]["card_count"] >= 1
    assert validation["valid"] is True


def test_legacy_fields_remain_present(tmp_path):
    payloads = _rail_payloads(tmp_path)

    assert "examples" in payloads["system_question_answer"]
    assert "operator_display" in payloads["workflow_package_request_consumer"]
    assert "decision_history" in payloads["workroom_review_decision_consumer"]
    assert "dynamic_card" in payloads["evidence_intake"]
    assert "registration_readback" in payloads["workbook_registration"]
    assert "approval_requests" in payloads["approval_request_queue"]
    assert "decisions" in payloads["gate_decision_ledger"]
    assert "latest_plan" in payloads["workflow_composer"]
    assert "promotion_entries" in payloads["memory_promotion_gate"]


def test_required_examples_are_populated(tmp_path):
    payloads = _rail_payloads(tmp_path)

    assert _card_by_family(payloads["workflow_package_request_consumer"], "payment_watch_card")[
        "headline"
    ] == "Stay on payment watch"
    assert _card_by_family(payloads["evidence_intake"], "evidence_intake_receipt_card")[
        "headline"
    ] == "Payment proof received"
    assert _card_by_family(payloads["workroom_review_decision_consumer"], "review_packet_card")[
        "headline"
    ] == "Review packet needs local decision"
    assert _card_by_family(payloads["workflow_package_request_consumer"], "workflow_composer_plan_card")[
        "headline"
    ] == "Proposal follow-up is review-only"
    assert _card_by_family(payloads["system_question_answer"], "gate_lock_card")[
        "headline"
    ] == "Chief diagnostic only"
    assert _card_by_family(payloads["workflow_package_request_consumer"], "completed_historical_receipt_card")[
        "headline"
    ] == "St. Anne's work-log review"
    assert _card_by_family(payloads["workbook_registration"], "current_focus_card")[
        "headline"
    ] == "Workbook reference can be registered"
    assert _card_by_family(payloads["approval_request_queue"], "approval_request_card")[
        "headline"
    ] == "Coupa submit requires a protected gate"
    assert _card_by_family(payloads["memory_promotion_gate"], "memory_candidate_card")[
        "headline"
    ] == "Candidate memory stays unpromoted"
    assert _card_by_family(payloads["workflow_composer"], "workflow_composer_plan_card")[
        "headline"
    ] == "Proposal follow-up is review-only"


def test_capital_hilton_payment_watch_remains_clean(tmp_path):
    card = _card_by_family(_rail_payloads(tmp_path)["workflow_package_request_consumer"], "payment_watch_card")

    assert card["authority_boundary"]["coupa_allowed"] is False
    assert card["authority_boundary"]["ledger_mutation_allowed"] is False
    assert card["action_slots"]["danger_disabled"]["enabled"] is False
    for slot in card["action_slots"].values():
        if slot["enabled"] is True:
            assert "coupa" not in slot["label"].lower()
            assert "ledger" not in slot["label"].lower()


def test_evidence_intake_card_does_not_mark_paid(tmp_path):
    payload = _rail_payloads(tmp_path)["evidence_intake"]
    card = _card_by_family(payload, "evidence_intake_receipt_card")

    assert card["trust_state"] == "operator_reported"
    assert card["freshness_state"] == "waiting_on_external"
    assert card["lifecycle_state"] == "waiting"
    assert card["authority_boundary"]["paid"] is False
    assert card["authority_boundary"]["paid_marking_allowed"] is False
    assert payload["machine_proof"]["paid_marking_performed"] is False
    assert payload["machine_proof"]["ledger_mutation_performed"] is False


def test_review_packet_resolved_card_hidden_by_lifecycle_policy(tmp_path):
    payload = _rail_payloads(tmp_path)["workroom_review_decision_consumer"]
    card = _card_by_family(payload, "completed_historical_receipt_card")

    assert card["card_id"] == "dynamic_card.build.review_packet.completed_historical_receipt"
    assert card["lifecycle_state"] == "resolved"
    assert card["freshness_state"] == "historical"
    assert card["visible_by_default"] is False
    assert card["operator_attention_required"] is False


def test_approval_and_gate_cards_do_not_execute(tmp_path):
    payloads = _rail_payloads(tmp_path)
    for payload in (payloads["approval_request_queue"], payloads["gate_decision_ledger"]):
        for card in _cards(payload):
            assert card["authority_boundary"]["business_action_allowed"] is False
            assert card["authority_boundary"]["external_action_allowed"] is False
            assert card["action_slots"]["danger_disabled"]["enabled"] is False
    assert payloads["approval_request_queue"]["machine_proof"]["business_action_performed"] is False
    assert payloads["gate_decision_ledger"]["machine_proof"]["business_action_performed"] is False


def test_unsafe_scan_clean_for_rail_packets(tmp_path):
    for rail_ref, payload in _rail_payloads(tmp_path).items():
        assert dynamic_card_packet.unsafe_true_grants(payload) == [], rail_ref
        assert payload["dynamic_card_packet_v1"]["machine_proof"]["unsafe_true_grants_absent"] is True
