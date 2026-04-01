"""
chief_marketing_brain.py

Stateless marketing assistant for H. Winship Wheatley IV / Deep Pocket Records.
Every command is one-shot — no multi-turn session state.

Intents handled (called from chief_router.py):
  marketing_ideas      — generate content ideas (optionally time-constrained or song-specific)
  content_draft        — write ready-to-use copy (caption, hook, script)
  content_log_update   — update content_log.json status entries

Does NOT auto-post anything. Suggests and drafts only.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

from chief_llm import ollama_json, ollama_call

# ── Paths ──────────────────────────────────────────────────────────────────────

VAULT_MARKETING      = Path("/mnt/c/OpenClawShared/openclaw-vault/Marketing")
CONTENT_LOG_JSON     = Path("/mnt/c/OpenClawShared/album/content_log.json")
CONTENT_LOG_MD       = VAULT_MARKETING / "Content Log.md"
CSV_PATH             = Path("/mnt/c/OpenClawShared/album/album_work_log.csv")
FUNDO_CONTENT_LOG    = Path("/mnt/c/OpenClawShared/business/fundo_content_log.json")
FUNDO_CONTENT_MD     = Path("/mnt/c/OpenClawShared/openclaw-vault/Fundo/Content Log.md")

# ── Artist profile ─────────────────────────────────────────────────────────────

ARTIST_PROFILE = {
    "name":     "H. Winship Wheatley IV",
    "artist":   "Winship",
    "label":    "Deep Pocket Records (Winship Live sole prop)",
    "domain":   "deeppocketrecords.com",
    "genre":    "Yacht rock / pop rock / soul / electronica / world rhythm",
    "location": "Annapolis, MD",
    "album":    "12-song album in progress, target release 2026-04-17",
}

PLATFORM_GUIDE = {
    "Instagram": {
        "formats":     "Reels (vertical, 15–90s), quote cards, BTS stills, carousels",
        "best_for":    "Visual moments, short clips, mood content",
        "caption":     "Hook in first line, 3–5 relevant hashtags, keep it conversational",
    },
    "TikTok": {
        "formats":     "Short videos (15–60s), trending audio overlay, text-on-screen hooks",
        "best_for":    "Behind-the-scenes, personality, process, raw moments",
        "caption":     "First line is the hook, max 150 chars, 3–5 hashtags",
    },
    "YouTube": {
        "formats":     "Long-form (3–15 min), YouTube Shorts (vertical < 60s), studio vlogs",
        "best_for":    "Mini-docs, album trailers, full session recaps",
        "caption":     "SEO title, first 2 sentences matter most for description, timestamps",
    },
}

ALBUM_SONGS = [
    "1 In A Million", "A Night To Remember", "Blue Weather", "Built By Stars",
    "Can You Feel It", "Count On Your Faith", "I Cry Over Love", "Im Somebody",
    "Kamakazi Of Life", "Slow Me Down", "Ten Fingers", "The Future",
]

# ── CSV reader ─────────────────────────────────────────────────────────────────

def _load_song_statuses() -> list[dict]:
    """Load album CSV, return songs sorted by completion % descending."""
    import csv
    if not CSV_PATH.exists():
        return []
    songs = []
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            title = row.get("song_title", "").strip()
            if not title:
                continue
            try:
                pct = int(row.get("completion_pct", "0").strip() or "0")
            except ValueError:
                pct = 0
            songs.append({
                "title":       title,
                "completion":  pct,
                "locked":      row.get("version_locked", "").lower() in ("yes", "true", "locked"),
                "rerecord":    row.get("needs_rerecord", "").lower() in ("yes", "true"),
                "blocker":     row.get("completion_blocker", "").strip(),
                "status":      row.get("status", "").strip() or "in-progress",
            })
    # Songs with data sorted by completion desc; songs with no data appended at end
    songs.sort(key=lambda s: s["completion"], reverse=True)
    # Backfill any songs not in CSV
    titled = {s["title"] for s in songs}
    for t in ALBUM_SONGS:
        if t not in titled:
            songs.append({"title": t, "completion": 0, "locked": False,
                          "rerecord": False, "blocker": "no notes yet", "status": "no notes yet"})
    return songs


# ── Content log ────────────────────────────────────────────────────────────────

_LOG_DEFAULT = {"entries": []}


def _load_content_log() -> dict:
    if CONTENT_LOG_JSON.exists():
        try:
            return json.loads(CONTENT_LOG_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return json.loads(json.dumps(_LOG_DEFAULT))


def _save_content_log(data: dict) -> None:
    CONTENT_LOG_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _new_entry_id(data: dict) -> str:
    today = datetime.now().strftime("%Y%m%d")
    existing = [e["id"] for e in data.get("entries", []) if e["id"].startswith(today)]
    return f"{today}-{len(existing) + 1:03d}"


def _add_to_log(entry: dict) -> None:
    """Append a new entry to content_log.json and sync vault markdown."""
    data = _load_content_log()
    data.setdefault("entries", []).append(entry)
    _save_content_log(data)
    _write_content_log_md(data)


def _write_content_log_md(data: dict) -> None:
    """Render content_log.json → Marketing/Content Log.md."""
    entries = data.get("entries", [])

    def table_for(status_entries: list) -> str:
        if not status_entries:
            return "_(none yet)_\n"
        header = "| Title | Platform | Size | Song | Date |\n|---|---|---|---|---|\n"
        rows = []
        for e in status_entries:
            size_label = e.get("size", "").replace("_", " ").title()
            date_col = e.get("date_posted") or e.get("date_suggested", "—")
            rows.append(
                f"| {e.get('title','—')} "
                f"| {e.get('platform','—')} "
                f"| {size_label} "
                f"| {e.get('song') or '—'} "
                f"| {date_col} |"
            )
        return header + "\n".join(rows) + "\n"

    in_progress = [e for e in entries if e.get("status") == "in_progress"]
    suggested   = [e for e in entries if e.get("status") == "suggested"]
    posted      = [e for e in entries if e.get("status") == "posted"]

    today = datetime.now().strftime("%Y-%m-%d")
    content = (
        "---\n"
        "type: content-log\n"
        f"last_updated: {today}\n"
        "---\n\n"
        "# Content Log\n\n"
        "_Managed by `chief_marketing_brain.py` — do not edit manually._\n\n"
        "## In Progress\n\n"
        + table_for(in_progress)
        + "\n## Suggested\n\n"
        + table_for(suggested)
        + "\n## Posted\n\n"
        + table_for(posted)
    )
    VAULT_MARKETING.mkdir(parents=True, exist_ok=True)
    CONTENT_LOG_MD.write_text(content, encoding="utf-8")


# ── Calendar (best-effort) ─────────────────────────────────────────────────────

_GCAL_CREDS   = Path("/home/openclaw/gcal_credentials.json")
_GCAL_TOKEN   = Path("/home/openclaw/gcal_token.json")
_MUSIC_KEYWORDS = {"gig", "show", "session", "studio", "rehearsal", "performance", "concert", "soundcheck"}


def _read_upcoming_events(days: int = 14) -> list[dict]:
    """Read upcoming Google Calendar events. Returns [] if not connected."""
    if not _GCAL_CREDS.exists():
        return []
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from datetime import timezone, timedelta

        SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
        creds = None
        if _GCAL_TOKEN.exists():
            creds = Credentials.from_authorized_user_file(str(_GCAL_TOKEN), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                return []  # Need --auth first; fail silently
            _GCAL_TOKEN.write_text(creds.to_json(), encoding="utf-8")

        service = build("calendar", "v3", credentials=creds)
        now = datetime.now(timezone.utc)
        time_max = now + timedelta(days=days)
        result = service.events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=20,
        ).execute()

        events = []
        for item in result.get("items", []):
            title = item.get("summary", "")
            start = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date", "")
            event_date = start[:10] if start else ""
            t = title.lower()
            event_type = next((k for k in _MUSIC_KEYWORDS if k in t), "event")
            events.append({"title": title, "date": event_date, "event_type": event_type})
        return events
    except Exception:
        return []


def _run_gcal_auth() -> None:
    """One-time OAuth flow. Run with: python3 chief_marketing_brain.py --auth"""
    from google_auth_oauthlib.flow import InstalledAppFlow
    SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
    flow = InstalledAppFlow.from_client_secrets_file(str(_GCAL_CREDS), SCOPES)
    creds = flow.run_local_server(port=0)
    _GCAL_TOKEN.write_text(creds.to_json(), encoding="utf-8")
    print("Google Calendar auth complete. Token saved.")


# ── Context builders ───────────────────────────────────────────────────────────

def _calendar_context() -> str:
    events = _read_upcoming_events()
    if not events:
        return ""
    lines = ["Upcoming calendar events (next 14 days):"]
    for e in events:
        lines.append(f"  - {e['date']}: {e['title']} ({e['event_type']})")
    return "\n".join(lines)


def _song_context() -> str:
    songs = _load_song_statuses()
    lines = ["Album songs (sorted by completion):"]
    for s in songs:
        pct = f"{s['completion']}%" if s["completion"] else "no notes yet"
        locked = " [locked]" if s["locked"] else ""
        rerecord = " [needs re-record]" if s["rerecord"] else ""
        blocker = f" — blocker: {s['blocker']}" if s["blocker"] and s["blocker"] != "no notes yet" else ""
        lines.append(f"  - {s['title']}: {pct}{locked}{rerecord}{blocker}")
    return "\n".join(lines)


def _pending_log_context() -> str:
    data = _load_content_log()
    pending = [e for e in data.get("entries", [])
               if e.get("status") in ("suggested", "in_progress")]
    if not pending:
        return ""
    lines = ["Content already in the pipeline (don't suggest duplicates):"]
    for e in pending:
        lines.append(f"  - {e['title']} ({e['platform']}, {e['status']})")
    return "\n".join(lines)


def _ideas_context() -> str:
    parts = [
        f"Artist: {ARTIST_PROFILE['name']} aka {ARTIST_PROFILE['artist']}",
        f"Label: {ARTIST_PROFILE['label']}",
        f"Genre: {ARTIST_PROFILE['genre']}",
        f"Location: {ARTIST_PROFILE['location']}",
        f"Album status: {ARTIST_PROFILE['album']}",
        "",
        _song_context(),
    ]
    cal = _calendar_context()
    if cal:
        parts += ["", cal]
    pending = _pending_log_context()
    if pending:
        parts += ["", pending]
    return "\n".join(parts)


# ── LLM prompts ────────────────────────────────────────────────────────────────

_IDEAS_PROMPT = """\
You are a music marketing assistant for an independent artist.

