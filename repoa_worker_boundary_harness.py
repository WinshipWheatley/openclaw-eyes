"""Repo A worker boundary harness v0.

Builds one bounded Repo A Chief package, runs the local Chief offline worker
adapter, validates the worker result with Guardian, and records one SQLite
receipt. This is executable local plumbing only; it does not start Repo B,
call models, run tools, or perform external actions.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import chief_offline_worker_adapter
import cassandra_clara_offline_worker_adapter
import guardian_output_gate
import intent_ingest_gate
import machine_intent_candidate_validator as intent_validator
import role_package_gate


SCHEMA_VERSION = "repoa_worker_boundary_harness_v0"
DEFAULT_RECEIPT_DB_PATH = Path(".openclaw/test_harness/repoa_worker_boundary.sqlite")

AUTHORITY_BOUNDARY = {
    "repo_b_runtime_start_allowed": False,
    "live_model_call_allowed": False,
    "tool_execution_allowed": False,
    "external_action_allowed": False,
    "send_submit_allowed": False,
    "workflow_execution_allowed": False,
    "production_state_mutation_allowed": False,
    "credential_access_allowed": False,
    "network_allowed": False,
}


@dataclass(frozen=True)
class WorkerBoundaryReceipt:
    receipt_id: str
    run_id: str
    source_request_id: str
    package_id: str
    worker_adapter_id: str
    role_family: str
    selected_voice: str
    validation_verdict: str
    action_taken: str
    external_action: bool
    authority_used: bool
    receipt_hash: str
    created_at: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _receipt_hash(payload: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(stable_json(dict(payload)).encode("utf-8")).hexdigest()


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
CREATE TABLE IF NOT EXISTS repoa_worker_run_receipts (
  receipt_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  source_request_id TEXT NOT NULL,
  package_id TEXT NOT NULL,
  worker_adapter_id TEXT NOT NULL,
  role_family TEXT NOT NULL,
  selected_voice TEXT NOT NULL,
  validation_verdict TEXT NOT NULL,
  action_taken TEXT NOT NULL,
  external_action INTEGER NOT NULL CHECK (external_action = 0),
  authority_used INTEGER NOT NULL CHECK (authority_used = 0),
  receipt_hash TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
)
"""
    )
    existing = {
        row[1]
        for row in conn.execute("PRAGMA table_info(repoa_worker_run_receipts)").fetchall()
    }
    if "role_family" not in existing:
        conn.execute("ALTER TABLE repoa_worker_run_receipts ADD COLUMN role_family TEXT NOT NULL DEFAULT 'UNKNOWN'")
    if "selected_voice" not in existing:
        conn.execute("ALTER TABLE repoa_worker_run_receipts ADD COLUMN selected_voice TEXT NOT NULL DEFAULT 'UNKNOWN'")


def build_chief_status_role_package(
    *,
    source_request_id: str,
    user_message: str = "Show me the next safe move.",
    world_ref: str = "finance",
    client_ref: str = "capital_hilton",
    workflow_ref: str = "capital_hilton_invoice_workflow",
) -> dict[str, Any]:
    candidate = intent_validator.MachineIntentCandidate(
        intent_id=f"chief_worker_candidate:{_short_hash(source_request_id, user_message)}",
        source_request_id=source_request_id,
        original_operator_text=user_message,
        inferred_intent_type="ANSWER_STATUS",
        target_world_ref=world_ref,
        target_folder_ref=client_ref,
        target_thread_ref=f"thread_ref:{world_ref}:{client_ref}",
        target_workflow_ref=workflow_ref,
        target_agent_role="CHIEF",
        target_worker_type="PC_CODEX",
        requested_action="status_or_next_safe_move",
        referenced_next_action="",
        confidence="HIGH",
        ambiguity_status="UNAMBIGUOUS",
        required_clarification="",
        evidence_refs_used=("generated/read_models/lm_readiness_dashboard.json",),
        context_refs_used=("tenant_scope:fixture_business_ops",),
        source_refs_used=(),
        missing_requirements=(),
        forbidden_assumptions=(),
        authority_requested={"send_submit": False, "external_action": False, "tool_execution": False},
        authority_granted={"send_submit": False, "external_action": False, "tool_execution": False},
        validation_required=True,
        next_safe_move="Compile a bounded Chief package; do not execute tools.",
    )
    ingest_result = intent_ingest_gate.ingest_intent_proposal(candidate)
    package_result = role_package_gate.compile_role_package(ingest_result)
    return {
        "candidate": candidate.__dict__,
        "ingest_result": ingest_result,
        "package_result": package_result,
        "role_package": package_result.get("role_execution_package"),
    }


