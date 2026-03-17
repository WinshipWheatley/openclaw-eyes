"""
chief_album_batch.py

Cross-album batch planner. Reads CSV, groups songs by work type,
and responds naturally to batch planning queries.

Answers queries like:
  - "what should I do next on the album"
  - "what is the best batch to run"
  - "give me a chill maintenance batch"
  - "give me a creative batch"
  - "vocals batch" / "recording batch" / "cleanup batch" / etc.

Batch types:
  recording     — instrument parts not yet done
  vocals        — vocals not final or re-records needed
  arrangement   — structure / arrangement work needed
  mix           — songs prepped and close or ready to mix
  cleanup       — session prep, labeling, mix prep, organization
  decision      — version not locked, open creative decisions
  creative      — documented refinement needs + structural work
  magic         — songs with captured feels_magical notes to revisit

Triggered by:
  - "batch", "what should I do next", "best batch", "album work"
  - "[type] batch", "give me a [type] batch"
Intent: batch_query in chief_router.py

Reads from: /mnt/c/OpenClawShared/album/album_work_log.csv
Saves to:   /mnt/c/OpenClawShared/openclaw-vault/Album/Batch Plan.md
"""

from datetime import datetime
from pathlib import Path

from chief_album_io import load_all_rows, _is_done, _needs_rerecord

BATCH_MD = Path("/mnt/c/OpenClawShared/openclaw-vault/Album/Batch Plan.md")

# Canonical song list — imported from brain, fallback to empty (all songs used)
try:
    from chief_album_brain import _ALBUM_SONGS
except ImportError:
    _ALBUM_SONGS = []


# ── Batch definitions ─────────────────────────────────────────────────────────

BATCH_DEFS = {
    "recording": {
        "label": "Recording",
        "desc":  "instrument parts not yet tracked or completed",
        "chill": False,
        "check": lambda r: any(
            not _is_done(r.get(f, ""))
            for f in ("drums_pass", "bass_pass", "guitars_pass", "keys_pass")
        ),
    },
    "vocals": {
        "label": "Vocals",
        "desc":  "leads not final, re-records needed, or BGVs outstanding",
        "chill": False,
        "check": lambda r: (
            not _is_done(r.get("vocals_pass", ""))
            or _needs_rerecord(r.get("needs_rerecord", ""))
        ),
    },
    "arrangement": {
        "label": "Arrangement / Writing",
        "desc":  "structure or arrangement pass not complete",
        "chill": False,
        "check": lambda r: not _is_done(r.get("structure_pass", "")),
    },
    "mix": {
        "label": "Mix / Sonics",
        "desc":  "prepped and ready or close to mix",
        "chill": False,
        "check": lambda r: (
            r.get("mix_readiness", "").strip().lower() in ("close", "ready", "not_ready")
            and _is_done(r.get("mix_prep_done", ""))
        ),
    },
    "cleanup": {
        "label": "Cleanup / Organization",
        "desc":  "session prep, labeling, gain staging, mix prep",
        "chill": True,
        "check": lambda r: not _is_done(r.get("mix_prep_done", "")),
    },
    "decision": {
        "label": "Decision / Review",
        "desc":  "version not locked, open creative choices to make",
        "chill": True,
        "check": lambda r: not _is_done(r.get("version_locked", "")),
    },
    "creative": {
        "label": "Creative",
        "desc":  "documented refinement notes — needs a focused creative pass",
        "chill": False,
        "check": lambda r: bool(r.get("needs_refinement", "").strip()),
    },
    "magic": {
        "label": "Keep / Protect",
        "desc":  "songs with documented magic — revisit and make sure it's protected",
        "chill": True,
        "check": lambda r: bool(r.get("feels_magical", "").strip()),
    },
}

# Natural priority order for "best batch" recommendation
_PRIORITY = ["recording", "vocals", "arrangement", "decision", "cleanup", "mix", "creative", "magic"]


