"""OpenClaw policy patch for the ignored Hermes gateway runtime.

The live Hermes gateway package is intentionally kept outside this repository
tree, so OpenClaw-owned safety behavior has to be injected from tracked code.
This module is deterministic and text-only: it does not dispatch agents, send
external messages, move money, start services, or write route receipts.
"""

from __future__ import annotations

import contextvars
import os
import re
from typing import Any

from listener_resilience import bounded_reply_timeout, clean_stale_carryover


_ROUTE_TARGET_RE = re.compile(
    r"\b(?:route|send|handoff|hand off|pass|forward|dispatch)\b.{0,80}\bto\s+([a-z][a-z0-9_-]{1,40})\b",
    re.IGNORECASE,
)
_FALLBACK_AGENT_TARGETS = frozenset(
    {
        "cassandra",
        "chief",
        "guardian",
        "hermes",
        "niles",
        "operator_briefing",
        "operations_router",
        "producer",
        "report_bridge",
    }
)
_ROUTE_INVENTORY_PHRASES = (
    "what can you route to",
    "who can you route to",
    "what agents can you route to",
    "which agents can you route",
    "route inventory",
    "routing inventory",
    "real agent bridges",
    "agent bridges",
)
_CAPABILITY_PHRASES = (
    "what's your job",
    "whats your job",
    "what is your job",
    "what do you do",
    "what can you do",
    "what are you",
    "what is hermes",
    "who are you",
)
_SEND_OR_MONEY_RE = re.compile(
    r"\b(send|email|message|text|telegram|notify|reply|forward|post|deliver|pay|payment|money|wire|ach|transfer|refund|charge)\b",
    re.IGNORECASE,
)
_LEAK_PATTERNS = (
    re.compile(r"\bNon-canonical advisory output\b[:\s-]*", re.IGNORECASE),
    re.compile(r"\bInterrupting current task\s*(?:\([^)]*\))?", re.IGNORECASE),
    re.compile(r"\(?(?:iteration|loop)\s+\d+\s*/\s*\d+\)?", re.IGNORECASE),
)
_DEFAULT_GATEWAY_REPLY_TIMEOUT_SECONDS = 45.0
_STALL_FAILURE_REPLY = "\n".join(
    [
        "Hermes could not produce a fresh answer before the local model stream limit.",
        "The upstream local model returned no usable chunks, so stale partial output was discarded.",
        "No requested send, agent dispatch, route receipt, or money action occurred.",
        "Ask Fable or the operator to check Hermes gateway health and Ollama contention before retrying.",
    ]
)
_RAW_PRECLAIMED_UPDATE_ID: contextvars.ContextVar[object | None] = contextvars.ContextVar(
    "openclaw_hermes_raw_preclaimed_update_id",
    default=None,
)


def _normalize(text: str) -> str:
    return " ".join(str(text or "").lower().strip().replace("’", "'").split())


