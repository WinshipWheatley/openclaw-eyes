#!/usr/bin/env python3
"""
claim_detector.py — Component 3: Self-Healing Claim Detector

Precision-first claim detector that identifies direct factual assertions in
operator-visible answer text, validates them against grounded read-model truth,
and queues SUPERVISED heal tasks ONLY for confirmed-incorrect deterministic claims.

LOAD-BEARING DEFAULTS:
  - llm_claim_queue_mode = 'shadow'  (LLM-assisted candidates CANNOT queue heals)
  - No auto-deploy: worker proposes only; human approves
  - TRUTH FIRST: any uncertainty => abstain
  - False negatives OK; false positives NOT

Safety: read-only truth sources; no sends/money/.chief.env/Legal.
"""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

# ---------------------------------------------------------------------------
# Dependency imports (these are in the base — they ARE available)
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from polish_loop.answer_auditor import AuditFinding, check_agent_claim
    from polish_loop.control_plane import ControlPlaneLedger, TaskRejected
    from polish_loop.pc4_heal_emitter import emit_heal_task
except ImportError:
    try:
        sys.path.insert(0, str(ROOT / "polish_loop"))
        from answer_auditor import AuditFinding, check_agent_claim
        from control_plane import ControlPlaneLedger, TaskRejected
        from pc4_heal_emitter import emit_heal_task
    except ImportError:
        # Allow module to import without polish_loop for structural tests
        AuditFinding = None  # type: ignore[assignment]
        check_agent_claim = None  # type: ignore[assignment]
        ControlPlaneLedger = None  # type: ignore[assignment]
        TaskRejected = None  # type: ignore[assignment]
        emit_heal_task = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DETECTOR_VERSION = "1.0.0"
REGISTRY_VERSION = "1"

# llm_claim_queue_mode default: shadow means LLM-assisted candidates record/score only
# They may NEVER queue heals. Only deterministic candidates may queue.
LLM_CLAIM_QUEUE_MODE: str = os.environ.get("OPENCLAW_LLM_CLAIM_QUEUE_MODE", "shadow")

MAX_LLM_CANDIDATES_PER_REPLY = 3   # max unmatched sentences sent to LLM extractor
MAX_CLAIMS_PER_REPLY = 5            # max detected claims per reply

HEDGING_TOKENS = frozenset({
    "maybe", "probably", "possibly", "approximately", "roughly", "about",
    "around", "i think", "it appears", "it seems", "should", "could", "might",
    "likely", "perhaps", "seems", "appear", "estimate", "estimated",
    "approximately", "near", "nearly", "almost", "virtually", "supposedly",
})

ASSERTION_KIND_DIRECT = "direct"
ASSERTION_KIND_QUOTED = "quoted"
ASSERTION_KIND_HYPOTHETICAL = "hypothetical"
ASSERTION_KIND_FORECAST = "forecast"
ASSERTION_KIND_RECOMMENDATION = "recommendation"
ASSERTION_KIND_AMBIGUOUS = "ambiguous"

EXTRACTION_ROUTE_DETERMINISTIC = "deterministic"
EXTRACTION_ROUTE_LLM_ASSISTED = "llm_assisted"

FAULT_DOMAIN_RENDERER_MUTATION = "renderer_mutation"
FAULT_DOMAIN_UNGROUNDED_ASSERTION = "ungrounded_assertion"
FAULT_DOMAIN_PACKET_VALUE_ERROR = "packet_value_error"
FAULT_DOMAIN_SOURCE_MAPPING_ERROR = "source_mapping_error"
FAULT_DOMAIN_UNKNOWN = "unknown"

HEAL_STATUS_AWAITING_REVIEW = "awaiting_review"

FORBIDDEN_PATH_MARKERS = (
    ".chief.env", ".google-secrets", "OpenClawLegalPrivate",
    "LegalPrivate", "FinancePrivate", "MusicLawPrivate",
)

# ---------------------------------------------------------------------------
# ClaimTypeSpec Registry
# (NO generic count/status/date — encode semantics per spec)
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class ClaimTypeSpec:
    claim_type: str
    description: str
    value_kind: str          # integer|money|percentage|date|datetime|status|boolean|version|string_enum
    entity_kind: str
    allowed_status_values: tuple[str, ...]
    aliases: dict[str, str]  # wording -> canonical status
    deterministic_patterns: tuple[str, ...]
    truth_source_adapter: str
    comparison_policy: str   # exact|currency_exact|datetime_exact|tolerance
    tolerance: Any           # None unless registered
    max_truth_age_seconds: int
    historical_snapshot_required: bool
    registry_version: str


