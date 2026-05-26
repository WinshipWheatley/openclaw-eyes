"""Client invoice audit handoff contract v0.

This rail records operator-provided workbook path approval and explicit invoice
sheet schema mapping. It prepares the whitelisted sheet audit lane without
opening workbooks, reading cells, inferring schema, translating Mac paths, or
performing external actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import client_invoice_workbook_registry
import local_artifact_reference


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "client_invoice_audit_handoff_v0"
READ_MODEL_ID = "client_invoice_audit_handoff"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_CLIENT_INVOICE_AUDIT_HANDOFF_CONTRACT_NO_WORKBOOK_READ"

INTENDED_USE = "client_invoice_audit_handoff"
PATH_APPROVAL_INTENDED_USE = "client_invoice_workbook_path_approval"
SCHEMA_MAPPING_INTENDED_USE = "client_invoice_sheet_schema_mapping"
ACCEPTED_INTENDED_USES = (INTENDED_USE, PATH_APPROVAL_INTENDED_USE, SCHEMA_MAPPING_INTENDED_USE)

PATH_STATUSES = (
    "APPROVED_PC_PATH_CAPTURED",
    "APPROVED_PC_PATH_REQUIRED",
    "APPROVED_PC_PATH_REJECTED_MAC_VISIBLE",
    "WORKBOOK_REGISTRY_REQUIRED",
    "HANDOFF_CONTEXT_MISSING",
    "NO_PATH_REQUESTED",
    "UNKNOWN_FAIL_CLOSED",
)

SCHEMA_STATUSES = (
    "SHEET_AUDIT_SCHEMA_CAPTURED",
    "SHEET_AUDIT_SCHEMA_MISSING",
    "SHEET_AUDIT_SCHEMA_INCOMPLETE",
    "HANDOFF_CONTEXT_MISSING",
    "NO_SCHEMA_REQUESTED",
    "LOCAL_SURFACE_RESULT_UNCONFIRMED",
    "LOCAL_SURFACE_RESULT_UNSAFE_FLAGS",
    "LOCAL_SURFACE_RESULT_BLOCKED",
    "UNKNOWN_FAIL_CLOSED",
)

READBACK_STATUSES = (
    "HANDOFF_READY_FOR_SHEET_AUDIT",
    "APPROVED_PC_PATH_CAPTURED_SCHEMA_REQUIRED",
    "SCHEMA_MAPPING_CAPTURED_PATH_REQUIRED",
    "APPROVED_PC_PATH_REQUIRED",
    "SHEET_AUDIT_SCHEMA_MISSING",
    "SHEET_AUDIT_SCHEMA_INCOMPLETE",
    "WORKBOOK_REGISTRY_REQUIRED",
    "HANDOFF_CONTEXT_MISSING",
    "LOCAL_SURFACE_RESULT_UNCONFIRMED",
    "LOCAL_SURFACE_RESULT_UNSAFE_FLAGS",
    "LOCAL_SURFACE_RESULT_BLOCKED",
    "UNKNOWN_FAIL_CLOSED",
)

FORMULA_POLICY_STATES = (
    "operator_confirmation_required",
    "deterministic_recalculation_required",
    "cached_readback_allowed_only_if_explicit",
    "formula_values_not_promoted",
)

REQUIRED_SEMANTIC_FIELDS = (
    "invoice_number",
    "performance_dates",
    "rate",
    "subtotal_or_total",
    "po_reference",
)

LOCAL_SURFACE_RESULT_KIND = "LOCAL_SURFACE_RESULT"

LOCAL_SURFACE_RESULT_FALSE_FLAGS = (
    "body_read",
    "workbook_body_read",
    "spreadsheet_cell_read",
    "ocr_performed",
    "external_llm_shared",
    "external_action",
    "path_translation_guessed",
)

OPTIONAL_SEMANTIC_FIELDS = (
    "notes_status",
)

AUTHORITY_BOUNDARY = {
    "live_workbook_parse_allowed": False,
    "live_spreadsheet_cell_read_allowed": False,
    "live_schema_inference_allowed": False,
    "live_mac_path_translation_allowed": False,
    "live_formula_evaluation_allowed": False,
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


@dataclass(frozen=True)
class FormulaPromotionPolicy:
    policy_id: str
    selected_policy: str
    allowed_policy_states: tuple[str, ...]
    operator_confirmation_required: bool
    deterministic_recalculation_required: bool
    cached_readback_allowed_only_if_explicit: bool
    formula_values_not_promoted: bool
    formula_evaluation_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class ApprovedWorkbookPathRef:
    path_ref_id: str
    client_ref: str
    workflow_ref: str
    world_ref: str
    workbook_ref: str
    approved_pc_readable_path: str
    approved_path_ref: str
    path_kind: str
    path_approval_status: str
    operator_approval_marker: str
    source_request_id: str
    mac_visible_path_rejected: bool
    path_translation_guessed: bool
    workbook_body_read: bool
    next_safe_move: str


@dataclass(frozen=True)
class ClientInvoiceSheetSchemaMapping:
    schema_mapping_id: str
    client_ref: str
    workflow_ref: str
    world_ref: str
    sheet_name: str
    whitelisted_cells: tuple[dict[str, Any], ...]
    whitelisted_columns: tuple[dict[str, Any], ...]
    semantic_fields_present: tuple[str, ...]
    semantic_fields_missing: tuple[str, ...]
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...]
    expected_value_types: dict[str, str]
    formula_promotion_policy: dict[str, Any]
    schema_mapping_status: str
    source_request_id: str
    inferred_schema: bool
    workbook_layout_inspected: bool
    next_safe_move: str


@dataclass(frozen=True)
class ClientInvoiceWorkbookPathApprovalRequest:
    request_id: str
    source_request_id: str
    intended_use: str
    client_ref: str
    workflow_ref: str
    world_ref: str
    workbook_ref: str
    workbook_identity: str
    approved_pc_readable_path: str
    approved_path_ref: str
    operator_approval_marker: str
    authority_boundary: dict[str, bool]
    validation_status: str
    missing_context: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class ClientInvoiceSheetSchemaMappingRequest:
    request_id: str
    source_request_id: str
    intended_use: str
    client_ref: str
    workflow_ref: str
    world_ref: str
    sheet_name: str
    schema_ref: str
    formula_promotion_policy: str
    authority_boundary: dict[str, bool]
    validation_status: str
    missing_context: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class ClientInvoiceAuditHandoffReadback:
    readback_id: str
    status: str
    operator_headline: str
    operator_message: str
    path_approval_status: str
    schema_mapping_status: str
    formula_policy_status: str
    live_audit_ready: bool
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


def is_audit_handoff_request(raw_request: Mapping[str, Any]) -> bool:
    return str(raw_request.get("intended_use") or "").strip() in ACCEPTED_INTENDED_USES


def _local_surface_result_kind(raw_request: Mapping[str, Any]) -> str:
    for key in ("kind", "type", "request_type", "result_type"):
        value = str(raw_request.get(key) or "").strip().upper()
        if value:
            return value
    return ""


def is_local_surface_schema_mapping_result(raw_request: Mapping[str, Any]) -> bool:
    return (
        _local_surface_result_kind(raw_request) == LOCAL_SURFACE_RESULT_KIND
        and str(raw_request.get("intended_use") or "").strip() == SCHEMA_MAPPING_INTENDED_USE
    )


def _safe_text(value: object, fallback: str = "unknown") -> str:
    text = str(value or "").strip()
    return text or fallback


def _safe_field_name(value: object) -> str:
    text = str(value or "").strip().lower()
    cleaned = "".join(char if char.isalnum() else "_" for char in text).strip("_")
    aliases = {
        "coupa_po_reference": "po_reference",
        "po": "po_reference",
        "po_ref": "po_reference",
        "po_reference": "po_reference",
        "total": "subtotal_or_total",
        "subtotal": "subtotal_or_total",
        "subtotal_total": "subtotal_or_total",
        "subtotal_or_total": "subtotal_or_total",
        "notes": "notes_status",
        "status": "notes_status",
        "notes_status": "notes_status",
    }
    return aliases.get(cleaned, cleaned or "unknown_field")


def _safe_cell_ref(value: object) -> str:
    text = str(value or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{1,3}[1-9][0-9]{0,6}", text):
        return ""
    return text


def _split_cell_ref(cell_ref: str) -> tuple[str, int] | None:
    match = re.fullmatch(r"([A-Z]{1,3})([1-9][0-9]{0,6})", cell_ref)
    if not match:
        return None
    return match.group(1), int(match.group(2))


def _safe_cell_range(value: object) -> tuple[str, ...]:
    text = str(value or "").strip().upper()
    if ":" not in text:
        cell = _safe_cell_ref(text)
        return (cell,) if cell else ()
    start_raw, end_raw = (part.strip() for part in text.split(":", 1))
    start = _safe_cell_ref(start_raw)
    end = _safe_cell_ref(end_raw)
    parsed_start = _split_cell_ref(start)
    parsed_end = _split_cell_ref(end)
    if not parsed_start or not parsed_end:
        return ()
    start_col, start_row = parsed_start
    end_col, end_row = parsed_end
    if start_col != end_col or end_row < start_row or (end_row - start_row) > 200:
        return ()
    return tuple(f"{start_col}{row}" for row in range(start_row, end_row + 1))


def _is_unknown(value: object) -> bool:
    return str(value or "").strip() in {"", "unknown", "UNKNOWN", "none", "None"}


def _mac_visible_path(value: object) -> bool:
    text = str(value or "").strip()
    lowered = text.lower()
    return (
        text.startswith("/Volumes/")
        or text.startswith("/Users/")
        or text.startswith("~/")
        or lowered.startswith("mac_path_ref:")
        or lowered.startswith("mac_visible_path_ref:")
        or "/volumes/" in lowered
        or "/users/" in lowered
    )


def _approval_marker(raw_request: Mapping[str, Any]) -> str:
    marker = str(
        raw_request.get("operator_approval_marker")
        or raw_request.get("path_approval_source_marker")
        or raw_request.get("approval_source")
        or ""
    ).strip()
    if marker:
        return marker[:160]
    if raw_request.get("operator_approved") is True:
        return "operator_approved:true"
    if raw_request.get("approved_pc_workbook_path_authorized") is True:
        return "approved_pc_workbook_path_authorized:true"
    if raw_request.get("approved_by_operator") is True:
        return "approved_by_operator:true"
    return ""


def _context_values(raw_request: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(raw_request.get("client_ref") or "unknown").strip(),
        str(raw_request.get("workflow_ref") or "unknown").strip(),
        str(raw_request.get("world_ref") or "unknown").strip(),
    )


def _context_missing(client_ref: str, workflow_ref: str, world_ref: str) -> tuple[str, ...]:
    missing = []
    if _is_unknown(client_ref):
        missing.append("client_ref")
    if _is_unknown(workflow_ref):
        missing.append("workflow_ref")
    if _is_unknown(world_ref):
        missing.append("world_ref")
    if client_ref == "capital_hilton" and workflow_ref != "capital_hilton_invoice_workflow":
        missing.append("capital_hilton_invoice_workflow")
    if client_ref == "capital_hilton" and world_ref != "finance":
        missing.append("finance_world_ref")
    return tuple(missing)


def load_workbook_registry(export_root: Path = DEFAULT_EXPORT_ROOT) -> dict[str, Any] | None:
    return client_invoice_workbook_registry.load_existing_payload(export_root)


def _registry_records(payload: Mapping[str, Any] | None) -> tuple[dict[str, Any], ...]:
    if not isinstance(payload, Mapping):
        return ()
    registry = payload.get("registry") if isinstance(payload.get("registry"), Mapping) else {}
    records = registry.get("client_records") if isinstance(registry.get("client_records"), list) else []
    return tuple(dict(record) for record in records if isinstance(record, Mapping))


def _matching_workbook_record(
    registry_payload: Mapping[str, Any] | None,
    *,
    client_ref: str,
    workflow_ref: str,
    workbook_ref: str = "",
) -> dict[str, Any] | None:
    for record in _registry_records(registry_payload):
        if record.get("client_ref") != client_ref or record.get("workflow_ref") != workflow_ref:
            continue
        if workbook_ref and record.get("workbook_ref") != workbook_ref:
            continue
        return record
    return None


def load_existing_payload(export_root: Path = DEFAULT_EXPORT_ROOT) -> dict[str, Any] | None:
    path = Path(export_root) / JSON_EXPORT_NAME
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _fixture_source_id(value: object) -> bool:
    return "fixture" in str(value or "").lower()


def _existing_path_ref(
    existing_payload: Mapping[str, Any] | None,
    *,
    client_ref: str,
    workflow_ref: str,
    world_ref: str,
    source_request_id: str = "",
) -> dict[str, Any] | None:
    if not isinstance(existing_payload, Mapping):
        return None
    path_ref = existing_payload.get("approved_workbook_path_ref")
    if not isinstance(path_ref, Mapping):
        return None
    if (
        path_ref.get("client_ref") == client_ref
        and path_ref.get("workflow_ref") == workflow_ref
        and path_ref.get("world_ref") == world_ref
        and path_ref.get("path_approval_status") == "APPROVED_PC_PATH_CAPTURED"
    ):
        if _fixture_source_id(path_ref.get("source_request_id")) and not _fixture_source_id(source_request_id):
            return None
        return dict(path_ref)
    return None


def _existing_schema(
    existing_payload: Mapping[str, Any] | None,
    *,
    client_ref: str,
    workflow_ref: str,
    world_ref: str,
) -> dict[str, Any] | None:
    if not isinstance(existing_payload, Mapping):
        return None
    mapping = existing_payload.get("schema_mapping")
    if not isinstance(mapping, Mapping):
        return None
    if (
        mapping.get("client_ref") == client_ref
        and mapping.get("workflow_ref") == workflow_ref
        and mapping.get("world_ref") == world_ref
        and mapping.get("schema_mapping_status") == "SHEET_AUDIT_SCHEMA_CAPTURED"
    ):
        return dict(mapping)
    return None


def _path_request_has_artifact_signal(raw_request: Mapping[str, Any]) -> bool:
    intended_use = str(raw_request.get("intended_use") or "")
    if intended_use in {INTENDED_USE, PATH_APPROVAL_INTENDED_USE}:
        return True
    return bool(
        raw_request.get("approved_pc_readable_path")
        or raw_request.get("approved_pc_workbook_path")
        or raw_request.get("approved_path_ref")
        or raw_request.get("approved_pc_workbook_path_ref")
        or raw_request.get("artifact_ref")
    )


def _artifact_request_from_handoff(
    raw_request: Mapping[str, Any],
    *,
    workbook_record: Mapping[str, Any] | None,
    path_request: ClientInvoiceWorkbookPathApprovalRequest,
) -> dict[str, Any]:
    artifact_request = dict(raw_request)
    workbook_ref = (
        str(path_request.workbook_ref or "")
        or str(path_request.workbook_identity or "")
        or str((workbook_record or {}).get("workbook_ref") or "")
    )
    if workbook_ref:
        artifact_request.setdefault("artifact_ref", workbook_ref)
    artifact_request.setdefault("artifact_kind", "invoice_workbook")
    artifact_request.setdefault("artifact_label", str((workbook_record or {}).get("workbook_display_name") or "client invoice workbook"))
    artifact_request["artifact_intended_use"] = "client_invoice_sheet_audit"
    artifact_request.setdefault("approved_for_write", False)
    artifact_request.setdefault("body_read", False)
    artifact_request.setdefault("content_extracted", False)
    artifact_request.setdefault("external_shared", False)
    return artifact_request


def _matching_artifact_from_payload(
    payload: Mapping[str, Any] | None,
    *,
    client_ref: str,
    workflow_ref: str,
    world_ref: str,
    source_request_id: str,
) -> dict[str, Any] | None:
    artifact = None
    for artifact_kind in ("invoice_workbook", "spreadsheet_workbook"):
        artifact = local_artifact_reference.find_approved_readable_artifact(
            payload,
            world_ref=world_ref,
            workflow_ref=workflow_ref,
            client_ref=client_ref,
            artifact_kind=artifact_kind,
            intended_use="client_invoice_sheet_audit",
        )
        if artifact is not None:
            break
    if artifact and _fixture_source_id(artifact.get("source_request_id")) and not _fixture_source_id(source_request_id):
        return None
    return artifact


def _artifact_payload_from_existing_handoff(existing_payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(existing_payload, Mapping):
        return None
    payload = existing_payload.get("local_artifact_reference_payload")
    return dict(payload) if isinstance(payload, Mapping) else None


def _path_ref_from_artifact(artifact: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(artifact, Mapping):
        return None
    scope = artifact.get("scope_binding") if isinstance(artifact.get("scope_binding"), Mapping) else {}
    pc_path = str(artifact.get("pc_path") or "")
    path_ref = str(artifact.get("approved_path_ref") or "")
    return {
        "path_ref_id": f"approved_workbook_path_ref:{_short_hash(artifact.get('artifact_ref'), pc_path, path_ref)}",
        "client_ref": str(scope.get("client_ref") or ""),
        "workflow_ref": str(scope.get("workflow_ref") or ""),
        "world_ref": str(scope.get("world_ref") or ""),
        "workbook_ref": str(artifact.get("artifact_ref") or ""),
        "approved_pc_readable_path": pc_path,
        "approved_path_ref": path_ref,
        "path_kind": "PC_LOCAL_PATH" if pc_path else "APPROVED_PC_PATH_REF",
        "path_approval_status": "APPROVED_PC_PATH_CAPTURED",
        "operator_approval_marker": str(artifact.get("approval_source") or "approved_readable_artifact"),
        "source_request_id": str(artifact.get("source_request_id") or ""),
        "mac_visible_path_rejected": False,
        "path_translation_guessed": False,
        "workbook_body_read": False,
        "next_safe_move": "Next: provide the invoice tab name and cell mapping.",
    }


def _formula_policy(raw_policy: object) -> FormulaPromotionPolicy:
    if isinstance(raw_policy, Mapping):
        selected = str(raw_policy.get("selected_policy") or raw_policy.get("policy") or "").strip()
    else:
        selected = str(raw_policy or "").strip()
    if selected not in FORMULA_POLICY_STATES:
        selected = "operator_confirmation_required"
    return FormulaPromotionPolicy(
        policy_id=f"formula_promotion_policy:{_short_hash(selected)}",
        selected_policy=selected,
        allowed_policy_states=FORMULA_POLICY_STATES,
        operator_confirmation_required=selected == "operator_confirmation_required",
        deterministic_recalculation_required=selected == "deterministic_recalculation_required",
        cached_readback_allowed_only_if_explicit=selected == "cached_readback_allowed_only_if_explicit",
        formula_values_not_promoted=selected in {"operator_confirmation_required", "formula_values_not_promoted"},
        formula_evaluation_allowed=False,
        next_safe_move="Treat formula cells as derived workbook values until a promotion policy clears them.",
    )


def _raw_path_value(raw_request: Mapping[str, Any]) -> tuple[str, str]:
    path = str(
        raw_request.get("approved_pc_readable_path")
        or raw_request.get("approved_pc_workbook_path")
        or raw_request.get("approved_local_workbook_path")
        or ""
    ).strip()
    ref = str(
        raw_request.get("approved_path_ref")
        or raw_request.get("approved_pc_workbook_path_ref")
        or raw_request.get("approved_pc_readable_path_ref")
        or ""
    ).strip()
    return path, ref


def _path_kind(path: str, path_ref: str) -> str:
    if path:
        return "PC_LOCAL_PATH"
    if path_ref:
        return "APPROVED_PC_PATH_REF"
    return "NO_PATH"


def normalize_path_approval_request(
    raw_request: Mapping[str, Any],
    *,
    registry_payload: Mapping[str, Any] | None,
) -> tuple[ClientInvoiceWorkbookPathApprovalRequest, ApprovedWorkbookPathRef | None, dict[str, Any] | None]:
    source_request_id = str(raw_request.get("request_id") or "unknown_audit_handoff_request")
    client_ref, workflow_ref, world_ref = _context_values(raw_request)
    workbook_ref = str(raw_request.get("workbook_ref") or raw_request.get("workbook_registry_ref") or "").strip()
    workbook_identity = str(raw_request.get("workbook_identity") or workbook_ref or "").strip()
    record = _matching_workbook_record(
        registry_payload,
        client_ref=client_ref,
        workflow_ref=workflow_ref,
        workbook_ref=workbook_ref,
    )
    if record and not workbook_ref:
        workbook_ref = str(record.get("workbook_ref") or "")
        workbook_identity = workbook_identity or workbook_ref
    approved_path, approved_ref = _raw_path_value(raw_request)
    marker = _approval_marker(raw_request)
    missing = list(_context_missing(client_ref, workflow_ref, world_ref))
    status = "NO_PATH_REQUESTED"
    next_move = "Next: provide approved PC-readable workbook access."
    path_ref: ApprovedWorkbookPathRef | None = None

    intended_use = str(raw_request.get("intended_use") or "")
    path_requested = intended_use in {INTENDED_USE, PATH_APPROVAL_INTENDED_USE} and bool(approved_path or approved_ref or marker)
    if intended_use == SCHEMA_MAPPING_INTENDED_USE and not approved_path and not approved_ref:
        status = "NO_PATH_REQUESTED"
    elif missing:
        status = "HANDOFF_CONTEXT_MISSING"
        next_move = "Next: confirm the client, workflow, and world."
    elif record is None and not workbook_identity:
        status = "WORKBOOK_REGISTRY_REQUIRED"
        missing.append("workbook registry ref or workbook identity")
        next_move = "Next: register or identify the workbook first."
    elif _mac_visible_path(approved_path) or _mac_visible_path(approved_ref):
        status = "APPROVED_PC_PATH_REJECTED_MAC_VISIBLE"
        missing.append("approved PC-readable workbook path")
        next_move = "Next: provide approved PC-readable workbook access."
    elif not approved_path and not approved_ref:
        status = "APPROVED_PC_PATH_REQUIRED" if path_requested else "NO_PATH_REQUESTED"
        if status == "APPROVED_PC_PATH_REQUIRED":
            missing.append("approved PC-readable workbook path")
    elif not marker:
        status = "APPROVED_PC_PATH_REQUIRED"
        missing.append("operator approval marker")
    else:
        status = "APPROVED_PC_PATH_CAPTURED"
        next_move = "Next: provide the invoice tab name and cell mapping."
        path_ref = ApprovedWorkbookPathRef(
            path_ref_id=f"approved_workbook_path_ref:{_short_hash(client_ref, workflow_ref, approved_path, approved_ref)}",
            client_ref=client_ref,
            workflow_ref=workflow_ref,
            world_ref=world_ref,
            workbook_ref=workbook_ref or workbook_identity,
            approved_pc_readable_path=approved_path,
            approved_path_ref=approved_ref or f"approved_pc_path_ref:{_short_hash(approved_path)}",
            path_kind=_path_kind(approved_path, approved_ref),
            path_approval_status=status,
            operator_approval_marker=marker,
            source_request_id=source_request_id,
            mac_visible_path_rejected=False,
            path_translation_guessed=False,
            workbook_body_read=False,
            next_safe_move=next_move,
        )

    request = ClientInvoiceWorkbookPathApprovalRequest(
        request_id=f"path_approval_request:{_short_hash(source_request_id, client_ref, workflow_ref)}",
        source_request_id=source_request_id,
        intended_use=intended_use,
        client_ref=client_ref,
        workflow_ref=workflow_ref,
        world_ref=world_ref,
        workbook_ref=workbook_ref,
        workbook_identity=workbook_identity,
        approved_pc_readable_path=approved_path if status == "APPROVED_PC_PATH_CAPTURED" else "",
        approved_path_ref=approved_ref if status == "APPROVED_PC_PATH_CAPTURED" else "",
        operator_approval_marker=marker,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        validation_status=status,
        missing_context=tuple(dict.fromkeys(missing)),
        next_safe_move=next_move,
    )
    return request, path_ref, record


def _schema_source(raw_request: Mapping[str, Any]) -> Mapping[str, Any] | None:
    schema = raw_request.get("sheet_schema_mapping")
    if not isinstance(schema, Mapping):
        schema = raw_request.get("sheet_audit_schema")
    if not isinstance(schema, Mapping):
        schema = raw_request.get("audit_schema")
    if isinstance(schema, Mapping):
        return schema
    keys = {"sheet_name", "sheet_tab_name", "whitelisted_cells", "whitelisted_columns", "allowed_cells", "allowed_columns"}
    if any(key in raw_request for key in keys):
        return raw_request
    return None


def _surface_result_containers(raw_request: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    containers: list[Mapping[str, Any]] = [raw_request]
    for key in (
        "local_surface_result",
        "surface_result",
        "result",
        "result_payload",
        "payload",
        "mapping_result",
        "field_mapping_result",
        "schema_mapping_result",
    ):
        value = raw_request.get(key)
        if isinstance(value, Mapping):
            containers.append(value)
    for container in tuple(containers):
        for key in ("mapping", "field_mapping", "field_mappings", "schema_mapping", "sheet_schema_mapping"):
            value = container.get(key)
            if isinstance(value, Mapping):
                containers.append(value)
    deduped: list[Mapping[str, Any]] = []
    for container in containers:
        if not any(container is existing for existing in deduped):
            deduped.append(container)
    return tuple(deduped)


def _first_surface_value(raw_request: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for container in _surface_result_containers(raw_request):
        for key in keys:
            if key in container and container.get(key) not in (None, ""):
                return container.get(key)
    return None


def _cell_ref_from_value(value: Any) -> str:
    if isinstance(value, Mapping):
        for key in (
            "cell_ref",
            "cell",
            "cell_reference",
            "selected_cell",
            "address",
            "location",
            "operator_entered_cell_ref",
            "operator_provided_cell_ref",
            "operator_provided_location",
            "value",
        ):
            cell = _safe_cell_ref(value.get(key))
            if cell:
                return cell
        return ""
    return _safe_cell_ref(value)


def _default_expected_value_type(field_name: str) -> str:
    if field_name in {"rate", "subtotal_or_total"}:
        return "currency"
    if field_name == "performance_dates":
        return "date_or_text"
    return "text"


def _column_from_value(field_name: str, value: Any, formula_policy: FormulaPromotionPolicy) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    if not any(key in value for key in ("header_name", "header_cell", "data_cells", "column_ref", "column")):
        return None
    raw = dict(value)
    raw.setdefault("field_name", field_name)
    if "column_ref" in raw and "header_name" not in raw:
        raw["header_name"] = raw["column_ref"]
    if "column" in raw and "header_name" not in raw:
        raw["header_name"] = raw["column"]
    return _normalize_column(raw, formula_policy)


def _surface_field_entries(raw_request: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
    entries: list[tuple[str, Any]] = []
    field_mapping_keys = (
        "field_mappings",
        "mapped_fields",
        "mapping_fields",
        "fields",
        "field_mapping",
        "schema_mapping",
    )
    for container in _surface_result_containers(raw_request):
        for key in field_mapping_keys:
            value = container.get(key)
            if isinstance(value, Mapping):
                entries.extend((str(field_name), field_value) for field_name, field_value in value.items())
            elif isinstance(value, (list, tuple)):
                for item in value:
                    if isinstance(item, Mapping):
                        field_name = str(item.get("field_name") or item.get("semantic_field_name") or item.get("field") or "")
                        if field_name:
                            entries.append((field_name, item))
        targets = container.get("whitelisted_targets")
        if isinstance(targets, (list, tuple)):
            for item in targets:
                if isinstance(item, Mapping):
                    field_name = str(item.get("field_name") or item.get("semantic_field_name") or item.get("field") or "")
                    if field_name:
                        entries.append((field_name, item))
        for field_name in (*REQUIRED_SEMANTIC_FIELDS, *OPTIONAL_SEMANTIC_FIELDS):
            for key in (
                field_name,
                f"{field_name}_cell",
                f"{field_name}_cell_ref",
                f"{field_name}_location",
                f"{field_name}_mapping",
            ):
                if key in container and container.get(key) not in (None, ""):
                    entries.append((field_name, container.get(key)))
                    break
    normalized: list[tuple[str, Any]] = []
    seen: set[str] = set()
    for raw_field, value in entries:
        field_name = _safe_field_name(raw_field)
        if field_name == "unknown_field" or field_name in seen:
            continue
        seen.add(field_name)
        normalized.append((field_name, value))
    return tuple(normalized)


def _schema_mapping_from_local_surface_result(raw_request: Mapping[str, Any]) -> dict[str, Any] | None:
    existing = _schema_source(raw_request)
    if isinstance(existing, Mapping) and (
        existing.get("whitelisted_cells")
        or existing.get("allowed_cells")
        or (isinstance(existing.get("sheet_target"), Mapping) and existing.get("sheet_target", {}).get("allowed_cells"))
    ):
        return dict(existing)

    formula_policy = _formula_policy(_first_surface_value(raw_request, ("formula_promotion_policy", "formula_policy")))
    sheet_name = str(
        _first_surface_value(
            raw_request,
            ("sheet_name", "sheet_tab_name", "invoice_sheet_name", "tab_name", "worksheet_name"),
        )
        or ""
    ).strip()
    cells: list[dict[str, Any]] = []
    columns: list[dict[str, Any]] = []
    for field_name, value in _surface_field_entries(raw_request):
        column = _column_from_value(field_name, value, formula_policy)
        if column is not None:
            columns.append(column)
            continue
        if isinstance(value, Mapping):
            location = (
                value.get("operator_provided_location")
                or value.get("cell_ref")
                or value.get("cell")
                or value.get("location")
                or value.get("value")
            )
        else:
            location = value
        cell_range = _safe_cell_range(location)
        if len(cell_range) > 1:
            columns.append(
                {
                    "field_name": field_name,
                    "header_name": "",
                    "header_cell": "",
                    "data_cells": cell_range,
                    "required": field_name in REQUIRED_SEMANTIC_FIELDS,
                    "expected_value_type": str(
                        value.get("expected_value_type") or value.get("value_type") or _default_expected_value_type(field_name)
                        if isinstance(value, Mapping)
                        else _default_expected_value_type(field_name)
                    ),
                    "formula_promotion_policy": formula_policy.selected_policy,
                }
            )
            continue
        cell_ref = cell_range[0] if cell_range else _cell_ref_from_value(value)
        if not cell_ref:
            continue
        cells.append(
            {
                "field_name": field_name,
                "cell_ref": cell_ref,
                "expected_value_type": str(
                    value.get("expected_value_type") or value.get("value_type") or _default_expected_value_type(field_name)
                    if isinstance(value, Mapping)
                    else _default_expected_value_type(field_name)
                ),
                "required": field_name in REQUIRED_SEMANTIC_FIELDS,
            }
        )
    if not sheet_name and not cells and not columns:
        return None
    return {
        "sheet_name": sheet_name,
        "whitelisted_cells": tuple(cells),
        "whitelisted_columns": tuple(columns),
        "required_fields": REQUIRED_SEMANTIC_FIELDS,
        "optional_fields": OPTIONAL_SEMANTIC_FIELDS,
        "formula_promotion_policy": formula_policy.selected_policy,
    }


def _normalize_cell(raw: Mapping[str, Any], formula_policy: FormulaPromotionPolicy) -> dict[str, Any] | None:
    cell_ref = _safe_cell_ref(raw.get("cell_ref"))
    field_name = _safe_field_name(raw.get("field_name") or raw.get("semantic_field_name"))
    if not cell_ref or field_name == "unknown_field":
        return None
    return {
        "field_name": field_name,
        "cell_ref": cell_ref,
        "required": bool(raw.get("required")),
        "expected_value_type": str(raw.get("expected_value_type") or raw.get("value_type") or "text"),
        "formula_promotion_policy": formula_policy.selected_policy,
    }


def _normalize_column(raw: Mapping[str, Any], formula_policy: FormulaPromotionPolicy) -> dict[str, Any] | None:
    field_name = _safe_field_name(raw.get("field_name") or raw.get("semantic_field_name"))
    header_cell = _safe_cell_ref(raw.get("header_cell"))
    data_cells = tuple(cell for cell in (_safe_cell_ref(value) for value in raw.get("data_cells") or ()) if cell)
    header_name = str(raw.get("header_name") or "").strip()
    if field_name == "unknown_field" or (not header_cell and not data_cells and not header_name):
        return None
    return {
        "field_name": field_name,
        "header_name": header_name,
        "header_cell": header_cell,
        "data_cells": data_cells,
        "required": bool(raw.get("required")),
        "expected_value_type": str(raw.get("expected_value_type") or raw.get("value_type") or "text"),
        "formula_promotion_policy": formula_policy.selected_policy,
    }


def normalize_schema_mapping_request(
    raw_request: Mapping[str, Any],
) -> tuple[ClientInvoiceSheetSchemaMappingRequest, ClientInvoiceSheetSchemaMapping | None]:
    source_request_id = str(raw_request.get("request_id") or "unknown_audit_handoff_request")
    intended_use = str(raw_request.get("intended_use") or "")
    client_ref, workflow_ref, world_ref = _context_values(raw_request)
    missing = list(_context_missing(client_ref, workflow_ref, world_ref))
    schema_source = _schema_source(raw_request)
    policy_source = (
        schema_source.get("formula_promotion_policy")
        if isinstance(schema_source, Mapping)
        else raw_request.get("formula_promotion_policy")
    )
    formula_policy = _formula_policy(policy_source)
    status = "NO_SCHEMA_REQUESTED"
    next_move = "Next: provide the invoice tab name and cell mapping."
    mapping: ClientInvoiceSheetSchemaMapping | None = None

    sheet_name = ""
    cells: tuple[dict[str, Any], ...] = ()
    columns: tuple[dict[str, Any], ...] = ()
    semantic_present: tuple[str, ...] = ()
    semantic_missing: tuple[str, ...] = REQUIRED_SEMANTIC_FIELDS
    required_fields: tuple[str, ...] = ()
    optional_fields: tuple[str, ...] = ()
    expected_types: dict[str, str] = {}

    if intended_use == PATH_APPROVAL_INTENDED_USE and schema_source is None:
        status = "NO_SCHEMA_REQUESTED"
    elif missing:
        status = "HANDOFF_CONTEXT_MISSING"
        next_move = "Next: confirm the client, workflow, and world."
    elif schema_source is None:
        status = "SHEET_AUDIT_SCHEMA_MISSING"
        missing.append("invoice sheet/schema mapping")
        next_move = "Next: provide the invoice tab name and cell mapping."
    else:
        sheet = schema_source.get("sheet_target") if isinstance(schema_source.get("sheet_target"), Mapping) else {}
        sheet_name = str(schema_source.get("sheet_name") or schema_source.get("sheet_tab_name") or sheet.get("sheet_name") or "").strip()
        raw_cells = sheet.get("allowed_cells") or schema_source.get("whitelisted_cells") or schema_source.get("allowed_cells") or ()
        raw_columns = sheet.get("allowed_columns") or schema_source.get("whitelisted_columns") or schema_source.get("allowed_columns") or ()
        cells = tuple(
            cell
            for cell in (_normalize_cell(item, formula_policy) for item in raw_cells if isinstance(item, Mapping))
            if cell is not None
        )
        columns = tuple(
            column
            for column in (_normalize_column(item, formula_policy) for item in raw_columns if isinstance(item, Mapping))
            if column is not None
        )
        semantic_present = tuple(dict.fromkeys(item["field_name"] for item in (*cells, *columns)))
        semantic_missing = tuple(field for field in REQUIRED_SEMANTIC_FIELDS if field not in semantic_present)
        required_fields = tuple(
            dict.fromkeys(
                tuple(_safe_field_name(value) for value in schema_source.get("required_fields") or ())
                + tuple(item["field_name"] for item in (*cells, *columns) if item.get("required") is True)
            )
        )
        optional_fields = tuple(
            dict.fromkeys(
                tuple(_safe_field_name(value) for value in schema_source.get("optional_fields") or ())
                + tuple(item["field_name"] for item in (*cells, *columns) if item.get("required") is not True)
            )
        )
        expected_types = {item["field_name"]: str(item.get("expected_value_type") or "text") for item in (*cells, *columns)}
        if not sheet_name or not (cells or columns):
            status = "SHEET_AUDIT_SCHEMA_MISSING"
            missing.append("sheet name and whitelisted cells/columns")
        elif semantic_missing:
            status = "SHEET_AUDIT_SCHEMA_INCOMPLETE"
            missing.extend(semantic_missing)
        else:
            status = "SHEET_AUDIT_SCHEMA_CAPTURED"
            next_move = "Next: provide approved PC-readable workbook access."
            mapping = ClientInvoiceSheetSchemaMapping(
                schema_mapping_id=f"sheet_schema_mapping:{_short_hash(client_ref, workflow_ref, sheet_name, semantic_present)}",
                client_ref=client_ref,
                workflow_ref=workflow_ref,
                world_ref=world_ref,
                sheet_name=sheet_name,
                whitelisted_cells=cells,
                whitelisted_columns=columns,
                semantic_fields_present=semantic_present,
                semantic_fields_missing=(),
                required_fields=required_fields,
                optional_fields=optional_fields,
                expected_value_types=expected_types,
                formula_promotion_policy=asdict(formula_policy),
                schema_mapping_status=status,
                source_request_id=source_request_id,
                inferred_schema=False,
                workbook_layout_inspected=False,
                next_safe_move=next_move,
            )
    request = ClientInvoiceSheetSchemaMappingRequest(
        request_id=f"schema_mapping_request:{_short_hash(source_request_id, client_ref, workflow_ref)}",
        source_request_id=source_request_id,
        intended_use=intended_use,
        client_ref=client_ref,
        workflow_ref=workflow_ref,
        world_ref=world_ref,
        sheet_name=sheet_name,
        schema_ref=mapping.schema_mapping_id if mapping else "",
        formula_promotion_policy=formula_policy.selected_policy,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        validation_status=status,
        missing_context=tuple(dict.fromkeys(missing)),
        next_safe_move=next_move,
    )
    return request, mapping


def _mapping_to_sheet_audit_schema(mapping: Mapping[str, Any]) -> dict[str, Any]:
    def formula_policy(_selected: str) -> str:
        if _selected == "cached_readback_allowed_only_if_explicit":
            return "ALLOW_CACHED_READBACK_IF_EXPLICITLY_ALLOWED"
        return "FORMULA_BLOCK_UNLESS_OPERATOR_CONFIRMS"

    selected = str((mapping.get("formula_promotion_policy") or {}).get("selected_policy") or "operator_confirmation_required")
    return {
        "schema_id": str(mapping.get("schema_mapping_id") or ""),
        "schema_version": "v0",
        "client_ref": mapping.get("client_ref"),
        "workflow_ref": mapping.get("workflow_ref"),
        "world_ref": mapping.get("world_ref"),
        "sheet_target": {
            "sheet_name": mapping.get("sheet_name"),
            "allowed_cells": tuple(
                {
                    "field_name": cell["field_name"],
                    "cell_ref": cell["cell_ref"],
                    "expected_value_type": cell["expected_value_type"],
                    "required": cell["required"],
                    "formula_policy": formula_policy(selected),
                }
                for cell in mapping.get("whitelisted_cells") or ()
            ),
            "allowed_columns": tuple(
                {
                    "field_name": column["field_name"],
                    "header_name": column.get("header_name", ""),
                    "header_cell": column.get("header_cell", ""),
                    "data_cells": tuple(column.get("data_cells") or ()),
                    "expected_value_type": column["expected_value_type"],
                    "required": column["required"],
                    "formula_policy": formula_policy(selected),
                }
                for column in mapping.get("whitelisted_columns") or ()
            ),
        },
        "required_fields": tuple(mapping.get("required_fields") or ()),
        "optional_fields": tuple(mapping.get("optional_fields") or ()),
        "formula_cached_readback_policy": formula_policy(selected),
        "known_facts": {},
    }


def _sheet_audit_request_template(
    *,
    client_ref: str,
    workflow_ref: str,
    world_ref: str,
    path_ref: Mapping[str, Any] | None,
    schema_mapping: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not path_ref or not schema_mapping:
        return None
    return {
        "intended_use": "client_invoice_sheet_audit",
        "client_ref": client_ref,
        "workflow_ref": workflow_ref,
        "world_ref": world_ref,
        "approved_pc_workbook_path_authorized": True,
        "approved_pc_workbook_path": path_ref.get("approved_pc_readable_path", ""),
        "approved_pc_workbook_path_ref": path_ref.get("approved_path_ref", ""),
        "sheet_audit_schema": _mapping_to_sheet_audit_schema(schema_mapping),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _readback_for(
    *,
    client_ref: str,
    workflow_ref: str,
    world_ref: str,
    path_status: str,
    schema_status: str,
    formula_policy: FormulaPromotionPolicy,
    live_ready: bool,
    missing_items: tuple[str, ...],
    path_ref: Mapping[str, Any] | None,
    schema_mapping: Mapping[str, Any] | None,
    workbook_record: Mapping[str, Any] | None,
    source_request_id: str,
) -> ClientInvoiceAuditHandoffReadback:
    capital = client_ref == "capital_hilton"
    client_name = "Capital Hilton" if capital else client_ref.replace("_", " ").title()
    if live_ready:
        status = "HANDOFF_READY_FOR_SHEET_AUDIT"
        headline = f"{client_name} sheet audit is ready"
        message = (
            "OpenClaw has the workbook reference, approved PC-readable path, and explicit sheet mapping. "
            "It can now run the whitelisted audit."
        )
        next_action = f"Next: run the {client_name} sheet audit."
    elif schema_status == "SHEET_AUDIT_SCHEMA_INCOMPLETE":
        status = "SHEET_AUDIT_SCHEMA_INCOMPLETE"
        headline = "Sheet mapping needs fields"
        message = "OpenClaw received a sheet mapping, but it is missing required invoice audit fields."
        next_action = "Next: provide the missing invoice field mappings."
    elif path_status == "APPROVED_PC_PATH_CAPTURED" and schema_status not in {"SHEET_AUDIT_SCHEMA_CAPTURED"}:
        status = "APPROVED_PC_PATH_CAPTURED_SCHEMA_REQUIRED"
        headline = f"{client_name} workbook path approved"
        message = (
            "OpenClaw now has an approved PC-readable workbook path, but still needs the invoice sheet mapping before it can audit cells."
        )
        next_action = "Next: provide the invoice tab name and cell mapping."
    elif schema_status == "SHEET_AUDIT_SCHEMA_CAPTURED" and path_status != "APPROVED_PC_PATH_CAPTURED":
        status = "SCHEMA_MAPPING_CAPTURED_PATH_REQUIRED"
        headline = f"{client_name} invoice sheet mapping captured"
        message = "OpenClaw knows which fields to audit, but still needs an approved PC-readable workbook path."
        next_action = "Next: provide approved PC-readable workbook access."
    elif path_status in {"APPROVED_PC_PATH_REJECTED_MAC_VISIBLE", "APPROVED_PC_PATH_REQUIRED"}:
        status = "APPROVED_PC_PATH_REQUIRED"
        headline = "PC-readable workbook path needed"
        message = "OpenClaw needs an explicitly approved PC-readable workbook path. It did not guess or translate a Mac path."
        next_action = "Next: provide approved PC-readable workbook access."
    elif schema_status == "SHEET_AUDIT_SCHEMA_MISSING":
        status = "SHEET_AUDIT_SCHEMA_MISSING"
        headline = "Invoice sheet mapping needed"
        message = "OpenClaw needs the invoice tab name and whitelisted cell or column mapping before it can audit cells."
        next_action = "Next: provide the invoice tab name and cell mapping."
    elif path_status == "WORKBOOK_REGISTRY_REQUIRED":
        status = "WORKBOOK_REGISTRY_REQUIRED"
        headline = "Register the workbook first"
        message = "OpenClaw needs a registered workbook record before this audit handoff can be used."
        next_action = "Next: register or capture the workbook first."
    else:
        status = "HANDOFF_CONTEXT_MISSING"
        headline = "Audit context needed"
        message = "OpenClaw needs explicit client, workflow, and world context before preparing sheet audit handoff."
        next_action = "Next: confirm the client, workflow, and world."
    return ClientInvoiceAuditHandoffReadback(
        readback_id=f"audit_handoff_readback:{_short_hash(source_request_id, status)}",
        status=status,
        operator_headline=headline,
        operator_message=message,
        path_approval_status=path_status,
        schema_mapping_status=schema_status,
        formula_policy_status=formula_policy.selected_policy,
        live_audit_ready=live_ready,
        missing_items=missing_items,
        next_action=next_action,
        hidden_refs={
            "source_request_id": source_request_id,
            "workbook_ref": str(workbook_record.get("workbook_ref") or "") if workbook_record else "",
            "approved_path_ref_id": str(path_ref.get("path_ref_id") or "") if path_ref else "",
            "schema_mapping_id": str(schema_mapping.get("schema_mapping_id") or "") if schema_mapping else "",
        },
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move=next_action,
    )


def process_handoff_request(
    raw_request: Mapping[str, Any],
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    source_request_id = str(raw_request.get("request_id") or "unknown_audit_handoff_request")
    client_ref, workflow_ref, world_ref = _context_values(raw_request)
    registry_payload = load_workbook_registry(export_root)
    existing_payload = load_existing_payload(export_root)
    path_request, _new_path_ref, workbook_record = normalize_path_approval_request(
        raw_request,
        registry_payload=registry_payload,
    )
    schema_request, new_schema_mapping = normalize_schema_mapping_request(raw_request)
    existing_schema = _existing_schema(existing_payload, client_ref=client_ref, workflow_ref=workflow_ref, world_ref=world_ref)

    artifact_payload: dict[str, Any] | None = None
    active_artifact: dict[str, Any] | None = None
    if _path_request_has_artifact_signal(raw_request):
        artifact_payload = local_artifact_reference.evaluate_artifact_reference(
            _artifact_request_from_handoff(raw_request, workbook_record=workbook_record, path_request=path_request),
            expected_scope={
                "world_ref": world_ref,
                "workflow_ref": workflow_ref,
                "client_ref": client_ref,
            },
            artifact_kind_default="invoice_workbook",
            intended_use_default="client_invoice_sheet_audit",
            generated_at=generated_at,
        )
        active_artifact = _matching_artifact_from_payload(
            artifact_payload,
            client_ref=client_ref,
            workflow_ref=workflow_ref,
            world_ref=world_ref,
            source_request_id=source_request_id,
        )
    if active_artifact is None:
        for candidate_payload in (
            _artifact_payload_from_existing_handoff(existing_payload),
            local_artifact_reference.load_existing_payload(export_root),
        ):
            active_artifact = _matching_artifact_from_payload(
                candidate_payload,
                client_ref=client_ref,
                workflow_ref=workflow_ref,
                world_ref=world_ref,
                source_request_id=source_request_id,
            )
            if active_artifact is not None:
                artifact_payload = candidate_payload
                break

    active_path_ref = _path_ref_from_artifact(active_artifact)
    active_schema_mapping = asdict(new_schema_mapping) if new_schema_mapping else existing_schema
    formula_policy = _formula_policy(
        (active_schema_mapping or {}).get("formula_promotion_policy")
        or raw_request.get("formula_promotion_policy")
    )

    path_status = str((active_path_ref or {}).get("path_approval_status") or path_request.validation_status)
    schema_status = str((active_schema_mapping or {}).get("schema_mapping_status") or schema_request.validation_status)
    if schema_request.validation_status == "SHEET_AUDIT_SCHEMA_INCOMPLETE":
        schema_status = "SHEET_AUDIT_SCHEMA_INCOMPLETE"
    if path_request.validation_status in {"APPROVED_PC_PATH_REJECTED_MAC_VISIBLE", "APPROVED_PC_PATH_REQUIRED"}:
        path_status = path_request.validation_status
    if path_request.validation_status == "APPROVED_PC_PATH_CAPTURED" and active_artifact is None:
        path_status = "APPROVED_PC_PATH_REQUIRED"
    live_ready = bool(
        workbook_record
        and active_artifact
        and active_path_ref
        and active_schema_mapping
        and path_status == "APPROVED_PC_PATH_CAPTURED"
        and schema_status == "SHEET_AUDIT_SCHEMA_CAPTURED"
        and not _context_missing(client_ref, workflow_ref, world_ref)
    )
    missing: list[str] = []
    if not workbook_record:
        missing.append("registered workbook")
    if path_status != "APPROVED_PC_PATH_CAPTURED":
        missing.append("approved PC-readable workbook path")
    if schema_status != "SHEET_AUDIT_SCHEMA_CAPTURED":
        missing.extend(schema_request.missing_context or ("explicit sheet/schema mapping",))
    missing.extend(_context_missing(client_ref, workflow_ref, world_ref))
    readback = _readback_for(
        client_ref=client_ref,
        workflow_ref=workflow_ref,
        world_ref=world_ref,
        path_status=path_status,
        schema_status=schema_status,
        formula_policy=formula_policy,
        live_ready=live_ready,
        missing_items=tuple(dict.fromkeys(missing)),
        path_ref=active_path_ref,
        schema_mapping=active_schema_mapping,
        workbook_record=workbook_record,
        source_request_id=source_request_id,
    )
    template = _sheet_audit_request_template(
        client_ref=client_ref,
        workflow_ref=workflow_ref,
        world_ref=world_ref,
        path_ref=active_path_ref if live_ready else None,
        schema_mapping=active_schema_mapping if live_ready else None,
    )
    return _build_payload(
        generated_at=generated_at,
        path_request=path_request,
        schema_request=schema_request,
        approved_path_ref=active_path_ref,
        schema_mapping=active_schema_mapping,
        formula_policy=formula_policy,
        readback=readback,
        workbook_record=workbook_record,
        live_audit_ready=live_ready,
        sheet_audit_request_template=template,
        local_artifact_payload=artifact_payload,
        approved_readable_artifact=active_artifact,
    )


def _capital_hilton_binding_errors(client_ref: str, workflow_ref: str, world_ref: str) -> tuple[str, ...]:
    errors: list[str] = []
    if client_ref != "capital_hilton":
        errors.append("client_ref=capital_hilton")
    if workflow_ref != "capital_hilton_invoice_workflow":
        errors.append("workflow_ref=capital_hilton_invoice_workflow")
    if world_ref != "finance":
        errors.append("world_ref=finance")
    return tuple(errors)


def _local_surface_result_validation_errors(raw_request: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    if not is_local_surface_schema_mapping_result(raw_request):
        errors.append("LOCAL_SURFACE_RESULT/client_invoice_sheet_schema_mapping")
    client_ref, workflow_ref, world_ref = _context_values(raw_request)
    errors.extend(_capital_hilton_binding_errors(client_ref, workflow_ref, world_ref))
    if _first_surface_value(raw_request, ("operator_provided",)) is not True:
        errors.append("operator_provided=true")
    if _first_surface_value(raw_request, ("operator_confirmed_mapping", "operator_confirmed")) is not True:
        errors.append("operator_confirmed_mapping=true")
    for flag in LOCAL_SURFACE_RESULT_FALSE_FLAGS:
        if _first_surface_value(raw_request, (flag,)) is not False:
            errors.append(f"{flag}=false")
    authority = raw_request.get("authority_boundary")
    if isinstance(authority, Mapping) and any(value is True for value in authority.values()):
        errors.append("authority_boundary_all_false")
    return tuple(dict.fromkeys(errors))


def _local_surface_status_for_errors(errors: tuple[str, ...]) -> str:
    if any(error.startswith("operator_") for error in errors):
        return "LOCAL_SURFACE_RESULT_UNCONFIRMED"
    if any(error.endswith("=false") or error == "authority_boundary_all_false" for error in errors):
        return "LOCAL_SURFACE_RESULT_UNSAFE_FLAGS"
    return "LOCAL_SURFACE_RESULT_BLOCKED"


def _local_surface_receipt(
    raw_request: Mapping[str, Any],
    *,
    status: str,
    validation_errors: tuple[str, ...],
    missing_mapping_fields: tuple[str, ...],
    live_audit_ready: bool,
) -> dict[str, Any]:
    return {
        "receipt_id": f"local_surface_schema_mapping_receipt:{_short_hash(raw_request.get('request_id'), status)}",
        "source_request_id": str(raw_request.get("request_id") or "unknown_local_surface_result"),
        "result_kind": _local_surface_result_kind(raw_request),
        "intended_use": str(raw_request.get("intended_use") or ""),
        "receipt_status": status,
        "operator_provided": _first_surface_value(raw_request, ("operator_provided",)) is True,
        "operator_confirmed_mapping": _first_surface_value(raw_request, ("operator_confirmed_mapping", "operator_confirmed")) is True,
        "mapping_classification": "operator_provided_schema_guidance",
        "verified_sheet_data": False,
        "spreadsheet_truth_claimed": False,
        "validation_errors": validation_errors,
        "missing_mapping_fields": missing_mapping_fields,
        "live_audit_ready": live_audit_ready,
        "safety_flags": {
            flag: _first_surface_value(raw_request, (flag,))
            for flag in LOCAL_SURFACE_RESULT_FALSE_FLAGS
        },
        "workbook_body_read_performed": False,
        "spreadsheet_cell_read_performed": False,
        "schema_inference_performed": False,
        "external_action_performed": False,
        "next_safe_move": (
            "Use this only as operator-provided mapping guidance; validate gates before any sheet audit."
            if not validation_errors
            else "Resend the local surface result with confirmed mapping and all safety flags false."
        ),
    }


def _blocked_local_surface_result_payload(
    raw_request: Mapping[str, Any],
    *,
    export_root: Path,
    generated_at: str,
    validation_errors: tuple[str, ...],
) -> dict[str, Any]:
    source_request_id = str(raw_request.get("request_id") or "unknown_local_surface_result")
    client_ref, workflow_ref, world_ref = _context_values(raw_request)
    registry_payload = load_workbook_registry(export_root)
    path_request, _new_path_ref, workbook_record = normalize_path_approval_request(
        {**dict(raw_request), "sheet_schema_mapping": None},
        registry_payload=registry_payload,
    )
    formula_policy = _formula_policy(_first_surface_value(raw_request, ("formula_promotion_policy", "formula_policy")))
    status = _local_surface_status_for_errors(validation_errors)
    headline = "Field mapping result blocked"
    message = "OpenClaw received a field mapping result, but it failed the local surface safety or confirmation checks."
    if status == "LOCAL_SURFACE_RESULT_UNCONFIRMED":
        headline = "Confirm the field mapping"
        message = "OpenClaw received field mapping guidance, but the operator confirmation receipt was missing."
    elif status == "LOCAL_SURFACE_RESULT_UNSAFE_FLAGS":
        headline = "Field mapping result blocked"
        message = "OpenClaw blocked the field mapping result because a read, share, path-translation, or external-action flag was not false."
    schema_request = ClientInvoiceSheetSchemaMappingRequest(
        request_id=f"schema_mapping_request:{_short_hash(source_request_id, client_ref, workflow_ref)}",
        source_request_id=source_request_id,
        intended_use=str(raw_request.get("intended_use") or ""),
        client_ref=client_ref,
        workflow_ref=workflow_ref,
        world_ref=world_ref,
        sheet_name="",
        schema_ref="",
        formula_promotion_policy=formula_policy.selected_policy,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        validation_status=status,
        missing_context=validation_errors,
        next_safe_move="Next: resend the confirmed field mapping result with all safety flags false.",
    )
    readback = ClientInvoiceAuditHandoffReadback(
        readback_id=f"audit_handoff_readback:{_short_hash(source_request_id, status)}",
        status=status,
        operator_headline=headline,
        operator_message=message,
        path_approval_status=path_request.validation_status,
        schema_mapping_status=status,
        formula_policy_status=formula_policy.selected_policy,
        live_audit_ready=False,
        missing_items=validation_errors,
        next_action="Next: resend the confirmed field mapping result with all safety flags false.",
        hidden_refs={
            "source_request_id": source_request_id,
            "workbook_ref": str(workbook_record.get("workbook_ref") or "") if workbook_record else "",
            "approved_path_ref_id": "",
            "schema_mapping_id": "",
        },
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Next: resend the confirmed field mapping result with all safety flags false.",
    )
    payload = _build_payload(
        generated_at=generated_at,
        path_request=path_request,
        schema_request=schema_request,
        approved_path_ref=None,
        schema_mapping=None,
        formula_policy=formula_policy,
        readback=readback,
        workbook_record=workbook_record,
        live_audit_ready=False,
        sheet_audit_request_template=None,
    )
    receipt = _local_surface_receipt(
        raw_request,
        status=status,
        validation_errors=validation_errors,
        missing_mapping_fields=(),
        live_audit_ready=False,
    )
    payload["local_surface_result_receipt"] = receipt
    payload["machine_proof"].update(
        {
            "local_surface_result_consumed": True,
            "operator_provided_schema_guidance": False,
            "verified_sheet_data": False,
            "spreadsheet_truth_claimed": False,
            "operator_confirmed_mapping": receipt["operator_confirmed_mapping"],
        }
    )
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def process_local_surface_schema_mapping_result(
    raw_request: Mapping[str, Any],
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    validation_errors = _local_surface_result_validation_errors(raw_request)
    if validation_errors:
        return _blocked_local_surface_result_payload(
            raw_request,
            export_root=export_root,
            generated_at=generated_at,
            validation_errors=validation_errors,
        )

    schema_mapping = _schema_mapping_from_local_surface_result(raw_request)
    normalized_request = dict(raw_request)
    if schema_mapping is not None:
        normalized_request["sheet_schema_mapping"] = schema_mapping
    payload = process_handoff_request(normalized_request, export_root=export_root, generated_at=generated_at)
    schema_request = payload.get("schema_mapping_request") if isinstance(payload.get("schema_mapping_request"), Mapping) else {}
    missing_mapping_fields = tuple(
        str(item)
        for item in schema_request.get("missing_context", ())
        if str(item) in REQUIRED_SEMANTIC_FIELDS or str(item) in {"sheet name and whitelisted cells/columns", "invoice sheet/schema mapping"}
    )
    receipt_status = (
        "LOCAL_SURFACE_RESULT_SCHEMA_GUIDANCE_CAPTURED"
        if schema_request.get("validation_status") == "SHEET_AUDIT_SCHEMA_CAPTURED"
        else "LOCAL_SURFACE_RESULT_SCHEMA_GUIDANCE_INCOMPLETE"
    )
    receipt = _local_surface_receipt(
        raw_request,
        status=receipt_status,
        validation_errors=(),
        missing_mapping_fields=missing_mapping_fields,
        live_audit_ready=bool(payload.get("live_audit_ready")),
    )
    payload["local_surface_result_receipt"] = receipt
    payload["machine_proof"].update(
        {
            "local_surface_result_consumed": True,
            "operator_provided_schema_guidance": True,
            "verified_sheet_data": False,
            "spreadsheet_truth_claimed": False,
            "operator_confirmed_mapping": True,
            "body_read_flag_false": _first_surface_value(raw_request, ("body_read",)) is False,
            "workbook_body_read_flag_false": _first_surface_value(raw_request, ("workbook_body_read",)) is False,
            "spreadsheet_cell_read_flag_false": _first_surface_value(raw_request, ("spreadsheet_cell_read",)) is False,
            "ocr_performed_flag_false": _first_surface_value(raw_request, ("ocr_performed",)) is False,
            "external_llm_shared_flag_false": _first_surface_value(raw_request, ("external_llm_shared",)) is False,
            "external_action_flag_false": _first_surface_value(raw_request, ("external_action",)) is False,
            "path_translation_guessed_flag_false": _first_surface_value(raw_request, ("path_translation_guessed",)) is False,
        }
    )
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def _build_payload(
    *,
    generated_at: str,
    path_request: ClientInvoiceWorkbookPathApprovalRequest,
    schema_request: ClientInvoiceSheetSchemaMappingRequest,
    approved_path_ref: Mapping[str, Any] | None,
    schema_mapping: Mapping[str, Any] | None,
    formula_policy: FormulaPromotionPolicy,
    readback: ClientInvoiceAuditHandoffReadback,
    workbook_record: Mapping[str, Any] | None,
    live_audit_ready: bool,
    sheet_audit_request_template: Mapping[str, Any] | None,
    local_artifact_payload: Mapping[str, Any] | None = None,
    approved_readable_artifact: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    artifact_readiness = (
        local_artifact_payload.get("artifact_readiness_state")
        if isinstance(local_artifact_payload, Mapping) and isinstance(local_artifact_payload.get("artifact_readiness_state"), Mapping)
        else {}
    )
    artifact_receipt = (
        local_artifact_payload.get("artifact_approval_receipt")
        if isinstance(local_artifact_payload, Mapping) and isinstance(local_artifact_payload.get("artifact_approval_receipt"), Mapping)
        else {}
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "accepted_intended_uses": ACCEPTED_INTENDED_USES,
        "path_statuses": PATH_STATUSES,
        "schema_statuses": SCHEMA_STATUSES,
        "readback_statuses": READBACK_STATUSES,
        "model_schemas": {
            "ClientInvoiceWorkbookPathApprovalRequest": tuple(field.name for field in fields(ClientInvoiceWorkbookPathApprovalRequest)),
            "ClientInvoiceSheetSchemaMappingRequest": tuple(field.name for field in fields(ClientInvoiceSheetSchemaMappingRequest)),
            "ApprovedWorkbookPathRef": tuple(field.name for field in fields(ApprovedWorkbookPathRef)),
            "ClientInvoiceSheetSchemaMapping": tuple(field.name for field in fields(ClientInvoiceSheetSchemaMapping)),
            "FormulaPromotionPolicy": tuple(field.name for field in fields(FormulaPromotionPolicy)),
            "ClientInvoiceAuditHandoffReadback": tuple(field.name for field in fields(ClientInvoiceAuditHandoffReadback)),
        },
        "path_approval_request": asdict(path_request),
        "schema_mapping_request": asdict(schema_request),
        "approved_workbook_path_ref": dict(approved_path_ref) if approved_path_ref else None,
        "schema_mapping": dict(schema_mapping) if schema_mapping else None,
        "formula_promotion_policy": asdict(formula_policy),
        "audit_handoff_readback": asdict(readback),
        "workbook_registry_record_ref": str(workbook_record.get("workbook_ref") or "") if workbook_record else "",
        "workbook_registry_record_present": bool(workbook_record),
        "live_audit_ready": live_audit_ready,
        "sheet_audit_request_template": dict(sheet_audit_request_template) if sheet_audit_request_template else None,
        "local_artifact_reference_payload": dict(local_artifact_payload) if isinstance(local_artifact_payload, Mapping) else None,
        "approved_readable_artifact": dict(approved_readable_artifact) if isinstance(approved_readable_artifact, Mapping) else None,
        "artifact_approval_receipt": dict(artifact_receipt) if artifact_receipt else None,
        "artifact_readiness_state": dict(artifact_readiness) if artifact_readiness else None,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "workbook_registry_readmodel_read": True,
            "generic_approved_artifact_reference_used": isinstance(local_artifact_payload, Mapping),
            "approved_readable_artifact_ready": bool(approved_readable_artifact),
            "approved_pc_path_or_ref_contract_present": bool(approved_path_ref),
            "legacy_workbook_path_not_sufficient_for_readiness": True,
            "explicit_schema_mapping_contract_present": bool(schema_mapping),
            "formula_promotion_policy_present": True,
            "formula_policy_default_conservative": formula_policy.selected_policy == "operator_confirmation_required",
            "live_audit_ready": live_audit_ready,
            "artifact_approved_for_read": bool((approved_readable_artifact or {}).get("approved_for_read")),
            "artifact_approved_for_write": bool((approved_readable_artifact or {}).get("approved_for_write")),
            "artifact_body_read": bool((approved_readable_artifact or {}).get("body_read")),
            "artifact_content_extracted": bool((approved_readable_artifact or {}).get("content_extracted")),
            "artifact_external_shared": bool((approved_readable_artifact or {}).get("external_shared")),
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "schema_inference_performed": False,
            "mac_path_translation_guessed": False,
            "formula_evaluation_performed": False,
            "pdf_generation_performed": False,
            "email_send_performed": False,
            "gmail_send_performed": False,
            "coupa_access_or_submit_performed": False,
            "browser_access_performed": False,
            "workflow_execution_performed": False,
            "agent_dispatch_performed": False,
            "model_call_performed": False,
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


def make_capital_hilton_path_only_fixture_request(*, created_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    return {
        "request_id": "mission_control_chat_request_capital_hilton_path_handoff_fixture",
        "workflow_ref": "capital_hilton_invoice_workflow",
        "world_ref": "finance",
        "client_ref": "capital_hilton",
        "operator_goal": "Approve the PC-readable invoice workbook path.",
        "operator_message": "Use this PC-readable workbook path for the Capital Hilton invoice.",
        "sanitized_message_summary": "Approve Capital Hilton workbook path.",
        "intended_use": PATH_APPROVAL_INTENDED_USE,
        "approved_pc_readable_path": "/mnt/e/openclaw/fixtures/capital_hilton_invoice_workbook.xlsx",
        "approved_path_ref": "approved_pc_path_ref:capital_hilton_invoice_workbook",
        "operator_approval_marker": "operator_selected_pc_path",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "created_at": created_at,
    }


def build_payload(*, export_root: Path = DEFAULT_EXPORT_ROOT, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    return process_handoff_request(
        make_capital_hilton_path_only_fixture_request(created_at=generated_at),
        export_root=export_root,
        generated_at=generated_at,
    )


def format_operator_markdown(payload: Mapping[str, Any]) -> str:
    readback = payload.get("audit_handoff_readback") if isinstance(payload.get("audit_handoff_readback"), Mapping) else {}
    lines = [
        "# Client Invoice Audit Handoff",
        "",
        "ELIOPERATOR: Path/schema handoff contract only. No workbook body, spreadsheet cells, schema inference, formula evaluation, Mac path translation, browser, Coupa, PDF, email, network, credentials, or external systems were touched.",
        "",
        f"- Status: `{readback.get('status', 'UNKNOWN')}`",
        f"- Path status: `{readback.get('path_approval_status', 'UNKNOWN')}`",
        f"- Schema status: `{readback.get('schema_mapping_status', 'UNKNOWN')}`",
        f"- Formula policy: `{readback.get('formula_policy_status', 'UNKNOWN')}`",
        f"- Live audit ready: `{payload.get('live_audit_ready', False)}`",
        "",
        f"## {readback.get('operator_headline', 'Audit handoff')}",
        "",
        str(readback.get("operator_message") or "No audit handoff request was processed."),
        "",
        "## Next",
        "",
        str(readback.get("next_action") or "Wait for an approved path/schema handoff."),
        "",
    ]
    return "\n".join(lines)


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    artifact_payload = payload.get("local_artifact_reference_payload")
    if isinstance(artifact_payload, dict) and artifact_payload.get("approved_readable_artifact"):
        local_artifact_reference.write_exports(artifact_payload, export_root)
    return json_path, operator_path


def build_summary(payload: Mapping[str, Any], paths: tuple[Path, Path]) -> dict[str, Any]:
    readback = payload.get("audit_handoff_readback") if isinstance(payload.get("audit_handoff_readback"), Mapping) else {}
    proof = payload.get("machine_proof") if isinstance(payload.get("machine_proof"), Mapping) else {}
    return {
        "read_model_id": payload.get("read_model_id"),
        "contract_status": payload.get("contract_status"),
        "json_path": paths[0].as_posix(),
        "operator_path": paths[1].as_posix(),
        "status": readback.get("status"),
        "operator_headline": readback.get("operator_headline"),
        "next_action": readback.get("next_action"),
        "path_approval_status": readback.get("path_approval_status"),
        "schema_mapping_status": readback.get("schema_mapping_status"),
        "formula_policy_status": readback.get("formula_policy_status"),
        "live_audit_ready": payload.get("live_audit_ready"),
        "all_live_authority_false": proof.get("all_live_authority_false"),
        "content_hash": proof.get("content_hash"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the client invoice audit path/schema handoff read-model.")
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
