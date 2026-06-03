import json
import re
from pathlib import Path

import homecoming_brief as brief


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PATH = ROOT / "generated/read_models/homecoming_brief.json"
BRIDGE_PATH = Path("/mnt/e/openclaw/generated/read_models/homecoming_brief.json")


def _sources() -> dict:
    return {
        "client_work_closeout": {"status": "CLIENT_WORK_CLOSEOUT_READY"},
        "operator_next_decision": {
            "headline": "Watch Capital Hilton payment",
            "plain_summary": "Coupa is processing. Ledger stays untouched until payment proof arrives.",
            "action_label": "Open Capital Hilton",
            "action_type": "navigate",
            "target_world_ref": "finance",
            "target_thread_ref": "capital_hilton",
        },
        "overnight_workboard": {
            "hermes_recommendation": {
                "recommended_lane_sequence": [
                    {"label": "Confirm/discard St. Anne's work-log events"},
                ]
            }
        },
        "package_event_index": {"status": "PACKAGE_EVENT_INDEX_READY", "event_count": 32},
        "operator_conversation_journal": {"status": "OPERATOR_CONVERSATION_JOURNAL_READY", "entry_count": 32},
        "capital_hilton_invoice_status": {
            "coupa_submission_recorded": True,
            "coupa_submitted": True,
            "coupa_status_observed": "Processing",
            "email_to_annette_recorded": True,
            "email_status": "sent_operator_assisted",
            "paid": False,
            "ledger_mutation_performed": False,
        },
        "capital_hilton_proposal": {
            "proposal_status": "SENT_FOR_CLIENT_REVIEW",
            "client_review_pending": True,
            "email_send_record": {"recipient_display_name": "Will / Lawrence Valcovic"},
            "paid": False,
            "ledger_posting_allowed": False,
        },
        "st_annes_invoice_status": {
            "invoice_status": "MANUAL_SEND_OUT_OF_BAND_RECORDED",
            "manual_send_out_of_band_known": True,
            "paid": False,
            "ledger_mutation_performed": False,
        },
        "st_annes_work_log_events": {
            "event_count": 1,
            "staged_events": [
                {
                    "billing_truth_status": "SMOKE_OR_TEST_EVENT",
                    "invoice_inclusion_status": "NOT_INCLUDED_SMOKE_EVENT",
                }
            ],
        },
        "automation_permission_registry": {
            "machine_proof": {
                "ledger_post_blocked": True,
                "paid_marking_blocked": True,
                "gmail_send_blocked_until_explicit_gate": True,
                "coupa_submit_blocked_until_explicit_gate": True,
            }
        },
        "agent_voice_profiles": {"status": "AGENT_VOICE_PROFILES_V0_READY"},
    }


def _make_brief() -> dict:
    return brief.build_homecoming_brief(**_sources(), generated_at="2026-06-03T02:00:00+00:00")


def test_brief_includes_st_annes_invoice_sent_manual_truth():
    payload = _make_brief()
    text = payload["spoken_text"].lower()

    assert "st. anne's" in text
    assert "may invoice" in text
    assert "sent" in text
    assert "manual" in text or "out of band" in text


def test_brief_includes_capital_hilton_submitted_and_emailed_truth():
    payload = _make_brief()
    text = payload["spoken_text"].lower()

    assert "capital hilton" in text
    assert "submitted" in text
    assert "processing" in text
    assert "annette" in text
    assert "emailed" in text


def test_brief_includes_proposal_sent_for_client_review_truth():
    payload = _make_brief()
    text = payload["spoken_text"].lower()

    assert "proposal" in text
    assert "lawrence" in text
    assert "review" in text


def test_brief_includes_no_paid_and_no_ledger_truth():
    payload = _make_brief()
    text = payload["spoken_text"].lower()

    assert "no payment has been marked" in text
    assert "ledger is untouched" in text
    assert payload["authority_boundary"]["paid"] is False
    assert payload["authority_boundary"]["ledger_posting_allowed"] is False


def test_spoken_text_is_tts_safe_and_visible_text_hides_machine_details():
    payload = _make_brief()
    visible_text = " ".join(payload["visible_summary"] + [item["text"] for item in payload["agent_inserts"]])

    assert payload["speaker_ref"] == "cassandra"
    assert payload["spoken_text"].startswith("Good")
    assert not re.search(r"https?://|/mnt/|\\.json|\\.sqlite|`|#", payload["spoken_text"])
    assert not re.search(r"package_event:|workflow_package|\\.sqlite|sqlite", visible_text, re.IGNORECASE)
    assert "  " not in payload["spoken_text"]


def test_homecoming_brief_uses_evidence_backed_readiness_wording():
    payload = _make_brief()
    combined = " ".join([payload["headline"], payload["spoken_text"], *payload["visible_summary"]])

    assert "OpenClaw is calm and ready" not in combined
    assert "Client work is recorded, and protected actions remain locked." in combined
    assert payload["evidence_confidence"]["readiness_or_calm_claim"] == "not_asserted"
    assert payload["machine_proof"]["unproven_ready_claim_absent"] is True


def test_authority_flags_false():
    payload = _make_brief()

    assert all(value is False for value in payload["authority_boundary"].values())
    assert payload["machine_proof"]["unsafe_true_grants_absent"] is True


def test_generated_json_parse_and_bridge_equality():
    local = json.loads(LOCAL_PATH.read_text(encoding="utf-8"))
    bridge = json.loads(BRIDGE_PATH.read_text(encoding="utf-8"))

    assert local == bridge
    assert local["schema_version"] == "homecoming_brief_v0"
    assert local["speaker_ref"] == "cassandra"
    assert local["next_recommended_action"]["label"]
    assert local["next_recommended_action"]["target_world_ref"]
    assert local["next_recommended_action"]["target_thread_ref"]


def test_unsafe_true_grant_scan_clean_in_generated_payload():
    payload = json.loads(LOCAL_PATH.read_text(encoding="utf-8"))
    unsafe_keys = {
        "email_send_allowed",
        "ledger_posting_allowed",
        "browser_access_allowed",
        "gmail_allowed",
        "coupa_allowed",
        "portal_submit_allowed",
        "sent",
        "paid",
    }

    assert not [
        key
        for key, value in payload["authority_boundary"].items()
        if key in unsafe_keys and value is True
    ]
