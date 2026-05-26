"""Approved PC-readable local artifact reference contract v0.

This substrate records whether an exact local artifact reference is approved
for a scoped workflow and has a PC-readable path/ref. It does not open files,
read bodies, extract content, call models, launch apps, or execute workflows.
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

SCHEMA_VERSION = "local_artifact_reference_v0"
READ_MODEL_ID = "local_artifact_reference"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_APPROVED_READABLE_ARTIFACT_REFERENCE_NO_CONTENT_READ"

READINESS_STATUSES = (
    "ARTIFACT_READY_FOR_READ",
    "ARTIFACT_SCOPE_MISSING",
    "ARTIFACT_SCOPE_MISMATCH",
    "ARTIFACT_PC_PATH_REQUIRED",
    "ARTIFACT_MAC_PATH_NOT_PC_READABLE",
    "ARTIFACT_APPROVAL_REQUIRED",
    "ARTIFACT_WRITE_AUTHORITY_BLOCKED",
    "ARTIFACT_BODY_OR_CONTENT_ALREADY_READ_BLOCKED",
    "ARTIFACT_EXTERNAL_SHARE_BLOCKED",
    "ARTIFACT_PATH_TRANSLATION_GUESSED_BLOCKED",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_file_body_read_allowed": False,
    "live_workbook_body_read_allowed": False,
    "live_spreadsheet_cell_read_allowed": False,
    "live_content_extraction_allowed": False,
    "live_ocr_allowed": False,
    "live_path_translation_guess_allowed": False,
    "live_write_allowed": False,
    "live_external_share_allowed": False,
    "live_external_action_allowed": False,
    "live_workflow_run_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_model_call_allowed": False,
    "live_browser_allowed": False,
    "network_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
}


@dataclass(frozen=True)
class ArtifactScopeBinding:
    binding_id: str
    world_ref: str
    workflow_ref: str
    client_ref: str
    project_ref: str
    tenant_ref: str
    required_scope_keys: tuple[str, ...]
    binding_status: str
    scope_hash: str
    next_safe_move: str


@dataclass(frozen=True)
class LocalArtifactReference:
    artifact_ref: str
    artifact_kind: str
    artifact_label: str
    source_request_id: str
    intended_use: str
    world_ref: str
    workflow_ref: str
    client_ref: str
    project_ref: str
    tenant_ref: str
    local_surface_ref: str
    mac_path: str
    pc_path: str
    approved_path_ref: str
    path_mapping_verified: bool
    path_translation_guessed: bool
    operator_approved: bool
    approved_for_read: bool
    approved_for_write: bool
    body_read: bool
    content_extracted: bool
    external_shared: bool
    approval_timestamp: str
    approval_source: str
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class ApprovedReadableArtifact:
    approval_id: str
    artifact_ref: str
    artifact_kind: str
    artifact_label: str
    intended_use: str
    scope_binding: dict[str, Any]
    source_request_id: str
    local_surface_ref: str
    mac_path: str
    pc_path: str
    approved_path_ref: str
    path_mapping_verified: bool
    operator_approved: bool
    approved_for_read: bool
    approved_for_write: bool
    body_read: bool
    content_extracted: bool
    external_shared: bool
    approval_timestamp: str
    approval_source: str
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class ArtifactApprovalReceipt:
    receipt_id: str
    source_request_id: str
    artifact_ref: str
    artifact_kind: str
    receipt_status: str
    operator_approved: bool
    approved_for_read: bool
    approved_for_write: bool
    body_read: bool
    content_extracted: bool
    external_shared: bool
    path_mapping_verified: bool
    path_translation_guessed: bool
    validation_errors: tuple[str, ...]
    missing_items: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class ArtifactReadinessState:
    readiness_id: str
    readiness_status: str
    artifact_ref: str
    artifact_kind: str
    intended_use: str
    scope_binding_status: str
    pc_readable_path_present: bool
    path_mapping_verified: bool
    operator_approved: bool
    approved_for_read: bool
    approved_for_write: bool
    body_read: bool
    content_extracted: bool
    external_shared: bool
    live_read_ready: bool
    missing_items: tuple[str, ...]
    blocking_reasons: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class ArtifactReferenceHandlerRegistration:
    handler_id: str
    handler_label: str
    artifact_kind: str
    intended_use: str
    world_refs: tuple[str, ...]
    client_or_project_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class ArtifactReferenceRouter:
    router_id: str
    contract_status: str
    registered_handlers: tuple[dict[str, Any], ...]
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


def _bool_from_request(raw_request: Mapping[str, Any], keys: tuple[str, ...], *, default: bool = False) -> bool:
    for key in keys:
        if key in raw_request:
            return raw_request.get(key) is True
    return default


def _first_text(raw_request: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = str(raw_request.get(key) or "").strip()
        if value:
            return value
    return ""


def is_mac_visible_path(value: object) -> bool:
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


def is_pc_readable_path_style(value: object) -> bool:
    text = str(value or "").strip()
    lowered = text.lower()
    if not text or is_mac_visible_path(text) or "\x00" in text:
        return False
    if "://" in text or lowered.startswith(("http:", "https:", "ftp:", "smb:")):
        return False
    if ".." in Path(text).parts:
        return False
    return text.startswith(("/mnt/", "/home/", "/tmp/", "/var/tmp/", "/opt/")) or lowered.startswith(
        ("backend_readable_ref:", "wsl_path_ref:", "linux_path_ref:")
    )


def _approval_source(raw_request: Mapping[str, Any]) -> str:
    source = _first_text(
        raw_request,
        (
            "approval_source",
            "operator_approval_marker",
            "path_approval_source_marker",
            "local_surface_ref",
            "source_request_id",
        ),
    )
    if source:
        return source[:180]
    if raw_request.get("approved_by_operator") is True:
        return "approved_by_operator:true"
    if raw_request.get("approved_pc_workbook_path_authorized") is True:
        return "approved_pc_workbook_path_authorized:true"
    return ""


def _operator_approved(raw_request: Mapping[str, Any]) -> bool:
    return (
        raw_request.get("operator_approved") is True
        or raw_request.get("approved_by_operator") is True
        or raw_request.get("approved_pc_workbook_path_authorized") is True
        or bool(_first_text(raw_request, ("operator_approval_marker", "path_approval_source_marker")))
    )


def _artifact_ref(raw_request: Mapping[str, Any], *, artifact_kind: str, scope_hash: str) -> str:
    explicit = _first_text(raw_request, ("artifact_ref", "workbook_ref", "workbook_registry_ref", "workbook_identity"))
    if explicit:
        return explicit
    label = _first_text(raw_request, ("artifact_label", "workbook_display_name", "file_display_name")) or artifact_kind
    return f"artifact_ref:{artifact_kind}:{scope_hash}:{_short_hash(label)}"


def scope_binding_from_request(raw_request: Mapping[str, Any]) -> ArtifactScopeBinding:
    world_ref = _safe_text(raw_request.get("world_ref"))
    workflow_ref = _safe_text(raw_request.get("workflow_ref"))
    client_ref = _safe_text(raw_request.get("client_ref"), "")
    project_ref = _safe_text(raw_request.get("project_ref") or raw_request.get("lane_ref"), "")
    tenant_ref = _safe_text(raw_request.get("tenant_ref"), "")
    missing: list[str] = []
    if world_ref == "unknown":
        missing.append("world_ref")
    if workflow_ref == "unknown":
        missing.append("workflow_ref")
    if not client_ref and not project_ref:
        missing.append("client_ref or project_ref")
    status = "ARTIFACT_SCOPE_BOUND" if not missing else "ARTIFACT_SCOPE_MISSING"
    scope_hash = _short_hash(world_ref, workflow_ref, client_ref, project_ref, tenant_ref)
    return ArtifactScopeBinding(
        binding_id=f"artifact_scope_binding:{scope_hash}",
        world_ref=world_ref,
        workflow_ref=workflow_ref,
        client_ref=client_ref,
        project_ref=project_ref,
        tenant_ref=tenant_ref,
        required_scope_keys=("world_ref", "workflow_ref", "client_ref_or_project_ref"),
        binding_status=status,
        scope_hash=scope_hash,
        next_safe_move="Provide explicit world/workflow and client or project scope." if missing else "Use this scope only for matching artifact approvals.",
    )


def _scope_mismatch(scope: ArtifactScopeBinding, expected_scope: Mapping[str, Any] | None) -> tuple[str, ...]:
    if not expected_scope:
        return ()
    mismatches: list[str] = []
    for key in ("world_ref", "workflow_ref", "client_ref", "project_ref"):
        expected = str(expected_scope.get(key) or "").strip()
        if not expected:
            continue
        actual = str(getattr(scope, key) or "").strip()
        if actual != expected:
            mismatches.append(f"{key}={expected}")
    return tuple(mismatches)


def reference_from_request(
    raw_request: Mapping[str, Any],
    *,
    artifact_kind_default: str = "local_artifact",
    intended_use_default: str = "local_artifact_reference",
    generated_at: str | None = None,
) -> tuple[LocalArtifactReference, ArtifactScopeBinding]:
    generated_at = generated_at or utc_now()
    scope = scope_binding_from_request(raw_request)
    artifact_kind = _safe_text(raw_request.get("artifact_kind") or raw_request.get("file_type"), artifact_kind_default)
    intended_use = _safe_text(raw_request.get("artifact_intended_use") or raw_request.get("intended_use"), intended_use_default)
    pc_path = _first_text(
        raw_request,
        (
            "pc_path",
            "approved_pc_readable_path",
            "approved_pc_workbook_path",
            "approved_local_workbook_path",
            "backend_readable_path",
        ),
    )
    approved_path_ref = _first_text(
        raw_request,
        (
            "approved_path_ref",
            "approved_pc_readable_path_ref",
            "approved_pc_workbook_path_ref",
            "backend_readable_ref",
        ),
    )
    mac_path = _first_text(raw_request, ("mac_path", "local_path_ref", "source_mac_path"))
    path_mapping_verified = raw_request.get("path_mapping_verified") is True or is_pc_readable_path_style(pc_path or approved_path_ref)
    operator_approved = _operator_approved(raw_request)
    approved_for_read = raw_request.get("approved_for_read") is True or bool(operator_approved and (pc_path or approved_path_ref))
    approved_for_write = raw_request.get("approved_for_write") is True or raw_request.get("write_allowed") is True
    body_read = _bool_from_request(raw_request, ("body_read", "workbook_body_read", "file_body_read"))
    content_extracted = _bool_from_request(
        raw_request,
        ("content_extracted", "spreadsheet_cell_read", "ocr_performed", "text_extracted"),
    )
    external_shared = _bool_from_request(raw_request, ("external_shared", "external_llm_shared", "external_model_shared"))
    path_translation_guessed = raw_request.get("path_translation_guessed") is True
    artifact_ref = _artifact_ref(raw_request, artifact_kind=artifact_kind, scope_hash=scope.scope_hash)
    return (
        LocalArtifactReference(
            artifact_ref=artifact_ref,
            artifact_kind=artifact_kind,
            artifact_label=_first_text(raw_request, ("artifact_label", "workbook_display_name", "file_display_name")) or artifact_kind,
            source_request_id=str(raw_request.get("request_id") or raw_request.get("source_request_id") or "unknown_request"),
            intended_use=intended_use,
            world_ref=scope.world_ref,
            workflow_ref=scope.workflow_ref,
            client_ref=scope.client_ref,
            project_ref=scope.project_ref,
            tenant_ref=scope.tenant_ref,
            local_surface_ref=_first_text(raw_request, ("local_surface_ref", "surface_request_id")),
            mac_path=mac_path,
            pc_path=pc_path,
            approved_path_ref=approved_path_ref,
            path_mapping_verified=path_mapping_verified,
            path_translation_guessed=path_translation_guessed,
            operator_approved=operator_approved,
            approved_for_read=approved_for_read,
            approved_for_write=approved_for_write,
            body_read=body_read,
            content_extracted=content_extracted,
            external_shared=external_shared,
            approval_timestamp=_first_text(raw_request, ("approval_timestamp", "created_at")) or generated_at,
            approval_source=_approval_source(raw_request),
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Use this artifact only after readiness is true for the matching workflow scope.",
        ),
        scope,
    )


def _readiness_status(
    reference: LocalArtifactReference,
    scope: ArtifactScopeBinding,
    *,
    expected_scope: Mapping[str, Any] | None = None,
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    missing: list[str] = []
    blockers: list[str] = []
    scope_mismatches = _scope_mismatch(scope, expected_scope)
    if scope.binding_status != "ARTIFACT_SCOPE_BOUND":
        missing.extend(item for item in scope.required_scope_keys if item != "client_ref_or_project_ref")
        if not scope.client_ref and not scope.project_ref:
            missing.append("client_ref or project_ref")
        blockers.append("artifact scope binding required")
        return "ARTIFACT_SCOPE_MISSING", tuple(dict.fromkeys(missing)), tuple(dict.fromkeys(blockers))
    if scope_mismatches:
        blockers.extend(scope_mismatches)
        return "ARTIFACT_SCOPE_MISMATCH", (), tuple(dict.fromkeys(blockers))
    if reference.path_translation_guessed:
        blockers.append("path translation guessed")
        return "ARTIFACT_PATH_TRANSLATION_GUESSED_BLOCKED", (), tuple(dict.fromkeys(blockers))
    if is_mac_visible_path(reference.pc_path) or is_mac_visible_path(reference.approved_path_ref):
        missing.append("approved PC-readable artifact path")
        blockers.append("Mac-visible path is not PC-readable approval")
        return "ARTIFACT_MAC_PATH_NOT_PC_READABLE", tuple(dict.fromkeys(missing)), tuple(dict.fromkeys(blockers))
    if not reference.pc_path and not reference.approved_path_ref:
        missing.append("approved PC-readable artifact path")
        return "ARTIFACT_PC_PATH_REQUIRED", tuple(dict.fromkeys(missing)), ()
    if not reference.path_mapping_verified:
        missing.append("verified PC-readable artifact path")
        blockers.append("path mapping not verified")
        return "ARTIFACT_PC_PATH_REQUIRED", tuple(dict.fromkeys(missing)), tuple(dict.fromkeys(blockers))
    if not reference.operator_approved or not reference.approved_for_read:
        missing.append("operator approval for read")
        return "ARTIFACT_APPROVAL_REQUIRED", tuple(dict.fromkeys(missing)), ()
    if reference.approved_for_write:
        blockers.append("write approval is not allowed in this contract")
        return "ARTIFACT_WRITE_AUTHORITY_BLOCKED", (), tuple(dict.fromkeys(blockers))
    if reference.body_read or reference.content_extracted:
        blockers.append("artifact body/content was already read or extracted")
        return "ARTIFACT_BODY_OR_CONTENT_ALREADY_READ_BLOCKED", (), tuple(dict.fromkeys(blockers))
    if reference.external_shared:
        blockers.append("artifact was externally shared")
        return "ARTIFACT_EXTERNAL_SHARE_BLOCKED", (), tuple(dict.fromkeys(blockers))
    return "ARTIFACT_READY_FOR_READ", (), ()


def evaluate_artifact_reference(
    raw_request: Mapping[str, Any],
    *,
    expected_scope: Mapping[str, Any] | None = None,
    artifact_kind_default: str = "local_artifact",
    intended_use_default: str = "local_artifact_reference",
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    reference, scope = reference_from_request(
        raw_request,
        artifact_kind_default=artifact_kind_default,
        intended_use_default=intended_use_default,
        generated_at=generated_at,
    )
    status, missing, blockers = _readiness_status(reference, scope, expected_scope=expected_scope)
    live_ready = status == "ARTIFACT_READY_FOR_READ"
    approved = (
        ApprovedReadableArtifact(
            approval_id=f"approved_readable_artifact:{_short_hash(reference.artifact_ref, reference.source_request_id)}",
            artifact_ref=reference.artifact_ref,
            artifact_kind=reference.artifact_kind,
            artifact_label=reference.artifact_label,
            intended_use=reference.intended_use,
            scope_binding=asdict(scope),
            source_request_id=reference.source_request_id,
            local_surface_ref=reference.local_surface_ref,
            mac_path=reference.mac_path,
            pc_path=reference.pc_path,
            approved_path_ref=reference.approved_path_ref
            or f"approved_artifact_path_ref:{_short_hash(reference.pc_path)}",
            path_mapping_verified=reference.path_mapping_verified,
            operator_approved=reference.operator_approved,
            approved_for_read=reference.approved_for_read,
            approved_for_write=reference.approved_for_write,
            body_read=reference.body_read,
            content_extracted=reference.content_extracted,
            external_shared=reference.external_shared,
            approval_timestamp=reference.approval_timestamp,
            approval_source=reference.approval_source,
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Use as a read gate only; do not write, extract, or dispatch.",
        )
        if live_ready
        else None
    )
    receipt = ArtifactApprovalReceipt(
        receipt_id=f"artifact_approval_receipt:{_short_hash(reference.artifact_ref, status)}",
        source_request_id=reference.source_request_id,
        artifact_ref=reference.artifact_ref,
        artifact_kind=reference.artifact_kind,
        receipt_status=status,
        operator_approved=reference.operator_approved,
        approved_for_read=reference.approved_for_read,
        approved_for_write=reference.approved_for_write,
        body_read=reference.body_read,
        content_extracted=reference.content_extracted,
        external_shared=reference.external_shared,
        path_mapping_verified=reference.path_mapping_verified,
        path_translation_guessed=reference.path_translation_guessed,
        validation_errors=blockers,
        missing_items=missing,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Proceed only when artifact readiness is true for the matching scope.",
    )
    readiness = ArtifactReadinessState(
        readiness_id=f"artifact_readiness:{_short_hash(reference.artifact_ref, status)}",
        readiness_status=status,
        artifact_ref=reference.artifact_ref,
        artifact_kind=reference.artifact_kind,
        intended_use=reference.intended_use,
        scope_binding_status=scope.binding_status,
        pc_readable_path_present=bool(reference.pc_path or reference.approved_path_ref),
        path_mapping_verified=reference.path_mapping_verified,
        operator_approved=reference.operator_approved,
        approved_for_read=reference.approved_for_read,
        approved_for_write=reference.approved_for_write,
        body_read=reference.body_read,
        content_extracted=reference.content_extracted,
        external_shared=reference.external_shared,
        live_read_ready=live_ready,
        missing_items=missing,
        blocking_reasons=blockers,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move=(
            "Artifact is ready for a future bounded read gate."
            if live_ready
            else "Capture an approved PC-readable artifact reference for the exact workflow scope."
        ),
    )
    payload = _build_payload(
        generated_at=generated_at,
        local_artifact_reference=reference,
        scope_binding=scope,
        approved_readable_artifact=approved,
        approval_receipt=receipt,
        readiness_state=readiness,
    )
    return payload


def _default_router() -> ArtifactReferenceRouter:
    handlers = (
        ArtifactReferenceHandlerRegistration(
            handler_id="finance.client_invoice_workbook.read_approval",
            handler_label="Finance client invoice workbook read approval",
            artifact_kind="invoice_workbook",
            intended_use="client_invoice_sheet_audit",
            world_refs=("finance",),
            client_or_project_required=True,
            next_safe_move="Record approved workbook read reference; do not open the workbook.",
        ),
        ArtifactReferenceHandlerRegistration(
            handler_id="music.local_project_file.read_approval",
            handler_label="Music local project file read approval",
            artifact_kind="music_project_file",
            intended_use="music_project_intake",
            world_refs=("music",),
            client_or_project_required=True,
            next_safe_move="Record approved local project file reference; do not open the file.",
        ),
        ArtifactReferenceHandlerRegistration(
            handler_id="guardian.protected_artifact.boundary_review",
            handler_label="Guardian protected artifact boundary review",
            artifact_kind="protected_artifact",
            intended_use="protected_boundary_review",
            world_refs=("*",),
            client_or_project_required=False,
            next_safe_move="Record protected artifact boundary only; do not read private content.",
        ),
    )
    return ArtifactReferenceRouter(
        router_id="artifact_reference_router:v0",
        contract_status="HANDLER_REGISTRATION_ONLY_NO_EXECUTION",
        registered_handlers=tuple(asdict(handler) for handler in handlers),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Register domain handlers behind this artifact approval boundary.",
    )


def _build_payload(
    *,
    generated_at: str,
    local_artifact_reference: LocalArtifactReference,
    scope_binding: ArtifactScopeBinding,
    approved_readable_artifact: ApprovedReadableArtifact | None,
    approval_receipt: ArtifactApprovalReceipt,
    readiness_state: ArtifactReadinessState,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "readiness_statuses": READINESS_STATUSES,
        "model_schemas": {
            "LocalArtifactReference": tuple(field.name for field in fields(LocalArtifactReference)),
            "ApprovedReadableArtifact": tuple(field.name for field in fields(ApprovedReadableArtifact)),
            "ArtifactApprovalReceipt": tuple(field.name for field in fields(ArtifactApprovalReceipt)),
            "ArtifactScopeBinding": tuple(field.name for field in fields(ArtifactScopeBinding)),
            "ArtifactReadinessState": tuple(field.name for field in fields(ArtifactReadinessState)),
            "ArtifactReferenceRouter": tuple(field.name for field in fields(ArtifactReferenceRouter)),
        },
        "local_artifact_reference": asdict(local_artifact_reference),
        "approved_readable_artifact": asdict(approved_readable_artifact) if approved_readable_artifact else None,
        "approved_artifacts": (asdict(approved_readable_artifact),) if approved_readable_artifact else (),
        "artifact_approval_receipt": asdict(approval_receipt),
        "artifact_scope_binding": asdict(scope_binding),
        "artifact_readiness_state": asdict(readiness_state),
        "artifact_reference_router": asdict(_default_router()),
        "fixture_artifact": "fixture" in local_artifact_reference.source_request_id.lower(),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "generic_artifact_reference_contract": True,
            "capital_hilton_fixture_only": False,
            "fixture_artifact_not_live_business_truth": "fixture" in local_artifact_reference.source_request_id.lower(),
            "scope_binding_required": True,
            "pc_readable_path_distinct_from_mac_path": True,
            "approved_for_read_distinct_from_write": True,
            "approved_for_write": local_artifact_reference.approved_for_write,
            "body_read_performed": False,
            "content_extracted": local_artifact_reference.content_extracted,
            "external_shared": local_artifact_reference.external_shared,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "file_open_performed": False,
            "path_existence_check_performed": False,
            "ocr_performed": False,
            "schema_inference_performed": False,
            "path_translation_guessed": local_artifact_reference.path_translation_guessed,
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
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": "",
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def load_existing_payload(export_root: Path = DEFAULT_EXPORT_ROOT) -> dict[str, Any] | None:
    path = Path(export_root) / JSON_EXPORT_NAME
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _scope_matches(artifact: Mapping[str, Any], *, world_ref: str, workflow_ref: str, client_ref: str = "", project_ref: str = "") -> bool:
    scope = artifact.get("scope_binding") if isinstance(artifact.get("scope_binding"), Mapping) else {}
    if scope.get("world_ref") != world_ref or scope.get("workflow_ref") != workflow_ref:
        return False
    if client_ref and scope.get("client_ref") != client_ref:
        return False
    if project_ref and scope.get("project_ref") != project_ref:
        return False
    return True


def find_approved_readable_artifact(
    payload: Mapping[str, Any] | None,
    *,
    world_ref: str,
    workflow_ref: str,
    client_ref: str = "",
    project_ref: str = "",
    artifact_kind: str = "",
    intended_use: str = "",
) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    candidates: list[Mapping[str, Any]] = []
    single = payload.get("approved_readable_artifact")
    if isinstance(single, Mapping):
        candidates.append(single)
    for item in payload.get("approved_artifacts") or ():
        if isinstance(item, Mapping):
            candidates.append(item)
    for artifact in candidates:
        if artifact_kind and artifact.get("artifact_kind") != artifact_kind:
            continue
        if intended_use and artifact.get("intended_use") != intended_use:
            continue
        if not _scope_matches(
            artifact,
            world_ref=world_ref,
            workflow_ref=workflow_ref,
            client_ref=client_ref,
            project_ref=project_ref,
        ):
            continue
        if (
            artifact.get("approved_for_read") is True
            and artifact.get("approved_for_write") is False
            and artifact.get("body_read") is False
            and artifact.get("content_extracted") is False
            and artifact.get("external_shared") is False
            and artifact.get("path_mapping_verified") is True
            and (artifact.get("pc_path") or artifact.get("approved_path_ref"))
        ):
            return dict(artifact)
    return None


def build_payload(*, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    return evaluate_artifact_reference(
        {
            "request_id": "local_artifact_reference_capital_hilton_fixture",
            "artifact_ref": "workbook_ref:client_invoice:capital_hilton:fixture",
            "artifact_kind": "invoice_workbook",
            "artifact_label": "Capital Hilton invoice workbook fixture",
            "intended_use": "client_invoice_sheet_audit",
            "world_ref": "finance",
            "workflow_ref": "capital_hilton_invoice_workflow",
            "client_ref": "capital_hilton",
            "approved_pc_readable_path": "/mnt/e/openclaw/fixtures/capital_hilton_invoice_workbook.xlsx",
            "path_mapping_verified": True,
            "operator_approved": True,
            "approved_for_read": True,
            "approved_for_write": False,
            "body_read": False,
            "content_extracted": False,
            "external_shared": False,
            "approval_source": "fixture_operator_approval",
            "created_at": generated_at,
        },
        expected_scope={
            "world_ref": "finance",
            "workflow_ref": "capital_hilton_invoice_workflow",
            "client_ref": "capital_hilton",
        },
        artifact_kind_default="invoice_workbook",
        intended_use_default="client_invoice_sheet_audit",
        generated_at=generated_at,
    )


def format_operator_markdown(payload: Mapping[str, Any]) -> str:
    readiness = payload.get("artifact_readiness_state") if isinstance(payload.get("artifact_readiness_state"), Mapping) else {}
    reference = payload.get("local_artifact_reference") if isinstance(payload.get("local_artifact_reference"), Mapping) else {}
    lines = [
        "# Local Artifact Reference",
        "",
        "ELIOPERATOR: Approved PC-readable artifact reference contract only. No file body, workbook cells, OCR, schema inference, path guessing, external share, model call, workflow execution, credentials, browser, email, Coupa, or network action occurred.",
        "",
        f"- Status: `{readiness.get('readiness_status', 'UNKNOWN')}`",
        f"- Artifact kind: `{reference.get('artifact_kind', 'unknown')}`",
        f"- Intended use: `{reference.get('intended_use', 'unknown')}`",
        f"- Scope: `{reference.get('world_ref', 'unknown')} / {reference.get('workflow_ref', 'unknown')} / {reference.get('client_ref') or reference.get('project_ref') or 'unknown'}`",
        f"- Ready for read gate: `{readiness.get('live_read_ready', False)}`",
        f"- Missing: `{', '.join(readiness.get('missing_items') or ()) or 'none'}`",
        "",
        "## Next",
        "",
        str(readiness.get("next_safe_move") or "Capture an approved PC-readable artifact reference."),
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
    readiness = payload.get("artifact_readiness_state") if isinstance(payload.get("artifact_readiness_state"), Mapping) else {}
    proof = payload.get("machine_proof") if isinstance(payload.get("machine_proof"), Mapping) else {}
    return {
        "read_model_id": payload.get("read_model_id"),
        "contract_status": payload.get("contract_status"),
        "json_path": paths[0].as_posix(),
        "operator_path": paths[1].as_posix(),
        "readiness_status": readiness.get("readiness_status"),
        "live_read_ready": readiness.get("live_read_ready"),
        "missing_items": readiness.get("missing_items"),
        "all_live_authority_false": proof.get("all_live_authority_false"),
        "content_hash": proof.get("content_hash"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the approved local artifact reference read-model.")
    parser.add_argument("--format", choices=("json", "summary"), default="json")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    args = parser.parse_args(argv)

    export_root = Path(args.export_root)
    payload = build_payload(generated_at=args.generated_at)
    paths = write_exports(payload, export_root)
    output: Mapping[str, Any] = payload if args.format == "json" else build_summary(payload, paths)
    sys.stdout.write(stable_json(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
