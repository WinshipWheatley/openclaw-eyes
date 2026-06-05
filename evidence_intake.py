"""Verified Evidence Intake V0.

Records operator-dropped evidence artifacts as candidate evidence only. It
classifies payment screenshots locally, records hashing and lineage metadata,
and emits a human card without mutating ledger, workbook, Coupa, browser, Gmail,
or paid truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import first_class_operator_envelope as operator_authority_envelope
import verified_operator_envelope as operator_envelope


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Evidence Intake.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/evidence_intake.sqlite")
DEFAULT_ARTIFACT_LINEAGE_SQLITE_PATH = Path("generated/system_knowledge/artifact_lineage_registry.sqlite")
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")

REQUEST_TYPE = "EVIDENCE_INTAKE_REQUEST_V0"
VERIFIED_REQUEST_TYPE = "VERIFIED_EVIDENCE_INTAKE_REQUEST_V0"
REQUEST_TYPE_ALIASES = (REQUEST_TYPE, VERIFIED_REQUEST_TYPE)
SCHEMA_VERSION = "evidence_intake_v0"
CONTRACT_SCHEMA_VERSION = "evidence_intake_contract_v0"
CONTRACT_READ_MODEL_ID = "evidence_intake_contract"
STATUS_READ_MODEL_ID = "evidence_intake_status"
CONTRACT_JSON_EXPORT_NAME = f"{CONTRACT_READ_MODEL_ID}.json"
STATUS_JSON_EXPORT_NAME = f"{STATUS_READ_MODEL_ID}.json"
READY_STATUS = "EVIDENCE_INTAKE_READY"
NOT_READY_STATUS = "EVIDENCE_INTAKE_NOT_READY"
VERIFICATION_REQUIRED_STATUS = operator_envelope.STATUS_VERIFICATION_REQUIRED
REQUEST_BLOCKED_STATUS = "EVIDENCE_INTAKE_REQUEST_BLOCKED"
EVIDENCE_STATUS_RECORDED = "CANDIDATE_EVIDENCE_RECORDED"
FIRST_CLASS_OPERATOR_ENVELOPE_STATUS_REF = "generated/read_models/first_class_operator_envelope_status.json"
FIRST_CLASS_OPERATOR_ENVELOPE_CONTRACT_REF = "generated/read_models/first_class_operator_envelope_contract.json"

ARTIFACT_KINDS = ("screenshot", "pdf", "image", "document", "receipt")
INTENDED_USES = (
    "payment_proof",
    "invoice_proof",
    "proposal_proof",
    "work_log_proof",
    "general_reference",
)
PAYMENT_PROOF_STATES = (
    "payment_proof_candidate",
    "payment_processing_evidence_received",
    "payment_arrival_expected",
    "payment_arrived_unverified",
    "ledger_recording_pending_operator_review",
    "ledger_recorded",
    "rejected_or_test",
)

PRECONDITIONS = {
    "dynamic_card_packet": {
        "filename": "dynamic_card_packet_latest.json",
        "accepted_statuses": ("DYNAMIC_CARD_PACKET_READY",),
    },
    "operator_action_payloads": {
        "filename": "operator_action_payloads.json",
        "accepted_statuses": ("OPERATOR_ACTION_PAYLOADS_READY",),
    },
    "artifact_lineage_registry": {
        "filename": "artifact_lineage_registry.json",
        "accepted_statuses": ("ARTIFACT_LINEAGE_REGISTRY_READY",),
    },
    "evidence_confidence_scoring": {
        "filename": "evidence_confidence_scoring.json",
        "accepted_statuses": ("EVIDENCE_CONFIDENCE_SCORING_READY",),
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
    "sent": False,
    "paid": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | {
    "email_send_performed",
    "gmail_access_performed",
    "browser_access_performed",
    "coupa_access_performed",
    "coupa_submit_performed",
    "portal_submit_performed",
    "ledger_posting_performed",
    "ledger_mutation_performed",
    "workbook_open_performed",
    "workbook_body_read_performed",
    "spreadsheet_cell_read_performed",
    "workbook_mutation_performed",
    "excel_automation_performed",
    "pdf_export_performed",
    "paid_marking_performed",
    "payment_marking_performed",
    "mark_paid_performed",
    "submit_performed",
    "business_action_performed",
    "authority_grant_performed",
    "worker_spawn_performed",
    "worker_execution_performed",
    "child_agent_run_performed",
    "external_llm_invoked",
    "external_llm_called",
    "external_provider_connected",
    "local_model_runtime_connected",
    "model_invoked",
    "raw_ocr_text_stored",
    "raw_sensitive_detail_promoted_to_memory",
    "general_memory_promotion_allowed",
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def _artifact_path_exists(path: str) -> bool:
    if not path:
        return False
    p = Path(path)
    return p.exists() if p.is_absolute() else (ROOT / p).exists()


def _resolve_artifact_path(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _artifact_sha256(path: str) -> str:
    if not _artifact_path_exists(path):
        return ""
    return _sha256_file(_resolve_artifact_path(path))


def _artifact_hash_allowed(request: Mapping[str, Any]) -> bool:
    return any(
        request.get(field) is True
        for field in (
            "artifact_hash_allowed",
            "hash_artifact_allowed",
            "file_hash_allowed",
            "approved_for_hash",
        )
    )


def _bridge_path(path: str, bridge_artifact_ref: str) -> str:
    if path.startswith("/mnt/e/openclaw/"):
        return path
    if bridge_artifact_ref.startswith("/mnt/e/openclaw/"):
        return bridge_artifact_ref
    return ""


def _request_text(request: Mapping[str, Any]) -> str:
    fields = [
        request.get("operator_note"),
        request.get("artifact_path"),
        request.get("bridge_artifact_ref"),
        request.get("claimed_client_ref"),
        request.get("claimed_workflow_ref"),
        request.get("current_world_ref"),
        request.get("current_thread_ref"),
        request.get("intended_use"),
    ]
    return " ".join(str(value or "") for value in fields).lower()


def request_type_value(request: Mapping[str, Any]) -> str:
    for key in ("request_type", "kind", "type"):
        value = str(request.get(key) or "").strip().upper()
        if value:
            return value
    return ""


def is_evidence_intake_request(request: Mapping[str, Any]) -> bool:
    return request_type_value(request) in REQUEST_TYPE_ALIASES


def _normalized_artifact_kind(request: Mapping[str, Any]) -> str:
    explicit = str(request.get("artifact_kind") or "").strip().lower()
    if explicit in ARTIFACT_KINDS:
        return explicit
    hint = str(request.get("file_kind_hint") or "").strip().lower()
    extension = str(request.get("file_extension") or "").strip().lower().lstrip(".")
    if "screenshot" in hint:
        return "screenshot"
    if extension in {"png", "jpg", "jpeg", "heic", "webp", "gif", "tiff"} or "image" in hint:
        return "image"
    if extension == "pdf" or "pdf" in hint:
        return "pdf"
    if "receipt" in hint:
        return "receipt"
    if "document" in hint or extension in {"doc", "docx", "txt", "rtf"}:
        return "document"
    return explicit


def _first_present(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _verified_mac_drop_shape(request: Mapping[str, Any]) -> bool:
    if str(request.get("original_request_type") or request_type_value(request)).strip().upper() != VERIFIED_REQUEST_TYPE:
        return False
    required = (
        "operator_ref",
        "app_instance_ref",
        "device_ref",
        "session_ref",
        "created_at",
        "request_hash",
        "current_world_ref",
        "current_thread_ref",
    )
    return all(_first_present(request.get(field)) for field in required)


def _attach_derived_envelopes_for_verified_drop(request: dict[str, Any]) -> dict[str, Any]:
    if "operator_envelope" in request and any(key in request for key in operator_authority_envelope.ENVELOPE_KEYS):
        return request
    if not _verified_mac_drop_shape(request):
        return request

    original_request_hash = str(request.get("request_hash") or "")
    created_at = str(request.get("created_at") or utc_now())
    current_world_ref = str(request.get("current_world_ref") or request.get("world_ref") or "")
    current_thread_ref = str(request.get("current_thread_ref") or request.get("thread_ref") or request.get("lane_ref") or "")
    operator_ref = str(request.get("operator_ref") or "")
    app_instance_ref = str(request.get("app_instance_ref") or "")
    device_ref = str(request.get("device_ref") or "")
    session_ref = str(request.get("session_ref") or "")

    request["source_request_hash"] = original_request_hash
    request["controller_action_type"] = "attach_proof"
    request["operator_envelope"] = {
        "operator_ref": operator_ref,
        "app_instance_ref": app_instance_ref,
        "device_ref": device_ref,
        "session_ref": session_ref,
        "created_at": created_at,
        "source_surface": operator_envelope.SOURCE_SURFACE,
        "operator_verified": True,
        "request_hash": "",
    }
    request["operator_authority_envelope"] = {
        "envelope_id": "operator_authority_envelope:" + _short_hash(
            operator_ref,
            app_instance_ref,
            device_ref,
            session_ref,
            current_world_ref,
            current_thread_ref,
            created_at,
            "attach_proof",
        ),
        "operator_ref": operator_ref,
        "app_instance_ref": app_instance_ref,
        "device_ref": device_ref,
        "device_class": "mac",
        "session_ref": session_ref,
        "request_hash": "",
        "created_at": created_at,
        "source_surface": "dropzone",
        "current_world_ref": current_world_ref,
        "current_thread_ref": current_thread_ref,
        "active_entity_ref": str(request.get("selected_entity_ref") or current_thread_ref),
        "authority_requested": [],
        "operator_verified": True,
        "app_instance_verified": True,
        "device_verified": True,
        "session_verified": True,
        "verification_status": operator_authority_envelope.VERIFICATION_STATUS_VERIFIED,
        "proof_refs": [
            str(request.get("origin_surface") or request.get("source_channel") or "mission_control_evidence_drop_zone"),
            app_instance_ref,
            device_ref,
            session_ref,
            original_request_hash,
        ],
    }
    canonical_hash = operator_envelope.compute_request_hash(request)
    request["request_hash"] = canonical_hash
    request["operator_envelope"]["request_hash"] = canonical_hash
    request["operator_authority_envelope"]["request_hash"] = canonical_hash
    return request


def normalize_evidence_request(request: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(request)
    original_request_type = str(normalized.get("original_request_type") or request_type_value(normalized)).strip().upper()
    if original_request_type in REQUEST_TYPE_ALIASES:
        normalized["original_request_type"] = original_request_type
        normalized["request_type"] = REQUEST_TYPE
    normalized.setdefault("source_surface", operator_envelope.SOURCE_SURFACE)
    normalized["current_world_ref"] = _first_present(
        normalized.get("current_world_ref"),
        normalized.get("world_ref"),
    )
    normalized["current_thread_ref"] = _first_present(
        normalized.get("current_thread_ref"),
        normalized.get("thread_ref"),
        normalized.get("lane_ref"),
        normalized.get("visible_lane_ref"),
    )
    normalized["claimed_client_ref"] = _first_present(
        normalized.get("claimed_client_ref"),
        normalized.get("selected_client_ref"),
        normalized.get("client_ref"),
        normalized.get("current_thread_ref"),
    )
    normalized["claimed_workflow_ref"] = _first_present(
        normalized.get("claimed_workflow_ref"),
        normalized.get("workflow_ref"),
    )
    artifact_kind = _normalized_artifact_kind(normalized)
    if artifact_kind:
        normalized["artifact_kind"] = artifact_kind
    if not _first_present(normalized.get("artifact_path"), normalized.get("bridge_artifact_ref")):
        normalized["bridge_artifact_ref"] = _first_present(
            normalized.get("approved_pc_readable_path"),
            normalized.get("bridge_path"),
            normalized.get("mac_visible_path_ref"),
            normalized.get("file_display_name"),
        )
    if str(normalized.get("intended_use") or "") == "payment_proof":
        normalized.setdefault("privacy_class", "financial_sensitive")
    return _attach_derived_envelopes_for_verified_drop(normalized)


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
    for ref, spec in PRECONDITIONS.items():
        filename = str(spec["filename"])
        payload = _load_json(_rooted(read_model_root) / filename)
        observed = _status(payload)
        accepted = tuple(str(status) for status in spec["accepted_statuses"])
        rows.append(
            {
                "precondition_ref": ref,
                "observed_status": observed,
                "accepted_statuses": list(accepted),
                "ready": observed in accepted,
                "source_ref": _source_ref(filename),
            }
        )
    return rows


def _detect_invoice_ref(request: Mapping[str, Any]) -> str:
    text = _request_text(request)
    match = re.search(r"\binvoice\s+#?\s*([0-9]{4}-[0-9A-Za-z-]+)\b", text, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"\b([0-9]{4}-[0-9]{3,})\b", text)
    return match.group(1) if match else ""


def _redact_sensitive_note(note: str) -> str:
    redacted = re.sub(
        r"(?i)\b(bank\s+account|account|acct|routing|aba|wire|ach|card)\s*(?:#|number|no\.?)?\s*[:=-]?\s*[A-Za-z0-9* -]{4,}",
        lambda match: f"{match.group(1)} [redacted]",
        note,
    )
    redacted = re.sub(r"\b\d{9,}\b", "[redacted-number]", redacted)
    return redacted


def _operator_note_hash(note: str) -> str:
    return "sha256:" + hashlib.sha256(note.encode("utf-8")).hexdigest()


def _coerce_authority_boundary(value: Any) -> dict[str, bool]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): bool(item) for key, item in value.items()}


def _authority_all_false(boundary: Mapping[str, Any]) -> bool:
    expected = set(AUTHORITY_BOUNDARY)
    observed = set(str(key) for key in boundary)
    if not expected.issubset(observed):
        return False
    return all(boundary.get(key) is False for key in expected)


def classify_privacy(request: Mapping[str, Any]) -> dict[str, Any]:
    text = _request_text(request)
    is_payment = str(request.get("intended_use") or "") == "payment_proof"
    looks_financial = is_payment or any(term in text for term in ("payment", "invoice", "coupa", "paid", "bank", "ach"))
    if looks_financial:
        return {
            "privacy_class": "financial_sensitive",
            "processing_location": "local_only",
            "local_only": True,
            "external_provider_policy": "external_provider_blocked",
            "external_provider_blocked": True,
            "tokenization_required": True,
            "raw_ocr_text_stored": False,
            "raw_sensitive_detail_promoted_to_memory": False,
            "general_memory_promotion_allowed": False,
            "memory_destination": "none_for_raw_sensitive_detail",
        }
    proposed = str(request.get("privacy_class") or "internal_reference")
    return {
        "privacy_class": proposed,
        "processing_location": "local_only",
        "local_only": True,
        "external_provider_policy": "external_provider_blocked",
        "external_provider_blocked": True,
        "tokenization_required": proposed not in {"public", "internal_reference"},
        "raw_ocr_text_stored": False,
        "raw_sensitive_detail_promoted_to_memory": False,
        "general_memory_promotion_allowed": False,
        "memory_destination": "none_for_raw_sensitive_detail",
    }


def classify_payment_state(request: Mapping[str, Any]) -> dict[str, Any]:
    intended_use = str(request.get("intended_use") or "")
    text = _request_text(request)
    invoice_ref = _detect_invoice_ref(request)
    if intended_use != "payment_proof":
        payment_state = "payment_proof_candidate"
    elif any(term in text for term in ("processing", "pending", "in process", "scheduled", "expected")):
        payment_state = "payment_processing_evidence_received"
    elif any(term in text for term in ("arrived", "received")):
        payment_state = "payment_arrived_unverified"
    else:
        payment_state = "payment_proof_candidate"
    return {
        "payment_state": payment_state,
        "invoice_ref": invoice_ref,
        "evidence_is_payment_processing_only": payment_state == "payment_processing_evidence_received",
        "paid": False,
        "paid_truth_status": "NOT_PAID_PROOF",
        "ledger_recording_allowed": False,
        "ledger_mutation_performed": False,
        "paid_marking_performed": False,
        "paid_truth_requires": [
            "payment or bank confirmation",
            "ledger confirmation",
            "operator review before ledger recording",
        ],
    }


def validate_evidence_request(request: Mapping[str, Any]) -> dict[str, Any]:
    request = normalize_evidence_request(request)
    blockers: list[str] = []
    envelope_result = operator_envelope.validate_operator_envelope(request)
    authority_envelope_result = operator_authority_envelope.validate_operator_authority_envelope(request)
    if authority_envelope_result["verification_status"] != operator_authority_envelope.VERIFICATION_STATUS_VERIFIED:
        blockers.append("first_class_operator_authority_envelope_invalid")
    if envelope_result["status"] != operator_envelope.STATUS_VERIFIED:
        blockers.append("operator_verification_required")
    if request.get("request_type") != REQUEST_TYPE:
        blockers.append("request_type_invalid")
    if request.get("source_surface") != operator_envelope.SOURCE_SURFACE:
        blockers.append("source_surface_not_mission_control")
    if not str(request.get("current_world_ref") or "").strip():
        blockers.append("current_world_ref_missing")
    if not str(request.get("current_thread_ref") or "").strip():
        blockers.append("current_thread_ref_missing")
    if request.get("artifact_kind") not in ARTIFACT_KINDS:
        blockers.append("artifact_kind_invalid")
    if request.get("intended_use") not in INTENDED_USES:
        blockers.append("intended_use_invalid")
    if not str(request.get("artifact_path") or request.get("bridge_artifact_ref") or "").strip():
        blockers.append("artifact_ref_missing")
    boundary = _coerce_authority_boundary(request.get("authority_boundary"))
    if not _authority_all_false(boundary):
        blockers.append("authority_boundary_not_all_false")

    if envelope_result["status"] == operator_envelope.STATUS_VERIFICATION_REQUIRED:
        status = VERIFICATION_REQUIRED_STATUS
    elif blockers:
        status = REQUEST_BLOCKED_STATUS
    else:
        status = READY_STATUS
    return {
        "status": status,
        "valid": not blockers,
        "blockers": blockers,
        "operator_envelope": envelope_result,
        "operator_authority_envelope": authority_envelope_result,
    }


def build_dynamic_card(record: Mapping[str, Any]) -> dict[str, Any]:
    payment = record.get("payment") if isinstance(record.get("payment"), Mapping) else {}
    authority_envelope = (
        record.get("operator_authority_envelope")
        if isinstance(record.get("operator_authority_envelope"), Mapping)
        else {}
    )
    invoice_ref = str(payment.get("invoice_ref") or record.get("invoice_ref") or "2026-1001")
    summary = (
        f"This appears to show payment processing for invoice {invoice_ref}. "
        "Ledger remains untouched until payment is confirmed."
    )
    actions = [
        ("evidence_intake.attach_to_lane", "Attach to lane", "local_evidence_metadata_only"),
        ("evidence_intake.ask_what_this_means", "Ask what this means", "local_context_answer_only"),
        ("evidence_intake.mark_as_test", "Mark as test", "candidate_evidence_status_only"),
        ("evidence_intake.show_details", "Show details", "local_proof_drawer_only"),
    ]
    return {
        "schema_version": "evidence_intake_dynamic_card_v0",
        "card_id": f"dynamic_card.evidence_intake.payment_processing.{_short_hash(record.get('artifact_ref'), invoice_ref, length=10)}",
        "card_type": "evidence_intake",
        "headline": "Payment proof received",
        "summary": summary,
        "plain_summary": summary,
        "status_label": "Processing evidence",
        "trust_state": "operator_reported",
        "source_surface": operator_envelope.SOURCE_SURFACE,
        "target_world_ref": str(record.get("current_world_ref") or ""),
        "target_thread_ref": str(record.get("current_thread_ref") or ""),
        "actions": [
            {
                "action_id": action_id,
                "label": label,
                "enabled": True,
                "effect": effect,
                "business_action": False,
                "requires_operator_authority_envelope": True,
                "operator_authority_envelope_contract_ref": FIRST_CLASS_OPERATOR_ENVELOPE_CONTRACT_REF,
                "operator_authority_envelope_ref": str(authority_envelope.get("envelope_id") or ""),
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            }
            for action_id, label, effect in actions
        ],
        "proof": {
            "collapsed_by_default": True,
            "artifact_ref": str(record.get("artifact_ref") or ""),
            "read_model_refs": [
                f"generated/read_models/{STATUS_JSON_EXPORT_NAME}",
                FIRST_CLASS_OPERATOR_ENVELOPE_STATUS_REF,
            ],
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "ledger_mutation_performed": False,
            "paid_marking_performed": False,
            "business_action_performed": False,
        },
    }


def build_intake_record(request: Mapping[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
    request = normalize_evidence_request(request)
    generated_at = generated_at or utc_now()
    validation = validate_evidence_request(request)
    if validation["status"] != READY_STATUS:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": validation["status"],
            "evidence_status": "NOT_RECORDED",
            "blockers": validation["blockers"],
            "operator_envelope": validation["operator_envelope"],
            "operator_authority_envelope": validation.get("operator_authority_envelope") or {},
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
            "machine_proof": {
                "candidate_evidence_recorded": False,
                "ledger_mutation_performed": False,
                "paid_marking_performed": False,
                "business_action_performed": False,
            },
        }

    envelope = validation["operator_envelope"]
    authority_envelope = validation.get("operator_authority_envelope") or {}
    request_hash = str(envelope.get("request_hash") or operator_envelope.compute_request_hash(request))
    artifact_path = str(request.get("artifact_path") or "")
    bridge_artifact_ref = str(request.get("bridge_artifact_ref") or "")
    artifact_sha256 = str(request.get("artifact_sha256") or request.get("sha256") or "")
    if not artifact_sha256 and artifact_path and _artifact_hash_allowed(request):
        artifact_sha256 = _artifact_sha256(artifact_path)
    artifact_ref = f"artifact:evidence_intake_{_short_hash(request_hash, artifact_path, bridge_artifact_ref)}"
    request_ref = f"evidence_intake_request:{_short_hash(request_hash)}"
    operator_note = str(request.get("operator_note") or "")
    privacy = classify_privacy(request)
    payment = classify_payment_state(request)
    intake_id = f"evidence_intake:{_short_hash(request_hash, artifact_ref)}"
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": READY_STATUS,
        "intake_id": intake_id,
        "request_ref": request_ref,
        "source_request": {
            "request_type": REQUEST_TYPE,
            "source_surface": operator_envelope.SOURCE_SURFACE,
            "request_hash": request_hash,
            "source_request_hash": str(request.get("source_request_hash") or ""),
        },
        "operator_envelope": {
            "operator_ref": str(envelope.get("operator_ref") or ""),
            "app_instance_ref": str(envelope.get("app_instance_ref") or ""),
            "device_ref": str(envelope.get("device_ref") or ""),
            "session_ref": str(envelope.get("session_ref") or ""),
            "created_at": str((request.get("operator_envelope") or {}).get("created_at") or ""),
            "request_hash": request_hash,
            "operator_verified": True,
        },
        "operator_authority_envelope": {
            "envelope_id": str(authority_envelope.get("envelope_id") or ""),
            "verification_status": str(authority_envelope.get("verification_status") or ""),
            "operator_ref": str(authority_envelope.get("operator_ref") or ""),
            "app_instance_ref": str(authority_envelope.get("app_instance_ref") or ""),
            "device_ref": str(authority_envelope.get("device_ref") or ""),
            "device_class": str(authority_envelope.get("device_class") or ""),
            "session_ref": str(authority_envelope.get("session_ref") or ""),
            "controller_action_type": str(authority_envelope.get("controller_action_type") or ""),
            "authority_requested": list(authority_envelope.get("authority_requested") or []),
            "authority_granted": list(authority_envelope.get("authority_granted") or []),
            "proof_refs": list(authority_envelope.get("proof_refs") or []),
            "read_model_ref": FIRST_CLASS_OPERATOR_ENVELOPE_STATUS_REF if authority_envelope else "",
        } if authority_envelope else {},
        "current_world_ref": str(request.get("current_world_ref") or ""),
        "current_thread_ref": str(request.get("current_thread_ref") or ""),
        "claimed_client_ref": str(request.get("claimed_client_ref") or ""),
        "claimed_workflow_ref": str(request.get("claimed_workflow_ref") or ""),
        "artifact_ref": artifact_ref,
        "artifact": {
            "artifact_ref": artifact_ref,
            "kind": str(request.get("artifact_kind") or ""),
            "path": artifact_path,
            "bridge_artifact_ref": bridge_artifact_ref,
            "bridge_path": _bridge_path(artifact_path, bridge_artifact_ref),
            "path_exists": _artifact_path_exists(artifact_path),
            "sha256": artifact_sha256,
        },
        "operator_note": {
            "redacted": _redact_sensitive_note(operator_note),
            "sha256": _operator_note_hash(operator_note),
            "raw_note_stored_in_general_memory": False,
        },
        "privacy": privacy,
        "intended_use": str(request.get("intended_use") or ""),
        "evidence_status": EVIDENCE_STATUS_RECORDED,
        "payment": payment,
        "lineage_status": "candidate_evidence",
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    record["dynamic_card"] = build_dynamic_card(record)
    record["machine_proof"] = {
        "operator_verification_required_if_missing": True,
        "candidate_evidence_recorded": True,
        "artifact_hash_recorded_if_possible": bool(artifact_sha256),
        "artifact_hash_recorded_if_available": bool(artifact_sha256),
        "artifact_file_body_read_for_hash": bool(artifact_path and _artifact_hash_allowed(request) and artifact_sha256),
        "payment_processing_evidence_does_not_mark_paid": payment["paid"] is False,
        "ledger_mutation_performed": False,
        "paid_marking_performed": False,
        "raw_ocr_text_stored": False,
        "raw_sensitive_detail_promoted_to_memory": False,
        "general_memory_promotion_allowed": False,
        "external_llm_invoked": False,
        "external_provider_connected": False,
        "local_model_runtime_connected": False,
        "worker_spawn_performed": False,
        "business_action_performed": False,
    }
    return record


def _init_evidence_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS evidence_intake_records (
          intake_id TEXT PRIMARY KEY,
          request_ref TEXT NOT NULL,
          request_hash TEXT NOT NULL,
          operator_ref TEXT NOT NULL,
          app_instance_ref TEXT NOT NULL,
          device_ref TEXT NOT NULL,
          session_ref TEXT NOT NULL,
          source_surface TEXT NOT NULL,
          current_world_ref TEXT NOT NULL,
          current_thread_ref TEXT NOT NULL,
          claimed_client_ref TEXT NOT NULL,
          claimed_workflow_ref TEXT NOT NULL,
          artifact_ref TEXT NOT NULL,
          artifact_kind TEXT NOT NULL,
          artifact_path TEXT NOT NULL,
          bridge_artifact_ref TEXT NOT NULL,
          artifact_sha256 TEXT NOT NULL,
          path_exists INTEGER NOT NULL,
          operator_note_redacted TEXT NOT NULL,
          operator_note_sha256 TEXT NOT NULL,
          privacy_class TEXT NOT NULL,
          processing_location TEXT NOT NULL,
          external_provider_policy TEXT NOT NULL,
          tokenization_required INTEGER NOT NULL,
          intended_use TEXT NOT NULL,
          evidence_status TEXT NOT NULL,
          payment_state TEXT NOT NULL,
          invoice_ref TEXT NOT NULL,
          paid INTEGER NOT NULL,
          ledger_mutation_performed INTEGER NOT NULL,
          raw_ocr_text_stored INTEGER NOT NULL,
          general_memory_promotion_allowed INTEGER NOT NULL,
          dynamic_card_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        )
        """
    )


