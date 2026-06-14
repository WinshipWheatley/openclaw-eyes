"""Unified composer seam for safe operator messages.

This module is additive and not wired into the running listener. It gives the
future API a single front door:

    PII redaction -> deterministic intent route -> read-only reply or gated
    work packet -> human approval -> executor.

The executor registry is empty by default. Nothing sends or mutates external
systems unless a future surface is explicitly registered and approved.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from compose_contract import ComposeResult, ExecutionReceipt, GateState, is_action_intent


DEFAULT_SOURCE_KIND = "mission_control"
DEFAULT_SOURCE_CHANNEL = "mac_app"
DEFAULT_REQUESTED_BY = "winship"


def _branch_for(result: Any) -> str:
    """Return blocked, gated, or fast. Missing fields fail toward gated."""
    rejection = getattr(result, "rejection_reason", None)
    status = getattr(result, "status", "") or ""
    if rejection or status.lower() == "rejected":
        return "blocked"
    if getattr(result, "approval_required", True):
        return "gated"
    return "fast"


def _segments_from_routed(routed: dict[str, Any]) -> list[str]:
    replies = routed.get("replies")
    if isinstance(replies, list) and replies:
        return [str(reply) for reply in replies if str(reply).strip()]
    reply = routed.get("reply")
    return [str(reply)] if reply and str(reply).strip() else []


def _gate_convergence_preview(surface: str) -> dict[str, Any]:
    from approval_gate_convergence import convergence_for_surface

    return convergence_for_surface(surface)


def compose(
    text: str,
    *,
    source_kind: str = DEFAULT_SOURCE_KIND,
    source_channel: str = DEFAULT_SOURCE_CHANNEL,
    requested_by: str = DEFAULT_REQUESTED_BY,
    source_message_id: str | None = None,
    db_path: str | None = None,
) -> ComposeResult:
    text = (text or "").strip()
    if not text:
        return ComposeResult.read_only("empty", ["Say or type something and I will route it."])

    from intent_router import route_operator_intent
    from pii_vault import redact_text

    redacted, _token_map = redact_text(text)
    result = route_operator_intent(
        text=redacted,
        source_kind=source_kind,
        source_channel=source_channel,
        requested_by=requested_by,
        source_message_id=source_message_id,
        db_path=db_path,
    )
    intent = getattr(result, "candidate_action_type", None) or getattr(result, "intent_category", "unknown")
    branch = _branch_for(result)

    if branch == "blocked":
        reason = getattr(result, "rejection_reason", None) or "That request was refused at intake."
        return ComposeResult.blocked(intent, str(reason), run_id=getattr(result, "run_id", None))

    if branch == "gated":
        from agent_work_packet import build_agent_work_packet, get_agent_work_packet_approval_state

        packet = build_agent_work_packet(
            intent_id=getattr(result, "intent_id", None),
            run_id=getattr(result, "run_id", None),
            db_path=db_path,
        )
        packet_state = get_agent_work_packet_approval_state(
            packet_id=getattr(packet, "packet_id", "unknown"),
            db_path=db_path,
        )
        goal = getattr(packet, "goal", "") or "Proposed action"
        surface = intent or "unknown"
        return ComposeResult.pending(
            intent=intent,
            packet_id=getattr(packet, "packet_id", "unknown"),
            surface=surface,
            segments=[goal, "Nothing has been sent yet.", "Review the approval card, then approve, edit, or cancel."],
            preview={
                "goal": goal,
                "candidate_action_type": getattr(result, "candidate_action_type", None),
                "world_hint": getattr(result, "world_hint", None),
                "execution_allowed": getattr(packet, "execution_allowed", False),
                "button_label": _button_label_for_surface(surface),
                "packet_hash": packet_state.packet_hash,
                "gate_convergence": _gate_convergence_preview(surface),
            },
            run_id=getattr(result, "run_id", None),
            next_safe_move=getattr(result, "next_safe_move", None),
        )

    from chief_router import route_message

    routed = route_message(text)
    routed_intent = routed.get("intent", intent)
    if is_action_intent(routed_intent):
        return ComposeResult(
            intent=routed_intent,
            gate_state=GateState.BLOCKED,
            segments=[
                "Routing disagreement: intake marked this safe but the legacy router "
                "treats it as an action. Held for review; not executed.",
            ],
            meta={
                "a1_intent": intent,
                "router_intent": routed_intent,
                "needs": "taxonomy_alignment",
            },
        )
    return ComposeResult.read_only(
        routed_intent,
        _segments_from_routed(routed),
        run_id=getattr(result, "run_id", None),
    )


def _button_label_for_surface(surface: str) -> str:
    labels = {
        "invoice_send": "Approve invoice send",
        "email_send": "Approve email send",
        "sms_send": "Approve text send",
        "phone_log": "Approve phone action",
        "calendar_create": "Approve calendar create",
        "ledger_mutation": "Approve ledger change",
        "coupa_submit": "Approve Coupa submit",
        "obs_launch": "Approve OBS launch",
        "livestream_setup": "Approve livestream setup",
    }
    return labels.get(surface, f"Approve {surface.replace('_', ' ')}")


EXECUTORS: dict[str, Callable[..., ExecutionReceipt]] = {}


def register_executor(surface: str, fn: Callable[..., ExecutionReceipt]) -> None:
    EXECUTORS[surface] = fn


def execute_packet(packet_id: str, *, surface: str, db_path: str | None = None) -> ExecutionReceipt:
    return execute_packet_with_state(packet_id, surface=surface, db_path=db_path)


def get_packet_approval_state(
    packet_id: str,
    *,
    expected_packet_hash: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    from agent_work_packet import get_agent_work_packet_approval_state

    return get_agent_work_packet_approval_state(
        packet_id=packet_id,
        expected_packet_hash=expected_packet_hash,
        db_path=db_path,
    ).to_dict()


def _record_executor_side_effect(
    *,
    packet_id: str,
    surface: str,
    status: str,
    db_path: str | None = None,
) -> str | None:
    from business_ops_ledger import append_side_effect, init_business_ops_ledger

    init_business_ops_ledger(db_path)
    return append_side_effect(
        packet_id=packet_id,
        effect_type=surface,
        status=status,
        approval_required=True,
        approval_tier="operator_final_send",
        replay_safe=False,
        external_ref=None,
        db_path=db_path,
    )


def _with_side_effect_receipt(receipt: ExecutionReceipt, *, status: str, db_path: str | None = None) -> ExecutionReceipt:
    if receipt.side_effect_id:
        return receipt
    side_effect_id = _record_executor_side_effect(
        packet_id=receipt.packet_id,
        surface=receipt.surface,
        status=status,
        db_path=db_path,
    )
    meta = dict(receipt.meta)
    meta["side_effect_recorded"] = bool(side_effect_id)
    return replace(receipt, side_effect_id=side_effect_id, meta=meta)


def execute_packet_with_state(
    packet_id: str,
    *,
    surface: str,
    db_path: str | None = None,
    expected_packet_hash: str | None = None,
) -> ExecutionReceipt:
    if expected_packet_hash is not None:
        try:
            state = get_packet_approval_state(
                packet_id,
                expected_packet_hash=expected_packet_hash,
                db_path=db_path,
            )
        except ValueError as exc:
            receipt = ExecutionReceipt(packet_id=packet_id, surface=surface, ok=False, detail=str(exc))
            return _with_side_effect_receipt(receipt, status="blocked_packet_state_unavailable", db_path=db_path)
        if state["stale"]:
            receipt = ExecutionReceipt(
                packet_id=packet_id,
                surface=surface,
                ok=False,
                detail="Packet stale-hash check failed. Nothing was sent.",
                meta={"approval_state": state},
            )
            return _with_side_effect_receipt(receipt, status="blocked_stale_hash", db_path=db_path)
    fn = EXECUTORS.get(surface)
    if fn is None:
        receipt = ExecutionReceipt(
            packet_id=packet_id,
            surface=surface,
            ok=False,
            detail=f"No executor wired for surface '{surface}'. Nothing was sent.",
        )
        return _with_side_effect_receipt(receipt, status="blocked_no_executor", db_path=db_path)
    try:
        receipt = fn(packet_id=packet_id, db_path=db_path)
        return _with_side_effect_receipt(
            receipt,
            status="executor_ok" if receipt.ok else "executor_failed",
            db_path=db_path,
        )
    except Exception as exc:
        receipt = ExecutionReceipt(
            packet_id=packet_id,
            surface=surface,
            ok=False,
            detail=f"Executor error: {exc}",
        )
        return _with_side_effect_receipt(receipt, status="executor_exception", db_path=db_path)


def _register_default_executors() -> None:
    from invoice_send_executor import execute_invoice_send_packet

    register_executor("invoice_send", execute_invoice_send_packet)


_register_default_executors()
