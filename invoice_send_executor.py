"""Sandbox-only Square invoice-send executor.

This module wires the `invoice_send` executor surface without granting live
Square, email, workbook, ledger-payment, or paid-marking authority. Under the
active orchestration SEND_HOLD it always fails closed. When the hold is absent
and a packet is explicitly execution-approved, it records a local Square
sandbox receipt only; it does not call Square APIs.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any

from business_ops_ledger import DEFAULT_DB_PATH, append_side_effect, init_business_ops_ledger
from compose_contract import ExecutionReceipt


INVOICE_SEND_SURFACE = "invoice_send"
SQUARE_SANDBOX_EFFECT = "invoice_send.square.sandbox"
DEFAULT_SEND_HOLD_PATH = Path("/mnt/e/openclaw/orchestration/SEND_HOLD.md")


def invoice_send_executor_registered() -> bool:
    """Return whether the compose registry has an invoice sender installed."""

    from chief_compose import EXECUTORS

    return INVOICE_SEND_SURFACE in EXECUTORS


def _safe_db_path(db_path: str | None) -> str:
    return str(db_path or DEFAULT_DB_PATH)


def _side_effect_exists(packet_id: str, db_path: str | None) -> bool:
    path = _safe_db_path(db_path)
    init_business_ops_ledger(path)
    conn = sqlite3.connect(path)
    try:
        row = conn.execute(
            """
SELECT 1
FROM side_effects
WHERE packet_id = ?
  AND effect_type = ?
  AND status = 'sandbox_send_recorded'
LIMIT 1
""".strip(),
            (packet_id, SQUARE_SANDBOX_EFFECT),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def _sandbox_ref(packet_id: str) -> str:
    digest = hashlib.sha256(f"square-sandbox\0{packet_id}".encode("utf-8")).hexdigest()
    return f"square_sandbox_local:{digest[:20]}"


def _append_invoice_side_effect(
    *,
    packet_id: str,
    status: str,
    db_path: str | None,
    external_ref: str | None = None,
) -> str | None:
    init_business_ops_ledger(db_path)
    return append_side_effect(
        packet_id=packet_id,
        effect_type=SQUARE_SANDBOX_EFFECT,
        status=status,
        approval_required=True,
        approval_tier="G3",
        replay_safe=False,
        external_ref=external_ref,
        db_path=db_path,
    )


def _receipt(
    *,
    packet_id: str,
    ok: bool,
    detail: str,
    status: str,
    db_path: str | None,
    external_ref: str | None = None,
    meta: dict[str, Any] | None = None,
) -> ExecutionReceipt:
    side_effect_id = _append_invoice_side_effect(
        packet_id=packet_id,
        status=status,
        db_path=db_path,
        external_ref=external_ref,
    )
    return ExecutionReceipt(
        packet_id=packet_id,
        surface=INVOICE_SEND_SURFACE,
        ok=ok,
        detail=detail,
        side_effect_id=side_effect_id,
        meta={
            "provider": "square",
            "square_environment": "sandbox",
            "square_api_called": False,
            "square_production_used": False,
            "external_send_performed": False,
            "email_send_performed": False,
            "workbook_written": False,
            "ledger_payment_posted": False,
            "invoice_marked_paid": False,
            "side_effect_recorded": bool(side_effect_id),
            **(meta or {}),
        },
    )


def execute_invoice_send_packet(
    *,
    packet_id: str,
    db_path: str | None = None,
    expected_packet_hash: str | None = None,
    send_hold_path: str | Path = DEFAULT_SEND_HOLD_PATH,
    square_environment: str = "sandbox",
) -> ExecutionReceipt:
    """Execute an approved invoice-send packet in local Square sandbox mode only."""

    from chief_compose import get_packet_approval_state

    packet_id = (packet_id or "").strip()
    if not packet_id:
        return ExecutionReceipt(packet_id="", surface=INVOICE_SEND_SURFACE, ok=False, detail="packet_id is required")

    try:
        state = get_packet_approval_state(
            packet_id,
            expected_packet_hash=expected_packet_hash,
            db_path=_safe_db_path(db_path),
        )
    except ValueError as exc:
        return _receipt(
            packet_id=packet_id,
            ok=False,
            detail=str(exc),
            status="blocked_guard_failed",
            db_path=db_path,
        )

    if state["surface"] != INVOICE_SEND_SURFACE:
        return _receipt(
            packet_id=packet_id,
            ok=False,
            detail=f"Packet surface is {state['surface']!r}, not 'invoice_send'. Nothing was sent.",
            status="blocked_guard_failed",
            db_path=db_path,
            meta={"approval_state": state},
        )
    if state["stale"]:
        return _receipt(
            packet_id=packet_id,
            ok=False,
            detail="Packet stale-hash check failed. Nothing was sent.",
            status="blocked_guard_failed",
            db_path=db_path,
            meta={"approval_state": state},
        )
    if Path(send_hold_path).is_file():
        return _receipt(
            packet_id=packet_id,
            ok=False,
            detail="SEND_HOLD is active. Square invoice sandbox send is blocked; nothing was sent.",
            status="blocked_send_hold",
            db_path=db_path,
            meta={"approval_state": state, "send_hold_active": True},
        )
    if not state["execution_allowed"]:
        return _receipt(
            packet_id=packet_id,
            ok=False,
            detail="Packet is not execution-approved. Nothing was sent.",
            status="blocked_guard_failed",
            db_path=db_path,
            meta={"approval_state": state, "send_hold_active": False},
        )
    if square_environment != "sandbox":
        return _receipt(
            packet_id=packet_id,
            ok=False,
            detail="Only Square sandbox execution is allowed in this lane. Nothing was sent.",
            status="blocked_non_sandbox",
            db_path=db_path,
            meta={"approval_state": state, "send_hold_active": False, "requested_environment": square_environment},
        )
    if _side_effect_exists(packet_id, db_path):
        return _receipt(
            packet_id=packet_id,
            ok=False,
            detail="A Square sandbox invoice send receipt already exists for this packet. Nothing was sent again.",
            status="blocked_duplicate_success",
            db_path=db_path,
            meta={"approval_state": state, "send_hold_active": False},
        )

    sandbox_ref = _sandbox_ref(packet_id)
    return _receipt(
        packet_id=packet_id,
        ok=True,
        detail=(
            "Square sandbox invoice send recorded locally. No production send, email, workbook write, "
            "ledger payment post, or paid marking occurred."
        ),
        status="sandbox_send_recorded",
        db_path=db_path,
        external_ref=sandbox_ref,
        meta={
            "approval_state": state,
            "send_hold_active": False,
            "square_sandbox_ref": sandbox_ref,
            "sandbox_receipt_only": True,
        },
    )


__all__ = [
    "DEFAULT_SEND_HOLD_PATH",
    "INVOICE_SEND_SURFACE",
    "SQUARE_SANDBOX_EFFECT",
    "execute_invoice_send_packet",
    "invoice_send_executor_registered",
]
