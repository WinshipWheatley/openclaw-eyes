"""No-send morning/operator brief failover chain.

The chain is intentionally small and deterministic at the bottom:
Cassandra -> Chief -> Hermes -> Guardian -> deterministic template.
It returns internal brief text and metadata only. It does not send, speak,
restart services, or mutate runtime state.
"""

from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from business_ops_ledger import resolve_business_ops_ledger_path
from operator_surface_guard import operator_surface_text


PROVIDER_ORDER = ("cassandra", "chief", "hermes", "guardian")
DETERMINISTIC_PROVIDER = "deterministic_template"
MIN_BRIEF_CHARS = 40

ProviderFn = Callable[["MorningBriefFacts"], object]


@dataclass(frozen=True)
class MorningBriefFacts:
    generated_at: str
    ledger_path: str
    latest_event_summary: str
    pending_approval_packets: int
    pending_side_effects: int
    open_packet_count: int
    canonical_fact_count: int
    source_notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_notes"] = list(self.source_notes)
        return data


@dataclass(frozen=True)
class MorningBriefAttempt:
    provider: str
    ok: bool
    reason: str
    duration_ms: int
    preview: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MorningBriefResult:
    text: str
    provider: str
    attempts: tuple[MorningBriefAttempt, ...]
    facts: MorningBriefFacts
    deterministic: bool
    sent: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "provider": self.provider,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "facts": self.facts.to_dict(),
            "deterministic": self.deterministic,
            "sent": self.sent,
        }


def _count_or_zero(conn: sqlite3.Connection, sql: str) -> int:
    try:
        row = conn.execute(sql).fetchone()
        return int(row[0] or 0) if row else 0
    except Exception:
        return 0


def _latest_event_summary(conn: sqlite3.Connection) -> str:
    try:
        row = conn.execute(
            """
            SELECT operator_visible_summary
            FROM events
            WHERE operator_visible_summary IS NOT NULL
              AND TRIM(operator_visible_summary) != ''
            ORDER BY ts DESC
            LIMIT 1
            """
        ).fetchone()
        if row and str(row[0]).strip():
            return _operator_surface_line(str(row[0]), limit=220)
    except Exception:
        pass
    return "No recent ledger event summary was available."


def load_morning_brief_facts(
    *,
    db_path: str | Path | None = None,
    now: datetime | None = None,
) -> MorningBriefFacts:
    """Read a bounded ledger snapshot; never create or mutate the ledger."""
    generated_at = (now or datetime.now()).isoformat(timespec="seconds")
    resolved = resolve_business_ops_ledger_path(str(db_path) if db_path is not None else None)
    path = Path(resolved)
    notes: list[str] = []
    latest = "No recent ledger event summary was available."
    pending_approval_packets = 0
    pending_side_effects = 0
    open_packet_count = 0
    canonical_fact_count = 0

    if not path.is_file():
        notes.append("ledger_missing")
        return MorningBriefFacts(
            generated_at=generated_at,
            ledger_path=str(path),
            latest_event_summary=latest,
            pending_approval_packets=0,
            pending_side_effects=0,
            open_packet_count=0,
            canonical_fact_count=0,
            source_notes=tuple(notes),
        )

    try:
        with sqlite3.connect(path) as conn:
            pending_approval_packets = _count_or_zero(
                conn,
                """
                SELECT COUNT(*)
                FROM packets
                WHERE approval_required = 1
                  AND LOWER(COALESCE(action_status, '')) NOT IN
                      ('approved', 'complete', 'completed', 'done', 'sent', 'blocked_no_send')
                """,
            )
            pending_side_effects = _count_or_zero(
                conn,
                """
                SELECT COUNT(*)
                FROM side_effects
                WHERE LOWER(COALESCE(status, '')) IN
                      ('pending', 'pending_approval', 'queued', 'requested')
                """,
            )
            open_packet_count = _count_or_zero(
                conn,
                """
                SELECT COUNT(*)
                FROM packets
                WHERE LOWER(COALESCE(action_status, '')) NOT IN
                      ('approved', 'complete', 'completed', 'done', 'sent', 'blocked_no_send')
                """,
            )
            canonical_fact_count = _count_or_zero(conn, "SELECT COUNT(*) FROM canonical_facts")
            latest = _latest_event_summary(conn)
            notes.append("ledger_read")
    except Exception as exc:
        notes.append(f"ledger_read_failed:{type(exc).__name__}")

    return MorningBriefFacts(
        generated_at=generated_at,
        ledger_path=str(path),
        latest_event_summary=latest,
        pending_approval_packets=pending_approval_packets,
        pending_side_effects=pending_side_effects,
        open_packet_count=open_packet_count,
        canonical_fact_count=canonical_fact_count,
        source_notes=tuple(notes),
    )


