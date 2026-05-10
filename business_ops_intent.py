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

    # 1. User denial phrases (Highest priority)
    if any(phrase in q for phrase in ("no gmail", "no email", "no tools", "without gmail", "without email")):
        return IntentFrame("deny", "stop", "none", 1.0)

    # 2. Email / Gmail
    email_terms = (
        "email", "gmail", "inbox", "message", "unread", "sender",
        "subject", "from", "reply", "draft", "thread", "attachment"
    )
    for term in email_terms:
        if term in q:
            return IntentFrame("email_search", "read_only", "email", 0.9, term)

    # 3. Calendar
    calendar_terms = (
        "calendar", "schedule", "appointment", "meeting", "event",
        "tomorrow morning", "tomorrow afternoon", "this week", "next week",
        "what's on", "what do i have", "what's tomorrow", "what's today"
    )
    for term in calendar_terms:
        if term in q:
            return IntentFrame("calendar_read", "read_only", "calendar", 0.9, term)

    # 4. Payment / Billing
    payment_terms = (
        "invoice", "payment", "paid", "unpaid", "receivable",
        "owes", "owed", "client follow-up", "balance", "overdue",
        "deposit", "cleared", "transfer", "funds"
    )
    for term in payment_terms:
        if term in q:
            return IntentFrame("payment_verify", "read_only", "payment", 0.9, term)

    # 5. File / Path
    file_terms = (
        "file", "path", "exist", "directory", "folder", "/mnt", "/home",
        ".py", ".md", ".json", ".sh", ".txt", ".csv"
    )
    for term in file_terms:
        if term in q:
            return IntentFrame("file_verify", "read_only", "file", 0.8, term)

    # 6. Contacts
    contact_terms = (
        "number for", "phone number", "phone for", "contact for",
        "do i have a number", "do i have contact", "what's the number",
        "how do i reach", "how do i contact", "their number", "his number",
        "her number", "have their contact"
    )
    for term in contact_terms:
        if term in q:
            return IntentFrame("contacts_read", "read_only", "contacts", 0.9, term)

    # 7. Status / Orientation
    status_terms = ("status", "orientation", "where are we", "what's next", "summary")
    for term in status_terms:
        if term in q:
            return IntentFrame("ops_status", "read_only", "logging", 0.7, term)

    return IntentFrame("none", "none", "none", 0.0)
