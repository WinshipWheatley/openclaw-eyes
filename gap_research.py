"""Fill a packet's knowledge gap from the web, and extract the nectar.

When a doer's packet does not cover its target, the honest fallback is to say
so — but the better move, when the gap is a plain unknown TERM ("what is
TH-U?"), is to go and learn it. This does that, then hands back ONE
concentrated, sourced fact.

Two rules this module exists to enforce:

**Only the unknown term is searched — never the assignment.** An assignment
can carry client names, amounts, addresses and private context. The query is
built from the specific unknown term alone, and terms that look personal or
financial are never searched at all.

**What is learned is labelled.** The returned fact carries
``provenance="web_lookup"``, the source URL and a retrieval timestamp. It is
outside knowledge with a receipt, never blended in as if it were the
operator's own data.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

# A term is only searchable if it looks like a product/technical name.
_PRIVATE_PATTERNS = (
    re.compile(r"@"),                      # any address-like token
    re.compile(r"^\d[\d,._-]*$"),          # bare numbers / amounts
    re.compile(r"^\$"),                    # money
    re.compile(r"\d{3,}"),                 # long digit runs (ids, invoices, phones)
)
# Never search these even if they show up as "unknown".
_PRIVATE_TERMS = frozenset(
    """winship winshiplive megan rivas draper glen glenn nancy hilton lamd
    stannes invoice receivable payment bank account routing ssn address phone""".split()
)

NECTAR_CHARS = 400
MAX_TERMS = 2


def _is_searchable(term: str) -> bool:
    token = str(term or "").strip().lower()
    if len(token) < 2 or token in _PRIVATE_TERMS:
        return False
    return not any(pattern.search(token) for pattern in _PRIVATE_PATTERNS)


def _default_search(query: str, max_results: int = 4) -> list[dict[str, Any]]:
    from chief_scout_brain import _web_search

    return _web_search(query, max_results=max_results)


def _nectar(results: Iterable[dict[str, Any]], term: str) -> tuple[str, str]:
    """Concentrate results into the useful sentence(s) plus their source."""

    best_text, best_url, best_score = "", "", -1
    for row in results:
        body = " ".join(str(row.get("body") or "").split())
        title = " ".join(str(row.get("title") or "").split())
        url = str(row.get("url") or "")
        if not body and not title:
            continue
        blob = f"{title}. {body}".strip()
        # Prefer a result that actually defines the term.
        score = blob.lower().count(term.lower()) + (2 if " is " in blob.lower() else 0)
        if score > best_score:
            best_text, best_url, best_score = blob, url, score
    return best_text[:NECTAR_CHARS], best_url


def research_gap(
    *,
    target: str,
    uncovered_terms: Iterable[str],
    search: Callable[..., list[dict[str, Any]]] | None = None,
) -> dict[str, Any] | None:
    """Look up the unknown term and return one sourced fact, or ``None``.

    ``None`` means the gap stands — the caller reports it honestly rather than
    letting anything be invented.
    """

    terms = [t for t in dict.fromkeys(uncovered_terms) if _is_searchable(t)][:MAX_TERMS]
    if not terms:
        return None

    caller = search or _default_search
    term = terms[0]
    # The query is the TERM, not the assignment. Never interpolate ``target``.
    query = f"what is {term}"
    try:
        results = caller(query, max_results=4)
    except Exception:
        return None
    if not results:
        return None

    value, url = _nectar(results, term)
    if not value:
        return None

    return {
        "fact_id": f"web_lookup:{term}",
        "topic": "web_lookup",
        "label": f"Looked up: {term}",
        "value": value,
        "provenance": "web_lookup",
        "source_ref": url or f"web_search:{query}",
        "pii_tier": "PUBLIC",
        "freshness": {
            "retrieved_at": datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        },
    }
