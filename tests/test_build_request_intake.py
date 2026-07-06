from __future__ import annotations

import activation_gate_register
from polish_loop import build_request_intake


def test_admit_or_escalate_routes_allowed_capacity_to_factory_task() -> None:
    request = {
        "intent": "build_request",
        "what": "scene recall helper for the X32",
        "requesting_agent": "niles",
        "chief_allowance": True,
        "capability_id": "polish_loop_factory_mode",
    }

    result = build_request_intake.admit_or_escalate(request, factory_capacity_available=True)

    assert result["status"] == "ADMITTED_TO_FACTORY"
    assert result["factory_task"]["task_type"] == "build_request"
    assert result["factory_task"]["requested_by_agent"] == "niles"
    assert result["factory_task"]["what"] == "scene recall helper for the X32"
    assert result["authority_boundary"]["live_factory_execution_allowed"] is False


def test_admit_or_escalate_uses_activation_register_when_not_allowed() -> None:
    request = {
        "intent": "build_request",
        "what": "autonomous Niles DAW publisher",
        "requesting_agent": "niles",
        "chief_allowance": False,
        "capability_id": "polish_loop_factory_mode",
    }
    register = activation_gate_register.build_activation_gate_register()
    capability = next(item for item in register["capabilities"] if item["capability_id"] == "polish_loop_factory_mode")

    result = build_request_intake.admit_or_escalate(
        request,
        factory_capacity_available=True,
        activation_register=register,
    )

    assert result["status"] == "ACTIVATION_REQUIRED"
    assert result["activation_instructions"]["capability_id"] == "polish_loop_factory_mode"
    assert result["activation_instructions"]["next_required_step"] == capability["next_required_step"]
    assert result["activation_instructions"]["activation_allowed_now"] is capability["activation_allowed_now"]
    assert "canned" not in result["operator_message"].lower()


def test_is_request_allowed_requires_chief_allowance_and_known_capability() -> None:
    assert build_request_intake.is_request_allowed(
        {"chief_allowance": True, "capability_id": "polish_loop_factory_mode"}
    )["allowed"] is True
    assert build_request_intake.is_request_allowed(
        {"chief_allowance": False, "capability_id": "polish_loop_factory_mode"}
    )["allowed"] is False
    assert build_request_intake.is_request_allowed(
        {"chief_allowance": True, "capability_id": "missing.capability"}
    )["allowed"] is False