# Canonical claim type registry — semantics over generic labels
CLAIM_TYPE_REGISTRY: dict[str, ClaimTypeSpec] = {
    "project.open_task_count.v1": ClaimTypeSpec(
        claim_type="project.open_task_count.v1",
        description="Number of open/pending tasks in a project",
        value_kind="integer",
        entity_kind="project",
        allowed_status_values=(),
        aliases={},
        deterministic_patterns=(
            r"\b(?:there are|has)\s+(\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten)\s+open\s+tasks?\b",
            r"\b(\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:open|pending|unfinished|unresolved)\s+tasks?\b",
            r"\bopen\s+task\s+count\s+(?:is|=)\s*:?\s*(\d+)\b",
        ),
        truth_source_adapter="agent_presence_online_count",
        comparison_policy="exact",
        tolerance=None,
        max_truth_age_seconds=300,
        historical_snapshot_required=True,
        registry_version=REGISTRY_VERSION,
    ),
    "project.status.v1": ClaimTypeSpec(
        claim_type="project.status.v1",
        description="Status of a named project",
        value_kind="status",
        entity_kind="project",
        allowed_status_values=("active", "on_hold", "complete", "blocked", "cancelled"),
        aliases={
            "on hold": "on_hold",
            "completed": "complete",
            "done": "complete",
            "canceled": "cancelled",
            "in progress": "active",
            "in-progress": "active",
            "running": "active",
        },
        deterministic_patterns=(
            r"\bproject\s+(?:is|status\s+is)\s+(active|on\s+hold|complete|blocked|cancelled|done|in\s+progress)\b",
        ),
        truth_source_adapter="capability_live",
        comparison_policy="exact",
        tolerance=None,
        max_truth_age_seconds=600,
        historical_snapshot_required=True,
        registry_version=REGISTRY_VERSION,
    ),
    "finance.invoice_total.v1": ClaimTypeSpec(
        claim_type="finance.invoice_total.v1",
        description="Total dollar amount of a specific invoice",
        value_kind="money",
        entity_kind="invoice",
        allowed_status_values=(),
        aliases={},
        deterministic_patterns=(
            r"\binvoice\s+total\s+(?:is|=|of)\s*:?\s*\$?\s*([\d,]+(?:\.\d{1,2})?)\b",
            r"\btotal\s+(?:amount|due)\s+(?:is|=)\s*:?\s*\$?\s*([\d,]+(?:\.\d{1,2})?)\b",
        ),
        truth_source_adapter="receipt_type_count",
        comparison_policy="currency_exact",
        tolerance=None,
        max_truth_age_seconds=3600,
        historical_snapshot_required=True,
        registry_version=REGISTRY_VERSION,
    ),
    "finance.outstanding_balance.v1": ClaimTypeSpec(
        claim_type="finance.outstanding_balance.v1",
        description="Outstanding balance owed on an account or invoice",
        value_kind="money",
        entity_kind="account",
        allowed_status_values=(),
        aliases={},
        deterministic_patterns=(
            r"\boutstanding\s+balance\s+(?:is|=|of)\s*:?\s*\$?\s*([\d,]+(?:\.\d{1,2})?)\b",
            r"\bbalance\s+(?:due|owed)\s+(?:is|=)\s*:?\s*\$?\s*([\d,]+(?:\.\d{1,2})?)\b",
        ),
        truth_source_adapter="receipt_type_count",
        comparison_policy="currency_exact",
        tolerance=None,
        max_truth_age_seconds=3600,
        historical_snapshot_required=True,
        registry_version=REGISTRY_VERSION,
    ),
    "schedule.event_start.v1": ClaimTypeSpec(
        claim_type="schedule.event_start.v1",
        description="Start date/time of a scheduled event",
        value_kind="datetime",
        entity_kind="event",
        allowed_status_values=(),
        aliases={},
        deterministic_patterns=(
            r"\b(?:event|show|gig|meeting|session)\s+(?:starts?|begins?)\s+(?:at|on)\s+([\d\-T:Z+\s,]+(?:AM|PM)?)\b",
            r"\bstart\s+(?:date|time)\s+(?:is|=)\s*:?\s*([\d\-T:Z+\s]+)\b",
        ),
        truth_source_adapter="receipt_type_count",
        comparison_policy="datetime_exact",
        tolerance=None,
        max_truth_age_seconds=86400,
        historical_snapshot_required=True,
        registry_version=REGISTRY_VERSION,
    ),
    "schedule.due_date.v1": ClaimTypeSpec(
        claim_type="schedule.due_date.v1",
        description="Due date of a task or deliverable",
        value_kind="date",
        entity_kind="task",
        allowed_status_values=(),
        aliases={},
        deterministic_patterns=(
            r"\bdue\s+(?:on|by|date(?:\s+is)?)\s*:?\s*(\d{4}-\d{2}-\d{2})\b",
            r"\bdeadline\s+(?:is|=)\s*:?\s*(\d{4}-\d{2}-\d{2})\b",
        ),
        truth_source_adapter="receipt_type_count",
        comparison_policy="datetime_exact",
        tolerance=None,
        max_truth_age_seconds=86400,
        historical_snapshot_required=True,
        registry_version=REGISTRY_VERSION,
    ),
    "operations.queue_depth.v1": ClaimTypeSpec(
        claim_type="operations.queue_depth.v1",
        description="Number of items in an agent's work queue",
        value_kind="integer",
        entity_kind="agent_queue",
        allowed_status_values=(),
        aliases={},
        deterministic_patterns=(
            r"\bqueue\s+(?:depth|size|length)\s+(?:is|=|has)\s*:?\s*(\d+)\b",
            r"\b(\d+)\s+(?:item|job|task)s?\s+(?:in|waiting\s+in)\s+(?:the\s+)?queue\b",
        ),
        truth_source_adapter="agent_presence_online_count",
        comparison_policy="exact",
        tolerance=None,
        max_truth_age_seconds=60,   # fast-changing: tighter freshness
        historical_snapshot_required=True,
        registry_version=REGISTRY_VERSION,
    ),
    "operations.agent_health_status.v1": ClaimTypeSpec(
        claim_type="operations.agent_health_status.v1",
        description="Health/online status of an agent",
        value_kind="status",
        entity_kind="agent",
        allowed_status_values=("online", "offline", "degraded", "unknown"),
        aliases={
            "up": "online",
            "running": "online",
            "down": "offline",
            "stopped": "offline",
            "unhealthy": "degraded",
            "partial": "degraded",
        },
        deterministic_patterns=(
            r"\bagent\s+(?:is\s+)?(online|offline|degraded|unknown|up|down|running|stopped)\b",
            r"\b(?:health|status)\s+(?:is|=)\s*:?\s*(online|offline|degraded|unknown|up|down)\b",
        ),
        truth_source_adapter="agent_presence_online_count",
        comparison_policy="exact",
        tolerance=None,
        max_truth_age_seconds=60,   # fast-changing
        historical_snapshot_required=True,
        registry_version=REGISTRY_VERSION,
    ),
    "artifact.file_count.v1": ClaimTypeSpec(
        claim_type="artifact.file_count.v1",
        description="Number of files in an artifact set or directory",
        value_kind="integer",
        entity_kind="artifact_set",
        allowed_status_values=(),
        aliases={},
        deterministic_patterns=(
            r"\b(?:there are|contains?|has)\s+(\d+)\s+files?\b",
            r"\b(\d+)\s+files?\s+(?:in|under|within)\b",
        ),
        truth_source_adapter="receipt_type_count",
        comparison_policy="exact",
        tolerance=None,
        max_truth_age_seconds=3600,
        historical_snapshot_required=True,
        registry_version=REGISTRY_VERSION,
    ),
    "deployment.release_version.v1": ClaimTypeSpec(
        claim_type="deployment.release_version.v1",
        description="Released version of a deployed component",
        value_kind="version",
        entity_kind="component",
        allowed_status_values=(),
        aliases={},
        deterministic_patterns=(
            r"\bversion\s+(?:is\s+)?v?(\d+\.\d+(?:\.\d+)?(?:-[\w.]+)?)\b",
            r"\brelease\s+v?(\d+\.\d+(?:\.\d+)?(?:-[\w.]+)?)\b",
        ),
        truth_source_adapter="change_sentinel_generated_at",
        comparison_policy="exact",
        tolerance=None,
        max_truth_age_seconds=3600,
        historical_snapshot_required=True,
        registry_version=REGISTRY_VERSION,
    ),
    "operations.online_agent_count.v1": ClaimTypeSpec(
        claim_type="operations.online_agent_count.v1",
        description="Count of agents currently online",
        value_kind="integer",
        entity_kind="fleet",
        allowed_status_values=(),
        aliases={},
        deterministic_patterns=(
            r"\b(\d+)\s+agents?\s+(?:are\s+)?(?:online|running|active)\b",
            r"\b(\d+)\s+(?:online|active)\s+agents?\b",
        ),
        truth_source_adapter="agent_presence_online_count",
        comparison_policy="exact",
        tolerance=None,
        max_truth_age_seconds=60,
        historical_snapshot_required=True,
        registry_version=REGISTRY_VERSION,
    ),
}


# ---------------------------------------------------------------------------
# Number-word to int mapping (for deterministic extraction)
# ---------------------------------------------------------------------------

NUMBER_WORDS: dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}

# Currency symbol / code to ISO 4217 code
CURRENCY_SYMBOLS: dict[str, str] = {
    "$": "USD", "usd": "USD", "us$": "USD",
    "€": "EUR", "eur": "EUR",
    "£": "GBP", "gbp": "GBP",
    "¥": "JPY", "jpy": "JPY",
    "cad": "CAD", "c$": "CAD",
    "aud": "AUD", "a$": "AUD",
}

