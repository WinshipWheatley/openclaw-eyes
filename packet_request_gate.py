"""Safety gate for LM packet renegotiation requests.

The gate is deliberately pure and read-only: it validates a bounded structured
request against an allowlisted catalog, PII tier, known entity, and hard-deny
control list before returning a fetcher. The fetcher only copies grounded facts
from an injected source mapping and never writes or executes actions.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Any


MAX_REQUESTS = 3
FACTS_PER_FETCH_CAP = 8

_PII_TIER_RANK = {
    "PUBLIC": 0,
    "LIGHT": 1,
    "MED": 2,
    "MEDIUM": 2,
    "MAX": 3,
}

_HARD_DENY_TERMS = (
    "send_approval",
    "sendapproval",
    "send_hold_override",
    "sendholdoverride",
    "send hold override",
    "legal_body",
    "legalbody",
    "legal discovery body",
    "credential",
    "credentials",
    "secret",
    "secrets",
    "token",
    "tokens",
    "money_move_authority",
    "moneymoveauthority",
    "money movement authority",
    "move funds",
    "send hold bypass",
    "gate bypass",
    "bypass gate",
    "write authority",
    "write_access",
    "writable",
)

_CONTROLISH_CATALOG_NEEDS = frozenset(
    {
        "send_approval",
        "send_hold_override",
        "legal_body",
        "credentials",
        "secrets",
        "money_move_authority",
    }
)

_ACTION_KEYS = frozenset(
    {
        "action",
        "approval",
        "authority",
        "credential",
        "execute",
        "money_move",
        "secret",
        "send",
        "token",
        "write",
    }
)


@dataclass(frozen=True)
class CatalogEntry:
    need: str
    max_pii_tier: str
    source_key: str
    description: str


BOUNDED_CATALOG: dict[str, CatalogEntry] = {
    "invoice_records": CatalogEntry(
        need="invoice_records",
        max_pii_tier="LIGHT",
        source_key="invoice_records",
        description="Derived workbook invoice records with source provenance.",
    ),
    "client_model": CatalogEntry(
        need="client_model",
        max_pii_tier="PUBLIC",
        source_key="client_model",
        description="Registry client routing/workflow model.",
    ),
    "payment_status": CatalogEntry(
        need="payment_status",
        max_pii_tier="LIGHT",
        source_key="payment_status",
        description="Bank-backed payment/reconciliation status metadata.",
    ),
    "receivables": CatalogEntry(
        need="receivables",
        max_pii_tier="LIGHT",
        source_key="receivables",
        description="Expected receivable records and statuses.",
    ),
    "gigs": CatalogEntry(
        need="gigs",
        max_pii_tier="LIGHT",
        source_key="gigs",
        description="Gig/work-session metadata.",
    ),
    "calendar_read": CatalogEntry(
        need="calendar_read",
        max_pii_tier="MED",
        source_key="calendar_read",
        description="Read-only calendar context metadata.",
    ),
    "contact_nonpii": CatalogEntry(
        need="contact_nonpii",
        max_pii_tier="PUBLIC",
        source_key="contact_nonpii",
        description="Non-PII contact policy and routing metadata.",
    ),
    "ledger_fact_by_topic": CatalogEntry(
        need="ledger_fact_by_topic",
        max_pii_tier="PUBLIC",
        source_key="ledger_fact_by_topic",
        description="Grounded ledger/canonical fact lookup by topic.",
    ),
}


def _deny(reason: str, *, need: str = "", entity: str = "") -> dict[str, Any]:
    return {
        "allowed": False,
        "reason": reason,
        "need": need,
        "entity": entity,
        "fetch": None,
        "writes_performed": False,
    }


def _allow(
    *,
    need: str,
    entity: str,
    reason: str,
    pii_tier: str,
    fetch: Callable[[], list[dict[str, Any]]],
) -> dict[str, Any]:
    return {
        "allowed": True,
        "reason": reason,
        "need": need,
        "entity": entity,
        "pii_tier": pii_tier,
        "fetch": fetch,
        "writes_performed": False,
    }


def _normalize_need(value: Any) -> str:
    text = str(value or "").strip().casefold()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _entity_key(value: Any) -> str:
    text = str(value or "").strip().casefold().replace("&", "and")
    return re.sub(r"[^a-z0-9]", "", text)


def _tier_name(value: Any, *, access_level: bool = False) -> str:
    tier = str(value or "").strip().upper()
    if tier == "MEDIUM":
        tier = "MED"
    if tier in _PII_TIER_RANK:
        return tier
    return "PUBLIC" if access_level else "MAX"


def _tier_rank(value: Any, *, access_level: bool = False) -> int:
    return _PII_TIER_RANK[_tier_name(value, access_level=access_level)]


def _combined_request_text(req: Mapping[str, Any]) -> str:
    return " ".join(str(req.get(key) or "") for key in ("need", "entity", "reason")).casefold()


def _compact_request_text(req: Mapping[str, Any]) -> str:
    return re.sub(r"[^a-z0-9]", "", _combined_request_text(req))


def _hard_deny_reason(req: Mapping[str, Any], need: str) -> str | None:
    if need in _CONTROLISH_CATALOG_NEEDS:
        return f"hard-denied control/bypass request: {need}"
    text = _combined_request_text(req)
    compact = _compact_request_text(req)
    for term in _HARD_DENY_TERMS:
        term_text = term.casefold()
        term_compact = re.sub(r"[^a-z0-9]", "", term_text)
        if term_text in text or (term_compact and term_compact in compact):
            return f"hard-denied control/bypass request: {term}"
    return None


def _bucket_for(entry: CatalogEntry, source: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(source, Mapping):
        return {}
    bucket = source.get(entry.source_key)
    return bucket if isinstance(bucket, Mapping) else {}


def _lookup_entity(bucket: Mapping[str, Any], entity: str) -> tuple[str, Any] | None:
    if entity in bucket:
        return entity, bucket[entity]
    wanted = _entity_key(entity)
    for key, value in bucket.items():
        if _entity_key(key) == wanted:
            return str(key), value
    return None


def _raw_records(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [item for item in value if isinstance(item, Mapping)]
    return []


def _record_tier(raw: Mapping[str, Any], entry: CatalogEntry) -> str:
    return _tier_name(raw.get("pii_tier") or entry.max_pii_tier)


def _max_entity_tier(value: Any, entry: CatalogEntry) -> str:
    records = _raw_records(value)
    if not records:
        return "MAX"
    highest = max(_tier_rank(_record_tier(record, entry)) for record in records)
    for tier, rank in _PII_TIER_RANK.items():
        if rank == highest and tier != "MEDIUM":
            return tier
    return "MAX"


def _normalize_fact(
    raw: Mapping[str, Any],
    *,
    need: str,
    entity: str,
    entry: CatalogEntry,
) -> dict[str, Any]:
    fact = {
        key: value
        for key, value in dict(raw).items()
        if key not in _ACTION_KEYS
    }
    fact.setdefault("label", f"{need}:{entity}")
    fact.setdefault("value", "")
    fact.setdefault("source_ref", f"catalog://{need}/{entity}")
    fact.setdefault("pii_tier", _record_tier(raw, entry))
    fact.setdefault("provenance", "grounded_catalog")
    fact["need"] = need
    fact["entity"] = entity
    fact["source_ref"] = str(fact.get("source_ref") or f"catalog://{need}/{entity}")
    fact["pii_tier"] = _tier_name(fact.get("pii_tier"))
    fact["provenance"] = str(fact.get("provenance") or "grounded_catalog")
    return fact


def _build_fetcher(
    *,
    need: str,
    entity: str,
    entry: CatalogEntry,
    value: Any,
) -> Callable[[], list[dict[str, Any]]]:
    records = tuple(dict(record) for record in _raw_records(value)[:FACTS_PER_FETCH_CAP])

    def fetch() -> list[dict[str, Any]]:
        return [
            _normalize_fact(record, need=need, entity=entity, entry=entry)
            for record in records
        ]

    return fetch


def validate_request(
    req: Mapping[str, Any],
    *,
    caller_pii_tier: str,
    source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one LM packet request and return a read-only fetcher when safe."""
    if not isinstance(req, Mapping):
        return _deny("request must be a mapping")

    need = _normalize_need(req.get("need"))
    entity = str(req.get("entity") or "").strip()
    reason_text = str(req.get("reason") or "").strip()
    if not need or not entity or not reason_text:
        return _deny("request schema requires non-empty need, entity, and reason", need=need, entity=entity)

    hard = _hard_deny_reason(req, need)
    if hard:
        return _deny(hard, need=need, entity=entity)

    entry = BOUNDED_CATALOG.get(need)
    if entry is None:
        return _deny(f"need {need!r} is not in grounded catalog", need=need, entity=entity)

    caller_rank = _tier_rank(caller_pii_tier, access_level=True)
    catalog_rank = _tier_rank(entry.max_pii_tier)
    if catalog_rank > caller_rank:
        return _deny(
            f"PII tier denied: {need} requires {entry.max_pii_tier}, caller allows {_tier_name(caller_pii_tier, access_level=True)}",
            need=need,
            entity=entity,
        )

    bucket = _bucket_for(entry, source)
    lookup = _lookup_entity(bucket, entity)
    if lookup is None:
        return _deny(f"unknown entity for {need}: {entity}", need=need, entity=entity)

    resolved_entity, value = lookup
    entity_tier = _max_entity_tier(value, entry)
    if _tier_rank(entity_tier) > caller_rank:
        return _deny(
            f"PII tier denied: entity {resolved_entity} is {entity_tier}, caller allows {_tier_name(caller_pii_tier, access_level=True)}",
            need=need,
            entity=resolved_entity,
        )

    return _allow(
        need=need,
        entity=resolved_entity,
        reason="allowed grounded catalog request",
        pii_tier=entity_tier,
        fetch=_build_fetcher(need=need, entity=resolved_entity, entry=entry, value=value),
    )


def validate_requests(
    reqs: Sequence[Mapping[str, Any]],
    *,
    caller_pii_tier: str,
    source: Mapping[str, Any] | None = None,
    max_requests: int = MAX_REQUESTS,
) -> list[dict[str, Any]]:
    """Validate a bounded list of LM packet requests, denying excess entries."""
    results: list[dict[str, Any]] = []
    for index, req in enumerate(reqs):
        need = _normalize_need(req.get("need")) if isinstance(req, Mapping) else ""
        entity = str(req.get("entity") or "").strip() if isinstance(req, Mapping) else ""
        if index >= max_requests:
            results.append(_deny("request cap exceeded", need=need, entity=entity))
            continue
        results.append(validate_request(req, caller_pii_tier=caller_pii_tier, source=source))
    return results


__all__ = [
    "BOUNDED_CATALOG",
    "CatalogEntry",
    "FACTS_PER_FETCH_CAP",
    "MAX_REQUESTS",
    "validate_request",
    "validate_requests",
]
