"""Universal Receipt Envelope V0.

Defines one safe receipt shape for controller events, packages, evidence,
review decisions, approval queues, dynamic cards, memory gates, workflow plans,
and future worker result rails. The envelope records what happened and what did
not happen; it does not execute business actions or grant authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Universal Receipt Envelope.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/universal_receipts.sqlite")

SCHEMA_VERSION = "universal_receipt_envelope_v0"
CONTRACT_READ_MODEL_ID = "universal_receipt_envelope_contract"
STATUS_READ_MODEL_ID = "universal_receipt_envelope_status"
CONTRACT_JSON_EXPORT_NAME = f"{CONTRACT_READ_MODEL_ID}.json"
STATUS_JSON_EXPORT_NAME = f"{STATUS_READ_MODEL_ID}.json"
READY_STATUS = "UNIVERSAL_RECEIPT_ENVELOPE_READY"
NOT_READY_STATUS = "UNIVERSAL_RECEIPT_ENVELOPE_NOT_READY"

RECEIPT_TYPES = (
    "controller_event_received",
    "evidence_recorded",
    "package_staged",
    "package_rejected",
    "review_decision_recorded",
    "approval_recorded",
    "gate_blocked",
    "dynamic_card_emitted",
    "memory_candidate_recorded",
    "workflow_plan_staged",
    "worker_result_recorded_future",
)

REQUIRED_RECEIPT_FIELDS = (
    "receipt_id",
    "receipt_type",
    "created_at",
    "source_request_id",
    "controller_event_id",
    "operator_envelope_ref",
    "package_id",
    "card_id",
    "world_ref",
    "thread_ref",
    "client_ref",
    "workflow_ref",
    "actor_ref",
    "agent_character",
    "action_taken",
    "action_not_taken",
    "authority_requested",
    "authority_granted",
    "authority_denied",
    "proof_refs",
    "artifact_refs",
    "hash_refs",
    "sqlite_refs",
    "read_model_refs",
    "validation_refs",
    "result_status",
    "business_action_performed",
    "paid_marking_performed",
    "ledger_mutation_performed",
    "email_send_performed",
    "coupa_submit_performed",
    "workbook_mutation_performed",
    "pdf_export_performed",
    "next_safe_action",
)

LIST_FIELDS = (
    "action_not_taken",
    "authority_requested",
    "authority_granted",
    "authority_denied",
    "proof_refs",
    "artifact_refs",
    "hash_refs",
    "sqlite_refs",
    "read_model_refs",
    "validation_refs",
)

FALSE_OPERATION_FIELDS = (
    "business_action_performed",
    "paid_marking_performed",
    "ledger_mutation_performed",
    "email_send_performed",
    "coupa_submit_performed",
    "workbook_mutation_performed",
    "pdf_export_performed",
    "merge_performed",
    "git_push_performed",
    "worker_spawn_performed",
    "worker_run_performed",
    "submit_performed",
    "gmail_access_performed",
    "browser_access_performed",
    "external_llm_invoked",
    "external_provider_connected",
    "workbook_body_read_performed",
)

UNSAFE_TRUE_KEYS = set(FALSE_OPERATION_FIELDS) | {
    "authority_granted",
    "authority_grant_allowed",
    "business_action_allowed",
    "paid",
    "paid_marking_allowed",
    "ledger_mutation_allowed",
    "ledger_posting_allowed",
    "email_send_allowed",
    "coupa_allowed",
    "portal_submit_allowed",
    "workbook_mutation_allowed",
    "pdf_export_allowed",
    "git_push_allowed",
    "worker_spawn_allowed",
    "external_action_allowed",
    "incoming_authority_granted_accepted",
    "approval_is_execution_proof",
    "evidence_is_paid_truth",
    "lm_output_is_receipt_truth",
}

AUTHORITY_BOUNDARY = {
    "authority_grant_allowed": False,
    "business_action_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "ledger_posting_allowed": False,
    "paid": False,
    "paid_marking_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "git_push_allowed": False,
    "worker_spawn_allowed": False,
    "external_action_allowed": False,
}

PRECONDITIONS = {
    "operator_controller_event_live_route": {
        "filename": "operator_controller_event_router_status.json",
        "accepted_statuses": ["OPERATOR_CONTROLLER_EVENT_LIVE_ROUTE_READY", "OPERATOR_CONTROLLER_EVENT_ROUTER_READY"],
    },
    "dynamic_card_packet_v1": {
        "filename": "dynamic_card_packet_latest.json",
        "accepted_statuses": ["DYNAMIC_CARD_PACKET_V1_READY", "DYNAMIC_CARD_PACKET_READY"],
    },
    "verified_evidence_intake": {
        "filename": "evidence_intake_status.json",
        "accepted_statuses": ["VERIFIED_EVIDENCE_INTAKE_READY", "EVIDENCE_INTAKE_LIVE_ROUTE_READY", "EVIDENCE_INTAKE_READY"],
    },
    "workroom_review_decision_consumer": {
        "filename": "workroom_review_decision_status.json",
        "accepted_statuses": ["WORKROOM_REVIEW_DECISION_CONSUMER_READY"],
    },
    "gate_decision_ledger": {
        "filename": "gate_decision_ledger.json",
        "accepted_statuses": ["GATE_DECISION_LEDGER_READY"],
    },
    "approval_request_queue": {
        "filename": "approval_request_queue.json",
        "accepted_statuses": ["APPROVAL_REQUEST_QUEUE_READY"],
    },
}

EXAMPLE_RECEIPT_SPECS = (
    {
        "receipt_type": "controller_event_received",
        "source_request_id": "controller_event:ask_why:capital_hilton",
        "controller_event_id": "controller_event:ask_why:capital_hilton",
        "card_id": "dynamic_card.finance.capital_hilton.payment_watch",
        "world_ref": "finance",
        "thread_ref": "capital_hilton",
        "workflow_ref": "operator_controller_event_router",
        "actor_ref": "openclaw",
        "agent_character": "Chief",
        "action_taken": "Verified controller event was accepted for safe routing.",
        "action_not_taken": ["No package dispatch.", "No business execution.", "No external provider action."],
        "authority_requested": [],
        "proof_refs": ["generated/read_models/operator_controller_event_router_status.json"],
        "read_model_refs": ["generated/read_models/operator_controller_event_router_status.json"],
        "result_status": "received",
        "next_safe_action": "Route only to a safe backend read-model or details action.",
    },
    {
        "receipt_type": "evidence_recorded",
        "source_request_id": "evidence_intake:live_arts_md:payment_processing",
        "controller_event_id": "controller_event:attach_proof:live_arts_md",
        "world_ref": "finance",
        "thread_ref": "live_arts_md",
        "client_ref": "live_arts_md",
        "workflow_ref": "evidence_intake",
        "actor_ref": "guardian",
        "agent_character": "Guardian",
        "action_taken": "Payment-processing evidence candidate was recorded locally.",
        "action_not_taken": ["No ledger mutation.", "No paid marking.", "No payment truth inferred from operator report."],
        "authority_requested": ["record_evidence_candidate", "mark_paid"],
        "proof_refs": ["generated/read_models/evidence_intake_status.json"],
        "sqlite_refs": ["generated/system_knowledge/evidence_intake.sqlite"],
        "read_model_refs": ["generated/read_models/evidence_intake_status.json"],
        "result_status": "evidence_recorded",
        "next_safe_action": "Wait for payment or ledger evidence before any paid or ledger state changes.",
    },
    {
        "receipt_type": "package_staged",
        "source_request_id": "workflow_package:capital_hilton_follow_up",
        "package_id": "workflow_package:capital_hilton_follow_up",
        "world_ref": "business_development",
        "thread_ref": "capital_hilton",
        "workflow_ref": "workflow_package_request_consumer",
        "actor_ref": "cassandra",
        "agent_character": "Cassandra",
        "action_taken": "Workflow package was staged for review-only handling.",
        "action_not_taken": ["No email sent.", "No CRM or portal update.", "No business execution."],
        "authority_requested": ["stage_package"],
        "proof_refs": ["generated/read_models/workflow_package_request_consumer_status.json"],
        "sqlite_refs": ["generated/system_knowledge/workflow_package_queue.sqlite"],
        "read_model_refs": ["generated/read_models/workflow_package_request_consumer_status.json"],
        "result_status": "staged",
        "next_safe_action": "Show the staged package and wait for operator review.",
    },
    {
        "receipt_type": "package_rejected",
        "source_request_id": "workflow_package:protected_send_without_gate",
        "world_ref": "business_development",
        "thread_ref": "capital_hilton",
        "workflow_ref": "workflow_package_request_consumer",
        "actor_ref": "guardian",
        "agent_character": "Guardian",
        "action_taken": "Protected package request was rejected because execution authority was missing.",
        "action_not_taken": ["No send.", "No submit.", "No external provider action."],
        "authority_requested": ["send_email"],
        "proof_refs": ["generated/read_models/gate_decision_ledger.json"],
        "read_model_refs": ["generated/read_models/gate_decision_ledger.json"],
        "result_status": "rejected",
        "next_safe_action": "Stage approval or rework request instead of executing.",
    },
    {
        "receipt_type": "review_decision_recorded",
        "source_request_id": "workroom_review:mark_informational",
        "package_id": "review_packet:build_dynamic_card_v1_rails",
        "world_ref": "build",
        "thread_ref": "workroom_review",
        "workflow_ref": "workroom_review_decision_consumer",
        "actor_ref": "chief",
        "agent_character": "Chief",
        "action_taken": "Review decision was recorded as informational.",
        "action_not_taken": ["No merge.", "No git push.", "No worker spawn.", "No business execution."],
        "authority_requested": ["record_review_decision"],
        "proof_refs": ["generated/read_models/workroom_review_decision_status.json"],
        "read_model_refs": ["generated/read_models/workroom_review_decision_status.json"],
        "result_status": "decision_recorded",
        "next_safe_action": "Keep the receipt as history; any build work requires a separate task.",
    },
    {
        "receipt_type": "approval_recorded",
        "source_request_id": "approval_request:coupa_submit",
        "world_ref": "finance",
        "thread_ref": "capital_hilton",
        "workflow_ref": "approval_request_queue",
        "actor_ref": "guardian",
        "agent_character": "Guardian",
        "action_taken": "Approval need was recorded in the queue.",
        "action_not_taken": ["No Coupa submit.", "No portal access.", "No business execution."],
        "authority_requested": ["coupa_submit"],
        "proof_refs": ["generated/read_models/approval_request_queue.json"],
        "sqlite_refs": ["generated/system_knowledge/approval_request_queue.sqlite"],
        "read_model_refs": ["generated/read_models/approval_request_queue.json"],
        "result_status": "approval_recorded_not_executed",
        "next_safe_action": "Wait for a separate explicit executor gate before any protected action.",
    },
    {
        "receipt_type": "gate_blocked",
        "source_request_id": "gate_decision:mark_paid",
        "world_ref": "finance",
        "thread_ref": "capital_hilton",
        "workflow_ref": "gate_decision_ledger",
        "actor_ref": "guardian",
        "agent_character": "Guardian",
        "action_taken": "Protected paid/ledger gate was blocked.",
        "action_not_taken": ["No paid marking.", "No ledger mutation.", "No authority granted."],
        "authority_requested": ["mark_paid", "ledger_post"],
        "proof_refs": ["generated/read_models/gate_decision_ledger.json"],
        "sqlite_refs": ["generated/system_knowledge/gate_decision_ledger.sqlite"],
        "read_model_refs": ["generated/read_models/gate_decision_ledger.json"],
        "result_status": "blocked",
        "next_safe_action": "Require payment or ledger evidence before any protected finance state change.",
    },
    {
        "receipt_type": "dynamic_card_emitted",
        "source_request_id": "dynamic_card_packet:latest",
        "card_id": "dynamic_card.finance.capital_hilton.payment_watch",
        "world_ref": "finance",
        "thread_ref": "capital_hilton",
        "workflow_ref": "dynamic_card_packet",
        "actor_ref": "openclaw",
        "agent_character": "Chief",
        "action_taken": "Receipt-backed dynamic card was emitted for Mission Control.",
        "action_not_taken": ["No business execution.", "No source truth changed.", "No client-specific hardcoding required."],
        "authority_requested": ["render_card"],
        "proof_refs": ["generated/read_models/dynamic_card_packet_latest.json"],
        "hash_refs": ["sha256:dynamic_card_packet_latest:capital_hilton_payment_watch"],
        "read_model_refs": ["generated/read_models/dynamic_card_packet_latest.json"],
        "result_status": "card_emitted",
        "next_safe_action": "Render the card and open proof details on request.",
    },
    {
        "receipt_type": "memory_candidate_recorded",
        "source_request_id": "memory_promotion_gate:payment_evidence_candidate",
        "world_ref": "memory",
        "thread_ref": "promotion_gate",
        "workflow_ref": "memory_promotion_gate",
        "actor_ref": "guardian",
        "agent_character": "Guardian",
        "action_taken": "Memory candidate was recorded for review.",
        "action_not_taken": ["No canonical memory promotion.", "No proof elevation.", "No business execution."],
        "authority_requested": ["record_memory_candidate"],
        "proof_refs": ["generated/read_models/memory_promotion_gate.json"],
        "read_model_refs": ["generated/read_models/memory_promotion_gate.json"],
        "result_status": "candidate_recorded",
        "next_safe_action": "Show candidate for operator review; promote only after a later promotion receipt.",
    },
    {
        "receipt_type": "workflow_plan_staged",
        "source_request_id": "workflow_composer:capital_hilton_follow_up",
        "world_ref": "business_development",
        "thread_ref": "capital_hilton",
        "workflow_ref": "workflow_composer",
        "actor_ref": "cassandra",
        "agent_character": "Cassandra",
        "action_taken": "Workflow plan was staged as a deterministic proposal.",
        "action_not_taken": ["No email sent.", "No submit.", "No worker run."],
        "authority_requested": ["stage_plan"],
        "proof_refs": ["generated/read_models/workflow_composer_latest.json"],
        "read_model_refs": ["generated/read_models/workflow_composer_latest.json"],
        "result_status": "plan_staged",
        "next_safe_action": "Review the plan and choose a safe controller event.",
    },
    {
        "receipt_type": "worker_result_recorded_future",
        "source_request_id": "future_worker_result:placeholder",
        "world_ref": "build",
        "thread_ref": "future_worker_results",
        "workflow_ref": "worker_result_future",
        "actor_ref": "codex",
        "agent_character": "Codex",
        "action_taken": "Future worker result receipt shape is reserved.",
        "action_not_taken": ["No worker run.", "No child agent run.", "No authority inherited from speaker."],
        "authority_requested": ["record_future_worker_result"],
        "proof_refs": ["generated/read_models/universal_receipt_envelope_contract.json"],
        "read_model_refs": ["generated/read_models/universal_receipt_envelope_contract.json"],
        "result_status": "future_shape_reserved",
        "next_safe_action": "Use this shape only after a future explicit worker gate records a result.",
    },
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
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


def _short_hash(payload: Any) -> str:
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()[:16]


def _string_list(values: Iterable[Any] | None) -> list[str]:
    if values is None:
        return []
    return list(dict.fromkeys(str(value) for value in values if str(value)))


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


def build_receipt(
    receipt_type: str,
    *,
    created_at: str | None = None,
    source_request_id: str,
    controller_event_id: str = "",
    operator_envelope_ref: str = "",
    package_id: str = "",
    card_id: str = "",
    world_ref: str,
    thread_ref: str,
    client_ref: str = "",
    workflow_ref: str = "",
    actor_ref: str = "",
    agent_character: str = "",
    action_taken: str,
    action_not_taken: Iterable[Any] | None = None,
    authority_requested: Iterable[Any] | None = None,
    incoming_authority_granted: Iterable[Any] | None = None,
    proof_refs: Iterable[Any] | None = None,
    artifact_refs: Iterable[Any] | None = None,
    hash_refs: Iterable[Any] | None = None,
    sqlite_refs: Iterable[Any] | None = None,
    read_model_refs: Iterable[Any] | None = None,
    validation_refs: Iterable[Any] | None = None,
    result_status: str,
    next_safe_action: str,
) -> dict[str, Any]:
    if receipt_type not in RECEIPT_TYPES:
        raise ValueError(f"unknown receipt type: {receipt_type}")
    created_at = created_at or utc_now()
    requested = _string_list(authority_requested)
    incoming_granted = _string_list(incoming_authority_granted)
    seed = {
        "receipt_type": receipt_type,
        "created_at": created_at,
        "source_request_id": source_request_id,
        "controller_event_id": controller_event_id,
        "package_id": package_id,
        "card_id": card_id,
        "world_ref": world_ref,
        "thread_ref": thread_ref,
        "workflow_ref": workflow_ref,
        "result_status": result_status,
    }
    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": f"universal_receipt:{receipt_type}:{_short_hash(seed)}",
        "receipt_type": receipt_type,
        "created_at": created_at,
        "source_request_id": source_request_id,
        "controller_event_id": controller_event_id,
        "operator_envelope_ref": operator_envelope_ref,
        "package_id": package_id,
        "card_id": card_id,
        "world_ref": world_ref,
        "thread_ref": thread_ref,
        "client_ref": client_ref,
        "workflow_ref": workflow_ref,
        "actor_ref": actor_ref,
        "agent_character": agent_character,
        "action_taken": action_taken,
        "action_not_taken": _string_list(action_not_taken),
        "authority_requested": requested,
        "authority_granted": [],
        "authority_denied": requested,
        "proof_refs": _string_list(proof_refs),
        "artifact_refs": _string_list(artifact_refs),
        "hash_refs": _string_list(hash_refs),
        "sqlite_refs": _string_list(sqlite_refs),
        "read_model_refs": _string_list(read_model_refs),
        "validation_refs": _string_list(validation_refs),
        "result_status": result_status,
        "business_action_performed": False,
        "paid_marking_performed": False,
        "ledger_mutation_performed": False,
        "email_send_performed": False,
        "coupa_submit_performed": False,
        "workbook_mutation_performed": False,
        "pdf_export_performed": False,
        "merge_performed": False,
        "git_push_performed": False,
        "worker_spawn_performed": False,
        "worker_run_performed": False,
        "submit_performed": False,
        "gmail_access_performed": False,
        "browser_access_performed": False,
        "external_llm_invoked": False,
        "external_provider_connected": False,
        "workbook_body_read_performed": False,
        "next_safe_action": next_safe_action,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "receipt_records_what_happened_and_not_happened": True,
            "incoming_authority_granted_accepted": False,
            "incoming_authority_granted_ignored": bool(incoming_granted),
            "incoming_authority_granted_values": incoming_granted,
            "approval_is_execution_proof": False,
            "evidence_is_paid_truth": False,
            "lm_output_is_receipt_truth": False,
            "business_action_receipt_requires_future_executor_gate": True,
            "no_business_action_receipt_type_available": True,
        },
    }
    receipt["receipt_content_hash"] = _content_hash(receipt)
    receipt["validation"] = validate_receipt(receipt)
    return receipt


def validate_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    for field in REQUIRED_RECEIPT_FIELDS:
        if field not in receipt:
            errors.append(f"missing_field:{field}")
    receipt_type = str(receipt.get("receipt_type") or "")
    if receipt_type not in RECEIPT_TYPES:
        errors.append(f"unknown_receipt_type:{receipt_type}")
    for field in LIST_FIELDS:
        if not isinstance(receipt.get(field), list):
            errors.append(f"list_field_required:{field}")
    if receipt.get("authority_granted") not in ([], None):
        errors.append("authority_granted_must_be_empty")
    for field in FALSE_OPERATION_FIELDS:
        if receipt.get(field) is not False:
            errors.append(f"operation_field_must_be_false:{field}")
    unsafe = unsafe_true_grants(receipt)
    if unsafe:
        errors.extend(f"unsafe_true_grant:{key}" for key in unsafe)
    return {
        "valid": not errors,
        "errors": errors,
        "unsafe_true_grants": unsafe,
        "unsafe_true_grants_absent": not unsafe,
    }


def _preconditions(read_model_root: Path) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, contract in PRECONDITIONS.items():
        filename = str(contract["filename"])
        payload = _load_json(root / filename)
        observed = str(payload.get("status") or payload.get("contract_status") or "")
        accepted = [str(status) for status in contract["accepted_statuses"]]
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


def build_example_receipts(*, generated_at: str | None = None) -> list[dict[str, Any]]:
    created_at = generated_at or utc_now()
    return [
        build_receipt(
            str(spec["receipt_type"]),
            created_at=created_at,
            source_request_id=str(spec["source_request_id"]),
            controller_event_id=str(spec.get("controller_event_id") or ""),
            package_id=str(spec.get("package_id") or ""),
            card_id=str(spec.get("card_id") or ""),
            world_ref=str(spec["world_ref"]),
            thread_ref=str(spec["thread_ref"]),
            client_ref=str(spec.get("client_ref") or ""),
            workflow_ref=str(spec.get("workflow_ref") or ""),
            actor_ref=str(spec.get("actor_ref") or ""),
            agent_character=str(spec.get("agent_character") or ""),
            action_taken=str(spec["action_taken"]),
            action_not_taken=spec.get("action_not_taken") or [],
            authority_requested=spec.get("authority_requested") or [],
            incoming_authority_granted=spec.get("incoming_authority_granted") or [],
            proof_refs=spec.get("proof_refs") or [],
            artifact_refs=spec.get("artifact_refs") or [],
            hash_refs=spec.get("hash_refs") or [],
            sqlite_refs=spec.get("sqlite_refs") or [],
            read_model_refs=spec.get("read_model_refs") or [],
            validation_refs=spec.get("validation_refs") or [],
            result_status=str(spec["result_status"]),
            next_safe_action=str(spec["next_safe_action"]),
        )
        for spec in EXAMPLE_RECEIPT_SPECS
    ]


def _write_sqlite(sqlite_path: Path, receipts: list[Mapping[str, Any]]) -> int:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.execute("DROP TABLE IF EXISTS universal_receipts")
        conn.execute(
            """
            CREATE TABLE universal_receipts (
              receipt_id TEXT PRIMARY KEY,
              receipt_type TEXT NOT NULL,
              created_at TEXT NOT NULL,
              source_request_id TEXT NOT NULL,
              controller_event_id TEXT NOT NULL,
              operator_envelope_ref TEXT NOT NULL,
              package_id TEXT NOT NULL,
              card_id TEXT NOT NULL,
              world_ref TEXT NOT NULL,
              thread_ref TEXT NOT NULL,
              client_ref TEXT NOT NULL,
              workflow_ref TEXT NOT NULL,
              actor_ref TEXT NOT NULL,
              agent_character TEXT NOT NULL,
              action_taken TEXT NOT NULL,
              action_not_taken_json TEXT NOT NULL,
              authority_requested_json TEXT NOT NULL,
              authority_granted_json TEXT NOT NULL,
              authority_denied_json TEXT NOT NULL,
              proof_refs_json TEXT NOT NULL,
              artifact_refs_json TEXT NOT NULL,
              hash_refs_json TEXT NOT NULL,
              sqlite_refs_json TEXT NOT NULL,
              read_model_refs_json TEXT NOT NULL,
              validation_refs_json TEXT NOT NULL,
              result_status TEXT NOT NULL,
              business_action_performed INTEGER NOT NULL,
              paid_marking_performed INTEGER NOT NULL,
              ledger_mutation_performed INTEGER NOT NULL,
              email_send_performed INTEGER NOT NULL,
              coupa_submit_performed INTEGER NOT NULL,
              workbook_mutation_performed INTEGER NOT NULL,
              pdf_export_performed INTEGER NOT NULL,
              merge_performed INTEGER NOT NULL,
              git_push_performed INTEGER NOT NULL,
              worker_spawn_performed INTEGER NOT NULL,
              worker_run_performed INTEGER NOT NULL,
              next_safe_action TEXT NOT NULL,
              receipt_content_hash TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO universal_receipts (
              receipt_id, receipt_type, created_at, source_request_id,
              controller_event_id, operator_envelope_ref, package_id, card_id,
              world_ref, thread_ref, client_ref, workflow_ref, actor_ref,
              agent_character, action_taken, action_not_taken_json,
              authority_requested_json, authority_granted_json,
              authority_denied_json, proof_refs_json, artifact_refs_json,
              hash_refs_json, sqlite_refs_json, read_model_refs_json,
              validation_refs_json, result_status, business_action_performed,
              paid_marking_performed, ledger_mutation_performed,
              email_send_performed, coupa_submit_performed,
              workbook_mutation_performed, pdf_export_performed,
              merge_performed, git_push_performed, worker_spawn_performed,
              worker_run_performed, next_safe_action, receipt_content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["receipt_id"],
                    row["receipt_type"],
                    row["created_at"],
                    row["source_request_id"],
                    row["controller_event_id"],
                    row["operator_envelope_ref"],
                    row["package_id"],
                    row["card_id"],
                    row["world_ref"],
                    row["thread_ref"],
                    row["client_ref"],
                    row["workflow_ref"],
                    row["actor_ref"],
                    row["agent_character"],
                    row["action_taken"],
                    json.dumps(row["action_not_taken"], sort_keys=True),
                    json.dumps(row["authority_requested"], sort_keys=True),
                    json.dumps(row["authority_granted"], sort_keys=True),
                    json.dumps(row["authority_denied"], sort_keys=True),
                    json.dumps(row["proof_refs"], sort_keys=True),
                    json.dumps(row["artifact_refs"], sort_keys=True),
                    json.dumps(row["hash_refs"], sort_keys=True),
                    json.dumps(row["sqlite_refs"], sort_keys=True),
                    json.dumps(row["read_model_refs"], sort_keys=True),
                    json.dumps(row["validation_refs"], sort_keys=True),
                    row["result_status"],
                    1 if row["business_action_performed"] else 0,
                    1 if row["paid_marking_performed"] else 0,
                    1 if row["ledger_mutation_performed"] else 0,
                    1 if row["email_send_performed"] else 0,
                    1 if row["coupa_submit_performed"] else 0,
                    1 if row["workbook_mutation_performed"] else 0,
                    1 if row["pdf_export_performed"] else 0,
                    1 if row["merge_performed"] else 0,
                    1 if row["git_push_performed"] else 0,
                    1 if row["worker_spawn_performed"] else 0,
                    1 if row["worker_run_performed"] else 0,
                    row["next_safe_action"],
                    row["receipt_content_hash"],
                )
                for row in receipts
            ],
        )
        conn.commit()
        row = conn.execute("SELECT COUNT(*) FROM universal_receipts").fetchone()
        return int(row[0])
    finally:
        conn.close()


