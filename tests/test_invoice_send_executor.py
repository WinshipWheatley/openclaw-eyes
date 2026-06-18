import sqlite3
from pathlib import Path

import pytest

from agent_work_packet import get_agent_work_packet_approval_state
from chief_compose import EXECUTORS, compose, execute_packet
from compose_contract import GateState
from invoice_send_executor import (
    DEFAULT_SEND_HOLD_PATH,
    INVOICE_SEND_SURFACE,
    SQUARE_SANDBOX_EFFECT,
    execute_invoice_send_packet,
    invoice_send_executor_registered,
)


TEMP_DB = Path("/tmp/invoice_send_executor_test.sqlite")
VALIDATION_DB = Path("/tmp/compose_invoice_validation_test.sqlite")


@pytest.fixture(autouse=True)
def clean_temp_db():
    for path in (TEMP_DB, VALIDATION_DB):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    yield
    for path in (TEMP_DB, VALIDATION_DB):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _approve_packet_for_test(packet_id: str, *, db_path: Path = TEMP_DB) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE agent_work_packets SET execution_allowed = 1, status = 'proposed' WHERE packet_id = ?",
            (packet_id,),
        )
        conn.commit()
    finally:
        conn.close()


def _side_effect_rows(
    packet_id: str,
    *,
    db_path: Path = TEMP_DB,
) -> list[tuple[str, str, int, int, str | None]]:
    conn = sqlite3.connect(db_path)
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


def test_compose_invoice_send_validation_contract_blocks_live_and_records_sandbox_only(tmp_path):
    result = compose(
        "send invoice to Sally at Reynolds Tavern for 250 dollars through Square sandbox",
        source_kind="mission_control",
        source_channel="compose_invoice_validation_test",
        requested_by="winship",
        db_path=str(VALIDATION_DB),
    )

    assert result.gate_state is GateState.PENDING_APPROVAL
    assert result.intent == INVOICE_SEND_SURFACE
    assert result.packet_id
    assert result.pending_approval is not None
    assert result.pending_approval.surface == INVOICE_SEND_SURFACE
    assert result.pending_approval.preview["execution_allowed"] is False

    state = get_agent_work_packet_approval_state(
        packet_id=result.packet_id,
        expected_packet_hash=result.pending_approval.preview["packet_hash"],
        db_path=VALIDATION_DB,
    )
    assert state.surface == INVOICE_SEND_SURFACE
    assert state.approval_required is True
    assert state.execution_allowed is False
    assert state.action_created is False
    assert state.hash_matches is True
    assert state.stale is False

    _approve_packet_for_test(result.packet_id, db_path=VALIDATION_DB)
    assert DEFAULT_SEND_HOLD_PATH.is_file()

    blocked = execute_packet(
        result.packet_id,
        surface=INVOICE_SEND_SURFACE,
        db_path=str(VALIDATION_DB),
    )

    assert blocked.ok is False
    assert "SEND_HOLD is active" in blocked.detail
    assert blocked.meta["send_hold_active"] is True
    assert blocked.meta["production_used"] is False
    assert blocked.meta["square_production_used"] is False
    assert blocked.meta["external_send_performed"] is False
    assert blocked.meta["square_api_called"] is False

    sandbox = execute_invoice_send_packet(
        packet_id=result.packet_id,
        db_path=str(VALIDATION_DB),
        send_hold_path=tmp_path / "SEND_HOLD_missing.md",
    )

    assert sandbox.ok is True
    assert sandbox.gate_state is GateState.DONE
    assert sandbox.meta["sandbox_receipt_only"] is True
    assert sandbox.meta["production_used"] is False
    assert sandbox.meta["square_production_used"] is False
    assert sandbox.meta["external_send_performed"] is False
    assert sandbox.meta["square_api_called"] is False
    assert sandbox.meta["email_send_performed"] is False
    assert sandbox.meta["workbook_written"] is False
    assert sandbox.meta["ledger_payment_posted"] is False
    assert sandbox.meta["invoice_marked_paid"] is False

    assert _side_effect_rows(result.packet_id, db_path=VALIDATION_DB) == [
        (SQUARE_SANDBOX_EFFECT, "blocked_send_hold", 1, 0, None),
        (SQUARE_SANDBOX_EFFECT, "sandbox_send_recorded", 1, 0, sandbox.meta["square_sandbox_ref"]),
    ]


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
    assert receipt.meta["production_used"] is False
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
    assert receipt.meta["production_used"] is False
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
    assert receipt.meta["production_used"] is False
    assert receipt.meta["square_production_used"] is False
    assert _side_effect_rows(result.packet_id or "") == [
        (SQUARE_SANDBOX_EFFECT, "blocked_non_sandbox", 1, 0, None)
    ]
