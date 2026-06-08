"""LM2 live worker pilot boundary packet V0.

Review-only boundary packet for the first bounded LM2 worker pilot. This module
does not invoke a model, connect runtimes, spawn workers, send prompts or proof
bundles, call providers, mutate business systems, or grant authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import local_model_selection_for_proof_response
import proof_bundle_builder as bundles
import proof_to_response_runtime as runtime
import proof_to_response_schema_adapter as schema_adapter


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/LM2 Live Worker Pilot Boundary Packet.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/lm2_live_worker_pilot_boundary_packet.sqlite")
ROOM_BACKED_DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/LM2 Room Backed Worker Pilot Boundary.md")
ROOM_BACKED_DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/lm2_room_backed_worker_pilot_boundary.sqlite")

SCHEMA_VERSION = "lm2_live_worker_pilot_boundary_packet_v0"
READ_MODEL_ID = "lm2_live_worker_pilot_boundary_packet"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "LM2_LIVE_WORKER_PILOT_BOUNDARY_READY"
NOT_READY_STATUS = "LM2_LIVE_WORKER_PILOT_BOUNDARY_NOT_READY"
ROOM_BACKED_SCHEMA_VERSION = "lm2_room_backed_worker_pilot_boundary_v1"
ROOM_BACKED_READ_MODEL_ID = "lm2_room_backed_worker_pilot_boundary"
ROOM_BACKED_JSON_EXPORT_NAME = f"{ROOM_BACKED_READ_MODEL_ID}.json"
ROOM_BACKED_READY_STATUS = "LM2_ROOM_BACKED_WORKER_PILOT_BOUNDARY_READY"
ROOM_BACKED_NOT_READY_STATUS = "LM2_ROOM_BACKED_WORKER_PILOT_BOUNDARY_NOT_READY"
PACKET_STATUS = "pending_operator_review"

WORKER_CLASS = "lm2_bounded_worker"
RUNTIME_REF = "ollama"
MODEL_NAME = "qwen3:8b-q4_K_M"
MODEL_REF = "local_model:ollama:qwen3_8b-q4_k_m"
PILOT_LANE = "finance/capital_hilton"
WORLD_REF = "finance"
THREAD_REF = "capital_hilton"
OBJECTIVE_REF = "payment_watch_response"
QUESTION = "What should I do here?"
MODE = "proof_to_response_only"

PRECONDITIONS = {
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
    "local_lm_proof_response_retry_operator_approval": {
        "filename": "local_lm_proof_response_retry_operator_approval.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_RETRY_OPERATOR_APPROVAL_READY",),
    },
    "goldilocks_gate_calibration": {
        "filename": "goldilocks_gate_calibration.json",
        "accepted_statuses": ("GOLDILOCKS_GATE_CALIBRATION_READY",),
    },
    "universal_receipt_envelope": {
        "filename": "universal_receipt_envelope_status.json",
        "accepted_statuses": ("UNIVERSAL_RECEIPT_ENVELOPE_READY",),
    },
    "operator_controller_protocol": {
        "filename": "operator_controller_protocol.json",
        "accepted_statuses": ("OPERATOR_CONTROLLER_PROTOCOL_READY",),
    },
}

ROOM_BACKED_PRECONDITIONS = {
    "lm2_live_worker_pilot_boundary": {
        "filename": JSON_EXPORT_NAME,
        "accepted_statuses": (READY_STATUS,),
    },
    "project_room_sourceset_contract": {
        "filename": "project_room_sourceset_contract.json",
        "accepted_statuses": ("PROJECT_ROOM_SOURCESET_CONTRACT_READY",),
    },
    "project_room_package_compiler_integration": {
        "filename": "project_room_package_compiler_integration.json",
        "accepted_statuses": ("PROJECT_ROOM_PACKAGE_COMPILER_INTEGRATION_READY",),
    },
    "context_compaction_preview_policy": {
        "filename": "context_compaction_preview_policy.json",
        "accepted_statuses": ("CONTEXT_COMPACTION_PREVIEW_POLICY_READY",),
    },
    "context_freshness_decision_trace_gate": {
        "filename": "context_freshness_decision_trace_gate.json",
        "accepted_statuses": ("CONTEXT_FRESHNESS_DECISION_TRACE_GATE_READY",),
    },
    "proof_bundle_freshness_trace_integration": {
        "filename": bundles.FRESHNESS_TRACE_STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (bundles.FRESHNESS_TRACE_READY_STATUS,),
    },
    "proof_bundle_builder_redaction_integration": {
        "filename": bundles.REDACTION_STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (bundles.REDACTION_READY_STATUS,),
    },
    "proof_to_response_schema_adapter": {
        "filename": schema_adapter.STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (schema_adapter.READY_STATUS,),
    },
    "universal_receipt_envelope": {
        "filename": "universal_receipt_envelope_status.json",
        "accepted_statuses": ("UNIVERSAL_RECEIPT_ENVELOPE_READY",),
    },
    "goldilocks_gate_calibration": {
        "filename": "goldilocks_gate_calibration.json",
        "accepted_statuses": ("GOLDILOCKS_GATE_CALIBRATION_READY",),
    },
}

ALLOWED_WORKER_INPUTS = (
    "redacted_freshness_gated_proof_bundle",
    "agent_voice_mode",
    "required_json_response_schema",
    "expected_response_example",
    "stop_conditions",
    "verifier_requirements",
)

FORBIDDEN_WORKER_INPUTS = (
    "raw_financial_proof",
    "bank_or_account_details",
    "credentials_or_tokens",
    "operator_device_session_verification_secrets",
    "raw_prompt_dumps",
    "raw_ocr_or_artifact_text",
    "workbook_bodies",
    "email_bodies",
    "ledger_bodies",
    "hidden_machine_contracts",
    "authority_granted_fields",
)

WORKER_CAPABILITIES_ALLOWED = (
    "read_provided_redacted_proof_bundle",
    "draft_one_json_proof_to_response_candidate",
    "return_candidate_to_verifier",
    "stop",
)

WORKER_CAPABILITIES_FORBIDDEN = (
    "tool_use",
    "browser_gmail_coupa",
    "email_send",
    "submit",
    "ledger_mutation",
    "workbook_mutation",
    "pdf_export",
    "paid_marking",
    "memory_promotion",
    "worker_spawning",
    "external_provider",
    "file_system_mutation",
    "shell_commands",
    "repeated_invocations",
)

RECEIPTS_REQUIRED_BEFORE = (
    "operator_approval_receipt",
    "worker_package_boundary_receipt",
    "model_invocation_boundary_receipt",
    "redacted_proof_bundle_receipt",
    "no_external_provider_receipt",
    "no_tool_authority_receipt",
)

RECEIPTS_REQUIRED_DURING = (
    "worker_started_receipt",
    "model_invocation_attempt_receipt",
    "raw_draft_captured_receipt",
    "worker_stopped_receipt",
)

RECEIPTS_REQUIRED_AFTER = (
    "verifier_pass_fail_receipt",
    "published_response_hash_receipt_or_fallback_receipt",
    "no_business_action_receipt",
)

STOP_CONDITIONS = (
    "proof_bundle_contains_forbidden_field",
    "context_freshness_stale_superseded_or_unknown",
    "model_returns_non_json",
    "model_claims_paid_sent_submitted_or_executed",
    "model_promises_protected_action",
    "model_asks_for_hidden_private_context",
    "model_attempts_tool_use",
    "model_exceeds_one_attempt",
    "verifier_fails",
)

OPERATOR_DECISION_OPTIONS = (
    "approve_one_time_lm2_worker_pilot",
    "request_more_detail",
    "reject_for_now",
)

ROOM_BACKED_OPERATOR_DECISION_OPTIONS = (
    "approve_one_time_room_backed_lm2_worker_pilot",
    "request_more_detail",
    "reject_for_now",
)

EXPECTED_RESPONSE = {
    "headline": "Payment evidence needed",
    "body": "Coupa is processing. I can't mark this paid until payment evidence is attached. The ledger stays untouched.",
    "next_step": "Attach payment evidence.",
    "missing_input": ["payment_evidence"],
    "can_do_now": ["explain the payment-watch state", "accept payment evidence"],
    "cannot_do_yet": ["mark paid", "post to the ledger", "submit anything"],
    "claimed_facts": ["payment_evidence_missing", "coupa_processing", "ledger_untouched"],
    "requested_controls": ["Attach payment evidence"],
    "uncertainty_notes": [],
}

ROOM_BACKED_EXPECTED_RESPONSE = {
    "headline": "Payment evidence needed",
    "body": "Coupa is processing. I can't mark this paid until payment evidence is attached. The ledger stays untouched.",
    "next_step": "Attach payment evidence.",
    "missing_input": ["payment_evidence"],
    "can_do_now": ["explain the payment-watch state", "accept payment evidence"],
    "cannot_do_yet": ["mark paid", "post to the ledger", "submit anything"],
    "claimed_facts": ["payment_evidence_missing", "processor_processing", "ledger_untouched", "paid_false"],
    "requested_controls": ["attach_proof"],
    "uncertainty_notes": [],
}

ROOM_BACKED_PACKAGE_REQUIRED_REFS = (
    "project_room_id",
    "source_inventory_ref",
    "conflict_log_ref",
    "missing_context_ref",
    "duplicate_report_ref",
    "decision_trace_ref",
    "freshness_gate_ref",
    "compaction_policy_ref",
    "redacted_proof_bundle_ref",
    "authority_boundary_ref",
    "receipt_requirement_ref",
)

ROOM_BACKED_ALLOWED_WORKER_INPUTS = (
    "redacted_freshness_gated_proof_bundle",
    "current_lane_summary",
    "source_inventory_summary",
    "missing_context_summary",
    "decision_trace_summary",
    "proof_meter_labels",
    "allowed_controls",
    "blocked_action_summaries",
    "required_json_response_schema",
    "one_valid_json_example",
    "stop_conditions",
)

ROOM_BACKED_FORBIDDEN_WORKER_INPUTS = (
    "raw_messy_folder_dump",
    "full_logs_or_artifacts_by_default",
    "raw_financial_proof",
    "bank_or_account_details",
    "credentials_or_tokens",
    "operator_device_session_verification_secrets",
    "raw_prompt_dumps",
    "raw_ocr_or_artifact_text",
    "workbook_email_or_ledger_bodies",
    "hidden_machine_contracts",
    "authority_granted_fields",
    "stale_source_as_current_truth",
    "duplicate_versions_as_equal_evidence",
    "missing_context_as_permission_to_invent",
)

ROOM_BACKED_RECEIPTS_REQUIRED_BEFORE = (
    "operator_approval_receipt",
    "room_backed_package_receipt",
    "project_room_readiness_receipt",
    "worker_package_boundary_receipt",
    "model_invocation_boundary_receipt",
    "redacted_proof_bundle_receipt",
    "no_external_provider_receipt",
    "no_tool_authority_receipt",
)

ROOM_BACKED_RECEIPTS_REQUIRED_AFTER = (
    "worker_started_receipt",
    "model_invocation_attempt_receipt",
    "raw_draft_captured_receipt",
    "worker_stopped_receipt",
    "verifier_pass_fail_receipt",
    "published_response_hash_receipt_or_fallback_receipt",
    "no_business_action_receipt",
)

ROOM_BACKED_STOP_CONDITIONS = (
    "project_room_not_ready",
    "source_inventory_missing",
    "unresolved_critical_conflict",
    "missing_context_blocks_supported_claim",
    "freshness_stale_superseded_or_unknown",
    "proof_bundle_contains_forbidden_field",
    "model_returns_non_json",
    "model_claims_paid_sent_submitted_or_executed",
    "model_promises_protected_action",
    "model_asks_for_hidden_private_context",
    "model_attempts_tool_use",
    "model_exceeds_one_attempt",
    "verifier_fails",
)

AUTHORITY_BOUNDARY = {
    "invocation_allowed": False,
    "worker_spawn_allowed": False,
    "proof_bundle_allowed": False,
    "protected_actions_allowed": False,
    "authority_granted": False,
    "authority_grant_allowed": False,
    "model_invocation_allowed": False,
    "local_model_runtime_contact_allowed": False,
    "external_llm_allowed": False,
    "external_provider_connect_allowed": False,
    "tool_authority": False,
    "tool_authority_allowed": False,
    "tool_execution_allowed": False,
    "business_action_authority": False,
    "business_action_allowed": False,
    "memory_write_authority": False,
    "memory_write_access": False,
    "memory_promotion_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "paid_marking_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "file_system_mutation_allowed": False,
    "shell_command_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
    "repeated_invocations_allowed": False,
}

IMPLEMENTATION_BOUNDARY = {
    "model_invoked": False,
    "ollama_called": False,
    "runtime_connected": False,
    "local_model_runtime_connected": False,
    "prompt_sent": False,
    "proof_bundle_sent": False,
    "worker_spawn_performed": False,
    "tool_execution_performed": False,
    "browser_opened": False,
    "gmail_opened": False,
    "coupa_opened": False,
    "email_send_performed": False,
    "submit_performed": False,
    "ledger_mutation_performed": False,
    "workbook_mutation_performed": False,
    "pdf_export_performed": False,
    "paid_marking_performed": False,
    "memory_promotion_performed": False,
    "external_provider_used": False,
    "external_provider_connected": False,
    "file_system_mutation_performed": False,
    "shell_command_performed": False,
    "git_push_performed": False,
    "merge_performed": False,
    "repeated_invocation_performed": False,
}

UNSAFE_TRUE_KEYS = (
    set(AUTHORITY_BOUNDARY)
    | set(IMPLEMENTATION_BOUNDARY)
    | set(local_model_selection_for_proof_response.UNSAFE_TRUE_KEYS)
    | set(runtime.UNSAFE_TRUE_KEYS)
    | set(schema_adapter.UNSAFE_TRUE_KEYS)
    | {
        "approved",
        "operator_approved",
        "worker_spawned",
        "worker_started",
        "invocation_performed",
        "proof_bundle_visible_to_worker",
        "ready_for_invocation",
        "ready_for_worker_spawn",
        "paid",
        "sent",
        "submitted",
        "executed",
    }
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
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
    return str(payload.get("readiness_status") or payload.get("status") or payload.get("contract_status") or "")


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


def room_backed_precondition_rows(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, spec in ROOM_BACKED_PRECONDITIONS.items():
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


def build_room_backed_package() -> dict[str, Any]:
    return {
        "package_ref": "lm2_room_backed_package:finance_capital_hilton_payment_watch_response:v1",
        "compiled_by_ref": "generated/read_models/project_room_package_compiler_integration.json",
        "worker_class": WORKER_CLASS,
        "runtime": RUNTIME_REF,
        "model": MODEL_NAME,
        "lane": PILOT_LANE,
        "objective": OBJECTIVE_REF,
        "question": QUESTION,
        "mode": MODE,
        "project_room_id": "finance_capital_hilton_payment_watch",
        "source_inventory_ref": "source_inventory:finance_capital_hilton_payment_watch",
        "conflict_log_ref": "conflict_log:finance_capital_hilton_payment_watch",
        "missing_context_ref": "missing_context:finance_payment_evidence",
        "duplicate_report_ref": "version_family:finance_payment_watch",
        "decision_trace_ref": "decision_trace:finance_capital_hilton_payment_watch",
        "freshness_gate_ref": "freshness_gate:receipt_current_or_needs_verification",
        "compaction_policy_ref": "generated/read_models/context_compaction_preview_policy.json",
        "redacted_proof_bundle_ref": "generated/read_models/proof_bundle_freshness_trace_status.json#finance_capital_hilton_payment_watch_redacted",
        "authority_boundary_ref": "lm2_room_backed_worker_pilot_boundary:authority_boundary:v1",
        "receipt_requirement_ref": "lm2_room_backed_worker_pilot_boundary:receipt_requirements:v1",
        "project_room_required": True,
        "project_room_ready_required": True,
        "room_backed_package_required": True,
        "current_proof_bundle_required": True,
        "one_bounded_objective": True,
        "synthesis_allowed": False,
        "invocation_allowed": False,
        "worker_spawn_allowed": False,
        "proof_bundle_allowed": False,
        "current_lane_summary": "Finance / Capital Hilton payment watch. Coupa is processing; payment evidence is missing; paid=false; ledger untouched.",
        "source_inventory_summary": "Use the payment-watch receipt as current proof and generated summaries only as support.",
        "missing_context_summary": "Payment evidence is missing and blocks paid/ledger claims.",
        "decision_trace_summary": "Prior payment-watch lane/gate routing showed that safe text can still be wrong if scoped to the wrong lane.",
        "proof_meter_labels": ["payment_evidence_missing", "processor_processing", "ledger_untouched", "paid_false"],
        "allowed_controls": ["attach_proof"],
        "blocked_action_summaries": ["mark paid", "post to the ledger", "submit anything"],
        "required_json_response_schema": schema_adapter.strict_json_draft_schema(),
        "one_valid_json_example": dict(ROOM_BACKED_EXPECTED_RESPONSE),
        "stop_conditions": list(ROOM_BACKED_STOP_CONDITIONS),
    }


def build_room_backed_worker_input() -> dict[str, Any]:
    return {
        "allowed": list(ROOM_BACKED_ALLOWED_WORKER_INPUTS),
        "forbidden": list(ROOM_BACKED_FORBIDDEN_WORKER_INPUTS),
        "room_backed_package_required": True,
        "loose_proof_bundle_allowed": False,
        "raw_context_allowed": False,
        "required_package_refs": list(ROOM_BACKED_PACKAGE_REQUIRED_REFS),
        "package": build_room_backed_package(),
    }


def room_backed_required_receipt_rows(generated_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for phase, refs in {
        "before_future_invocation": ROOM_BACKED_RECEIPTS_REQUIRED_BEFORE,
        "after_future_invocation": ROOM_BACKED_RECEIPTS_REQUIRED_AFTER,
    }.items():
        for receipt_ref in refs:
            rows.append(
                {
                    "record_id": f"lm2_room_backed_boundary:{phase}:{receipt_ref}",
                    "record_kind": "receipt_requirement",
                    "record_ref": receipt_ref,
                    "phase": phase,
                    "status": "required_future_receipt",
                    "created_at": generated_at,
                    "record_json": stable_json(
                        {
                            "receipt_ref": receipt_ref,
                            "phase": phase,
                            "required_before_invocation": phase == "before_future_invocation",
                            "required_after_invocation": phase == "after_future_invocation",
                        }
                    ),
                }
            )
    return rows


def room_backed_boundary_records(generated_at: str, read_model: Mapping[str, Any]) -> list[dict[str, Any]]:
    records = [
        {
            "record_id": "lm2_room_backed_boundary:package",
            "record_kind": "room_backed_package",
            "record_ref": str((read_model.get("room_backed_package") or {}).get("package_ref") or ""),
            "phase": "boundary",
            "status": "defined_not_invoked",
            "created_at": generated_at,
            "record_json": stable_json(read_model.get("room_backed_package") or {}),
        },
        {
            "record_id": "lm2_room_backed_boundary:worker_input",
            "record_kind": "worker_input_contract",
            "record_ref": "room_backed_worker_input:v1",
            "phase": "boundary",
            "status": "defined_not_sent",
            "created_at": generated_at,
            "record_json": stable_json(read_model.get("worker_package_input") or {}),
        },
        {
            "record_id": "lm2_room_backed_boundary:stop_conditions",
            "record_kind": "stop_conditions",
            "record_ref": "room_backed_stop_conditions:v1",
            "phase": "boundary",
            "status": "defined",
            "created_at": generated_at,
            "record_json": stable_json(read_model.get("stop_conditions") or []),
        },
    ]
    records.extend(room_backed_required_receipt_rows(generated_at))
    return records


def room_backed_sqlite_schema() -> str:
    return """
