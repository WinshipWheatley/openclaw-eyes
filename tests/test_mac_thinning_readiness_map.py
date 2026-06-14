import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mac_thinning_readiness_map as thinning


FIXED_NOW = "2026-06-05T21:00:00+00:00"


def _read_model():
    return thinning.build_read_model(generated_at=FIXED_NOW)


def _surface(read_model, surface_ref):
    for surface in read_model["surface_readiness"]:
        if surface["surface_ref"] == surface_ref:
            return surface
    raise AssertionError(f"missing surface: {surface_ref}")


def test_shell_components_remain_bespoke():
    read_model = _read_model()
    for surface_ref in ("helm", "composer", "world_bank_switcher", "dynamic_card_renderer"):
        surface = _surface(read_model, surface_ref)
        assert surface["classification"] == "keep_bespoke"
        assert surface["surface_kind"] == "shell"
        assert surface["authority_boundary"]
        assert all(value is False for value in surface["authority_boundary"].values())


def test_capital_hilton_payment_watch_can_convert_to_dynamic_card():
    surface = _surface(_read_model(), "finance_capital_hilton")

    assert surface["classification"] == "convert_to_dynamic_card_now"
    assert "dynamic_card.finance.capital_hilton.payment_watch" in surface["backend_card_coverage"]["covered_card_ids"]
    assert surface["backend_card_coverage"]["status"] == "full"
    assert surface["proof_meter_coverage"]["status"] == "covered"
    assert surface["action_payload_coverage"]["status"] == "covered"
    assert surface["receipt_coverage"]["status"] == "covered"


def test_live_arts_evidence_receipt_can_convert_to_dynamic_card():
    surface = _surface(_read_model(), "finance_live_arts_md")

    assert surface["classification"] == "convert_to_dynamic_card_now"
    assert surface["backend_card_coverage"]["covered_card_ids"] == [
        "dynamic_card.finance.live_arts_md.evidence_intake.payment_processing"
    ]
    assert surface["controller_event_coverage"]["observed_controller_event_types"] == ["attach_proof"]
    assert surface["receipt_coverage"]["covered_receipt_types"] == ["evidence_recorded"]


def test_build_review_packet_can_convert_only_if_review_actions_covered():
    surface = _surface(_read_model(), "build_review_packets")
    payload_refs = surface["action_payload_coverage"]["covered_action_payload_refs"]

    assert surface["classification"] == "convert_to_dynamic_card_now"
    assert surface["backend_card_coverage"]["status"] == "full"
    assert any("approve_review_packet_for_record" in ref for ref in payload_refs)
    assert any("mark_review_packet_informational" in ref for ref in payload_refs)
    assert any("request_review_packet_rework" in ref for ref in payload_refs)
    assert surface["action_payload_coverage"]["all_payload_authority_boundaries_false"] is True


def test_protected_gate_surfaces_cannot_expose_execution():
    surface = _surface(_read_model(), "approval_gate_surfaces")

    assert surface["classification"] == "convert_to_dynamic_card_now"
    assert surface["machine_proof"]["protected_execution_exposed"] is False
    assert surface["action_payload_coverage"]["all_payload_authority_boundaries_false"] is True
    assert all(value is False for value in surface["authority_boundary"].values())
    assert "dynamic_card.finance.capital_hilton.approval_request.coupa_submit" in surface["backend_card_coverage"][
        "covered_card_ids"
    ]


def test_readiness_rules_do_not_remove_without_dynamic_coverage():
    read_model = _read_model()
    for surface in read_model["surface_readiness"]:
        if surface["classification"] == "remove_after_receipt_parity":
            assert surface["backend_card_coverage"]["coverage_exists"] is True
        if surface["classification"] in {"convert_to_dynamic_card_now", "convert_after_v1_parity"}:
            assert (
                surface["action_payload_coverage"]["covered_action_payload_refs"]
                or surface["receipt_coverage"]["covered_receipt_types"]
                or surface["surface_kind"] in {"shell", "shell_input"}
            )
            assert not surface["recommendation_errors"]


def test_unsafe_scan_clean():
    read_model = _read_model()

    assert read_model["status"] == thinning.READY_STATUS
    assert read_model["machine_proof"]["validation_errors"] == []
    assert thinning.unsafe_true_grants(read_model) == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True
