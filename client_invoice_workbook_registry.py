"""Client invoice workbook registry v0.

This deterministic rail consumes metadata-only file-intake requests whose
intended_use is client_invoice_workbook_registration. It registers safe workbook
references in generated read-models only. It does not open workbooks, read
cells, parse spreadsheets, generate PDFs, send email, access Coupa/browser, run
workflows, dispatch agents, handle credentials, or scan folders.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "client_invoice_workbook_registry_v0"
READ_MODEL_ID = "client_invoice_workbook_registry"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_CLIENT_INVOICE_WORKBOOK_REGISTRY_NO_CELL_READ"

INTENDED_USE = "client_invoice_workbook_registration"
REQUEST_TYPE = "WORKBOOK_REGISTRATION_REQUEST_V0"
REQUEST_KIND = "WORKBOOK_REGISTRATION_REQUEST"

WORKBOOK_STATUSES = (
    "WORKBOOK_REFERENCE_CAPTURED",
    "WORKBOOK_CANDIDATE",
    "WORKBOOK_CONFIRMED",
    "WORKBOOK_MISSING",
    "WORKBOOK_CONTEXT_MISSING",
    "WORKBOOK_PATH_UNVERIFIED",
    "UNKNOWN_FAIL_CLOSED",
)

READBACK_STATUSES = (
    "WORKBOOK_REFERENCE_CAPTURED",
    "WORKBOOK_CANDIDATE_KEPT",
    "WORKBOOK_REPLACEMENT_CONFIRMED",
    "WORKBOOK_CONTEXT_MISSING",
    "WORKBOOK_NOT_SPREADSHEET",
    "WORKBOOK_REGISTRATION_BLOCKED",
    "UNKNOWN_FAIL_CLOSED",
)

SPREADSHEET_EXTENSIONS = {".xlsx", ".xls", ".csv"}

AUTHORITY_BOUNDARY = {
    "metadata_request_parsing_allowed": False,
    "generated_readmodel_update_allowed": False,
    "mac_response_payload_generation_allowed": False,
    "live_workbook_parse_allowed": False,
    "live_spreadsheet_cell_read_allowed": False,
    "live_pdf_generation_allowed": False,
    "live_email_send_allowed": False,
    "live_gmail_send_allowed": False,
    "live_coupa_access_allowed": False,
    "live_coupa_submit_allowed": False,
    "live_browser_allowed": False,
    "live_external_action_allowed": False,
    "live_workflow_run_allowed": False,
    "live_agent_dispatch_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

LIVE_AUTHORITY_KEYS = tuple(AUTHORITY_BOUNDARY)


@dataclass(frozen=True)
class ClientInvoiceWorkbookRecord:
    client_ref: str
    client_display_name: str
    tenant_scope: str
    workflow_ref: str
    workbook_ref: str
    workbook_display_name: str
    workbook_path_ref: str
    workbook_extension: str
    workbook_exists_status: str
    workbook_status: str
    intended_use: str
    approved_for_metadata_read: bool
    approved_for_cell_read: bool
    source_request_id: str
    source_file_metadata_ref: str
    next_safe_move: str


@dataclass(frozen=True)
class WorkbookRegistrationRequest:
    request_id: str
    source_request_id: str
    intended_use: str
    file_display_name: str
    file_extension: str
    file_type: str
    local_path_ref: str
    client_ref: str
    workflow_ref: str
    world_ref: str
    authority_boundary: dict[str, bool]
    validation_status: str
    missing_context: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class WorkbookRegistrationReadback:
    readback_id: str
    status: str
    operator_headline: str
    operator_message: str
    client_summary: str
    workbook_summary: str
    missing_items: tuple[str, ...]
    next_action: str
    hidden_refs: dict[str, Any]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class ClientInvoiceWorkbookRegistry:
    registry_id: str
    doctrine: tuple[str, ...]
    client_records: tuple[dict[str, Any], ...]
    workbook_policy: tuple[str, ...]
    invoice_sheet_policy: tuple[str, ...]
    registration_policy: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _safe_label(value: object) -> str:
    name = Path(str(value or "invoice workbook")).name.strip() or "invoice workbook"
    return name[:120]


def _normalize_extension(extension: object, display_name: object) -> str:
    ext = str(extension or "").strip().lower()
    if ext and not ext.startswith("."):
        ext = "." + ext
    return ext or Path(str(display_name or "")).suffix.lower()


def _safe_token(value: object) -> str:
    text = str(value or "").strip().lower()
    cleaned = "".join(char if char.isalnum() else "_" for char in text).strip("_")
    return cleaned or "unknown"


def _path_ref_from_request(raw_request: Mapping[str, Any], source_request_id: str) -> str:
    raw_ref = str(
        raw_request.get("local_path_ref")
        or raw_request.get("mac_visible_path_ref")
        or raw_request.get("selected_local_path")
        or ""
    ).strip()
    if not raw_ref:
        return "path_ref:missing"
    lowered = raw_ref.lower()
    safe_prefixes = ("path_ref:", "fixture_path_ref:", "mac_path_ref:", "source_ref:")
    if raw_ref.startswith(safe_prefixes) and "/" not in raw_ref and "\\" not in raw_ref:
        return raw_ref[:160]
    if lowered.startswith("fixture:") or lowered.startswith("metadata_ref:"):
        return raw_ref[:160]
    return f"path_ref:metadata_request:{source_request_id}"


def _detect_file_type(file_extension: str, file_type_hint: object, display_name: object) -> str:
    text = f"{file_type_hint or ''} {display_name or ''}".lower()
    if file_extension in SPREADSHEET_EXTENSIONS:
        return "spreadsheet"
    if "spreadsheet" in text or "workbook" in text:
        return "spreadsheet" if file_extension in SPREADSHEET_EXTENSIONS else "non_spreadsheet"
    if file_extension == ".pdf":
        return "pdf"
    if file_extension in {".txt", ".md", ".rtf", ".doc", ".docx"}:
        return "document"
    return "unknown_file_fail_closed"


def _is_spreadsheet_request(request: WorkbookRegistrationRequest) -> bool:
    return request.file_extension in SPREADSHEET_EXTENSIONS and request.file_type == "spreadsheet"


def is_workbook_registration_request(raw_request: Mapping[str, Any]) -> bool:
    request_type = str(raw_request.get("request_type") or raw_request.get("type") or "").strip().upper()
    kind = str(raw_request.get("kind") or "").strip().upper()
    return (
        str(raw_request.get("intended_use") or "").strip() == INTENDED_USE
        or request_type == REQUEST_TYPE
        or kind == REQUEST_KIND
    )


def _capital_hilton_explicit(request: WorkbookRegistrationRequest) -> bool:
    return (
        request.client_ref == "capital_hilton"
        and request.workflow_ref == "capital_hilton_invoice_workflow"
        and request.world_ref.lower() == "finance"
    )


def _client_display_name(client_ref: str) -> str:
    if client_ref == "capital_hilton":
        return "Capital Hilton"
    return " ".join(part.capitalize() for part in client_ref.replace("-", "_").split("_") if part) or "Unknown client"


def _tenant_scope(raw_request: Mapping[str, Any], request: WorkbookRegistrationRequest) -> str:
    explicit = str(raw_request.get("tenant_scope") or raw_request.get("tenant_ref") or "").strip()
    if _capital_hilton_explicit(request):
        return "tenant_scope:fixture_business_ops"
    if explicit and explicit != "unknown":
        return explicit
    return "UNKNOWN"


def normalize_registration_request(raw_request: Mapping[str, Any]) -> WorkbookRegistrationRequest:
    source_request_id = str(raw_request.get("request_id") or "unknown_file_metadata_request")
    display_name = _safe_label(
        raw_request.get("file_display_name")
        or raw_request.get("selected_local_path")
        or raw_request.get("local_path_ref")
    )
    extension = _normalize_extension(raw_request.get("file_extension"), display_name)
    file_type = _detect_file_type(extension, raw_request.get("file_type") or raw_request.get("file_kind_hint"), display_name)
    client_ref = str(raw_request.get("client_ref") or "").strip()
    workflow_ref = str(raw_request.get("workflow_ref") or "").strip()
    world_ref = str(raw_request.get("world_ref") or "").strip()
    intended_use = str(raw_request.get("intended_use") or "")
    if is_workbook_registration_request(raw_request) and not intended_use:
        intended_use = INTENDED_USE
    missing_context: list[str] = []
    if client_ref in {"", "unknown", "UNKNOWN"}:
        missing_context.append("client_ref")
    if workflow_ref in {"", "unknown", "UNKNOWN"}:
        missing_context.append("workflow_ref")
    if intended_use != INTENDED_USE:
        validation_status = "UNKNOWN_FAIL_CLOSED"
        next_move = "Use the generic file metadata rail."
    elif extension not in SPREADSHEET_EXTENSIONS or file_type != "spreadsheet":
        validation_status = "WORKBOOK_NOT_SPREADSHEET"
        next_move = "Attach a spreadsheet workbook file for invoice workbook registration."
    elif missing_context:
        validation_status = "WORKBOOK_CONTEXT_MISSING"
        next_move = "Ask which client/workflow this workbook belongs to."
    else:
        validation_status = "WORKBOOK_REFERENCE_CAPTURED"
        next_move = "Capture the workbook reference without reading workbook cells."
    return WorkbookRegistrationRequest(
        request_id=f"workbook_registration_request:{_short_hash(source_request_id, display_name, extension)}",
        source_request_id=source_request_id,
        intended_use=intended_use,
        file_display_name=display_name,
        file_extension=extension,
        file_type=file_type,
        local_path_ref=_path_ref_from_request(raw_request, source_request_id),
        client_ref=client_ref or "unknown",
        workflow_ref=workflow_ref or "unknown",
        world_ref=world_ref or "unknown",
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        validation_status=validation_status,
        missing_context=tuple(missing_context),
        next_safe_move=next_move,
    )


def _workbook_ref(request: WorkbookRegistrationRequest) -> str:
    return (
        "workbook_ref:client_invoice:"
        f"{_safe_token(request.client_ref)}:"
        f"{_safe_token(request.workflow_ref)}:"
        f"{_short_hash(request.local_path_ref, request.file_display_name, request.file_extension)}"
    )


def record_from_request(
    raw_request: Mapping[str, Any],
    request: WorkbookRegistrationRequest,
    *,
    source_file_metadata_ref: str,
    status: str = "WORKBOOK_REFERENCE_CAPTURED",
) -> ClientInvoiceWorkbookRecord:
    return ClientInvoiceWorkbookRecord(
        client_ref=request.client_ref,
        client_display_name=_client_display_name(request.client_ref),
        tenant_scope=_tenant_scope(raw_request, request),
        workflow_ref=request.workflow_ref,
        workbook_ref=_workbook_ref(request),
        workbook_display_name=request.file_display_name,
        workbook_path_ref=request.local_path_ref,
        workbook_extension=request.file_extension,
        workbook_exists_status="PATH_REF_PROVIDED_NOT_OPENED" if request.local_path_ref != "path_ref:missing" else "PATH_REF_MISSING",
        workbook_status=status,
        intended_use=request.intended_use,
        approved_for_metadata_read=True,
        approved_for_cell_read=False,
        source_request_id=request.source_request_id,
        source_file_metadata_ref=source_file_metadata_ref,
        next_safe_move="Audit the invoice sheet only after the operator requests the governed sheet audit lane.",
    )


def _registry_policy() -> dict[str, tuple[str, ...]]:
    return {
        "doctrine": (
            "Client invoice workbook references are metadata-only until a governed sheet audit lane exists.",
            "One active workbook reference per client/workflow; replacement needs explicit operator confirmation.",
            "Client-specific bindings require explicit client_ref and workflow_ref context.",
        ),
        "workbook_policy": (
            "Workbook path/ref must come from an explicit metadata request or prior approved generated record.",
            "Do not guess workbook paths from filename, client name, or folder names.",
            "Do not broad-scan folders for likely workbooks.",
        ),
        "invoice_sheet_policy": (
            "One invoice sheet/tab per invoice.",
            "This lane does not read tabs, cells, formulas, workbook bodies, or file bytes.",
            "Sheet audit is a later governed action with separate authority.",
        ),
        "registration_policy": (
            "intended_use must equal client_invoice_workbook_registration.",
            "Spreadsheet-like metadata is required for workbook registration.",
            "Missing client/workflow context asks clarification rather than binding a client.",
        ),
    }


def empty_registry() -> ClientInvoiceWorkbookRegistry:
    policies = _registry_policy()
    return ClientInvoiceWorkbookRegistry(
        registry_id="client_invoice_workbook_registry:v0",
        doctrine=policies["doctrine"],
        client_records=(),
        workbook_policy=policies["workbook_policy"],
        invoice_sheet_policy=policies["invoice_sheet_policy"],
        registration_policy=policies["registration_policy"],
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Register workbook references only from metadata-only requests.",
    )


def _records_from_existing(payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    registry = payload.get("registry") if isinstance(payload.get("registry"), Mapping) else {}
    records = registry.get("client_records") if isinstance(registry.get("client_records"), list) else []
    clean: list[dict[str, Any]] = []
    allowed = {field.name for field in fields(ClientInvoiceWorkbookRecord)}
    for record in records:
        if isinstance(record, Mapping):
            clean.append({key: record[key] for key in allowed if key in record})
    return clean


def load_existing_payload(export_root: Path = DEFAULT_EXPORT_ROOT) -> dict[str, Any] | None:
    path = Path(export_root) / JSON_EXPORT_NAME
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _matching_record(records: list[dict[str, Any]], request: WorkbookRegistrationRequest) -> dict[str, Any] | None:
    for record in records:
        if record.get("client_ref") == request.client_ref and record.get("workflow_ref") == request.workflow_ref:
            return record
    return None


def _record_from_mapping(record: Mapping[str, Any] | None) -> ClientInvoiceWorkbookRecord | None:
    if not isinstance(record, Mapping):
        return None
    values = {field.name: record.get(field.name) for field in fields(ClientInvoiceWorkbookRecord)}
    if any(value is None for value in values.values()):
        return None
    return ClientInvoiceWorkbookRecord(**values)


def _matching_record_by_refs(
    records: list[dict[str, Any]],
    *,
    client_ref: str,
    workflow_ref: str,
) -> dict[str, Any] | None:
    for record in records:
        if record.get("client_ref") == client_ref and record.get("workflow_ref") == workflow_ref:
            return record
    return None


def _readback_for(
    *,
    request: WorkbookRegistrationRequest,
    status: str,
    record: ClientInvoiceWorkbookRecord | None,
    existing_record: Mapping[str, Any] | None = None,
    candidate_record: ClientInvoiceWorkbookRecord | None = None,
) -> WorkbookRegistrationReadback:
    hidden_refs: dict[str, Any] = {
        "source_request_id": request.source_request_id,
        "workbook_path_ref": request.local_path_ref,
        "workbook_ref": record.workbook_ref if record else candidate_record.workbook_ref if candidate_record else "",
        "existing_workbook_ref": str(existing_record.get("workbook_ref") or "") if existing_record else "",
    }
    if status == "WORKBOOK_REFERENCE_CAPTURED" and record:
        capital = record.client_ref == "capital_hilton"
        headline = "Capital Hilton workbook captured" if capital else f"{record.client_display_name} workbook captured"
        message = (
            "OpenClaw captured the workbook reference for the Capital Hilton invoice workflow. "
            "The workbook body was not read. Next, audit the invoice sheet when you are ready."
            if capital
            else f"OpenClaw captured the workbook reference for {record.client_display_name}. The workbook body was not read."
        )
        next_action = (
            "Next: Audit the Capital Hilton invoice sheet."
            if capital
            else f"Next: Audit the {record.client_display_name} invoice sheet."
        )
        return WorkbookRegistrationReadback(
            readback_id=f"workbook_registration_readback:{_short_hash(request.source_request_id, status)}",
            status=status,
            operator_headline=headline,
            operator_message=message,
            client_summary=f"{record.client_display_name} / {record.workflow_ref}",
            workbook_summary=f"{record.workbook_display_name} captured as metadata-only.",
            missing_items=(),
            next_action=next_action,
            hidden_refs=hidden_refs,
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move=next_action,
        )
    if status == "WORKBOOK_CONTEXT_MISSING":
        return WorkbookRegistrationReadback(
            readback_id=f"workbook_registration_readback:{_short_hash(request.source_request_id, status)}",
            status=status,
            operator_headline="Which client is this for?",
            operator_message=(
                "OpenClaw received a workbook reference, but I need the client or workflow before registering it. "
                "The workbook body was not read."
            ),
            client_summary="Client/workflow context missing.",
            workbook_summary=f"{request.file_display_name} received as metadata-only.",
            missing_items=request.missing_context,
            next_action="Next: Choose the client for this workbook.",
            hidden_refs=hidden_refs,
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Next: Choose the client for this workbook.",
        )
    if status == "WORKBOOK_NOT_SPREADSHEET":
        return WorkbookRegistrationReadback(
            readback_id=f"workbook_registration_readback:{_short_hash(request.source_request_id, status)}",
            status=status,
            operator_headline="Workbook not captured",
            operator_message="OpenClaw received an invoice workbook registration request, but the file does not look like a spreadsheet. The file body was not read.",
            client_summary="No client workbook binding was created.",
            workbook_summary=f"{request.file_display_name} has extension {request.file_extension or 'unknown'}.",
            missing_items=("Spreadsheet workbook file",),
            next_action="Next: Attach a spreadsheet workbook.",
            hidden_refs=hidden_refs,
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Next: Attach a spreadsheet workbook.",
        )
    return WorkbookRegistrationReadback(
        readback_id=f"workbook_registration_readback:{_short_hash(request.source_request_id, status)}",
        status="WORKBOOK_REGISTRATION_BLOCKED",
        operator_headline="Confirm workbook replacement",
        operator_message=(
            "OpenClaw already has a different workbook reference for this client/workflow. "
            "I kept the existing workbook and staged this as a candidate only. The workbook body was not read."
        ),
        client_summary=f"{request.client_ref} / {request.workflow_ref}",
        workbook_summary=f"Candidate: {request.file_display_name}. Existing workbook was not overwritten.",
        missing_items=("Operator replacement confirmation",),
        next_action="Next: Confirm whether to replace the current workbook.",
        hidden_refs=hidden_refs,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Next: Confirm whether to replace the current workbook.",
    )


def keep_candidate_and_cancel_replacement(
    raw_request: Mapping[str, Any],
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Record an operator choice to leave a staged workbook as candidate-only."""

    generated_at = generated_at or utc_now()
    existing_payload = load_existing_payload(export_root)
    records = _records_from_existing(existing_payload)
    candidate_mapping = (
        existing_payload.get("candidate_record")
        if isinstance(existing_payload, Mapping) and isinstance(existing_payload.get("candidate_record"), Mapping)
        else None
    )
    candidate_record = _record_from_mapping(candidate_mapping)
    client_ref = str(raw_request.get("client_ref") or (candidate_mapping or {}).get("client_ref") or "capital_hilton")
    workflow_ref = str(
        raw_request.get("workflow_ref") or (candidate_mapping or {}).get("workflow_ref") or "capital_hilton_invoice_workflow"
    )
    existing_mapping = _matching_record_by_refs(records, client_ref=client_ref, workflow_ref=workflow_ref)
    active_record = _record_from_mapping(existing_mapping)
    source_request_id = str(raw_request.get("request_id") or "unknown_candidate_choice_request")
    readback = WorkbookRegistrationReadback(
        readback_id=f"workbook_registration_readback:{_short_hash(source_request_id, 'candidate_kept')}",
        status="WORKBOOK_CANDIDATE_KEPT",
        operator_headline="Workbook candidate kept",
        operator_message=(
            "OpenClaw kept the current Capital Hilton workbook. The test workbook remains staged as a candidate only. "
            "No workbook body or cells were read."
        ),
        client_summary=f"{client_ref} / {workflow_ref}",
        workbook_summary=(
            f"Candidate retained: {candidate_record.workbook_display_name}. Existing workbook was not replaced."
            if candidate_record
            else "No candidate workbook was promoted or replaced."
        ),
        missing_items=(),
        next_action="Next: provide the invoice field mapping when you are ready, or add the real workbook file.",
        hidden_refs={
            "source_request_id": source_request_id,
            "existing_workbook_ref": active_record.workbook_ref if active_record else "",
            "candidate_workbook_ref": candidate_record.workbook_ref if candidate_record else "",
            "candidate_source_request_id": candidate_record.source_request_id if candidate_record else "",
        },
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Next: provide the invoice field mapping when you are ready, or add the real workbook file.",
    )
    registry = empty_registry()
    registry_payload = ClientInvoiceWorkbookRegistry(
        registry_id=registry.registry_id,
        doctrine=registry.doctrine,
        client_records=tuple(records),
        workbook_policy=registry.workbook_policy,
        invoice_sheet_policy=registry.invoice_sheet_policy,
        registration_policy=registry.registration_policy,
        authority_boundary=registry.authority_boundary,
        next_safe_move=registry.next_safe_move,
    )
    payload = _build_payload(
        generated_at=generated_at,
        registry=registry_payload,
        request=None,
        readback=readback,
        active_record=active_record,
        candidate_record=candidate_record,
        duplicate_result="CANDIDATE_LEFT_UNCHANGED_BY_OPERATOR",
        existing_record=existing_mapping,
    )
    payload["operator_choice_request"] = {
        "source_request_id": source_request_id,
        "operator_choice": "LEAVE_CANDIDATE_CANCEL_REPLACEMENT",
        "client_ref": client_ref,
        "workflow_ref": workflow_ref,
        "current_workbook_preserved": active_record is not None,
        "candidate_preserved": candidate_record is not None,
        "workbook_replacement_performed": False,
        "workbook_body_read_performed": False,
        "spreadsheet_cell_read_performed": False,
        "external_action_performed": False,
    }
    payload["machine_proof"].update(
        {
            "operator_candidate_keep_choice_recorded": True,
            "current_workbook_preserved": active_record is not None,
            "candidate_preserved": candidate_record is not None,
            "workbook_replacement_performed": False,
            "candidate_promoted_to_authoritative": False,
        }
    )
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def replace_current_with_candidate(
    raw_request: Mapping[str, Any],
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Record an operator choice to make the staged candidate the current workbook reference."""

    generated_at = generated_at or utc_now()
    existing_payload = load_existing_payload(export_root)
    records = _records_from_existing(existing_payload)
    candidate_mapping = (
        existing_payload.get("candidate_record")
        if isinstance(existing_payload, Mapping) and isinstance(existing_payload.get("candidate_record"), Mapping)
        else None
    )
    candidate_record = _record_from_mapping(candidate_mapping)
    client_ref = str(raw_request.get("client_ref") or (candidate_mapping or {}).get("client_ref") or "capital_hilton")
    workflow_ref = str(
        raw_request.get("workflow_ref") or (candidate_mapping or {}).get("workflow_ref") or "capital_hilton_invoice_workflow"
    )
    existing_mapping = _matching_record_by_refs(records, client_ref=client_ref, workflow_ref=workflow_ref)
    old_active_record = _record_from_mapping(existing_mapping)
    source_request_id = str(raw_request.get("request_id") or "unknown_candidate_replacement_request")
    replacement_record: ClientInvoiceWorkbookRecord | None = None
    if candidate_record is not None and candidate_record.client_ref == client_ref and candidate_record.workflow_ref == workflow_ref:
        replacement_record = ClientInvoiceWorkbookRecord(
            client_ref=candidate_record.client_ref,
            client_display_name=candidate_record.client_display_name,
            tenant_scope=candidate_record.tenant_scope,
            workflow_ref=candidate_record.workflow_ref,
            workbook_ref=candidate_record.workbook_ref,
            workbook_display_name=candidate_record.workbook_display_name,
            workbook_path_ref=candidate_record.workbook_path_ref,
            workbook_extension=candidate_record.workbook_extension,
            workbook_exists_status=candidate_record.workbook_exists_status,
            workbook_status="WORKBOOK_CONFIRMED",
            intended_use=candidate_record.intended_use,
            approved_for_metadata_read=candidate_record.approved_for_metadata_read,
            approved_for_cell_read=False,
            source_request_id=candidate_record.source_request_id,
            source_file_metadata_ref=candidate_record.source_file_metadata_ref,
            next_safe_move="Next: confirm the invoice field mapping before audit.",
        )
        replacement_mapping = asdict(replacement_record)
        replaced = False
        for index, record in enumerate(records):
            if record.get("client_ref") == client_ref and record.get("workflow_ref") == workflow_ref:
                records[index] = replacement_mapping
                replaced = True
                break
        if not replaced:
            records.append(replacement_mapping)
    readback_status = "WORKBOOK_REPLACEMENT_CONFIRMED" if replacement_record else "WORKBOOK_REGISTRATION_BLOCKED"
    readback = WorkbookRegistrationReadback(
        readback_id=f"workbook_registration_readback:{_short_hash(source_request_id, 'candidate_replaced')}",
        status=readback_status,
        operator_headline="Capital Hilton workbook updated" if replacement_record else "No workbook candidate found",
        operator_message=(
            "OpenClaw made the new workbook the current Capital Hilton running invoice workbook. "
            "The previous workbook is no longer the active workbook reference. Nothing was deleted from disk. "
            "No workbook body or cells were read."
            if replacement_record
            else "OpenClaw did not find a staged workbook candidate to make current. No workbook body or cells were read."
        ),
        client_summary=f"{client_ref} / {workflow_ref}",
        workbook_summary=(
            f"Current workbook: {replacement_record.workbook_display_name}."
            if replacement_record
            else "No workbook replacement was performed."
        ),
        missing_items=() if replacement_record else ("staged workbook candidate",),
        next_action=(
            "Next: confirm the invoice field mapping before audit."
            if replacement_record
            else "Next: choose the workbook again in the Mac app."
        ),
        hidden_refs={
            "source_request_id": source_request_id,
            "previous_workbook_ref": old_active_record.workbook_ref if old_active_record else "",
            "current_workbook_ref": replacement_record.workbook_ref if replacement_record else "",
            "candidate_source_request_id": candidate_record.source_request_id if candidate_record else "",
        },
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move=(
            "Next: confirm the invoice field mapping before audit."
            if replacement_record
            else "Next: choose the workbook again in the Mac app."
        ),
    )
    registry = empty_registry()
    registry_payload = ClientInvoiceWorkbookRegistry(
        registry_id=registry.registry_id,
        doctrine=registry.doctrine,
        client_records=tuple(records),
        workbook_policy=registry.workbook_policy,
        invoice_sheet_policy=registry.invoice_sheet_policy,
        registration_policy=registry.registration_policy,
        authority_boundary=registry.authority_boundary,
        next_safe_move=registry.next_safe_move,
    )
    payload = _build_payload(
        generated_at=generated_at,
        registry=registry_payload,
        request=None,
        readback=readback,
        active_record=replacement_record,
        candidate_record=None,
        duplicate_result=(
            "CANDIDATE_CONFIRMED_AS_CURRENT_WORKBOOK_BY_OPERATOR"
            if replacement_record
            else "NO_STAGED_CANDIDATE_TO_CONFIRM"
        ),
        existing_record=existing_mapping,
    )
    payload["operator_choice_request"] = {
        "source_request_id": source_request_id,
        "operator_choice": "MAKE_CANDIDATE_CURRENT_WORKBOOK",
        "client_ref": client_ref,
        "workflow_ref": workflow_ref,
        "previous_workbook_ref": old_active_record.workbook_ref if old_active_record else "",
        "current_workbook_ref": replacement_record.workbook_ref if replacement_record else "",
        "workbook_replacement_performed": replacement_record is not None,
        "workbook_body_read_performed": False,
        "spreadsheet_cell_read_performed": False,
        "external_action_performed": False,
        "invoice_sent_or_submitted": False,
        "ledger_posted": False,
    }
    payload["machine_proof"].update(
        {
            "operator_candidate_replace_choice_recorded": True,
            "current_workbook_preserved": False,
            "candidate_preserved": False,
            "workbook_replacement_performed": replacement_record is not None,
            "candidate_promoted_to_authoritative": False,
            "candidate_promoted_to_current_workbook": replacement_record is not None,
            "invoice_sent_or_submitted": False,
            "ledger_posted": False,
        }
    )
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def register_workbook_request(
    raw_request: Mapping[str, Any],
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
    source_file_metadata_ref: str = "",
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    request = normalize_registration_request(raw_request)
    existing_payload = load_existing_payload(export_root)
    records = _records_from_existing(existing_payload)
    record: ClientInvoiceWorkbookRecord | None = None
    candidate_record: ClientInvoiceWorkbookRecord | None = None
    existing = _matching_record(records, request)
    duplicate_result = "NO_PRIOR_WORKBOOK_RECORD"
    readback_status = request.validation_status

    if request.validation_status == "WORKBOOK_REFERENCE_CAPTURED":
        candidate_record = record_from_request(raw_request, request, source_file_metadata_ref=source_file_metadata_ref)
        if existing is None:
            record = candidate_record
            records.append(asdict(record))
            duplicate_result = "NEW_WORKBOOK_REFERENCE_CAPTURED"
        elif existing.get("workbook_ref") == candidate_record.workbook_ref:
            record = ClientInvoiceWorkbookRecord(**{field.name: existing[field.name] for field in fields(ClientInvoiceWorkbookRecord)})
            duplicate_result = "DUPLICATE_SAME_WORKBOOK_NOOP"
        else:
            readback_status = "WORKBOOK_REGISTRATION_BLOCKED"
            candidate_record = record_from_request(
                raw_request,
                request,
                source_file_metadata_ref=source_file_metadata_ref,
                status="WORKBOOK_CANDIDATE",
            )
            duplicate_result = "DIFFERENT_WORKBOOK_CANDIDATE_REQUIRES_CONFIRMATION"

    readback = _readback_for(
        request=request,
        status=readback_status,
        record=record,
        existing_record=existing,
        candidate_record=candidate_record,
    )
    registry = empty_registry()
    registry_payload = ClientInvoiceWorkbookRegistry(
        registry_id=registry.registry_id,
        doctrine=registry.doctrine,
        client_records=tuple(records),
        workbook_policy=registry.workbook_policy,
        invoice_sheet_policy=registry.invoice_sheet_policy,
        registration_policy=registry.registration_policy,
        authority_boundary=registry.authority_boundary,
        next_safe_move=registry.next_safe_move,
    )
    return _build_payload(
        generated_at=generated_at,
        registry=registry_payload,
        request=request,
        readback=readback,
        active_record=record,
        candidate_record=candidate_record if readback_status == "WORKBOOK_REGISTRATION_BLOCKED" else None,
        duplicate_result=duplicate_result,
        existing_record=existing,
    )


def _example_requests() -> dict[str, dict[str, Any]]:
    base = make_capital_hilton_fixture_request()
    missing = dict(base)
    missing.update({"client_ref": "unknown", "workflow_ref": "unknown", "payload_hash": "fixture_hash_context_missing"})
    not_sheet = dict(base)
    not_sheet.update({"file_display_name": "Capital Hilton invoice.pdf", "file_extension": ".pdf", "file_kind_hint": "invoice pdf"})
    return {
        "capital_hilton_success": base,
        "missing_context": missing,
        "non_spreadsheet": not_sheet,
    }


def _build_payload(
    *,
    generated_at: str,
    registry: ClientInvoiceWorkbookRegistry,
    request: WorkbookRegistrationRequest | None,
    readback: WorkbookRegistrationReadback | None,
    active_record: ClientInvoiceWorkbookRecord | None,
    candidate_record: ClientInvoiceWorkbookRecord | None,
    duplicate_result: str,
    existing_record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    examples = {
        name: {
            "source_request_id": value["request_id"],
            "intended_use": value["intended_use"],
            "file_display_name": value["file_display_name"],
            "file_extension": value["file_extension"],
            "client_ref": value.get("client_ref", "unknown"),
            "workflow_ref": value.get("workflow_ref", "unknown"),
        }
        for name, value in _example_requests().items()
    }
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "workbook_statuses": WORKBOOK_STATUSES,
        "readback_statuses": READBACK_STATUSES,
        "model_schemas": {
            "ClientInvoiceWorkbookRegistry": tuple(field.name for field in fields(ClientInvoiceWorkbookRegistry)),
            "ClientInvoiceWorkbookRecord": tuple(field.name for field in fields(ClientInvoiceWorkbookRecord)),
            "WorkbookRegistrationRequest": tuple(field.name for field in fields(WorkbookRegistrationRequest)),
            "WorkbookRegistrationReadback": tuple(field.name for field in fields(WorkbookRegistrationReadback)),
        },
        "registry": asdict(registry),
        "registration_request": asdict(request) if request else None,
        "registration_readback": asdict(readback) if readback else None,
        "active_record": asdict(active_record) if active_record else None,
        "candidate_record": asdict(candidate_record) if candidate_record else None,
        "existing_record": dict(existing_record) if existing_record else None,
        "duplicate_result": duplicate_result,
        "examples": examples,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "registry_model_present": True,
            "workbook_record_model_present": True,
            "registration_request_model_present": True,
            "registration_readback_model_present": True,
            "intended_use_required": True,
            "spreadsheet_type_required": True,
            "capital_hilton_bound_only_with_explicit_context": bool(
                active_record
                and active_record.client_ref == "capital_hilton"
                and active_record.workflow_ref == "capital_hilton_invoice_workflow"
            ),
            "duplicate_same_workbook_idempotent": duplicate_result == "DUPLICATE_SAME_WORKBOOK_NOOP",
            "different_workbook_does_not_overwrite": duplicate_result
            == "DIFFERENT_WORKBOOK_CANDIDATE_REQUIRES_CONFIRMATION",
            "approved_for_cell_read_false": all(
                record.get("approved_for_cell_read") is False for record in registry.client_records
            )
            and (candidate_record is None or candidate_record.approved_for_cell_read is False),
            "metadata_only_request_parsed": True,
            "generated_readmodel_update_performed": True,
            "mac_response_payload_generation_supported": True,
            "workbook_body_read_performed": False,
            "spreadsheet_parse_performed": False,
            "spreadsheet_cell_read_performed": False,
            "formula_read_performed": False,
            "folder_scan_performed": False,
            "pdf_generation_performed": False,
            "email_send_performed": False,
            "gmail_send_performed": False,
            "coupa_access_or_submit_performed": False,
            "browser_access_performed": False,
            "workflow_execution_performed": False,
            "agent_dispatch_performed": False,
            "credential_handling_performed": False,
            "raw_body_ingestion_performed": False,
            "external_action_performed": False,
            "network_used": False,
            "mission_control_swift_changed": False,
            "mac_sync_import_run": False,
            "git_push_pull_fetch_run": False,
            "all_live_authority_false": all(AUTHORITY_BOUNDARY[key] is False for key in LIVE_AUTHORITY_KEYS),
            "content_hash": "",
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def build_payload(*, export_root: Path = DEFAULT_EXPORT_ROOT, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    existing = load_existing_payload(export_root)
    if existing is not None:
        return existing
    return register_workbook_request(
        make_capital_hilton_fixture_request(),
        export_root=export_root,
        generated_at=generated_at,
        source_file_metadata_ref="generated/read_models/operator_file_metadata_readback.json",
    )


def make_capital_hilton_fixture_request(*, created_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    return {
        "request_id": "mission_control_file_intake_request_capital_hilton_workbook_fixture",
        "origin_surface": "Mission Control chat",
        "source_channel": "mission_control_chat_attachment",
        "workflow_ref": "capital_hilton_invoice_workflow",
        "world_ref": "finance",
        "lane_ref": "Capital Hilton",
        "client_ref": "capital_hilton",
        "tenant_ref": "openclaw_repo_a_local",
        "operator_goal": "Register this workbook as the invoice workbook.",
        "intended_use": INTENDED_USE,
        "file_display_name": "Capital Hilton invoice workbook.xlsx",
        "file_kind_hint": "invoice workbook spreadsheet",
        "mac_visible_path_ref": "fixture_path_ref:capital_hilton_invoice_workbook",
        "file_size_bytes": 24576,
        "file_extension": ".xlsx",
        "privacy_class": "business_source_metadata",
        "requested_intake_mode": "METADATA_ONLY",
        "idempotency_key": "client_invoice_workbook_registration_capital_hilton_fixture",
        "payload_hash": "fixture_hash_capital_hilton_workbook_registration",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "created_at": created_at,
    }


def format_operator_markdown(payload: Mapping[str, Any]) -> str:
    readback = payload.get("registration_readback") or {}
    registry = payload.get("registry") or {}
    lines = [
        "# Client Invoice Workbook Registry",
        "",
        "ELIOPERATOR: Metadata-only workbook registration. No workbook body, cells, tabs, formulas, folders, browser, Coupa, PDF, email, or external systems were touched.",
        "",
        f"- Status: `{readback.get('status', 'UNKNOWN')}`",
        f"- Client records: `{len(registry.get('client_records') or [])}`",
        f"- Duplicate result: `{payload.get('duplicate_result', 'UNKNOWN')}`",
        "",
        f"## {readback.get('operator_headline', 'Workbook registry')}",
        "",
        str(readback.get("operator_message") or "No workbook registration request was processed."),
        "",
        "## Next",
        "",
        str(readback.get("next_action") or registry.get("next_safe_move") or "Wait for a metadata-only workbook request."),
        "",
    ]
    return "\n".join(lines)


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: Mapping[str, Any], paths: tuple[Path, Path]) -> dict[str, Any]:
    readback = payload.get("registration_readback") or {}
    active_record = payload.get("active_record") or {}
    registry = payload.get("registry") or {}
    return {
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": paths[0].as_posix(),
        "operator_path": paths[1].as_posix(),
        "status": readback.get("status"),
        "operator_headline": readback.get("operator_headline"),
        "next_action": readback.get("next_action"),
        "client_ref": active_record.get("client_ref"),
        "workflow_ref": active_record.get("workflow_ref"),
        "workbook_ref": active_record.get("workbook_ref"),
        "client_record_count": len(registry.get("client_records") or ()),
        "duplicate_result": payload.get("duplicate_result"),
        "approved_for_cell_read_false": payload["machine_proof"]["approved_for_cell_read_false"],
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the metadata-only client invoice workbook registry.")
    parser.add_argument("--format", choices=("json", "summary"), default="json")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--fixture", choices=("capital_hilton", "none"), default="capital_hilton")
    args = parser.parse_args(argv)

    export_root = Path(args.export_root)
    if args.fixture == "capital_hilton":
        payload = register_workbook_request(
            make_capital_hilton_fixture_request(created_at=args.generated_at),
            export_root=export_root,
            generated_at=args.generated_at,
            source_file_metadata_ref="generated/read_models/operator_file_metadata_readback.json",
        )
    else:
        registry = empty_registry()
        payload = _build_payload(
            generated_at=args.generated_at,
            registry=registry,
            request=None,
            readback=None,
            active_record=None,
            candidate_record=None,
            duplicate_result="NO_REQUEST_PROCESSED",
            existing_record=None,
        )
    paths = write_exports(payload, export_root)
    output: Mapping[str, Any] = payload if args.format == "json" else build_summary(payload, paths)
    sys.stdout.write(stable_json(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