def _gateway_reply_timeout_seconds() -> float:
    raw = os.environ.get("HERMES_OPENCLAW_GATEWAY_REPLY_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return _DEFAULT_GATEWAY_REPLY_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return _DEFAULT_GATEWAY_REPLY_TIMEOUT_SECONDS
    return value if value > 0 else _DEFAULT_GATEWAY_REPLY_TIMEOUT_SECONDS


def stalled_stream_failure_reply() -> str:
    return _STALL_FAILURE_REPLY


def _agent_route_targets() -> frozenset[str]:
    try:
        from agent_lane_registry import DEFAULT_AGENT_LANE_SEEDS

        targets: set[str] = set()
        for seed in DEFAULT_AGENT_LANE_SEEDS:
            targets.add(str(seed.agent_id).strip().lower())
            targets.add(str(seed.display_name).strip().lower().replace(" ", "_"))
            targets.update(str(alias).strip().lower() for alias in seed.aliases)
        return frozenset(target for target in targets if target)
    except Exception:
        return _FALLBACK_AGENT_TARGETS


def _route_target_candidate(text: str) -> str:
    match = _ROUTE_TARGET_RE.search(text)
    return match.group(1).lower() if match else ""


def _route_target(text: str) -> str:
    target = _route_target_candidate(text)
    return target if target in _agent_route_targets() else ""


def _is_route_request(text: str) -> bool:
    return bool(_ROUTE_TARGET_RE.search(text))


def _is_route_inventory(text: str) -> bool:
    normalized = _normalize(text)
    return any(phrase in normalized for phrase in _ROUTE_INVENTORY_PHRASES)


def _is_capability_prompt(text: str) -> bool:
    normalized = _normalize(text)
    return ("hermes" in normalized and any(phrase in normalized for phrase in _CAPABILITY_PHRASES)) or any(
        phrase == normalized for phrase in ("what can you do", "who are you", "what are you")
    )


def _is_send_or_money_action(text: str) -> bool:
    return bool(_SEND_OR_MONEY_RE.search(text))


def truthful_reply_for_text(text: str) -> str | None:
    """Return a deterministic Hermes gateway reply, or ``None`` to fall through."""

    raw = str(text or "").strip()
    if not raw:
        return None

    # ── Refusal-first guard (task 141) — FIRST tap, before route/send/money
    # checks or any gateway model fallthrough. Adds the destructive-scope and
    # gate-bypass classes Hermes' own send/money matcher misses ("wipe the
    # X32", "approve everything"); the money class keeps Hermes' verbatim
    # reference denial. Fail-open: guard errors fall through unchanged.
    try:
        from operator_refusal_guard import refusal_reply_for_text as _refusal_reply_for_text

        _refusal = _refusal_reply_for_text(raw, agent="hermes", surface="hermes_gateway")
    except Exception:
        _refusal = None
    if _refusal is not None:
        return _refusal

    # Task 151: deterministic Hermes status (and other safe direct contracts)
    # before the sidecar worker.  Real send/pay actions were already refused
    # above; authority tokens and delegated domains pass through unchanged.
    try:
        from agent_contract_renderers import render_hermes_status
        from typed_contract_decision import (
            ContractContext,
            decide_contract,
            semantic_vote_enabled_for_adapter,
        )

        _typed = decide_contract(
            raw,
            context=ContractContext(agent="hermes", surface="hermes_gateway_policy"),
            status_renderer=render_hermes_status,
            semantic_vote_enabled=semantic_vote_enabled_for_adapter("hermes_status"),
        )
    except Exception:
        _typed = None
    if _typed is not None and _typed.handled:
        return str(_typed.reply or "")

    target = _route_target(raw)
    if target:
        return "\n".join(
            [
                f"Hermes cannot route this to {target} from this surface.",
                "No agent handoff ran, no route receipt was written, and no message was sent.",
                "Hermes can describe adapter and protocol boundaries or recommend a review packet.",
                "A real handoff needs a sanctioned bridge with a receipt.",
                "SEND_HOLD remains in force.",
            ]
        )

    if _is_send_or_money_action(raw):
        return "\n".join(
            [
                "Hermes cannot send messages, trigger payments, or move money from this surface.",
                "This request is denied for live action and can only be staged for an operator-controlled review path.",
                "No external send, payment, ledger mutation, route receipt, service start, or agent dispatch occurred.",
                "SEND_HOLD remains in force.",
            ]
        )

    if _is_route_request(raw):
        requested = _route_target_candidate(raw) or "that destination"
        return "\n".join(
            [
                f"Hermes cannot route this to {requested} from this surface.",
                "That route target is not a canonical OpenClaw agent route.",
                "No agent handoff ran, no route receipt was written, and no message was sent.",
                "SEND_HOLD remains in force.",
            ]
        )

    if _is_route_inventory(raw):
        return "\n".join(
            [
                "Hermes has no proven live agent-routing bridge from this surface.",
                "Real agent bridges available to Hermes here: none proven.",
                "Read-model sidecars may support advisory review, but they are not dispatch routes.",
                "Hermes cannot send, enqueue, start services, or bypass SEND_HOLD.",
                "SEND_HOLD remains in force.",
            ]
        )

    if _is_capability_prompt(raw):
        return "\n".join(
            [
                "Hermes is an advisory boundary reviewer, not a live routing or send gateway.",
                "Current scope: adapter and protocol boundary review, bridge posture, sidecar inventory, and authority-fit checks.",
                "Hard no: no external send, Gmail/Coupa/browser access, payment, ledger/workbook/PDF mutation, service start, model-provider fallback, or agent dispatch from this surface.",
                "Chief or operator-controlled promotion is required for any action.",
                "SEND_HOLD remains in force.",
            ]
        )

    return None


def sanitize_gateway_response(content: Any) -> Any:
    """Remove internal gateway/runtime wording from user-facing text."""

    return clean_stale_carryover(
        content,
        failure_text=stalled_stream_failure_reply(),
        artifact_patterns=_LEAK_PATTERNS,
    )


def _event_is_authorized_for_intercept(runner: Any, event: Any) -> bool:
    if getattr(event, "internal", False):
        return False
    source = getattr(event, "source", None)
    if source is None or getattr(source, "user_id", None) is None:
        return False
    is_authorized = getattr(runner, "_is_user_authorized", None)
    if callable(is_authorized):
        try:
            return bool(is_authorized(source))
        except Exception:
            return False
    return False


def _event_is_telegram(event: Any) -> bool:
    platform = getattr(getattr(event, "source", None), "platform", None)
    return str(getattr(platform, "value", platform) or "").strip().lower() == "telegram"


def _claim_hermes_telegram_event(event: Any) -> bool:
    """Defense-in-depth for synthetic events or an unpatched adapter path."""

    from telegram_agent_intake import claim_listener_update

    return claim_listener_update(
        event,
        role="hermes",
        source_channel="hermes_gateway",
        telegram_update_id=getattr(event, "platform_update_id", None),
    )


def _claim_hermes_raw_update(event: Any, update_id: object | None) -> bool:
    """Durably claim one authorized raw PTB update before batching/cache work."""

    from telegram_agent_intake import claim_listener_update

    return claim_listener_update(
        event,
        role="hermes",
        source_channel="hermes_gateway",
        telegram_update_id=update_id,
    )


def _raw_message_type(message: Any, handler_name: str, message_type_cls: Any) -> Any:
    if handler_name == "_handle_text_message":
        return message_type_cls.TEXT
    if handler_name == "_handle_command":
        return message_type_cls.COMMAND
    if handler_name == "_handle_location_message":
        return message_type_cls.LOCATION
    for attribute, type_name in (
        ("sticker", "STICKER"),
        ("photo", "PHOTO"),
        ("video", "VIDEO"),
        ("audio", "AUDIO"),
        ("voice", "VOICE"),
        ("document", "DOCUMENT"),
    ):
        if getattr(message, attribute, None):
            return getattr(message_type_cls, type_name)
    return message_type_cls.DOCUMENT


def _raw_update_passes_cheap_checks(adapter: Any, update: Any, handler_name: str) -> bool:
    message = getattr(update, "message", None)
    if message is None:
        return False
    if handler_name in {"_handle_text_message", "_handle_command"} and not getattr(message, "text", None):
        return False
    if handler_name == "_handle_location_message":
        venue = getattr(message, "venue", None)
        location = getattr(venue, "location", None) if venue else getattr(message, "location", None)
        if location is None:
            return False
        if getattr(location, "latitude", None) is None or getattr(location, "longitude", None) is None:
            return False
    try:
        return bool(
            adapter._should_process_message(
                message,
                is_command=handler_name == "_handle_command",
            )
        )
    except TypeError:
        # Older/fake adapters may not accept the keyword for non-command paths.
        return bool(adapter._should_process_message(message))
    except Exception as exc:
        print(
            f"[hermes_listener] raw update trigger check failed ({exc.__class__.__name__}); refusing update.",
            flush=True,
        )
        return False


def _raw_event_is_authorized(adapter: Any, event: Any) -> bool:
    handler = getattr(adapter, "_message_handler", None)
    runner = getattr(handler, "__self__", None)
    checker = getattr(runner, "_is_user_authorized", None)
    if not callable(checker):
        print(
            "[hermes_listener] raw update authorization binding unavailable; refusing update before batching/cache.",
            flush=True,
        )
        return False
    try:
        return bool(checker(event.source))
    except Exception as exc:
        print(
            f"[hermes_listener] raw update authorization failed ({exc.__class__.__name__}); refusing update.",
            flush=True,
        )
        return False


def _install_hermes_raw_update_claim_patch(telegram_adapter_cls: Any, message_type_cls: Any) -> None:
    """Patch raw PTB handlers so every update id is claimed before work."""

    if getattr(telegram_adapter_cls, "_openclaw_raw_update_claim_patch", False):
        return

    original_build_event = telegram_adapter_cls._build_message_event

    def _openclaw_build_message_event(self: Any, *args: Any, **kwargs: Any) -> Any:
        event = original_build_event(self, *args, **kwargs)
        raw_update_id = _RAW_PRECLAIMED_UPDATE_ID.get()
        event_update_id = kwargs.get("update_id")
        if event_update_id is None and len(args) >= 3:
            event_update_id = args[2]
        if raw_update_id is not None and str(event_update_id) == str(raw_update_id):
            event._openclaw_raw_update_preclaimed = True
        return event

    telegram_adapter_cls._build_message_event = _openclaw_build_message_event

    for handler_name in (
        "_handle_text_message",
        "_handle_command",
        "_handle_location_message",
        "_handle_media_message",
    ):
        original_handler = getattr(telegram_adapter_cls, handler_name)

        async def _openclaw_raw_handler(
            self: Any,
            update: Any,
            context: Any,
            *,
            _handler_name: str = handler_name,
            _original_handler: Any = original_handler,
        ) -> Any:
            if not _raw_update_passes_cheap_checks(self, update, _handler_name):
                return None
            update_id = getattr(update, "update_id", None)
            message = update.message
            msg_type = _raw_message_type(message, _handler_name, message_type_cls)
            try:
                claim_event = original_build_event(self, message, msg_type, update_id=update_id)
            except Exception as exc:
                print(
                    f"[hermes_listener] raw update source build failed ({exc.__class__.__name__}); refusing update.",
                    flush=True,
                )
                return None
            if not _raw_event_is_authorized(self, claim_event):
                return None
            if not _claim_hermes_raw_update(claim_event, update_id):
                return None

            context_token = _RAW_PRECLAIMED_UPDATE_ID.set(update_id)
            try:
                return await _original_handler(self, update, context)
            finally:
                _RAW_PRECLAIMED_UPDATE_ID.reset(context_token)

        setattr(telegram_adapter_cls, handler_name, _openclaw_raw_handler)

    telegram_adapter_cls._openclaw_raw_update_claim_patch = True


def _install_hermes_voice_patch(runner_cls: Any) -> None:
    """Give the conversational Hermes the fleet Kokoro voice (am_echo), on by default.

    Two patches on GatewayRunner:
      * ``_should_send_voice_reply`` — default a chat that has never set a voice mode to
        "all", so Hermes speaks by default. An explicit ``/voice off`` persists as a real
        key and still wins (operator override is preserved).
      * ``_send_voice_reply`` — synthesize via the warm localhost Kokoro service and send
        through the gateway's OWN Telegram adapter (one voice note per reply, same engine
        and voice as the other five agents). Any failure — service down, synth error —
        falls back to the original edge-tts path, so a voice outage never silences Hermes.
    """

    if getattr(runner_cls, "_openclaw_hermes_voice_patch", False):
        return

    original_should = getattr(runner_cls, "_should_send_voice_reply", None)
    if callable(original_should):

        def _openclaw_should_send_voice_reply(self: Any, event: Any, response: Any,
                                              agent_messages: Any, already_sent: bool = False) -> Any:
            try:
                modes = getattr(self, "_voice_mode", None)
                if isinstance(modes, dict):
                    key = self._voice_key(event.source.platform, event.source.chat_id)
                    if key not in modes:
                        modes[key] = "all"  # default-on; explicit /voice off persists and wins
            except Exception:
                pass
            return original_should(self, event, response, agent_messages, already_sent=already_sent)

        runner_cls._should_send_voice_reply = _openclaw_should_send_voice_reply

    original_send_voice = getattr(runner_cls, "_send_voice_reply", None)
    if callable(original_send_voice):

        async def _openclaw_send_voice_reply(self: Any, event: Any, text: str) -> Any:
            import asyncio
            import os

            try:
                platform = getattr(getattr(event, "source", None), "platform", None)
                if getattr(platform, "value", "") == "telegram":
                    adapter = self.adapters.get(platform) if hasattr(self, "adapters") else None
                    if adapter is not None and hasattr(adapter, "send_voice"):
                        import kokoro_voice_client

                        path = await asyncio.to_thread(kokoro_voice_client.synthesize_remote, text)
                        if path and os.path.isfile(path):
                            try:
                                await adapter.send_voice(chat_id=event.source.chat_id, audio_path=path)
                            finally:
                                try:
                                    os.unlink(path)
                                except Exception:
                                    pass
                            return None
            except Exception:
                pass
            return await original_send_voice(self, event, text)

        runner_cls._send_voice_reply = _openclaw_send_voice_reply

    runner_cls._openclaw_hermes_voice_patch = True


def install_gateway_policy_patch(
    *,
    gateway_run_module: Any | None = None,
    base_adapter_cls: type | None = None,
    telegram_adapter_cls: type | None = None,
    message_type_cls: Any | None = None,
) -> bool:
    """Patch Hermes GatewayRunner after the ignored runtime is importable."""

    if gateway_run_module is None:
        import gateway.run as gateway_run_module  # type: ignore[import-not-found]

    runner_cls = getattr(gateway_run_module, "GatewayRunner")
    if not getattr(runner_cls, "_openclaw_truthful_gateway_patch", False):
        original_handle_message = runner_cls._handle_message

        async def _openclaw_handle_message(self: Any, event: Any) -> Any:
            authorized = _event_is_authorized_for_intercept(self, event)
            raw_preclaimed = bool(getattr(event, "_openclaw_raw_update_preclaimed", False))
            if authorized and _event_is_telegram(event) and not raw_preclaimed and not _claim_hermes_telegram_event(event):
                return None
            if authorized:
                command = event.get_command() if callable(getattr(event, "get_command", None)) else None
                if not command:
                    reply = truthful_reply_for_text(getattr(event, "text", "") or "")
                    if reply is not None:
                        return reply
            result = await bounded_reply_timeout(
                original_handle_message(self, event),
                timeout_seconds=_gateway_reply_timeout_seconds(),
                timeout_result=stalled_stream_failure_reply(),
                failure_text=stalled_stream_failure_reply(),
                artifact_patterns=_LEAK_PATTERNS,
            )
            return sanitize_gateway_response(result)

        runner_cls._handle_message = _openclaw_handle_message
        runner_cls._openclaw_truthful_gateway_patch = True

    _install_hermes_voice_patch(runner_cls)

    if telegram_adapter_cls is None or message_type_cls is None:
        try:
            from gateway.platforms.telegram import TelegramAdapter as discovered_telegram_adapter  # type: ignore[import-not-found]
            from gateway.platforms.base import MessageType as discovered_message_type  # type: ignore[import-not-found]

            telegram_adapter_cls = telegram_adapter_cls or discovered_telegram_adapter
            message_type_cls = message_type_cls or discovered_message_type
        except Exception:
            telegram_adapter_cls = None
            message_type_cls = None
    if telegram_adapter_cls is not None and message_type_cls is not None:
        _install_hermes_raw_update_claim_patch(telegram_adapter_cls, message_type_cls)

    if base_adapter_cls is None:
        try:
            from gateway.platforms.base import BasePlatformAdapter as base_adapter_cls  # type: ignore[import-not-found]
        except Exception:
            base_adapter_cls = None

    if base_adapter_cls is not None and not getattr(base_adapter_cls, "_openclaw_truthful_send_patch", False):
        original_send_with_retry = base_adapter_cls._send_with_retry

        async def _openclaw_send_with_retry(self: Any, *args: Any, **kwargs: Any) -> Any:
            if "content" in kwargs:
                kwargs["content"] = sanitize_gateway_response(kwargs["content"])
            elif len(args) >= 2:
                args = (args[0], sanitize_gateway_response(args[1]), *args[2:])
            return await original_send_with_retry(self, *args, **kwargs)

        base_adapter_cls._send_with_retry = _openclaw_send_with_retry
        base_adapter_cls._openclaw_truthful_send_patch = True

    return True


__all__ = [
    "install_gateway_policy_patch",
    "sanitize_gateway_response",
    "stalled_stream_failure_reply",
    "truthful_reply_for_text",
]
