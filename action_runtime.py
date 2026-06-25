"""
action_runtime.py — Flag-gated Slice-2 action runtime coordinator.

This module is the ONLY place that:
  1. Registers the synthetic_noop executor into chief_compose.EXECUTORS
  2. Provides the correlated dispatch entrypoint (dispatch_action)
  3. Populates conversation_capsule.recent_receipt_refs after a receipt

FLAG GATE — OPENCLAW_ACTION_RUNTIME (default OFF)
-------------------------------------------------
When OFF:
  - register_synthetic_executor() is a no-op
  - dispatch_action() raises RuntimeError immediately (belt-and-suspenders)
  - chief_compose.EXECUTORS is byte-identical to base a89a4dee
  - NO synthetic_noop, NO new behaviour anywhere

When ON:
  - synthetic_noop is registered in chief_compose on first call to
    register_synthetic_executor() (or via ensure_runtime_registered())
  - dispatch_action() runs the full gated loop

BINDING RULES (enforced here, not just in tests)
-------------------------------------------------
- authority_gate.decide() is ALWAYS consulted before any executor call.
- If verdict != ALLOW → the executor is NOT called.
- HITL_REQUIRED → a pending action is created (WAITING_FOR_APPROVAL).
- email_send_executor and all real-effect executors remain UNREGISTERED.
- No network, no file mutation outside the business_ops_ledger + capsule store.

ExecutionReceipt correlation
----------------------------
The spec requires conversation_id + package_id on each receipt.  ExecutionReceipt
is a frozen dataclass with a `meta: dict` field.  We inject correlation into meta
so the downstream shape is additive and non-breaking.  The helper
correlated_receipt() wraps any ExecutionReceipt with:
    meta["conversation_id"] = conversation_id
    meta["package_id"]      = package_id

Capsule receipt-ref population
-------------------------------
After a receipt is produced (flag ON), append_receipt_to_capsule() appends
    f"action:{conversation_id}:{package_id}:{receipt.packet_id}"
to the capsule's recent_receipt_refs via ConversationCapsuleStore.write().
"""

from __future__ import annotations

import os
import uuid
from dataclasses import replace
from typing import Any

from compose_contract import ExecutionReceipt


# ── Flag helper ───────────────────────────────────────────────────────────────


def _action_runtime_enabled() -> bool:
    """Return True only when OPENCLAW_ACTION_RUNTIME=1 (default OFF)."""
    return os.environ.get("OPENCLAW_ACTION_RUNTIME", "0").strip().lower() in ("1", "true", "yes")


# ── Receipt correlation helper ────────────────────────────────────────────────


def correlated_receipt(
    receipt: ExecutionReceipt,
    *,
    conversation_id: str,
    package_id: str,
) -> ExecutionReceipt:
    """
    Return a new ExecutionReceipt (frozen dataclass replace) with
    conversation_id and package_id injected into meta.

    Additive: existing meta keys are preserved.  Does NOT break any
    existing ExecutionReceipt consumer because meta is already dict[str,Any].
    """
    meta = dict(receipt.meta)
    meta["conversation_id"] = conversation_id
    meta["package_id"] = package_id
    return replace(receipt, meta=meta)


# ── Capsule receipt-ref population ───────────────────────────────────────────


def append_receipt_to_capsule(
    *,
    conversation_id: str,
    package_id: str,
    receipt: ExecutionReceipt,
    operator_id: str = "op1",
    agent_id: str = "action_runtime",
    channel_id: str = "synthetic",
    store_dir: str | None = None,
) -> bool:
    """
    Append a receipt ref to the capsule's recent_receipt_refs.

    ref format: "action:{conversation_id}:{package_id}:{receipt.packet_id}"

    Returns True on success, False if the capsule could not be loaded/written
    (non-fatal — the receipt itself is still valid).
    """
    try:
        import conversation_capsule as cc

        kwargs: dict[str, Any] = {}
        if store_dir is not None:
            kwargs["store_dir"] = store_dir

        store = cc.ConversationCapsuleStore(**kwargs)
        capsule = store.load(operator_id, agent_id, conversation_id, channel_id)
        if capsule is None:
            capsule = cc.Capsule.cold_start(
                agent_id=agent_id,
                operator_id=operator_id,
                conversation_id=conversation_id,
                channel_id=channel_id,
            )

        ref = f"action:{conversation_id}:{package_id}:{receipt.packet_id}"
        new_refs = list(capsule.recent_receipt_refs) + [ref]
        # Dataclass is not frozen so we can assign directly.
        capsule.recent_receipt_refs = new_refs

        store.write(operator_id, agent_id, conversation_id, channel_id, capsule)
        return True
    except Exception:
        return False


# ── Synthetic no-op executor ─────────────────────────────────────────────────


def _synthetic_noop_executor(
    *,
    packet_id: str,
    db_path: str | None = None,
) -> ExecutionReceipt:
    """
    Synthetic no-op executor.

    Returns a successful ExecutionReceipt with NO side effect, NO network,
    NO file mutation.  This is the ONLY executor registered by this slice.
    """
    return ExecutionReceipt(
        packet_id=packet_id,
        surface="synthetic_noop",
        ok=True,
        detail="synthetic_noop: no real action taken; this is a safe dry-run.",
        meta={"synthetic": True, "no_side_effect": True},
    )


