"""Deterministic context packet for Maestro's protected brain.

The packet is a compact, provenance-carrying view of current read models plus
operator-corrected truth. It is deliberately not a raw dump: the facts are
small, source-tagged, and safe for a gated model prompt.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "maestro_context_packet_v0"
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
_PACKET_TOP_K = 8
_PACKET_WORD_RE = re.compile(r"[a-z]+")
_PACKET_STOP_WORDS = frozenset(
    {
        "about", "across", "and", "are", "can", "could", "does", "for", "from",
        "have", "how", "into", "know", "like", "look", "next", "now", "status",
        "tell", "that", "the", "this", "today", "what", "whats", "when", "where",
        "which", "with", "would", "you", "your",
    }
)
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


def _question_terms(question: str) -> set[str]:
    return {
        token
        for token in _PACKET_WORD_RE.findall(str(question or "").lower())
        if len(token) > 2 and token not in _PACKET_STOP_WORDS
    }


def _score_fact(fact: Mapping[str, Any], terms: set[str]) -> int:
    text = " ".join(str(fact.get(k) or "") for k in ("topic", "label", "value")).lower()
    return sum(2 for term in terms if term in text)


def _trim_facts(facts: list[dict[str, Any]], question: str) -> list[dict[str, Any]]:
    """Return top-K question-relevant facts; if no question or few facts, return all."""
    if not question or len(facts) <= _PACKET_TOP_K:
        return facts
    terms = _question_terms(question)
    if not terms:
        return facts
    scored = sorted(((  _score_fact(f, terms), i, f) for i, f in enumerate(facts)), reverse=True)
    relevant = [f for score, _i, f in scored if score > 0]
    return relevant[:_PACKET_TOP_K] if relevant else facts[:_PACKET_TOP_K]


def _read_model_facts(root: Path, question: str = "") -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
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

    return _trim_facts(facts, question), refs, proof


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


def build_maestro_context_packet(
    *,
    question: str = "",
    session: Mapping[str, Any] | None = None,
    source_surface: str = "operator_maestro_chat",
    read_model_root: str | Path | None = None,
    operator_truth_store_path: str | Path | None = None,
    require_real_truth: bool = True,
) -> dict[str, Any]:
    root = _read_model_root(session, read_model_root)
    truth_path = _operator_truth_store_path(session, operator_truth_store_path)
    generated_at = _utc_now()

    truth_facts, operator_truth_used, truth_ref = _operator_truth_facts(path=truth_path, question=question)
    read_model_facts, read_model_refs, read_model_proof = _read_model_facts(root, question=question)
    facts = [*truth_facts, *read_model_facts]

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
