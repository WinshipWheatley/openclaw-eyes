import ast
import builtins
import copy
import inspect
import sys

import pytest

import expert_escalation_job_manifest as manifest_module
from expert_escalation_job_manifest import build_expert_job_manifest
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
        allowed_paths=("expert_escalation_packet.py", "tests/test_expert_escalation_job_manifest.py"),
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


def test_valid_packet_produces_no_execution_manifest():
    packet = _valid_packet()

    manifest = build_expert_job_manifest(packet, created_at="2026-04-30T13:00:00Z")

    assert manifest["manifest_type"] == "external_expert.job_manifest"
    assert manifest["schema_version"] == 1
    assert manifest["manifest_created_at"] == "2026-04-30T13:00:00Z"
    assert manifest["packet_id"] == packet["packet_id"]
    assert manifest["task_type"] == "code_review"
    assert manifest["selected_lane"] == "code_review"
    assert manifest["runner_class"] == "external_expert"
    assert manifest["execution_allowed"] is False
    assert manifest["approval_required"] is True
    assert manifest["checker_passed"] is True
    assert manifest["lane_policy_passed"] is True
    assert manifest["refusal_reason"] == ""
    assert manifest["violations"] == []


def test_checker_failure_produces_refusal_manifest():
    packet = _valid_packet(cloud_allowed=False)

    manifest = build_expert_job_manifest(packet, created_at="2026-04-30T13:00:00Z")

    assert manifest["selected_lane"] is None
    assert manifest["execution_allowed"] is False
    assert manifest["approval_required"] is True
    assert manifest["checker_passed"] is False
    assert manifest["lane_policy_passed"] is False
    assert manifest["refusal_reason"] == "packet_checker_failed"
    assert "missing_explicit_cloud_allowed" in manifest["violations"]
    assert manifest["prompt_body"] == ""


def test_lane_policy_failure_produces_refusal_manifest(monkeypatch):
    packet = _valid_packet()

    def fake_select_expert_lane(_packet):
        return {
            "packet_id": packet["packet_id"],
            "selected_lane": None,
            "task_type": "code_review",
            "runner_class": "external_expert",
            "execution_allowed": False,
            "allowed_outputs": [],
            "refusal_reason": "lane_policy_failed_for_test",
            "violations": ["synthetic_lane_policy_violation"],
        }

    monkeypatch.setattr(manifest_module, "select_expert_lane", fake_select_expert_lane)

    manifest = build_expert_job_manifest(packet, created_at="2026-04-30T13:00:00Z")

    assert manifest["checker_passed"] is True
    assert manifest["lane_policy_passed"] is False
    assert manifest["execution_allowed"] is False
    assert manifest["refusal_reason"] == "lane_policy_failed_for_test"
    assert manifest["violations"] == ["synthetic_lane_policy_violation"]


def test_manifest_contains_selected_lane_and_allowed_outputs():
    packet = _valid_packet(task_type="architecture_review")

    manifest = build_expert_job_manifest(packet, created_at="2026-04-30T13:00:00Z")

    assert manifest["selected_lane"] == "architecture_review"
    assert manifest["allowed_outputs"] == ["risk_summary", "test_suggestions"]


def test_execution_allowed_is_always_false():
    valid_manifest = build_expert_job_manifest(_valid_packet(), created_at="2026-04-30T13:00:00Z")
    refused_manifest = build_expert_job_manifest(
        _valid_packet(prompt="Review /mnt/c/OpenClawLegalPrivate/demo."),
        created_at="2026-04-30T13:00:00Z",
    )

    assert valid_manifest["execution_allowed"] is False
    assert refused_manifest["execution_allowed"] is False


def test_prompt_body_is_rendered_deterministically():
    packet = _valid_packet()

    first = build_expert_job_manifest(packet, created_at="2026-04-30T13:00:00Z")
    second = build_expert_job_manifest(packet, created_at="2026-04-30T13:00:00Z")

    assert first["prompt_body"] == packet["prompt"]
    assert second["prompt_body"] == first["prompt_body"]
    assert first == second


def test_no_shell_invoke_or_provider_command_field_exists():
    packet = _valid_packet(provider_metadata={"capability_class": "large_context_review"})

    manifest = build_expert_job_manifest(packet, created_at="2026-04-30T13:00:00Z")
    keys = {key.lower() for key in manifest}
    rendered = repr(manifest).lower()

    assert "provider_metadata" in manifest
    assert manifest["provider_metadata"] == {"capability_class": "large_context_review"}
    assert not any("command" in key or "invoke" in key or "shell" in key for key in keys)
    assert "invoke_cmd" not in rendered
    assert "openrouter_call" not in rendered
    assert "codex exec" not in rendered


def test_candidate_runner_is_preserved_as_metadata_only():
    packet = _valid_packet(execution_policy={"candidate_runner": "codex"})

    manifest = build_expert_job_manifest(packet, created_at="2026-04-30T13:00:00Z")

    assert manifest["candidate_runner_metadata"] == {
        "candidate_runner": "codex",
        "metadata_only": True,
        "execution_allowed": False,
    }
    assert manifest["execution_allowed"] is False


def test_packet_input_is_not_mutated():
    packet = _valid_packet(execution_policy={"candidate_runner": "codex"})
    original = copy.deepcopy(packet)

    build_expert_job_manifest(packet, created_at="2026-04-30T13:00:00Z")

    assert packet == original


def test_job_manifest_module_does_not_import_or_call_external_surfaces(monkeypatch):
    source = inspect.getsource(manifest_module)
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

    assert imported_modules <= {
        "__future__",
        "datetime",
        "expert_escalation_lane_policy",
        "expert_escalation_packet",
        "typing",
    }
    assert "eval" not in called_names
    assert "exec" not in called_names
    assert "openrouter_call" not in source
    assert "invoke_cmd" not in source

    forbidden_modules = {
        "builder_watcher",
        "chief_llm",
        "chief_notify",
        "chief_sender",
        "cloud",
        "codex",
        "gateway",
        "hermes_cli",
        "mcp",
        "openai",
        "openrouter",
        "requests",
        "runner_profiles",
        "runner_registry",
        "run_agent",
        "service",
        "subprocess",
        "systemd",
        "telegram",
        "urllib",
    }
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        assert name.split(".")[0] not in forbidden_modules
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    manifest = build_expert_job_manifest(_valid_packet(), created_at="2026-04-30T13:00:00Z")

    assert manifest["selected_lane"] == "code_review"
    assert manifest["execution_allowed"] is False
    assert "expert_escalation_job_manifest" in sys.modules