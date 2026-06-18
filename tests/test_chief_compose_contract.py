import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

import agent_work_packet
import intent_router
from chief_compose import compose, execute_packet, execute_packet_with_state, get_packet_approval_state
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
    ("surface", "text", "expected_category", "expected_candidate"),
    [
        ("invoice_send", "send the Capital Hilton invoice for 4200 dollars", "invoice_send", "invoice_send"),
        ("email_send", "email Annette the invoice now", "email_send", "email_send"),
        ("sms_send", "text Annette that the invoice is ready", "sms_send", "sms_send"),
        ("phone_call", "call Annette about the overdue payment", "phone_log", "phone_log"),
        ("calendar_create", "make a calendar event for the gig tomorrow at 2", "calendar_create", "calendar_create"),
        ("ledger_mutation", "mark the Capital Hilton invoice paid in the ledger", "ledger_mutation", "ledger_mutation"),
        ("coupa_submit", "submit this invoice in Coupa", "coupa_submit", "coupa_submit"),
        ("browser_action", "open the browser and upload the payment proof", "unknown_review", None),
        ("gmail_draft", "create a Gmail draft to the client", "email_send", "email_send"),
        ("workbook_mutation", "update the workbook with this payment", "unknown_review", None),
        ("pdf_export", "export the invoice PDF", "unknown_review", None),
        ("daw_action", "open Logic and bounce the song", "file_context_request", None),
        ("obs_launch", "start OBS and go live", "obs_launch", "obs_launch"),
        ("livestream_setup", "set up the livestream for tonight", "livestream_setup", "livestream_setup"),
    ],
)
def test_route_operator_intent_gates_action_surfaces(surface, text, expected_category, expected_candidate):
    result = route_operator_intent(
        text=text,
        source_kind="mission_control",
        source_channel="compose_contract_test",
        requested_by="winship",
        db_path=TEMP_DB,
    )

    assert surface
    assert result.intent_category == expected_category
    assert result.candidate_action_type == expected_candidate
    assert result.approval_required is True
    assert result.execution_allowed is False
    assert result.action_request_created is False


def test_route_operator_intent_declared_action_categories_all_require_approval():
    examples = {
        "invoice_send": "send invoice to Sally at Reynolds Tavern for 250 dollars",
        "email_send": "send Annette an email with the invoice",
        "sms_send": "text Annette that the invoice is ready",
        "phone_log": "call Annette about the overdue payment",
        "calendar_create": "create a calendar event for the gig tomorrow",
        "ledger_mutation": "mark the invoice paid in the ledger",
        "coupa_submit": "submit this invoice in Coupa",
        "obs_launch": "launch OBS for the stream",
        "livestream_setup": "set up the livestream for tonight",
    }
    assert set(examples) == intent_router.ACTION_INTENT_CATEGORIES

    for category, text in examples.items():
        result = route_operator_intent(
            text=text,
            source_kind="mission_control",
            source_channel=f"compose_contract_{category}",
            requested_by="winship",
            db_path=TEMP_DB,
        )

        assert result.intent_category == category
        assert result.candidate_action_type == category
        assert result.approval_required is True
        assert result.execution_allowed is False
        assert result.action_request_created is False


@pytest.mark.parametrize(
    ("text", "expected_category"),
    [
        ("did the invoice thing go out?", "invoice_status_lookup"),
        ("what is pending?", "pending_approval_lookup"),
        ("what does PENDING_APPROVAL mean like I am five?", "approval_explainer"),
        ("what can you do with invoices?", "capability_query"),
        ("what is on the schedule today?", "schedule_lookup"),
    ],
)
def test_route_operator_intent_read_only_lookup_and_explainer_buckets_do_not_require_approval(text, expected_category):
    result = route_operator_intent(
        text=text,
        source_kind="mission_control",
        source_channel="compose_contract_test",
        requested_by="winship",
        db_path=TEMP_DB,
    )

    assert result.intent_category == expected_category
    assert result.candidate_action_type is None
    assert result.approval_required is False
    assert result.execution_allowed is False


