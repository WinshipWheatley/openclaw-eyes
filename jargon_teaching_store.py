"""
Jargon-Teaching Store — Component 2 of the Three-Component Engineering Spec.

Ledger storage choice: append-only JSONL file at .openclaw/jargon/term_events.jsonl
Rationale: simpler than SQLite for this domain (no FK constraints needed, no cross-table
joins required). Idempotency enforced by (reply_id, term_id, event_type) uniqueness for
teaching events and (operator_turn_id, term_id, TERM_CORRECT_USE_CONFIRMED) for validated
uses. The projector tracks last_applied_event_seq per (operator_id, term_id) row to ensure
events are applied exactly once and in order.

TRUTH FIRST: Runtime NEVER authors or paraphrases a definition. Only exact verified catalog
wording is used. Missing/stale/rejected/unverified terms use substitute plain or BLOCK.
Teaching metadata never enters grounded operational facts.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────────────────────────

LEARNING_EXPIRY_DAYS = int(os.environ.get("OPENCLAW_JARGON_LEARNING_EXPIRY_DAYS", "180"))
REFRESHER_THRESHOLD_DAYS = int(os.environ.get("OPENCLAW_JARGON_REFRESHER_DAYS", "90"))

VERIFIED_TERM_CATALOG_PATH = Path("generated/read_models/verified_term_catalog.json")
OPERATOR_TERM_KNOWLEDGE_PATH = Path("generated/read_models/operator_term_knowledge.json")
JARGON_LEDGER_PATH = Path(".openclaw/jargon/term_events.jsonl")


# ────────────────────────────────────────────────────────────────────────────────
# Ledger event types (spec §Component 2)
# ────────────────────────────────────────────────────────────────────────────────

TERM_TAUGHT_FULL = "TERM_TAUGHT_FULL"
TERM_TAUGHT_BRIEF = "TERM_TAUGHT_BRIEF"
TERM_USED_PLAIN = "TERM_USED_PLAIN"
TERM_ACKNOWLEDGED = "TERM_ACKNOWLEDGED"
TERM_CORRECT_USE_CONFIRMED = "TERM_CORRECT_USE_CONFIRMED"
TERM_DEFINITION_REQUESTED = "TERM_DEFINITION_REQUESTED"
TERM_MISUSE_CONFIRMED = "TERM_MISUSE_CONFIRMED"
TERM_LEARNING_EXPIRED = "TERM_LEARNING_EXPIRED"
TERM_CONCEPT_VERSION_CHANGED = "TERM_CONCEPT_VERSION_CHANGED"

ALL_EVENT_TYPES = {
    TERM_TAUGHT_FULL,
    TERM_TAUGHT_BRIEF,
    TERM_USED_PLAIN,
    TERM_ACKNOWLEDGED,
    TERM_CORRECT_USE_CONFIRMED,
    TERM_DEFINITION_REQUESTED,
    TERM_MISUSE_CONFIRMED,
    TERM_LEARNING_EXPIRED,
    TERM_CONCEPT_VERSION_CHANGED,
}

# Status values
STATUS_UNKNOWN = "unknown"
STATUS_LEARNING = "learning"
STATUS_KNOWN = "known"

# Status reason values
REASON_UNSEEN = "unseen"
REASON_FIRST_TAUGHT = "first_taught"
REASON_REINFORCEMENT = "reinforcement"
REASON_EXPLICIT_ACK = "explicit_ack"
REASON_CORRECT_USE_THRESHOLD = "correct_use_threshold"
REASON_DEFINITION_REQUESTED = "definition_requested"
REASON_CONFIRMED_MISUSE = "confirmed_misuse"
REASON_LEARNING_EXPIRED = "learning_expired"
REASON_CONCEPT_VERSION_CHANGED = "concept_version_changed"

# Teaching modes
MODE_FULL = "full"
MODE_BRIEF = "brief"
MODE_PLAIN = "plain"
MODE_SUBSTITUTE = "substitute"
MODE_BLOCKED = "blocked"

# Insertion policies
INSERT_AFTER_FIRST_USE = "after_first_use"
INSERT_REPLACE_WITH_PLAIN = "replace_with_plain"
INSERT_NONE = "none"

# Verification statuses
VSTATUS_DRAFT = "draft"
VSTATUS_VERIFIED = "verified"
VSTATUS_STALE = "stale"
VSTATUS_REJECTED = "rejected"


# ────────────────────────────────────────────────────────────────────────────────
# Data schemas (spec §Component 2)
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class VerifiedTermCatalogEntry:
    """
    Immutable catalog entry describing a verified term and its approved wording.
    Only verified entries (verification_status == "verified") reach the operator.
    wording-only edit ++wording_version, doesn't touch operator knowledge.
    meaning/scope change ++concept_version; prior-version knowledge must NOT silently transfer.
    """
    term_id: str
    canonical_surface: str
    aliases: list[str]
    domain: str
    concept_version: int                      # ++ on meaning/scope change
    wording_version: int                      # ++ on wording-only change
    precise_definition: str                   # exact operator-visible wording
    eli5_full: str                            # full eli5 explanation (exact wording)
    eli5_brief: str                           # brief reminder (exact wording)
    plain_replacement: Optional[str]          # fallback plain language
    definition_dependencies: list[str]        # list of term_ids this def depends on
    usage_validator_id: Optional[str]         # deterministic validator ref
    source_refs: list[str]                    # citations for this definition
    verification_status: str                  # draft|verified|stale|rejected
    verified_by: Optional[str]
    verified_at: Optional[str]

    def is_safe_to_teach(self) -> bool:
        """Only verified entries may be taught. TRUTH FIRST."""
        return self.verification_status == VSTATUS_VERIFIED


@dataclass
class OperatorTermKnowledge:
    """
    Per-operator learning state for a single term.
    PK: (operator_id, term_id). Absent row = unknown.
    Counters apply to current concept_version only.
    """
    operator_id: str
    term_id: str
    concept_version: int                       # concept_version at last teaching event
    status: str                                # unknown|learning|known
    status_reason: str                         # see REASON_* constants
    exposure_count: int = 0
    full_teach_count: int = 0
    brief_teach_count: int = 0
    correct_use_count: int = 0
    unprompted_correct_use_count: int = 0
    explicit_ack_at: Optional[str] = None
    last_exposed_at: Optional[str] = None
    last_taught_at: Optional[str] = None
    last_taught_mode: Optional[str] = None    # full|brief|null
    last_correct_use_at: Optional[str] = None
    known_at: Optional[str] = None
    learning_expires_at: Optional[str] = None
    updated_at: str = field(default_factory=lambda: _now_iso())
    row_version: int = 1
    last_applied_event_seq: int = 0           # idempotency: projector ignores <= this seq


# ────────────────────────────────────────────────────────────────────────────────
# TermRequirement — planning input (spec §Component 2)
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class TermRequirement:
    """
    Describes a term that may appear in an agent reply.
    Generated from grounded fact types, action schemas, verified domain term maps,
    explicit operator requests, reviewed comedy templates.
    """
    term_id: str
    preferred_surface: str
    necessity: str                             # "required" | "optional"
    supporting_fact_ids: list[str]
    plain_replacement: Optional[str]           # caller-supplied plain language
    definition_requested: bool = False         # operator explicitly asked for definition


# ────────────────────────────────────────────────────────────────────────────────
# TermTeachingHint — planning output (spec §Component 2)
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class TermTeachingHint:
    """
    Added to context_packet.render_hints.term_teaching.
    Tells the renderer exactly how to handle each term.
    """
    term_id: str
    surface_form: str
    mode: str                                  # full|brief|plain|substitute|blocked
    supporting_fact_ids: list[str]
    definition_fact_id: Optional[str]          # grounded fact ID carrying the def
    allowed_surface_forms: list[str]           # canonical + aliases when allowed
    insertion_policy: str                      # after_first_use|replace_with_plain|none


# ────────────────────────────────────────────────────────────────────────────────
# Ledger (append-only JSONL)
# ────────────────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_ledger_path(ledger_path: Optional[Path] = None) -> Path:
    return ledger_path or JARGON_LEDGER_PATH


def _resolve_catalog_path(catalog_path: Optional[Path] = None) -> Path:
    return catalog_path or VERIFIED_TERM_CATALOG_PATH


def _resolve_knowledge_path(knowledge_path: Optional[Path] = None) -> Path:
    return knowledge_path or OPERATOR_TERM_KNOWLEDGE_PATH


def _load_json_file(path: Path, default: Any) -> Any:
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load %s: %s", path, exc)
    return default


def _save_json_file(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _load_ledger_events(ledger_path: Optional[Path] = None) -> list[dict[str, Any]]:
    """Load all events from the JSONL ledger."""
    path = _resolve_ledger_path(ledger_path)
    if not path.is_file():
        return []
    events = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    logger.warning("Malformed ledger line: %s — %s", line[:80], exc)
    except Exception as exc:
        logger.error("Failed to read ledger: %s", exc)
    return events


def _check_uniqueness(
    new_event: dict[str, Any],
    existing_events: list[dict[str, Any]],
) -> bool:
    """
    Returns True if the event is unique (safe to append).
    Uniqueness rules per spec:
    - Teaching events: (reply_id, term_id, event_type)
    - TERM_CORRECT_USE_CONFIRMED: (operator_turn_id, term_id, event_type)
    """
    et = new_event.get("event_type")
    term_id = new_event.get("term_id")

    if et == TERM_CORRECT_USE_CONFIRMED:
        key = (new_event.get("operator_turn_id"), term_id, et)
        for ev in existing_events:
            if (ev.get("operator_turn_id"), ev.get("term_id"), ev.get("event_type")) == key:
                return False
    elif et in {TERM_TAUGHT_FULL, TERM_TAUGHT_BRIEF, TERM_USED_PLAIN, TERM_ACKNOWLEDGED,
                TERM_DEFINITION_REQUESTED, TERM_MISUSE_CONFIRMED}:
        key = (new_event.get("reply_id"), term_id, et)
        for ev in existing_events:
            if (ev.get("reply_id"), ev.get("term_id"), ev.get("event_type")) == key:
                return False

    return True


def append_term_event(
    event: dict[str, Any],
    ledger_path: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Append a single term event to the JSONL ledger.
    Returns the event dict with seq, event_id, and ts assigned.
    Does NOT enforce uniqueness — callers that need it should use append_unique_term_event.
    """
    path = _resolve_ledger_path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Assign sequence number
    existing_events = _load_ledger_events(ledger_path)
    seq = len(existing_events) + 1

    event = {
        **event,
        "event_id": event.get("event_id") or f"jte_{uuid.uuid4().hex[:12]}",
        "event_seq": seq,
        "ts": event.get("ts") or _now_iso(),
    }

    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")

    return event


