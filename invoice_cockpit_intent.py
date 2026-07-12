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


_PRONOUN_ANTECEDENT_PATTERNS = (
    re.compile(
        r"(?:^|[;.!?]\s*)\s*(?:did|does|has|have|is|was|were)\s+"
        r"(?P<client>[^,;.!?\n]{1,80}?)\s+"
        r"(?:(?:pay|paid)(?:\s+(?:us|me))?|owe(?:d|s)?(?:\s+(?:us|me))?|"
        r"(?:payment|check|deposit)\s+"
        r"(?:arrive(?:d)?|clear(?:ed)?|land(?:ed)?|post(?:ed)?))"
        r"(?:\s+(?:yet|already|today|tonight))?"
        r"(?:\s*,?\s*(?:and\s+)?|\s*\?\s*)if\s+not\s*,?"
        r"(?:\s+(?:can|could|would)\s+you)?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:^|[;.!?]\s*)\s*(?:prepare|check|get|show|review)\s+"
        r"(?:me\s+)?(?:a\s+|the\s+)?(?:payment|balance)\s+status\s+"
        r"for\s+(?P<client>[^,;.!?\n]{1,60}?)"
        r"\s*,?\s*(?:and\s+)?then\s*$",
        re.IGNORECASE,
    ),
)


def _model_candidate_values(model: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        model.get("display_name"),
        model.get("client_display_name"),
        model.get("client_name"),
        model.get("client"),
        *_model_aliases(model),
        model.get("slug"),
        model.get("client_ref"),
    )


def _alias_occurs_as_tokens(text: str, candidate: Any) -> bool:
    tokens = re.findall(r"[a-z0-9]+", str(candidate or "").casefold().replace("&", " and "))
    if not tokens:
        return False
    pattern = r"(?<![a-z0-9])" + r"[^a-z0-9]+".join(
        re.escape(token) for token in tokens
    ) + r"(?![a-z0-9])"
    return re.search(pattern, str(text or "").casefold().replace("&", " and ")) is not None


def _registered_client_matches(
    text: str,
    client_models: Iterable[Mapping[str, Any]],
) -> dict[str, tuple[dict[str, Any], str]]:
    matches: dict[str, tuple[dict[str, Any], str]] = {}
    for raw_model in client_models:
        model = dict(raw_model)
        model_ref = normalize_client_ref(
            model.get("client_ref")
            or model.get("slug")
            or model.get("display_name")
            or model.get("client_display_name")
        )
        if not model_ref:
            continue
        for candidate in _model_candidate_values(model):
            if not _alias_occurs_as_tokens(text, candidate):
                continue
            previous = matches.get(model_ref)
            if previous is None or len(str(candidate)) > len(previous[1]):
                matches[model_ref] = (model, str(candidate))
    return matches


_PORTAL_OR_PO_RE = re.compile(
    r"(?<![a-z0-9])(?:coupa|portal|purchase\s+order|p\.?\s*o\.?)"
    r"(?![a-z0-9])",
    re.IGNORECASE,
)
_ARTIFACT_SELECTOR_RE = re.compile(
    r"(?<![a-z0-9])(?:latest|current|existing|issued)(?![a-z0-9])",
    re.IGNORECASE,
)


def _portal_or_po_implied(text: Any) -> bool:
    """Return true only for an affirmative portal/PO path qualifier."""

    value = re.sub(
        r"\b([a-z]+)n['’]t\b",
        r"\1 not",
        str(text or ""),
        flags=re.IGNORECASE,
    )
    matches = tuple(_PORTAL_OR_PO_RE.finditer(value))
    for match in matches:
        prefix = value[max(0, match.start() - 96) : match.start()]
        suffix = value[match.end() : match.end() + 64]
        if re.search(
            r"(?:\b(?:not|no|without|excluding|exclude|except|minus|avoid|"
            r"avoiding|skip|never|off|cannot|can't|won't|shouldn't|don't)\b|"
            r"\bdo\s+not\b|\brefus(?:e|ed|es|ing)(?:\s+to)?\b|"
            r"\b(?:instead\s+of|rather\s+than|anything\s+but|note\s+about)\b|"
            r"\b(?:whether|if|question|ask(?:ed|ing)?|decid(?:e|ed|ing)|"
            r"wonder(?:ed|ing)?|unsure|uncertain|maybe|perhaps|possibly|"
            r"possible|can|could|may|might|would|should|consider(?:ed|ing)?|"
            r"option(?:al)?)\b|"
            r"\b(?:can|could|should|would|will|do|does|did|are|were|have|has)"
            r"\s+(?:we|i|you)\b|\b(?:what|how)\s+about\b|"
            r"\b(?:is|are|was|were|do|does|did|can|could|should|would|will)"
            r"\s+(?:the\s+)?$|"
            r"\b(?:compar(?:e|ed|ing)\s+(?:against|with|to)|"
            r"comparison\s+(?:against|with|to))\b|\bnon[-\s]*)"
            r"[^,;.!?]{0,56}$",
            prefix,
            re.IGNORECASE,
        ):
            return False
        suffix_clause = re.split(r"[,;.!?]", suffix, maxsplit=1)[0]
        if re.search(
            r"(?:-\s*free\b|\b(?:not|no|never|isn't|wasn't|shouldn't|"
            r"excluded|disabled|avoided|forbidden|disallowed|off|without)\b)",
            suffix_clause,
            re.IGNORECASE,
        ):
            return False
    for match in matches:
        prefix = value[max(0, match.start() - 96) : match.start()]
        suffix = value[match.end() : match.end() + 64]
        direct_artifact_qualifier = re.match(
            r"\s*(?:invoice|bill|path|route|workflow)\b",
            suffix,
            re.IGNORECASE,
        )
        affirmative_route_phrase = re.search(
            r"\b(?:use|using|via|through|"
            r"(?:submit(?:ted|ting)?|upload(?:ed|ing)?|rout(?:e|ed|ing))"
            r"(?:\s+(?:(?:(?:the|this|that|my|our|your|their)\s+)?"
            r"(?:invoice|bill)|it))?"
            r"\s+(?:via|through|to))\s+(?:the\s+)?$",
            prefix,
            re.IGNORECASE,
        )
        affirmative_requirement = re.match(
            r"\s*(?:is\s+)?(?:required|needed|enabled|applicable)\b",
            suffix,
            re.IGNORECASE,
        )
        if direct_artifact_qualifier or affirmative_route_phrase or affirmative_requirement:
            return True
    return False