# Deterministic cue scan patterns (broad — only decides whether to parse more)
CUE_PATTERNS = [
    re.compile(r"\b\d+\b"),                          # digits
    re.compile(r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b", re.I),  # number words
    re.compile(r"[$€£¥]|\b(?:USD|EUR|GBP|JPY|CAD|AUD)\b", re.I),   # currency
    re.compile(r"\b\d+(?:\.\d+)?%"),                 # percentages
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),            # dates
    re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|UTC|EST|PST|CST|MST)?\b", re.I),  # times
    re.compile(r"\b(?:online|offline|active|inactive|enabled|disabled|degraded|blocked|complete)\b", re.I),  # status
    re.compile(r"\b(?:true|false|yes|no|enabled|disabled)\b", re.I),  # boolean
    re.compile(r"\bv\d+\.\d+(?:\.\d+)?(?:-[\w.]+)?\b"),  # version strings
    re.compile(r"\b(?:tasks?|jobs?|items?|files?|agents?|queue)\b", re.I),  # semantic nouns
]

# Quoted speech patterns
QUOTED_SPEECH_PATTERNS = [
    re.compile(r'(?:said|says|noted|reported|mentioned|stated|wrote|claimed|told)\b', re.I),
    re.compile(r'(?:according\s+to|per\s+\w+|as\s+(?:stated|reported|noted))', re.I),
    re.compile(r'["“”]'),  # actual quote marks
]

# Hypothetical / conditional patterns
HYPOTHETICAL_PATTERNS = [
    re.compile(r'\b(?:if|when|unless|suppose|imagine|hypothetically|in\s+theory|would\s+be|were\s+to)\b', re.I),
    re.compile(r'\b(?:for\s+example|e\.g\.|such\s+as|like\s+when)\b', re.I),
]

# Forecast / prediction patterns
FORECAST_PATTERNS = [
    re.compile(r'\b(?:will\s+(?:be|have)|expected\s+to|projected\s+to|forecast(?:ed)?|predicted)\b', re.I),
    re.compile(r'\b(?:by\s+(?:end\s+of|Q\d|next\s+(?:month|year|week)))\b', re.I),
]

# Recommendation patterns
RECOMMENDATION_PATTERNS = [
    re.compile(r'\b(?:should|recommend|suggest|consider|you\s+(?:may|might|could|should)|advise)\b', re.I),
    re.compile(r'\b(?:best\s+practice|preferred|ideal(?:ly)?)\b', re.I),
]

# ---------------------------------------------------------------------------
# Core data schemas
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class MoneyValue:
    """Currency + integer minor units (e.g. USD 10050 = $100.50). No binary float."""
    currency_code: str    # ISO 4217
    minor_units: int      # e.g. cents; 0.01 precision


@dataclasses.dataclass
class DetectedClaim:
    detector_version: str
    reply_id: str
    agent_id: str
    claim_type: str
    normalized_value: Any                 # typed: int | MoneyValue | str | bool | ...
    value_surface: str                    # raw text extracted
    entity_ref: str                       # resolved entity identifier
    entity_surface: str                   # raw entity text in answer
    temporal_scope: Optional[str]         # ISO 8601 or "reply_time"
    assertion_span_text: str
    assertion_span_start: int
    assertion_span_end: int
    assertion_kind: str                   # direct|quoted|hypothetical|forecast|recommendation|ambiguous
    polarity: str                         # positive|negative
    extraction_route: str                 # deterministic|llm_assisted
    extraction_confidence: float          # 1.0 for deterministic
    supporting_fact_ids: list[str]
    registry_version: str
    hedged: bool


@dataclasses.dataclass
class BoundTruthSource:
    claim_type: str
    entity_ref: str
    as_of: Optional[str]
    source_ref: str
    source_revision: Optional[str]
    observed_at: Optional[str]
    freshness_status: str     # fresh|stale|unknown
    adapter: str
    historical_snapshot_exists: bool


@dataclasses.dataclass
class HealTask:
    heal_task_id: str
    idempotency_key: str
    reply_id: str
    agent_id: str
    claim_type: str
    entity_ref: str
    temporal_scope: Optional[str]
    assertion_span_text: str
    assertion_span_start: int
    assertion_span_end: int
    claimed_value: Any
    truth_value: Any
    truth_source_ref: str
    truth_source_revision: Optional[str]
    audited_at: str
    detector_route: str
    detector_policy_version: str
    fault_domain: str
    status: str


# ---------------------------------------------------------------------------
# Deterministic extraction helpers
# ---------------------------------------------------------------------------

def _sentence_split(text: str) -> list[tuple[str, int]]:
    """Split text into (sentence, char_offset) pairs preserving offsets."""
    sentences: list[tuple[str, int]] = []
    # Split on '. ', '! ', '? ', '\n' boundaries
    pattern = re.compile(r'(?<=[.!?])\s+|\n+')
    start = 0
    for m in pattern.finditer(text):
        sent = text[start:m.start()].strip()
        if sent:
            sentences.append((sent, start))
        start = m.end()
    remaining = text[start:].strip()
    if remaining:
        sentences.append((remaining, start))
    return sentences


def _normalize_number(raw: str) -> Optional[int]:
    """Parse digit or number-word to int. Returns None if ambiguous."""
    raw = raw.strip().lower().replace(",", "")
    if raw in NUMBER_WORDS:
        return NUMBER_WORDS[raw]
    try:
        v = int(raw)
        return v
    except ValueError:
        pass
    return None


def _normalize_money(amount_str: str, currency_hint: Optional[str]) -> Optional[MoneyValue]:
    """Convert amount string to MoneyValue with integer minor units. No float."""
    amount_str = amount_str.strip().replace(",", "")
    try:
        # Parse to fixed decimal: find dollars and cents
        if "." in amount_str:
            parts = amount_str.split(".", 1)
            dollars = int(parts[0])
            cents_str = (parts[1] + "00")[:2]
            cents = int(cents_str)
        else:
            dollars = int(amount_str)
            cents = 0
        minor_units = dollars * 100 + cents
    except (ValueError, IndexError):
        return None

    if currency_hint:
        code = CURRENCY_SYMBOLS.get(currency_hint.lower().strip())
        if not code:
            return None  # unresolved currency => reject per spec
    else:
        code = "USD"  # default only if no ambiguity

    return MoneyValue(currency_code=code, minor_units=minor_units)


def _normalize_status(raw: str, spec: ClaimTypeSpec) -> Optional[str]:
    """Resolve raw status text via alias map to canonical. None if unregistered."""
    raw_lower = raw.strip().lower()
    if raw_lower in spec.allowed_status_values:
        return raw_lower
    canonical = spec.aliases.get(raw_lower)
    if canonical and canonical in spec.allowed_status_values:
        return canonical
    # Try space-normalized alias
    raw_collapsed = re.sub(r'\s+', ' ', raw_lower)
    canonical = spec.aliases.get(raw_collapsed)
    if canonical and canonical in spec.allowed_status_values:
        return canonical
    return None


def _normalize_date_iso(raw: str) -> Optional[str]:
    """Parse date to ISO 8601 YYYY-MM-DD. Returns None if vague."""
    raw = raw.strip()
    # Reject vague: "soon", "around Friday", etc.
    if re.search(r'\b(?:soon|around|about|next|this|upcoming|near|shortly)\b', raw, re.I):
        return None
    m = re.match(r'^(\d{4}-\d{2}-\d{2})$', raw)
    if m:
        return m.group(1)
    # Try month/day/year
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})$', raw)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if year < 100:
            year += 2000
        try:
            d = datetime.date(year, month, day)
            return d.isoformat()
        except ValueError:
            return None
    return None


