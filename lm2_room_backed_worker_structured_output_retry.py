"""One-time room-backed LM2 structured-output retry V0.

Runs one approved local Ollama retry for Finance / Capital Hilton with a
room-backed package and strict JSON output enforcement. The model receives only
redacted, freshness-gated, decision-trace-aware context. Publication remains
gated by the schema adapter and deterministic verifier; failures publish a safe
fallback unless structured output enforcement itself is unavailable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import lm2_live_worker_pilot_boundary_packet as boundary
import lm2_room_backed_worker_one_time_pilot as prior_pilot
import proof_bundle_builder as bundles
import proof_to_response_runtime as runtime
import proof_to_response_schema_adapter as schema_adapter


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/LM2 Room Backed Worker Structured Output Retry.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/lm2_room_backed_worker_structured_output_retry.sqlite")

SCHEMA_VERSION = "lm2_room_backed_worker_structured_output_retry_v0"
READ_MODEL_ID = "lm2_room_backed_worker_structured_output_retry"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "LM2_ROOM_BACKED_WORKER_STRUCTURED_OUTPUT_RETRY_READY"
NOT_READY_STATUS = "LM2_ROOM_BACKED_WORKER_STRUCTURED_OUTPUT_RETRY_NOT_READY"

SCENARIO_ID = prior_pilot.SCENARIO_ID
WORKER_CLASS = prior_pilot.WORKER_CLASS
RUNTIME_REF = prior_pilot.RUNTIME_REF
MODEL_NAME = prior_pilot.MODEL_NAME
MODEL_REF = prior_pilot.MODEL_REF
PILOT_LANE = prior_pilot.PILOT_LANE
WORLD_REF = prior_pilot.WORLD_REF
THREAD_REF = prior_pilot.THREAD_REF
OBJECTIVE_REF = prior_pilot.OBJECTIVE_REF
QUESTION = prior_pilot.QUESTION
MODE = prior_pilot.MODE
PACKAGE_TYPE = prior_pilot.PACKAGE_TYPE
CANDIDATE_SOURCE = "lm2_room_backed_worker_structured_output_retry"
SOURCE_REQUEST_ID = "lm2_room_backed_worker_structured_output_retry_finance_capital_hilton_payment_watch"
OLLAMA_GENERATE_URL = "http://127.0.0.1:11434/api/generate"
STRUCTURED_OUTPUT_METHOD = "ollama_api_generate_format_json_schema"

PRECONDITIONS = {
    "lm2_structured_output_retry_operator_approval": {
        "filename": "lm2_structured_output_retry_operator_approval.json",
        "accepted_statuses": ("LM2_STRUCTURED_OUTPUT_RETRY_OPERATOR_APPROVAL_READY",),
    },
    "lm2_structured_output_retry_approval_packet": {
        "filename": "lm2_structured_output_retry_approval_packet.json",
        "accepted_statuses": ("LM2_STRUCTURED_OUTPUT_RETRY_APPROVAL_PACKET_READY",),
    },
    "lm2_room_backed_worker_pilot_postmortem": {
        "filename": "lm2_room_backed_worker_pilot_postmortem.json",
        "accepted_statuses": ("LM2_ROOM_BACKED_WORKER_PILOT_POSTMORTEM_READY",),
    },
    "lm2_room_backed_worker_one_time_pilot": {
        "filename": prior_pilot.JSON_EXPORT_NAME,
        "accepted_statuses": (prior_pilot.READY_STATUS,),
    },
    "lm2_room_backed_worker_pilot_approval_packet": {
        "filename": "lm2_room_backed_worker_pilot_approval_packet.json",
        "accepted_statuses": ("LM2_ROOM_BACKED_WORKER_PILOT_APPROVAL_PACKET_READY",),
    },
    "lm2_room_backed_worker_pilot_boundary": {
        "filename": boundary.ROOM_BACKED_JSON_EXPORT_NAME,
        "accepted_statuses": (boundary.ROOM_BACKED_READY_STATUS,),
    },
    "project_room_sourceset_contract": {
        "filename": "project_room_sourceset_contract.json",
        "accepted_statuses": ("PROJECT_ROOM_SOURCESET_CONTRACT_READY",),
    },
    "project_room_package_compiler_integration": {
        "filename": "project_room_package_compiler_integration.json",
        "accepted_statuses": ("PROJECT_ROOM_PACKAGE_COMPILER_INTEGRATION_READY",),
    },
    "proof_bundle_freshness_trace_integration": {
        "filename": bundles.FRESHNESS_TRACE_STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (bundles.FRESHNESS_TRACE_READY_STATUS,),
    },
    "proof_bundle_builder_redaction_integration": {
        "filename": bundles.REDACTION_STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (bundles.REDACTION_READY_STATUS,),
    },
    "context_freshness_decision_trace_gate": {
        "filename": "context_freshness_decision_trace_gate.json",
        "accepted_statuses": ("CONTEXT_FRESHNESS_DECISION_TRACE_GATE_READY",),
    },
    "context_compaction_preview_policy": {
        "filename": "context_compaction_preview_policy.json",
        "accepted_statuses": ("CONTEXT_COMPACTION_PREVIEW_POLICY_READY",),
    },
    "proof_to_response_schema_adapter": {
        "filename": schema_adapter.STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (schema_adapter.READY_STATUS,),
    },
    "proof_to_response_runtime": {
        "filename": runtime.STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (runtime.READY_STATUS,),
    },
    "local_model_selection_for_proof_response": {
        "filename": "local_model_selection_for_proof_response.json",
        "accepted_statuses": ("LOCAL_MODEL_SELECTION_FOR_PROOF_RESPONSE_READY",),
    },
}

REQUIRED_RECEIPT_REFS = (
    "operator_approval_receipt",
    "structured_output_boundary_receipt",
    "room_backed_package_receipt",
    "project_room_readiness_receipt",
    "worker_package_boundary_receipt",
    "model_invocation_boundary_receipt",
    "redacted_proof_bundle_receipt",
    "no_external_provider_receipt",
    "no_tool_authority_receipt",
    "worker_started_receipt",
    "model_invocation_attempt_receipt",
    "raw_draft_captured_receipt",
    "schema_adapter_pass_fail_receipt",
    "worker_stopped_receipt",
    "verifier_pass_fail_receipt",
    "no_business_action_receipt",
)

PROTECTED_ACTIONS_NOT_AUTHORIZED = (
    "repeated_invocations",
    "external_provider",
    "tool_use",
    "browser_gmail_coupa",
    "email_send",
    "send",
    "submit",
    "ledger_mutation",
    "workbook_mutation",
    "pdf_export",
    "paid_marking",
    "memory_promotion",
    "additional_worker_spawning",
    "shell_commands_by_lm2",
    "file_system_mutation_by_lm2",
    "push_merge",
    "raw_finance_private_proof",
    "operator_device_session_secrets",
    "stale_source_as_current_truth",
    "duplicate_versions_as_equal_evidence",
    "missing_context_as_permission_to_invent",
)

UNSAFE_TRUE_KEYS = set(prior_pilot.UNSAFE_TRUE_KEYS) | {
    "external_provider_used",
    "external_provider_connected",
    "external_llm_invoked",
    "tool_authority",
    "tool_authority_allowed",
    "tool_execution_allowed",
    "tool_execution_performed",
    "business_action_authority",
    "business_action_allowed",
    "business_action_performed",
    "browser_access_allowed",
    "browser_opened",
    "gmail_allowed",
    "gmail_opened",
    "coupa_allowed",
    "coupa_opened",
    "email_send_allowed",
    "email_send_performed",
    "portal_submit_allowed",
    "submit_performed",
    "ledger_mutation_allowed",
    "ledger_mutation_performed",
    "workbook_mutation_allowed",
    "workbook_mutation_performed",
    "pdf_export_allowed",
    "pdf_export_performed",
    "paid_marking_allowed",
    "paid_marking_performed",
    "memory_promotion_allowed",
    "memory_promotion_performed",
    "additional_worker_spawning_allowed",
    "additional_worker_spawn_performed",
    "lm2_shell_commands_allowed",
    "lm2_shell_command_performed",
    "lm2_file_system_mutation_allowed",
    "lm2_file_system_mutation_performed",
    "git_push_allowed",
    "git_push_performed",
    "git_merge_allowed",
    "git_merge_performed",
    "raw_financial_proof_sent",
    "operator_device_session_secret_sent",
    "stale_source_current_truth_allowed",
    "duplicate_versions_equal_evidence_allowed",
    "missing_context_invention_allowed",
    "protected_actions_allowed",
    "authority_granted",
    "authority_grant_allowed",
    "paid",
    "sent",
    "submitted",
    "executed",
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path | str) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path | str, payload: Mapping[str, Any]) -> None:
    path = _rooted(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _content_hash(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _walk_values(payload: Any):
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield str(key), value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def unsafe_true_grants(payload: Mapping[str, Any]) -> list[str]:
    return sorted({key for key, value in _walk_values(payload) if key in UNSAFE_TRUE_KEYS and value is True})


def _status(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status") or payload.get("readiness_status") or payload.get("contract_status") or "")


def precondition_rows(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, spec in PRECONDITIONS.items():
        filename = str(spec["filename"])
        payload = _load_json(root / filename)
        observed = _status(payload)
        accepted = [str(status) for status in spec["accepted_statuses"]]
        rows.append(
            {
                "precondition_ref": ref,
                "source_ref": f"generated/read_models/{filename}",
                "observed_status": observed,
                "accepted_statuses": accepted,
                "ready": observed in accepted,
            }
        )
    return rows


def approval_scope_matches(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> bool:
    root = _rooted(read_model_root)
    approval = _load_json(root / "lm2_structured_output_retry_operator_approval.json")
    scope = approval.get("approval_scope") if isinstance(approval.get("approval_scope"), Mapping) else {}
    return (
        approval.get("status") == "LM2_STRUCTURED_OUTPUT_RETRY_OPERATOR_APPROVAL_READY"
        and approval.get("operator_decision") == "approve_one_time_room_backed_lm2_structured_output_retry"
        and approval.get("approved_for_one_future_attempt_only") is True
        and scope.get("attempt_limit") == 1
        and scope.get("worker_class") == WORKER_CLASS
        and scope.get("runtime_ref") == RUNTIME_REF
        and scope.get("model_ref") == MODEL_REF
        and scope.get("model_name") == MODEL_NAME
        and scope.get("lane") == PILOT_LANE
        and scope.get("objective") == OBJECTIVE_REF
        and scope.get("pilot_question") == QUESTION
        and scope.get("mode") == MODE
        and scope.get("package_type") == PACKAGE_TYPE
        and scope.get("structured_output_required") is True
        and scope.get("schema_adapter_required") is True
        and scope.get("verifier_required") is True
        and scope.get("fallback_required") is True
    )


def approval_unused(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> bool:
    prior = _load_json(_rooted(read_model_root) / JSON_EXPORT_NAME)
    usage = prior.get("approval_usage") if isinstance(prior.get("approval_usage"), Mapping) else {}
    return usage.get("approval_used") is not True


def package_matches_scope(package: Mapping[str, Any]) -> bool:
    return prior_pilot.package_matches_scope(package)


def build_prompt(lm_package: Mapping[str, Any], schema: Mapping[str, Any]) -> str:
    payload = {
        "worker_class": WORKER_CLASS,
        "task": "Return one strict JSON proof-to-response candidate for the operator question.",
        "question": QUESTION,
        "strict_rules": [
            "Return JSON only.",
            "No markdown, code fences, prose outside JSON, or hidden reasoning.",
            "Use only the room-backed package below.",
            "Do not claim paid, sent, submitted, executed, or ledger changed.",
            "Do not promise protected action.",
            "Do not ask for hidden/private context.",
            "Do not call tools.",
            "Use exactly the required JSON keys.",
        ],
        "required_output_keys": list(schema_adapter.STRICT_DRAFT_FIELDS),
        "required_json_schema": dict(schema),
        "valid_json_example": dict(boundary.ROOM_BACKED_EXPECTED_RESPONSE),
        "room_backed_package": lm_package,
    }
    return stable_json(payload)


def invoke_ollama_structured_once(
    prompt: str,
    schema: Mapping[str, Any],
    *,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    started_at = utc_now()
    request_payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "format": dict(schema),
        "options": {
            "temperature": 0,
            "num_predict": 500,
        },
    }
    request = urllib.request.Request(
        OLLAMA_GENERATE_URL,
        data=json.dumps(request_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    base = {
        "attempted": True,
        "started_at": started_at,
        "completed_at": "",
        "runtime_ref": RUNTIME_REF,
        "model_name": MODEL_NAME,
        "method": STRUCTURED_OUTPUT_METHOD,
        "structured_output_requested": True,
        "format_schema_sent": True,
        "temperature": 0,
        "request_payload_hash": _content_hash(request_payload),
    }
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        raw_text = str(body.get("response") or "")
        return {
            **base,
            "completed_at": utc_now(),
            "returncode": 0,
            "http_status": 200,
            "stdout": raw_text,
            "stderr": "",
            "timed_out": False,
            "structured_output_enforced": True,
            "structured_output_unavailable_reason": "",
            "response_body_hash": _content_hash(body),
        }
    except TimeoutError as exc:
        return {
            **base,
            "completed_at": utc_now(),
            "returncode": 124,
            "http_status": 0,
            "stdout": "",
            "stderr": str(exc),
            "timed_out": True,
            "structured_output_enforced": False,
            "structured_output_unavailable_reason": "ollama_structured_output_timeout",
            "response_body_hash": "",
        }
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        return {
            **base,
            "completed_at": utc_now(),
            "returncode": 1,
            "http_status": int(exc.code),
            "stdout": "",
            "stderr": error_body or str(exc),
            "timed_out": False,
            "structured_output_enforced": False,
            "structured_output_unavailable_reason": f"ollama_http_error:{exc.code}",
            "response_body_hash": _content_hash(error_body),
        }
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        return {
            **base,
            "completed_at": utc_now(),
            "returncode": 1,
            "http_status": 0,
            "stdout": "",
            "stderr": str(exc),
            "timed_out": False,
            "structured_output_enforced": False,
            "structured_output_unavailable_reason": "ollama_structured_output_call_failed",
            "response_body_hash": "",
        }


def safe_room_backed_fallback_candidate(verifier_bundle: Mapping[str, Any], *, reason: str) -> dict[str, Any]:
    return {
        "response_id": "lm2_room_backed_worker_structured_output_retry:fallback:finance_capital_hilton_payment_watch",
        "proof_bundle_id": str(verifier_bundle.get("proof_bundle_id") or ""),
        "speaker_ref": str(verifier_bundle.get("response_speaker_ref") or "chief"),
        "draft_headline": "Payment evidence needed",
        "draft_body": "Coupa is processing. I can't mark this paid until payment evidence is attached. The ledger stays untouched.",
        "draft_next_step": "Attach payment evidence.",
        "claimed_facts": ["payment_evidence_missing", "processor_processing", "ledger_untouched", "paid_false"],
        "implied_actions": [],
        "requested_controls": ["attach_proof"],
        "uncertainty_notes": [reason] if reason else [],
    }


def publish_from_adapter(
    adapter_result: Mapping[str, Any],
    verifier_bundle: Mapping[str, Any],
    *,
    generated_at: str,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    if adapter_result.get("verifier_ready") is True:
        verifier_result = dict(adapter_result.get("verifier_result") or {})
        candidate = dict(adapter_result.get("adapted_candidate") or {})
        published = runtime._published_response_from_candidate(
            candidate,
            verifier_bundle,
            generated_at=generated_at,
            verification_status="publishable",
            candidate_source=CANDIDATE_SOURCE,
        )
        return verifier_result, published, ""

    reasons = [str(error) for error in adapter_result.get("adapter_errors") or []]
    reasons.extend(str(error) for error in adapter_result.get("verifier_failure_reasons") or [])
    fallback_reason = "; ".join(reasons) or "adapter_or_verifier_failed"
    fallback = safe_room_backed_fallback_candidate(verifier_bundle, reason=fallback_reason)
    fallback_verifier = runtime.verify_candidate_response(fallback, verifier_bundle)
    if fallback_verifier.get("publishable") is not True:
        fallback = runtime._safe_fallback_candidate(
            verifier_bundle,
            reason="; ".join(str(error) for error in fallback_verifier.get("verification_errors") or []) or fallback_reason,
        )
    published = runtime._published_response_from_candidate(
        fallback,
        verifier_bundle,
        generated_at=generated_at,
        verification_status="fallback",
        candidate_source=CANDIDATE_SOURCE,
        fallback_reason=fallback_reason,
    )
    verifier_result = dict(adapter_result.get("verifier_result") or fallback_verifier)
    if not verifier_result:
        verifier_result = fallback_verifier
    verifier_result["fallback_verifier_result"] = fallback_verifier
    return verifier_result, published, fallback_reason


def _receipt(
    receipt_ref: str,
    *,
    receipt_status: str,
    created_at: str,
    phase: str,
    proof_summary: str,
    source_ref: str = "",
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    body = dict(payload or {})
    return {
        "receipt_id": f"lm2_structured_output_retry:{receipt_ref}",
        "receipt_ref": receipt_ref,
        "receipt_status": receipt_status,
        "created_at": created_at,
        "phase": phase,
        "source_ref": source_ref,
        "proof_summary": proof_summary,
        "payload_hash": _content_hash(body) if body else "",
        "payload": body,
    }


def action_flags() -> dict[str, bool]:
    return prior_pilot.action_flags()


def build_receipts(
    *,
    package: Mapping[str, Any],
    room_gate: Mapping[str, Any],
    freshness_gate: Mapping[str, Any],
    invocation_result: Mapping[str, Any],
    adapter_result: Mapping[str, Any],
    verifier_result: Mapping[str, Any],
    published_response: Mapping[str, Any],
    fallback_reason: str,
    structured_output_enforced: bool,
    structured_output_unavailable_reason: str,
    generated_at: str,
) -> list[dict[str, Any]]:
    schema_passed = adapter_result.get("parse_status") == schema_adapter.PARSE_STATUS_PARSED and not adapter_result.get("adapter_errors")
    verifier_passed = adapter_result.get("verifier_ready") is True and verifier_result.get("publishable") is True
    receipts = [
        _receipt(
            "operator_approval_receipt",
            receipt_status="present",
            created_at=generated_at,
            phase="before_future_retry",
            source_ref="generated/read_models/lm2_structured_output_retry_operator_approval.json",
            proof_summary="Operator approved one future room-backed LM2 structured-output retry.",
        ),
        _receipt(
            "structured_output_boundary_receipt",
            receipt_status="present" if structured_output_enforced else "failed",
            created_at=generated_at,
            phase="before_future_retry",
            source_ref="generated/read_models/lm2_structured_output_retry_approval_packet.json",
            proof_summary="Structured-output boundary required Ollama API format with the response JSON schema.",
            payload={
                "method": invocation_result.get("method"),
                "structured_output_requested": invocation_result.get("structured_output_requested") is True,
                "format_schema_sent": invocation_result.get("format_schema_sent") is True,
                "structured_output_enforced": structured_output_enforced,
                "structured_output_unavailable_reason": structured_output_unavailable_reason,
            },
        ),
        _receipt(
            "room_backed_package_receipt",
            receipt_status="present",
            created_at=generated_at,
            phase="before_future_retry",
            source_ref="generated/read_models/lm2_room_backed_worker_pilot_boundary.json",
            proof_summary="Room-backed package was built for Finance / Capital Hilton payment watch.",
            payload={
                "package_ref": package.get("package_ref"),
                "project_room_id": package.get("project_room_id"),
                "room_backed_package_required": package.get("room_backed_package_required") is True,
            },
        ),
        _receipt(
            "project_room_readiness_receipt",
            receipt_status="present",
            created_at=generated_at,
            phase="before_future_retry",
            source_ref="generated/read_models/project_room_sourceset_contract.json",
            proof_summary="Project room/source room gates were checked before invocation.",
            payload=dict(room_gate),
        ),
        _receipt(
            "worker_package_boundary_receipt",
            receipt_status="present",
            created_at=generated_at,
            phase="before_future_retry",
            source_ref="generated/read_models/lm2_room_backed_worker_pilot_boundary.json",
            proof_summary="Worker package boundary limits input, output, tools, and stop conditions.",
            payload={"worker_class": WORKER_CLASS, "package_type": PACKAGE_TYPE, "one_bounded_objective": True},
        ),
        _receipt(
            "model_invocation_boundary_receipt",
            receipt_status="present",
            created_at=generated_at,
            phase="before_future_retry",
            source_ref="generated/read_models/lm2_structured_output_retry_operator_approval.json",
            proof_summary="Invocation boundary matched approved runtime and model.",
            payload={"runtime_ref": RUNTIME_REF, "model_name": MODEL_NAME, "attempt_limit": 1},
        ),
        _receipt(
            "redacted_proof_bundle_receipt",
            receipt_status="present",
            created_at=generated_at,
            phase="before_future_retry",
            source_ref="generated/read_models/proof_bundle_freshness_trace_status.json",
            proof_summary="Only redacted freshness-gated proof context and summaries were included.",
            payload=dict(freshness_gate),
        ),
        _receipt(
            "no_external_provider_receipt",
            receipt_status="present",
            created_at=generated_at,
            phase="before_future_retry",
            proof_summary="No external provider path was used.",
            payload={"external_provider_used": False},
        ),
        _receipt(
            "no_tool_authority_receipt",
            receipt_status="present",
            created_at=generated_at,
            phase="before_future_retry",
            proof_summary="The LM2 worker had no tool authority.",
            payload={"tool_authority": False, "tool_execution_performed": False},
        ),
        _receipt(
            "worker_started_receipt",
            receipt_status="present",
            created_at=generated_at,
            phase="after_future_retry",
            proof_summary="The bounded LM2 retry attempt started.",
            payload={"attempt_number": 1, "worker_class": WORKER_CLASS},
        ),
        _receipt(
            "model_invocation_attempt_receipt",
            receipt_status="present",
            created_at=generated_at,
            phase="after_future_retry",
            proof_summary="Exactly one local Ollama structured-output invocation attempt was recorded.",
            payload={
                "runtime_ref": invocation_result.get("runtime_ref"),
                "model_name": invocation_result.get("model_name"),
                "attempted": invocation_result.get("attempted") is True,
                "returncode": invocation_result.get("returncode"),
                "timed_out": invocation_result.get("timed_out") is True,
                "method": invocation_result.get("method"),
            },
        ),
        _receipt(
            "raw_draft_captured_receipt",
            receipt_status="present",
            created_at=generated_at,
            phase="after_future_retry",
            proof_summary="Raw model draft was captured by hash for adapter/verifier processing.",
            payload={
                "raw_stdout_hash": _content_hash(str(invocation_result.get("stdout") or "")),
                "raw_stderr_hash": _content_hash(str(invocation_result.get("stderr") or "")),
                "parse_status": adapter_result.get("parse_status"),
            },
        ),
        _receipt(
            "schema_adapter_pass_fail_receipt",
            receipt_status="present",
            created_at=generated_at,
            phase="after_future_retry",
            proof_summary=f"Schema adapter result: {'pass' if schema_passed else 'fail'}.",
            payload={
                "parse_status": adapter_result.get("parse_status"),
                "adapter_errors": list(adapter_result.get("adapter_errors") or []),
                "schema_adapter_passed": schema_passed,
            },
        ),
        _receipt(
            "worker_stopped_receipt",
            receipt_status="present",
            created_at=generated_at,
            phase="after_future_retry",
            proof_summary="The bounded LM2 retry stopped after one model attempt.",
            payload={"attempt_count": 1, "repeated_invocation_performed": False},
        ),
        _receipt(
            "verifier_pass_fail_receipt",
            receipt_status="present",
            created_at=generated_at,
            phase="after_future_retry",
            proof_summary=f"Verifier result after schema adapter: {'pass' if verifier_passed else 'fail'}.",
            payload={
                "schema_adapter_parse_status": adapter_result.get("parse_status"),
                "verifier_ready": adapter_result.get("verifier_ready") is True,
                "verification_errors": list(verifier_result.get("verification_errors") or []),
            },
        ),
    ]
    if verifier_passed:
        receipts.append(
            _receipt(
                "published_response_hash_receipt",
                receipt_status="present",
                created_at=generated_at,
                phase="after_future_retry",
                proof_summary="Verifier passed and the proof-to-response text was published.",
                payload={"response_content_hash": published_response.get("response_content_hash")},
            )
        )
    else:
        receipts.append(
            _receipt(
                "fallback_receipt",
                receipt_status="present",
                created_at=generated_at,
                phase="after_future_retry",
                proof_summary="Schema adapter or verifier failed; safe fallback was published.",
                payload={"fallback_reason": fallback_reason, "response_content_hash": published_response.get("response_content_hash")},
            )
        )
    receipts.append(
        _receipt(
            "no_business_action_receipt",
            receipt_status="present",
            created_at=generated_at,
            phase="after_future_retry",
            proof_summary="No protected business action was performed.",
            payload=action_flags(),
        )
    )
    return receipts


def sqlite_schema() -> str:
    return """
