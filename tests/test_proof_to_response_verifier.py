import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import proof_bundle_builder as bundles
import proof_to_response_verifier as verifier


def _bundle(scenario_id="finance_capital_hilton_payment_watch"):
    return bundles.build_proof_bundle(scenario_id)


def _draft(bundle, *, headline="Payment watch", body=None, next_step="Attach proof", controls=None):
    return {
        "response_id": "lm_shadow_response:test",
        "proof_bundle_id": bundle["proof_bundle_id"],
        "speaker_ref": bundle["response_speaker_ref"],
        "draft_headline": headline,
        "draft_body": body or "Payment evidence is still missing. Coupa is processing, and the ledger stays untouched until payment is confirmed.",
        "draft_next_step": next_step,
        "claimed_facts": ["payment_evidence_missing", "coupa_processing", "ledger_untouched"],
        "implied_actions": [],
        "requested_controls": controls if controls is not None else ["Attach proof"],
        "uncertainty_notes": [],
    }


def test_capital_hilton_lm_draft_passes_when_payment_missing_and_ledger_untouched():
    bundle = _bundle()
    result = verifier.verify_lm_shadow_response(_draft(bundle), bundle)

    assert result["publishable"] is True
    assert result["status"] == "VERIFIED_FOR_SHADOW_PUBLISH"
    assert result["verification_errors"] == []
    assert result["details_collapsed"] is True


def test_capital_hilton_lm_draft_fails_if_required_payment_missing_claim_omitted():
    bundle = _bundle()
    draft = _draft(bundle, body="Coupa is processing. The ledger stays untouched until payment is confirmed.")

    result = verifier.verify_lm_shadow_response(draft, bundle)

    assert result["publishable"] is False
    assert "required_phrase_missing:payment evidence" in result["verification_errors"]


def test_lm_draft_claiming_paid_fails():
    bundle = _bundle()
    draft = _draft(bundle, body="Payment evidence is still missing. The invoice has been paid. The ledger stays untouched.")

    result = verifier.verify_lm_shadow_response(draft, bundle)

    assert result["publishable"] is False
    assert any(error.startswith("unsupported_completion_claim") for error in result["verification_errors"])


def test_lm_draft_claiming_email_sent_fails_without_receipt():
    bundle = bundles.build_proof_bundle("business_development_capital_hilton_followup")
    draft = {
        "response_id": "lm_shadow_response:sent_claim",
        "proof_bundle_id": bundle["proof_bundle_id"],
        "speaker_ref": "cassandra",
        "draft_headline": "Follow-up sent",
        "draft_body": "I sent the follow-up email to Capital Hilton.",
        "draft_next_step": "Stage follow-up",
        "claimed_facts": ["followup_stageable"],
        "implied_actions": ["email_send"],
        "requested_controls": ["Stage follow-up"],
        "uncertainty_notes": [],
    }

    result = verifier.verify_lm_shadow_response(draft, bundle)

    assert result["publishable"] is False
    assert "protected_action_promise:email_send" in result["verification_errors"]
    assert any(error.startswith("unsupported_completion_claim") for error in result["verification_errors"])


def test_lm_draft_promising_coupa_submit_fails():
    bundle = bundles.build_proof_bundle("protected_coupa_ledger_email_request")
    draft = {
        "response_id": "lm_shadow_response:coupa_submit",
        "proof_bundle_id": bundle["proof_bundle_id"],
        "speaker_ref": "guardian",
        "draft_headline": "I can submit it",
        "draft_body": "Protected action is blocked until proof and approval, but I will submit this in Coupa once ready.",
        "draft_next_step": "Submit in Coupa",
        "claimed_facts": ["protected_action_blocked"],
        "implied_actions": ["coupa_submit"],
        "requested_controls": ["Submit in Coupa"],
        "uncertainty_notes": [],
    }

    result = verifier.verify_lm_shadow_response(draft, bundle)

    assert result["publishable"] is False
    assert "protected_action_promise:coupa_submit" in result["verification_errors"]
    assert "next_step_not_allowed:Submit in Coupa" in result["verification_errors"]


def test_machine_contract_jargon_fails_primary_response_verifier():
    bundle = _bundle()
    draft = _draft(bundle, body="The dynamic card read model says payment evidence is still missing and the ledger stays untouched.")

    result = verifier.verify_lm_shadow_response(draft, bundle)

    assert result["publishable"] is False
    assert any(error.startswith("machine_contract_jargon") for error in result["verification_errors"])


def test_overlong_response_fails_concision_verifier():
    bundle = _bundle()
    long_body = "Payment evidence is still missing. " + ("This extra sentence should not be in the concise response. " * 20)
    draft = _draft(bundle, body=long_body)

    result = verifier.verify_lm_shadow_response(draft, bundle)

    assert result["publishable"] is False
    assert "response_not_concise" in result["verification_errors"]


def test_allowed_controls_pass_only_when_mapped_to_controller_events_and_payloads():
    bundle = _bundle()
    assert verifier.verify_lm_shadow_response(_draft(bundle, controls=["Attach proof"]), bundle)["publishable"] is True

    bad = verifier.verify_lm_shadow_response(_draft(bundle, controls=["Wire money"]), bundle)

    assert bad["publishable"] is False
    assert "requested_control_not_allowed:Wire money" in bad["verification_errors"]


def test_unknown_context_produces_safe_fallback():
    bundle = bundles.build_proof_bundle("unknown_context")
    draft = {
        "response_id": "lm_shadow_response:unknown_context",
        "proof_bundle_id": bundle["proof_bundle_id"],
        "speaker_ref": "openclaw",
        "draft_headline": "Needs lane context",
        "draft_body": "Which world and thread should I use for this?",
        "draft_next_step": "Pick the world and thread",
        "claimed_facts": ["lane_context_missing"],
        "implied_actions": [],
        "requested_controls": ["Choose lane"],
        "uncertainty_notes": ["world_ref and thread_ref are missing"],
    }

    result = verifier.verify_lm_shadow_response(draft, bundle)

    assert result["publishable"] is True
    fallback = verifier.safe_fallback_response(bundle, reason="missing_context")
    assert fallback["draft_headline"] == "Needs lane context"
    assert "world and thread" in fallback["draft_body"].lower()


def test_unsafe_true_grant_scan_clean_for_verifier_result():
    bundle = _bundle()
    result = verifier.verify_lm_shadow_response(_draft(bundle), bundle)

    assert verifier.unsafe_true_grants(result) == []
