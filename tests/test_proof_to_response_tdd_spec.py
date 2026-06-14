import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import proof_to_response_tdd_spec as proof_response


FIXED_NOW = "2026-06-06T12:00:00+00:00"


def _read_model():
    return proof_response.build_read_model(generated_at=FIXED_NOW)


def _response(read_model, scenario_id):
    for response in read_model["example_responses"]:
        if response["scenario_id"] == scenario_id:
            return response
    raise AssertionError(f"missing response scenario: {scenario_id}")


def _primary_text(response):
    human = response["human_response"]
    parts = [
        human["headline"],
        human["body"],
        human["next_step"],
        " ".join(human["missing_input"]),
        " ".join(human["what_i_can_do_now"]),
        " ".join(human["what_i_cannot_do_yet"]),
    ]
    return " ".join(parts).lower()


def test_finance_capital_hilton_payment_watch_response():
    response = _response(_read_model(), "finance_capital_hilton_payment_watch")
    text = _primary_text(response)

    assert response["speaker_ref"] in {"chief", "cassandra"}
    assert "payment evidence" in text
    assert "ledger stays untouched" in text or "ledger remains untouched" in text
    assert response["human_response"]["next_step"] == "Attach proof"
    assert "card deck" not in text
    assert proof_response.validate_response(response) == []


def test_finance_live_arts_payment_evidence_response():
    response = _response(_read_model(), "finance_live_arts_payment_evidence")
    text = _primary_text(response)

    assert "evidence recorded" in text or "candidate evidence recorded" in text
    assert "does not mark paid" in text or "not paid" in text
    assert "ledger" in text
    assert "verify arrival" in text or "ledger review" in text
    assert proof_response.validate_response(response) == []


def test_business_development_followup_response_stages_only():
    response = _response(_read_model(), "business_development_capital_hilton_followup")
    text = _primary_text(response)

    assert response["speaker_ref"] == "cassandra"
    assert "draft can be staged" in text or "follow-up can be staged" in text
    assert "no send" in text or "nothing gets sent" in text
    assert response["human_response"]["next_step"] == "Stage follow-up"
    assert proof_response.validate_response(response) == []


def test_build_review_packet_response_records_review_only():
    response = _response(_read_model(), "build_review_packet")
    text = _primary_text(response)

    assert "informational" in text or "ready for review" in text or "resolved" in text
    assert "no merge" in text
    assert "no push" in text
    assert response["human_response"]["next_step"] in {"Review packet", "Request rework", "Mark informational"}
    assert proof_response.validate_response(response) == []


def test_unknown_context_needs_lane_context_precise_question():
    response = _response(_read_model(), "unknown_context")
    text = _primary_text(response)

    assert response["speaker_ref"] == "openclaw"
    assert "needs lane context" in text or "need lane context" in text
    assert "package staging" in text
    assert "which world and lane" in text
    assert response["human_response"]["missing_input"] == ["world_ref", "thread_ref"]
    assert proof_response.validate_response(response) == []


def test_protected_coupa_ledger_email_request_guardian_block():
    response = _response(_read_model(), "protected_coupa_ledger_email_request")
    text = _primary_text(response)

    assert response["speaker_ref"] == "guardian"
    assert response["voice_mode"] == "safety"
    assert "blocked" in text
    assert "proof" in text
    assert "approval" in text
    assert "cannot send" in text
    assert "submit" in text
    assert "ledger" in text
    assert proof_response.validate_response(response) == []


def test_responses_are_concise():
    for response in _read_model()["example_responses"]:
        human = response["human_response"]
        assert "\n" not in human["headline"]
        assert len(human["headline"]) <= 90
        paragraphs = [part for part in human["body"].split("\n\n") if part.strip()]
        assert len(paragraphs) <= 2
        assert all(len(part) <= 220 for part in paragraphs)
        assert len(human["next_step"]) <= 120
        assert proof_response.response_is_concise(response)


def test_every_factual_claim_has_source_ref():
    for response in _read_model()["example_responses"]:
        allowed_refs = proof_response.response_grounding_refs(response)
        assert allowed_refs
        for claim in response["factual_claims"]:
            assert claim["claim"]
            assert claim["source_refs"]
            assert set(claim["source_refs"]).issubset(allowed_refs)


def test_no_paid_sent_submitted_without_receipt():
    for response in _read_model()["example_responses"]:
        assert proof_response.unproven_completion_claims(response) == []


def test_generated_summary_cannot_override_receipt():
    read_model = _read_model()

    assert read_model["rules"]["generated_summary_cannot_override_receipt"] is True
    assert read_model["rules"]["lm_may_not_create_truth_or_authority"] is True
    for response in read_model["example_responses"]:
        assert response["grounding_order"][0] == "receipts"
        assert "generated_summary" in response["grounding_order"]


def test_authority_grant_terms_stay_false_and_details_collapsed():
    read_model = _read_model()

    assert read_model["status"] == proof_response.READY_STATUS
    assert proof_response.unsafe_true_grants(read_model) == []
    for response in read_model["example_responses"]:
        assert response["authority_boundary"]["protected_actions_allowed"] is False
        assert response["details_collapsed"] is True
        assert proof_response.validate_authority_boundary(response) == []


def test_no_machine_contract_jargon_in_primary_response():
    for response in _read_model()["example_responses"]:
        text = _primary_text(response)
        for term in proof_response.MACHINE_CONTRACT_JARGON:
            assert term not in text


def test_read_model_validation_and_export_round_trip(tmp_path):
    bridge_root = tmp_path / "bridge"
    result = proof_response.export_proof_to_response_tdd_spec(
        read_model_root=ROOT / "generated/read_models",
        export_root=tmp_path / "read_models",
        bridge_export_root=bridge_root,
        wiki_path=tmp_path / "Proof To Response TDD Spec.md",
        generated_at=FIXED_NOW,
    )
    local_payload = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge_payload = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))

    assert result["status"] == proof_response.READY_STATUS
    assert local_payload == bridge_payload
    assert local_payload["response_count"] == 6
    assert local_payload["machine_proof"]["response_validation_errors"] == []