def _resolved_registered_model(
    model_ref: str,
    model: Mapping[str, Any],
    alias: str,
    requested_text: str,
) -> dict[str, Any]:
    resolved = dict(model)
    resolved["client_ref"] = model_ref
    resolved.setdefault(
        "display_name",
        resolved.get("client_display_name") or requested_text,
    )
    resolved["requested_client_text"] = requested_text
    resolved["matched_client_text"] = alias
    resolved["coupa_or_po_implied"] = _portal_or_po_implied(requested_text)
    return resolved


def _closed_owner_slot_identity(value: Any) -> str:
    """Remove only closed, non-identity invoice-slot modifiers."""

    identity = str(value or "").strip()
    identity = re.sub(r"^the\s+", "", identity, flags=re.IGNORECASE)
    identity = re.sub(
        r"^(?:a\s+)?copy\s+of\s+",
        "",
        identity,
        flags=re.IGNORECASE,
    )
    identity = _PORTAL_OR_PO_RE.sub(" ", identity)
    identity = re.sub(
        r"(?<![a-z0-9])-\s*free(?![a-z0-9])",
        " ",
        identity,
        flags=re.IGNORECASE,
    )
    identity = _ARTIFACT_SELECTOR_RE.sub(" ", identity)
    return " ".join(identity.split()).strip(" -,:;")


