"""
Business Ops Intent v0.

Deterministic intent classification for the Business Ops Spine.
Unifies keyword-based intent detection across Gmail, Calendar, Payments, and Files.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from email_intent import (
    EmailIntent,
    classify_email_intent,
    email_intent_requires_read,
)
from money_truth import classify_money_question


@dataclass(frozen=True)
class IntentFrame:
    intent_name: str
    request_category: str
    domain: str
    confidence: float
    trigger: Optional[str] = None


def classify_business_ops_intent(query: str) -> IntentFrame:
    """
    Deterministic intent classification based on keywords and phrases.
    """
    q = (query or "").lower().strip()
    # Normalize curly apostrophes and strip common sentence-ending/prefix-separating punctuation
    q = q.replace("’", "'").replace("‘", "'")
    q = q.strip("?.!,").strip()

    # 1. User denial phrases (Highest priority)
    if any(phrase in q for phrase in ("no gmail", "no email", "no tools", "without gmail", "without email")):
        return IntentFrame("deny", "stop", "none", 1.0)

    # 2. Background / Automated (Internal use)
    if q == "monitored_email_conversation":
        return IntentFrame("monitored_email_conversation", "automated", "email", 1.0)

    # 3. Specific payment reads.  This shared classifier must run before
    # status and email: ordinary grammar ("check from Capital Hilton") is not
    # an email-search instruction merely because it contains the word "from".
    money_class = classify_money_question(q)
    if money_class == "payment_arrival_verify":
        return IntentFrame("payment_verify", "read_only", "payment", 1.0, money_class)

    # 4. Status / Orientation (High priority for explicit orientation)
    # Explicit OpenClaw orientation/status questions (High confidence)
    explicit_status_phrases = (
        "where are we", "openclaw status", "system status", "orientation",
        "lay of the land", "where do things stand", "what's the move",
        "catch me up", "orient me"
    )
    if any(phrase in q for phrase in explicit_status_phrases):
        # Prevent false positives with specific context blockers
        if not any(blocker in q for blocker in ("weather", "invoice", "email", "dinner", "lunch")):
            # Overriding 'thread' or 'subject' if 'catch me up' or 'orientation' is present
            return IntentFrame("ops_status", "read_only", "logging", 1.0, "explicit_status")

    # 5. Email / Gmail.  The owner enum keeps mailbox reads separate from
    # draft-producing requests; this adapter only translates that decision
    # into the Business Ops vocabulary.
    email_class = classify_email_intent(q)
    if email_class in {EmailIntent.METADATA_READ, EmailIntent.UNREAD_LIST} or (
        email_class is EmailIntent.REPLY and email_intent_requires_read(q)
    ):
        return IntentFrame(
            "email_search", "read_only", "email", 1.0, email_class.value
        )
    if email_class in {
        EmailIntent.DRAFT_SEND,
        EmailIntent.REPLY,
        EmailIntent.OUTREACH,
    }:
        return IntentFrame(
            "email_draft", "draft_only", "email", 1.0, email_class.value
        )

    # A user who explicitly asks to find an email keeps the email lane even if
    # the quoted subject is money-shaped.  Bare money reads use the shared
    # ledger classifier after that explicit instruction has had its turn.
    if money_class == "money_read":
        return IntentFrame("money_read", "read_only", "payment", 1.0, money_class)

    # 6. Calendar
    calendar_terms = (
        "calendar", "schedule", "appointment", "meeting", "event",
        "tomorrow morning", "tomorrow afternoon", "this week", "next week",
        "what's on", "what do i have", "what's tomorrow", "what's today"
    )
    for term in calendar_terms:
        if term in q:
            return IntentFrame("calendar_read", "read_only", "calendar", 0.9, term)

    # 7. File / Path. Payment verification has no keyword fallback here: the
    # shared money owner above is the only API allowed to select that domain.
    file_terms = (
        "file", "path", "exist", "directory", "folder", "/mnt", "/home",
        ".py", ".md", ".json", ".sh", ".txt", ".csv"
    )
    for term in file_terms:
        if term in q:
            return IntentFrame("file_verify", "read_only", "file", 0.8, term)

    # 9. Contacts
    contact_terms = (
        "number for", "phone number", "phone for", "contact for",
        "do i have a number", "do i have contact", "what's the number",
        "how do i reach", "how do i contact", "their number", "his number",
        "her number", "have their contact"
    )
    for term in contact_terms:
        if term in q:
            return IntentFrame("contacts_read", "read_only", "contacts", 0.9, term)

    # 10. Fuzzy/Natural Operator Phrases (Lower priority than specific domains)
    fuzzy_status_phrases = (
        "what's up", "where are we at", "how are things looking",
        "what should i know", "what's going on", "remind me what's current",
        "what did we just finish", "what did we finish", "coming back in cold",
        "been gone a while"
    )
    # Trigger if it's a short, direct orientation question or starts with a known phrase
    for phrase in fuzzy_status_phrases:
        if q == phrase or q.startswith(phrase):
            if not any(blocker in q for blocker in ("weather", "invoice", "email", "dinner", "lunch")):
                # If it's short or clearly contains OpenClaw/system/orient/status keywords, we trigger
                if len(q.split()) <= 12 or any(k in q for k in ("openclaw", "system", "orient", "status")):
                    return IntentFrame("ops_status", "read_only", "logging", 0.9, "fuzzy_status")

    # Bounded fallback for status/next/summary (Lower confidence)
    status_terms = ("status", "what's next", "summary", "what next", "what should i do next")
    for term in status_terms:
        if term in q:
            # Again, check for payment/email keywords that should override this
            if not any(p in q for p in ("invoice", "payment", "email", "gmail", "receipt")):
                return IntentFrame("ops_status", "read_only", "logging", 0.7, term)

    return IntentFrame("none", "none", "none", 0.0)
