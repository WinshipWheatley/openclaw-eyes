import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import dynamic_card_lifecycle_policy as lifecycle
import dynamic_card_packet


FIXED_NOW = "2026-06-04T22:15:00+00:00"


def _base_card(**overrides):
    card = {
        "card_id": "dynamic_card.example",
        "card_type": "status",
        "status_label": "Current",
        "trust_state": "trusted_current",
        "visible_by_default": True,
        "authority_boundary": dict(lifecycle.AUTHORITY_BOUNDARY),
    }
    card.update(overrides)
    return card


def test_resolved_review_packet_is_hidden_by_default():
    card = lifecycle.apply_lifecycle_policy(
        _base_card(
            card_id="dynamic_card.build.review_packet.current",
            card_type="review_packet",
            status_label="Review recorded",
            visible_by_default=False,
        )
    )

    assert card["lifecycle_state"] == "resolved"
    assert card["freshness_state"] == "historical"
    assert card["visible_by_default"] is False
    assert card["collapse_when_resolved"] is True
    assert card["resolved_by_receipt_ref"] == "generated/read_models/workroom_review_decision_status.json"
    assert lifecycle.validate_card_lifecycle(card) == []


def test_active_payment_watch_remains_visible():
    card = lifecycle.apply_lifecycle_policy(
        _base_card(
            card_id="dynamic_card.finance.capital_hilton.payment_watch",
            card_type="payment_watch",
            status_label="Payment watch",
            visible_by_default=True,
        )
    )

    assert card["lifecycle_state"] == "active"
    assert card["freshness_state"] == "current"
    assert card["visible_by_default"] is True
    assert card["collapse_when_resolved"] is False
    assert lifecycle.validate_card_lifecycle(card) == []


def test_payment_proof_candidate_becomes_waiting_not_paid():
    card = lifecycle.apply_lifecycle_policy(
        _base_card(
            card_id="dynamic_card.finance.live_arts_md.evidence_intake.payment_processing",
            card_type="evidence_intake",
            status_label="Processing evidence",
            trust_state="operator_reported",
            visible_by_default=True,
        )
    )

    assert card["lifecycle_state"] == "waiting"
    assert card["freshness_state"] == "waiting_on_external"
    assert card["authority_boundary"]["paid"] is False
    assert card["authority_boundary"]["paid_marking_allowed"] is False
    assert lifecycle.validate_card_lifecycle(card) == []


def test_historical_workroom_posts_are_collapsed():
    card = lifecycle.apply_lifecycle_policy(
        _base_card(
            card_id="dynamic_card.finance.st_annes.work_log_review",
            card_type="status",
            status_label="No active blocker",
            visible_by_default=False,
        )
    )

    assert card["lifecycle_state"] == "resolved"
    assert card["freshness_state"] == "historical"
    assert card["visible_by_default"] is False
    assert card["collapse_when_resolved"] is True
    assert lifecycle.validate_card_lifecycle(card) == []


def test_stale_card_says_needs_verification():
    card = lifecycle.apply_lifecycle_policy(
        _base_card(
            card_id="dynamic_card.finance.example.stale",
            status_label="Unknown",
            trust_state="stale_needs_proof",
        )
    )

    assert card["lifecycle_state"] == "stale"
    assert card["freshness_state"] == "needs_verification"
    assert card["status_label"] == "Needs verification"
    assert card["stale_reason"] == "Needs verification"
    assert lifecycle.validate_card_lifecycle(card) == []


def test_proof_only_card_hidden_by_default():
    card = lifecycle.apply_lifecycle_policy(
        _base_card(
            card_id="dynamic_card.artifact.proof_only",
            card_type="artifact",
            status_label="Proof",
            visible_by_default=True,
        )
    )

    assert card["lifecycle_state"] == "archived"
    assert card["freshness_state"] == "historical"
    assert card["visible_by_default"] is False
    assert card["primary_control_ref"] == ""
    assert lifecycle.validate_card_lifecycle(card) == []


def test_dynamic_card_packet_validates_lifecycle_fields():
    packet = dynamic_card_packet.build_latest_packet(generated_at=FIXED_NOW)
    action_index = dynamic_card_packet._action_index(dynamic_card_packet._source_payloads()["operator_action_payloads"])
    validation = dynamic_card_packet.validate_packet(packet, action_index)

    assert validation["valid"] is True
    assert validation["lifecycle_fields_present"] is True
    assert packet["machine_proof"]["lifecycle_fields_present"] is True
    assert all(
        all(field in card for field in lifecycle.REQUIRED_CARD_FIELDS)
        for card in packet["cards"]
    )


def test_export_writes_json_bridge_and_wiki(tmp_path):
    result = lifecycle.export_dynamic_card_lifecycle_policy(
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Dynamic Card Lifecycle Policy.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))

    assert local == bridge
    assert local["read_model_id"] == "dynamic_card_lifecycle_policy"
    assert local["machine_proof"]["example_cards_valid"] is True
    assert local["machine_proof"]["unsafe_true_grants_absent"] is True
    assert Path(result["wiki_path"]).exists()


def test_unsafe_true_grant_scan_clean():
    read_model = lifecycle.build_read_model(generated_at=FIXED_NOW)
    packet = dynamic_card_packet.build_latest_packet(generated_at=FIXED_NOW)

    assert lifecycle.unsafe_true_grants(read_model) == []
    assert dynamic_card_packet.unsafe_true_grants(packet) == []
