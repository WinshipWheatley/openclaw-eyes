"""money_truth — the ONE money source for every agent (task 140).

Doctrine (Operator/to-codex/140-money-one-source-fleetwide.md):
  Money has ONE source: generated/read_models/receivables_month_bounded.json
  (built by receivables_month_bounded.py from canonical business facts) plus the
  finance_invoice_reconciliation answer-topic shape. Every agent pipeline, on any
  money-class question, either
    (a) answers VERBATIM from that source via the shared humanized lines
        (operator_surface_guard.render_operator_money_status_line), or
    (b) routes in ONE warm line and includes the answer.
  NEVER a second money pipeline. NEVER certainty from empty data
  ("no data yet" != "none outstanding"). NEVER a relevance-free "verified match".

Blast-radius guard-rail (141 interplay): an active money-MOVEMENT ask
("pay Sarah $500 now", "send $200 to X") must NEVER receive a read-only ledger
answer — classify_money_question() returns "money_movement" for those and every
consumer defers to the refusal/approval gates.

Contract: deterministic, read-only, no LLM calls, no network. The only I/O is
reading the read-model JSON.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from operator_surface_guard import operator_surface_value, render_operator_money_status_line

SCHEMA_VERSION = "money_truth_v0"
AUTHORITY_SOURCE = "receivables_month_bounded"
FINANCE_ANSWER_TOPIC = "finance_invoice_reconciliation"

# The one truth read-model. Tests monkeypatch this module attribute.
DEFAULT_READ_MODEL_PATH = Path(__file__).resolve().parent / "generated" / "read_models" / "receivables_month_bounded.json"

# "No data yet" is a DATA GAP, never a zero balance ("Outstanding — none" is banned).
NOT_TRACKED_LINE = (
    "Money is not tracked yet — the receivables ledger read-model has no rows. "
    "That's a data gap, not a zero balance."
)

# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_money_truth(path: str | Path | None = None) -> dict[str, Any]:
    """Read the receivables_month_bounded read-model. Empty dict on any failure."""
    target = Path(path) if path is not None else DEFAULT_READ_MODEL_PATH
    try:
        payload = json.loads(Path(target).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def money_rows(payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping):
        return []
    return [dict(row) for row in payload.get("rows", ()) if isinstance(row, Mapping)]


def money_truth_as_of(payload: Mapping[str, Any] | None) -> str:
    raw = str((payload or {}).get("generated_at") or "").strip()
    return raw[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", raw) else raw


# ---------------------------------------------------------------------------
# Rendering — the shared humanized lines (fleet-identical facts)
# ---------------------------------------------------------------------------

def _fmt_minor_units(value: int, currency: str = "USD") -> str:
    major = value / 100
    prefix = "$" if str(currency or "USD").upper() == "USD" else f"{str(currency).upper()} "
    if float(major).is_integer():
        return f"{prefix}{int(major):,}"
    return f"{prefix}{major:,.2f}"


def _client_display(row: Mapping[str, Any]) -> str:
    name = str(row.get("client_display_name") or "").strip()
    if name:
        return name
    return str(row.get("client_ref") or "Unknown client").replace("_", " ").title()


def _month_name(row: Mapping[str, Any]) -> str:
    raw = str(row.get("month") or "").strip()
    matched = re.fullmatch(r"(\d{4})-(0[1-9]|1[0-2])", raw)
    if not matched:
        return operator_surface_value(raw)
    # Task 155: rendering the year is part of temporal honesty.  "May" alone
    # is ambiguous once the ledger contains more than one May.
    return f"{operator_surface_value(raw)} {matched.group(1)}"


def _norm_question(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", str(text or "").lower().replace("'", "").replace("’", "")).strip()


def _client_phrases(row: Mapping[str, Any]) -> set[str]:
    """Phrases/tokens that identify this client inside an operator question."""
    phrases: set[str] = set()
    for raw in (str(row.get("client_ref") or ""), str(row.get("client_display_name") or "")):
        cleaned = re.sub(r"[^a-z0-9 ]+", "", raw.lower().replace("_", " ").replace("'", "")).strip()
        if not cleaned:
            continue
        phrases.add(cleaned)
        words = cleaned.split()
        for a, b in zip(words, words[1:]):
            phrases.add(f"{a} {b}")
        for word in words:
            if len(word) >= 5:
                phrases.add(word)
    return phrases


_MONTH_NUMBERS = {
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
}


def _requested_temporal_scope(
    question: str,
    *,
    default_year: str = "",
) -> tuple[set[str], set[str]]:
    """Return exact periods plus any year-only filter.

    Month/year pairs stay paired, never cartesian.  A named month without a
    year binds to the read-model's as-of year, so "back in May" in a July 2026
    snapshot means May 2026 rather than every May ever recorded.
    """
    q = str(question or "").lower()
    temporal_years = set(
        re.findall(r"\b(?:in|during|for|from|since|through|year)\s+(20\d{2})\b", q)
    )
    periods: set[str] = set()
    paired_months: set[str] = set()

    for year, month in re.findall(r"\b(20\d{2})[-/](0[1-9]|1[0-2])\b", q):
        periods.add(f"{year}-{month}")
        temporal_years.add(year)
    for month, year in re.findall(r"\b(0?[1-9]|1[0-2])[-/](20\d{2})\b", q):
        periods.add(f"{year}-{month.zfill(2)}")
        temporal_years.add(year)

    month_names = "|".join(_MONTH_NUMBERS)
    for name, year in re.findall(rf"\b({month_names})\s+(20\d{{2}})\b", q):
        month = _MONTH_NUMBERS[name]
        periods.add(f"{year}-{month}")
        paired_months.add(month)
        temporal_years.add(year)
    for year, name in re.findall(rf"\b(20\d{{2}})\s+({month_names})\b", q):
        month = _MONTH_NUMBERS[name]
        periods.add(f"{year}-{month}")
        paired_months.add(month)
        temporal_years.add(year)

    named_months = {
        number
        for name, number in _MONTH_NUMBERS.items()
        if name != "may" and re.search(rf"\b{re.escape(name)}\b", q)
    }
    may_is_temporal = bool(
        "05" in paired_months
        or re.search(r"\b(?:in|during|for|from|since|through|by)\s+may\b", q)
        or re.search(
            rf"\bmay\s+(?:vs\.?|versus|compared\s+(?:with|to)|and|to)\s+(?:{month_names})\b",
            q,
        )
    )
    if may_is_temporal:
        named_months.add("05")
    for month in named_months - paired_months:
        bind_year = next(iter(temporal_years)) if len(temporal_years) == 1 else default_year
        if bind_year:
            periods.add(f"{bind_year}-{month}")

    year_only = temporal_years if not named_months and not periods else set()
    return periods, year_only


def _rows_for_question(
    rows: Sequence[Mapping[str, Any]],
    question: str,
    *,
    default_year: str = "",
) -> list[Mapping[str, Any]]:
    """Filter rows to every explicitly named client and period.

    Once the operator names a month/year, an empty temporal match stays empty;
    falling back to every client row would silently blend periods again.
    """
    q = _norm_question(question)
    if not q:
        return list(rows)
    client_matched = [row for row in rows if any(p in q for p in _client_phrases(row))]
    scoped: list[Mapping[str, Any]] = client_matched or list(rows)

    periods, year_only = _requested_temporal_scope(question, default_year=default_year)
    if not periods and not year_only:
        return scoped
    temporal: list[Mapping[str, Any]] = []
    for row in scoped:
        matched = re.fullmatch(r"(\d{4})-(0[1-9]|1[0-2])", str(row.get("month") or "").strip())
        if not matched:
            continue
        row_year, row_month = matched.groups()
        if periods and f"{row_year}-{row_month}" not in periods:
            continue
        if year_only and row_year not in year_only:
            continue
        temporal.append(row)
    return temporal


def _temporal_scope_label(question: str, payload: Mapping[str, Any] | None) -> str:
    as_of = money_truth_as_of(payload)
    default_year = as_of[:4] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of) else ""
    periods, years = _requested_temporal_scope(question, default_year=default_year)
    labels = []
    for period in sorted(periods):
        year, _month = period.split("-", 1)
        labels.append(f"{operator_surface_value(period)} {year}")
    labels.extend(sorted(years))
    return " and ".join(labels)


def _no_matching_rows_answer(question: str, payload: Mapping[str, Any] | None) -> str:
    label = _temporal_scope_label(question, payload)
    if money_rows(payload) and label:
        return (
            f"No receivable row matches {label} in receivables_month_bounded. "
            "That is a scoped data gap, not a zero balance."
        )
    return NOT_TRACKED_LINE


def _ensure_period(line: str) -> str:
    line = line.strip()
    return line if line.endswith((".", "!", "?")) else line + "."


def money_lines(payload: Mapping[str, Any] | None = None, *, question: str = "") -> list[str]:
    """Humanized money lines from the one truth. Same facts for every agent.

    Open/needs-reconcile rows first, then pending-send (expected_uninvoiced),
    then the settled tail. Empty read-model -> [] (callers render NOT_TRACKED_LINE).
    """
    payload = payload if payload is not None else load_money_truth()
    as_of = money_truth_as_of(payload)
    default_year = as_of[:4] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of) else ""
    rows = _rows_for_question(money_rows(payload), question, default_year=default_year)
    open_lines: list[str] = []
    pending_lines: list[str] = []
    settled_months: dict[str, list[str]] = {}

    for row in rows:
        status = str(row.get("payment_status") or "unknown").strip().lower()
        client = _client_display(row)
        month = _month_name(row)
        amount_known = bool(row.get("amount_known", True))
        open_minor = row.get("open_minor_units")
        needs_reconcile = bool(row.get("needs_reconcile"))

        if status == "expected_uninvoiced":
            line = f"{client}: current invoice ready to send once the copy is fixed"
            pending_lines.append(_ensure_period(f"{line} ({month})" if month else line))
        elif status == "settled" or bool(row.get("settled_past_no_compound")):
            settled_months.setdefault(client, [])
            if month:
                settled_months[client].append(month)
        elif not amount_known or open_minor is None:
            open_lines.append(_ensure_period(
                render_operator_money_status_line(entity=client, amount="", status=status or "open_amount_unknown")
            ))
        elif int(open_minor or 0) > 0 or needs_reconcile:
            amount = _fmt_minor_units(int(open_minor or 0), str(row.get("currency_iso") or "USD"))
            line = render_operator_money_status_line(
                entity=client,
                amount=amount,
                status="needs_reconcile" if needs_reconcile else (status or "open"),
            )
            open_lines.append(_ensure_period(f"{line} ({month})" if month else line))

    lines = open_lines + pending_lines
    for client, months in settled_months.items():
        month_text = "/".join(dict.fromkeys(months))
        prefix = f"{client} {month_text}" if month_text else client
        lines.append(f"{prefix} settled — paid; don't chase.")
    return lines


def render_money_answer(
    agent: str = "maestro",
    *,
    payload: Mapping[str, Any] | None = None,
    path: str | Path | None = None,
    question: str = "",
) -> str:
    """The shared money answer text (agent framing is the caller's route_line)."""
    payload = payload if payload is not None else load_money_truth(path)
    lines = money_lines(payload, question=question)
    text = " ".join(lines) if lines else _no_matching_rows_answer(question, payload)
    if text == NOT_TRACKED_LINE:
        return text
    as_of = money_truth_as_of(payload)
    if as_of:
        text = f"{text} (as of {as_of})"
    return text


def settled_row_proof_refs(
    question: str,
    *,
    payload: Mapping[str, Any] | None = None,
    path: str | Path | None = None,
) -> tuple[str, ...]:
    """Return proof refs only for structured settled rows selected by the question."""

    payload = payload if payload is not None else load_money_truth(path)
    as_of = money_truth_as_of(payload)
    default_year = as_of[:4] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of) else ""
    rows = _rows_for_question(money_rows(payload), question, default_year=default_year)
    refs = []
    for row in rows:
        client_ref = str(row.get("client_ref") or "").strip()
        month = str(row.get("month") or "").strip()
        if not client_ref or not re.fullmatch(r"[a-z0-9_]+", client_ref):
            continue
        if not re.fullmatch(r"\d{4}-\d{2}", month):
            continue
        if not (
            row.get("structured_fact") is True
            and row.get("current_truth") is True
            and str(row.get("payment_status") or "") == "settled"
            and row.get("open_minor_units") == 0
            and row.get("needs_reconcile") is False
            and row.get("settled_past_no_compound") is True
        ):
            continue
        refs.append(f"receivables_row:{client_ref}:{month}:settled")
    return tuple(dict.fromkeys(refs))


