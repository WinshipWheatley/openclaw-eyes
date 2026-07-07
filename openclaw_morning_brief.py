#!/usr/bin/env python3
"""Deterministic Maestro morning brief from structured OpenClaw read-models."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date
import json
import os
from pathlib import Path
import subprocess
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = REPO_ROOT / "generated" / "read_models"
MONEY_SOURCE_TOKENS = ("receivable", "invoice", "finance", "billing", "payment")
EVENT_SOURCE_TOKENS = ("calendar", "gig", "schedule")
DECISION_SOURCE_TOKENS = ("approval", "work_board", "attention", "reconcile", "review")
ACTION_STATUSES = {"pending_approval", "needs_operator_review", "needs_reconcile", "approval_required"}


@dataclass(frozen=True)
class MoneyItem:
    label: str
    amount: float
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

    money_items = collect_open_money_items(root)
    events = collect_today_events(root, today_value)
    decisions = collect_decision_items(root)
    health = system_health_line(root)

    if not money_items and not events and not decisions:
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

    if health:
        system_sentence = "System: " + health + "."
        if len(parts) < 4:
            parts.append(system_sentence)
        else:
            parts[-1] = parts[-1].rstrip(".") + " " + system_sentence

    return " ".join(parts)


def collect_open_money_items(root: Path) -> list[MoneyItem]:
    items: list[MoneyItem] = []
    for path in _candidate_json_paths(root, MONEY_SOURCE_TOKENS):
        payload = _load_json(path)
        if payload is None:
            continue
        for obj, context in _iter_dicts(payload):
            amount = _structured_amount(obj)
            if amount is None or not _is_open_money_status(obj):
                continue
            as_of = _first_text(obj.get("as_of"), context.get("as_of"), obj.get("generated_at"), context.get("generated_at"))
            label = _money_label(obj, context)
            if not as_of or not label:
                continue
            items.append(
                MoneyItem(
                    label=label,
                    amount=amount,
                    currency=str(obj.get("currency") or obj.get("currency_iso") or context.get("currency") or "USD"),
                    as_of=_date_part(as_of),
                    status=str(obj.get("payment_status") or obj.get("status") or "").strip(),
                )
            )
    return _dedupe_dataclasses(items)


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
    if status in {"open", "open_not_paid", "unpaid", "outstanding", "unverified", "check_unverified", "needs_reconcile", "needs_operator_review"}:
        return True
    return bool(obj.get("open") is True)


def _money_label(obj: Mapping[str, Any], context: Mapping[str, Any]) -> str:
    client = _display_token(_first_text(obj.get("client"), obj.get("client_name"), obj.get("client_display_name"), obj.get("client_ref"), context.get("client")))
    project = _display_token(_first_text(obj.get("project"), obj.get("event"), obj.get("month"), obj.get("label"), obj.get("title"), obj.get("name")))
    if client and project and project.lower() not in client.lower():
        return _compact(f"{client} {project}")
    return _compact(client or project or _first_text(obj.get("summary"), obj.get("description")) or "")


def _format_money_item(item: MoneyItem) -> str:
    status = str(item.status or "").strip()
    status_text = f" {status}" if status in {"needs_reconcile", "open_not_paid", "unverified", "check_unverified", "needs_operator_review"} else ""
    return f"{item.label}: {_format_amount(item.amount, item.currency)}{status_text} as of {item.as_of}"


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