CREATE TABLE IF NOT EXISTS lm2_room_backed_worker_pilot_boundary_records (
  record_id TEXT PRIMARY KEY,
  record_kind TEXT NOT NULL,
  record_ref TEXT NOT NULL,
  phase TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  record_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lm2_room_backed_boundary_kind ON lm2_room_backed_worker_pilot_boundary_records(record_kind);
CREATE INDEX IF NOT EXISTS idx_lm2_room_backed_boundary_phase ON lm2_room_backed_worker_pilot_boundary_records(phase);
"""


def write_room_backed_sqlite(records: list[Mapping[str, Any]], sqlite_path: Path = ROOM_BACKED_DEFAULT_SQLITE_PATH) -> int:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(room_backed_sqlite_schema())
        conn.execute("DELETE FROM lm2_room_backed_worker_pilot_boundary_records")
        for row in records:
            conn.execute(
                """
INSERT INTO lm2_room_backed_worker_pilot_boundary_records (
  record_id, record_kind, record_ref, phase, status, created_at, record_json
) VALUES (?, ?, ?, ?, ?, ?, ?)
""",
                (
                    str(row.get("record_id") or ""),
                    str(row.get("record_kind") or ""),
                    str(row.get("record_ref") or ""),
                    str(row.get("phase") or ""),
                    str(row.get("status") or ""),
                    str(row.get("created_at") or ""),
                    str(row.get("record_json") or stable_json(row)),
                ),
            )
        conn.commit()
    return len(records)


def required_receipt_rows(generated_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    phase_map = {
        "before": RECEIPTS_REQUIRED_BEFORE,
        "during": RECEIPTS_REQUIRED_DURING,
        "after": RECEIPTS_REQUIRED_AFTER,
    }
    for phase, refs in phase_map.items():
        for receipt_ref in refs:
            rows.append(
                {
                    "receipt_id": f"lm2_worker_boundary:{phase}:{receipt_ref}",
                    "receipt_ref": receipt_ref,
                    "phase": phase,
                    "status": "required_future_receipt",
                    "created_at": generated_at,
                    "proof_summary": f"{receipt_ref} is required in the {phase} phase before a live LM2 worker pilot can complete.",
                }
            )
    return rows


def sqlite_schema() -> str:
    return """
CREATE TABLE IF NOT EXISTS lm2_worker_pilot_boundary_receipts (
  receipt_id TEXT PRIMARY KEY,
  receipt_ref TEXT NOT NULL,
  phase TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  proof_summary TEXT NOT NULL,
  receipt_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lm2_worker_boundary_receipts_phase ON lm2_worker_pilot_boundary_receipts(phase);
"""


def write_sqlite(receipts: list[Mapping[str, Any]], sqlite_path: Path = DEFAULT_SQLITE_PATH) -> int:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(sqlite_schema())
        conn.execute("DELETE FROM lm2_worker_pilot_boundary_receipts")
        for row in receipts:
            conn.execute(
                """
INSERT INTO lm2_worker_pilot_boundary_receipts (
  receipt_id, receipt_ref, phase, status, created_at, proof_summary, receipt_json
) VALUES (?, ?, ?, ?, ?, ?, ?)
""",
                (
                    str(row.get("receipt_id") or ""),
                    str(row.get("receipt_ref") or ""),
                    str(row.get("phase") or ""),
                    str(row.get("status") or ""),
                    str(row.get("created_at") or ""),
                    str(row.get("proof_summary") or ""),
                    stable_json(row),
                ),
            )
        conn.commit()
    return len(receipts)


def build_worker_package_input() -> dict[str, Any]:
    return {
        "allowed": list(ALLOWED_WORKER_INPUTS),
        "forbidden": list(FORBIDDEN_WORKER_INPUTS),
        "proof_bundle_policy": {
            "input_scope": "redacted_freshness_gated_proof_bundle_only",
            "freshness_required": True,
            "decision_trace_required": True,
            "raw_private_detail_allowed": False,
        },
        "required_json_response_schema": schema_adapter.strict_json_draft_schema(),
        "expected_response_example": dict(EXPECTED_RESPONSE),
        "stop_conditions": list(STOP_CONDITIONS),
        "verifier_requirements": [
            "proof_to_response_schema_adapter must parse JSON",
            "proof_to_response_verifier must pass before publication",
            "fallback is mandatory if adapter or verifier fails",
        ],
    }


def build_worker_capabilities() -> dict[str, Any]:
    return {
        "allowed": list(WORKER_CAPABILITIES_ALLOWED),
        "forbidden": list(WORKER_CAPABILITIES_FORBIDDEN),
        "one_attempt_only": True,
        "model_tool_access": False,
        "file_system_mutation_allowed": False,
        "shell_commands_allowed": False,
        "external_provider_allowed": False,
    }


def build_boundary_packet(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    return {
        "packet_id": "lm2_worker_boundary:finance_capital_hilton:qwen3_8b_q4_k_m:v0",
        "status": PACKET_STATUS,
        "generated_at": generated_at,
        "worker_class": WORKER_CLASS,
        "runtime": RUNTIME_REF,
        "runtime_ref": RUNTIME_REF,
        "model": MODEL_NAME,
        "model_ref": MODEL_REF,
        "lane": PILOT_LANE,
        "objective": OBJECTIVE_REF,
        "question": QUESTION,
        "mode": MODE,
        "pilot_scope": {
            "worker_class": WORKER_CLASS,
            "runtime": RUNTIME_REF,
            "model": MODEL_NAME,
            "lane": PILOT_LANE,
            "world_ref": WORLD_REF,
            "thread_ref": THREAD_REF,
            "objective": OBJECTIVE_REF,
            "question": QUESTION,
            "mode": MODE,
            "attempt_limit": 1,
        },
        "invocation_allowed": False,
        "worker_spawn_allowed": False,
        "proof_bundle_allowed": False,
        "worker_package_input": build_worker_package_input(),
        "worker_capabilities": build_worker_capabilities(),
        "required_receipts": {
            "before": list(RECEIPTS_REQUIRED_BEFORE),
            "during": list(RECEIPTS_REQUIRED_DURING),
            "after": list(RECEIPTS_REQUIRED_AFTER),
        },
        "stop_conditions": list(STOP_CONDITIONS),
        "expected_response": dict(EXPECTED_RESPONSE),
        "operator_decision_options": list(OPERATOR_DECISION_OPTIONS),
        "rules": [
            "invocation_allowed=false until explicit operator approval is recorded",
            "worker_spawn_allowed=false until explicit operator approval is recorded",
            "proof_bundle_allowed=false until explicit operator approval is recorded",
            "this packet is not approval",
            "this packet does not run LM2",
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
    }


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    packet = build_boundary_packet(generated_at=generated_at)
    receipts = required_receipt_rows(generated_at)
    sqlite_row_count = write_sqlite(receipts, sqlite_path=sqlite_path)
    preconditions_ready = all(row["ready"] for row in preconditions)
    receipt_count_ok = sqlite_row_count == len(receipts)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready and receipt_count_ok else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Define the review-only boundary packet for one bounded LM2 worker proof-to-response pilot.",
        "boundary_packet": packet,
        "packet_id": packet["packet_id"],
        "packet_status": packet["status"],
        "worker_class": WORKER_CLASS,
        "runtime": RUNTIME_REF,
        "model": MODEL_NAME,
        "lane": PILOT_LANE,
        "objective": OBJECTIVE_REF,
        "question": QUESTION,
        "mode": MODE,
        "invocation_allowed": False,
        "worker_spawn_allowed": False,
        "proof_bundle_allowed": False,
        "required_receipts": packet["required_receipts"],
        "required_receipt_rows": receipts,
        "sqlite_ref": _rooted(sqlite_path).as_posix(),
        "sqlite_row_count": sqlite_row_count,
        "preconditions": preconditions,
        "source_refs": [row["source_ref"] for row in preconditions],
        "operator_decision_options": list(OPERATOR_DECISION_OPTIONS),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
        "machine_proof": {
            "review_only": True,
            "packet_pending_operator_review": packet["status"] == PACKET_STATUS,
            "preconditions_ready": preconditions_ready,
            "invocation_allowed": False,
            "worker_spawn_allowed": False,
            "proof_bundle_allowed": False,
            "tool_authority": False,
            "business_action_authority": False,
            "external_provider_used": False,
            "model_invoked": False,
            "worker_spawn_performed": False,
            "prompt_sent": False,
            "proof_bundle_sent": False,
            "sqlite_row_count_matches_receipts": receipt_count_ok,
        },
        "source_content_hashes": {
            "preconditions": _content_hash(preconditions),
            "boundary_packet": _content_hash(packet),
            "required_receipt_rows": _content_hash(receipts),
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    payload["content_hash"] = _content_hash({key: value for key, value in payload.items() if key != "content_hash"})
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    packet = read_model.get("boundary_packet") if isinstance(read_model.get("boundary_packet"), Mapping) else {}
    lines = [
        "# LM2 Live Worker Pilot Boundary Packet",
        "",
        f"Status: {read_model.get('status')}",
        f"Packet status: {packet.get('status')}",
        "",
        "This is review-only. It does not spawn a worker, invoke a model, send a prompt, send a proof bundle, or grant authority.",
        "",
        "## Pilot Scope",
        "",
        f"- Worker class: `{packet.get('worker_class')}`",
        f"- Runtime: `{packet.get('runtime')}`",
        f"- Model: `{packet.get('model')}`",
        f"- Lane: `{packet.get('lane')}`",
        f"- Objective: `{packet.get('objective')}`",
        f"- Question: {packet.get('question')}",
        f"- Mode: `{packet.get('mode')}`",
        "",
        "## Authority",
        "",
        f"- Invocation allowed: `{str(packet.get('invocation_allowed')).lower()}`",
        f"- Worker spawn allowed: `{str(packet.get('worker_spawn_allowed')).lower()}`",
        f"- Proof bundle allowed: `{str(packet.get('proof_bundle_allowed')).lower()}`",
        "",
        "## Allowed Worker Input",
        "",
    ]
    worker_input = packet.get("worker_package_input") if isinstance(packet.get("worker_package_input"), Mapping) else {}
    for item in worker_input.get("allowed") or []:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Forbidden Worker Input", ""])
    for item in worker_input.get("forbidden") or []:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Worker Capabilities", ""])
    capabilities = packet.get("worker_capabilities") if isinstance(packet.get("worker_capabilities"), Mapping) else {}
    lines.append("Allowed:")
    for item in capabilities.get("allowed") or []:
        lines.append(f"- `{item}`")
    lines.append("")
    lines.append("Forbidden:")
    for item in capabilities.get("forbidden") or []:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Stop Conditions", ""])
    for item in packet.get("stop_conditions") or []:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Operator Decision Options", ""])
    for item in packet.get("operator_decision_options") or []:
        lines.append(f"- `{item}`")
    lines.append("")
    return "\n".join(lines)


def export_lm2_live_worker_pilot_boundary_packet(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(read_model_root=read_model_root, sqlite_path=sqlite_path, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    _write_json(read_model_path, read_model)

    bridge_read_model_path = ""
    if bridge_root is not None:
        bridge_root = _rooted(bridge_root)
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_path = bridge_root / JSON_EXPORT_NAME
        shutil.copy2(read_model_path, bridge_path)
        bridge_read_model_path = bridge_path.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model.get("status") or NOT_READY_STATUS),
        "packet_status": str(read_model.get("packet_status") or ""),
        "worker_class": str(read_model.get("worker_class") or ""),
        "lane": str(read_model.get("lane") or ""),
        "invocation_allowed": str(read_model.get("invocation_allowed")).lower(),
        "worker_spawn_allowed": str(read_model.get("worker_spawn_allowed")).lower(),
        "proof_bundle_allowed": str(read_model.get("proof_bundle_allowed")).lower(),
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_read_model_path,
        "wiki_path": wiki_path.as_posix(),
        "sqlite_path": _rooted(sqlite_path).as_posix(),
        "sqlite_row_count": str(read_model.get("sqlite_row_count") or 0),
    }


def build_room_backed_wiki(read_model: Mapping[str, Any]) -> str:
    package = read_model.get("room_backed_package") if isinstance(read_model.get("room_backed_package"), Mapping) else {}
    worker_input = read_model.get("worker_package_input") if isinstance(read_model.get("worker_package_input"), Mapping) else {}
    lines = [
        "# LM2 Room Backed Worker Pilot Boundary",
        "",
        f"Status: {read_model.get('status')}",
        "",
        "This is boundary/read-model work only. It requires a room-backed worker package before any future LM2 pilot and does not invoke LM2, connect Ollama, spawn a worker, send a prompt, or send a proof bundle.",
        "",
        "## Pilot Scope",
        "",
        f"- Worker class: `{read_model.get('worker_class')}`",
        f"- Runtime: `{read_model.get('runtime')}`",
        f"- Model: `{read_model.get('model')}`",
        f"- Lane: `{read_model.get('lane')}`",
        f"- Objective: `{read_model.get('objective')}`",
        f"- Question: {read_model.get('question')}",
        f"- Mode: `{read_model.get('mode')}`",
        "",
        "## Required Package Refs",
        "",
    ]
    for ref in ROOM_BACKED_PACKAGE_REQUIRED_REFS:
        lines.append(f"- `{ref}`: `{package.get(ref)}`")
    lines.extend(["", "## Allowed Worker Input", ""])
    for item in worker_input.get("allowed") or []:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Forbidden Worker Input", ""])
    for item in worker_input.get("forbidden") or []:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Stop Conditions", ""])
    for item in read_model.get("stop_conditions") or []:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Rules", ""])
    for item in read_model.get("rules") or []:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_room_backed_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_path: Path = ROOM_BACKED_DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = room_backed_precondition_rows(read_model_root)
    package = build_room_backed_package()
    worker_input = build_room_backed_worker_input()
    required_refs_present = all(str(package.get(ref) or "") for ref in ROOM_BACKED_PACKAGE_REQUIRED_REFS)
    allowed_input_set = set(worker_input["allowed"])
    forbidden_input_set = set(worker_input["forbidden"])
    stop_condition_set = set(ROOM_BACKED_STOP_CONDITIONS)
    required_stop_conditions = {
        "project_room_not_ready",
        "source_inventory_missing",
        "unresolved_critical_conflict",
        "missing_context_blocks_supported_claim",
        "freshness_stale_superseded_or_unknown",
        "model_returns_non_json",
        "model_claims_paid_sent_submitted_or_executed",
        "model_promises_protected_action",
        "model_attempts_tool_use",
        "model_exceeds_one_attempt",
        "verifier_fails",
    }
    payload: dict[str, Any] = {
        "schema_version": ROOM_BACKED_SCHEMA_VERSION,
        "read_model_id": ROOM_BACKED_READ_MODEL_ID,
        "status": ROOM_BACKED_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Revise the LM2 live worker pilot boundary so any future LM2 worker receives a room-backed package, not a loose proof bundle or messy context.",
        "worker_class": WORKER_CLASS,
        "runtime": RUNTIME_REF,
        "model": MODEL_NAME,
        "lane": PILOT_LANE,
        "world_ref": WORLD_REF,
        "thread_ref": THREAD_REF,
        "objective": OBJECTIVE_REF,
        "question": QUESTION,
        "mode": MODE,
        "room_backed_package_required": True,
        "project_room_ready_required": True,
        "invocation_allowed": False,
        "worker_spawn_allowed": False,
        "proof_bundle_allowed": False,
        "packet_status": PACKET_STATUS,
        "room_backed_package": package,
        "worker_package_input": worker_input,
        "allowed_worker_inputs": list(ROOM_BACKED_ALLOWED_WORKER_INPUTS),
        "forbidden_worker_inputs": list(ROOM_BACKED_FORBIDDEN_WORKER_INPUTS),
        "worker_capabilities": build_worker_capabilities(),
        "required_receipts": {
            "before_future_invocation": list(ROOM_BACKED_RECEIPTS_REQUIRED_BEFORE),
            "after_future_invocation": list(ROOM_BACKED_RECEIPTS_REQUIRED_AFTER),
        },
        "stop_conditions": list(ROOM_BACKED_STOP_CONDITIONS),
        "expected_response_target": dict(ROOM_BACKED_EXPECTED_RESPONSE),
        "operator_decision_options": list(ROOM_BACKED_OPERATOR_DECISION_OPTIONS),
        "rules": [
            "invocation_allowed=false",
            "worker_spawn_allowed=false",
            "proof_bundle_allowed=false",
            "room_backed_package_required=true",
            "project_room_ready_required=true",
            "this packet is not approval",
            "this packet does not run LM2",
        ],
        "preconditions": preconditions,
        "source_refs": [row["source_ref"] for row in preconditions],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
    }
    records = room_backed_boundary_records(generated_at, payload)
    sqlite_row_count = write_room_backed_sqlite(records, sqlite_path=sqlite_path)
    receipt_count_ok = sqlite_row_count == len(records)
    preconditions_ready = all(row["ready"] for row in preconditions)
    payload["sqlite_ref"] = _rooted(sqlite_path).as_posix()
    payload["sqlite_row_count"] = sqlite_row_count
    payload["sqlite_expected_row_count"] = len(records)
    payload["machine_proof"] = {
        "boundary_read_model_only": True,
        "preconditions_ready": preconditions_ready,
        "room_backed_package_required": True,
        "project_room_ready_required": True,
        "required_package_refs_present": required_refs_present,
        "allowed_inputs_match_contract": allowed_input_set == set(ROOM_BACKED_ALLOWED_WORKER_INPUTS),
        "forbidden_inputs_match_contract": forbidden_input_set == set(ROOM_BACKED_FORBIDDEN_WORKER_INPUTS),
        "allowed_forbidden_inputs_disjoint": allowed_input_set.isdisjoint(forbidden_input_set),
        "stop_conditions_complete": required_stop_conditions <= stop_condition_set,
        "expected_response_target_present": payload["expected_response_target"] == ROOM_BACKED_EXPECTED_RESPONSE,
        "invocation_disallowed": payload["invocation_allowed"] is False,
        "worker_spawn_disallowed": payload["worker_spawn_allowed"] is False,
        "loose_proof_bundle_disallowed": payload["proof_bundle_allowed"] is False,
        "tool_authority_false": payload["authority_boundary"]["tool_authority"] is False,
        "business_action_authority_false": payload["authority_boundary"]["business_action_authority"] is False,
        "model_invocation_absent": payload["implementation_boundary"]["model_invoked"] is False,
        "worker_spawn_absent": payload["implementation_boundary"]["worker_spawn_performed"] is False,
        "prompt_send_absent": payload["implementation_boundary"]["prompt_sent"] is False,
        "proof_bundle_send_absent": payload["implementation_boundary"]["proof_bundle_sent"] is False,
        "sqlite_row_count_matches_records": receipt_count_ok,
        "unsafe_true_grants_absent": True,
    }
    if not all(value is True for value in payload["machine_proof"].values()):
        payload["status"] = ROOM_BACKED_NOT_READY_STATUS
    unsafe = unsafe_true_grants(payload)
    payload["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = ROOM_BACKED_NOT_READY_STATUS
    payload["source_content_hashes"] = {
        "preconditions": _content_hash(preconditions),
        "room_backed_package": _content_hash(package),
        "worker_package_input": _content_hash(worker_input),
        "records": _content_hash(records),
    }
    payload["content_hash"] = _content_hash({key: value for key, value in payload.items() if key != "content_hash"})
    return payload


def export_lm2_room_backed_worker_pilot_boundary(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = ROOM_BACKED_DEFAULT_WIKI_PATH,
    sqlite_path: Path = ROOM_BACKED_DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_room_backed_read_model(
        read_model_root=read_model_root,
        sqlite_path=sqlite_path,
        generated_at=generated_at,
    )
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / ROOM_BACKED_JSON_EXPORT_NAME
    _write_json(read_model_path, read_model)

    bridge_read_model_path = ""
    if bridge_root is not None:
        bridge_root = _rooted(bridge_root)
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_path = bridge_root / ROOM_BACKED_JSON_EXPORT_NAME
        shutil.copy2(read_model_path, bridge_path)
        bridge_read_model_path = bridge_path.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_room_backed_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model.get("status") or ROOM_BACKED_NOT_READY_STATUS),
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_read_model_path,
        "wiki_path": wiki_path.as_posix(),
        "sqlite_path": _rooted(sqlite_path).as_posix(),
        "sqlite_row_count": str(read_model.get("sqlite_row_count") or 0),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish LM2 Live Worker Pilot Boundary Packet V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--generated-at")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    bridge_root = Path(args.bridge_root) if args.bridge_root else None
    result = export_lm2_live_worker_pilot_boundary_packet(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=bridge_root,
        wiki_path=Path(args.wiki_path),
        sqlite_path=Path(args.sqlite_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