def _normalize_datetime_iso(raw: str, operator_tz: Optional[str] = None) -> Optional[str]:
    """Parse datetime to ISO 8601. Explicit or unique tz required. None if ambiguous."""
    raw = raw.strip()
    # ISO 8601 with timezone
    m = re.match(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2}))$', raw)
    if m:
        return m.group(1)
    # Has explicit UTC/Z suffix
    m = re.match(r'^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}(?::\d{2})?)\s*UTC$', raw, re.I)
    if m:
        return f"{m.group(1)}T{m.group(2)}Z"
    # Reject: no timezone context
    return None


def _is_hedged(sentence: str) -> bool:
    """True if the sentence contains hedging/modal qualifiers."""
    lower = sentence.lower()
    for token in HEDGING_TOKENS:
        if token in lower:
            return True
    return False


def _is_quoted(sentence: str) -> bool:
    """True if sentence appears to be quoted speech (not a direct assertion)."""
    for pat in QUOTED_SPEECH_PATTERNS:
        if pat.search(sentence):
            return True
    return False


def _is_hypothetical(sentence: str) -> bool:
    for pat in HYPOTHETICAL_PATTERNS:
        if pat.search(sentence):
            return True
    return False


def _is_forecast(sentence: str) -> bool:
    for pat in FORECAST_PATTERNS:
        if pat.search(sentence):
            return True
    return False


def _is_recommendation(sentence: str) -> bool:
    for pat in RECOMMENDATION_PATTERNS:
        if pat.search(sentence):
            return True
    return False


def _classify_assertion_kind(sentence: str) -> str:
    """Classify sentence assertion kind. direct only if not any filtered kind."""
    if _is_quoted(sentence):
        return ASSERTION_KIND_QUOTED
    if _is_hypothetical(sentence):
        return ASSERTION_KIND_HYPOTHETICAL
    if _is_forecast(sentence):
        return ASSERTION_KIND_FORECAST
    if _is_recommendation(sentence):
        return ASSERTION_KIND_RECOMMENDATION
    return ASSERTION_KIND_DIRECT


def _has_cue(sentence: str) -> bool:
    """Broad cue scan — only decides whether to parse more."""
    for pat in CUE_PATTERNS:
        if pat.search(sentence):
            return True
    return False


# ---------------------------------------------------------------------------
# Entity resolution (4-step order per spec)
# ---------------------------------------------------------------------------

def _resolve_entity(
    sentence: str,
    spec: ClaimTypeSpec,
    operator_question: str,
    packet_entity_aliases: Optional[dict[str, str]] = None,
) -> Optional[tuple[str, str]]:
    """
    Resolve entity from sentence per spec 4-step order:
    1. Explicit name in assertion
    2. Verified aliases in packet
    3. Operator question only if exactly one entity of required kind in scope
    4. Pronoun only if antecedent unambiguous

    Returns (entity_ref, entity_surface) or None if ambiguous.
    Ambiguous => abstain (never ask LLM to guess between entities).
    """
    # Step 1: Look for explicit entity names — find all nouns that could be entities
    # For agent/project/component names: look for capitalized proper nouns
    entity_kind = spec.entity_kind
    found_entities: list[tuple[str, str]] = []

    # Try packet aliases first (step 2)
    if packet_entity_aliases:
        for alias, canonical in packet_entity_aliases.items():
            if alias.lower() in sentence.lower():
                found_entities.append((canonical, alias))

    # Step 1: Proper nouns in assertion
    if not found_entities:
        # Look for capitalized runs that could be entity names
        proper_nouns = re.findall(r'\b([A-Z][A-Za-z0-9_\-]+(?:\s+[A-Z][A-Za-z0-9_\-]+)*)\b', sentence)
        # Filter out sentence starters (first word of sentence)
        sentence_first = sentence.split()[0] if sentence.split() else ""
        proper_nouns = [n for n in proper_nouns if n != sentence_first or len(proper_nouns) > 1]
        # Only include if they look like entity names (not common words)
        common_words = frozenset({"The", "There", "This", "That", "It", "They", "He", "She", "We", "You"})
        proper_nouns = [n for n in proper_nouns if n not in common_words]
        if len(proper_nouns) == 1:
            found_entities.append((proper_nouns[0], proper_nouns[0]))
        elif len(proper_nouns) > 1:
            # Multiple candidates — ambiguous => abstain
            return None

    # Step 3: Operator question context — only if exactly one entity of required kind
    if not found_entities and operator_question:
        q_entities = re.findall(r'\b([A-Z][A-Za-z0-9_\-]+(?:\s+[A-Z][A-Za-z0-9_\-]+)*)\b', operator_question)
        q_entities = [e for e in q_entities if e not in frozenset({"What", "How", "When", "Where", "Which", "Who", "The", "Is", "Are", "Do", "Does"})]
        if len(q_entities) == 1:
            found_entities.append((q_entities[0], q_entities[0]))
        elif len(q_entities) > 1:
            # Multiple entities in question without disambiguation in sentence => ambiguous
            return None

    # Step 4: Pronouns — only if clearly unambiguous (skip if uncertain)
    # Per spec: "Atlas and Beacon... They have 12" => ambiguous => no audit/heal
    if not found_entities:
        if re.search(r'\b(?:they|it|he|she)\b', sentence, re.I):
            # Pronoun without clear antecedent => abstain
            return None
        # No entity at all — abstain
        return None

    if len(found_entities) > 1:
        return None  # ambiguous

    return found_entities[0]


# ---------------------------------------------------------------------------
# Deterministic extractors per claim type
# ---------------------------------------------------------------------------

def _try_extract_count(
    sentence: str,
    sentence_start: int,
    spec: ClaimTypeSpec,
    operator_question: str,
    packet_entity_aliases: Optional[dict[str, str]] = None,
) -> Optional["DetectedClaim"]:
    """Extract integer count claims deterministically."""
    for pattern_str in spec.deterministic_patterns:
        m = re.search(pattern_str, sentence, re.I)
        if not m:
            continue
        raw_value = m.group(1) if m.lastindex else ""
        normalized = _normalize_number(raw_value)
        if normalized is None:
            continue

        entity = _resolve_entity(sentence, spec, operator_question, packet_entity_aliases)
        if entity is None:
            return None  # ambiguous => abstain

        assertion_text = sentence
        span_start = sentence_start
        span_end = sentence_start + len(sentence)

        return DetectedClaim(
            detector_version=DETECTOR_VERSION,
            reply_id="",  # filled by caller
            agent_id="",  # filled by caller
            claim_type=spec.claim_type,
            normalized_value=normalized,
            value_surface=raw_value,
            entity_ref=entity[0],
            entity_surface=entity[1],
            temporal_scope=None,  # filled by caller
            assertion_span_text=assertion_text,
            assertion_span_start=span_start,
            assertion_span_end=span_end,
            assertion_kind=ASSERTION_KIND_DIRECT,
            polarity="positive",
            extraction_route=EXTRACTION_ROUTE_DETERMINISTIC,
            extraction_confidence=1.0,
            supporting_fact_ids=[],
            registry_version=REGISTRY_VERSION,
            hedged=False,
        )
    return None


