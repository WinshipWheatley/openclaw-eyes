import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import proof_bundle_builder as bundles
import proof_to_response_lm_shadow_pilot as pilot
import proof_to_response_runtime as runtime


FIXED_NOW = "2026-06-07T03:10:00+00:00"


def _text(value: object) -> str:
    return json.dumps(value, sort_keys=True).lower()


def test_redacted_proof_bundle_contains_allowed_fields():
    bundle = bundles.build_redacted_proof_bundle("finance_capital_hilton_payment_watch")
    lm_input = bundle["lm_input"]

    assert set(lm_input) == set(bundles._policy_module().ALLOWED_FIELD_REASONS)
    assert "payment evidence is missing" in _text(lm_input)
    assert "ledger remains untouched" in _text(lm_input)
    assert "coupa is processing" in _text(lm_input)
    assert bundles.validate_redacted_proof_bundle(bundle) == []


def test_redacted_proof_bundle_excludes_forbidden_fields():
    bundle = bundles.build_redacted_proof_bundle(
        "finance_capital_hilton_payment_watch",
        raw_request={
            "bank_account": "123456789",
            "routing_number": "987654321",
            "credential_token": "token-secret",
            "raw_prompt_body": "private prompt body",
            "raw_artifact_text": "private artifact",
            "authority_granted": True,
        },
    )
    text = _text(bundle["lm_input"])

    assert "123456789" not in text
    assert "987654321" not in text
    assert "token-secret" not in text
    assert "private prompt body" not in text
    assert "private artifact" not in text
    assert "authority_granted" not in text
    assert "financial_detail_excluded" in bundle["excluded_input_markers"]
    assert "authority_input_excluded" in bundle["excluded_input_markers"]


def test_financial_sensitive_bundle_is_local_only_redacted():
    bundle = bundles.build_redacted_proof_bundle(
        "finance_live_arts_payment_evidence",
        raw_request={"raw_ocr_text": "ACH account 111222333 full document text"},
    )
    text = _text(bundle)

    assert bundle["privacy_class"] == "financial_sensitive/local_only"
    assert bundle["sensitive_detail_policy"] == "redacted_summary_only"
    assert "candidate payment-processing evidence" in text
    assert "does not mark the invoice paid" in text
    assert "111222333" not in text
    assert "full document text" not in text


def test_operator_device_session_verification_secrets_are_absent():
    bundle = bundles.build_redacted_proof_bundle(
        "finance_capital_hilton_payment_watch",
        raw_request={
            "operator_envelope": {"secret": "operator-secret"},
            "device_verification_secret": "device-secret",
            "session_verification_secret": "session-secret",
        },
    )
    text = _text(bundle["lm_input"])

    assert "operator-secret" not in text
    assert "device-secret" not in text
    assert "session-secret" not in text
    assert "operator_envelope" not in text


def test_agent_voice_mode_present_but_grants_no_authority():
    bundle = bundles.build_redacted_proof_bundle("finance_capital_hilton_payment_watch")
    lm_input = bundle["lm_input"]

    assert lm_input["agent_voice_mode"] == "diagnostic"
    assert bundle["response_speaker_ref"] == "chief"
    assert bundle["voice_mode_policy"]["may_shape_phrasing"] is True
    assert bundle["voice_mode_policy"]["may_create_truth"] is False
    assert bundle["voice_mode_policy"]["may_grant_authority"] is False
    assert all(value is False for value in bundle["authority_boundary"].values())


def test_cassandra_voice_bundle_allows_client_aware_tone_but_no_send():
    bundle = bundles.build_redacted_proof_bundle("business_development_capital_hilton_followup")
    candidate = pilot.mock_lm_style_candidate_response(bundle)
    text = _text({"bundle": bundle["lm_input"], "candidate": candidate})

    assert bundle["response_speaker_ref"] == "cassandra"
    assert bundle["lm_input"]["agent_voice_mode"] == "operations"
    assert "warm client-aware" in text
    assert "will not send it" in text
    assert "send_email_allowed" not in text
    assert bundle["authority_boundary"]["email_send_allowed"] is False


def test_niles_voice_bundle_allows_creative_context_but_excludes_finance_proof():
    bundle = bundles.build_redacted_proof_bundle(
        "music_niles_controller_mapping",
        creative_context={"target_software": "Ableton", "controller": "Push"},
        raw_request={"finance_proof": "Capital Hilton ACH account 555444333"},
    )
    text = _text(bundle["lm_input"])

    assert bundle["response_speaker_ref"] == "niles"
    assert bundle["lm_input"]["agent_voice_mode"] == "creative"
    assert "ableton" in text
    assert "push" in text
    assert "capital hilton" not in text
    assert "555444333" not in text
    assert "finance" not in bundle["proof_scope"]


def test_shadow_pilot_uses_only_redacted_bundle_fields():
    bundle = pilot.build_pilot_proof_bundle("finance_capital_hilton_payment_watch")
    run = pilot.run_pilot_scenario("finance_capital_hilton_payment_watch", generated_at=FIXED_NOW)

    assert "lm_input" in bundle
    assert "known_facts" not in bundle
    assert "allowed_response_controls" not in bundle
    assert set(bundle["lm_input"]) == set(bundles._policy_module().ALLOWED_FIELD_REASONS)
    assert run["proof_bundle"]["schema_version"] == "redacted_proof_bundle_v0"
    assert run["redaction_validation_errors"] == []


def test_verifier_still_rejects_unsafe_claims():
    bundle = pilot.build_pilot_proof_bundle("finance_capital_hilton_payment_watch")
    candidate = pilot.mock_lm_style_candidate_response(bundle)
    candidate["draft_body"] = "The invoice has been paid. I will update the ledger."
    run = pilot.run_pilot_scenario("finance_capital_hilton_payment_watch", candidate_response=candidate, generated_at=FIXED_NOW)

    assert run["published_response"]["verification_status"] == "fallback"
    assert "unsupported_completion_claim" in run["fallback_reason"]
    assert "protected_action_promise:ledger_mutation" in run["fallback_reason"]
    assert "has been paid" not in run["published_response"]["body"].lower()


def test_builder_redaction_status_export_bridge_and_unsafe_scan(tmp_path):
    result = bundles.export_redaction_integration_status(
        read_model_root=ROOT / "generated/read_models",
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Proof Bundle Builder Redaction Integration.md",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))

    assert result["status"] == bundles.REDACTION_READY_STATUS
    assert local == bridge
    assert local["machine_proof"]["unsafe_true_grants_absent"] is True
    assert Path(result["wiki_path"]).read_text(encoding="utf-8").startswith("# Proof Bundle Builder Redaction Integration")
