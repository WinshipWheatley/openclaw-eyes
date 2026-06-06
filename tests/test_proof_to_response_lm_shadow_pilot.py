import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import proof_to_response_lm_shadow_pilot as pilot


FIXED_NOW = "2026-06-06T22:30:00+00:00"


def _candidate(scenario_id: str = "finance_capital_hilton_payment_watch", **overrides):
    bundle = pilot.build_pilot_proof_bundle(scenario_id)
    candidate = pilot.mock_lm_style_candidate_response(bundle)
    candidate.update(overrides)
    return candidate


def _run(scenario_id: str = "finance_capital_hilton_payment_watch", candidate=None):
    return pilot.run_pilot_scenario(
        scenario_id,
        candidate_response=candidate,
        generated_at=FIXED_NOW,
    )


def test_lm_style_capital_hilton_response_passes_inside_proof():
    run = _run()

    assert run["verifier_result"]["publishable"] is True
    assert run["published_response"]["verification_status"] == "publishable"
    assert run["published_response"]["headline"] == "Payment evidence needed"
    assert "Coupa is processing" in run["published_response"]["body"]
    assert "can't mark this paid" in run["published_response"]["body"]
    assert run["published_response"]["next_step"] == "Attach payment evidence."
    assert run["published_response"]["speaker_ref"] == "chief"


def test_candidate_claiming_paid_fails_and_publishes_fallback():
    candidate = _candidate(
        draft_body="Payment evidence is missing. The invoice has been paid. The ledger stays untouched.",
    )
    run = _run(candidate=candidate)

    assert run["verifier_result"]["publishable"] is False
    assert "unsupported_completion_claim" in run["fallback_reason"]
    assert run["published_response"]["verification_status"] == "fallback"
    assert "has been paid" not in run["published_response"]["body"].lower()


def test_candidate_claiming_email_sent_fails():
    candidate = _candidate(
        "business_development_capital_hilton_followup",
        draft_headline="Follow-up sent",
        draft_body="I sent the follow-up email. A follow-up can be staged, but this text claims send.",
        draft_next_step="Stage follow-up",
        claimed_facts=["followup_stageable"],
        implied_actions=["email_send"],
        requested_controls=["Stage follow-up"],
    )
    run = _run("business_development_capital_hilton_followup", candidate)

    assert run["published_response"]["verification_status"] == "fallback"
    assert "protected_action_promise:email_send" in run["fallback_reason"]
    assert "sent the follow-up" not in run["published_response"]["body"].lower()


def test_candidate_promising_coupa_submit_fails():
    candidate = _candidate(
        "protected_coupa_ledger_email_request",
        draft_headline="Submit in Coupa",
        draft_body="Protected action is blocked until proof and approval, but I will submit this in Coupa.",
        draft_next_step="Submit in Coupa",
        claimed_facts=["protected_action_blocked", "proof_and_approval_required"],
        implied_actions=["coupa_submit"],
        requested_controls=["Submit in Coupa"],
    )
    run = _run("protected_coupa_ledger_email_request", candidate)

    assert run["published_response"]["verification_status"] == "fallback"
    assert "protected_action_promise:coupa_submit" in run["fallback_reason"]
    assert "will submit" not in run["published_response"]["body"].lower()


def test_machine_contract_jargon_fails():
    candidate = _candidate(
        draft_body="The generated/read_models source_request_id says payment evidence is missing and the ledger stays untouched.",
    )
    run = _run(candidate=candidate)

    assert run["published_response"]["verification_status"] == "fallback"
    assert "machine_contract_jargon" in run["fallback_reason"]


def test_overlong_response_fails():
    candidate = _candidate(
        draft_body="Payment evidence is missing. The ledger stays untouched. " + ("Extra detail. " * 40),
    )
    run = _run(candidate=candidate)

    assert run["published_response"]["verification_status"] == "fallback"
    assert "response_not_concise" in run["fallback_reason"]


def test_safe_fallback_publishes_when_verifier_rejects():
    candidate = _candidate(
        "business_development_capital_hilton_followup",
        draft_headline="Follow-up sent",
        draft_body="I sent the follow-up email.",
        draft_next_step="Send email",
        claimed_facts=["followup_stageable"],
        implied_actions=["email_send"],
        requested_controls=["Send email"],
    )
    run = _run("business_development_capital_hilton_followup", candidate)

    assert run["publication_decision"] == "safe_fallback_published"
    assert run["published_response"]["verification_status"] == "fallback"
    assert run["verifier_failure_reasons"]
    assert run["candidate_text_published"] is False


def test_dynamic_cards_remain_support():
    run = _run("business_development_capital_hilton_followup")

    assert run["primary_response_kind"] == "proof_to_response_text"
    assert run["dynamic_card_role"] == "support_display"
    assert run["dynamic_card_support"]["selected_card_ref"]
    assert run["published_response"]["details_collapsed"] is True


def test_pilot_read_model_builds_all_required_scenarios():
    read_model = pilot.build_read_model(generated_at=FIXED_NOW)

    assert read_model["status"] == pilot.READY_STATUS
    assert read_model["pilot_run_count"] == 6
    assert {run["scenario_id"] for run in read_model["pilot_runs"]} == set(pilot.PILOT_SCENARIOS)
    assert read_model["machine_proof"]["all_pilot_drafts_verified"] is True
    assert read_model["machine_proof"]["dynamic_cards_support_not_primary"] is True
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_and_unsafe_scan(tmp_path):
    result = pilot.export_proof_to_response_lm_shadow_pilot(
        read_model_root=ROOT / "generated/read_models",
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Proof To Response LM Shadow Pilot.md",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))

    assert result["status"] == pilot.READY_STATUS
    assert local == bridge
    assert pilot.unsafe_true_grants(local) == []
    assert Path(result["wiki_path"]).read_text(encoding="utf-8").startswith("# Proof To Response LM Shadow Pilot")