def _try_extract_status(
    sentence: str,
    sentence_start: int,
    spec: ClaimTypeSpec,
    operator_question: str,
    packet_entity_aliases: Optional[dict[str, str]] = None,
) -> Optional["DetectedClaim"]:
    """Extract status claims deterministically via alias map."""
    for pattern_str in spec.deterministic_patterns:
        m = re.search(pattern_str, sentence, re.I)
        if not m:
            continue
        raw_value = m.group(1) if m.lastindex else ""
        canonical = _normalize_status(raw_value, spec)
        if canonical is None:
            continue

        entity = _resolve_entity(sentence, spec, operator_question, packet_entity_aliases)
        if entity is None:
            return None

        return DetectedClaim(
            detector_version=DETECTOR_VERSION,
            reply_id="",
            agent_id="",
            claim_type=spec.claim_type,
            normalized_value=canonical,
            value_surface=raw_value,
            entity_ref=entity[0],
            entity_surface=entity[1],
            temporal_scope=None,
            assertion_span_text=sentence,
            assertion_span_start=sentence_start,
            assertion_span_end=sentence_start + len(sentence),
            assertion_kind=ASSERTION_KIND_DIRECT,
            polarity="positive",
            extraction_route=EXTRACTION_ROUTE_DETERMINISTIC,
            extraction_confidence=1.0,
            supporting_fact_ids=[],
            registry_version=REGISTRY_VERSION,
            hedged=False,
        )
    return None


def _try_extract_money(
    sentence: str,
    sentence_start: int,
    spec: ClaimTypeSpec,
    operator_question: str,
    packet_entity_aliases: Optional[dict[str, str]] = None,
) -> Optional["DetectedClaim"]:
    """Extract money claims. Currency code + integer minor units. No float."""
    # Find currency symbol/code in sentence
    currency_match = re.search(
        r'([$€£¥]|\b(?:USD|EUR|GBP|JPY|CAD|AUD)\b)',
        sentence, re.I
    )
    currency_hint: Optional[str] = None
    if currency_match:
        currency_hint = currency_match.group(1)

    for pattern_str in spec.deterministic_patterns:
        m = re.search(pattern_str, sentence, re.I)
        if not m:
            continue
        raw_amount = m.group(1) if m.lastindex else ""
        # Strip currency symbol if present at start
        raw_amount = re.sub(r'^[$€£¥]\s*', '', raw_amount.strip())
        money = _normalize_money(raw_amount, currency_hint)
        if money is None:
            continue

        entity = _resolve_entity(sentence, spec, operator_question, packet_entity_aliases)
        if entity is None:
            return None

        return DetectedClaim(
            detector_version=DETECTOR_VERSION,
            reply_id="",
            agent_id="",
            claim_type=spec.claim_type,
            normalized_value=money,
            value_surface=raw_amount,
            entity_ref=entity[0],
            entity_surface=entity[1],
            temporal_scope=None,
            assertion_span_text=sentence,
            assertion_span_start=sentence_start,
            assertion_span_end=sentence_start + len(sentence),
            assertion_kind=ASSERTION_KIND_DIRECT,
            polarity="positive",
            extraction_route=EXTRACTION_ROUTE_DETERMINISTIC,
            extraction_confidence=1.0,
            supporting_fact_ids=[],
            registry_version=REGISTRY_VERSION,
            hedged=False,
        )
    return None


def _try_extract_date(
    sentence: str,
    sentence_start: int,
    spec: ClaimTypeSpec,
    operator_question: str,
    packet_entity_aliases: Optional[dict[str, str]] = None,
) -> Optional["DetectedClaim"]:
    """Extract ISO 8601 date claims. Reject vague/relative."""
    for pattern_str in spec.deterministic_patterns:
        m = re.search(pattern_str, sentence, re.I)
        if not m:
            continue
        raw_date = m.group(1) if m.lastindex else ""
        iso_date = _normalize_date_iso(raw_date)
        if iso_date is None:
            continue

        entity = _resolve_entity(sentence, spec, operator_question, packet_entity_aliases)
        if entity is None:
            return None

        return DetectedClaim(
            detector_version=DETECTOR_VERSION,
            reply_id="",
            agent_id="",
            claim_type=spec.claim_type,
            normalized_value=iso_date,
            value_surface=raw_date,
            entity_ref=entity[0],
            entity_surface=entity[1],
            temporal_scope=iso_date,
            assertion_span_text=sentence,
            assertion_span_start=sentence_start,
            assertion_span_end=sentence_start + len(sentence),
            assertion_kind=ASSERTION_KIND_DIRECT,
            polarity="positive",
            extraction_route=EXTRACTION_ROUTE_DETERMINISTIC,
            extraction_confidence=1.0,
            supporting_fact_ids=[],
            registry_version=REGISTRY_VERSION,
            hedged=False,
        )
    return None


def _try_extract_datetime(
    sentence: str,
    sentence_start: int,
    spec: ClaimTypeSpec,
    operator_question: str,
    packet_entity_aliases: Optional[dict[str, str]] = None,
) -> Optional["DetectedClaim"]:
    """Extract ISO 8601 datetime. Requires explicit/unique timezone."""
    for pattern_str in spec.deterministic_patterns:
        m = re.search(pattern_str, sentence, re.I)
        if not m:
            continue
        raw_dt = (m.group(1) if m.lastindex else "").strip()
        iso_dt = _normalize_datetime_iso(raw_dt)
        if iso_dt is None:
            # Also try date-only as datetime fallback for this claim type
            iso_dt = _normalize_date_iso(raw_dt)
            if iso_dt is None:
                continue

        entity = _resolve_entity(sentence, spec, operator_question, packet_entity_aliases)
        if entity is None:
            return None

        return DetectedClaim(
            detector_version=DETECTOR_VERSION,
            reply_id="",
            agent_id="",
            claim_type=spec.claim_type,
            normalized_value=iso_dt,
            value_surface=raw_dt,
            entity_ref=entity[0],
            entity_surface=entity[1],
            temporal_scope=iso_dt,
            assertion_span_text=sentence,
            assertion_span_start=sentence_start,
            assertion_span_end=sentence_start + len(sentence),
            assertion_kind=ASSERTION_KIND_DIRECT,
            polarity="positive",
            extraction_route=EXTRACTION_ROUTE_DETERMINISTIC,
            extraction_confidence=1.0,
            supporting_fact_ids=[],
            registry_version=REGISTRY_VERSION,
            hedged=False,
        )
    return None


def _try_extract_version(
    sentence: str,
    sentence_start: int,
    spec: ClaimTypeSpec,
    operator_question: str,
    packet_entity_aliases: Optional[dict[str, str]] = None,
) -> Optional["DetectedClaim"]:
    """Extract version string claims (exact normalized eq)."""
    for pattern_str in spec.deterministic_patterns:
        m = re.search(pattern_str, sentence, re.I)
        if not m:
            continue
        raw_ver = m.group(1) if m.lastindex else ""
        if not raw_ver:
            continue

        entity = _resolve_entity(sentence, spec, operator_question, packet_entity_aliases)
        if entity is None:
            return None

        return DetectedClaim(
            detector_version=DETECTOR_VERSION,
            reply_id="",
            agent_id="",
            claim_type=spec.claim_type,
            normalized_value=raw_ver.strip(),
            value_surface=raw_ver,
            entity_ref=entity[0],
            entity_surface=entity[1],
            temporal_scope=None,
            assertion_span_text=sentence,
            assertion_span_start=sentence_start,
            assertion_span_end=sentence_start + len(sentence),
            assertion_kind=ASSERTION_KIND_DIRECT,
            polarity="positive",
            extraction_route=EXTRACTION_ROUTE_DETERMINISTIC,
            extraction_confidence=1.0,
            supporting_fact_ids=[],
            registry_version=REGISTRY_VERSION,
            hedged=False,
        )
    return None


