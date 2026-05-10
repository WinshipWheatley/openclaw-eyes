"""
Business Ops Intent v0.

Deterministic intent classification for the Business Ops Spine.
Unifies keyword-based intent detection across Gmail, Calendar, Payments, and Files.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


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

    # 3. Status / Orientation (High priority for explicit orientation)
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

    # 4. Email / Gmail
    email_terms = (
        "email", "gmail", "inbox", "message", "unread", "sender",
        "subject", "from", "reply", "draft", "thread", "attachment"
    )
    for term in email_terms:
        if term in q:
            return IntentFrame("email_search", "read_only", "email", 0.9, term)

    # 5. Calendar
    calendar_terms = (
        "calendar", "schedule", "appointment", "meeting", "event",
        "tomorrow morning", "tomorrow afternoon", "this week", "next week",
        "what's on", "what do i have", "what's tomorrow", "what's today"
    )
    for term in calendar_terms:
        if term in q:
            return IntentFrame("calendar_read", "read_only", "calendar", 0.9, term)

    # 6. Payment / Billing
    payment_terms = (
        "invoice", "payment", "paid", "unpaid", "receivable",
        "owes", "owed", "client follow-up", "balance", "overdue",
        "deposit", "cleared", "transfer", "funds"
    )
    for term in payment_terms:
        if term in q:
            return IntentFrame("payment_verify", "read_only", "payment", 0.9, term)

    # 7. File / Path
    file_terms = (
        "file", "path", "exist", "directory", "folder", "/mnt", "/home",
        ".py", ".md", ".json", ".sh", ".txt", ".csv"
    )
    for term in file_terms:
        if term in q:
            return IntentFrame("file_verify", "read_only", "file", 0.8, term)

    # 8. Contacts
    contact_terms = (
        "number for", "phone number", "phone for", "contact for",
        "do i have a number", "do i have contact", "what's the number",
        "how do i reach", "how do i contact", "their number", "his number",
        "her number", "have their contact"
    )
    for term in contact_terms:
        if term in q:
            return IntentFrame("contacts_read", "read_only", "contacts", 0.9, term)

    # 9. Fuzzy/Natural Operator Phrases (Lower priority than specific domains)
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
