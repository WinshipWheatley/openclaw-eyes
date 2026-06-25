"""Deterministic context packet for Maestro's protected brain.

The packet is a compact, provenance-carrying view of current read models plus
operator-corrected truth. It is deliberately not a raw dump: the facts are
small, source-tagged, and safe for a gated model prompt.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping, Sequence


# ── Conversation-continuity flag (ADDITIVE, default OFF) ──────────────────────
def _continuity_enabled() -> bool:
    """Return True only when OPENCLAW_CONTINUITY_CAPSULE is "1" or "true"."""
    return os.environ.get("OPENCLAW_CONTINUITY_CAPSULE", "0").lower() in ("1", "true")


SCHEMA_VERSION = "maestro_context_packet_v0"
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
KNOWN_READ_MODELS = (
    "agent_presence.json",
    "openclaw_capability_index.json",
    "chief_status_rail.json",
    "openclaw_change_sentinel.json",
    "finance_invoice_reconciliation.json",
    "capital_hilton_invoice_operator_readback.json",
    "capital_hilton_invoice_operator_run_status.json",
    "cassandra_email_calendar_delta_detangle.json",
    "work_board.json",
    "orchestration_progress.json",
)

FINANCE_CONTEXT_TERMS = frozenset(
    {
        "bank",
        "business",
        "capital hilton",
        "coupa",
        "finance",
        "financial",
        "gig",
        "gigs",
        "invoice",
        "invoices",
        "money",
        "owed",
        "paid",
        "payment",
        "payments",
        "receivable",
        "receivables",
        "st anne",
        "st anne's",
        "st annes",
    }
)
LEDGER_ACTION_TERMS = frozenset(
    {
        "mark paid",
        "mutate",
        "pay",
        "post",
        "submit",
        "write",
    }
)


class MaestroContextPacketError(RuntimeError):
    """Raised when a packet would be empty or ungrounded."""


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _short_hash(payload: Any) -> str:
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()[:16]


def _compact(value: Any, *, limit: int = 900) -> str:
    text = " ".join(str(value or "").replace("\x00", " ").split()).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _session_path(session: Mapping[str, Any] | None, *keys: str) -> str:
    if not isinstance(session, Mapping):
        return ""
    for key in keys:
        value = session.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _read_model_root(session: Mapping[str, Any] | None, read_model_root: str | Path | None) -> Path:
    if read_model_root is not None:
        return Path(read_model_root)
    configured = _session_path(session, "read_model_root", "read_model_root_path", "generated_read_model_root")
    return Path(configured) if configured else DEFAULT_READ_MODEL_ROOT


def _operator_truth_store_path(
    session: Mapping[str, Any] | None,
    operator_truth_store_path: str | Path | None,
) -> Path | None:
    if operator_truth_store_path is not None:
        return Path(operator_truth_store_path)
    configured = _session_path(session, "operator_truth_store_path", "operator_truth_store")
    return Path(configured) if configured else None


def _display_read_model_ref(path: Path) -> str:
    if path.parts[-2:] and len(path.parts) >= 2 and path.parent.name == "read_models":
        return f"generated/read_models/{path.name}"
    return path.as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _freshness(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    generated_at = str(payload.get("generated_at") or payload.get("updated_at") or "").strip()
    if not generated_at:
        try:
            generated_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat()
        except OSError:
            generated_at = ""
    return {"as_of": generated_at, "source_ref": _display_read_model_ref(path)}


CALENDAR_EVENT_LIST_KEYS = (
    "upcoming_calendar_events",
    "calendar_events",
    "today_events",
    "events_today",
    "upcoming_events",
    "upcoming_commitments",
    "commitments",
)


def _append_fact(
    facts: list[dict[str, Any]],
    *,
    topic: str,
    label: str,
    value: str,
    source_ref: str,
    provenance: str,
    pii_tier: str = "PUBLIC",
    freshness: Mapping[str, Any] | None = None,
) -> None:
    clean_value = _compact(value)
    if not clean_value:
        return
    fact = {
        "fact_id": f"{topic}:{_short_hash((label, clean_value, source_ref))}",
        "topic": topic,
        "label": _compact(label, limit=160),
        "value": clean_value,
        "provenance": provenance,
        "freshness": dict(freshness or {}),
        "source_ref": source_ref,
        "pii_tier": str(pii_tier or "PUBLIC").upper(),
    }
    facts.append(fact)


def _calendar_event_rows(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for key in CALENDAR_EVENT_LIST_KEYS:
        value = payload.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            rows.extend(row for row in value if isinstance(row, Mapping))
    return rows


def _calendar_event_when(row: Mapping[str, Any]) -> str:
    start = str(
        row.get("start")
        or row.get("start_time")
        or row.get("start_at")
        or row.get("date_time")
        or row.get("date")
        or ""
    ).strip()
    end = str(row.get("end") or row.get("end_time") or row.get("end_at") or "").strip()
    if start and end:
        return f"{start}-{end}"
    return start or end


def _calendar_event_title(row: Mapping[str, Any]) -> str:
    return str(
        row.get("title")
        or row.get("summary")
        or row.get("name")
        or row.get("display_name")
        or row.get("description")
        or "calendar commitment"
    ).strip()


def _calendar_event_lines(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    lines: list[str] = []
    for row in rows:
        when = _calendar_event_when(row)
        title = _calendar_event_title(row)
        location = str(row.get("location") or row.get("where") or "").strip()
        status = str(row.get("status") or "").strip()
        parts = [part for part in (when, title, location, status) if part]
        line = " - ".join(parts)
        if line:
            lines.append(_compact(line, limit=220))
    return lines


def _operator_truth_facts(
    *,
    path: Path | None,
    question: str,
) -> tuple[list[dict[str, Any]], bool, str]:
    try:
        from operator_truth_store import load_operator_truth_store

        data = load_operator_truth_store(path=path, ensure_seed=True)
    except Exception:
        return [], False, str(path or "")

    entities = data.get("entities") if isinstance(data, Mapping) else {}
    if not isinstance(entities, Mapping):
        return [], False, str(path or "")

    records = [record for record in entities.values() if isinstance(record, Mapping)]
    records.sort(
        key=lambda record: (
            -int(record.get("precedence") or 0) if str(record.get("precedence") or "").isdigit() else 0,
            str(record.get("label") or record.get("entity_key") or ""),
        )
    )
    facts: list[dict[str, Any]] = []
    for record in records:
        source_ref = str(record.get("source_ref") or path or "operator_truth_store")
        label = str(record.get("label") or record.get("entity_key") or "Operator truth")
        _append_fact(
            facts,
            topic="operator_truth",
            label=label,
            value=str(record.get("value") or ""),
            provenance=str(record.get("provenance") or "operator_corrected"),
            source_ref=source_ref,
            pii_tier=str(record.get("pii_tier") or "LIGHT"),
            freshness={
                "as_of": str(record.get("at") or ""),
                "source_surface": str(record.get("source_surface") or ""),
                "precedence": record.get("precedence"),
            },
        )
    return facts, bool(facts), str(path or "")


def _read_model_facts(root: Path) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    refs: list[str] = []
    proof: dict[str, Any] = {"read_model_presence": {}}
    payloads: dict[str, dict[str, Any]] = {}
    for name in KNOWN_READ_MODELS:
        path = root / name
        payload = _read_json(path)
        proof["read_model_presence"][name] = bool(payload)
        if not payload:
            continue
        payloads[name] = payload
        refs.append(_display_read_model_ref(path))

    presence = payloads.get("agent_presence.json", {})
    agents = [row for row in presence.get("agents", ()) if isinstance(row, Mapping)]
    online = [row for row in agents if str(row.get("actual_state") or "").lower() == "online"]
    if agents:
        names = ", ".join(str(row.get("display_name") or row.get("agent_id") or "agent") for row in online[:8])
        _append_fact(
            facts,
            topic="agent_presence",
            label="Online agents",
            value=f"{len(online)} of {len(agents)} listed agents are online: {names or 'none listed online'}.",
            provenance="generated_read_model",
            source_ref=_display_read_model_ref(root / "agent_presence.json"),
            freshness=_freshness(root / "agent_presence.json", presence),
        )
    next_safe = str(presence.get("next_safe_move") or "").strip()
    if next_safe:
        _append_fact(
            facts,
            topic="agent_presence",
            label="Next safe move",
            value=next_safe,
            provenance="generated_read_model",
            source_ref=_display_read_model_ref(root / "agent_presence.json"),
            freshness=_freshness(root / "agent_presence.json", presence),
        )

    capability = payloads.get("openclaw_capability_index.json", {})
    capabilities = [row for row in capability.get("generic_capabilities", ()) if isinstance(row, Mapping)]
    live = [row for row in capabilities if str(row.get("capability_status") or "") == "LIVE_IMPLEMENTED"]
    read_only = [
        row
        for row in capabilities
        if str(row.get("capability_status") or "") in {"READ_MODEL_ONLY", "IMPLEMENTED_NON_EXECUTING"}
    ]
    if capabilities:
        live_names = ", ".join(str(row.get("capability_name") or row.get("capability_id")) for row in live[:5])
        ro_names = ", ".join(str(row.get("capability_name") or row.get("capability_id")) for row in read_only[:5])
        _append_fact(
            facts,
            topic="capability",
            label="Truthful capability posture",
            value=(
                f"{len(live)} live-implemented rails and {len(read_only)} safe readback/non-executing rails. "
                f"Live examples: {live_names or 'none'}. Readback examples: {ro_names or 'none'}."
            ),
            provenance="generated_read_model",
            source_ref=_display_read_model_ref(root / "openclaw_capability_index.json"),
            freshness=_freshness(root / "openclaw_capability_index.json", capability),
        )

    chief = payloads.get("chief_status_rail.json", {})
    chief_status = str(chief.get("chief_current_status") or "").strip()
    role = chief.get("chief_current_proven_role") if isinstance(chief.get("chief_current_proven_role"), Mapping) else {}
    role_summary = str(role.get("role_summary") or "").strip() if isinstance(role, Mapping) else ""
    if chief_status or role_summary:
        _append_fact(
            facts,
            topic="chief",
            label="Chief role boundary",
            value="; ".join(part for part in (chief_status, role_summary) if part),
            provenance="generated_read_model",
            source_ref=_display_read_model_ref(root / "chief_status_rail.json"),
            freshness=_freshness(root / "chief_status_rail.json", chief),
        )

    sentinel = payloads.get("openclaw_change_sentinel.json", {})
    summary = sentinel.get("hermes_summary") if isinstance(sentinel.get("hermes_summary"), Mapping) else {}
    sentinel_text = "; ".join(
        part
        for part in (
            str(summary.get("what_changed") or "").strip(),
            str(summary.get("what_to_do_next") or "").strip(),
        )
        if part
    )
    if sentinel_text:
        _append_fact(
            facts,
            topic="freshness",
            label="Change sentinel",
            value=sentinel_text,
            provenance="generated_read_model",
            source_ref=_display_read_model_ref(root / "openclaw_change_sentinel.json"),
            freshness=_freshness(root / "openclaw_change_sentinel.json", sentinel),
        )

    finance = payloads.get("finance_invoice_reconciliation.json", {})
    counts = finance.get("counts") if isinstance(finance.get("counts"), Mapping) else {}
    proposal = finance.get("first_safe_workflow_proposal") if isinstance(finance.get("first_safe_workflow_proposal"), Mapping) else {}
    if counts or proposal:
        _append_fact(
            facts,
            topic="finance_invoice_reconciliation",
            label="Finance and invoice posture",
            value=(
                f"Finance candidates: {counts.get('finance_candidate_count', 'unknown')}; "
                f"high-risk count: {counts.get('high_risk_count', 'unknown')}. "
                f"{proposal.get('operator_summary') or proposal.get('summary') or ''}"
            ),
            provenance="generated_read_model",
            source_ref=_display_read_model_ref(root / "finance_invoice_reconciliation.json"),
            pii_tier="LIGHT",
            freshness=_freshness(root / "finance_invoice_reconciliation.json", finance),
        )

    cap_run = payloads.get("capital_hilton_invoice_operator_run_status.json", {})
    if cap_run:
        notes = cap_run.get("automation_notes") if isinstance(cap_run.get("automation_notes"), Sequence) else ()
        _append_fact(
            facts,
            topic="invoice_status",
            label="Capital Hilton invoice run status",
            value=" ".join(str(item) for item in list(notes)[:4]) or "Capital Hilton invoice run status read model is present.",
            provenance="generated_read_model",
            source_ref=_display_read_model_ref(root / "capital_hilton_invoice_operator_run_status.json"),
            pii_tier="LIGHT",
            freshness=_freshness(root / "capital_hilton_invoice_operator_run_status.json", cap_run),
        )

    email_calendar = payloads.get("cassandra_email_calendar_delta_detangle.json", {})
    calendar_context = (
        email_calendar.get("calendar_operator_context")
        if isinstance(email_calendar.get("calendar_operator_context"), Mapping)
        else {}
    )
    classification_counts = (
        email_calendar.get("classification_counts")
        if isinstance(email_calendar.get("classification_counts"), Mapping)
        else {}
    )
    calendar_events = _calendar_event_lines(_calendar_event_rows(email_calendar))
    if calendar_events:
        _append_fact(
            facts,
            topic="calendar_day",
            label="Upcoming calendar commitments",
            value="; ".join(calendar_events[:8]),
            provenance="generated_read_model",
            source_ref=_display_read_model_ref(root / "cassandra_email_calendar_delta_detangle.json"),
            pii_tier="MED",
            freshness=_freshness(root / "cassandra_email_calendar_delta_detangle.json", email_calendar),
        )
    if calendar_context or classification_counts:
        _append_fact(
            facts,
            topic="email_calendar",
            label="Email and calendar bounded posture",
            value=(
                f"Calendar merged-context recorded: {bool(calendar_context.get('google_apple_calendar_merged_context_recorded'))}. "
                f"Live calendar access enabled: {bool(calendar_context.get('live_calendar_access_enabled'))}. "
                f"Classification counts: {dict(list(classification_counts.items())[:4])}."
            ),
            provenance="generated_read_model",
            source_ref=_display_read_model_ref(root / "cassandra_email_calendar_delta_detangle.json"),
            pii_tier="MED",
            freshness=_freshness(root / "cassandra_email_calendar_delta_detangle.json", email_calendar),
        )

    work_board = payloads.get("work_board.json", {})
    board_counts = work_board.get("counts_by_column") if isinstance(work_board.get("counts_by_column"), Mapping) else {}
    if board_counts:
        _append_fact(
            facts,
            topic="work_board",
            label="Current work board",
            value=f"Work board columns: {dict(board_counts)}.",
            provenance="generated_read_model",
            source_ref=_display_read_model_ref(root / "work_board.json"),
            freshness=_freshness(root / "work_board.json", work_board),
        )

    progress = payloads.get("orchestration_progress.json", {})
    milestones = [m for m in progress.get("shipped_milestones", ()) if isinstance(m, Mapping)]
    if milestones:
        recent = "; ".join(str(m.get("summary") or "").strip() for m in milestones[:6] if m.get("summary"))
        _append_fact(
            facts,
            topic="progress",
            label="Where we are at (recently shipped)",
            value=(
                f"{len(milestones)} recent engineering milestones on branch "
                f"{progress.get('branch', 'unknown')}. Most recent: {recent}."
            ),
            provenance="generated_read_model",
            source_ref=_display_read_model_ref(root / "orchestration_progress.json"),
            freshness=_freshness(root / "orchestration_progress.json", progress),
        )

    return facts, refs, proof


def _actionable_sections(facts: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    money: list[str] = []
    attention: list[str] = []
    upcoming: list[str] = []
    for fact in facts:
        label = str(fact.get("label") or "")
        value = str(fact.get("value") or "")
        text = f"{label}: {value}"
        lowered = text.lower()
        topic = str(fact.get("topic") or "").lower()
        if any(term in lowered for term in ("$", "paid", "owes", "invoice", "check", "receivable")):
            money.append(_compact(text, limit=260))
        if any(term in lowered for term in ("owes", "next invoice", "needs", "must", "blocked", "review", "follow-up", "follow up")):
            attention.append(_compact(text, limit=260))
        if topic == "calendar_day" or any(
            term in lowered for term in ("next friday", "2026-06-26", "2026-07-01", "upcoming", "in progress")
        ):
            upcoming.append(_compact(text, limit=260))
    return {
        "money_in_out": money[:8],
        "needs_attention": attention[:8],
        "upcoming_commitments": upcoming[:8],
    }


def _privacy_summary(facts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    tiers = sorted({str(fact.get("pii_tier") or "PUBLIC").upper() for fact in facts})
    return {
        "tiers_present": tiers or ["PUBLIC"],
        "legal_discovery_included": "MAX" in tiers,
        "legal_discovery_fully_tokenized": False,
        "send_hold_active": True,
        "outbound_action_allowed": False,
        "money_movement_allowed": False,
        "ledger_mutation_allowed": False,
        "notes": (
            "LIGHT finance/bank ledger facts may be reasoned over through the graded gate.",
            "Email/calendar/invoice facts are MED/LIGHT and remain read/process only.",
            "Legal Discovery is MAX and must be fully tokenized before model processing.",
        ),
    }


# ---------------------------------------------------------------------------
# SQLite canonical-facts source (DEFAULT-OFF; enabled by OPENCLAW_PACKET_SOURCE)
# ---------------------------------------------------------------------------

_SENSITIVITY_TO_PII_TIER: dict[str, str] = {
    # canonical_facts doc-sensitivity classes
    "public_canonical": "PUBLIC",
    "operational_canonical": "PUBLIC",
    "non_sensitive": "PUBLIC",
    # explicit PII tiers passed through unchanged if a fact is already tier-tagged
    "public": "PUBLIC",
    "light": "LIGHT",
    "med": "MED",
    "medium": "MED",
    "high": "HIGH",
    "max": "MAX",
    # known-sensitive doc classes fail TOWARD protection
    "sensitive": "HIGH",
    "confidential": "HIGH",
    "legal": "MAX",
    "legal_discovery": "MAX",
}
# Unknown sensitivity classes FAIL CLOSED to MAX (never silently downgrade to PUBLIC).
_PII_TIER_FAIL_CLOSED = "MAX"

_STOP_WORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "do", "for",
        "from", "has", "have", "i", "if", "in", "is", "it", "its", "my",
        "no", "not", "of", "on", "or", "so", "the", "to", "up", "was",
        "what", "when", "which", "who", "with", "would",
        # Question-filler / function words: keep these OUT of FTS match terms so
        # rare, meaningful terms (e.g. "routing", "escalation", "send_hold") drive
        # relevance instead of being crowded out under the candidate cap.
        "how", "should", "could", "can", "you", "your", "about", "this",
        "that", "these", "those", "we", "us", "our", "me", "tell", "give",
        "show", "need", "want", "does", "did", "will", "they", "them",
        "their", "there", "here", "get", "got", "use", "using", "choose",
        "vs", "versus", "any", "into", "but", "than", "then", "also",
        "just", "like", "make", "way", "etc", "via", "per", "been",
        "being", "had", "were", "now", "let",
    }
)

# Doctrine facts are ALWAYS-included as candidates (relevance-independent), so the
# candidate query for them must not truncate below the doctrine-set size — otherwise
# later-inserted doctrine (e.g. MS-* added after the 12 SD-*) silently falls out of
# reach. Final per-packet output is still bounded by the caller's `limit`.
_DOCTRINE_CANDIDATE_CAP = 64


def _extract_query_terms(question: str) -> list[str]:
    """Return significant lowercase tokens from question, stripping stop-words."""
    tokens = re.findall(r"[a-zA-Z0-9_']+", question.lower())
    return [t for t in tokens if t not in _STOP_WORDS and len(t) >= 3]


def _sqlite_canonical_facts(
    question: str,
    agent: str = "maestro",
    ledger_path: str | None = None,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Pull relevant facts from the canonical_facts SQLite ledger.

    DEFAULT-OFF: only called when build_maestro_context_packet is explicitly
    enabled via packet_source or OPENCLAW_PACKET_SOURCE.

    Rules:
    - Opens READ-ONLY via URI mode (file:...?mode=ro).
    - Returns [] gracefully on ANY error (missing file, locked db, etc.).
    - Includes facts where allowed_actors contains agent name or "all".
    - Always includes doctrine facts regardless of query relevance.
    - Deduplicates by content_hash; caps at limit.
    - NEVER writes to the ledger.
    """
    if not ledger_path:
        from business_ops_ledger import resolve_business_ops_ledger_path
        ledger_path = resolve_business_ops_ledger_path(None)

    try:
        db_file = Path(ledger_path)
        if not db_file.exists():
            return []

        uri = f"file:{db_file.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row

        # Verify required tables exist
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        # fts_canonical_facts is a virtual table (type='table' in sqlite_master for FTS5)
        has_canonical = "canonical_facts" in tables
        has_fts = "fts_canonical_facts" in tables
        if not has_canonical:
            conn.close()
            return []

        candidate_ids: list[str] = []
        seen_hashes: set[str] = set()

        # 1. FTS5 relevance search (if table present and query has terms)
        terms = _extract_query_terms(question)
        if has_fts and terms:
            # Build a safe FTS5 MATCH expression: quote each term to avoid
            # special-character injection; join with OR so partial matches work.
            fts_expr = " OR ".join(f'"{t}"' for t in terms[:8])
            try:
                # ORDER BY rank (bm25) so the MOST RELEVANT facts come first —
                # without it FTS returns rowid order, and newest-inserted facts
                # (e.g. MS-* added after SD-*) get truncated by LIMIT even when
                # they match the query's rare terms best.
                rows = conn.execute(
                    "SELECT fact_id FROM fts_canonical_facts WHERE fts_canonical_facts MATCH ? ORDER BY rank LIMIT ?",
                    (fts_expr, limit),
                ).fetchall()
                candidate_ids.extend(r["fact_id"] for r in rows)
            except sqlite3.OperationalError:
                # FTS match failure (e.g. bad token) → skip FTS, fall through to doctrine
                pass

        # 2. Always include doctrine facts (temporal_or_doctrine)
        doctrine_rows = conn.execute(
            """SELECT fact_id FROM canonical_facts
               WHERE temporal_or_doctrine = 'doctrine'
                  OR doc_category LIKE '%doctrine%'
               LIMIT ?""",
            (_DOCTRINE_CANDIDATE_CAP,),
        ).fetchall()
        for r in doctrine_rows:
            if r["fact_id"] not in candidate_ids:
                candidate_ids.append(r["fact_id"])

        if not candidate_ids:
            conn.close()
            return []

        # 3. Fetch full rows for candidates; apply allowed_actors filter; dedupe
        results: list[dict[str, Any]] = []
        for fact_id in candidate_ids:
            if len(results) >= limit:
                break
            row = conn.execute(
                """SELECT fact_text, sensitivity_class, allowed_actors, doc_category,
                          section_heading, source_file, content_hash, temporal_or_doctrine
                   FROM canonical_facts WHERE fact_id = ? LIMIT 1""",
                (fact_id,),
            ).fetchone()
            if row is None:
                continue
            chash = row["content_hash"] or ""
            if chash in seen_hashes:
                continue

            # allowed_actors filter: must contain agent or "all"
            raw_actors = row["allowed_actors"] or "[]"
            try:
                actors: list[str] = json.loads(raw_actors)
            except (json.JSONDecodeError, TypeError):
                actors = []
            if agent not in actors and "all" not in actors:
                continue

            seen_hashes.add(chash)
            sensitivity = str(row["sensitivity_class"] or "operational_canonical")
            pii_tier = _SENSITIVITY_TO_PII_TIER.get(sensitivity.strip().lower(), _PII_TIER_FAIL_CLOSED)
            source_file = str(row["source_file"] or "unknown")
            topic = str(row["doc_category"] or "canonical_facts")
            label = str(row["section_heading"] or fact_id)
            fact_list: list[dict[str, Any]] = []
            _append_fact(
                fact_list,
                topic=topic,
                label=label,
                value=str(row["fact_text"] or ""),
                source_ref="canonical_facts:" + source_file,
                provenance="canonical_facts",
                pii_tier=pii_tier,
            )
            results.extend(fact_list)

        conn.close()
        return results

    except Exception:  # noqa: BLE001 — never break packet building
        return []