CREATE TABLE IF NOT EXISTS lm2_room_backed_worker_structured_output_retry_receipts (
  receipt_id TEXT PRIMARY KEY,
  receipt_ref TEXT NOT NULL,
  receipt_status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  phase TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  proof_summary TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  receipt_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lm2_structured_output_retry_receipts_ref
ON lm2_room_backed_worker_structured_output_retry_receipts(receipt_ref);
"""


def write_sqlite(receipts: list[Mapping[str, Any]], sqlite_path: Path = DEFAULT_SQLITE_PATH) -> int:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(sqlite_schema())
        conn.execute("DELETE FROM lm2_room_backed_worker_structured_output_retry_receipts")
        for row in receipts:
            conn.execute(
                """
INSERT INTO lm2_room_backed_worker_structured_output_retry_receipts (
  receipt_id, receipt_ref, receipt_status, created_at, phase, source_ref,
  proof_summary, payload_hash, receipt_json
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""",
                (
                    str(row.get("receipt_id") or ""),
                    str(row.get("receipt_ref") or ""),
                    str(row.get("receipt_status") or ""),
                    str(row.get("created_at") or ""),
                    str(row.get("phase") or ""),
                    str(row.get("source_ref") or ""),
                    str(row.get("proof_summary") or ""),
                    str(row.get("payload_hash") or ""),
                    stable_json(row),
                ),
            )
        conn.commit()
    return len(receipts)


def sqlite_row_count(sqlite_path: Path = DEFAULT_SQLITE_PATH) -> int:
    path = _rooted(sqlite_path)
    if not path.exists():
        return 0
    with sqlite3.connect(path) as conn:
        row = conn.execute("SELECT COUNT(*) FROM lm2_room_backed_worker_structured_output_retry_receipts").fetchone()
    return int(row[0] if row else 0)


def build_latest_read_model(
    published_response: Mapping[str, Any],
    receipts: list[Mapping[str, Any]],
    *,
    generated_at: str,
) -> dict[str, Any]:
    source_context = published_response.get("source_context") if isinstance(published_response.get("source_context"), Mapping) else {}
    latest = {
        "schema_version": runtime.SCHEMA_VERSION,
        "read_model_id": runtime.LATEST_READ_MODEL_ID,
        "status": runtime.READY_STATUS,
        "generated_at": generated_at,
        "source_status_ref": f"generated/read_models/{JSON_EXPORT_NAME}",
        "source_request_id": f"{SOURCE_REQUEST_ID}:{generated_at}",
        "source_response_path": f"generated/read_models/{JSON_EXPORT_NAME}",
        "world_ref": WORLD_REF,
        "thread_ref": THREAD_REF,
        "selected_card_id": str(source_context.get("card_id") or "redacted_proof_bundle"),
        "selected_action_id": "lm2_room_backed_worker_structured_output_retry",
        "candidate_source": CANDIDATE_SOURCE,
        "expires_or_superseded_by": "",
        "stale_if_context_mismatch": True,
        "latest_response": dict(published_response),
        "latest_receipt_ref": next(
            (
                str(row.get("receipt_id"))
                for row in receipts
                if row.get("receipt_ref") in {"published_response_hash_receipt", "fallback_receipt"}
            ),
            "",
        ),
        "proof_to_response_status": str(published_response.get("verification_status") or ""),
        "proof_to_response_unavailable_reason": "",
        "details_collapsed": True,
        "authority_boundary": {"protected_actions_allowed": False},
        "implementation_boundary": action_flags(),
    }
    unsafe = unsafe_true_grants(latest) + runtime.unsafe_true_grants(latest)
    latest["machine_proof"] = {
        "latest_response_present": bool(published_response),
        "latest_context_scoped": True,
        "stale_if_context_mismatch": True,
        "candidate_source": CANDIDATE_SOURCE,
        "unsafe_true_grants": sorted(set(unsafe)),
        "unsafe_true_grants_absent": not unsafe,
        **action_flags(),
    }
    if unsafe:
        latest["status"] = runtime.NOT_READY_STATUS
    return latest


ModelInvoker = Callable[[str, Mapping[str, Any]], Mapping[str, Any]]


def run_structured_output_retry(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
    invoker: ModelInvoker | None = None,
    invoke_model: bool = False,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    package = prior_pilot.build_room_backed_package()
    redacted_bundle = prior_pilot.build_redacted_proof_bundle(read_model_root)
    verifier_bundle = prior_pilot.verifier_bundle_for_room(redacted_bundle)
    room_gate = prior_pilot.project_room_gate(package, read_model_root)
    freshness_gate = prior_pilot.freshness_gate_check(redacted_bundle)
    approval_matched = approval_scope_matches(read_model_root)
    unused_before = approval_unused(read_model_root)
    package_ready = package_matches_scope(package)
    schema = schema_adapter.strict_json_draft_schema()
    preconditions_ready = all(row.get("ready") is True for row in preconditions)
    all_gates_ready = (
        preconditions_ready
        and approval_matched
        and unused_before
        and package_ready
        and room_gate["project_room_ready"] is True
        and freshness_gate["freshness_allowed"] is True
    )
    lm_package = prior_pilot.lm_visible_room_package(package, redacted_bundle)
    prompt = build_prompt(lm_package, schema)
    if not invoke_model:
        invocation_result = {
            "attempted": False,
            "started_at": "",
            "completed_at": "",
            "runtime_ref": RUNTIME_REF,
            "model_name": MODEL_NAME,
            "method": STRUCTURED_OUTPUT_METHOD,
            "returncode": None,
            "http_status": None,
            "stdout": "",
            "stderr": "invocation_not_requested",
            "timed_out": False,
            "structured_output_requested": True,
            "format_schema_sent": False,
            "structured_output_enforced": False,
            "structured_output_unavailable_reason": "invocation_not_requested",
        }
    elif not all_gates_ready:
        invocation_result = {
            "attempted": False,
            "started_at": "",
            "completed_at": "",
            "runtime_ref": RUNTIME_REF,
            "model_name": MODEL_NAME,
            "method": STRUCTURED_OUTPUT_METHOD,
            "returncode": None,
            "http_status": None,
            "stdout": "",
            "stderr": "precondition_or_room_gate_failed",
            "timed_out": False,
            "structured_output_requested": True,
            "format_schema_sent": False,
            "structured_output_enforced": False,
            "structured_output_unavailable_reason": "precondition_or_room_gate_failed",
        }
    else:
        invocation_result = dict((invoker or invoke_ollama_structured_once)(prompt, schema))

    structured_output_enforced = (
        invocation_result.get("attempted") is True
        and invocation_result.get("method") == STRUCTURED_OUTPUT_METHOD
        and invocation_result.get("structured_output_requested") is True
        and invocation_result.get("format_schema_sent") is True
        and invocation_result.get("structured_output_enforced") is True
    )
    structured_output_unavailable_reason = str(invocation_result.get("structured_output_unavailable_reason") or "")
    pipeline_steps = [
        "structured_retry_approval_unused_confirmed",
        "room_backed_package_built",
        "project_room_checked",
        "source_inventory_checked",
        "freshness_gate_checked",
        "conflict_gate_checked",
        "missing_context_gate_checked",
        "duplicate_version_gate_checked",
        "forbidden_fields_checked",
        "json_only_prompt_built",
        "structured_output_enforcement_used" if structured_output_enforced else "structured_output_enforcement_unavailable",
        "ollama_invoked_once" if invocation_result.get("attempted") is True else "ollama_not_invoked",
        "raw_draft_captured",
        "schema_adapter_ran",
        "verifier_ran",
        "publish_or_fallback_selected",
        "receipts_recorded",
        "approval_marked_used",
        "stopped",
    ]
    adapter_result = schema_adapter.adapt_model_draft(
        str(invocation_result.get("stdout") or ""),
        proof_bundle=verifier_bundle,
        read_model_root=read_model_root,
        generated_at=generated_at,
    )
    verifier_result, published_response, fallback_reason = publish_from_adapter(
        adapter_result,
        verifier_bundle,
        generated_at=generated_at,
    )
    if not structured_output_enforced:
        fallback_reason = structured_output_unavailable_reason or fallback_reason or "structured_output_enforcement_unavailable"
    receipts = build_receipts(
        package=package,
        room_gate=room_gate,
        freshness_gate=freshness_gate,
        invocation_result=invocation_result,
        adapter_result=adapter_result,
        verifier_result=verifier_result,
        published_response=published_response,
        fallback_reason=fallback_reason,
        structured_output_enforced=structured_output_enforced,
        structured_output_unavailable_reason=structured_output_unavailable_reason,
        generated_at=generated_at,
    )
    sqlite_count = write_sqlite(receipts, sqlite_path=sqlite_path)
    latest = build_latest_read_model(published_response, receipts, generated_at=generated_at)
    receipt_refs = {str(row.get("receipt_ref")) for row in receipts}
    required_receipts_present = set(REQUIRED_RECEIPT_REFS) <= receipt_refs and (
        "published_response_hash_receipt" in receipt_refs or "fallback_receipt" in receipt_refs
    )
    attempt_count = 1 if invocation_result.get("attempted") is True else 0
    approval_used = attempt_count == 1
    status_ready = (
        all_gates_ready
        and attempt_count == 1
        and structured_output_enforced
        and sqlite_count == len(receipts)
        and required_receipts_present
        and latest.get("status") == runtime.READY_STATUS
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if status_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Run one approved room-backed LM2 structured-output retry for Finance / Capital Hilton payment-watch proof-to-response.",
        "operator_decision": "approve_one_time_room_backed_lm2_structured_output_retry",
        "approval_usage": {
            "approval_required": True,
            "approval_ref": "generated/read_models/lm2_structured_output_retry_operator_approval.json",
            "approval_matched": approval_matched,
            "approval_unused_before_run": unused_before,
            "approval_used": approval_used,
            "approval_used_at": generated_at if approval_used else "",
            "approval_consumed_by": READ_MODEL_ID if approval_used else "",
        },
        "pilot_scope": {
            "attempt_limit": 1,
            "attempt_count": attempt_count,
            "approved_for_one_future_attempt_only": True,
            "structured_output_required": True,
            "schema_adapter_required": True,
            "verifier_required": True,
            "fallback_required": True,
            "repeated_invocations_allowed": False,
            "worker_class": WORKER_CLASS,
            "runtime_ref": RUNTIME_REF,
            "model_ref": MODEL_REF,
            "model_name": MODEL_NAME,
            "lane": PILOT_LANE,
            "world_ref": WORLD_REF,
            "thread_ref": THREAD_REF,
            "objective": OBJECTIVE_REF,
            "question": QUESTION,
            "mode": MODE,
            "package_type": PACKAGE_TYPE,
        },
        "preconditions": preconditions,
        "room_backed_package_summary": {
            "package_ref": package.get("package_ref"),
            "package_hash": _content_hash(package),
            "project_room_id": package.get("project_room_id"),
            "source_inventory_ref": package.get("source_inventory_ref"),
            "conflict_log_ref": package.get("conflict_log_ref"),
            "missing_context_ref": package.get("missing_context_ref"),
            "duplicate_report_ref": package.get("duplicate_report_ref"),
            "decision_trace_ref": package.get("decision_trace_ref"),
            "freshness_gate_ref": package.get("freshness_gate_ref"),
            "compaction_policy_ref": package.get("compaction_policy_ref"),
            "redacted_proof_bundle_ref": package.get("redacted_proof_bundle_ref"),
            "package_matches_scope": package_ready,
            "room_backed_package_required": package.get("room_backed_package_required") is True,
        },
        "project_room_gate": room_gate,
        "redacted_proof_bundle_summary": {
            "proof_bundle_id": redacted_bundle.get("proof_bundle_id"),
            "proof_bundle_hash": _content_hash(redacted_bundle),
            "lm_visible_package_hash": _content_hash(lm_package),
            **freshness_gate,
        },
        "forbidden_fields_absent": freshness_gate["forbidden_fields_absent"],
        "structured_output_boundary": {
            "method": invocation_result.get("method"),
            "json_schema_format_required": True,
            "strict_json_schema_hash": _content_hash(schema),
            "structured_output_requested": invocation_result.get("structured_output_requested") is True,
            "format_schema_sent": invocation_result.get("format_schema_sent") is True,
            "temperature": invocation_result.get("temperature"),
            "structured_output_enforced": structured_output_enforced,
            "structured_output_unavailable_reason": structured_output_unavailable_reason,
            "plain_text_prompt_fallback_used": False,
        },
        "prompt_hash": _content_hash(prompt),
        "invocation_attempt": {
            "attempt_number": attempt_count,
            "runtime_ref": invocation_result.get("runtime_ref"),
            "model_name": invocation_result.get("model_name"),
            "method": invocation_result.get("method"),
            "attempted": invocation_result.get("attempted") is True,
            "returncode": invocation_result.get("returncode"),
            "http_status": invocation_result.get("http_status"),
            "timed_out": invocation_result.get("timed_out") is True,
            "stdout_hash": _content_hash(str(invocation_result.get("stdout") or "")),
            "stderr_hash": _content_hash(str(invocation_result.get("stderr") or "")),
        },
        "raw_draft_captured": invocation_result.get("attempted") is True,
        "schema_adapter_result": {
            "parse_status": adapter_result.get("parse_status"),
            "adapter_errors": list(adapter_result.get("adapter_errors") or []),
            "verifier_ready": adapter_result.get("verifier_ready") is True,
            "verifier_failure_reasons": list(adapter_result.get("verifier_failure_reasons") or []),
            "adapted_candidate": adapter_result.get("adapted_candidate") or {},
        },
        "verifier_result": verifier_result,
        "publication_decision": "verified_text_published" if adapter_result.get("verifier_ready") is True else "safe_fallback_published",
        "fallback_reason": fallback_reason,
        "published_response": published_response,
        "proof_to_response_latest": latest,
        "pipeline_steps": pipeline_steps,
        "receipts": receipts,
        "required_receipts_present": required_receipts_present,
        "sqlite_ref": _rooted(sqlite_path).as_posix(),
        "sqlite_row_count": sqlite_count,
        "sqlite_expected_row_count": len(receipts),
        "source_refs": [row["source_ref"] for row in preconditions],
        "protected_actions_not_authorized": list(PROTECTED_ACTIONS_NOT_AUTHORIZED),
        "authority_boundary": {
            "protected_actions_allowed": False,
            "authority_granted": False,
            "authority_grant_allowed": False,
            "repeated_invocations_allowed": False,
            "external_provider_allowed": False,
            "tool_authority": False,
            "tool_authority_allowed": False,
            "tool_execution_allowed": False,
            "business_action_authority": False,
            "business_action_allowed": False,
            "browser_access_allowed": False,
            "gmail_allowed": False,
            "coupa_allowed": False,
            "email_send_allowed": False,
            "portal_submit_allowed": False,
            "ledger_mutation_allowed": False,
            "workbook_mutation_allowed": False,
            "pdf_export_allowed": False,
            "paid_marking_allowed": False,
            "memory_promotion_allowed": False,
            "additional_worker_spawning_allowed": False,
            "lm2_shell_commands_allowed": False,
            "lm2_file_system_mutation_allowed": False,
            "git_push_allowed": False,
            "git_merge_allowed": False,
            "raw_finance_private_proof_allowed": False,
            "operator_device_session_secrets_allowed": False,
            "stale_source_current_truth_allowed": False,
            "duplicate_versions_equal_evidence_allowed": False,
            "missing_context_invention_allowed": False,
        },
        "implementation_boundary": {
            "local_ollama_invocation_attempted": invocation_result.get("attempted") is True,
            "prompt_sent_to_local_ollama": invocation_result.get("attempted") is True,
            "redacted_room_backed_package_sent_to_local_ollama": invocation_result.get("attempted") is True,
            "logical_worker_started": invocation_result.get("attempted") is True,
            "logical_worker_stopped": True,
            **action_flags(),
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["unsafe_true_grants"] = unsafe
    payload["machine_proof"] = {
        "exactly_one_worker_attempt": attempt_count == 1,
        "structured_output_retry_approval_required_and_marked_used": payload["approval_usage"]["approval_required"] is True
        and payload["approval_usage"]["approval_used"] is True,
        "runtime_model_match_approval": approval_matched,
        "room_backed_package_required": package.get("room_backed_package_required") is True,
        "project_room_readiness_checked": room_gate["project_room_ready"] is True,
        "freshness_gate_checked": freshness_gate["freshness_gate_checked"] is True and freshness_gate["freshness_allowed"] is True,
        "forbidden_fields_absent": freshness_gate["forbidden_fields_absent"] is True,
        "external_provider_unused": payload["implementation_boundary"]["external_provider_used"] is False,
        "tool_authority_false": payload["authority_boundary"]["tool_authority"] is False,
        "business_action_flags_false": not any(action_flags().values())
        and payload["implementation_boundary"]["business_action_performed"] is False,
        "structured_output_boundary_receipt_recorded": "structured_output_boundary_receipt" in receipt_refs,
        "structured_output_enforced": structured_output_enforced,
        "schema_adapter_runs_before_verifier": pipeline_steps.index("schema_adapter_ran") < pipeline_steps.index("verifier_ran"),
        "verifier_gates_publication": True,
        "fallback_available": True,
        "sqlite_receipts_recorded": sqlite_count == len(receipts),
        "required_receipts_present": required_receipts_present,
        "unsafe_true_grants_absent": not unsafe,
    }
    if unsafe or not status_ready:
        payload["status"] = NOT_READY_STATUS
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    scope = read_model.get("pilot_scope") if isinstance(read_model.get("pilot_scope"), Mapping) else {}
    response = read_model.get("published_response") if isinstance(read_model.get("published_response"), Mapping) else {}
    invocation = read_model.get("invocation_attempt") if isinstance(read_model.get("invocation_attempt"), Mapping) else {}
    approval = read_model.get("approval_usage") if isinstance(read_model.get("approval_usage"), Mapping) else {}
    structured = read_model.get("structured_output_boundary") if isinstance(read_model.get("structured_output_boundary"), Mapping) else {}
    lines = [
        "# LM2 Room Backed Worker Structured Output Retry",
        "",
        f"Status: `{read_model.get('status')}`",
        "",
        "This records one approved room-backed LM2 structured-output retry for Finance / Capital Hilton.",
        "",
        "## Scope",
        "",
        f"- Worker class: `{scope.get('worker_class')}`",
        f"- Runtime: `{scope.get('runtime_ref')}`",
        f"- Model: `{scope.get('model_name')}`",
        f"- Lane: `{scope.get('lane')}`",
        f"- Question: {scope.get('question')}",
        f"- Attempt count: `{scope.get('attempt_count')}`",
        f"- Approval used: `{str(approval.get('approval_used')).lower()}`",
        "",
        "## Structured Output",
        "",
        f"- Method: `{structured.get('method')}`",
        f"- Format schema sent: `{str(structured.get('format_schema_sent')).lower()}`",
        f"- Enforced: `{str(structured.get('structured_output_enforced')).lower()}`",
        f"- Unavailable reason: `{structured.get('structured_output_unavailable_reason')}`",
        "",
        "## Invocation",
        "",
        f"- Attempted: `{str(invocation.get('attempted')).lower()}`",
        f"- Return code: `{invocation.get('returncode')}`",
        f"- HTTP status: `{invocation.get('http_status')}`",
        f"- Timed out: `{str(invocation.get('timed_out')).lower()}`",
        f"- Publication: `{read_model.get('publication_decision')}`",
        "",
        "## Published Response",
        "",
        f"- Headline: {response.get('headline')}",
        f"- Body: {response.get('body')}",
        f"- Next step: {response.get('next_step')}",
        "",
        "## Receipts",
        "",
    ]
    for receipt in read_model.get("receipts") or []:
        lines.append(f"- `{receipt.get('receipt_ref')}`: {receipt.get('receipt_status')}")
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- No external provider.",
            "- No model tool authority.",
            "- No browser, Gmail, Coupa, email send, submit, ledger mutation, workbook mutation, PDF export, paid marking, memory promotion, push, or merge.",
            "- Raw finance/private proof and operator/device/session secrets were not sent.",
            "- No plain-text prompt fallback is allowed when structured output enforcement is unavailable.",
            "",
        ]
    )
    return "\n".join(lines)


def export_structured_output_retry(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
    invoker: ModelInvoker | None = None,
    invoke_model: bool = False,
) -> dict[str, str]:
    read_model = run_structured_output_retry(
        read_model_root=read_model_root,
        generated_at=generated_at,
        invoker=invoker,
        invoke_model=invoke_model,
        sqlite_path=sqlite_path,
    )
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    latest_path = export_root / runtime.LATEST_JSON_EXPORT_NAME
    _write_json(read_model_path, read_model)
    _write_json(latest_path, read_model["proof_to_response_latest"])

    bridge_read_model_path = ""
    bridge_latest_path = ""
    if bridge_root is not None:
        bridge_root = _rooted(bridge_root)
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_read_model = bridge_root / JSON_EXPORT_NAME
        bridge_latest = bridge_root / runtime.LATEST_JSON_EXPORT_NAME
        shutil.copy2(read_model_path, bridge_read_model)
        shutil.copy2(latest_path, bridge_latest)
        bridge_read_model_path = bridge_read_model.as_posix()
        bridge_latest_path = bridge_latest.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model.get("status") or NOT_READY_STATUS),
        "publication_decision": str(read_model.get("publication_decision") or ""),
        "attempt_count": str((read_model.get("pilot_scope") or {}).get("attempt_count") or 0),
        "approval_used": str((read_model.get("approval_usage") or {}).get("approval_used") is True).lower(),
        "structured_output_enforced": str((read_model.get("structured_output_boundary") or {}).get("structured_output_enforced") is True).lower(),
        "read_model_path": read_model_path.as_posix(),
        "latest_path": latest_path.as_posix(),
        "bridge_read_model_path": bridge_read_model_path,
        "bridge_latest_path": bridge_latest_path,
        "wiki_path": wiki_path.as_posix(),
        "sqlite_path": _rooted(sqlite_path).as_posix(),
        "sqlite_row_count": str(read_model.get("sqlite_row_count") or 0),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the one-time room-backed LM2 structured-output retry.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--invoke-approved-model", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    bridge_root = Path(args.bridge_root) if args.bridge_root else None
    result = export_structured_output_retry(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=bridge_root,
        wiki_path=Path(args.wiki_path),
        sqlite_path=Path(args.sqlite_path),
        generated_at=args.generated_at,
        invoke_model=args.invoke_approved_model,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