# ── Batch builder ─────────────────────────────────────────────────────────────

def _build_batches(rows: list[dict]) -> dict[str, list[dict]]:
    """Return {batch_type: [matching rows]} for all batch types."""
    result = {}
    for btype, defn in BATCH_DEFS.items():
        result[btype] = [r for r in rows if defn["check"](r)]
    return result


def _song_detail(row: dict, btype: str) -> str:
    """Return a brief detail line for a song in a given batch type."""
    song = row.get("song_title", "?")
    if btype == "vocals":
        if _needs_rerecord(row.get("needs_rerecord", "")):
            reason = row.get("rerecord_reason", "see notes")
            return f"{song} — re-record: {reason[:50]}" if reason else f"{song} — re-record needed"
        return f"{song} — leads not final"
    if btype == "recording":
        missing = [f.replace("_pass", "") for f in ("drums_pass", "bass_pass", "guitars_pass", "keys_pass")
                   if not _is_done(row.get(f, ""))]
        return f"{song} — missing: {', '.join(missing)}"
    if btype == "creative":
        note = row.get("needs_refinement", "")[:60]
        return f"{song} — {note}" if note else song
    if btype == "magic":
        note = row.get("feels_magical", "")[:60]
        return f"{song} — {note}" if note else song
    if btype == "mix":
        readiness = row.get("mix_readiness", "?")
        return f"{song} — {readiness}"
    return song


# ── Response builders ─────────────────────────────────────────────────────────

def _format_batch(btype: str, songs: list[dict], show_detail: bool = True) -> str:
    defn = BATCH_DEFS[btype]
    if not songs:
        return f"{defn['label']}: none needed right now"
    names = [_song_detail(r, btype) if show_detail else r.get("song_title", "?")
             for r in songs]
    lines = [f"**{defn['label']}** ({len(songs)} songs) — {defn['desc']}"]
    for name in names:
        lines.append(f"  • {name}")
    return "\n".join(lines)


def _reply_single(rows: list[dict], btype: str) -> list[str]:
    batches = _build_batches(rows)
    songs = batches.get(btype, [])
    defn = BATCH_DEFS[btype]
    if not songs:
        return [f"No songs in the {defn['label']} batch right now."]
    lines = [_format_batch(btype, songs)]
    lines.append(f"\nSay 'album' to start a session for any of these.")
    return ["\n".join(lines)]


def _reply_grouped(rows: list[dict], btypes: list[str], label: str) -> list[str]:
    batches = _build_batches(rows)
    lines = [f"**{label} batch:**\n"]
    has_any = False
    for btype in btypes:
        songs = batches.get(btype, [])
        if songs:
            has_any = True
            lines.append(_format_batch(btype, songs))
            lines.append("")
    if not has_any:
        return [f"Nothing queued for {label.lower()} work right now."]
    lines.append("Say 'album' to start a session for any of these.")
    return ["\n".join(lines)]


def _reply_best(rows: list[dict]) -> list[str]:
    batches = _build_batches(rows)
    # Find largest / most impactful batch
    best_type = max(
        _PRIORITY,
        key=lambda b: len(batches.get(b, [])),
        default=None,
    )
    if not best_type or not batches.get(best_type):
        return ["All batches look clear — album is in good shape."]

    songs = batches[best_type]
    defn  = BATCH_DEFS[best_type]
    lines = [
        f"Best batch to run next: **{defn['label']}** ({len(songs)} songs)\n",
        _format_batch(best_type, songs),
        "",
    ]

    # Show a quick summary of other non-empty batches
    others = [(b, batches[b]) for b in _PRIORITY
              if b != best_type and batches.get(b)]
    if others:
        other_str = "  ".join(f"{BATCH_DEFS[b]['label']} ({len(s)})" for b, s in others[:4])
        lines.append(f"Other batches: {other_str}")
        lines.append("Say 'give me a [type] batch' for details.")

    lines.append("\nSay 'album' to start a session for any of these.")
    return ["\n".join(lines)]


