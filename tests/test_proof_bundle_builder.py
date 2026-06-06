import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import proof_bundle_builder as bundles


def test_capital_hilton_bundle_includes_required_refs_and_controls():
    bundle = bundles.build_proof_bundle("finance_capital_hilton_payment_watch")

    assert bundle["proof_bundle_id"].startswith("proof_bundle:")
    assert bundle["world_ref"] == "finance"
    assert bundle["thread_ref"] == "capital_hilton"
    assert bundle["selected_card_ref"] == "dynamic_card.finance.capital_hilton.payment_watch"
    assert bundle["receipt_refs"]
    assert "generated/read_models/dynamic_card_packet_latest.json" in bundle["read_model_refs"]
    assert "generated/read_models/proof_meter_normalization.json" in bundle["proof_refs"]
    assert any(fact["fact_id"] == "payment_evidence_missing" for fact in bundle["known_facts"])
    assert any(control["label"] == "Attach proof" for control in bundle["allowed_response_controls"])
    assert bundles.validate_proof_bundle(bundle) == []


def test_bundle_excludes_raw_sensitive_details_and_verification_tokens():
    bundle = bundles.build_proof_bundle("finance_live_arts_payment_evidence")
    text = bundles.stable_json(bundle).lower()

    assert bundle["sensitive_detail_policy"] == "redacted_summary_only"
    assert bundle["privacy_class"] == "financial_sensitive/local_only"
    assert "raw_file_body" not in text
    assert "operator_envelope" not in text
    assert "device_verification" not in text
    assert "session_verification" not in text
    assert "secret" not in text
    assert "token" not in text


def test_unknown_context_bundle_is_bounded_and_has_missing_context_unknowns():
    bundle = bundles.build_proof_bundle("unknown_context")

    assert bundle["world_ref"] == "unknown"
    assert bundle["thread_ref"] == "unknown"
    assert bundle["unknowns"] == ["world_ref", "thread_ref"]
    assert bundle["blocked_actions"]
    assert all(not control["enabled"] or control["controller_event_type"] in {"open_lane", "stop_hold_cancel"} for control in bundle["allowed_response_controls"])
    assert bundles.validate_proof_bundle(bundle) == []


def test_bundle_rejects_unknown_scenario():
    try:
        bundles.build_proof_bundle("not_a_real_scenario")
    except ValueError as exc:
        assert "unknown_scenario" in str(exc)
    else:
        raise AssertionError("unknown scenario did not fail")
