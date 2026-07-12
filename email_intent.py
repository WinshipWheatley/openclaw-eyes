"""Canonical, dependency-light email intent classification.

The enum is the only domain classification vocabulary used by email adapters.
Adapters may support different enum members, but they must not infer an email
intent from their own keyword tables.  Read and draft authority are exposed as
separate pure predicates because a ``reply`` request can mean either inspecting
received replies or preparing a reply draft.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from enum import Enum
from typing import Mapping


class EmailIntent(str, Enum):
    METADATA_READ = "metadata_read"
    UNREAD_LIST = "unread_list"
    DRAFT_SEND = "draft_send"
    REPLY = "reply"
    OUTREACH = "outreach"
    NONE = "none"


_DENIAL_RE = re.compile(
    r"\b(?:no|without)\s+(?:gmail|e-?mail|mailbox|inbox|tools?)\b|"
    r"\b(?:do\s+not|don['’]?t|never|no\s+need\s+to)\b[^\n]{0,45}"
    r"\b(?:gmail|e-?mails?|mailbox|inbox|messages?|threads?)\b",
    re.IGNORECASE,
)

_EMAIL_NOUN_RE = re.compile(
    r"\b(?:e-?mails?|gmail|mailbox|inbox|outbox|messages?|threads?|"
    r"attachments?|subjects?|senders?)\b",
    re.IGNORECASE,
)

_EXPLICIT_EMAIL_NOUN_RE = re.compile(
    r"\b(?:e-?mails?|gmail|mailbox|inbox|outbox)\b",
    re.IGNORECASE,
)

_NON_EMAIL_MESSAGE_RE = re.compile(
    r"(?:"
    r"\b(?:deployment|diagnostic|error|health|system|status|queue|log)\s+"
    r"messages?\b"
    r"|\bmessages?\s+(?:from|in|on|about)\s+(?:the\s+)?"
    r"(?:deployment|diagnostic|error|health|system|status|queue|log)\b"
    r"|\b(?:text|sms|telegram|slack|signal|whats?app)\s+messages?\b"
    r"|\bmessages?\b[^\n]{0,45}\b(?:via|on|through)\s+"
    r"(?:text|sms|telegram|slack|signal|whats?app)\b"
    r")",
    re.IGNORECASE,
)

_OUTREACH_RE = re.compile(
    r"\b(?:send|draft|prepare|create)\s+(?:the\s+)?(?:cassandra\s+)?"
    r"(?:pilot\s+)?(?:intro(?:duction)?|outreach)\s+(?:e-?mails?|messages?)\b",
    re.IGNORECASE,
)

_REPLY_LOOKUP_RE = re.compile(
    r"(?:"
    r"\b(?:check|show|list|find|search|read|review|any)\b[^\n]{0,60}"
    r"\b(?:repl(?:y|ies|ied)|responses?|acknowledg(?:e|ed|ement))\b"
    r"|\b(?:did|has|have|was|were|is|are)\b[^\n]{0,60}"
    r"\b(?:repl(?:y|ies|ied)|respond(?:ed|s)?|acknowledg(?:e|ed))\b"
    r")",
    re.IGNORECASE,
)

_REPLY_ACTION_RE = re.compile(
    r"^\s*(?:(?:can|could|would|will)\s+you\s+|please\s+)?"
    r"(?:reply|respond)\b",
    re.IGNORECASE,
)

_UNREAD_RE = re.compile(
    r"(?:"
    r"\b(?:show|list|count|check|find|any|what(?:'s|\s+is))\b[^\n]{0,45}"
    r"\bunread\b[^\n]{0,30}\b(?:e-?mails?|messages?|inbox)?\b"
    r"|\bany\s+new\s+(?:e-?mails?|messages?)\b"
    r"|\bany\s+e-?mails?\b"
    r"|\b(?:new|unread)\s+(?:e-?mails?|messages?|inbox\s+messages?)\b"
    r"|\bany\s+messages?\b"
    r")",
    re.IGNORECASE,
)

_PASSIVE_INBOUND_RE = re.compile(
    r"\b(?:did|have|has)\s+(?:we|i)\s+(?:get|got|receive(?:d)?)\s+"
    r"(?:sent\s+)?(?:anything|something|any(?:thing)?)\s+from\b",
    re.IGNORECASE,
)

_METADATA_QUERY_RE = re.compile(
    r"(?:"
    r"\b(?:check|show|list|find|search|read|review|open|look\s+in)\b[^\n]{0,70}"
    r"\b(?:e-?mails?|gmail|mailbox|inbox|outbox|messages?|threads?|"
    r"attachments?|subjects?|senders?)\b"
    r"|\b(?:did|do|have|has|are|is|was|were|who|what|when)\b[^\n]{0,70}"
    r"\b(?:e-?mails?|gmail|mailbox|inbox|outbox|messages?|threads?|"
    r"attachments?|subjects?|senders?)\b"
    r"|\b(?:e-?mail|message)\s+(?:history|log)\b"
    r"|\b(?:sent|received)\s+(?:e-?mails?|messages?)\b"
    r"|\b(?:e-?mails?|messages?)\s+from\s+\S+"
    r"|\b(?:inbox|outbox|gmail)\b\s*[?.!]*\s*$"
    r")",
    re.IGNORECASE,
)

_DRAFT_ACTION_RE = re.compile(
    r"(?:"
    r"^\s*(?:(?:can|could|would|will)\s+you\s+|please\s+)?"
    r"(?:draft|compose|write|prepare|create)\b[^\n]{0,55}"
    r"\b(?:e-?mail|message|note)\b"
    r"|^\s*(?:(?:can|could|would|will)\s+you\s+|please\s+)?"
    r"(?:send\s+(?:an?\s+)?(?:new\s+)?(?:e-?mail|gmail|message|msg|note)\b|"
    r"e-?mail\s+(?!(?:history|log|from|repl\w*|thread|subject|attachment|"
    r"inbox|outbox)\b)\S)"
    r"|^\s*(?:(?:can|could|would|will)\s+you\s+|please\s+)?"
    r"send\b[^\n]{1,45}\b(?:an?\s+)?(?:e-?mail|message|note)\b"
    r"|^\s*(?:(?:can|could|would|will)\s+you\s+|please\s+)?"
    r"send\s+[^\s]+@[^\s]+"
    r"|^\s*(?:(?:can|could|would|will)\s+you\s+|please\s+)?"
    r"forward\b[^\n]{0,55}\b(?:e-?mail|message)\b"
    r"|^\s*(?:invoice|follow[ -]?up)\s+e-?mail\b"
    r"|\btell\b[^\n]{1,50}\bby\s+e-?mail\b"
    r")",
    re.IGNORECASE,
)

_CONTEXTUAL_LOOKUP_RE = re.compile(
    r"\b(?:repl(?:y|ied)|respond(?:ed)?|acknowledg(?:e|ed)|"
    r"payment\s+update)\b",
    re.IGNORECASE,
)

_CONTEXTUAL_DRAFT_RE = re.compile(
    r"\b(?:draft|write|prepare)\b[^\n]{0,55}"
    r"\b(?:follow[ -]?up|what\s+(?:i|we)\s+should\s+ask|note)\b",
    re.IGNORECASE,
)

_OUTBOUND_HISTORY_RE = re.compile(
    r"\b(?:e-?mail\s+(?:history|log)|sent\s+e-?mails?|outbox)\b",
    re.IGNORECASE,
)

_SENDER_TOKEN = r"[A-Za-z0-9][A-Za-z0-9@._'+-]*"
_SENDER_SCOPE_RE = re.compile(
    r"\bfrom\s+(?P<sender>"
    + _SENDER_TOKEN
    + r"(?:\s+"
    + _SENDER_TOKEN
    + r"){0,3}?)(?="
    r"\s+(?:this|last|past)\s+(?:week|month|\d+\s+days?)\b"
    r"|\s+(?:today|yesterday)\b"
    r"|\s+(?:about|regarding|saying|with)\b"
    r"|[?!,.;]|$)",
    re.IGNORECASE,
)

_RECENCY_SCOPES = (
    (re.compile(r"\b(?:this|past)\s+week\b|\blast\s+7\s+days?\b", re.IGNORECASE), 7),
    (re.compile(r"\blast\s+week\b", re.IGNORECASE), 14),
    (re.compile(r"\btoday\b", re.IGNORECASE), 1),
    (re.compile(r"\byesterday\b", re.IGNORECASE), 2),
    (re.compile(r"\b(?:this|past)\s+month\b", re.IGNORECASE), 31),
)

_ST_ANNES_LANE_RE = re.compile(
    r"(?<![a-z0-9_])st[._ -]*anne(?:'?s)?(?![a-z0-9_])",
    re.IGNORECASE,
)
_GLENN_TOKEN_RE = re.compile(r"(?<![a-z0-9_])glenn(?![a-z0-9_])", re.IGNORECASE)
_ST_ANNES_EMAIL_TOPIC_RE = re.compile(r"\b(?:invoice|payment)\b", re.IGNORECASE)
_ST_ANNES_NON_EMAIL_CONTEXT_RE = re.compile(
    r"\b(?:meeting|phone|call|in[- ]person|face[- ]to[- ]face)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EmailMetadataScope:
    """Pure owner result for a bounded Gmail metadata read.

    ``gmail_query`` is suitable for the broker request. ``matches`` is a
    defensive post-filter: adapters must not assume a connector honored every
    requested constraint when it returns metadata.
    """

    sender: str | None = None
    newer_than_days: int | None = None

    @property
    def gmail_query(self) -> str:
        clauses: list[str] = []
        if self.sender:
            sender = self.sender.replace('"', "").strip()
            sender_atom = sender if " " not in sender else f'"{sender}"'
            clauses.append(f"from:{sender_atom}")
        if self.newer_than_days is not None:
            clauses.append(f"newer_than:{self.newer_than_days}d")
        return " ".join(clauses)

    def matches(
        self,
        metadata: Mapping[str, object],
        *,
        now: datetime | None = None,
    ) -> bool:
        """Return whether connector metadata remains inside this owner scope."""

        if self.sender:
            sender = self.sender.casefold().strip()
            sender_fields = " ".join(
                str(metadata.get(field) or "")
                for field in ("from_name", "from_email", "from")
            ).casefold()
            if not re.search(rf"(?<!\w){re.escape(sender)}(?!\w)", sender_fields):
                return False

        if self.newer_than_days is not None:
            date_raw = str(metadata.get("date_raw") or "").strip()
            parsed: datetime | None = None
            if date_raw:
                try:
                    parsed = parsedate_to_datetime(date_raw)
                except (TypeError, ValueError, OverflowError):
                    try:
                        parsed = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
                    except (TypeError, ValueError, OverflowError):
                        parsed = None
            # An absent/unparseable date is not grounds to discard a broker
            # result; the connector query is still authoritative for recency.
            if parsed is not None:
                reference = now or datetime.now().astimezone()
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=reference.tzinfo)
                elif reference.tzinfo is not None:
                    parsed = parsed.astimezone(reference.tzinfo)
                if parsed < reference - timedelta(days=self.newer_than_days):
                    return False

        return True


def _normalize(text: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(text or "").replace("’", "'").replace("‘", "'").strip(),
    )


def _has_st_annes_glenn_email_context(text: str, context: str) -> bool:
    if not (
        _ST_ANNES_LANE_RE.search(context)
        and _GLENN_TOKEN_RE.search(text)
    ):
        return False
    if _ST_ANNES_NON_EMAIL_CONTEXT_RE.search(text):
        return False
    return bool(
        _CONTEXTUAL_DRAFT_RE.search(text)
        or (
            _REPLY_LOOKUP_RE.search(text)
            and _ST_ANNES_EMAIL_TOPIC_RE.search(text)
        )
    )


def _has_email_context(text: str, context: str) -> bool:
    # A message-shaped utterance can itself be an email request (for example,
    # "draft a message to Dane"). Context is weaker evidence: a generic prior
    # message, deployment message, or SMS thread must not silently grant Gmail
    # authority to a follow-up such as "did they reply?".
    return bool(
        _EMAIL_NOUN_RE.search(text)
        or _EXPLICIT_EMAIL_NOUN_RE.search(context)
        # The St. Anne's workflow has one established email counterparty, but
        # lane + name alone cannot grant mailbox authority. Admit only the
        # bounded lookup/draft shapes used by that workflow and reject named
        # non-email contexts such as meetings or calls.
        or _has_st_annes_glenn_email_context(text, context)
    )


def classify_email_intent(text: str, *, context: str = "") -> EmailIntent:
    """Classify an operator utterance without I/O or adapter dependencies."""

    query = _normalize(text)
    lane_context = _normalize(context)
    if not query or _DENIAL_RE.search(query):
        return EmailIntent.NONE

    # Explicitly named non-email transports and machine/system messages own
    # their own lanes. A real email noun may coexist ("email me the deployment
    # message"), in which case the email request remains eligible below.
    if (
        _NON_EMAIL_MESSAGE_RE.search(query)
        and not _EXPLICIT_EMAIL_NOUN_RE.search(query)
    ):
        return EmailIntent.NONE

    if _OUTREACH_RE.search(query):
        return EmailIntent.OUTREACH

    has_email_context = _has_email_context(query, lane_context)
    reply_lookup = bool(_REPLY_LOOKUP_RE.search(query)) and has_email_context
    reply_action = bool(_REPLY_ACTION_RE.search(query)) and has_email_context
    if reply_lookup or reply_action:
        return EmailIntent.REPLY

    if _UNREAD_RE.search(query) and not _NON_EMAIL_MESSAGE_RE.search(query):
        return EmailIntent.UNREAD_LIST

    if _PASSIVE_INBOUND_RE.search(query):
        return EmailIntent.METADATA_READ

    if (
        has_email_context
        and _METADATA_QUERY_RE.search(query)
        and not _NON_EMAIL_MESSAGE_RE.search(query)
        and not _DRAFT_ACTION_RE.search(query)
    ):
        return EmailIntent.METADATA_READ

    if has_email_context and _CONTEXTUAL_LOOKUP_RE.search(query):
        return EmailIntent.METADATA_READ

    if _DRAFT_ACTION_RE.search(query):
        return EmailIntent.DRAFT_SEND

    if has_email_context and _CONTEXTUAL_DRAFT_RE.search(query):
        return EmailIntent.DRAFT_SEND

    return EmailIntent.NONE


def classify_email_metadata_scope(
    text: str,
    *,
    context: str = "",
) -> EmailMetadataScope | None:
    """Own the connector query and result scope for read-authorized email.

    Draft/send requests return ``None``. Adapters consume the resulting Gmail
    query and its defensive matcher instead of growing their own sender/time
    parsing tables.
    """

    query = _normalize(text)
    intent = classify_email_intent(query, context=context)
    is_read = intent in {EmailIntent.METADATA_READ, EmailIntent.UNREAD_LIST} or (
        intent is EmailIntent.REPLY and bool(_REPLY_LOOKUP_RE.search(query))
    )
    if not is_read:
        return None

    sender_match = _SENDER_SCOPE_RE.search(query)
    sender = sender_match.group("sender").strip() if sender_match else None
    newer_than_days = next(
        (days for pattern, days in _RECENCY_SCOPES if pattern.search(query)),
        None,
    )
    return EmailMetadataScope(sender=sender, newer_than_days=newer_than_days)


def email_intent_requires_read(text: str, *, context: str = "") -> bool:
    """Return whether the classified request needs mailbox read authority."""

    intent = classify_email_intent(text, context=context)
    if intent in {EmailIntent.METADATA_READ, EmailIntent.UNREAD_LIST}:
        return True
    return intent is EmailIntent.REPLY and bool(_REPLY_LOOKUP_RE.search(_normalize(text)))


def email_intent_requires_draft(text: str, *, context: str = "") -> bool:
    """Return whether the classified request needs draft-only authority."""

    intent = classify_email_intent(text, context=context)
    if intent in {EmailIntent.DRAFT_SEND, EmailIntent.OUTREACH}:
        return True
    return intent is EmailIntent.REPLY and bool(_REPLY_ACTION_RE.search(_normalize(text)))


def is_outbound_email_history_request(text: str) -> bool:
    """Narrow adapter subtype for Chief's local outbound-history read model."""

    return (
        classify_email_intent(text) is EmailIntent.METADATA_READ
        and bool(_OUTBOUND_HISTORY_RE.search(_normalize(text)))
    )