def _resolve_exact_client_alias(
    subject: str,
    client_models: Iterable[Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Resolve an antecedent only when its whole subject is one registry alias."""

    subject_without_modifiers = _closed_owner_slot_identity(subject)
    subject_without_possessive = re.sub(
        r"(?:['’]s)\s*$",
        "",
        subject_without_modifiers,
        flags=re.IGNORECASE,
    )
    subject_key = _client_match_key(subject_without_possessive)
    if not subject_key:
        return None
    matched: dict[str, tuple[dict[str, Any], str]] = {}
    for raw_model in client_models:
        model = dict(raw_model)
        for candidate in _model_candidate_values(model):
            if subject_key != _client_match_key(candidate):
                continue
            model_ref = normalize_client_ref(
                model.get("client_ref")
                or model.get("slug")
                or model.get("display_name")
                or model.get("client_display_name")
            )
            if model_ref:
                matched[model_ref] = (model, str(candidate))
    if len(matched) != 1:
        return None
    model_ref, (model, alias) = next(iter(matched.items()))
    return _resolved_registered_model(model_ref, model, alias, subject)


def _resolve_bounded_pronoun_antecedent(
    prior_text: str,
    client_models: Iterable[Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Resolve only a closed immediate-clause anaphora grammar.

    This intentionally rejects general discourse inference.  An older client
    mention, a nearer unknown client, an ambiguous comparison, or a lexical
    substring such as ``Hiltonian`` can never select a real invoice artifact.
    """

    for pattern in _PRONOUN_ANTECEDENT_PATTERNS:
        match = pattern.search(prior_text)
        if match is not None:
            return _resolve_exact_client_alias(match.group("client"), client_models)
    return None


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


def _unknown_client_models(text: str) -> tuple[dict[str, Any], ...]:
    """Return each explicit client slot in a direct review clause.

    A clause can put one identity before the artifact and another after it
    (``get the Alpha invoice for Beta ready``).  Returning every slot lets the
    authority classifier reject that collision instead of silently preferring
    whichever parser happened to run first.
    """

    verb = _STAGING_VERB
    patterns = (
        re.compile(
            rf"\b{verb}\b\s+(?:me\s+)?(?:the\s+|that\s+)?"
            rf"(.+?)\s+(?:invoice|bill)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:invoice|bill)\s+for\s+(.+?)(?:\s+and\b|\s+so\b|[?.!,]|$)",
            re.IGNORECASE,
        ),
    )
    models: list[dict[str, Any]] = []
    for pattern in patterns:
        for requested in pattern.finditer(text):
            client_text = requested.group(1).strip()
            client_text = re.sub(
                r"\s+(?:(?:ready|set\s+up|teed\s+up)\s+)?for\s+"
                r"(?:(?:me\s+to|my)\s+)?(?:review|look\s+over|once[-\s]?over)\s*$",
                "",
                client_text,
                flags=re.IGNORECASE,
            )
            # What remains between the staging verb and the artifact may be
            # only a determiner, month, or review cue ("get the July invoice
            # for review"). Those words are not a client identity.
            client_text = re.sub(
                rf"\b(?:the|that|this|a|an|their|its|his|her|final|finalized|ready|{('|'.join(_MONTH_NUMBERS))}|20\d{{2}})\b",
                " ",
                client_text,
                flags=re.IGNORECASE,
            )
            client_text = " ".join(client_text.split()).strip(" -,:;")
            requested_client_text = client_text
            client_text = _closed_owner_slot_identity(client_text)
            if not client_text or re.fullmatch(
                r"(?:for\s+)?(?:me\s+to\s+|my\s+)?"
                r"(?:review|look\s+(?:it\s+)?over|once[-\s]?over|"
                r"glance\s+at|eyeball)",
                client_text,
                re.IGNORECASE,
            ):
                continue
            models.append({
                "client_ref": normalize_client_ref(client_text),
                "display_name": client_text,
                "requested_client_text": requested_client_text,
                "matched_client_text": client_text,
            })
    return tuple(models)
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
    # The public API accepts one-shot iterables. Materialize once so direct
    # review resolution and bounded pronoun resolution see identical owners.
    owned_client_models = tuple(_iter_client_models(client_models))
    # P.O. is an invoice-slot qualifier, not two sentence boundaries.
    normalized = re.sub(
        r"(?<![a-z0-9])p\.\s*o\.(?![a-z0-9])",
        "PO",
        normalized,
        flags=re.IGNORECASE,
    )
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
    unknown_slots = _unknown_client_models(review_clause)
    explicit_registered: dict[str, dict[str, Any]] = {}
    unresolved_slots: list[dict[str, Any]] = []
    for slot in unknown_slots:
        resolved = _resolve_exact_client_alias(
            str(slot.get("requested_client_text") or slot.get("display_name") or ""),
            owned_client_models,
        )
        if resolved is None:
            unresolved_slots.append(slot)
            continue
        resolved_ref = normalize_client_ref(resolved.get("client_ref"))
        if resolved_ref:
            explicit_registered[resolved_ref] = resolved
    unresolved_slot_keys = {
        _client_match_key(slot.get("display_name"))
        for slot in unresolved_slots
        if _client_match_key(slot.get("display_name"))
    }
    if len(explicit_registered) > 1:
        return FinalizedInvoiceReviewDecision(matched=False)

    # A registered name used as a comparison, template, exclusion, or other
    # modifier is not an owner slot. Never let an alias merely occurring
    # somewhere in the review clause establish artifact authority.
    all_clause_registered = _registered_client_matches(
        review_clause,
        owned_client_models,
    )
    incidental_registered_refs = set(all_clause_registered).difference(
        explicit_registered
    )
    if incidental_registered_refs:
        return FinalizedInvoiceReviewDecision(matched=False)

    possessive_review = re.search(
        rf"\b(?P<pronoun>their|its|his|her)\b[^;.!?\n]{{0,40}}\b{_ARTIFACT_NOUN}\b",
        review_clause,
        re.IGNORECASE,
    )
    client_model = None
    if possessive_review is not None:
        if unresolved_slot_keys:
            return FinalizedInvoiceReviewDecision(matched=False)
        # ``_bound_review_clause`` returns a suffix of the regex match. Use its
        # absolute start, not the over-wide match start, to retain the immediate
        # governing clause while excluding older sentences.
        review_clause_start = review_match.end() - len(review_clause)
        if possessive_review.group("pronoun").casefold() in {"their", "its"}:
            client_model = _resolve_bounded_pronoun_antecedent(
                normalized[:review_clause_start],
                owned_client_models,
            )
        if client_model is None:
            return FinalizedInvoiceReviewDecision(matched=False)
        if explicit_registered and normalize_client_ref(
            client_model.get("client_ref")
        ) not in explicit_registered:
            return FinalizedInvoiceReviewDecision(matched=False)
    elif explicit_registered:
        if unresolved_slot_keys:
            return FinalizedInvoiceReviewDecision(matched=False)
        client_model = next(iter(explicit_registered.values()))
    else:
        if len(unresolved_slot_keys) != 1:
            return FinalizedInvoiceReviewDecision(matched=False)
        client_model = unresolved_slots[0]
    if client_model is None:
        return FinalizedInvoiceReviewDecision(matched=False)

    owned_model = dict(client_model)
    owned_model["coupa_or_po_implied"] = _portal_or_po_implied(review_clause)
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
