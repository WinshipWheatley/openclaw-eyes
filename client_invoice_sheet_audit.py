"""Client invoice sheet audit v0.

This rail audits explicitly whitelisted invoice sheet cells after a workbook
reference exists. It is generic and client-scoped; Capital Hilton is only the
first fixture. The rail never infers sheet layout, never dumps rows/sheets, and
never evaluates formulas, macros, external links, or external systems.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import zipfile
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping
from xml.etree import ElementTree

import client_invoice_workbook_registry


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "client_invoice_sheet_audit_v0"
READ_MODEL_ID = "client_invoice_sheet_audit"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_CLIENT_INVOICE_SHEET_AUDIT_WHITELISTED_READ"

INTENDED_USE = "client_invoice_sheet_audit"

AUDIT_STATUSES = (
    "SHEET_AUDIT_COMPLETE",
    "SHEET_AUDIT_NO_WORKBOOK_REGISTERED",
    "APPROVED_PC_PATH_REQUIRED",
    "SHEET_AUDIT_WORKBOOK_PATH_MISSING",
    "SHEET_AUDIT_SCHEMA_MISSING",
    "SHEET_AUDIT_SHEET_MISSING",
    "SHEET_AUDIT_REQUIRED_FIELD_MISSING",
    "SHEET_AUDIT_FORMULA_CONFIRMATION_REQUIRED",
    "SHEET_AUDIT_UNSUPPORTED_WORKBOOK_FORMAT",
    "SHEET_AUDIT_CONTEXT_MISSING",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_workbook_parse_allowed": False,
    "live_arbitrary_spreadsheet_parse_allowed": False,
    "live_full_workbook_ingestion_allowed": False,
    "live_full_sheet_dump_allowed": False,
    "live_formula_evaluation_allowed": False,
    "live_macro_processing_allowed": False,
    "live_external_link_follow_allowed": False,
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

ALLOWED_FORMULA_POLICIES = (
    "FORMULA_BLOCK_UNLESS_OPERATOR_CONFIRMS",
    "ALLOW_CACHED_READBACK_IF_EXPLICITLY_ALLOWED",
)


@dataclass(frozen=True)
class WhitelistedCellTarget:
    field_name: str
    cell_ref: str
    expected_value_type: str
    required: bool
    formula_policy: str


@dataclass(frozen=True)
class WhitelistedColumnTarget:
    field_name: str
    header_name: str
    header_cell: str
    data_cells: tuple[str, ...]
    expected_value_type: str
    required: bool
    formula_policy: str


@dataclass(frozen=True)
class WhitelistedSheetTarget:
    sheet_name: str
    allowed_cells: tuple[WhitelistedCellTarget, ...]
    allowed_columns: tuple[WhitelistedColumnTarget, ...]


@dataclass(frozen=True)
class ClientInvoiceSheetAuditSchema:
    schema_id: str
    schema_version: str
    client_ref: str
    workflow_ref: str
    world_ref: str
    sheet_target: WhitelistedSheetTarget
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...]
    expected_value_types: dict[str, str]
    formula_cached_readback_policy: str
    known_facts: dict[str, Any]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class ClientInvoiceSheetAuditRequest:
    request_id: str
    source_request_id: str
    intended_use: str
    client_ref: str
    workflow_ref: str
    world_ref: str
    workbook_ref: str
    registry_readmodel_ref: str
    approved_pc_path_ref: str
    schema_ref: str
    authority_boundary: dict[str, bool]
    validation_status: str
    missing_context: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class ClientInvoiceSheetAuditResult:
    result_id: str
    status: str
    client_ref: str
    workflow_ref: str
    world_ref: str
    workbook_registry_record_ref: str
    workbook_path_ref: str
    workbook_path_known_and_approved: bool
    path_pc_readable: bool
    schema_explicit: bool
    sheet_audited: str
    whitelist_used: tuple[dict[str, Any], ...]
    fields_read: tuple[dict[str, Any], ...]
    fields_missing: tuple[str, ...]
    fields_blocked_due_to_formula: tuple[dict[str, Any], ...]
    conflicts_vs_known_facts: tuple[dict[str, Any], ...]
    po_reference_status: str
    body_ingested: bool
    arbitrary_parse: bool
    inferred_schema: bool
    full_sheet_dump: bool
    formula_evaluated: bool
    macro_processed: bool
    external_links_followed: bool
    external_action: bool
    next_recommended_lane: str


@dataclass(frozen=True)
class ClientInvoiceSheetAuditReadback:
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


def _safe_text(value: object, fallback: str = "unknown") -> str:
    text = str(value or "").strip()
    return text or fallback


def _safe_cell_ref(value: object) -> str:
    text = str(value or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{1,3}[1-9][0-9]{0,6}", text):
        return ""
    return text


def _safe_field_name(value: object) -> str:
    text = str(value or "").strip().lower()
    cleaned = "".join(char if char.isalnum() else "_" for char in text).strip("_")
    return cleaned or "unknown_field"


def is_sheet_audit_request(raw_request: Mapping[str, Any]) -> bool:
    return str(raw_request.get("intended_use") or "").strip() == INTENDED_USE


def _capital_hilton_explicit(client_ref: str, workflow_ref: str, world_ref: str) -> bool:
    return client_ref == "capital_hilton" and workflow_ref == "capital_hilton_invoice_workflow" and world_ref == "finance"


def _normalize_cell_target(raw: Mapping[str, Any]) -> WhitelistedCellTarget | None:
    cell_ref = _safe_cell_ref(raw.get("cell_ref"))
    if not cell_ref:
        return None
    formula_policy = str(raw.get("formula_policy") or "FORMULA_BLOCK_UNLESS_OPERATOR_CONFIRMS")
    if formula_policy not in ALLOWED_FORMULA_POLICIES:
        formula_policy = "FORMULA_BLOCK_UNLESS_OPERATOR_CONFIRMS"
    return WhitelistedCellTarget(
        field_name=_safe_field_name(raw.get("field_name")),
        cell_ref=cell_ref,
        expected_value_type=str(raw.get("expected_value_type") or "text"),
        required=bool(raw.get("required")),
        formula_policy=formula_policy,
    )


def _normalize_column_target(raw: Mapping[str, Any]) -> WhitelistedColumnTarget | None:
    header_cell = _safe_cell_ref(raw.get("header_cell"))
    data_cells = tuple(cell for cell in (_safe_cell_ref(value) for value in raw.get("data_cells") or ()) if cell)
    if not header_cell and not data_cells:
        return None
    formula_policy = str(raw.get("formula_policy") or "FORMULA_BLOCK_UNLESS_OPERATOR_CONFIRMS")
    if formula_policy not in ALLOWED_FORMULA_POLICIES:
        formula_policy = "FORMULA_BLOCK_UNLESS_OPERATOR_CONFIRMS"
    return WhitelistedColumnTarget(
        field_name=_safe_field_name(raw.get("field_name")),
        header_name=str(raw.get("header_name") or ""),
        header_cell=header_cell,
        data_cells=data_cells,
        expected_value_type=str(raw.get("expected_value_type") or "text"),
        required=bool(raw.get("required")),
        formula_policy=formula_policy,
    )


def normalize_schema(raw_schema: Mapping[str, Any] | None) -> ClientInvoiceSheetAuditSchema | None:
    if not isinstance(raw_schema, Mapping):
        return None
    sheet = raw_schema.get("sheet_target") if isinstance(raw_schema.get("sheet_target"), Mapping) else {}
    sheet_name = str(sheet.get("sheet_name") or raw_schema.get("sheet_name") or "").strip()
    cell_targets = tuple(
        target
        for target in (_normalize_cell_target(item) for item in sheet.get("allowed_cells") or raw_schema.get("allowed_cells") or ())
        if target is not None
    )
    column_targets = tuple(
        target
        for target in (
            _normalize_column_target(item) for item in sheet.get("allowed_columns") or raw_schema.get("allowed_columns") or ()
        )
        if target is not None
    )
    if not sheet_name or (not cell_targets and not column_targets):
        return None
    expected_types = {target.field_name: target.expected_value_type for target in cell_targets}
    expected_types.update({target.field_name: target.expected_value_type for target in column_targets})
    required_fields = tuple(
        dict.fromkeys(
            tuple(_safe_field_name(value) for value in raw_schema.get("required_fields") or ())
            + tuple(target.field_name for target in cell_targets if target.required)
            + tuple(target.field_name for target in column_targets if target.required)
        )
    )
    optional_fields = tuple(
        dict.fromkeys(
            tuple(_safe_field_name(value) for value in raw_schema.get("optional_fields") or ())
            + tuple(target.field_name for target in cell_targets if not target.required)
            + tuple(target.field_name for target in column_targets if not target.required)
        )
    )
    formula_policy = str(raw_schema.get("formula_cached_readback_policy") or "FORMULA_BLOCK_UNLESS_OPERATOR_CONFIRMS")
    if formula_policy not in ALLOWED_FORMULA_POLICIES:
        formula_policy = "FORMULA_BLOCK_UNLESS_OPERATOR_CONFIRMS"
    return ClientInvoiceSheetAuditSchema(
        schema_id=str(raw_schema.get("schema_id") or f"sheet_audit_schema:{_short_hash(sheet_name, required_fields)}"),
        schema_version=str(raw_schema.get("schema_version") or "v0"),
        client_ref=str(raw_schema.get("client_ref") or "unknown"),
        workflow_ref=str(raw_schema.get("workflow_ref") or "unknown"),
        world_ref=str(raw_schema.get("world_ref") or "unknown"),
        sheet_target=WhitelistedSheetTarget(
            sheet_name=sheet_name,
            allowed_cells=cell_targets,
            allowed_columns=column_targets,
        ),
        required_fields=required_fields,
        optional_fields=optional_fields,
        expected_value_types=expected_types,
        formula_cached_readback_policy=formula_policy,
        known_facts=dict(raw_schema.get("known_facts") or {}),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Read only the whitelisted invoice sheet fields.",
    )


def load_registry_payload(export_root: Path = DEFAULT_EXPORT_ROOT) -> dict[str, Any] | None:
    path = Path(export_root) / client_invoice_workbook_registry.JSON_EXPORT_NAME
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _registry_records(payload: Mapping[str, Any] | None) -> tuple[dict[str, Any], ...]:
    if not isinstance(payload, Mapping):
        return ()
    registry = payload.get("registry") if isinstance(payload.get("registry"), Mapping) else {}
    records = registry.get("client_records") if isinstance(registry.get("client_records"), list) else []
    return tuple(dict(record) for record in records if isinstance(record, Mapping))


def find_workbook_record(
    registry_payload: Mapping[str, Any] | None,
    *,
    client_ref: str,
    workflow_ref: str,
    world_ref: str,
) -> dict[str, Any] | None:
    if not _capital_hilton_explicit(client_ref, workflow_ref, world_ref):
        return None
    for record in _registry_records(registry_payload):
        if (
            record.get("client_ref") == client_ref
            and record.get("workflow_ref") == workflow_ref
            and record.get("workbook_status") in {"WORKBOOK_REFERENCE_CAPTURED", "WORKBOOK_CONFIRMED"}
        ):
            return record
    return None


def _schema_from_request(raw_request: Mapping[str, Any]) -> ClientInvoiceSheetAuditSchema | None:
    schema = raw_request.get("sheet_audit_schema")
    if not isinstance(schema, Mapping):
        schema = raw_request.get("audit_schema")
    return normalize_schema(schema if isinstance(schema, Mapping) else None)


def _mac_visible_only(path_ref: object) -> bool:
    text = str(path_ref or "").strip()
    lowered = text.lower()
    return (
        text.startswith("/Volumes/")
        or lowered.startswith("mac_path_ref:")
        or lowered.startswith("mac_visible_path_ref:")
        or "/volumes/" in lowered
    )


def _path_ref_from_approved_path(raw_request: Mapping[str, Any], path: Path | None) -> str:
    explicit = str(raw_request.get("approved_pc_workbook_path_ref") or "").strip()
    if explicit:
        return explicit[:200]
    if path is None:
        return ""
    return f"approved_pc_path_ref:{_short_hash(path.as_posix())}"


def _approved_path(raw_request: Mapping[str, Any]) -> tuple[Path | None, bool]:
    if raw_request.get("approved_pc_workbook_path_authorized") is not True:
        return None, False
    raw_path = str(raw_request.get("approved_pc_workbook_path") or "").strip()
    if not raw_path:
        return None, False
    path = Path(raw_path)
    return path, path.is_file()


def _validation_status(
    raw_request: Mapping[str, Any],
    *,
    registry_record: Mapping[str, Any] | None,
    schema: ClientInvoiceSheetAuditSchema | None,
    approved_path: Path | None,
    path_readable: bool,
) -> tuple[str, tuple[str, ...], str]:
    client_ref = str(raw_request.get("client_ref") or "unknown")
    workflow_ref = str(raw_request.get("workflow_ref") or "unknown")
    world_ref = str(raw_request.get("world_ref") or "unknown")
    missing: list[str] = []
    if not _capital_hilton_explicit(client_ref, workflow_ref, world_ref):
        for key, value in (("client_ref", client_ref), ("workflow_ref", workflow_ref), ("world_ref", world_ref)):
            if value in {"", "unknown", "UNKNOWN"}:
                missing.append(key)
        return "SHEET_AUDIT_CONTEXT_MISSING", tuple(missing or ("explicit Capital Hilton finance context",)), "Confirm the client/workflow/world before auditing a sheet."
    if registry_record is None:
        return "SHEET_AUDIT_NO_WORKBOOK_REGISTERED", ("registered workbook",), "Next: Register or capture the Capital Hilton invoice workbook first."
    registry_path_ref = registry_record.get("workbook_path_ref")
    if approved_path is None:
        status = "APPROVED_PC_PATH_REQUIRED" if _mac_visible_only(registry_path_ref) or registry_path_ref else "SHEET_AUDIT_WORKBOOK_PATH_MISSING"
        return status, ("approved PC-readable workbook path",), "Next: Provide an approved PC-readable workbook path or handoff."
    if not path_readable:
        return "SHEET_AUDIT_WORKBOOK_PATH_MISSING", ("readable workbook file",), "Next: Provide an approved PC-readable workbook path or handoff."
    if schema is None:
        return "SHEET_AUDIT_SCHEMA_MISSING", ("explicit sheet/schema mapping",), "Next: Confirm the invoice sheet/schema mapping."
    return "READY_TO_AUDIT", (), "Read only the whitelisted invoice sheet fields."


def normalize_audit_request(
    raw_request: Mapping[str, Any],
    *,
    registry_payload: Mapping[str, Any] | None,
    export_root: Path = DEFAULT_EXPORT_ROOT,
) -> tuple[ClientInvoiceSheetAuditRequest, ClientInvoiceSheetAuditSchema | None, dict[str, Any] | None, Path | None, bool]:
    source_request_id = str(raw_request.get("request_id") or "unknown_sheet_audit_request")
    client_ref = str(raw_request.get("client_ref") or "unknown").strip()
    workflow_ref = str(raw_request.get("workflow_ref") or "unknown").strip()
    world_ref = str(raw_request.get("world_ref") or "unknown").strip()
    schema = _schema_from_request(raw_request)
    record = find_workbook_record(
        registry_payload,
        client_ref=client_ref,
        workflow_ref=workflow_ref,
        world_ref=world_ref,
    )
    approved_path, path_readable = _approved_path(raw_request)
    validation_status, missing_context, next_move = _validation_status(
        raw_request,
        registry_record=record,
        schema=schema,
        approved_path=approved_path,
        path_readable=path_readable,
    )
    request = ClientInvoiceSheetAuditRequest(
        request_id=f"sheet_audit_request:{_short_hash(source_request_id, client_ref, workflow_ref, world_ref)}",
        source_request_id=source_request_id,
        intended_use=str(raw_request.get("intended_use") or ""),
        client_ref=client_ref,
        workflow_ref=workflow_ref,
        world_ref=world_ref,
        workbook_ref=str(record.get("workbook_ref") or "") if record else "",
        registry_readmodel_ref=(Path(export_root) / client_invoice_workbook_registry.JSON_EXPORT_NAME).as_posix(),
        approved_pc_path_ref=_path_ref_from_approved_path(raw_request, approved_path),
        schema_ref=schema.schema_id if schema else "",
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        validation_status=validation_status,
        missing_context=missing_context,
        next_safe_move=next_move,
    )
    return request, schema, record, approved_path, path_readable


def _xlsx_namespaces() -> dict[str, str]:
    return {
        "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
    }


def _xml_from_zip(zf: zipfile.ZipFile, name: str) -> ElementTree.Element:
    return ElementTree.fromstring(zf.read(name))


def _shared_strings(zf: zipfile.ZipFile) -> tuple[str, ...]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return ()
    root = _xml_from_zip(zf, "xl/sharedStrings.xml")
    ns = _xlsx_namespaces()
    values: list[str] = []
    for item in root.findall(".//main:si", ns):
        pieces = [node.text or "" for node in item.findall(".//main:t", ns)]
        values.append("".join(pieces))
    return tuple(values)


def _sheet_path_for_name(zf: zipfile.ZipFile, sheet_name: str) -> str | None:
    ns = _xlsx_namespaces()
    workbook = _xml_from_zip(zf, "xl/workbook.xml")
    rels = _xml_from_zip(zf, "xl/_rels/workbook.xml.rels")
    targets: dict[str, str] = {}
    for rel in rels.findall(".//pkgrel:Relationship", ns):
        rel_id = rel.attrib.get("Id")
        target = rel.attrib.get("Target")
        if rel_id and target:
            path = PurePosixPath("xl") / PurePosixPath(target)
            targets[rel_id] = path.as_posix()
    for sheet in workbook.findall(".//main:sheet", ns):
        if sheet.attrib.get("name") == sheet_name:
            rel_id = sheet.attrib.get(f"{{{ns['rel']}}}id")
            return targets.get(str(rel_id))
    return None


def _cell_text(cell: ElementTree.Element, shared_strings: tuple[str, ...], ns: Mapping[str, str]) -> tuple[Any, bool, bool]:
    formula = cell.find("main:f", ns)
    formula_present = formula is not None
    inline_text = cell.find("main:is/main:t", ns)
    if inline_text is not None:
        return inline_text.text or "", formula_present, False
    value = cell.find("main:v", ns)
    if value is None:
        return None, formula_present, False
    raw_value = value.text or ""
    cell_type = cell.attrib.get("t")
    if cell_type == "s":
        try:
            return shared_strings[int(raw_value)], formula_present, True
        except (ValueError, IndexError):
            return None, formula_present, True
    if cell_type == "b":
        return raw_value == "1", formula_present, True
    if cell_type == "str":
        return raw_value, formula_present, True
    try:
        if "." in raw_value:
            return float(raw_value), formula_present, True
        return int(raw_value), formula_present, True
    except ValueError:
        return raw_value, formula_present, True


def _target_cell_refs(schema: ClientInvoiceSheetAuditSchema) -> tuple[str, ...]:
    refs: list[str] = []
    refs.extend(target.cell_ref for target in schema.sheet_target.allowed_cells)
    for target in schema.sheet_target.allowed_columns:
        refs.append(target.header_cell)
        refs.extend(target.data_cells)
    return tuple(dict.fromkeys(ref for ref in refs if ref))


def _read_xlsx_whitelisted_cells(path: Path, schema: ClientInvoiceSheetAuditSchema) -> tuple[dict[str, dict[str, Any]], dict[str, bool]]:
    target_refs = set(_target_cell_refs(schema))
    values: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        flags = {
            "macro_present": "xl/vbaProject.bin" in names,
            "external_links_present": any(name.startswith("xl/externalLinks/") for name in names),
        }
        sheet_path = _sheet_path_for_name(zf, schema.sheet_target.sheet_name)
        if sheet_path is None or sheet_path not in names:
            raise KeyError("sheet_missing")
        ns = _xlsx_namespaces()
        shared_strings = _shared_strings(zf)
        worksheet = _xml_from_zip(zf, sheet_path)
        for cell in worksheet.findall(".//main:c", ns):
            cell_ref = str(cell.attrib.get("r") or "").upper()
            if cell_ref not in target_refs:
                continue
            value, formula_present, cached_value_present = _cell_text(cell, shared_strings, ns)
            values[cell_ref] = {
                "cell_ref": cell_ref,
                "value": value,
                "formula_present": formula_present,
                "cached_value_present": cached_value_present,
            }
        return values, flags


def _cell_ref_to_indexes(cell_ref: str) -> tuple[int, int]:
    match = re.fullmatch(r"([A-Z]+)([1-9][0-9]*)", cell_ref)
    if not match:
        raise ValueError(cell_ref)
    col = 0
    for char in match.group(1):
        col = col * 26 + (ord(char) - ord("A") + 1)
    return int(match.group(2)) - 1, col - 1


def _read_csv_whitelisted_cells(path: Path, schema: ClientInvoiceSheetAuditSchema) -> tuple[dict[str, dict[str, Any]], dict[str, bool]]:
    target_refs = set(_target_cell_refs(schema))
    target_indexes = {_cell_ref_to_indexes(ref): ref for ref in target_refs}
    values: dict[str, dict[str, Any]] = {}
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        for row_index, row in enumerate(reader):
            needed_cols = [col for (r, col), _ref in target_indexes.items() if r == row_index]
            if not needed_cols:
                continue
            for col_index in needed_cols:
                cell_ref = target_indexes[(row_index, col_index)]
                values[cell_ref] = {
                    "cell_ref": cell_ref,
                    "value": row[col_index] if col_index < len(row) else None,
                    "formula_present": False,
                    "cached_value_present": False,
                }
    return values, {"macro_present": False, "external_links_present": False}


def _read_whitelisted_cells(path: Path, schema: ClientInvoiceSheetAuditSchema) -> tuple[dict[str, dict[str, Any]], dict[str, bool]]:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return _read_xlsx_whitelisted_cells(path, schema)
    if suffix == ".csv":
        return _read_csv_whitelisted_cells(path, schema)
    raise ValueError("unsupported_workbook_format")


def _target_descriptors(schema: ClientInvoiceSheetAuditSchema) -> tuple[dict[str, Any], ...]:
    descriptors: list[dict[str, Any]] = []
    for target in schema.sheet_target.allowed_cells:
        descriptors.append(
            {
                "target_type": "cell",
                "field_name": target.field_name,
                "cell_ref": target.cell_ref,
                "required": target.required,
                "expected_value_type": target.expected_value_type,
                "formula_policy": target.formula_policy,
            }
        )
    for target in schema.sheet_target.allowed_columns:
        descriptors.append(
            {
                "target_type": "column",
                "field_name": target.field_name,
                "header_name": target.header_name,
                "header_cell": target.header_cell,
                "data_cells": target.data_cells,
                "required": target.required,
                "expected_value_type": target.expected_value_type,
                "formula_policy": target.formula_policy,
            }
        )
    return tuple(descriptors)


def _field_from_target(
    *,
    field_name: str,
    value: Any,
    cell_refs: Iterable[str],
    expected_value_type: str,
    required: bool,
    formula_present: bool,
    cached_value_present: bool,
    verified: bool,
    promotion_status: str,
    value_type_valid: bool,
    mismatch_reason: str,
) -> dict[str, Any]:
    return {
        "field_name": field_name,
        "cell_refs": tuple(cell_refs),
        "value": value,
        "expected_value_type": expected_value_type,
        "required": required,
        "formula_present": formula_present,
        "cached_value_present": cached_value_present,
        "verified": verified,
        "value_origin": "formula_derived_workbook_value" if formula_present else "whitelisted_workbook_cell",
        "accepted_as_openclaw_fact": verified,
        "promotion_status": promotion_status,
        "value_type_valid": value_type_valid,
        "mismatch_reason": mismatch_reason,
        "confidence": "high" if verified else "low",
    }


def _formula_blocks_target(
    target_policy: str,
    schema_policy: str,
    *,
    formula_present: bool,
    cached_value_present: bool,
) -> bool:
    if not formula_present:
        return False
    return not (
        target_policy == "ALLOW_CACHED_READBACK_IF_EXPLICITLY_ALLOWED"
        and schema_policy == "ALLOW_CACHED_READBACK_IF_EXPLICITLY_ALLOWED"
        and cached_value_present
    )


def _value_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _values_for_validation(value: Any) -> tuple[Any, ...]:
    if isinstance(value, (tuple, list)):
        return tuple(item for item in value if not _value_missing(item))
    return () if _value_missing(value) else (value,)


def _currency_value_valid(value: Any) -> bool:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    if not isinstance(value, str):
        return False
    text = value.strip()
    return bool(re.fullmatch(r"\$?\s*-?\d{1,3}(?:,\d{3})*(?:\.\d+)?|-?\d+(?:\.\d+)?", text))


def _looks_like_date_list(value: Any) -> bool:
    text = " ".join(str(item) for item in _values_for_validation(value))
    return len(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)) >= 2


def _validate_expected_value(field_name: str, expected_value_type: str, value: Any) -> tuple[bool, str]:
    values = _values_for_validation(value)
    if not values:
        return False, "VALUE_MISSING"
    expected = expected_value_type.lower().strip()
    if expected == "currency":
        if all(_currency_value_valid(item) for item in values):
            return True, ""
        return False, "EXPECTED_CURRENCY_VALUE"
    if field_name in {"po_reference", "coupa_po_reference"} and _looks_like_date_list(value):
        return False, "PO_REFERENCE_LOOKS_LIKE_DATE_LIST"
    return True, ""


def _known_fact_conflicts(fields_read: tuple[dict[str, Any], ...], known_facts: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    conflicts: list[dict[str, Any]] = []
    by_field = {field["field_name"]: field for field in fields_read}
    for field_name, expected in known_facts.items():
        field = by_field.get(str(field_name))
        if field and field.get("verified") is True and str(field.get("value") or "").strip() and str(field.get("value")) != str(expected):
            conflicts.append({"field_name": str(field_name), "expected": str(expected), "actual": str(field.get("value"))})
    return tuple(conflicts)


def _evaluate_whitelist(
    schema: ClientInvoiceSheetAuditSchema,
    raw_cells: Mapping[str, Mapping[str, Any]],
) -> tuple[tuple[dict[str, Any], ...], tuple[str, ...], tuple[dict[str, Any], ...], str, tuple[dict[str, Any], ...]]:
    fields_read: list[dict[str, Any]] = []
    missing: list[str] = []
    formula_blocked: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []

    for target in schema.sheet_target.allowed_cells:
        raw = dict(raw_cells.get(target.cell_ref) or {})
        formula_present = bool(raw.get("formula_present"))
        cached_value_present = bool(raw.get("cached_value_present"))
        blocked = _formula_blocks_target(
            target.formula_policy,
            schema.formula_cached_readback_policy,
            formula_present=formula_present,
            cached_value_present=cached_value_present,
        )
        raw_value = raw.get("value")
        value = raw_value
        if blocked:
            formula_blocked.append(
                {
                    "field_name": target.field_name,
                    "cell_ref": target.cell_ref,
                    "formula_present": True,
                    "cached_value_present": cached_value_present,
                    "workbook_derived_value_reported": raw_value,
                    "reason": "Formula-derived workbook values require deterministic validation, cached-readback policy, recalculation, or operator confirmation before promotion.",
                }
            )
        if target.required and _value_missing(value):
            missing.append(target.field_name)
        value_type_valid, mismatch_reason = _validate_expected_value(
            target.field_name,
            target.expected_value_type,
            value,
        )
        if not _value_missing(value) and not value_type_valid:
            mismatches.append(
                {
                    "field_name": target.field_name,
                    "cell_refs": (target.cell_ref,),
                    "expected_value_type": target.expected_value_type,
                    "actual_value": value,
                    "reason": mismatch_reason,
                }
            )
        if target.required and not value_type_valid:
            missing.append(target.field_name)
        promotion_status = (
            "FORMULA_VALUE_REQUIRES_PROMOTION_POLICY"
            if blocked
            else "VALUE_TYPE_MISMATCH"
            if not value_type_valid and not _value_missing(value)
            else "ACCEPTED_FROM_WHITELISTED_WORKBOOK_CELL"
            if not _value_missing(value)
            else "VALUE_MISSING"
        )
        fields_read.append(
            _field_from_target(
                field_name=target.field_name,
                value=value,
                cell_refs=(target.cell_ref,),
                expected_value_type=target.expected_value_type,
                required=target.required,
                formula_present=formula_present,
                cached_value_present=cached_value_present,
                verified=not blocked and not _value_missing(value) and value_type_valid,
                promotion_status=promotion_status,
                value_type_valid=value_type_valid,
                mismatch_reason=mismatch_reason,
            )
        )

    for target in schema.sheet_target.allowed_columns:
        refs = tuple(ref for ref in (target.header_cell, *target.data_cells) if ref)
        values: list[Any] = []
        formula_present = False
        cached_value_present = False
        blocked = False
        for cell_ref in refs:
            raw = dict(raw_cells.get(cell_ref) or {})
            formula_present = formula_present or bool(raw.get("formula_present"))
            cached_value_present = cached_value_present or bool(raw.get("cached_value_present"))
            cell_blocked = _formula_blocks_target(
                target.formula_policy,
                schema.formula_cached_readback_policy,
                formula_present=bool(raw.get("formula_present")),
                cached_value_present=bool(raw.get("cached_value_present")),
            )
            blocked = blocked or cell_blocked
            values.append(raw.get("value"))
        clean_values = tuple(value for value in values if not _value_missing(value))
        if blocked:
            formula_blocked.append(
                {
                    "field_name": target.field_name,
                    "cell_refs": refs,
                    "formula_present": True,
                    "cached_value_present": cached_value_present,
                    "workbook_derived_value_reported": clean_values,
                    "reason": "Formula-derived workbook values require deterministic validation, cached-readback policy, recalculation, or operator confirmation before promotion.",
                }
            )
        if target.required and not clean_values:
            missing.append(target.field_name)
        value_type_valid, mismatch_reason = _validate_expected_value(
            target.field_name,
            target.expected_value_type,
            clean_values,
        )
        if clean_values and not value_type_valid:
            mismatches.append(
                {
                    "field_name": target.field_name,
                    "cell_refs": refs,
                    "expected_value_type": target.expected_value_type,
                    "actual_value": clean_values,
                    "reason": mismatch_reason,
                }
            )
        if target.required and not value_type_valid:
            missing.append(target.field_name)
        promotion_status = (
            "FORMULA_VALUE_REQUIRES_PROMOTION_POLICY"
            if blocked
            else "VALUE_TYPE_MISMATCH"
            if clean_values and not value_type_valid
            else "ACCEPTED_FROM_WHITELISTED_WORKBOOK_CELL"
            if clean_values
            else "VALUE_MISSING"
        )
        fields_read.append(
            _field_from_target(
                field_name=target.field_name,
                value=clean_values,
                cell_refs=refs,
                expected_value_type=target.expected_value_type,
                required=target.required,
                formula_present=formula_present,
                cached_value_present=cached_value_present,
                verified=not blocked and bool(clean_values) and value_type_valid,
                promotion_status=promotion_status,
                value_type_valid=value_type_valid,
                mismatch_reason=mismatch_reason,
            )
        )

    by_field = {field["field_name"]: field for field in fields_read}
    po_field = by_field.get("coupa_po_reference") or by_field.get("po_reference")
    if po_field and po_field.get("verified") is True and not _value_missing(po_field.get("value")):
        po_status = "PO_REFERENCE_PRESENT_VERIFIED_FROM_WHITELISTED_FIELD"
    elif po_field and po_field.get("formula_present") is True and not _value_missing(po_field.get("value")):
        po_status = "PO_REFERENCE_DERIVED_REQUIRES_PROMOTION_POLICY"
    else:
        po_status = "PO_REFERENCE_MISSING_OR_UNVERIFIED"
        missing_field = str(po_field.get("field_name") or "po_reference") if po_field else "po_reference"
        if po_field and missing_field not in missing:
            missing.append(missing_field)

    conflicts = tuple(mismatches) + _known_fact_conflicts(tuple(fields_read), schema.known_facts)
    return tuple(fields_read), tuple(dict.fromkeys(missing)), tuple(formula_blocked), po_status, conflicts


def _blocked_result(
    *,
    request: ClientInvoiceSheetAuditRequest,
    record: Mapping[str, Any] | None,
    status: str,
    missing_items: tuple[str, ...],
    next_lane: str,
    schema: ClientInvoiceSheetAuditSchema | None,
    path_readable: bool,
) -> ClientInvoiceSheetAuditResult:
    return ClientInvoiceSheetAuditResult(
        result_id=f"sheet_audit_result:{_short_hash(request.source_request_id, status)}",
        status=status,
        client_ref=request.client_ref,
        workflow_ref=request.workflow_ref,
        world_ref=request.world_ref,
        workbook_registry_record_ref=str(record.get("workbook_ref") or "") if record else "",
        workbook_path_ref=request.approved_pc_path_ref or str(record.get("workbook_path_ref") or "") if record else "",
        workbook_path_known_and_approved=bool(request.approved_pc_path_ref),
        path_pc_readable=path_readable,
        schema_explicit=schema is not None,
        sheet_audited=schema.sheet_target.sheet_name if schema else "",
        whitelist_used=_target_descriptors(schema) if schema else (),
        fields_read=(),
        fields_missing=missing_items,
        fields_blocked_due_to_formula=(),
        conflicts_vs_known_facts=(),
        po_reference_status="PO_REFERENCE_MISSING_OR_UNVERIFIED",
        body_ingested=False,
        arbitrary_parse=False,
        inferred_schema=False,
        full_sheet_dump=False,
        formula_evaluated=False,
        macro_processed=False,
        external_links_followed=False,
        external_action=False,
        next_recommended_lane=next_lane,
    )


def _status_from_findings(
    *,
    fields_missing: tuple[str, ...],
    formula_blocked: tuple[dict[str, Any], ...],
    po_reference_status: str,
) -> str:
    if formula_blocked:
        return "SHEET_AUDIT_FORMULA_CONFIRMATION_REQUIRED"
    if fields_missing:
        return "SHEET_AUDIT_REQUIRED_FIELD_MISSING"
    if po_reference_status == "PO_REFERENCE_MISSING_OR_UNVERIFIED":
        return "SHEET_AUDIT_REQUIRED_FIELD_MISSING"
    return "SHEET_AUDIT_COMPLETE"


def _next_lane_for_result(status: str, po_reference_status: str) -> str:
    if status == "SHEET_AUDIT_COMPLETE" and po_reference_status.startswith("PO_REFERENCE_PRESENT"):
        return "Next: prepare the local invoice artifact."
    if status == "SHEET_AUDIT_REQUIRED_FIELD_MISSING" and po_reference_status == "PO_REFERENCE_MISSING_OR_UNVERIFIED":
        return "Next: confirm the Coupa PO/reference."
    if status == "SHEET_AUDIT_FORMULA_CONFIRMATION_REQUIRED":
        return "Next: confirm formula-derived values or approve a promotion policy."
    return "Next: fix the invoice sheet fields listed below."


def run_audit(
    raw_request: Mapping[str, Any],
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    registry_payload = load_registry_payload(export_root)
    request, schema, record, approved_path, path_readable = normalize_audit_request(
        raw_request,
        registry_payload=registry_payload,
        export_root=export_root,
    )
    if request.validation_status != "READY_TO_AUDIT":
        result = _blocked_result(
            request=request,
            record=record,
            status=request.validation_status,
            missing_items=request.missing_context,
            next_lane=request.next_safe_move,
            schema=schema,
            path_readable=path_readable,
        )
        readback = _readback_for_result(request, result, record)
        return _build_payload(
            generated_at=generated_at,
            request=request,
            schema=schema,
            result=result,
            readback=readback,
            registry_record=record,
            workbook_opened=False,
            whitelisted_cells_read=False,
        )

    assert schema is not None
    assert approved_path is not None
    workbook_opened = False
    whitelisted_cells_read = False
    try:
        raw_cells, workbook_flags = _read_whitelisted_cells(approved_path, schema)
        workbook_opened = True
        whitelisted_cells_read = True
    except KeyError:
        result = _blocked_result(
            request=request,
            record=record,
            status="SHEET_AUDIT_SHEET_MISSING",
            missing_items=("confirmed sheet name",),
            next_lane="Next: confirm the invoice sheet/schema mapping.",
            schema=schema,
            path_readable=path_readable,
        )
        readback = _readback_for_result(request, result, record)
        return _build_payload(
            generated_at=generated_at,
            request=request,
            schema=schema,
            result=result,
            readback=readback,
            registry_record=record,
            workbook_opened=workbook_opened,
            whitelisted_cells_read=whitelisted_cells_read,
        )
    except (ValueError, zipfile.BadZipFile, OSError):
        result = _blocked_result(
            request=request,
            record=record,
            status="SHEET_AUDIT_UNSUPPORTED_WORKBOOK_FORMAT",
            missing_items=("supported .xlsx or .csv fixture workbook",),
            next_lane="Next: provide a supported approved workbook handoff.",
            schema=schema,
            path_readable=path_readable,
        )
        readback = _readback_for_result(request, result, record)
        return _build_payload(
            generated_at=generated_at,
            request=request,
            schema=schema,
            result=result,
            readback=readback,
            registry_record=record,
            workbook_opened=workbook_opened,
            whitelisted_cells_read=whitelisted_cells_read,
        )

    fields_read, fields_missing, formula_blocked, po_status, conflicts = _evaluate_whitelist(schema, raw_cells)
    status = _status_from_findings(
        fields_missing=fields_missing,
        formula_blocked=formula_blocked,
        po_reference_status=po_status,
    )
    next_lane = _next_lane_for_result(status, po_status)
    result = ClientInvoiceSheetAuditResult(
        result_id=f"sheet_audit_result:{_short_hash(request.source_request_id, status)}",
        status=status,
        client_ref=request.client_ref,
        workflow_ref=request.workflow_ref,
        world_ref=request.world_ref,
        workbook_registry_record_ref=str(record.get("workbook_ref") or "") if record else "",
        workbook_path_ref=request.approved_pc_path_ref,
        workbook_path_known_and_approved=True,
        path_pc_readable=path_readable,
        schema_explicit=True,
        sheet_audited=schema.sheet_target.sheet_name,
        whitelist_used=_target_descriptors(schema),
        fields_read=fields_read,
        fields_missing=fields_missing,
        fields_blocked_due_to_formula=formula_blocked,
        conflicts_vs_known_facts=conflicts,
        po_reference_status=po_status,
        body_ingested=False,
        arbitrary_parse=False,
        inferred_schema=False,
        full_sheet_dump=False,
        formula_evaluated=False,
        macro_processed=bool(workbook_flags.get("macro_present")) and False,
        external_links_followed=bool(workbook_flags.get("external_links_present")) and False,
        external_action=False,
        next_recommended_lane=next_lane,
    )
    readback = _readback_for_result(request, result, record)
    return _build_payload(
        generated_at=generated_at,
        request=request,
        schema=schema,
        result=result,
        readback=readback,
        registry_record=record,
        workbook_opened=workbook_opened,
        whitelisted_cells_read=whitelisted_cells_read,
    )


def _readback_for_result(
    request: ClientInvoiceSheetAuditRequest,
    result: ClientInvoiceSheetAuditResult,
    record: Mapping[str, Any] | None,
) -> ClientInvoiceSheetAuditReadback:
    client_name = "Capital Hilton" if request.client_ref == "capital_hilton" else request.client_ref.replace("_", " ").title()
    hidden_refs = {
        "source_request_id": request.source_request_id,
        "workbook_ref": result.workbook_registry_record_ref,
        "approved_pc_path_ref": request.approved_pc_path_ref,
        "schema_ref": request.schema_ref,
    }
    if result.status == "SHEET_AUDIT_COMPLETE":
        headline = f"{client_name} invoice sheet audited"
        message = (
            "OpenClaw checked only the approved invoice sheet fields. "
            "It did not ingest the workbook body or parse the full spreadsheet."
        )
        next_action = result.next_recommended_lane
    elif result.status == "SHEET_AUDIT_NO_WORKBOOK_REGISTERED":
        headline = "Register the workbook first"
        message = "OpenClaw cannot audit the invoice sheet because no registered workbook is available for this client/workflow."
        next_action = "Next: Register or capture the Capital Hilton invoice workbook first."
    elif result.status == "SHEET_AUDIT_SCHEMA_MISSING":
        headline = "Sheet schema needed"
        message = "OpenClaw has a workbook reference, but I need the explicit sheet/schema mapping before reading any cells."
        next_action = "Next: Confirm the invoice sheet/schema mapping."
    elif result.status == "APPROVED_PC_PATH_REQUIRED":
        headline = "PC-readable workbook needed"
        message = "OpenClaw has a workbook reference, but it is not an approved PC-readable path. I did not guess a Mac-to-PC path."
        next_action = "Next: Provide an approved PC-readable workbook path or handoff."
    elif result.status == "SHEET_AUDIT_WORKBOOK_PATH_MISSING":
        headline = "Workbook path needed"
        message = "OpenClaw has the registry context, but no approved readable workbook path was provided for this audit."
        next_action = "Next: Provide an approved PC-readable workbook path or handoff."
    elif result.status == "SHEET_AUDIT_SHEET_MISSING":
        headline = "Invoice sheet not found"
        message = "OpenClaw could not find the confirmed sheet name in the approved workbook. No layout inference was attempted."
        next_action = "Next: Confirm the invoice sheet/schema mapping."
    elif result.status == "SHEET_AUDIT_FORMULA_CONFIRMATION_REQUIRED":
        headline = "Formula confirmation needed"
        message = "OpenClaw found a formula-derived workbook value in a whitelisted field. It reported the workbook value but did not promote it as accepted truth."
        next_action = "Next: confirm formula-derived values or approve a promotion policy."
    elif result.status == "SHEET_AUDIT_REQUIRED_FIELD_MISSING":
        headline = "Invoice sheet needs fixes"
        message = (
            "OpenClaw checked only the approved invoice sheet fields. "
            "One or more required fields are missing or unverified."
        )
        next_action = result.next_recommended_lane
    elif result.status == "SHEET_AUDIT_CONTEXT_MISSING":
        headline = "Which workflow is this for?"
        message = "OpenClaw needs explicit client, workflow, and finance world context before auditing an invoice sheet."
        next_action = "Next: Confirm the client, workflow, and world for this sheet audit."
    else:
        headline = "Sheet audit blocked"
        message = "OpenClaw could not safely audit this workbook with the current bounded rail."
        next_action = result.next_recommended_lane
    return ClientInvoiceSheetAuditReadback(
        readback_id=f"sheet_audit_readback:{_short_hash(request.source_request_id, result.status)}",
        status=result.status,
        operator_headline=headline,
        operator_message=message,
        client_summary=f"{client_name} / {request.workflow_ref}",
        workbook_summary=str(record.get("workbook_display_name") or "No workbook record") if record else "No workbook record",
        missing_items=result.fields_missing,
        next_action=next_action,
        hidden_refs=hidden_refs,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move=next_action,
    )


def _example_request() -> dict[str, Any]:
    return {
        "request_id": "mission_control_chat_request_capital_hilton_sheet_audit_fixture",
        "workflow_ref": "capital_hilton_invoice_workflow",
        "world_ref": "finance",
        "client_ref": "capital_hilton",
        "operator_goal": "Audit the Capital Hilton invoice sheet.",
        "operator_message": "Audit the Capital Hilton invoice sheet.",
        "sanitized_message_summary": "Audit the Capital Hilton invoice sheet.",
        "intended_use": INTENDED_USE,
        "approved_pc_workbook_path_authorized": False,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _build_payload(
    *,
    generated_at: str,
    request: ClientInvoiceSheetAuditRequest,
    schema: ClientInvoiceSheetAuditSchema | None,
    result: ClientInvoiceSheetAuditResult,
    readback: ClientInvoiceSheetAuditReadback,
    registry_record: Mapping[str, Any] | None,
    workbook_opened: bool,
    whitelisted_cells_read: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "audit_statuses": AUDIT_STATUSES,
        "model_schemas": {
            "ClientInvoiceSheetAuditRequest": tuple(field.name for field in fields(ClientInvoiceSheetAuditRequest)),
            "ClientInvoiceSheetAuditSchema": tuple(field.name for field in fields(ClientInvoiceSheetAuditSchema)),
            "WhitelistedSheetTarget": tuple(field.name for field in fields(WhitelistedSheetTarget)),
            "WhitelistedCellTarget": tuple(field.name for field in fields(WhitelistedCellTarget)),
            "WhitelistedColumnTarget": tuple(field.name for field in fields(WhitelistedColumnTarget)),
            "ClientInvoiceSheetAuditResult": tuple(field.name for field in fields(ClientInvoiceSheetAuditResult)),
            "ClientInvoiceSheetAuditReadback": tuple(field.name for field in fields(ClientInvoiceSheetAuditReadback)),
        },
        "audit_request": asdict(request),
        "audit_schema": asdict(schema) if schema else None,
        "audit_result": asdict(result),
        "audit_readback": asdict(readback),
        "workbook_registry_record_ref": result.workbook_registry_record_ref,
        "registry_record_snapshot": {
            "client_ref": registry_record.get("client_ref"),
            "workflow_ref": registry_record.get("workflow_ref"),
            "workbook_ref": registry_record.get("workbook_ref"),
            "workbook_display_name": registry_record.get("workbook_display_name"),
            "workbook_path_ref": registry_record.get("workbook_path_ref"),
            "approved_for_metadata_read": registry_record.get("approved_for_metadata_read"),
            "approved_for_cell_read": registry_record.get("approved_for_cell_read"),
        }
        if registry_record
        else None,
        "examples": {
            "blocked_default": {
                "intended_use": INTENDED_USE,
                "client_ref": "capital_hilton",
                "workflow_ref": "capital_hilton_invoice_workflow",
                "world_ref": "finance",
                "requires": (
                    "registered workbook",
                    "approved PC-readable workbook path",
                    "explicit sheet/schema mapping",
                ),
            }
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "workbook_registry_readmodel_read": True,
            "approved_workbook_registry_record_required": True,
            "approved_pc_readable_path_required": True,
            "explicit_schema_required": True,
            "fixture_workbook_reads_are_test_only": True,
            "live_capital_hilton_requires_approved_business_workbook_path": True,
            "capital_hilton_bound_only_with_explicit_context": request.client_ref == "capital_hilton"
            and request.workflow_ref == "capital_hilton_invoice_workflow"
            and request.world_ref == "finance",
            "schema_explicit": result.schema_explicit,
            "path_pc_readable": result.path_pc_readable,
            "workbook_opened": workbook_opened,
            "whitelisted_cells_read": whitelisted_cells_read,
            "whitelisted_cells_requested_count": len(result.whitelist_used),
            "fields_read_count": len(result.fields_read),
            "body_ingested": False,
            "arbitrary_parse": False,
            "inferred_schema": False,
            "full_workbook_ingestion_performed": False,
            "full_sheet_dump": False,
            "formula_evaluated": False,
            "macro_processed": False,
            "external_links_followed": False,
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
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": "",
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def build_payload(*, export_root: Path = DEFAULT_EXPORT_ROOT, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    return run_audit(_example_request(), export_root=export_root, generated_at=generated_at)


def format_operator_markdown(payload: Mapping[str, Any]) -> str:
    readback = payload.get("audit_readback") if isinstance(payload.get("audit_readback"), Mapping) else {}
    result = payload.get("audit_result") if isinstance(payload.get("audit_result"), Mapping) else {}
    lines = [
        "# Client Invoice Sheet Audit",
        "",
        "ELIOPERATOR: Whitelisted invoice sheet audit. No arbitrary workbook parsing, inferred schema, full workbook ingestion, full sheet dump, formula evaluation, macros, external links, browser, Coupa, PDF, email, or external systems were touched.",
        "",
        f"- Status: `{readback.get('status', 'UNKNOWN')}`",
        f"- Client: `{result.get('client_ref', 'unknown')}`",
        f"- Workflow: `{result.get('workflow_ref', 'unknown')}`",
        f"- Sheet audited: `{result.get('sheet_audited', '')}`",
        f"- Fields read: `{len(result.get('fields_read') or [])}`",
        f"- PO/reference status: `{result.get('po_reference_status', 'UNKNOWN')}`",
        "",
        f"## {readback.get('operator_headline', 'Sheet audit')}",
        "",
        str(readback.get("operator_message") or "No sheet audit request was processed."),
        "",
        "## Next",
        "",
        str(readback.get("next_action") or result.get("next_recommended_lane") or "Wait for an approved sheet audit request."),
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
    readback = payload.get("audit_readback") if isinstance(payload.get("audit_readback"), Mapping) else {}
    result = payload.get("audit_result") if isinstance(payload.get("audit_result"), Mapping) else {}
    proof = payload.get("machine_proof") if isinstance(payload.get("machine_proof"), Mapping) else {}
    return {
        "read_model_id": payload.get("read_model_id"),
        "contract_status": payload.get("contract_status"),
        "json_path": paths[0].as_posix(),
        "operator_path": paths[1].as_posix(),
        "status": readback.get("status"),
        "operator_headline": readback.get("operator_headline"),
        "next_action": readback.get("next_action"),
        "client_ref": result.get("client_ref"),
        "workflow_ref": result.get("workflow_ref"),
        "sheet_audited": result.get("sheet_audited"),
        "path_pc_readable": result.get("path_pc_readable"),
        "schema_explicit": result.get("schema_explicit"),
        "fields_read_count": len(result.get("fields_read") or ()),
        "po_reference_status": result.get("po_reference_status"),
        "all_live_authority_false": proof.get("all_live_authority_false"),
        "content_hash": proof.get("content_hash"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the client invoice sheet audit read-model.")
    parser.add_argument("--format", choices=("json", "summary"), default="json")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    args = parser.parse_args(argv)

    export_root = Path(args.export_root)
    payload = build_payload(export_root=export_root, generated_at=args.generated_at)
    paths = write_exports(payload, export_root)
    output: Mapping[str, Any] = payload if args.format == "json" else build_summary(payload, paths)
    sys.stdout.write(stable_json(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
