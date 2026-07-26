"""Stop an internal excuse from reaching a client.

Standing order: *"the AI is hoinky, we're working it out" is an internal
sentence, never a client-facing one.* An instruction in a prompt is a wish. A
check at the send seam is the rule, so this is a check.

Two classes are caught:

**Excuse** — our own machinery offered to a client as the reason. Matching is
deliberately two-part: a sentence must name our *apparatus* (system, AI,
automation, software…) **and** carry an *excuse frame* (working it out, still,
glitch, acting up…) before it counts. That means "we're working on the final
mix" passes and "our system is still working it out" does not — a client can
be told about the work, just not about our plumbing.

A short list of phrases needs no partner: nothing rescues "bear with us" or
"technical difficulties".

**Leak** — internal vocabulary in outward copy. Cassandra is the officer;
*Clara Reid* is who the client knows. A client reading the word "packet",
"read-model" or an agent codename is being shown the inside of the machine.

This is a precision gate, not friction: it blocks a small, well-defined class
of sentence and always returns what to write instead, so a blocked draft is a
next step rather than a dead end.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, NamedTuple

# --- our own apparatus, named to a client -------------------------------
_APPARATUS = (
    "system", "systems", "ai", "a.i.", "automation", "automated", "software",
    "platform", "backend", "back-end", "server", "database", "integration",
    "bot", "script", "pipeline", "tooling", "workflow engine", "the tool",
    "our tech", "our setup", "our process",
)

# --- the frame that turns apparatus into an excuse ----------------------
_EXCUSE_FRAME = (
    "working it out", "working on it", "work it out", "still working",
    "still sorting", "sorting it out", "ironing out", "teething", "kinks",
    "glitch", "glitchy", "hiccup", "acting up", "playing up", "being weird",
    "on the fritz", "flaky", "hoinky", "wonky", "janky", "buggy", "a bug",
    "bugs", "broke", "broken", "went down", "is down", "outage", "misfired",
    "didn't fire", "didn t fire", "failed to", "error", "errored", "crashed",
    "not cooperating", "gave us trouble", "having trouble", "being difficult",
    "under construction", "in beta", "new system", "still learning",
)

# --- phrases that are an excuse on their own ----------------------------
_UNCONDITIONAL = (
    "bear with us", "bear with me", "thanks for your patience while we",
    "technical difficulties", "technical issues on our end",
    "on our end", "our end is", "hoinky", "gremlins",
    "please excuse any", "apologies for the confusion caused by",
    "we're working it out", "we are working it out",
)

# --- internal vocabulary that must not face a client --------------------
_LEAKS = (
    "cassandra", "maestro", "hermes", "guardian agent", "the chief agent",
    "openclaw", "read-model", "read model", "packet engine", "context packet",
    "send_hold", "send hold", "dry run", "dry-run", "test mode", "loopback",
    "llm", "prompt", "the model", "sqlite", "receipt id", "doer", "sub-agent",
    "subagent", "agent packet", "guardian gate",
)

REMEDY = (
    "Say what is true for the client — the current status and the date it "
    "lands — and nothing about our machinery. Send the underlying fault to "
    "Chief as a repair item instead."
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?;\n])\s+")


class Violation(NamedTuple):
    kind: str            # "excuse" | "leak"
    phrase: str          # the matched trigger
    apparatus: str       # the apparatus word, when kind == "excuse"
    sentence: str        # the offending sentence, trimmed


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_SPLIT.split(str(text or "")) if part.strip()]


def _contains(haystack: str, needles: Iterable[str]) -> str:
    """Return the first needle present as a whole phrase, else ``""``."""

    for needle in needles:
        pattern = r"(?<!\w)" + re.escape(needle) + r"(?!\w)"
        if re.search(pattern, haystack):
            return needle
    return ""


def scan_client_copy(text: str) -> tuple[Violation, ...]:
    """Return every excuse or leak in client-facing ``text``."""

    found: list[Violation] = []
    for sentence in _sentences(text):
        lowered = sentence.lower()

        unconditional = _contains(lowered, _UNCONDITIONAL)
        if unconditional:
            found.append(Violation("excuse", unconditional, "", sentence[:220]))
        else:
            apparatus = _contains(lowered, _APPARATUS)
            frame = _contains(lowered, _EXCUSE_FRAME)
            if apparatus and frame:
                found.append(Violation("excuse", frame, apparatus, sentence[:220]))

        leak = _contains(lowered, _LEAKS)
        if leak:
            found.append(Violation("leak", leak, "", sentence[:220]))
    return tuple(found)


def is_client_safe(text: str) -> bool:
    return not scan_client_copy(text)


def review_client_copy(
    *,
    subject: str = "",
    body: str = "",
    recipient: str = "",
) -> dict[str, Any]:
    """Return a blocking decision for one piece of outbound client copy."""

    violations = scan_client_copy(f"{subject}\n{body}")
    if not violations:
        return {
            "status": "CLIENT_COPY_CLEAR",
            "blocked": False,
            "recipient": recipient,
            "violations": [],
            "detail": "",
            "remedy": "",
        }
    worst = violations[0]
    detail = (
        f"Client copy blocked: {worst.kind} — "
        f"{'“' + worst.sentence + '”'} contains {worst.phrase!r}"
        + (f" about our {worst.apparatus!r}" if worst.apparatus else "")
        + ". Nothing was sent."
    )
    return {
        "status": "CLIENT_COPY_BLOCKED",
        "blocked": True,
        "recipient": recipient,
        "violations": [violation._asdict() for violation in violations],
        "detail": detail,
        "remedy": REMEDY,
    }


def review_outbound_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Review a normalized outbound email payload."""

    data = dict(payload or {})
    return review_client_copy(
        subject=str(data.get("subject") or ""),
        body=str(data.get("body") or ""),
        recipient=str(data.get("to") or ""),
    )


__all__ = [
    "REMEDY",
    "Violation",
    "is_client_safe",
    "review_client_copy",
    "review_outbound_payload",
    "scan_client_copy",
]
