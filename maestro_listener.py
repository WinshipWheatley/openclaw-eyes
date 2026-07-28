"""PC-side Telegram listener for Maestro.

Maestro is the operator front door. This listener receives Telegram text from
the authorized operator, records governed intake metadata, writes a bounded
file-bridge request for the PC request/response service, polls only the scoped
response for that request, and replies with display text. It never imports the
Maestro responder directly and never imports outbound send/execution paths.
"""

from __future__ import annotations

import asyncio
import contextvars
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import first_touch_decision
from fleet_receipt_index import (
    DEFAULT_SQLITE_PATH as DEFAULT_FLEET_RECEIPT_INDEX_PATH,
    ReceiptDescriptor,
    register_delivered_receipt,
    register_delivered_text_receipt,
    render_receipt_safe_visible_text,
    resolve_receipt_request,
)
from listener_resilience import clean_stale_carryover, honest_short_fail
from telegram_agent_intake import claim_listener_update
from telegram_listener_integrity import install_identity_preflight, run_verified_polling
from telegram_receipt_adapter import (
    contract_delivery_descriptor,
    register_operator_text_delivery_v2,
)

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
DEFAULT_ARTIFACT_RENDER_DIR = Path("/home/openclaw/state/operator_artifact_delivery/rendered")
DEFAULT_ARTIFACT_DELIVERY_RECEIPT_PATH = Path(
    "/home/openclaw/generated/receipts/operator_artifact_deliveries.jsonl"
)
DEFAULT_VOICE_DELIVERY_RECEIPT_PATH = Path(
    "/home/openclaw/generated/receipts/agent_voice_deliveries.jsonl"
)
DEFAULT_RESPONSE_TIMEOUT_S = 45.0
DEFAULT_RESPONSE_POLL_INTERVAL_S = 0.25

