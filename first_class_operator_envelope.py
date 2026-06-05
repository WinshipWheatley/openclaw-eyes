"""First-Class Operator Authority Envelope V0.

Verifies operator/controller request envelopes from Mission Control-class
surfaces. This proves who/where/request integrity only; it never grants
business authority, executes tools, invokes models, or mutates business state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/First Class Operator Envelope.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/first_class_operator_envelope.sqlite")

SCHEMA_VERSION = "first_class_operator_envelope_v0"
CONTRACT_SCHEMA_VERSION = "first_class_operator_envelope_contract_v0"
CONTRACT_READ_MODEL_ID = "first_class_operator_envelope_contract"
STATUS_READ_MODEL_ID = "first_class_operator_envelope_status"
CONTRACT_JSON_EXPORT_NAME = f"{CONTRACT_READ_MODEL_ID}.json"
STATUS_JSON_EXPORT_NAME = f"{STATUS_READ_MODEL_ID}.json"

READY_STATUS = "FIRST_CLASS_OPERATOR_ENVELOPE_READY"
NOT_READY_STATUS = "FIRST_CLASS_OPERATOR_ENVELOPE_NOT_READY"
VERIFICATION_STATUS_VERIFIED = "verified"
VERIFICATION_STATUS_NEEDS_VERIFICATION = "needs_verification"
VERIFICATION_STATUS_REJECTED = "rejected"

ENVELOPE_KEYS = (
    "operator_authority_envelope",
    "first_class_operator_envelope",
    "operator_controller_envelope",
    "operator_envelope",
)

REQUIRED_ENVELOPE_FIELDS = (
    "envelope_id",
    "operator_ref",
    "app_instance_ref",
    "device_ref",
    "device_class",
    "session_ref",
    "request_hash",
    "created_at",
    "source_surface",
    "current_world_ref",
    "current_thread_ref",
    "authority_requested",
    "operator_verified",
    "app_instance_verified",
    "device_verified",
    "session_verified",
    "verification_status",
    "proof_refs",
)

BACKEND_ONLY_FIELDS = (
    "authority_granted",
    "gate_decision_ref",
    "approval_receipt_ref",
)

DEVICE_CLASSES = ("mac", "ipad", "iphone", "unknown")
SOURCE_SURFACES = ("chat", "pad", "card", "dropzone", "proof_drawer")
CONTROLLER_ACTION_TYPES = (
    "chat_goal",
    "do_it",
    "approve",
    "deny",
    "attach_proof",
    "ask_why",
    "open_lane",
    "stage_plan",
    "request_rework",
    "mark_informational",
    "stop_hold_cancel",
    "show_details",
)

PROTECTED_AUTHORITY_REQUESTS = {
    "email_send",
    "gmail",
    "gmail_access",
    "browser",
    "browser_access",
    "coupa",
    "portal_submit",
    "ledger_post",
    "ledger_mutation",
    "workbook_mutation",
    "workbook_source_mutation",
    "pdf_export",
    "mark_paid",
    "paid_marking",
    "git_push",
    "worker_spawn",
    "external_provider",
    "external_llm",
    "business_action",
}

PRECONDITIONS = {
    "operator_runtime_chain_current_state_audit": {
        "filename": "operator_runtime_chain_current_state_audit.json",
        "accepted_statuses": ("OPERATOR_RUNTIME_CHAIN_CURRENT_STATE_AUDIT_READY",),
    },
    "dynamic_card_packet": {
        "filename": "dynamic_card_packet_latest.json",
        "accepted_statuses": ("DYNAMIC_CARD_PACKET_READY",),
    },
    "verified_evidence_intake": {
        "filename": "evidence_intake_status.json",
        "accepted_statuses": ("EVIDENCE_INTAKE_READY",),
    },
    "gate_decision_ledger": {
        "filename": "gate_decision_ledger.json",
        "accepted_statuses": ("GATE_DECISION_LEDGER_READY",),
    },
}

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_posting_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_source_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "business_action_allowed": False,
    "external_action_allowed": False,
    "authority_grant_allowed": False,
    "worker_spawn_allowed": False,
    "git_push_allowed": False,
    "sent": False,
    "paid": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | {
    "email_send_performed",
    "email_sent",
    "gmail_access_performed",
    "gmail_opened",
    "browser_access_performed",
    "browser_opened",
    "coupa_access_performed",
    "coupa_opened",
    "coupa_submit_performed",
    "portal_submit_performed",
    "ledger_posting_performed",
    "ledger_mutation_performed",
    "workbook_mutation_performed",
    "pdf_export_performed",
    "paid_marking_performed",
    "mark_paid_performed",
    "submit_performed",
    "business_action_performed",
    "authority_grant_performed",
    "authority_granted_by_envelope",
    "worker_spawn_performed",
    "worker_execution_performed",
    "child_agent_run_performed",
    "external_llm_invoked",
    "external_provider_connected",
    "local_model_runtime_connected",
    "model_invoked",
    "git_push_performed",
    "push_performed",
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _short_hash(*parts: object, length: int = 16) -> str:
    joined = "\0".join(str(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:length]


def _copy_without_request_hash(payload: Any) -> Any:
    if isinstance(payload, Mapping):
        return {
            str(key): _copy_without_request_hash(value)
            for key, value in payload.items()
            if key != "request_hash"
        }
    if isinstance(payload, list):
        return [_copy_without_request_hash(item) for item in payload]
    return payload


def compute_request_hash(request_payload: Mapping[str, Any]) -> str:
    canonical = _copy_without_request_hash(request_payload)
    digest = hashlib.sha256(stable_json(canonical).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _load_json(path: Path) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _status(payload: Mapping[str, Any]) -> str:
    for key in ("status", "readiness_status", "contract_status"):
        value = payload.get(key)
        if value:
            return str(value)
    return ""


def _source_ref(filename: str) -> str:
    return f"generated/read_models/{filename}"


def _precondition_rows(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for precondition_ref, spec in PRECONDITIONS.items():
        filename = str(spec["filename"])
        payload = _load_json(_rooted(read_model_root) / filename)
        observed = _status(payload)
        accepted = tuple(str(status) for status in spec["accepted_statuses"])
        rows.append(
            {
                "precondition_ref": precondition_ref,
                "observed_status": observed,
                "accepted_statuses": list(accepted),
                "ready": observed in accepted,
                "source_ref": _source_ref(filename),
            }
        )
    return rows


def _present(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _as_bool(value: Any) -> bool:
    return value is True


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _extract_envelope(payload: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    for key in ENVELOPE_KEYS:
        envelope = payload.get(key)
        if isinstance(envelope, Mapping):
            return key, dict(envelope)
    if any(field in payload for field in REQUIRED_ENVELOPE_FIELDS):
        return "top_level", dict(payload)
    return "", {}


def _incoming_backend_only_fields(payload: Mapping[str, Any], envelope: Mapping[str, Any]) -> list[str]:
    fields: list[str] = []
    for field in BACKEND_ONLY_FIELDS:
        if field in payload:
            fields.append(field)
        if field in envelope:
            fields.append(f"envelope.{field}")
    return fields


def _authority_requested(payload: Mapping[str, Any], envelope: Mapping[str, Any]) -> list[str]:
    envelope_requested = _normalize_list(envelope.get("authority_requested"))
    payload_requested = _normalize_list(payload.get("authority_requested"))
    return envelope_requested or payload_requested


def validate_operator_authority_envelope(
    payload: Mapping[str, Any],
    *,
    enforce_request_hash: bool = True,
) -> dict[str, Any]:
    """Validate a supplied controller envelope without minting missing proof."""

    blockers: list[str] = []
    rejected_reasons: list[str] = []
    envelope_key, envelope = _extract_envelope(payload)
    if not envelope:
        blockers.append("operator_authority_envelope_missing")

    for field in REQUIRED_ENVELOPE_FIELDS:
        if field in {"authority_requested", "proof_refs"}:
            if field not in envelope:
                blockers.append(f"{field}_missing")
            continue
        if field in {"operator_verified", "app_instance_verified", "device_verified", "session_verified"}:
            if field not in envelope:
                blockers.append(f"{field}_missing")
            continue
        if not _present(envelope.get(field)):
            blockers.append(f"{field}_missing")

    device_class = str(envelope.get("device_class") or "")
    if device_class and device_class not in DEVICE_CLASSES:
        blockers.append("device_class_invalid")

    source_surface = str(envelope.get("source_surface") or "")
    if source_surface and source_surface not in SOURCE_SURFACES:
        blockers.append("source_surface_invalid")

    controller_action_type = str(payload.get("controller_action_type") or envelope.get("controller_action_type") or "")
    if controller_action_type not in CONTROLLER_ACTION_TYPES:
        blockers.append("controller_action_type_invalid_or_missing")

    if envelope.get("verification_status") not in {
        VERIFICATION_STATUS_VERIFIED,
        VERIFICATION_STATUS_NEEDS_VERIFICATION,
        VERIFICATION_STATUS_REJECTED,
    }:
        blockers.append("verification_status_invalid")

    proof_refs = _normalize_list(envelope.get("proof_refs"))
    if "proof_refs" in envelope and not proof_refs:
        blockers.append("proof_refs_empty")

    authority_requested = _authority_requested(payload, envelope)
    if "authority_requested" in envelope and not isinstance(envelope.get("authority_requested"), list):
        blockers.append("authority_requested_not_list")
    if "authority_requested" in payload and _normalize_list(payload.get("authority_requested")) != authority_requested:
        blockers.append("authority_requested_mismatch")

    incoming_backend_fields = _incoming_backend_only_fields(payload, envelope)
    if incoming_backend_fields:
        rejected_reasons.append("incoming_backend_only_authority_fields_not_accepted")

    local_dev_verified = envelope.get("local_dev_verified") is True
    verification_flags = {
        "operator_verified": _as_bool(envelope.get("operator_verified")),
        "app_instance_verified": _as_bool(envelope.get("app_instance_verified")),
        "device_verified": _as_bool(envelope.get("device_verified")),
        "session_verified": _as_bool(envelope.get("session_verified")),
    }
    production_verified = all(verification_flags.values()) and envelope.get("verification_status") == VERIFICATION_STATUS_VERIFIED
    protected_requested = sorted(set(authority_requested).intersection(PROTECTED_AUTHORITY_REQUESTS))
    if local_dev_verified and protected_requested:
        rejected_reasons.append("local_dev_verified_cannot_request_production_authority")
    if not production_verified and not local_dev_verified:
        for field, verified in verification_flags.items():
            if not verified:
                blockers.append(f"{field}_false_or_missing")
        if envelope.get("verification_status") != VERIFICATION_STATUS_VERIFIED:
            blockers.append("verification_status_not_verified")

    request_hash = str(envelope.get("request_hash") or "")
    hash_checked = False
    expected_request_hash = ""
    if enforce_request_hash and request_hash:
        expected_request_hash = compute_request_hash(payload)
        hash_checked = True
        if request_hash != expected_request_hash:
            blockers.append("request_hash_mismatch")

    if rejected_reasons:
        verification_status = VERIFICATION_STATUS_REJECTED
    elif blockers:
        verification_status = VERIFICATION_STATUS_NEEDS_VERIFICATION
    else:
        verification_status = VERIFICATION_STATUS_VERIFIED

    verified = verification_status == VERIFICATION_STATUS_VERIFIED
    verification_mode = "local_dev" if verified and local_dev_verified and not production_verified else "controller_proof"
    production_authority_eligible = verified and production_verified and not local_dev_verified
    return {
        "schema_version": SCHEMA_VERSION,
        "verification_status": verification_status,
        "verified": verified,
        "verification_mode": verification_mode if verified else "",
        "envelope_key": envelope_key,
        "blockers": blockers,
        "rejected_reasons": rejected_reasons,
        "envelope_id": str(envelope.get("envelope_id") or ""),
        "operator_ref": str(envelope.get("operator_ref") or ""),
        "app_instance_ref": str(envelope.get("app_instance_ref") or ""),
        "device_ref": str(envelope.get("device_ref") or ""),
        "device_class": device_class,
        "session_ref": str(envelope.get("session_ref") or ""),
        "source_surface": source_surface,
        "controller_action_type": controller_action_type,
        "current_world_ref": str(envelope.get("current_world_ref") or ""),
        "current_thread_ref": str(envelope.get("current_thread_ref") or ""),
        "active_entity_ref": str(envelope.get("active_entity_ref") or ""),
        "created_at": str(envelope.get("created_at") or ""),
        "request_hash": request_hash,
        "request_hash_checked": hash_checked,
        "expected_request_hash": expected_request_hash if hash_checked else "",
        "authority_requested": authority_requested,
        "authority_granted": [],
        "gate_decision_ref": "",
        "approval_receipt_ref": "",
        "operator_verified": verification_flags["operator_verified"],
        "app_instance_verified": verification_flags["app_instance_verified"],
        "device_verified": verification_flags["device_verified"],
        "session_verified": verification_flags["session_verified"],
        "local_dev_verified": local_dev_verified,
        "proof_refs": proof_refs,
        "incoming_backend_only_fields": incoming_backend_fields,
        "incoming_authority_granted_accepted": False,
        "production_authority_eligible": production_authority_eligible,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "lm_cannot_generate_verification": True,
            "missing_fields_were_not_filled": True,
            "request_hash_required": True,
            "request_hash_checked": hash_checked,
            "incoming_authority_granted_ignored_or_rejected": bool(incoming_backend_fields),
            "authority_requested_does_not_imply_authority_granted": True,
            "authority_granted_produced_only_by_backend_gates": True,
            "envelope_proves_identity_not_business_permission": True,
            "local_dev_verified_not_production_authority": local_dev_verified and not production_authority_eligible,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "business_action_performed": False,
            "external_llm_invoked": False,
            "external_provider_connected": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
            "git_push_performed": False,
        },
    }


def attach_verified_authority_envelope(
    request_payload: Mapping[str, Any],
    *,
    operator_ref: str = "operator:winship",
    app_instance_ref: str = "mission_control:mac",
    device_ref: str = "device:macbook",
    device_class: str = "mac",
    session_ref: str = "session:mission-control",
    source_surface: str = "card",
    current_world_ref: str = "mission_control",
    current_thread_ref: str = "operator_surface",
    active_entity_ref: str = "",
    controller_action_type: str = "show_details",
    authority_requested: Sequence[str] = (),
    proof_refs: Sequence[str] = (),
    created_at: str | None = None,
    local_dev_verified: bool = False,
) -> dict[str, Any]:
    """Attach a correctly hashed controller envelope for trusted fixtures/UI."""

    created_at = created_at or utc_now()
    request = dict(request_payload)
    requested = [str(item) for item in authority_requested]
    request["controller_action_type"] = controller_action_type
    request["authority_requested"] = requested
    envelope_id = "operator_authority_envelope:" + _short_hash(
        operator_ref,
        app_instance_ref,
        device_ref,
        session_ref,
        source_surface,
        current_world_ref,
        current_thread_ref,
        controller_action_type,
        created_at,
    )
    request["operator_authority_envelope"] = {
        "envelope_id": envelope_id,
        "operator_ref": operator_ref,
        "app_instance_ref": app_instance_ref,
        "device_ref": device_ref,
        "device_class": device_class,
        "session_ref": session_ref,
        "request_hash": "",
        "created_at": created_at,
        "source_surface": source_surface,
        "current_world_ref": current_world_ref,
        "current_thread_ref": current_thread_ref,
        "active_entity_ref": active_entity_ref,
        "authority_requested": requested,
        "operator_verified": not local_dev_verified,
        "app_instance_verified": not local_dev_verified,
        "device_verified": not local_dev_verified,
        "session_verified": not local_dev_verified,
        "local_dev_verified": bool(local_dev_verified),
        "verification_status": VERIFICATION_STATUS_VERIFIED,
        "proof_refs": list(proof_refs)
        or [
            app_instance_ref,
            device_ref,
            session_ref,
        ],
    }
    request["operator_authority_envelope"]["request_hash"] = compute_request_hash(request)
    return request


def build_envelope_record(payload: Mapping[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    validation = validate_operator_authority_envelope(payload)
    record = {
        "schema_version": SCHEMA_VERSION,
        "status": READY_STATUS if validation["verified"] else NOT_READY_STATUS,
        "generated_at": generated_at,
        "envelope": validation,
        "verification_status": validation["verification_status"],
        "authority_requested": validation["authority_requested"],
        "authority_granted": [],
        "gate_decision_ref": "",
        "approval_receipt_ref": "",
        "controller_action_type": validation["controller_action_type"],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            **dict(validation["machine_proof"]),
            "operator_identity_envelope_recorded": validation["verified"],
            "authority_granted_empty_until_backend_gate": validation["authority_granted"] == [],
            "business_action_performed": False,
            "external_llm_invoked": False,
            "external_provider_connected": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
        },
    }
    record["machine_proof"]["unsafe_true_grants"] = unsafe_true_grants(record)
    record["machine_proof"]["unsafe_true_grants_absent"] = not record["machine_proof"]["unsafe_true_grants"]
    return record


def _init_schema(conn: sqlite3.Connection, *, replace: bool = False) -> None:
    if replace:
        conn.execute("DROP TABLE IF EXISTS first_class_operator_envelopes")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS first_class_operator_envelopes (
          envelope_id TEXT PRIMARY KEY,
          operator_ref TEXT NOT NULL,
          app_instance_ref TEXT NOT NULL,
          device_ref TEXT NOT NULL,
          device_class TEXT NOT NULL,
          session_ref TEXT NOT NULL,
          request_hash TEXT NOT NULL,
          controller_action_type TEXT NOT NULL,
          source_surface TEXT NOT NULL,
          current_world_ref TEXT NOT NULL,
          current_thread_ref TEXT NOT NULL,
          active_entity_ref TEXT NOT NULL,
          authority_requested_json TEXT NOT NULL,
          authority_granted_json TEXT NOT NULL,
          operator_verified INTEGER NOT NULL,
          app_instance_verified INTEGER NOT NULL,
          device_verified INTEGER NOT NULL,
          session_verified INTEGER NOT NULL,
          local_dev_verified INTEGER NOT NULL,
          verification_status TEXT NOT NULL,
          gate_decision_ref TEXT NOT NULL,
          approval_receipt_ref TEXT NOT NULL,
          proof_refs_json TEXT NOT NULL,
          production_authority_eligible INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          recorded_at TEXT NOT NULL
        )
        """
    )


