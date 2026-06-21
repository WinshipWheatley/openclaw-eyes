"""OpenClaw policy patch for the ignored Hermes gateway runtime.

The live Hermes gateway package is intentionally kept outside this repository
tree, so OpenClaw-owned safety behavior has to be injected from tracked code.
This module is deterministic and text-only: it does not dispatch agents, send
external messages, move money, start services, or write route receipts.
"""

from __future__ import annotations

import re
from typing import Any


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


def _normalize(text: str) -> str:
    return " ".join(str(text or "").lower().strip().replace("’", "'").split())


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

    if not isinstance(content, str) or not content:
        return content
    cleaned_lines: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line
        for pattern in _LEAK_PATTERNS:
            line = pattern.sub("", line)
        line = re.sub(r"[ \t]{2,}", " ", line).strip()
        line = re.sub(r"\s+([.,;:!?])", r"\1", line)
        if line:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


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


def install_gateway_policy_patch(*, gateway_run_module: Any | None = None, base_adapter_cls: type | None = None) -> bool:
    """Patch Hermes GatewayRunner after the ignored runtime is importable."""

    if gateway_run_module is None:
        import gateway.run as gateway_run_module  # type: ignore[import-not-found]

    runner_cls = getattr(gateway_run_module, "GatewayRunner")
    if not getattr(runner_cls, "_openclaw_truthful_gateway_patch", False):
        original_handle_message = runner_cls._handle_message

        async def _openclaw_handle_message(self: Any, event: Any) -> Any:
            if _event_is_authorized_for_intercept(self, event):
                command = event.get_command() if callable(getattr(event, "get_command", None)) else None
                if not command:
                    reply = truthful_reply_for_text(getattr(event, "text", "") or "")
                    if reply is not None:
                        return reply
            result = await original_handle_message(self, event)
            return sanitize_gateway_response(result)

        runner_cls._handle_message = _openclaw_handle_message
        runner_cls._openclaw_truthful_gateway_patch = True

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
    "truthful_reply_for_text",
]
