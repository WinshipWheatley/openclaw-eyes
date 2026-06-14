import sqlite3
from pathlib import Path

import pytest

from agent_work_packet import get_agent_work_packet_approval_state
from chief_compose import EXECUTORS, compose, execute_packet
from compose_contract import GateState
from invoice_send_executor import (
    INVOICE_SEND_SURFACE,
    SQUARE_SANDBOX_EFFECT,
    execute_invoice_send_packet,
    invoice_send_executor_registered,
)


TEMP_DB = Path("/tmp/invoice_send_executor_test.sqlite")


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


def _side_effect_rows(packet_id: str) -> list[tuple[str, str, int, int, str | None]]:
    conn = sqlite3.connect(TEMP_DB)
    try:
        return conn.execute(
            """
SELECT effect_type, status, approval_required, replay_safe, external_ref
FROM side_effects
WHERE packet_id = ?
ORDER BY id
""".strip(),
            (packet_id,),
        ).fetchall()
    finally:
        conn.close()


def test_invoice_send_executor_is_registered_for_compose_surface():
    assert invoice_send_executor_registered() is True
    assert EXECUTORS[INVOICE_SEND_SURFACE] is execute_invoice_send_packet


def test_reynolds_invoice_reaches_pending_approval_packet():
    result = compose(
        "send the Reynolds Tavern invoice for 250 dollars through Square sandbox",
        source_kind="mission_control",
        source_channel="invoice_send_executor_test",
        requested_by="winship",
        db_path=str(TEMP_DB),
    )

    assert result.gate_state is GateState.PENDING_APPROVAL
    assert result.intent == INVOICE_SEND_SURFACE
    assert result.packet_id
    assert result.pending_approval is not None
    assert result.pending_approval.surface == INVOICE_SEND_SURFACE
    assert result.pending_approval.preview["execution_allowed"] is False

    state = get_agent_work_packet_approval_state(packet_id=result.packet_id, db_path=TEMP_DB)
    assert state.surface == INVOICE_SEND_SURFACE
    assert state.execution_allowed is False


def test_registered_invoice_executor_blocks_under_send_hold():
    result = compose(
        "send the Reynolds Tavern invoice for 250 dollars through Square sandbox",
        source_kind="mission_control",
        source_channel="invoice_send_executor_test",
        requested_by="winship",
        db_path=str(TEMP_DB),
    )
    _approve_packet_for_test(result.packet_id or "")

    receipt = execute_packet(result.packet_id or "", surface=INVOICE_SEND_SURFACE, db_path=str(TEMP_DB))

    assert receipt.ok is False
    assert "SEND_HOLD is active" in receipt.detail
    assert receipt.meta["send_hold_active"] is True
    assert receipt.meta["square_api_called"] is False
    assert receipt.meta["external_send_performed"] is False
    assert receipt.meta["invoice_marked_paid"] is False

    assert _side_effect_rows(result.packet_id or "") == [
        (SQUARE_SANDBOX_EFFECT, "blocked_send_hold", 1, 0, None)
    ]


def test_square_sandbox_receipt_records_when_hold_absent_and_packet_approved(tmp_path):
    result = compose(
        "send the Reynolds Tavern invoice for 250 dollars through Square sandbox",
        source_kind="mission_control",
        source_channel="invoice_send_executor_test",
        requested_by="winship",
        db_path=str(TEMP_DB),
    )
    _approve_packet_for_test(result.packet_id or "")
    missing_hold = tmp_path / "SEND_HOLD_missing.md"

    receipt = execute_invoice_send_packet(
        packet_id=result.packet_id or "",
        db_path=str(TEMP_DB),
        send_hold_path=missing_hold,
    )

    assert receipt.ok is True
    assert receipt.gate_state is GateState.DONE
    assert "Square sandbox invoice send recorded locally" in receipt.detail
    assert receipt.meta["send_hold_active"] is False
    assert receipt.meta["sandbox_receipt_only"] is True
    assert receipt.meta["square_api_called"] is False
    assert receipt.meta["square_production_used"] is False
    assert receipt.meta["email_send_performed"] is False
    assert receipt.meta["workbook_written"] is False
    assert receipt.meta["ledger_payment_posted"] is False
    assert receipt.meta["invoice_marked_paid"] is False

    rows = _side_effect_rows(result.packet_id or "")
    assert len(rows) == 1
    assert rows[0][0:4] == (SQUARE_SANDBOX_EFFECT, "sandbox_send_recorded", 1, 0)
    assert rows[0][4].startswith("square_sandbox_local:")


def test_square_sandbox_duplicate_success_blocks_second_attempt(tmp_path):
    result = compose(
        "send the Reynolds Tavern invoice for 250 dollars through Square sandbox",
        source_kind="mission_control",
        source_channel="invoice_send_executor_test",
        requested_by="winship",
        db_path=str(TEMP_DB),
    )
    _approve_packet_for_test(result.packet_id or "")
    missing_hold = tmp_path / "SEND_HOLD_missing.md"

    first = execute_invoice_send_packet(
        packet_id=result.packet_id or "",
        db_path=str(TEMP_DB),
        send_hold_path=missing_hold,
    )
    second = execute_invoice_send_packet(
        packet_id=result.packet_id or "",
        db_path=str(TEMP_DB),
        send_hold_path=missing_hold,
    )

    assert first.ok is True
    assert second.ok is False
    assert "already exists" in second.detail
    assert second.meta["external_send_performed"] is False

    rows = _side_effect_rows(result.packet_id or "")
    assert [row[1] for row in rows] == ["sandbox_send_recorded", "blocked_duplicate_success"]


def test_square_executor_refuses_production_environment_when_hold_absent(tmp_path):
    result = compose(
        "send the Reynolds Tavern invoice for 250 dollars through Square sandbox",
        source_kind="mission_control",
        source_channel="invoice_send_executor_test",
        requested_by="winship",
        db_path=str(TEMP_DB),
    )
    _approve_packet_for_test(result.packet_id or "")

    receipt = execute_invoice_send_packet(
        packet_id=result.packet_id or "",
        db_path=str(TEMP_DB),
        send_hold_path=tmp_path / "SEND_HOLD_missing.md",
        square_environment="production",
    )

    assert receipt.ok is False
    assert "Only Square sandbox execution is allowed" in receipt.detail
    assert receipt.meta["square_production_used"] is False
    assert _side_effect_rows(result.packet_id or "") == [
        (SQUARE_SANDBOX_EFFECT, "blocked_non_sandbox", 1, 0, None)
    ]