{context}

Platform formats available:
- Instagram: Reels (vertical, 15–90s), quote cards, BTS stills
- TikTok: short hooks (15–60s), text-on-screen, trending audio overlay
- YouTube: long-form (3–15 min), Shorts (< 60s), studio vlogs

Content sizes:
- quick_win: under 1 hour to make
- medium_project: half day
- big_project: multi-day

Request from artist: {request}
{constraint}

Generate 3–5 specific, actionable content ideas. Each idea should be tied to something REAL — a specific song, an upcoming event, or the album story. No generic filler.

For video ideas, note what footage is needed.
For graphic ideas, note that Canva is available.
For written copy, note it can be drafted immediately.

Return a JSON array. Each object must have exactly these keys:
  title        — short name for the idea
  platform     — Instagram, TikTok, or YouTube
  size         — quick_win, medium_project, or big_project
  song         — song title if tied to a specific song, else null
  hook         — one-sentence description of the content angle
  what_to_make — 1–2 sentences of specific production instructions
  tool_note    — "Draft now (LLM)", "Canva (graphic)", or "Footage needed: [what]"

Return only the JSON array, no markdown, no extra text."""

_DRAFT_PROMPT = """\
You are a music marketing copywriter for an independent artist.

Artist: {name} aka {artist}
Label: {label}
Genre: {genre}

