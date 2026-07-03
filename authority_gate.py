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
synthetic executor is never registered.  decide() itself is flag-agnostic and
records to the ledger regardless; for send surfaces it also validates the
SEND_HOLD sentinel before returning a decision.

SEND_HOLD behaviour
-------------------
Any surface in _SEND_SURFACES is DENY when the SEND_HOLD file exists. A
sentinel that has unsafe permissions, cannot be stat()ed, or is not a regular
file fails closed and emits an alert. Callers that have an external reason to
expect SEND_HOLD to be active can opt into treating a missing sentinel as
tamper/vanish.
An absent sentinel without that explicit expectation is treated as the operator's
deliberate SEND_HOLD-off state and is not recreated.

Allow-list (this slice)
-----------------------
ONLY "synthetic_noop" is allow-listed as ALLOW.
All real-effect surfaces (email_send, invoice_send, calendar_create, …)
return HITL_REQUIRED or DENY — never ALLOW from this gate.
"""

from __future__ import annotations

import logging
import os
import stat
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable

# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_SEND_HOLD_PATH: Path = Path("/mnt/e/openclaw/orchestration/SEND_HOLD.md")
SEND_HOLD_SENTINEL_TIGHT_MODE = 0o600
SEND_HOLD_SENTINEL_ALLOWED_MODES: frozenset[int] = frozenset({0o600, 0o640})
SEND_HOLD_SENTINEL_ALERT_SCHEMA = "SEND_HOLD_SENTINEL_ALERT_V0"

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


@dataclass(frozen=True)
class SendHoldSentinelState:
    send_hold_active: bool
    fail_closed: bool
    path: str
    reason: str
    mode: str | None = None
    alert_type: str | None = None
    self_healed: bool = False
    chmod_attempted: bool = False
    chmod_succeeded: bool | None = None


def _mode_text(mode: int | None) -> str | None:
    if mode is None:
        return None
    return f"0o{mode:03o}"


def _emit_send_hold_sentinel_alert(
    *,
    alert_type: str,
    path: Path,
    summary: str,
    observed_mode: int | None,
    alert_sink: Callable[[dict[str, Any]], Any] | None,
    self_healed: bool = False,
    chmod_attempted: bool = False,
    chmod_succeeded: bool | None = None,
    error: str | None = None,
) -> None:
    alert = {
        "schema_version": SEND_HOLD_SENTINEL_ALERT_SCHEMA,
        "alert_type": alert_type,
        "severity": "critical",
        "summary": summary,
        "send_hold_path": str(path),
        "observed_mode": _mode_text(observed_mode),
        "send_hold_active": True,
        "fail_closed": True,
        "self_healed": bool(self_healed),
        "chmod_attempted": bool(chmod_attempted),
        "chmod_succeeded": chmod_succeeded,
    }
    if error:
        alert["error"] = error

    if alert_sink is not None:
        try:
            alert_sink(dict(alert))
            return
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "SEND_HOLD sentinel alert sink failed for %s: %s",
                path,
                exc,
            )
    logging.getLogger(__name__).warning("%s", summary)


def _recreate_send_hold_sentinel(path: Path) -> tuple[bool, int | None, str | None]:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, SEND_HOLD_SENTINEL_TIGHT_MODE)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("SEND_HOLD self-healed vanished sentinel; external sends remain blocked.\n")
        try:
            path.chmod(SEND_HOLD_SENTINEL_TIGHT_MODE)
        except OSError:
            pass
        return True, stat.S_IMODE(path.stat().st_mode), None
    except FileExistsError:
        return True, None, None
    except OSError as exc:
        return False, None, str(exc)


def ensure_send_hold_sentinel(
    send_hold_path: str | Path = DEFAULT_SEND_HOLD_PATH,
    *,
    alert_sink: Callable[[dict[str, Any]], Any] | None = None,
    missing_is_tamper: bool = False,
) -> SendHoldSentinelState:
    """Read and harden the SEND_HOLD sentinel without trapping deliberate lifts.

    Missing is the operator-lifted state unless a caller explicitly supplies an
    external expectation that absence is tamper/vanish.
    """

    path = Path(send_hold_path)

    if not path.exists():
        if not missing_is_tamper:
            return SendHoldSentinelState(
                send_hold_active=False,
                fail_closed=False,
                path=str(path),
                reason=f"SEND_HOLD sentinel absent ({path}); hold is not active.",
            )

        self_healed, observed_mode, error = _recreate_send_hold_sentinel(path)
        summary = (
            "SEND_HOLD sentinel is missing despite an active-hold expectation; external sends remain held fail-closed."
            if self_healed
            else "SEND_HOLD sentinel is missing despite an active-hold expectation and could not be recreated; external sends remain held fail-closed."
        )
        chmod_succeeded = (
            observed_mode in SEND_HOLD_SENTINEL_ALLOWED_MODES
            if self_healed and observed_mode is not None
            else None
        )
        _emit_send_hold_sentinel_alert(
            alert_type="send_hold_sentinel_vanished",
            path=path,
            summary=summary,
            observed_mode=observed_mode,
            alert_sink=alert_sink,
            self_healed=self_healed,
            chmod_attempted=self_healed,
            chmod_succeeded=chmod_succeeded,
            error=error,
        )
        return SendHoldSentinelState(
            send_hold_active=True,
            fail_closed=True,
            path=str(path),
            reason=summary,
            mode=_mode_text(observed_mode),
            alert_type="send_hold_sentinel_vanished",
            self_healed=self_healed,
            chmod_attempted=self_healed,
            chmod_succeeded=chmod_succeeded,
        )

    try:
        current_stat = path.stat()
    except OSError as exc:
        summary = "SEND_HOLD sentinel could not be stat()ed; external sends remain held fail-closed."
        _emit_send_hold_sentinel_alert(
            alert_type="send_hold_sentinel_stat_failed",
            path=path,
            summary=summary,
            observed_mode=None,
            alert_sink=alert_sink,
            error=str(exc),
        )
        return SendHoldSentinelState(
            send_hold_active=True,
            fail_closed=True,
            path=str(path),
            reason=summary,
            alert_type="send_hold_sentinel_stat_failed",
        )

    observed_mode = stat.S_IMODE(current_stat.st_mode)
    if not path.is_file():
        summary = "SEND_HOLD sentinel path is not a regular file; external sends remain held fail-closed."
        _emit_send_hold_sentinel_alert(
            alert_type="send_hold_sentinel_invalid_type",
            path=path,
            summary=summary,
            observed_mode=observed_mode,
            alert_sink=alert_sink,
        )
        return SendHoldSentinelState(
            send_hold_active=True,
            fail_closed=True,
            path=str(path),
            reason=summary,
            mode=_mode_text(observed_mode),
            alert_type="send_hold_sentinel_invalid_type",
        )

    original_mode = observed_mode
    world_writable = bool(original_mode & 0o002)
    chmod_attempted = False
    chmod_succeeded: bool | None = None
    chmod_error: str | None = None

    if observed_mode not in SEND_HOLD_SENTINEL_ALLOWED_MODES:
        chmod_attempted = True
        try:
            path.chmod(SEND_HOLD_SENTINEL_TIGHT_MODE)
            observed_mode = stat.S_IMODE(path.stat().st_mode)
            chmod_succeeded = observed_mode in SEND_HOLD_SENTINEL_ALLOWED_MODES
        except OSError as exc:
            chmod_succeeded = False
            chmod_error = str(exc)

    alert_type: str | None = None
    summary: str | None = None
    if world_writable:
        alert_type = "send_hold_sentinel_world_writable"
        summary = "SEND_HOLD sentinel was world-writable; external sends remain held fail-closed."
    elif chmod_attempted and chmod_succeeded is False:
        alert_type = "send_hold_sentinel_chmod_failed"
        summary = "SEND_HOLD sentinel permissions could not be tightened; external sends remain held fail-closed."

    if alert_type and summary:
        _emit_send_hold_sentinel_alert(
            alert_type=alert_type,
            path=path,
            summary=summary,
            observed_mode=original_mode,
            alert_sink=alert_sink,
            chmod_attempted=chmod_attempted,
            chmod_succeeded=chmod_succeeded,
            error=chmod_error,
        )
        reason = summary
    else:
        reason = f"SEND_HOLD is active ({path})."

    return SendHoldSentinelState(
        send_hold_active=True,
        fail_closed=True,
        path=str(path),
        reason=reason,
        mode=_mode_text(observed_mode),
        alert_type=alert_type,
        chmod_attempted=chmod_attempted,
        chmod_succeeded=chmod_succeeded,
    )


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
    send_hold_alert_sink: Callable[[dict[str, Any]], Any] | None = None,
    send_hold_missing_is_tamper: bool = False,
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
    # Missing with explicit tamper expectation or tampered sentinel state is held.

    if resolved_surface in _SEND_SURFACES:
        send_hold_state = ensure_send_hold_sentinel(
            send_hold_path,
            alert_sink=send_hold_alert_sink,
            missing_is_tamper=send_hold_missing_is_tamper,
        )
    else:
        send_hold_state = None

    if send_hold_state and send_hold_state.send_hold_active:
        verdict = Verdict.DENY
        reason = (
            f"{send_hold_state.reason} "
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
