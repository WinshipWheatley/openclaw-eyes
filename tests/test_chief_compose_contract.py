import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

import agent_work_packet
import intent_router
from chief_compose import compose, execute_packet
from compose_contract import GateState
from intent_router import route_operator_intent


TEMP_DB = Path("/tmp/compose_test.sqlite")


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


def _stub_chief_router(monkeypatch, *, intent="communication_summary_request", reply="[stubbed read-only reply]"):
    stub = types.ModuleType("chief_router")
    stub.route_message = lambda text: {"intent": intent, "reply": reply}
    monkeypatch.setitem(sys.modules, "chief_router", stub)
    return stub


def _raising_chief_router(monkeypatch):
    stub = types.ModuleType("chief_router")

    def _raise(_text):
        raise AssertionError("route_message must not run for gated action paths")

    stub.route_message = _raise
    monkeypatch.setitem(sys.modules, "chief_router", stub)
    return stub


@pytest.mark.parametrize(
    ("surface", "text"),
    [
        ("invoice_send", "send the Capital Hilton invoice for 4200 dollars"),
        ("email_send", "email Annette the invoice now"),
        ("sms_send", "text Annette that the invoice is ready"),
        ("phone_call", "call Annette about the overdue payment"),
        ("calendar_create", "make a calendar event for the gig tomorrow at 2"),
        ("ledger_mutation", "mark the Capital Hilton invoice paid in the ledger"),
        ("coupa_submit", "submit this invoice in Coupa"),
        ("browser_action", "open the browser and upload the payment proof"),
        ("gmail_draft", "create a Gmail draft to the client"),
        ("workbook_mutation", "update the workbook with this payment"),
        ("pdf_export", "export the invoice PDF"),
        ("daw_action", "open Logic and bounce the song"),
        ("obs_launch", "start OBS and go live"),
    ],
)
def test_route_operator_intent_gates_action_surfaces(surface, text):
    result = route_operator_intent(
        text=text,
        source_kind="mission_control",
        source_channel="compose_contract_test",
        requested_by="winship",
        db_path=TEMP_DB,
    )

    assert surface
    assert result.approval_required is True
    assert result.execution_allowed is False
    assert result.action_request_created is False


def test_compose_read_only_input_returns_read_only_without_packet(monkeypatch):
    _stub_chief_router(monkeypatch)

    result = compose(
        "Cassandra, summarize what changed.",
        source_kind="mission_control",
        source_channel="compose_contract_test",
        requested_by="winship",
        db_path=str(TEMP_DB),
    )

    assert result.gate_state is GateState.READ_ONLY
    assert result.packet_id is None
    assert result.pending_approval is None
    assert result.segments == ["[stubbed read-only reply]"]


def test_compose_action_input_returns_pending_approval_packet(monkeypatch):
    _raising_chief_router(monkeypatch)

    result = compose(
        "send the Capital Hilton invoice for 4200 dollars",
        source_kind="mission_control",
        source_channel="compose_contract_test",
        requested_by="winship",
        db_path=str(TEMP_DB),
    )

    assert result.gate_state is GateState.PENDING_APPROVAL
    assert result.packet_id
    assert result.pending_approval is not None
    assert result.pending_approval.preview["execution_allowed"] is False


def test_compose_malformed_classifier_result_gates_not_fast_path(monkeypatch):
    _raising_chief_router(monkeypatch)

    def fake_route_operator_intent(**_kwargs):
        return SimpleNamespace(
            status="routed",
            intent_category="malformed_fixture",
            run_id="run_malformed_fixture",
        )

    def fake_build_agent_work_packet(**_kwargs):
        return SimpleNamespace(
            packet_id="packet_malformed_fixture",
            goal="Hold for review.",
            execution_allowed=False,
        )

    monkeypatch.setattr(intent_router, "route_operator_intent", fake_route_operator_intent)
    monkeypatch.setattr(agent_work_packet, "build_agent_work_packet", fake_build_agent_work_packet)

    result = compose(
        "???",
        source_kind="mission_control",
        source_channel="compose_contract_test",
        requested_by="winship",
        db_path=str(TEMP_DB),
    )

    assert result.gate_state is GateState.PENDING_APPROVAL
    assert result.packet_id == "packet_malformed_fixture"
    assert result.pending_approval is not None


def test_execute_packet_refuses_unwired_surface():
    receipt = execute_packet("packet_fixture", surface="invoice_send", db_path=str(TEMP_DB))

    assert receipt.ok is False
    assert receipt.gate_state is GateState.FAILED
    assert "No executor wired" in receipt.detail
