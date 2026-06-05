import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import proof_meter_normalization as meters


FIXED_NOW = "2026-06-05T18:00:00+00:00"


def _read_model():
    return meters.build_read_model(generated_at=FIXED_NOW)


def _card_set(read_model, card_id):
    for card_set in read_model["card_meter_sets"]:
        if card_set["card_id"] == card_id:
            return card_set
    raise AssertionError(f"missing card set: {card_id}")


def _meter(card_set, meter_ref):
    return card_set["meter_map"][meter_ref]


def test_capital_hilton_payment_watch_meters_are_current_no_grant_watch():
    card = _card_set(_read_model(), "dynamic_card.finance.capital_hilton.payment_watch")

    assert _meter(card, "truth")["meter_state"] == "trusted_current"
    assert _meter(card, "freshness")["meter_state"] == "current"
    assert _meter(card, "authority")["meter_state"] == "no_grant"
    assert _meter(card, "risk")["meter_state"] == "watch"
    assert _meter(card, "risk")["opens_details"] is True


def test_live_arts_payment_evidence_is_operator_reported_candidate_not_paid():
    card = _card_set(_read_model(), "dynamic_card.finance.live_arts_md.evidence_intake.payment_processing")

    assert _meter(card, "truth")["meter_state"] == "operator_reported"
    assert _meter(card, "evidence")["meter_state"] == "operator_reported"
    assert _meter(card, "freshness")["meter_state"] == "waiting_external"
    assert _meter(card, "risk")["meter_state"] == "watch"
    for meter in card["meters"]:
        assert "Payment-processing evidence means paid." in _meter(card, "truth")["must_never_imply"]
        assert "Paid, sent, or ledger state changed." in _meter(card, "evidence")["must_never_imply"]


def test_review_packet_informational_meters_are_historical_resolved():
    card = _card_set(_read_model(), "dynamic_card.build.review_packet.completed_historical_receipt")

    assert _meter(card, "freshness")["meter_state"] == "historical"
    assert _meter(card, "truth")["meter_state"] in {"receipt_backed", "trusted_current"}
    assert _meter(card, "risk")["meter_state"] == "calm"
    assert _meter(card, "freshness")["opens_details"] is True


def test_gate_lock_meters_are_blocked_and_protected():
    read_model = _read_model()
    gate_lock = _card_set(read_model, "dynamic_card.system.check_engine.diagnostic")
    approval_gate = _card_set(read_model, "dynamic_card.finance.capital_hilton.approval_request.coupa_submit")

    assert _meter(gate_lock, "authority")["meter_state"] == "blocked_gate"
    assert _meter(gate_lock, "risk")["meter_state"] == "blocked"
    assert _meter(approval_gate, "authority")["meter_state"] == "blocked_gate"
    assert _meter(approval_gate, "risk")["meter_state"] == "protected"


def test_missing_source_becomes_needs_verification(tmp_path):
    card = {
        "card_id": "dynamic_card.test.missing_source",
        "card_family": "answer_card",
        "card_type": "answer",
        "headline": "Missing source",
        "plain_summary": "No backing source is available.",
        "supporting_lines": [],
        "status_label": "Ready",
        "tone": "calm",
        "trust_state": "trusted_current",
        "confidence_class": "high",
        "freshness_state": "current",
        "lifecycle_state": "active",
        "source_read_model_refs": ["generated/read_models/missing_source.json"],
        "action_slots": {},
        "proof": {},
    }
    card_set = meters.build_card_meter_set(card, read_model_root=tmp_path)

    assert card_set["missing_source_refs"] == ["generated/read_models/missing_source.json"]
    assert _meter(card_set, "truth")["meter_state"] == "needs_verification"
    assert _meter(card_set, "freshness")["meter_state"] == "needs_verification"
    assert _meter(card_set, "authority")["meter_state"] == "needs_verification"


def test_read_model_validation_and_unsafe_scan_clean():
    read_model = _read_model()

    assert read_model["status"] == meters.READY_STATUS
    assert read_model["card_count"] >= 1
    assert read_model["meter_count"] == read_model["card_count"] * len(meters.METER_REFS)
    assert read_model["machine_proof"]["meter_validation_errors"] == []
    assert meters.unsafe_true_grants(read_model) == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True
    for meter in read_model["meters"]:
        assert meters.validate_meter(meter) == []


def test_export_json_round_trips(tmp_path):
    bridge_root = tmp_path / "bridge"
    result = meters.export_proof_meter_normalization(
        export_root=tmp_path / "read_models",
        bridge_export_root=bridge_root,
        wiki_path=tmp_path / "Proof Meter Normalization.md",
        generated_at=FIXED_NOW,
    )
    local_payload = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge_payload = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))

    assert result["status"] == meters.READY_STATUS
    assert local_payload == bridge_payload
    assert local_payload["meter_count"] == local_payload["card_count"] * 6
