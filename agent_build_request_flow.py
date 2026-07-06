"""Agent-facing build-request flow.

The flow models the Telegram-facing behavior locally:
operator -> addressed agent -> Chief handoff -> build-request intake.
It does not send Telegram messages, start workers, or mutate live ledgers.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

import interpreter_lm
from agent_handoff_registry import _handoff
from polish_loop import build_request_intake


def _clean_agent(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _handoff_to_chief(*, requesting_agent: str, what: str) -> dict[str, Any]:
    handoff = _handoff(
        handoff_ref=f"{requesting_agent}_to_chief_build_request",
        from_agent=requesting_agent,
        to_agent_or_worker="chief",
        channel_ref="operations_chief_workboard",
        trigger_condition="An addressed agent received a fuzzy operator request to build tooling or automation.",
        package_type="build_request_handoff_packet",
        allowed_actions=(
            "summarize_requested_build",
            "request_chief_factory_admission_review",
        ),
        blocked_actions=(
            "spawn_worker_from_build_request",
            "start_factory_from_build_request",
            "grant_runtime_authority_from_build_request",
        ),
    )
    handoff["packet"] = {
        "intent": interpreter_lm.BUILD_REQUEST_INTENT,
        "requesting_agent": requesting_agent,
        "what": what,
        "sent": False,
        "worker_spawned": False,
    }
    return handoff


def handle_agent_build_request(
    text: str,
    *,
    addressed_agent: str,
    factory_capacity_available: bool = False,
    chief_allowance: bool = False,
    capability_id: str = build_request_intake.DEFAULT_FACTORY_CAPABILITY_ID,
    protected_generate_fn: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Handle a fuzzy agent build request through the real routing seams."""

    interpreted = interpreter_lm.interpret_operator_message(
        text,
        protected_generate_fn=protected_generate_fn,
    )
    agent = _clean_agent(addressed_agent)
    requesting_agent = _clean_agent(interpreted.requesting_agent)
    if (
        interpreted.intent != interpreter_lm.BUILD_REQUEST_INTENT
        or not interpreted.is_high_confidence_action()
        or not interpreted.what
        or requesting_agent != agent
    ):
        return {
            "handled": False,
            "reason": "not_high_confidence_addressed_build_request",
            "interpretation": interpreted,
        }

    handoff = _handoff_to_chief(requesting_agent=requesting_agent, what=interpreted.what)
    chief_request = {
        "intent": interpreted.intent,
        "what": interpreted.what,
        "requesting_agent": requesting_agent,
        "chief_allowance": bool(chief_allowance),
        "capability_id": capability_id,
        "handoff_ref": handoff["handoff_ref"],
    }
    chief_decision = build_request_intake.admit_or_escalate(
        chief_request,
        factory_capacity_available=bool(factory_capacity_available),
    )

    result: dict[str, Any] = {
        "handled": True,
        "agent_reply": "Sending that to Chief.",
        "interpretation": {
            "route": interpreted.route,
            "intent": interpreted.intent,
            "confidence": interpreted.confidence,
            "what": interpreted.what,
            "requesting_agent": requesting_agent,
        },
        "handoff": handoff,
        "chief_decision": chief_decision,
        "operator_message": chief_decision["operator_message"],
        "authority_boundary": chief_decision["authority_boundary"],
    }
    if "activation_instructions" in chief_decision:
        result["activation_instructions"] = chief_decision["activation_instructions"]
    return result


def clarify_activation_instructions(
    text: str,
    *,
    previous_result: Mapping[str, Any],
    addressed_agent: str,
) -> dict[str, Any]:
    """Explain the previous activation-register instructions through the agent."""

    instructions = previous_result.get("activation_instructions")
    if not isinstance(instructions, Mapping):
        return {
            "handled": False,
            "responding_agent": _clean_agent(addressed_agent),
            "reason": "no_activation_instructions_available",
        }

    next_step = str(instructions.get("next_required_step") or "").strip()
    capability_id = str(instructions.get("capability_id") or "").strip()
    reason_if_off = str(instructions.get("reason_if_off") or "").strip()
    return {
        "handled": True,
        "responding_agent": _clean_agent(addressed_agent),
        "heard": text,
        "plain_language": (
            f"Chief needs {capability_id} to clear its activation gate before that can run. "
            f"The blocker is: {reason_if_off or 'the activation register does not mark it ready'}."
        ),
        "grounded_instructions": next_step,
        "activation_instructions": dict(instructions),
        "authority_boundary": dict(build_request_intake.AUTHORITY_BOUNDARY),
    }
