"""Deterministic date awareness for Cassandra.

This module is intentionally small and side-effect free except for the targeted
wrong-date scan helper. It keeps relative date math out of model memory.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


DEFAULT_SCAN_PATHS = (
    Path("/mnt/c/OpenClaw/logs/cassandra_conversations.jsonl"),
    Path("/mnt/c/OpenClaw/logs/cassandra_correspondence.jsonl"),
)

WRONG_DATE_SIGNATURES = (
    "june 24, 2024",
    "june 24 2024",
    "jun 24, 2024",
    "jun 24 2024",
    "2024-06-24",
)

_WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_DATE_PHRASES = (
    "last thursday",
    "this friday",
    "yesterday",
    "tomorrow",
    "next week",
    "last week",
    "next month",
    "last month",
    "next year",
    "last year",
    "today",
)


@dataclass(frozen=True)
class DateResolution:
    phrase: str
    kind: str
    label: str
    start_date: str
    end_date: str | None
    weekday: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "phrase": self.phrase,
            "kind": self.kind,
            "label": self.label,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "weekday": self.weekday,
        }


def _coerce_local_now(now: datetime | None = None) -> datetime:
    raw = now or datetime.now().astimezone()
    if raw.tzinfo is not None:
        return raw.astimezone().replace(tzinfo=None)
    return raw


def _format_date(d) -> str:
    return f"{d.isoformat()} ({d.strftime('%A')})"


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    raw = (year * 12 + (month - 1)) + delta
    return raw // 12, raw % 12 + 1


def _month_label(year: int, month: int) -> str:
    return datetime(year, month, 1).strftime("%B %Y")


def _weekday_date(today, weekday_name: str, mode: str):
    target = _WEEKDAY_INDEX[weekday_name]
    current = today.weekday()
    if mode == "this":
        days = (target - current) % 7
        return today + timedelta(days=days)
    if mode == "next":
        days = (target - current) % 7
        return today + timedelta(days=days or 7)
    if mode == "last":
        days = (current - target) % 7
        return today - timedelta(days=days or 7)
    raise ValueError(f"unsupported weekday mode: {mode}")


def resolve_relative_date_phrase(phrase: str, *, now: datetime | None = None) -> DateResolution:
    local_now = _coerce_local_now(now)
    today = local_now.date()
    normalized = " ".join(phrase.strip().lower().split())

    if normalized == "today":
        return DateResolution(normalized, "date", _format_date(today), today.isoformat(), None, today.strftime("%A"))
    if normalized == "yesterday":
        d = today - timedelta(days=1)
        return DateResolution(normalized, "date", _format_date(d), d.isoformat(), None, d.strftime("%A"))
    if normalized == "tomorrow":
        d = today + timedelta(days=1)
        return DateResolution(normalized, "date", _format_date(d), d.isoformat(), None, d.strftime("%A"))

    weekday_match = re.fullmatch(r"(this|next|last)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", normalized)
    if weekday_match:
        mode, weekday = weekday_match.groups()
        d = _weekday_date(today, weekday, mode)
        return DateResolution(normalized, "date", _format_date(d), d.isoformat(), None, d.strftime("%A"))

    if normalized in {"next week", "last week"}:
        monday_this_week = today - timedelta(days=today.weekday())
        if normalized == "next week":
            start = monday_this_week + timedelta(days=7)
        else:
            start = monday_this_week - timedelta(days=7)
        end = start + timedelta(days=6)
        label = f"{start.isoformat()} ({start.strftime('%A')}) through {end.isoformat()} ({end.strftime('%A')})"
        return DateResolution(normalized, "week_range", label, start.isoformat(), end.isoformat(), None)

    if normalized in {"next month", "last month"}:
        delta = 1 if normalized == "next month" else -1
        year, month = _add_months(today.year, today.month, delta)
        return DateResolution(normalized, "month", _month_label(year, month), f"{year:04d}-{month:02d}", None, None)

    if normalized == "next year":
        return DateResolution(normalized, "year", str(today.year + 1), str(today.year + 1), None, None)
    if normalized == "last year":
        return DateResolution(normalized, "year", str(today.year - 1), str(today.year - 1), None, None)

    raise ValueError(f"unsupported relative date phrase: {phrase}")


def build_authoritative_date_context(*, now: datetime | None = None) -> str:
    local_now = _coerce_local_now(now)
    tz_label = datetime.now().astimezone().tzname() or "local"
    resolutions = [
        resolve_relative_date_phrase(phrase, now=local_now)
        for phrase in (
            "yesterday",
            "today",
            "tomorrow",
            "this friday",
            "last thursday",
            "next week",
            "last week",
            "next month",
            "last month",
            "next year",
            "last year",
        )
    ]
    lines = [
        "[AUTHORITATIVE DATE CONTEXT]",
        f"System/operator date now: {local_now.strftime('%Y-%m-%d %H:%M')} ({local_now.strftime('%A')}, {tz_label}).",
        "Use this clock for relative dates. Do not use stale model memory for dates.",
    ]
    lines.extend(f"- {item.phrase}: {item.label}" for item in resolutions)
    return "\n".join(lines)


def _mentioned_date_phrase(query: str) -> str | None:
    lowered = " ".join(query.lower().split())
    for phrase in _DATE_PHRASES:
        if re.search(rf"\b{re.escape(phrase)}\b", lowered):
            return phrase
    return None


def answer_date_awareness_query(query: str, *, now: datetime | None = None) -> str | None:
    lowered = " ".join(query.lower().strip().split())
    phrase = _mentioned_date_phrase(lowered)
    if phrase is None:
        return None

    asks_for_date = bool(
        re.search(r"\b(what date|what day|what's the date|what is the date|when is|date for)\b", lowered)
        or re.search(r"\b(what's|what is)\s+(today|yesterday|tomorrow|this\s+\w+|last\s+\w+|next\s+\w+)\b", lowered)
        or lowered in {phrase, f"{phrase}?"}
    )
    if not asks_for_date:
        return None

    resolution = resolve_relative_date_phrase(phrase, now=now)
    if resolution.kind == "week_range":
        return f"{resolution.phrase.title()} is {resolution.label}."
    if resolution.kind == "month":
        return f"{resolution.phrase.title()} is {resolution.label}."
    if resolution.kind == "year":
        return f"{resolution.phrase.title()} is {resolution.label}."
    return f"{resolution.phrase.title()} is {resolution.label}."


def _value_contains_wrong_date(value: Any) -> bool:
    if isinstance(value, str):
        lowered = value.lower()
        return any(signature in lowered for signature in WRONG_DATE_SIGNATURES)
    if isinstance(value, list):
        return any(_value_contains_wrong_date(item) for item in value)
    if isinstance(value, dict):
        return any(_value_contains_wrong_date(item) for item in value.values())
    return False


def scan_wrong_date_correspondence(paths: tuple[Path, ...] = DEFAULT_SCAN_PATHS) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    scanned_files: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        scanned_files.append(str(path))
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line_number, raw in enumerate(lines, start=1):
            if not any(signature in raw.lower() for signature in WRONG_DATE_SIGNATURES):
                continue
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                entry = {}
            matches.append(
                {
                    "path": str(path),
                    "line_number": line_number,
                    "timestamp": str(entry.get("ts") or entry.get("timestamp") or ""),
                    "route": str(entry.get("route") or entry.get("state") or ""),
                    "matched_wrong_date_signature": True,
                    "raw_content_included": False,
                    "visible_reply_or_record": _value_contains_wrong_date(entry),
                }
            )
    return {
        "scanned_files": scanned_files,
        "wrong_date_correspondence_found": bool(matches),
        "wrong_date_match_count": len(matches),
        "matches": matches,
        "raw_content_included": False,
    }
