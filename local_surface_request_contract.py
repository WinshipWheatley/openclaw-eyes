"""Local surface request contract v0.

This module converts backend next-step guidance into a safe, machine-readable
local UI/surface request for device apps. It does not implement UI, launch
apps, call device APIs, read private files, or perform external actions.
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

SCHEMA_VERSION = "local_surface_request_contract_v0"
READ_MODEL_ID = "local_surface_request_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_LOCAL_SURFACE_REQUEST_CONTRACT_NO_DEVICE_ACTION"

LOCAL_SURFACE_REQUEST_TYPES = (
    "OPEN_FILE_PICKER",
    "OPEN_PHOTO_PICKER",
    "OPEN_CAMERA",
    "SHOW_FIELD_MAPPING_PANEL",
    "SHOW_CONFIRMATION_CARD",
    "SHOW_PACKAGE_PREVIEW",
    "SHOW_TROUBLESHOOTING_CARD",
    "NO_SURFACE_REQUEST",
)

DEVICE_TYPES = ("mac", "iphone", "ipad", "android", "windows", "linux", "unknown")
PATH_REF_STYLES = (
    "mac_posix",
    "ios_security_scoped_url",
    "android_uri",
    "windows_path",
    "wsl_path",
    "linux_path",
    "backend_readable_ref",
    "metadata_only_ref",
    "unknown",
)

AUTHORITY_BOUNDARY = {
    "local_ui_implementation_allowed": False,
    "app_launch_allowed": False,
    "mac_api_call_allowed": False,
    "browser_allowed": False,
    "network_allowed": False,
    "file_body_read_allowed": False,
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "ocr_allowed": False,
    "email_send_allowed": False,
    "gmail_send_allowed": False,
    "coupa_access_allowed": False,
    "coupa_submit_allowed": False,
    "credential_handling_allowed": False,
    "model_call_allowed": False,
    "agent_dispatch_allowed": False,
    "workflow_execution_allowed": False,
    "external_action_allowed": False,
    "raw_body_ingestion_allowed": False,
    "path_translation_guess_allowed": False,
    "send_submit_allowed": False,
}


@dataclass(frozen=True)
class LocalSurfaceRequestType:
    surface_type: str
    human_label: str
    description: str
    default_safe_to_auto_open: bool
    requires_operator_confirmation: bool


@dataclass(frozen=True)
class DeviceLocalCapability:
    capability_id: str
    surface_type: str
    supported_device_types: tuple[str, ...]
    supported_path_ref_styles: tuple[str, ...]
    local_only: bool
    external_model_share_allowed: bool
    external_action_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class DeviceContext:
    device_context_id: str
    device_type_target: str
    device_type_allowed: tuple[str, ...]
    path_ref_styles_allowed: tuple[str, ...]
    unknown_device_degrades_to_guidance: bool
    local_only: bool
    next_safe_move: str


@dataclass(frozen=True)
class LocalSurfaceRequestResultExpectation:
    expectation_id: str
    accepted_result_type: str
    result_must_be_local_metadata_only: bool
    raw_body_allowed: bool
    path_translation_guess_allowed: bool
    external_model_share_allowed: bool
    validation_required_before_next_action: bool
    next_safe_move: str


@dataclass(frozen=True)
class LocalSurfaceRequestPolicy:
    policy_id: str
    supported_surface_request_types: tuple[str, ...]
    supported_device_types: tuple[str, ...]
    supported_path_ref_styles: tuple[str, ...]
    raw_body_allowed_default: bool
    external_model_share_allowed_default: bool
    arbitrary_scan_allowed_default: bool
    path_translation_guess_allowed_default: bool
    external_action_allowed_default: bool
    local_only_default: bool
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class LocalSurfaceRequest:
    request_id: str
    surface_type: str
    human_label: str
    human_reason: str
    concise_spoken_guidance: str
    device_type_target: str
    device_type_allowed: tuple[str, ...]
    input_requirements: tuple[dict[str, Any], ...]
    allowed_file_types: tuple[str, ...]
    allowed_file_extensions: tuple[str, ...]
    accepted_result_type: str
    world_ref: str
    client_ref: str
    workflow_ref: str
    related_contract_ref: str
    authority_boundary: dict[str, bool]
    raw_body_allowed: bool
    external_model_share_allowed: bool
    arbitrary_scan_allowed: bool
    path_translation_guess_allowed: bool
    external_action_allowed: bool
    local_only: bool
    requires_operator_confirmation: bool
    safe_to_auto_open: bool
    fallback_if_unavailable: str
    troubleshooting_code: str
    result_expectation: dict[str, Any]


@dataclass(frozen=True)
class LocalSurfaceRequestReadback:
    readback_id: str
    status: str
    operator_headline: str
    operator_message: str
    example_count: int
    default_surface_type: str
    validation_errors: tuple[str, ...]
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


def _surface_type(surface_type: str) -> str:
    text = str(surface_type or "").strip().upper()
    return text if text in LOCAL_SURFACE_REQUEST_TYPES else "NO_SURFACE_REQUEST"


def _device_type(device_type: object) -> str:
    text = str(device_type or "unknown").strip().lower()
    return text if text in DEVICE_TYPES else "unknown"


def default_policy() -> LocalSurfaceRequestPolicy:
    return LocalSurfaceRequestPolicy(
        policy_id="local_surface_request_policy:v0",
        supported_surface_request_types=LOCAL_SURFACE_REQUEST_TYPES,
        supported_device_types=DEVICE_TYPES,
        supported_path_ref_styles=PATH_REF_STYLES,
        raw_body_allowed_default=False,
        external_model_share_allowed_default=False,
        arbitrary_scan_allowed_default=False,
        path_translation_guess_allowed_default=False,
        external_action_allowed_default=False,
        local_only_default=True,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Return local surface requests beside human next_action; device apps return metadata/result receipts.",
    )


def surface_request_types() -> tuple[LocalSurfaceRequestType, ...]:
    return (
        LocalSurfaceRequestType("OPEN_FILE_PICKER", "Choose a file", "Open a local file picker for metadata-only selection.", True, False),
        LocalSurfaceRequestType("OPEN_PHOTO_PICKER", "Choose photos", "Open a local photo picker for metadata-only media selection.", True, False),
        LocalSurfaceRequestType("OPEN_CAMERA", "Use camera", "Open local capture only when an explicit local capture context exists.", False, True),
        LocalSurfaceRequestType("SHOW_FIELD_MAPPING_PANEL", "Map fields", "Show a local field mapping surface.", True, False),
        LocalSurfaceRequestType("SHOW_CONFIRMATION_CARD", "Confirm this plan", "Show a local confirmation card; no execution authority is granted.", False, True),
        LocalSurfaceRequestType("SHOW_PACKAGE_PREVIEW", "Review the package", "Show a local package preview; no dispatch authority is granted.", True, False),
        LocalSurfaceRequestType("SHOW_TROUBLESHOOTING_CARD", "Fix access", "Show a blocked-state troubleshooting card without automatic repair.", True, False),
        LocalSurfaceRequestType("NO_SURFACE_REQUEST", "Review the response", "No local surface should open automatically.", False, False),
    )


def capabilities() -> tuple[DeviceLocalCapability, ...]:
    return tuple(
        DeviceLocalCapability(
            capability_id=f"device_local_capability:{surface.surface_type.lower()}",
            surface_type=surface.surface_type,
            supported_device_types=DEVICE_TYPES,
            supported_path_ref_styles=PATH_REF_STYLES,
            local_only=True,
            external_model_share_allowed=False,
            external_action_allowed=False,
            next_safe_move="Render locally only and return metadata/receipt to backend.",
        )
        for surface in surface_request_types()
    )


def result_expectation_for(surface_type: str, accepted_result_type: str) -> LocalSurfaceRequestResultExpectation:
    surface = _surface_type(surface_type)
    default_result = {
        "OPEN_FILE_PICKER": "file_metadata_manifest",
        "OPEN_PHOTO_PICKER": "photo_metadata_manifest",
        "OPEN_CAMERA": "local_capture_metadata_manifest",
        "SHOW_FIELD_MAPPING_PANEL": "field_mapping_manifest",
        "SHOW_CONFIRMATION_CARD": "operator_confirmation_receipt",
        "SHOW_PACKAGE_PREVIEW": "package_preview_receipt",
        "SHOW_TROUBLESHOOTING_CARD": "troubleshooting_receipt",
        "NO_SURFACE_REQUEST": "no_result_expected",
    }[surface]
    result_type = accepted_result_type or default_result
    return LocalSurfaceRequestResultExpectation(
        expectation_id=f"local_surface_result_expectation:{_short_hash(surface, result_type)}",
        accepted_result_type=result_type,
        result_must_be_local_metadata_only=surface in {"OPEN_FILE_PICKER", "OPEN_PHOTO_PICKER", "OPEN_CAMERA"},
        raw_body_allowed=False,
        path_translation_guess_allowed=False,
        external_model_share_allowed=False,
        validation_required_before_next_action=True,
        next_safe_move="Device app returns local metadata/manifest/receipt; backend validates before further action.",
    )


def make_surface_request(
    *,
    surface_type: str,
    human_label: str,
    human_reason: str,
    concise_spoken_guidance: str,
    device_type_target: str = "mac",
    device_type_allowed: tuple[str, ...] = ("mac",),
    input_requirements: tuple[dict[str, Any], ...] = (),
    allowed_file_types: tuple[str, ...] = (),
    allowed_file_extensions: tuple[str, ...] = (),
    accepted_result_type: str = "",
    world_ref: str = "unknown",
    client_ref: str = "unknown",
    workflow_ref: str = "unknown",
    related_contract_ref: str = "",
    requires_operator_confirmation: bool = False,
    safe_to_auto_open: bool = True,
    fallback_if_unavailable: str = "Show the human next action and wait for operator input.",
    troubleshooting_code: str = "",
) -> LocalSurfaceRequest:
    surface = _surface_type(surface_type)
    device_target = _device_type(device_type_target)
    allowed_devices = tuple(_device_type(item) for item in device_type_allowed) or ("unknown",)
    if device_target == "unknown":
        safe_to_auto_open = False
        fallback_if_unavailable = "Unknown device type: show human-readable guidance only."
    if surface in {"SHOW_CONFIRMATION_CARD", "OPEN_CAMERA"}:
        requires_operator_confirmation = True
        safe_to_auto_open = False
    if surface == "NO_SURFACE_REQUEST":
        safe_to_auto_open = False
        requires_operator_confirmation = False
    expectation = result_expectation_for(surface, accepted_result_type)
    return LocalSurfaceRequest(
        request_id=f"local_surface_request:{_short_hash(surface, human_label, workflow_ref, related_contract_ref)}",
        surface_type=surface,
        human_label=human_label,
        human_reason=human_reason,
        concise_spoken_guidance=concise_spoken_guidance,
        device_type_target=device_target,
        device_type_allowed=allowed_devices,
        input_requirements=input_requirements,
        allowed_file_types=allowed_file_types,
        allowed_file_extensions=allowed_file_extensions,
        accepted_result_type=expectation.accepted_result_type,
        world_ref=world_ref or "unknown",
        client_ref=client_ref or "unknown",
        workflow_ref=workflow_ref or "unknown",
        related_contract_ref=related_contract_ref,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        raw_body_allowed=False,
        external_model_share_allowed=False,
        arbitrary_scan_allowed=False,
        path_translation_guess_allowed=False,
        external_action_allowed=False,
        local_only=True,
        requires_operator_confirmation=requires_operator_confirmation,
        safe_to_auto_open=safe_to_auto_open,
        fallback_if_unavailable=fallback_if_unavailable,
        troubleshooting_code=troubleshooting_code,
        result_expectation=asdict(expectation),
    )


def validate_surface_request(request: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    surface = _surface_type(str(request.get("surface_type") or ""))
    if surface != request.get("surface_type"):
        errors.append("UNKNOWN_SURFACE_TYPE")
    if request.get("raw_body_allowed") is not False:
        errors.append("RAW_BODY_NOT_ALLOWED")
    if request.get("external_model_share_allowed") is not False:
        errors.append("EXTERNAL_MODEL_SHARE_NOT_ALLOWED")
    if request.get("arbitrary_scan_allowed") is not False:
        errors.append("ARBITRARY_SCAN_NOT_ALLOWED")
    if request.get("path_translation_guess_allowed") is not False:
        errors.append("PATH_TRANSLATION_GUESS_NOT_ALLOWED")
    if request.get("external_action_allowed") is not False:
        errors.append("EXTERNAL_ACTION_NOT_ALLOWED")
    if request.get("local_only") is not True:
        errors.append("LOCAL_ONLY_REQUIRED")
    authority = request.get("authority_boundary") if isinstance(request.get("authority_boundary"), Mapping) else {}
    if any(value is True for value in authority.values()):
        errors.append("LIVE_AUTHORITY_NOT_ALLOWED")
    if surface == "OPEN_FILE_PICKER" and request.get("raw_body_allowed") is not False:
        errors.append("FILE_PICKER_RAW_BODY_BLOCKED")
    if surface == "OPEN_PHOTO_PICKER" and request.get("external_model_share_allowed") is not False:
        errors.append("PHOTO_PICKER_EXTERNAL_MODEL_SHARE_BLOCKED")
    if surface == "OPEN_CAMERA" and request.get("requires_operator_confirmation") is not True:
        errors.append("CAMERA_REQUIRES_EXPLICIT_LOCAL_CAPTURE_CONTEXT")
    if surface == "SHOW_CONFIRMATION_CARD" and request.get("external_action_allowed") is not False:
        errors.append("CONFIRMATION_CARD_CANNOT_EXECUTE")
    if surface == "SHOW_PACKAGE_PREVIEW" and (
        authority.get("agent_dispatch_allowed") is True or authority.get("model_call_allowed") is True
    ):
        errors.append("PACKAGE_PREVIEW_CANNOT_DISPATCH")
    if surface == "SHOW_TROUBLESHOOTING_CARD" and request.get("safe_to_auto_open") is not True:
        errors.append("TROUBLESHOOTING_CARD_SHOULD_SHOW_LOCAL_GUIDANCE_ONLY")
    return tuple(dict.fromkeys(errors))


def capital_hilton_workbook_file_request() -> LocalSurfaceRequest:
    return make_surface_request(
        surface_type="OPEN_FILE_PICKER",
        human_label="Choose the invoice workbook",
        human_reason="OpenClaw needs the local workbook file reference.",
        concise_spoken_guidance="Choose the invoice workbook. The file body will not be read.",
        input_requirements=(
            {"field": "invoice_workbook_file", "required": True, "result": "metadata/manifest only"},
        ),
        allowed_file_types=("spreadsheet",),
        allowed_file_extensions=(".xlsx", ".xlsm", ".xls", ".csv"),
        accepted_result_type="file_metadata_manifest",
        world_ref="finance",
        client_ref="capital_hilton",
        workflow_ref="capital_hilton_invoice_workflow",
        related_contract_ref="client_invoice_audit_handoff",
    )


def capital_hilton_field_mapping_request() -> LocalSurfaceRequest:
    return make_surface_request(
        surface_type="SHOW_FIELD_MAPPING_PANEL",
        human_label="Tell OpenClaw where the fields are",
        human_reason="OpenClaw needs the invoice tab name and whitelisted field mapping before auditing cells.",
        concise_spoken_guidance="Tell OpenClaw where the invoice fields are.",
        input_requirements=(
            {"field": "sheet_tab_name", "required": True},
            {"field": "invoice_number", "required": True},
            {"field": "performance_dates", "required": True},
            {"field": "rate", "required": True},
            {"field": "subtotal_or_total", "required": True},
            {"field": "po_reference", "required": True},
            {"field": "notes_status", "required": False},
            {"field": "formula_policy", "required": True, "default": "operator_confirmation_required"},
        ),
        accepted_result_type="field_mapping_manifest",
        world_ref="finance",
        client_ref="capital_hilton",
        workflow_ref="capital_hilton_invoice_workflow",
        related_contract_ref="client_invoice_audit_handoff",
    )


def capital_hilton_confirmation_request() -> LocalSurfaceRequest:
    return make_surface_request(
        surface_type="SHOW_CONFIRMATION_CARD",
        human_label="Confirm the safe plan",
        human_reason="OpenClaw inferred a workflow plan and needs operator confirmation before preparing backend contracts.",
        concise_spoken_guidance="Confirm the safe plan before OpenClaw prepares contracts.",
        input_requirements=({"field": "operator_confirmation", "required": True},),
        accepted_result_type="operator_confirmation_receipt",
        world_ref="finance",
        client_ref="capital_hilton",
        workflow_ref="capital_hilton_invoice_workflow",
        related_contract_ref="deterministic_intent_interpreter",
        requires_operator_confirmation=True,
        safe_to_auto_open=False,
    )


def capital_hilton_blocked_path_request() -> LocalSurfaceRequest:
    return make_surface_request(
        surface_type="SHOW_TROUBLESHOOTING_CARD",
        human_label="Fix file access",
        human_reason="Current path is Mac-visible only; backend needs approved PC-readable path/ref or local snapshot handoff.",
        concise_spoken_guidance="Fix file access. OpenClaw will not guess path translation.",
        input_requirements=(
            {"field": "approved_pc_readable_path_or_ref", "required": True},
            {"field": "operator_approval_marker", "required": True},
        ),
        accepted_result_type="troubleshooting_receipt",
        world_ref="finance",
        client_ref="capital_hilton",
        workflow_ref="capital_hilton_invoice_workflow",
        related_contract_ref="client_invoice_audit_handoff",
        troubleshooting_code="APPROVED_PC_PATH_REQUIRED",
    )


def cross_domain_examples() -> dict[str, dict[str, Any]]:
    examples = {
        "music_niles_project_picker": make_surface_request(
            surface_type="OPEN_FILE_PICKER",
            human_label="Choose the project file",
            human_reason="Niles needs a local project or audio file reference, not file contents.",
            concise_spoken_guidance="Choose the local project file.",
            allowed_file_types=("audio_project", "audio_file"),
            allowed_file_extensions=(".logicx", ".als", ".wav", ".aiff", ".mp3"),
            accepted_result_type="file_metadata_manifest",
            world_ref="music",
            client_ref="unknown",
            workflow_ref="niles_local_project_review",
            related_contract_ref="niles_future_local_project_context",
        ),
        "video_package_preview": make_surface_request(
            surface_type="SHOW_PACKAGE_PREVIEW",
            human_label="Review the package",
            human_reason="Show a local livestream setup checklist/package preview without dispatching providers.",
            concise_spoken_guidance="Review the local setup package.",
            accepted_result_type="package_preview_receipt",
            world_ref="video",
            workflow_ref="local_livestream_setup",
            related_contract_ref="visual_event_package",
        ),
        "photos_picker": make_surface_request(
            surface_type="OPEN_PHOTO_PICKER",
            human_label="Choose photos",
            human_reason="Open a local photo picker and return metadata/selection receipts only.",
            concise_spoken_guidance="Choose photos locally.",
            allowed_file_types=("image",),
            allowed_file_extensions=(".png", ".jpg", ".jpeg", ".heic", ".webp"),
            accepted_result_type="photo_metadata_manifest",
            world_ref="media",
            workflow_ref="local_media_selection",
        ),
        "admin_cassandra_confirmation": make_surface_request(
            surface_type="SHOW_CONFIRMATION_CARD",
            human_label="Confirm this plan",
            human_reason="Cassandra can prepare a local draft/package contract only; no send authority is granted.",
            concise_spoken_guidance="Confirm the draft plan. Nothing will send.",
            accepted_result_type="operator_confirmation_receipt",
            world_ref="admin",
            workflow_ref="cassandra_draft_package",
            related_contract_ref="draft_package_future",
            requires_operator_confirmation=True,
            safe_to_auto_open=False,
        ),
        "guardian_protected_file_boundary": make_surface_request(
            surface_type="SHOW_TROUBLESHOOTING_CARD",
            human_label="Fix file access",
            human_reason="Guardian needs a protected-file boundary card before any private file handling.",
            concise_spoken_guidance="Review the protected-file boundary.",
            accepted_result_type="protected_boundary_receipt",
            world_ref="guardian",
            workflow_ref="protected_file_boundary",
            related_contract_ref="guardian_protected_intake_future",
            troubleshooting_code="PROTECTED_FILE_BOUNDARY_REQUIRED",
        ),
    }
    return {name: asdict(value) for name, value in examples.items()}


def no_surface_request(*, next_action: str = "Review the response.", device_type: str = "unknown") -> LocalSurfaceRequest:
    return make_surface_request(
        surface_type="NO_SURFACE_REQUEST",
        human_label="Review the response",
        human_reason="No device-local surface should open automatically.",
        concise_spoken_guidance=next_action,
        device_type_target=device_type,
        device_type_allowed=(device_type if _device_type(device_type) != "unknown" else "unknown",),
        accepted_result_type="no_result_expected",
        safe_to_auto_open=False,
    )


def infer_surface_request(response_payload: Mapping[str, Any]) -> dict[str, Any]:
    detail = response_payload.get("detail_disclosure") if isinstance(response_payload.get("detail_disclosure"), Mapping) else {}
    layered_kind = str(response_payload.get("response_kind") or "")
    next_action = str(response_payload.get("next_action") or response_payload.get("next_safe_move") or "")
    lowered = f"{layered_kind} {next_action} {response_payload.get('headline') or ''}".lower()

    audit_handoff = detail.get("client_invoice_audit_handoff") if isinstance(detail.get("client_invoice_audit_handoff"), Mapping) else {}
    if audit_handoff:
        readback = audit_handoff.get("audit_handoff_readback") if isinstance(audit_handoff.get("audit_handoff_readback"), Mapping) else {}
        path_status = str(readback.get("path_approval_status") or "")
        schema_status = str(readback.get("schema_mapping_status") or "")
        if schema_status not in {"SHEET_AUDIT_SCHEMA_CAPTURED"} and path_status == "APPROVED_PC_PATH_CAPTURED":
            return asdict(capital_hilton_field_mapping_request())
        if path_status in {"APPROVED_PC_PATH_REQUIRED", "APPROVED_PC_PATH_REJECTED_MAC_VISIBLE"}:
            return asdict(capital_hilton_blocked_path_request())
        if bool(audit_handoff.get("live_audit_ready")):
            return asdict(capital_hilton_confirmation_request())

    sheet_audit = detail.get("client_invoice_sheet_audit") if isinstance(detail.get("client_invoice_sheet_audit"), Mapping) else {}
    if sheet_audit:
        result = sheet_audit.get("audit_result") if isinstance(sheet_audit.get("audit_result"), Mapping) else {}
        status = str(result.get("status") or "")
        if status in {"APPROVED_PC_PATH_REQUIRED", "SHEET_AUDIT_WORKBOOK_PATH_MISSING"}:
            return asdict(capital_hilton_blocked_path_request())
        if status == "SHEET_AUDIT_SCHEMA_MISSING":
            return asdict(capital_hilton_field_mapping_request())

    if "provide the invoice tab name and cell mapping" in lowered or "field mapping" in lowered:
        return asdict(capital_hilton_field_mapping_request())
    if "choose the invoice workbook" in lowered or "provide approved pc-readable workbook access" in lowered:
        return asdict(capital_hilton_workbook_file_request())
    if "confirm" in lowered and "plan" in lowered:
        return asdict(capital_hilton_confirmation_request())
    return asdict(no_surface_request(next_action=next_action))


def build_examples() -> dict[str, dict[str, Any]]:
    examples = {
        "capital_hilton_need_workbook_file": asdict(capital_hilton_workbook_file_request()),
        "capital_hilton_need_field_mapping": asdict(capital_hilton_field_mapping_request()),
        "capital_hilton_need_confirmation": asdict(capital_hilton_confirmation_request()),
        "capital_hilton_blocked_path": asdict(capital_hilton_blocked_path_request()),
        **cross_domain_examples(),
    }
    return examples


def build_payload(*, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    examples = build_examples()
    validation = {name: validate_surface_request(example) for name, example in examples.items()}
    policy = default_policy()
    readback = LocalSurfaceRequestReadback(
        readback_id=f"local_surface_request_readback:{_short_hash(SCHEMA_VERSION, len(examples))}",
        status="LOCAL_SURFACE_REQUEST_CONTRACT_READY",
        operator_headline="Local surface contract ready",
        operator_message="OpenClaw can return local surface requests beside human next actions. Device apps still act locally and return metadata or receipts.",
        example_count=len(examples),
        default_surface_type="NO_SURFACE_REQUEST",
        validation_errors=tuple(error for errors in validation.values() for error in errors),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Use local_surface_request beside next_action; backend validates returned metadata before any further action.",
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "model_schemas": {
            "LocalSurfaceRequestType": tuple(field.name for field in fields(LocalSurfaceRequestType)),
            "DeviceLocalCapability": tuple(field.name for field in fields(DeviceLocalCapability)),
            "DeviceContext": tuple(field.name for field in fields(DeviceContext)),
            "LocalSurfaceRequestPolicy": tuple(field.name for field in fields(LocalSurfaceRequestPolicy)),
            "LocalSurfaceRequest": tuple(field.name for field in fields(LocalSurfaceRequest)),
            "LocalSurfaceRequestResultExpectation": tuple(field.name for field in fields(LocalSurfaceRequestResultExpectation)),
            "LocalSurfaceRequestReadback": tuple(field.name for field in fields(LocalSurfaceRequestReadback)),
        },
        "surface_request_types": tuple(asdict(item) for item in surface_request_types()),
        "device_local_capabilities": tuple(asdict(item) for item in capabilities()),
        "policy": asdict(policy),
        "examples": examples,
        "example_validation": validation,
        "readback": asdict(readback),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "structured_surface_contract_present": True,
            "human_next_action_preserved": True,
            "capital_hilton_examples_present": all(
                key in examples
                for key in (
                    "capital_hilton_need_workbook_file",
                    "capital_hilton_need_field_mapping",
                    "capital_hilton_need_confirmation",
                    "capital_hilton_blocked_path",
                )
            ),
            "cross_domain_examples_present": all(
                key in examples
                for key in (
                    "music_niles_project_picker",
                    "video_package_preview",
                    "photos_picker",
                    "admin_cassandra_confirmation",
                    "guardian_protected_file_boundary",
                )
            ),
            "all_examples_validate": all(not errors for errors in validation.values()),
            "raw_body_allowed_default_false": policy.raw_body_allowed_default is False,
            "external_model_share_allowed_default_false": policy.external_model_share_allowed_default is False,
            "local_only_default_true": policy.local_only_default is True,
            "path_translation_guess_allowed_default_false": policy.path_translation_guess_allowed_default is False,
            "device_ui_implemented": False,
            "app_launch_performed": False,
            "mac_api_call_performed": False,
            "browser_access_performed": False,
            "network_used": False,
            "file_body_read_performed": False,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "ocr_performed": False,
            "email_send_performed": False,
            "gmail_send_performed": False,
            "coupa_access_or_submit_performed": False,
            "credential_handling_performed": False,
            "model_call_performed": False,
            "agent_dispatch_performed": False,
            "workflow_execution_performed": False,
            "external_action_performed": False,
            "path_translation_guess_performed": False,
            "send_submit_performed": False,
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": "",
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: Mapping[str, Any]) -> str:
    readback = payload.get("readback") if isinstance(payload.get("readback"), Mapping) else {}
    examples = payload.get("examples") if isinstance(payload.get("examples"), Mapping) else {}
    lines = [
        "# Local Surface Request Contract",
        "",
        "ELIOPERATOR: Structured local surface requests only. No UI was implemented, no app was launched, no files were read, no network/model/agent/workflow action occurred.",
        "",
        f"- Status: `{readback.get('status', 'UNKNOWN')}`",
        f"- Examples: `{len(examples)}`",
        f"- Default surface: `{readback.get('default_surface_type', 'NO_SURFACE_REQUEST')}`",
        "",
        "## Example Labels",
        "",
        *[f"- {example.get('human_label', 'Surface request')}: `{example.get('surface_type', 'UNKNOWN')}`" for example in examples.values()],
        "",
        "## Next",
        "",
        str(readback.get("next_safe_move") or "Return local_surface_request beside human next_action."),
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
    proof = payload.get("machine_proof") if isinstance(payload.get("machine_proof"), Mapping) else {}
    return {
        "read_model_id": payload.get("read_model_id"),
        "contract_status": payload.get("contract_status"),
        "json_path": paths[0].as_posix(),
        "operator_path": paths[1].as_posix(),
        "example_count": len(payload.get("examples") or {}),
        "all_examples_validate": proof.get("all_examples_validate"),
        "raw_body_allowed_default_false": proof.get("raw_body_allowed_default_false"),
        "external_model_share_allowed_default_false": proof.get("external_model_share_allowed_default_false"),
        "local_only_default_true": proof.get("local_only_default_true"),
        "all_live_authority_false": proof.get("all_live_authority_false"),
        "content_hash": proof.get("content_hash"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export local surface request contract.")
    parser.add_argument("--format", choices=("json", "summary"), default="json")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    args = parser.parse_args(argv)

    payload = build_payload(generated_at=args.generated_at)
    paths = write_exports(payload, Path(args.export_root))
    output: Mapping[str, Any] = payload if args.format == "json" else build_summary(payload, paths)
    sys.stdout.write(stable_json(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
