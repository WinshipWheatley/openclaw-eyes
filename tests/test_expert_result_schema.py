import ast
import builtins
import copy
import inspect
import sys

import pytest

import expert_result_schema as result_module
from expert_escalation_job_manifest import build_expert_job_manifest
from expert_escalation_lane_policy import select_expert_lane
from expert_escalation_packet import REQUIRED_SENSITIVITY_ATTESTATIONS, build_expert_escalation_packet
from expert_execution_approval_receipt import REQUIRED_FORBIDDEN_ACTION_ACKS
from expert_provider_policy import select_expert_provider
from expert_result_schema import check_expert_result_artifact


def _attestation() -> dict[str, bool]:
    return {key: True for key in REQUIRED_SENSITIVITY_ATTESTATIONS}


def _acknowledgements() -> dict[str, bool]:
    return {key: True for key in REQUIRED_FORBIDDEN_ACTION_ACKS}


def _valid_packet(**overrides):
    packet = build_expert_escalation_packet(
        packet_id="expert-20260430-result-code-review",
        created_at="2026-04-30T12:00:00Z",
        operator_request_summary="Review a synthetic public parser helper.",
        task_type="code_review",
        data_classification="synthetic_public",
        cloud_allowed=True,
        sensitivity_attestation=_attestation(),
        allowed_paths=("expert_result_schema.py", "tests/test_expert_result_schema.py"),
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
    provider_plan["provider_plan_hash"] = "providerplanhash-20260430-0002"
    manifest = dict(build_expert_job_manifest(packet, created_at="2026-04-30T13:00:00Z"))
    manifest["manifest_hash"] = "manifesthash-20260430-0002"
    receipt = {
        "receipt_schema_version": 1,
        "receipt_type": "external_expert.execution_approval_receipt",
        "approval_id": "GUARD-20260430-0002",
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
    result = _valid_result(packet, manifest, receipt, provider_plan)
    return packet, manifest, provider_plan, receipt, result


def _valid_result(packet, manifest, receipt, provider_plan, **overrides):
    result = {
        "result_schema_version": 1,
        "result_type": "external_expert.result_artifact",
        "packet_id": packet["packet_id"],
        "manifest_hash": manifest["manifest_hash"],
        "approval_receipt_id": receipt["approval_id"],
        "selected_provider": provider_plan["selected_provider"],
        "provider_role": provider_plan["provider_role"],
        "model_selected": None,
        "execution_status": "succeeded",
        "started_at": "2026-04-30T13:10:00Z",
        "completed_at": "2026-04-30T13:11:00Z",
        "summary": "Synthetic review completed with one low-risk test suggestion.",
        "findings": [
            {
                "severity": "low",
                "title": "Parser fixture coverage",
                "detail": "Add a public synthetic fixture for whitespace-only input.",
                "evidence_refs": ["tests/test_expert_result_schema.py"],
                "recommendation": "Keep the fixture local and synthetic.",
            }
        ],
        "assumptions": ["Inputs were synthetic and public."],
        "limitations": ["No live provider behavior was evaluated."],
        "requested_outputs": ["risk_summary", "test_suggestions"],
        "produced_outputs": ["risk_summary", "test_suggestions"],
        "artifact_paths": [f"expert_artifacts/{packet['packet_id']}/review-summary.md"],
        "stdout_excerpt": "",
        "stderr_excerpt": "",
        "safety_check": {
            "passed": True,
            "checked_at": "2026-04-30T13:11:30Z",
            "violations": [],
        },
    }
    for key, value in overrides.items():
        if key == "safety_check":
            merged = dict(result["safety_check"])
            merged.update(value)
            result[key] = merged
        else:
            result[key] = value
    return result


def test_valid_result_artifact_passes_with_bound_receipt():
    _packet, manifest, provider_plan, receipt, result = _chain()

    check = check_expert_result_artifact(
        result,
        approval_receipt=receipt,
        manifest=manifest,
        provider_plan=provider_plan,
    )

    assert check.passed is True
    assert check.violations == []
    assert check.recommended_action == "pass"
    assert result["model_selected"] is None


def test_missing_approval_receipt_fails_closed():
    _packet, manifest, provider_plan, _receipt, result = _chain()

    check = check_expert_result_artifact(
        result,
        approval_receipt=None,
        manifest=manifest,
        provider_plan=provider_plan,
    )

    assert check.passed is False
    assert "missing_approval_receipt" in check.violations


def test_result_rejects_manifest_and_provider_drift():
    _packet, manifest, provider_plan, receipt, result = _chain()
    result["manifest_hash"] = "manifesthash-20260430-drift"
    result["selected_provider"] = "future_provider"

    check = check_expert_result_artifact(
        result,
        approval_receipt=receipt,
        manifest=manifest,
        provider_plan=provider_plan,
    )

    assert check.passed is False
    assert "manifest_hash_mismatch" in check.violations
    assert "provider_drift" in check.violations


def test_result_rejects_model_selection_by_default():
    _packet, manifest, provider_plan, receipt, result = _chain()
    result["model_selected"] = "synthetic-approved-model"

    check = check_expert_result_artifact(
        result,
        approval_receipt=receipt,
        manifest=manifest,
        provider_plan=provider_plan,
    )

    assert check.passed is False
    assert "concrete_model_selection_not_allowed" in check.violations


@pytest.mark.parametrize(
    "artifact_paths",
    [
        ["../secret.txt"],
        ["/tmp/expert-result.md"],
        ["expert_artifacts/shared/review-summary.md"],
    ],
)
def test_result_rejects_unsafe_or_unscoped_artifact_paths(artifact_paths):
    _packet, manifest, provider_plan, receipt, result = _chain()
    result["artifact_paths"] = artifact_paths

    check = check_expert_result_artifact(
        result,
        approval_receipt=receipt,
        manifest=manifest,
        provider_plan=provider_plan,
    )

    assert check.passed is False
    assert any(
        violation in check.violations
        for violation in ("unsafe_artifact_path", "artifact_path_outside_receipt_root", "artifact_path_not_packet_scoped")
    )


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("started_at", "not-a-time", "malformed_timestamp:started_at"),
        ("completed_at", "not-a-time", "malformed_timestamp:completed_at"),
        ("execution_status", "unknown", "unknown_execution_status:unknown"),
    ],
)
def test_result_rejects_malformed_timestamps_and_unknown_status(field, value, expected):
    _packet, manifest, provider_plan, receipt, result = _chain()
    result[field] = value

    check = check_expert_result_artifact(
        result,
        approval_receipt=receipt,
        manifest=manifest,
        provider_plan=provider_plan,
    )

    assert check.passed is False
    assert expected in check.violations


