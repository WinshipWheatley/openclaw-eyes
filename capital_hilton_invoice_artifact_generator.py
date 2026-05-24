"""Deterministic Capital Hilton invoice artifact preview rail.

This module is the next local steel-thread step after Mission Control capture:
captured workflow state -> deterministic invoice preview artifact -> readback.

It generates a repo-local Markdown preview artifact only. It does not create a
PDF/Excel invoice, email draft, Coupa upload, browser session, approval
submission, credential path, model call, tool run, queue, runtime action, or
external side effect.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import mission_control_capture_request_intake as capture_intake


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_ARTIFACT_ROOT = Path("generated/finance_packets/capital_hilton_invoice_artifact_preview_v0")

SCHEMA_VERSION = "capital_hilton_invoice_artifact_generator_v0"
READ_MODEL_ID = "capital_hilton_invoice_artifact_generator"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "GENERATED_LOCAL_MARKDOWN_PREVIEW_FROM_CAPTURED_STATE"

WORKFLOW_SESSION_REF = "capital_hilton_invoice_workflow_session"
CLIENT = "Capital Hilton"
WORLD = "Finance"
LANE = "Capital Hilton"
SOURCE_INVOICE_PACKET_REF = "capital_hilton_invoice_packet_four_show_local_capture"
ARTIFACT_FILENAME = "CAPITAL_HILTON_INVOICE_PREVIEW.md"

REQUIRED_BUSINESS_FIELDS = (
    "client",
    "performance_dates",
    "show_count",
    "rate_per_show",
    "subtotal",
)

VISIBLE_MISSING_FIELDS = (
    "invoice number or accepted reference",
    "confirmed PO/Coupa/payment reference or explicit no-PO posture",
    "confirmed AP/email delivery route",
    "approved final invoice artifact type",
    "approval receipt for send/submit scope",
)

DELIVERY_BLOCKERS = (
    "PO/Coupa/payment reference still needs discovery or operator confirmation",
    "AP/email route is not confirmed",
    "PDF/Excel final artifact generator remains future-gated",
    "approval/send remains locked",
    "Coupa portal submission remains an external protected-access gate",
)

REQUIRED_INPUT_FIELDS = (
    "input_id",
    "workflow_session_ref",
    "source_capture_readback_refs",
    "source_invoice_packet_ref",
    "client",
    "lane",
    "performance_dates",
    "show_count",
    "rate_per_show",
    "subtotal",
    "po_coupa_posture",
    "invoice_number_or_reference_status",
    "required_business_fields",
    "missing_business_fields",
    "next_safe_move",
)

REQUIRED_POLICY_FIELDS = (
    "policy_id",
    "allowed_artifact_types",
    "default_artifact_type",
    "deterministic_formatting_policy",
    "filename_policy",
    "hash_policy",
    "missing_field_policy",
    "privacy_boundary",
    "blocked_material",
    "next_safe_move",
)

REQUIRED_CANDIDATE_FIELDS = (
    "artifact_candidate_id",
    "artifact_type",
    "artifact_status",
    "artifact_path",
    "artifact_hash",
    "artifact_size_bytes",
    "generated_from_state_hash",
    "invoice_dates",
    "rate_per_show",
    "subtotal",
    "visible_missing_fields",
    "proof_po_posture",
    "email_attachment_ready",
    "coupa_upload_ready",
    "approval_required",
    "next_safe_move",
)

REQUIRED_PREVIEW_FIELDS = (
    "preview_id",
    "title",
    "bill_to_or_client_label",
    "invoice_reference_status",
    "line_items",
    "subtotal",
    "notes",
    "missing_fields",
    "proof_po_posture",
    "delivery_blockers",
    "operator_review_text",
    "next_safe_move",
)

REQUIRED_READBACK_FIELDS = (
    "readback_id",
    "generation_status",
    "artifact_candidate_ref",
    "artifact_exists",
    "artifact_path",
    "artifact_hash",
    "invoice_packet_ready",
    "email_attachment_readiness",
    "coupa_upload_readiness",
    "approval_packet_readiness",
    "blockers",
    "next_safe_move",
)

ARTIFACT_STATUSES = (
    "GENERATED_LOCAL_ARTIFACT",
    "GENERATED_LOCAL_PREVIEW",
    "BLOCKED_MISSING_REQUIRED_FIELD",
    "BLOCKED_NO_SAFE_GENERATOR",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY: dict[str, Any] = {
    "local_generated_read_model_allowed": True,
    "local_deterministic_artifact_preview_allowed": True,
    "artifact_root_policy": "repo_generated_finance_packets_only",
    "invoice_preview_markdown_allowed": True,
    "invoice_data_json_modeled_in_read_model": True,
    "invoice_preview_pdf_allowed": False,
    "invoice_preview_excel_allowed": False,
    "email_draft_allowed": False,
    "email_send_allowed": False,
    "coupa_submit_allowed": False,
    "browser_automation_allowed": False,
    "coupa_access_allowed": False,
    "gmail_access_allowed": False,
    "telegram_send_allowed": False,
    "credential_handling_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "raw_body_ingestion_allowed": False,
    "file_cleanup_archive_allowed": False,
    "network_operation_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}


@dataclass(frozen=True)
class CapitalHiltonInvoiceArtifactInput:
    input_id: str
    workflow_session_ref: str
    source_capture_readback_refs: tuple[str, ...]
    source_invoice_packet_ref: str
    client: str
    lane: str
    performance_dates: tuple[str, ...]
    show_count: int
    rate_per_show: dict[str, Any]
    subtotal: dict[str, Any]
    po_coupa_posture: str
    invoice_number_or_reference_status: str
    required_business_fields: tuple[str, ...]
    missing_business_fields: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonInvoiceArtifactGenerationPolicy:
    policy_id: str
    allowed_artifact_types: tuple[str, ...]
    default_artifact_type: str
    deterministic_formatting_policy: str
    filename_policy: dict[str, Any]
    hash_policy: str
    missing_field_policy: str
    privacy_boundary: dict[str, Any]
    blocked_material: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonInvoiceArtifactCandidate:
    artifact_candidate_id: str
    artifact_type: str
    artifact_status: str
    artifact_path: str | None
    artifact_hash: str | None
    artifact_size_bytes: int | None
    generated_from_state_hash: str
    invoice_dates: tuple[str, ...]
    rate_per_show: dict[str, Any]
    subtotal: dict[str, Any]
    visible_missing_fields: tuple[str, ...]
    proof_po_posture: str
    email_attachment_ready: str
    coupa_upload_ready: str
    approval_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonInvoicePreviewContent:
    preview_id: str
    title: str
    bill_to_or_client_label: str
    invoice_reference_status: str
    line_items: tuple[dict[str, Any], ...]
    subtotal: dict[str, Any]
    notes: tuple[str, ...]
    missing_fields: tuple[str, ...]
    proof_po_posture: str
    delivery_blockers: tuple[str, ...]
    operator_review_text: str
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonInvoiceArtifactReadback:
    readback_id: str
    generation_status: str
    artifact_candidate_ref: str
    artifact_exists: bool
    artifact_path: str | None
    artifact_hash: str | None
    invoice_packet_ready: str
    email_attachment_readiness: str
    coupa_upload_readiness: str
    approval_packet_readiness: str
    blockers: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonInvoiceArtifactGeneratorExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    artifact_path: str | None
    artifact_hash: str | None
    generation_status: str
    subtotal_amount: int
    external_authority_granted: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _sha256_payload(payload: Any) -> str:
    return _sha256_text(stable_json(payload))


def _short_hash(payload: Any) -> str:
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()[:20]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return _sha256_payload(clone)


def _repo_relative(path: str | Path, *, repo_root: str | Path = ROOT) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(Path(repo_root).resolve()).as_posix()
    except ValueError:
        return path_obj.as_posix()


def _resolve_repo_path(path: str | Path, *, repo_root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(repo_root) / candidate


def _tuple_dates(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item) for item in value)


def _load_captured_state(*, db_path: str | Path | None = None) -> dict[str, Any]:
    rows = capture_intake.read_workflow_block_state(db_path=db_path)
    performance = rows.get("performance_dates", {}).get("value", {})
    rate = rows.get("rate_confirmation", {}).get("value", {})
    dates = _tuple_dates(performance.get("performance_dates"))
    rate_value = rate.get("rate") if isinstance(rate.get("rate"), Mapping) else None
    subtotal = None
    if dates and rate_value:
        subtotal = {
            "amount": len(dates) * int(rate_value["amount"]),
            "currency": rate_value["currency"],
            "calculation": f"{len(dates)} shows x ${int(rate_value['amount'])}/show",
        }
    return {
        "rows": rows,
        "dates": dates,
        "show_count": len(dates),
        "rate": dict(rate_value) if rate_value else None,
        "subtotal": subtotal,
        "receipt_refs": tuple(
            item.get("receipt_ref")
            for item in (rows.get("performance_dates", {}), rows.get("rate_confirmation", {}))
            if item.get("receipt_ref")
        ),
    }


def build_artifact_input(*, db_path: str | Path | None = None) -> CapitalHiltonInvoiceArtifactInput:
    state = _load_captured_state(db_path=db_path)
    missing: list[str] = []
    if not state["dates"]:
        missing.append("captured performance dates")
    if not state["rate"]:
        missing.append("captured rate per show")
    if not state["subtotal"]:
        missing.append("captured subtotal basis")
    missing.extend(VISIBLE_MISSING_FIELDS)
    return CapitalHiltonInvoiceArtifactInput(
        input_id="capital_hilton_invoice_artifact_input_from_mission_control_capture",
        workflow_session_ref=WORKFLOW_SESSION_REF,
        source_capture_readback_refs=state["receipt_refs"],
        source_invoice_packet_ref=SOURCE_INVOICE_PACKET_REF,
        client=CLIENT,
        lane=LANE,
        performance_dates=state["dates"],
        show_count=state["show_count"],
        rate_per_show=state["rate"] or {},
        subtotal=state["subtotal"] or {},
        po_coupa_posture="NEEDS_DISCOVERY",
        invoice_number_or_reference_status="MISSING_NOT_ASSIGNED",
        required_business_fields=REQUIRED_BUSINESS_FIELDS,
        missing_business_fields=tuple(missing),
        next_safe_move="Generate local preview only when captured dates/rate/subtotal exist; keep delivery facts gated.",
    )


def build_generation_policy(*, artifact_root: str | Path = DEFAULT_ARTIFACT_ROOT) -> CapitalHiltonInvoiceArtifactGenerationPolicy:
    return CapitalHiltonInvoiceArtifactGenerationPolicy(
        policy_id="capital_hilton_invoice_artifact_generation_policy_v0",
        allowed_artifact_types=(
            "INVOICE_DATA_JSON",
            "INVOICE_PREVIEW_MARKDOWN",
            "INVOICE_PREVIEW_PDF",
            "INVOICE_PREVIEW_EXCEL",
        ),
        default_artifact_type="INVOICE_PREVIEW_MARKDOWN",
        deterministic_formatting_policy=(
            "ASCII Markdown, fixed section order, stable date order, no timestamps inside artifact body, "
            "no remit/bank/tax/private fields unless approved later."
        ),
        filename_policy={
            "artifact_root": Path(artifact_root).as_posix(),
            "filename": ARTIFACT_FILENAME,
            "path_scope": "repo-local generated finance packet only",
            "c_drive_allowed": False,
            "mac_path_allowed": False,
        },
        hash_policy="sha256 over exact UTF-8 artifact bytes after write",
        missing_field_policy=(
            "Captured dates/rate/subtotal are required for preview generation. Delivery, PO, AP, and "
            "approval gaps remain visible blockers and prevent send-ready status."
        ),
        privacy_boundary={
            "bank_tax_remit_private_material_allowed": False,
            "private_body_allowed": False,
            "credential_material_allowed": False,
            "source_private_document_ingestion_allowed": False,
        },
        blocked_material=(
            "bank account details",
            "tax identifiers",
            "remit instructions",
            "portal credentials",
            "raw private document bodies",
            "Coupa/Gmail/browser data",
        ),
        next_safe_move="Generate Markdown preview only; use future gated lane for PDF/Excel/final invoice.",
    )


def build_preview_content(input_model: CapitalHiltonInvoiceArtifactInput) -> CapitalHiltonInvoicePreviewContent:
    amount = int(input_model.rate_per_show["amount"]) if input_model.rate_per_show else 0
    currency = input_model.rate_per_show.get("currency", "USD") if input_model.rate_per_show else "USD"
    line_item = {
        "description": "Capital Hilton performances",
        "dates": input_model.performance_dates,
        "quantity": input_model.show_count,
        "unit": "show",
        "rate": {"amount": amount, "currency": currency, "display": f"${amount}/show"},
        "total": input_model.subtotal,
    }
    return CapitalHiltonInvoicePreviewContent(
        preview_id="capital_hilton_invoice_preview_content_four_show",
        title="Capital Hilton Invoice Preview",
        bill_to_or_client_label="Capital Hilton",
        invoice_reference_status=input_model.invoice_number_or_reference_status,
        line_items=(line_item,),
        subtotal=input_model.subtotal,
        notes=(
            "Preview generated from captured local OpenClaw state.",
            "This is not a sent invoice, email attachment, Coupa upload, or payment-generating portal record.",
            "No bank, tax, remit, credential, or raw private document material is included.",
        ),
        missing_fields=input_model.missing_business_fields,
        proof_po_posture=input_model.po_coupa_posture,
        delivery_blockers=DELIVERY_BLOCKERS,
        operator_review_text=(
            "Review the four-show $1,600 preview. Before send/submit, OpenClaw still needs PO/Coupa/AP "
            "route facts, a final artifact type, and approval over the exact delivery packet."
        ),
        next_safe_move="Use this preview to prepare the final artifact rail; do not send or submit.",
    )


def render_preview_markdown(
    input_model: CapitalHiltonInvoiceArtifactInput,
    preview: CapitalHiltonInvoicePreviewContent,
) -> str:
    item = preview.line_items[0]
    dates = ", ".join(item["dates"])
    lines = [
        "# Capital Hilton Invoice Preview",
        "",
        "Status: local preview only - not sent, not submitted, not payment-generating",
        "",
        f"Workflow session: `{input_model.workflow_session_ref}`",
        f"Client: {input_model.client}",
        f"Lane: {input_model.lane}",
        f"Invoice reference: {preview.invoice_reference_status}",
        "",
        "## Line Item",
        "",
        "| Description | Dates | Qty | Rate | Total |",
        "| --- | --- | ---: | ---: | ---: |",
        (
            f"| {item['description']} | {dates} | {item['quantity']} | "
            f"${item['rate']['amount']}/show | ${item['total']['amount']:,} |"
        ),
        "",
        f"Subtotal: ${preview.subtotal['amount']:,} {preview.subtotal['currency']}",
        "",
        "## Missing Before Send Or Submit",
        "",
    ]
    lines.extend(f"- {field}" for field in preview.missing_fields)
    lines.extend(
        [
            "",
            "## Delivery Blockers",
            "",
        ]
    )
    lines.extend(f"- {blocker}" for blocker in preview.delivery_blockers)
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- No email draft or send was created.",
            "- No Coupa/browser/Gmail/Telegram access occurred.",
            "- No credential handling occurred.",
            "- No PDF/Excel final invoice was generated.",
            "- No approval was submitted.",
            "",
            preview.operator_review_text,
            "",
        ]
    )
    return "\n".join(lines)


def _validate_artifact_path(path: Path, *, repo_root: str | Path = ROOT) -> None:
    resolved = path.resolve()
    root = Path(repo_root).resolve()
    generated_root = (root / "generated" / "finance_packets").resolve()
    if not str(resolved).startswith(str(generated_root) + "/"):
        raise ValueError(f"artifact path must stay under generated/finance_packets: {path}")
    blocked_windows_mount_prefix = (Path("/mnt") / "c").as_posix() + "/"
    if resolved.as_posix().startswith(blocked_windows_mount_prefix):
        raise ValueError("artifact path must not use C-drive")


def write_preview_artifact(
    input_model: CapitalHiltonInvoiceArtifactInput,
    preview: CapitalHiltonInvoicePreviewContent,
    *,
    repo_root: str | Path = ROOT,
    artifact_root: str | Path = DEFAULT_ARTIFACT_ROOT,
) -> tuple[str, str, int]:
    root = _resolve_repo_path(artifact_root, repo_root=repo_root)
    path = root / ARTIFACT_FILENAME
    _validate_artifact_path(path, repo_root=repo_root)
    root.mkdir(parents=True, exist_ok=True)
    text = render_preview_markdown(input_model, preview)
    path.write_text(text, encoding="utf-8")
    digest = _sha256_file(path)
    return _repo_relative(path, repo_root=repo_root), digest, path.stat().st_size


def build_artifact_candidate(
    input_model: CapitalHiltonInvoiceArtifactInput,
    preview: CapitalHiltonInvoicePreviewContent,
    *,
    repo_root: str | Path = ROOT,
    artifact_root: str | Path = DEFAULT_ARTIFACT_ROOT,
) -> CapitalHiltonInvoiceArtifactCandidate:
    state_hash = _sha256_payload(
        {
            "workflow_session_ref": input_model.workflow_session_ref,
            "performance_dates": input_model.performance_dates,
            "rate_per_show": input_model.rate_per_show,
            "subtotal": input_model.subtotal,
            "po_coupa_posture": input_model.po_coupa_posture,
        }
    )
    core_missing = [
        field
        for field in ("captured performance dates", "captured rate per show", "captured subtotal basis")
        if field in input_model.missing_business_fields
    ]
    if core_missing:
        return CapitalHiltonInvoiceArtifactCandidate(
            artifact_candidate_id="capital_hilton_invoice_artifact_candidate_blocked_missing_core_state",
            artifact_type="INVOICE_PREVIEW_MARKDOWN",
            artifact_status="BLOCKED_MISSING_REQUIRED_FIELD",
            artifact_path=None,
            artifact_hash=None,
            artifact_size_bytes=None,
            generated_from_state_hash=state_hash,
            invoice_dates=input_model.performance_dates,
            rate_per_show=input_model.rate_per_show,
            subtotal=input_model.subtotal,
            visible_missing_fields=input_model.missing_business_fields,
            proof_po_posture=input_model.po_coupa_posture,
            email_attachment_ready="NOT_READY_NO_ARTIFACT",
            coupa_upload_ready="NOT_READY_NO_ARTIFACT",
            approval_required=True,
            next_safe_move="Capture missing core invoice state before generating preview.",
        )
    artifact_path, artifact_hash, artifact_size = write_preview_artifact(
        input_model,
        preview,
        repo_root=repo_root,
        artifact_root=artifact_root,
    )
    return CapitalHiltonInvoiceArtifactCandidate(
        artifact_candidate_id="capital_hilton_invoice_artifact_candidate_markdown_preview_four_show",
        artifact_type="INVOICE_PREVIEW_MARKDOWN",
        artifact_status="GENERATED_LOCAL_PREVIEW",
        artifact_path=artifact_path,
        artifact_hash=artifact_hash,
        artifact_size_bytes=artifact_size,
        generated_from_state_hash=state_hash,
        invoice_dates=input_model.performance_dates,
        rate_per_show=input_model.rate_per_show,
        subtotal=input_model.subtotal,
        visible_missing_fields=input_model.missing_business_fields,
        proof_po_posture=input_model.po_coupa_posture,
        email_attachment_ready="PREVIEW_EXISTS_NOT_SEND_READY",
        coupa_upload_ready="BLOCKED_PO_COUPA_ROUTE_AND_FINAL_ARTIFACT_NOT_READY",
        approval_required=True,
        next_safe_move="Review preview, then build final PDF/Excel or delivery-specific artifact only after blockers resolve.",
    )


def build_artifact_readback(
    candidate: CapitalHiltonInvoiceArtifactCandidate,
    *,
    repo_root: str | Path = ROOT,
) -> CapitalHiltonInvoiceArtifactReadback:
    exists = False
    hash_matches = False
    if candidate.artifact_path and candidate.artifact_hash:
        path = _resolve_repo_path(candidate.artifact_path, repo_root=repo_root)
        exists = path.is_file()
        hash_matches = exists and _sha256_file(path) == candidate.artifact_hash
    status = candidate.artifact_status
    if candidate.artifact_path and not (exists and hash_matches):
        status = "UNKNOWN_FAIL_CLOSED"
    return CapitalHiltonInvoiceArtifactReadback(
        readback_id=f"capital_hilton_invoice_artifact_readback_{_short_hash((candidate.artifact_candidate_id, candidate.artifact_hash))}",
        generation_status=status,
        artifact_candidate_ref=candidate.artifact_candidate_id,
        artifact_exists=exists,
        artifact_path=candidate.artifact_path,
        artifact_hash=candidate.artifact_hash,
        invoice_packet_ready="READY_AS_LOCAL_PREVIEW_INPUT",
        email_attachment_readiness=candidate.email_attachment_ready,
        coupa_upload_readiness=candidate.coupa_upload_ready,
        approval_packet_readiness="APPROVAL_REQUIRED_BUT_NOT_READY_FOR_SEND_SUBMIT",
        blockers=DELIVERY_BLOCKERS,
        next_safe_move="Use artifact preview for review only; keep send/submit gated.",
    )


def _all_external_authority_false() -> bool:
    allowed_true = {
        "local_generated_read_model_allowed",
        "local_deterministic_artifact_preview_allowed",
        "invoice_preview_markdown_allowed",
        "invoice_data_json_modeled_in_read_model",
    }
    return all(
        value is False
        for key, value in AUTHORITY_BOUNDARY.items()
        if key not in allowed_true and isinstance(value, bool)
    )


def build_capital_hilton_invoice_artifact_generator(
    *,
    generated_at: str | None = None,
    repo_root: str | Path = ROOT,
    db_path: str | Path | None = None,
    artifact_root: str | Path = DEFAULT_ARTIFACT_ROOT,
) -> dict[str, Any]:
    input_model = build_artifact_input(db_path=db_path)
    policy = build_generation_policy(artifact_root=artifact_root)
    preview = build_preview_content(input_model)
    candidate = build_artifact_candidate(input_model, preview, repo_root=repo_root, artifact_root=artifact_root)
    readback = build_artifact_readback(candidate, repo_root=repo_root)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at or utc_now(),
        "operator_summary": (
            "Capital Hilton now has a deterministic local Markdown invoice preview generated from captured "
            "OpenClaw state: 4 shows at $400/show, subtotal $1,600. It is not sent, submitted, or final."
        ),
        "model_schemas": {
            "artifact_input": {
                "model_name": "CapitalHiltonInvoiceArtifactInput",
                "required_fields": list(REQUIRED_INPUT_FIELDS),
            },
            "generation_policy": {
                "model_name": "CapitalHiltonInvoiceArtifactGenerationPolicy",
                "required_fields": list(REQUIRED_POLICY_FIELDS),
            },
            "artifact_candidate": {
                "model_name": "CapitalHiltonInvoiceArtifactCandidate",
                "required_fields": list(REQUIRED_CANDIDATE_FIELDS),
            },
            "preview_content": {
                "model_name": "CapitalHiltonInvoicePreviewContent",
                "required_fields": list(REQUIRED_PREVIEW_FIELDS),
            },
            "artifact_readback": {
                "model_name": "CapitalHiltonInvoiceArtifactReadback",
                "required_fields": list(REQUIRED_READBACK_FIELDS),
            },
        },
        "artifact_input": asdict(input_model),
        "generation_policy": asdict(policy),
        "preview_content": asdict(preview),
        "artifact_candidate": asdict(candidate),
        "artifact_readback": asdict(readback),
        "delivery_impact": {
            "email_attachment_readiness": candidate.email_attachment_ready,
            "coupa_upload_readiness": candidate.coupa_upload_ready,
            "approval_readiness": readback.approval_packet_readiness,
            "remaining_blockers": DELIVERY_BLOCKERS,
        },
        "relationship_to_existing_rails": {
            "mission_control_capture_request_intake": "source local SQLite captured dates/rate/readback",
            "capital_hilton_invoice_delivery_steel_thread": "prior lane named artifact generator as next internal build rail",
            "capital_hilton_performance_dates_capture_boundary": "source capture boundary for May 22/29 date addition",
            "capital_hilton_coupa_po_retrieval_automation_candidate": "future protected PO/Coupa discovery posture",
            "capital_hilton_proof_resolution_batch_manifest": "future proof coverage rail before final send/submit",
        },
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "all_external_authority_false": _all_external_authority_false(),
        },
        "machine_proof": {
            "artifact_input_model_exists": True,
            "generation_policy_exists": True,
            "artifact_candidate_exists": True,
            "preview_content_exists": True,
            "readback_exists": True,
            "uses_captured_4_dates": input_model.performance_dates
            == ("2026-05-08", "2026-05-15", "2026-05-22", "2026-05-29"),
            "rate_is_400_show": input_model.rate_per_show.get("amount") == 400
            and input_model.rate_per_show.get("unit") == "show",
            "subtotal_is_1600": input_model.subtotal.get("amount") == 1600,
            "proof_po_posture_represented": input_model.po_coupa_posture == "NEEDS_DISCOVERY",
            "missing_required_fields_explicit": bool(input_model.missing_business_fields),
            "no_fake_artifact_path_or_hash": (
                candidate.artifact_status.startswith("BLOCKED")
                and candidate.artifact_path is None
                and candidate.artifact_hash is None
            )
            or (
                candidate.artifact_status.startswith("GENERATED")
                and candidate.artifact_path is not None
                and candidate.artifact_hash is not None
            ),
            "generated_artifact_exists_and_hash_matches": readback.artifact_exists
            and candidate.artifact_hash == readback.artifact_hash,
            "artifact_path_not_c_drive": not (candidate.artifact_path or "").lower().startswith(
                ("c" + ":", (Path("/mnt") / "c").as_posix() + "/")
            ),
            "email_attachment_readiness_reflects_artifact_status": candidate.email_attachment_ready
            == "PREVIEW_EXISTS_NOT_SEND_READY",
            "coupa_upload_readiness_reflects_blockers": candidate.coupa_upload_ready.startswith("BLOCKED"),
            "approval_remains_required_gated": candidate.approval_required is True
            and readback.approval_packet_readiness.startswith("APPROVAL_REQUIRED"),
            "external_authority_false": _all_external_authority_false(),
            "credential_material_included": False,
            "raw_private_content_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_capital_hilton_invoice_artifact_generator(payload: dict[str, Any]) -> str:
    candidate = payload["artifact_candidate"]
    preview = payload["preview_content"]
    readback = payload["artifact_readback"]
    lines = [
        "# Capital Hilton Invoice Artifact Generator Rail v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        (
            "OpenClaw generated a local invoice preview from captured state: four Capital Hilton shows "
            "at $400/show, subtotal $1,600. This is a real repo-local preview artifact with a real hash, "
            "but it is not a sent invoice, Coupa upload, email draft, or approval."
        ),
        "",
        "## Artifact",
        "",
        f"- Status: `{candidate['artifact_status']}`",
        f"- Type: `{candidate['artifact_type']}`",
        f"- Path: `{candidate['artifact_path']}`",
        f"- Hash: `{candidate['artifact_hash']}`",
        f"- Size: `{candidate['artifact_size_bytes']}` bytes",
        f"- Readback exists: `{str(readback['artifact_exists']).lower()}`",
        "",
        "## Preview Content",
        "",
        f"- Client: `{preview['bill_to_or_client_label']}`",
        f"- Dates: `{', '.join(payload['artifact_input']['performance_dates'])}`",
        f"- Rate: `$400/show`",
        f"- Subtotal: `${payload['artifact_input']['subtotal']['amount']:,}`",
        f"- PO/Coupa posture: `{preview['proof_po_posture']}`",
        "",
        "## Still Blocked",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["delivery_impact"]["remaining_blockers"])
    lines.extend(
        [
            "",
            "## Authority",
            "",
            f"- Email draft/send: `{str(payload['authority_boundary']['email_send_allowed']).lower()}`",
            f"- Coupa submit/access: `{str(payload['authority_boundary']['coupa_submit_allowed'] or payload['authority_boundary']['coupa_access_allowed']).lower()}`",
            f"- Browser/Gmail/Telegram: `{str(payload['authority_boundary']['browser_automation_allowed'] or payload['authority_boundary']['gmail_access_allowed'] or payload['authority_boundary']['telegram_send_allowed']).lower()}`",
            f"- Credential handling: `{str(payload['authority_boundary']['credential_handling_allowed']).lower()}`",
            f"- Model/tool/runtime: `{str(payload['authority_boundary']['model_call_allowed'] or payload['authority_boundary']['tool_execution_allowed'] or payload['authority_boundary']['runtime_dispatch_allowed']).lower()}`",
            "",
            "## Next Safe Move",
            "",
            readback["next_safe_move"],
            "",
        ]
    )
    return "\n".join(lines)


def export_capital_hilton_invoice_artifact_generator(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    artifact_root: str | Path = DEFAULT_ARTIFACT_ROOT,
    generated_at: str | None = None,
    db_path: str | Path | None = None,
) -> CapitalHiltonInvoiceArtifactGeneratorExportResult:
    payload = build_capital_hilton_invoice_artifact_generator(
        generated_at=generated_at,
        repo_root=repo_root,
        db_path=db_path,
        artifact_root=artifact_root,
    )
    root = _resolve_repo_path(export_root, repo_root=repo_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_capital_hilton_invoice_artifact_generator(payload), encoding="utf-8")
    candidate = payload["artifact_candidate"]
    return CapitalHiltonInvoiceArtifactGeneratorExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        artifact_path=candidate["artifact_path"],
        artifact_hash=candidate["artifact_hash"],
        generation_status=candidate["artifact_status"],
        subtotal_amount=payload["artifact_input"]["subtotal"].get("amount", 0),
        external_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Capital Hilton invoice artifact generator read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--artifact-root", default=DEFAULT_ARTIFACT_ROOT.as_posix())
    parser.add_argument("--db", default=None)
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_capital_hilton_invoice_artifact_generator(
        repo_root=args.repo_root,
        export_root=args.export_root,
        artifact_root=args.artifact_root,
        db_path=args.db,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "artifact_path": result.artifact_path,
        "artifact_hash": result.artifact_hash,
        "generation_status": result.generation_status,
        "subtotal_amount": result.subtotal_amount,
        "external_authority_granted": result.external_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        payload = build_capital_hilton_invoice_artifact_generator(
            repo_root=args.repo_root,
            db_path=args.db,
            artifact_root=args.artifact_root,
        )
        print(format_capital_hilton_invoice_artifact_generator(payload), end="")
    return 0


__all__ = [
    "ARTIFACT_FILENAME",
    "ARTIFACT_STATUSES",
    "AUTHORITY_BOUNDARY",
    "CLIENT",
    "CONTRACT_STATUS",
    "DEFAULT_ARTIFACT_ROOT",
    "DEFAULT_EXPORT_ROOT",
    "DELIVERY_BLOCKERS",
    "JSON_EXPORT_NAME",
    "LANE",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_ID",
    "REQUIRED_BUSINESS_FIELDS",
    "REQUIRED_CANDIDATE_FIELDS",
    "REQUIRED_INPUT_FIELDS",
    "REQUIRED_POLICY_FIELDS",
    "REQUIRED_PREVIEW_FIELDS",
    "REQUIRED_READBACK_FIELDS",
    "SCHEMA_VERSION",
    "VISIBLE_MISSING_FIELDS",
    "WORKFLOW_SESSION_REF",
    "CapitalHiltonInvoiceArtifactCandidate",
    "CapitalHiltonInvoiceArtifactGenerationPolicy",
    "CapitalHiltonInvoiceArtifactGeneratorExportResult",
    "CapitalHiltonInvoiceArtifactInput",
    "CapitalHiltonInvoiceArtifactReadback",
    "CapitalHiltonInvoicePreviewContent",
    "build_artifact_candidate",
    "build_artifact_input",
    "build_artifact_readback",
    "build_capital_hilton_invoice_artifact_generator",
    "build_generation_policy",
    "build_preview_content",
    "export_capital_hilton_invoice_artifact_generator",
    "format_capital_hilton_invoice_artifact_generator",
    "main",
    "render_preview_markdown",
    "stable_json",
    "write_preview_artifact",
]