def test_route_operator_intent_recovers_disposable_tmp_sqlite_after_readonly_stale_file(tmp_path):
    db_path = tmp_path / "stale-compose.sqlite"
    db_path.write_text("not a live sqlite database", encoding="utf-8")
    db_path.chmod(0o400)

    result = route_operator_intent(
        text="email Annette the invoice now",
        source_kind="mission_control",
        source_channel="compose_contract_test",
        requested_by="winship",
        db_path=db_path,
    )

    assert result.intent_category == "email_send"
    assert result.candidate_action_type == "email_send"
    assert result.approval_required is True


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


def test_compose_pending_lookup_input_returns_read_only_without_packet(monkeypatch):
    _stub_chief_router(monkeypatch, intent="pending_approval_lookup", reply="No pending approval cards found.")

    result = compose(
        "what is pending?",
        source_kind="mission_control",
        source_channel="compose_contract_test",
        requested_by="winship",
        db_path=str(TEMP_DB),
    )

    assert result.gate_state is GateState.READ_ONLY
    assert result.intent == "pending_approval_lookup"
    assert result.packet_id is None
    assert result.pending_approval is None


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
    assert result.intent == "invoice_send"
    assert result.packet_id
    assert result.pending_approval is not None
    assert result.pending_approval.preview["execution_allowed"] is False
    assert result.pending_approval.preview["button_label"] == "Approve invoice send"
    assert "Nothing has been sent yet." in result.segments

    state = get_packet_approval_state(
        result.packet_id,
        expected_packet_hash=result.pending_approval.preview["packet_hash"],
        db_path=str(TEMP_DB),
    )
    assert state["surface"] == "invoice_send"
    assert state["approval_required"] is True
    assert state["execution_allowed"] is False
    assert state["hash_matches"] is True
    assert state["stale"] is False


def test_packet_stale_hash_check_fails_closed(monkeypatch):
    _raising_chief_router(monkeypatch)

    result = compose(
        "send the Capital Hilton invoice for 4200 dollars",
        source_kind="mission_control",
        source_channel="compose_contract_test",
        requested_by="winship",
        db_path=str(TEMP_DB),
    )

    stale = get_packet_approval_state(
        result.packet_id,
        expected_packet_hash="not-the-current-hash",
        db_path=str(TEMP_DB),
    )
    assert stale["hash_matches"] is False
    assert stale["stale"] is True

    receipt = execute_packet_with_state(
        result.packet_id,
        surface="invoice_send",
        expected_packet_hash="not-the-current-hash",
        db_path=str(TEMP_DB),
    )
    assert receipt.ok is False
    assert receipt.gate_state is GateState.FAILED
    assert "stale-hash" in receipt.detail
    assert receipt.side_effect_id

    import sqlite3

    conn = sqlite3.connect(TEMP_DB)
    try:
        row = conn.execute(
            "SELECT effect_type, status, approval_required FROM side_effects WHERE packet_id = ?",
            (result.packet_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row == ("invoice_send", "blocked_stale_hash", 1)


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

    def fake_get_agent_work_packet_approval_state(**_kwargs):
        return SimpleNamespace(packet_hash="packet_hash_malformed_fixture")

    monkeypatch.setattr(intent_router, "route_operator_intent", fake_route_operator_intent)
    monkeypatch.setattr(agent_work_packet, "build_agent_work_packet", fake_build_agent_work_packet)
    monkeypatch.setattr(agent_work_packet, "get_agent_work_packet_approval_state", fake_get_agent_work_packet_approval_state)

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


def test_execute_packet_registered_invoice_surface_fails_closed_for_missing_packet():
    receipt = execute_packet("packet_fixture", surface="invoice_send", db_path=str(TEMP_DB))

    assert receipt.ok is False
    assert receipt.gate_state is GateState.FAILED
    assert "agent work packet not found" in receipt.detail
    assert receipt.side_effect_id

    import sqlite3

    conn = sqlite3.connect(TEMP_DB)
    try:
        row = conn.execute(
            "SELECT effect_type, status, approval_required FROM side_effects WHERE packet_id = 'packet_fixture'"
        ).fetchone()
    finally:
        conn.close()
    assert row == ("invoice_send.square.sandbox", "blocked_guard_failed", 1)