def build_cassandra_clara_role_package(
    *,
    source_request_id: str,
    user_message: str,
    audience: str,
    world_ref: str = "finance",
    client_ref: str = "capital_hilton",
    workflow_ref: str = "capital_hilton_invoice_workflow",
) -> dict[str, Any]:
    normalized_audience = str(audience or "").strip().lower()
    if normalized_audience not in {"internal", "external"}:
        raise ValueError("audience must be internal or external")
    selected_voice = "CLARA" if normalized_audience == "external" else "CASSANDRA"
    candidate = intent_validator.MachineIntentCandidate(
        intent_id=f"cassandra_clara_worker_candidate:{_short_hash(source_request_id, user_message, normalized_audience)}",
        source_request_id=source_request_id,
        original_operator_text=user_message,
        inferred_intent_type="CAPTURE_MISSING_INPUT",
        target_world_ref=world_ref,
        target_folder_ref=client_ref,
        target_thread_ref=f"thread_ref:{world_ref}:{client_ref}",
        target_workflow_ref=workflow_ref,
        target_agent_role="CASSANDRA",
        target_worker_type="PC_CODEX",
        requested_action="comms_draft_or_status",
        referenced_next_action="",
        confidence="HIGH",
        ambiguity_status="UNAMBIGUOUS",
        required_clarification="",
        evidence_refs_used=("generated/read_models/lm_readiness_dashboard.json",),
        context_refs_used=("tenant_scope:fixture_business_ops",),
        source_refs_used=(),
        missing_requirements=(),
        forbidden_assumptions=("do_not_send", "do_not_claim_submitted", "do_not_mark_final"),
        authority_requested={"send_submit": False, "external_action": False, "tool_execution": False},
        authority_granted={"send_submit": False, "external_action": False, "tool_execution": False},
        validation_required=True,
        next_safe_move="Compile a bounded Cassandra/Clara package; do not execute tools or send.",
    )
    ingest_result = intent_ingest_gate.ingest_intent_proposal(candidate)
    package_result = role_package_gate.compile_role_package(ingest_result)
    role_package = package_result.get("role_execution_package")
    if isinstance(role_package, Mapping):
        role_package = {
            **dict(role_package),
            "role_family": "CASSANDRA_CLARA",
            "internal_role_identity": "CASSANDRA",
            "external_voice_identity": "CLARA",
            "audience": normalized_audience,
            "internal_or_external": normalized_audience,
            "selected_voice": selected_voice,
            "task": "comms_draft_or_status",
        }
        package_result = {**package_result, "role_execution_package": role_package}
    return {
        "candidate": candidate.__dict__,
        "ingest_result": ingest_result,
        "package_result": package_result,
        "role_package": role_package,
    }


def guardian_package_from_role_package(package: Mapping[str, Any]) -> guardian_output_gate.RoleExecutionPackage:
    tool_policy = package.get("tool_policy") if isinstance(package.get("tool_policy"), Mapping) else {}
    role = str(package.get("role_identity") or "CHIEF").upper()
    return guardian_output_gate.RoleExecutionPackage(
        package_id=str(package.get("package_id") or ""),
        source_request_id=str(package.get("source_request_id") or ""),
        source_intent_ref=str(package.get("source_intent_ref") or ""),
        role=role,
        model_backend=f"OFFLINE_DETERMINISTIC_{role}_WORKER",
        device_response_target="mission_control_scoped_response",
        workflow_ref=str(package.get("workflow_ref") or ""),
        client_ref=str(package.get("client_ref") or ""),
        allowed_tools=tuple(str(item) for item in tool_policy.get("allowed_tools") or ()),
        allowed_actions=("respond_to_originating_device",),
        forbidden_actions=guardian_output_gate.FORBIDDEN_ACTIONS,
        proof_refs=(str(package.get("source_ingest_result_ref") or ""),),
        authority_boundary=dict(guardian_output_gate.AUTHORITY_BOUNDARY),
        output_contract=(
            "respond only to scoped originating device/thread",
            "do not claim send/submit/paid/completed without proof",
            "do not request tools/actions outside package",
            "do not expose credentials, raw bodies, hashes, or local paths",
        ),
        validation_required=True,
        next_safe_move="Validate offline worker output before recording the receipt.",
    )


