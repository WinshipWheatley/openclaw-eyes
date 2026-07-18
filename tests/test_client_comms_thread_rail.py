import json

import client_comms_thread_rail as rail
from scripts.export_client_comms_thread_rail import main as export_main


FIXED_NOW = "2026-05-28T16:20:00+00:00"


def test_first_clara_contact_generates_intro_required_policy():
    payload = rail.build_payload(generated_at=FIXED_NOW)
    live = payload["fixtures"]["live_arts_md_first_invoice_email"]

    assert live["first_contact_policy"]["intro_required"] is True
    assert live["first_contact_policy"]["first_clara_contact"] is True
    assert "I'm Clara Reid" in live["draft_candidate"]["body"]
    assert "Live Arts MD" in live["draft_candidate"]["body"]


def test_existing_clara_thread_does_not_repeat_full_intro():
    payload = rail.build_payload(generated_at=FIXED_NOW)
    existing = payload["fixtures"]["existing_clara_thread_no_repeat_intro"]

    assert existing["first_contact_policy"]["intro_required"] is False
    assert "I'm Clara Reid" not in existing["draft_candidate"]["body"]
    assert existing["first_contact_policy"]["prior_clara_thread_exists"] is True


def test_intro_is_contextual_not_fixed_canned_block():
    payload = rail.build_payload(generated_at=FIXED_NOW)
    live_body = payload["fixtures"]["live_arts_md_first_invoice_email"]["draft_candidate"]["body"]
    capital_body = payload["fixtures"]["capital_hilton_followup_thread"]["draft_candidate"]["body"]

    assert live_body != capital_body
    assert "confirmed Live Arts MD invoice" in live_body
    assert "I hope this note finds you well" not in live_body
    assert "confirmed Excel invoice" in capital_body
    assert payload["first_contact_intro_policy"]["contextual_not_canned"] is True


def test_clara_draft_remains_draft_only_and_sent_false():
    payload = rail.build_payload(generated_at=FIXED_NOW)
    draft = payload["fixtures"]["live_arts_md_first_invoice_email"]["draft_candidate"]

    assert draft["selected_voice"] == "CLARA"
    assert draft["external_identity"] == "CLARA_REID"
    assert draft["draft_only"] is True
    assert draft["sent"] is False
    assert draft["send_allowed"] is False
    assert draft["guardian_approval_required"] is True


def test_reply_inside_owned_thread_creates_reply_draft_candidate():
    payload = rail.build_payload(generated_at=FIXED_NOW)
    reply = payload["fixtures"]["reply_inside_clara_thread"]

    assert reply["reply_intent"] == "RESEND_INVOICE_REQUEST"
    assert reply["allowed_to_draft"] is True
    assert reply["draft_candidate"]["draft_only"] is True
    assert "Nothing has been resent yet" in reply["draft_candidate"]["body"]
    assert reply["send_allowed"] is False


def test_reply_draft_requires_guardian_approval_before_send():
    payload = rail.build_payload(generated_at=FIXED_NOW)
    reply = payload["fixtures"]["reply_inside_clara_thread"]

    assert reply["guardian_approval_required"] is True
    assert reply["draft_candidate"]["guardian_approval_request_status"] == "REQUIRED_BEFORE_SEND"
    assert "operator_approval_receipt" in reply["draft_candidate"]["required_receipts_before_send"]
    assert "email_send_receipt" in reply["draft_candidate"]["required_receipts_before_send"]


def test_new_email_outside_owned_thread_offers_adoption_not_auto_reply():
    payload = rail.build_payload(generated_at=FIXED_NOW)
    offer = payload["fixtures"]["new_email_outside_clara_thread"]

    assert offer["thread_status"] == "THREAD_ADOPTION_OFFERED"
    assert offer["auto_adopted"] is False
    assert offer["auto_replied"] is False
    assert {action["action_kind"] for action in offer["actions"]} == {
        "ADOPT_THREAD_AND_DRAFT",
        "IGNORE_THREAD",
        "SHOW_EMAIL_SUMMARY",
        "ASK_ME_LATER",
    }


def test_uncertain_or_high_risk_client_request_needs_child_package_or_operator_input():
    payload = rail.build_payload(generated_at=FIXED_NOW)
    risky = payload["fixtures"]["reply_requires_child_package"]

    assert risky["reply_intent"] == "CHANGE_INVOICE_AMOUNT"
    assert risky["allowed_to_draft"] is False
    assert risky["needs_child_packages"] is True
    assert risky["needs_operator_input"] is True
    assert "operator_decision" in risky["required_context"]


def test_clara_cannot_claim_send_resend_or_change_amount_without_receipts():
    payload = rail.build_payload(generated_at=FIXED_NOW)
    live = payload["fixtures"]["live_arts_md_first_invoice_email"]["draft_candidate"]
    reply = payload["fixtures"]["reply_inside_clara_thread"]["draft_candidate"]
    risky = payload["fixtures"]["reply_requires_child_package"]

    assert live["send_execution_status"] == "NOT_SENT"
    assert "sent" in live["forbidden_claims"]
    assert "resent" in reply["forbidden_claims"]
    assert "changed invoice amount" in reply["forbidden_claims"]
    assert risky["draft_candidate"] is None


def test_thread_adoption_requires_operator_approval():
    payload = rail.build_payload(generated_at=FIXED_NOW)
    offer = payload["fixtures"]["new_email_outside_clara_thread"]
    adopt = next(action for action in offer["actions"] if action["action_kind"] == "ADOPT_THREAD_AND_DRAFT")

    assert offer["adoption_status"] == "OPERATOR_DECISION_REQUIRED"
    assert adopt["requires_operator_approval"] is True
    assert adopt["hidden_request_payload"]["email_send_allowed"] is False


def test_no_live_gmail_or_email_send_occurs():
    payload = rail.build_payload(generated_at=FIXED_NOW)

    assert all(value is False for value in payload["authority_boundary"].values())
    assert payload["machine_proof"]["no_live_gmail_polling"] is True
    assert payload["machine_proof"]["no_email_send"] is True
    assert payload["machine_proof"]["no_gmail_draft_created"] is True


def test_export_writes_parseable_read_model_and_bridge(tmp_path):
    export_root = tmp_path / "read_models"
    bridge_root = tmp_path / "bridge"

    assert export_main(
        [
            "--export-root",
            str(export_root),
            "--bridge-export-root",
            str(bridge_root),
            "--generated-at",
            FIXED_NOW,
        ]
    ) == 0
    source = export_root / rail.JSON_EXPORT_NAME
    operator = export_root / rail.OPERATOR_EXPORT_NAME
    bridge = bridge_root / rail.JSON_EXPORT_NAME

    assert source.is_file()
    assert operator.is_file()
    assert bridge.is_file()
    assert json.loads(source.read_text(encoding="utf-8"))["read_model_id"] == rail.READ_MODEL_ID
    assert source.read_bytes() == bridge.read_bytes()
