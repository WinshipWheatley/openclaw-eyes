"""
chief_publishing_brain.py

Tracks every DPR song as a business asset — registration status, splits,
royalty streams, and sync opportunities. Knows the 12 Deep Pocket Records
songs. Ten Fingers is pre-flagged as disputed.

Triggered by:
  - "publishing status" / "catalog status" / "what songs are registered"
  - "sync opportunities" / "what songs are sync-ready"
  - "ten fingers status"
  - "update publishing [song] [field] [value]"
  - "register [song]" (marks as PRO-registered)
Intent: publishing_query in chief_router.py

Saves to:
  - /mnt/c/OpenClawShared/business/publishing_registry.json  (source of truth)
  - openclaw-vault/Business/Publishing Log.md                (Obsidian)
"""

import csv
import json
from datetime import date
from pathlib import Path

from chief_llm import claude_json as ollama_json

# ── Paths ──────────────────────────────────────────────────────────────────────

BUSINESS_DIR      = Path("/mnt/c/OpenClawShared/business")
PUBLISHING_JSON   = BUSINESS_DIR / "publishing_registry.json"
PUBLISHING_MD     = Path("/mnt/c/OpenClawShared/openclaw-vault/Business/Publishing Log.md")
ALBUM_CSV         = Path("/mnt/c/OpenClawShared/album/album_work_log.csv")

# ── Catalog ────────────────────────────────────────────────────────────────────

DPR_SONGS = [
    "1 In A Million",
    "A Night To Remember",
    "Blue Weather",
    "Built By Stars",
    "Can You Feel It",
    "Count On Your Faith",
    "I Cry Over Love",
    "Im Somebody",
    "Kamakazi Of Life",
    "Slow Me Down",
    "Ten Fingers",
    "The Future",
]

# Default registry entry for each song
_DEFAULT_ENTRY = {
    "writer_splits":       "100% Winship Wheatley IV",
    "publisher":           "Deep Pocket Records",
    "pro_registered":      False,
    "registration_number": "",
    "master_owner":        "Deep Pocket Records",
    "distribution":        "DistroKid (pending)",
    "sync_eligible":       True,
    "status":              "unregistered",   # clear | disputed | unregistered
    "notes":               "",
}

# Ten Fingers overrides
_TEN_FINGERS_OVERRIDE = {
    "writer_splits":       "disputed — no signed agreement",
    "publisher":           "Log Rhythm Records (claimed)",
    "pro_registered":      False,
    "registration_number": "",
    "master_owner":        "Log Rhythm Records (controlled by Renae Timmi Jenkins)",
    "distribution":        "DistroKid (via Renae Timmi Jenkins / Log Rhythm Records)",
    "sync_eligible":       False,
    "status":              "disputed",
    "notes":               (
        "Co-ownership of Log Rhythm Records verbally claimed but not on MD registry. "
        "Name appeared in unsigned internal doc. No signed co-writing agreement. "
        "Do not license for sync without legal advice."
    ),
}


# ── Registry load / save ───────────────────────────────────────────────────────

def _default_registry() -> dict:
    entries = {}
    for title in DPR_SONGS:
        entry = dict(_DEFAULT_ENTRY)
        if title == "Ten Fingers":
            entry.update(_TEN_FINGERS_OVERRIDE)
        entries[title] = entry
    return {"songs": entries, "last_updated": date.today().strftime("%Y-%m-%d")}


def _load_registry() -> dict:
    if PUBLISHING_JSON.exists():
        try:
            data = json.loads(PUBLISHING_JSON.read_text(encoding="utf-8"))
            # Ensure all 12 songs present (add new defaults for any missing)
            songs = data.setdefault("songs", {})
            for title in DPR_SONGS:
                if title not in songs:
                    entry = dict(_DEFAULT_ENTRY)
                    if title == "Ten Fingers":
                        entry.update(_TEN_FINGERS_OVERRIDE)
                    songs[title] = entry
            return data
        except Exception:
            pass
    return _default_registry()


def _save_registry(data: dict) -> None:
    BUSINESS_DIR.mkdir(parents=True, exist_ok=True)
    data["last_updated"] = date.today().strftime("%Y-%m-%d")
    PUBLISHING_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Album CSV: production completion ──────────────────────────────────────────

def _load_completion() -> dict[str, str]:
    """Return {title: completion_pct} from album CSV."""
    result = {}
    if not ALBUM_CSV.exists():
        return result
    try:
        with ALBUM_CSV.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                title = row.get("song_title", "").strip()
                pct   = row.get("completion_pct", "0").strip() or "0"
                if title:
                    result[title] = pct
    except Exception:
        pass
    return result


# ── Song title fuzzy match ────────────────────────────────────────────────────

def _match_song(text: str) -> str | None:
    t = text.lower()
    for title in DPR_SONGS:
        if title.lower() in t:
            return title
    return None


# ── Field update via LLM ──────────────────────────────────────────────────────

