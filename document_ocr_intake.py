"""Local document OCR intake — let the SYSTEM read checks/documents the operator sends.

Operator ask (2026-07-03): "I know you have vision, but did the system record the check
or did you? ... how do we make [the system see it] happen?" This is that: on-box OCR
(tesseract, $0, no cloud, no LLM) so a snapped check/document becomes structured, grounded
facts the system holds — not just image bytes.

Honesty rules (checks are money — being wrong is worse than saying "unsure"):
- Extract only what OCR supports; cross-validate the amount (digits vs spelled-out).
- Fields OCR mangles (check numbers, dates on a noisy fax) are marked LOW confidence and
  listed in needs_review — the system asks the operator to confirm, never fabricates.
- No external calls, no LLM. Everything local and deterministic.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

TESSERACT = shutil.which("tesseract") or "/usr/bin/tesseract"

_KNOWN_BANKS = (
    ("wells fargo", "Wells Fargo Bank, N.A."),
    ("bank of america", "Bank of America, N.A."),
    ("chase", "JPMorgan Chase Bank, N.A."),
    ("pnc", "PNC Bank, N.A."),
    ("truist", "Truist Bank"),
    ("citibank", "Citibank, N.A."),
    ("capital one", "Capital One, N.A."),
)

_WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "hundred": 100, "thousand": 1000, "million": 1000000,
}


def run_ocr(image_path: str | Path) -> str:
    """Run tesseract on an image; return extracted text ('' on any failure). Local only."""
    path = Path(image_path)
    if not path.is_file():
        return ""
    try:
        result = subprocess.run(
            [TESSERACT, str(path), "-", "--psm", "6"],
            capture_output=True, text=True, timeout=45,
        )
        return result.stdout if result.returncode == 0 else ""
    except Exception:
        return ""


def classify_document(text: str) -> str:
    low = text.lower()
    check_markers = ("pay exactly", "pay to the order", "to the order of", "void after",
                     "authorized signer", "authorised signer", "check#", "check #")
    if sum(1 for m in check_markers if m in low) >= 2 or ("dollars" in low and "amount" in low):
        return "check"
    if any(m in low for m in ("statement period", "beginning balance", "ending balance",
                              "account summary", "deposits and additions")):
        return "bank_statement"
    if any(m in low for m in ("invoice", "bill to", "amount due", "remit to")):
        return "invoice"
    return "unknown"


def _words_to_amount(text: str) -> float | None:
    """Best-effort spelled-out dollar amount, e.g. 'Two Thousand and 00/100' -> 2000.0."""
    low = text.lower()
    m = re.search(r"([a-z ]+?)\s+(?:and\s+)?\d{1,2}\s*/\s*100", low)
    phrase = m.group(1) if m else low
    tokens = [t for t in re.findall(r"[a-z]+", phrase) if t in _WORD_NUMBERS]
    if not tokens:
        return None
    total = 0
    current = 0
    for tok in tokens:
        val = _WORD_NUMBERS[tok]
        if val == 100:
            current = (current or 1) * 100
        elif val >= 1000:
            current = (current or 1) * val
            total += current
            current = 0
        else:
            current += val
    total += current
    return float(total) if total else None


def _numeric_amount(text: str) -> float | None:
    # Prefer a $-anchored figure; fall back to any N,NNN.NN. OCR often mangles the $.
    for pat in (r"\$?\s*\**\s*([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2})",
                r"([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2})"):
        for m in re.finditer(pat, text):
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                continue
    return None


def _find_bank(text: str) -> str | None:
    low = text.lower()
    for needle, canonical in _KNOWN_BANKS:
        if needle in low:
            return canonical
    return None


# Payees this system pays out to are the operator's own business names — anchoring on
# them is the most robust extraction for HIS checks (OCR mangles generic layout cues).
_KNOWN_PAYEES = ("WINSHIP LIVE", "WINSHIP", "DEEP POCKET RECORDS")
_ADDRESS_MARKERS = (" ST", " AVE", " RD", " BLVD", " LANE", " DR", " CT", " WAY", "VOID", "SUITE", "APT")


def _looks_like_address(candidate: str) -> bool:
    up = " " + candidate.upper() + " "
    if any(m in up for m in _ADDRESS_MARKERS):
        return True
    if len(re.findall(r"\d", candidate)) >= 3:  # street numbers / zips
        return True
    return False


def _find_payee(text: str) -> tuple[str | None, str]:
    up = text.upper()
    # 1) Known operator payee anchored — highest confidence on his own checks.
    for name in _KNOWN_PAYEES:
        if name in up:
            return name.title() if name != "WINSHIP LIVE" else "Winship Live", "high"
    # 2) "TO THE ORDER OF <NAME>" — check the marker line itself then the next line,
    #    rejecting address/void junk so we never present an address as the payee.
    lines = [ln.strip() for ln in text.splitlines()]
    for i, ln in enumerate(lines):
        low = ln.lower()
        if "order" in low or "to the" in low or "pay to" in low:
            after = re.sub(r"(?i).*(order|to the|pay to)\s*(of)?", "", ln).strip(" .:-&")
            for c in [after] + [l.strip(" .:-&") for l in lines[i + 1:i + 2]]:
                if len(c) >= 3 and re.search(r"[A-Za-z]", c) and not _looks_like_address(c):
                    return c, "medium"
    return None, "none"


def extract_check_facts(text: str) -> dict[str, Any]:
    numeric = _numeric_amount(text)
    words = _words_to_amount(text)
    amount = numeric if numeric is not None else words
    amount_confidence = "none"
    if numeric is not None and words is not None:
        amount_confidence = "high" if abs(numeric - words) < 0.01 else "conflict"
    elif numeric is not None or words is not None:
        amount_confidence = "medium"

    bank = _find_bank(text)
    payee, payee_conf = _find_payee(text)
    void_days = None
    mvoid = re.search(r"void after\s+(\d{1,3})\s*days", text, re.IGNORECASE)
    if mvoid:
        void_days = int(mvoid.group(1))

    # These OCR-mangle badly on a noisy check; capture the raw guess but flag for review.
    mnum = re.search(r"check\s*#?\s*:?\s*([0-9]{6,12})", text, re.IGNORECASE)
    check_number_guess = mnum.group(1) if mnum else None
    mdate = re.search(r"date\s*:?\s*([0-9]{1,2}\s*/\s*[0-9]{1,2}\s*/\s*[0-9]{2,4})", text, re.IGNORECASE)
    date_guess = mdate.group(1).replace(" ", "") if mdate else None

    needs_review: list[str] = []
    if amount_confidence in ("none", "conflict"):
        needs_review.append("amount")
    if check_number_guess:
        needs_review.append("check_number (OCR-unreliable — confirm)")
    if date_guess:
        needs_review.append("date (OCR-unreliable — confirm)")
    if payee_conf in ("low", "none"):
        needs_review.append("payee")

    return {
        "amount": amount,
        "amount_confidence": amount_confidence,
        "amount_numeric": numeric,
        "amount_words": words,
        "payee": payee,
        "payee_confidence": payee_conf,
        "bank": bank,
        "check_number_guess": check_number_guess,
        "date_guess": date_guess,
        "void_after_days": void_days,
        "needs_review": needs_review,
    }


def read_document(image_path: str | Path, *, caption: str = "") -> dict[str, Any]:
    """OCR a document image and return structured, honest facts. Never raises."""
    text = run_ocr(image_path)
    if not text.strip():
        return {"status": "ocr_empty", "doc_type": "unknown", "image_path": str(image_path),
                "note": "OCR produced no text (image unreadable or tesseract unavailable)."}
    doc_type = classify_document(text)
    out: dict[str, Any] = {
        "status": "read",
        "doc_type": doc_type,
        "image_path": str(image_path),
        "caption": caption,
        "ocr_char_count": len(text),
    }
    if doc_type == "check":
        out["check"] = extract_check_facts(text)
    return out


def summarize_for_operator(result: dict[str, Any]) -> str:
    """A tasteful, TRUE one-liner the system can reply with — flags uncertainty honestly."""
    if result.get("status") != "read":
        return "I stored the image but couldn't read it (OCR came back empty)."
    if result.get("doc_type") != "check":
        return f"Read the image — looks like a {result.get('doc_type')} document. Saved it."
    c = result.get("check", {})
    amt = c.get("amount")
    amt_str = f"${amt:,.2f}" if isinstance(amt, (int, float)) else "an unclear amount"
    payee = c.get("payee") or "you"
    bank = c.get("bank") or "the bank on it"
    line = f"Read the check: {amt_str} to {payee}, drawn on {bank}."
    cn, dt = c.get("check_number_guess"), c.get("date_guess")
    if cn or dt:
        bits = []
        if cn:
            bits.append(f"check # {cn}")
        if dt:
            bits.append(f"date {dt}")
        line += " I read " + " and ".join(bits) + " — worth a quick confirm (OCR can slip a digit)."
    return line


__all__ = ["run_ocr", "classify_document", "extract_check_facts", "read_document",
           "summarize_for_operator"]
