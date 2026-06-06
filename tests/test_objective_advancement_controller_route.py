import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

import operator_controller_event_router as router
from test_operator_controller_event_router import _event_request, _route, _unsafe_true_grants


def _assert_protected_actions_false(receipt: dict) -> None:
    proof = receipt["machine_proof"]
    for key in (
        "ledger_mutation_performed",
        "paid_marking_performed",
        "coupa_access_performed",
        "browser_access_performed",
        "submit_performed",
        "merge_performed",
        "git_push_performed",
        "business_action_performed",
        "external_llm_invoked",
        "local_model_runtime_connected",
    ):
        assert proof[key] is False
    assert receipt["authority_granted"] == []
    assert all(value is False for value in receipt["authority_boundary"].values())
    assert not _unsafe_true_grants(receipt)


def test_finance_capital_hilton_advance_returns_payment_evidence_needed(tmp_path):
    receipt = _route(
        tmp_path,
        _event_request(
            event_type="advance_objective",
            world="finance",
            thread="capital_hilton",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
            operator_text="Advance this.",
        ),
    )

    assert receipt["raw_internal_status"] == router.RESPONSE_READY
    assert receipt["backend_route"] == "objective_advancement_protocol.advance_objective"
    assert receipt["route_status"] == "NEEDS_PROOF"
    assert receipt["route_result"]["next_safe_state"] == "REQUEST_PAYMENT_EVIDENCE"
    assert receipt["route_result"]["suggested_controller_event"] == "attach_proof"
    assert receipt["dynamic_card_response"]["headline"] == "Payment evidence needed"
    assert receipt["dynamic_card_response"]["plain_summary"] == (
        "I can't complete payment yet. Attach payment evidence before anything touches the ledger."
    )
    assert receipt["dynamic_card_response"]["next_safe_action"] == "Attach payment evidence."
    assert receipt["dynamic_card_response"]["action_slots"][0]["controller_event_type"] == "attach_proof"
    assert receipt["dynamic_card_response"]["proof"]["collapsed_by_default"] is True
    _assert_protected_actions_false(receipt)


def test_capital_hilton_advancement_does_not_mark_paid_or_mutate_ledger(tmp_path):
    receipt = _route(
        tmp_path,
        _event_request(
            event_type="advance_objective",
            world="finance",
            thread="capital_hilton",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
        ),
    )

    assert receipt["route_result"]["current_state"]["paid"] is False
    assert receipt["route_result"]["current_state"]["ledger_untouched"] is True
    assert receipt["route_result"]["protected_final_action"] == "ledger_post_or_mark_paid"
    _assert_protected_actions_false(receipt)


def test_live_arts_evidence_advancement_waits_for_confirmation_not_paid(tmp_path):
    request = _event_request(
        event_type="advance_objective",
        world="finance",
        thread="live_arts_md",
        selected_card_id="dynamic_card.finance.live_arts_md.evidence_intake.payment_processing",
        operator_text="Advance this proof.",
        artifact_ref="mission_control_drop:live_arts_md_payment_processing_screenshot",
    )
    receipt = _route(tmp_path, request)

    assert receipt["raw_internal_status"] == router.RESPONSE_READY
    assert receipt["route_result"]["next_safe_state"] == "EVIDENCE_RECORDED_WAITING_FOR_CONFIRMATION"
    assert "Ledger remains untouched" in receipt["route_result"]["operator_response"]
    assert receipt["route_result"]["current_state"]["paid"] is False
    _assert_protected_actions_false(receipt)


def test_business_development_advance_stages_followup_only_no_send(tmp_path):
    receipt = _route(
        tmp_path,
        _event_request(
            event_type="advance_objective",
            world="business_development",
            thread="capital_hilton",
            selected_action_id="capital_hilton.proposal.stage_followup",
            operator_text="Prepare next step.",
        ),
    )

    assert receipt["route_result"]["next_safe_state"] == "FOLLOWUP_DRAFT_STAGED"
    assert receipt["route_result"]["protected_final_action"] == "email_send"
    assert "will not send" in receipt["route_result"]["operator_response"]
    _assert_protected_actions_false(receipt)


