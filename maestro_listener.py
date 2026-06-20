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
    return request


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
    request_id_for_reply: str | None = None
    try:
        request = build_operator_maestro_chat_request(text, message_id=message_id, chat_id=chat_id)
        request_id_for_reply = str(request["request_id"])
        write_bridge_request(request)
        response = await poll_bridge_response(request_id_for_reply)
        await update.message.reply_text(reply_text_from_bridge_response(response, request_id=request_id_for_reply))
    except Exception as exc:
        print(f"[maestro_listener] bridge error: {exc.__class__.__name__}", flush=True)
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
