import ast
import builtins
import copy
import inspect
import sys

import expert_approval_packet as approval_module
from expert_approval_packet import build_expert_approval_packet, check_expert_approval_packet
from expert_escalation_packet import REQUIRED_SENSITIVITY_ATTESTATIONS, build_expert_escalation_packet
from expert_staged_packet_flow import build_expert_staged_packet_artifact


def _attestation() -> dict[str, bool]:
    return {key: True for key in REQUIRED_SENSITIVITY_ATTESTATIONS}


def _valid_packet(**overrides):
    packet = build_expert_escalation_packet(
        packet_id="expert-20260501-approval-code-review",
        created_at="2026-05-01T05:00:00Z",
        operator_request_summary="Review a synthetic public parser helper.",
        task_type="code_review",
        data_classification="synthetic_public",
        cloud_allowed=True,
        sensitivity_attestation=_attestation(),
        allowed_paths=("expert_approval_packet.py", "tests/test_expert_approval_packet.py"),
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


def _valid_staged_artifact(packet=None):
    source_packet = packet or _valid_packet()
    return build_expert_staged_packet_artifact(source_packet, created_at="2026-05-01T06:00:00Z")


def test_valid_staged_artifact_produces_approval_packet():
    packet = _valid_packet()
    staged_artifact = _valid_staged_artifact(packet)

    approval_packet = build_expert_approval_packet(
        packet,
        staged_artifact,
        created_at="2026-05-01T07:00:00Z",
        staged_artifact_ref="staged_artifact:expert-20260501-approval-code-review",
    )

    assert approval_packet["passed"] is True
    assert approval_packet["approval_packet_check"] == {"passed": True, "violations": [], "recommended_action": "pass"}
    assert approval_packet["packet_type"] == "external_expert.approval_packet"
    assert approval_packet["schema_version"] == 1
    assert approval_packet["created_at"] == "2026-05-01T07:00:00Z"
    assert approval_packet["packet_id"] == packet["packet_id"]
    assert approval_packet["task_title"] == packet["operator_request_summary"]
    assert approval_packet["task_summary"] == packet["prompt"]
    assert approval_packet["staged_artifact_summary"]["passed"] is True
    assert approval_packet["staged_artifact_summary"]["staged_packet_check"]["passed"] is True
    assert approval_packet["next_allowed_action"] == "human_review_approval_packet"
    assert approval_packet["boundary_statement"].startswith("This packet is for local human/Guardian review only")


def test_hashes_are_preserved_from_staged_artifact():
    packet = _valid_packet()
    staged_artifact = _valid_staged_artifact(packet)

    approval_packet = build_expert_approval_packet(packet, staged_artifact, created_at="2026-05-01T07:00:00Z")

    assert approval_packet["provider_plan_hash"] == staged_artifact["provider_plan_hash"]
    assert approval_packet["manifest_hash"] == staged_artifact["manifest_hash"]
    assert f"provider_plan_hash:{staged_artifact['provider_plan_hash']}" in approval_packet["source_artifact_refs"]
    assert f"manifest_hash:{staged_artifact['manifest_hash']}" in approval_packet["source_artifact_refs"]

    tampered = copy.deepcopy(approval_packet)
    tampered["provider_plan_hash"] = "sha256:" + "1" * 64
    check = check_expert_approval_packet(tampered, packet=packet, staged_artifact=staged_artifact)

    assert check["passed"] is False
    assert "provider_plan_hash_mismatch" in check["violations"]


def test_execution_provider_telegram_and_live_approval_flags_remain_false():
    packet = _valid_packet()
    staged_artifact = _valid_staged_artifact(packet)

    approval_packet = build_expert_approval_packet(packet, staged_artifact, created_at="2026-05-01T07:00:00Z")

    assert approval_packet["execution_allowed"] is False
    assert approval_packet["provider_call_allowed"] is False
    assert approval_packet["telegram_return_allowed"] is False
    assert approval_packet["approval_request_allowed"] is False
    assert approval_packet["requires_human_review"] is True
    assert "provider_call" in approval_packet["forbidden_actions"]
    assert "telegram_return" in approval_packet["forbidden_actions"]
    assert "live_guardian_approval_request" in approval_packet["forbidden_actions"]
    assert "not_live_approval" in approval_packet["required_human_acknowledgements"]
    assert "no_provider_call_authorized" in approval_packet["required_human_acknowledgements"]
    assert "model_selected" not in approval_packet["provider_role_metadata"]

    tampered = copy.deepcopy(approval_packet)
    tampered["approval_request_allowed"] = True
    check = check_expert_approval_packet(tampered, packet=packet, staged_artifact=staged_artifact)

    assert check["passed"] is False
    assert "approval_request_allowed" in check["violations"]


def test_protected_private_markers_fail_closed():
    packet = _valid_packet(prompt="Review a synthetic parser near private logs and an api key.")
    staged_artifact = _valid_staged_artifact(packet)

    approval_packet = build_expert_approval_packet(packet, staged_artifact, created_at="2026-05-01T07:00:00Z")

    assert approval_packet["passed"] is False
    assert approval_packet["execution_allowed"] is False
    assert approval_packet["provider_call_allowed"] is False
    assert approval_packet["telegram_return_allowed"] is False
    assert approval_packet["approval_request_allowed"] is False
    assert "source_packet_check_failed" in approval_packet["violations"]
    assert "staged_artifact_check_failed" in approval_packet["violations"]
    assert "protected_marker:private logs" in approval_packet["violations"]
    assert "protected_marker:api key" in approval_packet["violations"]

    clean_packet = _valid_packet()
    clean_staged_artifact = _valid_staged_artifact(clean_packet)
    clean_approval = build_expert_approval_packet(clean_packet, clean_staged_artifact, created_at="2026-05-01T07:00:00Z")
    clean_approval["task_summary"] = "Synthetic summary accidentally mentions a bot token."
    check = check_expert_approval_packet(clean_approval, packet=clean_packet, staged_artifact=clean_staged_artifact)

    assert check["passed"] is False
    assert "protected_marker:bot token" in check["violations"]


def test_missing_or_mismatched_staged_artifact_fails_closed():
    packet = _valid_packet()
    staged_artifact = _valid_staged_artifact(packet)
    approval_packet = build_expert_approval_packet(packet, staged_artifact, created_at="2026-05-01T07:00:00Z")

    missing_check = check_expert_approval_packet(approval_packet, packet=packet, staged_artifact=None)
    assert missing_check["passed"] is False
    assert "missing_staged_artifact" in missing_check["violations"]

    wrong_packet = copy.deepcopy(packet)
    wrong_packet["packet_id"] = "expert-20260501-approval-other"
    mismatch_check = check_expert_approval_packet(approval_packet, packet=wrong_packet, staged_artifact=staged_artifact)
    assert mismatch_check["passed"] is False
    assert "packet_id_mismatch" in mismatch_check["violations"]
    assert "staged_artifact_check_failed" in mismatch_check["violations"]

    wrong_staged = copy.deepcopy(staged_artifact)
    wrong_staged["manifest_hash"] = "sha256:" + "2" * 64
    wrong_staged_check = check_expert_approval_packet(approval_packet, packet=packet, staged_artifact=wrong_staged)
    assert wrong_staged_check["passed"] is False
    assert "manifest_hash_mismatch" in wrong_staged_check["violations"]


def test_packet_input_and_staged_artifact_are_not_mutated():
    packet = _valid_packet()
    staged_artifact = _valid_staged_artifact(packet)
    original_packet = copy.deepcopy(packet)
    original_staged_artifact = copy.deepcopy(staged_artifact)

    build_expert_approval_packet(packet, staged_artifact, created_at="2026-05-01T07:00:00Z")

    assert packet == original_packet
    assert staged_artifact == original_staged_artifact


def test_no_file_write_helper_is_added():
    assert not hasattr(approval_module, "write_expert_approval_packet")
    assert not hasattr(approval_module, "save_expert_approval_packet")


def test_unrelated_legal_or_mac_sync_files_are_not_referenced_by_module():
    source = inspect.getsource(approval_module)

    assert "sync_legal_planning_to_mac" not in source
    assert "mac_eyes" not in source
    assert "OpenClawLegal" not in source


def test_approval_packet_module_does_not_import_or_call_external_surfaces(monkeypatch):
    source = inspect.getsource(approval_module)
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
        "expert_escalation_packet",
        "expert_staged_packet_flow",
        "re",
        "typing",
    }
    assert called_names.isdisjoint({"open", "openrouter_call", "run", "Popen", "urlopen", "Request", "systemctl"})
    forbidden_call_text = {
        "openrouter_call",
        "telegram_send",
        "gmail_send",
        "guardian_send",
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
    packet = _valid_packet()
    staged_artifact = _valid_staged_artifact(packet)
    approval_packet = build_expert_approval_packet(packet, staged_artifact, created_at="2026-05-01T07:00:00Z")

    assert approval_packet["passed"] is True
    assert approval_packet["execution_allowed"] is False
    assert approval_packet["provider_call_allowed"] is False
    assert "expert_approval_packet" in sys.modules