def _insert_row(conn: sqlite3.Connection, record: Mapping[str, Any]) -> None:
    envelope = record["envelope"]
    conn.execute(
        """
        INSERT OR REPLACE INTO first_class_operator_envelopes (
          envelope_id, operator_ref, app_instance_ref, device_ref, device_class,
          session_ref, request_hash, controller_action_type, source_surface,
          current_world_ref, current_thread_ref, active_entity_ref,
          authority_requested_json, authority_granted_json, operator_verified,
          app_instance_verified, device_verified, session_verified,
          local_dev_verified, verification_status, gate_decision_ref,
          approval_receipt_ref, proof_refs_json, production_authority_eligible,
          created_at, recorded_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            envelope["envelope_id"],
            envelope["operator_ref"],
            envelope["app_instance_ref"],
            envelope["device_ref"],
            envelope["device_class"],
            envelope["session_ref"],
            envelope["request_hash"],
            envelope["controller_action_type"],
            envelope["source_surface"],
            envelope["current_world_ref"],
            envelope["current_thread_ref"],
            envelope["active_entity_ref"],
            stable_json(envelope["authority_requested"]),
            stable_json(envelope["authority_granted"]),
            1 if envelope["operator_verified"] else 0,
            1 if envelope["app_instance_verified"] else 0,
            1 if envelope["device_verified"] else 0,
            1 if envelope["session_verified"] else 0,
            1 if envelope["local_dev_verified"] else 0,
            envelope["verification_status"],
            envelope["gate_decision_ref"],
            envelope["approval_receipt_ref"],
            stable_json(envelope["proof_refs"]),
            1 if envelope["production_authority_eligible"] else 0,
            envelope["created_at"],
            record["generated_at"],
        ),
    )


def record_operator_authority_envelope(
    payload: Mapping[str, Any],
    *,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
    replace_status_snapshot: bool = False,
) -> dict[str, Any]:
    record = build_envelope_record(payload, generated_at=generated_at)
    if record["verification_status"] != VERIFICATION_STATUS_VERIFIED:
        return record
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    try:
        _init_schema(conn, replace=replace_status_snapshot)
        _insert_row(conn, record)
        conn.commit()
    finally:
        conn.close()
    return record


def example_verified_mac_request(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    return attach_verified_authority_envelope(
        {
            "request_type": "OPERATOR_CONTROLLER_ACTION_V0",
            "plain_text": "Show details for the current evidence card.",
        },
        operator_ref="operator:winship",
        app_instance_ref="mission_control:mac",
        device_ref="device:macbook",
        device_class="mac",
        session_ref="session:first-class-envelope-example",
        source_surface="card",
        current_world_ref="finance",
        current_thread_ref="live_arts_md",
        active_entity_ref="dynamic_card.finance.live_arts_md.evidence_intake.payment_processing",
        controller_action_type="show_details",
        authority_requested=[],
        proof_refs=[
            "controller_surface:mission_control",
            "mission_control:mac",
            "device:macbook",
            "session:first-class-envelope-example",
        ],
        created_at=generated_at,
    )


def build_contract_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _precondition_rows(read_model_root)
    status = READY_STATUS if all(row["ready"] for row in preconditions) else NOT_READY_STATUS
    payload: dict[str, Any] = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "read_model_id": CONTRACT_READ_MODEL_ID,
        "status": status,
        "generated_at": generated_at,
        "purpose": "Verify app/device/session/operator control requests without granting business authority.",
        "request_envelope_keys": list(ENVELOPE_KEYS),
        "required_envelope_fields": list(REQUIRED_ENVELOPE_FIELDS),
        "backend_only_fields": list(BACKEND_ONLY_FIELDS),
        "device_classes": list(DEVICE_CLASSES),
        "source_surfaces": list(SOURCE_SURFACES),
        "controller_action_types": list(CONTROLLER_ACTION_TYPES),
        "verification_statuses": [
            VERIFICATION_STATUS_VERIFIED,
            VERIFICATION_STATUS_NEEDS_VERIFICATION,
            VERIFICATION_STATUS_REJECTED,
        ],
        "rules": [
            "LM output cannot mint operator, app, device, session, or verification proof fields.",
            "Incoming authority_requested is allowed as a request, not a grant.",
            "Incoming authority_granted, gate_decision_ref, and approval_receipt_ref are backend-only and rejected or ignored.",
            "authority_granted remains empty until backend gates write a separate gate/approval receipt.",
            "Missing app/device/session proof fails closed.",
            "local_dev_verified is accepted only as local-dev identity proof and never production authority.",
            "Envelope verification does not authorize email, Coupa, browser, ledger, workbook, PDF, paid, submit, push, worker, or provider actions.",
        ],
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "preconditions_ready": all(row["ready"] for row in preconditions),
            "contract_only_no_business_authority": True,
            "backend_only_authority_fields_documented": True,
            "controller_action_types_declared": True,
            "external_llm_invoked": False,
            "external_provider_connected": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
            "business_action_performed": False,
            "authority_grant_performed": False,
        },
    }
    payload["machine_proof"]["unsafe_true_grants"] = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants_absent"] = not payload["machine_proof"]["unsafe_true_grants"]
    return payload


def build_status_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
    replace_status_snapshot: bool = True,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    request = example_verified_mac_request(generated_at=generated_at)
    latest_record = record_operator_authority_envelope(
        request,
        sqlite_path=sqlite_path,
        generated_at=generated_at,
        replace_status_snapshot=replace_status_snapshot,
    )
    preconditions = _precondition_rows(read_model_root)
    status = READY_STATUS if latest_record["verification_status"] == VERIFICATION_STATUS_VERIFIED and all(row["ready"] for row in preconditions) else NOT_READY_STATUS
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": STATUS_READ_MODEL_ID,
        "status": status,
        "generated_at": generated_at,
        "latest_record": latest_record,
        "sqlite_path": str(_rooted(sqlite_path)),
        "preconditions": preconditions,
        "bridge_contract_ref": f"/mnt/e/openclaw/generated/read_models/{CONTRACT_JSON_EXPORT_NAME}",
        "bridge_status_ref": f"/mnt/e/openclaw/generated/read_models/{STATUS_JSON_EXPORT_NAME}",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "preconditions_ready": all(row["ready"] for row in preconditions),
            "first_class_operator_envelope_ready": status == READY_STATUS,
            "latest_envelope_verified": latest_record["verification_status"] == VERIFICATION_STATUS_VERIFIED,
            "authority_requested_does_not_imply_authority_granted": latest_record["authority_granted"] == [],
            "business_action_performed": False,
            "authority_grant_performed": False,
            "external_llm_invoked": False,
            "external_provider_connected": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
        },
    }
    payload["machine_proof"]["unsafe_true_grants"] = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants_absent"] = not payload["machine_proof"]["unsafe_true_grants"]
    return payload


def build_wiki(contract: Mapping[str, Any], status: Mapping[str, Any]) -> str:
    latest = status.get("latest_record") if isinstance(status.get("latest_record"), Mapping) else {}
    envelope = latest.get("envelope") if isinstance(latest.get("envelope"), Mapping) else {}
    lines = [
        "# First Class Operator Envelope",
        "",
        f"Status: `{status.get('status', NOT_READY_STATUS)}`",
        "",
        "This contract verifies operator controller envelopes from Mission Control-class surfaces.",
        "It proves operator/app/device/session/request integrity only. It does not grant business authority.",
        "",
        "## Required Envelope Fields",
        "",
        ", ".join(f"`{field}`" for field in REQUIRED_ENVELOPE_FIELDS),
        "",
        "## Backend-Only Fields",
        "",
        ", ".join(f"`{field}`" for field in BACKEND_ONLY_FIELDS),
        "",
        "Incoming requests may ask for `authority_requested`, but only backend gates may later produce `authority_granted`.",
        "",
        "## Latest Example",
        "",
        f"- Envelope: `{envelope.get('envelope_id', '')}`",
        f"- Device: `{envelope.get('device_class', '')}` / `{envelope.get('device_ref', '')}`",
        f"- Surface: `{envelope.get('source_surface', '')}`",
        f"- Action: `{envelope.get('controller_action_type', '')}`",
        f"- Verification status: `{latest.get('verification_status', '')}`",
        f"- Authority requested: `{latest.get('authority_requested', [])}`",
        f"- Authority granted: `{latest.get('authority_granted', [])}`",
        "",
        "## Safety",
        "",
        "- LMs cannot mint verification fields.",
        "- Local-dev verification is not production authority.",
        "- Business actions still require package, gate, Guardian, and operator review.",
        "- Email, Gmail, browser, Coupa, ledger, workbook, PDF, paid, submit, push, worker, and provider actions remain unavailable from this envelope.",
        "",
    ]
    return "\n".join(lines)


def export_first_class_operator_envelope(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    generated_at = generated_at or utc_now()
    contract = build_contract_read_model(read_model_root=read_model_root, generated_at=generated_at)
    status = build_status_read_model(
        read_model_root=read_model_root,
        sqlite_path=sqlite_path,
        generated_at=generated_at,
        replace_status_snapshot=True,
    )
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    contract_path = export_root / CONTRACT_JSON_EXPORT_NAME
    status_path = export_root / STATUS_JSON_EXPORT_NAME
    contract_path.write_text(stable_json(contract), encoding="utf-8")
    status_path.write_text(stable_json(status), encoding="utf-8")

    bridge_contract_path = ""
    bridge_status_path = ""
    if bridge_root is not None:
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_contract = bridge_root / CONTRACT_JSON_EXPORT_NAME
        bridge_status = bridge_root / STATUS_JSON_EXPORT_NAME
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
    }


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


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish First-Class Operator Envelope V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_first_class_operator_envelope(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=None if args.no_bridge else Path(args.bridge_root),
        wiki_path=Path(args.wiki_path),
        sqlite_path=Path(args.sqlite_path),
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result), end="")
    else:
        print(f"{result['status']}: {result['status_read_model_path']}")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
