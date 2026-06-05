import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import controller_knob_mode_filters as filters


FIXED_NOW = "2026-06-05T19:00:00+00:00"


def _inputs():
    packet = json.loads(Path("generated/read_models/dynamic_card_packet_latest.json").read_text(encoding="utf-8"))
    proof = json.loads(Path("generated/read_models/proof_meter_normalization.json").read_text(encoding="utf-8"))
    return packet["cards"], proof


def _read_model():
    return filters.build_read_model(generated_at=FIXED_NOW)


def test_moment_zoom_shows_one_current_focus_card():
    read_model = _read_model()
    moment = read_model["filter_profiles"]["moment_default"]

    assert moment["knob_state"]["zoom_level"] == "moment"
    assert moment["visible_card_count"] == 1
    assert moment["visible_card_ids"] == ["dynamic_card.finance.capital_hilton.workbook_registration"]


def test_system_zoom_can_show_wip_and_meters_but_not_machine_contracts_by_default():
    read_model = _read_model()
    system = read_model["filter_profiles"]["system_zoom"]

    assert system["knob_state"]["zoom_level"] == "system"
    assert "dynamic_card.system.check_engine.diagnostic" in system["visible_card_ids"]
    assert system["proof_policy"]["visible_meter_refs"] == ["truth", "freshness", "authority", "risk"]
    assert system["machine_contract_card_ids"] == []
    assert system["machine_contract_cards_visible_by_default"] is False


def test_delegation_depth_does_not_grant_authority():
    cards, proof = _inputs()
    for depth in filters.DELEGATION_DEPTHS:
        profile = filters.evaluate_knobs(cards, proof, {"delegation_depth": depth, "zoom_level": "system"})
        policy = profile["delegation_policy"]

        assert policy["protected_authority_granted"] is False
        assert all(value is False for value in policy["authority_boundary"].values())
        assert all(value is False for value in profile["authority_boundary"].values())
    blocked = filters.evaluate_knobs(
        cards,
        proof,
        {"delegation_depth": "execute_after_approval_blocked", "zoom_level": "system"},
    )
    assert blocked["delegation_policy"]["execute_after_approval_blocked"] is True
    assert blocked["delegation_policy"]["execute_after_approval_enabled"] is False


def test_proof_depth_controls_proof_visibility_only():
    read_model = _read_model()
    profiles = read_model["filter_profiles"]
    card_sets = {
        "none": profiles["proof_none"]["visible_card_ids"],
        "summary": profiles["proof_summary"]["visible_card_ids"],
        "receipts": profiles["proof_receipts"]["visible_card_ids"],
        "full": profiles["proof_full_developer"]["visible_card_ids"],
    }

    assert card_sets["none"] == card_sets["summary"] == card_sets["receipts"] == card_sets["full"]
    assert profiles["proof_none"]["proof_policy"]["visible_meter_refs"] == []
    assert profiles["proof_summary"]["proof_policy"]["developer_proof_visible"] is False
    assert profiles["proof_receipts"]["proof_policy"]["receipt_refs_visible"] is True
    assert profiles["proof_full_developer"]["proof_policy"]["developer_proof_visible"] is True
    assert profiles["proof_full_developer"]["proof_policy"]["requires_explicit_opt_in"] is True


def test_artist_mode_suppresses_noncritical_business_watch_cards():
    read_model = _read_model()
    artist = read_model["filter_profiles"]["artist_normal"]

    assert "dynamic_card.finance.capital_hilton.payment_watch" not in artist["visible_card_ids"]
    assert "dynamic_card.business_development.capital_hilton.proposal" not in artist["visible_card_ids"]
    assert "dynamic_card.system.check_engine.diagnostic" in artist["visible_card_ids"]


def test_urgent_does_not_bypass_gates():
    read_model = _read_model()
    urgent = read_model["filter_profiles"]["urgent_finance"]

    assert urgent["knob_state"]["urgency"] == "urgent"
    assert urgent["machine_proof"]["urgent_bypasses_gates"] is False
    assert all(value is False for value in urgent["authority_boundary"].values())
    assert "dynamic_card.finance.capital_hilton.approval_request.coupa_submit" in urgent["visible_card_ids"]
    assert urgent["delegation_policy"]["execute_after_approval_enabled"] is False


def test_unsafe_scan_clean():
    read_model = _read_model()

    assert read_model["status"] == filters.READY_STATUS
    assert read_model["machine_proof"]["validation_errors"] == []
    assert filters.unsafe_true_grants(read_model) == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True
