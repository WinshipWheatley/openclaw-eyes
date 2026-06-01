"""Live Arts MD simple invoice review bundle v0.

This module proves the reusable email-invoice rails for a non-Coupa client.
It does not read workbook cells, generate/export invoices, send email, access
Gmail/Coupa/browser, post ledgers, or mutate production business state.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Mapping

import client_invoice_workflow_framework as workflow
import client_comms_thread_rail
import clara_invoice_email_draft_package as clara_drafts
import client_invoice_workbook_registry
import live_arts_md_workbook_handoff
import local_artifact_reference
import simple_invoice_workflow_builder as simple_builder
import simple_invoice_workflow_fixtures as simple_fixtures


SCHEMA_VERSION = "live_arts_md_invoice_review_bundle_v0"
READ_MODEL_ID = "live_arts_md_invoice_review_bundle"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-28T00:00:00+00:00"
LEGACY_ACTION_RECEIPT_EXPORT_NAME = "invoice_review_action_request_receipt.json"
SELECTION_RECEIPT_EXPORT_NAME = "live_arts_md_invoice_candidate_selected_receipt.json"
PDF_EXPORT_RESULT_RECEIPT_EXPORT_NAME = "selected_invoice_pdf_export_completed_candidate_receipt.json"
PDF_EXPORT_OPERATOR_ASSISTANCE_ANNOTATION_EXPORT_NAME = (
    "selected_invoice_pdf_export_operator_assistance_annotation.json"
)
KNOWN_UNTRUSTED_DESKTOP_PDF_PATH = "/Users/hwinshipwheatley/Desktop/Live_Arts_MD_Speaker_Rental_Invoice_September_May_2026.pdf"
KNOWN_INVALID_BRIDGE_PDF_MAC_PATH = "/Volumes/openclaw_e/artifacts/invoice_workbooks/live_arts_md_invoice_2026-1001.pdf"
KNOWN_INVALID_BRIDGE_PDF_PC_PATH = "/mnt/e/openclaw/artifacts/invoice_workbooks/live_arts_md_invoice_2026-1001.pdf"

_SIMPLE_INVOICE_FIXTURE = simple_fixtures.get_simple_invoice_fixture("live_arts_md")
_SIMPLE_INVOICE_CONFIG = asdict(_SIMPLE_INVOICE_FIXTURE)

CLIENT_REF = _SIMPLE_INVOICE_CONFIG["client_ref"]
CLIENT_DISPLAY_NAME = _SIMPLE_INVOICE_CONFIG["client_display_name"]
WORKFLOW_REF = _SIMPLE_INVOICE_CONFIG["workflow_ref"]
EXPECTED_WORKBOOK_NAME = _SIMPLE_INVOICE_CONFIG["expected_workbook_name"]
WORKBOOK_SELECTION_USE = _SIMPLE_INVOICE_CONFIG["selection_intended_use"]
RECIPIENT_CONFIRM_USE = _SIMPLE_INVOICE_CONFIG["recipient_confirmation_intended_use"]
MANUAL_SEND_USE = _SIMPLE_INVOICE_CONFIG["manual_send_intended_use"]
INVOICE_CANDIDATE_SELECTED_RECEIPT = f"{CLIENT_REF}_invoice_candidate_selected_receipt"
INVOICE_STEP_PREFIX = f"{CLIENT_REF}_step"
INVOICE_BLOCKER_PREFIX = f"{CLIENT_REF}_blocker"
BUNDLE_ID = f"invoice_review_bundle:{CLIENT_REF}:v0"
CLIENT_ALIAS_READINESS = next(
    (
        value
        for value in clara_drafts.CLIENT_ALIAS_READINESS.values()
        if isinstance(value, Mapping) and value.get("canonical_client_ref") == CLIENT_REF
    ),
    {},
)
CLIENT_ALIAS_READINESS_MATCHED = bool(
    CLIENT_ALIAS_READINESS.get("canonical_client_ref") == CLIENT_REF if isinstance(CLIENT_ALIAS_READINESS, Mapping) else False
)
KNOWN_MANUAL_SEND_INVOICE_ID = _SIMPLE_INVOICE_CONFIG["known_manual_send_defaults"]["invoice_id"]
KNOWN_MANUAL_SEND_WORK = _SIMPLE_INVOICE_CONFIG["known_manual_send_defaults"]["work_or_period"]
KNOWN_MANUAL_SEND_AMOUNT = _SIMPLE_INVOICE_CONFIG["known_manual_send_defaults"]["amount"]
KNOWN_MANUAL_SEND_PROOF_ATTACHMENTS = _SIMPLE_INVOICE_CONFIG["known_manual_send_defaults"]["attachment_filename"]
KNOWN_MANUAL_SEND_ARTIFACT_PATH = _SIMPLE_INVOICE_CONFIG["known_manual_send_defaults"]["artifact_path"]
KNOWN_MANUAL_SEND_TO = tuple(_SIMPLE_INVOICE_CONFIG["known_manual_send_defaults"]["to"])
KNOWN_MANUAL_SEND_CC = tuple(_SIMPLE_INVOICE_CONFIG["known_manual_send_defaults"]["cc"])
KNOWN_MANUAL_SEND_SUBJECT = _SIMPLE_INVOICE_CONFIG["known_manual_send_defaults"]["subject"]
KNOWN_MANUAL_SEND_SEND_TIMESTAMP = _SIMPLE_INVOICE_CONFIG["known_manual_send_defaults"]["sent_timestamp"]
MANUAL_SEND_COMPLETION_REQUIRED_FIELDS = (
    "sent_timestamp",
    "to",
    "cc",
    "subject",
    "attachment_filename",
    "invoice_id",
    "amount",
    "work_or_period",
)
MANUAL_SEND_PROOF_STATUS_PENDING = simple_builder.MANUAL_SEND_PROOF_STATUS_PENDING
MANUAL_SEND_PROOF_STATUS_CONFIRMED = simple_builder.MANUAL_SEND_PROOF_STATUS_CONFIRMED
MANUAL_SEND_PROOF_CONFIRMED_RECEIPT = simple_builder.MANUAL_SEND_PROOF_CONFIRMED_RECEIPT
PAYMENT_WATCH_STATUS_READY_TO_CONFIGURE = simple_builder.PAYMENT_WATCH_STATUS_READY_TO_CONFIGURE
PAYMENT_WATCH_STATUS_ACTIVE_PENDING_PAYMENT = simple_builder.PAYMENT_WATCH_STATUS_ACTIVE_PENDING_PAYMENT
PAYMENT_WATCH_STATUS_READINESS_ONLY = simple_builder.PAYMENT_WATCH_STATUS_READINESS_ONLY
PAYMENT_WATCH_EXPECTED_STATUS_OPEN = simple_builder.PAYMENT_WATCH_EXPECTED_STATUS_OPEN
PAYMENT_WATCH_REVIEW_STATUS_WAITING_FOR_PAYMENT = simple_builder.PAYMENT_WATCH_REVIEW_STATUS_WAITING_FOR_PAYMENT
PAYMENT_WATCH_REVIEW_STATUS_WAITING_FOR_PROOF = simple_builder.PAYMENT_WATCH_REVIEW_STATUS_WAITING_FOR_PROOF
PAYMENT_WATCH_LEDGER_MATCH_NOT_MATCHED = simple_builder.PAYMENT_WATCH_LEDGER_MATCH_NOT_MATCHED
PAYMENT_WATCH_LEDGER_MATCH_NOT_ATTEMPTED = simple_builder.PAYMENT_WATCH_LEDGER_MATCH_NOT_ATTEMPTED
PAYMENT_WATCH_LEDGER_HANDOFF_PLANNING_ONLY = simple_builder.PAYMENT_WATCH_LEDGER_HANDOFF_PLANNING_ONLY
PROOF_CAPTURE_TYPE_REFERENCE_ONLY = simple_builder.PROOF_CAPTURE_TYPE_REFERENCE_ONLY
PROOF_CAPTURE_TYPE_FILE_BACKED = simple_builder.PROOF_CAPTURE_TYPE_FILE_BACKED
PROOF_STRENGTH_OPERATOR_ATTESTED_REFERENCE = simple_builder.PROOF_STRENGTH_OPERATOR_ATTESTED_REFERENCE
PROOF_STRENGTH_FILE_VERIFIED = simple_builder.PROOF_STRENGTH_FILE_VERIFIED
PDF_EXPORT_PACKAGE_READY_FOR_MAC = simple_builder.PDF_EXPORT_PACKAGE_READY_FOR_MAC
PDF_EXPORT_BLOCKED_MISSING_MAC_CAPABILITY = simple_builder.PDF_EXPORT_BLOCKED_MISSING_MAC_CAPABILITY
PDF_EXPORT_BLOCKED_MISSING_SELECTION = simple_builder.PDF_EXPORT_BLOCKED_MISSING_SELECTION
PDF_EXPORT_BLOCKED_MISSING_PRINT_SCOPE = simple_builder.PDF_EXPORT_BLOCKED_MISSING_PRINT_SCOPE
PDF_EXPORT_BLOCKED_OUTPUT_PATH_CONTRACT = simple_builder.PDF_EXPORT_BLOCKED_OUTPUT_PATH_CONTRACT
PDF_EXPORT_COMPLETED_CANDIDATE = simple_builder.PDF_EXPORT_COMPLETED_CANDIDATE
PDF_EXPORT_REQUIRES_OPERATOR_REVIEW = simple_builder.PDF_EXPORT_REQUIRES_OPERATOR_REVIEW
PDF_EXPORT_SCOPE_DRIFT = "PDF_EXPORT_SCOPE_DRIFT"
PDF_EXPORT_BLOCKED_SCOPE_INCONSISTENCY = "BLOCKED_SCOPE_INCONSISTENCY"
PDF_EXPORT_REQUIRED_CAPABILITY = simple_builder.PDF_EXPORT_REQUIRED_CAPABILITY
PDF_EXPORT_EXECUTION_VENUE = simple_builder.PDF_EXPORT_EXECUTION_VENUE
PDF_EXPORT_OUTPUT_ARTIFACT_KIND = simple_builder.PDF_EXPORT_OUTPUT_ARTIFACT_KIND
PDF_EXPORT_PACKAGE_REQUESTED_RECEIPT = simple_builder.PDF_EXPORT_PACKAGE_REQUESTED_RECEIPT
PDF_EXPORT_COMPLETION_RECEIPT = simple_builder.PDF_EXPORT_COMPLETION_RECEIPT
ARTIFACT_REVIEW_STATUS_OPERATOR_REVIEW_REQUIRED = "OPERATOR_REVIEW_REQUIRED"
ARTIFACT_REVIEW_STATUS_SCOPE_MISMATCH_REJECTED = "SCOPE_MISMATCH_REJECTED"
ARTIFACT_REVIEW_STATUS_APPROVED_FOR_ATTACHMENT = "APPROVED_FOR_ATTACHMENT"
ARTIFACT_REVIEW_STATUS_NOT_READY = "NOT_READY"
ARTIFACT_REVIEW_STATUS_EXPORT_FAILED = "EXPORT_FAILED"
ARTIFACT_REVIEW_REASON_WRONG_EXPORT_SCOPE = "WRONG_EXPORT_SCOPE_WORKBOOK_INSTEAD_OF_SELECTED_INVOICE_PAGE"
LEGACY_GUARDRAIL_NOT_TRUSTED_EXISTING_MULTI_PAGE_PDF = "NOT_TRUSTED_EXISTING_MULTI_PAGE_PDF"
EXPECTED_SELECTED_INVOICE_PAGE_COUNT = 1
PDF_EXPORT_PACKAGE_REQUEST_TEMPLATE = _SIMPLE_INVOICE_CONFIG["pdf_package_request_template"]
PDF_EXPORT_SCOPE_REVIEW_TEMPLATE = _SIMPLE_INVOICE_CONFIG["pdf_scope_review_template"]
PROOF_CAPTURE_REF_REQUEST_TEMPLATE = (
    f"Add sent-email screenshot or sent-mail proof for {_SIMPLE_INVOICE_CONFIG['client_display_name']} invoice {{invoice_id}}."
)
LIVE_ARTS_MD_MANUAL_SEND_PROOF = dict(_SIMPLE_INVOICE_CONFIG["known_manual_send_defaults"])
INVOICE_CANDIDATE_REGISTER_REF = _SIMPLE_INVOICE_CONFIG["invoice_candidate_register_ref"]
RECIPIENT_REF = f"{CLIENT_REF}_billing_contact_candidate"

ALLOWED_ARTIFACT_EXTENSIONS = simple_builder.ALLOWED_ARTIFACT_EXTENSIONS

AUTHORITY_BOUNDARY = {
    "workbook_body_read_performed": False,
    "spreadsheet_cell_read_performed": False,
    "invoice_generation_performed": False,
    "pdf_export_performed": False,
    "email_send_performed": False,
    "gmail_access_performed": False,
    "coupa_access_performed": False,
    "browser_automation_performed": False,
    "ledger_posting_performed": False,
    "production_business_mutation_performed": False,
    "physical_deletion_performed": False,
    "external_action_performed": False,
    "live_gmail_polling_performed": False,
    "gmail_draft_created": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: Mapping[str, Any]) -> str:
    clone = json.loads(stable_json(dict(payload)))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _source_commit() -> str | None:
    git_dir = Path(__file__).resolve().parent / ".git"
    try:
        if git_dir.is_file():
            git_pointer = git_dir.read_text(encoding="utf-8").strip()
            if git_pointer.startswith("gitdir: "):
                git_dir = (git_dir.parent / git_pointer.removeprefix("gitdir: ").strip()).resolve()
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref: "):
            ref_name = head.removeprefix("ref: ").strip()
            ref_path = git_dir / ref_name
            if not ref_path.exists():
                common_dir_ref = git_dir / "commondir"
                if common_dir_ref.exists():
                    common_dir = (git_dir / common_dir_ref.read_text(encoding="utf-8").strip()).resolve()
                    ref_path = common_dir / ref_name
            return ref_path.read_text(encoding="utf-8").strip()[:40]
        return head[:40]
    except OSError:
        return None


def _as_sequence(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        stripped = value.strip()
        return (stripped,) if stripped else ()
    if isinstance(value, (list, tuple, set)):
        return tuple(
            str(item).strip()
            for item in value
            if str(item).strip()
        )
    return (str(value).strip(),) if str(value).strip() else ()


def _is_present_field(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set)):
        return bool(_as_sequence(value))
    if isinstance(value, bool):
        return value is True
    if isinstance(value, (int, float)):
        return True
    return bool(str(value).strip())


def _looks_like_path(value: str) -> bool:
    value = value.strip()
    return (
        value.startswith(("/", "./", "../", "~", "file://"))
        or (len(value) >= 3 and value[1] == ":" and value[2] in ("/", "\\") )
    )


def _proof_capture_metadata(value: object) -> dict[str, Any]:
    if not isinstance(value, str):
        return {
            "proof_ref": value,
            "is_path": False,
            "proof_path_status": "non_text_reference",
            "exists": False,
            "extension": None,
            "file_size": None,
            "sha256": None,
        }
    text = value.strip()
    if not text:
        return {
            "proof_ref": value,
            "is_path": False,
            "proof_path_status": "missing",
            "exists": False,
            "extension": None,
            "file_size": None,
            "sha256": None,
        }
    if not _looks_like_path(text):
        return {
            "proof_ref": value,
            "is_path": False,
            "proof_path_status": "reference_only",
            "exists": True,
            "extension": None,
            "file_size": None,
            "sha256": None,
        }
    path = Path(text[7:] if text.startswith("file://") else text).expanduser()
    if not path.exists() or not path.is_file():
        return {
            "proof_ref": value,
            "is_path": True,
            "proof_path_status": "missing",
            "path_candidate": path.as_posix(),
            "exists": path.exists(),
            "extension": path.suffix.lower(),
            "file_size": None,
            "sha256": None,
        }
    data = path.read_bytes()
    return {
        "proof_ref": value,
        "is_path": True,
        "proof_path_status": "metadata_valid",
        "path_candidate": path.as_posix(),
        "exists": True,
        "extension": path.suffix.lower(),
        "file_size": len(data),
        "sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
    }


def _proof_capture_request(invoice_id: str, request_needed: bool) -> str | None:
    if not request_needed:
        return None
    return PROOF_CAPTURE_REF_REQUEST_TEMPLATE.format(invoice_id=invoice_id)


def _selected_invoice_pdf_export_package(
    *,
    selected_candidate: Mapping[str, Any] | None,
    source_workbook: Mapping[str, Any] | None,
    present_receipts: set[str],
) -> tuple[dict[str, Any], str | None]:
    return simple_builder.build_selected_invoice_pdf_export_package(
        fixture=_SIMPLE_INVOICE_CONFIG,
        selected_candidate=selected_candidate,
        source_workbook=source_workbook,
        present_receipts=set(present_receipts),
    )


def _normalize_manual_send_proof(
    *,
    manual_send_proof: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return simple_builder.normalize_manual_send_proof(
        fixture=_SIMPLE_INVOICE_CONFIG,
        manual_send_proof=manual_send_proof,
    )


def _manual_send_proof_status(
    *,
    manual_send_proof: Mapping[str, Any] | None,
    present_receipts: set[str],
) -> tuple[dict[str, Any], str]:
    return simple_builder.evaluate_manual_send_proof_status(
        fixture=_SIMPLE_INVOICE_CONFIG,
        manual_send_proof=manual_send_proof,
        present_receipts=set(present_receipts),
    )


def _invoice_candidate_lookup(invoice_id: str) -> Mapping[str, Any] | None:
    target = str(invoice_id).strip()
    if not target:
        return None
    lookup = _SIMPLE_INVOICE_FIXTURE.candidate_lookup
    return lookup(target) if callable(lookup) else None


def _load_existing_selection_receipt() -> Mapping[str, Any] | None:
    receipt_names = (
        SELECTION_RECEIPT_EXPORT_NAME,
        LEGACY_ACTION_RECEIPT_EXPORT_NAME,
    )
    for root in (DEFAULT_EXPORT_ROOT, DEFAULT_BRIDGE_EXPORT_ROOT):
        for receipt_name in receipt_names:
            path = root / receipt_name
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                continue
            receipt = _selection_receipt_from_payload(payload)
            if receipt is not None:
                return receipt
    return None


def _load_existing_pdf_export_result_receipt() -> Mapping[str, Any] | None:
    for path in (
        DEFAULT_EXPORT_ROOT / PDF_EXPORT_RESULT_RECEIPT_EXPORT_NAME,
        DEFAULT_BRIDGE_EXPORT_ROOT / PDF_EXPORT_RESULT_RECEIPT_EXPORT_NAME,
    ):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
        receipt = _pdf_export_result_receipt_from_payload(payload)
        if receipt is not None:
            return receipt
    return None


def _load_existing_pdf_export_operator_assistance_annotation() -> Mapping[str, Any] | None:
    for path in (
        DEFAULT_EXPORT_ROOT / PDF_EXPORT_OPERATOR_ASSISTANCE_ANNOTATION_EXPORT_NAME,
        DEFAULT_BRIDGE_EXPORT_ROOT / PDF_EXPORT_OPERATOR_ASSISTANCE_ANNOTATION_EXPORT_NAME,
    ):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
        annotation = _pdf_export_operator_assistance_annotation_from_payload(payload)
        if annotation is not None:
            return annotation
    return None


def _selection_receipt_from_payload(payload: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    receipt = payload.get("action_start_receipt")
    if isinstance(receipt, Mapping):
        candidate = receipt
    else:
        candidate = payload
    if candidate.get("receipt_event") != INVOICE_CANDIDATE_SELECTED_RECEIPT:
        return None
    if candidate.get("client_ref") != CLIENT_REF or candidate.get("workflow_ref") != WORKFLOW_REF:
        return None
    if candidate.get("validation_errors"):
        return None
    if not str(candidate.get("invoice_id") or "").strip():
        return None
    return candidate


def _pdf_export_result_receipt_from_payload(payload: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    receipt = payload.get("action_start_receipt")
    if isinstance(receipt, Mapping):
        candidate = receipt
    else:
        candidate = payload
    if candidate.get("receipt_name") != "selected_invoice_pdf_export_completed_candidate_receipt":
        return None
    if candidate.get("client_ref") != CLIENT_REF or candidate.get("workflow_ref") != WORKFLOW_REF:
        return None
    if candidate.get("validation_errors"):
        return None
    if not str(candidate.get("invoice_id") or "").strip():
        return None
    return candidate


def _pdf_export_operator_assistance_annotation_from_payload(
    payload: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    if payload.get("read_model_id") != "selected_invoice_pdf_export_operator_assistance_annotation":
        return None
    if payload.get("annotation_status") not in {
        "OPERATOR_ASSISTED_ANNOTATED",
        ARTIFACT_REVIEW_STATUS_SCOPE_MISMATCH_REJECTED,
        "PDF_PAGE_COUNT_UNKNOWN_REJECTED",
    }:
        return None
    if payload.get("client_ref") != CLIENT_REF or payload.get("workflow_ref") != WORKFLOW_REF:
        return None
    if payload.get("operator_assisted") is not True or payload.get("fully_unattended") is not False:
        return None
    if payload.get("validation_errors"):
        return None
    if not str(payload.get("invoice_id") or "").strip():
        return None
    return payload


def _operator_assisted_candidate_fields(annotation: Mapping[str, Any] | None) -> dict[str, Any]:
    if not annotation:
        return {}
    return {
        "pdf_export_candidate_provenance_status": "OPERATOR_ASSISTED",
        "operator_assisted": True,
        "fully_unattended": False,
        "operator_intervention_kind": annotation.get("operator_intervention_kind"),
        "operator_assistance_annotation_ref": annotation.get("annotation_id"),
    }


def _operator_assisted_provenance(annotation: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not annotation:
        return None
    artifact = annotation.get("pdf_artifact") if isinstance(annotation.get("pdf_artifact"), Mapping) else {}
    return {
        "status": "OPERATOR_ASSISTED",
        "annotation_ref": annotation.get("annotation_id"),
        "annotation_receipt_type": annotation.get("annotation_receipt_type"),
        "source_candidate_receipt_id": annotation.get("source_candidate_receipt_id"),
        "source_candidate_receipt_path": annotation.get("source_candidate_receipt_path"),
        "operator_assisted": True,
        "fully_unattended": False,
        "operator_intervention_kind": annotation.get("operator_intervention_kind"),
        "prompt_text_known": annotation.get("prompt_text_known"),
        "permission_or_access_granted_by_operator": annotation.get("permission_or_access_granted_by_operator"),
        "export_candidate_remains_review_required": annotation.get("export_candidate_remains_review_required"),
        "artifact_review_status": annotation.get("artifact_review_status"),
        "attachment_ready": False,
        "approval_ready": False,
        "ledger_posting_allowed": False,
        "pdf_path": artifact.get("path"),
        "pdf_mac_path": artifact.get("mac_path"),
        "artifact_filename": artifact.get("artifact_filename"),
        "sha256": artifact.get("sha256"),
        "page_count": artifact.get("page_count"),
        "expected_page_count": artifact.get("expected_page_count"),
        "reason_code": annotation.get("reason_code"),
    }


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _candidate_review_artifact_metadata(path_text: str, expected_sha256: str | None) -> dict[str, Any]:
    path = Path(path_text) if path_text else None
    if path is None:
        return {
            "exists": False,
            "is_file": False,
            "file_size_bytes": None,
            "sha256": None,
            "extension": None,
            "metadata_status": "MISSING_PATH",
        }
    if not path.exists() or not path.is_file():
        return {
            "exists": path.exists(),
            "is_file": path.is_file() if path.exists() else False,
            "file_size_bytes": None,
            "sha256": None,
            "extension": path.suffix.lower(),
            "metadata_status": "MISSING_FILE",
        }
    data = path.read_bytes()
    observed_sha256 = hashlib.sha256(data).hexdigest()
    expected_normalized = str(expected_sha256 or "").removeprefix("sha256:").strip()
    return {
        "exists": True,
        "is_file": True,
        "file_size_bytes": len(data),
        "sha256": observed_sha256,
        "extension": path.suffix.lower(),
        "metadata_status": "METADATA_MATCH"
        if not expected_normalized or observed_sha256 == expected_normalized
        else "SHA256_MISMATCH",
    }


def _replaced_failed_candidate_from_receipt(receipt: Mapping[str, Any]) -> dict[str, Any] | None:
    failed_sha = str(receipt.get("failed_candidate_sha256") or "").removeprefix("sha256:").strip()
    failed_page_count = _int_or_none(receipt.get("observed_failed_candidate_page_count"))
    failed_ref = str(receipt.get("final_candidate_parent_ref") or "").strip()
    if not failed_sha and failed_page_count is None and not failed_ref:
        return None
    return {
        "candidate_ref": failed_ref or None,
        "sha256": failed_sha or None,
        "artifact_review_status": str(
            receipt.get("failed_candidate_artifact_review_status")
            or ARTIFACT_REVIEW_STATUS_SCOPE_MISMATCH_REJECTED
        ),
        "reason_code": str(
            receipt.get("failed_candidate_reason_code")
            or ARTIFACT_REVIEW_REASON_WRONG_EXPORT_SCOPE
        ),
        "observed_page_count": failed_page_count,
        "expected_page_count": EXPECTED_SELECTED_INVOICE_PAGE_COUNT,
        "preserved_as": "rejected_candidate_lineage",
    }


def _artifact_candidate_review_card(
    *,
    selected_invoice_summary_text: str | None,
    selected_invoice_candidate: Mapping[str, Any] | None,
    pdf_export_package: Mapping[str, Any],
    pdf_export_result_receipt: Mapping[str, Any] | None,
    export_candidate_provenance: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not pdf_export_result_receipt or pdf_export_result_receipt.get("export_success") is not True:
        return None
    invoice_id = str(pdf_export_result_receipt.get("invoice_id") or pdf_export_package.get("invoice_id") or "").strip()
    pdf_bridge_path = str(
        pdf_export_result_receipt.get("pdf_bridge_path")
        or pdf_export_result_receipt.get("output_bridge_path")
        or (export_candidate_provenance or {}).get("pdf_path")
        or pdf_export_package.get("output_bridge_path")
        or ""
    )
    pdf_mac_path = str(
        pdf_export_result_receipt.get("exported_pdf_mac_path")
        or pdf_export_result_receipt.get("pdf_mac_path")
        or (export_candidate_provenance or {}).get("pdf_mac_path")
        or pdf_export_package.get("output_pdf_mac_path")
        or ""
    )
    artifact_filename = str(
        pdf_export_result_receipt.get("artifact_filename")
        or pdf_export_package.get("output_filename")
        or Path(pdf_bridge_path).name
        or ""
    )
    expected_size = _int_or_none(pdf_export_result_receipt.get("file_size_bytes"))
    expected_sha256 = str(
        pdf_export_result_receipt.get("sha256")
        or (export_candidate_provenance or {}).get("sha256")
        or ""
    ).removeprefix("sha256:")
    page_count = _int_or_none(
        pdf_export_result_receipt.get("page_count")
        if pdf_export_result_receipt.get("page_count") not in (None, "")
        else (export_candidate_provenance or {}).get("page_count")
    )
    expected_page_count = (
        _int_or_none(pdf_export_result_receipt.get("expected_page_count"))
        or _int_or_none((export_candidate_provenance or {}).get("expected_page_count"))
        or EXPECTED_SELECTED_INVOICE_PAGE_COUNT
    )
    selected_sheet_label = str(
        (selected_invoice_candidate or {}).get("sheet_label")
        or pdf_export_package.get("selected_sheet_label")
        or ""
    )
    selected_invoice_amount = (selected_invoice_candidate or {}).get("amount")
    observed_metadata = _candidate_review_artifact_metadata(pdf_bridge_path, expected_sha256)
    replaced_failed_candidate = _replaced_failed_candidate_from_receipt(pdf_export_result_receipt)
    warnings = []
    if page_count and page_count > 1:
        if page_count == 7:
            warnings.append("Seven-page PDF requires visual review before approval.")
        else:
            warnings.append(f"{page_count}-page PDF requires visual review before approval.")

    reason_code = None
    if page_count is not None and page_count != expected_page_count:
        status = ARTIFACT_REVIEW_STATUS_SCOPE_MISMATCH_REJECTED
        reason_code = ARTIFACT_REVIEW_REASON_WRONG_EXPORT_SCOPE
        operator_copy = (
            f"PDF export candidate has {page_count} pages, but selected invoice {invoice_id} "
            f"must be a {expected_page_count}-page export. Preserve this rejected candidate and prepare a scoped replacement."
        )
        warnings.append(f"Expected {expected_page_count} page; observed {page_count}.")
    elif not observed_metadata["exists"]:
        status = "CANDIDATE_FILE_MISSING"
        operator_copy = "PDF export candidate file is missing. Re-run the scoped export or provide a replacement candidate."
    elif (
        observed_metadata["extension"] != ".pdf"
        or observed_metadata["file_size_bytes"] in (0, 14)
        or (expected_size is not None and observed_metadata["file_size_bytes"] != expected_size)
        or observed_metadata["metadata_status"] == "SHA256_MISMATCH"
    ):
        status = "CANDIDATE_INVALID"
        operator_copy = "PDF export candidate metadata does not match the recorded receipt. Do not approve it for attachment."
    else:
        status = ARTIFACT_REVIEW_STATUS_OPERATOR_REVIEW_REQUIRED
        operator_copy = "PDF export candidate recorded. Review this PDF before approving it for draft attachment."

    review_ready = status == ARTIFACT_REVIEW_STATUS_OPERATOR_REVIEW_REQUIRED
    scope_rejected = status == ARTIFACT_REVIEW_STATUS_SCOPE_MISMATCH_REJECTED
    candidate_ref = str(
        pdf_export_result_receipt.get("candidate_ref")
        or pdf_export_result_receipt.get("receipt_id")
        or (f"{CLIENT_REF}_{invoice_id.replace('-', '_')}_pdf_export_candidate" if invoice_id else "")
    ) or None
    return {
        "status": status,
        "artifact_review_status": status,
        "reason_code": reason_code,
        "candidate_ref": candidate_ref,
        "client_ref": CLIENT_REF,
        "workflow_ref": WORKFLOW_REF,
        "invoice_id": invoice_id,
        "selected_invoice_id": invoice_id,
        "selected_sheet_label": selected_sheet_label,
        "selected_invoice_amount": selected_invoice_amount,
        "selected_invoice_summary": selected_invoice_summary_text,
        "artifact_kind": "PDF",
        "artifact_filename": artifact_filename,
        "pdf_bridge_path": pdf_bridge_path,
        "pdf_mac_path": pdf_mac_path,
        "file_size_bytes": expected_size,
        "observed_file_size_bytes": observed_metadata["file_size_bytes"],
        "sha256": expected_sha256 or None,
        "observed_sha256": observed_metadata["sha256"],
        "page_count": page_count,
        "observed_page_count": page_count,
        "expected_page_count": expected_page_count,
        "operator_assisted": bool((export_candidate_provenance or {}).get("operator_assisted")),
        "fully_unattended": (export_candidate_provenance or {}).get("fully_unattended")
        if export_candidate_provenance
        else None,
        "operator_intervention_kind": (export_candidate_provenance or {}).get("operator_intervention_kind"),
        "preview_available_expected": review_ready or (scope_rejected and observed_metadata["exists"]),
        "operator_copy": operator_copy,
        "warnings": tuple(dict.fromkeys(warnings)),
        "allowed_actions": (
            "preview_pdf_candidate",
            "approve_pdf_candidate_for_draft_attachment",
            "reject_pdf_candidate",
        )
        if review_ready
        else (
            "preview_pdf_candidate",
            "reject_pdf_candidate",
        )
        if scope_rejected
        else ("reject_pdf_candidate",),
        "blocked_actions": (
            ("approve_pdf_candidate_for_draft_attachment",)
            if scope_rejected
            else ()
        ) + (
            "send_email",
            "mark_paid",
            "post_ledger",
            "claim_final_approval",
        ),
        "source_candidate_receipt_id": pdf_export_result_receipt.get("receipt_id"),
        "operator_assistance_annotation_ref": (export_candidate_provenance or {}).get("annotation_ref"),
        "replaced_failed_candidate": replaced_failed_candidate,
        "failed_candidate_preserved": replaced_failed_candidate is not None,
        "metadata_proof": {
            "candidate_file_exists": observed_metadata["exists"],
            "candidate_file_is_pdf": observed_metadata["extension"] == ".pdf",
            "file_size_matches_receipt": expected_size is None
            or observed_metadata["file_size_bytes"] == expected_size,
            "sha256_matches_receipt": not expected_sha256
            or observed_metadata["sha256"] == expected_sha256,
            "metadata_status": observed_metadata["metadata_status"],
        },
        "attachment_ready": False,
        "approval_ready": False,
        "ledger_posting_allowed": False,
        "no_email_send": True,
        "no_gmail": True,
        "no_browser": True,
        "no_coupa": True,
        "no_ledger_post": True,
        "no_workbook_cell_read": True,
        "sent": False,
        "paid": False,
        "final": False,
        "candidate_only": True,
        "review_required_before_attachment": True,
        "rejected_before_attachment": scope_rejected,
    }


def _resolved_artifact_review_status(
    *,
    pdf_export_package: Mapping[str, Any],
    pdf_export_completion_receipt: str,
    present_receipts: set[str],
    artifact_candidate_review: Mapping[str, Any] | None,
) -> str:
    if isinstance(artifact_candidate_review, Mapping):
        return str(
            artifact_candidate_review.get("artifact_review_status")
            or artifact_candidate_review.get("status")
            or ARTIFACT_REVIEW_STATUS_NOT_READY
        )
    if pdf_export_package.get("status") == "EXPORT_FAILED":
        return ARTIFACT_REVIEW_STATUS_EXPORT_FAILED
    if pdf_export_completion_receipt in present_receipts:
        return ARTIFACT_REVIEW_STATUS_OPERATOR_REVIEW_REQUIRED
    return ARTIFACT_REVIEW_STATUS_NOT_READY


def _artifact_candidate_surface_fields(
    *,
    artifact_candidate_review: Mapping[str, Any] | None,
    export_candidate_provenance: Mapping[str, Any] | None,
    artifact_review_status: str,
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "artifact_review_status": artifact_review_status,
        "page_count": None,
        "observed_page_count": None,
        "expected_page_count": EXPECTED_SELECTED_INVOICE_PAGE_COUNT,
        "operator_assisted": bool((export_candidate_provenance or {}).get("operator_assisted")),
        "fully_unattended": (export_candidate_provenance or {}).get("fully_unattended")
        if export_candidate_provenance
        else None,
    }
    if isinstance(artifact_candidate_review, Mapping):
        fields.update(
            {
                "candidate_ref": artifact_candidate_review.get("candidate_ref"),
                "reason_code": artifact_candidate_review.get("reason_code"),
                "sha256": artifact_candidate_review.get("sha256"),
                "pdf_bridge_path": artifact_candidate_review.get("pdf_bridge_path"),
                "pdf_mac_path": artifact_candidate_review.get("pdf_mac_path"),
                "page_count": artifact_candidate_review.get("page_count"),
                "observed_page_count": artifact_candidate_review.get("observed_page_count"),
                "expected_page_count": artifact_candidate_review.get("expected_page_count"),
                "selected_invoice_id": artifact_candidate_review.get("selected_invoice_id"),
                "selected_sheet_label": artifact_candidate_review.get("selected_sheet_label"),
                "selected_invoice_amount": artifact_candidate_review.get("selected_invoice_amount"),
                "operator_assisted": artifact_candidate_review.get("operator_assisted"),
                "fully_unattended": artifact_candidate_review.get("fully_unattended"),
                "attachment_ready": False,
                "approval_ready": False,
                "ledger_posting_allowed": False,
            }
        )
    return fields


def _selected_candidate_from_receipt(receipt: Mapping[str, Any] | None) -> dict[str, Any] | None:
    valid_receipt = _selection_receipt_from_payload(receipt)
    if valid_receipt is None:
        return None
    invoice_id = str(valid_receipt.get("invoice_id") or "").strip()
    candidate = dict(_invoice_candidate_lookup(invoice_id) or {})
    if not candidate:
        return None
    if valid_receipt.get("sheet_label"):
        candidate["sheet_label"] = str(valid_receipt["sheet_label"])
    candidate["invoice_id"] = invoice_id
    candidate["selection_status"] = "OPERATOR_CONFIRMED"
    candidate["selection_source"] = "live_arts_md_invoice_candidate_selected_receipt"
    candidate["selection_receipt_id"] = valid_receipt.get("receipt_id")
    candidate["selection_receipt_name"] = valid_receipt.get("receipt_event")
    return candidate


def _selected_candidate_from_pdf_export_receipt(receipt: Mapping[str, Any] | None) -> dict[str, Any] | None:
    valid_receipt = _pdf_export_result_receipt_from_payload(receipt)
    if valid_receipt is None:
        return None
    invoice_id = str(valid_receipt.get("invoice_id") or "").strip()
    candidate = dict(_invoice_candidate_lookup(invoice_id) or {})
    if not candidate:
        return None
    candidate["invoice_id"] = invoice_id
    candidate["selection_status"] = "OPERATOR_CONFIRMED"
    candidate["selection_source"] = "selected_invoice_pdf_export_completed_candidate_receipt"
    candidate["selection_receipt_id"] = valid_receipt.get("receipt_id")
    candidate["selection_receipt_name"] = valid_receipt.get("receipt_name")
    return candidate


def _selected_invoice_summary_text(candidate: Mapping[str, Any]) -> str:
    amount = candidate.get("amount")
    amount_display = candidate.get("amount_display") or (
        f"${amount:,.0f}" if isinstance(amount, (int, float)) else f"${amount}" if amount not in (None, "") else ""
    )
    return " — ".join(
        part
        for part in (
            str(candidate.get("invoice_id") or "").strip(),
            str(candidate.get("sheet_label") or candidate.get("work_or_period") or "").strip(),
            str(amount_display or "").strip(),
        )
        if part
    )


def _scope_source_receipt(candidate: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not candidate:
        return None
    return {
        "receipt_id": candidate.get("selection_receipt_id"),
        "receipt_name": candidate.get("selection_receipt_name"),
        "selection_source": candidate.get("selection_source"),
        "invoice_id": candidate.get("invoice_id"),
    }


def _contains_stale_placeholder(value: object) -> bool:
    text = str(value or "")
    return "/selected-invoice/" in text or "selected-invoice.pdf" in text or "/unknown-sheet/" in text


def _payload_scope_errors(
    payload: Mapping[str, Any] | None,
    *,
    base_path: str,
    selected_candidate: Mapping[str, Any] | None,
    require_sheet_and_print: bool,
) -> tuple[str, ...]:
    if not isinstance(payload, Mapping) or not selected_candidate:
        return ()
    expected_invoice_id = str(selected_candidate.get("invoice_id") or "").strip()
    expected_sheet = str(selected_candidate.get("sheet_label") or "").strip()
    expected_print_areas = _as_sequence(selected_candidate.get("operator_provided_ranges"))
    errors: list[str] = []

    observed_invoice_id = str(payload.get("invoice_id") or "").strip()
    if observed_invoice_id != expected_invoice_id:
        errors.append(f"{base_path}.invoice_id")

    if require_sheet_and_print:
        observed_sheet = str(payload.get("selected_sheet_label") or "").strip()
        if observed_sheet != expected_sheet:
            errors.append(f"{base_path}.selected_sheet_label")
        observed_print_areas = _as_sequence(payload.get("selected_print_areas"))
        if observed_print_areas != expected_print_areas:
            errors.append(f"{base_path}.selected_print_areas")

    output_pdf_mac_path = str(payload.get("output_pdf_mac_path") or "")
    output_bridge_path = str(payload.get("output_bridge_path") or "")
    output_mac_path = str(payload.get("output_mac_path") or payload.get("output_path_policy") or "")
    if _contains_stale_placeholder(output_pdf_mac_path):
        errors.append(f"{base_path}.output_pdf_mac_path")
    if _contains_stale_placeholder(output_bridge_path):
        errors.append(f"{base_path}.output_bridge_path")
    if _contains_stale_placeholder(output_mac_path):
        errors.append(f"{base_path}.output_mac_path")
    if output_pdf_mac_path and expected_invoice_id and f"/{expected_invoice_id}/" not in output_pdf_mac_path:
        errors.append(f"{base_path}.output_pdf_mac_path")
    if output_bridge_path and expected_invoice_id and f"/{expected_invoice_id}/" not in output_bridge_path:
        errors.append(f"{base_path}.output_bridge_path")
    if output_pdf_mac_path and output_bridge_path:
        if output_pdf_mac_path.replace("/Volumes/openclaw_e", "/mnt/e/openclaw") != output_bridge_path:
            errors.append(f"{base_path}.output_bridge_path")
    return tuple(dict.fromkeys(errors))


def _pdf_export_scope_consistency(
    *,
    selected_candidate: Mapping[str, Any] | None,
    pdf_export_package: Mapping[str, Any],
    prepare_pdf_payload: Mapping[str, Any] | None = None,
    artifact_placement_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    selected_invoice_exists = bool(selected_candidate and str(selected_candidate.get("invoice_id") or "").strip())
    stale_paths: list[str] = []
    bad_paths: list[str] = []
    targets: tuple[tuple[str, Mapping[str, Any] | None, bool], ...] = (
        ("invoice_artifact.pdf_export_package", pdf_export_package, True),
        ("proof_timeline[2].primary_action.hidden_request_payload", prepare_pdf_payload, True),
        ("invoice_artifact.artifact_placement_policy", artifact_placement_policy, False),
    )
    for base_path, payload, require_sheet_and_print in targets:
        if not isinstance(payload, Mapping):
            continue
        for key, value in payload.items():
            if key in {"output_pdf_mac_path", "output_bridge_path", "output_mac_path", "output_path_policy"}:
                if _contains_stale_placeholder(value):
                    stale_paths.append(f"{base_path}.{key}")
        bad_paths.extend(
            _payload_scope_errors(
                payload,
                base_path=base_path,
                selected_candidate=selected_candidate,
                require_sheet_and_print=require_sheet_and_print,
            )
        )

    deduped_bad_paths = tuple(dict.fromkeys(bad_paths))
    deduped_stale_paths = tuple(dict.fromkeys(stale_paths))
    status = (
        PDF_EXPORT_SCOPE_DRIFT
        if selected_invoice_exists and deduped_bad_paths
        else "SCOPED"
        if selected_invoice_exists
        else "NO_SELECTED_INVOICE"
    )
    return {
        "selected_invoice_scope_status": "SELECTED_INVOICE_PRESENT" if selected_invoice_exists else "NO_SELECTED_INVOICE",
        "pdf_export_scope_status": status,
        "scope_consistency_status": status,
        "stale_placeholder_detected": bool(deduped_stale_paths),
        "bad_json_paths": deduped_bad_paths,
        "stale_placeholder_json_paths": deduped_stale_paths,
        "selected_invoice_id": str((selected_candidate or {}).get("invoice_id") or ""),
        "selected_sheet_label": str((selected_candidate or {}).get("sheet_label") or ""),
        "selected_print_areas": _as_sequence((selected_candidate or {}).get("operator_provided_ranges")),
    }


def _apply_scope_drift_block(
    pdf_export_package: dict[str, Any],
    scope_consistency: Mapping[str, Any],
) -> None:
    bad_paths = tuple(scope_consistency.get("bad_json_paths") or ())
    if not bad_paths:
        return
    pdf_export_package["status"] = PDF_EXPORT_SCOPE_DRIFT
    pdf_export_package["request_payload_ready"] = False
    pdf_export_package["missing_requirements"] = tuple(
        dict.fromkeys(tuple(pdf_export_package.get("missing_requirements") or ()) + bad_paths)
    )
    pdf_export_package["operator_review_prompt"] = "Resolve PDF export scope drift before preparing invoice PDF."
    pdf_export_package["scope_consistency_status"] = PDF_EXPORT_SCOPE_DRIFT
    pdf_export_package["scope_drift_json_paths"] = bad_paths


def _expected_receivable_state(
    *,
    manual_send_proof: Mapping[str, Any] | None,
    selected_invoice_summary: Mapping[str, Any] | None,
    payment_watch_status: str,
    manual_send_status: str,
) -> dict[str, Any]:
    return simple_builder.build_expected_receivable_state(
        fixture=_SIMPLE_INVOICE_CONFIG,
        manual_send_proof=manual_send_proof,
        selected_invoice_summary=selected_invoice_summary,
        payment_watch_status=payment_watch_status,
        manual_send_status=manual_send_status,
    )


def _workbook_records(payload: Mapping[str, Any] | None) -> tuple[dict[str, Any], ...]:
    if not isinstance(payload, Mapping):
        return ()
    records: list[dict[str, Any]] = []
    for key in ("active_record", "candidate_record", "existing_record"):
        item = payload.get(key)
        if isinstance(item, Mapping):
            records.append(dict(item))
    registry = payload.get("registry") if isinstance(payload.get("registry"), Mapping) else {}
    for item in registry.get("client_records") or ():
        if isinstance(item, Mapping):
            records.append(dict(item))
    filtered = [
        record
        for record in records
        if record.get("client_ref") == CLIENT_REF and record.get("workflow_ref") == WORKFLOW_REF
    ]
    deduped: dict[str, dict[str, Any]] = {}
    for record in filtered:
        deduped[str(record.get("workbook_ref") or _short_hash(record))] = record
    return tuple(deduped.values())


def inspect_source_workbook_state(
    *,
    workbook_registry_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = (
        workbook_registry_payload
        if workbook_registry_payload is not None
        else client_invoice_workbook_registry.load_existing_payload()
    )
    records = _workbook_records(payload)
    confirmed = next((record for record in records if record.get("workbook_status") == "WORKBOOK_CONFIRMED"), None)
    candidate = confirmed or (records[0] if records else None)
    status = "CONFIRMED" if confirmed else "CANDIDATE_ONLY" if candidate else "SOURCE_WORKBOOK_REQUIRED"
    return {
        "status": status,
        "client_ref": CLIENT_REF,
        "workflow_ref": WORKFLOW_REF,
        "expected_display_name": EXPECTED_WORKBOOK_NAME,
        "workbook_ref": candidate.get("workbook_ref") if candidate else None,
        "workbook_display_name": candidate.get("workbook_display_name") if candidate else None,
        "workbook_path_ref": candidate.get("workbook_path_ref") if candidate else None,
        "approved_for_metadata_read": bool(candidate.get("approved_for_metadata_read")) if candidate else False,
        "approved_for_cell_read": False,
        "no_workbook_body_read": True,
        "no_cell_read": True,
        "next_action": f"Choose the {CLIENT_DISPLAY_NAME} source workbook."
        if not confirmed
        else f"Select the {CLIENT_DISPLAY_NAME} invoice page/period.",
    }


def validate_operator_invoice_artifact_metadata(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    result: dict[str, Any] = {
        "path": path.as_posix(),
        "exists": path.exists(),
        "extension": suffix,
        "allowed_extension": suffix in ALLOWED_ARTIFACT_EXTENSIONS,
        "file_size": None,
        "sha256": None,
        "metadata_only": True,
        "body_read": False,
        "content_extracted": False,
    }
    if suffix not in ALLOWED_ARTIFACT_EXTENSIONS:
        result["status"] = "BLOCKED_EXTENSION_NOT_ALLOWED"
        return result
    if not path.exists() or not path.is_file():
        result["status"] = "BLOCKED_ARTIFACT_PATH_NOT_FOUND"
        return result
    data = path.read_bytes()
    result["file_size"] = len(data)
    result["sha256"] = "sha256:" + hashlib.sha256(data).hexdigest()
    result["status"] = "METADATA_VALID"
    return result


def _known_artifact_guardrails() -> dict[str, Any]:
    bridge_path = Path(KNOWN_INVALID_BRIDGE_PDF_PC_PATH)
    observed_size = None
    if bridge_path.exists() and bridge_path.is_file():
        observed_size = bridge_path.stat().st_size
    return {
        "trusted_selected_invoice_artifact_present": False,
        "attachment_ready": False,
        "desktop_pdf": {
            "path": KNOWN_UNTRUSTED_DESKTOP_PDF_PATH,
            "trusted_as_selected_invoice_artifact": False,
            "status": ARTIFACT_REVIEW_STATUS_SCOPE_MISMATCH_REJECTED,
            "legacy_status": LEGACY_GUARDRAIL_NOT_TRUSTED_EXISTING_MULTI_PAGE_PDF,
            "artifact_review_status": ARTIFACT_REVIEW_STATUS_SCOPE_MISMATCH_REJECTED,
            "reason_code": ARTIFACT_REVIEW_REASON_WRONG_EXPORT_SCOPE,
            "known_page_count": 7,
            "observed_page_count": 7,
            "expected_page_count": EXPECTED_SELECTED_INVOICE_PAGE_COUNT,
            "selected_invoice_id": KNOWN_MANUAL_SEND_INVOICE_ID,
            "selected_sheet_label": KNOWN_MANUAL_SEND_WORK,
            "selected_invoice_amount": KNOWN_MANUAL_SEND_AMOUNT,
            "reason": "Existing desktop PDF is not scoped proof for selected invoice 2026-1001.",
        },
        "bridge_pdf_placeholder": {
            "mac_path": KNOWN_INVALID_BRIDGE_PDF_MAC_PATH,
            "pc_reference_path": KNOWN_INVALID_BRIDGE_PDF_PC_PATH,
            "trusted_as_selected_invoice_artifact": False,
            "status": "INVALID_PLACEHOLDER"
            if observed_size in (None, 14)
            else "INVALID_UNTRUSTED_EXISTING_BRIDGE_ARTIFACT",
            "expected_placeholder_size_bytes": 14,
            "observed_file_size_bytes": observed_size,
            "reason": "Existing bridge PDF is a placeholder and is not selected-invoice proof.",
        },
    }


def _artifact_state(
    *,
    artifact_reference_payload: Mapping[str, Any] | None = None,
    operator_artifact_path: str | None = None,
    present_receipts: set[str] | list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    receipt_set = {str(item) for item in present_receipts}
    payload = (
        artifact_reference_payload
        if artifact_reference_payload is not None
        else local_artifact_reference.load_existing_payload()
    )
    attachment_receipts = "invoice_attachment_confirmed_receipt" in receipt_set
    approved = local_artifact_reference.find_approved_readable_artifact(
        payload,
        world_ref="finance",
        workflow_ref=WORKFLOW_REF,
        client_ref=CLIENT_REF,
        artifact_kind="invoice_artifact",
        intended_use="client_invoice_email_attachment",
    )
    if approved:
        return {
            "status": "OPERATOR_PROVIDED_ARTIFACT_CANDIDATE",
            "artifact_ref": approved.get("artifact_ref"),
            "path_ref": approved.get("pc_path") or approved.get("approved_path_ref"),
            "hash": approved.get("sha256") or approved.get("artifact_hash"),
            "attachment_ready": bool(attachment_receipts),
            "candidate_only": True,
            "receipt_required_for_attachment_ready": "invoice_attachment_confirmed_receipt",
            "metadata_only": True,
        }
    if operator_artifact_path:
        metadata = validate_operator_invoice_artifact_metadata(Path(operator_artifact_path))
        return {
            "status": "OPERATOR_PROVIDED_ARTIFACT_CANDIDATE"
            if metadata["status"] == "METADATA_VALID"
            else metadata["status"],
            "artifact_ref": f"operator_invoice_artifact_candidate:{_short_hash(operator_artifact_path, metadata.get('sha256'))}",
            "path_ref": operator_artifact_path,
            "hash": metadata.get("sha256"),
            "attachment_ready": bool(attachment_receipts),
            "candidate_only": True,
            "receipt_required_for_attachment_ready": "invoice_attachment_confirmed_receipt",
            "metadata": metadata,
            "metadata_only": True,
        }
    return {
        "status": "ARTIFACT_REQUIRED",
        "artifact_ref": None,
        "path_ref": None,
        "hash": None,
        "attachment_ready": bool(attachment_receipts),
        "candidate_only": False,
        "receipt_required_for_attachment_ready": "operator_provided_invoice_artifact_linked_candidate_receipt",
        "next_action": "Attach existing PDF / link external artifact as a fallback if automatic export is unavailable.",
    }


def _action(
    action_kind: str,
    label: str,
    *,
    enabled: bool,
    intended_use: str,
    disabled_reason: str | None = None,
    extra_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "request_type": "INVOICE_REVIEW_ACTION_REQUEST",
        "client_ref": CLIENT_REF,
        "workflow_ref": WORKFLOW_REF,
        "action_kind": action_kind,
        "intended_use": intended_use,
        "no_external_action": True,
        "no_workbook_body_read": True,
        "no_cell_read": True,
        "email_send_allowed": False,
        "ledger_posting_allowed": False,
        "coupa_submit_allowed": False,
        "physical_deletion_allowed": False,
    }
    if extra_payload:
        payload.update(dict(extra_payload))
    return {
        "action_ref": f"{CLIENT_REF}_invoice_action:{_short_hash(action_kind, label)}",
        "action_kind": action_kind,
        "label": label,
        "enabled": enabled,
        "disabled_reason": disabled_reason,
        "operator_visible_message": label,
        "hidden_request_payload": payload,
    }


def build_live_arts_md_bundle(
    *,
    workbook_registry_payload: Mapping[str, Any] | None = None,
    source_workbook_override: Mapping[str, Any] | None = None,
    artifact_reference_payload: Mapping[str, Any] | None = None,
    operator_artifact_path: str | None = None,
    manual_send_proof: Mapping[str, Any] | None = None,
    selected_invoice_candidate: Mapping[str, Any] | None = None,
    selected_invoice_candidates: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]] | None = None,
    selection_receipt_payload: Mapping[str, Any] | None = None,
    consume_existing_selection_receipt: bool = True,
    export_receipt_payload: Mapping[str, Any] | None = None,
    operator_assistance_annotation_payload: Mapping[str, Any] | None = None,
    present_receipts: tuple[str, ...] | list[str] | set[str] = (),
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    receipts = {str(receipt) for receipt in present_receipts}
    recipe = workflow.recipes_by_client_ref()[CLIENT_REF]
    handoff_builder = _SIMPLE_INVOICE_FIXTURE.candidate_register_builder
    try:
        handoff = handoff_builder(generated_at=generated_at)
    except TypeError:
        handoff = handoff_builder()
    source = (
        dict(source_workbook_override)
        if source_workbook_override is not None
        else inspect_source_workbook_state(workbook_registry_payload=workbook_registry_payload)
    )
    if (
        source.get("status") == "SOURCE_WORKBOOK_REQUIRED"
        and workbook_registry_payload is None
        and source_workbook_override is None
    ):
        source.update(
            {
                "status": "CONFIRMED",
                "workbook_ref": handoff["source_workbook"]["source_workbook_ref"],
                "workbook_display_name": EXPECTED_WORKBOOK_NAME,
                "workbook_path_ref": handoff["source_workbook"]["source_workbook_mac_path"],
                "source_workbook_mac_path": handoff["source_workbook"]["source_workbook_mac_path"],
                "approved_for_metadata_read": True,
                "approved_for_cell_read": False,
                "no_workbook_body_read": True,
                "no_cell_read": True,
                "confirmation_basis": "operator_provided_workbook_handoff",
                "next_action": f"Choose which {CLIENT_DISPLAY_NAME} invoice to prepare.",
            }
        )
    source.setdefault("client_ref", CLIENT_REF)
    source.setdefault("workflow_ref", WORKFLOW_REF)
    source.setdefault("expected_display_name", EXPECTED_WORKBOOK_NAME)
    source.setdefault("approved_for_metadata_read", False)
    source.setdefault("approved_for_cell_read", False)
    source.setdefault("no_workbook_body_read", True)
    source.setdefault("no_cell_read", True)
    source.setdefault(
        "next_action",
        f"Select the {CLIENT_DISPLAY_NAME} invoice page/period."
        if source.get("status") == "CONFIRMED"
        else f"Choose the {CLIENT_DISPLAY_NAME} source workbook.",
    )
    source_confirmed = source["status"] == "CONFIRMED" or "source_workbook_reference_confirmed_receipt" in receipts
    explicit_selected_candidate_supplied = (
        selected_invoice_candidate is not None
        or selected_invoice_candidates is not None
    )
    candidates_list = list(selected_invoice_candidates) if selected_invoice_candidates is not None else []
    if not candidates_list and selected_invoice_candidate:
        candidates_list = [selected_invoice_candidate]
    selection_receipt = (
        _selection_receipt_from_payload(selection_receipt_payload)
        if selection_receipt_payload is not None
        else _load_existing_selection_receipt()
        if consume_existing_selection_receipt
        else None
    )
    pdf_export_result_receipt = (
        _pdf_export_result_receipt_from_payload(export_receipt_payload)
        if export_receipt_payload is not None
        else _load_existing_pdf_export_result_receipt()
        if consume_existing_selection_receipt and not explicit_selected_candidate_supplied
        else None
    )
    operator_assistance_annotation = (
        _pdf_export_operator_assistance_annotation_from_payload(operator_assistance_annotation_payload)
        if operator_assistance_annotation_payload is not None
        else _load_existing_pdf_export_operator_assistance_annotation()
        if consume_existing_selection_receipt and not explicit_selected_candidate_supplied
        else None
    )
    if not candidates_list:
        receipt_candidate = _selected_candidate_from_receipt(selection_receipt)
        if receipt_candidate is not None:
            candidates_list = [receipt_candidate]
            receipts.add(INVOICE_CANDIDATE_SELECTED_RECEIPT)
    if not candidates_list:
        result_candidate = _selected_candidate_from_pdf_export_receipt(pdf_export_result_receipt)
        if result_candidate is not None:
            candidates_list = [result_candidate]
            receipts.add(INVOICE_CANDIDATE_SELECTED_RECEIPT)
            if (
                pdf_export_result_receipt.get("export_success") is True
                or pdf_export_result_receipt.get("result_status") == PDF_EXPORT_COMPLETED_CANDIDATE
            ):
                receipts.add(PDF_EXPORT_COMPLETION_RECEIPT)
    if operator_assistance_annotation and candidates_list:
        annotation_invoice_id = str(operator_assistance_annotation.get("invoice_id") or "").strip()
        assistance_fields = _operator_assisted_candidate_fields(operator_assistance_annotation)
        candidates_list = [
            {**dict(candidate), **assistance_fields}
            if str(candidate.get("invoice_id") or "").strip() == annotation_invoice_id
            else dict(candidate)
            for candidate in candidates_list
        ]

    selected_invoice_summary = dict(candidates_list[0]) if len(candidates_list) == 1 else None

    if len(candidates_list) == 1:
        selected_invoice_summary_text = _selected_invoice_summary_text(candidates_list[0])
    elif len(candidates_list) > 1:
        selected_invoice_summary_text = f"{len(candidates_list)} candidates selected"
    else:
        selected_invoice_summary_text = None

    if selected_invoice_summary is not None:
        selected_invoice_summary.setdefault("selection_status", "OPERATOR_CONFIRMED")
        selected_invoice_summary.setdefault("selection_source", f"{CLIENT_REF}_invoice_candidate_register")
    invoice_selected = (
        len(candidates_list) > 0
        or "invoice_record_selection_operator_confirmed_receipt" in receipts
        or INVOICE_CANDIDATE_SELECTED_RECEIPT in receipts
    )
    invoice_candidate_selected = INVOICE_CANDIDATE_SELECTED_RECEIPT in receipts
    visible_invoice_candidates = tuple(candidates_list) if invoice_selected and candidates_list else tuple(handoff["invoice_candidates"])

    candidate_selection_rail = simple_builder.build_generic_candidate_selection_rail(
        client_ref=CLIENT_REF,
        selection_mode="MULTI",
        candidate_selection_status="OPERATOR_CONFIRMED" if invoice_selected else "NEEDS_SELECTION",
        selected_invoice_ids=tuple(str(c.get("invoice_id")) for c in candidates_list),
        selected_invoice_candidates=tuple(candidates_list),
        selected_invoice_summary=selected_invoice_summary_text,
        allow_multiple=True,
        max_candidates=None,
    )
    if invoice_selected and candidates_list:
        candidate_selection_rail["candidate_selection_set"] = tuple(candidates_list)
        candidate_selection_rail["selection_complete"] = True
        candidate_selection_rail["presentation_hints"] = {
            **candidate_selection_rail["presentation_hints"],
            "ask_for_more_invoices_after_first_selection": False,
            "candidate_cards_hidden_when_confirmed": True,
            "candidate_list_collapsed": True,
        }
    artifact = _artifact_state(
        artifact_reference_payload=artifact_reference_payload,
        operator_artifact_path=operator_artifact_path,
        present_receipts=receipts,
    )
    attachment_receipt = "invoice_attachment_confirmed_receipt"
    pdf_export_completion_receipt = PDF_EXPORT_COMPLETION_RECEIPT
    attachment_ready = attachment_receipt in receipts
    pdf_export_package, _ = _selected_invoice_pdf_export_package(
        selected_candidate=selected_invoice_summary,
        source_workbook=source,
        present_receipts=receipts,
    )
    export_candidate_provenance = _operator_assisted_provenance(operator_assistance_annotation)
    if export_candidate_provenance:
        pdf_export_package.update(
            {
                "export_candidate_provenance_status": "OPERATOR_ASSISTED",
                "operator_assisted": True,
                "fully_unattended": False,
                "operator_intervention_kind": export_candidate_provenance["operator_intervention_kind"],
                "operator_assistance_annotation_ref": export_candidate_provenance["annotation_ref"],
                "permission_or_access_granted_by_operator": export_candidate_provenance[
                    "permission_or_access_granted_by_operator"
                ],
                "export_candidate_remains_review_required": True,
            }
        )
    if export_receipt_payload and export_receipt_payload.get("export_attempted") and not export_receipt_payload.get("export_success"):
        pdf_export_package["status"] = "EXPORT_FAILED"
        pdf_export_package["export_attempted"] = True
        pdf_export_package["export_success"] = False
        pdf_export_package["failure_code"] = export_receipt_payload.get("failure_code", "UNKNOWN_ERROR")
        pdf_export_package["failure_message"] = export_receipt_payload.get("failure_message", "Unknown export failure")
        pdf_export_package["failed_stage"] = export_receipt_payload.get("failed_stage", "UNKNOWN")
        pdf_export_package["fallback_available"] = True
        pdf_export_package["fallback_action"] = "Attach existing PDF"
        pdf_export_package["no_email_send"] = True
        pdf_export_package["no_ledger_post"] = True

    initial_scope_consistency = _pdf_export_scope_consistency(
        selected_candidate=selected_invoice_summary,
        pdf_export_package=pdf_export_package,
    )
    if initial_scope_consistency["scope_consistency_status"] == PDF_EXPORT_SCOPE_DRIFT:
        _apply_scope_drift_block(pdf_export_package, initial_scope_consistency)

    if invoice_selected and selected_invoice_summary:
        invoice_id = str(selected_invoice_summary.get("invoice_id") or "unknown_invoice")
        filename_policy = str(pdf_export_package["output_filename"])
        artifact_placement_policy = {
            "canonical_artifact_ref": f"{CLIENT_REF}_invoice_pdf_{invoice_id}",
            "canonical_storage_venue": "MAC_LOCAL",
            "preferred_mac_output_dir": f"/Volumes/openclaw_e/artifacts/invoice_workbooks/{CLIENT_REF}/{invoice_id}",
            "preferred_bridge_output_dir": f"/mnt/e/openclaw/artifacts/invoice_workbooks/{CLIENT_REF}/{invoice_id}",
            "filename_policy": filename_policy,
            "output_pdf_mac_path": pdf_export_package["output_pdf_mac_path"],
            "output_bridge_path": pdf_export_package["output_bridge_path"],
            "output_pc_reference_path": pdf_export_package["output_pc_reference_path"],
            "local_role": "MAC_HELPER_WRITE_DESTINATION",
            "bridge_role": "PC_READ_MODEL_REFERENCE_AND_MIRROR_DESTINATION",
            "client_ref": CLIENT_REF,
            "workflow_ref": WORKFLOW_REF,
            "invoice_id": invoice_id,
            "work_type": str(selected_invoice_summary.get("work_or_period") or "unknown"),
            "artifact_kind": "PDF",
            "retrieval_paths": {
                "open_in_app": True,
                "show_in_finder": True,
                "mac_path": pdf_export_package["output_pdf_mac_path"],
                "bridge_path": pdf_export_package["output_bridge_path"],
                "telegram_available": False,
            },
            "access_required": ("WORKBOOK_ACCESS", "OUTPUT_FOLDER_PERMISSION", "APPLE_EVENTS"),
            "permission_repair_action": "Grant file/folder access via Access Broker",
            "retention_policy": "PERMANENT_FINANCE_RECORD",
        }
    else:
        artifact_placement_policy = None

    artifact_candidate_review = _artifact_candidate_review_card(
        selected_invoice_summary_text=selected_invoice_summary_text,
        selected_invoice_candidate=selected_invoice_summary,
        pdf_export_package=pdf_export_package,
        pdf_export_result_receipt=pdf_export_result_receipt,
        export_candidate_provenance=export_candidate_provenance,
    )
    artifact_review_status = _resolved_artifact_review_status(
        pdf_export_package=pdf_export_package,
        pdf_export_completion_receipt=pdf_export_completion_receipt,
        present_receipts=receipts,
        artifact_candidate_review=artifact_candidate_review,
    )
    if artifact_review_status == ARTIFACT_REVIEW_STATUS_SCOPE_MISMATCH_REJECTED:
        attachment_ready = False
    artifact_candidate_surface_fields = _artifact_candidate_surface_fields(
        artifact_candidate_review=artifact_candidate_review,
        export_candidate_provenance=export_candidate_provenance,
        artifact_review_status=artifact_review_status,
    )
    if artifact_candidate_review:
        pdf_export_package.update(
            {
                "artifact_review_status": artifact_review_status,
                "reason_code": artifact_candidate_review.get("reason_code"),
                "page_count": artifact_candidate_review.get("page_count"),
                "observed_page_count": artifact_candidate_review.get("observed_page_count"),
                "expected_page_count": artifact_candidate_review.get("expected_page_count"),
                "operator_assisted": artifact_candidate_review.get("operator_assisted"),
                "fully_unattended": artifact_candidate_review.get("fully_unattended"),
                "attachment_ready": False,
                "approval_ready": False,
                "ledger_posting_allowed": False,
            }
        )
    selected_invoice_pdf_prepared = (
        pdf_export_package["status"] == PDF_EXPORT_COMPLETED_CANDIDATE
        and artifact_review_status != ARTIFACT_REVIEW_STATUS_SCOPE_MISMATCH_REJECTED
    )
    artifact_candidate = artifact["status"] == "OPERATOR_PROVIDED_ARTIFACT_CANDIDATE"
    artifact_candidate_or_exported = (
        artifact_candidate
        or artifact_review_status == ARTIFACT_REVIEW_STATUS_OPERATOR_REVIEW_REQUIRED
        or (pdf_export_completion_receipt in receipts and artifact_candidate_review is None)
    )
    recipient_confirmed = "recipient_confirmation_receipt" in receipts
    comms_fixture = client_comms_thread_rail.build_clara_first_contact_draft(
        client_ref=CLIENT_REF,
        workflow_ref=WORKFLOW_REF,
        recipient_ref=RECIPIENT_REF,
        recipient_name=f"[{CLIENT_DISPLAY_NAME} contact]",
        subject=f"{CLIENT_DISPLAY_NAME} invoice",
        work_kind="invoice package",
        prior_clara_thread_exists="clara_started_thread_receipt" in receipts,
    )
    comms_draft = dict(comms_fixture["draft_candidate"])
    comms_policy = dict(comms_fixture["first_contact_policy"])
    comms_thread = dict(comms_fixture["thread_registry_record"])
    recipient_package = _SIMPLE_INVOICE_FIXTURE.recipient_package_builder(confirmed=recipient_confirmed)
    invoice_period_label = "operator-selected period" if invoice_selected else None
    manual_send_proof_state, manual_send_status = _manual_send_proof_status(
        manual_send_proof=manual_send_proof,
        present_receipts=receipts,
    )
    email_send_status = manual_send_status
    clara_package = clara_drafts.build_clara_invoice_email_draft_package(
        client_ref=CLIENT_REF,
        workflow_ref=WORKFLOW_REF,
        client_display_name=CLIENT_DISPLAY_NAME,
        recipient_package=recipient_package,
        attachment_ready=attachment_ready,
        attachment_refs=(str(artifact.get("artifact_ref")),) if attachment_ready and artifact.get("artifact_ref") else (),
        invoice_period_label=invoice_period_label,
        invoice_dates_covered=(),
        supplier_portal_required=False,
        supplier_portal_provider=None,
        portal_submission_status=None,
        first_contact_intro_required=bool(comms_policy["intro_required"]),
        first_contact_intro_policy_ref="generated/read_models/client_comms_thread_rail.json#live_arts_md_first_contact_policy",
        proof_refs=tuple(item for item in (artifact.get("artifact_ref"),) if item),
        present_receipts=receipts,
    )
    comms_draft.update(
        {
            "draft_ref": clara_package["draft_ref"],
            "subject": clara_package["subject"],
            "body": clara_package["body"],
            "selected_voice": clara_package["selected_voice"],
            "external_identity": clara_package["external_identity"],
            "draft_status": clara_package["draft_status"],
        }
    )
    clara_ready = True
    guardian_approval_request_ready = "guardian_approval_request_receipt" in receipts
    email_sent = "email_send_receipt" in receipts
    thread_watch_status = "THREAD_WATCH_READY" if email_sent else "BLOCKED_UNTIL_SENT_RECEIPT"
    payment_watch_status = (
        PAYMENT_WATCH_STATUS_ACTIVE_PENDING_PAYMENT
        if manual_send_status == MANUAL_SEND_PROOF_STATUS_CONFIRMED
        else PAYMENT_WATCH_STATUS_READINESS_ONLY
    )
    payment_watch_expected = _expected_receivable_state(
        manual_send_proof=manual_send_proof_state,
        selected_invoice_summary=selected_invoice_summary,
        payment_watch_status=payment_watch_status,
        manual_send_status=manual_send_status,
    )
    payment_watch_next_operator_copy = (
        f"Payment watch is active for {CLIENT_DISPLAY_NAME} invoice {payment_watch_expected['invoice_id']}. "
        "Ledger posting remains blocked until bank/payment proof exists."
        if payment_watch_status != PAYMENT_WATCH_STATUS_READINESS_ONLY
        else "Payment watch is read-only readiness until manual send proof is confirmed."
    )
    approval_ready = all(
        (
            source_confirmed,
            invoice_selected,
            artifact_candidate_or_exported,
            attachment_ready,
            recipient_confirmed,
            clara_ready,
            guardian_approval_request_ready,
        )
    )
    blockers = []
    if not source_confirmed:
        blockers.append(f"Choose the {CLIENT_DISPLAY_NAME} source workbook.")
    if source_confirmed and not invoice_selected:
        blockers.append("Invoice candidate selection has not been confirmed.")
    if source_confirmed and invoice_selected and not artifact_candidate_or_exported:
        if artifact_review_status == ARTIFACT_REVIEW_STATUS_SCOPE_MISMATCH_REJECTED:
            blockers.append("Rejected PDF export candidate has the wrong page count; prepare a one-page selected invoice PDF.")
        elif pdf_export_package["status"] == "EXPORT_FAILED":
            blockers.append(f"PDF export failed: {pdf_export_package.get('failure_message', 'Unknown failure')}.")
        elif pdf_export_package["status"] == "BLOCKED_MISSING_EXPORT_SCOPE":
            blockers.append(str(pdf_export_package.get("operator_review_prompt") or "Confirm the selected sheet/print area for the invoice.")
            )
        elif pdf_export_package["status"] == PDF_EXPORT_BLOCKED_MISSING_MAC_CAPABILITY:
            blockers.append("Prepare the selected invoice PDF requires a supported Mac workbook path.")
        elif pdf_export_package["status"] in {PDF_EXPORT_SCOPE_DRIFT, PDF_EXPORT_BLOCKED_SCOPE_INCONSISTENCY}:
            blockers.append(
                str(pdf_export_package.get("operator_review_prompt") or "Resolve PDF export scope drift before preparing invoice PDF.")
            )
        elif pdf_export_package["status"] in {PDF_EXPORT_BLOCKED_MISSING_SELECTION, PDF_EXPORT_REQUIRES_OPERATOR_REVIEW}:
            blockers.append(
                str(pdf_export_package.get("operator_review_prompt") or "Confirm the selected invoice scope for PDF export.")
            )
        else:
            blockers.append("Prepare invoice PDFs" if len(candidates_list) > 1 else "Prepare invoice PDF")
    if artifact_candidate_or_exported and not attachment_ready:
        blockers.append("Confirm the invoice artifact as the email attachment.")
    if not recipient_confirmed:
        blockers.append(f"Confirm the {CLIENT_DISPLAY_NAME} recipient/contact.")
    if not guardian_approval_request_ready:
        blockers.append("Guardian approval request is required before send approval.")
    if not approval_ready:
        blockers.append("Approval/send remains disabled until receipts exist.")

    source_action = _action(
        "replace_source_workbook_reference",
        f"Choose {CLIENT_DISPLAY_NAME} source workbook",
        enabled=not source_confirmed,
        intended_use="replace_source_workbook_reference",
        disabled_reason=None if not source_confirmed else "Source workbook is already confirmed.",
        extra_payload={"expected_workbook_display_name": EXPECTED_WORKBOOK_NAME},
    )
    selection_action = _action(
        "select_invoice_candidate",
        "Choose invoice candidate",
        enabled=source_confirmed and not invoice_selected,
        intended_use=WORKBOOK_SELECTION_USE,
        disabled_reason=(
            None
            if source_confirmed and not invoice_selected
            else "Invoice candidate selection already confirmed."
            if invoice_selected
            else "Choose the source workbook first."
        ),
        extra_payload={"operator_provided": True} if source_confirmed else None,
    )
    urgent_invoice_actions = tuple(handoff["urgent_actions"])
    visible_urgent_actions = () if invoice_selected and candidates_list else urgent_invoice_actions
    prepare_pdf_enabled = (
        pdf_export_package["status"] == PDF_EXPORT_PACKAGE_READY_FOR_MAC
        or artifact_review_status == ARTIFACT_REVIEW_STATUS_SCOPE_MISMATCH_REJECTED
    )
    prepare_pdf_action = _action(
        "prepare_selected_invoice_pdf_artifact",
        "Prepare invoice PDFs" if len(candidates_list) > 1 else "Prepare invoice PDF",
        enabled=prepare_pdf_enabled,
        intended_use="prepare_selected_invoice_pdf_artifact",
        disabled_reason=(
            "Invoice candidate selection has not been confirmed."
            if not invoice_selected
            else None
            if prepare_pdf_enabled
                else (
                pdf_export_package.get("operator_review_prompt")
                if pdf_export_package.get("operator_review_prompt")
                else "Rejected PDF candidate has the wrong page count; prepare a one-page selected invoice PDF."
                if artifact_review_status == ARTIFACT_REVIEW_STATUS_SCOPE_MISMATCH_REJECTED
                else "PDF export candidate is ready for operator review."
                if pdf_export_package["status"] == PDF_EXPORT_COMPLETED_CANDIDATE
                else "Prepare the selected invoice PDF requires source/workbook scope inputs."
            )
        ),
        extra_payload={
            "execution_venue": PDF_EXPORT_EXECUTION_VENUE,
            "required_capability": PDF_EXPORT_REQUIRED_CAPABILITY,
            "source_workbook_path": pdf_export_package["source_workbook_path"],
            "source_workbook_mac_path": pdf_export_package["source_workbook_mac_path"],
            "selected_sheet_label": pdf_export_package["selected_sheet_label"],
            "selected_page_label": pdf_export_package["selected_page_label"],
            "selected_print_areas": pdf_export_package["selected_print_areas"],
            "invoice_id": pdf_export_package["invoice_id"],
            "output_artifact_kind": PDF_EXPORT_OUTPUT_ARTIFACT_KIND,
            "output_filename": pdf_export_package["output_filename"],
            "output_pdf_mac_path": pdf_export_package["output_pdf_mac_path"],
            "output_mac_path": pdf_export_package["output_mac_path"],
            "output_bridge_path": pdf_export_package["output_bridge_path"],
            "output_pc_reference_path": pdf_export_package["output_pc_reference_path"],
            "output_path_policy": pdf_export_package["output_path_policy"],
            "request_copy": pdf_export_package["request_copy"],
            "result_intended_use": pdf_export_package["result_intended_use"],
            "operator_review_required": True,
            "no_physical_printing": True,
            "no_email_send": True,
            "no_gmail": True,
            "no_browser": True,
            "no_ledger_post": True,
            "no_coupa": True,
            "no_source_workbook_mutation": True,
            "no_workbook_cell_read": True,
            "workbook_cell_read_required": False,
            "operator_review_required_after_export": True,
            "required_receipts": pdf_export_package["required_receipts"],
            "required_receipt_ref": pdf_export_completion_receipt,
            "expected_page_count": EXPECTED_SELECTED_INVOICE_PAGE_COUNT,
            "replacement_for_rejected_candidate_ref": artifact_candidate_review.get("candidate_ref")
            if isinstance(artifact_candidate_review, Mapping)
            and artifact_review_status == ARTIFACT_REVIEW_STATUS_SCOPE_MISMATCH_REJECTED
            else None,
        },
    )
    scope_consistency = _pdf_export_scope_consistency(
        selected_candidate=selected_invoice_summary,
        pdf_export_package=pdf_export_package,
        prepare_pdf_payload=prepare_pdf_action["hidden_request_payload"],
        artifact_placement_policy=artifact_placement_policy,
    )
    pdf_export_package["selected_invoice_scope_status"] = scope_consistency["selected_invoice_scope_status"]
    pdf_export_package["pdf_export_scope_status"] = scope_consistency["pdf_export_scope_status"]
    pdf_export_package["scope_consistency_status"] = scope_consistency["scope_consistency_status"]
    pdf_export_package["stale_placeholder_detected"] = scope_consistency["stale_placeholder_detected"]
    artifact_action = _action(
        "attach_generated_invoice_artifact",
        "Attach existing PDF",
        enabled=invoice_selected,
        intended_use="manual_operator_link_generated_invoice_artifact",
        disabled_reason=None if invoice_selected else "Select the invoice page/period first.",
        extra_payload={"allowed_extensions": ALLOWED_ARTIFACT_EXTENSIONS},
    )
    recipient_action = _action(
        "review_and_confirm_recipients",
        "Confirm recipient",
        enabled=True,
        intended_use=RECIPIENT_CONFIRM_USE,
    )
    send_action = _action(
        "prepare_manual_send_package",
        "Prepare manual send package",
        enabled=approval_ready,
        intended_use=MANUAL_SEND_USE,
        disabled_reason=None if approval_ready else "Attachment, recipient, and approval receipts are required first.",
    )
    primary_blocker_action = (
        source_action
        if not source_confirmed
        else selection_action
        if not invoice_selected
        else prepare_pdf_action
        if invoice_selected and not artifact_candidate_or_exported
        else recipient_action
    )

    timeline = (
        {
            "step_ref": f"{INVOICE_STEP_PREFIX}:source_workbook",
            "title": "Source workbook",
            "status": "COMPLETE" if source_confirmed else "NEEDS_ACTION",
            "operator_summary": source["next_action"],
            "primary_action": source_action,
            "required_receipts": ("source_workbook_reference_confirmed_receipt",),
        },
        {
            "step_ref": f"{INVOICE_STEP_PREFIX}:invoice_page_period",
            "title": "Invoice candidate",
            "status": "COMPLETE" if invoice_selected else "NEEDS_ACTION" if source_confirmed else "BLOCKED",
            "operator_summary": f"Choose which {CLIENT_DISPLAY_NAME} invoice to prepare from operator-provided handoff facts.",
            "primary_action": selection_action,
            "secondary_actions": urgent_invoice_actions,
            "required_receipts": (INVOICE_CANDIDATE_SELECTED_RECEIPT,),
        },
        {
            "step_ref": f"{INVOICE_STEP_PREFIX}:invoice_artifact",
            "title": "Invoice artifact",
            "status": (
                "REJECTED" if artifact_review_status == ARTIFACT_REVIEW_STATUS_SCOPE_MISMATCH_REJECTED else
                "READY" if artifact_candidate_or_exported and attachment_ready else
                "CANDIDATE" if selected_invoice_pdf_prepared else
                "CANDIDATE" if artifact_candidate else
                "NEEDS_ACTION" if invoice_selected else "BLOCKED"
            ),
            "operator_summary": f"Prepare a scoped PDF for the selected {CLIENT_DISPLAY_NAME} invoice and attach it as the email artifact.",
            "selected_invoice_summary": selected_invoice_summary_text,
            "selected_invoice_candidate": selected_invoice_summary,
            "primary_action": prepare_pdf_action,
            "secondary_actions": (artifact_action,),
            "required_receipts": (
                PDF_EXPORT_COMPLETION_RECEIPT,
                "operator_provided_invoice_artifact_linked_candidate_receipt",
                "invoice_attachment_confirmed_receipt",
            ),
        },
        {
            "step_ref": f"{INVOICE_STEP_PREFIX}:clara_draft",
            "title": "Clara draft",
            "status": "DRAFT_ONLY",
            "operator_summary": "Clara first-contact draft is ready for review only. Nothing was sent.",
            "primary_action": None,
            "required_receipts": ("clara_email_draft_receipt",),
        },
        {
            "step_ref": f"{INVOICE_STEP_PREFIX}:client_comms_thread",
            "title": "Client comms thread",
            "status": "BLOCKED" if not email_sent else "THREAD_WATCH_READY",
            "operator_summary": "Thread watch is not active until a future Clara send receipt starts the thread.",
            "primary_action": None,
            "required_receipts": ("email_send_receipt", "thread_ref_receipt"),
        },
        {
            "step_ref": f"{INVOICE_STEP_PREFIX}:recipient_send",
            "title": "Recipient and send readiness",
            "status": "READY" if approval_ready else "BLOCKED",
            "operator_summary": "Manual send package can be prepared only after attachment, recipient, and approval receipts.",
            "primary_action": send_action,
            "required_receipts": (
                "recipient_confirmation_receipt",
                "operator_approval_receipt",
                "email_send_receipt",
                "manual_send_receipt",
            ),
        },
        {
            "step_ref": f"{INVOICE_STEP_PREFIX}:payment_watch",
            "title": "Payment watch",
            "status": "READY" if payment_watch_status != PAYMENT_WATCH_STATUS_READINESS_ONLY else "READINESS_ONLY",
            "operator_summary": payment_watch_next_operator_copy
            if payment_watch_status != PAYMENT_WATCH_STATUS_READINESS_ONLY
            else "Payment watch can begin once send proof is confirmed.",
            "primary_action": None,
            "required_receipts": ("manual_send_receipt",),
        },
    )

    bundle = {
        "schema_version": SCHEMA_VERSION,
        "bundle_id": BUNDLE_ID,
        "client_ref": CLIENT_REF,
        "client_display_name": CLIENT_DISPLAY_NAME,
        "workflow_ref": WORKFLOW_REF,
        "recipe_ref": recipe["workflow_ref"],
        "producer_ref": "live_arts_md_invoice_review_bundle.py:build_live_arts_md_bundle",
        "source_commit": _source_commit(),
        "scope_source_receipt": _scope_source_receipt(selected_invoice_summary),
        "selected_invoice_scope_status": scope_consistency["selected_invoice_scope_status"],
        "pdf_export_scope_status": scope_consistency["pdf_export_scope_status"],
        "scope_consistency_status": scope_consistency["scope_consistency_status"],
        "stale_placeholder_detected": scope_consistency["stale_placeholder_detected"],
        "scope_consistency": scope_consistency,
        "status": "SIMPLE_EMAIL_INVOICE_REVIEW",
        "selected_rails": tuple(item["rail_ref"] for item in recipe["selected_rails"]),
        "rails_not_selected_by_default": ("supplier_portal_rail", "purchase_order_rail"),
        "supplier_portal_invoice_submission": {
            "required": False,
            "supplier_portal_required": False,
            "supplier_portal_provider": None,
            "portal_submission_proof_required": False,
            "purchase_order_required": False,
            "status": "NOT_REQUIRED_BY_RECIPE",
        },
        "source_workbook": source,
        "operator_workbook_handoff": {
            "receipt": handoff["operator_handoff_receipt"],
            "operator_provided": True,
            "workbook_body_read": False,
            "cell_read": False,
            "confidence": "operator_handoff",
        },
        "candidate_selection_rail": candidate_selection_rail,
        "invoice_candidate_register_ref": INVOICE_CANDIDATE_REGISTER_REF,
        "invoice_candidate_register": {
            "candidate_count": len(visible_invoice_candidates),
            "total_candidate_count": handoff["candidate_count"],
            "candidate_list_status": "COLLAPSED_AFTER_CONFIRMED_SELECTION"
            if invoice_selected and candidates_list
            else "OPEN_FOR_SELECTION",
            "primary_next_action": handoff["primary_next_action"],
            "invoice_candidates": visible_invoice_candidates,
            "urgent_actions": visible_urgent_actions,
            "presentation_hints": {
                "candidate_cards_hidden_when_confirmed": bool(invoice_selected and candidates_list),
                "selected_summary_primary": bool(selected_invoice_summary_text),
                "show_selected_summary": bool(selected_invoice_summary_text),
            },
        },
        "invoice_selection": {
            "status": "OPERATOR_CONFIRMED"
            if invoice_candidate_selected
            else "NEEDS_CANDIDATE_SELECTION"
            if source_confirmed
            else "BLOCKED_NEEDS_SOURCE_WORKBOOK",
            "selected_invoice_ids": tuple(str(c.get("invoice_id")) for c in candidates_list),
            "selected_invoice_summary": selected_invoice_summary_text,
            "selected_invoice_candidate": selected_invoice_summary,
            "selection_receipt_ref": selected_invoice_summary.get("selection_receipt_id")
            if selected_invoice_summary
            else None,
            "no_workbook_body_read": True,
            "no_cell_read": True,
            "primary_action": selection_action,
            "urgent_actions": visible_urgent_actions,
        },
        "invoice_artifact": {
            **artifact,
            **artifact_candidate_surface_fields,
            "pdf_export_package": pdf_export_package,
            "artifact_placement_policy": artifact_placement_policy,
            "export_candidate_provenance": export_candidate_provenance,
            "artifact_candidate_review": artifact_candidate_review,
            "known_artifact_guardrails": _known_artifact_guardrails(),
        },
        "client_comms_thread": {
            "comms_thread_status": "DRAFT_READY" if clara_ready else "NOT_STARTED",
            "thread_ref": comms_draft["thread_ref"],
            "thread_registry_record": comms_thread,
            "external_identity": client_comms_thread_rail.CLARA_EXTERNAL_IDENTITY,
            "internal_identity": client_comms_thread_rail.CASSANDRA_INTERNAL_IDENTITY,
            "selected_voice": "CLARA",
            "channel": "email",
            "audience": "external_client",
            "first_contact_intro_required": comms_policy["intro_required"],
            "first_contact_intro_policy_ref": "generated/read_models/client_comms_thread_rail.json#first_contact_intro_policy",
            "first_contact_intro_policy": comms_policy,
            "clara_draft_status": clara_package["draft_status"],
            "draft_only": True,
            "sent": False,
            "guardian_output_validation_status": comms_draft["guardian_output_validation_status"],
            "guardian_approval_required": True,
            "guardian_approval_request_status": "READY" if guardian_approval_request_ready else "NOT_CREATED",
            "send_execution_receipt_required": True,
            "send_execution_status": "SENT_RECEIPT_CONFIRMED" if email_sent else "NOT_SENT",
            "thread_watch_status": thread_watch_status,
            "thread_watch_future_gated": not email_sent,
            "manual_send_proof_status": manual_send_status,
            "manual_send_proof": manual_send_proof_state,
            "live_gmail_polling_active": False,
            "gmail_draft_created": False,
            "required_receipts_before_send": comms_draft["required_receipts_before_send"],
        },
        "clara_email_draft": {
            "draft_ref": comms_draft["draft_ref"],
            "selected_voice": comms_draft["selected_voice"],
            "external_identity": comms_draft["external_identity"],
            "internal_identity": clara_package["internal_identity"],
            "draft_status": clara_package["draft_status"],
            "draft_only": True,
            "sent": False,
            "send_allowed": False,
            "guardian_approval_required": True,
            "subject": comms_draft["subject"],
            "body": comms_draft["body"],
            "attachment_claim": "attachment confirmed" if attachment_ready else "attachment not ready yet",
            "attachment_ready": clara_package["attachment_ready"],
            "missing_prerequisites": clara_package["missing_prerequisites"],
            "recipient_confirmation_status": clara_package["recipient_confirmation_status"],
            "send_readiness": clara_package["send_readiness"],
            "thread_ref": comms_draft["thread_ref"],
        },
        "clara_invoice_email_draft_package": clara_package,
        "client_alias_readiness": CLIENT_ALIAS_READINESS,
        "recipient_state": {
            "status": "CONFIRMED" if recipient_confirmed else "RECIPIENT_INFO_REQUIRED",
            "recipient_email_invented": False,
            "to_candidates": clara_package["to_recipients"],
            "cc_candidates": clara_package["cc_recipients"],
            "recipient_candidates": (*clara_package["to_recipients"], *clara_package["cc_recipients"]),
            "confirmation_receipt_required": "recipient_confirmation_receipt",
            "primary_action": recipient_action,
        },
        "send_readiness": {
            "email_send_rail_exists": False,
            "manual_send_package_status": "MANUAL_SEND_PACKAGE_READY" if approval_ready else "BLOCKED_PREREQUISITES",
            "email_send_status": email_send_status,
            "manual_send_proof_status": manual_send_status,
            "manual_send_proof": manual_send_proof_state,
            "email_send_approval_required": True,
            "guardian_approval_required": True,
            "guardian_approval_request_ready": guardian_approval_request_ready,
            "operator_approval_receipt_required": True,
            "email_send_execution_receipt_required": True,
            "sent_receipt_confirmed": email_sent,
            "thread_watch_status_after_send": "THREAD_WATCH_READY",
            "primary_action": send_action,
        },
        "manual_send_proof": manual_send_proof_state,
        "payment_watch": {
            "payment_watch_status": payment_watch_status,
            "client_ref": CLIENT_REF,
            "invoice_ref": artifact.get("artifact_ref"),
            "expected_ar_layer_required": True,
            "actual_bank_transactions_separate": True,
            "active_only_after_send_or_manual_send_receipt": True,
            "bank_ledger_read_performed": False,
            "bank_ledger_match_required": True,
            "manual_send_evidence_ref": manual_send_proof_state["proof_refs"],
            "ledger_posting_allowed": False,
            "expected_receivable_status": payment_watch_expected["expected_receivable_status"],
            "expected_client": payment_watch_expected["expected_payer_client"],
            "invoice_id": payment_watch_expected["invoice_id"],
            "expected_amount": payment_watch_expected["expected_amount"],
            "work_type": payment_watch_expected["work_type"],
            "work_or_period": payment_watch_expected["work_or_period"],
            "receipt_status": payment_watch_expected["receipt_status"],
            "ledger_match_status": payment_watch_expected["ledger_match_status"],
            "ledger_handoff_status": payment_watch_expected["ledger_handoff_status"],
            "review_status": payment_watch_expected["review_status"],
            "matching_requirements": payment_watch_expected["matching_requirements"],
            "allowed_next_steps": payment_watch_expected["allowed_next_steps"],
            "send_proof_ref": payment_watch_expected["send_proof_ref"],
            "send_proof_strength": payment_watch_expected["send_proof_strength"],
            "proof_capture_type": payment_watch_expected["proof_capture_type"],
            "expected_window": None,
            "next_operator_copy": payment_watch_next_operator_copy,
        },
        "ledger_planning": handoff["ledger_planning"],
        "contact_ambiguity": handoff["contact_ambiguity"],
        "approval_footer": {
            "approval_ready": approval_ready,
            "approval_disabled_reasons": tuple(blockers),
        },
        "blockers": tuple(blockers),
        "next_safe_move": "Invoice candidate selection has not been confirmed."
        if source_confirmed and not invoice_selected
        else blockers[0]
        if blockers
        else "Prepare manual send package after approval receipts.",
        "actionable_blockers": (
            (
                {
                    "blocker_ref": f"{INVOICE_BLOCKER_PREFIX}:{_short_hash(blockers[0])}",
                    "operator_summary": blockers[0],
                    "primary_action": primary_blocker_action,
                },
            )
            if blockers
            else ()
        ),
        "proof_timeline": timeline,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "generated_at": generated_at,
        "developer_end_to_end_card": {
            "title": "Live Arts invoice automation path",
            "workbook_confirmed": source_confirmed,
            "invoice_selected": invoice_selected,
            "pdf_export_rail_status": pdf_export_package["status"],
            "artifact_storage_policy": artifact_placement_policy,
            "clara_draft_status": clara_package["draft_status"],
            "recipient_status": "CONFIRMED" if recipient_confirmed else "PENDING",
            "send_proof_status": email_send_status,
            "payment_watch_status": payment_watch_status,
            "ledger_status": payment_watch_expected["ledger_match_status"],
            "fallbacks": {
                "mac_unavailable": "Attach existing PDF manually",
                "openclaw_bridge_unavailable": "Manual email + manual folder placement",
            }
        },
        "machine_proof": {
            "live_arts_md_does_not_require_coupa": True,
            "live_arts_md_does_not_require_po": True,
            "uses_reusable_simple_invoice_rails": True,
            "operator_handoff_not_workbook_parsed": True,
            "candidate_register_present": True,
            "workbook_existence_does_not_mark_sent_paid_or_ledger_posted": True,
            "clara_draft_only": True,
            "client_comms_thread_rail_consumed": True,
            "clara_invoice_draft_package_consumed": True,
            "clara_client_draft_body_status_free": not clara_package[
                "client_facing_body_has_backend_status_language"
            ],
            "arts_alive_alias_mapped_to_live_arts_md": CLIENT_ALIAS_READINESS_MATCHED,
            "clara_first_contact_intro_required": comms_policy["intro_required"],
            "thread_watch_blocked_until_send_receipt": thread_watch_status == "BLOCKED_UNTIL_SENT_RECEIPT",
            "send_execution_receipt_required": True,
            "no_recipient_email_invented": True,
            "artifact_candidate_not_attachment_ready": artifact.get("attachment_ready") is False,
            "payment_watch_readiness_only_no_bank_read": True,
            "approval_send_disabled_without_receipts": approval_ready is False,
            "no_action_authority": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "manual_send_proof_evaluated": bool(manual_send_proof_state),
            "manual_send_proof_status": manual_send_status,
            "content_hash": "",
            "operator_assisted_pdf_export_candidate": bool(export_candidate_provenance),
            "operator_assisted_candidate_not_fully_unattended": bool(export_candidate_provenance)
            and export_candidate_provenance.get("fully_unattended") is False,
            "artifact_candidate_review_surface_present": bool(artifact_candidate_review),
            "artifact_candidate_review_keeps_gates_closed": bool(artifact_candidate_review)
            and artifact_candidate_review.get("attachment_ready") is False
            and artifact_candidate_review.get("approval_ready") is False
            and artifact_candidate_review.get("ledger_posting_allowed") is False,
        },
    }
    bundle["machine_proof"]["content_hash"] = _content_hash(bundle)
    return bundle


def build_payload(
    *,
    generated_at: str | None = None,
    selected_invoice_candidate: Mapping[str, Any] | None = None,
    selected_invoice_candidates: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]] | None = None,
    selection_receipt_payload: Mapping[str, Any] | None = None,
    consume_existing_selection_receipt: bool = True,
    export_receipt_payload: Mapping[str, Any] | None = None,
    operator_assistance_annotation_payload: Mapping[str, Any] | None = None,
    workbook_registry_payload: Mapping[str, Any] | None = None,
    source_workbook_override: Mapping[str, Any] | None = None,
    artifact_reference_payload: Mapping[str, Any] | None = None,
    operator_artifact_path: str | None = None,
    manual_send_proof: Mapping[str, Any] | None = None,
    present_receipts: tuple[str, ...] | list[str] | set[str] = (),
) -> dict[str, Any]:
    bundle = build_live_arts_md_bundle(
        generated_at=generated_at,
        selected_invoice_candidate=selected_invoice_candidate,
        selected_invoice_candidates=selected_invoice_candidates,
        selection_receipt_payload=selection_receipt_payload,
        consume_existing_selection_receipt=consume_existing_selection_receipt,
        export_receipt_payload=export_receipt_payload,
        operator_assistance_annotation_payload=operator_assistance_annotation_payload,
        workbook_registry_payload=workbook_registry_payload,
        source_workbook_override=source_workbook_override,
        artifact_reference_payload=artifact_reference_payload,
        operator_artifact_path=operator_artifact_path,
        manual_send_proof=manual_send_proof,
        present_receipts=present_receipts,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or DEFAULT_GENERATED_AT,
        "producer_ref": "live_arts_md_invoice_review_bundle.py:build_payload",
        "source_commit": _source_commit(),
        "selected_invoice_scope_status": bundle["selected_invoice_scope_status"],
        "pdf_export_scope_status": bundle["pdf_export_scope_status"],
        "scope_consistency_status": bundle["scope_consistency_status"],
        "stale_placeholder_detected": bundle["stale_placeholder_detected"],
        "live_arts_md_bundle": bundle,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "live_arts_md_bundle_present": True,
            "bridge_safe": True,
            "no_action_authority": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": _content_hash(bundle),
        },
    }


def format_operator(payload: Mapping[str, Any]) -> str:
    bundle = payload["live_arts_md_bundle"]
    pdf_package = bundle["invoice_artifact"]["pdf_export_package"]
    provenance = bundle["invoice_artifact"].get("export_candidate_provenance")
    review = bundle["invoice_artifact"].get("artifact_candidate_review")
    lines = [
        "# Live Arts MD Invoice Review Bundle",
        "",
        f"- Status: `{bundle['status']}`",
        f"- Next safe move: {bundle['next_safe_move']}",
        f"- Source workbook: `{bundle['source_workbook']['status']}`",
        f"- Invoice page/period: `{bundle['invoice_selection']['status']}`",
        f"- Artifact: `{bundle['invoice_artifact']['status']}`",
        f"- Clara draft: `{bundle['clara_email_draft']['selected_voice']}` draft-only",
        f"- Recipient state: `{bundle['recipient_state']['status']}`",
        f"- Manual send package: `{bundle['send_readiness']['manual_send_package_status']}`",
        f"- Manual send proof: `{bundle['manual_send_proof']['proof_status']}`",
        f"- Payment watch: `{bundle['payment_watch']['payment_watch_status']}`",
        f"- PDF output Mac path: `{pdf_package.get('output_pdf_mac_path')}`",
        f"- PDF output bridge path: `{pdf_package.get('output_bridge_path')}`",
        *(
            (
                f"- PDF candidate review: `{review.get('status')}`",
                f"- PDF candidate reason: `{review.get('reason_code')}`",
                f"- PDF candidate pages: `{review.get('page_count')}` observed / `{review.get('expected_page_count')}` expected",
                f"- PDF candidate bridge path: `{review.get('pdf_bridge_path')}`",
            )
            if isinstance(review, Mapping)
            else tuple()
        ),
        *(
            (
                f"- PDF export provenance: `{provenance.get('status')}`",
                f"- Fully unattended export: `{provenance.get('fully_unattended')}`",
            )
            if isinstance(provenance, Mapping)
            else tuple()
        ),
        *(
            (f"- {bundle['manual_send_proof']['proof_capture_request']}",)
            if bundle["manual_send_proof"].get("proof_capture_request")
            else tuple()
        ),
        "",
        "No email, Coupa, browser, ledger, workbook body/cell read, generation, export, or production action occurred.",
    ]
    return "\n".join(lines) + "\n"


def write_exports(
    payload: Mapping[str, Any],
    export_root: Path = DEFAULT_EXPORT_ROOT,
    *,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
) -> tuple[Path, Path, Path | None]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator(payload), encoding="utf-8")
    bridge_path = None
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_path = bridge_export_root / JSON_EXPORT_NAME
        shutil.copy2(json_path, bridge_path)
    return json_path, operator_path, bridge_path


def export_bundle(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_payload(generated_at=generated_at)
    json_path, operator_path, bridge_path = write_exports(
        payload,
        export_root,
        bridge_export_root=bridge_export_root,
    )
    return {
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "bridge_path": bridge_path.as_posix() if bridge_path else None,
        "source_workbook_status": payload["live_arts_md_bundle"]["source_workbook"]["status"],
        "next_safe_move": payload["live_arts_md_bundle"]["next_safe_move"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Live Arts MD simple invoice review bundle.")
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--bridge-export-root", default=DEFAULT_BRIDGE_EXPORT_ROOT.as_posix())
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--generated-at")
    args = parser.parse_args(argv)
    result = export_bundle(
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
