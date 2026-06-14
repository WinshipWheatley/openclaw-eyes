"""Invoice Artifact Builder / Attachment Verifier v0.

This deterministic module builds or verifies bounded local invoice artifacts and
turns them into safe attachment refs. It is the local bridge from Capital Hilton
delivery facts to artifact hashes/fingerprints and future Email Delivery Package
Compiler inputs.

It may write only bounded local generated artifact files under
generated/invoice_artifacts. It does not send email, access Mail/Gmail, access
Coupa, open browsers, submit payments, handle credentials, perform external
actions, ingest raw bodies, mutate Mission Control Swift, run Mac sync/import,
or push.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_ARTIFACT_ROOT = Path("generated/invoice_artifacts/capital_hilton_invoice_artifact_v0")
DEFAULT_GENERATED_AT = "2026-05-25T00:00:00+00:00"
DEFAULT_RECORD_DATE = "2026-05-25"

SCHEMA_VERSION = "invoice_artifact_builder_v0"
READ_MODEL_ID = "invoice_artifact_readback"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "BOUNDED_LOCAL_INVOICE_ARTIFACT_BUILDER_NO_SEND"

INVOICE_TYPES = (
    "CAPITAL_HILTON_PERFORMANCE_INVOICE",
    "GENERAL_CLIENT_INVOICE",
    "UNKNOWN_NEEDS_FRAMING",
)

OUTPUT_FORMATS = (
    "PDF",
    "XLSX",
    "CSV_SUMMARY",
    "METADATA_ONLY",
)

ARTIFACT_TYPES = (
    "WINSHIP_BRANDED_INVOICE_PDF",
    "WINSHIP_BRANDED_INVOICE_XLSX",
    "INVOICE_METADATA_SUMMARY",
    "UNKNOWN",
)

READBACK_STATUSES = (
    "ARTIFACT_READY",
    "ARTIFACT_METADATA_READY",
    "NOT_READY_MISSING_FACTS",
    "NOT_READY_MISSING_TEMPLATE",
    "NOT_READY_OUTPUT_PATH_BLOCKED",
    "BLOCKED_PRIVACY_BOUNDARY",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "MISSING_DELIVERY_FACTS",
    "MISSING_RATE",
    "MISSING_TEMPLATE",
    "OUTPUT_PATH_UNSAFE",
    "RAW_FILE_BODY_IN_READMODEL",
    "HASH_MISSING",
    "EMAIL_SEND_ATTEMPTED",
    "COUPA_SUBMIT_ATTEMPTED",
    "BROWSER_ATTEMPTED",
    "EXTERNAL_ACTION_ATTEMPTED",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "bounded_local_artifact_generation_allowed": True,
    "bounded_local_file_hash_allowed": True,
    "local_generated_read_model_allowed": True,
    "live_email_send_allowed": False,
    "live_mail_send_allowed": False,
    "live_gmail_send_allowed": False,
    "live_coupa_access_allowed": False,
    "live_coupa_submit_allowed": False,
    "live_browser_allowed": False,
    "live_external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "live_payment_submission_allowed": False,
    "live_invoice_send_allowed": False,
    "live_approval_submission_allowed": False,
    "live_workflow_run_allowed": False,
    "live_agent_dispatch_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

BLOCKED_ACTIONS = (
    "email send",
    "Mail/Gmail send",
    "Coupa access or submit",
    "browser automation",
    "payment submission",
    "external action",
    "credential handling",
    "raw file body in read-model",
)

CAPITAL_HILTON_FACTS = {
    "performance_dates": ("2026-05-08", "2026-05-15", "2026-05-22", "2026-05-29"),
    "rate_per_show": {"amount": 400, "currency": "USD", "display": "$400/show"},
    "show_count": 4,
    "subtotal": {"amount": 1600, "currency": "USD", "calculation": "4 shows x $400/show"},
}


@dataclass(frozen=True)
class InvoiceArtifactBuildRequest:
    request_id: str
    workflow_ref: str
    client_ref: str
    tenant_ref: str
    invoice_type: str
    source_delivery_facts_ref: str
    source_rate_ref: str
    source_template_ref: str
    requested_output_formats: tuple[str, ...]
    requested_branding: str
    output_path_policy: str
    privacy_class: str
    authority_boundary: dict[str, bool]
    created_at: str


@dataclass(frozen=True)
class InvoiceArtifact:
    artifact_ref: str
    workflow_ref: str
    client_ref: str
    tenant_ref: str
    safe_display_label: str
    artifact_type: str
    output_format: str
    local_path_policy: str
    file_size_bytes: int
    hash_or_fingerprint: str
    source_facts: dict[str, Any]
    branding_summary: str
    generated_at_policy: str
    exists_status: str
    attachment_ready: bool
    privacy_class: str
    next_safe_move: str


@dataclass(frozen=True)
class InvoiceArtifactReadback:
    readback_id: str
    artifact_ref: str
    status: str
    operator_headline: str
    operator_message: str
    artifact_summary: str
    proof_summary: str
    missing_items: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    how_to_fix: str
    next_safe_move: str


@dataclass(frozen=True)
class InvoiceAttachmentRef:
    attachment_ref: str
    artifact_ref: str
    safe_display_label: str
    artifact_type: str
    hash_or_fingerprint: str
    approved_for_email_package: bool
    approved_for_coupa_package: bool
    raw_body_included: bool
    next_safe_move: str


@dataclass(frozen=True)
class InvoiceArtifactBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:16]}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _repo_relative(path: Path, *, repo_root: Path | str = Path.cwd()) -> str:
    try:
        return path.resolve().relative_to(Path(repo_root).resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _resolve_repo_path(path: Path | str, *, repo_root: Path | str = Path.cwd()) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else Path(repo_root) / candidate


def _validate_output_path(path: Path, *, repo_root: Path | str = Path.cwd()) -> None:
    resolved = path.resolve()
    root = Path(repo_root).resolve()
    allowed_root = (root / "generated" / "invoice_artifacts").resolve()
    if not (resolved == allowed_root or str(resolved).startswith(str(allowed_root) + "/")):
        raise ValueError(f"output path must stay under generated/invoice_artifacts: {path}")
    if resolved.as_posix().lower().startswith(((Path("/mnt") / "c").as_posix() + "/").lower()):
        raise ValueError("output path must not use C-drive")


def build_capital_hilton_request(*, generated_at: str = DEFAULT_GENERATED_AT) -> InvoiceArtifactBuildRequest:
    return InvoiceArtifactBuildRequest(
        request_id="invoice_artifact_build_request_capital_hilton_v0",
        workflow_ref="capital_hilton_invoice_workflow",
        client_ref="client_ref:capital_hilton",
        tenant_ref="tenant_ref:winship",
        invoice_type="CAPITAL_HILTON_PERFORMANCE_INVOICE",
        source_delivery_facts_ref="capital_hilton_delivery_facts_capture_writer:four_performance_dates_rate_subtotal",
        source_rate_ref="capital_hilton_rate_ref:400_per_show",
        source_template_ref="repo_a_deterministic_winship_invoice_template_v0",
        requested_output_formats=("PDF", "XLSX", "CSV_SUMMARY"),
        requested_branding="Winship-branded local invoice artifact",
        output_path_policy="bounded repo path under generated/invoice_artifacts/capital_hilton_invoice_artifact_v0",
        privacy_class="client_invoice_artifact_private_ref",
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        created_at=generated_at,
    )


def _invoice_rows() -> list[dict[str, Any]]:
    return [
        {
            "description": "Capital Hilton performances",
            "dates": ", ".join(CAPITAL_HILTON_FACTS["performance_dates"]),
            "quantity": str(CAPITAL_HILTON_FACTS["show_count"]),
            "rate": CAPITAL_HILTON_FACTS["rate_per_show"]["display"],
            "total": "$1,600",
        }
    ]


def _invoice_summary_lines() -> tuple[str, ...]:
    return (
        "WINSHIP",
        "Capital Hilton Invoice",
        f"Invoice record date: {DEFAULT_RECORD_DATE}",
        "Status: local artifact only - not sent, not submitted",
        "Bill to: Capital Hilton",
        "Service: Capital Hilton performances",
        "Dates: " + ", ".join(CAPITAL_HILTON_FACTS["performance_dates"]),
        "Rate: $400/show",
        "Subtotal: $1,600 USD",
        "Payment rail note: official payment rail remains Coupa/PO when confirmed.",
        "Boundary: no email send, no Coupa submit, no browser, no external action.",
    )


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _render_pdf_bytes(lines: tuple[str, ...]) -> bytes:
    text_ops: list[str] = ["BT", "/F1 11 Tf", "72 740 Td", "14 TL"]
    for line in lines:
        text_ops.append(f"({_pdf_escape(line)}) Tj")
        text_ops.append("T*")
    text_ops.append("ET")
    stream = "\n".join(text_ops).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{idx} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f\n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n\n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


def _xlsx_cell(ref: str, value: object) -> str:
    text = xml_escape(str(value))
    return f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>'


def _render_xlsx_bytes() -> bytes:
    rows = [
        ("A1", "WINSHIP"),
        ("A2", "Capital Hilton Invoice"),
        ("A3", f"Invoice record date: {DEFAULT_RECORD_DATE}"),
        ("A5", "Description", "B5", "Dates", "C5", "Qty", "D5", "Rate", "E5", "Total"),
        (
            "A6",
            "Capital Hilton performances",
            "B6",
            ", ".join(CAPITAL_HILTON_FACTS["performance_dates"]),
            "C6",
            "4",
            "D6",
            "$400/show",
            "E6",
            "$1,600",
        ),
        ("A8", "Payment rail note", "B8", "Official payment rail remains Coupa/PO when confirmed."),
        ("A9", "Boundary", "B9", "No email send, no Coupa submit, no browser, no external action."),
    ]
    row_xml: list[str] = []
    for idx, row in enumerate(rows, start=1):
        cells = []
        parts = list(row)
        for offset in range(0, len(parts), 2):
            cells.append(_xlsx_cell(str(parts[offset]), parts[offset + 1]))
        row_xml.append(f'<row r="{idx}">{"".join(cells)}</row>')
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>"
        + "".join(row_xml)
        + "</sheetData></worksheet>"
    )
    files = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>"
        ),
        "xl/workbook.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Invoice" sheetId="1" r:id="rId1"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            "</Relationships>"
        ),
        "xl/worksheets/sheet1.xml": sheet_xml,
    }
    buffer = io.BytesIO()
    fixed_time = (2026, 5, 25, 0, 0, 0)
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=fixed_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, files[name].encode("utf-8"))
    return buffer.getvalue()


def _render_csv_bytes() -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(("brand", "client", "record_date", "dates", "quantity", "rate", "subtotal", "boundary"))
    writer.writerow(
        (
            "WINSHIP",
            "Capital Hilton",
            DEFAULT_RECORD_DATE,
            "; ".join(CAPITAL_HILTON_FACTS["performance_dates"]),
            CAPITAL_HILTON_FACTS["show_count"],
            "$400/show",
            "$1,600",
            "local artifact only; no send or submit",
        )
    )
    return buffer.getvalue().encode("utf-8")


def _artifact_filename(output_format: str) -> str:
    suffix = {
        "PDF": "pdf",
        "XLSX": "xlsx",
        "CSV_SUMMARY": "csv",
        "METADATA_ONLY": "json",
    }[output_format]
    return f"WINSHIP_CAPITAL_HILTON_INVOICE_{DEFAULT_RECORD_DATE}.{suffix}"


def _artifact_type(output_format: str) -> str:
    return {
        "PDF": "WINSHIP_BRANDED_INVOICE_PDF",
        "XLSX": "WINSHIP_BRANDED_INVOICE_XLSX",
        "CSV_SUMMARY": "INVOICE_METADATA_SUMMARY",
        "METADATA_ONLY": "INVOICE_METADATA_SUMMARY",
    }[output_format]


def _artifact_bytes(output_format: str) -> bytes:
    if output_format == "PDF":
        return _render_pdf_bytes(_invoice_summary_lines())
    if output_format == "XLSX":
        return _render_xlsx_bytes()
    if output_format == "CSV_SUMMARY":
        return _render_csv_bytes()
    return stable_json({"facts": CAPITAL_HILTON_FACTS, "record_date": DEFAULT_RECORD_DATE}).encode("utf-8")


def build_artifacts(
    request: InvoiceArtifactBuildRequest,
    *,
    repo_root: Path | str = Path.cwd(),
    artifact_root: Path | str = DEFAULT_ARTIFACT_ROOT,
    write_files: bool = True,
) -> tuple[InvoiceArtifact, ...]:
    root = _resolve_repo_path(artifact_root, repo_root=repo_root)
    artifacts: list[InvoiceArtifact] = []
    if write_files:
        root.mkdir(parents=True, exist_ok=True)
    for output_format in request.requested_output_formats:
        if output_format not in OUTPUT_FORMATS:
            continue
        path = root / _artifact_filename(output_format)
        _validate_output_path(path, repo_root=repo_root)
        content = _artifact_bytes(output_format)
        if write_files:
            path.write_bytes(content)
            hash_value = _sha256_file(path)
            size = path.stat().st_size
            exists_status = "ARTIFACT_EXISTS"
        else:
            hash_value = "sha256:" + hashlib.sha256(content).hexdigest()
            size = len(content)
            exists_status = "ARTIFACT_MODELED_NOT_WRITTEN"
        rel_path = _repo_relative(path, repo_root=repo_root)
        attachment_ready = output_format in ("PDF", "XLSX") and bool(hash_value) and exists_status == "ARTIFACT_EXISTS"
        artifacts.append(
            InvoiceArtifact(
                artifact_ref=f"invoice_artifact_ref:capital_hilton_{output_format.lower()}_{DEFAULT_RECORD_DATE}",
                workflow_ref=request.workflow_ref,
                client_ref=request.client_ref,
                tenant_ref=request.tenant_ref,
                safe_display_label=f"Winship-branded Capital Hilton invoice {output_format}",
                artifact_type=_artifact_type(output_format),
                output_format=output_format,
                local_path_policy=f"bounded_generated_artifact_ref:{rel_path}",
                file_size_bytes=size,
                hash_or_fingerprint=hash_value,
                source_facts={
                    "performance_dates": CAPITAL_HILTON_FACTS["performance_dates"],
                    "rate_per_show": CAPITAL_HILTON_FACTS["rate_per_show"],
                    "subtotal": CAPITAL_HILTON_FACTS["subtotal"],
                },
                branding_summary="WINSHIP header with Capital Hilton invoice facts and no private remit/tax/credential material.",
                generated_at_policy=request.created_at,
                exists_status=exists_status,
                attachment_ready=attachment_ready,
                privacy_class=request.privacy_class,
                next_safe_move=(
                    "Use this artifact ref/hash as an Email Delivery Package attachment ref; do not send."
                    if attachment_ready
                    else "Use this summary for review only; not approved as an email attachment."
                ),
            )
        )
    return tuple(artifacts)


def build_attachment_refs(artifacts: tuple[InvoiceArtifact, ...]) -> tuple[InvoiceAttachmentRef, ...]:
    refs: list[InvoiceAttachmentRef] = []
    for artifact in artifacts:
        email_ready = artifact.attachment_ready and bool(artifact.hash_or_fingerprint)
        refs.append(
            InvoiceAttachmentRef(
                attachment_ref=f"email_attachment_ref:{artifact.artifact_ref.split(':', 1)[1]}",
                artifact_ref=artifact.artifact_ref,
                safe_display_label=artifact.safe_display_label,
                artifact_type=artifact.artifact_type,
                hash_or_fingerprint=artifact.hash_or_fingerprint,
                approved_for_email_package=email_ready,
                approved_for_coupa_package=False,
                raw_body_included=False,
                next_safe_move=(
                    "Pass this attachment ref to Email Delivery Package Compiler; future send still gated."
                    if email_ready
                    else "Resolve artifact/hash readiness before email packaging."
                ),
            )
        )
    return tuple(refs)


def build_readback(
    artifacts: tuple[InvoiceArtifact, ...],
    attachments: tuple[InvoiceAttachmentRef, ...],
) -> InvoiceArtifactReadback:
    ready_artifacts = tuple(artifact for artifact in artifacts if artifact.attachment_ready)
    missing: list[str] = []
    if not CAPITAL_HILTON_FACTS["performance_dates"]:
        missing.append("4 performance dates")
    if not CAPITAL_HILTON_FACTS["rate_per_show"]:
        missing.append("$400/show rate")
    if not CAPITAL_HILTON_FACTS["subtotal"]:
        missing.append("$1,600 subtotal basis")
    if not ready_artifacts:
        missing.append("attachment-ready PDF/XLSX artifact with hash/fingerprint")

    status = "ARTIFACT_READY" if not missing else "NOT_READY_MISSING_FACTS"
    primary = next((artifact for artifact in artifacts if artifact.output_format == "PDF"), artifacts[0] if artifacts else None)
    artifact_ref = primary.artifact_ref if primary else "missing"
    if status == "ARTIFACT_READY":
        headline = "Invoice artifact ready for attachment review"
        message = (
            "OpenClaw generated bounded local Winship-branded Capital Hilton invoice artifacts with hashes. "
            "Nothing was sent or submitted."
        )
        fix = "Use the attachment refs in the Email Delivery Package Compiler and keep Guardian/send gates locked."
    else:
        headline = "Invoice artifact is not ready"
        message = "OpenClaw could not prove an attachment-ready artifact."
        fix = "Capture missing facts or regenerate the bounded local artifact package."
    return InvoiceArtifactReadback(
        readback_id=_stable_id("invoice_artifact_readback", artifact_ref, tuple(a.hash_or_fingerprint for a in artifacts)),
        artifact_ref=artifact_ref,
        status=status,
        operator_headline=headline,
        operator_message=message,
        artifact_summary="; ".join(f"{artifact.output_format}: {artifact.exists_status}" for artifact in artifacts),
        proof_summary="; ".join(f"{attachment.safe_display_label} hash {attachment.hash_or_fingerprint}" for attachment in attachments),
        missing_items=tuple(missing),
        blocked_actions=BLOCKED_ACTIONS,
        how_to_fix=fix,
        next_safe_move=fix,
    )


def build_blockers() -> tuple[InvoiceArtifactBlocker, ...]:
    return (
        InvoiceArtifactBlocker("invoice_artifact_blocker_missing_facts", "MISSING_DELIVERY_FACTS", "Performance dates are missing.", "high", "Delivery facts are missing.", True, "Capture delivery facts before building."),
        InvoiceArtifactBlocker("invoice_artifact_blocker_missing_rate", "MISSING_RATE", "Rate or subtotal basis is missing.", "high", "Rate/subtotal is missing.", True, "Capture rate and subtotal before building."),
        InvoiceArtifactBlocker("invoice_artifact_blocker_missing_template", "MISSING_TEMPLATE", "No safe bounded template exists.", "high", "Template is missing.", True, "Use deterministic Repo A template or report metadata-only readiness."),
        InvoiceArtifactBlocker("invoice_artifact_blocker_output_path", "OUTPUT_PATH_UNSAFE", "Output path escapes generated/invoice_artifacts or targets unsafe mount.", "critical", "Output path is unsafe.", True, "Use bounded generated artifact path."),
        InvoiceArtifactBlocker("invoice_artifact_blocker_raw_body", "RAW_FILE_BODY_IN_READMODEL", "Raw file body would be copied into read-model.", "critical", "Raw file body is blocked from read-models.", True, "Expose only refs, metadata, and hashes."),
        InvoiceArtifactBlocker("invoice_artifact_blocker_hash_missing", "HASH_MISSING", "Attachment artifact lacks hash/fingerprint.", "critical", "Hash/fingerprint is required before attachment readiness.", True, "Hash the artifact."),
        InvoiceArtifactBlocker("invoice_artifact_blocker_email", "EMAIL_SEND_ATTEMPTED", "Builder attempts email send.", "critical", "Email send is blocked.", True, "Return artifact/readback only."),
        InvoiceArtifactBlocker("invoice_artifact_blocker_coupa", "COUPA_SUBMIT_ATTEMPTED", "Builder attempts Coupa submit.", "critical", "Coupa submit is blocked.", True, "Use future governed Coupa adapter only."),
        InvoiceArtifactBlocker("invoice_artifact_blocker_browser", "BROWSER_ATTEMPTED", "Builder attempts browser automation.", "critical", "Browser automation is blocked.", True, "Stay local."),
        InvoiceArtifactBlocker("invoice_artifact_blocker_external", "EXTERNAL_ACTION_ATTEMPTED", "Builder attempts external action.", "critical", "External action is blocked.", True, "Stay local."),
        InvoiceArtifactBlocker("invoice_artifact_blocker_unknown", "UNKNOWN_FAIL_CLOSED", "Unknown artifact build state.", "high", "Unknown artifact state fails closed.", True, "Ask for scoped facts/template/output path."),
    )


def build_payload(
    *,
    generated_at: str = DEFAULT_GENERATED_AT,
    repo_root: Path | str = Path.cwd(),
    artifact_root: Path | str = DEFAULT_ARTIFACT_ROOT,
    write_files: bool = True,
) -> dict[str, Any]:
    request = build_capital_hilton_request(generated_at=generated_at)
    artifacts = build_artifacts(request, repo_root=repo_root, artifact_root=artifact_root, write_files=write_files)
    attachments = build_attachment_refs(artifacts)
    readback = build_readback(artifacts, attachments)
    blockers = build_blockers()
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "invoice_types": INVOICE_TYPES,
        "output_formats": OUTPUT_FORMATS,
        "artifact_types": ARTIFACT_TYPES,
        "readback_statuses": READBACK_STATUSES,
        "blocker_types": BLOCKER_TYPES,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "build_request": asdict(request),
        "artifacts": [asdict(artifact) for artifact in artifacts],
        "attachment_refs": [asdict(ref) for ref in attachments],
        "readback": asdict(readback),
        "invoice_artifact_blockers": [asdict(blocker) for blocker in blockers],
        "capital_hilton_example": {
            "known_facts": (
                "4 performance dates",
                "$400/show",
                "$1,600 subtotal basis",
                "Winship-branded invoice desired",
                "invoice saved with 2026-05-25 record date for future range tracking",
            ),
            "delivery_facts": CAPITAL_HILTON_FACTS,
            "email_delivery_package_ref": "email_delivery_package_compiler:capital_hilton_complete_except_approval",
            "guardian_approval_ref": "guardian_approval_request_wrapper:capital_hilton_email_approval",
            "future_completion_label": "INVOICE SENT",
            "future_completion_only": True,
        },
        "machine_proof": {
            "all_live_authority_false_except_bounded_local_artifact_generation": all(
                value is False
                for key, value in AUTHORITY_BOUNDARY.items()
                if key
                not in {
                    "bounded_local_artifact_generation_allowed",
                    "bounded_local_file_hash_allowed",
                    "local_generated_read_model_allowed",
                }
            ),
            "bounded_local_artifact_generation_performed": write_files,
            "bounded_local_file_hash_performed": True,
            "email_send_performed": False,
            "mail_or_gmail_send_performed": False,
            "coupa_access_or_submit_performed": False,
            "browser_access_performed": False,
            "external_action_performed": False,
            "credential_handling_performed": False,
            "raw_file_body_in_read_model": False,
            "raw_body_ingestion_performed": False,
            "mac_sync_import_performed": False,
            "swift_change_performed": False,
            "git_push_performed": False,
        },
        "operator_summary": (
            "OpenClaw generated bounded local Winship-branded Capital Hilton invoice artifacts "
            "and attachment refs with hashes. Nothing was sent, submitted, or exposed as raw file body."
        ),
        "next_safe_move": "Pass attachment refs to Email Delivery Package Compiler; keep Guardian/send gates locked.",
    }


def format_operator_markdown(payload: dict[str, Any]) -> str:
    readback = payload["readback"]
    lines = [
        "# Invoice Artifact Builder / Attachment Verifier",
        "",
        "## Summary",
        payload["operator_summary"],
        "",
        "## Readback",
        f"- Status: {readback['status']}",
        f"- Message: {readback['operator_message']}",
        f"- Artifact summary: {readback['artifact_summary']}",
        f"- Proof summary: {readback['proof_summary']}",
        f"- Next: {readback['next_safe_move']}",
        "",
        "## Attachments",
    ]
    for ref in payload["attachment_refs"]:
        lines.append(f"- {ref['safe_display_label']}: {ref['hash_or_fingerprint']} email_package={str(ref['approved_for_email_package']).lower()}")
    lines += ["", "## Blocked"]
    for blocker in payload["invoice_artifact_blockers"]:
        lines.append(f"- {blocker['blocker_type']}: {blocker['elioperator_warning']}")
    lines += [
        "",
        "## Boundary",
        "No email send, no Mail/Gmail send, no Coupa access/submit, no browser, no external action, no credential handling, no raw file body in read-models, no raw-body ingestion.",
    ]
    return "\n".join(lines) + "\n"


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def _summary(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> dict[str, Any]:
    return {
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "readback_status": payload["readback"]["status"],
        "artifact_count": len(payload["artifacts"]),
        "attachment_count": len(payload["attachment_refs"]),
        "email_ready_attachment_count": sum(1 for ref in payload["attachment_refs"] if ref["approved_for_email_package"]),
        "all_live_authority_false_except_bounded_local_artifact_generation": payload["machine_proof"]["all_live_authority_false_except_bounded_local_artifact_generation"],
        "json_export": str(export_root / JSON_EXPORT_NAME),
        "operator_export": str(export_root / OPERATOR_EXPORT_NAME),
    }


def build_and_export(
    *,
    fixture: str = "capital_hilton",
    generated_at: str = DEFAULT_GENERATED_AT,
    repo_root: Path = Path.cwd(),
    export_root: Path = DEFAULT_EXPORT_ROOT,
    artifact_root: Path = DEFAULT_ARTIFACT_ROOT,
    format_name: str = "summary",
) -> dict[str, Any]:
    if fixture != "capital_hilton":
        raise ValueError("Only capital_hilton fixture is supported in v0")
    payload = build_payload(generated_at=generated_at, repo_root=repo_root, artifact_root=artifact_root, write_files=True)
    write_exports(payload, export_root)
    return payload if format_name == "json" else _summary(payload, export_root)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build/export invoice artifact readback.")
    parser.add_argument("--fixture", choices=("capital_hilton",), default="capital_hilton")
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--repo-root", default=str(Path.cwd()))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--artifact-root", default=str(DEFAULT_ARTIFACT_ROOT))
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = build_and_export(
        fixture=args.fixture,
        generated_at=args.generated_at,
        repo_root=Path(args.repo_root),
        export_root=Path(args.export_root),
        artifact_root=Path(args.artifact_root),
        format_name=args.format,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