Request: {request}

Write ready-to-use copy for the platform and format described. Be specific, punchy, and authentic to the artist's voice (yacht rock / soul / world rhythm — sophisticated but accessible).

For captions: include a hook as the first line, body copy, and 4–6 relevant hashtags at the end.
For TikTok hooks: 1–2 sentences max, designed to be read as on-screen text.
For YouTube descriptions: title suggestion, 2–3 sentence description, 3–5 tags.

Return only the finished copy, no explanation."""

_LOG_UPDATE_PROMPT = """\
Parse this content log update command and return JSON.

Known statuses: suggested, in_progress, posted, archived
Command: {text}

Return JSON with:
  action    — "status_update" or "new_entry"
  title     — the content piece title (extract from the command)
  status    — new status (if action is status_update)
  platform  — platform if mentioned, else null
  size      — quick_win / medium_project / big_project if mentioned, else null
  song      — song title if mentioned, else null
  notes     — any extra context from the command

Return only valid JSON, no markdown."""


# ── Intent detection ───────────────────────────────────────────────────────────

def _is_draft_request(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in [
        "draft", "write me", "write a", "caption", "hook", "script",
        "copy for", "copy about", "description for",
    ])


def _is_log_update(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in [
        "log that", "i posted", "mark as", "mark it as", "mark the",
        "set as", "update the log", "log it", "posted the", "posted my",
    ])


def _parse_time_constraint(text: str) -> int | None:
    """Return available minutes if user said 'I have N minutes/hours', else None."""
    m = re.search(r"i have (\d+)\s*(minute|min|hour|hr)", text.lower())
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2)
    return n * 60 if "hour" in unit or unit == "hr" else n


def _song_from_text(text: str) -> str | None:
    """Return a known song title if explicitly mentioned."""
    t = text.lower()
    for song in ALBUM_SONGS:
        if song.lower() in t:
            return song
    return None


# ── Core handlers ──────────────────────────────────────────────────────────────

def _generate_ideas(text: str) -> list[str]:
    context = _ideas_context()
    minutes = _parse_time_constraint(text)
    song    = _song_from_text(text)

    constraint = ""
    if minutes is not None and minutes <= 60:
        constraint = f"IMPORTANT: The artist only has {minutes} minutes. Only return quick_win ideas."
    elif song:
        constraint = f"Focus ideas on the song \"{song}\" specifically."

    prompt = _IDEAS_PROMPT.format(
        context=context,
        request=text,
        constraint=constraint,
    )
    ideas = ollama_json(prompt, timeout=60)
    if not isinstance(ideas, list):
        return ["Couldn't generate ideas right now. Try again in a moment."]

    size_labels = {
        "quick_win":       "Quick Win (< 1 hr)",
        "medium_project":  "Medium (half day)",
        "big_project":     "Big Project (multi-day)",
    }

    lines = [f"Here are {len(ideas)} content ideas:\n"]
    for i, idea in enumerate(ideas, 1):
        size = size_labels.get(idea.get("size", ""), idea.get("size", ""))
        song_tag = f" · {idea['song']}" if idea.get("song") else ""
        lines.append(
            f"{i}. *{idea.get('title', 'Untitled')}*"
            f" — {idea.get('platform', '?')} · {size}{song_tag}\n"
            f"   {idea.get('hook', '')}\n"
            f"   ↳ {idea.get('what_to_make', '')}\n"
            f"   🛠 {idea.get('tool_note', '')}"
        )
        # Auto-log each suggested idea
        entry = {
            "id":             _new_entry_id(_load_content_log()),
            "date_suggested": datetime.now().strftime("%Y-%m-%d"),
            "title":          idea.get("title", "Untitled"),
            "platform":       idea.get("platform", ""),
            "size":           idea.get("size", ""),
            "status":         "suggested",
            "song":           idea.get("song") or "",
            "notes":          idea.get("what_to_make", ""),
            "date_posted":    None,
        }
        _add_to_log(entry)

    return ["\n".join(lines)]


def _draft_content(text: str) -> list[str]:
    prompt = _DRAFT_PROMPT.format(
        name=ARTIST_PROFILE["name"],
        artist=ARTIST_PROFILE["artist"],
        label=ARTIST_PROFILE["label"],
        genre=ARTIST_PROFILE["genre"],
        request=text,
    )
    result = ollama_call(prompt, timeout=60).strip()
    if not result:
        return ["Draft failed — try again."]
    return [result]


def _update_log(text: str) -> list[str]:
    prompt = _LOG_UPDATE_PROMPT.format(text=text)
    parsed = ollama_json(prompt, timeout=15)
    if not parsed:
        return ["Couldn't parse that log update. Try: 'log that I posted [title]' or 'mark [title] as in progress'."]

    action = parsed.get("action", "status_update")
    title  = parsed.get("title", "").strip()
    if not title:
        return ["I couldn't identify which content piece you meant. Try again with the title."]

    data    = _load_content_log()
    entries = data.get("entries", [])

    if action == "status_update":
        new_status = parsed.get("status", "")
        # Find entry by fuzzy title match
        match = next((e for e in entries if title.lower() in e.get("title", "").lower()
                      or e.get("title", "").lower() in title.lower()), None)
        if match:
            old_status = match.get("status", "?")
            match["status"] = new_status
            if new_status == "posted":
                match["date_posted"] = datetime.now().strftime("%Y-%m-%d")
            _save_content_log(data)
            _write_content_log_md(data)
            return [f"Updated \"{match['title']}\" from {old_status} → {new_status}."]
        else:
            return [f"Couldn't find \"{title}\" in the content log. Check the log or add it first."]

    elif action == "new_entry":
        entry = {
            "id":             _new_entry_id(data),
            "date_suggested": datetime.now().strftime("%Y-%m-%d"),
            "title":          title,
            "platform":       parsed.get("platform") or "",
            "size":           parsed.get("size") or "",
            "status":         parsed.get("status") or "suggested",
            "song":           parsed.get("song") or "",
            "notes":          parsed.get("notes") or "",
            "date_posted":    None,
        }
        _add_to_log(entry)
        return [f"Added \"{title}\" to the content log as {entry['status']}."]

    return ["Log update processed."]


# ── Fundo persona mode ─────────────────────────────────────────────────────────

def _is_fundo_request(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in [
        "fundo content", "fundo post", "fundo social", "fundo caption",
        "fundo tiktok", "fundo instagram", "post for fundo", "content for fundo",
        "fundo idea", "fundo marketing",
    ])


_FUNDO_IDEAS_PROMPT = """\
{fundo_context}

