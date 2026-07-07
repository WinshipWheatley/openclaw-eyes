"""
chief_calendar_brain.py

Reads Google Calendar via API and delivers clean, readable summaries.
Not a data dump — categorized, flagged, and actionable.

Reads Google Calendar via google_access_broker.py and delivers
clean, readable summaries. Dry-run mode when broker is unavailable.

Triggered by:
  - "what's my week" / "what's today" / "what's coming up"
  - "calendar" / "schedule"
Intent: calendar_query in chief_router.py

Saves to:
  - /mnt/c/OpenClawShared/openclaw-vault/Calendar/Weekly Log.md

Auth is handled exclusively by google_access_broker.py.
Run: python3 google_access_broker.py --auth  (one-time setup)
"""

from datetime import datetime, date, timedelta
from pathlib import Path

from adaptive_model_call import adaptive_ollama_text

ollama_call = adaptive_ollama_text

def _local_model_call(*args, **kwargs):
    return globals()["ollama_call"](*args, **kwargs)

# ── Paths ────────────────────────────────────────────────────────────────────────

VAULT_CAL_DIR  = Path("/mnt/c/OpenClawShared/openclaw-vault/Calendar")
WEEKLY_LOG_MD  = VAULT_CAL_DIR / "Weekly Log.md"

# ── Category rules ───────────────────────────────────────────────────────────────

BUSINESS_KEYWORDS = {
    "gig", "show", "session", "studio", "rehearsal", "performance", "concert",
    "soundcheck", "booking", "invoice", "meeting", "call", "zoom", "client",
    "record", "mix", "master", "photo shoot", "photoshoot", "interview",
    "podcast", "stream", "release", "drop", "launch", "promo", "press",
    "tax", "quarterly", "deadline", "payment", "contract",
}

PERSONAL_KEYWORDS = {
    "family", "birthday", "anniversary", "doctor", "dentist", "medical",
    "vacation", "trip", "flight", "gym", "church", "dinner", "date",
    "mortgage", "rent", "utilities",
}

# Known recurring dates (hardcoded awareness)
_MORTGAGE_DAY  = 1   # 1st of every month
_QUARTERLY_TAX = [   # from CPA brain
    ("Q1 2026", date(2026, 4, 15)),
    ("Q2 2026", date(2026, 6, 16)),
    ("Q3 2026", date(2026, 9, 15)),
    ("Q4 2026", date(2027, 1, 15)),
]


def _categorize(title: str) -> str:
    t = title.lower()
    if any(k in t for k in BUSINESS_KEYWORDS):
        return "business"
    if any(k in t for k in PERSONAL_KEYWORDS):
        return "personal"
    return "other"


# ── Google Calendar reader ────────────────────────────────────────────────────────

def _fetch_events(days_ahead: int = 7) -> list[dict] | None:
    """Fetch events via the Google Access Broker. Returns None if broker unavailable."""
    try:
        from google_access_broker import call as broker_call
        result = broker_call("cassandra", "google.calendar.read", {"days_ahead": days_ahead})
        if not result["ok"]:
            return None
        events = []
        for item in result["data"]:
            title     = item.get("summary", "(no title)")
            start     = item.get("start", {})
            start_dt  = start.get("dateTime") or start.get("date", "")
            end       = item.get("end", {})
            end_dt    = end.get("dateTime") or end.get("date", "")
            reminder  = item.get("reminders", {}).get("useDefault", True)
            overrides = item.get("reminders", {}).get("overrides", [])
            has_reminder = reminder or bool(overrides)
            events.append({
                "title":        title,
                "start":        start_dt,
                "end":          end_dt,
                "all_day":      "T" not in start_dt,
                "category":     _categorize(title),
                "has_reminder": has_reminder,
                "description":  item.get("description", ""),
            })
        return events
    except Exception:
        return None


# ── Hardcoded awareness injector ─────────────────────────────────────────────────

def _hardcoded_upcoming(days_ahead: int = 7) -> list[dict]:
    """Return always-known dates that don't need a calendar event."""
    today    = date.today()
    end_date = today + timedelta(days=days_ahead)
    items    = []

    # Mortgage (1st of month)
    for month_offset in range(2):
        m = (today.month + month_offset - 1) % 12 + 1
        y = today.year + (today.month + month_offset - 1) // 12
        mortgage_date = date(y, m, _MORTGAGE_DAY)
        if today <= mortgage_date <= end_date:
            items.append({
                "title":        "Mortgage payment due",
                "start":        mortgage_date.isoformat(),
                "category":     "personal",
                "has_reminder": True,
                "source":       "hardcoded",
            })

    # Quarterly tax deadlines
    for label, deadline in _QUARTERLY_TAX:
        if today <= deadline <= end_date:
            items.append({
                "title":        f"Estimated tax due — {label}",
                "start":        deadline.isoformat(),
                "category":     "business",
                "has_reminder": False,   # flag if not on calendar
                "source":       "hardcoded",
            })

    return items