def render_payment_verification_ledger(
    question: str,
    *,
    payload: Mapping[str, Any] | None = None,
    path: str | Path | None = None,
) -> str:
    """Render the bounded receivables side of a payment verification answer.

    Payment-notification metadata is only evidence; this explicit source and
    as-of label prevents it from being laundered into bank-settlement truth.
    The label remains present even when the read-model is temporarily missing.
    """
    payload = payload if payload is not None else load_money_truth(path)
    lines = money_lines(payload, question=question)
    answer = " ".join(lines) if lines else _no_matching_rows_answer(question, payload)
    as_of = money_truth_as_of(payload) or "unavailable"
    return f"Receivables (receivables_month_bounded, as of {as_of}): {answer}"


_ROUTE_LINES = {
    "niles": "Money's Maestro's desk — here's the picture:",
    "guardian": "Read-only money check — the ledger picture:",
    "cassandra": "From the shared money ledger:",
    "chief": "From the shared money ledger:",
    "hermes": "Maestro has the money picture — here it is:",
    "maestro": "Money:",
}


def route_line(agent: str = "maestro") -> str:
    return _ROUTE_LINES.get(str(agent or "").strip().lower(), "Maestro has the money picture — here it is:")


def finance_answer_topic_fact(
    payload: Mapping[str, Any] | None = None,
    *,
    path: str | Path | None = None,
) -> dict[str, Any] | None:
    """finance_invoice_reconciliation answer-topic fact (maestro_context_packet shape)."""
    payload = payload if payload is not None else load_money_truth(path)
    lines = money_lines(payload)
    if not lines:
        return None
    as_of = money_truth_as_of(payload)
    source_refs = [str(ref) for ref in (payload or {}).get("source_refs", ()) if str(ref).strip()]
    return {
        "topic": FINANCE_ANSWER_TOPIC,
        "label": "Current money owed answer topic",
        "value": "Money: " + " ".join(lines),
        "provenance": "derived_answer_topic",
        "source_ref": ", ".join(source_refs) or "generated/read_models/receivables_month_bounded.json",
        "answer_topic": True,
        "structured_fact": True,
        "current_truth": True,
        "as_of": as_of,
        "authority_source": AUTHORITY_SOURCE,
    }


