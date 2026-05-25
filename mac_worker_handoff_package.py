"""PC-to-Mac Worker Handoff Package v0.

This deterministic module packages Mac-owned work for a future Mac-side worker
lane. It writes metadata-only handoff packages and read-models. It does not
execute Mac code, automate apps, run Xcode, capture screenshots, mutate files,
dispatch agents, call models, handle credentials, ingest raw bodies, or perform
external actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Mapping


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_HANDOFF_OUTPUT_DIR = Path("/mnt/e/openclaw/mission_control_handoffs/to_mac")
MAC_VISIBLE_HANDOFF_DIR = "/Volumes/openclaw_e/mission_control_handoffs/to_mac"
DEFAULT_RESPONSE_DIR = Path("/mnt/e/openclaw/mission_control_responses/to_mac")
MAC_VISIBLE_RESPONSE_DIR = "/Volumes/openclaw_e/mission_control_responses/to_mac"
DEFAULT_GENERATED_AT = "2026-05-25T00:00:00+00:00"

SCHEMA_VERSION = "mac_worker_handoff_package_v0"
READ_MODEL_ID = "mac_worker_handoff_package"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_PC_TO_MAC_WORKER_HANDOFF_PACKAGE_NO_EXECUTION"

REQUESTED_WORKERS = (
    "MAC_CODEX",
    "MAC_UI_VALIDATION",
    "MAC_XCODE_BUILD",
    "MAC_SCREENSHOT_VALIDATION",
    "MAC_VISUAL_WORKSPACE",
    "MAC_AUDIO_PLAYBACK",
    "MAC_APP_INTEGRATION_SCOUT",
    "UNKNOWN_FAIL_CLOSED",
)

TARGET_SURFACES = (
    "mission_control_mac_app",
    "mac_chat",
    "mac_visual_workspace",
    "xcode",
    "finder",
    "apple_app_boundary_future",
    "unknown",
)

BLOCKER_TYPES = (
    "UNKNOWN_MAC_WORKER",
    "MISSING_TARGET_SURFACE",
    "UNSCOPED_CONTEXT",
    "RAW_PRIVATE_BODY_INCLUDED",
    "CREDENTIAL_INCLUDED",
    "APP_AUTOMATION_REQUESTED",
    "FILE_MUTATION_REQUESTED",
    "EXTERNAL_ACTION_REQUESTED",
    "MAC_HANDOFF_PATH_UNAVAILABLE",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "mac_code_edit_allowed": False,
    "xcode_build_allowed": False,
    "screenshot_allowed": False,
    "app_automation_allowed": False,
    "external_action_allowed": False,
    "credential_handling_allowed": False,
    "file_mutation_allowed": False,
    "raw_body_ingestion_allowed": False,
    "live_mac_execution_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_model_call_allowed": False,
    "live_workflow_run_allowed": False,
    "live_app_control_allowed": False,
    "live_browser_allowed": False,
    "live_email_send_allowed": False,
    "live_coupa_submit_allowed": False,
    "live_microphone_capture_allowed": False,
    "live_speech_synthesis_allowed": False,
    "live_cloud_audio_allowed": False,
    "network_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

RAW_BODY_KEYS = {
    "raw_body",
    "raw_private_body",
    "raw_message_body",
    "raw_email_body",
    "raw_file_body",
    "raw_transcript",
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
}

SECRET_KEYS = {
    "password",
    "passcode",
    "token",
    "oauth_token",
    "refresh_token",
    "api_key",
    "secret",
    "credential",
    "credentials",
    "cookie",
    "session_cookie",
    "private_key",
}

APP_AUTOMATION_TERMS = (
    "open mail",
    "open telegram",
    "open finder",
    "open logic",
    "open ableton",
    "open final cut",
    "click",
    "press the button",
    "control the app",
    "automate mail",
    "automate telegram",
    "drive the app",
)

EXTERNAL_ACTION_TERMS = (
    "send the invoice",
    "send email",
    "mail send",
    "gmail send",
    "submit invoice",
    "submit to coupa",
    "coupa submit",
    "log in",
    "use credentials",
    "payment",
    "approve it",
)

FILE_MUTATION_TERMS = (
    "edit the file",
    "change the file",
    "save the file",
    "rewrite the file",
    "delete the file",
    "move the file",
)


@dataclass(frozen=True)
class MacWorkerHandoffPackage:
    handoff_id: str
    source_request_id: str
    source_request_filename: str
    requested_worker: str
    target_machine: str
    target_surface: str
    workflow_ref: str
    world_ref: str
    lane_ref: str
    task_goal: str
    operator_message_summary: str
    scoped_context_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    artifact_refs: tuple[str, ...]
    validation_expectations: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    authority_boundary: dict[str, bool]
    response_expected: bool
    response_path_policy: dict[str, Any]
    created_at: str
    next_safe_move: str


@dataclass(frozen=True)
class MacWorkerHandoffBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha256(stable_json(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def _safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return cleaned[:160] if cleaned else hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def _walk_dict(value: Any, *, prefix: str = "") -> tuple[tuple[str, Any], ...]:
    entries: list[tuple[str, Any]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            entries.append((path, item))
            entries.extend(_walk_dict(item, prefix=path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            entries.extend(_walk_dict(item, prefix=f"{prefix}[{index}]"))
    return tuple(entries)


def _request_text(raw_request: Mapping[str, Any]) -> str:
    fields = (
        "operator_message",
        "sanitized_message_summary",
        "operator_goal",
        "workflow_ref",
        "workflow_type",
        "world_ref",
        "lane_ref",
        "client_ref",
        "tenant_ref",
    )
    return " ".join(str(raw_request.get(field) or "") for field in fields).strip()


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _safe_summary(raw_request: Mapping[str, Any]) -> str:
    summary = str(raw_request.get("sanitized_message_summary") or raw_request.get("operator_message") or "").strip()
    summary = " ".join(summary.split())
    if not summary:
        return "Mac-owned request needs scoped handling."
    return summary[:280]


def _safe_ref(value: object) -> str | None:
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("generated/read_models/"):
        return text
    if text.startswith("source_ref:") or text.startswith("artifact_ref:") or text.startswith("spoken_response_packet"):
        return text
    name = Path(text).name
    if name.endswith((".json", ".md")) and "/" not in text.strip("/"):
        return f"generated/read_models/{name}"
    return None


def _safe_refs(value: Any) -> tuple[str, ...]:
    refs: list[str] = []
    if isinstance(value, Mapping):
        for item in value.values():
            refs.extend(_safe_refs(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            refs.extend(_safe_refs(item))
    else:
        ref = _safe_ref(value)
        if ref:
            refs.append(ref)
    return tuple(dict.fromkeys(refs))


def _blocker(blocker_type: str, condition: str, severity: str, next_safe_move: str) -> MacWorkerHandoffBlocker:
    return MacWorkerHandoffBlocker(
        blocker_id=_stable_id("mac_worker_handoff_blocker", blocker_type, condition),
        blocker_type=blocker_type,
        condition=condition,
        severity=severity,
        elioperator_warning=f"ELIOPERATOR: {condition}",
        fail_closed=True,
        next_safe_move=next_safe_move,
    )


def blockers_for_request(raw_request: Mapping[str, Any]) -> tuple[MacWorkerHandoffBlocker, ...]:
    blockers: list[MacWorkerHandoffBlocker] = []
    lowered_text = _request_text(raw_request).lower()
    for key_path, value in _walk_dict(raw_request):
        key = key_path.rsplit(".", 1)[-1].lower()
        if key in RAW_BODY_KEYS and value not in (None, "", [], {}):
            blockers.append(
                _blocker(
                    "RAW_PRIVATE_BODY_INCLUDED",
                    f"Request includes raw/private body field {key_path}; handoff packages must use refs only.",
                    "critical",
                    "Remove raw body content and provide a safe source reference.",
                )
            )
        if key in SECRET_KEYS and value not in (None, "", [], {}):
            blockers.append(
                _blocker(
                    "CREDENTIAL_INCLUDED",
                    f"Request includes credential-like field {key_path}; raw secrets cannot enter a Mac handoff package.",
                    "critical",
                    "Use a future protected secret ref flow; do not include raw credentials.",
                )
            )
    if _contains_any(lowered_text, APP_AUTOMATION_TERMS):
        blockers.append(
            _blocker(
                "APP_AUTOMATION_REQUESTED",
                "Request asks PC to package app automation or native app control.",
                "critical",
                "Reframe as a scoped Mac readback or validation request without app automation authority.",
            )
        )
    if _contains_any(lowered_text, EXTERNAL_ACTION_TERMS):
        blockers.append(
            _blocker(
                "EXTERNAL_ACTION_REQUESTED",
                "Request asks for send, submit, login, approval, payment, or other external action.",
                "critical",
                "Use proof/approval package rails first; do not route this as executable Mac work.",
            )
        )
    if _contains_any(lowered_text, FILE_MUTATION_TERMS):
        blockers.append(
            _blocker(
                "FILE_MUTATION_REQUESTED",
                "Request asks for file mutation authority, which is outside this v0 handoff package lane.",
                "high",
                "Create a future explicit Mac implementation lane with scoped file mutation authority.",
            )
        )
    deduped: dict[str, MacWorkerHandoffBlocker] = {}
    for item in blockers:
        deduped[item.blocker_type] = item
    return tuple(deduped.values())


def classify_mac_worker(raw_request: Mapping[str, Any]) -> tuple[str, str, str]:
    text = _request_text(raw_request).lower()
    if "read this response aloud" in text or "read aloud" in text or "speak this" in text or "tts" in text:
        return "MAC_AUDIO_PLAYBACK", "mac_chat", "Native audio/TTS playback belongs on Mac."
    if "xcode" in text or "check if the mac app builds" in text or "build validation" in text or "xcodebuild" in text:
        return "MAC_XCODE_BUILD", "xcode", "Xcode build/run validation belongs on Mac."
    if "screenshot" in text or "screen capture" in text or "rendering check" in text:
        return "MAC_SCREENSHOT_VALIDATION", "mission_control_mac_app", "Screenshot validation belongs on Mac."
    if "visual workspace" in text or "show me" in text and "visually" in text or "workspace visually" in text:
        return "MAC_VISUAL_WORKSPACE", "mac_visual_workspace", "Local visual workspace rendering belongs on Mac."
    if any(term in text for term in ("mail", "telegram", "logic", "ableton", "final cut", "finder", "apple app")):
        surface = "finder" if "finder" in text else "apple_app_boundary_future"
        return "MAC_APP_INTEGRATION_SCOUT", surface, "Apple app integration boundaries belong on Mac."
    if any(term in text for term in ("swiftui", "mission control ui", "mac app", "macos app", "chat renderer", "chat response look better", "app layout")):
        return "MAC_CODEX", "mission_control_mac_app", "Mission Control Mac UI work belongs on Mac."
    return "UNKNOWN_FAIL_CLOSED", "unknown", "No supported Mac worker target could be selected safely."


def validation_expectations_for(worker: str) -> tuple[str, ...]:
    common = (
        "static authority scan",
        "no network",
        "no backend mutation",
        "no file-body ingestion",
        "no app automation unless explicitly scoped",
    )
    if worker in {"MAC_CODEX", "MAC_UI_VALIDATION"}:
        return ("xcodebuild build", "focused app tests", "screenshot if UI-visible", *common)
    if worker == "MAC_XCODE_BUILD":
        return ("xcodebuild build", "focused app tests", *common)
    if worker == "MAC_SCREENSHOT_VALIDATION":
        return ("screenshot if UI-visible", "compare Mac-rendered response fields", *common)
    if worker == "MAC_VISUAL_WORKSPACE":
        return ("source refs only", "local render readback", "no raw file bodies", *common)
    if worker == "MAC_AUDIO_PLAYBACK":
        return ("native Mac playback only", "no microphone", "no cloud synthesis/transcription", *common)
    if worker == "MAC_APP_INTEGRATION_SCOUT":
        return ("static integration boundary report", "no app control", "no account access", *common)
    return common


def forbidden_actions_for(worker: str) -> tuple[str, ...]:
    base = (
        "Mac execution",
        "Mac app automation",
        "Xcode execution",
        "screenshot capture",
        "file mutation",
        "external action",
        "send/submit",
        "credential handling",
        "raw-body ingestion",
    )
    if worker == "MAC_AUDIO_PLAYBACK":
        return (*base, "microphone capture", "cloud audio")
    return base


def response_path_policy(source_request_id: str) -> dict[str, Any]:
    safe_request_id = _safe_filename_part(source_request_id)
    return {
        "pc_response_dir": DEFAULT_RESPONSE_DIR.as_posix(),
        "mac_visible_response_dir": MAC_VISIBLE_RESPONSE_DIR,
        "expected_response_filename": f"openclaw_response_for_mac_{safe_request_id}.json",
        "latest_response_filename": "openclaw_response_for_mac_latest.json",
        "terminal_readback_expected": True,
        "completion_claim_allowed": False,
        "mac_execution_claim_allowed": False,
    }


def build_handoff_package_from_request(
    raw_request: Mapping[str, Any],
    *,
    source_request_filename: str,
    created_at: str = DEFAULT_GENERATED_AT,
) -> MacWorkerHandoffPackage | None:
    source_request_id = str(raw_request.get("request_id") or _stable_id("missing_request_id", source_request_filename))
    requested_worker, target_surface, reason = classify_mac_worker(raw_request)
    if requested_worker == "UNKNOWN_FAIL_CLOSED" or target_surface == "unknown" or blockers_for_request(raw_request):
        return None
    source_refs = _safe_refs(raw_request.get("source_refs") or raw_request.get("readback_files") or raw_request.get("proof_refs") or ())
    artifact_refs = _safe_refs(raw_request.get("artifact_refs") or raw_request.get("attachment_refs") or ())
    scoped_context_refs = _safe_refs(raw_request.get("scoped_context_refs") or raw_request.get("context_package_refs") or ())
    if requested_worker == "MAC_AUDIO_PLAYBACK":
        spoken_ref = raw_request.get("spoken_response_packet_ref") or raw_request.get("spoken_response_packet")
        source_refs = tuple(dict.fromkeys((*source_refs, *_safe_refs(spoken_ref or "spoken_response_packet_ref:pending"))))
    return MacWorkerHandoffPackage(
        handoff_id=f"mac_worker_handoff_{_safe_filename_part(source_request_id)}",
        source_request_id=source_request_id,
        source_request_filename=source_request_filename,
        requested_worker=requested_worker,
        target_machine="MAC",
        target_surface=target_surface,
        workflow_ref=str(raw_request.get("workflow_ref") or "unknown"),
        world_ref=str(raw_request.get("world_ref") or "openclaw"),
        lane_ref=str(raw_request.get("lane_ref") or "mac_worker_handoff_v0"),
        task_goal=reason,
        operator_message_summary=_safe_summary(raw_request),
        scoped_context_refs=scoped_context_refs,
        source_refs=source_refs,
        artifact_refs=artifact_refs,
        validation_expectations=validation_expectations_for(requested_worker),
        forbidden_actions=forbidden_actions_for(requested_worker),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        response_expected=True,
        response_path_policy=response_path_policy(source_request_id),
        created_at=created_at,
        next_safe_move="Run the Mac worker handoff lane; do not treat this package as execution authority.",
    )


def build_handoff_payload_from_request(
    raw_request: Mapping[str, Any],
    *,
    source_request_filename: str,
    created_at: str = DEFAULT_GENERATED_AT,
) -> dict[str, Any]:
    requested_worker, target_surface, reason = classify_mac_worker(raw_request)
    blockers = list(blockers_for_request(raw_request))
    if requested_worker == "UNKNOWN_FAIL_CLOSED":
        blockers.append(
            _blocker(
                "UNKNOWN_MAC_WORKER",
                "No supported Mac worker target could be selected safely.",
                "high",
                "Clarify whether this is Mac UI, Xcode, screenshot, visual workspace, audio playback, or Apple app boundary work.",
            )
        )
    if target_surface == "unknown":
        blockers.append(
            _blocker(
                "MISSING_TARGET_SURFACE",
                "The handoff target surface is missing or unknown.",
                "high",
                "Provide the Mac surface, such as Mission Control app, Xcode, or visual workspace.",
            )
        )
    package = build_handoff_package_from_request(
        raw_request,
        source_request_filename=source_request_filename,
        created_at=created_at,
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": created_at,
        "requested_workers": REQUESTED_WORKERS,
        "target_surfaces": TARGET_SURFACES,
        "blocker_types": BLOCKER_TYPES,
        "handoff_output_policy": {
            "pc_output_dir": DEFAULT_HANDOFF_OUTPUT_DIR.as_posix(),
            "mac_visible_dir": MAC_VISIBLE_HANDOFF_DIR,
            "per_request_filename": "mac_worker_handoff_<source_request_id>.json",
            "atomic_write_policy": "write temporary JSON then rename into place",
            "create_output_dir_if_missing": True,
        },
        "selected_worker": requested_worker,
        "selected_target_surface": target_surface,
        "selection_reason": reason,
        "handoff_package": asdict(package) if package else None,
        "blockers": tuple(asdict(blocker) for blocker in blockers),
        "examples": {},
        "authority_boundary": AUTHORITY_BOUNDARY,
        "next_safe_move": (
            "Write the handoff package to the Mac-visible handoff directory."
            if package
            else "Fix blockers before creating a Mac worker handoff package."
        ),
    }
    payload["machine_proof"] = _machine_proof(payload)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def write_handoff_package(
    payload: Mapping[str, Any],
    output_dir: Path = DEFAULT_HANDOFF_OUTPUT_DIR,
) -> Path:
    package = payload.get("handoff_package")
    if not isinstance(package, Mapping):
        raise ValueError("Cannot write Mac worker handoff package while package is blocked or missing.")
    if output_dir.is_symlink():
        raise ValueError("Mac handoff output path must not be a symlink.")
    request_id = str(package.get("source_request_id") or "unknown_request")
    path = output_dir / f"mac_worker_handoff_{_safe_filename_part(request_id)}.json"
    file_payload = {
        "schema_version": SCHEMA_VERSION,
        "contract_status": CONTRACT_STATUS,
        "handoff_package": package,
        "blockers": payload.get("blockers") or (),
        "operator_headline": "Mac worker handoff package ready",
        "operator_message": "This package routes Mac-owned work to a future Mac worker lane. Nothing has been executed.",
        "next_safe_move": "Run the Mac worker handoff lane.",
        "terminal": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "machine_proof": {
            "mac_execution_performed": False,
            "mac_automation_performed": False,
            "xcode_execution_performed": False,
            "screenshot_capture_performed": False,
            "file_mutation_performed": False,
            "external_action_performed": False,
            "send_submit_performed": False,
            "credential_handling_performed": False,
            "raw_body_ingestion_performed": False,
            "all_authority_boundary_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }
    _atomic_write_text(path, stable_json(file_payload))
    return path


def _example_request(request_id: str, message: str) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "source_request_filename": f"{request_id}.json",
        "request_type": "CHAT",
        "workflow_ref": "mac_worker_handoff_fixture",
        "world_ref": "openclaw",
        "lane_ref": "mac_worker_handoff_v0",
        "operator_message": message,
        "sanitized_message_summary": message,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def build_examples(*, created_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    examples: dict[str, Any] = {}
    fixtures = {
        "mac_ui": _example_request("mac_ui_render_task", "Make the chat response look better on Mac."),
        "xcode_build": _example_request("xcode_build_validation", "Check if the Mac app builds in Xcode."),
        "visual_workspace": _example_request("visual_workspace_request", "Show me the invoice workspace visually."),
        "blocked_mail_send": _example_request("blocked_mail_send", "Open Mail and send the invoice."),
        "audio_playback": {
            **_example_request("audio_playback_handoff", "Read this response aloud."),
            "spoken_response_packet_ref": "spoken_response_packet_ref:latest",
        },
    }
    for name, request in fixtures.items():
        payload = build_handoff_payload_from_request(
            request,
            source_request_filename=str(request["source_request_filename"]),
            created_at=created_at,
        )
        examples[name] = {
            "request_summary": request["sanitized_message_summary"],
            "selected_worker": payload["selected_worker"],
            "selected_target_surface": payload["selected_target_surface"],
            "handoff_package": payload["handoff_package"],
            "blockers": payload["blockers"],
            "package_created": payload["handoff_package"] is not None,
        }
    return examples


def build_read_model(*, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    examples = build_examples(created_at=generated_at)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "mac_worker_handoff_package_model_fields": tuple(field.name for field in fields(MacWorkerHandoffPackage)),
        "mac_worker_handoff_blocker_model_fields": tuple(field.name for field in fields(MacWorkerHandoffBlocker)),
        "requested_workers": REQUESTED_WORKERS,
        "target_surfaces": TARGET_SURFACES,
        "blocker_types": BLOCKER_TYPES,
        "handoff_output_path": DEFAULT_HANDOFF_OUTPUT_DIR.as_posix(),
        "mac_visible_path": MAC_VISIBLE_HANDOFF_DIR,
        "response_publication": {
            "pc_response_dir": DEFAULT_RESPONSE_DIR.as_posix(),
            "mac_visible_response_dir": MAC_VISIBLE_RESPONSE_DIR,
            "per_request_response": "openclaw_response_for_mac_<source_request_id>.json",
            "latest_response": "openclaw_response_for_mac_latest.json",
        },
        "validation_expectation_policy": {
            worker: validation_expectations_for(worker)
            for worker in REQUESTED_WORKERS
            if worker != "UNKNOWN_FAIL_CLOSED"
        },
        "forbidden_actions": forbidden_actions_for("MAC_CODEX"),
        "examples": examples,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "next_safe_move": "Use this package only to hand Mac-owned work to a future Mac lane; do not execute from PC.",
    }
    payload["machine_proof"] = _machine_proof(payload)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def _machine_proof(payload: Mapping[str, Any]) -> dict[str, Any]:
    examples = payload.get("examples") or {}
    mac_ui = examples.get("mac_ui", {}) if isinstance(examples, Mapping) else {}
    xcode = examples.get("xcode_build", {}) if isinstance(examples, Mapping) else {}
    visual = examples.get("visual_workspace", {}) if isinstance(examples, Mapping) else {}
    blocked = examples.get("blocked_mail_send", {}) if isinstance(examples, Mapping) else {}
    audio = examples.get("audio_playback", {}) if isinstance(examples, Mapping) else {}
    return {
        "mac_worker_handoff_package_model_present": True,
        "mac_worker_handoff_blocker_model_present": True,
        "handoff_output_path_correct": str(payload.get("handoff_output_path") or DEFAULT_HANDOFF_OUTPUT_DIR.as_posix())
        == DEFAULT_HANDOFF_OUTPUT_DIR.as_posix(),
        "mac_visible_path_correct": str(payload.get("mac_visible_path") or MAC_VISIBLE_HANDOFF_DIR) == MAC_VISIBLE_HANDOFF_DIR,
        "mac_ui_example_present": mac_ui.get("selected_worker") == "MAC_CODEX" and mac_ui.get("package_created") is True,
        "xcode_build_example_present": xcode.get("selected_worker") == "MAC_XCODE_BUILD" and xcode.get("package_created") is True,
        "visual_workspace_example_present": visual.get("selected_worker") == "MAC_VISUAL_WORKSPACE" and visual.get("package_created") is True,
        "blocked_mail_send_example_present": any(
            blocker.get("blocker_type") in {"APP_AUTOMATION_REQUESTED", "EXTERNAL_ACTION_REQUESTED"}
            for blocker in blocked.get("blockers", ())
            if isinstance(blocker, Mapping)
        ),
        "audio_playback_example_present": audio.get("selected_worker") == "MAC_AUDIO_PLAYBACK" and audio.get("package_created") is True,
        "validation_expectations_included": all(
            bool(example.get("handoff_package", {}).get("validation_expectations"))
            for key, example in examples.items()
            if key != "blocked_mail_send" and isinstance(example, Mapping)
        ),
        "response_publication_modeled": "response_publication" in payload,
        "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "mac_execution_performed": False,
        "mac_automation_performed": False,
        "xcode_execution_performed": False,
        "screenshot_capture_performed": False,
        "file_mutation_performed": False,
        "external_action_performed": False,
        "send_submit_performed": False,
        "credential_handling_performed": False,
        "raw_body_ingestion_performed": False,
        "mac_sync_import_run": False,
        "mission_control_swift_changed": False,
        "git_push_pull_fetch_run": False,
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "content_hash": None,
    }


def format_operator_markdown(payload: Mapping[str, Any]) -> str:
    examples = payload["examples"]
    return "\n".join(
        [
            "# PC-to-Mac Worker Handoff Package",
            "",
            f"Status: {payload['contract_status']}",
            f"Output path: {payload['handoff_output_path']}",
            f"Mac-visible path: {payload['mac_visible_path']}",
            "",
            "Examples:",
            f"- Mac UI: {examples['mac_ui']['selected_worker']} / package created: {examples['mac_ui']['package_created']}",
            f"- Xcode build: {examples['xcode_build']['selected_worker']} / package created: {examples['xcode_build']['package_created']}",
            f"- Visual workspace: {examples['visual_workspace']['selected_worker']} / package created: {examples['visual_workspace']['package_created']}",
            f"- Blocked Mail send: blockers {', '.join(blocker['blocker_type'] for blocker in examples['blocked_mail_send']['blockers'])}",
            f"- Audio playback: {examples['audio_playback']['selected_worker']} / package created: {examples['audio_playback']['package_created']}",
            "",
            "Boundary:",
            "- No Mac execution, Mac automation, Xcode execution, screenshot capture, file mutation, external action, send/submit, credential handling, raw-body ingestion, Mac sync/import, Swift change, or push.",
            "",
            f"Next safe move: {payload['next_safe_move']}",
            "",
        ]
    )


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    _atomic_write_text(json_path, stable_json(payload))
    _atomic_write_text(operator_path, format_operator_markdown(payload))
    return json_path, operator_path


def build_summary(payload: Mapping[str, Any], json_path: Path, operator_path: Path) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_status": CONTRACT_STATUS,
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "handoff_output_path": payload["handoff_output_path"],
        "mac_visible_path": payload["mac_visible_path"],
        "mac_ui_worker": payload["examples"]["mac_ui"]["selected_worker"],
        "xcode_build_worker": payload["examples"]["xcode_build"]["selected_worker"],
        "visual_workspace_worker": payload["examples"]["visual_workspace"]["selected_worker"],
        "blocked_mail_send_blockers": tuple(
            blocker["blocker_type"] for blocker in payload["examples"]["blocked_mail_send"]["blockers"]
        ),
        "audio_playback_worker": payload["examples"]["audio_playback"]["selected_worker"],
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "external_action_performed": payload["machine_proof"]["external_action_performed"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export deterministic PC-to-Mac worker handoff package read-model.")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    args = parser.parse_args(argv)
    payload = build_read_model(generated_at=args.generated_at)
    json_path, operator_path = write_exports(payload, args.export_root)
    output = payload if args.format == "json" else build_summary(payload, json_path, operator_path)
    print(stable_json(output), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
