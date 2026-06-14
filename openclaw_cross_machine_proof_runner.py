"""OpenClaw Cross-Machine Proof Runner v0.

Deterministic PC-coordinated proof runner for scoped Mac<->PC smoke tests.
The runner writes an allowlisted Mac-local proof job, waits for a Mac result
and the existing request-response service's scoped response, then records a
proof receipt/read-model. It does not call an LM, launch Chief, start services,
read workbook cells, export PDFs, send mail, browse, post ledgers, print, or
perform business workflow execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import openclaw_event_bridge_contract as event_contract


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_SYSTEM_KNOWLEDGE_ROOT = Path("generated/system_knowledge")
DEFAULT_PC_BRIDGE_ROOT = Path("/mnt/e/openclaw")
DEFAULT_MAC_BRIDGE_ROOT = "/Volumes/openclaw_e"

SCHEMA_VERSION = "openclaw_cross_machine_proof_runner_v0"
READ_MODEL_VERSION = "openclaw_cross_machine_proof_runner_read_model_v0"
READ_MODEL_ID = "openclaw_cross_machine_proof_runner"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
SQLITE_EXPORT_NAME = f"{READ_MODEL_ID}.sqlite"
SCHEMA_EXPORT_NAME = f"{READ_MODEL_ID}_SCHEMA.sql"
SEED_EXPORT_NAME = f"{READ_MODEL_ID}_SEED.sql"
MAC_WORK_PACKAGE_NAME = f"{READ_MODEL_ID}_MAC_WORK_PACKAGE.md"

SUPPORTED_PROOFS = ("event_bridge_live_arts_prepare_pdf",)
SUPPORTED_MAC_JOB_KINDS = ("EMIT_EVENT_BRIDGE_ENVELOPE",)

PROOF_STATUSES = (
    "PASS",
    "FAIL",
    "TIMEOUT",
    "MAC_WORKER_MISSING",
    "MAC_JOB_NOT_ACKED",
    "EVENT_NOT_EMITTED",
    "RESPONSE_NOT_FOUND",
    "ROUTE_REJECTED",
    "BOUNDARY_VIOLATION",
    "UNKNOWN",
)

REQUIRED_SQLITE_TABLES = (
    "proof_run",
    "proof_step",
    "proof_artifact",
    "proof_result",
    "proof_failure",
    "proof_boundary_check",
)

NO_AUTHORITY_FLAGS = {
    "metadata_only": True,
    "deterministic_proof_only": True,
    "bridge_job_written": True,
    "lm_called": False,
    "chief_launched": False,
    "services_started": False,
    "timers_installed": False,
    "business_workflow_executed": False,
    "handler_execution_allowed": False,
    "email_accessed": False,
    "email_sent": False,
    "gmail_accessed": False,
    "browser_accessed": False,
    "coupa_accessed": False,
    "workbook_cells_read": False,
    "excel_used": False,
    "pdf_generated_or_exported": False,
    "ledger_mutated": False,
    "physical_printing_performed": False,
    "production_state_mutated": False,
}

MAC_JOB_SAFETY_FLAGS = {
    "no_pdf_export": True,
    "no_excel": True,
    "no_email": True,
    "no_gmail": True,
    "no_browser": True,
    "no_ledger": True,
    "no_coupa": True,
    "no_workbook_cell_read": True,
    "no_physical_printing": True,
    "no_business_workflow_execution": True,
}

EVENT_REQUIRED_TRUE_FLAGS = (
    "no_email_send",
    "no_gmail",
    "no_browser",
    "no_ledger_post",
    "no_coupa",
    "no_workbook_cell_read",
    "no_physical_printing",
)

MACHINE_PROOF_FORBIDDEN_TRUE_KEYS = (
    "handler_execution_performed",
    "processor_execution_performed",
    "service_started",
    "telegram_runtime_started",
    "model_call_performed",
    "email_send_performed",
    "gmail_access_performed",
    "browser_access_performed",
    "coupa_access_performed",
    "ledger_post_performed",
    "workbook_cell_read_performed",
    "pdf_export_performed",
    "business_workflow_executed",
    "production_state_mutation_performed",
    "physical_printing_performed",
)

EXPECTED_ROUTE = {
    "route_status": "ROUTE_MATCHED",
    "workflow_status": "WORKFLOW_ACTION_ROUTED",
    "selected_handler_id": "invoice_review_action_request.live_arts_md",
}


@dataclass(frozen=True)
class CrossMachineProofExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    sqlite_path: str
    schema_sql_path: str
    seed_sql_path: str
    mac_work_package_path: str
    proof_ref: str
    proof_run_id: str
    status: str
    mac_worker_exists: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _rooted(path: str | Path, *, root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(root) / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _safe_filename_part(value: object) -> str:
    text = str(value)
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("._")
    if cleaned:
        return cleaned[:160]
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def _short_hash(*parts: object) -> str:
    digest = hashlib.sha256(stable_json(parts).encode("utf-8")).hexdigest()
    return digest[:20]


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _plus_minutes(value: str, minutes: int) -> str:
    parsed = _parse_datetime(value) or datetime.now(timezone.utc)
    return (parsed + timedelta(minutes=minutes)).replace(microsecond=0).isoformat()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _require_status(status: str) -> str:
    if status not in PROOF_STATUSES:
        raise ValueError(f"unknown cross-machine proof status: {status}")
    return status


def _relative_bridge_path(path: Path, *, pc_bridge_root: Path) -> str:
    try:
        return path.resolve().relative_to(pc_bridge_root.resolve()).as_posix()
    except (OSError, ValueError):
        return path.as_posix()


def _mac_path_for_pc_path(path: Path, *, pc_bridge_root: Path, mac_bridge_root: str) -> str:
    relative = _relative_bridge_path(path, pc_bridge_root=pc_bridge_root)
    return str(Path(mac_bridge_root) / relative)


def _proof_definition(proof_ref: str) -> dict[str, Any]:
    if proof_ref != "event_bridge_live_arts_prepare_pdf":
        raise ValueError(f"unsupported proof: {proof_ref}")
    return {
        "proof_ref": proof_ref,
        "expected_event_kind": "WORKFLOW_ACTION_REQUEST",
        "expected_source_channel": "MAC_APP",
        "client_ref": "live_arts_md",
        "workflow_ref": "live_arts_md_invoice_workflow",
        "world_ref": "finance",
        "thread_ref": "live_arts_md_invoice_workflow:2026-1001",
        "actor_ref": "operator:winship",
        "action_kind": "prepare_selected_invoice_pdf_artifact",
        "expected_route": dict(EXPECTED_ROUTE),
        "job_kind": "EMIT_EVENT_BRIDGE_ENVELOPE",
    }


def _event_payload(*, correlation_id: str, event_id: str) -> dict[str, Any]:
    return {
        "request_type": "INVOICE_REVIEW_ACTION_REQUEST",
        "action_kind": "prepare_selected_invoice_pdf_artifact",
        "intended_use": "prepare_selected_invoice_pdf_artifact",
        "button_ref": "live_arts_md.prepare_selected_invoice_pdf_artifact",
        "workflow_payload_shape_ref": event_contract.WORKFLOW_PAYLOAD_SHAPE_REF,
        "invoice_id": "2026-1001",
        "selected_sheet_label": "June 2026 Speaker Rental",
        "selected_print_areas": ["A1:H42"],
        "operator_copy": "Route the scoped Live Arts MD Prepare invoice PDF action without executing export.",
        "source_event_id": event_id,
        "correlation_id": correlation_id,
        "no_email_send": True,
        "no_gmail": True,
        "no_browser": True,
        "no_ledger_post": True,
        "no_coupa": True,
        "no_workbook_cell_read": True,
        "no_physical_printing": True,
    }


def build_proof_context(
    *,
    proof_ref: str,
    generated_at: str | None = None,
    pc_bridge_root: str | Path = DEFAULT_PC_BRIDGE_ROOT,
    mac_bridge_root: str = DEFAULT_MAC_BRIDGE_ROOT,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    pc_root = Path(pc_bridge_root)
    definition = _proof_definition(proof_ref)
    run_hash = _short_hash(proof_ref, generated, pc_root.as_posix(), mac_bridge_root)
    proof_run_id = f"proof_run_{proof_ref}_{run_hash}"
    correlation_id = f"correlation:cross_machine_proof:{run_hash}"
    event_id = f"openclaw_event_bridge_{proof_ref}_{run_hash}"
    job_id = f"mac_job_{proof_ref}_{run_hash}"
    result_filename = f"{_safe_filename_part(job_id)}.json"
    event_filename = f"{_safe_filename_part(event_id)}.json"
    event_path = pc_root / "mission_control_capture_requests" / "inbox" / event_filename
    response_path = (
        pc_root
        / "mission_control_responses"
        / "to_mac"
        / f"openclaw_response_for_mac_{_safe_filename_part(event_id)}.json"
    )
    mac_job_path = pc_root / "mac_local_jobs" / "inbox" / result_filename
    mac_result_path = pc_root / "mac_local_jobs" / "results" / result_filename
    worker_manifest_path = pc_root / "mac_local_jobs" / "worker_manifest.json"
    event_payload = _event_payload(correlation_id=correlation_id, event_id=event_id)
    event_envelope = event_contract.make_event_envelope(
        event_kind=definition["expected_event_kind"],
        source_channel=definition["expected_source_channel"],
        client_ref=definition["client_ref"],
        workflow_ref=definition["workflow_ref"],
        world_ref=definition["world_ref"],
        thread_ref=definition["thread_ref"],
        actor_ref=definition["actor_ref"],
        payload=event_payload,
        event_id=event_id,
        idempotency_key=f"idempotency:cross_machine_proof:{run_hash}",
        correlation_id=correlation_id,
        parent_event_id="cross_machine_proof_runner",
        created_at=generated,
        expires_at=_plus_minutes(generated, 5),
        expected_response_kind="WORKFLOW_ACTION_RESPONSE",
        result_receipt_required=True,
    )
    job = {
        "schema_version": SCHEMA_VERSION,
        "job_kind": definition["job_kind"],
        "job_id": job_id,
        "proof_ref": proof_ref,
        "proof_run_id": proof_run_id,
        "correlation_id": correlation_id,
        "requested_event_kind": definition["expected_event_kind"],
        "client_ref": definition["client_ref"],
        "workflow_ref": definition["workflow_ref"],
        "action_kind": definition["action_kind"],
        "expected_output_path": _mac_path_for_pc_path(event_path, pc_bridge_root=pc_root, mac_bridge_root=mac_bridge_root),
        "pc_expected_output_path": event_path.as_posix(),
        "expected_result_path": _mac_path_for_pc_path(mac_result_path, pc_bridge_root=pc_root, mac_bridge_root=mac_bridge_root),
        "pc_expected_result_path": mac_result_path.as_posix(),
        "expected_pc_response_path": response_path.as_posix(),
        "safety_flags": dict(MAC_JOB_SAFETY_FLAGS),
        "expires_at": _plus_minutes(generated, 5),
        "no_pdf_export": True,
        "no_excel": True,
        "no_email": True,
        "no_gmail": True,
        "no_browser": True,
        "no_ledger": True,
        "no_coupa": True,
        "no_workbook_cell_read": True,
        "no_physical_printing": True,
        "event_envelope": event_envelope,
    }
    return {
        "definition": definition,
        "generated_at": generated,
        "proof_ref": proof_ref,
        "proof_run_id": proof_run_id,
        "correlation_id": correlation_id,
        "job_id": job_id,
        "event_id": event_id,
        "pc_bridge_root": pc_root.as_posix(),
        "mac_bridge_root": mac_bridge_root,
        "request_path": event_path.as_posix(),
        "response_path": response_path.as_posix(),
        "mac_job_path": mac_job_path.as_posix(),
        "mac_result_path": mac_result_path.as_posix(),
        "mac_visible_job_path": _mac_path_for_pc_path(mac_job_path, pc_bridge_root=pc_root, mac_bridge_root=mac_bridge_root),
        "mac_visible_result_path": _mac_path_for_pc_path(mac_result_path, pc_bridge_root=pc_root, mac_bridge_root=mac_bridge_root),
        "mac_visible_event_path": _mac_path_for_pc_path(event_path, pc_bridge_root=pc_root, mac_bridge_root=mac_bridge_root),
        "worker_manifest_path": worker_manifest_path.as_posix(),
        "event_envelope": event_envelope,
        "mac_job": job,
    }


def _write_mac_job(context: Mapping[str, Any]) -> None:
    _atomic_write_text(Path(str(context["mac_job_path"])), stable_json(context["mac_job"]))


def _mac_worker_status(context: Mapping[str, Any]) -> dict[str, Any]:
    manifest_path = Path(str(context["worker_manifest_path"]))
    manifest = _read_json(manifest_path)
    supported = manifest.get("supported_job_kinds")
    if not isinstance(supported, list):
        supported = []
    exists = bool(manifest)
    job_supported = str(context["mac_job"]["job_kind"]) in {str(item) for item in supported}
    ready = str(manifest.get("status", "")).upper() in {"READY", "ACTIVE", "RUNNING"} if exists else False
    return {
        "manifest_path": manifest_path.as_posix(),
        "mac_visible_manifest_path": _mac_path_for_pc_path(
            manifest_path,
            pc_bridge_root=Path(str(context["pc_bridge_root"])),
            mac_bridge_root=str(context["mac_bridge_root"]),
        ),
        "exists": exists,
        "ready": ready,
        "job_supported": job_supported,
        "status": str(manifest.get("status", "")) if exists else "MISSING",
        "supported_job_kinds": supported,
        "worker_id": str(manifest.get("worker_id", "")) if exists else "",
        "missing_reason": ""
        if exists and ready and job_supported
        else "Mac local proof worker manifest is missing or does not support EMIT_EVENT_BRIDGE_ENVELOPE.",
    }


def _wait_for_file(path: Path, *, timeout_seconds: float, poll_interval_seconds: float) -> bool:
    if path.exists() and path.is_file():
        return True
    if timeout_seconds <= 0:
        return False
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        time.sleep(max(0.05, min(poll_interval_seconds, 5.0)))
        if path.exists() and path.is_file():
            return True
    return path.exists() and path.is_file()


def _boundary_check_row(
    *,
    check_ref: str,
    status: str,
    expected: str,
    actual: str,
    detail: str,
) -> dict[str, Any]:
    return {
        "check_ref": check_ref,
        "status": status,
        "expected": expected,
        "actual": actual,
        "detail": detail,
    }


def _event_boundary_checks(event_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for flag in EVENT_REQUIRED_TRUE_FLAGS:
        actual = event_payload.get(flag)
        rows.append(
            _boundary_check_row(
                check_ref=f"event_guard:{flag}",
                status="PASS" if actual is True else "FAIL",
                expected="true",
                actual=str(actual),
                detail=f"Event envelope guard {flag} must be true.",
            )
        )
    safety = event_payload.get("safety_flags")
    if isinstance(safety, Mapping):
        for flag in ("hot_path_event", "structured_action_required", "operator_receipt_required_before_mutation"):
            actual = safety.get(flag)
            rows.append(
                _boundary_check_row(
                    check_ref=f"event_safety:{flag}",
                    status="PASS" if actual is True else "FAIL",
                    expected="true",
                    actual=str(actual),
                    detail=f"Event safety flag {flag} must be true.",
                )
            )
    return rows


def _mac_result_boundary_checks(result_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    boundary = result_payload.get("boundary_flags")
    if not isinstance(boundary, Mapping):
        return [
            _boundary_check_row(
                check_ref="mac_result_boundary_flags_present",
                status="FAIL",
                expected="boundary_flags object",
                actual=type(boundary).__name__,
                detail="Mac result must declare boundary flags.",
            )
        ]
    rows: list[dict[str, Any]] = []
    for flag, expected in MAC_JOB_SAFETY_FLAGS.items():
        actual = boundary.get(flag)
        rows.append(
            _boundary_check_row(
                check_ref=f"mac_result_boundary:{flag}",
                status="PASS" if actual is expected else "FAIL",
                expected=str(expected),
                actual=str(actual),
                detail=f"Mac result boundary flag {flag} must remain {expected}.",
            )
        )
    return rows


def _response_machine_proof(response_payload: Mapping[str, Any]) -> dict[str, Any]:
    direct = response_payload.get("machine_proof")
    if isinstance(direct, Mapping):
        proof = dict(direct)
    else:
        proof = {}
    adapter = response_payload.get("event_bridge_adapter_response")
    if isinstance(adapter, Mapping):
        adapter_proof = adapter.get("machine_proof")
        if isinstance(adapter_proof, Mapping):
            proof.update({f"adapter_{key}": value for key, value in adapter_proof.items()})
            proof.update({key: value for key, value in adapter_proof.items() if key not in proof})
    return proof


def _response_boundary_checks(response_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    proof = _response_machine_proof(response_payload)
    rows: list[dict[str, Any]] = []
    for key in MACHINE_PROOF_FORBIDDEN_TRUE_KEYS:
        actual = proof.get(key)
        passes = actual in (False, None, "")
        rows.append(
            _boundary_check_row(
                check_ref=f"response_machine_proof:{key}",
                status="PASS" if passes else "FAIL",
                expected="false or absent",
                actual=str(actual),
                detail=f"Response machine proof must not show {key}.",
            )
        )
    return rows


def _response_route_values(response_payload: Mapping[str, Any]) -> dict[str, str]:
    adapter = response_payload.get("event_bridge_adapter_response")
    adapter_map = adapter if isinstance(adapter, Mapping) else {}
    router_decision = adapter_map.get("router_decision")
    router_map = router_decision if isinstance(router_decision, Mapping) else {}
    return {
        "route_status": str(response_payload.get("route_status") or adapter_map.get("route_status") or ""),
        "workflow_status": str(response_payload.get("workflow_status") or adapter_map.get("workflow_status") or ""),
        "selected_handler_id": str(
            response_payload.get("selected_handler_id")
            or router_map.get("selected_handler_id")
            or adapter_map.get("selected_handler_id")
            or ""
        ),
    }


def _failure_row(
    *,
    failure_ref: str,
    failure_status: str,
    reason: str,
    exact_file: str = "",
) -> dict[str, Any]:
    return {
        "failure_ref": failure_ref,
        "failure_status": failure_status,
        "reason": reason,
        "exact_file": exact_file,
    }


def _step_rows(
    *,
    context: Mapping[str, Any],
    status_by_step: Mapping[str, str],
) -> list[dict[str, Any]]:
    step_specs = (
        ("create_proof_run", "Create proof run and correlation id.", ""),
        ("write_mac_job", "Write Mac proof job to bridge.", str(context["mac_job_path"])),
        ("detect_mac_worker", "Check Mac local proof worker manifest.", str(context["worker_manifest_path"])),
        ("wait_for_mac_result", "Wait for Mac proof result.", str(context["mac_result_path"])),
        ("verify_event", "Verify emitted Event Bridge envelope.", str(context["request_path"])),
        ("wait_for_pc_response", "Wait for scoped PC response.", str(context["response_path"])),
        ("verify_route", "Verify route result and selected handler.", str(context["response_path"])),
        ("verify_boundary", "Verify no-authority proof flags.", str(context["response_path"])),
        ("write_receipt", "Write proof receipt/read-model.", ""),
    )
    return [
        {
            "step_ref": step_ref,
            "status": status_by_step.get(step_ref, "PENDING"),
            "summary": summary,
            "path": path,
        }
        for step_ref, summary, path in step_specs
    ]


def _artifact_rows(
    *,
    context: Mapping[str, Any],
    mac_worker: Mapping[str, Any],
    event_payload: Mapping[str, Any] | None,
    result_payload: Mapping[str, Any] | None,
    response_payload: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    artifacts = [
        ("mac_job_request", str(context["mac_job_path"]), Path(str(context["mac_job_path"])).is_file()),
        ("mac_worker_manifest", str(mac_worker["manifest_path"]), bool(mac_worker.get("exists"))),
        ("mac_job_result", str(context["mac_result_path"]), result_payload is not None),
        ("event_bridge_envelope", str(context["request_path"]), event_payload is not None),
        ("pc_scoped_response", str(context["response_path"]), response_payload is not None),
    ]
    return [
        {
            "artifact_ref": artifact_ref,
            "path": path,
            "exists": exists,
            "purpose": artifact_ref.replace("_", " "),
        }
        for artifact_ref, path, exists in artifacts
    ]


def _operator_summary(status: str, *, mac_worker: Mapping[str, Any]) -> str:
    if status == "PASS":
        return "Cross-machine proof passed: Mac event, PC route response, and no-authority checks matched."
    if status == "MAC_WORKER_MISSING":
        return (
            "Mac local proof worker is missing. The PC wrote the bounded proof job and generated "
            "a Mac work package; no proof pass was claimed."
        )
    if status == "MAC_JOB_NOT_ACKED":
        return "Mac proof job was written, but no Mac result appeared before the timeout."
    if status == "EVENT_NOT_EMITTED":
        return "Mac result was present, but the requested Event Bridge envelope was missing or invalid."
    if status == "RESPONSE_NOT_FOUND":
        return "Mac emitted the Event Bridge envelope, but the scoped PC response was not found before timeout."
    if status == "ROUTE_REJECTED":
        return "The PC response existed, but route status or selected handler did not match the proof contract."
    if status == "BOUNDARY_VIOLATION":
        return "The proof saw a forbidden action flag or a missing no-authority guard."
    return f"Cross-machine proof ended with status {status}; review failures for exact blocker."


def _mac_work_package(context: Mapping[str, Any], mac_worker: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# OpenClaw Mac Local Proof Worker Work Package",
            "",
            "Implement a Mac-local proof worker that watches only the bounded proof-job inbox.",
            "",
            f"- Expected Mac inbox: `{Path(str(context['mac_bridge_root'])) / 'mac_local_jobs' / 'inbox'}`",
            f"- Expected Mac results: `{Path(str(context['mac_bridge_root'])) / 'mac_local_jobs' / 'results'}`",
            f"- PC job path already written: `{context['mac_job_path']}`",
            f"- Mac-visible job path: `{context['mac_visible_job_path']}`",
            f"- Worker manifest expected at: `{mac_worker['mac_visible_manifest_path']}`",
            "- Allowlisted job kind: `EMIT_EVENT_BRIDGE_ENVELOPE`",
            "- For v0, emit only the provided `event_envelope` to the requested Event Bridge output path.",
            "- Write a result JSON with `job_id`, `proof_run_id`, `status`, `emitted_event_path`, `correlation_id`, `error_code`, `error_message`, and `boundary_flags`.",
            "- Do not use Excel, export PDFs, send email, open Gmail/browser/Coupa, read workbook cells, post ledgers, print, launch Chief, or call an LM.",
            "",
        ]
    )


def _evaluate_proof(
    context: Mapping[str, Any],
    *,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None, dict[str, str]]:
    failures: list[dict[str, Any]] = []
    boundary_checks: list[dict[str, Any]] = []
    status_by_step: dict[str, str] = {
        "create_proof_run": "PASS",
        "write_mac_job": "PASS",
    }
    mac_worker = _mac_worker_status(context)
    status_by_step["detect_mac_worker"] = "PASS" if mac_worker.get("exists") and mac_worker.get("ready") and mac_worker.get("job_supported") else "FAIL"
    if status_by_step["detect_mac_worker"] == "FAIL":
        failures.append(
            _failure_row(
                failure_ref="missing_mac_worker",
                failure_status="MAC_WORKER_MISSING",
                reason=str(mac_worker["missing_reason"]),
                exact_file=str(mac_worker["manifest_path"]),
            )
        )
        return (
            "MAC_WORKER_MISSING",
            failures,
            boundary_checks,
            None,
            None,
            None,
            status_by_step,
        )

    result_path = Path(str(context["mac_result_path"]))
    if not _wait_for_file(result_path, timeout_seconds=timeout_seconds, poll_interval_seconds=poll_interval_seconds):
        status_by_step["wait_for_mac_result"] = "FAIL"
        failures.append(
            _failure_row(
                failure_ref="missing_mac_result",
                failure_status="MAC_JOB_NOT_ACKED",
                reason="No Mac proof result appeared before timeout.",
                exact_file=result_path.as_posix(),
            )
        )
        return "MAC_JOB_NOT_ACKED", failures, boundary_checks, None, None, None, status_by_step
    status_by_step["wait_for_mac_result"] = "PASS"
    result_payload = _read_json(result_path)
    if not result_payload:
        status_by_step["wait_for_mac_result"] = "FAIL"
        failures.append(
            _failure_row(
                failure_ref="invalid_mac_result",
                failure_status="EVENT_NOT_EMITTED",
                reason="Mac proof result was not valid JSON.",
                exact_file=result_path.as_posix(),
            )
        )
        return "EVENT_NOT_EMITTED", failures, boundary_checks, None, result_payload, None, status_by_step
    boundary_checks.extend(_mac_result_boundary_checks(result_payload))
    if str(result_payload.get("correlation_id") or "") != str(context["correlation_id"]):
        failures.append(
            _failure_row(
                failure_ref="mac_result_correlation_mismatch",
                failure_status="EVENT_NOT_EMITTED",
                reason="Mac result correlation_id did not match proof run.",
                exact_file=result_path.as_posix(),
            )
        )
    emitted_path = Path(str(result_payload.get("emitted_event_path") or context["request_path"]))
    if not emitted_path.is_file():
        status_by_step["verify_event"] = "FAIL"
        failures.append(
            _failure_row(
                failure_ref="missing_emitted_event",
                failure_status="EVENT_NOT_EMITTED",
                reason="Mac result did not point to an emitted Event Bridge envelope.",
                exact_file=emitted_path.as_posix(),
            )
        )
        return "EVENT_NOT_EMITTED", failures, boundary_checks, None, result_payload, None, status_by_step
    event_payload = _read_json(emitted_path)
    boundary_checks.extend(_event_boundary_checks(event_payload))
    expected = context["definition"]
    event_errors = []
    for field, expected_value in (
        ("event_kind", expected["expected_event_kind"]),
        ("source_channel", expected["expected_source_channel"]),
        ("client_ref", expected["client_ref"]),
        ("workflow_ref", expected["workflow_ref"]),
        ("actor_ref", expected["actor_ref"]),
        ("correlation_id", context["correlation_id"]),
    ):
        if str(event_payload.get(field) or "") != str(expected_value):
            event_errors.append(f"{field} expected {expected_value!r} got {event_payload.get(field)!r}")
    payload = event_payload.get("payload") if isinstance(event_payload.get("payload"), Mapping) else {}
    if str(payload.get("action_kind") or "") != expected["action_kind"]:
        event_errors.append("payload.action_kind did not match prepare_selected_invoice_pdf_artifact")
    if not str(event_payload.get("idempotency_key") or ""):
        event_errors.append("idempotency_key missing")
    if event_errors:
        status_by_step["verify_event"] = "FAIL"
        failures.append(
            _failure_row(
                failure_ref="event_contract_mismatch",
                failure_status="EVENT_NOT_EMITTED",
                reason="; ".join(event_errors),
                exact_file=emitted_path.as_posix(),
            )
        )
        return "EVENT_NOT_EMITTED", failures, boundary_checks, event_payload, result_payload, None, status_by_step
    status_by_step["verify_event"] = "PASS"

    response_path = Path(str(context["response_path"]))
    if not _wait_for_file(response_path, timeout_seconds=timeout_seconds, poll_interval_seconds=poll_interval_seconds):
        status_by_step["wait_for_pc_response"] = "FAIL"
        failures.append(
            _failure_row(
                failure_ref="missing_pc_response",
                failure_status="RESPONSE_NOT_FOUND",
                reason="Scoped PC response was not found before timeout.",
                exact_file=response_path.as_posix(),
            )
        )
        return "RESPONSE_NOT_FOUND", failures, boundary_checks, event_payload, result_payload, None, status_by_step
    status_by_step["wait_for_pc_response"] = "PASS"
    response_payload = _read_json(response_path)
    boundary_checks.extend(_response_boundary_checks(response_payload))
    route_values = _response_route_values(response_payload)
    route_errors = []
    for field, expected_value in expected["expected_route"].items():
        if route_values.get(field) != expected_value:
            route_errors.append(f"{field} expected {expected_value!r} got {route_values.get(field)!r}")
    if str(response_payload.get("correlation_id") or "") not in {"", str(context["correlation_id"])}:
        route_errors.append("response correlation_id did not match proof run")
    if route_errors:
        status_by_step["verify_route"] = "FAIL"
        failures.append(
            _failure_row(
                failure_ref="route_rejected_or_mismatched",
                failure_status="ROUTE_REJECTED",
                reason="; ".join(route_errors),
                exact_file=response_path.as_posix(),
            )
        )
        return "ROUTE_REJECTED", failures, boundary_checks, event_payload, result_payload, response_payload, status_by_step
    status_by_step["verify_route"] = "PASS"
    failed_boundary = [row for row in boundary_checks if row["status"] != "PASS"]
    if failed_boundary:
        status_by_step["verify_boundary"] = "FAIL"
        failures.append(
            _failure_row(
                failure_ref="boundary_violation",
                failure_status="BOUNDARY_VIOLATION",
                reason="; ".join(row["check_ref"] for row in failed_boundary),
                exact_file=response_path.as_posix(),
            )
        )
        return "BOUNDARY_VIOLATION", failures, boundary_checks, event_payload, result_payload, response_payload, status_by_step
    status_by_step["verify_boundary"] = "PASS"
    status_by_step["write_receipt"] = "PASS"
    return "PASS", failures, boundary_checks, event_payload, result_payload, response_payload, status_by_step


def build_read_model(
    *,
    context: Mapping[str, Any],
    status: str,
    failures: list[dict[str, Any]],
    boundary_checks: list[dict[str, Any]],
    mac_worker: Mapping[str, Any],
    event_payload: Mapping[str, Any] | None,
    result_payload: Mapping[str, Any] | None,
    response_payload: Mapping[str, Any] | None,
    status_by_step: Mapping[str, str],
    completed_at: str,
) -> dict[str, Any]:
    _require_status(status)
    actual_route = _response_route_values(response_payload or {})
    proof_run = {
        "proof_ref": context["proof_ref"],
        "proof_run_id": context["proof_run_id"],
        "started_at": context["generated_at"],
        "completed_at": completed_at,
        "status": status,
        "correlation_id": context["correlation_id"],
        "request_path": context["request_path"],
        "response_path": context["response_path"],
        "mac_job_path": context["mac_job_path"],
        "expected_route": context["definition"]["expected_route"],
        "actual_route": actual_route,
        "selected_handler_id": actual_route.get("selected_handler_id", ""),
        "boundary_flags": {
            "all_passed": bool(boundary_checks) and not any(row["status"] != "PASS" for row in boundary_checks),
            "failed_checks": [row["check_ref"] for row in boundary_checks if row["status"] != "PASS"],
            "evaluated_check_count": len(boundary_checks),
        },
        "operator_summary": _operator_summary(status, mac_worker=mac_worker),
    }
    return {
        "schema_version": READ_MODEL_VERSION,
        "contract_schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": completed_at,
        "read_model_id": READ_MODEL_ID,
        "purpose": "Deterministic Mac<->PC proof runner for scoped bridge smoke tests.",
        "proof_ref": context["proof_ref"],
        "proof_run_id": context["proof_run_id"],
        "status": status,
        "readiness": "READY" if status == "PASS" else "NOT_READY",
        "mac_worker_exists": bool(mac_worker.get("exists") and mac_worker.get("ready") and mac_worker.get("job_supported")),
        "mac_worker": dict(mac_worker),
        "job_paths": {
            "pc_job_inbox": str(Path(str(context["pc_bridge_root"])) / "mac_local_jobs" / "inbox"),
            "mac_job_inbox": str(Path(str(context["mac_bridge_root"])) / "mac_local_jobs" / "inbox"),
            "pc_result_dir": str(Path(str(context["pc_bridge_root"])) / "mac_local_jobs" / "results"),
            "mac_result_dir": str(Path(str(context["mac_bridge_root"])) / "mac_local_jobs" / "results"),
            "pc_event_inbox": str(Path(str(context["pc_bridge_root"])) / "mission_control_capture_requests" / "inbox"),
            "pc_response_dir": str(Path(str(context["pc_bridge_root"])) / "mission_control_responses" / "to_mac"),
        },
        "proof_runs": [proof_run],
        "proof_steps": _step_rows(context=context, status_by_step=status_by_step),
        "proof_artifacts": _artifact_rows(
            context=context,
            mac_worker=mac_worker,
            event_payload=event_payload,
            result_payload=result_payload,
            response_payload=response_payload,
        ),
        "proof_results": [
            {
                "proof_ref": context["proof_ref"],
                "proof_run_id": context["proof_run_id"],
                "status": status,
                "route_status": actual_route.get("route_status", ""),
                "workflow_status": actual_route.get("workflow_status", ""),
                "selected_handler_id": actual_route.get("selected_handler_id", ""),
                "correlation_id": context["correlation_id"],
            }
        ],
        "proof_failures": failures,
        "proof_boundary_checks": boundary_checks,
        "mac_worker_work_package": MAC_WORK_PACKAGE_NAME if status == "MAC_WORKER_MISSING" else "",
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def operator_markdown(read_model: Mapping[str, Any]) -> str:
    proof_run = (read_model.get("proof_runs") or [{}])[0]
    lines = [
        "# OpenClaw Cross-Machine Proof Runner",
        "",
        f"- Status: `{read_model.get('status', 'UNKNOWN')}`",
        f"- Proof: `{read_model.get('proof_ref', '')}`",
        f"- Proof run: `{read_model.get('proof_run_id', '')}`",
        f"- Correlation: `{proof_run.get('correlation_id', '')}`",
        f"- Mac worker ready: `{read_model.get('mac_worker_exists', False)}`",
        f"- Operator summary: {proof_run.get('operator_summary', '')}",
        "",
        "## Paths",
        "",
    ]
    for key, value in (read_model.get("job_paths") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Result", ""])
    for result in read_model.get("proof_results", []):
        lines.append(
            f"- `{result.get('status')}` route=`{result.get('route_status', '')}` "
            f"workflow=`{result.get('workflow_status', '')}` handler=`{result.get('selected_handler_id', '')}`"
        )
    failures = read_model.get("proof_failures") or []
    if failures:
        lines.extend(["", "## Failures", ""])
        for failure in failures:
            lines.append(f"- `{failure.get('failure_status')}`: {failure.get('reason')} (`{failure.get('exact_file', '')}`)")
    lines.extend(["", "## Boundary", ""])
    lines.append("No LM, Chief, services, email/Gmail/browser/Coupa, workbook cell read, PDF export, ledger mutation, production mutation, or physical printing is authorized.")
    lines.append("")
    return "\n".join(lines)


def sqlite_schema_sql() -> str:
    return """CREATE TABLE proof_run (
  proof_ref TEXT,
  proof_run_id TEXT PRIMARY KEY,
  started_at TEXT,
  completed_at TEXT,
  status TEXT,
  correlation_id TEXT,
  request_path TEXT,
  response_path TEXT,
  mac_job_path TEXT,
  expected_route TEXT,
  actual_route TEXT,
  selected_handler_id TEXT,
  boundary_flags TEXT,
  operator_summary TEXT
);

