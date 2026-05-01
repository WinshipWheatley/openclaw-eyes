import ast
import builtins
import copy
import inspect
import sys

import pytest

import expert_execution_approval_receipt as receipt_module
from expert_escalation_job_manifest import build_expert_job_manifest, hash_expert_job_manifest
from expert_escalation_lane_policy import select_expert_lane
from expert_escalation_packet import REQUIRED_SENSITIVITY_ATTESTATIONS, build_expert_escalation_packet
from expert_provider_policy import hash_expert_provider_plan, select_expert_provider
from expert_execution_approval_receipt import (
    REQUIRED_FORBIDDEN_ACTION_ACKS,
    check_expert_execution_approval_receipt,
)


def _attestation() -> dict[str, bool]:
    return {key: True for key in REQUIRED_SENSITIVITY_ATTESTATIONS}


def _acknowledgements() -> dict[str, bool]:
    return {key: True for key in REQUIRED_FORBIDDEN_ACTION_ACKS}


def _valid_packet(**overrides):
    packet = build_expert_escalation_packet(
        packet_id="expert-20260430-receipt-code-review",
        created_at="2026-04-30T12:00:00Z",
        operator_request_summary="Review a synthetic public parser helper.",
        task_type="code_review",
        data_classification="synthetic_public",
        cloud_allowed=True,
        sensitivity_attestation=_attestation(),
        allowed_paths=("expert_execution_approval_receipt.py", "tests/test_expert_execution_approval_receipt.py"),
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


def _chain():
    packet = _valid_packet()
    lane_plan = select_expert_lane(packet)
    provider_plan = dict(select_expert_provider(packet, lane_plan))
    manifest = dict(build_expert_job_manifest(packet, created_at="2026-04-30T13:00:00Z"))
    receipt = _valid_receipt(packet, manifest, provider_plan)
    return packet, manifest, provider_plan, receipt


def _valid_receipt(packet, manifest, provider_plan, **overrides):
    receipt = {
        "receipt_schema_version": 1,
        "receipt_type": "external_expert.execution_approval_receipt",
        "approval_id": "GUARD-20260430-0001",
        "packet_id": packet["packet_id"],
        "manifest_hash": manifest["manifest_hash"],
        "provider_plan_hash": provider_plan["provider_plan_hash"],
        "selected_provider": provider_plan["selected_provider"],
        "provider_role": provider_plan["provider_role"],
        "execution_scope": "single_expert_job",
        "execution_allowed": True,
        "artifact_root": f"expert_artifacts/{packet['packet_id']}",
        "approved_by": "operator-winship",
        "requested_at": "2026-04-30T13:05:00Z",
        "approved_at": "2026-04-30T13:06:00Z",
        "expires_at": "2099-04-30T13:30:00Z",
        "decision": "approved",
        "guardian_hmac_binding": {"hash": "HASH1234", "binding_status": "placeholder"},
        "forbidden_actions_acknowledged": _acknowledgements(),
    }
    for key, value in overrides.items():
        if key == "forbidden_actions_acknowledged":
            merged = dict(receipt["forbidden_actions_acknowledged"])
            merged.update(value)
            receipt[key] = merged
        else:
            receipt[key] = value
    return receipt


def test_valid_bound_receipt_passes_without_execution():
    packet, manifest, provider_plan, receipt = _chain()

    check = check_expert_execution_approval_receipt(
        receipt,
        packet=packet,
        manifest=manifest,
        provider_plan=provider_plan,
        now="2026-04-30T13:07:00Z",
    )

    assert check.passed is True
    assert check.violations == []
    assert check.recommended_action == "pass"
    assert receipt["execution_allowed"] is True
    assert provider_plan["execution_allowed"] is False
    assert receipt["manifest_hash"] == hash_expert_job_manifest(manifest)
    assert receipt["provider_plan_hash"] == hash_expert_provider_plan(provider_plan)


def test_missing_receipt_fails_closed():
    check = check_expert_execution_approval_receipt(None, now="2026-04-30T13:07:00Z")

    assert check.passed is False
    assert check.recommended_action == "reject"
    assert check.violations == ["missing_approval_receipt"]


def test_stale_receipt_fails_closed():
    packet, manifest, provider_plan, receipt = _chain()
    receipt["expires_at"] = "2026-04-30T13:06:30Z"

    check = check_expert_execution_approval_receipt(
        receipt,
        packet=packet,
        manifest=manifest,
        provider_plan=provider_plan,
        now="2026-04-30T13:07:00Z",
    )

    assert check.passed is False
    assert "stale_approval_receipt" in check.violations


def test_receipt_requires_explicit_execution_allowed_true_and_approved_decision():
    packet, manifest, provider_plan, receipt = _chain()
    receipt["execution_allowed"] = False
    receipt["decision"] = "denied"

    check = check_expert_execution_approval_receipt(
        receipt,
        packet=packet,
        manifest=manifest,
        provider_plan=provider_plan,
        now="2026-04-30T13:07:00Z",
    )

    assert check.passed is False
    assert "execution_not_approved" in check.violations
    assert "decision_not_approved" in check.violations


def test_receipt_rejects_mismatched_packet_manifest_and_provider_plan():
    packet, manifest, provider_plan, receipt = _chain()
    wrong_packet = copy.deepcopy(packet)
    wrong_packet["packet_id"] = "expert-20260430-other"
    wrong_manifest = dict(manifest)
    wrong_manifest["packet_id"] = "expert-20260430-other"
    wrong_manifest["manifest_hash"] = "manifesthash-20260430-other"
    wrong_provider = dict(provider_plan)
    wrong_provider["selected_provider"] = "future_provider"
    wrong_provider["provider_plan_hash"] = "providerplanhash-20260430-other"

    check = check_expert_execution_approval_receipt(
        receipt,
        packet=wrong_packet,
        manifest=wrong_manifest,
        provider_plan=wrong_provider,
        now="2026-04-30T13:07:00Z",
    )

    assert check.passed is False
    assert "packet_id_mismatch" in check.violations
    assert "manifest_packet_id_mismatch" in check.violations
    assert "manifest_hash_mismatch" in check.violations
    assert "provider_drift" in check.violations
    assert "provider_plan_hash_mismatch" in check.violations


def test_receipt_rejects_mismatched_canonical_hashes():
    packet, manifest, provider_plan, receipt = _chain()
    receipt["manifest_hash"] = "sha256:" + "1" * 64
    receipt["provider_plan_hash"] = "sha256:" + "2" * 64

    check = check_expert_execution_approval_receipt(
        receipt,
        packet=packet,
        manifest=manifest,
        provider_plan=provider_plan,
        now="2026-04-30T13:07:00Z",
    )

    assert check.passed is False
    assert "manifest_hash_mismatch" in check.violations
    assert "provider_plan_hash_mismatch" in check.violations


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("requested_at", "not-a-time", "malformed_timestamp:requested_at"),
        ("approved_at", "not-a-time", "malformed_timestamp:approved_at"),
        ("expires_at", "not-a-time", "malformed_timestamp:expires_at"),
    ],
)
def test_receipt_rejects_malformed_timestamps(field, value, expected):
    packet, manifest, provider_plan, receipt = _chain()
    receipt[field] = value

    check = check_expert_execution_approval_receipt(
        receipt,
        packet=packet,
        manifest=manifest,
        provider_plan=provider_plan,
        now="2026-04-30T13:07:00Z",
    )

    assert check.passed is False
    assert expected in check.violations