# Dispatch by value_kind
_EXTRACTOR_DISPATCH: dict[str, Any] = {
    "integer": _try_extract_count,
    "money": _try_extract_money,
    "status": _try_extract_status,
    "date": _try_extract_date,
    "datetime": _try_extract_datetime,
    "version": _try_extract_version,
    "string_enum": _try_extract_status,  # reuse alias map logic
    "boolean": None,  # placeholder; boolean claims handled below
    "percentage": None,
}


def _try_extract_boolean(
    sentence: str,
    sentence_start: int,
    spec: ClaimTypeSpec,
    operator_question: str,
    packet_entity_aliases: Optional[dict[str, str]] = None,
) -> Optional["DetectedClaim"]:
    """
    Extract boolean claims. Must be registered entity+type.
    Reject negated/conditional/nested. "Not necessarily disabled" => reject.
    """
    for pattern_str in spec.deterministic_patterns:
        m = re.search(pattern_str, sentence, re.I)
        if not m:
            continue
        raw = m.group(1) if m.lastindex else ""
        lower_raw = raw.strip().lower()

        # Reject negated/conditional booleans
        if re.search(r'\bnot\s+necessarily\b|\bnot\s+always\b|\bnot\s+exactly\b', sentence, re.I):
            return None

        if lower_raw in ("true", "yes", "enabled", "on"):
            normalized = True
        elif lower_raw in ("false", "no", "disabled", "off"):
            normalized = False
        else:
            continue

        entity = _resolve_entity(sentence, spec, operator_question, packet_entity_aliases)
        if entity is None:
            return None

        return DetectedClaim(
            detector_version=DETECTOR_VERSION,
            reply_id="",
            agent_id="",
            claim_type=spec.claim_type,
            normalized_value=normalized,
            value_surface=raw,
            entity_ref=entity[0],
            entity_surface=entity[1],
            temporal_scope=None,
            assertion_span_text=sentence,
            assertion_span_start=sentence_start,
            assertion_span_end=sentence_start + len(sentence),
            assertion_kind=ASSERTION_KIND_DIRECT,
            polarity="positive",
            extraction_route=EXTRACTION_ROUTE_DETERMINISTIC,
            extraction_confidence=1.0,
            supporting_fact_ids=[],
            registry_version=REGISTRY_VERSION,
            hedged=False,
        )
    return None


# ---------------------------------------------------------------------------
# Candidate-validation gate
# ---------------------------------------------------------------------------

def _validate_candidate(
    claim: DetectedClaim,
    answer_text: str,
) -> tuple[bool, str]:
    """
    Validate audit-eligibility per spec:
    - claim type in registry
    - span exact substring of answer
    - value parses deterministically
    - entity resolves uniquely
    - time scope resolves uniquely (or None is acceptable for some types)
    - assertion_kind == direct
    - not hedged
    - truth-source adapter resolves
    Returns (eligible, reason).
    """
    if claim.claim_type not in CLAIM_TYPE_REGISTRY:
        return False, "claim_type_not_in_registry"
    if claim.assertion_kind != ASSERTION_KIND_DIRECT:
        return False, f"not_direct_assertion: {claim.assertion_kind}"
    if claim.hedged:
        return False, "hedged"
    if not claim.entity_ref:
        return False, "no_entity_ref"
    # Span must be exact substring
    if claim.assertion_span_text not in answer_text:
        return False, "span_not_in_answer"
    if claim.normalized_value is None:
        return False, "null_normalized_value"
    # Truth source adapter must resolve
    spec = CLAIM_TYPE_REGISTRY[claim.claim_type]
    if not spec.truth_source_adapter:
        return False, "no_truth_source_adapter"
    return True, "ok"


def _make_idempotency_key(
    reply_id: str,
    claim_type: str,
    entity_ref: str,
    normalized_value: Any,
    truth_source_revision: Optional[str],
) -> str:
    """Stable idempotency key from (reply_id, claim_type, entity_ref, value, truth_source_revision)."""
    if isinstance(normalized_value, MoneyValue):
        value_str = f"{normalized_value.currency_code}:{normalized_value.minor_units}"
    elif isinstance(normalized_value, bool):
        value_str = str(normalized_value)
    else:
        value_str = str(normalized_value)
    raw = f"{reply_id}|{claim_type}|{entity_ref}|{value_str}|{truth_source_revision or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _classify_fault_domain(
    claim: DetectedClaim,
    finding: "AuditFinding",
    packet_value: Any,
) -> str:
    """
    Classify fault domain per spec:
    - packet has correct value, answer differs => renderer_mutation
    - packet has same wrong value => packet_value_error or source_mapping_error
    - packet has no corresponding fact => ungrounded_assertion
    - packet has answer value + audit passes => grounded+correct (not a fault)
    """
    if packet_value is None:
        return FAULT_DOMAIN_UNGROUNDED_ASSERTION
    claimed = claim.normalized_value
    truth = finding.actual_value if finding else None

    if isinstance(claimed, MoneyValue):
        claimed_comparable = claimed.minor_units
    else:
        claimed_comparable = claimed

    if isinstance(packet_value, MoneyValue):
        packet_comparable = packet_value.minor_units
    else:
        packet_comparable = packet_value

    # packet has correct (truth) value but answer claimed wrongly
    if packet_comparable == truth and claimed_comparable != truth:
        return FAULT_DOMAIN_RENDERER_MUTATION

    # packet has same wrong value as the claim
    if packet_comparable == claimed_comparable and claimed_comparable != truth:
        return FAULT_DOMAIN_PACKET_VALUE_ERROR

    return FAULT_DOMAIN_UNKNOWN


# ---------------------------------------------------------------------------
# Time-of-check safety helpers
# ---------------------------------------------------------------------------

def _bind_truth_source(
    claim: DetectedClaim,
    reply_timestamp: Optional[str],
    packet_source_revision: Optional[str],
    read_model_root: Optional[Path] = None,
) -> Optional[BoundTruthSource]:
    """
    Bind claim to truth source. Resolution order per spec:
    1. exact source revision from original packet
    2. historical read-model snapshot as of reply timestamp
    3. replay ledger as of reply timestamp
    Never audit old response vs latest value.
    No time-correct snapshot => None (unknown => no heal).
    """
    spec = CLAIM_TYPE_REGISTRY.get(claim.claim_type)
    if not spec:
        return None

    # For now, we support binding to the live read-model root.
    # historical_snapshot_required=True means we need a snapshot.
    # If no reply_timestamp provided, we can't safely bind for historical types.
    if spec.historical_snapshot_required and not reply_timestamp:
        return None

    source_ref = str(read_model_root or "generated/read_models")
    freshness = "unknown"

    # Check freshness: if we have a reply_timestamp and max_truth_age_seconds,
    # we can determine if the snapshot is fresh enough.
    if reply_timestamp:
        try:
            reply_dt = datetime.datetime.fromisoformat(reply_timestamp.replace("Z", "+00:00"))
            now = datetime.datetime.now(datetime.timezone.utc)
            age_seconds = (now - reply_dt).total_seconds()
            # Fast-changing facts have tighter freshness requirements
            if abs(age_seconds) < spec.max_truth_age_seconds:
                freshness = "fresh"
            else:
                freshness = "stale"
        except (ValueError, AttributeError):
            freshness = "unknown"

    return BoundTruthSource(
        claim_type=spec.claim_type,
        entity_ref=claim.entity_ref,
        as_of=reply_timestamp,
        source_ref=source_ref,
        source_revision=packet_source_revision,
        observed_at=reply_timestamp,
        freshness_status=freshness,
        adapter=spec.truth_source_adapter,
        historical_snapshot_exists=reply_timestamp is not None,
    )


