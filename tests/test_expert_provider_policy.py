import ast
import builtins
import inspect
import sys

import pytest

import expert_provider_policy as provider_policy
from expert_escalation_lane_policy import select_expert_lane
from expert_escalation_packet import REQUIRED_SENSITIVITY_ATTESTATIONS, build_expert_escalation_packet
from expert_provider_policy import select_expert_provider


def _attestation() -> dict[str, bool]:
    return {key: True for key in REQUIRED_SENSITIVITY_ATTESTATIONS}


def _valid_packet(task_type="code_review", **overrides):
    packet = build_expert_escalation_packet(
        packet_id=f"expert-20260430-provider-{task_type}",
        created_at="2026-04-30T12:00:00Z",
        operator_request_summary="Review a synthetic public parser helper.",
        task_type=task_type,
        data_classification="synthetic_public",
        cloud_allowed=True,
        sensitivity_attestation=_attestation(),
        allowed_paths=("expert_provider_policy.py", "tests/test_expert_provider_policy.py"),
        forbidden_paths=("private-vaults", "secret-env-files", "gmail-bodies"),
        prompt="Review this synthetic public parser helper and return risks plus focused test ideas.",
        expected_outputs=("risk_summary", "test_suggestions"),
    )
    for key, value in overrides.items():
        if key == "execution_policy":
            merged = dict(packet["execution_policy"])
            merged.update(value)
            packet[key] = merged
        elif key == "sensitivity_attestation":
            merged = dict(packet["sensitivity_attestation"])
            merged.update(value)
            packet[key] = merged
        else:
            packet[key] = value
    return packet


def test_valid_openrouter_candidate_is_metadata_only():
    packet = _valid_packet(execution_policy={"candidate_provider": "openrouter"})
    lane_plan = select_expert_lane(packet)

    provider_plan = select_expert_provider(packet, lane_plan)

    assert provider_plan["provider_allowed"] is True
    assert provider_plan["selected_provider"] == "openrouter"
    assert provider_plan["provider_role"] == "external_advisory_review"
    assert provider_plan["provider_candidate_is_metadata_only"] is True
    assert provider_plan["execution_allowed"] is False
    assert provider_plan["model_selected"] is None
    assert provider_plan["requires_operator_approval"] is True
    assert provider_plan["refusal_reason"] == ""
    assert provider_plan["violations"] == []
    assert "kimi" not in repr(provider_plan).lower()
    assert "codex" not in repr(provider_plan).lower()
    assert "gemini" not in repr(provider_plan).lower()


def test_available_openrouter_can_be_selected_without_packet_provider_metadata():
    packet = _valid_packet()
    lane_plan = select_expert_lane(packet)

    provider_plan = select_expert_provider(packet, lane_plan, available_providers=["openrouter", "openrouter"])

    assert provider_plan["provider_allowed"] is True
    assert provider_plan["selected_provider"] == "openrouter"
    assert provider_plan["execution_allowed"] is False
    assert provider_plan["model_selected"] is None


def test_missing_provider_refuses_without_defaulting_to_runner_or_model():
    packet = _valid_packet(execution_policy={"candidate_runner": "codex"})
    lane_plan = select_expert_lane(packet)

    provider_plan = select_expert_provider(packet, lane_plan)

    assert provider_plan["provider_allowed"] is False
    assert provider_plan["selected_provider"] is None
    assert provider_plan["execution_allowed"] is False
    assert provider_plan["model_selected"] is None
    assert provider_plan["refusal_reason"] == "missing_candidate_provider"
    assert "missing_candidate_provider" in provider_plan["violations"]


def test_cloud_external_not_explicitly_allowed_refuses():
    packet = _valid_packet(cloud_allowed=False, execution_policy={"candidate_provider": "openrouter"})
    lane_plan = select_expert_lane(packet)

    provider_plan = select_expert_provider(packet, lane_plan)

    assert provider_plan["provider_allowed"] is False
    assert provider_plan["execution_allowed"] is False
    assert provider_plan["refusal_reason"] == "packet_checker_failed"
    assert "missing_explicit_cloud_allowed" in provider_plan["violations"]