def test_receipt_requires_guardian_binding_and_forbidden_action_acknowledgements():
    packet, manifest, provider_plan, receipt = _chain()
    receipt["guardian_hmac_binding"] = {}
    receipt["forbidden_actions_acknowledged"]["no_gmail_actions"] = False

    check = check_expert_execution_approval_receipt(
        receipt,
        packet=packet,
        manifest=manifest,
        provider_plan=provider_plan,
        now="2026-04-30T13:07:00Z",
    )

    assert check.passed is False
    assert "missing_guardian_hmac_binding" in check.violations
    assert "missing_forbidden_action_ack:no_gmail_actions" in check.violations


def test_receipt_rejects_unsafe_or_unscoped_artifact_root():
    packet, manifest, provider_plan, receipt = _chain()
    receipt["artifact_root"] = "expert_artifacts/shared"

    check = check_expert_execution_approval_receipt(
        receipt,
        packet=packet,
        manifest=manifest,
        provider_plan=provider_plan,
        now="2026-04-30T13:07:00Z",
    )

    assert check.passed is False
    assert "artifact_root_not_packet_scoped" in check.violations

    receipt["artifact_root"] = "../secret"
    unsafe = check_expert_execution_approval_receipt(
        receipt,
        packet=packet,
        manifest=manifest,
        provider_plan=provider_plan,
        now="2026-04-30T13:07:00Z",
    )
    assert "unsafe_artifact_root" in unsafe.violations


def test_receipt_module_does_not_import_or_call_execution_surfaces(monkeypatch):
    source = inspect.getsource(receipt_module)
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
        "dataclasses",
        "datetime",
        "expert_escalation_job_manifest",
        "expert_escalation_packet",
        "expert_provider_policy",
        "re",
        "typing",
    }
    assert called_names.isdisjoint({"openrouter_call", "run", "Popen", "urlopen", "Request"})
    forbidden_text = {
        "chief_llm",
        "openrouter_call",
        "runner_profiles",
        "runner_registry",
        "subprocess",
        "systemd",
        "requests",
    }
    for text in forbidden_text:
        assert text not in source

    forbidden_modules = {
        "chief_llm",
        "cloud",
        "codex",
        "gmail",
        "mcp",
        "openai",
        "requests",
        "runner_profiles",
        "runner_registry",
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
    packet, manifest, provider_plan, receipt = _chain()
    check = check_expert_execution_approval_receipt(
        receipt,
        packet=packet,
        manifest=manifest,
        provider_plan=provider_plan,
        now="2026-04-30T13:07:00Z",
    )

    assert check.passed is True
    assert "expert_execution_approval_receipt" in sys.modules