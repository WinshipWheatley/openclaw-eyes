import ast
import builtins
import inspect
import sys

import pytest

import expert_escalation_lane_policy as lane_policy
from expert_escalation_lane_policy import select_expert_lane
from expert_escalation_packet import REQUIRED_SENSITIVITY_ATTESTATIONS, build_expert_escalation_packet


def _attestation() -> dict[str, bool]:
    return {key: True for key in REQUIRED_SENSITIVITY_ATTESTATIONS}


def _valid_packet(task_type="code_review", **overrides):
    packet = build_expert_escalation_packet(
        packet_id=f"expert-20260430-{task_type}",
        created_at="2026-04-30T12:00:00Z",
        operator_request_summary="Review a synthetic public parser helper.",
        task_type=task_type,
        data_classification="synthetic_public",
        cloud_allowed=True,
        sensitivity_attestation=_attestation(),
        allowed_paths=("expert_escalation_packet.py", "tests/test_expert_escalation_lane_policy.py"),
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


def test_valid_architecture_review_packet_returns_no_execution_lane_plan():
    packet = _valid_packet(task_type="architecture_review")

    plan = select_expert_lane(packet)

    assert plan["packet_id"] == packet["packet_id"]
    assert plan["selected_lane"] == "architecture_review"
    assert plan["task_type"] == "architecture_review"
    assert plan["runner_class"] == "external_expert"
    assert plan["execution_allowed"] is False
    assert plan["requires_human_or_runner_approval"] is True
    assert plan["requires_checker_pass"] is True
    assert plan["allowed_outputs"] == packet["expected_outputs"]
    assert plan["refusal_reason"] == ""
    assert plan["violations"] == []


def test_valid_code_review_packet_returns_no_execution_lane_plan():
    packet = _valid_packet(task_type="code_review")

    plan = select_expert_lane(packet)

    assert plan["selected_lane"] == "code_review"
    assert plan["execution_allowed"] is False
    assert plan["allowed_outputs"] == ["risk_summary", "test_suggestions"]


def test_invalid_packet_refuses_and_includes_checker_violations():
    packet = _valid_packet(cloud_allowed=False)

    plan = select_expert_lane(packet)

    assert plan["selected_lane"] is None
    assert plan["execution_allowed"] is False
    assert plan["refusal_reason"] == "packet_checker_failed"
    assert "missing_explicit_cloud_allowed" in plan["violations"]


def test_unknown_task_type_refuses():
    packet = _valid_packet(task_type="unknown_lane")

    plan = select_expert_lane(packet)

    assert plan["selected_lane"] is None
    assert plan["execution_allowed"] is False
    assert plan["refusal_reason"] == "packet_checker_failed"
    assert "unknown_task_type:unknown_lane" in plan["violations"]


def test_candidate_runner_codex_is_allowed_as_metadata_only():
    packet = _valid_packet(execution_policy={"candidate_runner": "codex"})

    plan = select_expert_lane(packet)
    rendered = repr(plan).lower()

    assert plan["selected_lane"] == "code_review"
    assert plan["execution_allowed"] is False
    assert plan["candidate_runner"] == "codex"
    assert plan["candidate_runner_is_metadata_only"] is True
    assert "invoke" not in rendered
    assert "command" not in rendered


@pytest.mark.parametrize(
    "candidate_runner",
    ["claude", "claude_code", "claude-cli", "shell", "systemctl", "telegram", "gmail", "mcp"],
)
def test_dangerous_candidate_runner_is_refused(candidate_runner):
    packet = _valid_packet(execution_policy={"candidate_runner": candidate_runner})

    plan = select_expert_lane(packet)

    assert plan["selected_lane"] is None
    assert plan["execution_allowed"] is False
    assert plan["violations"]
    assert any("candidate_runner" in violation for violation in plan["violations"])


def test_output_always_has_execution_allowed_false():
    allowed_plan = select_expert_lane(_valid_packet())
    refused_plan = select_expert_lane(_valid_packet(prompt="Review /mnt/c/OpenClawLegalPrivate/demo."))

    assert allowed_plan["execution_allowed"] is False
    assert refused_plan["execution_allowed"] is False


def test_lane_policy_module_does_not_import_or_call_external_surfaces(monkeypatch):
    source = inspect.getsource(lane_policy)
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
    assert "eval" not in called_names
    assert "exec" not in called_names

    forbidden_modules = {
        "builder_watcher",
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
    plan = select_expert_lane(_valid_packet())

    assert plan["selected_lane"] == "code_review"
    assert plan["execution_allowed"] is False
    assert "expert_escalation_lane_policy" in sys.modules