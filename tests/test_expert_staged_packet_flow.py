import ast
import builtins
import copy
import inspect
import sys

import pytest

import expert_staged_packet_flow as staged_flow
from expert_escalation_packet import REQUIRED_SENSITIVITY_ATTESTATIONS, build_expert_escalation_packet
from expert_staged_packet_flow import build_expert_staged_packet_artifact, check_expert_staged_packet_artifact
from expert_synthetic_handoff import build_expert_synthetic_handoff


def _attestation() -> dict[str, bool]:
    return {key: True for key in REQUIRED_SENSITIVITY_ATTESTATIONS}


def _valid_packet(**overrides):
    packet = build_expert_escalation_packet(
        packet_id="expert-20260501-staged-code-review",
        created_at="2026-05-01T03:00:00Z",
        operator_request_summary="Review a synthetic public parser helper.",
        task_type="code_review",
        data_classification="synthetic_public",
        cloud_allowed=True,
        sensitivity_attestation=_attestation(),
        allowed_paths=("expert_staged_packet_flow.py", "tests/test_expert_staged_packet_flow.py"),
        forbidden_paths=("private-vaults", "secret-env-files", "mail-bodies"),
        prompt="Review this synthetic public parser helper and return risks plus focused test ideas.",
        expected_outputs=("risk_summary", "test_suggestions"),
        execution_policy={
            "runner_class": "external_expert",
            "mode": "sequential_external_runner_only",
            "hermes_may_execute": False,
            "requires_checker_pass": True,
            "preferred_lane": "code_review",
            "candidate_provider": "openrouter",
        },
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


def test_valid_synthetic_packet_produces_deterministic_staged_artifact():
    packet = _valid_packet()

    first = build_expert_staged_packet_artifact(packet, created_at="2026-05-01T04:00:00Z")
    second = build_expert_staged_packet_artifact(copy.deepcopy(packet), created_at="2026-05-01T04:00:00Z")

    assert first == second
    assert first["passed"] is True
    assert first["artifact_type"] == "external_expert.staged_packet_artifact"
    assert first["schema_version"] == 1
    assert first["created_at"] == "2026-05-01T04:00:00Z"
    assert first["packet_id"] == packet["packet_id"]
    assert first["summary"]
    assert len(first["summary"]) <= 240
    assert first["next_allowed_action"] == "human_review_staged_artifact"
    assert first["staged_packet_check"] == {"passed": True, "violations": [], "recommended_action": "pass"}


def test_hashes_are_preserved_from_provider_plan_and_manifest():
    packet = _valid_packet()

    handoff = build_expert_synthetic_handoff(packet, created_at="2026-05-01T04:00:00Z")
    artifact = build_expert_staged_packet_artifact(packet, created_at="2026-05-01T04:00:00Z")

    assert artifact["provider_plan_hash"] == handoff["provider_plan_hash"]
    assert artifact["manifest_hash"] == handoff["manifest_hash"]
    assert artifact["provider_plan_metadata"]["provider_plan_hash"] == handoff["provider_plan"]["provider_plan_hash"]
    assert artifact["job_manifest_metadata"]["manifest_hash"] == handoff["job_manifest"]["manifest_hash"]
    assert artifact["synthetic_receipt_validation"]["passed"] is True
    assert artifact["synthetic_result_validation"]["passed"] is True


def test_execution_provider_and_telegram_flags_remain_false():
    artifact = build_expert_staged_packet_artifact(_valid_packet(), created_at="2026-05-01T04:00:00Z")

    assert artifact["execution_allowed"] is False
    assert artifact["provider_call_allowed"] is False
    assert artifact["telegram_return_allowed"] is False
    assert artifact["provider_plan_metadata"]["execution_allowed"] is False
    assert artifact["job_manifest_metadata"]["execution_allowed"] is False
    assert artifact["synthetic_result_validation"]["execution_allowed"] is False
    assert artifact["synthetic_result_validation"]["model_selected"] is None
    assert "provider_call" in artifact["forbidden_actions"]
    assert "telegram_return" in artifact["forbidden_actions"]


def test_artifact_requires_human_review():
    artifact = build_expert_staged_packet_artifact(_valid_packet(), created_at="2026-05-01T04:00:00Z")

    assert artifact["requires_human_review"] is True
    assert artifact["next_allowed_action"] == "human_review_staged_artifact"
    assert artifact["provider_plan_metadata"]["requires_operator_approval"] is True
    assert artifact["job_manifest_metadata"]["approval_required"] is True


def test_mismatched_packet_or_artifact_hashes_fail_closed():
    packet = _valid_packet()
    artifact = build_expert_staged_packet_artifact(packet, created_at="2026-05-01T04:00:00Z")

    wrong_packet = copy.deepcopy(packet)
    wrong_packet["packet_id"] = "expert-20260501-staged-other"
    wrong_packet_check = check_expert_staged_packet_artifact(artifact, packet=wrong_packet)
    assert wrong_packet_check["passed"] is False
    assert "packet_id_mismatch" in wrong_packet_check["violations"]

    wrong_provider_hash = copy.deepcopy(artifact)
    wrong_provider_hash["provider_plan_hash"] = "sha256:" + "1" * 64
    provider_check = check_expert_staged_packet_artifact(wrong_provider_hash, packet=packet)
    assert provider_check["passed"] is False
    assert "provider_plan_hash_mismatch" in provider_check["violations"]

    wrong_manifest_hash = copy.deepcopy(artifact)
    wrong_manifest_hash["manifest_hash"] = "sha256:" + "2" * 64
    manifest_check = check_expert_staged_packet_artifact(wrong_manifest_hash, packet=packet)
    assert manifest_check["passed"] is False
    assert "manifest_hash_mismatch" in manifest_check["violations"]

    wrong_metadata = copy.deepcopy(artifact)
    wrong_metadata["provider_plan_metadata"]["selected_provider"] = "future_provider"
    metadata_check = check_expert_staged_packet_artifact(wrong_metadata, packet=packet)
    assert metadata_check["passed"] is False
    assert "provider_plan_metadata_mismatch" in metadata_check["violations"]


def test_unsafe_packet_fails_closed_without_execution_authority():
    packet = _valid_packet(cloud_allowed=False)

    artifact = build_expert_staged_packet_artifact(packet, created_at="2026-05-01T04:00:00Z")

    assert artifact["passed"] is False
    assert artifact["execution_allowed"] is False
    assert artifact["provider_call_allowed"] is False
    assert artifact["telegram_return_allowed"] is False
    assert artifact["requires_human_review"] is True
    assert artifact["next_allowed_action"] == "repair_sanitized_packet_and_rerun_checks"
    assert "synthetic_handoff_failed" in artifact["violations"]
    assert "missing_explicit_cloud_allowed" in artifact["violations"]


def test_protected_private_markers_fail_closed():
    packet = _valid_packet(prompt="Review a synthetic parser near private logs and an api key.")

    artifact = build_expert_staged_packet_artifact(packet, created_at="2026-05-01T04:00:00Z")

    assert artifact["passed"] is False
    assert "protected_marker:private logs" in artifact["violations"]
    assert "protected_marker:api key" in artifact["violations"]
    assert artifact["execution_allowed"] is False
    assert artifact["provider_call_allowed"] is False
    assert artifact["telegram_return_allowed"] is False


def test_packet_input_is_not_mutated():
    packet = _valid_packet()
    original = copy.deepcopy(packet)

    build_expert_staged_packet_artifact(packet, created_at="2026-05-01T04:00:00Z")

    assert packet == original


def test_no_file_write_helper_is_added():
    assert not hasattr(staged_flow, "write_expert_staged_packet_artifact")
    assert not hasattr(staged_flow, "save_expert_staged_packet_artifact")


def test_unrelated_legal_sync_file_is_not_referenced_or_touched_by_module():
    source = inspect.getsource(staged_flow)

    assert "sync_legal_planning_to_mac" not in source
    assert "mac_eyes" not in source
    assert "OpenClawLegal" not in source


def test_staged_flow_module_does_not_import_or_call_external_surfaces(monkeypatch):
    source = inspect.getsource(staged_flow)
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

    assert imported_modules <= {"__future__", "expert_synthetic_handoff", "typing"}
    assert called_names.isdisjoint({"open", "openrouter_call", "run", "Popen", "urlopen", "Request", "systemctl"})
    forbidden_call_text = {
        "openrouter_call",
        "telegram_send",
        "gmail_send",
        "provider_execute",
        "model_execute",
        "runner_execute",
        "subprocess",
        "requests",
        "run_agent",
    }
    for text in forbidden_call_text:
        assert text not in source

    forbidden_modules = {
        "builder_watcher",
        "chief_llm",
        "chief_notify",
        "chief_sender",
        "cloud",
        "codex",
        "gateway",
        "gmail",
        "hermes_cli",
        "mcp",
        "openai",
        "openrouter",
        "pathlib",
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
    artifact = build_expert_staged_packet_artifact(_valid_packet(), created_at="2026-05-01T04:00:00Z")

    assert artifact["passed"] is True
    assert artifact["provider_call_allowed"] is False
    assert "expert_staged_packet_flow" in sys.modules