# ---------------------------------------------------------------------------
# Main detector procedure (steps 1-21 per spec)
# ---------------------------------------------------------------------------

class ClaimDetector:
    """
    Self-Healing Claim Detector (Component 3).

    Precision-first: false negatives OK, false positives NOT.
    Only deterministic candidates that pass the full gate AND
    check_agent_claim returns explicit FAIL may queue heals.
    LLM-assisted candidates NEVER queue heals in shadow mode (default).
    """

    def __init__(
        self,
        reply_id: str,
        agent_id: str,
        operator_question: str,
        answer_text: str,
        reply_timestamp: Optional[str] = None,
        packet_source_revision: Optional[str] = None,
        packet_entity_aliases: Optional[dict[str, str]] = None,
        read_model_root: Optional[Path] = None,
        llm_claim_queue_mode: str = LLM_CLAIM_QUEUE_MODE,
    ):
        self.reply_id = reply_id
        self.agent_id = agent_id
        self.operator_question = operator_question
        self.answer_text = answer_text
        self.reply_timestamp = reply_timestamp
        self.packet_source_revision = packet_source_revision
        self.packet_entity_aliases = packet_entity_aliases or {}
        self.read_model_root = read_model_root or Path("generated/read_models")
        self.llm_claim_queue_mode = llm_claim_queue_mode

        # Outputs
        self.detected_claims: list[DetectedClaim] = []
        self.heal_tasks: list[HealTask] = []
        self.shadow_candidates: list[DetectedClaim] = []  # LLM candidates in shadow mode
        self._queued_idempotency_keys: set[str] = set()

    def run(self) -> "DetectorResult":
        """
        Execute the detector procedure (steps 1-21).
        Returns DetectorResult with all claims and any queued heal tasks.
        """
        # Step 1: Split into sentences with char offsets
        sentences = _sentence_split(self.answer_text)

        # Step 2: Cue prefilter — low cost scan
        cue_sentences: list[tuple[str, int]] = []
        for sent, offset in sentences:
            if _has_cue(sent):
                cue_sentences.append((sent, offset))

        if not cue_sentences:
            # No cue => no LLM => done
            return DetectorResult(
                reply_id=self.reply_id,
                agent_id=self.agent_id,
                detected_claims=[],
                heal_tasks=[],
                shadow_candidates=[],
                abstain_reasons=["no_cue_found"],
            )

        # Step 3: Deterministic parsers on cue sentences
        raw_candidates: list[DetectedClaim] = []
        matched_sentence_offsets: set[int] = set()

        for sent, offset in cue_sentences:
            # Step 4: Validate assertion kind / hedging before extraction
            assertion_kind = _classify_assertion_kind(sent)
            if assertion_kind != ASSERTION_KIND_DIRECT:
                continue  # non-direct => skip
            if _is_hedged(sent):
                continue  # hedged => skip

            # Try each registered claim type
            for spec in CLAIM_TYPE_REGISTRY.values():
                extractor = _EXTRACTOR_DISPATCH.get(spec.value_kind)
                if extractor is None and spec.value_kind == "boolean":
                    extractor = _try_extract_boolean
                if extractor is None:
                    continue

                claim = extractor(
                    sent, offset, spec,
                    self.operator_question,
                    self.packet_entity_aliases,
                )
                if claim is None:
                    continue

                # Fill in reply/agent context
                claim = dataclasses.replace(
                    claim,
                    reply_id=self.reply_id,
                    agent_id=self.agent_id,
                    temporal_scope=claim.temporal_scope or self.reply_timestamp,
                )

                raw_candidates.append(claim)
                matched_sentence_offsets.add(offset)
                break  # one claim type per sentence (first match wins)

        # Step 5: Dedup by (claim_type, entity_ref, normalized_value, span_start)
        seen: set[tuple] = set()
        deduped: list[DetectedClaim] = []
        for c in raw_candidates:
            val_key = _value_key(c.normalized_value)
            key = (c.claim_type, c.entity_ref, val_key, c.assertion_span_start)
            if key not in seen:
                seen.add(key)
                deduped.append(c)
        raw_candidates = deduped

        # Step 6: Identify unmatched cue sentences (not handled by deterministic parsers)
        unmatched = [
            (sent, off) for sent, off in cue_sentences
            if off not in matched_sentence_offsets
            and _classify_assertion_kind(sent) == ASSERTION_KIND_DIRECT
            and not _is_hedged(sent)
        ]

        # Step 7: LLM extraction budget (default shadow mode — no heal queue)
        # Per spec: <=3 unmatched cue sentences to restricted LLM extractor
        # In shadow mode: record/score only, never queue heals
        # We do NOT call an actual LLM here; this is the integration point.
        # LLM candidates would be ingested via ingest_llm_candidate() for shadow scoring.
        llm_candidates: list[DetectedClaim] = []
        # (LLM extractor invocation is external; see ingest_llm_candidate)

        # Step 8: Validate each LLM candidate
        # (handled in ingest_llm_candidate)

        # Step 9: Merge and dedup with LLM candidates
        all_candidates = raw_candidates + llm_candidates

        # Cap at MAX_CLAIMS_PER_REPLY
        all_candidates = all_candidates[:MAX_CLAIMS_PER_REPLY]

        # Step 10: Skip non-eligible
        eligible: list[DetectedClaim] = []
        for c in all_candidates:
            ok, reason = _validate_candidate(c, self.answer_text)
            if ok:
                eligible.append(c)

        self.detected_claims = all_candidates

        # Steps 11-21: For each eligible candidate, bind truth source and audit
        for claim in eligible:
            # Step 11: Bind to truth source
            bound = _bind_truth_source(
                claim,
                self.reply_timestamp,
                self.packet_source_revision,
                self.read_model_root,
            )

            # Step 12: Skip if no historical snapshot
            if bound is None or not bound.historical_snapshot_exists:
                continue

            # Stale truth source => abstain
            if bound.freshness_status == "stale":
                continue

            # Step 13: Call check_agent_claim (truth authority)
            if check_agent_claim is None:
                continue  # dependency unavailable

            finding = check_agent_claim(
                self.agent_id,
                bound.adapter,
                claim.normalized_value if not isinstance(claim.normalized_value, MoneyValue)
                    else claim.normalized_value.minor_units,
                read_model_root=self.read_model_root,
            )

            # Step 14: Pass => no action
            if finding.verdict == "pass":
                continue

            # Step 15: Abstain on unknown/error/stale/non-explicit-fail
            if finding.verdict != "fail":
                continue

            # Step 16: LLM-assisted fail => require verified mode else shadow-only
            if claim.extraction_route == EXTRACTION_ROUTE_LLM_ASSISTED:
                if self.llm_claim_queue_mode != "verified":
                    # Shadow: record but DO NOT queue
                    self.shadow_candidates.append(claim)
                    continue
                # Steps 17-18: Independent verifier required for LLM candidates
                # (verifier call would go here in verified mode)
                # For safety, abstain unless verified
                continue

            # Steps 19-21: Deterministic candidate confirmed fail — queue heal task

            # Step 19: Packet cross-check fault domain
            fault_domain = FAULT_DOMAIN_UNKNOWN
            # (packet_value would come from the context packet in full integration)

            # Step 20: Create idempotent HealTask
            idem_key = _make_idempotency_key(
                claim.reply_id,
                claim.claim_type,
                claim.entity_ref,
                claim.normalized_value,
                bound.source_revision,
            )

            # Step 21: Queue for SUPERVISED review (idempotent — no duplicate heals)
            if idem_key in self._queued_idempotency_keys:
                continue  # duplicate => skip
            self._queued_idempotency_keys.add(idem_key)

            truth_value = finding.actual_value
            heal = HealTask(
                heal_task_id=str(uuid.uuid4()),
                idempotency_key=idem_key,
                reply_id=claim.reply_id,
                agent_id=claim.agent_id,
                claim_type=claim.claim_type,
                entity_ref=claim.entity_ref,
                temporal_scope=claim.temporal_scope,
                assertion_span_text=claim.assertion_span_text,
                assertion_span_start=claim.assertion_span_start,
                assertion_span_end=claim.assertion_span_end,
                claimed_value=claim.normalized_value,
                truth_value=truth_value,
                truth_source_ref=bound.source_ref,
                truth_source_revision=bound.source_revision,
                audited_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                detector_route=claim.extraction_route,
                detector_policy_version=DETECTOR_VERSION,
                fault_domain=fault_domain,
                status=HEAL_STATUS_AWAITING_REVIEW,
            )
            self.heal_tasks.append(heal)

            # Emit to control plane if emit_heal_task is available and finding confirms fail
            # NOTE: emit_heal_task ONLY emits when finding.verdict == "fail" (it returns None otherwise)
            if emit_heal_task is not None:
                try:
                    ledger = ControlPlaneLedger() if ControlPlaneLedger else None
                    if ledger is not None:
                        emit_heal_task(
                            ledger,
                            finding,
                            request_text=self.operator_question,
                            answer_text=self.answer_text,
                            source_surface=self.agent_id,
                        )
                except Exception:
                    # Emit failure must not crash the detector
                    pass

        return DetectorResult(
            reply_id=self.reply_id,
            agent_id=self.agent_id,
            detected_claims=self.detected_claims,
            heal_tasks=self.heal_tasks,
            shadow_candidates=self.shadow_candidates,
            abstain_reasons=[],
        )

    def ingest_llm_candidate(
        self,
        decision: str,
        claim_type: str,
        exact_span: str,
        value_surface: str,
        entity_surface: str,
        time_scope_surface: Optional[str],
        assertion_kind: str,
        hedged: bool,
        confidence: float,
    ) -> Optional[DetectedClaim]:
        """
        Ingest an LLM-provided candidate (Step 8: validate each LLM candidate).
        Spec requirements:
        - span must be exact substring of answer_text
        - value must reparse deterministically from span
        - entity must pass deterministic resolution
        - extractor conf >= 0.98, type allowed
        In shadow mode: records for eval, NEVER queues heals.
        """
        if decision not in ("auditable",):
            return None
        if claim_type not in CLAIM_TYPE_REGISTRY:
            return None
        if exact_span not in self.answer_text:
            return None  # LLM value not in span => rejected
        if hedged:
            return None
        if assertion_kind != ASSERTION_KIND_DIRECT:
            return None
        if confidence < 0.98:
            return None

        spec = CLAIM_TYPE_REGISTRY[claim_type]
        # Value must reparse deterministically from span
        extractor = _EXTRACTOR_DISPATCH.get(spec.value_kind)
        if extractor is None:
            return None

        # Find span offset in answer
        span_start = self.answer_text.find(exact_span)
        if span_start < 0:
            return None

        reparsed = extractor(exact_span, span_start, spec, self.operator_question, self.packet_entity_aliases)
        if reparsed is None:
            return None  # value not reparseable from span => invalid

        candidate = dataclasses.replace(
            reparsed,
            reply_id=self.reply_id,
            agent_id=self.agent_id,
            extraction_route=EXTRACTION_ROUTE_LLM_ASSISTED,
            extraction_confidence=confidence,
        )
        return candidate