def test_result_rejects_failed_or_missing_safety_check():
    _packet, manifest, provider_plan, receipt, result = _chain()
    result["safety_check"] = {"passed": False, "checked_at": "2026-04-30T13:11:30Z", "violations": ["blocked"]}

    check = check_expert_result_artifact(
        result,
        approval_receipt=receipt,
        manifest=manifest,
        provider_plan=provider_plan,
    )

    assert check.passed is False
    assert "safety_check_not_passed" in check.violations
    assert "safety_check_has_violations" in check.violations

    missing = copy.deepcopy(result)
    missing.pop("safety_check")
    missing_check = check_expert_result_artifact(
        missing,
        approval_receipt=receipt,
        manifest=manifest,
        provider_plan=provider_plan,
    )
    assert "missing_required_field:safety_check" in missing_check.violations
    assert "missing_safety_check" in missing_check.violations


def test_result_rejects_protected_or_sensitive_markers():
    _packet, manifest, provider_plan, receipt, result = _chain()
    result["summary"] = "Review mentions an api key and private logs."

    check = check_expert_result_artifact(
        result,
        approval_receipt=receipt,
        manifest=manifest,
        provider_plan=provider_plan,
    )

    assert check.passed is False
    assert "protected_marker:api key" in check.violations
    assert "protected_marker:private logs" in check.violations


def test_result_rejects_unbounded_stdout_and_stderr_excerpts():
    _packet, manifest, provider_plan, receipt, result = _chain()
    result["stdout_excerpt"] = "o" * 4001
    result["stderr_excerpt"] = "e" * 4001

    check = check_expert_result_artifact(
        result,
        approval_receipt=receipt,
        manifest=manifest,
        provider_plan=provider_plan,
    )

    assert check.passed is False
    assert "stdout_excerpt_too_long" in check.violations
    assert "stderr_excerpt_too_long" in check.violations


def test_result_module_does_not_import_or_call_execution_surfaces(monkeypatch):
    source = inspect.getsource(result_module)
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
        "expert_escalation_packet",
        "expert_execution_approval_receipt",
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
    _packet, manifest, provider_plan, receipt, result = _chain()
    check = check_expert_result_artifact(
        result,
        approval_receipt=receipt,
        manifest=manifest,
        provider_plan=provider_plan,
    )

    assert check.passed is True
    assert "expert_result_schema" in sys.modules