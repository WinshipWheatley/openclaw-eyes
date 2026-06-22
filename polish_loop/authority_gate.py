"""authority_gate.py — Deterministic, fail-closed authority gate for the polish loop.

This module enforces agent-lane authority BEFORE any build task is executed.
Python reads rules to BLOCK; agents read rules to plan.

Design contract:
- check_task_authority() is the sole public interface.
- Returns {allowed: bool, reason: str, required_tier: str | None}.
- FAIL CLOSED: any error, missing field, unknown agent, unknown authority level → allowed=False.
- Consequence is an UN-DISCOUNTABLE HARD FLOOR: R3/R4 tasks are never allowed
  autonomously regardless of agent authority or packet quality.
- Integration point: call BEFORE promoting a queued task to task.md in handle_idle().

Task schema (fields expected on the task dict):
    agent_id (str, required)         — originating agent (e.g. "chief", "cassandra")
    consequence (str, optional)       — "R0"/"R1"/"R2"/"R3"/"R4" (inferred if absent)
    output_kind (str, optional)       — the output kind this task produces (cross-checked
                                        against agent's blocked_output_kinds)
    action (str, optional)            — free-form action text used for consequence inference

Consequence tiers:
    R0 = read-only                    advisory_only agents may run
    R1 = local writes / analysis      advisory_only agents may run
    R2 = draft / internal-only send   request_only agents may run; advisory_only blocked
    R3 = external-send / destructive  approval_required agents may run; lower blocked
    R4 = money / prod / irreversible  NEVER autonomous; always operator-gated (hard floor)

If consequence is not supplied, it is inferred from action/output_kind keywords.
When inference is ambiguous or fields are absent, consequence is elevated to be safe.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Authority level ordering (higher index = more authority)
# ---------------------------------------------------------------------------

_AUTHORITY_ORDER = [
    "advisory_only",      # index 0 — read-only / draft / local
    "request_only",       # index 1 — can request work, still needs approval
    "approval_required",  # index 2 — gate exists but agent passes it
    "future_gated",       # index 3 — placeholder; treated like advisory_only for safety
]

# Minimum authority level index required to run each consequence tier autonomously.
# R4 maps to None — never autonomous; always fails closed.
_CONSEQUENCE_MIN_AUTHORITY: dict[str, str | None] = {
    "R0": "advisory_only",
    "R1": "advisory_only",
    "R2": "request_only",
    "R3": "approval_required",
    "R4": None,  # hard floor — no autonomous execution ever
}

# ---------------------------------------------------------------------------
# Consequence inference keywords (applied to action + output_kind strings)
# ---------------------------------------------------------------------------

_R4_KEYWORDS = frozenset({
    "money", "payment", "pay", "invoice_paid", "wire", "transfer",
    "production", "prod", "irreversible", "identity", "secret",
    "credential", "merge_to_main", "deploy_to_prod", "force_push",
})

_R3_KEYWORDS = frozenset({
    "external_send", "send", "sending", "sent", "email", "sms", "push_notification",
    "destructive", "delete", "file_delete", "file_move", "daw_session_edit",
    "external_ledger_mutation", "truth_promotion", "canonical_promotion",
    "approval_decision", "direct_execution",
})

_R2_KEYWORDS = frozenset({
    "draft", "draft_message", "external_comms", "action_request", "marking_paid",
    "action_request_draft", "codex_work_packet",
})

# Output kinds explicitly blocked for each agent type (from agent_lane_registry).
# Used to detect over-scoped output_kind even if consequence tag is absent.
_HIGH_RISK_OUTPUT_KINDS = frozenset(
    _R4_KEYWORDS | _R3_KEYWORDS | {
        "client_deployment", "state_mutation", "truth_write",
        "secret_disclosure", "policy_mutation_without_approval",
    }
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _authority_index(level: str) -> int:
    """Return numeric authority index; unknown levels → -1 (treated as no authority)."""
    try:
        return _AUTHORITY_ORDER.index(level)
    except ValueError:
        return -1


def _infer_consequence(task: dict[str, Any]) -> str:
    """
    Infer consequence tier from action and output_kind fields.
    Errs on the side of elevation: returns the highest tier triggered,
    defaulting to "R2" when evidence is ambiguous (never R0/R1 on unknown input).
    """
    action = str(task.get("action", "")).lower()
    output_kind = str(task.get("output_kind", "")).lower()
    combined = f"{action} {output_kind}"

    # Check highest tiers first
    if any(kw in combined for kw in _R4_KEYWORDS):
        return "R4"
    if any(kw in combined for kw in _R3_KEYWORDS):
        return "R3"
    if any(kw in combined for kw in _R2_KEYWORDS):
        return "R2"

    # If no keywords match and no explicit consequence, default to R2 (cautious).
    # A task with a declared consequence of R0/R1 is trusted IF the field is explicit.
    return "R2"


def _lookup_agent(agent_id: str, registry: list[Any] | None) -> dict[str, Any] | None:
    """
    Return a normalized agent dict from registry.
    Accepts either AgentLaneSeed dataclass instances or plain dicts.
    Returns None if not found.
    """
    if not agent_id or not isinstance(agent_id, str):
        return None

    normalized = agent_id.strip().lower()

    # Default: import from agent_lane_registry if no registry provided
    if registry is None:
        try:
            from agent_lane_registry import DEFAULT_AGENT_LANE_SEEDS  # type: ignore[import]
            registry = list(DEFAULT_AGENT_LANE_SEEDS)
        except Exception:
            return None

    for entry in registry:
        # Support both AgentLaneSeed dataclass and plain dict
        if hasattr(entry, "agent_id"):
            if entry.agent_id == normalized:
                return {
                    "agent_id": entry.agent_id,
                    "authority_level": entry.authority_level,
                    "blocked_output_kinds": list(entry.blocked_output_kinds),
                    "status": entry.status,
                }
        elif isinstance(entry, dict):
            if entry.get("agent_id") == normalized:
                return {
                    "agent_id": entry.get("agent_id", ""),
                    "authority_level": entry.get("authority_level", ""),
                    "blocked_output_kinds": list(entry.get("blocked_output_kinds", [])),
                    "status": entry.get("status", ""),
                }

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_task_authority(
    task: dict[str, Any],
    *,
    registry: list[Any] | None = None,
) -> dict[str, Any]:
    """Determine whether a queued task may be executed autonomously.

    Parameters
    ----------
    task:
        Dict with task metadata. Required key: ``agent_id``.
        Optional keys: ``consequence``, ``output_kind``, ``action``.
    registry:
        Optional list of AgentLaneSeed instances or dicts to use instead
        of the real DEFAULT_AGENT_LANE_SEEDS. Pass a mock list in tests.

    Returns
    -------
    dict with keys:
        allowed (bool)             — True only when ALL checks pass
        reason (str)               — human-readable explanation
        required_tier (str|None)   — minimum authority tier required, or None
    """

    # --- Structural guard: task must be a dict ---
    if not isinstance(task, dict):
        return {
            "allowed": False,
            "reason": "gate_error: task is not a dict — fail closed",
            "required_tier": None,
        }

    # --- agent_id: required, non-empty string ---
    agent_id = task.get("agent_id")
    if not agent_id or not isinstance(agent_id, str) or not agent_id.strip():
        return {
            "allowed": False,
            "reason": "gate_error: agent_id missing or empty — fail closed",
            "required_tier": None,
        }
    agent_id = agent_id.strip().lower()

    # --- Lookup agent in registry (fail closed if not found) ---
    try:
        agent = _lookup_agent(agent_id, registry)
    except Exception as exc:
        return {
            "allowed": False,
            "reason": f"gate_error: registry lookup failed ({exc!r}) — fail closed",
            "required_tier": None,
        }

    if agent is None:
        return {
            "allowed": False,
            "reason": f"agent '{agent_id}' not found in registry — fail closed",
            "required_tier": None,
        }

    # --- Validate agent status (deprecated / future_gated agents cannot run tasks) ---
    agent_status = agent.get("status", "")
    if agent_status in ("deprecated", "future_gated"):
        return {
            "allowed": False,
            "reason": (
                f"agent '{agent_id}' has status '{agent_status}' "
                "and cannot run build tasks autonomously — fail closed"
            ),
            "required_tier": None,
        }

    authority_level = agent.get("authority_level", "")
    authority_idx = _authority_index(authority_level)

    # Unknown authority level → fail closed
    if authority_idx < 0:
        return {
            "allowed": False,
            "reason": (
                f"agent '{agent_id}' has unrecognised authority_level "
                f"'{authority_level}' — fail closed"
            ),
            "required_tier": None,
        }

    # future_gated authority is treated as no authority for safety
    if authority_level == "future_gated":
        return {
            "allowed": False,
            "reason": (
                f"agent '{agent_id}' authority_level is 'future_gated' "
                "— treated as no authority, fail closed"
            ),
            "required_tier": None,
        }

    # --- Determine consequence tier ---
    raw_consequence = task.get("consequence")
    if raw_consequence and isinstance(raw_consequence, str):
        consequence = raw_consequence.strip().upper()
        if consequence not in _CONSEQUENCE_MIN_AUTHORITY:
            # Unrecognised tier → fail closed
            return {
                "allowed": False,
                "reason": (
                    f"unrecognised consequence tier '{raw_consequence}' — fail closed"
                ),
                "required_tier": None,
            }
    else:
        # No explicit consequence — infer from action/output_kind
        consequence = _infer_consequence(task)

    # --- Hard floor: R4 is never autonomous ---
    if consequence == "R4":
        return {
            "allowed": False,
            "reason": (
                "consequence R4 (money/prod/irreversible) is a hard floor — "
                "requires operator approval, never autonomous"
            ),
            "required_tier": "approval_required",
        }

    # --- Consequence floor: check agent authority against minimum required ---
    min_authority = _CONSEQUENCE_MIN_AUTHORITY[consequence]
    # min_authority is a string (R4 is already handled above)
    assert min_authority is not None
    min_authority_idx = _authority_index(min_authority)

    if authority_idx < min_authority_idx:
        return {
            "allowed": False,
            "reason": (
                f"agent '{agent_id}' authority_level '{authority_level}' "
                f"is insufficient for consequence {consequence} "
                f"(requires at least '{min_authority}') — rejected"
            ),
            "required_tier": min_authority,
        }

    # --- Output kind check: reject if task output_kind is in agent's blocked list ---
    output_kind = task.get("output_kind")
    if output_kind and isinstance(output_kind, str):
        output_kind_norm = output_kind.strip().lower()
        blocked = [k.lower() for k in agent.get("blocked_output_kinds", [])]
        if output_kind_norm in blocked:
            return {
                "allowed": False,
                "reason": (
                    f"agent '{agent_id}' has output_kind '{output_kind}' "
                    "explicitly blocked in its lane — rejected"
                ),
                "required_tier": "approval_required",
            }

    # --- All checks passed ---
    return {
        "allowed": True,
        "reason": (
            f"agent '{agent_id}' ({authority_level}) is authorised "
            f"for consequence {consequence}"
        ),
        "required_tier": min_authority,
    }


# ---------------------------------------------------------------------------
# Rejection recording helper
# ---------------------------------------------------------------------------


def record_rejection(
    task: dict[str, Any],
    gate_result: dict[str, Any],
    *,
    ledger: Any | None = None,
) -> None:
    """Record a gate rejection to the control-plane ledger (best-effort, never raises).

    Parameters
    ----------
    task:
        The rejected task dict.
    gate_result:
        The dict returned by check_task_authority().
    ledger:
        Optional ControlPlaneLedger instance. If None, a structured log line
        is emitted to stdout as a fallback.

    This function is explicitly best-effort: if ledger recording fails, a
    structured stdout line is always written so the rejection is never silent.
    """
    import datetime
    import json

    task_id = task.get("task_id") or task.get("title") or task.get("agent_id") or "unknown"
    agent_id = task.get("agent_id", "unknown")
    record = {
        "event": "authority_gate_rejection",
        "task_id": task_id,
        "agent_id": agent_id,
        "consequence": task.get("consequence", "inferred"),
        "output_kind": task.get("output_kind"),
        "reason": gate_result.get("reason"),
        "required_tier": gate_result.get("required_tier"),
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    recorded = False
    if ledger is not None:
        try:
            ledger.record_authority_rejection(record)
            recorded = True
        except AttributeError:
            # Ledger doesn't implement record_authority_rejection yet — fall through
            pass
        except Exception:
            pass

    # Always emit to stdout — the orchestrator log captures this
    prefix = "[AUTHORITY_GATE] REJECTED" if not recorded else "[AUTHORITY_GATE] REJECTED (ledger+stdout)"
    print(
        f"{prefix} | task={task_id!r} agent={agent_id!r} "
        f"reason={gate_result.get('reason')!r}",
        flush=True,
    )


__all__ = [
    "check_task_authority",
    "record_rejection",
]