# ---------------------------------------------------------------------------
# Money-question classification (140 x 141 guard-rail lives here)
# ---------------------------------------------------------------------------

_MOVEMENT_PHRASES = (
    "wire ", "zelle", "venmo", " ach ", "bank transfer", "pay $", "send $", "transfer $",
)
_MOVEMENT_VERB_RE = re.compile(r"\b(send|pay|wire|transfer)\b")
_AMOUNT_RE = re.compile(r"\$\s*\d")
_MOVEMENT_MONEY_WORD_RE = re.compile(
    r"\b(send|pay|wire|transfer)\b[^.?!]{0,50}\b(\d[\d,]*(?:\.\d{1,2})?\s*)?(money|dollars|bucks)\b[^.?!]{0,40}\bto\b"
)
_ARRIVAL_SUBJECT_RE = re.compile(r"\b(payment|check|cheque|deposit|funds|money|remittance)\b")
_ARRIVAL_VERB_RE = re.compile(
    r"\b(com(?:e|es|ing) through|came through|com(?:e|es|ing) in|came in|"
    r"arriv(?:e|es|ed|ing)|land(?:s|ed|ing)?|clear(?:s|ed|ing)?|post(?:s|ed|ing)?(?: yet)?|"
    r"hit(?:ting|s)? the (?:bank )?account|show(?:s|ed|ing)? up|"
    r"in my account|in the account|in the bank)\b"
)
_ARRIVAL_QUESTION_RE = re.compile(
    r"^(?:did|has|have|is|are|was|were|can|could|would|do\s+you\s+know|"
    r"what(?:'s|\s+is)|where(?:'s|\s+is))\b|\bwhether\b"
)
_PAYMENT_OPERATOR_ACTION_RE = re.compile(
    r"(?:"
    r"^(?:(?:can|could|would|will|did|have|has)\b[^.?!]{0,80}|(?:please\s+)?)"
    r"(?:post(?:ed|ing)?|clear(?:ed|ing)?|mark(?:ed|ing)?|set(?:ting)?|"
    r"update(?:d|ing)?)\b[^.?!]{0,120}"
    r"\b(?:payment|check|cheque|deposit|funds|money|remittance)\b"
    r"|^(?:was|were|is|are|has|have)\b[^.?!]{0,80}"
    r"\b(?:payment|check|cheque|deposit|funds|money|remittance)\b"
    r"[^.?!]{0,60}\b(?:posted|cleared|marked|set|updated)\b"
    r"[^.?!]{0,40}\bby\b(?=\s+\S)"
    r")",
)
_EXTERNAL_SETTLEMENT_ACTOR = (
    r"(?:the\s+)?(?:bank|payment\s+processor|processor|stripe|client|customer|"
    r"payer|remitter|vendor|capital\s+hilton|hilton)"
)
_PAYMENT_EXTERNAL_ARRIVAL_ACTION_RE = re.compile(
    r"(?:"
    r"^(?:did|has|have)\s+" + _EXTERNAL_SETTLEMENT_ACTOR
    + r"\b[^.?!]{0,60}\b(?:post(?:ed|ing)?|clear(?:ed|ing)?)\b"
    r"[^.?!]{0,80}\b(?:payment|check|cheque|deposit|funds|money|remittance)\b"
    r"|^(?:was|were|is|are|has|have)\b[^.?!]{0,80}"
    r"\b(?:payment|check|cheque|deposit|funds|money|remittance)\b"
    r"[^.?!]{0,60}\b(?:posted|cleared)\b[^.?!]{0,40}\bby\s+"
    + _EXTERNAL_SETTLEMENT_ACTOR
    + r"\b"
    r")"
)
_PAYMENT_STATUS_RE = re.compile(
    r"\b(?:status|state)\b[^.?!]{0,70}\b(?:payment|deposit|funds)\b"
    r"|\b(?:payment|deposit|funds)\b[^.?!]{0,70}\b(?:status|state)\b"
)
_CHECK_STATUS_RE = re.compile(
    r"\b(?:status|state)\b\s+(?:of|for|on)\b[^.?!]{0,50}"
    r"\b(?:hilton|capital|client|customer|vendor|payer|payment|money|invoice)\b"
    r"[^.?!]{0,35}\b(?:check|cheque)\b"
    r"|\b(?:hilton|capital|client|customer|vendor|payer|payment|money|invoice)\b[^.?!]{0,60}"
    r"\b(?:check|cheque)\b[^.?!]{0,40}\b(?:status|state)\b"
)
_DID_CLIENT_PAY_RE = re.compile(
    r"\b(?:did|has|have)\b[^.?!]{0,80}\b(?:pay|paid)\b[^.?!]{0,30}\b(?:us|me)\b"
    r"|\b(?:are|were)\s+(?:we|you)\s+paid\b"
)
_NONFINANCIAL_CHECK_RE = re.compile(
    r"\b(?:background|health|deployment|system|smoke|integrity)\s+(?:check|cheque)\b"
)
_FINANCIAL_CHECK_CONTEXT_RE = re.compile(
    r"\b(?:payment|deposit|funds|money|invoice|remittance|bank|account)\b"
)
_INVOICE_ACTION_RE = re.compile(
    r"\b(create|generate|draft|write|make|prepare|send|upload|attach|fix|"
    r"updat(?:e|ed|ing)|set(?:ting)?|chang(?:e|ed|ing)|mark(?:ed|ing)?|"
    r"mov(?:e|ed|ing))\b[^.?!]{0,60}\b(?:invoice|bill)\b|"
    r"\b(?:invoice|bill)\b[^.?!]{0,60}\b(?:updat(?:e|ed|ing)|set(?:ting)?|"
    r"chang(?:e|ed|ing)|mark(?:ed|ing)?|mov(?:e|ed|ing))\b"
)
_INVOICE_STATUS_READ_RE = re.compile(
    r"\b(?:status|state)\b[^.?!]{0,90}\b(?:invoice|bill)\b|"
    r"\b(?:invoice|bill)\b[^.?!]{0,90}\b(?:status|state)\b"
)
_READ_MARKERS = (
    "who owes", "owes me", "owe me", "owes us", "owe us", "owed",
    "outstanding", "receivable", "receivables", "unpaid", "overdue",
    "money owed", "still owe", "invoice status", "status of the invoice",
    "been paid", "are we paid", "pay us", "paid us", "pay me yet", "paid me yet",
    "paid yet", "get paid for", "who still owes", "open invoices", "money picture",
)


