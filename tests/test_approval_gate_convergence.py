from pathlib import Path

import pytest

from approval_gate_convergence import (
    G3_GATE,
    convergence_for_surface,
    map_legacy_tier_to_g3,
)
from chief_compose import compose, execute_packet
from compose_contract import GateState


TEMP_DB = Path("/tmp/approval_gate_convergence_test.sqlite")


@pytest.fixture(autouse=True)
def clean_temp_db():
    try:
        TEMP_DB.unlink()
    except FileNotFoundError:
        pass
    yield
    try:
        TEMP_DB.unlink()
    except FileNotFoundError:
        pass


def test_legacy_approval_tiers_map_to_g3_states():
    tier_0 = map_legacy_tier_to_g3("tier_0")
    tier_1 = map_legacy_tier_to_g3("tier_1")
    tier_2 = map_legacy_tier_to_g3("tier_2")
    hard_tier_2 = map_legacy_tier_to_g3("hard_t2")

    assert tier_0["g3_gate_state"] == GateState.READ_ONLY.value
    assert tier_0["approval_required"] is False
    assert tier_1["g3_gate_state"] == GateState.PENDING_APPROVAL.value
    assert tier_1["approval_required"] is True
    assert tier_2["guardian_required"] is True
    assert hard_tier_2["non_overrideable"] is True
    for mapped in (tier_0, tier_1, tier_2, hard_tier_2):
        assert mapped["canonical_gate"] == G3_GATE
        assert mapped["execution_allowed"] is False


@pytest.mark.parametrize("surface", ["email_send", "sms_send", "approval_response"])
def test_legacy_send_and_approval_surfaces_converge_to_one_g3_gate(surface):
    convergence = convergence_for_surface(surface)

    assert convergence["canonical_gate"] == G3_GATE
    assert convergence["single_authoritative_gate"] == G3_GATE
    assert convergence["g3_gate_state"] == GateState.PENDING_APPROVAL.value
    assert convergence["double_gate_allowed"] is False
    assert convergence["legacy_direct_send_allowed"] is False
    assert convergence["executor_registered"] is False
    assert convergence["approval_required"] is True
    assert convergence["execution_allowed"] is False
    assert convergence["external_send_allowed"] is False
    assert convergence["send_hold_active"] is True


def test_invoice_send_executor_is_registered_but_send_hold_blocks_execution():
    blocked = convergence_for_surface("invoice_send")
    ready_after_hold = convergence_for_surface("invoice_send", send_hold_active=False)

    assert blocked["canonical_gate"] == G3_GATE
    assert blocked["executor_registered"] is False
    assert blocked["execution_allowed"] is False
    assert blocked["external_send_allowed"] is False
    assert blocked["executor_mode"] == "square_sandbox_only"

    assert ready_after_hold["executor_registered"] is True
    assert ready_after_hold["execution_allowed"] is False
    assert ready_after_hold["external_send_allowed"] is False


def test_exact_gmail_send_links_approved_guardian_receipt_without_hiding_registered_executor():
    convergence = convergence_for_surface(
        "exact_gmail_send",
        send_hold_active=True,
        approval_status="APPROVED",
        approval_receipt_ref="hitl_pending_store:5FF438AC#decision_receipt",
    )

    assert convergence["executor_registered"] is True
    assert convergence["executor"] == "cassandra_exact_send_executor"
    assert convergence["g3_gate_state"] == GateState.DONE.value
    assert convergence["approval_receipt_linked"] is True
    assert convergence["approval_receipt_ref"] == "hitl_pending_store:5FF438AC#decision_receipt"
    assert convergence["g3_execution_eligible"] is True
    assert convergence["send_hold_active"] is True
    assert convergence["execution_allowed"] is False
    assert convergence["external_send_allowed"] is False


@pytest.mark.parametrize(
    ("text", "surface"),
    [
        ("email Sally about the Reynolds gig", "email_send"),
        ("text Sally that the invoice is ready", "sms_send"),
    ],
)
def test_compose_preview_embeds_gate_convergence_for_email_and_sms(text, surface):
    result = compose(
        text,
        source_kind="mission_control",
        source_channel="gate_convergence_test",
        requested_by="winship",
        db_path=str(TEMP_DB),
    )

    assert result.gate_state is GateState.PENDING_APPROVAL
    assert result.intent == surface
    assert result.pending_approval is not None
    convergence = result.pending_approval.preview["gate_convergence"]
    assert convergence["surface"] == surface
    assert convergence["single_authoritative_gate"] == G3_GATE
    assert convergence["double_gate_allowed"] is False
    assert convergence["executor_registered"] is False
    assert convergence["external_send_allowed"] is False
    assert result.pending_approval.preview["execution_allowed"] is False


@pytest.mark.parametrize("surface", ["email_send", "sms_send"])
def test_send_surfaces_remain_unwired_under_send_hold(surface):
    receipt = execute_packet("packet_fixture", surface=surface, db_path=str(TEMP_DB))

    assert receipt.ok is False
    assert receipt.gate_state is GateState.FAILED
    assert "No executor wired" in receipt.detail
