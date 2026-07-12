"""Dependency-light owner for finalized-invoice review intent.

This module is deliberately safe for first-touch classifiers to import: it
uses only the standard library and the static invoice cockpit client registry.
The stateful cockpit consumes the structured decision; other classifiers may
consume ``matched`` without importing the cockpit's executor, workflow, or
model interpreter.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from invoice_cockpit_client_registry import DEFAULT_CLIENT_MODELS


_STAGING_VERB = (
    r"(?:prep(?:ping)?|prepar(?:e|ing)|get(?:ting)?|hav(?:e|ing)|mak(?:e|ing)|"
    r"set(?:ting)?\s+up|surface|pull\s+up|show|line\s+up)"
)
_ARTIFACT_NOUN = r"(?:invoice|bill)"
_REVIEW_CUE = (
    r"(?:\bready\b|\bteed\s+up\b|\bfor\s+(?:me\s+to\s+|my\s+)?review\b|"
    r"\blook\s+(?:it\s+)?over\b|\beyeball\b|\bglance\s+at\b|"
    r"\bonce[-\s]?over\b|\bfinal(?:ized)?\b|"
    r"\breview\s+(?:the\s+)?(?:final(?:ized)?\s+)?(?:copy|invoice|bill)\b)"
)
_FINALIZED_REVIEW_CLAUSE_RE = re.compile(
    rf"(?:"
    rf"\b{_STAGING_VERB}\b[^;.!?\n]{{0,120}}\b{_ARTIFACT_NOUN}\b"
    rf"[^;.!?\n]{{0,120}}{_REVIEW_CUE}"
    rf"|"
    rf"\b{_STAGING_VERB}\b[^;.!?\n]{{0,60}}\bfinal(?:ized)?\b"
    rf"[^;.!?\n]{{0,80}}\b{_ARTIFACT_NOUN}\b"
    rf")",
    re.IGNORECASE,
)

_MONTH_NUMBERS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


@dataclass(frozen=True)
class FinalizedInvoiceReviewDecision:
    """The cockpit-owned interpretation of an existing-artifact review ask."""

    matched: bool
    client_ref: str | None = None
    requested_period: str | None = None
    client_model: Mapping[str, Any] | None = None


def normalize_client_ref(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").casefold()).strip("_")


def _client_match_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold().replace("&", "and"))


def _model_aliases(model: Mapping[str, Any]) -> tuple[Any, ...]:
    aliases = model.get("aliases") or model.get("alias") or ()
    if isinstance(aliases, str):
        return (aliases,)
    if isinstance(aliases, Iterable):
        return tuple(aliases)
    return ()


def _iter_client_models(
    client_models: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]] | None,
) -> Iterable[dict[str, Any]]:
    if client_models is None:
        yield from (dict(model) for model in DEFAULT_CLIENT_MODELS)
        return
    if isinstance(client_models, Mapping):
        for key, model in client_models.items():
            merged = dict(model)
            merged.setdefault("client_ref", str(key))
            merged["client_ref"] = normalize_client_ref(merged.get("client_ref"))
            merged.setdefault(
                "display_name",
                merged.get("client_display_name") or merged.get("client_name"),
            )
            yield merged
        return
    for model in client_models:
        merged = dict(model)
        if "client_ref" in merged:
            merged["client_ref"] = normalize_client_ref(merged.get("client_ref"))
        merged.setdefault(
            "display_name",
            merged.get("client_display_name") or merged.get("client_name"),
        )
        yield merged


def resolve_client_model(
    requested_client: str,
    client_models: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Resolve the longest registered alias contained in ``requested_client``."""

    requested_key = _client_match_key(requested_client)
    if not requested_key:
        return None
    best: dict[str, Any] | None = None
    best_alias = ""
    best_len = -1
    for model in _iter_client_models(client_models):
        candidates = [
            model.get("display_name"),
            model.get("client_display_name"),
            model.get("client_name"),
            model.get("client"),
            *_model_aliases(model),
            model.get("slug"),
            model.get("client_ref"),
        ]
        for candidate in candidates:
            candidate_key = _client_match_key(candidate)
            if not candidate_key:
                continue
            if requested_key == candidate_key or candidate_key in requested_key:
                if len(candidate_key) > best_len:
                    best = model
                    best_len = len(candidate_key)
                    best_alias = str(candidate)
    if best is None:
        return None
    resolved = dict(best)
    if "client_ref" in resolved:
        resolved["client_ref"] = normalize_client_ref(resolved.get("client_ref"))
    resolved.setdefault("display_name", resolved.get("client_display_name") or requested_client)
    resolved["requested_client_text"] = requested_client
    resolved["matched_client_text"] = best_alias
    resolved["coupa_or_po_implied"] = bool(
        re.search(
            r"\b(coupa|p\.?o\.?|po|purchase\s+order|portal)\b",
            requested_client,
            re.IGNORECASE,
        )
    )
    return resolved


