"""Cross-reference a snapped check against the bank's deposit email.

Operator idea (2026-07-03): "the picture didn't give a good check number — the system
could check the Bank of America email to see if the check number is in there." Two
imperfect sources → one confident record. The photo OCR gives amount + payee + bank; the
bank email confirms the check number, date, and amount. Where OCR is fuzzy and the email
is clean, the email wins; disagreements are surfaced, never silently merged.

Read-only + governed: the Gmail lookup goes through google_access_broker (gmail.readonly);
this module never sends, never posts to the ledger. All parsing is local + deterministic.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Mapping

_BANK_SENDERS = {
    "bankofamerica.com": "Bank of America",
    "ealerts.bankofamerica.com": "Bank of America",
    "wellsfargo.com": "Wells Fargo",
    "chase.com": "JPMorgan Chase",
}
_DEPOSIT_MARKERS = ("deposit", "mobile deposit", "check received", "eposit received",
                    "your deposit", "funds are available", "deposit of")


def _amount(text: str) -> float | None:
    # Handle both "$2,000.00" (comma-grouped) and "$2000.00" (plain) — BoA uses the latter.
    m = re.search(r"\$\s*([0-9][0-9,]*\.[0-9]{2}|[0-9][0-9,]*)", text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def parse_bank_email(*, subject: str, body: str, sender: str) -> dict[str, Any]:
    """Extract deposit facts from a bank alert email. Honest: absent fields stay None."""
    blob = f"{subject}\n{body}"
    low_sender = sender.lower()
    bank = None
    for domain, name in _BANK_SENDERS.items():
        if domain in low_sender:
            bank = name
            break
    is_deposit = any(m in blob.lower() for m in _DEPOSIT_MARKERS)

    check_number = None
    for pat in (r"check\s*(?:#|number|no\.?)\s*:?\s*([0-9]{4,12})",
                r"check\s+([0-9]{6,12})\b"):
        m = re.search(pat, blob, re.IGNORECASE)
        if m:
            check_number = m.group(1)
            break

    date = None
    m = re.search(r"\b([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})\b", blob)
    if m:
        date = m.group(1)
    else:
        m = re.search(r"\b([A-Z][a-z]{2,8}\s+[0-9]{1,2},?\s+20[0-9]{2})\b", blob)
        if m:
            date = m.group(1)

    acct = None
    m = re.search(r"(?:ending in|ending|banking)\D{0,4}([0-9]{4})\b", blob, re.IGNORECASE)
    if m:
        acct = m.group(1)

    # BoA deposit emails carry a "Confirmation # NNNN" (their deposit tracking id) — NOT the
    # paper check number. Verified against the operator's real 2026-07-02 BoA email.
    confirmation_number = None
    mc = re.search(r"confirmation\s*(?:#|number|no\.?)?\s*:?\s*([0-9]{6,})", blob, re.IGNORECASE)
    if mc:
        confirmation_number = mc.group(1)

    posted = re.search(r"(?:credit posts?|posts?)\D{0,8}([0-9]{1,2}/\s?[0-9]{1,2}/\s?[0-9]{2,4})", blob, re.IGNORECASE)
    post_date = posted.group(1).replace(" ", "") if posted else None
    available_now = None
    ma = re.search(r"available now\s*\$\s*([0-9,]+\.[0-9]{2})", blob, re.IGNORECASE)
    if ma:
        available_now = float(ma.group(1).replace(",", ""))

    return {
        "bank": bank,
        "is_deposit_confirmation": is_deposit,
        "amount": _amount(blob),
        "check_number": check_number,        # usually None for BoA — the check# is on the photo
        "confirmation_number": confirmation_number,
        "date": date,
        "post_date": post_date,
        "available_now": available_now,
        "account_last4": acct,
        "source": "bank_email",
    }


def reconcile(ocr_check: Mapping[str, Any], email: Mapping[str, Any]) -> dict[str, Any]:
    """Merge OCR check facts with bank-email facts. Email fills/confirms what OCR left
    uncertain; conflicts are surfaced. Returns a reconciled record with per-field source."""
    fields: dict[str, Any] = {}
    sources: dict[str, str] = {}
    conflicts: list[str] = []
    resolved_review: list[str] = []

    ocr_amt = ocr_check.get("amount")
    em_amt = email.get("amount")
    if ocr_amt is not None and em_amt is not None:
        if abs(float(ocr_amt) - float(em_amt)) < 0.01:
            fields["amount"], sources["amount"] = ocr_amt, "photo+bank_email (agree)"
        else:
            fields["amount"], sources["amount"] = ocr_amt, "photo (DISAGREES with bank_email)"
            conflicts.append(f"amount: photo ${ocr_amt:,.2f} vs bank email ${em_amt:,.2f}")
    elif ocr_amt is not None:
        fields["amount"], sources["amount"] = ocr_amt, "photo"
    elif em_amt is not None:
        fields["amount"], sources["amount"] = em_amt, "bank_email"

    # Check number: OCR is unreliable; the bank email is authoritative when present.
    ocr_cn = ocr_check.get("check_number_guess")
    em_cn = email.get("check_number")
    if em_cn:
        fields["check_number"], sources["check_number"] = em_cn, "bank_email (authoritative)"
        # OCR-vs-email difference here is the EXPECTED fix (email corrects a garbled read),
        # not a blocking conflict — record it as a resolution note only.
        resolved_review.append("check_number")
    elif ocr_cn:
        fields["check_number"], sources["check_number"] = ocr_cn, "photo (unconfirmed)"

    # Date: prefer the bank email's clean date over OCR's garbled one.
    ocr_dt = ocr_check.get("date_guess")
    em_dt = email.get("date")
    if em_dt:
        fields["date"], sources["date"] = em_dt, "bank_email"
        resolved_review.append("date")
    elif ocr_dt:
        fields["date"], sources["date"] = ocr_dt, "photo (unconfirmed)"

    fields["payee"] = ocr_check.get("payee")
    sources["payee"] = "photo"
    fields["bank"] = ocr_check.get("bank") or email.get("bank")
    sources["bank"] = "photo" if ocr_check.get("bank") else "bank_email"
    fields["account_last4"] = email.get("account_last4")
    if email.get("account_last4"):
        sources["account_last4"] = "bank_email"

    if email.get("confirmation_number"):
        fields["deposit_confirmation_number"] = email["confirmation_number"]
        sources["deposit_confirmation_number"] = "bank_email"
    if email.get("available_now") is not None:
        fields["funds_available"] = email["available_now"] > 0
        fields["post_date"] = email.get("post_date")

    deposit_confirmed = bool(email.get("is_deposit_confirmation"))
    amount_agrees = ("amount" in sources and "agree" in sources["amount"])
    return {
        "reconciled": fields,
        "field_sources": sources,
        "deposit_confirmed_by_bank": deposit_confirmed,
        "conflicts": conflicts,
        "resolved_from_email": resolved_review,
        # High when the bank confirms the deposit AND the amount matches the photo — the
        # realistic BoA case (check# comes from the photo, amount+deposit from the email).
        "confidence": "high" if (deposit_confirmed and amount_agrees and not conflicts) else
                       ("review" if conflicts else "medium"),
    }


def find_bank_email_for_check(
    ocr_check: Mapping[str, Any],
    *,
    gmail_search: Callable[[str], list[dict]],
    gmail_read_body: Callable[[str], dict] | None = None,
    max_scan: int = 10,
) -> dict[str, Any] | None:
    """Search Gmail (governed, read-only) for the bank deposit email matching this check's
    amount, parse it, and return its facts. gmail_search/read_body are injected (the live
    wiring passes google_access_broker.call closures); returns None if no match."""
    amount = ocr_check.get("amount")
    query_terms = ["from:bankofamerica.com OR from:bofa.com OR subject:deposit"]
    if isinstance(amount, (int, float)):
        query_terms.append(f'"{amount:,.2f}"')
    try:
        hits = gmail_search(" ".join(query_terms)) or []
    except Exception:
        return None
    for hit in hits[:max_scan]:
        subject = str(hit.get("subject") or "")
        sender = str(hit.get("from") or hit.get("sender") or "")
        body = str(hit.get("snippet") or hit.get("body") or "")
        if gmail_read_body and hit.get("id"):
            try:
                full = gmail_read_body(str(hit["id"])) or {}
                body = str(full.get("body") or body)
            except Exception:
                pass
        facts = parse_bank_email(subject=subject, body=body, sender=sender)
        if facts["is_deposit_confirmation"] and (
            facts["amount"] is None or amount is None
            or abs(float(facts["amount"]) - float(amount)) < 0.01
        ):
            facts["email_id"] = hit.get("id")
            return facts
    return None


__all__ = ["parse_bank_email", "reconcile", "find_bank_email_for_check"]
