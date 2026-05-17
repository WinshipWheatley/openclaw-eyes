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
    "invoice_number",
    "invoice_date",
    "invoice_amount",
    "po_number",
    "match_status",
    "match_basis",
    "source_basis",
    "captured_at",
    "synthetic_or_test",
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


def _safe_metadata(raw: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key in _ALLOWED_METADATA_FIELDS:
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(value, bool) or value is None:
            safe[key] = value
        elif isinstance(value, (int, float)):
            safe[key] = value
        else:
            safe[key] = _sanitize_text(value)
    return safe


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
        "invoice_number": metadata.get("invoice_number", ""),
        "invoice_date": metadata.get("invoice_date", ""),
        "invoice_amount": metadata.get("invoice_amount", ""),
        "po_number": metadata.get("po_number", ""),
        "match_status": metadata.get("match_status", "not_applicable" if proof_type != "excel_coupa_match_proof" else "pending"),
        "match_basis": metadata.get("match_basis", ""),
        "source_basis": metadata.get("source_basis", "operator_supplied_metadata_only" if operator_supplied else "not_supplied"),
        "captured_at": metadata.get("captured_at", generated_at if captured else ""),
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
    real_proof_recorded = any(item["proof_status"] == "captured" for item in records.values())
    synthetic_recorded = any(item["proof_status"] == "synthetic_test_recorded_not_real" for item in records.values())
    no_authority = dict(NO_AUTHORITY_FLAGS)
    no_authority["real_proof_recorded"] = real_proof_recorded
    no_authority["synthetic_or_test_proof_recorded"] = synthetic_recorded
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": ts,
        "packet_kind": "external_artifact_proof_capture_contract",
        "workflow": WORKFLOW_ID,
        "workflow_scope": "Capital Hilton / Hilton only",
        "capture_mode": "operator_supplied_safe_metadata_only",
        "proof_records": records,
        "supported_metadata_fields": sorted(_ALLOWED_METADATA_FIELDS),
        "proof_capture_requirements": {
            "proof_requires_explicit_operator_input_or_safe_metadata": True,
            "missing_input_does_not_create_proof": True,
            "synthetic_test_proof_never_counts_as_real": True,
            "raw_artifact_contents_allowed_in_read_models": False,
        },
        "final_send_approval_prerequisites": prerequisites,
        "final_send_approval_availability_state": availability,
        "final_send_approval_remains_blocked_without_required_proof": availability != "available_for_guardian_send_approval",
        "status_summary": {
            "coupa_invoice_proof_status": records["coupa_payment_invoice_proof"]["proof_status"],
            "excel_companion_artifact_status": records["excel_companion_invoice_artifact"]["proof_status"],
            "excel_coupa_match_proof_status": records["excel_coupa_match_proof"]["proof_status"],
            "real_proof_recorded": real_proof_recorded,
            "paid_status": False,
            "final_send_approval_availability_state": availability,
            "raw_sensitive_artifact_stored_in_read_model": False,
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
        "- Raw sensitive artifacts stored in read-model: `false`.",
        "- Coupa/browser/email/spreadsheet/credential/runtime authority added: `false`.",
        "",
        "## Proof Records",
    ]
    for proof_type, record in payload["proof_records"].items():
        lines.append(f"- `{proof_type}`: {record['proof_status']} (operator supplied: `{str(record['operator_supplied']).lower()}`)")
    lines.extend(["", "## Final Send Approval Prerequisites"])
    for key, present in payload["final_send_approval_prerequisites"].items():
        lines.append(f"- `{key}`: `{str(bool(present)).lower()}`")
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
    "build_capital_hilton_external_artifact_proof_capture",
    "export_capital_hilton_external_artifact_proof_capture",
    "final_send_prerequisite_status_from_records",
    "format_capital_hilton_external_artifact_proof_capture",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
