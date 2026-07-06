"""Build-request intake for Chief -> Polish Loop factory routing.

This module is intentionally a decision seam only. It can admit a local
build-request task packet for review, or return activation instructions from
the activation gate register, but it never starts the factory, spawns workers,
or grants live execution authority.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

import activation_gate_register
import capability_registry


DEFAULT_FACTORY_CAPABILITY_ID = "polish_loop_factory_mode"

AUTHORITY_BOUNDARY = {
    "live_factory_execution_allowed": False,
    "worker_spawn_allowed": False,
    "agent_loop_allowed": False,
    "external_tool_connect_allowed": False,
    "send_allowed": False,
    "email_send_allowed": False,
    "ledger_mutation_allowed": False,
    "payment_action_allowed": False,
}


def _capability_id(request: Mapping[str, Any]) -> str:
    return str(request.get("capability_id") or DEFAULT_FACTORY_CAPABILITY_ID).strip()


def _activation_register(
    activation_register: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    return activation_register or activation_gate_register.build_activation_gate_register()


def _capabilities_by_id(register: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    capabilities = register.get("capabilities") if isinstance(register, Mapping) else None
    if not isinstance(capabilities, list):
        return {}
    return {
        str(item.get("capability_id")): item
        for item in capabilities
        if isinstance(item, Mapping) and item.get("capability_id")
    }


def _capability_for(
    capability_id: str,
    *,
    activation_register: Mapping[str, Any] | None = None,
) -> Mapping[str, Any] | None:
    return _capabilities_by_id(_activation_register(activation_register)).get(capability_id)


def is_request_allowed(
    request: Mapping[str, Any],
    *,
    activation_register: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return Chief's admission precheck without starting any build machinery."""

    capability_id = _capability_id(request)
    capability = _capability_for(capability_id, activation_register=activation_register)
    chief_allows = bool(request.get("chief_allowance"))

    reasons: list[str] = []
    if not chief_allows:
        reasons.append("chief_allowance_required")
    if capability is None:
        reasons.append("known_activation_capability_required")

    return {
        "allowed": not reasons,
        "reasons": reasons,
        "capability_id": capability_id,
        "known_activation_capability": capability is not None,
        "chief_allowance": chief_allows,
        "chief_registry_context": capability_registry.describe_actor_capability("chief", "routing"),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _task_id(request: Mapping[str, Any], capability_id: str) -> str:
    material = json.dumps(
        {
            "what": str(request.get("what") or ""),
            "requesting_agent": str(request.get("requesting_agent") or ""),
            "capability_id": capability_id,
        },
        sort_keys=True,
    )
    return "build_request_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _factory_task(request: Mapping[str, Any], capability_id: str) -> dict[str, Any]:
    return {
        "task_id": _task_id(request, capability_id),
        "task_type": "build_request",
        "status": "ADMITTED_FOR_CHIEF_FACTORY_REVIEW",
        "requested_by_agent": str(request.get("requesting_agent") or "").strip(),
        "what": " ".join(str(request.get("what") or "").split()),
        "capability_id": capability_id,
        "intake_source": "polish_loop.build_request_intake",
        "factory_execution_started": False,
        "worker_spawn_requested": False,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _activation_instructions(
    capability_id: str,
    *,
    activation_register: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    capability = _capability_for(capability_id, activation_register=activation_register)
    if capability is None:
        return {
            "capability_id": capability_id,
            "display_name": capability_id,
            "gate_stage": "unknown",
            "activation_allowed_now": False,
            "operator_approval_required": True,
            "next_required_step": "register this capability in activation_gate_register before any build routing",
            "reason_if_off": "capability is not present in the activation gate register",
            "rollback_note": "no live change was made",
            "current_state_if_verifiable": {},
        }

    return {
        "capability_id": str(capability.get("capability_id") or capability_id),
        "display_name": str(capability.get("display_name") or capability_id),
        "gate_stage": str(capability.get("gate_stage") or ""),
        "activation_allowed_now": bool(capability.get("activation_allowed_now")),
        "operator_approval_required": bool(capability.get("operator_approval_required")),
        "next_required_step": str(capability.get("next_required_step") or ""),
        "reason_if_off": str(capability.get("reason_if_off") or ""),
        "rollback_note": str(capability.get("rollback_note") or ""),
        "current_state_if_verifiable": dict(capability.get("current_state_if_verifiable") or {}),
    }


def _activation_operator_message(
    *,
    what: str,
    instructions: Mapping[str, Any],
    reason: str,
) -> str:
    target = what or "that build request"
    next_step = str(instructions.get("next_required_step") or "no next step is registered")
    capability_id = str(instructions.get("capability_id") or DEFAULT_FACTORY_CAPABILITY_ID)
    gate_stage = str(instructions.get("gate_stage") or "unknown")
    reason_if_off = str(instructions.get("reason_if_off") or reason)
    return (
        f"Chief cannot put '{target}' into live factory execution yet. "
        f"The activation register has {capability_id} at gate stage '{gate_stage}': {reason_if_off}. "
        f"Next required step: {next_step}."
    )


def admit_or_escalate(
    request: Mapping[str, Any],
    *,
    factory_capacity_available: bool,
    activation_register: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Admit an inert factory task packet or return register-grounded activation steps."""

    register = _activation_register(activation_register)
    allowance = is_request_allowed(request, activation_register=register)
    capability_id = str(allowance["capability_id"])

    if allowance["allowed"] and factory_capacity_available:
        task = _factory_task(request, capability_id)
        return {
            "status": "ADMITTED_TO_FACTORY",
            "factory_task": task,
            "allowance": allowance,
            "operator_message": (
                "Chief accepted the build request into a local factory task packet for review. "
                "No live worker was started."
            ),
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }

    reason = (
        "factory_capacity_unavailable"
        if allowance["allowed"] and not factory_capacity_available
        else ",".join(allowance["reasons"])
    )
    instructions = _activation_instructions(capability_id, activation_register=register)
    return {
        "status": "ACTIVATION_REQUIRED",
        "allowance": allowance,
        "activation_instructions": instructions,
        "operator_message": _activation_operator_message(
            what=str(request.get("what") or "").strip(),
            instructions=instructions,
            reason=reason,
        ),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
