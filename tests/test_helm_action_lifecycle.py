import json
from pathlib import Path

import helm_action_lifecycle as lifecycle


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "generated/read_models/helm_action_lifecycle_status.json"
SURFACE_PATH = ROOT / "generated/read_models/helm_actionability_surface.json"
BRIDGE_STATUS_PATH = Path("/mnt/e/openclaw/generated/read_models/helm_action_lifecycle_status.json")
BRIDGE_SURFACE_PATH = Path("/mnt/e/openclaw/generated/read_models/helm_actionability_surface.json")


def _surface_with_st_annes_card() -> dict:
    return {
        "schema_version": "helm_actionability_surface_v0",
        "status": "HELM_ACTIONABILITY_SURFACE_READY",
        "primary_next_action": {
            "action_id": "safe_next:finance:st_annes_work_log_review",
            "label": "Open Finance / St. Anne's work-log review",
            "action_type": "navigate",
            "target_world_ref": "finance",
            "target_thread_ref": "st_annes",
            "payload_ref": "generated/read_models/st_annes_work_log_review_surface.json",
        },
        "suggested_questions": [
            {
                "question_id": "safe_next",
                "question_text": "What is safe next?",
                "precomputed_answer": {
                    "speaker_ref": "openclaw",
                    "headline": "Review St. Anne's.",
                    "plain_summary": "Open St. Anne's review.",
                    "next_safe_action": "Open Finance / St. Anne's work-log review.",
                },
                "action": {
                    "action_type": "navigate",
                    "label": "Open Finance / St. Anne's",
                    "target_world_ref": "finance",
                    "target_thread_ref": "st_annes",
                    "payload_ref": "generated/read_models/st_annes_work_log_review_surface.json",
                },
            }
        ],
        "action_cards": [
            {
                "card_id": "st_annes_smoke_work_log_event",
                "speaker_ref": "cassandra",
                "headline": "St. Anne's church sound entry is staged as smoke/test.",
                "action_label": "Mark as test",
                "action_type": "mark_test",
                "target_world_ref": "finance",
                "target_thread_ref": "st_annes",
                "payload_ref": "generated/read_models/st_annes_work_log_review_surface.json#event-1",
                "business_action": False,
            },
            {
                "card_id": "capital_hilton_payment_watch",
                "speaker_ref": "chief",
                "headline": "Capital Hilton payment watch is finance-only.",
                "action_label": "Open Finance / Capital Hilton",
                "action_type": "navigate",
                "target_world_ref": "finance",
                "target_thread_ref": "capital_hilton",
                "payload_ref": "generated/read_models/capital_hilton_invoice_operator_run_status.json",
                "business_action": False,
            },
            {
                "card_id": "capital_hilton_proposal_watch",
                "speaker_ref": "chief",
                "headline": "Capital Hilton proposal is waiting for client review.",
                "action_label": "Open Business Development / Capital Hilton",
                "action_type": "navigate",
                "target_world_ref": "business_development",
                "target_thread_ref": "capital_hilton",
                "payload_ref": "generated/read_models/capital_hilton_business_development_proposal.json",
                "business_action": False,
            },
        ],
        "history_policy": {
            "show_full_history_by_default": False,
            "proof_collapsed_by_default": True,
        },
        "authority_boundary": lifecycle.AUTHORITY_BOUNDARY.copy(),
    }


def _st_annes_review_surface(*, status: str, invoice_status: str) -> dict:
    return {
        "events": [
            {
                "event_id": "event-1",
                "staging_status": status,
                "billing_truth_status": status,
                "invoice_inclusion_status": invoice_status,
                "operator_confirmed": invoice_status == "READY_FOR_MONTHLY_ROLLUP",
                "hygiene_evidence_refs": [
                    {"path": "mission_control_request.json"},
                    {"path": "openclaw_response.json"},
                ],
            }
        ]
    }