def test_sensitive_or_protected_packet_refuses():
    packet = _valid_packet(
        execution_policy={"candidate_provider": "openrouter"},
        prompt="Review synthetic code near /mnt/c/OpenClawLegalPrivate/demo.",
    )
    lane_plan = select_expert_lane(packet)

    provider_plan = select_expert_provider(packet, lane_plan)

    assert provider_plan["provider_allowed"] is False
    assert provider_plan["execution_allowed"] is False
    assert provider_plan["refusal_reason"] == "packet_checker_failed"
    assert any(violation.startswith("protected_marker:") for violation in provider_plan["violations"])


def test_lane_plan_with_execution_allowed_true_refuses():
    packet = _valid_packet(execution_policy={"candidate_provider": "openrouter"})
    lane_plan = dict(select_expert_lane(packet))
    lane_plan["execution_allowed"] = True

    provider_plan = select_expert_provider(packet, lane_plan)

    assert provider_plan["provider_allowed"] is False
    assert provider_plan["execution_allowed"] is False
    assert provider_plan["refusal_reason"] == "lane_plan_execution_allowed"
    assert "lane_plan_execution_allowed" in provider_plan["violations"]


def test_refused_lane_plan_refuses_provider_selection():
    packet = _valid_packet(execution_policy={"candidate_provider": "openrouter"})
    lane_plan = dict(select_expert_lane(packet))
    lane_plan["refusal_reason"] = "manual_review_required"
    lane_plan["violations"] = ["manual_review_required"]

    provider_plan = select_expert_provider(packet, lane_plan)

    assert provider_plan["provider_allowed"] is False
    assert provider_plan["execution_allowed"] is False
    assert provider_plan["refusal_reason"] == "invalid_lane_plan"
    assert "lane_plan_refused" in provider_plan["violations"]
    assert "manual_review_required" in provider_plan["violations"]


@pytest.mark.parametrize(
    "provider_name",
    ["shell", "bash", "systemctl", "ssh", "telegram", "gmail", "hermes", "mcp", "claude_code", "openclaw_service"],
)
def test_unsafe_provider_names_refuse(provider_name):
    packet = _valid_packet()
    lane_plan = select_expert_lane(packet)

    provider_plan = select_expert_provider(packet, lane_plan, available_providers=[provider_name])

    assert provider_plan["provider_allowed"] is False
    assert provider_plan["selected_provider"] is None
    assert provider_plan["execution_allowed"] is False
    assert provider_plan["refusal_reason"] == "provider_not_allowed"
    assert f"unsafe_provider:{provider_name}" in provider_plan["violations"]


@pytest.mark.parametrize("provider_name", ["anthropic", "codex", "gemini", "kimi", "future_provider"])
def test_unknown_provider_names_refuse(provider_name):
    packet = _valid_packet()
    lane_plan = select_expert_lane(packet)

    provider_plan = select_expert_provider(packet, lane_plan, available_providers=[provider_name])

    assert provider_plan["provider_allowed"] is False
    assert provider_plan["selected_provider"] is None
    assert provider_plan["execution_allowed"] is False
    assert provider_plan["model_selected"] is None
    assert f"unknown_provider:{provider_name}" in provider_plan["violations"]


def test_candidate_provider_is_allowed_when_availability_is_not_supplied():
    packet = _valid_packet(execution_policy={"candidate_provider": "openrouter"})
    lane_plan = select_expert_lane(packet)

    provider_plan = select_expert_provider(packet, lane_plan, available_providers=[])

    assert provider_plan["provider_allowed"] is False
    assert provider_plan["selected_provider"] is None
    assert provider_plan["execution_allowed"] is False
    assert provider_plan["model_selected"] is None
    assert "candidate_provider_unavailable:openrouter" in provider_plan["violations"]

    allowed = select_expert_provider(packet, lane_plan)
    assert allowed["provider_allowed"] is True
    assert allowed["selected_provider"] == "openrouter"