def _requested_invoice_period(
    text: str,
    *,
    reference_year: int | None = None,
) -> str | None:
    normalized = str(text or "").casefold()
    months = "|".join(_MONTH_NUMBERS)
    month_pattern = re.compile(
        rf"\b(?P<month>{months})\b(?:\s+(?P<year>20\d{{2}}))?",
        re.IGNORECASE,
    )
    month_match = None
    # Bind a leading month to the staging clause containing the artifact. This
    # accepts "July St Anne's invoice" while excluding an earlier payment
    # clause such as "compare May payment, then get the invoice ready".
    for artifact in re.finditer(r"\b(?:invoice|bill)\b", normalized):
        prefix = normalized[: artifact.start()]
        staging = tuple(re.finditer(rf"\b{_STAGING_VERB}\b", prefix, re.IGNORECASE))
        clause_start = staging[-1].start() if staging else max(
            prefix.rfind(";"),
            prefix.rfind("."),
            prefix.rfind("!"),
            prefix.rfind("?"),
        ) + 1
        candidates = tuple(month_pattern.finditer(normalized[clause_start : artifact.start()]))
        if candidates:
            month_match = candidates[-1]
            break
        suffix_match = re.match(
            rf"[^;.!?\n]{{0,30}}\b(?:for\s+)?(?P<month>{months})\b"
            rf"(?:\s+(?P<year>20\d{{2}}))?",
            normalized[artifact.end() :],
            re.IGNORECASE,
        )
        if suffix_match is not None:
            month_match = suffix_match
            break
    if month_match is None:
        return None
    year = (
        int(month_match.group("year"))
        if month_match.group("year")
        else int(reference_year if reference_year is not None else date.today().year)
    )
    return f"{year:04d}-{_MONTH_NUMBERS[month_match.group('month')]:02d}"


def _unknown_client_model(text: str) -> dict[str, Any] | None:
    verb = r"(?:prep|prepare|get|make|have|set\s+up|surface|pull\s+up|show|line\s+up)"
    before_artifact = re.search(
        rf"\b{verb}\b\s+(?:the\s+|that\s+)?(.+?)\s+(?:invoice|bill)\b",
        text,
        re.IGNORECASE,
    )
    after_artifact = re.search(
        r"\b(?:invoice|bill)\s+for\s+(.+?)(?:\s+and\b|\s+so\b|[?.!,]|$)",
        text,
        re.IGNORECASE,
    )
    requested = before_artifact or after_artifact
    if requested is None:
        return None
    client_text = requested.group(1).strip()
    client_text = re.sub(
        r"\s+(?:(?:ready|set\s+up|teed\s+up)\s+)?for\s+"
        r"(?:(?:me\s+to|my)\s+)?(?:review|look\s+over|once[-\s]?over)\s*$",
        "",
        client_text,
        flags=re.IGNORECASE,
    )
    # What remains between the staging verb and the artifact may be only a
    # determiner, month, or review cue ("get the July invoice for review").
    # Those words are not a client identity and must not manufacture a client
    # called "review" or "July".
    client_text = re.sub(
        rf"\b(?:the|that|this|a|an|final|finalized|ready|{('|'.join(_MONTH_NUMBERS))}|20\d{{2}})\b",
        " ",
        client_text,
        flags=re.IGNORECASE,
    )
    client_text = " ".join(client_text.split()).strip(" -,:;")
    if not client_text or re.fullmatch(
        r"(?:for\s+)?(?:me\s+to\s+|my\s+)?(?:review|look\s+over|once[-\s]?over)",
        client_text,
        re.IGNORECASE,
    ):
        return None
    return {
        "client_ref": normalize_client_ref(client_text),
        "display_name": client_text,
        "requested_client_text": client_text,
        "matched_client_text": client_text,
    }


def _bound_review_clause(match: re.Match[str]) -> str:
    """Trim an over-wide regex match to the staging verb for its last artifact."""

    clause = match.group(0)
    artifacts = tuple(re.finditer(rf"\b{_ARTIFACT_NOUN}\b", clause, re.IGNORECASE))
    if not artifacts:
        return clause
    artifact = artifacts[-1]
    staging = tuple(
        re.finditer(rf"\b{_STAGING_VERB}\b", clause[: artifact.start()], re.IGNORECASE)
    )
    return clause[staging[-1].start() :] if staging else clause


def classify_finalized_invoice_review(
    text: str,
    *,
    client_models: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]] | None = None,
    reference_year: int | None = None,
) -> FinalizedInvoiceReviewDecision:
    """Classify a bounded request to surface an existing finalized invoice."""

    normalized = str(text or "").replace("’", "'")
    # ``St. Anne's`` contains punctuation but is one registry alias, not a
    # clause boundary for the review matcher.
    normalized = re.sub(r"\bSt\.(?=\s+[A-Z])", "St", normalized, flags=re.IGNORECASE)
    review_match = _FINALIZED_REVIEW_CLAUSE_RE.search(normalized)
    if review_match is None:
        return FinalizedInvoiceReviewDecision(matched=False)

    # Only identities and periods inside the clause that actually established
    # finalized-review intent may bind this decision.  An earlier payment or
    # status clause can mention a different client without stealing the ask.
    review_clause = _bound_review_clause(review_match)
    client_model = resolve_client_model(review_clause, client_models)
    if client_model is None:
        client_model = _unknown_client_model(review_clause)
    if client_model is None:
        return FinalizedInvoiceReviewDecision(matched=False)

    owned_model = dict(client_model)
    client_ref = normalize_client_ref(
        owned_model.get("client_ref") or owned_model.get("display_name")
    )
    if client_ref:
        owned_model["client_ref"] = client_ref
    return FinalizedInvoiceReviewDecision(
        matched=True,
        client_ref=client_ref or None,
        requested_period=_requested_invoice_period(
            review_clause,
            reference_year=reference_year,
        ),
        client_model=owned_model,
    )


__all__ = [
    "FinalizedInvoiceReviewDecision",
    "classify_finalized_invoice_review",
    "normalize_client_ref",
    "resolve_client_model",
]