def _insert_evidence_row(conn: sqlite3.Connection, record: Mapping[str, Any]) -> None:
    artifact = record["artifact"]
    privacy = record["privacy"]
    payment = record["payment"]
    envelope = record["operator_envelope"]
    conn.execute(
        """
        INSERT OR REPLACE INTO evidence_intake_records (
          intake_id, request_ref, request_hash, operator_ref, app_instance_ref,
          device_ref, session_ref, source_surface, current_world_ref,
          current_thread_ref, claimed_client_ref, claimed_workflow_ref,
          artifact_ref, artifact_kind, artifact_path, bridge_artifact_ref,
          artifact_sha256, path_exists, operator_note_redacted,
          operator_note_sha256, privacy_class, processing_location,
          external_provider_policy, tokenization_required, intended_use,
          evidence_status, payment_state, invoice_ref, paid,
          ledger_mutation_performed, raw_ocr_text_stored,
          general_memory_promotion_allowed, dynamic_card_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record["intake_id"],
            record["request_ref"],
            record["source_request"]["request_hash"],
            envelope["operator_ref"],
            envelope["app_instance_ref"],
            envelope["device_ref"],
            envelope["session_ref"],
            record["source_request"]["source_surface"],
            record["current_world_ref"],
            record["current_thread_ref"],
            record["claimed_client_ref"],
            record["claimed_workflow_ref"],
            record["artifact_ref"],
            artifact["kind"],
            artifact["path"],
            artifact["bridge_artifact_ref"],
            artifact["sha256"],
            1 if artifact["path_exists"] else 0,
            record["operator_note"]["redacted"],
            record["operator_note"]["sha256"],
            privacy["privacy_class"],
            privacy["processing_location"],
            privacy["external_provider_policy"],
            1 if privacy["tokenization_required"] else 0,
            record["intended_use"],
            record["evidence_status"],
            payment["payment_state"],
            payment["invoice_ref"],
            1 if payment["paid"] else 0,
            1 if payment["ledger_mutation_performed"] else 0,
            1 if privacy["raw_ocr_text_stored"] else 0,
            1 if privacy["general_memory_promotion_allowed"] else 0,
            stable_json(record["dynamic_card"]),
            record["created_at"],
        ),
    )


def _reset_evidence_records(sqlite_path: Path) -> None:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    try:
        _init_evidence_schema(conn)
        conn.execute("DELETE FROM evidence_intake_records")
        conn.commit()
    finally:
        conn.close()


def _init_artifact_lineage_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS artifact_lineage (
          artifact_ref TEXT PRIMARY KEY,
          artifact_kind TEXT NOT NULL,
          path TEXT NOT NULL,
          bridge_path TEXT NOT NULL,
          path_exists INTEGER NOT NULL,
          sha256 TEXT NOT NULL,
          source_workflow_ref TEXT NOT NULL,
          source_package_id TEXT NOT NULL,
          source_receipt_ref TEXT NOT NULL,
          lineage_status TEXT NOT NULL,
          trusted_for_action INTEGER NOT NULL,
          proof_refs_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        )
        """
    )


