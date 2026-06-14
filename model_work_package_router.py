"""Model Work Package Router V0.

Deterministic package and receipt builders for future model consults. This
module does not call models, create live approvals, run tools, or mutate
runtime/business systems.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from model_selection_policy_contract import MODEL_CLASSES


MODEL_WORK_PACKAGE_SCHEMA_VERSION = "MODEL_WORK_PACKAGE_V0"
MODEL_CONSULT_PERMISSION_SCHEMA_VERSION = "MODEL_CONSULT_PERMISSION_REQUEST_V0"
MODEL_CONSULT_RESULT_SCHEMA_VERSION = "MODEL_CONSULT_RESULT_V0"
MODEL_WORK_PACKAGE_RECEIPT_SCHEMA_VERSION = "MODEL_WORK_PACKAGE_RECEIPT_V0"
MODEL_CONSULT_RESULT_RECEIPT_SCHEMA_VERSION = "MODEL_CONSULT_RESULT_RECEIPT_V0"
TEAM_WORKFLOW_SCHEMA_VERSION = "MODEL_WORK_TEAM_WORKFLOW_V0"
MODULE_ROLE = "support_metadata"
CANONICAL_RUNTIME_SPINE_REF = "codex_work_package_lifecycle.py"
MIGRATION_NOTE = (
    "Retained for deterministic model consult/package metadata. Runtime queue, dispatch, "
    "ingest, proof verification, and Watch Desk projection are canonical in "
    "codex_work_package_lifecycle.py."
)

DEFAULT_REDACTION_POLICY = "redacted_refs_and_summaries_only"
DEFAULT_EXPECTED_OUTPUT_SCHEMA = "concise_advisory_response_v0"
DEFAULT_STOP_CONDITION = "Stop before any model/tool/runtime execution or unsupported claim."

AUTHORITY_FALSE = {
    "execution_allowed": False,
    "advisory_only": True,
    "receipt_required": True,
    "sensitive_data_excluded": True,
    "runtime_mutation_allowed": False,
    "external_call_allowed": False,
}

FAST_TASK_TERMS = (
    "quick",
    "explanation",
    "summary",
    "summarize",
    "brainstorm",
    "rewrite",
    "coach",
    "friendly",
)
CODE_TASK_TERMS = (
    "code",
    "implementation",
    "test",
    "repo",
    "script",
    "debug",
    "operational",
    "verification",
)
DEEP_REASONING_TERMS = (
    "architecture",
    "policy",
    "taste",
    "product",
    "high-stakes",
    "safety",
    "multi-agent",
    "synthesis",
)
LOCAL_TASK_TERMS = (
    "redaction",
    "classification",
    "private",
    "local",
    "sensitive",
)

FORBIDDEN_INPUTS = (
    "credentials",
    "tokens",
    "secrets",
    "raw private documents",
    "raw financial account details",
    "operator/device/session verification material",
    "browser/Gmail/Coupa content",
    "workbook bodies",
    "ledger rows",
)

FABLE_ALTERNATIVES = (
    "Gemini only",
    "Codex only",
    "local only",
    "defer",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object, length: int = 16) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:length]


def _content_hash(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").replace("-", " ").split())


def _as_list(values: Sequence[str] | None) -> list[str]:
    return [str(value) for value in values or [] if str(value).strip()]


def _contains_any(text: str, terms: Sequence[str]) -> bool:
    return any(term in text for term in terms)


def _model_class_known(model_class: str) -> str:
    return model_class if model_class in MODEL_CLASSES else "blocked_no_model"


def resolve_model_for_package(
    *,
    task_type: str,
    requested_model_class: str = "",
    risk_tier: str = "low",
    sensitive_data_excluded: bool = True,
    operator_requested: bool = True,
    bounded: bool = True,
) -> dict[str, Any]:
    """Resolve a model class label without allowing execution."""

    normalized_task = _normalize(task_type)
    requested = _model_class_known(str(requested_model_class or "").strip())
    if requested != "blocked_no_model":
        resolved = requested
        reason = "Requested model class is known in the existing model selection policy contract."
    elif not sensitive_data_excluded:
        resolved = "local_sensitive"
        reason = "Sensitive raw data is not excluded, so external model classes are blocked."
    elif _contains_any(normalized_task, LOCAL_TASK_TERMS):
        resolved = "local_sensitive"
        reason = "Private redaction/classification work stays local."
    elif _contains_any(normalized_task, CODE_TASK_TERMS):
        resolved = "external_code_worker"
        reason = "Code, test, repo inspection, debugging, and operational verification route to the code-worker class."
    elif _contains_any(normalized_task, DEEP_REASONING_TERMS) or risk_tier in {"high", "critical"}:
        resolved = "external_deep_reasoner"
        reason = "Architecture, policy, taste, product, safety, or multi-agent synthesis needs deep reasoning review."
    elif _contains_any(normalized_task, FAST_TASK_TERMS):
        resolved = "external_fast_worker"
        reason = "Low-risk quick advisory work fits the fast external worker class."
    else:
        resolved = "local_reasoning"
        reason = "Unclear advisory work defaults to local/internal reasoning posture."

    candidate_by_class = {
        "external_fast_worker": "Gemini Flash-class",
        "external_code_worker": "Codex 5.5-class",
        "external_deep_reasoner": "Fable 5-class",
        "local_sensitive": "local model",
        "local_reasoning": "local model",
        "local_small_fast": "local model",
    }
    approval_required = resolved == "external_deep_reasoner"
    if resolved == "external_code_worker" and operator_requested and bounded:
        approval_required = False
    if resolved == "external_fast_worker" and sensitive_data_excluded and risk_tier in {"low", "medium"}:
        approval_required = False
    if resolved.startswith("local"):
        approval_required = False

    return {
        "resolved_model_class": resolved,
        "candidate_model": candidate_by_class.get(resolved, "no model"),
        "reason_for_model_choice": reason,
        "approval_required": approval_required,
    }


def build_model_work_package(
    *,
    task_type: str,
    requested_by_agent: str = "chief",
    owner_agent: str = "",
    assignment_loop_ref: str = "",
    risk_tier: str = "low",
    requested_model_class: str = "",
    context_refs: Sequence[str] | None = None,
    redaction_policy: str = DEFAULT_REDACTION_POLICY,
    allowed_inputs: Sequence[str] | None = None,
    forbidden_inputs: Sequence[str] | None = None,
    expected_output_schema: str = DEFAULT_EXPECTED_OUTPUT_SCHEMA,
    stop_condition: str = DEFAULT_STOP_CONDITION,
    created_at_utc: str | None = None,
    operator_requested: bool = True,
    bounded: bool = True,
    sensitive_data_excluded: bool = True,
) -> dict[str, Any]:
    created_at_utc = created_at_utc or utc_now()
    owner_agent = owner_agent or requested_by_agent
    context_refs_list = _as_list(context_refs)
    routing = resolve_model_for_package(
        task_type=task_type,
        requested_model_class=requested_model_class,
        risk_tier=risk_tier,
        sensitive_data_excluded=sensitive_data_excluded,
        operator_requested=operator_requested,
        bounded=bounded,
    )
    package_id = "model_work_package:" + _short_hash(
        created_at_utc,
        requested_by_agent,
        owner_agent,
        task_type,
        tuple(context_refs_list),
        routing["resolved_model_class"],
    )
    permission_request_ref = (
        f"model_consult_permission:{_short_hash(package_id, routing['candidate_model'])}"
        if routing["approval_required"]
        else ""
    )
    return {
        "schema_version": MODEL_WORK_PACKAGE_SCHEMA_VERSION,
        "package_id": package_id,
        "created_at_utc": created_at_utc,
        "requested_by_agent": requested_by_agent,
        "owner_agent": owner_agent,
        "assignment_loop_ref": str(assignment_loop_ref or ""),
        "task_type": task_type,
        "risk_tier": risk_tier,
        "requested_model_class": requested_model_class,
        "resolved_model_class": routing["resolved_model_class"],
        "candidate_model": routing["candidate_model"],
        "reason_for_model_choice": routing["reason_for_model_choice"],
        "context_refs": context_refs_list,
        "redaction_policy": redaction_policy,
        "allowed_inputs": _as_list(allowed_inputs) or ["redacted summaries", "source refs", "expected output schema"],
        "forbidden_inputs": _as_list(forbidden_inputs) or list(FORBIDDEN_INPUTS),
        "expected_output_schema": expected_output_schema,
        "stop_condition": stop_condition,
        "execution_allowed": False,
        "advisory_only": True,
        "receipt_required": True,
        "sensitive_data_excluded": bool(sensitive_data_excluded),
        "runtime_mutation_allowed": False,
        "external_call_allowed": False,
        "approval_required": bool(routing["approval_required"]),
        "permission_request_ref": permission_request_ref,
        "status": "permission_required" if routing["approval_required"] else "staged_advisory_only",
    }


def build_fable_permission_prompt(permission_request: Mapping[str, Any]) -> str:
    context = ", ".join(str(ref) for ref in permission_request.get("data_to_be_sent", []) if str(ref).strip()) or "no context refs"
    alternatives = ", ".join(str(item) for item in permission_request.get("alternatives", []) if str(item).strip())
    return (
        "Fable would be useful here because this is a product/policy architecture decision, "
        "not just code or a quick summary. "
        f"I would send: [{context}]. "
        "I would exclude: secrets, raw docs, credentials, private account details, and raw operator/session material. "
        f"Cheaper model note: {permission_request.get('why_cheaper_model_insufficient')}. "
        f"Alternatives: {alternatives}. "
        f"Stop condition: {permission_request.get('stop_condition')}. "
        "Approve?"
    )


def maybe_build_model_consult_permission(package: Mapping[str, Any]) -> dict[str, Any] | None:
    if not package.get("approval_required"):
        return None
    request_id = str(package.get("permission_request_ref") or "")
    if not request_id:
        request_id = f"model_consult_permission:{_short_hash(package.get('package_id'), package.get('candidate_model'))}"
    why_cheaper = (
        "Gemini-class quick pass and Codex-class implementation are insufficient because this asks for "
        "architecture, policy, product taste, or high-stakes synthesis rather than a quick rewrite or code patch."
    )
    permission = {
        "schema_version": MODEL_CONSULT_PERMISSION_SCHEMA_VERSION,
        "request_id": request_id,
        "source_package_id": str(package.get("package_id") or ""),
        "target_model": str(package.get("candidate_model") or ""),
        "model_class": str(package.get("resolved_model_class") or ""),
        "proposed_task": str(package.get("task_type") or ""),
        "why_this_model": str(package.get("reason_for_model_choice") or ""),
        "why_cheaper_model_insufficient": why_cheaper,
        "data_to_be_sent": list(package.get("context_refs") or []),
        "sensitive_data_excluded": True,
        "expected_output_schema": str(package.get("expected_output_schema") or DEFAULT_EXPECTED_OUTPUT_SCHEMA),
        "stop_condition": str(package.get("stop_condition") or DEFAULT_STOP_CONDITION),
        "cost_risk_posture": "use only if operator agrees the deeper review value exceeds cost/latency",
        "alternatives": list(FABLE_ALTERNATIVES),
        "operator_decision": "PENDING",
        "advisory_only": True,
        "execution_allowed": False,
    }
    permission["operator_prompt"] = build_fable_permission_prompt(permission)
    return permission


def build_model_consult_result(
    package: Mapping[str, Any],
    *,
    advisory_output_ref: str = "",
    output_summary: str = "",
    status: str = "result_ready",
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    created_at_utc = created_at_utc or utc_now()
    result_id = "model_consult_result:" + _short_hash(package.get("package_id"), advisory_output_ref, output_summary, created_at_utc)
    return {
        "schema_version": MODEL_CONSULT_RESULT_SCHEMA_VERSION,
        "result_id": result_id,
        "package_id": str(package.get("package_id") or ""),
        "executing_model": str(package.get("candidate_model") or ""),
        "model_class": str(package.get("resolved_model_class") or ""),
        "advisory_output_ref": advisory_output_ref,
        "output_summary": output_summary,
        "execution_attempted": False,
        "runtime_mutation_performed": False,
        "external_action_performed": False,
        "receipt_ref": f"{result_id}#receipt",
        "status": status,
    }


def build_model_work_package_receipt(package: Mapping[str, Any], *, created_at_utc: str | None = None) -> dict[str, Any]:
    created_at_utc = created_at_utc or utc_now()
    receipt_id = "model_work_package_receipt:" + _short_hash(package.get("package_id"), created_at_utc)
    return {
        "schema_version": MODEL_WORK_PACKAGE_RECEIPT_SCHEMA_VERSION,
        "receipt_id": receipt_id,
        "created_at_utc": created_at_utc,
        "package_id": str(package.get("package_id") or ""),
        "receipt_type": "model_work_package_staged",
        "model_class": str(package.get("resolved_model_class") or ""),
        "candidate_model": str(package.get("candidate_model") or ""),
        "approval_required": bool(package.get("approval_required")),
        "permission_request_ref": str(package.get("permission_request_ref") or ""),
        "execution_attempted": False,
        "model_call_performed": False,
        "runtime_mutation_performed": False,
        "external_call_performed": False,
        "advisory_only": True,
        "content_hash": _content_hash(dict(package)),
    }


def write_model_work_package_receipt(
    package: Mapping[str, Any],
    *,
    receipt_path: str | Path,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    receipt = build_model_work_package_receipt(package, created_at_utc=created_at_utc)
    path = Path(receipt_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(receipt), encoding="utf-8")
    receipt["receipt_ref"] = f"{path.as_posix()}#receipt"
    return receipt


def build_model_consult_result_receipt(result: Mapping[str, Any], *, created_at_utc: str | None = None) -> dict[str, Any]:
    created_at_utc = created_at_utc or utc_now()
    receipt_id = "model_consult_result_receipt:" + _short_hash(result.get("result_id"), created_at_utc)
    return {
        "schema_version": MODEL_CONSULT_RESULT_RECEIPT_SCHEMA_VERSION,
        "receipt_id": receipt_id,
        "created_at_utc": created_at_utc,
        "result_id": str(result.get("result_id") or ""),
        "package_id": str(result.get("package_id") or ""),
        "status": str(result.get("status") or ""),
        "execution_attempted": False,
        "model_call_performed": False,
        "runtime_mutation_performed": False,
        "external_action_performed": False,
        "content_hash": _content_hash(dict(result)),
    }


def write_model_consult_result_receipt(
    result: Mapping[str, Any],
    *,
    receipt_path: str | Path,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    receipt = build_model_consult_result_receipt(result, created_at_utc=created_at_utc)
    path = Path(receipt_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(receipt), encoding="utf-8")
    receipt["receipt_ref"] = f"{path.as_posix()}#receipt"
    return receipt


def build_team_model_workflow(
    *,
    workflow_id: str = "model_work_team:default",
    context_refs: Sequence[str] | None = None,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    created_at_utc = created_at_utc or utc_now()
    refs = _as_list(context_refs)
    step_specs = (
        ("local_redaction_pass", "local_sensitive", "Redact and classify bounded context before any advisory pass.", False),
        ("gemini_quick_pass", "external_fast_worker", "Quick low-risk advisory summary or brainstorm over sanitized refs.", False),
        ("codex_implementation_pass", "external_code_worker", "Scoped code/test implementation package after operator-requested boundary.", False),
        ("fable_review_pass", "external_deep_reasoner", "Deep architecture or policy review over sanitized context.", True),
    )
    steps = [
        {
            "step_id": step_id,
            "model_class": model_class,
            "purpose": purpose,
            "input_refs": refs,
            "output_schema": DEFAULT_EXPECTED_OUTPUT_SCHEMA,
            "permission_required": permission_required,
            "advisory_only": True,
        }
        for step_id, model_class, purpose, permission_required in step_specs
    ]
    return {
        "schema_version": TEAM_WORKFLOW_SCHEMA_VERSION,
        "workflow_id": workflow_id,
        "created_at_utc": created_at_utc,
        "steps": steps,
        "execution_allowed": False,
        "external_call_allowed": False,
        "runtime_mutation_allowed": False,
        "status": "planned_advisory_only",
    }


def build_watch_desk_item_for_model_package(
    package: Mapping[str, Any],
    *,
    permission_request: Mapping[str, Any] | None = None,
    result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if permission_request:
        request_id = str(permission_request.get("request_id") or package.get("permission_request_ref") or "model_consult_permission")
        return {
            "item_id": f"model_consult_permission:{_short_hash(request_id)}",
            "lane": "guardian_approval",
            "urgency": "needs_operator",
            "plain_line": f"Model consult permission pending for {permission_request.get('target_model')}.",
            "source_receipt_ref": f"{request_id}#permission_request",
            "one_next_safe_action": "Review the existing model consult permission request; no model call is allowed from Watch Desk.",
            "push_class": "approval_waiting",
            "state": {
                "package_id": str(package.get("package_id") or ""),
                "permission_request_id": request_id,
                "model_class": str(permission_request.get("model_class") or ""),
                "operator_decision": str(permission_request.get("operator_decision") or "PENDING"),
                "execution_allowed": False,
            },
        }
    if result:
        result_id = str(result.get("result_id") or "model_consult_result")
        return {
            "item_id": f"model_consult_result:{_short_hash(result_id)}",
            "lane": "chief_runtime",
            "urgency": "watch",
            "plain_line": "Model consult result receipt is ready for review.",
            "source_receipt_ref": f"{result_id}#receipt",
            "one_next_safe_action": "Review the advisory result receipt before any deterministic executor action.",
            "push_class": "info",
            "state": {
                "package_id": str(package.get("package_id") or ""),
                "result_id": result_id,
                "status": str(result.get("status") or ""),
                "execution_attempted": False,
            },
        }
    return {
        "item_id": f"model_consult_blocked:{_short_hash(package.get('package_id'))}",
        "lane": "chief_runtime",
        "urgency": "blocked" if package.get("status") == "blocked" else "watch",
        "plain_line": "Model work package is staged as advisory-only; no execution is allowed.",
        "source_receipt_ref": f"{package.get('package_id')}#model_work_package",
        "one_next_safe_action": "Review the package fields and keep model execution blocked until an explicit later gate.",
        "push_class": "on_demand",
        "state": {
            "package_id": str(package.get("package_id") or ""),
            "status": str(package.get("status") or ""),
            "resolved_model_class": str(package.get("resolved_model_class") or ""),
            "execution_allowed": False,
        },
    }


__all__ = [
    "AUTHORITY_FALSE",
    "MODEL_CONSULT_PERMISSION_SCHEMA_VERSION",
    "MODEL_CONSULT_RESULT_SCHEMA_VERSION",
    "MODEL_WORK_PACKAGE_SCHEMA_VERSION",
    "build_fable_permission_prompt",
    "build_model_consult_result",
    "build_model_consult_result_receipt",
    "build_model_work_package",
    "build_model_work_package_receipt",
    "build_team_model_workflow",
    "build_watch_desk_item_for_model_package",
    "maybe_build_model_consult_permission",
    "resolve_model_for_package",
    "stable_json",
    "write_model_consult_result_receipt",
    "write_model_work_package_receipt",
]