def classify_money_question(text: str) -> str | None:
    """Classify a money-flavored message.

    Returns one of:
      "money_movement"        — active send/pay/transfer ask; ALWAYS defers to the
                                refusal/approval gates (141), never a ledger answer.
      "payment_arrival_verify"— genuine did-a-payment-arrive verification; the
                                payment_verify lane (with relevance threshold) owns it.
      "money_read"            — read-only money question; answer from the one truth.
      None                    — not a money-class message.
    """
    t = " ".join(str(text or "").lower().replace("-", " ").split())
    if not t:
        return None
    padded = f" {t} "
    if any(phrase in padded for phrase in _MOVEMENT_PHRASES):
        return "money_movement"
    if _AMOUNT_RE.search(t) and _MOVEMENT_VERB_RE.search(t):
        return "money_movement"
    if _MOVEMENT_MONEY_WORD_RE.search(t):
        return "money_movement"
    # Arrival morphology ("posting", "clearing") describes evidence only
    # when the financial subject is doing the arriving.  Requests/history in
    # which the operator is the actor ("can you post...", "did you clear...")
    # are mutation lanes, never payment-arrival verification.
    if (
        _PAYMENT_OPERATOR_ACTION_RE.search(t)
        and not _PAYMENT_EXTERNAL_ARRIVAL_ACTION_RE.search(t)
    ):
        return None
    question_shaped = bool("?" in str(text or "") or _ARRIVAL_QUESTION_RE.search(t))
    nonfinancial_check_only = bool(
        _NONFINANCIAL_CHECK_RE.search(t) and not _FINANCIAL_CHECK_CONTEXT_RE.search(t)
    )
    if question_shaped and (
        (
            _ARRIVAL_SUBJECT_RE.search(t)
            and _ARRIVAL_VERB_RE.search(t)
            and not nonfinancial_check_only
        )
        or _PAYMENT_STATUS_RE.search(t)
        or _CHECK_STATUS_RE.search(t)
        or _DID_CLIENT_PAY_RE.search(t)
    ):
        return "payment_arrival_verify"
    if _INVOICE_ACTION_RE.search(t):
        return None
    if question_shaped and _INVOICE_STATUS_READ_RE.search(t):
        return "money_read"
    if any(marker in t for marker in _READ_MARKERS):
        return "money_read"
    return None


