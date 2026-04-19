"""
chief_album_mixer.py

Mix session brain. Reads song notes and structured fields from the album
work log, looks up any Fundo/session Suno prompts for sonic reference,
and generates a focused mix session brief — what needs attention, the
reference vibe, instrument balance notes.

Triggered by:
  - "mix brief for [song]" / "mix brief [song]"
  - "mix session" / "mix session for [song]"
  - "mix [song]" — only when combined with mix context
Intent: mix_brief in chief_router.py

Saves to:
  - openclaw-vault/Album/Mix Briefs/[song].md
"""

import csv
import json
import re
from datetime import datetime
from pathlib import Path

from chief_llm import ollama_call

# ── Paths ─────────────────────────────────────────────────────────────────────

ALBUM_CSV     = Path("/mnt/c/OpenClawShared/album/album_work_log.csv")
SESSIONS_JSON = Path("/mnt/c/OpenClawShared/business/fundo_sessions.json")
MIX_BRIEFS_DIR = Path("/mnt/c/OpenClawShared/openclaw-vault/Album/Mix Briefs")

ALBUM_SONGS = [
    "1 In A Million", "A Night To Remember", "Blue Weather", "Built By Stars",
    "Can You Feel It", "Count On Your Faith", "I Cry Over Love", "Im Somebody",
    "Kamakazi Of Life", "Slow Me Down", "Ten Fingers", "The Future",
]

# ── Pass fields (instrument readiness checks) ─────────────────────────────────

PASS_FIELDS = [
    ("structure_pass",  "Structure"),
    ("vocals_pass",     "Vocals"),
    ("drums_pass",      "Drums"),
    ("bass_pass",       "Bass"),
    ("guitars_pass",    "Guitars"),
    ("keys_pass",       "Keys"),
]


# ── CSV loader ────────────────────────────────────────────────────────────────

def _load_csv() -> dict:
    data = {}
    if not ALBUM_CSV.exists():
        return data
    with ALBUM_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            title = row.get("song_title", "").strip()
            if title:
                data[title] = row
    return data


def _match_song(query: str, csv_data: dict) -> tuple[str, dict] | tuple[None, None]:
    """Fuzzy match song title from query string."""
    q = query.lower().strip()
    # Exact match first
    for title, row in csv_data.items():
        if title.lower() == q:
            return title, row
    # Partial match
    for title, row in csv_data.items():
        if q in title.lower() or title.lower() in q:
            return title, row
    return None, None


# ── Readiness summary ─────────────────────────────────────────────────────────

def _readiness_lines(row: dict) -> list[str]:
    lines = []
    mix_ready = row.get("mix_readiness", "").strip().lower()
    mix_prep   = row.get("mix_prep_done", "").strip().lower()

    if mix_ready in ("ready", "close", "yes"):
        lines.append(f"Mix readiness: ✓ {mix_ready}")
    elif mix_ready:
        lines.append(f"Mix readiness: {mix_ready}")
    else:
        pct = row.get("completion_pct", "0").strip()
        lines.append(f"Mix readiness: not set ({pct}% complete)")

    lines.append(f"Mix prep done: {'✓' if mix_prep in ('yes', 'true', 'done') else '✗'}")

    locked = row.get("version_locked", "").strip().lower()
    lines.append(f"Version locked: {'✓' if locked in ('yes', 'true', 'locked') else '✗'}")

    rerecord = row.get("needs_rerecord", "").strip().lower()
    if rerecord in ("yes", "true"):
        reason = row.get("rerecord_reason", "").strip()
        lines.append(f"⚠ Needs re-record: {reason or 'yes'}")

    # Instrument pass checks
    passes = []
    gaps = []
    for field, label in PASS_FIELDS:
        val = row.get(field, "").strip().lower()
        if val in ("done", "yes", "pass", "✓"):
            passes.append(label)
        elif val:
            gaps.append(f"{label} ({val})")
        else:
            gaps.append(f"{label} (not checked)")

    if passes:
        lines.append(f"Passes: {', '.join(passes)}")
    if gaps:
        lines.append(f"Needs attention: {', '.join(gaps)}")

    blocker = row.get("completion_blocker", row.get("blocker", "")).strip()
    if blocker:
        lines.append(f"Blocker: {blocker}")

    return lines