BLOCKED_OR_UNKNOWN_REPLY = (
    "Maestro did not receive a final response for this request. "
    "I can't verify whether a model ran from the scoped bridge result. "
    "The listener did not authorize an external action."
)
PROCESSING_ONLY_REPLY = (
    "Recorded, no action ran. Maestro received only a processing heartbeat, not a final answer. "
    "I can't verify from this heartbeat whether a model ran."
)
WORKFLOW_STAGED_REPLY = (
    "OpenClaw staged a workflow package instead of producing a final answer. "
    "I can't verify from this payload whether a model ran."
)
TIMEOUT_REPLY = (
    "Maestro's bounded answer attempt timed out before a final response was ready. "
    "The timeout payload does not prove that a model result exists."
)
STALE_CARRYOVER_REPLY = honest_short_fail(
    "Maestro",
    no_action_line="The bridge stayed local; no send, workflow, model, tool, or external action ran.",
    next_step="Retry after checking the request-response service and model contention.",
)
INTERIM_OR_STAGING_MARKERS = (
    "openclaw picked this up and is checking",
    "recorded, no action ran - i can answer date / system-orbit",
    "capability readback is live after reconcile",
    "workflow package staged",
    "staged a package instead of answering",
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
_OUTPUT_BOUNDARY_RECEIPT: contextvars.ContextVar[dict[str, Any] | None] = (
    contextvars.ContextVar("maestro_output_boundary_receipt", default=None)
)


def current_output_boundary_receipt() -> dict[str, Any] | None:
    receipt = _OUTPUT_BOUNDARY_RECEIPT.get()
    return dict(receipt) if isinstance(receipt, dict) else None


def _identity_gated_reply(text: str, *, question: str = "") -> str:
    """Banner every reply, and refuse to emit a nonce while identity is unproven.

    Two things happen here, both learned on 2026-07-28. The banner is rendered from
    the identity registry, so it cannot drift the way `Casandra bot` drifted from
    `Cassandra` — it IS the registry. And the interlock catches a nonce on the way
    out: a preview that lands in the wrong chat is worse than no preview, because it
    teaches the wrong human what a valid approval looks like.

    Enforcing at egress rather than at the caller means a future preview builder
    cannot forget to ask.
    """

    from agent_reply_egress import finalize_agent_reply

    return finalize_agent_reply("maestro", str(text or ""), question=question)


def _final_operator_reply(
    reply: str,
    *,
    source_request: str,
    action_receipt_refs: tuple[str, ...] = (),
) -> str:
    try:
        from operator_surface_guard import guard_operator_reply_with_receipt

        bounded = guard_operator_reply_with_receipt(
            str(reply or ""),
            agent_role="MAESTRO",
            source_request=source_request,
            action_receipt_refs=action_receipt_refs,
        )
        _OUTPUT_BOUNDARY_RECEIPT.set(bounded.receipt.to_dict())
        return _identity_gated_reply(bounded.visible_text, question=source_request)
    except Exception:
        _OUTPUT_BOUNDARY_RECEIPT.set({
            "outcome": "adapter_boundary_error",
            "raw_control_text_included": False,
        })
        return "Maestro couldn't safely render that answer just now. Nothing was sent or changed."


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


def _is_authorized_operator_private_chat(update: Update, auth_id: int) -> bool:
    user_id = getattr(getattr(update, "effective_user", None), "id", None)
    chat_id = getattr(getattr(update, "effective_chat", None), "id", None)
    return user_id == auth_id and chat_id == auth_id


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
    reply_to_message_id: str = "",
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

    # ── APPROVAL INTENT (narrow, additive, staging only) ─────────────────────
    # A "SEND <nonce>" from Telegram is approval-SHAPED, and Maestro's job is to
    # notice that and carry it — not to act on it. authority_boundary above stays
    # all-false: staging an intent is not execution, and nothing downstream may
    # read this block as permission. Chief/Guardian issue the scoped graduation
    # and google_access_broker performs the send behind its own gate; this block
    # cannot shorten that path.
    #
    # Attached BEFORE payload_hash on purpose, so the chat/message/reply/nonce
    # binding is covered by the request's own content hash and cannot be edited
    # in flight without invalidating it.
    try:
        from telegram_send_approval_engine import classify_approval_intent

        _intent = classify_approval_intent(
            text,
            message_id=str(message_id),
            chat_ref=str(request["telegram_chat_ref"]),
            reply_to_message_id=str(reply_to_message_id or ""),
            observed_at=created_at,
        )
        if _intent:
            request["approval_intent"] = _intent
    except Exception:
        # Recognition failing must never cost the operator their message. The
        # request still goes through as ordinary chat; it simply isn't staged.
        pass

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


def build_maestro_chat_replay_request(
    text: str,
    *,
    message_id: str,
    created_at: str | None = None,
    replay_actor: str = "pc_codex_desktop_replay",
) -> dict[str, Any]:
    """Build a Telegram-shaped processor probe that cannot impersonate or reach the operator."""

    request = build_operator_maestro_chat_request(
        text,
        message_id=message_id,
        chat_id=None,
        created_at=created_at,
    )
    request.update(
        {
            "speaker": "PC Codex Desktop replay",
            "actor": replay_actor,
            "replay_mode": "bounded_synthetic",
            "test_actor": True,
            "delivery_suppressed": True,
            "privacy_impact": "synthetic_replay_no_live_delivery",
            "idempotency_key": (
                f"maestro_listener:replay:{message_id}:{request['protected_text_hash']}"
            ),
            "telegram_chat_ref": "suppressed",
        }
    )
    request["message_provenance"] = {
        "speaker": "PC Codex Desktop replay",
        "lane": "pc_codex_desktop_replay",
        "relay_origin": None,
        "actor": replay_actor,
        "surface_ref": "operator_maestro_chat",
        "message_role": "synthetic_replay_prompt",
    }
    request["correlation"] = {
        **dict(request["correlation"]),
        "telegram_message_id": str(message_id),
        "telegram_chat_ref": "suppressed",
    }
    request["payload_hash"] = _content_hash(request)
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
    if request_type == "WORKFLOW_PACKAGE_REQUEST" and not _best_final_text(payload):
        return True
    if "workflow package staged" in headline and not _best_final_text(payload):
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


def _failure_specific_reply(payload: Mapping[str, Any] | None) -> str:
    if not payload:
        return BLOCKED_OR_UNKNOWN_REPLY
    blocked_reason = str(payload.get("blocked_reason") or "").casefold()
    request_type = str(payload.get("request_type") or "").upper()
    headline = str(payload.get("operator_headline") or payload.get("headline") or "").casefold()
    if blocked_reason == "guardian_output_denied":
        return _best_final_text(payload) or (
            "Guardian held this reply before publication. Ask me to retry or show the gate reason."
        )
    timeout_blob = " ".join(
        str(payload.get(key) or "")
        for key in ("internal_status", "blocked_reason", "operator_message", "why_it_happened")
    ).casefold()
    if "timeout" in timeout_blob or "timed out" in timeout_blob or "deadline_exceeded" in timeout_blob:
        return _best_final_text(payload) or TIMEOUT_REPLY
    if request_type == "WORKFLOW_PACKAGE_REQUEST" or "workflow package staged" in headline:
        return _best_final_text(payload) or WORKFLOW_STAGED_REPLY
    if payload.get("terminal") is False or payload.get("processing_heartbeat_id"):
        return PROCESSING_ONLY_REPLY
    return _best_final_text(payload) or BLOCKED_OR_UNKNOWN_REPLY


# Task 174: _correlation_ref was deleted with the visible provenance tag it
# manufactured — the correlation ref lives ONLY in the receipt channel now.


def _append_provenance(text: str, *, payload: Mapping[str, Any] | None, request_id: str | None) -> str:
    # ── Task 174 UPSTREAM ROOT FIX (the six MT1-MT6 fails were born HERE) ──
    # This function used to glue a machine correlation line onto the VISIBLE
    # reply: "\n\n[Maestro-native reply - ref 42:abcdef]". That bracketed
    # fragment starts with "[", so operator_surface_guard's per-fragment leak
    # check flagged it as JSON-shaped machine contract (reason
    # machine_contract_leak) on EVERY bridge reply carrying a
    # source_request_id — which decorated every good Maestro answer
    # (bare status, persona, clarify) with the "Routed for review..." footer.
    # Receipt lines belong in the RECEIPT CHANNEL, never visible text: the
    # correlation ref already travels in the bridge response payload
    # (source_request_id) and in the delivered-receipt registration
    # (_register_maestro_receipt_after_delivery); the operator-facing
    # affordance is the human "show receipt" hint appended by
    # render_receipt_safe_visible_text. So the visible surface now ships the
    # body ONLY. (The 2026-07-03 "tag is fine in text" ask is superseded by
    # the 174 doctrine: machine receipt refs never join visible text.)
    body = _first_text(text)
    if not body:
        body = BLOCKED_OR_UNKNOWN_REPLY
    return body


def _resilient_reply_text(text: str, *, payload: Mapping[str, Any] | None, request_id: str | None) -> str:
    return str(
        clean_stale_carryover(
            text,
            failure_text=_append_provenance(STALE_CARRYOVER_REPLY, payload=payload, request_id=request_id),
        )
    )


def _retrieval_status_suffix(payload: Mapping[str, Any] | None) -> str:
    """Turn a bare UNKNOWN into a refusal the operator can act on.

    Maestro answered `UNKNOWN` while `chief_status_rail.json` sat on disk at 30KB,
    because a retrieval failure and an honest empty were the same value. If the
    bridge reports a retrieval status, say which one it was.
    """

    if not isinstance(payload, Mapping):
        return ""
    try:
        import packet_retrieval_status as prs
    except Exception:  # noqa: BLE001 - never break a reply over a contract import
        return ""

    raw = payload.get("retrieval_status")
    if not isinstance(raw, Mapping):
        return ""
    status = str(raw.get("status") or "")
    if status not in prs.FAILURE_STATUSES:
        return ""
    result = prs.RetrievalResult(
        facts=[], status=status, detail=str(raw.get("detail") or ""),
        source_path=str(raw.get("source_path") or ""),
    )
    packet = {"source_refs": list(payload.get("source_refs") or ()), "facts": []}
    return prs.answer_suffix(packet, retrieval=result)


def _question_dominance_guard(payload: Mapping[str, Any] | None, text: str) -> str:
    """Refuse to relay a persona deflection as if it answered the question.

    Niles replied "What's the main goal: groove, melody, or arrangement?" to a
    technical exact-send question. That reads as engagement while carrying nothing,
    which is worse than an UNKNOWN because an UNKNOWN gets fixed.
    """

    if not isinstance(payload, Mapping) or not text:
        return text
    try:
        import grounded_answer_contract as gac
    except Exception:  # noqa: BLE001
        return text
    question = str(payload.get("source_text") or payload.get("operator_message") or "")
    if not question:
        return text
    ok, reason = gac.check_question_dominance(question, text)
    if ok:
        return text
    return (
        f"UNKNOWN — I did not answer your question. ({reason}) "
        "The reply I produced changed the subject rather than addressing it, so I am "
        "not relaying it. Nothing ran and nothing was sent."
    )


def reply_text_from_bridge_response(payload: Mapping[str, Any] | None, *, request_id: str | None = None) -> str:
    if _blocked_or_unknown_response(payload):
        reply = _append_provenance(_failure_specific_reply(payload), payload=payload, request_id=request_id)
        reply = _join_reply(reply, _retrieval_status_suffix(payload))
        return _resilient_reply_text(reply, payload=payload, request_id=request_id)
    assert payload is not None
    text = _question_dominance_guard(payload, _best_final_text(payload))
    reply = _append_provenance(text or BLOCKED_OR_UNKNOWN_REPLY, payload=payload, request_id=request_id)
    reply = _join_reply(reply, _retrieval_status_suffix(payload))
    return _resilient_reply_text(reply, payload=payload, request_id=request_id)


def _join_reply(reply: str, suffix: str) -> str:
    suffix = str(suffix or "").strip()
    if not suffix or suffix in str(reply or ""):
        return reply
    return f"{reply}\n\n{suffix}".strip()


def _reply_only_egress_enabled(env: Mapping[str, Any] | None = None) -> bool:
    e = os.environ if env is None else env
    return str(e.get("OPENCLAW_MAESTRO_REPLY_ONLY", "0")).strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(dict(payload), sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o660)
    try:
        os.write(descriptor, body)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _voice_receipt_path() -> Path:
    override = str(os.environ.get("OPENCLAW_VOICE_DELIVERY_RECEIPT_PATH") or "").strip()
    return Path(override) if override else DEFAULT_VOICE_DELIVERY_RECEIPT_PATH


def _fire_agent_voice(
    text: str,
    chat_id: int | str | None,
    *,
    speaker: str,
    source_request_id: str = "",
) -> None:
    """Use the addressed speaker's Kokoro profile through the Maestro carrier."""
    try:
        if os.environ.get("OPENCLAW_AGENT_VOICE_NOTES", "1").strip().lower() not in ("1", "true", "yes"):
            return
        body = str(text or "").strip()
        if not body:
            return
        import agent_voice_sender

        speaker_ref = str(speaker or "maestro").strip().lower()

        def _send_and_record() -> None:
            receipt = agent_voice_sender.send_agent_voice_note(
                speaker_ref,
                body,
                chat_id=chat_id,
                carrier_agent="maestro",
            )
            _append_jsonl(
                _voice_receipt_path(),
                {
                    "schema_version": "agent_voice_delivery_receipt_v1",
                    "source_request_id": source_request_id,
                    "speaker": receipt.agent,
                    "carrier": receipt.carrier_agent or "maestro",
                    "voice": receipt.voice,
                    "text_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                    "synthesized": receipt.synthesized,
                    "delivery_succeeded": receipt.sent,
                    "delivered_message_id": receipt.delivered_message_id,
                    "delivered_at": receipt.delivered_at or utc_now(),
                    "fallback": "words_already_delivered_as_text" if not receipt.sent else "",
                    "error_class": receipt.error.split(":", 1)[0][:80] if receipt.error else "",
                },
            )

        asyncio.get_running_loop().run_in_executor(None, _send_and_record)
    except Exception as exc:  # a voice issue must never break the text reply
        print(f"[maestro_listener] agent voice note skipped: {exc.__class__.__name__}", flush=True)


def _fire_maestro_voice(
    text: str,
    chat_id: int | str | None,
    *,
    source_request_id: str = "",
) -> None:
    _fire_agent_voice(
        text,
        chat_id,
        speaker="maestro",
        source_request_id=source_request_id,
    )


def _fleet_receipt_index_path() -> Path:
    override = str(os.environ.get("OPENCLAW_FLEET_RECEIPT_INDEX_DB") or "").strip()
    return Path(override) if override else DEFAULT_FLEET_RECEIPT_INDEX_PATH


def _reply_to_message_id(message: Any) -> str:
    replied_to = getattr(message, "reply_to_message", None)
    return str(getattr(replied_to, "message_id", "") or "")


def _typed_contract_receipt(payload: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    detail = payload.get("detail_disclosure")
    if not isinstance(detail, Mapping):
        return None
    responder = detail.get("maestro_cassandra_responder")
    if not isinstance(responder, Mapping):
        return None
    proof = responder.get("machine_proof")
    if not isinstance(proof, Mapping):
        return None
    decision = proof.get("typed_contract_decision")
    return decision if isinstance(decision, Mapping) else None


def _receipt_descriptor_from_bridge_response(
    payload: Mapping[str, Any] | None,
) -> ReceiptDescriptor | None:
    """Translate only the two durable Maestro contract outcomes.

    A successful ``stage_handoff`` means the workflow stager already committed
    its queue receipt. A preserved-session pointer belongs to the typed-contract
    provider and is eligible only when that provider says persistence succeeded.
    """

    decision = _typed_contract_receipt(payload)
    if decision is None:
        return None
    try:
        return contract_delivery_descriptor(
            decision,
            actor="maestro",
            surface="operator_maestro_chat",
        )
    except Exception as exc:
        print(
            f"[maestro_listener] receipt descriptor skipped: {exc.__class__.__name__}",
            flush=True,
        )
    return None


def _raw_receipt_ref_from_bridge_response(payload: Mapping[str, Any] | None) -> str:
    decision = _typed_contract_receipt(payload)
    if decision is None:
        return ""
    nested_receipt = decision.get("receipt")
    receipt = nested_receipt if isinstance(nested_receipt, Mapping) else decision
    return str(receipt.get("receipt_pointer") or "").strip()


def _without_raw_receipt_ref(text: str, raw_ref: str, *, advertise: bool = True) -> str:
    return render_receipt_safe_visible_text(
        text,
        raw_ref=raw_ref,
        advertise=advertise,
    )


def _register_maestro_receipt_after_delivery(
    descriptor: ReceiptDescriptor | None,
    *,
    chat_id: int | str,
    source_message_id: str,
    delivered_message: Any,
) -> None:
    """Fail-soft after Telegram confirms the final reply's message id."""

    if descriptor is None or not source_message_id:
        return
    delivered_message_id = str(getattr(delivered_message, "message_id", "") or "")
    if not delivered_message_id:
        return
    try:
        register_delivered_receipt(
            descriptor,
            surface="operator_maestro_chat",
            bot_identity="maestro",
            chat_id=str(chat_id),
            source_message_id=source_message_id,
            delivered_message_id=delivered_message_id,
            delivery_succeeded=True,
            db_path=_fleet_receipt_index_path(),
        )
    except Exception as exc:
        # Delivery already succeeded. Index failure must not trigger a second
        # Telegram reply or route into the bridge failure fallback.
        print(
            f"[maestro_listener] delivered receipt index skipped: {exc.__class__.__name__}",
            flush=True,
        )


def _register_maestro_delivered_text_after_delivery(
    *,
    delivered_text: str,
    source_request_id: str,
    chat_id: int | str,
    source_message_id: str,
    delivered_message: Any,
    response_author: str,
) -> None:
    """Fail-soft delivery-boundary proof for every final Maestro reply."""

    delivered_message_id = str(getattr(delivered_message, "message_id", "") or "")
    if not delivered_message_id or not source_message_id or not source_request_id:
        return
    try:
        register_delivered_text_receipt(
            surface="operator_maestro_chat",
            bot_identity="maestro",
            chat_id=str(chat_id),
            source_message_id=source_message_id,
            delivered_message_id=delivered_message_id,
            source_request_id=source_request_id,
            delivered_text=delivered_text,
            delivery_succeeded=True,
            db_path=_fleet_receipt_index_path(),
        )
        register_operator_text_delivery_v2(
            delivered_text=delivered_text,
            source_request_id=source_request_id,
            chat_id=chat_id,
            source_message_id=source_message_id,
            delivered_message=delivered_message,
            effective_service="maestro-listener.service",
            effective_surface="operator_maestro_chat",
            effective_bot_identity="maestro",
            token_owner_label="MAESTRO_BOT_TOKEN",
            bot_token=maestro_bot_token(),
            response_author=response_author,
            carrier_identity="maestro",
            db_path=_fleet_receipt_index_path(),
        )
    except Exception as exc:
        print(
            f"[maestro_listener] delivered text receipt skipped: {exc.__class__.__name__}",
            flush=True,
        )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bare_sha256(value: object) -> str:
    text = str(value or "").strip().lower()
    return text.removeprefix("sha256:")


def _operator_response_disposition(
    payload: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    detail = payload.get("detail_disclosure")
    if not isinstance(detail, Mapping):
        return None
    disposition = detail.get("operator_response_disposition")
    return disposition if isinstance(disposition, Mapping) else None


def _selected_proof_artifact(payload: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    artifacts = payload.get("proof_artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 1:
        return None
    artifact = artifacts[0]
    return artifact if isinstance(artifact, Mapping) else None


def _artifact_delivery_receipt_path() -> Path:
    override = str(os.environ.get("OPENCLAW_ARTIFACT_DELIVERY_RECEIPT_PATH") or "").strip()
    return Path(override) if override else DEFAULT_ARTIFACT_DELIVERY_RECEIPT_PATH


def _verified_telegram_image(
    artifact: Mapping[str, Any],
) -> tuple[Path, str, str]:
    rendered_path = Path(str(artifact.get("rendered_image_path") or ""))
    rendered_sha = _bare_sha256(artifact.get("rendered_image_sha256"))
    if rendered_path.is_absolute() and rendered_path.is_file() and rendered_sha:
        actual = _sha256_file(rendered_path)
        if actual != rendered_sha:
            raise RuntimeError("rendered_image_hash_mismatch")
        return rendered_path, actual, "preverified_render"

    pdf_path = Path(str(artifact.get("bridge_path") or ""))
    artifact_sha = _bare_sha256(artifact.get("sha256"))
    if not pdf_path.is_absolute() or not pdf_path.is_file():
        raise RuntimeError("artifact_pdf_missing")
    if not artifact_sha or _sha256_file(pdf_path) != artifact_sha:
        raise RuntimeError("artifact_pdf_hash_mismatch")
    renderer = shutil.which("pdftoppm")
    if not renderer:
        raise RuntimeError("pdftoppm_unavailable")
    DEFAULT_ARTIFACT_RENDER_DIR.mkdir(parents=True, exist_ok=True)
    output_prefix = DEFAULT_ARTIFACT_RENDER_DIR / artifact_sha
    image_path = output_prefix.with_suffix(".png")
    if not image_path.is_file():
        subprocess.run(
            [
                renderer,
                "-f",
                "1",
                "-l",
                "1",
                "-singlefile",
                "-png",
                "-r",
                "160",
                pdf_path.as_posix(),
                output_prefix.as_posix(),
            ],
            check=True,
            capture_output=True,
            timeout=45,
        )
    return image_path, _sha256_file(image_path), "pdftoppm_page_1"


def _response_speaker(payload: Mapping[str, Any] | None) -> str:
    if not isinstance(payload, Mapping):
        return "maestro"
    detail = payload.get("detail_disclosure")
    if isinstance(detail, Mapping):
        display = detail.get("operator_display")
        if isinstance(display, Mapping) and str(display.get("speaker_ref") or "").strip():
            return str(display["speaker_ref"]).strip().lower()
        disposition = detail.get("operator_response_disposition")
        if isinstance(disposition, Mapping) and str(disposition.get("addressed_agent") or "").strip():
            return str(disposition["addressed_agent"]).strip().lower()
    return str(payload.get("response_author") or "maestro").strip().lower()


async def _deliver_telegram_artifact(
    *,
    bot: Any,
    chat_id: int | str,
    caption: str,
    payload: Mapping[str, Any],
    source_request_id: str,
    source_message_id: str,
) -> Any:
    artifact = _selected_proof_artifact(payload)
    disposition = _operator_response_disposition(payload)
    if artifact is None or disposition is None:
        raise RuntimeError("telegram_artifact_disposition_incomplete")
    if disposition.get("delivery_suppressed") is True:
        raise RuntimeError("telegram_artifact_delivery_suppressed")
    image_path, rendered_sha, render_source = await asyncio.to_thread(
        _verified_telegram_image,
        artifact,
    )
    with image_path.open("rb") as photo:
        delivered_message = await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
        )
    delivered_message_id = str(getattr(delivered_message, "message_id", "") or "")
    if not delivered_message_id:
        raise RuntimeError("telegram_photo_delivery_missing_message_id")
    selected_artifact_sha = _bare_sha256(artifact.get("sha256"))
    receipt = {
        "schema_version": "operator_artifact_delivery_receipt_v1",
        "receipt_id": "artifact-delivery:" + hashlib.sha256(
            "\0".join((source_request_id, selected_artifact_sha, delivered_message_id)).encode("utf-8")
        ).hexdigest()[:24],
        "source_request_id": source_request_id,
        "source_message_id": source_message_id,
        "active_surface": "operator_maestro_chat",
        "effective_bot_identity": "maestro",
        "speaker": _response_speaker(payload),
        "artifact_variant": str(disposition.get("artifact_variant") or "current"),
        "selected_artifact_id": str(artifact.get("artifact_id") or ""),
        "selected_artifact_sha256": selected_artifact_sha,
        "rendered_image_sha256": rendered_sha,
        "render_source": render_source,
        "caption_sha256": hashlib.sha256(caption.encode("utf-8")).hexdigest(),
        "delivered_message_id": delivered_message_id,
        "delivered_at": utc_now(),
        "delivery_succeeded": True,
        "provider_draft_created": False,
        "business_send_performed": False,
        "money_moved": False,
    }
    _append_jsonl(_artifact_delivery_receipt_path(), receipt)
    return delivered_message


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    if not text:
        return

    auth_id = authorized_user_id()
    if not _is_authorized_operator_private_chat(update, auth_id):
        return
    if not claim_listener_update(update, role="maestro", source_channel="maestro_listener"):
        return

    chat_id = update.effective_chat.id if update.effective_chat else auth_id
    intake_source_message_id = str(getattr(update, "update_id", "") or "")
    delivery_source_message_id = str(getattr(update.message, "message_id", "") or "")
    try:
        receipt_resolution = resolve_receipt_request(
            text,
            surface="operator_maestro_chat",
            bot_identity="maestro",
            chat_id=str(chat_id),
            reply_to_message_id=_reply_to_message_id(update.message),
            db_path=_fleet_receipt_index_path(),
        )
    except Exception as exc:
        print(
            f"[maestro_listener] receipt lookup failed: {exc.__class__.__name__}",
            flush=True,
        )
        await update.message.reply_text(_final_operator_reply(
            "I couldn't read the delivered-receipt index right now. No action ran.",
            source_request=text,
        ))
        return
    if receipt_resolution is not None:
        try:
            await update.message.reply_text(
                _final_operator_reply(receipt_resolution.text, source_request=text)
            )
        except Exception as exc:
            print(
                f"[maestro_listener] receipt reply failed: {exc.__class__.__name__}",
                flush=True,
            )
        return

    first_touch = first_touch_decision.attempt_first_touch(
        text,
        agent="maestro",
        surface="maestro_listener",
    )
    if first_touch.handled and first_touch.decision is not None:
        reply = _final_operator_reply(
            first_touch.decision.reply,
            source_request=text,
        )
        await update.message.reply_text(reply)
        return

    record_maestro_intake_metadata(
        text=text,
        source_message_id=intake_source_message_id or None,
        source_user_label="operator",
        operator_message=True,
    )

    message_id = delivery_source_message_id or intake_source_message_id or _short_hash(text)
    typing_task = asyncio.create_task(_telegram_typing_loop(context.bot, chat_id))

    request_id_for_reply: str | None = None
    try:
        request = build_operator_maestro_chat_request(text, message_id=message_id, chat_id=chat_id)
        request_id_for_reply = str(request["request_id"])
        write_bridge_request(request)
        response = await poll_bridge_response(request_id_for_reply)
        receipt_descriptor = _receipt_descriptor_from_bridge_response(response)
        _maestro_reply = _final_operator_reply(_without_raw_receipt_ref(
            reply_text_from_bridge_response(response, request_id=request_id_for_reply),
            _raw_receipt_ref_from_bridge_response(response),
            advertise=receipt_descriptor is not None,
        ), source_request=text)
        disposition = _operator_response_disposition(response)
        if (
            isinstance(disposition, Mapping)
            and disposition.get("delivery_mode") == "telegram_photo"
        ):
            delivered_message = await _deliver_telegram_artifact(
                bot=context.bot,
                chat_id=chat_id,
                caption=_maestro_reply,
                payload=response,
                source_request_id=request_id_for_reply,
                source_message_id=delivery_source_message_id,
            )
        else:
            delivered_message = await update.message.reply_text(_maestro_reply)
        speaker = _response_speaker(response)
        _register_maestro_delivered_text_after_delivery(
            delivered_text=_maestro_reply,
            source_request_id=request_id_for_reply,
            chat_id=chat_id,
            source_message_id=delivery_source_message_id,
            delivered_message=delivered_message,
            response_author=speaker,
        )
        _register_maestro_receipt_after_delivery(
            receipt_descriptor,
            chat_id=chat_id,
            source_message_id=delivery_source_message_id,
            delivered_message=delivered_message,
        )
        if speaker == "maestro":
            _fire_maestro_voice(
                _maestro_reply,
                chat_id,
                source_request_id=request_id_for_reply,
            )
        else:
            _fire_agent_voice(
                _maestro_reply,
                chat_id,
                speaker=speaker,
                source_request_id=request_id_for_reply,
            )
    except Exception as exc:
        print(f"[maestro_listener] bridge error: {exc.__class__.__name__}", flush=True)
        await update.message.reply_text(
            _final_operator_reply(
                reply_text_from_bridge_response(
                    None,
                    request_id=request_id_for_reply or message_id,
                ),
                source_request=text,
            )
        )
    finally:
        typing_task.cancel()
        try:
            await typing_task
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
    if not _is_authorized_operator_private_chat(update, auth_id):
        return
    if not claim_listener_update(update, role="maestro", source_channel="maestro_listener"):
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
            await update.message.reply_text(
                _final_operator_reply(
                    str(
                        request.get("operator_reply")
                        or "noted — I can't read it yet, I'll reprocess when vision's back."
                    ),
                    source_request=caption,
                )
            )
            return
        request_id_for_reply = str(request["request_id"])
        write_bridge_request(request)
        response = await poll_bridge_response(request_id_for_reply)
        _maestro_photo_reply = reply_text_from_bridge_response(response, request_id=request_id_for_reply)
        if _ocr_summary:
            _maestro_photo_reply = _ocr_summary + "\n\n" + _maestro_photo_reply
        _maestro_photo_reply = _final_operator_reply(
            _maestro_photo_reply,
            source_request=caption,
        )
        await update.message.reply_text(_maestro_photo_reply)
        _fire_maestro_voice(
            _maestro_photo_reply,
            chat_id,
            source_request_id=request_id_for_reply,
        )
    except Exception as exc:
        print(f"[maestro_listener] image bridge error: {exc.__class__.__name__}", flush=True)
        await update.message.reply_text(
            _final_operator_reply(
                reply_text_from_bridge_response(
                    None,
                    request_id=request_id_for_reply or message_id,
                ),
                source_request=caption,
            )
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
    install_identity_preflight(application, "maestro")
    return application


async def run_listener(application=None, stop_event: asyncio.Event | None = None) -> None:
    application = application or build_application()
    await run_verified_polling(application, "maestro", stop_event=stop_event)


def main() -> None:
    print("[maestro_listener] starting", flush=True)
    asyncio.run(run_listener())


if __name__ == "__main__":
    main()