def test_candidate_provider_must_be_available_when_availability_is_supplied():
    packet = _valid_packet(execution_policy={"candidate_provider": "openrouter"})
    lane_plan = select_expert_lane(packet)

    provider_plan = select_expert_provider(packet, lane_plan, available_providers=["openrouter"])

    assert provider_plan["provider_allowed"] is True
    assert provider_plan["selected_provider"] == "openrouter"

    refused = select_expert_provider(packet, lane_plan, available_providers=["future_provider"])
    assert refused["provider_allowed"] is False
    assert "unknown_provider:future_provider" in refused["violations"]


def test_concrete_model_selection_refuses_even_for_openrouter():
    packet = _valid_packet(
        execution_policy={
            "candidate_provider": "openrouter",
            "candidate_model": "openrouter/example-model",
        }
    )
    lane_plan = select_expert_lane(packet)

    provider_plan = select_expert_provider(packet, lane_plan)

    assert provider_plan["provider_allowed"] is False
    assert provider_plan["selected_provider"] is None
    assert provider_plan["execution_allowed"] is False
    assert provider_plan["model_selected"] is None
    assert provider_plan["refusal_reason"] == "concrete_model_selection_not_allowed"
    assert "concrete_model_selection_not_allowed" in provider_plan["violations"]


def test_all_supported_task_types_can_consider_openrouter_as_metadata():
    task_types = [
        "architecture_review",
        "code_review",
        "test_design",
        "implementation_plan",
        "model_routing_review",
        "prompt_hardening",
        "security_review",
        "local_model_benchmark_design",
    ]
    for task_type in task_types:
        packet = _valid_packet(task_type=task_type, execution_policy={"candidate_provider": "openrouter"})
        lane_plan = select_expert_lane(packet)

        provider_plan = select_expert_provider(packet, lane_plan)

        assert provider_plan["provider_allowed"] is True
        assert provider_plan["selected_provider"] == "openrouter"
        assert provider_plan["selected_lane"] == task_type
        assert provider_plan["execution_allowed"] is False
        assert provider_plan["model_selected"] is None


def test_provider_policy_module_does_not_import_or_call_external_surfaces(monkeypatch):
    source = inspect.getsource(provider_policy)
    tree = ast.parse(source)
    imported_modules = set()
    called_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            called = node.func
            if isinstance(called, ast.Name):
                called_names.add(called.id)
            elif isinstance(called, ast.Attribute):
                called_names.add(called.attr)

    assert imported_modules <= {"__future__", "expert_escalation_packet", "typing"}
    forbidden_call_names = {
        "openrouter_call",
        "claude_call",
        "claude_json",
        "nemotron_call",
        "run",
        "Popen",
        "urlopen",
        "Request",
    }
    assert called_names.isdisjoint(forbidden_call_names)
    assert "chief_llm" not in source
    assert "openrouter_call" not in source
    assert "runner_profiles" not in source
    assert "runner_registry" not in source
    assert "subprocess" not in source
    assert "systemd" not in source

    forbidden_modules = {
        "aider",
        "chief_llm",
        "chief_notify",
        "chief_sender",
        "cloud",
        "codex",
        "gateway",
        "hermes_cli",
        "mcp",
        "openai",
        "requests",
        "runner_profiles",
        "runner_registry",
        "run_agent",
        "service",
        "subprocess",
        "telegram",
        "urllib",
    }
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        assert name.split(".")[0] not in forbidden_modules
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    packet = _valid_packet(execution_policy={"candidate_provider": "openrouter"})
    lane_plan = select_expert_lane(packet)
    provider_plan = select_expert_provider(packet, lane_plan)

    assert provider_plan["provider_allowed"] is True
    assert provider_plan["execution_allowed"] is False
    assert "expert_provider_policy" in sys.modules