def worker_result_candidate(
    worker_result: Mapping[str, Any],
    package: guardian_output_gate.RoleExecutionPackage,
) -> guardian_output_gate.RoleResponseCandidate:
    raw_text = " ".join(
        str(worker_result.get(key) or "")
        for key in ("headline", "one_line_answer", "eliwinship", "status_summary", "draft_text", "next_action")
    )
    return guardian_output_gate.RoleResponseCandidate(
        candidate_id=f"chief_worker_candidate:{_short_hash(worker_result.get('result_id'), raw_text)}",
        source_package_id=str(worker_result.get("source_package_id") or ""),
        source_request_id=str(worker_result.get("source_request_id") or ""),
        response_author=str(worker_result.get("response_author") or "").upper(),
        target_device_ref="mission_control_scoped_response",
        target_thread_ref=str(worker_result.get("source_request_id") or ""),
        headline=str(worker_result.get("headline") or ""),
        one_line_answer=str(worker_result.get("one_line_answer") or ""),
        eliwinship=str(worker_result.get("eliwinship") or ""),
        next_action=str(worker_result.get("next_action") or ""),
        requested_tool_calls=tuple(str(item) for item in worker_result.get("requested_tool_calls") or ()),
        requested_external_actions=tuple(str(item) for item in worker_result.get("requested_external_actions") or ()),
        completion_claims=guardian_output_gate._unnegated_claims(raw_text),
        proof_refs=package.proof_refs,
        authority_requested={"external_action": bool(worker_result.get("external_action")), "authority_used": bool(worker_result.get("authority_used"))},
        raw_output_text=raw_text,
        next_safe_move=str(worker_result.get("next_safe_move") or ""),
    )


def validate_worker_result(worker_result: Mapping[str, Any], role_package: Mapping[str, Any]) -> dict[str, Any]:
    guardian_package = guardian_package_from_role_package(role_package)
    candidate = worker_result_candidate(worker_result, guardian_package)
    validation = guardian_output_gate.validate_role_output(candidate, guardian_package)
    return {
        "guardian_package": asdict(guardian_package),
        "worker_response_candidate": asdict(candidate),
        "validation_result": asdict(validation),
    }


def record_worker_receipt(
    *,
    role_package: Mapping[str, Any],
    worker_result: Mapping[str, Any],
    validation_result: Mapping[str, Any],
    db_path: Path = DEFAULT_RECEIPT_DB_PATH,
    created_at: str | None = None,
    receipt_classification: str = "offline_worker_fixture",
    production_receipt: bool = False,
    harness_ref: str = "",
) -> dict[str, Any]:
    created_at = created_at or utc_now()
    if validation_result.get("verdict") != guardian_output_gate.VALIDATED:
        raise ValueError("Worker result must pass Guardian before receipt recording.")
    if str(worker_result.get("action_taken") or "") != "none":
        raise ValueError("Only no-action offline worker results may be recorded.")
    if bool(worker_result.get("external_action")) or bool(worker_result.get("authority_used")):
        raise ValueError("Worker result used authority or external action.")
    role_family = str(worker_result.get("role_family") or role_package.get("role_family") or role_package.get("role_identity") or "")
    selected_voice = str(worker_result.get("selected_voice") or role_package.get("selected_voice") or role_family or "")

    receipt_payload = {
        "schema_version": SCHEMA_VERSION,
        "receipt_classification": str(receipt_classification or "offline_worker_fixture"),
        "production_receipt": bool(production_receipt),
        "harness_ref": str(harness_ref or ""),
        "source_request_id": worker_result["source_request_id"],
        "package_id": role_package["package_id"],
        "worker_adapter_id": worker_result["worker_adapter_id"],
        "role_family": role_family,
        "selected_voice": selected_voice,
        "worker_result_id": worker_result["result_id"],
        "validation_result_id": validation_result["validation_result_id"],
        "validation_verdict": validation_result["verdict"],
        "action_taken": worker_result["action_taken"],
        "external_action": False,
        "authority_used": False,
    }
    receipt_hash = _receipt_hash(receipt_payload)
    receipt = WorkerBoundaryReceipt(
        receipt_id=f"repoa_worker_receipt:{_short_hash(receipt_hash)}",
        run_id=f"repoa_worker_run:{_short_hash(role_package['package_id'], worker_result['result_id'])}",
        source_request_id=str(worker_result["source_request_id"]),
        package_id=str(role_package["package_id"]),
        worker_adapter_id=str(worker_result["worker_adapter_id"]),
        role_family=role_family,
        selected_voice=selected_voice,
        validation_verdict=str(validation_result["verdict"]),
        action_taken=str(worker_result["action_taken"]),
        external_action=False,
        authority_used=False,
        receipt_hash=receipt_hash,
        created_at=created_at,
    )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        _create_schema(conn)
        conn.execute(
            """
INSERT OR REPLACE INTO repoa_worker_run_receipts
  (receipt_id, run_id, source_request_id, package_id, worker_adapter_id,
   role_family, selected_voice, validation_verdict, action_taken, external_action, authority_used,
   receipt_hash, payload_json, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""",
            (
                receipt.receipt_id,
                receipt.run_id,
                receipt.source_request_id,
                receipt.package_id,
                receipt.worker_adapter_id,
                receipt.role_family,
                receipt.selected_voice,
                receipt.validation_verdict,
                receipt.action_taken,
                int(receipt.external_action),
                int(receipt.authority_used),
                receipt.receipt_hash,
                stable_json(receipt_payload),
                receipt.created_at,
            ),
        )
        conn.commit()
    return asdict(receipt)


