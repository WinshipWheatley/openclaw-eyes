#!/usr/bin/env python3
"""Deterministic Maestro morning brief from structured OpenClaw read-models."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date, datetime
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = REPO_ROOT / "generated" / "read_models"
MONEY_SOURCE_TOKENS = ("receivable", "invoice", "finance", "billing", "payment")
MONEY_FACT_FRESHNESS_MAX_AGE_DAYS = 7
# Task 127 (task 138: added expected_uninvoiced): mirrors operator_surface_guard.
# _UNKNOWN_AMOUNT_STATUSES -- a pending "check expected" item is plate-worthy even before
# the amount is confirmed. expected_uninvoiced (133/136a's tier -- owed but not yet invoiced,
# distinct from "invoiced but amount uncertain") was missing here, so the St Anne's pending
# item was silently dropped from the brief entirely.
_UNKNOWN_AMOUNT_STATUS_TOKENS = {"open_amount_unknown", "amount_unknown", "unknown_amount", "expected_uninvoiced"}
EVENT_SOURCE_TOKENS = ("calendar", "gig", "schedule")
DECISION_SOURCE_TOKENS = ("approval", "work_board", "attention", "reconcile", "review")
ACTION_STATUSES = {"pending_approval", "needs_operator_review", "needs_reconcile", "approval_required"}
PRACTICE_PLAN_FILENAME = "practice_plan.json"
OPEN_AR_AGING_FILENAME = "open_ar_aging.json"
_NEXT_ACTION_WORDS = {
    "request_or_confirm_po": "request or confirm the PO",
    "reconcile_amount": "reconcile the amount",
    "follow_up_draft": "follow-up draft ready",
    "watch": "watch it",
    "wait": "not due yet",
}


@dataclass(frozen=True)
class MoneyItem:
    label: str
    amount: float | None
    currency: str
    as_of: str
    status: str = ""


@dataclass(frozen=True)
class DayEvent:
    title: str
    time: str


def build_morning_brief(*, read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT, today: date | None = None) -> str:
    root = Path(read_model_root)
    today_value = today or date.today()

    money_items = collect_open_money_items(root, today=today_value)
    events = collect_today_events(root, today_value)
    decisions = collect_decision_items(root)
    health = system_health_line(root)
    aging = aging_line(root, today=today_value)
    practice = practice_line(root)

    if not money_items and not events and not decisions and not aging and not practice:
        parts = ["Morning."]
        if health:
            parts.append("System: " + health + ".")
        return " ".join(parts)

    parts = ["Morning."]
    if money_items:
        parts.append(
            "You're clear today except money needs attention: "
            + "; ".join(_format_money_item(item) for item in money_items[:4])
            + "."
        )
    else:
        parts.append("You're clear today.")

    if events:
        parts.append("Today: " + "; ".join(_format_event(event) for event in events[:5]) + ".")

    if decisions:
        parts.append("Decisions to review: " + "; ".join(decisions[:4]) + ".")

    if aging:
        parts.append(aging)

    if practice:
        parts.append(practice)

    if health:
        system_sentence = "System: " + health + "."
        if len(parts) < 4:
            parts.append(system_sentence)
        else:
            parts[-1] = parts[-1].rstrip(".") + " " + system_sentence

    return " ".join(parts)


def collect_open_money_items(root: Path, *, today: date | None = None) -> list[MoneyItem]:
    items: list[MoneyItem] = []
    today_value = today or date.today()
    for path in _candidate_json_paths(root, MONEY_SOURCE_TOKENS):
        payload = _load_json(path)
        if payload is None:
            continue
        for obj, context in _iter_dicts(payload):
            amount = _structured_amount(obj)
            status_token = str(obj.get("payment_status") or obj.get("status") or "").strip().lower()
            # Task 127: a pending "check expected" item IS plate-worthy even with no
            # confirmed amount -- don't drop it just because there's no number yet.
            if amount is None and status_token not in _UNKNOWN_AMOUNT_STATUS_TOKENS:
                continue
            if amount is not None and not _is_open_money_status(obj):
                continue
            as_of = _first_text(obj.get("as_of"), context.get("as_of"), obj.get("generated_at"), context.get("generated_at"))
            label = _money_label(obj, context)
            if not as_of or not label:
                continue
            if _money_fact_is_stale(as_of, today=today_value):
                continue
            items.append(
                MoneyItem(
                    label=label,
                    amount=amount,
                    currency=str(obj.get("currency") or obj.get("currency_iso") or context.get("currency") or "USD"),
                    as_of=_date_part(as_of),
                    status=status_token,
                )
            )
    return _dedupe_dataclasses(items)


def _money_fact_is_stale(as_of: str, *, today: date) -> bool:
    try:
        fact_date = _parse_date(_date_part(as_of))
    except ValueError:
        return True
    return fact_date is not None and (today - fact_date).days > MONEY_FACT_FRESHNESS_MAX_AGE_DAYS


def collect_today_events(root: Path, today: date) -> list[DayEvent]:
    events: list[DayEvent] = []
    today_iso = today.isoformat()
    for path in _candidate_json_paths(root, EVENT_SOURCE_TOKENS):
        payload = _load_json(path)
        if payload is None:
            continue
        for obj, context in _iter_dicts(payload):
            event_date = _date_part(_first_text(obj.get("date"), obj.get("start_date"), obj.get("day"), context.get("date")))
            if event_date != today_iso:
                continue
            title = _first_text(obj.get("title"), obj.get("summary"), obj.get("name"), obj.get("label"))
            if not title:
                continue
            events.append(DayEvent(title=title, time=_first_text(obj.get("time"), obj.get("start_time")) or ""))
    return _dedupe_dataclasses(events)


def collect_decision_items(root: Path) -> list[str]:
    decisions: list[str] = []
    for path in _candidate_json_paths(root, DECISION_SOURCE_TOKENS):
        payload = _load_json(path)
        if payload is None:
            continue
        for obj, _context in _iter_dicts(payload):
            status = str(obj.get("status") or obj.get("board_column") or "").strip().lower()
            if status not in ACTION_STATUSES and not bool(obj.get("needs_operator_review")):
                continue
            label = _first_text(obj.get("title"), obj.get("summary"), obj.get("next_safe_move"), obj.get("human_message"))
            if _looks_like_raw_intent(label):
                continue
            if label:
                decisions.append(_strip_terminal_punctuation(_compact(label)))
    return _dedupe_strings(decisions)


def aging_line(root: Path, *, today: date | None = None) -> str:
    """One sentence from the open AR aging read model: who is past due and what to do.

    Amounts are spoken only when the row says amount_known; otherwise the client,
    month, days past due and next action carry the line (money doctrine: never
    certainty from unknown data).
    """
    payload = _load_json(root / OPEN_AR_AGING_FILENAME)
    if not isinstance(payload, Mapping):
        return ""
    today_value = today or date.today()
    as_of = _first_text(payload.get("money_source_generated_at"), payload.get("generated_at"))
    if not as_of or _money_fact_is_stale(as_of, today=today_value):
        return ""
    rows = [row for row in payload.get("rows", ()) if isinstance(row, Mapping)]
    spoken: list[str] = []
    for row in rows:
        days = row.get("days_past_due")
        try:
            days_value = int(days) if days is not None else 0
        except (TypeError, ValueError):
            days_value = 0
        action = str(row.get("next_action") or "").strip()
        if days_value <= 0 and action not in {"request_or_confirm_po", "reconcile_amount", "follow_up_draft"}:
            continue
        client = _first_text(row.get("client_display_name"), row.get("client_ref"))
        if not client:
            continue
        pieces = [client]
        month = _first_text(row.get("month"))
        if month:
            pieces.append(_month_display(month))
        amount = _structured_amount(row) if bool(row.get("amount_known")) else None
        if amount is not None:
            pieces.append(_format_amount(amount, str(row.get("currency_iso") or row.get("currency") or "USD")))
        if days_value > 0:
            pieces.append(f"{days_value} days past due")
        words = _NEXT_ACTION_WORDS.get(action)
        if words:
            pieces.append(words)
        spoken.append(", ".join(pieces))
        if len(spoken) == 2:
            break
    if not spoken:
        return ""
    return "Aging: " + "; ".join(spoken) + "."


def practice_line(root: Path) -> str:
    """One sentence from the practice plan read model: what to play today."""
    payload = _load_json(root / PRACTICE_PLAN_FILENAME)
    if not isinstance(payload, Mapping):
        return ""
    plan = payload.get("plan")
    if not isinstance(plan, list):
        plan = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    items: list[str] = []
    for entry in plan:
        if not isinstance(entry, Mapping):
            continue
        title = _first_text(entry.get("title"), entry.get("song"))
        if not title:
            continue
        piece = title
        minutes = entry.get("minutes")
        try:
            minutes_value = int(minutes) if minutes is not None else 0
        except (TypeError, ValueError):
            minutes_value = 0
        if minutes_value > 0:
            piece += f" {minutes_value} min"
        reason = _first_text(entry.get("reason"))
        if reason:
            piece += f" ({reason})"
        items.append(piece)
        if len(items) == 3:
            break
    if not items:
        return ""
    line = "Practice today: " + "; ".join(items) + "."
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    streak = summary.get("streak_days")
    try:
        streak_value = int(streak) if streak is not None else 0
    except (TypeError, ValueError):
        streak_value = 0
    if streak_value >= 2:
        line += f" Streak: {streak_value} days."
    return line


def system_health_line(root: Path) -> str:
    payload = _load_json(root / "agent_presence.json")
    if not isinstance(payload, Mapping):
        return ""
    agents = [agent for agent in payload.get("agents", ()) if isinstance(agent, Mapping)]
    online = [
        str(agent.get("display_name") or agent.get("agent_id") or "").strip()
        for agent in agents
        if str(agent.get("actual_state") or "").strip().lower() == "online"
    ]
    online = [name for name in online if name]
    if len(online) == 1:
        return f"{online[0].capitalize()} online"
    if len(online) > 1:
        return f"{len(online)} agents online"
    return ""


def run_once(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    today: date | None = None,
    runner: Callable[..., Any] = subprocess.run,
    send: bool = True,
) -> str:
    brief = build_morning_brief(read_model_root=read_model_root, today=today)
    if send:
        send_morning_brief(brief, runner=runner)
    return brief


def send_morning_brief(text: str, *, runner: Callable[..., Any] = subprocess.run) -> Any:
    env = os.environ.copy()
    env.setdefault("OPENCLAW_AGENT", "maestro")
    env.setdefault("KOKORO_AGENT", "maestro")
    env.setdefault("RELAY_LABEL", "Maestro morning brief")
    return runner(["bash", str(REPO_ROOT / "master_voice.sh")], input=text, text=True, check=True, env=env)


def _candidate_json_paths(root: Path, tokens: tuple[str, ...]) -> Iterator[Path]:
    if not root.is_dir():
        return iter(())
    return (path for path in sorted(root.glob("*.json")) if any(token in path.name.lower() for token in tokens))


def _load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


def _iter_dicts(value: Any, context: Mapping[str, Any] | None = None) -> Iterator[tuple[Mapping[str, Any], dict[str, Any]]]:
    inherited = dict(context or {})
    if isinstance(value, Mapping):
        current = dict(inherited)
        for key in ("as_of", "generated_at", "updated_at", "currency", "client", "project", "date"):
            if value.get(key) not in (None, ""):
                current.setdefault(key, value.get(key))
        yield value, current
        for child in value.values():
            yield from _iter_dicts(child, current)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_dicts(child, inherited)


def _structured_amount(obj: Mapping[str, Any]) -> float | None:
    value = obj.get("open_minor_units")
    if isinstance(value, int | float):
        return float(value) / 100.0
    for key in ("amount_minor", "minor_units", "amount_cents"):
        value = obj.get(key)
        if isinstance(value, int | float):
            return float(value) / 100.0
    value = obj.get("amount")
    if isinstance(value, int | float):
        return float(value)
    return None


def _is_open_money_status(obj: Mapping[str, Any]) -> bool:
    status = str(obj.get("status") or obj.get("payment_status") or "").strip().lower()
    if status in {"open", "open_not_paid", "entered_for_payment_not_paid", "unpaid", "outstanding", "unverified", "check_unverified", "needs_reconcile", "needs_operator_review"}:
        return True
    if status in _UNKNOWN_AMOUNT_STATUS_TOKENS:
        return True
    return bool(obj.get("open") is True)


_MONTH_CODE_RE = re.compile(r"^\d{4}-\d{2}$")


def _month_display(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m").strftime("%B")
    except ValueError:
        return value


def _money_label(obj: Mapping[str, Any], context: Mapping[str, Any]) -> str:
    client = _display_token(_first_text(obj.get("client"), obj.get("client_name"), obj.get("client_display_name"), obj.get("client_ref"), context.get("client")))
    raw_project = _first_text(obj.get("project"), obj.get("event"), obj.get("month"), obj.get("label"), obj.get("title"), obj.get("name"))
    if raw_project and _MONTH_CODE_RE.match(raw_project.strip()):
        # A bare YYYY-MM month code reads as an operator-facing "(June)", not the raw token.
        project = f"({_month_display(raw_project.strip())})"
    else:
        project = _display_token(raw_project)
    if client and project and project.lower() not in client.lower():
        return _compact(f"{client} {project}")
    return _compact(client or project or _first_text(obj.get("summary"), obj.get("description")) or "")


def _format_money_item(item: MoneyItem) -> str:
    from operator_surface_guard import render_operator_money_status_line

    amount_text = _format_amount(item.amount, item.currency) if item.amount is not None else ""
    return render_operator_money_status_line(entity=item.label, amount=amount_text, status=item.status).rstrip(".")


def _format_amount(amount: float, currency: str) -> str:
    prefix = "$" if currency.upper() == "USD" else f"{currency.upper()} "
    if amount == int(amount):
        return f"{prefix}{int(amount):,}"
    return f"{prefix}{amount:,.2f}"


def _format_event(event: DayEvent) -> str:
    return _compact(f"{event.time} {event.title}" if event.time else event.title)


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _display_token(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    known = {
        "live_arts_md": "Live Arts MD",
        "st_annes": "St. Anne's",
        "capital_hilton": "Capital Hilton",
    }
    return known.get(text, text.replace("_", " ").title() if "_" in text else text)


def _looks_like_raw_intent(value: str) -> bool:
    text = str(value or "").strip().lower()
    return text.startswith("intent:") or " intent:" in text


def _date_part(value: str) -> str:
    return str(value or "").strip()[:10]


def _compact(text: str, *, limit: int = 140) -> str:
    compacted = " ".join(str(text or "").split())
    return compacted if len(compacted) <= limit else compacted[: limit - 1].rstrip() + "."


def _strip_terminal_punctuation(text: str) -> str:
    return str(text or "").rstrip().rstrip(".;:")


def _dedupe_dataclasses(items: list[Any]) -> list[Any]:
    seen: set[Any] = set()
    deduped: list[Any] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _dedupe_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and send the OpenClaw Maestro morning brief.")
    parser.add_argument("--once", action="store_true", help="Build one brief and send it through master_voice.sh.")
    parser.add_argument("--dry-run", action="store_true", help="Print the brief instead of sending it.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--today", help="Override today's date as YYYY-MM-DD for deterministic tests.")
    args = parser.parse_args(argv)

    if not args.once:
        parser.error("--once is required")

    brief = run_once(
        read_model_root=args.read_model_root,
        today=_parse_date(args.today),
        send=not args.dry_run,
    )
    if args.dry_run:
        print(brief)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
