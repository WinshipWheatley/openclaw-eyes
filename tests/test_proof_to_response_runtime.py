import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import proof_to_response_runtime as runtime


FIXED_NOW = "2026-06-06T16:00:00+00:00"


def _publish(scenario_id="finance_capital_hilton_payment_watch", candidate=None, tmp_path=None):
    sqlite_path = (tmp_path / "runtime.sqlite") if tmp_path else None
    return runtime.publish_response(
        scenario_id,
        candidate_response=candidate,
        generated_at=FIXED_NOW,
        sqlite_path=sqlite_path,
    )


def _candidate(scenario_id="finance_capital_hilton_payment_watch", **overrides):
    bundle = runtime.build_or_load_proof_bundle(scenario_id)
    candidate = runtime.fixture_candidate_response(bundle)
    candidate.update(overrides)
    return candidate


def test_valid_capital_hilton_candidate_publishes(tmp_path):
    result = _publish(tmp_path=tmp_path)
    response = result["published_response"]

    assert result["verifier_result"]["publishable"] is True
    assert response["verification_status"] == "publishable"
    assert response["headline"] == "Payment evidence needed"
    assert "Coupa is processing" in response["body"]
    assert "can't mark this paid" in response["body"]
    assert response["next_step"] == "Attach payment evidence."
    assert "ledger mutation" in response["cannot_do_yet"]
    assert "paid marking" in response["cannot_do_yet"]
    assert "Coupa/browser action" in response["cannot_do_yet"]


def test_capital_hilton_attach_proof_explanation_publishes_candidate_evidence_copy(tmp_path):
    result = _publish("finance_capital_hilton_attach_proof_explanation", tmp_path=tmp_path)
    response = result["published_response"]

    assert result["verifier_result"]["publishable"] is True
    assert response["verification_status"] == "publishable"
    assert response["headline"] == "Proof can be recorded"
    assert "candidate/payment-processing evidence" in response["body"]
    assert "will not mark this paid" in response["body"]
    assert "touch the ledger" in response["body"]
    assert response["next_step"] == "Attach payment evidence."
    assert response["authority_boundary"]["protected_actions_allowed"] is False
    assert "paid marking" in response["cannot_do_yet"]
    assert "ledger mutation" in response["cannot_do_yet"]


def test_candidate_claiming_paid_fails(tmp_path):
    candidate = _candidate(draft_body="Payment evidence is missing. The invoice has been paid. The ledger stays untouched.")
    result = _publish(candidate=candidate, tmp_path=tmp_path)

    assert result["published_response"]["verification_status"] == "fallback"
    assert "unsupported_completion_claim" in result["published_response"]["fallback_reason"]


def test_candidate_promising_ledger_mutation_fails(tmp_path):
    candidate = _candidate(draft_body="Payment evidence is missing. I will update the ledger after this. The ledger stays untouched.")
    result = _publish(candidate=candidate, tmp_path=tmp_path)

    assert result["published_response"]["verification_status"] == "fallback"
    assert "protected_action_promise:ledger_mutation" in result["published_response"]["fallback_reason"]


def test_candidate_saying_email_sent_fails_without_receipt(tmp_path):
    candidate = _candidate(
        "business_development_capital_hilton_followup",
        draft_headline="Follow-up sent",
        draft_body="I sent the follow-up email to Capital Hilton.",
        draft_next_step="Stage follow-up",
        claimed_facts=["followup_stageable"],
        implied_actions=["email_send"],
        requested_controls=["Stage follow-up"],
    )
    result = _publish("business_development_capital_hilton_followup", candidate=candidate, tmp_path=tmp_path)

    assert result["published_response"]["verification_status"] == "fallback"
    assert "protected_action_promise:email_send" in result["published_response"]["fallback_reason"]
    assert "unsupported_completion_claim" in result["published_response"]["fallback_reason"]