def test_build_review_advance_does_not_merge_or_push(tmp_path):
    receipt = _route(
        tmp_path,
        _event_request(
            event_type="advance_objective",
            world="build",
            thread="build_openclaw_backend",
            selected_card_id="dynamic_card.build.review_packet.current",
            selected_action_id="review_packet.review_packet_c4ec166103f9aa35.mark_review_packet_informational",
            operator_text="Advance this review packet.",
        ),
    )

    assert receipt["route_result"]["next_safe_state"] == "REVIEW_DECISION_READY_TO_RECORD"
    assert receipt["route_result"]["review_packet_id"] == "review_packet:c4ec166103f9aa35"
    assert receipt["route_result"]["protected_final_action"] == "merge_or_git_push"
    _assert_protected_actions_false(receipt)


def test_unknown_context_fails_closed_with_needs_verification_card(tmp_path):
    receipt = _route(
        tmp_path,
        _event_request(
            event_type="advance_objective",
            world="unknown",
            thread="unknown",
            operator_text="Handle what you can.",
        ),
    )

    assert receipt["raw_internal_status"] == router.RESPONSE_READY
    assert receipt["route_status"] == "NEEDS_VERIFICATION"
    assert receipt["route_result"]["next_safe_state"] == "NEEDS_VERIFICATION"
    assert receipt["dynamic_card_response"]["headline"] == "Needs verification"
    assert "lane or objective" in receipt["route_result"]["operator_response"]
    _assert_protected_actions_false(receipt)


def test_selected_do_it_maps_to_objective_advancement_when_payload_permits(tmp_path):
    receipt = _route(
        tmp_path,
        _event_request(
            event_type="do_it",
            world="finance",
            thread="capital_hilton",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
            selected_action_id="capital_hilton.payment.open_finance",
            operator_text="Do it.",
        ),
    )

    assert receipt["backend_route"] == "objective_advancement_protocol.advance_objective"
    assert receipt["route_result"]["next_safe_state"] == "REQUEST_PAYMENT_EVIDENCE"
    assert receipt["route_result"]["suggested_controller_event"] == "attach_proof"
    _assert_protected_actions_false(receipt)


def test_class_a_approval_never_grants_protected_actions(tmp_path):
    request = _event_request(
        event_type="advance_objective",
        world="finance",
        thread="capital_hilton",
        selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
        extra_payload={"class_a_approved": True},
    )
    receipt = _route(tmp_path, request)

    scope = receipt["route_result"]["class_a_approval_scope"]
    assert scope["class_a_approval_present"] is True
    assert scope["requires_separate_future_gate_for_protected_actions"] is True
    assert receipt["route_result"]["class_a_approval_bypasses_guardian"] is False
    _assert_protected_actions_false(receipt)


def test_every_objective_advancement_emits_dynamic_card_compatible_output(tmp_path):
    receipt = _route(
        tmp_path,
        _event_request(
            event_type="continue",
            world="finance",
            thread="st_annes",
            operator_text="Continue.",
        ),
    )

    card = receipt["dynamic_card_response"]
    assert receipt["backend_route"] == "objective_advancement_protocol.advance_objective"
    assert card["schema_version"] == "dynamic_card_packet_v1"
    assert card["card_type"] == "objective_advancement"
    assert card["controller_event_type"] == "continue"
    assert card["action_slots"]
    assert card["proof"]["collapsed_by_default"] is True
    _assert_protected_actions_false(receipt)


def test_unsafe_true_grant_scan_clean_for_objective_route(tmp_path):
    receipt = _route(
        tmp_path,
        _event_request(
            event_type="advance_objective",
            world="business_development",
            thread="capital_hilton",
        ),
    )

    assert receipt["machine_proof"]["unsafe_true_grants_absent"] is True
    assert not _unsafe_true_grants(receipt)
