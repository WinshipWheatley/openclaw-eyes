"""Convergence metadata for legacy approval gates and compose/G3 packets.

This module is deliberately descriptive. It does not call legacy brains,
register executors, approve packets, or send anything. The goal is to make the
single active gate explicit for old email/SMS approval surfaces while SEND_HOLD
is active and while the old brains are still present as compatibility code.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


G3_GATE = "agent_work_packet_g3"
SEND_HOLD_REF = "/mnt/e/openclaw/orchestration/SEND_HOLD.md"


LEGACY_TIER_TO_G3: dict[str, dict[str, Any]] = {
    "tier_0": {
        "legacy_meaning": "old path could proceed without a human gate",
        "g3_gate_state": "READ_ONLY",
        "approval_required": False,
        "guardian_required": False,
        "execution_allowed": False,
    },
    "tier_1": {
        "legacy_meaning": "old path required local terminal confirmation",
        "g3_gate_state": "PENDING_APPROVAL",
        "approval_required": True,
        "guardian_required": False,
        "execution_allowed": False,
    },
    "tier_2": {
        "legacy_meaning": "old path required Guardian/HITL approval",
        "g3_gate_state": "PENDING_APPROVAL",
        "approval_required": True,
        "guardian_required": True,
        "execution_allowed": False,
    },
    "hard_tier_2": {
        "legacy_meaning": "old path required non-overrideable Guardian/HITL approval",
        "g3_gate_state": "PENDING_APPROVAL",
        "approval_required": True,
        "guardian_required": True,
        "execution_allowed": False,
        "non_overrideable": True,
    },
}


SURFACE_CONVERGENCE: dict[str, dict[str, Any]] = {
    "exact_gmail_send": {
        "surface": "exact_gmail_send",
        "legacy_brain": None,
        "legacy_gate": None,
        "legacy_tier": "hard_tier_2",
        "canonical_gate": G3_GATE,
        "g3_gate_state": "PENDING_APPROVAL",
        "single_authoritative_gate": G3_GATE,
        "legacy_gate_runtime_role": "none",
        "legacy_direct_send_allowed": False,
        "double_gate_allowed": False,
        "executor_registered": True,
        "executor_registration_owner": "hitl_action_service.register_builtin_action_dispatchers",
        "executor": "cassandra_exact_send_executor",
        "registration_independent_of_send_hold": True,
        "approval_required": True,
        "approval_receipt_linked": False,
        "execution_allowed": False,
        "external_send_allowed": False,
        "send_hold_ref": SEND_HOLD_REF,
    },
    "invoice_send": {
        "surface": "invoice_send",
        "legacy_brain": None,
        "legacy_gate": None,
        "legacy_tier": "tier_2",
        "canonical_gate": G3_GATE,
        "g3_gate_state": "PENDING_APPROVAL",
        "single_authoritative_gate": G3_GATE,
        "legacy_gate_runtime_role": "none",
        "legacy_direct_send_allowed": False,
        "double_gate_allowed": False,
        "executor_registered": True,
        "approval_required": True,
        "execution_allowed": False,
        "external_send_allowed": False,
        "send_hold_ref": SEND_HOLD_REF,
        "executor_mode": "square_sandbox_only",
    },
    "email_send": {
        "surface": "email_send",
        "legacy_brain": "chief_email_brain.py",
        "legacy_gate": "chief_approval_brain.request_approval",
        "legacy_tier": "tier_2",
        "canonical_gate": G3_GATE,
        "g3_gate_state": "PENDING_APPROVAL",
        "single_authoritative_gate": G3_GATE,
        "legacy_gate_runtime_role": "compatibility_only_after_g3_decision",
        "legacy_direct_send_allowed": False,
        "double_gate_allowed": False,
        "executor_registered": False,
        "approval_required": True,
        "execution_allowed": False,
        "external_send_allowed": False,
        "send_hold_ref": SEND_HOLD_REF,
    },
    "sms_send": {
        "surface": "sms_send",
        "legacy_brain": "chief_sms_brain.py",
        "legacy_gate": "chief_approval_brain.request_approval",
        "legacy_tier": "tier_2",
        "canonical_gate": G3_GATE,
        "g3_gate_state": "PENDING_APPROVAL",
        "single_authoritative_gate": G3_GATE,
        "legacy_gate_runtime_role": "compatibility_only_after_g3_decision",
        "legacy_direct_send_allowed": False,
        "double_gate_allowed": False,
        "executor_registered": False,
        "approval_required": True,
        "execution_allowed": False,
        "external_send_allowed": False,
        "send_hold_ref": SEND_HOLD_REF,
    },
    "approval_response": {
        "surface": "approval_response",
        "legacy_brain": "chief_approval_brain.py",
        "legacy_gate": "approval_pending.json",
        "legacy_tier": "tier_2",
        "canonical_gate": G3_GATE,
        "g3_gate_state": "PENDING_APPROVAL",
        "single_authoritative_gate": G3_GATE,
        "legacy_gate_runtime_role": "compatibility_pending_state_only",
        "legacy_direct_send_allowed": False,
        "double_gate_allowed": False,
        "executor_registered": False,
        "approval_required": True,
        "execution_allowed": False,
        "external_send_allowed": False,
        "send_hold_ref": SEND_HOLD_REF,
    },
}


def normalize_legacy_tier(tier: int | str) -> str:
    text = str(tier).strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "0": "tier_0",
        "t0": "tier_0",
        "tier0": "tier_0",
        "1": "tier_1",
        "t1": "tier_1",
        "tier1": "tier_1",
        "2": "tier_2",
        "t2": "tier_2",
        "tier2": "tier_2",
        "hard_t2": "hard_tier_2",
        "hard_tier2": "hard_tier_2",
    }
    return aliases.get(text, text)


def map_legacy_tier_to_g3(tier: int | str) -> dict[str, Any]:
    normalized = normalize_legacy_tier(tier)
    if normalized not in LEGACY_TIER_TO_G3:
        raise ValueError(f"unknown legacy approval tier: {tier}")
    mapped = deepcopy(LEGACY_TIER_TO_G3[normalized])
    mapped["legacy_tier"] = normalized
    mapped["canonical_gate"] = G3_GATE
    return mapped


def convergence_for_surface(
    surface: str,
    *,
    send_hold_active: bool = True,
    approval_status: str | None = None,
    approval_receipt_ref: str | None = None,
) -> dict[str, Any]:
    normalized = str(surface or "").strip()
    base = deepcopy(SURFACE_CONVERGENCE.get(normalized))
    if base is None:
        base = {
            "surface": normalized,
            "legacy_brain": None,
            "legacy_gate": None,
            "legacy_tier": None,
            "canonical_gate": G3_GATE,
            "g3_gate_state": "PENDING_APPROVAL",
            "single_authoritative_gate": G3_GATE,
            "legacy_gate_runtime_role": "none",
            "legacy_direct_send_allowed": False,
            "double_gate_allowed": False,
            "executor_registered": False,
            "approval_required": True,
            "execution_allowed": False,
            "external_send_allowed": False,
            "send_hold_ref": SEND_HOLD_REF,
        }
    base["send_hold_active"] = bool(send_hold_active)
    normalized_approval = str(approval_status or "").strip().upper()
    if normalized_approval == "APPROVED" and normalized == "exact_gmail_send":
        base["g3_gate_state"] = "DONE"
        base["approval_receipt_linked"] = True
        base["approval_receipt_ref"] = str(approval_receipt_ref or "")
        base["g3_execution_eligible"] = True
    if send_hold_active:
        if not base.get("registration_independent_of_send_hold"):
            base["executor_registered"] = False
        base["execution_allowed"] = False
        base["external_send_allowed"] = False
    return base


def is_converged_action_surface(surface: str) -> bool:
    return str(surface or "").strip() in SURFACE_CONVERGENCE


__all__ = [
    "G3_GATE",
    "LEGACY_TIER_TO_G3",
    "SEND_HOLD_REF",
    "SURFACE_CONVERGENCE",
    "convergence_for_surface",
    "is_converged_action_surface",
    "map_legacy_tier_to_g3",
    "normalize_legacy_tier",
]
