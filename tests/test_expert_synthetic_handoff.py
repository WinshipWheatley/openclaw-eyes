import ast
import builtins
import copy
import inspect
import sys

import pytest

import expert_synthetic_handoff as handoff_module
from expert_escalation_job_manifest import hash_expert_job_manifest
from expert_escalation_packet import REQUIRED_SENSITIVITY_ATTESTATIONS, build_expert_escalation_packet
from expert_provider_policy import hash_expert_provider_plan
from expert_synthetic_handoff import build_expert_synthetic_handoff, check_expert_synthetic_handoff


def _attestation() -> dict[str, bool]:
    return {key: True for key in REQUIRED_SENSITIVITY_ATTESTATIONS}


def _valid_packet(**overrides):
    packet = build_expert_escalation_packet(
        packet_id="expert-20260501-synthetic-code-review",
        created_at="2026-05-01T01:00:00Z",
        operator_request_summary="Review a synthetic public parser helper.",
        task_type="code_review",
        data_classification="synthetic_public",
        cloud_allowed=True,
        sensitivity_attestation=_attestation(),
        allowed_paths=("expert_synthetic_handoff.py", "tests/test_expert_synthetic_handoff.py"),
        forbidden_paths=("private-vaults", "secret-env-files", "gmail-bodies"),
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


def test_valid_synthetic_handoff_passes_without_execution():
    packet = _valid_packet()

    handoff = build_expert_synthetic_handoff(packet, created_at="2026-05-01T02:00:00Z")

    assert handoff["passed"] is True
    assert handoff["violations"] == []
    assert handoff["handoff_check"] == {"passed": True, "violations": [], "recommended_action": "pass"}
    assert handoff["synthetic_only"] is True
    assert handoff["execution_allowed"] is False
    assert handoff["service_wiring_allowed"] is False
    assert handoff["packet_check"]["passed"] is True
    assert handoff["receipt_check"]["passed"] is True
    assert handoff["result_check"]["passed"] is True
    assert handoff["lane_plan"]["execution_allowed"] is False
    assert handoff["provider_plan"]["execution_allowed"] is False
    assert handoff["job_manifest"]["execution_allowed"] is False
    assert handoff["synthetic_result_artifact"]["execution_allowed"] is False
    assert handoff["synthetic_result_artifact"]["model_selected"] is None
    assert handoff["synthetic_approval_receipt"]["synthetic_only"] is True
    assert handoff["synthetic_approval_receipt"]["live_guardian_request_made"] is False
    assert handoff["synthetic_approval_receipt"]["live_execution_allowed"] is False


def test_manifest_and_provider_hashes_are_preserved_and_validated():
    packet = _valid_packet()

    handoff = build_expert_synthetic_handoff(packet, created_at="2026-05-01T02:00:00Z")
    manifest = handoff["job_manifest"]
    provider_plan = handoff["provider_plan"]
    receipt = handoff["synthetic_approval_receipt"]
    result = handoff["synthetic_result_artifact"]

    assert handoff["manifest_hash"] == manifest["manifest_hash"] == receipt["manifest_hash"] == result["manifest_hash"]
    assert handoff["provider_plan_hash"] == provider_plan["provider_plan_hash"] == receipt["provider_plan_hash"]
    assert handoff["manifest_hash"] == hash_expert_job_manifest(manifest)
    assert handoff["provider_plan_hash"] == hash_expert_provider_plan(provider_plan)

    changed = copy.deepcopy(handoff)
    changed["manifest_hash"] = "sha256:" + "1" * 64
    check = check_expert_synthetic_handoff(changed, packet=packet, now="2026-05-01T02:00:00Z")

    assert check["passed"] is False
    assert "handoff_manifest_hash_mismatch" in check["violations"]


def test_mismatched_packet_provider_manifest_receipt_or_result_fails_closed():
    packet = _valid_packet()
    handoff = build_expert_synthetic_handoff(packet, created_at="2026-05-01T02:00:00Z")

    wrong_packet = copy.deepcopy(packet)
    wrong_packet["packet_id"] = "expert-20260501-other"
    packet_check = check_expert_synthetic_handoff(handoff, packet=wrong_packet, now="2026-05-01T02:00:00Z")
    assert packet_check["passed"] is False
    assert "handoff_packet_id_mismatch" in packet_check["violations"]

    wrong_provider = copy.deepcopy(handoff)
    wrong_provider["provider_plan"]["selected_provider"] = "future_provider"
    provider_check = check_expert_synthetic_handoff(wrong_provider, packet=packet, now="2026-05-01T02:00:00Z")
    assert provider_check["passed"] is False
    assert "provider_plan_hash_mismatch" in provider_check["violations"]

    wrong_manifest = copy.deepcopy(handoff)
    wrong_manifest["job_manifest"]["selected_lane"] = "security_review"
    manifest_check = check_expert_synthetic_handoff(wrong_manifest, packet=packet, now="2026-05-01T02:00:00Z")
    assert manifest_check["passed"] is False
    assert "manifest_hash_mismatch" in manifest_check["violations"]

    wrong_receipt = copy.deepcopy(handoff)
    wrong_receipt["synthetic_approval_receipt"]["provider_plan_hash"] = "sha256:" + "2" * 64
    receipt_check = check_expert_synthetic_handoff(wrong_receipt, packet=packet, now="2026-05-01T02:00:00Z")
    assert receipt_check["passed"] is False
    assert "approval_receipt_failed" in receipt_check["violations"]
    assert "provider_plan_hash_mismatch" in receipt_check["violations"]

    wrong_result = copy.deepcopy(handoff)
    wrong_result["synthetic_result_artifact"]["manifest_hash"] = "sha256:" + "3" * 64
    result_check = check_expert_synthetic_handoff(wrong_result, packet=packet, now="2026-05-01T02:00:00Z")
    assert result_check["passed"] is False
    assert "result_artifact_failed" in result_check["violations"]
    assert "manifest_hash_mismatch" in result_check["violations"]


def test_execution_authority_remains_false_even_when_nested_synthetic_receipt_binds_hashes():
    packet = _valid_packet()

    handoff = build_expert_synthetic_handoff(packet, created_at="2026-05-01T02:00:00Z")

    assert handoff["execution_allowed"] is False
    assert handoff["service_wiring_allowed"] is False
    assert handoff["provider_plan"]["execution_allowed"] is False
    assert handoff["job_manifest"]["execution_allowed"] is False
    assert handoff["synthetic_result_artifact"]["execution_allowed"] is False
    assert handoff["synthetic_approval_receipt"]["live_execution_allowed"] is False
    assert handoff["synthetic_approval_receipt"]["live_guardian_request_made"] is False

    tampered = copy.deepcopy(handoff)
    tampered["execution_allowed"] = True
    check = check_expert_synthetic_handoff(tampered, packet=packet, now="2026-05-01T02:00:00Z")

    assert check["passed"] is False
    assert "handoff_execution_allowed" in check["violations"]


@pytest.mark.parametrize(
    "artifact_paths",
    [
        ["../secret/result.json"],
        ["/tmp/result.json"],
        ["expert_artifacts/shared/result.json"],
    ],
)
def test_unsafe_artifact_paths_fail_closed(artifact_paths):
    packet = _valid_packet()
    handoff = build_expert_synthetic_handoff(packet, created_at="2026-05-01T02:00:00Z")
    handoff["synthetic_result_artifact"]["artifact_paths"] = artifact_paths

    check = check_expert_synthetic_handoff(handoff, packet=packet, now="2026-05-01T02:00:00Z")

    assert check["passed"] is False
    assert any(
        violation in check["violations"]
        for violation in ("unsafe_artifact_path", "artifact_path_outside_receipt_root", "artifact_path_not_packet_scoped")
    )


def test_protected_private_markers_fail_closed_in_packet_or_result():
    packet = _valid_packet(prompt="Review a synthetic parser near private logs.")

    refused = build_expert_synthetic_handoff(packet, created_at="2026-05-01T02:00:00Z")

    assert refused["passed"] is False
    assert "packet_checker_failed" in refused["violations"]
    assert "protected_marker:private logs" in refused["violations"]

    clean_packet = _valid_packet()
    handoff = build_expert_synthetic_handoff(clean_packet, created_at="2026-05-01T02:00:00Z")
    handoff["synthetic_result_artifact"]["summary"] = "Synthetic result mentions an api key."
    check = check_expert_synthetic_handoff(handoff, packet=clean_packet, now="2026-05-01T02:00:00Z")

    assert check["passed"] is False
    assert "protected_marker:api key" in check["violations"]


def test_packet_input_is_not_mutated():
    packet = _valid_packet()
    original = copy.deepcopy(packet)

    build_expert_synthetic_handoff(packet, created_at="2026-05-01T02:00:00Z")

    assert packet == original


def test_synthetic_handoff_module_does_not_import_or_call_external_surfaces(monkeypatch):
    source = inspect.getsource(handoff_module)
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
        "expert_escalation_job_manifest",
        "expert_escalation_lane_policy",
        "expert_escalation_packet",
        "expert_execution_approval_receipt",
        "expert_provider_policy",
        "expert_result_schema",
        "re",
        "typing",
    }
    assert called_names.isdisjoint({"openrouter_call", "run", "Popen", "urlopen", "Request", "systemctl"})
    forbidden_text = {
        "chief_llm",
        "openrouter_call",
        "telegram_send",
        "gmail_send",
        "subprocess",
        "systemd",
        "requests",
        "run_agent",
    }
    for text in forbidden_text:
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
    handoff = build_expert_synthetic_handoff(_valid_packet(), created_at="2026-05-01T02:00:00Z")

    assert handoff["passed"] is True
    assert handoff["execution_allowed"] is False
    assert "expert_synthetic_handoff" in sys.modules