def _one_line(text: str, *, limit: int = 160) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").replace("\x00", "")).strip()
    if len(cleaned) <= limit:
        return cleaned
    clipped = cleaned[:limit].rstrip()
    boundary = clipped.rfind(" ")
    if boundary >= 80:
        clipped = clipped[:boundary]
    return clipped.rstrip(" .,;:") + "..."


def _operator_surface_line(text: object, *, limit: int = 220) -> str:
    return operator_surface_text(_one_line(_coerce_text(text), limit=limit))


def _coerce_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        for key in ("text", "brief", "body", "output", "result"):
            if key in value:
                return _coerce_text(value[key])
    return str(value)


def validate_morning_brief(text: object) -> tuple[bool, str]:
    cleaned = _one_line(_coerce_text(text), limit=600)
    if len(cleaned) < MIN_BRIEF_CHARS:
        return False, "empty_or_too_short"

    lower = cleaned.lower()
    if lower in {"none", "null", "{}", "[]", "false"}:
        return False, "empty_or_too_short"
    if re.fullmatch(r"[\W_]+", cleaned):
        return False, "non_text_garbage"
    if len(set(re.findall(r"[a-z0-9]+", lower))) < 6:
        return False, "low_information_garbage"

    blocked_markers = (
        "traceback",
        "exception:",
        "error:",
        "jsondecodeerror",
        "keyerror:",
        "timeout waiting",
        "prompt:",
        "current context:",
        "task - morning briefing",
        "task -- morning briefing",
        "you are cassandra",
        "you are chief",
        "<think>",
    )
    for marker in blocked_markers:
        if marker in lower:
            return False, "garbage_or_prompt_echo"

    if "niles" in lower and "morning" in lower:
        return False, "wrong_author_niles_insulated"

    return True, "valid"


def _preview(text: object) -> str:
    return _one_line(_coerce_text(text), limit=140)


def _attempt(
    *,
    provider: str,
    ok: bool,
    reason: str,
    started: float,
    preview: str = "",
    error: str = "",
) -> MorningBriefAttempt:
    return MorningBriefAttempt(
        provider=provider,
        ok=ok,
        reason=reason,
        duration_ms=max(0, int((time.monotonic() - started) * 1000)),
        preview=preview,
        error=error,
    )


