"""Capital Hilton Protected Reference Placeholder Contract v0.

This read-model lets OpenClaw represent "I know where the proof lives" without
reading, copying, uploading, extracting, or storing raw protected proof. A
placeholder is metadata-only, does not satisfy proof by itself, and does not
grant invoice, account, browser, Coupa, email, send, model, tool, queue, or
runtime authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from capital_hilton_protected_proof_intake import BLOCKED_ACTIONS as INTAKE_BLOCKED_ACTIONS


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "capital_hilton_protected_reference_placeholder_v0"
READ_MODEL_ID = "capital_hilton_protected_reference_placeholder"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

ANSWER_CANDIDATE_READ_MODEL_REF = "generated/read_models/capital_hilton_answer_candidate_receipt.json"
ANSWER_CANDIDATE_OPERATOR_REF = "generated/read_models/capital_hilton_answer_candidate_receipt_OPERATOR.md"
GUARDIAN_PACKET_READ_MODEL_REF = "generated/read_models/capital_hilton_guardian_review_packet.json"
GUARDIAN_PACKET_OPERATOR_REF = "generated/read_models/capital_hilton_guardian_review_packet_OPERATOR.md"
SHARED_EXECUTION_PATH_ID = "protected_finance_proof_metadata_intake"

REFERENCE_TYPES = (
    "EXCEL_WORKBOOK_REFERENCE",
    "PDF_INVOICE_REFERENCE",
    "COUPA_REFERENCE_METADATA",
    "AP_EMAIL_ROUTE_METADATA",
    "CONTRACT_OR_RATE_SOURCE_REFERENCE",
    "PAYMENT_OR_PO_REFERENCE_METADATA",
    "PERFORMANCE_PROOF_REFERENCE",
    "TAX_VENDOR_PAYMENT_REFERENCE",
    "FUTURE_INVOICE_RECEIPT_REFERENCE",
    "UNKNOWN_FAIL_CLOSED",
)

REFERENCE_STATUSES = (
    "PLACEHOLDER_ONLY",
    "OPERATOR_REPORTED",
    "SOURCE_CARD_LINKED",
    "RECEIPT_LINKED",
    "HASH_LINKED",
    "PROTECTED_METADATA_READY_FOR_GUARDIAN",
    "GUARDIAN_REVIEW_REQUIRED",
    "GUARDIAN_APPROVED_METADATA",
    "REJECTED_OR_OBSOLETE",
    "UNKNOWN_FAIL_CLOSED",
)

SAFE_METADATA_FIELDS_BY_REFERENCE_TYPE = {
    "EXCEL_WORKBOOK_REFERENCE": {
        "allowed": (
            "file label",
            "approximate source location hint",
            "workbook role",
            "expected invoice/source relationship",
            "hash/receipt placeholder",
        ),
        "blocked": (
            "raw workbook contents",
            "customer/private financial details",
            "formulas/body extraction",
            "embedded images",
            "bank/remit/check details unless protected-reference only",
        ),
    },
    "PDF_INVOICE_REFERENCE": {
        "allowed": (
            "document label",
            "document role",
            "expected invoice relationship",
            "hash/receipt placeholder",
        ),
        "blocked": (
            "raw PDF contents",
            "embedded private details",
            "automatic extraction",
        ),
    },
    "COUPA_REFERENCE_METADATA": {
        "allowed": (
            "PO/reference identifier placeholder",
            "vendor/customer route label",
            "portal reference exists yes/no",
        ),
        "blocked": (
            "Coupa login",
            "Coupa session",
            "browser automation",
            "credential material",
            "portal body scraping",
        ),
    },
    "AP_EMAIL_ROUTE_METADATA": {
        "allowed": (
            "route label",
            "recipient role",
            "approved channel type",
            "source-card/receipt pointer",
        ),
        "blocked": (
            "raw email bodies",
            "sending email",
            "Gmail/calendar/account access",
        ),
    },
    "CONTRACT_OR_RATE_SOURCE_REFERENCE": {
        "allowed": (
            "source label",
            "rate source role",
            "source-card/receipt pointer",
        ),
        "blocked": ("raw contract body unless separately allowlisted",),
    },
    "PAYMENT_OR_PO_REFERENCE_METADATA": {
        "allowed": (
            "PO/payment reference placeholder",
            "reference role",
            "protected metadata pointer",
        ),
        "blocked": ("bank/check/remit details unless explicitly protected-reference only",),
    },
    "PERFORMANCE_PROOF_REFERENCE": {
        "allowed": (
            "performance proof label",
            "service-date role",
            "source-card/receipt pointer",
            "redacted metadata label",
        ),
        "blocked": (
            "raw calendar body",
            "raw email body",
            "raw venue/private content",
        ),
    },
    "TAX_VENDOR_PAYMENT_REFERENCE": {
        "allowed": (
            "tax/vendor handling label",
            "payment handling role",
            "protected metadata pointer",
        ),
        "blocked": (
            "tax form body",
            "bank/check/remit details unless protected-reference only",
            "credential or account material",
        ),
    },
    "FUTURE_INVOICE_RECEIPT_REFERENCE": {
        "allowed": (
            "future receipt requirement label",
            "expected receipt role",
            "source fact refs required",
            "hash/receipt placeholder",
        ),
        "blocked": (
            "invoice generation",
            "send/submit approval",
            "ledger write",
        ),
    },
    "UNKNOWN_FAIL_CLOSED": {
        "allowed": (),
        "blocked": ("all raw material", "all authority claims"),
    },
}

NO_AUTHORITY_FLAGS = {
    "file_read_allowed": False,
    "file_copy_allowed": False,
    "file_upload_allowed": False,
    "raw_body_ingestion_allowed": False,
    "excel_body_ingestion_allowed": False,
    "pdf_body_ingestion_allowed": False,
    "email_body_ingestion_allowed": False,
    "coupa_access_allowed": False,
    "browser_oauth_allowed": False,
    "account_access_allowed": False,
    "gmail_calendar_email_access_allowed": False,
    "credential_handling_allowed": False,
    "invoice_generation_allowed": False,
    "ledger_write_allowed": False,
    "send_submit_approval_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
}

BLOCKED_ACTIONS = tuple(
    dict.fromkeys(
        (
            *INTAKE_BLOCKED_ACTIONS,
            "file read",
            "file copy",
            "file upload",
            "protected evidence body access",
            "proof satisfaction by placeholder alone",
            "automatic quieting",
            "Guardian action approval",
        )
    )
)


@dataclass(frozen=True)
class CapitalHiltonProtectedReferencePlaceholder:
    placeholder_id: str
    proof_item_ids: tuple[str, ...]
    display_name: str
    reference_type: str
    reference_status: str
    safe_metadata_fields: tuple[str, ...]
    blocked_raw_material: tuple[str, ...]
    operator_supplied_label: str | None
    source_location_hint: str | None
    source_card_ref: str | None
    receipt_ref: str | None
    hash_ref: str | None
    redaction_required: bool
    metadata_only: bool
    raw_body_allowed: bool
    guardian_gate_required: bool
    operator_final_authority_required: bool
    can_satisfy_proof: bool
    can_quiet_item: bool
    promotion_requirements: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class ProtectedReferencePlaceholderExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    placeholder_count: int
    metadata_only: bool
    raw_body_allowed: bool
    action_authority_granted: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _metadata_fields(reference_type: str) -> tuple[str, ...]:
    return tuple(SAFE_METADATA_FIELDS_BY_REFERENCE_TYPE[reference_type]["allowed"])


def _blocked_material(reference_type: str) -> tuple[str, ...]:
    return tuple(SAFE_METADATA_FIELDS_BY_REFERENCE_TYPE[reference_type]["blocked"])


def _placeholder(
    placeholder_id: str,
    *,
    proof_item_ids: tuple[str, ...],
    display_name: str,
    reference_type: str,
    source_location_hint: str,
    next_safe_move: str,
) -> CapitalHiltonProtectedReferencePlaceholder:
    return CapitalHiltonProtectedReferencePlaceholder(
        placeholder_id=placeholder_id,
        proof_item_ids=proof_item_ids,
        display_name=display_name,
        reference_type=reference_type,
        reference_status="PLACEHOLDER_ONLY",
        safe_metadata_fields=_metadata_fields(reference_type),
        blocked_raw_material=_blocked_material(reference_type),
        operator_supplied_label=None,
        source_location_hint=source_location_hint,
        source_card_ref=None,
        receipt_ref=None,
        hash_ref=None,
        redaction_required=True,
        metadata_only=True,
        raw_body_allowed=False,
        guardian_gate_required=True,
        operator_final_authority_required=True,
        can_satisfy_proof=False,
        can_quiet_item=False,
        promotion_requirements=(
            "operator answer candidate may point to this placeholder",
            "source-card, receipt, or hash placeholder must be linked before promotion",
            "Guardian metadata review required before protected metadata promotion",
            "placeholder alone is not proof and cannot quiet the item",
        ),
        blocked_actions=BLOCKED_ACTIONS,
        next_safe_move=next_safe_move,
    )


def build_default_protected_reference_placeholders() -> list[CapitalHiltonProtectedReferencePlaceholder]:
    return [
        _placeholder(
            "excel_workbook_invoice_source_placeholder",
            proof_item_ids=(
                "excel_workbook_or_invoice_source_reference",
                "subtotal_800_proof",
                "future_invoice_generation_receipt_requirement",
            ),
            display_name="Excel Workbook / Invoice Source Placeholder",
            reference_type="EXCEL_WORKBOOK_REFERENCE",
            source_location_hint="operator_supplied_workbook_or_invoice_source_hint_metadata_only",
            next_safe_move="capture_label_hash_or_source_card_ref_without_reading_workbook_body",
        ),
        _placeholder(
            "coupa_po_payment_reference_placeholder",
            proof_item_ids=("coupa_po_payment_reference_metadata",),
            display_name="Coupa / PO / Payment Reference Placeholder",
            reference_type="COUPA_REFERENCE_METADATA",
            source_location_hint="operator_supplied_coupa_or_po_reference_hint_metadata_only",
            next_safe_move="capture_redacted_reference_placeholder_and_route_metadata_to_guardian",
        ),
        _placeholder(
            "ap_route_metadata_placeholder",
            proof_item_ids=("ap_recipient_route_metadata",),
            display_name="AP Route Metadata Placeholder",
            reference_type="AP_EMAIL_ROUTE_METADATA",
            source_location_hint="operator_supplied_ap_route_label_metadata_only",
            next_safe_move="capture_route_label_without_email_access_or_send_authority",
        ),
        _placeholder(
            "rate_source_placeholder",
            proof_item_ids=("rate_400_per_gig_proof",),
            display_name="Rate Source Placeholder",
            reference_type="CONTRACT_OR_RATE_SOURCE_REFERENCE",
            source_location_hint="operator_supplied_rate_source_label_metadata_only",
            next_safe_move="capture_rate_source_label_or_source_card_ref_without_raw_contract_body",
        ),
        _placeholder(
            "performance_proof_reference_placeholder",
            proof_item_ids=(
                "performance_date_2026_05_08_proof",
                "performance_date_2026_05_15_proof",
            ),
            display_name="Performance Proof Reference Placeholder",
            reference_type="PERFORMANCE_PROOF_REFERENCE",
            source_location_hint="operator_supplied_performance_proof_label_metadata_only",
            next_safe_move="capture_service_date_reference_label_without_calendar_email_or_private_body_access",
        ),
        _placeholder(
            "tax_vendor_payment_handling_placeholder",
            proof_item_ids=("tax_vendor_handling_metadata",),
            display_name="Tax / Vendor / Payment Handling Placeholder",
            reference_type="TAX_VENDOR_PAYMENT_REFERENCE",
            source_location_hint="operator_supplied_tax_vendor_payment_label_metadata_only",
            next_safe_move="capture_sensitive_metadata_label_and_route_to_guardian_before_promotion",
        ),
        _placeholder(
            "future_invoice_generation_receipt_placeholder",
            proof_item_ids=("future_invoice_generation_receipt_requirement",),
            display_name="Future Invoice Generation Receipt Placeholder",
            reference_type="FUTURE_INVOICE_RECEIPT_REFERENCE",
            source_location_hint="future_receipt_shape_placeholder_no_invoice_generation",
            next_safe_move="define_receipt_requirements_without_generating_invoice_or_approving_action",
        ),
    ]


def build_capital_hilton_protected_reference_placeholder(
    *,
    generated_at: str | None = None,
    guardian_packet_present: bool = False,
) -> dict[str, Any]:
    placeholders = build_default_protected_reference_placeholders()
    proof_item_ids = sorted({proof_item_id for item in placeholders for proof_item_id in item.proof_item_ids})
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_id": "capital_hilton_protected_reference_placeholder_v0",
        "generated_at": generated_at or utc_now(),
        **NO_AUTHORITY_FLAGS,
        "contract_status": "deterministic_protected_reference_placeholder_metadata_only",
        "operator_summary": (
            "Protected reference placeholders let Winship point to where Capital Hilton proof "
            "may live without exposing raw protected files or treating the pointer as proof."
        ),
        "reference_types": list(REFERENCE_TYPES),
        "reference_statuses": list(REFERENCE_STATUSES),
        "safe_metadata_fields_by_reference_type": {
            key: {
                "allowed": list(value["allowed"]),
                "blocked": list(value["blocked"]),
            }
            for key, value in SAFE_METADATA_FIELDS_BY_REFERENCE_TYPE.items()
        },
        "protected_reference_placeholders": [asdict(placeholder) for placeholder in placeholders],
        "relationship_to_answer_candidates": {
            "read_model_ref": ANSWER_CANDIDATE_READ_MODEL_REF,
            "operator_ref": ANSWER_CANDIDATE_OPERATOR_REF,
            "shared_execution_path_id": SHARED_EXECUTION_PATH_ID,
            "answer_candidate_may_point_to_placeholder": True,
            "placeholder_remains_non_proof_until_validated": True,
            "guardian_gate_decides_metadata_promotion": True,
            "raw_body_remains_blocked": True,
            "file_access_occurs_here": False,
        },
        "relationship_to_guardian_review_packet": {
            "read_model_ref": GUARDIAN_PACKET_READ_MODEL_REF,
            "operator_ref": GUARDIAN_PACKET_OPERATOR_REF,
            "status": "OBSERVED" if guardian_packet_present else "EXPECTED_OR_PENDING",
            "placeholders_may_be_ready_for_guardian_review": True,
            "guardian_reviews_metadata_posture_only": True,
            "guardian_cannot_approve_invoice_action_or_account_access": True,
        },
        "placeholder_rules": {
            "metadata_only": True,
            "raw_body_allowed": False,
            "can_satisfy_proof_by_default": False,
            "can_quiet_item_by_default": False,
            "guardian_review_required_for_protected_sensitive_references": True,
            "operator_final_authority_required_before_future_action": True,
            "unknown_references_fail_closed": True,
        },
        "authority_boundary": {
            **NO_AUTHORITY_FLAGS,
            "all_authority_flags_false": all(value is False for value in NO_AUTHORITY_FLAGS.values()),
            "blocked_actions": list(BLOCKED_ACTIONS),
        },
        "batch_relationship": {
            "batch_id": "capital_hilton_proof_resolution_batch_v0",
            "prompt_index": 2,
            "stable_map_refresh_deferred": True,
            "commit_deferred_until_final_prompt": True,
            "next_lane": "capital_hilton_guardian_review_packet",
        },
        "machine_proof": {
            "default_placeholder_count": len(placeholders),
            "default_placeholder_ids": [placeholder.placeholder_id for placeholder in placeholders],
            "all_reference_types_exist": set(REFERENCE_TYPES)
            == {
                "EXCEL_WORKBOOK_REFERENCE",
                "PDF_INVOICE_REFERENCE",
                "COUPA_REFERENCE_METADATA",
                "AP_EMAIL_ROUTE_METADATA",
                "CONTRACT_OR_RATE_SOURCE_REFERENCE",
                "PAYMENT_OR_PO_REFERENCE_METADATA",
                "PERFORMANCE_PROOF_REFERENCE",
                "TAX_VENDOR_PAYMENT_REFERENCE",
                "FUTURE_INVOICE_RECEIPT_REFERENCE",
                "UNKNOWN_FAIL_CLOSED",
            },
            "all_reference_statuses_exist": set(REFERENCE_STATUSES)
            == {
                "PLACEHOLDER_ONLY",
                "OPERATOR_REPORTED",
                "SOURCE_CARD_LINKED",
                "RECEIPT_LINKED",
                "HASH_LINKED",
                "PROTECTED_METADATA_READY_FOR_GUARDIAN",
                "GUARDIAN_REVIEW_REQUIRED",
                "GUARDIAN_APPROVED_METADATA",
                "REJECTED_OR_OBSOLETE",
                "UNKNOWN_FAIL_CLOSED",
            },
            "proof_item_ids_represented": proof_item_ids,
            "metadata_only_true_for_all": all(placeholder.metadata_only for placeholder in placeholders),
            "raw_body_allowed_false_for_all": all(placeholder.raw_body_allowed is False for placeholder in placeholders),
            "can_satisfy_proof_false_by_default": all(
                placeholder.can_satisfy_proof is False for placeholder in placeholders
            ),
            "can_quiet_item_false_by_default": all(placeholder.can_quiet_item is False for placeholder in placeholders),
            "guardian_review_required_for_protected_placeholders": all(
                placeholder.guardian_gate_required for placeholder in placeholders
            ),
            "file_read_copy_upload_false": (
                NO_AUTHORITY_FLAGS["file_read_allowed"] is False
                and NO_AUTHORITY_FLAGS["file_copy_allowed"] is False
                and NO_AUTHORITY_FLAGS["file_upload_allowed"] is False
            ),
            "raw_excel_pdf_email_body_ingestion_false": (
                NO_AUTHORITY_FLAGS["excel_body_ingestion_allowed"] is False
                and NO_AUTHORITY_FLAGS["pdf_body_ingestion_allowed"] is False
                and NO_AUTHORITY_FLAGS["email_body_ingestion_allowed"] is False
            ),
            "coupa_browser_email_account_credential_authority_false": (
                NO_AUTHORITY_FLAGS["coupa_access_allowed"] is False
                and NO_AUTHORITY_FLAGS["browser_oauth_allowed"] is False
                and NO_AUTHORITY_FLAGS["account_access_allowed"] is False
                and NO_AUTHORITY_FLAGS["gmail_calendar_email_access_allowed"] is False
                and NO_AUTHORITY_FLAGS["credential_handling_allowed"] is False
            ),
            "invoice_ledger_send_authority_false": (
                NO_AUTHORITY_FLAGS["invoice_generation_allowed"] is False
                and NO_AUTHORITY_FLAGS["ledger_write_allowed"] is False
                and NO_AUTHORITY_FLAGS["send_submit_approval_allowed"] is False
            ),
            "model_tool_agent_runtime_queue_authority_false": (
                NO_AUTHORITY_FLAGS["model_call_allowed"] is False
                and NO_AUTHORITY_FLAGS["tool_execution_allowed"] is False
                and NO_AUTHORITY_FLAGS["agent_activation_allowed"] is False
                and NO_AUTHORITY_FLAGS["runtime_dispatch_allowed"] is False
                and NO_AUTHORITY_FLAGS["queue_execution_allowed"] is False
            ),
            "answer_candidate_linkage_represented": True,
            "guardian_packet_linkage_represented": True,
            "unknown_references_fail_closed": True,
            "credential_or_secret_included": False,
            "raw_private_body_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_capital_hilton_protected_reference_placeholder(payload: dict[str, Any]) -> str:
    lines = [
        "# Capital Hilton Protected Reference Placeholder v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "A protected reference placeholder is a safe pointer. It lets Winship say where proof may live without exposing the raw file, copying it, uploading it, reading it, or treating the pointer as proof.",
        "",
        "## Why This Helps",
        "",
        "The system can remember that proof may be in a workbook, PDF, Coupa/PO reference, AP route, contract/rate source, performance proof source, tax/vendor/payment source, or future receipt shape. It keeps only metadata labels, source-card refs, receipt refs, hash placeholders, and redaction posture.",
        "",
        "## What Is Safe Metadata",
        "",
        "- Labels, roles, approximate source-location hints, source-card pointers, receipt pointers, hash placeholders, and redacted reference labels.",
        "- These are still not proof until validated and promoted through the required receipts and Guardian review.",
        "",
        "## What Stays Blocked",
        "",
        "- Raw workbook, PDF, email, finance/private, Coupa portal, contract, tax, vendor, bank, check, remit, credential, session, account, browser, invoice, ledger, send, submit, approval, model, tool, agent, queue, and runtime material.",
        "",
        "## Default Placeholders",
        "",
    ]
    for placeholder in payload["protected_reference_placeholders"]:
        lines.append(f"- `{placeholder['placeholder_id']}`: `{placeholder['reference_type']}`")
    lines.extend(
        [
            "",
            "## Guardian Review",
            "",
            "Guardian can later review whether the metadata posture is safe to promote. Guardian cannot approve invoice generation, send/submit, Coupa/account access, browser access, email dispatch, raw body extraction, ledger writes, or runtime execution.",
            "",
            "## Future Answer Workspace",
            "",
            "Answer candidates may point to these placeholders. The placeholder remains non-proof until source-card, receipt, hash, redaction, and Guardian metadata requirements are satisfied. No upload or file picker is implemented here.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_capital_hilton_protected_reference_placeholder(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> ProtectedReferencePlaceholderExportResult:
    guardian_packet_present = (Path(repo_root) / GUARDIAN_PACKET_READ_MODEL_REF).exists()
    payload = build_capital_hilton_protected_reference_placeholder(
        generated_at=generated_at,
        guardian_packet_present=guardian_packet_present,
    )
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_capital_hilton_protected_reference_placeholder(payload), encoding="utf-8")
    return ProtectedReferencePlaceholderExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        placeholder_count=payload["machine_proof"]["default_placeholder_count"],
        metadata_only=payload["placeholder_rules"]["metadata_only"],
        raw_body_allowed=payload["placeholder_rules"]["raw_body_allowed"],
        action_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Capital Hilton Protected Reference Placeholder read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_capital_hilton_protected_reference_placeholder(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "placeholder_count": result.placeholder_count,
        "metadata_only": result.metadata_only,
        "raw_body_allowed": result.raw_body_allowed,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"Capital Hilton Protected Reference Placeholder: `{result.schema_version}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "ANSWER_CANDIDATE_OPERATOR_REF",
    "ANSWER_CANDIDATE_READ_MODEL_REF",
    "GUARDIAN_PACKET_OPERATOR_REF",
    "GUARDIAN_PACKET_READ_MODEL_REF",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_ID",
    "REFERENCE_STATUSES",
    "REFERENCE_TYPES",
    "SAFE_METADATA_FIELDS_BY_REFERENCE_TYPE",
    "SCHEMA_VERSION",
    "CapitalHiltonProtectedReferencePlaceholder",
    "build_capital_hilton_protected_reference_placeholder",
    "build_default_protected_reference_placeholders",
    "export_capital_hilton_protected_reference_placeholder",
    "format_capital_hilton_protected_reference_placeholder",
    "stable_json",
]