def test_mark_as_test_event_resolves_action_card():
    result = lifecycle.apply_lifecycle(
        actionability_surface=_surface_with_st_annes_card(),
        st_annes_review_surface=_st_annes_review_surface(
            status="SMOKE_OR_TEST_EVENT",
            invoice_status="NOT_INCLUDED_SMOKE_EVENT",
        ),
    )
    card = next(card for card in result.surface["action_cards"] if card["card_id"] == "st_annes_smoke_work_log_event")

    assert card["lifecycle_status"] == "RESOLVED_TEST_EVENT"
    assert card["visible_by_default"] is False
    assert card["completed_summary"] == "St. Anne's test event cleared."
    assert result.status["resolved_action_count"] == 1


def test_confirmed_event_resolves_action_card():
    result = lifecycle.apply_lifecycle(
        actionability_surface=_surface_with_st_annes_card(),
        st_annes_review_surface=_st_annes_review_surface(
            status="OPERATOR_CONFIRMED",
            invoice_status="READY_FOR_MONTHLY_ROLLUP",
        ),
    )
    card = next(card for card in result.surface["action_cards"] if card["card_id"] == "st_annes_smoke_work_log_event")

    assert card["lifecycle_status"] == "READY_FOR_MONTHLY_ROLLUP"
    assert card["visible_by_default"] is False
    assert card["completed_summary"] == "St. Anne's event confirmed for month-end rollup."


def test_primary_next_action_advances_when_work_log_card_resolved():
    result = lifecycle.apply_lifecycle(
        actionability_surface=_surface_with_st_annes_card(),
        st_annes_review_surface=_st_annes_review_surface(
            status="SMOKE_OR_TEST_EVENT",
            invoice_status="NOT_INCLUDED_SMOKE_EVENT",
        ),
    )

    assert result.status["active_action_count"] == 2
    assert result.surface["primary_next_action"]["action_id"] == "capital_hilton_payment_watch"
    assert result.surface["primary_next_action"]["target_thread_ref"] == "capital_hilton"
    safe_next = next(item for item in result.surface.get("suggested_questions", []) if item["question_text"] == "What is safe next?")
    assert safe_next["action"]["target_thread_ref"] == "capital_hilton"


def test_evidence_is_preserved_and_proof_collapsed():
    result = lifecycle.apply_lifecycle(
        actionability_surface=_surface_with_st_annes_card(),
        st_annes_review_surface=_st_annes_review_surface(
            status="SMOKE_OR_TEST_EVENT",
            invoice_status="NOT_INCLUDED_SMOKE_EVENT",
        ),
    )
    resolved = result.status["resolved_actions"][0]

    assert resolved["evidence_preserved"] is True
    assert resolved["proof_refs"]
    assert result.surface["history_policy"]["proof_collapsed_by_default"] is True
    assert result.status["machine_proof"]["proof_collapsed_by_default"] is True


def test_no_unsafe_true_grants():
    result = lifecycle.apply_lifecycle(
        actionability_surface=_surface_with_st_annes_card(),
        st_annes_review_surface=_st_annes_review_surface(
            status="SMOKE_OR_TEST_EVENT",
            invoice_status="NOT_INCLUDED_SMOKE_EVENT",
        ),
    )

    assert all(value is False for value in result.status["authority_boundary"].values())
    assert result.status["machine_proof"]["unsafe_true_grants_absent"] is True
    assert result.status["machine_proof"]["business_action_truth_created"] is False


def test_generated_json_and_bridge_match():
    local_status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    bridge_status = json.loads(BRIDGE_STATUS_PATH.read_text(encoding="utf-8"))
    local_surface = json.loads(SURFACE_PATH.read_text(encoding="utf-8"))
    bridge_surface = json.loads(BRIDGE_SURFACE_PATH.read_text(encoding="utf-8"))

    assert bridge_status == local_status
    assert bridge_surface == local_surface
    assert local_status["schema_version"] == "helm_action_lifecycle_status_v0"
