"""Unregistered email-send executor scaffold.

This module defines the future `email_send` executor boundary without wiring it
into `chief_compose.EXECUTORS`. Under the active SEND_HOLD it always fails
closed and records only local blocked side-effect metadata.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from business_ops_ledger import append_side_effect, init_business_ops_ledger
from compose_contract import ExecutionReceipt


EMAIL_SEND_SURFACE = "email_send"
DEFAULT_SEND_HOLD_PATH = Path("/mnt/e/openclaw/orchestration/SEND_HOLD.md")
EMAIL_SEND_EXECUTOR_VERSION = "email_send_executor_v0"
EMAIL_SEND_GMAIL_SCOPE_DECISION_FOR_WINSHIP = {
    "decision_owner": "Winship",
    "decision_status": "pending",
    "send_scope_not_activated_here": True,
    "scope_options": (
        {
            "option": "manual_send_handoff",
            "gmail_scope": None,
            "posture": "safest default while SEND_HOLD is active",
        },
        {
            "option": "gmail_draft_only",
            "gmail_scope": "https://www.googleapis.com/auth/gmail.compose",
            "posture": "future draft creation only; still not live send",
        },
        {
            "option": "gmail_live_send",
            "gmail_scope": "https://www.googleapis.com/auth/gmail.send",
            "posture": "requires separate final-send approval after SEND_HOLD lifts",
        },
    ),
    "module_default": "no transport attached; fail closed",
}


def email_send_executor_registered() -> bool:
    """Return whether the live compose registry has an email sender installed."""

    from chief_compose import EXECUTORS

    return EMAIL_SEND_SURFACE in EXECUTORS


def email_send_executor_descriptor() -> dict[str, Any]:
    """Describe the unregistered executor boundary for the pc-1 registry lane."""

    return {
        "schema_version": EMAIL_SEND_EXECUTOR_VERSION,
        "surface": EMAIL_SEND_SURFACE,
        "callable": "email_send_executor.execute_email_send_packet",
        "registry_owner": "codex-pc-1",
        "registered_by_this_module": False,
        "send_hold_path": str(DEFAULT_SEND_HOLD_PATH),
        "respects_send_hold": True,
        "requires_packet_surface": EMAIL_SEND_SURFACE,
        "requires_execution_allowed": True,
        "requires_operator_final_send": True,
        "default_transport_attached": False,
        "gmail_scope_decision_for_winship": dict(EMAIL_SEND_GMAIL_SCOPE_DECISION_FOR_WINSHIP),
        "blocked_external_actions": (
            "gmail_api_send",
            "smtp_send",
            "apple_mail_send",
            "external_email_send",
        ),
    }


def _blocked_receipt(
    *,
    packet_id: str,
    detail: str,
    db_path: str | None,
    meta: dict[str, Any] | None = None,
) -> ExecutionReceipt:
    init_business_ops_ledger(db_path)
    side_effect_id = append_side_effect(
        packet_id=packet_id,
        effect_type="email_send",
        status="blocked_no_send",
        approval_required=True,
        approval_tier="operator_final_send",
        replay_safe=False,
        external_ref=None,
        db_path=db_path,
    )
    return ExecutionReceipt(
        packet_id=packet_id,
        surface=EMAIL_SEND_SURFACE,
        ok=False,
        detail=detail,
        side_effect_id=side_effect_id,
        meta={
            "email_send_performed": False,
            "gmail_api_called": False,
            "external_send_performed": False,
            "side_effect_recorded": bool(side_effect_id),
            "requires_operator_final_send": True,
            "gmail_scope_decision_for_winship": dict(EMAIL_SEND_GMAIL_SCOPE_DECISION_FOR_WINSHIP),
            **(meta or {}),
        },
    )


def build_email_send_executor(
    *,
    send_hold_path: str | Path = DEFAULT_SEND_HOLD_PATH,
    email_sender: Callable[..., Any] | None = None,
) -> Callable[..., ExecutionReceipt]:
    """Return a registry-compatible executor wrapper without registering it."""

    def _executor(
        *,
        packet_id: str,
        db_path: str | None = None,
        expected_packet_hash: str | None = None,
    ) -> ExecutionReceipt:
        return execute_email_send_packet(
            packet_id=packet_id,
            db_path=db_path,
            expected_packet_hash=expected_packet_hash,
            send_hold_path=send_hold_path,
            email_sender=email_sender,
        )

    return _executor


def execute_email_send_packet(
    *,
    packet_id: str,
    db_path: str | None = None,
    expected_packet_hash: str | None = None,
    send_hold_path: str | Path = DEFAULT_SEND_HOLD_PATH,
    email_sender: Callable[..., Any] | None = None,
) -> ExecutionReceipt:
    """Fail-closed email executor scaffold.

    A future live implementation must still be registered explicitly through
    `chief_compose.register_executor`. This helper never imports or calls
    Gmail/SMTP by default.
    """

    from chief_compose import get_packet_approval_state

    packet_id = (packet_id or "").strip()
    if not packet_id:
        return ExecutionReceipt(packet_id="", surface=EMAIL_SEND_SURFACE, ok=False, detail="packet_id is required")

    try:
        state = get_packet_approval_state(
            packet_id,
            expected_packet_hash=expected_packet_hash,
            db_path=db_path,
        )
    except ValueError as exc:
        return _blocked_receipt(packet_id=packet_id, detail=str(exc), db_path=db_path)

    if state["surface"] != EMAIL_SEND_SURFACE:
        return _blocked_receipt(
            packet_id=packet_id,
            detail=f"Packet surface is {state['surface']!r}, not 'email_send'. Nothing was sent.",
            db_path=db_path,
            meta={"approval_state": state},
        )
    if state["stale"]:
        return _blocked_receipt(
            packet_id=packet_id,
            detail="Packet stale-hash check failed. Nothing was sent.",
            db_path=db_path,
            meta={"approval_state": state},
        )
    if Path(send_hold_path).is_file():
        return _blocked_receipt(
            packet_id=packet_id,
            detail="SEND_HOLD is active. Email send is blocked; nothing was sent.",
            db_path=db_path,
            meta={"approval_state": state, "send_hold_active": True},
        )
    if not state["execution_allowed"]:
        return _blocked_receipt(
            packet_id=packet_id,
            detail="Packet is not execution-approved. Nothing was sent.",
            db_path=db_path,
            meta={"approval_state": state, "send_hold_active": False},
        )
    if email_sender is None:
        return _blocked_receipt(
            packet_id=packet_id,
            detail="No approved email transport is attached to this scaffold. Nothing was sent.",
            db_path=db_path,
            meta={"approval_state": state, "send_hold_active": False},
        )

    return _blocked_receipt(
        packet_id=packet_id,
        detail="Live email transport remains intentionally disabled in this scaffold. Nothing was sent.",
        db_path=db_path,
        meta={"approval_state": state, "send_hold_active": False, "transport_supplied_but_not_called": True},
    )


__all__ = [
    "DEFAULT_SEND_HOLD_PATH",
    "EMAIL_SEND_EXECUTOR_VERSION",
    "EMAIL_SEND_GMAIL_SCOPE_DECISION_FOR_WINSHIP",
    "EMAIL_SEND_SURFACE",
    "build_email_send_executor",
    "email_send_executor_descriptor",
    "email_send_executor_registered",
    "execute_email_send_packet",
]
