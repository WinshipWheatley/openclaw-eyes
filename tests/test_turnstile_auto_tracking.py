import json
import sqlite3
from pathlib import Path

import pytest

from agent_work_packet import get_agent_work_packet_approval_state
from business_ops_ledger import append_side_effect
from chief_compose import EXECUTORS, compose, execute_packet, register_executor
from compose_contract import ExecutionReceipt
from invoice_send_executor import INVOICE_SEND_SURFACE


TEMP_DB = Path("/tmp/turnstile_auto_tracking_test.sqlite")


@pytest.fixture(autouse=True)
def clean_temp_db():
    original_executors = dict(EXECUTORS)
    try:
        TEMP_DB.unlink()
    except FileNotFoundError:
        pass
    yield
    EXECUTORS.clear()
    EXECUTORS.update(original_executors)
    try:
        TEMP_DB.unlink()
    except FileNotFoundError:
        pass


def _rows(table: str, where: str = "", params: tuple = ()) -> list[sqlite3.Row]:
    conn = sqlite3.connect(TEMP_DB)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(f"SELECT * FROM {table} {where}", params).fetchall()
    finally:
        conn.close()


def _approve_packet_for_test(packet_id: str) -> None:
    conn = sqlite3.connect(TEMP_DB)
    try:
        conn.execute(
            "UPDATE agent_work_packets SET execution_allowed = 1, status = 'proposed' WHERE packet_id = ?",
            (packet_id,),
        )
        conn.commit()
    finally:
        conn.close()


def test_sandbox_executor_auto_records_one_operator_action_and_side_effect():
    surface = "turnstile_sandbox_action"

    def sandbox_executor(*, packet_id: str, db_path: str | None = None) -> ExecutionReceipt:
        return ExecutionReceipt(
            packet_id=packet_id,
            surface=surface,
            ok=True,
            detail="Sandbox executor completed.",
        )

    register_executor(surface, sandbox_executor)

    receipt = execute_packet("packet_turnstile_success", surface=surface, db_path=str(TEMP_DB))

    assert receipt.ok is True
    assert receipt.side_effect_id == "side_effect:1"
    assert receipt.meta["side_effect_recorded"] is True
    assert receipt.meta["operator_action_recorded"] is True

    side_effects = _rows("side_effects", "WHERE packet_id = ?", ("packet_turnstile_success",))
    assert len(side_effects) == 1
    assert (side_effects[0]["effect_type"], side_effects[0]["status"]) == (
        surface,
        "executor_ok",
    )

    actions = _rows("operator_action_requests")
    receipts = _rows("operator_action_receipts")
    assert len(actions) == 1
    assert len(receipts) == 1
    assert actions[0]["action_type"] == surface
    assert actions[0]["status"] == "completed"
    assert receipts[0]["result"] == "completed"
    payload = json.loads(receipts[0]["payload_json"])
    assert payload["packet_id"] == "packet_turnstile_success"
    assert payload["side_effect_id"] == "side_effect:1"


def test_executor_owned_side_effect_is_not_recorded_twice_and_refusal_is_not_success():
    surface = "turnstile_refused_action"

    def refused_executor(*, packet_id: str, db_path: str | None = None) -> ExecutionReceipt:
        side_effect_id = append_side_effect(
            packet_id=packet_id,
            effect_type=surface,
            status="refused_by_fixture_policy",
            approval_required=True,
            approval_tier="operator_final_send",
            replay_safe=False,
            db_path=db_path,
        )
        return ExecutionReceipt(
            packet_id=packet_id,
            surface=surface,
            ok=False,
            detail="Refused by fixture policy.",
            side_effect_id=side_effect_id,
        )

    register_executor(surface, refused_executor)

    receipt = execute_packet("packet_turnstile_refused", surface=surface, db_path=str(TEMP_DB))

    assert receipt.ok is False
    assert receipt.side_effect_id == "side_effect:1"
    assert receipt.meta["operator_action_recorded"] is True
    assert len(_rows("side_effects", "WHERE packet_id = ?", ("packet_turnstile_refused",))) == 1

    actions = _rows("operator_action_requests")
    receipts = _rows("operator_action_receipts")
    assert len(actions) == 1
    assert len(receipts) == 1
    assert actions[0]["status"] == "refused"
    assert receipts[0]["result"] == "refused"


def test_send_hold_invoice_path_still_blocks_and_records_blocked_action():
    result = compose(
        "send the Reynolds Tavern invoice for 250 dollars through Square sandbox",
        source_kind="mission_control",
        source_channel="turnstile_auto_tracking_test",
        requested_by="winship",
        db_path=str(TEMP_DB),
    )
    assert result.packet_id
    _approve_packet_for_test(result.packet_id)

    state = get_agent_work_packet_approval_state(packet_id=result.packet_id, db_path=TEMP_DB)
    assert state.surface == INVOICE_SEND_SURFACE
    assert state.execution_allowed is True

    receipt = execute_packet(result.packet_id, surface=INVOICE_SEND_SURFACE, db_path=str(TEMP_DB))

    assert receipt.ok is False
    assert "SEND_HOLD is active" in receipt.detail
    assert receipt.meta["send_hold_active"] is True
    assert receipt.meta["external_send_performed"] is False
    assert receipt.meta["operator_action_recorded"] is True

    side_effects = _rows("side_effects", "WHERE packet_id = ?", (result.packet_id,))
    assert len(side_effects) == 1
    assert side_effects[0]["status"] == "blocked_send_hold"

    actions = _rows("operator_action_requests")
    receipts = _rows("operator_action_receipts")
    assert len(actions) == 1
    assert len(receipts) == 1
    assert actions[0]["action_type"] == INVOICE_SEND_SURFACE
    assert actions[0]["status"] == "blocked"
    assert receipts[0]["result"] == "blocked"
