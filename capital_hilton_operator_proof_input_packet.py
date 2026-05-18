"""Capital Hilton operator proof input packet/template v0.

This read-model gives the operator the exact safe JSON shape for later proof
metadata intake. It is a template only. It does not record real proof, store raw
artifacts, create Coupa invoices, automate browsers, send email, write
spreadsheets, access credentials/PII, or grant runtime/send/submit/approval
authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from capital_hilton_actionable_review_packet import DEFAULT_EXPORT_ROOT, stable_json
from capital_hilton_external_artifact_proof_capture import (
    PROOF_TYPES,
    WORKFLOW_ID,
    build_capital_hilton_external_artifact_proof_capture,
)


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "capital_hilton_operator_proof_input_packet_v0"
JSON_EXPORT_NAME = "capital_hilton_operator_proof_input_packet.json"
OPERATOR_EXPORT_NAME = "capital_hilton_operator_proof_input_packet_OPERATOR.md"
PROOF_INTAKE_COMMAND = "python3 scripts/export_capital_hilton_external_artifact_proof_capture.py --proof-input-json <path>"

TEMPLATE_FIELDS = (
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
    "no_external_action",
)

NO_AUTHORITY_FLAGS = {
    "template_only": True,
    "real_proof_recorded": False,
    "proof_receipt_created": False,
    "coupa_invoice_created": False,
    "coupa_submit_triggered": False,
    "browser_automation_added": False,
    "email_send_enabled": False,
    "email_draft_created": False,
    "spreadsheet_write_triggered": False,
    "credentials_accessed": False,
    "credential_or_pii_access_enabled": False,
    "raw_sensitive_artifact_stored_in_read_model": False,
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "approval_authority_added": False,
    "repo_b_executed": False,
    "mission_control_app_changed": False,
}


@dataclass(frozen=True)
class OperatorProofInputPacketExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    proof_input_template_added: bool
    synthetic_examples_labeled: bool
    real_proof_recorded: bool
    final_send_approval_availability_state: str
    runtime_authority_added: bool
    send_or_submit_authority_added: bool
    approval_authority_added: bool


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


def _template_record(proof_type: str) -> dict[str, Any]:
    return {
        "proof_type": proof_type,
        "proof_status": "pending_not_recorded",
        "operator_supplied": False,
        "protected_artifact_reference": None,
        "protected_artifact_type": None,
        "artifact_identity_or_hash": None,
        "protected_reference_id": None,
        "protected_reference_path_token": None,
        "invoice_number": None,
        "invoice_date": None,
        "invoice_amount": None,
        "amount": None,
        "po_number": None,
        "po_reference": None,
        "service_dates": [],
        "match_status": "pending" if proof_type == "excel_coupa_match_proof" else "not_applicable",
        "match_basis": None,
        "mismatch_reasons": [],
        "operator_confirmed": None,
        "operator_confirmation_status": None,
        "operator_confirmation_basis": None,
        "redaction_status": None,
        "protection_status": None,
        "source_basis": "not_supplied",
        "date_captured": None,
        "captured_at": None,
        "synthetic_or_test": False,
        "no_external_action": True,
    }


def empty_pending_template() -> dict[str, Any]:
    return {"proof_records": {proof_type: _template_record(proof_type) for proof_type in PROOF_TYPES}}


def partial_coupa_example() -> dict[str, Any]:
    payload = empty_pending_template()
    payload["example_kind"] = "partial_coupa_metadata_example_not_recorded"
    payload["example_is_real_proof"] = False
    payload["proof_records"]["coupa_payment_invoice_proof"] = {
        "proof_type": "coupa_payment_invoice_proof",
        "proof_status": "captured",
        "operator_supplied": True,
        "protected_artifact_reference": "protected://capital-hilton/coupa-invoice-proof/<redacted-reference>",
        "protected_artifact_type": "coupa_supplier_portal_invoice_pdf_reference",
        "artifact_identity_or_hash": "sha256:<operator-supplied-redacted-metadata-hash>",
        "protected_reference_id": "<protected-artifact-reference-id-or-null>",
        "protected_reference_path_token": "<local-protected-path-token-or-null>",
        "invoice_number": "<operator-supplied-invoice-number-or-null>",
        "invoice_date": "<YYYY-MM-DD-or-null>",
        "invoice_amount": "<amount-currency-or-null>",
        "amount": "<amount-currency-or-null>",
        "po_number": "<po-number-or-null>",
        "po_reference": "<po-reference-or-null>",
        "service_dates": ["<YYYY-MM-DD>", "<YYYY-MM-DD>"],
        "match_status": "not_applicable",
        "match_basis": None,
        "mismatch_reasons": [],
        "operator_confirmed": True,
        "operator_confirmation_status": "operator_supplied_metadata_only",
        "operator_confirmation_basis": "manual_review_of_protected_artifact_reference",
        "redaction_status": "redacted_or_protected_reference_only",
        "protection_status": "protected_local_reference",
        "source_basis": "operator_supplied_metadata_only",
        "date_captured": "<YYYY-MM-DD-or-null>",
        "captured_at": "<ISO-8601-timestamp-or-null>",
        "synthetic_or_test": True,
        "no_external_action": True,
    }
    return payload


def full_synthetic_example() -> dict[str, Any]:
    return {
        "example_kind": "full_synthetic_test_metadata_example_not_real_proof",
        "example_is_real_proof": False,
        "all_records_are_synthetic_test_examples": True,
        "proof_records": {
            "coupa_payment_invoice_proof": {
                "proof_type": "coupa_payment_invoice_proof",
                "proof_status": "captured",
                "operator_supplied": True,
                "protected_artifact_reference": "protected://capital-hilton/coupa-invoice-proof/synthetic-example-ref",
                "protected_artifact_type": "coupa_supplier_portal_invoice_pdf_reference",
                "artifact_identity_or_hash": "sha256:synthetic-coupa-proof-metadata-hash",
                "protected_reference_id": "synthetic-protected-coupa-reference-id",
                "protected_reference_path_token": "synthetic-local-path-token",
                "invoice_number": "synthetic-invoice-number",
                "invoice_date": "2026-05-18",
                "invoice_amount": "800.00 USD",
                "amount": "800.00 USD",
                "po_number": "synthetic-po-number",
                "po_reference": "synthetic-po-number",
                "service_dates": ["2026-05-08", "2026-05-15"],
                "match_status": "not_applicable",
                "match_basis": None,
                "mismatch_reasons": [],
                "operator_confirmed": True,
                "operator_confirmation_status": "synthetic_confirmed",
                "operator_confirmation_basis": "synthetic_test_metadata_only",
                "redaction_status": "synthetic_redacted_reference",
                "protection_status": "synthetic_protected_reference",
                "source_basis": "synthetic_test_metadata_only",
                "date_captured": "2026-05-18",
                "captured_at": "2026-05-18T00:00:00+00:00",
                "synthetic_or_test": True,
                "no_external_action": True,
            },
            "excel_companion_invoice_artifact": {
                "proof_type": "excel_companion_invoice_artifact",
                "proof_status": "captured",
                "operator_supplied": True,
                "protected_artifact_reference": "protected://capital-hilton/excel-companion-invoice/synthetic-example-ref",
                "protected_artifact_type": "excel_companion_invoice_pdf_reference",
                "artifact_identity_or_hash": "sha256:synthetic-excel-companion-metadata-hash",
                "protected_reference_id": "synthetic-protected-excel-reference-id",
                "protected_reference_path_token": "synthetic-local-excel-path-token",
                "invoice_number": "synthetic-invoice-number",
                "invoice_date": "2026-05-18",
                "invoice_amount": "800.00 USD",
                "amount": "800.00 USD",
                "po_number": "synthetic-po-number",
                "po_reference": "synthetic-po-number",
                "service_dates": ["2026-05-08", "2026-05-15"],
                "match_status": "not_applicable",
                "match_basis": None,
                "mismatch_reasons": [],
                "operator_confirmed": True,
                "operator_confirmation_status": "synthetic_confirmed",
                "operator_confirmation_basis": "synthetic_test_metadata_only",
                "redaction_status": "synthetic_redacted_reference",
                "protection_status": "synthetic_protected_reference",
                "source_basis": "synthetic_test_metadata_only",
                "date_captured": "2026-05-18",
                "captured_at": "2026-05-18T00:00:00+00:00",
                "synthetic_or_test": True,
                "no_external_action": True,
            },
            "excel_coupa_match_proof": {
                "proof_type": "excel_coupa_match_proof",
                "proof_status": "verified",
                "operator_supplied": True,
                "protected_artifact_reference": "protected://capital-hilton/excel-coupa-match/synthetic-example-ref",
                "protected_artifact_type": "excel_coupa_match_metadata_reference",
                "artifact_identity_or_hash": "sha256:synthetic-match-proof-metadata-hash",
                "protected_reference_id": "synthetic-protected-match-reference-id",
                "protected_reference_path_token": "synthetic-local-match-path-token",
                "invoice_number": "synthetic-invoice-number",
                "invoice_date": "2026-05-18",
                "invoice_amount": "800.00 USD",
                "amount": "800.00 USD",
                "po_number": "synthetic-po-number",
                "po_reference": "synthetic-po-number",
                "service_dates": ["2026-05-08", "2026-05-15"],
                "match_status": "matched",
                "match_basis": "synthetic_test_metadata_match_example",
                "mismatch_reasons": [],
                "operator_confirmed": True,
                "operator_confirmation_status": "synthetic_confirmed",
                "operator_confirmation_basis": "synthetic_test_metadata_only",
                "redaction_status": "synthetic_redacted_reference",
                "protection_status": "synthetic_protected_reference",
                "source_basis": "synthetic_test_metadata_only",
                "date_captured": "2026-05-18",
                "captured_at": "2026-05-18T00:00:00+00:00",
                "synthetic_or_test": True,
                "no_external_action": True,
            },
        },
    }


def _safe_instructions() -> list[str]:
    return [
        "Provide metadata and protected/local-only artifact references only.",
        "Do not paste raw PDF contents, Excel file contents, portal screenshots, or copied private document bodies.",
        "Do not paste passwords, tokens, portal credentials, bank details, check images, or full home addresses.",
        "Keep raw files in protected/local-only storage outside normal generated read-models.",
        "Use null for unknown values.",
        "Use false only for explicit negative confirmations, not for unknowns.",
        "Proof must be operator-supplied or safely metadata-derived.",
        "Synthetic examples are examples only and must not be treated as real proof.",
    ]


def build_capital_hilton_operator_proof_input_packet(*, generated_at: str | None = None) -> dict[str, Any]:
    ts = generated_at or utc_now()
    proof_capture_baseline = build_capital_hilton_external_artifact_proof_capture(generated_at=ts)
    no_authority = dict(NO_AUTHORITY_FLAGS)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": ts,
        "packet_kind": "operator_proof_input_template",
        "workflow": WORKFLOW_ID,
        "workflow_scope": "Capital Hilton / Hilton only",
        "template_status": "template_only_no_real_proof_recorded",
        "proof_input_template_added": True,
        "proof_intake_command": PROOF_INTAKE_COMMAND,
        "proof_input_shape": empty_pending_template(),
        "template_fields": list(TEMPLATE_FIELDS),
        "proof_sections": list(PROOF_TYPES),
        "safe_operator_instructions": _safe_instructions(),
        "example_payloads": {
            "empty_pending_template": empty_pending_template(),
            "partial_coupa_proof_only_example": partial_coupa_example(),
            "full_synthetic_test_metadata_example": full_synthetic_example(),
        },
        "proof_capture_baseline": {
            "schema_version": proof_capture_baseline["schema_version"],
            "real_proof_recorded": proof_capture_baseline["status_summary"]["real_proof_recorded"],
            "coupa_invoice_proof_status": proof_capture_baseline["status_summary"]["coupa_invoice_proof_status"],
            "excel_companion_artifact_status": proof_capture_baseline["status_summary"]["excel_companion_artifact_status"],
            "excel_coupa_match_proof_status": proof_capture_baseline["status_summary"]["excel_coupa_match_proof_status"],
            "final_send_approval_availability_state": proof_capture_baseline[
                "final_send_approval_availability_state"
            ],
        },
        "final_send_gate_posture": {
            "final_send_gate_remains_blocked": True,
            "current_approval_availability_state": proof_capture_baseline[
                "final_send_approval_availability_state"
            ],
            "reason": "No real operator proof metadata was recorded by this template packet.",
        },
        "template_alignment": {
            "aligns_with_proof_intake_command": True,
            "supported_fields_match_template_fields": True,
            "partial_proof_intake_supported": True,
            "future_workflows_may_reuse_pattern": True,
        },
        "authority_boundary": {
            "template_only": True,
            "no_authority_flags": no_authority,
            "raw_sensitive_artifact_included": False,
            "raw_sensitive_artifact_stored_in_read_model": False,
            "real_proof_recorded": False,
            "coupa_submit_triggered": False,
            "browser_automation_added": False,
            "email_send_enabled": False,
            "spreadsheet_write_triggered": False,
            "credential_or_pii_access_enabled": False,
            "runtime_authority_added": False,
            "send_or_submit_authority_added": False,
            "approval_authority_added": False,
        },
        "boundaries": no_authority,
        **no_authority,
        "next_recommended_lane": "Capital Hilton Manual Proof Metadata Capture v0",
    }


def format_capital_hilton_operator_proof_input_packet(payload: dict[str, Any]) -> str:
    baseline = payload["proof_capture_baseline"]
    lines = [
        "# Capital Hilton Operator Proof Input Packet",
        "",
        "Status:",
        "- Template only; no real proof was recorded.",
        f"- Intake command: `{payload['proof_intake_command']}`.",
        f"- Coupa proof: `{baseline['coupa_invoice_proof_status']}`.",
        f"- Excel companion artifact: `{baseline['excel_companion_artifact_status']}`.",
        f"- Excel-vs-Coupa match proof: `{baseline['excel_coupa_match_proof_status']}`.",
        f"- Final send approval availability: `{baseline['final_send_approval_availability_state']}`.",
        "",
        "## What To Provide Later",
    ]
    for proof_type in payload["proof_sections"]:
        lines.append(f"- `{proof_type}` metadata/protected reference fields only.")
    lines.extend(["", "## Safe Input Rules"])
    for instruction in payload["safe_operator_instructions"]:
        lines.append(f"- {instruction}")
    lines.extend([
        "",
        "## Examples Included",
        "- `empty_pending_template`: safe starting shape with null unknowns.",
        "- `partial_coupa_proof_only_example`: example only, not recorded as proof.",
        "- `full_synthetic_test_metadata_example`: synthetic/test example only, not real proof.",
        "",
        "## Boundary",
        "- No Coupa submit, browser automation, email send, spreadsheet write, credential access, runtime authority, send authority, or approval authority was added.",
        "- No raw PDFs, Excel files, screenshots, passwords, tokens, bank details, home addresses, or check images are included.",
        "",
        f"Next safe lane: {payload['next_recommended_lane']}",
        "",
    ])
    return "\n".join(lines)


def export_capital_hilton_operator_proof_input_packet(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> OperatorProofInputPacketExportResult:
    payload = build_capital_hilton_operator_proof_input_packet(generated_at=generated_at)
    root = _rooted(export_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_capital_hilton_operator_proof_input_packet(payload), encoding="utf-8")
    return OperatorProofInputPacketExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        proof_input_template_added=True,
        synthetic_examples_labeled=True,
        real_proof_recorded=False,
        final_send_approval_availability_state=payload["proof_capture_baseline"][
            "final_send_approval_availability_state"
        ],
        runtime_authority_added=False,
        send_or_submit_authority_added=False,
        approval_authority_added=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Capital Hilton operator proof input packet/template.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_capital_hilton_operator_proof_input_packet(export_root=args.export_root)
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
    "OPERATOR_EXPORT_NAME",
    "PROOF_INTAKE_COMMAND",
    "SCHEMA_VERSION",
    "TEMPLATE_FIELDS",
    "build_capital_hilton_operator_proof_input_packet",
    "empty_pending_template",
    "export_capital_hilton_operator_proof_input_packet",
    "format_capital_hilton_operator_proof_input_packet",
    "full_synthetic_example",
    "partial_coupa_example",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
