"""Protected evidence reference receipt contract v0.

This module defines the deterministic receipt shape for sensitive proof that is
represented by protected references only. It does not store raw sensitive
content, access protected artifacts, approve anything, automate browsers, call
external accounts, send messages, inspect Repo B, or grant runtime authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from protected_access_broker_concept import (
    NORMAL_READ_MODEL_FORBIDDEN_VALUES,
    SAFE_METADATA_FIELDS,
    build_protected_access_broker_concept,
    stable_json,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "protected_evidence_reference_receipt_v0"
JSON_EXPORT_NAME = "protected_evidence_reference_receipt.json"
OPERATOR_EXPORT_NAME = "protected_evidence_reference_receipt_OPERATOR.md"

RECEIPT_STATUSES = (
    "REFERENCE_MISSING",
    "REFERENCE_RECORDED",
    "METADATA_INCOMPLETE",
    "METADATA_VALID",
    "METADATA_INVALID",
    "RAW_CONTENT_REJECTED",
    "PROTECTED_ACCESS_REQUIRED",
    "UNKNOWN_FAIL_CLOSED",
)

RECEIPT_TYPES = (
    "coupa_payment_invoice_proof_reference",
    "excel_companion_artifact_reference",
    "pdf_invoice_artifact_reference",
    "gmail_email_evidence_reference",
    "calendar_evidence_reference",
    "bank_remit_home_check_image_sensitive_reference",
    "client_credential_reference",
    "unknown_sensitive_surface_reference",
)

ALLOWED_RECEIPT_METADATA_FIELDS = tuple(
    dict.fromkeys(
        (
            "receipt_type",
            "workflow_id",
            "workflow_name",
            "protected_reference_id",
            "protected_reference_path_token",
            "protected_artifact_reference",
            "protected_evidence_type",
            "source_system_label",
            "artifact_identity_or_hash",
            "invoice_number",
            "portal_invoice_reference",
            "po_reference",
            "amount",
            "service_dates",
            "capture_recorded_at",
            "date_captured",
            "operator_supplied",
            "operator_confirmation_status",
            "operator_source_confirmation",
            "validation_status",
            "match_status",
            "mismatch_reasons",
            "redaction_status",
            "protection_status",
            "future_gate_required_before_access_use",
            *SAFE_METADATA_FIELDS,
        )
    )
)

FORBIDDEN_RAW_CONTENT_FIELDS = (
    "raw_pdf_body",
    "raw_pdf_contents",
    "pdf_body",
    "pdf_contents",
    "raw_excel_body",
    "raw_excel_contents",
    "excel_body",
    "excel_contents",
    "raw_document_body",
    "raw_private_document",
    "raw_artifact_contents",
    "artifact_body",
    "raw_email_body",
    "raw_gmail_body",
    "raw_calendar_body",
    "portal_username",
    "portal_password",
    "password",
    "token",
    "oauth_token",
    "refresh_token",
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
    "browser_session_cookie",
)

NO_AUTHORITY_FLAGS = {
    "receipt_contract_only": True,
    "real_sensitive_proof_recorded": False,
    "raw_content_stored": False,
    "raw_pdf_or_excel_stored": False,
    "raw_private_document_stored": False,
    "credentials_or_tokens_stored": False,
    "pii_bank_remit_check_image_stored": False,
    "raw_access_granted": False,
    "protected_artifact_access_granted": False,
    "receipt_is_approval_authority": False,
    "receipt_is_execution_authority": False,
    "approval_authority_added": False,
    "execution_authority_added": False,
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "browser_automation_added": False,
    "coupa_accessed": False,
    "gmail_calendar_accessed": False,
    "oauth_access_enabled": False,
    "credentials_accessed": False,
    "telegram_send_triggered": False,
    "email_send_triggered": False,
    "pdf_generated_or_attached": False,
    "spreadsheet_mutation_triggered": False,
    "guardian_live_message_sent": False,
    "mission_control_app_changed": False,
    "repo_b_filesystem_inspected": False,
    "repo_b_code_executed": False,
    "security_pass_started": False,
}

SECRET_PATTERN = re.compile(
    r"(?i)(password\s*(is|:|=)|token\s*[:=]|oauth\s*[:=]|refresh[_ -]?token\s*[:=]|secret\s*[:=]|api[_ -]?key\s*[:=]|bearer\s+)"
)


@dataclass(frozen=True)
class ProtectedEvidenceReferenceReceiptExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    receipt_template_count: int
    real_sensitive_proof_recorded: bool
    raw_content_stored: bool
    runtime_authority_added: bool
    send_or_submit_authority_added: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _rooted(path: str | Path, *, repo_root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(repo_root) / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _read_json_if_present(path: str | Path, *, repo_root: str | Path = ROOT) -> dict[str, Any]:
    target = _rooted(path, repo_root=repo_root)
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _receipt_id(receipt_type: str, protected_reference_id: object = "") -> str:
    digest = hashlib.sha256(f"{receipt_type}\0{protected_reference_id or 'missing'}".encode("utf-8")).hexdigest()
    return f"protected_ref_receipt_{digest[:20]}"


def _sanitize_text(value: object, *, max_len: int = 180) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return ""
    if SECRET_PATTERN.search(text):
        return "[REDACTED sensitive metadata]"
    return text[:max_len]


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [_sanitize_text(item, max_len=80) for item in value[:16]]
    return _sanitize_text(value)


def _safe_metadata(raw: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key in ALLOWED_RECEIPT_METADATA_FIELDS:
        if key in raw:
            safe[key] = _sanitize_value(raw[key])
    return safe


def _receipt_kind_definitions() -> tuple[dict[str, Any], ...]:
    return (
        {
            "receipt_type": "coupa_payment_invoice_proof_reference",
            "workflow_id": "capital_hilton_coupa_supplier_portal_invoice",
            "workflow_name": "Capital Hilton Coupa supplier-portal invoice",
            "protected_evidence_type": "coupa_payment_invoice_proof",
            "surface_id": "capital_hilton_coupa_payment_invoice_proof",
            "required_safe_metadata": ("protected_reference_id", "artifact_identity_or_hash", "po_reference", "amount"),
            "future_gate_required_before_access_use": "Guardian protected access gate plus security-threshold controls before Coupa artifact access or use",
        },
        {
            "receipt_type": "excel_companion_artifact_reference",
            "workflow_id": "capital_hilton_coupa_supplier_portal_invoice",
            "workflow_name": "Capital Hilton Excel companion invoice",
            "protected_evidence_type": "excel_companion_invoice_artifact",
            "surface_id": "capital_hilton_excel_pdf_invoice_artifacts",
            "required_safe_metadata": ("protected_reference_id", "artifact_identity_or_hash", "invoice_number", "amount"),
            "future_gate_required_before_access_use": "Guardian protected access gate plus spreadsheet/PDF execution controls before opening or generating artifacts",
        },
        {
            "receipt_type": "pdf_invoice_artifact_reference",
            "workflow_id": "capital_hilton_coupa_supplier_portal_invoice",
            "workflow_name": "Invoice PDF protected reference",
            "protected_evidence_type": "pdf_invoice_artifact",
            "surface_id": "capital_hilton_excel_pdf_invoice_artifacts",
            "required_safe_metadata": ("protected_reference_id", "artifact_identity_or_hash", "invoice_number"),
            "future_gate_required_before_access_use": "Guardian protected access gate before attaching, opening, or sending PDF artifacts",
        },
        {
            "receipt_type": "gmail_email_evidence_reference",
            "workflow_id": "cassandra_outward_email_review",
            "workflow_name": "Cassandra email evidence",
            "protected_evidence_type": "gmail_email_evidence",
            "surface_id": "gmail_email_send_or_draft",
            "required_safe_metadata": ("protected_reference_id", "artifact_identity_or_hash", "source_system_label"),
            "future_gate_required_before_access_use": "Guardian final-send or account-access gate before Gmail access or send",
        },
        {
            "receipt_type": "calendar_evidence_reference",
            "workflow_id": "calendar_governed_reference",
            "workflow_name": "Calendar evidence reference",
            "protected_evidence_type": "calendar_evidence",
            "surface_id": "calendar_access",
            "required_safe_metadata": ("protected_reference_id", "source_system_label"),
            "future_gate_required_before_access_use": "Guardian protected access gate before calendar account access",
        },
        {
            "receipt_type": "bank_remit_home_check_image_sensitive_reference",
            "workflow_id": "payment_verification_reference",
            "workflow_name": "Payment/remit/check image protected reference",
            "protected_evidence_type": "bank_remit_home_check_image_reference",
            "surface_id": "bank_remit_home_address_check_images",
            "required_safe_metadata": ("protected_reference_id", "redaction_status", "protection_status"),
            "future_gate_required_before_access_use": "Guardian protected access gate plus money-ledger/payment verification controls",
        },
        {
            "receipt_type": "client_credential_reference",
            "workflow_id": "client_specific_protected_access",
            "workflow_name": "Client/company credential protected reference",
            "protected_evidence_type": "client_credential_reference",
            "surface_id": "client_company_credentials",
            "required_safe_metadata": ("protected_reference_id", "source_system_label", "protection_status"),
            "future_gate_required_before_access_use": "Credential broker security threshold and scoped Guardian gate before any credential use",
        },
        {
            "receipt_type": "unknown_sensitive_surface_reference",
            "workflow_id": "unknown_sensitive_surface",
            "workflow_name": "Unknown sensitive surface",
            "protected_evidence_type": "unknown_sensitive_surface",
            "surface_id": "unknown_sensitive_surface",
            "required_safe_metadata": ("protected_reference_id",),
            "future_gate_required_before_access_use": "classification lane and operator review before any protected access",
        },
    )


def _input_for(raw_inputs: dict[str, Any] | None, receipt_type: str) -> dict[str, Any]:
    if not isinstance(raw_inputs, dict):
        return {}
    source = raw_inputs.get("protected_evidence_references")
    if not isinstance(source, dict):
        source = raw_inputs
    raw = source.get(receipt_type) if isinstance(source, dict) else None
    return raw if isinstance(raw, dict) else {}


def _forbidden_keys(raw: dict[str, Any]) -> list[str]:
    return sorted(key for key in raw if str(key).strip().lower() in FORBIDDEN_RAW_CONTENT_FIELDS)


def _unsupported_keys(raw: dict[str, Any]) -> list[str]:
    return sorted(
        key
        for key in raw
        if str(key).strip().lower() not in FORBIDDEN_RAW_CONTENT_FIELDS
        and key not in ALLOWED_RECEIPT_METADATA_FIELDS
    )


def _receipt_status(kind: dict[str, Any], raw: dict[str, Any], metadata: dict[str, Any], forbidden: list[str]) -> str:
    if kind["receipt_type"] == "unknown_sensitive_surface_reference":
        return "UNKNOWN_FAIL_CLOSED"
    if forbidden:
        return "RAW_CONTENT_REJECTED"
    if not raw:
        return "REFERENCE_MISSING"
    if not metadata.get("protected_reference_id") and not metadata.get("protected_reference_path_token"):
        return "METADATA_INCOMPLETE"
    required = set(kind["required_safe_metadata"])
    missing = [field for field in required if not metadata.get(field)]
    if missing:
        return "METADATA_INCOMPLETE"
    validation = str(metadata.get("validation_status") or "").strip().lower()
    if validation in {"invalid", "mismatch", "failed"}:
        return "METADATA_INVALID"
    if validation in {"valid", "verified", "metadata_valid"}:
        return "METADATA_VALID"
    return "REFERENCE_RECORDED"


def _missing_required_metadata(kind: dict[str, Any], metadata: dict[str, Any]) -> list[str]:
    return [field for field in kind["required_safe_metadata"] if not metadata.get(field)]


def protected_reference_receipt_record(
    kind: dict[str, Any],
    raw_input: dict[str, Any] | None = None,
    *,
    generated_at: str,
) -> dict[str, Any]:
    raw = raw_input if isinstance(raw_input, dict) else {}
    metadata = _safe_metadata(raw)
    forbidden = _forbidden_keys(raw)
    unsupported = _unsupported_keys(raw)
    status = _receipt_status(kind, raw, metadata, forbidden)
    missing = _missing_required_metadata(kind, metadata)
    protected_reference_id = str(metadata.get("protected_reference_id") or "")
    receipt_id = _receipt_id(kind["receipt_type"], protected_reference_id)
    return {
        "receipt_id": receipt_id,
        "receipt_type": kind["receipt_type"],
        "workflow_id": metadata.get("workflow_id", kind["workflow_id"]),
        "workflow_name": metadata.get("workflow_name", kind["workflow_name"]),
        "protected_reference_id": protected_reference_id,
        "protected_reference_path_token": metadata.get("protected_reference_path_token", ""),
        "protected_artifact_reference": metadata.get("protected_artifact_reference", ""),
        "protected_evidence_type": metadata.get("protected_evidence_type", kind["protected_evidence_type"]),
        "surface_id": kind["surface_id"],
        "receipt_status": status,
        "allowed_metadata_fields": list(ALLOWED_RECEIPT_METADATA_FIELDS),
        "safe_metadata": metadata,
        "required_safe_metadata": list(kind["required_safe_metadata"]),
        "missing_required_metadata": missing,
        "forbidden_raw_content_fields": list(FORBIDDEN_RAW_CONTENT_FIELDS),
        "forbidden_input_keys_refused": forbidden,
        "unsupported_input_keys_ignored": unsupported,
        "raw_content_rejected": bool(forbidden),
        "raw_content_stored": False,
        "underlying_raw_artifact_truth_proven": False,
        "protected_reference_truth_proven": status in {"METADATA_VALID", "REFERENCE_RECORDED"},
        "redaction_status": metadata.get("redaction_status", "not_supplied"),
        "protection_status": metadata.get("protection_status", "protected_reference_required"),
        "capture_recorded_at": metadata.get("capture_recorded_at", metadata.get("date_captured", generated_at if raw else "")),
        "operator_source_confirmation": metadata.get("operator_source_confirmation", metadata.get("operator_confirmation_status", "not_supplied")),
        "validation_status": metadata.get("validation_status", status),
        "mismatch_error_reasons": metadata.get("mismatch_reasons", []),
        "future_gate_required_before_access_use": metadata.get(
            "future_gate_required_before_access_use",
            kind["future_gate_required_before_access_use"],
        ),
        "access_use_status": "PROTECTED_ACCESS_REQUIRED",
        "future_access_or_use_requires_guardian_gate": True,
        "future_access_or_use_requires_security_threshold": True,
        "receipt_grants_raw_access": False,
        "receipt_grants_approval_authority": False,
        "receipt_grants_execution_authority": False,
        "receipt_grants_send_or_submit_authority": False,
        "agent_direct_access_allowed": False,
        "explicit_authority_exclusions": [
            "raw artifact access",
            "credential/OAuth access",
            "browser automation",
            "Gmail/calendar/Coupa access",
            "approval authority",
            "execution authority",
            "send/submit authority",
            "runtime authority",
        ],
        "operator_next_safe_move": (
            "Record only protected-reference metadata; use a later Guardian/security-threshold lane before opening or using the artifact."
        ),
    }


def build_receipt_records(
    *,
    receipt_inputs: dict[str, Any] | None = None,
    generated_at: str,
) -> tuple[dict[str, Any], ...]:
    return tuple(
        protected_reference_receipt_record(
            kind,
            _input_for(receipt_inputs, kind["receipt_type"]),
            generated_at=generated_at,
        )
        for kind in _receipt_kind_definitions()
    )


def _receipt_summary(records: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    counts = Counter(record["receipt_status"] for record in records)
    refused = sum(len(record["forbidden_input_keys_refused"]) for record in records)
    recorded = sum(
        1
        for record in records
        if record["receipt_status"] in {"REFERENCE_RECORDED", "METADATA_VALID", "METADATA_INVALID", "RAW_CONTENT_REJECTED"}
    )
    return {
        "receipt_record_count": len(records),
        "recorded_reference_count": recorded,
        "real_sensitive_proof_recorded": False,
        "raw_content_rejected_count": refused,
        "status_counts": {status: counts.get(status, 0) for status in RECEIPT_STATUSES},
        "unknown_fail_closed_count": counts.get("UNKNOWN_FAIL_CLOSED", 0),
        "reference_missing_count": counts.get("REFERENCE_MISSING", 0),
    }


def _contract_shape() -> dict[str, Any]:
    return {
        "contract_id": "protected_evidence_reference_receipt_v0",
        "contract_kind": "protected_evidence_reference_receipt",
        "required_fields": [
            "receipt_id",
            "workflow_id",
            "workflow_name",
            "protected_reference_id",
            "protected_reference_path_token",
            "protected_evidence_type",
            "receipt_status",
            "allowed_metadata_fields",
            "forbidden_raw_content_fields",
            "redaction_status",
            "protection_status",
            "capture_recorded_at",
            "operator_source_confirmation",
            "validation_status",
            "mismatch_error_reasons",
            "future_gate_required_before_access_use",
            "explicit_authority_exclusions",
            "operator_next_safe_move",
        ],
        "receipt_proves_only": [
            "a protected reference or metadata receipt record exists",
            "the workflow and evidence type it is associated with",
            "which safe metadata fields were recorded",
            "which raw content fields were refused",
            "what future gate is required before access or use",
        ],
        "receipt_does_not_prove": [
            "the underlying raw artifact is true",
            "the protected artifact was opened or validated",
            "the operator approved an action",
            "execution, browser, credential, OAuth, send, submit, or runtime authority",
        ],
        "safe_metadata_fields": list(ALLOWED_RECEIPT_METADATA_FIELDS),
        "forbidden_raw_content_fields": list(FORBIDDEN_RAW_CONTENT_FIELDS),
        "receipt_statuses": list(RECEIPT_STATUSES),
    }


def _eli5_summary() -> dict[str, Any]:
    return {
        "openclaw_can_remember_protected_proof_exists": (
            "OpenClaw can record a safe reference saying protected proof exists for a workflow."
        ),
        "stores_only_safe_metadata_reference_not_secret_raw_file": (
            "The receipt stores IDs, hashes, dates, labels, and status, not passwords, raw PDFs, raw spreadsheets, bank details, or private bodies."
        ),
        "receipt_does_not_give_agents_access": "The receipt is not a key; agents still cannot open the protected artifact.",
        "receipt_does_not_authorize_execution": "The receipt does not approve sends, browser actions, portal submits, spreadsheet writes, or runtime work.",
        "future_gates_still_required_before_using_proof": (
            "Guardian and security-threshold controls are still required before any sensitive artifact is opened or used."
        ),
        "what_this_unlocks_later": (
            "Future workflows can cite protected proof references without copying secrets or raw private content into normal read-models."
        ),
    }


def build_protected_evidence_reference_receipt(
    *,
    repo_root: str | Path = ROOT,
    receipt_inputs: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    ts = generated_at or utc_now()
    concept_payload = _read_json_if_present(
        DEFAULT_EXPORT_ROOT / "protected_access_broker_concept.json",
        repo_root=repo_root,
    )
    if not concept_payload:
        concept_payload = build_protected_access_broker_concept(repo_root=repo_root, generated_at=ts)
    records = build_receipt_records(receipt_inputs=receipt_inputs, generated_at=ts)
    summary = _receipt_summary(records)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": ts,
        "purpose": "Define protected evidence reference receipts without raw sensitive content or access authority.",
        "source_concept": {
            "schema_version": concept_payload.get("schema_version"),
            "path": "generated/read_models/protected_access_broker_concept.json",
            "used_existing_repo_a_read_model_or_contract_only": True,
        },
        "receipt_contract": _contract_shape(),
        "receipt_statuses": list(RECEIPT_STATUSES),
        "receipt_types": list(RECEIPT_TYPES),
        "normal_read_model_forbidden_values": list(NORMAL_READ_MODEL_FORBIDDEN_VALUES),
        "allowed_metadata_fields": list(ALLOWED_RECEIPT_METADATA_FIELDS),
        "receipt_records": list(records),
        "receipt_summary": summary,
        "operator_eli5_summary": _eli5_summary(),
        "authority_boundary": {
            "receipt_is_reference_only": True,
            "receipt_is_not_approval_authority": True,
            "receipt_is_not_execution_authority": True,
            "receipt_does_not_grant_raw_access": True,
            "future_guardian_gate_required_before_access_use": True,
            "future_security_threshold_required_before_live_access": True,
            "underlying_raw_artifact_truth_not_proven_by_receipt": True,
        },
        "current_supported_examples": [
            "Coupa payment invoice proof reference",
            "Excel companion artifact reference",
            "PDF invoice artifact reference",
            "Gmail/email evidence reference",
            "calendar evidence reference",
            "bank/remit/home/check image sensitive reference",
            "client credential reference",
            "unknown sensitive surface reference",
        ],
        "source_boundaries": {
            "repo_a_only": True,
            "repo_b_delta_read_model_may_be_referenced_by_source_concept": True,
            "repo_b_filesystem_inspected": False,
            "raw_private_content_read": False,
        },
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "next_recommended_lane": "Guardian Protected Access Gate Spec v0",
    }


def format_protected_evidence_reference_receipt(payload: dict[str, Any]) -> str:
    eli5 = payload["operator_eli5_summary"]
    summary = payload["receipt_summary"]
    lines = [
        "# Protected Evidence Reference Receipt v0",
        "",
        "Status:",
        "- Receipt contract only; no real sensitive proof was recorded.",
        "- Raw artifact/content storage: `false`.",
        "- Access, approval, execution, browser, credential, OAuth, send, submit, and runtime authority: `false`.",
        "",
        "## ELI5 Summary",
        f"- {eli5['openclaw_can_remember_protected_proof_exists']}",
        f"- {eli5['stores_only_safe_metadata_reference_not_secret_raw_file']}",
        f"- {eli5['receipt_does_not_give_agents_access']}",
        f"- {eli5['receipt_does_not_authorize_execution']}",
        f"- {eli5['future_gates_still_required_before_using_proof']}",
        f"- {eli5['what_this_unlocks_later']}",
        "",
        "## Receipt Status Counts",
    ]
    for status in RECEIPT_STATUSES:
        lines.append(f"- `{status}`: {summary['status_counts'].get(status, 0)}")
    lines.extend(["", "## Receipt Types"])
    for record in payload["receipt_records"]:
        lines.append(
            f"- `{record['receipt_type']}`: `{record['receipt_status']}`; "
            f"raw access granted: `{str(record['receipt_grants_raw_access']).lower()}`."
        )
    lines.extend(["", "## Forbidden Raw Content Fields"])
    for field in payload["receipt_contract"]["forbidden_raw_content_fields"]:
        lines.append(f"- `{field}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "- A protected reference receipt is not proof that the underlying artifact is true.",
            "- A protected reference receipt is not permission to open the artifact.",
            "- Guardian/security-threshold gates remain required before access or use.",
            "",
            f"Next safe lane: {payload['next_recommended_lane']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_protected_evidence_reference_receipt(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> ProtectedEvidenceReferenceReceiptExportResult:
    root = Path(repo_root)
    out_dir = _rooted(export_root, repo_root=root)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_protected_evidence_reference_receipt(repo_root=root, generated_at=generated_at)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_protected_evidence_reference_receipt(payload), encoding="utf-8")
    return ProtectedEvidenceReferenceReceiptExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        receipt_template_count=len(payload["receipt_records"]),
        real_sensitive_proof_recorded=payload["real_sensitive_proof_recorded"],
        raw_content_stored=payload["raw_content_stored"],
        runtime_authority_added=payload["runtime_authority_added"],
        send_or_submit_authority_added=payload["send_or_submit_authority_added"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export protected evidence reference receipt read-model.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repo A root.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Generated read-model export root.")
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_protected_evidence_reference_receipt(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    root = _rooted(args.export_root, repo_root=args.repo_root)
    if args.format == "json":
        print((root / JSON_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    elif args.format == "operator":
        print((root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    else:
        print(stable_json(result.__dict__), end="")
    return 0 if result.schema_version == SCHEMA_VERSION else 1


__all__ = [
    "ALLOWED_RECEIPT_METADATA_FIELDS",
    "FORBIDDEN_RAW_CONTENT_FIELDS",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "RECEIPT_STATUSES",
    "RECEIPT_TYPES",
    "SCHEMA_VERSION",
    "build_protected_evidence_reference_receipt",
    "build_receipt_records",
    "export_protected_evidence_reference_receipt",
    "format_protected_evidence_reference_receipt",
    "protected_reference_receipt_record",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