# ── Vocal archetype ───────────────────────────────────────────────────────────

def _vocal_context(row: dict) -> str:
    primary    = row.get("vocal_archetype_primary", "").strip()
    influences = row.get("vocal_archetype_influences", "").strip()
    if primary or influences:
        parts = []
        if primary:
            parts.append(f"Vocal archetype: {primary}")
        if influences:
            parts.append(f"Influences: {influences}")
        return " | ".join(parts)
    return ""


# ── LLM brief generator ───────────────────────────────────────────────────────

_MIX_PROMPT = """\
You are a recording engineer giving a pre-session mix brief for a music producer.

Song: {title}
Completion: {pct}%
Status: {status}
Passes done: {passes}
Needs attention: {gaps}
Blocker: {blocker}
Vocal archetype: {vocal}
Batch days planned: {batch_days}

Write a focused 3-4 sentence mix session brief:
- Lead with the most important thing to fix in this session
- Note the reference vibe / target sound (based on passes and archetype)
- End with a specific "start here" instruction for the session

Be concrete. No vague advice. Sound like an experienced mix engineer."""


def _build_brief(title: str, row: dict) -> str:
    passes = [label for field, label in PASS_FIELDS if row.get(field, "").strip().lower() in ("done", "yes", "pass")]
    gaps   = [label for field, label in PASS_FIELDS if row.get(field, "").strip().lower() not in ("done", "yes", "pass", "")]

    prompt = _MIX_PROMPT.format(
        title=title,
        pct=row.get("completion_pct", "0").strip(),
        status=row.get("status", "in-progress").strip(),
        passes=", ".join(passes) or "none",
        gaps=", ".join(gaps) or "none",
        blocker=row.get("completion_blocker", row.get("blocker", "")).strip() or "none",
        vocal=_vocal_context(row) or "not specified",
        batch_days=row.get("batch_days", "").strip() or "not planned",
    )
    result = ollama_call(prompt, timeout=30, task_class="chief_structured_plan").strip()
    return result if result else ""


# ── Mix-ready list ────────────────────────────────────────────────────────────

def _mix_ready_songs(csv_data: dict) -> list[tuple[str, dict]]:
    """Return songs where mix_readiness is set OR completion >= 50%."""
    ready = []
    for title, row in csv_data.items():
        mix_ready = row.get("mix_readiness", "").strip().lower()
        try:
            pct = int(row.get("completion_pct", "0").strip() or "0")
        except ValueError:
            pct = 0
        rerecord = row.get("needs_rerecord", "").strip().lower() in ("yes", "true")
        if mix_ready in ("ready", "close") or (pct >= 50 and not rerecord):
            ready.append((title, row))
    return sorted(ready, key=lambda x: -int(x[1].get("completion_pct", "0").strip() or "0"))


# ── Vault write ───────────────────────────────────────────────────────────────

def _write_mix_brief(title: str, row: dict, brief: str) -> None:
    MIX_BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    safe_title = re.sub(r"[^\w\s-]", "", title).strip()
    path = MIX_BRIEFS_DIR / f"{safe_title}.md"

    readiness = _readiness_lines(row)
    vocal_ctx = _vocal_context(row)
    batch = row.get("batch_days", "").strip()

    lines = [
        "---",
        f'title: "{title}"',
        "type: mix-brief",
        f"completion: {row.get('completion_pct', '0').strip()}",
        f"last_updated: {today}",
        "---",
        "",
        f"# Mix Brief: {title}",
        "",
    ]

    if brief:
        lines += [brief, ""]

    lines += ["## Track Status", ""]
    lines += [f"- {line}" for line in readiness]

    if vocal_ctx:
        lines += ["", f"**{vocal_ctx}**"]

    if batch:
        lines += ["", f"**Planned batch days:** {batch}"]

    path.write_text("\n".join(lines), encoding="utf-8")


