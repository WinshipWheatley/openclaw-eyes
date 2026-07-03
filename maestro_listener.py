"""PC-side Telegram listener for Maestro.

Maestro is the operator front door. This listener receives Telegram text from
the authorized operator, records governed intake metadata, writes a bounded
file-bridge request for the PC request/response service, polls only the scoped
response for that request, and replies with display text. It never imports the
Maestro responder directly and never imports outbound send/execution paths.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:
    from telegram import Update
    from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
except ModuleNotFoundError:
    Update = Any  # type: ignore[misc, assignment]

    class ContextTypes:  # type: ignore[no-redef]
        DEFAULT_TYPE = Any

    ApplicationBuilder = None  # type: ignore[assignment]
    MessageHandler = None  # type: ignore[assignment]
    filters = None  # type: ignore[assignment]


DEFAULT_ENV_PATH = Path("/home/openclaw/.chief.env")
DEFAULT_REQUEST_INBOX = Path("/mnt/e/openclaw/mission_control_capture_requests/inbox")
DEFAULT_RESPONSE_DIR = Path("/mnt/e/openclaw/mission_control_responses/to_mac")
DEFAULT_IMAGE_INTAKE_DIR = Path("/home/openclaw/state/telegram_image_intake/maestro")
DEFAULT_DEFERRED_IMAGE_MARKER_DIR = Path("/home/openclaw/state/operator_file_metadata_intake/pending_vision")
DEFAULT_RESPONSE_TIMEOUT_S = 45.0
DEFAULT_RESPONSE_POLL_INTERVAL_S = 0.25

BLOCKED_OR_UNKNOWN_REPLY = (
    "Recorded, no action ran. Maestro did not receive a final answer for this request. "
    "Capability readback did not produce a final response. "
    "The request stayed inside the local bridge; no send, workflow, model, tool, or external action ran."
)
INTERIM_OR_STAGING_MARKERS = (
    "openclaw picked this up and is checking",
    "recorded, no action ran - i can answer date / system-orbit",
    "capability readback is live after reconcile",
    "workflow package staged",
)

AUTHORITY_BOUNDARY = {
    "live_daemon_allowed": False,
    "live_watcher_allowed": False,
    "live_auto_dispatch_allowed": False,
    "live_workflow_execution_allowed": False,
    "live_model_call_allowed": False,
    "live_tool_execution_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_email_draft_allowed": False,
    "live_email_send_allowed": False,
    "live_coupa_access_allowed": False,
    "live_coupa_submit_allowed": False,
    "live_browser_allowed": False,
    "live_invoice_generation_allowed": False,
    "live_attachment_allowed": False,
    "live_approval_request_allowed": False,
    "live_payment_tracking_write_allowed": False,
    "live_external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "sent": False,
    "paid": False,
    "coupa_submit_allowed": False,
    "gmail_access_allowed": False,
    "coupa_access_allowed": False,
    "browser_automation_allowed": False,
    "workbook_mutation_allowed": False,
    "workbook_open_allowed": False,
    "workbook_source_mutation_allowed": False,
    "excel_automation_allowed": False,
    "pdf_export_allowed": False,
    "email_draft_allowed": False,
    "ledger_mutation_allowed": False,
    "payment_marking_allowed": False,
    "business_action_allowed": False,
    "external_action_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "runtime_dispatch_allowed": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# ── Conversation-continuity flag (ADDITIVE, default OFF) ──────────────────────
def _continuity_enabled() -> bool:
    """Return True only when OPENCLAW_CONTINUITY_CAPSULE is "1" or "true".

    Cheap + import-safe: reads env at call time, no side-effects.
    """
    return os.environ.get("OPENCLAW_CONTINUITY_CAPSULE", "0").lower() in ("1", "true")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _content_hash(payload: Mapping[str, Any]) -> str:
    clone = json.loads(stable_json(dict(payload)))
    clone.pop("payload_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    if cleaned:
        return cleaned[:160]
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def _short_hash(*parts: Any) -> str:
    return hashlib.sha256(stable_json(parts).encode("utf-8")).hexdigest()[:12]


def _protected_text_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].strip()
    key, value = stripped.split("=", 1)
    key = key.strip()
    if not key:
        return None
    try:
        parsed = shlex.split(value, comments=False, posix=True)
    except ValueError:
        parsed = [value.strip().strip("'\"")]
    return key, parsed[0] if parsed else ""


def env_value(name: str, *, env_path: Path = DEFAULT_ENV_PATH) -> str:
    """Return a config value from process env or .chief.env without logging it."""

    value = os.environ.get(name)
    if value:
        return value
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise RuntimeError(f"{name} is not configured.") from exc
    for line in lines:
        parsed = _parse_env_line(line)
        if parsed is None:
            continue
        key, candidate = parsed
        if key == name and candidate:
            return candidate
    raise RuntimeError(f"{name} is not configured.")


def maestro_bot_token() -> str:
    return env_value("MAESTRO_BOT_TOKEN")


def authorized_user_id() -> int:
    return int(env_value("TELEGRAM_AUTHORIZED_USER_ID"))


async def _telegram_typing_loop(bot, chat_id: int | None) -> None:
    if chat_id is None:
        return
    while True:
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception as exc:
            print(f"[maestro_listener] typing indicator error: {exc.__class__.__name__}", flush=True)
        await asyncio.sleep(4.0)


def record_maestro_intake_metadata(
    *,
    text: str,
    source_message_id: str | None,
    source_user_label: str,
    operator_message: bool,
) -> str | None:
    """Best-effort governed receive metadata; never stores raw payloads."""

    try:
        from telegram_agent_intake import record_telegram_listener_update_safe

        return record_telegram_listener_update_safe(
            text=text,
            source_channel="maestro_listener",
            agent_target="maestro",
            source_message_id=source_message_id,
            source_user_label=source_user_label,
            operator_message=operator_message,
            route_intent=False,
        )
    except Exception as exc:
        print(f"[maestro_listener] governed intake failed: {exc.__class__.__name__}", flush=True)
        return None


def build_operator_maestro_chat_request(
    text: str,
    *,
    message_id: str,
    chat_id: int | None,
    created_at: str | None = None,
) -> dict[str, Any]:
    created_at = created_at or utc_now()
    request_id = f"maestro_telegram_{_safe_filename_part(str(message_id))}_{_short_hash(text, message_id, created_at)}"
    protected_text_hash = _protected_text_hash(text)
    request: dict[str, Any] = {
        "schema_version": "operator_instruction_writer_v0",
        "request_id": request_id,
        "source_request_id": request_id,
        "request_type": "WORKFLOW_PACKAGE_REQUEST_V0",
        "kind": "OPERATOR_INSTRUCTION_PACKAGE_REQUEST",
        "active_surface_ref": "operator_maestro_chat",
        "source_surface": "mission_control",
        "origin_surface": "telegram_pc_maestro_listener",
        "source_channel": "maestro_listener",
        "requested_mode": "operator",
        "result_receipt_required": True,
        "world": "general",
        "world_ref": "general",
        "current_world_ref": "general",
        "thread_ref": "operator_maestro_chat",
        "current_thread_ref": "operator_maestro_chat",
        "active_entity_ref": "operator_maestro_chat",
        "thread_title": "Maestro",
        "speaker": "Winship",
        "lane": "telegram_pc_maestro_listener",
        "relay_origin": None,
        "actor": "operator_winship",
        "message_provenance": {
            "speaker": "Winship",
            "lane": "telegram_pc_maestro_listener",
            "relay_origin": None,
            "actor": "operator_winship",
            "surface_ref": "operator_maestro_chat",
            "message_role": "operator_prompt",
        },
        "expected_response_provenance": {
            "speaker": "Maestro",
            "lane": "telegram_pc_maestro_listener",
            "relay_origin": None,
            "actor": "maestro",
            "surface_ref": "operator_maestro_chat",
            "message_role": "final_agent_reply",
            "processing_receipt_user_visible": False,
        },
        "correlation": {
            "request_id": request_id,
            "telegram_message_id": str(message_id),
            "telegram_chat_ref": f"sha256:{_short_hash('telegram_chat', chat_id)}" if chat_id is not None else "unknown",
        },
        "source_text": text,
        "operator_message": text,
        "source_text_ref": f"protected_text_hash:{protected_text_hash}",
        "protected_text_hash": protected_text_hash,
        "privacy_impact": "operator_chat_metadata_only",
        "idempotency_key": f"maestro_listener:telegram:{message_id}:{protected_text_hash}",
        "created_at": created_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "mac_wrote_request_only": False,
        "pc_listener_wrote_request_only": True,
        "no_external_action": True,
        "telegram_chat_ref": f"sha256:{_short_hash('telegram_chat', chat_id)}" if chat_id is not None else "unknown",
    }
    request["payload_hash"] = _content_hash(request)
    # ── CONTINUITY CAPSULE (flag-gated, ADDITIVE) ────────────────────────────
    # When ON: mint a deterministic conversation_id and add it to the request so
    # the processor can correlate capsule load/write to this exact chat session.
    # When OFF: no key added — dict is byte-identical to pre-edit behavior.
    if _continuity_enabled():
        try:
            import conversation_capsule as _cc
            _channel_id = str(request.get("source_channel") or "maestro_listener")
            _chat_id_str = str(chat_id) if chat_id is not None else "unknown"
            _first_seen = str(request.get("created_at") or created_at)
            request["conversation_id"] = _cc.mint_conversation_id(
                _channel_id, _chat_id_str, _first_seen
            )
        except Exception:
            pass  # never block the live path
    return request


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _which(tool: str) -> str | None:
    return shutil.which(tool)


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


_IMAGE_AGENT_SURFACES = {
    "maestro": {
        "source_channel": "maestro_listener",
        "origin_surface": "telegram_pc_maestro_listener",
        "lane": "telegram_pc_maestro_listener",
        "active_surface_ref": "operator_maestro_chat",
        "thread_ref": "operator_maestro_chat",
        "thread_title": "Maestro",
        "expected_speaker": "Maestro",
        "expected_actor": "maestro",
    },
    "cassandra": {
        "source_channel": "cassandra_listener",
        "origin_surface": "telegram_pc_cassandra_listener",
        "lane": "telegram_pc_cassandra_listener",
        "active_surface_ref": "operator_cassandra_chat",
        "thread_ref": "operator_cassandra_chat",
        "thread_title": "Cassandra",
        "expected_speaker": "Cassandra",
        "expected_actor": "cassandra",
    },
    "niles": {
        "source_channel": "niles_producer_listener",
        "origin_surface": "telegram_pc_niles_listener",
        "lane": "telegram_pc_niles_listener",
        "active_surface_ref": "operator_niles_chat",
        "thread_ref": "operator_niles_chat",
        "thread_title": "Niles",
        "expected_speaker": "Niles",
        "expected_actor": "niles",
    },
    "chief": {
        "source_channel": "chief_listener",
        "origin_surface": "telegram_pc_chief_listener",
        "lane": "telegram_pc_chief_listener",
        "active_surface_ref": "operator_chief_chat",
        "thread_ref": "operator_chief_chat",
        "thread_title": "Chief",
        "expected_speaker": "Chief",
        "expected_actor": "chief",
    },
    "guardian": {
        "source_channel": "guardian_listener",
        "origin_surface": "telegram_pc_guardian_listener",
        "lane": "telegram_pc_guardian_listener",
        "active_surface_ref": "operator_guardian_chat",
        "thread_ref": "operator_guardian_chat",
        "thread_title": "Guardian",
        "expected_speaker": "Guardian",
        "expected_actor": "guardian",
    },
}


def _retarget_image_request(
    request: dict[str, Any],
    *,
    agent: str,
    text: str,
    message_id: str,
    chat_id: int | None,
    created_at: str,
) -> dict[str, Any]:
    agent = str(agent or "maestro").strip().lower()
    surface = _IMAGE_AGENT_SURFACES.get(agent, _IMAGE_AGENT_SURFACES["maestro"])
    if agent == "maestro":
        return request
    request_id = f"{agent}_telegram_{_safe_filename_part(str(message_id))}_{_short_hash(agent, text, message_id, created_at)}"
    request["request_id"] = request_id
    request["source_request_id"] = request_id
    request["active_surface_ref"] = surface["active_surface_ref"]
    request["origin_surface"] = surface["origin_surface"]
    request["source_channel"] = surface["source_channel"]
    request["thread_ref"] = surface["thread_ref"]
    request["current_thread_ref"] = surface["thread_ref"]
    request["active_entity_ref"] = surface["thread_ref"]
    request["thread_title"] = surface["thread_title"]
    request["lane"] = surface["lane"]
    request["expected_response_provenance"].update(
        {
            "speaker": surface["expected_speaker"],
            "lane": surface["lane"],
            "actor": surface["expected_actor"],
            "surface_ref": surface["active_surface_ref"],
        }
    )
    request["message_provenance"].update(
        {
            "lane": surface["lane"],
            "surface_ref": surface["active_surface_ref"],
        }
    )
    request["correlation"].update(
        {
            "request_id": request_id,
            "telegram_message_id": str(message_id),
            "telegram_chat_ref": f"sha256:{_short_hash('telegram_chat', chat_id)}" if chat_id is not None else "unknown",
        }
    )
    request["idempotency_key"] = f"{surface['source_channel']}:telegram_image:{message_id}:{request['protected_text_hash']}"
    request["payload_hash"] = _content_hash(request)
    return request


def _deferred_image_marker_path(marker_dir: Path, *, agent: str, image_sha256: str, message_id: str) -> Path:
    safe_agent = _safe_filename_part(str(agent or "maestro").lower())
    safe_message = _safe_filename_part(str(message_id or "image"))
    return Path(marker_dir) / safe_agent / f"{safe_message}_{image_sha256[:16]}.json"


def write_deferred_image_marker(
    image_path: str | Path,
    *,
    agent: str,
    caption: str,
    message_id: str,
    chat_id: int | None,
    mime_type: str,
    ocr_result: Mapping[str, Any] | None,
    marker_dir: Path = DEFAULT_DEFERRED_IMAGE_MARKER_DIR,
    created_at: str | None = None,
) -> dict[str, Any]:
    image_path = Path(image_path)
    created_at = created_at or utc_now()
    image_sha256 = _sha256_file(image_path)
    marker_path = _deferred_image_marker_path(marker_dir, agent=agent, image_sha256=image_sha256, message_id=message_id)
    marker = {
        "schema_version": "operator_image_deferred_vision_v0",
        "status": "pending_vision_reprocess",
        "agent": str(agent or "maestro").strip().lower(),
        "local_path": str(image_path),
        "sha256": image_sha256,
        "mime": str(mime_type or "image/jpeg"),
        "caption": str(caption or "").strip(),
        "message_id": str(message_id),
        "chat_id": chat_id,
        "created_at": created_at,
        "last_ocr_error": str((ocr_result or {}).get("error") or ""),
        "raw_image_body_shared_with_model": False,
        "live_attachment_allowed": False,
        "next_safe_move": "Re-run local OCR later and write a normal bridge request only if text is extracted.",
    }
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(stable_json(marker), encoding="utf-8")
    return {"marker": marker, "marker_path": marker_path}


def build_operator_image_request(
    image_path: str | Path,
    *,
    agent: str = "maestro",
    caption: str,
    message_id: str,
    chat_id: int | None,
    mime_type: str = "image/jpeg",
    created_at: str | None = None,
    ocr_fn: Any | None = None,
    deferred_marker_dir: Path = DEFAULT_DEFERRED_IMAGE_MARKER_DIR,
) -> dict[str, Any]:
    image_path = Path(image_path)
    created_at = created_at or utc_now()
    if ocr_fn is None:
        from oclaw_doctools import ocr_image

        ocr_fn = ocr_image
    ocr_result = ocr_fn(image_path)
    ocr_text = str(ocr_result.get("text") or "").strip() if isinstance(ocr_result, Mapping) else ""
    caption = str(caption or "").strip()
    if not (isinstance(ocr_result, Mapping) and ocr_result.get("ok") is True and ocr_text):
        deferred = write_deferred_image_marker(
            image_path,
            agent=agent,
            caption=caption,
            message_id=message_id,
            chat_id=chat_id,
            mime_type=mime_type,
            ocr_result=ocr_result if isinstance(ocr_result, Mapping) else {},
            marker_dir=deferred_marker_dir,
            created_at=created_at,
        )
        return {
            "schema_version": "operator_image_deferred_vision_v0",
            "image_input_received": True,
            "image_deferred_for_reprocess": True,
            "deferred_marker_path": str(deferred["marker_path"]),
            "operator_reply": "noted — I can't read it yet, I'll reprocess when vision's back.",
            "image_ocr": {
                "method": "tesseract",
                "ok": False,
                "text": ocr_text,
                "confidence": str(ocr_result.get("confidence") or "") if isinstance(ocr_result, Mapping) else "",
                "error": str(ocr_result.get("error") or "") if isinstance(ocr_result, Mapping) else "",
            },
            "raw_image_body_shared_with_model": False,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
    prompt_parts = [
        caption or "Image received.",
        "OCR text from the attached image:",
        ocr_text or "(no OCR text extracted)",
    ]
    text = "\n\n".join(part for part in prompt_parts if part)
    request = build_operator_maestro_chat_request(
        text,
        message_id=message_id,
        chat_id=chat_id,
        created_at=created_at,
    )
    request = _retarget_image_request(
        request,
        agent=agent,
        text=text,
        message_id=message_id,
        chat_id=chat_id,
        created_at=created_at,
    )
    attachment = {
        "local_path": str(image_path),
        "sha256": _sha256_file(image_path),
        "mime": str(mime_type or "image/jpeg"),
        "caption": caption,
        "source": "telegram_photo",
    }
    request.update(
        {
            "image_input_received": True,
            "attachments": [attachment],
            "image_ocr": {
                "method": "tesseract",
                "ok": bool(isinstance(ocr_result, Mapping) and ocr_result.get("ok") is True),
                "text": ocr_text,
                "confidence": str(ocr_result.get("confidence") or "") if isinstance(ocr_result, Mapping) else "",
                "error": str(ocr_result.get("error") or "") if isinstance(ocr_result, Mapping) else "",
            },
            "raw_image_body_shared_with_model": False,
            "privacy_impact": "operator_image_local_ocr_text_only",
            "source_text": text,
            "operator_message": text,
        }
    )
    request["payload_hash"] = _content_hash(request)
    return request


def build_operator_maestro_image_request(
    image_path: str | Path,
    *,
    caption: str,
    message_id: str,
    chat_id: int | None,
    mime_type: str = "image/jpeg",
    created_at: str | None = None,
    ocr_fn: Any | None = None,
    deferred_marker_dir: Path = DEFAULT_DEFERRED_IMAGE_MARKER_DIR,
) -> dict[str, Any]:
    return build_operator_image_request(
        image_path,
        agent="maestro",
        caption=caption,
        message_id=message_id,
        chat_id=chat_id,
        mime_type=mime_type,
        created_at=created_at,
        ocr_fn=ocr_fn,
        deferred_marker_dir=deferred_marker_dir,
    )


def drain_deferred_image_markers(
    *,
    marker_dir: Path = DEFAULT_DEFERRED_IMAGE_MARKER_DIR,
    ocr_fn: Any | None = None,
    write_request_fn: Any | None = None,
) -> dict[str, Any]:
    if ocr_fn is None:
        from oclaw_doctools import ocr_image

        ocr_fn = ocr_image
    write_request_fn = write_request_fn or write_bridge_request
    marker_dir = Path(marker_dir)
    resolved = 0
    still_pending = 0
    failed = 0
    results: list[dict[str, Any]] = []
    for marker_path in sorted(marker_dir.glob("*/*.json")):
        marker = _read_json_file(marker_path)
        if marker.get("status") != "pending_vision_reprocess":
            continue
        image_path = Path(str(marker.get("local_path") or ""))
        ocr_result = ocr_fn(image_path)
        ocr_text = str(ocr_result.get("text") or "").strip() if isinstance(ocr_result, Mapping) else ""
        if not (isinstance(ocr_result, Mapping) and ocr_result.get("ok") is True and ocr_text):
            marker["last_ocr_error"] = str(ocr_result.get("error") or "") if isinstance(ocr_result, Mapping) else "ocr_result_not_mapping"
            marker["last_attempt_at"] = utc_now()
            marker_path.write_text(stable_json(marker), encoding="utf-8")
            still_pending += 1
            continue
        try:
            request = build_operator_image_request(
                image_path,
                agent=str(marker.get("agent") or "maestro"),
                caption=str(marker.get("caption") or ""),
                message_id=str(marker.get("message_id") or image_path.stem),
                chat_id=marker.get("chat_id"),
                mime_type=str(marker.get("mime") or "image/jpeg"),
                ocr_fn=lambda _path, _result=ocr_result: _result,
            )
            output_path = write_request_fn(request)
            marker["status"] = "resolved"
            marker["resolved_at"] = utc_now()
            marker["resolved_request_id"] = request["request_id"]
            marker["request_path"] = str(output_path)
            marker_path.write_text(stable_json(marker), encoding="utf-8")
            resolved += 1
            results.append({"marker_path": str(marker_path), "request_id": request["request_id"], "request_path": str(output_path)})
        except Exception as exc:
            marker["last_ocr_error"] = f"drain_error:{type(exc).__name__}"
            marker["last_attempt_at"] = utc_now()
            marker_path.write_text(stable_json(marker), encoding="utf-8")
            failed += 1
    return {"resolved": resolved, "still_pending": still_pending, "failed": failed, "results": results}


def write_bridge_request(
    request: Mapping[str, Any],
    *,
    inbox: Path = DEFAULT_REQUEST_INBOX,
) -> Path:
    inbox.mkdir(parents=True, exist_ok=True)
    request_id = str(request["request_id"])
    path = inbox / f"mission_control_operator_instruction_request_{_safe_filename_part(request_id)}.json"
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp_path.write_text(stable_json(dict(request)), encoding="utf-8")
    temp_path.replace(path)
    return path


def scoped_response_path(request_id: str, *, response_dir: Path = DEFAULT_RESPONSE_DIR) -> Path:
    return response_dir / f"openclaw_response_for_mac_{_safe_filename_part(request_id)}.json"


async def poll_bridge_response(
    request_id: str,
    *,
    response_dir: Path = DEFAULT_RESPONSE_DIR,
    timeout_s: float = DEFAULT_RESPONSE_TIMEOUT_S,
    poll_interval_s: float = DEFAULT_RESPONSE_POLL_INTERVAL_S,
) -> dict[str, Any] | None:
    response_path = scoped_response_path(request_id, response_dir=response_dir)
    deadline = asyncio.get_running_loop().time() + timeout_s
    while True:
        if response_path.exists() and response_path.is_file():
            try:
                value = json.loads(response_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                value = None
            if isinstance(value, dict) and str(value.get("source_request_id") or "") == request_id:
                return value
        if asyncio.get_running_loop().time() >= deadline:
            return None
        await asyncio.sleep(poll_interval_s)


def _first_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _looks_like_interim_or_staging_text(text: str) -> bool:
    normalized = _first_text(text).lower()
    if not normalized:
        return True
    return any(marker in normalized for marker in INTERIM_OR_STAGING_MARKERS)


def _blocked_or_unknown_response(payload: Mapping[str, Any] | None) -> bool:
    if not payload:
        return True
    if payload.get("terminal") is False or payload.get("processing_heartbeat_id"):
        return True
    internal_status = str(payload.get("internal_status") or "").upper()
    request_type = str(payload.get("request_type") or "").upper()
    headline = str(payload.get("operator_headline") or payload.get("headline") or "").lower()
    if internal_status and internal_status != "RESPONSE_READY":
        return True
    if request_type == "WORKFLOW_PACKAGE_REQUEST":
        return True
    if "workflow package staged" in headline:
        return True
    return False


def _text_candidates(payload: Mapping[str, Any]) -> tuple[str, ...]:
    candidates: list[str] = []
    top_level_keys = (
        "operator_message",
        "plain_summary",
        "summary",
        "eliwinship",
        "body",
    )
    for key in top_level_keys:
        text = _first_text(payload.get(key))
        if text:
            candidates.append(text)

    detail = payload.get("detail_disclosure")
    if isinstance(detail, Mapping):
        responder = detail.get("maestro_cassandra_responder")
        if isinstance(responder, Mapping):
            for key in ("plain_summary", "operator_message", "one_line_answer"):
                text = _first_text(responder.get(key))
                if text:
                    candidates.append(text)
        card = detail.get("dynamic_card_response")
        if isinstance(card, Mapping):
            for key in ("summary", "title"):
                text = _first_text(card.get(key))
                if text:
                    candidates.append(text)

    visible_cards = payload.get("visible_cards")
    if isinstance(visible_cards, list):
        for item in visible_cards:
            if not isinstance(item, Mapping):
                continue
            for key in ("summary", "title"):
                text = _first_text(item.get(key))
                if text:
                    candidates.append(text)

    for key in ("one_line_answer", "operator_headline", "headline"):
        text = _first_text(payload.get(key))
        if text:
            candidates.append(text)

    deduped: list[str] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return tuple(deduped)


def _best_final_text(payload: Mapping[str, Any]) -> str:
    for candidate in _text_candidates(payload):
        if not _looks_like_interim_or_staging_text(candidate):
            return candidate
    return ""


def _correlation_ref(request_id: str | None) -> str:
    raw = _first_text(request_id)
    if not raw:
        return "unknown"
    parts = raw.split("_")
    if len(parts) >= 4 and parts[0] == "maestro" and parts[1] == "telegram":
        return f"{parts[2]}:{parts[-1][:6]}"
    return _short_hash(raw)[:8]


def _append_provenance(text: str, *, payload: Mapping[str, Any] | None, request_id: str | None) -> str:
    source_request_id = ""
    if isinstance(payload, Mapping):
        source_request_id = _first_text(payload.get("source_request_id"))
    ref = _correlation_ref(source_request_id)
    label = f"Maestro-native reply - ref {ref}"
    body = _first_text(text)
    if not body:
        body = BLOCKED_OR_UNKNOWN_REPLY
    if not source_request_id:
        return body
    if label.lower() in body.lower():
        return body
    return f"{body}\n\n[{label}]"


def reply_text_from_bridge_response(payload: Mapping[str, Any] | None, *, request_id: str | None = None) -> str:
    if _blocked_or_unknown_response(payload):
        return _append_provenance(BLOCKED_OR_UNKNOWN_REPLY, payload=payload, request_id=request_id)
    assert payload is not None
    text = _best_final_text(payload)
    return _append_provenance(text or BLOCKED_OR_UNKNOWN_REPLY, payload=payload, request_id=request_id)


# ── Fast "hang on" ack ────────────────────────────────────────────────────────
# When a reply takes longer than the delay, send a casual acknowledgment so the operator
# sees it's being worked — the real answer follows. Fast answers cancel it before it
# fires. Default ON; fail-safe (a failed ack never blocks the real reply).
# Taste note: NO task-completion framing ("I'll get back to you when it's done") — that
# reads wrong on a casual message where nothing needs doing. Just a light "hang on".
# Varied by message content so it isn't the same robotic line every time.
_FAST_ACK_PHRASES = (
    "one sec…",
    "gimme a beat…",
    "hang tight…",
    "on it — one moment.",
    "lemme think on that…",
)


def _fast_ack_enabled(env: Mapping[str, Any] | None = None) -> bool:
    e = os.environ if env is None else env
    return str(e.get("OPENCLAW_FAST_ACK", "1")).strip().lower() not in (
        "0", "false", "no", "off", "")


def _fast_ack_delay(env: Mapping[str, Any] | None = None) -> float:
    e = os.environ if env is None else env
    try:
        return max(0.0, float(e.get("OPENCLAW_FAST_ACK_DELAY", "3")))
    except Exception:
        return 3.0


def _fast_ack_text(env: Mapping[str, Any] | None = None, *, message: str = "") -> str:
    e = os.environ if env is None else env
    override = e.get("OPENCLAW_FAST_ACK_TEXT")
    if override:
        return str(override)
    if not message:
        return _FAST_ACK_PHRASES[0]
    idx = int(hashlib.sha256(message.encode("utf-8")).hexdigest(), 16) % len(_FAST_ACK_PHRASES)
    return _FAST_ACK_PHRASES[idx]


def _fire_maestro_voice(text: str, chat_id: int | str | None) -> None:
    """Fire-and-forget Maestro Kokoro voice note (am_michael), non-blocking + fail-soft.
    Mirrors the producer/cassandra/chief listeners, which already voice their replies;
    the Maestro listener was the one reply path never wired for it. Toggle with
    OPENCLAW_AGENT_VOICE_NOTES=0."""
    try:
        if os.environ.get("OPENCLAW_AGENT_VOICE_NOTES", "1").strip().lower() not in ("1", "true", "yes"):
            return
        body = str(text or "").strip()
        if not body:
            return
        import agent_voice_sender

        asyncio.get_event_loop().run_in_executor(
            None, lambda: agent_voice_sender.send_agent_voice_note("maestro", body, chat_id=chat_id)
        )
    except Exception as exc:  # a voice issue must never break the text reply
        print(f"[maestro_listener] maestro voice note skipped: {exc.__class__.__name__}", flush=True)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    if not text:
        return

    auth_id = authorized_user_id()
    is_authorized_user = bool(update.effective_user and update.effective_user.id == auth_id)
    source_user_label = "operator" if is_authorized_user else "unverified_sender"
    source_message_id = str(getattr(update, "update_id", "")) or None
    record_maestro_intake_metadata(
        text=text,
        source_message_id=source_message_id,
        source_user_label=source_user_label,
        operator_message=is_authorized_user,
    )
    if not is_authorized_user:
        return

    chat_id = update.effective_chat.id if update.effective_chat else auth_id
    message_id = str(getattr(update.message, "message_id", "") or getattr(update, "update_id", "") or _short_hash(text))
    typing_task = asyncio.create_task(_telegram_typing_loop(context.bot, chat_id))

    # Fast "I'm on it" ack — fires only if the answer takes longer than the delay.
    async def _send_delayed_ack() -> None:
        try:
            await asyncio.sleep(_fast_ack_delay())
            await update.message.reply_text(_fast_ack_text(message=text))
        except asyncio.CancelledError:
            raise
        except Exception:
            pass  # a failed ack must never affect the real reply

    ack_task = asyncio.create_task(_send_delayed_ack()) if _fast_ack_enabled() else None

    request_id_for_reply: str | None = None
    try:
        request = build_operator_maestro_chat_request(text, message_id=message_id, chat_id=chat_id)
        request_id_for_reply = str(request["request_id"])
        write_bridge_request(request)
        response = await poll_bridge_response(request_id_for_reply)
        if ack_task is not None:
            ack_task.cancel()  # answer arrived; if before the delay, the ack is suppressed
        _maestro_reply = reply_text_from_bridge_response(response, request_id=request_id_for_reply)
        await update.message.reply_text(_maestro_reply)
        _fire_maestro_voice(_maestro_reply, chat_id)
    except Exception as exc:
        print(f"[maestro_listener] bridge error: {exc.__class__.__name__}", flush=True)
        await update.message.reply_text(
            reply_text_from_bridge_response(None, request_id=request_id_for_reply or message_id)
        )
    finally:
        typing_task.cancel()
        if ack_task is not None:
            ack_task.cancel()
        for _t in (typing_task, ack_task):
            if _t is None:
                continue
            try:
                await _t
            except asyncio.CancelledError:
                pass


def _ocr_read_document(image_path) -> dict | None:
    """Local OCR pre-read of a snapped document (checks etc.). Fail-soft: returns None on
    any error so the normal image path is never broken. Operator ask 2026-07-03: the SYSTEM
    should read the check, not just store it."""
    try:
        import document_ocr_intake as _ocr
        result = _ocr.read_document(image_path)
        if result.get("status") == "read" and result.get("doc_type") == "check":
            return result
    except Exception as exc:
        print(f"[maestro_listener] ocr pre-read skipped: {exc.__class__.__name__}", flush=True)
    return None


def _capture_check_evidence(result: dict, image_path, caption: str) -> None:
    """Write a governed payment-evidence record from OCR facts. Never posts to the ledger
    (money-write stays gated); this is evidence intake only. Fail-soft."""
    try:
        import json as _json
        import document_ocr_intake as _ocr
        from datetime import datetime, timezone
        c = result.get("check", {})
        stamp = _now_utc_compact() if "_now_utc_compact" in globals() else ""
        ev_dir = Path("/home/openclaw/Operator/finance-evidence")
        ev_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "captured_by": "maestro_listener.ocr_intake",
            "source": "operator_telegram_photo",
            "image_path": str(image_path),
            "caption": caption,
            "ledger_posted": False,
            "note": "OCR evidence only; ledger money-write remains gated + operator-approved.",
            "check_facts": c,
            "operator_summary": _ocr.summarize_for_operator(result),
        }
        out = ev_dir / f"ocr_check_evidence_{_safe_filename_part(str(image_path).split('/')[-2] or 'doc')}.json"
        out.write_text(_json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"[maestro_listener] check evidence capture skipped: {exc.__class__.__name__}", flush=True)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    auth_id = authorized_user_id()
    if not update.effective_user or update.effective_user.id != auth_id:
        return

    message_id = str(getattr(update.message, "message_id", "") or getattr(update, "update_id", "") or "photo")
    chat_id = update.effective_chat.id if update.effective_chat else auth_id
    caption = str(getattr(update.message, "caption", "") or "").strip()
    media = None
    mime_type = "image/jpeg"
    suffix = ".jpg"
    if getattr(update.message, "photo", None):
        media = update.message.photo[-1]
    elif getattr(update.message, "document", None):
        document = update.message.document
        media = document
        mime_type = str(getattr(document, "mime_type", "") or "image/jpeg")
        if "png" in mime_type:
            suffix = ".png"
        elif "webp" in mime_type:
            suffix = ".webp"
    if media is None:
        return

    request_id_for_reply: str | None = None
    typing_task = asyncio.create_task(_telegram_typing_loop(context.bot, chat_id))
    try:
        intake_dir = DEFAULT_IMAGE_INTAKE_DIR / _safe_filename_part(message_id)
        intake_dir.mkdir(parents=True, exist_ok=True)
        image_path = intake_dir / f"telegram_image{suffix}"
        telegram_file = await media.get_file()
        await telegram_file.download_to_drive(str(image_path))
        # Local OCR pre-read: if it's a check/financial doc, the SYSTEM reads it (not just stores it).
        _ocr_result = await asyncio.to_thread(_ocr_read_document, image_path)
        _ocr_summary = ""
        if _ocr_result is not None:
            await asyncio.to_thread(_capture_check_evidence, _ocr_result, image_path, caption)
            try:
                import document_ocr_intake as _ocr_mod
                _ocr_summary = _ocr_mod.summarize_for_operator(_ocr_result)
            except Exception:
                _ocr_summary = ""
        request = await asyncio.to_thread(
            build_operator_maestro_image_request,
            image_path,
            caption=caption,
            message_id=message_id,
            chat_id=chat_id,
            mime_type=mime_type,
        )
        if request.get("image_deferred_for_reprocess"):
            await update.message.reply_text(str(request.get("operator_reply") or "noted — I can't read it yet, I'll reprocess when vision's back."))
            return
        request_id_for_reply = str(request["request_id"])
        write_bridge_request(request)
        response = await poll_bridge_response(request_id_for_reply)
        _maestro_photo_reply = reply_text_from_bridge_response(response, request_id=request_id_for_reply)
        if _ocr_summary:
            _maestro_photo_reply = _ocr_summary + "\n\n" + _maestro_photo_reply
        await update.message.reply_text(_maestro_photo_reply)
        _fire_maestro_voice(_maestro_photo_reply, chat_id)
    except Exception as exc:
        print(f"[maestro_listener] image bridge error: {exc.__class__.__name__}", flush=True)
        await update.message.reply_text(
            reply_text_from_bridge_response(None, request_id=request_id_for_reply or message_id)
        )
    finally:
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass


def build_application():
    if ApplicationBuilder is None or MessageHandler is None or filters is None:
        raise RuntimeError("python-telegram-bot is required to run maestro_listener.")
    application = ApplicationBuilder().token(maestro_bot_token()).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    image_filter = filters.PHOTO | filters.Document.IMAGE
    application.add_handler(MessageHandler(image_filter, handle_photo))
    return application


async def run_listener(application=None, stop_event: asyncio.Event | None = None) -> None:
    application = application or build_application()
    updater = application.updater
    if updater is None:
        raise RuntimeError("Maestro listener application must have an updater.")

    loop = asyncio.get_running_loop()
    stop_event = stop_event or asyncio.Event()
    registered_signals: list[signal.Signals] = []
    polling_started = False
    app_started = False
    initialized = False

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
            registered_signals.append(sig)
        except (NotImplementedError, RuntimeError):
            pass

    try:
        await application.initialize()
        initialized = True
        if application.post_init:
            await application.post_init(application)
        await updater.start_polling()
        polling_started = True
        await application.start()
        app_started = True
        await stop_event.wait()
    finally:
        for sig in registered_signals:
            try:
                loop.remove_signal_handler(sig)
            except (NotImplementedError, RuntimeError):
                pass
        if polling_started:
            await updater.stop()
        if app_started and application.running:
            await application.stop()
        if initialized:
            await application.shutdown()


def main() -> None:
    print("[maestro_listener] starting", flush=True)
    asyncio.run(run_listener())


if __name__ == "__main__":
    main()