_UPDATE_PROMPT = """\
Extract publishing update details from this message.
Known song titles: {songs}
Known fields: writer_splits, publisher, pro_registered (true/false),
  registration_number, master_owner, distribution, sync_eligible (true/false),
  status (clear/disputed/unregistered), notes

Return a JSON object with:
  song   — exact song title from the list above, or null
  field  — field name to update, or null
  value  — new value as string, or null

Message: {text}
Return only valid JSON, no markdown."""


def _parse_update(text: str) -> tuple[str | None, str | None, str | None]:
    prompt = _UPDATE_PROMPT.format(
        songs=", ".join(f'"{s}"' for s in DPR_SONGS),
        text=text,
    )
    parsed = ollama_json(prompt, timeout=20)
    if not isinstance(parsed, dict):
        return None, None, None
    return parsed.get("song"), parsed.get("field"), parsed.get("value")


# ── Markdown writer ────────────────────────────────────────────────────────────

def _status_icon(status: str) -> str:
    return {"clear": "✅", "disputed": "⚠️", "unregistered": "🔲"}.get(status, "?")


def _write_publishing_md() -> None:
    data       = _load_registry()
    songs      = data.get("songs", {})
    completion = _load_completion()
    today      = date.today().strftime("%Y-%m-%d")

    # Summary counts
    total       = len(DPR_SONGS)
    registered  = sum(1 for s in songs.values() if s.get("pro_registered"))
    disputed    = sum(1 for s in songs.values() if s.get("status") == "disputed")
    clear       = sum(1 for s in songs.values() if s.get("status") == "clear")
    sync_ready  = sum(1 for s in songs.values() if s.get("sync_eligible") and s.get("status") == "clear")

    # Catalog table
    rows = []
    for title in DPR_SONGS:
        s    = songs.get(title, {})
        icon = _status_icon(s.get("status", "unregistered"))
        pro  = "✓" if s.get("pro_registered") else "—"
        sync = "✓" if s.get("sync_eligible") else "—"
        comp = completion.get(title, "—")
        if comp and comp != "—":
            comp = f"{comp}%"
        rows.append(f"| {icon} | [[../Album/Songs/{title}\\|{title}]] | {pro} | {sync} | {comp} |")

    catalog_table = (
        "| Status | Song | PRO | Sync | Production |\n"
        "|---|---|---|---|---|\n"
        + "\n".join(rows)
    )

    # Disputed songs detail
    disputed_sections = []
    for title in DPR_SONGS:
        s = songs.get(title, {})
        if s.get("status") == "disputed":
            disputed_sections.append(
                f"### {title}\n"
                f"- **Publisher:** {s.get('publisher','?')}\n"
                f"- **Master owner:** {s.get('master_owner','?')}\n"
                f"- **Distribution:** {s.get('distribution','?')}\n"
                f"- **Splits:** {s.get('writer_splits','?')}\n"
                f"- **Notes:** {s.get('notes','')}\n"
            )

    content = (
        "---\n"
        "type: publishing-log\n"
        f"last_updated: {today}\n"
        "---\n\n"
        "# Publishing Log\n\n"
        "_Managed by `chief_publishing_brain.py` — do not edit manually._\n\n"
        "## Summary\n\n"
        f"| | |\n|---|---|\n"
        f"| Total songs | {total} |\n"
        f"| PRO registered | {registered} / {total} |\n"
        f"| Clear for sync | {sync_ready} |\n"
        f"| Disputed | {disputed} |\n\n"
        "## Catalog\n\n"
        "**Legend:** ✅ Clear · ⚠️ Disputed · 🔲 Unregistered\n\n"
        + catalog_table + "\n\n"
        + ("## Disputed Songs\n\n" + "\n".join(disputed_sections) if disputed_sections else "")
        + "\n## Register a Song\n\n"
        "Use: `register [song title]` or `update publishing [song] [field] [value]`\n"
    )
    PUBLISHING_MD.parent.mkdir(parents=True, exist_ok=True)
    PUBLISHING_MD.write_text(content, encoding="utf-8")


# ── Formatters ─────────────────────────────────────────────────────────────────

def _format_catalog(songs: dict, completion: dict) -> str:
    lines = ["📋 Deep Pocket Records — Publishing Catalog\n"]
    for title in DPR_SONGS:
        s    = songs.get(title, {})
        icon = _status_icon(s.get("status", "unregistered"))
        pro  = "PRO ✓" if s.get("pro_registered") else "PRO —"
        sync = "Sync ✓" if (s.get("sync_eligible") and s.get("status") == "clear") else ""
        comp = completion.get(title, "?")
        flag = " ⚠️ DISPUTED" if s.get("status") == "disputed" else ""
        lines.append(f"{icon} {title}  [{pro}]{(' ' + sync) if sync else ''}{flag}  ({comp}%)")

    registered = sum(1 for s in songs.values() if s.get("pro_registered"))
    disputed   = sum(1 for s in songs.values() if s.get("status") == "disputed")
    sync_ready = sum(1 for s in songs.values() if s.get("sync_eligible") and s.get("status") == "clear")
    lines.append(f"\n{registered}/12 PRO-registered · {sync_ready} sync-ready · {disputed} disputed")
    return "\n".join(lines)


