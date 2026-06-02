"""Mission Control workflow package request consumer V0.

This adapter consumes ``WORKFLOW_PACKAGE_REQUEST_V0`` operator-instruction
envelopes and records a dry-run package in the Workflow Package Queue V0.
It does not execute workers beyond the queue's no-op result, mutate business
state, touch workbooks, export PDFs, send email, open browser/Gmail/Coupa, post
ledger entries, submit portals, or mark paid/sent.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import workflow_package_queue


REQUEST_TYPE = "WORKFLOW_PACKAGE_REQUEST_V0"
REQUEST_KIND = "OPERATOR_INSTRUCTION_PACKAGE_REQUEST"
REQUEST_FILENAME_PATTERNS = (
    "mission_control_operator_instruction_request_*.json",
    "mission_control_workflow_package_request_*.json",
)
DEFAULT_SQLITE_PATH = workflow_package_queue.DEFAULT_SQLITE_PATH
SQLITE_PATH_ENV = "OPENCLAW_WORKFLOW_PACKAGE_QUEUE_SQLITE_PATH"

AUTHORITY_FALSE_FIELDS = (
    "email_send_allowed",
    "ledger_posting_allowed",
    "browser_access_allowed",
    "gmail_allowed",
    "coupa_allowed",
    "portal_submit_allowed",
    "sent",
    "paid",
    "coupa_submit_allowed",
    "gmail_access_allowed",
    "coupa_access_allowed",
    "browser_automation_allowed",
    "workbook_mutation_allowed",
    "workbook_open_allowed",
    "workbook_source_mutation_allowed",
    "excel_automation_allowed",
    "pdf_export_allowed",
    "email_draft_allowed",
    "ledger_mutation_allowed",
    "payment_marking_allowed",
    "business_action_allowed",
    "external_action_allowed",
    "model_call_allowed",
    "agent_activation_allowed",
    "tool_execution_allowed",
    "runtime_dispatch_allowed",
    "raw_body_ingestion_allowed",
)

TOP_LEVEL_FALSE_FIELDS = (
    "email_send_performed",
    "ledger_mutation_performed",
    "browser_access_performed",
    "browser_or_coupa_open_performed",
    "gmail_access_performed",
    "coupa_access_performed",
    "coupa_submit_performed",
    "submit_performed",
    "workbook_mutation_performed",
    "excel_automation_performed",
    "pdf_export_performed",
    "paid_marking_performed",
    "business_action_performed",
)

BLOCKING_PACKAGE_STATUSES = {
    "PERMISSION_REQUIRED",
    "ARTIFACT_REQUIRED",
    "PROVIDER_GATE_REQUIRED",
}


@dataclass(frozen=True)
class WorkflowPackageRequestResult:
    status: str
    request_id: str
    request_filename: str
    package: dict[str, Any] | None
    blockers: tuple[str, ...]
    response_primary_status: str
    next_safe_action: str
    receipt: dict[str, Any]


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_sqlite_path() -> Path:
    configured = os.environ.get(SQLITE_PATH_ENV)
    return Path(configured) if configured else DEFAULT_SQLITE_PATH


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_workflow_package_request(raw_request: Mapping[str, Any]) -> bool:
    return (
        str(raw_request.get("request_type") or raw_request.get("envelope_type") or "").strip().upper()
        == REQUEST_TYPE
    ) or str(raw_request.get("kind") or "").strip().upper() == REQUEST_KIND


def _request_id(raw_request: Mapping[str, Any], filename: str) -> str:
    return str(
        raw_request.get("request_id")
        or raw_request.get("source_request_id")
        or f"workflow_package_request:{filename}"
    )


def _source_text(raw_request: Mapping[str, Any]) -> str:
    for key in ("source_text", "operator_message", "sanitized_message_summary", "operator_goal", "message", "text"):
        value = str(raw_request.get(key) or "").strip()
        if value:
            return value
    return ""


def _authority_blockers(raw_request: Mapping[str, Any]) -> tuple[str, ...]:
    blockers: list[str] = []
    authority = raw_request.get("authority_boundary")
    if not isinstance(authority, Mapping):
        blockers.append("authority_boundary_missing_or_invalid")
    else:
        for key, value in authority.items():
            if value is True:
                blockers.append(f"authority_true:{key}")
        for key in AUTHORITY_FALSE_FIELDS:
            if authority.get(key) is True:
                blockers.append(f"unsafe_authority_true:{key}")
    for key in TOP_LEVEL_FALSE_FIELDS:
        if raw_request.get(key) is True:
            blockers.append(f"unsafe_action_performed_true:{key}")
    return tuple(dict.fromkeys(blockers))


def validate_envelope(raw_request: Mapping[str, Any], *, source_request_filename: str = "") -> tuple[bool, tuple[str, ...]]:
    blockers: list[str] = []
    if not is_workflow_package_request(raw_request):
        blockers.append("not_workflow_package_request_v0")
    if str(raw_request.get("source_surface") or "").strip() != "mission_control":
        blockers.append("source_surface_not_mission_control")
    if str(raw_request.get("requested_mode") or "").strip() != "operator":
        blockers.append("requested_mode_not_operator")
    if raw_request.get("result_receipt_required") is not True:
        blockers.append("result_receipt_required_not_true")
    if not _source_text(raw_request):
        blockers.append("source_text_missing")
    blockers.extend(_authority_blockers(raw_request))

    expected_hash = workflow_package_queue.protected_text_hash(_source_text(raw_request)) if _source_text(raw_request) else ""
    provided_hash = str(raw_request.get("protected_text_hash") or "").strip()
    source_text_ref = str(raw_request.get("source_text_ref") or "").strip()
    if provided_hash and expected_hash and provided_hash != expected_hash:
        blockers.append("protected_text_hash_mismatch")
    if source_text_ref and expected_hash and not source_text_ref.endswith(expected_hash):
        blockers.append("source_text_ref_hash_mismatch")

    return not blockers, tuple(dict.fromkeys(blockers))


def _next_safe_action(package: Mapping[str, Any] | None, blockers: tuple[str, ...]) -> str:
    if package is None:
        return "Fix the safe Mission Control operator-instruction envelope and resend it."
    status = str(package.get("status") or "")
    workflow_ref = str(package.get("workflow_ref") or "")
    if status == "PROVIDER_GATE_REQUIRED":
        return "Stage the operator-assist provider and final Submit gate; no Coupa or email action ran."
    if status == "PERMISSION_REQUIRED":
        return "Stage permission and artifact prerequisites; no send, workbook, PDF, or ledger action ran."
    if status == "ARTIFACT_REQUIRED":
        return "Attach or approve the required artifact before operator review; no send action ran."
    if workflow_ref == "capital_hilton_proposal_followup":
        return "Review the staged Business Development follow-up package; V0 does not send email."
    if workflow_ref == "st_annes_work_log_event":
        return "Review the staged work-log package; invoice inclusion still requires separate operator confirmation."
    return "Review the staged dry-run package; the business action gate remains closed."


def _primary_status(package: Mapping[str, Any] | None, blockers: tuple[str, ...]) -> str:
    if package is None:
        return "BLOCKED_BY_ENVELOPE_VALIDATION"
    return str(package.get("status") or "UNKNOWN_FAIL_CLOSED")


def _blocker(package: Mapping[str, Any] | None, blockers: tuple[str, ...]) -> str:
    if blockers:
        return "; ".join(blockers)
    if package is None:
        return "package_not_created"
    if str(package.get("status") or "") in BLOCKING_PACKAGE_STATUSES:
        capability = package.get("capability_gate_result")
        if isinstance(capability, Mapping):
            return str(capability.get("reason") or capability.get("status") or package["status"])
    return ""


def consume_workflow_package_request(
    raw_request: Mapping[str, Any],
    *,
    source_request_filename: str = "",
    generated_at: str | None = None,
    sqlite_path: Path | None = None,
) -> WorkflowPackageRequestResult:
    generated_at = generated_at or utc_now()
    sqlite_path = sqlite_path or default_sqlite_path()
    request_id = _request_id(raw_request, source_request_filename)
    ok, blockers = validate_envelope(raw_request, source_request_filename=source_request_filename)
    package: dict[str, Any] | None = None
    if ok:
        package_created_at = str(raw_request.get("created_at") or generated_at)
        package = workflow_package_queue.create_package(
            _source_text(raw_request),
            source_surface="mission_control",
            created_at=package_created_at,
        )
        package["source_request_metadata"] = {
            "request_id": request_id,
            "source_request_filename": source_request_filename,
            "world_ref": str(raw_request.get("world_ref") or raw_request.get("world") or ""),
            "thread_ref": str(raw_request.get("thread_ref") or ""),
            "source_text_ref": str(raw_request.get("source_text_ref") or ""),
            "protected_text_hash": str(raw_request.get("protected_text_hash") or ""),
            "idempotency_key": str(raw_request.get("idempotency_key") or ""),
            "payload_hash": str(raw_request.get("payload_hash") or ""),
        }
        workflow_package_queue.record_package(sqlite_path, package)

    primary_status = _primary_status(package, blockers)
    blocker = _blocker(package, blockers)
    next_safe_action = _next_safe_action(package, blockers)
    receipt = {
        "schema_version": "workflow_package_request_consumer_v0",
        "receipt_type": "WORKFLOW_PACKAGE_REQUEST_RESULT_RECEIPT",
        "request_id": request_id,
        "source_request_filename": source_request_filename,
        "raw_internal_status": "RESPONSE_READY" if package is not None else "BLOCKED_WITH_REASON",
        "primary_status": primary_status,
        "package_id": package.get("package_id") if package else "",
        "workflow_ref": package.get("workflow_ref") if package else "",
        "client_ref": package.get("client_ref") if package else None,
        "world": package.get("world") if package else str(raw_request.get("world_ref") or raw_request.get("world") or ""),
        "package_status": package.get("status") if package else "NOT_CREATED",
        "capability_gate_status": (
            (package.get("capability_gate_result") or {}).get("status")
            if package
            else "NOT_EVALUATED"
        ),
        "blocker": blocker,
        "next_safe_action": next_safe_action,
        "authority_boundary": dict(workflow_package_queue.AUTHORITY_BOUNDARY_DEFAULT),
        "request_authority_boundary_all_false": not _authority_blockers(raw_request),
        "no_external_authority_granted": True,
        "result_receipt_required": raw_request.get("result_receipt_required") is True,
        "sqlite_path": str(sqlite_path),
        "created_at": generated_at,
        "machine_proof": {
            "workflow_package_request_v0_detected": is_workflow_package_request(raw_request),
            "source_surface_mission_control": str(raw_request.get("source_surface") or "") == "mission_control",
            "requested_mode_operator": str(raw_request.get("requested_mode") or "") == "operator",
            "package_recorded": package is not None,
            "queue_noop_worker_only": True,
            "business_action_gate_closed": bool(
                package and (package.get("business_action_gate_result") or {}).get("status") == "CLOSED"
            ),
            "authority_flags_all_false": all(
                value is False for value in workflow_package_queue.AUTHORITY_BOUNDARY_DEFAULT.values()
            ),
            "email_send_performed": False,
            "ledger_mutation_performed": False,
            "browser_access_performed": False,
            "gmail_access_performed": False,
            "coupa_access_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "business_state_mutation_performed": False,
            "raw_text_stored_in_sqlite": False,
            "unsafe_true_grants_absent": not _authority_blockers(raw_request),
        },
    }
    return WorkflowPackageRequestResult(
        status="RECORDED" if package is not None else "BLOCKED",
        request_id=request_id,
        request_filename=source_request_filename,
        package=package,
        blockers=blockers,
        response_primary_status=primary_status,
        next_safe_action=next_safe_action,
        receipt=receipt,
    )
