"""Canonical gig-business doctrine loading, freshness, ingest, and packet delivery."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from markdown_it import MarkdownIt

from canonical_fact_ingest import ingest_graded_fact


ROOT = Path(__file__).resolve().parent
DOCTRINE_PATH = ROOT / "docs/doctrine/GIG_BUSINESS_DOCTRINE.md"
CANONICAL_PATH = "docs/doctrine/GIG_BUSINESS_DOCTRINE.md"
CONTRACT_START = "<!-- BEGIN GIG_BUSINESS_DOCTRINE_CONTRACT -->"
CONTRACT_END = "<!-- END GIG_BUSINESS_DOCTRINE_CONTRACT -->"
SCHEMA_VERSION = "gig_business_doctrine_contract_v1_2"
DOCTRINE_REF = "gig_business_doctrine:v1.2"
FRESHNESS_CLASS = "NEVER_STALE"
PRICING_LOGISTICS_SOURCE_POLICY = "ONLY"

_FREEFORM_CLASSIFIERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("gig_pricing", ("price", "pricing", "rate", "quote", "cost", "fee", "payout")),
    ("email_watch", ("follow-up", "follow up", "reply", "client email", "outreach")),
    ("gig_logistics", ("travel", "venue", "flight", "gear", "safety", "roadie", "drink")),
    ("gig_intake", ("gig", "booking", "wedding", "live event", "band")),
)
_LEDGER_ACTORS = {"maestro", "chief", "cassandra", "niles", "guardian", "hermes"}


def _source_sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _contract_json(text: str) -> str:
    if CONTRACT_START not in text or CONTRACT_END not in text:
        raise ValueError("Gig business doctrine is missing contract boundaries")
    bounded = text.split(CONTRACT_START, 1)[1].split(CONTRACT_END, 1)[0].strip()
    match = re.fullmatch(r"```json\s*(\{.*\})\s*```", bounded, flags=re.DOTALL)
    if match is None:
        raise ValueError("Gig business doctrine contract must be one JSON code block")
    return match.group(1)


def _h2_titles(text: str) -> set[str]:
    tokens = MarkdownIt("commonmark").parse(text)
    titles: set[str] = set()
    for index, token in enumerate(tokens[:-1]):
        if token.type == "heading_open" and token.tag == "h2":
            inline = tokens[index + 1]
            if inline.type == "inline":
                titles.add(str(inline.content).strip())
    return titles


def load_gig_business_doctrine(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path is not None else DOCTRINE_PATH
    text = target.read_text(encoding="utf-8")
    payload = json.loads(_contract_json(text))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unexpected gig business doctrine schema version")
    if payload.get("doctrine_ref") != DOCTRINE_REF:
        raise ValueError("Unexpected gig business doctrine reference")
    if payload.get("pricing_logistics_source_policy") != PRICING_LOGISTICS_SOURCE_POLICY:
        raise ValueError("Gig business doctrine must be the only pricing/logistics source")
    freshness = dict(payload.get("freshness") or {})
    if freshness.get("class") != FRESHNESS_CLASS or freshness.get("stale_on_age") is not False:
        raise ValueError("Gig business doctrine freshness contract is incomplete")
    titles = _h2_titles(text)
    sections = [dict(section) for section in payload.get("sections", ())]
    if not sections or any(str(section.get("title") or "") not in titles for section in sections):
        raise ValueError("Gig business doctrine section contract does not match Markdown headings")
    payload["sections"] = sections
    payload["canonical_path"] = CANONICAL_PATH
    payload["source_sha256"] = _source_sha256(target)
    return payload


def build_freshness_registration(
    path: str | Path | None = None,
    *,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    target = Path(path) if path is not None else DOCTRINE_PATH
    if not target.exists():
        return {
            "doctrine_ref": DOCTRINE_REF,
            "canonical_path": CANONICAL_PATH,
            "freshness_class": FRESHNESS_CLASS,
            "status": "STALE_MISSING",
            "age_seconds": None,
            "max_age_seconds": None,
            "stale_on_age": False,
            "source_sha256": "",
        }
    source_sha256 = _source_sha256(target)
    age_seconds = max(
        0,
        int(datetime.now(timezone.utc).timestamp() - target.stat().st_mtime),
    )
    status = (
        "STALE_HASH_DRIFT"
        if expected_sha256 and expected_sha256 != source_sha256
        else "CURRENT"
    )
    return {
        "doctrine_ref": DOCTRINE_REF,
        "canonical_path": CANONICAL_PATH,
        "freshness_class": FRESHNESS_CLASS,
        "status": status,
        "age_seconds": age_seconds,
        "max_age_seconds": None,
        "stale_on_age": False,
        "drift_on_hash_change": True,
        "missing_is_stale": True,
        "source_sha256": source_sha256,
    }


def _effective_question_class(question_class: str, question: str) -> str:
    normalized = str(question_class or "").strip().lower()
    if normalized and normalized != "frontdoor_freeform":
        return normalized
    lowered = str(question or "").casefold()
    for candidate, terms in _FREEFORM_CLASSIFIERS:
        if any(term in lowered for term in terms):
            return candidate
    return ""


def _short_hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:20]


def build_doctrine_delivery(
    *,
    agent_id: str,
    question_class: str = "",
    question: str = "",
    path: str | Path | None = None,
) -> dict[str, Any]:
    agent = str(agent_id or "").strip().lower()
    effective_class = _effective_question_class(question_class, question)
    if not effective_class:
        return {
            "status": "NOT_RELEVANT",
            "agent_id": agent,
            "question_class": effective_class,
            "sections": [],
            "packet_text": "",
        }
    target = Path(path) if path is not None else DOCTRINE_PATH
    freshness = build_freshness_registration(target)
    if freshness["status"] != "CURRENT":
        return {
            "status": freshness["status"],
            "doctrine_ref": DOCTRINE_REF,
            "canonical_path": CANONICAL_PATH,
            "source_sha256": str(freshness.get("source_sha256") or ""),
            "source_ref": "",
            "freshness": freshness,
            "pricing_logistics_source_policy": PRICING_LOGISTICS_SOURCE_POLICY,
            "agent_id": agent,
            "question_class": effective_class,
            "sections": [],
            "packet_text": (
                "GIG BUSINESS DOCTRINE UNAVAILABLE: DO NOT PROVIDE OR ACT ON "
                "PRICING/LOGISTICS FROM ANY ALTERNATE SOURCE."
            ),
            "receipt": {
                "schema_version": "gig_business_doctrine_delivery_receipt_v1",
                "receipt_id": f"gig_doctrine_delivery:{_short_hash(freshness)}",
                "status": freshness["status"],
                "source_sha256": str(freshness.get("source_sha256") or ""),
                "freshness_class": FRESHNESS_CLASS,
                "pricing_logistics_source_policy": PRICING_LOGISTICS_SOURCE_POLICY,
                "section_ids": [],
            },
        }
    contract = load_gig_business_doctrine(target)
    selected = []
    source_ref = f"{contract['canonical_path']}#{contract['source_sha256']}"
    for section in contract["sections"]:
        consumers = {str(value).lower() for value in section.get("consumers", ())}
        question_classes = {
            str(value).lower() for value in section.get("question_classes", ())
        }
        if agent not in consumers or effective_class not in question_classes:
            continue
        selected.append(
            {
                "section_id": str(section["section_id"]),
                "title": str(section["title"]),
                "text": str(section["packet_summary"]),
                "source_ref": source_ref,
            }
        )
    if not selected:
        return {
            "status": "NOT_RELEVANT",
            "agent_id": agent,
            "question_class": effective_class,
            "sections": [],
            "packet_text": "",
        }
    packet_text = "\n".join(
        [
            "GIG BUSINESS DOCTRINE (v1.2; NEVER_STALE; ONLY pricing/logistics source):",
            *(f"- {section['title']}: {section['text']}" for section in selected),
        ]
    )
    receipt_seed = {
        "doctrine_ref": contract["doctrine_ref"],
        "source_sha256": contract["source_sha256"],
        "agent_id": agent,
        "question_class": effective_class,
        "section_ids": [section["section_id"] for section in selected],
    }
    return {
        "status": "READY",
        "doctrine_ref": contract["doctrine_ref"],
        "canonical_path": contract["canonical_path"],
        "source_sha256": contract["source_sha256"],
        "source_ref": source_ref,
        "freshness": freshness,
        "pricing_logistics_source_policy": contract[
            "pricing_logistics_source_policy"
        ],
        "agent_id": agent,
        "question_class": effective_class,
        "sections": selected,
        "packet_text": packet_text,
        "receipt": {
            "schema_version": "gig_business_doctrine_delivery_receipt_v1",
            "receipt_id": f"gig_doctrine_delivery:{_short_hash(receipt_seed)}",
            "status": "READY",
            "source_sha256": contract["source_sha256"],
            "freshness_class": FRESHNESS_CLASS,
            "pricing_logistics_source_policy": PRICING_LOGISTICS_SOURCE_POLICY,
            "section_ids": [section["section_id"] for section in selected],
        },
    }


def _ledger_actors(consumers: list[str]) -> list[str]:
    normalized = {"cassandra" if value == "clara" else value for value in consumers}
    return sorted(actor for actor in normalized if actor in _LEDGER_ACTORS)


def ingest_doctrine_into_ledger(
    *,
    db_path: str | Path,
    allow_production: bool = False,
) -> dict[str, Any]:
    contract = load_gig_business_doctrine()
    results = []
    for section in contract["sections"]:
        record = {
            "fact_id": f"gig_business_doctrine:{section['section_id']}:v1_2",
            "source_file": contract["canonical_path"],
            "section_heading": section["title"],
            "source_commit": contract["source_sha256"],
            "fact_text": section["packet_summary"],
            "sensitivity_class": "operational_canonical",
            "allowed_actors": _ledger_actors(list(section["consumers"])),
            "doc_category": "gig_business_doctrine",
            "temporal_or_doctrine": "doctrine_never_stale",
            "source_description": (
                "Operator-derived GIG_BUSINESS_DOCTRINE v1.2; NEVER_STALE; "
                "only pricing/logistics source"
            ),
            "truth_status": "declared",
            "verification_required": 1,
            "verification_evidence_id": "operator_terminal:2026-07-18",
        }
        results.append(
            ingest_graded_fact(
                record,
                db_path=str(db_path),
                allow_production=allow_production,
            )
        )
    counts = {
        status: sum(1 for result in results if result.get("status") == status)
        for status in ("inserted", "replaced", "skipped")
    }
    return {
        "schema_version": "gig_business_doctrine_ingest_receipt_v1",
        "status": "INGESTED",
        "doctrine_ref": contract["doctrine_ref"],
        "source_file": contract["canonical_path"],
        "source_sha256": contract["source_sha256"],
        "freshness_class": FRESHNESS_CLASS,
        "pricing_logistics_source_policy": PRICING_LOGISTICS_SOURCE_POLICY,
        "production_ledger_post": bool(allow_production),
        "total": len(results),
        **counts,
        "results": results,
    }


__all__ = [
    "DOCTRINE_PATH",
    "DOCTRINE_REF",
    "FRESHNESS_CLASS",
    "PRICING_LOGISTICS_SOURCE_POLICY",
    "build_doctrine_delivery",
    "build_freshness_registration",
    "ingest_doctrine_into_ledger",
    "load_gig_business_doctrine",
]