def run_morning_brief_failover(
    *,
    providers: Mapping[str, ProviderFn] | None = None,
    db_path: str | Path | None = None,
    facts: MorningBriefFacts | None = None,
    now: datetime | None = None,
    order: tuple[str, ...] = PROVIDER_ORDER,
) -> MorningBriefResult:
    """Return the first valid internal morning/operator brief in failover order."""
    snapshot = facts or load_morning_brief_facts(db_path=db_path, now=now)
    provider_map = dict(default_morning_brief_providers() if providers is None else providers)
    attempts: list[MorningBriefAttempt] = []

    for provider in order:
        started = time.monotonic()
        fn = provider_map.get(provider)
        if fn is None:
            attempts.append(_attempt(provider=provider, ok=False, reason="provider_missing", started=started))
            continue

        try:
            candidate = fn(snapshot)
        except TimeoutError as exc:
            attempts.append(
                _attempt(
                    provider=provider,
                    ok=False,
                    reason="timeout",
                    started=started,
                    error=str(exc) or type(exc).__name__,
                )
            )
            continue
        except Exception as exc:
            attempts.append(
                _attempt(
                    provider=provider,
                    ok=False,
                    reason="exception",
                    started=started,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            continue

        ok, reason = validate_morning_brief(candidate)
        attempts.append(_attempt(provider=provider, ok=ok, reason=reason, started=started, preview=_preview(candidate)))
        if ok:
            return MorningBriefResult(
                text=_one_line(_coerce_text(candidate), limit=2400),
                provider=provider,
                attempts=tuple(attempts),
                facts=snapshot,
                deterministic=False,
            )

    started = time.monotonic()
    text = build_deterministic_morning_brief(snapshot)
    ok, reason = validate_morning_brief(text)
    if not ok:
        text = (
            "Morning brief safe mode. All expressive briefing agents were unavailable, "
            "and the ledger snapshot could not be rendered. No external send was attempted. "
            "Next safe move: open the local queue and review pending approvals before treating the day as clear."
        )
        reason = "valid"
    attempts.append(
        _attempt(
            provider=DETERMINISTIC_PROVIDER,
            ok=True,
            reason=reason,
            started=started,
            preview=_preview(text),
        )
    )
    return MorningBriefResult(
        text=text,
        provider=DETERMINISTIC_PROVIDER,
        attempts=tuple(attempts),
        facts=snapshot,
        deterministic=True,
    )


def build_guardian_morning_brief(facts: MorningBriefFacts) -> str:
    return (
        "Guardian morning failover. The expressive briefing path was not trusted, "
        f"so this internal brief is bounded to ledger facts from {Path(facts.ledger_path).name}. "
        f"Open approval packets: {facts.pending_approval_packets}. "
        f"Pending side effects: {facts.pending_side_effects}. "
        f"Open packet records: {facts.open_packet_count}. "
        f"Latest ledger note: {_operator_surface_line(facts.latest_event_summary, limit=220)} "
        "Next safe move: inspect pending approvals and active sessions before assuming the day is clear."
    )


def build_deterministic_morning_brief(facts: MorningBriefFacts) -> str:
    try:
        source_note = ", ".join(facts.source_notes) if facts.source_notes else "ledger_status_unknown"
        return (
            "Morning brief safe mode. All expressive briefing agents were unavailable or returned invalid output. "
            f"Generated at: {facts.generated_at}. "
            f"Ledger source: {facts.ledger_path} ({source_note}). "
            f"Open approval packets: {max(0, int(facts.pending_approval_packets))}. "
            f"Pending side effects: {max(0, int(facts.pending_side_effects))}. "
            f"Open packet records: {max(0, int(facts.open_packet_count))}. "
            f"Canonical facts recorded: {max(0, int(facts.canonical_fact_count))}. "
            f"Latest ledger note: {_operator_surface_line(facts.latest_event_summary, limit=220)} "
            "Next safe move: review the local queue, pending approvals, and session state before treating the day as clear. "
            "No external send, voice, service restart, or live mutation was attempted."
        )
    except Exception:
        return (
            "Morning brief safe mode. All expressive briefing agents were unavailable, "
            "and ledger facts were unavailable. Next safe move: review the local queue, "
            "pending approvals, and session state before treating the day as clear. "
            "No external send, voice, service restart, or live mutation was attempted."
        )


def _cassandra_provider(_facts: MorningBriefFacts) -> str:
    import cassandra_briefing_brain as briefing

    bundle = briefing.generate_briefing_bundle("morning")
    return _coerce_text(bundle)


def _chief_provider(_facts: MorningBriefFacts) -> str:
    import cassandra_briefing_brain as briefing

    reference = briefing._build_morning_context_from_synthesis()
    freshness = str(reference.get("freshness", "")).lower()
    if not reference.get("available") or "stale" in freshness:
        return ""
    return briefing._fallback_morning_delivery(reference)


def _hermes_provider(_facts: MorningBriefFacts) -> str:
    path = Path("generated/read_models/openclaw_hermes_sidecar_OPERATOR.md")
    try:
        lines = [
            line.strip(" -")
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    except Exception:
        return ""
    useful = [line for line in lines if len(line.split()) >= 5][:3]
    if not useful:
        return ""
    return (
        "Hermes morning advisory failover. "
        + " ".join(_one_line(line, limit=160) for line in useful)
        + " Next safe move: keep execution bounded to the reviewed queue."
    )


def _guardian_provider(facts: MorningBriefFacts) -> str:
    return build_guardian_morning_brief(facts)


def default_morning_brief_providers() -> dict[str, ProviderFn]:
    return {
        "cassandra": _cassandra_provider,
        "chief": _chief_provider,
        "hermes": _hermes_provider,
        "guardian": _guardian_provider,
    }


def cadence_dispatcher_stub() -> dict[str, Any]:
    """Static dispatcher shape for the later cadence wiring packet."""
    return {
        "status": "stub_no_runtime_scheduling",
        "send_authority": False,
        "service_restart_authority": False,
        "cadence": [
            {
                "slot": "morning",
                "flow": "agents -> subsystems -> systems -> guardian -> cassandra -> operator brief",
                "failover": list(PROVIDER_ORDER) + [DETERMINISTIC_PROVIDER],
            },
            {
                "slot": "midday",
                "flow": "chief_midday_review -> cassandra_operator_update",
                "failover": ["chief", "cassandra", "deterministic_status"],
            },
            {
                "slot": "end_of_day",
                "flow": "cassandra_eod + chief_eod_harness",
                "failover": ["chief", "cassandra", "deterministic_rollup"],
            },
            {
                "slot": "overnight",
                "flow": "chief + hermes advisory -> gated polish_loop cue",
                "idle_gate_required": True,
            },
        ],
        "wire_candidates": [
            "chief_watcher_brain.py",
            "chief_end_of_day_review.py",
            "cassandra_briefing_scheduler.py",
            "morning_brief_harness.py",
        ],
    }


__all__ = [
    "DETERMINISTIC_PROVIDER",
    "PROVIDER_ORDER",
    "MorningBriefAttempt",
    "MorningBriefFacts",
    "MorningBriefResult",
    "build_deterministic_morning_brief",
    "build_guardian_morning_brief",
    "cadence_dispatcher_stub",
    "default_morning_brief_providers",
    "load_morning_brief_facts",
    "run_morning_brief_failover",
    "validate_morning_brief",
]