def append_unique_term_event(
    event: dict[str, Any],
    ledger_path: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    """
    Append event only if it satisfies uniqueness constraints.
    Returns the appended event or None if duplicate.
    """
    existing = _load_ledger_events(ledger_path)
    if not _check_uniqueness(event, existing):
        logger.debug("Duplicate event suppressed: %s %s %s",
                     event.get("event_type"), event.get("term_id"), event.get("reply_id"))
        return None
    return append_term_event(event, ledger_path)


# ────────────────────────────────────────────────────────────────────────────────
# Read-model loaders
# ────────────────────────────────────────────────────────────────────────────────

def load_verified_term_catalog(
    catalog_path: Optional[Path] = None,
) -> dict[str, VerifiedTermCatalogEntry]:
    """Load verified term catalog from JSON read-model. Returns {term_id: entry}."""
    path = _resolve_catalog_path(catalog_path)
    raw = _load_json_file(path, {})

    # Support both {"terms": [...]} and {term_id: {...}} shapes
    entries: dict[str, VerifiedTermCatalogEntry] = {}
    items = raw.get("terms", raw) if isinstance(raw, dict) else []
    if isinstance(items, list):
        for item in items:
            try:
                entry = _dict_to_catalog_entry(item)
                entries[entry.term_id] = entry
            except Exception as exc:
                logger.warning("Skipping malformed catalog entry: %s", exc)
    elif isinstance(items, dict):
        for term_id, item in items.items():
            try:
                if "term_id" not in item:
                    item = {**item, "term_id": term_id}
                entry = _dict_to_catalog_entry(item)
                entries[entry.term_id] = entry
            except Exception as exc:
                logger.warning("Skipping malformed catalog entry %s: %s", term_id, exc)
    return entries


def _dict_to_catalog_entry(d: dict[str, Any]) -> VerifiedTermCatalogEntry:
    return VerifiedTermCatalogEntry(
        term_id=d["term_id"],
        canonical_surface=d["canonical_surface"],
        aliases=d.get("aliases") or [],
        domain=d.get("domain", ""),
        concept_version=int(d.get("concept_version", 1)),
        wording_version=int(d.get("wording_version", 1)),
        precise_definition=d["precise_definition"],
        eli5_full=d["eli5_full"],
        eli5_brief=d["eli5_brief"],
        plain_replacement=d.get("plain_replacement"),
        definition_dependencies=d.get("definition_dependencies") or [],
        usage_validator_id=d.get("usage_validator_id"),
        source_refs=d.get("source_refs") or [],
        verification_status=d.get("verification_status", VSTATUS_DRAFT),
        verified_by=d.get("verified_by"),
        verified_at=d.get("verified_at"),
    )


def load_operator_term_knowledge(
    operator_id: str,
    knowledge_path: Optional[Path] = None,
) -> dict[str, OperatorTermKnowledge]:
    """Load all knowledge rows for an operator. Returns {term_id: row}."""
    path = _resolve_knowledge_path(knowledge_path)
    raw = _load_json_file(path, {})

    rows: dict[str, OperatorTermKnowledge] = {}
    operator_data = raw.get(operator_id, {})
    for term_id, item in operator_data.items():
        try:
            rows[term_id] = _dict_to_knowledge_row(item)
        except Exception as exc:
            logger.warning("Skipping malformed knowledge row %s/%s: %s", operator_id, term_id, exc)
    return rows


def _dict_to_knowledge_row(d: dict[str, Any]) -> OperatorTermKnowledge:
    return OperatorTermKnowledge(
        operator_id=d["operator_id"],
        term_id=d["term_id"],
        concept_version=int(d.get("concept_version", 1)),
        status=d.get("status", STATUS_UNKNOWN),
        status_reason=d.get("status_reason", REASON_UNSEEN),
        exposure_count=int(d.get("exposure_count", 0)),
        full_teach_count=int(d.get("full_teach_count", 0)),
        brief_teach_count=int(d.get("brief_teach_count", 0)),
        correct_use_count=int(d.get("correct_use_count", 0)),
        unprompted_correct_use_count=int(d.get("unprompted_correct_use_count", 0)),
        explicit_ack_at=d.get("explicit_ack_at"),
        last_exposed_at=d.get("last_exposed_at"),
        last_taught_at=d.get("last_taught_at"),
        last_taught_mode=d.get("last_taught_mode"),
        last_correct_use_at=d.get("last_correct_use_at"),
        known_at=d.get("known_at"),
        learning_expires_at=d.get("learning_expires_at"),
        updated_at=d.get("updated_at", _now_iso()),
        row_version=int(d.get("row_version", 1)),
        last_applied_event_seq=int(d.get("last_applied_event_seq", 0)),
    )


def save_operator_term_knowledge(
    operator_id: str,
    rows: dict[str, OperatorTermKnowledge],
    knowledge_path: Optional[Path] = None,
) -> None:
    """Persist operator knowledge rows back to the read-model JSON file."""
    path = _resolve_knowledge_path(knowledge_path)
    raw = _load_json_file(path, {})
    if not isinstance(raw, dict):
        raw = {}

    serialized: dict[str, Any] = {}
    for term_id, row in rows.items():
        serialized[term_id] = asdict(row)

    raw[operator_id] = serialized
    _save_json_file(path, raw)


# ────────────────────────────────────────────────────────────────────────────────
# Projector — event sourced, idempotent
# ────────────────────────────────────────────────────────────────────────────────

def project_term_events(
    operator_id: str,
    ledger_path: Optional[Path] = None,
    knowledge_path: Optional[Path] = None,
    expiry_days: int = LEARNING_EXPIRY_DAYS,
) -> dict[str, OperatorTermKnowledge]:
    """
    Load all ledger events for operator_id and apply them to the knowledge rows.
    Idempotent: skips events with seq <= last_applied_event_seq per row.
    Returns the updated {term_id: OperatorTermKnowledge} dict.
    Does NOT persist — caller must call save_operator_term_knowledge.
    """
    rows = load_operator_term_knowledge(operator_id, knowledge_path)
    all_events = _load_ledger_events(ledger_path)

    # Filter to this operator's events, sorted by seq
    my_events = sorted(
        [e for e in all_events if e.get("operator_id") == operator_id],
        key=lambda e: e.get("event_seq", 0),
    )

    for event in my_events:
        seq = event.get("event_seq", 0)
        term_id = event.get("term_id", "")
        et = event.get("event_type", "")

        if not term_id or et not in ALL_EVENT_TYPES:
            continue

        # Get or create the knowledge row
        if term_id not in rows:
            rows[term_id] = OperatorTermKnowledge(
                operator_id=operator_id,
                term_id=term_id,
                concept_version=event.get("concept_version", 1),
                status=STATUS_UNKNOWN,
                status_reason=REASON_UNSEEN,
            )

        row = rows[term_id]

        # Idempotency: skip already-applied events
        if seq <= row.last_applied_event_seq:
            continue

        # Apply the event
        _apply_event_to_row(row, event, expiry_days)
        row.last_applied_event_seq = seq
        row.updated_at = _now_iso()
        row.row_version += 1

    return rows


def _apply_event_to_row(
    row: OperatorTermKnowledge,
    event: dict[str, Any],
    expiry_days: int = LEARNING_EXPIRY_DAYS,
) -> None:
    """
    Apply one event to one knowledge row (in-place).
    Per spec §Component 2 "Knowledge update (per event)".
    """
    et = event.get("event_type")
    now_str = event.get("ts") or _now_iso()
    now_dt = _parse_dt(now_str)

    if et == TERM_TAUGHT_FULL:
        # TAUGHT_FULL: learning/first_taught (or reinforcement), ++exposure, ++full_teach,
        # set last_exposed/taught, mode full, expires=+expiry_days
        event_cv = event.get("concept_version", row.concept_version)
        if row.concept_version != event_cv:
            _reset_for_concept_version(row, event_cv)
        first = (row.status == STATUS_UNKNOWN)
        row.status = STATUS_LEARNING
        row.status_reason = REASON_FIRST_TAUGHT if first else REASON_REINFORCEMENT
        row.exposure_count += 1
        row.full_teach_count += 1
        row.last_exposed_at = now_str
        row.last_taught_at = now_str
        row.last_taught_mode = MODE_FULL
        row.learning_expires_at = _add_days_iso(now_dt, expiry_days)

    elif et == TERM_TAUGHT_BRIEF:
        # TAUGHT_BRIEF: learning/reinforcement, ++exposure, ++brief_teach, mode brief, reset expires
        event_cv = event.get("concept_version", row.concept_version)
        if row.concept_version != event_cv:
            _reset_for_concept_version(row, event_cv)
        row.status = STATUS_LEARNING
        row.status_reason = REASON_REINFORCEMENT
        row.exposure_count += 1
        row.brief_teach_count += 1
        row.last_exposed_at = now_str
        row.last_taught_at = now_str
        row.last_taught_mode = MODE_BRIEF
        row.learning_expires_at = _add_days_iso(now_dt, expiry_days)

    elif et == TERM_USED_PLAIN:
        # USED_PLAIN: ++exposure, last_exposed (status unchanged)
        row.exposure_count += 1
        row.last_exposed_at = now_str

    elif et == TERM_ACKNOWLEDGED:
        # ACKNOWLEDGED: known/explicit_ack, set explicit_ack_at+known_at, clear expires
        row.status = STATUS_KNOWN
        row.status_reason = REASON_EXPLICIT_ACK
        row.explicit_ack_at = now_str
        row.known_at = now_str
        row.learning_expires_at = None

    elif et == TERM_CORRECT_USE_CONFIRMED:
        # ++correct_use, last_correct_use; if not prompted ++unprompted
        # if correct>=2 & unprompted>=1 -> known/correct_use_threshold
        row.correct_use_count += 1
        row.last_correct_use_at = now_str
        if event.get("unprompted", False):
            row.unprompted_correct_use_count += 1
        if row.correct_use_count >= 2 and row.unprompted_correct_use_count >= 1:
            row.status = STATUS_KNOWN
            row.status_reason = REASON_CORRECT_USE_THRESHOLD
            row.known_at = now_str
            row.learning_expires_at = None

    elif et == TERM_DEFINITION_REQUESTED:
        # -> learning/definition_requested, expires +expiry_days
        row.status = STATUS_LEARNING
        row.status_reason = REASON_DEFINITION_REQUESTED
        row.learning_expires_at = _add_days_iso(now_dt, expiry_days)

    elif et == TERM_MISUSE_CONFIRMED:
        # -> learning/confirmed_misuse, expires +expiry_days
        row.status = STATUS_LEARNING
        row.status_reason = REASON_CONFIRMED_MISUSE
        row.learning_expires_at = _add_days_iso(now_dt, expiry_days)

    elif et == TERM_LEARNING_EXPIRED:
        # learning -> unknown/learning_expired, clear expires
        if row.status == STATUS_LEARNING:
            row.status = STATUS_UNKNOWN
            row.status_reason = REASON_LEARNING_EXPIRED
            row.learning_expires_at = None

    elif et == TERM_CONCEPT_VERSION_CHANGED:
        # Reset to learning for new version, clear prior ack+correct-use counters
        new_cv = event.get("new_concept_version") or event.get("concept_version", row.concept_version + 1)
        _reset_for_concept_version(row, new_cv)


def _reset_for_concept_version(row: OperatorTermKnowledge, new_cv: int) -> None:
    """Reset knowledge to learning state for a new concept version (spec rule)."""
    row.concept_version = new_cv
    row.status = STATUS_LEARNING
    row.status_reason = REASON_CONCEPT_VERSION_CHANGED
    # Clear prior ack and correct-use counters (spec: "clear prior ack+correct-use counters")
    row.explicit_ack_at = None
    row.known_at = None
    row.correct_use_count = 0
    row.unprompted_correct_use_count = 0
    row.learning_expires_at = None  # will be set by the teaching event that follows


def _parse_dt(iso_str: str) -> datetime:
    """Parse ISO datetime string. Handles UTC 'Z' suffix and aware/naive."""
    try:
        s = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.now(timezone.utc)


def _add_days_iso(dt: datetime, days: int) -> str:
    return (dt + timedelta(days=days)).isoformat()


# ────────────────────────────────────────────────────────────────────────────────
# Effective status calculation (spec §Component 2)
# ────────────────────────────────────────────────────────────────────────────────

def calc_effective_status(
    row: Optional[OperatorTermKnowledge],
    catalog_entry: VerifiedTermCatalogEntry,
    now: Optional[datetime] = None,
) -> str:
    """
    Compute the operator's effective status for a term per spec rules:
    - missing row => unknown
    - record concept_version != catalog version => learning (revised teaching required)
    - learning & expired => unknown
    - else stored status
    Known does NOT decay with time (spec: "Known does NOT decay with time").
    """
    now = now or datetime.now(timezone.utc)

    if row is None:
        return STATUS_UNKNOWN

    # Concept version mismatch -> treat as learning (revised teaching required)
    if row.concept_version != catalog_entry.concept_version:
        return STATUS_LEARNING

    # Learning expiry check (does NOT apply to known status)
    if row.status == STATUS_LEARNING and row.learning_expires_at:
        expires_dt = _parse_dt(row.learning_expires_at)
        if now >= expires_dt:
            return STATUS_UNKNOWN

    return row.status


# ────────────────────────────────────────────────────────────────────────────────
# Explicit-ack recognition (spec §Component 2)
# ────────────────────────────────────────────────────────────────────────────────

def detect_explicit_ack(
    operator_text: str,
    catalog: dict[str, VerifiedTermCatalogEntry],
) -> list[str]:
    """
    Returns list of term_ids that operator_text explicitly acknowledges.
    MUST unambiguously name exactly one verified term to count.
    Bare "Got it / Okay / Makes sense" does NOT count.
    "Stop explaining <named term>" counts as ack.
    """
    text_lower = operator_text.lower()
    acked: list[str] = []

    ACK_PATTERNS = [
        "i know what {term} means",
        "mark {term} known",
        "stop defining {term}",
        "stop explaining {term}",
        "do not explain {term} again",
        "don't explain {term} again",
        "i understand {term}",
    ]

    for term_id, entry in catalog.items():
        surfaces = [entry.canonical_surface.lower()] + [a.lower() for a in entry.aliases]
        for surface in surfaces:
            for pattern in ACK_PATTERNS:
                if pattern.format(term=surface) in text_lower:
                    acked.append(term_id)
                    break
            else:
                continue
            break

    return list(set(acked))


# ────────────────────────────────────────────────────────────────────────────────
# TermTeachingPlanner (spec §Component 2 "Planner procedure" steps 1-12)
# ────────────────────────────────────────────────────────────────────────────────

def plan_term_teaching(
    operator_id: str,
    requirements: list[TermRequirement],
    catalog: dict[str, VerifiedTermCatalogEntry],
    knowledge_rows: dict[str, OperatorTermKnowledge],
    now: Optional[datetime] = None,
    refresher_threshold_days: int = REFRESHER_THRESHOLD_DAYS,
) -> list[TermTeachingHint]:
    """
    TermTeachingPlanner: steps 1-12 per spec.
    Returns list of TermTeachingHint (one per unique term_id).
    TRUTH FIRST: never invents a definition; missing/stale/rejected/unverified => substitute or block.
    """
    now = now or datetime.now(timezone.utc)
    hints: list[TermTeachingHint] = []
    seen_term_ids: set[str] = set()

    # Step 1: collect + dedup TermRequirements by term_id
    deduped: dict[str, TermRequirement] = {}
    for req in requirements:
        if req.term_id not in deduped:
            deduped[req.term_id] = req
        else:
            # Merge: required wins over optional; def request propagates
            existing = deduped[req.term_id]
            if req.necessity == "required":
                existing.necessity = "required"
            if req.definition_requested:
                existing.definition_requested = True

    for term_id, req in deduped.items():
        if term_id in seen_term_ids:
            continue
        seen_term_ids.add(term_id)

        # Step 2: load catalog entry
        entry = catalog.get(term_id)

        # Step 3: blocked if no entry or not verified (TRUTH FIRST)
        if entry is None or not entry.is_safe_to_teach():
            hint = _make_blocked_or_substitute_hint(req, entry)
            hints.append(hint)
            continue

        # Step 4: load operator knowledge
        row = knowledge_rows.get(term_id)

        # Step 5: calc effective status
        effective_status = calc_effective_status(row, entry, now)

        # Step 6: select mode per runtime rules
        mode = _select_mode(req, entry, row, effective_status, now, refresher_threshold_days)

        # Step 7: substitute => use requirement.plain_replacement then catalog.plain_replacement
        if mode == MODE_SUBSTITUTE:
            surface = req.plain_replacement or entry.plain_replacement or entry.canonical_surface
            hint = TermTeachingHint(
                term_id=term_id,
                surface_form=surface,
                mode=MODE_SUBSTITUTE,
                supporting_fact_ids=req.supporting_fact_ids,
                definition_fact_id=None,
                allowed_surface_forms=[surface] if surface else [],
                insertion_policy=INSERT_REPLACE_WITH_PLAIN,
            )
            hints.append(hint)
            continue

        if mode == MODE_BLOCKED:
            hint = _make_blocked_or_substitute_hint(req, entry)
            hints.append(hint)
            continue

        # Step 8: full/brief => create GROUNDED term-definition fact with EXACT catalog wording
        definition_fact_id: Optional[str] = None
        if mode in (MODE_FULL, MODE_BRIEF):
            definition_fact_id = _create_definition_fact_id(term_id, entry, mode)
            # Definition fact assembled by packet-extension using EXACT catalog wording (step 11)
            # Runtime LLM NEVER authors/paraphrases a definition.

        # Step 9: catalog source refs + version embedded in definition_fact_id / build_definition_grounded_fact

        # Step 10 + 11 + 12: build hint with permitted surface forms and insertion policy
        if effective_status == STATUS_KNOWN and mode == MODE_PLAIN:
            # known => canonical + aliases allowed
            allowed_surfaces = [entry.canonical_surface] + list(entry.aliases)
        elif mode in (MODE_FULL, MODE_BRIEF):
            # unknown/learning => allowed only when exact required explanation is adjacent
            allowed_surfaces = [entry.canonical_surface] + list(entry.aliases)
        else:
            allowed_surfaces = []

        insertion_policy = INSERT_AFTER_FIRST_USE if mode in (MODE_FULL, MODE_BRIEF) else INSERT_NONE

        hint = TermTeachingHint(
            term_id=term_id,
            surface_form=entry.canonical_surface,
            mode=mode,
            supporting_fact_ids=req.supporting_fact_ids,
            definition_fact_id=definition_fact_id,
            allowed_surface_forms=allowed_surfaces,
            insertion_policy=insertion_policy,
        )
        hints.append(hint)

    return hints


def _select_mode(
    req: TermRequirement,
    entry: VerifiedTermCatalogEntry,
    row: Optional[OperatorTermKnowledge],
    effective_status: str,
    now: datetime,
    refresher_threshold_days: int,
) -> str:
    """
    Select teaching mode per spec runtime rules:
    - required unknown => FULL
    - required learning & taught<90d => BRIEF
    - required learning & taught>=90d => FULL refresher
    - known => plain
    - operator asks for def => FULL regardless
    - optional & unknown => substitute (use plain replacement) or block
    """
    # Operator explicitly requested a definition => FULL regardless
    if req.definition_requested:
        return MODE_FULL

    if effective_status == STATUS_UNKNOWN:
        if req.necessity == "required":
            return MODE_FULL
        else:
            # optional & unknown => substitute with plain replacement if available
            if req.plain_replacement or entry.plain_replacement:
                return MODE_SUBSTITUTE
            else:
                return MODE_BLOCKED

    if effective_status == STATUS_LEARNING:
        if req.necessity == "required":
            # Check refresher threshold
            if row and row.last_taught_at:
                last_taught = _parse_dt(row.last_taught_at)
                days_since = (now - last_taught).days
                if days_since >= refresher_threshold_days:
                    return MODE_FULL  # refresher
            return MODE_BRIEF
        else:
            # optional + learning: allow plain use (operator has been taught)
            return MODE_PLAIN

    if effective_status == STATUS_KNOWN:
        return MODE_PLAIN

    # Fallback safety: block
    return MODE_BLOCKED


def _make_blocked_or_substitute_hint(
    req: TermRequirement,
    entry: Optional[VerifiedTermCatalogEntry],
) -> TermTeachingHint:
    """
    Create a BLOCKED or SUBSTITUTE hint when catalog entry is missing/unverified.
    TRUTH FIRST: never invent a definition.
    """
    plain = req.plain_replacement or (entry.plain_replacement if entry else None)
    if plain:
        return TermTeachingHint(
            term_id=req.term_id,
            surface_form=plain,
            mode=MODE_SUBSTITUTE,
            supporting_fact_ids=req.supporting_fact_ids,
            definition_fact_id=None,
            allowed_surface_forms=[plain],
            insertion_policy=INSERT_REPLACE_WITH_PLAIN,
        )
    return TermTeachingHint(
        term_id=req.term_id,
        surface_form="",
        mode=MODE_BLOCKED,
        supporting_fact_ids=req.supporting_fact_ids,
        definition_fact_id=None,
        allowed_surface_forms=[],
        insertion_policy=INSERT_NONE,
    )


def _create_definition_fact_id(
    term_id: str,
    entry: VerifiedTermCatalogEntry,
    mode: str,
) -> str:
    """
    Generate a stable fact ID for a grounded term-definition fact.
    Encodes term_id, concept_version, wording_version, and mode for traceability.
    """
    return f"def_fact_{term_id}_cv{entry.concept_version}_wv{entry.wording_version}_{mode}"


def build_definition_grounded_fact(
    term_id: str,
    entry: VerifiedTermCatalogEntry,
    mode: str,
) -> dict[str, Any]:
    """
    Assemble the grounded GroundedFact for a term definition using EXACT catalog wording.
    Per spec §Component 2 "Definition grounding":
    - Runtime LLM NEVER authors/paraphrases a definition
    - Loads exact verified catalog text, inserts deterministically
    - Cites versioned catalog source
    TRUTH FIRST invariant: value = exact catalog text, not any paraphrase.
    """
    fact_id = _create_definition_fact_id(term_id, entry, mode)
    if mode == MODE_FULL:
        approved_wording = entry.eli5_full
    else:
        approved_wording = entry.eli5_brief

    return {
        "fact_id": fact_id,
        "subject_ref": term_id,
        "predicate": "definition",
        "value": approved_wording,        # EXACT approved catalog wording — never paraphrased
        "value_type": "definition_text",
        "source_refs": entry.source_refs,
        "source_revision": f"cv{entry.concept_version}_wv{entry.wording_version}",
        "observed_at": entry.verified_at,
        "catalog_term_id": term_id,
        "catalog_concept_version": entry.concept_version,
        "catalog_wording_version": entry.wording_version,
        "teaching_metadata": True,         # NEVER enters grounded operational facts
        "definition_only": True,           # packet-extension only, not a business fact
    }


# ────────────────────────────────────────────────────────────────────────────────
# High-level API: record teaching events after confirmed delivery
# ────────────────────────────────────────────────────────────────────────────────

def record_teaching_events_after_delivery(
    operator_id: str,
    reply_id: str,
    delivered_hints: list[TermTeachingHint],
    ledger_path: Optional[Path] = None,
    knowledge_path: Optional[Path] = None,
) -> None:
    """
    Called ONLY after confirmed delivery of a reply.
    Appends ledger events for each taught/used term in the delivered text.
    One exposure per term per reply even if term appears multiple times (spec: "x5 in one reply = 1 exposure").
    Rejected/failed/retried/undelivered text => NO events appended.
    """
    for hint in delivered_hints:
        et = _mode_to_event_type(hint.mode)
        if et is None:
            continue
        event = {
            "event_type": et,
            "operator_id": operator_id,
            "term_id": hint.term_id,
            "reply_id": reply_id,
            "ts": _now_iso(),
        }
        append_unique_term_event(event, ledger_path)

    # Re-project and persist
    updated_rows = project_term_events(operator_id, ledger_path, knowledge_path)
    save_operator_term_knowledge(operator_id, updated_rows, knowledge_path)


def _mode_to_event_type(mode: str) -> Optional[str]:
    """Map teaching mode to ledger event type."""
    return {
        MODE_FULL: TERM_TAUGHT_FULL,
        MODE_BRIEF: TERM_TAUGHT_BRIEF,
        MODE_PLAIN: TERM_USED_PLAIN,
        MODE_SUBSTITUTE: None,     # substitute => no teaching exposure
        MODE_BLOCKED: None,        # blocked => no teaching exposure
    }.get(mode)


def record_acknowledgement_event(
    operator_id: str,
    term_id: str,
    reply_id: str,
    ledger_path: Optional[Path] = None,
    knowledge_path: Optional[Path] = None,
) -> None:
    """Record an explicit acknowledgement event for a single verified term."""
    event = {
        "event_type": TERM_ACKNOWLEDGED,
        "operator_id": operator_id,
        "term_id": term_id,
        "reply_id": reply_id,
        "ts": _now_iso(),
    }
    append_unique_term_event(event, ledger_path)
    updated_rows = project_term_events(operator_id, ledger_path, knowledge_path)
    save_operator_term_knowledge(operator_id, updated_rows, knowledge_path)


def record_correct_use_confirmed_event(
    operator_id: str,
    term_id: str,
    operator_turn_id: str,
    unprompted: bool,
    ledger_path: Optional[Path] = None,
    knowledge_path: Optional[Path] = None,
) -> None:
    """
    Record a confirmed correct-use event.
    ONLY called after deterministic validator confirms OR operator explicitly acks (spec rule).
    LLM may nominate but NOT commit correct-use — caller is responsible for validation gate.
    """
    event = {
        "event_type": TERM_CORRECT_USE_CONFIRMED,
        "operator_id": operator_id,
        "term_id": term_id,
        "operator_turn_id": operator_turn_id,
        "unprompted": unprompted,
        "ts": _now_iso(),
    }
    append_unique_term_event(event, ledger_path)
    updated_rows = project_term_events(operator_id, ledger_path, knowledge_path)
    save_operator_term_knowledge(operator_id, updated_rows, knowledge_path)


def record_concept_version_changed_event(
    operator_id: str,
    term_id: str,
    new_concept_version: int,
    ledger_path: Optional[Path] = None,
    knowledge_path: Optional[Path] = None,
) -> None:
    """
    Record a concept-version change event.
    Forces reset to learning for the operator; prior ack/correct-use counters cleared.
    """
    event = {
        "event_type": TERM_CONCEPT_VERSION_CHANGED,
        "operator_id": operator_id,
        "term_id": term_id,
        "new_concept_version": new_concept_version,
        "reply_id": f"system_{uuid.uuid4().hex[:8]}",
        "ts": _now_iso(),
    }
    # concept version changes don't need reply-scoped uniqueness
    append_term_event(event, ledger_path)
    updated_rows = project_term_events(operator_id, ledger_path, knowledge_path)
    save_operator_term_knowledge(operator_id, updated_rows, knowledge_path)


def record_learning_expired_event(
    operator_id: str,
    term_id: str,
    ledger_path: Optional[Path] = None,
    knowledge_path: Optional[Path] = None,
) -> None:
    """Record a learning-expired event (e.g. triggered by expiry check scheduler)."""
    event = {
        "event_type": TERM_LEARNING_EXPIRED,
        "operator_id": operator_id,
        "term_id": term_id,
        "reply_id": f"expiry_{uuid.uuid4().hex[:8]}",
        "ts": _now_iso(),
    }
    append_term_event(event, ledger_path)
    updated_rows = project_term_events(operator_id, ledger_path, knowledge_path)
    save_operator_term_knowledge(operator_id, updated_rows, knowledge_path)


# ────────────────────────────────────────────────────────────────────────────────
# Surface-guard term allowance check (spec §Component 2 "Surface-guard integration")
# ────────────────────────────────────────────────────────────────────────────────

def is_surface_term_allowed(
    surface: str,
    hint: TermTeachingHint,
) -> bool:
    """
    Returns True if the given surface form is allowed in the final rendered text.
    Per spec surface-guard rules:
    - known => canonical+aliases allowed
    - unknown/learning => allowed only when exact required explanation is adjacent (full/brief hint)
    - substituted => only plain replacement surface allowed
    - blocked => no catalog surface allowed
    """
    if hint.mode == MODE_BLOCKED:
        return False
    if hint.mode == MODE_SUBSTITUTE:
        return surface in hint.allowed_surface_forms
    return surface in hint.allowed_surface_forms


__all__ = [
    # Schemas
    "VerifiedTermCatalogEntry",
    "OperatorTermKnowledge",
    "TermRequirement",
    "TermTeachingHint",
    # Event types
    "TERM_TAUGHT_FULL",
    "TERM_TAUGHT_BRIEF",
    "TERM_USED_PLAIN",
    "TERM_ACKNOWLEDGED",
    "TERM_CORRECT_USE_CONFIRMED",
    "TERM_DEFINITION_REQUESTED",
    "TERM_MISUSE_CONFIRMED",
    "TERM_LEARNING_EXPIRED",
    "TERM_CONCEPT_VERSION_CHANGED",
    # Status / mode constants
    "STATUS_UNKNOWN", "STATUS_LEARNING", "STATUS_KNOWN",
    "MODE_FULL", "MODE_BRIEF", "MODE_PLAIN", "MODE_SUBSTITUTE", "MODE_BLOCKED",
    # Ledger
    "append_unique_term_event",
    "append_term_event",
    # Catalog/knowledge I/O
    "load_verified_term_catalog",
    "load_operator_term_knowledge",
    "save_operator_term_knowledge",
    # Projector
    "project_term_events",
    # Effective status
    "calc_effective_status",
    # Planner
    "plan_term_teaching",
    "build_definition_grounded_fact",
    # Ack detection
    "detect_explicit_ack",
    # High-level event recorders
    "record_teaching_events_after_delivery",
    "record_acknowledgement_event",
    "record_correct_use_confirmed_event",
    "record_concept_version_changed_event",
    "record_learning_expired_event",
    # Surface guard
    "is_surface_term_allowed",
    # Config
    "LEARNING_EXPIRY_DAYS",
    "REFRESHER_THRESHOLD_DAYS",
    "VSTATUS_VERIFIED",
    "VSTATUS_DRAFT",
    "VSTATUS_STALE",
    "VSTATUS_REJECTED",
]
