"""Shared timeout and stale-output cleanup for long-running listener replies."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Iterable, Mapping, Sequence
from typing import Any
import re


STALE_CARRYOVER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bprevious response was truncated\b", re.IGNORECASE),
    re.compile(r"\bskill_view\s*:\s*factory_handoff_status\b", re.IGNORECASE),
    re.compile(r"\bstill working\b", re.IGNORECASE),
    re.compile(r"\bwaiting for stream response\b", re.IGNORECASE),
    re.compile(r"\bno chunks yet\b", re.IGNORECASE),
)


DEFAULT_ARTIFACT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bNon-canonical advisory output\b[:\s-]*", re.IGNORECASE),
    re.compile(r"\bInterrupting current task\s*(?:\([^)]*\))?", re.IGNORECASE),
    re.compile(r"\(?(?:iteration|loop)\s+\d+\s*/\s*\d+\)?", re.IGNORECASE),
)


DEFAULT_RESPONSE_TEXT_FIELDS: tuple[str, ...] = (
    "operator_message",
    "plain_summary",
    "summary",
    "eliwinship",
    "body",
    "one_line_answer",
)


def honest_short_fail(
    listener_name: str,
    *,
    reason: str = "the model path returned no usable fresh output",
    no_action_line: str = "No send, dispatch, workflow execution, ledger post, payment, or external action occurred.",
    next_step: str = "Retry after checking listener health and model contention.",
) -> str:
    name = str(listener_name or "The listener").strip() or "The listener"
    return "\n".join(
        [
            f"{name} could not produce a fresh answer before the local model stream limit.",
            f"The stale or partial output was discarded because {reason}.",
            no_action_line,
            next_step,
        ]
    )


def _as_patterns(patterns: Iterable[re.Pattern[str] | str] | None) -> tuple[re.Pattern[str], ...]:
    if not patterns:
        return ()
    compiled: list[re.Pattern[str]] = []
    for pattern in patterns:
        if isinstance(pattern, re.Pattern):
            compiled.append(pattern)
        else:
            compiled.append(re.compile(str(pattern), re.IGNORECASE))
    return tuple(compiled)


def _is_stale_carryover_line(text: str, patterns: Sequence[re.Pattern[str]]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def clean_stale_carryover(
    content: Any,
    *,
    failure_text: str | None = None,
    artifact_patterns: Iterable[re.Pattern[str] | str] | None = DEFAULT_ARTIFACT_PATTERNS,
    stale_patterns: Iterable[re.Pattern[str] | str] | None = STALE_CARRYOVER_PATTERNS,
) -> Any:
    """Remove progress/truncation artifacts from a user-visible reply.

    Non-string payloads pass through unchanged so callers can use this at broad
    reply boundaries without changing existing data contracts.
    """

    if not isinstance(content, str) or not content:
        return content
    stale = _as_patterns(stale_patterns)
    artifacts = _as_patterns(artifact_patterns)
    cleaned_lines: list[str] = []
    for raw_line in content.splitlines():
        if _is_stale_carryover_line(raw_line, stale):
            continue
        line = raw_line
        for pattern in artifacts:
            line = pattern.sub("", line)
        line = re.sub(r"[ \t]{2,}", " ", line).strip()
        line = re.sub(r"\s+([.,;:!?])", r"\1", line)
        if line:
            cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines).strip()
    if not cleaned and content.strip():
        return failure_text if failure_text is not None else honest_short_fail("The listener")
    return cleaned


async def bounded_reply_timeout(
    awaitable: Awaitable[Any],
    *,
    timeout_seconds: float,
    timeout_result: Any,
    clean_result: bool = True,
    failure_text: str | None = None,
    artifact_patterns: Iterable[re.Pattern[str] | str] | None = DEFAULT_ARTIFACT_PATTERNS,
) -> Any:
    try:
        result = await asyncio.wait_for(awaitable, timeout=max(0.001, float(timeout_seconds)))
    except (asyncio.TimeoutError, TimeoutError):
        return timeout_result
    if clean_result:
        return clean_stale_carryover(result, failure_text=failure_text, artifact_patterns=artifact_patterns)
    return result


def clean_response_payload_text(
    payload: Mapping[str, Any],
    *,
    failure_text: str,
    text_fields: Iterable[str] = DEFAULT_RESPONSE_TEXT_FIELDS,
    artifact_patterns: Iterable[re.Pattern[str] | str] | None = DEFAULT_ARTIFACT_PATTERNS,
) -> dict[str, Any]:
    cleaned = dict(payload)
    for field in text_fields:
        if field in cleaned:
            cleaned[field] = clean_stale_carryover(
                cleaned[field],
                failure_text=failure_text,
                artifact_patterns=artifact_patterns,
            )
    return cleaned