CREATE TABLE proof_step (
  step_ref TEXT,
  proof_run_id TEXT,
  status TEXT,
  summary TEXT,
  path TEXT
);

CREATE TABLE proof_artifact (
  artifact_ref TEXT,
  proof_run_id TEXT,
  path TEXT,
  artifact_exists INTEGER,
  purpose TEXT
);

CREATE TABLE proof_result (
  proof_ref TEXT,
  proof_run_id TEXT,
  status TEXT,
  route_status TEXT,
  workflow_status TEXT,
  selected_handler_id TEXT,
  correlation_id TEXT
);

CREATE TABLE proof_failure (
  failure_ref TEXT,
  proof_run_id TEXT,
  failure_status TEXT,
  reason TEXT,
  exact_file TEXT
);

CREATE TABLE proof_boundary_check (
  check_ref TEXT,
  proof_run_id TEXT,
  status TEXT,
  expected TEXT,
  actual TEXT,
  detail TEXT
);
"""


def _sql_quote(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def sqlite_seed_sql(read_model: Mapping[str, Any]) -> str:
    rows: list[str] = []
    run_id = str(read_model.get("proof_run_id", ""))
    for row in read_model.get("proof_runs", []):
        rows.append(
            "INSERT INTO proof_run VALUES ("
            + ", ".join(
                _sql_quote(value)
                for value in (
                    row.get("proof_ref", ""),
                    row.get("proof_run_id", ""),
                    row.get("started_at", ""),
                    row.get("completed_at", ""),
                    row.get("status", ""),
                    row.get("correlation_id", ""),
                    row.get("request_path", ""),
                    row.get("response_path", ""),
                    row.get("mac_job_path", ""),
                    stable_json(row.get("expected_route", {})).strip(),
                    stable_json(row.get("actual_route", {})).strip(),
                    row.get("selected_handler_id", ""),
                    stable_json(row.get("boundary_flags", {})).strip(),
                    row.get("operator_summary", ""),
                )
            )
            + ");"
        )
    for row in read_model.get("proof_steps", []):
        rows.append(
            "INSERT INTO proof_step VALUES ("
            + ", ".join(_sql_quote(value) for value in (row.get("step_ref", ""), run_id, row.get("status", ""), row.get("summary", ""), row.get("path", "")))
            + ");"
        )
    for row in read_model.get("proof_artifacts", []):
        rows.append(
            "INSERT INTO proof_artifact VALUES ("
            + ", ".join(_sql_quote(value) for value in (row.get("artifact_ref", ""), run_id, row.get("path", ""), 1 if row.get("exists") else 0, row.get("purpose", "")))
            + ");"
        )
    for row in read_model.get("proof_results", []):
        rows.append(
            "INSERT INTO proof_result VALUES ("
            + ", ".join(
                _sql_quote(value)
                for value in (
                    row.get("proof_ref", ""),
                    row.get("proof_run_id", ""),
                    row.get("status", ""),
                    row.get("route_status", ""),
                    row.get("workflow_status", ""),
                    row.get("selected_handler_id", ""),
                    row.get("correlation_id", ""),
                )
            )
            + ");"
        )
    for row in read_model.get("proof_failures", []):
        rows.append(
            "INSERT INTO proof_failure VALUES ("
            + ", ".join(_sql_quote(value) for value in (row.get("failure_ref", ""), run_id, row.get("failure_status", ""), row.get("reason", ""), row.get("exact_file", "")))
            + ");"
        )
    for row in read_model.get("proof_boundary_checks", []):
        rows.append(
            "INSERT INTO proof_boundary_check VALUES ("
            + ", ".join(_sql_quote(value) for value in (row.get("check_ref", ""), run_id, row.get("status", ""), row.get("expected", ""), row.get("actual", ""), row.get("detail", "")))
            + ");"
        )
    return "\n".join(rows) + ("\n" if rows else "")


def create_sqlite_registry(read_model: Mapping[str, Any], sqlite_path: str | Path) -> None:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    try:
        connection.executescript(sqlite_schema_sql())
        run_id = str(read_model.get("proof_run_id", ""))
        for row in read_model.get("proof_runs", []):
            connection.execute(
                "INSERT INTO proof_run VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row.get("proof_ref", ""),
                    row.get("proof_run_id", ""),
                    row.get("started_at", ""),
                    row.get("completed_at", ""),
                    row.get("status", ""),
                    row.get("correlation_id", ""),
                    row.get("request_path", ""),
                    row.get("response_path", ""),
                    row.get("mac_job_path", ""),
                    stable_json(row.get("expected_route", {})).strip(),
                    stable_json(row.get("actual_route", {})).strip(),
                    row.get("selected_handler_id", ""),
                    stable_json(row.get("boundary_flags", {})).strip(),
                    row.get("operator_summary", ""),
                ),
            )
        for row in read_model.get("proof_steps", []):
            connection.execute(
                "INSERT INTO proof_step VALUES (?, ?, ?, ?, ?)",
                (row.get("step_ref", ""), run_id, row.get("status", ""), row.get("summary", ""), row.get("path", "")),
            )
        for row in read_model.get("proof_artifacts", []):
            connection.execute(
                "INSERT INTO proof_artifact VALUES (?, ?, ?, ?, ?)",
                (row.get("artifact_ref", ""), run_id, row.get("path", ""), 1 if row.get("exists") else 0, row.get("purpose", "")),
            )
        for row in read_model.get("proof_results", []):
            connection.execute(
                "INSERT INTO proof_result VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    row.get("proof_ref", ""),
                    row.get("proof_run_id", ""),
                    row.get("status", ""),
                    row.get("route_status", ""),
                    row.get("workflow_status", ""),
                    row.get("selected_handler_id", ""),
                    row.get("correlation_id", ""),
                ),
            )
        for row in read_model.get("proof_failures", []):
            connection.execute(
                "INSERT INTO proof_failure VALUES (?, ?, ?, ?, ?)",
                (row.get("failure_ref", ""), run_id, row.get("failure_status", ""), row.get("reason", ""), row.get("exact_file", "")),
            )
        for row in read_model.get("proof_boundary_checks", []):
            connection.execute(
                "INSERT INTO proof_boundary_check VALUES (?, ?, ?, ?, ?, ?)",
                (row.get("check_ref", ""), run_id, row.get("status", ""), row.get("expected", ""), row.get("actual", ""), row.get("detail", "")),
            )
        connection.commit()
    finally:
        connection.close()


def run_cross_machine_proof(
    *,
    proof_ref: str,
    generated_at: str | None = None,
    pc_bridge_root: str | Path = DEFAULT_PC_BRIDGE_ROOT,
    mac_bridge_root: str = DEFAULT_MAC_BRIDGE_ROOT,
    timeout_seconds: float = 60.0,
    poll_interval_seconds: float = 1.0,
) -> dict[str, Any]:
    context = build_proof_context(
        proof_ref=proof_ref,
        generated_at=generated_at,
        pc_bridge_root=pc_bridge_root,
        mac_bridge_root=mac_bridge_root,
    )
    _write_mac_job(context)
    status, failures, boundary_checks, event_payload, result_payload, response_payload, status_by_step = _evaluate_proof(
        context,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
    mac_worker = _mac_worker_status(context)
    completed_at = utc_now() if generated_at is None else _plus_minutes(generated_at, 0)
    return build_read_model(
        context=context,
        status=status,
        failures=failures,
        boundary_checks=boundary_checks,
        mac_worker=mac_worker,
        event_payload=event_payload,
        result_payload=result_payload,
        response_payload=response_payload,
        status_by_step=status_by_step,
        completed_at=completed_at,
    )


def export_openclaw_cross_machine_proof_runner(
    *,
    proof_ref: str = "event_bridge_live_arts_prepare_pdf",
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    system_knowledge_root: str | Path = DEFAULT_SYSTEM_KNOWLEDGE_ROOT,
    pc_bridge_root: str | Path = DEFAULT_PC_BRIDGE_ROOT,
    mac_bridge_root: str = DEFAULT_MAC_BRIDGE_ROOT,
    timeout_seconds: float = 60.0,
    poll_interval_seconds: float = 1.0,
    generated_at: str | None = None,
) -> CrossMachineProofExportResult:
    read_root = _rooted(read_model_root)
    system_root = _rooted(system_knowledge_root)
    read_model = run_cross_machine_proof(
        proof_ref=proof_ref,
        generated_at=generated_at,
        pc_bridge_root=pc_bridge_root,
        mac_bridge_root=mac_bridge_root,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
    json_path = read_root / JSON_EXPORT_NAME
    operator_path = read_root / OPERATOR_EXPORT_NAME
    mac_work_package_path = read_root / MAC_WORK_PACKAGE_NAME
    sqlite_path = system_root / SQLITE_EXPORT_NAME
    schema_path = system_root / SCHEMA_EXPORT_NAME
    seed_path = system_root / SEED_EXPORT_NAME
    _atomic_write_text(json_path, stable_json(read_model))
    _atomic_write_text(operator_path, operator_markdown(read_model))
    _atomic_write_text(schema_path, sqlite_schema_sql())
    _atomic_write_text(seed_path, sqlite_seed_sql(read_model))
    create_sqlite_registry(read_model, sqlite_path)
    if read_model.get("status") == "MAC_WORKER_MISSING":
        context = build_proof_context(
            proof_ref=proof_ref,
            generated_at=read_model["proof_runs"][0]["started_at"],
            pc_bridge_root=pc_bridge_root,
            mac_bridge_root=mac_bridge_root,
        )
        _atomic_write_text(mac_work_package_path, _mac_work_package(context, read_model.get("mac_worker", {})))
    elif mac_work_package_path.exists():
        mac_work_package_path.unlink()
    return CrossMachineProofExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        sqlite_path=_display_path(sqlite_path),
        schema_sql_path=_display_path(schema_path),
        seed_sql_path=_display_path(seed_path),
        mac_work_package_path=_display_path(mac_work_package_path) if mac_work_package_path.exists() else "",
        proof_ref=str(read_model.get("proof_ref", "")),
        proof_run_id=str(read_model.get("proof_run_id", "")),
        status=str(read_model.get("status", "UNKNOWN")),
        mac_worker_exists=bool(read_model.get("mac_worker_exists", False)),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an OpenClaw deterministic cross-machine proof.")
    parser.add_argument("--proof", choices=SUPPORTED_PROOFS, default="event_bridge_live_arts_prepare_pdf")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--system-knowledge-root", default=str(DEFAULT_SYSTEM_KNOWLEDGE_ROOT))
    parser.add_argument("--pc-bridge-root", default=str(DEFAULT_PC_BRIDGE_ROOT))
    parser.add_argument("--mac-bridge-root", default=DEFAULT_MAC_BRIDGE_ROOT)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=1.0)
    parser.add_argument("--generated-at", default="")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)
    result = export_openclaw_cross_machine_proof_runner(
        proof_ref=args.proof,
        read_model_root=args.read_model_root,
        system_knowledge_root=args.system_knowledge_root,
        pc_bridge_root=args.pc_bridge_root,
        mac_bridge_root=args.mac_bridge_root,
        timeout_seconds=args.timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
        generated_at=args.generated_at or None,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(f"proof={result.proof_ref}")
        print(f"proof_run_id={result.proof_run_id}")
        print(f"status={result.status}")
        print(f"mac_worker_exists={result.mac_worker_exists}")
        print(f"json={result.json_path}")
        print(f"operator={result.operator_path}")
        print(f"sqlite={result.sqlite_path}")
        if result.mac_work_package_path:
            print(f"mac_work_package={result.mac_work_package_path}")
    return 0 if result.status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