def test_candidate_promising_coupa_submit_fails(tmp_path):
    candidate = _candidate(
        "protected_coupa_ledger_email_request",
        draft_headline="Submit in Coupa",
        draft_body="Protected action is blocked until proof and approval, but I will submit this in Coupa.",
        draft_next_step="Submit in Coupa",
        claimed_facts=["protected_action_blocked"],
        implied_actions=["coupa_submit"],
        requested_controls=["Submit in Coupa"],
    )
    result = _publish("protected_coupa_ledger_email_request", candidate=candidate, tmp_path=tmp_path)

    assert result["published_response"]["verification_status"] == "fallback"
    assert "protected_action_promise:coupa_submit" in result["published_response"]["fallback_reason"]


def test_machine_contract_jargon_fails(tmp_path):
    candidate = _candidate(draft_body="The dynamic card read model says payment evidence is missing and the ledger stays untouched.")
    result = _publish(candidate=candidate, tmp_path=tmp_path)

    assert result["published_response"]["verification_status"] == "fallback"
    assert "machine_contract_jargon" in result["published_response"]["fallback_reason"]


def test_overlong_candidate_fails(tmp_path):
    candidate = _candidate(draft_body="Payment evidence is missing. " + ("Extra detail. " * 40))
    result = _publish(candidate=candidate, tmp_path=tmp_path)

    assert result["published_response"]["verification_status"] == "fallback"
    assert "response_not_concise" in result["published_response"]["fallback_reason"]


def test_unknown_context_publishes_safe_fallback(tmp_path):
    candidate = _candidate(
        "unknown_context",
        draft_headline="I can stage it",
        draft_body="I can stage a package now.",
        draft_next_step="Stage package",
        claimed_facts=["lane_context_missing"],
        requested_controls=["Stage package"],
    )
    result = _publish("unknown_context", candidate=candidate, tmp_path=tmp_path)
    response = result["published_response"]

    assert response["verification_status"] == "fallback"
    assert response["headline"] == "Needs lane context"
    assert "world and thread" in response["body"].lower()
    assert "package staging" in response["cannot_do_yet"]


def test_self_heal_candidate_includes_blocker_proof_can_do_cannot_do_next_step(tmp_path):
    result = _publish("self_heal_missing_proof_for_payment", tmp_path=tmp_path)
    response = result["published_response"]

    assert response["verification_status"] == "publishable"
    assert response["speaker_ref"] == "chief"
    assert "Payment evidence is missing" in response["headline"]
    assert "Proof:" in response["body"]
    assert response["can_do_now"]
    assert response["cannot_do_yet"]
    assert response["next_step"] == "Attach payment proof"


def test_published_response_includes_proof_meters_and_collapsed_details(tmp_path):
    response = _publish(tmp_path=tmp_path)["published_response"]

    assert response["proof_meters"]
    assert response["details_collapsed"] is True
    assert response["authority_boundary"]["protected_actions_allowed"] is False


def test_export_sqlite_row_count_matches_status(tmp_path):
    result = runtime.export_proof_to_response_runtime(
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Proof To Response Runtime.md",
        sqlite_path=tmp_path / "proof_to_response_runtime.sqlite",
        generated_at=FIXED_NOW,
    )
    status = json.loads(Path(result["status_path"]).read_text(encoding="utf-8"))
    con = sqlite3.connect(result["sqlite_path"])
    row_count = con.execute("select count(*) from proof_to_response_receipts").fetchone()[0]

    assert result["status"] == runtime.READY_STATUS
    assert status["sqlite_row_count"] == row_count
    assert row_count == status["published_response_count"]


def test_export_json_bridge_equality_and_unsafe_scan(tmp_path):
    result = runtime.export_proof_to_response_runtime(
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Proof To Response Runtime.md",
        sqlite_path=tmp_path / "proof_to_response_runtime.sqlite",
        generated_at=FIXED_NOW,
    )

    for local_key, bridge_key in [
        ("contract_path", "bridge_contract_path"),
        ("status_path", "bridge_status_path"),
        ("latest_path", "bridge_latest_path"),
    ]:
        local = json.loads(Path(result[local_key]).read_text(encoding="utf-8"))
        bridge = json.loads(Path(result[bridge_key]).read_text(encoding="utf-8"))
        assert local == bridge
        assert runtime.unsafe_true_grants(local) == []
    assert result["status"] == runtime.READY_STATUS
