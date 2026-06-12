import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import model_work_package_router as router


FIXED_NOW = "2026-06-12T16:00:00+00:00"


def test_gemini_quick_package_does_not_require_fable_permission():
    package = router.build_model_work_package(
        task_type="quick explanation and friendly rewrite",
        requested_by_agent="cassandra",
        risk_tier="low",
        context_refs=["generated/read_models/safe_summary.json#summary"],
        created_at_utc=FIXED_NOW,
    )

    assert package["schema_version"] == "MODEL_WORK_PACKAGE_V0"
    assert package["resolved_model_class"] == "external_fast_worker"
    assert package["candidate_model"] == "Gemini Flash-class"
    assert package["approval_required"] is False
    assert package["permission_request_ref"] == ""
    assert router.maybe_build_model_consult_permission(package) is None
    assert package["execution_allowed"] is False
    assert package["advisory_only"] is True
    assert package["external_call_allowed"] is False


def test_codex_implementation_package_resolves_to_external_code_worker_without_extra_prompt():
    package = router.build_model_work_package(
        task_type="code implementation with tests and repo inspection",
        requested_by_agent="chief",
        owner_agent="codex",
        risk_tier="medium",
        context_refs=["tests/test_model_work_package_router.py"],
        created_at_utc=FIXED_NOW,
        operator_requested=True,
        bounded=True,
    )

    assert package["resolved_model_class"] == "external_code_worker"
    assert package["candidate_model"] == "Codex 5.5-class"
    assert package["approval_required"] is False
    assert package["execution_allowed"] is False
    assert package["runtime_mutation_allowed"] is False


def test_fable_architecture_review_creates_permission_request_and_does_not_execute():
    package = router.build_model_work_package(
        task_type="architecture policy product synthesis review",
        requested_by_agent="hermes",
        risk_tier="high",
        context_refs=["generated/read_models/model_orchestration_audit.json#summary"],
        created_at_utc=FIXED_NOW,
    )
    permission = router.maybe_build_model_consult_permission(package)

    assert package["resolved_model_class"] == "external_deep_reasoner"
    assert package["candidate_model"] == "Fable 5-class"
    assert package["approval_required"] is True
    assert package["execution_allowed"] is False
    assert permission is not None
    assert permission["schema_version"] == "MODEL_CONSULT_PERMISSION_REQUEST_V0"
    assert permission["target_model"] == "Fable 5-class"
    assert permission["operator_decision"] == "PENDING"
    assert permission["advisory_only"] is True
    assert permission["execution_allowed"] is False
    assert permission["sensitive_data_excluded"] is True


def test_local_redaction_package_stays_local():
    package = router.build_model_work_package(
        task_type="private redaction and classification summary",
        requested_by_agent="guardian",
        risk_tier="medium",
        context_refs=["generated/read_models/redaction_policy.json#allowed_fields"],
        created_at_utc=FIXED_NOW,
    )

    assert package["resolved_model_class"] == "local_sensitive"
    assert package["candidate_model"] == "local model"
    assert package["approval_required"] is False
    assert package["external_call_allowed"] is False


def test_team_workflow_includes_multiple_advisory_steps():
    workflow = router.build_team_model_workflow(
        workflow_id="model_work_team:test",
        context_refs=["generated/read_models/package.json#bounded"],
        created_at_utc=FIXED_NOW,
    )

    assert workflow["schema_version"] == "MODEL_WORK_TEAM_WORKFLOW_V0"
    assert [step["step_id"] for step in workflow["steps"]] == [
        "local_redaction_pass",
        "gemini_quick_pass",
        "codex_implementation_pass",
        "fable_review_pass",
    ]
    assert {step["model_class"] for step in workflow["steps"]} >= {
        "local_sensitive",
        "external_fast_worker",
        "external_code_worker",
        "external_deep_reasoner",
    }
    assert all(step["advisory_only"] is True for step in workflow["steps"])
    assert workflow["steps"][-1]["permission_required"] is True
    assert workflow["execution_allowed"] is False
    assert workflow["external_call_allowed"] is False