def is_money_read_question(text: str) -> bool:
    return classify_money_question(text) == "money_read"


# ---------------------------------------------------------------------------
# Payment-evidence relevance threshold (kills the "newsletter verified" class)
# ---------------------------------------------------------------------------

_PAYMENT_SIGNAL_RE = re.compile(
    r"\b(payment|paid|deposit|check|remittance|zelle|venmo|wire|ach|invoice|sent you|funds)\b"
)


def _known_amount_strings(rows: Sequence[Mapping[str, Any]]) -> set[str]:
    amounts: set[str] = set()
    for row in rows:
        for field in ("open_minor_units", "paid_minor_units", "invoiced_minor_units"):
            value = row.get(field)
            if isinstance(value, int) and value > 0:
                major = value / 100
                if float(major).is_integer():
                    amounts.add(f"{int(major):,}")
                    amounts.add(str(int(major)))
                else:
                    amounts.add(f"{major:,.2f}")
    return amounts


def payment_evidence_correlates(
    question: str,
    *,
    sender: str = "",
    subject: str = "",
    snippet: str = "",
    payload: Mapping[str, Any] | None = None,
    extra_entity_terms: Iterable[str] = (),
) -> bool:
    """True only when a Gmail message actually correlates with the payment asked about.

    Threshold: the message must carry a payment signal AND line up with the client —
    either the entity named in the question appears in sender/subject/snippet, or
    (when the question names no entity) a known ledger client or exact ledger amount
    appears. A newsletter can never be a "verified match".
    """
    haystack = " ".join(part for part in (sender, subject, snippet) if part).lower()
    if not haystack:
        return False
    if not _PAYMENT_SIGNAL_RE.search(haystack):
        return False

    payload = payload if payload is not None else load_money_truth()
    rows = money_rows(payload)
    norm_hay = re.sub(r"[^a-z0-9$., ]+", " ", haystack.replace("'", ""))

    client_phrases: set[str] = set()
    for row in rows:
        client_phrases.update(_client_phrases(row))

    q = _norm_question(question)
    question_terms = {p for p in client_phrases if p in q}
    for term in extra_entity_terms:
        cleaned = re.sub(r"[^a-z0-9 ]+", "", str(term or "").lower().replace("'", "")).strip()
        if cleaned and cleaned in q:
            question_terms.add(cleaned)

    if question_terms:
        return any(term in norm_hay for term in question_terms)

    if any(phrase in norm_hay for phrase in client_phrases):
        return True
    amounts = _known_amount_strings(rows)
    return any(amount in norm_hay for amount in amounts)


__all__ = [
    "SCHEMA_VERSION",
    "AUTHORITY_SOURCE",
    "FINANCE_ANSWER_TOPIC",
    "DEFAULT_READ_MODEL_PATH",
    "NOT_TRACKED_LINE",
    "load_money_truth",
    "money_rows",
    "money_truth_as_of",
    "money_lines",
    "render_money_answer",
    "settled_row_proof_refs",
    "render_payment_verification_ledger",
    "route_line",
    "finance_answer_topic_fact",
    "classify_money_question",
    "is_money_read_question",
    "payment_evidence_correlates",
]
