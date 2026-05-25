"""Deterministic file-metadata intake adapter v0.

This module accepts a Mission Control file-intake request JSON object and turns
safe metadata into an operator file source ref readback. It does not open,
parse, OCR, hash file contents, ingest raw bodies, scan folders, automate apps,
call models, access external systems, handle credentials, mutate Mission
Control Swift, run Mac sync/import, or push.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
APPROVED_INBOX = Path("/mnt/e/openclaw/mission_control_capture_requests/inbox")
REQUEST_FILENAME_PATTERN = "mission_control_file_intake_request_*.json"

SCHEMA_VERSION = "operator_file_metadata_intake_v0"
READ_MODEL_ID = "operator_file_metadata_readback"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_METADATA_ONLY_FILE_INTAKE_ADAPTER"

SUPPORTED_INTAKE_MODES = (
    "REFERENCE_ONLY",
    "METADATA_ONLY",
    "PROTECTED_EVIDENCE_REFERENCE",
    "VISUAL_WORKSPACE_SOURCE",
    "SAFE_EXTRACT_REQUESTED_FUTURE_GATED",
)

READBACK_STATUSES = (
    "SOURCE_REF_CREATED",
    "DUPLICATE_NOOP",
    "BLOCKED_INVALID_REQUEST",
    "BLOCKED_UNSUPPORTED_FILE_TYPE",
    "BLOCKED_RAW_BODY_INCLUDED",
    "BLOCKED_UNSCOPED_FOLDER_SCAN",
    "NO_REQUEST_AVAILABLE",
    "UNKNOWN_FAIL_CLOSED",
)

RECEIPT_STATUSES = (
    "METADATA_CAPTURED",
    "DUPLICATE_NOOP",
    "REQUEST_BLOCKED",
    "NO_PERSISTENT_REGISTRY_WRITE",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "RAW_FILE_BODY_INCLUDED",
    "RAW_FILE_BODY_READ_ATTEMPTED",
    "UNSCOPED_FOLDER_SCAN",
    "PRIVATE_PATH_VISIBLE_IN_NORMAL_READMODEL",
    "UNSUPPORTED_FILE_TYPE",
    "MISSING_IDEMPOTENCY_KEY",
    "MISSING_PAYLOAD_HASH",
    "EXTRACTION_REQUEST_NOT_GATED",
    "PROTECTED_FILE_WITHOUT_GUARDIAN",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_file_body_ingestion_allowed": False,
    "live_raw_body_extraction_allowed": False,
    "live_ocr_allowed": False,
    "live_spreadsheet_parse_allowed": False,
    "live_pdf_parse_allowed": False,
    "live_image_analysis_allowed": False,
    "live_folder_scan_allowed": False,
    "live_app_automation_allowed": False,
    "live_external_action_allowed": False,
    "live_model_call_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

REQUIRED_REQUEST_FIELDS = (
    "request_id",
    "origin_surface",
    "source_channel",
    "workflow_ref",
    "world_ref",
    "lane_ref",
    "client_ref",
    "tenant_ref",
    "operator_goal",
    "file_display_name",
    "file_kind_hint",
    "file_size_bytes",
    "file_extension",
    "privacy_class",
    "requested_intake_mode",
    "idempotency_key",
    "payload_hash",
    "authority_boundary",
    "created_at",
)

REQUIRED_SOURCE_REF_FIELDS = (
    "source_ref_id",
    "safe_display_label",
    "file_type",
    "file_extension",
    "file_size_bytes",
    "source_surface",
    "workflow_ref",
    "world_ref",
    "lane_ref",
    "client_ref",
    "tenant_ref",
    "privacy_class",
    "sensitivity_class",
    "requested_intake_mode",
    "hash_or_fingerprint_policy",
    "extraction_status",
    "protected_ref_required",
    "allowed_use",
    "prohibited_use",
    "next_safe_move",
)

REQUIRED_READBACK_FIELDS = (
    "readback_id",
    "source_request_ref",
    "readback_status",
    "headline",
    "summary",
    "human_bullets",
    "source_ref",
    "operator_choices",
    "missing_registry_rails",
    "next_safe_move",
)

REQUIRED_RECEIPT_FIELDS = (
    "receipt_id",
    "source_request_ref",
    "idempotency_key",
    "payload_hash",
    "intake_status",
    "source_ref_id",
    "duplicate_result",
    "persistent_registry_write",
    "external_authority",
    "raw_body_ingestion",
    "credential_handling",
    "created_at_policy",
    "next_safe_move",
)

REQUIRED_BLOCKER_FIELDS = (
    "blocker_id",
    "blocker_type",
    "condition",
    "severity",
    "elioperator_warning",
    "fail_closed",
    "next_safe_move",
)

RAW_BODY_KEYS = {
    "raw_file_body",
    "file_body",
    "body",
    "content",
    "contents",
    "raw_bytes",
    "file_bytes",
    "base64",
    "base64_body",
    "ocr_text",
    "pdf_text",
    "spreadsheet_rows",
    "image_pixels",
    "raw_private_body",
}

SUPPORTED_EXTENSIONS = {
    ".xlsx": "spreadsheet",
    ".xls": "spreadsheet",
    ".csv": "spreadsheet",
    ".numbers": "spreadsheet",
    ".pdf": "pdf",
    ".doc": "doc",
    ".docx": "doc",
    ".rtf": "rich_text_doc",
    ".txt": "rich_text_doc",
    ".md": "doc",
    ".png": "screenshot",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".heic": "image",
    ".webp": "image",
    ".tif": "image",
    ".tiff": "image",
    ".logicx": "audio_session_or_project_metadata",
    ".als": "audio_session_or_project_metadata",
    ".fcpxml": "video_project_metadata",
    ".drp": "video_project_metadata",
    ".xml": "video_project_metadata",
    ".json": "database_or_export_file",
    ".sqlite": "database_or_export_file",
    ".db": "database_or_export_file",
    ".zip": "folder_or_project_capsule",
}

SENSITIVE_HINTS = (
    "proof",
    "evidence",
    "screenshot",
    "contract",
    "legal",
    "invoice",
    "payment",
    "private",
    "protected",
    "credential",
)

COMMON_ALLOWED_USE = (
    "show safe label in chat",
    "bind into visual workspace",
    "route metadata to a governed package",
    "request future gated extraction if approved",
)

COMMON_PROHIBITED_USE = (
    "raw body to LLM",
    "file content parsing",
    "OCR",
    "spreadsheet/PDF/image parsing",
    "folder scan",
    "external action",
    "app automation",
)


@dataclass(frozen=True)
class OperatorFileMetadataIntakeRequest:
    request_id: str
    origin_surface: str
    source_channel: str
    workflow_ref: str
    world_ref: str
    lane_ref: str
    client_ref: str
    tenant_ref: str
    operator_goal: str
    file_display_name: str
    file_kind_hint: str
    local_path_ref_policy: str
    file_size_bytes: int | None
    file_extension: str
    privacy_class: str
    requested_intake_mode: str
    idempotency_key: str
    payload_hash: str
    authority_boundary: dict[str, bool]
    created_at: str


@dataclass(frozen=True)
class OperatorFileSourceRefRecord:
    source_ref_id: str
    safe_display_label: str
    file_type: str
    file_extension: str
    file_size_bytes: int | None
    source_surface: str
    workflow_ref: str
    world_ref: str
    lane_ref: str
    client_ref: str
    tenant_ref: str
    privacy_class: str
    sensitivity_class: str
    requested_intake_mode: str
    hash_or_fingerprint_policy: str
    extraction_status: str
    protected_ref_required: bool
    allowed_use: tuple[str, ...]
    prohibited_use: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class OperatorFileMetadataReadback:
    readback_id: str
    source_request_ref: str
    readback_status: str
    headline: str
    summary: str
    human_bullets: tuple[str, ...]
    source_ref: dict[str, Any] | None
    operator_choices: tuple[str, ...]
    missing_registry_rails: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class OperatorFileIntakeReceipt:
    receipt_id: str
    source_request_ref: str
    idempotency_key: str | None
    payload_hash: str | None
    intake_status: str
    source_ref_id: str | None
    duplicate_result: str
    persistent_registry_write: bool
    external_authority: bool
    raw_body_ingestion: bool
    credential_handling: bool
    created_at_policy: str
    next_safe_move: str


@dataclass(frozen=True)
class OperatorFileIntakeBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


REQUIRED_INTAKE_REQUEST_FIELDS = tuple(OperatorFileMetadataIntakeRequest.__dataclass_fields__.keys())
REQUIRED_SOURCE_RECORD_FIELDS = tuple(OperatorFileSourceRefRecord.__dataclass_fields__.keys())
REQUIRED_METADATA_READBACK_FIELDS = tuple(OperatorFileMetadataReadback.__dataclass_fields__.keys())
REQUIRED_INTAKE_RECEIPT_FIELDS = tuple(OperatorFileIntakeReceipt.__dataclass_fields__.keys())
REQUIRED_INTAKE_BLOCKER_FIELDS = tuple(OperatorFileIntakeBlocker.__dataclass_fields__.keys())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _sha256_payload(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _short_hash(*parts: Any) -> str:
    return hashlib.sha256(stable_json(parts).encode("utf-8")).hexdigest()[:20]


def compute_request_payload_hash(request: Mapping[str, Any]) -> str:
    clone = json.loads(stable_json(dict(request)))
    clone.pop("payload_hash", None)
    return _sha256_payload(clone)


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return _sha256_payload(clone)


def _model_schemas() -> dict[str, Any]:
    return {
        "operator_file_metadata_intake_request": {
            "required_fields": list(REQUIRED_INTAKE_REQUEST_FIELDS),
            "request_shape_fields": list(REQUIRED_REQUEST_FIELDS),
        },
        "operator_file_source_ref_record": {"required_fields": list(REQUIRED_SOURCE_RECORD_FIELDS)},
        "operator_file_metadata_readback": {
            "required_fields": list(REQUIRED_METADATA_READBACK_FIELDS),
            "readback_statuses": list(READBACK_STATUSES),
        },
        "operator_file_intake_receipt": {
            "required_fields": list(REQUIRED_INTAKE_RECEIPT_FIELDS),
            "receipt_statuses": list(RECEIPT_STATUSES),
        },
        "operator_file_intake_blocker": {
            "required_fields": list(REQUIRED_INTAKE_BLOCKER_FIELDS),
            "blocker_types": list(BLOCKER_TYPES),
        },
    }


def _blocker(blocker_type: str, condition: str, *, severity: str = "BLOCKS_SAFE_FILE_INTAKE") -> OperatorFileIntakeBlocker:
    return OperatorFileIntakeBlocker(
        blocker_id=f"operator_file_intake_blocker_{blocker_type.lower()}",
        blocker_type=blocker_type,
        condition=condition,
        severity=severity,
        elioperator_warning=f"ELIOPERATOR: {condition}",
        fail_closed=True,
        next_safe_move="Return a blocked readback and ask for a safer metadata-only request.",
    )


def build_standard_blockers() -> tuple[OperatorFileIntakeBlocker, ...]:
    conditions = {
        "RAW_FILE_BODY_INCLUDED": "The request includes raw file content. Remove the body and send metadata only.",
        "RAW_FILE_BODY_READ_ATTEMPTED": "This adapter must not open, parse, OCR, or read the referenced file.",
        "UNSCOPED_FOLDER_SCAN": "The request describes a folder scan or unbounded project crawl.",
        "PRIVATE_PATH_VISIBLE_IN_NORMAL_READMODEL": "Full private paths must stay hidden from normal read-models.",
        "UNSUPPORTED_FILE_TYPE": "The file type is unsupported or unknown.",
        "MISSING_IDEMPOTENCY_KEY": "Request must include idempotency_key.",
        "MISSING_PAYLOAD_HASH": "Request must include payload_hash.",
        "EXTRACTION_REQUEST_NOT_GATED": "Extraction was requested without a future gated extraction mode.",
        "PROTECTED_FILE_WITHOUT_GUARDIAN": "Sensitive proof/source material needs protected evidence posture.",
        "UNKNOWN_FAIL_CLOSED": "Ambiguous file metadata intake state fails closed.",
    }
    return tuple(_blocker(blocker_type, condition) for blocker_type, condition in conditions.items())


def _safe_label(display_name: str) -> str:
    name = Path(str(display_name or "unnamed source")).name.strip()
    if not name:
        return "Unnamed source"
    return name[:120]


def _normalize_extension(extension: str, display_name: str) -> str:
    ext = str(extension or "").strip().lower()
    if ext and not ext.startswith("."):
        ext = "." + ext
    if not ext:
        ext = Path(display_name).suffix.lower()
    return ext


def _detect_file_type(extension: str, hint: str, display_name: str) -> str:
    text = f"{hint} {display_name}".lower()
    ext = _normalize_extension(extension, display_name)
    if "screenshot" in text:
        return "screenshot"
    if "invoice" in text and ext in {".xlsx", ".xls", ".csv", ".pdf"}:
        return "invoice_artifact"
    if "contract" in text or "legal" in text:
        return "contract_or_legal_doc"
    if "email thread" in text:
        return "email_thread_reference"
    if "calendar" in text or "event" in text:
        return "calendar_or_event_reference"
    if "folder" in text or "directory" in text or "scan" in text:
        return "folder_or_project_capsule"
    return SUPPORTED_EXTENSIONS.get(ext, "unknown_file_fail_closed")


def _sensitivity_class(request: Mapping[str, Any], file_type: str) -> str:
    text = " ".join(
        str(request.get(key) or "")
        for key in ("file_display_name", "file_kind_hint", "privacy_class", "operator_goal")
    ).lower()
    if file_type in {"contract_or_legal_doc", "email_thread_reference"} or any(hint in text for hint in ("legal", "private", "credential")):
        return "PROTECTED_SOURCE_METADATA"
    if file_type in {"screenshot", "invoice_artifact"} or any(hint in text for hint in SENSITIVE_HINTS):
        return "SENSITIVE_SOURCE_METADATA"
    return "WORK_SOURCE_METADATA"


def _protected_required(request: Mapping[str, Any], file_type: str) -> bool:
    mode = str(request.get("requested_intake_mode") or "")
    privacy = str(request.get("privacy_class") or "").lower()
    sensitivity = _sensitivity_class(request, file_type)
    return (
        mode == "PROTECTED_EVIDENCE_REFERENCE"
        or file_type in {"screenshot", "contract_or_legal_doc", "email_thread_reference"}
        or "protected" in privacy
        or sensitivity == "PROTECTED_SOURCE_METADATA"
    )


def _path_ref_present(request: Mapping[str, Any]) -> bool:
    return bool(request.get("local_path_ref") or request.get("mac_visible_path_ref"))


def make_fixture_request(
    fixture: str = "spreadsheet",
    *,
    created_at: str = "2026-05-25T00:00:00+00:00",
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "request_id": f"mission_control_file_intake_request_{fixture}_fixture",
        "origin_surface": "Mission Control chat",
        "source_channel": "mission_control_chat_attachment",
        "workflow_ref": "capital_hilton_invoice_workflow" if fixture == "spreadsheet" else "generic_visual_workspace",
        "world_ref": "finance" if fixture == "spreadsheet" else "creative_ops",
        "lane_ref": "Capital Hilton" if fixture == "spreadsheet" else "operator_workspace",
        "client_ref": "capital_hilton" if fixture == "spreadsheet" else "operator_project",
        "tenant_ref": "openclaw_repo_a_local",
        "operator_goal": "Use this file as a safe source reference.",
        "file_display_name": "Capital Hilton invoice.xlsx",
        "file_kind_hint": "invoice spreadsheet",
        "mac_visible_path_ref": "mac_path_ref:hidden_by_adapter",
        "file_size_bytes": 24576,
        "file_extension": ".xlsx",
        "privacy_class": "business_source_metadata",
        "requested_intake_mode": "METADATA_ONLY",
        "idempotency_key": f"file_metadata_{fixture}_fixture",
        "payload_hash": "",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "created_at": created_at,
    }
    if fixture == "screenshot":
        base.update(
            {
                "workflow_ref": "proof_workspace",
                "world_ref": "operations",
                "lane_ref": "protected_proof",
                "client_ref": "operator_project",
                "operator_goal": "Use this screenshot as proof.",
                "file_display_name": "screenshot-proof.png",
                "file_kind_hint": "screenshot proof",
                "file_size_bytes": 512000,
                "file_extension": ".png",
                "privacy_class": "protected_evidence_metadata",
                "requested_intake_mode": "PROTECTED_EVIDENCE_REFERENCE",
                "idempotency_key": "file_metadata_screenshot_fixture",
            }
        )
    elif fixture == "album":
        base.update(
            {
                "workflow_ref": "album_workspace",
                "world_ref": "music_art",
                "lane_ref": "album_planning",
                "client_ref": "operator_project",
                "operator_goal": "Use this album spreadsheet in a future visual workspace.",
                "file_display_name": "album spreadsheet.xlsx",
                "file_kind_hint": "album spreadsheet",
                "file_size_bytes": 49152,
                "file_extension": ".xlsx",
                "privacy_class": "creative_source_metadata",
                "requested_intake_mode": "VISUAL_WORKSPACE_SOURCE",
                "idempotency_key": "file_metadata_album_fixture",
            }
        )
    elif fixture == "unknown":
        base.update(
            {
                "file_display_name": "mystery.bundle",
                "file_kind_hint": "unknown source",
                "file_extension": ".bundle",
                "requested_intake_mode": "METADATA_ONLY",
                "idempotency_key": "file_metadata_unknown_fixture",
            }
        )
    elif fixture == "raw_body":
        base.update(
            {
                "file_display_name": "unsafe-source.pdf",
                "file_kind_hint": "pdf",
                "file_extension": ".pdf",
                "requested_intake_mode": "METADATA_ONLY",
                "idempotency_key": "file_metadata_raw_body_fixture",
                "raw_file_body": "RAW BODY OMITTED IN REAL REQUESTS",
            }
        )
    elif fixture == "folder":
        base.update(
            {
                "file_display_name": "client folder",
                "file_kind_hint": "folder scan",
                "file_extension": "",
                "requested_intake_mode": "METADATA_ONLY",
                "idempotency_key": "file_metadata_folder_fixture",
            }
        )
    elif fixture == "missing_idempotency":
        base["idempotency_key"] = ""
    base["payload_hash"] = compute_request_payload_hash(base)
    return base


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("request JSON must be an object")
    return value


def find_latest_request(inbox: Path = APPROVED_INBOX) -> Path | None:
    if not inbox.exists():
        return None
    matches = sorted(
        path
        for path in inbox.iterdir()
        if path.is_file() and fnmatch.fnmatch(path.name, REQUEST_FILENAME_PATTERN)
    )
    return matches[-1] if matches else None


def validate_request_shape(request: Mapping[str, Any], *, request_path: Path | None = None) -> tuple[bool, tuple[OperatorFileIntakeBlocker, ...]]:
    blockers: list[OperatorFileIntakeBlocker] = []
    if request_path is not None and not fnmatch.fnmatch(request_path.name, REQUEST_FILENAME_PATTERN):
        blockers.append(_blocker("UNKNOWN_FAIL_CLOSED", f"Filename must match {REQUEST_FILENAME_PATTERN}."))
    missing = [field for field in REQUIRED_REQUEST_FIELDS if field not in request]
    if missing:
        blockers.append(_blocker("UNKNOWN_FAIL_CLOSED", f"Missing required fields: {', '.join(missing)}."))
    if not request.get("idempotency_key"):
        blockers.append(_blocker("MISSING_IDEMPOTENCY_KEY", "Request is missing idempotency_key."))
    if not request.get("payload_hash"):
        blockers.append(_blocker("MISSING_PAYLOAD_HASH", "Request is missing payload_hash."))
    elif request.get("payload_hash") != compute_request_payload_hash(request):
        blockers.append(_blocker("UNKNOWN_FAIL_CLOSED", "payload_hash does not match request metadata."))
    if not request.get("file_display_name") or not _path_ref_present(request):
        blockers.append(_blocker("UNKNOWN_FAIL_CLOSED", "Request must include file_display_name and a hidden path ref."))
    for key in RAW_BODY_KEYS:
        if key in request and request.get(key) not in (None, "", [], {}):
            blockers.append(_blocker("RAW_FILE_BODY_INCLUDED", f"Request includes raw content field {key}."))
            break
    authority = request.get("authority_boundary")
    if not isinstance(authority, Mapping):
        blockers.append(_blocker("UNKNOWN_FAIL_CLOSED", "authority_boundary must be an object."))
    elif any(value is True for value in authority.values()):
        blockers.append(_blocker("UNKNOWN_FAIL_CLOSED", "Request asks for authority this adapter cannot grant."))
    mode = str(request.get("requested_intake_mode") or "")
    if mode not in SUPPORTED_INTAKE_MODES:
        blockers.append(_blocker("EXTRACTION_REQUEST_NOT_GATED", "Requested intake mode is unsupported or not gated."))
    if mode == "SAFE_EXTRACT_REQUESTED_FUTURE_GATED":
        blockers.append(_blocker("EXTRACTION_REQUEST_NOT_GATED", "Safe extraction is a future gated rail; metadata ref only for now."))
    file_type = _detect_file_type(
        str(request.get("file_extension") or ""),
        str(request.get("file_kind_hint") or ""),
        str(request.get("file_display_name") or ""),
    )
    if file_type == "unknown_file_fail_closed":
        blockers.append(_blocker("UNSUPPORTED_FILE_TYPE", "Unsupported file type."))
    if file_type == "folder_or_project_capsule" and "scan" in str(request.get("file_kind_hint") or "").lower():
        blockers.append(_blocker("UNSCOPED_FOLDER_SCAN", "Folder scan requests are not allowed in metadata intake."))
    if _protected_required(request, file_type) and mode != "PROTECTED_EVIDENCE_REFERENCE":
        # This is a posture warning only for invoice-like business artifacts; fail closed for protected/legal proof.
        if file_type in {"screenshot", "contract_or_legal_doc", "email_thread_reference"}:
            blockers.append(_blocker("PROTECTED_FILE_WITHOUT_GUARDIAN", "Protected proof/source needs protected evidence mode."))
    return not blockers, tuple(blockers)


def normalize_request(request: Mapping[str, Any]) -> OperatorFileMetadataIntakeRequest:
    return OperatorFileMetadataIntakeRequest(
        request_id=str(request.get("request_id") or "unknown_file_intake_request"),
        origin_surface=str(request.get("origin_surface") or "unknown"),
        source_channel=str(request.get("source_channel") or "unknown"),
        workflow_ref=str(request.get("workflow_ref") or "unknown"),
        world_ref=str(request.get("world_ref") or "unknown"),
        lane_ref=str(request.get("lane_ref") or "unknown"),
        client_ref=str(request.get("client_ref") or "unknown"),
        tenant_ref=str(request.get("tenant_ref") or "unknown"),
        operator_goal=str(request.get("operator_goal") or ""),
        file_display_name=_safe_label(str(request.get("file_display_name") or "")),
        file_kind_hint=str(request.get("file_kind_hint") or "unknown"),
        local_path_ref_policy="provided_path_ref_hidden_from_normal_read_model" if _path_ref_present(request) else "missing_path_ref",
        file_size_bytes=int(request["file_size_bytes"]) if str(request.get("file_size_bytes") or "").isdigit() else None,
        file_extension=_normalize_extension(str(request.get("file_extension") or ""), str(request.get("file_display_name") or "")),
        privacy_class=str(request.get("privacy_class") or "unknown"),
        requested_intake_mode=str(request.get("requested_intake_mode") or "REFERENCE_ONLY"),
        idempotency_key=str(request.get("idempotency_key") or ""),
        payload_hash=str(request.get("payload_hash") or ""),
        authority_boundary=AUTHORITY_BOUNDARY,
        created_at=str(request.get("created_at") or ""),
    )


def create_source_ref(request: OperatorFileMetadataIntakeRequest) -> OperatorFileSourceRefRecord:
    file_type = _detect_file_type(request.file_extension, request.file_kind_hint, request.file_display_name)
    source_ref_id = f"source_ref:{_short_hash(request.idempotency_key, request.payload_hash, request.file_display_name)}"
    protected_required = _protected_required(asdict(request), file_type)
    return OperatorFileSourceRefRecord(
        source_ref_id=source_ref_id,
        safe_display_label=request.file_display_name,
        file_type=file_type,
        file_extension=request.file_extension,
        file_size_bytes=request.file_size_bytes,
        source_surface=request.origin_surface,
        workflow_ref=request.workflow_ref,
        world_ref=request.world_ref,
        lane_ref=request.lane_ref,
        client_ref=request.client_ref,
        tenant_ref=request.tenant_ref,
        privacy_class=request.privacy_class,
        sensitivity_class=_sensitivity_class(asdict(request), file_type),
        requested_intake_mode=request.requested_intake_mode,
        hash_or_fingerprint_policy="metadata_fingerprint_only_body_not_read",
        extraction_status="NOT_EXTRACTED_BODY_NOT_READ",
        protected_ref_required=protected_required,
        allowed_use=COMMON_ALLOWED_USE,
        prohibited_use=COMMON_PROHIBITED_USE,
        next_safe_move="Use this source ref in a visual workspace or future gated extraction request.",
    )


def build_readback(
    request: OperatorFileMetadataIntakeRequest,
    source_ref: OperatorFileSourceRefRecord | None,
    *,
    status: str,
    blockers: tuple[OperatorFileIntakeBlocker, ...] = (),
) -> OperatorFileMetadataReadback:
    if source_ref is None:
        summary = "OpenClaw did not capture this file reference because the request was not safe metadata-only."
        bullets = tuple(blocker.elioperator_warning for blocker in blockers) or ("No file metadata request is available.",)
        headline = "File reference blocked" if status != "NO_REQUEST_AVAILABLE" else "No file request available"
        next_safe_move = "Send a metadata-only file reference with idempotency and payload hash."
    else:
        summary = (
            f"OpenClaw captured a file reference for '{source_ref.safe_display_label}'. "
            "The file body was not read."
        )
        bullets = (
            f"Referenced source: {source_ref.safe_display_label}.",
            f"Detected type: {source_ref.file_type}.",
            "The file body was not read, parsed, OCRed, or sent to a model.",
            "This can be used later as a source for a visual workspace or governed extraction.",
            "Full private paths are hidden from the normal read-model.",
        )
        if source_ref.protected_ref_required:
            bullets = bullets + ("Protected evidence posture is required before raw/protected use.",)
        headline = "File reference captured"
        next_safe_move = "Show the file reference card and ask whether to use it in a visual workspace."
    return OperatorFileMetadataReadback(
        readback_id=f"operator_file_metadata_readback_{_short_hash(request.request_id, status)}",
        source_request_ref=request.request_id,
        readback_status=status,
        headline=headline,
        summary=summary,
        human_bullets=bullets,
        source_ref=asdict(source_ref) if source_ref else None,
        operator_choices=("Use in visual workspace later", "Request governed extraction later", "Cancel"),
        missing_registry_rails=("persistent source registry", "duplicate idempotency ledger", "future governed extraction adapter"),
        next_safe_move=next_safe_move,
    )


def build_receipt(
    request: OperatorFileMetadataIntakeRequest,
    source_ref: OperatorFileSourceRefRecord | None,
    *,
    status: str,
    duplicate_result: str = "NOT_PERSISTED_NO_DUPLICATE_CHECK",
) -> OperatorFileIntakeReceipt:
    return OperatorFileIntakeReceipt(
        receipt_id=f"operator_file_intake_receipt_{_short_hash(request.idempotency_key, request.payload_hash, status)}",
        source_request_ref=request.request_id,
        idempotency_key=request.idempotency_key or None,
        payload_hash=request.payload_hash or None,
        intake_status=status,
        source_ref_id=source_ref.source_ref_id if source_ref else None,
        duplicate_result=duplicate_result,
        persistent_registry_write=False,
        external_authority=False,
        raw_body_ingestion=False,
        credential_handling=False,
        created_at_policy="deterministic generated read-model timestamp; no SQLite registry write",
        next_safe_move="Add a future metadata-only source registry before claiming duplicate persistence.",
    )


def build_payload_from_request(
    raw_request: Mapping[str, Any],
    *,
    generated_at: str | None = None,
    source_request_path: Path | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    ok, blockers = validate_request_shape(raw_request, request_path=source_request_path)
    request = normalize_request(raw_request)
    if ok:
        source_ref = create_source_ref(request)
        status = "SOURCE_REF_CREATED"
        route_mode = "REQUEST_ACCEPTED_METADATA_ONLY"
    else:
        source_ref = None
        route_mode = "REQUEST_BLOCKED"
        blocker_types = {blocker.blocker_type for blocker in blockers}
        if "RAW_FILE_BODY_INCLUDED" in blocker_types:
            status = "BLOCKED_RAW_BODY_INCLUDED"
        elif "UNSCOPED_FOLDER_SCAN" in blocker_types:
            status = "BLOCKED_UNSCOPED_FOLDER_SCAN"
        elif "UNSUPPORTED_FILE_TYPE" in blocker_types:
            status = "BLOCKED_UNSUPPORTED_FILE_TYPE"
        else:
            status = "BLOCKED_INVALID_REQUEST"
    readback = build_readback(request, source_ref, status=status, blockers=blockers)
    receipt = build_receipt(request, source_ref, status="METADATA_CAPTURED" if ok else "REQUEST_BLOCKED")
    return _build_payload(
        generated_at=generated_at,
        source_request_path=source_request_path,
        intake_request=request,
        source_ref=source_ref,
        readback=readback,
        receipt=receipt,
        blockers=blockers,
        route_mode=route_mode,
    )


def build_payload_from_request_file(request_path: Path, *, generated_at: str | None = None) -> dict[str, Any]:
    return build_payload_from_request(_load_json(request_path), generated_at=generated_at, source_request_path=request_path)


def build_no_request_payload(*, generated_at: str | None = None, inbox: Path = APPROVED_INBOX) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    request = OperatorFileMetadataIntakeRequest(
        request_id="no_file_metadata_request_available",
        origin_surface="none",
        source_channel="none",
        workflow_ref="unknown",
        world_ref="unknown",
        lane_ref="unknown",
        client_ref="unknown",
        tenant_ref="unknown",
        operator_goal="No file request available.",
        file_display_name="No file request",
        file_kind_hint="none",
        local_path_ref_policy="missing_path_ref",
        file_size_bytes=None,
        file_extension="",
        privacy_class="no_request",
        requested_intake_mode="REFERENCE_ONLY",
        idempotency_key="",
        payload_hash="",
        authority_boundary=AUTHORITY_BOUNDARY,
        created_at=generated_at,
    )
    blocker = _blocker(
        "UNKNOWN_FAIL_CLOSED",
        f"No {REQUEST_FILENAME_PATTERN} file was found in the approved inbox.",
        severity="NEEDS_INPUT",
    )
    readback = build_readback(request, None, status="NO_REQUEST_AVAILABLE", blockers=(blocker,))
    receipt = build_receipt(request, None, status="NO_REQUEST_AVAILABLE")
    return _build_payload(
        generated_at=generated_at,
        source_request_path=None,
        intake_request=request,
        source_ref=None,
        readback=readback,
        receipt=receipt,
        blockers=(blocker,),
        route_mode="NO_REQUEST_AVAILABLE",
    )


def _build_payload(
    *,
    generated_at: str,
    source_request_path: Path | None,
    intake_request: OperatorFileMetadataIntakeRequest,
    source_ref: OperatorFileSourceRefRecord | None,
    readback: OperatorFileMetadataReadback,
    receipt: OperatorFileIntakeReceipt,
    blockers: tuple[OperatorFileIntakeBlocker, ...],
    route_mode: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "route_mode": route_mode,
        "source_request_path_policy": "hidden_from_normal_read_model" if source_request_path else "none",
        "approved_inbox_policy": "mission_control_file_intake_request inbox path hidden in operator cards",
        "supported_filename_pattern": REQUEST_FILENAME_PATTERN,
        "supported_intake_modes": SUPPORTED_INTAKE_MODES,
        "model_schemas": _model_schemas(),
        "intake_request": asdict(intake_request),
        "source_ref_record": asdict(source_ref) if source_ref else None,
        "metadata_readback": asdict(readback),
        "intake_receipt": asdict(receipt),
        "active_blockers_by_id": {blocker.blocker_id: asdict(blocker) for blocker in blockers},
        "standard_blockers_by_id": {blocker.blocker_id: asdict(blocker) for blocker in build_standard_blockers()},
        "source_registry_status": {
            "persistent_source_registry_available": False,
            "metadata_only_sqlite_write_performed": False,
            "missing_registry_rail": "persistent source registry / duplicate idempotency ledger not connected",
        },
        "relationship_refs": {
            "file_intake_visual_workspace_contract": "operator_file_intake_visual_workspace_contract_v0",
            "handoff_registry": "cross_surface_artifact_handoff_registry_contract_v0",
            "protected_evidence": "protected_evidence_reference_receipt_v0",
            "sensitive_policy": "openclaw_sensitive_policy",
        },
        "operator_markdown_mode": "ELIOPERATOR",
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["machine_proof"] = _machine_proof(payload)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def _machine_proof(payload: dict[str, Any]) -> dict[str, Any]:
    source_ref = payload["source_ref_record"] or {}
    readback_text = stable_json(payload["metadata_readback"]).lower()
    blocker_types = {
        blocker["blocker_type"]
        for blocker in {
            **payload["active_blockers_by_id"],
            **payload["standard_blockers_by_id"],
        }.values()
    }
    return {
        "intake_request_model_present": True,
        "source_ref_record_model_present": True,
        "metadata_readback_model_present": True,
        "intake_receipt_model_present": True,
        "intake_blocker_model_present": True,
        "supported_modes_present": set(SUPPORTED_INTAKE_MODES).issubset(payload["supported_intake_modes"]),
        "blockers_present": set(BLOCKER_TYPES).issubset(blocker_types),
        "source_ref_created_if_valid": payload["metadata_readback"]["readback_status"] != "SOURCE_REF_CREATED" or source_ref.get("source_ref_id", "").startswith("source_ref:"),
        "spreadsheet_fixture_creates_source_ref": source_ref.get("safe_display_label") == "Capital Hilton invoice.xlsx",
        "screenshot_protected_posture_if_present": (
            source_ref.get("file_type") != "screenshot" or source_ref.get("protected_ref_required") is True
        ),
        "album_visual_workspace_source_if_present": (
            payload["intake_request"]["file_display_name"] != "album spreadsheet.xlsx"
            or payload["intake_request"]["requested_intake_mode"] == "VISUAL_WORKSPACE_SOURCE"
        ),
        "full_private_path_hidden": payload["intake_request"]["local_path_ref_policy"].endswith("hidden_from_normal_read_model")
        or payload["intake_request"]["local_path_ref_policy"] == "missing_path_ref",
        "human_readback_present": "file reference" in readback_text,
        "raw_body_included": any(blocker["blocker_type"] == "RAW_FILE_BODY_INCLUDED" for blocker in payload["active_blockers_by_id"].values()),
        "unknown_file_type_blocked": any(blocker["blocker_type"] == "UNSUPPORTED_FILE_TYPE" for blocker in payload["active_blockers_by_id"].values()),
        "folder_scan_blocked": any(blocker["blocker_type"] == "UNSCOPED_FOLDER_SCAN" for blocker in payload["active_blockers_by_id"].values()),
        "missing_idempotency_blocked": any(blocker["blocker_type"] == "MISSING_IDEMPOTENCY_KEY" for blocker in payload["active_blockers_by_id"].values()),
        "duplicate_persistence_implemented": False,
        "duplicate_noop_available": False,
        "persistent_registry_write_performed": payload["intake_receipt"]["persistent_registry_write"],
        "all_live_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "file_body_ingestion_performed": False,
        "raw_body_extraction_performed": False,
        "ocr_performed": False,
        "spreadsheet_parse_performed": False,
        "pdf_parse_performed": False,
        "image_analysis_performed": False,
        "folder_scan_performed": False,
        "app_automation_performed": False,
        "external_action_performed": False,
        "model_call_performed": False,
        "credential_handling_performed": False,
        "raw_body_ingestion_performed": False,
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "raw_pii_in_generated_outputs": False,
        "network_used": False,
        "mission_control_swift_changed": False,
        "mac_sync_import_run": False,
        "git_push_pull_fetch_run": False,
        "content_hash": None,
    }


def write_exports(payload: dict[str, Any], export_root: Path) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def format_operator_markdown(payload: dict[str, Any]) -> str:
    readback = payload["metadata_readback"]
    lines = [
        "# Operator File Metadata Readback v0",
        "",
        "ELIOPERATOR: This readback captures file metadata as a safe source reference. It does not read the file body or execute anything.",
        "",
        f"- Route mode: `{payload['route_mode']}`.",
        f"- Readback status: `{readback['readback_status']}`.",
        "",
        f"## {readback['headline']}",
        "",
        readback["summary"],
        "",
    ]
    lines.extend(f"- {bullet}" for bullet in readback["human_bullets"])
    lines.extend(
        [
            "",
            "## What did not happen",
            "",
            "- No file body was read or ingested.",
            "- No OCR, spreadsheet parsing, PDF parsing, or image analysis occurred.",
            "- No folder scan, app automation, model call, credential handling, or external action occurred.",
            "",
            "## Registry posture",
            "",
            "- Persistent source registry is not connected yet.",
            "- Idempotency is validated, but duplicate persistence is not claimed.",
            "",
            f"Next safe move: {readback['next_safe_move']}",
            "",
        ]
    )
    return "\n".join(lines)


def build_summary(payload: dict[str, Any], json_path: Path | None, operator_path: Path | None) -> dict[str, Any]:
    source_ref = payload["source_ref_record"] or {}
    return {
        "schema_version": payload["schema_version"],
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path) if json_path else None,
        "operator_path": str(operator_path) if operator_path else None,
        "route_mode": payload["route_mode"],
        "readback_status": payload["metadata_readback"]["readback_status"],
        "source_ref_id": source_ref.get("source_ref_id"),
        "file_type": source_ref.get("file_type"),
        "safe_display_label": source_ref.get("safe_display_label"),
        "protected_ref_required": source_ref.get("protected_ref_required"),
        "persistent_registry_write": payload["intake_receipt"]["persistent_registry_write"],
        "duplicate_result": payload["intake_receipt"]["duplicate_result"],
        "all_live_authority_flags_false": payload["machine_proof"]["all_live_authority_flags_false"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def build_payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.fixture:
        return build_payload_from_request(make_fixture_request(args.fixture, created_at=args.generated_at or "2026-05-25T00:00:00+00:00"), generated_at=args.generated_at)
    if args.request_json:
        return build_payload_from_request_file(Path(args.request_json), generated_at=args.generated_at)
    export_path = Path(args.export_root) / JSON_EXPORT_NAME
    if export_path.exists():
        return json.loads(export_path.read_text(encoding="utf-8"))
    latest = find_latest_request(Path(args.inbox))
    if latest:
        return build_payload_from_request_file(latest, generated_at=args.generated_at)
    return build_no_request_payload(generated_at=args.generated_at, inbox=Path(args.inbox))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import/export operator file metadata readback.")
    parser.add_argument("--request-json", "--file", dest="request_json", default=None)
    parser.add_argument("--fixture", choices=("spreadsheet", "screenshot", "album", "unknown", "raw_body", "folder", "missing_idempotency"), default=None)
    parser.add_argument("--inbox", default=str(APPROVED_INBOX))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)

    payload = build_payload_from_args(args)
    json_path, operator_path = write_exports(payload, Path(args.export_root))
    output = payload if args.format == "json" else build_summary(payload, json_path, operator_path)
    print(stable_json(output), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
