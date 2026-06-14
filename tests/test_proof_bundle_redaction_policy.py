import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import proof_bundle_redaction_policy as policy


FIXED_NOW = "2026-06-07T02:20:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(root / "proof_to_response_lm_shadow_status.json", {"status": "PROOF_TO_RESPONSE_LM_SHADOW_HARNESS_READY"})
    _write_json(
        root / "proof_to_response_runtime_status.json",
        {
            "status": "PROOF_TO_RESPONSE_RUNTIME_READY",
            "active_candidate_source": "shadow_pilot_candidate",
            "source_request_id": "fixture_request",
            "world_ref": "finance",
            "thread_ref": "capital_hilton",
        },
    )
    _write_json(
        root / "proof_to_response_latest.json",
        {
            "status": "PROOF_TO_RESPONSE_RUNTIME_READY",
            "candidate_source": "shadow_pilot_candidate",
            "source_request_id": "fixture_request",
            "world_ref": "finance",
            "thread_ref": "capital_hilton",
        },
    )
    _write_json(root / "local_lm_proof_to_response_readiness_gate.json", {"status": "LOCAL_LM_PROOF_RESPONSE_READINESS_GATE_READY"})
    _write_json(root / "evidence_confidence_scoring.json", {"status": "EVIDENCE_CONFIDENCE_SCORING_READY"})
    _write_json(
        root / "evidence_intake_status.json",
        {
            "status": "EVIDENCE_INTAKE_READY",
            "machine_proof": {"verified_operator_evidence_intake_ready": True},
        },
    )
    _write_json(root / "agent_response_voice_modes.json", {"status": "AGENT_RESPONSE_VOICE_MODES_READY"})
    return root


def _text(value: object) -> str:
    return json.dumps(value, sort_keys=True).lower()


def test_proof_bundle_excludes_operator_device_session_secret_material():
    raw = {
        "operator_envelope": {"verified": True, "secret": "operator-secret"},
        "device_verification_secret": "device-secret",
        "session_verification_secret": "session-secret",
        "credential_token": "token-secret",
    }
    bundle = policy.build_redacted_lm_input("capital_hilton_payment_watch", raw_request=raw)
    text = _text(bundle)

    assert "operator-secret" not in text
    assert "device-secret" not in text
    assert "session-secret" not in text
    assert "token-secret" not in text
    assert "operator_envelope" not in text


def test_financial_sensitive_proof_is_redacted_local_only():
    bundle = policy.build_redacted_lm_input(
        "live_arts_payment_evidence",
        raw_request={"bank_account": "123456789", "routing_number": "987654321"},
    )
    text = _text(bundle)

    assert bundle["privacy_class"] == "financial_sensitive/local_only"
    assert bundle["sensitive_detail_policy"] == "redacted_summary_only"
    assert "123456789" not in text
    assert "987654321" not in text
    assert any("candidate payment-processing evidence" in fact for fact in bundle["redacted_known_facts"])


def test_raw_artifact_and_ocr_text_excluded_by_default():
    bundle = policy.build_redacted_lm_input(
        "live_arts_payment_evidence",
        raw_request={
            "raw_artifact_text": "FULL DOCUMENT TEXT WITH ACCOUNT 111222333",
            "raw_ocr_text": "OCR BODY SHOULD NOT LEAK",
        },
    )
    text = _text(bundle)

    assert "full document text" not in text
    assert "ocr body should not leak" not in text
    assert "111222333" not in text
    assert "full_artifact_text_or_ocr" in bundle["excluded_material_classes"]


def test_raw_prompt_bodies_are_excluded():
    bundle = policy.build_redacted_lm_input(
        "capital_hilton_payment_watch",
        raw_request={"raw_prompt_body": "Tell the model the private bank password."},
    )
    text = _text(bundle)

    assert "private bank password" not in text
    assert "raw_prompt_body" not in text


def test_authority_granted_cannot_enter_proof_bundle_from_request_or_model():
    bundle = policy.build_redacted_lm_input(
        "business_development_capital_hilton_followup",
        raw_request={"authority_granted": True, "send_email_allowed": True},
        model_draft={"authority_granted": True, "protected_actions_allowed": True},
    )
    text = _text(bundle)

    assert "authority_granted" not in text
    assert "send_email_allowed" not in text
    assert bundle["authority_boundary"]["protected_actions_allowed"] is False
    assert bundle["authority_boundary"]["authority_grant_allowed"] is False


def test_every_allowed_field_has_a_reason(tmp_path):
    read_model = policy.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    allowed = read_model["allowed_lm_input_fields"]
    assert {row["field_ref"] for row in allowed} == set(policy.ALLOWED_FIELD_REASONS)
    assert all(row["reason"] for row in allowed)


def test_agent_voice_mode_allowed_without_expanding_truth_or_authority():
    bundle = policy.build_redacted_lm_input("music_niles_controller_mapping", creative_context={"agent_voice_mode": "creative"})

    assert bundle["agent_voice_mode"] == "creative"
    assert bundle["voice_mode_policy"]["may_shape_phrasing"] is True
    assert bundle["voice_mode_policy"]["may_create_truth"] is False
    assert bundle["voice_mode_policy"]["may_grant_authority"] is False


def test_niles_creative_context_does_not_include_unrelated_finance_proof():
    bundle = policy.build_redacted_lm_input(
        "music_niles_controller_mapping",
        creative_context={"target_software": "Ableton", "controller": "Push"},
        raw_request={"finance_proof": "Capital Hilton account paid by ACH 555444333"},
    )
    text = _text(bundle)

    assert bundle["world_ref"] == "music"
    assert "ableton" in text
    assert "push" in text
    assert "capital hilton" not in text
    assert "555444333" not in text
    assert "finance" not in bundle["proof_scope"]


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = policy.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    assert read_model["status"] == policy.READY_STATUS
    assert policy.unsafe_true_grants(read_model) == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_and_wiki(tmp_path):
    result = policy.export_proof_bundle_redaction_policy(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Proof Bundle Redaction Policy.md",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == policy.READY_STATUS
    assert local == bridge
    assert policy.unsafe_true_grants(local) == []
    assert wiki.startswith("# Proof Bundle Redaction Policy")