# ── Formatter ────────────────────────────────────────────────────────────────────

_SUMMARY_PROMPT = """\
You are a personal assistant summarizing a musician's upcoming week.

Events this week (next 7 days):
{event_lines}

Hardcoded reminders:
{hardcoded_lines}

Write a clean, readable 7-day summary. Rules:
- Group by day (Mon, Tue, etc.) — skip days with nothing
- Categorize clearly: business events (gigs, sessions, meetings, tax) vs personal
- Flag any item that is missing a calendar reminder (marked "NO REMINDER")
- End with a 1-sentence "Focus this week:" recommendation based on what's coming up
- Keep it conversational — like a good assistant, not a data export
- Plain text only, no markdown tables

If there are no events at all, say so clearly and give a general productivity nudge."""


def _format_event_line(e: dict) -> str:
    start = e.get("start", "")
    try:
        if "T" in start:
            dt    = datetime.fromisoformat(start.replace("Z", "+00:00"))
            label = dt.strftime("%a %b %-d at %-I:%M%p").lower()
        else:
            dt    = datetime.strptime(start, "%Y-%m-%d")
            label = dt.strftime("%a %b %-d (all day)").lower()
    except Exception:
        label = start[:10]

    cat     = e.get("category", "other")
    remind  = "" if e.get("has_reminder") else " [NO REMINDER]"
    source  = " (auto-reminder)" if e.get("source") == "hardcoded" else ""
    return f"  {label} — {e['title']} [{cat}]{remind}{source}"


def _build_summary(events: list[dict], hardcoded: list[dict]) -> str:
    event_lines    = "\n".join(_format_event_line(e) for e in events) or "  (no events found)"
    hardcoded_lines = "\n".join(_format_event_line(h) for h in hardcoded) or "  (none this week)"

    prompt = _SUMMARY_PROMPT.format(
        event_lines=event_lines,
        hardcoded_lines=hardcoded_lines,
    )
    result = _local_model_call(prompt, timeout=30)
    return result or f"Events this week:\n{event_lines}\n\nHardcoded:\n{hardcoded_lines}"


# ── Dry-run mode message ──────────────────────────────────────────────────────────

_SETUP_MSG = """\
Calendar brain could not reach Google Calendar via the broker.

To reconnect: run python3 /home/openclaw/google_access_broker.py --auth
and verify /home/openclaw/.google-secrets/token.json is present.

Hardcoded reminders still active:
{hardcoded}"""


# ── Vault writer ─────────────────────────────────────────────────────────────────

def _write_weekly_log(summary: str, connected: bool) -> None:
    VAULT_CAL_DIR.mkdir(parents=True, exist_ok=True)
    today   = date.today().strftime("%Y-%m-%d")
    week_of = (date.today() - timedelta(days=date.today().weekday())).strftime("%Y-%m-%d")
    status  = "✅ Connected" if connected else "⚠️ Not connected (dry-run)"

    existing = WEEKLY_LOG_MD.read_text(encoding="utf-8") if WEEKLY_LOG_MD.exists() else (
        "---\ntype: calendar-log\n---\n\n# Calendar — Weekly Log\n\n"
        "_Generated by `chief_calendar_brain.py`_\n"
    )

    entry = (
        f"\n## Week of {week_of} _(updated {today})_\n\n"
        f"**Calendar status:** {status}\n\n"
        f"{summary}\n\n---"
    )

    # Replace the most recent entry for this week if it exists, else append
    if f"## Week of {week_of}" in existing:
        import re
        existing = re.sub(
            rf"## Week of {week_of}.*?(?=\n## Week of |\Z)",
            entry.lstrip("\n"),
            existing,
            flags=re.DOTALL,
        )
        WEEKLY_LOG_MD.write_text(existing, encoding="utf-8")
    else:
        WEEKLY_LOG_MD.write_text(existing + entry, encoding="utf-8")


# ── Public entry point ────────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    t          = text.lower().strip()
    hardcoded  = _hardcoded_upcoming(days_ahead=7)
    events     = _fetch_events(days_ahead=7)
    connected  = events is not None

    if not connected:
        hc_lines = "\n".join(_format_event_line(h) for h in hardcoded) or "  (none this week)"
        msg      = _SETUP_MSG.format(hardcoded=hc_lines)
        _write_weekly_log(msg, connected=False)
        return [msg]

    summary = _build_summary(events, hardcoded)
    _write_weekly_log(summary, connected=True)
    return [summary]


if __name__ == "__main__":
    import sys
    text = " ".join(a for a in sys.argv[1:] if not a.startswith("--")) or "what's my week"
    print(f"Running calendar brain: '{text}'\n")
    for line in handle(text):
        print(line)
    print(f"\nWeekly Log: {WEEKLY_LOG_MD}")
