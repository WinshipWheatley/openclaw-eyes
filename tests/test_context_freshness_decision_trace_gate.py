import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import context_freshness_decision_trace_gate as gate


FIXED_NOW = "2026-06-07T09:25:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    statuses = {
        "proof_bundle_redaction_policy.json": "PROOF_BUNDLE_REDACTION_HARDENING_READY",
        "proof_bundle_builder_redaction_status.json": "PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY",
        "proof_to_response_runtime_status.json": "PROOF_TO_RESPONSE_RUNTIME_READY",
        "universal_receipt_envelope_status.json": "UNIVERSAL_RECEIPT_ENVELOPE_READY",
        "operator_session_timeline.json": "OPERATOR_SESSION_TIMELINE_READY",
        "evidence_confidence_scoring.json": "EVIDENCE_CONFIDENCE_SCORING_READY",
        "dynamic_card_lifecycle_policy.json": "DYNAMIC_CARD_LIFECYCLE_POLICY_READY",
        "memory_promotion_gate.json": "MEMORY_PROMOTION_GATE_READY",
    }
    for filename, status in statuses.items():
        _write_json(root / filename, {"status": status})
    return root


def _read_model(tmp_path: Path) -> dict:
    return gate.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)


def _row(read_model: dict, context_ref: str) -> dict:
    return next(row for row in read_model["gate_rows"] if row["context_ref"] == context_ref)


def test_current_receipt_is_allowed_into_proof_bundle(tmp_path):
    read_model = _read_model(tmp_path)
    row = _row(read_model, "context:finance:capital_hilton:payment_watch")

    assert read_model["status"] == gate.READY_STATUS
    assert row["freshness_state"] == "current"
    assert row["latest_receipt_ref"] == "receipt:capital_hilton_payment_watch_current"
    assert row["allowed_for_lm_bundle"] is True
    assert row["lm_bundle_policy"]["may_enter_as_current_truth"] is True
    assert row["canonical_claims"]["ledger_state"] == "untouched"
    assert row["canonical_claims"]["payment_evidence"] == "missing"


def test_superseded_receipt_is_excluded_from_current_truth(tmp_path):
    row = _row(_read_model(tmp_path), "context:finance:capital_hilton:superseded_payment_source")

    assert row["freshness_state"] == "superseded"
    assert row["allowed_for_lm_bundle"] is False
    assert "receipt:capital_hilton_old_payment_watch" in row["superseded_receipt_refs"]
    assert row["required_refresh_action"] == "refresh_from_latest_receipt"
    assert "Needs verification" in row["safe_human_response_if_blocked"]


def test_generated_summary_cannot_override_receipt(tmp_path):
    row = _row(_read_model(tmp_path), "context:finance:capital_hilton:generated_summary_conflict")

    assert row["allowed_for_lm_bundle"] is True
    assert row["latest_receipt_ref"] == "receipt:capital_hilton_payment_watch_current"
    assert row["canonical_claims"]["payment_evidence"] == "missing"
    assert row["canonical_claims"]["ledger_state"] == "untouched"
    assert row["blocked_claims"][0]["claim_ref"] == "generated_summary_claim:capital_hilton_paid"
    assert "No payment receipt" in row["prior_rejections"][0]["rejection_reason"]
    assert row["lm_bundle_policy"]["must_not_override_receipts"] is True


def test_candidate_evidence_remains_candidate_not_paid_truth(tmp_path):
    row = _row(_read_model(tmp_path), "context:finance:live_arts_md:payment_evidence")

    assert row["allowed_for_lm_bundle"] is True
    assert row["confidence_class"] == "operator_reported_candidate"
    assert row["canonical_claims"]["payment_processing_evidence"] == "candidate"
    assert row["canonical_claims"]["paid_status"] == "not_proven"
    assert row["lm_bundle_policy"]["must_preserve_confidence_label"] is True


def test_test_only_evidence_blocked_as_primary_truth(tmp_path):
    row = _row(_read_model(tmp_path), "context:test_only:evidence_fixture")

    assert row["confidence_class"] == "test_only"
    assert row["allowed_for_lm_bundle"] is False
    assert row["required_refresh_action"] == "attach_live_receipt_backed_evidence"
    assert row["lm_bundle_policy"]["must_preserve_confidence_label"] is True
    assert "test-only" in row["decision_trace_summary"].lower()


def test_stale_context_returns_needs_verification(tmp_path):
    row = _row(_read_model(tmp_path), "context:system:stale_or_unknown_source")

    assert row["freshness_state"] == "stale"
    assert row["confidence_class"] == "unknown"
    assert row["allowed_for_lm_bundle"] is False
    assert row["latest_receipt_ref"] == ""
    assert row["safe_human_response_if_blocked"].startswith("Needs verification")
    assert row["required_refresh_action"] == "request_current_lane_context_or_receipt"


def test_prior_rejected_attempt_is_included_in_decision_trace(tmp_path):
    row = _row(_read_model(tmp_path), "context:finance:capital_hilton:payment_watch")
    rejection = row["prior_rejections"][0]

    assert rejection["attempt_ref"] == "attempt:capital_hilton_coupa_submit_without_payment_evidence"
    assert "Payment proof missing" in rejection["rejection_reason"]
    assert rejection["what_changed"]
    assert "gate:coupa_submit_protected_action" in row["decision_trace_refs"]


def test_unpromoted_memory_cannot_become_canonical_truth(tmp_path):
    row = _row(_read_model(tmp_path), "context:memory:unpromoted_operator_memory")

    assert row["confidence_class"] == "unpromoted_memory"
    assert row["allowed_for_lm_bundle"] is False
    assert row["receipt_refs"] == []
    assert row["required_refresh_action"] == "request_memory_promotion_or_current_receipt"
    assert "not been promoted" in row["stale_reason"]


def test_required_fields_present_for_every_gate_row(tmp_path):
    read_model = _read_model(tmp_path)
    required = {
        "context_ref",
        "world_ref",
        "thread_ref",
        "objective_ref",
        "source_refs",
        "receipt_refs",
        "decision_trace_refs",
        "latest_receipt_ref",
        "superseded_receipt_refs",
        "freshness_state",
        "confidence_class",
        "confidence_score",
        "decision_trace_summary",
        "prior_attempts",
        "prior_rejections",
        "operator_decisions",
        "allowed_for_lm_bundle",
        "safe_human_response_if_blocked",
    }

    for row in read_model["gate_rows"]:
        assert required <= set(row)
        assert row["freshness_state"] in gate.FRESHNESS_STATES


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _read_model(tmp_path)

    assert gate.unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_and_wiki(tmp_path):
    result = gate.export_context_freshness_decision_trace_gate(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Context Freshness Decision Trace Gate.md",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == gate.READY_STATUS
    assert result["contexts_total"] == str(len(local["gate_rows"]))
    assert local == bridge
    assert gate.unsafe_true_grants(local) == []
    assert wiki.startswith("# Context Freshness Decision Trace Gate")
