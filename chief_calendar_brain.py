"""
chief_calendar_brain.py

Reads Google Calendar via API and delivers clean, readable summaries.
Not a data dump — categorized, flagged, and actionable.

Dry-run mode when credentials are not configured. Setup instructions
printed automatically the first time it runs without credentials.

Triggered by:
  - "what's my week" / "what's today" / "what's coming up"
  - "calendar" / "schedule"
Intent: calendar_query in chief_router.py

Saves to:
  - /mnt/c/OpenClawShared/openclaw-vault/Calendar/Weekly Log.md

Setup (one-time):
  1. Go to console.cloud.google.com → create a project
  2. Enable Google Calendar API
  3. Create OAuth 2.0 credentials → download as credentials.json
  4. Place credentials.json at /home/openclaw/gcal_credentials.json
  5. Run: python3 chief_calendar_brain.py --auth
"""

import json
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

from chief_llm import ollama_call

# ── Paths ────────────────────────────────────────────────────────────────────────

VAULT_CAL_DIR  = Path("/mnt/c/OpenClawShared/openclaw-vault/Calendar")
WEEKLY_LOG_MD  = VAULT_CAL_DIR / "Weekly Log.md"
GCAL_CREDS     = Path("/home/openclaw/gcal_credentials.json")
GCAL_TOKEN     = Path("/home/openclaw/gcal_token.json")

GCAL_SCOPES    = ["https://www.googleapis.com/auth/calendar.readonly"]

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

def _load_credentials():
    """Load or refresh OAuth2 credentials. Returns None if not configured."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        if not GCAL_CREDS.exists():
            return None

        creds = None
        if GCAL_TOKEN.exists():
            creds = Credentials.from_authorized_user_file(str(GCAL_TOKEN), GCAL_SCOPES)

        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            GCAL_TOKEN.write_text(creds.to_json(), encoding="utf-8")
            return creds

        return None  # Need --auth flow
    except Exception:
        return None


def _fetch_events(days_ahead: int = 7) -> list[dict] | None:
    """Fetch events from Google Calendar. Returns None if not configured."""
    creds = _load_credentials()
    if not creds:
        return None

    try:
        from googleapiclient.discovery import build

        service  = build("calendar", "v3", credentials=creds)
        now      = datetime.now(timezone.utc)
        time_max = now + timedelta(days=days_ahead)

        result = service.events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=50,
        ).execute()

        events = []
        for item in result.get("items", []):
            title    = item.get("summary", "(no title)")
            start    = item.get("start", {})
            start_dt = start.get("dateTime") or start.get("date", "")
            end      = item.get("end", {})
            end_dt   = end.get("dateTime") or end.get("date", "")
            reminder = item.get("reminders", {}).get("useDefault", True)
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
    except Exception as e:
        return []


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
    result = ollama_call(prompt, timeout=30)
    return result or f"Events this week:\n{event_lines}\n\nHardcoded:\n{hardcoded_lines}"


# ── Dry-run mode message ──────────────────────────────────────────────────────────

_SETUP_MSG = """\
Calendar brain is not connected to Google Calendar yet.

To connect:
1. Go to console.cloud.google.com
2. Create a project → Enable "Google Calendar API"
3. Go to APIs & Services → Credentials → Create OAuth 2.0 Client ID (Desktop app)
4. Download the JSON → save as /home/openclaw/gcal_credentials.json
5. Run: python3 /home/openclaw/chief_calendar_brain.py --auth
6. Complete the browser OAuth flow (one-time)
7. Token saved automatically — all future reads are automatic

Until connected, calendar queries will show this setup message.

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


# ── Auth flow + CLI ───────────────────────────────────────────────────────────────

def _run_auth() -> None:
    """One-time OAuth2 flow. Run: python3 chief_calendar_brain.py --auth"""
    from google_auth_oauthlib.flow import InstalledAppFlow
    if not GCAL_CREDS.exists():
        print(f"ERROR: {GCAL_CREDS} not found. Download from Google Cloud Console first.")
        return
    flow  = InstalledAppFlow.from_client_secrets_file(str(GCAL_CREDS), GCAL_SCOPES)
    creds = flow.run_local_server(port=0)
    GCAL_TOKEN.write_text(creds.to_json(), encoding="utf-8")
    print(f"Auth complete. Token saved to {GCAL_TOKEN}")


if __name__ == "__main__":
    import sys
    if "--auth" in sys.argv:
        _run_auth()
    else:
        text = " ".join(a for a in sys.argv[1:] if not a.startswith("--")) or "what's my week"
        print(f"Running calendar brain: '{text}'\n")
        for line in handle(text):
            print(line)
        print(f"\nWeekly Log: {WEEKLY_LOG_MD}")