def _reply_overview(rows: list[dict]) -> list[str]:
    """Full overview of all batch states."""
    batches = _build_batches(rows)
    lines = [f"**Album Batch Overview** — {len(rows)} songs\n"]
    for btype in _PRIORITY:
        songs = batches.get(btype, [])
        defn  = BATCH_DEFS[btype]
        if songs:
            names = ", ".join(r.get("song_title", "?") for r in songs[:4])
            tail  = f" +{len(songs)-4} more" if len(songs) > 4 else ""
            lines.append(f"  {defn['label']} ({len(songs)}): {names}{tail}")
        else:
            lines.append(f"  {defn['label']}: ✓ clear")
    lines.append("\nSay 'give me a [type] batch' or 'what should I do next'.")
    return ["\n".join(lines)]


def _save_batch_md(rows: list[dict]) -> None:
    batches = _build_batches(rows)
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "---\ntype: batch-plan\n---\n",
        "# Album Batch Plan\n",
        f"_Updated: {today}_\n",
    ]
    for btype in _PRIORITY:
        songs = batches.get(btype, [])
        defn  = BATCH_DEFS[btype]
        lines.append(f"\n## {defn['label']}\n\n_{defn['desc']}_\n")
        if songs:
            for r in songs:
                lines.append(f"- {_song_detail(r, btype)}")
        else:
            lines.append("_Clear_")
    BATCH_MD.parent.mkdir(parents=True, exist_ok=True)
    BATCH_MD.write_text("\n".join(lines), encoding="utf-8")


# ── Intent detection ──────────────────────────────────────────────────────────

def batch_intent(text: str) -> bool:
    t = text.lower().strip()
    triggers = [
        "batch", "what should i do", "what to do next", "next batch",
        "album work", "what's the best", "whats the best",
        "what should we", "what should i work on",
        "give me a", "album overview", "batch overview",
        "batch plan", "what needs doing",
    ]
    return any(k in t for k in triggers)


# ── Public entry point ────────────────────────────────────────────────────────

def handle(text: str) -> list[str]:
    rows = load_all_rows()
    # Filter to canonical album songs only if possible
    if _ALBUM_SONGS:
        known = {s.lower() for s in _ALBUM_SONGS}
        rows = [r for r in rows if r.get("song_title", "").lower() in known] or rows
    if not rows:
        return ["No album data yet. Run album sessions first."]

    t = text.lower()
    _save_batch_md(rows)

    # Specific batch type requests
    if "chill" in t or "maintenance" in t or "easy" in t or "light" in t:
        return _reply_grouped(rows, ["cleanup", "decision", "magic"], "Chill / Maintenance")
    if "creative" in t and "batch" in t:
        return _reply_grouped(rows, ["creative", "arrangement", "vocals"], "Creative")
    if "vocal" in t:
        return _reply_single(rows, "vocals")
    if "record" in t and ("batch" in t or "day" in t or "session" in t):
        return _reply_single(rows, "recording")
    if "mix" in t or "sonic" in t:
        return _reply_single(rows, "mix")
    if "cleanup" in t or "organiz" in t or "prep" in t or "housekeep" in t:
        return _reply_single(rows, "cleanup")
    if "decision" in t or "lock" in t:
        return _reply_single(rows, "decision")
    if "magic" in t or "special" in t or "protect" in t:
        return _reply_single(rows, "magic")
    if "arrangement" in t or "writing" in t or "structure" in t and "batch" in t:
        return _reply_single(rows, "arrangement")
    if "overview" in t or "all batch" in t or "all work" in t:
        return _reply_overview(rows)

    # Generic: "what should I do next", "best batch", "what to do"
    return _reply_best(rows)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "what should I do next on the album"
    for line in handle(text):
        print(line)