Generate 3-5 content ideas for the Fundo anonymous electronic project.

PLATFORM RULES:
- TikTok: fast visual hook (no face), rhythm-focused, mysterious — texture clips, extreme close-ups of gear
- Instagram: dark aesthetic, minimal text, image-first, cryptic long captions

PERSONA RULES:
- No face, no real name, no location
- Anonymous, mysterious, slightly unsettling in a good way
- Nobody knows if it's human or AI — protect that ambiguity
- Content should create intrigue, not explain

Request: {request}

Return a JSON array. Each object: title, platform, size (quick_win/medium_project/big_project),
hook (one cryptic sentence), what_to_make (specific visual/audio direction), tool_note.
Return only the JSON array."""

_FUNDO_DRAFT_PROMPT = """\
{fundo_context}

Write content copy for Fundo. Request: {request}

Rules:
- No face, no real name, no location revealed
- Lowercase preferred. Fragments. Cryptic but not annoying.
- Leave something unexplained — that's the hook
- Platform: {platform}

Return only the finished copy."""


def _get_fundo_ctx() -> str:
    try:
        from chief_fundo_identity import get_fundo_context
        return get_fundo_context()
    except ImportError:
        return "FUNDO: anonymous electronic project. World rhythm + club/DnB/techno. No face."


def _load_fundo_content_log() -> dict:
    if FUNDO_CONTENT_LOG.exists():
        try:
            return json.loads(FUNDO_CONTENT_LOG.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"entries": []}


def _save_fundo_content_log(data: dict) -> None:
    FUNDO_CONTENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    FUNDO_CONTENT_LOG.write_text(json.dumps(data, indent=2), encoding="utf-8")
    _write_fundo_content_md(data)


def _write_fundo_content_md(data: dict) -> None:
    entries = data.get("entries", [])
    today   = datetime.now().strftime("%Y-%m-%d")
    rows    = "\n".join(
        f"| {e.get('date_suggested','—')} | {e.get('platform','—')} | {e.get('title','—')} | {e.get('status','—')} |"
        for e in reversed(entries[-20:])
    ) or "| — | — | — | — |"
    content = (
        "---\ntype: fundo-content-log\n"
        f"last_updated: {today}\n---\n\n"
        "# Fundo Content Log\n\n"
        "_Fundo content lane — completely separate from Winship/DPR content._\n\n"
        "| Date | Platform | Title | Status |\n|---|---|---|---|\n"
        + rows + "\n"
    )
    FUNDO_CONTENT_MD.parent.mkdir(parents=True, exist_ok=True)
    FUNDO_CONTENT_MD.write_text(content, encoding="utf-8")


def _fundo_ideas(text: str) -> list[str]:
    ctx    = _get_fundo_ctx()
    prompt = _FUNDO_IDEAS_PROMPT.format(fundo_context=ctx, request=text)
    ideas  = ollama_json(prompt, timeout=45)
    if not isinstance(ideas, list):
        return ["Couldn't generate Fundo content ideas — check Claude API."]

    data = _load_fundo_content_log()
    lines = [f"Fundo content ideas ({len(ideas)}):\n"]
    for i, idea in enumerate(ideas, 1):
        lines.append(
            f"{i}. {idea.get('title','?')} — {idea.get('platform','?')}\n"
            f"   {idea.get('hook','')}\n"
            f"   ↳ {idea.get('what_to_make','')}\n"
            f"   🛠 {idea.get('tool_note','')}"
        )
        data.setdefault("entries", []).append({
            "date_suggested": datetime.now().strftime("%Y-%m-%d"),
            "title":    idea.get("title", "Untitled"),
            "platform": idea.get("platform", ""),
            "size":     idea.get("size", ""),
            "status":   "suggested",
            "hook":     idea.get("hook", ""),
        })
    _save_fundo_content_log(data)
    return ["\n".join(lines)]


def _fundo_draft(text: str) -> list[str]:
    ctx      = _get_fundo_ctx()
    platform = "TikTok" if "tiktok" in text.lower() else "Instagram"
    prompt   = _FUNDO_DRAFT_PROMPT.format(fundo_context=ctx, request=text, platform=platform)
    result   = ollama_call(prompt, timeout=40)
    return [result or "Draft failed — check Claude API."]


# ── Public entry point ─────────────────────────────────────────────────────────

def handle(text: str) -> list[str]:
    """Route to the appropriate handler based on message content."""
    # Fundo persona mode — completely separate from DPR/Winship content
    if _is_fundo_request(text):
        if _is_draft_request(text):
            return _fundo_draft(text)
        return _fundo_ideas(text)
    # DPR/Winship mode (unchanged)
    if _is_log_update(text):
        return _update_log(text)
    if _is_draft_request(text):
        return _draft_content(text)
    return _generate_ideas(text)


# ── CLI helpers ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--auth" in sys.argv:
        _run_gcal_auth()
    elif "--test-cal" in sys.argv:
        events = _read_upcoming_events()
        if events:
            for e in events:
                print(f"  {e['date']} — {e['title']} ({e['event_type']})")
        else:
            print("No events found (or calendar not connected).")
    else:
        # Quick smoke test
        test = sys.argv[1] if len(sys.argv) > 1 else "marketing ideas this week"
        print(f"Test query: {test}\n")
        for line in handle(test):
            print(line)