# ── Registration (flag-gated) ─────────────────────────────────────────────────


def register_synthetic_executor() -> None:
    """
    Register synthetic_noop into chief_compose.EXECUTORS.

    NO-OP when OPENCLAW_ACTION_RUNTIME is OFF.  Safe to call multiple times
    (re-registration of the same function is idempotent).

    BINDING RULE: email_send_executor and any real-effect executor are NEVER
    registered here.  Only synthetic_noop.
    """
    if not _action_runtime_enabled():
        return
    from chief_compose import register_executor

    register_executor("synthetic_noop", _synthetic_noop_executor)


def ensure_runtime_registered() -> bool:
    """
    Idempotent initialisation guard.  Returns True if the flag is ON
    (and registration was performed/re-confirmed), False if flag is OFF.
    """
    if not _action_runtime_enabled():
        return False
    register_synthetic_executor()
    return True


# ── HITL pending-action creation ──────────────────────────────────────────────


def _create_hitl_pending(
    surface: str,
    package_id: str,
    conversation_id: str,
) -> str | None:
    """
    Create a HITL pending action (WAITING_FOR_APPROVAL).

    Returns the action_id or None if HITL is disabled / creation fails.
    Wraps hitl_pending_action.create_pending_action() exactly.
    """
    try:
        from hitl_pending_action import create_pending_action, is_hitl_enabled

        if not is_hitl_enabled():
            # HITL disabled — we still surface HITL_REQUIRED to the caller
            # but cannot create a store entry.
            return None

        return create_pending_action(
            source_agent="action_runtime",
            action_type=surface,
            payload={
                "surface": surface,
                "package_id": package_id,
                "conversation_id": conversation_id,
            },
        )
    except Exception:
        return None


# ── Main gated dispatch entrypoint ────────────────────────────────────────────


def dispatch_action(
    *,
    surface: str,
    packet_id: str,
    conversation_id: str = "",
    package_id: str = "",
    send_hold_path: str | None = None,
    db_path: str | None = None,
    capsule_store_dir: str | None = None,
    operator_id: str = "op1",
    agent_id: str = "action_runtime",
    channel_id: str = "synthetic",
) -> dict[str, Any]:
    """
    Full gated action dispatch (flag ON only).

    Flow:
        authority_gate.decide() → verdict
        ALLOW      → chief_compose.execute_packet_with_state(packet_id, surface)
                     → correlated_receipt → append_receipt_to_capsule
        HITL_REQUIRED → create_hitl_pending() → WAITING (no execute)
        DENY       → return decision without executing

    Returns a dict with:
        verdict:        str ("ALLOW" | "HITL_REQUIRED" | "DENY")
        reason:         str
        receipt:        dict | None  (serialisable ExecutionReceipt, if executed)
        hitl_action_id: str | None  (if HITL_REQUIRED and store available)
        gate_ref:       str | None  (ledger ref from authority_gate)
        capsule_updated: bool
    """
    if not _action_runtime_enabled():
        raise RuntimeError(
            "dispatch_action called but OPENCLAW_ACTION_RUNTIME is OFF. "
            "This is a programming error — check caller."
        )

    from authority_gate import decide, DEFAULT_SEND_HOLD_PATH, Verdict

    effective_send_hold = send_hold_path or str(DEFAULT_SEND_HOLD_PATH)

    decision = decide(
        surface,
        conversation_id=conversation_id,
        surface=surface,
        send_hold_path=effective_send_hold,
        db_path=db_path,
    )

    out: dict[str, Any] = {
        "verdict": decision.verdict.value,
        "reason": decision.reason,
        "receipt": None,
        "hitl_action_id": None,
        "gate_ref": decision.ledger_receipt_ref,
        "capsule_updated": False,
    }

    if decision.verdict == Verdict.ALLOW:
        # Ensure the executor is registered.
        ensure_runtime_registered()

        from chief_compose import execute_packet_with_state

        raw_receipt = execute_packet_with_state(
            packet_id,
            surface=surface,
            db_path=db_path,
        )

        # Inject conversation_id + package_id into the receipt meta.
        eff_package_id = package_id or packet_id
        receipt = correlated_receipt(
            raw_receipt,
            conversation_id=conversation_id,
            package_id=eff_package_id,
        )

        out["receipt"] = {
            "packet_id": receipt.packet_id,
            "surface": receipt.surface,
            "ok": receipt.ok,
            "detail": receipt.detail,
            "side_effect_id": receipt.side_effect_id,
            "meta": dict(receipt.meta),
        }

        # Populate capsule.recent_receipt_refs.
        updated = append_receipt_to_capsule(
            conversation_id=conversation_id,
            package_id=eff_package_id,
            receipt=receipt,
            operator_id=operator_id,
            agent_id=agent_id,
            channel_id=channel_id,
            store_dir=capsule_store_dir,
        )
        out["capsule_updated"] = updated

    elif decision.verdict == Verdict.HITL_REQUIRED:
        action_id = _create_hitl_pending(surface, package_id, conversation_id)
        out["hitl_action_id"] = action_id

    # DENY: no executor called, no capsule update, no HITL record.
    return out
