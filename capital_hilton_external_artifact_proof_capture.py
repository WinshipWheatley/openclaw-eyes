"""Capital Hilton external artifact proof capture contract v0.

This read-model models protected metadata capture for external Coupa and Excel
invoice artifacts. It records evidence posture only. It does not create Coupa
invoices, submit portals, automate browsers, send email, write spreadsheets,
access credentials/PII, store raw artifact contents, or grant runtime/send/
submit/approval authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from capital_hilton_actionable_review_packet import DEFAULT_EXPORT_ROOT, stable_json


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "capital_hilton_external_artifact_proof_capture_v0"
JSON_EXPORT_NAME = "capital_hilton_external_artifact_proof_capture.json"
OPERATOR_EXPORT_NAME = "capital_hilton_external_artifact_proof_capture_OPERATOR.md"
WORKFLOW_ID = "capital_hilton_coupa_supplier_portal_invoice"

PROOF_TYPES = (
    "coupa_payment_invoice_proof",
    "excel_companion_invoice_artifact",
    "excel_coupa_match_proof",
)

EXPECTED_CAPITAL_HILTON_PROOF_CONTEXT = {
    "po_number": "DCASH00983536",
    "customer": "Hilton | Smart Spend",
    "po_status": "Issued - Pending Manual",
    "po_total": "4000.00 USD",
    "invoiced_to_date": "2000.00 USD",
    "apparent_remaining": "2000.00 USD",
    "line_item": "Musician",
    "requester": "Sam Getachew",
    "excel_companion_invoice": {
        "invoice_number": "2026-1005",
        "invoice_date": "2026-05-17",
        "total_due": "800.00 USD",
        "completed_service_dates": ["2026-05-08", "2026-05-15"],
        "rate": "400.00 USD per gig",
    },
}

NO_AUTHORITY_FLAGS = {
    "evidence_only": True,
    "no_external_action": True,
    "real_proof_recorded": False,
    "synthetic_or_test_proof_recorded": False,
    "coupa_invoice_created": False,
    "coupa_submit_triggered": False,
    "portal_submitted": False,
    "browser_automation_added": False,
    "email_send_enabled": False,
    "email_or_telegram_sent": False,
    "spreadsheet_write_triggered": False,
    "spreadsheet_cells_read": False,
    "credentials_accessed": False,
    "credential_or_pii_access_enabled": False,
    "raw_sensitive_artifact_stored_in_read_model": False,
    "raw_coupa_invoice_pdf_stored": False,
    "raw_excel_file_stored": False,
    "home_address_stored": False,
    "bank_details_stored": False,
    "portal_password_stored": False,
    "token_material_stored": False,
    "check_image_stored": False,
    "payment_marked_paid": False,
    "approval_authority_added": False,
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "repo_b_executed": False,
    "mission_control_app_changed": False,
}

_CREDENTIAL_PATTERN = re.compile(
    r"(?i)(password\s*(is|:|=)|login\s+is|api[_ -]?key\s*[:=]|token\s*[:=]|secret\s*[:=]|bearer\s+)"
)
_ALLOWED_METADATA_FIELDS = {
    "proof_type",
    "proof_status",
    "operator_supplied",
    "protected_artifact_reference",
    "protected_artifact_type",
    "artifact_identity_or_hash",
    "protected_reference_id",
    "protected_reference_path_token",
    "invoice_number",
    "invoice_date",
    "invoice_amount",
    "amount",
    "po_number",
    "po_reference",
    "service_dates",
    "match_status",
    "match_basis",
    "mismatch_reasons",
    "operator_confirmed",
    "operator_confirmation_status",
    "operator_confirmation_basis",
    "redaction_status",
    "protection_status",
    "source_basis",
    "date_captured",
    "captured_at",
    "synthetic_or_test",
}

_FORBIDDEN_INPUT_KEYS = {
    "raw_pdf_body",
    "raw_pdf_contents",
    "pdf_body",
    "pdf_contents",
    "raw_excel_body",
    "raw_excel_contents",
    "excel_body",
    "excel_contents",
    "raw_artifact_contents",
    "artifact_body",
    "portal_username",
    "portal_user",
    "portal_password",
    "password",
    "token",
    "api_key",
    "secret",
    "credential",
    "credentials",
    "bank_details",
    "bank_account",
    "routing_number",
    "remit_details",
    "home_address",
    "check_image",
    "check_image_bytes",
}


@dataclass(frozen=True)
class ExternalArtifactProofCaptureExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    coupa_invoice_proof_modeled: bool
    excel_companion_artifact_modeled: bool
    excel_coupa_match_proof_modeled: bool
    real_proof_recorded: bool
    final_send_approval_availability_state: str
    runtime_authority_added: bool
    send_or_submit_authority_added: bool
    proof_input_path: str
    operator_proof_intake_enabled: bool
    partial_proof_intake_supported: bool
    supplied_proof_count: int
    recorded_real_proof_count: int


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _rooted(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return ROOT / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _read_json_if_present(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    target = _rooted(path)
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _sanitize_text(value: object, *, max_len: int = 180) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return ""
    if _CREDENTIAL_PATTERN.search(text):
        return "[REDACTED credential-bearing metadata]"
    return text[:max_len]


def _sanitize_metadata_value(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, list):
        return [_sanitize_text(item, max_len=80) for item in value[:12]]
    if isinstance(value, tuple):
        return [_sanitize_text(item, max_len=80) for item in value[:12]]
    return _sanitize_text(value)


def _safe_metadata(raw: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key in _ALLOWED_METADATA_FIELDS:
        if key not in raw:
            continue
        safe[key] = _sanitize_metadata_value(raw[key])
    return safe


def _input_rejection_summary(raw_inputs: dict[str, Any] | None) -> dict[str, Any]:
    source = raw_inputs.get("proof_records") if isinstance(raw_inputs, dict) else {}
    if not isinstance(source, dict):
        source = {}
    per_proof: dict[str, dict[str, Any]] = {}
    refused_key_count = 0
    unsupported_key_count = 0
    for proof_type in PROOF_TYPES:
        raw = source.get(proof_type)
        if not isinstance(raw, dict):
            per_proof[proof_type] = {
                "forbidden_input_keys_refused": [],
                "unsupported_input_keys_ignored": [],
                "raw_sensitive_input_refused": False,
            }
            continue
        forbidden_keys = sorted(
            key for key in raw if str(key).strip().lower() in _FORBIDDEN_INPUT_KEYS
        )
        unsupported_keys = sorted(
            key
            for key in raw
            if str(key).strip().lower() not in _FORBIDDEN_INPUT_KEYS
            and key not in _ALLOWED_METADATA_FIELDS
        )
        refused_key_count += len(forbidden_keys)
        unsupported_key_count += len(unsupported_keys)
        per_proof[proof_type] = {
            "forbidden_input_keys_refused": forbidden_keys,
            "unsupported_input_keys_ignored": unsupported_keys,
            "raw_sensitive_input_refused": bool(forbidden_keys),
        }
    return {
        "raw_sensitive_input_refused": refused_key_count > 0,
        "forbidden_input_key_count": refused_key_count,
        "unsupported_input_key_count": unsupported_key_count,
        "forbidden_input_keys_are_not_stored_as_values": True,
        "per_proof_type": per_proof,
    }


def _input_for(raw: dict[str, Any] | None, proof_type: str) -> dict[str, Any]:
    if not raw:
        return {}
    source = raw.get("proof_records") if isinstance(raw.get("proof_records"), dict) else raw
    value = source.get(proof_type) if isinstance(source, dict) else None
    return value if isinstance(value, dict) else {}


def _proof_record(proof_type: str, raw: dict[str, Any], generated_at: str) -> dict[str, Any]:
    metadata = _safe_metadata(raw)
    operator_supplied = bool(metadata.get("operator_supplied"))
    synthetic = bool(metadata.get("synthetic_or_test"))
    identity = bool(metadata.get("artifact_identity_or_hash"))
    reference = bool(metadata.get("protected_artifact_reference"))
    explicit_status = str(metadata.get("proof_status") or "").strip().lower()
    explicit_captured = explicit_status in {"captured", "recorded", "verified"}

    if proof_type == "excel_coupa_match_proof":
        match_status = str(metadata.get("match_status") or "").strip().lower()
        captured = operator_supplied and identity and match_status in {"matched", "verified"}
        proof_status = "captured" if captured else "pending_not_recorded"
    else:
        captured = operator_supplied and identity and reference and explicit_captured
        proof_status = "captured" if captured else "pending_not_recorded"

    if synthetic and captured:
        proof_status = "synthetic_test_recorded_not_real"

    return {
        "proof_id": _row_id("cap_hilton_proof", proof_type, metadata.get("artifact_identity_or_hash", "pending")),
        "workflow": WORKFLOW_ID,
        "proof_type": proof_type,
        "proof_status": proof_status,
        "operator_supplied": operator_supplied,
        "protected_artifact_reference": metadata.get("protected_artifact_reference", ""),
        "protected_artifact_type": metadata.get("protected_artifact_type", proof_type),
        "artifact_identity_or_hash": metadata.get("artifact_identity_or_hash", ""),
        "protected_reference_id": metadata.get("protected_reference_id", ""),
        "protected_reference_path_token": metadata.get("protected_reference_path_token", ""),
        "invoice_number": metadata.get("invoice_number", ""),
        "invoice_date": metadata.get("invoice_date", ""),
        "invoice_amount": metadata.get("invoice_amount", metadata.get("amount", "")),
        "amount": metadata.get("amount", metadata.get("invoice_amount", "")),
        "po_number": metadata.get("po_number", metadata.get("po_reference", "")),
        "po_reference": metadata.get("po_reference", metadata.get("po_number", "")),
        "service_dates": metadata.get("service_dates", []),
        "match_status": metadata.get("match_status", "not_applicable" if proof_type != "excel_coupa_match_proof" else "pending"),
        "match_basis": metadata.get("match_basis", ""),
        "mismatch_reasons": metadata.get("mismatch_reasons", []),
        "operator_confirmed": bool(metadata.get("operator_confirmed", False)),
        "operator_confirmation_status": metadata.get("operator_confirmation_status", ""),
        "operator_confirmation_basis": metadata.get("operator_confirmation_basis", ""),
        "redaction_status": metadata.get("redaction_status", ""),
        "protection_status": metadata.get("protection_status", ""),
        "source_basis": metadata.get("source_basis", "operator_supplied_metadata_only" if operator_supplied else "not_supplied"),
        "date_captured": metadata.get("date_captured", ""),
        "captured_at": metadata.get("captured_at", metadata.get("date_captured", generated_at if captured else "")),
        "synthetic_or_test": synthetic,
        "raw_artifact_contents_stored": False,
        "raw_sensitive_artifact_stored_in_read_model": False,
        "no_external_action": True,
    }


def _proof_inputs_from_path(path: str | Path | None) -> dict[str, Any]:
    payload = _read_json_if_present(path)
    if not payload:
        return {}
    if isinstance(payload.get("proof_records"), dict):
        return payload
    return {"proof_records": {}}


def _operator_proof_intake_summary(
    *,
    raw_inputs: dict[str, Any],
    proof_input_json: str | Path | None,
    records: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    supplied = [proof_type for proof_type in PROOF_TYPES if bool(_input_for(raw_inputs, proof_type))]
    captured = [proof_type for proof_type, record in records.items() if record["proof_status"] == "captured"]
    synthetic = [
        proof_type
        for proof_type, record in records.items()
        if record["proof_status"] == "synthetic_test_recorded_not_real"
    ]
    pending = [proof_type for proof_type, record in records.items() if record["proof_status"] == "pending_not_recorded"]
    rejection_summary = _input_rejection_summary(raw_inputs)
    return {
        "intake_path_added": True,
        "command_path": "scripts/export_capital_hilton_external_artifact_proof_capture.py --proof-input-json <path>",
        "proof_input_path": _display_path(proof_input_json) if proof_input_json else "",
        "proof_input_supplied": bool(supplied),
        "partial_proof_intake_supported": True,
        "supported_proof_types": list(PROOF_TYPES),
        "supported_metadata_fields": sorted(_ALLOWED_METADATA_FIELDS),
        "supplied_proof_count": len(supplied),
        "recorded_real_proof_count": len(captured),
        "pending_proof_count": len(pending),
        "synthetic_test_proof_count": len(synthetic),
        "supplied_proof_types": supplied,
        "recorded_real_proof_types": captured,
        "pending_proof_types": pending,
        "synthetic_test_proof_types": synthetic,
        "requires_operator_supplied_true": True,
        "requires_protected_reference_or_identity_metadata": True,
        "metadata_only": True,
        "raw_artifact_contents_allowed": False,
        "raw_sensitive_input_refused": rejection_summary["raw_sensitive_input_refused"],
        "forbidden_input_key_count": rejection_summary["forbidden_input_key_count"],
        "unsupported_input_key_count": rejection_summary["unsupported_input_key_count"],
        "input_rejection_summary": rejection_summary,
        "no_external_action": True,
    }


def final_send_prerequisite_status_from_records(records: dict[str, dict[str, Any]]) -> dict[str, bool]:
    coupa = records["coupa_payment_invoice_proof"]
    excel = records["excel_companion_invoice_artifact"]
    match = records["excel_coupa_match_proof"]
    coupa_captured = coupa["proof_status"] == "captured"
    excel_captured = excel["proof_status"] == "captured"
    match_captured = match["proof_status"] == "captured"
    return {
        "coupa_invoice_proof_exists": coupa_captured,
        "coupa_invoice_proof_references_expected_po_invoice_context": coupa_captured and bool(coupa.get("po_number")),
        "excel_companion_invoice_artifact_exists": excel_captured,
        "excel_companion_invoice_verified_to_match_coupa": match_captured,
        "cassandra_email_draft_exists": False,
        "attachment_reference_exists": False,
        "draft_identity_hash_reference_exists": False,
        "attachment_identity_hash_reference_exists": False,
        "no_unresolved_critical_blockers": False,
        "guardian_start_approval_recorded_or_required_upstream": True,
    }


def _capital_hilton_proof_evidence_rail(
    *,
    records: dict[str, dict[str, Any]],
    prerequisites: dict[str, bool],
    availability: str,
) -> dict[str, Any]:
    coupa = records["coupa_payment_invoice_proof"]
    excel = records["excel_companion_invoice_artifact"]
    match = records["excel_coupa_match_proof"]
    return {
        "rail_id": "capital_hilton_two_invoice_proof_evidence_rail_v0",
        "workflow": WORKFLOW_ID,
        "rail_status": "eligible_for_final_send_review"
        if availability == "available_for_guardian_send_approval"
        else "blocked_waiting_for_governed_proof",
        "operator_meaning": (
            "Tracks the protected evidence facts needed before Capital Hilton final send approval can be requested."
        ),
        "expected_context": EXPECTED_CAPITAL_HILTON_PROOF_CONTEXT,
        "proof_lanes": [
            {
                "lane_id": "payment_invoice_proof",
                "operator_label": "Coupa supplier-portal payment invoice proof",
                "proof_type": "coupa_payment_invoice_proof",
                "proof_status": coupa["proof_status"],
                "present_now": bool(prerequisites["coupa_invoice_proof_exists"]),
                "references_expected_po_context": bool(
                    prerequisites["coupa_invoice_proof_references_expected_po_invoice_context"]
                ),
                "required_to_unlock_final_send_review": True,
                "raw_artifact_stored_in_read_model": False,
            },
            {
                "lane_id": "companion_invoice_match_proof",
                "operator_label": "Excel companion invoice match proof",
                "proof_type": "excel_coupa_match_proof",
                "proof_status": match["proof_status"],
                "excel_companion_artifact_status": excel["proof_status"],
                "excel_companion_artifact_present_now": bool(
                    prerequisites["excel_companion_invoice_artifact_exists"]
                ),
                "match_verified_now": bool(prerequisites["excel_companion_invoice_verified_to_match_coupa"]),
                "required_to_unlock_final_send_review": True,
                "raw_artifact_stored_in_read_model": False,
            },
        ],
        "final_send_approval_eligibility": {
            "availability_state": availability,
            "payment_invoice_proof_present": bool(prerequisites["coupa_invoice_proof_exists"]),
            "companion_invoice_match_verified": bool(
                prerequisites["excel_companion_invoice_verified_to_match_coupa"]
            ),
            "eligible_for_guardian_final_send_approval_review": availability == "available_for_guardian_send_approval",
            "send_execution_available_now": False,
        },
        "protected_evidence_boundary": {
            "metadata_only": True,
            "raw_coupa_pdf_stored": False,
            "raw_excel_file_stored": False,
            "home_address_or_bank_details_stored": False,
            "portal_credentials_or_tokens_stored": False,
            "external_action_taken": False,
        },
    }


def _availability_from_prerequisites(prerequisites: dict[str, bool]) -> str:
    if not prerequisites["coupa_invoice_proof_exists"]:
        return "unavailable_missing_coupa_invoice_proof"
    if not prerequisites["excel_companion_invoice_artifact_exists"]:
        return "unavailable_missing_excel_companion_invoice"
    if not prerequisites["excel_companion_invoice_verified_to_match_coupa"]:
        return "unavailable_missing_excel_match_proof"
    if not prerequisites["cassandra_email_draft_exists"]:
        return "unavailable_missing_email_draft"
    if not prerequisites["attachment_reference_exists"]:
        return "unavailable_missing_attachment_reference"
    if not prerequisites["no_unresolved_critical_blockers"]:
        return "unavailable_unresolved_critical_blockers"
    return "available_for_guardian_send_approval"


def build_capital_hilton_external_artifact_proof_capture(
    *,
    proof_inputs: dict[str, Any] | None = None,
    proof_input_json: str | Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    ts = generated_at or utc_now()
    raw_inputs = proof_inputs if proof_inputs is not None else _proof_inputs_from_path(proof_input_json)
    records = {
        proof_type: _proof_record(proof_type, _input_for(raw_inputs, proof_type), ts)
        for proof_type in PROOF_TYPES
    }
    prerequisites = final_send_prerequisite_status_from_records(records)
    availability = _availability_from_prerequisites(prerequisites)
    proof_evidence_rail = _capital_hilton_proof_evidence_rail(
        records=records,
        prerequisites=prerequisites,
        availability=availability,
    )
    real_proof_recorded = any(item["proof_status"] == "captured" for item in records.values())
    synthetic_recorded = any(item["proof_status"] == "synthetic_test_recorded_not_real" for item in records.values())
    no_authority = dict(NO_AUTHORITY_FLAGS)
    no_authority["real_proof_recorded"] = real_proof_recorded
    no_authority["synthetic_or_test_proof_recorded"] = synthetic_recorded
    intake_summary = _operator_proof_intake_summary(
        raw_inputs=raw_inputs,
        proof_input_json=proof_input_json,
        records=records,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": ts,
        "packet_kind": "external_artifact_proof_capture_contract",
        "workflow": WORKFLOW_ID,
        "workflow_scope": "Capital Hilton / Hilton only",
        "capture_mode": "operator_supplied_safe_metadata_only",
        "operator_proof_intake": intake_summary,
        "proof_records": records,
        "capital_hilton_proof_evidence_rail": proof_evidence_rail,
        "supported_metadata_fields": sorted(_ALLOWED_METADATA_FIELDS),
        "proof_capture_requirements": {
            "proof_requires_explicit_operator_input_or_safe_metadata": True,
            "missing_input_does_not_create_proof": True,
            "synthetic_test_proof_never_counts_as_real": True,
            "raw_artifact_contents_allowed_in_read_models": False,
            "raw_sensitive_input_values_refused": True,
            "unsupported_input_fields_ignored": True,
        },
        "final_send_approval_prerequisites": prerequisites,
        "final_send_approval_availability_state": availability,
        "final_send_approval_remains_blocked_without_required_proof": availability != "available_for_guardian_send_approval",
        "status_summary": {
            "proof_evidence_rail_status": proof_evidence_rail["rail_status"],
            "coupa_invoice_proof_status": records["coupa_payment_invoice_proof"]["proof_status"],
            "excel_companion_artifact_status": records["excel_companion_invoice_artifact"]["proof_status"],
            "excel_coupa_match_proof_status": records["excel_coupa_match_proof"]["proof_status"],
            "real_proof_recorded": real_proof_recorded,
            "recorded_real_proof_count": intake_summary["recorded_real_proof_count"],
            "supplied_proof_count": intake_summary["supplied_proof_count"],
            "pending_proof_count": intake_summary["pending_proof_count"],
            "partial_proof_intake_supported": True,
            "paid_status": False,
            "final_send_approval_availability_state": availability,
            "raw_sensitive_artifact_stored_in_read_model": False,
            "raw_sensitive_input_refused": intake_summary["raw_sensitive_input_refused"],
            "forbidden_input_key_count": intake_summary["forbidden_input_key_count"],
            "unsupported_input_key_count": intake_summary["unsupported_input_key_count"],
            "no_submit_no_browser_no_email_no_spreadsheet_no_secret_storage": True,
        },
        "authority_boundary": {
            "evidence_only": True,
            "no_authority_flags": no_authority,
            "raw_sensitive_artifact_stored_in_read_model": False,
            "coupa_submit_triggered": False,
            "browser_automation_added": False,
            "email_send_enabled": False,
            "spreadsheet_write_triggered": False,
            "runtime_authority_added": False,
            "approval_authority_added": False,
        },
        "generalization_posture": {
            "pattern_name": "external_artifact_proof_capture_v0",
            "capital_hilton_is_first_proof_case": True,
            "future_workflows_may_reuse": True,
            "requires_client_specific_authority_boundary": True,
        },
        "boundaries": no_authority,
        **no_authority,
        "next_recommended_lane": "Capital Hilton Proof Capture Operator Surface v0",
    }


def format_capital_hilton_external_artifact_proof_capture(payload: dict[str, Any]) -> str:
    lines = [
        "# Capital Hilton External Artifact Proof Capture",
        "",
        "Status:",
        f"- Coupa invoice proof: `{payload['status_summary']['coupa_invoice_proof_status']}`.",
        f"- Excel companion invoice artifact: `{payload['status_summary']['excel_companion_artifact_status']}`.",
        f"- Excel-vs-Coupa match proof: `{payload['status_summary']['excel_coupa_match_proof_status']}`.",
        f"- Final send approval availability: `{payload['final_send_approval_availability_state']}`.",
        f"- Proof evidence rail: `{payload['capital_hilton_proof_evidence_rail']['rail_status']}`.",
        "- Raw sensitive artifacts stored in read-model: `false`.",
        "- Coupa/browser/email/spreadsheet/credential/runtime authority added: `false`.",
        "",
        "## Operator Proof Intake",
        f"- Command path: `{payload['operator_proof_intake']['command_path']}`.",
        f"- Proof input supplied: `{str(payload['operator_proof_intake']['proof_input_supplied']).lower()}`.",
        f"- Supplied proof count: `{payload['operator_proof_intake']['supplied_proof_count']}`.",
        f"- Recorded real proof count: `{payload['operator_proof_intake']['recorded_real_proof_count']}`.",
        "- Intake accepts protected references and metadata only; raw artifact bodies are not allowed.",
        f"- Forbidden raw/sensitive input keys refused: `{payload['operator_proof_intake']['forbidden_input_key_count']}`.",
        "",
        "## Proof Records",
    ]
    for proof_type, record in payload["proof_records"].items():
        lines.append(f"- `{proof_type}`: {record['proof_status']} (operator supplied: `{str(record['operator_supplied']).lower()}`)")
    lines.extend(["", "## Final Send Approval Prerequisites"])
    for key, present in payload["final_send_approval_prerequisites"].items():
        lines.append(f"- `{key}`: `{str(bool(present)).lower()}`")
    lines.extend(["", "## Proof Evidence Rail"])
    for lane in payload["capital_hilton_proof_evidence_rail"]["proof_lanes"]:
        lines.append(
            f"- {lane['operator_label']}: `{lane['proof_status']}`; required before final send review: `true`."
        )
    lines.extend([
        "",
        "## Boundary",
        "- Evidence only; no external action was taken.",
        "- No raw Coupa PDFs, Excel files, credentials, bank details, portal passwords, token material, or check images are stored in normal read-models.",
        "- Final send approval stays blocked until Coupa proof, Excel artifact, Excel-vs-Coupa match proof, draft identity, attachment identity, and blocker clearance exist.",
        "",
        f"Next safe lane: {payload['next_recommended_lane']}",
        "",
    ])
    return "\n".join(lines)


def export_capital_hilton_external_artifact_proof_capture(
    *,
    proof_input_json: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> ExternalArtifactProofCaptureExportResult:
    payload = build_capital_hilton_external_artifact_proof_capture(
        proof_input_json=proof_input_json,
        generated_at=generated_at,
    )
    root = _rooted(export_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_capital_hilton_external_artifact_proof_capture(payload), encoding="utf-8")
    return ExternalArtifactProofCaptureExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        coupa_invoice_proof_modeled=True,
        excel_companion_artifact_modeled=True,
        excel_coupa_match_proof_modeled=True,
        real_proof_recorded=payload["status_summary"]["real_proof_recorded"],
        final_send_approval_availability_state=payload["final_send_approval_availability_state"],
        runtime_authority_added=False,
        send_or_submit_authority_added=False,
        proof_input_path=payload["operator_proof_intake"]["proof_input_path"],
        operator_proof_intake_enabled=True,
        partial_proof_intake_supported=True,
        supplied_proof_count=payload["operator_proof_intake"]["supplied_proof_count"],
        recorded_real_proof_count=payload["operator_proof_intake"]["recorded_real_proof_count"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Capital Hilton external artifact proof capture read-model.")
    parser.add_argument("--proof-input-json", default=None)
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_capital_hilton_external_artifact_proof_capture(
        proof_input_json=args.proof_input_json,
        export_root=args.export_root,
    )
    root = _rooted(args.export_root)
    if args.format == "json":
        print((root / JSON_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    elif args.format == "operator":
        print((root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    else:
        print(stable_json(result.__dict__), end="")
    return 0


__all__ = [
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "PROOF_TYPES",
    "SCHEMA_VERSION",
    "WORKFLOW_ID",
    "EXPECTED_CAPITAL_HILTON_PROOF_CONTEXT",
    "build_capital_hilton_external_artifact_proof_capture",
    "export_capital_hilton_external_artifact_proof_capture",
    "final_send_prerequisite_status_from_records",
    "format_capital_hilton_external_artifact_proof_capture",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