def run_chief_status_worker_path(
    *,
    source_request_id: str = "repoa_chief_worker_fixture_request",
    receipt_db_path: Path = DEFAULT_RECEIPT_DB_PATH,
    created_at: str | None = None,
) -> dict[str, Any]:
    package_flow = build_chief_status_role_package(source_request_id=source_request_id)
    role_package = package_flow["role_package"]
    if not isinstance(role_package, Mapping):
        raise ValueError("Chief role package was not compiled.")
    worker_result = chief_offline_worker_adapter.run_chief_offline_worker(role_package)
    validation = validate_worker_result(worker_result, role_package)
    receipt = record_worker_receipt(
        role_package=role_package,
        worker_result=worker_result,
        validation_result=validation["validation_result"],
        db_path=receipt_db_path,
        created_at=created_at,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "source_request_id": source_request_id,
        **package_flow,
        "worker_result": worker_result,
        "guardian_validation": validation,
        "sqlite_receipt": receipt,
        "receipt_db_path": receipt_db_path.as_posix(),
        "machine_proof": {
            "gate2_ingest_used": package_flow["ingest_result"]["outcome"] == intent_ingest_gate.ACCEPTED_INTENT,
            "gate3_package_used": package_flow["package_result"]["package_status"] == role_package_gate.PACKAGE_COMPILED,
            "chief_offline_worker_called": worker_result["worker_adapter_id"] == chief_offline_worker_adapter.ADAPTER_ID,
            "guardian_output_gate_used": validation["validation_result"]["verdict"] == guardian_output_gate.VALIDATED,
            "sqlite_receipt_written": bool(receipt["receipt_id"]),
            "repo_b_runtime_started": False,
            "live_model_call_performed": False,
            "tool_execution_performed": False,
            "external_action_performed": False,
            "send_submit_performed": False,
            "production_state_mutation_performed": False,
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }


def run_cassandra_clara_worker_path(
    *,
    source_request_id: str,
    user_message: str,
    audience: str,
    receipt_db_path: Path = DEFAULT_RECEIPT_DB_PATH,
    created_at: str | None = None,
) -> dict[str, Any]:
    package_flow = build_cassandra_clara_role_package(
        source_request_id=source_request_id,
        user_message=user_message,
        audience=audience,
    )
    role_package = package_flow["role_package"]
    if not isinstance(role_package, Mapping):
        raise ValueError("Cassandra/Clara role package was not compiled.")
    worker_result = cassandra_clara_offline_worker_adapter.run_cassandra_clara_offline_worker(role_package)
    validation = validate_worker_result(worker_result, role_package)
    receipt = record_worker_receipt(
        role_package=role_package,
        worker_result=worker_result,
        validation_result=validation["validation_result"],
        db_path=receipt_db_path,
        created_at=created_at,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "source_request_id": source_request_id,
        **package_flow,
        "worker_result": worker_result,
        "guardian_validation": validation,
        "sqlite_receipt": receipt,
        "receipt_db_path": receipt_db_path.as_posix(),
        "machine_proof": {
            "gate2_ingest_used": package_flow["ingest_result"]["outcome"] == intent_ingest_gate.ACCEPTED_INTENT,
            "gate3_package_used": package_flow["package_result"]["package_status"] == role_package_gate.PACKAGE_COMPILED,
            "cassandra_clara_offline_worker_called": worker_result["worker_adapter_id"]
            == cassandra_clara_offline_worker_adapter.ADAPTER_ID,
            "guardian_output_gate_used": validation["validation_result"]["verdict"] == guardian_output_gate.VALIDATED,
            "sqlite_receipt_written": bool(receipt["receipt_id"]),
            "repo_b_runtime_started": False,
            "live_model_call_performed": False,
            "tool_execution_performed": False,
            "external_action_performed": False,
            "send_submit_performed": False,
            "production_state_mutation_performed": False,
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }


__all__ = [
    "DEFAULT_RECEIPT_DB_PATH",
    "build_cassandra_clara_role_package",
    "build_chief_status_role_package",
    "record_worker_receipt",
    "run_cassandra_clara_worker_path",
    "run_chief_status_worker_path",
    "validate_worker_result",
]