# ── Album → Marketing handoff ─────────────────────────────────────────────────

def _queue_marketing_handoff(title: str, row: dict) -> bool:
    """If this song is mix-ready and not already in the content pipeline, add it."""
    mix_ready = row.get("mix_readiness", "").strip().lower()
    try:
        pct = int(row.get("completion_pct", "0").strip() or "0")
    except ValueError:
        pct = 0
    rerecord = row.get("needs_rerecord", "").strip().lower() in ("yes", "true")

    if not (mix_ready in ("ready", "close") or (pct >= 70 and not rerecord)):
        return False

    content_log = Path("/mnt/c/OpenClawShared/album/content_log.json")
    try:
        data = json.loads(content_log.read_text(encoding="utf-8")) if content_log.exists() else {"entries": []}
        entries = data.get("entries", [])
        if any(e.get("song") == title and e.get("status") in ("suggested", "in_progress", "posted") for e in entries):
            return False  # already tracked
        entries.append({
            "id": f"ALB-{re.sub(r'[^A-Z0-9]', '', title.upper())[:8]}-REL",
            "title": f"Release campaign: {title}",
            "platform": "Instagram, TikTok",
            "size": "short_form",
            "song": title,
            "status": "suggested",
            "date_suggested": datetime.now().strftime("%Y-%m-%d"),
            "notes": f"Auto-queued: mix brief generated, song at {pct}% completion.",
        })
        data["entries"] = entries
        content_log.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


# ── Handlers ──────────────────────────────────────────────────────────────────

def _handle_song_brief(song_query: str) -> list[str]:
    csv_data = _load_csv()
    title, row = _match_song(song_query, csv_data)

    if not title:
        # Check ALBUM_SONGS for close matches
        q = song_query.lower()
        candidates = [s for s in ALBUM_SONGS if q in s.lower()]
        if candidates:
            return [f"Did you mean: {', '.join(candidates)}?"]
        return [f"Song '{song_query}' not found in album work log."]

    brief = _build_brief(title, row)
    _write_mix_brief(title, row, brief)
    queued = _queue_marketing_handoff(title, row)

    readiness = _readiness_lines(row)
    reply_parts = [f"**Mix Brief: {title}**\n"]
    if brief:
        reply_parts.append(brief + "\n")
    reply_parts += readiness
    reply_parts.append(f"\nBrief saved to vault/Album/Mix Briefs/{title}.md")
    if queued:
        reply_parts.append(f"→ Release campaign queued in content pipeline.")
    return ["\n".join(reply_parts)]


def _handle_mix_session() -> list[str]:
    """Show all songs that are mix-ready or close."""
    csv_data = _load_csv()
    ready = _mix_ready_songs(csv_data)

    if not ready:
        return [
            "No songs marked mix-ready yet.\n"
            "Songs reach mix eligibility when mix_readiness='ready/close' or completion ≥50% with no re-record flag.\n"
            "Say 'mix brief for [song]' to generate a brief for any track."
        ]

    lines = [f"Mix-eligible songs ({len(ready)}):"]
    for title, row in ready:
        pct = row.get("completion_pct", "0").strip()
        mix_ready = row.get("mix_readiness", "").strip() or f"{pct}%"
        lines.append(f"  • {title} — {mix_ready}")
    lines.append("\nSay 'mix brief for [song]' to generate a full brief.")
    return ["\n".join(lines)]


# ── Public entry point ────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    t = text.lower().strip()

    # "mix session" with no song → list mix-eligible tracks
    if t in ("mix session", "mix status", "mix ready", "what's mix ready", "whats mix ready"):
        return _handle_mix_session()

    # Extract song name
    patterns = [
        r"mix\s+brief\s+(?:for\s+)?(.+)",
        r"mix\s+session\s+(?:for\s+)?(.+)",
        r"mix\s+(?:for\s+)?(.+)",
    ]
    for pat in patterns:
        m = re.search(pat, t)
        if m:
            song = m.group(1).strip()
            return _handle_song_brief(song)

    return _handle_mix_session()


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "mix session"
    for line in handle(text):
        print(line)