def _insert_artifact_lineage_row(conn: sqlite3.Connection, record: Mapping[str, Any]) -> None:
    artifact = record["artifact"]
    proof_refs = [f"generated/read_models/{STATUS_JSON_EXPORT_NAME}", record["request_ref"]]
    path = str(artifact.get("path") or artifact.get("bridge_artifact_ref") or "")
    conn.execute(
        """
        INSERT OR REPLACE INTO artifact_lineage (
          artifact_ref, artifact_kind, path, bridge_path, path_exists, sha256,
          source_workflow_ref, source_package_id, source_receipt_ref,
          lineage_status, trusted_for_action, proof_refs_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record["artifact_ref"],
            artifact["kind"],
            path,
            artifact["bridge_path"],
            1 if artifact["path_exists"] else 0,
            artifact["sha256"],
            record["claimed_workflow_ref"] or "evidence_intake",
            "",
            "",
            "candidate_evidence",
            0,
            json.dumps(proof_refs, sort_keys=True),
            record["created_at"],
        ),
    )


def record_evidence_intake(
    request: Mapping[str, Any],
    *,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    artifact_lineage_sqlite_path: Path | None = DEFAULT_ARTIFACT_LINEAGE_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    record = build_intake_record(request, generated_at=generated_at)
    if record["status"] != READY_STATUS:
        return record

    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    try:
        _init_evidence_schema(conn)
        _insert_evidence_row(conn, record)
        conn.commit()
    finally:
        conn.close()

    lineage_status = "not_requested"
    if artifact_lineage_sqlite_path is not None:
        lineage_path = _rooted(artifact_lineage_sqlite_path)
        lineage_path.parent.mkdir(parents=True, exist_ok=True)
        lineage_conn = sqlite3.connect(lineage_path)
        try:
            _init_artifact_lineage_schema(lineage_conn)
            _insert_artifact_lineage_row(lineage_conn, record)
            lineage_conn.commit()
            lineage_status = "recorded"
        finally:
            lineage_conn.close()
    record["artifact_lineage_registry_update_status"] = lineage_status
    return record


def example_payment_processing_request(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or "2026-06-04T17:00:00+00:00"
    payload = {
        "request_id": "evidence_intake_example_payment_processing",
        "request_type": VERIFIED_REQUEST_TYPE,
        "kind": VERIFIED_REQUEST_TYPE,
        "type": VERIFIED_REQUEST_TYPE,
        "source_surface": operator_envelope.SOURCE_SURFACE,
        "current_world_ref": "finance",
        "current_thread_ref": "live_arts_md",
        "world_ref": "finance",
        "thread_ref": "live_arts_md",
        "claimed_client_ref": "live_arts_md",
        "claimed_workflow_ref": "live_arts_md_payment_watch",
        "operator_ref": "operator:winship",
        "app_instance_ref": "mission_control:pc",
        "device_ref": "device:pc",
        "session_ref": "session:evidence-intake-example",
        "created_at": generated_at,
        "request_hash": "sha256:example_source_request_hash",
        "artifact_path": "",
        "bridge_artifact_ref": "mission_control_drop:live_arts_md_payment_processing_screenshot_invoice_2026-1001",
        "artifact_kind": "screenshot",
        "operator_note": "Live Arts MD screenshot appears to show payment processing for invoice 2026-1001.",
        "privacy_class": "financial_sensitive",
        "intended_use": "payment_proof",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    return payload


def build_contract_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _precondition_rows(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    payload: dict[str, Any] = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "read_model_id": CONTRACT_READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "request_type": REQUEST_TYPE,
        "purpose": "Authenticated operator artifact drops for candidate evidence intake without business-truth mutation.",
        "required_operator_envelope_fields": list(operator_envelope.REQUIRED_ENVELOPE_FIELDS),
        "required_request_fields": [
            "request_type",
            "source_surface",
            "operator_envelope",
            "current_world_ref",
            "current_thread_ref",
            "artifact_path or bridge_artifact_ref",
            "artifact_kind",
            "operator_note",
            "privacy_class",
            "intended_use",
            "authority_boundary",
        ],
        "artifact_kinds": list(ARTIFACT_KINDS),
        "intended_uses": list(INTENDED_USES),
        "payment_proof_states": list(PAYMENT_PROOF_STATES),
        "privacy_rules": [
            "Payment screenshots classify as financial_sensitive.",
            "Payment screenshots stay local_only.",
            "External providers are blocked by default.",
            "Tokenization is required before any future provider boundary.",
            "Raw OCR/text is not stored in general memory.",
        ],
        "payment_truth_rules": [
            "Payment-processing evidence does not equal paid.",
            "Paid truth requires payment or ledger confirmation.",
            "Ledger recording remains pending operator review.",
        ],
        "dynamic_card_contract": {
            "headline": "Payment proof received",
            "status_label": "Processing evidence",
            "trust_states": ["preview_only", "operator_reported"],
            "required_actions": ["Attach to lane", "Ask what this means", "Mark as test", "Show details"],
        },
        "preconditions": preconditions,
        "sqlite_path": str(_rooted(DEFAULT_SQLITE_PATH)),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "contract_only": True,
            "operator_envelope_required": True,
            "request_hash_required": True,
            "payment_processing_evidence_does_not_mark_paid": True,
            "ledger_mutation_performed": False,
            "paid_marking_performed": False,
            "raw_ocr_text_stored": False,
            "raw_sensitive_detail_promoted_to_memory": False,
            "general_memory_promotion_allowed": False,
            "external_llm_invoked": False,
            "external_provider_connected": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
            "business_action_performed": False,
        },
    }
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe_true_grants(payload)
    return payload


def build_status_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    artifact_lineage_sqlite_path: Path | None = DEFAULT_ARTIFACT_LINEAGE_SQLITE_PATH,
    replace_status_snapshot: bool = True,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _precondition_rows(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    request = example_payment_processing_request(generated_at=generated_at)
    if replace_status_snapshot:
        _reset_evidence_records(sqlite_path)
    record = record_evidence_intake(
        request,
        sqlite_path=sqlite_path,
        artifact_lineage_sqlite_path=artifact_lineage_sqlite_path,
        generated_at=generated_at,
    )
    status = READY_STATUS if record["status"] == READY_STATUS and preconditions_ready else NOT_READY_STATUS
    payload = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": STATUS_READ_MODEL_ID,
        "status": status,
        "generated_at": generated_at,
        "latest_record": record,
        "dynamic_card": record.get("dynamic_card", {}),
        "preconditions": preconditions,
        "sqlite_path": str(_rooted(sqlite_path)),
        "artifact_lineage_sqlite_path": str(_rooted(artifact_lineage_sqlite_path)) if artifact_lineage_sqlite_path else "",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "verified_operator_evidence_intake_ready": status == READY_STATUS,
            "candidate_evidence_recorded": record.get("evidence_status") == EVIDENCE_STATUS_RECORDED,
            "payment_processing_evidence_does_not_mark_paid": (record.get("payment") or {}).get("paid") is False,
            "ledger_mutation_performed": False,
            "paid_marking_performed": False,
            "raw_ocr_text_stored": False,
            "raw_sensitive_detail_promoted_to_memory": False,
            "general_memory_promotion_allowed": False,
            "external_llm_invoked": False,
            "external_provider_connected": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
            "business_action_performed": False,
        },
    }
    payload["machine_proof"]["unsafe_true_grants"] = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants_absent"] = not payload["machine_proof"]["unsafe_true_grants"]
    return payload


def build_status_read_model_for_record(
    record: Mapping[str, Any],
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    artifact_lineage_sqlite_path: Path | None = DEFAULT_ARTIFACT_LINEAGE_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _precondition_rows(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    status = READY_STATUS if record.get("status") == READY_STATUS and preconditions_ready else NOT_READY_STATUS
    payload = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": STATUS_READ_MODEL_ID,
        "status": status,
        "generated_at": generated_at,
        "latest_record": dict(record),
        "dynamic_card": dict(record.get("dynamic_card") or {}),
        "preconditions": preconditions,
        "sqlite_path": str(_rooted(sqlite_path)),
        "artifact_lineage_sqlite_path": str(_rooted(artifact_lineage_sqlite_path)) if artifact_lineage_sqlite_path else "",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "verified_operator_evidence_intake_ready": status == READY_STATUS,
            "candidate_evidence_recorded": record.get("evidence_status") == EVIDENCE_STATUS_RECORDED,
            "payment_processing_evidence_does_not_mark_paid": (record.get("payment") or {}).get("paid") is False,
            "ledger_mutation_performed": False,
            "paid_marking_performed": False,
            "raw_ocr_text_stored": False,
            "raw_sensitive_detail_promoted_to_memory": False,
            "general_memory_promotion_allowed": False,
            "external_llm_invoked": False,
            "external_provider_connected": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
            "business_action_performed": False,
        },
    }
    payload["machine_proof"]["unsafe_true_grants"] = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants_absent"] = not payload["machine_proof"]["unsafe_true_grants"]
    return payload


def build_wiki(contract: Mapping[str, Any], status: Mapping[str, Any]) -> str:
    latest = status.get("latest_record") if isinstance(status.get("latest_record"), Mapping) else {}
    card = status.get("dynamic_card") if isinstance(status.get("dynamic_card"), Mapping) else {}
    return "\n".join(
        [
            "# Evidence Intake",
            "",
            f"Status: `{status.get('status', NOT_READY_STATUS)}`",
            "",
            "Evidence Intake records operator-dropped screenshots and files as candidate evidence. It is a local read-model and SQLite path, not business truth.",
            "",
            "## Boundary",
            "",
            "- Requires a verified Mission Control operator envelope.",
            "- Classifies payment screenshots as `financial_sensitive` and `local_only`.",
            "- Blocks external providers for financial screenshots.",
            "- Does not store raw OCR/text in general memory.",
            "- Does not mutate ledger, workbooks, Coupa, browser, Gmail, PDFs, send state, or paid truth.",
            "",
            "## Payment Proof",
            "",
            f"- Evidence status: `{latest.get('evidence_status', 'unknown')}`",
            f"- Payment state: `{(latest.get('payment') or {}).get('payment_state', 'unknown')}`",
            "- Payment-processing evidence is not paid proof.",
            "- Paid truth requires payment or ledger confirmation and operator review.",
            "",
            "## Dynamic Card",
            "",
            f"- Headline: `{card.get('headline', '')}`",
            f"- Status label: `{card.get('status_label', '')}`",
            f"- Trust state: `{card.get('trust_state', '')}`",
            f"- Summary: {card.get('summary', '')}",
            "",
            "## Artifacts",
            "",
            f"- Contract read model: `generated/read_models/{CONTRACT_JSON_EXPORT_NAME}`",
            f"- Status read model: `generated/read_models/{STATUS_JSON_EXPORT_NAME}`",
            f"- SQLite: `{status.get('sqlite_path', '')}`",
            "",
            "## Machine Proof",
            "",
            f"- Unsafe true grants absent: `{str((status.get('machine_proof') or {}).get('unsafe_true_grants_absent')).lower()}`",
            f"- Ledger mutation performed: `{str((status.get('machine_proof') or {}).get('ledger_mutation_performed')).lower()}`",
            f"- Paid marking performed: `{str((status.get('machine_proof') or {}).get('paid_marking_performed')).lower()}`",
        ]
    ) + "\n"


def publish_evidence_intake_status(
    record: Mapping[str, Any],
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    artifact_lineage_sqlite_path: Path | None = DEFAULT_ARTIFACT_LINEAGE_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    generated_at = generated_at or utc_now()
    contract = build_contract_read_model(read_model_root=read_model_root, generated_at=generated_at)
    status = build_status_read_model_for_record(
        record,
        read_model_root=read_model_root,
        sqlite_path=sqlite_path,
        artifact_lineage_sqlite_path=artifact_lineage_sqlite_path,
        generated_at=generated_at,
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
        "wiki_path": wiki_path.as_posix(),
    }


def export_evidence_intake(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    artifact_lineage_sqlite_path: Path | None = DEFAULT_ARTIFACT_LINEAGE_SQLITE_PATH,
    replace_status_snapshot: bool = True,
    generated_at: str | None = None,
) -> dict[str, str]:
    generated_at = generated_at or utc_now()
    contract = build_contract_read_model(read_model_root=read_model_root, generated_at=generated_at)
    status = build_status_read_model(
        read_model_root=read_model_root,
        sqlite_path=sqlite_path,
        artifact_lineage_sqlite_path=artifact_lineage_sqlite_path,
        replace_status_snapshot=replace_status_snapshot,
        generated_at=generated_at,
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
        "artifact_lineage_sqlite_path": str(_rooted(artifact_lineage_sqlite_path)) if artifact_lineage_sqlite_path else "",
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
    parser = argparse.ArgumentParser(description="Publish Verified Evidence Intake V0.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--artifact-lineage-sqlite-path", default=str(DEFAULT_ARTIFACT_LINEAGE_SQLITE_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--no-artifact-lineage", action="store_true")
    parser.add_argument("--append-status-snapshot", action="store_true")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_evidence_intake(
        export_root=Path(args.export_root),
        read_model_root=Path(args.read_model_root),
        bridge_root=None if args.no_bridge else Path(args.bridge_root),
        wiki_path=Path(args.wiki_path),
        sqlite_path=Path(args.sqlite_path),
        artifact_lineage_sqlite_path=None if args.no_artifact_lineage else Path(args.artifact_lineage_sqlite_path),
        replace_status_snapshot=not args.append_status_snapshot,
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result), end="")
    else:
        print(f"{result['status']}: {result['status_read_model_path']}")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
