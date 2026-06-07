import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import context_freshness_decision_trace_gate as freshness_gate
import proof_bundle_builder as bundles
import proof_to_response_runtime as runtime


FIXED_NOW = "2026-06-07T11:10:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    statuses = {
        "proof_bundle_redaction_policy.json": "PROOF_BUNDLE_REDACTION_HARDENING_READY",
        "proof_bundle_builder_redaction_status.json": "PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY",
        "proof_to_response_runtime_status.json": runtime.READY_STATUS,
        "proof_to_response_lm_shadow_status.json": "PROOF_TO_RESPONSE_LM_SHADOW_HARNESS_READY",
        "universal_receipt_envelope_status.json": "UNIVERSAL_RECEIPT_ENVELOPE_READY",
        "operator_session_timeline.json": "OPERATOR_SESSION_TIMELINE_READY",
        "evidence_confidence_scoring.json": "EVIDENCE_CONFIDENCE_SCORING_READY",
        "dynamic_card_lifecycle_policy.json": "DYNAMIC_CARD_LIFECYCLE_POLICY_READY",
        "memory_promotion_gate.json": "MEMORY_PROMOTION_GATE_READY",
    }
    for filename, status in statuses.items():
        payload = {"status": status}
        if filename == "proof_to_response_runtime_status.json":
            payload.update(
                {
                    "active_candidate_source": runtime.CANDIDATE_SOURCE_SHADOW_PILOT,
                    "source_request_id": "fixture_request",
                    "world_ref": "finance",
                    "thread_ref": "capital_hilton",
                }
            )
        _write_json(root / filename, payload)
    gate = freshness_gate.build_read_model(read_model_root=root, generated_at=FIXED_NOW)
    _write_json(root / "context_freshness_decision_trace_gate.json", gate)
    return root


def _text(value: object) -> str:
    return json.dumps(value, sort_keys=True).lower()


def test_current_context_enters_proof_bundle_with_freshness_current(tmp_path):
    bundle = bundles.build_redacted_proof_bundle(
        "finance_capital_hilton_payment_watch",
        read_model_root=_fixture_root(tmp_path),
    )

    assert bundle["freshness_state"] == "current"
    assert bundle["confidence_class"] == "receipt_backed"
    assert bundle["trusted_current"] is True
    assert bundle["proof_bundle_status"] == "trusted_current"
    assert bundle["latest_receipt_ref"] == "receipt:capital_hilton_payment_watch_current"
    assert "payment evidence is missing" in _text(bundle["lm_input"])
    assert "gate:coupa_submit_protected_action" in bundle["decision_trace_refs"]


def test_stale_context_blocks_trusted_current_bundle(tmp_path):
    bundle = bundles.build_redacted_proof_bundle(
        "unknown_context",
        read_model_root=_fixture_root(tmp_path),
    )

    assert bundle["freshness_state"] == "stale"
    assert bundle["trusted_current"] is False
    assert bundle["allowed_for_lm_bundle"] is False
    assert bundle["proof_bundle_status"] == "blocked_needs_verification"
    assert bundle["lm_input"]["redacted_known_facts"][0].startswith("Needs verification")
    assert bundle["lm_input"]["missing_input"] == ["request_current_lane_context_or_receipt"]


def test_superseded_receipt_excluded_from_current_known_facts(tmp_path):
    bundle = bundles.build_redacted_proof_bundle(
        "finance_capital_hilton_payment_watch",
        read_model_root=_fixture_root(tmp_path),
        context_ref="context:finance:capital_hilton:superseded_payment_source",
    )
    text = _text(bundle["lm_input"])

    assert bundle["freshness_state"] == "superseded"
    assert bundle["trusted_current"] is False
    assert bundle["proof_bundle_status"] == "blocked_needs_verification"
    assert "receipt:capital_hilton_old_payment_watch" in bundle["superseded_receipt_refs"]
    assert "receipt:capital_hilton_old_payment_watch" not in bundle["lm_input"]["receipt_refs"]
    assert "coupa is processing" not in text
    assert "needs verification" in text


