"""Task 136a: recognize an operator STATEMENT of a recurring business rule (say it once, the
system remembers), refine it into a structured RecurrenceRuleRecord, persist it via
RecurrenceRuleStore (superseding any prior active rule for the same client+event_type), and
confirm plainly what was understood.

Scope (136a, approved -- Fable 2026-07-07): monthly-day-N schedules only ("on the 1st of
every month"), invoice_send event type, Maestro intake path. Broader schedule grammar
(weekly/quarterly/odd phrasings), any-agent intake, exceptions/undo/idempotency, and the
semantic (interpreter-LM) recognizer are 136b/c/d -- this module is the deterministic
fast-path those phases build on, never the ceiling.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from receivables_month_bounded import _CLIENT_DISPLAY_NAMES, _client_display, _client_ref
from recurrence_rule_record import create_recurrence_rule
from recurrence_rule_store import RecurrenceRuleStore

_ORDINAL_WORDS: dict[str, int] = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
    "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12,
    "thirteenth": 13, "fourteenth": 14, "fifteenth": 15, "sixteenth": 16,
    "seventeenth": 17, "eighteenth": 18, "nineteenth": 19, "twentieth": 20,
    "twenty-first": 21, "twenty-second": 22, "twenty-third": 23, "twenty-fourth": 24,
    "twenty-fifth": 25, "twenty-sixth": 26, "twenty-seventh": 27, "twenty-eighth": 28,
}
_ORDINAL_TEXT_BY_DAY = {day: word for word, day in _ORDINAL_WORDS.items()}

_RULE_STATEMENT_RE = re.compile(
    r"\b(?:i\s+)?(?:send|sends|issue|issues)\s+(?P<client>[a-z][a-z .'&-]*?)\s+"
    r"(?:a\s+|an\s+|the\s+)?(?:new\s+)?invoice[s]?\b.*?"
    r"(?:on\s+the\s+(?P<day1>[a-z0-9-]+)(?:\s+of\s+every\s+month)|"
    r"every\s+month\s+on\s+the\s+(?P<day2>[a-z0-9-]+))",
    re.IGNORECASE,
)
# Task 136b#1 (Fable probe): a CORRECTION phrasing -- "St Anne's invoices should go out on
# the 15th of every month" / "St Anne's invoices now go out on the 15th" -- names the client
# as the sentence subject rather than the object of "send". Must reach the rule store, not
# get swallowed by the legacy operator-truth-store intake.
_RULE_CORRECTION_RE = re.compile(
    r"\b(?P<client>[a-z][a-z .'&-]*?)\s+invoice[s]?\s+(?:should\s+|now\s+)*go(?:es)?\s+out\s+"
    r"on\s+the\s+(?P<day1>[a-z0-9-]+)(?:\s+of\s+every\s+month)?",
    re.IGNORECASE,
)
# "I send OUT a new invoice..." -- "out" isn't a client, it's part of the verb phrase. A
# statement with no explicit client named in the same sentence needs conversation-context
# resolution (136b+); here it correctly falls through to None rather than guessing.
_NON_CLIENT_FILLER_WORDS = frozenset({"out", "it", "them", "invoices", "an", "invoice"})
_CLIENT_TEXT_LEADING_FILLER_RE = re.compile(
    r"^(?:actually|wait|hey|so|ok|okay|now|and)\s+", re.IGNORECASE
)


def _clean_client_text(raw: str) -> str:
    cleaned = str(raw or "").strip()
    while True:
        stripped = _CLIENT_TEXT_LEADING_FILLER_RE.sub("", cleaned).strip()
        if stripped == cleaned:
            return cleaned
        cleaned = stripped


def _ordinal_to_day(word: str) -> int | None:
    normalized = str(word or "").strip().lower().rstrip(".")
    if normalized in _ORDINAL_WORDS:
        return _ORDINAL_WORDS[normalized]
    digits_match = re.match(r"^(\d{1,2})(?:st|nd|rd|th)?$", normalized)
    if digits_match:
        value = int(digits_match.group(1))
        if 1 <= value <= 28:
            return value
    return None


def _ordinal_text(day: int) -> str:
    word = _ORDINAL_TEXT_BY_DAY.get(day)
    return f"the {word}" if word else f"the {day}th"


def detect_recurrence_rule_statement(text: str) -> dict[str, object] | None:
    """Returns {client_text, schedule_day} if ``text`` matches a monthly-day-N recurrence
    statement OR correction shape ("I send St Anne's a new invoice on the first of every
    month" / "every month on the 15th" / "St Anne's invoices should go out on the 15th of
    every month"), else None. Never guesses -- an unmatched shape falls through to normal
    question/instruction handling untouched."""
    body = str(text or "")
    for pattern in (_RULE_STATEMENT_RE, _RULE_CORRECTION_RE):
        match = pattern.search(body)
        if not match:
            continue
        groups = match.groupdict()
        day_word = groups.get("day1") or groups.get("day2")
        if not day_word:
            continue
        day = _ordinal_to_day(day_word)
        if day is None:
            continue
        client_text = _clean_client_text(groups.get("client") or "")
        if not client_text or client_text.lower() in _NON_CLIENT_FILLER_WORDS:
            continue
        return {"client_text": client_text, "schedule_day": day}
    return None


def capture_recurrence_rule_statement(
    text: str,
    *,
    store: RecurrenceRuleStore,
    source_ref: str = "operator_maestro_chat",
    now_iso: str | None = None,
) -> dict[str, object] | None:
    """Full intake: detect -> resolve client -> refine -> persist (superseding any prior
    active rule for the same client+event_type) -> plain confirmation. Returns None if the
    text doesn't match a recurrence-statement shape at all (caller falls through to normal
    handling). Returns a dict with status "needs_operator_review" or "captured"."""
    detected = detect_recurrence_rule_statement(text)
    if detected is None:
        return None

    client_text = str(detected["client_text"])
    resolved_ref = _client_ref(client_text)
    if resolved_ref not in _CLIENT_DISPLAY_NAMES:
        return {
            "status": "needs_operator_review",
            "reply": f"I want to get this one right -- which client did you mean by '{client_text}'?",
        }

    schedule_day = int(detected["schedule_day"])
    client_display = _client_display(resolved_ref)
    stated_as_of = now_iso or datetime.now(timezone.utc).isoformat()

    prior = store.latest_unsuperseded_for_client(resolved_ref, "invoice_send")
    record = create_recurrence_rule(
        client_ref=resolved_ref,
        event_type="invoice_send",
        schedule_kind="monthly_day",
        schedule_day=schedule_day,
        stated_as_of=stated_as_of,
        provenance_raw=str(text),
        source_ref=source_ref,
        rule_id=prior.rule_id if prior else None,
        supersedes_rule_version_id=prior.rule_version_id if prior else None,
    )
    store.append(record)

    if prior is not None and prior.schedule_day != schedule_day:
        reply = (
            f"Got it — {client_display} now bills on {_ordinal_text(schedule_day)} monthly "
            f"(was: {_ordinal_text(prior.schedule_day)})."
        )
    else:
        reply = f"Got it — {client_display} invoices go out on {_ordinal_text(schedule_day)} monthly. I'll track it."

    return {"status": "captured", "reply": reply, "record": record}
