"""
authority_gate.py — D6 canonical authority gate (Slice 2, flag-gated).

All action paths consult decide() before any executor is called.
The gate is DEFAULT-DENY: only explicitly allow-listed safe synthetic
surfaces receive ALLOW.  Every decision is recorded to business_ops_ledger.

Flag gate
---------
_action_runtime_enabled() reads OPENCLAW_ACTION_RUNTIME (env, default "0").
When OFF the module is importable and all functions are callable, but the live
execution path in action_runtime.py will never reach decide() because the
synthetic executor is never registered.  decide() itself is stateless and
flag-agnostic — it is pure/deterministic and records to the ledger regardless.

SEND_HOLD behaviour
-------------------
Any surface in _SEND_SURFACES is DENY when the SEND_HOLD file exists.

Allow-list (this slice)
-----------------------
ONLY "synthetic_noop" is allow-listed as ALLOW.
All real-effect surfaces (email_send, invoice_send, calendar_create, …)
return HITL_REQUIRED or DENY — never ALLOW from this gate.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_SEND_HOLD_PATH: Path = Path("/mnt/e/openclaw/orchestration/SEND_HOLD.md")

# Surfaces that are DENY when SEND_HOLD is present.
_SEND_SURFACES: frozenset[str] = frozenset(
    {
        "email_send",
        "invoice_send",
        "sms_send",
        "phone_log",
        "calendar_create",
        "ledger_mutation",
        "coupa_submit",
        "obs_launch",
        "livestream_setup",
    }
)

# Surfaces that require HITL approval before any real execution.
# (This gate never auto-ALLOWs real-effect surfaces.)
_HITL_REQUIRED_SURFACES: frozenset[str] = _SEND_SURFACES | frozenset(
    {
        "bank_transfer",
        "payroll_submit",
        "contract_sign",
    }
)

# The ONLY allow-listed safe synthetic surface for this slice.
_ALLOWED_SYNTHETIC_SURFACES: frozenset[str] = frozenset({"synthetic_noop"})


# ── Flag helper ───────────────────────────────────────────────────────────────


def _action_runtime_enabled() -> bool:
    """Return True only when OPENCLAW_ACTION_RUNTIME=1 (default OFF)."""
    return os.environ.get("OPENCLAW_ACTION_RUNTIME", "0").strip().lower() in ("1", "true", "yes")


# ── Result types ──────────────────────────────────────────────────────────────


class Verdict(str, Enum):
    ALLOW = "ALLOW"
    HITL_REQUIRED = "HITL_REQUIRED"
    DENY = "DENY"


@dataclass(frozen=True)
class AuthorityDecision:
    verdict: Verdict
    reason: str
    ledger_receipt_ref: str | None = None
    surface: str = ""
    conversation_id: str = ""
    package_id: str = ""


# ── Ledger recording ──────────────────────────────────────────────────────────


def _record_gate_decision(
    *,
    surface: str,
    verdict: Verdict,
    reason: str,
    conversation_id: str,
    package_id: str,
    db_path: str | None,
) -> str | None:
    """
    Record every gate decision to business_ops_ledger.
    Uses record_action_intent_gate_receipt which maps naturally to gate events.
    Returns the event-level receipt ref, or None on ledger failure (non-fatal).
    """
    try:
        from business_ops_ledger import record_action_intent_gate_receipt, init_business_ops_ledger

        init_business_ops_ledger(db_path)

        gate_result = verdict.value.lower()  # "allow", "hitl_required", "deny"
        packet_id = package_id or f"gate_only_{uuid.uuid4().hex[:8]}"
        summary = (
            f"authority_gate verdict={verdict.value} surface={surface!r} "
            f"conversation_id={conversation_id!r} reason={reason!r}"
        )

        ok = record_action_intent_gate_receipt(
            packet_id=packet_id,
            packet_type=f"authority_gate:{surface}",
            gate_result=gate_result,
            evaluation_summary=summary,
            actor="authority_gate",
            db_path=db_path,
            approval_required=1 if verdict != Verdict.ALLOW else 0,
            send_hold_consulted=True,
        )

        if ok:
            return f"aig_gate_{surface}_{gate_result}"
        return None
    except Exception:
        # Ledger failure is non-fatal for the gate decision itself.
        return None


# ── Core gate ─────────────────────────────────────────────────────────────────


def decide(
    package_or_surface: Any,
    conversation_id: str = "",
    surface: str = "",
    *,
    send_hold_path: str | Path = DEFAULT_SEND_HOLD_PATH,
    db_path: str | None = None,
) -> AuthorityDecision:
    """
    Canonical authority gate decision.

    Parameters
    ----------
    package_or_surface : WorkerExecutionPackagePlan | str
        Either a WorkerExecutionPackagePlan (D5) or a bare surface string.
        The surface is extracted from the package if not provided explicitly.
    conversation_id : str
        Conversation correlation key (from the Slice-1 capsule).
    surface : str
        Override surface string; takes precedence over package.allowed_actions.
    send_hold_path : Path | str
        Path to the SEND_HOLD sentinel file.  Defaults to the canonical prod path.
    db_path : str | None
        SQLite path forwarded to business_ops_ledger.  None = default ledger.

    Returns
    -------
    AuthorityDecision
        verdict: ALLOW | HITL_REQUIRED | DENY
        reason: human-readable explanation
        ledger_receipt_ref: opaque ref from the ledger (may be None on ledger error)
        surface: the resolved surface string
        conversation_id: echoed back for correlation
        package_id: extracted package ID if available

    DEFAULT-DENY contract
    ---------------------
    Any surface not in _ALLOWED_SYNTHETIC_SURFACES → DENY or HITL_REQUIRED.
    Any send surface with SEND_HOLD present → DENY (highest priority).
    Unknown surface → DENY.
    """

    # ── Resolve surface and package_id ────────────────────────────────────────

    resolved_surface = surface
    package_id = ""

    if not resolved_surface:
        # Try to extract from a WorkerExecutionPackagePlan or similar object.
        if hasattr(package_or_surface, "allowed_actions"):
            actions = getattr(package_or_surface, "allowed_actions", ()) or ()
            resolved_surface = actions[0] if actions else ""
        elif isinstance(package_or_surface, str):
            resolved_surface = package_or_surface

    if hasattr(package_or_surface, "package_plan_id"):
        package_id = str(package_or_surface.package_plan_id)

    resolved_surface = (resolved_surface or "").strip()

    # ── Unknown / empty surface → DENY (default-deny) ────────────────────────

    if not resolved_surface:
        verdict = Verdict.DENY
        reason = "No surface resolved from package or surface argument; default-deny."
        ref = _record_gate_decision(
            surface="(empty)",
            verdict=verdict,
            reason=reason,
            conversation_id=conversation_id,
            package_id=package_id,
            db_path=db_path,
        )
        return AuthorityDecision(
            verdict=verdict,
            reason=reason,
            ledger_receipt_ref=ref,
            surface="(empty)",
            conversation_id=conversation_id,
            package_id=package_id,
        )

    # ── SEND_HOLD check (highest priority for send surfaces) ─────────────────
    #
    # Mirrors the pattern in email_send_executor.py ~line 401:
    #   if Path(send_hold_path).is_file(): → block
    #
    # Any surface in _SEND_SURFACES is DENY when the sentinel file exists.

    if resolved_surface in _SEND_SURFACES and Path(send_hold_path).is_file():
        verdict = Verdict.DENY
        reason = (
            f"SEND_HOLD is active ({send_hold_path}). "
            f"Surface '{resolved_surface}' is blocked; nothing was sent."
        )
        ref = _record_gate_decision(
            surface=resolved_surface,
            verdict=verdict,
            reason=reason,
            conversation_id=conversation_id,
            package_id=package_id,
            db_path=db_path,
        )
        return AuthorityDecision(
            verdict=verdict,
            reason=reason,
            ledger_receipt_ref=ref,
            surface=resolved_surface,
            conversation_id=conversation_id,
            package_id=package_id,
        )

    # ── Safe synthetic allow-list ─────────────────────────────────────────────

    if resolved_surface in _ALLOWED_SYNTHETIC_SURFACES:
        verdict = Verdict.ALLOW
        reason = f"Surface '{resolved_surface}' is allow-listed as a safe synthetic action."
        ref = _record_gate_decision(
            surface=resolved_surface,
            verdict=verdict,
            reason=reason,
            conversation_id=conversation_id,
            package_id=package_id,
            db_path=db_path,
        )
        return AuthorityDecision(
            verdict=verdict,
            reason=reason,
            ledger_receipt_ref=ref,
            surface=resolved_surface,
            conversation_id=conversation_id,
            package_id=package_id,
        )

    # ── Real-effect surfaces → HITL_REQUIRED ─────────────────────────────────

    if resolved_surface in _HITL_REQUIRED_SURFACES:
        verdict = Verdict.HITL_REQUIRED
        reason = (
            f"Surface '{resolved_surface}' requires explicit operator approval "
            f"before execution (HITL_REQUIRED)."
        )
        ref = _record_gate_decision(
            surface=resolved_surface,
            verdict=verdict,
            reason=reason,
            conversation_id=conversation_id,
            package_id=package_id,
            db_path=db_path,
        )
        return AuthorityDecision(
            verdict=verdict,
            reason=reason,
            ledger_receipt_ref=ref,
            surface=resolved_surface,
            conversation_id=conversation_id,
            package_id=package_id,
        )

    # ── Default-deny: unknown / unregistered surface ──────────────────────────

    verdict = Verdict.DENY
    reason = (
        f"Surface '{resolved_surface}' is not on any allow-list; default-deny. "
        "Only explicitly allow-listed safe synthetic surfaces may execute."
    )
    ref = _record_gate_decision(
        surface=resolved_surface,
        verdict=verdict,
        reason=reason,
        conversation_id=conversation_id,
        package_id=package_id,
        db_path=db_path,
    )
    return AuthorityDecision(
        verdict=verdict,
        reason=reason,
        ledger_receipt_ref=ref,
        surface=resolved_surface,
        conversation_id=conversation_id,
        package_id=package_id,
    )