def test_candidate_evidence_labeled_candidate(tmp_path):
    bundle = bundles.build_redacted_proof_bundle(
        "finance_live_arts_payment_evidence",
        read_model_root=_fixture_root(tmp_path),
    )
    text = _text(bundle["lm_input"])

    assert bundle["freshness_state"] == "current"
    assert bundle["confidence_class"] == "operator_reported_candidate"
    assert bundle["canonical_claims"]["paid_status"] == "not_proven"
    assert "candidate payment-processing evidence" in text
    assert "does not mark the invoice paid" in text


def test_test_only_evidence_blocked_as_primary_truth(tmp_path):
    bundle = bundles.build_redacted_proof_bundle(
        "finance_live_arts_payment_evidence",
        read_model_root=_fixture_root(tmp_path),
        context_ref="context:test_only:evidence_fixture",
    )

    assert bundle["confidence_class"] == "test_only"
    assert bundle["trusted_current"] is False
    assert bundle["proof_bundle_status"] == "blocked_needs_verification"
    assert bundle["required_refresh_action"] == "attach_live_receipt_backed_evidence"
    assert bundle["lm_input"]["redacted_known_facts"][0].startswith("Needs verification")


def test_prior_rejection_appears_in_decision_trace(tmp_path):
    bundle = bundles.build_redacted_proof_bundle(
        "finance_capital_hilton_payment_watch",
        read_model_root=_fixture_root(tmp_path),
    )
    rejection = bundle["prior_rejections"][0]

    assert rejection["attempt_ref"] == "attempt:capital_hilton_coupa_submit_without_payment_evidence"
    assert "Payment proof missing" in rejection["rejection_reason"]
    assert rejection["what_changed"]
    assert bundle["decision_trace_summary"]


def test_unpromoted_memory_not_canonical(tmp_path):
    bundle = bundles.build_redacted_proof_bundle(
        "unknown_context",
        read_model_root=_fixture_root(tmp_path),
        context_ref="context:memory:unpromoted_operator_memory",
    )

    assert bundle["confidence_class"] == "unpromoted_memory"
    assert bundle["trusted_current"] is False
    assert bundle["allowed_for_lm_bundle"] is False
    assert bundle["proof_bundle_status"] == "blocked_needs_verification"
    assert "not been promoted" in bundle["stale_reason"]


def test_generated_summary_does_not_override_current_receipt(tmp_path):
    bundle = bundles.build_redacted_proof_bundle(
        "finance_capital_hilton_payment_watch",
        read_model_root=_fixture_root(tmp_path),
        context_ref="context:finance:capital_hilton:generated_summary_conflict",
    )
    text = _text(bundle)

    assert bundle["trusted_current"] is True
    assert bundle["canonical_claims"]["payment_evidence"] == "missing"
    assert bundle["canonical_claims"]["ledger_state"] == "untouched"
    assert bundle["blocked_claims"][0]["claim_ref"] == "generated_summary_claim:capital_hilton_paid"
    assert "generated_summary_claim:capital_hilton_paid" in text


def test_redaction_still_excludes_forbidden_fields(tmp_path):
    bundle = bundles.build_redacted_proof_bundle(
        "finance_capital_hilton_payment_watch",
        read_model_root=_fixture_root(tmp_path),
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
    assert bundle["authority_boundary"]["protected_actions_allowed"] is False
    assert bundles.validate_redacted_proof_bundle(bundle) == []


def test_freshness_trace_status_export_bridge_and_unsafe_scan(tmp_path):
    result = bundles.export_freshness_trace_status(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Proof Bundle Freshness Trace Integration.md",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))

    assert result["status"] == bundles.FRESHNESS_TRACE_READY_STATUS
    assert local == bridge
    assert bundles._unsafe_true_grants(local) == []
    assert local["machine_proof"]["stale_and_superseded_context_blocked"] is True
    assert local["machine_proof"]["candidate_evidence_labeled_candidate"] is True
    assert local["machine_proof"]["test_only_evidence_blocked"] is True
    assert local["machine_proof"]["unpromoted_memory_blocked"] is True
    assert Path(result["wiki_path"]).read_text(encoding="utf-8").startswith("# Proof Bundle Freshness Trace Integration")
