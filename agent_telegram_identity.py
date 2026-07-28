"""Which chat is actually this agent — answered by username, or refused.

On 2026-07-28 a test message intended for Cassandra was sent to a real human
contact named Carter, because the target was chosen by searching display names.
Display names are a fuzzy namespace shared with every person in the address book,
and "closest match" in that namespace is not identification, it is a guess that
happens to be right most of the time.

So this module resolves by ``@username`` — Telegram's one unique, unforgeable
handle — and refuses whenever the answer is not exactly one. Zero matches is a
refusal. Two matches is a refusal. A chat whose username disagrees with the
registry is a refusal even if its display name is perfect. There is deliberately
no best-match path: best-match is the defect.

It also carries the interlock. Until identity resolution actually proves out, no
approval preview carrying a nonce may be emitted over Telegram. A preview in the
wrong chat is worse than no preview, because it teaches the wrong human what a
valid approval looks like.

No secret is read here. Bot *tokens* live in the environment and are never touched;
this module deals only in public usernames, display names and chat ids.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = "agent_telegram_identity_v1"

#: Canonical registry. The `agent_lanes` table was specified in
#: tests/test_t016_synthetic_e2e.py but no production CREATE TABLE was found, so the
#: contract lived only in a fixture. This is that contract made real and importable.
#: A row here is the ONLY thing that authorises resolution to a chat.
#: CORRECTED 2026-07-28 from a live getMe audit of all six bots.
#:
#: The previous values (@openclaw_<agent>_bot) came from the pattern asserted in
#: tests/test_t016_synthetic_e2e.py and were fiction: **all six were wrong**. Not one
#: live bot uses that scheme. Had the interlock been opened on the strength of that
#: table, resolution would have refused every real chat — or worse, a future edit
#: "fixing" the mismatch could have pointed an agent at whatever did match.
#:
#: This is why declared is not proved, and why every lane stays UNVERIFIED until a
#: live check writes it down. The check has now run for username and bot id.
AGENT_IDENTITIES: dict[str, dict[str, str]] = {
    "maestro":   {"role": "First Officer — bridge and front door",
                  "username": "@winship_maestro_bot",      "bot_id": "8719135741"},
    "chief":     {"role": "Chief of Staff",
                  "username": "@sysrelay_bot",             "bot_id": "8780205422"},
    "cassandra": {"role": "Client Voice (Clara Reid)",
                  "username": "@cassandrastudio_bot",      "bot_id": "8775077131"},
    "niles":     {"role": "Audio / X32",
                  "username": "@nilesproducerbot",         "bot_id": "8652409115"},
    "guardian":  {"role": "Approvals and Gates",
                  "username": "@deeppocketguardianbot",    "bot_id": "8545796633"},
    "hermes":    {"role": "Messaging Gateway",
                  "username": "@HermesWinshipBot",         "bot_id": "8651405393"},
}

REFUSE_UNKNOWN_AGENT = "unknown_agent"
REFUSE_NO_MATCH = "no_chat_matched"
REFUSE_AMBIGUOUS = "multiple_chats_matched"
REFUSE_USERNAME_MISMATCH = "chat_username_does_not_match_registry"
REFUSE_HUMAN_CONTACT = "target_is_a_human_contact"
REFUSE_NO_USERNAME = "chat_has_no_username"

#: Set only once a real six-agent identity battery has passed. Absent env var ->
#: unproven -> no nonce previews. Fail closed: the default is the safe answer.
IDENTITY_PROOF_ENV = "OPENCLAW_TELEGRAM_IDENTITY_PROVEN"

#: The banner changes what the operator reads on every single message, which is a
#: deployment decision rather than a code one — three existing listener tests assert
#: the exact visible reply, and they are right to. So the banner is opt-in.
#:
#: The nonce interlock is NOT opt-in and never will be: withholding a nonce is
#: safety, and safety that can be switched off by forgetting an env var is
#: decoration. Cosmetics are flagged; guards are not.
IDENTITY_BANNER_ENV = "OPENCLAW_TELEGRAM_IDENTITY_BANNER"


class IdentityError(RuntimeError):
    """Programmer error. A refused resolution is a Resolution, not an exception."""


def normalize_agent(agent: str) -> str:
    return str(agent or "").strip().lower()


def normalize_username(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if not text.startswith("@"):
        text = "@" + text
    return text


@dataclass(frozen=True)
class Resolution:
    ok: bool
    reason: str
    agent: str = ""
    username: str = ""
    chat_id: str = ""
    detail: str = ""
    candidates_considered: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": self.ok,
            "reason": self.reason,
            "agent": self.agent,
            "username": self.username,
            "chat_id": self.chat_id,
            "detail": self.detail,
            "candidates_considered": self.candidates_considered,
        }


def registry_username(agent: str) -> str:
    row = AGENT_IDENTITIES.get(normalize_agent(agent))
    return row["username"] if row else ""


def identity_banner(agent: str) -> str:
    """``AGENT / ROLE / @username`` — shown before every agent turn.

    The operator must be able to see who is speaking without trusting a sidebar
    label. On 2026-07-28 the sidebar said ``Cassandra`` while the chat header said
    ``Casandra bot``; a banner rendered from the registry cannot drift that way,
    because it is the registry.
    """

    key = normalize_agent(agent)
    row = AGENT_IDENTITIES.get(key)
    if not row:
        raise IdentityError(f"no registry row for agent {agent!r}; refusing to render a banner")
    return f"{key.upper()} / {row['role']} / {row['username']}"


def _is_probably_human(chat: Mapping[str, Any]) -> bool:
    """A private chat with a real person is never an agent, whatever it is called."""

    if str(chat.get("type") or "").strip().lower() == "private" and not chat.get("is_bot", False):
        return True
    return bool(chat.get("is_human_contact"))


def resolve_agent_chat(
    agent: str,
    candidates: Sequence[Mapping[str, Any]],
    *,
    registry: Mapping[str, Mapping[str, str]] | None = None,
) -> Resolution:
    """Return the one chat that IS this agent, or a named refusal.

    ``candidates`` are chat records with at least ``username`` and ``chat_id``;
    ``display_name``, ``type`` and ``is_bot`` are used only to refuse faster, never
    to select.
    """

    table = registry or AGENT_IDENTITIES
    key = normalize_agent(agent)
    row = table.get(key)
    if not row:
        return Resolution(False, REFUSE_UNKNOWN_AGENT, agent=key,
                          detail="agent is not in the identity registry")

    want = normalize_username(row["username"])
    considered = len(candidates)

    matches = []
    for chat in candidates:
        got = normalize_username(chat.get("username", ""))
        if not got:
            continue
        if got == want:
            matches.append(chat)

    if not matches:
        # Say WHY there was no match, because "not found" and "found the wrong
        # thing" need different fixes and look identical in a bare refusal.
        named = [c for c in candidates if _is_probably_human(c)]
        if named and any(
            _display_resembles(c.get("display_name", ""), key) for c in named
        ):
            return Resolution(
                False, REFUSE_HUMAN_CONTACT, agent=key, username=want,
                detail=("a human contact resembles this agent's name; refusing rather "
                        "than sending to a person"),
                candidates_considered=considered,
            )
        unnamed = [c for c in candidates if not normalize_username(c.get("username", ""))]
        if unnamed and len(unnamed) == considered:
            return Resolution(False, REFUSE_NO_USERNAME, agent=key, username=want,
                              detail="no candidate exposes a username to match on",
                              candidates_considered=considered)
        return Resolution(False, REFUSE_NO_MATCH, agent=key, username=want,
                          detail=f"no chat with username {want}",
                          candidates_considered=considered)

    if len(matches) > 1:
        ids = ", ".join(str(c.get("chat_id")) for c in matches)
        return Resolution(False, REFUSE_AMBIGUOUS, agent=key, username=want,
                          detail=f"{len(matches)} chats claim {want}: {ids}",
                          candidates_considered=considered)

    chat = matches[0]
    if _is_probably_human(chat):
        return Resolution(False, REFUSE_HUMAN_CONTACT, agent=key, username=want,
                          detail="matched chat is a human contact",
                          candidates_considered=considered)

    chat_id = str(chat.get("chat_id") or "").strip()
    if not chat_id:
        return Resolution(False, REFUSE_NO_MATCH, agent=key, username=want,
                          detail="matched chat carries no chat_id",
                          candidates_considered=considered)

    return Resolution(True, "resolved", agent=key, username=want, chat_id=chat_id,
                      detail="", candidates_considered=considered)


def _display_resembles(display_name: str, agent_key: str) -> bool:
    """Loose, deliberately over-eager: used only to REFUSE, never to select.

    Being wrong here costs a refusal. Being wrong in the other direction cost a
    message to Carter.
    """

    text = re.sub(r"[^a-z]", "", str(display_name or "").lower())
    key = re.sub(r"[^a-z]", "", agent_key)
    if not text or not key:
        return False
    if text.startswith(key[:3]) or key.startswith(text[:3]):
        return True
    return key in text or text in key


def identity_proven(env: Mapping[str, str] | None = None) -> bool:
    """Exactly ``"1"``. No stripping, no truthiness, no case folding.

    Stripping felt like hygiene until a test set ``"1 "`` and the interlock opened.
    Anything other than the exact token is a configuration the author did not
    clearly intend, and the safe reading of an unclear intent about releasing a
    nonce into an untrusted channel is "no".
    """

    source = env if env is not None else os.environ
    return source.get(IDENTITY_PROOF_ENV, "") == "1"


def banner_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = env if env is not None else os.environ
    return source.get(IDENTITY_BANNER_ENV, "") == "1"


def nonce_preview_allowed(env: Mapping[str, str] | None = None) -> tuple[bool, str]:
    """The interlock. Returns ``(allowed, reason)``.

    Fail closed: an unset variable means unproven means no preview. This is the
    only thing standing between a nonce and a stranger's chat while SEAM 2 is open.
    """

    if not identity_proven(env):
        return False, (
            "Telegram agent identity is not proven; a nonce-bearing preview must not "
            "be emitted. Pass the six-agent identity battery and set "
            f"{IDENTITY_PROOF_ENV}=1 at the operator's keyboard."
        )
    return True, ""


__all__ = [
    "AGENT_IDENTITIES",
    "IDENTITY_PROOF_ENV",
    "IdentityError",
    "REFUSE_AMBIGUOUS",
    "REFUSE_HUMAN_CONTACT",
    "REFUSE_NO_MATCH",
    "REFUSE_NO_USERNAME",
    "REFUSE_UNKNOWN_AGENT",
    "REFUSE_USERNAME_MISMATCH",
    "Resolution",
    "identity_banner",
    "identity_proven",
    "nonce_preview_allowed",
    "normalize_username",
    "registry_username",
    "resolve_agent_chat",
]