def build_maestro_context_packet(
    *,
    question: str = "",
    session: Mapping[str, Any] | None = None,
    source_surface: str = "operator_maestro_chat",
    read_model_root: str | Path | None = None,
    operator_truth_store_path: str | Path | None = None,
    require_real_truth: bool = True,
    packet_source: str | None = None,
    capsule: Any | None = None,
    fact_selection: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic context packet for the Maestro brain.

    Parameters (new — flag-gated)
    ------------------------------
    fact_selection:
        Optional list of read-model filenames (e.g. "agent_presence.json")
        provided by the interpreter LM to guide which facts are elevated.
        When None (default) OR when OPENCLAW_INTERPRETER_LM is off → current
        deterministic behaviour, BYTE-IDENTICAL.  When provided and the
        interpreter flag is on, the selected read-models are moved to the
        front of the fact list so they survive the facts[:30] cap in
        format_maestro_context_packet.  All existing facts are still assembled
        normally; this is purely an ordering/elevation hint — never a filter.
    """
    root = _read_model_root(session, read_model_root)
    truth_path = _operator_truth_store_path(session, operator_truth_store_path)
    generated_at = _utc_now()

    truth_facts, operator_truth_used, truth_ref = _operator_truth_facts(path=truth_path, question=question)
    read_model_facts, read_model_refs, read_model_proof = _read_model_facts(root)
    facts = [*truth_facts, *read_model_facts]

    # SQLite canonical-facts source — DEFAULT-OFF.
    # Enabled when packet_source param is "sqlite"/"hybrid", OR when
    # env OPENCLAW_PACKET_SOURCE is set to "sqlite" or "hybrid".
    # The param overrides the env (explicit beats implicit).
    _effective_source = packet_source if packet_source is not None else os.environ.get("OPENCLAW_PACKET_SOURCE", "flat")
    if _effective_source.lower() in ("sqlite", "hybrid"):
        sqlite_facts = _sqlite_canonical_facts(question=question, agent="maestro")
        # Insert canonical/doctrine facts AHEAD of the bulky read-model facts (but after
        # operator truth) so they survive format_maestro_context_packet's facts[:30] cap on
        # packet_text. Appending at the end risked silent truncation when truth+read-models
        # already fill the cap (AGY-G flip-1 audit, hole #3).
        facts = [*truth_facts, *sqlite_facts, *read_model_facts]

    # ── Interpreter LM fact-selection elevation (flag-gated, ADDITIVE) ──────────
    # When OPENCLAW_INTERPRETER_LM is on AND fact_selection is a non-empty list,
    # elevate the interpreter-selected READ-MODEL facts to the front of the
    # read-model slice ONLY — operator-truth and SQLite canonical facts keep their
    # higher precedence (they are NEVER demoted below a read-model fact). This
    # preserves the [*truth_facts, *sqlite_facts, *read_model_facts] precedence
    # invariant. This is purely an ordering hint within the read-model slice — all
    # existing facts remain; nothing is filtered, removed, or rewritten.
    # When flag is off OR fact_selection is None/empty → NO change (byte-identical).
    # The interpreter_lm import is guarded behind fact_selection so the default
    # (None) path does not even import the module.
    if fact_selection:
        try:
            from interpreter_lm import _interpreter_enabled  # local import avoids circular dep

            _selection_active = _interpreter_enabled()
        except Exception:  # noqa: BLE001 — never break packet building
            _selection_active = False
        if _selection_active:
            try:
                # The leading facts (operator truth + optional sqlite canonical) keep
                # their precedence; we only reorder WITHIN the trailing read-model slice.
                _lead_count = len(facts) - len(read_model_facts)
                _lead_facts = facts[:_lead_count]
                _rm_slice = facts[_lead_count:]
                _selected_set = set(fact_selection)
                _selected_rm = [
                    f for f in _rm_slice
                    if any(sel in (f.get("source_ref") or "") for sel in _selected_set)
                ]
                _other_rm = [
                    f for f in _rm_slice
                    if not any(sel in (f.get("source_ref") or "") for sel in _selected_set)
                ]
                if _selected_rm:
                    facts = [*_lead_facts, *_selected_rm, *_other_rm]
            except Exception:  # noqa: BLE001 — never break packet building
                pass  # fall through to deterministic fact order unchanged
    # ──────────────────────────────────────────────────────────────────────────

    if require_real_truth and (not operator_truth_used or len(read_model_refs) < 2):
        raise MaestroContextPacketError(
            "Maestro context packet requires real truth inputs: operator truth plus generated read models."
        )

    source_refs = tuple(dict.fromkeys([*(fact["source_ref"] for fact in facts), *read_model_refs]))
    packet_basis = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "question_hash": hashlib.sha256(str(question or "").encode("utf-8")).hexdigest(),
        "source_refs": source_refs,
        "fact_count": len(facts),
    }
    packet_id = f"maestro_context_packet:{_short_hash(packet_basis)}"
    packet: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "packet_id": packet_id,
        "status": "READY",
        "generated_at": generated_at,
        "source_surface": source_surface,
        "question": _compact(question, limit=300),
        "facts": facts,
        "actionable": _actionable_sections(facts),
        "privacy": _privacy_summary(facts),
        "bounds": {
            "send_hold_absolute": True,
            "outbound_send_allowed": False,
            "money_movement_allowed": False,
            "ledger_mutation_allowed": False,
            "browser_or_coupa_access_allowed": False,
            "claims_must_trace_to_packet": True,
        },
        "source_refs": list(source_refs),
        "machine_proof": {
            "packet_compiler": "maestro_context_packet.build_maestro_context_packet",
            "operator_truth_store_used": operator_truth_used,
            "operator_truth_store_ref": truth_ref,
            "read_model_root": root.as_posix(),
            "read_model_count": len(read_model_refs),
            "fact_count": len(facts),
            "stub_truth_root_rejected_when_required": require_real_truth,
            **read_model_proof,
        },
    }
    packet["packet_text"] = format_maestro_context_packet(packet)

    # ── CONTINUITY CAPSULE enrichment (flag-gated, ADDITIVE) ─────────────────
    # When ON and a capsule is provided, inject entity aliases from distilled
    # memories + current facts, and set packet_source_revision from the capsule
    # version.  This revives the dormant claim-detector heal path (the
    # claim_detector needs non-None packet_entity_aliases + packet_source_revision
    # to emit HealTasks via _bind_truth_source).
    # When OFF or capsule is None: packet is byte-identical to pre-edit behavior.
    if _continuity_enabled() and capsule is not None:
        try:
            _entity_aliases = list(getattr(capsule, "current_facts", []) or [])
            _capsule_version = getattr(capsule, "capsule_version", 1)
            _conversation_id = getattr(capsule, "conversation_id", "")
            packet["packet_entity_aliases"] = _entity_aliases
            packet["packet_source_revision"] = (
                f"capsule:v{_capsule_version}:{_conversation_id}"
            )
        except Exception:
            pass  # never break packet building
    # ─────────────────────────────────────────────────────────────────────────

    # T014: Capital Hilton AR Context integration & Deterministic Response
    if os.environ.get("OPENCLAW_FEATURE_CAPITAL_HILTON_AR") == "1":
        q_lower = (question or "").lower()
        if "capital hilton" in q_lower:
            try:
                from read_model_resolver import resolve_current_read_model
                from ar_counterparty_contact_operations import _connect
                db_path = root / "ar.sqlite"
                with _connect(db_path) as conn:
                    ch_path, ch_payload = resolve_current_read_model(conn, root, "capital_hilton_ar_context")
                
                _append_fact(
                    packet["facts"],
                    topic="capital_hilton_ar",
                    label="Capital Hilton Context",
                    value=f"Status: {ch_payload.get('status')}",
                    provenance="generated_read_model",
                    source_ref=_display_read_model_ref(ch_path),
                    pii_tier="LIGHT"
                )
                
                packet["status"] = "ANSWER_READY"
                packet["deterministic_response"] = (
                    "Deterministic Context: The Capital Hilton read-model answers this query directly. "
                    f"Status: {ch_payload.get('status')}."
                )
                
                run_id = conn.execute("SELECT current_run_id FROM ar_published_read_models WHERE read_model_domain = 'capital_hilton_ar_context'").fetchone()["current_run_id"]
                
                # T015: Traceability
                packet["traceability"] = {
                    "renderer_bypassed": True,
                    "reason": "Deterministic read-model match for Capital Hilton",
                    "package_hash": _short_hash(packet_basis),
                    "prompt_hash": hashlib.sha256(question.encode("utf-8")).hexdigest() if question else "",
                    "response_hash": _short_hash(packet["deterministic_response"]),
                    "conversation_id": session.get("conversation_id", "unknown") if isinstance(session, dict) else "unknown",
                    "turn_id": session.get("turn_id", "unknown") if isinstance(session, dict) else "unknown",
                    "timestamp": generated_at,
                    "materialization_run_id": run_id,
                    "model": "explicit_no_model_invocation",
                    "agent_id": "cassandra",
                    "lane_id": "operator_comms",
                    "telegram_bot_username": "@openclaw_cassandra_bot",
                    "telegram_display_name": "Clara Reid",
                    "authority_scope": "read_only",
                    "delivery_status": "pending_delivery",
                    "telegram_chat_id": session.get("telegram_chat_id", "unknown") if isinstance(session, dict) else "unknown",
                    "telegram_message_id": session.get("telegram_message_id", "unknown") if isinstance(session, dict) else "unknown"
                }
                packet["packet_text"] = format_maestro_context_packet(packet)
            except Exception:
                pass

    return packet


def format_maestro_context_packet(packet: Mapping[str, Any]) -> str:
    facts = [fact for fact in packet.get("facts", ()) if isinstance(fact, Mapping)]
    actionable = packet.get("actionable") if isinstance(packet.get("actionable"), Mapping) else {}
    bounds = packet.get("bounds") if isinstance(packet.get("bounds"), Mapping) else {}
    lines = [
        f"MAESTRO_CONTEXT_PACKET {packet.get('packet_id', '')}",
        f"Generated: {packet.get('generated_at', '')}",
        "",
        "Grounded facts:",
    ]
    for fact in facts[:30]:
        source = str(fact.get("source_ref") or "")
        provenance = str(fact.get("provenance") or "")
        tier = str(fact.get("pii_tier") or "PUBLIC")
        lines.append(
            f"- {fact.get('label')}: {fact.get('value')} "
            f"[tier={tier}; provenance={provenance}; source={source}]"
        )
    lines.extend(["", "Actionable view:"])
    for title, key in (
        ("Money in/out", "money_in_out"),
        ("Needs attention", "needs_attention"),
        ("Upcoming commitments", "upcoming_commitments"),
    ):
        values = [str(item) for item in actionable.get(key, ()) if str(item).strip()]
        lines.append(f"- {title}: {' | '.join(values) if values else 'none in packet'}")
    lines.extend(
        [
            "",
            "Boundaries:",
            f"- SEND_HOLD absolute: {bool(bounds.get('send_hold_absolute', True))}",
            f"- Outbound send allowed: {bool(bounds.get('outbound_send_allowed', False))}",
            f"- Money movement allowed: {bool(bounds.get('money_movement_allowed', False))}",
            f"- Ledger mutation allowed: {bool(bounds.get('ledger_mutation_allowed', False))}",
        ]
    )
    return "\n".join(lines).strip()


def resolve_ledger_reference(text: str, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    normalized = " ".join(str(text or "").lower().replace("'", "'").split())
    if "ledger" not in normalized:
        return {"status": "NO_LEDGER_REFERENCE", "processing_allowed": False, "action_allowed": False}

    action_requested = any(term in normalized for term in LEDGER_ACTION_TERMS)
    context_text = normalized
    if isinstance(context, Mapping):
        context_text = " ".join(
            [
                context_text,
                str(context.get("world") or ""),
                str(context.get("topic") or ""),
                str(context.get("last_topic") or ""),
                str(context.get("active_surface") or ""),
            ]
        ).lower()

    has_finance_context = any(term in context_text for term in FINANCE_CONTEXT_TERMS)
    if not has_finance_context:
        return {
            "status": "NEEDS_CLARIFICATION",
            "reason": "ledger_reference_without_context",
            "clarifying_question": "Which ledger do you mean: the bank/finance ledger or a system/control ledger?",
            "processing_allowed": False,
            "action_allowed": False,
        }

    return {
        "status": "RESOLVED",
        "referent": "bank_finance_ledger",
        "pii_tier": "LIGHT",
        "processing_allowed": True,
        "action_allowed": False,
        "reason": "finance_context_resolves_ledger_to_bank_finance_ledger",
        "blocked_action_requested": action_requested,
    }


__all__ = [
    "MaestroContextPacketError",
    "build_maestro_context_packet",
    "format_maestro_context_packet",
    "resolve_ledger_reference",
]