def sqlite_receipt_count(sqlite_path: Path = DEFAULT_SQLITE_PATH) -> int:
    sqlite_path = _rooted(sqlite_path)
    conn = sqlite3.connect(sqlite_path)
    try:
        row = conn.execute("SELECT COUNT(*) FROM universal_receipts").fetchone()
        return int(row[0])
    finally:
        conn.close()


def build_contract_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _preconditions(read_model_root)
    return {
        "schema_version": f"{SCHEMA_VERSION}_contract",
        "read_model_id": CONTRACT_READ_MODEL_ID,
        "status": READY_STATUS if all(row["ready"] for row in preconditions) else NOT_READY_STATUS,
        "generated_at": generated_at,
        "receipt_schema_version": SCHEMA_VERSION,
        "receipt_types": list(RECEIPT_TYPES),
        "required_receipt_fields": list(REQUIRED_RECEIPT_FIELDS),
        "list_fields": list(LIST_FIELDS),
        "false_operation_fields": list(FALSE_OPERATION_FIELDS),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "preconditions": preconditions,
        "rules": [
            "Receipt records what happened and what did not happen.",
            "Approval receipt is not execution proof.",
            "Evidence receipt is not paid truth unless payment or ledger evidence exists.",
            "LM output is not receipt truth.",
            "Incoming authority_granted is ignored or rejected.",
            "No business action receipt exists unless a future explicit executor gate records one.",
        ],
        "machine_proof": {
            "incoming_authority_granted_accepted": False,
            "business_action_performed": False,
            "paid_marking_performed": False,
            "ledger_mutation_performed": False,
            "email_send_performed": False,
            "coupa_submit_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "unsafe_true_grants": [],
            "unsafe_true_grants_absent": True,
        },
    }