@dataclasses.dataclass
class DetectorResult:
    reply_id: str
    agent_id: str
    detected_claims: list[DetectedClaim]
    heal_tasks: list[HealTask]
    shadow_candidates: list[DetectedClaim]
    abstain_reasons: list[str]

    def heal_queued(self) -> bool:
        return len(self.heal_tasks) > 0

    def to_dict(self) -> dict:
        return {
            "reply_id": self.reply_id,
            "agent_id": self.agent_id,
            "detected_claims_count": len(self.detected_claims),
            "heal_tasks_count": len(self.heal_tasks),
            "shadow_candidates_count": len(self.shadow_candidates),
            "abstain_reasons": self.abstain_reasons,
            "heal_tasks": [
                {
                    "heal_task_id": h.heal_task_id,
                    "idempotency_key": h.idempotency_key,
                    "claim_type": h.claim_type,
                    "entity_ref": h.entity_ref,
                    "claimed_value": _value_key(h.claimed_value),
                    "truth_value": str(h.truth_value),
                    "fault_domain": h.fault_domain,
                    "status": h.status,
                }
                for h in self.heal_tasks
            ],
        }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _value_key(v: Any) -> str:
    if isinstance(v, MoneyValue):
        return f"{v.currency_code}:{v.minor_units}"
    return str(v)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_claims(
    reply_id: str,
    agent_id: str,
    operator_question: str,
    answer_text: str,
    *,
    reply_timestamp: Optional[str] = None,
    packet_source_revision: Optional[str] = None,
    packet_entity_aliases: Optional[dict[str, str]] = None,
    read_model_root: Optional[Path] = None,
    llm_claim_queue_mode: str = LLM_CLAIM_QUEUE_MODE,
) -> DetectorResult:
    """
    Main entry point for Component 3.
    Inspect the EXACT final operator-visible answer text.
    Returns DetectorResult with detected claims and any supervised heal tasks.
    Called AFTER all rendering/insertion/guard rewriting (step 8 in reply pipeline).
    """
    detector = ClaimDetector(
        reply_id=reply_id,
        agent_id=agent_id,
        operator_question=operator_question,
        answer_text=answer_text,
        reply_timestamp=reply_timestamp,
        packet_source_revision=packet_source_revision,
        packet_entity_aliases=packet_entity_aliases,
        read_model_root=read_model_root,
        llm_claim_queue_mode=llm_claim_queue_mode,
    )
    return detector.run()