def _format_song_detail(title: str, s: dict) -> str:
    icon = _status_icon(s.get("status", "unregistered"))
    return (
        f"{icon} {title}\n"
        f"Status: {s.get('status','?').upper()}\n"
        f"Splits: {s.get('writer_splits','?')}\n"
        f"Publisher: {s.get('publisher','?')}\n"
        f"Master owner: {s.get('master_owner','?')}\n"
        f"Distribution: {s.get('distribution','?')}\n"
        f"PRO registered: {'Yes' if s.get('pro_registered') else 'No'}\n"
        f"Sync eligible: {'Yes' if s.get('sync_eligible') else 'No'}\n"
        + (f"Notes: {s['notes']}" if s.get("notes") else "")
    )


def _format_sync_report(songs: dict) -> str:
    ready    = [t for t in DPR_SONGS if songs.get(t, {}).get("sync_eligible") and songs.get(t, {}).get("status") == "clear"]
    blocked  = [t for t in DPR_SONGS if not songs.get(t, {}).get("sync_eligible") or songs.get(t, {}).get("status") != "clear"]
    lines    = ["🎬 Sync Opportunities — Deep Pocket Records\n"]
    if ready:
        lines.append("Ready for sync licensing:")
        for t in ready:
            lines.append(f"  ✅ {t}")
    else:
        lines.append("No songs currently clear for sync.")
    if blocked:
        lines.append("\nNot sync-ready (disputed or unregistered):")
        for t in blocked:
            s    = songs.get(t, {})
            why  = "disputed" if s.get("status") == "disputed" else "unregistered"
            lines.append(f"  ⚠️ {t} — {why}")
    lines.append("\nTo clear a song: register it with ASCAP/BMI and update status to 'clear'.")
    return "\n".join(lines)


# ── Public entry point ─────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    t    = text.lower().strip()
    data = _load_registry()
    songs = data["songs"]

    # ── Ten Fingers detail ─────────────────────────────────────────────────────
    if "ten fingers" in t and ("status" in t or "detail" in t or t == "ten fingers status"):
        reply = _format_song_detail("Ten Fingers", songs.get("Ten Fingers", {}))
        _write_publishing_md()
        return [reply]

    # ── Sync opportunities ─────────────────────────────────────────────────────
    if any(k in t for k in ("sync", "sync-ready", "sync ready", "sync opportunities")):
        reply = _format_sync_report(songs)
        _write_publishing_md()
        return [reply]

    # ── Register a song ────────────────────────────────────────────────────────
    if t.startswith("register "):
        song_match = _match_song(text)
        if not song_match:
            return [f"Song not found. Known songs: {', '.join(DPR_SONGS)}"]
        songs[song_match]["pro_registered"] = True
        if songs[song_match]["status"] == "unregistered":
            songs[song_match]["status"] = "clear"
        _save_registry(data)
        _write_publishing_md()
        return [f"✅ {song_match} marked as PRO-registered and status set to 'clear'."]

    # ── Update a field ────────────────────────────────────────────────────────
    if any(k in t for k in ("update publishing", "update song", "set ")):
        song_match, field, value = _parse_update(text)
        if not song_match or not field or value is None:
            return ["Couldn't parse that update. Try: 'update publishing Ten Fingers status clear'"]
        if song_match not in songs:
            return [f"Song '{song_match}' not found in registry."]
        valid_fields = {"writer_splits", "publisher", "pro_registered", "registration_number",
                        "master_owner", "distribution", "sync_eligible", "status", "notes"}
        if field not in valid_fields:
            return [f"Unknown field '{field}'. Valid fields: {', '.join(sorted(valid_fields))}"]
        # Coerce booleans
        if field in ("pro_registered", "sync_eligible"):
            value = value.lower() in ("true", "yes", "1")
        songs[song_match][field] = value
        _save_registry(data)
        _write_publishing_md()
        return [f"Updated {song_match} — {field}: {value}"]

    # ── Single song detail ─────────────────────────────────────────────────────
    song_match = _match_song(text)
    if song_match and any(k in t for k in ("status", "detail", "info", "rights", "who owns")):
        reply = _format_song_detail(song_match, songs.get(song_match, {}))
        _write_publishing_md()
        return [reply]

    # ── Full catalog (default) ─────────────────────────────────────────────────
    completion = _load_completion()
    reply      = _format_catalog(songs, completion)
    _write_publishing_md()
    return [reply]


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "publishing status"
    print(f"Running publishing brain: '{text}'\n")
    for line in handle(text):
        print(line)
    print(f"\nPublishing MD: {PUBLISHING_MD}")
    print(f"Publishing JSON: {PUBLISHING_JSON}")