def test_fable_permission_prompt_contains_required_operator_context():
    package = router.build_model_work_package(
        task_type="high-stakes safety architecture review",
        risk_tier="high",
        context_refs=["generated/read_models/safety_packet.json#redacted"],
        created_at_utc=FIXED_NOW,
    )
    permission = router.maybe_build_model_consult_permission(package)
    prompt = permission["operator_prompt"]

    assert "Fable would be useful here" in prompt
    assert "product/policy architecture decision" in prompt
    assert "not just code or a quick summary" in prompt
    assert "generated/read_models/safety_packet.json#redacted" in prompt
    assert "exclude: secrets, raw docs, credentials" in prompt
    assert "Alternatives: Gemini only, Codex only, local only, defer" in prompt
    assert "Stop condition:" in prompt


def test_watch_desk_item_shape_for_pending_fable_permission():
    package = router.build_model_work_package(
        task_type="architecture policy review",
        risk_tier="high",
        context_refs=["generated/read_models/router_audit.json#summary"],
        created_at_utc=FIXED_NOW,
    )
    permission = router.maybe_build_model_consult_permission(package)
    item = router.build_watch_desk_item_for_model_package(package, permission_request=permission)

    assert item["lane"] == "guardian_approval"
    assert item["urgency"] == "needs_operator"
    assert item["push_class"] == "approval_waiting"
    assert item["source_receipt_ref"].endswith("#permission_request")
    assert item["state"]["execution_allowed"] is False
    assert "no model call is allowed" in item["one_next_safe_action"]


def test_receipts_and_result_keep_execution_false(tmp_path):
    package = router.build_model_work_package(
        task_type="quick summary",
        context_refs=["generated/read_models/safe.json#summary"],
        created_at_utc=FIXED_NOW,
    )
    package_receipt = router.write_model_work_package_receipt(
        package,
        receipt_path=tmp_path / "model_work_package_receipt.json",
        created_at_utc=FIXED_NOW,
    )
    result = router.build_model_consult_result(
        package,
        advisory_output_ref="generated/read_models/advisory_output.json#candidate",
        output_summary="Advisory summary ready.",
        created_at_utc=FIXED_NOW,
    )
    result_receipt = router.write_model_consult_result_receipt(
        result,
        receipt_path=tmp_path / "model_consult_result_receipt.json",
        created_at_utc=FIXED_NOW,
    )

    assert json.loads((tmp_path / "model_work_package_receipt.json").read_text())["model_call_performed"] is False
    assert json.loads((tmp_path / "model_consult_result_receipt.json").read_text())["external_action_performed"] is False
    assert package_receipt["execution_attempted"] is False
    assert package_receipt["external_call_performed"] is False
    assert result["schema_version"] == "MODEL_CONSULT_RESULT_V0"
    assert result["execution_attempted"] is False
    assert result["runtime_mutation_performed"] is False
    assert result["external_action_performed"] is False
    assert result_receipt["model_call_performed"] is False


def test_router_source_has_no_model_or_network_invocation_imports():
    source = Path("model_work_package_router.py").read_text(encoding="utf-8")
    forbidden_patterns = [
        r"^\s*import\s+requests\b",
        r"^\s*import\s+httpx\b",
        r"^\s*import\s+socket\b",
        r"^\s*import\s+subprocess\b",
        r"openai\b",
        r"anthropic\b",
        r"ollama\s+run",
        r"gemini\s+generate",
        r"openrouter\b",
        r"requests\.",
        r"httpx\.",
        r"Popen\s*\(",
        r"os\.system\s*\(",
    ]
    for pattern in forbidden_patterns:
        assert re.search(pattern, source, flags=re.MULTILINE | re.IGNORECASE) is None
