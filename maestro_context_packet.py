"""Deterministic context packet for Maestro's protected brain.

The packet is a compact, provenance-carrying view of current read models plus
operator-corrected truth. It is deliberately not a raw dump: the facts are
small, source-tagged, and safe for a gated model prompt.
"""

from __future__ import annotations

import copy
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping, Sequence

from context_source import annotate_facts_with_ledger_provenance, ledger_machine_proof
from fleet_temporal_anchor import temporal_anchor_text


# ── Conversation-continuity flag (ADDITIVE, default OFF) ──────────────────────
def _continuity_enabled() -> bool:
    """Return True only when OPENCLAW_CONTINUITY_CAPSULE is "1" or "true"."""
    return os.environ.get("OPENCLAW_CONTINUITY_CAPSULE", "0").lower() in ("1", "true")


SCHEMA_VERSION = "maestro_context_packet_v0"
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_SYSTEM_CATALOG_PATH = Path("/home/openclaw/.openclaw/business_ops/ledger.sqlite")
DEFAULT_FRONTDOOR_MODEL_MAX_GB = 6.0
CLIENT_INVOICE_WORKFLOW_FRAMEWORK_READ_MODEL = "client_invoice_workflow_framework.json"
KNOWN_READ_MODELS = (
    "agent_presence.json",
    "openclaw_capability_index.json",
    "chief_status_rail.json",
    "openclaw_change_sentinel.json",
    "finance_invoice_reconciliation.json",
    CLIENT_INVOICE_WORKFLOW_FRAMEWORK_READ_MODEL,
    "capital_hilton_invoice_operator_readback.json",
    "capital_hilton_invoice_operator_run_status.json",
    "cassandra_email_calendar_delta_detangle.json",
    "work_board.json",
    "orchestration_progress.json",
    "niles_track_registry.json",
    "niles_album_review_packet.json",
    "niles_album_matrix_review.json",
    "niles_album_metadata_intake_packet.json",
    "reynolds_gig_setup_status.json",
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


def _prebuilt_lm1_shared_packet(session: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if os.environ.get("OPENCLAW_LM1_SHARED_SEAM", "0").lower() not in ("1", "true"):
        return None
    if not isinstance(session, Mapping):
        return None
    packet = session.get("lm1_shared_rich_context_packet")
    if not isinstance(packet, Mapping) or not str(packet.get("packet_id") or "").strip():
        return None
    cloned = copy.deepcopy(dict(packet))
    machine_proof = dict(cloned.get("machine_proof") or {})
    machine_proof["lm1_shared_packet_reused"] = True
    machine_proof["packet_compiler"] = "maestro_context_packet.build_maestro_context_packet"
    cloned["machine_proof"] = machine_proof
    cloned["lm1_shared_packet_reused"] = True
    return cloned


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


_RELATIVE_DATE_TERMS = re.compile(
    r"\b("
    r"today|tomorrow|yesterday|"
    r"next (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|month)|"
    r"last (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|month)|"
    r"this (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|weekend|week|month)"
    r")\b",
    re.IGNORECASE,
)
_ISO_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_RAW_OPERATOR_NOTE_PREFIX_RE = re.compile(
    r"^\s*(?:i\s+got\s+your\s+message,?\s*)?"
    r"(?:(?:one\s+thing\s+i\s+want\s+you\s+to\s+remember)|(?:remember\s+this)|(?:note\s+this))"
    r"\s*[:,-]?\s*",
    re.IGNORECASE,
)
_PAID_UP_NOTE_RE = re.compile(r"\b(?:all\s+paid\s+up|paid\s+up|all\s+square|caught\s+up)\b", re.IGNORECASE)

_CLIENT_DISPLAY_NAMES = {
    "st_annes": "St Anne's",
    "live_arts_md": "Live Arts MD",
    "capital_hilton": "Capital Hilton",
}


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _is_stale_relative_date_truth(text: str, *, today: date | None = None) -> bool:
    body = str(text or "")
    if not _RELATIVE_DATE_TERMS.search(body):
        return False
    current = today or _today_utc()
    for match in _ISO_DATE_RE.finditer(body):
        try:
            referenced = date.fromisoformat(match.group(1))
        except ValueError:
            continue
        if referenced < current:
            return True
    return False


def _strip_stale_relative_date_truth(text: str, *, today: date | None = None) -> str:
    body = str(text or "").strip()
    if not _is_stale_relative_date_truth(body, today=today):
        return body
    clauses = [part.strip() for part in re.split(r";\s*", body) if part.strip()]
    if len(clauses) <= 1:
        return ""
    kept = [
        clause
        for clause in clauses
        if not _is_stale_relative_date_truth(clause, today=today)
    ]
    if not kept:
        return ""
    return "; ".join(kept).rstrip(".") + "."


def _distill_operator_truth_note(text: str) -> str:
    body = str(text or "").strip()
    body = _RAW_OPERATOR_NOTE_PREFIX_RE.sub("", body).strip()
    body = re.sub(r"^\s*i(?:'| a)?m\s+actually\s+", "", body, flags=re.IGNORECASE).strip()
    return body or str(text or "").strip()


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
        raw_value = _strip_stale_relative_date_truth(str(record.get("value") or ""))
        value = _distill_operator_truth_note(raw_value)
        if not value or _is_stale_relative_date_truth(f"{label} {value}"):
            continue
        before_count = len(facts)
        _append_fact(
            facts,
            topic="operator_truth",
            label=label,
            value=value,
            provenance=str(record.get("provenance") or "operator_corrected"),
            source_ref=source_ref,
            pii_tier=str(record.get("pii_tier") or "LIGHT"),
            freshness={
                "as_of": str(record.get("at") or ""),
                "source_surface": str(record.get("source_surface") or ""),
                "precedence": record.get("precedence"),
            },
        )
        if len(facts) > before_count:
            facts[-1].update(
                {
                    "raw_operator_note": True,
                    "verbatim_readback": False,
                    "operator_note_handling": "distill_not_quote",
                    "raw_operator_note_sha256": hashlib.sha256(str(raw_value or "").encode("utf-8")).hexdigest(),
                    "current_truth": True,
                    "entity_key": str(record.get("entity_key") or ""),
                }
            )
    return facts, bool(facts), str(path or "")


def _as_of_date_from_session(session: Mapping[str, Any] | None) -> date:
    raw = _session_path(session, "as_of_date", "packet_as_of_date", "today")
    if not raw:
        raw = os.environ.get("OPENCLAW_TODAY", "").strip()
    if raw:
        try:
            return datetime.fromisoformat(raw).date()
        except ValueError:
            pass
    return datetime.now(timezone.utc).date()


def _client_display(client_ref: str) -> str:
    return _CLIENT_DISPLAY_NAMES.get(client_ref, client_ref.replace("_", " ").title())


def _money_minor_units(value: int, currency: str) -> str:
    major = value / 100
    if major.is_integer():
        return f"{currency} {int(major)}"
    return f"{currency} {major:.2f}"


def _current_open_receivables_by_client(db_path: Path) -> dict[str, list[Any]]:
    if not db_path.exists():
        return {}
    try:
        from ar_expected_receivable_record import ExpectedReceivableRecord
        from ar_gig_to_cash_store import GigToCashStore
        from temporal_recurrence_registry import client_ref_slug
    except Exception:
        return {}

    grouped: dict[str, list[Any]] = {}
    try:
        with GigToCashStore(str(db_path)) as store:
            conn = getattr(store, "_conn", None)
            if conn is None:
                return {}
            rows = conn.execute(
                """
                SELECT receivable_id
                FROM expected_receivable_records
                WHERE receivable_version_id NOT IN (
                    SELECT supersedes_receivable_version_id
                    FROM expected_receivable_records
                    WHERE supersedes_receivable_version_id IS NOT NULL
                )
                ORDER BY ingestion_seq ASC
                """
            ).fetchall()
            for row in rows:
                current = store.get_current(ExpectedReceivableRecord, row["receivable_id"])
                if current is None or current.lifecycle_state != "open":
                    continue
                grouped.setdefault(client_ref_slug(current.counterparty_ref), []).append(current)
    except Exception:
        return {}
    return grouped


def _receivable_temporal_facts(
    *,
    session: Mapping[str, Any] | None,
    question: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ar_path_raw = _session_path(
        session,
        "gig_to_cash_db_path",
        "ar_gig_to_cash_db_path",
        "receivable_ledger_path",
    )
    proof: dict[str, Any] = {
        "receivable_temporal_scoping_used": False,
        "receivable_temporal_fact_count": 0,
    }
    if not ar_path_raw:
        return [], proof

    ar_path = Path(ar_path_raw)
    open_by_client = _current_open_receivables_by_client(ar_path)
    paid_store_raw = _session_path(
        session,
        "client_paid_through_store_path",
        "paid_through_store_path",
        "receivable_paid_through_store_path",
    )
    now = _as_of_date_from_session(session)
    facts: list[dict[str, Any]] = []

    clients = set(open_by_client)
    question_lower = str(question or "").lower()
    if any(token in question_lower for token in ("st anne", "st anne's", "st annes", "saint anne")):
        clients.add("st_annes")
    if not clients:
        return [], proof

    try:
        from receivable_temporal_scoping import ClientPaidThroughStore, paid_up_state_for_client
        from temporal_recurrence_registry import paid_up_state
    except Exception:
        return [], proof

    paid_store = ClientPaidThroughStore(paid_store_raw) if paid_store_raw else None
    for client_ref in sorted(clients):
        open_receivables = open_by_client.get(client_ref, [])
        if paid_store is not None:
            state = paid_up_state_for_client(client_ref, now=now, paid_through_store=paid_store)
        else:
            state = paid_up_state(client_ref, paid_through=None, now=now)
        if not open_receivables and state.status == "unknown_scope":
            continue
        receivable_bits = []
        for receivable in open_receivables[:5]:
            receivable_bits.append(
                f"{receivable.receivable_id} due {receivable.due_date_iso} "
                f"for {_money_minor_units(receivable.expected_minor_units, receivable.currency_iso)}"
            )
        value = (
            f"{_client_display(client_ref)} current receivable state: {state.status}; "
            f"paid_through={state.paid_through.isoformat() if state.paid_through else 'unknown'}; "
            f"next_expected_invoice={state.next_expected_invoice.isoformat() if state.next_expected_invoice else 'unknown'}; "
            f"open_receivables={'; '.join(receivable_bits) if receivable_bits else 'none'}."
        )
        before_count = len(facts)
        _append_fact(
            facts,
            topic="receivable_temporal_state",
            label=f"{_client_display(client_ref)} receivable temporal state",
            value=value,
            provenance="receivable_temporal_scoping",
            source_ref=f"gig_to_cash:{ar_path.as_posix()}",
            pii_tier="LIGHT",
            freshness={
                "as_of": now.isoformat(),
                "client_ref": client_ref,
                "paid_through_store_ref": paid_store_raw,
            },
        )
        if len(facts) > before_count:
            facts[-1].update(
                {
                    "client_ref": client_ref,
                    "paid_up_status": state.status,
                    "paid_through": state.paid_through.isoformat() if state.paid_through else "",
                    "next_expected_invoice": state.next_expected_invoice.isoformat() if state.next_expected_invoice else "",
                    "open_receivable_count": len(open_receivables),
                    "current_truth": True,
                    "authority_source": "receivable_temporal_scoping.paid_up_state_for_client",
                }
            )

    proof["receivable_temporal_scoping_used"] = bool(facts)
    proof["receivable_temporal_fact_count"] = len(facts)
    proof["receivable_temporal_clients"] = [str(fact.get("client_ref") or "") for fact in facts]
    return facts, proof


def _fact_mentions_client(fact: Mapping[str, Any], client_ref: str) -> bool:
    display = _client_display(client_ref).lower()
    compact_display = display.replace("'", "")
    blob = " ".join(str(fact.get(key) or "") for key in ("label", "value", "source_ref", "entity_key")).lower()
    blob_compact = blob.replace("'", "")
    return client_ref in blob_compact or display in blob or compact_display in blob_compact


def _resolve_operator_truth_drift(
    truth_facts: Sequence[Mapping[str, Any]],
    temporal_facts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    authoritative_due = {
        str(fact.get("client_ref") or ""): fact
        for fact in temporal_facts
        if str(fact.get("paid_up_status") or "") == "invoice_due" or int(fact.get("open_receivable_count") or 0) > 0
    }
    resolved: list[dict[str, Any]] = []
    for fact in truth_facts:
        cloned = dict(fact)
        for client_ref, temporal_fact in authoritative_due.items():
            if not client_ref or not _fact_mentions_client(cloned, client_ref):
                continue
            if not _PAID_UP_NOTE_RE.search(str(cloned.get("value") or "")):
                continue
            cloned.update(
                {
                    "current_truth": False,
                    "drift_status": "superseded_by_receivable_temporal_state",
                    "drift_resolution": "ledger_wins",
                    "superseded_by_source_ref": str(temporal_fact.get("source_ref") or ""),
                    "value": (
                        f"{_client_display(client_ref)} has a prior settlement note, but the current "
                        f"receivable temporal state is {temporal_fact.get('paid_up_status')}; use the "
                        "receivable state as current."
                    ),
                }
            )
            break
        resolved.append(cloned)
    return resolved


_MONTH_BOUND_RE = re.compile(
    r"\b(month|january|february|march|april|may|june|july|august|september|october|november|december)\b",
    re.IGNORECASE,
)
_RECEIVABLE_STATUS_QUESTION_RE = re.compile(
    r"(\breceivables?\b|\bowe[ds]?\b|\bpaid\s+up\b|\bcaught\s+up\b|\bsettled?\b|\bsettlement\b|\bunpaid\b)",
    re.IGNORECASE,
)
_MONEY_STATUS_VALUE_RE = re.compile(
    r"(\$|\bpaid\b|\bpaid\s+up\b|\bowes?\b|\binvoice\b|\breceivable\b|\bsettled\b|\bunpaid\b|\bdue\b)",
    re.IGNORECASE,
)


def _fact_as_of(fact: Mapping[str, Any]) -> str:
    direct = str(fact.get("as_of") or fact.get("refined_as_of") or "").strip()
    if direct:
        return direct
    freshness = fact.get("freshness") if isinstance(fact.get("freshness"), Mapping) else {}
    return str(freshness.get("as_of") or "").strip()


def _question_needs_money_status_data(question: str) -> bool:
    text = str(question or "")
    if _RECEIVABLE_STATUS_QUESTION_RE.search(text):
        return True
    if _MONTH_BOUND_RE.search(text) and re.search(r"\b(invoice|invoices|money|due)\b", text, re.IGNORECASE):
        return True
    return False


def _fact_is_money_status_fact(fact: Mapping[str, Any]) -> bool:
    topic = str(fact.get("topic") or "").lower()
    if any(token in topic for token in ("money", "invoice", "receivable", "settlement", "finance")):
        return True
    value = " ".join(str(fact.get(key) or "") for key in ("label", "value")).lower()
    return bool(_MONEY_STATUS_VALUE_RE.search(value))


def _fact_is_structured_money_status(fact: Mapping[str, Any]) -> bool:
    if fact.get("needs_operator_review"):
        return False
    if str(fact.get("topic") or "") == "receivable_temporal_state" and _fact_as_of(fact):
        return True
    return bool(fact.get("structured_fact") is True and _fact_as_of(fact))


def _money_not_tracked_label(question: str) -> str:
    lowered = str(question or "").lower()
    if "receivable" in lowered or "owe" in lowered or "owed" in lowered:
        return "month-bounded receivables"
    if "invoice" in lowered:
        return "invoice status"
    if "settle" in lowered or "paid" in lowered or "caught up" in lowered:
        return "settlement status"
    return "money/status data"


def _anti_launder_not_tracked_fact(question: str, *, as_of: str, dropped_count: int) -> dict[str, Any]:
    label = _money_not_tracked_label(question)
    return {
        "fact_id": f"money_not_tracked:{_short_hash((question, as_of, dropped_count))}",
        "topic": "money_not_tracked",
        "label": "Money/status data not tracked",
        "value": f"not tracked: {label} (no structured fact with as_of is available).",
        "provenance": "money_status_anti_launder_guard",
        "source_ref": "maestro_context_packet:money_status_anti_launder_guard",
        "pii_tier": "PUBLIC",
        "structured_fact": True,
        "as_of": as_of,
        "dropped_unstructured_money_fact_count": dropped_count,
    }


def _apply_money_status_anti_launder_guard(
    facts: Sequence[Mapping[str, Any]],
    *,
    question: str,
    session: Mapping[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not _question_needs_money_status_data(question):
        return [dict(fact) for fact in facts], {
            "money_status_anti_launder_guard_applied": False,
            "money_status_unstructured_facts_dropped": 0,
            "money_status_not_tracked_marker_added": False,
        }

    kept: list[dict[str, Any]] = []
    dropped = 0
    structured_money_facts = 0
    for fact in facts:
        cloned = dict(fact)
        if not _fact_is_money_status_fact(cloned):
            kept.append(cloned)
            continue
        if _fact_is_structured_money_status(cloned):
            structured_money_facts += 1
            if _fact_as_of(cloned):
                cloned["as_of"] = _fact_as_of(cloned)
            kept.append(cloned)
        else:
            dropped += 1

    marker_added = False
    if structured_money_facts == 0:
        kept.insert(
            0,
            _anti_launder_not_tracked_fact(
                question,
                as_of=_as_of_date_from_session(session).isoformat(),
                dropped_count=dropped,
            ),
        )
        marker_added = True

    return kept, {
        "money_status_anti_launder_guard_applied": True,
        "money_status_structured_fact_count": structured_money_facts,
        "money_status_unstructured_facts_dropped": dropped,
        "money_status_not_tracked_marker_added": marker_added,
    }


def _contacts_db_path() -> str:
    try:
        from contacts_registry import DEFAULT_CONTACTS_DB_PATH

        return os.environ.get("OPENCLAW_CONTACTS_DB_PATH") or DEFAULT_CONTACTS_DB_PATH
    except Exception:
        return os.environ.get("OPENCLAW_CONTACTS_DB_PATH") or ""


def _contact_text_key(value: Any) -> str:
    text = str(value or "").lower().replace("'", "")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _contact_query_client_slugs(question: str, contacts: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    query_key = f" {_contact_text_key(question)} "
    slugs: list[str] = []
    for contact in contacts:
        clients = contact.get("connected_clients") or contact.get("connected_client") or ()
        if isinstance(clients, str):
            clients = (clients,)
        for client in clients:
            slug = str(client or "").strip()
            if not slug:
                continue
            terms = {
                _contact_text_key(slug),
                _contact_text_key(slug.replace("-", " ")),
                _contact_text_key(slug.replace("-", "")),
            }
            if any(term and f" {term} " in query_key for term in terms) and slug not in slugs:
                slugs.append(slug)
    return tuple(slugs)


def _contact_fact_value(contact: Mapping[str, Any]) -> str:
    clients = contact.get("connected_clients") or contact.get("connected_client") or ()
    if isinstance(clients, str):
        clients = (clients,)
    client_text = ", ".join(str(client) for client in clients if str(client).strip()) or "no client link"
    role = str(contact.get("role") or "contact").strip()
    name = str(contact.get("name") or contact.get("id") or "Contact").strip()
    return f"{name} is a contacts_registry contact for {client_text}; role: {role}."


def _contacts_registry_facts(question: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    db_path = _contacts_db_path()
    proof: dict[str, Any] = {
        "contacts_registry_used": False,
        "contacts_registry_ref": f"contacts_registry:{db_path}" if db_path else "contacts_registry",
        "contacts_registry_contact_count": 0,
        "contacts_registry_client_slugs": [],
    }
    try:
        from contacts_registry import ContactsRegistry

        registry = ContactsRegistry(db_path, seed=True)
        all_contacts = registry.list_contacts()
    except Exception as exc:
        proof["contacts_registry_error"] = str(exc)
        return [], proof

    client_slugs = _contact_query_client_slugs(question, all_contacts)
    selected: list[dict[str, Any]] = []
    if client_slugs:
        for slug in client_slugs:
            selected.extend(registry.get_contacts_for_client(slug))
    elif re.search(r"\b(contact|person|people|who is|who's|who do i talk to)\b", str(question or ""), re.IGNORECASE):
        selected = all_contacts

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for contact in selected:
        contact_id = str(contact.get("id") or "")
        if contact_id and contact_id not in seen:
            seen.add(contact_id)
            deduped.append(contact)

    facts: list[dict[str, Any]] = []
    source_ref = proof["contacts_registry_ref"]
    for contact in deduped:
        _append_fact(
            facts,
            topic="contacts_registry",
            label=f"Contact: {contact.get('name') or contact.get('id')}",
            value=_contact_fact_value(contact),
            provenance="contacts_registry",
            source_ref=source_ref,
            pii_tier="LIGHT",
            freshness={"client_slugs": list(client_slugs)},
        )

    proof["contacts_registry_used"] = bool(facts)
    proof["contacts_registry_contact_count"] = len(deduped)
    proof["contacts_registry_client_slugs"] = list(client_slugs)
    return facts, proof


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y", "required"}


def _recipe_selected_rail_refs(recipe: Mapping[str, Any]) -> set[str]:
    selected = recipe.get("selected_rails")
    if not isinstance(selected, Sequence) or isinstance(selected, (str, bytes)):
        return set()
    refs: set[str] = set()
    for item in selected:
        if not isinstance(item, Mapping):
            continue
        rail_ref = str(item.get("rail_ref") or "").strip()
        if rail_ref:
            refs.add(rail_ref)
    return refs


def _recipe_coupa_evidence(recipe: Mapping[str, Any], portal: Mapping[str, Any]) -> str:
    payment = (
        recipe.get("client_specific_payment_expectations")
        if isinstance(recipe.get("client_specific_payment_expectations"), Mapping)
        else {}
    )
    bits = [
        portal.get("supplier_portal_provider"),
        portal.get("portal_provider"),
        portal.get("provider_display_name"),
        portal.get("portal_ref"),
        payment.get("expected_payment_signal") if isinstance(payment, Mapping) else "",
    ]
    selected = recipe.get("selected_rails")
    if isinstance(selected, Sequence) and not isinstance(selected, (str, bytes)):
        for item in selected:
            if isinstance(item, Mapping):
                bits.append(item.get("recipe_notes"))
                bits.append(item.get("rail_ref"))
    return " ".join(str(bit or "") for bit in bits)


def _client_invoice_billing_channel_facts(
    root: Path,
    payload: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = root / CLIENT_INVOICE_WORKFLOW_FRAMEWORK_READ_MODEL
    source_ref = _display_read_model_ref(path)
    recipes = payload.get("recipes")
    proof: dict[str, Any] = {
        "client_invoice_workflow_framework_used_for_billing_channels": False,
        "client_billing_channel_fact_count": 0,
        "client_billing_channel_clients": [],
    }
    if not isinstance(recipes, Sequence) or isinstance(recipes, (str, bytes)):
        return [], proof

    facts: list[dict[str, Any]] = []
    for recipe in recipes:
        if not isinstance(recipe, Mapping):
            continue
        client_ref = str(recipe.get("client_ref") or "").strip()
        display = str(recipe.get("client_display_name") or client_ref.replace("_", " ").title()).strip()
        portal = (
            recipe.get("client_specific_portal_requirements")
            if isinstance(recipe.get("client_specific_portal_requirements"), Mapping)
            else {}
        )
        selected_rails = _recipe_selected_rail_refs(recipe)
        supplier_portal_required = _truthy(portal.get("supplier_portal_required")) or (
            "supplier_portal_rail" in selected_rails
        )
        purchase_order_required = (
            _truthy(portal.get("purchase_order_required"))
            or _truthy(portal.get("requires_purchase_order"))
            or "purchase_order_rail" in selected_rails
        )
        coupa_evidence = _recipe_coupa_evidence(recipe, portal).lower()
        uses_coupa = supplier_portal_required and "coupa" in coupa_evidence
        portal_ref = str(portal.get("portal_ref") or "").strip() or "none"

        if uses_coupa:
            channel_sentence = (
                f"{display} uses Coupa for its client invoice recipe; "
                f"supplier_portal_required=true; purchase_order_required={str(purchase_order_required).lower()}; "
                f"portal_ref={portal_ref}."
            )
        else:
            channel_sentence = (
                f"{display} does not use Coupa by default; "
                f"supplier_portal_required={str(supplier_portal_required).lower()}; "
                f"purchase_order_required={str(purchase_order_required).lower()}; portal_ref={portal_ref}; "
                "use the non-Coupa client invoice recipe until a client-specific portal requirement is configured."
            )

        before_count = len(facts)
        _append_fact(
            facts,
            topic="client_billing_channel",
            label=f"{display} billing channel",
            value=channel_sentence,
            provenance="generated_read_model",
            source_ref=source_ref,
            pii_tier="LIGHT",
            freshness=_freshness(path, payload),
        )
        if len(facts) > before_count:
            facts[-1].update(
                {
                    "client_ref": client_ref,
                    "uses_coupa": uses_coupa,
                    "supplier_portal_required": supplier_portal_required,
                    "purchase_order_required": purchase_order_required,
                    "portal_ref": portal_ref,
                    "authority_source": "client_invoice_workflow_framework.recipes",
                    "current_truth": True,
                }
            )

    proof["client_invoice_workflow_framework_used_for_billing_channels"] = bool(facts)
    proof["client_billing_channel_fact_count"] = len(facts)
    proof["client_billing_channel_clients"] = [
        str(fact.get("client_ref") or "") for fact in facts if str(fact.get("client_ref") or "").strip()
    ]
    return facts, proof


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

    invoice_framework = payloads.get(CLIENT_INVOICE_WORKFLOW_FRAMEWORK_READ_MODEL, {})
    if invoice_framework:
        billing_facts, billing_proof = _client_invoice_billing_channel_facts(root, invoice_framework)
        facts.extend(billing_facts)
        proof.update(billing_proof)

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

    niles_tracks = payloads.get("niles_track_registry.json", {})
    tracks = [row for row in niles_tracks.get("tracks", ()) if isinstance(row, Mapping)]
    if tracks:
        track_lines: list[str] = []
        for row in tracks[:8]:
            title = str(row.get("title") or row.get("track_title") or row.get("name") or "").strip()
            status = str(row.get("status") or row.get("state") or row.get("note") or "").strip()
            if title and status:
                track_lines.append(f"{title} ({status})")
            elif title:
                track_lines.append(title)
        _append_fact(
            facts,
            topic="niles_music_context",
            label="Niles track registry",
            value=(
                f"Real track roster available: {bool(niles_tracks.get('real_track_roster_available'))}; "
                f"track count: {niles_tracks.get('track_count', len(tracks))}. "
                f"Tracks: {'; '.join(track_lines)}."
            ),
            provenance="generated_read_model",
            source_ref=_display_read_model_ref(root / "niles_track_registry.json"),
            freshness=_freshness(root / "niles_track_registry.json", niles_tracks),
        )

    reynolds = payloads.get("reynolds_gig_setup_status.json", {})
    core = reynolds.get("known_core_facts") if isinstance(reynolds.get("known_core_facts"), Mapping) else {}
    if core or reynolds:
        venue = str(core.get("venue_name") or reynolds.get("venue_display_name") or "").strip()
        gig_date = str(core.get("date") or "").strip()
        start = str(core.get("start_time") or "").strip()
        fee = str(core.get("fee_amount") or "").strip()
        music_lane = ""
        lanes = reynolds.get("lanes") if isinstance(reynolds.get("lanes"), Mapping) else {}
        if isinstance(lanes.get("music"), Mapping):
            music_lane = str(lanes["music"].get("status") or lanes["music"].get("summary") or "").strip()
        details = [part for part in (venue, gig_date, start and f"start {start}", fee and f"fee ${fee}", music_lane) if part]
        _append_fact(
            facts,
            topic="niles_gig_context",
            label="Niles gig setup context",
            value="; ".join(details) or "Reynolds gig setup status read model is present.",
            provenance="generated_read_model",
            source_ref=_display_read_model_ref(root / "reynolds_gig_setup_status.json"),
            freshness=_freshness(root / "reynolds_gig_setup_status.json", reynolds),
        )

    niles_review = payloads.get("niles_album_review_packet.json", {})
    if niles_review:
        blockers = [b for b in niles_review.get("blockers", ()) if isinstance(b, Mapping)]
        blocker_text = "; ".join(str(b.get("description") or b.get("next_safe_move") or "").strip() for b in blockers[:3])
        _append_fact(
            facts,
            topic="niles_album_context",
            label="Niles album review posture",
            value=(
                f"Album state confirmed: {bool(niles_review.get('album_state_confirmed'))}; "
                f"evidence sufficient: {bool(niles_review.get('evidence_sufficient_for_album_status'))}. "
                f"{blocker_text}"
            ),
            provenance="generated_read_model",
            source_ref=_display_read_model_ref(root / "niles_album_review_packet.json"),
            freshness=_freshness(root / "niles_album_review_packet.json", niles_review),
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


def _system_catalog_path(session: Mapping[str, Any] | None = None) -> Path:
    if isinstance(session, Mapping):
        configured = _session_path(session, "system_catalog_path", "openclaw_system_catalog_path")
        if configured:
            return Path(configured)
    configured_env = os.environ.get("OPENCLAW_SYSTEM_CATALOG", "").strip()
    return Path(configured_env) if configured_env else DEFAULT_SYSTEM_CATALOG_PATH


def _matchable_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _skill_trigger_matches(question: str, trigger: str) -> bool:
    raw_question = str(question or "").lower()
    raw_trigger = str(trigger or "").strip().lower()
    if not raw_question or not raw_trigger:
        return False
    if raw_trigger in raw_question:
        return True
    normalized_question = _matchable_text(raw_question)
    normalized_trigger = _matchable_text(raw_trigger)
    return bool(normalized_trigger and normalized_trigger in normalized_question)


def _model_size_hint(model_name: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*b\b", str(model_name or "").lower())
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _frontdoor_model_max_gb() -> float:
    raw = os.environ.get("OPENCLAW_FRONTDOOR_MODEL_MAX_GB", "").strip()
    if not raw:
        return DEFAULT_FRONTDOOR_MODEL_MAX_GB
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_FRONTDOOR_MODEL_MAX_GB
    return value if value > 0 else DEFAULT_FRONTDOOR_MODEL_MAX_GB


def _select_skill_tier(skill: Mapping[str, Any], question: str) -> dict[str, Any]:
    try:
        from model_router_policy import select_model_class

        model_class = select_model_class(
            {
                "request_id": f"skill_tier:{skill.get('skill_id') or skill.get('id')}",
                "chain_lane": "LM2_ROLE_RESPONSE",
                "task_type": str(skill.get("capability_needed") or "multi-step-reasoning"),
                "role": str(skill.get("owner_agent") or "chief"),
                "risk_level": "medium",
                "sensitivity_level": "low",
                "context_size": "small" if len(str(question or "")) < 600 else "large",
                "requires_structured_output": True,
                "local_lm_required": True,
                "package_minimized": True,
            }
        )
    except Exception:
        model_class = {"selected_model_class": "LOCAL_FALLBACK_MODEL", "selection_reason": "model_router_unavailable"}

    try:
        from chief_llm import select_frontdoor_model

        available_vram_gb = None
        available_ram_gb = None
        resident_vram_by_model_gb: dict[str, float] = {}
        try:
            from frontdoor_resource_probe import probe_frontdoor_resources

            resource_snapshot = probe_frontdoor_resources()
            available_vram_gb = resource_snapshot.available_vram_gb
            available_ram_gb = resource_snapshot.available_ram_gb
            resident_vram_by_model_gb = resource_snapshot.resident_vram_by_model_gb()
        except Exception:
            pass
        model_selected, model_reason = select_frontdoor_model(
            max_gb=_frontdoor_model_max_gb(),
            available_vram_gb=available_vram_gb,
            available_ram_gb=available_ram_gb,
            resident_vram_by_model_gb=resident_vram_by_model_gb,
        )
    except Exception:
        model_selected, model_reason = None, "frontdoor_selector_unavailable"

    size_hint = _model_size_hint(str(model_selected or ""))
    selected_tier = "simple" if size_hint is None or size_hint <= 8.0 else "rich"
    tiers = skill.get("tiers") if isinstance(skill.get("tiers"), Mapping) else {}
    if selected_tier not in tiers and "simple" in tiers:
        selected_tier = "simple"
    if selected_tier not in tiers and "rich" in tiers:
        selected_tier = "rich"

    return {
        "selected_tier": selected_tier,
        "tier_body": str(tiers.get(selected_tier) or ""),
        "model_selected": model_selected or "",
        "frontdoor_model_reason": model_reason,
        "selected_model_class": str(model_class.get("selected_model_class") or ""),
        "model_class_reason": str(model_class.get("selection_reason") or ""),
    }


def _registered_skill_matches(question: str, session: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    try:
        from skill_loader import load_registered_skills

        registered = load_registered_skills(_system_catalog_path(session))
    except Exception:
        return []

    applied: list[dict[str, Any]] = []
    for skill in registered:
        triggers = [str(trigger) for trigger in skill.get("triggers", ()) if str(trigger).strip()]
        matched_triggers = [trigger for trigger in triggers if _skill_trigger_matches(question, trigger)]
        if not matched_triggers:
            continue
        tier = _select_skill_tier(skill, question)
        skill_id = str(skill.get("skill_id") or skill.get("id") or "")
        display_name = str(skill.get("name") or skill_id).replace("-", " ").replace("_", " ").title()
        applied.append(
            {
                "skill_id": skill_id,
                "display_name": display_name,
                "owner_agent": str(skill.get("owner_agent") or ""),
                "matched_triggers": matched_triggers,
                "tools": [str(tool) for tool in skill.get("tools", ()) if str(tool).strip()],
                "authority": str(skill.get("authority") or ""),
                "capability_needed": str(skill.get("capability_needed") or ""),
                "source_path": str(skill.get("source_path") or ""),
                **tier,
            }
        )
    return applied[:3]


def _music_law_skill_facts(applied_skills: Sequence[Mapping[str, Any]], question: str) -> list[dict[str, Any]]:
    if not any(str(skill.get("skill_id") or "") == "music_law_advisory" for skill in applied_skills):
        return []

    facts: list[dict[str, Any]] = []
    try:
        from chief_musiclaw_brain import MUSIC_LAW_KNOWLEDGE, TEN_FINGERS_CASE
    except Exception:
        return facts

    _append_fact(
        facts,
        topic="music_law_advisory",
        label="chief_musiclaw_brain fundamentals",
        value=MUSIC_LAW_KNOWLEDGE,
        provenance="chief_musiclaw_brain",
        source_ref="chief_musiclaw_brain:MUSIC_LAW_KNOWLEDGE",
        pii_tier="PUBLIC",
    )
    lowered = str(question or "").lower()
    if "ten fingers" in lowered or "log rhythm" in lowered:
        _append_fact(
            facts,
            topic="music_law_advisory",
            label="chief_musiclaw_brain Ten Fingers context",
            value=TEN_FINGERS_CASE,
            provenance="chief_musiclaw_brain",
            source_ref="chief_musiclaw_brain:TEN_FINGERS_CASE",
            pii_tier="LIGHT",
        )
    return facts


def _skill_answer_scope_facts(applied_skills: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """A leading directive that scopes a skill-matched advisory answer.

    A weak front-door model, handed the full deterministic packet, will weave the operator's
    unrelated finance/payment/gig facts into an advisory KNOWLEDGE answer (observed live:
    a music-law reply that bled in "all paid up with St Annes Live Arts"). Placed FIRST so the
    model reads it before the noise, this directive tells the model to answer only from the
    advisory knowledge and to leave the operator's business facts out unless the question asks
    for them. Skill-gated: empty when no skill matched (byte-identical default path).
    """
    if not applied_skills:
        return []
    labels = sorted(
        {str(skill.get("skill_id") or "").replace("_", " ").strip() for skill in applied_skills if skill.get("skill_id")}
    )
    scope = ("/".join(label for label in labels if label) or "advisory") + " knowledge"
    directive = (
        f"ANSWER SCOPE - this is a {scope} question. Answer it directly and conversationally using "
        "ONLY the advisory knowledge provided below. This is general information, not legal or "
        "financial advice - say so, and flag when a real professional (e.g. an entertainment "
        "lawyer) is needed. Do NOT state, restate, or reference the operator's finances, payment "
        "status, invoices, receivables, gigs, or calendar in this answer unless the question "
        "explicitly asks about them."
    )
    facts: list[dict[str, Any]] = []
    _append_fact(
        facts,
        topic="answer_scope",
        label="answer scope directive",
        value=directive,
        provenance="skill_answer_scope",
        source_ref="skill_answer_scope_directive",
        pii_tier="PUBLIC",
    )
    return facts


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

        existing_columns = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(canonical_facts)").fetchall()
        }
        optional_columns = []
        for column in (
            "refined_entity",
            "refined_claim",
            "refined_amount",
            "refined_due_date",
            "refined_status",
            "refined_as_of",
            "provenance_raw_sha256",
            "needs_operator_review",
            "refinement_status",
        ):
            if column in existing_columns:
                optional_columns.append(column)
            else:
                optional_columns.append(f"NULL AS {column}")

        # 3. Fetch full rows for candidates; apply allowed_actors filter; dedupe
        results: list[dict[str, Any]] = []
        for fact_id in candidate_ids:
            if len(results) >= limit:
                break
            row = conn.execute(
                f"""SELECT fact_text, sensitivity_class, allowed_actors, doc_category,
                           section_heading, source_file, content_hash, temporal_or_doctrine,
                           {", ".join(optional_columns)}
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
            if fact_list:
                fact_list[-1].update(
                    {
                        "structured_fact": bool(
                            row["refined_entity"]
                            and row["refined_claim"]
                            and row["refined_status"]
                            and row["refined_as_of"]
                            and not row["needs_operator_review"]
                        ),
                        "needs_operator_review": bool(row["needs_operator_review"]),
                        "refinement_status": str(row["refinement_status"] or ""),
                        "refined_entity": str(row["refined_entity"] or ""),
                        "refined_claim": str(row["refined_claim"] or ""),
                        "refined_amount": str(row["refined_amount"] or ""),
                        "refined_due_date": str(row["refined_due_date"] or ""),
                        "refined_status": str(row["refined_status"] or ""),
                        "as_of": str(row["refined_as_of"] or ""),
                        "provenance_raw_sha256": str(row["provenance_raw_sha256"] or ""),
                    }
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
    prebuilt_lm1_packet = _prebuilt_lm1_shared_packet(session)
    if prebuilt_lm1_packet is not None:
        return prebuilt_lm1_packet

    root = _read_model_root(session, read_model_root)
    truth_path = _operator_truth_store_path(session, operator_truth_store_path)
    generated_at = _utc_now()

    truth_facts, operator_truth_used, truth_ref = _operator_truth_facts(path=truth_path, question=question)
    receivable_temporal_facts, receivable_temporal_proof = _receivable_temporal_facts(
        session=session,
        question=question,
    )
    truth_facts = _resolve_operator_truth_drift(truth_facts, receivable_temporal_facts)
    contacts_facts, contacts_proof = _contacts_registry_facts(question)
    read_model_facts, read_model_refs, read_model_proof = _read_model_facts(root)
    facts = [*receivable_temporal_facts, *truth_facts, *contacts_facts, *read_model_facts]

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
        facts = [*receivable_temporal_facts, *truth_facts, *contacts_facts, *sqlite_facts, *read_model_facts]

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

    applied_skills = _registered_skill_matches(question, session=session)
    skill_facts = _music_law_skill_facts(applied_skills, question)
    if skill_facts:
        # Context-bleed fix (2026-06-29): a skill-matched advisory KNOWLEDGE question must be
        # answered FROM the skill knowledge -- not by weaving in the operator's unrelated
        # finance/payment/gig facts (observed live: "all paid up with St Annes Live Arts" bled
        # into a music-law reply). (1) Lead the packet with a scope directive; (2) elevate the
        # skill knowledge AHEAD of the bulky read-model facts so a weak front-door model meets it
        # before the noise and it never slips past the facts[:30] cap in
        # format_maestro_context_packet. Operator-truth keeps its precedence (still ahead of the
        # read models); the directive de-scopes the unrelated truth facts at answer time.
        scope_facts = _skill_answer_scope_facts(applied_skills)
        _lead = len(facts) - len(read_model_facts)
        facts = [*scope_facts, *facts[:_lead], *skill_facts, *facts[_lead:]]
    skill_receipts = [
        {
            "skill_id": skill["skill_id"],
            "applied": True,
            "owner_agent": skill["owner_agent"],
            "selected_tier": skill["selected_tier"],
            "authority": skill["authority"],
            "matched_triggers": list(skill["matched_triggers"]),
            "model_selected": skill["model_selected"],
            "selected_model_class": skill["selected_model_class"],
            "frontdoor_model_reason": skill["frontdoor_model_reason"],
        }
        for skill in applied_skills
    ]

    facts, money_status_guard_proof = _apply_money_status_anti_launder_guard(
        facts,
        question=question,
        session=session,
    )

    facts = annotate_facts_with_ledger_provenance(
        facts,
        builder_name="maestro_context_packet.build_maestro_context_packet",
    )

    if require_real_truth and (not operator_truth_used or len(read_model_refs) < 2):
        raise MaestroContextPacketError(
            "Maestro context packet requires real truth inputs: operator truth plus generated read models."
        )

    skill_refs = [f"skill:{skill['skill_id']}:{skill['source_path']}" for skill in applied_skills]
    source_refs = tuple(
        dict.fromkeys(
            [
                *(fact["source_ref"] for fact in facts),
                *(str(fact.get("ledger_source_ref") or "") for fact in facts if fact.get("ledger_source_ref")),
                *read_model_refs,
                *skill_refs,
            ]
        )
    )
    packet_basis = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "question_hash": hashlib.sha256(str(question or "").encode("utf-8")).hexdigest(),
        "source_refs": source_refs,
        "fact_count": len(facts),
        "skills_applied": [skill["skill_id"] for skill in applied_skills],
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
        "skills": applied_skills,
        "skill_receipts": skill_receipts,
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
            "skills_applied": [skill["skill_id"] for skill in applied_skills],
            "skill_receipts": skill_receipts,
            "stub_truth_root_rejected_when_required": require_real_truth,
            **ledger_machine_proof(
                builder_name="maestro_context_packet.build_maestro_context_packet",
                facts=facts,
            ),
            **receivable_temporal_proof,
            **money_status_guard_proof,
            **contacts_proof,
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
    skills = [skill for skill in packet.get("skills", ()) if isinstance(skill, Mapping)]
    actionable = packet.get("actionable") if isinstance(packet.get("actionable"), Mapping) else {}
    bounds = packet.get("bounds") if isinstance(packet.get("bounds"), Mapping) else {}
    lines = [
        f"MAESTRO_CONTEXT_PACKET {packet.get('packet_id', '')}",
        f"Generated: {packet.get('generated_at', '')}",
        temporal_anchor_text(),
        "",
        "Grounded facts:",
    ]
    for fact in facts[:30]:
        source = str(fact.get("source_ref") or "")
        provenance = str(fact.get("provenance") or "")
        tier = str(fact.get("pii_tier") or "PUBLIC")
        handling = ""
        as_of = _fact_as_of(fact)
        if as_of:
            handling = f"{handling}; as_of={as_of}"
        if fact.get("raw_operator_note") and fact.get("verbatim_readback") is False:
            handling = "; raw_operator_note=true; verbatim_readback=false; distill_not_quote"
        if fact.get("current_truth") is False:
            handling = f"{handling}; current_truth=false; drift_resolution={fact.get('drift_resolution') or 'downranked'}"
        lines.append(
            f"- {fact.get('label')}: {fact.get('value')} "
            f"[tier={tier}; provenance={provenance}; source={source}{handling}]"
        )
    if skills:
        lines.extend(["", "Applied skills:"])
        for skill in skills:
            tier_body = str(skill.get("tier_body") or "").strip()
            lines.append(
                f"- {skill.get('display_name') or skill.get('skill_id')} "
                f"({skill.get('skill_id')}): owner={skill.get('owner_agent')}; "
                f"tier={skill.get('selected_tier')}; authority={skill.get('authority')}; "
                f"tools={', '.join(str(tool) for tool in skill.get('tools', ()))}"
            )
            if tier_body:
                lines.append(f"  Instructions: {tier_body}")
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