def build_status_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    receipts = build_example_receipts(generated_at=generated_at)
    validations = [validate_receipt(receipt) for receipt in receipts]
    sqlite_row_count = _write_sqlite(sqlite_path, receipts)
    payload: dict[str, Any] = {
        "schema_version": f"{SCHEMA_VERSION}_status",
        "read_model_id": STATUS_READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready and all(item["valid"] for item in validations) else NOT_READY_STATUS,
        "generated_at": generated_at,
        "receipt_schema_version": SCHEMA_VERSION,
        "receipt_count": len(receipts),
        "sqlite_row_count": sqlite_row_count,
        "receipts": receipts,
        "receipt_types_present": sorted({str(receipt["receipt_type"]) for receipt in receipts}),
        "preconditions": preconditions,
        "sqlite_path": str(_rooted(sqlite_path)),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "rules": [
            "Receipts are durable local proof refs, not action grants.",
            "Approval and gate receipts remain separate from protected execution.",
            "Evidence receipts remain candidate proof until source payment or ledger evidence exists.",
            "Dynamic card receipts prove emission and card hashes, not source truth changes.",
            "Worker-result receipt shape is reserved but no worker is run by this read model.",
        ],
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "all_receipts_valid": all(item["valid"] for item in validations),
            "sqlite_row_count_matches_status": sqlite_row_count == len(receipts),
            "incoming_authority_granted_accepted": False,
            "business_action_performed": False,
            "paid_marking_performed": False,
            "ledger_mutation_performed": False,
            "email_send_performed": False,
            "coupa_submit_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "worker_run_performed": False,
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    return payload


def build_wiki(contract: Mapping[str, Any], status: Mapping[str, Any]) -> str:
    lines = [
        "# Universal Receipt Envelope",
        "",
        "Status: " + str(status["status"]),
        "",
        "Universal Receipt Envelope V0 is the shared receipt shape for controller events, packages, evidence, review decisions, approval queues, dynamic cards, memory gates, workflow plans, and future worker result rails.",
        "",
        "A receipt records what happened and what did not happen. It is not an approval, not execution proof, and not a source of business truth by itself.",
        "",
        "## Doctrine",
        "",
        "- Approval receipt is not execution proof.",
        "- Evidence receipt is not paid truth unless payment or ledger evidence exists.",
        "- LM output is not receipt truth.",
        "- Incoming authority_granted is ignored or rejected.",
        "- No business action receipt exists until a future explicit executor gate records one.",
        "",
        "## Receipt Types",
        "",
    ]
    for receipt_type in contract["receipt_types"]:
        lines.append(f"- `{receipt_type}`")
    lines.extend(
        [
            "",
            "## Required Fields",
            "",
        ]
    )
    for field in contract["required_receipt_fields"]:
        lines.append(f"- `{field}`")
    lines.extend(
        [
            "",
            "## Status Snapshot",
            "",
            f"- Receipt count: `{status['receipt_count']}`",
            f"- SQLite row count: `{status['sqlite_row_count']}`",
            f"- SQLite: `{status['sqlite_path']}`",
            f"- Unsafe true grants absent: `{str((status.get('machine_proof') or {}).get('unsafe_true_grants_absent')).lower()}`",
            "",
        ]
    )
    return "\n".join(lines)


def export_universal_receipt_envelope(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    generated_at = generated_at or utc_now()
    contract = build_contract_read_model(read_model_root=read_model_root, generated_at=generated_at)
    status = build_status_read_model(read_model_root=read_model_root, sqlite_path=sqlite_path, generated_at=generated_at)

    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    contract_path = export_root / CONTRACT_JSON_EXPORT_NAME
    status_path = export_root / STATUS_JSON_EXPORT_NAME
    _write_json(contract_path, contract)
    _write_json(status_path, status)

    bridge_contract_path = ""
    bridge_status_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_contract = bridge_export_root / CONTRACT_JSON_EXPORT_NAME
        bridge_status = bridge_export_root / STATUS_JSON_EXPORT_NAME
        shutil.copy2(contract_path, bridge_contract)
        shutil.copy2(status_path, bridge_status)
        bridge_contract_path = bridge_contract.as_posix()
        bridge_status_path = bridge_status.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(contract, status), encoding="utf-8")
    return {
        "status": str(status["status"]),
        "contract_read_model_path": contract_path.as_posix(),
        "status_read_model_path": status_path.as_posix(),
        "bridge_contract_read_model_path": bridge_contract_path,
        "bridge_status_read_model_path": bridge_status_path,
        "sqlite_path": str(_rooted(sqlite_path)),
        "wiki_path": wiki_path.as_posix(),
        "receipt_count": str(status["receipt_count"]),
        "sqlite_row_count": str(status["sqlite_row_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Universal Receipt Envelope V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_universal_receipt_envelope(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        sqlite_path=Path(args.sqlite_path),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result), end="")
    else:
        print(f"{result['status']}: {result['status_read_model_path']}")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
